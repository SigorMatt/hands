"""A daemon stop does not strand the builder (DESIGN §38; H-047; §2, §6, §28, §31).

A job the daemon's own stop ends is recorded `orphaned` with `orphan_reason:
daemon_stop` (its process is still signalled, §2); `killed` stays the record of a
cancel. At the next start every orphan owed to the engine is fed to it once as
`<role>.orphaned`, after the workers are up, so `builder.orphaned → resume` re-sends
the kickoff from a fresh context, bounded by `max_resumes`; the start notification
names the resumed job.

Each test runs a real daemon over its real socket, more than once on one spool, with
`tests/fake_claude.py` as claude and a recorder as the ntfy transport.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import pytest

from conftest import commit_file, strip_paths
from hands.config import load_config
from hands.daemon import Daemon
from hands.spool import Spool
from harness import BLOCK, PROJECT, TIMEOUT, as_published, config_body, ok, poll, running_job

KICKOFF = f"Kick off mission 22\n{BLOCK}"

NOTIFY = """
[notify]
ntfy_url = "https://ntfy.example"
ntfy_topic = "hands-events-test"
"""


def book(max_resumes: int | None = None, rules: str = "") -> str:
    limits = "" if max_resumes is None else f"\n[limits]\nmax_resumes = {max_resumes}\n"
    return f"""version = 1

[series]
kickoff = "Kick off mission 22"
{limits}
[[rule]]
on = "builder.orphaned"
then = "resume"
{rules}"""


class Recorder:
    """Every publish, title and message; no test reaches a network (§11)."""

    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    async def __call__(self, url: str, **kwargs: Any) -> int:
        self.sent.append({"url": url, **kwargs})
        return 200

    def started(self) -> list[str]:
        title = as_published("hands: handsd started")
        return [item["message"] for item in self.sent if item["title"] == title]


@pytest.fixture
def workdir(tmp_path: Path) -> Path:
    d = tmp_path / "work"
    d.mkdir(exist_ok=True)
    return d


def setup(
    tmp_home: Path, workdir: Path, *, max_resumes: int | None = None, rules: str = ""
) -> Spool:
    body = config_body(
        tmp_home, workdir, builder="cancel_gated = false", extra=NOTIFY
    )
    (tmp_home / ".hands" / f"{PROJECT}.toml").write_text(body)
    commit_file(workdir, "PLAYBOOK.toml", book(max_resumes, rules))
    return Spool(tmp_home / ".hands" / PROJECT)


def run_daemon(body: Callable[[Daemon], Awaitable[None]]) -> Recorder:
    """One daemon's life on the project's spool: start, `body`, stop. Its publishes."""
    posts = Recorder()

    async def scenario() -> None:
        daemon = Daemon(load_config(PROJECT))
        daemon.notifier.post = posts  # before start(): no test may reach a network
        await daemon.start()
        try:
            await asyncio.wait_for(body(daemon), TIMEOUT)
        finally:
            await daemon.stop()

    asyncio.run(scenario())
    return posts


async def builder_jobs() -> list[dict[str, Any]]:
    rows = (await ok("jobs", "-n", "50"))["jobs"]
    return sorted((row for row in rows if row["role"] == "builder"), key=lambda r: r["id"])


async def settle(daemon: Daemon) -> None:
    """Room for anything the start scheduled to have had its turn."""
    await asyncio.sleep(0.3)
    await daemon.notifier.drain()


def stop_with_running_builder(prompt: str = KICKOFF) -> str:
    """A daemon whose stop ends a running builder job; that job's id."""
    seen: dict[str, str] = {}

    async def body(daemon: Daemon) -> None:
        sent = await ok("send", "--role", "builder", "--context", "clear", prompt)
        await running_job("builder")
        seen["id"] = sent["id"]

    run_daemon(body)
    return seen["id"]


# ------------------------------------------------------------------ the stop


def test_a_daemon_stop_records_the_running_job_orphaned_daemon_stop(
    tmp_home: Path, workdir: Path
) -> None:
    spool = setup(tmp_home, workdir)
    job_id = stop_with_running_builder()

    record = spool.load_job(job_id)
    assert record.state == "orphaned"
    assert record.orphan_reason == "daemon_stop"
    assert record.exit_code is not None  # the process was signalled and ended (§2)
    [event] = [e for e in spool.events() if e.kind == "job.orphaned"]
    assert event.payload["job"] == job_id
    assert event.payload["reason"] == "daemon_stop"
    assert not [e for e in spool.events() if e.kind in ("job.killed", "resume")]
    # the dying daemon resumed nothing: the next start owns the orphan
    assert [job.id for job in spool.list_jobs()] == [job_id]


def test_a_cancel_still_ends_killed_and_the_next_start_resumes_nothing(
    tmp_home: Path, workdir: Path
) -> None:
    spool = setup(tmp_home, workdir)
    seen: dict[str, Any] = {}

    async def first(daemon: Daemon) -> None:
        sent = await ok("send", "--role", "builder", "--context", "clear", KICKOFF)
        await running_job("builder")
        seen["cancelled"] = await ok("cancel", sent["id"], "--reason", "a human asked")
        seen["id"] = sent["id"]

    run_daemon(first)
    assert seen["cancelled"]["state"] == "killed"
    record = spool.load_job(seen["id"])
    assert record.state == "killed" and record.orphan_reason is None

    async def second(daemon: Daemon) -> None:
        await settle(daemon)
        assert [row["id"] for row in await builder_jobs()] == [seen["id"]]

    run_daemon(second)
    assert not [e for e in spool.events() if e.kind in ("job.orphaned", "resume", "stop")]


# ------------------------------------------------------------- the next start


def test_the_next_start_resumes_the_orphaned_builder_once_with_the_kickoff(
    tmp_home: Path, workdir: Path
) -> None:
    spool = setup(tmp_home, workdir)
    orphan = stop_with_running_builder()
    seen: dict[str, Any] = {}

    async def second(daemon: Daemon) -> None:
        async def two() -> Any:
            rows = await builder_jobs()
            return rows if len(rows) == 2 else None

        rows = await poll(two, "the resumed builder job")
        seen["resumed"] = rows[1]["id"]
        await running_job("builder")
        await settle(daemon)

    posts = run_daemon(second)
    resumed = spool.load_job(seen["resumed"])
    assert resumed.resumed_from == orphan
    assert resumed.context == "clear"
    assert resumed.prompt == KICKOFF
    assert resumed.origin == "playbook"
    assert spool.read_role("builder").consecutive_resumes == 1
    # §38: the start notification names the resumed job.
    [message] = posts.started()
    assert resumed.id in strip_paths(message), message
    assert f"from job {orphan}" in strip_paths(message), message
    # The second daemon's own stop orphaned the resumed job in turn.
    assert spool.load_job(resumed.id).state == "orphaned"

    # A third start feeds the second orphan once, and never the first again.
    async def third(daemon: Daemon) -> None:
        async def three() -> Any:
            rows = await builder_jobs()
            return rows if len(rows) == 3 else None

        await poll(three, "the second resume")
        await running_job("builder")
        await settle(daemon)
        assert len(await builder_jobs()) == 3

    run_daemon(third)
    froms = [job.resumed_from for job in spool.list_jobs() if job.resumed_from]
    assert froms == [orphan, resumed.id]
    assert len([e for e in spool.events() if e.kind == "resume"]) == 2


def test_a_stop_with_the_builder_idle_resumes_nothing(tmp_home: Path, workdir: Path) -> None:
    spool = setup(tmp_home, workdir)

    async def first(daemon: Daemon) -> None:
        sent = await ok("send", "--role", "builder", "--context", "clear", "FAKE:result fine")
        assert (await ok("wait", sent["id"]))["state"] == "done"

    run_daemon(first)

    async def second(daemon: Daemon) -> None:
        await settle(daemon)
        assert len(await builder_jobs()) == 1
        assert (await ok("status"))["roles"]["builder"]["running"] is None

    posts = run_daemon(second)
    assert not [e for e in spool.events() if e.kind in ("job.orphaned", "resume")]
    # the one stop is the first daemon's: `builder.done` has no rule in this playbook
    assert [e.payload["event"] for e in spool.events() if e.kind == "stop"] == ["builder.done"]
    [message] = posts.started()
    assert "Resumed:" not in strip_paths(message), message


def test_max_resumes_reached_stops_with_the_reason(tmp_home: Path, workdir: Path) -> None:
    spool = setup(tmp_home, workdir, max_resumes=0)
    orphan = stop_with_running_builder()

    async def second(daemon: Daemon) -> None:
        async def stopped() -> Any:
            return (await ok("pipeline"))["stop_reason"]

        reason = await poll(stopped, "the stop")
        assert "builder.orphaned" in strip_paths(reason), reason
        assert "max_resumes is 0" in strip_paths(reason), reason
        await settle(daemon)
        assert [row["id"] for row in await builder_jobs()] == [orphan]

    posts = run_daemon(second)
    assert not [e for e in spool.events() if e.kind == "resume"]
    # §32: the stop the start raised is folded into its one notification.
    [message] = posts.started()
    assert "max_resumes is 0" in strip_paths(message), message


def test_an_orphan_recorded_before_section_38_is_not_fed(tmp_home: Path, workdir: Path) -> None:
    """A record kept from before §38 carries no `orphan_fed`; no start feeds it, so an
    old orphan in a long-lived spool is never resumed by the upgrade."""
    spool = setup(tmp_home, workdir)
    job = spool.create_job(role="builder", context="clear", prompt=KICKOFF, origin="cli")
    spool.transition(job, "running")
    old = spool.transition(job, "orphaned")
    old.orphan_fed = None  # as a record written before the field existed loads
    spool.save_job(old)

    async def body(daemon: Daemon) -> None:
        await settle(daemon)
        assert len(await builder_jobs()) == 1

    run_daemon(body)
    assert not [e for e in spool.events() if e.kind in ("resume", "stop")]


# ------------------------------------------------------------- the pieces


def test_the_spool_owes_every_new_orphan_to_the_engine_until_it_is_marked_fed(
    tmp_path: Path,
) -> None:
    spool = Spool(tmp_path / "spool")
    job = spool.create_job(role="builder", context="clear", prompt="p", origin="cli")
    spool.transition(job, "running")
    orphan = spool.transition(job, "orphaned", orphan_reason="daemon_stop")
    assert orphan.orphan_fed is False
    assert [owed.id for owed in spool.orphans_owed()] == [orphan.id]
    assert spool.mark_orphan_fed(orphan.id).orphan_fed is True
    assert spool.orphans_owed() == []
    assert spool.load_job(orphan.id).orphan_reason == "daemon_stop"
    done = spool.create_job(role="builder", context="clear", prompt="p", origin="cli")
    spool.transition(done, "running")
    assert spool.transition(done, "done").orphan_fed is None


def test_a_cancel_wins_over_the_daemon_stop() -> None:
    from hands.runner import _final_state, _Parsed

    assert _final_state(_Parsed(), 130, cancelled=True, daemon_stop=True) == ("killed", None)
    assert _final_state(_Parsed(), 130, cancelled=False, daemon_stop=True) == ("orphaned", None)
    assert _final_state(_Parsed(), 130, cancelled=True) == ("killed", None)


# ------------------------------------------- §39: review 22 should-fix 3 and 4, H-057

#: §39 (H-057): the rule both templates and this repository's playbook now carry.
AUX_RESUME = """
[[rule]]
on = "aux.orphaned"
then = "resume"
"""
#: A builder.done that fires a rule, so a warm-up job does not stop the pipeline.
DONE_NOTE = """
[[rule]]
on = "builder.done"
then = "notify"
message = "builder done"
"""
REVIEW = f"Read meta/REVIEW-PROTOCOL.md and review mission 22\n{BLOCK}"


def jobs_resumed_from(spool: Spool, job_id: str) -> list[Any]:
    return [job for job in spool.list_jobs() if job.resumed_from == job_id]


def test_a_review_a_stop_orphans_is_resumed_fresh_with_its_prompt_at_the_next_start(
    tmp_home: Path, workdir: Path
) -> None:
    """H-057: the daemon's stop records the running aux job `orphaned` with `reason:
    daemon_stop`, as it does a builder's; at the next start `aux.orphaned → resume`
    re-sends the review's prompt to a fresh context (the orphan was a `keep`)."""
    spool = setup(tmp_home, workdir, rules=AUX_RESUME)
    seen: dict[str, Any] = {}

    async def first(daemon: Daemon) -> None:
        warm = await ok("send", "--role", "aux", "--context", "clear", "FAKE:result ok")
        assert (await ok("wait", warm["id"]))["state"] == "done"
        sent = await ok("send", "--role", "aux", "--context", "keep", REVIEW)
        await running_job("aux")
        seen["id"] = sent["id"]

    run_daemon(first)
    orphan = spool.load_job(seen["id"])
    assert (orphan.state, orphan.orphan_reason, orphan.context) == (
        "orphaned", "daemon_stop", "keep",
    )

    async def second(daemon: Daemon) -> None:
        async def resumed() -> Any:
            return jobs_resumed_from(spool, orphan.id)

        [job] = await poll(resumed, "the resumed review")
        seen["resumed"] = job.id
        await running_job("aux")
        await settle(daemon)

    posts = run_daemon(second)
    resumed = spool.load_job(seen["resumed"])
    assert (resumed.role, resumed.prompt, resumed.context, resumed.origin) == (
        "aux", REVIEW, "clear", "playbook",
    )
    assert spool.read_role("aux").consecutive_resumes == 1
    [message] = posts.started()
    assert (
        f"Resumed: aux job {resumed.id}, from job {orphan.id} which a daemon stop orphaned"
        in strip_paths(message)
    ), message


def test_an_orphaned_review_is_bounded_by_max_resumes(tmp_home: Path, workdir: Path) -> None:
    spool = setup(tmp_home, workdir, max_resumes=0, rules=AUX_RESUME)
    seen: dict[str, Any] = {}

    async def first(daemon: Daemon) -> None:
        seen["id"] = (await ok("send", "--role", "aux", "--context", "clear", REVIEW))["id"]
        await running_job("aux")

    run_daemon(first)

    async def second(daemon: Daemon) -> None:
        async def stopped() -> Any:
            return (await ok("pipeline"))["stop_reason"]

        reason = await poll(stopped, "the stop")
        assert "aux.orphaned" in strip_paths(reason), reason
        assert "max_resumes is 0" in strip_paths(reason), reason

    run_daemon(second)
    assert jobs_resumed_from(spool, seen["id"]) == []


def test_the_start_notification_names_a_crash_orphan_as_found_not_as_a_daemon_stop(
    tmp_home: Path, workdir: Path
) -> None:
    """Review 22 should-fix 4: a job the start reconciled (its process gone, no
    `orphan_reason`) is resumed and named as found, never as a daemon stop's."""
    spool = setup(tmp_home, workdir)
    job = spool.create_job(role="builder", context="clear", prompt=KICKOFF, origin="cli")
    spool.transition(job, "running")  # no pid: the process is gone, as after a crash

    async def body(daemon: Daemon) -> None:
        async def resumed() -> Any:
            return jobs_resumed_from(spool, job.id)

        await poll(resumed, "the resumed builder job")
        await running_job("builder")
        await settle(daemon)

    posts = run_daemon(body)
    assert spool.load_job(job.id).orphan_reason is None
    [message] = posts.started()
    assert f"from job {job.id}" in strip_paths(message), message
    assert "daemon stop" not in strip_paths(message), message
    assert "found orphaned" in strip_paths(message), message


def test_an_answer_a_stop_orphans_is_published_and_re_sent_as_a_keep(
    tmp_home: Path, workdir: Path
) -> None:
    """Review 22 should-fix 3: a phone `answer` the daemon's stop ends is published on
    ntfy_topic titled `builder` as its end, and `builder.orphaned → resume` re-sends
    it to the builder's session as a `keep` with its own text, never as a clear."""
    spool = setup(tmp_home, workdir, rules=DONE_NOTE)
    answer = f"Take the second option.\n{BLOCK}"
    seen: dict[str, Any] = {}

    async def first(daemon: Daemon) -> None:
        warm = await ok("send", "--role", "builder", "--context", "clear", "FAKE:result ok")
        assert (await ok("wait", warm["id"]))["state"] == "done"
        seen["id"] = (await daemon.api.answer_builder(answer))["id"]
        await running_job("builder")

    posts = run_daemon(first)
    orphan = spool.load_job(seen["id"])
    assert (orphan.state, orphan.orphan_reason) == ("orphaned", "daemon_stop")
    ended = [item for item in posts.sent if item["title"] == as_published("builder")]
    assert [item["message"] for item in ended] == [
        f"builder job {orphan.id} ended orphaned with no reply"
    ], posts.sent

    async def second(daemon: Daemon) -> None:
        async def resumed() -> Any:
            return jobs_resumed_from(spool, orphan.id)

        [job] = await poll(resumed, "the re-sent answer")
        seen["resumed"] = job.id
        await settle(daemon)

    run_daemon(second)
    resumed = spool.load_job(seen["resumed"])
    assert (resumed.role, resumed.context, resumed.prompt) == ("builder", "keep", answer)
