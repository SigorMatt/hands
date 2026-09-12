"""U5: limits — notice detection, reset parsing, the resume, the counter (§6, §11).

No test here sleeps for a limit interval: the clock is injected (`now=`) and the
scheduler's sleep is a recorder, so the *scheduled* delay is what is asserted.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from conftest import strip_paths
from hands.config import Config, parse_config
from hands.limits import (
    RESUME_GRACE_S,
    LimitManager,
    is_limit_notice,
    parse_reset_at,
    resume_delay_s,
    to_iso,
)
from hands.spool import Job, Spool

EAST = ZoneInfo("America/New_York")
WEST = ZoneInfo("America/Los_Angeles")
NOW = datetime(2026, 9, 11, 12, 0, tzinfo=EAST)  # a Friday noon, -04:00


# ------------------------------------------------------- the notice shapes


@pytest.mark.parametrize(
    "text",
    [
        "Usage limit reached · continuing automatically at 3pm · esc or type to cancel",
        "usage limit reached — check plan",
        "Claude usage limit reached. Your limit will reset at 2026-09-11T17:00:00Z.",
        "rate limit exceeded, try again in 45 minutes",
        "You have reached your weekly limit.",
        "waiting until your limit resets at 3pm",
    ],
)
def test_a_limit_notice_is_recognised(text: str) -> None:
    assert is_limit_notice(text)


@pytest.mark.parametrize(
    "text",
    [
        None,
        "",
        "VERDICT: PASS",
        "we should add rate limiting to the API before the next run",
        "the limit of that function is 3 arguments",
        "Resume WORKPLAN.md",
    ],
)
def test_ordinary_text_is_not_a_limit_notice(text: str | None) -> None:
    assert not is_limit_notice(text)


# --------------------------------------------------------- reset parsing


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # ISO, with a zone
        ("Usage limit reached. Resets at 2026-09-11T17:30:00Z",
         datetime(2026, 9, 11, 17, 30, tzinfo=UTC)),
        ("resets at 2026-09-11T14:30:00-04:00", datetime(2026, 9, 11, 18, 30, tzinfo=UTC)),
        # ISO, naive → the injected now's zone
        ("resets at 2026-09-11 16:30", datetime(2026, 9, 11, 16, 30, tzinfo=EAST)),
        # "resets at <time>", no date: today when still ahead …
        ("continuing automatically at 3pm", datetime(2026, 9, 11, 15, 0, tzinfo=EAST)),
        ("continuing automatically at 3:45pm", datetime(2026, 9, 11, 15, 45, tzinfo=EAST)),
        ("resets at 15:30", datetime(2026, 9, 11, 15, 30, tzinfo=EAST)),
        # … and the next occurrence when it is already behind us
        ("continuing automatically at 11am", datetime(2026, 9, 12, 11, 0, tzinfo=EAST)),
        # a named zone in parentheses is honoured
        ("continuing automatically at 3pm (America/Los_Angeles)",
         datetime(2026, 9, 11, 15, 0, tzinfo=WEST)),
        # with a date, the way the binary spells it past 24 hours
        ("continuing automatically at Sep 12, 3pm", datetime(2026, 9, 12, 15, 0, tzinfo=EAST)),
        ("resets Sep 12, 2026, 3:45pm", datetime(2026, 9, 12, 15, 45, tzinfo=EAST)),
        # relative
        ("rate limit exceeded, try again in 45 minutes",
         datetime(2026, 9, 11, 12, 45, tzinfo=EAST)),
        ("try again in 2 hours", datetime(2026, 9, 11, 14, 0, tzinfo=EAST)),
        ("retrying in 90 seconds", datetime(2026, 9, 11, 12, 1, 30, tzinfo=EAST)),
    ],
)
def test_a_reset_time_is_parsed(text: str, expected: datetime) -> None:
    assert parse_reset_at(text, now=NOW) == expected


@pytest.mark.parametrize(
    "text",
    [
        None,
        "",
        # the shape this unit cannot parse, and must not pretend to
        "Usage limit reached. Try later.",
        "usage limit reached — check plan",
        # absurd: in the past
        "resets at 2020-01-01T00:00:00Z",
        # absurd: further ahead than any subscription window
        "resets at 2031-01-01T00:00:00Z",
        # not a time at all
        "at 99:99",
        "resets at 25:00",
    ],
)
def test_an_unparseable_or_absurd_reset_time_is_none(text: str | None) -> None:
    assert parse_reset_at(text, now=NOW) is None


def test_the_raw_notice_is_never_normalised() -> None:
    """Parsing is a read: whatever it decides, the notice text is untouched."""
    notice = "  Usage limit reached · continuing automatically at 3pm  "
    assert parse_reset_at(notice, now=NOW) is not None
    assert notice == "  Usage limit reached · continuing automatically at 3pm  "


# ------------------------------------------------------- the resume delay


def _limited(spool: Spool, *, reset_at: str | None, role: str = "builder") -> Job:
    job = spool.create_job(role=role, context="clear", prompt="work", origin="cli")
    spool.transition(job, "running")
    return spool.transition(
        job,
        "limited",
        limit={"category": "rate_limit", "message": "Usage limit reached", "reset_at": reset_at},
    )


def test_a_parsed_reset_schedules_the_resume_at_that_time_plus_60s(tmp_home: Path) -> None:
    spool = Spool(tmp_home / ".hands")
    job = _limited(spool, reset_at=to_iso(NOW + timedelta(minutes=30)))
    delay = resume_delay_s(job, now=NOW, backoff_minutes=30.0)
    assert delay == 30 * 60 + RESUME_GRACE_S


def test_no_parsed_reset_falls_back_to_backoff_minutes(tmp_home: Path) -> None:
    spool = Spool(tmp_home / ".hands")
    job = _limited(spool, reset_at=None)
    assert resume_delay_s(job, now=NOW, backoff_minutes=30.0) == 30 * 60


def test_a_reset_already_past_resumes_after_the_grace_only(tmp_home: Path) -> None:
    """A daemon restart can leave a stored reset behind us; that is not a reason to wait."""
    spool = Spool(tmp_home / ".hands")
    job = _limited(spool, reset_at=to_iso(NOW - timedelta(hours=2)))
    assert resume_delay_s(job, now=NOW, backoff_minutes=30.0) == RESUME_GRACE_S


# ------------------------------------------------------------- the manager


@pytest.fixture
def cfg(tmp_home: Path, tmp_path: Path) -> Config:
    return make_cfg(tmp_home, tmp_path)


def make_cfg(
    tmp_home: Path,
    tmp_path: Path,
    *,
    builder: dict[str, Any] | None = None,
    aux: dict[str, Any] | None = None,
) -> Config:
    """§13 roles; the two dicts add keys to a role table (H-008: `resume_line`)."""
    work = tmp_path / "work"
    work.mkdir(exist_ok=True)
    return parse_config(
        {
            "roles": {
                "builder": {"cwd": str(work), **(builder or {})},
                "aux": {"cwd": str(work), **(aux or {})},
            },
            "limits": {"backoff_minutes": 30, "max_resumes": 3},
        },
        project="demo",
        path=tmp_home / ".hands" / "demo.toml",
    )


class Harness:
    """A LimitManager whose sleep records instead of sleeping, and whose enqueue is a spool."""

    def __init__(self, cfg: Config, spool: Spool) -> None:
        self.spool = spool
        self.delays: list[float] = []
        self.stops: list[tuple[str, dict[str, Any]]] = []
        self.manager = LimitManager(
            cfg,
            spool,
            enqueue=self._enqueue,
            clock=lambda: NOW,
            sleep=self._sleep,
        )
        self.manager.on_stop = self._stop

    async def _sleep(self, seconds: float) -> None:
        self.delays.append(seconds)

    async def _enqueue(self, **kwargs: Any) -> Job:
        return self.spool.create_job(**kwargs)

    def _stop(self, reason: str, payload: dict[str, Any]) -> None:
        self.stops.append((reason, payload))

    async def limit(self, *, role: str = "builder", prompt: str = "work", notice: str = "") -> Job:
        job = self.spool.create_job(role=role, context="clear", prompt=prompt, origin="cli")
        self.spool.transition(job, "running")
        job = self.spool.transition(
            job,
            "limited",
            limit={
                "category": "rate_limit",
                "message": notice,
                "reset_at": to_iso(parse_reset_at(notice, now=NOW)),
            },
        )
        await self.manager.on_job_finished(job)
        await self.manager.drain()
        return job

    async def finish_done(self, role: str = "builder") -> None:
        job = self.spool.create_job(role=role, context="clear", prompt="x", origin="playbook")
        self.spool.transition(job, "running")
        await self.manager.on_job_finished(self.spool.transition(job, "done"))

    def resumes(self) -> list[Job]:
        return [job for job in self.spool.list_jobs() if job.resumed_from]

    def kinds(self) -> list[str]:
        return [event.kind for event in self.spool.events()]


@pytest.fixture
def harness(cfg: Config, tmp_home: Path) -> Harness:
    return Harness(cfg, Spool(tmp_home / ".hands"))


def run(coro: Callable[[], Awaitable[None]]) -> None:
    asyncio.run(coro())


def test_a_limited_builder_is_resumed_with_the_resume_line(
    tmp_home: Path, tmp_path: Path
) -> None:
    """H-008: `resume_line` set — the spanweave form sends that line, `clear`."""
    cfg = make_cfg(tmp_home, tmp_path, builder={"resume_line": "Resume WORKPLAN.md"})
    harness = Harness(cfg, Spool(tmp_home / ".hands"))

    async def scenario() -> None:
        limited = await harness.limit(
            prompt="Read meta/BUILDER-2-PROMPT.md",
            notice="Usage limit reached, resets at 3pm",
        )
        (resume,) = harness.resumes()
        assert resume.prompt == "Resume WORKPLAN.md"  # roles.builder.resume_line (§13)
        assert resume.context == "clear"
        assert resume.resumed_from == limited.id
        assert resume.origin == "limit"  # §6, H-004: not a client's origin
        assert harness.delays == [3 * 3600 + RESUME_GRACE_S]

    run(scenario)


def test_a_limited_builder_without_a_resume_line_is_sent_its_own_prompt_again(
    harness: Harness,
) -> None:
    """H-008: `resume_line` absent — §6 re-sends the limited job's own prompt, `clear`.

    The agile-skills form: the kickoff line is checkpoint-driven, so the prompt
    that was limited is exactly the right thing to send again.
    """

    async def scenario() -> None:
        limited = await harness.limit(
            prompt="Read meta/BUILDER-2-PROMPT.md and execute the mission",
            notice="Usage limit reached, resets at 3pm",
        )
        (resume,) = harness.resumes()
        assert resume.prompt == "Read meta/BUILDER-2-PROMPT.md and execute the mission"
        assert resume.context == "clear"
        assert resume.resumed_from == limited.id
        assert resume.origin == "limit"

    run(scenario)


def test_a_limited_aux_job_is_sent_the_same_prompt_again(harness: Harness) -> None:
    async def scenario() -> None:
        limited = await harness.limit(role="aux", prompt="audit run 3")
        (resume,) = harness.resumes()
        assert resume.role == "aux"
        assert resume.prompt == "audit run 3"
        assert resume.resumed_from == limited.id
        # no reset time in the notice → limits.backoff_minutes
        assert harness.delays == [30 * 60]

    run(scenario)


def test_a_limited_aux_job_ignores_a_resume_line(tmp_home: Path, tmp_path: Path) -> None:
    """H-008: aux is unchanged — always the same prompt again, line or no line."""
    cfg = make_cfg(tmp_home, tmp_path, aux={"resume_line": "Resume WORKPLAN.md"})
    harness = Harness(cfg, Spool(tmp_home / ".hands"))

    async def scenario() -> None:
        await harness.limit(role="aux", prompt="audit run 3")
        (resume,) = harness.resumes()
        assert resume.prompt == "audit run 3"

    run(scenario)


def test_one_inbox_event_per_limit_and_per_resume(harness: Harness) -> None:
    async def scenario() -> None:
        limited = await harness.limit(notice="Usage limit reached, resets at 3pm")
        assert harness.kinds() == ["limit", "resume"]
        limit_event, resume_event = harness.spool.events()
        assert limit_event.payload["job"] == limited.id
        assert limit_event.payload["message"] == "Usage limit reached, resets at 3pm"
        assert limit_event.payload["reset_at"] is not None
        assert resume_event.payload["resumed_from"] == limited.id
        assert resume_event.payload["job"] == harness.resumes()[0].id
        assert resume_event.payload["origin"] == "limit"  # §6, H-004

    run(scenario)


def test_resumes_stop_after_max_resumes_and_leave_a_stop_for_the_playbook(
    harness: Harness,
) -> None:
    async def scenario() -> None:
        for _ in range(3):  # limits.max_resumes = 3
            await harness.limit()
        assert len(harness.resumes()) == 3
        assert harness.stops == []

        await harness.limit()  # the fourth limit with no `done` in between
        assert len(harness.resumes()) == 3  # no fourth resume
        # §10: every stop goes through the playbook engine's one `stop()`, which
        # the daemon wires to `on_stop`; the manager does not write the `stop`
        # event itself, or a limit stop over an existing one would be the one
        # stop recorded twice. `tests/test_playbook.py` pins the event and the
        # notification over the real daemon wiring.
        assert "stop" not in harness.kinds()
        assert len(harness.stops) == 1
        reason, payload = harness.stops[0]
        assert "max_resumes" in strip_paths(reason)
        assert payload["role"] == "builder"
        assert payload["resumes"] == 3

    run(scenario)


def test_the_counter_is_per_role(harness: Harness) -> None:
    async def scenario() -> None:
        for _ in range(3):
            await harness.limit(role="builder")
        await harness.limit(role="aux")
        assert harness.stops == []
        assert len(harness.resumes()) == 4

    run(scenario)


def test_a_done_job_resets_the_counter(harness: Harness) -> None:
    async def scenario() -> None:
        for _ in range(3):
            await harness.limit()
        await harness.finish_done()
        assert harness.spool.read_role("builder").consecutive_resumes == 0
        await harness.limit()
        assert len(harness.resumes()) == 4  # resumed again, not stopped
        assert harness.stops == []

    run(scenario)


def test_max_resumes_is_a_parameter_the_playbook_can_override(harness: Harness) -> None:
    async def scenario() -> None:
        harness.manager.max_resumes = 1  # §10: the playbook may override it
        await harness.limit()
        await harness.limit()
        assert len(harness.resumes()) == 1
        assert len(harness.stops) == 1

    run(scenario)


def test_the_session_id_of_a_later_job_does_not_clear_the_counter(harness: Harness) -> None:
    """`set_last_session` is written on every job; the counter must survive it."""

    async def scenario() -> None:
        await harness.limit()
        harness.spool.set_last_session("builder", session_id="sess-9", job_id="j9")
        assert harness.spool.read_role("builder").consecutive_resumes == 1

    run(scenario)


# ---------------------------------------------------- the daemon end to end


def test_the_daemon_resumes_a_limited_builder(tmp_home: Path, tmp_path: Path) -> None:
    """The whole path: a limited job, the scheduled wait, a resume job that runs.

    The wait is real code with a fake sleep — nothing here waits out a limit.
    """
    from hands.config import load_config
    from hands.daemon import Daemon
    from harness import PROJECT, config_body, write_project

    work = tmp_path / "work"
    work.mkdir(exist_ok=True)
    write_project(
        tmp_home, config_body(tmp_home, work, builder='resume_line = "Resume WORKPLAN.md"')
    )
    slept: list[float] = []

    async def instant(seconds: float) -> None:
        slept.append(seconds)

    async def scenario() -> None:
        daemon = Daemon(load_config(PROJECT))
        daemon.limits.sleep = instant
        await daemon.start()
        try:
            sent = await daemon.api.send(
                role="builder",
                context="clear",
                prompt="FAKE:result Usage limit reached, try again in 20 minutes",
            )
            limited = await daemon.wait_for_terminal(sent["id"], timeout=30)
            assert limited is not None and limited.state == "limited"
            await daemon.limits.drain()

            resumes = [job for job in daemon.spool.list_jobs() if job.resumed_from]
            assert [job.resumed_from for job in resumes] == [sent["id"]]
            assert resumes[0].prompt == "Resume WORKPLAN.md"
            finished = await daemon.wait_for_terminal(resumes[0].id, timeout=30)
            assert finished is not None and finished.state == "done"
            # the `done` clears the counter §6 counts resumes with
            assert daemon.spool.read_role("builder").consecutive_resumes == 0
            assert [event.kind for event in daemon.spool.events()] == [
                "job.limited", "limit", "resume", "job.done",
            ]
            assert slept and 19 * 60 < slept[0] <= 20 * 60 + RESUME_GRACE_S
        finally:
            await daemon.stop()

    asyncio.run(scenario())
