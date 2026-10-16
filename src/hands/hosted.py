"""`hands hosted-review <pr>`: the hosted review, read mechanically (DESIGN §39, §35).

The method is docs/QODO-EXTRACTION.md's. The bot posts three things on a pull
request: a summary issue comment with no findings, a "Code Review" issue comment
that is the canonical numbered list under header counts, and a `COMMENTED`
review with one inline comment per finding. After a push it edits the Code
Review comment in place and posts nothing new, so the reading is:

1. fetch the issue comments, the reviews and the review comments, every page
   (an explicit `page=` loop up to the first empty page), through `gh api`;
2. keep the bot's (`--bot`, default `qodo-code-review[bot]`); with none, or
   with no Code Review comment among them yet, say so, write nothing and exit
   3 — a state to wait on, never a clean review (PR #4 hosted review, finding
   10: a wait loop's retries must not pile up archives);
3. archive each body byte for byte (`<kind>-<id>.md`) with the comment's JSON
   (`<kind>-<id>.json`) under `meta/reviews/hosted/PR-<n>/<k>/` at the
   repository root, `k` one more than the highest already there — written into
   a hidden sibling directory and renamed to `<k>` only once complete, so a
   failed write leaves no `<k>` (finding 6);
4. print the Code Review comment's header categories as found, every numbered
   finding verbatim with its file:line anchor, the summary comment's id, the
   diff against the previous `k` by comment id, and the verdict — taken from
   the Code Review comment only, never from the inline comments. A header that
   counts findings while none parsed is open is no clean review: exit 4
   (finding 8); a parse whose open count differs from the header's is said.

Speaks a transport only through `gh`, as `hands doctor`'s `gh` row does.
"""

from __future__ import annotations

import difflib
import html
import json
import os
import re
import shutil
import subprocess
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TextIO

DEFAULT_BOT = "qodo-code-review[bot]"
#: §39: "no bot comment yet" (and no Code Review comment yet) is a state to wait on.
EXIT_NOT_YET = 3
#: The header counts findings, yet none parsed is open: no verdict can be read.
EXIT_UNPARSED = 4
PER_PAGE = 100
#: A loop that never meets an empty page is a broken `gh`, not a long review.
MAX_PAGES = 100
GH_TIMEOUT_S = 120

#: (endpoint under `repos/{owner}/{repo}/`, the kind that names its files)
SOURCES: tuple[tuple[str, str], ...] = (
    ("issues/{n}/comments", "issue-comment"),
    ("pulls/{n}/reviews", "review"),
    ("pulls/{n}/comments", "review-comment"),
)

_HEADING = re.compile(r"<h\d>([^<]*)</h\d>")
_CATEGORY = re.compile(r"<code>\s*([^<]*?\(\d+\))\s*</code>")
_FINDING = re.compile(r"<summary>[ \t]*(\d+)\.[ \t]+([^\n]*?)[ \t]*</summary>")
_DESCRIPTION = re.compile(r"<summary>Description</summary>.*?<pre>(.*?)</pre>", re.DOTALL)
_ANCHOR = re.compile(r"\[([^\[\]\s()]+?)\\?\[R?(\d+)(?:-R?(\d+))?\\?\]\]\(")
_INLINE_TITLE = re.compile(r"^[ \t]*(\d+)\\?\.[ \t]+(.+)$", re.MULTILINE)
#: Struck through, or the bot's `✓ Resolved` mark — never the bare word, which an
#: open finding's title can carry (PR #4 hosted review, finding 9).
_STRUCK = re.compile(r"<s>|<del>|<strike>|~~|✓\s*Resolved")
_COUNT = re.compile(r"\((\d+)\)\s*$")


class HostedError(Exception):
    """A fetch or the archive failed; nothing was written."""


@dataclass
class Finding:
    number: str
    title: str  # the summary line's text, verbatim
    anchor: str | None
    description: list[str]

    @property
    def resolved(self) -> bool:
        return bool(_STRUCK.search(self.title))

    @property
    def plain(self) -> str:
        return _plain(self.title)

    @property
    def key(self) -> str:
        """What pairs the finding with its inline comment: the plain title, case
        folded (on PR #4 two inline titles differed from theirs only in case)."""
        return self.plain.casefold()


def _plain(title: str) -> str:
    """A title without markup, code spans or the resolved mark: what pairs a
    finding across fetches and with its inline comment."""
    text = re.sub(r"<code>.*?</code>", "", title)
    text = re.sub(r"<[^>]+>", "", text).replace("~~", "")
    text = re.sub(r"✓\s*Resolved", "", html.unescape(text))
    return " ".join(text.replace("\\", "").split())


# ------------------------------------------------------------------ fetching


def _gh_page(endpoint: str, page: int, cwd: Path) -> list[dict[str, Any]]:
    path = f"repos/{{owner}}/{{repo}}/{endpoint}?per_page={PER_PAGE}&page={page}"
    try:
        done = subprocess.run(
            ["gh", "api", path], cwd=cwd, capture_output=True, text=True,
            encoding="utf-8", timeout=GH_TIMEOUT_S,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise HostedError(f"gh api {path}: {exc}") from exc
    if done.returncode != 0:
        raise HostedError(f"gh api {path} exited {done.returncode}: {done.stderr.strip()}")
    try:
        data = json.loads(done.stdout)
    except json.JSONDecodeError as exc:
        raise HostedError(f"gh api {path}: not JSON ({exc})") from exc
    if not isinstance(data, list):
        raise HostedError(f"gh api {path}: expected a list, got {type(data).__name__}")
    return data


def fetch(pr: int, bot: str, cwd: Path) -> list[tuple[str, dict[str, Any]]]:
    """Every comment of the three sources whose author is `bot`, as (kind, object),
    in the order the API gave them, every page read."""
    found: list[tuple[str, dict[str, Any]]] = []
    for template, kind in SOURCES:
        endpoint = template.format(n=pr)
        for page in range(1, MAX_PAGES + 1):
            objects = _gh_page(endpoint, page, cwd)
            if not objects:
                break
            for obj in objects:
                user = obj.get("user") or {}
                if isinstance(user, dict) and user.get("login") == bot:
                    found.append((kind, obj))
        else:
            raise HostedError(f"{endpoint}: still not empty after {MAX_PAGES} pages")
    return found


# ------------------------------------------------------------------- archive


def repo_root(cwd: Path) -> Path:
    try:
        done = subprocess.run(
            ["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise HostedError(f"git rev-parse --show-toplevel: {exc}") from exc
    if done.returncode != 0:
        raise HostedError(f"not inside a git repository: {done.stderr.strip()}")
    return Path(done.stdout.strip())


def _numbered(base: Path) -> list[int]:
    if not base.is_dir():
        return []
    return sorted(int(p.name) for p in base.iterdir() if p.is_dir() and p.name.isdigit())


def _body(obj: dict[str, Any]) -> str:
    return obj.get("body") or ""


def archive(base: Path, k: int, comments: list[tuple[str, dict[str, Any]]]) -> Path:
    """Write the fetch into a hidden sibling of `<k>` (`_numbered` skips it) and
    rename it to `<k>` once every file is written; on any failure remove it, so
    the next run numbers and diffs as if this one never happened."""
    target = base / str(k)
    base.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise HostedError(f"{target} already exists")
    partial = Path(tempfile.mkdtemp(prefix=f".{k}.partial-", dir=base))
    try:
        for kind, obj in comments:
            name = f"{kind}-{obj['id']}"
            (partial / f"{name}.md").write_bytes(_body(obj).encode("utf-8"))
            (partial / f"{name}.json").write_text(
                json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
        os.chmod(partial, 0o755)  # mkdtemp's 0700, as a plain mkdir would leave it
        os.rename(partial, target)
    except BaseException:
        shutil.rmtree(partial, ignore_errors=True)
        raise
    return target


def _load(directory: Path) -> dict[str, dict[str, Any]]:
    """A previous archive: `<kind>-<id>` → its JSON, with the body from the `.md`."""
    loaded: dict[str, dict[str, Any]] = {}
    for raw in sorted(directory.glob("*.json")):
        obj = json.loads(raw.read_text(encoding="utf-8"))
        body = raw.with_suffix(".md")
        if body.is_file():
            obj["body"] = body.read_bytes().decode("utf-8")
        loaded[raw.stem] = obj
    return loaded


# ------------------------------------------------------------------- reading


def _heading(body: str) -> str:
    match = _HEADING.search(body)
    return match.group(1) if match else (body.strip().splitlines() or [""])[0]


def _is_code_review(kind: str, obj: dict[str, Any]) -> bool:
    return kind == "issue-comment" and "Code Review" in _heading(_body(obj))


def _is_summary(kind: str, obj: dict[str, Any]) -> bool:
    return kind == "issue-comment" and "Summary" in _heading(_body(obj))


def categories(body: str) -> list[str]:
    """The header counts as found, before the first finding: any label at all."""
    header = body.split("<details", 1)[0]
    return [label.strip() for label in _CATEGORY.findall(header)]


def header_total(body: str) -> int | None:
    """The header counts added up (`Bugs (7)` + …), or None with no header label."""
    labels = categories(body)
    counts = [int(hit.group(1)) for label in labels if (hit := _COUNT.search(label))]
    return sum(counts) if counts else None


def findings(body: str) -> list[Finding]:
    matches = list(_FINDING.finditer(body))
    found = []
    for i, match in enumerate(matches):
        block = body[match.start(): matches[i + 1].start() if i + 1 < len(matches) else len(body)]
        anchor = None
        if hit := _ANCHOR.search(block):
            path, start, end = hit.groups()
            anchor = f"{path}:{start}" if end in (None, start) else f"{path}:{start}-{end}"
        description: list[str] = []
        if desc := _DESCRIPTION.search(block):
            description = [line[1:] if line.startswith(">") else line
                           for line in desc.group(1).splitlines()]
            while description and not description[0].strip():
                description.pop(0)
            while description and not description[-1].strip():
                description.pop()
        found.append(Finding(match.group(1), match.group(2).strip(), anchor, description))
    return found


def _inline(obj: dict[str, Any]) -> tuple[str | None, str]:
    """An inline comment's finding title (plain) and its file:line; matched to a
    finding by `Finding.key`, case folded."""
    match = _INLINE_TITLE.search(_body(obj))
    line = obj.get("line") or obj.get("original_line")
    where = f"{obj.get('path')}:{line}" if line else str(obj.get("path"))
    return (_plain(match.group(2)) if match else None), where


def _code_review(
    comments: list[tuple[str, dict[str, Any]]],
) -> dict[str, Any] | None:
    reviews = [obj for kind, obj in comments if _is_code_review(kind, obj)]
    return max(reviews, key=lambda obj: obj["id"]) if reviews else None


# ------------------------------------------------------------------ printing


def _print_finding(finding: Finding, out: TextIO, inline: Sequence[str] = ()) -> None:
    print(f"  {finding.number}.  {finding.title}", file=out)
    print(f"      at {finding.anchor or '(no file:line anchor in the comment)'}", file=out)
    if finding.resolved:
        print("      resolved", file=out)
    for line in inline:
        print(f"      inline: {line}", file=out)
    for line in finding.description:
        print(f"      {line}", file=out)


def _diff(
    previous_k: int,
    previous: dict[str, dict[str, Any]],
    current: list[tuple[str, dict[str, Any]]],
    out: TextIO,
) -> None:
    print(f"diff against {previous_k}:", file=out)
    now = {f"{kind}-{obj['id']}": obj for kind, obj in current}
    said = False
    for key, obj in now.items():
        before = previous.get(key)
        if before is None:
            continue
        old_body, new_body = _body(before), _body(obj)
        stamp = f"updated_at {before.get('updated_at')} -> {obj.get('updated_at')}"
        name = key.rsplit("-", 1)
        if old_body == new_body:
            if before.get("updated_at") != obj.get("updated_at"):
                print(f"  touched: {name[0]} {name[1]} {stamp} (body unchanged)", file=out)
                said = True
            continue
        print(f"  changed: {name[0]} {name[1]} {stamp}", file=out)
        for line in difflib.unified_diff(
            old_body.splitlines(), new_body.splitlines(), lineterm="", n=0
        ):
            if line.startswith(("---", "+++")):
                continue
            print(f"    {line}", file=out)
        said = True
    for key in now:
        if key not in previous:
            print("  added: " + " ".join(key.rsplit("-", 1)), file=out)
            said = True
    for key in previous:
        if key not in now:
            print("  vanished: " + " ".join(key.rsplit("-", 1)), file=out)
            said = True
    before_review = _code_review(
        [(key.rsplit("-", 1)[0], obj) for key, obj in previous.items()]
    )
    after_review = _code_review(current)
    if before_review is not None and after_review is not None:
        old = {f.plain: f for f in findings(_body(before_review))}
        new = {f.plain: f for f in findings(_body(after_review))}
        for plain, finding in old.items():
            later = new.get(plain)
            if later is None:
                print(f"  gone from the Code Review comment since {previous_k}: "
                      f"{finding.number}.  {finding.title}", file=out)
                said = True
            elif later.resolved and not finding.resolved:
                print(f"  resolved since {previous_k}: {finding.number}.  {finding.title}",
                      file=out)
                said = True
        for plain, finding in new.items():
            if plain not in old:
                print(f"  new in the Code Review comment since {previous_k}: "
                      f"{finding.number}.  {finding.title}", file=out)
                said = True
    if not said:
        print("  no change by comment id (an in-place edit would show as changed)", file=out)


def run(pr: int, bot: str = DEFAULT_BOT, *, out: TextIO, err: TextIO,
        cwd: Path | None = None) -> int:
    where = Path.cwd() if cwd is None else cwd
    try:
        comments = fetch(pr, bot, where)
        if not comments:
            print(f"PR #{pr}: no bot comment yet from {bot}; nothing written. Wait and run "
                  "again: this is not a clean review (§39)", file=out)
            return EXIT_NOT_YET
        if _code_review(comments) is None:
            print(f"PR #{pr}: {bot} has commented, but the Code Review comment is not there "
                  "yet; nothing written. Wait and run again: this is not a clean review "
                  "(§39)", file=out)
            return EXIT_NOT_YET
        review = _code_review(comments)
        if review is None:
            print(f"PR #{pr}: {bot} has commented, but the Code Review comment is not there "
                  "yet; nothing written. Wait and run again: this is not a clean review "
                  "(§39)", file=out)
            return EXIT_NOT_YET
        root = repo_root(where)
        base = root / "meta" / "reviews" / "hosted" / f"PR-{pr}"
        existing = _numbered(base)
        k = (existing[-1] + 1) if existing else 1
        target = archive(base, k, comments)
    except (HostedError, OSError, ValueError) as exc:
        print(f"hands: hosted-review: {exc}", file=err)
        return 1

    counts = {kind: sum(1 for k_, _ in comments if k_ == kind) for _, kind in SOURCES}
    print(f"PR #{pr}, {bot}: " + ", ".join(f"{kind}s {n}" for kind, n in counts.items()),
          file=out)
    print(f"archived: {target.relative_to(root)}/", file=out)
    summaries = [obj for kind, obj in comments if _is_summary(kind, obj)]
    for obj in summaries:
        print(f"summary comment: issue-comment {obj['id']}", file=out)
    if not summaries:
        print("summary comment: none from the bot", file=out)

    body = _body(review)
    print(f"code review comment: issue-comment {review['id']} "
          f"updated_at {review.get('updated_at')}", file=out)
    print("categories:", file=out)
    for label in categories(body) or ["(none in the header)"]:
        print(f"  {label}", file=out)
    current = findings(body)
    inline: dict[str, list[str]] = {}
    unmatched: list[str] = []
    titles = {f.key for f in current}
    for kind, obj in comments:
        if kind != "review-comment":
            continue
        plain, at = _inline(obj)
        line = f"review-comment {obj['id']} at {at}"
        if plain is not None and plain.casefold() in titles:
            inline.setdefault(plain.casefold(), []).append(line)
        else:
            unmatched.append(f"{line}: {plain or '(no numbered title)'}")
    print("findings:", file=out)
    for finding in current:
        _print_finding(finding, out, inline.get(finding.key, ()))
    if not current:
        print("  (none numbered)", file=out)
    for line in unmatched:
        print(f"inline comment with no finding of that title: {line}", file=out)

    if existing:
        _diff(existing[-1], _load(base / str(existing[-1])), comments, out)

    open_ = [f for f in current if not f.resolved]
    total = header_total(body)
    if total is not None and total > 0 and not open_:
        # PR #4 hosted review, finding 8: a markup change the parser does not read
        # must not turn a review with open findings into a pass.
        print(f"verdict: the findings could not be parsed against the header counts "
              f"(the header counts {total}, {len(current)} parsed, 0 open) — no verdict, "
              "and not a clean review: read the Code Review comment itself", file=out)
        return EXIT_UNPARSED
    if total is not None and total != len(open_):
        print(f"header counts {total} findings, but {len(current)} parsed "
              f"({len(open_)} open): read the Code Review comment itself", file=out)
    if open_:
        print(f"verdict: {len(open_)} of {len(current)} findings open in the Code Review "
              "comment", file=out)
        for finding in open_:
            _print_finding(finding, out)
    else:
        note = f"{len(current)} resolved" if current else "it numbers none"
        print(f"verdict: no finding open in the Code Review comment ({note})", file=out)
    return 0
