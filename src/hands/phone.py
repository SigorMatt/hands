"""The phone channel — commands from ntfy to handsd (DESIGN §8, §11, §24, §26; H-015).

    handsd ── GET <ntfy_url>/<cmd_topic>/json?since=… ──▶ ntfy   (outbound only)
       ▲                                                   │
       └──────────── one JSON line per message ────────────┘

The daemon subscribes to `[notify] cmd_topic` with a long-poll and accepts eight
commands, each ending in its token but `reply`, whose secret is its second word:

    approve <job> <secret|nonce>
    deny <job> [reason words…] <secret|nonce>
    pause <secret>
    resume <secret>
    status <secret>
    go <secret>
    kit <secret>        (a message that carries an ntfy attachment)
    reply <secret> <text>

**`reply`** (§33) sends `<text>` — the rest of the message after the whitespace
that follows the secret, unchanged — to the architect's last session as one
`keep` job of `origin: phone` (`Api.reply_architect`, the one send to the
architect role, H-032). It is refused, and the refusal answered on `ntfy_topic`
titled `hands: reply`, when there is no `[roles.architect]`, while an architect
job is running, queued or held, while the engine waits for a consultation's
`next kit`, and when the role has recorded no session. When the job ends, the
daemon publishes the architect's final message on `ntfy_topic` titled
`architect`. The job is not a consultation: the engine reads no verdict from it,
it does not un-pause a stopped pipeline, it is not counted against
`max_architect_consults`, and `kit_file` refuses a kit filed while it runs.

**`go`** (§26) is the one way to start work from the phone: it sends the
playbook's `[series] kickoff` line to the builder as a `clear` send with
`origin: phone`, through `Api.send`, so §8's gate patterns still apply. It is
refused while the builder has a job running, queued or held (§27; the refusal
names the job), checked before the playbook is read and again after it; when
there is no playbook (none in the builder's cwd, or one that cannot be loaded);
and when the playbook has no `[series] kickoff`. A stopped pipeline's playbook is still a
playbook: a `go` is accepted, and its job un-pauses the pipeline when it starts
(`UNPAUSE_ORIGINS`, H-018 gap 2).

**`kit`** (§26) moves a file from the phone to this machine and does nothing
else with it. The message's ntfy `attachment` (`name`, `size`, `url`) is checked
before anything is fetched: the name must be a `.zip` basename (printable, no
`/` or `\\`, no leading dot, a non-empty stem, ending in lowercase `.zip`), the
reported `size` an integer no larger than `[files] kit_max_mb` MiB, the `url`
one that passes `url_problem` — every step inside one try (§28): a string with no
whitespace that httpx parses, scheme `http` or `https`, a non-empty host that is
an IP literal or a name `idna.encode` accepts (§29), a port (when given) in
1-65535 — and `[files] kit_dir` inside
`[files] allowed_roots`. Once the secret is accepted, every refusal —
before the fetch or during it — is logged and filed as `kit.refused` with the
check that refused it, never the attachment's name or URL (§27). The download is
streamed by httpx on the event loop into a temp file in `kit_dir`, capped while
it streams, and must end at exactly the reported size; the temp file is then
hard-linked to the name (`os.link`, which never replaces an existing entry) or,
if that exists, to `<stem>-1.zip`, `<stem>-2.zip`, … and unlinked. Nothing is
unzipped, executed, or made executable. A written kit is filed as
`kit.received` (name as written, bytes, sha256) and answered on `ntfy_topic` as
`kit received <name> <bytes> <sha256>`. The channel reads its next command when
the download has ended.

**The apply from the kit** (§27). Once the kit is written, handsd lists the
zip's entries — never extracting one, reading only a root `KIT.md` — by
`hands.kit.apply_from_zip`, the path rules and the prompt builder `hands kit
check` uses, against the builder's cwd. It then files the §3 apply prompt
through `Api.file_apply` (§32: `Api.send`'s path, with a `kit_id` handsd mints
and records on the job) as a `clear` builder job with `origin: kit` and gate
reason `apply <name>` (the kit's file name without `.zip`), so the job is born `held`
and its `job.held` notification carries the Approve/Deny buttons. The prompt
names the file where it was written: `~/…` when `kit_dir` is under `$HOME`, else
its absolute path. A zip that cannot be read, holds no files, or has an entry
that is not a repository path under the builder's cwd is refused as
`kit.refused` ("the apply was not filed: …", naming the kinds of problem, never
an entry's name) and no job is filed; the kit stays on disk, so `hands kit
check` can say which entry. A builder that is busy does not refuse the apply:
it is held, and the human decides when to approve it. The builder unzips it.
When the commit message is the default `plan: kit <name>` — no `KIT.md`, or a
first line §28's rules refuse — the phone is told why on `ntfy_topic`: `apply
<name>: <why>; the commit message is the default '<message>'`.

**The token.** A typed command carries `cmd_secret` as its last word. A held
job's notification carries Approve/Deny buttons that publish `approve <job>
<nonce>` / `deny <job> <nonce>` to `cmd_topic`, where the nonce is 32 random
bytes (URL-safe base 64, `secrets.token_urlsafe(32)`) minted when the job is
held. The nonce lives in this object's memory only — never in the job record,
an event, the spool or a log line — and it authorizes a decision on that one
job only. It is spent by the decision it authorizes; a wrong token spends
nothing. It is dropped when the job is decided by any route (the daemon calls
`discard` on every `gate.decided`), and with the daemon. A restarted daemon
mints a fresh nonce for every job still held (§25; `Daemon._remint_held`), but
publishes no notification per job: §31 lists those jobs inside the one `handsd
started` notification, which carries no buttons, so after a restart a held job
is decided by `hands approve|deny` or by a command with the secret until it is
held again. `pause`, `resume`,
`status` and `go` take the secret only. The secret is compared with
`hmac.compare_digest` and never published: a notification carries only nonces.

**What is answered.** `status` publishes a short summary to `ntfy_topic`, an
accepted `go` publishes the id and state of the job it filed there, a
written kit publishes its name, size and sha256, and a `reply` with the secret
publishes the job it filed or why it was refused (then the architect's answer).
Nothing else is answered: a bad token, an unknown or malformed command, a
command for a job that is not held — each is logged (without the token, and
without any word of the message that could be one) and ignored.

**Replays.** The first connection asks for `since=<unix time the channel
started>`, and a message whose `time` is before that is not acted on, so a
restart does not re-run yesterday's approvals. Every later connection asks for
`since=<the last message id read>`, and the ids already read are remembered,
so a reconnect after an error does not act on a message twice.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import hmac
import itertools
import json
import logging
import os
import re
import secrets
import shlex
import tempfile
import time
from collections import deque
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path
from typing import IO, TYPE_CHECKING
from urllib.parse import quote

from hands import notify as notify_mod
from hands.api import ApiError
from hands.kit import KitError, apply_from_zip, home_shown
from hands.notify import PAIR_SPACING_S
from hands.playbook import PlaybookError, load_playbook, playbook_path
from hands.spool import Job, PathEscape, SpoolError, new_kit_id, resolve_under_roots

if TYPE_CHECKING:  # pragma: no cover
    import httpx

    from hands.daemon import Daemon

__all__ = [
    "ARCHITECT_TITLE", "BACKOFF_S", "GO_TITLE", "KIT_TITLE", "NONCE_BYTES", "REPLY_TITLE",
    "STATUS_TITLE", "PhoneChannel", "parse_reply", "reply_answer", "status_summary",
]  # fmt: skip

log = logging.getLogger("hands.phone")

#: §24: "the nonce is 32 random bytes".
NONCE_BYTES = 32
#: Seconds between reconnects, by consecutive failure; the last one repeats.
#: A line read from the stream resets the count.
BACKOFF_S: tuple[float, ...] = (1.0, 2.0, 5.0, 10.0, 30.0, 60.0)
#: Message ids remembered against a replay. A reconnect asks for what came after
#: the last one, so this only has to cover a server that sends a few again.
SEEN_IDS = 1024
#: The titles of the two answers the channel gives.
STATUS_TITLE = "hands: status"
GO_TITLE = "hands: go"
KIT_TITLE = "hands: kit received"
#: §33: the channel's answer to a `reply` — accepted (the job) or refused (why).
REPLY_TITLE = "hands: reply"
#: §33: "the reply's text is published on `ntfy_topic` with title `architect`".
ARCHITECT_TITLE = "architect"

#: §26's size cap is in MB; hands reads that as MiB.
MIB = 1024 * 1024
#: Connect, read and write timeout of one kit download, per operation.
KIT_TIMEOUT_S = 30.0
#: The ceiling on a whole kit download: a server that trickles is refused.
KIT_DEADLINE_S = 300.0
#: The temp file a kit is streamed into, in `kit_dir` itself (a hidden name).
KIT_TEMP_PREFIX = ".hands-kit-"
KIT_SUFFIX = ".zip"

_SECRET_ONLY = ("pause", "resume", "status", "go", "kit")
#: §33: `reply <secret> <text>`. The secret is the second word, not the last, and the
#: text is the rest of the message as typed: whitespace before `reply`, the run
#: between `reply` and the secret, and the run between the secret and the text are
#: the separators, and nothing else is stripped.
_REPLY_RE = re.compile(r"\A\s*reply\s+(?P<token>\S+)\s+(?P<text>.*)\Z", re.IGNORECASE | re.DOTALL)
_DECISIONS = {"approve": "approved", "deny": "denied"}


class PhoneChannel:
    """One daemon's subscription to `cmd_topic`, and the nonces of its held jobs."""

    def __init__(
        self,
        daemon: Daemon,
        *,
        stream: Callable[..., AsyncIterator[str]] | None = None,
        clock: Callable[[], float] = time.time,
        sleep: Callable[[float], Awaitable[None]] | None = None,
    ) -> None:
        self.daemon = daemon
        self.notify = daemon.config.notify
        #: The transport: None means `hands.notify.http_stream`, looked up at call
        #: time. A test sets a fake stream here before `start()`.
        self.stream = stream
        self.clock = clock
        self.sleep: Callable[[float], Awaitable[None]] = sleep or asyncio.sleep
        #: job id → the unspent nonce of that held job. Memory only, by design.
        self.nonces: dict[str, str] = {}
        #: Unix seconds at `start()`: the first `since`, and the floor for `time`.
        self.started_at: int | None = None
        self.last_id: str | None = None
        #: Message events read, acted on or ignored; a test waits on this count.
        self.handled = 0
        self.task: asyncio.Task[None] | None = None
        self._seen: deque[str] = deque(maxlen=SEEN_IDS)

    # ---------------------------------------------------------------- nonces

    @property
    def topic_url(self) -> str:
        return f"{self.notify.ntfy_url.rstrip('/')}/{self.notify.cmd_topic}"

    def actions(self, job_id: str) -> list[dict[str, str]]:
        """The Approve/Deny buttons of a held job's notification, minting its nonce."""
        nonce = self.nonces.get(job_id)
        if nonce is None:
            nonce = self.nonces[job_id] = secrets.token_urlsafe(NONCE_BYTES)
        return [
            {"label": "Approve", "url": self.topic_url, "body": f"approve {job_id} {nonce}"},
            {"label": "Deny", "url": self.topic_url, "body": f"deny {job_id} {nonce}"},
        ]

    def discard(self, job_id: str) -> None:
        """The job left `held` (or its gate was decided): its nonce dies with it."""
        self.nonces.pop(job_id, None)

    # ------------------------------------------------------------- lifecycle

    def start(self) -> None:
        self.started_at = int(self.clock())
        self.task = asyncio.create_task(self.run(), name="hands-phone")
        log.info("phone: command channel on; subscribing to cmd_topic")

    async def stop(self) -> None:
        if self.task is not None:
            self.task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.task
        self.nonces.clear()

    def url(self) -> str:
        since = self.last_id if self.last_id is not None else str(self.started_at)
        return f"{self.topic_url}/json?since={quote(since, safe='')}"

    async def run(self) -> None:
        """Long-poll forever; any error or end of stream is a reconnect after a backoff."""
        failures = 0
        while True:
            stream = self.stream if self.stream is not None else notify_mod.http_stream
            try:
                token = notify_mod.token_kwargs(self.notify.ntfy_token)
                async for line in stream(self.url(), **token):
                    failures = 0
                    await self._line(line)
                why = "the stream ended"
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # any transport failure: reconnect, never die
                why = _failure(exc)
            delay = BACKOFF_S[min(failures, len(BACKOFF_S) - 1)]
            failures += 1
            log.warning("phone: %s; reconnecting in %.0f s", why, delay)
            await self.sleep(delay)

    # -------------------------------------------------------------- messages

    async def _line(self, line: str) -> None:
        if not line.strip():
            return
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            log.warning("phone: a stream line is not JSON; ignored")
            return
        if not isinstance(event, dict) or event.get("event") != "message":
            return  # `open`, `keepalive`, `poll_request`
        msg_id = event.get("id")
        if isinstance(msg_id, str):
            if msg_id in self._seen:
                log.info("phone: message %s was already read; ignored", msg_id)
                return
            self._seen.append(msg_id)
            self.last_id = msg_id
        try:
            when = event.get("time")
            if (
                isinstance(when, (int, float))
                and self.started_at is not None
                and when < self.started_at
            ):
                log.info("phone: message %s predates this subscription; ignored", msg_id)
                return
            text = event.get("message")
            if isinstance(text, str):
                await self.command(text, attachment=event.get("attachment"))
        except asyncio.CancelledError:
            raise
        except Exception:  # a bug here must not end the subscription
            log.exception("phone: a command raised")
        finally:
            self.handled += 1

    async def command(self, text: str, *, attachment: object = None) -> None:
        """Authenticate and carry out one command; anything else is logged and ignored.

        `attachment` is the ntfy message's `attachment` object; only `kit` reads it.
        """
        words = text.split()
        verb = words[0].lower() if words else ""
        token = words[-1] if words else ""
        if verb == "reply":
            return await self._reply_command(text)
        if verb in _SECRET_ONLY:
            if len(words) != 2:
                return self._ignore(f"{verb} takes only the secret")
            if not self._is_secret(token):
                return self._ignore(f"{verb}: bad secret")
            if verb == "go":
                return await self._go()
            if verb == "kit":
                return await self._kit(attachment)
            if verb == "pause":
                await self.daemon.playbook.pause(by="phone")
            elif verb == "resume":
                await self.daemon.api.resume()
            else:
                await self.daemon.notifier.answer(STATUS_TITLE, status_summary(self.daemon))
            log.info("phone: %s", verb)
            return None
        if verb in _DECISIONS:
            if len(words) < 3 or (verb == "approve" and len(words) != 3):
                return self._ignore(f"{verb}: malformed")
            job_id = words[1]
            reason = " ".join(words[2:-1]) or None
            if not (self._is_secret(token) or self._is_nonce(job_id, token)):
                return self._ignore(f"{verb} {self._label(job_id)}: bad secret or nonce")
            try:
                record = self.daemon.spool.load_job(job_id)
            except SpoolError:
                return self._ignore(f"{verb}: no such job")
            if record.state != "held":
                return self._ignore(f"{verb} {job_id}: the job is {record.state}, not held")
            try:
                await self.daemon.api.decide_from_phone(job_id, _DECISIONS[verb], reason=reason)
            except ApiError as exc:
                return self._ignore(f"{verb} {job_id}: {exc}")
            self.discard(job_id)
            log.info("phone: %s %s", verb, job_id)
            return None
        return self._ignore("not a command")

    async def _go(self) -> None:
        """§26, §27: the series' kickoff line to the builder, `clear`, `origin: phone`.

        Refused while the builder has a job running, queued or held (§27). The
        builder is checked first, with nothing awaited before it, and again after
        the playbook is read: the read runs in a thread, and a `hands send` can
        land meanwhile (review 10 should-fix 1). `Api.send` awaits nothing before
        its enqueue, so the second check and the job it allows are one step of the
        event loop. The playbook is read from the builder's cwd now, by the same
        loader the engine uses (only the committed file loads, §10) — not taken
        from the engine's last load, which happens only when a job starts — and a
        read never files a stop.
        """
        busy = self._builder_busy()
        if busy is not None:
            return self._ignore(f"go: {busy}")
        config = self.daemon.config
        try:
            book = await asyncio.to_thread(
                load_playbook, playbook_path(config), cwd=config.role("builder").cwd
            )
        except PlaybookError as exc:
            return self._ignore(f"go: no playbook is loaded: it cannot be loaded ({exc})")
        if book is None:
            return self._ignore("go: no playbook is loaded")
        if book.kickoff is None:
            return self._ignore("go: the playbook has no [series] kickoff")
        busy = self._builder_busy()
        if busy is not None:
            return self._ignore(f"go: {busy}")
        try:
            job = await self.daemon.api.send(
                role="builder", context="clear", prompt=book.kickoff, origin="phone"
            )
        except ApiError as exc:
            return self._ignore(f"go: the send was refused ({exc})")
        log.info("phone: go filed builder job %s (%s)", job["id"], job["state"])
        await self.daemon.notifier.answer(GO_TITLE, f"go: builder job {job['id']} {job['state']}")
        return None

    async def _reply_command(self, text: str) -> None:
        """§33: `reply <secret> <text>` — the text, verbatim, to the architect's last
        session as one `keep` job of `origin: phone`.

        Neither the text nor any word of it is logged. A message without a text, or
        with a token that is not the secret, is ignored like any command; once the
        secret is accepted, a refusal is answered on `ntfy_topic` (`REPLY_TITLE`)
        with hands' own words, because the human on the phone is waiting for the
        architect and would otherwise hear nothing. Every refusal is decided by
        `Api.reply_architect`, next to the enqueue it allows, with nothing awaited
        between them.
        """
        parsed = parse_reply(text)
        if parsed is None:
            return self._ignore("reply takes the secret and a text")
        token, reply = parsed
        if not self._is_secret(token):
            return self._ignore("reply: bad secret")
        try:
            job = await self.daemon.api.reply_architect(reply)
        except ApiError as exc:
            self._ignore(f"reply: {exc}")
            await self.daemon.notifier.answer(REPLY_TITLE, f"reply refused: {exc}")
            return None
        log.info("phone: reply filed architect job %s (%s)", job["id"], job["state"])
        await self.daemon.notifier.answer(
            REPLY_TITLE, f"reply: architect job {job['id']} {job['state']}"
        )
        return None

    def _builder_busy(self) -> str | None:
        """Why the builder cannot take a `go` now — a job running, queued or held — or None."""
        builder = self.daemon.status()["roles"]["builder"]
        if builder["running"]:
            return f"the builder has a job running ({builder['running']['id']})"
        if builder["queued"]:
            return f"the builder has a job queued ({', '.join(builder['queued'])})"
        held = [
            job.id
            for job in self.daemon.spool.list_jobs()
            if job.role == "builder" and job.state == "held"
        ]
        if held:
            return f"the builder has a job held ({', '.join(held)})"
        return None

    async def _kit(self, attachment: object) -> None:
        """§26: the message's attachment, fetched into `[files] kit_dir`.

        Every check that needs no network runs first, so a refused kit never
        reaches the attachment's server. A refusal names the check, never the
        attachment's name or URL (text the sender chose), and is filed as
        `kit.refused` (§27).
        """
        if not isinstance(attachment, dict):
            return self._refuse_kit("the message carries no attachment")
        name = attachment.get("name")
        if not _is_kit_name(name):
            return self._refuse_kit("the attachment name is not a .zip basename")
        assert isinstance(name, str)
        files = self.daemon.config.files
        size = attachment.get("size")
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            return self._refuse_kit("the attachment reports no size in bytes")
        cap = files.kit_max_mb * MIB
        if size > cap:
            return self._refuse_kit(
                f"the attachment is {size} bytes, over [files] kit_max_mb = "
                f"{files.kit_max_mb} ({cap} bytes)"
            )
        url = attachment.get("url")
        problem = url_problem(url)
        if problem is not None:
            return self._refuse_kit(f"the attachment has no valid http(s) url: {problem}")
        assert isinstance(url, str)
        try:
            directory = resolve_under_roots(files.kit_dir, files.allowed_roots)
        except PathEscape:
            return self._refuse_kit("[files] kit_dir is outside [files] allowed_roots")
        if not directory.is_dir():
            return self._refuse_kit("[files] kit_dir is not a directory")
        try:
            written, total, digest = await fetch_kit(
                url,
                directory,
                name,
                cap=cap,
                expected=size,
                token=attachment_token(url, self.notify.ntfy_url, self.notify.ntfy_token),
            )
        except _KitRefused as exc:
            return self._refuse_kit(str(exc))
        self.daemon.spool.append_event(
            "kit.received", {"name": written, "bytes": total, "sha256": digest}
        )
        text = f"kit received {written} {total} {digest}"
        log.info("phone: %s", text)
        await self.daemon.notifier.answer(KIT_TITLE, text)
        # §30 (decision 2026-09-15): the receipt and the `job.held` of the apply
        # it is about to file are two notifications of one cause, and ntfy stamps
        # whole seconds. Published inside one second they sort arbitrarily on the
        # phone, and the receipt is what explains the hold. So: this one wait,
        # between the two publishes, on the channel's own injected sleep. It
        # delays nothing but the next command on this channel (a kit download has
        # just held it far longer), and no job waits on it — the apply is filed
        # after it, held, and a held job runs nothing until a human decides.
        await self.sleep(PAIR_SPACING_S)
        return await self._file_apply(directory / written)

    async def _file_apply(self, path: Path) -> None:
        """§27: the kit's apply, filed as a held builder job, or `kit.refused`.

        The zip is listed in a thread, never extracted. The job goes through
        `Api.send` with an explicit gate, so it is born `held` and takes §8's
        path: `job.held`, the playbook's `job.held` event, the buttons.
        """
        cwd = self.daemon.config.role("builder").cwd
        try:
            plan = await asyncio.to_thread(apply_from_zip, path, cwd, home_shown(path))
        except KitError as exc:
            return self._refuse_kit(f"the apply was not filed: {exc}")
        try:
            # §31, §32: the one path `hands kit file` takes too (`Api.file_apply`),
            # with this route's origin, and a `kit_id` handsd mints here.
            job = await self.daemon.api.file_apply(plan, "kit", new_kit_id())
        except ApiError as exc:
            return self._refuse_kit(f"the apply was not filed: the send was refused ({exc})")
        log.info("phone: kit apply filed as builder job %s (%s)", job["id"], job["state"])
        if plan.default_why is not None:  # §28: the notification says so
            text = (
                f"apply {plan.name}: {plan.default_why}; the commit message is the default "
                f"{shlex.quote(plan.commit_message)}"
            )
            log.info("phone: %s", text)
            # §31 (review 14 blocker 2): this is the ordinary kit — no `KIT.md`, so
            # there is a default to explain — and it is a *third* publish of the one
            # cause the receipt and the hold are. §30's spacing is per consecutive
            # pair, not per cause, so it is waited here too; without it this answer
            # and the `job.held` above share a stamp and sort arbitrarily. The wait
            # also lets the held notification's spawned publish run first, so the
            # order on the phone is receipt, hold (with the buttons), explanation.
            await self.sleep(PAIR_SPACING_S)
            await self.daemon.notifier.answer(KIT_TITLE, text)
        return None

    def _refuse_kit(self, why: str) -> None:
        """An authenticated `kit` refused: logged, and filed as `kit.refused` (§27).

        `why` is hands' own text naming the check; it never carries the attachment's
        name or URL. A `kit` with a bad secret is only logged, like any command.
        """
        self.daemon.spool.append_event("kit.refused", {"reason": why})
        self._ignore(f"kit: {why}")

    def _is_secret(self, token: str) -> bool:
        secret = self.notify.cmd_secret
        return secret is not None and hmac.compare_digest(token.encode(), secret.encode())

    def _is_nonce(self, job_id: str, token: str) -> bool:
        nonce = self.nonces.get(job_id)
        return nonce is not None and hmac.compare_digest(token.encode(), nonce.encode())

    def _label(self, job_id: str) -> str:
        """A job id fit for the log: only one that names a real job is echoed.

        Before the token is accepted, the second word of a command is anything
        the sender typed — possibly the secret itself — so it is logged only when
        a job record by that name exists.
        """
        try:
            self.daemon.spool.load_job(job_id)
        except SpoolError:
            return "(an unknown job)"
        return job_id

    @staticmethod
    def _ignore(why: str) -> None:
        log.warning("phone: command ignored (%s)", why)


def status_summary(daemon: Daemon) -> str:
    """§24's status line: roles, held jobs, the pipeline and the inbox, in a few lines.

    Job ids and states only — no prompt, no reason text — so what the summary
    carries is hands' own words.
    """
    status = daemon.status()
    lines = [f"{daemon.config.project}"]
    for role, info in status["roles"].items():
        running = info.get("running")
        now = f"running {running['id']}" if running else "idle"
        lines.append(f"{role}: {now}, {len(info.get('queued') or [])} queued")
    held = [job.id for job in daemon.spool.list_jobs() if job.state == "held"]
    lines.append(f"held: {', '.join(held) if held else 'none'}")
    pipeline = daemon.playbook.pipeline()
    lines.append(f"pipeline: {'paused' if pipeline.get('paused') else 'running'}")
    lines.append(f"inbox: {status['inbox']['unacked']} unacked")
    return "\n".join(lines)


def parse_reply(text: str) -> tuple[str, str] | None:
    """§33: the token and the text of `reply <token> <text>`, or None.

    Stripped: whitespace before `reply`, the whitespace between `reply` and the
    token, and the whitespace between the token and the text. The text is the rest
    of the message, unchanged — inner and trailing whitespace and newlines kept. A
    text that is empty after the separator is no reply (None)."""
    match = _REPLY_RE.match(text)
    if match is None or not match.group("text"):
        return None
    return match.group("token"), match.group("text")


def reply_answer(job: Job) -> str:
    """§33: what the phone is told when a reply job ends — the architect's final
    message, verbatim, or, when the job ended without one, which job ended how."""
    if job.state == "done" and job.result:
        return job.result
    return f"architect job {job.id} ended {job.state} with no reply"


class _KitRefused(Exception):
    """A kit download that is not written; the text is the logged reason."""


def url_problem(url: object) -> str | None:
    """Why `url` is not an attachment URL handsd fetches, or None (§28).

    Every step runs inside the one try: reading `httpx.URL.host` decodes the host
    as IDNA and raises idna's error for a label such as `xn--` (review 11 blocker
    2), and `httpx.InvalidURL` is not an `httpx.HTTPError` (review 10 should-fix
    6). Whatever else parsing raises is a refusal too, never a traceback. The
    reason names the check, never the URL's text.

    "IDNA-valid" means `idna.encode(host)` succeeds (§29, review 12 blocker 2). An
    IP literal (`127.0.0.1`, `[::1]`) is not a name, and `idna.encode` refuses an
    IPv6 one, so a host that `ipaddress.ip_address` parses is judged by that and
    every other host by `idna.encode` (§29 is silent on IP literals).
    """
    import ipaddress

    import httpx
    import idna

    try:
        if not isinstance(url, str):
            return "it is not a string"
        if any(char.isspace() for char in url):
            return "it contains whitespace"  # httpx would percent-encode it into the host
        try:
            parsed = httpx.URL(url)
        except (httpx.InvalidURL, ValueError, TypeError):
            return "it does not parse"
        if parsed.scheme not in ("http", "https"):
            return "its scheme is not http or https"
        if not parsed.raw_host:
            return "it has no host"
        try:
            host = parsed.host
            try:
                ipaddress.ip_address(host)
            except ValueError:
                idna.encode(host)  # §29: a name is IDNA-valid when this succeeds
        except (UnicodeError, ValueError):  # idna.IDNAError is a UnicodeError
            return "its host is not a valid IDNA name"
        if not host:
            return "it has no host"
        port = parsed.port
        if port is not None and not 1 <= port <= 65535:
            return "its port is not in 1-65535"
    except Exception as exc:  # §28: any failure is a refusal, filed as kit.refused
        return f"it could not be checked ({type(exc).__name__})"
    return None


def attachment_token(url: str, ntfy_url: str, token: str | None) -> str | None:
    """§33's bearer for a kit attachment: the token when `url` is on `ntfy_url`'s own
    origin (scheme, host and port), else None.

    §33 names publish and subscribe; it is silent on an attachment, which a server
    whose topics require a token may serve under the same rule. The simplest
    thing that neither breaks that server nor hands the token to a host it is not
    for: the attachment URL is whatever the message says, so the bearer goes only
    where `[notify] ntfy_url` already sends it.
    """
    import httpx

    if not token:
        return None
    try:
        ours, theirs = httpx.URL(ntfy_url), httpx.URL(url)
        same = (
            ours.scheme == theirs.scheme
            and ours.host == theirs.host
            and _port(ours) == _port(theirs)
        )
    except Exception:  # a URL that does not parse is no origin of ours
        return None
    return token if same else None


def _port(url: httpx.URL) -> int | None:
    """An URL's port, with the scheme's default filled in (`https://h` is `:443`)."""
    port = url.port
    if port is not None:
        return int(port)
    return {"http": 80, "https": 443}.get(url.scheme)


def _is_kit_name(name: object) -> bool:
    """§26's "sanitized to a basename; `.zip` only", as a refusal, not a rewrite.

    Printable, no path separator of either platform, no leading dot (which also
    rules out `.`, `..` and a bare `.zip`), and a lowercase `.zip` after a
    non-empty stem. A name that fails is refused rather than cleaned up, so the
    name written is the name the sender chose.
    """
    return (
        isinstance(name, str)
        and name.isprintable()
        and "/" not in name
        and "\\" not in name
        and not name.startswith(".")
        and name.endswith(KIT_SUFFIX)
        and len(name) > len(KIT_SUFFIX)
    )


async def fetch_kit(
    url: str,
    directory: Path,
    name: str,
    *,
    cap: int,
    expected: int,
    token: str | None = None,
) -> tuple[str, int, str]:
    """Stream `url` into `directory` under `name` (or its first free suffix).

    Answers the name written, the bytes and the sha256. The body is streamed on
    the event loop into a temp file in `directory`; the fsync and the link run in
    a thread. The cap is enforced on the bytes read, whatever `Content-Length`
    or the attachment said, and a body that does not end at `expected` bytes is
    refused. `Accept-Encoding: identity` keeps the bytes counted the bytes
    stored. On any refusal the temp file is removed and nothing is written.
    `token`, when given, is sent as a bearer (§33; `attachment_token` decides).
    """
    import httpx

    handle, temp_name = tempfile.mkstemp(prefix=KIT_TEMP_PREFIX, suffix=".part", dir=directory)
    temp = Path(temp_name)
    digest = hashlib.sha256()
    total = 0
    try:
        with os.fdopen(handle, "wb") as out:
            try:
                async with asyncio.timeout(KIT_DEADLINE_S):
                    async with httpx.AsyncClient(timeout=httpx.Timeout(KIT_TIMEOUT_S)) as client:
                        headers = {
                            "Accept-Encoding": "identity",
                            **notify_mod.auth_headers(token),
                        }
                        async with client.stream("GET", url, headers=headers) as response:
                            response.raise_for_status()
                            async for chunk in response.aiter_raw():
                                total += len(chunk)
                                if total > cap:
                                    raise _KitRefused(
                                        f"the download passed [files] kit_max_mb ({cap} bytes)"
                                    )
                                digest.update(chunk)
                                out.write(chunk)
            except (httpx.HTTPError, httpx.InvalidURL) as exc:
                raise _KitRefused(f"the download failed ({_failure(exc)})") from exc
            except TimeoutError as exc:
                raise _KitRefused(f"the download took longer than {KIT_DEADLINE_S:.0f} s") from exc
            if total != expected:
                raise _KitRefused(
                    f"the download is {total} bytes, not the {expected} the attachment reported"
                )
            await asyncio.to_thread(_flush, out)
        written = await asyncio.to_thread(_link_first_free, temp, directory, name)
    except OSError as exc:
        raise _KitRefused(f"the kit could not be written ({type(exc).__name__})") from exc
    finally:
        with contextlib.suppress(FileNotFoundError):
            temp.unlink()
    return written, total, digest.hexdigest()


def _flush(out: IO[bytes]) -> None:
    out.flush()
    os.fsync(out.fileno())


def _link_first_free(temp: Path, directory: Path, name: str) -> str:
    """Link `temp` to `name`, else `<stem>-1.zip`, `<stem>-2.zip`, …; never replace.

    `os.link` fails with `FileExistsError` when the new name exists (a dangling
    symlink included), so an existing file is never overwritten, even by a
    writer racing this one: the check and the create are one system call.
    """
    stem = name[: -len(KIT_SUFFIX)]
    for n in itertools.count():
        candidate = name if n == 0 else f"{stem}-{n}{KIT_SUFFIX}"
        try:
            os.link(temp, directory / candidate)
        except FileExistsError:
            continue
        return candidate
    raise AssertionError("unreachable")  # pragma: no cover


def _failure(exc: BaseException) -> str:
    """The reconnect warning's reason: the exception type and HTTP status only.

    Never the exception's text: httpx puts the request URL in it, and the URL
    carries `cmd_topic`, which reveals the secret (review 8 should-fix 4). An
    exception without a response (a refused connection, a timeout) is its type.
    """
    status = getattr(getattr(exc, "response", None), "status_code", None)
    name = type(exc).__name__
    return f"{name}: HTTP {status}" if isinstance(status, int) else name
