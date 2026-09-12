"""U6: the monitor bridge (DESIGN §1 invariant 4, §5, §11, §13).

Two monitors, one contract: every block reaches the inbox as `monitor.<kind>`
and nothing here ever touches the job. The ops script is `tests/fake_monitor.py`;
the built-in monitor is driven at `stall_minutes = 0.01` (0.6 s), so no test
waits a real stall interval.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import pytest

from conftest import strip_paths
from fake_monitor import FAREWELL, FIRST, SECOND, THIRD
from hands.config import Config, parse_config
from hands.monitor import BlockBuffer, MonitorSupervisor, block_kind, descendants_of, pid_list
from hands.spool import Event, Job, Spool
from harness import BLOCK, config_body, drive, ok, write_project

FAKE_MONITOR = Path(__file__).with_name("fake_monitor.py")
FAKE_CLAUDE = Path(__file__).with_name("fake_claude.py")


# ------------------------------------------------------------------ fixtures


@pytest.fixture
def workdir(tmp_path: Path) -> Path:
    d = tmp_path / "work"
    d.mkdir()
    return d


@pytest.fixture
def opsdir(tmp_path: Path) -> Path:
    """An ops repo (§13 `[ops] repo`) holding a copy of the fake monitor."""
    d = tmp_path / "ops"
    d.mkdir()
    shutil.copy(FAKE_MONITOR, d / "watch_monitor.sh")
    (d / "watch_monitor.sh").chmod(0o755)
    return d


@pytest.fixture
def spool(tmp_home: Path) -> Spool:
    return Spool(tmp_home / ".hands")


def make_config(
    tmp_home: Path,
    workdir: Path,
    *,
    ops: Path | None = None,
    monitor_cmd: str | None = None,
    stall_minutes: float = 40.0,
) -> Config:
    data: dict[str, Any] = {
        "roles": {"builder": {"cwd": str(workdir)}, "aux": {"cwd": str(workdir)}},
        "monitor": {"stall_minutes": stall_minutes},
        "runner": {"claude": str(FAKE_CLAUDE)},
    }
    if ops is not None:
        data["ops"] = {"repo": str(ops), "monitor_cmd": monitor_cmd}
    return parse_config(data, project="demo", path=tmp_home / ".hands" / "demo.toml")


def running(spool: Spool, *, role: str = "builder", transcript: str | None = None) -> Job:
    """A job in the state the daemon hands the monitor: running, pid and base known."""
    job = spool.create_job(role=role, context="clear", prompt="p", origin="cli")
    return spool.transition(
        job,
        "running",
        pid=os.getpid(),
        transcript_path=transcript,
        head_at_start="deadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
    )


def monitor_events(spool: Spool) -> list[Event]:
    return [event for event in spool.events() if event.kind.startswith("monitor.")]


def run(body: Callable[[], Awaitable[None]]) -> None:
    asyncio.run(asyncio.wait_for(body(), 30))


async def wait_for(check: Callable[[], Any], what: str, timeout: float = 15.0) -> Any:
    for _ in range(int(timeout / 0.02)):
        value = check()
        if value:
            return value
        await asyncio.sleep(0.02)
    raise AssertionError(f"timed out waiting for {what}")


def blocks(events: list[Event]) -> list[str]:
    return [event.payload["block"] for event in events]


# ------------------------------------------------------------- pure helpers


@pytest.mark.parametrize(
    ("block", "kind"),
    [
        ("STALL builder has not moved in 40m\n  detail", "stall"),
        ("stall", "stall"),
        ("Tripwire: deadbee landed on main", "tripwire"),
        ("TRIPWIRE deadbee", "tripwire"),
        ("noise the ops script felt like printing", "event"),
        ("stalled but not a stall", "event"),
        ("", "event"),
        ("1234 numbers first", "event"),
    ],
)
def test_block_kind_is_the_first_word_lower_cased(block: str, kind: str) -> None:
    assert block_kind(block) == kind


def test_blocks_are_split_on_blank_lines_and_kept_verbatim() -> None:
    buf = BlockBuffer()
    assert buf.feed("STALL one") == []
    assert buf.feed("  indented detail") == []
    assert buf.feed("") == ["STALL one\n  indented detail"]
    assert buf.feed("   ") == []  # a whitespace-only line separates, it never starts a block
    assert buf.feed("TRIPWIRE two") == []
    assert buf.flush() == ["TRIPWIRE two"]
    assert buf.flush() == []


def test_the_pid_list_is_this_process_and_its_descendants() -> None:
    pids = descendants_of(os.getpid())
    assert pids[0] == os.getpid()
    assert len(set(pids)) == len(pids)


def test_a_dead_or_missing_pid_yields_no_pids(spool: Spool) -> None:
    job = spool.create_job(role="builder", context="clear", prompt="p", origin="cli")
    assert pid_list(job) == []  # no pid yet
    job.pid = 2**22 - 1  # above /proc/sys/kernel/pid_max on Linux: never a live pid
    assert pid_list(job) == []


# -------------------------------------------------------- the ops script §5


def test_the_ops_script_gets_the_design_flags_and_blocks_arrive_as_they_happen(
    tmp_home: Path, workdir: Path, opsdir: Path, spool: Spool, monkeypatch: pytest.MonkeyPatch
) -> None:
    argv_file = tmp_home / "argv.json"
    gate = tmp_home / "go"
    monkeypatch.setenv("HANDS_FAKE_MONITOR_ARGV", str(argv_file))
    monkeypatch.setenv("HANDS_FAKE_MONITOR_GO", str(gate))
    config = make_config(tmp_home, workdir, ops=opsdir, monitor_cmd="watch_monitor.sh")

    async def body() -> None:
        monitors = MonitorSupervisor(config, spool)
        job = running(spool, transcript=str(tmp_home / "t.jsonl"))
        monitors.start(job)

        first = await wait_for(lambda: monitor_events(spool), "the first block")
        # Filed as it arrived: the script has not exited and has not written the rest.
        assert len(first) == 1
        assert first[0].kind == "monitor.stall"
        assert first[0].payload["block"] == FIRST  # verbatim, §5
        assert first[0].payload["job"] == job.id

        argv = json.loads(argv_file.read_text())
        assert argv["cwd"] == str(opsdir)
        assert argv["base"] == job.head_at_start
        assert argv["transcript"] == job.transcript_path
        assert str(os.getpid()) in argv["pids"].split(",")

        gate.touch()
        events = await wait_for(
            lambda: monitor_events(spool) if len(monitor_events(spool)) >= 3 else None,
            "the remaining blocks",
        )
        assert [event.kind for event in events[:3]] == [
            "monitor.stall",
            "monitor.tripwire",
            "monitor.event",
        ]
        assert blocks(events)[:3] == [FIRST, SECOND, THIRD]

        await monitors.stop(job.id)
        # Killed when the job ends (§5), and whatever it had already written is drained.
        assert not _alive(argv["pid"])
        assert FAREWELL in blocks(monitor_events(spool))

    run(body)


def test_a_missing_monitor_script_is_an_inbox_event_and_not_a_fallback(
    tmp_home: Path, workdir: Path, opsdir: Path, spool: Spool
) -> None:
    # §21 refuses a monitor_cmd whose script is missing at load, so the script
    # exists for the load and is deleted after it: the run-time check (§5) is
    # what catches a script that goes away while hands is up, and it still runs.
    script = opsdir / "not_there.sh"
    shutil.copy(FAKE_MONITOR, script)
    script.chmod(0o755)
    config = make_config(
        tmp_home, workdir, ops=opsdir, monitor_cmd="not_there.sh", stall_minutes=0.01
    )
    script.unlink()

    async def body() -> None:
        monitors = MonitorSupervisor(config, spool, poll_s=0.05)
        job = running(spool)
        task = monitors.start(job)
        assert task is not None
        await asyncio.wait_for(task, 5)
        events = monitor_events(spool)
        assert len(events) == 1
        assert events[0].kind == "monitor.event"
        assert "not_there.sh" in strip_paths(events[0].payload["block"])
        # No silent fallback: the built-in monitor would have stalled by now.
        await asyncio.sleep(1.0)
        assert [event.kind for event in monitor_events(spool)] == ["monitor.event"]
        await monitors.stop(job.id)

    run(body)


def test_a_monitor_script_that_is_not_executable_is_an_inbox_event(
    tmp_home: Path, workdir: Path, opsdir: Path, spool: Spool
) -> None:
    # As above: executable at load (§21), chmod-ed away underneath the daemon.
    config = make_config(tmp_home, workdir, ops=opsdir, monitor_cmd="watch_monitor.sh")
    (opsdir / "watch_monitor.sh").chmod(0o644)

    async def body() -> None:
        monitors = MonitorSupervisor(config, spool)
        job = running(spool)
        task = monitors.start(job)
        assert task is not None
        await asyncio.wait_for(task, 5)
        events = monitor_events(spool)
        assert len(events) == 1
        assert events[0].kind == "monitor.event"
        assert "not executable" in strip_paths(events[0].payload["block"])

    run(body)


def test_a_monitor_script_that_dies_on_its_own_says_so(
    tmp_home: Path, workdir: Path, opsdir: Path, spool: Spool, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HANDS_FAKE_MONITOR_EXIT", "3")
    config = make_config(tmp_home, workdir, ops=opsdir, monitor_cmd="watch_monitor.sh")

    async def body() -> None:
        monitors = MonitorSupervisor(config, spool)
        job = running(spool)
        task = monitors.start(job)
        assert task is not None
        await asyncio.wait_for(task, 10)
        events = monitor_events(spool)
        assert blocks(events)[:3] == [FIRST, SECOND, THIRD]  # everything it wrote is drained
        assert events[-1].kind == "monitor.event"
        assert "exited with code 3" in strip_paths(events[-1].payload["block"])
        assert "giving up" in strip_paths(events[-1].payload["block"])  # its stderr tail

    run(body)


# ---------------------------------------------------- the built-in monitor §5


def test_the_builtin_monitor_stalls_and_refires_after_another_interval(
    tmp_home: Path, workdir: Path, spool: Spool
) -> None:
    # No ops.monitor_cmd, no transcript, a dead pid, a cwd that is not a git repo:
    # every input of §5 is missing and none of them may crash or read as liveness.
    config = make_config(tmp_home, workdir, stall_minutes=0.01)  # 0.6 s

    async def body() -> None:
        monitors = MonitorSupervisor(config, spool, poll_s=0.05)
        job = running(spool)
        job.pid = None
        spool.save_job(job)
        monitors.start(job)

        first = await wait_for(lambda: monitor_events(spool), "the first stall")
        assert first[0].kind == "monitor.stall"
        assert first[0].payload["source"] == "builtin"
        assert first[0].payload["block"].lower().startswith("stall")
        assert first[0].payload["job"] == job.id

        await wait_for(
            lambda: len(monitor_events(spool)) >= 2, "the stall to re-fire after an interval"
        )
        await monitors.stop(job.id)
        # One event per interval, not one per poll: 0.05 s polls, 0.6 s intervals.
        assert len(monitor_events(spool)) < 6

    run(body)


def test_the_builtin_monitor_reads_a_touched_transcript_as_liveness(
    tmp_home: Path, workdir: Path, spool: Spool
) -> None:
    config = make_config(tmp_home, workdir, stall_minutes=0.01)  # 0.6 s
    transcript = tmp_home / "transcript.jsonl"
    transcript.write_text("")

    async def body() -> None:
        monitors = MonitorSupervisor(config, spool, poll_s=0.05)
        job = running(spool, transcript=str(transcript))
        job.pid = None  # the transcript is the only input that may move
        spool.save_job(job)
        monitors.start(job)

        for _ in range(30):  # 1.5 s of liveness — two and a half stall intervals
            transcript.write_text(transcript.read_text() + "x")
            await asyncio.sleep(0.05)
        assert monitor_events(spool) == []

        await wait_for(lambda: monitor_events(spool), "a stall once the transcript stops moving")
        await monitors.stop(job.id)

    run(body)


def test_only_builder_jobs_are_watched(tmp_home: Path, workdir: Path, spool: Spool) -> None:
    config = make_config(tmp_home, workdir, stall_minutes=0.01)

    async def body() -> None:
        monitors = MonitorSupervisor(config, spool, poll_s=0.05)
        job = running(spool, role="aux")
        assert monitors.start(job) is None
        await asyncio.sleep(1.0)
        assert monitor_events(spool) == []
        assert monitors.status()["watching"] == []

    run(body)


def test_status_names_the_source_and_what_is_watched(
    tmp_home: Path, workdir: Path, opsdir: Path, spool: Spool
) -> None:
    builtin = MonitorSupervisor(make_config(tmp_home, workdir), spool)
    assert builtin.status()["source"] == "builtin"
    assert builtin.status()["cmd"] is None
    assert builtin.status()["stall_minutes"] == 40.0

    external = MonitorSupervisor(
        make_config(tmp_home, workdir, ops=opsdir, monitor_cmd="watch_monitor.sh"), spool
    )
    assert external.status()["source"] == "ops"
    assert external.status()["cmd"] == str(opsdir / "watch_monitor.sh")


# ------------------------------------------------------- the daemon wires it


def test_the_daemon_watches_every_builder_job_and_stops_at_the_end(
    tmp_home: Path, tmp_path: Path, opsdir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    argv_file = tmp_home / "argv.json"
    monkeypatch.setenv("HANDS_FAKE_MONITOR_ARGV", str(argv_file))
    workdir = tmp_path / "work"
    workdir.mkdir()
    write_project(
        tmp_home,
        config_body(
            tmp_home,
            workdir,
            builder="cancel_gated = false",
            extra=f'\n[ops]\nrepo = "{opsdir}"\nmonitor_cmd = "watch_monitor.sh"\n',
        ),
    )

    async def body(daemon: Any) -> None:
        job = await ok("send", "--role", "builder", "--context", "clear", BLOCK)
        events = await wait_for(
            lambda: [e for e in daemon.spool.events() if e.kind.startswith("monitor.")],
            "a monitor event for the running builder job",
        )
        assert events[0].payload["job"] == job["id"]
        assert events[0].payload["block"] == FIRST
        argv = json.loads(argv_file.read_text())
        assert argv["transcript"].endswith(".jsonl")
        assert argv["base"] in ("", None) or isinstance(argv["base"], str)
        assert (await ok("status"))["monitor"]["watching"] == [job["id"]]

        await ok("cancel", job["id"], "--reason", "the run is over")
        await wait_for(lambda: not _alive(argv["pid"]), "the monitor to be killed with the job")
        assert (await ok("status"))["monitor"]["watching"] == []

    drive(body)


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:  # pragma: no cover - not ours, but it exists
        return True
    return True
