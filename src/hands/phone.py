"""The phone channel — commands from ntfy to handsd (DESIGN §8, §11, §24, §26; H-015).

    handsd ── GET <ntfy_url>/<cmd_topic>/json?since=… ──▶ ntfy   (outbound only)
       ▲                                                   │
       └──────────── one JSON line per message ────────────┘

The daemon subscribes to `[notify] cmd_topic` with a long-poll and accepts seven
commands, each ending in its token:

    approve <job> <secret|nonce>
    deny <job> [reason words…] <secret|nonce>
    pause <secret>
    resume <secret>
    status <secret>
    go <secret>
    kit <secret>        (a message that carries an ntfy attachment)

**`go`** (§26) is the one way to start work from the phone: it sends the
playbook's `[series] kickoff` line to the builder as a `clear` send with
`origin: phone`, through `Api.send`, so §8's gate patterns still apply. It is
refused while the builder has a job running or queued, when there is no
playbook (none in the builder's cwd, or one that cannot be loaded), and when
the playbook has no `[series] kickoff`. A stopped pipeline's playbook is still a
playbook: a `go` is accepted, and its job un-pauses the pipeline when it starts
(`UNPAUSE_ORIGINS`, H-018 gap 2).

**`kit`** (§26) moves a file from the phone to this machine and does nothing
else with it. The message's ntfy `attachment` (`name`, `size`, `url`) is checked
before anything is fetched: the name must be a `.zip` basename (printable, no
`/` or `\\`, no leading dot, a non-empty stem, ending in lowercase `.zip`), the
reported `size` an integer no larger than `[files] kit_max_mb` MiB, the `url`
http(s), and `[files] kit_dir` inside `[files] allowed_roots`. The download is
streamed by httpx on the event loop into a temp file in `kit_dir`, capped while
it streams, and must end at exactly the reported size; the temp file is then
hard-linked to the name (`os.link`, which never replaces an existing entry) or,
if that exists, to `<stem>-1.zip`, `<stem>-2.zip`, … and unlinked. Nothing is
unzipped, executed, or made executable. A written kit is filed as
`kit.received` (name as written, bytes, sha256) and answered on `ntfy_topic` as
`kit received <name> <bytes> <sha256>`. The channel reads its next command when
the download has ended.

**The token.** A typed command carries `cmd_secret` as its last word. A held
job's notification carries Approve/Deny buttons that publish `approve <job>
<nonce>` / `deny <job> <nonce>` to `cmd_topic`, where the nonce is 32 random
bytes (URL-safe base 64, `secrets.token_urlsafe(32)`) minted when the job is
held. The nonce lives in this object's memory only — never in the job record,
an event, the spool or a log line — and it authorizes a decision on that one
job only. It is spent by the decision it authorizes; a wrong token spends
nothing. It is dropped when the job is decided by any route (the daemon calls
`discard` on every `gate.decided`), and with the daemon. A restarted daemon
mints a fresh nonce for every job still held and re-sends its notification with
the new buttons (§25; `Daemon._renotify_held`). `pause`, `resume`,
`status` and `go` take the secret only. The secret is compared with
`hmac.compare_digest` and never published: a notification carries only nonces.

**What is answered.** `status` publishes a short summary to `ntfy_topic`, an
accepted `go` publishes the id and state of the job it filed there, and a
written kit publishes its name, size and sha256. Nothing else
is answered: a bad token, an unknown or malformed command, a
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
import secrets
import tempfile
import time
from collections import deque
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path
from typing import IO, TYPE_CHECKING
from urllib.parse import quote

from hands import notify as notify_mod
from hands.api import ApiError
from hands.playbook import PlaybookError, load_playbook, playbook_path
from hands.spool import PathEscape, SpoolError, resolve_under_roots

if TYPE_CHECKING:  # pragma: no cover
    from hands.daemon import Daemon

__all__ = [
    "BACKOFF_S", "GO_TITLE", "KIT_TITLE", "NONCE_BYTES", "STATUS_TITLE", "PhoneChannel",
    "status_summary",
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
_DECISIONS = {"approve": "approved", "deny": "denied"}


class PhoneChannel:
    """One daemon's subscription to `cmd_topic`, and the nonces of its held jobs."""

    def __init__(
        self,
        daemon: Daemon,
        *,
        stream: Callable[[str], AsyncIterator[str]] | None = None,
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
                async for line in stream(self.url()):
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
        """§26: the series' kickoff line to the builder, `clear`, `origin: phone`.

        The builder's queue is checked first, with nothing awaited before it, so
        what is refused is the state the command arrived in. The playbook is read
        from the builder's cwd now, by the same loader the engine uses (only the
        committed file loads, §10) — not taken from the engine's last load, which
        happens only when a job starts — and a read never files a stop.
        """
        builder = self.daemon.status()["roles"]["builder"]
        if builder["running"]:
            running = builder["running"]["id"]
            return self._ignore(f"go: the builder has a job running ({running})")
        if builder["queued"]:
            queued = ", ".join(builder["queued"])
            return self._ignore(f"go: the builder has a job queued ({queued})")
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
        try:
            job = await self.daemon.api.send(
                role="builder", context="clear", prompt=book.kickoff, origin="phone"
            )
        except ApiError as exc:
            return self._ignore(f"go: the send was refused ({exc})")
        log.info("phone: go filed builder job %s (%s)", job["id"], job["state"])
        await self.daemon.notifier.answer(GO_TITLE, f"go: builder job {job['id']} {job['state']}")
        return None

    async def _kit(self, attachment: object) -> None:
        """§26: the message's attachment, fetched into `[files] kit_dir`.

        Every check that needs no network runs first, so a refused kit never
        reaches the attachment's server. A refusal names the check, never the
        attachment's name or URL (text the sender chose).
        """
        if not isinstance(attachment, dict):
            return self._ignore("kit: the message carries no attachment")
        name = attachment.get("name")
        if not _is_kit_name(name):
            return self._ignore("kit: the attachment name is not a .zip basename")
        assert isinstance(name, str)
        files = self.daemon.config.files
        size = attachment.get("size")
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            return self._ignore("kit: the attachment reports no size in bytes")
        cap = files.kit_max_mb * MIB
        if size > cap:
            return self._ignore(
                f"kit: the attachment is {size} bytes, over [files] kit_max_mb = "
                f"{files.kit_max_mb} ({cap} bytes)"
            )
        url = attachment.get("url")
        if not isinstance(url, str) or not url.startswith(("https://", "http://")):
            return self._ignore("kit: the attachment has no http(s) url")
        try:
            directory = resolve_under_roots(files.kit_dir, files.allowed_roots)
        except PathEscape:
            return self._ignore("kit: [files] kit_dir is outside [files] allowed_roots")
        if not directory.is_dir():
            return self._ignore("kit: [files] kit_dir is not a directory")
        try:
            written, total, digest = await fetch_kit(
                url, directory, name, cap=cap, expected=size
            )
        except _KitRefused as exc:
            return self._ignore(f"kit: {exc}")
        self.daemon.spool.append_event(
            "kit.received", {"name": written, "bytes": total, "sha256": digest}
        )
        text = f"kit received {written} {total} {digest}"
        log.info("phone: %s", text)
        await self.daemon.notifier.answer(KIT_TITLE, text)
        return None

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


class _KitRefused(Exception):
    """A kit download that is not written; the text is the logged reason."""


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
    url: str, directory: Path, name: str, *, cap: int, expected: int
) -> tuple[str, int, str]:
    """Stream `url` into `directory` under `name` (or its first free suffix).

    Answers the name written, the bytes and the sha256. The body is streamed on
    the event loop into a temp file in `directory`; the fsync and the link run in
    a thread. The cap is enforced on the bytes read, whatever `Content-Length`
    or the attachment said, and a body that does not end at `expected` bytes is
    refused. `Accept-Encoding: identity` keeps the bytes counted the bytes
    stored. On any refusal the temp file is removed and nothing is written.
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
                        async with client.stream(
                            "GET", url, headers={"Accept-Encoding": "identity"}
                        ) as response:
                            response.raise_for_status()
                            async for chunk in response.aiter_raw():
                                total += len(chunk)
                                if total > cap:
                                    raise _KitRefused(
                                        f"the download passed [files] kit_max_mb ({cap} bytes)"
                                    )
                                digest.update(chunk)
                                out.write(chunk)
            except httpx.HTTPError as exc:
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
