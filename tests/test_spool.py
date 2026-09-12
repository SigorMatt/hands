"""U1: the spool — job records (§6), role state, the inbox (§11), path confinement (§4)."""

import json
import os
from pathlib import Path

import pytest

from conftest import strip_paths
from hands import spool as spool_mod
from hands.spool import (
    INITIAL_STATES,
    JOB_FIELDS,
    STATES,
    TERMINAL_STATES,
    TRANSITIONS,
    IllegalTransition,
    PathEscape,
    Spool,
    SpoolError,
    new_job_id,
    resolve_under_roots,
)

# ---------------------------------------------------------------- job records


def make(spool: Spool, **kw):
    kw.setdefault("role", "builder")
    kw.setdefault("context", "clear")
    kw.setdefault("prompt", "Execute WORKPLAN.md run 2")
    kw.setdefault("origin", "cli")
    return spool.create_job(**kw)


def test_spool_creates_its_directories(tmp_home: Path) -> None:
    spool = Spool()
    assert spool.root == tmp_home / ".hands"
    assert spool.jobs_dir.is_dir()
    assert spool.roles_dir.is_dir()


def test_job_record_has_exactly_the_design_fields(tmp_home: Path) -> None:
    """DESIGN §6 lists the record verbatim; later units must not reshape it."""
    design = {
        "id",
        "role",
        "context",
        "created",
        "started",
        "ended",
        "origin",
        "prompt",
        "files_written",
        "session_id",
        "transcript_path",
        "pid",
        "exit_code",
        "head_at_start",
        "head_at_end",
        "result",
        "verdict",
        "stderr_tail",
        "permission_denials",
        "num_turns",
        "duration_ms",
        "total_cost_usd",
        "limit",
        "gate",
        "resumed_from",
    }
    # `state` and `playbook_sha256` are carried too: §6 names the states and §10
    # requires the playbook sha on every job the playbook fires. `failure_reason`
    # is §23's (H-014): which of the failure causes made a job `failed`.
    assert set(JOB_FIELDS) == design | {"state", "playbook_sha256", "failure_reason"}

    spool = Spool()
    job = make(spool)
    on_disk = json.loads((spool.jobs_dir / f"{job.id}.json").read_text())
    assert set(on_disk) == set(JOB_FIELDS)


def test_new_job_starts_queued_and_stamps_created(tmp_home: Path) -> None:
    spool = Spool()
    job = make(spool)
    assert job.state == "queued"
    assert job.created.endswith("Z")
    assert job.started is None and job.ended is None
    assert job.files_written == [] and job.permission_denials == []
    assert spool.load_job(job.id) == job


def test_a_gated_job_may_start_held(tmp_home: Path) -> None:
    spool = Spool()
    job = make(spool, state="held", gate={"reason": "decisions file"})
    assert job.state == "held"
    assert spool.load_job(job.id).gate == {"reason": "decisions file"}


def test_a_job_cannot_be_created_in_a_non_initial_state(tmp_home: Path) -> None:
    spool = Spool()
    assert INITIAL_STATES == frozenset({"held", "queued"})
    with pytest.raises(SpoolError):
        make(spool, state="running")


@pytest.mark.parametrize("field,value", [("context", "resume"), ("origin", "robot"), ("role", "")])
def test_bad_job_fields_are_refused(tmp_home: Path, field: str, value: str) -> None:
    spool = Spool()
    with pytest.raises(SpoolError):
        make(spool, **{field: value})


def test_job_ids_are_short_sortable_and_unique(tmp_home: Path) -> None:
    spool = Spool()
    ids = [make(spool).id for _ in range(50)]
    assert len(set(ids)) == 50
    assert all(len(i) <= 16 for i in ids)
    assert all(i == "".join(c for c in i if c.isalnum() or c == "-") for i in ids)
    assert ids == sorted(ids) or sorted(ids) == sorted(set(ids))
    # monotonic in time: a later millisecond sorts after an earlier one
    assert new_job_id(1_700_000_000_000) < new_job_id(1_700_000_001_000)


def test_missing_job_raises(tmp_home: Path) -> None:
    with pytest.raises(SpoolError):
        Spool().load_job("nosuchjob")


def test_list_jobs_is_sorted_and_ignores_stray_files(tmp_home: Path) -> None:
    spool = Spool()
    ids = sorted(make(spool).id for _ in range(3))
    (spool.jobs_dir / "notes.txt").write_text("hi")
    (spool.jobs_dir / ".tmp-half.json").write_text("{")
    assert [j.id for j in spool.list_jobs()] == ids


# ----------------------------------------------------------- state machine §6


def test_transition_table_matches_design_section_6() -> None:
    assert TRANSITIONS["held"] == frozenset({"queued", "denied"})
    assert TRANSITIONS["queued"] == frozenset({"running", "killed"})
    assert TRANSITIONS["running"] == frozenset({"done", "failed", "limited", "killed", "orphaned"})
    assert TERMINAL_STATES == frozenset(
        {"done", "failed", "limited", "killed", "orphaned", "denied"}
    )
    for state in TERMINAL_STATES:
        assert TRANSITIONS[state] == frozenset()
    assert set(TRANSITIONS) == set(STATES)


# Every state is reachable by legal edges only, so the tests below never need a
# back door into the state machine.
PATH_TO = {
    "held": (),
    "queued": ("queued",),
    "denied": ("denied",),
    "running": ("queued", "running"),
    "done": ("queued", "running", "done"),
    "failed": ("queued", "running", "failed"),
    "limited": ("queued", "running", "limited"),
    "killed": ("queued", "killed"),
    "orphaned": ("queued", "running", "orphaned"),
}


def job_in_state(spool: Spool, state: str):
    """A fresh job driven from `held` to `state` along legal edges only."""
    job = make(spool, state="held")
    for step in PATH_TO[state]:
        spool.transition(job, step)
    assert job.state == state
    return job


LEGAL = sorted((a, b) for a, targets in TRANSITIONS.items() for b in targets)
ILLEGAL = sorted((a, b) for a in STATES for b in STATES if b not in TRANSITIONS[a])


@pytest.mark.parametrize("start,end", LEGAL)
def test_every_legal_transition_is_allowed(tmp_home: Path, start: str, end: str) -> None:
    spool = Spool()
    job = job_in_state(spool, start)
    out = spool.transition(job, end)
    assert out.state == end
    assert spool.load_job(job.id).state == end


@pytest.mark.parametrize("start,end", ILLEGAL)
def test_every_illegal_transition_is_refused(tmp_home: Path, start: str, end: str) -> None:
    spool = Spool()
    job = job_in_state(spool, start)
    before = (spool.jobs_dir / f"{job.id}.json").read_bytes()
    with pytest.raises(IllegalTransition) as exc:
        spool.transition(job, end)
    assert start in strip_paths(str(exc.value)) and end in strip_paths(str(exc.value))
    assert (spool.jobs_dir / f"{job.id}.json").read_bytes() == before
    assert spool.load_job(job.id).state == start


def test_unknown_state_is_refused(tmp_home: Path) -> None:
    spool = Spool()
    job = make(spool)
    with pytest.raises(IllegalTransition):
        spool.transition(job, "finished")


def test_denied_is_terminal(tmp_home: Path) -> None:
    """U4 depends on this: nothing releases a denied job."""
    spool = Spool()
    job = make(spool, state="held")
    spool.transition(job, "denied", gate={"reason": "no", "decided_by": "cli"})
    for state in STATES:
        with pytest.raises(IllegalTransition):
            spool.transition(job, state)


def test_running_stamps_started_and_terminal_stamps_ended(tmp_home: Path) -> None:
    spool = Spool()
    job = make(spool)
    spool.transition(job, "running", pid=4242)
    assert job.started is not None and job.ended is None
    assert job.pid == 4242
    spool.transition(job, "done", result="VERDICT: run 2 finished", exit_code=0)
    assert job.ended is not None
    assert spool.load_job(job.id).result == "VERDICT: run 2 finished"


def test_transition_refuses_unknown_fields(tmp_home: Path) -> None:
    spool = Spool()
    job = make(spool)
    with pytest.raises(SpoolError):
        spool.transition(job, "running", pdi=1)
    assert spool.load_job(job.id).state == "queued"


def test_a_limited_job_is_superseded_by_a_resume_job_not_a_transition(tmp_home: Path) -> None:
    spool = Spool()
    job = make(spool)
    spool.transition(job, "running")
    spool.transition(job, "limited", limit={"category": "rate_limit", "message": "x"})
    resume = make(spool, prompt="Resume WORKPLAN.md", origin="playbook", resumed_from=job.id)
    assert resume.id != job.id
    assert resume.resumed_from == job.id
    assert spool.load_job(job.id).state == "limited"


# ------------------------------------------------------------- atomic writes


def test_atomic_write_leaves_the_old_record_intact_when_the_replace_crashes(
    tmp_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spool = Spool()
    job = make(spool)
    path = spool.jobs_dir / f"{job.id}.json"
    before = path.read_bytes()

    def crash(src, dst):  # simulate a crash between writing the tmp file and renaming
        raise OSError("power cut")

    monkeypatch.setattr(spool_mod.os, "replace", crash)
    job.result = "half a record"
    with pytest.raises(OSError):
        spool.save_job(job)

    assert path.read_bytes() == before
    assert spool.load_job(job.id).result is None
    assert list(spool.jobs_dir.iterdir()) == [path]  # no temp file left behind


def test_a_record_is_never_visible_half_written(
    tmp_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spool = Spool()
    job = make(spool)
    path = spool.jobs_dir / f"{job.id}.json"
    seen = []

    real_replace = os.replace

    def watch(src, dst):
        seen.append(json.loads(Path(dst).read_text())["state"])  # old content still readable
        return real_replace(src, dst)

    monkeypatch.setattr(spool_mod.os, "replace", watch)
    spool.transition(job, "running")
    monkeypatch.undo()
    assert seen == ["queued"]
    assert json.loads(path.read_text())["state"] == "running"


# ------------------------------------------------------------- role state §6


def test_unknown_role_state_is_empty(tmp_home: Path) -> None:
    state = Spool().read_role("builder")
    assert state.role == "builder"
    assert state.last_session_id is None
    assert state.last_job is None


def test_role_state_round_trips(tmp_home: Path) -> None:
    spool = Spool()
    job = make(spool)
    spool.set_last_session("builder", session_id="sess-1", job_id=job.id)
    state = spool.read_role("builder")
    assert state.last_session_id == "sess-1"
    assert state.last_job == job.id
    assert json.loads((spool.roles_dir / "builder.json").read_text())["last_session_id"] == "sess-1"


def test_role_state_is_written_atomically(tmp_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    spool = Spool()
    spool.set_last_session("builder", session_id="sess-1", job_id="j1")
    monkeypatch.setattr(spool_mod.os, "replace", lambda src, dst: (_ for _ in ()).throw(OSError()))
    with pytest.raises(OSError):
        spool.set_last_session("builder", session_id="sess-2", job_id="j2")
    monkeypatch.undo()
    assert spool.read_role("builder").last_session_id == "sess-1"
    assert sorted(p.name for p in spool.roles_dir.iterdir()) == ["builder.json"]


# ------------------------------------------------------------------ inbox §11


def test_inbox_is_append_only_jsonl(tmp_home: Path) -> None:
    spool = Spool()
    first = spool.append_event("job.done", {"job": "j1", "verdict": "VERDICT: ok"})
    before = spool.inbox_path.read_bytes()
    second = spool.append_event("stop", {"reason": "blockers"})
    after = spool.inbox_path.read_bytes()

    assert after.startswith(before)  # history is never rewritten
    assert first.id != second.id and first.id < second.id
    assert [e.kind for e in spool.events()] == ["job.done", "stop"]
    assert spool.events()[0].payload == {"job": "j1", "verdict": "VERDICT: ok"}
    assert spool.events()[0].created.endswith("Z")
    assert len(spool.inbox_path.read_text().strip().splitlines()) == 2


def test_ack_does_not_rewrite_history(tmp_home: Path) -> None:
    spool = Spool()
    a = spool.append_event("job.done", {"job": "j1"})
    b = spool.append_event("stop", {"reason": "why"})
    before = spool.inbox_path.read_bytes()

    assert [e.id for e in spool.unacked()] == [a.id, b.id]
    spool.ack(a.id)
    assert spool.inbox_path.read_bytes() == before
    assert [e.id for e in spool.unacked()] == [b.id]
    assert [e.id for e in spool.events()] == [a.id, b.id]

    spool.ack(a.id)  # acking twice is a no-op, not an error
    assert [e.id for e in spool.unacked()] == [b.id]

    spool.ack([b.id])
    assert spool.unacked() == []


def test_acking_an_unknown_event_is_an_error(tmp_home: Path) -> None:
    spool = Spool()
    with pytest.raises(SpoolError):
        Spool().ack("e000999")
    assert spool.unacked() == []


def test_events_since_filters_by_id(tmp_home: Path) -> None:
    spool = Spool()
    a = spool.append_event("heartbeat", {})
    b = spool.append_event("stop", {})
    assert [e.id for e in spool.events(since=a.id)] == [b.id]


@pytest.mark.parametrize(
    "kind",
    [
        "job.done",
        "job.failed",
        "job.limited",
        "job.killed",
        "job.orphaned",
        "job.denied",
        "job.held",
        "monitor.stall",
        "monitor.tripwire",
        "monitor.event",
        "playbook.rule",
        "stop",
        "gate.decided",
        "gate.requested",
        "limit",
        "resume",
        "heartbeat",
    ],
)
def test_every_design_event_kind_is_accepted(tmp_home: Path, kind: str) -> None:
    assert Spool().append_event(kind, {}).kind == kind


@pytest.mark.parametrize("kind", ["", "Job.Done", "weather.report", "job..done", "job done"])
def test_unknown_event_kinds_are_refused(tmp_home: Path, kind: str) -> None:
    with pytest.raises(SpoolError):
        Spool().append_event(kind, {})


def test_inbox_survives_a_truncated_last_line(tmp_home: Path) -> None:
    spool = Spool()
    spool.append_event("heartbeat", {})
    with spool.inbox_path.open("a") as fh:
        fh.write('{"id": "e000002", "kind": "st')
    with pytest.raises(SpoolError):
        spool.events()


# ------------------------------------------------------ path confinement (§4)


@pytest.fixture
def roots(tmp_home: Path) -> list[Path]:
    (tmp_home / "git" / "demo" / "src").mkdir(parents=True)
    (tmp_home / "Downloads").mkdir()
    (tmp_home / "secrets").mkdir()
    (tmp_home / "secrets" / "key").write_text("shh")
    return [tmp_home / "git" / "demo", tmp_home / "Downloads"]


def test_a_path_inside_a_root_resolves(roots, tmp_home: Path) -> None:
    assert resolve_under_roots("~/git/demo/src/a.py", roots) == tmp_home / "git/demo/src/a.py"
    assert resolve_under_roots(tmp_home / "Downloads" / "x", roots) == tmp_home / "Downloads/x"


def test_the_root_itself_is_inside(roots, tmp_home: Path) -> None:
    assert resolve_under_roots(tmp_home / "git" / "demo", roots) == tmp_home / "git" / "demo"


def test_a_nonexistent_path_under_a_root_is_allowed(roots, tmp_home: Path) -> None:
    new = tmp_home / "git/demo/new/deep.txt"
    assert resolve_under_roots("~/git/demo/new/deep.txt", roots) == new


@pytest.mark.parametrize(
    "candidate",
    [
        "~/git/demo/../secrets/key",
        "~/git/demo/src/../../secrets/key",
        "~/git/../secrets/key",
        "..",
    ],
)
def test_dotdot_is_rejected(roots, candidate: str) -> None:
    with pytest.raises(PathEscape):
        resolve_under_roots(candidate, roots)


def test_an_absolute_path_outside_the_roots_is_rejected(roots, tmp_home: Path) -> None:
    with pytest.raises(PathEscape):
        resolve_under_roots("/etc/passwd", roots)
    with pytest.raises(PathEscape):
        resolve_under_roots(tmp_home / "secrets" / "key", roots)


def test_a_sibling_with_the_same_prefix_is_rejected(roots, tmp_home: Path) -> None:
    (tmp_home / "git" / "demo-evil").mkdir()
    with pytest.raises(PathEscape):
        resolve_under_roots(tmp_home / "git" / "demo-evil" / "x", roots)


def test_a_relative_path_is_rejected(roots) -> None:
    with pytest.raises(PathEscape):
        resolve_under_roots("src/a.py", roots)


def test_an_empty_path_is_rejected(roots) -> None:
    with pytest.raises(PathEscape):
        resolve_under_roots("", roots)


def test_no_roots_means_nothing_is_allowed(tmp_home: Path) -> None:
    with pytest.raises(PathEscape):
        resolve_under_roots("~/git/demo/src/a.py", [])


def test_a_symlink_leaving_the_roots_is_rejected(roots, tmp_home: Path) -> None:
    (tmp_home / "git" / "demo" / "escape").symlink_to(tmp_home / "secrets")
    with pytest.raises(PathEscape):
        resolve_under_roots("~/git/demo/escape/key", roots)
    with pytest.raises(PathEscape):
        resolve_under_roots("~/git/demo/escape", roots)


def test_a_symlinked_file_leaving_the_roots_is_rejected(roots, tmp_home: Path) -> None:
    (tmp_home / "git" / "demo" / "key").symlink_to(tmp_home / "secrets" / "key")
    with pytest.raises(PathEscape):
        resolve_under_roots("~/git/demo/key", roots)


def test_a_symlink_staying_inside_the_roots_is_allowed(roots, tmp_home: Path) -> None:
    (tmp_home / "git" / "demo" / "inside").symlink_to(tmp_home / "Downloads")
    assert resolve_under_roots("~/git/demo/inside", roots) == tmp_home / "Downloads"


def test_a_root_that_is_itself_a_symlink_still_works(tmp_home: Path) -> None:
    (tmp_home / "real").mkdir()
    (tmp_home / "link").symlink_to(tmp_home / "real")
    (tmp_home / "real" / "f.txt").write_text("x")
    assert resolve_under_roots("~/link/f.txt", [tmp_home / "link"]) == tmp_home / "real" / "f.txt"


# ------------------------------------------------- record compatibility (§7)


def test_a_record_written_before_a_later_field_existed_still_loads(tmp_home: Path) -> None:
    """Records are kept forever (§7); an optional field added later takes its default."""
    spool = Spool()
    job = make(spool)
    path = spool.jobs_dir / f"{job.id}.json"
    data = json.loads(path.read_text())
    del data["playbook_sha256"]
    path.write_text(json.dumps(data))
    assert spool.load_job(job.id).playbook_sha256 is None


def test_a_record_written_before_failure_reason_existed_still_loads(tmp_home: Path) -> None:
    """§23 added `failure_reason`; every record kept from before has none (§7)."""
    spool = Spool()
    job = make(spool)
    path = spool.jobs_dir / f"{job.id}.json"
    data = json.loads(path.read_text())
    del data["failure_reason"]
    path.write_text(json.dumps(data))
    assert spool.load_job(job.id).failure_reason is None


def test_a_record_missing_a_required_field_is_refused(tmp_home: Path) -> None:
    spool = Spool()
    job = make(spool)
    path = spool.jobs_dir / f"{job.id}.json"
    data = json.loads(path.read_text())
    del data["role"]
    path.write_text(json.dumps(data))
    with pytest.raises(SpoolError):
        spool.load_job(job.id)


def test_a_record_with_an_unknown_field_is_refused(tmp_home: Path) -> None:
    spool = Spool()
    job = make(spool)
    path = spool.jobs_dir / f"{job.id}.json"
    data = json.loads(path.read_text())
    data["mood"] = "cheerful"
    path.write_text(json.dumps(data))
    with pytest.raises(SpoolError):
        spool.load_job(job.id)
