"""Notifications — ntfy, best effort, quiet hours (DESIGN §11, §13).

§11 names four notifications, and no others: `stop`, `job.held`, `max_resumes`
exhausted (which is a `stop` of its own), and daemon start/crash. "Not for
routine progress" is the rule that keeps the phone worth looking at, so nothing
here is wired to a job finishing normally.

Three properties this module exists to hold:

* **Best effort.** A publish that fails is logged and written to the inbox as a
  `notify` event; it never raises into a job and never blocks one. `notify()` is
  a synchronous seam that schedules the delivery and returns, so a caller on the
  job path (the playbook engine, the daemon's inbox listener) pays nothing.
* **Quiet hours delay delivery, never actions** (§11). A notification raised
  inside the window is queued and one flush task delivers the queue at the end
  of the window. The job that raised it has already happened; nothing waits.
* **Nothing here reaches the network on its own terms.** `post` and `clock` and
  `sleep` are injected, so a test drives every branch with a recorder.

The quiet window is the playbook's `[limits] quiet_hours` (§10). §13's config
table has no such key, and `config.py` refuses keys §13 does not list, so the
playbook is the only source hands can read today — see the commit body.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from typing import Any

from hands.config import Config
from hands.spool import Spool

__all__ = [
    "DEFAULT_TEST_MESSAGE",
    "TEST_TITLE",
    "Notification",
    "Notifier",
    "NotifyError",
    "QuietWindow",
    "accepted",
    "http_post",
    "parse_quiet_hours",
    "send_test",
]

log = logging.getLogger("hands.notify")

#: ntfy is a phone notification, not a transfer: a slow one is a failed one.
POST_TIMEOUT_S = 10.0

#: `hands notify --test` with no message of its own (§4).
DEFAULT_TEST_MESSAGE = "hands notify --test: if you can read this, delivery works."
#: The title of that one message, so it is obvious on the phone what it is.
TEST_TITLE = "hands: notify --test"

_WINDOW_RE = re.compile(r"^\s*(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})\s*$")


# ------------------------------------------------------------- quiet hours


@dataclass(frozen=True)
class QuietWindow:
    """A `23:00-07:00` window of local wall-clock time (§10)."""

    start: time
    end: time

    def contains(self, moment: datetime) -> bool:
        """Is `moment` inside the window? The start is in it, the end is not."""
        now = moment.time()
        if self.start == self.end:
            return False  # a zero-width window silences nothing
        if self.start < self.end:
            return self.start <= now < self.end
        return now >= self.start or now < self.end  # the window crosses midnight

    def ends_after(self, moment: datetime) -> float:
        """Seconds from `moment` to the next end of the window."""
        end = moment.replace(
            hour=self.end.hour, minute=self.end.minute, second=0, microsecond=0
        )
        if end <= moment:
            end += timedelta(days=1)
        return (end - moment).total_seconds()


def parse_quiet_hours(text: str | None) -> QuietWindow | None:
    """`"23:00-07:00"` → a window; None for no window and for an unreadable one.

    Unreadable is deliberately *not* an error: a typo in the playbook must not
    silence hands, and it must not stop the pipeline either — the notification is
    delivered at once and the typo is logged.
    """
    if not text:
        return None
    match = _WINDOW_RE.match(text)
    if match is None:
        log.warning("quiet_hours %r is not a HH:MM-HH:MM window; ignoring it", text)
        return None
    values = [int(part) for part in match.groups()]
    if values[0] > 23 or values[2] > 23 or values[1] > 59 or values[3] > 59:
        log.warning("quiet_hours %r is not a clock time; ignoring it", text)
        return None
    return QuietWindow(start=time(values[0], values[1]), end=time(values[2], values[3]))


# ------------------------------------------------------------ the transport


async def http_post(url: str, *, title: str, message: str, transport: Any = None) -> int:
    """Publish one ntfy message; answer with the HTTP status ntfy gave back.

    The only place in hands that speaks to a network. **Any** response is a
    return, 2xx or not: a 403 from ntfy is an answer, and `hands notify --test`
    (§4, §19) exists to print exactly that answer. Judging the code is the
    caller's job — `accepted()` below is how both callers do it — because the two
    callers want different things from a refusal (§11 inboxes it and is quiet;
    `--test` prints it and exits 1). Only a request that got no response at all
    raises here.

    `transport` is a test seam and nothing more: it is handed to the client
    unchanged, so a test can drive this very function through
    `httpx.MockTransport` and prove the status plumbing without a network.

    `httpx` is imported here and not at module scope so that importing `hands`
    — which the CLI does for every command — costs nothing.
    """
    import httpx

    async with httpx.AsyncClient(timeout=POST_TIMEOUT_S, transport=transport) as client:
        response = await client.post(
            url,
            content=message.encode("utf-8"),
            headers={"Title": title, "Tags": "robot"},
        )
    return int(response.status_code)


def accepted(status: Any) -> bool:
    """Did ntfy take the message? A 2xx is a yes; any other number is a no.

    A transport that answered with no status at all — an injected publisher, a
    recorder in a test — has said nothing about the response, and there "it did
    not raise" stays the whole answer, which is the rule §11 has always had.
    """
    if isinstance(status, bool) or not isinstance(status, int):
        return True
    return 200 <= status < 300


class NotifyError(Exception):
    """`hands notify --test` could not send. The one loud failure in this module.

    Everything else here is best effort (§11): a job must never learn that ntfy
    is down. `--test` is the opposite — a human asked, at an install, for proof
    of delivery, and a silent failure would be the one answer that is useless.
    """


async def send_test(
    config: Config, message: str, *, post: Callable[..., Awaitable[Any]] | None = None
) -> dict[str, Any]:
    """One message to the configured topic, now, and the status it got back (§4).

    Deliberately not routed through `Notifier`: quiet hours delay notifications
    and never actions (§11), and a `--test` the human asked for at a terminal is
    an action. The transport underneath is the same `http_post` every §11
    notification uses — that is what makes this a proof of delivery.

    A refusal is **returned, not raised** (§19): `delivered` is False and
    `status` is the code ntfy answered with, so the caller can print the code and
    still fail. `NotifyError` is kept for the two cases that have no code at all
    — nowhere to send to, and nothing answered.
    """
    topic = config.server.ntfy_topic
    if not topic:
        raise NotifyError(
            f"no [server] ntfy_topic in {config.path}: there is nowhere to send to. "
            "Set one (a long random word — anyone who knows it can read your "
            "notifications) and subscribe to it in the ntfy app (§11, §16)."
        )
    url = f"{config.server.ntfy_url.rstrip('/')}/{topic}"
    send = post if post is not None else http_post
    try:
        status = await send(url, title=TEST_TITLE, message=message)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        raise NotifyError(f"{url} did not take the message: {type(exc).__name__}: {exc}") from exc
    delivered = accepted(status)
    if delivered:
        log.info("ntfy test published to %s (%s)", url, status)
    else:
        log.warning("ntfy refused the test message at %s (%s)", url, status)
    return {
        "topic": topic,
        "url": url,
        "title": TEST_TITLE,
        "message": message,
        "status": status,
        "delivered": delivered,
    }


# ---------------------------------------------------------------- notifier


@dataclass
class Notification:
    """One message, with the payload it came from (kept for the inbox record)."""

    title: str
    message: str
    payload: dict[str, Any] = field(default_factory=dict)


class Notifier:
    """The ntfy publisher of §11, with §10's quiet hours in front of it."""

    def __init__(
        self,
        config: Config,
        spool: Spool,
        *,
        post: Callable[..., Awaitable[Any]] | None = None,
        clock: Callable[[], datetime] | None = None,
        sleep: Callable[[float], Awaitable[None]] | None = None,
        quiet_hours: Callable[[], str | None] | None = None,
    ) -> None:
        self.config = config
        self.spool = spool
        #: The transport. None means the real one, looked up at call time so a
        #: test can replace `hands.notify.http_post` wholesale.
        self.post = post
        self.clock = clock or _local_now
        self.sleep: Callable[[float], Awaitable[None]] = sleep or asyncio.sleep
        #: Read at every notification, not once: the playbook (and its
        #: `[limits] quiet_hours`) is re-read whenever a job starts (§10).
        self.quiet_hours = quiet_hours
        #: Raised inside the window, waiting for the flush at its end.
        self.queued: list[Notification] = []
        self._tasks: set[asyncio.Task[None]] = set()
        self._flush: asyncio.Task[None] | None = None

    # ------------------------------------------------------------- the seam

    def notify(self, title: str, payload: dict[str, Any] | None = None) -> None:
        """Raise a notification and return at once (§11: never blocking a job).

        This is the seam the playbook engine and the daemon hold; it is
        deliberately synchronous so neither has to know that delivery is async.
        Quiet hours are decided here and now — only the publish is a task, so a
        caller that looks at `queued` on the next line sees the truth.
        """
        payload = dict(payload or {})
        note = Notification(title=title, message=_message(payload), payload=payload)
        if self._route(note):
            self._spawn(self._publish(note), "hands-notify")

    async def deliver(
        self, title: str, message: str, payload: dict[str, Any] | None = None
    ) -> None:
        """`notify` for a caller that wants to await the publish (the crash path)."""
        note = Notification(title=title, message=message, payload=dict(payload or {}))
        if self._route(note):
            await self._publish(note)

    def _route(self, note: Notification) -> bool:
        """Publish now (True), or queue it for the end of quiet hours (False) (§11)."""
        if not self.config.server.ntfy_topic:
            log.debug("no [server] ntfy_topic; not publishing %r", note.title)
            return False
        window = parse_quiet_hours(self.quiet_hours() if self.quiet_hours else None)
        now = self.clock()
        if window is not None and window.contains(now):
            self.queued.append(note)
            log.info("quiet hours: %r queued until the window ends", note.title)
            self._arm_flush(window.ends_after(now))
            return False
        return True

    # -------------------------------------------------------------- delivery

    async def _publish(self, note: Notification) -> bool:
        """One publish, best effort: a failure is logged and inboxed, never raised."""
        url = f"{self.config.server.ntfy_url.rstrip('/')}/{self.config.server.ntfy_topic}"
        post = self.post if self.post is not None else http_post
        try:
            status = await post(url, title=note.title, message=note.message)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            return self._failed(note, f"{type(exc).__name__}: {exc}")
        # A non-2xx is a failed delivery here too. `http_post` used to raise on
        # one; now it returns the code, so the judgement is made in the open —
        # same outcome for §11, and `--test` gets to print the code (§19).
        if not accepted(status):
            return self._failed(note, f"ntfy answered {status}")
        log.info("ntfy: %s", note.title)
        return True

    def _failed(self, note: Notification, error: str) -> bool:
        """A publish that did not land: logged, written to the inbox, never raised."""
        log.warning("ntfy publish failed: %s", error)
        self.spool.append_event(
            "notify",
            {
                **note.payload,
                "title": note.title,
                "message": note.message,
                "delivered": False,
                "error": error,
            },
        )
        return False

    def _arm_flush(self, seconds: float) -> None:
        """One flush task for the whole queue, armed by the first quiet notification."""
        if self._flush is not None and not self._flush.done():
            return
        self._flush = self._spawn(self._flush_after(seconds), "hands-notify-flush")

    async def _flush_after(self, seconds: float) -> None:
        await self.sleep(seconds)
        pending, self.queued = self.queued, []
        for note in pending:
            await self._publish(note)

    # ----------------------------------------------------------------- tasks

    def _spawn(self, coro: Any, name: str) -> asyncio.Task[None]:
        task = asyncio.ensure_future(coro)
        task.set_name(name)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    async def drain(self) -> None:
        """Wait for every scheduled delivery. For tests and for shutdown."""
        while True:
            pending = [task for task in self._tasks if not task.done()]
            if not pending:
                await asyncio.sleep(0)  # let the done callbacks empty the set
                return
            await asyncio.gather(*pending, return_exceptions=True)

    def cancel_all(self) -> None:
        """Drop every scheduled delivery — the daemon is going down (§3).

        The queue is in memory: a notification quiet hours delayed past the death
        of the daemon is lost, exactly as a phone that was off would lose it.
        """
        for task in list(self._tasks):
            task.cancel()
        self._tasks.clear()
        self._flush = None


def _message(payload: dict[str, Any]) -> str:
    """The human-readable body of a notification, from the event payload it came with."""
    lines: list[str] = []
    for key in ("reason", "message"):
        value = payload.get(key)
        if value:
            lines.append(str(value))
            break
    for key in ("role", "job", "rule", "on"):
        value = payload.get(key)
        if value is not None:
            lines.append(f"{key}: {value}")
    if not lines:
        lines.append(json.dumps(payload, sort_keys=True))
    return "\n".join(lines)


def _local_now() -> datetime:
    """Now, aware, in this machine's timezone — quiet hours are wall-clock hours."""
    return datetime.now().astimezone()
