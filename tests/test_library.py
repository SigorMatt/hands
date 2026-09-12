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
import tracemalloc
from pathlib import Path
from typing import Any

import pytest

from conftest import strip_paths
from hands.api import LOG_PAGE_BYTES, MAX_TAIL_ENTRIES, TAIL_WINDOW_BYTES, tail_entries
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
        assert "yesterday" in strip_paths(err)
        assert "2d" in strip_paths(err), "the refusal must show the forms --since does take"

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
        assert "robot" in strip_paths(err)
        for known in ("cli", "driver", "limit", "playbook"):
            assert known in strip_paths(err), f"the refusal must name the whole vocabulary: {err}"

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
        assert "builder" in strip_paths(line)
        assert "done" in strip_paths(line)
        assert line.endswith("VERDICT: PASS"), "the verdict is what the human is looking for"
        assert "FAKE:" not in strip_paths(line), (
            "the verdict replaces the prompt line, it does not follow it"
        )
        assert re.search(r"\b\d+[smhd]\b", strip_paths(line)), (
            f"the line must carry the job's age: {line}"
        )

        # With no verdict, the first line of the prompt stands in for one.
        other = await run("--role", "aux", "--context", "clear", "hello there")
        code, out, _ = await cli("jobs", "--role", "aux")
        assert other["id"] in out
        assert "hello there" in strip_paths(out)

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
        assert "running" in strip_paths(err)
        assert "log -f" in strip_paths(err), (
            "§2: for a live job the answer is `hands log -f <role>`"
        )
        await ok("cancel", sent["id"])

    drive(body)


def test_open_refuses_a_job_that_has_no_session(project: str) -> None:
    async def body(daemon: Daemon) -> None:
        held = await ok(
            "send", "--role", "builder", "--context", "clear", "--gate", "look first", "x"
        )
        assert held["state"] == "held"
        err = await fails("open", held["id"])
        assert "session" in strip_paths(err)

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
        assert "no captured stream" in strip_paths(out)

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
        assert "builder" in strip_paths(err)
        assert "running" in strip_paths(err)
        # A job id and -f are two different questions; asking both is a mistake.
        assert "not both" in strip_paths(await fails("log", "somejob", "-f", "builder"))

    drive(body)


# ------------------------------------------------------- log pages §4 (H-013)


def _fat_stream(daemon: Daemon, job_id: str, count: int) -> tuple[Path, list[str]]:
    """Put `count` fat stream-json lines in the job's log file, bigger than a page."""
    path = daemon.spool.stream_path(job_id)
    lines = [json.dumps({"type": "assistant", "n": n, "pad": "p" * 4000}) for n in range(count)]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path, lines


def test_log_is_delivered_in_pages(project: str) -> None:
    """§4's `log` row: a whole transcript is never one message (H-013).

    One answer carries at most `LOG_PAGE_BYTES` of complete lines and says
    whether more follows; a `--json` caller continues from the `offset` it was
    given, and the human route loops so it still prints the whole stream.
    """

    async def body(daemon: Daemon) -> None:
        done = await run("--role", "builder", "--context", "clear", "FAKE:result paged")
        path, lines = _fat_stream(daemon, done["id"], 200)  # ~800 KB, several pages
        size = path.stat().st_size
        assert size > 3 * LOG_PAGE_BYTES, "the fixture has to need more than one page"

        first = await ok("log", done["id"])
        assert first["more"] is True, "there is more of this stream than one answer carries"
        assert 0 < first["offset"] < size
        assert sum(len(line) + 1 for line in first["lines"]) <= LOG_PAGE_BYTES
        assert first["lines"] == lines[: len(first["lines"])]

        seen = list(first["lines"])
        page = first
        pages = 1
        while page["more"] and page["lines"]:
            page = await ok("log", done["id"], "--offset", str(page["offset"]))
            assert sum(len(line) + 1 for line in page["lines"]) <= LOG_PAGE_BYTES
            seen += page["lines"]
            pages += 1
        assert pages > 3, "one page per answer, so this stream took several"
        assert seen == lines, "the pages are the stream, in order, with nothing dropped"
        assert page["offset"] == size and page["more"] is False

        # The human route is one command and still prints all of it (§4).
        code, out, err = await cli("log", done["id"])
        assert code == 0, err
        assert out.splitlines() == lines

    drive(body)


def test_log_of_a_huge_stream_is_read_in_bounded_memory(project: str) -> None:
    """§21 through §4's `log` row: 64 MB on disk, a page at a time in the daemon.

    Measured the way mission 5's U6 measured the runner: `tracemalloc` around
    the daemon-side call, peak against a file two orders of magnitude bigger.
    """

    async def body(daemon: Daemon) -> None:
        done = await run("--role", "builder", "--context", "clear", "FAKE:result huge")
        line = json.dumps({"type": "assistant", "pad": "p" * 4000})
        count = 64 * 1024 * 1024 // (len(line) + 1)
        path = daemon.spool.stream_path(done["id"])
        with path.open("w", encoding="utf-8") as handle:
            for _ in range(count):
                handle.write(line + "\n")
        size = path.stat().st_size
        assert size > 60 * 1024 * 1024

        tracemalloc.start()
        try:
            offset = seen = pages = 0
            while True:
                page = await daemon.api.log(job=done["id"], offset=offset)
                assert page["lines"], "a page of a file of complete lines is never empty"
                seen += len(page["lines"])
                offset = page["offset"]
                pages += 1
                if not page["more"]:
                    break
            peak = tracemalloc.get_traced_memory()[1]
        finally:
            tracemalloc.stop()

        assert (seen, offset) == (count, size), "every line, once, and up to the end"
        assert pages > 200, "a 64 MB stream is many pages, not one message"
        assert peak < 8 * 1024 * 1024, f"peak {peak} bytes reading a {size} byte stream"

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


def test_tail_reads_only_the_end_of_a_transcript(project: str) -> None:
    """§21: `tail` holds a window over the end of the file, never the file.

    The transcript here is bigger than the window, so a whole-file read would
    return the first entry as easily as the last. Only the last ones come back,
    and the read is bounded by `TAIL_WINDOW_BYTES` however long the file gets.
    """

    async def body(daemon: Daemon) -> None:
        done = await run("--role", "builder", "--context", "clear", "FAKE:result big")
        transcript = Path(done["transcript_path"])
        transcript.parent.mkdir(parents=True, exist_ok=True)
        pad = "x" * 1000
        with transcript.open("w", encoding="utf-8") as handle:
            for n in range(10_000):  # ~10 MB, more than the window
                handle.write(json.dumps({"type": "user", "n": n, "pad": pad}) + "\n")
        assert transcript.stat().st_size > TAIL_WINDOW_BYTES

        record = await ok("tail", "--role", "builder", "-n", "3")
        assert [json.loads(line)["n"] for line in record["entries"]] == [9997, 9998, 9999]

    drive(body)


def test_tail_returns_at_most_the_entry_cap(project: str) -> None:
    """`-n` is bounded: `tail` is a peek, and the daemon answers it from memory."""

    async def body(daemon: Daemon) -> None:
        done = await run("--role", "builder", "--context", "clear", "FAKE:result capped")
        transcript = Path(done["transcript_path"])
        transcript.parent.mkdir(parents=True, exist_ok=True)
        transcript.write_text(
            "".join(json.dumps({"n": n}) + "\n" for n in range(MAX_TAIL_ENTRIES + 500))
        )
        record = await ok("tail", "--role", "builder", "-n", str(MAX_TAIL_ENTRIES + 400))
        assert len(record["entries"]) == MAX_TAIL_ENTRIES
        assert json.loads(record["entries"][-1])["n"] == MAX_TAIL_ENTRIES + 499

    drive(body)


def test_tail_of_a_transcript_of_one_huge_entry_is_still_bounded(tmp_path: Path) -> None:
    """A single entry wider than the window is not read whole (§21)."""
    path = tmp_path / "t.jsonl"
    with path.open("w", encoding="utf-8") as handle:
        handle.write("a" * (TAIL_WINDOW_BYTES * 2) + "\n")
        handle.write("last\n")

    entries, truncated = tail_entries(path, 5)
    assert entries == ["last"], "the window ends at the last complete lines"
    assert truncated is True, "5 were asked for, 1 came back, and the rest is off the window"


def test_tail_refuses_an_n_below_one(project: str) -> None:
    """§4: `--role r -n` is `n >= 1`. 0 and negatives are refused, exit 2, one line."""

    async def body(daemon: Daemon) -> None:
        for value in ("0", "-1", "-1000"):
            code, out, err = await cli("tail", "--role", "builder", "-n", value)
            assert code == 2, f"-n {value} must be refused with exit 2, not {code}"
            assert out == "", "a refused command answers nothing"
            assert len(strip_paths(err).strip().splitlines()) == 1, f"one line, not {err!r}"
            assert "-n" in strip_paths(err), "the refusal names the option"
            assert value in strip_paths(err), "and the value it will not take"
            assert "1" in strip_paths(err), "and the least it does take"

    drive(body)


def test_tail_says_when_the_entry_cap_cut_the_answer(project: str) -> None:
    """§4: `truncated: true` when the 1000-entry cap cut the answer short.

    The transcript here has 2000 entries and the caller asks for all 2000: the
    cap answers 1000 of them, and before review 5's blocker 2 it said nothing
    about the other 1000.
    """

    async def body(daemon: Daemon) -> None:
        done = await run("--role", "builder", "--context", "clear", "FAKE:result capped")
        transcript = Path(done["transcript_path"])
        transcript.parent.mkdir(parents=True, exist_ok=True)
        transcript.write_text("".join(json.dumps({"n": n}) + "\n" for n in range(2000)))

        record = await ok("tail", "--role", "builder", "-n", "2000")
        assert len(record["entries"]) == MAX_TAIL_ENTRIES
        assert record["truncated"] is True
        code, out, err = await cli("tail", "--role", "builder", "-n", "2000")
        assert code == 0, err
        assert "truncated" in strip_paths(out), "the human is told in one line"
        said = [line for line in strip_paths(out).splitlines() if "truncated" in line]
        assert len(said) == 1, f"one line, not {said}"

        # The same transcript, an answer nothing cut: no claim of truncation.
        whole = await ok("tail", "--role", "builder", "-n", "20")
        assert len(whole["entries"]) == 20
        assert whole["truncated"] is False
        code, out, err = await cli("tail", "--role", "builder", "-n", "20")
        assert code == 0, err
        assert "truncated" not in strip_paths(out)

    drive(body)


def test_tail_says_when_the_read_window_cut_the_answer(project: str) -> None:
    """§4: `truncated: true` when the read window cut it — including to nothing.

    A trailing entry wider than `TAIL_WINDOW_BYTES` fills the window with a
    fragment of one entry, and a fragment is not an entry. The answer is empty,
    and before review 5's blocker 2 an empty answer was all a caller got.
    """

    async def body(daemon: Daemon) -> None:
        done = await run("--role", "builder", "--context", "clear", "FAKE:result wide")
        transcript = Path(done["transcript_path"])
        transcript.parent.mkdir(parents=True, exist_ok=True)
        with transcript.open("w", encoding="utf-8") as handle:
            handle.write(json.dumps({"n": 0}) + "\n")
            handle.write(json.dumps({"n": 1, "pad": "p" * (TAIL_WINDOW_BYTES + 4096)}) + "\n")

        record = await ok("tail", "--role", "builder", "-n", "5")
        assert record["entries"] == [], "half an entry is not an entry"
        assert record["truncated"] is True
        code, out, err = await cli("tail", "--role", "builder", "-n", "5")
        assert code == 0, err
        assert "truncated" in strip_paths(out)

    drive(body)


def test_tail_says_plainly_when_there_is_no_transcript_file(project: str) -> None:
    async def body(daemon: Daemon) -> None:
        done = await run("--role", "builder", "--context", "clear", "FAKE:result no file")
        err = await fails("tail", "--role", "builder")
        assert done["transcript_path"] in err
        assert "Claude Code" in strip_paths(err), "the file is Claude Code's, not hands' (§7)"

    drive(body)


def test_tail_of_a_role_that_never_ran_says_so(project: str) -> None:
    async def body(daemon: Daemon) -> None:
        err = await fails("tail", "--role", "aux")
        assert "aux" in strip_paths(err)

    drive(body)
