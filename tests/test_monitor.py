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
import subprocess
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import pytest

from conftest import kill_quietly, process_live, strip_paths
from fake_monitor import FAREWELL, FIRST, SECOND, THIRD
from hands.config import Config, parse_config
from hands.monitor import (
    MAX_CMDLINE,
    BlockBuffer,
    MonitorSupervisor,
    TaskKillWatch,
    block_kind,
    cgroup_path,
    cgroup_pids,
    cmdline,
    descendants_of,
    group_pids,
    pid_list,
)
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


# ------------------------------------------- the task-killed notice (§5, §24)

TASK_KILLED_FIXTURE = Path(__file__).parent / "fixtures" / "task_killed.stream.jsonl"


def recorded_events() -> list[dict[str, Any]]:
    """The fixture's events: its `#` header quotes where each line was recorded."""
    text = TASK_KILLED_FIXTURE.read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line and not line.startswith("#")]


def kills_of(events: list[dict[str, Any]]) -> list[Any]:
    watch = TaskKillWatch()
    return [kill for event in events for kill in [watch.feed(event)] if kill is not None]


def test_the_recorded_notice_is_one_kill_per_task_with_its_command_line() -> None:
    kills = kills_of(recorded_events())
    assert [(kill.task_id, kill.task_type) for kill in kills] == [
        ("bar46gi30", "local_bash"),
        ("bs3zkkxlo", "local_bash"),
    ]
    assert kills[0].command.startswith("for i in 1 2 3; do timeout 900 ./scripts/check")
    assert kills[1].command.startswith("sed -n 379590,379615p /tmp/claude-strings.txt")
    assert kills[0].tool_use_id == "toolu_01GbuPKhvSEfHEhe9X6dRVde"
    assert kills[0].description == "Re-run the gate three times after the doc edit"


def test_either_half_of_the_notice_is_the_notice() -> None:
    events = recorded_events()
    without_update = [e for e in events if e.get("subtype") != "task_updated"]
    without_notification = [e for e in events if e.get("subtype") != "task_notification"]
    for stream in (without_update, without_notification):
        kills = kills_of(stream)
        assert [kill.task_id for kill in kills] == ["bar46gi30", "bs3zkkxlo"]
        assert all(kill.command for kill in kills)


def test_a_completed_or_backgrounded_task_is_not_a_kill() -> None:
    completed = []
    for event in recorded_events():
        event = json.loads(json.dumps(event))
        if event.get("subtype") == "task_updated" and "status" in event["patch"]:
            event["patch"]["status"] = "completed"
        if event.get("subtype") == "task_notification":
            event["status"] = "completed"
        completed.append(event)
    assert kills_of(completed) == []


def test_a_repeated_notice_is_one_kill_per_task() -> None:
    assert [kill.task_id for kill in kills_of(recorded_events() * 2)] == ["bar46gi30", "bs3zkkxlo"]


def test_a_kill_with_no_recorded_tool_use_names_no_command() -> None:
    events = [e for e in recorded_events() if e.get("type") != "assistant"]
    kills = kills_of(events)
    assert [kill.command for kill in kills] == [None, None]
    assert kills[0].description == "Re-run the gate three times after the doc edit"


def test_the_supervisor_files_the_kill_and_hands_it_on(
    tmp_home: Path, workdir: Path, spool: Spool
) -> None:
    seen: list[tuple[str, dict[str, Any]]] = []
    monitors = MonitorSupervisor(
        make_config(tmp_home, workdir), spool, on_event=lambda kind, p: seen.append((kind, p))
    )
    job = running(spool, role="aux")
    for event in recorded_events() * 2:
        monitors.observe(job, event)
    events = monitor_events(spool)
    assert [event.kind for event in events] == ["monitor.task_killed"] * 2
    assert [kind for kind, _ in seen] == ["monitor.task_killed"] * 2
    first = events[0].payload
    assert first["job"] == job.id and first["role"] == "aux" and first["source"] == "stream"
    assert first["task_id"] == "bar46gi30"
    assert first["command"].startswith("for i in 1 2 3;")
    assert first["command"] in first["block"]
    run(lambda: monitors.stop(job.id))


KILL_A = "FAKE:task-killed bg1 sleep 600"
KILL_B = "FAKE:task-killed bg2 tail -f /tmp/app.log"


@pytest.mark.parametrize(
    ("role", "lines", "expected"),
    [
        ("builder", [], []),
        ("builder", [KILL_A], [("bg1", "sleep 600")]),
        ("builder", [KILL_A, KILL_A], [("bg1", "sleep 600")]),
        ("builder", [KILL_A, KILL_B], [("bg1", "sleep 600"), ("bg2", "tail -f /tmp/app.log")]),
        ("aux", [KILL_A], [("bg1", "sleep 600")]),
    ],
    ids=["normal-run", "one-kill", "repeated-notice", "two-tasks", "aux-job"],
)
def test_a_role_job_through_the_daemon_files_one_task_killed_per_task(
    tmp_home: Path, tmp_path: Path, role: str, lines: list[str], expected: list[tuple[str, str]]
) -> None:
    workdir = tmp_path / "work"
    workdir.mkdir()
    write_project(tmp_home, config_body(tmp_home, workdir))

    async def body(daemon: Any) -> None:
        job = await ok("send", "--role", role, "--context", "clear", "\n".join(["go", *lines]))
        assert (await ok("wait", job["id"]))["state"] == "done"
        events = [e for e in daemon.spool.events() if e.kind.startswith("monitor.")]
        assert [e.kind for e in events] == ["monitor.task_killed"] * len(expected)
        assert [(e.payload["task_id"], e.payload["command"]) for e in events] == expected
        for event in events:
            assert event.payload["job"] == job["id"]
            assert event.payload["role"] == role
            assert event.payload["command"] in event.payload["block"]

    drive(body)


def test_a_queued_reply_can_carry_the_notice(
    tmp_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    replies = tmp_path / "replies.json"
    replies.write_text(json.dumps([{"result": "ok", "task_killed": [["bg9", "npm run dev"]]}]))
    monkeypatch.setenv("HANDS_FAKE_CLAUDE_REPLIES", str(replies))
    workdir = tmp_path / "work"
    workdir.mkdir()
    write_project(tmp_home, config_body(tmp_home, workdir))

    async def body(daemon: Any) -> None:
        job = await ok("send", "--role", "builder", "--context", "clear", "go")
        assert (await ok("wait", job["id"]))["state"] == "done"
        events = [e for e in daemon.spool.events() if e.kind == "monitor.task_killed"]
        assert [(e.payload["task_id"], e.payload["command"]) for e in events] == [
            ("bg9", "npm run dev")
        ]

    drive(body)


# ------------------------------------- the live pid set and orphans (§5, §24)


SCOPE_PATH = (
    "/user.slice/user-1000.slice/user@1000.service/app.slice/hands-demo-0mtygi953-ym63.scope"
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (f"0::{SCOPE_PATH}\n", SCOPE_PATH),
        (f"12:pids:/user.slice/user-1000.slice\n1:name=systemd:/user.slice\n0::{SCOPE_PATH}\n",
         SCOPE_PATH),
        ("12:pids:/user.slice\n1:name=systemd:/user.slice\n", None),
        ("", None),
    ],
    ids=["unified", "hybrid", "v1-only", "empty"],
)
def test_the_unified_cgroup_line_names_the_scope(text: str, expected: str | None) -> None:
    assert cgroup_path(text) == expected


def test_a_scopes_pid_set_is_its_cgroup_procs(tmp_path: Path) -> None:
    scope = tmp_path / SCOPE_PATH.lstrip("/")
    scope.mkdir(parents=True)
    (scope / "cgroup.procs").write_text("101\n202\n\n")
    assert cgroup_pids(SCOPE_PATH, root=tmp_path) == [101, 202]
    assert cgroup_pids("/user.slice/gone.scope", root=tmp_path) == []


def test_a_groups_pid_set_is_its_live_members() -> None:
    child = subprocess.Popen(["sleep", "30"], start_new_session=True)
    try:
        assert group_pids(child.pid) == [child.pid]  # this process is not in it
    finally:
        child.kill()
        child.wait()
    assert group_pids(child.pid) == []


def fake_proc(root: Path, pid: int, state: str, pgrp: int, argv: bytes = b"") -> None:
    d = root / str(pid)
    d.mkdir(parents=True)
    # The comm field is parenthesised and may hold spaces and parentheses.
    (d / "stat").write_text(f"{pid} (a (b) c) {state} 1 {pgrp} {pgrp} 0 -1 4194304 0 0\n")
    (d / "cmdline").write_bytes(argv)


def test_a_zombie_is_not_live_and_a_command_line_is_capped(tmp_path: Path) -> None:
    fake_proc(tmp_path, 10, "S", 10, b"sleep\x00300\x00")
    fake_proc(tmp_path, 11, "Z", 10)
    fake_proc(tmp_path, 12, "R", 99, b"x\x00" + b"a" * (MAX_CMDLINE * 3) + b"\x00")
    (tmp_path / "self").mkdir()
    assert group_pids(10, proc_root=tmp_path) == [10]
    assert cmdline(10, proc_root=tmp_path) == "sleep 300"
    long = cmdline(12, proc_root=tmp_path)
    assert long.startswith("x aaa") and long.endswith("…") and len(long) == MAX_CMDLINE
    assert cmdline(13, proc_root=tmp_path) == ""


def test_the_ops_script_is_given_the_pid_set_the_supervisor_is_handed(
    tmp_home: Path, workdir: Path, opsdir: Path, spool: Spool, monkeypatch: pytest.MonkeyPatch
) -> None:
    argv_file = tmp_home / "argv.json"
    monkeypatch.setenv("HANDS_FAKE_MONITOR_ARGV", str(argv_file))
    config = make_config(tmp_home, workdir, ops=opsdir, monitor_cmd="watch_monitor.sh")

    async def body() -> None:
        monitors = MonitorSupervisor(config, spool, pids=lambda job: [4242, 4343])
        job = running(spool)
        monitors.start(job)
        await wait_for(lambda: monitor_events(spool), "the first block")
        assert json.loads(argv_file.read_text())["pids"] == "4242,4343"
        await monitors.stop(job.id)

    run(body)


def orphan_events(daemon: Any) -> list[Event]:
    return [e for e in daemon.spool.events() if e.kind == "monitor.orphan_processes"]


@pytest.mark.parametrize("stdio", ["", " keep-stdio"], ids=["detached", "holding-its-pipes"])
def test_a_double_forked_orphan_is_filed_with_its_command_line_and_killed(
    tmp_home: Path, tmp_path: Path, stdio: str
) -> None:
    """§24 through a real daemon, runner and fake_claude, in process-group mode.

    The grandchild never calls setsid, so it is still in the job's group when
    claude exits: that is what the fallback can see. `holding-its-pipes` keeps
    the job's stdout open as well, so job end cannot wait for EOF to sweep.
    """
    workdir = tmp_path / "work"
    workdir.mkdir()
    write_project(tmp_home, config_body(tmp_home, workdir))
    pidfile = tmp_path / "orphan.pid"
    seen: list[str] = []

    async def body(daemon: Any) -> None:
        assert daemon.monitors.pids == daemon.runner.live_pids  # §5's `--pids`
        dispatch = daemon.monitors.on_event
        daemon.monitors.on_event = lambda kind, payload: (
            seen.append(kind),
            dispatch(kind, payload),
        )
        prompt = f"go\nFAKE:orphan {pidfile}{stdio}"
        job = await ok("send", "--role", "builder", "--context", "clear", prompt)
        assert (await ok("wait", job["id"]))["state"] == "done"
        pid = int(pidfile.read_text())
        events = orphan_events(daemon)
        assert len(events) == 1
        payload = events[0].payload
        assert (payload["job"], payload["role"]) == (job["id"], "builder")
        assert payload["isolation"] == "group"
        assert payload["processes"] == [{"pid": pid, "cmdline": "sleep 300"}]
        assert f"{pid} sleep 300" in payload["block"]
        assert not process_live(pid)
        assert seen.count("monitor.orphan_processes") == 1

    try:
        drive(body)
    finally:
        if pidfile.exists():
            kill_quietly(int(pidfile.read_text()))


def test_a_normal_run_files_no_orphan_processes(tmp_home: Path, tmp_path: Path) -> None:
    workdir = tmp_path / "work"
    workdir.mkdir()
    write_project(tmp_home, config_body(tmp_home, workdir))

    async def body(daemon: Any) -> None:
        job = await ok("send", "--role", "builder", "--context", "clear", "go")
        assert (await ok("wait", job["id"]))["state"] == "done"
        assert orphan_events(daemon) == []

    drive(body)
