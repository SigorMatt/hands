"""U2: the fake claude and the runner (DESIGN §2, §5 job fields, §6, §13).

Every test drives `tests/fake_claude.py` through `runner.claude` in the config;
no test needs the real binary.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
from pathlib import Path

import pytest

from hands.config import Config, parse_config
from hands.runner import (
    KeepRefused,
    Runner,
    RunnerError,
    extract_verdict,
    project_dir_name,
    reconcile_orphans,
    transcript_path_for,
)
from hands.spool import Job, Spool

FAKE = Path(__file__).with_name("fake_claude.py")


# ------------------------------------------------------------------ fixtures


@pytest.fixture
def workdir(tmp_path: Path) -> Path:
    d = tmp_path / "work"
    d.mkdir()
    return d


@pytest.fixture
def cfg(tmp_home: Path, workdir: Path) -> Config:
    data = {
        "roles": {"builder": {"cwd": str(workdir), "model": "opus"}},
        "runner": {"claude": str(FAKE), "cancel_grace_s": 0.2},
    }
    return parse_config(data, project="demo", path=tmp_home / ".hands" / "demo.toml")


@pytest.fixture
def spool(tmp_home: Path) -> Spool:
    return Spool(tmp_home / ".hands")


@pytest.fixture
def runner(cfg: Config, spool: Spool) -> Runner:
    return Runner(cfg, spool)


def send(runner: Runner, spool: Spool, prompt: str, *, context: str = "clear") -> Job:
    job = spool.create_job(role="builder", context=context, prompt=prompt, origin="cli")
    return asyncio.run(runner.run(job))


# ------------------------------------------------------- the §2 invocation


def test_clear_job_runs_and_records_the_whole_record(runner: Runner, spool: Spool) -> None:
    job = send(runner, spool, "FAKE:result done\nFAKE:turns 4\nFAKE:cost 0.25\nFAKE:duration 4242")

    assert job.state == "done"
    assert job.exit_code == 0
    assert job.session_id
    assert job.pid and isinstance(job.pid, int)
    assert job.result == "done"
    assert job.num_turns == 4
    assert job.total_cost_usd == 0.25
    assert job.duration_ms == 4242
    assert job.started and job.ended
    # persisted, not just returned
    assert spool.load_job(job.id).state == "done"


def test_clear_invocation_has_the_design_flags_and_no_resume(
    runner: Runner, spool: Spool
) -> None:
    job = send(runner, spool, "FAKE:result ok")
    argv = runner.last_argv[job.id]
    assert argv[0] == str(FAKE)
    assert "-p" in argv
    assert argv[argv.index("--output-format") + 1] == "stream-json"
    assert "--verbose" in argv
    assert argv[argv.index("--model") + 1] == "opus"
    assert argv[argv.index("--permission-prompts") + 1] == "none"
    assert "--resume" not in argv


def test_permission_flags_from_config_are_passed_through(
    tmp_home: Path, workdir: Path, spool: Spool
) -> None:
    cfg = parse_config(
        {
            "roles": {
                "builder": {
                    "cwd": str(workdir),
                    "permission_flags": "--dangerously-skip-permissions",
                }
            },
            "runner": {"claude": str(FAKE)},
        },
        project="demo",
        path=tmp_home / ".hands" / "demo.toml",
    )
    runner = Runner(cfg, spool)
    job = send(runner, spool, "FAKE:result ok")
    assert "--dangerously-skip-permissions" in runner.last_argv[job.id]


def test_the_prompt_arrives_on_stdin(runner: Runner, spool: Spool) -> None:
    # The fake only sees the control line if it was fed the prompt on stdin.
    job = send(runner, spool, "some work to do\nFAKE:result from-stdin")
    assert job.result == "from-stdin"


# ------------------------------------------------------------ clear vs keep


def test_keep_resumes_the_roles_last_session(runner: Runner, spool: Spool) -> None:
    first = send(runner, spool, "FAKE:session sess-1\nFAKE:result one")
    assert first.session_id == "sess-1"
    assert spool.read_role("builder").last_session_id == "sess-1"

    second = send(runner, spool, "FAKE:result two", context="keep")
    argv = runner.last_argv[second.id]
    assert argv[argv.index("--resume") + 1] == "sess-1"
    assert second.session_id == "sess-1"


def test_keep_is_refused_when_the_role_has_no_session(runner: Runner, spool: Spool) -> None:
    job = spool.create_job(role="builder", context="keep", prompt="x", origin="cli")
    with pytest.raises(KeepRefused):
        asyncio.run(runner.run(job))
    # The job is untouched: a refused keep never ran.
    assert spool.load_job(job.id).state == "queued"


def test_keep_is_refused_while_the_sessions_last_job_is_not_terminal(
    runner: Runner, spool: Spool
) -> None:
    running = spool.create_job(role="builder", context="clear", prompt="x", origin="cli")
    spool.transition(running, "running", session_id="sess-live", pid=os.getpid())
    spool.set_last_session("builder", session_id="sess-live", job_id=running.id)

    job = spool.create_job(role="builder", context="keep", prompt="y", origin="cli")
    with pytest.raises(KeepRefused):
        asyncio.run(runner.run(job))


def test_a_finished_job_makes_its_session_resumable(runner: Runner, spool: Spool) -> None:
    send(runner, spool, "FAKE:session sess-a\nFAKE:result ok")
    assert runner.resolve_resume_session("builder") == "sess-a"


# ----------------------------------------------------------- verbatim result


def test_result_is_stored_verbatim(runner: Runner, spool: Spool) -> None:
    text = "line one\n  indented\n\ntrailing spaces   \nunicode: — é \U0001f600"
    escaped = text.replace("\\", "\\\\").replace("\n", "\\n")
    job = send(runner, spool, f"FAKE:result {escaped}")
    assert job.result == text


# ------------------------------------------------------------------ verdict


def test_verdict_is_the_first_line_matching_the_prefix(runner: Runner, spool: Spool) -> None:
    job = send(runner, spool, "FAKE:result intro\\nVERDICT: PASS\\nVERDICT: LATER\\ntail")
    assert job.verdict == "VERDICT: PASS"


def test_verdict_is_null_when_no_line_matches(runner: Runner, spool: Spool) -> None:
    job = send(runner, spool, "FAKE:result nothing here\\n  VERDICT: indented does not count")
    assert job.verdict is None


@pytest.mark.parametrize(
    ("result", "expected"),
    [
        ("VERDICT: ok", "VERDICT: ok"),
        ("a\nVERDICT:ok\n", "VERDICT:ok"),
        ("no verdict", None),
        ("", None),
        (None, None),
        ("x VERDICT: no", None),
    ],
)
def test_extract_verdict(result: str | None, expected: str | None) -> None:
    assert extract_verdict(result) == expected


# ------------------------------------------------------------------- limits


def test_a_rate_limit_retry_event_makes_the_job_limited(runner: Runner, spool: Spool) -> None:
    job = send(runner, spool, "FAKE:rate-limit slow down")
    assert job.state == "limited"
    assert job.limit is not None
    assert job.limit["category"] == "rate_limit"
    assert "rate_limit" in job.limit["message"]
    # Reset-time parsing is U5's, not this unit's.
    assert job.limit["reset_at"] is None


def test_a_limit_notice_in_the_result_makes_the_job_limited(runner: Runner, spool: Spool) -> None:
    job = send(runner, spool, "FAKE:result Usage limit reached. Try later.")
    assert job.state == "limited"
    assert job.limit is not None
    assert job.limit["message"] == "Usage limit reached. Try later."
    assert job.result == "Usage limit reached. Try later."


def test_an_ordinary_result_is_not_limited(runner: Runner, spool: Spool) -> None:
    job = send(runner, spool, "FAKE:result all good, no limits in sight")
    assert job.state == "done"
    assert job.limit is None


# ------------------------------------------------------------------ failure


def test_a_nonzero_exit_without_a_result_fails(runner: Runner, spool: Spool) -> None:
    job = send(runner, spool, "FAKE:no-result\nFAKE:exit 7")
    assert job.state == "failed"
    assert job.exit_code == 7


def test_an_error_result_fails_and_stderr_tail_is_kept(runner: Runner, spool: Spool) -> None:
    job = send(runner, spool, "FAKE:error boom\nFAKE:stderr trouble here")
    assert job.state == "failed"
    assert job.stderr_tail is not None
    assert "trouble here" in job.stderr_tail


def test_stderr_tail_keeps_only_the_last_50_lines(runner: Runner, spool: Spool) -> None:
    lines = "\\n".join(f"line{n}" for n in range(80))
    job = send(runner, spool, f"FAKE:stderr {lines}\nFAKE:result ok")
    assert job.stderr_tail is not None
    tail = job.stderr_tail.splitlines()
    assert len(tail) == 50
    assert tail[0] == "line30"
    assert tail[-1] == "line79"


def test_a_missing_claude_binary_fails_the_job(
    tmp_home: Path, workdir: Path, spool: Spool
) -> None:
    cfg = parse_config(
        {
            "roles": {"builder": {"cwd": str(workdir)}},
            "runner": {"claude": str(tmp_home / "no-such-claude")},
        },
        project="demo",
        path=tmp_home / ".hands" / "demo.toml",
    )
    runner = Runner(cfg, spool)
    job = send(runner, spool, "FAKE:result ok")
    assert job.state == "failed"
    assert job.stderr_tail is not None


def test_non_json_lines_in_the_stream_are_ignored(runner: Runner, spool: Spool) -> None:
    job = send(runner, spool, "FAKE:junk not json at all\nFAKE:result ok")
    assert job.state == "done"
    assert job.result == "ok"


def test_a_prompt_over_the_10mb_cap_is_refused(runner: Runner, spool: Spool) -> None:
    job = spool.create_job(role="builder", context="clear", prompt="x" * (10 * 1024 * 1024 + 1),
                           origin="cli")
    with pytest.raises(RunnerError):
        asyncio.run(runner.run(job))
    assert spool.load_job(job.id).state == "queued"


# ----------------------------------------------------------- cancel / killed


def test_cancel_sigints_the_process_and_the_job_is_killed(runner: Runner, spool: Spool) -> None:
    async def scenario() -> Job:
        job = spool.create_job(role="builder", context="clear", prompt="FAKE:block",
                               origin="cli")
        task = asyncio.create_task(runner.run(job))
        await runner.wait_for_session(job.id, timeout=10)
        assert await runner.cancel(job.id)
        return await task

    job = asyncio.run(scenario())
    assert job.state == "killed"
    assert job.exit_code == 130  # SIGINT


def test_cancel_escalates_to_sigterm_after_the_grace(runner: Runner, spool: Spool) -> None:
    async def scenario() -> Job:
        job = spool.create_job(
            role="builder", context="clear", prompt="FAKE:block\nFAKE:ignore-int", origin="cli"
        )
        task = asyncio.create_task(runner.run(job))
        await runner.wait_for_session(job.id, timeout=10)
        assert await runner.cancel(job.id)
        return await task

    job = asyncio.run(scenario())
    assert job.state == "killed"
    assert job.exit_code == 143  # SIGTERM


def test_cancelling_an_unknown_job_is_a_no_op(runner: Runner) -> None:
    assert asyncio.run(runner.cancel("nope")) is False


# ------------------------------------------------------------------- git heads


def test_heads_are_recorded_when_the_cwd_is_a_git_repo(
    tmp_home: Path, tmp_path: Path, spool: Spool
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@e",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@e",
    }
    subprocess.run(["git", "init", "-q", str(repo)], check=True, env=env)
    (repo / "a").write_text("1")
    subprocess.run(["git", "-C", str(repo), "add", "a"], check=True, env=env)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "one"], check=True, env=env)
    head = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()

    cfg = parse_config(
        {"roles": {"builder": {"cwd": str(repo)}}, "runner": {"claude": str(FAKE)}},
        project="demo",
        path=tmp_home / ".hands" / "demo.toml",
    )
    job = send(Runner(cfg, spool), spool, "FAKE:result ok")
    assert job.head_at_start == head
    assert job.head_at_end == head


def test_heads_are_null_outside_a_git_repo(runner: Runner, spool: Spool) -> None:
    job = send(runner, spool, "FAKE:result ok")
    assert job.head_at_start is None
    assert job.head_at_end is None


# --------------------------------------------------------- permission denials


def test_permission_denials_are_carried_over(runner: Runner, spool: Spool) -> None:
    job = send(runner, spool, "FAKE:result ok\nFAKE:denial Bash\nFAKE:denial Edit")
    assert [d["tool_name"] for d in job.permission_denials] == ["Bash", "Edit"]


# ------------------------------------------------------------ transcript path


def test_project_dir_name_matches_the_observed_naming() -> None:
    # Evidence: ~/.claude/projects on this machine, each dir checked against the
    # `cwd` recorded inside its own transcripts (see FINDINGS H-001).
    assert project_dir_name("/home/msi/git/hands") == "-home-msi-git-hands"
    assert project_dir_name("/home/msi/git_2/flying_squirrel") == "-home-msi-git-2-flying-squirrel"
    assert project_dir_name("/home/msi/Downloads/weaveviz") == "-home-msi-Downloads-weaveviz"
    assert (
        project_dir_name("/tmp/claude-1000/-home-msi-git-agile-skills/x/scratchpad")
        == "-tmp-claude-1000--home-msi-git-agile-skills-x-scratchpad"
    )


def test_transcript_path_is_derived_not_required_to_exist(tmp_home: Path) -> None:
    path = transcript_path_for("/home/msi/git/hands", "abc-123")
    assert path == str(tmp_home / ".claude/projects/-home-msi-git-hands/abc-123.jsonl")
    assert not Path(path).exists()


def test_the_job_carries_the_derived_transcript_path(
    runner: Runner, spool: Spool, workdir: Path, tmp_home: Path
) -> None:
    job = send(runner, spool, "FAKE:session sess-t\nFAKE:result ok")
    expected = str(
        tmp_home / ".claude/projects" / project_dir_name(workdir) / "sess-t.jsonl"
    )
    assert job.transcript_path == expected


# ---------------------------------------------------------------- orphaned


def _dead_pid() -> int:
    proc = subprocess.Popen(["true"])
    proc.wait()
    return proc.pid


def test_a_running_job_whose_pid_is_gone_becomes_orphaned(spool: Spool) -> None:
    job = spool.create_job(role="builder", context="clear", prompt="x", origin="cli")
    spool.transition(job, "running", pid=_dead_pid(), session_id="sess-x")

    orphans = reconcile_orphans(spool)

    assert [o.id for o in orphans] == [job.id]
    after = spool.load_job(job.id)
    assert after.state == "orphaned"
    assert after.session_id == "sess-x"  # §3: "marked orphaned with its session id"
    assert after.ended
    assert [e.kind for e in spool.events()] == ["job.orphaned"]


def test_reconcile_leaves_a_live_pid_alone(spool: Spool) -> None:
    job = spool.create_job(role="builder", context="clear", prompt="x", origin="cli")
    spool.transition(job, "running", pid=os.getpid())
    assert reconcile_orphans(spool) == []
    assert spool.load_job(job.id).state == "running"


def test_reconcile_orphans_a_running_job_with_no_pid(spool: Spool) -> None:
    job = spool.create_job(role="builder", context="clear", prompt="x", origin="cli")
    spool.transition(job, "running")
    assert [o.id for o in reconcile_orphans(spool)] == [job.id]


def test_reconcile_ignores_terminal_and_queued_jobs(spool: Spool) -> None:
    spool.create_job(role="builder", context="clear", prompt="x", origin="cli")
    done = spool.create_job(role="builder", context="clear", prompt="y", origin="cli")
    spool.transition(done, "running", pid=_dead_pid())
    spool.transition(done, "done")
    assert reconcile_orphans(spool) == []


# -------------------------------------------------------------- inbox events


@pytest.mark.parametrize(
    ("prompt", "kind"),
    [
        ("FAKE:result ok", "job.done"),
        ("FAKE:no-result\nFAKE:exit 3", "job.failed"),
        ("FAKE:rate-limit nope", "job.limited"),
    ],
)
def test_a_terminal_state_writes_one_inbox_event(
    runner: Runner, spool: Spool, prompt: str, kind: str
) -> None:
    job = send(runner, spool, prompt)
    events = spool.events()
    assert [e.kind for e in events] == [kind]
    assert events[0].payload["job"] == job.id
    assert events[0].payload["role"] == "builder"


def test_is_running_tracks_the_process(runner: Runner, spool: Spool) -> None:
    async def scenario() -> None:
        job = spool.create_job(role="builder", context="clear", prompt="FAKE:block", origin="cli")
        assert not runner.is_running(job.id)
        task = asyncio.create_task(runner.run(job))
        await runner.wait_until_running(job.id, timeout=10)
        assert runner.is_running(job.id)
        await runner.cancel(job.id)
        await task
        assert not runner.is_running(job.id)

    asyncio.run(scenario())
