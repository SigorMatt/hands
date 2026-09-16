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
import warnings
import zipfile
from pathlib import Path

import pytest

from conftest import strip_paths
from hands import kit as kit_mod
from hands.cli import main
from hands.playbook import parse_playbook

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

PROTOCOL = (
    "# REVIEW-PROTOCOL\n\nYour reply's first line is exactly:\n\n"
    "    VERDICT: review mission N blockers=<k> should-fix=<m>\n"
)


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
    # §27: no KIT.md in the kit, so the commit message is `plan: kit <name>`.
    assert "'plan: kit mission-11-kit'" in strip_paths(flat), out
    assert (
        "KIT.md: the first line of a KIT.md entry is the commit message when it is not "
        "empty, at most 72 characters, and has no quote character or line break; this kit "
        "carries no KIT.md, so the message is 'plan: kit mission-11-kit'"
    ) in strip_paths(flat), out
    assert "Reply with one line: VERDICT: kit applied <sha>." in strip_paths(flat), out
    # The kit carries a playbook, so it is the one in force and its kickoff is compared.
    assert "the kit's PLAYBOOK.toml" in strip_paths(line(out, "playbook"))
    # §27: builder.done rules against the brief, aux.done against the protocol.
    verdicts = line(out, "verdicts")
    assert "VERDICT: kit applied <sha>" in strip_paths(verdicts)
    assert (
        "1 aux.done verdict rule(s) match the review protocol's "
        "'VERDICT: review mission N blockers=<k> should-fix=<m>'"
    ) in strip_paths(verdicts)


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
    assert answer["commit_message"] == "plan: kit k"
    assert answer["kit_md"] is None
    assert "VERDICT: kit applied <sha>" in strip_paths(answer["apply_prompt"])


def test_the_commit_message_is_the_first_line_of_the_kits_kit_md(
    tmp_path: Path, repo: Path
) -> None:
    """§27: "the first line of a `KIT.md` inside the zip, else `plan: kit <name>`";
    kit check writes the shape and what this kit's KIT.md gives."""
    kit = write_tree(
        tmp_path / "mission-11-kit",
        {**good_kit(), "KIT.md": "  plan: mission 11 kit (DESIGN v3.10)  \n\nThe body.\n"},
    )
    code, out, err = run_check(kit, repo)
    assert code == 0, out + err
    flat = " ".join(strip_paths(out).split())
    assert "commit 'plan: mission 11 kit (DESIGN v3.10)' listing" in strip_paths(flat), out
    assert "commit message: plan: mission 11 kit (DESIGN v3.10)" in strip_paths(flat), out
    assert (
        "KIT.md: the first line of a KIT.md entry is the commit message when it is not "
        "empty, at most 72 characters, and has no quote character or line break; this kit's "
        "KIT.md gives 'plan: mission 11 kit (DESIGN v3.10)'"
    ) in strip_paths(flat), out
    assert "adds KIT.md and meta/BUILDER-11-PROMPT.md)" in strip_paths(flat), out
    code, out, _ = run_check(kit, repo, "--json")
    assert json.loads(out)["kit_md"] == "plan: mission 11 kit (DESIGN v3.10)"


@pytest.mark.parametrize(
    "text", ["", "\n\nplan: second line\n", "   \n"], ids=["empty", "blank-first", "blanks"]
)
def test_a_kit_md_with_a_blank_first_line_gives_the_default_message(
    tmp_path: Path, repo: Path, text: str
) -> None:
    kit = write_tree(tmp_path / "mission-11-kit", {**good_kit(), "KIT.md": text})
    code, out, _ = run_check(kit, repo, "--json")
    assert code == 0
    answer = json.loads(out)
    assert answer["commit_message"] == "plan: kit mission-11-kit"
    assert answer["kit_md"] is None


def test_plan_apply_computes_replaced_and_added_against_the_repo(tmp_path: Path) -> None:
    """The one function `kit check` and handsd both call (§27): a file that exists
    in the repo (a dangling symlink included) is replaced, any other is added."""
    repo = write_tree(tmp_path / "cwd", {"DESIGN.md": "x", "meta/plan.md": "x"})
    (repo / "gone.md").symlink_to(repo / "nowhere.md")
    plan = kit_mod.plan_apply(
        "~/Downloads/m-11.zip",
        ["meta/plan.md", "DESIGN.md", "gone.md", "meta/NEW.md", "KIT.md"],
        None,
        repo,
    )
    assert plan.name == "m-11"
    assert plan.replaces == ["DESIGN.md", "gone.md", "meta/plan.md"]
    assert plan.adds == ["KIT.md", "meta/NEW.md"]
    assert plan.commit_message == "plan: kit m-11" and plan.kit_md is None
    assert plan.prompt == (
        "Apply ~/Downloads/m-11.zip to this repository: unzip -o into the repo root "
        "(it replaces DESIGN.md, gone.md and meta/plan.md and adds KIT.md and meta/NEW.md), "
        "then one plan-only sub-agent makes a single commit 'plan: kit m-11' listing those "
        "files in its body, and pushes. Change nothing else. "
        "Reply with one line: VERDICT: kit applied <sha>."
    )
    with_md = kit_mod.plan_apply("/x/m-11.zip", ["KIT.md"], b"plan: mission 11\nmore\n", repo)
    assert with_md.commit_message == "plan: mission 11" == with_md.kit_md
    assert with_md.prompt.startswith("Apply /x/m-11.zip to this repository")


@pytest.mark.parametrize(
    "entries,said",
    [
        ([("../x.md", b"x")], "a .. component"),
        ([("/etc/x.md", b"x")], "an absolute path"),
        ([(".GIT/config", b"x")], "a path inside .git"),
        ([("docs/N.md", b"1"), ("docs/N.md", b"2")], "a duplicate entry"),
    ],
    ids=["dotdot", "absolute", "git", "duplicate"],
)
def test_apply_from_zip_refuses_by_kit_checks_path_rules_without_naming_entries(
    tmp_path: Path, repo: Path, entries: list[tuple[str, bytes]], said: str
) -> None:
    kit = zipped(tmp_path / "bad.zip", entries)
    with pytest.raises(kit_mod.KitError) as exc:
        kit_mod.apply_from_zip(kit, repo, "~/Downloads/bad.zip")
    assert said in strip_paths(str(exc.value))
    assert "not repository paths" in strip_paths(str(exc.value))
    for name, _ in entries:
        assert name not in strip_paths(str(exc.value))


def test_apply_from_zip_refuses_a_file_that_is_not_a_zip_and_an_empty_zip(
    tmp_path: Path, repo: Path
) -> None:
    junk = tmp_path / "junk.zip"
    junk.write_bytes(b"not a zip at all" * 8)
    with pytest.raises(kit_mod.KitError, match="not a readable zip"):
        kit_mod.apply_from_zip(junk, repo, "~/Downloads/junk.zip")
    empty = tmp_path / "empty.zip"
    zipfile.ZipFile(empty, "w").close()
    with pytest.raises(kit_mod.KitError, match="holds no files"):
        kit_mod.apply_from_zip(empty, repo, "~/Downloads/empty.zip")


def test_apply_from_zip_equals_kit_checks_prompt_for_the_same_zip(
    tmp_path: Path, repo: Path
) -> None:
    kit = zipped(tmp_path / "mission-11.zip", [("KIT.md", b"plan: mission 11 kit\n")])
    code, out, _ = run_check(kit, repo, "--json")
    assert code == 0, out
    plan = kit_mod.apply_from_zip(kit, repo, "~/Downloads/mission-11.zip")
    assert plan.prompt == json.loads(out)["apply_prompt"]
    assert plan.replaces == ["PLAYBOOK.toml"]
    assert plan.adds == ["KIT.md", "meta/BUILDER-11-PROMPT.md"]


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
    [
        "../escape.md", "/etc/passwd", "meta/../../x.md", "a\\b.md", "C:/x.md", ".git/config",
        ".GIT/config", "docs/.Git/hooks/post-checkout",
    ],
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


def zipped(kit: Path, extra: list[tuple[str, bytes]]) -> Path:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # zipfile warns on a duplicate name, and writes it
        with zipfile.ZipFile(kit, "w") as archive:
            for good, text in good_kit().items():
                archive.writestr(good, text)
            for name, data in extra:
                archive.writestr(name, data)
    return kit


def test_a_zip_with_a_duplicate_entry_name_fails(tmp_path: Path, repo: Path) -> None:
    """Review 10 should-fix 5: the second entry was silently collapsed into the first."""
    kit = zipped(tmp_path / "dup.zip", [("docs/NOTE.md", b"one"), ("docs/NOTE.md", b"two")])
    failed = assert_failed_only(*run_check(kit, repo)[:2], "paths")
    assert "docs/NOTE.md (a duplicate entry)" in strip_paths(failed)


def test_a_zip_entry_name_with_a_nul_fails(tmp_path: Path, repo: Path) -> None:
    """zipfile cuts a name at its first NUL (`docs/a`); the name as stored is checked."""
    kit = zipped(tmp_path / "nul.zip", [("docs/aXb.md", b"x")])
    kit.write_bytes(kit.read_bytes().replace(b"docs/aXb.md", b"docs/a\x00b.md"))
    failed = assert_failed_only(*run_check(kit, repo)[:2], "paths")
    assert "docs/a\\0b.md (a NUL in the name)" in strip_paths(failed)


@pytest.mark.parametrize("cap", ["entry", "total"])
def test_a_zip_over_the_size_cap_fails_before_its_bytes_are_read(
    tmp_path: Path, repo: Path, monkeypatch: pytest.MonkeyPatch, cap: str
) -> None:
    """The sizes are the zip directory's, read before any entry is decompressed."""
    kit = zipped(tmp_path / "big.zip", [("docs/BIG.md", b"x" * 5000)])
    if cap == "entry":
        monkeypatch.setattr(kit_mod, "MAX_ENTRY_BYTES", 4096)
        said = "docs/BIG.md (5000 bytes, over the 4096-byte cap on one entry)"
    else:
        monkeypatch.setattr(kit_mod, "MAX_TOTAL_BYTES", 4096)
        said = "over the 4096-byte cap on a kit's total"
    read: list[str] = []
    real = zipfile.ZipFile.read

    def reading(self: zipfile.ZipFile, name: object, pwd: bytes | None = None) -> bytes:
        read.append(getattr(name, "filename", str(name)))
        return real(self, name, pwd)  # type: ignore[arg-type]

    monkeypatch.setattr(zipfile.ZipFile, "read", reading)
    code, out, _ = run_check(kit, repo)
    assert code == 1
    assert line(out, "paths").startswith("FAIL") and said in strip_paths(line(out, "paths"))
    assert read.count("docs/BIG.md") == 0
    if cap == "total":
        assert read == []


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


def test_a_builder_rule_with_a_broken_branch_is_not_excused_by_the_apply_literal(
    tmp_path: Path, repo: Path
) -> None:
    """Review 10 should-fix 4's probe: the `misison` branch can never match the
    builder's reply; matching `VERDICT: kit applied <sha>` does not excuse it."""
    probe = "'^VERDICT: (kit applied|misison \\d+ finished)'"
    book = PLAYBOOK.replace("'^VERDICT: kit applied'", probe)
    kit = write_tree(tmp_path / "k", {**good_kit(), "PLAYBOOK.toml": book})
    code, out, _ = run_check(kit, repo)
    assert "misison" in strip_paths(assert_failed_only(code, out, "verdicts"))


def test_a_review_rule_that_matches_nothing_the_protocol_says_fails(
    tmp_path: Path, repo: Path
) -> None:
    """§27 (H-021): aux.done rules are checked against the protocol's VERDICT line."""
    book = PLAYBOOK.replace("blockers=0'", "blockers=none'")
    kit = write_tree(tmp_path / "k", {**good_kit(), "PLAYBOOK.toml": book})
    code, out, _ = run_check(kit, repo)
    failed = assert_failed_only(code, out, "verdicts")
    assert "blockers=none" in strip_paths(failed)
    assert "VERDICT: review mission N blockers=<k> should-fix=<m>" in strip_paths(failed)


def test_the_protocol_placeholders_are_read_as_counts(tmp_path: Path, repo: Path) -> None:
    """`N`, `<k>`, `<m>` stand for digits: `blockers=[1-9]` matches, `blockers=x` not."""
    extra = (
        "\n[[rule]]\non = \"aux.done\"\nverdict = '^VERDICT: review mission \\d+ "
        "blockers=[1-9]\\d* should-fix=\\d+$'\nthen = \"stop\"\nmessage = \"m\"\n"
    )
    kit = write_tree(tmp_path / "k", {**good_kit(), "PLAYBOOK.toml": PLAYBOOK + extra})
    code, out, err = run_check(kit, repo)
    assert code == 0, out + err
    bad = extra.replace("blockers=[1-9]", "blockers=x")
    kit = write_tree(tmp_path / "k2", {**good_kit(), "PLAYBOOK.toml": PLAYBOOK + bad})
    code, out, _ = run_check(kit, repo)
    assert "blockers=x" in strip_paths(assert_failed_only(code, out, "verdicts"))


def test_a_review_rule_with_no_protocol_verdict_line_fails(tmp_path: Path) -> None:
    bare = write_tree(
        tmp_path / "bare", {"meta/REVIEW-PROTOCOL.md": "# REVIEW-PROTOCOL\n\nNo line here.\n"}
    )
    kit = write_tree(tmp_path / "k", good_kit())
    code, out, _ = run_check(kit, bare)
    failed = assert_failed_only(code, out, "verdicts")
    assert "no review vocabulary" in strip_paths(failed)


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
        PLAYBOOK.replace("VERDICT: mission (?P<n>", "VERDICT: run (?P<n>")
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
    # With the protocol missing, the aux.done rule has no review line to match
    # either (§27), so verdicts fails beside protocol and points at it.
    assert code == 1
    for other in ("paths", "playbook", "brief", "wording"):
        assert line(out, other).startswith("PASS"), (other, out)
    failed = line(out, "protocol")
    assert failed.startswith("FAIL")
    assert "meta/REVIEW-PROTOCOL.md" in strip_paths(failed)
    assert "REVIEW-{n}" not in strip_paths(failed)
    assert line(out, "verdicts").startswith("FAIL")
    assert "(see protocol)" in strip_paths(line(out, "verdicts"))


@pytest.mark.parametrize("named", ["../X.md", "~/X.md", "/etc/X.md", "meta/../X.md"])
def test_a_send_path_the_check_cannot_resolve_fails(
    tmp_path: Path, repo: Path, named: str
) -> None:
    """Review 10 should-fix 5: such a path was skipped, so it passed unchecked."""
    book = PLAYBOOK.replace(
        "Read meta/REVIEW-PROTOCOL.md,", f"Read meta/REVIEW-PROTOCOL.md and {named},"
    )
    assert book != PLAYBOOK
    kit = write_tree(tmp_path / "k", {**good_kit(), "PLAYBOOK.toml": book})
    code, out, _ = run_check(kit, repo)
    failed = assert_failed_only(code, out, "protocol")
    assert named in strip_paths(failed) and "not a repository path" in strip_paths(failed)


def test_a_protocol_path_that_lands_outside_the_repo_fails(tmp_path: Path) -> None:
    outside = write_tree(tmp_path / "outside", {"REVIEW-PROTOCOL.md": PROTOCOL})
    bare = write_tree(tmp_path / "bare", {"README.md": "x"})
    (bare / "meta").symlink_to(outside)
    kit = write_tree(tmp_path / "k", good_kit())
    code, out, _ = run_check(kit, bare)
    assert code == 1
    assert line(out, "protocol").startswith("FAIL")
    assert "meta/REVIEW-PROTOCOL.md" in strip_paths(line(out, "protocol"))


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
        " | `VERDICT: awaiting decision <memo>` | `VERDICT: question <one line>`\n"
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


# ------------------------------------------------- §27: consult and the driver

def _consult_book(resolved: str = "'^VERDICT: resolved (?P<what>.+)'") -> str:
    """PLAYBOOK with §27's consult rule on a builder question and its follow-ups."""
    book = PLAYBOOK.replace(
        "[limits]\nmax_resumes = 2", "[limits]\nmax_resumes = 2\nmax_consults = 2"
    )
    book = book.replace(
        "verdict = '^VERDICT: question'\nthen = \"stop\"\nmessage = \"The builder has a question\"",
        "verdict = '^VERDICT: question'\nthen = \"consult\"",
    )
    return book + (
        "\n[[rule]]\non = \"driver.done\"\n"
        f"verdict = {resolved}\nthen = \"notify\"\nmessage = \"consult resolved: {{what}}\"\n"
        "\n[[rule]]\non = \"driver.done\"\n"
        "verdict = '^VERDICT: escalate (?P<reason>.+)'\nthen = \"stop\"\n"
        "message = \"driver escalated: {reason}\"\n"
        "\n[[rule]]\non = \"driver.failed\"\nthen = \"stop\"\n"
    )


def test_kit_check_accepts_consult_rules_and_the_drivers_vocabulary(
    tmp_path: Path, repo: Path
) -> None:
    """§27: `consult`, `driver.done` and `driver.failed` are playbook words, and a
    verdict rule on `driver.done` is checked against the driver's two VERDICT lines."""
    book = _consult_book()
    assert 'then = "consult"' in strip_paths(book)
    kit = write_tree(tmp_path / "k", {**good_kit(), "PLAYBOOK.toml": book})
    code, out, err = run_check(kit, repo)
    assert code == 0, out + err
    assert "driver.done" in strip_paths(line(out, "verdicts"))


def test_a_driver_rule_that_matches_neither_driver_verdict_fails(
    tmp_path: Path, repo: Path
) -> None:
    kit = write_tree(
        tmp_path / "k",
        {**good_kit(), "PLAYBOOK.toml": _consult_book("'^VERDICT: settled (?P<what>.+)'")},
    )
    code, out, _ = run_check(kit, repo)
    failed = assert_failed_only(code, out, "verdicts")
    assert "settled" in strip_paths(failed)
    assert "VERDICT: resolved <what was sent, and the section cited>" in strip_paths(failed)


# ------------------------------------ §28: named paths (review 11 should-fix 6)


def _send_naming(text: str) -> str:
    """PLAYBOOK whose aux send prompt also names `text`."""
    book = PLAYBOOK.replace(
        "Read meta/REVIEW-PROTOCOL.md,", f"Read meta/REVIEW-PROTOCOL.md and {text},"
    )
    assert book != PLAYBOOK
    return book


@pytest.mark.parametrize(
    "said,named",
    [
        ("meta/MISSING.txt", "meta/MISSING.txt"),
        ("(meta/MISSING.txt)", "meta/MISSING.txt"),
        ('\\"meta/MISSING.txt\\"', "meta/MISSING.txt"),
        ("'meta/MISSING.txt'", "meta/MISSING.txt"),
        ("`meta/MISSING.txt`", "meta/MISSING.txt"),
        ("<meta/MISSING.txt>", "meta/MISSING.txt"),
        ("[meta/MISSING.txt]", "meta/MISSING.txt"),
        ("meta/MISSING.txt:", "meta/MISSING.txt"),
        ("meta/MISSING.txt;", "meta/MISSING.txt"),
        ("meta/MISSING.json.", "meta/MISSING.json"),
        ("MISSING.py", "MISSING.py"),
        # review 12 should-fix 1: names the daemon's path syntax accepts (§29)
        ("meta/MISSING", "meta/MISSING"),
        ("meta/X.c", "meta/X.c"),
        ("meta/MISSING.1st", "meta/MISSING.1st"),
        ("(meta/MISSING)", "meta/MISSING"),
        ("X.c", "X.c"),
        ("meta/A.md,meta/MISSING.txt", "meta/MISSING.txt"),
    ],
    ids=["bare", "parens", "double-quotes", "single-quotes", "backticks", "angles",
         "brackets", "colon", "semicolon", "json-full-stop", "py-root", "no-extension",
         "one-letter-extension", "digit-first-extension", "parens-no-extension",
         "root-one-letter-extension", "comma-joined"],
)  # fmt: skip
def test_a_named_file_neither_the_kit_nor_the_repo_has_fails_whatever_surrounds_it(
    tmp_path: Path, repo: Path, said: str, named: str
) -> None:
    """§28: every file path a send names is resolved against the kit, then the
    repo; a name neither has fails, not only a `.md`/`.toml` one."""
    kit = write_tree(tmp_path / "k", {**good_kit(), "PLAYBOOK.toml": _send_naming(said)})
    code, out, _ = run_check(kit, repo)
    failed = assert_failed_only(code, out, "protocol")
    assert f"names {named}, which is in neither the kit nor the repo" in strip_paths(failed)


@pytest.mark.parametrize("named", ["../{n}.md", "../REVIEW-{n}.txt", "/tmp/{n}.md", "~/{n}.md",
                                   "meta/../{n}.md", "{n}/../../x.md"])  # fmt: skip
def test_a_placeholder_path_that_is_not_a_repository_path_fails(
    tmp_path: Path, repo: Path, named: str
) -> None:
    """Review 11 should-fix 6: a name with `{` was skipped, so `../{n}.md` passed."""
    kit = write_tree(tmp_path / "k", {**good_kit(), "PLAYBOOK.toml": _send_naming(named)})
    code, out, _ = run_check(kit, repo)
    failed = assert_failed_only(code, out, "protocol")
    assert named in strip_paths(failed) and "not a repository path" in strip_paths(failed)


def test_a_placeholder_repository_path_is_judged_by_its_syntax_and_reported(
    tmp_path: Path, repo: Path
) -> None:
    """A path with a `{placeholder}` names a different file per job (the review a
    job writes), so its existence is not required; it is listed as not read."""
    kit = write_tree(tmp_path / "k", good_kit())
    code, out, err = run_check(kit, repo)
    assert code == 0, out + err
    assert "meta/reviews/REVIEW-{n}.md (a placeholder path, not read)" in strip_paths(
        line(out, "protocol")
    )


def test_a_named_txt_file_the_repo_has_passes(tmp_path: Path, repo: Path) -> None:
    (repo / "meta" / "NOTES.txt").write_text("notes\n", encoding="utf-8")
    kit = write_tree(
        tmp_path / "k", {**good_kit(), "PLAYBOOK.toml": _send_naming("`meta/NOTES.txt`")}
    )
    code, out, err = run_check(kit, repo)
    assert code == 0, out + err
    assert "meta/NOTES.txt (repo)" in strip_paths(line(out, "protocol"))


def _path_repo(root: Path) -> Path:
    """A repo with a `meta/` and a `src/hands/` directory and a root `Makefile`."""
    repo = write_tree(root, {"Makefile": "all:\n", "meta/A.md": "a\n", ".gitignore": "x\n"})
    (repo / "src" / "hands").mkdir(parents=True)
    return repo


@pytest.mark.parametrize(
    "said,named",
    [
        # a word with an extension: its last component has a `.` inside it and the
        # text after its last `.` holds a letter
        ("meta/X.c", ["meta/X.c"]),
        ("X.c", ["X.c"]),
        ("MISSING.1st", ["MISSING.1st"]),
        ("(meta/MISSING.txt)", ["meta/MISSING.txt"]),
        ("meta/MISSING.json.", ["meta/MISSING.json"]),
        ("**NOTES.md**", ["NOTES.md"]),
        ("REVIEW-{n}.md", ["REVIEW-{n}.md"]),
        ("newdir/NOTES.md", ["newdir/NOTES.md"]),
        ("e.g.", ["e.g"]),  # prose the rule cannot tell from a file; it fails closed
        ("github.com", ["github.com"]),  # likewise
        ("v3.12", []),
        ("0.2", []),
        ("§0.2", []),
        (".md", []),
        # a word with a `/`: its first component is a directory of the kit or the repo
        ("meta/MISSING", ["meta/MISSING"]),
        ("(meta/MISSING)", ["meta/MISSING"]),
        ("meta/reviews/REVIEW-{n}", ["meta/reviews/REVIEW-{n}"]),
        ("origin/main", []),
        ("and/or", []),
        ("newdir/NOTES", ["newdir/NOTES"]),  # §30: its last component is a caps name
        ("newdir/notes", []),  # no such directory: indistinguishable from `origin/main`
        ("src/hands", []),  # a directory, not a file
        ("src/hands/", []),
        # ... or it is not a repository path by the daemon's syntax: it fails closed
        ("./scripts/check", ["./scripts/check"]),
        ("/etc/passwd", ["/etc/passwd"]),
        ("~/notes", ["~/notes"]),
        ("../notes", ["../notes"]),
        ("meta//A", ["meta//A"]),
        ("/", []),
        # a bare word: only a file the kit or the repo has
        ("Makefile", ["Makefile"]),
        ("`Makefile`", ["Makefile"]),
        ("GNUmakefile", ["GNUmakefile"]),  # §30: a build-file name, judged absent
        ("notes", []),  # absent and lower-case: indistinguishable from prose
        (".gitignore", [".gitignore"]),
        (".dockerignore", []),
        ("review", []),
        ("{n}", []),
        ("{n+1}", []),
        ("blockers=<k>", []),
        ("--squash", []),
        ("https://example.com/x.md", []),
        ("meta/X.md:12", ["meta/X.md"]),  # §30: `path:line` names the path
        ("meta/A.md,meta/B.md", ["meta/A.md", "meta/B.md"]),
        ("Read meta/A.md, then Makefile (and origin/main).", ["meta/A.md", "Makefile"]),
    ],
)  # fmt: skip
def test_the_named_path_rule_table(tmp_path: Path, said: str, named: list[str]) -> None:
    """§29 (review 12 should-fix 1): which words of a send prompt are file paths.
    §29 is silent on telling a path from an English word; `kit.NAMED_PATH_RULE`
    states the rule this table enumerates."""
    repo = _path_repo(tmp_path / "repo")
    assert kit_mod.named_paths(said, ["kitdir/X.md"], repo) == named


SHAPES = ROOT / "tests" / "fixtures" / "named_path_shapes.tsv"


def _shape_rows() -> list[tuple[str, list[str]]]:
    rows = []
    for text in SHAPES.read_text(encoding="utf-8").splitlines():
        if not text or text.startswith("# "):
            continue
        said, names = text.split("\t")
        rows.append((said, names.split()))
    return rows


@pytest.mark.parametrize("said,named", _shape_rows())
def test_the_named_path_shapes_fixture(tmp_path: Path, said: str, named: list[str]) -> None:
    """§30 (review 13 blocker 2): `kit check` judges bare relative names and names in
    any punctuation the handbook's prompts use; tests/fixtures/named_path_shapes.tsv
    enumerates the shapes, each with the names read from it."""
    repo = _path_repo(tmp_path / "repo")
    assert kit_mod.named_paths(said, ["kitdir/X.md"], repo) == named


def test_the_shapes_fixture_holds_the_reviewers_inputs_and_the_real_prompts() -> None:
    """The fixture is the enumeration §30 asks for: review 13's probes, and this
    repository's and both templates' send prompts, verbatim, are rows of it."""
    rows = _shape_rows()
    for probe in REVIEW_13_PROBES:
        assert probe in [said for said, _ in rows], probe
    books = [ROOT / "PLAYBOOK.toml", TEMPLATES / "PLAYBOOK-missions.toml",
             TEMPLATES / "PLAYBOOK-runs.toml"]  # fmt: skip
    prompts = [
        line.split(" = ", 1)[1].strip().strip('"')
        for book in books
        for line in book.read_text(encoding="utf-8").splitlines()
        if line.startswith("prompt = ")
    ]
    assert len(prompts) == 4
    for prompt in prompts:
        assert prompt in [said for said, _ in rows], prompt


#: §31 (review 14 should-fix 6): the bare-name rule's false positives — English
#: words `named_paths` reads as a file name, so that the boundary of
#: `kit.NAMED_PATH_RULE` is a fixture row and not only prose. It is fail-closed (a
#: prompt saying one of these fails `kit check` until the repository has the file)
#: and no shipped prompt says one, but a change that widened or narrowed the class
#: used to leave no trace.
NAMED_PATH_FALSE_POSITIVES = (
    "PASS", "FAIL", "NOT", "GREEN", "VERDICTS", "README",
    "API", "CLI", "HEAD", "TODO", "Profile",
)  # fmt: skip


def test_the_shapes_fixture_pins_the_bare_name_rules_false_positives() -> None:
    """Each false positive is a row of tests/fixtures/named_path_shapes.tsv naming
    itself, so the parametrized test above runs it against the rule."""
    rows = dict(_shape_rows())
    for word in NAMED_PATH_FALSE_POSITIVES:
        assert rows.get(word) == [word], f"{word!r} is not pinned as a false positive"
    assert rows.get("VERDICT") == [], "VERDICT, the verdict line's word, is excepted"


#: Review 13 blocker 2's inputs, each with the file it names.
REVIEW_13_PROBES = {
    "read NOTES": "NOTES",
    "run Makefile": "Makefile",
    "see meta/MISSING.md:12": "meta/MISSING.md",
    "meta/MISSING.md#L3": "meta/MISSING.md",
    "\u201cmeta/MISSING.md\u201d": "meta/MISSING.md",
    "meta/MISSING.md\u2026": "meta/MISSING.md",
    "--prompt-file=meta/MISSING.md": "meta/MISSING.md",
    "meta/MISSING.md|": "meta/MISSING.md",
    "NOTES": "NOTES",
    "MISSING.1": "MISSING.1",
}


@pytest.mark.parametrize("said,named", sorted(REVIEW_13_PROBES.items()))
def test_review_13s_inputs_fail_protocol_end_to_end(
    tmp_path: Path, repo: Path, said: str, named: str
) -> None:
    """Review 13 blocker 2: `hands kit check` exited 0 with "PASS protocol" when a
    send named any of these; each missing file now fails protocol, and only it."""
    kit = write_tree(tmp_path / "k", {**good_kit(), "PLAYBOOK.toml": _send_naming(said)})
    code, out, _ = run_check(kit, repo)
    failed = assert_failed_only(code, out, "protocol")
    assert f"names {named}, which is in neither the kit nor the repo" in strip_paths(failed)


def test_a_word_under_a_directory_only_the_kit_has_is_a_path(tmp_path: Path) -> None:
    repo = _path_repo(tmp_path / "repo")
    assert kit_mod.named_paths("kitdir/NOTES", ["kitdir/X.md"], repo) == ["kitdir/NOTES"]
    assert kit_mod.named_paths("kitdir", ["kitdir/X.md"], repo) == []


def test_a_named_bare_file_the_repo_has_is_judged_and_listed(tmp_path: Path, repo: Path) -> None:
    (repo / "Makefile").write_text("all:\n", encoding="utf-8")
    kit = write_tree(tmp_path / "k", {**good_kit(), "PLAYBOOK.toml": _send_naming("Makefile")})
    code, out, err = run_check(kit, repo)
    assert code == 0, out + err
    assert "Makefile (repo)" in strip_paths(line(out, "protocol"))


@pytest.mark.parametrize("n", range(8, 15))
def test_this_repositorys_brief_checked_against_this_repository_passes(
    tmp_path: Path, n: int
) -> None:
    """§28 H-022's acceptance, kept under §29's and §30's wider path rule: a kit of
    meta/BUILDER-<n>-PROMPT.md checked with `--repo` this repository exits 0 (its
    playbook's send names `origin/main` and says `VERDICT`, neither a file). The
    briefs 8 to 14 are the ones that passed before §30; 1 to 7 fail on checks the
    path rule does not touch."""
    name = f"meta/BUILDER-{n}-PROMPT.md"
    brief = (ROOT / name).read_text(encoding="utf-8")
    kit = write_tree(tmp_path / "k", {name: brief})
    code, out, err = run_check(kit, ROOT)
    assert code == 0, out + err


# --------------------------- §28: the apply exception, alternatives (should-fix 7)


@pytest.mark.parametrize(
    "pattern,outcome",
    [
        # match the apply literal and nothing in the vocabulary: the one exception
        ("^VERDICT: kit applied", "excused"),
        ("VERDICT: kit applied", "excused"),
        ("^VERDICT: kit applied ", "excused"),
        ("VERDICT: kit applied .*", "excused"),
        ("^VERDICT: kit applied\\b", "excused"),
        ("(?i)^verdict: kit applied", "excused"),
        ("^VERDICT: kit applied <sha>", "excused"),
        ("^VERDICT: kit", "excused"),
        ("kit applied", "excused"),
        # match the literal and a vocabulary literal: judged by the vocabulary, not excused
        ("^VERDICT: ", "vocabulary"),
        ("VERDICT", "vocabulary"),
        ("^VERDICT: (kit applied|mission \\d+ finished)", "fails"),  # `kit applied` branch
        # match the literal, but an alternative does not
        ("^VERDICT: (kit applied|misison \\d+ finished)", "fails"),
        # match neither the literal nor the vocabulary
        ("^VERDICT: kit applied$", "fails"),
        ("^VERDICT: kit applied \\w+", "fails"),
        ("^VERDICT: kit applied [0-9a-f]+", "fails"),
    ],
)  # fmt: skip
def test_the_apply_verdict_exception_enumerated(
    tmp_path: Path, repo: Path, pattern: str, outcome: str
) -> None:
    """§29 (review 12 should-fix 7): exactly one `builder.done` rule may match the
    literal `VERDICT: kit applied <sha>` and nothing in the vocabulary
    (`kit.APPLY_EXCEPTION`). Rule 1 of PLAYBOOK is replaced by `pattern`."""
    book = PLAYBOOK.replace("'^VERDICT: kit applied'", f"'{pattern}'")
    kit = write_tree(tmp_path / "k", {**good_kit(), "PLAYBOOK.toml": book})
    code, out, err = run_check(kit, repo)
    if outcome != "fails":
        assert code == 0, out + err
        noted = "rule 1 matches the apply prompt's" in strip_paths(line(out, "verdicts"))
        assert noted == (outcome == "excused"), out
    else:
        failed = assert_failed_only(code, out, "verdicts")
        assert f"verdict '{pattern}'" in strip_paths(failed)


def _extra_builder_rule(pattern: str) -> str:
    return (
        f"\n[[rule]]\non = \"builder.done\"\nverdict = '{pattern}'\n"
        "then = \"notify\"\nmessage = \"extra\"\n"
    )


def test_a_catch_all_beside_the_apply_rule_is_judged_by_the_vocabulary(
    tmp_path: Path, repo: Path
) -> None:
    """§29: `^VERDICT:` matches the apply literal and the vocabulary; it is judged by
    the vocabulary and is not a second excused rule (this repository's playbook
    has one after its apply rule)."""
    book = PLAYBOOK + _extra_builder_rule("^VERDICT:")
    kit = write_tree(tmp_path / "k", {**good_kit(), "PLAYBOOK.toml": book})
    code, out, err = run_check(kit, repo)
    assert code == 0, out + err
    assert "rule 1 matches the apply prompt's" in strip_paths(line(out, "verdicts"))


def test_a_vocabulary_rule_with_an_apply_branch_fails_by_its_alternative(
    tmp_path: Path, repo: Path
) -> None:
    book = PLAYBOOK + _extra_builder_rule("^VERDICT: (?:kit applied|question)")
    kit = write_tree(tmp_path / "k", {**good_kit(), "PLAYBOOK.toml": book})
    code, out, _ = run_check(kit, repo)
    failed = assert_failed_only(code, out, "verdicts")
    assert "rule 6 verdict '^VERDICT: (?:kit applied|question)': its alternative 'kit applied'" in (
        strip_paths(failed)
    )


def test_the_apply_exception_is_stated_once_in_the_code_and_the_handbook() -> None:
    assert kit_mod.APPLY_EXCEPTION == (
        "exactly one builder.done rule may match the literal 'VERDICT: kit applied <sha>' "
        "and nothing in the vocabulary"
    )
    handbook = (ROOT / "docs" / "ARCHITECT-HANDBOOK.md").read_text(encoding="utf-8")
    assert kit_mod.APPLY_EXCEPTION in " ".join(handbook.split())


def test_only_one_rule_is_excused_by_the_apply_literal(tmp_path: Path, repo: Path) -> None:
    second = (
        "\n[[rule]]\non = \"builder.done\"\nverdict = '^VERDICT: kit applied'\n"
        "then = \"notify\"\nmessage = \"again\"\n"
    )
    kit = write_tree(tmp_path / "k", {**good_kit(), "PLAYBOOK.toml": PLAYBOOK + second})
    code, out, _ = run_check(kit, repo)
    failed = assert_failed_only(code, out, "verdicts")
    assert "rule 6 verdict '^VERDICT: kit applied'" in strip_paths(failed)
    assert "only one rule is excused by the apply prompt's literal, and rule 1 is" in (
        strip_paths(failed)
    )


def test_a_review_rule_with_a_typod_alternative_fails(tmp_path: Path, repo: Path) -> None:
    """Review 11 should-fix 7: `(blockers=0|blokers=0)` passed because one branch
    matched. Hands' reading of §28 "must match a vocabulary literal": every
    alternative of the regex must."""
    book = PLAYBOOK.replace("blockers=0'", "(blockers=0|blokers=0)'")
    kit = write_tree(tmp_path / "k", {**good_kit(), "PLAYBOOK.toml": book})
    code, out, _ = run_check(kit, repo)
    failed = assert_failed_only(code, out, "verdicts")
    assert "its alternative 'blokers=0' matches none of the review protocol's" in strip_paths(
        failed
    )
    good = PLAYBOOK.replace("blockers=0'", "(blockers=0|blockers=[1-9])'")
    kit = write_tree(tmp_path / "k2", {**good_kit(), "PLAYBOOK.toml": good})
    code, out, err = run_check(kit, repo)
    assert code == 0, out + err


def test_a_builder_rule_with_a_typod_alternative_fails(tmp_path: Path, repo: Path) -> None:
    book = PLAYBOOK.replace("(?P<n>\\d+) blocked'", "(?P<n>\\d+) (?:blocked|blokced)'")
    kit = write_tree(tmp_path / "k", {**good_kit(), "PLAYBOOK.toml": book})
    code, out, _ = run_check(kit, repo)
    failed = assert_failed_only(code, out, "verdicts")
    assert "its alternative 'blokced' matches none of:" in strip_paths(failed)


def test_a_driver_rule_with_a_typod_alternative_fails(tmp_path: Path, repo: Path) -> None:
    book = _consult_book("'^VERDICT: (resolved|reslved) (?P<what>.+)'")
    kit = write_tree(tmp_path / "k", {**good_kit(), "PLAYBOOK.toml": book})
    code, out, _ = run_check(kit, repo)
    failed = assert_failed_only(code, out, "verdicts")
    assert "its alternative 'reslved' matches none of the driver's" in strip_paths(failed)


def test_pattern_alternatives_skips_classes_and_escapes_and_keeps_groups() -> None:
    alternatives = kit_mod.pattern_alternatives
    assert alternatives(r"^V: [|a] b\| c") == []
    assert alternatives("a|b") == [("a", "a"), ("b", "b")]
    assert alternatives(r"^V: (?P<n>x|y) (?:p|q)") == [
        ("x", r"^V: (?P<n>x) (?:p|q)"),
        ("y", r"^V: (?P<n>y) (?:p|q)"),
        ("p", r"^V: (?P<n>x|y) (?:p)"),
        ("q", r"^V: (?P<n>x|y) (?:q)"),
    ]
    assert alternatives("(a|(b|c))") == [
        ("b", "(a|(b))"), ("c", "(a|(c))"), ("a", "(a)"), ("(b|c)", "((b|c))"),
    ]  # fmt: skip
    assert alternatives(r"[]|](x|y)") == [("x", "[]|](x)"), ("y", "[]|](y)")]


# ------------------------------------- §28: KIT.md's line and the quoting (SF9)


@pytest.mark.parametrize(
    "text,why",
    [
        ("x" * 73 + "\n", "it is 73 characters, over 72"),
        ("plan: it's done\n", "it contains a quote character"),
        ('plan: "done"\n', "it contains a quote character"),
        ("plan: `done`\n", "it contains a quote character"),
        ("plan: one\rtwo\n", "it contains a line break"),
        ("plan: one\u2028two\n", "it contains a line break"),
        ("\n\nplan: second line\n", "it is empty"),
        ("", "it is empty"),
        (b"\xff\xfe plan\n", "it is not UTF-8"),
    ],
    ids=["73-chars", "single-quote", "double-quote", "backtick", "carriage-return",
         "line-separator", "blank-first", "empty", "not-utf8"],
)  # fmt: skip
def test_a_kit_md_line_that_breaks_a_rule_gives_the_default_and_says_why(
    tmp_path: Path, repo: Path, text: str | bytes, why: str
) -> None:
    """§28: the first line is the message only when ≤ 72 characters, with no quote
    character or newline, and not empty; else `plan: kit <name>`, and it says so."""
    kit = write_tree(tmp_path / "mission-11-kit", good_kit())
    (kit / "KIT.md").write_bytes(text if isinstance(text, bytes) else text.encode("utf-8"))
    code, out, err = run_check(kit, repo, "--json")
    assert code == 0, out + err
    answer = json.loads(out)
    assert answer["commit_message"] == "plan: kit mission-11-kit"
    assert answer["kit_md"] is None
    code, out, _ = run_check(kit, repo)
    assert code == 0
    flat = " ".join(strip_paths(out).split())
    assert (
        f"this kit's KIT.md first line is not used ({why}), so the message is the default "
        "'plan: kit mission-11-kit'"
    ) in strip_paths(flat), out
    assert "commit 'plan: kit mission-11-kit' listing" in strip_paths(flat)


def test_a_kit_md_line_of_72_characters_is_the_message(tmp_path: Path, repo: Path) -> None:
    message = "plan: " + "x" * 66
    assert len(message) == 72
    kit = write_tree(tmp_path / "k", {**good_kit(), "KIT.md": f"{message}\nbody\n"})
    code, out, _ = run_check(kit, repo, "--json")
    assert code == 0 and json.loads(out)["commit_message"] == message


@pytest.mark.parametrize(
    "name", ["k.zip", "a$(x).zip", "a`x`.zip", "a;b.zip", "a'b.zip", "a b.zip", "m-12.zip"]
)
def test_the_apply_prompts_kit_name_is_shell_quoted(tmp_path: Path, name: str) -> None:
    """§29 (review 12 should-fix 6): the kit's name is shell-quoted like the
    message; the directory before it stays as handsd shows it (`~` expands)."""
    import shlex

    plan = kit_mod.plan_apply(f"~/Downloads/{name}", ["KIT.md"], None, tmp_path)
    said = plan.prompt.removeprefix("Apply ").split(" to this repository: ", 1)[0]
    assert said == f"~/Downloads/{shlex.quote(name)}"
    assert shlex.split(said) == [f"~/Downloads/{name}"]
    assert plan.prompt.startswith("Apply ~/Downloads/")  # the default gate pattern


@pytest.mark.parametrize(
    "location,kit_md,message",
    [
        ("~/Downloads/it's.zip", None, "plan: kit it's"),
        ("~/Downloads/a$b`c.zip", None, "plan: kit a$b`c"),
        ("/x/m-12.zip", b"plan: mission 12 kit (DESIGN v3.11) $HOME\n",
         "plan: mission 12 kit (DESIGN v3.11) $HOME"),
        ("/x/m-12.zip", b"fix\n", "fix"),
    ],
    ids=["quote-in-name", "dollar-backtick-in-name", "kit-md", "one-word"],
)  # fmt: skip
def test_the_apply_prompts_commit_message_is_shell_quoted(
    tmp_path: Path, location: str, kit_md: bytes | None, message: str
) -> None:
    """§28: the message is shell-quoted, so the shell hands `git commit -m` the
    message as one word whatever the kit's name holds."""
    import shlex

    plan = kit_mod.plan_apply(location, ["KIT.md"], kit_md, tmp_path)
    assert plan.commit_message == message
    said = plan.prompt.split(" makes a single commit ", 1)[1].split(" listing those files", 1)[0]
    assert said == shlex.quote(message)
    assert shlex.split(said) == [message]


# ------------------------- §30: the `job.held` rule is not shipped, not forbidden


#: §30 removed this rule from the playbooks hands ships; it stays a rule a
#: playbook may carry, so another project's file is not made unloadable by it.
HELD_RULE = '\n[[rule]]\non = "job.held"\nthen = "notify"\nmessage = "A job is held"\n'


def test_a_playbook_that_keeps_the_job_held_rule_still_loads_and_passes(
    tmp_path: Path, repo: Path
) -> None:
    """§30: hands stopped shipping the rule; it never forbade it. A kit whose
    playbook still notifies on `job.held` loads through the engine's own parser
    and passes every `kit check`."""
    book = PLAYBOOK + HELD_RULE
    parsed = parse_playbook(book, path=tmp_path / "PLAYBOOK.toml")
    assert [rule.on for rule in parsed.rules if rule.on == "job.held"] == ["job.held"]
    kit = write_tree(tmp_path / "k", {**good_kit(), "PLAYBOOK.toml": book})
    code, out, err = run_check(kit, repo)
    assert code == 0, out + err


def test_the_missions_template_with_the_held_rule_added_back_still_passes(
    tmp_path: Path,
) -> None:
    """The same for the shipped template a project may edit: adding the rule
    back to it keeps the kit passing."""
    kit = write_tree(
        tmp_path / "k",
        {
            "meta/BUILDER-11-PROMPT.md": template("BUILDER-N-PROMPT.md"),
            "PLAYBOOK.toml": template("PLAYBOOK-missions.toml") + HELD_RULE,
            "meta/REVIEW-PROTOCOL.md": template("REVIEW-PROTOCOL.md"),
        },
    )
    code, out, err = run_check(kit, write_tree(tmp_path / "repo", {"README.md": "x"}))
    assert code == 0, out + err


# ------------------------------------------------- `hands kit file` (§31, U3)
#
# The architect's own route to the phone's `kit`: a zip under `$HANDS_KITS`,
# checked against the role's clone (`$HANDS_CLONE`) first, and — only when every
# check passes — filed as the same held builder apply, with `origin: architect`.
# Unlike `kit check` it reaches the daemon, so it needs a config and a socket.


@pytest.fixture
def kits(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, repo: Path) -> Path:
    """The role's kits directory and clone, as handsd sets them on the job."""
    directory = tmp_path / "kits"
    directory.mkdir()
    monkeypatch.setenv("HANDS_KITS", str(directory))
    monkeypatch.setenv("HANDS_CLONE", str(repo))
    return directory


def zip_kit(path: Path, files: dict[str, str]) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        for name, text in files.items():
            archive.writestr(name, text)
    return path


def run_file(kit: Path, *extra: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    code = main(["kit", "file", str(kit), *extra], stdout=out, stderr=err)
    return code, out.getvalue(), err.getvalue()


def test_hands_help_lists_kit_file(capsys: pytest.CaptureFixture[str]) -> None:
    """The mission's acceptance: `hands --help` names `kit file`."""
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    assert "kit file" in strip_paths(capsys.readouterr().out)


def test_hands_kit_help_lists_both_subcommands(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["kit", "--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert re.search(r"^\s+check\s", out, re.MULTILINE), out
    assert re.search(r"^\s+file\s", out, re.MULTILINE), out


@pytest.mark.parametrize("where", ["outside", "dotdot", "symlink"])
def test_kit_file_refuses_a_path_that_is_not_under_hands_kits(
    tmp_path: Path, repo: Path, kits: Path, write_config, where: str
) -> None:
    """§31: "from a path under `HANDS_KITS`" — decided by realpath, so a `..`
    and a symlink out of the directory are refused as an outside path is."""
    write_config()
    outside = zip_kit(tmp_path / "outside.zip", good_kit())
    if where == "outside":
        path = outside
    elif where == "dotdot":
        path = kits / ".." / "outside.zip"
    else:
        path = kits / "link.zip"
        path.symlink_to(outside)
    code, out, err = run_file(path)
    assert code != 0, out
    assert "HANDS_KITS" in strip_paths(err), err
    assert "filed" not in strip_paths(out)


def test_kit_file_refuses_when_hands_kits_is_unset(
    tmp_path: Path, repo: Path, kits: Path, write_config, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_config()
    kit = zip_kit(kits / "m16.zip", good_kit())
    monkeypatch.delenv("HANDS_KITS")
    code, _, err = run_file(kit)
    assert code != 0 and "HANDS_KITS" in strip_paths(err), err
    monkeypatch.setenv("HANDS_KITS", "")
    code, _, err = run_file(kit)
    assert code != 0 and "HANDS_KITS" in strip_paths(err), err


def test_kit_file_refuses_when_hands_clone_is_unset(
    repo: Path, kits: Path, write_config, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§31: the check runs "against the role's clone (`HANDS_CLONE`) as the repo"."""
    write_config()
    kit = zip_kit(kits / "m16.zip", good_kit())
    monkeypatch.delenv("HANDS_CLONE")
    code, _, err = run_file(kit)
    assert code != 0 and "HANDS_CLONE" in strip_paths(err), err


def test_kit_file_does_not_file_a_failing_kit_and_carries_the_checks_output(
    repo: Path, kits: Path, write_config
) -> None:
    """§31: "after running the kit check itself and refusing a failing kit"."""
    write_config()
    broken = {**good_kit(), "../escape.md": "no"}
    kit = zip_kit(kits / "m16.zip", broken)
    code, out, err = run_file(kit)
    assert code == 1, out + err
    # the check's own output, line for line, is what the refusal carries
    assert line(out, "paths").startswith("FAIL"), out
    for name in CHECK_NAMES:
        assert line(out, name), out
    assert "not filed" in strip_paths(out), out
    assert "apply prompt:" not in strip_paths(out), out


def test_kit_file_json_says_the_failing_kit_was_not_filed(
    repo: Path, kits: Path, write_config
) -> None:
    write_config()
    kit = zip_kit(kits / "m16.zip", {**good_kit(), "/etc/passwd": "no"})
    code, out, _ = run_file(kit, "--json")
    assert code == 1
    answer = json.loads(out)
    assert answer["filed"] is False and answer["ok"] is False and answer["job"] is None
    assert [check["name"] for check in answer["checks"]] == list(CHECK_NAMES)


def test_kit_file_files_the_held_apply_the_phones_kit_files(
    tmp_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§31: "files a held apply job exactly as the phone's `kit` does
    (`origin: architect`, the same prompt from the zip's entries and `KIT.md`)".

    The prompt is built by the one function the phone builds it with, from the
    same three arguments; the job is born `held` inside `Api.send`, so the
    `job.held` inbox event — and with it the notification and the buttons —
    happens on the daemon's own event path, with nothing added here.
    """
    import asyncio

    from harness import config_body, drive, write_project

    workdir = write_tree(
        tmp_path / "work", {"PLAYBOOK.toml": PLAYBOOK, "meta/REVIEW-PROTOCOL.md": PROTOCOL}
    )
    clone = write_tree(
        tmp_path / "clone", {"PLAYBOOK.toml": PLAYBOOK, "meta/REVIEW-PROTOCOL.md": PROTOCOL}
    )
    kits_dir = tmp_path / "kits"
    kits_dir.mkdir()
    monkeypatch.setenv("HANDS_KITS", str(kits_dir))
    monkeypatch.setenv("HANDS_CLONE", str(clone))
    kit = zip_kit(
        kits_dir / "mission-16-kit.zip", {**good_kit(), "KIT.md": "plan: mission 16 kit\n"}
    )
    write_project(tmp_home, config_body(tmp_home, workdir))
    answers: dict[str, object] = {}

    async def body(daemon) -> None:
        code, out, err = await asyncio.to_thread(run_file, kit, "--json")
        answers["code"], answers["out"], answers["err"] = code, out, err
        answers["events"] = [event.kind for event in daemon.spool.unacked()]

    drive(body)
    assert answers["code"] == 0, answers["out"] + answers["err"]
    answer = json.loads(str(answers["out"]))
    assert answer["filed"] is True and answer["ok"] is True
    job = answer["job"]
    assert job["role"] == "builder" and job["context"] == "clear"
    assert job["origin"] == "architect", "§31: the origin is the architect's own"
    assert job["state"] == "held", "§8: a gated job is born held"
    assert job["gate"]["reason"] == "apply mission-16-kit"
    plan = kit_mod.apply_from_zip(kit, workdir, kit_mod.home_shown(kit))
    assert job["prompt"] == plan.prompt
    assert plan.commit_message == "plan: mission 16 kit"
    kinds = answers["events"]
    assert isinstance(kinds, list) and kinds[0] == "job.held", kinds


def test_the_phone_and_the_architect_file_one_apply_with_two_origins() -> None:
    """The shared body, so the two routes cannot drift: same role, context, gate
    and prompt; only the origin differs (§27 `kit`, §31 `architect`)."""
    plan = kit_mod.Apply(name="m16", replaces=[], adds=[], commit_message="plan: kit m16",
                         kit_md=None, prompt="Apply it.")
    phone = kit_mod.apply_params(plan, "kit")
    architect = kit_mod.apply_params(plan, "architect")
    assert phone == {**architect, "origin": "kit"}
    assert architect == {
        "role": "builder",
        "context": "clear",
        "prompt": "Apply it.",
        "gate": "apply m16",
        "origin": "architect",
    }
