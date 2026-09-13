"""`hands kit check` — a kit checked before it is sent (DESIGN §4 `kit check`, §26).

Runs in the client, like `doctor`: no daemon, no socket, no network, and no
hands config, so it works in an architect's sandbox where hands is only
installed. It reads the kit (a `.zip` or a directory whose files sit at their
repository paths) and the repository the kit lands in, and prints one line per
check, then — only when every check passes — the apply prompt of the handbook's
§3 naming every file the kit replaces or adds, and the commit message.

The checks, in order (docs/ARCHITECT-HANDBOOK.md §11 says the same):

* `paths` — every entry is a repository path: relative, no `..`, `.` or empty
  component, no NUL, no backslash, no drive letter, nothing under `.git` in any
  letter case, no symlink entry (a kit is whole files), no zip entry name twice,
  and it lands inside `--repo` once the repo's own symlinks are resolved. No
  entry is over `MAX_ENTRY_BYTES` and the kit is not over `MAX_TOTAL_BYTES`, by
  the sizes the zip's directory declares, read before any byte is (§27).
* `playbook` — the playbook in force is the kit's `PLAYBOOK.toml` or
  `meta/PLAYBOOK.toml` (DESIGN §10's two spellings; there is no config to name
  another path), else the repo's at the same paths. It is parsed by
  `hands.playbook.parse_playbook` — the engine's own parser, which refuses
  `quiet_hours` — without the HEAD comparison, because a kit is by definition
  not yet committed. A kit's playbook must also carry a `[series] kickoff` equal
  to the brief's kickoff line; the repo's is not compared (§26 compares a kit's).
* `brief` — the kit carries exactly one brief, `meta/BUILDER-<N>-PROMPT.md`
  (missions form) or `WORKPLAN.md` (runs form); its kickoff line is the first
  indented line after "Kickoff line"; its final-reply vocabulary is the
  backticked literals of the paragraph that follows "Your final reply begins
  with" or "Reply with one of", its lines joined, so a literal may wrap.
* `verdicts` — every `verdict` regex of the playbook is checked (§27, H-021).
  One on `builder.done` matches (by `re.search`, as the engine does) at least
  one literal of the brief, placeholders such as `<unit>` left as text, and
  every literal matches some such rule. A builder rule that matches no literal
  of the brief passes only when it exists for the apply: its pattern is plain
  text (an optional `^`, no other regex syntax) that the apply prompt's
  `VERDICT: kit applied <sha>` contains, so no branch of it goes unchecked
  (review 10 should-fix 4). One on `aux.done` matches at least one of the
  review protocol's `VERDICT: review …` lines — found in the send prompts and in
  the files they name — with each placeholder (`N`, `<k>`, `{n}`) read as a
  count, tried as each of `PLACEHOLDER_VALUES`. A rule on any other event has
  no vocabulary here to match, and fails.
* `wording` — the brief says neither "as before" nor has a "Budget guidance"
  section (a heading or a bold lead).
* `protocol` — every file a `send` rule's prompt names (a `.md` or `.toml` path
  without a `{placeholder}`) is a repository path, and is in the kit or inside
  the repo. A named path the check cannot resolve (`../X.md`, `~/X.md`, `/X.md`)
  fails rather than being skipped (§27).
"""

from __future__ import annotations

import itertools
import json
import os
import re
import stat
import subprocess
import zipfile
import zlib
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TextIO

from hands.playbook import GIT_ENV_CLEARED, Playbook, PlaybookError, parse_playbook

__all__ = [
    "APPLY_VERDICT",
    "CHECK_NAMES",
    "MAX_ENTRY_BYTES",
    "MAX_TOTAL_BYTES",
    "Check",
    "KitError",
    "Report",
    "check_kit",
    "final_reply_literals",
    "kickoff_line",
    "placeholder_instances",
    "review_literals",
    "run",
]

#: DESIGN §10: `PLAYBOOK.toml` next to `WORKPLAN.md`, or agile-skills' `meta/PLAYBOOK.toml`.
PLAYBOOK_PATHS = ("PLAYBOOK.toml", "meta/PLAYBOOK.toml")
#: The two plan forms of the handbook's §4.
BRIEF_RE = re.compile(r"^(?:meta/BUILDER-(?P<n>\d+)-PROMPT\.md|WORKPLAN\.md)$")
#: The reply the apply prompt asks for; the only literal seen outside the brief.
APPLY_VERDICT = "VERDICT: kit applied <sha>"
KICKOFF_MARK = "Kickoff line"
VOCABULARY_OPENERS = ("Your final reply begins with", "Reply with one of")
#: The event whose verdict is the builder's reply, the one a brief fixes.
BUILDER_DONE = "builder.done"
#: The event whose verdict is the reviewer's, the one the review protocol fixes (§27).
REVIEW_DONE = "aux.done"
#: What `kit check` reads into memory (review 10 should-fix 5; hands' own numbers,
#: the design names none). A kit is text: a DESIGN.md is some 100 KiB.
MAX_ENTRY_BYTES = 16 * 1024 * 1024
MAX_TOTAL_BYTES = 64 * 1024 * 1024
#: §27: a placeholder of the protocol's VERDICT line is read as its class of
#: values, a count; these are the counts tried (none, one, several digits).
PLACEHOLDER_VALUES = ("0", "1", "12")
#: More placeholders than this in one line are tried with one value for all.
MAX_PLACEHOLDERS = 6
CHECK_NAMES = ("paths", "playbook", "brief", "verdicts", "wording", "protocol")
GIT_TIMEOUT_S = 10.0

#: A file a prompt names: a token ending in `.md`/`.toml`, however it begins, so a
#: path the check cannot resolve (`../X.md`, `~/X.md`, `/X.md`) is seen, not skipped.
_NAMED_FILE_RE = re.compile(
    r"[^\s\"'`()\[\]<>,;*]*[^\s\"'`()\[\]<>,;*./]\.(?:md|toml)(?![\w/-])"
)
#: The review's verdict line: at a line's start (a code or list line) or after a
#: colon ("Begin your reply with: VERDICT: review …"); not a backticked mention.
_REVIEW_LINE_RE = re.compile(r"(?:^[ \t>*+-]*|:[ \t]+)(VERDICT: review\b[^`\n]*)", re.MULTILINE)
#: A placeholder in that line: `<k>`, `{n}`, or the bare `N` of the templates.
_PLACEHOLDER_RE = re.compile(r"<[^<>\n]+>|\{[^{}\n]+\}|\bN\b")
#: A pattern that is plain text: an optional `^`, then no regex syntax at all.
_PLAIN_RE = re.compile(r"\^?[^\\.^$*+?{}\[\]|()]+")
_LITERAL_RE = re.compile(r"`([^`]+)`")
_BUDGET_RE = re.compile(r"^\s*(?:#+\s*|\*\*)budget guidance", re.IGNORECASE | re.MULTILINE)
_AS_BEFORE_RE = re.compile(r"\bas\s+before\b", re.IGNORECASE)
_PARAGRAPH_BREAK_RE = re.compile(r"^(?:[-*+]\s|#|\d+\.\s)")


class KitError(ValueError):
    """The command could not run at all: no kit there, not a zip, no repository."""


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    reason: str

    def line(self) -> str:
        return f"{'PASS' if self.ok else 'FAIL'} {self.name}: {self.reason}"


@dataclass
class Report:
    kit: Path
    repo: Path
    checks: list[Check]
    replaces: list[str] = field(default_factory=list)
    adds: list[str] = field(default_factory=list)
    commit_message: str = ""
    apply_prompt: str | None = None

    @property
    def ok(self) -> bool:
        return all(check.ok for check in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kit": str(self.kit),
            "repo": str(self.repo),
            "ok": self.ok,
            "checks": [
                {"name": check.name, "ok": check.ok, "reason": check.reason}
                for check in self.checks
            ],
            "replaces": self.replaces,
            "adds": self.adds,
            "commit_message": self.commit_message,
            "apply_prompt": self.apply_prompt,
        }


@dataclass
class _Kit:
    #: The name the kit has in `~/Downloads`: a zip's own, a directory's plus `.zip`.
    filename: str
    files: dict[str, bytes]
    problems: list[str]


# ------------------------------------------------------------------ the kit


def _path_problem(name: str) -> str | None:
    """Why `name` is not a repository path, or None when it is one."""
    if not name:
        return "an empty name"
    if "\0" in name:
        return "a NUL in the name"
    if "\\" in name:
        return "a backslash in the name"
    if name.startswith("/") or re.match(r"^[A-Za-z]:", name):
        return "an absolute path"
    if name.startswith("~"):
        return "a path under a home directory"
    parts = name.split("/")
    if ".." in parts:
        return "a .. component"
    if any(part in ("", ".") for part in parts):
        return "an empty or . component"
    if any(part.lower() == ".git" for part in parts):  # `.GIT` is `.git` where case folds
        return "a path inside .git"
    return None


def _shown(name: str) -> str:
    """A name fit for a report line: a NUL is written `\\0`."""
    return name.replace("\0", "\\0")


def _read_zip(path: Path) -> _Kit:
    try:
        archive = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError) as exc:
        raise KitError(f"{path} is neither a directory nor a zip: {exc}") from exc
    files: dict[str, bytes] = {}
    problems: list[str] = []
    with archive:
        infos = archive.infolist()
        # The sizes the zip's directory declares, before any byte is read; zipfile
        # stops an entry at its declared size, so what is read cannot exceed them.
        declared = sum(info.file_size for info in infos)
        whole = declared <= MAX_TOTAL_BYTES
        if not whole:
            problems.append(
                f"the entries declare {declared} bytes, over the {MAX_TOTAL_BYTES}-byte cap "
                "on a kit's total"
            )
        seen: set[str] = set()
        for info in infos:
            name = info.orig_filename  # `filename` is cut at a NUL; this is the name stored
            shown = _shown(name)
            if name in seen:  # zipfile would keep only one of them
                problems.append(f"{shown} (a duplicate entry)")
                continue
            seen.add(name)
            if name.endswith("/"):  # a directory entry: checked, never a file
                problem = _path_problem(name.rstrip("/"))
                if problem:
                    problems.append(f"{shown} ({problem})")
                continue
            problem = _path_problem(name)
            if problem is None and stat.S_ISLNK(info.external_attr >> 16):
                problem = "a symlink"
            elif problem is None and info.file_size > MAX_ENTRY_BYTES:
                problem = (
                    f"{info.file_size} bytes, over the {MAX_ENTRY_BYTES}-byte cap on one entry"
                )
            if problem:
                problems.append(f"{shown} ({problem})")
                continue
            if not whole:
                continue
            try:
                files[name] = archive.read(info)
            except (zipfile.BadZipFile, zlib.error, OSError, EOFError, RuntimeError,
                    NotImplementedError, ValueError) as exc:  # fmt: skip
                problems.append(f"{shown} (unreadable: {type(exc).__name__})")
    return _Kit(filename=path.name, files=files, problems=problems)


def _read_dir(root: Path) -> _Kit:
    files: dict[str, bytes] = {}
    problems: list[str] = []
    total = 0
    for dirpath, dirnames, filenames in os.walk(root):  # never follows a symlink
        here = Path(dirpath)
        dirnames.sort()
        for name in list(dirnames):
            if (here / name).is_symlink():
                problems.append(f"{(here / name).relative_to(root).as_posix()}/ (a symlink)")
                dirnames.remove(name)
        for name in sorted(filenames):
            path = here / name
            where = path.relative_to(root).as_posix()
            problem = _path_problem(where)
            if problem is None and path.is_symlink():
                problem = "a symlink"
            elif problem is None and not path.is_file():
                problem = "not a regular file"
            elif problem is None:
                size = path.stat().st_size
                if size > MAX_ENTRY_BYTES:
                    problem = f"{size} bytes, over the {MAX_ENTRY_BYTES}-byte cap on one entry"
                elif total + size > MAX_TOTAL_BYTES:
                    problem = f"over the {MAX_TOTAL_BYTES}-byte cap on a kit's total"
                total += size
            if problem:
                problems.append(f"{where} ({problem})")
                continue
            files[where] = path.read_bytes()
    return _Kit(filename=f"{root.resolve().name}.zip", files=files, problems=problems)


def _read_kit(path: Path) -> _Kit:
    if path.is_dir():
        return _read_dir(path)
    if not path.exists():
        raise KitError(f"no kit at {path}: give a .zip or a directory")
    return _read_zip(path)


# ---------------------------------------------------------------- the brief


def kickoff_line(text: str) -> str | None:
    """The first indented line after a line carrying "Kickoff line", stripped."""
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if KICKOFF_MARK not in line:
            continue
        for following in lines[index + 1 :]:
            if not following.strip():
                continue
            if following.startswith(("    ", "\t")):
                return following.strip()
            break
    return None


def final_reply_literals(text: str) -> list[str] | None:
    """The backticked literals of the paragraph after the vocabulary's opener.

    The paragraph ends at a blank line, a list item, a heading or a numbered
    line; its lines are joined first, so `VERDICT: mission 10\\n  finished` is
    one literal. None when no opener is in the text.
    """
    lines = text.splitlines()
    for index, line in enumerate(lines):
        for opener in VOCABULARY_OPENERS:
            at = line.find(opener)
            if at < 0:
                continue
            paragraph = [line[at + len(opener) :]]
            for following in lines[index + 1 :]:
                stripped = following.strip()
                if not stripped or _PARAGRAPH_BREAK_RE.match(stripped):
                    break
                paragraph.append(stripped)
            joined = " ".join(paragraph)
            return [" ".join(found.split()) for found in _LITERAL_RE.findall(joined)]
    return None


def review_literals(texts: Iterable[str]) -> list[str]:
    """The review protocol's `VERDICT: review …` lines in `texts`, in order, once each."""
    found: list[str] = []
    for text in texts:
        for match in _REVIEW_LINE_RE.finditer(text):
            literal = " ".join(match.group(1).split()).rstrip(".")
            if literal not in found:
                found.append(literal)
    return found


def placeholder_instances(literal: str) -> list[str]:
    """`literal` with each placeholder replaced by a count (§27, H-021).

    `VERDICT: review mission N blockers=<k> should-fix=<m>` becomes every line
    with `N`, `<k>` and `<m>` each one of `PLACEHOLDER_VALUES`, so a regex that
    discriminates on the count (`blockers=0`, `blockers=[1-9]`) meets a value it
    can match, and one that expects text where a count goes (`blockers=none`)
    meets none.
    """
    pieces = _PLACEHOLDER_RE.split(literal)
    holes = len(pieces) - 1
    if holes == 0:
        return [literal]
    if holes <= MAX_PLACEHOLDERS:
        choices: Iterable[tuple[str, ...]] = itertools.product(PLACEHOLDER_VALUES, repeat=holes)
    else:
        choices = ((value,) * holes for value in PLACEHOLDER_VALUES)
    out = []
    for values in choices:
        text = pieces[0]
        for value, piece in zip(values, pieces[1:], strict=True):
            text += value + piece
        out.append(text)
    return out


# --------------------------------------------------------------- the checks


def _and(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def _inside(repo: Path, name: str) -> bool:
    real_repo = os.path.realpath(repo)
    landed = os.path.realpath(repo / name)
    return landed == real_repo or landed.startswith(real_repo + os.sep)


def _check_paths(kit: _Kit, repo: Path) -> Check:
    problems = list(kit.problems)
    problems += [
        f"{name} (lands outside the repo through a symlink)"
        for name in sorted(kit.files)
        if not _inside(repo, name)
    ]
    total = len(kit.files) + len(kit.problems)
    if problems:
        return Check(
            "paths",
            False,
            f"{len(problems)} of {total} entries are not repository paths under {repo}: "
            + "; ".join(problems),
        )
    if not kit.files:
        return Check("paths", False, "the kit holds no files")
    return Check(
        "paths", True, f"{len(kit.files)} files, every one a repository path under {repo}"
    )


def _load(text: bytes | str, name: str) -> Playbook:
    try:
        decoded = text if isinstance(text, str) else text.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PlaybookError(f"{name} is not valid UTF-8: {exc}") from exc
    return parse_playbook(decoded, path=Path(name))


def _check_playbook(
    kit: _Kit, repo: Path, kickoff: str | None
) -> tuple[Check, Playbook | None]:
    carried = [name for name in PLAYBOOK_PATHS if name in kit.files]
    if len(carried) > 1:
        return Check("playbook", False, f"the kit carries {_and(carried)}; carry one"), None
    if carried:
        name = carried[0]
        try:
            book = _load(kit.files[name], name)
        except PlaybookError as exc:
            return Check("playbook", False, f"the kit's {name} does not load: {exc}"), None
        if book.kickoff is None:
            reason = f"the kit's {name} loads but sets no [series] kickoff"
            return Check("playbook", False, reason), book
        if kickoff is None:
            reason = (
                f"the kit's {name} loads; its [series] kickoff {book.kickoff!r} has no "
                "brief kickoff line to equal (see brief)"
            )
            return Check("playbook", False, reason), book
        if book.kickoff != kickoff:
            reason = (
                f"the kit's {name} loads, but its [series] kickoff {book.kickoff!r} is not "
                f"the brief's kickoff line {kickoff!r}"
            )
            return Check("playbook", False, reason), book
        reason = (
            f"the kit's {name} loads, sets no quiet_hours, and its [series] kickoff "
            "equals the brief's kickoff line"
        )
        return Check("playbook", True, reason), book
    present = [name for name in PLAYBOOK_PATHS if (repo / name).is_file()]
    if not present:
        reason = (
            f"the kit carries no playbook and the repo has none at {' or '.join(PLAYBOOK_PATHS)}"
        )
        return Check("playbook", False, reason), None
    name = present[0]
    try:
        book = _load((repo / name).read_bytes(), name)
    except (PlaybookError, OSError) as exc:
        return Check("playbook", False, f"the repo's {name} does not load: {exc}"), None
    reason = (
        f"the kit carries no playbook; the repo's {name} is in force (loads, no "
        "quiet_hours; its kickoff is not compared, §26 compares a kit's)"
    )
    return Check("playbook", True, reason), book


def _find_brief(kit: _Kit) -> tuple[Check, str | None, str | None]:
    """The brief check, the brief's name, and its text."""
    briefs = sorted(name for name in kit.files if BRIEF_RE.match(name))
    if not briefs:
        reason = "the kit carries no brief (meta/BUILDER-<N>-PROMPT.md or WORKPLAN.md)"
        return Check("brief", False, reason), None, None
    if len(briefs) > 1:
        return Check("brief", False, f"the kit carries {_and(briefs)}; carry one"), None, None
    name = briefs[0]
    try:
        text = kit.files[name].decode("utf-8")
    except UnicodeDecodeError as exc:
        return Check("brief", False, f"{name} is not valid UTF-8: {exc}"), name, None
    kickoff = kickoff_line(text)
    literals = final_reply_literals(text)
    missing = []
    if kickoff is None:
        missing.append(f'no kickoff line (an indented line after "{KICKOFF_MARK}")')
    if not literals:
        missing.append(
            "no final-reply vocabulary (backticked literals after "
            + " or ".join(f'"{opener}"' for opener in VOCABULARY_OPENERS)
            + ")"
        )
    if missing:
        return Check("brief", False, f"{name}: " + "; ".join(missing)), name, text
    reason = f"{name}: kickoff {kickoff!r}; final-reply literals " + " | ".join(literals or [])
    return Check("brief", True, reason), name, text


def _is_the_apply_rule(verdict: re.Pattern[str]) -> bool:
    """A builder rule that exists for the apply (review 10 should-fix 4).

    Its pattern is plain text — an optional `^` and no other regex syntax — and the
    apply prompt's literal contains it, so it has no branch, class or repeat that
    could hold a typo `VERDICT: kit applied <sha>` never exercises.
    """
    return bool(_PLAIN_RE.fullmatch(verdict.pattern)) and verdict.search(APPLY_VERDICT) is not None


def _check_verdicts(
    book: Playbook | None, literals: list[str] | None, review: list[str]
) -> Check:
    if book is None:
        return Check("verdicts", False, "no playbook in force to match (see playbook)")
    if not literals:
        return Check("verdicts", False, "no final-reply vocabulary to match (see brief)")
    verdict_rules = [rule for rule in book.rules if rule.verdict is not None]
    rules = [rule for rule in verdict_rules if rule.on == BUILDER_DONE]
    reviews = [rule for rule in verdict_rules if rule.on == REVIEW_DONE]
    others = [rule for rule in verdict_rules if rule.on not in (BUILDER_DONE, REVIEW_DONE)]
    problems: list[str] = []
    via_apply: list[str] = []
    for rule in rules:
        assert rule.verdict is not None
        if any(rule.verdict.search(literal) for literal in literals):
            continue
        if _is_the_apply_rule(rule.verdict):
            via_apply.append(f"rule {rule.index}")
            continue
        why = ""
        if rule.verdict.search(APPLY_VERDICT):
            why = (
                f" (it matches the apply prompt's {APPLY_VERDICT!r}, but only a plain-text "
                "pattern of that literal is excused by it)"
            )
        problems.append(
            f"rule {rule.index} verdict '{rule.verdict.pattern}' matches none of: "
            + " | ".join(literals)
            + why
        )
    for literal in literals:
        if not any(rule.verdict and rule.verdict.search(literal) for rule in rules):
            problems.append(f"the brief's {literal!r} matches no {BUILDER_DONE} verdict rule")
    shown_review = " | ".join(repr(literal) for literal in review)
    if reviews and not review:
        names = _and([f"rule {rule.index}" for rule in reviews])
        problems.append(
            f"{names} on {REVIEW_DONE} have no review vocabulary to match: no "
            "'VERDICT: review …' line in a send's prompt or in a file a send names "
            "(see protocol)"
        )
    elif reviews:
        instances = [text for literal in review for text in placeholder_instances(literal)]
        for rule in reviews:
            assert rule.verdict is not None
            if not any(rule.verdict.search(text) for text in instances):
                problems.append(
                    f"rule {rule.index} verdict '{rule.verdict.pattern}' matches none of the "
                    f"review protocol's {shown_review} (placeholders read as counts)"
                )
    for rule in others:
        assert rule.verdict is not None
        problems.append(
            f"rule {rule.index} verdict '{rule.verdict.pattern}' is on {rule.on}, whose "
            "replies neither the brief nor the review protocol fixes"
        )
    notes = []
    if via_apply:
        verb = "matches" if len(via_apply) == 1 else "match"
        notes.append(f"{_and(via_apply)} {verb} the apply prompt's {APPLY_VERDICT!r}")
    if problems:
        return Check("verdicts", False, "; ".join(problems + notes))
    parts = [
        f"{len(rules)} {BUILDER_DONE} verdict rules and the brief's {len(literals)} "
        "literals match each other",
        *notes,
    ]
    if reviews:
        parts.append(
            f"{len(reviews)} {REVIEW_DONE} verdict rule(s) match the review protocol's "
            f"{shown_review} (placeholders read as counts)"
        )
    return Check("verdicts", True, "; ".join(parts))


def _check_wording(name: str | None, text: str | None) -> Check:
    if text is None:
        return Check("wording", False, "no brief to read (see brief)")
    found = []
    if _AS_BEFORE_RE.search(text):
        found.append('"as before"')
    if _BUDGET_RE.search(text):
        found.append('a "Budget guidance" section')
    if found:
        return Check("wording", False, f"{name} has {_and(found)}")
    return Check("wording", True, f'{name} has no "as before" and no "Budget guidance" section')


def _named_files(book: Playbook) -> dict[str, list[int]]:
    """Every file a `send` rule's prompt names, with the rules naming it."""
    named: dict[str, list[int]] = {}
    for rule in book.rules:
        if rule.then != "send" or not rule.prompt:
            continue
        for name in _NAMED_FILE_RE.findall(rule.prompt):
            if "{" in name or "}" in name:
                continue  # a placeholder: a different file per job, not one to check
            named.setdefault(name, []).append(rule.index)
    return named


def _named_file(name: str, kit: _Kit, repo: Path) -> tuple[bytes | None, str]:
    """A named file's bytes and where they are (`kit`, `repo`), or None and why not."""
    problem = _path_problem(name)
    if problem:
        return None, f"not a repository path ({problem})"
    if name in kit.files:
        return kit.files[name], "kit"
    if not _inside(repo, name):
        return None, "outside the repo (through a symlink)"
    path = repo / name
    if not path.is_file():
        return None, "in neither the kit nor the repo"
    try:
        if path.stat().st_size > MAX_ENTRY_BYTES:
            return None, f"over the {MAX_ENTRY_BYTES}-byte cap on one file"
        return path.read_bytes(), "repo"
    except OSError as exc:
        return None, f"unreadable ({type(exc).__name__})"


def _review_vocabulary(book: Playbook | None, kit: _Kit, repo: Path) -> list[str]:
    """The `VERDICT: review …` lines of the send prompts and of the files they name."""
    if book is None:
        return []
    texts = [rule.prompt for rule in book.rules if rule.then == "send" and rule.prompt]
    for name in sorted(_named_files(book)):
        data, _ = _named_file(name, kit, repo)
        if data is not None:
            texts.append(data.decode("utf-8", errors="replace"))
    return review_literals(texts)


def _check_protocol(book: Playbook | None, kit: _Kit, repo: Path) -> Check:
    if book is None:
        return Check("protocol", False, "no playbook in force to read (see playbook)")
    named = _named_files(book)
    if not named:
        return Check("protocol", True, "no send rule names a file")
    missing = []
    found = []
    for name, indexes in sorted(named.items()):
        rules = _and([f"rule {index}" for index in sorted(set(indexes))])
        data, where = _named_file(name, kit, repo)
        if data is None:
            missing.append(f"{rules} names {_shown(name)}, which is {where}")
        else:
            found.append(f"{name} ({where})")
    if missing:
        return Check("protocol", False, "; ".join(missing))
    return Check("protocol", True, "every file a send names is present: " + ", ".join(found))


def _commit_message(brief: str | None, filename: str) -> str:
    match = BRIEF_RE.match(brief or "")
    if match and match.group("n"):
        return f"plan: mission {match.group('n')} kit"
    return f"plan: kit {filename.removesuffix('.zip')}"


def apply_prompt(filename: str, replaces: list[str], adds: list[str], message: str) -> str:
    """The handbook's §3 apply prompt, naming every file the kit touches."""
    touched = []
    if replaces:
        touched.append("replaces " + _and(replaces))
    if adds:
        touched.append("adds " + _and(adds))
    return (
        f"Apply ~/Downloads/{filename} to this repository: unzip -o into the repo root "
        f"(it {' and '.join(touched)}), then one plan-only sub-agent makes a single commit "
        f"'{message}' listing those files in its body, and pushes. Change nothing else. "
        f"Reply with one line: {APPLY_VERDICT}."
    )


def check_kit(path: Path, repo: Path) -> Report:
    kit = _read_kit(path)
    brief_check, brief_name, brief_text = _find_brief(kit)
    kickoff = kickoff_line(brief_text) if brief_text is not None else None
    literals = final_reply_literals(brief_text) if brief_text is not None else None
    playbook_check, book = _check_playbook(kit, repo, kickoff)
    review = _review_vocabulary(book, kit, repo)
    checks = [
        _check_paths(kit, repo),
        playbook_check,
        brief_check,
        _check_verdicts(book, literals, review),
        _check_wording(brief_name, brief_text),
        _check_protocol(book, kit, repo),
    ]
    replaces = sorted(name for name in kit.files if os.path.lexists(repo / name))
    adds = sorted(name for name in kit.files if name not in replaces)
    report = Report(
        kit=path,
        repo=repo,
        checks=checks,
        replaces=replaces,
        adds=adds,
        commit_message=_commit_message(brief_name, kit.filename),
    )
    if report.ok:
        report.apply_prompt = apply_prompt(kit.filename, replaces, adds, report.commit_message)
    return report


# ------------------------------------------------------------------ the CLI


def git_toplevel(cwd: Path) -> Path:
    """`--repo`'s default: the top level of the git repository `cwd` is in."""
    env = {name: value for name, value in os.environ.items() if name not in GIT_ENV_CLEARED}
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=cwd,
            env=env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_S,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise KitError(f"cannot run git in {cwd} ({exc}); pass --repo <path>") from exc
    if proc.returncode != 0 or not proc.stdout.strip():
        said = (proc.stderr.strip().splitlines() or [f"exit {proc.returncode}"])[0]
        raise KitError(f"{cwd} is not inside a git repository ({said}); pass --repo <path>")
    return Path(proc.stdout.strip())


def run(kit: str, repo: str | None, *, out: TextIO, as_json: bool) -> int:
    """`hands kit check <zip|dir> [--repo path]`: exit 0 only when every check passes."""
    root = Path(repo).expanduser() if repo else git_toplevel(Path.cwd())
    if not root.is_dir():
        raise KitError(f"--repo {root} is not a directory")
    report = check_kit(Path(kit).expanduser(), root)
    if as_json:
        print(json.dumps(report.to_dict(), sort_keys=True), file=out)
        return 0 if report.ok else 1
    for check in report.checks:
        print(check.line(), file=out)
    failed = [check for check in report.checks if not check.ok]
    if failed:
        print(
            f"kit check: FAIL ({len(failed)} of {len(report.checks)} checks failed); "
            "no apply prompt for a failing kit",
            file=out,
        )
        return 1
    print("apply prompt:", file=out)
    print(f"    {report.apply_prompt}", file=out)
    print(f"commit message: {report.commit_message}", file=out)
    print(f"kit check: pass ({len(report.checks)} of {len(report.checks)} checks)", file=out)
    return 0
