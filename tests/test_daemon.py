"""U3: the daemon, the local API and the CLI (DESIGN §3, §4, §6, §9, §13).

Every test here drives the *real* unix socket: the daemon runs in the test's
event loop and the CLI runs in a worker thread, exactly as `hands` runs at a
terminal. Nothing is mocked but the `claude` binary (`tests/fake_claude.py`).
"""

from __future__ import annotations

import argparse
import asyncio
import io
import json
import logging
import os
import shutil
import socket
import threading
from pathlib import Path
from typing import Any

import pytest

from conftest import strip_paths
from hands import cli as cli_mod
from hands import daemon as daemon_mod
from hands.cli import EXIT_REFUSED, EXIT_TIMEOUT, main
from hands.config import load_config
from hands.daemon import Daemon
from hands.runner import LINE_LIMIT, MAX_PROMPT_BYTES
from hands.spool import Spool
from harness import (
    BLOCK,
    PROJECT,
    TIMEOUT,
    cli,
    config_body,
    drive,
    fails,
    ok,
    running_job,
    write_project,
)

# ------------------------------------------------------------------ fixtures


@pytest.fixture
def workdir(tmp_path: Path) -> Path:
    d = tmp_path / "work"
    d.mkdir(exist_ok=True)
    return d


@pytest.fixture
def project(tmp_home: Path, workdir: Path) -> str:
    """`~/.hands/demo.toml`. Cancel is ungated here: these are U3's queue tests,
    and the cancel gate of §8 has its own file (tests/test_gates.py)."""
    body = config_body(
        tmp_home, workdir, builder="cancel_gated = false", aux="cancel_gated = false"
    )
    (tmp_home / ".hands" / f"{PROJECT}.toml").write_text(body)
    return PROJECT


# --------------------------------------------------- the gate of this unit


def test_send_wait_result_end_to_end(project: str, tmp_home: Path) -> None:
    result = "VERDICT: PASS\n  indented\n\ntrailing   \nunicode: — é"
    escaped = result.replace("\\", "\\\\").replace("\n", "\\n")

    async def body(daemon: Daemon) -> None:
        sent = await ok("send", "--role", "builder", "--context", "clear", f"FAKE:result {escaped}")
        job_id = sent["id"]
        assert sent["role"] == "builder"
        assert sent["context"] == "clear"
        assert sent["state"] in {"queued", "running"}

        waited = await ok("wait", job_id)
        assert waited["state"] == "done"
        assert waited["id"] == job_id

        got = await ok("result", job_id)
        assert got["result"] == result  # verbatim, §6
        assert got["verdict"] == "VERDICT: PASS"
        assert got["session_id"]
        assert got["exit_code"] == 0

        # readable form, not JSON
        code, out, _ = await cli("result", job_id)
        assert code == 0
        assert job_id in strip_paths(out)
        assert "done" in strip_paths(out)
        assert "VERDICT: PASS" in strip_paths(out)

    drive(body)


def test_a_second_send_to_a_busy_role_queues_and_a_third_is_refused(project: str) -> None:
    async def body(daemon: Daemon) -> None:
        first = await ok("send", "--role", "builder", "--context", "clear", BLOCK)
        await running_job("builder")

        second = await ok("send", "--role", "builder", "--context", "clear", "FAKE:result second")
        assert second["state"] == "queued"

        err = await fails("send", "--role", "builder", "--context", "clear", "FAKE:result third")
        assert "queue" in strip_paths(err.lower())

        status = await ok("status")
        assert status["roles"]["builder"]["queued"] == [second["id"]]
        assert status["roles"]["builder"]["queue_depth"] == 1

        # cancelling the running job lets the queued one through
        await ok("cancel", first["id"], "--reason", "making room")
        assert (await ok("result", first["id"]))["state"] == "killed"
        done = await ok("wait", second["id"])
        assert done["state"] == "done"
        assert done["result"] == "second"

    drive(body)


def test_the_aux_queue_accepts_four(project: str) -> None:
    async def body(daemon: Daemon) -> None:
        await ok("send", "--role", "aux", "--context", "clear", BLOCK)
        await running_job("aux")

        queued = [
            (await ok("send", "--role", "aux", "--context", "clear", f"FAKE:result q{n}"))["id"]
            for n in range(4)
        ]
        assert (await ok("status"))["roles"]["aux"]["queued"] == queued

        err = await fails("send", "--role", "aux", "--context", "clear", "FAKE:result fifth")
        assert "queue" in strip_paths(err.lower())

    drive(body)


# ------------------------------------------------------------ queue details


def test_queued_jobs_survive_a_daemon_restart(project: str, tmp_home: Path) -> None:
    async def body(daemon: Daemon) -> None:
        await ok("send", "--role", "builder", "--context", "clear", BLOCK)
        await running_job("builder")
        queued = await ok("send", "--role", "builder", "--context", "clear", "FAKE:result later")
        assert queued["state"] == "queued"
        body.queued_id = queued["id"]  # type: ignore[attr-defined]

    drive(body)

    async def after(daemon: Daemon) -> None:
        job = await ok("wait", body.queued_id)  # type: ignore[attr-defined]
        assert job["state"] == "done"
        assert job["result"] == "later"

    drive(after)


def test_a_queued_job_can_be_cancelled_before_it_runs(project: str) -> None:
    async def body(daemon: Daemon) -> None:
        await ok("send", "--role", "builder", "--context", "clear", BLOCK)
        await running_job("builder")
        queued = await ok("send", "--role", "builder", "--context", "clear", "FAKE:result never")

        cancelled = await ok("cancel", queued["id"], "--reason", "not needed")
        assert cancelled["state"] == "killed"
        assert (await ok("status"))["roles"]["builder"]["queued"] == []

    drive(body)


# ------------------------------------------------------------ startup facts


def test_running_jobs_of_a_dead_daemon_are_orphaned_at_startup(
    project: str, tmp_home: Path, workdir: Path
) -> None:
    spool = Spool(tmp_home / ".hands")
    job = spool.create_job(role="builder", context="clear", prompt="x", origin="cli")
    spool.transition(job, "running", pid=999999, session_id="gone")

    async def body(daemon: Daemon) -> None:
        assert (await ok("result", job.id))["state"] == "orphaned"

    drive(body)


def test_the_captured_stream_is_persisted_per_job(project: str, tmp_home: Path) -> None:
    async def body(daemon: Daemon) -> None:
        sent = await ok("send", "--role", "builder", "--context", "clear", "FAKE:result streamed")
        await ok("wait", sent["id"])
        path = tmp_home / ".hands" / "jobs" / f"{sent['id']}.stream.jsonl"
        assert path.exists(), "the daemon must persist the stream for `hands log` (U9)"
        events = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        kinds = [(e.get("type"), e.get("subtype")) for e in events]
        assert ("system", "init") in kinds
        assert ("result", "success") in kinds

    drive(body)


# ------------------------------------------------------------ other commands


def test_status_reports_daemon_roles_and_monitor(project: str) -> None:
    async def body(daemon: Daemon) -> None:
        status = await ok("status")
        assert status["daemon"]["pid"] == os.getpid()
        assert status["daemon"]["project"] == PROJECT
        assert status["daemon"]["socket"].endswith("handsd.sock")
        assert set(status["roles"]) == {"builder", "aux"}
        assert status["roles"]["builder"]["running"] is None
        assert "monitor" in status  # the status record, not text
        code, out, _ = await cli("status")
        assert code == 0
        assert "builder" in strip_paths(out)

    drive(body)


def test_inbox_shows_terminal_events_and_acks_them(project: str) -> None:
    async def body(daemon: Daemon) -> None:
        sent = await ok("send", "--role", "builder", "--context", "clear", "FAKE:result ok")
        await ok("wait", sent["id"])

        inbox = await ok("inbox")
        kinds = [event["kind"] for event in inbox["events"]]
        assert "job.done" in kinds
        assert inbox["events"][-1]["payload"]["job"] == sent["id"]

        acked = await ok("inbox", "--ack")
        assert acked["acked"]
        assert (await ok("inbox"))["events"] == []

    drive(body)


def test_wait_reports_a_timeout_rather_than_hanging(project: str) -> None:
    async def body(daemon: Daemon) -> None:
        sent = await ok("send", "--role", "builder", "--context", "clear", BLOCK)
        await running_job("builder")
        err = await fails("wait", sent["id"], "--timeout", "0.2")
        assert "timeout" in strip_paths(err.lower())

    drive(body)


def test_send_refuses_an_unknown_role_and_a_keep_with_no_session(project: str) -> None:
    async def body(daemon: Daemon) -> None:
        err = await fails("send", "--role", "nobody", "--context", "clear", "x")
        assert "nobody" in strip_paths(err)
        err = await fails("send", "--role", "builder", "--context", "keep", "x")
        assert "clear" in strip_paths(err)  # "send --context clear" is the advice §6 gives

    drive(body)


def test_send_reads_the_prompt_from_stdin(project: str) -> None:
    async def body(daemon: Daemon) -> None:
        out, err = io.StringIO(), io.StringIO()
        code = await asyncio.to_thread(
            main,
            ["--project", PROJECT, "send", "--role", "aux", "--context", "clear", "--stdin",
             "--json"],
            stdout=out,
            stderr=err,
            stdin=io.StringIO("FAKE:result from-stdin"),
        )
        assert code == 0, err.getvalue()
        job = json.loads(out.getvalue())
        assert job["prompt"] == "FAKE:result from-stdin"
        assert (await ok("wait", job["id"]))["result"] == "from-stdin"

    drive(body)


# ------------------------------------------- `send --prompt-file` (§4, §12, §19)

#: A prompt no shell could be trusted with: a redirection sign, a paren, both
#: kinds of quote and an interior newline. §4's point is that `--prompt-file`
#: means none of it is ever parsed by anything — it is read and sent verbatim.
VERBATIM = (
    'Run step 2 (the "hard" one) > notes.md\n'
    "It's prose, not a redirection: keep every byte."
)


def send_cli(*argv: str, stdin: str = "") -> tuple[int, str, str]:
    """`hands send …` in this thread: these cases fail before any socket call."""
    out, err = io.StringIO(), io.StringIO()
    code = main(
        ["--project", PROJECT, "send", *argv, "--json"],
        stdout=out,
        stderr=err,
        stdin=io.StringIO(stdin),
    )
    return code, out.getvalue(), err.getvalue()


def test_send_reads_the_prompt_from_a_file_byte_for_byte(project: str, tmp_path: Path) -> None:
    """§4: `--prompt-file` is the route for prose; the prompt never touches a
    command line, and every byte of it reaches the job record unchanged."""
    path = tmp_path / "prompt.txt"
    path.write_text(VERBATIM, encoding="utf-8")

    async def body(daemon: Daemon) -> None:
        job = await ok("send", "--role", "aux", "--context", "clear", "--prompt-file", str(path))
        assert job["prompt"] == VERBATIM
        assert (await ok("show", job["id"]))["prompt"] == VERBATIM

    drive(body)


def test_a_prompt_file_is_sent_with_its_trailing_newline(project: str, tmp_path: Path) -> None:
    """Byte for byte means byte for byte: an editor's trailing newline is part
    of the file and is sent, exactly as `--stdin` sends what it is given."""
    path = tmp_path / "prompt.txt"
    path.write_text("FAKE:result from-a-file\n", encoding="utf-8")

    async def body(daemon: Daemon) -> None:
        job = await ok("send", "--role", "aux", "--context", "clear", "--prompt-file", str(path))
        assert job["prompt"] == "FAKE:result from-a-file\n"
        assert (await ok("wait", job["id"]))["result"] == "from-a-file"

    drive(body)


def test_send_reads_a_prompt_file_outside_the_allowed_roots(
    project: str, tmp_path: Path
) -> None:
    """Deliberate: `files.allowed_roots` confines what the *daemon* writes for a
    role; `--prompt-file` is read by the CLI, running as the human."""
    path = tmp_path / "elsewhere" / "prompt.txt"
    path.parent.mkdir()
    path.write_text("FAKE:result outside-the-roots", encoding="utf-8")

    async def body(daemon: Daemon) -> None:
        job = await ok("send", "--role", "aux", "--context", "clear", "--prompt-file", str(path))
        assert (await ok("wait", job["id"]))["result"] == "outside-the-roots"

    drive(body)


def test_send_refuses_a_prompt_file_together_with_stdin_or_a_prompt(
    project: str, tmp_path: Path
) -> None:
    path = tmp_path / "prompt.txt"
    path.write_text("from the file", encoding="utf-8")
    for extra in (["a prompt"], ["--stdin"]):
        code, _, err = send_cli(
            "--role", "aux", "--context", "clear", "--prompt-file", str(path), *extra
        )
        assert code == 1, "a bad command line is a plain failure, not a refused file"
        for named in ("--prompt-file", "--stdin", "prompt"):
            assert named in strip_paths(err), f"the refusal must name all three routes: {err!r}"


def test_send_with_no_prompt_at_all_names_every_route(project: str) -> None:
    code, _, err = send_cli("--role", "aux", "--context", "clear")
    assert code == 1, "a bad command line is a plain failure, not a refused file"
    for named in ("--prompt-file", "--stdin", "prompt"):
        assert named in strip_paths(err)


def test_a_refused_prompt_file_and_a_wait_timeout_share_one_exit_code() -> None:
    """Exit 2 means the command did nothing: `wait` gave up waiting, or `send`
    refused its file before contacting the daemon. Two spellings, one value."""
    assert EXIT_REFUSED == 2
    assert EXIT_TIMEOUT == EXIT_REFUSED


def test_send_refuses_a_missing_prompt_file(project: str, tmp_path: Path) -> None:
    missing = tmp_path / "nope.txt"
    code, _, err = send_cli("--role", "aux", "--context", "clear", "--prompt-file", str(missing))
    assert code == EXIT_REFUSED
    assert str(missing) in err and "No such file" in strip_paths(err)


def test_send_refuses_a_directory_as_a_prompt_file(project: str, tmp_path: Path) -> None:
    code, _, err = send_cli("--role", "aux", "--context", "clear", "--prompt-file", str(tmp_path))
    assert code == EXIT_REFUSED
    assert str(tmp_path) in err and "directory" in strip_paths(err.lower())


def test_send_refuses_a_prompt_file_that_is_not_utf8(project: str, tmp_path: Path) -> None:
    path = tmp_path / "prompt.bin"
    path.write_bytes(b"a prompt\xff\xfe and then some")
    code, _, err = send_cli("--role", "aux", "--context", "clear", "--prompt-file", str(path))
    assert code == EXIT_REFUSED
    assert str(path) in err and "UTF-8" in strip_paths(err)


def test_every_prompt_route_refuses_the_same_not_utf8_bytes_the_same_way(
    project: str, tmp_path: Path
) -> None:
    """§4 (review 5 should-fix 7): one prompt, one refusal, on all three routes.

    `--prompt-file` read bytes and refused them itself. The other two never see
    bytes: under `PYTHONUTF8=1` the interpreter decodes both stdin and `argv`
    with `errors="surrogateescape"`, so the same file piped in — or pasted on
    the command line — arrives as lone surrogates, and nothing looked at them
    until the request was measured for the wire. There the encode raised, the
    human got `hands: 'utf-8' codec can't encode characters…`, and the exit code
    was 1, not 2: "fails somewhere other than at the place the human named", one
    route over, which is review 5 blocker 1's shape. All three carry their text
    into one check now and come back with one sentence.
    """
    raw = b"a prompt\xff\xfe and then some"
    # What `PYTHONUTF8=1` hands the client for those bytes, on stdin or in argv.
    text = raw.decode("utf-8", "surrogateescape")
    path = tmp_path / "prompt.bin"
    path.write_bytes(raw)
    argv = ["--role", "aux", "--context", "clear"]
    answers = {
        "--prompt-file": send_cli(*argv, "--prompt-file", str(path)),
        "--stdin": send_cli(*argv, "--stdin", stdin=text),
        "a prompt argument": send_cli(*argv, text),
    }

    tails = set()
    for route, (code, _out, err) in answers.items():
        assert code == EXIT_REFUSED, f"{route}: {err}"
        assert err.startswith(f"hands: {route}"), err  # the route names itself first
        _head, sep, tail = err.partition(": not UTF-8 text ")
        assert sep, f"{route} refused it as something else: {err!r}"
        tails.add(tail)
    assert len(tails) == 1, f"the routes give different reasons for the same bytes: {tails}"


def test_a_gate_reason_that_is_not_utf8_is_refused_where_the_prompt_would_be(
    project: str
) -> None:
    """The prompt is not the only string argv carries (§4, H-012).

    `--gate`, `--file` and `--content` reach the wire measurement the same way,
    so the same bytes in any of them used to die there with a codec message and
    exit 1 while the prompt beside them was refused politely. Every string in a
    request is checked before it is measured, under the name it was typed as.
    """
    reason = b"why\xff".decode("utf-8", "surrogateescape")
    code, _out, err = send_cli("--role", "aux", "--context", "clear", "--gate", reason, "go")
    assert code == EXIT_REFUSED, err
    assert "not UTF-8 text" in strip_paths(err)
    assert err.startswith("hands: --gate"), err


def test_send_refuses_an_empty_prompt_file(project: str, tmp_path: Path) -> None:
    """An empty prompt is a mistake, not an instruction — and the daemon refuses
    one anyway (§6); catching it here names the file that was empty."""
    for body_text in ("", "\n   \n"):
        path = tmp_path / "empty.txt"
        path.write_text(body_text, encoding="utf-8")
        code, _, err = send_cli("--role", "aux", "--context", "clear", "--prompt-file", str(path))
        assert code == EXIT_REFUSED
        assert str(path) in err and "empty" in strip_paths(err)


def test_send_refuses_an_oversized_prompt_file(project: str, tmp_path: Path) -> None:
    """§4: "the client refuses a missing, unreadable, empty or over-10 MB file".

    The cap is `runner.MAX_PROMPT_BYTES`, the one the daemon enforces at run
    time; enforcing it here means the error names the path the human typed
    instead of arriving from a round trip (review 3 should-fix 9).
    """
    path = tmp_path / "huge.txt"
    with path.open("wb") as handle:  # sparse: the size is the point, not the bytes
        handle.truncate(MAX_PROMPT_BYTES + 1)
    code, _, err = send_cli("--role", "aux", "--context", "clear", "--prompt-file", str(path))
    assert code == EXIT_REFUSED
    assert str(path) in err and str(MAX_PROMPT_BYTES) in err
    assert len(err.splitlines()) == 1, f"a refusal is one line: {err!r}"


def test_the_prompt_file_cap_is_checked_without_reading_the_file(
    project: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The size comes from `stat`, so a 10 MB mistake never enters memory."""
    path = tmp_path / "huge.txt"
    with path.open("wb") as handle:
        handle.truncate(MAX_PROMPT_BYTES + 1)

    def never(self: Path) -> bytes:
        raise AssertionError(f"the CLI read {self} before checking its size")

    monkeypatch.setattr(Path, "read_bytes", never)
    code, _, err = send_cli("--role", "aux", "--context", "clear", "--prompt-file", str(path))
    assert code == EXIT_REFUSED and str(path) in err


def test_a_prompt_file_at_exactly_the_cap_is_sent(project: str, tmp_path: Path) -> None:
    """The cap is a maximum, not a margin: the client refuses what the runner
    refuses (`> MAX_PROMPT_BYTES`) and nothing more."""
    path = tmp_path / "at-the-cap.txt"
    path.write_bytes(b"x" * MAX_PROMPT_BYTES)

    async def body(daemon: Daemon) -> None:
        job = await ok("send", "--role", "aux", "--context", "clear", "--prompt-file", str(path))
        assert len(job["prompt"].encode("utf-8")) == MAX_PROMPT_BYTES

    drive(body)


def test_no_bad_prompt_file_ever_reaches_the_daemon(
    project: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§4: all four refusals are the *client's*. No socket is opened for any of
    them — `call` is the CLI's only route to the daemon, and it is not taken."""
    missing = tmp_path / "nope.txt"
    unreadable = tmp_path / "unreadable"  # a directory: openable, not readable
    unreadable.mkdir()
    empty = tmp_path / "empty.txt"
    empty.write_text("\n   \n", encoding="utf-8")
    oversized = tmp_path / "huge.txt"
    with oversized.open("wb") as handle:
        handle.truncate(MAX_PROMPT_BYTES + 1)

    def never(*args: object, **kwargs: object) -> dict[str, object]:
        raise AssertionError("the CLI contacted the daemon about a bad --prompt-file")

    monkeypatch.setattr(cli_mod, "call", never)
    for path in (missing, unreadable, empty, oversized):
        code, out, err = send_cli("--role", "aux", "--context", "clear", "--prompt-file", str(path))
        assert code == EXIT_REFUSED, f"{path.name}: exit {code}"
        assert out == "", f"{path.name}: a refusal prints no job record"
        assert str(path) in err, f"{path.name}: the refusal must name the path: {err!r}"
        assert len(err.splitlines()) == 1, f"{path.name}: a refusal is one line: {err!r}"


# ------------------------- U4: the wire, the cap on it, and non-regular files
# §4 (and review 4 should-fix 3, 4): the client refuses a missing, unreadable,
# non-regular, empty or over-cap prompt "on either route", and the wire carries
# UTF-8 unescaped so the daemon's line room (the cap plus a quarter) fits any
# prompt the client accepted.


def refuse_the_daemon(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make any daemon contact an error: these refusals are the client's own."""

    def never(*args: object, **kwargs: object) -> dict[str, object]:
        raise AssertionError("the CLI contacted the daemon about a refused prompt")

    monkeypatch.setattr(cli_mod, "call", never)


def test_the_daemon_line_room_is_the_cap_plus_a_quarter() -> None:
    """§4: "the daemon's line room (cap plus one quarter)". The prompt is capped
    at the cap *as it appears on the wire*, and the quarter is the envelope's
    room — not a proof that an envelope fits it (H-012), which is why the client
    measures the whole request against this same number before it connects."""
    assert LINE_LIMIT == MAX_PROMPT_BYTES + MAX_PROMPT_BYTES // 4
    assert daemon_mod.LINE_LIMIT is LINE_LIMIT and cli_mod.LINE_LIMIT is LINE_LIMIT


def test_the_wire_size_of_a_prompt_is_the_json_it_becomes() -> None:
    """The client measures what `json.dumps(..., ensure_ascii=False)` will spend
    on the prompt without building it; the two must agree byte for byte."""
    sample = 'quote " backslash \\ nul \x00 bell \x07 tab \t line \n cjk 字 emoji \U0001f642'
    escaped = json.dumps(sample, ensure_ascii=False).encode("utf-8")
    assert cli_mod._wire_bytes(sample) == len(escaped) - 2  # minus the two quotes


def capture_one_request(where: Path, *argv: str) -> tuple[bytes, tuple[int, str, str]]:
    """Run `hands send` against a socket that records the request line verbatim."""
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(str(where))
    server.listen(1)
    seen: list[bytes] = []

    def serve() -> None:
        conn, _ = server.accept()
        with conn, conn.makefile("rwb") as stream:
            seen.append(stream.readline())
            stream.write(b'{"jsonrpc": "2.0", "id": 1, "result": {}}\n')
            stream.flush()

    thread = threading.Thread(target=serve)
    thread.start()
    try:
        result = send_cli(*argv, "--socket", str(where))
    finally:
        thread.join(TIMEOUT)
        server.close()
    assert seen, "the client never sent a request"
    return seen[0], result


def test_the_request_carries_utf8_unescaped(project: str, tmp_path: Path) -> None:
    """§4: "the wire carries UTF-8 unescaped". `ensure_ascii` at its default
    turned every 3-byte CJK character into 6 bytes of `\\uXXXX` (should-fix 3)."""
    line, (code, _, err) = capture_one_request(
        tmp_path / "capture.sock", "--role", "aux", "--context", "clear", "字 prompt"
    )
    assert code == 0, err
    wire = line.decode("utf-8")  # the whole request, as the daemon's reader sees it
    assert "字".encode() in line, "the prompt is not on the wire as UTF-8"
    assert "\\u" not in strip_paths(wire), f"the client escaped what it need not: {wire[:200]!r}"


def test_a_cjk_prompt_file_under_the_cap_reaches_the_daemon(project: str, tmp_path: Path) -> None:
    """9 MiB of CJK is under the cap, 9 MiB on the wire, and fits the daemon's
    line room. It used to die at `[Errno 32] Broken pipe` (should-fix 3)."""
    text = "字" * (3 * 1024 * 1024)  # 3 bytes each: 9 MiB of UTF-8
    path = tmp_path / "cjk.txt"
    path.write_text(text, encoding="utf-8")
    assert path.stat().st_size == 9 * 1024 * 1024 < MAX_PROMPT_BYTES

    async def body(daemon: Daemon) -> None:
        job = await ok("send", "--role", "aux", "--context", "clear", "--prompt-file", str(path))
        assert job["prompt"] == text

    drive(body)


def test_send_refuses_a_prompt_file_that_only_fits_before_escaping(
    project: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A file at the cap whose bytes inflate as JSON is refused here, naming the
    path — not at a broken pipe with nothing in the daemon log (should-fix 3).
    A quote costs 2 bytes on the wire and a NUL costs 6."""
    refuse_the_daemon(monkeypatch)
    for name, byte in (("quotes.txt", b'"'), ("nul.txt", b"\x00")):
        path = tmp_path / name
        path.write_bytes(byte * MAX_PROMPT_BYTES)  # at the cap, not over it
        code, out, err = send_cli("--role", "aux", "--context", "clear", "--prompt-file", str(path))
        assert code == EXIT_REFUSED, f"{name}: exit {code}"
        assert str(path) in err and str(MAX_PROMPT_BYTES) in err, f"{name}: {err!r}"
        assert out == "", f"{name}: a refusal prints no job record"
        assert len(err.splitlines()) == 1, f"{name}: a refusal is one line: {err!r}"


def test_send_refuses_a_prompt_file_that_is_not_a_regular_file(
    project: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """review 4 should-fix 4: a FIFO reports 0 bytes to `stat`, passes every
    other refusal, and then blocks forever with no writer. `stat` answers "not a
    regular file" too, so none of these is ever opened."""
    fifo = tmp_path / "fifo"
    os.mkfifo(fifo)
    directory = tmp_path / "dir"
    directory.mkdir()
    endpoint = tmp_path / "endpoint.sock"
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(str(endpoint))
    cases = [fifo, directory, endpoint]
    if Path("/dev/zero").exists():  # a character device: an endless read
        cases.append(Path("/dev/zero"))

    def never_read(self: Path) -> bytes:
        raise AssertionError(f"the CLI opened {self} instead of refusing it")

    monkeypatch.setattr(Path, "read_bytes", never_read)
    refuse_the_daemon(monkeypatch)
    try:
        for path in cases:
            code, out, err = send_cli(
                "--role", "aux", "--context", "clear", "--prompt-file", str(path)
            )
            assert code == EXIT_REFUSED, f"{path}: exit {code}"
            assert str(path) in err, f"{path}: the refusal must name the path: {err!r}"
            assert "regular file" in strip_paths(err), f"{path}: {err!r}"
            assert out == "" and len(err.splitlines()) == 1, f"{path}: {err!r}"
    finally:
        server.close()


def test_the_same_oversized_prompt_refuses_the_same_way_on_both_routes(
    project: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§4: the refusals are the client's "on either route" — the same bytes get
    the same message and the same exit code from `--prompt-file` and `--stdin`,
    and neither reaches the daemon (should-fix 3)."""
    over = "x" * (MAX_PROMPT_BYTES + 1)
    path = tmp_path / "huge.txt"
    path.write_text(over, encoding="utf-8")
    refuse_the_daemon(monkeypatch)
    code_file, out_file, err_file = send_cli(
        "--role", "aux", "--context", "clear", "--prompt-file", str(path)
    )
    code_stdin, out_stdin, err_stdin = send_cli(
        "--role", "aux", "--context", "clear", "--stdin", stdin=over
    )
    assert code_file == EXIT_REFUSED and code_stdin == EXIT_REFUSED
    assert out_file == "" and out_stdin == ""
    said = f"is {MAX_PROMPT_BYTES + 1} bytes, over the {MAX_PROMPT_BYTES} byte cap of §2"
    assert err_file == f"hands: --prompt-file {path} {said}" + err_file.split(said)[1]
    assert err_stdin == f"hands: --stdin {said}" + err_stdin.split(said)[1]
    assert err_file.split(said)[1] == err_stdin.split(said)[1], "one message, one advice"


def test_send_refuses_an_empty_stdin_prompt(
    project: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§4 refuses an empty prompt "on either route": `--stdin` had no check at
    all, so the same mistake came back from the daemon as exit 1."""
    refuse_the_daemon(monkeypatch)
    for text in ("", "\n   \n"):
        code, out, err = send_cli("--role", "aux", "--context", "clear", "--stdin", stdin=text)
        assert code == EXIT_REFUSED, f"{text!r}: exit {code}"
        assert "--stdin is empty" in strip_paths(err), f"{text!r}: {err!r}"
        assert out == ""


def test_hands_help_says_what_exit_2_means(capsys: pytest.CaptureFixture[str]) -> None:
    """review 4 should-fix 5: exit 2 is a refusal *or* a timeout, and the one
    reader of it that is not a machine reads `--help` and the docs."""
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    # One line or three is argparse's business, not the product's claim.
    said = " ".join(capsys.readouterr().out.split())
    assert "2 when the client did not deliver a completed request" in strip_paths(said)


def test_send_help_lists_the_prompt_file_route(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["send", "--help"])
    assert exc.value.code == 0
    assert "--prompt-file" in strip_paths(capsys.readouterr().out)


def test_global_flags_work_before_and_after_the_command(project: str) -> None:
    async def body(daemon: Daemon) -> None:
        out, err = io.StringIO(), io.StringIO()
        code = await asyncio.to_thread(
            main, ["--json", "--project", PROJECT, "status"], stdout=out, stderr=err
        )
        assert code == 0, err.getvalue()
        assert json.loads(out.getvalue())["daemon"]["project"] == PROJECT

    drive(body)


def test_jobs_lists_recent_jobs_newest_first(project: str) -> None:
    async def body(daemon: Daemon) -> None:
        first = await ok("send", "--role", "builder", "--context", "clear", "FAKE:result one")
        await ok("wait", first["id"])
        second = await ok("send", "--role", "aux", "--context", "clear", "FAKE:result two")
        await ok("wait", second["id"])

        listed = await ok("jobs")
        assert [job["id"] for job in listed["jobs"]] == [second["id"], first["id"]]
        only_aux = await ok("jobs", "--role", "aux")
        assert [job["id"] for job in only_aux["jobs"]] == [second["id"]]
        assert (await ok("show", first["id"]))["prompt"] == "FAKE:result one"

    drive(body)


# ----------------------- U1: the whole request on the wire (§4, H-012)
# §4's `send` row: "the client then measures the **whole request** as it will go
# on the wire (prompt, `--file` payloads, gate, envelope) and refuses before
# connecting if it exceeds the daemon's line room, so a request never fails
# inside the socket (H-012)". Review 5 blocker 1 is the request the prompt-sized
# check of U4 let through: an at-cap prompt beside twelve `--file` values of
# backslashes, which died at `[Errno 32] Broken pipe` with nothing in the
# daemon log — the fault class review 4 should-fix 3 named, one field over.

#: The reviewer's reproduction, to the byte: twelve `--file` values of 131 000
#: backslashes each (a backslash costs 2 bytes as JSON) beside a prompt at the
#: cap. 13 630 051 bytes against a 13 107 200 byte line room.
REPRO_FILES = 12
REPRO_BACKSLASHES = 131_000


def repro_files(tmp_path: Path) -> list[str]:
    """The twelve `--file path=content` values of the reviewer's reproduction."""
    content = "\\" * REPRO_BACKSLASHES  # not inside the f-string: 3.11 forbids it
    return [f"{tmp_path / f'payload-{index}.txt'}={content}" for index in range(REPRO_FILES)]


def repro_argv(tmp_path: Path, prompt_path: Path) -> list[str]:
    """`hands send` as the reviewer ran it: an at-cap prompt file and the twelve."""
    prompt_path.write_bytes(b"x" * MAX_PROMPT_BYTES)
    argv = ["--role", "aux", "--context", "clear"]
    for spec in repro_files(tmp_path):
        argv += ["--file", spec]
    return [*argv, "--prompt-file", str(prompt_path)]


def refuse_the_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make opening a socket an error: this refusal happens *before* connecting.

    `refuse_the_daemon` cannot say it any more — the measurement lives inside
    `call`, so patching `call` out would patch the thing under test out with it.
    """

    def never(*args: object, **kwargs: object) -> object:
        raise AssertionError("the CLI opened a socket for a request it must refuse")

    monkeypatch.setattr(cli_mod.socket, "socket", never)


def test_the_wire_size_of_a_request_is_the_line_the_client_writes() -> None:
    """The client measures the request without building it, so the count and
    `json.dumps(..., ensure_ascii=False)` must agree byte for byte — over what a
    request actually carries: quotes, backslashes, NULs, CJK, and `--file`
    payloads in a list beside non-strings (`true`, `null`, a number)."""
    awkward = 'quote " backslash \\ nul \x00 tab \t cjk 字 emoji \U0001f642'
    requests: list[dict[str, Any]] = [
        {"jsonrpc": "2.0", "id": 1, "method": "status", "params": {}},
        {
            "jsonrpc": "2.0", "id": 1, "method": "send",
            "params": {
                "role": "aux", "context": "clear", "prompt": awkward,
                "file": [f"/tmp/{awkward}=value {awkward}", "/tmp/b=plain"],
                "gate": awkward,
            },
        },
        {
            "jsonrpc": "2.0", "id": 1, "method": "jobs",
            "params": {"role": None, "n": 20, "ack": True, "grep": awkward},
        },
        {"jsonrpc": "2.0", "id": 1, "method": "send", "params": {"prompt": "\\" * 4096}},
    ]
    for request in requests:
        built = json.dumps(request, ensure_ascii=False).encode("utf-8")
        assert cli_mod._wire_size(request) == len(built), request["method"]


def test_send_refuses_a_request_whose_files_overflow_the_line_room(
    project: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review 5 blocker 1: each half fits, the request does not. One line, exit
    2, before any socket is opened — and it names the total, the limit and the
    part to move (`hands put`), because "too big" without a size is not actionable.
    """
    refuse_the_socket(monkeypatch)
    code, out, err = send_cli(*repro_argv(tmp_path, tmp_path / "at-the-cap.txt"))
    assert code == EXIT_REFUSED, f"exit {code}: {err!r}"
    assert out == "", "a refusal prints no job record"
    assert len(err.splitlines()) == 1, f"a refusal is one line: {err!r}"
    said = strip_paths(err)
    assert str(LINE_LIMIT) in said, f"the refusal never names the limit: {said!r}"
    assert "the prompt" in strip_paths(err), said
    assert str(MAX_PROMPT_BYTES) in said, said
    # The prompt and the twelve payloads, to the byte; the rest of the line is
    # the envelope (the method, the keys, the role, the twelve paths).
    carried = MAX_PROMPT_BYTES + sum(
        len(spec.encode("utf-8")) + REPRO_BACKSLASHES for spec in repro_files(tmp_path)
    )
    assert carried > LINE_LIMIT, "the reproduction no longer overflows the line room"
    for size in range(carried, carried + 256):  # the envelope is the only unknown
        if str(size) in err:
            break
    else:
        raise AssertionError(f"the refusal never names the request's size: {said!r}")


def test_the_largest_part_of_an_over_long_request_is_the_one_named(
    project: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The message points at the part worth moving. With a small prompt and one
    fat `--file`, that is the file — named by its path, not by "a file"."""
    refuse_the_socket(monkeypatch)
    fat = tmp_path / "fat.txt"
    spec = f"{fat}={'x' * (LINE_LIMIT + 1)}"
    code, _, err = send_cli("--role", "aux", "--context", "clear", "--file", spec, "go")
    assert code == EXIT_REFUSED
    assert f"--file {fat}" in err, f"the refusal must name the fattest part: {err!r}"
    # The size named is that value's own: `path=content`, nothing escaped in it.
    assert f"at {len(spec.encode('utf-8'))} bytes" in err, err


def test_every_prompt_route_refuses_the_same_over_long_request(
    project: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§4's three routes carry the same bytes to the same daemon, so the same
    request gets the same refusal on `--prompt-file`, `--stdin` and a positional
    prompt: one message, one exit code, no socket (review 4 should-fix 3)."""
    refuse_the_socket(monkeypatch)
    prompt = "y" * MAX_PROMPT_BYTES
    path = tmp_path / "prompt.txt"
    path.write_text(prompt, encoding="utf-8")
    files: list[str] = []
    for spec in repro_files(tmp_path):
        files += ["--file", spec]
    common = ["--role", "aux", "--context", "clear", *files]
    answers = [
        send_cli(*common, "--prompt-file", str(path)),
        send_cli(*common, "--stdin", stdin=prompt),
        send_cli(*common, prompt),
    ]
    for code, out, err in answers:
        assert code == EXIT_REFUSED and out == "", f"{code}: {err!r}"
    messages = {strip_paths(err) for _, _, err in answers}
    assert len(messages) == 1, f"one request, three answers: {messages}"


def test_the_reviewers_reproduction_never_reaches_the_daemon(
    project: str, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The gate of this unit, against a real daemon on a real socket: the
    reproduction is refused by the client, the daemon logs nothing about it, and
    no job is created. It used to arrive as a broken pipe and exit 1."""
    caplog.set_level(logging.DEBUG, logger="hands")
    argv = repro_argv(tmp_path, tmp_path / "at-the-cap.txt")

    async def body(daemon: Daemon) -> None:
        assert any(record.name == "hands.daemon" for record in caplog.records), (
            "nothing of the daemon's log is captured here, so an empty log proves nothing"
        )
        before = len(caplog.records)
        code, out, err = await cli("send", *argv, "--json")
        after = caplog.records[before:]
        assert code == EXIT_REFUSED, f"exit {code}: {err!r}"
        assert out == "" and len(err.splitlines()) == 1, f"{out!r} {err!r}"
        assert "Broken pipe" not in strip_paths(err), err
        assert after == [], f"the daemon logged a request it must never have read: {after}"
        assert (await ok("jobs"))["jobs"] == [], "a refused request creates no job"

    drive(body)


def test_a_request_at_the_line_room_is_sent_and_one_byte_more_is_refused(
    project: str, workdir: Path, tmp_path: Path
) -> None:
    """The limit is a maximum, not a margin, and the client's count is the
    daemon's: a request whose line is exactly `LINE_LIMIT` bytes is read, run and
    its file written, and the same request one byte fatter is refused here."""
    target = workdir / "payload.txt"
    prompt = "FAKE:result at the limit"

    def request_of(content: str) -> dict[str, Any]:
        params = {
            "role": "aux", "context": "clear", "prompt": prompt,
            "file": [f"{target}={content}"],
        }
        return {"jsonrpc": "2.0", "id": 1, "method": "send", "params": params}

    room = LINE_LIMIT - cli_mod._wire_size(request_of(""))
    assert room > 0, "the envelope alone is over the line room"
    content = "x" * room  # one byte of wire per byte of content
    assert cli_mod._wire_size(request_of(content)) == LINE_LIMIT

    async def body(daemon: Daemon) -> None:
        sent = await ok(
            "send", "--role", "aux", "--context", "clear",
            "--file", f"{target}={content}", prompt,
        )
        done = await ok("wait", sent["id"])
        assert done["state"] == "done", done
        assert target.read_text(encoding="utf-8") == content
        code, out, err = await cli("send", "--role", "aux", "--context", "clear",
            "--file", f"{target}={content}x", prompt, "--json")
        assert code == EXIT_REFUSED, f"exit {code}: {err!r}"
        assert out == "" and str(LINE_LIMIT + 1) in err, err

    drive(body)


# ------------------- U4: one tree walk; positionals keep their names (§4, §23)
# Review 6 should-fix 4: the UTF-8 check walked top-level strings and lists of
# strings while the size measurement recursed and `json.dumps` encoded dict keys
# too, so a string one level down died inside the measurement as a bare
# `UnicodeEncodeError`. Should-fix 5: a positional was refused under a flag the
# human never typed (`--job`, `--path`).

#: What `PYTHONUTF8=1` hands the client for `\xff` in argv: a lone surrogate.
BAD = b"bad-\xff".decode("utf-8", "surrogateescape")


def _request(params: dict[Any, Any], method: str = "send") -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}


def _string_slots(value: Any, path: tuple[Any, ...] = ()) -> list[tuple[tuple[Any, ...], str]]:
    """Every place a string sits in `value` — values and dict keys, any depth —
    as a path; ("key", k) marks the key itself rather than what it holds."""
    slots: list[tuple[tuple[Any, ...], str]] = []
    if isinstance(value, str):
        slots.append((path, "value"))
    elif isinstance(value, dict):
        for key, item in value.items():
            if isinstance(key, str):
                slots.append(((*path, key), "key"))
            slots += _string_slots(item, (*path, key))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            slots += _string_slots(item, (*path, index))
    return slots


def _spoiled(value: Any, path: tuple[Any, ...], kind: str) -> Any:
    """`value` with the string at `path` (or the key at it) made un-encodable."""
    if not path:
        return value + BAD if kind == "value" else value
    head, rest = path[0], path[1:]
    if isinstance(value, list):
        return [_spoiled(item, rest, kind) if index == head else item
                for index, item in enumerate(value)]
    out: dict[Any, Any] = {}
    for key, item in value.items():
        if key != head:
            out[key] = item
        elif kind == "key" and not rest:
            out[key + BAD] = item
        else:
            out[key] = _spoiled(item, rest, kind)
    return out


#: Nested params no command builds today, and one that it does.
NESTED_PARAMS: list[dict[Any, Any]] = [
    {"files": {"a": "v"}},
    {"file": [["x"]]},
    {"gate": [{"k": "v"}, "plain"]},
    {"gate": {"a": [{"b": [[{"c": 'quote " cjk 字'}]]}]}, "n": 3, "ack": True},
    {"role": "aux", "context": "clear", "prompt": "go", "file": ["/tmp/a=1", "/tmp/b=2"]},
]


def test_a_string_at_any_depth_of_a_request_is_refused_as_not_utf8() -> None:
    """The review's three shapes, then every string slot — value or key — of
    every nested request above: each is §4's refusal, never a codec error."""
    reviewed = [
        ({"files": {"a": BAD}}, "files"),
        ({"files": {BAD: "v"}}, "files"),
        ({"file": [[BAD]]}, "--file"),
        ({"gate": [{"k": [{"deep": {"deeper": [BAD]}}]}]}, "--gate"),
    ]
    for params, label in reviewed:
        with pytest.raises(cli_mod.PromptError) as caught:
            cli_mod._checked_request(_request(params))
        said = str(caught.value)
        assert said.startswith(f"{label}"), said
        assert ": not UTF-8 text (" in strip_paths(said), said
    tried = 0
    for params in NESTED_PARAMS:
        cli_mod._checked_request(_request(params))  # clean, it passes
        for path, kind in _string_slots(params):
            spoiled = _spoiled(params, path, kind)
            with pytest.raises(cli_mod.PromptError, match="not UTF-8 text"):
                cli_mod._checked_request(_request(spoiled))
            tried += 1
    assert tried >= 25, tried  # the slots were really enumerated


def test_the_size_walk_measures_only_strings_the_utf8_walk_checks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One tree: every string the measurement counts was checked first, every
    string a request carries (keys included) is checked, and the count is still
    `json.dumps(..., ensure_ascii=False)` to the byte (H-012)."""
    measured: list[str] = []
    checked: list[str] = []
    wire_bytes, utf8_bytes = cli_mod._wire_bytes, cli_mod._utf8_bytes

    def counting(text: str) -> int:
        measured.append(text)
        return wire_bytes(text)

    def checking(text: str, where: str) -> bytes:
        checked.append(text)
        return utf8_bytes(text, where)

    monkeypatch.setattr(cli_mod, "_wire_bytes", counting)
    monkeypatch.setattr(cli_mod, "_utf8_bytes", checking)
    shapes = [*NESTED_PARAMS, {"odd keys": {1: "one", None: "nil", 2.5: ["x", {}, []]}}]
    for params in shapes:
        request = _request(params)
        measured.clear()
        checked.clear()
        cli_mod._checked_request(request)
        carried = [text for path, kind in _string_slots(request) for text in [
            (path[-1] if kind == "key" else _at(request, path))]]
        assert measured, params
        assert sorted(measured) == sorted(checked), params
        assert sorted(carried) == sorted(checked), params
        built = json.dumps(request, ensure_ascii=False).encode("utf-8")
        assert cli_mod._wire_size(request) == len(built), params


def _at(value: Any, path: tuple[Any, ...]) -> Any:
    for step in path:
        value = value[step]
    return value


def _cli(argv: list[str]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    code = main(["--project", PROJECT, *argv], stdout=out, stderr=err, stdin=io.StringIO(""))
    return code, out.getvalue(), err.getvalue()


#: Every command of §4 that takes a positional, and the argv that puts BAD in it.
POSITIONALS = [
    ("job", ["result", BAD, "--json"]),
    ("job", ["show", BAD, "--json"]),
    ("job", ["open", BAD, "--json"]),
    ("job", ["open", BAD]),
    ("job", ["wait", BAD, "--json"]),
    ("job", ["log", BAD, "--json"]),
    ("job", ["log", BAD]),  # the page-walking route
    ("job", ["cancel", BAD, "--json"]),
    ("job", ["approve", BAD, "--json"]),
    ("job", ["deny", BAD, "--json"]),
    ("path", ["put", BAD, "--content", "x", "--json"]),
    ("path", ["get", BAD, "--json"]),
    ("path", ["ls", BAD, "--json"]),
    ("prompt", ["send", "--role", "aux", "--context", "clear", BAD, "--json"]),
]


@pytest.mark.parametrize(("name", "argv"), POSITIONALS, ids=lambda v: str(v))
def test_a_positional_is_refused_under_the_name_the_human_typed(
    project: str, monkeypatch: pytest.MonkeyPatch, name: str, argv: list[str]
) -> None:
    """Review 6 should-fix 5: `hands result $'job-\\xff'` said `--job`, a flag
    that does not exist. A positional is named as `hands --help` names it."""
    refuse_the_socket(monkeypatch)
    code, out, err = _cli(argv)
    assert code == EXIT_REFUSED, f"exit {code}: {err!r}"
    assert out == "" and len(err.splitlines()) == 1, (out, err)
    assert err.startswith(f"hands: a {name} argument: not UTF-8 text ("), err
    assert f"--{name}" not in strip_paths(err), err


#: A real flag keeps its flag name.
FLAGS = [
    ("--reason", ["cancel", "j1", "--reason", BAD, "--json"]),
    ("--reason", ["approve", "j1", "--reason", BAD, "--json"]),
    ("--quote", ["deny", "j1", "--human-confirmed", "--quote", BAD, "--json"]),
    ("--content", ["put", "/tmp/x", "--content", BAD, "--json"]),
    ("--from", ["put", "/tmp/x", "--from", BAD, "--json"]),
    ("--for", ["wait", "--for", BAD, "--json"]),
    ("--grep", ["jobs", "--grep", BAD, "--json"]),
    ("--role", ["tail", "--role", BAD, "--json"]),
    ("-f", ["log", "-f", BAD]),
    ("--gate", ["send", "--role", "aux", "--context", "clear", "--gate", BAD, "go", "--json"]),
    ("--file /tmp/p", ["send", "--role", "aux", "--context", "clear",
                       "--file", f"/tmp/p={BAD}", "go", "--json"]),
]


@pytest.mark.parametrize(("label", "argv"), FLAGS, ids=lambda v: str(v))
def test_a_flag_is_refused_under_its_flag_name(
    project: str, monkeypatch: pytest.MonkeyPatch, label: str, argv: list[str]
) -> None:
    refuse_the_socket(monkeypatch)
    code, out, err = _cli(argv)
    assert code == EXIT_REFUSED, f"exit {code}: {err!r}"
    assert out == "", out
    assert err.startswith(f"hands: {label}: not UTF-8 text ("), err


def test_every_param_of_every_command_is_named_as_its_parser_names_it() -> None:
    """The whole space: each key `_PARAMS` sends, for each of §4's commands, is
    refused under the name argparse gives the argument it came from — `a <dest>
    argument` for a positional, its option string for a flag. `send`'s prompt is
    the one exception, and it is refused earlier under its route's name (above);
    at the request it is "the prompt", because three routes fill it."""
    from hands.cli import _PARAMS, build_parser

    class Blank(argparse.Namespace):
        def __getattr__(self, name: str) -> None:
            return None

    commands = next(
        action for action in build_parser()._actions
        if isinstance(action, argparse._SubParsersAction)
    ).choices
    named = 0
    for command, params_of in _PARAMS.items():
        for key in params_of(Blank()):
            action = next(
                action for action in commands[command]._actions
                if action.dest in (key, f"{key}_")
            )
            if command == "send" and key == "prompt":
                expected = "the prompt"
            elif action.option_strings:
                expected = next(
                    (flag for flag in action.option_strings if flag.startswith("--")),
                    action.option_strings[0],
                )
            else:
                expected = f"a {action.dest} argument"
            with pytest.raises(cli_mod.PromptError) as caught:
                cli_mod._checked_request(_request({key: BAD}, command))
            assert str(caught.value).startswith(f"{expected}"), (command, key, caught.value)
            assert not str(caught.value).startswith(f"{expected}-"), (command, key)
            named += 1
    assert named >= 30, named


# --------------------------------------------------- the surface of §4 (§9)


SECTION_4 = [
    "send", "wait", "result", "jobs", "show", "open", "log", "cancel",
    "put", "get", "ls", "tail", "inbox", "pipeline", "approve", "deny",
    "pause", "resume", "status", "notify", "doctor",
]


def test_help_lists_every_command_of_section_4(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    printed = capsys.readouterr().out
    for command in SECTION_4:
        assert command in strip_paths(printed), (
            f"`{command}` (DESIGN §4) is missing from hands --help"
        )


# Every command of §4 is implemented: the last stub (`doctor`, U10) landed with
# `hands.doctor`, and its own tests are in tests/test_doctor.py.


def test_the_api_method_names_are_exactly_the_command_names() -> None:
    """§9: the MCP face wraps these one-to-one, so the three lists cannot drift."""
    from hands.api import Api
    from hands.cli import _PARAMS

    assert sorted(Api.COMMANDS) == sorted(SECTION_4)
    for name in Api.COMMANDS:
        assert callable(getattr(Api, name, None)), f"Api has no method for `{name}`"
    assert sorted(_PARAMS) == sorted(SECTION_4)


# ------------------------------------------------------------ daemon hygiene


def test_the_socket_is_removed_on_shutdown_and_refuses_a_second_daemon(
    project: str, tmp_home: Path
) -> None:
    sock = tmp_home / ".hands" / "handsd.sock"

    async def body(daemon: Daemon) -> None:
        assert sock.exists()
        second = Daemon(load_config(PROJECT))
        with pytest.raises(Exception, match="already"):
            await second.start()

    drive(body)
    assert not sock.exists()


def test_the_cli_says_so_when_no_daemon_is_listening(project: str) -> None:
    code, _out, err = main_capture(["--project", PROJECT, "status"])
    assert code != 0
    # U2: the socket path ends in `handsd.sock`, so the bare word proved nothing.
    assert "is handsd running?" in strip_paths(err)


def main_capture(argv: list[str]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    code = main(argv, stdout=out, stderr=err)
    return code, out.getvalue(), err.getvalue()


def test_status_says_queue_depth_is_capacity_and_what_the_monitor_sees(project: str) -> None:
    """U6: `queue_depth` is how many *may* be queued (§4, §13); `queued` is what
    is waiting. The monitor line claims only what §5 claims."""

    async def body(daemon: Daemon) -> None:
        status = await ok("status")
        builder = status["roles"]["builder"]
        assert builder["queue_depth"] == 1
        assert builder["queued"] == []
        # U2 (review should-fix 8): the alias is asserted on aux, whose depth is 4
        # (§6/§13), not on builder, where depth 1 makes a hardcoded literal pass.
        aux = status["roles"]["aux"]
        assert aux["queue_depth"] == 4
        assert aux["queue_capacity"] == 4  # alias, §4 — the role's capacity, not a constant
        assert aux["queue_capacity"] == aux["queue_depth"]
        assert aux["queue_capacity"] != builder["queue_capacity"]
        assert aux["queued"] == []

        code, out, _ = await cli("status")
        assert code == 0
        assert "capacity" in strip_paths(out)
        assert "queue_depth" in strip_paths(out)
        # §5: a stall is no progress *and* no liveness, and nothing more.
        assert "no progress and no liveness" in strip_paths(out)
        assert "busy-wait on a nested run is not a stall" in strip_paths(out)
        # U1: the built-in monitor is the one deciding here; there is no script.
        assert (await ok("status"))["monitor"]["source"] == "builtin"
        assert "for 40m" in strip_paths(out)  # the §13 default, spelled as it is configured
        assert "--pids" not in strip_paths(out)

    drive(body)


FAKE_MONITOR = Path(__file__).with_name("fake_monitor.py")


def _ops_project(tmp_home: Path, workdir: Path, tmp_path: Path) -> Path:
    """A config whose `[ops]` monitor is the deciding one (§5). Returns the script."""
    ops = tmp_path / "ops"
    ops.mkdir(exist_ok=True)
    script = ops / "watch_monitor.sh"
    shutil.copy(FAKE_MONITOR, script)
    script.chmod(0o755)
    write_project(
        tmp_home,
        config_body(
            tmp_home,
            workdir,
            extra=f'\n[ops]\nrepo = "{ops}"\nmonitor_cmd = "watch_monitor.sh"\n',
        ),
    )
    return script


def test_status_names_the_ops_script_and_its_flags_when_ops_decides(
    tmp_home: Path, workdir: Path, tmp_path: Path
) -> None:
    """U1 (§4 status row, §5, §19): with `[ops]` configured the ops script is the
    monitor that decides, and hands gives it exactly `--pids/--transcript/--base`.
    The built-in stall rule is not what is deciding, so status must not state it."""
    script = _ops_project(tmp_home, workdir, tmp_path)

    async def body(daemon: Daemon) -> None:
        monitor = (await ok("status"))["monitor"]
        assert monitor["source"] == "ops"
        assert monitor["cmd"] == str(script)
        assert monitor["flags"] == ["--pids", "--transcript", "--base"]

        code, out, _ = await cli("status")
        assert code == 0
        assert str(script) in out
        for flag in ("--pids", "--transcript", "--base"):
            assert flag in strip_paths(out)
        # The built-in rule is not the one deciding here, and stall_minutes
        # never reaches the script. U2 (review blocker 2): this is asserted on
        # the stall sentence, never on a bare "40" — the monitor line carries the
        # ops script's path as well, so under `--basetemp .../pytest-1340` the
        # substring matched the path and the gate went red about one run in ten.
        assert "no progress and no liveness" not in strip_paths(out)
        assert "for 40m" not in strip_paths(out)
        assert "the script decides; hands fills --pids --transcript --base" in strip_paths(out)

    drive(body)


def test_status_says_stall_detection_is_off_at_zero_minutes(tmp_home: Path, workdir: Path) -> None:
    """U1: `monitor.stall_minutes = 0` is stall detection off, not "for 0m"."""
    write_project(
        tmp_home, config_body(tmp_home, workdir, extra="\n[monitor]\nstall_minutes = 0\n")
    )

    async def body(daemon: Daemon) -> None:
        assert (await ok("status"))["monitor"]["stall_minutes"] == 0

        code, out, _ = await cli("status")
        assert code == 0
        # U2: the sentence, not "off" and not a bare "0m" — every line of `status`
        # carries a tmpdir path, and the monitor line is one of them.
        assert "stall detection off (monitor.stall_minutes = 0)" in strip_paths(out)
        assert "for 0m" not in strip_paths(out)
        assert "no progress and no liveness" not in strip_paths(out)

    drive(body)
