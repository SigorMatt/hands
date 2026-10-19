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
import base64
import binascii
import contextlib
import hashlib
import os
import re
import shlex
import shutil
import subprocess
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

from hands import __version__, files, gates
from hands.config import ARCHITECT_ROLE, CONSULT_ROLES
from hands.doctor import report as doctor_report
from hands.doctor import run_checks as doctor_checks
from hands.kit import (
    KIT_NAME_RE,
    Apply,
    KitError,
    Report,
    apply_from_zip,
    apply_params,
    check_kit,
    home_shown,
    is_consult_file_name,
    is_kit_file_name,
    kit_directory,
    place_kit,
    read_staged,
    remove_staged,
    staged_path,
)
from hands.notify import NotifyError, send_test
from hands.playbook import (
    ConsultRefused,
    PlaybookError,
    ResumeRefused,
    load_playbook,
    playbook_path,
    sent_prompt,
)
from hands.runner import MAX_PROMPT_BYTES, KeepRefused
from hands.spool import (
    ANSWER_ORIGIN,
    ARCHITECT_ORIGIN,
    KIT_CHECK_PASSED,
    ORIGINS,
    REPLY_ORIGIN,
    TERMINAL_STATES,
    Event,
    Job,
    Spool,
    SpoolError,
    is_architect_reply,
    kit_apply_problem,
    kits_filed_during,
    new_kit_id,
    resolve_kinds,
)

#: §31: the origin of the jobs the engine files, a consultation among them.
ORIGIN_PLAYBOOK = "playbook"
#: §27, §40: the origin of a kit's held apply filed from the phone's `kit` or from
#: `hands kit apply`.
KIT_ORIGIN = "kit"

if TYPE_CHECKING:  # pragma: no cover - import cycle only matters to type checkers
    from hands.daemon import Daemon

__all__ = [
    "LOG_PAGE_BYTES",
    "MAX_TAIL_ENTRIES",
    "TAIL_WINDOW_BYTES",
    "Api",
    "ApiError",
    "Timeout",
    "CONSULT_FILE_MAX_BYTES",
    "attachment_sentence",
    "consult_file_problem",
    "consult_file_text",
    "consult_reason",
    "job_summary",
    "match_job_id",
    "tail_entries",
]

#: §21: `tail` must not read a whole transcript into the daemon. A 60-turn
#: mission's transcript ran to hundreds of megabytes, and every `hands tail`
#: poll used to copy all of it; these two bounds are what the daemon holds
#: instead, whatever the file grows to. 4 MiB is the window read back from the
#: end of the file — comfortably more than a thousand ordinary entries, so the
#: answer to `-n 20` is unchanged — and 1000 is the most entries any one answer
#: carries, because `tail` is a peek at the end of a session and a caller that
#: wants the session reads the transcript itself (§7: it is Claude Code's file).
TAIL_WINDOW_BYTES = 4 * 1024 * 1024
MAX_TAIL_ENTRIES = 1000

#: §4's `log` row: "delivered in pages so a whole transcript is never one
#: message (H-013)". One answer carries at most this many bytes of *complete*
#: lines — and, when a single line is wider than that, exactly that one line,
#: because a line is the unit hands captured and half of one is not an event.
#: The caller continues from the `offset` the answer ends at; the CLI's human
#: route loops over the pages itself, so `hands log <job>` still prints the
#: whole stream (§7).
LOG_PAGE_BYTES = 256 * 1024
#: How much of the window is read per seek. The file is being read backwards,
#: so it is read in blocks and joined once, never re-copied per block.
_TAIL_CHUNK = 64 * 1024

# JSON-RPC 2.0 reserves -32768..-32000 for the protocol; -32000..-32099 is the
# implementation-defined server-error range, which is where these live.
HANDS_ERROR = -32001  # a refusal hands is sure about (bad role, full queue, …)
TIMEOUT = -32003  # `wait --timeout` expired


#: §42: the most bytes the file a `consult` carries may hold (256 KiB).
CONSULT_FILE_MAX_BYTES = 256 * 1024

#: §42 "The decisions kit": `kit_file`'s refusal of one. The architect role files
#: kits; an owner file is the human's, sent by the phone's `kit` or `hands kit apply`.
DECISIONS_REFUSAL = (
    "kit_file: kit {name!r} is a decisions kit (§42): an owner file is the human's "
    "word, and one the architect role filed would be listed to the next consultation "
    "as decided by the human and carried out by the brief's §R; nothing is filed — "
    "the human sends a decisions kit by the phone's `kit` or `hands kit apply`"
)


def consult_file_problem(name: object, size: object, what: str) -> str | None:
    """§42: why the file a `consult` carries is refused by its name or its size —
    `what` names it in the reason (`the attachment`, `--file <path>`) — or None.
    The name rule is `hands.kit.is_consult_file_name`; the size at most
    `CONSULT_FILE_MAX_BYTES`. The phone asks with the size the attachment reports,
    before it fetches; the CLI with the size of the file it names."""
    if not is_consult_file_name(name):
        return f"{what} is not a .md basename (§42)"
    if isinstance(size, bool) or not isinstance(size, int) or size < 0:
        return f"{what} reports no size in bytes"
    if size > CONSULT_FILE_MAX_BYTES:
        return f"{what} is {size} bytes, over the {CONSULT_FILE_MAX_BYTES}-byte cap of §42"
    return None


def consult_file_text(data: bytes, what: str) -> str:
    """§42: the file a `consult` carries, "read as UTF-8"; `ValueError` naming
    `what` when it is not."""
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{what} is not UTF-8 text (§42)") from exc


def consult_reason(text: str, attached: str | None) -> str:
    """§42: the human's reason — the text, and the attached file's text after it,
    separated by one blank line; either alone when the other is empty. Verbatim:
    nothing is stripped from either."""
    parts = [part for part in (text, attached) if part is not None and part.strip()]
    return "\n\n".join(parts)


def attachment_sentence(path: Path) -> str:
    """§36: the one sentence an `answer`'s delivered text ends with when the message
    carried a file — its path where handsd wrote it, absolute, so the builder can read
    it whatever its cwd."""
    return f"The human attached a file to this answer; it is at {path}."


def _check_refusal(name: str, repo: Path, report: Report, *, method: str = "kit_file") -> str:
    """§33: `kit_file`'s refusal of a kit that fails the check — the check's own lines.
    §40: `kit_apply`'s too."""
    failed = [check.name for check in report.checks if not check.ok]
    lines = "\n".join(check.line() for check in report.checks)
    return (
        f"{method}: kit {name!r} fails `hands kit check` against the builder's repository "
        f"{repo} ({', '.join(failed)}), so handsd did not file it (§33):\n{lines}"
    )


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
#: §26's `kit_max_mb` is in MiB.
_MIB = 1024 * 1024


def job_summary(job: Job) -> dict[str, Any]:
    """The short form of a job record, for `jobs` and `status` (§4). §43: its prompt
    line is the sender's, read without hands' leading sentences (`sent_prompt`)."""
    out: dict[str, Any] = {name: getattr(job, name) for name in _SUMMARY_FIELDS}
    sent = sent_prompt(job.prompt)
    first = sent.splitlines()[0] if sent else ""
    out["prompt_line"] = first[:_PROMPT_LINE_CHARS]
    return out


#: §39 (H-059): the shortest prefix of a job id `match_job_id` accepts.
MIN_ID_PREFIX = 4
#: §39 (H-059): what a human reads one character as: `O` as `0`, `l` and `I` as `1`
#: (after lower-casing, so `i`, `l` and `o`).
_ID_LOOKALIKES = str.maketrans({"o": "0", "l": "1", "i": "1"})


def _id_key(text: str) -> str:
    return text.lower().translate(_ID_LOOKALIKES)


def match_job_id(spool: Spool, typed: str) -> str:
    """§39 (H-059): the id of the one job `typed` names, or `ApiError` saying why not.

    An exact id wins. Otherwise both sides are compared case-insensitively with `O`
    read as `0` and `l` or `I` as `1` — a whole id, else a prefix of `MIN_ID_PREFIX`
    or more characters. Two or more jobs matching is refused with the candidates.
    Used by `approve`, `deny` and `cancel` (laptop and phone alike); the phone's
    `answer` and `reply` carry no job id.

    The typed id is quoted with `str`, never `repr`: the phone cuts its secret out
    of the reason, and `repr` doubles a backslash in it (REVIEW-23 should-fix 5)."""
    with contextlib.suppress(SpoolError):
        return spool.load_job(typed).id
    key = _id_key(typed.strip())
    ids = sorted(
        path.stem for path in spool.jobs_dir.glob("*.json") if not path.name.startswith(".")
    )
    whole = [job_id for job_id in ids if _id_key(job_id) == key]
    if len(whole) == 1:
        return whole[0]
    if not whole and len(key) >= MIN_ID_PREFIX:
        whole = [job_id for job_id in ids if _id_key(job_id).startswith(key)]
        if len(whole) == 1:
            return whole[0]
    if whole:
        raise ApiError(f"job id `{typed}` is ambiguous: it matches {', '.join(whole)}")
    short = (
        f" (a prefix needs {MIN_ID_PREFIX} or more characters)"
        if 0 < len(key) < MIN_ID_PREFIX else ""
    )
    raise ApiError(f"no such job `{typed}`{short}")


class Api:
    """Every command of §4, bound to one running daemon."""

    #: The command surface of §4, in the order §4 lists it. `hands --help` and
    #: the MCP face of §9 both read this, so the two can never drift apart.
    COMMANDS: tuple[str, ...] = (
        "send", "wait", "result", "jobs", "show", "open", "log", "cancel",
        "put", "get", "ls", "tail", "inbox", "pipeline", "approve", "deny",
        "pause", "resume", "status", "notify", "who", "doctor",
    )  # fmt: skip

    def __init__(self, daemon: Daemon) -> None:
        self.daemon = daemon
        self.config = daemon.config
        self.spool = daemon.spool
        #: §34: `kit_file` is serialized per consultation: architect job id → its lock.
        #: One lock per consultation, kept for the daemon's life (a lock is dropped
        #: only by a restart, which ends every consultation).
        self._kit_locks: dict[str, asyncio.Lock] = {}

    #: §31, §32: the daemon half of `hands kit file`. `kit` is one row of §4's table
    #: and its `check` is answered by the client, so this is not in `COMMANDS` (which
    #: §4 pins); `method()` answers it as well, because the apply and its `kit_id`
    #: are the daemon's to create. §40: `kit_apply` is the daemon half of `hands kit
    #: apply <zip>`, the phone's kit path without the phone.
    KIT_METHODS: tuple[str, ...] = ("kit_file", "kit_apply")

    #: §40: "every phone command has a laptop form" — the commands that were
    #: phone-only and gained one in mission 24. Not rows of §4's table, so not in
    #: `COMMANDS`; `method()` answers them.
    #: §42: `consult` joins them — `hands consult`, the phone's `consult` at the laptop.
    OPERATIONS: tuple[str, ...] = ("go", "consult")

    def method(self, name: str) -> Any:
        """The bound coroutine for a command name, or None if there is no such command."""
        if (
            name not in self.COMMANDS
            and name not in self.KIT_METHODS
            and name not in self.OPERATIONS
        ):
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
        """Queue a prompt for a role (§4, §6). Returns the job record.

        No `kit_id` parameter: that id is minted by handsd for an apply it files
        itself (`file_apply`, §32), so no socket client can put one on a job. And
        no `origin: architect`: §32, "a socket client cannot set `origin:
        architect`" — only `kit_file` files an architect-origin job. Nor `origin:
        phone`: §37, only the daemon's own phone channel sets it (`answer_builder`,
        `reply_architect`, `kickoff`), so a raw send cannot be published as the
        builder's answer or listed to the architect as a human decision.

        A cli send to the builder gets §39's journal sentence (H-060) when it is
        dispatched, not here (review 23 should-fix 6): `Daemon._run`.
        """
        if origin == ARCHITECT_ORIGIN:
            raise ApiError(
                f"origin {ARCHITECT_ORIGIN!r} is handsd's own: it marks the apply handsd files "
                "for a kit the architect role filed with `hands kit file`, and a socket client "
                "cannot set it (§32)"
            )
        if origin == ANSWER_ORIGIN:
            raise ApiError(
                f"origin {ANSWER_ORIGIN!r} is handsd's own: the phone's `answer <secret> "
                "<text>` is the only path that files a builder answer of that origin (the "
                "phone's `reply` and `go` are handsd's too), and a socket client cannot set "
                "it (§37)"
            )
        return await self._send(
            role=role,
            context=context,
            prompt=prompt,
            file=file,
            gate=gate,
            origin=origin,
            playbook_sha256=playbook_sha256,
        )

    async def _send(
        self,
        *,
        role: str,
        context: str,
        prompt: str,
        file: list[str] | None = None,
        gate: str | None = None,
        origin: str = "cli",
        playbook_sha256: str | None = None,
        kit_id: str | None = None,
        reply: bool = False,
        ungated: bool = False,
        attached: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        if role not in self.config.roles:
            known = ", ".join(sorted(self.config.roles))
            raise ApiError(f"unknown role {role!r}; this project configures: {known}")
        # §33: `reply` is `reply_architect`'s, which no socket client reaches.
        if role in CONSULT_ROLES and not (reply and role == ARCHITECT_ROLE):
            # §27: the driver role is "started by `handsd` only through a `consult`
            # action" — not by a send from the CLI, the phone or a playbook rule.
            # H-032, §32: so is the architect, "started by `consult` only".
            raise ApiError(
                f"the {role} role is started by handsd only through a playbook `consult` "
                f"action (§27, §32); `hands send --role {role}` is refused"
            )
        if context not in ("clear", "keep"):
            raise ApiError(f"--context must be clear or keep, got {context!r}")
        if not prompt.strip():
            raise ApiError("refusing to send an empty prompt")

        # §8: "gating on the default patterns cannot be disabled" — `config.py`
        # keeps the defaults in `gates.patterns` whatever the project says.
        # §36: an `answer` is the one send that is never gated: "the secret is the
        # approval" (`ungated`, which only `answer_builder` passes).
        reason = (
            None
            if ungated
            else gates.gate_reason(prompt, explicit=gate, patterns=self.config.gates.patterns)
        )

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
        written = self._write_files(file or []) + list(attached or [])

        job = self.daemon.enqueue(
            role=role,
            context=context,
            prompt=prompt,
            origin=origin,
            gate=gates.new_gate(kind="send", reason=reason) if reason else None,
            files_written=written,
            playbook_sha256=playbook_sha256,
            kit_id=kit_id,
        )
        # §10's stop → resume cycle is not closed here: a `cli` send un-pauses the
        # pipeline when its job *starts* (`PlaybookEngine.on_job_start`), because a
        # send that is held at §8's gate or waiting in the queue has not yet
        # answered the stop.
        if reason:
            # §36 (H-045): the hold of a kit the role filed, under `autonomous`, is
            # decided by the engine before anything is published.
            self.daemon.playbook.defer_hold(job)
            self.spool.append_event(
                "job.held",
                {"job": job.id, "role": role, "state": "held", "reason": reason, "gate": "send"},
            )
            # §10 lists `job.held`: a job waiting for a human is the pipeline's
            # business, and with no rule for it the pipeline stops.
            await self.daemon.playbook.on_event("job.held", job=job)
        return job.to_dict()

    async def reply_architect(self, text: str) -> dict[str, Any]:
        """§33: the phone's `reply <secret> <text>`, "delivered as `hands send --role
        architect --context keep` to the architect's last session". Returns the job.

        The one send to the architect role (H-032: `send` refuses it to every socket
        client, and this method is in neither `COMMANDS` nor `KIT_METHODS`, so the
        phone channel is its only caller). It takes `send`'s own path — §8's gate
        patterns, `keep`'s session check — with `origin: phone` and `text` as the
        prompt, unchanged. Refused, filing nothing:

        - when this project configures no `[roles.architect]` (the series' `[series]
          architect` mode is not read: a session exists only where the role ran);
        - while an architect job is running, queued or held — a consultation or an
          earlier reply: one job per turn;
        - while the engine waits for the kit a consultation's `VERDICT: next kit
          <name>` named (§32), which is still that consultation;
        - when the role has recorded no session.

        Nothing is awaited between these checks and the enqueue.
        """
        if ARCHITECT_ROLE not in self.config.roles:
            raise ApiError(
                "this project configures no [roles.architect], so there is no architect "
                "to reply to (§31, §33)"
            )
        running = self.daemon.running(ARCHITECT_ROLE)
        if running is not None:
            try:
                consulting = self.spool.load_job(running).origin == ORIGIN_PLAYBOOK
            except SpoolError:
                consulting = False
            if consulting:
                raise ApiError(f"an architect consultation is running (job {running}) (§33)")
            raise ApiError(f"the architect has a job running ({running}) (§33)")
        queued = self.daemon.status()["roles"][ARCHITECT_ROLE]["queued"]
        if queued:
            raise ApiError(f"the architect has a job queued ({', '.join(queued)}) (§33)")
        held = [job.id for job in self.spool.list_jobs()
                if job.role == ARCHITECT_ROLE and job.state == "held"]
        if held:
            raise ApiError(f"the architect has a job held ({', '.join(held)}) (§33)")
        waiting = self.daemon.playbook.kit_wait()
        if waiting is not None:
            consultation, name = waiting
            raise ApiError(
                f"the engine waits for kit {name!r} of consultation {consultation} "
                "([series] kit_wait_s), and the consultation is open until it ends (§32, §33)"
            )
        if not self.spool.read_role(ARCHITECT_ROLE).last_session_id:
            raise ApiError(
                "the architect has no session to reply to: no architect job has recorded "
                "one (§33)"
            )
        return await self._send(
            role=ARCHITECT_ROLE, context="keep", prompt=text, origin=REPLY_ORIGIN, reply=True
        )

    async def go(self) -> dict[str, Any]:
        """§40: `hands go` — the phone's `go` from the laptop, with `origin: cli`.

        The same code the phone's `go` runs (`kickoff`), so the refusals are the
        phone's: while a builder job is running, queued or held, with no playbook,
        and with no `[series] kickoff`."""
        return await self.kickoff("cli")

    async def kickoff(self, origin: str) -> dict[str, Any]:
        """§26, §27, §40: the playbook's `[series] kickoff` line to the builder, one
        `clear` job of `origin` — `phone` for the phone's `go`, `cli` for `hands go`.
        Returns the job; refuses with `ApiError`, whose text is the reason.

        Refused while the builder has a job running, queued or held (§27). The
        builder is checked first, with nothing awaited before it, and again after
        the playbook is read: the read runs in a thread, and a `hands send` can land
        meanwhile (review 10 should-fix 1). `_send` awaits nothing before its
        enqueue, so the second check and the job it allows are one step of the event
        loop. The playbook is read from the builder's cwd now, by the same loader the
        engine uses (only the committed file loads, §10) — not taken from the
        engine's last load, which happens only when a job starts — and a read never
        files a stop. Gated by §8 as `send` is. Not reachable with `origin: phone`
        from a socket client: `go` is the socket's method and passes `cli` (§37).
        """
        # §44 rule 3: only `resume` ends a human pause; `go` is refused under one.
        paused = self.daemon.playbook.human_pause_refusal("go")
        if paused is not None:
            raise ApiError(paused)
        busy = self.builder_busy()
        if busy is not None:
            raise ApiError(busy)
        try:
            book = await asyncio.to_thread(
                load_playbook, playbook_path(self.config), cwd=self.config.role("builder").cwd
            )
        except PlaybookError as exc:
            raise ApiError(f"no playbook is loaded: it cannot be loaded ({exc})") from exc
        if book is None:
            raise ApiError("no playbook is loaded")
        if book.kickoff is None:
            raise ApiError("the playbook has no [series] kickoff")
        busy = self.builder_busy()
        if busy is not None:
            raise ApiError(busy)
        try:
            return await self._send(
                role="builder", context="clear", prompt=book.kickoff, origin=origin
            )
        except ApiError as exc:
            raise ApiError(f"the send was refused ({exc})") from exc

    # ---------------------------------------------------------- consult (§42)

    async def consult(self, *, reason: str) -> dict[str, Any]:
        """§42: `hands consult [--file <path>] [<text>]` — the phone's `consult` at the
        laptop, through the socket, `requested_by: cli`. The client reads the file
        under the name and size rules and sends the reason it makes
        (`consult_reason`); the refusals are the phone's. Returns the job."""
        return await self.start_consult(reason, requested_by="cli")

    async def consult_refusal(self, reason: str | None) -> str | None:
        """§42: why a consultation the human asks for is refused now, or None.

        Every refusal that needs no playbook is asked first: an architect job is
        running, queued or held, or a consultation's `next kit` wait is open; a
        builder or aux job is running, queued or held; the reason is empty
        (`reason=None` skips this one: the phone asks before it fetches the
        attachment, which may carry the whole reason). Only a command none of these
        refuses loads the committed playbook, as a job's start loads it (§10) — so a
        refused consult never stops the pipeline on a playbook that does not load,
        nor swaps the playbook or clears `last_rule` under a running job (PR #6
        hosted review finding 6). Then: the playbook in force does not set `[series]
        architect = "role"`, or the project configures no `[roles.architect]`; the
        budget is spent. Nothing is awaited after the load, so `start_consult`'s
        enqueue follows these checks in one step of the event loop."""
        engine = self.daemon.playbook
        # §44 rule 3: only `resume` ends a human pause; `consult` is refused under one.
        paused = engine.human_pause_refusal("consult")
        if paused is not None:
            return paused
        if ARCHITECT_ROLE in self.config.roles:
            why = self._role_busy(ARCHITECT_ROLE)
            if why is not None:
                return why
        waiting = engine.kit_wait()
        if waiting is not None:
            consultation, name = waiting
            return (
                f"the engine waits for kit {name!r} of consultation {consultation} "
                "([series] kit_wait_s), and the consultation is open until it ends (§32, §42)"
            )
        for role in ("builder", "aux"):
            if role in self.config.roles:
                why = self._role_busy(role)
                if why is not None:
                    return f"{why}: a consultation decides what a stopped series does next"
        if reason is not None and not reason.strip():
            return "the reason is empty (§42)"
        await engine.reload()
        why = engine.consult_mode_refusal()
        if why is not None:
            return why
        return engine.consult_budget_refusal()

    async def start_consult(self, reason: str, *, requested_by: str) -> dict[str, Any]:
        """§42: the one path both routes take — the phone's `consult` (`requested_by:
        phone`) and `hands consult` (`cli`). Every refusal is `consult_refusal`'s or
        the engine's (`ConsultRefused`: the prompt over `MAX_PROMPT_BYTES`), as
        `ApiError`; then the engine un-pauses a stopped pipeline and starts the
        architect job (`PlaybookEngine.consult_human`). Not reachable from a socket
        client but as `consult`, which passes `cli`."""
        why = await self.consult_refusal(reason)
        if why is not None:
            raise ApiError(why)
        try:
            job = await self.daemon.playbook.consult_human(
                reason, requested_by=requested_by, cap=MAX_PROMPT_BYTES
            )
        except ConsultRefused as exc:
            raise ApiError(str(exc)) from exc
        return job.to_dict()

    def _role_busy(self, role: str) -> str | None:
        """Why `role` has work now — a job running, queued or held — or None."""
        running = self.daemon.running(role)
        if running is not None:
            return f"the {role} has a job running ({running})"
        queued = self.daemon.status()["roles"][role]["queued"]
        if queued:
            return f"the {role} has a job queued ({', '.join(queued)})"
        held = [job.id for job in self.spool.list_jobs()
                if job.role == role and job.state == "held"]
        if held:
            return f"the {role} has a job held ({', '.join(held)})"
        return None

    def builder_busy(self) -> str | None:
        """Why the builder cannot take a `go` now — a job running, queued or held — or None."""
        builder = self.daemon.status()["roles"]["builder"]
        if builder["running"]:
            return f"the builder has a job running ({builder['running']['id']})"
        if builder["queued"]:
            return f"the builder has a job queued ({', '.join(builder['queued'])})"
        held = [
            job.id
            for job in self.spool.list_jobs()
            if job.role == "builder" and job.state == "held"
        ]
        if held:
            return f"the builder has a job held ({', '.join(held)})"
        return None

    def answer_refusal(self, text: str) -> str | None:
        """§36: why an `answer` to the builder is refused now, or None.

        Refused when the text is empty (whitespace only is empty), while the builder
        has a job running, queued or held, and when it has no resumable session
        (`--context keep`'s own check, §6). The phone asks before it fetches an
        attachment, and `answer_builder` asks again next to its enqueue.
        """
        if not text.strip():
            return "the text is empty (§36)"
        builder = "builder"
        running = self.daemon.running(builder)
        if running is not None:
            return f"the builder has a job running ({running}) (§36)"
        queued = self.daemon.status()["roles"][builder]["queued"]
        if queued:
            return f"the builder has a job queued ({', '.join(queued)}) (§36)"
        held = [job.id for job in self.spool.list_jobs()
                if job.role == builder and job.state == "held"]
        if held:
            return f"the builder has a job held ({', '.join(held)}) (§36)"
        try:
            self.daemon.runner.resolve_resume_session(builder)
        except KeepRefused as exc:
            return f"the builder has no resumable session: {exc} (§36)"
        return None

    async def answer_builder(
        self, text: str, *, attachment: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """§36: the phone's `answer <secret> <text>`, "delivered as `hands send --role
        builder --context keep "<text>"` would be, to the builder's last session, one
        job of origin `phone`". Returns the job.

        Not held by §8's gate whatever the text says (`ungated`). `attachment`, when
        the message carried one the phone has written to `kit_dir`, is `{"path",
        "name", "sha256", "bytes"}`: the delivered text is `text`, a blank line and
        `attachment_sentence(path)`, and the path, sha256 and bytes go to the record's
        `files_written` (the record keeps the sha256). `answer.sent` files `text`, the
        attachment's name and its hash. Refusals are `answer_refusal`'s, decided with
        nothing awaited between them and the enqueue. §39's journal sentence is put
        before it when it is dispatched (`Daemon._run`). Not a command of §4 and in neither
        `COMMANDS` nor `KIT_METHODS`, so the phone channel is its only caller.
        """
        why = self.answer_refusal(text)
        if why is not None:
            raise ApiError(why)
        prompt, attached, filed = text, [], None
        if attachment is not None:
            prompt = f"{text}\n\n{attachment_sentence(Path(attachment['path']))}"
            attached = [{key: attachment[key] for key in ("path", "sha256", "bytes")}]
            filed = {"name": attachment["name"], "sha256": attachment["sha256"]}
        job = await self._send(
            role="builder",
            context="keep",
            prompt=prompt,
            origin=ANSWER_ORIGIN,
            ungated=True,
            attached=attached,
        )
        self.spool.append_event(
            "answer.sent", {"job": job["id"], "text": text, "attachment": filed}
        )
        return job

    async def file_apply(self, plan: Apply, origin: str, kit_id: str) -> dict[str, Any]:
        """§27, §31, §32: a kit's held apply, filed by handsd itself.

        The one path both routes take — the phone's `kit` (origin `kit`) and `hands
        kit file` (origin `architect`) — so the job is `apply_params`' and carries
        the `kit_id` handsd minted. Not a command of §4 and in neither `COMMANDS`
        nor `KIT_METHODS`, so no socket client reaches it.
        """
        return await self._send(**apply_params(plan, origin), kit_id=kit_id)

    async def kit_file(self, *, name: str, zip: str) -> dict[str, Any]:
        """§32: the daemon half of `hands kit file <dir>`. Returns the job record.

        `name` is the kit directory's name and `zip` the base64 of the zip the
        client built from that directory and checked against the role's clone.
        handsd mints the `kit_id` and stores the bytes at
        `<spool>/kits/<kit_id>/<name>.zip`. §33: it then runs `check_kit` on those
        stored bytes itself, against the builder's repository (its cwd) and this
        daemon's config, and refuses a failing kit with the check's output — the
        client's check is not trusted, since any socket client can call this. A
        passing kit gets the record `kit.json` naming the consultation and the
        passing check, is listed with the phone's `apply_from_zip` against the
        builder's cwd, and is filed as the held apply with `origin: architect`. A
        refusal files nothing and keeps nothing. §42: a decisions kit passes the
        check and is refused (`DECISIONS_REFUSAL`): an owner file is the human's.

        §34: calls are serialized per consultation under a lock, and a call that
        gets the lock after its consultation has filed a kit (`kits_filed_during`) is
        refused as "one kit per consultation" before it is stored or checked; the
        engine is told (`PlaybookEngine.kit_refused`), and §33's minimum follows from
        there: the consultation ends `escalate`. The kit's name against the
        architect's `VERDICT: next kit <name>` is the engine's to judge when it
        decides the hold, because the verdict usually arrives after the kit. A kit
        that fails the check files nothing, so a later call may file one.

        §34: the record holds the sha256 of the bytes handsd stored and ran the check
        on; the engine re-hashes the stored zip when it approves. §36 (review 18
        should-fix 3): that sha256 is the one `check_kit` computed over the very
        bytes it judged (read once), compared with the client's; a mismatch refuses
        the filing.

        §32: the engine approves "a kit filed by the architect role", so a kit is
        accepted only during an architect consultation — while an architect job is
        running (`Daemon.running`), or while the engine waits for the kit that
        consultation's `VERDICT: next kit <name>` named (`PlaybookEngine.kit_wait`),
        and then only under that name — and the record links the kit to it. What
        this cannot tell apart is a same-user process calling the socket during a
        consultation from the architect's own `hands kit file`.
        """
        if not isinstance(name, str) or not KIT_NAME_RE.fullmatch(name):
            raise ApiError(f"kit_file: the kit name must match {KIT_NAME_RE.pattern}")
        if not isinstance(zip, str):
            raise ApiError("kit_file: the zip is base64 text")
        try:
            data = base64.b64decode(zip, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ApiError("kit_file: the zip is not valid base64") from exc
        cap = self.config.files.kit_max_mb * _MIB
        if len(data) > cap:
            raise ApiError(
                f"kit_file: the zip is {len(data)} bytes, over [files] kit_max_mb = "
                f"{self.config.files.kit_max_mb} ({cap} bytes)"
            )
        if "builder" not in self.config.roles:
            raise ApiError("kit_file: this project configures no builder to apply a kit")
        consultation = self._consultation_for(name)
        async with self._kit_locks.setdefault(consultation, asyncio.Lock()):
            filed = kits_filed_during(self.spool, consultation)
            if filed:
                first, first_name = filed[0]
                await self.daemon.playbook.kit_refused(consultation)
                raise ApiError(
                    f"kit_file: one kit per consultation — consultation {consultation} has "
                    f"filed kit {first_name!r} (job {first.id}), so kit {name!r} is refused "
                    "before it is checked (§33, §34)"
                )
            if self._consultation_for(name) != consultation:
                raise ApiError(
                    f"kit_file: consultation {consultation} is no longer the one open while "
                    "this kit waited for the call before it (§32, §34)"
                )
            return await self._file_kit(consultation, name, data)

    async def _file_kit(self, consultation: str, name: str, data: bytes) -> dict[str, Any]:
        """`kit_file`'s store, check, record and apply, under its consultation's lock."""
        kit_id = new_kit_id()
        directory = self.spool.kit_dir(kit_id)
        try:
            path = await asyncio.to_thread(self.spool.store_kit, kit_id, name=name, data=data)
        except FileExistsError as exc:  # an existing directory: it is not this kit's
            raise ApiError(f"kit_file: the kit could not be stored ({type(exc).__name__})") from exc
        except OSError as exc:
            shutil.rmtree(directory, ignore_errors=True)
            raise ApiError(f"kit_file: the kit could not be stored ({type(exc).__name__})") from exc
        builder = self.config.role("builder").cwd
        try:
            report = await asyncio.to_thread(check_kit, path, builder, config=self.config)
            sent = hashlib.sha256(data).hexdigest()
            if report.sha256 != sent:
                # §36 (review 18 should-fix 3): what was checked is not what was sent.
                raise ApiError(
                    f"kit_file: the stored kit {name!r} changed under the check — the "
                    f"client sent sha256 {sent}, the check read sha256 {report.sha256}; "
                    "nothing is filed (§34, §36)"
                )
            if not report.ok:
                raise ApiError(_check_refusal(name, builder, report))
            if report.decisions:
                raise ApiError(DECISIONS_REFUSAL.format(name=name))
            plan = await asyncio.to_thread(apply_from_zip, path, builder, home_shown(path))
            await asyncio.to_thread(
                self.spool.record_kit,
                kit_id,
                name=name,
                consultation=consultation,
                check=KIT_CHECK_PASSED,
                sha256=report.sha256,
            )
            job = await self.file_apply(plan, ARCHITECT_ORIGIN, kit_id)
            self.daemon.playbook.kit_filed(consultation)
            return job
        except OSError as exc:
            shutil.rmtree(directory, ignore_errors=True)
            raise ApiError(f"kit_file: the kit could not be stored ({type(exc).__name__})") from exc
        except KitError as exc:
            shutil.rmtree(directory, ignore_errors=True)
            raise ApiError(f"kit_file: the apply was not filed: {exc}") from exc
        except ApiError:
            shutil.rmtree(directory, ignore_errors=True)
            raise

    async def kit_apply(self, *, name: str, staged: str) -> dict[str, Any]:
        """§40: the daemon half of `hands kit apply <zip>` — the phone's kit path
        without the phone. Returns `{"job", "zip", "copied", "sha256",
        "commit_message", "default_why"}`.

        `name` is the zip's file name (judged as the phone's `kit` judges one,
        `is_kit_file_name`) and `staged` the hidden basename the client wrote its
        bytes under in `[files] kit_dir` (`kit.staged_path`, `kit.stage_kit`): the
        bytes never travel over the socket, so a kit at `[files] kit_max_mb` fits
        the line room (PR #5 hosted review, finding 8). The staged file is read
        (`read_staged`: a regular file, not through a symlink, never blocking on a
        FIFO, at most kit_max_mb) and removed whatever follows, a refusal of the
        name, the builder or the file included (§41). The kit is checked as
        `hands kit check` checks it
        (`check_kit`, against the builder's cwd and this daemon's config, as
        `kit_file` does), on a copy under its own name in a scratch directory; a
        failing kit is refused with the check's output and nothing is copied or
        filed. A passing kit is copied into `[files] kit_dir` (inside `[files]
        allowed_roots`, as the phone requires) under its own name (`place_kit`):
        unless the same bytes are already there, and never over another file.
        Then, exactly as the phone's kit path after the fetch: `apply_from_zip` on
        the copied file, named `~/…` when it is under `$HOME`, and `file_apply`
        with `origin: kit` and a `kit_id` handsd mints — a held builder job, its
        hold published as any hold is, released by `hands approve`.
        """
        files_config = self.config.files
        cap = files_config.kit_max_mb * _MIB
        try:
            directory = kit_directory(files_config)
            source = staged_path(directory, staged)
        except KitError as exc:
            raise ApiError(f"kit_apply: {exc}") from exc
        # §41: from here every refusal removes the staged entry, so a caller other
        # than the CLI (which removes its own on every path) leaves nothing behind.
        try:
            if not is_kit_file_name(name):
                raise ApiError(
                    "kit_apply: the name must be a printable .zip basename not starting "
                    "with a dot (§26, §40)"
                )
            if "builder" not in self.config.roles:
                raise ApiError("kit_apply: this project configures no builder to apply a kit")
            try:
                data = await asyncio.to_thread(read_staged, source, cap)
            except KitError as exc:
                raise ApiError(f"kit_apply: {exc}") from exc
        finally:
            await asyncio.to_thread(remove_staged, source)
        builder = self.config.role("builder").cwd
        try:
            report = await asyncio.to_thread(self._check_bytes, name, data, builder)
            if not report.ok:
                raise ApiError(_check_refusal(name, builder, report, method="kit_apply"))
            copied = await asyncio.to_thread(place_kit, directory, name, data)
            path = directory / name
            shown = home_shown(path)
            plan = await asyncio.to_thread(apply_from_zip, path, builder, shown)
        except KitError as exc:
            raise ApiError(f"kit_apply: the apply was not filed: {exc}") from exc
        except OSError as exc:
            why = type(exc).__name__
            raise ApiError(f"kit_apply: the kit could not be written ({why})") from exc
        job = await self.file_apply(plan, KIT_ORIGIN, new_kit_id())
        return {
            "job": job,
            "zip": shown,
            "copied": copied,
            "sha256": report.sha256,
            "commit_message": plan.commit_message,
            "default_why": plan.default_why,
        }

    def _check_bytes(self, name: str, data: bytes, repo: Path) -> Report:
        """`check_kit` on `data`, written as `name` in a scratch directory."""
        with tempfile.TemporaryDirectory(prefix="hands-kit-apply-") as scratch:
            path = Path(scratch) / name
            path.write_bytes(data)
            return check_kit(path, repo, config=self.config)

    def _consultation_for(self, name: str) -> str:
        """§32: the architect consultation a kit named `name` is filed during, by job
        id, or `ApiError` when there is none open for it."""
        if ARCHITECT_ROLE not in self.config.roles:
            raise ApiError(
                "kit_file: this project configures no [roles.architect], and a kit is filed "
                "by the architect role during its consultation (§32)"
            )
        running = self.daemon.running(ARCHITECT_ROLE)
        if running is not None:
            # §33: a phone `reply` runs the architect too, and is not a consultation.
            try:
                replying = is_architect_reply(self.spool.load_job(running))
            except SpoolError:
                replying = False
            if replying:
                raise ApiError(
                    f"kit_file: architect job {running} is a reply from the phone, not a "
                    "consultation, and a kit is filed only during a consultation (§32, §33)"
                )
            return running
        waiting = self.daemon.playbook.kit_wait()
        if waiting is None:
            raise ApiError(
                "kit_file: no architect consultation is open — a kit is filed by the "
                "architect role while handsd runs its consultation, or while the engine "
                "waits for the kit its `VERDICT: next kit <name>` named ([series] "
                "kit_wait_s) (§32)"
            )
        consultation, expected = waiting
        if name != expected:
            raise ApiError(
                f"kit_file: the engine waits for kit {expected!r}, which the architect's "
                f"`VERDICT: next kit {expected}` named, not {name!r} (§32)"
            )
        return consultation

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

        `--for` blocks on a subscription, returns the event *unacked* (whoever
        waited acks it with `hands inbox --ack` once it has acted), and answers
        a timeout with a `Timeout` error, which the CLI turns into its own exit
        code so a wait that gave up can be told apart from a failure. §11
        retired the driver's standing wait, so the caller here is a human at the
        laptop or a short foreground wait after an approval (§12 rule 8).
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

        `origin` is §6's closed vocabulary (`driver|playbook|cli|limit|phone|kit`,
        v3.10, H-018), and a spelling outside it is refused rather than
        answered with "no jobs": every
        value is a filter that can legitimately match nothing, so silence would
        not tell a typo from an empty result.

        §7: "searching prompts is searching work items". `grep` is a
        case-insensitive substring of the *prompt* only — not of `result`: the
        prompt is the work item a human named ("run 3", "Batch 12"), while the
        result is the model's prose, and matching it would answer a search for a
        run with jobs that were never part of it. What a human wants out of the
        result — the verdict — is on every summary line already. §43: it searches
        the stored prompt as it is, hands' sentences included: what was delivered.
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
        """One page of the captured stream of a job, from `offset` bytes on (§4, §7).

        The lines are the `--output-format stream-json` lines of §2, verbatim:
        hands captured them, it does not re-render them. One answer carries at
        most `LOG_PAGE_BYTES` of them and says in `more` whether the file holds
        any further bytes, so a whole transcript is never one message (§4's
        `log` row, H-013); the caller continues from `offset`, which is also
        what makes `hands log -f` a follow rather than a re-print. A half-written
        trailing line is never returned, so neither a follower nor a pager sees a
        fragment of an event.
        """
        if role is not None and job:
            raise ApiError(f"hands log takes a job id or -f <role>, not both (got {job!r})")
        record = self._role_job(role) if role is not None else self._log_job(job)
        path = self.spool.stream_path(record.id)
        lines, end, more = _read_from(path, offset)
        return {
            "job": record.id,
            "role": record.role,
            "state": record.state,
            "running": record.state not in TERMINAL_STATES,
            "path": str(path),
            "exists": path.exists(),
            "offset": end,
            "more": more,
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

        Only the end of it is read: `n` is capped at `MAX_TAIL_ENTRIES` and the
        read at `TAIL_WINDOW_BYTES` from the end, so the daemon's resident size
        does not grow with the transcript (§21). §4 asks for `n >= 1` and for a
        `truncated` flag whenever either bound cut the answer short, so a caller
        is never told "these are the last n entries" when they are not.
        """
        if int(n) < 1:
            raise ApiError(f"hands tail takes -n 1 or more, not {n} (§4: n >= 1)")
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
            entries, truncated = tail_entries(path, n)
        except OSError as exc:
            raise ApiError(
                f"cannot read the transcript of job {record.id} at {path}: {exc}. "
                "Claude Code writes that file, not hands, and only for a session "
                "that really ran on this machine"
            ) from exc
        return {
            "role": role,
            "job": record.id,
            "state": record.state,
            "session_id": record.session_id,
            "path": str(path),
            "entries": entries,
            "truncated": truncated,
        }

    # ---------------------------------------------------------------- cancel

    async def cancel(self, *, job: str, reason: str | None = None) -> dict[str, Any]:
        """Stop a job: SIGINT then SIGTERM if running, drop it if queued (§2, §4).

        §4: "held for human unless `role.cancel_gated: false`". When the role
        gates its cancels the job is *not* touched — the request waits for a
        decision and the record comes back in the state it is still in, with the
        pending gate on it.
        """
        record = self._job(match_job_id(self.spool, job))  # §39: a lenient id
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
        decided_by = gates.decider_for(human_confirmed=human_confirmed)
        job = match_job_id(self.spool, job)  # §39 (H-059): a lenient id
        return await self._decide_as(job, decision, decided_by, reason=reason, quote=quote)

    async def decide_from_phone(
        self, job: str, decision: str, *, reason: str | None = None
    ) -> dict[str, Any]:
        """§24: a decision the ntfy command channel authenticated, `decided_by: phone`.

        Not a command of §4 and not in `COMMANDS`, so no socket client can reach
        it: `method()` answers None for any name outside that tuple. `hands.phone`
        is its only caller, and calls it only for a job that is `held`, after the
        command's token matched `cmd_secret` or that job's nonce.
        """
        return await self._decide_as(job, decision, "phone", reason=reason, quote=None)

    async def decide_from_playbook(self, job: str, *, reason: str | None = None) -> dict[str, Any]:
        """§31: the engine approving a held apply the architect role filed.

        Not a command of §4 and not in `COMMANDS`, so no socket client can reach
        it: `method()` answers None for any name outside that tuple. The playbook
        engine is its only caller, and it calls it only under a playbook that sets
        `[series] architect = "role"` and `autonomous = true`.

        The origin is checked here as well as there, because it is the half of the
        narrowness that does not depend on which file is in force: §31 gives this
        authority over applies the architect filed, and over nothing else. A kit
        from the phone, a human's own gated send and a gated cancel stay §8's.
        """
        record = self._job(job)
        if record.origin != ARCHITECT_ORIGIN:
            raise ApiError(
                f"job {record.id} is of origin {record.origin!r}: §31 gives the playbook "
                f"authority over a held apply of origin {ARCHITECT_ORIGIN!r} and nothing "
                "else; §8's table decides this one"
            )
        problem = kit_apply_problem(self.spool, record)
        if problem is not None:
            # §32: "never by origin alone".
            raise ApiError(
                f"job {record.id} is not an apply handsd filed from a kit the architect role "
                f"filed ({problem}): §32 gives the playbook no authority over it; §8's table "
                "decides this one"
            )
        if record.state != "held":
            raise ApiError(
                f"job {record.id} is {record.state}, not held; the playbook releases holds "
                "and never cancels"
            )
        return await self._decide_as(job, "approved", "playbook", reason=reason, quote=None)

    async def deny_from_playbook(self, job: str, *, reason: str | None = None) -> dict[str, Any]:
        """§33: the engine denying a held apply the architect role filed — a kit its
        consultation may not file (a second one, or one whose name is not the
        verdict's `next kit <name>`).

        Not a command of §4, like `decide_from_playbook`, and as narrow in origin: a
        held job of origin `architect` and nothing else. It does not ask
        `kit_apply_problem`: a denial releases nothing, and a hold that is not a
        filed kit is left to the human by the engine before it gets here.
        """
        record = self._job(job)
        if record.origin != ARCHITECT_ORIGIN:
            raise ApiError(
                f"job {record.id} is of origin {record.origin!r}: §33 gives the playbook "
                f"authority to deny a held apply of origin {ARCHITECT_ORIGIN!r} and nothing "
                "else; §8's table decides this one"
            )
        if record.state != "held":
            raise ApiError(f"job {record.id} is {record.state}, not held; there is no hold to deny")
        return await self._decide_as(job, "denied", "playbook", reason=reason, quote=None)

    async def _decide_as(
        self,
        job: str,
        decision: str,
        decided_by: str,
        *,
        reason: str | None,
        quote: str | None,
    ) -> dict[str, Any]:
        record = self._job(job)
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
            self.daemon.playbook.check_at_rest()  # §44 rule 4: a denied job has ended
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
        """Un-pause the playbook engine and clear the stop reason (§4, §10).

        §44 rule 5: a human pause's `resume` replays the kept ends, and is refused
        (`ApiError`, the load's reason) when the playbook does not load."""
        try:
            return await self.daemon.playbook.resume()
        except ResumeRefused as exc:
            raise ApiError(str(exc)) from exc

    # ---------------------------------------------------------- notify (§4)

    async def notify(self, *, test: str | None = None) -> dict[str, Any]:
        """Send one test message to the configured ntfy topic (§4, §11).

        `hands notify --test` does this in the *client*, so that it works at an
        install with no daemon yet; this method is the other half of the same
        surface (§9), for a caller that has only the daemon — and it sends
        through the daemon's own transport, so a test that replaced it sees this
        message too.

        A refusal by ntfy (any non-2xx) comes back as the result, with
        `delivered: false` and the code — the same answer `hands notify --test`
        prints (§19). `ApiError` is kept for the cases with no code to report:
        no topic configured, and a transport that never answered.
        """
        if test is None:
            raise ApiError('notify takes --test "<message>": it has no other mode (§4)')
        try:
            return await send_test(self.config, test, post=self.daemon.notifier.post)
        except NotifyError as exc:
            raise ApiError(str(exc)) from exc

    # ------------------------------------------------------------- who (§4)

    async def who(self) -> dict[str, Any]:
        """This daemon's part of the `hands who` picture (§4, §24). Read-only.

        One call so the client does not stitch four: each role's running job and
        queue, the running, queued and held jobs (a held job with its gate
        reason), the pipeline, and the unread inbox as ids and kinds only. The
        /proc and transcript parts are the client's (`hands.who`).
        """
        status = self.daemon.status()
        jobs: list[dict[str, Any]] = []
        for record in self.spool.list_jobs():
            if record.state not in ("running", "queued", "held"):
                continue
            row = job_summary(record)
            if record.state == "held":
                row["gate_reason"] = (record.gate or {}).get("reason")
            jobs.append(row)
        return {
            "project": self.config.project,
            "roles": {
                role: {"cwd": info["cwd"], "running": info["running"], "queued": info["queued"]}
                for role, info in status["roles"].items()
            },
            "jobs": jobs,
            "pipeline": self.daemon.playbook.pipeline(),
            "inbox": [{"id": event.id, "kind": event.kind} for event in self.spool.unacked()],
        }

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
        return doctor_report(self.config.project, self.config.path, found, live=live)

    # ------------------------------------------------- the phone's progress (§38)

    async def progress_report(self) -> str:
        """§38: the text of the phone's `progress <secret>` answer. Read-only.

        Not a command of §4 (`COMMANDS` is §4's table and `method()` does not
        answer this): it is the phone channel's tenth command, and lives here
        beside `status` because it reads the same daemon state. Three parts, one
        or more lines each: the builder's running job and its age, or the last
        ended builder job and its verdict; the branch and `git log --oneline -3`
        of the builder's cwd; and the first line of `meta/CHECKPOINT.md` at the
        repository root (`git rev-parse --show-toplevel` of the builder's cwd, §39)
        that names a unit in progress, or "no checkpoint".
        The git calls and the file read run in a thread, so the queue keeps moving.
        """
        cwd = self.config.role("builder").cwd
        lines = [self._builder_line()]
        lines.extend(await asyncio.to_thread(_progress_git, Path(cwd)))
        lines.append(await asyncio.to_thread(_checkpoint_line, Path(cwd)))
        return "\n".join(lines)

    def _builder_line(self) -> str:
        running_id = self.daemon.running_job_id("builder")
        if running_id is not None:
            record = self._job(running_id)
            return f"builder: running {record.id}, for {_age(record.started)}"
        for record in reversed(self.spool.list_jobs()):
            if record.role == "builder" and record.state in TERMINAL_STATES:
                verdict = record.verdict or "no verdict"
                return f"builder: idle; last ended {record.id} {record.state}, {verdict}"
        return "builder: idle; no job has ended"

    # -------------------------------------------------------------- internals

    def _job(self, job_id: str) -> Job:
        try:
            return self.spool.load_job(job_id)
        except SpoolError as exc:
            raise ApiError(str(exc)) from exc



#: §38: the `progress` answer's git calls; a git that hangs is a plain line, not a stall.
PROGRESS_GIT_TIMEOUT_S = 10.0
#: §38: "the first line of `meta/CHECKPOINT.md` that names a unit in progress".
PROGRESS_CHECKPOINT = Path("meta") / "CHECKPOINT.md"
_UNIT_IN_PROGRESS_RE = re.compile(r"\bunit in progress\b", re.IGNORECASE)
#: The longest checkpoint line the answer quotes; a longer one is cut with "…".
_CHECKPOINT_LINE_CHARS = 200
_NO_GIT = "git: no branch or log (not a repository, or no commit yet)"


def _age(started: str | None) -> str:
    """How long ago an ISO `started` stamp was: `42s`, `17m` or `3h05m`."""
    if not started:
        return "an unknown time"
    try:
        then = datetime.fromisoformat(started.replace("Z", "+00:00"))
    except ValueError:
        return "an unknown time"
    seconds = max(0, int((datetime.now(UTC) - then).total_seconds()))
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m"
    return f"{seconds // 3600}h{seconds % 3600 // 60:02d}m"


def _progress_git(cwd: Path) -> list[str]:
    """§38: `branch: <name>` and `git log --oneline -3` of `cwd`, or one plain line.

    A cwd that is not a repository, a repository with no commit, a git that is
    missing or one that does not answer in time all give the same one line.
    """

    def git(*args: str) -> str | None:
        try:
            done = subprocess.run(
                ["git", "-C", str(cwd), *args],
                capture_output=True,
                text=True,
                errors="replace",
                timeout=PROGRESS_GIT_TIMEOUT_S,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        return done.stdout if done.returncode == 0 else None

    branch = git("rev-parse", "--abbrev-ref", "HEAD")
    log = git("log", "--oneline", "-3") if branch is not None else None
    if branch is None or log is None:
        return [_NO_GIT]
    return [f"branch: {branch.strip()}", *log.splitlines()]


def _checkpoint_root(cwd: Path) -> Path:
    """§39: `git -C <cwd> rev-parse --show-toplevel`, or `cwd` itself when git gives none.

    The design names only the repository root; a cwd outside a repository (or a
    git that fails or hangs) falls back to the cwd, the simplest reading.
    """
    try:
        done = subprocess.run(
            ["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=PROGRESS_GIT_TIMEOUT_S,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return cwd
    top = done.stdout.strip() if done.returncode == 0 else ""
    return Path(top) if top else cwd


def _checkpoint_line(cwd: Path) -> str:
    """§38, §39: `checkpoint: <the first line naming a unit in progress>` of the
    `meta/CHECKPOINT.md` at the repository root of `cwd`, or "no checkpoint"."""
    try:
        path = _checkpoint_root(cwd) / PROGRESS_CHECKPOINT
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "no checkpoint"
    for line in text.splitlines():
        if _UNIT_IN_PROGRESS_RE.search(line):
            line = line.strip()
            if len(line) > _CHECKPOINT_LINE_CHARS:
                line = line[: _CHECKPOINT_LINE_CHARS - 1] + "…"
            return f"checkpoint: {line}"
    return "no checkpoint"


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


def tail_entries(path: Path, n: int) -> tuple[list[str], bool]:
    """The last `n` non-empty lines of `path`, read from the end, and whether that is all (§4, §21).

    `n` is `n >= 1` (§4); anything less is a `ValueError`, because "all of it" is
    not something a bounded read can answer.

    Bounded twice over: at most `MAX_TAIL_ENTRIES` lines come back, and at most
    `TAIL_WINDOW_BYTES` are ever read, from the end of the file backwards in
    chunks. The whole-file read this replaces put a mission's entire transcript
    in the daemon's heap on every poll. A first line that is cut by the window is
    dropped rather than returned half — an entry is a JSON object, and half of
    one is not one — so a file whose entries are wider than the window answers
    with fewer than `n` of them, and a file whose *last* entry is wider than the
    window answers with none.

    The second value is §4's `truncated`: true when either bound cut the answer
    short — the cap, when `n` was above it and the file had that many entries, or
    the window, when fewer than `n` entries came back and the file goes on before
    them. It is what review 5's blocker 2 asked for: both cuts used to be silent.
    """
    if int(n) < 1:
        raise ValueError(f"tail takes n >= 1, not {n}")
    want = min(int(n), MAX_TAIL_ENTRIES)
    chunks: list[bytes] = []
    read = newlines = 0
    with path.open("rb") as handle:
        start = handle.seek(0, os.SEEK_END)
        while start > 0 and read < TAIL_WINDOW_BYTES and newlines <= want:
            step = min(_TAIL_CHUNK, start, TAIL_WINDOW_BYTES - read)
            start -= step
            handle.seek(start)
            block = handle.read(step)
            chunks.append(block)
            read += len(block)
            newlines += block.count(b"\n")
    raw = b"".join(reversed(chunks))
    cut = start > 0  # the window stopped before the start of the file
    if cut:
        # The first line in the window began before it: it is a fragment.
        raw = raw[raw.find(b"\n") + 1 :] if b"\n" in raw else b""
    lines = [line for line in raw.decode("utf-8", errors="replace").splitlines() if line.strip()]
    truncated = want < int(n) if len(lines) >= want else cut
    return lines[-want:], truncated


def _read_from(
    path: Path, offset: int, limit: int = LOG_PAGE_BYTES
) -> tuple[list[str], int, bool]:
    """One page of `path` after `offset`: its complete lines, its end, is there more (§4, §7).

    At most `limit` bytes of complete lines are read (plus the remainder of one
    line that is itself wider than `limit` — the runner's reader bounds a
    captured line at `_STREAM_LIMIT`), so neither the daemon nor the socket ever
    carries a whole transcript — H-013, closed by §4's `log` row.
    `more` is true when bytes remain after the page; the caller asks again from
    the returned offset.

    A trailing partial line is left for the next read: the daemon appends to this
    file while the job runs, so a follower that took one would print half an event
    and then its other half.
    """
    start = max(0, int(offset))
    chunks: list[bytes] = []
    taken = 0
    try:
        with path.open("rb") as handle:
            handle.seek(start)
            while True:
                raw = handle.readline()
                if not raw.endswith(b"\n"):
                    break  # a half-written line: it is the next page's problem
                if chunks and taken + len(raw) > limit:
                    break  # this line starts the next page; the page ends whole
                chunks.append(raw)
                taken += len(raw)
                if taken >= limit:
                    break
            end = start + taken
            more = handle.seek(0, os.SEEK_END) > end
    except FileNotFoundError:
        return [], start, False
    except OSError as exc:  # pragma: no cover - unreadable spool file
        raise ApiError(f"cannot read {path}: {exc}") from exc
    if not chunks:
        return [], start, more
    return b"".join(chunks).decode("utf-8", errors="replace").splitlines(), end, more
