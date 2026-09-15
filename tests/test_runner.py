"""U2: the fake claude and the runner (DESIGN §2, §5 job fields, §6, §13).

Every test drives `tests/fake_claude.py` through `runner.claude` in the config;
no test needs the real binary.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import signal
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

import pytest

from conftest import kill_quietly, process_live, strip_paths
from hands.config import Config, parse_config
from hands.limits import from_iso
from hands.monitor import group_pids
from hands.runner import (
    GROUP,
    JOB_ENV,
    MAX_LAST_ARGV,
    SCOPE,
    KeepRefused,
    Runner,
    RunnerError,
    _kill_group,
    extract_verdict,
    is_harness_termination,
    probe_isolation,
    project_dir_name,
    reconcile_orphans,
    spawn_argv,
    transcript_path_for,
    unit_name,
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
    assert job.failure_reason is None  # §23: null for every job that is not failed
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
    assert "rate_limit" in strip_paths(job.limit["message"])
    # "slow down" names no reset time, and U5's parser does not invent one.
    assert job.limit["reset_at"] is None


def test_a_limit_notice_in_the_result_makes_the_job_limited(runner: Runner, spool: Spool) -> None:
    job = send(runner, spool, "FAKE:result Usage limit reached. Try later.")
    assert job.state == "limited"
    assert job.limit is not None
    assert job.limit["message"] == "Usage limit reached. Try later."
    assert job.result == "Usage limit reached. Try later."


def test_a_widened_limit_notice_is_detected_and_its_reset_time_parsed(
    runner: Runner, spool: Spool
) -> None:
    """U5 widened the notice shapes the runner accepts, and fills `reset_at` (§6)."""
    notice = "Rate limit exceeded - try again in 45 minutes"
    job = send(runner, spool, f"FAKE:result {notice}")
    assert job.state == "limited"
    assert job.limit is not None
    assert job.limit["message"] == notice  # raw, never normalised
    parsed = from_iso(job.limit["reset_at"])
    assert parsed is not None
    ahead = (parsed - datetime.now(UTC)).total_seconds()
    assert 44 * 60 < ahead <= 45 * 60


def test_a_reset_time_in_the_retry_event_reaches_the_record(
    runner: Runner, spool: Spool
) -> None:
    job = send(runner, spool, "FAKE:rate-limit usage limit reached, try again in 30 minutes")
    assert job.state == "limited"
    assert job.limit is not None
    assert from_iso(job.limit["reset_at"]) is not None


def test_an_ordinary_result_is_not_limited(runner: Runner, spool: Spool) -> None:
    job = send(runner, spool, "FAKE:result all good, no limits in sight")
    assert job.state == "done"
    assert job.limit is None


# ------------------------------------------------------------------ failure


def test_a_nonzero_exit_without_a_result_fails(runner: Runner, spool: Spool) -> None:
    job = send(runner, spool, "FAKE:no-result\nFAKE:exit 7")
    assert job.state == "failed"
    assert job.exit_code == 7
    assert job.failure_reason == "no_final_result"


def test_an_error_result_fails_and_stderr_tail_is_kept(runner: Runner, spool: Spool) -> None:
    job = send(runner, spool, "FAKE:error boom\nFAKE:stderr trouble here")
    assert job.state == "failed"
    assert job.failure_reason == "error_result"
    assert job.stderr_tail is not None
    assert "trouble here" in strip_paths(job.stderr_tail)


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
    assert job.failure_reason == "spawn_error"


# ------------------------------------------ harness termination (§2, §6, §23, H-014)

#: The line claude 2.1.x writes when its bg-wait ceiling ends a `-p` process,
#: verbatim from job 0mtygi953-ym63's stderr_tail (H-014).
TERMINATING = (
    "Background tasks still running after 600s; terminating. "
    "Set CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0 to wait indefinitely."
)
#: That job's `result`: a progress note, not a report.
MID_MISSION_NOTE = (
    "U0–U5 are committed and pushed; the U5 follow-up is running now. "
    "I'll continue with U6 and U7 when it reports back."
)


def test_the_exact_shape_of_job_0mtygi953_is_failed_harness_terminated(
    runner: Runner, spool: Spool
) -> None:
    """H-014's record: a final success result, num_turns 59, exit 0 — and the
    terminating line. DESIGN v3.8 §6: "a cancel stays `killed` and a limit stays
    `limited`; otherwise the termination line wins even over a `success` result"
    (FINAL-REPORT-8 §5 item 1). Mission 8 pinned this shape `done`; v3.8 reverses
    that back to mission 7a's reading.
    """
    job = send(
        runner,
        spool,
        f"FAKE:stderr {TERMINATING}\nFAKE:result {MID_MISSION_NOTE}\nFAKE:turns 59\nFAKE:exit 0",
    )
    assert job.exit_code == 0
    assert job.num_turns == 59
    assert job.result == MID_MISSION_NOTE
    assert job.state == "failed"
    assert job.failure_reason == "harness_terminated"
    assert job.stderr_tail is not None and TERMINATING in strip_paths(job.stderr_tail)
    assert spool.load_job(job.id).failure_reason == "harness_terminated"
    assert [event.kind for event in spool.events()] == ["job.failed"]


@pytest.mark.parametrize(
    "missing",
    [
        "FAKE:no-turns",  # a success result, exit 0, no num_turns
        "FAKE:exit 3",  # a success result with turns, exit non-zero
        "FAKE:subtype error_during_execution",  # a result that is not `success`
        "FAKE:error stopped",  # an error result
        "FAKE:no-result",  # no result event at all
    ],
    ids=["no-turns", "nonzero-exit", "not-success-subtype", "error-result", "no-result"],
)
def test_the_terminating_line_fails_a_job_missing_any_of_success_turns_and_exit_0(
    runner: Runner, spool: Spool, missing: str
) -> None:
    """§6: the line wins over every other failure too; with any one of success,
    turns or exit 0 taken away the recorded reason is still `harness_terminated`
    (the full shape is the test above)."""
    job = send(runner, spool, f"FAKE:stderr {TERMINATING}\nFAKE:result a note\n{missing}")
    assert job.state == "failed"
    assert job.failure_reason == "harness_terminated"


#: Review 7 should-fix 2, verbatim: the two lines the unanchored matcher took.
REVIEW_7_OVER_MATCHES = (
    "background tasks still running after 3 retries; terminating the loop",
    "grep said: Background tasks still running after 600s; terminating.",
)


@pytest.mark.parametrize("line", REVIEW_7_OVER_MATCHES)
def test_review_7s_over_match_lines_do_not_set_the_failure_reason(
    runner: Runner, spool: Spool, line: str
) -> None:
    """On a run that fails for another reason, the review's lines are not read as
    the harness's: the reason is the one the run itself earns."""
    job = send(runner, spool, f"FAKE:stderr {line}\nFAKE:no-result")
    assert job.state == "failed"
    assert job.failure_reason == "no_final_result"


@pytest.mark.parametrize("line", REVIEW_7_OVER_MATCHES)
def test_review_7s_over_match_lines_leave_a_successful_job_done(
    runner: Runner, spool: Spool, line: str
) -> None:
    """The line beats a `success` result only in its exact shape (§6): a success
    result with turns and exit 0 whose stderr carries a look-alike stays `done`."""
    job = send(runner, spool, f"FAKE:stderr {line}\nFAKE:result fin\nFAKE:turns 59\nFAKE:exit 0")
    assert job.state == "done"
    assert job.failure_reason is None


def test_a_mid_turn_exit_with_no_result_event_is_failed(runner: Runner, spool: Spool) -> None:
    """Assistant events, then the process ends with exit 0 and no `result` (§23)."""
    job = send(runner, spool, "FAKE:events 3\nFAKE:no-result\nFAKE:exit 0")
    assert job.exit_code == 0
    assert job.session_id
    assert job.state == "failed"
    assert job.failure_reason == "no_final_result"


def test_a_clean_exit_stays_done_with_no_failure_reason(runner: Runner, spool: Spool) -> None:
    job = send(runner, spool, "FAKE:events 3\nFAKE:stderr an ordinary warning\nFAKE:result fin")
    assert job.state == "done"
    assert job.failure_reason is None
    assert job.num_turns == 1


def test_a_result_without_num_turns_is_failed(runner: Runner, spool: Spool) -> None:
    job = send(runner, spool, "FAKE:result looks finished\nFAKE:no-turns")
    assert job.exit_code == 0
    assert job.num_turns is None
    assert job.state == "failed"
    assert job.failure_reason == "no_num_turns"


@pytest.mark.parametrize("subtype", ["progress", "success_partial", ""], ids=repr)
def test_a_result_whose_subtype_is_not_success_or_error_is_not_a_final_result(
    runner: Runner, spool: Spool, subtype: str
) -> None:
    """`""` is the event with no subtype key at all (fake_claude's bare FAKE:subtype)."""
    job = send(runner, spool, f"FAKE:result ok\nFAKE:subtype {subtype}".rstrip())
    assert job.state == "failed"
    assert job.failure_reason == "no_final_result"


@pytest.mark.parametrize(
    "subtype", ["error_during_execution", "error_max_turns", "error_max_budget_usd"]
)
def test_an_error_subtype_is_a_final_result_and_fails_as_an_error(
    runner: Runner, spool: Spool, subtype: str
) -> None:
    """The error family of claude 2.1.x's result subtypes counts as §23's `error`."""
    job = send(runner, spool, f"FAKE:error stopped\nFAKE:subtype {subtype}")
    assert job.state == "failed"
    assert job.failure_reason == "error_result"


@pytest.mark.parametrize("subtype", ["error", "error_max_turns", "error_during_execution"])
def test_an_error_subtype_fails_as_an_error_even_when_is_error_is_false(
    runner: Runner, spool: Spool, subtype: str
) -> None:
    """§6 (REVIEW-9 should-fix 2, H-018 gap 3): the subtype decides, not `is_error`.
    FAKE:subtype without FAKE:error emits `is_error: false`, `num_turns` and exit 0."""
    job = send(runner, spool, f"FAKE:result partial\nFAKE:subtype {subtype}")
    events = [json.loads(line) for line in spool.stream_path(job.id).read_text().splitlines()]
    final = [event for event in events if event.get("type") == "result"]
    assert [(e["subtype"], e["is_error"]) for e in final] == [(subtype, False)]
    assert (job.exit_code, job.num_turns) == (0, 1)
    assert job.state == "failed"
    assert job.failure_reason == "error_result"


def test_a_success_result_with_a_nonzero_exit_is_failed_nonzero_exit(
    runner: Runner, spool: Spool
) -> None:
    job = send(runner, spool, "FAKE:result ok\nFAKE:exit 3")
    assert job.state == "failed"
    assert job.failure_reason == "nonzero_exit"


def test_the_terminating_line_wins_over_every_other_failure_reason(
    runner: Runner, spool: Spool
) -> None:
    job = send(runner, spool, f"FAKE:stderr {TERMINATING}\nFAKE:events 2\nFAKE:no-result")
    assert job.state == "failed"
    assert job.failure_reason == "harness_terminated"


def test_a_limit_wins_over_the_terminating_line(runner: Runner, spool: Spool) -> None:
    """Decided (U1): `limited`, not `failed`. §6 owns the limit resume and waits out
    the reset; a `failed` here would hand the playbook a `builder.failed → resume`
    that sends a job straight back into the same limit (H-005)."""
    retry = send(runner, spool, f"FAKE:stderr {TERMINATING}\nFAKE:rate-limit slow down")
    assert retry.state == "limited"
    assert retry.failure_reason is None
    notice = send(
        runner,
        spool,
        f"FAKE:stderr {TERMINATING}\nFAKE:result Usage limit reached. Try later.",
    )
    assert notice.state == "limited"
    assert notice.failure_reason is None


def test_a_cancel_wins_over_the_terminating_line(runner: Runner, spool: Spool) -> None:
    async def scenario() -> Job:
        job = spool.create_job(
            role="builder",
            context="clear",
            prompt=f"FAKE:stderr {TERMINATING}\nFAKE:block",
            origin="cli",
        )
        task = asyncio.create_task(runner.run(job))
        await runner.wait_for_session(job.id)
        await runner.cancel(job.id)
        return await task

    job = asyncio.run(scenario())
    assert job.state == "killed"
    assert job.failure_reason is None


@pytest.mark.parametrize(
    "line",
    [
        TERMINATING,
        "Background tasks still running after 1200s; terminating. "
        "Set CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0 to wait indefinitely.",
        "Background tasks still running after 0s; terminating. "
        "Set CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0 to wait indefinitely.",
    ],
)
def test_the_terminating_line_is_matched_by_its_exact_shape(line: str) -> None:
    """The harness's message, one line (claude 2.1.270 writes it as one string):
    line start, digits, the `s;` unit, and the `Set …_CEILING_MS` tail."""
    assert is_harness_termination(line)


@pytest.mark.parametrize(
    "line",
    [
        *REVIEW_7_OVER_MATCHES,
        # Missing tail: the message without its `Set …` sentence.
        "Background tasks still running after 5s; terminating.",
        # H-014's display wrap: the tail on the next line is not on this one.
        "Background tasks still running after 600s; terminating. Set",
        # Leading text: whitespace, a terminal colour code, a quoting prefix.
        " " + TERMINATING,
        "\x1b[33m" + TERMINATING,
        "stderr: " + TERMINATING,
        # Wrong unit, a spaced unit, a non-integer count.
        TERMINATING.replace("600s;", "600ms;"),
        TERMINATING.replace("600s;", "600 s;"),
        TERMINATING.replace("600s;", "1.5s;"),
        TERMINATING.replace("600s;", "s;"),
        # Case and wording: the harness's text is matched as it is written.
        TERMINATING.lower(),
        TERMINATING.replace("tasks", "task"),
        TERMINATING.replace("terminating.", "Terminating."),
        TERMINATING.replace("CEILING_MS", "CEILING"),
        "  background tasks still running after 90 s; Terminating",
        "Background tasks still running after 600s; waiting.",
        "terminating",
        "the builder is terminating the U5 follow-up",
        "Set CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0 to wait indefinitely.",
        "",
    ],
)
def test_a_line_without_that_shape_is_not_a_termination(line: str) -> None:
    assert not is_harness_termination(line)


# --------------------------------------------------- the role environment (§23)

CEILING = "CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS"


def test_the_bg_wait_ceiling_reaches_the_process_as_0_by_default(
    runner: Runner, spool: Spool, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Even when the daemon's own environment carries a ceiling: the config did not
    set one, so the role job gets `0` (§23)."""
    monkeypatch.setenv(CEILING, "600000")
    monkeypatch.setenv("HANDS_TEST_INHERITED", "kept")
    assert send(runner, spool, f"FAKE:env {CEILING}").result == "0"
    # the rest of the daemon's environment is still inherited
    assert send(runner, spool, "FAKE:env HANDS_TEST_INHERITED").result == "kept"


def test_a_configured_role_env_wins_and_reaches_the_process(
    tmp_home: Path, workdir: Path, spool: Spool, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(CEILING, "600000")
    cfg = parse_config(
        {
            "roles": {
                "builder": {
                    "cwd": str(workdir),
                    "env": {CEILING: "1800000", "HANDS_ROLE_EXTRA": "yes"},
                }
            },
            "runner": {"claude": str(FAKE)},
        },
        project="demo",
        path=tmp_home / ".hands" / "demo.toml",
    )
    runner = Runner(cfg, spool)
    assert send(runner, spool, f"FAKE:env {CEILING}").result == "1800000"
    assert send(runner, spool, "FAKE:env HANDS_ROLE_EXTRA").result == "yes"


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


# ------------------------------------------------- the stream is a file (§21)

#: The gate of DESIGN §21: a transcript far larger than any real mission.
HUGE = 200_000


def test_the_stream_is_written_to_the_job_log_file_as_it_arrives(
    runner: Runner, spool: Spool
) -> None:
    """§7's captured stream is a file the runner appends to, line by line."""
    job = send(runner, spool, "FAKE:junk not json\nFAKE:result written")

    path = spool.stream_path(job.id)
    lines = path.read_text(encoding="utf-8").splitlines()
    kinds = [json.loads(line).get("type") for line in lines if line.startswith("{")]
    assert kinds == ["system", "result"]
    # Verbatim, including a line that is not an event at all (§7).
    assert lines.count("not json") == 1


def test_a_huge_stream_is_never_retained_by_the_runner(runner: Runner, spool: Spool) -> None:
    """§21: 200 000 events on disk, and nothing per-event in the runner.

    The design's claim is about resident size, but RSS is a property of the
    machine, not of the code: what is asserted here is the *length* of every
    structure the runner keeps. Each is one-per-job or empty while a job with
    200 000 events in its log is running, so none of them can grow with a
    transcript. The counts are read mid-run, which is where the 959 MB of §21
    was observed — not after the process is gone.
    """

    async def scenario() -> Job:
        job = spool.create_job(
            role="builder",
            context="clear",
            prompt=f"FAKE:events {HUGE}\nFAKE:block",
            origin="cli",
        )
        task = asyncio.create_task(runner.run(job))
        await runner.wait_for_session(job.id, timeout=60)
        path = spool.stream_path(job.id)
        deadline = time.monotonic() + 120
        while path.read_bytes().count(b"\n") <= HUGE:  # init + HUGE events
            assert time.monotonic() < deadline, "the stream never reached the whole run"
            await asyncio.sleep(0.02)
        assert runner.retained() == {
            "cancelled": 0,
        "isolated": 1,
            "last_argv": 1,
            "logs": 1,
            "procs": 1,
            "running": 1,
            "session_ready": 1,
        }
        await runner.cancel(job.id)
        return await task

    job = asyncio.run(scenario())

    assert job.state == "killed"
    # Everything per-job is released with the job; `last_argv` keeps the last few.
    assert runner.retained() == {
        "cancelled": 0,
        "isolated": 0,
        "last_argv": 1,
        "logs": 0,
        "procs": 0,
        "running": 0,
        "session_ready": 0,
    }
    assert spool.stream_path(job.id).read_bytes().count(b"\n") > HUGE


def test_last_argv_is_bounded_and_retained_names_what_it_does_not_count(
    runner: Runner, spool: Spool
) -> None:
    """§21 (review 5 should-fix 3): every count `retained()` reports is bounded.

    `_procs`, `_running`, `_session_ready` and `_logs` are popped when a run
    ends; `last_argv` never was, so the daemon held one argv list per job for
    the rest of its life while the method's docstring said every count was
    "bounded by the number of jobs in flight". The cap is what makes that
    sentence true, and the docstring now also names the three things the method
    does *not* count, so its number is not read as "everything the runner holds".
    """
    jobs = [send(runner, spool, "FAKE:result ok") for _ in range(MAX_LAST_ARGV + 3)]

    assert runner.retained()["last_argv"] == MAX_LAST_ARGV
    # Which ones: the newest `MAX_LAST_ARGV`, the three oldest dropped.
    assert sorted(runner.last_argv) == sorted(job.id for job in jobs[3:])

    doc = Runner.retained.__doc__ or ""
    for unreported in ("_Parsed.result", "stderr", "reader"):
        assert unreported in strip_paths(doc), f"the docstring calls {unreported!r} counted"


def test_the_final_result_is_the_only_event_kept_after_a_huge_run(
    runner: Runner, spool: Spool
) -> None:
    """§21's other half: of 200 000 events, the record keeps the last one's text."""
    job = send(runner, spool, f"FAKE:events {HUGE}\nFAKE:result the last word")

    assert job.state == "done"
    assert job.result == "the last word"
    assert spool.stream_path(job.id).read_bytes().count(b"\n") == HUGE + 2


# ------------------------------------------ per-job isolation (§24, backlog 2)


def test_a_unit_name_is_hands_project_job_with_only_safe_characters() -> None:
    assert unit_name("demo", "0mtygi953-ym63") == "hands-demo-0mtygi953-ym63"
    assert unit_name("my proj.é/x", "j:1@2") == "hands-my_proj___x-j_1_2"
    long = unit_name("p" * 300, "0mtygi953-ym63")
    assert long == "hands-" + "p" * 64 + "-0mtygi953-ym63"
    assert re.fullmatch(r"[A-Za-z0-9_-]+", long)


def test_scope_mode_wraps_the_invocation_and_group_mode_does_not() -> None:
    argv = ["claude", "-p", "--output-format", "stream-json"]
    assert spawn_argv(argv, project="demo", job_id="j1", isolation=SCOPE) == [
        "systemd-run", "--user", "--scope", "--quiet", "--unit", "hands-demo-j1", "--", *argv
    ]
    assert spawn_argv(argv, project="demo", job_id="j1", isolation=GROUP) == argv


def cgroup_v2(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "cgroup.controllers").write_text("cpu memory pids\n")
    return root


def test_the_probe_picks_a_scope_only_when_systemd_run_starts_one(tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def answers(code: int):  # noqa: ANN202 - builds a fake subprocess.run
        def fake(argv: list[str], **_kw: object) -> subprocess.CompletedProcess[str]:
            calls.append(argv)
            return subprocess.CompletedProcess(argv, code, "", "")

        return fake

    def times_out(argv: list[str], **_kw: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(argv, 1.0)

    found = lambda name: f"/usr/bin/{name}"  # noqa: E731
    v2 = cgroup_v2(tmp_path / "v2")
    assert probe_isolation(which=found, run=answers(0), cgroup_root=v2) == SCOPE
    assert calls[0][:4] == ["systemd-run", "--user", "--scope", "--quiet"]
    assert probe_isolation(which=found, run=answers(1), cgroup_root=v2) == GROUP
    assert probe_isolation(which=found, run=times_out, cgroup_root=v2) == GROUP
    assert probe_isolation(which=lambda name: None, run=answers(0), cgroup_root=v2) == GROUP
    v1 = tmp_path / "v1"
    v1.mkdir()
    assert probe_isolation(which=found, run=answers(0), cgroup_root=v1) == GROUP


def start(runner: Runner, spool: Spool, prompt: str) -> tuple[Job, asyncio.Task[Job]]:
    job = spool.create_job(role="builder", context="clear", prompt=prompt, origin="cli")
    return job, asyncio.create_task(runner.run(job))


async def until(check, what: str, timeout: float = 15.0):  # noqa: ANN001, ANN201
    for _ in range(int(timeout / 0.02)):
        value = check()
        if value:
            return value
        await asyncio.sleep(0.02)
    raise AssertionError(f"timed out waiting for {what}")


def test_group_mode_starts_each_job_as_its_own_process_group(runner: Runner, spool: Spool) -> None:
    async def body() -> None:
        job, task = start(runner, spool, "FAKE:block")
        await runner.wait_for_session(job.id)
        pid = spool.load_job(job.id).pid
        assert pid is not None
        assert os.getpgid(pid) == pid != os.getpgrp()
        assert runner.live_pids(spool.load_job(job.id)) == [pid]
        assert runner.last_argv[job.id][0] == str(FAKE)
        await runner.cancel(job.id)
        assert (await task).state == "killed"

    asyncio.run(asyncio.wait_for(body(), 30))


def test_scope_mode_spawns_through_systemd_run_with_the_unit_name(
    runner: Runner, spool: Spool, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No systemd needed: a `systemd-run` on PATH records its argv and execs the rest."""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    record = tmp_path / "systemd-run.argv"
    (bindir / "systemd-run").write_text(
        "#!/bin/sh\n"
        f'printf "%s\\n" "$@" > "{record}"\n'
        'while [ "$1" != "--" ]; do shift; done\nshift\nexec "$@"\n'
    )
    (bindir / "systemctl").write_text("#!/bin/sh\nexit 0\n")  # the scope is already gone
    for tool in ("systemd-run", "systemctl"):
        (bindir / tool).chmod(0o755)
    monkeypatch.setenv("PATH", f"{bindir}{os.pathsep}{os.environ['PATH']}")
    runner.isolation = SCOPE

    job = send(runner, spool, "FAKE:result scoped")
    assert (job.state, job.result) == ("done", "scoped")
    recorded = record.read_text().splitlines()
    assert recorded[:6] == ["--user", "--scope", "--quiet", "--unit", f"hands-demo-{job.id}", "--"]
    assert recorded[6] == str(FAKE)
    assert runner.last_argv[job.id][:2] == ["systemd-run", "--user"]


def test_a_normal_run_reports_no_orphans(runner: Runner, spool: Spool) -> None:
    seen: list[object] = []
    runner.on_orphans = lambda job, processes, isolation: seen.append(processes)
    assert send(runner, spool, "FAKE:result ok").state == "done"
    assert seen == []


def test_a_cancelled_jobs_orphan_is_reported_and_killed(
    runner: Runner, spool: Spool, tmp_path: Path
) -> None:
    pidfile = tmp_path / "orphan.pid"
    seen: list[tuple[str, list[dict[str, object]]]] = []
    runner.on_orphans = lambda job, processes, isolation: seen.append((job.id, processes))

    def execd() -> bool:
        if not pidfile.exists() or not pidfile.read_text():
            return False
        return Path(f"/proc/{pidfile.read_text()}/cmdline").read_bytes().startswith(b"sleep")

    async def body() -> None:
        job, task = start(runner, spool, f"FAKE:orphan {pidfile}\nFAKE:block")
        await until(execd, "the orphan to exec")
        orphan = int(pidfile.read_text())
        # §29: the orphan is the job's because it started before the last moment
        # claude was observed alive; the runner's poll is what observes it.
        await until(
            lambda: runner._last_seen.get(job.id, 0) > _start_ticks(orphan),
            "claude to be observed alive after the orphan started",
        )
        await runner.cancel(job.id)
        finished = await task
        pid = int(pidfile.read_text())
        assert finished.state == "killed"
        assert seen == [(job.id, [{"pid": pid, "cmdline": "sleep 300", "killed": True}])]
        assert not process_live(pid)

    try:
        asyncio.run(asyncio.wait_for(body(), 30))
    finally:
        if pidfile.exists() and pidfile.read_text():
            kill_quietly(int(pidfile.read_text()))


def _start_ticks(pid: int) -> int:
    """Field 22 of `/proc/<pid>/stat`: the start time, in clock ticks since boot."""
    text = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
    return int(text[text.rindex(")") + 1 :].split()[19])


def _exit_within(proc: subprocess.Popen[bytes], seconds: float) -> int | None:
    try:
        return proc.wait(timeout=seconds)
    except subprocess.TimeoutExpired:
        return None


def _reused_group(runner: Runner, spool: Spool) -> tuple[Job, subprocess.Popen[bytes]]:
    """REVIEW-9 should-fix 1's case: claude was reaped, its pid was free, and a new
    session leader took it, so a group with the job's pid as its id has members
    again. The recorded leader is claude, which started before the new one."""
    other = subprocess.Popen(["sleep", "30"], start_new_session=True)
    job = spool.create_job(role="builder", context="clear", prompt="x", origin="cli")
    job.pid = other.pid
    runner._leader_start = {job.id: _start_ticks(other.pid) - 1}
    return job, other


def test_the_last_resort_leaves_a_reused_group_alone(runner: Runner, spool: Spool) -> None:
    """A membership check cannot tell this group from claude's; the start time can."""
    job, other = _reused_group(runner, spool)
    try:
        runner._last_resort(job, GROUP)
        assert _exit_within(other, 0.5) is None, "the reused group was killed"
    finally:
        other.kill()
        other.wait()


def test_the_sweep_leaves_a_reused_group_alone(runner: Runner, spool: Spool) -> None:
    """The sweep runs after claude is reaped, so it has the same window."""
    job, other = _reused_group(runner, spool)
    seen: list[object] = []
    runner.on_orphans = lambda job, processes, isolation: seen.append(processes)
    try:
        assert asyncio.run(runner._sweep(job, GROUP)) == []
        assert seen == []
        assert _exit_within(other, 0.5) is None, "the reused group was killed"
    finally:
        other.kill()
        other.wait()


def test_the_last_resort_kills_the_group_while_its_leader_is_the_one_spawned(
    runner: Runner, spool: Spool
) -> None:
    leader = subprocess.Popen(["sleep", "30"], start_new_session=True)
    try:
        job = spool.create_job(role="builder", context="clear", prompt="x", origin="cli")
        job.pid = leader.pid
        runner._leader_start = {job.id: _start_ticks(leader.pid)}
        runner._last_resort(job, GROUP)
        assert _exit_within(leader, 5) == -signal.SIGKILL
    finally:
        leader.kill()
        leader.wait()


def _vacated_group(job: Job | None, *, marked: bool = True) -> subprocess.Popen[bytes]:
    """A group whose leader was reaped and whose background sleep lives on. With
    `job`, the group was started in that job's environment (its descendants), with
    its `HANDS_JOB` mark unless `marked` is False (a descendant that cleared it);
    without, it is a stranger's — review 10 should-fix 3's reused-then-vacated
    leader, which no process holds either."""
    unmarked = {name: value for name, value in os.environ.items() if name != JOB_ENV}
    if job is None:
        env = None
    else:
        env = {**unmarked, JOB_ENV: job.id} if marked else unmarked
    leader = subprocess.Popen(
        ["sh", "-c", "sleep 30 & exit 0"], start_new_session=True, env=env
    )
    leader.wait()  # reaped: /proc/<pgid> is gone, the background sleep is not
    return leader


def test_the_last_resort_kills_the_members_of_a_group_whose_leader_was_reaped(
    runner: Runner, spool: Spool
) -> None:
    """No process holds the id; every member is in the session the job's pid led
    and started before the last moment that pid was observed alive (§29), so each
    descends from the job and is killed."""
    job = spool.create_job(role="builder", context="clear", prompt="x", origin="cli")
    leader = _vacated_group(job)
    members = group_pids(leader.pid)
    assert members, "the background sleep should still be in the group"
    try:
        job.pid = leader.pid
        runner._leader_start = {job.id: 1}
        runner._last_seen = {job.id: max(_start_ticks(pid) for pid in members) + 1}
        runner._last_resort(job, GROUP)

        async def gone() -> None:
            await until(lambda: not any(process_live(pid) for pid in members), "members dead", 5)

        asyncio.run(gone())
    finally:
        for pid in members:
            kill_quietly(pid)


@pytest.mark.parametrize("path", ["last_resort", "sweep"])
def test_a_vacated_group_of_strangers_with_the_jobs_pid_as_its_id_is_left_alone(
    runner: Runner, spool: Spool, path: str
) -> None:
    """Review 10 should-fix 3: claude was reaped, a stranger's session leader took
    the pid, forked and was reaped. No process holds the id, but the members are
    not the job's descendants, so neither the sweep nor the last resort signals
    them, and nothing is reported."""
    job = spool.create_job(role="builder", context="clear", prompt="x", origin="cli")
    leader = _vacated_group(None)
    members = group_pids(leader.pid)
    assert members, "the background sleep should still be in the group"
    seen: list[object] = []
    runner.on_orphans = lambda job, processes, isolation: seen.append(processes)
    try:
        job.pid = leader.pid
        runner._leader_start = {job.id: 1}
        if path == "sweep":
            assert asyncio.run(runner._sweep(job, GROUP)) == []
        else:
            runner._last_resort(job, GROUP)
        time.sleep(0.3)
        assert all(process_live(pid) for pid in members), "the stranger's group was killed"
        assert seen == []
    finally:
        for pid in members:
            kill_quietly(pid)


def _foreign_session_group(job: Job) -> subprocess.Popen[bytes]:
    """A leaderless group whose members carry the job's `HANDS_JOB` mark but whose
    session is not the one the job's pid led: its leader joined a new group in
    this test's session (`setpgid`, not `setsid`), forked, and was reaped."""
    leader = subprocess.Popen(
        ["sh", "-c", "sleep 30 & exit 0"],
        process_group=0,
        env={**os.environ, JOB_ENV: job.id},
    )
    leader.wait()
    return leader


@pytest.mark.parametrize("path", ["sweep", "kill_group", "last_resort"])
def test_a_leaderless_marked_group_in_a_foreign_session_is_left_alone(
    runner: Runner, spool: Spool, path: str
) -> None:
    """H-023, §29: the mark is corroboration and never sufficient alone. The group
    id is the job's pid and every member carries the job's mark, but no member is
    in the job's session, so nothing is signalled, whatever the last observation
    says; the sweep reports what it saw with `killed: false`."""
    job = spool.create_job(role="builder", context="clear", prompt="x", origin="cli")
    leader = _foreign_session_group(job)
    members = group_pids(leader.pid)
    assert members, "the background sleep should still be in the group"
    assert all(os.getsid(pid) != leader.pid for pid in members)
    seen: list[object] = []
    runner.on_orphans = lambda job, processes, isolation: seen.append(processes)
    try:
        job.pid = leader.pid
        runner._leader_start = {job.id: 1}
        runner._last_seen = {job.id: 2**62}
        if path == "sweep":
            reported = [{"pid": pid, "cmdline": "sleep 30", "killed": False} for pid in members]
            assert asyncio.run(runner._sweep(job, GROUP)) == reported
            assert seen == [reported]
        elif path == "kill_group":
            asyncio.run(_kill_group(leader.pid, 1, last_seen=2**62, grace=0.2))
        else:
            runner._last_resort(job, GROUP)
        time.sleep(0.3)
        assert all(process_live(pid) for pid in members), "a marked stranger was killed"
    finally:
        for pid in members:
            kill_quietly(pid)


@pytest.mark.parametrize(("after", "killed"), [(0, False), (1, True)],
                         ids=["started-at-the-last-observation", "started-before-it"])
def test_a_session_member_is_the_jobs_only_if_it_started_before_the_last_observation(
    runner: Runner, spool: Spool, after: int, killed: bool
) -> None:
    """§29's residual, at the unit: the member is in the job's session and carries
    its mark. Observed alive in a later clock tick than the member's start, the
    job's pid proves it; observed in the same tick, nothing proves it, and it is
    left alive and reported `killed: false`. (The observation is set here, not
    measured: a fork inside a real job's last poll interval is not constructed.)"""
    job = spool.create_job(role="builder", context="clear", prompt="x", origin="cli")
    leader = _vacated_group(job)
    members = group_pids(leader.pid)
    assert len(members) == 1, "the background sleep should still be in the group"
    member = members[0]
    seen: list[object] = []
    runner.on_orphans = lambda job, processes, isolation: seen.append(processes)
    try:
        job.pid = leader.pid
        runner._leader_start = {job.id: 1}
        runner._last_seen = {job.id: _start_ticks(member) + after}
        reported = [{"pid": member, "cmdline": "sleep 30", "killed": killed}]
        assert asyncio.run(runner._sweep(job, GROUP)) == reported
        assert seen == [reported]
        time.sleep(0.3)
        assert process_live(member) is not killed
    finally:
        kill_quietly(member)


@pytest.mark.parametrize(("after", "killed"), [(0, False), (1, True)],
                         ids=["started-at-the-last-observation", "started-before-it"])
def test_a_session_member_without_the_mark_is_judged_by_session_and_start_time_alone(
    runner: Runner, spool: Spool, after: int, killed: bool
) -> None:
    """§30 (REVIEW-13 should-fix 2): session-and-start-time is the proof and the mark
    corroborates only. The member is in the job's session and has cleared
    `HANDS_JOB`. Started before the last observation, it is the job's: killed and
    reported like a marked one. Started in the same tick (the residual), nothing
    proves it, and what the sweep leaves alive is still reported, `killed: false`."""
    job = spool.create_job(role="builder", context="clear", prompt="x", origin="cli")
    leader = _vacated_group(job, marked=False)
    members = group_pids(leader.pid)
    assert len(members) == 1, "the background sleep should still be in the group"
    member = members[0]
    environ = Path(f"/proc/{member}/environ").read_bytes().split(b"\0")
    assert not any(entry.startswith(JOB_ENV.encode() + b"=") for entry in environ)
    assert os.getsid(member) == leader.pid
    seen: list[object] = []
    runner.on_orphans = lambda job, processes, isolation: seen.append(processes)
    try:
        job.pid = leader.pid
        runner._leader_start = {job.id: 1}
        runner._last_seen = {job.id: _start_ticks(member) + after}
        reported = [{"pid": member, "cmdline": "sleep 30", "killed": killed}]
        assert asyncio.run(runner._sweep(job, GROUP)) == reported
        assert seen == [reported]
        time.sleep(0.3)
        assert process_live(member) is not killed
    finally:
        kill_quietly(member)


@pytest.mark.parametrize("timeout", [0.2, 1.5])
def test_job_end_is_bounded_by_pipe_timeout_s_when_an_unproven_orphan_holds_the_pipes(
    tmp_home: Path, workdir: Path, spool: Spool, tmp_path: Path, timeout: float
) -> None:
    """§29: the orphan called setsid, so the sweep cannot prove it is the job's and
    does not kill it; it still holds claude's stdout and stderr. Job end reads
    them for `runner.pipe_timeout_s` after the sweep and then ends the job anyway,
    and the orphan is reported `killed: false`.

    §30 (REVIEW-13 should-fix 3): the time from the sweep's report to job end is
    bound to the configured value from both sides, for two values 1.3 s apart
    with 1 s of slack, so no single hardcoded timeout passes both rows."""
    cfg = parse_config(
        {
            "roles": {"builder": {"cwd": str(workdir), "model": "opus"}},
            "runner": {"claude": str(FAKE), "cancel_grace_s": 0.2, "pipe_timeout_s": timeout},
        },
        project="demo",
        path=tmp_home / ".hands" / "demo.toml",
    )
    runner = Runner(cfg, spool)
    pidfile = tmp_path / "orphan.pid"
    seen: list[tuple[str, list[dict[str, object]]]] = []
    reported_at: list[float] = []

    def on_orphans(job: Job, processes: list[dict[str, object]], isolation: str) -> None:
        reported_at.append(time.monotonic())
        seen.append((job.id, processes))

    runner.on_orphans = on_orphans

    async def body() -> tuple[Job, float]:
        job = spool.create_job(
            role="builder",
            context="clear",
            prompt=f"FAKE:orphan {pidfile} keep-stdio setsid",
            origin="cli",
        )
        finished = await runner.run(job)
        return finished, time.monotonic()

    try:
        job, ended = asyncio.run(asyncio.wait_for(body(), 30))
        pid = int(pidfile.read_text())
        assert job.state == "done"
        [swept] = reported_at
        # The sweep reports, then job end reads the held pipes for the configured
        # timeout and no longer: far under the orphan's 300 s and the 10 s default.
        drained = ended - swept
        assert timeout - 0.05 <= drained < timeout + 1.0, drained
        assert seen == [(job.id, [{"pid": pid, "cmdline": "sleep 300", "killed": False}])]
        assert process_live(pid), "an orphan the sweep could not prove was killed"
    finally:
        if pidfile.exists() and pidfile.read_text():
            kill_quietly(int(pidfile.read_text()))


def test_a_job_runs_with_its_id_in_hands_job(runner: Runner, spool: Spool) -> None:
    """The mark the sweep reads to tell the job's descendants from strangers."""
    prompt = f"FAKE:env {JOB_ENV}"
    job = spool.create_job(role="builder", context="clear", prompt=prompt, origin="cli")
    assert asyncio.run(runner.run(job)).result == job.id


def test_a_cancelled_run_is_killed_by_the_last_resort_through_run(
    runner: Runner, spool: Spool
) -> None:
    """The exception path of `run()` itself: the start time recorded at spawn is
    claude's, so the still-running claude is killed."""

    async def body() -> int:
        job, task = start(runner, spool, "FAKE:block\nFAKE:ignore-int")
        await runner.wait_for_session(job.id)
        pid = spool.load_job(job.id).pid
        assert pid is not None and process_live(pid)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        return pid

    pid = asyncio.run(asyncio.wait_for(body(), 30))
    try:

        async def gone() -> None:
            await until(lambda: not process_live(pid), "claude to die", 5)

        asyncio.run(gone())
    finally:
        kill_quietly(pid)


def test_a_driver_job_runs_with_hands_role_driver(
    tmp_home: Path, workdir: Path, spool: Spool, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§27: the guard's role mode is `HANDS_ROLE=driver` in the job's environment,
    whatever handsd itself inherited or the role's env table says."""
    monkeypatch.setenv("HANDS_ROLE", "builder")
    cfg = parse_config(
        {
            "roles": {
                "builder": {"cwd": str(workdir)},
                "driver": {"cwd": str(workdir), "env": {"HANDS_ROLE": "aux"}},
            },
            "runner": {"claude": str(FAKE)},
        },
        project="demo",
        path=tmp_home / ".hands" / "demo.toml",
    )
    runner = Runner(cfg, spool)
    job = spool.create_job(role="driver", context="clear", prompt="FAKE:env HANDS_ROLE",
                           origin="cli")
    assert asyncio.run(runner.run(job)).result == "driver"
    # a builder job does not get it from hands (it inherits handsd's own)
    assert send(runner, spool, "FAKE:env HANDS_ROLE").result == "builder"


@pytest.mark.parametrize("layout", ["repo-under-cwd", "cwd-is-the-repo", "no-clone"])
def test_a_driver_job_carries_its_clone_as_hands_clone(
    tmp_home: Path, workdir: Path, spool: Spool, monkeypatch: pytest.MonkeyPatch, layout: str
) -> None:
    """§29: the guard pins role mode's `git -C` to `HANDS_CLONE`, which handsd sets on
    the driver job to the role's clone: `<cwd>/repo` (driver/README.md), or `<cwd>`
    when that is the repository (doctor's rule). Never from handsd's environment or
    the role's env table; with no clone it is absent and every `git -C` is refused."""
    monkeypatch.setenv("HANDS_CLONE", "/tmp")
    if layout == "repo-under-cwd":
        (workdir / "repo" / ".git").mkdir(parents=True)
        expected = str(workdir / "repo")
    elif layout == "cwd-is-the-repo":
        (workdir / ".git").mkdir()
        expected = str(workdir)
    else:
        expected = "UNSET:HANDS_CLONE"
    cfg = parse_config(
        {
            "roles": {
                "builder": {"cwd": str(workdir)},
                "driver": {"cwd": str(workdir), "env": {"HANDS_CLONE": "/etc"}},
            },
            "runner": {"claude": str(FAKE)},
        },
        project="demo",
        path=tmp_home / ".hands" / "demo.toml",
    )
    runner = Runner(cfg, spool)
    job = spool.create_job(role="driver", context="clear", prompt="FAKE:env HANDS_CLONE",
                           origin="cli")
    assert asyncio.run(runner.run(job)).result == expected
    # a builder job does not get it from hands (it inherits handsd's own)
    assert send(runner, spool, "FAKE:env HANDS_CLONE").result == "/tmp"
