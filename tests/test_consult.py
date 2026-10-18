"""Mission 26 U1: `consult` from the laptop, and the engine's half of it (DESIGN §42;
§31, §33, §38, H-058).

`hands consult [--file <path>] [<text>]` asks the engine, through the socket, to
start one architect consultation whose prompt carries the human's reason in place
of a review. The daemon, its socket and the CLI are the real ones (`harness`); the
roles are `tests/fake_claude.py`. The phone's `consult <secret> <text>` takes the
same `Api` code and is tested in `tests/test_phone.py`. Nothing here touches the
network, and every config and spool lives under the test's temporary home.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import pytest

import hands.api as api_mod
from conftest import commit_file, strip_paths
from hands.config import docs_root, load_config
from hands.daemon import Daemon
from hands.playbook import (
    ARCHITECT,
    HUMAN_REASON_HEADING,
    ArchitectBrief,
    ConsultRefused,
    PlaybookEngine,
    consult_prompt,
    parse_playbook,
)
from hands.runner import job_env
from hands.spool import Job, Spool
from harness import (
    PROJECT,
    architect_table,
    cli,
    close_consultation,
    config_body,
    drive,
    kit_zip,
    ok,
    open_consultation,
    passing_kit,
    poll,
)

#: §42: "The prompt's first line is exactly `hands consult: consult on job none
#: (role human)`".
HEAD = "hands consult: consult on job none (role human)"

KICKOFF = "Read meta/BRIEF.md and execute it.\\nFAKE:result VERDICT: mission 17 finished"

#: §31's series in role mode, autonomous, consulted on the review outcome.
ROLE_BOOK = f"""version = 1

[series]
name = "m17"
kickoff = "{KICKOFF}"
architect = "role"
autonomous = true
escalate_on = ["budget-exhausted"]

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

ROADMAP = "# ROADMAP\n\n- **M5 the next milestone** — gate: two runs merged.\n"

#: The human's reason; the fake architect's reply rides in it as a `FAKE:` line.
REASON = "The owner ruled on O-3; write the next kit.\n\n  Keep the second paragraph.\n"


@pytest.fixture
def workdir(tmp_path: Path) -> Path:
    d = tmp_path / "work"
    d.mkdir()
    return d


def role_project(tmp_home: Path, workdir: Path, *, book: str | None = ROLE_BOOK,
                 architect: bool = True) -> str:
    extra = architect_table(tmp_home) if architect else ""
    (tmp_home / ".hands" / f"{PROJECT}.toml").write_text(
        config_body(tmp_home, workdir, extra=extra)
    )
    commit_file(workdir, "meta/ROADMAP.md", ROADMAP)
    if book is not None:
        commit_file(workdir, "PLAYBOOK.toml", book)
    return PROJECT


async def events(kind: str) -> list[dict[str, Any]]:
    return [e for e in (await ok("inbox"))["events"] if e["kind"] == kind]


async def wait_events(kind: str, count: int) -> list[dict[str, Any]]:
    async def check() -> Any:
        found = await events(kind)
        return found if len(found) >= count else None

    return await poll(check, f"{count} {kind} event(s)")


async def stopped() -> dict[str, Any]:
    async def check() -> Any:
        state = await ok("pipeline")
        return state if state["paused"] else None

    return dict(await poll(check, "the pipeline to stop"))


# ---------------------------------------------------- the CLI twin (§42)


def test_hands_consult_starts_one_architect_consultation_of_origin_playbook(
    tmp_home: Path, workdir: Path
) -> None:
    """§42: `hands consult <text>` — one architect job of origin `playbook`, never
    `phone`, `clear`, its prompt's first line the human head, the reason verbatim
    under its heading and no review section; it un-pauses a stopped pipeline before
    the job starts; `consult.sent` carries every field §42 lists, never the reason;
    `consult.done` and the journal line name the human, never `job none`."""
    role_project(tmp_home, workdir)
    reason = REASON + "FAKE:result VERDICT: series complete"

    async def body(daemon: Daemon) -> None:
        await ok("pause")
        job = await ok("consult", reason)
        assert (job["role"], job["origin"], job["context"]) == (ARCHITECT, "playbook", "clear")
        record = await ok("wait", job["id"])
        assert record["state"] == "done" and record["verdict"] == "VERDICT: series complete"
        prompt = record["prompt"]
        assert prompt.splitlines()[0] == HEAD
        assert f"{HUMAN_REASON_HEADING}, verbatim between the markers:\n" in prompt
        assert f"----- BEGIN REASON -----\n{reason}\n----- END REASON -----\n" in prompt
        assert "BEGIN REVIEW" not in strip_paths(prompt)
        assert "## Blockers" not in strip_paths(prompt)
        assert "- **M5 the next milestone**" in strip_paths(prompt)  # §31's brief
        assert "consultation 1 of 12" in strip_paths(prompt)
        assert (await ok("show", job["id"]))["origin"] == "playbook"

        # §42: the stopped pipeline was un-paused before the job started.
        (resumed,) = await events("pipeline.resumed")
        assert resumed["payload"]["was"] == "paused by human"
        (sent,) = await events("consult.sent")
        payload = sent["payload"]
        head = payload.pop("head")
        assert isinstance(head, str) and len(head) == 40  # the builder's HEAD
        assert payload == {
            "job": job["id"],
            "about": None,
            "role": "human",
            "consulted": ARCHITECT,
            "event": "consult",
            "verdict": None,
            "rule": None,
            "consults": 1,
            "max_consults": 12,
            "requested_by": "cli",
            "reason_sha256": hashlib.sha256(reason.encode()).hexdigest(),
        }
        kinds = [e["kind"] for e in (await ok("inbox"))["events"]]
        assert kinds.index("pipeline.resumed") < kinds.index("consult.sent"), kinds

        (done,) = await wait_events("consult.done", 1)
        assert done["payload"]["about"] is None
        assert done["payload"]["role"] == "human"
        assert done["payload"]["event"] == "consult"
        assert done["payload"]["job"] == job["id"]
        state = await stopped()  # `series complete` stops, as any consultation's does
        assert "series complete" in strip_paths(state["stop_reason"])
        assert daemon.playbook.architect_consults_used() == 1
        for event in (await ok("inbox"))["events"]:
            assert "O-3" not in strip_paths(json.dumps(event)), event  # never the reason

    drive(body)
    (line,) = (workdir / "meta" / "journal.md").read_text(encoding="utf-8").splitlines()
    assert line.endswith(
        "on consult by the human: VERDICT: series complete"
    ), line
    assert " consult " in strip_paths(line) and "(architect done)" in strip_paths(line)
    assert "job none" not in strip_paths(line)


def test_hands_consult_with_a_file_appends_its_text_after_the_reason(
    tmp_home: Path, workdir: Path
) -> None:
    role_project(tmp_home, workdir)
    notes = workdir / "owner-notes.md"
    notes.write_text("## The ruling\n\nO-3: keep it.\nFAKE:result VERDICT: series complete\n",
                     encoding="utf-8")

    async def body(daemon: Daemon) -> None:
        job = await ok("consult", "--file", str(notes), "Read the notes.")
        record = await ok("wait", job["id"])
        reason = f"Read the notes.\n\n{notes.read_text(encoding='utf-8')}"
        assert f"----- BEGIN REASON -----\n{reason}\n----- END REASON -----\n" in record["prompt"]
        (sent,) = await events("consult.sent")
        assert sent["payload"]["reason_sha256"] == hashlib.sha256(reason.encode()).hexdigest()
        assert sent["payload"]["requested_by"] == "cli"

    drive(body)


@pytest.mark.parametrize(
    ("name", "data", "why"),
    [
        ("notes.txt", b"text", "is not a .md basename"),
        (".notes.md", b"text", "is not a .md basename"),
        ("notes.MD", b"text", "is not a .md basename"),
        ("big.md", b"x" * (256 * 1024 + 1), "over the 262144-byte cap"),
        ("latin.md", "café".encode("latin-1"), "is not UTF-8 text"),
    ],
    ids=["txt", "dotted", "upper", "big", "latin-1"],
)
def test_hands_consult_refuses_a_file_outside_the_name_and_size_rules(
    tmp_home: Path, workdir: Path, name: str, data: bytes, why: str
) -> None:
    """§42: "the CLI reads the file under the same name and size rules" — refused in
    the client, before the daemon is asked, with nothing filed."""
    role_project(tmp_home, workdir)
    path = workdir / name
    path.write_bytes(data)

    async def body(daemon: Daemon) -> None:
        code, _out, err = await cli("consult", "--file", str(path), "why")
        assert code == 2, err
        assert why in strip_paths(err), err
        assert (await ok("jobs"))["jobs"] == []

    drive(body)


def test_hands_consult_refuses_an_empty_reason(tmp_home: Path, workdir: Path) -> None:
    role_project(tmp_home, workdir)

    async def body(daemon: Daemon) -> None:
        for argv in (("consult",), ("consult", "   ")):
            code, _out, err = await cli(*argv)
            assert code == 1, err
            assert "the reason is empty" in strip_paths(err), err
        assert (await ok("jobs"))["jobs"] == []

    drive(body)


#: A phone-mode series: no `architect = "role"`, and so no rule consulting the role.
PHONE_BOOK = f'version = 1\n\n[series]\nname = "m17"\nkickoff = "{KICKOFF}"\n'


@pytest.mark.parametrize(
    ("book", "why"),
    [(PHONE_BOOK, '[series] architect = "role"'), (None, "no playbook is loaded")],
    ids=["phone-mode", "no-playbook"],
)
def test_hands_consult_is_refused_outside_role_mode(
    tmp_home: Path, workdir: Path, book: str | None, why: str
) -> None:
    role_project(tmp_home, workdir, book=book)

    async def body(daemon: Daemon) -> None:
        code, _out, err = await cli("consult", "why")
        assert code == 1, err
        assert why in strip_paths(err), err
        assert (await ok("jobs"))["jobs"] == []

    drive(body)


def test_a_consultation_is_refused_without_an_architect_role(
    tmp_home: Path, workdir: Path
) -> None:
    """§42: "the project configures no `[roles.architect]`". A daemon refuses to
    start on a role-mode playbook without the table (§31), so this is the engine's
    own refusal, asked with that playbook in hand; nothing is enqueued."""
    role_project(tmp_home, workdir, architect=False)
    config = load_config(PROJECT)
    spool = Spool(tmp_home / ".hands")
    enqueued: list[dict[str, Any]] = []

    async def enqueue(**fields: Any) -> Job:
        enqueued.append(fields)
        return spool.create_job(**fields)

    async def nothing(**_: Any) -> dict[str, Any]:
        return {}

    engine = PlaybookEngine(config, spool, send=nothing, enqueue=enqueue)
    engine.playbook = parse_playbook(ROLE_BOOK, path=workdir / "PLAYBOOK.toml")
    why = engine.consult_mode_refusal()
    assert why is not None and "[roles.architect]" in strip_paths(why), why
    with pytest.raises(ConsultRefused, match=r"\[roles\.architect\]"):
        asyncio.run(engine.consult_human("why", requested_by="cli", cap=1 << 20))
    assert enqueued == []


@pytest.mark.parametrize("role", ["builder", "aux"])
@pytest.mark.parametrize("how", ["running", "held"])
def test_hands_consult_is_refused_while_a_builder_or_aux_job_is_busy(
    tmp_home: Path, workdir: Path, role: str, how: str
) -> None:
    role_project(tmp_home, workdir)

    async def body(daemon: Daemon) -> None:
        if how == "running":
            busy = await ok("send", "--role", role, "--context", "clear", "FAKE:block")

            async def running() -> bool:
                return (await ok("show", busy["id"]))["state"] == "running"

            await poll(running, "the busy job to run")
        else:
            busy = await ok("send", "--role", role, "--context", "clear", "--gate", "hold", "x")
        code, _out, err = await cli("consult", "why")
        assert code == 1, err
        assert f"the {role} has a job {how} ({busy['id']})" in strip_paths(err), err
        assert [row["role"] for row in (await ok("jobs"))["jobs"]] == [role]
        await ok("cancel" if how == "running" else "deny", busy["id"])

    drive(body)


def test_hands_consult_is_refused_while_an_architect_job_is_running_or_held(
    tmp_home: Path, workdir: Path
) -> None:
    role_project(tmp_home, workdir)

    async def body(daemon: Daemon) -> None:
        job = open_consultation(daemon)
        try:
            code, _out, err = await cli("consult", "again")
        finally:
            close_consultation(daemon, job)
        assert code == 1, err
        assert f"the architect has a job running ({job.id})" in strip_paths(err), err
        held = daemon.spool.create_job(
            role=ARCHITECT, context="clear", prompt="x", origin="playbook", state="held"
        )
        code, _out, err = await cli("consult", "again")
        assert code == 1, err
        assert f"the architect has a job held ({held.id})" in strip_paths(err), err

    drive(body)


def test_hands_consult_is_refused_while_a_next_kit_wait_is_open(
    tmp_home: Path, workdir: Path
) -> None:
    role_project(tmp_home, workdir)

    async def body(daemon: Daemon) -> None:
        job = await ok("consult", "FAKE:result VERDICT: next kit never-filed")
        await ok("wait", job["id"])

        async def waiting() -> bool:
            return daemon.playbook.kit_wait() == (job["id"], "never-filed")

        await poll(waiting, "the engine's wait for the kit")
        code, _out, err = await cli("consult", "again")
        assert code == 1, err
        assert "the engine waits for kit 'never-filed'" in strip_paths(err), err

    drive(body)


def test_a_consultation_whose_enqueue_fails_leaves_the_pipeline_stopped(
    tmp_home: Path, workdir: Path
) -> None:
    """PR #6 hosted review finding 2: the un-pause comes before the enqueue (§42),
    and an enqueue that raises restores the stop it cleared — paused, by whom, its
    reason and its time — and files no `consult.sent`."""
    role_project(tmp_home, workdir)

    async def body(daemon: Daemon) -> None:
        await ok("pause")
        engine = daemon.playbook
        before = (engine.state.paused, engine.state.paused_by, engine.state.stop_reason,
                  engine.state.stopped_at)
        assert before[0] is True

        async def broken(**_: Any) -> Job:
            raise OSError("the spool is full")

        engine.enqueue = broken
        code, _out, _err = await cli("consult", "why")
        assert code != 0
        after = (engine.state.paused, engine.state.paused_by, engine.state.stop_reason,
                 engine.state.stopped_at)
        assert after == before
        state = await ok("pipeline")
        assert state["paused"] is True and state["stop_reason"] == before[2]
        assert await events("consult.sent") == []
        assert (await ok("jobs"))["jobs"] == []

    drive(body)


@pytest.mark.parametrize("change", ["dirty", "recommitted"])
def test_a_consult_refused_as_busy_leaves_the_engine_untouched(
    tmp_home: Path, workdir: Path, change: str
) -> None:
    """PR #6 hosted review finding 6: a consult refused because the builder runs
    does not load the playbook — a dirty one does not stop the pipeline, and a newly
    committed one replaces neither the engine's playbook nor its `last_rule`."""
    role_project(tmp_home, workdir)

    async def body(daemon: Daemon) -> None:
        busy = await ok("send", "--role", "builder", "--context", "clear", "FAKE:block")

        async def running() -> bool:
            return (await ok("show", busy["id"]))["state"] == "running"

        await poll(running, "the builder to run")
        engine = daemon.playbook
        book = engine.playbook
        assert book is not None
        rule = {"rule": 1, "event": "aux.done", "fired_at": "2026-10-18T00:00:00Z"}
        engine.state.last_rule, engine.state.last_rule_sha256 = rule, book.sha256
        if change == "dirty":
            (workdir / "PLAYBOOK.toml").write_text(ROLE_BOOK + "\n# dirty\n", encoding="utf-8")
        else:
            commit_file(workdir, "PLAYBOOK.toml", ROLE_BOOK + "\n# another file\n")
        try:
            code, _out, err = await cli("consult", "why")
            assert code == 1, err
            assert f"the builder has a job running ({busy['id']})" in strip_paths(err), err
            assert engine.playbook is book
            assert engine.state.last_rule == rule
            assert engine.state.last_rule_sha256 == book.sha256
            assert engine.state.paused is False
            assert await events("stop") == []
        finally:
            await ok("cancel", busy["id"])

    drive(body)


def test_the_budget_counts_a_human_consultation_and_refuses_at_the_limit(
    tmp_home: Path, workdir: Path
) -> None:
    """§42: "counted against `[limits] max_architect_consults`" — and, once spent,
    refused with the budget's reason, starting nothing."""
    role_project(tmp_home, workdir,
                 book=ROLE_BOOK.replace("max_architect_consults = 12",
                                        "max_architect_consults = 1"))

    async def body(daemon: Daemon) -> None:
        job = await ok("consult", "FAKE:result VERDICT: series complete")
        await ok("wait", job["id"])
        await stopped()
        assert daemon.playbook.architect_consults_used() == 1
        code, _out, err = await cli("consult", "again")
        assert code == 1, err
        assert "max_architect_consults is 1" in strip_paths(err), err
        assert "budget-exhausted" in strip_paths(err), err
        assert len((await ok("jobs"))["jobs"]) == 1
        assert (await ok("pipeline"))["paused"] is True, "a refusal un-paused the pipeline"

    drive(body)


def test_a_prompt_over_the_cap_is_refused_with_the_caps_reason(
    tmp_home: Path, workdir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    role_project(tmp_home, workdir)
    monkeypatch.setattr(api_mod, "MAX_PROMPT_BYTES", 4096)

    async def body(daemon: Daemon) -> None:
        await ok("pause")
        code, _out, err = await cli("consult", "x" * 4096)
        assert code == 1, err
        assert "over the 4096 byte cap of §2" in strip_paths(err), err
        assert (await ok("jobs"))["jobs"] == []
        assert (await ok("pipeline"))["paused"] is True, "a refusal un-paused the pipeline"

    drive(body)


# ------------------------------------- next kit and `hands kit file` (§42, §32)

#: The scripted architect's `hands kit file`: the daemon's `kit_file` over the
#: socket with the kit's name and bytes, as `tests/test_playbook.py`'s e2e does.
FILE_APPLY = """
import base64, sys
from pathlib import Path
from hands.cli import call
name, _, path = sys.argv[3].partition("=")
params = {"name": name, "zip": base64.b64encode(Path(path).read_bytes()).decode()}
try:
    call(sys.argv[1], "kit_file", params, project=sys.argv[2])
except Exception as exc:
    Path(path).with_suffix(".refused").write_text(str(exc))
"""


def test_a_human_consultations_next_kit_is_filed_approved_and_applied_as_any(
    tmp_home: Path, workdir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§42: "read for its verdict (`next kit`, …), its kit filed and applied as any":
    `hands kit file` during it is accepted as a consultation's, the engine approves
    the apply under `autonomous` and the kickoff follows."""
    role_project(tmp_home, workdir)
    kits = tmp_home / "filed"
    kits.mkdir()
    zipped = kits / "mission-18-kit.zip"
    zipped.write_bytes(kit_zip(passing_kit()))
    argv = [sys.executable, "-c", FILE_APPLY, str(tmp_home / ".hands" / "handsd.sock"),
            PROJECT, f"mission-18-kit={zipped}"]
    replies = tmp_home / "replies.json"
    replies.write_text(json.dumps([
        {"result": "VERDICT: next kit mission-18-kit", "exec": argv},
        "VERDICT: kit applied abc1234",
    ]))
    monkeypatch.setenv("HANDS_FAKE_CLAUDE_REPLIES", str(replies))

    async def body(daemon: Daemon) -> None:
        job = await ok("consult", "The owner file is committed; write the next kit.")
        state = await stopped()
        assert "Mission 17 finished" in strip_paths(state["stop_reason"]), state
        rows = sorted((await ok("jobs", "-n", "50"))["jobs"], key=lambda row: row["id"])
        assert [(row["role"], row["origin"]) for row in rows] == [
            (ARCHITECT, "playbook"), ("builder", "architect"), ("builder", "playbook"),
        ]
        assert not list(kits.glob("*.refused")), [p.read_text() for p in kits.glob("*.refused")]
        apply_job = await ok("show", rows[1]["id"])
        record = daemon.spool.read_kit_record(apply_job["kit_id"])
        assert record is not None and record["consultation"] == job["id"]
        assert apply_job["gate"]["decided_by"] == "playbook"

    drive(body)


# ----------------------------------- the guard's variable and the runner (§42)


def test_the_runner_sets_hands_consult_role_to_human_from_the_head(
    tmp_home: Path, workdir: Path
) -> None:
    role_project(tmp_home, workdir)
    config = load_config(PROJECT)
    job = Job(id="j1", role=ARCHITECT, context="clear", state="queued", created="now",
              origin="playbook", prompt=f"{HEAD}\n\nrest")
    env = job_env(job, config.role(ARCHITECT), PROJECT)
    assert env["HANDS_CONSULT_ROLE"] == "human"


# --------------------------------- a review's consultation is unchanged (§42)

_REVIEW_RESULT = (
    "VERDICT: review mission 7 blockers=1 should-fix=1\n\n## Blockers\n\n1. b one\n\n"
    "## Should-fix\n\n1. s one\n\n## Notes\n\nn\n"
)

#: main's (9877b57) prompt for this review and brief, the docs root as `<docs>`.
_MAIN_REVIEW_PROMPT = (
    "hands consult: aux.done on job j-review-1 (role aux)\n\nhandsd started you as the "
    "architect role for one consultation (DESIGN §31).\n\nEvent: aux.done\nJob: j-review-1\n"
    "Role: aux\nState: done\nVerdict: VERDICT: review mission 7 blockers=1 should-fix=1\n"
    "The full record: hands show j-review-1\n\nThe review's verdict line and its "
    "`## Blockers` and `## Should-fix` sections, verbatim between the markers:\n"
    "----- BEGIN REVIEW -----\nVERDICT: review mission 7 blockers=1 should-fix=1\n\n"
    "## Blockers\n\n1. b one\n\n\n## Should-fix\n\n1. s one\n\n----- END REVIEW -----\n\n"
    "Decided by the human since your last consultation — every `answer` from the phone, "
    "every `hands send --role builder --context keep`, and every meta/decisions/*-owner.md "
    "committed since then — verbatim between the markers:\n----- BEGIN DECISIONS -----\n"
    "[d]\nx\n----- END DECISIONS -----\n\nThe roadmap is meta/ROADMAP.md; read it whole "
    "from your clone. Its next unmet milestone — the first milestone in meta/ROADMAP.md "
    "whose heading is not marked DONE — verbatim between the markers:\n"
    "----- BEGIN MILESTONE -----\n- **M5 next**\n----- END MILESTONE -----\n\n"
    "The escalation conditions of this series ([series], §31):\n    gate_failures = 2 "
    "(the same roadmap gate failing that many times in a row)\n    escalate_on = "
    "budget-exhausted\n    this is consultation 3 of 12 ([limits] max_architect_consults); "
    "when the budget is exhausted handsd stops the series itself, naming budget-exhausted\n\n"
    "The handbook of the hands that runs you (HANDS_DOCS=<docs>); Read it before writing "
    "anything:\n    handbook  = `<docs>/docs/ARCHITECT-HANDBOOK.md`\n    templates = "
    "`<docs>/templates`\n\nThe instruction: write the next kit from ROADMAP and the review, "
    "file it, or escalate.\nStage the kit as a directory kits/<name>/<repository paths> and "
    "file it with `hands kit file kits/<name>` before you reply `VERDICT: next kit <name>`: "
    "handsd waits for the apply that filing makes, and stops when there is none.\n\n"
    "Your reply's first line is exactly one of:\n\n    VERDICT: next kit <name>\n"
    "    VERDICT: series complete\n    VERDICT: escalate <reason>\n"
)


def test_a_reviews_architect_prompt_is_mains_byte_for_byte() -> None:
    job = Job(id="j-review-1", role="aux", context="clear", state="done",
              created="2026-10-18T00:00:00Z", origin="playbook", prompt="Review it",
              verdict=_REVIEW_RESULT.splitlines()[0], result=_REVIEW_RESULT)
    brief = ArchitectBrief(roadmap="- **M5 next**", consults=3, max_consults=12,
                           escalate_on=("budget-exhausted",), decided="[d]\nx")
    prompt = consult_prompt("aux.done", job, role=ARCHITECT, brief=brief)
    assert prompt.replace(str(docs_root()), "<docs>") == _MAIN_REVIEW_PROMPT


def test_a_reviews_consult_sent_carries_mains_fields(tmp_home: Path, workdir: Path) -> None:
    """The review's `consult.sent` keeps main's fields and values: nothing §42 adds
    (`requested_by`, `reason_sha256`) is on it, and `role` is the reviewer's."""
    role_project(tmp_home, workdir)
    config = load_config(PROJECT)
    spool = Spool(tmp_home / ".hands")
    enqueued: list[dict[str, Any]] = []

    async def enqueue(**fields: Any) -> Job:
        enqueued.append(fields)
        return spool.create_job(**fields)

    async def nothing(**_: Any) -> dict[str, Any]:
        return {}

    engine = PlaybookEngine(config, spool, send=nothing, enqueue=enqueue)
    review = spool.create_job(role="aux", context="clear", prompt="Review it", origin="cli")
    spool.transition(review, "running")
    review = spool.transition(review, "done", verdict=_REVIEW_RESULT.splitlines()[0],
                              result=_REVIEW_RESULT)
    asyncio.run(engine.on_job(review))
    (call,) = enqueued
    assert call["prompt"].startswith(f"hands consult: aux.done on job {review.id} (role aux)\n")
    (sent,) = [e.payload for e in spool.events() if e.kind == "consult.sent"]
    head = sent.pop("head")
    assert isinstance(head, str) and len(head) == 40
    assert sent == {
        "job": sent["job"], "about": review.id, "role": "aux", "consulted": ARCHITECT,
        "event": "aux.done", "verdict": review.verdict, "rule": 0, "consults": 1,
        "max_consults": 12,
    }
    assert set(sent) == {"job", "about", "role", "consulted", "event", "verdict", "rule",
                         "consults", "max_consults"}
