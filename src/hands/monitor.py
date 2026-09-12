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

Beside whichever of those decides, every role job's stream-json (builder and
aux alike) is read for the harness's task-killed notice (§24): the runner hands
each parsed event to `MonitorSupervisor.observe`, and a killed task is one
`monitor.task_killed` event carrying the task's command line, once per task.

At job end the runner hands over what was still alive in the job's scope or
process group once claude had exited (§24): `MonitorSupervisor.orphan_processes`
files it as one `monitor.orphan_processes` event with each process's command
line. The readers of that pid set (`group_pids`, `cgroup_path`, `cgroup_pids`,
`cmdline`) live here with the other `/proc` readers; the kill that follows is
the runner's, because the runner owns the process it spawned.

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
from collections import OrderedDict
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hands.config import Config
from hands.spool import Job, Spool

__all__ = [
    "DEFAULT_POLL_S",
    "MAX_CMDLINE",
    "OPS_FLAGS",
    "ops_argv",
    "TASK_MEMORY",
    "WATCHED_ROLES",
    "BlockBuffer",
    "KilledTask",
    "MonitorSupervisor",
    "TaskKillWatch",
    "block_kind",
    "cgroup_path",
    "cgroup_pids",
    "cmdline",
    "cpu_ticks",
    "descendants_of",
    "group_pids",
    "pid_list",
]

log = logging.getLogger("hands.monitor")

#: §5 says "hands starts those with every builder job"; aux is not watched for
#: stalls. The task-killed notice (§24) is read from every role's stream.
WATCHED_ROLES = frozenset({"builder"})

#: The whole of what §5 hands the ops script, in the order `_external` passes it.
#: `hands status` names these when the ops script is the monitor that decides, so
#: the list lives where the invocation is built and is never spelled out again.
OPS_FLAGS = ("--pids", "--transcript", "--base")


def ops_argv(path: Path, values: Sequence[str]) -> list[str]:
    """The ops script's command line: `path`, then each of `OPS_FLAGS` with its value.

    The one place that argv is built. The monitor fills `values` from the job
    record (§5); `hands doctor` fills them with a dead pid and calls the same
    function, so what doctor probes is what the monitor sends (review 3
    should-fix 3). `OPS_FLAGS` is read at call time, not bound here.
    """
    argv = [str(path)]
    for flag, value in zip(OPS_FLAGS, values, strict=True):
        argv += [flag, value]
    return argv

DEFAULT_POLL_S = 5.0  # how often the built-in monitor samples; a test shortens it
MIN_POLL_S = 0.01
STOP_GRACE_S = 5.0  # SIGTERM → this long → SIGKILL, and the same to drain stdout
MAX_PIDS = 256  # a deep sub-agent tree must not build an unbounded command line
STDERR_TAIL_LINES = 20
PROC_ROOT = Path("/proc")
CGROUP_ROOT = Path("/sys/fs/cgroup")  # the unified (v2) hierarchy
#: Characters of one orphan's command line kept in its event (§24). Arguments
#: can be whole scripts; past this the line ends in `…`.
MAX_CMDLINE = 1024
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


# ------------------------------------------------- the task-killed notice


#: How many Bash commands, started tasks and killed task ids one job's
#: `TaskKillWatch` remembers. §21 forbids the daemon growing with a transcript,
#: so past this the oldest entry is forgotten: a kill whose Bash call is that far
#: back names no command, and a notice repeated after that many later kills
#: would be filed again.
TASK_MEMORY = 1024


@dataclass(frozen=True)
class KilledTask:
    """One task the stream says was killed, with what is known about it."""

    task_id: str
    task_type: str | None  # `local_bash`, `local_agent`, … from `task_started`
    tool_use_id: str | None
    command: str | None  # the `Bash` tool_use's `input.command`, when it was seen
    description: str | None  # `task_started`'s description, else the notice's summary


def _text(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _remember(store: OrderedDict[str, Any], key: str, value: Any) -> None:
    store[key] = value
    store.move_to_end(key)
    while len(store) > TASK_MEMORY:
        store.popitem(last=False)


class TaskKillWatch:
    """The harness's task-killed notice in one job's stream-json (§5, §24).

    The shape is the recorded one quoted in `tests/fixtures/task_killed.stream.jsonl`
    (claude 2.1.269 and 2.1.270): a killed task is `system`/`task_updated` with
    `patch.status == "killed"`, then `system`/`task_notification` with
    `status == "stopped"` (the binary maps killed to stopped on that event).
    Either one is the notice, and `feed` returns a `KilledTask` for the first of
    them and None for everything else, so a task is reported once however often
    the notice repeats. The command line is not in the notice: it is recovered
    from the `Bash` tool_use whose id is the task's `tool_use_id`.
    """

    def __init__(self) -> None:
        self._commands: OrderedDict[str, str] = OrderedDict()  # tool_use id → command
        self._tasks: OrderedDict[str, dict[str, str | None]] = OrderedDict()
        self._killed: OrderedDict[str, None] = OrderedDict()

    def feed(self, event: dict[str, Any]) -> KilledTask | None:
        kind = event.get("type")
        if kind == "assistant":
            self._note_commands(event)
            return None
        if kind != "system":
            return None
        task_id = _text(event.get("task_id"))
        if task_id is None:
            return None
        subtype = event.get("subtype")
        if subtype == "task_started":
            _remember(
                self._tasks,
                task_id,
                {
                    "tool_use_id": _text(event.get("tool_use_id")),
                    "task_type": _text(event.get("task_type")),
                    "description": _text(event.get("description")),
                },
            )
            return None
        if subtype == "task_updated":
            patch = event.get("patch")
            if isinstance(patch, dict) and patch.get("status") == "killed":
                return self._kill(task_id, None, None)
            return None
        if subtype == "task_notification" and event.get("status") == "stopped":
            return self._kill(task_id, _text(event.get("tool_use_id")), _text(event.get("summary")))
        return None

    def _note_commands(self, event: dict[str, Any]) -> None:
        message = event.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, list):
            return
        for item in content:
            if not isinstance(item, dict) or item.get("type") != "tool_use":
                continue
            if item.get("name") != "Bash" or not isinstance(item.get("input"), dict):
                continue
            tool_use_id = _text(item.get("id"))
            command = item["input"].get("command")
            if tool_use_id is not None and isinstance(command, str):
                _remember(self._commands, tool_use_id, command)

    def _kill(
        self, task_id: str, tool_use_id: str | None, summary: str | None
    ) -> KilledTask | None:
        if task_id in self._killed:
            return None
        _remember(self._killed, task_id, None)
        started = self._tasks.get(task_id, {})
        tool_use_id = started.get("tool_use_id") or tool_use_id
        return KilledTask(
            task_id=task_id,
            task_type=started.get("task_type"),
            tool_use_id=tool_use_id,
            command=self._commands.get(tool_use_id) if tool_use_id else None,
            description=started.get("description") or summary,
        )


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


def cgroup_path(text: str) -> str | None:
    """The unified-hierarchy path in `/proc/<pid>/cgroup` text: its `0::` line.

    A transient scope's path ends in `/<unit>.scope`. None when there is no `0::`
    line (a cgroup v1-only machine), which is one reason there is no scope.
    """
    for line in text.splitlines():
        if line.startswith("0::"):
            return line[3:].strip() or None
    return None


def cgroup_pids(path: str, *, root: Path = CGROUP_ROOT) -> list[int]:
    """The pids in a cgroup's `cgroup.procs`: a scope's live pid set (§24).

    Empty when the cgroup is gone, which is what a scope whose last process
    exited is. Membership survives double forks and setsid.
    """
    pids: list[int] = []
    for word in (_read(root / path.lstrip("/") / "cgroup.procs") or "").split():
        with contextlib.suppress(ValueError):
            pids.append(int(word))
    return pids


def group_pids(pgid: int, *, proc_root: Path = PROC_ROOT) -> list[int]:
    """Every live process whose process group is `pgid`, from `/proc/*/stat` (§24).

    The process-group fallback's live pid set. A zombie has exited and is left
    out. A process that called setsid (or setpgid) has left the group and is not
    here: that is why this fallback is weaker than a scope.
    """
    try:
        entries = [entry for entry in proc_root.iterdir() if entry.name.isdigit()]
    except OSError:  # pragma: no cover - no /proc
        return []
    found: list[int] = []
    for entry in entries:
        text = _read(entry / "stat")
        if not text or ")" not in text:
            continue  # it died between the listing and the read
        # Fields after the parenthesised comm: state, ppid, pgrp, ...
        fields = text[text.rindex(")") + 1 :].split()
        if len(fields) < 3 or fields[0] in ("Z", "X") or fields[2] != str(pgid):
            continue
        found.append(int(entry.name))
    return sorted(found)


def cmdline(pid: int, *, proc_root: Path = PROC_ROOT) -> str:
    """`/proc/<pid>/cmdline` with NULs as spaces, capped at `MAX_CMDLINE` (§24).

    Empty when it cannot be read (the process is gone, or is a kernel thread).
    """
    try:
        raw = (proc_root / str(pid) / "cmdline").read_bytes()
    except OSError:
        return ""
    text = raw.rstrip(b"\0").replace(b"\0", b" ").decode("utf-8", errors="replace")
    if len(text) > MAX_CMDLINE:
        text = text[: MAX_CMDLINE - 1] + "…"
    return text


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
        pids: Callable[[Job], list[int]] = pid_list,
    ) -> None:
        self.config = config
        #: The live pid set of a job, which is what `--pids` carries (§5, §24). The
        #: daemon passes `runner.live_pids`: the job's scope or process group.
        self.pids = pids
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
        #: job id → the task-killed reader of its stream (§24), for every role.
        #: Created by the first event `observe` sees and dropped by `stop`.
        self._kill_watches: dict[str, TaskKillWatch] = {}

    @property
    def source(self) -> str:
        return "ops" if self.config.ops.monitor_path is not None else "builtin"

    def status(self) -> dict[str, Any]:
        """§4's "monitor state", for `hands status`.

        Both monitors are described, because only one of them decides: `flags` is
        what the ops script is given (and is None for the built-in monitor, which
        is given nothing), and `stall_minutes` is the built-in rule's interval,
        which never reaches the ops script (§5, §19).
        """
        path = self.config.ops.monitor_path
        ops = self.source == "ops"
        return {
            "source": self.source,
            "cmd": str(path) if path is not None else None,
            "flags": list(OPS_FLAGS) if ops else None,
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
        self._kill_watches.pop(job_id, None)
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

    # ------------------------------------------------ the stream (§5, §24)

    def observe(self, job: Job, event: dict[str, Any]) -> None:
        """One parsed stream-json event of a running job, of any role (§24).

        The runner calls this for every event as it reads it. A killed task is
        filed as `monitor.task_killed`, once per task per job; nothing else is
        done with the event, and a failure here is logged, never raised into the
        run (§1 invariant 4).
        """
        try:
            watch = self._kill_watches.get(job.id)
            if watch is None:
                watch = self._kill_watches[job.id] = TaskKillWatch()
            kill = watch.feed(event)
            if kill is not None:
                self._task_killed(job, kill)
        except Exception:
            log.exception("job %s: the task-killed reader failed; the job is untouched", job.id)

    def _task_killed(self, job: Job, kill: KilledTask) -> None:
        block = (
            f"TASK_KILLED {job.id} ({job.role}) task {kill.task_id} "
            f"({kill.task_type or 'type unknown'}) was killed\n"
            f"command: {kill.command if kill.command is not None else 'unknown'}\n"
            f"description: {kill.description or 'none'}"
        )
        self._file(
            job,
            block,
            source="stream",
            kind="task_killed",
            task_id=kill.task_id,
            task_type=kill.task_type,
            tool_use_id=kill.tool_use_id,
            command=kill.command,
            description=kill.description,
        )

    # ---------------------------------------------------- job end (§24)

    def orphan_processes(
        self, job: Job, processes: list[dict[str, Any]], isolation: str
    ) -> None:
        """What was still alive in a job's scope or group after claude exited (§24).

        The runner calls this once per job, only with a non-empty list, and kills
        the processes after it returns. One event, every process's pid and
        command line in it.
        """
        where = "scope" if isolation == "scope" else "process group"
        lines = [
            f"ORPHAN_PROCESSES {job.id} ({job.role}) {len(processes)} process(es) "
            f"still in the job's {where} after claude exited; they are killed now"
        ]
        lines += [f"{proc['pid']} {proc['cmdline'] or '(no command line)'}" for proc in processes]
        self._file(
            job,
            "\n".join(lines),
            source="job_end",
            kind="orphan_processes",
            isolation=isolation,
            processes=processes,
        )

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

        pids = self.pids(job)
        values = (
            ",".join(str(pid) for pid in pids),
            job.transcript_path or "",
            job.head_at_start or "",
        )
        argv = ops_argv(path, values)
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
            cpu_ticks(self.pids(job)),
            index_mtime,
            await _git(cwd, "rev-parse", "HEAD"),
            await _git(cwd, "stash", "list"),
        )

    def _stall(self, job: Job, idle_s: float, interval_s: float) -> None:
        pids = self.pids(job)
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
