"""The phone channel — commands from ntfy to handsd (DESIGN §8, §11, §24; H-015).

    handsd ── GET <ntfy_url>/<cmd_topic>/json?since=… ──▶ ntfy   (outbound only)
       ▲                                                   │
       └──────────── one JSON line per message ────────────┘

The daemon subscribes to `[notify] cmd_topic` with a long-poll and accepts five
commands, each ending in its token:

    approve <job> <secret|nonce>
    deny <job> [reason words…] <secret|nonce>
    pause <secret>
    resume <secret>
    status <secret>

**The token.** A typed command carries `cmd_secret` as its last word. A held
job's notification carries Approve/Deny buttons that publish `approve <job>
<nonce>` / `deny <job> <nonce>` to `cmd_topic`, where the nonce is 32 random
bytes (URL-safe base 64, `secrets.token_urlsafe(32)`) minted when the job is
held. The nonce lives in this object's memory only — never in the job record,
an event, the spool or a log line — and it authorizes a decision on that one
job only. It is spent by the decision it authorizes; a wrong token spends
nothing. It is dropped when the job is decided by any route (the daemon calls
`discard` on every `gate.decided`), and with the daemon. `pause`, `resume` and
`status` take the secret only. The secret is compared with
`hmac.compare_digest` and never published: a notification carries only nonces.

**What is answered.** `status` publishes a short summary to `ntfy_topic`.
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
import hmac
import json
import logging
import secrets
import time
from collections import deque
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import TYPE_CHECKING
from urllib.parse import quote

from hands import notify as notify_mod
from hands.api import ApiError
from hands.spool import SpoolError

if TYPE_CHECKING:  # pragma: no cover
    from hands.daemon import Daemon

__all__ = ["BACKOFF_S", "NONCE_BYTES", "STATUS_TITLE", "PhoneChannel", "status_summary"]

log = logging.getLogger("hands.phone")

#: §24: "the nonce is 32 random bytes".
NONCE_BYTES = 32
#: Seconds between reconnects, by consecutive failure; the last one repeats.
#: A line read from the stream resets the count.
BACKOFF_S: tuple[float, ...] = (1.0, 2.0, 5.0, 10.0, 30.0, 60.0)
#: Message ids remembered against a replay. A reconnect asks for what came after
#: the last one, so this only has to cover a server that sends a few again.
SEEN_IDS = 1024
#: The title of the one answer the channel gives.
STATUS_TITLE = "hands: status"

_SECRET_ONLY = ("pause", "resume", "status")
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
                await self.command(text)
        except asyncio.CancelledError:
            raise
        except Exception:  # a bug here must not end the subscription
            log.exception("phone: a command raised")
        finally:
            self.handled += 1

    async def command(self, text: str) -> None:
        """Authenticate and carry out one command; anything else is logged and ignored."""
        words = text.split()
        verb = words[0].lower() if words else ""
        token = words[-1] if words else ""
        if verb in _SECRET_ONLY:
            if len(words) != 2:
                return self._ignore(f"{verb} takes only the secret")
            if not self._is_secret(token):
                return self._ignore(f"{verb}: bad secret")
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


def _failure(exc: BaseException) -> str:
    """The reconnect warning's reason: the exception type and HTTP status only.

    Never the exception's text: httpx puts the request URL in it, and the URL
    carries `cmd_topic`, which reveals the secret (review 8 should-fix 4). An
    exception without a response (a refused connection, a timeout) is its type.
    """
    status = getattr(getattr(exc, "response", None), "status_code", None)
    name = type(exc).__name__
    return f"{name}: HTTP {status}" if isinstance(status, int) else name
