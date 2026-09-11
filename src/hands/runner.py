"""The runner — one `claude -p` process per job (DESIGN §2, §6).

This module owns exactly one job at a time: spawn it, parse its stream-json,
fill the record of §6, move it to a terminal state, and cancel it on request.
Queueing, the one-running-job-per-role rule and everything else about *which*
job runs next belong to the daemon (§3), which drives this as a library.

The invocation is §2, verbatim:

    cd <role.cwd>
    claude -p [--resume <id>] --output-format stream-json --verbose \\
      --model <role.model> <role.permission_flags> --permission-prompts none

All six flags were checked against the installed binary (claude 2.1.268,
`claude --help`) before this was written; each exists with that spelling, and
`--permission-prompts` does take `none`.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import signal
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from hands.config import Config, RoleConfig
from hands.spool import TERMINAL_STATES, Job, Spool, SpoolError

__all__ = [
    "MAX_PROMPT_BYTES",
    "KeepRefused",
    "Runner",
    "RunnerError",
    "build_argv",
    "extract_verdict",
    "project_dir_name",
    "reconcile_orphans",
    "transcript_path_for",
]


class RunnerError(Exception):
    """The runner was asked for something it cannot do."""


class KeepRefused(RunnerError):
    """`--context keep` has no session to resume, or that session is still busy (§6).

    Raised before anything is spawned; the job is left exactly as it was. §6
    makes this a refusal of the *send*, not a job outcome, and §6's state machine
    has no `queued → failed` edge to put an outcome on.
    """


# §2: "The prompt arrives on stdin (10 MB cap; long content is written as a file
# first and named in the prompt)." Writing the file is `send --file`, not here.
MAX_PROMPT_BYTES = 10 * 1024 * 1024

# One stream-json line can be large (a whole result). asyncio's default 64 KiB
# reader limit would raise on it, so the reader is given room for the cap.
_STREAM_LIMIT = MAX_PROMPT_BYTES + 1024 * 1024

_STDERR_TAIL_LINES = 50  # §6: "stderr_tail  # last 50 lines"

_VERDICT_RE = re.compile(r"^VERDICT:")  # §6: "the first line of result matching ^VERDICT:"

# §6 detects a limit from "the `api_retry` error category `rate_limit` or the
# limit notice in `result`". In claude 2.1.268 the wire event is
# `{"type":"system","subtype":"api_retry", … "error":"rate_limit"}` — the
# category lives in the `error` field, whose schema is an enum that contains
# `rate_limit`; `category` is read too in case a future build renames it.
_RATE_LIMIT = "rate_limit"
# The notice text, kept deliberately narrow: the only phrasing this unit can
# point at evidence for is the binary's own "Usage limit reached". Widening it,
# parsing the reset time and scheduling the retry are U5's.
_LIMIT_NOTICE_RE = re.compile(r"usage limit reached", re.IGNORECASE)

# Claude Code's project directory under ~/.claude/projects is the working
# directory with every non-alphanumeric character replaced by "-" (see the
# evidence in meta/findings/FINDINGS.md H-001).
_NON_ALNUM_RE = re.compile(r"[^a-zA-Z0-9]")


# ------------------------------------------------------------- pure helpers


def project_dir_name(cwd: str | os.PathLike[str]) -> str:
    """The `~/.claude/projects/<name>` directory Claude Code uses for `cwd`."""
    return _NON_ALNUM_RE.sub("-", str(Path(cwd)))


def transcript_path_for(cwd: str | os.PathLike[str], session_id: str) -> str:
    """`~/.claude/projects/<dashed cwd>/<session_id>.jsonl` (§2).

    Derived, never verified: the file is Claude Code's to create, and at the
    moment of the init event it may not exist yet.
    """
    base = Path("~/.claude/projects").expanduser()
    return str(base / project_dir_name(cwd) / f"{session_id}.jsonl")


def extract_verdict(result: str | None) -> str | None:
    """The first line of `result` matching `^VERDICT:`, verbatim, or None (§6)."""
    if not result:
        return None
    for line in result.splitlines():
        if _VERDICT_RE.match(line):
            return line.rstrip()
    return None


def build_argv(config: Config, role: RoleConfig, *, resume: str | None = None) -> list[str]:
    """The §2 invocation, in the order §2 writes it."""
    argv = [config.runner.claude, "-p"]
    if resume is not None:
        argv += ["--resume", resume]
    argv += ["--output-format", "stream-json", "--verbose", "--model", role.model]
    argv += list(role.permission_argv)
    argv += ["--permission-prompts", "none"]
    return argv


# ------------------------------------------------------------ orphan sweep


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:  # exists, owned by someone else
        return True
    except OSError:  # pragma: no cover - defensive
        return True
    return True


def reconcile_orphans(spool: Spool) -> list[Job]:
    """Mark every `running` job whose process is gone as `orphaned` (§3, §6).

    The daemon calls this once at startup, before it dispatches anything. A pid
    that has been reused by an unrelated process reads as alive and the job
    stays `running`; the monitor (§5) is what notices a job that never ends.
    """
    orphans = []
    for job in spool.list_jobs():
        if job.state != "running":
            continue
        if job.pid is not None and _pid_alive(job.pid):
            continue
        spool.transition(job, "orphaned")
        spool.append_event("job.orphaned", _event_payload(job))
        orphans.append(job)
    return orphans


def _event_payload(job: Job) -> dict[str, Any]:
    return {
        "job": job.id,
        "role": job.role,
        "state": job.state,
        "session_id": job.session_id,
        "verdict": job.verdict,
    }


# ---------------------------------------------------------- stream parsing


@dataclass
class _Parsed:
    """What the stream-json of one run yielded."""

    session_id: str | None = None
    result: str | None = None
    is_error: bool = False
    saw_result: bool = False
    num_turns: int | None = None
    duration_ms: int | None = None
    total_cost_usd: float | None = None
    permission_denials: list[Any] = field(default_factory=list)
    limit_category: str | None = None
    limit_message: str | None = None


def _as_int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


# ------------------------------------------------------------------ runner


class Runner:
    """Spawns and supervises one `claude -p` per job.

    The daemon (§3) owns the queue and calls `run()` for the job it picked;
    `cancel()` is safe to call from another task while `run()` is in flight.
    """

    def __init__(self, config: Config, spool: Spool) -> None:
        self.config = config
        self.spool = spool
        self._procs: dict[str, asyncio.subprocess.Process] = {}
        self._cancelled: set[str] = set()
        self._running: dict[str, asyncio.Event] = {}
        self._session_ready: dict[str, asyncio.Event] = {}
        #: job id → the argv it was spawned with, for `hands status`/tests.
        self.last_argv: dict[str, list[str]] = {}

    # ------------------------------------------------------------ sessions

    def resolve_resume_session(self, role: str) -> str:
        """The session id `--context keep` resumes, or raise `KeepRefused` (§6)."""
        state = self.spool.read_role(role)
        if not state.last_session_id:
            raise KeepRefused(f"role {role!r} has no session to resume; send --context clear")
        if not state.last_job:
            raise KeepRefused(
                f"role {role!r} has session {state.last_session_id} but no job for it; "
                "refusing to resume a session whose state is unknown"
            )
        try:
            last = self.spool.load_job(state.last_job)
        except SpoolError as exc:
            raise KeepRefused(f"role {role!r}: {exc}") from exc
        if last.state not in TERMINAL_STATES:
            raise KeepRefused(
                f"role {role!r}: job {last.id} is {last.state}; "
                "§2 never resumes a session whose job is still running"
            )
        return state.last_session_id

    # ----------------------------------------------------------- lifecycle

    def is_running(self, job_id: str) -> bool:
        proc = self._procs.get(job_id)
        return proc is not None and proc.returncode is None

    async def wait_until_running(self, job_id: str, *, timeout: float = 30.0) -> None:
        """Block until the job's process exists. The daemon needs this; so do tests."""
        event = self._running.setdefault(job_id, asyncio.Event())
        await asyncio.wait_for(event.wait(), timeout)

    async def wait_for_session(self, job_id: str, *, timeout: float = 30.0) -> None:
        """Block until the job's `system`/`init` event has given up a session id.

        A spawned process is not yet a usable one: until claude has booted there
        is no session to resume, no transcript to tail, and a SIGINT would land
        on the default handler. `hands log -f` and `cancel` want this point, not
        the fork.
        """
        event = self._session_ready.setdefault(job_id, asyncio.Event())
        await asyncio.wait_for(event.wait(), timeout)

    async def run(self, job: Job) -> Job:
        """Run one `queued` job to a terminal state and return the finished record."""
        if job.state != "queued":
            raise RunnerError(f"job {job.id} is {job.state}; only a queued job can be run")
        role = self.config.role(job.role)

        size = len(job.prompt.encode("utf-8"))
        if size > MAX_PROMPT_BYTES:
            raise RunnerError(
                f"prompt is {size} bytes, over the {MAX_PROMPT_BYTES} byte cap of §2; "
                "write the content to a file and name it in the prompt"
            )

        resume = self.resolve_resume_session(job.role) if job.context == "keep" else None
        argv = build_argv(self.config, role, resume=resume)
        self.last_argv[job.id] = argv

        head_at_start = await _git_head(role.cwd)
        job = self.spool.transition(job, "running", head_at_start=head_at_start)

        try:
            proc = await asyncio.create_subprocess_exec(
                *argv,
                cwd=str(role.cwd),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                limit=_STREAM_LIMIT,
            )
        except OSError as exc:
            # The one dispatch failure that never produces a process. `failed` is
            # the only terminal state §6 offers for it.
            reason = f"cannot spawn {argv[0]}: {exc}"
            return await self._finish(job, role, "failed", _Parsed(), None, reason)

        self._procs[job.id] = proc
        job.pid = proc.pid
        self.spool.save_job(job)
        self._running.setdefault(job.id, asyncio.Event()).set()

        parsed = _Parsed()
        stderr_lines: list[str] = []
        try:
            await asyncio.gather(
                self._write_prompt(proc, job.prompt),
                self._read_stdout(proc, job, role, parsed),
                self._read_stderr(proc, stderr_lines),
            )
            exit_code = await proc.wait()
        finally:
            self._procs.pop(job.id, None)
            self._running.pop(job.id, None)
            self._session_ready.pop(job.id, None)

        cancelled = job.id in self._cancelled
        self._cancelled.discard(job.id)
        state = _final_state(parsed, exit_code, cancelled=cancelled)
        tail = "\n".join(stderr_lines[-_STDERR_TAIL_LINES:]) or None
        return await self._finish(job, role, state, parsed, exit_code, tail)

    async def cancel(self, job_id: str, *, grace_s: float | None = None) -> bool:
        """SIGINT, wait `cancel_grace_s`, then SIGTERM (§2). False if not running."""
        proc = self._procs.get(job_id)
        if proc is None or proc.returncode is not None:
            return False
        self._cancelled.add(job_id)
        grace = self.config.runner.cancel_grace_s if grace_s is None else grace_s
        _signal(proc, signal.SIGINT)
        try:
            await asyncio.wait_for(asyncio.shield(_wait(proc)), grace)
        except TimeoutError:
            _signal(proc, signal.SIGTERM)
        return True

    # -------------------------------------------------------------- internals

    async def _write_prompt(self, proc: asyncio.subprocess.Process, prompt: str) -> None:
        stdin = proc.stdin
        if stdin is None:  # pragma: no cover - PIPE is always requested
            return
        try:
            stdin.write(prompt.encode("utf-8"))
            await stdin.drain()
        except (BrokenPipeError, ConnectionResetError):
            pass  # the process ended before it read the prompt; its exit says why
        finally:
            try:
                stdin.close()
            except (BrokenPipeError, ConnectionResetError):  # pragma: no cover
                pass

    async def _read_stdout(
        self, proc: asyncio.subprocess.Process, job: Job, role: RoleConfig, parsed: _Parsed
    ) -> None:
        stream = proc.stdout
        if stream is None:  # pragma: no cover
            return
        async for raw in stream:
            line = raw.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue  # not every line of a real run is an event
            if not isinstance(event, dict):
                continue
            self._on_event(event, job, role, parsed)

    def _on_event(
        self, event: dict[str, Any], job: Job, role: RoleConfig, parsed: _Parsed
    ) -> None:
        session_id = event.get("session_id")
        if isinstance(session_id, str) and session_id and parsed.session_id is None:
            parsed.session_id = session_id
            job.session_id = session_id
            job.transcript_path = transcript_path_for(role.cwd, session_id)
            self.spool.save_job(job)
            # Written as soon as it is known so that a `keep` send arriving while
            # this job runs can see that the session's last job is not terminal.
            self.spool.set_last_session(job.role, session_id=session_id, job_id=job.id)
            self._session_ready.setdefault(job.id, asyncio.Event()).set()

        kind = event.get("type")
        if kind == "system" and event.get("subtype") == "api_retry":
            category = event.get("error") or event.get("category")
            if category == _RATE_LIMIT:
                parsed.limit_category = _RATE_LIMIT
                parsed.limit_message = json.dumps(event, sort_keys=True)
            return
        if kind != "result":
            return

        parsed.saw_result = True
        parsed.is_error = bool(event.get("is_error"))
        result = event.get("result")
        if isinstance(result, str):
            parsed.result = result  # verbatim; never trimmed, never reformatted
        elif isinstance(event.get("errors"), list):
            parsed.result = "\n".join(str(item) for item in event["errors"]) or None
        parsed.num_turns = _as_int(event.get("num_turns"))
        parsed.duration_ms = _as_int(event.get("duration_ms"))
        parsed.total_cost_usd = _as_float(event.get("total_cost_usd"))
        denials = event.get("permission_denials")
        parsed.permission_denials = list(denials) if isinstance(denials, list) else []
        if (
            parsed.limit_category is None
            and isinstance(result, str)
            and _LIMIT_NOTICE_RE.search(result)
        ):
            parsed.limit_category = _RATE_LIMIT
            parsed.limit_message = result

    @staticmethod
    async def _read_stderr(proc: asyncio.subprocess.Process, sink: list[str]) -> None:
        stream = proc.stderr
        if stream is None:  # pragma: no cover
            return
        async for raw in stream:
            sink.append(raw.decode("utf-8", errors="replace").rstrip("\n"))
            del sink[:-_STDERR_TAIL_LINES]

    async def _finish(
        self,
        job: Job,
        role: RoleConfig,
        state: str,
        parsed: _Parsed,
        exit_code: int | None,
        stderr_tail: str | None,
    ) -> Job:
        limit = None
        if state == "limited":
            # reset_at stays None here: parsing it, and the backoff that uses it,
            # are U5's (§6). What this unit stores is the raw notice.
            limit = {
                "category": parsed.limit_category,
                "message": parsed.limit_message,
                "reset_at": None,
            }
        updates: dict[str, Any] = {
            "exit_code": exit_code,
            "result": parsed.result,
            "verdict": extract_verdict(parsed.result),
            "stderr_tail": stderr_tail,
            "permission_denials": parsed.permission_denials,
            "num_turns": parsed.num_turns,
            "duration_ms": parsed.duration_ms,
            "total_cost_usd": parsed.total_cost_usd,
            "limit": limit,
        }
        updates["head_at_end"] = await _git_head(role.cwd)
        finished = self.spool.transition(job, state, **updates)
        self.spool.append_event(f"job.{state}", _event_payload(finished))
        return finished


def _final_state(parsed: _Parsed, exit_code: int | None, *, cancelled: bool) -> str:
    if cancelled:
        return "killed"  # a human asked; nothing the process said changes that
    if parsed.limit_category is not None:
        return "limited"
    if exit_code == 0 and parsed.saw_result and not parsed.is_error:
        return "done"
    return "failed"


def _signal(proc: asyncio.subprocess.Process, signum: int) -> None:
    try:
        proc.send_signal(signum)
    except ProcessLookupError:  # it finished between the check and the signal
        pass


async def _wait(proc: asyncio.subprocess.Process) -> int:
    return await proc.wait()


async def _git_head(cwd: Path) -> str | None:
    """`git rev-parse HEAD` in `cwd`, or None. §5: always `--no-optional-locks`."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "git",
            "--no-optional-locks",
            "rev-parse",
            "HEAD",
            cwd=str(cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
    except OSError:
        return None
    out, _ = await proc.communicate()
    if proc.returncode != 0:
        return None
    return out.decode("utf-8", errors="replace").strip() or None
