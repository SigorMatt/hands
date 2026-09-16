"""The runner — one `claude -p` process per job (DESIGN §2, §6).

This module owns exactly one job at a time: spawn it, parse its stream-json,
write that stream to the job's log file as it arrives (§7, §21 — it is never
collected in memory), fill the record of §6, move it to a terminal state, and
cancel it on request.
Queueing, the one-running-job-per-role rule and everything else about *which*
job runs next belong to the daemon (§3), which drives this as a library.

The invocation is §2, verbatim:

    cd <role.cwd>
    claude -p [--resume <id>] --output-format stream-json --verbose \\
      --model <role.model> <role.permission_flags> --permission-prompts none

All six flags were checked against the installed binary (claude 2.1.268,
`claude --help`) before this was written; each exists with that spelling, and
`--permission-prompts` does take `none`.

The process runs in handsd's environment plus the role's `spawn_env` (§23):
`CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0` unless `[roles.<r>] env` sets it; and
`HANDS_JOB=<job id>`, which the post-exit sweep reads as corroboration only (§29).

Each process is isolated per job (§24). When `systemd-run --user --scope` can
start a scope here, the invocation runs inside a transient user scope named
`hands-<project>-<job>`; otherwise it starts in a new process group
(`start_new_session`). Which one is probed once per `Runner`, at its first job
(`detect_isolation`). The job's live pid set is the scope's `cgroup.procs` or the
group's members (`live_pids`, the monitor's `--pids`). Once claude has exited,
whatever is still in that set is handed to `on_orphans` (the daemon files
`monitor.orphan_processes`) and then killed: the scope is stopped; in group mode
each process proven the job's is sent SIGTERM and, after `ORPHAN_GRACE_S`,
SIGKILL. Group mode's proof is §29's session proof (`_job_processes`): a live
process descends from the job when its session id is the job's pid and it started
before the last moment the job's pid was observed held by claude (`_last_seen`,
refreshed on every poll of `_until_exit`). `HANDS_JOB` never proves anything and
is not needed (§30); what the proof misses and is still the job's (a fork inside
claude's last poll interval, marked or not, or a marked process that called
setsid) is reported `killed: false` and left alive, and job end reads the pipes
it may hold for at most `runner.pipe_timeout_s`.

A job is `done` only when the process ends cleanly with a final `result` event
of subtype `success` that carries `num_turns`, and stderr never carried the
harness's termination line (§2, §6, §23; H-014). A cancel stays `killed` and a
limit stays `limited`; anything else is `failed`, and `failure_reason` names
which — see `FAILURE_REASONS`.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import re
import shutil
import signal
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TextIO

from hands.config import (
    ARCHITECT_ROLE,
    CLONE_ENV,
    CONSULT_ROLE_ENV,
    DRIVER_ROLE,
    KITS_ENV,
    Config,
    RoleConfig,
    driver_clone,
)
from hands.limits import is_limit_notice, parse_reset_at, to_iso
from hands.monitor import (
    CGROUP_ROOT,
    MAX_PIDS,
    cgroup_path,
    cgroup_pids,
    cmdline,
    descendants_of,
    environ_has,
    group_pids,
    proc_stats,
    start_time,
)
from hands.playbook import consult_head
from hands.spool import TERMINAL_STATES, Job, Spool, SpoolError

__all__ = [
    "FAILURE_REASONS",
    "GROUP",
    "JOB_ENV",
    "LINE_LIMIT",
    "MAX_PROMPT_BYTES",
    "SCOPE",
    "KeepRefused",
    "Runner",
    "RunnerError",
    "build_argv",
    "detect_isolation",
    "extract_verdict",
    "is_harness_termination",
    "probe_isolation",
    "project_dir_name",
    "reconcile_orphans",
    "spawn_argv",
    "transcript_path_for",
    "unit_name",
]


log = logging.getLogger("hands.runner")


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

# §4's "the daemon's line room": the daemon reads one JSON-RPC request per line
# and gives that reader the cap plus a quarter (`daemon.py`). The number lives
# here, beside the cap it is derived from, because both ends need it — the
# daemon to size its reader, and the client to measure the whole request it is
# about to write before it connects (§4's `send` row, H-012).
LINE_LIMIT = MAX_PROMPT_BYTES + MAX_PROMPT_BYTES // 4

# One stream-json line can be large (a whole result). asyncio's default 64 KiB
# reader limit would raise on it, so the reader is given room for the cap.
_STREAM_LIMIT = MAX_PROMPT_BYTES + 1024 * 1024

_STDERR_TAIL_LINES = 50  # §6: "stderr_tail  # last 50 lines"

# How many spawned command lines `last_argv` keeps (§21, review 5 should-fix 3).
# It is a debugging aid — nothing in hands reads it back — so it is the one
# structure here that is not emptied when a run ends; a cap is what keeps it
# from growing with the number of jobs the daemon has ever run.
MAX_LAST_ARGV = 8

_VERDICT_RE = re.compile(r"^VERDICT:")  # §6: "the first line of result matching ^VERDICT:"

# §6 detects a limit from "the `api_retry` error category `rate_limit` or the
# limit notice in `result`". In claude 2.1.268 the wire event is
# `{"type":"system","subtype":"api_retry", … "error":"rate_limit"}` — the
# category lives in the `error` field, whose schema is an enum that contains
# `rate_limit`; `category` is read too in case a future build renames it.
_RATE_LIMIT = "rate_limit"
# The notice text and the reset time in it are `hands.limits` (U5): the runner
# asks, it does not decide. `_finish` stores whatever the parser makes of the
# notice, and the raw notice either way.

# Claude Code's project directory under ~/.claude/projects is the working
# directory with every non-alphanumeric character replaced by "-" (see the
# evidence in meta/findings/FINDINGS.md H-001).
_NON_ALNUM_RE = re.compile(r"[^a-zA-Z0-9]")

# §6 (H-014, review 7 should-fix 2). claude 2.1.269 and 2.1.270 write, when the
# bg-wait ceiling ends a `-p` run, one string with no newline in it:
#   `Background tasks still running after ${Math.round(A/1000)}s; terminating.`
#   ` Set CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0 to wait indefinitely.`
# (shown in two pieces here for width only; read from the binary; job
# 0mtygi953-ym63's line is that, with 600). Anchored to that exact shape,
# case-sensitive as written: the line starts with it, the count is digits, the
# unit is `s;`, and the `Set CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=` tail is on
# the same line. What follows the `=` is not read.
_TERMINATING_RE = re.compile(
    r"Background tasks still running after [0-9]+s; terminating\. "
    r"Set CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS="
)

# §24's per-job isolation: a transient systemd user scope, or a process group.
SCOPE = "scope"
GROUP = "group"
#: Seconds for `systemd-run`/`systemctl` to answer (the probe, a scope lookup).
PROBE_S = 5.0
#: A stuck `systemctl --user stop` is given this long; systemd finishes the stop
#: on its own schedule (its TimeoutStopSec then SIGKILL) either way.
SCOPE_STOP_S = 30.0
#: SIGTERM → this long → SIGKILL, for what is left in a process group (§24).
ORPHAN_GRACE_S = 2.0
#: The variable every job runs with, set to its id. §29: corroboration and never
#: sufficient alone (any process can set it): the sweep reports a process that
#: carries it but kills only what the session proof shows is the job's (H-023).
JOB_ENV = "HANDS_JOB"
#: Clock ticks per second: the unit of `/proc/<pid>/stat`'s start time (field 22).
CLK_TCK = os.sysconf("SC_CLK_TCK")
#: Once claude has exited, how long its pipes may stay open before the sweep runs
#: anyway: an orphan that inherited stdout would otherwise hold the job open.
DRAIN_S = 1.0
_EXIT_POLL_S = 0.05
# A systemd unit name may hold more than this, but these are all hands needs.
_UNIT_UNSAFE_RE = re.compile(r"[^A-Za-z0-9_-]")
#: The project part of a unit name is cut to this many characters, so a long
#: project name cannot push the name past systemd's 255; the job id is kept whole.
MAX_UNIT_PROJECT = 64

#: Every `failure_reason` the runner writes, in the order it checks them (§23):
#:   harness_terminated  stderr carried the harness's `terminating` line
#:   no_final_result     no `result` event, or its subtype is not success/error_*
#:   error_result        the final result's subtype is `error`/`error_*`, or it
#:                       says `is_error` (§6: the subtype decides, whatever
#:                       `is_error` says)
#:   nonzero_exit        a clean result, but the process exited non-zero
#:   no_num_turns        a clean result with no `num_turns`
#:   spawn_error         the process could not be started at all
#: The first that holds is the one recorded. A cancel (`killed`) and a detected
#: limit (`limited`) are decided before any of these, and their reason is null.
#: Otherwise the terminating line wins even over a `success` result with
#: `num_turns` and exit 0: the harness ended the session mid-turn (DESIGN v3.8 §6).
FAILURE_REASONS: tuple[str, ...] = (
    "harness_terminated",
    "no_final_result",
    "error_result",
    "nonzero_exit",
    "no_num_turns",
    "spawn_error",
)


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


def is_harness_termination(line: str) -> bool:
    """Does this stderr line say the harness terminated the `-p` process? (§6)"""
    return _TERMINATING_RE.match(line) is not None


def _is_final_subtype(subtype: str | None) -> bool:
    """§23's "subtype `success` or `error`": `error` is claude's `error_*` family
    (`error_during_execution`, `error_max_turns`, `error_max_budget_usd`, …)."""
    if not isinstance(subtype, str):
        return False
    return subtype in ("success", "error") or subtype.startswith("error_")


def build_argv(config: Config, role: RoleConfig, *, resume: str | None = None) -> list[str]:
    """The §2 invocation, in the order §2 writes it."""
    argv = [config.runner.claude, "-p"]
    if resume is not None:
        argv += ["--resume", resume]
    argv += ["--output-format", "stream-json", "--verbose", "--model", role.model]
    argv += list(role.permission_argv)
    argv += ["--permission-prompts", "none"]
    return argv


def unit_name(project: str, job_id: str) -> str:
    """`hands-<project>-<job>`, a valid systemd unit name (§24).

    Every character outside `[A-Za-z0-9_-]` becomes `_` (so `.`, `/`, `@`, `:`,
    spaces and non-ASCII are all replaced), and the project part is cut to
    `MAX_UNIT_PROJECT` characters.
    """
    safe_project = _UNIT_UNSAFE_RE.sub("_", project)[:MAX_UNIT_PROJECT]
    return f"hands-{safe_project}-{_UNIT_UNSAFE_RE.sub('_', job_id)}"


def spawn_argv(argv: list[str], *, project: str, job_id: str, isolation: str) -> list[str]:
    """What is actually executed: the §2 invocation, inside a scope when there is one."""
    if isolation != SCOPE:
        return list(argv)
    unit = unit_name(project, job_id)
    return ["systemd-run", "--user", "--scope", "--quiet", "--unit", unit, "--", *argv]


def probe_isolation(
    *,
    which: Callable[[str], str | None] = shutil.which,
    run: Callable[..., subprocess.CompletedProcess[Any]] = subprocess.run,
    cgroup_root: Path = CGROUP_ROOT,
) -> str:
    """`SCOPE` when a transient user scope can be started here, else `GROUP` (§24).

    A scope needs `systemd-run` and `systemctl` on PATH, the unified cgroup
    hierarchy (to read `cgroup.procs`), and a user manager that really starts
    one: `systemd-run --user --scope --quiet -- true` must exit 0 in `PROBE_S`.
    """
    if which("systemd-run") is None or which("systemctl") is None:
        return GROUP
    if not (cgroup_root / "cgroup.controllers").exists():
        return GROUP
    try:
        proc = run(
            ["systemd-run", "--user", "--scope", "--quiet", "--", "true"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=PROBE_S,
        )
    except (OSError, subprocess.SubprocessError):
        return GROUP
    return SCOPE if proc.returncode == 0 else GROUP


def detect_isolation() -> str:
    """The isolation this machine gives a job now. The test suite pins it to `GROUP`."""
    return probe_isolation()


# ------------------------------------------------------------ orphan sweep


def boot_ticks() -> int:
    """Now, in the clock of `/proc/<pid>/stat`'s start time: whole clock ticks since
    boot (`CLOCK_BOOTTIME`, which Linux has used for that field since 5.3), rounded
    down as the kernel rounds a start time (§29)."""
    return time.clock_gettime_ns(time.CLOCK_BOOTTIME) * CLK_TCK // 1_000_000_000


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
    subtype: str | None = None  # of the last `result` event
    harness_terminated: bool = False  # stderr carried the terminating line (§23)
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
        #: job id → the open append handle of its stream log, for the length of
        #: the run and no longer (§21). Every structure on this object is keyed by
        #: job, never by event: the stream-json goes to the file as it arrives and
        #: is not collected anywhere, so a 60-turn transcript costs the daemon the
        #: same resident bytes as a one-turn one. `retained()` states that as a
        #: number a test can assert on.
        self._logs: dict[str, TextIO] = {}
        #: job id → the argv it was spawned with, for a human reading a spawn.
        #: The last `MAX_LAST_ARGV` of them: this is the one structure here that
        #: outlives its job, so it is the one that needs a cap (§21).
        self.last_argv: dict[str, list[str]] = {}
        #: Handed every parsed stream-json event of every run, with its job, as it
        #: is read. The daemon passes the monitor's `observe` (§5, §24: the
        #: task-killed notice). A hook that raises is logged; the run goes on.
        self.on_stream_event: Callable[[Job, dict[str, Any]], None] | None = None
        #: `SCOPE` or `GROUP` (§24). None until the first job probes it; a caller
        #: (or a test) may set it first.
        self.isolation: str | None = None
        #: job id → the isolation its process was started under, for the run only.
        self._isolated: dict[str, str] = {}
        # Job id -> the start time of the process group's leader (claude) read
        # at spawn, None when it could not be read: what ties a group kill to
        # the job's own group and not a later one with the same id (§24).
        self._leader_start: dict[str, int | None] = {}
        # Job id -> `boot_ticks()` when claude was last observed holding its pid
        # (its pid with the start time above), for the run only (§29).
        self._last_seen: dict[str, int] = {}
        #: Handed (job, processes, isolation) once claude has exited, when anything
        #: is still alive in its scope or group; each process is {pid, cmdline}. The
        #: daemon passes the monitor's `orphan_processes` (§24). Killed afterwards.
        self.on_orphans: Callable[[Job, list[dict[str, Any]], str], None] | None = None

    def _remember_argv(self, job_id: str, argv: list[str]) -> None:
        """Keep this argv and drop the oldest beyond `MAX_LAST_ARGV` (§21).

        Review 5 should-fix 3: every other structure on this object is popped
        when the run ends, so it is bounded by the jobs in flight. This one is
        not, and without the cap the daemon held one argv list per job it had
        ever run.
        """
        self.last_argv[job_id] = argv
        while len(self.last_argv) > MAX_LAST_ARGV:
            self.last_argv.pop(next(iter(self.last_argv)))

    def retained(self) -> dict[str, int]:
        """How many items this runner is still holding, by structure (§21).

        §21 forbids the daemon's resident size growing with a job's transcript.
        RSS is a property of the machine and cannot be asserted; the length of
        what is held is a property of the code and can be. Nothing counted here
        is per-event: five of the six counts are emptied when a run ends and so
        are bounded by the jobs in flight, and `last_argv`, which is not emptied,
        is bounded by `MAX_LAST_ARGV` instead. (`isolated` is emptied too.)

        What it does not count, so the number is not read as everything the
        runner holds: the in-flight `_Parsed.result` (one job's final result),
        the stderr tail `run()` keeps as a local (`_STDERR_TAIL_LINES` lines),
        and asyncio's own reader buffer (`_STREAM_LIMIT`). Each is bounded, none
        is per-event, and none of them is on this object to be counted.
        """
        return {
            "cancelled": len(self._cancelled),
            "isolated": len(self._isolated),
            "last_argv": len(self.last_argv),
            "logs": len(self._logs),
            "procs": len(self._procs),
            "running": len(self._running),
            "session_ready": len(self._session_ready),
        }

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

    def live_pids(self, job: Job) -> list[int]:
        """The job's live pid set, which the monitor passes as `--pids` (§5, §24).

        Its scope's `cgroup.procs`, or every live member of its process group.
        For a job this runner is not running, or a scope whose cgroup cannot be
        read yet, it is the process and its descendants, as before §24.
        """
        if job.pid is None:
            return []
        isolation = self._isolated.get(job.id)
        if isolation == GROUP:
            return group_pids(job.pid)[:MAX_PIDS]
        if isolation == SCOPE:
            path = cgroup_path(_read_text(f"/proc/{job.pid}/cgroup"))
            if path and path.endswith(f"/{unit_name(self.config.project, job.id)}.scope"):
                return cgroup_pids(path)[:MAX_PIDS]
        return descendants_of(job.pid)

    async def _isolation(self) -> str:
        if self.isolation is None:
            self.isolation = await asyncio.to_thread(detect_isolation)
        return self.isolation

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
        isolation = await self._isolation()
        spawned = spawn_argv(
            argv, project=self.config.project, job_id=job.id, isolation=isolation
        )
        self._remember_argv(job.id, spawned)

        head_at_start = await _git_head(role.cwd)
        job = self.spool.transition(job, "running", head_at_start=head_at_start)

        try:
            proc = await asyncio.create_subprocess_exec(
                *spawned,
                cwd=str(role.cwd),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                limit=_STREAM_LIMIT,
                # §23, plus the job's id: the mark the post-exit sweep reads to
                # tell the job's descendants from strangers (§27).
                env=job_env(job, role),
                start_new_session=isolation == GROUP,  # §24: its own process group
            )
        except OSError as exc:
            # The one dispatch failure that never produces a process. `failed` is
            # the only terminal state §6 offers for it.
            reason = f"cannot spawn {spawned[0]}: {exc}"
            return await self._finish(
                job, role, "failed", _Parsed(), None, reason, failure_reason="spawn_error"
            )

        self._procs[job.id] = proc
        self._isolated[job.id] = isolation
        job.pid = proc.pid
        if isolation == GROUP:
            self._leader_start[job.id] = start_time(proc.pid)
            self._observe_alive(job)
        self.spool.save_job(job)
        self._running.setdefault(job.id, asyncio.Event()).set()

        parsed = _Parsed()
        stderr_lines: list[str] = []
        self._open_log(job.id)
        swept = False
        try:
            io = asyncio.gather(
                self._write_prompt(proc, job.prompt),
                self._read_stdout(proc, job, role, parsed),
                self._read_stderr(proc, stderr_lines, parsed),
            )
            try:
                await _until_exit(proc, io, lambda: self._observe_alive(job))
                if io.done():
                    await io
                    exit_code = await proc.wait()
                    await self._sweep(job, isolation)
                    swept = True
                else:
                    # claude has exited and something still holds its pipes: an
                    # orphan that inherited them. Sweep first, so they close.
                    await self._sweep(job, isolation)
                    swept = True
                    exit_code = await self._drain(proc, io, job)
            except BaseException:
                io.cancel()
                raise
        finally:
            if not swept:
                self._last_resort(job, isolation)
            self._isolated.pop(job.id, None)
            self._leader_start.pop(job.id, None)
            self._last_seen.pop(job.id, None)
            self._close_log(job.id)
            self._procs.pop(job.id, None)
            self._running.pop(job.id, None)
            self._session_ready.pop(job.id, None)

        cancelled = job.id in self._cancelled
        self._cancelled.discard(job.id)
        state, failure_reason = _final_state(parsed, exit_code, cancelled=cancelled)
        tail = "\n".join(stderr_lines[-_STDERR_TAIL_LINES:]) or None
        return await self._finish(
            job, role, state, parsed, exit_code, tail, failure_reason=failure_reason
        )

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

    # ------------------------------------------------------- job end (§24)

    def _observe_alive(self, job: Job) -> None:
        """Record now as the last moment claude held the job's pid, if it still does (§29).

        The clock is read before `/proc`: claude holds its pid from its fork until
        it is reaped, so a process that still has claude's start time after the
        reading held the pid at that reading. Called at spawn, on every poll of
        `_until_exit` (`_EXIT_POLL_S`), and at the start of the sweep.
        """
        leader = self._leader_start.get(job.id)
        if job.pid is None or leader is None:
            return
        now = boot_ticks()
        if start_time(job.pid) == leader:
            self._last_seen[job.id] = now

    async def _sweep(self, job: Job, isolation: str) -> list[dict[str, Any]]:
        """Report and kill what is still alive of the job (§24, §29).

        Called once claude has exited. Nothing found, nothing reported and
        nothing signalled. Otherwise `on_orphans` is handed every process with its
        command line and `killed`, and then the scope is stopped, or in group mode
        every process proven the job's is killed (`_kill_group`), with or without
        its `HANDS_JOB` mark (§30). What is still the job's but not proven (the
        residual in claude's session, marked or not, or a marked process outside
        it) is reported `killed: false` and left alive.
        """
        if job.pid is None:  # pragma: no cover - a spawned job always has one
            return []
        unit = unit_name(self.config.project, job.id)
        leader = self._leader_start.get(job.id)
        if isolation == SCOPE:
            path = await _systemctl(
                "show", "--property", "ControlGroup", "--value", f"{unit}.scope"
            )
            pids = cgroup_pids(path) if path else []
            processes = [
                {"pid": pid, "cmdline": cmdline(pid), "killed": True} for pid in pids[:MAX_PIDS]
            ]
        else:
            self._observe_alive(job)
            found = _job_processes(job.pid, leader, self._last_seen.get(job.id), job.id)
            processes = [
                {"pid": pid, "cmdline": cmdline(pid), "killed": proven}
                for pid, _start, proven in found[:MAX_PIDS]
            ]
        if not processes:
            return []
        log.warning(
            "job %s: %d process(es) outlived claude in its %s: %s",
            job.id,
            len(processes),
            isolation,
            ", ".join(
                f"{proc['pid']}{'' if proc['killed'] else ' (left alive)'}" for proc in processes
            ),
        )
        hook = self.on_orphans
        if hook is not None:
            try:
                hook(job, processes, isolation)
            except Exception:  # reporting must never keep the orphans alive
                log.exception("job %s: the orphan reporter failed", job.id)
        if isolation == SCOPE:
            await _systemctl("stop", f"{unit}.scope", timeout=SCOPE_STOP_S)
        elif any(proc["killed"] for proc in processes):
            await _kill_group(job.pid, leader, last_seen=self._last_seen.get(job.id))
        return processes

    async def _drain(
        self, proc: asyncio.subprocess.Process, io: asyncio.Future[Any], job: Job
    ) -> int | None:
        """After the sweep, read claude's pipes for at most `runner.pipe_timeout_s` (§29).

        A process the sweep left alive may still hold them; past the timeout the
        readers are cancelled and the pipes closed, and claude's exit status, which
        is already known, is the job's.
        """
        timeout = self.config.runner.pipe_timeout_s
        try:
            await asyncio.wait_for(io, timeout)
        except TimeoutError:
            log.warning(
                "job %s: claude's pipes are still held %gs after the sweep; ending the job",
                job.id,
                timeout,
            )
            # asyncio's `wait()` also waits for the pipes, so the transport is
            # closed here; claude has exited, so closing it signals nothing.
            transport = getattr(proc, "_transport", None)
            if transport is not None:
                transport.close()
            return proc.returncode
        return await proc.wait()

    def _last_resort(self, job: Job, isolation: str) -> None:
        """The run ended by an exception before its sweep: kill, report nothing."""
        if job.pid is None:
            return
        if isolation == SCOPE:
            unit = unit_name(self.config.project, job.id)
            with contextlib.suppress(OSError, subprocess.SubprocessError):
                subprocess.run(
                    ["systemctl", "--user", "stop", "--no-block", f"{unit}.scope"],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=PROBE_S,
                )
            return
        # Not a membership check: a group with members can be a new session
        # leader's that took claude's pid after claude was reaped, whether that
        # leader is alive (review 9 should-fix 1) or reaped too (review 10
        # should-fix 3); nor the mark (H-023). Only §29's proof selects.
        self._observe_alive(job)
        found = _job_processes(job.pid, self._leader_start.get(job.id), self._last_seen.get(job.id))
        for pid, start, proven in found:
            if proven:
                _signal_process(pid, start, signal.SIGKILL)

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

    def _open_log(self, job_id: str) -> None:
        """Open the job's stream log for the run (§7, §21)."""
        try:
            self._logs[job_id] = self.spool.stream_path(job_id).open("a", encoding="utf-8")
        except (OSError, SpoolError) as exc:  # pragma: no cover - unwritable spool
            log.warning("job %s: cannot open its stream log: %s", job_id, exc)

    def _close_log(self, job_id: str) -> None:
        handle = self._logs.pop(job_id, None)
        if handle is not None:
            with contextlib.suppress(Exception):
                handle.close()

    def _write_log(self, job_id: str, line: str) -> None:
        """Append one captured line, flushed so `hands log -f` sees it (§7, §21).

        A write that fails closes the log for the rest of the run: a full disk
        must not kill the job, and must not put one warning per event in the
        daemon's log either.
        """
        handle = self._logs.get(job_id)
        if handle is None:
            return
        try:
            handle.write(line + "\n")
            handle.flush()
        except OSError as exc:  # pragma: no cover - a full disk must not kill the job
            log.warning("job %s: cannot write its stream, dropping the rest: %s", job_id, exc)
            self._close_log(job_id)

    async def _read_stdout(
        self, proc: asyncio.subprocess.Process, job: Job, role: RoleConfig, parsed: _Parsed
    ) -> None:
        stream = proc.stdout
        if stream is None:  # pragma: no cover
            return
        async for raw in stream:
            line = raw.decode("utf-8", errors="replace").rstrip("\n")
            if not line.strip():
                continue
            # §21: written as it arrives, and then only the line at hand is held.
            self._write_log(job.id, line)
            line = line.strip()
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue  # not every line of a real run is an event
            if not isinstance(event, dict):
                continue
            self._on_event(event, job, role, parsed)
            self._observe(job, event)

    def _observe(self, job: Job, event: dict[str, Any]) -> None:
        hook = self.on_stream_event
        if hook is None:
            return
        try:
            hook(job, event)
        except Exception:  # the observer only reports; it never breaks a run
            log.exception("job %s: the stream observer failed", job.id)

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
        subtype = event.get("subtype")
        parsed.subtype = subtype if isinstance(subtype, str) else None
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
        if parsed.limit_category is None and is_limit_notice(result):
            parsed.limit_category = _RATE_LIMIT
            parsed.limit_message = result

    @staticmethod
    async def _read_stderr(
        proc: asyncio.subprocess.Process, sink: list[str], parsed: _Parsed
    ) -> None:
        stream = proc.stderr
        if stream is None:  # pragma: no cover
            return
        async for raw in stream:
            line = raw.decode("utf-8", errors="replace").rstrip("\n")
            # Checked on every line, not on the tail: 50 later lines must not
            # hide the one that says why the process ended (§23).
            if is_harness_termination(line):
                parsed.harness_terminated = True
            sink.append(line)
            del sink[:-_STDERR_TAIL_LINES]

    async def _finish(
        self,
        job: Job,
        role: RoleConfig,
        state: str,
        parsed: _Parsed,
        exit_code: int | None,
        stderr_tail: str | None,
        *,
        failure_reason: str | None = None,
    ) -> Job:
        limit = None
        if state == "limited":
            # §6's `{category, message, reset_at}`. `message` is the raw notice,
            # stored whatever the parser makes of it; `reset_at` is None whenever
            # the notice names no usable reset time, and the daemon then waits
            # `limits.backoff_minutes` (`hands.limits`).
            limit = {
                "category": parsed.limit_category,
                "message": parsed.limit_message,
                "reset_at": to_iso(parse_reset_at(parsed.limit_message)),
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
            "failure_reason": failure_reason if state == "failed" else None,
        }
        updates["head_at_end"] = await _git_head(role.cwd)
        finished = self.spool.transition(job, state, **updates)
        self.spool.append_event(f"job.{state}", _event_payload(finished))
        return finished


def _final_state(
    parsed: _Parsed, exit_code: int | None, *, cancelled: bool
) -> tuple[str, str | None]:
    """The terminal state and, for `failed`, its `failure_reason` (§6, §23)."""
    if cancelled:
        return "killed", None  # a human asked; nothing the process said changes that
    if parsed.limit_category is not None:
        # Decided in U1 of mission 7a: a limit wins over the terminating line. §6
        # owns the limit resume and waits out the reset; `failed` would hand the
        # playbook a `builder.failed → resume` straight back into the limit (H-005).
        return "limited", None
    reason = _failure_reason(parsed, exit_code)
    return ("failed", reason) if reason is not None else ("done", None)


def _failure_reason(parsed: _Parsed, exit_code: int | None) -> str | None:
    """The first of `FAILURE_REASONS` that holds for a finished run, or None."""
    if parsed.harness_terminated:
        return "harness_terminated"  # §6: wins even over a `success` result (H-014)
    if not parsed.saw_result or not _is_final_subtype(parsed.subtype):
        return "no_final_result"
    if parsed.is_error or parsed.subtype != "success":
        return "error_result"  # §6: `error`/`error_*` fails whatever `is_error` says
    if exit_code != 0:
        return "nonzero_exit"
    if parsed.num_turns is None:
        return "no_num_turns"
    return None


def job_env(job: Job, role: RoleConfig) -> dict[str, str]:
    """handsd's environment, the role's `spawn_env` (§23) and `HANDS_JOB` (§27).

    §28: a driver job also carries `HANDS_CONSULT_ROLE`, the role its consult
    prompt's first line names, and never a value from anywhere else: with no
    readable head the variable is absent, and the guard refuses every send.
    §29: it also carries `HANDS_CLONE`, the role's clone (`driver_clone`), the same
    way: never from handsd's environment or the env table, and absent with no
    clone, when the guard refuses every `git -C`.
    §31: an architect job carries the same `HANDS_CLONE` and, in addition,
    `HANDS_KITS` — `<cwd>/kits`, the one directory that role may write to. It is
    set whether or not the directory exists yet: the guard confines paths to it,
    and a `mkdir -p` under it is how the architect makes it.
    """
    env = {**os.environ, **role.spawn_env, JOB_ENV: job.id}
    if job.role in (DRIVER_ROLE, ARCHITECT_ROLE):
        env.pop(CONSULT_ROLE_ENV, None)
        head = consult_head(job.prompt)
        if head is not None:
            env[CONSULT_ROLE_ENV] = head["role"]
        env.pop(CLONE_ENV, None)
        clone = driver_clone(role.cwd)
        if clone is not None:
            env[CLONE_ENV] = str(clone)
    if job.role == ARCHITECT_ROLE:
        env[KITS_ENV] = str(role.cwd / "kits")
    return env


def _signal(proc: asyncio.subprocess.Process, signum: int) -> None:
    try:
        proc.send_signal(signum)
    except ProcessLookupError:  # it finished between the check and the signal
        pass


async def _wait(proc: asyncio.subprocess.Process) -> int:
    return await proc.wait()


async def _until_exit(
    proc: asyncio.subprocess.Process, io: asyncio.Future[Any], observe: Callable[[], None]
) -> None:
    """Until the pipes are drained, or claude has exited and `DRAIN_S` has passed.

    asyncio's `wait()` also waits for the pipes to close, and an orphan that
    inherited them keeps them open; the exit status itself arrives without them.
    `observe` is called on every poll: it records claude still holding its pid
    (§29's last observation), so a fork inside the last `_EXIT_POLL_S` is the
    residual the sweep cannot prove.
    """
    while not io.done() and proc.returncode is None:
        observe()
        await asyncio.wait({io}, timeout=_EXIT_POLL_S)
    observe()
    if not io.done():
        await asyncio.wait({io}, timeout=DRAIN_S)


def _read_text(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _job_processes(
    pgid: int, leader_start: int | None, last_seen: int | None, job_id: str | None = None
) -> list[tuple[int, int, bool]]:
    """`(pid, start time, proven)` of every live process that is the job's (§29).

    Linux does not hand a pid out again while a process has it as its pid, its
    process-group id or its session id. claude was started as a session leader, so
    a live process whose session id is the job's pid (`pgid`) is in claude's
    session, and descends from claude, when the pid was never free since it
    started: when claude held the pid at a moment after the process started.
    `proven` is True for a process in that session which

    * started in a clock tick before `last_seen`, the last observation of claude
      holding the pid (`Runner._observe_alive`), or
    * was read before claude was seen holding the pid now (its start time equals
      `leader_start`, read after the scan: the leader is still alive or a zombie).

    Nothing else proves anything, and the mark is not read for the proof: a
    proven process is the job's with or without it (§30). With `job_id`, what is
    left is listed with `proven` False when it is still the job's to report (§29,
    §30): a process in claude's session that forked inside claude's last poll
    interval (the residual; its start is not before `last_seen`), marked or not,
    unless the pid is now held by a process that is not claude (a new session
    leader took it, so its session is a stranger's) or claude was never observed
    holding it; and a process that carries `HANDS_JOB=<job_id>` (one that called
    setsid, or one in a group whose id is the job's pid but whose session is not).
    A process that is neither is a stranger and not listed. A start time that
    could not be read at spawn (None) proves nothing; nothing unproven is listed
    without `job_id`.
    """
    stats = proc_stats()
    holder = start_time(pgid)
    leader_holds = leader_start is not None and holder == leader_start
    # A live process holding the pid that is not claude took it after claude was
    # reaped, when no process had it as a session id: every member is its own.
    reused = holder is not None and not leader_holds
    found: list[tuple[int, int, bool]] = []
    for pid, sid, start in stats:
        in_session = sid == pgid
        proven = in_session and (
            leader_holds or (last_seen is not None and start < last_seen)
        )
        if proven:
            found.append((pid, start, True))
        elif job_id is None:
            continue
        elif (in_session and last_seen is not None and not reused) or environ_has(
            pid, JOB_ENV, job_id
        ):
            found.append((pid, start, False))
    return found


def _signal_process(pid: int, start: int, signum: int) -> None:
    """Signal `pid` only while it is the process that started at `start`. Never raises.

    Where the interpreter has pidfds, the pidfd pins the process first, so the
    start time read after it cannot belong to a later process with the same pid.
    Without them (some Python builds lack `os.pidfd_open`) the start time is read
    and then `kill` is sent: two steps, not one, as the group kill always was.
    """
    pidfd_open = getattr(os, "pidfd_open", None)
    send = getattr(signal, "pidfd_send_signal", None)
    if pidfd_open is None or send is None:
        with contextlib.suppress(OSError):
            if start_time(pid) == start:
                os.kill(pid, signum)
        return
    try:
        fd = pidfd_open(pid)
    except OSError:
        return  # it is gone: nothing is signalled on a guess
    try:
        if start_time(pid) == start:
            send(fd, signum)
    except OSError:
        pass
    finally:
        os.close(fd)


async def _kill_group(
    pgid: int,
    leader_start: int | None,
    *,
    last_seen: int | None,
    grace: float = ORPHAN_GRACE_S,
) -> None:
    """SIGTERM the job's processes, wait `grace`, SIGKILL what is left, wait again.

    §24's group kill, one process at a time: before each signal the processes are
    read again and only those §29's session proof still shows are the job's
    (`_job_processes`) are signalled. A member of the group that is not proven
    (the `HANDS_JOB` mark alone, a foreign session, a fork after `last_seen`) is
    never signalled.
    """
    remaining: set[tuple[int, int]] = set()
    for signum in (signal.SIGTERM, signal.SIGKILL):
        targets = [
            (pid, start) for pid, start, proven in _job_processes(pgid, leader_start, last_seen)
            if proven
        ]
        if not targets:
            return
        for pid, start in targets:
            _signal_process(pid, start, signum)
        deadline = time.monotonic() + grace
        while True:
            live = {(pid, start) for pid, _sid, start in proc_stats()}
            remaining = set(targets) & live
            if not remaining or time.monotonic() >= deadline:
                break
            await asyncio.sleep(0.02)
        if not remaining:
            return
    log.warning(
        "job group %d still has processes after SIGKILL: %s",
        pgid,
        sorted(pid for pid, _start in remaining),
    )


async def _systemctl(*args: str, timeout: float = PROBE_S) -> str | None:
    """`systemctl --user <args>`'s stdout, stripped, or None. Never raises."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "systemctl",
            "--user",
            *args,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
    except OSError:
        return None
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout)
    except TimeoutError:
        with contextlib.suppress(ProcessLookupError):
            proc.kill()
        await proc.wait()
        return None
    if proc.returncode != 0:
        return None
    return out.decode("utf-8", errors="replace").strip()


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
