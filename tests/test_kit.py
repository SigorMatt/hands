"""`hands kit check` (DESIGN §4 `kit check` row, §26 "the architect's tooling").

A kit is checked in the client, without a daemon, a socket or the network: its
paths, the playbook in force, the brief's kickoff line and final-reply vocabulary
against the playbook's `verdict` regexes, the brief's wording, and the protocol
files the playbook's sends name. One passing kit (dir and zip), one failing kit
per check, the mission 10 kit as it was committed at 61e1486, and the shipped
templates filled in.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import shutil
import subprocess
import sys
import warnings
import zipfile
from pathlib import Path

import pytest

from conftest import strip_paths
from hands import kit as kit_mod
from hands.cli import main
from hands.playbook import orphaned_rule_warnings, parse_playbook
from harness import CRAFTED_HOWS, CRAFTED_NAME, CRAFTED_TARGET, crafted_zip

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
        "files in its body, and pushes. If the push is refused, undo that commit "
        "(git reset --keep HEAD~1) and reply instead with one line: VERDICT: kit not "
        "applied pr=none <why, in one line>. Change nothing else. "
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
        ([(".claude/settings.json", b"{}")], "a path inside .claude"),
        ([("docs/N.md", b"1"), ("docs/N.md", b"2")], "a duplicate entry"),
    ],
    ids=["dotdot", "absolute", "git", "claude", "duplicate"],
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
        ".GIT/config", "docs/.Git/hooks/post-checkout", ".claude/settings.json",
        ".Claude/hooks/bash_guard.py", "docs/.claude/settings.json",
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


# §33 (REVIEW-16 blocker 2, H-036): the names extraction uses, and one judge of them.

#: Why `kit check` and `apply_from_zip` refuse each `crafted_zip` entry.
DISAGREE = {
    "unicode": "a Unicode Path extra field naming another file",
    "local-unicode": "a Unicode Path extra field naming another file",
    "local": "a local-header name that differs from the central directory's",
}


@pytest.mark.parametrize("how", CRAFTED_HOWS)
def test_a_zip_entry_whose_names_disagree_fails_paths(
    tmp_path: Path, repo: Path, how: str
) -> None:
    """The reviewer's zip: `docs/notes.md` in both headers, `.git/hooks/pre-commit`
    in its Unicode Path field. `paths` fails naming the entry and why."""
    kit = tmp_path / "evil.zip"
    kit.write_bytes(crafted_zip(dict(good_kit()), how))
    failed = assert_failed_only(*run_check(kit, repo)[:2], "paths")
    assert f"{CRAFTED_NAME} ({DISAGREE[how]})" in strip_paths(failed), failed


@pytest.mark.parametrize("how", CRAFTED_HOWS)
def test_apply_from_zip_refuses_an_entry_whose_names_disagree(
    tmp_path: Path, repo: Path, how: str
) -> None:
    """The phone's kit path and `kit_file` list the zip with `apply_from_zip`: it
    files no apply whose prompt names another file than the one unzip writes."""
    kit = tmp_path / "evil.zip"
    kit.write_bytes(crafted_zip(dict(good_kit()), how))
    with pytest.raises(kit_mod.KitError) as exc:
        kit_mod.apply_from_zip(kit, repo, "~/Downloads/evil.zip")
    said = strip_paths(str(exc.value))
    assert said == f"1 of 3 entries are not repository paths ({DISAGREE[how]})", said


@pytest.mark.skipif(shutil.which("unzip") is None, reason="needs Info-ZIP unzip")
def test_unzip_writes_the_unicode_path_of_the_crafted_zip(tmp_path: Path) -> None:
    """The crafted zip is the attack: `unzip -o` writes `.git/hooks/pre-commit`,
    not `docs/notes.md`. hands reads the Unicode Path field itself (`_unicode_paths`),
    so it sees the target on every Python; `ZipInfo.filename` takes the field only
    from CPython 3.12 — 3.11's zipfile ignores it and keeps the header's name."""
    kit = tmp_path / "evil.zip"
    kit.write_bytes(crafted_zip(dict(good_kit()), "unicode"))
    with zipfile.ZipFile(kit) as archive:
        (info,) = [each for each in archive.infolist() if each.orig_filename == CRAFTED_NAME]
        assert kit_mod._unicode_paths(info.extra) == [CRAFTED_TARGET]
        honoured = sys.version_info >= (3, 12)
        assert info.filename == (CRAFTED_TARGET if honoured else CRAFTED_NAME)
    into = tmp_path / "into"
    into.mkdir()
    subprocess.run(["unzip", "-q", "-o", str(kit)], cwd=into, check=True)
    assert (into / CRAFTED_TARGET).is_file()
    assert not (into / CRAFTED_NAME).exists()


def test_a_zip_with_a_unicode_path_field_that_agrees_passes(tmp_path: Path, repo: Path) -> None:
    """A Unicode Path field naming the entry's own name is no disagreement."""
    import struct
    import zlib

    raw = b"docs/NOTE.md"
    kit = tmp_path / "agree.zip"
    with zipfile.ZipFile(kit, "w") as archive:
        for good, text in good_kit().items():
            archive.writestr(good, text)
        info = zipfile.ZipInfo(raw.decode())
        info.extra = struct.pack("<HHBL", 0x7075, 5 + len(raw), 1, zlib.crc32(raw)) + raw
        archive.writestr(info, "x")
    code, out, _ = run_check(kit, repo)
    assert code == 0, out
    adds = kit_mod.apply_from_zip(kit, repo, "~/Downloads/agree.zip").adds
    assert adds == ["docs/NOTE.md", "meta/BUILDER-11-PROMPT.md"], adds


def test_a_zip_entry_name_that_is_not_ascii_passes_only_marked_utf8(
    tmp_path: Path, repo: Path
) -> None:
    """A name not marked UTF-8 is read as cp437 by zipfile and in the host's charset
    by other unzips, so a non-ASCII one has no one name: refused. Marked, it passes."""
    marked = zipped(tmp_path / "marked.zip", [("docs/\u00e9.md", b"x")])
    code, out, _ = run_check(marked, repo)
    assert code == 0, out
    unmarked = zipped(tmp_path / "unmarked.zip", [("docs/X.md", b"x")])
    unmarked.write_bytes(unmarked.read_bytes().replace(b"docs/X.md", b"docs/\x82.md"))
    failed = assert_failed_only(*run_check(unmarked, repo)[:2], "paths")
    assert "(a name that is not ASCII and not marked UTF-8)" in strip_paths(failed), failed
    with pytest.raises(kit_mod.KitError, match="not marked UTF-8"):
        kit_mod.apply_from_zip(unmarked, repo, "~/Downloads/unmarked.zip")


def test_a_dir_kit_entry_inside_claude_fails(tmp_path: Path, repo: Path) -> None:
    kit = write_tree(tmp_path / "k", {**good_kit(), ".claude/settings.json": "{}"})
    failed = assert_failed_only(*run_check(kit, repo)[:2], "paths")
    assert ".claude/settings.json (a path inside .claude)" in strip_paths(failed), failed


@pytest.mark.parametrize("into", [".claude", ".git"])
def test_an_entry_that_lands_inside_claude_or_git_through_a_repo_symlink_fails(
    tmp_path: Path, repo: Path, into: str
) -> None:
    """`cfg -> .claude` in the repo: the entry `cfg/settings.json` resolves into it."""
    (repo / into).mkdir()
    (repo / "cfg").symlink_to(into)
    kit = zipped(tmp_path / "link.zip", [("cfg/settings.json", b"{}")])
    failed = assert_failed_only(*run_check(kit, repo)[:2], "paths")
    assert "cfg/settings.json (lands inside .git or .claude through a symlink)" in strip_paths(
        failed
    ), failed
    with pytest.raises(kit_mod.KitError, match="lands inside .git or .claude"):
        kit_mod.apply_from_zip(kit, repo, "~/Downloads/link.zip")


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


# ------------------------------------- §35: the pull-request flow's templates

#: The finished literal a PR-shaped brief asks for (§35 "The builder").
PR_FINISHED = "VERDICT: mission 11 finished pr=<number>"


def test_a_brief_with_the_pr_literal_passes_the_verdicts_check(
    tmp_path: Path, repo: Path
) -> None:
    """§35: the playbook's unchanged `^VERDICT: mission (?P<n>\\d+) finished` matches
    `VERDICT: mission N finished pr=<number>` by prefix, so kit check's vocabulary
    accepts the `pr=<number>` placeholder as it accepts `<unit>`."""
    brief = BRIEF.replace("`VERDICT: mission 11\n  finished`", f"`{PR_FINISHED}`")
    assert PR_FINISHED in strip_paths(brief)
    kit = write_tree(tmp_path / "k", {**good_kit(), "meta/BUILDER-11-PROMPT.md": brief})
    code, out, err = run_check(kit, repo)
    assert code == 0, out + err
    assert line(out, "verdicts").startswith("PASS verdicts: ")


def test_a_brief_with_both_finished_literals_passes_and_one_without_pr_still_does(
    tmp_path: Path, repo: Path
) -> None:
    """The template offers both shapes (PR and "direct"); each literal must match a
    rule, and the one finished rule matches both. The direct brief (no `pr=`) is
    `BRIEF` itself."""
    assert "pr=" not in strip_paths(BRIEF)
    both = BRIEF.replace(
        "`VERDICT: mission 11\n  finished`", f"`{PR_FINISHED}` | `VERDICT: mission 11 finished`"
    )
    for name, brief in (("both", both), ("direct", BRIEF)):
        kit = write_tree(tmp_path / name, {**good_kit(), "meta/BUILDER-11-PROMPT.md": brief})
        code, out, err = run_check(kit, repo)
        assert code == 0, (name, out + err)
        assert line(out, "verdicts").startswith("PASS verdicts: "), name


def test_the_filled_brief_template_carries_both_finished_literals() -> None:
    literals = kit_mod.final_reply_literals(template("BUILDER-N-PROMPT.md"))
    assert literals is not None
    assert literals.count(PR_FINISHED) == 1
    assert literals.count("VERDICT: mission 11 finished") == 1


def test_the_brief_template_says_the_branch_the_pr_and_the_return_to_main() -> None:
    """§35 "The builder": the brief template's text, flattened."""
    text = " ".join((TEMPLATES / "BUILDER-N-PROMPT.md").read_text(encoding="utf-8").split())
    for said in (
        "`mission-N`",
        "merging `main` in first",
        "push",
        "`gh pr create --base main --head mission-N --title \"mission N: <title>\" "
        "--body-file meta/FINAL-REPORT-N.md`",
        "`VERDICT: mission N finished pr=<number>`",
        "`git checkout main && git pull --ff-only`",
        "direct",
    ):
        assert said in strip_paths(text), f"the brief template does not say {said!r}"
    assert "as before" not in strip_paths(text)


def test_the_protocol_template_finds_the_pr_reads_the_hosted_review_and_merges() -> None:
    """§35 "The review": the protocol template's text, flattened."""
    text = " ".join((TEMPLATES / "REVIEW-PROTOCOL.md").read_text(encoding="utf-8").split())
    for said in (
        "gh pr list --head <branch> --state open --json number,baseRefName,headRefOid",
        "`git log <base>..origin/<branch> ^origin/main`",
        "merge-base with `main`",
        "`reviewed:` sha",
        "`review:` commit on `main`",
        "`gh api repos/<owner>/<repo>/issues/<pr>/comments`",
        "pulls/<pr>/comments`",
        "pulls/<pr>/reviews`",
        "ten minutes",
        "one-minute foreground steps",
        "`## Hosted review`",
        "verbatim",
        "dismissed",
        "`reviewed: <sha>`",
        "first line after the title",
        "before any merge",
        "`gh pr merge <number> --merge --subject \"merge: mission N (PR #<number>)\"`",
        "`git checkout main && git pull --ff-only`",
        "leaves the PR open",
        "VERDICT: review mission N blockers=<k> should-fix=<m>",
    ):
        assert said in strip_paths(text), f"the protocol template does not say {said!r}"
    raw = (TEMPLATES / "REVIEW-PROTOCOL.md").read_text(encoding="utf-8")
    assert kit_mod.review_literals([raw]) == [
        "VERDICT: review mission N blockers=<k> should-fix=<m>"
    ]


#: §36 "The review protocol" (review 19 should-fix 1, 2 and its Notes item for
#: mission 20's protocol; HF-007; HF-008): each sentence the protocol template
#: must carry, flattened. meta/REVIEW-PROTOCOL.md is the template with the
#: repository's names (tests/test_docs.py), so it carries them too.
PROTOCOL_36_SENTENCES = {
    "direct-only-when-the-brief-says-direct": (
        "The direct shape only when the Branch section of `meta/BUILDER-N-PROMPT.md`"
        ' says "Direct"'
    ),
    "the-branch-named-once": "the branch the brief names, `<branch>`",
    "find-the-pr-of-the-branch": (
        "gh pr list --head <branch> --state open --json number,baseRefName,headRefOid"
    ),
    "no-pr-is-a-blocker": 'one blocker, "no pull request for <branch>"',
    "no-pr-stops-the-review": "the review goes no further",
    "no-pr-records-nothing-reviewed": "`reviewed: none`",
    "commits-exclude-mains-history": "`git log <base>..origin/<branch> ^origin/main`",
    "merge-base-of-the-branch": "`git merge-base origin/main origin/<branch>`",
    "sub-agents-one-at-a-time": "one at a time, never concurrently",
    "tests-only-commit-body-names-wrong-changes": (
        "A commit that changes only tests must name in its body each wrong change"
        " that would make them red"
    ),
    "tests-only-wrong-changes-made-in-the-worktree": (
        "the sub-agent makes each one in the worktree, without committing, runs the"
        " relevant tests, expects red, and restores"
    ),
    "tests-only-commit-naming-none-is-a-blocker": (
        "A tests-only commit whose body names none is a blocker"
    ),
    "the-reviewers-own-run-once-at-the-tip": (
        "You run `./scripts/check` yourself once, at the tip under review"
    ),
    "on-an-up-to-date-main-before-committing": (
        "Before you commit it, bring the tree to an up-to-date `main`:"
        " `git checkout main && git pull --ff-only`"
    ),
}


#: §38 (review 21 should-fix 2; H-049, H-050): the four sentences both protocol
#: files carry, flattened. The revert step supersedes §37's single
#: `git checkout <sha>~1 -- <files>`, which fails for a file the commit adds.
PROTOCOL_38_SENTENCES = {
    "the-revert-step-per-file": (
        "in the worktree at the commit, for each non-test file the body lists,"
        " `git checkout <sha>~1 -- <file>` when the file exists at `<sha>~1`, else"
        " `rm` it; then run the commit's new tests and expect red; then restore"
    ),
    "the-schedule-in-the-notes": (
        "one line per sub-agent with its start and end time; the sub-agents run one"
        " at a time so that one `./scripts/check` runs at a time inside the"
        " gate's timeout"
    ),
    "the-owner-decisions-commit-is-not-a-unit": (
        "A `plan: decisions <date> (owner)` commit is read for what it says it does"
        " and is not reviewed as a unit"
    ),
    "a-human-supplied-commit-by-show-stat-alone": (
        'A human-supplied commit (`fixtures:`, from a "human-supplied unit" of the'
        " brief) is checked by `git show --stat` alone"
    ),
}

#: §39 (review 22 should-fix 8; H-055; "The hosted review, read mechanically";
#: docs/QODO-EXTRACTION.md): the sentences both protocol files carry, flattened.
PROTOCOL_39_SENTENCES = {
    "the-restore-git-rms-a-file-absent-at-sha": (
        "`git rm -q -f -- <file>` for each listed file absent at `<sha>` (a file"
        " the commit deletes), then `git checkout <sha> -- <the other files>`"
    ),
    "the-tree-is-clean-after-the-restore": "`git status --short` must be empty after it",
    "an-unclean-tree-stops-the-sub-agent": (
        "A sub-agent whose `git status --short` is not empty after the restore stops"
    ),
    "a-body-names-deleted-files": (
        "A commit body names each file it adds as added and each file it deletes as"
        " deleted"
    ),
    "the-hosted-review-is-a-command": "`hands hosted-review <pr>`",
    "run-by-a-fresh-context-sub-agent": "ONE fresh-context sub-agent",
    "in-a-worktree-at-the-branch": "in a `git worktree` at `origin/<branch>`",
    "the-method-is-cited": "docs/QODO-EXTRACTION.md",
    "the-archive-path": "`meta/reviews/hosted/PR-<pr>/<k>/`",
    "the-verdict-from-the-code-review-comment-only": (
        "takes the verdict from the Code Review comment only"
    ),
    "no-bot-comment-yet-is-the-wait": (
        'Exit 3, "no bot comment yet", is the wait, never a clean review'
    ),
    "the-dispositions-audited-against-the-archive": (
        "audits the builder's dispositions, the `## Hosted review` table of"
        " `meta/FINAL-REPORT-N.md`, against the archive"
    ),
    "a-silent-design-fix-is-reported": (
        "a finding that needed a design decision and was fixed in silence"
    ),
    "the-archive-committed-with-the-review-file": (
        "You may commit that file and the hosted-review archive directory only"
    ),
}

#: §38's restore and §35's one-file commit, superseded by §39.
PROTOCOL_39_SUPERSEDED = (
    "then `git checkout <sha> -- <the same files>`",
    "You may commit that one file only",
)


@pytest.mark.parametrize("key", sorted(PROTOCOL_39_SENTENCES))
@pytest.mark.parametrize("name", ["templates", "meta"])
def test_the_protocol_restores_per_file_and_reads_the_hosted_review_by_command(
    name: str, key: str
) -> None:
    """§39: both protocol files carry the restore that `git rm`s a file the commit
    deletes and requires a clean `git status`, and the hosted-review step run as
    `hands hosted-review <pr>` by a fresh-context sub-agent; the superseded
    wording and "stash" are gone from each."""
    path = Path(__file__).resolve().parents[1] / name / "REVIEW-PROTOCOL.md"
    text = " ".join(path.read_text(encoding="utf-8").split())
    said = PROTOCOL_39_SENTENCES[key]
    assert said in strip_paths(text), f"{name}/REVIEW-PROTOCOL.md does not say {said!r}"
    for old in PROTOCOL_39_SUPERSEDED:
        assert old not in strip_paths(text), f"{name}/REVIEW-PROTOCOL.md still says {old!r}"
    for word in ("stash", "Stash", "STASH"):
        assert word not in strip_paths(text), f"{name}/REVIEW-PROTOCOL.md says {word}"


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


def test_the_protocols_revert_and_restore_leave_a_clean_tree_for_add_edit_delete(
    tmp_path: Path,
) -> None:
    """H-055: the protocol's commands, run on a local repository whose commit adds,
    edits and deletes a file, revert all three and restore to an empty `git status
    --short`; the old one-checkout restore fails on the deleted file, and a plain
    `git rm -q` refuses the file the revert staged, which is why the step says `-f`."""
    repo = tmp_path / "r"
    repo.mkdir()
    for args in (("init", "-q"), ("config", "user.email", "t@t"), ("config", "user.name", "t")):
        assert _git(repo, *args).returncode == 0
    (repo / "edited.py").write_text("old\n")
    (repo / "deleted.py").write_text("gone\n")
    assert _git(repo, "add", ".").returncode == 0
    assert _git(repo, "commit", "-qm", "one").returncode == 0
    (repo / "edited.py").write_text("new\n")
    (repo / "added.py").write_text("added\n")
    assert _git(repo, "rm", "-q", "deleted.py").returncode == 0
    assert _git(repo, "add", "edited.py", "added.py").returncode == 0
    assert _git(repo, "commit", "-qm", "two").returncode == 0
    sha = _git(repo, "rev-parse", "HEAD").stdout.strip()
    listed = ["edited.py", "added.py", "deleted.py"]

    def exists(rev: str, name: str) -> bool:
        return _git(repo, "cat-file", "-e", f"{rev}:{name}").returncode == 0

    def revert() -> None:
        for name in listed:
            if exists(f"{sha}~1", name):
                assert _git(repo, "checkout", f"{sha}~1", "--", name).returncode == 0
            else:
                (repo / name).unlink()
        assert (repo / "edited.py").read_text() == "old\n"
        assert (repo / "deleted.py").exists() and not (repo / "added.py").exists()

    revert()
    # §38's restore: one checkout of the same files at <sha> restores none of them.
    assert _git(repo, "checkout", sha, "--", *listed).returncode != 0
    assert _git(repo, "status", "--short").stdout != ""
    # A plain `git rm -q` refuses the file the revert staged.
    assert _git(repo, "rm", "-q", "--", "deleted.py").returncode != 0

    # §39's restore, as the protocol words it.
    absent = [name for name in listed if not exists(sha, name)]
    assert absent == ["deleted.py"]
    for name in absent:
        assert _git(repo, "rm", "-q", "-f", "--", name).returncode == 0
    others = [name for name in listed if name not in absent]
    assert _git(repo, "checkout", sha, "--", *others).returncode == 0
    assert _git(repo, "status", "--short").stdout == ""


#: §39 "The hosted review's findings are fixed in the pull request they belong
#: to": what the brief template's last unit says, flattened, in this order.
BRIEF_39_SENTENCES = (
    "opens the pull request (see Branch)",
    "waits up to ten minutes for the bot",
    "`hands hosted-review <pr>`",
    "docs/QODO-EXTRACTION.md",
    "fixes each finding that is within the design",
    "a finding that needs a design decision is filed in `meta/findings/FINDINGS.md`,"
    " never fixed in silence",
    "pushes",
    "the `## Hosted review` table",
    "`fixed in <sha>` | `dismissed: <reason>` | `finding H-nnn filed`",
    "returns the tree to `main`",
)


def test_the_brief_templates_last_unit_reads_and_fixes_the_hosted_review() -> None:
    text = " ".join((TEMPLATES / "BUILDER-N-PROMPT.md").read_text(encoding="utf-8").split())
    last = text.split("**U-last Final report.**", 1)[1].split("## Acceptance", 1)[0]
    at = -1
    for said in BRIEF_39_SENTENCES:
        assert said in strip_paths(last[at + 1:]), (
            f"the brief's last unit does not say {said!r} in order"
        )
        at = last.index(said, at + 1)
    assert "no bot comment yet" in strip_paths(last)
    assert "never a clean review" in strip_paths(last)
    assert "`hands hosted-review <pr>`" in strip_paths(text.split("## Execution model", 1)[1])


#: §37's wording, superseded by §38: it must be gone from both files.
PROTOCOL_37_REVERT_STEP = (
    "in the worktree at the commit, `git checkout <sha>~1 -- <the non-test files"
    " the body lists>`, run the commit's new tests and expect red"
)


@pytest.mark.parametrize("key", sorted(PROTOCOL_38_SENTENCES))
@pytest.mark.parametrize("name", ["templates", "meta"])
def test_the_protocol_reverts_by_checkout_and_never_says_stash(name: str, key: str) -> None:
    """§38: both protocol files carry the per-file revert step (checkout at the
    parent when the file exists there, else rm), the Notes schedule and its
    reason, the owner-decisions exception and the human-supplied check; §37's
    one-command wording and "stash" are gone from each (the files differ only in
    the project's names, tests/test_docs.py)."""
    path = Path(__file__).resolve().parents[1] / name / "REVIEW-PROTOCOL.md"
    text = " ".join(path.read_text(encoding="utf-8").split())
    said = PROTOCOL_38_SENTENCES[key]
    assert said in strip_paths(text), f"{name}/REVIEW-PROTOCOL.md does not say {said!r}"
    keeps = f"{name}/REVIEW-PROTOCOL.md keeps §37's step"
    assert PROTOCOL_37_REVERT_STEP not in strip_paths(text), keeps
    for word in ("stash", "Stash", "STASH"):
        assert word not in strip_paths(text), f"{name}/REVIEW-PROTOCOL.md still says {word}"


@pytest.mark.parametrize("key", sorted(PROTOCOL_36_SENTENCES))
def test_the_protocol_template_carries_section_36s_sentence(key: str) -> None:
    text = " ".join((TEMPLATES / "REVIEW-PROTOCOL.md").read_text(encoding="utf-8").split())
    said = PROTOCOL_36_SENTENCES[key]
    assert said in strip_paths(text), f"the protocol template does not say {said!r}"


def test_the_protocol_template_names_the_branch_once() -> None:
    """§36: `mission-N` appears once (as what `<branch>` is by default); every
    command says `<branch>`."""
    text = (TEMPLATES / "REVIEW-PROTOCOL.md").read_text(encoding="utf-8")
    assert text.count("mission-N") == 1, text.count("mission-N")
    assert "origin/mission-N" not in strip_paths(text)
    assert "--head mission-N" not in strip_paths(text)


def test_the_missions_template_review_prompt_lets_the_protocol_find_the_commits() -> None:
    """§35: the review prompt no longer fixes the base itself; the finished regex
    is unchanged."""
    book = parse_playbook(
        template("PLAYBOOK-missions.toml"), path=TEMPLATES / "PLAYBOOK-missions.toml"
    )
    finished = [rule for rule in book.rules if rule.then == "send" and rule.role == "aux"]
    assert len(finished) == 1
    rule = finished[0]
    assert rule.verdict is not None
    assert rule.verdict.pattern == r"^VERDICT: mission (?P<n>\d+) finished"
    assert rule.prompt is not None
    assert "every commit after" not in strip_paths(rule.prompt)
    assert "finds the mission's commits itself" in strip_paths(rule.prompt)


def test_the_filled_missions_templates_pass_six_of_six_against_a_clone_of_this_repository(
    tmp_path: Path,
) -> None:
    """§35's gate: a kit from the filled templates, checked against a `git clone` of
    this repository, passes every check."""
    clone = tmp_path / "clone"
    subprocess.run(
        ["git", "clone", "--quiet", str(ROOT), str(clone)], check=True, capture_output=True
    )
    kit = write_tree(
        tmp_path / "k",
        {
            "meta/BUILDER-11-PROMPT.md": template("BUILDER-N-PROMPT.md"),
            "PLAYBOOK.toml": template("PLAYBOOK-missions.toml"),
            "meta/REVIEW-PROTOCOL.md": template("REVIEW-PROTOCOL.md"),
        },
    )
    code, out, err = run_check(kit, clone)
    assert code == 0, out + err
    for name in CHECK_NAMES:
        assert line(out, name).startswith(f"PASS {name}: "), out


def test_the_role_mode_missions_templates_pass_six_of_six_with_the_blocked_consult(
    tmp_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§38 (H-048): a kit from the filled missions templates with the architect
    blocks uncommented — the role-mode variant, whose `builder.done` blocked verdict
    consults the architect — checked against a clone of this repository and a config
    with `[roles.architect]`, passes every check."""
    monkeypatch.delenv("HANDS_PROJECT", raising=False)
    _config(tmp_home, tmp_path, architect=True)
    clone = tmp_path / "clone"
    subprocess.run(
        ["git", "clone", "--quiet", str(ROOT), str(clone)], check=True, capture_output=True
    )
    # "Uncomment" as a human does (and test_docs' `uncommented`): strip one `# `
    # from each line between the `# >>> architect` markers, drop the markers.
    lines, inside = [], False
    for text in template("PLAYBOOK-missions.toml").splitlines():
        if text.strip() in ("# >>> architect", "# <<< architect"):
            inside = text.strip() == "# >>> architect"
            continue
        lines.append(text[2:] if inside and text.startswith("# ") else text)
    book = "\n".join(lines) + "\n"
    parsed = parse_playbook(book, path=TEMPLATES / "PLAYBOOK-missions.toml")
    assert [rule for rule in parsed.rules if rule.then == "consult" and rule.on == "builder.done"
            and rule.verdict is not None
            and rule.verdict.search("VERDICT: mission 11 blocked <unit>")]
    kit = write_tree(
        tmp_path / "k",
        {
            "meta/BUILDER-11-PROMPT.md": template("BUILDER-N-PROMPT.md"),
            "PLAYBOOK.toml": book,
            "meta/REVIEW-PROTOCOL.md": template("REVIEW-PROTOCOL.md"),
        },
    )
    code, out, err = run_check(kit, clone)
    assert code == 0, out + err
    for name in CHECK_NAMES:
        assert line(out, name).startswith(f"PASS {name}: "), out
    assert len(CHECK_NAMES) == 6


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


# ------------------------------------- `hands kit file <dir>` (§31, §32; U2)
#
# The architect's own route to the phone's `kit` (§32, H-030): a DIRECTORY
# `kits/<name>/<repository paths>` under `$HANDS_KITS`. The client builds the zip
# from it (entries at their paths relative to the directory), checks that zip
# against the role's clone (`$HANDS_CLONE`), and — only when every check passes —
# sends the zip's bytes to the daemon's `kit_file`, which stores them in the
# spool, mints the `kit_id`, and files the held builder apply with `origin:
# architect`. Unlike `kit check` it reaches the daemon, so it needs a config.


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


def never_send(params: dict[str, object]) -> dict[str, object]:
    raise AssertionError(f"a refused kit reached the daemon: {sorted(params)}")


def file_direct(kit: Path, *, send=never_send, as_json: bool = False) -> tuple[int, str]:
    out = io.StringIO()
    code = kit_mod.file_run(str(kit), send=send, out=out, as_json=as_json)
    return code, out.getvalue()


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


def test_hands_kit_file_help_says_directory_not_zip(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["kit", "file", "--help"])
    assert exc.value.code == 0
    out = " ".join(capsys.readouterr().out.split())
    assert "build the zip of a kit directory" in strip_paths(out), out
    assert "a .zip under" not in strip_paths(out), out


@pytest.mark.parametrize("where", ["outside", "dotdot", "symlink"])
def test_kit_file_refuses_a_directory_that_is_not_under_hands_kits(
    tmp_path: Path, repo: Path, kits: Path, write_config, where: str
) -> None:
    """§31, §32: a directory under `HANDS_KITS`, decided by realpath, so a `..` and
    a symlink out of the directory are refused as an outside path is."""
    write_config()
    outside = write_tree(tmp_path / "outside" / "m16", good_kit())
    if where == "outside":
        path = outside
    elif where == "dotdot":
        path = kits / ".." / "outside" / "m16"
    else:
        path = kits / "m16"
        path.symlink_to(outside)
    code, out, err = run_file(path)
    assert code != 0, out
    assert "HANDS_KITS" in strip_paths(err), err
    assert "filed" not in strip_paths(out)


@pytest.mark.parametrize("shape", ["zip", "file", "kits-itself", "missing", "dot-name"])
def test_kit_file_refuses_anything_but_a_kit_directory_under_hands_kits(
    repo: Path, kits: Path, write_config, shape: str
) -> None:
    """§32: `hands kit file <dir>` — a zip is not filed (the architect has no `zip`
    to make one), nor a file, nor the kits directory itself (its entries would be
    `<name>/…`), nor a path that is not there, nor a name the apply cannot carry."""
    write_config()
    if shape == "zip":
        path = zip_kit(kits / "m16.zip", good_kit())
    elif shape == "file":
        path = kits / "m16.md"
        path.write_text("x")
    elif shape == "kits-itself":
        write_tree(kits, good_kit())
        path = kits
    elif shape == "missing":
        path = kits / "m16"
    else:
        path = write_tree(kits / ".m16", good_kit())
    code, out, err = run_file(path)
    assert code != 0, out
    assert "hands kit file" in strip_paths(err) and "kits/<name>" in strip_paths(err), err
    assert "filed" not in strip_paths(out)


def test_kit_file_refuses_when_hands_kits_is_unset_or_empty(
    repo: Path, kits: Path, write_config, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_config()
    kit = write_tree(kits / "m16", good_kit())
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
    kit = write_tree(kits / "m16", good_kit())
    monkeypatch.delenv("HANDS_CLONE")
    code, _, err = run_file(kit)
    assert code != 0 and "HANDS_CLONE" in strip_paths(err), err


@pytest.mark.parametrize("inside", ["file", "directory"])
def test_kit_file_refuses_a_symlink_inside_the_kit_directory(
    tmp_path: Path, repo: Path, kits: Path, inside: str
) -> None:
    """§32 is silent on a symlink inside the staged directory; the choice is to
    refuse it, file or directory, pointing in or out: a kit is whole files, and a
    link would carry bytes from outside `HANDS_KITS` into the zip."""
    kit = write_tree(kits / "m16", good_kit())
    secret = write_tree(tmp_path / "secret", {"id_rsa": "private"})
    if inside == "file":
        (kit / "docs").mkdir()
        (kit / "docs" / "KEY.md").symlink_to(secret / "id_rsa")
        named = "docs/KEY.md"
    else:
        (kit / "docs").symlink_to(secret)
        named = "docs/"
    with pytest.raises(kit_mod.KitError) as exc:
        file_direct(kit)
    assert "symlink" in strip_paths(str(exc.value)), exc.value
    assert named in strip_paths(str(exc.value)), exc.value


def test_a_directory_kits_entries_are_its_repository_paths(tmp_path: Path) -> None:
    """§32 (H-030): `kits/m16/meta/X.md` becomes the entry `meta/X.md`. Dotfiles are
    entries like any other; an empty directory carries nothing (a zip of files);
    the same directory builds the same bytes (one date, sorted entries)."""
    kit = write_tree(
        tmp_path / "kits" / "m16",
        {**good_kit(), "KIT.md": "plan: m16\n", ".github/workflows/ci.yml": "on: push\n"},
    )
    (kit / "empty" / "deeper").mkdir(parents=True)
    data = kit_mod.build_zip(kit)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = archive.namelist()
        assert archive.read("meta/BUILDER-11-PROMPT.md").decode() == BRIEF
        assert all(not info.is_dir() for info in archive.infolist())
    assert names == sorted(
        ["meta/BUILDER-11-PROMPT.md", "PLAYBOOK.toml", "KIT.md", ".github/workflows/ci.yml"]
    )
    assert not any(name.startswith(("kits/", "m16/", "/")) for name in names)
    assert kit_mod.build_zip(kit) == data


def test_kit_file_does_not_file_a_failing_kit_and_carries_the_checks_output(
    repo: Path, kits: Path, write_config
) -> None:
    """§31, §32: "checks it … refusing a failing kit" with the check's output, and
    nothing reaches the daemon (no daemon runs here, and none is asked)."""
    write_config()
    kit = write_tree(kits / "m16", {"PLAYBOOK.toml": PLAYBOOK})  # no brief
    code, out = file_direct(kit)
    assert code == 1, out
    assert line(out, "brief").startswith("FAIL"), out
    for name in CHECK_NAMES:
        assert line(out, name), out
    assert "not filed" in strip_paths(out), out
    assert "apply prompt:" not in strip_paths(out), out
    code, out, err = run_file(kit)
    assert code == 1, out + err
    assert line(out, "brief").startswith("FAIL") and "not filed" in strip_paths(out), out


def test_kit_file_checks_the_zip_it_built_whose_git_entry_fails_paths(
    repo: Path, kits: Path
) -> None:
    """The check reads the built zip, so a staged `.git/…` is a `paths` FAIL."""
    kit = write_tree(kits / "m16", {**good_kit(), ".git/hooks/post-checkout": "x"})
    code, out = file_direct(kit)
    assert code == 1, out
    assert line(out, "paths").startswith("FAIL"), out
    assert ".git" in strip_paths(line(out, "paths")), out


def test_kit_file_json_says_the_failing_kit_was_not_filed(
    repo: Path, kits: Path, write_config
) -> None:
    write_config()
    kit = write_tree(kits / "m16", {"PLAYBOOK.toml": PLAYBOOK})
    code, out = file_direct(kit, as_json=True)
    assert code == 1
    answer = json.loads(out)
    assert answer["filed"] is False and answer["ok"] is False and answer["job"] is None
    assert [check["name"] for check in answer["checks"]] == list(CHECK_NAMES)


def test_kit_file_sends_only_the_name_and_the_built_zip(repo: Path, kits: Path) -> None:
    """The daemon mints the `kit_id` and builds the apply: the client sends the
    kit's name and the bytes it checked, and nothing that names an origin, a
    prompt, a gate or an id."""
    import base64

    kit = write_tree(kits / "m16", good_kit())
    sent: list[dict[str, object]] = []

    def send(params: dict[str, object]) -> dict[str, object]:
        sent.append(params)
        return {"id": "20260916-000001-abcd", "state": "held", "kit_id": "k", "prompt": "p"}

    code, out = file_direct(kit, send=send)
    assert code == 0, out
    (params,) = sent
    assert sorted(params) == ["name", "zip"]
    assert params["name"] == "m16"
    assert base64.b64decode(str(params["zip"])) == kit_mod.build_zip(kit)


def test_under_pull_request_kit_file_files_the_pull_request_prompt(
    tmp_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§45: the architect's `hands kit file` files the apply's prompt in the
    configured shape; its branch names the sha256 of the zip handsd stored, the
    one `build_zip` builds and `hands kit check` prints for the directory."""
    import asyncio

    from harness import (
        architect_table,
        close_consultation,
        config_body,
        drive,
        open_consultation,
        write_project,
    )

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
    kit = write_tree(kits_dir / "m29", {**good_kit(), "KIT.md": "plan: mission 29 kit\n"})
    extra = architect_table(tmp_home) + '\n[repository]\nmain = "pull-request"\n'
    write_project(tmp_home, config_body(tmp_home, workdir, extra=extra))
    answers: dict[str, object] = {}

    async def body(daemon) -> None:
        consulting = open_consultation(daemon)
        answers["passing"] = await asyncio.to_thread(run_file, kit, "--json")
        answers["spool"] = daemon.spool.root
        close_consultation(daemon, consulting)

    drive(body)
    code, out, err = answers["passing"]  # type: ignore[misc]
    assert code == 0, out + err
    job = json.loads(out)["job"]
    digest = hashlib.sha256(kit_mod.build_zip(kit)).hexdigest()
    stored = Path(str(answers["spool"])) / "kits" / job["kit_id"] / "m29.zip"
    assert hashlib.sha256(stored.read_bytes()).hexdigest() == digest
    plan = kit_mod.apply_from_zip(
        stored, workdir, kit_mod.home_shown(stored), shape="pull-request"
    )
    assert job["prompt"] == plan.prompt
    assert job["prompt"].startswith(f"Apply {kit_mod.home_shown(stored)} to this repository, ")
    assert f"`kit/m29-{digest[:12]}`" in job["prompt"]
    assert f"(sha256 {digest})" in job["prompt"]
    checked = kit_mod.check_kit(kit, workdir, project="demo")
    assert checked.sha256 == digest and checked.apply_shape == "pull-request"


def test_kit_file_files_a_held_apply_with_a_daemon_minted_kit_id(
    tmp_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§32 over a real daemon socket: a failing kit files nothing; a passing one is
    filed as the held builder apply the phone's `kit` files, `origin: architect`,
    with a `kit_id` the daemon minted, recorded on the job in the spool, and the
    zip stored under the spool where the architect's writes cannot reach."""
    import asyncio

    from harness import (
        architect_table,
        close_consultation,
        config_body,
        drive,
        open_consultation,
        write_project,
    )

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
    failing = write_tree(kits_dir / "broken", {"PLAYBOOK.toml": PLAYBOOK})
    kit = write_tree(
        kits_dir / "mission-16-kit", {**good_kit(), "KIT.md": "plan: mission 16 kit\n"}
    )
    write_project(tmp_home, config_body(tmp_home, workdir, extra=architect_table(tmp_home)))
    answers: dict[str, object] = {}

    async def body(daemon) -> None:
        consulting = open_consultation(daemon)  # §32: a kit is filed during one
        answers["consultation"] = consulting.id
        answers["failing"] = await asyncio.to_thread(run_file, failing, "--json")
        answers["jobs_after_failing"] = len(daemon.spool.list_jobs()) - 1
        answers["passing"] = await asyncio.to_thread(run_file, kit, "--json")
        answers["events"] = [event.kind for event in daemon.spool.unacked()]
        answers["spool"] = daemon.spool.root
        answers["record"] = daemon.spool.read_kit_record(
            json.loads(answers["passing"][1])["job"]["kit_id"]  # type: ignore[index]
        )
        close_consultation(daemon, consulting)

    drive(body)
    code, out, err = answers["failing"]  # type: ignore[misc]
    assert code == 1, out + err
    assert json.loads(out)["filed"] is False
    assert answers["jobs_after_failing"] == 0, "a failing kit filed a job"

    code, out, err = answers["passing"]  # type: ignore[misc]
    assert code == 0, out + err
    answer = json.loads(out)
    assert answer["filed"] is True and answer["ok"] is True
    job = answer["job"]
    assert job["role"] == "builder" and job["context"] == "clear"
    assert job["origin"] == "architect", "§31: the origin is the architect's own"
    assert job["state"] == "held", "§8: a gated job is born held"
    assert job["gate"]["reason"] == "apply mission-16-kit"
    kit_id = job["kit_id"]
    assert isinstance(kit_id, str) and re.fullmatch(r"[0-9a-f]{16}", kit_id), kit_id
    spool = Path(str(answers["spool"]))
    on_disk = json.loads((spool / "jobs" / f"{job['id']}.json").read_text())
    assert on_disk["kit_id"] == kit_id and on_disk["origin"] == "architect"
    stored = spool / "kits" / kit_id / "mission-16-kit.zip"
    assert stored.read_bytes() == kit_mod.build_zip(kit)
    # §32: the record the engine checks an approval against, naming the consultation.
    # §33: and the check handsd ran on the stored bytes, against the builder's repo.
    # §34: and the sha256 of the bytes that check passed on.
    assert answers["record"] == {
        "kit_id": kit_id, "name": "mission-16-kit", "consultation": answers["consultation"],
        "check": "pass", "sha256": hashlib.sha256(kit_mod.build_zip(kit)).hexdigest(),
    }
    assert not any(kits_dir.glob("*.zip")), "the zip is the daemon's, not under HANDS_KITS"
    with zipfile.ZipFile(stored) as archive:
        names = sorted(archive.namelist())
    assert names == ["KIT.md", "PLAYBOOK.toml", "meta/BUILDER-11-PROMPT.md"]
    plan = kit_mod.apply_from_zip(stored, workdir, kit_mod.home_shown(stored))
    assert job["prompt"] == plan.prompt
    shown = f"Apply ~/.hands/{spool.name}/kits/{kit_id}/mission-16-kit.zip "
    assert job["prompt"].startswith(shown), job["prompt"]
    assert plan.commit_message == "plan: mission 16 kit"
    kinds = answers["events"]
    assert isinstance(kinds, list) and kinds[0] == "job.held", kinds


def test_the_daemon_refuses_a_kit_id_from_the_client_and_a_bad_kit(
    tmp_home: Path, tmp_path: Path
) -> None:
    """The `kit_id` is the daemon's: neither `kit_file` nor `send` takes one from
    the wire, and `kit_file` refuses a name the apply cannot carry and bytes that
    are not a zip of repository paths, filing nothing."""
    import asyncio
    import base64

    from hands.cli import call
    from harness import (
        architect_table,
        close_consultation,
        config_body,
        drive,
        open_consultation,
        write_project,
    )

    workdir = write_tree(tmp_path / "work", {"PLAYBOOK.toml": PLAYBOOK})
    write_project(tmp_home, config_body(tmp_home, workdir, extra=architect_table(tmp_home)))
    socket_path = tmp_home / ".hands" / "handsd.sock"
    good = base64.b64encode(kit_mod.build_zip(write_tree(tmp_path / "m16", good_kit()))).decode()
    bad_zip = io.BytesIO()
    with zipfile.ZipFile(bad_zip, "w") as archive:
        archive.writestr("../escape.md", "x")
    refusals: list[str] = []

    def refused(method: str, params: dict[str, object]) -> None:
        try:
            call(socket_path, method, params)
        except Exception as exc:  # the client's refusal of an error answer
            refusals.append(f"{method}: {exc}")
            return
        raise AssertionError(f"{method} {sorted(params)} was not refused")

    async def body(daemon) -> None:
        consulting = open_consultation(daemon)  # so each refusal is for its own reason
        for method, params in (
            ("kit_file", {"name": "m16", "zip": good, "kit_id": "forged"}),
            ("send", {"role": "builder", "context": "clear", "prompt": "x", "kit_id": "forged"}),
            ("kit_file", {"name": "../m16", "zip": good}),
            ("kit_file", {"name": "m16", "zip": "not base64!"}),
            ("kit_file", {"name": "m16", "zip": base64.b64encode(bad_zip.getvalue()).decode()}),
            ("file_apply", {"plan": {}, "origin": "architect", "kit_id": "forged"}),
        ):
            await asyncio.to_thread(refused, method, params)
        close_consultation(daemon, consulting)
        answers["jobs"] = [job for job in daemon.spool.list_jobs() if job.role != "architect"]
        answers["kits"] = sorted((daemon.spool.root / "kits").glob("*/*")) if (
            daemon.spool.root / "kits").exists() else []

    answers: dict[str, object] = {}
    drive(body)
    assert answers["jobs"] == [], refusals
    assert answers["kits"] == [], "a refused kit stayed in the spool"
    assert len(refusals) == 6, refusals
    assert "kit_id" in strip_paths(refusals[0]), refusals
    assert "kit_id" in strip_paths(refusals[1]), refusals
    assert "no method 'file_apply'" in strip_paths(refusals[5]), refusals


def test_the_daemon_refuses_a_kit_that_fails_the_check_with_the_checks_output(
    tmp_home: Path, tmp_path: Path
) -> None:
    """§33 (REVIEW-16 blocker 1, H-035): "`kit_file` runs `check_kit` on the bytes it
    stores, against the builder's clone, and refuses a failing kit with the check's
    output". A raw socket `kit_file` — no client-side check — during an open
    consultation: refused, the refusal carries the check's FAIL lines, and nothing is
    filed or kept in the spool."""
    import asyncio
    import base64

    from hands.cli import call
    from harness import (
        UNCHECKED_KIT,
        architect_table,
        close_consultation,
        config_body,
        drive,
        open_consultation,
        write_project,
    )

    workdir = write_tree(
        tmp_path / "work", {"PLAYBOOK.toml": PLAYBOOK, "meta/REVIEW-PROTOCOL.md": PROTOCOL}
    )
    write_project(tmp_home, config_body(tmp_home, workdir, extra=architect_table(tmp_home)))
    socket_path = tmp_home / ".hands" / "handsd.sock"
    unchecked = kit_mod.build_zip(write_tree(tmp_path / "foo", UNCHECKED_KIT))
    assert not kit_mod.check_kit(zip_kit(tmp_path / "foo.zip", UNCHECKED_KIT), workdir).ok
    answers: dict[str, object] = {}

    async def body(daemon) -> None:
        consulting = open_consultation(daemon)
        try:
            await asyncio.to_thread(
                call, socket_path, "kit_file",
                {"name": "foo", "zip": base64.b64encode(unchecked).decode()},
            )
        except Exception as exc:  # the client's refusal of an error answer
            answers["refused"] = str(exc)
        close_consultation(daemon, consulting)
        answers["jobs"] = [job for job in daemon.spool.list_jobs() if job.role != "architect"]
        kits = daemon.spool.root / "kits"
        answers["kits"] = sorted(kits.glob("*")) if kits.exists() else []

    drive(body)
    said = strip_paths(str(answers.get("refused")))
    assert "hands kit check" in strip_paths(said) and "§33" in strip_paths(said), said
    # §33 (H-036): the kit's `.claude/` entries fail `paths` too, since mission 17 U2.
    for check in ("paths", "playbook", "brief", "verdicts", "wording"):
        assert f"FAIL {check}: " in said, (check, said)
    assert ".claude/settings.json (a path inside .claude)" in strip_paths(said), said
    assert answers["jobs"] == [], "a kit that fails the check was filed"
    assert answers["kits"] == [], "a refused kit stayed in the spool"


@pytest.mark.parametrize("how", CRAFTED_HOWS)
def test_the_daemon_refuses_a_kit_whose_entry_names_disagree_and_files_a_clean_one(
    tmp_home: Path, tmp_path: Path, how: str
) -> None:
    """§33 (REVIEW-16 blocker 2, H-036): the reviewer's zip over a raw socket
    `kit_file` during an open consultation — refused with the check's `paths` FAIL,
    nothing filed or kept — and the same kit without that entry is filed, held."""
    import asyncio
    import base64

    from hands.cli import call
    from harness import (
        architect_table,
        close_consultation,
        config_body,
        drive,
        open_consultation,
        write_project,
    )

    workdir = write_tree(
        tmp_path / "work", {"PLAYBOOK.toml": PLAYBOOK, "meta/REVIEW-PROTOCOL.md": PROTOCOL}
    )
    write_project(tmp_home, config_body(tmp_home, workdir, extra=architect_table(tmp_home)))
    socket_path = tmp_home / ".hands" / "handsd.sock"
    evil = base64.b64encode(crafted_zip(dict(good_kit()), how)).decode()
    clean = base64.b64encode(kit_mod.build_zip(write_tree(tmp_path / "m17", good_kit())))
    answers: dict[str, object] = {}

    async def body(daemon) -> None:
        consulting = open_consultation(daemon)
        try:
            await asyncio.to_thread(call, socket_path, "kit_file", {"name": "evil", "zip": evil})
        except Exception as exc:  # the client's refusal of an error answer
            answers["refused"] = str(exc)
        answers["jobs_after_evil"] = [
            job for job in daemon.spool.list_jobs() if job.role != "architect"
        ]
        kits = daemon.spool.root / "kits"
        answers["kits_after_evil"] = sorted(kits.glob("*")) if kits.exists() else []
        answers["filed"] = await asyncio.to_thread(
            call, socket_path, "kit_file", {"name": "m17", "zip": clean.decode()}
        )
        close_consultation(daemon, consulting)

    drive(body)
    said = strip_paths(str(answers.get("refused")))
    assert "FAIL paths: " in strip_paths(said), said
    assert f"{CRAFTED_NAME} ({DISAGREE[how]})" in strip_paths(said), said
    assert answers["jobs_after_evil"] == [], "a kit whose names disagree was filed"
    assert answers["kits_after_evil"] == [], "a refused kit stayed in the spool"
    filed = answers["filed"]
    assert isinstance(filed, dict) and filed["state"] == "held", filed
    assert filed["origin"] == "architect", filed
    assert ".git" not in strip_paths(filed["prompt"]), filed


@pytest.mark.parametrize("configured", [True, False], ids=["no consultation", "no role"])
def test_kit_file_is_refused_when_no_architect_consultation_is_open(
    tmp_home: Path, tmp_path: Path, configured: bool
) -> None:
    """§32: the engine approves "a kit filed by the architect role", so the daemon
    accepts `kit_file` only while an architect consultation is running (or the engine
    waits for its `next kit`), and links the kit to it. Outside one, a same-user
    socket client's zip is refused, naming §32, and nothing is stored or filed."""
    import asyncio
    import base64

    from hands.cli import call
    from harness import architect_table, config_body, drive, write_project

    workdir = write_tree(tmp_path / "work", {"PLAYBOOK.toml": PLAYBOOK})
    extra = architect_table(tmp_home) if configured else ""
    write_project(tmp_home, config_body(tmp_home, workdir, extra=extra))
    socket_path = tmp_home / ".hands" / "handsd.sock"
    good = base64.b64encode(kit_mod.build_zip(write_tree(tmp_path / "m16", good_kit()))).decode()
    answers: dict[str, object] = {}

    async def body(daemon) -> None:
        try:
            await asyncio.to_thread(
                call, socket_path, "kit_file", {"name": "m16", "zip": good}
            )
        except Exception as exc:  # the client's refusal of an error answer
            answers["refused"] = str(exc)
        answers["jobs"] = daemon.spool.list_jobs()
        answers["kits"] = list((daemon.spool.root / "kits").glob("*")) if (
            daemon.spool.root / "kits").exists() else []

    drive(body)
    said = strip_paths(str(answers.get("refused")))
    assert "§32" in strip_paths(said) and "architect" in strip_paths(said), said
    assert answers["jobs"] == [] and answers["kits"] == []


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


def test_kit_file_says_who_releases_the_hold_not_that_a_human_decides_it(
    repo: Path, kits: Path
) -> None:
    """U4's report (§31, §8): the printed line said "a human decides it", which is
    false in exactly the case §31 built — under `[series] architect = "role"` with
    `autonomous = true` the engine approves the record it has just been told about,
    `decided_by: playbook`. The line names both releases and asserts neither.

    `file_run` is called directly with a stand-in `send`, so this pins the words
    the architect reads, not the daemon's path (which the test above drives).
    """
    kit = write_tree(kits / "m16", good_kit())
    filed = {"id": "20260916-000001-abcd", "state": "held", "role": "builder",
             "kit_id": "0123456789abcdef", "prompt": "Apply it."}
    code, text = file_direct(kit, send=lambda params: filed)
    assert code == 0, text
    assert "a human decides it" not in strip_paths(text), text
    assert "kit file: filed 20260916-000001-abcd as a held builder job" in strip_paths(text), text
    assert "(gate: apply m16, origin: architect, kit_id: 0123456789abcdef)" in strip_paths(text)
    for said in ("hands approve", "the engine", "autonomous"):
        assert said in strip_paths(text), f"the filed line does not say {said!r}: {text}"


# ------------------ §32 (review 15 blocker 4): the kit's series against this config

ROLE_PLAYBOOK = PLAYBOOK.replace(
    'name = "demo-missions"\n', 'name = "demo-missions"\narchitect = "role"\n'
)


def _config(tmp_home: Path, tmp_path: Path, *, architect: bool) -> Path:
    body = f'[roles.builder]\ncwd = "{tmp_path}"\n'
    if architect:
        (tmp_path / "hands-architect").mkdir(exist_ok=True)
        body += f'\n[roles.architect]\ncwd = "{tmp_path / "hands-architect"}"\n'
    path = tmp_home / ".hands" / "demo.toml"
    path.write_text(body, encoding="utf-8")
    return path


def test_a_kit_playbook_in_role_mode_fails_against_a_config_without_roles_architect(
    tmp_home: Path, tmp_path: Path, repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§32: "refused … by `hands kit check` when the kit carries the playbook". The
    config is the one `hands` resolves as every command does (`--project`,
    `$HANDS_PROJECT`, the only config); the refusal names both files."""
    monkeypatch.delenv("HANDS_PROJECT", raising=False)
    _config(tmp_home, tmp_path, architect=False)
    kit = write_tree(tmp_path / "k", {**good_kit(), "PLAYBOOK.toml": ROLE_PLAYBOOK})
    code, out, _ = run_check(kit, repo)
    failed = strip_paths(assert_failed_only(code, out, "playbook"))
    assert "PLAYBOOK.toml" in strip_paths(failed) and "demo.toml" in strip_paths(failed), failed
    assert '[series] architect = "role"' in strip_paths(failed), failed
    assert "[roles.architect]" in strip_paths(failed), failed
    # named explicitly, the same
    code, out, _ = run_check(kit, repo, "--project", "demo")
    assert "[roles.architect]" in strip_paths(assert_failed_only(code, out, "playbook"))


def test_a_kit_playbook_in_role_mode_passes_against_a_config_with_roles_architect(
    tmp_home: Path, tmp_path: Path, repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("HANDS_PROJECT", raising=False)
    _config(tmp_home, tmp_path, architect=True)
    kit = write_tree(tmp_path / "k", {**good_kit(), "PLAYBOOK.toml": ROLE_PLAYBOOK})
    code, out, _ = run_check(kit, repo)
    assert code == 0, out
    assert "[roles.architect]" in strip_paths(line(out, "playbook")), out


@pytest.mark.parametrize("case", ["no config", "two configs", "a config that is not TOML"])
def test_a_kit_playbook_in_role_mode_that_cannot_be_judged_fails_and_says_why(
    tmp_home: Path, tmp_path: Path, repo: Path, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    """§33 (REVIEW-16 should-fix 5): `kit check` "judges the playbook's role
    requirements against the repository's config the way `handsd` will at load, and
    says so". handsd loads no playbook without a config it can read, so a role-mode
    kit whose config does not resolve here — none, two and no `--project` /
    `$HANDS_PROJECT`, or one that is not valid TOML — is not passed unjudged: the
    playbook check fails, naming why, and says where it can be judged."""
    monkeypatch.delenv("HANDS_PROJECT", raising=False)
    if case == "two configs":
        _config(tmp_home, tmp_path, architect=True)
        (tmp_home / ".hands" / "other.toml").write_text(
            f'[roles.builder]\ncwd = "{tmp_path}"\n', encoding="utf-8"
        )
    elif case == "a config that is not TOML":
        (tmp_home / ".hands" / "demo.toml").write_text("[roles.builder\n", encoding="utf-8")
    kit = write_tree(tmp_path / "k", {**good_kit(), "PLAYBOOK.toml": ROLE_PLAYBOOK})
    code, out, _ = run_check(kit, repo)
    failed = strip_paths(assert_failed_only(code, out, "playbook"))
    assert "not judged" not in strip_paths(failed), failed
    assert '[series] architect = "role"' in strip_paths(failed), failed
    assert "handsd" in strip_paths(failed), failed
    assert "--project" in strip_paths(failed), failed
    because = {
        "no config": "no project config",
        "two configs": "configures several projects",
        "a config that is not TOML": "is not valid TOML",
    }[case]
    assert because in strip_paths(failed), failed


def test_a_kit_playbook_in_role_mode_is_judged_against_a_named_project_among_two(
    tmp_home: Path, tmp_path: Path, repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Named, one of two configs is the one handsd loads: judged, and the line says
    which file it was judged against and that this is handsd's load-time check."""
    monkeypatch.delenv("HANDS_PROJECT", raising=False)
    _config(tmp_home, tmp_path, architect=True)
    (tmp_home / ".hands" / "other.toml").write_text(
        f'[roles.builder]\ncwd = "{tmp_path}"\n', encoding="utf-8"
    )
    kit = write_tree(tmp_path / "k", {**good_kit(), "PLAYBOOK.toml": ROLE_PLAYBOOK})
    code, out, _ = run_check(kit, repo, "--project", "demo")
    assert code == 0, out
    said = strip_paths(line(out, "playbook"))
    assert "[roles.architect]" in strip_paths(said) and "demo.toml" in strip_paths(said), said
    assert "as handsd does at load" in strip_paths(said), said
    code, out, _ = run_check(kit, repo, "--project", "other")
    assert "[roles.architect]" in strip_paths(assert_failed_only(code, out, "playbook"))


def test_a_kit_playbook_in_phone_mode_does_not_look_for_a_config(
    tmp_path: Path, repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only a role-mode playbook is judged against a config, so `kit check` of any
    other kit stays what §26 made it: no config read, wherever it runs."""
    from hands import config as config_mod

    monkeypatch.setattr(
        config_mod, "load_config", lambda *a, **k: pytest.fail("a config was read")
    )
    kit = write_tree(tmp_path / "k", good_kit())
    code, out, _ = run_check(kit, repo)
    assert code == 0, out
    assert "[roles.architect]" not in strip_paths(line(out, "playbook"))


# --------------------------- §38: the owner file, the brief's shapes, the Purpose

OWNER_TEMPLATE = TEMPLATES / "DECISIONS-owner.md"
#: The two instruction templates §38 names: the Project chat's and the role's.
INSTRUCTIONS = {
    "docs/ARCHITECT-INSTRUCTION.md": ROOT / "docs" / "ARCHITECT-INSTRUCTION.md",
    "architect/CLAUDE.md": ROOT / "architect" / "CLAUDE.md",
}
#: The Purpose block's three lines, as the templates ship them (§38 "Onboarding").
PURPOSE_LINES = (
    "FOR     = <what the project is for, one line>",
    "NOT     = <what the project is not, one line>",
    "DECIDES = <who decides, one line>",
)


def flat(text: str) -> str:
    return " ".join(text.split())


def test_the_owner_decisions_template_has_its_sections() -> None:
    """§38 "The owner-decisions round, as a template": `O-n` numbering continued
    from the last owner file, a precedence header (this file wins over DESIGN and
    earlier decisions), a "Findings closed:" line, and "For the builder" last, the
    only section the builder is told to read."""
    text = OWNER_TEMPLATE.read_text(encoding="utf-8")
    said = flat(text)
    for needed in (
        "O-<n>",
        "continued from the last owner file on the branch",
        "wins over `DESIGN.md` and over every earlier decisions file",
        "Findings closed:",
        "meta/decisions/<date>-owner.md",
        "`plan: decisions <date> (owner)`",
        "the only section the builder reads",
    ):
        assert needed in strip_paths(said), f"the owner template does not say {needed!r}"
    headings = [row for row in text.splitlines() if row.startswith("## ")]
    assert headings and headings[-1] == "## For the builder", headings
    # The precedence header comes before the first decision.
    assert said.index("wins over `DESIGN.md`") < said.index("## O-<n>")
    assert any(row.startswith("Findings closed:") for row in text.splitlines())


def _brief_section(heading: str) -> str:
    text = (TEMPLATES / "BUILDER-N-PROMPT.md").read_text(encoding="utf-8")
    return flat(text.split(f"\n## {heading}\n", 1)[1].split("\n## ", 1)[0])


def test_the_brief_templates_recovery_takes_a_keep_after_a_question_as_the_answer() -> None:
    """§38: a `keep` send after `VERDICT: question` is the answer, carried out, the
    mission continued from the checkpoint, a `VERDICT:` line always, even when a
    file had to be committed first — in §R, where a resumed builder reads it."""
    section = _brief_section("§R Recovery brief")
    for needed in (
        "A `keep` send that arrives after you replied `VERDICT: question` is the answer",
        "carry it out",
        "continue the mission from the checkpoint",
        "end that reply with one of the mission's `VERDICT:` lines, always, even when "
        "the answer came with a file to commit first",
    ):
        assert needed in strip_paths(section), f"§R does not say {needed!r}"


def test_the_brief_templates_units_carry_the_human_supplied_unit_shape() -> None:
    """§38 "Human-supplied content": the unit names the files, their paths and the
    commit message; the human places them under `~/Downloads/<name>/`; the builder
    copies and commits them by path without opening them."""
    section = _brief_section("Units, in order")
    for needed in (
        "human-supplied unit",
        "`~/Downloads/<name>/`",
        "the files, their repository paths and the commit message",
        "copies them to those paths and commits them by path without opening them",
        "`git show --stat`",
    ):
        assert needed in strip_paths(section), f"the Units section does not say {needed!r}"


def _instruction(path: Path) -> list[str]:
    """The instruction's lines: below the `---` divider for the Project chat's
    (the block that is pasted), below the title for the role's."""
    text = path.read_text(encoding="utf-8")
    if "\n---\n" in text:
        text = text.split("\n---\n", 1)[1]
    else:
        text = text.split("\n", 1)[1]
    return text.splitlines()


@pytest.mark.parametrize("name", INSTRUCTIONS)
def test_each_instruction_template_opens_with_the_purpose_block(name: str) -> None:
    """§38 "Onboarding": the Purpose block is a standard slot of three lines the
    human fills (what the project is for, what it is not, who decides), kept
    verbatim at the top of the instruction."""
    rows = [row for row in _instruction(INSTRUCTIONS[name]) if row.strip()]
    assert rows[0].startswith("Purpose"), (name, rows[0])
    assert [row.strip() for row in rows[1:4]] == list(PURPOSE_LINES), (name, rows[1:4])
    raw = INSTRUCTIONS[name].read_text(encoding="utf-8")
    assert "kept verbatim" in strip_paths(flat(raw)), name
    # Once each: the slot is not repeated further down for the human to miss.
    assert [raw.count(purpose) for purpose in PURPOSE_LINES] == [1, 1, 1], name


@pytest.mark.parametrize("name", INSTRUCTIONS)
def test_each_instruction_template_answers_rulings_with_the_owner_file(name: str) -> None:
    """§38: both instruction templates carry the paragraph that tells a project's
    architect to answer rulings with the owner-decisions file."""
    text = flat(INSTRUCTIONS[name].read_text(encoding="utf-8"))
    for needed in (
        "ruling",
        "`templates/DECISIONS-owner.md`",
        "`meta/decisions/<date>-owner.md`",
        "`plan: decisions <date> (owner)`",
        "\"For the builder\"",
    ):
        assert needed in strip_paths(text), f"{name} does not say {needed!r}"


def _role_rule(number: int) -> str:
    """Rule `number` of architect/CLAUDE.md's `## Rules`, flattened to one line."""
    text = INSTRUCTIONS["architect/CLAUDE.md"].read_text(encoding="utf-8")
    rules = text.split("\n## Rules\n", 1)[1]
    found = re.search(rf"^{number}\. (.*?)(?=^\d+\. |\Z)", rules, re.M | re.S)
    assert found, f"architect/CLAUDE.md has no rule {number}"
    return flat(found.group(1)).strip()


def test_the_role_escalates_a_ruling_with_a_drafted_owner_file() -> None:
    """§39 (REVIEW-22 should-fix 9): rule 13 and rule 8 agree. A ruling the role
    cannot make is `VERDICT: escalate ruling: <what>` with a drafted owner file under
    `kits/<name>/meta/decisions/`, which the human adopts or rewrites; rule 8 lists
    the ruling among its conditions."""
    eight, thirteen = _role_rule(8), _role_rule(13)
    assert eight.startswith("Escalate, with `VERDICT: escalate <reason>`"), eight
    assert "ruling" in strip_paths(eight) and "rule 13" in strip_paths(eight), eight
    for said in (
        "`VERDICT: escalate ruling: <what>`",
        "`kits/<name>/meta/decisions/<date>-owner.md`",
        "adopts or rewrites",
        "rule 8",
    ):
        assert said in strip_paths(thirteen), f"rule 13 does not say {said!r}: {thirteen}"
    assert "escalate under rule 8" not in strip_paths(thirteen)
    assert "the draft of the file in your reply's body" not in strip_paths(thirteen)


def test_the_roles_rule_2_reads_the_paths_the_prompt_names() -> None:
    """§39 (H-051 ruling), review 23 should-fix 8: rule 2 tells the role that the
    consultation prompt names the installed handbook and templates by absolute path,
    to Read those paths as the prompt gives them, that `cat` works under them and
    that `hands handbook` prints them. Reverting architect/CLAUDE.md to its text
    before mission 23 U7 (2b4df10~1) turns this red."""
    two = _role_rule(2)
    assert strip_paths(two).startswith("Read the handbook of the hands that runs you"), two
    for said in (
        "`$HANDS_DOCS/docs/ARCHITECT-HANDBOOK.md`",
        "`$HANDS_DOCS/templates/` are your forms",
        "The consultation prompt names both by absolute path",
        "Read those paths, as the prompt gives them, with the Read tool",
        "(`cat` works under them too, and `hands handbook` prints them)",
        "a `docs/` or `templates/` in the clone is the project's, not hands'",
    ):
        assert said in strip_paths(two), f"rule 2 does not say {said!r}: {two}"


def test_the_filled_templates_with_an_owner_file_pass_six_of_six(tmp_path: Path) -> None:
    """§38's gate for U8: a kit built from the templates with placeholders filled —
    the brief with its new §R and Units text, the playbook, the protocol, and an owner
    file from `templates/DECISIONS-owner.md` — checked against a clone of this
    repository, passes every one of the six checks."""
    clone = tmp_path / "clone"
    subprocess.run(
        ["git", "clone", "--quiet", str(ROOT), str(clone)], check=True, capture_output=True
    )
    owner = template("DECISIONS-owner.md").replace("<date>", "2026-10-15").replace("<n>", "1")
    kit = write_tree(
        tmp_path / "k",
        {
            "meta/BUILDER-11-PROMPT.md": template("BUILDER-N-PROMPT.md"),
            "PLAYBOOK.toml": template("PLAYBOOK-missions.toml"),
            "meta/REVIEW-PROTOCOL.md": template("REVIEW-PROTOCOL.md"),
            "meta/decisions/2026-10-15-owner.md": owner,
        },
    )
    code, out, err = run_check(kit, clone)
    assert code == 0, out + err
    assert len(CHECK_NAMES) == 6
    for name in CHECK_NAMES:
        assert line(out, name).startswith(f"PASS {name}: "), out


# ------------------------------------- §39 (H-057): a killed review is resumed


@pytest.mark.parametrize(
    "name", ["PLAYBOOK-missions.toml", "PLAYBOOK-runs.toml", "this repository's PLAYBOOK.toml"]
)
def test_each_shipped_playbook_resumes_an_orphaned_review(name: str) -> None:
    """§39: both templates and this repository's playbook carry `aux.orphaned →
    resume`, one rule, no verdict; read by the engine's own parser (which `kit check`
    uses), so a playbook naming the event loads."""
    if name.startswith("this"):
        text = (ROOT / "PLAYBOOK.toml").read_text(encoding="utf-8")
    else:
        text = template(name)
    book = parse_playbook(text, path=Path("PLAYBOOK.toml"))
    rules = [rule for rule in book.rules if rule.on == "aux.orphaned"]
    assert [(rule.then, rule.verdict) for rule in rules] == [("resume", None)], rules


# ---------------------- §40 (H-061): the playbook without `aux.orphaned` warns

AUX_ORPHANED = '\n[[rule]]\non = "aux.orphaned"\nthen = "resume"\n'
BUILDER_ORPHANED = '\n[[rule]]\non = "builder.orphaned"\nthen = "resume"\n'


def warn_lines(out: str) -> list[str]:
    return [text for text in out.splitlines() if text.startswith("WARN ")]


@pytest.mark.parametrize(
    ("added", "warned", "silent"),
    [
        # PLAYBOOK has rules on builder.done and aux.done and none on either orphaned.
        (AUX_ORPHANED, "builder", "aux"),
        (BUILDER_ORPHANED, "aux", "builder"),
    ],
)
def test_a_done_rule_without_its_orphaned_rule_warns_and_passes_six_of_six(
    tmp_path: Path, repo: Path, added: str, warned: str, silent: str
) -> None:
    """§40: `kit check` warns, and does not refuse, on a playbook with a rule on
    `<role>.done` and none on `<role>.orphaned`; the playbook line still passes."""
    kit = write_tree(tmp_path / "k", {**good_kit(), "PLAYBOOK.toml": PLAYBOOK + added})
    code, out, err = run_check(kit, repo)
    assert code == 0, out + err
    for name in CHECK_NAMES:
        assert line(out, name).startswith(f"PASS {name}: "), out
    assert "kit check: pass (6 of 6 checks)" in strip_paths(out)
    warns = warn_lines(out)
    assert len(warns) == 1, out
    assert warns[0].startswith("WARN playbook: "), out
    assert f"{warned}.done" in strip_paths(warns[0]), out
    assert f"{warned}.orphaned" in strip_paths(warns[0]), out
    assert f"{silent}." not in strip_paths(warns[0]), out


def test_both_done_rules_without_orphaned_rules_warn_twice(tmp_path: Path, repo: Path) -> None:
    kit = write_tree(tmp_path / "k", good_kit())
    code, out, err = run_check(kit, repo)
    assert code == 0, out + err
    assert "kit check: pass (6 of 6 checks)" in strip_paths(out)
    warns = warn_lines(out)
    assert len(warns) == 2, out
    assert "aux.orphaned" in strip_paths(" ".join(warns)), out
    assert "builder.orphaned" in strip_paths(" ".join(warns)), out
    answer = json.loads(run_check(kit, repo, "--json")[1])
    assert answer["ok"] is True
    assert answer["warnings"] == [text.removeprefix("WARN playbook: ") for text in warns]


def test_a_playbook_with_both_orphaned_rules_warns_nothing(tmp_path: Path, repo: Path) -> None:
    book = PLAYBOOK + AUX_ORPHANED + BUILDER_ORPHANED
    kit = write_tree(tmp_path / "k", {**good_kit(), "PLAYBOOK.toml": book})
    code, out, err = run_check(kit, repo)
    assert code == 0, out + err
    assert warn_lines(out) == [], out
    assert json.loads(run_check(kit, repo, "--json")[1])["warnings"] == []


def test_the_repos_playbook_in_force_warns_too(tmp_path: Path, repo: Path) -> None:
    """A kit that carries no playbook is judged against the repo's, which warns."""
    kit = write_tree(tmp_path / "k", {"meta/BUILDER-11-PROMPT.md": BRIEF})
    code, out, _ = run_check(kit, repo)
    assert code == 0, out
    assert len(warn_lines(out)) == 2, out


@pytest.mark.parametrize(
    ("book", "said"),
    [
        (PLAYBOOK.replace("BUILDER-11-PROMPT.md and", "BUILDER-12-PROMPT.md and"), "BUILDER-12"),
        (re.sub(r"kickoff = .*\n", "", PLAYBOOK), "[series] kickoff"),
    ],
    ids=["kickoff-differs", "no-kickoff"],
)
def test_the_warning_prints_when_the_playbook_line_fails_too(
    tmp_path: Path, repo: Path, book: str, said: str
) -> None:
    """§41 "Smaller rulings" (REVIEW-24 should-fix 4): the WARN for a done rule
    without its orphaned rule prints whether or not the `playbook` line passes.
    Making the warning conditional on `playbook_check.ok` turns this red."""
    kit = write_tree(tmp_path / "k", {**good_kit(), "PLAYBOOK.toml": book + AUX_ORPHANED})
    code, out, _ = run_check(kit, repo)
    assert said in strip_paths(assert_failed_only(code, out, "playbook"))
    warns = warn_lines(out)
    assert len(warns) == 1, out
    assert warns[0].startswith("WARN playbook: "), out
    assert "builder.orphaned" in strip_paths(warns[0]), out
    answer = json.loads(run_check(kit, repo, "--json")[1])
    assert answer["ok"] is False
    assert answer["warnings"] == [warns[0].removeprefix("WARN playbook: ")]


@pytest.mark.parametrize(
    "name", ["PLAYBOOK-missions.toml", "PLAYBOOK-runs.toml", "this repository's PLAYBOOK.toml"]
)
def test_each_shipped_playbook_warns_nothing(name: str) -> None:
    if name.startswith("this"):
        text = (ROOT / "PLAYBOOK.toml").read_text(encoding="utf-8")
    else:
        text = template(name)
    assert orphaned_rule_warnings(parse_playbook(text, path=Path("PLAYBOOK.toml"))) == []


# ------------------------- §40 (H-066..H-069): refusals, worktrees, skip list, gate

#: §40 (H-066): the brief template's sub-agent rule and execution-model rule,
#: worded as meta/BUILDER-24-PROMPT.md has them, flattened.
BRIEF_40_SUB_AGENT_RULE = (
    "if you cannot or will not produce what the unit asks, report `refused: <one"
    " line>` and stop, changing nothing;"
)
BRIEF_40_EXECUTION_RULE = (
    "A sub-agent that reports `refused: <one line>` is not retried: mark the unit"
    " `[b] refused` and continue likewise."
)


def test_the_brief_templates_sub_agent_rules_say_refused() -> None:
    """§40 (H-066): the verbatim sub-agent brief carries the `refused:` sentence."""
    section = _brief_section(
        "Sub-agent brief (give this to every unit sub-agent, verbatim, plus the unit)"
    )
    assert BRIEF_40_SUB_AGENT_RULE in strip_paths(section), section


def test_the_brief_templates_execution_model_marks_a_refusal_b_refused() -> None:
    """§40 (H-066): a refusal is not retried; the unit is `[b] refused`, the
    mission continues with units that do not depend on it, and the verdict
    vocabulary still has the blocked line the playbook matches."""
    section = _brief_section("Execution model (binding)")
    assert BRIEF_40_EXECUTION_RULE in strip_paths(section), section
    retry = "Retry a failed unit once with the sub-agent's report attached"
    assert section.index(retry) < section.index(BRIEF_40_EXECUTION_RULE)
    assert "`VERDICT: mission N blocked <unit>`" in strip_paths(section)


def test_the_roles_rule_8_escalates_a_unit_no_agent_will_author() -> None:
    """§40 (H-066), §38: rule 8's conditions gain "a unit no agent will author",
    answered `VERDICT: escalate ruling: human-supplied content` and naming the
    human-supplied unit shape of the brief template."""
    eight = _role_rule(8)
    for said in (
        "a unit no agent will author",
        "`VERDICT: escalate ruling: human-supplied content`",
        "human-supplied unit",
        "`templates/BUILDER-N-PROMPT.md`",
        "`~/Downloads/<name>/`",
    ):
        assert said in strip_paths(eight), f"rule 8 does not say {said!r}: {eight}"


#: §40 (H-067, H-068, H-069): the sentences both protocol files carry, flattened.
PROTOCOL_40_SENTENCES = {
    "the-reviewer-starts-with-prune": "Before anything else, run `git worktree prune`",
    "stale-review-worktrees-under-tmp-removed": (
        "remove each stale review worktree an earlier review left under `/tmp`"
    ),
    "worktrees-removed-with-force": "`git worktree remove --force <path>`",
    "the-review-ends-by-removing-its-own": (
        "Last, remove every worktree this review added"
    ),
    "plan-read-for-what-it-says": (
        "Every other `plan:` commit (the mission's U0 among them) is read the same"
        " way, for what it says it does"
    ),
    "meta-journal-report-for-forbidden-edits-only": (
        "A `meta:`, `journal:` or `report:` commit is read for forbidden edits only"
        " and never reviewed as a unit"
    ),
    "a-file-outside-meta-is-forbidden": (
        "a file it lists outside `meta/` is a forbidden edit"
    ),
    "review-and-merge-commits-skipped": "A `review:` commit and a merge commit are skipped",
    "the-gate-once-in-the-foreground": (
        "run `./scripts/check` once, in the foreground, and report only when every"
        " command has finished"
    ),
}

#: §36's skip list and gate step, superseded by §40.
PROTOCOL_40_SUPERSEDED = (
    "skip `meta:` bookkeeping commits and merge commits",
    "Runs `./scripts/check` once at that commit",
)


def _protocol(name: str) -> str:
    return flat((ROOT / name / "REVIEW-PROTOCOL.md").read_text(encoding="utf-8"))


@pytest.mark.parametrize("key", sorted(PROTOCOL_40_SENTENCES))
@pytest.mark.parametrize("name", ["templates", "meta"])
def test_the_protocol_prunes_worktrees_skips_bookkeeping_and_runs_the_gate_once(
    name: str, key: str
) -> None:
    """§40: both protocol files carry H-067's worktree hygiene, H-068's skip list
    and H-069's gate sentence; §36's skip list and gate step are gone."""
    text = _protocol(name)
    said = PROTOCOL_40_SENTENCES[key]
    assert said in strip_paths(text), f"{name}/REVIEW-PROTOCOL.md does not say {said!r}"
    for old in PROTOCOL_40_SUPERSEDED:
        assert old not in strip_paths(text), f"{name}/REVIEW-PROTOCOL.md still says {old!r}"


@pytest.mark.parametrize("name", ["templates", "meta"])
def test_the_protocol_prunes_first_and_removes_its_own_worktrees_last(name: str) -> None:
    """§40 (H-067): the prune comes before the commits are found, and the removal
    of the review's own worktrees after the merge, before the verdict line."""
    text = strip_paths(_protocol(name))
    prune = text.index(PROTOCOL_40_SENTENCES["the-reviewer-starts-with-prune"])
    assert prune < text.index("## The commits under review")
    own = text.index(PROTOCOL_40_SENTENCES["the-review-ends-by-removing-its-own"])
    assert text.index("## The merge (with a PR)") < own
    assert own < text.index("Your reply's first line is exactly")


#: §41 "Smaller rulings" (REVIEW-24 should-fix 5): what "stale" means, as both
#: protocol files and the handbook's §7 say it, flattened.
STALE_DEFINITION = (
    "A worktree is stale when it is registered under the clone and its path no longer"
    " exists, or when it is a review worktree under `/tmp` that is not this review's"
    " and is older than the current aux job's start",
    "a worktree of a review running concurrently, or one a human made, is never stale",
)


def _paragraph(text: str, opening: str) -> str:
    """The one blank-line-separated paragraph of `text` that starts with `opening`, flattened."""
    found = [flat(p) for p in re.split(r"\n\s*\n", text) if flat(p).startswith(opening)]
    assert len(found) == 1, (opening, found)
    return found[0]


@pytest.mark.parametrize("name", ["templates", "meta"])
def test_the_protocol_defines_stale_and_pins_each_worktree_command_where_it_occurs(
    name: str,
) -> None:
    """§41: the opening paragraph defines stale and removes stale worktrees with
    `git worktree remove --force`; the closing paragraph removes the review's own
    with `git worktree remove --force` and then runs `git worktree prune`.
    Deleting any one of the three commands, or the definition, turns this red."""
    raw = (ROOT / name / "REVIEW-PROTOCOL.md").read_text(encoding="utf-8")
    opening = _paragraph(raw, "Before anything else, run `git worktree prune`")
    assert "under `/tmp` with `git worktree remove --force <path>`" in strip_paths(opening), opening
    for said in STALE_DEFINITION:
        assert said in strip_paths(opening), f"{name}: the opening paragraph does not say {said!r}"
    closing = _paragraph(raw, "Last, remove every worktree this review added")
    assert "`git worktree remove --force <path>` for each" in strip_paths(closing), closing
    assert "then `git worktree prune`" in strip_paths(closing), closing


def test_the_handbook_section_7_defines_stale() -> None:
    """§41 "Documentation": the handbook's §7 carries the definition."""
    text = (ROOT / "docs" / "ARCHITECT-HANDBOOK.md").read_text(encoding="utf-8")
    section = flat(text.split("\n## 7. ", 1)[1].split("\n## ", 1)[0])
    for said in STALE_DEFINITION:
        assert said in strip_paths(section), f"handbook §7 does not say {said!r}"


@pytest.mark.parametrize(
    ("number", "said"),
    [
        (7, "`git worktree prune`"),
        (7, "stale review worktree"),
        (7, "ends by removing its own"),
        (7, "`plan:` (read for what it says)"),
        (7, "`meta:`, `journal:` and `report:` (read for forbidden edits only, never"
            " reviewed as a unit)"),
        (7, "`review:` and merge commits"),
        (7, "run `./scripts/check` once, in the foreground, and report only when every"
            " command has finished"),
        (17, "`refused: <one line>`"),
        (17, "`[b] refused`"),
        (17, "`VERDICT: mission N blocked <unit>`"),
        (17, "`autonomous`"),
        (17, "a unit no agent will author"),
        (17, "`VERDICT: escalate ruling: human-supplied content`"),
    ],
)
def test_the_handbook_says_section_40s_rules(number: int, said: str) -> None:
    """§40 "Documentation": the handbook's §7 says the worktree hygiene, the skip
    list and the gate sentence; §17 says the refusal path."""
    text = (ROOT / "docs" / "ARCHITECT-HANDBOOK.md").read_text(encoding="utf-8")
    heads = re.findall(rf"^## {number}\. .*$", text, flags=re.M)
    assert len(heads) == 1, number
    section = flat(text.split(heads[0], 1)[1].split("\n## ", 1)[0])
    assert said in strip_paths(section), f"handbook §{number} does not say {said!r}"


# ------------------------- §42 "The decisions kit": an owner file sent as a kit

DECISIONS_DATE = "2026-10-18"
OWNER_PATH = f"meta/decisions/{DECISIONS_DATE}-owner.md"
DECISIONS_MESSAGE = f"plan: decisions {DECISIONS_DATE} (owner)"


def owner_text() -> str:
    """An owner file from `templates/DECISIONS-owner.md`, its placeholders filled."""
    return template("DECISIONS-owner.md").replace("<date>", DECISIONS_DATE).replace("<n>", "1")


def decisions_kit() -> dict[str, str]:
    return {OWNER_PATH: owner_text(), "KIT.md": f"{DECISIONS_MESSAGE}\n\nO-1.\n"}


def zip_with_dirs(path: Path, files: dict[str, str]) -> Path:
    """A zip as `zip -r` writes one: a directory entry for each directory, first."""
    dirs = sorted({
        "/".join(name.split("/")[:depth]) + "/"
        for name in files
        for depth in range(1, name.count("/") + 1)
    })  # fmt: skip
    with zipfile.ZipFile(path, "w") as archive:
        for name in dirs:
            archive.writestr(name, "")
        for name, text in files.items():
            archive.writestr(name, text)
    return path


@pytest.mark.parametrize("form", ["zip", "zip -r", "dir"])
def test_a_decisions_kit_passes_six_of_six_with_the_plan_only_apply_prompt(
    tmp_path: Path, repo: Path, form: str
) -> None:
    """§42: a kit of one owner file and a `KIT.md` reading `plan: decisions <date>
    (owner)` passes 6 of 6 — `brief`, `verdicts` and `wording` each saying why it
    applies no brief — and its apply prompt names that file and that message; built
    with directory entries, as `zip -r` writes them, it passes too."""
    if form == "zip":
        kit = zip_kit(tmp_path / "decisions.zip", decisions_kit())
    elif form == "zip -r":
        kit = zip_with_dirs(tmp_path / "decisions.zip", decisions_kit())
        with zipfile.ZipFile(kit) as archive:
            dirs = [info.filename for info in archive.infolist() if info.is_dir()]
        assert dirs == ["meta/", "meta/decisions/"], dirs
    else:
        kit = write_tree(tmp_path / "decisions", decisions_kit())
    code, out, err = run_check(kit, repo)
    assert code == 0, out + err
    for name in CHECK_NAMES:
        assert line(out, name).startswith(f"PASS {name}: "), out
    assert "kit check: pass (6 of 6 checks)" in strip_paths(out)
    brief, verdicts, wording = (strip_paths(line(out, n)) for n in ("brief", "verdicts", "wording"))
    assert "a decisions kit" in strip_paths(brief) and "needs no brief" in strip_paths(brief), brief
    assert "carries no vocabulary" in strip_paths(verdicts), verdicts
    assert "the playbook in force is unchanged" in strip_paths(verdicts), verdicts
    assert "holds no brief" in strip_paths(wording), wording
    assert "the repo's PLAYBOOK.toml is in force" in strip_paths(line(out, "playbook")), out
    said = flat(strip_paths(out))
    assert (
        "Apply ~/Downloads/decisions.zip to this repository: unzip -o into the repo root "
        f"(it adds KIT.md and {OWNER_PATH}), then one plan-only sub-agent makes a single "
        f"commit '{DECISIONS_MESSAGE}' listing those files in its body, and pushes."
    ) in strip_paths(said), out
    assert f"commit message: {DECISIONS_MESSAGE}" in strip_paths(out), out
    report = kit_mod.check_kit(kit, repo)
    assert report.decisions is True and report.ok
    assert json.loads(run_check(kit, repo, "--json")[1])["decisions"] is True


def test_two_owner_files_are_one_decisions_kit(tmp_path: Path, repo: Path) -> None:
    files = {**decisions_kit(), "meta/decisions/2026-10-17-owner.md": owner_text()}
    report = kit_mod.check_kit(zip_kit(tmp_path / "d.zip", files), repo)
    assert report.decisions and report.ok, [c.line() for c in report.checks]


@pytest.mark.parametrize(
    "change",
    [
        {"README.md": "# readme\n"},
        {"PLAYBOOK.toml": PLAYBOOK},
        {"KIT.md": None},
        {"KIT.md": "plan: kit decisions\n"},
        {"KIT.md": "plan: decisions  (owner)\n"},
        {"KIT.md": "plan: decisions 'x' (owner)\n"},
        {"KIT.md": f"{DECISIONS_MESSAGE} and more\n"},
        {OWNER_PATH: None, "meta/decisions/a/b-owner.md": "x\n"},
        {OWNER_PATH: None, "meta/decisions/-owner.md": "x\n"},
        {"meta/decisions/a/b-owner.md": "x\n"},
        {"meta/decisions/-owner.md": "x\n"},
        {OWNER_PATH: None},
        {"meta/decisions/notes.md": "x\n"},
        {".claude/settings.json": "{}\n"},
    ],
    ids=[
        "README.md", "PLAYBOOK.toml", "no KIT.md", "another first line", "an empty date",
        "a quote", "a longer first line", "a/b-owner only", "-owner only",
        "a/b-owner beside", "-owner beside", "KIT.md alone", "not an owner file",
        "a refused entry",
    ],
)  # fmt: skip
def test_a_kit_with_anything_else_is_not_a_decisions_kit_and_is_judged_as_before(
    tmp_path: Path, repo: Path, change: dict[str, str | None]
) -> None:
    """§42: a kit with any other entry beside the owner files, without `KIT.md`, with
    another first line, with an owner file whose `<name>` is not one non-empty path
    component, with no owner file, or with an entry the path rules refuse, is judged
    as before §42: no brief, so `brief` fails as it always has."""
    files: dict[str, str] = {}
    for name, text in {**decisions_kit(), **change}.items():
        if text is not None:
            files[name] = text
    kit = zip_kit(tmp_path / "decisions.zip", files)
    code, out, err = run_check(kit, repo)
    assert code == 1, out + err
    assert line(out, "brief") == (
        "FAIL brief: the kit carries no brief (meta/BUILDER-<N>-PROMPT.md or WORKPLAN.md)"
    ), out
    assert "decisions kit" not in strip_paths(out), out
    assert kit_mod.check_kit(kit, repo).decisions is False


def test_the_brief_templates_recovery_carries_out_the_newest_owner_file() -> None:
    """§42 "The newest owner file, on a resume": §R's sentence, as BUILDER-26's §R
    has it. Deleting it from templates/BUILDER-N-PROMPT.md turns this red."""
    section = _brief_section("§R Recovery brief")
    assert (
        "If a `plan: decisions <date> (owner)` commit is on the branch after the "
        "checkpoint's last update and the checkpoint does not record its \"For the "
        "builder\" steps as done, carry them out first, record them in the checkpoint, "
        "and continue."
    ) in strip_paths(section), section


@pytest.mark.parametrize(
    ("number", "said"),
    [
        (3, "decisions kit"),
        (3, "`meta/decisions/<date>-owner.md`"),
        (3, "`plan: decisions <date> (owner)`"),
        (4, "decisions kit"),
        (4, "\"For the builder\""),
        (11, "decisions kit"),
        (11, "`kit check: pass (6 of 6 checks)`"),
        (11, "`hands kit file` refuses"),
    ],
)
def test_the_handbook_names_the_decisions_kit(number: int, said: str) -> None:
    """§42 "The decisions kit": the handbook's §3, §4 and §11 say so."""
    text = (ROOT / "docs" / "ARCHITECT-HANDBOOK.md").read_text(encoding="utf-8")
    heads = re.findall(rf"^## {number}\. .*$", text, flags=re.M)
    assert len(heads) == 1, number
    section = flat(text.split(heads[0], 1)[1].split("\n## ", 1)[0])
    assert said in strip_paths(section), f"handbook §{number} does not say {said!r}"


def test_kit_file_refuses_a_decisions_kit(
    tmp_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§42: `hands kit file` refuses a decisions kit with a reason — an owner file
    is the human's word — during an open consultation, where an ordinary kit is
    filed; nothing is filed and nothing stays in the spool."""
    import asyncio

    from harness import (
        architect_table,
        close_consultation,
        config_body,
        drive,
        open_consultation,
        write_project,
    )

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
    kit = write_tree(kits_dir / "decisions", decisions_kit())
    assert kit_mod.check_kit(kit, clone).ok
    write_project(tmp_home, config_body(tmp_home, workdir, extra=architect_table(tmp_home)))
    answers: dict[str, object] = {}

    async def body(daemon) -> None:
        consulting = open_consultation(daemon)
        answers["filed"] = await asyncio.to_thread(run_file, kit)
        answers["jobs"] = [job.id for job in daemon.spool.list_jobs()]
        root = daemon.spool.root / "kits"
        answers["kits"] = list(root.glob("*")) if root.exists() else []
        answers["consultation"] = consulting.id
        close_consultation(daemon, consulting)

    drive(body)
    code, out, err = answers["filed"]  # type: ignore[misc]
    assert code != 0, out + err
    said = flat(strip_paths(out + err))
    assert "kit_file: kit 'decisions' is a decisions kit (§42)" in strip_paths(said), said
    assert "an owner file is the human's word" in strip_paths(said), said
    assert answers["jobs"] == [answers["consultation"]], "a decisions kit was filed"
    assert answers["kits"] == [], "a refused decisions kit stayed in the spool"


# ------------- §43: what a report holds, the gate's timeout and the wait rule

#: §43 "H-070 and H-071, built": what a per-commit sub-agent's report holds, and
#: what the hosted-review sub-agent's holds, in both protocol files, flattened.
PROTOCOL_43_REPORTS = {
    "per-commit": "5. Reports the sha, a verdict per point and what is not proven.",
    "hosted-review": (
        "It reports the sha, a verdict per point and what is not proven, and every"
        " finding verbatim with its verdict on the builder's disposition"
    ),
}

#: §43 rule 6, the wait rule's three parts, word for word where §43 quotes them;
#: each file then names its timeout (`WAIT_TIMEOUT`).
WAIT_RULE = {
    "a-prevent": (
        "(a) prevent — a project whose gate can run past its role's"
        " `BASH_MAX_TIMEOUT_MS` raises `BASH_DEFAULT_TIMEOUT_MS` and"
        " `BASH_MAX_TIMEOUT_MS` above its worst case, and its briefs name that"
        " timeout"
    ),
    "b-exit-marker": (
        "(b) a long command ends with an exit marker,"
        ' `./scripts/check; echo "check-exit=$?"`, so its end shows in its output'
    ),
    "c-blocking-wait": (
        "(c) if a run is moved to the background anyway, wait with one foreground"
        " command that blocks until the output file shows the marker —"
        " `until grep -q '^check-exit=' <file>; do sleep 5; done`, with an explicit"
        " timeout — never a `sleep` of 25 seconds or more as a command's first"
        " statement, never Monitor or a background task, and never end the turn"
        " before the run has finished"
    ),
}

#: The timeout each file writes, as §43 gives it: 15 minutes in this repository's
#: protocol, the project's briefs' timeout in the protocol template and the
#: handbook, a placeholder the brief fills in the brief template.
WAIT_TIMEOUT = {
    "meta/REVIEW-PROTOCOL.md": "the gate's timeout, 15 minutes (900000 ms)",
    "templates/REVIEW-PROTOCOL.md": (
        "the gate's timeout, the timeout the project's briefs name (hands' default"
        " 15 minutes)"
    ),
    "templates/BUILDER-N-PROMPT.md": "the gate's timeout, `<the gate's timeout, in ms>`",
    "docs/ARCHITECT-HANDBOOK.md": (
        "the gate's timeout, the timeout the project's briefs name (hands' default"
        " 15 minutes)"
    ),
}

PROTOCOLS = ("templates/REVIEW-PROTOCOL.md", "meta/REVIEW-PROTOCOL.md")


def _flat(rel: str) -> str:
    path = Path(__file__).resolve().parents[1] / rel
    return " ".join(path.read_text(encoding="utf-8").split())


def _brief_sub_agent_block() -> str:
    text = _flat("templates/BUILDER-N-PROMPT.md")
    return text.split("## Sub-agent brief", 1)[1].split("## §R Recovery brief", 1)[0]


def _handbook_section_7() -> str:
    return _flat("docs/ARCHITECT-HANDBOOK.md").split("## 7. The review protocol", 1)[1].split(
        "## 8. ", 1
    )[0]


@pytest.mark.parametrize("key", sorted(PROTOCOL_43_REPORTS))
@pytest.mark.parametrize("rel", PROTOCOLS)
def test_both_protocols_say_what_a_report_holds(rel: str, key: str) -> None:
    said = PROTOCOL_43_REPORTS[key]
    assert said in strip_paths(_flat(rel)), f"{rel} does not say {said!r}"


@pytest.mark.parametrize("rel", PROTOCOLS)
def test_both_protocols_drop_the_twelve_line_count_and_the_20_minute_cap(rel: str) -> None:
    text = _flat(rel)
    for gone in ("≤12 lines", "≤12-line", "20-minute", "twelve lines"):
        assert gone not in strip_paths(text), f"{rel} still says {gone!r}"


@pytest.mark.parametrize("rel", PROTOCOLS)
def test_both_protocols_run_one_gate_at_a_time_inside_the_gates_timeout(rel: str) -> None:
    text = _flat(rel)
    timeout = WAIT_TIMEOUT[rel]
    assert f"one run at a time fits inside {timeout}" in strip_paths(text), rel
    assert f"runs at a time inside {timeout}." in strip_paths(text), rel


def _wait_rule_places() -> dict[str, str]:
    """Each place §43 rule 6 writes the wait rule, by name, as its flattened text."""
    places = {}
    for rel in PROTOCOLS:
        text = _flat(rel)
        hosted = text.split("## The hosted review", 1)[1]
        hosted = hosted.split("## The per-commit sub-agents", 1)[0]
        per_commit = text.split("## The per-commit sub-agents", 1)[1]
        per_commit = per_commit.split("## The review file", 1)[0]
        places[f"{rel} hosted-review sub-agent"] = hosted
        places[f"{rel} per-commit sub-agent"] = per_commit
    places["templates/BUILDER-N-PROMPT.md sub-agent brief"] = _brief_sub_agent_block()
    places["docs/ARCHITECT-HANDBOOK.md §7"] = _handbook_section_7()
    return places


@pytest.mark.parametrize("part", sorted(WAIT_RULE))
@pytest.mark.parametrize(
    "place",
    [
        f"{rel} {who}"
        for rel in PROTOCOLS
        for who in ("hosted-review sub-agent", "per-commit sub-agent")
    ]
    + ["templates/BUILDER-N-PROMPT.md sub-agent brief", "docs/ARCHITECT-HANDBOOK.md §7"],
)
def test_the_wait_rule_is_written_where_section_43_puts_it(place: str, part: str) -> None:
    text = _wait_rule_places()[place]
    said = WAIT_RULE[part]
    assert said in strip_paths(text), f"{place} does not say {said!r}"
    rel = place.split(" ", 1)[0]
    assert WAIT_TIMEOUT[rel] in strip_paths(text), f"{place} does not name {WAIT_TIMEOUT[rel]!r}"


def test_the_brief_template_keeps_its_twelve_lines() -> None:
    """§43: the brief template's sub-agent report keeps its twelve lines."""
    assert "report in ≤12 lines: sha, files, tests added, what is NOT proven" in (
        strip_paths(_brief_sub_agent_block())
    )


# ------------------------------- §43: a playbook change is the owner's (H-075)

#: §43: `[series] architect = "role"` with `autonomous = true`.
AUTONOMOUS_PLAYBOOK = ROLE_PLAYBOOK.replace(
    'architect = "role"\n', 'architect = "role"\nautonomous = true\n'
)


def _warns(out: str) -> list[str]:
    return [text for text in out.splitlines() if text.startswith("WARN playbook: ")]


def _owner_warns(out: str) -> list[str]:
    return [text for text in _warns(out) if "§43" in strip_paths(text)]


@pytest.mark.parametrize("whose", ["the repository's", "the kit's own"])
def test_kit_check_warns_when_a_kit_carries_a_playbook_under_an_autonomous_series(
    tmp_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, whose: str
) -> None:
    """§43: `hands kit check` prints a `WARN playbook:` line for a kit that carries a
    playbook when the repository's playbook in force before the apply, or the kit's
    own, sets `architect = "role"` with `autonomous = true`: filed by the role, its
    apply waits for the human. A WARN fails no check."""
    monkeypatch.delenv("HANDS_PROJECT", raising=False)
    _config(tmp_home, tmp_path, architect=True)
    repo_book, kit_book = (
        (AUTONOMOUS_PLAYBOOK, PLAYBOOK) if whose == "the repository's"
        else (PLAYBOOK, AUTONOMOUS_PLAYBOOK)
    )
    repo = write_tree(
        tmp_path / "repo", {"PLAYBOOK.toml": repo_book, "meta/REVIEW-PROTOCOL.md": PROTOCOL}
    )
    kit = write_tree(tmp_path / "k", {**good_kit(), "PLAYBOOK.toml": kit_book})
    code, out, _ = run_check(kit, repo)
    assert code == 0, out
    [warn] = _owner_warns(out)
    said = strip_paths(warn)
    assert "the kit carries PLAYBOOK.toml" in strip_paths(said), said
    assert f"{whose.replace(' own', '')} PLAYBOOK.toml" in strip_paths(said), said
    assert 'architect = "role"' in strip_paths(said), said
    assert "autonomous = true" in strip_paths(said), said
    assert "waits for the human" in strip_paths(said), said
    assert "kit check: pass (6 of 6 checks)" in strip_paths(out), out


def test_kit_check_warns_for_a_kit_carrying_meta_playbook_toml(
    tmp_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§43: the paths are the two `hands kit check` reads (§26)."""
    monkeypatch.delenv("HANDS_PROJECT", raising=False)
    _config(tmp_home, tmp_path, architect=True)
    repo = write_tree(
        tmp_path / "repo",
        {"meta/PLAYBOOK.toml": AUTONOMOUS_PLAYBOOK, "meta/REVIEW-PROTOCOL.md": PROTOCOL},
    )
    kit = write_tree(
        tmp_path / "k",
        {"meta/BUILDER-11-PROMPT.md": BRIEF, "meta/PLAYBOOK.toml": PLAYBOOK},
    )
    code, out, _ = run_check(kit, repo)
    assert code == 0, out
    [warn] = _owner_warns(out)
    said = strip_paths(warn)
    assert "the kit carries meta/PLAYBOOK.toml" in strip_paths(said), said
    assert "the repository's meta/PLAYBOOK.toml" in strip_paths(said), said


@pytest.mark.parametrize("case", ["a kit that carries no playbook", "all in phone mode"])
def test_kit_check_does_not_warn_of_the_owner_without_a_playbook_or_autonomy(
    tmp_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    """§43: no WARN for a kit that carries no playbook (its apply is the engine's to
    approve), even under an autonomous repository playbook; none for a kit whose
    playbook and the repository's are both judged in phone mode."""
    monkeypatch.delenv("HANDS_PROJECT", raising=False)
    _config(tmp_home, tmp_path, architect=True)
    if case == "a kit that carries no playbook":
        repo_book, kit_files = AUTONOMOUS_PLAYBOOK, {"meta/BUILDER-11-PROMPT.md": BRIEF}
    else:
        repo_book, kit_files = PLAYBOOK, good_kit()
    repo = write_tree(
        tmp_path / "repo", {"PLAYBOOK.toml": repo_book, "meta/REVIEW-PROTOCOL.md": PROTOCOL}
    )
    code, out, _ = run_check(write_tree(tmp_path / "k", kit_files), repo)
    assert code == 0, out
    assert _owner_warns(out) == [], out


def test_the_role_mode_missions_templates_warn_of_the_owner_and_pass_six_of_six(
    tmp_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§43: a kit from the filled missions templates with the architect blocks
    uncommented carries an autonomous playbook: `kit check` passes it 6 of 6 and
    prints the owner's WARN; the phone-mode templates print none."""
    monkeypatch.delenv("HANDS_PROJECT", raising=False)
    _config(tmp_home, tmp_path, architect=True)
    lines, inside = [], False
    for text in template("PLAYBOOK-missions.toml").splitlines():
        if text.strip() in ("# >>> architect", "# <<< architect"):
            inside = text.strip() == "# >>> architect"
            continue
        lines.append(text[2:] if inside and text.startswith("# ") else text)
    repo = write_tree(tmp_path / "repo", {"README.md": "x"})
    for name, book, warned in (
        ("role", "\n".join(lines) + "\n", 1),
        ("phone", template("PLAYBOOK-missions.toml"), 0),
    ):
        kit = write_tree(
            tmp_path / name,
            {
                "meta/BUILDER-11-PROMPT.md": template("BUILDER-N-PROMPT.md"),
                "PLAYBOOK.toml": book,
                "meta/REVIEW-PROTOCOL.md": template("REVIEW-PROTOCOL.md"),
            },
        )
        code, out, err = run_check(kit, repo)
        assert code == 0, out + err
        assert "kit check: pass (6 of 6 checks)" in strip_paths(out), out
        assert len(_owner_warns(out)) == warned, (name, out)


# ---- §44 "H-077, ruled": the playbook in any letter case, and at the configured path


def _configured(tmp_home: Path, tmp_path: Path, path: str) -> None:
    """A project configuration with the architect role and `[playbook] path`."""
    config = _config(tmp_home, tmp_path, architect=True)
    with config.open("a", encoding="utf-8") as out:
        out.write(f'\n[playbook]\npath = "{path}"\n')


@pytest.mark.parametrize(
    "entry", ["playbook.toml", "Playbook.toml", "meta/playbook.toml", "Meta/PLAYBOOK.toml"]
)
@pytest.mark.parametrize("configured", [True, False], ids=["configured", "no configuration"])
def test_kit_check_warns_for_a_playbook_entry_in_another_letter_case(
    tmp_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, entry: str,
    configured: bool,
) -> None:
    """§44: an entry carries the playbook when its casefolded path equals a fixed name
    casefolded, by the engine's one test; the WARN names the entry. The `playbook`
    check is unchanged: it loads only an entry at a fixed name, so the repo's playbook
    is the one judged and the kit passes. Without a project configuration the WARN
    says kit check knows only the two fixed names; with one it names what it knows."""
    monkeypatch.delenv("HANDS_PROJECT", raising=False)
    if configured:
        _config(tmp_home, tmp_path, architect=True)
    repo = write_tree(
        tmp_path / "repo",
        {"PLAYBOOK.toml": AUTONOMOUS_PLAYBOOK, "meta/REVIEW-PROTOCOL.md": PROTOCOL},
    )
    kit = write_tree(tmp_path / "k", {"meta/BUILDER-11-PROMPT.md": BRIEF, entry: PLAYBOOK})
    code, out, _ = run_check(kit, repo)
    assert code == 0, out
    assert "the repo's PLAYBOOK.toml is in force" in strip_paths(line(out, "playbook")), out
    [warn] = _owner_warns(out)
    said = strip_paths(warn)
    assert f"the kit carries {entry}, and the repository's PLAYBOOK.toml sets" in said, said
    only = (
        "with no project configuration to name a [playbook] path, kit check knows only "
        "PLAYBOOK.toml and meta/PLAYBOOK.toml, in any letter case (§44)"
    )
    known = "kit check knows PLAYBOOK.toml and meta/PLAYBOOK.toml, in any letter case (§44)"
    assert said.endswith("; " + (known if configured else only)), said


@pytest.mark.parametrize("entry", ["ops/rules.toml", "OPS/Rules.toml"])
def test_kit_check_warns_for_the_configured_playbook_path_judging_the_repos_there(
    tmp_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, entry: str
) -> None:
    """§44: under `[playbook] path = "ops/rules.toml"` an entry at that path, in any
    letter case, carries the playbook; the WARN is given because the repository's
    playbook at `ops/rules.toml` is role mode with autonomy (its `PLAYBOOK.toml`, and
    the kit's own, are phone mode), and names the configured path among those known.
    Without that configuration the same kit draws no owner's WARN."""
    monkeypatch.delenv("HANDS_PROJECT", raising=False)
    repo = write_tree(
        tmp_path / "repo",
        {
            "PLAYBOOK.toml": PLAYBOOK,
            "ops/rules.toml": AUTONOMOUS_PLAYBOOK,
            "meta/REVIEW-PROTOCOL.md": PROTOCOL,
        },
    )
    kit = write_tree(tmp_path / "k", {"meta/BUILDER-11-PROMPT.md": BRIEF, entry: PLAYBOOK})
    _config(tmp_home, tmp_path, architect=True)
    code, out, _ = run_check(kit, repo)
    assert code == 0, out
    assert _owner_warns(out) == [], out
    _configured(tmp_home, tmp_path, "ops/rules.toml")
    code, out, _ = run_check(kit, repo)
    assert code == 0, out
    [warn] = _owner_warns(out)
    said = strip_paths(warn)
    assert said.startswith(
        f"WARN playbook: the kit carries {entry}, and the repository's ops/rules.toml sets "
        '[series] architect = "role" with autonomous = true'
    ), said
    assert said.endswith(
        "; kit check knows ops/rules.toml, PLAYBOOK.toml and meta/PLAYBOOK.toml, in any "
        "letter case (§44)"
    ), said


def test_the_daemons_kit_check_from_a_builder_cwd_below_the_root_warns_for_the_configured_path(
    tmp_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mission 28 U5, PR #8 hosted finding 5 (§44 "H-077, ruled", §38): handsd's
    `kit_file` runs `check_kit` with the builder's cwd as its repo argument. With that
    cwd at `sub/dir` below the repository root and `[playbook] path = "ops/rules.toml"`
    (the repository path `sub/dir/ops/rules.toml`), a kit carrying that entry draws the
    owner's WARN because the repository's playbook there is role mode with autonomy —
    the configured path is resolved against the repository root, not joined beneath
    the cwd a second time."""
    from conftest import commit_file
    from hands.config import load_config

    monkeypatch.delenv("HANDS_PROJECT", raising=False)
    root = tmp_path / "root"
    commit_file(root, "sub/dir/ops/rules.toml", AUTONOMOUS_PLAYBOOK)
    commit_file(root, "sub/dir/meta/REVIEW-PROTOCOL.md", PROTOCOL)
    cwd = root / "sub" / "dir"
    architect = tmp_path / "hands-architect"
    architect.mkdir()
    (tmp_home / ".hands" / "demo.toml").write_text(
        f'[roles.builder]\ncwd = "{cwd}"\n\n[roles.architect]\ncwd = "{architect}"\n'
        '\n[playbook]\npath = "ops/rules.toml"\n',
        encoding="utf-8",
    )
    kit = write_tree(
        tmp_path / "k",
        {"meta/BUILDER-11-PROMPT.md": BRIEF, "sub/dir/ops/rules.toml": PLAYBOOK},
    )
    report = kit_mod.check_kit(kit, cwd, config=load_config("demo"))
    owner = [text for text in report.warnings if "§43" in strip_paths(text)]
    assert len(owner) == 1, report.warnings
    said = strip_paths(owner[0])
    assert said.startswith(
        "the kit carries sub/dir/ops/rules.toml, and the repository's sub/dir/ops/rules.toml "
        'sets [series] architect = "role" with autonomous = true'
    ), said


def test_an_ordinary_kit_is_unchanged_under_a_configured_playbook_path(
    tmp_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§44: a kit that carries no playbook draws no owner's WARN under a configured
    path whose repository playbook is autonomous, and passes as before."""
    monkeypatch.delenv("HANDS_PROJECT", raising=False)
    _configured(tmp_home, tmp_path, "ops/rules.toml")
    repo = write_tree(
        tmp_path / "repo",
        {
            "PLAYBOOK.toml": AUTONOMOUS_PLAYBOOK,
            "ops/rules.toml": AUTONOMOUS_PLAYBOOK,
            "meta/REVIEW-PROTOCOL.md": PROTOCOL,
        },
    )
    kit = write_tree(tmp_path / "k", {"meta/BUILDER-11-PROMPT.md": BRIEF})
    code, out, _ = run_check(kit, repo)
    assert code == 0, out
    assert _owner_warns(out) == [], out
    assert "kit check: pass (6 of 6 checks)" in strip_paths(out), out


@pytest.mark.parametrize(
    "name", ["templates/PLAYBOOK-missions.toml", "templates/BUILDER-N-PROMPT.md"]
)
def test_the_role_mode_templates_name_a_kickoff_that_never_changes(name: str) -> None:
    """§43: "a series in role mode needs a kickoff line that never changes", stated
    in the role-mode templates: a kickoff that names the mission would need a
    playbook in every kit, and every kit would wait for the human."""
    text = " ".join(strip_paths((ROOT / name).read_text(encoding="utf-8")).split())
    flat = text.replace("# ", "")
    assert (
        "Read the builder prompt with the highest mission number in the meta directory "
        "and execute the mission below its divider." in strip_paths(flat)
    ), name
    assert "never changes" in strip_paths(flat), name
    assert "wait for the human" in strip_paths(flat), name


def test_the_missions_template_says_the_kit_applied_rule_fires_for_a_human_approval() -> None:
    """§43: the missions playbook template's comment on the `kit applied` rule says it
    fires for an apply the human approved."""
    text = " ".join(
        strip_paths((TEMPLATES / "PLAYBOOK-missions.toml").read_text(encoding="utf-8"))
        .replace("# ", "").split()
    )
    assert "series this rule does not fire" not in strip_paths(text), text
    assert "fires for an apply the human approved" in strip_paths(text), text


def _rule(text: str, number: int) -> str:
    start = text.index(f"\n{number}. ")
    return " ".join(text[start:text.index(f"\n{number + 1}. ", start)].split())


def test_architect_rules_3_and_8_make_a_playbook_change_the_owners() -> None:
    """§43: `architect/CLAUDE.md` rule 3 no longer lists `PLAYBOOK.toml` among a
    kit's entries, and rule 8 says a change of the playbook is the shape the human
    approved at the switch point."""
    text = strip_paths((ROOT / "architect" / "CLAUDE.md").read_text(encoding="utf-8"))
    assert "PLAYBOOK.toml" not in strip_paths(_rule(text, 3).replace("never `PLAYBOOK.toml`", ""))
    eight = _rule(text, 8)
    assert "a change of the playbook" in strip_paths(eight), eight
    assert "the shape the human approved at the switch point" in strip_paths(eight), eight


@pytest.mark.parametrize("section", ["## 3. ", "## 6. ", "## 12. "])
def test_the_handbook_says_a_playbook_change_is_the_owners(section: str) -> None:
    """§43: the handbook's §3, §6 and §12 say a change of the playbook is the
    owner's, and that a role-filed kit carrying it waits for the human."""
    handbook = strip_paths((ROOT / "docs" / "ARCHITECT-HANDBOOK.md").read_text(encoding="utf-8"))
    start = handbook.index("\n" + section)
    end = handbook.index("\n## ", start + 1)
    text = " ".join(handbook[start:end].split())
    assert "the owner's" in strip_paths(text), section
    assert "waits for the human" in strip_paths(text), section
