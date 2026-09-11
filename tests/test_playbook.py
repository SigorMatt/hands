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
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import pytest

from hands.config import Config, load_config, parse_config
from hands.daemon import Daemon
from hands.playbook import (
    ACTIONS,
    EVENTS,
    JOB_PLACEHOLDERS,
    PlaceholderError,
    PlaybookEngine,
    PlaybookError,
    load_playbook,
    parse_playbook,
    playbook_path,
    render,
)
from hands.spool import Job, Spool
from harness import PROJECT, cli, config_body, drive, ok, poll, write_project

DESIGN = Path(__file__).parents[1] / "DESIGN.md"
EXAMPLE_FIXTURE = Path(__file__).parent / "fixtures" / "playbook_example.toml"
EXAMPLE = EXAMPLE_FIXTURE.read_text(encoding="utf-8")
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
    tmp_home: Path, workdir: Path, *, builder: dict[str, Any] | None = None
) -> Config:
    return parse_config(
        {
            "roles": {
                "builder": {"cwd": str(workdir), **(builder or {})},
                "aux": {"cwd": str(workdir)},
            }
        },
        project=PROJECT,
        path=tmp_home / ".hands" / f"{PROJECT}.toml",
    )


class Recorder:
    """The engine's two seams: what it sent, and what it enqueued (§6, §8)."""

    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []
        self.enqueued: list[dict[str, Any]] = []
        self.notified: list[tuple[str, dict[str, Any]]] = []
        self.refuse: str | None = None

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

    def notify(self, title: str, payload: dict[str, Any]) -> None:
        self.notified.append((title, payload))


def engine_for(
    tmp_home: Path,
    workdir: Path,
    body: str | None = EXAMPLE,
    *,
    builder: dict[str, Any] | None = None,
) -> tuple[PlaybookEngine, Recorder]:
    if body is not None:
        (workdir / "PLAYBOOK.toml").write_text(body)
    config = make_config(tmp_home, workdir, builder=builder)
    recorder = Recorder()
    engine = PlaybookEngine(
        config,
        Spool(tmp_home / ".hands"),
        send=recorder.send,
        enqueue=recorder.enqueue,
        notify=recorder.notify,
    )
    return engine, recorder


def finished(
    spool: Spool,
    *,
    role: str = "builder",
    state: str = "done",
    verdict: str | None = None,
    **kw: Any,
) -> Job:
    """A terminal job record in the spool, as the runner would leave it (§6)."""
    job = spool.create_job(role=role, context="clear", prompt="p", origin="cli")
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
    assert book.quiet_hours == "23:00-07:00"
    assert [(rule.on, rule.then) for rule in book.rules] == [
        ("builder.done", "send"),
        ("aux.done", "send"),
        ("aux.done", "stop"),
        ("builder.done", "stop"),
        ("builder.orphaned", "resume"),
        ("builder.failed", "resume"),
        ("monitor.tripwire", "stop"),
    ]
    assert book.rules[1].run == "{n+1}"
    assert book.rules[1].role == "builder"
    assert book.rules[1].context == "clear"
    assert book.rules[2].message == "Review of run {n} has blockers"
    assert book.sha256 == hashlib.sha256(EXAMPLE.encode()).hexdigest()


def test_the_events_and_actions_are_exactly_section_10s() -> None:
    assert EVENTS == (
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
    assert ACTIONS == ("send", "resume", "notify", "stop")
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
]


@pytest.mark.parametrize(
    ("name", "body", "expected"), BAD_PLAYBOOKS, ids=[case[0] for case in BAD_PLAYBOOKS]
)
def test_an_invalid_playbook_is_an_error_not_a_half_read_file(
    name: str, body: str, expected: str, tmp_path: Path
) -> None:
    with pytest.raises(PlaybookError) as caught:
        parse_playbook(body, path=tmp_path / "PLAYBOOK.toml")
    assert expected in str(caught.value)


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
        assert expected in refusals[name], f"{name}: the expectation is not its own refusal"
        for other, refusal in refusals.items():
            if other == name or refusal == refusals[name]:
                continue  # one sentence for two inputs is the loader's answer, not a loose pin
            assert expected not in refusal, f"{name}'s expectation also matches {other}"


def test_an_unparseable_playbook_stops_and_notifies_and_fires_nothing(
    tmp_home: Path, workdir: Path
) -> None:
    engine, recorder = engine_for(tmp_home, workdir, body="version = = 1")
    job = finished(engine.spool, verdict="VERDICT: run 2 finished")
    run(engine.on_job_start(job))
    assert engine.pipeline()["paused"] is True
    # U2: not the bare word "playbook" — the tmpdir path in the reason carries that.
    assert "the playbook cannot be read, so no rule can be trusted to fire" in (
        engine.pipeline()["stop_reason"]
    )
    assert [event.kind for event in engine.spool.events()] == ["stop"]
    assert recorder.notified
    run(engine.on_job(job))
    assert recorder.sent == []


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
    assert expected in str(caught.value)


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
            "prompt": "Review WORKPLAN.md commits since abc123",
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
    assert expected in state["stop_reason"]
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
        engine.pipeline()["stop_reason"]
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
    assert "monitor.tripwire" in engine.pipeline()["stop_reason"]


def test_a_held_job_stops_the_pipeline(tmp_home: Path, workdir: Path) -> None:
    """§10 lists `job.held`; the example has no rule for it, so it stops (§8)."""
    engine, _recorder = engine_for(tmp_home, workdir)
    job = engine.spool.create_job(
        role="builder", context="clear", prompt="p", origin="playbook", state="held"
    )
    run(engine.on_job_start(job))
    run(engine.on_event("job.held", job=job))
    assert engine.pipeline()["paused"] is True
    assert "job.held" in engine.pipeline()["stop_reason"]


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
    assert "max_resumes" in engine.pipeline()["stop_reason"]


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
    assert "4 job(s) queued" in engine.pipeline()["stop_reason"]


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
    (`paused by human`) and notifies. Without the event, a driver blocked on
    `hands wait --for stop,held` is not woken by a pause and §11's wake check has
    no one-command event behind it."""
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
    """One stop, one notification (the rule `stop()` already keeps): no event storm."""
    engine, recorder = engine_for(tmp_home, workdir)
    run(engine.pause())
    run(engine.pause())
    assert [e.kind for e in engine.spool.events()] == ["stop"]
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
    assert event.payload["by"] == "hands resume"
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
    job = finished(again.spool, verdict="VERDICT: run 2 finished")
    run(again.on_job_start(job))
    run(again.on_job(job))
    assert recorder.sent == []


def test_a_hand_sent_job_unpauses_the_pipeline(tmp_home: Path, workdir: Path) -> None:
    engine, _recorder = engine_for(tmp_home, workdir)
    run(engine.stop("because", {}))
    run(engine.on_send("cli"))
    assert engine.pipeline()["paused"] is False
    (resumed,) = [e for e in engine.spool.events() if e.kind == "pipeline.resumed"]
    assert resumed.payload["by"] == "a send"  # §10: a send un-pauses, and says so
    run(engine.stop("because", {}))
    run(engine.on_send("playbook"))  # its own send must not un-pause it
    assert engine.pipeline()["paused"] is True


# ----------------------------------------------- the daemon path (§4, §8, §11)


@pytest.fixture
def project(tmp_home: Path, workdir: Path) -> str:
    return write_project(tmp_home, config_body(tmp_home, workdir))


def write_playbook(workdir: Path, body: str) -> None:
    (workdir / "PLAYBOOK.toml").write_text(body)


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
        assert "audit-fixes" in out and "paused" in out

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

    async def __call__(self, url: str, *, title: str, message: str) -> None:
        self.sent.append(title)


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


async def assert_pause_is_a_no_op(daemon: Daemon, posts: Posts, reason: str) -> None:
    """Review should-fix 4 / §19: the pipeline is already stopped for `reason`, so
    `hands pause` keeps it, files nothing, notifies nobody — and says the reason,
    because a silent success reads as "I stopped it"."""
    was = await ok("pipeline")
    assert was["stop_reason"] == reason, was["stop_reason"]
    before = [event["id"] for event in (await ok("inbox"))["events"]]
    await daemon.notifier.drain()
    notified = list(posts.sent)

    code, out, err = await cli("pause")

    assert code == 0, err  # a no-op, not a failure
    assert reason in out, out  # the human learns why it was already stopped
    assert "already stopped" in out, out  # …and that this pause did nothing
    now = await ok("pipeline")
    assert now["stop_reason"] == reason
    assert now["stopped_at"] == was["stopped_at"]
    assert [event["id"] for event in (await ok("inbox"))["events"]] == before
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
        assert "job.held" in state["stop_reason"]
        await assert_pause_is_a_no_op(daemon, posts, state["stop_reason"])

    drive_notified(tmp_home, workdir, body)


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
        assert "a rule said so" in out
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
        assert "decisions-" in record["gate"]["reason"]
        # …and the held job is itself a §10 event with no rule: hands stops.
        state = await wait_for_stop()
        assert "job.held" in state["stop_reason"]

    drive(body)


def test_the_daemon_stops_the_pipeline_on_an_unmatched_event(
    project: str, workdir: Path
) -> None:
    write_playbook(workdir, 'version = 1\n[[rule]]\non = "aux.done"\nthen = "stop"\n')

    async def body(daemon: Daemon) -> None:
        job = await ok("send", "--role", "builder", "--context", "clear", "FAKE:result ok")
        await ok("wait", job["id"])
        state = await wait_for_stop()
        assert "builder.done" in state["stop_reason"]
        events = (await ok("inbox"))["events"]
        assert [event["kind"] for event in events][-1] == "stop"

    drive(body)


# ------------------------------------------- the acceptance criterion (§10)


def test_the_section_10_example_end_to_end(
    tmp_home: Path, workdir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """run finished → review sent → blockers=0 → run 3 sent → run 4 stops (§10)."""
    head = git_repo(workdir)
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
        assert records[1]["prompt"] == f"Review WORKPLAN.md commits since {head}"
        assert records[2]["prompt"] == "Execute WORKPLAN.md run 3"
        assert records[3]["prompt"] == f"Review WORKPLAN.md commits since {head}"
        assert all(record["state"] == "done" for record in records)
        sha = state["playbook"]["sha256"]
        assert [record["playbook_sha256"] for record in records] == [None, sha, sha, sha]

        assert state["auto_runs"] == {"allowed": [2, 3], "used": [3]}
        assert "would start run 4, which [limits] auto_runs does not list ([2, 3])" in (
            state["stop_reason"]
        )
        kinds = [event["kind"] for event in (await ok("inbox"))["events"]]
        assert kinds.count("playbook.rule") == 3
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


