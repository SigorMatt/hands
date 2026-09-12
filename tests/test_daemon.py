"""U3: the daemon, the local API and the CLI (DESIGN §3, §4, §6, §9, §13).

Every test here drives the *real* unix socket: the daemon runs in the test's
event loop and the CLI runs in a worker thread, exactly as `hands` runs at a
terminal. Nothing is mocked but the `claude` binary (`tests/fake_claude.py`).
"""

from __future__ import annotations

import asyncio
import io
import json
import os
import shutil
import socket
import threading
from pathlib import Path

import pytest

from conftest import strip_paths
from hands import cli as cli_mod
from hands import daemon as daemon_mod
from hands.cli import EXIT_REFUSED, EXIT_TIMEOUT, main
from hands.config import load_config
from hands.daemon import Daemon
from hands.runner import MAX_PROMPT_BYTES
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
    at the cap *as it appears on the wire*, so the quarter is the envelope's."""
    assert daemon_mod._LINE_LIMIT == MAX_PROMPT_BYTES + MAX_PROMPT_BYTES // 4


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
