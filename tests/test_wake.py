"""U8: the wake path, ntfy notifications and the heartbeat (DESIGN §3, §8, §11, §13).

Nothing here touches the network: the ntfy transport is a recorder, the quiet
hours clock is injected and the scheduler's sleep records the delay instead of
waiting it out. The heartbeat interval is a daemon parameter, so the test that
watches one takes milliseconds rather than an hour.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from hands.config import Config, load_config, parse_config
from hands.daemon import Daemon
from hands.limits import LimitManager, to_iso
from hands.notify import Notifier, parse_quiet_hours
from hands.spool import Job, Spool, resolve_kinds
from harness import BLOCK, PROJECT, cli, config_body, drive, ok, poll

NOW = datetime(2026, 9, 11, 12, 0, tzinfo=UTC)


@pytest.fixture
def workdir(tmp_path: Path) -> Path:
    d = tmp_path / "work"
    d.mkdir(exist_ok=True)
    return d


@pytest.fixture
def project(tmp_home: Path, workdir: Path) -> str:
    (tmp_home / ".hands" / f"{PROJECT}.toml").write_text(config_body(tmp_home, workdir))
    return PROJECT


# ------------------------------------------------------- the kind vocabulary


def test_the_driver_kit_spelling_resolves_to_real_event_kinds() -> None:
    """§11/§12: the driver types `--for stop,held`; `held` is the kind `job.held`."""
    assert resolve_kinds("stop,held") == frozenset({"stop", "job.held"})
    assert resolve_kinds(" stop , job.held ") == frozenset({"stop", "job.held"})
    assert resolve_kinds("job") >= frozenset({"job.done", "job.held", "job.failed"})


def test_a_kind_no_event_can_have_is_refused() -> None:
    with pytest.raises(Exception) as exc:
        resolve_kinds("stop,banana")
    assert "banana" in str(exc.value)


# ---------------------------------------------------------- wait --for (§11)


def test_wait_for_returns_the_event_it_was_armed_for(project: str, tmp_home: Path) -> None:
    """The driver arms the wait and goes idle; the event returns it."""

    async def body(daemon: Daemon) -> None:
        waiting = asyncio.create_task(ok("wait", "--for", "stop,held", "--timeout", "30"))
        await asyncio.sleep(0.1)  # the wait is armed and blocking
        assert not waiting.done()
        await daemon.playbook.stop("run 3 has blockers")
        event = await asyncio.wait_for(waiting, 10)
        assert event["kind"] == "stop"
        assert event["payload"]["reason"] == "run 3 has blockers"

    drive(body)


def test_wait_for_does_not_ack_the_event_it_returns(project: str, tmp_home: Path) -> None:
    """§11: the event is returned, not acked — the driver acks with `inbox --ack`."""

    async def body(daemon: Daemon) -> None:
        await daemon.playbook.stop("stopped for a human")
        event = await ok("wait", "--for", "stop", "--timeout", "30")
        unacked = await ok("inbox")
        assert [item["id"] for item in unacked["events"]] == [event["id"]]
        assert (await ok("inbox", "--ack"))["acked"] == [event["id"]]
        assert (await ok("inbox"))["events"] == []

    drive(body)


def test_wait_for_returns_an_event_that_arrived_before_the_wait(
    project: str, tmp_home: Path
) -> None:
    """An unacked match is returned at once: an event between acting and re-arming
    must not be lost, and unacked is exactly "the driver has not handled it"."""

    async def body(daemon: Daemon) -> None:
        await daemon.playbook.stop("arrived while the driver was reporting")
        event = await asyncio.wait_for(ok("wait", "--for", "stop,held", "--timeout", "30"), 10)
        assert event["payload"]["reason"] == "arrived while the driver was reporting"

    drive(body)


def test_an_acked_event_does_not_wake_the_re_armed_wait(project: str, tmp_home: Path) -> None:
    """The other half of the rule: once acked, the same event never wakes again."""

    async def body(daemon: Daemon) -> None:
        await daemon.playbook.stop("handled already")
        await ok("wait", "--for", "stop", "--timeout", "30")
        await ok("inbox", "--ack")
        code, _, err = await cli("wait", "--for", "stop", "--timeout", "0.3", "--json")
        assert code == 2, err
        assert "timeout" in err.lower()

    drive(body)


def test_wait_for_times_out_with_a_distinguishable_exit_code(
    project: str, tmp_home: Path
) -> None:
    async def body(daemon: Daemon) -> None:
        code, out, err = await cli("wait", "--for", "stop,held", "--timeout", "0.3")
        assert code == 2, f"{out}{err}"
        assert "timeout" in err.lower()
        # An ordinary refusal is still 1, so the driver can tell them apart.
        code, _, err = await cli("wait", "--for", "banana", "--timeout", "0.3")
        assert code == 1, err

    drive(body)


def test_wait_for_wakes_on_a_gated_job(project: str, tmp_home: Path) -> None:
    """§8's `job.held` is the other half of `--for stop,held`."""

    async def body(daemon: Daemon) -> None:
        waiting = asyncio.create_task(ok("wait", "--for", "stop,held", "--timeout", "30"))
        await asyncio.sleep(0.1)
        await ok("send", "--role", "builder", "--context", "clear", "--gate", "by hand", "hi")
        event = await asyncio.wait_for(waiting, 10)
        assert event["kind"] == "job.held"
        assert event["payload"]["reason"] == "by hand"

    drive(body)


def test_wait_for_stop_wakes_on_a_hand_pause(project: str, tmp_home: Path) -> None:
    """H-007: `hands pause` is the one-command event §11's wake check can fire —
    no job, nothing to clean up but `hands resume`."""

    async def body(daemon: Daemon) -> None:
        waiting = asyncio.create_task(ok("wait", "--for", "stop,held", "--timeout", "30"))
        await asyncio.sleep(0.1)
        assert not waiting.done()
        await ok("pause")
        event = await asyncio.wait_for(waiting, 10)
        assert event["kind"] == "stop"
        assert event["payload"]["reason"] == "paused by human"

    drive(body)


def test_a_resume_files_the_pipeline_resumed_event(project: str, tmp_home: Path) -> None:
    """§10's stop → resume cycle, both halves in the inbox."""

    async def body(daemon: Daemon) -> None:
        await ok("pause")
        await ok("resume")
        events = (await ok("inbox"))["events"]
        assert [event["kind"] for event in events] == ["stop", "pipeline.resumed"]
        assert events[1]["payload"]["was"] == "paused by human"

    drive(body)


def test_wait_needs_a_job_or_for_but_not_both(project: str, tmp_home: Path) -> None:
    async def body(daemon: Daemon) -> None:
        code, _, err = await cli("wait", "somejob", "--for", "stop")
        assert code == 1
        assert "--for" in err

    drive(body)


def test_shutting_down_does_not_wait_for_an_armed_wait(tmp_home: Path, workdir: Path) -> None:
    """A `wait --for` with no timeout is a request that never returns (§11): the
    daemon must not wait for it to finish before it can go down (§3)."""
    (tmp_home / ".hands" / f"{PROJECT}.toml").write_text(config_body(tmp_home, workdir))

    async def scenario() -> None:
        daemon = Daemon(load_config(PROJECT))
        await daemon.start()
        waiting = asyncio.create_task(cli("wait", "--for", "stop"))
        await asyncio.sleep(0.2)  # armed, blocking, no timeout
        await asyncio.wait_for(daemon.stop(), 10)
        code, _, err = await asyncio.wait_for(waiting, 10)
        assert code == 1, err  # the client is told the daemon went away

    asyncio.run(scenario())


# ------------------------------------------------------------ ntfy (§11, §13)


def cfg_with(tmp_home: Path, tmp_path: Path, **server: Any) -> Config:
    work = tmp_path / "work"
    work.mkdir(exist_ok=True)
    server = {key: value for key, value in server.items() if value is not None}
    return parse_config(
        {"server": server, "roles": {"builder": {"cwd": str(work)}}},
        project="demo",
        path=tmp_home / ".hands" / "demo.toml",
    )


class Posts:
    """The ntfy transport, recorded. No test may make a network call."""

    def __init__(self, fail: bool = False) -> None:
        self.sent: list[dict[str, Any]] = []
        self.fail = fail

    async def __call__(self, url: str, *, title: str, message: str) -> None:
        if self.fail:
            raise OSError("ntfy.sh is unreachable")
        self.sent.append({"url": url, "title": title, "message": message})


class Clock:
    def __init__(self, now: datetime = NOW) -> None:
        self.now = now
        self.slept: list[float] = []

    def __call__(self) -> datetime:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)


def notifier(
    tmp_home: Path,
    tmp_path: Path,
    *,
    posts: Posts | None = None,
    clock: Clock | None = None,
    quiet: str | None = None,
    topic: str | None = "hands-abc123",
) -> tuple[Notifier, Posts, Clock, Spool]:
    posts = posts or Posts()
    clock = clock or Clock()
    spool = Spool(tmp_home / ".hands")
    config = cfg_with(tmp_home, tmp_path, ntfy_topic=topic, ntfy_url="https://ntfy.example")
    return (
        Notifier(
            config,
            spool,
            post=posts,
            clock=clock,
            sleep=clock.sleep,
            quiet_hours=lambda: quiet,
        ),
        posts,
        clock,
        spool,
    )


def test_a_notification_is_published_to_the_configured_topic(
    tmp_home: Path, tmp_path: Path
) -> None:
    note, posts, _, _ = notifier(tmp_home, tmp_path)

    async def body() -> None:
        note.notify("hands: the pipeline stopped", {"reason": "blockers", "job": "j1"})
        await note.drain()

    asyncio.run(body())
    assert len(posts.sent) == 1
    assert posts.sent[0]["url"] == "https://ntfy.example/hands-abc123"
    assert posts.sent[0]["title"] == "hands: the pipeline stopped"
    assert "blockers" in posts.sent[0]["message"]


def test_with_no_topic_nothing_is_published(tmp_home: Path, tmp_path: Path) -> None:
    note, posts, _, spool = notifier(tmp_home, tmp_path, topic=None)

    async def body() -> None:
        note.notify("hands: stop", {"reason": "x"})
        await note.drain()

    asyncio.run(body())
    assert posts.sent == []
    assert [event.kind for event in spool.events()] == []


def test_a_failed_publish_is_inboxed_and_never_raised(tmp_home: Path, tmp_path: Path) -> None:
    """Best effort (§11): ntfy being down must never touch a job."""
    note, posts, _, spool = notifier(tmp_home, tmp_path, posts=Posts(fail=True))

    async def body() -> None:
        note.notify("hands: the pipeline stopped", {"reason": "blockers"})
        await note.drain()

    asyncio.run(body())
    events = spool.events()
    assert [event.kind for event in events] == ["notify"]
    assert events[0].payload["delivered"] is False
    assert "unreachable" in events[0].payload["error"]


# ----------------------------------------------------------- quiet hours §10


@pytest.mark.parametrize(
    ("window", "moment", "inside"),
    [
        ("23:00-07:00", datetime(2026, 9, 11, 23, 30, tzinfo=UTC), True),
        ("23:00-07:00", datetime(2026, 9, 11, 2, 0, tzinfo=UTC), True),
        ("23:00-07:00", datetime(2026, 9, 11, 12, 0, tzinfo=UTC), False),
        ("23:00-07:00", datetime(2026, 9, 11, 7, 0, tzinfo=UTC), False),
        ("09:00-17:00", datetime(2026, 9, 11, 12, 0, tzinfo=UTC), True),
        ("09:00-17:00", datetime(2026, 9, 11, 8, 59, tzinfo=UTC), False),
    ],
)
def test_the_quiet_window_knows_when_it_is_quiet(
    window: str, moment: datetime, inside: bool
) -> None:
    parsed = parse_quiet_hours(window)
    assert parsed is not None
    assert parsed.contains(moment) is inside


def test_an_unreadable_quiet_window_is_no_window(tmp_home: Path, tmp_path: Path) -> None:
    """A broken window must not silence notifications: it is ignored, not obeyed."""
    assert parse_quiet_hours("all night") is None
    note, posts, _, _ = notifier(tmp_home, tmp_path, quiet="all night")

    async def body() -> None:
        note.notify("hands: stop", {"reason": "x"})
        await note.drain()

    asyncio.run(body())
    assert len(posts.sent) == 1


def test_quiet_hours_delays_delivery_to_the_window_end(tmp_home: Path, tmp_path: Path) -> None:
    """§11: quiet hours delay the notification; the scheduler flushes at the end."""
    clock = Clock(datetime(2026, 9, 11, 23, 30, tzinfo=UTC))
    note, posts, clock, _ = notifier(tmp_home, tmp_path, clock=clock, quiet="23:00-07:00")

    async def body() -> None:
        note.notify("hands: the pipeline stopped", {"reason": "blockers"})
        assert posts.sent == []  # nothing goes out at 23:30
        assert [item.title for item in note.queued] == ["hands: the pipeline stopped"]
        await note.drain()  # the flush task's sleep is the recorder

    asyncio.run(body())
    assert clock.slept == [7.5 * 3600]  # 23:30 → 07:00
    assert len(posts.sent) == 1, "the queue is flushed at the window end"
    assert note.queued == []


def test_two_quiet_notifications_share_one_flush(tmp_home: Path, tmp_path: Path) -> None:
    clock = Clock(datetime(2026, 9, 11, 2, 0, tzinfo=UTC))
    note, posts, clock, _ = notifier(tmp_home, tmp_path, clock=clock, quiet="23:00-07:00")

    async def body() -> None:
        note.notify("hands: one", {"reason": "a"})
        note.notify("hands: two", {"reason": "b"})
        await note.drain()

    asyncio.run(body())
    assert clock.slept == [5 * 3600]
    assert [item["title"] for item in posts.sent] == ["hands: one", "hands: two"]


# ------------------------------------------------------- wiring (§10 → §11)


def config_with_ntfy(tmp_home: Path, workdir: Path) -> None:
    body = config_body(tmp_home, workdir).replace(
        "[server]", '[server]\nntfy_topic = "hands-test"\nntfy_url = "https://ntfy.example"'
    )
    (tmp_home / ".hands" / f"{PROJECT}.toml").write_text(body)


def test_a_stop_notifies_and_a_held_job_notifies(tmp_home: Path, workdir: Path) -> None:
    """§11's list: `stop` and `job.held` are the two a running daemon produces."""
    config_with_ntfy(tmp_home, workdir)
    posts = Posts()

    async def scenario() -> None:
        daemon = Daemon(load_config(PROJECT))
        daemon.notifier.post = posts  # before start(): no test may reach a network
        await daemon.start()
        try:
            await ok("send", "--role", "builder", "--context", "clear", "--gate", "by hand", "hi")
            await daemon.playbook.stop("no rule for it")
            await daemon.notifier.drain()
        finally:
            await daemon.stop()
        titles = [item["title"] for item in posts.sent]
        assert any("held" in title for title in titles), titles
        assert any("stopped" in title for title in titles), titles

    asyncio.run(scenario())


def test_a_hand_pause_notifies_like_any_other_stop(tmp_home: Path, workdir: Path) -> None:
    """§11 lists `stop` among the notifications, and a pause files a `stop`. Quiet
    hours are the Notifier's (they delay this exact title, see the quiet tests);
    the action — the pause itself — is never delayed."""
    config_with_ntfy(tmp_home, workdir)
    posts = Posts()

    async def scenario() -> None:
        daemon = Daemon(load_config(PROJECT))
        daemon.notifier.post = posts
        await daemon.start()
        try:
            await ok("pause")
            await ok("resume")
            await daemon.notifier.drain()
        finally:
            await daemon.stop()
        titles = [item["title"] for item in posts.sent]
        assert any("stopped" in title for title in titles), titles
        assert sum("stopped" in title for title in titles) == 1, titles

    asyncio.run(scenario())


def test_the_daemon_announces_its_start(tmp_home: Path, workdir: Path) -> None:
    """§11: daemon start/crash are notifications."""
    config_with_ntfy(tmp_home, workdir)
    posts = Posts()

    async def scenario() -> None:
        daemon = Daemon(load_config(PROJECT))
        daemon.notifier.post = posts
        await daemon.start()
        try:
            await daemon.notifier.drain()
        finally:
            await daemon.stop()

    asyncio.run(scenario())
    assert any("started" in item["title"] for item in posts.sent), posts.sent


# -------------------------------------------------------------- heartbeat §11


def test_a_heartbeat_lands_while_a_job_runs(tmp_home: Path, workdir: Path) -> None:
    """§11: hourly while any job runs, so silence is distinguishable from death.
    The interval is a parameter, so this test is milliseconds, not an hour."""
    (tmp_home / ".hands" / f"{PROJECT}.toml").write_text(config_body(tmp_home, workdir))

    async def scenario() -> None:
        daemon = Daemon(load_config(PROJECT), heartbeat_s=0.05)
        await daemon.start()
        try:
            await ok("send", "--role", "builder", "--context", "clear", BLOCK)

            async def beat() -> Any:
                events = daemon.spool.events()
                return [event for event in events if event.kind == "heartbeat"]

            beats = await poll(beat, "a heartbeat event")
            assert beats[0].payload["running"], "a heartbeat names the jobs that are running"
        finally:
            await daemon.stop()

    asyncio.run(scenario())


def test_no_heartbeat_when_nothing_runs(tmp_home: Path, workdir: Path) -> None:
    (tmp_home / ".hands" / f"{PROJECT}.toml").write_text(config_body(tmp_home, workdir))

    async def scenario() -> None:
        daemon = Daemon(load_config(PROJECT), heartbeat_s=0.02)
        await daemon.start()
        try:
            await asyncio.sleep(0.2)
            assert [e for e in daemon.spool.events() if e.kind == "heartbeat"] == []
        finally:
            await daemon.stop()

    asyncio.run(scenario())


# ------------------------------- the U5 gap: resumes lost with the daemon (§6)


def limited_job(spool: Spool, *, role: str = "builder", reset_at: str | None) -> Job:
    job = spool.create_job(role=role, context="clear", prompt="work", origin="cli")
    spool.transition(job, "running")
    return spool.transition(
        job, "limited", limit={"category": "rate_limit", "message": "", "reset_at": reset_at}
    )


class Recorder:
    def __init__(self, config: Config, spool: Spool) -> None:
        self.spool = spool
        self.delays: list[float] = []
        self.manager = LimitManager(
            config, spool, enqueue=self._enqueue, clock=lambda: NOW, sleep=self._sleep
        )

    async def _sleep(self, seconds: float) -> None:
        self.delays.append(seconds)

    async def _enqueue(self, **kwargs: Any) -> Job:
        return self.spool.create_job(**kwargs)


def test_a_resume_the_dead_daemon_owed_is_rescheduled_at_startup(
    tmp_home: Path, tmp_path: Path
) -> None:
    """U5's gap: the resume was a task in a process that died. The spool still says
    the role is limited and nothing newer happened, so the next daemon owes it."""
    spool = Spool(tmp_home / ".hands")
    config = cfg_with(tmp_home, tmp_path)
    job = limited_job(spool, reset_at=to_iso(NOW + timedelta(minutes=10)))
    rec = Recorder(config, spool)

    async def body() -> None:
        assert [pending.id for pending in rec.manager.pending_resumes()] == [job.id]
        await rec.manager.reschedule_pending()
        await rec.manager.drain()

    asyncio.run(body())
    assert rec.delays == [10 * 60 + 60.0]  # the reset, plus §6's grace
    resumed = [item for item in spool.list_jobs() if item.resumed_from == job.id]
    assert len(resumed) == 1
    assert [event.kind for event in spool.events()] == ["resume"]


def test_a_limited_job_whose_role_moved_on_is_not_rescheduled(
    tmp_home: Path, tmp_path: Path
) -> None:
    """The resume already happened (or a human sent new work): nothing is owed."""
    spool = Spool(tmp_home / ".hands")
    config = cfg_with(tmp_home, tmp_path)
    limited_job(spool, reset_at=to_iso(NOW + timedelta(minutes=10)))
    spool.create_job(role="builder", context="clear", prompt="newer", origin="cli")
    rec = Recorder(config, spool)

    async def body() -> None:
        assert rec.manager.pending_resumes() == []
        await rec.manager.reschedule_pending()
        await rec.manager.drain()

    asyncio.run(body())
    assert rec.delays == []


def test_the_daemon_reschedules_owed_resumes_when_it_starts(
    tmp_home: Path, workdir: Path
) -> None:
    (tmp_home / ".hands" / f"{PROJECT}.toml").write_text(config_body(tmp_home, workdir))
    spool = Spool(tmp_home / ".hands")
    job = limited_job(spool, reset_at=to_iso(datetime.now(UTC) - timedelta(hours=1)))

    async def scenario() -> None:
        daemon = Daemon(load_config(PROJECT))
        delays: list[float] = []

        async def sleep(seconds: float) -> None:
            delays.append(seconds)

        daemon.limits.sleep = sleep
        await daemon.start()
        try:
            await daemon.limits.drain()
            assert delays == [60.0], "a reset that passed while the daemon was down is due now"
            resumed = [item for item in spool.list_jobs() if item.resumed_from == job.id]
            assert len(resumed) == 1
        finally:
            await daemon.stop()

    asyncio.run(scenario())


def test_the_event_stream_of_a_wait_is_json_on_stdout(project: str, tmp_home: Path) -> None:
    """The driver reads stdout: one JSON object, whether or not --json is given."""

    async def body(daemon: Daemon) -> None:
        await daemon.playbook.stop("for the driver")
        code, out, err = await cli("wait", "--for", "stop", "--timeout", "30", "--json")
        assert code == 0, err
        assert json.loads(out)["kind"] == "stop"
        # the readable form is one line, not a job block
        await ok("inbox", "--ack")
        await daemon.playbook.resume()
        await daemon.playbook.stop("again")
        code, out, err = await cli("wait", "--for", "stop", "--timeout", "30")
        assert code == 0, err
        assert "stop" in out and "again" in out

    drive(body)
