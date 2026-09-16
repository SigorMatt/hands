"""U7: the playbook engine (DESIGN §10; also §4, §6, §11, §13).

Two levels, and both are needed:

* the engine on its own — parsing, placeholders, and the rule table — driven
  through `PlaybookEngine` with recording seams, so every `stop` of §10 can be
  provoked in one line;
* the whole of §10's example playbook, verbatim from the design, driven end to
  end over a real daemon and `tests/fake_claude.py`: run finished → review sent
  → blockers=0 → run 3 sent → run 4 is not in `auto_runs` → stop.

Nothing here mocks hands. The only stand-in is the `claude` binary.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import subprocess
import time
import tomllib
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import pytest

import hands.runner as hands_runner
from conftest import commit_file, strip_paths
from hands.api import ApiError
from hands.cli import _pipeline_block
from hands.config import Config, load_config, parse_config
from hands.daemon import Daemon
from hands.gates import DECIDERS
from hands.kit import Apply, apply_params
from hands.playbook import (
    ACTIONS,
    ARCHITECT,
    ARCHITECT_INSTRUCTION,
    ARCHITECT_VERDICTS,
    AUTONOMOUS_APPROVAL,
    CONSULT_EVENTS,
    CONSULT_QUESTION,
    CONSULT_ROLES,
    DEFAULT_MAX_ARCHITECT_CONSULTS,
    DRIVER_VERDICTS,
    ENGINE_RULE_INDEX,
    ESCALATE_ON,
    EVENTS,
    JOB_PLACEHOLDERS,
    LIMIT_KEYS,
    ROADMAP,
    PipelineState,
    PlaceholderError,
    PlaybookEngine,
    PlaybookError,
    check_series_roles,
    consult_prompt,
    load_playbook,
    next_milestone,
    parse_playbook,
    playbook_path,
    render,
)
from hands.spool import Job, Spool, new_kit_id, now_iso
from harness import (
    PROJECT,
    UNCHECKED_KIT,
    architect_table,
    cli,
    config_body,
    drive,
    kit_zip,
    ok,
    passing_kit,
    poll,
    running_job,
    write_project,
)

DESIGN = Path(__file__).parents[1] / "DESIGN.md"
EXAMPLE_FIXTURE = Path(__file__).parent / "fixtures" / "playbook_example.toml"
EXAMPLE = EXAMPLE_FIXTURE.read_text(encoding="utf-8")
#: §10's review prompt since v3.6: the reviewer computes the base, so the example
#: names no `{job.head_at_start}` (§23); the placeholder is tested on its own below.
REVIEW_PROMPT = "Review WORKPLAN.md commits since the last review: commit on the branch"
PAUSE_REASON = "paused by human"


# ------------------------------------------------------------------ fixtures


@pytest.fixture
def workdir(tmp_path: Path) -> Path:
    d = tmp_path / "work"
    d.mkdir(exist_ok=True)
    return d


def git_repo(path: Path) -> str:
    """A one-commit repo, so `{job.head_at_start}` has something real to render."""
    env = {
        "PATH": "/usr/bin:/bin:/usr/local/bin",
        "HOME": str(path),
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@e",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@e",
    }
    subprocess.run(["git", "init", "-q", str(path)], check=True, env=env)
    (path / "WORKPLAN.md").write_text("run 2\nrun 3\n")
    subprocess.run(["git", "-C", str(path), "add", "-A"], check=True, env=env)
    subprocess.run(["git", "-C", str(path), "commit", "-qm", "plan"], check=True, env=env)
    head = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    )
    return head.stdout.strip()


def make_config(
    tmp_home: Path,
    workdir: Path,
    *,
    builder: dict[str, Any] | None = None,
    driver: Path | None = None,
    architect: Path | None = None,
) -> Config:
    roles: dict[str, Any] = {
        "builder": {"cwd": str(workdir), **(builder or {})},
        "aux": {"cwd": str(workdir)},
    }
    if driver is not None:
        roles["driver"] = {"cwd": str(driver)}  # §27
    if architect is not None:
        roles["architect"] = {"cwd": str(architect)}  # §31
    return parse_config(
        {"roles": roles},
        project=PROJECT,
        path=tmp_home / ".hands" / f"{PROJECT}.toml",
    )


class Recorder:
    """The engine's two seams: what it sent, and what it enqueued (§6, §8)."""

    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []
        self.enqueued: list[dict[str, Any]] = []
        self.notified: list[tuple[str, dict[str, Any]]] = []
        self.approved: list[dict[str, Any]] = []
        #: §33: the holds the engine denied (`Api.deny_from_playbook`).
        self.denied: list[dict[str, Any]] = []
        self.refuse: str | None = None
        #: §31: what `Api.decide_from_playbook` would raise, when it would.
        self.refuse_approve: str | None = None

    async def send(self, **fields: Any) -> dict[str, Any]:
        if self.refuse:
            raise RuntimeError(self.refuse)
        self.sent.append(fields)
        return {"id": f"sent-{len(self.sent)}", **fields}

    async def enqueue(self, **fields: Any) -> Job:
        self.enqueued.append(fields)
        return Job(
            id=f"enq-{len(self.enqueued)}",
            role=fields["role"],
            context=fields["context"],
            state="queued",
            created="now",
            origin=fields["origin"],
            prompt=fields["prompt"],
        )

    async def approve(self, *, job: str, reason: str | None = None) -> dict[str, Any]:
        if self.refuse_approve:
            raise RuntimeError(self.refuse_approve)
        self.approved.append({"job": job, "reason": reason})
        return {"id": job, "state": "queued"}

    async def deny(self, *, job: str, reason: str | None = None) -> dict[str, Any]:
        self.denied.append({"job": job, "reason": reason})
        return {"id": job, "state": "denied"}

    def notify(self, title: str, payload: dict[str, Any]) -> None:
        self.notified.append((title, payload))


def engine_for(
    tmp_home: Path,
    workdir: Path,
    body: str | None = EXAMPLE,
    *,
    builder: dict[str, Any] | None = None,
    driver: Path | None = None,
    architect: Path | None = None,
) -> tuple[PlaybookEngine, Recorder]:
    if body is not None:
        commit_file(workdir, "PLAYBOOK.toml", body)  # §10: only the committed file loads
    config = make_config(
        tmp_home, workdir, builder=builder, driver=driver, architect=architect
    )
    recorder = Recorder()
    engine = PlaybookEngine(
        config,
        Spool(tmp_home / ".hands"),
        send=recorder.send,
        enqueue=recorder.enqueue,
        notify=recorder.notify,
        approve=recorder.approve,
        deny=recorder.deny,
    )
    return engine, recorder


def finished(
    spool: Spool,
    *,
    role: str = "builder",
    state: str = "done",
    verdict: str | None = None,
    origin: str = "cli",
    **kw: Any,
) -> Job:
    """A terminal job record in the spool, as the runner would leave it (§6)."""
    job = spool.create_job(role=role, context="clear", prompt="p", origin=origin)
    spool.transition(job, "running")
    return spool.transition(job, state, verdict=verdict, result=verdict, **kw)


def run(coro: Awaitable[Any]) -> Any:
    return asyncio.run(coro)  # type: ignore[arg-type]


# ------------------------------------------- the example playbook is the design's


def test_the_fixture_is_section_10s_example_verbatim() -> None:
    """§10's example is the acceptance criterion, so it is the design's own bytes."""
    lines = DESIGN.read_text(encoding="utf-8").splitlines()
    start = lines.index("### Example (spanweave audit-fix series)") + 1
    block: list[str] = []
    for line in lines[start:]:
        if line.strip() and not line.startswith("    "):
            break
        block.append(line[4:] if line.startswith("    ") else line)
    assert "\n".join(block).strip() == EXAMPLE.strip()


def test_the_example_parses_into_the_rules_of_section_10(tmp_home: Path, workdir: Path) -> None:
    book = parse_playbook(EXAMPLE, path=workdir / "PLAYBOOK.toml")
    assert book.version == 1
    assert book.series == "audit-fixes"
    assert book.auto_runs == (2, 3)
    assert book.max_resumes == 3
    assert [(rule.on, rule.then) for rule in book.rules] == [
        ("builder.done", "send"),
        ("aux.done", "send"),
        ("aux.done", "stop"),
        ("builder.done", "stop"),
        ("builder.orphaned", "resume"),
        ("builder.failed", "resume"),
        ("monitor.tripwire", "stop"),
        ("monitor.task_killed", "stop"),
        ("monitor.orphan_processes", "stop"),
    ]
    assert book.rules[1].run == "{n+1}"
    assert book.rules[1].role == "builder"
    assert book.rules[1].context == "clear"
    assert book.rules[2].message == "Review of run {n} has blockers"
    assert book.sha256 == hashlib.sha256(EXAMPLE.encode()).hexdigest()


def test_the_repositorys_own_playbook_loads_and_its_review_reads_from_the_last_review() -> None:
    """§23, review 6's scope note: the root `PLAYBOOK.toml` goes through the real
    loader, and the rule that sends the cold review names its base as the last
    `review:` commit, never `{job.head_at_start}` of the job that finished — a
    resumed mission's last job starts mid-mission."""
    path = Path(__file__).parents[1] / "PLAYBOOK.toml"
    book = load_playbook(path)
    assert book is not None, "the repository's PLAYBOOK.toml is missing"
    assert book == parse_playbook(path.read_text(encoding="utf-8"), path=path)
    reviews = [
        rule for rule in book.rules if rule.then == "send" and rule.role == "aux"
    ]
    assert len(reviews) == 1, f"expected one review send, got {reviews}"
    prompt = reviews[0].prompt
    assert prompt is not None
    assert "head_at_start" not in strip_paths(prompt)
    assert "every commit after the last review: commit" in strip_paths(prompt)
    assert "meta/REVIEW-PROTOCOL.md" in strip_paths(prompt)


def test_the_repositorys_own_playbook_carries_the_series_kickoff() -> None:
    """§26 (mission 10 U2): the root playbook names its kickoff line in `[series]`.
    §27 Conventions, §32 (mission 16 U6): it is the next mission's line, BUILDER-17.
    §31: this repository runs a phone architect, and says so — `architect = "phone"`
    is the default, written out, and it is the only §31 key the table sets."""
    path = Path(__file__).parents[1] / "PLAYBOOK.toml"
    book = load_playbook(path)
    assert book is not None, "the repository's PLAYBOOK.toml is missing"
    assert book.series == "hands-missions"
    assert book.kickoff == (
        "Read meta/BUILDER-17-PROMPT.md and execute the mission below its divider."
    )
    assert book.architect == "phone"
    assert book.autonomous is False
    table = tomllib.loads(path.read_text(encoding="utf-8"))["series"]
    assert table["architect"] == "phone", "stated explicitly, not left to the default"
    assert sorted(table) == ["architect", "kickoff", "name"]


ROOT_PLAYBOOK = Path(__file__).parents[1] / "PLAYBOOK.toml"


def test_the_repositorys_own_playbook_consults_the_driver_on_questions_only_from_the_builder(
) -> None:
    """§27 Conventions (mission 11 U6): `max_consults = 2`; `builder.done` with
    `^VERDICT: question` and the unrecognised-verdict catch-all route to `consult`
    after every recognised builder verdict; `driver.done` resolved → notify,
    escalate → stop with the reason, anything else and `driver.failed` → stop; no
    other event consults. Read through the real loader."""
    book = load_playbook(ROOT_PLAYBOOK)
    assert book is not None, "the repository's PLAYBOOK.toml is missing"
    assert book.max_consults == 2
    builder = [
        (rule.verdict.pattern if rule.verdict else None, rule.then)
        for rule in book.rules_for("builder.done")
    ]
    assert builder == [
        (r"^VERDICT: mission (?P<n>\d+) finished", "send"),
        ("^VERDICT: kit applied", "notify"),
        (r"^VERDICT: mission (?P<n>\d+) blocked", "stop"),
        ("^VERDICT: question", "consult"),
        ("^VERDICT:", "consult"),
    ]
    for rule in book.rules_for("builder.done")[3:]:
        assert rule.role in (None, "driver") and rule.prompt is None
    driver = [
        (rule.verdict.pattern if rule.verdict else None, rule.then, rule.message)
        for rule in book.rules_for("driver.done")
    ]
    assert [(pattern, then) for pattern, then, _ in driver] == [
        ("^VERDICT: resolved (?P<what>.+)", "notify"),
        ("^VERDICT: escalate (?P<reason>.+)", "stop"),
        (None, "stop"),
    ]
    assert driver[1][2] == "The driver escalated: {reason}"
    assert [rule.then for rule in book.rules_for("driver.failed")] == ["stop"]
    assert {rule.on for rule in book.rules if rule.then == "consult"} == {"builder.done"}


@pytest.mark.parametrize(
    ("verdict", "sent", "enqueued", "paused", "reason"),
    [
        ("VERDICT: mission 12 finished", ["aux"], [], False, None),
        ("VERDICT: kit applied abc123", [], [], False, None),
        ("VERDICT: mission 12 blocked U3", [], [], True, "Mission 12 blocked"),
        ("VERDICT: question which section?", [], ["driver"], False, None),
        ("VERDICT: mission 12 half done", [], ["driver"], False, None),
        (None, [], [], True, "has no VERDICT: line"),
    ],
)
def test_the_repositorys_own_playbook_routes_builder_verdicts(
    tmp_home: Path,
    workdir: Path,
    verdict: str | None,
    sent: list[str],
    enqueued: list[str],
    paused: bool,
    reason: str | None,
) -> None:
    """§27, §10 (mission 11 U6): the root playbook's text through the engine. A
    question and an unrecognised verdict consult the driver; a reply with no
    `VERDICT:` line still stops (§10), because the catch-all matches on `^VERDICT:`."""
    body = ROOT_PLAYBOOK.read_text(encoding="utf-8")
    engine, recorder = engine_for(tmp_home, workdir, body, driver=workdir.parent / "d")
    run(engine.on_job(finished(engine.spool, verdict=verdict)))
    assert [fields["role"] for fields in recorder.sent] == sent
    assert [fields["role"] for fields in recorder.enqueued] == enqueued
    assert engine.state.paused is paused, engine.state.stop_reason
    if reason is not None:
        assert reason in strip_paths(engine.state.stop_reason or "")


@pytest.mark.parametrize(
    ("state", "verdict", "paused", "reason"),
    [
        ("done", "VERDICT: resolved sent keep, DESIGN §27", False, None),
        ("done", "VERDICT: escalate needs a design change", True, "needs a design change"),
        ("done", "VERDICT: maybe", True, None),
        ("failed", None, True, None),
    ],
)
def test_the_repositorys_own_playbook_follows_up_the_driver(
    tmp_home: Path, workdir: Path, state: str, verdict: str | None, paused: bool,
    reason: str | None,
) -> None:
    """§27 (mission 11 U6): resolved notifies; escalate, anything else and a failed
    driver job stop; a follow-up never starts another job."""
    body = ROOT_PLAYBOOK.read_text(encoding="utf-8")
    engine, recorder = engine_for(tmp_home, workdir, body, driver=workdir.parent / "d")
    about = finished(engine.spool, verdict="VERDICT: question x")
    run(engine.on_job(_driver_job(engine.spool, state=state, verdict=verdict, about=about)))
    assert engine.state.paused is paused, engine.state.stop_reason
    if reason is not None:
        assert reason in strip_paths(engine.state.stop_reason or "")
    assert recorder.sent == [] and recorder.enqueued == []


@pytest.mark.parametrize(
    ("event", "role", "state", "verdict"),
    [
        ("aux.done", "aux", "done", "VERDICT: review mission 11 blockers=0 should-fix=0"),
        ("aux.done", "aux", "done", "VERDICT: review mission 11 blockers=2 should-fix=1"),
        ("aux.done", "aux", "done", "VERDICT: something"),
        ("aux.failed", "aux", "failed", None),
    ],
)
def test_the_repositorys_own_playbook_never_consults_on_a_review(
    tmp_home: Path, workdir: Path, event: str, role: str, state: str, verdict: str | None
) -> None:
    """§27: never review outcomes, never `aux.done`: each stops, no driver job."""
    body = ROOT_PLAYBOOK.read_text(encoding="utf-8")
    engine, recorder = engine_for(tmp_home, workdir, body, driver=workdir.parent / "d")
    run(engine.on_job(finished(engine.spool, role=role, state=state, verdict=verdict)))
    assert engine.state.paused, event
    assert recorder.enqueued == []


def test_a_series_table_carries_the_name_and_the_kickoff(tmp_path: Path) -> None:
    """§26: `[series] kickoff`; the name moves into the table as `name` (H-019)."""
    book = parse_playbook(
        'version = 1\n[series]\nname = "s"\nkickoff = "Execute WORKPLAN.md run 1"\n',
        path=tmp_path / "PLAYBOOK.toml",
    )
    assert (book.series, book.kickoff) == ("s", "Execute WORKPLAN.md run 1")
    only_kickoff = parse_playbook(
        'version = 1\n[series]\nkickoff = "k"\n', path=tmp_path / "PLAYBOOK.toml"
    )
    assert (only_kickoff.series, only_kickoff.kickoff) == (None, "k")


def test_the_top_level_series_string_still_loads_with_no_kickoff(tmp_path: Path) -> None:
    """§10's example keeps `series = "…"`: it is the name, and there is no kickoff."""
    book = parse_playbook('version = 1\nseries = "audit-fixes"\n', path=tmp_path / "PLAYBOOK.toml")
    assert (book.series, book.kickoff) == ("audit-fixes", None)
    assert parse_playbook("version = 1\n", path=tmp_path / "PLAYBOOK.toml").kickoff is None


def test_a_series_string_and_a_series_table_together_is_not_toml(tmp_path: Path) -> None:
    """H-019: TOML forbids defining `series` twice, so the string-plus-table form the
    templates carry is refused by the parser, before any key is read."""
    with pytest.raises(PlaybookError) as caught:
        parse_playbook(
            'version = 1\nseries = "s"\n\n[series]\nkickoff = "k"\n',
            path=tmp_path / "PLAYBOOK.toml",
        )
    assert "is not valid TOML" in strip_paths(str(caught.value))


def test_the_repositorys_own_playbook_maps_the_mission_8_detectors() -> None:
    """§24: `monitor.orphan_processes` maps to `stop`. §32: `monitor.task_killed`
    maps to `notify` in this repository's playbook — the detector cannot tell a
    reap from a `TaskStop` or a reaped long foreground command, and a job that
    ends `failed` is what stops. Read through the real loader."""
    path = Path(__file__).parents[1] / "PLAYBOOK.toml"
    book = load_playbook(path)
    assert book is not None, "the repository's PLAYBOOK.toml is missing"
    for event, then in (("monitor.task_killed", "notify"), ("monitor.orphan_processes", "stop")):
        rules = [rule for rule in book.rules if rule.on == event]
        assert rules, f"PLAYBOOK.toml has no rule for {event}"
        assert [rule.then for rule in rules] == [then], (event, rules)
        assert rules[0].verdict is None, "a monitor event has no verdict to match"


def test_the_events_and_actions_are_exactly_section_10s() -> None:
    assert EVENTS == (
        "builder.done",
        "builder.failed",
        "builder.limited",
        "builder.orphaned",
        "aux.done",
        "aux.failed",
        "driver.done",  # §27: a consultation's driver job ended done
        "driver.failed",  # §27: … or failed
        "driver.killed",  # §28: … or any other way, each a stop the engine enforces
        "driver.orphaned",
        "driver.limited",
        "monitor.stall",
        "monitor.tripwire",
        "monitor.task_killed",  # §24: mission 8's detector; §32 maps it to `notify`
        "monitor.orphan_processes",  # §24: the other one, mapped to `stop`
        "job.held",
        "job.denied",
    )
    assert ACTIONS == ("send", "resume", "notify", "stop", "consult")
    assert JOB_PLACEHOLDERS == ("id", "head_at_start", "head_at_end", "session_id")


# --------------------------------------------------------------- loading (§10)


def test_a_missing_playbook_is_no_engine_and_not_an_error(tmp_home: Path, workdir: Path) -> None:
    engine, recorder = engine_for(tmp_home, workdir, body=None)
    assert load_playbook(playbook_path(engine.config)) is None
    job = finished(engine.spool, verdict="VERDICT: run 2 finished")
    run(engine.on_job_start(job))
    run(engine.on_job(job))
    assert recorder.sent == []
    assert engine.pipeline()["paused"] is False
    assert engine.spool.events() == []


# The refusal messages the cases below pin, verbatim from src/hands/playbook.py (§10,
# H-006). U2 (review blocker 2, should-fix 11): every one of these messages opens with
# the playbook's path — a pytest tmpdir — and most of them print the list of keys,
# events or actions the loader knows, so a bare word ("on", "role", "send", "auto_runs")
# can be matched by the path or by another case's message. Each case pins the sentence
# that only it makes; `test_every_bad_playbook_is_pinned_to_a_refusal_only_it_makes`
# holds the table to that.
NOT_A_RUN_EXPRESSION = (
    "run takes one named group of the rule's verdict regex, {name} or {name+k} (§10), got "
)
ONLY_IF_RUN_IN_IS_GONE = 'only_if_run_in is gone; §10 spells the check as run = "{n+1}"'
#: One sentence, two inputs: no `[limits] auto_runs` at all and an empty one are the
#: same refusal by design, so the two cases are told apart by their bodies, not by it.
NEEDS_AUTO_RUNS = (
    'run = "{n+1}" needs [limits] auto_runs to list the runs hands may start on its own'
)
NO_SUCH_GROUP = "names no group of this rule's verdict regex"
#: §20 for the `[series]` table: "" or blanks is neither absent nor a usable value.
SERIES_EMPTY = "[series] {key} is empty (§20): omit the key or give it a value"


BAD_PLAYBOOKS: list[tuple[str, str, str]] = [
    ("not toml", "version = = 1", "is not valid TOML"),
    ("unknown top key", 'version = 1\nseries = "s"\nrules = []',
     "unknown key(s) in the playbook: rules"),
    ("wrong version", "version = 2", "version must be 1 (§10), got 2"),
    ("unknown rule key", 'version = 1\n[[rule]]\non = "builder.done"\nthen = "stop"\nwhen = 1',
     "unknown key(s) in rule 0: when"),
    ("unknown event", 'version = 1\n[[rule]]\non = "builder.exploded"\nthen = "stop"',
     "on must be one of §10's events"),
    ("unknown action", 'version = 1\n[[rule]]\non = "builder.done"\nthen = "shrug"',
     "then must be one of §10's actions"),
    ("bad regex", 'version = 1\n[[rule]]\non = "builder.done"\nverdict = "(unclosed"\n'
     'then = "stop"', "verdict is not a valid regex"),
    ("send with no prompt", 'version = 1\n[[rule]]\non = "builder.done"\nthen = "send"\n'
     'role = "aux"', "a send needs a prompt"),
    ("send with no role", 'version = 1\n[[rule]]\non = "builder.done"\nthen = "send"\n'
     'prompt = "go"', "a send needs a role (builder or aux)"),
    ("send to an unknown role", 'version = 1\n[[rule]]\non = "builder.done"\nthen = "send"\n'
     'role = "cook"\nprompt = "go"', "role must be builder or aux, got 'cook'"),
    ("notify with no message", 'version = 1\n[[rule]]\non = "builder.done"\nthen = "notify"',
     "a notify needs a message"),
    ("unknown placeholder", 'version = 1\n[[rule]]\non = "builder.done"\nthen = "send"\n'
     'role = "aux"\nprompt = "run {n}"', "prompt: {n} " + NO_SUCH_GROUP),
    ("unknown job field", 'version = 1\n[[rule]]\non = "builder.done"\nthen = "send"\n'
     'role = "aux"\nprompt = "run {job.cost}"', "{job.cost} is not one of §10's job fields"),
    ("run on a non-send", 'version = 1\n[limits]\nauto_runs = [2]\n[[rule]]\n'
     'on = "builder.done"\nverdict = "run (?P<n>\\\\d+)"\nthen = "stop"\nrun = "{n}"',
     "run belongs on a send, not on a stop"),
    ("run with no auto_runs", 'version = 1\n[[rule]]\non = "aux.done"\n'
     'verdict = "run (?P<n>\\\\d+)"\nthen = "send"\nrole = "builder"\nprompt = "run {n+1}"\n'
     'run = "{n+1}"', NEEDS_AUTO_RUNS),
    ("run with an empty auto_runs", 'version = 1\n[limits]\nauto_runs = []\n[[rule]]\n'
     'on = "aux.done"\nverdict = "run (?P<n>\\\\d+)"\nthen = "send"\nrole = "builder"\n'
     'prompt = "run {n+1}"\nrun = "{n+1}"', NEEDS_AUTO_RUNS),
    ("run naming a group the verdict does not define", 'version = 1\n[limits]\n'
     'auto_runs = [2]\n[[rule]]\non = "aux.done"\nverdict = "run (?P<n>\\\\d+)"\n'
     'then = "send"\nrole = "builder"\nprompt = "run {n+1}"\nrun = "{k+1}"',
     'run = "{k+1}" reads {k+1}, which ' + NO_SUCH_GROUP + " (n)"),
    ("run on a rule with no verdict at all", 'version = 1\n[limits]\nauto_runs = [2]\n'
     '[[rule]]\non = "aux.done"\nthen = "send"\nrole = "builder"\nprompt = "go"\n'
     'run = "{n+1}"',
     'run = "{n+1}" reads {n+1}, which ' + NO_SUCH_GROUP + " (the rule has no verdict)"),
    ("run that is not an expression", 'version = 1\n[limits]\nauto_runs = [2]\n[[rule]]\n'
     'on = "aux.done"\nverdict = "run (?P<n>\\\\d+)"\nthen = "send"\nrole = "builder"\n'
     'prompt = "run {n+1}"\nrun = "3"', NOT_A_RUN_EXPRESSION + "'3'"),
    ("run naming a job field", 'version = 1\n[limits]\nauto_runs = [2]\n[[rule]]\n'
     'on = "aux.done"\nverdict = "run (?P<n>\\\\d+)"\nthen = "send"\nrole = "builder"\n'
     'prompt = "run {n+1}"\nrun = "{job.id}"', NOT_A_RUN_EXPRESSION + "'{job.id}'"),
    ("only_if_run_in at all", 'version = 1\n[limits]\nauto_runs = [2]\n[[rule]]\n'
     'on = "aux.done"\nverdict = "run (?P<n>\\\\d+)"\nthen = "send"\nrole = "builder"\n'
     'prompt = "run {n+1}"\nonly_if_run_in = "auto_runs"', ONLY_IF_RUN_IN_IS_GONE),
    ("only_if_run_in on its own", 'version = 1\n[[rule]]\non = "builder.done"\n'
     'then = "stop"\nonly_if_run_in = "auto_runs"', ONLY_IF_RUN_IN_IS_GONE),
    ("auto_runs is not integers", 'version = 1\n[limits]\nauto_runs = ["two"]',
     "[limits] auto_runs must be a list of run numbers, got ['two']"),
    # §26 (mission 10 U2, H-019): the `[series]` table holds `name` and `kickoff`.
    ("unknown [series] key", 'version = 1\n[series]\nkickoff = "go"\nkick_off = "go"',
     "unknown key(s) in [series]: kick_off"),
    ("empty kickoff", 'version = 1\n[series]\nkickoff = ""', SERIES_EMPTY.format(key="kickoff")),
    ("blank kickoff", 'version = 1\n[series]\nkickoff = "   "',
     SERIES_EMPTY.format(key="kickoff")),
    ("kickoff not a string", 'version = 1\n[series]\nkickoff = 3',
     "[series] kickoff must be a string, got 3"),
    ("empty series name", 'version = 1\n[series]\nname = ""', SERIES_EMPTY.format(key="name")),
    ("series neither a string nor a table", "version = 1\nseries = 3",
     "series must be a string (the series' name) or a [series] table, got 3"),
    # §27 (mission 11 U5): `consult` builds its own prompt for the driver role.
    ("consult with a prompt", 'version = 1\n[[rule]]\non = "builder.done"\n'
     'then = "consult"\nprompt = "x"',
     "a consult takes no prompt: hands writes the driver's prompt (§27, §31)"),
    ("consult to another role", 'version = 1\n[[rule]]\non = "builder.done"\n'
     'then = "consult"\nrole = "aux"',
     "a consult's role is driver or architect (§27, §31), got 'aux'"),
    ("consult with keep", 'version = 1\n[[rule]]\non = "builder.done"\n'
     'then = "consult"\ncontext = "keep"',
     "a consult starts a fresh driver session: context is clear, got 'keep'"),
    ("consult on a driver event", 'version = 1\n[[rule]]\non = "driver.done"\n'
     'then = "consult"', "a consult on driver.done would consult the driver about itself"),
    ("max_consults negative", 'version = 1\n[limits]\nmax_consults = -1',
     "[limits] max_consults must be a non-negative integer, got -1"),
]


@pytest.mark.parametrize(
    ("name", "body", "expected"), BAD_PLAYBOOKS, ids=[case[0] for case in BAD_PLAYBOOKS]
)
def test_an_invalid_playbook_is_an_error_not_a_half_read_file(
    name: str, body: str, expected: str, tmp_path: Path
) -> None:
    with pytest.raises(PlaybookError) as caught:
        parse_playbook(body, path=tmp_path / "PLAYBOOK.toml")
    assert expected in strip_paths(str(caught.value))


def _refusal(body: str, tmp_path: Path) -> str:
    with pytest.raises(PlaybookError) as caught:
        parse_playbook(body, path=tmp_path / "PLAYBOOK.toml")
    return str(caught.value)


def test_every_bad_playbook_is_pinned_to_a_refusal_only_it_makes(tmp_path: Path) -> None:
    """U2 (review blocker 2, should-fix 11): a bare substring is not a pin.

    Every refusal above opens with the playbook's path, which lives under the
    pytest tmpdir, and most of them print a list of the keys, events or actions
    the loader knows. So a one-word expectation can be satisfied by the path, by
    that list, or by a *different* case's message — and then the case passes
    without ever reading the sentence it is about. Each expectation has to single
    its own case out: it appears in that case's refusal and in no other, bar the
    pairs the loader answers with one and the same sentence by design.
    """
    refusals = {name: _refusal(body, tmp_path) for name, body, _expected in BAD_PLAYBOOKS}
    for name, _body, expected in BAD_PLAYBOOKS:
        assert expected in strip_paths(refusals[name]), (
            f"{name}: the expectation is not its own refusal"
        )
        for other, refusal in refusals.items():
            if other == name or refusal == refusals[name]:
                continue  # one sentence for two inputs is the loader's answer, not a loose pin
            assert expected not in strip_paths(refusal), (
                f"{name}'s expectation also matches {other}"
            )


def test_an_unparseable_playbook_stops_and_notifies_and_fires_nothing(
    tmp_home: Path, workdir: Path
) -> None:
    engine, recorder = engine_for(tmp_home, workdir, body="version = = 1")
    job = finished(engine.spool, verdict="VERDICT: run 2 finished")
    run(engine.on_job_start(job))
    assert engine.pipeline()["paused"] is True
    # U2: not the bare word "playbook" — the tmpdir path in the reason carries that.
    assert "the playbook cannot be read, so no rule can be trusted to fire" in (
        strip_paths(engine.pipeline()["stop_reason"])
    )
    assert [event.kind for event in engine.spool.events()] == ["stop"]
    assert recorder.notified
    run(engine.on_job(job))
    assert recorder.sent == []


#: §11 (§25): the refusal a playbook setting the retired key gets, in two parts.
QUIET_HOURS_RETIRED = "[limits] quiet_hours is retired"
NEVER_DELAYED = "notifications are never delayed"


def test_a_committed_playbook_that_sets_quiet_hours_is_refused_at_load_and_stops(
    tmp_home: Path, workdir: Path
) -> None:
    """§11, §25: `quiet_hours` is retired (decision 2026-09-12). A committed
    playbook whose `[limits]` sets it is refused at load with a message saying
    so and that notifications are never delayed; the engine's one load-refusal
    `stop()` carries that message as its reason."""
    body = 'version = 1\n\n[limits]\nauto_runs = [2]\nquiet_hours = "23:00-07:00"\n'
    commit_file(workdir, "PLAYBOOK.toml", body)
    with pytest.raises(PlaybookError) as refused:
        load_playbook(workdir / "PLAYBOOK.toml", cwd=workdir)
    assert QUIET_HOURS_RETIRED in strip_paths(str(refused.value))
    assert NEVER_DELAYED in strip_paths(str(refused.value))

    engine, recorder = engine_for(tmp_home, workdir, body=body)
    run(engine.on_job_start(finished(engine.spool, origin="cli")))
    state = engine.pipeline()
    assert state["paused"] is True
    assert QUIET_HOURS_RETIRED in strip_paths(state["stop_reason"])
    assert NEVER_DELAYED in strip_paths(state["stop_reason"])
    assert [event.kind for event in engine.spool.events()] == ["stop"]
    assert recorder.notified


# --------------------------------- the playbook must match the committed file (§10)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_a_committed_and_clean_playbook_loads(tmp_home: Path, workdir: Path) -> None:
    """§10, §25: the tracked file, byte for byte `git show HEAD:<path>`, loads."""
    committed = commit_file(workdir, "PLAYBOOK.toml", EXAMPLE)
    book = load_playbook(workdir / "PLAYBOOK.toml", cwd=workdir)
    assert book is not None and book.sha256 == committed

    engine, recorder = engine_for(tmp_home, workdir, body=None)
    run(engine.on_job_start(finished(engine.spool, origin="cli")))
    state = engine.pipeline()
    assert state["paused"] is False
    assert state["playbook"]["loaded"] is True and state["playbook"]["sha256"] == committed
    assert [event.kind for event in engine.spool.events()] == []
    assert recorder.notified == []


def test_a_dirty_playbook_is_refused_naming_both_sha256s_and_stops_the_pipeline(
    tmp_home: Path, workdir: Path
) -> None:
    """§10, §25: a file modified after its commit is refused at load; the one
    `stop()` takes the refusal as its reason and the `stop` event carries it."""
    committed = commit_file(workdir, "PLAYBOOK.toml", EXAMPLE)
    dirty = EXAMPLE + "\n# edited after the commit\n"
    (workdir / "PLAYBOOK.toml").write_text(dirty)
    working = _sha(dirty)
    assert working != committed

    with pytest.raises(PlaybookError) as refused:
        load_playbook(workdir / "PLAYBOOK.toml", cwd=workdir)
    assert "dirty" in strip_paths(str(refused.value))
    assert f"working sha256 {working}" in strip_paths(str(refused.value))
    assert f"committed sha256 {committed}" in strip_paths(str(refused.value))

    engine, recorder = engine_for(tmp_home, workdir, body=None)
    job = finished(engine.spool, verdict="VERDICT: run 2 finished", origin="cli")
    run(engine.on_job_start(job))
    state = engine.pipeline()
    assert state["paused"] is True
    assert state["playbook"]["loaded"] is False
    reason = state["stop_reason"]
    assert "dirty" in strip_paths(reason)
    assert f"working sha256 {working}" in strip_paths(reason)
    assert f"committed sha256 {committed}" in strip_paths(reason)
    events = engine.spool.events()
    assert [event.kind for event in events] == ["stop"]
    assert events[0].payload["reason"] == reason
    assert len(recorder.notified) == 1 and recorder.notified[0][1]["reason"] == reason
    run(engine.on_job(job))
    assert recorder.sent == [] and recorder.enqueued == []


def test_an_untracked_playbook_is_refused_and_stops_the_pipeline(
    tmp_home: Path, workdir: Path
) -> None:
    """§10, §25: a playbook that is not in HEAD has no committed copy to match."""
    git_repo(workdir)  # a repository with a commit, just not this file
    (workdir / "PLAYBOOK.toml").write_text(EXAMPLE)
    with pytest.raises(PlaybookError) as refused:
        load_playbook(workdir / "PLAYBOOK.toml", cwd=workdir)
    assert "untracked" in strip_paths(str(refused.value))
    assert f"working sha256 {_sha(EXAMPLE)}" in strip_paths(str(refused.value))
    assert "committed sha256 none" in strip_paths(str(refused.value))

    engine, recorder = engine_for(tmp_home, workdir, body=None)
    run(engine.on_job_start(finished(engine.spool, origin="cli")))
    state = engine.pipeline()
    assert state["paused"] is True
    assert "untracked" in strip_paths(state["stop_reason"])
    assert [event.kind for event in engine.spool.events()] == ["stop"]
    assert recorder.notified


def test_a_playbook_outside_any_git_repository_is_refused(workdir: Path) -> None:
    """§10 refuses what differs from the committed copy; with no repository there
    is no committed copy, so the file is refused as untracked."""
    (workdir / "PLAYBOOK.toml").write_text(EXAMPLE)
    with pytest.raises(PlaybookError) as refused:
        load_playbook(workdir / "PLAYBOOK.toml", cwd=workdir)
    assert "untracked" in strip_paths(str(refused.value))


def test_a_crlf_checkout_of_an_lf_commit_loads(workdir: Path) -> None:
    """REVIEW-9 should-fix 3, §26: committed with LF, checked out with CRLF under
    `core.autocrlf=true`; `git status` calls it clean, so it is not refused."""
    commit_file(workdir, "PLAYBOOK.toml", EXAMPLE)
    assert EXAMPLE.encode("utf-8").count(b"\r") == 0  # committed with LF only

    def git(*args: str) -> str:
        done = subprocess.run(
            ["git", "-C", str(workdir), *args], check=True, capture_output=True, text=True
        )
        return done.stdout

    git("config", "--local", "core.autocrlf", "true")
    (workdir / "PLAYBOOK.toml").unlink()
    git("checkout", "--", "PLAYBOOK.toml")
    assert b"\r\n" in (workdir / "PLAYBOOK.toml").read_bytes()
    assert git("status", "--porcelain") == ""

    book = load_playbook(workdir / "PLAYBOOK.toml", cwd=workdir)
    assert book is not None


def test_git_dir_in_the_daemons_environment_does_not_vouch_for_an_untracked_playbook(
    tmp_path: Path, workdir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """REVIEW-9 should-fix 3, §26: another repository whose HEAD has an identical file,
    named by the daemon's GIT_DIR, must not stand in for the playbook's own."""
    other = tmp_path / "other"
    commit_file(other, "PLAYBOOK.toml", EXAMPLE)
    git_repo(workdir)  # the playbook's own repository: a commit, not this file
    (workdir / "PLAYBOOK.toml").write_text(EXAMPLE)
    monkeypatch.setenv("GIT_DIR", str(other / ".git"))
    monkeypatch.setenv("GIT_INDEX_FILE", str(other / ".git" / "index"))

    with pytest.raises(PlaybookError) as refused:
        load_playbook(workdir / "PLAYBOOK.toml", cwd=workdir)
    assert "untracked" in strip_paths(str(refused.value))


# ----------------------------------------------------------- placeholders (§10)


PLACEHOLDERS: list[tuple[str, str, str]] = [
    ("group", "run {n}", "run 3"),
    ("arithmetic", "run {n+1}", "run 4"),
    ("arithmetic by k", "run {n+10}", "run 13"),
    ("subtraction", "run {n-1}", "run 2"),
    ("job id", "job {job.id}", "job j1"),
    ("job head", "since {job.head_at_start}", "since abc123"),
    ("job session", "session {job.session_id}", "session s1"),
    ("several", "{n} then {n+1} in {job.id}", "3 then 4 in j1"),
]


@pytest.mark.parametrize(
    ("name", "text", "expected"), PLACEHOLDERS, ids=[case[0] for case in PLACEHOLDERS]
)
def test_placeholders_render(name: str, text: str, expected: str) -> None:
    job = Job(
        id="j1",
        role="builder",
        context="clear",
        state="done",
        created="now",
        origin="cli",
        prompt="p",
        session_id="s1",
        head_at_start="abc123",
        head_at_end="def456",
    )
    assert render(text, groups={"n": "3"}, job=job) == expected


BAD_PLACEHOLDERS: list[tuple[str, str, str]] = [
    ("unknown name", "run {k}", "{k}"),
    ("unknown job field", "run {job.cost}", "job.cost"),
    ("not an integer", "run {word+1}", "integer"),
    ("null job field", "since {job.head_at_start}", "head_at_start"),
    ("nonsense", "run {n +}", "{n +}"),
]


@pytest.mark.parametrize(
    ("name", "text", "expected"), BAD_PLACEHOLDERS, ids=[case[0] for case in BAD_PLACEHOLDERS]
)
def test_a_placeholder_that_cannot_be_resolved_is_an_error(
    name: str, text: str, expected: str
) -> None:
    job = Job(
        id="j1", role="builder", context="clear", state="done", created="now",
        origin="cli", prompt="p",
    )
    with pytest.raises(PlaceholderError) as caught:
        render(text, groups={"n": "3", "word": "two"}, job=job)
    assert expected in strip_paths(str(caught.value))


# ------------------------------------------------------- the rule table (§10)


def test_a_matching_rule_sends_with_origin_playbook_and_the_sha(
    tmp_home: Path, workdir: Path
) -> None:
    engine, recorder = engine_for(tmp_home, workdir)
    job = finished(engine.spool, verdict="VERDICT: run 2 finished", head_at_start="abc123")
    run(engine.on_job_start(job))
    run(engine.on_job(job))
    assert recorder.sent == [
        {
            "role": "aux",
            "context": "clear",
            "prompt": REVIEW_PROMPT,
            "origin": "playbook",
            "playbook_sha256": engine.playbook.sha256,
        }
    ]
    kinds = [event.kind for event in engine.spool.events()]
    assert kinds == ["playbook.rule"]
    fired = engine.spool.events()[0].payload
    assert fired["rule"] == 0 and fired["on"] == "builder.done" and fired["then"] == "send"
    assert engine.pipeline()["last_rule"]["rule"] == 0
    assert engine.pipeline()["paused"] is False


def test_the_first_matching_rule_wins(tmp_home: Path, workdir: Path) -> None:
    """Two rules on one event, both matching: §10 reads top to bottom."""
    body = (
        "version = 1\n"
        '[[rule]]\non = "builder.done"\nverdict = "^VERDICT:"\nthen = "notify"\n'
        'message = "first"\n'
        '[[rule]]\non = "builder.done"\nverdict = "^VERDICT: run"\nthen = "notify"\n'
        'message = "second"\n'
    )
    engine, recorder = engine_for(tmp_home, workdir, body=body)
    job = finished(engine.spool, verdict="VERDICT: run 2 finished")
    run(engine.on_job_start(job))
    run(engine.on_job(job))
    assert [payload["message"] for _title, payload in recorder.notified] == ["first"]


STOPS: list[tuple[str, str, str | None, str]] = [
    (
        "unmatched event",
        'version = 1\n[[rule]]\non = "aux.done"\nthen = "stop"\n',
        "VERDICT: run 2 finished",
        # U2: "no rule" was the expectation of two of these three, so neither case
        # could tell the event it did not pre-plan from the verdict nothing matched.
        "builder.done: the playbook has no rule for it",
    ),
    (
        "no rule matches the verdict",
        EXAMPLE,
        "VERDICT: run two finished",
        "no rule matches the verdict 'VERDICT: run two finished'",
    ),
    ("no VERDICT line", EXAMPLE, None, "has no VERDICT: line"),
]


@pytest.mark.parametrize(
    ("name", "body", "verdict", "expected"), STOPS, ids=[case[0] for case in STOPS]
)
def test_stop_is_the_default(
    name: str, body: str, verdict: str | None, expected: str, tmp_home: Path, workdir: Path
) -> None:
    engine, recorder = engine_for(tmp_home, workdir, body=body)
    job = finished(engine.spool, verdict=verdict)
    run(engine.on_job_start(job))
    run(engine.on_job(job))
    assert recorder.sent == []
    state = engine.pipeline()
    assert state["paused"] is True
    assert expected in strip_paths(state["stop_reason"])
    assert [event.kind for event in engine.spool.events()] == ["stop"]
    assert recorder.notified  # §11: a stop notifies


def test_a_run_outside_auto_runs_stops(tmp_home: Path, workdir: Path) -> None:
    engine, recorder = engine_for(tmp_home, workdir)
    job = finished(engine.spool, role="aux", verdict="VERDICT: review run 3 blockers=0")
    run(engine.on_job_start(job))
    run(engine.on_job(job))
    assert recorder.sent == []
    # U2: the run number is a bare digit that the rule index, the allowed list and a
    # job id in the reason could all supply; pin the sentence that names run 4.
    assert "would start run 4, which [limits] auto_runs does not list ([2, 3])" in (
        strip_paths(engine.pipeline()["stop_reason"])
    )


def test_the_run_key_is_read_not_the_prompt(tmp_home: Path, workdir: Path) -> None:
    """H-006: `run` names the checked value; a prompt with two of them is fine."""
    body = (
        "version = 1\n[limits]\nauto_runs = [3]\n[[rule]]\n"
        'on = "aux.done"\nverdict = \'^VERDICT: review run (?P<n>\\d+)\'\n'
        'then = "send"\nrole = "builder"\nprompt = "run {n+1} follows run {n}"\n'
        'run = "{n+1}"\n'
    )
    engine, recorder = engine_for(tmp_home, workdir, body=body)
    job = finished(engine.spool, role="aux", verdict="VERDICT: review run 2")
    run(engine.on_job_start(job))
    run(engine.on_job(job))
    assert [sent["prompt"] for sent in recorder.sent] == ["run 3 follows run 2"]
    assert engine.pipeline()["auto_runs"] == {"allowed": [3], "used": [3]}
    assert engine.pipeline()["paused"] is False


def test_an_event_outside_section_10s_list_fires_nothing(tmp_home: Path, workdir: Path) -> None:
    """`killed` is a human's own cancel (§4); it is not one of §10's events."""
    engine, recorder = engine_for(tmp_home, workdir)
    job = engine.spool.create_job(role="builder", context="clear", prompt="p", origin="cli")
    engine.spool.transition(job, "running")
    killed = engine.spool.transition(job, "killed")
    run(engine.on_job_start(killed))
    run(engine.on_job(killed))
    assert recorder.sent == [] and engine.pipeline()["paused"] is False


def test_a_monitor_tripwire_stops_the_pipeline(tmp_home: Path, workdir: Path) -> None:
    engine, _recorder = engine_for(tmp_home, workdir)
    job = engine.spool.create_job(role="builder", context="clear", prompt="p", origin="cli")
    run(engine.on_job_start(job))
    run(engine.on_event("monitor.tripwire", payload={"job": job.id, "block": "TRIPWIRE main"}))
    assert engine.pipeline()["paused"] is True
    assert "monitor.tripwire" in strip_paths(engine.pipeline()["stop_reason"])


def test_a_task_killed_rule_loads_and_stops_the_pipeline(tmp_home: Path, workdir: Path) -> None:
    """§24: the loader accepts `monitor.task_killed` and the event reaches the rule.
    A playbook may still map it to `stop`; §32's shipped playbooks map it to
    `notify` (pinned below, over `SHIPPED_PLAYBOOKS`)."""
    body = EXAMPLE + '\n[[rule]]\non = "monitor.task_killed"\nthen = "stop"\n'
    book = parse_playbook(body, path=workdir / "PLAYBOOK.toml")
    assert (book.rules[-1].on, book.rules[-1].then) == ("monitor.task_killed", "stop")
    engine, recorder = engine_for(tmp_home, workdir, body=body)
    job = engine.spool.create_job(role="builder", context="clear", prompt="p", origin="cli")
    run(engine.on_job_start(job))
    payload = {"job": job.id, "task_id": "bg1", "command": "sleep 600", "block": "TASK_KILLED"}
    run(engine.on_event("monitor.task_killed", payload=payload))
    assert engine.pipeline()["paused"] is True
    assert "monitor.task_killed" in strip_paths(engine.pipeline()["stop_reason"])
    assert recorder.sent == []


def test_an_orphan_processes_rule_loads_and_stops_the_pipeline(
    tmp_home: Path, workdir: Path
) -> None:
    """§24: `monitor.orphan_processes` is a name a rule may use, and it stops."""
    body = EXAMPLE + '\n[[rule]]\non = "monitor.orphan_processes"\nthen = "stop"\n'
    book = parse_playbook(body, path=workdir / "PLAYBOOK.toml")
    assert (book.rules[-1].on, book.rules[-1].then) == ("monitor.orphan_processes", "stop")
    engine, recorder = engine_for(tmp_home, workdir, body=body)
    job = engine.spool.create_job(role="builder", context="clear", prompt="p", origin="cli")
    run(engine.on_job_start(job))
    payload = {"job": job.id, "processes": [{"pid": 7, "cmdline": "sleep 300"}], "block": "x"}
    run(engine.on_event("monitor.orphan_processes", payload=payload))
    assert engine.pipeline()["paused"] is True
    assert "monitor.orphan_processes" in strip_paths(engine.pipeline()["stop_reason"])
    assert recorder.sent == []


def test_a_held_job_stops_the_pipeline(tmp_home: Path, workdir: Path) -> None:
    """§10 lists `job.held`; the example has no rule for it, so it stops (§8)."""
    engine, _recorder = engine_for(tmp_home, workdir)
    job = engine.spool.create_job(
        role="builder", context="clear", prompt="p", origin="playbook", state="held"
    )
    run(engine.on_job_start(job))
    run(engine.on_event("job.held", job=job))
    assert engine.pipeline()["paused"] is True
    assert "job.held" in strip_paths(engine.pipeline()["stop_reason"])


def test_a_resume_rule_on_an_orphan_resends_the_resume_line(
    tmp_home: Path, workdir: Path
) -> None:
    """H-008: §10's `resume` sends the role's resume line when one is configured."""
    engine, recorder = engine_for(
        tmp_home, workdir, builder={"resume_line": "Resume WORKPLAN.md"}
    )
    job = finished(engine.spool, state="orphaned")
    run(engine.on_job_start(job))
    run(engine.on_job(job))
    assert recorder.enqueued == [
        {
            "role": "builder",
            "context": "clear",
            "prompt": "Resume WORKPLAN.md",
            "origin": "playbook",
            "resumed_from": job.id,
            "playbook_sha256": engine.playbook.sha256,
        }
    ]
    assert engine.spool.read_role("builder").consecutive_resumes == 1
    (event,) = [e for e in engine.spool.events() if e.kind == "resume"]
    # H-004: only §6's limit resume is `limit`; a rule-issued one stays playbook.
    assert event.payload["origin"] == "playbook"


def test_a_resume_rule_without_a_resume_line_resends_the_jobs_own_prompt(
    tmp_home: Path, workdir: Path
) -> None:
    """H-008: §10 reads as §6 does — no line configured, the same prompt again."""
    engine, recorder = engine_for(tmp_home, workdir)
    job = finished(engine.spool, state="orphaned")
    run(engine.on_job_start(job))
    run(engine.on_job(job))
    assert [(e["prompt"], e["context"]) for e in recorder.enqueued] == [(job.prompt, "clear")]
    assert engine.spool.read_role("builder").consecutive_resumes == 1


def test_exhausted_resumes_stop(tmp_home: Path, workdir: Path) -> None:
    engine, recorder = engine_for(tmp_home, workdir)
    engine.spool.update_role("builder", consecutive_resumes=3)  # = the example's max_resumes
    job = finished(engine.spool, state="orphaned")
    run(engine.on_job_start(job))
    run(engine.on_job(job))
    assert recorder.enqueued == []
    assert "max_resumes" in strip_paths(engine.pipeline()["stop_reason"])


LIMITED_BOOK = '''version = 1
[limits]
auto_runs = [2, 3]
max_resumes = 3

[[rule]]
on = "builder.limited"
then = "resume"
'''


def test_a_limited_job_leaves_the_resume_to_section_6(tmp_home: Path, workdir: Path) -> None:
    """§6 schedules the limit resume for the reset; the rule must not double it.

    §10's example no longer carries this rule (H-005), so the playbook is
    written here: the behaviour is the finding's, not the example's.
    """
    engine, recorder = engine_for(tmp_home, workdir, body=LIMITED_BOOK)
    job = finished(engine.spool, state="limited", limit={"category": "rate_limit"})
    run(engine.on_job_start(job))
    run(engine.on_job(job))
    assert recorder.enqueued == [] and recorder.sent == []
    fired = engine.spool.events()[-1]
    assert fired.kind == "playbook.rule" and fired.payload["then"] == "resume"
    assert engine.pipeline()["paused"] is False


def test_the_playbook_overrides_max_resumes(tmp_home: Path, workdir: Path) -> None:
    """§10's `[limits] max_resumes` is the one §6 counts against."""
    engine, _recorder = engine_for(tmp_home, workdir, body="version = 1\n[limits]\nmax_resumes = 7")
    job = finished(engine.spool)
    run(engine.on_job_start(job))
    assert engine.pipeline()["resumes"]["max_resumes"] == 7


def test_a_refused_send_stops_rather_than_losing_the_step(
    tmp_home: Path, workdir: Path
) -> None:
    engine, recorder = engine_for(tmp_home, workdir)
    recorder.refuse = "role aux already has 4 job(s) queued"
    job = finished(engine.spool, verdict="VERDICT: run 2 finished", head_at_start="abc")
    run(engine.on_job_start(job))
    run(engine.on_job(job))
    assert engine.pipeline()["paused"] is True
    assert "4 job(s) queued" in strip_paths(engine.pipeline()["stop_reason"])


# ------------------------------------------------------- pause / resume (§10)


def test_while_paused_no_rule_fires_and_resume_unpauses(tmp_home: Path, workdir: Path) -> None:
    engine, recorder = engine_for(tmp_home, workdir)
    job = finished(engine.spool, verdict="VERDICT: run 2 finished", head_at_start="abc")
    run(engine.on_job_start(job))
    run(engine.pause())
    assert engine.pipeline()["paused"] is True
    run(engine.on_job(job))
    assert recorder.sent == []

    run(engine.resume())
    assert engine.pipeline()["paused"] is False
    assert engine.pipeline()["stop_reason"] is None
    run(engine.on_job(job))
    assert len(recorder.sent) == 1


def test_a_hand_pause_files_a_stop_event_and_notifies(tmp_home: Path, workdir: Path) -> None:
    """H-007, §11: a pause is a stop like any other, so it files the `stop` event
    (`paused by human`) and notifies. Without the event, a pause never reaches
    the human's phone, and §11's notification check has no one-command event
    behind it."""
    engine, recorder = engine_for(tmp_home, workdir)
    state = run(engine.pause())
    (event,) = [e for e in engine.spool.events() if e.kind == "stop"]
    assert event.payload["reason"] == PAUSE_REASON
    assert event.payload["by"] == "hands pause"
    assert state["paused"] is True and state["stop_reason"] == PAUSE_REASON
    assert [title for title, _ in recorder.notified] == ["hands: the pipeline stopped"]


def test_pausing_an_already_paused_pipeline_files_one_event(
    tmp_home: Path, workdir: Path
) -> None:
    """One stop, one notification: the second pause is a
    `pipeline.stop_suppressed` record in the inbox and nothing else (§10)."""
    engine, recorder = engine_for(tmp_home, workdir)
    run(engine.pause())
    run(engine.pause())
    assert [e.kind for e in engine.spool.events()] == ["stop", "pipeline.stop_suppressed"]
    assert len(recorder.notified) == 1


def test_a_pause_works_with_no_playbook_at_all(tmp_home: Path, workdir: Path) -> None:
    """§14: the wake check is run at install time, before any playbook exists."""
    engine, _recorder = engine_for(tmp_home, workdir, body=None)
    state = run(engine.pause())
    assert state["paused"] is True
    assert state["playbook"]["loaded"] is False
    (event,) = [e for e in engine.spool.events() if e.kind == "stop"]
    assert event.payload["reason"] == PAUSE_REASON


def test_a_resume_files_a_pipeline_resumed_event(tmp_home: Path, workdir: Path) -> None:
    """The other half of §10's stop → resume cycle is in the inbox too."""
    engine, recorder = engine_for(tmp_home, workdir)
    run(engine.pause())
    run(engine.resume())
    (event,) = [e for e in engine.spool.events() if e.kind == "pipeline.resumed"]
    assert event.payload["by"] == "resume"  # §10: `resume`, or `start` for a job
    assert event.payload["was"] == PAUSE_REASON
    assert len(recorder.notified) == 1, "a resume is not on §11's notification list"


def test_resuming_a_pipeline_that_is_not_paused_files_nothing(
    tmp_home: Path, workdir: Path
) -> None:
    engine, _recorder = engine_for(tmp_home, workdir)
    assert run(engine.resume())["paused"] is False
    run(engine.resume())
    assert [e.kind for e in engine.spool.events()] == []


def test_a_pause_survives_a_restart(tmp_home: Path, workdir: Path) -> None:
    """A stop that a restart forgot would chain runs nobody is watching."""
    engine, _recorder = engine_for(tmp_home, workdir)
    run(engine.stop("because", {}))
    again, recorder = engine_for(tmp_home, workdir)
    assert again.pipeline()["paused"] is True
    # A job the pipeline started itself, so the restart is the only thing under
    # test: a `cli` job starting is §10's un-pause and is tested below.
    job = finished(again.spool, verdict="VERDICT: run 2 finished", origin="playbook")
    run(again.on_job_start(job))
    assert again.pipeline()["paused"] is True
    run(again.on_job(job))
    assert recorder.sent == []


def test_a_cli_job_un_pauses_the_pipeline_when_it_starts(
    tmp_home: Path, workdir: Path
) -> None:
    """§10's stop → resume cycle: "so does a `cli`-origin send, but only when that
    job **starts**". The start is the seam because that is the moment the human's
    answer to the stop actually runs."""
    engine, _recorder = engine_for(tmp_home, workdir)
    run(engine.stop("because", {}))
    job = finished(engine.spool, verdict="VERDICT: run 2 finished", origin="cli")
    run(engine.on_job_start(job))
    assert engine.pipeline()["paused"] is False
    (resumed,) = [e for e in engine.spool.events() if e.kind == "pipeline.resumed"]
    assert resumed.payload["by"] == "start"  # §10: how it was un-paused
    assert resumed.payload["was"] == "because"


@pytest.mark.parametrize("origin", ["phone", "kit"])
def test_a_phone_or_kit_job_un_pauses_the_pipeline_when_it_starts(
    tmp_home: Path, workdir: Path, origin: str
) -> None:
    """H-018 gap 2 and §27: a `go` from the phone, or the apply a kit from the phone
    filed, is the human answering the stop, so a `phone`- or `kit`-origin job
    clears it under the same "only when it starts" rule."""
    engine, _recorder = engine_for(tmp_home, workdir)
    run(engine.stop("because", {}))
    queued = engine.spool.create_job(role="builder", context="clear", prompt="p", origin=origin)
    assert engine.pipeline()["paused"] is True, f"a queued {origin} job has not started"
    run(engine.on_job_start(queued))
    assert engine.pipeline()["paused"] is False
    (resumed,) = [e for e in engine.spool.events() if e.kind == "pipeline.resumed"]
    assert resumed.payload == {"by": "start", "was": "because"}


@pytest.mark.parametrize("origin", ["playbook", "limit", "driver"])
def test_a_job_the_pipeline_started_itself_never_clears_a_stop(
    tmp_home: Path, workdir: Path, origin: str
) -> None:
    """§10: "a stop is never cleared by a job the playbook or the limit manager
    started". `driver` is in §6's origin vocabulary and nothing files one today;
    it is not the `cli` origin §10 names, so it does not clear a stop either."""
    engine, _recorder = engine_for(tmp_home, workdir)
    run(engine.stop("because", {}))
    job = finished(engine.spool, verdict="VERDICT: run 2 finished", origin=origin)
    run(engine.on_job_start(job))
    assert engine.pipeline()["paused"] is True
    assert engine.pipeline()["stop_reason"] == "because"
    assert [e.kind for e in engine.spool.events()] == ["stop"]


def test_a_stop_over_a_stop_keeps_the_first_reason_and_files_it_as_suppressed(
    tmp_home: Path, workdir: Path
) -> None:
    """§10: "Every stop, from any component, goes through one `stop()` that keeps
    the first reason and files one notification; a later stop over an existing one
    is recorded in the inbox only"."""
    engine, recorder = engine_for(tmp_home, workdir)
    run(engine.stop("the first reason", {"event": "aux.done"}))
    first = engine.pipeline()
    run(engine.stop("the second reason", {"event": "builder.failed"}))

    now = engine.pipeline()
    assert now["stop_reason"] == "the first reason"
    assert now["stopped_at"] == first["stopped_at"]
    kinds = [e.kind for e in engine.spool.events()]
    assert kinds == ["stop", "pipeline.stop_suppressed"]
    suppressed = engine.spool.events()[1]
    assert suppressed.payload["reason"] == "the second reason"  # the would-be reason
    assert suppressed.payload["kept"] == "the first reason"
    assert suppressed.payload["event"] == "builder.failed"  # its payload, not the first's
    assert len(recorder.notified) == 1  # one notification per stop that takes


def test_last_rule_is_cleared_when_a_playbook_with_another_sha_loads(
    tmp_home: Path, workdir: Path
) -> None:
    """§10: "`last_rule` is cleared when a different playbook file is loaded" — the
    rule numbers a new file uses are not the ones `last_rule` was fired under."""
    engine, _recorder = engine_for(tmp_home, workdir)
    job = finished(engine.spool, verdict="VERDICT: run 2 finished", head_at_start="abc")
    run(engine.on_job_start(job))
    run(engine.on_job(job))
    fired = engine.pipeline()["last_rule"]
    assert fired is not None and fired["rule"] == 0

    run(engine.on_job_start(finished(engine.spool, origin="playbook")))
    assert engine.pipeline()["last_rule"] == fired, "the same file keeps it"

    commit_file(
        workdir,
        "PLAYBOOK.toml",
        'version = 1\n[[rule]]\non = "aux.done"\nthen = "notify"\nmessage = "hi"\n',
    )
    run(engine.on_job_start(finished(engine.spool, origin="playbook")))
    assert engine.pipeline()["last_rule"] is None
    assert engine.pipeline()["playbook"]["rules"] == 1


def test_last_rule_survives_a_restart_under_the_same_playbook(
    tmp_home: Path, workdir: Path
) -> None:
    """The reset is "a different file", not "a restart": §4's `hands pipeline`
    keeps reporting the last rule while the playbook behind it is unchanged."""
    engine, _recorder = engine_for(tmp_home, workdir)
    job = finished(engine.spool, verdict="VERDICT: run 2 finished", head_at_start="abc")
    run(engine.on_job_start(job))
    run(engine.on_job(job))
    fired = engine.pipeline()["last_rule"]

    again, _r = engine_for(tmp_home, workdir)
    run(again.on_job_start(finished(again.spool, origin="playbook")))
    assert again.pipeline()["last_rule"] == fired


def test_hands_pipeline_marks_a_last_rule_from_another_playbook_stale(
    tmp_home: Path, workdir: Path
) -> None:
    """§21 (review 4 should-fix 7): the display says so instead of printing it plain.

    `last_rule` is cleared when a different file *loads* (§10), and that load
    happens when a job starts. `hands pipeline` is a read-only command on a
    daemon that may not have started one yet: its own lazy load reads the new
    file, so the rule numbers it prints would be the old file's next to the new
    file's sha. The record is kept — the next job start is what clears it — and
    marked `stale: true`, which is the difference between a display and a state
    change.
    """
    engine, _recorder = engine_for(tmp_home, workdir)
    job = finished(engine.spool, verdict="VERDICT: run 2 finished", head_at_start="abc")
    run(engine.on_job_start(job))
    run(engine.on_job(job))
    fired = engine.pipeline()["last_rule"]
    assert fired is not None, "the rule fired"
    assert fired.get("stale") is None, "the loaded file is the one it fired under"

    write_playbook(
        workdir, 'version = 1\n[[rule]]\non = "aux.done"\nthen = "notify"\nmessage = "hi"\n'
    )
    again, _r = engine_for(tmp_home, workdir, body=None)  # a restart; no job has started
    state = again.pipeline()
    shown = state["last_rule"]
    assert shown is not None, "the record is marked, not dropped"
    assert shown["rule"] == fired["rule"] and shown["fired_at"] == fired["fired_at"]
    assert shown["stale"] is True
    assert shown["playbook_sha256"] != state["playbook"]["sha256"]

    # …and the next job start is still what clears it (§10).
    run(again.on_job_start(finished(again.spool, origin="playbook")))
    assert again.pipeline()["last_rule"] is None


def test_the_pipeline_block_says_stale_only_when_the_rule_is(
    tmp_home: Path, workdir: Path
) -> None:
    """§21: the prose rendering of `hands pipeline` carries the mark too.

    The JSON is for the driver; the line the human reads is where a rule number
    from a file that is no longer the playbook does its damage.
    """
    engine, _recorder = engine_for(tmp_home, workdir)
    job = finished(engine.spool, verdict="VERDICT: run 2 finished", head_at_start="abc")
    run(engine.on_job_start(job))
    run(engine.on_job(job))
    fresh = _pipeline_block(engine.pipeline())
    assert "rule 0 on builder.done" in strip_paths(fresh)
    assert "stale" not in strip_paths(fresh)

    write_playbook(
        workdir, 'version = 1\n[[rule]]\non = "aux.done"\nthen = "notify"\nmessage = "hi"\n'
    )
    again, _r = engine_for(tmp_home, workdir, body=None)
    marked = _pipeline_block(again.pipeline())
    assert "rule 0 on builder.done" in strip_paths(marked)
    assert "stale" in strip_paths(marked)


def test_a_state_file_from_an_older_build_keeps_its_last_rule(tmp_home: Path) -> None:
    """The persisted state gained a key: a file written before it must not crash,
    and must not lose `last_rule` — the sha it was fired under is in the record."""
    state = PipelineState.from_dict(
        {"paused": True, "last_rule": {"rule": 2, "playbook_sha256": "abc"}}
    )
    assert state.last_rule_sha256 == "abc"
    assert state.paused is True
    assert PipelineState.from_dict({}).last_rule_sha256 is None
    round_tripped = PipelineState.from_dict(
        PipelineState(last_rule={"rule": 1}, last_rule_sha256="def").to_dict()
    )
    assert round_tripped.last_rule_sha256 == "def"
    assert round_tripped.last_rule == {"rule": 1}


# ----------------------------------------------- the daemon path (§4, §8, §11)


@pytest.fixture
def project(tmp_home: Path, workdir: Path) -> str:
    return write_project(tmp_home, config_body(tmp_home, workdir))


def write_playbook(workdir: Path, body: str) -> None:
    commit_file(workdir, "PLAYBOOK.toml", body)  # §10: only the committed file loads


async def wait_for_jobs(count: int, role: str | None = None) -> list[dict[str, Any]]:
    async def check() -> Any:
        rows = (await ok("jobs", "-n", "50"))["jobs"]
        if role is not None:
            rows = [row for row in rows if row["role"] == role]
        return rows if len(rows) >= count else None

    return await poll(check, f"{count} job(s)")


async def wait_for_stop() -> dict[str, Any]:
    async def check() -> Any:
        state = await ok("pipeline")
        return state if state["paused"] else None

    return await poll(check, "the pipeline to stop")


def test_pipeline_reports_section_4s_fields(project: str, workdir: Path) -> None:
    write_playbook(workdir, EXAMPLE)

    async def body(daemon: Daemon) -> None:
        state = await ok("pipeline")
        assert state["playbook"]["path"] == str(workdir / "PLAYBOOK.toml")
        assert state["playbook"]["series"] == "audit-fixes"
        assert len(state["playbook"]["sha256"]) == 64
        assert state["paused"] is False
        assert state["stop_reason"] is None
        assert state["auto_runs"] == {"allowed": [2, 3], "used": []}
        assert state["resumes"] == {"used": {"builder": 0, "aux": 0}, "max_resumes": 3}
        assert state["last_rule"] is None

        code, out, _err = await cli("pipeline")
        assert code == 0
        assert "audit-fixes" in strip_paths(out) and "paused" in strip_paths(out)

    drive(body)


def test_pause_and_resume_are_the_cli_commands_of_section_4(project: str, workdir: Path) -> None:
    write_playbook(workdir, EXAMPLE)

    async def body(daemon: Daemon) -> None:
        assert (await ok("pause"))["paused"] is True
        assert (await ok("pipeline"))["paused"] is True
        assert (await ok("resume"))["paused"] is False
        assert (await ok("pipeline"))["paused"] is False

    drive(body)


class Posts:
    """The ntfy transport, recorded: no test may make a network call (§11)."""

    def __init__(self) -> None:
        self.sent: list[str] = []

    async def __call__(self, url: str, *, title: str, message: str) -> int:
        self.sent.append(title)
        return 200  # ntfy's answer: a double speaks the transport's `-> int` too


def drive_notified(
    tmp_home: Path, workdir: Path, body: Callable[[Daemon, Posts], Awaitable[None]]
) -> None:
    """`drive`, with the notifications of §11 countable instead of published."""
    write_project(
        tmp_home,
        config_body(tmp_home, workdir).replace(
            "[server]", '[server]\nntfy_topic = "hands-test"\nntfy_url = "https://ntfy.example"'
        ),
    )
    posts = Posts()

    async def scenario() -> None:
        daemon = Daemon(load_config(PROJECT))
        daemon.notifier.post = posts  # before start(): no test may reach a network
        await daemon.start()
        try:
            await asyncio.wait_for(body(daemon, posts), 60)
        finally:
            await daemon.stop()

    asyncio.run(scenario())


def stop_posts(posts: Posts) -> list[str]:
    """The stop notifications of §11, without the daemon's own start message."""
    return [title for title in posts.sent if title == "hands: the pipeline stopped"]


async def assert_pause_is_a_no_op(daemon: Daemon, posts: Posts, reason: str) -> None:
    """Review should-fix 4 / §10: the pipeline is already stopped for `reason`, so
    `hands pause` keeps it, notifies nobody — and says the reason, because a silent
    success reads as "I stopped it". §10 (v3.3) adds the one thing it does write:
    the suppressed stop is "recorded in the inbox only"."""
    was = await ok("pipeline")
    assert was["stop_reason"] == reason, was["stop_reason"]
    before = [event["id"] for event in (await ok("inbox"))["events"]]
    await daemon.notifier.drain()
    notified = list(posts.sent)

    code, out, err = await cli("pause")

    assert code == 0, err  # a no-op, not a failure
    assert reason in strip_paths(out), out  # the human learns why it was already stopped
    assert "already stopped" in strip_paths(out), out  # …and that this pause did nothing
    now = await ok("pipeline")
    assert now["stop_reason"] == reason
    assert now["stopped_at"] == was["stopped_at"]
    after = (await ok("inbox"))["events"]
    assert [event["id"] for event in after[: len(before)]] == before
    added = after[len(before) :]
    assert [event["kind"] for event in added] == ["pipeline.stop_suppressed"]
    assert added[0]["payload"]["reason"] == PAUSE_REASON  # the stop that did not take
    assert added[0]["payload"]["kept"] == reason
    await daemon.notifier.drain()
    assert posts.sent == notified


def test_a_pause_after_a_rule_stop_keeps_the_first_reason(
    tmp_home: Path, workdir: Path
) -> None:
    """§19: the reason the pipeline stopped is what `hands pipeline` must keep
    showing; `paused by human` over it loses the only copy outside the inbox."""
    write_playbook(
        workdir,
        "version = 1\n"
        '[[rule]]\non = "builder.done"\nverdict = "^VERDICT: stop me"\nthen = "stop"\n'
        'message = "asked for"\n',
    )

    async def body(daemon: Daemon, posts: Posts) -> None:
        job = await ok(
            "send", "--role", "builder", "--context", "clear", "FAKE:result VERDICT: stop me"
        )
        await ok("wait", job["id"])
        await wait_for_stop()
        await assert_pause_is_a_no_op(daemon, posts, "asked for")

    drive_notified(tmp_home, workdir, body)


def test_a_pause_after_a_held_job_stop_keeps_the_first_reason(
    tmp_home: Path, workdir: Path
) -> None:
    """The same for §8's `job.held` stop: a pause must not hide the held job."""
    write_playbook(workdir, 'version = 1\n[[rule]]\non = "aux.done"\nthen = "stop"\n')

    async def body(daemon: Daemon, posts: Posts) -> None:
        await ok("send", "--role", "builder", "--context", "clear", "--gate", "by hand", "hi")
        state = await wait_for_stop()
        assert "job.held" in strip_paths(state["stop_reason"])
        await assert_pause_is_a_no_op(daemon, posts, state["stop_reason"])

    drive_notified(tmp_home, workdir, body)


def test_a_limit_stop_over_a_rule_stop_keeps_the_first_reason(
    tmp_home: Path, workdir: Path
) -> None:
    """§10: "Every stop, from any component" — §6's `max_resumes` stop included.
    It lands over a rule stop through the daemon's own wiring, so the first reason
    survives, one notification was sent in all, and the reason that did not take is
    in the inbox as `pipeline.stop_suppressed`."""
    write_playbook(workdir, EXAMPLE)

    async def body(daemon: Daemon, posts: Posts) -> None:
        await daemon.playbook.stop("a rule said so")
        await daemon.notifier.drain()
        first = await ok("pipeline")
        assert first["stop_reason"] == "a rule said so"
        assert stop_posts(posts) == ["hands: the pipeline stopped"]

        daemon.limits.max_resumes = 0  # §6: the next limit has no resume left
        job = daemon.spool.create_job(
            role="builder", context="clear", prompt="work", origin="cli"
        )
        daemon.spool.transition(job, "running")
        limited = daemon.spool.transition(
            job, "limited", limit={"category": "rate_limit", "message": "", "reset_at": None}
        )
        await daemon.limits.on_job_finished(limited)
        await daemon.limits.drain()
        await daemon.notifier.drain()

        now = await ok("pipeline")
        assert now["stop_reason"] == "a rule said so"  # the first reason is kept
        assert now["stopped_at"] == first["stopped_at"]
        kinds = [event["kind"] for event in (await ok("inbox"))["events"]]
        assert kinds.count("stop") == 1  # one `stop` event per stop that takes
        assert kinds.count("pipeline.stop_suppressed") == 1
        (suppressed,) = [
            event
            for event in (await ok("inbox"))["events"]
            if event["kind"] == "pipeline.stop_suppressed"
        ]
        assert "max_resumes" in strip_paths(suppressed["payload"]["reason"])
        assert suppressed["payload"]["kept"] == "a rule said so"
        assert suppressed["payload"]["role"] == "builder"
        # one notification per stop that takes: the rule's, and no second one
        assert stop_posts(posts) == ["hands: the pipeline stopped"]

    drive_notified(tmp_home, workdir, body)


def test_a_limit_stop_with_no_stop_over_it_still_files_its_event_and_notifies(
    tmp_home: Path, workdir: Path
) -> None:
    """The other half of the same move: §6's stop now writes its `stop` event
    through the engine, so it must still write exactly one, and notify."""
    write_playbook(workdir, EXAMPLE)

    async def body(daemon: Daemon, posts: Posts) -> None:
        daemon.limits.max_resumes = 0
        job = daemon.spool.create_job(
            role="builder", context="clear", prompt="work", origin="cli"
        )
        daemon.spool.transition(job, "running")
        limited = daemon.spool.transition(
            job, "limited", limit={"category": "rate_limit", "message": "", "reset_at": None}
        )
        await daemon.limits.on_job_finished(limited)
        await daemon.limits.drain()
        await daemon.notifier.drain()

        state = await ok("pipeline")
        assert state["paused"] is True
        assert "max_resumes" in strip_paths(state["stop_reason"])
        kinds = [event["kind"] for event in (await ok("inbox"))["events"]]
        assert kinds.count("stop") == 1
        assert "pipeline.stop_suppressed" not in kinds
        assert stop_posts(posts) == ["hands: the pipeline stopped"]

    drive_notified(tmp_home, workdir, body)


def test_a_send_filed_while_stopped_un_pauses_only_when_its_job_starts(
    project: str, workdir: Path
) -> None:
    """§10: a `cli` send un-pauses "only when that job **starts** (a held or queued
    send changes nothing)". The gate of §8 is what holds it: filing it leaves the
    stop exactly as it was, and approving it is what clears it."""

    async def body(daemon: Daemon) -> None:
        await daemon.playbook.stop("a rule said so")
        job = await ok(
            "send", "--role", "builder", "--context", "clear", "--gate", "by hand",
            "FAKE:result VERDICT: whatever",
        )
        assert job["state"] == "held"
        held = await ok("pipeline")
        assert held["paused"] is True, "filing a send is not an answer to the stop"
        assert held["stop_reason"] == "a rule said so"
        assert [event["kind"] for event in (await ok("inbox"))["events"]] == [
            "stop",
            "job.held",
        ]

        await ok("approve", job["id"])
        await ok("wait", job["id"])

        state = await ok("pipeline")
        assert state["paused"] is False
        assert state["stop_reason"] is None
        resumed = [
            event
            for event in (await ok("inbox"))["events"]
            if event["kind"] == "pipeline.resumed"
        ]
        assert [event["payload"]["by"] for event in resumed] == ["start"]
        assert resumed[0]["payload"]["was"] == "a rule said so"

    drive(body)


def test_a_resume_still_clears_a_stop_whatever_its_reason(
    project: str, workdir: Path
) -> None:
    """The no-op is the pause path only: `hands resume` un-pauses a rule stop that a
    pause no longer overwrites, or a stop could only be cleared by a `send`."""
    write_playbook(workdir, EXAMPLE)

    async def body(daemon: Daemon) -> None:
        await daemon.playbook.stop("a rule said so")
        code, out, err = await cli("pause")
        assert code == 0, err
        assert "a rule said so" in strip_paths(out)
        assert (await ok("resume"))["paused"] is False
        assert (await ok("pipeline"))["stop_reason"] is None

    drive(body)


def test_a_job_the_engine_fires_is_still_gated_by_the_default_patterns(
    project: str, workdir: Path
) -> None:
    """§8: gating on the default patterns cannot be disabled — not even for hands."""
    write_playbook(
        workdir,
        "version = 1\n"
        '[[rule]]\non = "builder.done"\nverdict = "^VERDICT: ok"\nthen = "send"\n'
        'role = "aux"\ncontext = "clear"\nprompt = "Apply decisions-1.md to WORKPLAN.md"\n',
    )

    async def body(daemon: Daemon) -> None:
        await ok("send", "--role", "builder", "--context", "clear", "FAKE:result VERDICT: ok")
        rows = await wait_for_jobs(2)
        fired = [row for row in rows if row["origin"] == "playbook"][0]
        record = await ok("result", fired["id"])
        assert record["state"] == "held"
        assert record["origin"] == "playbook"
        assert record["playbook_sha256"]
        assert "decisions-" in strip_paths(record["gate"]["reason"])
        # …and the held job is itself a §10 event with no rule: hands stops.
        state = await wait_for_stop()
        assert "job.held" in strip_paths(state["stop_reason"])

    drive(body)


def test_the_daemon_stops_the_pipeline_on_an_unmatched_event(
    project: str, workdir: Path
) -> None:
    write_playbook(workdir, 'version = 1\n[[rule]]\non = "aux.done"\nthen = "stop"\n')

    async def body(daemon: Daemon) -> None:
        job = await ok("send", "--role", "builder", "--context", "clear", "FAKE:result ok")
        await ok("wait", job["id"])
        state = await wait_for_stop()
        assert "builder.done" in strip_paths(state["stop_reason"])
        events = (await ok("inbox"))["events"]
        assert [event["kind"] for event in events][-1] == "stop"

    drive(body)


def test_a_dirty_playbook_is_refused_at_job_start(project: str, workdir: Path) -> None:
    """Mission 9 acceptance (§10, §25), through the daemon's real job-start path:
    a `PLAYBOOK.toml` edited after its commit is refused when a job starts, the
    pipeline stops with the refusal as its reason, the inbox `stop` event says so,
    and no rule of the edited file fires."""
    committed = commit_file(workdir, "PLAYBOOK.toml", EXAMPLE)
    dirty = EXAMPLE + "\n# edited after the commit\n"
    (workdir / "PLAYBOOK.toml").write_text(dirty)
    working = hashlib.sha256(dirty.encode("utf-8")).hexdigest()

    async def body(daemon: Daemon) -> None:
        job = await ok(
            "send", "--role", "builder", "--context", "clear",
            "FAKE:result VERDICT: run 2 finished",
        )
        await ok("wait", job["id"])
        state = await wait_for_stop()
        reason = state["stop_reason"]
        assert "dirty" in strip_paths(reason)
        assert f"working sha256 {working}" in strip_paths(reason)
        assert f"committed sha256 {committed}" in strip_paths(reason)
        assert state["playbook"]["loaded"] is False
        stops = [e for e in (await ok("inbox"))["events"] if e["kind"] == "stop"]
        assert len(stops) == 1
        assert stops[0]["payload"]["reason"] == reason
        assert len((await ok("jobs", "-n", "50"))["jobs"]) == 1, "a refused file fired a rule"

    drive(body)


# ------------------------------------------- the acceptance criterion (§10)


def test_the_section_10_example_end_to_end(
    tmp_home: Path, workdir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """run finished → review sent → blockers=0 → run 3 sent → run 4 stops (§10)."""
    git_repo(workdir)
    write_project(tmp_home, config_body(tmp_home, workdir))
    write_playbook(workdir, EXAMPLE)
    replies = tmp_home / "replies.json"
    replies.write_text(
        json.dumps(
            [
                "VERDICT: run 2 finished",
                "VERDICT: review run 2 blockers=0",
                "VERDICT: run 3 finished",
                "VERDICT: review run 3 blockers=0",
            ]
        )
    )
    monkeypatch.setenv("HANDS_FAKE_CLAUDE_REPLIES", str(replies))

    async def body(daemon: Daemon) -> None:
        first = await ok(
            "send", "--role", "builder", "--context", "clear", "Execute WORKPLAN.md run 2"
        )
        await ok("wait", first["id"])
        state = await wait_for_stop()

        rows = sorted((await ok("jobs", "-n", "50"))["jobs"], key=lambda row: row["id"])
        assert [(row["role"], row["origin"]) for row in rows] == [
            ("builder", "cli"),
            ("aux", "playbook"),
            ("builder", "playbook"),
            ("aux", "playbook"),
        ]
        records = [await ok("result", row["id"]) for row in rows]
        assert records[1]["prompt"] == REVIEW_PROMPT
        assert records[2]["prompt"] == "Execute WORKPLAN.md run 3"
        assert records[3]["prompt"] == REVIEW_PROMPT
        assert all(record["state"] == "done" for record in records)
        sha = state["playbook"]["sha256"]
        assert [record["playbook_sha256"] for record in records] == [None, sha, sha, sha]

        assert state["auto_runs"] == {"allowed": [2, 3], "used": [3]}
        assert "would start run 4, which [limits] auto_runs does not list ([2, 3])" in (
            strip_paths(state["stop_reason"])
        )
        kinds = [event["kind"] for event in (await ok("inbox"))["events"]]
        assert kinds.count("playbook.rule") == 3
        assert kinds[-1] == "stop"

    drive(body)


#: The harness's terminating line, verbatim from job 0mtygi953-ym63 (H-014).
TERMINATING = (
    "Background tasks still running after 600s; terminating. "
    "Set CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0 to wait indefinitely."
)


def test_a_harness_terminated_builder_job_is_failed_and_the_example_resumes_it(
    tmp_home: Path, workdir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§23, H-014: `builder.failed → resume`, over the §10 example in a real daemon.

    The first builder job ends like job 0mtygi953-ym63 — a final success result
    with no verdict, `num_turns`, exit 0, and the terminating line on stderr:
    DESIGN v3.8 §6 lets the line win even over a `success` result. That job is
    `failed`, the example's
    `builder.failed` rule resumes it, and the resumed job's own
    `VERDICT: question` is what stops the pipeline.
    """
    git_repo(workdir)
    write_project(tmp_home, config_body(tmp_home, workdir))
    write_playbook(workdir, EXAMPLE)
    replies = tmp_home / "replies.json"
    replies.write_text(
        json.dumps(
            [
                {
                    "result": "U0–U5 are committed; I'll continue with U6 when it reports back.",
                    "stderr": TERMINATING,
                },
                "VERDICT: question resumed after the termination",
            ]
        )
    )
    monkeypatch.setenv("HANDS_FAKE_CLAUDE_REPLIES", str(replies))

    async def body(daemon: Daemon) -> None:
        first = await ok(
            "send", "--role", "builder", "--context", "clear", "Execute WORKPLAN.md run 2"
        )
        await ok("wait", first["id"])
        state = await wait_for_stop()

        rows = sorted((await ok("jobs", "-n", "50"))["jobs"], key=lambda row: row["id"])
        assert [(row["role"], row["origin"]) for row in rows] == [
            ("builder", "cli"),
            ("builder", "playbook"),
        ]
        failed, resumed = [await ok("result", row["id"]) for row in rows]
        assert failed["state"] == "failed"
        assert failed["failure_reason"] == "harness_terminated"
        assert failed["exit_code"] == 0
        assert failed["result"].startswith("U0–U5")  # a final result event was there
        assert failed["num_turns"] is not None  # H-014's shape carries turns
        assert TERMINATING in strip_paths(failed["stderr_tail"])

        assert resumed["resumed_from"] == failed["id"]
        assert resumed["context"] == "clear"
        assert resumed["prompt"] == failed["prompt"]  # no resume_line configured (H-008)
        assert resumed["playbook_sha256"] == state["playbook"]["sha256"]
        assert resumed["state"] == "done"
        assert resumed["failure_reason"] is None

        events = (await ok("inbox"))["events"]
        kinds = [event["kind"] for event in events]
        assert kinds.index("job.failed") < kinds.index("resume")
        resume = next(event for event in events if event["kind"] == "resume")
        assert resume["payload"]["resumed_from"] == failed["id"]
        assert resume["payload"]["job"] == resumed["id"]
        assert kinds[-1] == "stop"

    drive(body)


def test_the_chain_does_not_restart_after_a_stop(tmp_home: Path, workdir: Path) -> None:
    """A stopped pipeline is stopped: the jobs already queued may finish, but
    nothing new is chained until a human resumes (§10, stop → resume cycle)."""
    write_project(tmp_home, config_body(tmp_home, workdir))
    write_playbook(
        workdir,
        "version = 1\n"
        '[[rule]]\non = "builder.done"\nverdict = "^VERDICT: stop me"\nthen = "stop"\n'
        'message = "asked for"\n',
    )

    async def body(daemon: Daemon) -> None:
        job = await ok(
            "send", "--role", "builder", "--context", "clear", "FAKE:result VERDICT: stop me"
        )
        await ok("wait", job["id"])
        state = await wait_for_stop()
        assert state["stop_reason"] == "asked for"
        assert state["last_rule"]["then"] == "stop"

        again = await ok(
            "send", "--role", "builder", "--context", "clear", "FAKE:result VERDICT: stop me"
        )
        assert (await ok("pipeline"))["paused"] is False  # the send un-paused it (§10)
        await ok("wait", again["id"])
        await wait_for_stop()

    drive(body)


def test_the_verdict_regex_named_groups_reach_the_message(
    tmp_home: Path, workdir: Path
) -> None:
    write_project(tmp_home, config_body(tmp_home, workdir))
    write_playbook(workdir, EXAMPLE)

    async def body(daemon: Daemon) -> None:
        job = await ok(
            "send",
            "--role",
            "aux",
            "--context",
            "clear",
            "FAKE:result VERDICT: review run 5 blockers=2",
        )
        await ok("wait", job["id"])
        state = await wait_for_stop()
        assert state["stop_reason"] == "Review of run 5 has blockers"

    drive(body)




# ------------------------------------------- §27: consult, driver.done, max_consults

KICKOFF = "Kick off mission 11"

CONSULT_BOOK = f"""version = 1

[series]
kickoff = "{KICKOFF}"

[limits]
max_consults = 2

[[rule]]
on = "builder.done"
verdict = '^VERDICT: question'
then = "consult"

[[rule]]
on = "builder.done"
verdict = '^VERDICT: answered'
then = "notify"
message = "the builder answered"

[[rule]]
on = "driver.done"
verdict = '^VERDICT: resolved (?P<what>.+)'
then = "notify"
message = "consult resolved: {{what}}"

[[rule]]
on = "driver.done"
verdict = '^VERDICT: escalate (?P<reason>.+)'
then = "stop"
message = "driver escalated: {{reason}}"
"""

QUESTION_RESULT = (
    "VERDICT: question may U5 count consults from the kickoff?\n"
    "Details, verbatim: {not a placeholder} and a FAKE-free line.\n"
)


def test_the_consult_prompt_carries_the_event_the_record_and_the_reply_verbatim(
    tmp_home: Path, workdir: Path
) -> None:
    driver = workdir.parent / "driver"
    engine, recorder = engine_for(tmp_home, workdir, CONSULT_BOOK, driver=driver)
    job = engine.spool.create_job(role="builder", context="clear", prompt="p", origin="cli")
    engine.spool.transition(job, "running")
    job = engine.spool.transition(
        job, "done", verdict=QUESTION_RESULT.splitlines()[0], result=QUESTION_RESULT
    )

    run(engine.on_job(job))

    assert not engine.state.paused, engine.state.stop_reason
    assert recorder.sent == []  # never through Api.send, which refuses the driver (U4)
    [call] = recorder.enqueued
    assert call["role"] == "driver"
    assert call["context"] == "clear"
    assert call["origin"] == "playbook"
    assert call["playbook_sha256"] == engine.playbook.sha256  # type: ignore[union-attr]
    prompt = call["prompt"]
    assert prompt == consult_prompt("builder.done", job)
    assert QUESTION_RESULT in strip_paths(prompt)  # the role's last reply, verbatim
    for said in ("builder.done", job.id, "builder", str(job.verdict), CONSULT_QUESTION,
                 *DRIVER_VERDICTS, "hands send --role builder --context keep"):
        assert said in strip_paths(prompt), said
    assert CONSULT_QUESTION == (
        "resolve within your authority, citing the mission file or DESIGN section, or escalate"
    )
    assert DRIVER_VERDICTS == (
        "VERDICT: resolved <what was sent, and the section cited>",
        "VERDICT: escalate <reason>",
    )
    events = engine.spool.events()
    sent = [event for event in events if event.kind == "consult.sent"]
    assert len(sent) == 1
    assert sent[0].payload["job"] == "enq-1"
    assert sent[0].payload["about"] == job.id
    assert sent[0].payload["event"] == "builder.done"
    rule = [event for event in events if event.kind == "playbook.rule"]
    assert rule[-1].payload["then"] == "consult"
    assert rule[-1].payload["fired_job"] == "enq-1"


def test_a_consult_with_no_driver_role_configured_stops_and_starts_nothing(
    tmp_home: Path, workdir: Path
) -> None:
    engine, recorder = engine_for(tmp_home, workdir, CONSULT_BOOK)
    job = finished(engine.spool, verdict="VERDICT: question x")
    run(engine.on_job(job))
    assert recorder.enqueued == []
    assert engine.state.paused
    assert "[roles.driver]" in strip_paths(engine.state.stop_reason or "")


def _driver_job(spool: Spool, *, state: str, verdict: str | None, about: Job) -> Job:
    job = spool.create_job(
        role="driver",
        context="clear",
        prompt=consult_prompt("builder.done", about),
        origin="playbook",
    )
    spool.transition(job, "running")
    return spool.transition(job, state, verdict=verdict, result=verdict)


def test_an_unrecognised_driver_verdict_stops(tmp_home: Path, workdir: Path) -> None:
    engine, recorder = engine_for(tmp_home, workdir, CONSULT_BOOK, driver=workdir.parent / "d")
    about = finished(engine.spool, verdict="VERDICT: question x")
    driver = _driver_job(engine.spool, state="done", verdict="VERDICT: maybe", about=about)
    run(engine.on_job(driver))
    assert engine.state.paused
    assert (
        "driver.done: the driver's verdict 'VERDICT: maybe' is neither resolved nor escalate"
        in strip_paths(engine.state.stop_reason or "")
    )
    assert recorder.enqueued == []


def test_a_resolved_driver_verdict_notifies_and_does_not_stop(
    tmp_home: Path, workdir: Path
) -> None:
    engine, recorder = engine_for(tmp_home, workdir, CONSULT_BOOK, driver=workdir.parent / "d")
    about = finished(engine.spool, verdict="VERDICT: question x")
    driver = _driver_job(
        engine.spool, state="done", verdict="VERDICT: resolved sent keep, §27", about=about
    )
    run(engine.on_job(driver))
    assert not engine.state.paused, engine.state.stop_reason
    assert [title for title, _ in recorder.notified] == ["hands: consult resolved: sent keep, §27"]


def test_a_failed_driver_job_stops_and_notifies(tmp_home: Path, workdir: Path) -> None:
    engine, recorder = engine_for(tmp_home, workdir, CONSULT_BOOK, driver=workdir.parent / "d")
    about = finished(engine.spool, verdict="VERDICT: question x")
    driver = _driver_job(engine.spool, state="failed", verdict=None, about=about)
    run(engine.on_job(driver))
    assert engine.state.paused
    assert "driver.failed: the consultation's driver job ended failed" in strip_paths(
        engine.state.stop_reason or ""
    )
    assert [title for title, _ in recorder.notified] == ["hands: the pipeline stopped"]


def test_a_driver_job_that_ends_files_consult_done_and_one_journal_line(
    tmp_home: Path, workdir: Path
) -> None:
    engine, _recorder = engine_for(
        tmp_home, workdir, CONSULT_BOOK, driver=workdir.parent / "d"
    )
    about = finished(engine.spool, verdict="VERDICT: question x")
    verdict = "VERDICT: resolved sent the answer to builder, DESIGN §27"
    driver = _driver_job(engine.spool, state="done", verdict=verdict, about=about)
    run(engine.on_job(driver))
    [done] = [event for event in engine.spool.events() if event.kind == "consult.done"]
    assert done.payload["job"] == driver.id
    assert done.payload["about"] == about.id
    assert done.payload["state"] == "done"
    assert done.payload["verdict"] == verdict
    journal = workdir / "meta" / "journal.md"
    lines = journal.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert driver.id in lines[0] and about.id in lines[0] and verdict in strip_paths(lines[0])
    assert engine.spool.load_job(driver.id).result == verdict  # stored verbatim (§6)


def test_max_consults_is_counted_from_the_last_kickoff(tmp_home: Path, workdir: Path) -> None:
    """§27: `[limits] max_consults` per mission; the mission starts at the last
    builder job whose prompt is the `[series] kickoff` line (not a resume of it)."""
    engine, recorder = engine_for(tmp_home, workdir, CONSULT_BOOK, driver=workdir.parent / "d")
    spool = engine.spool
    about = finished(spool, verdict="VERDICT: question x")
    for _ in range(3):  # an earlier mission's consultations
        _driver_job(spool, state="done", verdict="VERDICT: resolved a", about=about)
    kickoff = spool.create_job(role="builder", context="clear", prompt=KICKOFF, origin="phone")
    spool.transition(kickoff, "running")
    spool.transition(kickoff, "done")
    _driver_job(spool, state="done", verdict="VERDICT: resolved b", about=about)
    assert engine.pipeline()["consults"] == {"used": 1, "max_consults": 2}

    question = finished(spool, verdict="VERDICT: question y")
    run(engine.on_job(question))
    assert len(recorder.enqueued) == 1 and not engine.state.paused
    # The Recorder files no job: the second consultation is put in the spool by hand.
    _driver_job(spool, state="done", verdict="VERDICT: resolved c", about=question)

    third = finished(spool, verdict="VERDICT: question z")
    run(engine.on_job(third))
    assert len(recorder.enqueued) == 1, "a consult beyond max_consults started a driver job"
    assert engine.state.paused
    assert "[limits] max_consults is 2" in strip_paths(engine.state.stop_reason or "")


def test_max_consults_defaults_to_2(tmp_path: Path) -> None:
    book = parse_playbook("version = 1", path=tmp_path / "PLAYBOOK.toml")
    assert book.max_consults == 2
    book = parse_playbook("version = 1\n[limits]\nmax_consults = 5", path=tmp_path / "P.toml")
    assert book.max_consults == 5


# ------------------------------------------------------- §27 end to end


def _consult_project(tmp_home: Path, workdir: Path) -> Path:
    driver = tmp_home.parent / "driver"
    driver.mkdir()
    write_project(
        tmp_home, config_body(tmp_home, workdir, extra=f'[roles.driver]\ncwd = "{driver}"')
    )
    write_playbook(workdir, CONSULT_BOOK)
    return driver


def _keep_send_argv(prompt: str) -> list[str]:
    """What the scripted driver runs: `hands send --context keep` to the builder."""
    import sys

    return [
        sys.executable,
        "-c",
        "import sys; from hands.cli import main; sys.exit(main(sys.argv[1:]))",
        "--project", PROJECT, "send", "--role", "builder", "--context", "keep", prompt,
    ]


async def _events(kind: str) -> list[dict[str, Any]]:
    return [e for e in (await ok("inbox"))["events"] if e["kind"] == kind]


async def _wait_events(kind: str, count: int) -> list[dict[str, Any]]:
    async def check() -> Any:
        found = await _events(kind)
        return found if len(found) >= count else None

    return await poll(check, f"{count} {kind} event(s)")


def test_a_question_is_consulted_and_resolved_by_a_keep_send_without_a_stop(
    tmp_home: Path, workdir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """(a) builder `VERDICT: question` → consult → the driver sends `keep` to the
    builder and replies `VERDICT: resolved …` → no stop."""
    _consult_project(tmp_home, workdir)
    resolved = "VERDICT: resolved sent the answer to builder, DESIGN §27"
    replies = tmp_home / "replies.json"
    replies.write_text(
        json.dumps(
            [
                QUESTION_RESULT,
                {"result": resolved, "exec": _keep_send_argv("Yes: count from the kickoff")},
                "VERDICT: answered",
            ]
        )
    )
    monkeypatch.setenv("HANDS_FAKE_CLAUDE_REPLIES", str(replies))

    async def body(daemon: Daemon) -> None:
        first = await ok("send", "--role", "builder", "--context", "clear", KICKOFF)
        await ok("wait", first["id"])
        await _wait_events("consult.done", 1)
        rules = await _wait_events("playbook.rule", 3)  # consult, resolved, answered

        rows = sorted((await ok("jobs", "-n", "50"))["jobs"], key=lambda row: row["id"])
        assert [(row["role"], row["origin"]) for row in rows] == [
            ("builder", "cli"),
            ("driver", "playbook"),
            ("builder", "cli"),  # the driver's own `hands send`
        ]
        builder, driver, keep = [await ok("result", row["id"]) for row in rows]
        await ok("wait", keep["id"])
        keep = await ok("result", keep["id"])
        assert driver["context"] == "clear"
        assert driver["result"] == resolved  # the reply, verbatim in the record
        assert QUESTION_RESULT in strip_paths(driver["prompt"])
        assert keep["context"] == "keep" and keep["prompt"] == "Yes: count from the kickoff"
        assert keep["session_id"] == builder["session_id"]
        assert [rule["payload"]["then"] for rule in rules][:2] == ["consult", "notify"]

        state = await ok("pipeline")
        assert state["paused"] is False, state["stop_reason"]
        assert state["consults"] == {"used": 1, "max_consults": 2}
        [sent] = await _events("consult.sent")
        [done] = await _events("consult.done")
        assert sent["payload"]["job"] == driver["id"] == done["payload"]["job"]
        assert done["payload"]["verdict"] == resolved
        lines = (workdir / "meta" / "journal.md").read_text(encoding="utf-8").splitlines()
        assert len(lines) == 1 and driver["id"] in lines[0]

    drive(body)


def test_a_question_consulted_and_escalated_stops_with_the_reason(
    tmp_home: Path, workdir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """(b) question → consult → `VERDICT: escalate …` → stopped, the reason in the message."""
    _consult_project(tmp_home, workdir)
    replies = tmp_home / "replies.json"
    replies.write_text(
        json.dumps([QUESTION_RESULT, "VERDICT: escalate the mission file does not decide it"])
    )
    monkeypatch.setenv("HANDS_FAKE_CLAUDE_REPLIES", str(replies))

    async def body(daemon: Daemon) -> None:
        first = await ok("send", "--role", "builder", "--context", "clear", KICKOFF)
        await ok("wait", first["id"])
        state = await wait_for_stop()
        assert state["stop_reason"] == "driver escalated: the mission file does not decide it"
        drivers = [row for row in (await ok("jobs", "-n", "50"))["jobs"]
                   if row["role"] == "driver"]
        assert len(drivers) == 1
        assert len(await _events("consult.sent")) == 1
        assert len(await _events("consult.done")) == 1

    drive(body)


def test_a_third_consult_in_one_mission_stops_naming_max_consults(
    tmp_home: Path, workdir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """(c) two consultations resolve; the third question stops, and no third driver job."""
    _consult_project(tmp_home, workdir)
    replies = tmp_home / "replies.json"
    replies.write_text(
        json.dumps(
            [
                QUESTION_RESULT,
                "VERDICT: resolved one, §27",
                QUESTION_RESULT,
                "VERDICT: resolved two, §27",
                QUESTION_RESULT,
            ]
        )
    )
    monkeypatch.setenv("HANDS_FAKE_CLAUDE_REPLIES", str(replies))

    async def body(daemon: Daemon) -> None:
        for n, prompt in enumerate((KICKOFF, "Second question round"), start=1):
            job = await ok("send", "--role", "builder", "--context", "clear", prompt)
            await ok("wait", job["id"])
            await _wait_events("consult.done", n)
            await _wait_events("playbook.rule", 2 * n)
            assert (await ok("pipeline"))["paused"] is False
        job = await ok("send", "--role", "builder", "--context", "clear", "Third question round")
        await ok("wait", job["id"])
        state = await wait_for_stop()
        assert "[limits] max_consults is 2" in strip_paths(state["stop_reason"])
        drivers = [row for row in (await ok("jobs", "-n", "50"))["jobs"]
                   if row["role"] == "driver"]
        assert len(drivers) == 2
        assert len(await _events("consult.sent")) == 2

    drive(body)


# ------------------------------------ §28: the engine's driver stops (U2, m12)

#: A playbook with a consult rule and no rule on any driver event.
NO_DRIVER_RULES = f"""version = 1

[series]
kickoff = "{KICKOFF}"

[[rule]]
on = "builder.done"
verdict = '^VERDICT: question'
then = "consult"
"""

#: A playbook whose own driver rules would carry on instead of stopping.
CARRY_ON = f"""version = 1

[series]
kickoff = "{KICKOFF}"

[[rule]]
on = "driver.done"
verdict = '^VERDICT: resolved (?P<what>.+)'
then = "notify"
message = "resolved: {{what}}"

[[rule]]
on = "driver.done"
verdict = '^VERDICT: escalate'
then = "notify"
message = "escalated, carrying on"

[[rule]]
on = "driver.done"
then = "send"
role = "builder"
prompt = "carry on"

[[rule]]
on = "driver.failed"
then = "send"
role = "builder"
prompt = "carry on"

[[rule]]
on = "driver.killed"
then = "notify"
message = "killed, carrying on"

[[rule]]
on = "driver.orphaned"
then = "notify"
message = "orphaned, carrying on"

[[rule]]
on = "driver.limited"
then = "notify"
message = "limited, carrying on"
"""


def test_the_driver_end_events_are_events() -> None:
    """§28: `driver.killed`, `driver.orphaned` and `driver.limited` are events."""
    wanted = ["driver.done", "driver.failed", "driver.killed", "driver.orphaned",
              "driver.limited"]
    assert set(wanted) <= set(EVENTS), sorted(set(wanted) - set(EVENTS))


@pytest.mark.parametrize(
    ("state", "verdict", "reason"),
    [
        ("done", "VERDICT: escalate the brief is silent",
         "the driver escalated: the brief is silent"),
        ("done", "VERDICT: maybe", "neither resolved nor escalate"),
        ("done", None, "no VERDICT: line"),
        ("failed", None, "driver.failed"),
        ("killed", None, "driver.killed"),
        ("orphaned", None, "driver.orphaned"),
        ("limited", None, "driver.limited"),
    ],
)
@pytest.mark.parametrize("body", [NO_DRIVER_RULES, CARRY_ON], ids=["no-driver-rules", "carry-on"])
def test_the_engine_stops_a_consultation_whatever_the_playbooks_driver_rules(
    tmp_home: Path, workdir: Path, body: str, state: str, verdict: str | None, reason: str
) -> None:
    """§28: escalate, an unrecognised verdict, `driver.failed`, `killed`, `orphaned`
    and `limited` stop and notify, and a playbook's own `driver.*` rules (notify,
    send) cannot remove the stop: no rule of theirs fires, no job is sent."""
    engine, recorder = engine_for(tmp_home, workdir, body, driver=workdir.parent / "d")
    about = finished(engine.spool, verdict="VERDICT: question x")
    run(engine.on_job(_driver_job(engine.spool, state=state, verdict=verdict, about=about)))
    assert engine.state.paused, (state, verdict)
    assert reason in strip_paths(engine.state.stop_reason or "")
    assert "§28" in strip_paths(engine.state.stop_reason or "")
    assert recorder.sent == [] and recorder.enqueued == []
    assert [title for title, _ in recorder.notified] == ["hands: the pipeline stopped"]
    assert [e for e in engine.spool.events() if e.kind == "playbook.rule"] == []
    [done] = [e for e in engine.spool.events() if e.kind == "consult.done"]
    assert done.payload["state"] == state  # §28: consult.done carries the terminal state


def test_a_resolved_verdict_still_goes_to_the_playbooks_own_rules(
    tmp_home: Path, workdir: Path
) -> None:
    """§28: "a playbook may add rules on `driver.done` for its own messages"."""
    engine, recorder = engine_for(tmp_home, workdir, CARRY_ON, driver=workdir.parent / "d")
    about = finished(engine.spool, verdict="VERDICT: question x")
    verdict = "VERDICT: resolved sent keep, §27"
    run(engine.on_job(_driver_job(engine.spool, state="done", verdict=verdict, about=about)))
    assert not engine.state.paused, engine.state.stop_reason
    assert [title for title, _ in recorder.notified] == ["hands: resolved: sent keep, §27"]


def test_a_playbook_stop_rule_on_an_escalation_keeps_its_message(
    tmp_home: Path, workdir: Path
) -> None:
    """The engine's stop is not a second stop: a matching `stop` rule is the stop."""
    engine, recorder = engine_for(tmp_home, workdir, CONSULT_BOOK, driver=workdir.parent / "d")
    about = finished(engine.spool, verdict="VERDICT: question x")
    driver = _driver_job(engine.spool, state="done", verdict="VERDICT: escalate why", about=about)
    run(engine.on_job(driver))
    assert engine.state.stop_reason == "driver escalated: why"
    assert [title for title, _ in recorder.notified] == ["hands: the pipeline stopped"]


def test_max_consults_counts_from_a_kickoff_seen_before_it_was_renamed(
    tmp_home: Path, workdir: Path
) -> None:
    """§28: the count starts at the most recent job whose prompt equals *any*
    `[series] kickoff` value seen in the pipeline's history, or the last kit apply,
    whichever is later; renaming the kickoff does not freeze it. "Seen" is
    remembered in `pipeline.json`, so a fresh engine (a daemon restart) keeps it."""
    driver_dir = workdir.parent / "d"
    engine, _ = engine_for(tmp_home, workdir, CONSULT_BOOK, driver=driver_dir)
    spool = engine.spool
    about = finished(spool, verdict="VERDICT: question x")
    for _ in range(3):  # an earlier mission's consultations
        _driver_job(spool, state="done", verdict="VERDICT: resolved a", about=about)
    kickoff = spool.create_job(role="builder", context="clear", prompt=KICKOFF, origin="phone")
    run(engine.on_job_start(kickoff))  # the kickoff job starts: its playbook is loaded
    spool.transition(kickoff, "running")
    spool.transition(kickoff, "done")
    _driver_job(spool, state="done", verdict="VERDICT: resolved b", about=about)
    assert engine.consults_used(engine.playbook) == 1

    renamed = CONSULT_BOOK.replace(KICKOFF, "Kick off mission 12")
    commit_file(workdir, "PLAYBOOK.toml", renamed)
    fresh = PlaybookEngine(
        make_config(tmp_home, workdir, driver=driver_dir), Spool(tmp_home / ".hands"),
        send=Recorder().send, enqueue=Recorder().enqueue,
    )
    run(fresh.on_job_start(finished(spool, verdict="VERDICT: question y")))
    assert fresh.playbook is not None and fresh.playbook.kickoff == "Kick off mission 12"
    assert fresh.consults_used(fresh.playbook) == 1
    assert fresh.pipeline()["consults"] == {"used": 1, "max_consults": 2}

    # A kit apply that ran, after the kickoff, is the later start.
    apply = spool.create_job(role="builder", context="clear", prompt="Apply kit", origin="kit")
    spool.transition(apply, "running")
    spool.transition(apply, "done", verdict="VERDICT: kit applied abc")
    assert fresh.consults_used(fresh.playbook) == 0
    _driver_job(spool, state="done", verdict="VERDICT: resolved c", about=about)
    assert fresh.consults_used(fresh.playbook) == 1
    # A kit apply still held (never ran) is not an apply.
    spool.create_job(role="builder", context="clear", prompt="Apply kit 2", origin="kit",
                     state="held")
    assert fresh.consults_used(fresh.playbook) == 1


# ------------------------------- §29: consult edges (mission 13 U4, REVIEW-12 SF3, SF5)

SUPPRESSED_CONSULT = "hands: a consultation stopped over a paused pipeline"


@pytest.mark.parametrize(
    ("state", "verdict", "reason"),
    [
        ("done", "VERDICT: escalate the brief is silent",
         "the driver escalated: the brief is silent"),
        ("done", "VERDICT: maybe", "neither resolved nor escalate"),
        ("done", None, "no VERDICT: line"),
        ("failed", None, "driver.failed"),
        ("killed", None, "driver.killed"),
        ("orphaned", None, "driver.orphaned"),
        ("limited", None, "driver.limited"),
    ],
)
@pytest.mark.parametrize(
    "body", [NO_DRIVER_RULES, CARRY_ON, CONSULT_BOOK, None],
    ids=["no-driver-rules", "carry-on", "stop-rule", "no-playbook"],
)
def test_a_consult_stop_over_a_paused_pipeline_is_suppressed_with_its_reason_and_notifies(
    tmp_home: Path, workdir: Path, body: str | None, state: str, verdict: str | None,
    reason: str,
) -> None:
    """§29 (REVIEW-12 SF3): the engine's consult stops apply whether or not the
    pipeline is paused; over a paused one the stop is `pipeline.stop_suppressed`
    carrying the consult reason, and it notifies, once. The pause keeps its reason
    and no playbook rule fires."""
    engine, recorder = engine_for(tmp_home, workdir, body, driver=workdir.parent / "d")
    run(engine.pause())
    assert [title for title, _ in recorder.notified] == ["hands: the pipeline stopped"]
    about = finished(engine.spool, verdict="VERDICT: question x")
    run(engine.on_job(_driver_job(engine.spool, state=state, verdict=verdict, about=about)))

    assert engine.state.paused and engine.state.stop_reason == PAUSE_REASON
    [suppressed] = [e for e in engine.spool.events() if e.kind == "pipeline.stop_suppressed"]
    assert reason in strip_paths(suppressed.payload["reason"])
    assert "§28" in strip_paths(suppressed.payload["reason"])
    assert suppressed.payload["kept"] == PAUSE_REASON
    assert suppressed.payload["event"] == f"driver.{state}"
    titles = [title for title, _ in recorder.notified]
    assert titles == ["hands: the pipeline stopped", SUPPRESSED_CONSULT], titles
    assert reason in strip_paths(recorder.notified[-1][1]["reason"])
    assert len([e for e in engine.spool.events() if e.kind == "stop"]) == 1  # the pause's
    assert [e for e in engine.spool.events() if e.kind == "playbook.rule"] == []
    assert recorder.sent == [] and recorder.enqueued == []


def test_a_resolved_consultation_over_a_paused_pipeline_files_and_notifies_nothing(
    tmp_home: Path, workdir: Path
) -> None:
    """§10: paused, no rule fires; a resolved consultation is no stop to suppress."""
    engine, recorder = engine_for(tmp_home, workdir, CARRY_ON, driver=workdir.parent / "d")
    run(engine.pause())
    about = finished(engine.spool, verdict="VERDICT: question x")
    verdict = "VERDICT: resolved sent keep, §27"
    run(engine.on_job(_driver_job(engine.spool, state="done", verdict=verdict, about=about)))
    assert [e for e in engine.spool.events() if e.kind == "pipeline.stop_suppressed"] == []
    assert [title for title, _ in recorder.notified] == ["hands: the pipeline stopped"]
    assert [e for e in engine.spool.events() if e.kind == "consult.done"]


def test_a_non_consult_stop_over_a_paused_pipeline_still_notifies_nobody(
    tmp_home: Path, workdir: Path
) -> None:
    """§10's rule for every other stop is unchanged: suppressed, not notified."""
    engine, recorder = engine_for(tmp_home, workdir, EXAMPLE)
    run(engine.pause())
    run(engine.stop("some other stop"))
    [suppressed] = [e for e in engine.spool.events() if e.kind == "pipeline.stop_suppressed"]
    assert suppressed.payload["reason"] == "some other stop"
    assert [title for title, _ in recorder.notified] == ["hands: the pipeline stopped"]


def test_max_consults_counts_from_the_daemon_start_when_no_kickoff_was_seen_since(
    tmp_home: Path, workdir: Path
) -> None:
    """§29 (REVIEW-12 SF5, the reviewer's probe): an older spool with earlier driver
    jobs, a playbook whose kickoff was renamed before any engine saw the old one,
    and a daemon restart: the earlier driver jobs do not count. The anchor is the
    latest of the last kickoff seen, the last kit apply that ran, and daemon start."""
    driver_dir = workdir.parent / "d"
    old = engine_for(tmp_home, workdir, None, driver=driver_dir)[0]
    spool = old.spool
    about = finished(spool, verdict="VERDICT: question x")
    old_kickoff = spool.create_job(
        role="builder", context="clear", prompt="Kick off mission 12", origin="phone"
    )
    spool.transition(old_kickoff, "running")
    spool.transition(old_kickoff, "done")
    for _ in range(4):  # the earlier mission's consultations, under the old kickoff
        _driver_job(spool, state="done", verdict="VERDICT: resolved a", about=about)

    engine, _ = engine_for(tmp_home, workdir, CONSULT_BOOK, driver=driver_dir)
    run(engine._ensure_loaded())
    assert engine.state.kickoffs == [KICKOFF]  # the old kickoff was never seen
    assert engine.consults_used(engine.playbook) == 4  # no daemon start: every one counts

    time.sleep(0.01)  # job timestamps are milliseconds
    engine.daemon_start(now_iso())
    assert engine.consults_used(engine.playbook) == 0
    assert engine.pipeline()["consults"] == {"used": 0, "max_consults": 2}
    _driver_job(spool, state="done", verdict="VERDICT: resolved b", about=about)
    assert engine.consults_used(engine.playbook) == 1

    # A kickoff after the daemon start is the later anchor.
    time.sleep(0.01)
    kickoff = spool.create_job(role="builder", context="clear", prompt=KICKOFF, origin="phone")
    spool.transition(kickoff, "running")
    spool.transition(kickoff, "done")
    assert engine.consults_used(engine.playbook) == 0
    _driver_job(spool, state="done", verdict="VERDICT: resolved c", about=about)
    assert engine.consults_used(engine.playbook) == 1


def test_end_to_end_a_restarted_daemon_counts_consults_from_its_start(
    tmp_home: Path, workdir: Path
) -> None:
    """The probe over a real daemon: its start is the engine's anchor."""
    _consult_project(tmp_home, workdir)
    spool = Spool(tmp_home / ".hands" / PROJECT)  # §29: the daemon's own spool
    about = finished(spool, verdict="VERDICT: question x")
    for _ in range(4):
        _driver_job(spool, state="done", verdict="VERDICT: resolved a", about=about)
    time.sleep(0.01)

    async def body(daemon: Daemon) -> None:
        anchor = daemon.playbook.state.consults_since
        assert anchor is not None and anchor.daemon_start == daemon.started
        assert (await ok("pipeline"))["consults"] == {"used": 0, "max_consults": 2}

    drive(body)


def test_a_daemon_restart_mid_mission_keeps_the_consult_count(
    tmp_home: Path, workdir: Path
) -> None:
    """§30 (REVIEW-13 should-fix 5, the reviewer's probe): the anchor is persisted
    in `pipeline.json`. A kickoff and two consultations after the first daemon
    start are 2 used; after a restart they are still 2, so with max 2 the next
    consult is refused. The restart's own start is not a new anchor while one is
    persisted."""
    _consult_project(tmp_home, workdir)
    spool = Spool(tmp_home / ".hands" / PROJECT)
    started: list[str | None] = []

    async def first(daemon: Daemon) -> None:
        started.append(daemon.started)
        time.sleep(0.01)  # job timestamps are milliseconds
        about = finished(spool, verdict="VERDICT: question x")
        kickoff = spool.create_job(
            role="builder", context="clear", prompt=KICKOFF, origin="phone"
        )
        spool.transition(kickoff, "running")
        spool.transition(kickoff, "done")
        for _ in range(2):
            _driver_job(spool, state="done", verdict="VERDICT: resolved a", about=about)
        assert (await ok("pipeline"))["consults"] == {"used": 2, "max_consults": 2}

    drive(first)
    time.sleep(0.01)

    async def second(daemon: Daemon) -> None:
        assert daemon.started != started[0]
        assert (await ok("pipeline"))["consults"] == {"used": 2, "max_consults": 2}
        question = finished(spool, verdict="VERDICT: question y")
        await daemon.playbook.on_job(question)
        await daemon.playbook.drain()
        assert [job for job in spool.list_jobs() if job.role == "driver"
                and job.state not in ("done",)] == []
        assert "[limits] max_consults is 2" in strip_paths(
            daemon.playbook.state.stop_reason or ""
        )

    drive(second)
    persisted = json.loads((spool.root / "pipeline.json").read_text(encoding="utf-8"))
    assert persisted["consults_since"]["daemon_start"] == started[0]


def test_the_persisted_consult_anchor_names_its_daemon_start_and_the_job_it_derives_from(
    tmp_home: Path, workdir: Path
) -> None:
    """§31 (review 14 should-fix 5): "the `max_consults` anchor stores the job id
    and the daemon start time it derives from, and a test reads them back".

    The anchor was a bare timestamp, so what it was derived from was not on disk.
    It is now an object with both fields, read back here off `pipeline.json`: the
    daemon start is that daemon's own `started`, and the job is the last job in
    the spool at that moment — every job up to it is on the far side of the
    anchor. A second daemon does not move either field."""
    _consult_project(tmp_home, workdir)
    spool = Spool(tmp_home / ".hands" / PROJECT)
    about = finished(spool, verdict="VERDICT: question x")
    started: list[str | None] = []

    async def first(daemon: Daemon) -> None:
        started.append(daemon.started)
        anchor = daemon.playbook.state.consults_since
        assert anchor is not None
        assert anchor.daemon_start == daemon.started
        assert anchor.job == about.id

    drive(first)
    on_disk = json.loads((spool.root / "pipeline.json").read_text(encoding="utf-8"))
    assert on_disk["consults_since"] == {"daemon_start": started[0], "job": about.id}

    # A later job, a later daemon: neither field moves, and the count still runs
    # from the anchor's daemon start.
    time.sleep(0.01)
    _driver_job(spool, state="done", verdict="VERDICT: resolved a", about=about)

    async def second(daemon: Daemon) -> None:
        assert daemon.started != started[0]
        anchor = daemon.playbook.state.consults_since
        assert anchor is not None and (anchor.daemon_start, anchor.job) == (
            started[0], about.id
        )
        assert (await ok("pipeline"))["consults"] == {"used": 1, "max_consults": 2}

    drive(second)
    again = json.loads((spool.root / "pipeline.json").read_text(encoding="utf-8"))
    assert again["consults_since"] == on_disk["consults_since"]


def test_a_pipeline_json_written_before_the_anchor_had_fields_still_reads(
    tmp_home: Path, workdir: Path
) -> None:
    """§31: an older `pipeline.json` persisted the anchor as a bare timestamp
    string. It is read back as the daemon start, with no job, and is not moved by
    the start that finds it."""
    _consult_project(tmp_home, workdir)
    spool = Spool(tmp_home / ".hands" / PROJECT)
    spool.root.mkdir(parents=True, exist_ok=True)
    old = "2026-09-15T00:00:00+00:00"
    (spool.root / "pipeline.json").write_text(
        json.dumps({"consults_since": old}), encoding="utf-8"
    )

    async def body(daemon: Daemon) -> None:
        anchor = daemon.playbook.state.consults_since
        assert anchor is not None and (anchor.daemon_start, anchor.job) == (old, None)
        read = json.loads((spool.root / "pipeline.json").read_text(encoding="utf-8"))
        assert read["consults_since"] == old  # a start that finds one rewrites nothing
        await ok("pause")  # any later save writes the anchor in its widened shape

    drive(body)
    on_disk = json.loads((spool.root / "pipeline.json").read_text(encoding="utf-8"))
    assert on_disk["consults_since"] == {"daemon_start": old, "job": None}


def test_end_to_end_an_escalation_over_a_paused_pipeline_is_suppressed_and_notified(
    tmp_home: Path, workdir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§29: a human pauses while the driver runs; its escalation is filed as
    `pipeline.stop_suppressed` with the consult reason and reaches the phone once."""
    driver = tmp_home.parent / "driver"
    driver.mkdir()
    write_project(
        tmp_home,
        config_body(tmp_home, workdir, extra=f'[roles.driver]\ncwd = "{driver}"').replace(
            "[server]", '[server]\nntfy_topic = "hands-test"\nntfy_url = "https://ntfy.example"'
        ),
    )
    write_playbook(workdir, NO_DRIVER_RULES)
    _script(tmp_home, monkeypatch, [
        QUESTION_RESULT,
        {"result": "VERDICT: escalate the mission file does not decide it",
         "exec": ["sleep", "2"]},
    ])
    posts = Posts()

    async def body(daemon: Daemon) -> None:
        first = await ok("send", "--role", "builder", "--context", "clear", KICKOFF)
        await ok("wait", first["id"])
        await running_job("driver")
        await ok("pause")
        [suppressed] = await _wait_events("pipeline.stop_suppressed", 1)
        assert "the driver escalated: the mission file does not decide it" in strip_paths(
            suppressed["payload"]["reason"]
        )
        assert suppressed["payload"]["kept"] == PAUSE_REASON
        [done] = await _events("consult.done")
        assert done["payload"]["state"] == "done"
        state = await ok("pipeline")
        assert state["paused"] and state["stop_reason"] == PAUSE_REASON
        await daemon.notifier.drain()
        assert posts.sent.count("hands: the pipeline stopped") == 1  # the pause
        assert posts.sent.count(SUPPRESSED_CONSULT) == 1

    async def scenario() -> None:
        daemon = Daemon(load_config(PROJECT))
        daemon.notifier.post = posts  # before start(): no test may reach a network
        await daemon.start()
        try:
            await asyncio.wait_for(body(daemon), 60)
        finally:
            await daemon.stop()

    asyncio.run(scenario())


# ---------------------------------------------- §28 end to end, no driver rules


def _no_rules_project(tmp_home: Path, workdir: Path, driver_extra: str = "") -> Path:
    driver = tmp_home.parent / "driver"
    driver.mkdir(exist_ok=True)
    write_project(
        tmp_home,
        config_body(
            tmp_home, workdir, extra=f'[roles.driver]\ncwd = "{driver}"\n{driver_extra}'
        ),
    )
    write_playbook(workdir, NO_DRIVER_RULES)
    return driver


def _script(tmp_home: Path, monkeypatch: pytest.MonkeyPatch, replies: list[Any]) -> None:
    path = tmp_home / "replies.json"
    path.write_text(json.dumps(replies))
    monkeypatch.setenv("HANDS_FAKE_CLAUDE_REPLIES", str(path))


async def _driver_rows() -> list[dict[str, Any]]:
    return [row for row in (await ok("jobs", "-n", "50"))["jobs"] if row["role"] == "driver"]


async def _stopped_consultation(state: str, reason: str) -> dict[str, Any]:
    """The pipeline stopped with `reason`, one `stop` event, one consult.done in `state`."""
    stopped = await wait_for_stop()
    assert reason in strip_paths(stopped["stop_reason"]), stopped["stop_reason"]
    assert "§28" in strip_paths(stopped["stop_reason"]), "the engine's stop, not §10's default"
    [done] = await _wait_events("consult.done", 1)
    assert done["payload"]["state"] == state
    assert len(await _events("stop")) == 1
    return done


@pytest.mark.parametrize(
    ("reply", "reason"),
    [
        ("VERDICT: escalate the mission file does not decide it",
         "the driver escalated: the mission file does not decide it"),
        ("VERDICT: maybe", "neither resolved nor escalate"),
    ],
    ids=["escalate", "unrecognised"],
)
def test_end_to_end_a_driver_verdict_that_is_not_resolved_stops(
    tmp_home: Path, workdir: Path, monkeypatch: pytest.MonkeyPatch, reply: str, reason: str
) -> None:
    _no_rules_project(tmp_home, workdir)
    _script(tmp_home, monkeypatch, [QUESTION_RESULT, reply])

    async def body(daemon: Daemon) -> None:
        first = await ok("send", "--role", "builder", "--context", "clear", KICKOFF)
        await ok("wait", first["id"])
        await _stopped_consultation("done", reason)
        assert len(await _driver_rows()) == 1

    drive(body)


def test_end_to_end_a_failed_driver_job_stops(
    tmp_home: Path, workdir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The builder's reply is carried verbatim, so its `FAKE:error` line fails the driver."""
    _no_rules_project(tmp_home, workdir)
    _script(tmp_home, monkeypatch, ["VERDICT: question x\nFAKE:error boom"])

    async def body(daemon: Daemon) -> None:
        first = await ok("send", "--role", "builder", "--context", "clear", KICKOFF)
        await ok("wait", first["id"])
        await _stopped_consultation("failed", "driver.failed")

    drive(body)


def test_end_to_end_a_killed_driver_job_stops(
    tmp_home: Path, workdir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _no_rules_project(tmp_home, workdir, "cancel_gated = false")
    _script(tmp_home, monkeypatch, ["VERDICT: question x\nFAKE:block"])

    async def body(daemon: Daemon) -> None:
        first = await ok("send", "--role", "builder", "--context", "clear", KICKOFF)
        await ok("wait", first["id"])

        async def running() -> Any:
            rows = await _driver_rows()
            return rows if rows and rows[0]["state"] == "running" else None

        [row] = await poll(running, "the driver job to run")
        await ok("cancel", row["id"])
        await _stopped_consultation("killed", "driver.killed")

    drive(body)


def test_end_to_end_a_driver_job_that_cannot_spawn_files_consult_done_and_stops(
    tmp_home: Path, workdir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """REVIEW-11 SF2: a driver job the runner refuses before spawning (its prompt,
    which carries the builder's reply verbatim, is over the cap) is `killed`."""
    _no_rules_project(tmp_home, workdir)
    monkeypatch.setattr(hands_runner, "MAX_PROMPT_BYTES", 4000)
    _script(tmp_home, monkeypatch, ["VERDICT: question x\n" + "y" * 5000])

    async def body(daemon: Daemon) -> None:
        first = await ok("send", "--role", "builder", "--context", "clear", KICKOFF)
        await ok("wait", first["id"])
        done = await _stopped_consultation("killed", "driver.killed")
        assert done["payload"]["about"] == first["id"]
        lines = (workdir / "meta" / "journal.md").read_text(encoding="utf-8").splitlines()
        assert len(lines) == 1 and "(driver killed)" in strip_paths(lines[0])

    drive(body)


def test_end_to_end_a_limited_driver_job_stops_and_is_not_resumed(
    tmp_home: Path, workdir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _no_rules_project(tmp_home, workdir)
    _script(tmp_home, monkeypatch, ["VERDICT: question x\nFAKE:rate-limit slow down"])

    async def body(daemon: Daemon) -> None:
        first = await ok("send", "--role", "builder", "--context", "clear", KICKOFF)
        await ok("wait", first["id"])
        await _stopped_consultation("limited", "driver.limited")
        assert [row["state"] for row in await _driver_rows()] == ["limited"]
        assert daemon.limits.pending_resumes() == []  # §28: the consultation ended
        assert not [t for t in daemon.limits._tasks if not t.done()]

    drive(body)


def test_end_to_end_an_orphaned_driver_job_stops_when_the_daemon_starts(
    tmp_home: Path, workdir: Path
) -> None:
    _no_rules_project(tmp_home, workdir)
    spool = Spool(tmp_home / ".hands" / PROJECT)  # §29: the daemon's own spool
    about = finished(spool, verdict="VERDICT: question x")
    job = spool.create_job(
        role="driver", context="clear", prompt=consult_prompt("builder.done", about),
        origin="playbook",
    )
    spool.transition(job, "running")  # no pid: its process is gone

    async def body(daemon: Daemon) -> None:
        done = await _stopped_consultation("orphaned", "driver.orphaned")
        assert done["payload"]["job"] == job.id

    drive(body)


def test_end_to_end_the_driver_job_carries_the_consultations_role(
    tmp_home: Path, workdir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§28: the role the consultation names reaches the driver as HANDS_CONSULT_ROLE,
    whatever handsd's own environment says (U1's guard refuses a role send without it)."""
    _no_rules_project(tmp_home, workdir)
    monkeypatch.setenv("HANDS_CONSULT_ROLE", "aux")
    _script(tmp_home, monkeypatch, ["VERDICT: question x\nFAKE:env HANDS_CONSULT_ROLE"])

    async def body(daemon: Daemon) -> None:
        first = await ok("send", "--role", "builder", "--context", "clear", KICKOFF)
        await ok("wait", first["id"])
        await wait_for_stop()
        [row] = await _driver_rows()
        driver = await ok("result", row["id"])
        assert driver["result"] == "builder"

    drive(body)


# ---------------------------------- §30: the playbooks ship no `job.held` rule


#: The three playbooks this repository ships (DESIGN §10, §30).
SHIPPED_PLAYBOOKS = (
    Path(__file__).parents[1] / "PLAYBOOK.toml",
    Path(__file__).parents[1] / "templates" / "PLAYBOOK-missions.toml",
    Path(__file__).parents[1] / "templates" / "PLAYBOOK-runs.toml",
)


def test_no_shipped_playbook_notifies_on_job_held() -> None:
    """§30: "The `job.held` rule is removed from this repository's playbook and
    from both templates; the daemon's held notification with buttons is the one
    message." A rule here would publish a second message for the same hold."""
    offenders = []
    for path in SHIPPED_PLAYBOOKS:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        for index, rule in enumerate(data.get("rule", []), 1):
            if rule.get("on") == "job.held":
                offenders.append(f"{path.name}: rule {index} is on job.held")
    assert not offenders, "a shipped playbook still doubles the held message:\n" + "\n".join(
        offenders
    )
    # Not a blanket ban: `job.held` stays an event a playbook may use — a kit
    # whose playbook keeps the rule still passes `kit check` (tests/test_kit.py)
    # — and the hold's own notification, with buttons, is still published.
    root = tomllib.loads(SHIPPED_PLAYBOOKS[0].read_text(encoding="utf-8"))
    assert [r["on"] for r in root["rule"] if r["on"] == "job.denied"] == ["job.denied"]


@pytest.mark.parametrize("path", SHIPPED_PLAYBOOKS, ids=lambda path: path.name)
def test_each_shipped_playbook_notifies_a_killed_task_and_stops_a_failed_job(path: Path) -> None:
    """§32: "the example playbook and this repository's map it to `notify`, and a
    job that ends `failed` is what stops". Read through the real loader (the
    committed copy): `monitor.task_killed` has exactly one rule, `notify` with a
    message; `aux.failed` is `stop`; `builder.failed` is `resume`, bounded by a
    `[limits] max_resumes` the file sets, which stops once used up."""
    book = load_playbook(path)
    assert book is not None, f"{path} is missing"

    def thens(event: str) -> list[str]:
        return [rule.then for rule in book.rules if rule.on == event and rule.verdict is None]

    killed = [rule for rule in book.rules if rule.on == "monitor.task_killed"]
    assert [rule.then for rule in killed] == ["notify"], (path.name, killed)
    assert killed[0].message, "a notify needs a message"
    assert thens("aux.failed") == ["stop"], path.name
    assert thens("builder.failed") == ["resume"], path.name
    assert isinstance(book.max_resumes, int), f"{path.name} leaves max_resumes unbounded"
    assert thens("monitor.orphan_processes") == ["stop"], path.name


#: Words that name who or what killed a task. §32: the detector cannot tell a reap
#: from a `TaskStop` or from a backgrounded long foreground command that was reaped.
CAUSE_WORDS = ("harness", "reap", "taskstop", "timeout", "timed out", " by ")


@pytest.mark.parametrize("path", SHIPPED_PLAYBOOKS, ids=lambda path: path.name)
def test_each_shipped_playbook_task_killed_message_names_no_cause(path: Path) -> None:
    """§33 (review 16 should-fix 8), from §32's last paragraph: the detector cannot
    tell who killed a task, so the `monitor.task_killed` rule's message in each
    shipped playbook names no cause (none of `CAUSE_WORDS`)."""
    book = load_playbook(path)
    assert book is not None, f"{path} is missing"
    messages = [rule.message or "" for rule in book.rules if rule.on == "monitor.task_killed"]
    assert messages, f"{path.name} has no monitor.task_killed rule"
    for message in messages:
        named = [word for word in CAUSE_WORDS if word in message.lower()]
        assert not named, f"{path.name}: {message!r} names a cause ({named})"


@pytest.mark.parametrize("path", SHIPPED_PLAYBOOKS, ids=lambda path: path.name)
def test_each_shipped_playbook_under_the_engine_keeps_going_on_a_killed_task(
    path: Path, tmp_home: Path, workdir: Path
) -> None:
    """§32 through the engine: each shipped file, committed in a scratch repository,
    notifies on `monitor.task_killed` without pausing; the builder job that then
    ends `failed` with its resumes used up stops the pipeline, and so does an
    `aux` job that ends `failed`."""
    engine, recorder = engine_for(tmp_home, workdir, body=path.read_text(encoding="utf-8"))
    job = engine.spool.create_job(role="builder", context="clear", prompt="p", origin="cli")
    run(engine.on_job_start(job))
    payload = {"job": job.id, "task_id": "bg1", "command": "sleep 600", "block": "TASK_KILLED"}
    run(engine.on_event("monitor.task_killed", payload=payload))
    assert engine.pipeline()["paused"] is False, engine.pipeline()["stop_reason"]
    assert len(recorder.notified) == 1, recorder.notified
    assert recorder.sent == [] and recorder.enqueued == []

    assert engine.playbook is not None and engine.playbook.max_resumes is not None
    engine.spool.update_role("builder", consecutive_resumes=engine.playbook.max_resumes)
    failed = finished(engine.spool, state="failed")
    run(engine.on_job_start(failed))
    run(engine.on_job(failed))
    assert recorder.enqueued == []
    assert engine.pipeline()["paused"] is True
    assert "max_resumes" in strip_paths(engine.pipeline()["stop_reason"])

    run(engine.resume())  # the human's `hands resume`
    assert engine.pipeline()["paused"] is False
    aux = finished(engine.spool, role="aux", state="failed")
    run(engine.on_job_start(aux))
    run(engine.on_job(aux))
    assert recorder.enqueued == [] and recorder.sent == []
    assert engine.pipeline()["paused"] is True
    assert strip_paths(engine.pipeline()["stop_reason"]) == "Aux job failed"


# ------------------------------- §31: series mode and autonomy (mission 15 U4)

#: A playbook in §31's role mode with `autonomous`, and the escalation conditions
#: §31 writes into `[series]`. Its `builder.done` rule for `^VERDICT: kit applied`
#: is the one the shipped playbooks carry, so the engine-added rule of §31 meets a
#: playbook rule that would also match.
AUTONOMOUS = """
version = 1

[series]
name = "m16"
kickoff = "Read meta/BUILDER-16-PROMPT.md and execute the mission below its divider."
architect = "role"
autonomous = true
gate_failures = 2
escalate_on = ["blocker-unanswered", "milestone-missing", "budget-exhausted"]

[limits]
max_architect_consults = 12

[[rule]]
on = "builder.done"
verdict = '^VERDICT: kit applied'
then = "notify"
message = "Kit applied; the next kickoff is the driver's"

[[rule]]
on = "builder.done"
verdict = '^VERDICT: mission (?P<n>\\d+) finished'
then = "stop"
message = "Mission {n} finished"
"""

PHONE_MODE = AUTONOMOUS.replace('architect = "role"', 'architect = "phone"')
NOT_AUTONOMOUS = AUTONOMOUS.replace("autonomous = true", "autonomous = false")


def series_body(**keys: str) -> str:
    """A minimal playbook whose `[series]` table is exactly `keys`."""
    lines = "\n".join(f"{name} = {value}" for name, value in keys.items())
    return f'version = 1\n\n[series]\nname = "s"\n{lines}\n'


def held_apply(spool: Spool, *, origin: str = "architect", name: str = "m16") -> Job:
    """The held builder job a kit apply is (§27, §31): gated, born `held`."""
    from hands.gates import new_gate

    return spool.create_job(
        role="builder",
        context="clear",
        prompt="Apply the kit.",
        origin=origin,
        state="held",
        gate=new_gate(kind="send", reason=f"apply {name}"),
    )


def consultation(spool: Spool, *, state: str = "running", verdict: str | None = None) -> Job:
    """An architect job, the consultation a kit is filed during (§31, §32)."""
    job = spool.create_job(
        role=ARCHITECT, context="clear", prompt="hands consult: aux.done on job 0 (role aux)\n",
        origin="playbook",
    )
    job = spool.transition(job, "running", session_id="sess-arch-1")
    if state == "running":
        return job
    return spool.transition(job, state, verdict=verdict, result=verdict)


def filed_kit(
    spool: Spool, *, name: str = "m16", during: Job | None = None, **job: Any
) -> Job:
    """§32: a kit's held apply exactly as `Api.kit_file` leaves it — the zip stored
    under `kits/<kit_id>/` by `Spool.store_kit` and its record (`Spool.record_kit`),
    naming the consultation it was filed during and (§33) the passing check handsd
    ran, and the held builder job carrying the kit_id.

    By default the consultation has ended `VERDICT: next kit <name>`: §33's approval
    waits for the verdict's name, so that is the consultation whose kit the engine
    decides at once."""
    from hands.gates import new_gate

    if during is None:
        during = consultation(spool, state="done", verdict=f"VERDICT: next kit {name}")
    kit_id = new_kit_id()
    spool.store_kit(kit_id, name=name, data=b"PK\x05\x06" + bytes(18))
    spool.record_kit(kit_id, name=name, consultation=during.id, check="pass")
    fields: dict[str, Any] = {
        "role": "builder",
        "context": "clear",
        "prompt": "Apply the kit.",
        "origin": "architect",
        "state": "held",
        "gate": new_gate(kind="send", reason=f"apply {name}"),
        "kit_id": kit_id,
        **job,
    }
    return spool.create_job(**fields)


def applied_kit(
    spool: Spool, *, verdict: str = "VERDICT: kit applied abc1234", decided_by: str = "playbook",
    **kw: Any,
) -> Job:
    """A filed kit's apply that was approved (by the engine, unless `decided_by`
    says otherwise) and ran to `done` with `verdict`."""
    from hands.gates import decide

    job = filed_kit(spool, **kw)
    assert job.gate is not None
    gate = decide(job.gate, decision="approved", decided_by=decided_by, reason="r",
                  quote="q" if decided_by == "driver" else None)
    spool.transition(job, "queued", gate=gate)
    spool.transition(job, "running")
    return spool.transition(job, "done", verdict=verdict, result=verdict)


# ---- the keys (§31, refused at load)


def test_the_series_defaults_are_phone_not_autonomous(tmp_home: Path, workdir: Path) -> None:
    """§31: `architect` defaults to `phone`, `autonomous` to `false`. U4 also
    decides the two the design leaves open: `gate_failures` defaults to §31's own
    2, and `escalate_on` to nothing — a condition is enforced when it is written."""
    book = parse_playbook(EXAMPLE, path=workdir / "PLAYBOOK.toml")
    assert book.architect == "phone"
    assert book.autonomous is False
    assert book.gate_failures == 2
    assert book.escalate_on == ()
    assert book.max_architect_consults == DEFAULT_MAX_ARCHITECT_CONSULTS == 12


def test_the_series_keys_of_section_31_load(tmp_home: Path, workdir: Path) -> None:
    book = parse_playbook(AUTONOMOUS, path=workdir / "PLAYBOOK.toml")
    assert book.architect == "role"
    assert book.autonomous is True
    assert book.gate_failures == 2
    assert book.escalate_on == (
        "blocker-unanswered",
        "milestone-missing",
        "budget-exhausted",
    )
    assert book.max_architect_consults == 12
    assert book.kickoff == (
        "Read meta/BUILDER-16-PROMPT.md and execute the mission below its divider."
    )


@pytest.mark.parametrize(
    ("keys", "because"),
    [
        ({"architect": '"laptop"'}, "architect must be"),
        ({"architect": "true"}, "architect must be"),
        ({"autonomous": '"yes"'}, "autonomous must be"),
        ({"autonomous": "1"}, "autonomous must be"),
        ({"gate_failures": "0"}, "gate_failures must be"),
        ({"gate_failures": "-1"}, "gate_failures must be"),
        ({"gate_failures": "true"}, "gate_failures must be"),
        ({"gate_failures": '"2"'}, "gate_failures must be"),
        ({"escalate_on": '"blocker-unanswered"'}, "escalate_on must be a list"),
        ({"escalate_on": "[1]"}, "escalate_on must be a list"),
        ({"escalate_on": '["blocker-unaswered"]'}, "escalate_on"),
        ({"escalate_on": '["budget-exhausted", "nope"]'}, "escalate_on"),
        ({"leader": '"me"'}, "leader"),
    ],
)
def test_the_series_table_refuses_what_section_31_does_not_name(
    workdir: Path, keys: dict[str, str], because: str
) -> None:
    """§10's discipline: refused when the playbook is loaded, never when a rule
    fires. The closed vocabulary of `escalate_on` is §31's three conditions."""
    with pytest.raises(PlaybookError) as caught:
        parse_playbook(series_body(**keys), path=workdir / "PLAYBOOK.toml")
    assert because in strip_paths(str(caught.value)), caught.value


def test_escalate_on_names_the_three_conditions_of_section_31(workdir: Path) -> None:
    with pytest.raises(PlaybookError) as caught:
        parse_playbook(series_body(escalate_on='["nope"]'), path=workdir / "PLAYBOOK.toml")
    for condition in ESCALATE_ON:
        assert condition in strip_paths(str(caught.value))
    assert set(ESCALATE_ON) == {"blocker-unanswered", "milestone-missing", "budget-exhausted"}


@pytest.mark.parametrize("value", ["-1", '"12"', "true"])
def test_max_architect_consults_must_be_a_non_negative_integer(
    workdir: Path, value: str
) -> None:
    body = f"version = 1\n\n[limits]\nmax_architect_consults = {value}\n"
    with pytest.raises(PlaybookError) as caught:
        parse_playbook(body, path=workdir / "PLAYBOOK.toml")
    assert "max_architect_consults" in strip_paths(str(caught.value))


def test_max_architect_consults_is_a_limits_key_the_playbook_may_set(workdir: Path) -> None:
    body = "version = 1\n\n[limits]\nmax_architect_consults = 3\n"
    assert parse_playbook(body, path=workdir / "PLAYBOOK.toml").max_architect_consults == 3
    assert LIMIT_KEYS == ("auto_runs", "max_resumes", "max_consults", "max_architect_consults")


# ---- `architect = "role"` without `[roles.architect]` (§31)


def test_role_mode_without_the_configured_role_is_a_config_error(
    tmp_home: Path, workdir: Path
) -> None:
    """§31: "a `[series] architect = "role"` without `[roles.architect]` is a
    config error". The two live in different files, so the message names both."""
    book = parse_playbook(AUTONOMOUS, path=workdir / "PLAYBOOK.toml")
    config = make_config(tmp_home, workdir)
    with pytest.raises(PlaybookError) as caught:
        check_series_roles(book, config)
    said = str(caught.value)
    assert "PLAYBOOK.toml" in strip_paths(said), said
    assert config.path.name in strip_paths(said), said
    assert "[roles.architect]" in strip_paths(said), said


def test_phone_mode_needs_no_configured_architect(tmp_home: Path, workdir: Path) -> None:
    book = parse_playbook(PHONE_MODE, path=workdir / "PLAYBOOK.toml")
    check_series_roles(book, make_config(tmp_home, workdir))  # no raise


def test_role_mode_with_the_configured_role_loads(tmp_home: Path, workdir: Path) -> None:
    book = parse_playbook(AUTONOMOUS, path=workdir / "PLAYBOOK.toml")
    check_series_roles(book, make_config(tmp_home, workdir, architect=workdir))  # no raise


def test_the_engine_stops_on_a_role_mode_playbook_with_no_architect_role(
    tmp_home: Path, workdir: Path
) -> None:
    """The cross-check runs where a loaded playbook meets the config — the engine's
    own load — so the pipeline stops rather than fire a rule under a playbook the
    project cannot honour."""
    engine, _ = engine_for(tmp_home, workdir, AUTONOMOUS)
    run(engine.on_event("builder.done", job=finished(engine.spool, verdict="VERDICT: x")))
    assert engine.state.paused
    said = engine.state.stop_reason or ""
    assert "[roles.architect]" in strip_paths(said), said
    assert engine.playbook is None


# ---- the engine's approval of the architect's holds (§8, §31)


@pytest.mark.parametrize(
    ("body", "approved"),
    [(AUTONOMOUS, True), (NOT_AUTONOMOUS, False), (PHONE_MODE, False), (EXAMPLE, False)],
    ids=["role+autonomous", "no autonomous", "phone mode", "no series keys"],
)
def test_only_a_role_mode_autonomous_playbook_approves_the_architects_hold(
    tmp_home: Path, workdir: Path, body: str, approved: bool
) -> None:
    engine, recorder = engine_for(tmp_home, workdir, body, architect=workdir)
    job = filed_kit(engine.spool)
    run(engine.on_event("job.held", job=job))
    assert [call["job"] for call in recorder.approved] == ([job.id] if approved else [])
    if approved:
        assert recorder.approved[0]["reason"] == AUTONOMOUS_APPROVAL
        assert not engine.state.paused, "an approved hold is not a stop"
    else:
        # §30: no shipped playbook has a `job.held` rule, so the hold stops the
        # pipeline and waits for a human, exactly as it does today.
        assert engine.state.paused


@pytest.mark.parametrize("origin", ["kit", "cli", "phone", "limit", "playbook"])
def test_the_engine_approves_only_the_architects_own_holds(
    tmp_home: Path, workdir: Path, origin: str
) -> None:
    """§31 names one origin. A kit from the phone, a human's gated send and every
    other origin keep §8's table: only a human releases them."""
    engine, recorder = engine_for(tmp_home, workdir, AUTONOMOUS, architect=workdir)
    job = held_apply(engine.spool, origin=origin)
    run(engine.on_event("job.held", job=job))
    assert recorder.approved == []
    assert engine.spool.load_job(job.id).state == "held"


def test_a_held_architect_apply_under_a_paused_pipeline_is_not_approved(
    tmp_home: Path, workdir: Path
) -> None:
    """§10: a paused pipeline fires nothing, and the engine's approval is the
    pipeline acting. The hold waits for the human who is already being asked."""
    engine, recorder = engine_for(tmp_home, workdir, AUTONOMOUS, architect=workdir)
    run(engine.pause())
    job = filed_kit(engine.spool)
    run(engine.on_event("job.held", job=job))
    assert recorder.approved == []


def test_an_approval_the_api_refuses_stops_the_pipeline(tmp_home: Path, workdir: Path) -> None:
    engine, recorder = engine_for(tmp_home, workdir, AUTONOMOUS, architect=workdir)
    recorder.refuse_approve = "the builder queue is full"
    job = filed_kit(engine.spool)
    run(engine.on_event("job.held", job=job))
    assert engine.state.paused
    assert "the builder queue is full" in strip_paths(engine.state.stop_reason or "")


# ---- §32: the approval is for an apply hands filed from the architect's kit


def _forged(spool: Spool, case: str) -> Job:
    """An architect-origin hold that is *not* an apply hands filed from a kit the
    architect role filed, one way per case (REVIEW-15 blocker 3)."""
    from hands.gates import new_gate

    if case == "no kit_id":
        return held_apply(spool)
    if case == "a kit_id handsd never recorded":
        return spool.create_job(
            role="builder", context="clear", prompt="Apply it.", origin="architect",
            state="held", gate=new_gate(kind="send", reason="apply m16"), kit_id=new_kit_id(),
        )
    if case == "a malformed kit_id":
        return spool.create_job(
            role="builder", context="clear", prompt="Apply it.", origin="architect",
            state="held", gate=new_gate(kind="send", reason="apply m16"), kit_id="../forged",
        )
    if case == "not an apply gate":
        return filed_kit(
            spool, gate=new_gate(kind="send", reason="the prompt matches the gate pattern "
                                 "'gh pr create' (§8)"),
        )
    if case == "the gate names another kit":
        return filed_kit(spool, gate=new_gate(kind="send", reason="apply other"))
    if case == "the zip is gone":
        job = filed_kit(spool)
        assert job.kit_id is not None
        (spool.kit_dir(job.kit_id) / "m16.zip").unlink()
        return job
    if case == "filed during no architect job":
        aux = finished(spool, role="aux")
        return filed_kit(spool, during=aux)
    if case == "a second job carries the kit_id":
        first = filed_kit(spool)
        return spool.create_job(
            role="builder", context="clear", prompt="Apply it.", origin="architect",
            state="held", gate=new_gate(kind="send", reason="apply m16"), kit_id=first.kit_id,
        )
    if case == "not a builder job":
        return filed_kit(spool, role="aux")
    if case == "the record holds no passing check":
        job = filed_kit(spool)
        assert job.kit_id is not None
        record = spool.kit_dir(job.kit_id) / "kit.json"
        record.write_text(record.read_text().replace('"pass"', '"fail"'))
        return job
    raise AssertionError(case)


FORGED = [
    "no kit_id",
    "a kit_id handsd never recorded",
    "a malformed kit_id",
    "not an apply gate",
    "the gate names another kit",
    "the zip is gone",
    "filed during no architect job",
    "a second job carries the kit_id",
    "not a builder job",
    "the record holds no passing check",
]


@pytest.mark.parametrize("case", FORGED)
def test_an_architect_origin_hold_that_is_not_a_filed_kit_is_not_approved(
    tmp_home: Path, workdir: Path, case: str
) -> None:
    """§32: "only when it is an apply hands itself created from a kit filed by the
    architect role (a `kit_id` the daemon minted, checked against the spool), never
    by origin alone". Refused, the hold takes today's path: no shipped playbook has a
    `job.held` rule, so the pipeline stops and the human decides the hold."""
    engine, recorder = engine_for(tmp_home, workdir, AUTONOMOUS, architect=workdir)
    job = _forged(engine.spool, case)
    run(engine.on_event("job.held", job=job))
    assert recorder.approved == [], case
    assert engine.spool.load_job(job.id).state == "held"
    assert engine.state.paused, "the refused hold is a stop, as any hold without a rule is"


def test_the_kit_check_accepts_a_filed_kit_and_names_every_forgery(
    tmp_home: Path, workdir: Path
) -> None:
    from hands.spool import kit_apply_problem

    engine, _recorder = engine_for(tmp_home, workdir, AUTONOMOUS, architect=workdir)
    job = filed_kit(engine.spool)
    assert kit_apply_problem(engine.spool, job) is None
    for case in FORGED:
        assert kit_apply_problem(engine.spool, _forged(engine.spool, case)), case


# ---- §32: the kickoff follows only the engine's own approved kit apply


@pytest.mark.parametrize(
    "case", ["cli send", "architect origin, no kit", "a kit a human approved"]
)
def test_kit_applied_from_anything_but_the_engines_kit_apply_fires_no_kickoff(
    tmp_home: Path, workdir: Path, case: str
) -> None:
    """REVIEW-15 should-fix 1, the reviewer's probe: a plain `hands send` job (origin
    `cli`) replying `VERDICT: kit applied deadbee` fired `rule: -1`. The engine's rule
    is for an apply hands filed from the architect's kit and the engine approved;
    anything else meets the playbook's own rules, here its `notify`."""
    engine, recorder = engine_for(tmp_home, workdir, AUTONOMOUS, architect=workdir)
    verdict = "VERDICT: kit applied deadbee"
    if case == "cli send":
        job = finished(engine.spool, verdict=verdict, origin="cli")
    elif case == "architect origin, no kit":
        job = finished(engine.spool, verdict=verdict, origin="architect")
    else:
        job = applied_kit(engine.spool, verdict=verdict, decided_by="cli")
    run(engine.on_event("builder.done", job=job))
    assert recorder.sent == [], case
    assert [title for title, _ in recorder.notified] == [
        "hands: Kit applied; the next kickoff is the driver's"
    ]
    assert engine.state.last_rule is not None and engine.state.last_rule["rule"] == 0


# ---- §32: `[series] kit_wait_s`


def test_kit_wait_s_defaults_to_600_and_loads(workdir: Path) -> None:
    from hands.playbook import DEFAULT_KIT_WAIT_S, SERIES_KEYS

    assert DEFAULT_KIT_WAIT_S == 600
    assert SERIES_KEYS.count("kit_wait_s") == 1
    assert parse_playbook(AUTONOMOUS, path=workdir / "PLAYBOOK.toml").kit_wait_s == 600
    for value, loaded in (("30", 30), ("0.5", 0.5)):
        book = parse_playbook(series_body(kit_wait_s=value), path=workdir / "PLAYBOOK.toml")
        assert book.kit_wait_s == loaded


@pytest.mark.parametrize("value", ["0", "-1", "true", '"600"', "nan", "inf"])
def test_kit_wait_s_must_be_a_positive_number(workdir: Path, value: str) -> None:
    with pytest.raises(PlaybookError) as caught:
        parse_playbook(series_body(kit_wait_s=value), path=workdir / "PLAYBOOK.toml")
    assert "kit_wait_s must be" in strip_paths(str(caught.value)), caught.value


# ---- the kickoff the engine adds after `VERDICT: kit applied` (§31)


def test_the_engine_sends_the_kickoff_after_kit_applied(tmp_home: Path, workdir: Path) -> None:
    """§31: "a `builder.done` rule the engine adds, not the playbook". It is first,
    so the playbook's own `^VERDICT: kit applied` rule does not fire — §10's own
    "the first rule whose `on` matches … fires"."""
    engine, recorder = engine_for(tmp_home, workdir, AUTONOMOUS, architect=workdir)
    job = applied_kit(engine.spool)
    run(engine.on_event("builder.done", job=job))
    assert recorder.sent == [
        {
            "role": "builder",
            "context": "clear",
            "prompt": (
                "Read meta/BUILDER-16-PROMPT.md and execute the mission below its divider."
            ),
            "origin": "playbook",
            "playbook_sha256": engine.playbook.sha256,
        }
    ]
    assert recorder.notified == [], "the playbook's notify rule did not fire"
    assert engine.state.last_rule is not None
    assert engine.state.last_rule["rule"] == ENGINE_RULE_INDEX == -1
    assert engine.state.last_rule["then"] == "send"


@pytest.mark.parametrize("body", [NOT_AUTONOMOUS, PHONE_MODE])
def test_without_role_mode_and_autonomous_the_playbooks_own_rule_fires(
    tmp_home: Path, workdir: Path, body: str
) -> None:
    engine, recorder = engine_for(tmp_home, workdir, body, architect=workdir)
    job = applied_kit(engine.spool)
    run(engine.on_event("builder.done", job=job))
    assert recorder.sent == []
    assert [title for title, _ in recorder.notified] == [
        "hands: Kit applied; the next kickoff is the driver's"
    ]


def test_the_engine_rule_does_not_swallow_other_builder_verdicts(
    tmp_home: Path, workdir: Path
) -> None:
    engine, recorder = engine_for(tmp_home, workdir, AUTONOMOUS, architect=workdir)
    job = finished(engine.spool, verdict="VERDICT: mission 16 finished")
    run(engine.on_event("builder.done", job=job))
    assert recorder.sent == []
    assert engine.state.paused
    assert "Mission 16 finished" in strip_paths(engine.state.stop_reason or "")


def test_the_engine_rule_stops_when_the_series_has_no_kickoff(
    tmp_home: Path, workdir: Path
) -> None:
    """The rule the engine adds sends `[series] kickoff`; without one there is
    nothing to send, and §10 stops for what it cannot do."""
    body = AUTONOMOUS.replace(
        'kickoff = "Read meta/BUILDER-16-PROMPT.md and execute the mission below its divider."\n',
        "",
    )
    engine, recorder = engine_for(tmp_home, workdir, body, architect=workdir)
    job = applied_kit(engine.spool)
    run(engine.on_event("builder.done", job=job))
    assert recorder.sent == []
    assert engine.state.paused
    assert "kickoff" in strip_paths(engine.state.stop_reason or "")


# ---- end to end (§31, the unit's gate)


#: The reviewer's forged-origin probe (REVIEW-15 blocker 3), verbatim in shape.
FORGED_SEND = {
    "role": "builder",
    "context": "clear",
    "origin": "architect",
    "prompt": "gh pr create --fill, then commit meta/decisions-2026.md",
}


def test_end_to_end_a_socket_client_cannot_send_as_the_architect(
    tmp_home: Path, workdir: Path
) -> None:
    """REVIEW-15 blocker 3, the reviewer's probe over a real daemon under an
    autonomous role-mode playbook: a raw socket client sends `origin: architect`.
    §32: "a socket client cannot set `origin: architect`" — refused at `send`, naming
    §32; no job, no hold, no decision."""
    from hands.cli import call

    git_repo(workdir)
    write_project(tmp_home, config_body(tmp_home, workdir, extra=architect_table(tmp_home)))
    write_playbook(workdir, AUTONOMOUS)
    socket_path = tmp_home / ".hands" / "handsd.sock"

    async def body(daemon: Daemon) -> None:
        with pytest.raises(Exception) as caught:
            await asyncio.to_thread(call, socket_path, "send", FORGED_SEND, project=PROJECT)
        said = strip_paths(str(caught.value))
        assert "§32" in strip_paths(said) and "architect" in strip_paths(said), said
        with pytest.raises(ApiError):
            await daemon.api.send(**FORGED_SEND)
        assert daemon.spool.list_jobs() == []
        assert not [e for e in daemon.spool.events() if e.kind in ("job.held", "gate.decided")]

    drive(body)


def test_end_to_end_a_held_architect_job_injected_without_a_kit_is_not_approved(
    tmp_home: Path, workdir: Path
) -> None:
    """The second half of the probe: a held job of origin `architect` put straight
    into the spool (no `kit_file`, no kit_id) and announced to the engine is not
    approved — it stays held for a human, and the pipeline stops as it does for any
    hold no rule answers. `Api.decide_from_playbook` refuses it too."""
    from hands.gates import new_gate

    git_repo(workdir)
    write_project(tmp_home, config_body(tmp_home, workdir, extra=architect_table(tmp_home)))
    write_playbook(workdir, AUTONOMOUS)

    async def body(daemon: Daemon) -> None:
        job = daemon.spool.create_job(
            role="builder", context="clear", prompt=FORGED_SEND["prompt"], origin="architect",
            state="held", gate=new_gate(kind="send", reason="apply m16"),
        )
        await daemon.playbook.on_event("job.held", job=job)
        with pytest.raises(ApiError) as caught:
            await daemon.api.decide_from_playbook(job.id)
        assert "§32" in strip_paths(str(caught.value))
        record = await ok("result", job.id)
        assert record["state"] == "held"
        assert record["gate"]["decided_by"] is None
        state = await ok("pipeline")
        assert state["paused"] is True
        assert [e for e in (await ok("inbox"))["events"] if e["kind"] == "gate.decided"] == []

    drive(body)


def test_the_architects_readme_shows_keys_that_load(tmp_home: Path, workdir: Path) -> None:
    """`architect/README.md`'s Config block is what the human types. Its `[series]`
    half is lifted out of the file and put through the real loader, so a key that
    stops loading cannot stay in the instructions."""
    readme = (Path(__file__).parents[1] / "architect" / "README.md").read_text(encoding="utf-8")
    lines = [line[4:] for line in readme.splitlines() if line.startswith("    ")]
    start = lines.index("[series]")
    table = []
    for line in lines[start:]:
        if not line.strip():
            break
        table.append(line)
    book = parse_playbook("version = 1\n\n" + "\n".join(table), path=workdir / "PLAYBOOK.toml")
    assert book.architect == "role" and book.autonomous is True
    assert book.gate_failures == 2
    assert book.escalate_on == ESCALATE_ON
    config = make_config(tmp_home, workdir, architect=workdir)
    check_series_roles(book, config)  # the README's `[roles.architect]`, as configured


def test_a_playbook_that_sets_autonomous_arrives_as_a_gated_apply() -> None:
    """§31: "a playbook that sets `autonomous` is itself gated as any kit is".

    It is, by construction and with nothing added here: every kit apply carries a
    gate reason, whichever route filed it, so the job is born `held` and §8's
    table decides it. Pinned rather than built."""
    plan = Apply(name="m16", replaces=["PLAYBOOK.toml"], adds=[],
                 commit_message="plan: kit m16", kit_md=None, prompt="Apply it.")
    for origin in ("kit", "architect"):
        assert apply_params(plan, origin)["gate"] == "apply m16"
    assert DECIDERS["playbook"].available and not DECIDERS["playbook"].requires_quote


# ------------------------------------------ §31: the architect consultation (U5)

#: The reviewer's reply in the shape the review protocol fixes — the verdict line
#: first, then the sections `meta/reviews/REVIEW-14.md` carries. `## Notes` is here
#: so that a test can prove the prompt carries the two sections §31 names and not
#: the whole reply.
REVIEW_VERDICT = "VERDICT: review mission 16 blockers=1 should-fix=1"
REVIEW_BLOCKERS = """## Blockers

1. **The kickoff names a brief the branch lacks (U2 `abc1234`).**
   - Why. `[series] kickoff` reads a file no commit on the branch adds.
"""
REVIEW_SHOULD_FIX = """## Should-fix

1. The journal line does not name the role that was consulted.
"""
REVIEW_NOTES = """## Notes

The reviewer re-ran both probes at the tip; neither is a blocker.
"""
REVIEW = (
    f"{REVIEW_VERDICT}\n\nBase `abc1234`, tip `def5678`.\n\n"
    f"{REVIEW_BLOCKERS}\n{REVIEW_SHOULD_FIX}\n{REVIEW_NOTES}"
)

#: `meta/ROADMAP.md` under the builder's cwd: the consult prompt carries its next
#: unmet milestone (§32), `M5`, and not the milestone marked DONE before it.
ROADMAP_DONE = "- **M4c The architect role** — missions 15 and 16. DONE."
ROADMAP_NEXT = "- **M5 spanweave integration** — the next milestone; gate: two runs merged."
ROADMAP_TEXT = f"""# ROADMAP

{ROADMAP_DONE}
{ROADMAP_NEXT}
"""

ARCHITECT_KICKOFF = "Read meta/BUILDER-17-PROMPT.md and execute the mission below its divider."

#: §31's series: the architect role, autonomous, consulted on the review outcome.
ARCHITECT_BOOK = f"""version = 1

[series]
name = "m17"
kickoff = "{ARCHITECT_KICKOFF}"
architect = "role"
autonomous = true
gate_failures = 2
escalate_on = ["blocker-unanswered", "milestone-missing", "budget-exhausted"]

[limits]
max_architect_consults = 12

[[rule]]
on = "aux.done"
verdict = '^VERDICT: review mission (?P<n>\\d+)'
then = "consult"
role = "architect"

[[rule]]
on = "builder.done"
verdict = '^VERDICT: mission (?P<n>\\d+) finished'
then = "stop"
message = "Mission {{n}} finished"
"""


def architect_dir(tmp_home: Path) -> Path:
    d = tmp_home.parent / "hands-architect"
    d.mkdir(exist_ok=True)
    return d


def architect_engine(
    tmp_home: Path,
    workdir: Path,
    body: str = ARCHITECT_BOOK,
    *,
    roadmap: str | None = ROADMAP_TEXT,
) -> tuple[PlaybookEngine, Recorder]:
    engine = engine_for(tmp_home, workdir, body, architect=architect_dir(tmp_home))
    if roadmap is not None:
        # §32: the roadmap is read as the playbook is, from the committed file.
        commit_file(workdir, str(ROADMAP), roadmap)
    return engine


def reviewed(spool: Spool, result: str = REVIEW) -> Job:
    """The aux job a review outcome is (§10's `aux.done`)."""
    job = spool.create_job(role="aux", context="clear", prompt="Review it", origin="playbook")
    spool.transition(job, "running")
    return spool.transition(
        job, "done", verdict=result.splitlines()[0], result=result
    )


def _architect_job(
    spool: Spool,
    *,
    state: str = "done",
    verdict: str | None,
    about: Job,
    session_id: str | None = "sess-arch-1",
) -> Job:
    job = spool.create_job(
        role=ARCHITECT,
        context="clear",
        prompt=f"hands consult: aux.done on job {about.id} (role aux)\n",
        origin="playbook",
    )
    spool.transition(job, "running", session_id=session_id)
    return spool.transition(job, state, verdict=verdict, result=verdict)


# ---- the rule: `consult` with `role = "architect"` (§27, §31)


def test_a_consult_may_name_the_architect_on_a_review_outcome(workdir: Path) -> None:
    book = parse_playbook(ARCHITECT_BOOK, path=workdir / "PLAYBOOK.toml")
    [rule] = [rule for rule in book.rules if rule.then == "consult"]
    assert rule.role == ARCHITECT
    assert rule.on == "aux.done"
    assert rule.context == "clear"  # §27: a consultation is a fresh session
    assert CONSULT_ROLES == ("driver", ARCHITECT)
    # Each role's events are explicit, and the driver's are exactly today's.
    assert CONSULT_EVENTS[ARCHITECT] == ("aux.done",)
    assert CONSULT_EVENTS["driver"] == tuple(
        event for event in EVENTS if not event.startswith("driver.")
    )


@pytest.mark.parametrize(
    ("body", "because"),
    [
        (
            'version = 1\n[series]\narchitect = "role"\n[[rule]]\non = "builder.done"\n'
            'then = "consult"\nrole = "architect"',
            "aux.done",
        ),
        (
            'version = 1\n[[rule]]\non = "aux.done"\nthen = "consult"\nrole = "architect"',
            '[series] architect is "phone"',
        ),
        (
            'version = 1\n[[rule]]\non = "architect.done"\nthen = "stop"',
            "on must be one of",
        ),
    ],
    ids=["architect on a builder verdict", "architect rule in phone mode", "an architect event"],
)
def test_the_architect_consult_is_refused_at_load_not_when_it_fires(
    workdir: Path, body: str, because: str
) -> None:
    """§10's discipline: refused when the playbook is loaded. The mode and the rule
    are both in the playbook file, so the earliest place that sees both is the load."""
    with pytest.raises(PlaybookError) as caught:
        parse_playbook(body, path=workdir / "PLAYBOOK.toml")
    assert because in strip_paths(str(caught.value)), caught.value


def test_the_architect_events_are_not_playbook_events(tmp_home: Path, workdir: Path) -> None:
    """§31 puts the follow-up in the engine, so no rule fires on an architect end:
    `EVENTS` stays the closed list it is today, without the architect's states."""
    ends = {f"{ARCHITECT}.{state}" for state in ("done", "failed", "killed", "orphaned")}
    assert set(EVENTS).isdisjoint(ends | {f"{ARCHITECT}.limited"})
    assert CONSULT_EVENTS[ARCHITECT] == ("aux.done",)


# ---- the prompt (§31: the event, the review's sections, the roadmap, the instruction)


def test_the_architect_prompt_carries_the_event_the_review_the_roadmap_and_the_instruction(
    tmp_home: Path, workdir: Path
) -> None:
    engine, recorder = architect_engine(tmp_home, workdir)
    review = reviewed(engine.spool)

    run(engine.on_job(review))

    assert not engine.state.paused, engine.state.stop_reason
    assert recorder.sent == []
    [call] = recorder.enqueued
    assert call["role"] == ARCHITECT
    assert call["context"] == "clear"
    assert call["origin"] == "playbook"
    assert call["playbook_sha256"] == engine.playbook.sha256  # type: ignore[union-attr]
    prompt = call["prompt"]
    # the event
    assert prompt.startswith(f"hands consult: aux.done on job {review.id} (role aux)\n")
    # the review's verdict line and its two sections, verbatim
    assert REVIEW_VERDICT in strip_paths(prompt)
    assert REVIEW_BLOCKERS in strip_paths(prompt)
    assert REVIEW_SHOULD_FIX in strip_paths(prompt)
    assert REVIEW_NOTES not in strip_paths(prompt), "§31 names two sections, not the reply"
    # §32: the roadmap's next unmet milestone, not the whole file, and the file's path
    assert ROADMAP_NEXT in strip_paths(prompt)
    assert ROADMAP_DONE not in strip_paths(prompt)
    assert str(ROADMAP) in strip_paths(prompt)
    # the instruction and the vocabulary, verbatim
    assert ARCHITECT_INSTRUCTION in strip_paths(prompt)
    assert ARCHITECT_INSTRUCTION == (
        "write the next kit from ROADMAP and the review, file it, or escalate"
    )
    assert ARCHITECT_VERDICTS == (
        "VERDICT: next kit <name>",
        "VERDICT: series complete",
        "VERDICT: escalate <reason>",
    )
    for line in ARCHITECT_VERDICTS:
        assert line in strip_paths(prompt)
    # the conditions the architect judges, and the budget handsd tells it about
    assert "gate_failures = 2" in strip_paths(prompt)
    for condition in ESCALATE_ON:
        assert condition in strip_paths(prompt)
    assert "consultation 1 of 12" in strip_paths(prompt)
    [sent] = [event for event in engine.spool.events() if event.kind == "consult.sent"]
    assert sent.payload["consulted"] == ARCHITECT
    assert sent.payload["about"] == review.id
    assert sent.payload["event"] == "aux.done"
    assert sent.payload["consults"] == 1
    assert sent.payload["max_consults"] == 12


def test_a_review_whose_headings_are_missing_is_carried_whole(
    tmp_home: Path, workdir: Path
) -> None:
    """Fail soft: a reply hands cannot find the headings in is carried entire,
    never silently emptied, and the prompt says which heading was not found."""
    engine, recorder = architect_engine(tmp_home, workdir)
    reply = f"{REVIEW_VERDICT}\n\n## Findings\n\nOne finding, in a heading of its own.\n"
    run(engine.on_job(reviewed(engine.spool, reply)))
    prompt = recorder.enqueued[0]["prompt"]
    assert reply in strip_paths(prompt)
    assert "Blockers" in strip_paths(prompt)  # the headings it looked for, named
    assert "Should-fix" in strip_paths(prompt)


def test_a_roadmap_hands_cannot_read_is_said_and_does_not_stop_the_consultation(
    tmp_home: Path, workdir: Path
) -> None:
    engine, recorder = architect_engine(tmp_home, workdir, roadmap=None)
    run(engine.on_job(reviewed(engine.spool)))
    assert not engine.state.paused, engine.state.stop_reason
    prompt = recorder.enqueued[0]["prompt"]
    assert str(ROADMAP) in strip_paths(prompt)
    assert "could not be read" in strip_paths(prompt)


# ---- §32 (review 15 should-fix 4): the roadmap's next unmet milestone, not the file

#: A roadmap in the shape `meta/ROADMAP.md` has: a preamble, then one top-level
#: `- **M… Title** — …` item per milestone, wrapped onto indented lines.
ROADMAP_WRAPPED = """# ROADMAP

Milestones are gated by a clean cold review. A DONE here is not a milestone.

- **M1 Core** — DONE 2026-09-11 (mission 1). Dispatch, gates,
  playbook, limits.
- **M2 Shakeout** — mission 2. A run chained into a cold review;
  mission 2a DONE, and its gate is not marked on the first line.
  Gate: ntfy proven.
- **M3 Hardening** — DONE 2026-09-12: reviews find claims.
- **M4 Detectors** — mission 8. Gate: clean review.

## Notes

- **M5 After a heading** — still a milestone line, and not DONE either.
"""


def test_the_next_milestone_is_the_first_whose_first_line_is_not_marked_done() -> None:
    """§32: "the first whose gate is not marked DONE". A milestone is a top-level
    list item beginning `- **M`, running over its indented continuation lines; it
    is marked DONE when the word `DONE` is on its first line. M2's continuation says
    DONE of a sub-mission, which is not its mark."""
    found = next_milestone(ROADMAP_WRAPPED)
    assert found.milestone == (
        "- **M2 Shakeout** — mission 2. A run chained into a cold review;\n"
        "  mission 2a DONE, and its gate is not marked on the first line.\n"
        "  Gate: ntfy proven."
    )
    assert found.count == 5


def test_the_architect_prompt_carries_only_the_next_unmet_milestone(
    tmp_home: Path, workdir: Path
) -> None:
    engine, recorder = architect_engine(tmp_home, workdir, roadmap=ROADMAP_WRAPPED)
    run(engine.on_job(reviewed(engine.spool)))
    prompt = strip_paths(recorder.enqueued[0]["prompt"])
    assert "- **M2 Shakeout** — mission 2." in strip_paths(prompt)
    assert "  Gate: ntfy proven." in strip_paths(prompt)
    for other in ("**M1 Core**", "**M3 Hardening**", "**M4 Detectors**", "Milestones are gated"):
        assert other not in strip_paths(prompt), other
    assert f"first milestone in {ROADMAP} whose first line is not marked DONE" in prompt


def test_a_roadmap_whose_milestones_are_all_done_says_so(tmp_home: Path, workdir: Path) -> None:
    roadmap = "# ROADMAP\n\n- **M1 Core** — DONE.\n- **M2 Shakeout** — DONE 2026-09-11.\n"
    engine, recorder = architect_engine(tmp_home, workdir, roadmap=roadmap)
    run(engine.on_job(reviewed(engine.spool)))
    assert not engine.state.paused, engine.state.stop_reason
    prompt = strip_paths(recorder.enqueued[0]["prompt"])
    assert f"every milestone in {ROADMAP} (2) is marked DONE" in prompt
    assert "**M1 Core**" not in strip_paths(prompt)


def test_a_roadmap_with_no_milestone_hands_can_read_says_so(
    tmp_home: Path, workdir: Path
) -> None:
    roadmap = "# ROADMAP\n\n1. Core — DONE.\n2. Shakeout.\n"
    engine, recorder = architect_engine(tmp_home, workdir, roadmap=roadmap)
    run(engine.on_job(reviewed(engine.spool)))
    assert not engine.state.paused, engine.state.stop_reason
    prompt = strip_paths(recorder.enqueued[0]["prompt"])
    assert f"no milestone in {ROADMAP}" in prompt
    assert "- **M" in strip_paths(prompt)  # the shape it looked for, named
    assert "Shakeout" not in strip_paths(prompt)


def test_the_roadmap_is_the_committed_file_not_the_working_tree(
    tmp_home: Path, workdir: Path
) -> None:
    """§32 (review 15 should-fix 4): the playbook loads only the committed file, and
    the roadmap is read the same way — the working tree's edit is not what the
    branch carries, so it is not what the architect is told."""
    engine, recorder = architect_engine(tmp_home, workdir)
    (workdir / ROADMAP).write_text("# ROADMAP\n\n- **M9 Uncommitted** — next.\n")
    run(engine.on_job(reviewed(engine.spool)))
    prompt = strip_paths(recorder.enqueued[0]["prompt"])
    assert ROADMAP_NEXT in strip_paths(prompt)
    assert "M9 Uncommitted" not in strip_paths(prompt)


def test_an_untracked_roadmap_is_one_hands_cannot_read(tmp_home: Path, workdir: Path) -> None:
    engine, recorder = architect_engine(tmp_home, workdir, roadmap=None)
    (workdir / ROADMAP).parent.mkdir(parents=True, exist_ok=True)
    (workdir / ROADMAP).write_text(ROADMAP_TEXT, encoding="utf-8")
    run(engine.on_job(reviewed(engine.spool)))
    assert not engine.state.paused, engine.state.stop_reason
    prompt = strip_paths(recorder.enqueued[0]["prompt"])
    assert "could not be read" in strip_paths(prompt)
    assert ROADMAP_NEXT not in strip_paths(prompt)


def test_a_consult_with_no_architect_role_configured_stops_and_starts_nothing(
    tmp_home: Path, workdir: Path
) -> None:
    engine, recorder = engine_for(tmp_home, workdir, ARCHITECT_BOOK)
    run(engine.on_job(reviewed(engine.spool)))
    assert recorder.enqueued == []
    assert engine.state.paused
    assert "[roles.architect]" in strip_paths(engine.state.stop_reason or "")


# ---- the verdicts and the follow-ups, which are the engine's (§31)


class Sleeps:
    """The engine's `sleep` seam (§32's `kit_wait_s`), so no test waits one out: it
    records each delay and runs `during` (the world changing while the engine
    waits) before it returns."""

    def __init__(self, during: Callable[[], Any] | None = None) -> None:
        self.delays: list[float] = []
        self.during = during

    async def __call__(self, delay: float) -> None:
        self.delays.append(delay)
        if self.during is not None:
            outcome = self.during()
            if asyncio.iscoroutine(outcome):
                await outcome


def end_consultation(engine: PlaybookEngine, job: Job) -> None:
    """The architect's end, and whatever wait it starts, decided to the last task."""

    async def go() -> None:
        await engine.on_job(job)
        await engine.drain()

    run(go())


def test_next_kit_waits_for_the_apply_the_architect_filed(
    tmp_home: Path, workdir: Path
) -> None:
    """§31: "`next kit` waits for the apply the architect filed" — §32: the specific
    apply, by its `kit_id`, filed during that consultation under the name the verdict
    gives. Filed before the end, there is nothing to wait for and nothing to stop."""
    engine, recorder = architect_engine(tmp_home, workdir)
    engine.sleep = sleeps = Sleeps()
    architect = consultation(engine.spool)
    filed_kit(engine.spool, name="mission-17-kit", during=architect)
    architect = engine.spool.transition(
        architect, "done", verdict="VERDICT: next kit mission-17-kit",
        result="VERDICT: next kit mission-17-kit",
    )

    end_consultation(engine, architect)
    assert not engine.state.paused, engine.state.stop_reason
    assert sleeps.delays == [], "the kit was filed: nothing to wait for"
    assert recorder.enqueued == [] and recorder.sent == []
    assert [title for title, _ in recorder.notified] == []


@pytest.mark.parametrize(
    "case",
    [
        "nothing filed",
        "an earlier kit",
        "a done aux job of origin architect",
        "an architect-origin hold with no kit_id",
    ],
)
def test_next_kit_stops_when_its_kit_is_not_filed_within_kit_wait_s(
    tmp_home: Path, workdir: Path, case: str
) -> None:
    """REVIEW-15 should-fix 2, the reviewer's probes among them: a done `aux` job of
    origin `architect` and a denied apply named `bar` satisfied `next kit foo`. §32:
    nothing but the kit filed during the consultation under the verdict's name does,
    and when none is filed within `[series] kit_wait_s` (default 600) the pipeline
    stops, naming the key. (A kit of another name filed during the consultation, or a
    denied one, is §33's: it escalates at once — see the test after this one.)"""
    engine, recorder = architect_engine(tmp_home, workdir)
    engine.sleep = sleeps = Sleeps()
    spool = engine.spool
    if case == "an earlier kit":
        filed_kit(spool, name="foo")  # during another consultation
    architect = consultation(spool)
    if case == "a done aux job of origin architect":
        finished(spool, role="aux", origin="architect", verdict="VERDICT: x")
    elif case == "an architect-origin hold with no kit_id":
        held_apply(spool, name="foo")
    architect = spool.transition(
        architect, "done", verdict="VERDICT: next kit foo", result="VERDICT: next kit foo"
    )

    end_consultation(engine, architect)
    assert sleeps.delays == [600], case
    assert engine.state.paused, case
    said = strip_paths(engine.state.stop_reason or "")
    for word in ("kit_wait_s", "600", "next kit foo", architect.id):
        assert word in strip_paths(said), (word, said)
    assert [title for title, _ in recorder.notified] == ["hands: the pipeline stopped"]


def test_a_kit_filed_while_the_engine_waits_satisfies_next_kit(
    tmp_home: Path, workdir: Path
) -> None:
    """§32: the architect's job may end before its apply is filed. The engine waits
    `kit_wait_s` (here the playbook's 30) and names the consultation and the kit it
    waits for (`kit_wait`, what `Api.kit_file` asks); a kit filed in that time is
    the one, and nothing stops."""
    body = ARCHITECT_BOOK.replace('architect = "role"', 'architect = "role"\nkit_wait_s = 30')
    engine, recorder = architect_engine(tmp_home, workdir, body)
    architect = consultation(engine.spool, state="done", verdict="VERDICT: next kit m18")
    seen: list[Any] = []

    def during() -> None:
        seen.append(engine.kit_wait())
        filed_kit(engine.spool, name="m18", during=architect)

    engine.sleep = sleeps = Sleeps(during)
    end_consultation(engine, architect)
    assert sleeps.delays == [30]
    assert seen == [(architect.id, "m18")]
    assert not engine.state.paused, engine.state.stop_reason
    assert engine.kit_wait() is None, "the wait ended"


def test_a_filed_kit_ends_the_wait_it_answers(tmp_home: Path, workdir: Path) -> None:
    """`kit_filed` is how `Api.kit_file` tells the engine: the wait is dropped, so a
    second kit for the same `next kit` is not accepted and no timer outlives it."""
    engine, _recorder = architect_engine(tmp_home, workdir)
    architect = consultation(engine.spool, state="done", verdict="VERDICT: next kit m18")
    gate = asyncio.Event()

    async def blocked(delay: float) -> None:
        await gate.wait()

    engine.sleep = blocked

    async def go() -> None:
        await engine.on_job(architect)
        await asyncio.sleep(0)
        assert engine.kit_wait() == (architect.id, "m18")
        filed_kit(engine.spool, name="m18", during=architect)
        engine.kit_filed(architect.id)
        assert engine.kit_wait() is None
        await engine.drain()

    run(go())
    assert not engine.state.paused, engine.state.stop_reason


# ---- §33: one kit per consultation, named as the verdict names it


def test_a_kit_filed_while_its_consultation_runs_is_approved_only_once_its_verdict_names_it(
    tmp_home: Path, workdir: Path
) -> None:
    """§33: "a consultation may file at most one kit, and its name must equal the name
    the architect's `VERDICT: next kit <name>` states". The kit is filed while the
    architect's job runs, before that verdict exists, so the engine does not decide its
    hold then (no approval, no stop): it decides it when the consultation ends and both
    are known."""
    engine, recorder = architect_engine(tmp_home, workdir)
    engine.sleep = sleeps = Sleeps()
    architect = consultation(engine.spool)
    job = filed_kit(engine.spool, name="m18", during=architect)
    run(engine.on_event("job.held", job=job))
    assert recorder.approved == [] and recorder.denied == []
    assert not engine.state.paused, engine.state.stop_reason

    architect = engine.spool.transition(
        architect, "done", verdict="VERDICT: next kit m18", result="VERDICT: next kit m18"
    )
    end_consultation(engine, architect)
    assert [call["job"] for call in recorder.approved] == [job.id]
    assert recorder.approved[0]["reason"] == AUTONOMOUS_APPROVAL
    assert recorder.denied == []
    assert sleeps.delays == [], "the kit was filed: nothing to wait for"
    assert not engine.state.paused, engine.state.stop_reason


def _kits_escalated(engine: PlaybookEngine, recorder: Recorder, architect: Job) -> str:
    """§33's escalate: stopped and notified with the reason, the architect's session id
    and the `claude --resume` line (§31's escalate path); nothing approved."""
    assert recorder.approved == []
    assert engine.state.paused
    said = strip_paths(engine.state.stop_reason or "")
    assert "escalate" in strip_paths(said) and "§33" in strip_paths(said), said
    assert "claude --resume sess-arch-1" in strip_paths(said), said
    assert architect.id in said, said
    assert [title for title, _ in recorder.notified] == ["hands: the pipeline stopped"]
    return said


@pytest.mark.parametrize("filed", ["both while it ran", "the second after the first's approval"])
def test_a_second_kit_in_one_consultation_is_denied_and_the_consultation_escalates(
    tmp_home: Path, workdir: Path, filed: str
) -> None:
    """REVIEW-16 should-fix 1: `foo` and `bar` filed during one consultation were both
    approved although the verdict was `next kit foo`. §33: at most one kit. Filed while
    the job ran, neither is decided before the verdict, and then both are denied — a
    consultation that broke the rule releases nothing. A second kit that arrives after
    the first was approved (a race `Api.kit_file` does not rule out) is denied when it
    is held. Either way the consultation ends `escalate`."""
    engine, recorder = architect_engine(tmp_home, workdir)
    engine.sleep = Sleeps()
    spool = engine.spool
    if filed == "both while it ran":
        architect = consultation(spool)
        foo = filed_kit(spool, name="foo", during=architect)
        bar = filed_kit(spool, name="bar", during=architect)
        for job in (foo, bar):
            run(engine.on_event("job.held", job=job))
        assert recorder.approved == [] and recorder.denied == []
        architect = spool.transition(
            architect, "done", verdict="VERDICT: next kit foo", result="VERDICT: next kit foo"
        )
        end_consultation(engine, architect)
        assert sorted(call["job"] for call in recorder.denied) == sorted([foo.id, bar.id])
    else:
        architect = consultation(spool, state="done", verdict="VERDICT: next kit foo")
        foo = filed_kit(spool, name="foo", during=architect)
        run(engine.on_event("job.held", job=foo))
        assert [call["job"] for call in recorder.approved] == [foo.id]
        from hands.gates import decide

        assert foo.gate is not None
        spool.transition(foo, "queued", gate=decide(foo.gate, decision="approved",
                                                    decided_by="playbook", reason="r"))
        recorder.approved.clear()
        bar = filed_kit(spool, name="foo", during=architect)
        run(engine.on_event("job.held", job=bar))
        assert [call["job"] for call in recorder.denied] == [bar.id]
    said = _kits_escalated(engine, recorder, architect)
    assert "at most one" in strip_paths(said), said
    for call in recorder.denied:
        assert "§33" in strip_paths(call["reason"] or ""), call


@pytest.mark.parametrize(
    "case", ["a kit of another name", "a denied apply of another name", "no next kit verdict"]
)
def test_a_kit_the_verdict_does_not_name_is_denied_and_the_consultation_escalates(
    tmp_home: Path, workdir: Path, case: str
) -> None:
    """§33: the kit's name "must equal the name the architect's `VERDICT: next kit
    <name>` states, else the apply is denied by the engine and the consultation ends
    `escalate`" — at once, without waiting `kit_wait_s` for a kit a filed one already
    contradicts. A reply that states no `next kit` names no kit at all."""
    engine, recorder = architect_engine(tmp_home, workdir)
    engine.sleep = sleeps = Sleeps()
    spool = engine.spool
    architect = consultation(spool)
    bar = filed_kit(spool, name="bar", during=architect)
    run(engine.on_event("job.held", job=bar))
    if case == "a denied apply of another name":
        spool.transition(bar, "denied")
    verdict = "VERDICT: series complete" if case == "no next kit verdict" else (
        "VERDICT: next kit foo"
    )
    architect = spool.transition(architect, "done", verdict=verdict, result=verdict)
    end_consultation(engine, architect)
    assert sleeps.delays == [], "a contradicted verdict waits for nothing"
    expected = [] if case == "a denied apply of another name" else [bar.id]
    assert [call["job"] for call in recorder.denied] == expected
    said = _kits_escalated(engine, recorder, architect)
    assert "'bar'" in strip_paths(said), said


def test_outside_autonomy_the_engine_denies_nothing_and_the_hold_is_the_humans(
    tmp_home: Path, workdir: Path
) -> None:
    """The engine decides an architect's hold only where it approves one — role mode
    with `autonomous` (§31, §32). Elsewhere a kit of another name is left held for the
    human, as every hold is there, and the consultation's end is what it was."""
    body = ARCHITECT_BOOK.replace("autonomous = true", "autonomous = false")
    engine, recorder = architect_engine(tmp_home, workdir, body)
    engine.sleep = Sleeps()
    architect = consultation(engine.spool)
    filed_kit(engine.spool, name="bar", during=architect)
    architect = engine.spool.transition(
        architect, "done", verdict="VERDICT: next kit foo", result="VERDICT: next kit foo"
    )
    end_consultation(engine, architect)
    assert recorder.approved == [] and recorder.denied == []
    assert "kit_wait_s" in strip_paths(engine.state.stop_reason or "")


def test_series_complete_stops_with_that_reason(tmp_home: Path, workdir: Path) -> None:
    engine, recorder = architect_engine(tmp_home, workdir)
    review = reviewed(engine.spool)
    architect = _architect_job(engine.spool, verdict="VERDICT: series complete", about=review)
    run(engine.on_job(architect))
    assert engine.state.paused
    said = engine.state.stop_reason or ""
    assert "series complete" in strip_paths(said), said
    assert [title for title, _ in recorder.notified] == ["hands: the pipeline stopped"]


def test_escalate_stops_and_notifies_with_the_reason_the_session_and_the_resume_line(
    tmp_home: Path, workdir: Path
) -> None:
    """§31, and `architect/README.md`'s "When it escalates": the notification names
    the condition, the architect's session id and the `claude --resume` line."""
    engine, recorder = architect_engine(tmp_home, workdir)
    review = reviewed(engine.spool)
    reason = "milestone-missing: the roadmap has no milestone after M5"
    architect = _architect_job(
        engine.spool, verdict=f"VERDICT: escalate {reason}", about=review, session_id="sess-9"
    )
    run(engine.on_job(architect))
    assert engine.state.paused
    [(title, payload)] = recorder.notified
    assert title == "hands: the pipeline stopped"
    said = payload["reason"]
    assert reason in strip_paths(said), said
    assert "sess-9" in strip_paths(said), said
    assert "claude --resume sess-9" in strip_paths(said), said


def test_an_escalation_with_no_session_id_says_so(tmp_home: Path, workdir: Path) -> None:
    engine, recorder = architect_engine(tmp_home, workdir)
    review = reviewed(engine.spool)
    architect = _architect_job(
        engine.spool, verdict="VERDICT: escalate budget-exhausted", about=review, session_id=None
    )
    run(engine.on_job(architect))
    said = engine.state.stop_reason or ""
    assert "no session id" in strip_paths(said), said
    assert "no `claude --resume` line" in strip_paths(said), said


@pytest.mark.parametrize(
    ("state", "verdict", "because"),
    [
        ("done", "VERDICT: maybe next kit", "is none of"),
        ("done", None, "has no VERDICT: line"),
        ("failed", None, "ended failed"),
        ("killed", None, "ended killed"),
        ("orphaned", None, "ended orphaned"),
        ("limited", None, "ended limited"),
    ],
)
def test_every_other_architect_end_stops_and_notifies(
    tmp_home: Path, workdir: Path, state: str, verdict: str | None, because: str
) -> None:
    engine, recorder = architect_engine(tmp_home, workdir)
    review = reviewed(engine.spool)
    architect = _architect_job(engine.spool, state=state, verdict=verdict, about=review)
    run(engine.on_job(architect))
    assert engine.state.paused
    assert because in strip_paths(engine.state.stop_reason or "")
    assert [title for title, _ in recorder.notified] == ["hands: the pipeline stopped"]


def test_an_architect_consultation_files_consult_done_and_one_journal_line(
    tmp_home: Path, workdir: Path
) -> None:
    """§27: "every consultation is an inbox event and a `meta/journal.md` line" —
    the architect's as much as the driver's."""
    engine, _recorder = architect_engine(tmp_home, workdir)
    review = reviewed(engine.spool)
    architect = _architect_job(engine.spool, verdict="VERDICT: series complete", about=review)
    run(engine.on_job(architect))
    [done] = [event for event in engine.spool.events() if event.kind == "consult.done"]
    assert done.payload["job"] == architect.id
    assert done.payload["about"] == review.id
    assert done.payload["consulted"] == ARCHITECT
    assert done.payload["state"] == "done"
    assert done.payload["verdict"] == "VERDICT: series complete"
    lines = (workdir / "meta" / "journal.md").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert architect.id in strip_paths(lines[0])
    assert review.id in strip_paths(lines[0])
    assert ARCHITECT in strip_paths(lines[0])


# ---- `[limits] max_architect_consults`, per series, and `budget-exhausted` (§31)


def test_the_budget_is_the_engines_own_stop(tmp_home: Path, workdir: Path) -> None:
    """§31: "the engine stops on the budget one itself". `escalate_on`'s other two
    conditions are the architect's judgement, stated in its escalate reason."""
    body = ARCHITECT_BOOK.replace("max_architect_consults = 12", "max_architect_consults = 1")
    engine, recorder = architect_engine(tmp_home, workdir, body)
    first = reviewed(engine.spool)
    run(engine.on_job(first))
    assert len(recorder.enqueued) == 1
    _architect_job(engine.spool, verdict="VERDICT: series complete", about=first)
    engine.state.paused = False  # the `series complete` stop is not what is tested here
    engine.state.stop_reason = None

    run(engine.on_job(reviewed(engine.spool)))

    assert len(recorder.enqueued) == 1, "a consult beyond the budget started an architect job"
    assert engine.state.paused
    said = engine.state.stop_reason or ""
    assert "max_architect_consults is 1" in strip_paths(said), said
    assert "budget-exhausted" in strip_paths(said), said


def test_the_architect_budget_is_counted_per_series_not_per_mission(
    tmp_home: Path, workdir: Path
) -> None:
    """The series is `[series] name`: a kickoff does not restart the count (that is
    `max_consults`, per mission), and a playbook that names another series does."""
    engine, recorder = architect_engine(tmp_home, workdir)
    spool = engine.spool
    review = reviewed(spool)
    run(engine.on_job(review))  # loads the playbook, which anchors the series
    for _ in range(2):
        _architect_job(spool, verdict="VERDICT: series complete", about=review)
    kickoff = spool.create_job(
        role="builder", context="clear", prompt=ARCHITECT_KICKOFF, origin="phone"
    )
    spool.transition(kickoff, "running")
    spool.transition(kickoff, "done")
    assert engine.pipeline()["architect_consults"] == {
        "used": 2,
        "max_architect_consults": 12,
    }

    commit_file(workdir, "PLAYBOOK.toml", ARCHITECT_BOOK.replace('name = "m17"', 'name = "m18"'))
    engine._loaded = False
    run(engine.on_job(reviewed(spool)))
    assert engine.pipeline()["architect_consults"]["used"] == 0
    assert engine.state.series_since is not None
    assert engine.state.series_since.series == "m18"


def test_the_pipeline_shows_the_architects_budget_only_in_role_mode(
    tmp_home: Path, workdir: Path
) -> None:
    """The human's view of the series budget until `hands doctor` gets its row: a
    line for a series whose architect is the role, and nothing for one that is not."""
    engine, _recorder = architect_engine(tmp_home, workdir)
    review = reviewed(engine.spool)
    run(engine.on_job(review))  # loads the playbook, which anchors the series
    _architect_job(engine.spool, verdict="VERDICT: series complete", about=review)
    assert "architect 1 of max_architect_consults 12" in strip_paths(
        _pipeline_block(engine.pipeline())
    )
    phone, _r = engine_for(tmp_home, workdir, PHONE_MODE)
    assert "max_architect_consults" not in strip_paths(_pipeline_block(phone.pipeline()))


def test_the_series_anchor_is_persisted_and_read_back(tmp_home: Path, workdir: Path) -> None:
    engine, _recorder = architect_engine(tmp_home, workdir)
    run(engine.on_job(reviewed(engine.spool)))
    anchor = engine.state.series_since
    assert anchor is not None and anchor.series == "m17" and anchor.at
    data = json.loads((engine.spool.root / "pipeline.json").read_text(encoding="utf-8"))
    assert data["series_since"]["series"] == "m17"
    reread = PipelineState.from_dict(data).series_since
    assert reread == anchor


# ---- §32: the budget anchors to `[series] name`; a rename restates the budget

#: ARCHITECT_BOOK without `[limits] max_architect_consults`: the key is not restated.
UNSTATED = ARCHITECT_BOOK.replace("[limits]\nmax_architect_consults = 12\n", "")


def test_a_series_rename_that_does_not_restate_the_budget_is_refused(
    tmp_home: Path, workdir: Path
) -> None:
    """REVIEW-15 should-fix 3, the reviewer's probe m17 → m18 → m17: the rename to m18
    does not restate `max_architect_consults`, so the engine refuses the playbook
    (a stop naming the key), the anchor stays m17, and m17 again counts on from 2."""
    assert UNSTATED != ARCHITECT_BOOK and UNSTATED.count("max_architect_consults") == 0
    engine, recorder = architect_engine(tmp_home, workdir)
    spool = engine.spool
    review = reviewed(spool)
    run(engine.on_job(review))  # loads m17, which anchors the series
    for _ in range(2):
        _architect_job(spool, verdict="VERDICT: series complete", about=review)
    assert engine.architect_consults_used() == 2
    consulted = len(recorder.enqueued)

    commit_file(workdir, "PLAYBOOK.toml", UNSTATED.replace('name = "m17"', 'name = "m18"'))
    engine._loaded = False
    run(engine.on_job(reviewed(spool)))
    assert engine.state.paused
    said = engine.state.stop_reason or ""
    for word in ("m17", "m18", "max_architect_consults", "§32"):
        assert word in strip_paths(said), (word, said)
    assert engine.playbook is None
    assert len(recorder.enqueued) == consulted, "a refused playbook consulted nobody"
    assert engine.state.series_since is not None and engine.state.series_since.series == "m17"
    assert engine.architect_consults_used() == 2

    commit_file(workdir, "PLAYBOOK.toml", UNSTATED)  # back to m17: not a rename
    engine._loaded = False
    engine.state.paused = False
    engine.state.stop_reason = None
    run(engine._load())
    assert engine.playbook is not None and engine.playbook.series == "m17"
    assert engine.architect_consults_used() == 2, "m17 → m18 → m17 reset the count"


def test_a_series_rename_that_restates_the_budget_moves_the_anchor(
    tmp_home: Path, workdir: Path
) -> None:
    """"Restated" is the key written in the new playbook's `[limits]` table, whatever
    its value: explicit, where the default would be implicit."""
    engine, _recorder = architect_engine(tmp_home, workdir, UNSTATED)
    run(engine._load())
    _architect_job(engine.spool, verdict="VERDICT: series complete", about=reviewed(engine.spool))
    assert engine.architect_consults_used() == 1
    assert engine.playbook is not None and not engine.playbook.architect_consults_restated
    commit_file(workdir, "PLAYBOOK.toml", ARCHITECT_BOOK.replace('name = "m17"', 'name = "m18"'))
    engine._loaded = False
    run(engine._load())
    assert not engine.state.paused, engine.state.stop_reason
    assert engine.playbook is not None and engine.playbook.architect_consults_restated
    assert engine.state.series_since is not None and engine.state.series_since.series == "m18"
    assert engine.architect_consults_used() == 0


# ---- end to end, one test per verdict (§31, the unit's gate)

#: The e2e playbook: §31's series, with the kickoff line carrying the reply the
#: builder gives it, so only the architect's own reply comes from the scripted queue
#: (`fake_claude` prefers a `FAKE:` directive and leaves the queue where it was).
E2E_BOOK = ARCHITECT_BOOK.replace(
    ARCHITECT_KICKOFF, f"{ARCHITECT_KICKOFF}\\nFAKE:result VERDICT: mission 17 finished"
)

#: What the scripted architect runs in place of `hands kit file <dir>`: the call
#: that command makes once its client-side check passes — the daemon's `kit_file`
#: with the kit's name and the zip's bytes, over the same socket (§32) — made here
#: with no client-side check at all, as any socket client can (REVIEW-16 blocker 1).
#: One call per `name=path` argument, in order; a refusal is written beside the zip
#: as `<name>.refused`. The daemon checks the zip (§33), mints the kit_id, stores
#: it, and files the held apply of origin architect.
FILE_APPLY = """
import base64, sys
from pathlib import Path
from hands.cli import call
for pair in sys.argv[3:]:
    name, _, path = pair.partition("=")
    params = {"name": name, "zip": base64.b64encode(Path(path).read_bytes()).decode()}
    try:
        call(sys.argv[1], "kit_file", params, project=sys.argv[2])
    except Exception as exc:
        Path(path).with_suffix(".refused").write_text(str(exc))
"""


def file_apply_argv(
    tmp_home: Path, kits: dict[str, dict[str, str]] | None = None
) -> list[str]:
    """The scripted architect's `exec`: file each of `kits` (name → entries) over the
    socket, in order; by default one kit, `mission-17-kit`, that passes the check."""
    import sys

    kits = kits if kits is not None else {"mission-17-kit": passing_kit()}
    where = tmp_home / "filed-kits"
    where.mkdir(exist_ok=True)
    pairs = []
    for name, files in kits.items():
        path = where / f"{name}.zip"
        path.write_bytes(kit_zip(files))
        pairs.append(f"{name}={path}")
    return [
        sys.executable,
        "-c",
        FILE_APPLY,
        str(tmp_home / ".hands" / "handsd.sock"),
        PROJECT,
        *pairs,
    ]


def refusals(tmp_home: Path) -> dict[str, str]:
    """The `kit_file` refusals `FILE_APPLY` wrote, by kit name."""
    return {
        path.stem: path.read_text() for path in sorted((tmp_home / "filed-kits").glob("*.refused"))
    }


def fake_result(text: str) -> str:
    """A prompt that makes `fake_claude` reply `text` verbatim, however many lines."""
    return "FAKE:result " + text.replace("\\", "\\\\").replace("\n", "\\n")


class TextPosts:
    """`Posts`, keeping the message body too: §31's escalation is about what it says."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    async def __call__(self, url: str, *, title: str, message: str) -> int:
        self.sent.append((title, message))
        return 200


def architect_project(tmp_home: Path, workdir: Path, *, book: str = E2E_BOOK,
                      ntfy: bool = False) -> Path:
    """§31's project: the architect role configured, its playbook committed, and the
    roadmap the consult prompt reads on the branch."""
    architect = architect_dir(tmp_home)
    body = config_body(tmp_home, workdir, extra=f'\n[roles.architect]\ncwd = "{architect}"\n')
    if ntfy:
        body = body.replace(
            "[server]", '[server]\nntfy_topic = "hands-test"\nntfy_url = "https://ntfy.example"'
        )
    write_project(tmp_home, body)
    write_playbook(workdir, book)
    commit_file(workdir, str(ROADMAP), ROADMAP_TEXT)  # §32: read as committed
    return architect


def script(tmp_home: Path, monkeypatch: pytest.MonkeyPatch, replies: list[Any]) -> None:
    path = tmp_home / "replies.json"
    path.write_text(json.dumps(replies))
    monkeypatch.setenv("HANDS_FAKE_CLAUDE_REPLIES", str(path))


def test_end_to_end_next_kit_waits_for_the_apply_the_architect_filed(
    tmp_home: Path, workdir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """(a) review → consult the architect → it files an apply and replies `VERDICT:
    next kit <name>` → the engine waits: the apply it filed is approved
    (`decided_by: playbook`), applied, and the kickoff follows it."""
    architect_project(tmp_home, workdir)
    script(
        tmp_home,
        monkeypatch,
        [
            {"result": "VERDICT: next kit mission-17-kit", "exec": file_apply_argv(tmp_home)},
            "VERDICT: kit applied abc1234",  # the builder's reply to the apply prompt
        ],
    )

    async def body(daemon: Daemon) -> None:
        review = await ok("send", "--role", "aux", "--context", "clear", fake_result(REVIEW))
        await ok("wait", review["id"])
        state = await wait_for_stop()

        rows = sorted((await ok("jobs", "-n", "50"))["jobs"], key=lambda row: row["id"])
        assert [(row["role"], row["origin"]) for row in rows] == [
            ("aux", "cli"),
            (ARCHITECT, "playbook"),
            ("builder", "architect"),  # the apply `hands kit file` files
            ("builder", "playbook"),  # the kickoff the engine sends after it
        ]
        _reviewer, architect, apply_job, kickoff = [
            await ok("result", row["id"]) for row in rows
        ]
        assert architect["context"] == "clear"
        assert architect["result"] == "VERDICT: next kit mission-17-kit"
        assert REVIEW_VERDICT in strip_paths(architect["prompt"])
        assert REVIEW_BLOCKERS in strip_paths(architect["prompt"])
        assert REVIEW_SHOULD_FIX in strip_paths(architect["prompt"])
        assert ROADMAP_NEXT in strip_paths(architect["prompt"])
        assert ARCHITECT_INSTRUCTION in strip_paths(architect["prompt"])
        # §32: the apply hands filed from the architect's kit — a kit_id handsd
        # minted, its zip and record stored under the spool naming this consultation.
        kit_id = apply_job["kit_id"]
        assert isinstance(kit_id, str) and len(kit_id) == 16, kit_id
        assert daemon.spool.read_kit_record(kit_id) == {
            "kit_id": kit_id, "name": "mission-17-kit", "consultation": architect["id"],
            "check": "pass",  # §33: handsd's own check of the stored bytes
        }
        assert refusals(tmp_home) == {}
        assert (daemon.spool.kit_dir(kit_id) / "mission-17-kit.zip").is_file()
        assert apply_job["created"] > architect["started"]
        gate = apply_job["gate"]
        assert gate["reason"] == "apply mission-17-kit"
        assert gate["decision"] == "approved" and gate["decided_at"]
        assert gate["decided_by"] == "playbook", "§31: the engine is the decider"
        assert gate["decided_reason"] == AUTONOMOUS_APPROVAL
        assert gate["quote"] is None
        assert apply_job["verdict"] == "VERDICT: kit applied abc1234"
        assert kickoff["prompt"].startswith(ARCHITECT_KICKOFF)
        decided = await _events("gate.decided")
        assert [event["payload"]["job"] for event in decided] == [apply_job["id"]]
        fired = [event["payload"] for event in await _events("playbook.rule")
                 if event["payload"].get("rule") == ENGINE_RULE_INDEX]
        assert [payload["fired_job"] for payload in fired] == [kickoff["id"]]
        assert state["stop_reason"] == "Mission 17 finished"  # not the architect's end

        [sent] = await _events("consult.sent")
        [done] = await _events("consult.done")
        assert sent["payload"]["consulted"] == ARCHITECT
        assert sent["payload"]["about"] == rows[0]["id"]
        assert sent["payload"]["consults"] == 1
        assert sent["payload"]["max_consults"] == 12
        assert done["payload"]["job"] == architect["id"]
        assert done["payload"]["verdict"] == "VERDICT: next kit mission-17-kit"
        assert state["architect_consults"] == {"used": 1, "max_architect_consults": 12}
        lines = (workdir / "meta" / "journal.md").read_text(encoding="utf-8").splitlines()
        assert len(lines) == 1
        assert architect["id"] in strip_paths(lines[0])

    drive(body)


def test_end_to_end_next_kit_stops_when_no_kit_is_filed_within_kit_wait_s(
    tmp_home: Path, workdir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§32: the architect replies `next kit` and files nothing. The engine waits
    `[series] kit_wait_s` (the default 600, through its `sleep` seam, so the test does
    not) and stops, naming the key; `kit_file` is refused once the wait is over."""
    architect_project(tmp_home, workdir)
    script(tmp_home, monkeypatch, ["VERDICT: next kit mission-17-kit"])

    async def body(daemon: Daemon) -> None:
        delays: list[float] = []

        async def sleep(delay: float) -> None:
            delays.append(delay)

        daemon.playbook.sleep = sleep
        review = await ok("send", "--role", "aux", "--context", "clear", fake_result(REVIEW))
        await ok("wait", review["id"])
        state = await wait_for_stop()

        assert delays == [600]
        for word in ("kit_wait_s", "next kit mission-17-kit"):
            assert word in strip_paths(state["stop_reason"]), state["stop_reason"]
        rows = (await ok("jobs", "-n", "50"))["jobs"]
        assert sorted(row["role"] for row in rows) == [ARCHITECT, "aux"]
        with pytest.raises(ApiError) as caught:
            await daemon.api.kit_file(name="mission-17-kit", zip="UEsFBgAAAAAAAAAAAAAAAAAAAAAAAA==")
        assert "§32" in strip_paths(str(caught.value))

    drive(body)


def test_end_to_end_a_kit_filed_after_the_architect_ended_is_waited_for(
    tmp_home: Path, workdir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§32: the architect's job may end before its apply is filed. Filed during the
    wait, the kit is the one `next kit` named: approved by the engine, applied, and
    the kickoff follows."""
    architect_project(tmp_home, workdir)
    script(tmp_home, monkeypatch, ["VERDICT: next kit mission-17-kit",
                                   "VERDICT: kit applied abc1234"])

    async def body(daemon: Daemon) -> None:
        import base64

        data = base64.b64encode(kit_zip(passing_kit())).decode()
        filed: list[dict[str, Any]] = []

        async def sleep(delay: float) -> None:
            with pytest.raises(ApiError) as caught:  # not the kit `next kit` named
                await daemon.api.kit_file(name="another-kit", zip=data)
            assert "mission-17-kit" in strip_paths(str(caught.value))
            filed.append(await daemon.api.kit_file(name="mission-17-kit", zip=data))

        daemon.playbook.sleep = sleep
        review = await ok("send", "--role", "aux", "--context", "clear", fake_result(REVIEW))
        await ok("wait", review["id"])
        state = await wait_for_stop()

        assert state["stop_reason"] == "Mission 17 finished", state["stop_reason"]
        [apply_row] = filed
        apply_job = await ok("result", apply_row["id"])
        assert apply_job["gate"]["decided_by"] == "playbook"
        assert apply_job["verdict"] == "VERDICT: kit applied abc1234"
        rows = sorted((await ok("jobs", "-n", "50"))["jobs"], key=lambda row: row["id"])
        assert [(row["role"], row["origin"]) for row in rows] == [
            ("aux", "cli"),
            (ARCHITECT, "playbook"),
            ("builder", "architect"),
            ("builder", "playbook"),
        ]
        record = daemon.spool.read_kit_record(apply_job["kit_id"])
        assert record is not None and record["consultation"] == rows[1]["id"]

    drive(body)


def test_acceptance_a_kit_that_fails_hands_kit_check_is_never_engine_approved(
    tmp_home: Path, workdir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """REVIEW-16 blocker 1 (H-035), the reviewer's probe: a real daemon, fake_claude and
    a role + autonomous playbook. While the architect job runs, a raw socket `kit_file`
    — no client-side check — files `foo` and `bar`, each carrying the guard, its
    settings, DESIGN.md and a playbook and no brief; the architect replies `VERDICT:
    next kit foo`. Then both were `decided_by=playbook`. §33: handsd runs the check on
    the bytes it stores and refuses each with the check's output, so no apply exists
    for the engine to approve: no builder job, no gate decision, and the wait for
    `foo` ends in a stop."""
    from hands.kit import check_kit

    architect_project(tmp_home, workdir)
    probe = file_apply_argv(tmp_home, {"foo": UNCHECKED_KIT, "bar": UNCHECKED_KIT})
    for name in ("foo", "bar"):  # the kits really fail `hands kit check` here
        assert not check_kit(tmp_home / "filed-kits" / f"{name}.zip", workdir).ok
    script(tmp_home, monkeypatch, [{"result": "VERDICT: next kit foo", "exec": probe}])

    async def body(daemon: Daemon) -> None:
        async def sleep(delay: float) -> None:
            return None

        daemon.playbook.sleep = sleep
        review = await ok("send", "--role", "aux", "--context", "clear", fake_result(REVIEW))
        await ok("wait", review["id"])
        state = await wait_for_stop()

        rows = sorted((await ok("jobs", "-n", "50"))["jobs"], key=lambda row: row["id"])
        assert [(row["role"], row["origin"]) for row in rows] == [
            ("aux", "cli"),
            (ARCHITECT, "playbook"),
        ], "a kit that fails the check was filed"
        assert await _events("gate.decided") == []
        assert await _events("job.held") == []
        refused = refusals(tmp_home)
        assert sorted(refused) == ["bar", "foo"], refused
        for said in refused.values():
            assert "hands kit check" in strip_paths(said) and "FAIL brief" in strip_paths(said)
        kits = daemon.spool.root / "kits"
        assert not kits.exists() or list(kits.iterdir()) == [], "a refused kit was kept"
        assert "kit_wait_s" in strip_paths(state["stop_reason"]), state["stop_reason"]

    drive(body)


def _denied_by_the_engine(row: dict[str, Any]) -> None:
    assert row["state"] == "denied", row["state"]
    gate = row["gate"]
    assert gate["decision"] == "denied" and gate["decided_by"] == "playbook", gate
    assert "§33" in strip_paths(gate["decided_reason"]), gate


@pytest.mark.parametrize("case", ["two kits", "a kit of another name"])
def test_end_to_end_a_kit_the_rule_forbids_is_denied_and_the_consultation_escalates(
    tmp_home: Path, workdir: Path, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    """REVIEW-16 should-fix 1, end to end with kits that pass the check: one
    consultation files `foo` and `bar` and replies `VERDICT: next kit foo` (both were
    approved), or files only `bar` under that verdict. §33: denied by the engine
    (`decided_by: playbook`), and the consultation ends `escalate` — the stop and its
    one notification carry the reason, the architect's session id and the `claude
    --resume` line. Nothing is applied and no kickoff follows."""
    architect_project(tmp_home, workdir, ntfy=True)
    kits = {"foo": passing_kit(), "bar": passing_kit()} if case == "two kits" else {
        "bar": passing_kit()
    }
    script(tmp_home, monkeypatch,
           [{"result": "VERDICT: next kit foo", "exec": file_apply_argv(tmp_home, kits)}])
    posts = TextPosts()

    async def scenario() -> None:
        daemon = Daemon(load_config(PROJECT))
        daemon.notifier.post = posts  # before start(): no test may reach a network
        await daemon.start()
        try:
            await asyncio.wait_for(body(daemon), 60)
        finally:
            await daemon.stop()

    async def body(daemon: Daemon) -> None:
        review = await ok("send", "--role", "aux", "--context", "clear", fake_result(REVIEW))
        await ok("wait", review["id"])
        state = await wait_for_stop()
        await daemon.notifier.drain()

        assert refusals(tmp_home) == {}, "the kits pass the check; handsd filed them"
        rows = sorted((await ok("jobs", "-n", "50"))["jobs"], key=lambda row: row["id"])
        assert [(row["role"], row["origin"]) for row in rows] == [
            ("aux", "cli"),
            (ARCHITECT, "playbook"),
            *[("builder", "architect")] * len(kits),
        ], "a kit was applied, or a kickoff followed"
        architect = await ok("result", rows[1]["id"])
        for row in rows[2:]:
            _denied_by_the_engine(await ok("result", row["id"]))
        said = strip_paths(state["stop_reason"])
        assert "escalate" in strip_paths(said) and "§33" in strip_paths(said), said
        assert ("at most one" if case == "two kits" else "'bar'") in said, said
        session = architect["session_id"]
        assert session and f"claude --resume {session}" in said, said
        stops = [message for title, message in posts.sent if title == "hands: the pipeline stopped"]
        assert len(stops) == 1, posts.sent
        assert f"claude --resume {session}" in strip_paths(stops[0])
        assert [e for e in await _events("gate.decided")
                if e["payload"]["decision"] == "approved"] == []

    asyncio.run(scenario())


def test_end_to_end_series_complete_stops_with_that_reason(
    tmp_home: Path, workdir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """(b) review → consult → `VERDICT: series complete` → the pipeline stops, and
    no kit, no kickoff and no further job follow."""
    architect_project(tmp_home, workdir)
    script(tmp_home, monkeypatch, ["VERDICT: series complete"])

    async def body(daemon: Daemon) -> None:
        review = await ok("send", "--role", "aux", "--context", "clear", fake_result(REVIEW))
        await ok("wait", review["id"])
        state = await wait_for_stop()

        assert "series complete" in strip_paths(state["stop_reason"])
        rows = sorted((await ok("jobs", "-n", "50"))["jobs"], key=lambda row: row["id"])
        assert [(row["role"], row["origin"]) for row in rows] == [
            ("aux", "cli"),
            (ARCHITECT, "playbook"),
        ]
        [done] = await _events("consult.done")
        assert done["payload"]["verdict"] == "VERDICT: series complete"
        assert done["payload"]["state"] == "done"
        assert [event["kind"] for event in (await ok("inbox"))["events"]][-1] == "stop"

    drive(body)


def test_end_to_end_escalate_notifies_with_the_reason_the_session_and_the_resume_line(
    tmp_home: Path, workdir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """(c) review → consult → `VERDICT: escalate <reason>` → stop, and the
    notification names the reason, the architect's session id and `claude --resume`."""
    architect_project(tmp_home, workdir, ntfy=True)
    reason = "blocker-unanswered: blocker 2 asks a design question the plan does not answer"
    script(tmp_home, monkeypatch, [f"FAKE:session sess-e2e-9\nVERDICT: escalate {reason}"])
    posts = TextPosts()

    async def scenario() -> None:
        daemon = Daemon(load_config(PROJECT))
        daemon.notifier.post = posts  # before start(): no test may reach a network
        await daemon.start()
        try:
            await asyncio.wait_for(body(daemon), 60)
        finally:
            await daemon.stop()

    async def body(daemon: Daemon) -> None:
        review = await ok("send", "--role", "aux", "--context", "clear", fake_result(REVIEW))
        await ok("wait", review["id"])
        state = await wait_for_stop()
        await daemon.notifier.drain()

        [row] = [r for r in (await ok("jobs", "-n", "50"))["jobs"] if r["role"] == ARCHITECT]
        architect = await ok("result", row["id"])
        session = architect["session_id"]
        assert session
        assert reason in strip_paths(state["stop_reason"])
        stops = [message for title, message in posts.sent if title == "hands: the pipeline stopped"]
        assert len(stops) == 1
        assert reason in strip_paths(stops[0])
        assert session in strip_paths(stops[0])
        assert f"claude --resume {session}" in strip_paths(stops[0])

    asyncio.run(scenario())


def test_end_to_end_the_engine_stops_itself_when_the_series_budget_is_exhausted(
    tmp_home: Path, workdir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """(d) `[limits] max_architect_consults = 1`: the first review is consulted, the
    second is not — §31's `budget-exhausted` is the one condition the engine judges."""
    book = E2E_BOOK.replace("max_architect_consults = 12", "max_architect_consults = 1")
    architect_project(tmp_home, workdir, book=book)
    script(tmp_home, monkeypatch, ["VERDICT: series complete", "VERDICT: series complete"])

    async def body(daemon: Daemon) -> None:
        first = await ok("send", "--role", "aux", "--context", "clear", fake_result(REVIEW))
        await ok("wait", first["id"])
        await wait_for_stop()
        await _wait_events("consult.done", 1)
        assert (await ok("resume"))["paused"] is False

        second = await ok("send", "--role", "aux", "--context", "clear", fake_result(REVIEW))
        await ok("wait", second["id"])
        state = await wait_for_stop()

        assert "budget-exhausted" in strip_paths(state["stop_reason"])
        assert "max_architect_consults is 1" in strip_paths(state["stop_reason"])
        architects = [
            row for row in (await ok("jobs", "-n", "50"))["jobs"] if row["role"] == ARCHITECT
        ]
        assert len(architects) == 1, "a consultation beyond the budget started a job"
        assert len(await _events("consult.sent")) == 1
        assert state["architect_consults"] == {"used": 1, "max_architect_consults": 1}

    drive(body)
