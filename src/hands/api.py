"""The local API — one method per command of DESIGN §4.

This is the surface, and the only surface: the CLI is a thin JSON-RPC client
over it (§3) and the optional remote face of §9 would wrap these same methods
one-to-one. That standing requirement shapes three things here:

* one method per command, named exactly as the command is named;
* arguments named as the CLI names them (`--role` → `role`, `--context` →
  `context`, `-n` → `n`), so a caller that knows the CLI knows the API;
* every result is JSON-serialisable — plain dicts and lists, no objects.

Every command of §4 is implemented here. `doctor` is the one method that also
exists outside the daemon: §14 runs `hands doctor` on a fresh config, before
handsd has ever been started, so the checks themselves live in `hands.doctor`
and both halves call them.
"""

from __future__ import annotations

import asyncio
import os
import re
import shlex
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

from hands import __version__, files, gates
from hands.doctor import report as doctor_report
from hands.doctor import run_checks as doctor_checks
from hands.notify import NotifyError, send_test
from hands.runner import KeepRefused
from hands.spool import ORIGINS, TERMINAL_STATES, Event, Job, SpoolError, resolve_kinds

if TYPE_CHECKING:  # pragma: no cover - import cycle only matters to type checkers
    from hands.daemon import Daemon

__all__ = ["Api", "ApiError", "Timeout", "job_summary"]

# JSON-RPC 2.0 reserves -32768..-32000 for the protocol; -32000..-32099 is the
# implementation-defined server-error range, which is where these live.
HANDS_ERROR = -32001  # a refusal hands is sure about (bad role, full queue, …)
TIMEOUT = -32003  # `wait --timeout` expired


class ApiError(Exception):
    """A refusal to report to the caller as a JSON-RPC error."""

    code = HANDS_ERROR


class Timeout(ApiError):
    code = TIMEOUT


_SINCE_RE = re.compile(r"^(\d+)([smhdw])$")
#: `--since 2026-09-01`, or a fuller ISO stamp; compared lexically against `created`.
_ISO_SINCE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}([T ][0-9:.]+Z?)?$")
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
        "pause", "resume", "status", "notify", "doctor",
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
        playbook_sha256: str | None = None,
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
            playbook_sha256=playbook_sha256,
        )
        # §10's stop → resume cycle: "`hands resume` or the next `send` un-pauses
        # the pipeline". Not the engine's own sends, which are the pipeline.
        await self.daemon.playbook.on_send(origin)
        if reason:
            self.spool.append_event(
                "job.held",
                {"job": job.id, "role": role, "state": "held", "reason": reason, "gate": "send"},
            )
            # §10 lists `job.held`: a job waiting for a human is the pipeline's
            # business, and with no rule for it the pipeline stops.
            await self.daemon.playbook.on_event("job.held", job=job)
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
        """A job's record once it is terminal, or the first event of `--for` (§4, §11).

        `--for` is the driver's wake path: it blocks on a subscription, returns
        the event *unacked* (the driver acks it with `hands inbox --ack` once it
        has acted), and answers a timeout with a `Timeout` error, which the CLI
        turns into its own exit code so a background wait can be told apart from
        a failure.
        """
        if for_:
            if job:
                raise ApiError(
                    f"hands wait takes a job id or --for <kinds>, not both (got {job!r})"
                )
            try:
                kinds = resolve_kinds(for_)
            except SpoolError as exc:
                raise ApiError(str(exc)) from exc
            event = await self.daemon.wait_for_event(kinds, timeout=timeout)
            if event is None:
                raise Timeout(f"timeout after {timeout}s waiting for an event of {for_}")
            return event.to_dict()
        if not job:
            raise ApiError("hands wait needs a job id, or --for <kinds> (§11)")
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
        origin: str | None = None,
        grep: str | None = None,
        since: str | None = None,
        n: int = 20,
    ) -> dict[str, Any]:
        """Recent job summaries, newest first (§4, §7).

        `origin` is §6's closed vocabulary (`driver|playbook|cli|limit`), and a
        spelling outside it is refused rather than answered with "no jobs": every
        value is a filter that can legitimately match nothing, so silence would
        not tell a typo from an empty result.

        §7: "searching prompts is searching work items". `grep` is a
        case-insensitive substring of the *prompt* only — not of `result`: the
        prompt is the work item a human named ("run 3", "Batch 12"), while the
        result is the model's prose, and matching it would answer a search for a
        run with jobs that were never part of it. What a human wants out of the
        result — the verdict — is on every summary line already.
        """
        cutoff = _since_cutoff(since)
        if origin is not None and origin not in ORIGINS:
            known = ", ".join(sorted(ORIGINS))
            raise ApiError(f"unknown origin {origin!r}; §6's origins are: {known}")
        needle = grep.lower() if grep is not None else None
        out: list[dict[str, Any]] = []
        for record in reversed(self.spool.list_jobs()):
            if role is not None and record.role != role:
                continue
            if origin is not None and record.origin != origin:
                continue
            if needle is not None and needle not in record.prompt.lower():
                continue
            if cutoff is not None and record.created < cutoff:
                continue
            out.append(job_summary(record))
            if n and len(out) >= n:
                break
        return {"jobs": out}

    async def open(self, *, job: str) -> dict[str, Any]:
        """The `claude --resume <session_id>` invocation for a finished job (§7).

        The API only ever *describes* the session: it returns the argv and the
        directory, and the CLI is what execs it (§3 — the daemon runs jobs, it
        does not hand a human a terminal). §2's rule is enforced here, where
        every caller of the API meets it: never resume a session whose job is
        still running.
        """
        record = self._job(job)
        if record.state == "running":
            raise ApiError(
                f"job {record.id} is still running; §2 forbids resuming its session. "
                f"Watch it with `hands log -f {record.role}`, or "
                f"`hands cancel {record.id}` first"
            )
        if not record.session_id:
            raise ApiError(
                f"job {record.id} is {record.state} and has no session id; "
                "there is nothing to resume"
            )
        live = self._running_with_session(record.session_id, exclude=record.id)
        if live is not None:
            raise ApiError(
                f"job {live} is running in the same session ({record.session_id}); "
                f"§2 forbids resuming it. Watch it with `hands log -f {record.role}`"
            )
        try:
            role_config = self.config.role(record.role)
        except KeyError as exc:
            raise ApiError(str(exc)) from exc
        # §7 spells this invocation out in full: `claude --resume <session_id>`.
        # Nothing else is added — this is the human's own interactive session,
        # and the headless flags of §2 are the runner's, not theirs.
        argv = [self.config.runner.claude, "--resume", record.session_id]
        return {
            "job": record.id,
            "role": record.role,
            "state": record.state,
            "session_id": record.session_id,
            "cwd": str(role_config.cwd),
            "argv": argv,
            "command": shlex.join(argv),
        }

    def _running_with_session(self, session_id: str, *, exclude: str) -> str | None:
        """The id of another job that is `running` in this session, if there is one (§2)."""
        for other in self.spool.list_jobs():
            if other.id != exclude and other.state == "running" and other.session_id == session_id:
                return other.id
        return None

    async def log(
        self, *, job: str | None = None, role: str | None = None, offset: int = 0
    ) -> dict[str, Any]:
        """The captured stream of a job, from `offset` bytes on (§7).

        The lines are the `--output-format stream-json` lines of §2, verbatim:
        hands captured them, it does not re-render them. `offset` is what makes
        `hands log -f` a follow rather than a re-print — the CLI asks again from
        where the last answer ended — and a half-written trailing line is never
        returned, so a follower never sees a fragment of an event.
        """
        if role is not None and job:
            raise ApiError(f"hands log takes a job id or -f <role>, not both (got {job!r})")
        record = self._role_job(role) if role is not None else self._log_job(job)
        path = self.spool.jobs_dir / f"{record.id}.stream.jsonl"
        lines, end = _read_from(path, offset)
        return {
            "job": record.id,
            "role": record.role,
            "state": record.state,
            "running": record.state not in TERMINAL_STATES,
            "path": str(path),
            "exists": path.exists(),
            "offset": end,
            "lines": lines,
        }

    def _log_job(self, job: str | None) -> Job:
        if not job:
            raise ApiError("hands log needs a job id, or -f <role> to follow a running one (§7)")
        return self._job(job)

    def _role_job(self, role: str) -> Job:
        """The job `hands log -f <role>` follows: the one running now (§7)."""
        if role not in self.config.roles:
            known = ", ".join(sorted(self.config.roles))
            raise ApiError(f"unknown role {role!r}; this project configures: {known}")
        running = self.daemon.running_job_id(role)
        if running is None:
            last = self._last_job(role)
            hint = f"; its last job was {last.id} (`hands log {last.id}`)" if last else ""
            raise ApiError(f"role {role} has no running job to follow{hint}")
        return self._job(running)

    def _last_job(self, role: str, *, with_transcript: bool = False) -> Job | None:
        for record in reversed(self.spool.list_jobs()):
            if record.role != role:
                continue
            if with_transcript and not record.transcript_path:
                continue
            return record
        return None

    async def tail(self, *, role: str, n: int = 20) -> dict[str, Any]:
        """The last `n` entries of the role's current or last transcript (§4).

        The file is Claude Code's own (§7: "Transcripts are Claude Code's own
        files under `~/.claude/projects/`; hands stores their paths"), so the
        lines come back verbatim and unparsed — hands does not own that format
        and will not pretend to.
        """
        if role not in self.config.roles:
            known = ", ".join(sorted(self.config.roles))
            raise ApiError(f"unknown role {role!r}; this project configures: {known}")
        record = self._last_job(role, with_transcript=True)
        if record is None or not record.transcript_path:
            raise ApiError(
                f"role {role} has no session with a transcript yet; "
                f"`hands jobs --role {role}` shows what it has run"
            )
        path = Path(record.transcript_path).expanduser()
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            raise ApiError(
                f"cannot read the transcript of job {record.id} at {path}: {exc}. "
                "Claude Code writes that file, not hands, and only for a session "
                "that really ran on this machine"
            ) from exc
        entries = [line for line in text.splitlines() if line.strip()]
        return {
            "role": role,
            "job": record.id,
            "state": record.state,
            "session_id": record.session_id,
            "path": str(path),
            "entries": entries[-n:] if n else entries,
        }

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
            await self.daemon.playbook.on_event("job.denied", job=out)  # §10
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

    # --------------------------------------------------- the pipeline (§10)

    async def pipeline(self) -> dict[str, Any]:
        """The active playbook, paused?, auto-runs, resumes, last rule, stop reason (§4)."""
        return self.daemon.playbook.pipeline()

    async def pause(self) -> dict[str, Any]:
        """Pause the playbook engine: no rule fires until it is resumed (§4, §10).

        Over an already-stopped pipeline it is a no-op that keeps the first stop
        reason and answers `already_stopped: true` (§19).
        """
        return await self.daemon.playbook.pause()

    async def resume(self) -> dict[str, Any]:
        """Un-pause the playbook engine and clear the stop reason (§4, §10)."""
        return await self.daemon.playbook.resume()

    # ---------------------------------------------------------- notify (§4)

    async def notify(self, *, test: str | None = None) -> dict[str, Any]:
        """Send one test message to the configured ntfy topic (§4, §11).

        `hands notify --test` does this in the *client*, so that it works at an
        install with no daemon yet; this method is the other half of the same
        surface (§9), for a caller that has only the daemon — and it sends
        through the daemon's own transport, so a test that replaced it sees this
        message too. Quiet hours are not consulted here either: §11 delays
        notifications, never actions.
        """
        if test is None:
            raise ApiError('notify takes --test "<message>": it has no other mode (§4)')
        try:
            return await send_test(self.config, test, post=self.daemon.notifier.post)
        except NotifyError as exc:
            raise ApiError(str(exc)) from exc

    # ---------------------------------------------------------- doctor (§4)

    async def doctor(self, *, live: bool = False) -> dict[str, Any]:
        """The install check (§4, §11, §14), for a caller that has a daemon.

        `hands doctor` runs the same checks in the *client*, because §14 step 1
        runs it before handsd exists. This method is the other half of the same
        surface (§9): it is the daemon describing its own install, so the daemon
        check needs no socket round-trip to itself. The checks shell out, so they
        run in a thread — the queue must keep moving while doctor probes.
        """
        found = await asyncio.to_thread(
            doctor_checks,
            self.config,
            live=live,
            daemon={
                "version": __version__,
                "pid": os.getpid(),
                "socket": str(self.daemon.socket_path),
            },
        )
        return doctor_report(self.config, found, live=live)

    # -------------------------------------------------------------- internals

    def _job(self, job_id: str) -> Job:
        try:
            return self.spool.load_job(job_id)
        except SpoolError as exc:
            raise ApiError(str(exc)) from exc



def _since_cutoff(since: str | None) -> str | None:
    """`--since 30m|6h|2d|1w` or `--since 2026-09-01` → an ISO cutoff (§4, §7).

    A form hands cannot read is refused rather than guessed at: `created` is
    compared lexically, so an unreadable word would silently sort above every
    real timestamp and quietly answer "no jobs".
    """
    if since is None:
        return None
    text = since.strip()
    match = _SINCE_RE.match(text)
    if match is not None:
        amount, unit = int(match.group(1)), match.group(2)
        delta = {
            "s": timedelta(seconds=amount),
            "m": timedelta(minutes=amount),
            "h": timedelta(hours=amount),
            "d": timedelta(days=amount),
            "w": timedelta(weeks=amount),
        }[unit]
        return (datetime.now(UTC) - delta).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    if _ISO_SINCE_RE.match(text):
        return text.replace(" ", "T")
    raise ApiError(
        f"--since {since!r} is not a time hands can read; give an age (30s, 30m, "
        "6h, 2d, 1w) or a date (2026-09-01)"
    )


def _read_from(path: Path, offset: int) -> tuple[list[str], int]:
    """The complete lines of `path` after `offset` bytes, and where they end (§7).

    A trailing partial line is left for the next read: the daemon appends to this
    file while the job runs, so a follower that took one would print half an event
    and then its other half.
    """
    start = max(0, int(offset))
    try:
        with path.open("rb") as handle:
            handle.seek(start)
            raw = handle.read()
    except FileNotFoundError:
        return [], start
    except OSError as exc:  # pragma: no cover - unreadable spool file
        raise ApiError(f"cannot read {path}: {exc}") from exc
    cut = raw.rfind(b"\n") + 1
    if cut == 0:
        return [], start
    return raw[:cut].decode("utf-8", errors="replace").splitlines(), start + cut
