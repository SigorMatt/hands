"""U6 (mission 8): `hands who` and `handswho` (DESIGN §4, §11, §24; backlog item 6).

Every input is injected: the process table is a dict, the transcript reader reads
a temporary `projects` directory (or is a fixed function), the daemon's state is a
dict or the real daemon over its real socket, the clock is a number, and the ntfy
transport is a recorder and a fake stream. Nothing here reads the real /proc, the
real `~/.claude`, or the network.

The first block ports `meta/prototypes/claudewho.py`'s `selftest()` case by case.
"""

from __future__ import annotations

import asyncio
import io
import json
import os
import time
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Any

import pytest

from conftest import strip_paths
from hands import who
from hands.cli import main as hands_main
from harness import PROJECT, cli, config_body, drive, ok, write_project

HOME = Path("/home/u")
REPO = "/home/u/git/demo"
NTFY = "https://ntfy.example"
WHO_TOPIC = "hands-who-test"
WHO_CMD_TOPIC = "hands-who-cmd-test"


# ------------------------------------------------ the prototype's selftest, ported


def _line(entry: dict[str, Any]) -> str:
    return json.dumps(entry) + "\n"


def test_selftest_transcript_waiting_after_a_text_answer_keeps_the_last_human_prompt(
    tmp_path: Path,
) -> None:
    """Selftest case 1: an assistant text answer last → waiting; last prompt is the human's."""
    t = tmp_path / "s.jsonl"
    t.write_text(
        _line({"type": "user", "message": {"role": "user", "content": "Kick off mission 6: go"}})
        + _line({"type": "assistant", "message": {"content": [{"type": "tool_use"}]}})
        + _line({"type": "user", "message": {"content": [{"type": "tool_result", "content": "x"}]}})
        + _line({"type": "assistant", "message": {"content": [{"type": "text", "text": "ok"}]}})
    )
    s = who.transcript_state(t, now=t.stat().st_mtime + 12)
    assert s["waiting"] is True
    assert s["last_prompt"].startswith("Kick off mission 6")
    assert s["idle_s"] == pytest.approx(12)


def test_selftest_transcript_working_after_a_tool_use(tmp_path: Path) -> None:
    """Selftest case 2: a tool_use last → not waiting; the newest human prompt wins."""
    t = tmp_path / "s.jsonl"
    t.write_text(
        _line({"type": "user", "message": {"content": "Kick off mission 6"}})
        + _line({"type": "assistant", "message": {"content": [{"type": "text", "text": "ok"}]}})
        + _line({"type": "user", "message": {"content": "check"}})
        + _line({"type": "assistant", "message": {"content": [{"type": "tool_use"}]}})
    )
    s = who.transcript_state(t, now=t.stat().st_mtime)
    assert s["waiting"] is False
    assert s["last_prompt"] == "check"


def test_selftest_short() -> None:
    """Selftest case 3."""
    assert who.short("a" * 100, 10) == "a" * 9 + "…"
    assert who.short("  a \n b ", 10) == "a b"


def test_selftest_age() -> None:
    """Selftest case 4."""
    assert (who.age(45), who.age(3000), who.age(7200)) == ("45s", "50m", "2h00")
    assert who.age(200000) == "2d"


def _proc(ppid: int, argv: list[str], cwd: str, age_s: float, comm: str) -> dict[str, Any]:
    return {"ppid": ppid, "argv": argv, "cwd": cwd, "age_s": age_s, "comm": comm}


SELFTEST_TABLE = {
    1: _proc(0, ["init"], "/", 9e6, "init"),
    10: _proc(1, ["claude", "-p"], "/x", 100, "claude"),
    11: _proc(10, ["bash", "-c", "pytest"], "/x", 5, "bash"),
    12: _proc(11, ["python", "-m", "pytest", "tests"], "/x", 4, "python"),
    13: _proc(10, ["claude", "--resume", "abc"], "/x", 3, "claude"),
}


def test_selftest_claude_processes_are_top_level_only() -> None:
    """Selftest case 5: a claude under a claude is its parent's, not a second process."""
    procs = who.claude_processes(SELFTEST_TABLE)
    assert [p["pid"] for p in procs] == [10]
    assert procs[0]["headless"] is True


def test_selftest_current_command_is_the_leaf_under_the_shell() -> None:
    """Selftest case 6."""
    assert who.current_command(SELFTEST_TABLE, 10) == "python -m pytest tests"


def test_selftest_debounce() -> None:
    """Selftest case 7: a session state counts after two scans; hands state at once."""
    d = who.Debounce(hold=2)
    f0 = d.fingerprint([("s:1", "wait"), ("hands:builder", "idle")])
    f1 = d.fingerprint([("s:1", "think"), ("hands:builder", "idle")])  # one scan: ignored
    f2 = d.fingerprint([("s:1", "think"), ("hands:builder", "idle")])  # held: counts
    f3 = d.fingerprint([("s:1", "think"), ("hands:builder", "run:x")])  # hands: at once
    assert f0 == f1
    assert f1 != f2
    assert f2 != f3


# ------------------------------------------------------------- the /proc reader


def test_proc_table_reads_a_proc_tree(tmp_path: Path) -> None:
    """The reader itself, over a directory shaped like /proc (no real /proc)."""
    root = tmp_path / "proc"
    (root / "42").mkdir(parents=True)
    (root / "uptime").write_text("1000.00 5.00\n")
    (root / "42" / "cmdline").write_bytes(b"claude\0-p\0hi\0")
    # pid (comm) state ppid ... field 22 (index 19 after the comm) is starttime.
    fields = ["S", "7"] + ["0"] * 17 + ["90000"]
    (root / "42" / "stat").write_text("42 (claude code) " + " ".join(fields) + "\n")
    (root / "42" / "comm").write_text("claude\n")
    (root / "42" / "cwd").symlink_to(tmp_path)
    (root / "43").mkdir()  # a kernel thread: empty cmdline, skipped
    (root / "43" / "cmdline").write_bytes(b"")
    (root / "self").mkdir()  # not a pid
    table = who.proc_table(root, clk_tck=100)
    assert sorted(table) == [42]
    assert table[42]["argv"] == ["claude", "-p", "hi"]
    assert table[42]["ppid"] == 7
    assert table[42]["age_s"] == pytest.approx(100.0)
    assert table[42]["cwd"] == str(tmp_path)
    assert table[42]["comm"] == "claude"


def test_a_node_launched_claude_is_a_claude() -> None:
    assert who.is_claude(_proc(1, ["node", "/opt/bin/claude", "-p"], "/", 1, "node"))
    assert not who.is_claude(_proc(1, ["node", "server.js"], "/", 1, "node"))


# --------------------------------------------------------------- transcripts


def test_transcripts_read_the_newest_file_of_the_cwd_directory(tmp_path: Path) -> None:
    projects = tmp_path / "projects"
    folder = projects / who.dashed("/home/u/git/demo.x")
    folder.mkdir(parents=True)
    old, new = folder / "old.jsonl", folder / "new.jsonl"
    old.write_text(_line({"type": "user", "message": {"content": "old"}}))
    new.write_text(_line({"type": "user", "message": {"content": "new"}}))
    os.utime(old, (1000, 1000))
    os.utime(new, (2000, 2000))
    reader = who.Transcripts(projects, clock=lambda: 2030.0)
    state = reader("/home/u/git/demo.x", 60.0)
    assert state is not None
    assert state["last_prompt"] == "new"
    assert state["idle_s"] == pytest.approx(30.0)
    # Older than the session's age plus the hour of slack: not this session's.
    assert who.Transcripts(projects, clock=lambda: 9000.0)("/home/u/git/demo.x", 60.0) is None
    assert reader("/home/u/git/nowhere", 60.0) is None


def test_dashed_is_every_non_alphanumeric_character() -> None:
    assert who.dashed("/home/u/git/hands") == "-home-u-git-hands"
    assert who.dashed("/home/u/.hands/a_b") == "-home-u--hands-a-b"


# ------------------------------------------------------------- the picture (§24)


def picture_table() -> dict[int, dict[str, Any]]:
    """A fixed process table: a hands job with a child, your session, a driver, another."""
    return {
        1: _proc(0, ["init"], "/", 9e6, "init"),
        100: _proc(1, ["claude", "-p", "--output-format", "stream-json"], REPO, 300, "claude"),
        101: _proc(100, ["bash", "-c", "pytest"], REPO, 5, "bash"),
        102: _proc(101, ["/home/u/git/demo/.venv/bin/python3", "-m", "pytest"], REPO, 4, "python3"),
        200: _proc(1, ["claude"], REPO, 7200, "claude"),
        300: _proc(
            1, ["claude", "--dangerously-skip-permissions"], "/home/u/hands-driver/demo", 3600,
            "claude",
        ),
        400: _proc(1, ["node", "/opt/claude/bin/claude", "-p"], "/home/u/git/other", 60, "node"),
    }


def picture_daemon() -> dict[str, Any]:
    """A fixed `who` answer: builder running, one queued on aux, a held gate, two unread."""
    running = {"id": "j1", "role": "builder", "state": "running", "pid": 100,
               "prompt_line": "Execute WORKPLAN.md run 2"}  # fmt: skip
    return {
        "project": "demo",
        "roles": {
            "aux": {"cwd": REPO, "running": None, "queued": ["j2"]},
            "builder": {"cwd": REPO, "running": running, "queued": []},
        },
        "jobs": [
            running,
            {"id": "j2", "role": "aux", "state": "queued", "pid": None, "prompt_line": "q"},
            {"id": "j3", "role": "aux", "state": "held", "pid": None, "prompt_line": "Apply",
             "gate_reason": "decisions-file"},  # fmt: skip
        ],
        "pipeline": {"paused": False, "stop_reason": None, "playbook": {"rules": 4}},
        "inbox": [{"id": "e1", "kind": "job.held"}, {"id": "e2", "kind": "monitor.stall"}],
    }


TRANSCRIPTS = {
    REPO: {"waiting": True, "last_prompt": "look at the diff", "idle_s": 120.0},
    "/home/u/hands-driver/demo": {"waiting": True, "last_prompt": "check", "idle_s": 30.0},
}


@pytest.fixture
def utc() -> Iterator[None]:
    """The header's clock is local time; pin the zone so the picture is exact."""
    old = os.environ.get("TZ")
    os.environ["TZ"] = "UTC"
    time.tzset()
    yield
    if old is None:
        os.environ.pop("TZ", None)
    else:
        os.environ["TZ"] = old
    time.tzset()



def sources(
    *,
    daemon: Any = picture_daemon,
    table: Any = picture_table,
    transcripts: dict[str, Any] | None = None,
) -> who.Sources:
    seen = TRANSCRIPTS if transcripts is None else transcripts
    return who.Sources(
        project="demo",
        role_cwds={"builder": REPO, "aux": REPO},
        daemon=daemon,
        procs=table,
        transcripts=lambda cwd, _limit: seen.get(cwd),
        clock=lambda: 3600.0 * 9 + 60 * 5,
        home=HOME,
    )


PICTURE = """\
09:05 · 4 claude processes

handsd (daemon, project demo) — pipeline running · 4 rules
  role builder (job j1, 5m)
      Execute WORKPLAN.md run 2
    python -m pytest (process, 4s)
  role aux — 1 job queued
  held job j3 (aux) — needs YOUR decision
      decisions-file

driver:demo (session, 60m, skip-perms) — waiting for you · 30s idle
    last: check
  inbox: 2 unread from handsd — job.held, monitor.stall — needs YOU

demo (your session) (session, 2h00) — waiting for you · 2m idle
    last: look at the diff

other (headless, 60s) — state unknown"""


def test_the_picture_for_a_fixed_process_table_and_daemon_state(utc: None) -> None:
    """§24's hierarchy and labels, pinned whole: daemon → jobs → processes, then
    each session → its processes; `role <r>`, `(your session)`, `driver:<project>`."""
    text, items = who.build_summary(sources())
    assert text == PICTURE
    # Your own session (pid 200) is shown above and is not among the fingerprinted items.
    assert items == [
        ("demo:builder", "run:j1"),
        ("demo:aux", "q1"),
        ("demo:held:j3", "held"),
        ("demo:inbox", "2"),
        ("s:300", "wait"),
        ("s:400", "?"),
    ]


def test_the_picture_with_the_daemon_down_still_shows_the_processes(utc: None) -> None:
    text, items = who.build_summary(sources(daemon=lambda: None, transcripts={}))
    assert text.splitlines()[2:4] == ["handsd (daemon, project demo)", "    not answering"]
    assert ("demo", "down") in items
    # The hands job's process is now just another headless claude in the role dir.
    assert "demo (headless, 5m) — working" in strip_paths(text)
    assert "  python -m pytest (process, 4s)" in strip_paths(text)


def test_a_stopped_pipeline_says_so_and_its_reason(utc: None) -> None:
    def paused() -> dict[str, Any]:
        state = picture_daemon()
        state["pipeline"] = {"paused": True, "stop_reason": "monitor.stall on j1",
                             "playbook": {"rules": 4}}  # fmt: skip
        state["inbox"] = []
        return state

    text, items = who.build_summary(sources(daemon=paused))
    assert "handsd (daemon, project demo) — pipeline stopped · 4 rules" in strip_paths(text)
    assert "    reason: monitor.stall on j1" in strip_paths(text)
    assert ("demo:pipeline", "stopped") in items


def test_an_inbox_with_no_driver_session_gets_its_own_block(utc: None) -> None:
    table = picture_table()
    del table[300]
    text, _items = who.build_summary(sources(table=lambda: table))
    assert text.endswith(
        "inbox for a driver of demo (no driver session running)\n"
        "    2 unread from handsd — job.held, monitor.stall"
    )


def test_your_own_session_is_never_fingerprinted() -> None:
    """§24: shown, never fingerprinted — its state can flip every scan and push nothing."""
    deb = who.Debounce()
    prints = set()
    for waiting in (True, False, True, False, False, True, True):
        seen = {REPO: {"waiting": waiting, "last_prompt": "x", "idle_s": 1.0}}
        text, items = who.build_summary(sources(transcripts=seen))
        assert not [key for key, _ in items if key == "s:200"]
        prints.add(deb.fingerprint(items))
    assert len(prints) == 1


def test_a_session_state_changes_only_after_two_scans() -> None:
    """§24's debounce, through the scanner: the driver goes from waiting to thinking."""
    deb = who.Debounce()
    waiting = dict(TRANSCRIPTS)
    thinking = {**TRANSCRIPTS, "/home/u/hands-driver/demo": {
        "waiting": False, "last_prompt": "check", "idle_s": 3.0}}  # fmt: skip
    first = deb.fingerprint(who.build_summary(sources(transcripts=waiting))[1])
    once = deb.fingerprint(who.build_summary(sources(transcripts=thinking))[1])
    twice = deb.fingerprint(who.build_summary(sources(transcripts=thinking))[1])
    assert first == once
    assert once != twice


# ----------------------------------------------------------- handswho pushes


class Recorder:
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    async def __call__(self, url: str, **kwargs: Any) -> int:
        self.sent.append({"url": url, **kwargs})
        return 200


class Box:
    """A daemon state the test changes between scans."""

    def __init__(self) -> None:
        self.state = picture_daemon()

    def __call__(self) -> dict[str, Any]:
        return self.state


def pusher(box: Box, post: Recorder, **kwargs: Any) -> who.WhoPusher:
    return who.WhoPusher(
        sources(daemon=box),
        topic=WHO_TOPIC,
        cmd_topic=WHO_CMD_TOPIC,
        ntfy_url=NTFY,
        post=post,
        clock=kwargs.pop("clock", lambda: 1000.0),
        **kwargs,
    )


def test_identical_pictures_do_not_push_twice_and_a_change_pushes() -> None:
    box, post = Box(), Recorder()
    p = pusher(box, post, min_gap=0.0)

    async def scenario() -> None:
        assert await p.scan() is True  # the first picture is pushed
        assert await p.scan() is False
        assert await p.scan() is False
        box.state["roles"]["aux"]["queued"] = ["j2", "j4"]
        assert await p.scan() is True
        assert await p.scan() is False

    asyncio.run(scenario())
    assert len(post.sent) == 2
    assert {item["url"] for item in post.sent} == {f"{NTFY}/{WHO_TOPIC}"}
    assert post.sent[0]["title"] == who.PUSH_TITLE
    assert strip_paths(post.sent[1]["message"]).count("role aux — 2 jobs queued") == 1


def test_a_change_inside_the_minimum_gap_is_pushed_once_the_gap_has_passed() -> None:
    box, post = Box(), Recorder()
    now = [1000.0]
    p = pusher(box, post, min_gap=60.0, clock=lambda: now[0])

    async def scenario() -> None:
        assert await p.scan() is True
        box.state["inbox"] = []
        now[0] += 10
        assert await p.scan() is False
        now[0] += 60
        assert await p.scan() is True

    asyncio.run(scenario())
    assert len(post.sent) == 2


@pytest.mark.parametrize("text", ["status", "who", "check", "?", "  Status \n"])
def test_each_command_is_answered_with_a_push(text: str) -> None:
    box, post = Box(), Recorder()
    p = pusher(box, post)

    async def scenario() -> None:
        await p.scan()
        assert await p.command(text) is True

    asyncio.run(scenario())
    assert [item["title"] for item in post.sent] == [who.PUSH_TITLE, who.REQUESTED_TITLE]
    assert post.sent[0]["message"] == post.sent[1]["message"]


@pytest.mark.parametrize("text", ["approve j3", "status now", "", "pause"])
def test_anything_else_on_the_command_topic_is_not_answered(text: str) -> None:
    box, post = Box(), Recorder()
    p = pusher(box, post)
    assert asyncio.run(p.command(text)) is False
    assert post.sent == []


def test_the_command_stream_answers_all_four_commands_and_nothing_older() -> None:
    """A mocked `who_cmd_topic` stream: each of the four commands gets a push; a
    keepalive, a stranger's message and a message from before the start do not."""
    box, post = Box(), Recorder()
    urls: list[str] = []
    started = 5000

    def event(text: str, n: int, at: int = started + 1) -> str:
        return json.dumps({"event": "message", "id": f"m{n}", "time": at, "message": text})

    lines = [
        json.dumps({"event": "open"}),
        event("status", 0, at=started - 100),  # before the start: not a request now
        event("status", 1),
        json.dumps({"event": "keepalive"}),
        event("who", 2),
        event("hello", 3),
        event("check", 4),
        event("?", 5),
        event("?", 5),  # the same id again: read once
    ]

    async def stream(url: str) -> AsyncIterator[str]:
        urls.append(url)
        for line in lines:
            yield line

    p = pusher(box, post, stream=stream, clock=lambda: float(started))

    async def scenario() -> None:
        p.start_commands()
        await p.subscribe_once()

    asyncio.run(scenario())
    assert urls == [f"{NTFY}/{WHO_CMD_TOPIC}/json?since={started}"]
    assert [item["title"] for item in post.sent] == [who.REQUESTED_TITLE] * 4
    assert {item["url"] for item in post.sent} == {f"{NTFY}/{WHO_TOPIC}"}
    assert p.cmd_url() == f"{NTFY}/{WHO_CMD_TOPIC}/json?since=m5"


def test_run_pushes_the_first_picture_then_scans_on_its_interval() -> None:
    box, post = Box(), Recorder()
    sleeps: list[float] = []

    class Stop(Exception):
        pass

    async def sleep(seconds: float) -> None:
        sleeps.append(seconds)
        if len(sleeps) == 2:
            raise Stop

    p = who.WhoPusher(
        sources(daemon=box), topic=WHO_TOPIC, cmd_topic=None, ntfy_url=NTFY, post=post,
        sleep=sleep, interval=7.0, min_gap=0.0, clock=lambda: 1.0,
    )  # fmt: skip
    with pytest.raises(Stop):
        asyncio.run(p.run())
    assert sleeps == [7.0, 7.0]
    assert len(post.sent) == 1


# -------------------------------------------------------------------- the CLIs


def test_handswho_help(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        who.main(["--help"])
    assert exc.value.code == 0
    assert "usage: handswho" in strip_paths(capsys.readouterr().out)


def test_hands_help_lists_who(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        hands_main(["--help"])
    assert "who" in strip_paths(capsys.readouterr().out)


def test_handswho_without_a_who_topic_exits_1_and_says_which_key(
    tmp_home: Path, tmp_path: Path
) -> None:
    write_project(tmp_home, config_body(tmp_home, tmp_path))
    out, err = io.StringIO(), io.StringIO()
    assert who.main(["--project", PROJECT], stdout=out, stderr=err) == 1
    assert "[notify] who_topic" in strip_paths(err.getvalue())
    code = hands_main(["--project", PROJECT, "who", "--daemon"], stdout=out, stderr=err)
    assert code == 1
    assert strip_paths(err.getvalue()).count("[notify] who_topic") == 2


def test_hands_who_prints_once_and_exits_0_with_the_daemon_down(
    tmp_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, utc: None
) -> None:
    write_project(tmp_home, config_body(tmp_home, tmp_path))
    monkeypatch.setattr(who, "proc_table", lambda: picture_table())
    out, err = io.StringIO(), io.StringIO()
    assert hands_main(["--project", PROJECT, "who"], stdout=out, stderr=err) == 0
    assert "handsd (daemon, project demo)\n    not answering" in strip_paths(out.getvalue())
    assert "4 claude processes" in strip_paths(out.getvalue())
    assert "(headless, 60s)" in strip_paths(out.getvalue())


def test_hands_who_reads_the_daemon_over_its_socket(
    tmp_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The real daemon, the real socket: a held gate and the inbox arrive in the picture."""
    write_project(tmp_home, config_body(tmp_home, tmp_path))
    monkeypatch.setattr(who, "proc_table", lambda: {})

    async def body(_daemon: Any) -> None:
        sent = await ok("send", "--role", "aux", "--context", "clear", "--gate", "a gate", "hi")
        state = await ok("who")
        assert state["daemon"]["project"] == PROJECT
        held = [job for job in state["daemon"]["jobs"] if job["state"] == "held"]
        assert [(job["id"], job["gate_reason"]) for job in held] == [(sent["id"], "a gate")]
        assert [event["kind"] for event in state["daemon"]["inbox"]] == ["job.held"]
        code, out, _err = await cli("who")
        assert code == 0
        assert f"held job {sent['id']} (aux) — needs YOUR decision" in strip_paths(out)
        assert "      a gate" in strip_paths(out)
        assert "inbox for a driver of demo (no driver session running)" in strip_paths(out)

    drive(body)
