"""The monitor — one watch per builder job, reporting only (DESIGN §1 inv. 4, §5, §11).

§5 gives hands two monitors and one contract:

* the **ops script** (`ops.repo/ops.monitor_cmd`), run as
  `<script> --pids <pids> --transcript <path> --base <head_at_start>`, whose
  blank-line-separated stdout blocks are filed to the inbox **verbatim**;
* the **built-in** liveness/stall detector, used when no script is configured:
  transcript mtime, `subagents/` mtime and process CPU ticks for liveness, new
  commits, `.git/index` mtime and the stash list for progress; no progress and
  no liveness for `monitor.stall_minutes` is one `monitor.stall` event, which
  re-fires only after another interval.

Invariant 4 of §1 is the whole of this module's authority: **it reports, it
never intervenes**. Nothing here signals the job, cancels it, or sends a
prompt; a monitor that raises is logged and dropped, and the job runs on.
Tripwires are external-only in this mission — the built-in monitor never emits
`monitor.tripwire`, because the rules live in the ops repo.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import re
import signal
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hands.config import Config
from hands.spool import Job, Spool

__all__ = [
    "DEFAULT_POLL_S",
    "WATCHED_ROLES",
    "BlockBuffer",
    "MonitorSupervisor",
    "block_kind",
    "cpu_ticks",
    "descendants_of",
    "pid_list",
]

log = logging.getLogger("hands.monitor")

#: §5 says "hands starts those with every builder job"; aux is not watched.
WATCHED_ROLES = frozenset({"builder"})

DEFAULT_POLL_S = 5.0  # how often the built-in monitor samples; a test shortens it
MIN_POLL_S = 0.01
STOP_GRACE_S = 5.0  # SIGTERM → this long → SIGKILL, and the same to drain stdout
MAX_PIDS = 256  # a deep sub-agent tree must not build an unbounded command line
STDERR_TAIL_LINES = 20
READ_LIMIT = 1024 * 1024  # one block line of an ops script, generously

#: The kinds §5 names. Anything else the script says is `monitor.event`.
KNOWN_KINDS = ("stall", "tripwire")
_FIRST_WORD = re.compile(r"[A-Za-z]+")


# ------------------------------------------------------------ block parsing


def block_kind(block: str) -> str:
    """`stall`, `tripwire`, or `event` — the block's first word, lower-cased (§5).

    "Word" is the leading run of letters, so `STALL`, `Stall:` and `stall` all
    read as `stall` while `stalled` does not: the kind is a vocabulary, and a
    block hands does not recognise is reported, never dropped.
    """
    match = _FIRST_WORD.match(block.lstrip())
    word = match.group(0).lower() if match else ""
    return word if word in KNOWN_KINDS else "event"


class BlockBuffer:
    """Line-at-a-time splitter for an event stream of blank-line-separated blocks.

    `feed` returns the blocks that the line completed (never more than one), so
    a reader can file each block the moment it arrives rather than buffering the
    script's output to exit. Block text is kept exactly as written apart from
    the line terminators that delimit it.
    """

    def __init__(self) -> None:
        self._lines: list[str] = []

    def feed(self, line: str) -> list[str]:
        if line.strip():
            self._lines.append(line)
            return []
        return self.flush()

    def flush(self) -> list[str]:
        lines, self._lines = self._lines, []
        block = "\n".join(lines)
        return [block] if block.strip() else []


# ----------------------------------------------------------- process facts


def _read(path: str | Path) -> str | None:
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:  # pragma: no cover - exists, owned by someone else
        return True
    except OSError:  # pragma: no cover - defensive
        return False
    return True


def descendants_of(pid: int) -> list[int]:
    """`pid` and every descendant of it, from `/proc` alone (§5's `--pids`).

    The children of a process are `/proc/<pid>/task/<tid>/children`, which the
    kernel gives for free; nothing else is read and no new dependency is taken.
    Where that file is unavailable the answer degrades to `[pid]`, never to an
    error.
    """
    root = Path(f"/proc/{pid}")
    if not root.exists():
        return [pid] if _alive(pid) else []
    found: list[int] = []
    seen: set[int] = set()
    queue = [pid]
    while queue and len(found) < MAX_PIDS:
        current = queue.pop(0)
        if current in seen:
            continue
        seen.add(current)
        task_dir = Path(f"/proc/{current}/task")
        if not task_dir.exists():
            continue  # it died between being named and being read
        found.append(current)
        try:
            threads = sorted(task_dir.iterdir())
        except OSError:  # pragma: no cover - it died mid-walk
            continue
        for thread in threads:
            for word in (_read(thread / "children") or "").split():
                with contextlib.suppress(ValueError):
                    queue.append(int(word))
    return found


def pid_list(job: Job) -> list[int]:
    """The pids to watch: the claude process and its descendants, live ones only."""
    if job.pid is None:
        return []
    return descendants_of(job.pid)


def cpu_ticks(pids: list[int]) -> int | None:
    """utime+stime (fields 14, 15 of `/proc/<pid>/stat`) summed over `pids`.

    None when no pid could be read at all — a dead process is not liveness, so
    it must not look like a reading of zero.
    """
    total = 0
    seen = False
    for pid in pids:
        text = _read(f"/proc/{pid}/stat")
        if not text:
            continue
        # The comm field is parenthesised and may contain spaces; everything
        # after the last ')' is field 3 onwards, so utime/stime are [11] and [12].
        try:
            fields = text[text.rindex(")") + 1 :].split()
            total += int(fields[11]) + int(fields[12])
        except (ValueError, IndexError):  # pragma: no cover - a torn read
            continue
        seen = True
    return total if seen else None


def _mtime(path: str | Path | None) -> float | None:
    if not path:
        return None
    try:
        return os.stat(path).st_mtime
    except OSError:
        return None


async def _git(cwd: Path, *args: str) -> str | None:
    """`git --no-optional-locks <args>` in `cwd`, or None (§5). Never raises."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "git",
            "--no-optional-locks",
            *args,
            cwd=str(cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
    except OSError:
        return None
    out, _ = await proc.communicate()
    if proc.returncode != 0:
        return None
    return out.decode("utf-8", errors="replace").strip()


# ----------------------------------------------------------------- plumbing


async def _sleep_or_stop(stop: asyncio.Event, timeout: float) -> None:
    with contextlib.suppress(TimeoutError):
        await asyncio.wait_for(stop.wait(), timeout)


def _signal_group(proc: asyncio.subprocess.Process, signum: int) -> None:
    """Signal the script's whole process group; it is a script, it has children."""
    try:
        os.killpg(os.getpgid(proc.pid), signum)
    except OSError:
        with contextlib.suppress(ProcessLookupError):
            proc.send_signal(signum)


async def _terminate(proc: asyncio.subprocess.Process, grace: float) -> None:
    if proc.returncode is not None:
        return
    _signal_group(proc, signal.SIGTERM)
    try:
        await asyncio.wait_for(asyncio.shield(_wait(proc)), grace)
    except TimeoutError:
        _signal_group(proc, signal.SIGKILL)


async def _wait(proc: asyncio.subprocess.Process) -> int:
    return await proc.wait()


async def _tail(stream: asyncio.StreamReader | None, sink: list[str]) -> None:
    if stream is None:  # pragma: no cover - PIPE is always requested
        return
    async for raw in stream:
        sink.append(raw.decode("utf-8", errors="replace").rstrip("\n"))
        del sink[:-STDERR_TAIL_LINES]


@dataclass
class _Watch:
    job_id: str
    stop: asyncio.Event
    task: asyncio.Task[None]


# --------------------------------------------------------------- supervisor


class MonitorSupervisor:
    """One watch per running builder job (§5). The daemon owns one of these.

    `start(job)` is fire-and-forget; `stop(job_id)` ends the watch and is what
    "the monitor stops when the job ends" means. Which monitor runs is the
    config's choice and never a fallback: with `ops.monitor_cmd` set, a script
    that cannot be run is reported as one `monitor.event` and that job goes
    unwatched — silently substituting the weaker built-in monitor would leave
    the human believing their tripwires are armed.
    """

    def __init__(
        self,
        config: Config,
        spool: Spool,
        *,
        ready: Callable[[str], Awaitable[Any]] | None = None,
        on_event: Callable[[str, dict[str, Any]], None] | None = None,
        poll_s: float = DEFAULT_POLL_S,
        clock: Callable[[], float] = time.monotonic,
        stop_grace_s: float = STOP_GRACE_S,
    ) -> None:
        self.config = config
        self.spool = spool
        #: Awaited before a watch begins: the daemon passes `runner.wait_for_session`,
        #: so `--transcript` and the pid list are real by the time they are read.
        self.ready = ready
        #: Called with (event kind, payload) after each block is filed. The daemon
        #: passes the playbook engine's dispatch: §10 lists `monitor.stall` and
        #: `monitor.tripwire` among its events. Nothing here waits for it.
        self.on_event = on_event
        self.poll_s = poll_s
        self.clock = clock
        self.stop_grace_s = stop_grace_s
        self._watches: dict[str, _Watch] = {}

    @property
    def source(self) -> str:
        return "ops" if self.config.ops.monitor_path is not None else "builtin"

    def status(self) -> dict[str, Any]:
        """§4's "monitor state", for `hands status`."""
        path = self.config.ops.monitor_path
        return {
            "source": self.source,
            "cmd": str(path) if path is not None else None,
            "stall_minutes": self.config.monitor.stall_minutes,
            "watching": sorted(self._watches),
        }

    # ------------------------------------------------------------ lifecycle

    def start(self, job: Job) -> asyncio.Task[None] | None:
        """Begin watching a running builder job. None when it is not watched (§5)."""
        if job.role not in WATCHED_ROLES or job.id in self._watches:
            return None
        stop = asyncio.Event()
        task = asyncio.create_task(self._watch(job.id, stop), name=f"hands-monitor-{job.id}")
        self._watches[job.id] = _Watch(job_id=job.id, stop=stop, task=task)
        return task

    async def stop(self, job_id: str) -> None:
        """End the watch for a job and wait for it to have let go of its process."""
        watch = self._watches.pop(job_id, None)
        if watch is None:
            return
        watch.stop.set()
        try:
            await asyncio.wait_for(asyncio.shield(watch.task), self.stop_grace_s * 2 + 5.0)
        except TimeoutError:  # pragma: no cover - a wedged monitor, never the job's problem
            watch.task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await watch.task

    async def stop_all(self) -> None:
        for job_id in list(self._watches):
            await self.stop(job_id)

    async def _watch(self, job_id: str, stop: asyncio.Event) -> None:
        try:
            if not await self._ready(job_id, stop):
                return
            job = self.spool.load_job(job_id)
            if self.config.ops.monitor_path is not None:
                await self._external(job, stop)
            else:
                await self._builtin(job, stop)
        except asyncio.CancelledError:
            raise
        except Exception:  # §1 inv. 4: a monitor bug reports nothing and breaks nothing
            log.exception("job %s: the monitor failed; the job is untouched", job_id)
        finally:
            self._watches.pop(job_id, None)

    async def _ready(self, job_id: str, stop: asyncio.Event) -> bool:
        """Wait for the job to be watchable. False when the watch was stopped first."""
        if self.ready is None:
            return not stop.is_set()
        ready = asyncio.create_task(self.ready(job_id))
        stopper = asyncio.create_task(stop.wait())
        try:
            await asyncio.wait({ready, stopper}, return_when=asyncio.FIRST_COMPLETED)
        finally:
            stopper.cancel()
            if not ready.done():
                ready.cancel()
        with contextlib.suppress(TimeoutError, asyncio.CancelledError):
            await ready  # a job that never booted is simply not watched
        return not stop.is_set()

    # ----------------------------------------------------------- the inbox

    def _file(
        self, job: Job, block: str, *, source: str, kind: str | None = None, **extra: Any
    ) -> None:
        """One inbox event per block (§11), the block verbatim in `block`."""
        kind = block_kind(block) if kind is None else kind
        payload = {"job": job.id, "role": job.role, "source": source, "block": block, **extra}
        self.spool.append_event(f"monitor.{kind}", payload)
        log.info("job %s: monitor.%s", job.id, kind)
        if self.on_event is not None:
            self.on_event(f"monitor.{kind}", payload)

    # ------------------------------------------------------- the ops script

    async def _external(self, job: Job, stop: asyncio.Event) -> None:
        path = self.config.ops.monitor_path
        if path is None:  # pragma: no cover - only reached when it is configured
            return
        problem = _script_problem(path)
        if problem is not None:
            log.error("job %s: %s", job.id, problem)
            self._file(job, f"event: {problem}", source="ops", kind="event")
            return

        pids = pid_list(job)
        argv = [
            str(path),
            "--pids",
            ",".join(str(pid) for pid in pids),
            "--transcript",
            job.transcript_path or "",
            "--base",
            job.head_at_start or "",
        ]
        try:
            proc = await asyncio.create_subprocess_exec(
                *argv,
                cwd=str(self.config.ops.repo),
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                limit=READ_LIMIT,
                start_new_session=True,  # so the whole script, children included, can be killed
            )
        except OSError as exc:
            message = f"event: cannot run the monitor {path}: {exc}"
            log.error("job %s: %s", job.id, message)
            self._file(job, message, source="ops", kind="event")
            return

        errors: list[str] = []
        reader = asyncio.create_task(self._read_blocks(proc.stdout, job))
        stderr = asyncio.create_task(_tail(proc.stderr, errors))
        waiter = asyncio.create_task(_wait(proc))
        stopper = asyncio.create_task(stop.wait())
        try:
            await asyncio.wait({waiter, stopper}, return_when=asyncio.FIRST_COMPLETED)
        finally:
            stopper.cancel()

        killed = stop.is_set() and proc.returncode is None
        await _terminate(proc, self.stop_grace_s)
        code = await waiter
        # Drain: whatever it wrote before it died is still an event (§5, verbatim).
        for task in (reader, stderr):
            try:
                await asyncio.wait_for(asyncio.shield(task), self.stop_grace_s)
            except TimeoutError:  # pragma: no cover - a pipe held open by a grandchild
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await task

        if not killed and code != 0:
            # Silence from a dead monitor would read as "nothing is wrong" (§11).
            block = (
                f"event: the monitor {path.name} exited with code {code} "
                f"while job {job.id} was still running"
            )
            if errors:
                block += "\n" + "\n".join(errors)
            log.warning("job %s: %s", job.id, block)
            self._file(job, block, source="ops", kind="event")

    async def _read_blocks(self, stream: asyncio.StreamReader | None, job: Job) -> None:
        if stream is None:  # pragma: no cover - PIPE is always requested
            return
        buffer = BlockBuffer()
        async for raw in stream:
            line = raw.decode("utf-8", errors="replace").rstrip("\n").rstrip("\r")
            for block in buffer.feed(line):
                self._file(job, block, source="ops")
        for block in buffer.flush():  # a last block with no blank line after it
            self._file(job, block, source="ops")

    # -------------------------------------------------- the built-in monitor

    async def _builtin(self, job: Job, stop: asyncio.Event) -> None:
        interval = self.config.monitor.stall_minutes * 60.0
        if interval <= 0:
            # The simplest reading of `stall_minutes = 0`: stall detection off.
            log.info("job %s: monitor.stall_minutes is 0; no stall detection", job.id)
            return
        poll = max(min(self.poll_s, interval / 4.0), MIN_POLL_S)
        marker = await self._sample(job)
        since = self.clock()
        while not stop.is_set():
            await _sleep_or_stop(stop, poll)
            if stop.is_set():
                return
            current = await self._sample(job)
            now = self.clock()
            if current != marker:
                marker, since = current, now
                continue
            if now - since >= interval:
                self._stall(job, now - since, interval)
                since = now  # §5: it re-fires only after another interval

    async def _sample(self, job: Job) -> tuple[Any, ...]:
        """Liveness and progress in one reading; any change at all is movement (§5).

        Missing inputs read as None and stay None, which is what makes them not
        liveness: a job with no transcript, no `subagents/` and a dead pid has a
        constant sample and therefore stalls.
        """
        try:
            cwd = self.config.role(job.role).cwd
        except KeyError:  # pragma: no cover - the role was reconfigured mid-job
            return ()
        transcript = Path(job.transcript_path) if job.transcript_path else None
        # §5: the index is stat'd *before* any git command, or git's own writes
        # to it would look like progress.
        index_mtime = _mtime(cwd / ".git" / "index")
        return (
            _mtime(transcript),
            _mtime(transcript.parent / "subagents") if transcript is not None else None,
            cpu_ticks(pid_list(job)),
            index_mtime,
            await _git(cwd, "rev-parse", "HEAD"),
            await _git(cwd, "stash", "list"),
        )

    def _stall(self, job: Job, idle_s: float, interval_s: float) -> None:
        pids = pid_list(job)
        block = (
            f"STALL {job.id} ({job.role}) no progress and no liveness for "
            f"{idle_s / 60.0:.2f} minute(s) "
            f"(monitor.stall_minutes = {interval_s / 60.0:g})\n"
            f"pids: {','.join(str(pid) for pid in pids) or 'none'}\n"
            f"transcript: {job.transcript_path or 'unknown'}\n"
            f"base: {job.head_at_start or 'unknown'}"
        )
        self._file(
            job,
            block,
            source="builtin",
            kind="stall",
            idle_seconds=round(idle_s, 3),
            stall_minutes=interval_s / 60.0,
        )


def _script_problem(path: Path) -> str | None:
    """Why `ops.monitor_cmd` cannot be run, in words a human can act on."""
    where = "ops.repo + ops.monitor_cmd (§13)"
    if not path.exists():
        return f"the monitor script {path} does not exist; check {where}. This job is unwatched."
    if not path.is_file():
        return f"the monitor script {path} is not a file; check {where}. This job is unwatched."
    if not os.access(path, os.X_OK):
        return f"the monitor script {path} is not executable; chmod +x it. This job is unwatched."
    return None
