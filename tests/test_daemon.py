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
from pathlib import Path

import pytest

from hands.cli import main
from hands.config import load_config
from hands.daemon import Daemon
from hands.spool import Spool
from harness import BLOCK, PROJECT, cli, config_body, drive, fails, ok, running_job, write_project

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
        assert job_id in out
        assert "done" in out
        assert "VERDICT: PASS" in out

    drive(body)


def test_a_second_send_to_a_busy_role_queues_and_a_third_is_refused(project: str) -> None:
    async def body(daemon: Daemon) -> None:
        first = await ok("send", "--role", "builder", "--context", "clear", BLOCK)
        await running_job("builder")

        second = await ok("send", "--role", "builder", "--context", "clear", "FAKE:result second")
        assert second["state"] == "queued"

        err = await fails("send", "--role", "builder", "--context", "clear", "FAKE:result third")
        assert "queue" in err.lower()

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
        assert "queue" in err.lower()

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
        assert "monitor" in status
        code, out, _ = await cli("status")
        assert code == 0
        assert "builder" in out

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
        assert "timeout" in err.lower()

    drive(body)


def test_send_refuses_an_unknown_role_and_a_keep_with_no_session(project: str) -> None:
    async def body(daemon: Daemon) -> None:
        err = await fails("send", "--role", "nobody", "--context", "clear", "x")
        assert "nobody" in err
        err = await fails("send", "--role", "builder", "--context", "keep", "x")
        assert "clear" in err  # "send --context clear" is the advice §6 gives

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
        assert command in printed, f"`{command}` (DESIGN §4) is missing from hands --help"


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
    assert "handsd" in err


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
        assert "capacity" in out
        assert "queue_depth" in out
        # §5: a stall is no progress *and* no liveness, and nothing more.
        assert "no progress and no liveness" in out
        assert "busy-wait on a nested run is not a stall" in out
        # U1: the built-in monitor is the one deciding here; there is no script.
        assert (await ok("status"))["monitor"]["source"] == "builtin"
        assert "for 40m" in out  # the §13 default, spelled as it is configured
        assert "--pids" not in out

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
            assert flag in out
        # The built-in rule is not the one deciding here, and stall_minutes
        # never reaches the script.
        assert "no progress and no liveness" not in out
        assert "40" not in out.split("monitor  ")[1].splitlines()[0]

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
        assert "off" in out
        assert "stall_minutes = 0" in out
        assert "0m" not in out
        assert "no progress and no liveness" not in out

    drive(body)
