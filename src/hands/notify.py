"""Notifications — ntfy, best effort, never delayed (DESIGN §11, §13).

§11 names four notifications, and no others: `stop`, `job.held`, `max_resumes`
exhausted (which is a `stop` of its own), and daemon start/crash. "Not for
routine progress" is the rule that keeps the phone worth looking at, so nothing
here is wired to a job finishing normally.

Three properties this module exists to hold:

* **Best effort.** A publish that fails is logged and written to the inbox as a
  `notify` event; it never raises into a job and never blocks one. `notify()` is
  a synchronous seam that schedules the delivery and returns, so a caller on the
  job path (the playbook engine, the daemon's inbox listener) pays nothing.
* **Never delayed** (§11). A notification is published when it is raised;
  nothing is queued for later.
* **Nothing here reaches the network on its own terms.** `post` is injected,
  so a test drives every branch with a recorder.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from hands.config import Config
from hands.spool import Spool

__all__ = [
    "DEFAULT_TEST_MESSAGE",
    "TEST_TITLE",
    "Notification",
    "Notifier",
    "NotifyError",
    "PAIR_SPACING_S",
    "accepted",
    "actions_header",
    "auth_headers",
    "http_post",
    "http_stream",
    "send_test",
    "token_kwargs",
]

log = logging.getLogger("hands.notify")

#: ntfy is a phone notification, not a transfer: a slow one is a failed one.
POST_TIMEOUT_S = 10.0
#: §30 (decision 2026-09-15): ntfy stamps a message with whole seconds, so two
#: publishes made inside one second arrive in no defined order on the phone. When
#: the daemon publishes two notifications for *one cause* — a kit receipt and its
#: held apply, a limit and its resume — it waits this long between them, which is
#: one stamp plus enough margin for the clock. It is not a rate limit: unrelated
#: notifications are never delayed (§11), and nothing queues behind this.
PAIR_SPACING_S = 1.1
#: The command stream is a long poll: ntfy sends a keepalive about every 45 s,
#: so a connection silent for this long is dead and is reconnected (§24).
STREAM_READ_TIMEOUT_S = 120.0

#: `hands notify --test` with no message of its own (§4).
DEFAULT_TEST_MESSAGE = "hands notify --test: if you can read this, delivery works."
#: The title of that one message, so it is obvious on the phone what it is.
TEST_TITLE = "hands: notify --test"


# ------------------------------------------------------------ the transport


def auth_headers(token: str | None) -> dict[str, str]:
    """§33: `Authorization: Bearer <token>` when `[notify] ntfy_token` is set, else
    nothing — a server whose topics are open (ntfy.sh) sees the request it always
    did."""
    return {"Authorization": f"Bearer {token}"} if token else {}


def token_kwargs(token: str | None) -> dict[str, str]:
    """What a caller hands its transport: `token=` only when there is one.

    A transport injected in place of `http_post` / `http_stream` (a test's
    recorder, a fake stream) needs no `token` parameter until a config sets one.
    """
    return {"token": token} if token else {}


async def http_post(
    url: str,
    *,
    title: str,
    message: str,
    actions: list[dict[str, str]] | None = None,
    token: str | None = None,
    transport: Any = None,
) -> int:
    """Publish one ntfy message; answer with the HTTP status ntfy gave back.

    The only place in hands that speaks to a network. **Any** response is a
    return, 2xx or not: a 403 from ntfy is an answer, and `hands notify --test`
    (§4, §19) exists to print exactly that answer. Judging the code is the
    caller's job — `accepted()` below is how both callers do it — because the two
    callers want different things from a refusal (§11 inboxes it and is quiet;
    `--test` prints it and exits 1). Only a request that got no response at all
    raises here.

    `token` is §33's `[notify] ntfy_token`, sent as a bearer when given.
    `transport` is a test seam and nothing more: it is handed to the client
    unchanged, so a test can drive this very function through
    `httpx.MockTransport` and prove the status plumbing without a network.

    `httpx` is imported here and not at module scope so that importing `hands`
    — which the CLI does for every command — costs nothing.
    """
    import httpx

    headers = {"Title": title, "Tags": "robot", **auth_headers(token)}
    if actions:
        headers["Actions"] = actions_header(actions)
    async with httpx.AsyncClient(timeout=POST_TIMEOUT_S, transport=transport) as client:
        response = await client.post(url, content=message.encode("utf-8"), headers=headers)
    return int(response.status_code)


def actions_header(actions: list[dict[str, str]]) -> str:
    """ntfy's `Actions` header, short form: `http, <label>, <url>, method=POST, body=…`.

    Every value hands puts here is a label, a URL and a body of the shape
    `approve <job> <nonce>` — no comma or semicolon in any of them (job ids are
    base 36, the nonce is URL-safe base 64), so no quoting is needed.
    """
    return "; ".join(
        f"http, {a['label']}, {a['url']}, method=POST, body={a['body']}, clear=true"
        for a in actions
    )


async def http_stream(
    url: str, *, token: str | None = None, transport: Any = None
) -> AsyncIterator[str]:
    """One long-poll GET of an ntfy `/json` stream, line by line (§24).

    The command channel's only transport: an outbound connection, no ingress.
    A non-2xx raises; so does a connection that goes quiet for longer than
    `STREAM_READ_TIMEOUT_S` (ntfy sends a keepalive well inside it). The caller
    reconnects. `token` and `transport` are what `http_post` takes: §33's bearer
    on the subscription, and the test seam.
    """
    import httpx

    timeout = httpx.Timeout(POST_TIMEOUT_S, read=STREAM_READ_TIMEOUT_S)
    async with httpx.AsyncClient(timeout=timeout, transport=transport) as client:
        async with client.stream("GET", url, headers=auth_headers(token)) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                yield line


def accepted(status: object) -> bool:
    """Did ntfy take the message? Only an integer 2xx is a yes.

    `http_post` answers with an `int`, and a publisher injected in its place must
    too. Anything else — `None`, a bool, a string — says nothing about a
    response, so it is not a delivery: a transport regression that stops returning
    the code fails loudly (§11 inboxes it, `--test` exits 1) instead of passing
    as sent (review 3 should-fix 6).
    """
    return isinstance(status, int) and not isinstance(status, bool) and 200 <= status < 300


class NotifyError(Exception):
    """`hands notify --test` could not send. The one loud failure in this module.

    Everything else here is best effort (§11): a job must never learn that ntfy
    is down. `--test` is the opposite — a human asked, at an install, for proof
    of delivery, and a silent failure would be the one answer that is useless.
    """


async def send_test(
    config: Config, message: str, *, post: Callable[..., Awaitable[int]] | None = None
) -> dict[str, Any]:
    """One message to the configured topic, now, and the status it got back (§4).

    Not routed through `Notifier`: a `--test` is a status the human reads at the
    terminal, not a §11 notification whose failure goes to the inbox. The
    transport underneath is the same `http_post` every §11 notification uses —
    that is what makes this a proof of delivery.

    A refusal is **returned, not raised** (§19): `delivered` is False and
    `status` is the code ntfy answered with, so the caller can print the code and
    still fail. `NotifyError` is kept for the two cases that have no code at all
    — nowhere to send to, and nothing answered.
    """
    topic = config.server.ntfy_topic
    if not topic:
        raise NotifyError(
            f"no ntfy_topic ([notify], or [server]) in {config.path}: there is nowhere "
            "to send to. "
            "Set one (a long random word — anyone who knows it can read your "
            "notifications) and subscribe to it in the ntfy app (§11, §16)."
        )
    url = f"{config.server.ntfy_url.rstrip('/')}/{topic}"
    send = post if post is not None else http_post
    try:
        status = await send(
            url, title=TEST_TITLE, message=message, **token_kwargs(config.notify.ntfy_token)
        )
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
    #: ntfy action buttons (§24's Approve/Deny on a held job). Kept apart from
    #: `payload` on purpose: a failed delivery inboxes the payload, and the
    #: buttons carry a nonce that must never reach the spool.
    actions: list[dict[str, str]] | None = None
    #: §34: raised during a `hold` but published at once rather than kept (a
    #: `job.held`, with its buttons); `release` hands it back so the start
    #: notification can list it by title, and nobody publishes it a second time.
    published: bool = False


class Notifier:
    """The ntfy publisher of §11. It publishes when asked; nothing is delayed."""

    def __init__(
        self,
        config: Config,
        spool: Spool,
        *,
        post: Callable[..., Awaitable[int]] | None = None,
    ) -> None:
        self.config = config
        self.spool = spool
        #: The transport. None means the real one, looked up at call time so a
        #: test can replace `hands.notify.http_post` wholesale.
        self.post = post
        self._tasks: set[asyncio.Task[None]] = set()
        #: §32: while not None, `notify` keeps what it is asked to publish here
        #: instead (`hold`, `release`) — the daemon's start folds it into its one.
        self._held: list[Notification] | None = None

    # ------------------------------------------------------------- the seam

    def notify(
        self,
        title: str,
        payload: dict[str, Any] | None = None,
        *,
        actions: list[dict[str, str]] | None = None,
        fold: bool = True,
    ) -> None:
        """Raise a notification and return at once (§11: never blocking a job).

        This is the seam the playbook engine and the daemon hold; it is
        deliberately synchronous so neither has to know that delivery is async.

        §34: `fold=False` is a notification a `hold` may not keep — a `job.held`,
        whose buttons a folded line cannot carry. It is published now, hold or not,
        and a hold records it (`published`) so the start can name it.
        """
        payload = dict(payload or {})
        note = Notification(
            title=title, message=_message(payload), payload=payload, actions=actions
        )
        if self._held is not None:
            if fold:
                self._held.append(note)
                return
            note.published = True
            self._held.append(note)
        if self._has_topic(note):
            self._spawn(self._publish(note), "hands-notify")

    def hold(self) -> None:
        """§32: from now until `release`, `notify` keeps each notification instead of
        publishing it. Only the daemon's start holds: "daemon start publishes exactly
        one notification", so what the start itself raises — the stop an orphaned
        consultation's end makes — is folded into that one. §34: a `notify(...,
        fold=False)` (a `job.held`) is published all the same, and only recorded."""
        self._held = []

    def release(self) -> list[Notification]:
        """§32: end a `hold`, and hand back what `notify` kept during it, in order.
        Nothing kept is published by this call; the caller decides. §34: a note
        marked `published` is already out, and is handed back only to be named."""
        held, self._held = self._held or [], None
        return held

    async def answer(self, title: str, message: str) -> bool:
        """A reply to a phone command (§24's `status`), published now.

        Best effort like every publish; with no `ntfy_topic` there is nowhere to
        answer, and nothing is sent.
        """
        if not self.config.server.ntfy_topic:
            log.info("no ntfy_topic; the answer %r has nowhere to go", title)
            return False
        return await self._publish(Notification(title=title, message=message))

    async def deliver(
        self, title: str, message: str, payload: dict[str, Any] | None = None
    ) -> None:
        """`notify` for a caller that wants to await the publish (the crash path)."""
        note = Notification(title=title, message=message, payload=dict(payload or {}))
        if self._has_topic(note):
            await self._publish(note)

    def _has_topic(self, note: Notification) -> bool:
        """Is there a topic to publish to? With none, nothing is sent (§11)."""
        if not self.config.server.ntfy_topic:
            log.debug("no ntfy_topic; not publishing %r", note.title)
            return False
        return True

    # -------------------------------------------------------------- delivery

    async def _publish(self, note: Notification) -> bool:
        """One publish, best effort: a failure is logged and inboxed, never raised."""
        url = f"{self.config.server.ntfy_url.rstrip('/')}/{self.config.server.ntfy_topic}"
        post = self.post if self.post is not None else http_post
        try:
            extra: dict[str, Any] = {"actions": note.actions} if note.actions else {}
            extra.update(token_kwargs(self.config.notify.ntfy_token))
            status = await post(url, title=note.title, message=note.message, **extra)
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

    # ----------------------------------------------------------------- tasks

    def _spawn(self, coro: Any, name: str) -> asyncio.Task[None]:
        task = asyncio.ensure_future(coro)
        task.set_name(name)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    async def drain(self, timeout: float | None = None) -> None:
        """Wait for every scheduled delivery. For tests and for shutdown.

        §34: with `timeout`, stop waiting after that long; nothing is cancelled
        either way (`asyncio.wait` does not cancel what it waits for)."""
        loop = asyncio.get_running_loop()
        deadline = None if timeout is None else loop.time() + float(timeout)
        while True:
            pending = [task for task in self._tasks if not task.done()]
            if not pending:
                await asyncio.sleep(0)  # let the done callbacks empty the set
                return
            remaining = None if deadline is None else deadline - loop.time()
            if remaining is not None and remaining <= 0:
                return
            await asyncio.wait(pending, timeout=remaining)


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
