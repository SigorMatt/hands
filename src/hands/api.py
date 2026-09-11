"""The local API — one method per command of DESIGN §4.

This is the surface, and the only surface: the CLI is a thin JSON-RPC client
over it (§3) and the optional remote face of §9 would wrap these same methods
one-to-one. That standing requirement shapes three things here:

* one method per command, named exactly as the command is named;
* arguments named as the CLI names them (`--role` → `role`, `--context` →
  `context`, `-n` → `n`), so a caller that knows the CLI knows the API;
* every result is JSON-serialisable — plain dicts and lists, no objects.

Commands whose implementation belongs to a later unit are *present* with their
final name and arguments and raise `NotImplementedYet` naming that unit. They
are seams, not stubs: nothing in this unit's scope is hidden behind one.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from hands.runner import KeepRefused
from hands.spool import TERMINAL_STATES, Event, Job, SpoolError

if TYPE_CHECKING:  # pragma: no cover - import cycle only matters to type checkers
    from hands.daemon import Daemon

__all__ = ["Api", "ApiError", "NotImplementedYet", "Timeout", "job_summary"]

# JSON-RPC 2.0 reserves -32768..-32000 for the protocol; -32000..-32099 is the
# implementation-defined server-error range, which is where these live.
HANDS_ERROR = -32001  # a refusal hands is sure about (bad role, full queue, …)
NOT_IMPLEMENTED = -32002  # the command exists; its unit has not landed yet
TIMEOUT = -32003  # `wait --timeout` expired


class ApiError(Exception):
    """A refusal to report to the caller as a JSON-RPC error."""

    code = HANDS_ERROR


class NotImplementedYet(ApiError):
    code = NOT_IMPLEMENTED


class Timeout(ApiError):
    code = TIMEOUT


def _later(command: str, unit: str, what: str) -> NotImplementedYet:
    return NotImplementedYet(f"`hands {command}` is not implemented ({unit}): {what}")


_SINCE_RE = re.compile(r"^(\d+)([dhm])$")
_SUMMARY_FIELDS = (
    "id", "role", "context", "state", "created", "started", "ended",
    "origin", "verdict", "session_id", "pid", "resumed_from",
)  # fmt: skip
_PROMPT_LINE_CHARS = 120


def job_summary(job: Job) -> dict[str, Any]:
    """The short form of a job record, for `jobs` and `status` (§4)."""
    out: dict[str, Any] = {name: getattr(job, name) for name in _SUMMARY_FIELDS}
    first = job.prompt.splitlines()[0] if job.prompt else ""
    out["prompt_line"] = first[:_PROMPT_LINE_CHARS]
    return out


class Api:
    """Every command of §4, bound to one running daemon."""

    #: The command surface of §4, in the order §4 lists it. `hands --help` and
    #: the MCP face of §9 both read this, so the two can never drift apart.
    COMMANDS: tuple[str, ...] = (
        "send", "wait", "result", "jobs", "show", "open", "log", "cancel",
        "put", "get", "ls", "tail", "inbox", "pipeline", "approve", "deny",
        "pause", "resume", "status", "doctor",
    )  # fmt: skip

    def __init__(self, daemon: Daemon) -> None:
        self.daemon = daemon
        self.config = daemon.config
        self.spool = daemon.spool

    def method(self, name: str) -> Any:
        """The bound coroutine for a command name, or None if there is no such command."""
        if name not in self.COMMANDS:
            return None
        return getattr(self, name)

    # ------------------------------------------------------------------ send

    async def send(
        self,
        *,
        role: str,
        context: str,
        prompt: str,
        file: list[str] | None = None,
        gate: str | None = None,
        origin: str = "cli",
    ) -> dict[str, Any]:
        """Queue a prompt for a role (§4, §6). Returns the job record."""
        if role not in self.config.roles:
            known = ", ".join(sorted(self.config.roles))
            raise ApiError(f"unknown role {role!r}; this project configures: {known}")
        if context not in ("clear", "keep"):
            raise ApiError(f"--context must be clear or keep, got {context!r}")
        if not prompt.strip():
            raise ApiError("refusing to send an empty prompt")
        if file:
            raise _later("send", "U4", "--file writes content under the allowed roots")
        if gate:
            raise _later("send", "U4", "--gate holds the job for a human (§8)")

        # §8: "gating on the default patterns cannot be disabled". Until U4 can
        # hold a job, a matching prompt is refused rather than run ungated —
        # running it would silently disable a gate the design says is absolute.
        for pattern in self.config.gates.patterns:
            if pattern in prompt:
                raise _later(
                    "send", "U4", f"this prompt matches the gate pattern {pattern!r} (§8)"
                )

        if context == "keep":
            # §6: refused if there is no session or its last job is not terminal.
            # Checked here so the refusal lands on the `send`, not on a job that
            # has already been accepted.
            try:
                self.daemon.runner.resolve_resume_session(role)
            except KeepRefused as exc:
                raise ApiError(str(exc)) from exc

        job = self.daemon.enqueue(
            role=role, context=context, prompt=prompt, origin=origin
        )
        return job.to_dict()

    # ------------------------------------------------------------------ wait

    async def wait(
        self,
        *,
        job: str | None = None,
        for_: str | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """A job's record once it is terminal (§4). `--for <kinds>` is U8."""
        if for_:
            raise _later("wait", "U8", "--for <event kinds> is the driver's wake path (§11)")
        if not job:
            raise ApiError("hands wait needs a job id (or --for <kinds>, which is U8)")
        record = self._job(job)
        if record.state in TERMINAL_STATES:
            return record.to_dict()
        finished = await self.daemon.wait_for_terminal(job, timeout=timeout)
        if finished is None:
            state = self._job(job).state
            raise Timeout(f"timeout after {timeout}s waiting for job {job} (state: {state})")
        return finished.to_dict()

    # ----------------------------------------------------------- job library

    async def result(self, *, job: str) -> dict[str, Any]:
        """The job record, verbatim (§4, §6)."""
        return self._job(job).to_dict()

    async def show(self, *, job: str) -> dict[str, Any]:
        """The job record (§4). Identical to `result`; both are in §4, so both exist."""
        return self._job(job).to_dict()

    async def jobs(
        self,
        *,
        role: str | None = None,
        grep: str | None = None,
        since: str | None = None,
        n: int = 20,
    ) -> dict[str, Any]:
        """Recent job summaries, newest first (§4). Rendering is U9's."""
        cutoff = _since_cutoff(since)
        out: list[dict[str, Any]] = []
        for record in reversed(self.spool.list_jobs()):
            if role is not None and record.role != role:
                continue
            if grep is not None and grep not in record.prompt:
                continue
            if cutoff is not None and record.created < cutoff:
                continue
            out.append(job_summary(record))
            if n and len(out) >= n:
                break
        return {"jobs": out}

    async def open(self, *, job: str) -> dict[str, Any]:
        raise _later("open", "U9", "the `claude --resume` line for a finished job (§7)")

    async def log(self, *, job: str | None = None, role: str | None = None) -> dict[str, Any]:
        raise _later(
            "log", "U9", "the captured stream; the daemon already writes jobs/<id>.stream.jsonl"
        )

    async def tail(self, *, role: str, n: int = 20) -> dict[str, Any]:
        raise _later("tail", "U9", "the last n transcript entries of a role's session")

    # ---------------------------------------------------------------- cancel

    async def cancel(self, *, job: str, reason: str | None = None) -> dict[str, Any]:
        """Stop a job: SIGINT then SIGTERM if running, drop it if queued (§2, §4).

        §4 gates cancel by default; the gate itself is U4. This is the ungated
        form, which is what `role.cancel_gated = false` will reach.
        """
        record = self._job(job)
        return (await self.daemon.cancel(record, reason=reason)).to_dict()

    # ----------------------------------------------------------------- inbox

    async def inbox(self, *, ack: bool = False) -> dict[str, Any]:
        """Unread events, verbatim (§11). `--ack` marks the ones returned read."""
        events: list[Event] = self.spool.unacked()
        acked: list[str] = []
        if ack and events:
            acked = self.spool.ack([event.id for event in events])
        return {"events": [event.to_dict() for event in events], "acked": acked}

    # ---------------------------------------------------------------- status

    async def status(self) -> dict[str, Any]:
        """Daemon, roles, running jobs, monitor state (§4)."""
        return self.daemon.status()

    # ------------------------------------------------------ later units (§4)

    async def put(
        self, *, path: str, content: str | None = None, from_: str | None = None
    ) -> dict[str, Any]:
        raise _later("put", "U4", "writing content under files.allowed_roots")

    async def get(self, *, path: str) -> dict[str, Any]:
        raise _later("get", "U4", "reading a file under files.allowed_roots")

    async def ls(self, *, path: str) -> dict[str, Any]:
        raise _later("ls", "U4", "listing a directory under files.allowed_roots")

    async def approve(
        self,
        *,
        job: str,
        reason: str | None = None,
        human_confirmed: bool = False,
        quote: str | None = None,
    ) -> dict[str, Any]:
        raise _later("approve", "U4", "the gate authority table of §8")

    async def deny(
        self,
        *,
        job: str,
        reason: str | None = None,
        human_confirmed: bool = False,
        quote: str | None = None,
    ) -> dict[str, Any]:
        raise _later("deny", "U4", "the gate authority table of §8")

    async def pipeline(self) -> dict[str, Any]:
        raise _later("pipeline", "U7", "the active playbook and its counters (§10)")

    async def pause(self) -> dict[str, Any]:
        raise _later("pause", "U7", "pausing the playbook engine (§10)")

    async def resume(self) -> dict[str, Any]:
        raise _later("resume", "U7", "unpausing the playbook engine (§10)")

    async def doctor(self) -> dict[str, Any]:
        raise _later("doctor", "U10", "the install check of §4 and §11")

    # -------------------------------------------------------------- internals

    def _job(self, job_id: str) -> Job:
        try:
            return self.spool.load_job(job_id)
        except SpoolError as exc:
            raise ApiError(str(exc)) from exc



def _since_cutoff(since: str | None) -> str | None:
    """`--since 2d|6h|30m` → an ISO cutoff; anything else is used as a literal prefix."""
    if since is None:
        return None
    match = _SINCE_RE.match(since.strip())
    if match is None:
        return since  # e.g. `--since 2026-09-01`; job.created sorts lexically
    amount, unit = int(match.group(1)), match.group(2)
    delta = {"d": timedelta(days=amount), "h": timedelta(hours=amount)}.get(
        unit, timedelta(minutes=amount)
    )
    return (datetime.now(UTC) - delta).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
