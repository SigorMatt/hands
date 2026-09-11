"""The daemon — the process that owns the roles, the queue and the socket (DESIGN §3).

    handsd  (user daemon, unix socket ~/.hands/handsd.sock)
      ├─ api         local JSON-RPC over the socket; the CLI is a thin client
      ├─ runner      spawns claude -p per job, one per role, stream-json parser
      └─ spool       ~/.hands/jobs/<id>.json, ~/.hands/roles/<role>.json, inbox

Everything the daemon knows is in the spool, so a restart loses nothing: running
jobs whose process is gone are marked `orphaned` (§3) and jobs still `queued` are
picked up again in FIFO order.

The wire is newline-delimited JSON-RPC 2.0, one object per line:

    --> {"jsonrpc":"2.0","id":1,"method":"send","params":{"role":"builder",…}}
    <-- {"jsonrpc":"2.0","id":1,"result":{…}}
    <-- {"jsonrpc":"2.0","id":1,"error":{"code":-32001,"message":"…"}}

Requests on one connection are served concurrently, so a long `hands wait` never
blocks another client.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import inspect
import json
import keyword
import logging
import os
import signal
import socket as socket_mod
import sys
from collections import deque
from collections.abc import Sequence
from pathlib import Path
from typing import Any, TextIO

from hands import __version__
from hands.api import Api, ApiError, job_summary
from hands.config import Config, ConfigError, load_config, resolve_project
from hands.runner import MAX_PROMPT_BYTES, Runner, RunnerError, reconcile_orphans
from hands.spool import TERMINAL_STATES, Job, Spool, now_iso

__all__ = ["Daemon", "DaemonError", "main"]

log = logging.getLogger("hands.daemon")

# JSON-RPC 2.0 protocol errors.
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

# One request may carry a 10 MB prompt (§2), well over asyncio's 64 KiB default
# line limit; the reader is given the same room the runner gives the stream.
_LINE_LIMIT = MAX_PROMPT_BYTES + 1024 * 1024

_SHUTDOWN_GRACE_S = 30.0  # ceiling on waiting for cancelled jobs to write their record

class DaemonError(Exception):
    """The daemon cannot start, or cannot do what it was asked."""


class Daemon:
    """One project's daemon: role queues, the runner, and the JSON-RPC socket.

    Startable in-process (`await start()` … `await stop()`) as well as from
    `handsd`, so a test drives the same code path a terminal does.
    """

    def __init__(self, config: Config, *, socket_path: Path | None = None) -> None:
        self.config = config
        # The spool lives beside the config: `~/.hands/<project>.toml` → `~/.hands`.
        self.spool = Spool(config.path.parent)
        self.runner = Runner(config, self.spool, on_stream_line=self._capture)
        self.api = Api(self)
        self.socket_path = Path(socket_path) if socket_path else config.server.socket
        self.started: str | None = None

        self._roles = tuple(config.roles)
        #: role → job ids accepted and not yet picked up. This, not the spool, is
        #: the queue: a job is `queued` on disk from `send` until the worker
        #: transitions it, and only the daemon knows which of those it has picked.
        self._waiting: dict[str, deque[str]] = {role: deque() for role in self._roles}
        self._tokens: dict[str, asyncio.Queue[str | None]] = {
            role: asyncio.Queue() for role in self._roles
        }
        self._running: dict[str, str | None] = dict.fromkeys(self._roles)
        #: job id → the undecided `cancel` gate of §8, for `roles.<role>.cancel_gated`.
        #: It lives here and not on the job record because a cancel gate is a gate on
        #: the *request*, not on the job: the job keeps running, and the runner owns
        #: its record until it stops. The request is the daemon's, so it dies with the
        #: daemon — which is the safe direction, since nothing is ever cancelled
        #: without a decision. The inbox keeps the permanent trail (§11).
        self.pending_cancels: dict[str, dict[str, Any]] = {}
        self._workers: list[asyncio.Task[None]] = []
        self._conns: set[asyncio.Task[None]] = set()
        self._streams: dict[str, TextIO] = {}
        self._changed = asyncio.Condition()
        self._server: asyncio.Server | None = None
        self._stopping = False

    # ------------------------------------------------------------- lifecycle

    async def start(self) -> None:
        """Reconcile orphans, bind the socket, start the role workers (§3)."""
        orphans = reconcile_orphans(self.spool)
        for job in orphans:
            log.warning("job %s was running with no process; marked orphaned", job.id)

        self._bind_guard()
        self._server = await asyncio.start_unix_server(
            self._handle_conn, path=str(self.socket_path), limit=_LINE_LIMIT
        )
        # The socket lets its caller run `claude -p` as this user (§9, blast
        # radius): it is nobody else's business.
        os.chmod(self.socket_path, 0o600)

        self._workers = [
            asyncio.create_task(self._worker(role), name=f"hands-worker-{role}")
            for role in self._roles
        ]
        self.started = now_iso()
        self._readmit_queued()
        log.info(
            "handsd %s listening on %s (project %s)",
            __version__, self.socket_path, self.config.project,
        )

    async def serve_forever(self) -> None:
        if self._server is None:  # pragma: no cover - defensive
            raise DaemonError("start() first")
        await self._server.serve_forever()

    async def stop(self) -> None:
        """Graceful shutdown: no new clients, cancel running jobs, leave no strays."""
        if self._stopping:
            return
        self._stopping = True

        if self._server is not None:
            self._server.close()
            with contextlib.suppress(Exception):
                await self._server.wait_closed()

        # A running claude must never outlive the daemon: SIGINT, then SIGTERM
        # (§2). Its record becomes `killed`; a job still `queued` stays queued
        # and the next daemon picks it up.
        for job_id in [value for value in self._running.values() if value]:
            with contextlib.suppress(Exception):
                await self._signal_stop(job_id)
        for role in self._roles:
            self._tokens[role].put_nowait(None)
        if self._workers:
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(
                    asyncio.gather(*self._workers, return_exceptions=True), _SHUTDOWN_GRACE_S
                )
            for task in self._workers:
                task.cancel()
            await asyncio.gather(*self._workers, return_exceptions=True)
            self._workers = []

        for task in list(self._conns):
            task.cancel()
        if self._conns:
            await asyncio.gather(*self._conns, return_exceptions=True)
        self._conns.clear()

        for stream in self._streams.values():
            with contextlib.suppress(Exception):
                stream.close()
        self._streams.clear()

        with contextlib.suppress(OSError):
            self.socket_path.unlink()
        log.info("handsd stopped")

    def _bind_guard(self) -> None:
        self.socket_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.socket_path.exists():
            return
        probe = socket_mod.socket(socket_mod.AF_UNIX, socket_mod.SOCK_STREAM)
        try:
            probe.connect(str(self.socket_path))
        except OSError:
            self.socket_path.unlink()  # stale socket of a dead daemon
            return
        finally:
            probe.close()
        raise DaemonError(f"a daemon is already listening on {self.socket_path}")

    # ----------------------------------------------------------------- queue

    def enqueue(
        self,
        *,
        role: str,
        context: str,
        prompt: str,
        origin: str,
        gate: dict[str, Any] | None = None,
        files_written: list[dict[str, Any]] | None = None,
    ) -> Job:
        """Accept a send: create the record and either hold it or join the FIFO.

        A gated job is born `held` (§6, §8) and takes no queue slot until a human
        approves it, so the depth check is the queue's, not the gate's: it runs
        on admission, here for an ungated send and in `release` for an approved
        one.
        """
        if gate is None:
            self._check_depth(role)
        job = self.spool.create_job(
            role=role,
            context=context,
            prompt=prompt,
            origin=origin,
            state="held" if gate else "queued",
            gate=gate,
            files_written=files_written or [],
        )
        if gate is None:
            self._admit(job)
        return job

    def _check_depth(self, role: str) -> None:
        depth = self.config.role(role).queue_depth
        waiting = len(self._waiting[role])
        if waiting >= depth:
            running = self._running.get(role)
            behind = f" behind running job {running}" if running else ""
            raise ApiError(
                f"role {role} already has {waiting} job(s) queued{behind} and "
                f"roles.{role}.queue_depth is {depth}; wait or cancel one"
            )

    async def release(self, job: Job, *, gate: dict[str, Any]) -> Job:
        """held → queued: an approved job joins the normal path (§6, §8).

        The queue depth is the role's, not the gate's: approving into a full
        queue is refused and the job stays `held`, to be approved when there is
        room. Nothing else in hands calls this — that is the whole of "nothing
        else releases a held job".
        """
        if job.state != "held":
            raise ApiError(f"job {job.id} is {job.state}, not held")
        self._check_depth(job.role)
        released = self.spool.transition(job, "queued", gate=gate)
        self._admit(released)
        await self._announce()
        return released

    def _admit(self, job: Job) -> None:
        """Put a `queued` job at the back of its role's FIFO.

        The seam for §8: a `held` job is created outside the queue and occupies
        no slot until a human approves it, at which point U4 moves it held →
        queued and calls this.
        """
        self._waiting[job.role].append(job.id)
        self._tokens[job.role].put_nowait(job.id)

    def _readmit_queued(self) -> None:
        """Re-admit jobs left `queued` by a previous daemon, oldest first (§3)."""
        for job in self.spool.list_jobs():
            if job.state == "queued" and job.role in self._waiting:
                self._admit(job)
                log.info("re-queued job %s (%s) from the spool", job.id, job.role)

    async def _worker(self, role: str) -> None:
        """One worker per role — this is the "one running job per role" rule (§6)."""
        tokens = self._tokens[role]
        while True:
            await tokens.get()
            if self._stopping:
                return
            if not self._waiting[role]:
                continue  # the job was cancelled while it waited
            job_id = self._waiting[role].popleft()
            await self._run(role, job_id)
            if self._stopping:
                return

    async def _run(self, role: str, job_id: str) -> None:
        job = self.spool.load_job(job_id)
        if job.state != "queued":  # cancelled or decided while it waited
            return
        self._running[role] = job_id
        await self._announce()
        stream = (self.spool.jobs_dir / f"{job_id}.stream.jsonl").open("a", encoding="utf-8")
        self._streams[job_id] = stream
        try:
            log.info("job %s (%s) starting", job_id, role)
            finished = await self.runner.run(job)
            log.info("job %s (%s) %s", job_id, role, finished.state)
        except RunnerError as exc:
            # The job was accepted but cannot be spawned (a `keep` whose session
            # went away between the send and its turn, or an oversized prompt).
            # §6 gives `queued` exactly one other edge, so that is where it goes;
            # the reason is in the inbox because §6's record has no field for it.
            current = self.spool.load_job(job_id)
            if current.state == "queued":
                self.spool.transition(current, "killed")
                self.spool.append_event(
                    "job.killed",
                    {"job": job_id, "role": role, "state": "killed", "reason": str(exc)},
                )
            log.warning("job %s (%s) could not run: %s", job_id, role, exc)
        except Exception:  # pragma: no cover - a bug here must not kill the worker
            log.exception("job %s (%s) raised", job_id, role)
        finally:
            self._streams.pop(job_id, None)
            with contextlib.suppress(Exception):
                stream.close()
            self._running[role] = None
            await self._announce()

    def _capture(self, job_id: str, line: str) -> None:
        """Persist one captured stdout line so `hands log` (U9) has something to read."""
        stream = self._streams.get(job_id)
        if stream is None:  # pragma: no cover - the job is not ours
            return
        try:
            stream.write(line + "\n")
            stream.flush()
        except OSError as exc:  # pragma: no cover - a full disk must not kill the job
            log.warning("job %s: cannot write its stream: %s", job_id, exc)

    # ------------------------------------------------------------ job waiting

    async def _announce(self) -> None:
        async with self._changed:
            self._changed.notify_all()

    async def wait_for_terminal(self, job_id: str, *, timeout: float | None = None) -> Job | None:
        """The job record once it is terminal, or None if `timeout` expired (§4)."""
        loop = asyncio.get_running_loop()
        deadline = None if timeout is None else loop.time() + float(timeout)
        async with self._changed:
            while True:
                job = self.spool.load_job(job_id)
                if job.state in TERMINAL_STATES:
                    return job
                if deadline is None:
                    await self._changed.wait()
                    continue
                remaining = deadline - loop.time()
                if remaining <= 0:
                    return None
                try:
                    await asyncio.wait_for(self._changed.wait(), remaining)
                except TimeoutError:
                    return None

    async def cancel(self, job: Job, *, reason: str | None = None) -> Job:
        """Stop a job wherever it is: in the queue, or in flight (§2, §4)."""
        if job.state in TERMINAL_STATES:
            raise ApiError(f"job {job.id} is already {job.state}")
        if job.state == "held":
            raise ApiError(
                f"job {job.id} is held and has not run; §6 gives it no edge to "
                f"`killed`. Release or refuse it with `hands approve {job.id}` "
                f"or `hands deny {job.id}` (§8)"
            )
        if job.state == "queued":
            with contextlib.suppress(ValueError):
                self._waiting[job.role].remove(job.id)
            killed = self.spool.transition(job, "killed")
            self.spool.append_event(
                "job.killed",
                {"job": job.id, "role": job.role, "state": "killed", "reason": reason},
            )
            await self._announce()
            return killed

        await self._signal_stop(job.id)
        grace = self.config.runner.cancel_grace_s + 10.0
        finished = await self.wait_for_terminal(job.id, timeout=grace)
        return finished if finished is not None else self.spool.load_job(job.id)

    async def _signal_stop(self, job_id: str) -> None:
        """SIGINT then SIGTERM the job's process (§2), even if it was just spawned.

        `send` → spawn is not instantaneous, so a cancel (or a shutdown) that
        arrives in that window would otherwise signal nothing and leave a live
        `claude` behind.
        """
        if not self.runner.is_running(job_id):
            if self.spool.load_job(job_id).state in TERMINAL_STATES:
                return
            with contextlib.suppress(TimeoutError):
                await self.runner.wait_until_running(job_id, timeout=5.0)
        await self.runner.cancel(job_id)

    # ---------------------------------------------------------------- status

    def status(self) -> dict[str, Any]:
        """§4: "daemon, roles, running jobs, monitor state"."""
        running: list[dict[str, Any]] = []
        roles: dict[str, Any] = {}
        for role in self._roles:
            job_id = self._running.get(role)
            summary = job_summary(self.spool.load_job(job_id)) if job_id else None
            if summary is not None:
                running.append(summary)
            state = self.spool.read_role(role)
            roles[role] = {
                "cwd": str(self.config.role(role).cwd),
                "model": self.config.role(role).model,
                "queue_depth": self.config.role(role).queue_depth,
                "running": summary,
                "queued": list(self._waiting[role]),
                "last_session_id": state.last_session_id,
            }
        return {
            "daemon": {
                "project": self.config.project,
                "version": __version__,
                "pid": os.getpid(),
                "socket": str(self.socket_path),
                "config": str(self.config.path),
                "spool": str(self.spool.root),
                "started": self.started,
                "stopping": self._stopping,
            },
            "roles": roles,
            "running": running,
            # §5's monitor is U6; saying so is better than an empty dict that
            # reads like "nothing is wrong".
            "monitor": {"implemented": False, "note": "the monitor is unit U6 (§5)"},
            "inbox": {"unacked": len(self.spool.unacked())},
        }

    # -------------------------------------------------------------- JSON-RPC

    async def _handle_conn(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        lock = asyncio.Lock()
        pending: set[asyncio.Task[None]] = set()
        task = asyncio.current_task()
        if task is not None:
            self._conns.add(task)
            task.add_done_callback(self._conns.discard)
        try:
            while True:
                try:
                    line = await reader.readline()
                except (ValueError, ConnectionError) as exc:
                    await self._write(
                        writer, lock, _error(None, INVALID_REQUEST, f"bad request: {exc}")
                    )
                    break
                if not line:
                    break
                if not line.strip():
                    continue
                sub = asyncio.create_task(self._serve(line, writer, lock))
                pending.add(sub)
                sub.add_done_callback(pending.discard)
        finally:
            for sub in list(pending):
                sub.cancel()
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()

    async def _serve(self, line: bytes, writer: asyncio.StreamWriter, lock: asyncio.Lock) -> None:
        response = await self._respond(line)
        if response is not None:
            await self._write(writer, lock, response)

    async def _respond(self, line: bytes) -> dict[str, Any] | None:
        try:
            request = json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            return _error(None, PARSE_ERROR, f"not JSON: {exc}")
        if not isinstance(request, dict):
            return _error(None, INVALID_REQUEST, "a request must be a JSON object")
        request_id = request.get("id")
        is_notification = "id" not in request
        name = request.get("method")
        params = request.get("params", {})
        if not isinstance(name, str):
            return None if is_notification else _error(request_id, INVALID_REQUEST, "no method")
        if not isinstance(params, dict):
            return (
                None
                if is_notification
                else _error(request_id, INVALID_PARAMS, "params must be an object")
            )

        method = self.api.method(name)
        if method is None:
            known = ", ".join(Api.COMMANDS)
            return (
                None
                if is_notification
                else _error(request_id, METHOD_NOT_FOUND, f"no method {name!r}; hands has: {known}")
            )
        try:
            kwargs = _bind(method, params)
        except TypeError as exc:
            return None if is_notification else _error(request_id, INVALID_PARAMS, str(exc))

        try:
            result = await method(**kwargs)
        except ApiError as exc:
            return None if is_notification else _error(request_id, exc.code, str(exc))
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # a bug, a broken spool file, an OS error
            log.exception("method %s failed", name)
            return (
                None
                if is_notification
                else _error(request_id, INTERNAL_ERROR, f"{type(exc).__name__}: {exc}")
            )
        return None if is_notification else {"jsonrpc": "2.0", "id": request_id, "result": result}

    @staticmethod
    async def _write(
        writer: asyncio.StreamWriter, lock: asyncio.Lock, payload: dict[str, Any]
    ) -> None:
        async with lock:
            try:
                writer.write(json.dumps(payload).encode("utf-8") + b"\n")
                await writer.drain()
            except (ConnectionError, RuntimeError):  # the client hung up mid-answer
                pass


def _bind(method: Any, params: dict[str, Any]) -> dict[str, Any]:
    """Map JSON-RPC params onto an API method, refusing anything it cannot take.

    The names are the CLI's (§9), so one of them — `for`, of `wait --for` — is a
    Python keyword; a keyword param is spelled with a trailing underscore in
    Python and without it on the wire.
    """
    kwargs = {(f"{k}_" if keyword.iskeyword(k) else k): v for k, v in params.items()}
    inspect.signature(method).bind(**kwargs)  # raises TypeError, caught by the caller
    return kwargs


def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


# --------------------------------------------------------------------- handsd


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="handsd",
        description="The hands daemon: one project's roles, queue and local API (DESIGN §3).",
    )
    parser.add_argument(
        "--project",
        help="the project named by ~/.hands/<project>.toml; "
        "defaults to $HANDS_PROJECT, or to the only config there is",
    )
    parser.add_argument("--socket", help="override server.socket from the config")
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="stderr log level (default INFO)",
    )
    parser.add_argument("--version", action="version", version=f"handsd {__version__}")
    return parser


async def _serve(config: Config, socket_path: Path | None) -> int:
    daemon = Daemon(config, socket_path=socket_path)
    loop = asyncio.get_running_loop()
    stop = asyncio.Event()
    for signum in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):  # pragma: no cover - posix only
            loop.add_signal_handler(signum, stop.set)
    await daemon.start()
    try:
        await stop.wait()
    finally:
        await daemon.stop()
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=args.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    try:
        project = resolve_project(args.project)
        config = load_config(project)
    except ConfigError as exc:
        print(f"handsd: {exc}", file=sys.stderr)
        return 1
    socket_path = Path(args.socket).expanduser() if args.socket else None
    try:
        return asyncio.run(_serve(config, socket_path))
    except DaemonError as exc:
        print(f"handsd: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
