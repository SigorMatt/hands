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
`CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0` unless `[roles.<r>] env` sets it.

A job is `done` only when the process ends cleanly with a final `result` event
of subtype `success` (or the `error_*` family) that carries `num_turns`, and
stderr never said the harness terminated it (§2, §6, §23; H-014). Anything else
is `failed`, and `failure_reason` names which — see `FAILURE_REASONS`.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import re
import signal
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TextIO

from hands.config import Config, RoleConfig
from hands.limits import is_limit_notice, parse_reset_at, to_iso
from hands.spool import TERMINAL_STATES, Job, Spool, SpoolError

__all__ = [
    "FAILURE_REASONS",
    "LINE_LIMIT",
    "MAX_PROMPT_BYTES",
    "KeepRefused",
    "Runner",
    "RunnerError",
    "build_argv",
    "extract_verdict",
    "is_harness_termination",
    "project_dir_name",
    "reconcile_orphans",
    "transcript_path_for",
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

# §23 (H-014). claude 2.1.269 writes, when its bg-wait ceiling ends a `-p` run:
#   `Background tasks still running after ${Math.round(ms/1000)}s; terminating.
#    Set CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0 to wait indefinitely.`
# (read from the binary; the job 0mtygi953-ym63 line is that, with 600). Matched on
# its shape, so neither the number, its unit, the case, a singular "task" nor
# terminal colour codes around it change the answer.
_TERMINATING_RE = re.compile(
    r"background tasks? still running after\s+\d[\d.,]*\s*[a-z]*\s*;\s*terminating\b",
    re.IGNORECASE,
)

#: Every `failure_reason` the runner writes, in the order it checks them (§23):
#:   harness_terminated  stderr carried the harness's `terminating` line
#:   no_final_result     no `result` event, or its subtype is not success/error_*
#:   error_result        the final result says `is_error`
#:   nonzero_exit        a clean result, but the process exited non-zero
#:   no_num_turns        a clean result with no `num_turns`
#:   spawn_error         the process could not be started at all
#: The first that holds is the one recorded. A cancel (`killed`) and a detected
#: limit (`limited`) are decided before any of these, and their reason is null.
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
    """Does this stderr line say the harness terminated the `-p` process? (§23)"""
    return _TERMINATING_RE.search(line) is not None


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
        is bounded by `MAX_LAST_ARGV` instead.

        What it does not count, so the number is not read as everything the
        runner holds: the in-flight `_Parsed.result` (one job's final result),
        the stderr tail `run()` keeps as a local (`_STDERR_TAIL_LINES` lines),
        and asyncio's own reader buffer (`_STREAM_LIMIT`). Each is bounded, none
        is per-event, and none of them is on this object to be counted.
        """
        return {
            "cancelled": len(self._cancelled),
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
        self._remember_argv(job.id, argv)

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
                env={**os.environ, **role.spawn_env},  # §23
            )
        except OSError as exc:
            # The one dispatch failure that never produces a process. `failed` is
            # the only terminal state §6 offers for it.
            reason = f"cannot spawn {argv[0]}: {exc}"
            return await self._finish(
                job, role, "failed", _Parsed(), None, reason, failure_reason="spawn_error"
            )

        self._procs[job.id] = proc
        job.pid = proc.pid
        self.spool.save_job(job)
        self._running.setdefault(job.id, asyncio.Event()).set()

        parsed = _Parsed()
        stderr_lines: list[str] = []
        self._open_log(job.id)
        try:
            await asyncio.gather(
                self._write_prompt(proc, job.prompt),
                self._read_stdout(proc, job, role, parsed),
                self._read_stderr(proc, stderr_lines, parsed),
            )
            exit_code = await proc.wait()
        finally:
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
        return "harness_terminated"
    if not parsed.saw_result or not _is_final_subtype(parsed.subtype):
        return "no_final_result"
    if parsed.is_error:
        return "error_result"
    if exit_code != 0:
        return "nonzero_exit"
    if parsed.num_turns is None:
        return "no_num_turns"
    return None


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
