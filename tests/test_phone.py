"""U4 (mission 8): the phone channel (DESIGN §8, §11, §24; H-015).

Nothing here touches the network. The command stream is a fake ntfy `/json`
stream fed line by line from the test (`FakeNtfy`), the publisher is a recorder
(or the real `http_post` over `httpx.MockTransport`), and the reconnect backoff
is a recorded sleep. The daemon, its socket and the CLI are the real ones, as
in `tests/test_daemon.py`.
"""

from __future__ import annotations

import asyncio
import base64
import itertools
import json
import logging
import time
from functools import partial
from pathlib import Path
from typing import Any

import httpx
import pytest

from conftest import strip_paths
from hands import daemon as daemon_mod
from hands.config import ConfigError, load_config
from hands.daemon import Daemon
from hands.notify import http_post, http_stream
from harness import PROJECT, TIMEOUT, config_body, ok, poll

SECRET = "Xyzzy-PHONE-s3cret-0123456789abcdef"
EVENTS_TOPIC = "hands-events-test"
CMD_TOPIC = "hands-cmd-test"
NTFY = "https://ntfy.example"

NOTIFY = f"""
[notify]
ntfy_url = "{NTFY}"
ntfy_topic = "{EVENTS_TOPIC}"
cmd_topic = "{CMD_TOPIC}"
cmd_secret = "{SECRET}"
"""


@pytest.fixture
def workdir(tmp_path: Path) -> Path:
    d = tmp_path / "work"
    d.mkdir(exist_ok=True)
    return d


@pytest.fixture
def project(tmp_home: Path, workdir: Path) -> str:
    (tmp_home / ".hands" / f"{PROJECT}.toml").write_text(
        config_body(tmp_home, workdir, extra=NOTIFY)
    )
    return PROJECT


# ------------------------------------------------------------- the stand-ins


class FakeNtfy:
    """ntfy's `/json` stream: every GET is recorded; lines come from `push`.

    One queue feeds every connection in turn, so an exception pushed ends the
    current connection and whatever is pushed next is read by the reconnect.
    """

    def __init__(self) -> None:
        self.urls: list[str] = []
        self.queue: asyncio.Queue[Any] = asyncio.Queue()

    def __call__(self, url: str) -> Any:
        self.urls.append(url)
        return self._lines()

    async def _lines(self) -> Any:
        yield json.dumps({"event": "open", "topic": CMD_TOPIC})
        while True:
            item = await self.queue.get()
            if isinstance(item, BaseException):
                raise item
            yield item

    def push(self, item: Any) -> None:
        self.queue.put_nowait(item)


class Recorder:
    """Every publish, with every argument the transport was handed."""

    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    async def __call__(self, url: str, **kwargs: Any) -> int:
        self.sent.append({"url": url, **kwargs})
        return 200

    def titled(self, word: str) -> list[dict[str, Any]]:
        return [item for item in self.sent if word in item["title"]]


_ids = itertools.count(1)


def message(text: str, *, at: int | None = None, msg_id: str | None = None) -> str:
    """One `message` event of ntfy's JSON stream."""
    return json.dumps(
        {
            "id": msg_id or f"msg{next(_ids)}",
            "time": int(time.time()) + 5 if at is None else at,
            "event": "message",
            "topic": CMD_TOPIC,
            "message": text,
        }
    )


async def no_sleep(seconds: float) -> None:
    await asyncio.sleep(0)


def phone_drive(body: Any, posts: Any = None) -> None:
    """A daemon with the channel on, a fake stream and a recording publisher."""

    async def scenario() -> None:
        daemon = Daemon(load_config(PROJECT))
        daemon.notifier.post = posts if posts is not None else Recorder()
        fake = FakeNtfy()
        assert daemon.phone is not None, "the channel is on in this config"
        daemon.phone.stream = fake
        daemon.phone.sleep = no_sleep
        await daemon.start()
        try:
            await asyncio.wait_for(body(daemon, fake), TIMEOUT)
        finally:
            await daemon.stop()

    asyncio.run(scenario())


async def say(daemon: Daemon, fake: FakeNtfy, text: str, **kwargs: Any) -> None:
    """Publish one command to the fake topic and wait until the channel has read it."""
    assert daemon.phone is not None
    before = daemon.phone.handled
    fake.push(message(text, **kwargs))

    async def read() -> bool:
        return daemon.phone is not None and daemon.phone.handled > before

    await poll(read, f"the channel to read {text[:12]!r}")


async def held(prompt: str = "FAKE:result ok") -> dict[str, Any]:
    return await ok("send", "--role", "aux", "--context", "clear", "--gate", "phone test", prompt)


async def nonce_for(daemon: Daemon, job_id: str, verb: str = "approve") -> str:
    """The nonce as the phone gets it: from the held notification's button."""
    posts = daemon.notifier.post

    async def button() -> str | None:
        await daemon.notifier.drain()
        for item in posts.sent:
            for action in item.get("actions") or []:
                words = action["body"].split()
                if words[:2] == [verb, job_id]:
                    return str(words[2])
        return None

    return str(await poll(button, f"the {verb} button of {job_id}"))


async def state(job_id: str) -> str:
    return str((await ok("show", job_id))["state"])


# ------------------------------------------------------------ the commands


def test_approve_with_the_secret_records_decided_by_phone(project: str, tmp_home: Path) -> None:
    async def body(daemon: Daemon, fake: FakeNtfy) -> None:
        job = await held()
        await say(daemon, fake, f"approve {job['id']} {SECRET}")

        record = await ok("show", job["id"])
        assert record["state"] in {"queued", "running", "done"}
        assert record["gate"]["decision"] == "approved"
        assert record["gate"]["decided_by"] == "phone"
        # The record on disk says the same thing, not only the API's view of it.
        on_disk = json.loads((tmp_home / ".hands" / "jobs" / f"{job['id']}.json").read_text())
        assert on_disk["gate"]["decided_by"] == "phone"
        decided = [e for e in (await ok("inbox"))["events"] if e["kind"] == "gate.decided"]
        assert [e["payload"]["decided_by"] for e in decided] == ["phone"]
        assert (await ok("wait", job["id"]))["state"] == "done"

    phone_drive(body)


def test_deny_with_the_secret_carries_the_reason(project: str) -> None:
    async def body(daemon: Daemon, fake: FakeNtfy) -> None:
        job = await held()
        await say(daemon, fake, f"deny {job['id']} not from the train {SECRET}")
        record = await ok("show", job["id"])
        assert record["state"] == "denied"
        assert record["gate"]["decided_by"] == "phone"
        assert record["gate"]["decided_reason"] == "not from the train"

    phone_drive(body)


def test_pause_resume_and_status_with_the_secret(project: str) -> None:
    async def body(daemon: Daemon, fake: FakeNtfy) -> None:
        posts = daemon.notifier.post
        job = await held()

        await say(daemon, fake, f"pause {SECRET}")
        pipeline = await ok("pipeline")
        assert pipeline["paused"] is True
        assert pipeline["paused_by"] == "phone"

        await say(daemon, fake, f"resume {SECRET}")
        assert (await ok("pipeline"))["paused"] is False

        await say(daemon, fake, f"status {SECRET}")
        await daemon.notifier.drain()
        replies = posts.titled("status")
        assert len(replies) == 1, posts.sent
        assert replies[0]["url"] == f"{NTFY}/{EVENTS_TOPIC}"  # §24: answered on ntfy_topic
        assert job["id"] in replies[0]["message"]  # the held job is in the summary
        assert replies[0].get("actions") is None

    phone_drive(body)


def test_a_command_word_may_be_capitalised_by_a_phone_keyboard(project: str) -> None:
    async def body(daemon: Daemon, fake: FakeNtfy) -> None:
        await say(daemon, fake, f"Pause {SECRET}")
        assert (await ok("pipeline"))["paused"] is True

    phone_drive(body)


# --------------------------------------------------------------- the nonce


def test_the_held_notification_carries_approve_and_deny_buttons(project: str) -> None:
    async def body(daemon: Daemon, fake: FakeNtfy) -> None:
        job = await held()
        approve = await nonce_for(daemon, job["id"], "approve")
        deny = await nonce_for(daemon, job["id"], "deny")
        assert approve == deny  # one nonce per held job
        assert len(base64.urlsafe_b64decode(approve + "=" * (-len(approve) % 4))) == 32
        [note] = [item for item in daemon.notifier.post.sent if item.get("actions")]
        assert [a["label"] for a in note["actions"]] == ["Approve", "Deny"]
        assert {a["url"] for a in note["actions"]} == {f"{NTFY}/{CMD_TOPIC}"}
        assert note["url"] == f"{NTFY}/{EVENTS_TOPIC}"

    phone_drive(body)


def test_approve_with_the_nonce_is_single_use(project: str) -> None:
    async def body(daemon: Daemon, fake: FakeNtfy) -> None:
        job = await held()
        nonce = await nonce_for(daemon, job["id"])
        await say(daemon, fake, f"approve {job['id']} {nonce}")
        first = await ok("show", job["id"])
        assert first["gate"]["decided_by"] == "phone"
        assert daemon.phone is not None and daemon.phone.nonces.get(job["id"]) is None

        await say(daemon, fake, f"approve {job['id']} {nonce}")  # a second press
        again = await ok("show", job["id"])
        assert again["gate"]["decided_at"] == first["gate"]["decided_at"]
        decided = [e for e in (await ok("inbox"))["events"] if e["kind"] == "gate.decided"]
        assert len(decided) == 1

    phone_drive(body)


def test_deny_with_the_nonce(project: str) -> None:
    async def body(daemon: Daemon, fake: FakeNtfy) -> None:
        job = await held()
        nonce = await nonce_for(daemon, job["id"], "deny")
        await say(daemon, fake, f"deny {job['id']} {nonce}")
        record = await ok("show", job["id"])
        assert record["state"] == "denied"
        assert record["gate"]["decided_by"] == "phone"
        assert record["gate"]["decided_reason"] is None

    phone_drive(body)


def test_a_nonce_does_not_decide_another_job(project: str) -> None:
    async def body(daemon: Daemon, fake: FakeNtfy) -> None:
        first, second = await held(), await held()
        nonce = await nonce_for(daemon, first["id"])
        await say(daemon, fake, f"approve {second['id']} {nonce}")
        assert await state(second["id"]) == "held"
        # …and the attempt did not spend the nonce on the job it belongs to.
        await say(daemon, fake, f"approve {first['id']} {nonce}")
        assert (await ok("show", first["id"]))["gate"]["decided_by"] == "phone"

    phone_drive(body)


def test_a_wrong_token_is_ignored_answers_nothing_and_keeps_the_nonce(project: str) -> None:
    async def body(daemon: Daemon, fake: FakeNtfy) -> None:
        posts = daemon.notifier.post
        job = await held()
        nonce = await nonce_for(daemon, job["id"])
        await daemon.notifier.drain()
        published = len(posts.sent)

        for text in (
            f"approve {job['id']} {nonce[:-1]}",
            f"approve {job['id']} {SECRET}x",
            f"deny {job['id']} {SECRET.lower()}",
            f"approve {job['id']}",
        ):
            await say(daemon, fake, text)
        await daemon.notifier.drain()

        assert await state(job["id"]) == "held"
        assert len(posts.sent) == published, posts.sent[published:]
        assert daemon.phone is not None and daemon.phone.nonces[job["id"]] == nonce
        await say(daemon, fake, f"approve {job['id']} {nonce}")
        assert (await ok("show", job["id"]))["gate"]["decided_by"] == "phone"

    phone_drive(body)


@pytest.mark.parametrize("decide", ["approve", "deny"])
def test_the_nonce_dies_when_the_job_is_decided_at_the_laptop(project: str, decide: str) -> None:
    async def body(daemon: Daemon, fake: FakeNtfy) -> None:
        job = await held()
        nonce = await nonce_for(daemon, job["id"])
        await ok(decide, job["id"])
        assert daemon.phone is not None and daemon.phone.nonces.get(job["id"]) is None
        await say(daemon, fake, f"deny {job['id']} {nonce}")
        assert (await ok("show", job["id"]))["gate"]["decided_by"] == "cli"

    phone_drive(body)


def test_the_nonce_dies_with_the_daemon(project: str) -> None:
    kept: dict[str, str] = {}

    async def first(daemon: Daemon, fake: FakeNtfy) -> None:
        job = await held()
        kept["job"], kept["nonce"] = job["id"], await nonce_for(daemon, job["id"])

    async def second(daemon: Daemon, fake: FakeNtfy) -> None:
        assert daemon.phone is not None and daemon.phone.nonces == {}
        await say(daemon, fake, f"approve {kept['job']} {kept['nonce']}")
        assert await state(kept["job"]) == "held"
        await say(daemon, fake, f"approve {kept['job']} {SECRET}")  # the secret still works
        assert (await ok("show", kept["job"]))["gate"]["decided_by"] == "phone"

    phone_drive(first)
    phone_drive(second)


def test_pause_resume_and_status_refuse_a_nonce(project: str) -> None:
    async def body(daemon: Daemon, fake: FakeNtfy) -> None:
        posts = daemon.notifier.post
        job = await held()
        nonce = await nonce_for(daemon, job["id"])

        await say(daemon, fake, f"pause {nonce}")
        assert (await ok("pipeline"))["paused"] is False
        await say(daemon, fake, f"status {nonce}")
        await ok("pause")
        await say(daemon, fake, f"resume {nonce}")
        assert (await ok("pipeline"))["paused"] is True
        await daemon.notifier.drain()
        assert posts.titled("status") == []
        assert daemon.phone is not None and daemon.phone.nonces[job["id"]] == nonce

    phone_drive(body)


def test_unknown_malformed_and_not_held_commands_are_ignored(
    project: str, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)

    async def body(daemon: Daemon, fake: FakeNtfy) -> None:
        posts = daemon.notifier.post
        done = await ok("send", "--role", "aux", "--context", "clear", "FAKE:result ok")
        assert (await ok("wait", done["id"]))["state"] == "done"
        await daemon.notifier.drain()
        published = len(posts.sent)

        for text in (
            f"reboot {SECRET}",
            SECRET,
            f"approve {SECRET}",
            f"pause now {SECRET}",
            f"approve {done['id']} {SECRET}",
            f"deny nosuchjob {SECRET}",
            f"approve ../../etc {SECRET}",
            "",
        ):
            await say(daemon, fake, text)
        fake.push("this line is not JSON")
        await say(daemon, fake, f"status {SECRET}")  # the channel is still reading
        await daemon.notifier.drain()

        assert (await ok("show", done["id"]))["gate"] is None
        assert [item["title"] for item in posts.sent[published:]] == ["hands: status"]
        assert (await ok("pipeline"))["paused"] is False

    phone_drive(body)
    assert SECRET not in strip_paths(caplog.text)
    assert "phone" in strip_paths(caplog.text)  # the refusals were logged, not silent


# ---------------------------------------------------------- the stream itself


def test_a_reconnect_resumes_after_the_last_message_without_replaying_it(project: str) -> None:
    async def body(daemon: Daemon, fake: FakeNtfy) -> None:
        posts = daemon.notifier.post
        assert daemon.phone is not None
        started = daemon.phone.started_at
        await poll(_true_when(lambda: len(fake.urls) == 1), "the first connection")
        assert fake.urls[0] == f"{NTFY}/{CMD_TOPIC}/json?since={started}"

        await say(daemon, fake, f"status {SECRET}", msg_id="first")
        fake.push(httpx.ReadError("the connection dropped"))
        await poll(_true_when(lambda: len(fake.urls) == 2), "the reconnect")
        assert fake.urls[1] == f"{NTFY}/{CMD_TOPIC}/json?since=first"

        fake.push(message(f"status {SECRET}", msg_id="first"))  # a server that replays
        await say(daemon, fake, f"status {SECRET}", msg_id="second")
        await daemon.notifier.drain()
        assert len(posts.titled("status")) == 2

    phone_drive(body)


def test_a_stream_that_ends_is_reconnected_with_a_backoff(project: str) -> None:
    delays: list[float] = []

    async def body(daemon: Daemon, fake: FakeNtfy) -> None:
        assert daemon.phone is not None

        async def record(seconds: float) -> None:
            delays.append(seconds)
            await asyncio.sleep(0)

        daemon.phone.sleep = record
        for _ in range(3):
            fake.push(OSError("refused"))
        await poll(_true_when(lambda: len(fake.urls) >= 4), "three reconnects")
        await say(daemon, fake, f"pause {SECRET}")
        assert (await ok("pipeline"))["paused"] is True

    phone_drive(body)
    assert len(delays) >= 3 and all(delay > 0 for delay in delays)


def test_the_reconnect_warning_never_carries_the_topic(
    project: str, caplog: pytest.LogCaptureFixture
) -> None:
    """Review 8 should-fix 4: the type and the status are logged, never the URL."""
    caplog.set_level(logging.DEBUG)
    url = f"{NTFY}/{CMD_TOPIC}/json?since=123"
    request = httpx.Request("GET", url)
    refused = httpx.HTTPStatusError(
        f"Client error '403 Forbidden' for url '{url}'",
        request=request,
        response=httpx.Response(403, request=request),
    )
    unreachable = httpx.ConnectError(f"cannot connect to {url}", request=request)
    assert CMD_TOPIC in strip_paths(str(refused))
    assert CMD_TOPIC in strip_paths(str(unreachable))

    async def body(daemon: Daemon, fake: FakeNtfy) -> None:
        fake.push(refused)
        fake.push(unreachable)
        await poll(_true_when(lambda: len(fake.urls) >= 3), "two reconnects")

    phone_drive(body)
    records = [record for record in caplog.records if record.name == "hands.phone"]
    phone = [strip_paths(record.getMessage()) for record in records]
    reconnects = [line for line in phone if "; reconnecting in " in strip_paths(line)]
    assert len(reconnects) == 2, phone
    for line in phone:
        assert CMD_TOPIC not in strip_paths(line), line
    assert reconnects[0].startswith("phone: HTTPStatusError: HTTP 403;"), reconnects
    assert reconnects[1].startswith("phone: ConnectError;"), reconnects


def test_messages_from_before_the_subscription_are_not_acted_on(project: str) -> None:
    async def body(daemon: Daemon, fake: FakeNtfy) -> None:
        assert daemon.phone is not None and daemon.phone.started_at is not None
        job = await held()
        await say(daemon, fake, f"approve {job['id']} {SECRET}", at=daemon.phone.started_at - 60)
        await say(daemon, fake, f"pause {SECRET}", at=daemon.phone.started_at - 1)
        assert await state(job["id"]) == "held"
        assert (await ok("pipeline"))["paused"] is False

    phone_drive(body)


def test_the_channel_is_cancelled_with_the_daemon(project: str) -> None:
    tasks: list[asyncio.Task[Any]] = []

    async def body(daemon: Daemon, fake: FakeNtfy) -> None:
        assert daemon.phone is not None and daemon.phone.task is not None
        tasks.append(daemon.phone.task)

    phone_drive(body)
    assert tasks and tasks[0].done()


def test_no_channel_means_no_subscription_and_no_buttons(tmp_home: Path, workdir: Path) -> None:
    body_text = config_body(tmp_home, workdir, extra=NOTIFY.split("cmd_topic")[0])
    (tmp_home / ".hands" / f"{PROJECT}.toml").write_text(body_text)

    async def scenario() -> None:
        daemon = Daemon(load_config(PROJECT))
        posts = Recorder()
        daemon.notifier.post = posts
        assert daemon.phone is None
        await daemon.start()
        try:
            await held()
            await daemon.notifier.drain()
        finally:
            await daemon.stop()
        assert posts.titled("held"), posts.sent
        assert all(item.get("actions") is None for item in posts.sent)

    asyncio.run(scenario())


def _true_when(check: Any) -> Any:
    async def probe() -> bool:
        return bool(check())

    return probe


# ------------------------------------------------------------ the transport


def test_http_stream_reads_the_ndjson_lines_of_one_get() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        lines = [json.dumps({"event": "open"}), message(f"status {SECRET}")]
        return httpx.Response(200, content=("\n".join(lines) + "\n").encode())

    async def read() -> list[str]:
        url = f"{NTFY}/{CMD_TOPIC}/json?since=123"
        stream = http_stream(url, transport=httpx.MockTransport(handler))
        return [line async for line in stream]

    got = asyncio.run(read())
    assert [json.loads(line)["event"] for line in got] == ["open", "message"]
    assert seen[0].method == "GET"
    assert str(seen[0].url) == f"{NTFY}/{CMD_TOPIC}/json?since=123"


def test_http_stream_raises_on_a_refusal_so_the_channel_reconnects() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403)

    async def read() -> None:
        async for _ in http_stream(f"{NTFY}/x/json", transport=httpx.MockTransport(handler)):
            pass

    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(read())


# ------------------------------------------- the secret is never published


def test_the_secret_never_appears_in_any_notification(
    project: str, tmp_home: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """§24: "the long-term secret is never placed in a notification".

    Every publish goes through the real `http_post` over `httpx.MockTransport`,
    so what is checked is the request on the wire — URL, every header (the
    `Actions` header included) and the body. The scenario raises every kind of
    notification the daemon sends: daemon start, `job.held` with its buttons,
    the `stop` of a phone pause and of a playbook stop, a status reply, a
    `notify --test` through the API, and the crash notification. The spool and
    the log are checked too, and so is the nonce, which must be in exactly the
    held notification and nowhere on disk or in the log.
    """
    caplog.set_level(logging.DEBUG)
    wire: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        wire.append(request)
        return httpx.Response(200)

    transport = httpx.MockTransport(handler)
    nonces: list[str] = []

    recorder = Recorder()

    async def post(url: str, **kwargs: Any) -> int:
        await recorder(url, **kwargs)
        return await http_post(url, transport=transport, **kwargs)

    post.sent = recorder.sent  # type: ignore[attr-defined]

    async def body(daemon: Daemon, fake: FakeNtfy) -> None:
        first = await held()
        nonces.append(await nonce_for(daemon, first["id"]))
        second = await held()
        await say(daemon, fake, f"approve {first['id']} {nonces[0]}")
        await say(daemon, fake, f"deny {second['id']} not this one {SECRET}")
        await say(daemon, fake, f"pause {SECRET}")
        await say(daemon, fake, f"status {SECRET}")
        await say(daemon, fake, f"resume {SECRET}")
        await daemon.playbook.stop("a playbook stop")
        await daemon.api.notify(test="a notify --test")
        await ok("wait", first["id"])
        await daemon.notifier.drain()

    phone_drive(body, posts=post)
    monkeypatch.setattr("hands.notify.http_post", partial(http_post, transport=transport))
    daemon_mod._notify_crash(load_config(PROJECT), RuntimeError("boom"))

    titles = [request.headers.get("Title", "") for request in wire]
    for kind in ("started", "held", "stopped", "status", "notify --test", "crashed"):
        assert any(kind in strip_paths(title) for title in titles), (kind, titles)
    with_buttons = [request for request in wire if "Actions" in request.headers]
    assert len(with_buttons) == 2  # both held jobs
    assert any(nonces[0] in request.headers["Actions"] for request in with_buttons)

    for request in wire:
        assert SECRET not in strip_paths(str(request.url))
        for name, value in request.headers.raw:
            header = (name + b": " + value).decode("latin-1")
            assert SECRET not in strip_paths(header), header
        assert SECRET not in strip_paths(request.content.decode("utf-8", "replace"))
    for path in (tmp_home / ".hands").rglob("*"):
        if path.is_file() and path.suffix != ".toml":
            data = path.read_text(encoding="utf-8", errors="replace")
            assert SECRET not in strip_paths(data), path
            assert nonces[0] not in strip_paths(data), path
    assert SECRET not in strip_paths(caplog.text)
    assert nonces[0] not in strip_paths(caplog.text)


# ------------------------------------------------------------------ config


def test_cmd_topic_without_a_secret_is_refused(tmp_home: Path, workdir: Path) -> None:
    text = config_body(tmp_home, workdir, extra=NOTIFY.replace(f'cmd_secret = "{SECRET}"', ""))
    (tmp_home / ".hands" / f"{PROJECT}.toml").write_text(text)
    with pytest.raises(ConfigError, match="cmd_secret"):
        load_config(PROJECT)


def test_a_secret_with_a_blank_inside_is_refused(tmp_home: Path, workdir: Path) -> None:
    """The token is a command's last word: a secret with a blank could never match."""
    text = config_body(tmp_home, workdir, extra=NOTIFY.replace(SECRET, "two words"))
    (tmp_home / ".hands" / f"{PROJECT}.toml").write_text(text)
    with pytest.raises(ConfigError, match="cmd_secret") as exc:
        load_config(PROJECT)
    assert "two words" not in strip_paths(str(exc.value))  # a refusal never prints the secret


def test_the_command_topic_must_not_be_the_events_topic(tmp_home: Path, workdir: Path) -> None:
    text = config_body(tmp_home, workdir, extra=NOTIFY.replace(CMD_TOPIC, EVENTS_TOPIC))
    (tmp_home / ".hands" / f"{PROJECT}.toml").write_text(text)
    with pytest.raises(ConfigError, match="cmd_topic"):
        load_config(PROJECT)


def test_notify_keys_load_and_the_secret_is_not_in_the_repr(project: str) -> None:
    config = load_config(PROJECT)
    assert config.notify.channel is True
    assert config.notify.cmd_topic == CMD_TOPIC and config.notify.cmd_secret == SECRET
    assert config.server.ntfy_topic == EVENTS_TOPIC and config.server.ntfy_url == NTFY
    assert SECRET not in strip_paths(repr(config))


def test_the_server_section_still_carries_the_ntfy_keys(tmp_home: Path, workdir: Path) -> None:
    text = config_body(tmp_home, workdir).replace(
        "[server]", f'[server]\nntfy_topic = "{EVENTS_TOPIC}"\nntfy_url = "{NTFY}"'
    )
    (tmp_home / ".hands" / f"{PROJECT}.toml").write_text(text)
    config = load_config(PROJECT)
    assert config.notify.ntfy_topic == EVENTS_TOPIC == config.server.ntfy_topic
    assert config.notify.ntfy_url == NTFY
    assert config.notify.channel is False


def test_the_same_ntfy_key_in_both_sections_is_refused(tmp_home: Path, workdir: Path) -> None:
    text = config_body(tmp_home, workdir, extra=NOTIFY).replace(
        "[server]", '[server]\nntfy_topic = "hands-other"'
    )
    (tmp_home / ".hands" / f"{PROJECT}.toml").write_text(text)
    with pytest.raises(ConfigError, match=r"both \[server\] and \[notify\]"):
        load_config(PROJECT)


def test_who_topics_are_parsed(tmp_home: Path, workdir: Path) -> None:
    extra = NOTIFY + 'who_topic = "hands-who"\nwho_cmd_topic = "hands-who-cmd"\n'
    (tmp_home / ".hands" / f"{PROJECT}.toml").write_text(
        config_body(tmp_home, workdir, extra=extra)
    )
    config = load_config(PROJECT)
    assert config.notify.who_topic == "hands-who"
    assert config.notify.who_cmd_topic == "hands-who-cmd"
