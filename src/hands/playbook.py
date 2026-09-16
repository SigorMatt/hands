"""The playbook — the architect's pre-planned steps, run without a human (DESIGN §10).

    PLAYBOOK.toml (in the builder's repo, on the series branch)
      └─ [[rule]] on = <event> [verdict = <regex>] then = send|resume|notify|stop|consult

The engine is a table lookup and nothing more: an event arrives, the first rule
whose `on` matches it and whose `verdict` regex matches the job's `VERDICT:`
line fires, and **everything else is a `stop`** — an event with no rule, a
verdict that matches no rule, a `result` with no `VERDICT:` line, a run that is
not listed in `[limits] auto_runs`, a placeholder that cannot be resolved, a
send the daemon refuses, and exhausted resumes. `stop` pauses the engine,
records the reason, writes the inbox event (§11) and notifies. That default is
the whole safety property of §10: hands executes what the architect pre-planned
and calls a human for everything else.

What lives here and what does not:

* the playbook is **a file in the builder's repo**, read when a job starts, and
  its sha256 is stamped on every job the engine fires. A missing file is not an
  error — hands still runs jobs, nothing chains. An unparseable or invalid one
  **is**: the engine stops rather than fire a rule out of a half-read file. So
  is one that differs from `git show HEAD:<path>` (dirty) or is not in HEAD
  (untracked): only the committed file loads (§10, §25).
* the engine never spawns anything itself. `send` goes through the same API
  method `hands send` uses, so §8's gate patterns still apply to a job hands
  starts on its own; `resume` goes through the daemon's queue directly, like
  §6's limit resume, which is never re-gated.
* a `limited` job's resume belongs to §6 (`hands.limits`), which waits out the
  reset first. A `then = "resume"` rule on `builder.limited` therefore records
  that the rule fired and leaves the scheduling alone: firing a second resume
  here would send two jobs into the same limit.
* `consult` (§27) starts a driver-role job with a prompt hands writes itself
  (`consult_prompt`) through the daemon's queue, like `resume`: `Api.send`
  refuses the driver role from every origin, and a consultation is not re-gated.
  The driver job's end comes back as `driver.done|failed|killed|orphaned|limited`;
  `[limits] max_consults` bounds how many a mission may start.
* §28: the stops of a consultation are the engine's, not the playbook's. Every
  driver end but a `driver.done` whose verdict is `VERDICT: resolved …` stops —
  escalate, an unrecognised or missing verdict, failed, killed, orphaned,
  limited — whatever `driver.*` rules the playbook carries. A rule that matches
  first and is itself a `stop` is that stop (its message is the reason); any
  other matching rule does not fire. A resolved verdict goes to the rules.
"""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import logging
import os
import re
import subprocess
import tomllib
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from hands.config import ARCHITECT_ROLE, Config
from hands.limits import LimitManager
from hands.spool import ARCHITECT_ORIGIN, Job, Spool, SpoolError, atomic_write, now_iso

__all__ = [
    "ACTIONS",
    "ARCHITECT_MODES",
    "AUTONOMOUS_APPROVAL",
    "CONSULT_QUESTION",
    "ConsultAnchor",
    "DEFAULT_ARCHITECT_MODE",
    "DEFAULT_GATE_FAILURES",
    "DEFAULT_MAX_ARCHITECT_CONSULTS",
    "DEFAULT_MAX_CONSULTS",
    "DRIVER_VERDICTS",
    "ENGINE_RULE_INDEX",
    "ESCALATE_ON",
    "KIT_APPLIED",
    "LIMIT_KEYS",
    "SERIES_KEYS",
    "PAUSE_REASON",
    "EVENTS",
    "JOB_PLACEHOLDERS",
    "ORIGIN",
    "UNPAUSE_ORIGINS",
    "PipelineState",
    "PlaceholderError",
    "Playbook",
    "PlaybookEngine",
    "PlaybookConfigError",
    "PlaybookError",
    "PlaybookNotCommitted",
    "Rule",
    "check_series_roles",
    "load_playbook",
    "parse_playbook",
    "playbook_path",
    "consult_head",
    "consult_prompt",
    "render",
    "run_number",
]

log = logging.getLogger("hands.playbook")

#: §10's "Events", in the order §10 lists them, with §24's `monitor.task_killed`
#: and `monitor.orphan_processes` after their monitor siblings (§24: the
#: example playbook maps both to `stop`, so they have to be names a rule may
#: use). Closed: an event outside this list is not a playbook event and fires
#: nothing (a `killed` job, for one, is a human's own `hands cancel`, and the
#: human already knows).
EVENTS: tuple[str, ...] = (
    "builder.done",
    "builder.failed",
    "builder.limited",
    "builder.orphaned",
    "aux.done",
    "aux.failed",
    "driver.done",
    "driver.failed",
    "driver.killed",  # §28: a consultation's driver job ended any other way
    "driver.orphaned",
    "driver.limited",
    "monitor.stall",
    "monitor.tripwire",
    "monitor.task_killed",
    "monitor.orphan_processes",
    "job.held",
    "job.denied",
)

#: §10's "Actions", and §27's `consult`.
ACTIONS: tuple[str, ...] = ("send", "resume", "notify", "stop", "consult")

#: §27: the role a `consult` starts, and the question its prompt asks, verbatim.
DRIVER = "driver"
CONSULT_QUESTION = (
    "resolve within your authority, citing the mission file or DESIGN section, or escalate"
)
#: §27: the first line of the driver's reply is exactly one of these. `kit check`
#: reads a `driver.done` verdict rule against them, placeholders left as text.
DRIVER_VERDICTS: tuple[str, ...] = (
    "VERDICT: resolved <what was sent, and the section cited>",
    "VERDICT: escalate <reason>",
)
#: §27: `[limits] max_consults` when the playbook does not set it.
DEFAULT_MAX_CONSULTS = 2
#: The consult prompt's first line, which names what the consultation is about; the
#: engine reads it back when the driver job ends (`consult.done`, the journal line).
_CONSULT_HEAD_RE = re.compile(
    r"\Ahands consult: (?P<event>\S+) on job (?P<job>\S+) \(role (?P<role>\S+)\)$",
    re.MULTILINE,
)
#: §28: the driver job's end states that stop whatever the playbook says; and the
#: two verdicts of §27 read from a `driver.done`: only `resolved` goes to the rules.
DRIVER_STOP_STATES: tuple[str, ...] = ("failed", "killed", "orphaned", "limited")
_RESOLVED_RE = re.compile(r"\AVERDICT: resolved \S")
_ESCALATE_RE = re.compile(r"\AVERDICT: escalate(?:\s+(?P<reason>.*))?\Z")
#: §27, §28: the origin of the held apply handsd files for a kit; one that ran is a
#: kit apply, from which `max_consults` also counts.
KIT_ORIGIN = "kit"
#: §27: the journal a consultation appends one line to, under `roles.builder.cwd`.
JOURNAL = Path("meta") / "journal.md"

#: §31: `[series] architect`. `phone` is the architect the human talks to in a
#: chat Project; `role` is the headless architect handsd starts (`[roles.architect]`).
ARCHITECT_MODES: tuple[str, ...] = ("phone", "role")
DEFAULT_ARCHITECT_MODE = "phone"
#: §31: `[series] escalate_on`, a closed vocabulary. The engine owns the budget
#: one itself; the architect's CLAUDE.md names all three.
ESCALATE_ON: tuple[str, ...] = ("blocker-unanswered", "milestone-missing", "budget-exhausted")
#: §31 writes `gate_failures = 2` and leaves the default unsaid; U4 takes the
#: design's own number, so a playbook that omits the key behaves as §31's example.
DEFAULT_GATE_FAILURES = 2
#: §31: `[limits] max_architect_consults` per series (default 12).
DEFAULT_MAX_ARCHITECT_CONSULTS = 12
#: §31: the reply the engine's own `builder.done` rule matches. It is the verdict
#: line the apply prompt asks for (`hands.kit.APPLY_VERDICT`), anchored.
KIT_APPLIED = r"^VERDICT: kit applied"
_KIT_APPLIED_RE = re.compile(KIT_APPLIED)
#: §31: the index of the rule the engine adds. Negative so it can never be a
#: playbook rule's index, and so `last_rule` says plainly that no line of the
#: file fired.
ENGINE_RULE_INDEX = -1
#: §31: what a `decided_by: playbook` gate record stores as its reason. The
#: authority is one step removed and the record says which step.
AUTONOMOUS_APPROVAL = (
    'the playbook in force sets [series] architect = "role" and autonomous = true; '
    "the human's approval of that playbook is the standing approval for the applies "
    "the architect files under it (§31)"
)

#: §10's "Placeholders": the job fields a rule may name as `{job.<field>}`.
JOB_PLACEHOLDERS: tuple[str, ...] = ("id", "head_at_start", "head_at_end", "session_id")

#: §6's origin vocabulary. Every job the engine fires carries this one.
ORIGIN = "playbook"

#: §10's stop → resume cycle: the job origins whose *start* clears a stop. `cli` —
#: the human answering the stop — and `phone`, a `go` the human typed the secret
#: for (§26; H-018 gap 2: without it a `go` after a stop would run the builder
#: while its `builder.done` fired no rule) — and `kit`, the held apply a kit from
#: the phone filed, which starts only once the human approved it (§27). A job the
#: playbook started
#: (`playbook`) or one §6 filed when a limit reset (`limit`) is the pipeline
#: itself, and a `driver` job (in §6's vocabulary, filed by nothing today) is not
#: an origin §10 names, so neither clears one.
UNPAUSE_ORIGINS = frozenset({"cli", "phone", "kit"})

#: The `stop` reason `hands pause` files (§11, H-007). A human, not a rule.
PAUSE_REASON = "paused by human"
#: §29: the notification of an engine consult stop suppressed over a paused pipeline.
SUPPRESSED_CONSULT_TITLE = "hands: a consultation stopped over a paused pipeline"

TOP_KEYS: tuple[str, ...] = ("version", "series", "limits", "rule")
LIMIT_KEYS: tuple[str, ...] = (
    "auto_runs",
    "max_resumes",
    "max_consults",
    "max_architect_consults",  # §31
)
#: §26's `[series]` table: `kickoff`, and `name`, which is where the series' name
#: goes when the table is used — TOML cannot hold `series = "…"` beside a
#: `[series]` table (H-019).
#: §31 adds the series' mode (`architect`, `autonomous`) and its escalation
#: conditions (`gate_failures`, `escalate_on`), all refused at load like the rest.
SERIES_KEYS: tuple[str, ...] = (
    "name",
    "kickoff",
    "architect",
    "autonomous",
    "gate_failures",
    "escalate_on",
)
#: §11 (§25, decision 2026-09-12): the retired `[limits]` key, refused by name.
RETIRED_LIMIT = "quiet_hours"
RULE_KEYS: tuple[str, ...] = (
    "on",
    "verdict",
    "then",
    "role",
    "context",
    "prompt",
    "message",
    "run",
)
VERSION = 1
CONTEXTS = ("clear", "keep")


class PlaybookError(Exception):
    """The playbook is unparseable, or says something §10 does not allow."""


class PlaybookNotCommitted(PlaybookError):
    """The file on disk is not the committed copy (§10, §25): dirty or untracked."""


class PlaybookConfigError(PlaybookError):
    """The playbook is valid, and this project cannot honour it (§31).

    The playbook is a file in the builder's repository and the roles are in
    `~/.hands/<project>.toml`; only where the two meet can a `[series] architect
    = "role"` be checked against `[roles.architect]`. That is `check_series_roles`,
    called from the engine's own load — so the pipeline stops rather than fire a
    rule under a playbook whose architect this laptop does not configure.
    """


#: How long `git show HEAD:<path>` may take before the playbook is refused (§10).
GIT_SHOW_TIMEOUT_S = 10.0
#: Environment variables that would point `git show` at another repository,
#: work tree or index than the one `cwd` is in; never passed to it (§26).
GIT_ENV_CLEARED = frozenset({"GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"})


class PlaceholderError(Exception):
    """A `{placeholder}` that cannot be resolved for this event (§10)."""


# --------------------------------------------------------------- placeholders

_PLACEHOLDER_RE = re.compile(r"\{([^{}]*)\}")
_NAME = r"[A-Za-z_][A-Za-z0-9_]*"
_GROUP_RE = re.compile(rf"^({_NAME})$")
_ARITH_RE = re.compile(rf"^({_NAME})\s*([+-])\s*(\d+)$")
_JOB_RE = re.compile(rf"^job\.({_NAME})$")


@dataclass(frozen=True)
class Ref:
    """One placeholder: a named group of the verdict regex, or a job field."""

    spec: str
    kind: str  # "group" | "job"
    name: str
    delta: int = 0

    @property
    def text(self) -> str:
        return "{" + self.spec + "}"


def parse_ref(spec: str) -> Ref | None:
    """`n` / `n+1` / `job.head_at_start` → a `Ref`; anything else → None."""
    match = _GROUP_RE.match(spec)
    if match is not None:
        return Ref(spec=spec, kind="group", name=match.group(1))
    match = _ARITH_RE.match(spec)
    if match is not None:
        sign = -1 if match.group(2) == "-" else 1
        return Ref(spec=spec, kind="group", name=match.group(1), delta=sign * int(match.group(3)))
    match = _JOB_RE.match(spec)
    if match is not None:
        return Ref(spec=spec, kind="job", name=match.group(1))
    return None


def refs(text: str) -> list[Ref]:
    """Every placeholder in `text`, in order. Raises on one that is not one."""
    out = []
    for match in _PLACEHOLDER_RE.finditer(text):
        ref = parse_ref(match.group(1))
        if ref is None:
            raise PlaceholderError(
                f"{match.group(0)} is not a placeholder §10 knows: "
                "{name}, {name+k}, or {job.<field>}"
            )
        out.append(ref)
    return out


def render(text: str, *, groups: dict[str, str], job: Job | None = None) -> str:
    """Substitute §10's placeholders. An unresolvable one raises — it is never left in.

    A prompt with `{n}` still in it would be sent to a model as if it were
    English, and a job field that is null (`{job.head_at_start}` outside a git
    repo) would read as the word "None". Both are errors that stop the pipeline.
    """

    def one(match: re.Match[str]) -> str:
        ref = parse_ref(match.group(1))
        if ref is None:
            raise PlaceholderError(
                f"{match.group(0)} is not a placeholder §10 knows: "
                "{name}, {name+k}, or {job.<field>}"
            )
        return _value(ref, groups, job)

    return _PLACEHOLDER_RE.sub(one, text)


def _value(ref: Ref, groups: dict[str, str], job: Job | None) -> str:
    if ref.kind == "job":
        if ref.name not in JOB_PLACEHOLDERS:
            raise PlaceholderError(
                f"{ref.text} is not one of §10's job fields "
                f"({', '.join('job.' + name for name in JOB_PLACEHOLDERS)})"
            )
        if job is None:
            raise PlaceholderError(f"{ref.text} has no job to read: this event carries none")
        value = getattr(job, ref.name)
        if value is None:
            raise PlaceholderError(f"job {job.id} has no {ref.name} to put in {ref.text}")
        return str(value)
    if ref.name not in groups:
        raise PlaceholderError(
            f"{ref.text} is not a named group of the rule's verdict regex "
            f"({', '.join(sorted(groups)) or 'it has none'})"
        )
    raw = groups[ref.name]
    if ref.delta == 0:
        return raw
    try:
        return str(int(raw) + ref.delta)
    except ValueError as exc:
        raise PlaceholderError(
            f"{ref.text} needs {ref.name} to be an integer, and it is {raw!r}"
        ) from exc


def run_ref(expr: str) -> Ref:
    """`run = "<expr>"` → the one placeholder it computes (§10, H-006).

    The grammar is the placeholders' own, narrowed to a named group of the
    rule's verdict regex: `{n}` or `{n+1}`. A literal, a job field, prose, or
    two placeholders are not runs — and this is checked when the playbook is
    loaded, so nothing ambiguous can reach a running pipeline.
    """
    found = _PLACEHOLDER_RE.fullmatch(expr.strip())
    ref = parse_ref(found.group(1)) if found is not None else None
    if ref is None or ref.kind != "group":
        raise PlaceholderError(
            f"run takes one named group of the rule's verdict regex, {{name}} or "
            f"{{name+k}} (§10), got {expr!r}"
        )
    return ref


def run_number(expr: str, *, groups: dict[str, str], job: Job | None = None) -> int:
    """The run a `send` would start: the computed value of its `run` key (§10).

    §10 names the checked value explicitly (H-006): `run = "{n+1}"` with `n = 3`
    is run 4. The expression itself was validated at load time, so the only
    failure left here is a group whose matched text is not an integer.
    """
    ref = run_ref(expr)
    value = _value(ref, groups, job)
    try:
        return int(value)
    except ValueError as exc:
        raise PlaceholderError(
            f'run = "{expr}" needs {ref.text} to be a run number, and it is {value!r}'
        ) from exc


# -------------------------------------------------------------- the playbook


@dataclass(frozen=True)
class Rule:
    """One `[[rule]]` of §10, validated."""

    index: int
    on: str
    then: str
    verdict: re.Pattern[str] | None = None
    role: str | None = None
    context: str | None = None
    prompt: str | None = None
    message: str | None = None
    run: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "on": self.on,
            "then": self.then,
            "verdict": self.verdict.pattern if self.verdict else None,
            "role": self.role,
            "context": self.context,
            "prompt": self.prompt,
            "message": self.message,
            "run": self.run,
        }


@dataclass(frozen=True)
class Playbook:
    """A loaded `PLAYBOOK.toml`, with the sha256 that every fired job records."""

    path: Path
    sha256: str
    version: int
    series: str | None
    auto_runs: tuple[int, ...]
    max_resumes: int | None
    rules: tuple[Rule, ...]
    #: §26: the series' fixed kickoff line, `[series] kickoff`; what `go` sends.
    kickoff: str | None = None
    #: §27: consultations a mission may start, counted from the last kickoff.
    max_consults: int = DEFAULT_MAX_CONSULTS
    #: §31's `[series]`: which architect runs this series, whether the engine may
    #: approve its applies, and the escalation conditions written down rather than
    #: judged in the moment.
    architect: str = DEFAULT_ARCHITECT_MODE
    autonomous: bool = False
    gate_failures: int = DEFAULT_GATE_FAILURES
    escalate_on: tuple[str, ...] = ()
    #: §31: consultations of the architect role this series may start.
    max_architect_consults: int = DEFAULT_MAX_ARCHITECT_CONSULTS

    @property
    def architect_is_autonomous(self) -> bool:
        """§31: both keys, or neither. One alone gives the engine nothing: a
        `phone` architect files no job for it to approve, and a `role` architect
        without `autonomous` files applies a human decides."""
        return self.architect == "role" and self.autonomous

    def rules_for(self, event: str) -> list[Rule]:
        """Every rule on `event`, in file order — §10 reads top to bottom."""
        return [rule for rule in self.rules if rule.on == event]


def playbook_path(config: Config) -> Path:
    """§10, §13: `<roles.builder.cwd>/<playbook.path>`."""
    return config.role("builder").cwd / config.playbook.path


def load_playbook(path: Path, *, cwd: Path | None = None) -> Playbook | None:
    """The playbook at `path`, or None when there is no file there (§10).

    A missing playbook is not an error: hands runs jobs, nothing chains. Every
    other problem is a `PlaybookError` — a half-read file must never fire a rule.

    §10 (§25): the file is loaded only when it is the committed copy. Its bytes
    are compared with `git show HEAD:./<path relative to cwd>` run in `cwd`
    (`roles.builder.cwd` for the engine and doctor; the file's own directory
    when no `cwd` is given), before it is parsed — see `_check_committed`.
    """
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise PlaybookError(f"cannot read the playbook {path}: {exc}") from exc
    _check_committed(path, raw, path.parent if cwd is None else cwd)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PlaybookError(f"{path} is not valid UTF-8: {exc}") from exc
    return parse_playbook(text, path=path)


def _check_committed(path: Path, raw: bytes, cwd: Path) -> None:
    """§10: refuse the file when it differs from `git show HEAD:<path>` in `cwd`.

    `HEAD:./<relative>` is git's cwd-relative spelling, so `playbook.path` means
    what §13 says — relative to `roles.builder.cwd` — even when that directory
    is below the repository root. Every refusal names the working file's sha256
    and the committed one's (`none` when git has no committed copy).

    * git exits non-zero (the path is not in HEAD, HEAD has no commit, `cwd` is
      not a git repository): refused as **untracked**, with git's own line;
    * git exits zero with other bytes: refused as **dirty**;
    * git cannot be run or does not answer in time: refused — a file that could
      not be compared is not known to be the committed copy.

    §26 (review 9 should-fix 3): git runs without the daemon's `GIT_DIR`,
    `GIT_WORK_TREE` and `GIT_INDEX_FILE`, so the repository is the one `cwd` is
    in, and with `core.autocrlf=false`; both sides are compared with CRLF read as
    LF, so a CRLF checkout of an LF commit is the committed copy. The sha256s
    named are of the bytes as they are, on disk and in HEAD.
    """
    spec = "HEAD:./" + Path(os.path.relpath(path, cwd)).as_posix()
    working = hashlib.sha256(raw).hexdigest()
    env = {name: value for name, value in os.environ.items() if name not in GIT_ENV_CLEARED}
    try:
        proc = subprocess.run(
            ["git", "-c", "core.autocrlf=false", "show", spec],
            cwd=cwd,
            env=env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=GIT_SHOW_TIMEOUT_S,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise PlaybookNotCommitted(
            f"{path} cannot be compared with its committed copy (`git show {spec}` in "
            f"{cwd}: {exc}): working sha256 {working}, committed sha256 unknown; "
            "only the committed file loads (§10)"
        ) from exc
    if proc.returncode != 0:
        lines = proc.stderr.decode("utf-8", errors="replace").strip().splitlines()
        said = lines[0] if lines else f"exit {proc.returncode}"
        raise PlaybookNotCommitted(
            f"{path} is untracked: `git show {spec}` in {cwd} found no committed copy "
            f"({said}): working sha256 {working}, committed sha256 none; "
            "commit it on the series branch (§10)"
        )
    committed = hashlib.sha256(proc.stdout).hexdigest()
    if _lf(proc.stdout) != _lf(raw):
        raise PlaybookNotCommitted(
            f"{path} is dirty: it differs from `git show {spec}` in {cwd}: "
            f"working sha256 {working}, committed sha256 {committed}; "
            "commit it or restore the committed copy (§10)"
        )


def _lf(data: bytes) -> bytes:
    """`data` with every CRLF read as LF (§26)."""
    return data.replace(b"\r\n", b"\n")


def parse_playbook(text: str, *, path: Path) -> Playbook:
    """Parse and validate playbook text. Every refusal names what to fix."""
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise PlaybookError(f"{path} is not valid TOML: {exc}") from exc

    _check_keys(data, TOP_KEYS, "the playbook", path)
    version = data.get("version")
    if version != VERSION:
        raise PlaybookError(f"{path}: version must be {VERSION} (§10), got {version!r}")
    series = _series(data.get("series"), path)

    limits = data.get("limits", {})
    if not isinstance(limits, dict):
        raise PlaybookError(f"{path}: [limits] must be a table, got {limits!r}")
    if RETIRED_LIMIT in limits:
        # §11: named, not left to the unknown-key refusal, so an old playbook
        # learns why the key it relied on is gone.
        raise PlaybookError(
            f"{path}: [limits] {RETIRED_LIMIT} is retired (decision 2026-09-12): "
            "notifications are never delayed (§11); remove the key"
        )
    _check_keys(limits, LIMIT_KEYS, "[limits]", path)
    auto_runs = limits.get("auto_runs", [])
    if not isinstance(auto_runs, list) or any(
        isinstance(item, bool) or not isinstance(item, int) for item in auto_runs
    ):
        raise PlaybookError(
            f"{path}: [limits] auto_runs must be a list of run numbers, got {auto_runs!r}"
        )
    max_resumes = limits.get("max_resumes")
    if max_resumes is not None and (
        isinstance(max_resumes, bool) or not isinstance(max_resumes, int) or max_resumes < 0
    ):
        raise PlaybookError(
            f"{path}: [limits] max_resumes must be a non-negative integer, got {max_resumes!r}"
        )

    max_consults = limits.get("max_consults", DEFAULT_MAX_CONSULTS)
    if isinstance(max_consults, bool) or not isinstance(max_consults, int) or max_consults < 0:
        raise PlaybookError(
            f"{path}: [limits] max_consults must be a non-negative integer, got {max_consults!r}"
        )

    # §31: the architect role's own budget, counted per series rather than per
    # mission; U5 spends it, this unit only reads it out of the file.
    architect_consults = limits.get("max_architect_consults", DEFAULT_MAX_ARCHITECT_CONSULTS)
    if (
        isinstance(architect_consults, bool)
        or not isinstance(architect_consults, int)
        or architect_consults < 0
    ):
        raise PlaybookError(
            f"{path}: [limits] max_architect_consults must be a non-negative integer (§31), "
            f"got {architect_consults!r}"
        )

    raw_rules = data.get("rule", [])
    if not isinstance(raw_rules, list) or any(not isinstance(item, dict) for item in raw_rules):
        raise PlaybookError(f"{path}: [[rule]] must be a list of tables, got {raw_rules!r}")
    rules = tuple(
        _rule(index, table, path, auto_runs=tuple(auto_runs))
        for index, table in enumerate(raw_rules)
    )

    return Playbook(
        path=path,
        sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        version=version,
        series=series["name"],
        auto_runs=tuple(auto_runs),
        max_resumes=max_resumes,
        rules=rules,
        kickoff=series["kickoff"],
        max_consults=max_consults,
        architect=series["architect"],
        autonomous=series["autonomous"],
        gate_failures=series["gate_failures"],
        escalate_on=series["escalate_on"],
        max_architect_consults=architect_consults,
    )


def _series(value: Any, path: Path) -> dict[str, Any]:
    """The `[series]` table: `series = "<name>"` (§10's example), or a table of
    `name` and `kickoff` (§26; H-019) and §31's mode and escalation conditions.
    TOML allows the string or the table, never both.

    Every key is decided here, at load, and never when a rule fires — §10's
    discipline, which `run`/`auto_runs` already follows.
    """
    series: dict[str, Any] = {
        "name": None,
        "kickoff": None,
        "architect": DEFAULT_ARCHITECT_MODE,
        "autonomous": False,
        "gate_failures": DEFAULT_GATE_FAILURES,
        "escalate_on": (),
    }
    if value is None:
        return series
    if isinstance(value, str):
        return {**series, "name": value}
    if not isinstance(value, dict):
        raise PlaybookError(
            f"{path}: series must be a string (the series' name) or a [series] table, "
            f"got {value!r}"
        )
    _check_keys(value, SERIES_KEYS, "[series]", path)
    for key in ("name", "kickoff"):
        item = value.get(key)
        if item is None:
            continue
        if not isinstance(item, str):
            raise PlaybookError(f"{path}: [series] {key} must be a string, got {item!r}")
        if not item.strip():
            raise PlaybookError(
                f"{path}: [series] {key} is empty (§20): omit the key or give it a value"
            )
        series[key] = item

    if "architect" in value:
        mode = value["architect"]
        if not isinstance(mode, str) or mode not in ARCHITECT_MODES:
            raise PlaybookError(
                f"{path}: [series] architect must be one of "
                f"{' | '.join(repr(name) for name in ARCHITECT_MODES)} (§31), got {mode!r}"
            )
        series["architect"] = mode

    if "autonomous" in value:
        flag = value["autonomous"]
        if not isinstance(flag, bool):
            raise PlaybookError(
                f"{path}: [series] autonomous must be true or false (§31), got {flag!r}"
            )
        series["autonomous"] = flag

    if "gate_failures" in value:
        failures = value["gate_failures"]
        if isinstance(failures, bool) or not isinstance(failures, int) or failures < 1:
            raise PlaybookError(
                f"{path}: [series] gate_failures must be a positive integer — the number of "
                f"times one roadmap gate may fail in a row (§31), got {failures!r}"
            )
        series["gate_failures"] = failures

    if "escalate_on" in value:
        conditions = value["escalate_on"]
        if not isinstance(conditions, list) or any(
            not isinstance(item, str) for item in conditions
        ):
            raise PlaybookError(
                f"{path}: [series] escalate_on must be a list of condition names (§31), "
                f"got {conditions!r}"
            )
        unknown = [item for item in conditions if item not in ESCALATE_ON]
        if unknown:
            raise PlaybookError(
                f"{path}: [series] escalate_on names {', '.join(repr(u) for u in unknown)}, "
                f"which §31 does not; the conditions are: {', '.join(ESCALATE_ON)}"
            )
        series["escalate_on"] = tuple(conditions)

    return series


def check_series_roles(book: Playbook, config: Config) -> None:
    """§31: `[series] architect = "role"` without `[roles.architect]` is a config error.

    The check cannot live in `load_playbook`: the playbook is a repository file and
    the roles are in `~/.hands/<project>.toml`, and the loader is run by `hands kit
    check` in an architect's sandbox where this laptop's config is not there to read.
    So it lives where a loaded playbook meets a config — the engine's own `_load`,
    and any other caller that has both — and its message names both files, because
    either one of them is the thing to fix.
    """
    if book.architect != "role" or ARCHITECT_ROLE in config.roles:
        return
    raise PlaybookConfigError(
        f'{book.path} sets [series] architect = "role", and {config.path} configures no '
        f"[roles.architect] (§31): add the role's table (cwd = the architect's "
        f'directory), or set [series] architect = "phone"'
    )


def _rule(index: int, table: dict[str, Any], path: Path, *, auto_runs: tuple[int, ...]) -> Rule:
    where = f"{path}: rule {index}"
    if "only_if_run_in" in table:
        # §10 replaced the inferred check with an explicit key (H-006). Naming
        # the replacement here is the point: an old playbook must fail loudly
        # rather than quietly lose the check it thought it had.
        raise PlaybookError(
            f'{where}: only_if_run_in is gone; §10 spells the check as run = "{{n+1}}" — '
            "an expression over the rule's own verdict groups, checked against [limits] "
            "auto_runs"
        )
    _check_keys(table, RULE_KEYS, f"rule {index}", path)

    on = table.get("on")
    if on not in EVENTS:
        raise PlaybookError(
            f"{where}: on must be one of §10's events ({', '.join(EVENTS)}), got {on!r}"
        )
    then = table.get("then")
    if then not in ACTIONS:
        raise PlaybookError(
            f"{where}: then must be one of §10's actions ({', '.join(ACTIONS)}), got {then!r}"
        )

    pattern = table.get("verdict")
    verdict = None
    if pattern is not None:
        if not isinstance(pattern, str):
            raise PlaybookError(f"{where}: verdict must be a regex string, got {pattern!r}")
        try:
            verdict = re.compile(pattern)
        except re.error as exc:
            raise PlaybookError(f"{where}: verdict is not a valid regex: {exc}") from exc

    role = _opt_str(table, "role", where)
    context = _opt_str(table, "context", where)
    prompt = _opt_str(table, "prompt", where)
    message = _opt_str(table, "message", where)
    run = _opt_str(table, "run", where)

    if then == "send":
        if not role:
            raise PlaybookError(f"{where}: a send needs a role (builder or aux)")
        if role not in ("builder", "aux"):
            raise PlaybookError(f"{where}: role must be builder or aux, got {role!r}")
        if not prompt:
            raise PlaybookError(f"{where}: a send needs a prompt")
        context = context or "clear"  # §2's default for a fresh run; §10 is silent
        if context not in CONTEXTS:
            raise PlaybookError(f"{where}: context must be clear or keep, got {context!r}")
    elif then == "notify" and not message:
        raise PlaybookError(f"{where}: a notify needs a message")
    elif then == "consult":
        # §27: hands writes the driver's prompt, to a fresh driver session.
        if on.startswith(f"{DRIVER}."):
            raise PlaybookError(
                f"{where}: a consult on {on} would consult the driver about itself"
            )
        if prompt is not None:
            raise PlaybookError(
                f"{where}: a consult takes no prompt: hands writes the driver's prompt (§27)"
            )
        if role is not None and role != DRIVER:
            raise PlaybookError(f"{where}: a consult's role is driver, got {role!r}")
        if context is not None and context != "clear":
            raise PlaybookError(
                f"{where}: a consult starts a fresh driver session: context is clear, "
                f"got {context!r}"
            )
        role, context = DRIVER, "clear"

    group_names = tuple(verdict.groupindex) if verdict is not None else ()
    for name, text in (("prompt", prompt), ("message", message)):
        if text:
            _check_placeholders(text, group_names, f"{where}: {name}")

    if run is not None:
        if then != "send":
            raise PlaybookError(f"{where}: run belongs on a send, not on a {then}")
        if not auto_runs:
            raise PlaybookError(
                f'{where}: run = "{run}" needs [limits] auto_runs to list the runs hands '
                "may start on its own"
            )
        try:
            ref = run_ref(run)
        except PlaceholderError as exc:
            raise PlaybookError(f"{where}: {exc}") from exc
        if ref.name not in group_names:
            raise PlaybookError(
                f"{where}: run = \"{run}\" reads {ref.text}, which names no group of this "
                f"rule's verdict regex ({', '.join(group_names) or 'the rule has no verdict'})"
            )

    return Rule(
        index=index,
        on=on,
        then=then,
        verdict=verdict,
        role=role,
        context=context,
        prompt=prompt,
        message=message,
        run=run,
    )


def _check_placeholders(text: str, group_names: tuple[str, ...], where: str) -> None:
    """Every placeholder must be resolvable *before* a rule ever fires (§10)."""
    try:
        found = refs(text)
    except PlaceholderError as exc:
        raise PlaybookError(f"{where}: {exc}") from exc
    for ref in found:
        if ref.kind == "job":
            if ref.name not in JOB_PLACEHOLDERS:
                raise PlaybookError(
                    f"{where}: {ref.text} is not one of §10's job fields "
                    f"({', '.join('job.' + name for name in JOB_PLACEHOLDERS)})"
                )
        elif ref.name not in group_names:
            raise PlaybookError(
                f"{where}: {ref.text} names no group of this rule's verdict regex "
                f"({', '.join(group_names) or 'the rule has no verdict'})"
            )


def _check_keys(table: dict[str, Any], allowed: tuple[str, ...], where: str, path: Path) -> None:
    unknown = sorted(set(table) - set(allowed))
    if unknown:
        raise PlaybookError(
            f"{path}: unknown key(s) in {where}: {', '.join(unknown)}; "
            f"known keys are {', '.join(allowed)}"
        )


def _opt_str(table: dict[str, Any], key: str, where: str) -> str | None:
    value = table.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise PlaybookError(f"{where}: {key} must be a string, got {value!r}")
    return value


# ------------------------------------------------------------ pipeline state


@dataclass(frozen=True)
class ConsultAnchor:
    """Where `max_consults` starts counting, and what that was derived from (§31).

    §30 persisted the anchor as a bare timestamp, which read as more than it was.
    Review 14 should-fix 5 asked for both fields on disk: `daemon_start` is the
    `started` of the daemon that first found no anchor — the only field the count
    reads — and `job` is the last job in the spool at that moment, so a human can
    see which side of the anchor a job falls on without guessing from timestamps.

    What this does *not* change, said plainly because it was undisclosed before:
    a `pipeline.json` that was unreadable at start keeps its in-memory anchor and
    any later `_save()` (a pause, a stop) writes that anchor over the file; and a
    deleted or rotated `pipeline.json` has no anchor, so the next daemon start
    becomes one and the count restarts from there. Both remain true.
    """

    daemon_start: str
    job: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"daemon_start": self.daemon_start, "job": self.job}

    @classmethod
    def from_data(cls, data: Any) -> ConsultAnchor | None:
        """The anchor a `pipeline.json` carries, or None when it carries none.

        A file written before §31 holds the bare timestamp string; it is read as a
        daemon start with no job rather than being dropped, which would restart
        the count on the first start after an upgrade.
        """
        if isinstance(data, str):
            return cls(daemon_start=data) if data else None
        if not isinstance(data, dict):
            return None
        started = data.get("daemon_start")
        if not isinstance(started, str) or not started:
            return None
        job = data.get("job")
        return cls(daemon_start=started, job=job if isinstance(job, str) else None)


@dataclass
class PipelineState:
    """What `hands pipeline` reports and a restart must not forget (§4, §10).

    Persisted because a `stop` that a daemon restart forgot would chain runs
    nobody is watching — the opposite of what the stop was for.
    """

    paused: bool = False
    paused_by: str | None = None
    stop_reason: str | None = None
    stopped_at: str | None = None
    last_rule: dict[str, Any] | None = None
    #: The sha256 of the playbook `last_rule` fired under (§10): when a file with
    #: another sha loads, the rule numbers in `last_rule` are not that file's, so
    #: it is cleared.
    last_rule_sha256: str | None = None
    auto_runs_used: list[int] = field(default_factory=list)
    #: §28: every `[series] kickoff` value a loaded playbook has carried, in the
    #: order first seen; `max_consults` counts from a job whose prompt is any.
    kickoffs: list[str] = field(default_factory=list)
    #: §29, §30, §31: the daemon start `max_consults` also counts from, with the
    #: job it was derived from, persisted so a restart mid-mission keeps the count;
    #: set by the first daemon start that finds none (`PlaybookEngine.daemon_start`)
    #: and never moved by a later one.
    consults_since: ConsultAnchor | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "paused": self.paused,
            "paused_by": self.paused_by,
            "stop_reason": self.stop_reason,
            "stopped_at": self.stopped_at,
            "last_rule": self.last_rule,
            "last_rule_sha256": self.last_rule_sha256,
            "auto_runs_used": list(self.auto_runs_used),
            "kickoffs": list(self.kickoffs),
            "consults_since": (
                self.consults_since.to_dict() if self.consults_since is not None else None
            ),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PipelineState:
        last_rule = data.get("last_rule")
        sha = data.get("last_rule_sha256")
        if sha is None and isinstance(last_rule, dict):
            # A state file written before the key existed: the rule record itself
            # carries the sha it fired under, so an older build keeps its rule
            # instead of having it cleared by the first load.
            sha = last_rule.get("playbook_sha256")
        return cls(
            paused=bool(data.get("paused")),
            paused_by=data.get("paused_by"),
            stop_reason=data.get("stop_reason"),
            stopped_at=data.get("stopped_at"),
            last_rule=last_rule,
            last_rule_sha256=sha if isinstance(sha, str) else None,
            auto_runs_used=list(data.get("auto_runs_used") or []),
            kickoffs=[item for item in data.get("kickoffs") or [] if isinstance(item, str)],
            consults_since=ConsultAnchor.from_data(data.get("consults_since")),
        )


# ------------------------------------------------------------------- engine


class PlaybookEngine:
    """§10's automaton: one event in, one rule out, `stop` by default.

    The daemon owns one. Its seams are callables and not the daemon itself,
    so every branch below is drivable without a socket:

    * `send` — `Api.send`, so a job hands starts on its own passes §8's gate
      patterns exactly as a human's send does;
    * `enqueue` — the daemon's queue, for a `resume`, which §6 does not re-gate;
    * `approve` — `Api.decide_from_playbook`, §31's fourth gate authority, used
      for one thing only: a held apply of origin `architect` under a playbook that
      sets `[series] architect = "role"` and `autonomous = true`.
    """

    def __init__(
        self,
        config: Config,
        spool: Spool,
        *,
        send: Callable[..., Awaitable[dict[str, Any]]],
        enqueue: Callable[..., Awaitable[Job]],
        limits: LimitManager | None = None,
        notify: Callable[[str, dict[str, Any]], Any] | None = None,
        approve: Callable[..., Awaitable[dict[str, Any]]] | None = None,
    ) -> None:
        self.config = config
        self.spool = spool
        self.send = send
        self.enqueue = enqueue
        #: §31's seam: `Api.decide_from_playbook`. None in a caller that does not
        #: wire it, which is then a pipeline that cannot approve anything — the
        #: architect's hold stays held and the engine says so.
        self.approve = approve
        #: §6's manager, when there is one: §10's `[limits] max_resumes` overrides
        #: the config's, and the counter both units read is the role's.
        self.limits = limits
        #: U8's ntfy seam (§11): called for a stop and for a `notify` rule.
        self.notify = notify
        self.state_path = spool.root / "pipeline.json"
        #: True when `pipeline.json` exists and could not be read: `daemon_start`
        #: then keeps its anchor in memory rather than overwrite the file.
        self._state_unreadable = False
        self.state = self._read_state()
        self.playbook: Playbook | None = None
        self.load_error: str | None = None
        self._loaded = False
        self._tasks: set[asyncio.Task[None]] = set()

    def daemon_start(self, started: str) -> None:
        """§29, §30: the daemon that owns this engine started at `started`.

        That start is `max_consults`' daemon-start anchor only when `pipeline.json`
        persists none; a persisted anchor wins, so a restart mid-mission does not
        reset the count (REVIEW-13 should-fix 5). The first start is persisted,
        with the last job in the spool at that moment (§31; `ConsultAnchor`).
        """
        if self.state.consults_since is not None:
            return
        jobs = self.spool.list_jobs()
        self.state.consults_since = ConsultAnchor(
            daemon_start=started, job=jobs[-1].id if jobs else None
        )
        if not self._state_unreadable:
            self._save()

    # ------------------------------------------------------------- loading

    async def on_job_start(self, job: Job) -> None:
        """§10: "hands loads the tracked file from `role.cwd` when a job starts".

        And, before that, §10's stop → resume cycle: a `cli`-origin send un-pauses
        the pipeline "only when that job **starts** (a held or queued send changes
        nothing)". The un-pause comes first so that a playbook this load cannot
        read stops the pipeline and stays stopped, instead of being cleared by the
        job that just started.
        """
        log.debug("playbook: reading it for job %s (%s)", job.id, job.role)
        if job.origin in UNPAUSE_ORIGINS:
            self._unpause("start")
        await self._load()

    async def _ensure_loaded(self) -> None:
        if not self._loaded:
            await self._load()

    async def _load(self) -> None:
        path = playbook_path(self.config)
        self._loaded = True
        try:
            book = load_playbook(path, cwd=self.config.role("builder").cwd)
            if book is not None:
                # §31: the one check that needs the playbook *and* the config.
                check_series_roles(book, self.config)
        except PlaybookError as exc:
            self.playbook = None
            self.load_error = str(exc)
            # §10, §25: a dirty or untracked file is refused through this same
            # path — the one `stop()`, its reason naming both sha256s. §31: so is
            # a playbook this project's configuration cannot honour.
            if isinstance(exc, PlaybookNotCommitted):
                what = "is not the committed copy"
            elif isinstance(exc, PlaybookConfigError):
                what = "does not agree with this project's configuration"
            else:
                what = "cannot be read"
            await self.stop(
                f"the playbook {what}, so no rule can be trusted to fire: {exc}",
                {"playbook": str(path)},
            )
            return
        self.load_error = None
        self.playbook = book
        if book is not None and book.kickoff is not None:
            kickoff = book.kickoff.strip()
            if kickoff not in self.state.kickoffs:  # §28: seen in the pipeline's history
                self.state.kickoffs.append(kickoff)
                self._save()
        if book is not None and self.state.last_rule is not None:
            # §10: "`last_rule` is cleared when a different playbook file is
            # loaded" — rule 3 of the file that fired is not rule 3 of this one.
            if book.sha256 != self.state.last_rule_sha256:
                log.info("playbook: a new file (%s); last_rule is cleared", book.sha256[:12])
                self.state.last_rule = None
                self.state.last_rule_sha256 = None
                self._save()
        if book is not None and book.max_resumes is not None and self.limits is not None:
            # §10 lets the playbook set §6's counter; §6 is the one that counts.
            self.limits.max_resumes = book.max_resumes

    @property
    def max_resumes(self) -> int:
        if self.playbook is not None and self.playbook.max_resumes is not None:
            return self.playbook.max_resumes
        if self.limits is not None:
            return self.limits.max_resumes
        return self.config.limits.max_resumes

    # -------------------------------------------------------------- events

    async def on_job(self, job: Job) -> None:
        """A terminal job (§6) as one of §10's events, if it is one.

        A driver job's end is also the end of a consultation (§27): it is filed
        before the event is decided, so a paused pipeline still records it.
        """
        if job.role == DRIVER:
            self._consult_done(job)
        await self.on_event(f"{job.role}.{job.state}", job=job)

    def dispatch(self, event: str, *, payload: dict[str, Any] | None = None) -> None:
        """Fire-and-forget entry for a synchronous caller (the monitor of §5)."""
        if event not in EVENTS:
            return
        task = asyncio.create_task(
            self.on_event(event, payload=payload), name=f"hands-playbook-{event}"
        )
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def on_event(
        self, event: str, *, job: Job | None = None, payload: dict[str, Any] | None = None
    ) -> None:
        """One event, one rule — or a stop (§10)."""
        if event not in EVENTS:
            log.debug("playbook: %s is not one of §10's events; nothing fires", event)
            return
        await self._ensure_loaded()
        if job is None and payload:
            job = self._job(payload.get("job"))
        enforced = driver_stop(event, job)
        if self.state.paused:
            if enforced is not None:
                # §29: the engine's consult stops apply over a paused pipeline too:
                # suppressed like any later stop, and notified, so the human learns
                # the consultation did not resolve. No playbook rule fires (§10).
                await self.stop(enforced, _payload(event, job), notify_suppressed=True)
                return
            log.info("playbook: paused (%s); %s fires nothing", self.state.paused_by, event)
            return
        book = self.playbook
        if book is None:
            if enforced is not None:  # §28: the engine's stop needs no playbook
                await self.stop(enforced, _payload(event, job))
            return  # no playbook: hands runs jobs, nothing chains (§10)
        if event == "job.held" and await self._approve_architect_hold(book, job):
            return  # §31: the engine answered this hold; no rule fires for it
        try:
            await self._match(book, event, job, payload, enforced=enforced)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # a bug here must stop the pipeline, not chain blindly
            log.exception("playbook: %s could not be decided", event)
            await self.stop(
                f"{event}: the playbook engine failed ({type(exc).__name__}: {exc})",
                _payload(event, job),
            )

    async def _match(
        self,
        book: Playbook,
        event: str,
        job: Job | None,
        payload: dict[str, Any] | None,
        *,
        enforced: str | None = None,
    ) -> None:
        candidates = self._engine_rules(book, event) + book.rules_for(event)
        if enforced is not None:
            # §28: the playbook cannot remove this stop. A first matching `stop`
            # rule is the stop, with its message; any other rule does not fire.
            chosen, match = _choose(candidates, job)
            if chosen is not None and chosen.then == "stop":
                await self._fire(chosen, event, job, match)
                return
            extra = {} if chosen is None else {"rule_not_fired": chosen.index}
            await self.stop(enforced, _payload(event, job, **extra))
            return
        if not candidates:
            await self.stop(
                f"{event}: the playbook has no rule for it, and §10 stops for anything "
                "it did not pre-plan",
                _payload(event, job),
            )
            return

        verdict = job.verdict if job is not None else None
        chosen, match = _choose(candidates, job)
        if chosen is None:
            if verdict is None:
                what = (
                    f"job {job.id} has no VERDICT: line" if job is not None else "it carries no job"
                )
                reason = (
                    f"{event}: every rule for it matches on a verdict and {what}; "
                    "§10 stops on a missing or unparseable VERDICT:"
                )
            else:
                reason = f"{event}: no rule matches the verdict {verdict!r}"
            await self.stop(reason, _payload(event, job))
            return

        await self._fire(chosen, event, job, match)

    def _engine_rules(self, book: Playbook, event: str) -> list[Rule]:
        """§31: "a `builder.done` rule the engine adds, not the playbook".

        In role mode with `autonomous`, the engine behaves as if a `builder.done`
        rule on `^VERDICT: kit applied` sending `[series] kickoff` to the builder,
        clear, stood at the top of the file. At the top, and not at the bottom,
        because §10 already decides what happens when two rules match — "the first
        rule whose `on` matches it and whose `verdict` regex matches … fires" —
        and the engine's rule is the one §31 promises will run. Every shipped
        playbook carries a `^VERDICT: kit applied` rule of its own (a `notify`);
        under autonomy that rule does not fire, and the inbox says which rule did
        (`rule: -1`). Outside role mode with `autonomous` the engine adds nothing
        and the playbook's rule is the only one there is.

        The kickoff job's origin is `playbook` (`ORIGIN`), like every other job a
        rule starts: the phone did not send it, the engine did. It therefore does
        not clear a stop (`UNPAUSE_ORIGINS`), and it anchors `max_consults` as any
        kickoff-prompted builder job does (`consults_used`).
        """
        if event != "builder.done" or not book.architect_is_autonomous:
            return []
        if book.kickoff is None:
            # Refused here rather than rendered into an empty prompt: §10 stops
            # for what it cannot do, and the reason names the missing key.
            return [
                Rule(
                    index=ENGINE_RULE_INDEX,
                    on="builder.done",
                    then="stop",
                    verdict=_KIT_APPLIED_RE,
                    message=(
                        "the kit was applied and this playbook, which is autonomous, has no "
                        "[series] kickoff to send next (§31)"
                    ),
                )
            ]
        return [
            Rule(
                index=ENGINE_RULE_INDEX,
                on="builder.done",
                then="send",
                verdict=_KIT_APPLIED_RE,
                role="builder",
                context="clear",
                prompt=book.kickoff,
            )
        ]

    async def _approve_architect_hold(self, book: Playbook, job: Job | None) -> bool:
        """§31: release a held apply the architect filed, `decided_by: playbook`.

        True when the engine answered this `job.held` and no rule should fire for
        it. False when it is not the engine's — another origin, or a playbook that
        is not `architect = "role"` with `autonomous = true` — and the hold then
        takes exactly the path it takes today: the playbook's `job.held` rule if it
        has one, and otherwise a stop, so the human is asked.

        A paused pipeline approves nothing: §10 says a paused pipeline fires
        nothing, and this is the pipeline acting. The human being asked about the
        stop is the human who would decide the hold anyway.
        """
        if job is None or job.origin != ARCHITECT_ORIGIN or not book.architect_is_autonomous:
            return False
        where = _payload("job.held", job)
        if self.approve is None:  # pragma: no cover - wired by the daemon and the tests
            await self.stop(
                f"job.held: {job.id} is the architect's apply under an autonomous playbook "
                "and this engine has no approve seam to release it with (§31)",
                where,
            )
            return True
        try:
            await self.approve(job=job.id, reason=AUTONOMOUS_APPROVAL)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await self.stop(
                f"job.held: the engine could not approve the architect's apply {job.id}: {exc}",
                where,
            )
            return True
        # No inbox event of its own: the decision is recorded exactly as every
        # other gate decision is, by `Api._gate_decided` — one `gate.decided`
        # carrying `decided_by: playbook` and the reason above — and, as today,
        # a gate decision notifies nobody (`daemon.NOTIFY_KINDS`).
        log.info("playbook: approved the architect's apply %s (decided_by: playbook, §31)", job.id)
        return True

    # ------------------------------------------------------------- actions

    async def _fire(
        self, rule: Rule, event: str, job: Job | None, match: re.Match[str] | None
    ) -> None:
        groups = {
            name: value
            for name, value in (match.groupdict() if match is not None else {}).items()
            if value is not None
        }
        try:
            if rule.then == "send":
                await self._act_send(rule, event, job, groups)
            elif rule.then == "resume":
                await self._act_resume(rule, event, job)
            elif rule.then == "notify":
                await self._act_notify(rule, event, job, groups)
            elif rule.then == "consult":
                await self._act_consult(rule, event, job)
            else:
                await self._act_stop(rule, event, job, groups)
        except PlaceholderError as exc:
            await self.stop(f"{event}: rule {rule.index} cannot be rendered: {exc}",
                            _payload(event, job, rule=rule.index))

    async def _act_send(
        self, rule: Rule, event: str, job: Job | None, groups: dict[str, str]
    ) -> None:
        book = self.playbook
        assert book is not None and rule.prompt is not None and rule.role is not None
        prompt = render(rule.prompt, groups=groups, job=job)
        run: int | None = None
        if rule.run is not None:
            run = run_number(rule.run, groups=groups, job=job)
            if run not in book.auto_runs:
                await self.stop(
                    f"{event}: rule {rule.index} would start run {run}, which [limits] "
                    f"auto_runs does not list ({list(book.auto_runs)}); §10 stops for a run "
                    "nobody pre-planned",
                    _payload(event, job, rule=rule.index, run=run),
                )
                return
        try:
            sent = await self.send(
                role=rule.role,
                context=rule.context or "clear",
                prompt=prompt,
                origin=ORIGIN,
                playbook_sha256=book.sha256,
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await self.stop(
                f"{event}: rule {rule.index} could not send to {rule.role}: {exc}",
                _payload(event, job, rule=rule.index),
            )
            return
        if run is not None:
            self.state.auto_runs_used.append(run)
        self._fired(rule, event, job, fired_job=sent.get("id"), prompt=prompt, run=run)

    async def _act_resume(self, rule: Rule, event: str, job: Job | None) -> None:
        book = self.playbook
        assert book is not None
        if job is None:
            await self.stop(
                f"{event}: rule {rule.index} is a resume and the event carries no job to resume",
                _payload(event, job, rule=rule.index),
            )
            return
        if job.state == "limited":
            # §6 owns this one: it waits out the reset first (`hands.limits`).
            # Firing here as well would send two jobs into the same limit.
            self._fired(
                rule,
                event,
                job,
                note="§6 schedules the resume for the limit reset; the rule adds nothing",
            )
            return

        used = self.spool.read_role(job.role).consecutive_resumes
        if used >= self.max_resumes:
            await self.stop(
                f"{event}: {job.role} has already been resumed {used} time(s) with no `done` "
                f"in between and [limits] max_resumes is {self.max_resumes}",
                _payload(event, job, rule=rule.index),
            )
            return

        role = self.config.role(job.role)
        if job.role == "builder":  # §10/§6: the resume line when configured, else the
            prompt, context = role.resume_prompt(job.prompt), "clear"  # same prompt (H-008)
        else:
            prompt, context = job.prompt, job.context
        try:
            resumed = await self.enqueue(
                role=job.role,
                context=context,
                prompt=prompt,
                origin=ORIGIN,
                resumed_from=job.id,
                playbook_sha256=book.sha256,
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await self.stop(
                f"{event}: rule {rule.index} could not resume {job.role}: {exc}",
                _payload(event, job, rule=rule.index),
            )
            return
        self.spool.update_role(job.role, consecutive_resumes=used + 1)
        self.spool.append_event(
            "resume",
            {
                "job": resumed.id,
                "role": job.role,
                "resumed_from": job.id,
                "context": context,
                "origin": ORIGIN,
                "resumes": used + 1,
                "max_resumes": self.max_resumes,
                "rule": rule.index,
            },
        )
        self._fired(rule, event, job, fired_job=resumed.id, prompt=prompt)

    async def _act_consult(self, rule: Rule, event: str, job: Job | None) -> None:
        """§27: start a driver-role job that carries the event, the job record and
        the role's last reply — or stop, when there is no driver, no job, or the
        mission has used its `[limits] max_consults`."""
        book = self.playbook
        assert book is not None
        where = _payload(event, job, rule=rule.index)
        if DRIVER not in self.config.roles:
            await self.stop(
                f"{event}: rule {rule.index} is a consult and this project configures no "
                "[roles.driver] (§27)",
                where,
            )
            return
        if job is None:
            await self.stop(
                f"{event}: rule {rule.index} is a consult and the event carries no job to "
                "consult about",
                where,
            )
            return
        used = self.consults_used(book)
        if used >= book.max_consults:
            await self.stop(
                f"{event}: rule {rule.index} would start consultation {used + 1} of this "
                f"mission and [limits] max_consults is {book.max_consults} (§27)",
                {**where, "consults": used, "max_consults": book.max_consults},
            )
            return
        try:
            started = await self.enqueue(
                role=DRIVER,
                context="clear",
                prompt=consult_prompt(event, job),
                origin=ORIGIN,
                playbook_sha256=book.sha256,
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await self.stop(
                f"{event}: rule {rule.index} could not start the driver: {exc}", where
            )
            return
        self.spool.append_event(
            "consult.sent",
            {
                "job": started.id,
                "about": job.id,
                "role": job.role,
                "event": event,
                "verdict": job.verdict,
                "rule": rule.index,
                "consults": used + 1,
                "max_consults": book.max_consults,
            },
        )
        self._fired(rule, event, job, fired_job=started.id)

    def consults_used(self, book: Playbook | None) -> int:
        """§27, §28: the consultations of this mission — driver jobs (a §6 resume of
        one is not another) after the later of the last builder job whose prompt is
        *any* `[series] kickoff` value seen (`PipelineState.kickoffs`, plus the
        loaded file's) and the last kit apply that ran (a builder job of origin
        `kit` that started), neither a resume. §29, §30, §31: nor before the
        persisted daemon-start anchor (`PipelineState.consults_since.daemon_start`,
        the first daemon start that found none), whichever of the three is latest.
        With none of them, every driver job in the spool counts: the safe direction
        is to stop sooner."""
        jobs = self.spool.list_jobs()
        kickoffs = set(self.state.kickoffs)
        if book is not None and book.kickoff:
            kickoffs.add(book.kickoff.strip())
        start = 0
        for index, record in enumerate(jobs):
            if record.role != "builder" or record.resumed_from is not None:
                continue
            if record.prompt.strip() in kickoffs or (
                record.origin == KIT_ORIGIN and record.started is not None
            ):
                start = index + 1
        # §31: only the anchor's daemon start filters; its `job` is provenance.
        anchor = self.state.consults_since
        since = anchor.daemon_start if anchor is not None else None
        return sum(
            1
            for record in jobs[start:]
            if record.role == DRIVER
            and record.resumed_from is None
            and (since is None or record.created >= since)
        )

    def _consult_done(self, job: Job) -> None:
        """§27: the inbox event and the `meta/journal.md` line of a consultation.

        §28: every end is the end of its consultation, `limited` included (§6 does
        not resume a driver job), and the payload's `state` is that terminal state.
        """
        head = consult_head(job.prompt) or {}
        about = head.get("job")
        event = head.get("event")
        role = head.get("role")
        said = job.verdict if job.verdict is not None else "no VERDICT: line"
        journal = self.config.role("builder").cwd / JOURNAL
        line = (
            f"{now_iso()}  consult {job.id} ({job.state}) on {event} of {role} job {about}: "
            f"{said}"
        )
        payload: dict[str, Any] = {
            "job": job.id,
            "about": about,
            "role": role,
            "event": event,
            "state": job.state,
            "verdict": job.verdict,
            "journal": str(journal),
        }
        try:
            journal.parent.mkdir(parents=True, exist_ok=True)
            with journal.open("a", encoding="utf-8") as handle:
                handle.write(" ".join(line.splitlines()) + "\n")
        except OSError as exc:
            log.warning("playbook: cannot append to %s: %s", journal, exc)
            payload["journal_error"] = str(exc)
        self.spool.append_event("consult.done", payload)

    async def _act_notify(
        self, rule: Rule, event: str, job: Job | None, groups: dict[str, str]
    ) -> None:
        assert rule.message is not None
        message = render(rule.message, groups=groups, job=job)
        payload = self._fired(rule, event, job, message=message)
        self._notify(f"hands: {message}", payload)

    async def _act_stop(
        self, rule: Rule, event: str, job: Job | None, groups: dict[str, str]
    ) -> None:
        if rule.message:
            reason = render(rule.message, groups=groups, job=job)
        else:
            reason = f"{event} matched rule {rule.index}, whose action is stop (§10)"
        self._fired(rule, event, job, message=reason)
        await self.stop(reason, _payload(event, job, rule=rule.index))

    def _fired(
        self,
        rule: Rule,
        event: str,
        job: Job | None,
        *,
        fired_job: str | None = None,
        prompt: str | None = None,
        message: str | None = None,
        run: int | None = None,
        note: str | None = None,
    ) -> dict[str, Any]:
        """§11: "playbook rule fired" — one inbox event per rule that acted."""
        book = self.playbook
        payload = {
            "rule": rule.index,
            "on": event,
            "then": rule.then,
            "playbook_sha256": book.sha256 if book else None,
            "job": job.id if job is not None else None,
            "role": rule.role or (job.role if job is not None else None),
            "fired_job": fired_job,
            "prompt": prompt,
            "message": message,
            "run": run,
            "note": note,
        }
        self.spool.append_event("playbook.rule", payload)
        self.state.last_rule = {**payload, "fired_at": now_iso()}
        self.state.last_rule_sha256 = book.sha256 if book else None
        self._save()
        log.info("playbook: rule %d on %s fired (%s)", rule.index, event, rule.then)
        return payload

    # ------------------------------------------------------ stop and pause

    async def stop(
        self,
        reason: str,
        payload: dict[str, Any] | None = None,
        *,
        notify_suppressed: bool = False,
    ) -> None:
        """§10: pause the pipeline, notify, record the reason (§11's `stop` event).

        This is the one `stop()` §10 asks for: every component stops through it —
        a rule, the engine itself, `hands pause`, and §6's limit manager through
        the daemon's `on_stop` seam — so the rules below hold once, here.

        A stop over a pipeline that is *already* stopped takes nothing: the first
        reason is the one that explains the pipeline and it is kept, with its
        timestamp. The stop that did not take is "recorded in the inbox only" —
        one `pipeline.stop_suppressed` event carrying the reason it would have set
        and the reason that was kept — and notifies nobody, because the human was already
        told. So: one `stop` event and one notification per stop that takes.

        The kind is in the `pipeline` namespace (H-011, §21) so that a
        `hands wait --for stop,held` is not woken by it; `--for pipeline` is how
        a caller asks for them.

        §29: `notify_suppressed` is the one exception, the engine's consult stop over
        a paused pipeline: it is suppressed the same way and also notifies, once.
        """
        if self.state.paused:
            suppressed = {**(payload or {}), "reason": reason, "kept": self.state.stop_reason}
            self.spool.append_event("pipeline.stop_suppressed", suppressed)
            log.info("playbook: stop suppressed (%s); kept: %s", reason, self.state.stop_reason)
            if notify_suppressed:
                self._notify(SUPPRESSED_CONSULT_TITLE, suppressed)
            return
        self.state.paused = True
        self.state.paused_by = "stop"
        self.state.stop_reason = reason
        self.state.stopped_at = now_iso()
        self._save()
        self.spool.append_event("stop", {**(payload or {}), "reason": reason})
        log.warning("playbook: stop — %s", reason)
        self._notify("hands: the pipeline stopped", {**(payload or {}), "reason": reason})

    async def pause(self, *, by: str = "cli") -> dict[str, Any]:
        """`hands pause` (§4): no rule fires until it is resumed.

        `by` is who paused: `cli` for `hands pause`, `phone` for §24's command
        channel, which calls this same method. It is recorded as `paused_by` and
        in the `stop` event's `by`; the API command takes no such argument.

        H-007: a pause is a stop like any other, so it goes through `stop()` —
        the `stop` event of §11 (reason `paused by human`) and its notification,
        not a silent flag. Notifying is what makes `hands pause` the one command
        §11's notification check needs — the check `hands doctor` prints, which
        proves an event reaches the human's phone: no job, no turn, nothing to
        clean up but `hands resume`. No playbook has to be loaded: that check
        runs at install time (§14 step 1).

        §19: a pause over a pipeline *already* stopped — by a rule, by a held job,
        by an earlier pause — is a no-op. The first reason is the one that explains
        the pipeline, so it is kept: no second `stop` event, no second
        notification, and `hands pipeline` keeps showing the original stop instead
        of `paused by human`. The caller is told with `already_stopped` so it can
        print that reason rather than a silent success.

        §10 (v3.3) makes that one case of a general rule, so this pause goes
        through `stop()` like every other: over an existing stop it files the
        `pipeline.stop_suppressed` record and changes nothing else.
        """
        already = self.state.paused
        await self.stop(PAUSE_REASON, {"by": "hands pause" if by == "cli" else by})
        if already:
            return {**self.pipeline(), "already_stopped": True}
        self.state.paused_by = by  # `hands pipeline` still says who paused it
        self._save()
        return self.pipeline()

    async def resume(self) -> dict[str, Any]:
        """`hands resume` (§4, §10's stop → resume cycle)."""
        self._unpause("resume")
        return self.pipeline()

    def _unpause(self, by: str) -> None:
        """Close §10's cycle, and say so in the inbox (§11's `pipeline.resumed`).

        `by` is how it was un-paused, in §10's own two words: `resume` for
        `hands resume`, `start` for a `cli` job starting.

        A pipeline that is not paused has nothing to resume: nothing is written,
        so `hands resume` twice (or on a running pipeline) is not an event storm.
        A resume is not on §11's notification list — the human is the one doing
        it — so it is inboxed and not published.
        """
        if not self.state.paused:
            return
        was = self.state.stop_reason
        self.state.paused = False
        self.state.paused_by = None
        self.state.stop_reason = None
        self.state.stopped_at = None
        self._save()
        self.spool.append_event("pipeline.resumed", {"by": by, "was": was})
        log.info("playbook: un-paused by %s (was: %s)", by, was)

    # ------------------------------------------------------------ reporting

    def pipeline(self) -> dict[str, Any]:
        """§4: the active playbook, paused?, auto-runs, resumes, last rule, stop reason."""
        if not self._loaded:
            # A read-only command must still say what the file on disk is.
            try:
                self.playbook = load_playbook(
                    playbook_path(self.config), cwd=self.config.role("builder").cwd
                )
                self._loaded = True
            except PlaybookError as exc:
                self.load_error = str(exc)
        book = self.playbook
        return {
            "playbook": {
                "path": str(playbook_path(self.config)),
                "sha256": book.sha256 if book else None,
                "series": book.series if book else None,
                "version": book.version if book else None,
                "rules": len(book.rules) if book else 0,
                "loaded": book is not None,
                "error": self.load_error,
                # §31: which architect runs this series, and whether the engine
                # may approve its applies.
                "architect": book.architect if book else DEFAULT_ARCHITECT_MODE,
                "autonomous": bool(book.autonomous) if book else False,
            },
            "paused": self.state.paused,
            "paused_by": self.state.paused_by,
            "stop_reason": self.state.stop_reason,
            "stopped_at": self.state.stopped_at,
            "auto_runs": {
                "allowed": list(book.auto_runs) if book else [],
                "used": list(self.state.auto_runs_used),
            },
            "resumes": {
                "used": {
                    role: self.spool.read_role(role).consecutive_resumes
                    for role in self.config.roles
                },
                "max_resumes": self.max_resumes,
            },
            "consults": {
                "used": self.consults_used(book),
                "max_consults": book.max_consults if book else DEFAULT_MAX_CONSULTS,
            },
            "last_rule": self._shown_last_rule(book),
        }

    def _shown_last_rule(self, book: Playbook | None) -> dict[str, Any] | None:
        """`last_rule`, marked `stale: true` when it is not the loaded file's (§21).

        `_load` *clears* the record when a playbook with another sha loads (§10),
        and that load happens when a job starts. `hands pipeline` is read-only on
        a daemon that may not have started one yet: its own lazy load reads the
        new file, so without this the command prints the old file's rule numbers
        next to the new file's sha (review 4 should-fix 7). Marking is what a
        display may do; clearing stays with the load. When no playbook could be
        read there is no sha to compare against, so the record is shown as it is.
        """
        rule = self.state.last_rule
        if rule is None or book is None or book.sha256 == self.state.last_rule_sha256:
            return rule
        return {**rule, "stale": True}

    # ------------------------------------------------------------- plumbing

    def _notify(self, title: str, payload: dict[str, Any]) -> None:
        if self.notify is None:
            return
        outcome = self.notify(title, payload)
        if inspect.isawaitable(outcome):  # pragma: no cover - U8's seam may be async
            task = asyncio.create_task(_await(outcome), name="hands-playbook-notify")
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)

    def _job(self, job_id: Any) -> Job | None:
        if not isinstance(job_id, str):
            return None
        try:
            return self.spool.load_job(job_id)
        except SpoolError:  # pragma: no cover - the event names a job that is gone
            return None

    def _read_state(self) -> PipelineState:
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return PipelineState()
        except (OSError, json.JSONDecodeError) as exc:
            # Safe direction: a state file hands cannot read is a paused pipeline,
            # never a running one.
            log.error("playbook: %s is not readable (%s); the pipeline stays paused",
                      self.state_path, exc)
            self._state_unreadable = True
            return PipelineState(
                paused=True,
                paused_by="stop",
                stop_reason=f"the pipeline state file {self.state_path} is not readable: {exc}",
                stopped_at=now_iso(),
            )
        if not isinstance(data, dict):  # pragma: no cover - hand-edited file
            return PipelineState()
        return PipelineState.from_dict(data)

    def _save(self) -> None:
        atomic_write(self.state_path, json.dumps(self.state.to_dict(), indent=2, sort_keys=True))

    async def drain(self) -> None:
        """Wait for every dispatched event to have been decided. For tests and shutdown."""
        while True:
            pending = [task for task in self._tasks if not task.done()]
            if not pending:
                await asyncio.sleep(0)
                return
            await asyncio.gather(*pending, return_exceptions=True)

    def cancel_all(self) -> None:
        """Drop every event still being decided — the daemon is going down (§3)."""
        for task in list(self._tasks):
            task.cancel()
        self._tasks.clear()


async def _await(outcome: Any) -> None:  # pragma: no cover - U8's seam may be async
    await outcome


def _choose(rules: list[Rule], job: Job | None) -> tuple[Rule | None, re.Match[str] | None]:
    """§10: the first rule whose verdict regex matches (or that has none), top to bottom."""
    verdict = job.verdict if job is not None else None
    for rule in rules:
        if rule.verdict is None:
            return rule, None
        if verdict is None:
            continue
        found = rule.verdict.search(verdict)
        if found is not None:
            return rule, found
    return None, None


def driver_stop(event: str, job: Job | None) -> str | None:
    """§27, §28: the stop reason the engine enforces for a driver event, or None
    for a `driver.done` whose verdict is `VERDICT: resolved …` (and every event
    that is not a driver's)."""
    role, _, state = event.partition(".")
    if role != DRIVER:
        return None
    if state in DRIVER_STOP_STATES:
        return (
            f"{event}: the consultation's driver job ended {state}, and a consultation "
            "that does not end resolved stops (§27, §28)"
        )
    verdict = job.verdict if job is not None else None
    if verdict is None:
        return f"{event}: the driver's reply has no VERDICT: line, so it stops (§27, §28)"
    if _RESOLVED_RE.match(verdict):
        return None
    escalated = _ESCALATE_RE.match(verdict)
    if escalated is not None:
        reason = escalated.group("reason") or "(no reason given)"
        return f"{event}: the driver escalated: {reason} (§27, §28)"
    return (
        f"{event}: the driver's verdict {verdict!r} is neither resolved nor escalate, "
        "so it stops (§27, §28)"
    )


def consult_head(prompt: str) -> dict[str, str] | None:
    """The consult prompt's first line read back — `event`, `job`, and `role`, the
    role the consultation names (§27, §28) — or None for a prompt that is not one."""
    head = _CONSULT_HEAD_RE.search(prompt)
    return None if head is None else head.groupdict()


def consult_prompt(event: str, job: Job) -> str:
    """§27: what a `consult` sends the driver role — the event, the job record
    (id, role, state, verdict) and the role's last reply, verbatim, with the
    question and the two VERDICT lines the reply must begin with."""
    verdict = job.verdict if job.verdict is not None else "(none: the reply has no VERDICT: line)"
    result = job.result if job.result is not None else ""
    return (
        f"hands consult: {event} on job {job.id} (role {job.role})\n"
        "\n"
        "handsd started you as the driver role to resolve one consultation (DESIGN §27).\n"
        "\n"
        f"Event: {event}\n"
        f"Job: {job.id}\n"
        f"Role: {job.role}\n"
        f"State: {job.state}\n"
        f"Verdict: {verdict}\n"
        f"The full record: hands show {job.id}\n"
        "\n"
        "The role's last reply (the job's result), verbatim between the markers:\n"
        "----- BEGIN REPLY -----\n"
        f"{result}\n"
        "----- END REPLY -----\n"
        "\n"
        f"The question: {CONSULT_QUESTION}.\n"
        f"To answer the {job.role}, send it `hands send --role {job.role} --context keep` "
        "with your answer; that is the only send you may make.\n"
        "\n"
        "Your reply's first line is exactly one of:\n"
        "\n"
        + "".join(f"    {line}\n" for line in DRIVER_VERDICTS)
    )


def _payload(event: str, job: Job | None, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"event": event}
    if job is not None:
        payload["job"] = job.id
        payload["role"] = job.role
        payload["verdict"] = job.verdict
    return {**payload, **extra}
