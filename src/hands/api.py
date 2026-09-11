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

from hands import files, gates
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

        # §8: "gating on the default patterns cannot be disabled" — `config.py`
        # keeps the defaults in `gates.patterns` whatever the project says.
        reason = gates.gate_reason(prompt, explicit=gate, patterns=self.config.gates.patterns)

        if context == "keep":
            # §6: refused if there is no session or its last job is not terminal.
            # Checked here so the refusal lands on the `send`, not on a job that
            # has already been accepted.
            try:
                self.daemon.runner.resolve_resume_session(role)
            except KeepRefused as exc:
                raise ApiError(str(exc)) from exc

        # §4: `--file path=content`, written before the spawn and recorded with
        # its sha256 (§1 invariant 2). Every path is confined before any byte is
        # written, so a path outside the roots refuses the whole send.
        written = self._write_files(file or [])

        job = self.daemon.enqueue(
            role=role,
            context=context,
            prompt=prompt,
            origin=origin,
            gate=gates.new_gate(kind="send", reason=reason) if reason else None,
            files_written=written,
        )
        if reason:
            self.spool.append_event(
                "job.held",
                {"job": job.id, "role": role, "state": "held", "reason": reason, "gate": "send"},
            )
        return job.to_dict()

    def _write_files(self, specs: list[str]) -> list[dict[str, Any]]:
        try:
            return files.write_files(specs, roots=self.config.files.allowed_roots)
        except (files.PathEscape, files.FileError) as exc:
            raise ApiError(str(exc)) from exc

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

        §4: "held for human unless `role.cancel_gated: false`". When the role
        gates its cancels the job is *not* touched — the request waits for a
        decision and the record comes back in the state it is still in, with the
        pending gate on it.
        """
        record = self._job(job)
        if self.config.role(record.role).cancel_gated:
            return (await self._request_cancel(record, reason)).to_dict()
        return (await self.daemon.cancel(record, reason=reason)).to_dict()

    async def _request_cancel(self, record: Job, reason: str | None) -> Job:
        """Park a gated cancel until a human decides it (§8)."""
        if record.state in TERMINAL_STATES:
            raise ApiError(f"job {record.id} is already {record.state}")
        if record.state == "held":
            raise ApiError(
                f"job {record.id} is held and has not run; decide the job itself "
                f"with `hands approve {record.id}` or `hands deny {record.id}` (§8)"
            )
        if record.id in self.daemon.pending_cancels:
            raise ApiError(
                f"a cancel of job {record.id} is already waiting for a human decision (§8)"
            )
        gate = gates.new_gate(
            kind="cancel",
            reason=reason or f"cancel job {record.id} ({record.role})",
        )
        self.daemon.pending_cancels[record.id] = gate
        self.spool.append_event(
            "gate.requested",
            {
                "job": record.id,
                "role": record.role,
                "gate": "cancel",
                "reason": gate["reason"],
                "state": record.state,
            },
        )
        # Returned with the gate on it so the caller sees that nothing died. It is
        # deliberately not saved: while a job runs, the runner owns its record.
        out = self._job(record.id)
        out.gate = gate
        return out

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

    # ----------------------------------------------------------------- files

    async def put(
        self, *, path: str, content: str | None = None, from_: str | None = None
    ) -> dict[str, Any]:
        """Write a file under `files.allowed_roots` → sha256 and bytes (§4)."""
        return self._files(files.put_file, path, content=content, from_path=from_)

    async def get(self, *, path: str) -> dict[str, Any]:
        """Read a file under `files.allowed_roots` → its content (§4)."""
        return self._files(files.read_file, path)

    async def ls(self, *, path: str) -> dict[str, Any]:
        """List a directory under `files.allowed_roots` → entries (§4)."""
        return self._files(files.list_dir, path)

    def _files(self, operation: Any, path: str, **kwargs: Any) -> dict[str, Any]:
        try:
            return operation(path, roots=self.config.files.allowed_roots, **kwargs)
        except (files.PathEscape, files.FileError) as exc:
            raise ApiError(str(exc)) from exc

    # ------------------------------------------------------------ gates (§8)

    async def approve(
        self,
        *,
        job: str,
        reason: str | None = None,
        human_confirmed: bool = False,
        quote: str | None = None,
    ) -> dict[str, Any]:
        """Release a held job, or carry out a gated cancel (§8)."""
        return await self._decide(
            job, "approved", reason=reason, human_confirmed=human_confirmed, quote=quote
        )

    async def deny(
        self,
        *,
        job: str,
        reason: str | None = None,
        human_confirmed: bool = False,
        quote: str | None = None,
    ) -> dict[str, Any]:
        """Refuse a held job (terminal, §6) or a gated cancel (the job runs on)."""
        return await self._decide(
            job, "denied", reason=reason, human_confirmed=human_confirmed, quote=quote
        )

    async def _decide(
        self,
        job: str,
        decision: str,
        *,
        reason: str | None,
        human_confirmed: bool,
        quote: str | None,
    ) -> dict[str, Any]:
        """The authority table of §8, applied to whichever gate is waiting.

        The daemon cannot tell the laptop CLI from the driver — both are local
        clients of the same socket — and does not pretend to: `--human-confirmed`
        is a declaration, and its whole force is the quote it must carry. See
        `hands.gates`.
        """
        record = self._job(job)
        decided_by = gates.decider_for(human_confirmed=human_confirmed)
        try:
            gates.check_decider(decided_by, quote)
        except gates.GateRefused as exc:
            raise ApiError(str(exc)) from exc

        if record.state == "held":
            return await self._decide_send(record, decision, decided_by, quote, reason)
        pending = self.daemon.pending_cancels.get(record.id)
        if pending is not None:
            return await self._decide_cancel(record, pending, decision, decided_by, quote, reason)
        was = f"job {record.id} is {record.state}"
        if record.state == "denied":
            was += " — a denied job is terminal (§8)"
        raise ApiError(f"{was}; there is no gate on it waiting for a decision")

    async def _decide_send(
        self,
        record: Job,
        decision: str,
        decided_by: str,
        quote: str | None,
        reason: str | None,
    ) -> dict[str, Any]:
        gate = self._stamp(
            record.gate or gates.new_gate(kind="send", reason="gated"),
            decision, decided_by, quote, reason,
        )
        if decision == "approved":
            out = await self.daemon.release(record, gate=gate)
        else:
            out = self.spool.transition(record, "denied", gate=gate)
            self.spool.append_event(
                "job.denied",
                {"job": record.id, "role": record.role, "state": "denied", "reason": reason},
            )
        self._gate_decided(out, gate)
        return out.to_dict()

    async def _decide_cancel(
        self,
        record: Job,
        pending: dict[str, Any],
        decision: str,
        decided_by: str,
        quote: str | None,
        reason: str | None,
    ) -> dict[str, Any]:
        if record.state in TERMINAL_STATES:
            self.daemon.pending_cancels.pop(record.id, None)
            raise ApiError(
                f"job {record.id} reached {record.state} on its own; "
                "there is nothing left to cancel"
            )
        gate = self._stamp(pending, decision, decided_by, quote, reason)
        # Spent either way: a denied cancel is not standing permission to ask
        # again without a human, and an approved one is carried out now.
        self.daemon.pending_cancels.pop(record.id, None)
        self._gate_decided(record, gate)
        if decision == "denied":
            out = self._job(record.id)  # untouched: the job runs on
            out.gate = gate
            return out.to_dict()
        return (await self.daemon.cancel(record, reason=gate["reason"])).to_dict()

    def _stamp(
        self,
        gate: dict[str, Any],
        decision: str,
        decided_by: str,
        quote: str | None,
        reason: str | None,
    ) -> dict[str, Any]:
        try:
            return gates.decide(
                gate, decision=decision, decided_by=decided_by, quote=quote, reason=reason
            )
        except gates.GateRefused as exc:
            raise ApiError(str(exc)) from exc

    def _gate_decided(self, record: Job, gate: dict[str, Any]) -> None:
        self.spool.append_event(
            "gate.decided",
            {
                "job": record.id,
                "role": record.role,
                "gate": gate.get("kind"),
                "reason": gate.get("reason"),
                "decision": gate["decision"],
                "decided_by": gate["decided_by"],
                "decided_at": gate["decided_at"],
                "quote": gate["quote"],
                "decided_reason": gate["decided_reason"],
            },
        )

    # ------------------------------------------------------ later units (§4)

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
