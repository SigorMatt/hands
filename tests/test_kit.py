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
        "KIT.md: the first line of a KIT.md entry is the commit message; this kit "
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
        "KIT.md: the first line of a KIT.md entry is the commit message; this kit's "
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
