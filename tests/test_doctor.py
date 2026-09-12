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
import re
import shutil
from pathlib import Path
from typing import Any

import pytest

from conftest import strip_paths
from hands.cli import call, main
from hands.config import load_config
from hands.daemon import Daemon
from hands.doctor import FAIL, Check, run_checks
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
    resume_line: str | None = None,
    builder_extra: str = "",
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
            # Copied, not linked: §21 makes `ops.monitor_cmd` name a script the
            # ops repo really holds, and a symlink to this repo's stand-in
            # resolves outside it (review 5 should-fix 4).
            shutil.copy(FAKE_MONITOR, target)
            target.chmod(0o755)
    allowed = roots if roots is not None else [str(work)]
    ops_block = f'monitor_cmd = "{monitor_cmd}"' if monitor_cmd else ""
    resume_block = f'resume_line = "{resume_line}"' if resume_line else ""
    body = f"""
[server]
socket = "{home}/.hands/handsd.sock"
ntfy_topic = "hands-test"

[roles.builder]
cwd = "{work}"
{resume_block}
{builder_extra}

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
    assert "0 failed" in strip_paths(out)
    for expected in ("config", "claude", "ops script", "allowed roots", "playbook", "daemon"):
        assert expected in strip_paths(out), f"doctor printed no {expected!r} check:\n{out}"


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
        assert "--live" in strip_paths(check["detail"])


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
    assert "9.9.9" in strip_paths(found["claude"]["detail"])
    for role in ("builder", "aux"):
        check = found[f"live {role}"]
        assert check["status"] == "skip"
        assert "HANDS_DOCTOR_FAKE" in strip_paths(check["detail"])


# ---------------------------------------------------------- the free checks


def test_the_role_check_names_the_limit_resume_behaviour(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    """H-008: which of the two resumes a role has is invisible until a limit hits."""
    write_config(tmp_home, tmp_path)
    code, found = checks()
    assert code == 0
    detail = found["role builder"]["detail"]
    assert "limit resume: re-sends the limited job's own prompt" in strip_paths(detail)
    assert "resume_line" in strip_paths(detail)
    aux = found["role aux"]["detail"]
    assert "limit resume: re-sends the limited job's own prompt" in strip_paths(aux)


def test_the_role_check_names_a_configured_resume_line(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    write_config(tmp_home, tmp_path, resume_line="Resume WORKPLAN.md")
    code, found = checks()
    assert code == 0
    detail = found["role builder"]["detail"]
    assert 'limit resume: sends resume_line "Resume WORKPLAN.md"' in strip_paths(detail)
    # aux is unchanged either way (§6)
    aux = found["role aux"]["detail"]
    assert "limit resume: re-sends the limited job's own prompt" in strip_paths(aux)


CEILING = "CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS"


def text_row(out: str, name: str) -> str:
    """One check's lines in the text report: its row and the rows under it."""
    lines = out.splitlines()
    for i, line in enumerate(lines):
        if re.match(rf"^  \S+\s+{re.escape(name)}  ", line):
            rows = [line]
            for more in lines[i + 1 :]:
                if not more.startswith(" " * 8) or not more.strip():
                    break
                rows.append(more)
            return "\n".join(rows)
    raise AssertionError(f"the text report has no {name!r} row:\n{out}")


def test_doctor_shows_the_bg_wait_ceiling_is_0_for_both_roles_by_default(
    tmp_home: Path, tmp_path: Path, fake_mode: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mission 7a's acceptance: a config that does not set it shows `=0` per role (§23).

    The daemon's own environment is given a different value on purpose: the role
    job does not inherit it, so doctor must not report it either.
    """
    monkeypatch.setenv(CEILING, "600000")
    write_config(tmp_home, tmp_path)
    code, out, err = run()
    assert code == 0, f"{out}\n{err}"
    for role in ("builder", "aux"):
        assert f"{CEILING}=0" in strip_paths(text_row(out, f"role {role}"))
    code, found = checks()
    assert code == 0
    for role in ("builder", "aux"):
        assert f"{CEILING}=0" in strip_paths(found[f"role {role}"]["detail"])


def test_doctor_shows_a_configured_ceiling_for_the_role_that_sets_it(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    write_config(
        tmp_home, tmp_path, builder_extra=f'[roles.builder.env]\n{CEILING} = "1800000"'
    )
    code, out, err = run()
    assert code == 0, f"{out}\n{err}"
    assert f"{CEILING}=1800000" in strip_paths(text_row(out, "role builder"))
    assert f"{CEILING}=0" in strip_paths(text_row(out, "role aux"))
    code, found = checks()
    assert f"{CEILING}=1800000" in strip_paths(found["role builder"]["detail"])
    assert f"{CEILING}=0" not in strip_paths(found["role builder"]["detail"])
    assert f"{CEILING}=0" in strip_paths(found["role aux"]["detail"])


def test_the_live_turn_runs_with_the_role_environment(
    tmp_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`--live` spawns §2's invocation with the same environment a role job gets."""
    monkeypatch.setenv(CEILING, "600000")
    binary = tmp_path / "env_claude.sh"
    binary.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "--version" ]; then echo "9.9.9 (env probe)"; exit 0; fi\n'
        "cat >/dev/null\n"
        "printf '{\"type\":\"result\",\"subtype\":\"success\",\"is_error\":false,"
        "\"result\":\"ceiling=%s\",\"num_turns\":1}\\n' "
        f'"${CEILING}"\n'
    )
    binary.chmod(0o755)
    write_config(tmp_home, tmp_path, claude=binary)
    code, found = checks("--live")
    assert code == 0, found
    for role in ("builder", "aux"):
        assert "ceiling=0" in strip_paths(found[f"live {role}"]["detail"]), found[f"live {role}"]


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
        assert flag in strip_paths(detail)


def ops_row(found: list[Check]) -> Check:
    """The `ops script` row of a `run_checks` result (§4's doctor row order)."""
    rows = [check for check in found if check.name == "ops script"]
    assert len(rows) == 1, f"expected one ops script row, got {len(rows)}"
    return rows[0]


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
    assert "exited 0" in strip_paths(found["ops script"]["detail"])


def test_a_script_that_refuses_the_flags_fails(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    write_config(tmp_home, tmp_path)
    ops_script(tmp_path, 'echo "unknown option $1" >&2\nexit 2\n')
    code, found = checks()
    assert code == 1
    assert found["ops script"]["status"] == "fail"
    assert "§14" in strip_paths(found["ops script"]["detail"])


def test_a_missing_ops_script_is_refused_before_doctor_can_report_on_it(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    """§21 (review 4 blocker 2): a `monitor_cmd` with no script behind it does
    not load at all, so doctor's own missing-script row is not what the human
    meets — the `config` row is, naming the key and the path it could not find.
    That row is still the answer for a script deleted *after* the config was
    read, which is what the test below this one drives."""
    write_config(tmp_home, tmp_path, monitor_cmd="watch_monitor.sh")
    code, found = checks()
    assert code == 1
    assert found["config"]["status"] == "fail"
    detail = found["config"]["detail"]
    assert "monitor_cmd" in strip_paths(detail) and "watch_monitor.sh" in strip_paths(detail)


def test_an_ops_script_that_changes_after_the_config_was_read_is_doctors_own_row(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    """§14 step 4 (review 5 should-fix 4): the run-time rows, restored.

    §21 refuses a `monitor_cmd` with no executable script behind it at *load*, so
    the two rows above — "does not exist" and "is not executable" — are reachable
    only by a config that loaded and a script that changed under it afterwards.
    That is what they are for, and the commit that added the load refusal took
    their only coverage away with it. Here the config is read first, exactly as
    the daemon reads it once at startup, and the script is then taken away.
    """
    write_config(tmp_home, tmp_path)
    config = load_config("demo")
    script = tmp_path / "ops" / FAKE_MONITOR.name
    assert config.ops.monitor_path == script

    script.chmod(0o644)
    row = ops_row(run_checks(config))
    assert row.status == FAIL
    assert "not executable" in strip_paths(row.detail)
    assert "§14" in strip_paths(row.detail)

    script.unlink()
    row = ops_row(run_checks(config))
    assert row.status == FAIL
    assert "does not exist" in strip_paths(row.detail)
    assert "§14" in strip_paths(row.detail)


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
    assert "not-there" in strip_paths(found["allowed roots"]["detail"])


def test_the_playbook_is_loaded_when_there_is_one(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    write_config(tmp_home, tmp_path)
    (tmp_path / "work" / "PLAYBOOK.toml").write_text(EXAMPLE_PLAYBOOK.read_text())
    code, found = checks()
    assert code == 0
    assert found["playbook"]["status"] == "ok"
    assert "audit-fixes" in strip_paths(found["playbook"]["detail"])


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
    assert "handsd" in strip_paths(found["daemon"]["detail"])


# ------------------------------------------------ the notification check (§11)

#: The `hands` subcommands §11's notification check may tell the human to run:
#: the two events that file without a turn (`pause`, a gated `send`), their
#: clear-ups (`resume`, `deny`), and where to look (`inbox`, `notify --test`).
#: Not a list of retired phrases: what the output instructs is compared with
#: what §11 allows, so an arming step spelled any new way is still a `wait`.
NOTIFICATION_COMMANDS = {"pause", "send", "resume", "deny", "inbox", "notify"}


def assert_is_the_notification_check(text: str) -> None:
    """What §11 says doctor prints, asserted on the rendered text itself."""
    flat = " ".join(text.split())
    assert "Notification check (§11)" in strip_paths(flat)
    # It tells the human to fire an event — a pause or a gated send — ...
    assert "hands --project demo pause" in strip_paths(flat)
    sends = re.findall(r"hands --project demo send [^`]*?--gate", strip_paths(flat))
    assert sends, "no gated send in the notification check"
    # ... and to watch the phone for it.
    assert "phone" in strip_paths(flat)
    # Every `hands` command it tells the human to type — a code span or an
    # indented command line, not prose ("hands cannot run this one") — is one
    # §11 allows; none of them is a wait.
    typed = re.findall(r"`([^`]+)`", strip_paths(text)) + [
        line.strip() for line in strip_paths(text).splitlines() if line.strip().startswith("hands ")
    ]
    named = [
        found
        for span in typed
        for found in re.findall(r"^hands (?:--project demo )?([a-z-]+)", span.strip())
    ]
    assert named and set(named) <= NOTIFICATION_COMMANDS, sorted(set(named))
    # Any sentence that speaks of arming or of the background says it is not
    # done: the check never instructs either.
    for sentence in re.split(r"(?<=[.:;—])\s", flat):
        if re.search(r"\barms?\b|\barming\b|background", sentence, re.IGNORECASE):
            assert re.search(r"\b(no|not|never)\b", sentence), sentence


def test_the_wake_check_is_a_notification_test_not_an_armed_wait(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    """§11, §22: the driver arms no background wait, so what doctor prints is
    the one check hands still cannot run itself — the event has to reach the
    human's phone over ntfy. ntfy is the human's doorbell; the human's `check`
    is the driver's. Asserted on the real CLI's rendered output (review 6
    should-fix 2), not on phrases taken from the old text."""
    write_config(tmp_home, tmp_path)
    _code, out, _err = run()
    section = out.split("Notification check (§11)", 1)
    assert len(section) == 2, "doctor prints no notification check"
    assert_is_the_notification_check("Notification check (§11)" + section[1])
    assert "ntfy" in strip_paths(out)  # the doorbell it now checks
    assert "`check`" in strip_paths(out)  # and what wakes the driver instead


def test_the_notification_check_offers_a_pause_or_a_gated_send(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    """H-007: the simplest event to fire is `hands pause` — one command, no job,
    cleared by `hands resume`. The gated send stays: it is the only way to file a
    real `job.held`, and `hands deny` clears it without spending a turn."""
    write_config(tmp_home, tmp_path)
    _code, out, _err = run()
    assert "hands --project demo pause" in strip_paths(out)
    assert "paused by human" in strip_paths(out)
    assert "hands --project demo resume" in strip_paths(out)  # how to clear it
    assert "--gate" in strip_paths(out) and "deny <job>" in strip_paths(out)


def test_the_notification_check_is_in_the_json_too(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    write_config(tmp_home, tmp_path)
    _code, out, _err = run("--json")
    report = json.loads(out)
    joined = "\n".join(report["wake_check"])
    assert_is_the_notification_check(joined)
    assert "ntfy" in strip_paths(joined)
    assert report["green"] is True


# ------------------------------------------- a config that will not load (§20)


def break_config(tmp_home: Path, tmp_path: Path) -> str:
    """A whole, valid config with one key emptied — the §20 refusal from U4(a)."""
    path = write_config(tmp_home, tmp_path)
    path.write_text(path.read_text().replace('ntfy_topic = "hands-test"', "ntfy_topic = ''"))
    return str(path)


def test_doctor_reports_a_config_error_as_a_failed_check(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    """Review 3 should-fix 8: doctor explains a broken config, it does not die of one.

    Every other command exits 1 with the bare `ConfigError`; doctor is the one
    whose job this is, so the error becomes its `config` row — normal report,
    status `fail`, exit 1.
    """
    break_config(tmp_home, tmp_path)

    code, out, err = run()

    assert code == 1
    # the normal report, not a bare message
    assert "hands doctor — project demo" in strip_paths(out)
    assert "ntfy_topic" in strip_paths(out), out  # the ConfigError's own words
    # including both valid choices
    assert "omit" in strip_paths(out) and "non-empty" in strip_paths(out)
    assert "fail" in strip_paths(out) and "config" in strip_paths(out)
    assert out.strip().splitlines()[-1] == "doctor: 1 check(s) failed"
    assert err == "", err


def test_the_failed_config_check_has_the_same_shape_in_json(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    """A caller parsing `--json` reads the same failed `config` check, not a new shape."""
    path = break_config(tmp_home, tmp_path)

    code, out, _err = run("--json")

    report = json.loads(out)
    found = {check["name"]: check for check in report["checks"]}
    assert code == 1
    assert report["green"] is False
    assert report["project"] == "demo"
    assert report["config"] == path
    assert found["config"]["status"] == "fail"
    assert "ntfy_topic" in strip_paths(found["config"]["detail"])
    assert any("ntfy" in strip_paths(line) for line in report["wake_check"])


def test_doctor_reports_a_missing_config_too(tmp_home: Path) -> None:
    """§14 step 1 runs doctor on a config that may not be there yet."""
    code, out, err = run()
    assert code == 1
    assert "demo.toml" in strip_paths(out)
    assert err == ""


def test_other_commands_still_exit_with_the_bare_config_error(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    """The reporting is doctor's alone; `status` (and every other command) is unchanged."""
    break_config(tmp_home, tmp_path)
    out, err = io.StringIO(), io.StringIO()

    code = main(["--project", "demo", "status"], stdout=out, stderr=err)

    assert code == 1
    assert out.getvalue() == ""
    assert err.getvalue().startswith("hands: ")
    assert "ntfy_topic" in strip_paths(err.getvalue())


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
        assert any("ntfy" in strip_paths(line) for line in report["wake_check"])

    drive(body)
