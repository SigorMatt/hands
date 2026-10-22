"""Mission 29 U4: an apply that did not land, the CI's hold, the journal sentence
(DESIGN §45 "An apply that did not land (H-080)", "A kit that carries the CI is
the owner's", "The journal under a `main` that takes pull requests only"; §19,
§31, §36, §39, §43, §44).

The `builder.done` of an apply as §43 counts one (a job with a `kit_id`, or a
resume of one) whose reply does not begin `VERDICT: kit applied` is the engine's
to decide, before any playbook rule: a stop over an unpaused pipeline, one
publication over a paused one, never kept. (§45's CI hold is §46's plan-files
rule since mission 30, tested in tests/test_plan_files.py.) Under
`[repository] main = "pull-request"` hands' journal sentence is §45's, word for
word; §36's reader strips both.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from pathlib import Path
from typing import Any

import pytest

from conftest import commit_file, strip_paths
from hands.config import parse_config
from hands.gates import decide
from hands.playbook import (
    JOURNAL_REMINDER,
    JOURNAL_REMINDER_PULL_REQUEST,
    PAUSE_REASON,
    SUPPRESSED_HUMAN_TITLE,
    PlaybookEngine,
    sent_prompt,
)
from hands.spool import Job, Spool, new_kit_id
from test_human_pause import FINISHED, held_engine, kept_jobs, paused_by_human
from test_playbook import (
    AUTONOMOUS,
    ROOT_PLAYBOOK,
    Recorder,
    applied_kit,
    engine_for,
    filed_kit,
    finished,
)

ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "DESIGN.md"
STOPPED = "hands: the pipeline stopped"
FAILED = "VERDICT: kit not applied pr=12 a check failed"
KICKOFF = "Read meta/BUILDER-16-PROMPT.md and execute the mission below its divider."


def reason(verdict: str) -> str:
    """§45's stop reason, word for word."""
    return f"the kit's apply did not land: {verdict} (§45)"


@pytest.fixture
def workdir(tmp_path: Path) -> Path:
    d = tmp_path / "work"
    d.mkdir(exist_ok=True)
    return d


def run(coro: Awaitable[Any]) -> Any:
    return asyncio.run(coro)  # type: ignore[arg-type]


def phone_apply(spool: Spool, verdict: str | None, *, state: str = "done") -> Job:
    """A phone `kit`'s apply (origin `kit`, a `kit_id` handsd minted), approved by
    the human, ended with `verdict`."""
    job = spool.create_job(
        role="builder", context="clear", prompt="Apply the kit.", origin="kit",
        kit_id=new_kit_id(),
    )
    spool.transition(job, "running")
    return spool.transition(job, state, verdict=verdict, result=verdict)


def titles(recorder: Recorder) -> list[str]:
    return [title for title, _ in recorder.notified if title != "hands: at rest"]


def root_engine(tmp_home: Path, workdir: Path) -> tuple[PlaybookEngine, Recorder]:
    """This repository's own phone-mode PLAYBOOK.toml, with a driver to consult."""
    body = ROOT_PLAYBOOK.read_text(encoding="utf-8")
    return engine_for(tmp_home, workdir, body, driver=workdir.parent / "d")


# ------------------------------------------------ an unpaused pipeline: a stop


@pytest.mark.parametrize(
    ("verdict", "said"),
    [(FAILED, FAILED), (None, "no VERDICT: line")],
)
def test_under_the_repositorys_playbook_an_apply_that_did_not_land_stops(
    tmp_home: Path, workdir: Path, verdict: str | None, said: str
) -> None:
    """§45 (H-080): the catch-all `^VERDICT:` would consult the driver about a
    "question" that is not one; the engine stops first, with §45's reason, titled
    as every engine stop is, and consults no driver."""
    engine, recorder = root_engine(tmp_home, workdir)
    job = phone_apply(engine.spool, verdict)
    run(engine.on_job(job))
    assert recorder.enqueued == [] and recorder.sent == [], "a driver was consulted"
    assert engine.state.paused and engine.state.paused_by == "stop"
    assert engine.state.stop_reason == reason(said)
    assert titles(recorder) == [STOPPED]
    assert recorder.notified[0][1]["reason"] == reason(said)
    assert [e for e in engine.spool.events() if e.kind == "playbook.rule"] == []


def test_the_verdict_line_is_cut_to_200_characters(tmp_home: Path, workdir: Path) -> None:
    engine, _ = root_engine(tmp_home, workdir)
    verdict = "VERDICT: kit not applied pr=none " + "x" * 400
    run(engine.on_job(phone_apply(engine.spool, verdict)))
    stop = engine.state.stop_reason or ""
    shown = stop.removeprefix("the kit's apply did not land: ").removesuffix(" (§45)")
    assert len(shown) == 200 and shown.endswith("…") and verdict.startswith(shown[:-1])


def test_under_an_autonomous_role_mode_playbook_an_apply_that_did_not_land_sends_no_kickoff(
    tmp_home: Path, workdir: Path
) -> None:
    """§45 with §31: an engine-approved apply whose end is not `kit applied` stops;
    the engine's kickoff is not sent."""
    engine, recorder = engine_for(tmp_home, workdir, AUTONOMOUS, architect=workdir)
    job = applied_kit(engine.spool, verdict=FAILED)
    run(engine.on_job(job))
    assert recorder.sent == [] and recorder.enqueued == []
    assert engine.state.stop_reason == reason(FAILED)
    assert titles(recorder) == [STOPPED]


def test_a_resumed_applys_failed_end_stops_the_same_way(tmp_home: Path, workdir: Path) -> None:
    """§43's chain walk: the resume carries no `kit_id`; `resumed_from` leads back to
    the apply, so its end is an apply's end."""
    engine, recorder = engine_for(tmp_home, workdir, AUTONOMOUS, architect=workdir)
    spool = engine.spool
    apply = filed_kit(spool)
    assert apply.gate is not None
    gate = decide(apply.gate, decision="approved", decided_by="playbook", reason="r")
    spool.transition(apply, "queued", gate=gate)
    spool.transition(spool.load_job(apply.id), "running")
    spool.transition(spool.load_job(apply.id), "orphaned")
    resumed = spool.create_job(
        role="builder", context="clear", prompt="Apply the kit.", origin="playbook",
        resumed_from=apply.id,
    )
    spool.transition(resumed, "running")
    ended = spool.transition(spool.load_job(resumed.id), "done", verdict=FAILED, result=FAILED)
    assert ended.kit_id is None
    run(engine.on_job(ended))
    assert recorder.sent == [] and recorder.enqueued == []
    assert engine.state.stop_reason == reason(FAILED)


# ------------------------------------------------------- decided as today


def test_a_landed_phone_apply_meets_the_playbooks_kit_applied_rule(
    tmp_home: Path, workdir: Path
) -> None:
    engine, recorder = root_engine(tmp_home, workdir)
    run(engine.on_job(phone_apply(engine.spool, "VERDICT: kit applied abc1234")))
    assert not engine.state.paused, engine.state.stop_reason
    assert recorder.enqueued == [] and recorder.sent == []
    assert len(titles(recorder)) == 1 and "Kit applied" in strip_paths(titles(recorder)[0])


def test_a_landed_engine_approved_apply_is_followed_by_the_engines_kickoff(
    tmp_home: Path, workdir: Path
) -> None:
    engine, recorder = engine_for(tmp_home, workdir, AUTONOMOUS, architect=workdir)
    run(engine.on_job(applied_kit(engine.spool)))
    assert [sent["prompt"] for sent in recorder.sent] == [KICKOFF]
    assert not engine.state.paused, engine.state.stop_reason


def test_a_send_replying_kit_not_applied_meets_the_playbooks_rules_only(
    tmp_home: Path, workdir: Path
) -> None:
    """A `hands send` is not an apply: no `kit_id`, no chain back to one. This
    repository's catch-all consults the driver, as it does today."""
    engine, recorder = root_engine(tmp_home, workdir)
    run(engine.on_job(finished(engine.spool, verdict="VERDICT: kit not applied")))
    assert [fields["role"] for fields in recorder.enqueued] == ["driver"]
    assert not engine.state.paused, engine.state.stop_reason


# ------------------------------------------- a paused pipeline: one publication


def test_under_a_human_pause_an_apply_that_did_not_land_is_published_once_and_never_kept(
    tmp_home: Path, workdir: Path
) -> None:
    """§45 with §44 rule 2: published once as a stop under a human pause; the pause,
    its reason and the kept builder end (the mission's) stay as they were."""
    engine, recorder = held_engine(tmp_home, workdir)
    run(engine.pause())
    mission = finished(engine.spool, verdict=FINISHED, origin="playbook")
    run(engine.on_job(mission))
    assert kept_jobs(engine) == [mission.id]
    kept_before = engine.pipeline()["kept"]
    before = list(recorder.notified)
    apply = phone_apply(engine.spool, FAILED)
    run(engine.on_job(apply))
    published = [entry for entry in recorder.notified[len(before):]
                 if entry[0] != "hands: at rest"]
    assert [title for title, _ in published] == [SUPPRESSED_HUMAN_TITLE]
    assert published[0][1]["reason"] == reason(FAILED)
    assert paused_by_human(engine)
    assert engine.state.stop_reason == PAUSE_REASON
    assert engine.pipeline()["kept"] == kept_before, "the apply's end was kept"
    assert recorder.sent == [] and recorder.enqueued == []


def test_over_a_pipeline_stopped_by_a_rule_an_apply_that_did_not_land_is_published_once(
    tmp_home: Path, workdir: Path
) -> None:
    """§45: "under any other pause titled as a stop"; the stop's reason stays."""
    engine, recorder = root_engine(tmp_home, workdir)
    run(engine.on_job(finished(engine.spool, verdict="VERDICT: mission 12 blocked U3")))
    first = engine.state.stop_reason
    assert engine.state.paused and first is not None and "blocked" in strip_paths(first)
    before = len(recorder.notified)
    run(engine.on_job(phone_apply(engine.spool, FAILED)))
    published = recorder.notified[before:]
    assert [title for title, _ in published] == [STOPPED]
    assert published[0][1]["reason"] == reason(FAILED)
    assert engine.state.stop_reason == first
    assert recorder.enqueued == [] and recorder.sent == []


def test_the_engines_stop_reason_has_a_row_in_the_operator_table() -> None:
    """§19: the row for the apply that did not land — the project's chat's, route 3."""
    from test_operator_table import SECTION_19, flat, handbook_section, table_rows

    rows = table_rows(handbook_section(SECTION_19))[1:]
    [row] = [row for row in rows if "the kit's apply did not land" in row[0]]
    assert row[0].startswith(f"`{STOPPED}`"), row
    assert row[1] == "the project's chat — route 3", row
    said = flat(" ".join(row[2:]))
    for words in ("checks", "re-run", "merged", "`go <secret>`", "closed"):
        assert words in strip_paths(said), (words, row)


# §45's CI hold (`carries_ci`, `ci_hold_reason`, `WARN ci:`) is contained in
# §46's plan-files rule since mission 30: tests/test_plan_files.py.


# ----------------------------------------------- the journal sentence (§45)


def design_journal_sentence() -> str:
    """§45's `pull-request` sentence: the indented block, lines joined by single
    spaces (it is one line in the prompt)."""
    lines = DESIGN.read_text(encoding="utf-8").splitlines()
    start = lines.index(
        "    [hands: meta/journal.md is uncommitted in your working tree (`git"
    )
    block = []
    for text in lines[start:]:
        if not text.startswith("    "):
            break
        block.append(text.strip())
    return " ".join(block)


def journal_engine(tmp_home: Path, workdir: Path, main_setting: str | None) -> PlaybookEngine:
    commit_file(workdir, "README.md", "x\n")
    (workdir / "meta").mkdir(exist_ok=True)
    (workdir / "meta" / "journal.md").write_text("a line\n", encoding="utf-8")
    data: dict[str, Any] = {"roles": {"builder": {"cwd": str(workdir)},
                                      "aux": {"cwd": str(workdir)}}}
    if main_setting is not None:
        data["repository"] = {"main": main_setting}
    config = parse_config(data, project="p", path=tmp_home / ".hands" / "p.toml")
    recorder = Recorder()
    return PlaybookEngine(config, Spool(tmp_home / ".hands"), send=recorder.send,
                          enqueue=recorder.enqueue, notify=recorder.notify)


def test_the_pull_request_journal_sentence_is_section_45s_word_for_word(
    tmp_home: Path, workdir: Path
) -> None:
    expected = design_journal_sentence().replace("<consultation>", "consultation")
    assert JOURNAL_REMINDER_PULL_REQUEST.format(
        journal="meta/journal.md", consultation="consultation"
    ) == expected
    engine = journal_engine(tmp_home, workdir, "pull-request")
    assert engine.journal_reminder() == expected


@pytest.mark.parametrize("main_setting", [None, "direct"])
def test_the_direct_journal_sentence_is_unchanged(
    tmp_home: Path, workdir: Path, main_setting: str | None
) -> None:
    engine = journal_engine(tmp_home, workdir, main_setting)
    assert engine.journal_reminder() == (
        "[hands: meta/journal.md is uncommitted in your working tree (`git status "
        "--porcelain` shows it): commit it first, on its own, as `journal: consultation`, "
        "then do what follows.]"
    )
    assert engine.journal_reminder() == JOURNAL_REMINDER.format(
        journal="meta/journal.md", consultation="consultation"
    )


@pytest.mark.parametrize("template", ["direct", "pull-request"])
def test_section_36s_reader_strips_both_journal_sentences(template: str) -> None:
    sentence = (JOURNAL_REMINDER if template == "direct" else JOURNAL_REMINDER_PULL_REQUEST)
    line = sentence.format(journal="meta/journal.md", consultation="J-1")
    assert sent_prompt(f"{line}\n\nthe sender's words") == "the sender's words"
    owner = (
        "[hands: an owner file was committed after the last update of meta/CHECKPOINT.md: "
        "meta/decisions/x.md. Carry out the \"For the builder\" steps of each, oldest first, "
        "record them in the checkpoint and commit it, then do what follows.]"
    )
    assert sent_prompt(f"{owner}\n\n{line}\n\nwords") == "words"

