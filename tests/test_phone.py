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
import hashlib
import itertools
import json
import logging
import threading
import time
from collections.abc import Iterator
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import httpx
import pytest

from conftest import commit_file, strip_paths
from hands import daemon as daemon_mod
from hands.config import ConfigError, load_config
from hands.daemon import Daemon
from hands.notify import http_post, http_stream
from hands.phone import GO_TITLE, KIT_TITLE
from harness import PROJECT, TIMEOUT, config_body, ok, poll, running_job

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


def message(
    text: str,
    *,
    at: int | None = None,
    msg_id: str | None = None,
    attachment: Any = None,
) -> str:
    """One `message` event of ntfy's JSON stream, with an `attachment` when given."""
    event = {
        "id": msg_id or f"msg{next(_ids)}",
        "time": int(time.time()) + 5 if at is None else at,
        "event": "message",
        "topic": CMD_TOPIC,
        "message": text,
    }
    if attachment is not None:
        event["attachment"] = attachment
    return json.dumps(event)


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
        # §25: the job is still held, so it has a nonce again — a fresh one.
        assert daemon.phone is not None and set(daemon.phone.nonces) == {kept["job"]}
        assert daemon.phone.nonces[kept["job"]] != kept["nonce"]
        await say(daemon, fake, f"approve {kept['job']} {kept['nonce']}")
        assert await state(kept["job"]) == "held"
        await say(daemon, fake, f"approve {kept['job']} {SECRET}")  # the secret still works
        assert (await ok("show", kept["job"]))["gate"]["decided_by"] == "phone"

    phone_drive(first)
    phone_drive(second)


def test_a_restart_re_sends_each_held_job_with_a_fresh_nonce(project: str) -> None:
    """§25: "nonces are re-minted for every job still `held` and their
    notifications re-sent with fresh buttons" (FINAL-REPORT-8 §5 item 5).

    Two daemons over the same spool, each through `Daemon.start()`. The first
    leaves two jobs held, one approved (decided, then done) and one never gated
    (done). The second publishes one held notification per held job, with
    buttons whose nonce is new; the old nonce is refused, the new one decides.
    """
    kept: dict[str, Any] = {}

    async def first(daemon: Daemon, fake: FakeNtfy) -> None:
        one, two, decided = await held(), await held(), await held()
        kept["held"] = [one["id"], two["id"]]
        kept["old"] = {job: await nonce_for(daemon, job) for job in kept["held"]}
        await ok("approve", decided["id"])
        plain = await ok("send", "--role", "aux", "--context", "clear", "FAKE:result ok")
        kept["other"] = [decided["id"], plain["id"]]
        for job in kept["other"]:
            assert (await ok("wait", job))["state"] == "done"

    async def second(daemon: Daemon, fake: FakeNtfy) -> None:
        posts = daemon.notifier.post
        await daemon.notifier.drain()
        resent = posts.titled("held")
        buttons = {
            action["body"].split()[1]: action["body"].split()[2]
            for item in resent
            for action in item.get("actions") or []
        }
        assert len(resent) == 2, posts.sent  # one publish per held job, none for the others
        assert set(buttons) == set(kept["held"])
        for item in resent:
            assert item["url"] == f"{NTFY}/{EVENTS_TOPIC}"
            assert [a["label"] for a in item["actions"]] == ["Approve", "Deny"]
            assert SECRET not in strip_paths(json.dumps(item))  # §24: never the secret
        for job in kept["held"]:
            assert buttons[job] != kept["old"][job]
            assert daemon.phone is not None and daemon.phone.nonces[job] == buttons[job]

        one, two = kept["held"]
        await say(daemon, fake, f"approve {one} {kept['old'][one]}")  # the old button
        assert await state(one) == "held"
        await say(daemon, fake, f"approve {one} {buttons[one]}")  # the re-sent button
        record = await ok("show", one)
        assert record["gate"]["decision"] == "approved"
        assert record["gate"]["decided_by"] == "phone"
        assert daemon.phone is not None and daemon.phone.nonces.get(one) is None
        await say(daemon, fake, f"deny {two} {buttons[one]}")  # bound to its own job
        assert await state(two) == "held"
        await say(daemon, fake, f"deny {two} {buttons[two]}")
        assert (await ok("show", two))["gate"]["decided_by"] == "phone"
        assert await state(two) == "denied"

    phone_drive(first)
    phone_drive(second)


def test_a_restart_without_held_jobs_re_sends_nothing(project: str) -> None:
    async def first(daemon: Daemon, fake: FakeNtfy) -> None:
        job = await held()
        await ok("deny", job["id"])

    async def second(daemon: Daemon, fake: FakeNtfy) -> None:
        await daemon.notifier.drain()
        assert daemon.notifier.post.titled("held") == []
        assert all(item.get("actions") is None for item in daemon.notifier.post.sent)
        assert daemon.phone is not None and daemon.phone.nonces == {}

    phone_drive(first)
    phone_drive(second)


def test_without_the_channel_a_restart_re_sends_no_held_notification(
    tmp_home: Path, workdir: Path
) -> None:
    """The simplest consistent reading of §25 where it is silent: the re-send
    replaces buttons that died with the old daemon. Without `cmd_topic` the held
    notification never had buttons, nothing died, and nothing is re-sent."""
    body_text = config_body(tmp_home, workdir, extra=NOTIFY.split("cmd_topic")[0])
    (tmp_home / ".hands" / f"{PROJECT}.toml").write_text(body_text)

    async def once(hold: bool) -> Recorder:
        daemon = Daemon(load_config(PROJECT))
        posts = Recorder()
        daemon.notifier.post = posts
        await daemon.start()
        try:
            if hold:
                await held()
            await daemon.notifier.drain()
        finally:
            await daemon.stop()
        return posts

    before = asyncio.run(once(hold=True))
    assert len(before.titled("held")) == 1
    after = asyncio.run(once(hold=False))
    assert after.titled("held") == [], after.sent
    assert after.titled("started"), after.sent


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


# ------------------------------------------------------------- go (§26)

KICKOFF = "FAKE:result VERDICT: go ran"


def with_playbook(workdir: Path, series: str = f'[series]\nkickoff = "{KICKOFF}"\n',
                  rules: str = "") -> None:
    """A committed playbook in the builder's cwd (§10: only the committed file loads)."""
    commit_file(workdir, "PLAYBOOK.toml", f"version = 1\n{series}\n{rules}")


def go_answers(daemon: Daemon) -> list[dict[str, Any]]:
    return [item for item in daemon.notifier.post.sent if item["title"] == GO_TITLE]


def assert_refused(caplog: pytest.LogCaptureFixture, why: str) -> None:
    assert f"phone: command ignored (go: {why}" in strip_paths(caplog.text), caplog.text
    assert SECRET not in strip_paths(caplog.text)


def test_go_sends_the_kickoff_to_the_builder_with_origin_phone_and_answers_the_job_id(
    project: str, workdir: Path, tmp_home: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    with_playbook(workdir)

    async def body(daemon: Daemon, fake: FakeNtfy) -> None:
        await say(daemon, fake, f"go {SECRET}")
        (row,) = (await ok("jobs"))["jobs"]
        record = await ok("show", row["id"])
        assert record["prompt"] == KICKOFF
        assert (record["role"], record["context"], record["origin"]) == (
            "builder", "clear", "phone",
        )
        assert (await ok("wait", row["id"]))["state"] == "done"
        await daemon.notifier.drain()
        (answer,) = go_answers(daemon)
        assert answer["url"] == f"{NTFY}/{EVENTS_TOPIC}"  # answered on ntfy_topic
        assert row["id"] in answer["message"]
        assert answer.get("actions") is None
        for item in daemon.notifier.post.sent:
            assert SECRET not in strip_paths(json.dumps(item, default=str)), item
        for path in (tmp_home / ".hands").rglob("*"):
            if path.is_file() and path.suffix != ".toml":
                data = path.read_text(encoding="utf-8", errors="replace")
                assert SECRET not in strip_paths(data), path

    phone_drive(body)
    assert SECRET not in strip_paths(caplog.text)


def test_go_is_refused_with_no_playbook(
    project: str, workdir: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)

    async def body(daemon: Daemon, fake: FakeNtfy) -> None:
        await say(daemon, fake, f"go {SECRET}")
        await daemon.notifier.drain()
        assert (await ok("jobs"))["jobs"] == []
        assert go_answers(daemon) == []

    phone_drive(body)
    assert_refused(caplog, "no playbook is loaded")


def test_go_is_refused_when_the_playbook_has_no_kickoff(
    project: str, workdir: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    with_playbook(workdir, series='series = "no-kickoff"\n')

    async def body(daemon: Daemon, fake: FakeNtfy) -> None:
        await say(daemon, fake, f"go {SECRET}")
        await daemon.notifier.drain()
        assert (await ok("jobs"))["jobs"] == []
        assert go_answers(daemon) == []

    phone_drive(body)
    assert_refused(caplog, "the playbook has no [series] kickoff")


def test_go_is_refused_while_the_builder_runs_a_job(
    project: str, workdir: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    with_playbook(workdir)

    async def body(daemon: Daemon, fake: FakeNtfy) -> None:
        busy = await ok("send", "--role", "builder", "--context", "clear", "FAKE:block")
        assert (await running_job())["id"] == busy["id"]
        await say(daemon, fake, f"go {SECRET}")
        await daemon.notifier.drain()
        assert [row["id"] for row in (await ok("jobs"))["jobs"]] == [busy["id"]]
        assert go_answers(daemon) == []
        await ok("cancel", busy["id"])

    phone_drive(body)
    assert_refused(caplog, "the builder has a job running")


def test_go_is_refused_while_the_builder_has_a_job_queued(
    project: str, workdir: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Queued and not yet running: the command is handed straight to the channel
    after the enqueue, with no await between, so the worker has not taken it."""
    caplog.set_level(logging.DEBUG)
    with_playbook(workdir)

    async def body(daemon: Daemon, fake: FakeNtfy) -> None:
        assert daemon.phone is not None
        queued = daemon.enqueue(
            role="builder", context="clear", prompt="FAKE:result ok", origin="cli"
        )
        assert daemon.running_job_id("builder") is None
        await daemon.phone.command(f"go {SECRET}")
        await ok("wait", queued.id)
        await daemon.notifier.drain()
        assert [row["id"] for row in (await ok("jobs"))["jobs"]] == [queued.id]
        assert go_answers(daemon) == []

    phone_drive(body)
    assert_refused(caplog, "the builder has a job queued")


def test_go_with_a_bad_or_missing_secret_or_a_nonce_is_refused(
    project: str, workdir: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    with_playbook(workdir)

    async def body(daemon: Daemon, fake: FakeNtfy) -> None:
        job = await held()
        nonce = await nonce_for(daemon, job["id"])
        for text in ("go", "go not-the-secret", f"go {nonce}", f"go now {SECRET}"):
            await say(daemon, fake, text)
        await daemon.notifier.drain()
        assert [row["id"] for row in (await ok("jobs"))["jobs"]] == [job["id"]]
        assert go_answers(daemon) == []

    phone_drive(body)
    assert_refused(caplog, "bad secret")
    assert "phone: command ignored (go takes only the secret)" in strip_paths(caplog.text)


def test_go_after_a_stop_un_pauses_when_its_job_starts_and_the_done_fires_a_rule(
    project: str, workdir: Path
) -> None:
    """H-018 gap 2: a paused playbook is still loaded, so `go` is accepted; its job
    clears the stop when it starts, and its `builder.done` then fires a rule."""
    with_playbook(
        workdir,
        rules='[[rule]]\non = "builder.done"\nverdict = \'^VERDICT: go ran\'\n'
        'then = "notify"\nmessage = "the go chained"\n',
    )

    async def body(daemon: Daemon, fake: FakeNtfy) -> None:
        await ok("pause")
        assert (await ok("pipeline"))["paused"] is True
        await say(daemon, fake, f"go {SECRET}")
        (row,) = (await ok("jobs"))["jobs"]
        assert row["origin"] == "phone"
        assert (await ok("wait", row["id"]))["state"] == "done"

        async def fired() -> list[dict[str, Any]] | None:
            events = (await ok("inbox"))["events"]
            rules = [event for event in events if event["kind"] == "playbook.rule"]
            return events if rules else None

        events = await poll(fired, "the builder.done rule to fire")
        resumed = [event for event in events if event["kind"] == "pipeline.resumed"]
        assert [event["payload"]["by"] for event in resumed] == ["start"]
        (rule,) = [event for event in events if event["kind"] == "playbook.rule"]
        assert rule["payload"]["job"] == row["id"]
        assert (await ok("pipeline"))["paused"] is False

    phone_drive(body)


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


# ------------------------------------------------------ kit transport (§26)

MIB = 1024 * 1024
#: An empty zip archive's end record and some bytes: what is moved is bytes.
ZIP = b"PK\x05\x06" + bytes(18) + bytes(range(256)) * 40


class KitServer:
    """ntfy's attachment host, as a real socket on 127.0.0.1 (stdlib, in a thread).

    `files` maps a request path to the bytes served there; `hits` records every
    GET, so a test can prove a refused kit never reached the server. With
    `release` set, a GET waits on it before answering — a download in flight.
    """

    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}
        self.hits: list[str] = []
        self.release: threading.Event | None = None
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802 - http.server's name
                owner.hits.append(self.path)
                if owner.release is not None:
                    owner.release.wait(TIMEOUT)
                body = owner.files.get(self.path)
                if body is None:
                    self.send_response(404)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/zip")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                try:
                    self.wfile.write(body)
                except OSError:  # the client stopped reading at the cap
                    pass

            def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
                pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.httpd.daemon_threads = True
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def url(self, path: str) -> str:
        return f"http://127.0.0.1:{self.httpd.server_address[1]}{path}"

    def attach(self, name: Any, body: bytes, **fields: Any) -> dict[str, Any]:
        """ntfy's `attachment` object for `body`, served at a path of the server's own."""
        path = f"/file/k{next(_ids)}.zip"
        self.files[path] = body
        attachment = {
            "name": name,
            "type": "application/zip",
            "size": len(body),
            "expires": int(time.time()) + 3600,
            "url": self.url(path),
        }
        attachment.update(fields)
        return {key: value for key, value in attachment.items() if value is not ...}


@pytest.fixture
def kit_server() -> Iterator[KitServer]:
    server = KitServer()
    server.thread.start()
    try:
        yield server
    finally:
        if server.release is not None:
            server.release.set()
        server.httpd.shutdown()
        server.httpd.server_close()


@pytest.fixture
def downloads(tmp_home: Path) -> Path:
    d = tmp_home / "Downloads"
    d.mkdir()
    return d


def kit_config(tmp_home: Path, workdir: Path, files: str) -> None:
    (tmp_home / ".hands" / f"{PROJECT}.toml").write_text(
        config_body(tmp_home, workdir, extra=f"{NOTIFY}\n[files]\n{files}\n")
    )


@pytest.fixture
def kit_project(tmp_home: Path, workdir: Path, downloads: Path) -> str:
    kit_config(
        tmp_home,
        workdir,
        f'allowed_roots = ["{workdir}", "{downloads}"]\nkit_dir = "{downloads}"\nkit_max_mb = 1\n',
    )
    return PROJECT


def kit_answers(daemon: Daemon) -> list[dict[str, Any]]:
    return [item for item in daemon.notifier.post.sent if item["title"] == KIT_TITLE]


def kit_events(daemon: Daemon) -> list[dict[str, Any]]:
    return [event.payload for event in daemon.spool.events() if event.kind == "kit.received"]


def assert_kit_refused(caplog: pytest.LogCaptureFixture, why: str) -> None:
    assert f"phone: command ignored (kit{why}" in strip_paths(caplog.text), caplog.text
    assert SECRET not in strip_paths(caplog.text)


def assert_no_secret_anywhere(daemon: Daemon, tmp_home: Path) -> None:
    for item in daemon.notifier.post.sent:
        assert SECRET not in strip_paths(json.dumps(item, default=str)), item
    for path in (tmp_home / ".hands").rglob("*"):
        if path.is_file() and path.suffix != ".toml":
            data = path.read_text(encoding="utf-8", errors="replace")
            assert SECRET not in strip_paths(data), path


def test_a_kit_is_written_to_kit_dir_inboxed_and_notified_with_its_sha256(
    kit_project: str,
    downloads: Path,
    kit_server: KitServer,
    tmp_home: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    digest = hashlib.sha256(ZIP).hexdigest()

    async def body(daemon: Daemon, fake: FakeNtfy) -> None:
        attachment = kit_server.attach("mission-11.zip", ZIP)
        await say(daemon, fake, f"kit {SECRET}", attachment=attachment)
        await daemon.notifier.drain()
        assert len(kit_server.hits) == 1
        # the file, and nothing else: no temp file is left beside it
        assert [path.name for path in downloads.iterdir()] == ["mission-11.zip"]
        written = downloads / "mission-11.zip"
        assert written.read_bytes() == ZIP
        assert written.stat().st_mode & 0o111 == 0  # never made executable
        assert kit_events(daemon) == [
            {"name": "mission-11.zip", "bytes": len(ZIP), "sha256": digest}
        ]
        (answer,) = kit_answers(daemon)
        assert answer["url"] == f"{NTFY}/{EVENTS_TOPIC}"  # on ntfy_topic
        assert answer["message"] == f"kit received mission-11.zip {len(ZIP)} {digest}"
        assert answer.get("actions") is None
        assert (await ok("jobs"))["jobs"] == []  # a kit starts nothing
        assert_no_secret_anywhere(daemon, tmp_home)

    phone_drive(body)
    assert SECRET not in strip_paths(caplog.text)


def test_a_kit_over_kit_max_mb_by_its_reported_size_is_refused_before_the_fetch(
    kit_project: str, downloads: Path, kit_server: KitServer, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)

    async def body(daemon: Daemon, fake: FakeNtfy) -> None:
        attachment = kit_server.attach("big.zip", ZIP, size=MIB + 1)
        await say(daemon, fake, f"kit {SECRET}", attachment=attachment)
        await daemon.notifier.drain()
        assert kit_server.hits == []  # the server was never asked
        assert list(downloads.iterdir()) == []
        assert kit_events(daemon) == [] and kit_answers(daemon) == []

    phone_drive(body)
    assert_kit_refused(caplog, f": the attachment is {MIB + 1} bytes, over [files] kit_max_mb")


@pytest.mark.parametrize(
    "reported,served,why",
    [
        (10, MIB + 1, ": the download passed [files] kit_max_mb"),
        (len(ZIP) + 1, len(ZIP), f": the download is {len(ZIP)} bytes, not the {len(ZIP) + 1}"),
    ],
    ids=["over-the-cap-while-streaming", "shorter-than-reported"],
)
def test_a_download_that_does_not_match_its_reported_size_is_refused_and_leaves_nothing(
    kit_project: str,
    downloads: Path,
    kit_server: KitServer,
    caplog: pytest.LogCaptureFixture,
    reported: int,
    served: int,
    why: str,
) -> None:
    caplog.set_level(logging.DEBUG)

    async def body(daemon: Daemon, fake: FakeNtfy) -> None:
        attachment = kit_server.attach("liar.zip", bytes(served), size=reported)
        await say(daemon, fake, f"kit {SECRET}", attachment=attachment)
        await daemon.notifier.drain()
        assert len(kit_server.hits) == 1
        assert list(downloads.iterdir()) == []  # neither the kit nor its temp file
        assert kit_events(daemon) == [] and kit_answers(daemon) == []

    phone_drive(body)
    assert_kit_refused(caplog, why)


@pytest.mark.parametrize(
    "name",
    [
        "../evil.zip", "sub/kit.zip", "sub\\kit.zip", "/abs/kit.zip", "..", ".zip",
        ".hidden.zip", "kit.tar.gz", "kit.zip.sh", "kit.ZIP", "kit\n.zip", "", None, 7,
    ],
)  # fmt: skip
def test_a_kit_whose_name_is_not_a_zip_basename_is_refused_before_the_fetch(
    kit_project: str,
    downloads: Path,
    kit_server: KitServer,
    caplog: pytest.LogCaptureFixture,
    name: Any,
) -> None:
    caplog.set_level(logging.DEBUG)

    async def body(daemon: Daemon, fake: FakeNtfy) -> None:
        attachment = kit_server.attach(name, ZIP)
        await say(daemon, fake, f"kit {SECRET}", attachment=attachment)
        await daemon.notifier.drain()
        assert kit_server.hits == []
        assert list(downloads.iterdir()) == []
        assert list(downloads.parent.glob("*.zip")) == []  # nothing escaped either
        assert kit_events(daemon) == [] and kit_answers(daemon) == []

    phone_drive(body)
    assert_kit_refused(caplog, ": the attachment name is not a .zip basename")


def test_a_kit_whose_name_exists_gets_the_first_free_suffix_and_the_original_is_intact(
    kit_project: str, downloads: Path, kit_server: KitServer
) -> None:
    (downloads / "kit.zip").write_bytes(b"the original")
    second, third = ZIP + b"2", ZIP + b"3"

    async def body(daemon: Daemon, fake: FakeNtfy) -> None:
        await say(daemon, fake, f"kit {SECRET}", attachment=kit_server.attach("kit.zip", second))
        await say(daemon, fake, f"kit {SECRET}", attachment=kit_server.attach("kit.zip", third))
        await daemon.notifier.drain()
        assert sorted(path.name for path in downloads.iterdir()) == [
            "kit-1.zip", "kit-2.zip", "kit.zip",
        ]  # fmt: skip
        assert (downloads / "kit.zip").read_bytes() == b"the original"
        assert (downloads / "kit-1.zip").read_bytes() == second
        assert (downloads / "kit-2.zip").read_bytes() == third
        assert [event["name"] for event in kit_events(daemon)] == ["kit-1.zip", "kit-2.zip"]
        messages = [answer["message"] for answer in kit_answers(daemon)]
        assert [text.split()[2] for text in messages] == ["kit-1.zip", "kit-2.zip"]

    phone_drive(body)


def test_a_kit_with_a_missing_or_wrong_secret_is_refused_before_the_fetch(
    kit_project: str, downloads: Path, kit_server: KitServer, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)

    async def body(daemon: Daemon, fake: FakeNtfy) -> None:
        for text in ("kit", "kit not-the-secret", f"kit now {SECRET}"):
            await say(daemon, fake, text, attachment=kit_server.attach("kit.zip", ZIP))
        await daemon.notifier.drain()
        assert kit_server.hits == []
        assert list(downloads.iterdir()) == []
        assert kit_events(daemon) == [] and kit_answers(daemon) == []

    phone_drive(body)
    assert_kit_refused(caplog, ": bad secret")
    assert "phone: command ignored (kit takes only the secret)" in strip_paths(caplog.text)


@pytest.mark.parametrize(
    "fields,why",
    [
        (None, ": the message carries no attachment"),
        ({"size": ...}, ": the attachment reports no size in bytes"),
        ({"size": "12"}, ": the attachment reports no size in bytes"),
        ({"size": 12.5}, ": the attachment reports no size in bytes"),
        ({"size": True}, ": the attachment reports no size in bytes"),
        ({"size": -1}, ": the attachment reports no size in bytes"),
        ({"url": ...}, ": the attachment has no http(s) url"),
        ({"url": "file:///etc/passwd"}, ": the attachment has no http(s) url"),
    ],
    ids=["no-attachment", "no-size", "str-size", "float-size", "bool-size", "negative-size",
         "no-url", "file-url"],
)  # fmt: skip
def test_a_kit_without_an_attachment_a_size_or_an_http_url_is_refused_before_the_fetch(
    kit_project: str,
    downloads: Path,
    kit_server: KitServer,
    caplog: pytest.LogCaptureFixture,
    fields: dict[str, Any] | None,
    why: str,
) -> None:
    caplog.set_level(logging.DEBUG)

    async def body(daemon: Daemon, fake: FakeNtfy) -> None:
        attachment = None if fields is None else kit_server.attach("kit.zip", ZIP, **fields)
        await say(daemon, fake, f"kit {SECRET}", attachment=attachment)
        await daemon.notifier.drain()
        assert kit_server.hits == []
        assert list(downloads.iterdir()) == []
        assert kit_events(daemon) == [] and kit_answers(daemon) == []

    phone_drive(body)
    assert_kit_refused(caplog, why)


def test_a_kit_is_refused_when_kit_dir_is_outside_the_allowed_roots(
    tmp_home: Path,
    workdir: Path,
    downloads: Path,
    kit_server: KitServer,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    kit_config(tmp_home, workdir, f'allowed_roots = ["{workdir}"]\nkit_dir = "{downloads}"\n')

    async def body(daemon: Daemon, fake: FakeNtfy) -> None:
        await say(daemon, fake, f"kit {SECRET}", attachment=kit_server.attach("kit.zip", ZIP))
        await daemon.notifier.drain()
        assert kit_server.hits == []
        assert list(downloads.iterdir()) == []
        assert kit_events(daemon) == [] and kit_answers(daemon) == []

    phone_drive(body)
    assert_kit_refused(caplog, ": [files] kit_dir is outside [files] allowed_roots")


def test_the_daemon_answers_its_socket_while_a_kit_download_is_in_flight(
    kit_project: str, downloads: Path, kit_server: KitServer
) -> None:
    kit_server.release = threading.Event()

    async def body(daemon: Daemon, fake: FakeNtfy) -> None:
        assert daemon.phone is not None
        before = daemon.phone.handled
        fake.push(message(f"kit {SECRET}", attachment=kit_server.attach("slow.zip", ZIP)))

        async def asked() -> bool:
            return bool(kit_server.hits)

        await poll(asked, "the kit server to be asked")
        # the server has not answered yet, and the daemon's event loop still serves
        assert (await ok("status"))["daemon"] is not None
        assert daemon.phone.handled == before
        assert kit_server.release is not None
        kit_server.release.set()

        async def done() -> bool:
            return daemon.phone is not None and daemon.phone.handled > before

        await poll(done, "the kit to be written")
        assert (downloads / "slow.zip").read_bytes() == ZIP

    phone_drive(body)
