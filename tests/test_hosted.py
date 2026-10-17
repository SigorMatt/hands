"""DESIGN §39 "The hosted review, read mechanically" (§35; docs/QODO-EXTRACTION.md).

`hands hosted-review <pr>` fetches the pull request's issue comments, reviews
and review comments, every page, from a fake `gh` on PATH (tests/fake_gh.py)
serving the recorded pages under tests/fixtures/hosted/; `first/` is the bot's
first review of PR #3 and `edited/` the same PR after a push, with the Code
Review comment edited in place.
"""

from __future__ import annotations

import io
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from conftest import strip_paths
from hands.cli import main as hands_main

FIXTURES = Path(__file__).parent / "fixtures" / "hosted"
BOT = "qodo-code-review[bot]"
SOURCES = {
    "issues-3-comments": "issue-comment",
    "pulls-3-reviews": "review",
    "pulls-3-comments": "review-comment",
}


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A local repository; the command runs in a subdirectory of it, so the
    archive's place is proved to be the repository root, not the cwd."""
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    monkeypatch.chdir(root / "src")
    monkeypatch.setenv("FAKE_GH_API_LOG", str(tmp_path / "gh.log"))
    return root


def serve(monkeypatch: pytest.MonkeyPatch, directory: Path) -> None:
    monkeypatch.setenv("FAKE_GH_API_DIR", str(directory))


def run(*argv: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    code = hands_main(["hosted-review", *argv], stdout=out, stderr=err)
    return code, out.getvalue(), err.getvalue()


def recorded(directory: Path) -> dict[str, list[dict]]:
    """Every object the recorded pages carry, by source."""
    found: dict[str, list[dict]] = {}
    for stem in SOURCES:
        for page in sorted(directory.glob(f"{stem}.page-*.json")):
            found.setdefault(stem, []).extend(json.loads(page.read_text(encoding="utf-8")))
    return found


def test_first_fetch_archives_every_bot_body_byte_for_byte_and_prints_the_review(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    serve(monkeypatch, FIXTURES / "first")
    code, out, err = run("3")
    assert code == 0, err
    archive = repo / "meta" / "reviews" / "hosted" / "PR-3" / "1"
    assert archive.is_dir()
    expected = set()
    for stem, objects in recorded(FIXTURES / "first").items():
        for obj in objects:
            body = archive / f"{SOURCES[stem]}-{obj['id']}.md"
            raw = archive / f"{SOURCES[stem]}-{obj['id']}.json"
            if obj["user"]["login"] != BOT:
                assert not body.exists() and not raw.exists(), body
                continue
            expected |= {body.name, raw.name}
            assert body.read_bytes() == (obj["body"] or "").encode("utf-8")
            assert json.loads(raw.read_text(encoding="utf-8")) == obj
    assert {path.name for path in archive.iterdir()} == expected
    assert len(expected) == 2 * 6  # two issue comments, one review, three inline

    assert "summary comment: issue-comment 6001" in strip_paths(out)
    assert "code review comment: issue-comment 6002" in strip_paths(out)
    for category in ("🐞 Bugs (1)", "📘 Rule violations (1)", "🔗 Cross-repo conflicts (1)",
                     "📜 Skill insights (0)"):
        assert f"\n  {category}\n" in strip_paths(out), category
    assert ("  1.  A failed load leaves the widget half-built <code>🐞 Bug</code> "
            "<code>☼ Reliability</code>\n      at src/widget/loader.py:40-46\n") in strip_paths(out)
    assert "  2.  The report hides its verdict" in strip_paths(out)
    assert "      at meta/REPORT.md:1-3\n" in strip_paths(out)
    assert "  3.  The sibling repository expects the old name" in strip_paths(out)
    assert "      at src/widget/names.py:12\n" in strip_paths(out)
    # the inline duplicate of finding 1 is named with its anchor
    assert "      inline: review-comment 4002 at src/widget/loader.py:46\n" in strip_paths(out)
    assert "<b><i>load</i></b> writes the cache before the fetch succeeds." in strip_paths(out)
    assert "verdict: 3 of 3 findings open in the Code Review comment" in strip_paths(out)
    assert "previous" not in strip_paths(out)


def test_a_second_fetch_after_an_in_place_edit_prints_the_diff_by_comment_id(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    serve(monkeypatch, FIXTURES / "first")
    assert run("3")[0] == 0
    first = repo / "meta" / "reviews" / "hosted" / "PR-3" / "1"
    before = {path.name: path.read_bytes() for path in first.iterdir()}

    serve(monkeypatch, FIXTURES / "edited")
    code, out, err = run("3")
    assert code == 0, err
    second = first.parent / "2"
    assert second.is_dir()
    assert {path.name: path.read_bytes() for path in first.iterdir()} == before
    edited = recorded(FIXTURES / "edited")["issues-3-comments"][-1]
    assert (second / "issue-comment-6002.md").read_bytes() == edited["body"].encode("utf-8")

    assert "diff against 1:" in strip_paths(out)
    assert ("  changed: issue-comment 6002 updated_at 2026-10-15T15:09:40Z -> "
            "2026-10-15T16:52:23Z\n") in strip_paths(out)
    rest = "<code>📘 Rule violations (1)</code>  <code>🔗 Cross-repo conflicts (1)</code>  " \
        "<code>📜 Skill insights (0)</code>\n"
    assert f"    -<code>🐞 Bugs (1)</code>  {rest}" in strip_paths(out)
    assert f"    +<code>🐞 Bugs (0)</code>  {rest}" in strip_paths(out)
    struck = "<s>A failed load leaves the widget half-built</s> ✓ Resolved"
    assert f"    +<summary>  1.  {struck}" in strip_paths(out)
    assert "  added: review-comment 4004\n" in strip_paths(out)
    assert "  vanished: review-comment 4003\n" in strip_paths(out)
    # unchanged bodies are not listed as changed
    assert "changed: issue-comment 6001" not in strip_paths(out)
    assert "changed: review-comment 4001" not in strip_paths(out)
    assert "  resolved since 1: 1.  A failed load leaves the widget half-built" in strip_paths(out)
    assert "  1.  <s>A failed load leaves the widget half-built</s> ✓ Resolved" in strip_paths(out)
    assert "      resolved\n" in strip_paths(out)
    assert "verdict: 2 of 3 findings open in the Code Review comment" in strip_paths(out)
    # the open ones are named; the resolved one is not among them
    verdict = out.split("verdict:")[1]
    assert "2.  The report hides its verdict" in strip_paths(verdict)
    assert "A failed load" not in strip_paths(verdict)


def test_every_finding_resolved_says_none_is_open(
    repo: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    pages = tmp_path / "pages"
    shutil.copytree(FIXTURES / "edited", pages)
    page = pages / "issues-3-comments.page-2.json"
    data = json.loads(page.read_text(encoding="utf-8"))
    for title in ("The report hides its verdict", "The sibling repository expects the old name"):
        data[0]["body"] = data[0]["body"].replace(f"  {title} ", f"  <s>{title}</s> ✓ Resolved ")
    # the bot resets the header counts as it strikes findings (docs/QODO-EXTRACTION.md)
    for label in ("Rule violations", "Cross-repo conflicts"):
        data[0]["body"] = data[0]["body"].replace(f"{label} (1)", f"{label} (0)")
    page.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    serve(monkeypatch, pages)
    code, out, err = run("3")
    assert code == 0, err
    assert "verdict: no finding open in the Code Review comment (3 resolved)" in strip_paths(out)


def test_no_bot_comment_yet_exits_3_and_writes_nothing(
    repo: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    pages = tmp_path / "pages"
    pages.mkdir()
    first = recorded(FIXTURES / "first")
    human = [obj for obj in first["issues-3-comments"] if obj["user"]["login"] != BOT]
    (pages / "issues-3-comments.page-1.json").write_text(json.dumps(human), encoding="utf-8")
    serve(monkeypatch, pages)
    code, out, err = run("3")
    assert code == 3, (out, err)
    assert "no bot comment yet" in strip_paths(out)
    assert "verdict" not in strip_paths(out)
    assert not (repo / "meta").exists()


def test_every_page_of_every_source_is_read(
    repo: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    serve(monkeypatch, FIXTURES / "first")
    assert run("3")[0] == 0
    calls = (tmp_path / "gh.log").read_text(encoding="utf-8").splitlines()
    for source in ("issues/3/comments", "pulls/3/reviews", "pulls/3/comments"):
        pages = [call for call in calls if f"/{source}?" in call]
        last = 3 if source != "pulls/3/reviews" else 2  # up to the first empty page
        assert [call.rsplit("page=", 1)[1] for call in pages] == [
            str(n) for n in range(1, last + 1)
        ], (source, calls)
    archive = repo / "meta" / "reviews" / "hosted" / "PR-3" / "1"
    # the comments that are only on a second page
    assert (archive / "issue-comment-6002.md").is_file()
    assert (archive / "review-comment-4003.md").is_file()


def test_a_category_never_seen_before_is_printed(
    repo: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    pages = tmp_path / "pages"
    shutil.copytree(FIXTURES / "first", pages)
    page = pages / "issues-3-comments.page-2.json"
    text = page.read_text(encoding="utf-8")
    assert text.count("📜 Skill insights (0)") == 1  # the fixture page, not printed text
    page.write_text(text.replace("📜 Skill insights (0)", "🛰 Orbital hazards (2)"),
                    encoding="utf-8")
    serve(monkeypatch, pages)
    code, out, err = run("3")
    assert code == 0, err
    assert "\n  🛰 Orbital hazards (2)\n" in strip_paths(out)
    assert "\n  🔗 Cross-repo conflicts (1)\n" in strip_paths(out)


def test_bot_flag_changes_the_login_filtered_to(
    repo: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    pages = tmp_path / "pages"
    shutil.copytree(FIXTURES / "first", pages)
    page = pages / "issues-3-comments.page-1.json"
    data = json.loads(page.read_text(encoding="utf-8"))
    (human,) = [obj for obj in data if obj["id"] == 7001]
    human["body"] = "<h3>Code Review by some-human</h3>\r\n" + human["body"]
    page.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    serve(monkeypatch, pages)
    code, out, err = run("3", "--bot", "some-human")
    assert code == 0, err
    archive = repo / "meta" / "reviews" / "hosted" / "PR-3" / "1"
    assert sorted(path.name for path in archive.glob("*.md")) == [
        "issue-comment-7001.md", "review-5002.md"
    ]
    # CRLF and all: the bytes the API gave
    assert (archive / "issue-comment-7001.md").read_bytes() == (
        b"<h3>Code Review by some-human</h3>\r\nThanks, looking.\r\nTrailing CRLF kept.\r\n"
    )
    assert "code review comment: issue-comment 7001" in strip_paths(out)


def test_a_bot_comment_without_the_code_review_comment_exits_3_and_writes_nothing(
    repo: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """PR #4 hosted review, "Each wait-loop retry writes another archive": the bot
    has posted its summary but not yet its Code Review comment — a state to wait on,
    so nothing is written, however often the wait loop runs the command."""
    pages = tmp_path / "pages"
    shutil.copytree(FIXTURES / "first", pages)
    page = pages / "issues-3-comments.page-2.json"
    data = [obj for obj in json.loads(page.read_text(encoding="utf-8")) if obj["id"] != 6002]
    page.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    serve(monkeypatch, pages)
    for _ in range(3):
        code, out, err = run("3")
        assert code == 3, (out, err)
        assert "the Code Review comment is not there yet" in strip_paths(out)
        assert "nothing written" in strip_paths(out)
        assert not (repo / "meta").exists()
    # the same with --bot naming a login that has comments but no Code Review one
    serve(monkeypatch, FIXTURES / "first")
    code, out, err = run("3", "--bot", "some-human")
    assert code == 3, (out, err)
    assert not (repo / "meta").exists()


def test_a_failed_archive_leaves_no_fetch_behind(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """PR #4 hosted review, "A failed archive leaves a false review fetch": a write
    that fails after the first body is written leaves no `<k>` and no partial
    directory, and the next run numbers and diffs as if it never happened."""
    serve(monkeypatch, FIXTURES / "first")
    real = Path.write_text

    def failing(self: Path, *args: object, **kwargs: object) -> int:
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(Path, "write_text", failing)
    code, out, err = run("3")
    assert code == 1, (out, err)
    assert "No space left on device" in strip_paths(err)
    base = repo / "meta" / "reviews" / "hosted" / "PR-3"
    assert not base.exists() or list(base.iterdir()) == []
    monkeypatch.setattr(Path, "write_text", real)
    code, out, err = run("3")
    assert code == 0, err
    assert sorted(path.name for path in base.iterdir()) == ["1"]
    assert "diff against" not in strip_paths(out)


def test_a_title_with_the_word_resolved_stays_open(
    repo: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """PR #4 hosted review, "A finding titled with 'Resolved' counts as fixed":
    resolved is struck through or the bot's `✓ Resolved` mark, never the word."""
    pages = tmp_path / "pages"
    shutil.copytree(FIXTURES / "first", pages)
    page = pages / "issues-3-comments.page-2.json"
    text = page.read_text(encoding="utf-8")
    assert text.count("The report hides its verdict") == 1
    page.write_text(text.replace("The report hides its verdict",
                                 "Resolved paths escape the root"), encoding="utf-8")
    serve(monkeypatch, pages)
    code, out, err = run("3")
    assert code == 0, err
    assert "verdict: 3 of 3 findings open in the Code Review comment" in strip_paths(out)
    assert "      resolved\n" not in strip_paths(out)
    assert "2.  Resolved paths escape the root" in strip_paths(out.split("verdict:")[1])


def _renumber(body: str, numbers: str) -> str:
    """`body` with the numbered `<summary>` of each finding in `numbers` wrapped in
    `<b>` — a markup change the finding parser does not read."""
    return re.sub(rf"<summary>(\s*)([{numbers}])\.", r"<summary>\1<b>\2</b>.", body)


def test_header_counts_with_no_parsed_finding_is_no_clean_review(
    repo: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """PR #4 hosted review, "A misparsed Code Review reads as a clean review": the
    header counts three findings, none parses — no clean verdict, exit 4."""
    pages = tmp_path / "pages"
    shutil.copytree(FIXTURES / "first", pages)
    page = pages / "issues-3-comments.page-2.json"
    data = json.loads(page.read_text(encoding="utf-8"))
    data[0]["body"] = _renumber(data[0]["body"], "123")
    page.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    serve(monkeypatch, pages)
    code, out, err = run("3")
    assert code == 4, (out, err)
    assert "no finding open" not in strip_paths(out)
    assert ("verdict: the findings could not be parsed against the header counts "
            "(the header counts 3, 0 parsed, 0 open)") in strip_paths(out)


def test_a_parsed_count_short_of_the_header_is_said(
    repo: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    pages = tmp_path / "pages"
    shutil.copytree(FIXTURES / "first", pages)
    page = pages / "issues-3-comments.page-2.json"
    data = json.loads(page.read_text(encoding="utf-8"))
    data[0]["body"] = _renumber(data[0]["body"], "3")
    page.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    serve(monkeypatch, pages)
    code, out, err = run("3")
    assert code == 0, err
    assert ("header counts 3 findings, but 2 parsed (2 open): read the Code Review "
            "comment itself") in strip_paths(out)
    assert "verdict: 2 of 2 findings open in the Code Review comment" in strip_paths(out)


def test_the_header_and_the_parse_agreeing_says_nothing_more(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    serve(monkeypatch, FIXTURES / "edited")  # header reset to 2, three numbered, 2 open
    code, out, err = run("3")
    assert code == 0, err
    assert "but" not in strip_paths(out.split("findings:")[0])
    assert "header counts" not in strip_paths(out)


def test_an_inline_comment_matches_its_finding_whatever_the_case(
    repo: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """PR #4: the inline copies of findings 8 and 9 differed from their titles only in
    case (and an HTML-escaped quote) and were printed as matching no finding."""
    pages = tmp_path / "pages"
    shutil.copytree(FIXTURES / "first", pages)
    review = pages / "issues-3-comments.page-2.json"
    text = review.read_text(encoding="utf-8")
    review.write_text(text.replace("A failed load leaves the widget half-built",
                                   "A failed load leaves the &#x27;Widget&#x27; half-built"),
                      encoding="utf-8")
    inline = pages / "pulls-3-comments.page-1.json"
    text = inline.read_text(encoding="utf-8")
    inline.write_text(text.replace("A failed load leaves the widget half-built",
                                   "A failed load leaves the 'widget' half-built"),
                      encoding="utf-8")
    serve(monkeypatch, pages)
    code, out, err = run("3")
    assert code == 0, err
    assert "      inline: review-comment 4002 at src/widget/loader.py:46\n" in strip_paths(out)
    assert "no finding of that title: review-comment 4002" not in strip_paths(out)
    assert "inline comment with no finding of that title" not in strip_paths(out)


def test_a_failed_fetch_writes_nothing_and_exits_1(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    serve(monkeypatch, FIXTURES / "first")
    monkeypatch.setenv("FAKE_GH_MODE", "apifail")
    code, out, err = run("3")
    assert code == 1
    assert "HTTP 502" in strip_paths(err)
    assert not (repo / "meta").exists()


def test_the_help_names_both_exit_statuses(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        hands_main(["hosted-review", "--help"])
    text = " ".join(capsys.readouterr().out.split())
    assert "exit 3 with nothing written" in strip_paths(text)
    assert "Code Review comment is not there yet" in strip_paths(text)
    assert ("exit 4 when the header counts findings and none parsed is open (the findings "
            "could not be parsed against the header counts: no verdict)") in strip_paths(text)


def _code_review_body(directory: Path) -> str:
    return json.loads((directory / "issues-3-comments.page-2.json").read_text(
        encoding="utf-8"))[0]["body"]


@pytest.mark.parametrize(("stem", "decoy_id"), [
    ("pulls-3-reviews", 9001),   # a review whose body is headed "Code Review"
    ("pulls-3-comments", 9002),  # an inline comment headed "Code Review"
])
def test_the_verdict_comes_from_the_code_review_issue_comment_only(
    repo: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, stem: str, decoy_id: int
) -> None:
    """§39: "takes the verdict from the Code Review comment only" (REVIEW-23
    should-fix 3). A review body or an inline comment headed "Code Review", newer
    (higher id) than the Code Review issue comment and with every finding struck,
    is archived but never read for the verdict."""
    pages = tmp_path / "pages"
    shutil.copytree(FIXTURES / "first", pages)
    decoy = json.loads((pages / f"{stem}.page-1.json").read_text(encoding="utf-8"))[-1]
    decoy = {**decoy, "id": decoy_id, "body": _code_review_body(FIXTURES / "edited")
             .replace("The report hides its verdict",
                      "<s>The report hides its verdict</s> ✓ Resolved")
             .replace("The sibling repository expects the old name",
                      "<s>The sibling repository expects the old name</s> ✓ Resolved")
             .replace("(1)", "(0)")}
    assert decoy["user"]["login"] == BOT
    assert "<h3>Code Review by Qodo</h3>" in strip_paths(decoy["body"])
    page = pages / f"{stem}.page-1.json"
    data = json.loads(page.read_text(encoding="utf-8"))
    page.write_text(json.dumps([*data, decoy], ensure_ascii=False), encoding="utf-8")
    serve(monkeypatch, pages)
    code, out, err = run("3")
    assert code == 0, err
    kind = {"pulls-3-reviews": "review", "pulls-3-comments": "review-comment"}[stem]
    archive = repo / "meta" / "reviews" / "hosted" / "PR-3" / "1"
    assert (archive / f"{kind}-{decoy_id}.md").read_bytes() == decoy["body"].encode("utf-8")
    assert "code review comment: issue-comment 6002 " in strip_paths(out)
    assert "verdict: 3 of 3 findings open in the Code Review comment" in strip_paths(out)
    assert "no finding open" not in strip_paths(out)


def test_of_two_code_review_comments_the_newest_gives_the_verdict(
    repo: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """§39 (REVIEW-23 should-fix 3): two Code Review issue comments from the bot —
    the newer (6003, the edited reading: one of three struck) gives the verdict,
    not the older (6002, three open), which the API lists first."""
    pages = tmp_path / "pages"
    shutil.copytree(FIXTURES / "first", pages)
    page = pages / "issues-3-comments.page-2.json"
    data = json.loads(page.read_text(encoding="utf-8"))
    newer = {**data[0], "id": 6003, "created_at": "2026-10-15T16:52:23Z",
             "updated_at": "2026-10-15T16:52:23Z",
             "body": _code_review_body(FIXTURES / "edited")}
    page.write_text(json.dumps([*data, newer], ensure_ascii=False), encoding="utf-8")
    serve(monkeypatch, pages)
    code, out, err = run("3")
    assert code == 0, err
    assert "code review comment: issue-comment 6003 " in strip_paths(out)
    assert "code review comment: issue-comment 6002" not in strip_paths(out)
    assert "verdict: 2 of 3 findings open in the Code Review comment" in strip_paths(out)


def test_a_header_counting_one_whose_only_finding_is_struck_exits_4(
    repo: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """REVIEW-23 should-fix 4: the header counts one finding (the bot reset
    nothing) and the only finding parsed is struck through — every parsed finding
    resolved, none open against a count above zero: no clean verdict, exit 4."""
    pages = tmp_path / "pages"
    shutil.copytree(FIXTURES / "edited", pages)
    page = pages / "issues-3-comments.page-2.json"
    data = json.loads(page.read_text(encoding="utf-8"))
    body = data[0]["body"]
    head, rest = body.split("<details>\n<summary>  2.", 1)
    tail = "<!--" + rest.split("<!--", 1)[1]
    body = (head + tail).replace("Bugs (0)", "Bugs (1)")
    for label in ("Rule violations", "Cross-repo conflicts"):
        body = body.replace(f"{label} (1)", f"{label} (0)")
    data[0]["body"] = body
    page.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    serve(monkeypatch, pages)
    code, out, err = run("3")
    assert code == 4, (out, err)
    findings_part = out.split("findings:")[1]
    assert ("  1.  <s>A failed load leaves the widget half-built</s> ✓ Resolved"
            in strip_paths(findings_part))
    assert "  2.  " not in strip_paths(findings_part)
    assert "  3.  " not in strip_paths(findings_part)
    assert "no finding open" not in strip_paths(out)
    assert ("verdict: the findings could not be parsed against the header counts "
            "(the header counts 1, 1 parsed, 0 open)") in strip_paths(out)
