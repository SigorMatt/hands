"""U9: the job library — `jobs`, `show`, `open`, `log`, `tail` (DESIGN §2, §4, §7).

Same shape as tests/test_daemon.py: a real daemon on a real unix socket, the CLI
in a worker thread, nothing mocked but the `claude` binary. No test here execs a
real `claude` — `hands open` takes its exec as an argument (`main(exec_fn=…)`),
and every other assertion is on the argv the command *would* run.
"""

from __future__ import annotations

import asyncio
import io
import json
import re
from pathlib import Path
from typing import Any

import pytest

from hands.cli import main
from hands.daemon import Daemon
from harness import BLOCK, PROJECT, cli, config_body, drive, fails, ok, poll, running_job

# ------------------------------------------------------------------ fixtures


@pytest.fixture
def workdir(tmp_path: Path) -> Path:
    d = tmp_path / "work"
    d.mkdir(exist_ok=True)
    return d


@pytest.fixture
def project(tmp_home: Path, workdir: Path) -> str:
    body = config_body(
        tmp_home, workdir, builder="cancel_gated = false", aux="cancel_gated = false"
    )
    (tmp_home / ".hands" / f"{PROJECT}.toml").write_text(body)
    return PROJECT


async def run(*argv: str) -> Any:
    """Send a prompt and wait for the finished record."""
    sent = await ok("send", *argv)
    return await ok("wait", sent["id"])


async def cli_with_exec(*argv: str, exec_fn: Any) -> tuple[int, str, str]:
    """The CLI with its exec replaced — `hands open` must never exec in a test."""
    out, err = io.StringIO(), io.StringIO()
    code = await asyncio.to_thread(
        main, ["--project", PROJECT, *argv], stdout=out, stderr=err, exec_fn=exec_fn
    )
    return code, out.getvalue(), err.getvalue()


# -------------------------------------------------------------- filtering §7


def test_jobs_filters_by_role_grep_and_since(project: str) -> None:
    async def body(daemon: Daemon) -> None:
        one = await run("--role", "builder", "--context", "clear", "FAKE:result a\nrun 3 batch A")
        two = await run("--role", "aux", "--context", "clear", "FAKE:result b\nRUN 4 batch B")

        ids = lambda rows: [row["id"] for row in rows["jobs"]]  # noqa: E731
        assert ids(await ok("jobs")) == [two["id"], one["id"]]
        assert ids(await ok("jobs", "--role", "aux")) == [two["id"]]
        # §7: searching prompts is searching work items, and the human types the
        # run name in whatever case they remember it in.
        assert ids(await ok("jobs", "--grep", "run 3")) == [one["id"]]
        assert ids(await ok("jobs", "--grep", "run 4")) == [two["id"]]
        assert ids(await ok("jobs", "--grep", "batch")) == [two["id"], one["id"]]
        assert ids(await ok("jobs", "--grep", "no such thing")) == []
        # --since: relative forms and an ISO date, both against `created`.
        assert ids(await ok("jobs", "--since", "1d")) == [two["id"], one["id"]]
        assert ids(await ok("jobs", "--since", "2h")) == [two["id"], one["id"]]
        assert ids(await ok("jobs", "--since", "2000-01-01")) == [two["id"], one["id"]]
        assert ids(await ok("jobs", "--since", "2999-01-01")) == []
        # -n is the cap, newest first.
        assert ids(await ok("jobs", "-n", "1")) == [two["id"]]
        # Filters compose.
        assert ids(await ok("jobs", "--role", "builder", "--grep", "batch", "--since", "1d")) == [
            one["id"]
        ]

    drive(body)


def test_jobs_refuses_a_since_it_cannot_parse(project: str) -> None:
    async def body(daemon: Daemon) -> None:
        err = await fails("jobs", "--since", "yesterday")
        assert "yesterday" in err
        assert "2d" in err, "the refusal must show the forms --since does take"

    drive(body)


def test_jobs_filters_by_origin(project: str) -> None:
    """§4's `jobs [--origin o]` over §6's `driver|playbook|cli|limit` (H-004)."""

    async def body(daemon: Daemon) -> None:
        sent = await run("--role", "builder", "--context", "clear", "FAKE:result a\nfrom a human")
        # The origins no client can produce: filed straight into the spool, the
        # way §6's limit manager and §10's engine file theirs.
        limit = daemon.spool.create_job(
            role="builder", context="clear", prompt="Resume WORKPLAN.md",
            origin="limit", resumed_from=sent["id"],
        )  # fmt: skip
        book = daemon.spool.create_job(
            role="aux", context="clear", prompt="p", origin="playbook"
        )

        ids = lambda rows: [row["id"] for row in rows["jobs"]]  # noqa: E731
        assert ids(await ok("jobs", "--origin", "cli")) == [sent["id"]]
        assert ids(await ok("jobs", "--origin", "limit")) == [limit.id]
        assert ids(await ok("jobs", "--origin", "playbook")) == [book.id]
        assert ids(await ok("jobs", "--origin", "driver")) == []
        # Composes with the other filters.
        assert ids(await ok("jobs", "--origin", "limit", "--role", "aux")) == []
        assert ids(await ok("jobs", "--origin", "limit", "--role", "builder")) == [limit.id]

    drive(body)


def test_jobs_refuses_an_origin_outside_section_6s_vocabulary(project: str) -> None:
    async def body(daemon: Daemon) -> None:
        err = await fails("jobs", "--origin", "robot")
        assert "robot" in err
        for known in ("cli", "driver", "limit", "playbook"):
            assert known in err, f"the refusal must name the whole vocabulary: {err}"

    drive(body)


def test_jobs_readable_output_is_one_line_a_job(project: str) -> None:
    async def body(daemon: Daemon) -> None:
        done = await run(
            "--role", "builder", "--context", "clear", "FAKE:result VERDICT: PASS\\nmore"
        )
        code, out, _ = await cli("jobs")
        assert code == 0
        lines = [line for line in out.splitlines() if line.strip()]
        assert len(lines) == 1
        line = lines[0]
        assert done["id"] in line
        assert "builder" in line
        assert "done" in line
        assert line.endswith("VERDICT: PASS"), "the verdict is what the human is looking for"
        assert "FAKE:" not in line, "the verdict replaces the prompt line, it does not follow it"
        assert re.search(r"\b\d+[smhd]\b", line), f"the line must carry the job's age: {line}"

        # With no verdict, the first line of the prompt stands in for one.
        other = await run("--role", "aux", "--context", "clear", "hello there")
        code, out, _ = await cli("jobs", "--role", "aux")
        assert other["id"] in out
        assert "hello there" in out

    drive(body)


# ---------------------------------------------------------------- open §2 §7


def test_open_gives_the_resume_argv_in_the_role_cwd(project: str, workdir: Path) -> None:
    async def body(daemon: Daemon) -> None:
        done = await run("--role", "builder", "--context", "clear", "FAKE:session sess-open")
        plan = await ok("open", done["id"])
        assert plan["session_id"] == "sess-open"
        assert plan["cwd"] == str(workdir)
        assert plan["argv"][1:] == ["--resume", "sess-open"]
        assert plan["argv"][0].endswith("fake_claude.py"), "the claude of [runner], §13"

    drive(body)


def test_open_execs_claude_in_the_role_cwd(project: str, workdir: Path) -> None:
    calls: list[tuple[list[str], str]] = []

    async def body(daemon: Daemon) -> None:
        done = await run("--role", "builder", "--context", "clear", "FAKE:session sess-exec")
        code, out, err = await cli_with_exec(
            "open", done["id"], exec_fn=lambda argv, cwd: calls.append((list(argv), cwd))
        )
        assert code == 0, err
        assert len(calls) == 1, "`hands open` without --json execs, once"
        argv, cwd = calls[0]
        assert argv[0].endswith("fake_claude.py")
        assert argv[1:] == ["--resume", "sess-exec"]
        assert cwd == str(workdir)
        assert out == "", "the exec replaces the process; there is nothing to print"

    drive(body)


def test_open_refuses_a_running_job(project: str) -> None:
    async def body(daemon: Daemon) -> None:
        sent = await ok("send", "--role", "builder", "--context", "clear", BLOCK)
        running = await running_job("builder")
        err = await fails("open", running["id"])
        assert "running" in err
        assert "log -f" in err, "§2: for a live job the answer is `hands log -f <role>`"
        await ok("cancel", sent["id"])

    drive(body)


def test_open_refuses_a_job_that_has_no_session(project: str) -> None:
    async def body(daemon: Daemon) -> None:
        held = await ok(
            "send", "--role", "builder", "--context", "clear", "--gate", "look first", "x"
        )
        assert held["state"] == "held"
        err = await fails("open", held["id"])
        assert "session" in err

    drive(body)


# ----------------------------------------------------------------- log §7


def test_log_prints_the_captured_stream_of_a_finished_job(project: str) -> None:
    async def body(daemon: Daemon) -> None:
        done = await run("--role", "builder", "--context", "clear", "FAKE:result logged")
        code, out, err = await cli("log", done["id"])
        assert code == 0, err
        events = [json.loads(line) for line in out.splitlines() if line.strip()]
        kinds = [(e.get("type"), e.get("subtype")) for e in events]
        assert ("system", "init") in kinds
        assert ("result", "success") in kinds
        # --json is the same bytes, wrapped in the record the driver reads.
        record = await ok("log", done["id"])
        assert record["job"] == done["id"]
        assert record["state"] == "done"
        assert [json.loads(line) for line in record["lines"]] == events

    drive(body)


def test_log_of_a_job_that_never_ran_says_so(project: str) -> None:
    async def body(daemon: Daemon) -> None:
        held = await ok(
            "send", "--role", "builder", "--context", "clear", "--gate", "look first", "x"
        )
        record = await ok("log", held["id"])
        assert record["lines"] == []
        code, out, _ = await cli("log", held["id"])
        assert code == 0
        assert "no captured stream" in out

    drive(body)


def test_log_follow_streams_a_running_job_until_it_ends(project: str) -> None:
    async def body(daemon: Daemon) -> None:
        sent = await ok("send", "--role", "builder", "--context", "clear", BLOCK)
        await running_job("builder")
        follow = asyncio.create_task(cli("log", "-f", "builder"))
        # The first event of the stream arrives while the job is still running.
        await poll(
            lambda: _has_init(daemon, sent["id"]), "the init event to reach the stream file"
        )
        assert not follow.done(), "`log -f` must keep following a running job"
        await ok("cancel", sent["id"])
        code, out, err = await asyncio.wait_for(follow, 30)
        assert code == 0, err
        events = [json.loads(line) for line in out.splitlines() if line.strip()]
        assert ("system", "init") in [(e.get("type"), e.get("subtype")) for e in events]

    drive(body)


async def _has_init(daemon: Daemon, job_id: str) -> bool:
    path = daemon.spool.jobs_dir / f"{job_id}.stream.jsonl"
    return path.exists() and "init" in path.read_text()


def test_log_follow_refuses_a_role_with_no_running_job(project: str) -> None:
    async def body(daemon: Daemon) -> None:
        err = await fails("log", "-f", "builder")
        assert "builder" in err
        assert "running" in err
        # A job id and -f are two different questions; asking both is a mistake.
        assert "not both" in await fails("log", "somejob", "-f", "builder")

    drive(body)


# ---------------------------------------------------------------- tail §4


def test_tail_reads_the_transcript_claude_code_wrote(project: str) -> None:
    async def body(daemon: Daemon) -> None:
        done = await run("--role", "builder", "--context", "clear", "FAKE:result tailed")
        transcript = Path(done["transcript_path"])
        transcript.parent.mkdir(parents=True, exist_ok=True)
        transcript.write_text(
            "\n".join(json.dumps({"type": "user", "n": n}) for n in range(5)) + "\n"
        )
        record = await ok("tail", "--role", "builder", "-n", "2")
        assert record["job"] == done["id"]
        assert record["path"] == str(transcript)
        assert [json.loads(line)["n"] for line in record["entries"]] == [3, 4]

    drive(body)


def test_tail_says_plainly_when_there_is_no_transcript_file(project: str) -> None:
    async def body(daemon: Daemon) -> None:
        done = await run("--role", "builder", "--context", "clear", "FAKE:result no file")
        err = await fails("tail", "--role", "builder")
        assert done["transcript_path"] in err
        assert "Claude Code" in err, "the file is Claude Code's, not hands' (§7)"

    drive(body)


def test_tail_of_a_role_that_never_ran_says_so(project: str) -> None:
    async def body(daemon: Daemon) -> None:
        err = await fails("tail", "--role", "aux")
        assert "aux" in err

    drive(body)
