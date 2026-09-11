"""`hands doctor` — the install check (DESIGN §4, §11, §14).

The gate for this unit is "green in fake mode": every check that costs nothing
runs for real against the stand-ins (`tests/fake_claude.py`,
`tests/fake_monitor.py`), and the one check that would spend the human's
subscription — a one-turn `claude -p` per role — is skipped with a message that
says why. Two tests below exist only to prove that skip is real: `--live` is off
by default, and `HANDS_DOCTOR_FAKE=1` refuses it even when it is asked for.
"""

from __future__ import annotations

import asyncio
import io
import json
from pathlib import Path
from typing import Any

import pytest

from hands.cli import call, main
from hands.daemon import Daemon
from harness import PROJECT, config_body, drive, write_project

FAKE_CLAUDE = Path(__file__).with_name("fake_claude.py")
FAKE_MONITOR = Path(__file__).with_name("fake_monitor.py")
EXAMPLE_PLAYBOOK = Path(__file__).parent / "fixtures" / "playbook_example.toml"


# ------------------------------------------------------------------ fixtures


def write_config(
    home: Path,
    tmp_path: Path,
    *,
    claude: Path | str = FAKE_CLAUDE,
    monitor_cmd: str | None = FAKE_MONITOR.name,
    roots: list[str] | None = None,
    project: str = "demo",
) -> Path:
    """A whole, valid `~/.hands/<project>.toml` (§13) pointing at the stand-ins."""
    work = tmp_path / "work"
    work.mkdir(exist_ok=True)
    (work / ".git").mkdir(exist_ok=True)
    ops = tmp_path / "ops"
    ops.mkdir(exist_ok=True)
    if monitor_cmd == FAKE_MONITOR.name:
        target = ops / monitor_cmd
        if not target.exists():
            target.symlink_to(FAKE_MONITOR)
    allowed = roots if roots is not None else [str(work)]
    ops_block = f'monitor_cmd = "{monitor_cmd}"' if monitor_cmd else ""
    body = f"""
[server]
socket = "{home}/.hands/handsd.sock"
ntfy_topic = "hands-test"

[roles.builder]
cwd = "{work}"

[roles.aux]
cwd = "{work}"

[ops]
repo = "{ops}"
{ops_block}

[files]
allowed_roots = {json.dumps(allowed)}

[runner]
claude = "{claude}"
"""
    path = home / ".hands" / f"{project}.toml"
    path.write_text(body)
    return path


def sentinel_claude(tmp_path: Path) -> tuple[Path, Path]:
    """A `claude` that answers `--version` and leaves a file behind if ever spawned."""
    sentinel = tmp_path / "spawned"
    binary = tmp_path / "sentinel_claude.sh"
    binary.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "--version" ]; then echo "9.9.9 (sentinel)"; exit 0; fi\n'
        f'echo spawned > "{sentinel}"\n'
    )
    binary.chmod(0o755)
    return sentinel, binary


def run(*argv: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    code = main(["--project", "demo", "doctor", *argv], stdout=out, stderr=err)
    return code, out.getvalue(), err.getvalue()


def checks(*argv: str) -> tuple[int, dict[str, Any]]:
    code, out, err = run("--json", *argv)
    assert out, f"doctor --json printed nothing; stderr: {err}"
    report = json.loads(out)
    return code, {check["name"]: check for check in report["checks"]}


@pytest.fixture
def fake_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HANDS_DOCTOR_FAKE", "1")


# ------------------------------------------------------------ the whole run


def test_doctor_is_green_in_fake_mode(tmp_home: Path, tmp_path: Path, fake_mode: None) -> None:
    write_config(tmp_home, tmp_path)
    code, out, err = run()
    assert code == 0, f"doctor was not green:\n{out}\n{err}"
    assert out.strip().endswith("doctor: green"), out
    assert "0 failed" in out
    for expected in ("config", "claude", "ops script", "allowed roots", "playbook", "daemon"):
        assert expected in out, f"doctor printed no {expected!r} check:\n{out}"


def test_every_check_is_reported_with_a_status_and_a_detail(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    write_config(tmp_home, tmp_path)
    code, found = checks()
    assert code == 0
    assert found, "doctor --json reported no checks"
    for name, check in found.items():
        assert check["status"] in ("ok", "warn", "skip", "fail"), (name, check)
        assert check["detail"], f"check {name} says nothing"


# -------------------------------------------- the check that spends quota (§4)


def test_the_live_turn_is_not_run_without_the_flag(tmp_home: Path, tmp_path: Path) -> None:
    """No fake mode here: even against a real-looking binary, `--live` is opt-in."""
    sentinel, binary = sentinel_claude(tmp_path)
    write_config(tmp_home, tmp_path, claude=binary)
    code, found = checks()
    assert not sentinel.exists(), "doctor spawned a turn without --live"
    assert code == 0
    for role in ("builder", "aux"):
        check = found[f"live {role}"]
        assert check["status"] == "skip"
        assert "--live" in check["detail"]


def test_fake_mode_refuses_the_live_turn_and_spawns_nothing(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    """`--live` under `HANDS_DOCTOR_FAKE=1` must not start a single process.

    The stand-in here is not `fake_claude.py` but a script that leaves a file
    behind the moment it is run as anything other than `--version`: if doctor
    ever spawned a turn, the sentinel would exist.
    """
    sentinel, binary = sentinel_claude(tmp_path)
    write_config(tmp_home, tmp_path, claude=binary)

    code, found = checks("--live")

    assert not sentinel.exists(), "doctor spawned a turn in fake mode"
    assert code == 0
    assert "9.9.9" in found["claude"]["detail"]
    for role in ("builder", "aux"):
        check = found[f"live {role}"]
        assert check["status"] == "skip"
        assert "HANDS_DOCTOR_FAKE" in check["detail"]


# ---------------------------------------------------------- the free checks


def test_a_missing_claude_binary_fails(tmp_home: Path, tmp_path: Path, fake_mode: None) -> None:
    write_config(tmp_home, tmp_path, claude=tmp_path / "no-such-claude")
    code, found = checks()
    assert code == 1
    assert found["claude"]["status"] == "fail"


def test_the_ops_script_is_probed_for_the_three_flags(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    write_config(tmp_home, tmp_path)
    code, found = checks()
    assert code == 0
    detail = found["ops script"]["detail"]
    assert found["ops script"]["status"] == "ok", detail
    for flag in ("--pids", "--transcript", "--base"):
        assert flag in detail


def ops_script(tmp_path: Path, body: str) -> None:
    """Replace the ops script with one that behaves as `body` says."""
    script = tmp_path / "ops" / FAKE_MONITOR.name
    if script.is_symlink() or script.exists():
        script.unlink()
    script.write_text("#!/bin/sh\n" + body)
    script.chmod(0o755)


def test_a_script_that_has_no_help_is_probed_with_an_impossible_pid(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    """The fallback when `--help` says nothing about the three flags (§5)."""
    write_config(tmp_home, tmp_path)
    ops_script(
        tmp_path,
        'if [ "$1" = "--help" ]; then echo "usage: watch_monitor.sh"; exit 1; fi\nexit 0\n',
    )
    code, found = checks()
    assert code == 0
    assert found["ops script"]["status"] == "ok"
    assert "exited 0" in found["ops script"]["detail"]


def test_a_script_that_refuses_the_flags_fails(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    write_config(tmp_home, tmp_path)
    ops_script(tmp_path, 'echo "unknown option $1" >&2\nexit 2\n')
    code, found = checks()
    assert code == 1
    assert found["ops script"]["status"] == "fail"
    assert "§14" in found["ops script"]["detail"]


def test_a_missing_ops_script_names_section_14_step_4(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    write_config(tmp_home, tmp_path, monitor_cmd="watch_monitor.sh")
    code, out, _err = run()
    assert code == 1
    assert "§14" in out and "step 4" in out


def test_no_ops_script_configured_is_a_skip_not_a_failure(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    write_config(tmp_home, tmp_path, monitor_cmd=None)
    code, found = checks()
    assert code == 0
    assert found["ops script"]["status"] == "skip"


def test_a_missing_allowed_root_fails(tmp_home: Path, tmp_path: Path, fake_mode: None) -> None:
    write_config(tmp_home, tmp_path, roots=[str(tmp_path / "not-there")])
    code, found = checks()
    assert code == 1
    assert found["allowed roots"]["status"] == "fail"
    assert "not-there" in found["allowed roots"]["detail"]


def test_the_playbook_is_loaded_when_there_is_one(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    write_config(tmp_home, tmp_path)
    (tmp_path / "work" / "PLAYBOOK.toml").write_text(EXAMPLE_PLAYBOOK.read_text())
    code, found = checks()
    assert code == 0
    assert found["playbook"]["status"] == "ok"
    assert "audit-fixes" in found["playbook"]["detail"]


def test_an_unparseable_playbook_fails(tmp_home: Path, tmp_path: Path, fake_mode: None) -> None:
    write_config(tmp_home, tmp_path)
    (tmp_path / "work" / "PLAYBOOK.toml").write_text('version = 1\n[[rule]]\non = "nope"\n')
    code, found = checks()
    assert code == 1
    assert found["playbook"]["status"] == "fail"


def test_a_daemon_that_is_not_running_is_a_warning(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    """§14 step 1 runs doctor on a fresh config, before handsd is ever started."""
    write_config(tmp_home, tmp_path)
    code, found = checks()
    assert code == 0
    assert found["daemon"]["status"] == "warn"
    assert "handsd" in found["daemon"]["detail"]


# ------------------------------------------------- the background-wake check


def test_doctor_prints_the_background_wake_procedure(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    """§11: hands cannot run this one; it hands the human the exact commands."""
    write_config(tmp_home, tmp_path)
    _code, out, _err = run()
    assert "hands wait --for stop,held" in out
    assert "--gate" in out  # the free event that wakes the driver: a held job
    assert "deny <job>" in out  # and how to clear it without spending a turn
    assert "§11" in out


def test_the_wake_procedure_is_in_the_json_too(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    write_config(tmp_home, tmp_path)
    _code, out, _err = run("--json")
    report = json.loads(out)
    assert any("hands wait --for stop,held" in line for line in report["wake_check"])
    assert report["green"] is True


# ------------------------------------------------- the same surface over §9


def test_the_daemon_answers_doctor_over_the_api(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    """§9: the MCP face would wrap these methods, so `doctor` is a method too.

    The daemon does not connect to its own socket to check itself — it says what
    it is — and the live turn is skipped here exactly as it is in the CLI.
    """
    work = tmp_path / "work"
    work.mkdir(exist_ok=True)
    write_project(tmp_home, config_body(tmp_home, work))

    async def body(daemon: Daemon) -> None:
        report = await asyncio.to_thread(
            call, daemon.socket_path, "doctor", {}, project=PROJECT
        )
        found = {check["name"]: check for check in report["checks"]}
        assert report["green"] is True, found
        assert found["daemon"]["status"] == "ok"
        assert str(daemon.socket_path) in found["daemon"]["detail"]
        assert found["live builder"]["status"] == "skip"
        assert any("hands wait --for stop,held" in line for line in report["wake_check"])

    drive(body)
