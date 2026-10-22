"""Mission 30 U2: the engine approves plan files only (DESIGN §46 "H-083"; §31,
§32, §43, §45).

Under a role-mode autonomous playbook the engine approves a role-filed kit's apply
only when every file entry is a plan file — `KIT.md`, `DESIGN.md`, `WORKPLAN.md`,
a `decisions-<name>.md` at the root, or Markdown under `meta/` that no `send`
rule's prompt names, in exact case — and the kit carries no playbook. Any other
kit is held for the human with §46's reason (§43's when it carries the playbook),
and after the human's approval no engine kickoff follows. `hands kit check`
prints one `WARN owner:` line naming every such entry under `WARN playbook:`'s
condition.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from conftest import strip_paths
from hands.cli import main
from hands.gates import decide
from hands.playbook import PlaybookEngine, plan_hold_reason
from hands.spool import Job, is_plan_file, new_kit_id
from test_kit import AUTONOMOUS_PLAYBOOK, PLAYBOOK, PROTOCOL, good_kit, write_tree
from test_playbook import (
    ARCHITECT_BOOK,
    ARCHITECT_KICKOFF,
    Holds,
    Recorder,
    Sleeps,
    _filed_with,
    architect_engine,
    consultation,
    end_consultation,
    owner_reason,
    run,
)

#: A role-mode autonomous playbook whose review rule names meta/REVIEW-PROTOCOL.md
#: (and a placeholder path, which names no file), with the `kit applied` rule
#: every shipped playbook carries.
PLAN_BOOK = ARCHITECT_BOOK + """
[[rule]]
on = "builder.done"
verdict = '^VERDICT: mission (?P<n>\\d+) ready'
then = "send"
role = "aux"
context = "clear"
prompt = "Read meta/REVIEW-PROTOCOL.md, review mission {n}, commit meta/reviews/REVIEW-{n}.md."

[[rule]]
on = "builder.done"
verdict = '^VERDICT: kit applied'
then = "notify"
message = "Kit applied; the next kickoff is the driver's"
"""


def plan_reason(name: str, path: str) -> str:
    """§46's published reason, word for word."""
    return (
        f"apply {name}: the kit carries {path}, which is not a plan file; the engine "
        "approves plan files only (KIT.md, DESIGN.md, WORKPLAN.md, decisions files at "
        "the root, Markdown under meta/ that no send rule's prompt names), and any "
        "other file is the owner's (§46)"
    )


@pytest.fixture
def workdir(tmp_path: Path) -> Path:
    d = tmp_path / "work"
    d.mkdir(exist_ok=True)
    return d


def plan_engine(tmp_home: Path, workdir: Path) -> tuple[PlaybookEngine, Recorder, Holds]:
    engine, recorder = architect_engine(tmp_home, workdir, PLAN_BOOK)
    engine.sleep = Sleeps()
    holds = Holds()
    engine.hold = holds
    run(engine._load())
    assert engine.playbook is not None and engine.playbook.architect_is_autonomous
    return engine, recorder, holds


def file_and_end(engine: PlaybookEngine, entries: dict[str, str]) -> Job:
    architect = consultation(engine.spool)
    job = _filed_with(engine, architect, entries)
    architect = engine.spool.transition(
        architect, "done", verdict="VERDICT: next kit m16", result="VERDICT: next kit m16"
    )
    end_consultation(engine, architect)
    return job


def land(engine: PlaybookEngine, job: Job, decided_by: str) -> Job:
    """The held apply `job` approved by `decided_by` and run to `kit applied`."""
    held = engine.spool.load_job(job.id)
    assert held.gate is not None
    gate = decide(held.gate, decision="approved", decided_by=decided_by, reason="r",
                  quote="q" if decided_by == "driver" else None)
    engine.spool.transition(held, "queued", gate=gate)
    engine.spool.transition(held, "running")
    verdict = "VERDICT: kit applied abc1234"
    return engine.spool.transition(held, "done", verdict=verdict, result=verdict)


# ------------------------------------------------------------ the one test


@pytest.mark.parametrize(
    ("entry", "plan"),
    [
        ("KIT.md", True),
        ("DESIGN.md", True),
        ("WORKPLAN.md", True),
        ("decisions-2026-10-21.md", True),
        ("meta/BUILDER-31-PROMPT.md", True),
        ("meta/decisions/x-owner.md", True),
        ("meta/REVIEW-PROTOCOL.md", False),  # named below
        ("Design.md", False),
        ("Meta/x.md", False),
        ("kit.md", False),
        ("docs/decisions-x.md", False),
        ("decisions-.md", False),
        ("meta/conftest.py", False),
        ("meta/PLAYBOOK.toml", False),
        ("docs/x.md", False),
        ("SPEC.md", False),
        ("scripts/check", False),
    ],
)
def test_is_plan_file_is_section_46s_one_test(entry: str, plan: bool) -> None:
    assert is_plan_file(entry, {"meta/REVIEW-PROTOCOL.md"}) is plan


def test_the_reason_is_section_46s_word_for_word() -> None:
    assert plan_hold_reason("m16", "docs/x.md") == plan_reason("m16", "docs/x.md")


# ------------------------------------------------------------ the engine


@pytest.mark.parametrize(
    "entries",
    [
        {"KIT.md": "plan: m16\n", "DESIGN.md": "# D\n", "meta/BUILDER-31-PROMPT.md": "b\n",
         "meta/decisions/x-owner.md": "d\n"},
        {"WORKPLAN.md": "w\n", "decisions-2026-10-21.md": "d\n"},
    ],
    ids=["missions form", "runs form"],
)
def test_a_kit_of_plan_files_is_approved_and_followed_by_the_engines_kickoff(
    tmp_home: Path, workdir: Path, entries: dict[str, str]
) -> None:
    engine, recorder, holds = plan_engine(tmp_home, workdir)
    job = file_and_end(engine, entries)
    assert [entry["job"] for entry in recorder.approved] == [job.id]
    assert holds.published == []
    run(engine.on_job(land(engine, job, "playbook")))
    assert [sent["prompt"] for sent in recorder.sent] == [ARCHITECT_KICKOFF]


HELD = [
    "docs/x.md", ".github/workflows/x.yml", "scripts/check", "pyproject.toml", "uv.lock",
    "tests/conftest.py", "src/x.py", "SPEC.md", "meta/conftest.py",
    "meta/REVIEW-PROTOCOL.md", "Meta/x.md", "Design.md",
]


@pytest.mark.parametrize("entry", HELD)
def test_a_kit_carrying_another_file_is_held_with_section_46s_reason(
    tmp_home: Path, workdir: Path, entry: str
) -> None:
    engine, recorder, holds = plan_engine(tmp_home, workdir)
    job = file_and_end(engine, {"KIT.md": "plan: m16\n", "meta/BUILDER-31-PROMPT.md": "b\n",
                                entry: "x\n"})
    assert recorder.approved == [] and recorder.denied == []
    held = engine.spool.load_job(job.id)
    assert held.state == "held"
    assert held.gate is not None and held.gate["reason"] == "apply m16"
    assert holds.published == [(job.id, plan_reason("m16", entry))]
    assert engine.published_hold_reason(held) == plan_reason("m16", entry)
    assert not engine.state.paused, engine.state.stop_reason
    # the human approves: no engine kickoff, the playbook's `kit applied` rule fires
    run(engine.on_job(land(engine, job, "cli")))
    assert recorder.sent == [], "the engine sent a kickoff after a human's approval"
    assert "hands: Kit applied; the next kickoff is the driver's" in [
        title for title, _ in recorder.notified
    ]


def test_the_reason_names_the_first_such_entry_in_sorted_order(
    tmp_home: Path, workdir: Path
) -> None:
    engine, _, holds = plan_engine(tmp_home, workdir)
    job = file_and_end(engine, {"src/z.py": "z\n", "docs/a.md": "a\n", "KIT.md": "k\n"})
    assert holds.published == [(job.id, plan_reason("m16", "docs/a.md"))]


@pytest.mark.parametrize(
    ("entries", "path"),
    [
        ({"PLAYBOOK.toml": ARCHITECT_BOOK, "docs/x.md": "x\n"}, "PLAYBOOK.toml"),
        ({"meta/PLAYBOOK.toml": ARCHITECT_BOOK, "KIT.md": "k\n"}, "meta/PLAYBOOK.toml"),
    ],
)
def test_a_kit_carrying_the_playbook_is_held_with_section_43s_reason(
    tmp_home: Path, workdir: Path, entries: dict[str, str], path: str
) -> None:
    engine, recorder, holds = plan_engine(tmp_home, workdir)
    job = file_and_end(engine, entries)
    assert recorder.approved == []
    assert holds.published == [(job.id, owner_reason("m16", path))]
    assert engine.published_hold_reason(engine.spool.load_job(job.id)) == owner_reason(
        "m16", path
    )


def test_an_ordinary_phone_kit_is_unchanged(tmp_home: Path, workdir: Path) -> None:
    """A phone kit (origin `kit`) is the human's anyway: no reason of §46's."""
    engine, _, _ = plan_engine(tmp_home, workdir)
    job = engine.spool.create_job(
        role="builder", context="clear", prompt="Apply the kit.", origin="kit",
        kit_id=new_kit_id(), state="held",
    )
    assert engine.published_hold_reason(job) is None


# ------------------------------------------------------------ kit check


def _kit_config(tmp_home: Path, tmp_path: Path) -> None:
    (tmp_path / "hands-architect").mkdir(exist_ok=True)
    (tmp_home / ".hands" / "demo.toml").write_text(
        f'[roles.builder]\ncwd = "{tmp_path}"\n\n'
        f'[roles.architect]\ncwd = "{tmp_path / "hands-architect"}"\n',
        encoding="utf-8",
    )


def check(kit: Path, repo: Path, *extra: str) -> tuple[int, str]:
    out, err = io.StringIO(), io.StringIO()
    code = main(["kit", "check", str(kit), "--repo", str(repo), *extra], stdout=out, stderr=err)
    return code, out.getvalue()


def owner_warns(out: str) -> list[str]:
    return [text for text in out.splitlines() if text.startswith("WARN owner: ")]


OWNED = {"docs/x.md": "x\n", "src/x.py": "x\n", "meta/REVIEW-PROTOCOL.md": PROTOCOL,
         "Design.md": "d\n"}


def test_kit_check_warns_owner_naming_every_non_plan_entry_but_the_playbook(
    tmp_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("HANDS_PROJECT", raising=False)
    _kit_config(tmp_home, tmp_path)
    repo = write_tree(
        tmp_path / "repo",
        {"PLAYBOOK.toml": AUTONOMOUS_PLAYBOOK, "meta/REVIEW-PROTOCOL.md": PROTOCOL},
    )
    kit = write_tree(tmp_path / "k", {**good_kit(), "KIT.md": "plan: m11\n", **OWNED})
    code, out = check(kit, repo)
    assert code == 0, out
    [warn] = owner_warns(out)
    said = strip_paths(warn)
    assert (
        "the kit carries Design.md, docs/x.md, meta/REVIEW-PROTOCOL.md and src/x.py, "
        "which are not plan files" in strip_paths(said)
    ), said
    for plan in ("PLAYBOOK.toml", "BUILDER-11", "KIT.md"):
        assert plan not in strip_paths(said), said
    assert "the owner's (§46)" in strip_paths(said), said
    assert "WARN ci" not in strip_paths(out), out
    # the playbook keeps its own `WARN playbook:` line
    assert any(
        text.startswith("WARN playbook: ") and "§43" in strip_paths(text)
        for text in out.splitlines()
    ), out
    code, out = check(kit, repo, "--json")
    report = json.loads(out)
    assert report["owner_warnings"] == [warn.removeprefix("WARN owner: ")]
    assert sorted(key for key in report if key.endswith("_warnings")) == ["owner_warnings"]


def test_kit_check_prints_no_owner_line_for_a_phone_mode_repository(
    tmp_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("HANDS_PROJECT", raising=False)
    _kit_config(tmp_home, tmp_path)
    repo = write_tree(
        tmp_path / "repo", {"PLAYBOOK.toml": PLAYBOOK, "meta/REVIEW-PROTOCOL.md": PROTOCOL}
    )
    kit = write_tree(
        tmp_path / "k", {**good_kit(), ".github/workflows/x.yml": "x\n", **OWNED}
    )
    code, out = check(kit, repo)
    assert code == 0, out
    assert owner_warns(out) == []
    assert "WARN owner" not in strip_paths(out) and "WARN ci" not in strip_paths(out), out


# ------------------------------------------------------------ the operator table


def test_the_plan_hold_row_is_route_2_then_go() -> None:
    """§46: the hold of a kit that carries a file other than a plan file is the
    human's, and once the apply is approved no engine kickoff follows."""
    from test_operator_table import SECTION_19, handbook_section, table_rows

    rows = table_rows(handbook_section(SECTION_19))[1:]
    said = plan_reason("<name>", "<path>")
    [row] = [row for row in rows if said in strip_paths(row[0])]
    assert row[0].startswith("`hands: a job is held for a human`"), row
    assert row[1] == "the human alone — route 2", row
    assert "`go <secret>`" in strip_paths(row[2]), row
    assert "`hands go`" in strip_paths(row[3]), row
    assert "Approve" in strip_paths(row[2]), row
    assert "`hands approve <job>`" in strip_paths(row[3]), row
