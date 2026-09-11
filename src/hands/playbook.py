"""The playbook — the architect's pre-planned steps, run without a human (DESIGN §10).

    PLAYBOOK.toml (in the builder's repo, on the series branch)
      └─ [[rule]] on = <event> [verdict = <regex>] then = send|resume|notify|stop

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
  **is**: the engine stops rather than fire a rule out of a half-read file.
* the engine never spawns anything itself. `send` goes through the same API
  method `hands send` uses, so §8's gate patterns still apply to a job hands
  starts on its own; `resume` goes through the daemon's queue directly, like
  §6's limit resume, which is never re-gated.
* a `limited` job's resume belongs to §6 (`hands.limits`), which waits out the
  reset first. A `then = "resume"` rule on `builder.limited` therefore records
  that the rule fired and leaves the scheduling alone: firing a second resume
  here would send two jobs into the same limit.
"""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import logging
import re
import tomllib
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from hands.config import Config
from hands.limits import LimitManager
from hands.spool import Job, Spool, SpoolError, atomic_write, now_iso

__all__ = [
    "ACTIONS",
    "EVENTS",
    "JOB_PLACEHOLDERS",
    "ORIGIN",
    "PipelineState",
    "PlaceholderError",
    "Playbook",
    "PlaybookEngine",
    "PlaybookError",
    "Rule",
    "load_playbook",
    "parse_playbook",
    "playbook_path",
    "render",
    "run_number",
]

log = logging.getLogger("hands.playbook")

#: §10's "Events", in the order §10 lists them. Closed: an event outside this
#: list is not a playbook event and fires nothing (a `killed` job, for one, is a
#: human's own `hands cancel`, and the human already knows).
EVENTS: tuple[str, ...] = (
    "builder.done",
    "builder.failed",
    "builder.limited",
    "builder.orphaned",
    "aux.done",
    "aux.failed",
    "monitor.stall",
    "monitor.tripwire",
    "job.held",
    "job.denied",
)

#: §10's "Actions".
ACTIONS: tuple[str, ...] = ("send", "resume", "notify", "stop")

#: §10's "Placeholders": the job fields a rule may name as `{job.<field>}`.
JOB_PLACEHOLDERS: tuple[str, ...] = ("id", "head_at_start", "head_at_end", "session_id")

#: §6's origin vocabulary. Every job the engine fires carries this one.
ORIGIN = "playbook"

TOP_KEYS: tuple[str, ...] = ("version", "series", "limits", "rule")
LIMIT_KEYS: tuple[str, ...] = ("auto_runs", "max_resumes", "quiet_hours")
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
    quiet_hours: str | None
    rules: tuple[Rule, ...]

    def rules_for(self, event: str) -> list[Rule]:
        """Every rule on `event`, in file order — §10 reads top to bottom."""
        return [rule for rule in self.rules if rule.on == event]


def playbook_path(config: Config) -> Path:
    """§10, §13: `<roles.builder.cwd>/<playbook.path>`."""
    return config.role("builder").cwd / config.playbook.path


def load_playbook(path: Path) -> Playbook | None:
    """The playbook at `path`, or None when there is no file there (§10).

    A missing playbook is not an error: hands runs jobs, nothing chains. Every
    other problem is a `PlaybookError` — a half-read file must never fire a rule.
    """
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise PlaybookError(f"cannot read the playbook {path}: {exc}") from exc
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PlaybookError(f"{path} is not valid UTF-8: {exc}") from exc
    return parse_playbook(text, path=path)


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
    series = data.get("series")
    if series is not None and not isinstance(series, str):
        raise PlaybookError(f"{path}: series must be a string, got {series!r}")

    limits = data.get("limits", {})
    if not isinstance(limits, dict):
        raise PlaybookError(f"{path}: [limits] must be a table, got {limits!r}")
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
    quiet_hours = limits.get("quiet_hours")
    if quiet_hours is not None and not isinstance(quiet_hours, str):
        raise PlaybookError(f"{path}: [limits] quiet_hours must be a string, got {quiet_hours!r}")

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
        series=series,
        auto_runs=tuple(auto_runs),
        max_resumes=max_resumes,
        quiet_hours=quiet_hours,
        rules=rules,
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
    auto_runs_used: list[int] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "paused": self.paused,
            "paused_by": self.paused_by,
            "stop_reason": self.stop_reason,
            "stopped_at": self.stopped_at,
            "last_rule": self.last_rule,
            "auto_runs_used": list(self.auto_runs_used),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PipelineState:
        return cls(
            paused=bool(data.get("paused")),
            paused_by=data.get("paused_by"),
            stop_reason=data.get("stop_reason"),
            stopped_at=data.get("stopped_at"),
            last_rule=data.get("last_rule"),
            auto_runs_used=list(data.get("auto_runs_used") or []),
        )


# ------------------------------------------------------------------- engine


class PlaybookEngine:
    """§10's automaton: one event in, one rule out, `stop` by default.

    The daemon owns one. Its two seams are callables and not the daemon itself,
    so every branch below is drivable without a socket:

    * `send` — `Api.send`, so a job hands starts on its own passes §8's gate
      patterns exactly as a human's send does;
    * `enqueue` — the daemon's queue, for a `resume`, which §6 does not re-gate.
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
    ) -> None:
        self.config = config
        self.spool = spool
        self.send = send
        self.enqueue = enqueue
        #: §6's manager, when there is one: §10's `[limits] max_resumes` overrides
        #: the config's, and the counter both units read is the role's.
        self.limits = limits
        #: U8's ntfy seam (§11): called for a stop and for a `notify` rule.
        self.notify = notify
        self.state_path = spool.root / "pipeline.json"
        self.state = self._read_state()
        self.playbook: Playbook | None = None
        self.load_error: str | None = None
        self._loaded = False
        self._tasks: set[asyncio.Task[None]] = set()

    # ------------------------------------------------------------- loading

    async def on_job_start(self, job: Job) -> None:
        """§10: "hands loads the tracked file from `role.cwd` when a job starts"."""
        log.debug("playbook: reading it for job %s (%s)", job.id, job.role)
        await self._load()

    async def _ensure_loaded(self) -> None:
        if not self._loaded:
            await self._load()

    async def _load(self) -> None:
        path = playbook_path(self.config)
        self._loaded = True
        try:
            book = load_playbook(path)
        except PlaybookError as exc:
            self.playbook = None
            self.load_error = str(exc)
            await self.stop(
                f"the playbook cannot be read, so no rule can be trusted to fire: {exc}",
                {"playbook": str(path)},
            )
            return
        self.load_error = None
        self.playbook = book
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
        """A terminal job (§6) as one of §10's events, if it is one."""
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
        if self.state.paused:
            log.info("playbook: paused (%s); %s fires nothing", self.state.paused_by, event)
            return
        book = self.playbook
        if book is None:
            return  # no playbook: hands runs jobs, nothing chains (§10)
        if job is None and payload:
            job = self._job(payload.get("job"))
        try:
            await self._match(book, event, job, payload)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # a bug here must stop the pipeline, not chain blindly
            log.exception("playbook: %s could not be decided", event)
            await self.stop(
                f"{event}: the playbook engine failed ({type(exc).__name__}: {exc})",
                _payload(event, job),
            )

    async def _match(
        self, book: Playbook, event: str, job: Job | None, payload: dict[str, Any] | None
    ) -> None:
        candidates = book.rules_for(event)
        if not candidates:
            await self.stop(
                f"{event}: the playbook has no rule for it, and §10 stops for anything "
                "it did not pre-plan",
                _payload(event, job),
            )
            return

        verdict = job.verdict if job is not None else None
        chosen: Rule | None = None
        match: re.Match[str] | None = None
        for rule in candidates:  # §10 reads top to bottom: the first match wins
            if rule.verdict is None:
                chosen = rule
                break
            if verdict is None:
                continue
            found = rule.verdict.search(verdict)
            if found is not None:
                chosen, match = rule, found
                break

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
        self._save()
        log.info("playbook: rule %d on %s fired (%s)", rule.index, event, rule.then)
        return payload

    # ------------------------------------------------------ stop and pause

    async def stop(
        self, reason: str, payload: dict[str, Any] | None = None, *, write_event: bool = True
    ) -> None:
        """§10: pause the pipeline, notify, record the reason (§11's `stop` event).

        `write_event=False` is for §6's limit manager, which has already written
        its own `stop` event before calling this through its `on_stop` seam.
        """
        if self.state.paused and self.state.stop_reason == reason:
            return  # already stopped for this; one stop, one notification
        self.state.paused = True
        self.state.paused_by = "stop"
        self.state.stop_reason = reason
        self.state.stopped_at = now_iso()
        self._save()
        if write_event:
            self.spool.append_event("stop", {**(payload or {}), "reason": reason})
        log.warning("playbook: stop — %s", reason)
        self._notify("hands: the pipeline stopped", {**(payload or {}), "reason": reason})

    async def pause(self) -> dict[str, Any]:
        """`hands pause` (§4): no rule fires until it is resumed."""
        self.state.paused = True
        self.state.paused_by = "cli"
        self._save()
        log.info("playbook: paused by hand")
        return self.pipeline()

    async def resume(self) -> dict[str, Any]:
        """`hands resume` (§4, §10's stop → resume cycle)."""
        self._unpause("hands resume")
        return self.pipeline()

    async def on_send(self, origin: str) -> None:
        """§10: "`hands resume` or the next `send` un-pauses the pipeline"."""
        if origin == ORIGIN or not self.state.paused:
            return
        self._unpause("a send")

    def _unpause(self, by: str) -> None:
        was = self.state.stop_reason
        self.state.paused = False
        self.state.paused_by = None
        self.state.stop_reason = None
        self.state.stopped_at = None
        self._save()
        log.info("playbook: un-paused by %s (was: %s)", by, was)

    # ------------------------------------------------------------ reporting

    def pipeline(self) -> dict[str, Any]:
        """§4: the active playbook, paused?, auto-runs, resumes, last rule, stop reason."""
        if not self._loaded:
            # A read-only command must still say what the file on disk is.
            try:
                self.playbook = load_playbook(playbook_path(self.config))
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
            "last_rule": self.state.last_rule,
        }

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


def _payload(event: str, job: Job | None, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"event": event}
    if job is not None:
        payload["job"] = job.id
        payload["role"] = job.role
        payload["verdict"] = job.verdict
    return {**payload, **extra}
