"""A pause that holds the next step (DESIGN §44 rules 1, 2, 3, 5 and 6; H-078; also
§6, §10, §19, §29, §31, §32, §33, §38).

A human pause is `paused_by` `cli` or `phone`, set by `pause`; any other stop is
not one and keeps §10. Under a human pause a role's end whose decision would send,
consult or stop is kept, one per role, in `pipeline.json`; a `notify` fires at once;
a `resume` rule fires until a stop has been suppressed under the pause; every
suppressed stop is notified once; `go` and `consult` are refused; `resume` reloads,
refuses on a playbook that does not load, replays the kept ends up to the first
that starts a job or stops, and discards the rest.

Most tests drive `PlaybookEngine` with test_playbook's recording seams, on a
role-mode autonomous playbook unless named; a restart is a second engine (or a
second daemon) on the same home. The daemon-level ones run a real daemon over its
socket with `tests/fake_claude.py`.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from conftest import commit_file, strip_paths
from hands.cli import _job_block, _pipeline_block
from hands.config import load_config
from hands.daemon import Daemon
from hands.gates import decide
from hands.limits import LimitManager
from hands.phone import status_summary
from hands.playbook import (
    KEPT_DISCARDED_TITLE,
    SUPPRESSED_HUMAN_TITLE,
    PlaybookEngine,
    ResumeRefused,
)
from hands.spool import Job, Spool
from harness import (
    BLOCK,
    PROJECT,
    TIMEOUT,
    config_body,
    fails,
    ok,
    poll,
    running_job,
)
from test_playbook import (
    ROOT_PLAYBOOK,
    Recorder,
    _driver_job,
    applied_kit,
    architect_dir,
    consultation,
    engine_for,
    filed_kit,
    finished,
    run,
)

STOPPED = "hands: the pipeline stopped"
CONSULT_TITLE = "hands: a consultation stopped over a paused pipeline"
KICKOFF = "Read meta/BUILDER-28-PROMPT.md and execute the mission below its divider."
REVIEW_PROMPT = "Review mission {n} of this repository"

#: §31's role mode with `autonomous`: a finished mission is reviewed, a review is
#: consulted on, a kit the engine approved is followed by the engine's kickoff.
HELD = f"""version = 1

[series]
name = "m28"
kickoff = "{KICKOFF}"
architect = "role"
autonomous = true

[limits]
max_architect_consults = 12
max_resumes = 2

[[rule]]
on = "builder.done"
verdict = '^VERDICT: mission (?P<n>\\d+) finished'
then = "send"
role = "aux"
context = "clear"
prompt = "{REVIEW_PROMPT}"

[[rule]]
on = "builder.done"
verdict = '^VERDICT: kit applied'
then = "notify"
message = "Kit applied"

[[rule]]
on = "builder.done"
verdict = '^VERDICT: question'
then = "stop"
message = "The builder asks a question"

[[rule]]
on = "builder.done"
verdict = '^VERDICT: note'
then = "notify"
message = "A builder note"

[[rule]]
on = "aux.done"
verdict = '^VERDICT: review mission (?P<n>\\d+)'
then = "consult"
role = "architect"

[[rule]]
on = "builder.orphaned"
then = "resume"

[[rule]]
on = "aux.orphaned"
then = "resume"

[[rule]]
on = "monitor.tripwire"
then = "stop"
message = "Tripwire fired"
"""

FINISHED = "VERDICT: mission 28 finished"
QUESTION = "VERDICT: question which option, A or B?"
REVIEWED = "VERDICT: review mission 28 blockers=0 should-fix=1"


@pytest.fixture
def workdir(tmp_path: Path) -> Path:
    d = tmp_path / "work"
    d.mkdir(exist_ok=True)
    return d


def held_engine(
    tmp_home: Path, workdir: Path, body: str | None = HELD, **kw: Any
) -> tuple[PlaybookEngine, Recorder]:
    return engine_for(tmp_home, workdir, body, architect=architect_dir(tmp_home), **kw)


def restarted(tmp_home: Path, workdir: Path) -> tuple[PlaybookEngine, Recorder]:
    """A second engine on the same home: what a daemon restart reads back."""
    return held_engine(tmp_home, workdir, None)


def ended(spool: Spool, role: str, verdict: str | None, *, origin: str = "playbook",
          state: str = "done", **kw: Any) -> Job:
    return finished(spool, role=role, verdict=verdict, origin=origin, state=state, **kw)


def titles(recorder: Recorder) -> list[str]:
    return [title for title, _ in recorder.notified]


def kinds(engine: PlaybookEngine) -> list[str]:
    return [event.kind for event in engine.spool.events()]


def kept_jobs(engine: PlaybookEngine) -> list[str]:
    return [entry["job"] for entry in engine.pipeline()["kept"]]


def paused_by_human(engine: PlaybookEngine, by: str = "cli") -> bool:
    state = engine.pipeline()
    return state["paused"] is True and state["paused_by"] == by and state["human_pause"]


# --------------------------------------------------- rule 1: a role's end waits


def test_a_builder_end_under_a_human_pause_is_kept_and_resume_starts_the_review(
    tmp_home: Path, workdir: Path
) -> None:
    engine, recorder = held_engine(tmp_home, workdir)
    running = engine.spool.create_job(role="builder", context="clear", prompt="p", origin="cli")
    run(engine.on_job_start(running))
    run(engine.pause())
    job = engine.spool.transition(engine.spool.transition(running, "running"), "done",
                                  verdict=FINISHED, result=FINISHED)
    run(engine.on_job(job))
    assert recorder.sent == [] and recorder.enqueued == [], "no review is started"
    (entry,) = engine.pipeline()["kept"]
    assert (entry["event"], entry["role"], entry["job"], entry["verdict"]) == (
        "builder.done", "builder", job.id, FINISHED,
    )
    assert titles(recorder) == [STOPPED], "the pause's own stop, and nothing else"
    assert paused_by_human(engine)
    # §44 rule 6: the kept end is in pipeline.json, so a restart keeps it.
    again, _ = restarted(tmp_home, workdir)
    assert kept_jobs(again) == [job.id]

    state = run(engine.resume())
    assert state["paused"] is False and state["kept"] == []
    (sent,) = recorder.sent
    assert (sent["role"], sent["prompt"], sent["origin"]) == (
        "aux", "Review mission 28 of this repository", "playbook",
    )
    assert kinds(engine).count("stop") == 1, "the pause's own stop only"


def test_a_review_end_under_a_human_pause_keeps_the_consultation_until_resume(
    tmp_home: Path, workdir: Path
) -> None:
    engine, recorder = held_engine(tmp_home, workdir)
    run(engine.pause())
    review = ended(engine.spool, "aux", REVIEWED)
    run(engine.on_job(review))
    assert recorder.enqueued == [] and kinds(engine).count("consult.sent") == 0
    assert kept_jobs(engine) == [review.id]

    run(engine.resume())
    (consulted,) = recorder.enqueued
    assert consulted["role"] == "architect"
    assert kinds(engine).count("consult.sent") == 1
    assert engine.pipeline()["paused"] is False


def test_an_engine_approved_applys_end_is_kept_for_the_kickoff(
    tmp_home: Path, workdir: Path
) -> None:
    engine, recorder = held_engine(tmp_home, workdir)
    run(engine.pause())
    applied = applied_kit(engine.spool)  # approved by the engine before the pause
    run(engine.on_job(applied))
    assert recorder.sent == [], "the kickoff waits for resume"
    assert kept_jobs(engine) == [applied.id]
    assert titles(recorder) == [STOPPED], "the playbook's `kit applied` notify did not fire"

    run(engine.resume())
    (kickoff,) = recorder.sent
    assert (kickoff["role"], kickoff["prompt"], kickoff["context"]) == ("builder", KICKOFF, "clear")
    assert engine.state.last_rule is not None and engine.state.last_rule["rule"] == -1


def test_a_consultation_ending_under_a_human_pause_leaves_its_apply_to_the_human(
    tmp_home: Path, workdir: Path
) -> None:
    """§44 rule 2: no engine approval, the apply held for the human; after the
    human approves it, its end is decided by the playbook's rule, and no engine
    kickoff follows."""
    engine, recorder = held_engine(tmp_home, workdir)
    run(engine.pause())
    during = consultation(engine.spool)  # running when the pause was sent
    apply = filed_kit(engine.spool, during=during)
    run(engine.on_event("job.held", job=apply))
    done = engine.spool.transition(during, "done", verdict="VERDICT: next kit m16",
                                   result="VERDICT: next kit m16")
    run(engine.on_job(done))
    assert recorder.approved == []
    assert engine.spool.load_job(apply.id).state == "held"

    assert apply.gate is not None
    gate = decide(apply.gate, decision="approved", decided_by="phone", reason="ok")
    started = engine.spool.transition(apply.id, "queued", gate=gate)
    run(engine.on_job_start(started))
    engine.spool.transition(started, "running")
    applied = engine.spool.transition(started.id, "done", verdict="VERDICT: kit applied abc",
                                      result="VERDICT: kit applied abc")
    run(engine.on_job(applied))
    assert recorder.sent == [], "no engine kickoff after a human's approval"
    assert titles(recorder).count("hands: Kit applied") == 1, "the playbook's notify fires"
    assert kept_jobs(engine) == [] and paused_by_human(engine)


def test_a_question_kept_under_a_human_pause_stops_at_resume(
    tmp_home: Path, workdir: Path
) -> None:
    engine, recorder = held_engine(tmp_home, workdir)
    run(engine.pause())
    asked = ended(engine.spool, "builder", QUESTION, origin="cli")
    run(engine.on_job(asked))
    assert kept_jobs(engine) == [asked.id]
    assert titles(recorder) == [STOPPED]

    state = run(engine.resume())
    assert state["paused"] is True and state["paused_by"] == "stop"
    assert state["stop_reason"] == "The builder asks a question"
    assert state["kept"] == [] and not state["human_pause"]
    assert titles(recorder) == [STOPPED, STOPPED]


def test_a_notify_role_end_fires_at_once_under_a_human_pause(
    tmp_home: Path, workdir: Path
) -> None:
    engine, recorder = held_engine(tmp_home, workdir)
    run(engine.pause())
    noted = ended(engine.spool, "builder", "VERDICT: note the tree is clean")
    run(engine.on_job(noted))
    assert titles(recorder) == [STOPPED, "hands: A builder note"]
    assert kept_jobs(engine) == [] and paused_by_human(engine)


def test_the_humans_own_send_under_the_pause_replaces_the_kept_builder_end(
    tmp_home: Path, workdir: Path
) -> None:
    engine, recorder = held_engine(tmp_home, workdir)
    run(engine.pause())
    first = ended(engine.spool, "builder", FINISHED)
    run(engine.on_job(first))
    review = ended(engine.spool, "aux", REVIEWED)
    run(engine.on_job(review))
    # the human's own send: a cli job starting under a human pause does not end it
    sent = engine.spool.create_job(role="builder", context="keep", prompt="go on", origin="cli")
    run(engine.on_job_start(sent))
    assert paused_by_human(engine)
    engine.spool.transition(sent, "running")
    later = engine.spool.transition(sent.id, "done", verdict=QUESTION, result=QUESTION)
    run(engine.on_job(later))
    assert kept_jobs(engine) == [review.id, later.id], "the later end takes the later place"
    (replaced,) = [e.payload for e in engine.spool.events() if e.kind == "pipeline.kept_replaced"]
    assert (replaced["role"], replaced["replaced"], replaced["by"]) == (
        "builder", first.id, later.id,
    )
    assert kinds(engine).count("pipeline.resumed") == 0


def test_a_decisions_kit_applied_under_the_pause_does_not_end_it(
    tmp_home: Path, workdir: Path
) -> None:
    """§44 rule 3: a `kit`-origin apply held, approved and ended under a human pause
    leaves it, the kept end still kept, and its hold is no stop."""
    engine, recorder = held_engine(tmp_home, workdir)
    run(engine.pause())
    first = ended(engine.spool, "builder", FINISHED)
    run(engine.on_job(first))
    apply = filed_kit(engine.spool, origin="kit")
    run(engine.on_event("job.held", job=apply))
    assert kinds(engine).count("stop") == 1
    assert kinds(engine).count("pipeline.stop_suppressed") == 0
    assert apply.gate is not None
    gate = decide(apply.gate, decision="approved", decided_by="phone", reason="ok")
    started = engine.spool.transition(apply.id, "queued", gate=gate)
    run(engine.on_job_start(started))
    engine.spool.transition(started, "running")
    applied = engine.spool.transition(started.id, "done", verdict="VERDICT: kit applied d1",
                                      result="VERDICT: kit applied d1")
    run(engine.on_job(applied))
    assert paused_by_human(engine) and kinds(engine).count("pipeline.resumed") == 0
    assert kept_jobs(engine) == [first.id]
    assert engine.pipeline()["suppressed_stop"] is None
    assert recorder.sent == []


# ------------------------------------- rule 2: everything else, nothing silent


def test_a_tripwire_under_a_human_pause_is_notified_once_and_the_kept_end_stays(
    tmp_home: Path, workdir: Path
) -> None:
    engine, recorder = held_engine(tmp_home, workdir)
    run(engine.pause())
    first = ended(engine.spool, "builder", FINISHED)
    run(engine.on_job(first))
    run(engine.on_event("monitor.tripwire", payload={"job": first.id}))
    assert titles(recorder) == [STOPPED, SUPPRESSED_HUMAN_TITLE]
    assert recorder.notified[-1][1]["reason"] == "Tripwire fired"
    assert paused_by_human(engine) and kept_jobs(engine) == [first.id]
    assert engine.pipeline()["suppressed_stop"] == "Tripwire fired"
    assert kinds(engine).count("stop") == 1


def test_a_max_resumes_stop_under_a_human_pause_is_notified(
    tmp_home: Path, workdir: Path
) -> None:
    engine, recorder = held_engine(tmp_home, workdir)
    run(engine.pause())
    engine.spool.update_role("builder", consecutive_resumes=2)
    orphan = ended(engine.spool, "builder", None, state="orphaned")
    run(engine.on_job(orphan))
    assert recorder.enqueued == []
    assert titles(recorder) == [STOPPED, SUPPRESSED_HUMAN_TITLE]
    assert "max_resumes is 2" in strip_paths(recorder.notified[-1][1]["reason"])
    assert paused_by_human(engine) and engine.pipeline()["suppressed_stop"]


def test_after_a_suppressed_stop_a_restart_does_not_resume_the_orphaned_builder(
    tmp_home: Path, workdir: Path
) -> None:
    engine, recorder = held_engine(tmp_home, workdir)
    run(engine.pause())
    run(engine.on_event("monitor.tripwire", payload={}))
    assert titles(recorder) == [STOPPED, SUPPRESSED_HUMAN_TITLE]
    again, after = restarted(tmp_home, workdir)
    assert again.pipeline()["suppressed_stop"] == "Tripwire fired"
    orphan = ended(again.spool, "builder", None, state="orphaned")
    run(again.on_job(orphan))
    assert after.enqueued == [], "a resume rule fires nothing past a suppressed stop"
    assert paused_by_human(again)


def test_a_drivers_escalation_under_a_human_pause_is_notified_and_not_kept(
    tmp_home: Path, workdir: Path
) -> None:
    engine, recorder = held_engine(tmp_home, workdir, driver=workdir.parent / "d")
    run(engine.pause())
    about = ended(engine.spool, "builder", QUESTION, origin="cli")
    driver = _driver_job(engine.spool, state="done", verdict="VERDICT: escalate it is yours",
                         about=about)
    run(engine.on_job(driver))
    assert titles(recorder) == [STOPPED, CONSULT_TITLE]
    assert kept_jobs(engine) == []
    assert paused_by_human(engine) and engine.pipeline()["suppressed_stop"]


def test_a_limited_builder_under_the_pause_is_resumed_by_section_6_and_its_end_kept(
    tmp_home: Path, workdir: Path
) -> None:
    engine, recorder = held_engine(tmp_home, workdir)

    async def no_sleep(_: float) -> None:
        return None

    limits = LimitManager(engine.config, engine.spool, enqueue=recorder.enqueue,
                          sleep=no_sleep, on_stop=engine.stop)
    engine.limits = limits
    run(engine.pause())
    limited = ended(engine.spool, "builder", None, origin="cli", state="limited")

    async def limit() -> None:
        await limits.on_job_finished(limited)
        await engine.on_job(limited)
        await limits.drain()

    run(limit())
    (resume,) = recorder.enqueued
    assert (resume["origin"], resume["resumed_from"]) == ("limit", limited.id)
    assert kinds(engine).count("stop") == 1 and engine.pipeline()["suppressed_stop"] is None
    resumed = ended(engine.spool, "builder", FINISHED, origin="limit",
                    resumed_from=limited.id)
    run(engine.on_job_start(resumed))
    run(engine.on_job(resumed))
    assert kept_jobs(engine) == [resumed.id] and recorder.sent == []


def test_a_restart_under_a_human_pause_resumes_the_orphan_and_keeps_the_kept_ends(
    tmp_home: Path, workdir: Path
) -> None:
    engine, _recorder = held_engine(tmp_home, workdir)
    run(engine.pause())
    review = ended(engine.spool, "aux", REVIEWED)
    run(engine.on_job(review))
    again, after = restarted(tmp_home, workdir)
    orphan = ended(again.spool, "builder", None, origin="cli", state="orphaned")
    run(again.on_job(orphan))
    (resume,) = after.enqueued
    assert (resume["role"], resume["resumed_from"], resume["origin"]) == (
        "builder", orphan.id, "playbook",
    )
    assert kept_jobs(again) == [review.id] and paused_by_human(again)


def test_a_restart_under_a_rules_stop_resumes_nothing(tmp_home: Path, workdir: Path) -> None:
    engine, _recorder = held_engine(tmp_home, workdir)
    run(engine.stop("because", {}))
    again, after = restarted(tmp_home, workdir)
    orphan = ended(again.spool, "builder", None, origin="cli", state="orphaned")
    run(again.on_job(orphan))
    assert after.enqueued == []


# ------------------------------------------------- rule 3: only resume ends it


def test_a_second_pause_keeps_everything_and_a_restart_still_resumes_the_orphan(
    tmp_home: Path, workdir: Path
) -> None:
    engine, recorder = held_engine(tmp_home, workdir)
    run(engine.pause(by="phone"))
    review = ended(engine.spool, "aux", REVIEWED)
    run(engine.on_job(review))
    state = run(engine.pause())
    assert state["already_stopped"] is True
    assert paused_by_human(engine, "phone") and kept_jobs(engine) == [review.id]
    assert state["suppressed_stop"] is None
    assert titles(recorder) == [STOPPED], "a pause over the human pause is not notified"
    again, after = restarted(tmp_home, workdir)
    orphan = ended(again.spool, "builder", None, origin="cli", state="orphaned")
    run(again.on_job(orphan))
    assert len(after.enqueued) == 1


def test_a_pause_over_another_stop_is_still_a_no_op(tmp_home: Path, workdir: Path) -> None:
    engine, recorder = held_engine(tmp_home, workdir)
    run(engine.stop("because", {}))
    state = run(engine.pause())
    assert state["already_stopped"] is True and state["paused_by"] == "stop"
    assert not state["human_pause"]
    run(engine.on_job(ended(engine.spool, "builder", FINISHED)))
    assert kept_jobs(engine) == [] and recorder.sent == []
    run(engine.on_event("monitor.tripwire", payload={}))
    assert titles(recorder) == [STOPPED], "§10: a suppressed stop over a stop notifies nobody"


def test_an_unpaused_pipeline_is_unchanged(tmp_home: Path, workdir: Path) -> None:
    engine, recorder = held_engine(tmp_home, workdir)
    run(engine.on_job(ended(engine.spool, "builder", FINISHED)))
    assert len(recorder.sent) == 1
    state = engine.pipeline()
    assert state["kept"] == [] and state["human_pause"] is False
    assert state["suppressed_stop"] is None


# ------------------------------------------------------- rule 5: resume replays


def test_pause_then_resume_with_no_playbook_and_nothing_kept_un_pauses(
    tmp_home: Path, workdir: Path
) -> None:
    """Doctor's install check runs before any playbook exists."""
    engine, _recorder = engine_for(tmp_home, workdir, None)
    run(engine.pause())
    assert run(engine.resume())["paused"] is False


def test_resume_is_refused_while_the_playbook_does_not_load_then_accepted(
    tmp_home: Path, workdir: Path
) -> None:
    engine, recorder = held_engine(tmp_home, workdir)
    run(engine.pause())
    first = ended(engine.spool, "builder", FINISHED)
    run(engine.on_job(first))
    commit_file(workdir, "PLAYBOOK.toml", "version = [\n")
    with pytest.raises(ResumeRefused) as refused:
        run(engine.resume())
    assert "cannot be read" in strip_paths(str(refused.value))
    assert paused_by_human(engine) and kept_jobs(engine) == [first.id]
    assert titles(recorder) == [STOPPED], "a refused resume is not notified"
    assert engine.pipeline()["suppressed_stop"] is None

    commit_file(workdir, "PLAYBOOK.toml", HELD)
    run(engine.resume())
    assert len(recorder.sent) == 1 and engine.pipeline()["paused"] is False


def test_an_apply_that_commits_a_playbook_that_does_not_load_refuses_the_resume(
    tmp_home: Path, workdir: Path
) -> None:
    """The apply's end is kept for the kickoff (decided with the playbook loaded at
    its arrival; H-044's reload waits for `resume`'s), then `resume` is refused
    with the load's reason."""
    engine, recorder = held_engine(tmp_home, workdir)
    run(engine.reload())  # the apply's start loaded the playbook in force (§10)
    run(engine.pause())
    commit_file(workdir, "PLAYBOOK.toml", "version = [\n")  # what the apply committed
    applied = applied_kit(engine.spool)
    run(engine.on_job(applied))
    assert kept_jobs(engine) == [applied.id] and recorder.sent == []
    with pytest.raises(ResumeRefused) as refused:
        run(engine.resume())
    assert "cannot be read" in strip_paths(str(refused.value))
    assert paused_by_human(engine) and kept_jobs(engine) == [applied.id]
    assert recorder.sent == []


def test_resume_with_ends_kept_and_no_playbook_is_refused(
    tmp_home: Path, workdir: Path
) -> None:
    engine, _recorder = held_engine(tmp_home, workdir)
    run(engine.pause())
    first = ended(engine.spool, "builder", FINISHED)
    run(engine.on_job(first))
    commit_file(workdir, "PLAYBOOK.toml", HELD)  # still committed; now removed
    (workdir / "PLAYBOOK.toml").unlink()
    with pytest.raises(ResumeRefused) as refused:
        run(engine.resume())
    assert "no playbook" in strip_paths(str(refused.value))
    assert paused_by_human(engine) and kept_jobs(engine) == [first.id]


def test_a_playbook_committed_at_rest_is_the_one_the_replay_uses(
    tmp_home: Path, workdir: Path
) -> None:
    engine, recorder = held_engine(tmp_home, workdir)
    run(engine.pause())
    run(engine.on_job(ended(engine.spool, "builder", FINISHED)))
    commit_file(workdir, "PLAYBOOK.toml",
                HELD.replace(REVIEW_PROMPT, "Review mission {n} as ruled at rest"))
    run(engine.resume())
    (sent,) = recorder.sent
    assert sent["prompt"] == "Review mission 28 as ruled at rest"


def test_a_replayed_keep_send_the_api_refuses_stops_the_replay(
    tmp_home: Path, workdir: Path
) -> None:
    engine, recorder = held_engine(tmp_home, workdir, HELD.replace(
        'role = "aux"\ncontext = "clear"', 'role = "aux"\ncontext = "keep"'))
    run(engine.pause())
    run(engine.on_job(ended(engine.spool, "builder", FINISHED)))
    recorder.refuse = "the aux's last job has not ended"
    state = run(engine.resume())
    assert state["paused"] is True and state["paused_by"] == "stop"
    assert "could not send to aux" in strip_paths(state["stop_reason"])
    assert "the aux's last job has not ended" in strip_paths(state["stop_reason"])


def test_two_kept_ends_the_first_stops_and_the_second_is_discarded_and_named(
    tmp_home: Path, workdir: Path
) -> None:
    engine, recorder = held_engine(tmp_home, workdir)
    run(engine.pause())
    asked = ended(engine.spool, "builder", QUESTION)
    review = ended(engine.spool, "aux", REVIEWED)
    run(engine.on_job(asked))
    run(engine.on_job(review))
    state = run(engine.resume())
    assert state["stop_reason"] == "The builder asks a question"
    assert recorder.enqueued == [], "the review's consultation is discarded"
    (discarded,) = [e.payload for e in engine.spool.events()
                    if e.kind == "pipeline.kept_discarded"]
    assert discarded["after"] == asked.id
    assert [entry["job"] for entry in discarded["discarded"]] == [review.id]
    (note,) = [payload for title, payload in recorder.notified if title == KEPT_DISCARDED_TITLE]
    assert review.id in strip_paths(note["reason"]) and REVIEWED in strip_paths(note["reason"])
    assert state["kept"] == []


def test_two_kept_ends_the_first_starts_a_job_and_the_second_is_discarded_and_named(
    tmp_home: Path, workdir: Path
) -> None:
    engine, recorder = held_engine(tmp_home, workdir)
    run(engine.pause())
    review = ended(engine.spool, "aux", REVIEWED)
    done = ended(engine.spool, "builder", FINISHED)
    run(engine.on_job(review))
    run(engine.on_job(done))
    state = run(engine.resume())
    assert state["paused"] is False
    assert [item["role"] for item in recorder.enqueued] == ["architect"]
    assert recorder.sent == [], "the builder's end is discarded, its review not sent"
    (note,) = [payload for title, payload in recorder.notified if title == KEPT_DISCARDED_TITLE]
    assert done.id in strip_paths(note["reason"])
    assert "started a job" in strip_paths(note["reason"])


def test_this_repositorys_playbook_under_a_pause_keeps_the_clean_review_stop(
    tmp_home: Path, workdir: Path
) -> None:
    """Phone mode: the review's `blockers=0` stop is kept, then stops at `resume`."""
    engine, recorder = engine_for(tmp_home, workdir, ROOT_PLAYBOOK.read_text(encoding="utf-8"),
                                  driver=workdir.parent / "d")
    run(engine.pause())
    review = ended(engine.spool, "aux", REVIEWED)
    run(engine.on_job(review))
    assert kept_jobs(engine) == [review.id] and titles(recorder) == [STOPPED]
    state = run(engine.resume())
    assert state["stop_reason"] == "Mission 28 reviewed clean; next mission is the architect's"


# ------------------------------------------------------- rule 6: it shows


def test_hands_pipeline_prints_one_kept_line_per_end(tmp_home: Path, workdir: Path) -> None:
    engine, _recorder = held_engine(tmp_home, workdir)
    run(engine.pause())
    long = "VERDICT: question " + "x" * 200
    asked = ended(engine.spool, "builder", long)
    review = ended(engine.spool, "aux", REVIEWED)
    run(engine.on_job(asked))
    run(engine.on_job(review))
    text = _pipeline_block(engine.pipeline())
    lines = [line for line in text.splitlines() if line.startswith("  kept ")]
    assert len(lines) == 2, text
    assert f"builder job {asked.id} on builder.done: VERDICT: question x" in lines[0]
    assert "x" * 120 not in strip_paths(lines[0]), "the verdict line is cut"
    assert f"aux job {review.id} on aux.done: {REVIEWED}" in lines[1]
    assert "  paused   yes (cli)" in strip_paths(text)


def test_hands_show_prints_resumed_from_when_it_is_set() -> None:
    shown = _job_block({"id": "j2", "role": "builder", "state": "queued",
                        "resumed_from": "j1"})
    assert "\n  resumed_from j1\n" in strip_paths(shown + "\n")
    plain = _job_block({"id": "j1", "role": "builder", "state": "done"})
    assert "resumed_from" not in strip_paths(plain)


# ------------------------------------------------------- over a real daemon


NOTIFY = """
[notify]
ntfy_url = "https://ntfy.example"
ntfy_topic = "hands-events-test"
"""

DAEMON_BOOK = f"""version = 1

[series]
kickoff = "{KICKOFF}"

[[rule]]
on = "builder.orphaned"
then = "resume"

[[rule]]
on = "aux.done"
then = "stop"
message = "Reviewed"
"""


class Posts:
    """Every publish; no test reaches a network (§11)."""

    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    async def __call__(self, url: str, **kwargs: Any) -> int:
        self.sent.append({"url": url, **kwargs})
        return 200


def life(body: Any) -> Posts:
    posts = Posts()

    async def scenario() -> None:
        daemon = Daemon(load_config(PROJECT))
        daemon.notifier.post = posts
        await daemon.start()
        try:
            await asyncio.wait_for(body(daemon), TIMEOUT)
        finally:
            await daemon.stop()

    asyncio.run(scenario())
    return posts


def test_a_daemon_restart_under_a_human_pause_resumes_the_builder_it_killed(
    tmp_home: Path, workdir: Path
) -> None:
    """§44 rule 2, H-078: the start feeds the orphan once (`_feed_orphans`), and under
    a human pause its `builder.orphaned → resume` fires; the kept end stays."""
    (tmp_home / ".hands" / f"{PROJECT}.toml").write_text(
        config_body(tmp_home, workdir, builder="cancel_gated = false", extra=NOTIFY)
    )
    commit_file(workdir, "PLAYBOOK.toml", DAEMON_BOOK)
    seen: dict[str, Any] = {}

    async def first(daemon: Daemon) -> None:
        sent = await ok("send", "--role", "builder", "--context", "clear", f"{KICKOFF}\n{BLOCK}")
        await running_job("builder")
        assert (await ok("pause"))["paused_by"] == "cli"
        review = ended(daemon.spool, "aux", "VERDICT: review mission 28 blockers=0")
        await daemon.playbook.on_job(review)
        seen["orphan"], seen["review"] = sent["id"], review.id

    life(first)

    async def second(daemon: Daemon) -> None:
        async def resumed() -> Any:
            rows = [row for row in (await ok("jobs", "-n", "50"))["jobs"]
                    if row["role"] == "builder"]
            return rows if len(rows) == 2 else None

        rows = await poll(resumed, "the resumed builder job")
        job = next(row for row in rows if row["id"] != seen["orphan"])
        record = await ok("show", job["id"])
        assert record["resumed_from"] == seen["orphan"]
        state = await ok("pipeline")
        assert (state["paused"], state["paused_by"]) == (True, "cli")
        assert [entry["job"] for entry in state["kept"]] == [seen["review"]]
        # §44 rule 3: `go` and `consult` are refused under it, naming `resume`.
        for argv in (("go",), ("consult", "what next")):
            said = await fails(*argv)
            assert "paused by a human (cli)" in strip_paths(said), said
            assert "`resume`" in strip_paths(said), said
        # §44 rule 6: the phone's status names the human pause and the kept end.
        assert f"pipeline: paused by a human (cli); kept: aux {seen['review']}" in (
            status_summary(daemon).splitlines()
        )
        await running_job("builder")

    life(second)
