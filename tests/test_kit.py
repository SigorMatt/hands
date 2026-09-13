"""`hands kit check` (DESIGN §4 `kit check` row, §26 "the architect's tooling").

A kit is checked in the client, without a daemon, a socket or the network: its
paths, the playbook in force, the brief's kickoff line and final-reply vocabulary
against the playbook's `verdict` regexes, the brief's wording, and the protocol
files the playbook's sends name. One passing kit (dir and zip), one failing kit
per check, the mission 10 kit as it was committed at 61e1486, and the shipped
templates filled in.
"""

from __future__ import annotations

import io
import json
import re
import subprocess
import zipfile
from pathlib import Path

import pytest

from conftest import strip_paths
from hands.cli import main

ROOT = Path(__file__).parents[1]
MISSION_10_KIT = ROOT / "tests" / "fixtures" / "kit-mission-10"
TEMPLATES = ROOT / "templates"
CHECK_NAMES = ("paths", "playbook", "brief", "verdicts", "wording", "protocol")

BRIEF = """\
# BUILDER-11-PROMPT — demo mission 11: a test mission

Kickoff line (the only way this mission is started or resumed):

    Read meta/BUILDER-11-PROMPT.md and execute the mission below its divider.

---

## Execution model (binding)

- Every unit ends with a commit and a push.
- Your final reply begins with exactly one of: `VERDICT: mission 11
  finished` | `VERDICT: mission 11 blocked <unit>` | `VERDICT: question
  <one line>`.
- `./scripts/check` three times before every commit.
"""

PLAYBOOK = """\
version = 1

[series]
name = "demo-missions"
kickoff = "Read meta/BUILDER-11-PROMPT.md and execute the mission below its divider."

[limits]
max_resumes = 2

[[rule]]
on = "builder.done"
verdict = '^VERDICT: mission (?P<n>\\d+) finished'
then = "send"
role = "aux"
context = "clear"
prompt = "Read meta/REVIEW-PROTOCOL.md, review mission {n}, commit meta/reviews/REVIEW-{n}.md."

[[rule]]
on = "builder.done"
verdict = '^VERDICT: kit applied'
then = "notify"
message = "Kit applied"

[[rule]]
on = "builder.done"
verdict = '^VERDICT: mission (?P<n>\\d+) blocked'
then = "stop"
message = "Mission {n} blocked"

[[rule]]
on = "builder.done"
verdict = '^VERDICT: question'
then = "stop"
message = "The builder has a question"

[[rule]]
on = "builder.done"
then = "stop"
message = "Builder finished without a recognised verdict"

[[rule]]
on = "aux.done"
verdict = '^VERDICT: review mission (?P<n>\\d+) blockers=0'
then = "stop"
message = "Mission {n} reviewed clean"
"""

PROTOCOL = "# REVIEW-PROTOCOL\n\nYour reply's first line is exactly:\n\n    VERDICT: review\n"


def run_check(kit: Path, repo: Path | None, *extra: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    argv = ["kit", "check", str(kit), *(["--repo", str(repo)] if repo else []), *extra]
    code = main(argv, stdout=out, stderr=err)
    return code, out.getvalue(), err.getvalue()


def line(out: str, name: str) -> str:
    found = [text for text in out.splitlines() if re.match(rf"^(PASS|FAIL) {name}: ", text)]
    assert len(found) == 1, (name, out)
    return found[0]


def write_tree(root: Path, files: dict[str, str]) -> Path:
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


def good_kit() -> dict[str, str]:
    return {"meta/BUILDER-11-PROMPT.md": BRIEF, "PLAYBOOK.toml": PLAYBOOK}


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A repository the kit lands in: it already has a playbook and the protocol."""
    return write_tree(
        tmp_path / "repo", {"PLAYBOOK.toml": PLAYBOOK, "meta/REVIEW-PROTOCOL.md": PROTOCOL}
    )


def assert_failed_only(code: int, out: str, name: str) -> str:
    assert code == 1, out
    for other in CHECK_NAMES:
        if other != name:
            assert line(out, other).startswith("PASS"), (other, out)
    failed = line(out, name)
    assert failed.startswith("FAIL"), out
    assert "Apply ~/Downloads/" not in strip_paths(out), "a failing kit gets no apply prompt"
    return failed


# ---------------------------------------------------------------- the surface


def test_hands_help_lists_kit(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    assert re.search(r"^\s+kit\s", capsys.readouterr().out, re.MULTILINE)


# ---------------------------------------------------------------- passing kits


def test_a_passing_dir_kit_prints_six_passes_and_the_apply_prompt(
    tmp_path: Path, repo: Path
) -> None:
    kit = write_tree(tmp_path / "mission-11-kit", good_kit())
    code, out, err = run_check(kit, repo)
    assert code == 0, out + err
    for name in CHECK_NAMES:
        assert line(out, name).startswith("PASS"), out
    flat = " ".join(strip_paths(out).split())
    assert (
        "Apply ~/Downloads/mission-11-kit.zip to this repository: unzip -o into the repo "
        "root (it replaces PLAYBOOK.toml and adds meta/BUILDER-11-PROMPT.md)"
    ) in strip_paths(flat), out
    assert "'plan: mission 11 kit'" in strip_paths(flat), out
    assert "Reply with one line: VERDICT: kit applied <sha>." in strip_paths(flat), out
    # The kit carries a playbook, so it is the one in force and its kickoff is compared.
    assert "the kit's PLAYBOOK.toml" in strip_paths(line(out, "playbook"))
    # §26's regex ↔ literal check covers builder.done; the aux rule is said, not hidden.
    verdicts = line(out, "verdicts")
    assert "VERDICT: kit applied <sha>" in strip_paths(verdicts)
    assert "not matched against the brief" in strip_paths(verdicts)


def test_a_passing_zip_kit(tmp_path: Path, repo: Path) -> None:
    kit = tmp_path / "kit-11.zip"
    with zipfile.ZipFile(kit, "w") as archive:
        archive.writestr("meta/", "")  # a directory entry is not a file
        for name, text in good_kit().items():
            archive.writestr(name, text)
    code, out, err = run_check(kit, repo)
    assert code == 0, out + err
    assert "Apply ~/Downloads/kit-11.zip to this repository" in strip_paths(out)
    assert "2 files," in strip_paths(line(out, "paths"))


def test_json_carries_every_check_and_the_apply_prompt(tmp_path: Path, repo: Path) -> None:
    kit = write_tree(tmp_path / "k", good_kit())
    code, out, _ = run_check(kit, repo, "--json")
    assert code == 0
    answer = json.loads(out)
    assert [check["name"] for check in answer["checks"]] == list(CHECK_NAMES)
    assert answer["ok"] is True
    assert answer["replaces"] == ["PLAYBOOK.toml"]
    assert answer["adds"] == ["meta/BUILDER-11-PROMPT.md"]
    assert answer["commit_message"] == "plan: mission 11 kit"
    assert "VERDICT: kit applied <sha>" in strip_paths(answer["apply_prompt"])


def test_repo_defaults_to_the_top_level_of_the_current_git_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    top = write_tree(tmp_path / "top", {"meta/REVIEW-PROTOCOL.md": PROTOCOL, "PLAYBOOK.toml": ""})
    subprocess.run(["git", "init", "-q", str(top)], check=True)
    kit = write_tree(tmp_path / "k", good_kit())
    monkeypatch.chdir(top / "meta")
    code, out, err = run_check(kit, None, "--json")
    assert code == 0, out + err
    assert json.loads(out)["replaces"] == ["PLAYBOOK.toml"]


def test_outside_a_git_repository_without_repo_is_an_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    kit = write_tree(tmp_path / "k", good_kit())
    outside = tmp_path / "nowhere"
    outside.mkdir()
    monkeypatch.chdir(outside)
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    code, out, err = run_check(kit, None)
    assert code == 1 and "--repo" in strip_paths(err), (out, err)


def test_a_kit_that_does_not_exist_is_an_error(tmp_path: Path, repo: Path) -> None:
    code, _, err = run_check(tmp_path / "missing.zip", repo)
    assert code == 1 and "missing.zip" in strip_paths(err)


# ------------------------------------------------------------- a. paths


@pytest.mark.parametrize(
    "name",
    ["../escape.md", "/etc/passwd", "meta/../../x.md", "a\\b.md", "C:/x.md", ".git/config"],
)
def test_a_zip_entry_that_is_not_a_repository_path_fails(
    tmp_path: Path, repo: Path, name: str
) -> None:
    kit = tmp_path / "bad.zip"
    with zipfile.ZipFile(kit, "w") as archive:
        for good, text in good_kit().items():
            archive.writestr(good, text)
        archive.writestr(name, "x")
    code, out, _ = run_check(kit, repo)
    assert name in strip_paths(assert_failed_only(code, out, "paths"))


def test_a_zip_symlink_entry_fails(tmp_path: Path, repo: Path) -> None:
    kit = tmp_path / "link.zip"
    with zipfile.ZipFile(kit, "w") as archive:
        for good, text in good_kit().items():
            archive.writestr(good, text)
        info = zipfile.ZipInfo("docs/link.md")
        info.external_attr = 0o120777 << 16
        archive.writestr(info, "/etc/passwd")
    code, out, _ = run_check(kit, repo)
    assert "docs/link.md" in strip_paths(assert_failed_only(code, out, "paths"))


def test_a_dir_kit_symlink_fails(tmp_path: Path, repo: Path) -> None:
    kit = write_tree(tmp_path / "k", good_kit())
    (kit / "docs").mkdir()
    (kit / "docs" / "link.md").symlink_to(tmp_path / "elsewhere.md")
    code, out, _ = run_check(kit, repo)
    assert "docs/link.md" in strip_paths(assert_failed_only(code, out, "paths"))


def test_an_entry_that_lands_outside_the_repo_through_a_repo_symlink_fails(
    tmp_path: Path, repo: Path
) -> None:
    (tmp_path / "outside").mkdir()
    (repo / "docs").symlink_to(tmp_path / "outside")
    kit = write_tree(tmp_path / "k", {**good_kit(), "docs/NOTE.md": "x"})
    code, out, _ = run_check(kit, repo)
    assert "docs/NOTE.md" in strip_paths(assert_failed_only(code, out, "paths"))


# ------------------------------------------------------------- b. playbook


def test_a_kit_playbook_with_quiet_hours_fails(tmp_path: Path, repo: Path) -> None:
    book = PLAYBOOK.replace("max_resumes = 2", 'max_resumes = 2\nquiet_hours = "22-07"')
    kit = write_tree(tmp_path / "k", {**good_kit(), "PLAYBOOK.toml": book})
    code, out, _ = run_check(kit, repo)
    # A playbook that does not load leaves none in force, so verdicts and
    # protocol fail with it ("see playbook"); the reason is the playbook line's.
    assert code == 1
    assert "quiet_hours" in strip_paths(line(out, "playbook"))
    assert line(out, "playbook").startswith("FAIL")


def test_a_kit_playbook_that_does_not_load_fails(tmp_path: Path, repo: Path) -> None:
    """H-019's form: `series = "…"` beside `[series]` is not TOML."""
    book = PLAYBOOK.replace("version = 1\n", 'version = 1\nseries = "demo"\n')
    kit = write_tree(tmp_path / "k", {**good_kit(), "PLAYBOOK.toml": book})
    code, out, _ = run_check(kit, repo)
    assert code == 1
    assert "not valid TOML" in strip_paths(line(out, "playbook"))
    assert line(out, "playbook").startswith("FAIL")


def test_a_kit_playbook_whose_kickoff_differs_from_the_brief_fails(
    tmp_path: Path, repo: Path
) -> None:
    book = PLAYBOOK.replace("BUILDER-11-PROMPT.md and", "BUILDER-12-PROMPT.md and")
    kit = write_tree(tmp_path / "k", {**good_kit(), "PLAYBOOK.toml": book})
    code, out, _ = run_check(kit, repo)
    assert "BUILDER-12" in strip_paths(assert_failed_only(code, out, "playbook"))


def test_a_kit_playbook_without_a_kickoff_fails(tmp_path: Path, repo: Path) -> None:
    book = re.sub(r"kickoff = .*\n", "", PLAYBOOK)
    kit = write_tree(tmp_path / "k", {**good_kit(), "PLAYBOOK.toml": book})
    code, out, _ = run_check(kit, repo)
    assert "[series] kickoff" in strip_paths(assert_failed_only(code, out, "playbook"))


def test_a_kit_without_a_playbook_is_checked_against_the_repos(
    tmp_path: Path, repo: Path
) -> None:
    kit = write_tree(tmp_path / "k", {"meta/BUILDER-11-PROMPT.md": BRIEF})
    code, out, _ = run_check(kit, repo)
    assert code == 0, out
    assert "the repo's PLAYBOOK.toml is in force" in strip_paths(line(out, "playbook"))


def test_no_playbook_in_the_kit_or_the_repo_fails(tmp_path: Path) -> None:
    kit = write_tree(tmp_path / "k", {"meta/BUILDER-11-PROMPT.md": BRIEF})
    bare = write_tree(tmp_path / "bare", {"README.md": "x"})
    code, out, _ = run_check(kit, bare)
    assert code == 1
    assert line(out, "playbook").startswith("FAIL")


# ---------------------------------------------------------- c. brief, verdicts


def test_a_rule_whose_verdict_matches_no_literal_fails(tmp_path: Path, repo: Path) -> None:
    book = PLAYBOOK.replace("(?P<n>\\d+) blocked'", "(?P<n>\\d+) abandoned'")
    kit = write_tree(tmp_path / "k", {**good_kit(), "PLAYBOOK.toml": book})
    code, out, _ = run_check(kit, repo)
    failed = assert_failed_only(code, out, "verdicts")
    assert "abandoned" in strip_paths(failed)
    assert "VERDICT: mission 11 blocked <unit>" in strip_paths(failed)


def test_a_brief_literal_that_matches_no_rule_fails(tmp_path: Path, repo: Path) -> None:
    brief = BRIEF.replace("<one line>`.", "<one line>` | `VERDICT: gone`.")
    kit = write_tree(tmp_path / "k", {**good_kit(), "meta/BUILDER-11-PROMPT.md": brief})
    code, out, _ = run_check(kit, repo)
    assert "VERDICT: gone" in strip_paths(assert_failed_only(code, out, "verdicts"))


def test_a_rule_that_matches_only_a_literal_nobody_prints_fails_even_beside_kit_applied(
    tmp_path: Path, repo: Path
) -> None:
    """The apply prompt's literal is the only one seen outside the brief: a rule
    for some other unwritten reply is not excused by it."""
    book = PLAYBOOK.replace("'^VERDICT: kit applied'", "'^VERDICT: kit rejected'")
    kit = write_tree(tmp_path / "k", {**good_kit(), "PLAYBOOK.toml": book})
    code, out, _ = run_check(kit, repo)
    assert "kit rejected" in strip_paths(assert_failed_only(code, out, "verdicts"))


def test_a_brief_without_a_kickoff_line_fails(tmp_path: Path, repo: Path) -> None:
    brief = BRIEF.replace("Kickoff line (the only", "Start (the only")
    kit = write_tree(tmp_path / "k", {**good_kit(), "meta/BUILDER-11-PROMPT.md": brief})
    code, out, _ = run_check(kit, repo)
    assert code == 1
    assert "kickoff" in strip_paths(line(out, "brief"))
    assert line(out, "brief").startswith("FAIL")


def test_a_brief_without_a_final_reply_vocabulary_fails(tmp_path: Path, repo: Path) -> None:
    brief = BRIEF.replace("Your final reply begins with exactly one of:", "Finish with")
    kit = write_tree(tmp_path / "k", {**good_kit(), "meta/BUILDER-11-PROMPT.md": brief})
    code, out, _ = run_check(kit, repo)
    assert code == 1
    assert line(out, "brief").startswith("FAIL")


def test_a_kit_without_a_brief_fails(tmp_path: Path, repo: Path) -> None:
    kit = write_tree(tmp_path / "k", {"PLAYBOOK.toml": PLAYBOOK})
    code, out, _ = run_check(kit, repo)
    assert code == 1
    assert line(out, "brief").startswith("FAIL")


def test_the_runs_form_reads_workplan_and_reply_with_one_of(tmp_path: Path, repo: Path) -> None:
    workplan = (
        "# WORKPLAN\n\nKickoff line:\n\n    Execute WORKPLAN.md run 1\n\n"
        "Reply with one of: `VERDICT: run 1 finished` | `VERDICT: run 1 blocked\n"
        "<reason>` | `VERDICT: question <one line>`\n"
    )
    book = (
        PLAYBOOK.replace("mission (?P<n>", "run (?P<n>")
        .replace("Read meta/BUILDER-11-PROMPT.md and execute the mission below its divider.",
                 "Execute WORKPLAN.md run 1")
    )  # fmt: skip
    kit = write_tree(tmp_path / "k", {"WORKPLAN.md": workplan, "PLAYBOOK.toml": book})
    code, out, err = run_check(kit, repo)
    assert code == 0, out + err


# ------------------------------------------------------------- d. wording


@pytest.mark.parametrize(
    ("extra", "said"),
    [
        ("\nThe sub-agent brief is as before.\n", "as before"),
        ("\n## Budget guidance\n\nSpend little.\n", "Budget guidance"),
    ],
)
def test_a_brief_that_says_as_before_or_gives_budget_guidance_fails(
    tmp_path: Path, repo: Path, extra: str, said: str
) -> None:
    kit = write_tree(tmp_path / "k", {**good_kit(), "meta/BUILDER-11-PROMPT.md": BRIEF + extra})
    code, out, _ = run_check(kit, repo)
    assert said in strip_paths(assert_failed_only(code, out, "wording"))


# ------------------------------------------------------------- e. protocol


def test_a_protocol_file_named_by_a_send_that_is_nowhere_fails(tmp_path: Path) -> None:
    bare = write_tree(tmp_path / "bare", {"PLAYBOOK.toml": PLAYBOOK})
    kit = write_tree(tmp_path / "k", good_kit())
    code, out, _ = run_check(kit, bare)
    failed = assert_failed_only(code, out, "protocol")
    assert "meta/REVIEW-PROTOCOL.md" in strip_paths(failed)
    assert "REVIEW-{n}" not in strip_paths(failed)


def test_a_protocol_file_carried_by_the_kit_passes(tmp_path: Path) -> None:
    bare = write_tree(tmp_path / "bare", {"README.md": "x"})
    kit = write_tree(tmp_path / "k", {**good_kit(), "meta/REVIEW-PROTOCOL.md": PROTOCOL})
    code, out, _ = run_check(kit, bare)
    assert code == 0, out
    assert "meta/REVIEW-PROTOCOL.md" in strip_paths(line(out, "protocol"))


# ----------------------------------------------- the mission 10 kit (61e1486)


def test_the_mission_10_kit_passes_against_this_repository() -> None:
    """The ten files of the kit commit 61e1486, committed byte for byte under
    tests/fixtures/kit-mission-10 (from `git archive 61e1486 <paths>`), checked
    against this repository: the kit has no playbook, so the repo's is in force."""
    names = sorted(
        path.relative_to(MISSION_10_KIT).as_posix()
        for path in MISSION_10_KIT.rglob("*")
        if path.is_file()
    )
    assert len(names) == 10, names
    code, out, err = run_check(MISSION_10_KIT, ROOT)
    assert code == 0, out + err
    assert "the repo's PLAYBOOK.toml is in force" in strip_paths(line(out, "playbook"))


# ----------------------------------------------------------- the templates


def filled(text: str) -> str:
    """A template with its placeholders filled: N=11, <project>=hands."""
    text = text.replace("<N-1>", "10").replace("<project>", "hands").replace("<series>", "audit")
    return re.sub(r"\bN\b", "11", text)


def template(name: str) -> str:
    return filled((TEMPLATES / name).read_text(encoding="utf-8"))


def test_the_filled_missions_templates_pass(tmp_path: Path) -> None:
    kit = write_tree(
        tmp_path / "k",
        {
            "meta/BUILDER-11-PROMPT.md": template("BUILDER-N-PROMPT.md"),
            "PLAYBOOK.toml": template("PLAYBOOK-missions.toml"),
            "meta/REVIEW-PROTOCOL.md": template("REVIEW-PROTOCOL.md"),
        },
    )
    code, out, err = run_check(kit, write_tree(tmp_path / "repo", {"README.md": "x"}))
    assert code == 0, out + err


def test_the_filled_runs_playbook_passes_with_a_workplan(tmp_path: Path) -> None:
    """There is no WORKPLAN template, so the brief here is a stub carrying only
    the two things kit check reads from it."""
    workplan = (
        "# WORKPLAN — hands audit\n\nKickoff line:\n\n    Execute WORKPLAN.md run 1\n\n"
        "Reply with one of: `VERDICT: run 1 finished` | `VERDICT: run 1 blocked <reason>`"
        " | `VERDICT: question <one line>`\n"
    )
    kit = write_tree(
        tmp_path / "k",
        {"WORKPLAN.md": workplan, "PLAYBOOK.toml": template("PLAYBOOK-runs.toml")},
    )
    code, out, err = run_check(kit, write_tree(tmp_path / "repo", {"README.md": "x"}))
    assert code == 0, out + err


def test_the_handbook_section_11_names_every_check_and_the_apply_literal() -> None:
    handbook = (ROOT / "docs" / "ARCHITECT-HANDBOOK.md").read_text(encoding="utf-8")
    section = handbook.split("## 11. `hands kit check`")[1].split("\n## 12.")[0]
    for name in CHECK_NAMES:
        assert f"`{name}`" in section, name
    assert "VERDICT: kit applied <sha>" in strip_paths(" ".join(section.split()))
    assert "PLAYBOOK.toml" in strip_paths(section)
    assert "meta/BUILDER-<N>-PROMPT.md" in strip_paths(section)
