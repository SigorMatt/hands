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
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    serve(monkeypatch, FIXTURES / "first")
    code, out, err = run("3", "--bot", "some-human")
    assert code == 3, err  # bodies archived, but no verdict to read yet
    archive = repo / "meta" / "reviews" / "hosted" / "PR-3" / "1"
    assert sorted(path.name for path in archive.glob("*.md")) == [
        "issue-comment-7001.md", "review-5002.md"
    ]
    # CRLF and all: the bytes the API gave
    assert (archive / "issue-comment-7001.md").read_bytes() == (
        b"Thanks, looking.\r\nTrailing CRLF kept.\r\n"
    )
    assert "no Code Review comment" in strip_paths(out)


def test_a_failed_fetch_writes_nothing_and_exits_1(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    serve(monkeypatch, FIXTURES / "first")
    monkeypatch.setenv("FAKE_GH_MODE", "apifail")
    code, out, err = run("3")
    assert code == 1
    assert "HTTP 502" in strip_paths(err)
    assert not (repo / "meta").exists()
