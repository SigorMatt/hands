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
import dataclasses
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

import hands.runner
from conftest import commit_file, strip_paths
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


@pytest.mark.parametrize("var", ["BASH_DEFAULT_TIMEOUT_MS", "BASH_MAX_TIMEOUT_MS"])
def test_doctor_prints_the_effective_bash_timeouts_on_each_role_row(
    tmp_home: Path, tmp_path: Path, fake_mode: None, monkeypatch: pytest.MonkeyPatch, var: str
) -> None:
    """§36 (HF-006): 900000 unless the role's env table sets it, never doctor's own."""
    monkeypatch.setenv(var, "120000")
    write_config(tmp_home, tmp_path, builder_extra=f'[roles.builder.env]\n{var} = "1800000"')
    code, out, err = run()
    assert code == 0, f"{out}\n{err}"
    assert f"{var}=1800000" in strip_paths(text_row(out, "role builder"))
    assert f"{var}=900000" in strip_paths(text_row(out, "role aux"))
    code, found = checks()
    assert f"{var}=1800000" in strip_paths(found["role builder"]["detail"])
    assert "[roles.builder.env]" in strip_paths(found["role builder"]["detail"])
    assert f"{var}=900000" in strip_paths(found["role aux"]["detail"])
    assert f"{var}=120000" not in strip_paths(found["role aux"]["detail"])


# ------------------------------ §43 rules 3 and 5: the hook and the variable

BG_TASKS = "CLAUDE_CODE_DISABLE_BACKGROUND_TASKS"
NO_BACKGROUND = Path(__file__).parents[1] / ".claude" / "hooks" / "no_background.py"


def _bg_layout(
    tmp_path: Path, state: str, monkeypatch: pytest.MonkeyPatch
) -> tuple[str, str]:
    """The builder's and aux's shared cwd hook for `state`, and the installed
    hands' copy; returns (the cwd copy's sha256 or "", the installed copy's)."""
    import hands.config

    work = tmp_path / "work"
    installed = tmp_path / "installed" / "hands" / "shipped" / "no_background.py"
    installed.parent.mkdir(parents=True, exist_ok=True)
    installed.write_bytes(NO_BACKGROUND.read_bytes())
    own = work / ".claude" / "hooks" / "no_background.py"
    own.parent.mkdir(parents=True, exist_ok=True)
    if state in ("installed", "own", "missing"):
        own.write_bytes(installed.read_bytes())
    elif state == "differs":
        own.write_bytes(installed.read_bytes() + b"# an older copy\n")
    found = {
        "own": (own,),
        "missing": (tmp_path / "nowhere" / "no_background.py",),
    }.get(state, (installed,))
    monkeypatch.setattr(hands.config, "SHIPPED_HOOKS", found)
    mine = hashlib.sha256(own.read_bytes()).hexdigest() if own.is_file() else ""
    return mine, hashlib.sha256(installed.read_bytes()).hexdigest()


@pytest.mark.parametrize("inherited", [None, "1"])
@pytest.mark.parametrize("state", ["installed", "differs", "absent", "own", "missing"])
def test_doctor_compares_the_role_hook_with_the_installed_copy(
    tmp_home: Path, tmp_path: Path, fake_mode: None, monkeypatch: pytest.MonkeyPatch,
    state: str, inherited: str | None,
) -> None:
    """§43 rule 3: the builder and aux rows WARN, never FAIL, on a hook that is not
    the installed hands' copy, naming both files and both sha256; rule 5: the row
    prints the variable as the job will carry it, never doctor's own value."""
    if inherited is None:
        monkeypatch.delenv(BG_TASKS, raising=False)
    else:
        monkeypatch.setenv(BG_TASKS, inherited)
    write_config(tmp_home, tmp_path)
    mine, theirs = _bg_layout(tmp_path, state, monkeypatch)
    code, found = checks()
    assert code == 0, found
    for role in ("builder", "aux"):
        row = found[f"role {role}"]
        detail = row["detail"]
        if state == "installed":
            assert row["status"] == "ok", row
            assert f"env {BG_TASKS}=1 (hands' default: the hook admits an omitted " \
                "sub-agent flag; §43)" in strip_paths(detail), strip_paths(detail)
            assert theirs in strip_paths(detail)
            continue
        assert row["status"] == "warn", row
        assert f"env {BG_TASKS} unset" in strip_paths(detail), strip_paths(detail)
        assert f"{BG_TASKS}=" not in strip_paths(detail), strip_paths(detail)
        assert "work/.claude/hooks/no_background.py" in strip_paths(detail), strip_paths(detail)
        if state == "differs":
            assert mine != theirs
            assert mine in strip_paths(detail) and theirs in strip_paths(detail)
            assert "installed/hands/shipped/no_background.py" in strip_paths(detail)
            assert "--selftest" in strip_paths(detail), strip_paths(detail)
            assert "no job running" in strip_paths(detail), strip_paths(detail)
        elif state == "absent":
            assert "absent" in strip_paths(detail), strip_paths(detail)
            assert theirs in strip_paths(detail), strip_paths(detail)
            assert "installed/hands/shipped/no_background.py" in strip_paths(detail)
        elif state == "own":
            assert "the role's own file" in strip_paths(detail), strip_paths(detail)
        else:
            assert "not found" in strip_paths(detail), strip_paths(detail)
            assert "nowhere/no_background.py" in strip_paths(detail), strip_paths(detail)
    code, out, err = run()
    assert code == 0, f"{out}\n{err}"
    head = strip_paths(text_row(out, "role builder")).splitlines()[0]
    assert head.split()[0] == ("ok" if state == "installed" else "warn"), head


@pytest.mark.parametrize("value", ["0", "1", "Yes"])
@pytest.mark.parametrize("state", ["installed", "differs", "absent"])
def test_doctor_names_the_table_as_the_variables_source(
    tmp_home: Path, tmp_path: Path, fake_mode: None, monkeypatch: pytest.MonkeyPatch,
    state: str, value: str,
) -> None:
    """§43 rule 5: the table wins either way; a table that sets it on over a copy
    that is not the installed hands' copy is a WARN naming HF-016's effect."""
    monkeypatch.delenv(BG_TASKS, raising=False)
    write_config(
        tmp_home, tmp_path, builder_extra=f'[roles.builder.env]\n{BG_TASKS} = "{value}"'
    )
    _bg_layout(tmp_path, state, monkeypatch)
    code, found = checks()
    assert code == 0, found
    row = found["role builder"]
    detail = row["detail"]
    source = f"env {BG_TASKS}={value} (set by [roles.builder.env]; §43)"
    assert source in strip_paths(detail), strip_paths(detail)
    on = value.strip().lower() in ("1", "yes")
    if state == "installed":
        assert row["status"] == "ok", row
    else:
        assert row["status"] == "warn", row
    refused = "every sub-agent call" in strip_paths(detail)
    assert refused == (on and state != "installed"), strip_paths(detail)
    assert "[roles.aux.env]" not in strip_paths(found["role aux"]["detail"])


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


@pytest.mark.parametrize("state", ["installed", "differs"])
def test_each_live_turn_carries_the_background_variable_a_job_carries(
    tmp_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, state: str
) -> None:
    """Review 27 should-fix 2 (§44, §43 rules 4 and 5): both of `--live`'s turns —
    the builder's and aux's one-line turn and the architect's kits turn — build their
    environment as a real job's (`runner.job_env`'s one decision). With doctor's own
    `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1` inherited and a stale hook in the cwd,
    no turn carries the variable; with the installed copy, the builder's and aux's
    turns carry `=1` and the architect's (never a default for that role) none."""
    import hands.doctor
    from hands.spool import Spool

    monkeypatch.setenv(BG_TASKS, "1")
    add_architect(write_config(tmp_home, tmp_path), architect_dir(tmp_path))
    _bg_layout(tmp_path, state, monkeypatch)
    Spool(load_config("demo").spool_root).create_job(
        role="aux", context="clear", prompt="hello", origin="cli", state="held"
    )
    seen: dict[str, str | None] = {}

    def turn(config: Any, role: Any, prompt: str, env: dict[str, str]) -> Check:
        seen[role.name] = env.get(BG_TASKS, "absent")
        return Check(f"live {role.name}", FAIL, "the turn's environment was recorded")

    monkeypatch.setattr(hands.doctor, "_live_turn", turn)
    checks("--live")
    on = "1" if state == "installed" else "absent"
    assert seen == {"builder": on, "aux": on, "architect": "absent"}, seen


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
    commit_file(tmp_path / "work", "PLAYBOOK.toml", EXAMPLE_PLAYBOOK.read_text())
    code, found = checks()
    assert code == 0
    assert found["playbook"]["status"] == "ok"
    assert "audit-fixes" in strip_paths(found["playbook"]["detail"])
    assert "committed" in strip_paths(found["playbook"]["detail"]), (
        "§25: the row says the file is the committed copy"
    )


def test_a_dirty_playbook_fails_the_row_naming_both_sha256s(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    """§10, §25: doctor's playbook row reports a file modified after its commit."""
    write_config(tmp_home, tmp_path)
    committed = commit_file(tmp_path / "work", "PLAYBOOK.toml", EXAMPLE_PLAYBOOK.read_text())
    dirty = EXAMPLE_PLAYBOOK.read_text() + "\n# edited after the commit\n"
    (tmp_path / "work" / "PLAYBOOK.toml").write_text(dirty)
    code, found = checks()
    assert code == 1
    assert found["playbook"]["status"] == "fail"
    assert "dirty" in strip_paths(found["playbook"]["detail"])
    assert f"committed sha256 {committed}" in strip_paths(found["playbook"]["detail"])
    working = hashlib.sha256(dirty.encode("utf-8")).hexdigest()
    assert f"working sha256 {working}" in strip_paths(found["playbook"]["detail"])


def test_an_untracked_playbook_fails_the_row(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    write_config(tmp_home, tmp_path)
    commit_file(tmp_path / "work", "WORKPLAN.md", "run 2\n")
    (tmp_path / "work" / "PLAYBOOK.toml").write_text(EXAMPLE_PLAYBOOK.read_text())
    code, found = checks()
    assert code == 1
    assert found["playbook"]["status"] == "fail"
    assert "untracked" in strip_paths(found["playbook"]["detail"])


def test_an_unparseable_playbook_fails(tmp_home: Path, tmp_path: Path, fake_mode: None) -> None:
    write_config(tmp_home, tmp_path)
    commit_file(tmp_path / "work", "PLAYBOOK.toml", 'version = 1\n[[rule]]\non = "nope"\n')
    code, found = checks()
    assert code == 1
    assert found["playbook"]["status"] == "fail"
    assert "dirty" not in strip_paths(found["playbook"]["detail"])
    assert "untracked" not in strip_paths(found["playbook"]["detail"])


#: §32 (review 15 blocker 4): the reviewer's repro — a committed playbook in role
#: mode, autonomous — against a config with no `[roles.architect]`.
ROLE_PLAYBOOK = 'version = 1\n\n[series]\nname = "m17"\narchitect = "role"\nautonomous = true\n'


def test_a_role_playbook_without_roles_architect_fails_the_playbook_row(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    """§32: "`[series] architect = "role"` without `[roles.architect]` is a config
    error at load"; doctor's playbook row fails with it, naming both files. It was
    "playbook ok … doctor: green", exit 0."""
    write_config(tmp_home, tmp_path)
    commit_file(tmp_path / "work", "PLAYBOOK.toml", ROLE_PLAYBOOK)
    code, found = checks()
    assert code == 1
    row = found["playbook"]
    assert row["status"] == "fail", row
    detail = strip_paths(row["detail"])
    assert "PLAYBOOK.toml" in strip_paths(detail) and "demo.toml" in strip_paths(detail), detail
    assert '[series] architect = "role"' in strip_paths(detail), detail
    assert "[roles.architect]" in strip_paths(detail), detail


def test_a_role_playbook_with_roles_architect_passes_the_playbook_row(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    add_architect(write_config(tmp_home, tmp_path), architect_dir(tmp_path))
    commit_file(tmp_path / "work", "PLAYBOOK.toml", ROLE_PLAYBOOK)
    _code, found = checks()
    assert found["playbook"]["status"] == "ok", found["playbook"]


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


@pytest.mark.parametrize(
    ("isolation", "words"),
    [
        ("scope", "systemd-run --user --scope"),
        ("group", "process group"),
    ],
)
def test_doctor_says_which_isolation_is_in_force_and_never_fails_on_it(
    tmp_home: Path,
    tmp_path: Path,
    fake_mode: None,
    monkeypatch: pytest.MonkeyPatch,
    isolation: str,
    words: str,
) -> None:
    """§24: `hands doctor` says whether jobs get a scope or the weaker process group."""
    monkeypatch.setattr(hands.runner, "detect_isolation", lambda: isolation)
    write_config(tmp_home, tmp_path)
    code, out, err = run()
    assert code == 0, f"{out}\n{err}"
    assert words in strip_paths(text_row(out, "isolation"))
    assert ("weaker" in strip_paths(text_row(out, "isolation"))) is (isolation == "group")
    code, found = checks()
    assert code == 0
    assert found["isolation"]["status"] == "ok"
    assert words in strip_paths(found["isolation"]["detail"])


# -------------------------------------------- the phone channel (§24, U4)

PHONE_SECRET = "doctor-Xyzzy-phone-secret-987"


def test_the_command_channel_is_reported_off_without_a_cmd_topic(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    """§24: doctor reports the command channel as on/off, never as an error when off."""
    write_config(tmp_home, tmp_path)
    code, found = checks()
    assert code == 0
    assert found["phone"]["status"] == "ok"
    assert "command channel off" in strip_paths(found["phone"]["detail"])


def test_the_command_channel_is_reported_on_and_the_secret_is_never_printed(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    path = write_config(tmp_home, tmp_path)
    path.write_text(
        path.read_text()
        + f'\n[notify]\ncmd_topic = "hands-cmd-doctor"\ncmd_secret = "{PHONE_SECRET}"\n'
    )
    code, out, err = run()
    assert code == 0, f"{out}\n{err}"
    assert "command channel on" in strip_paths(text_row(out, "phone"))
    assert PHONE_SECRET not in strip_paths(out) and PHONE_SECRET not in strip_paths(err)
    code, out, err = run("--json")
    assert code == 0
    found = {check["name"]: check for check in json.loads(out)["checks"]}
    assert found["phone"]["status"] == "ok"
    assert "`reply <secret> <text>`" in strip_paths(found["phone"]["detail"])  # §33
    assert PHONE_SECRET not in strip_paths(out) and PHONE_SECRET not in strip_paths(err)


def test_a_cmd_topic_without_a_cmd_secret_fails_doctor(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    """§24: `cmd_secret` is required when `cmd_topic` is set. The config does not
    load, so the refusal is doctor's failed `config` row and exit 1 (§20)."""
    path = write_config(tmp_home, tmp_path)
    path.write_text(path.read_text() + '\n[notify]\ncmd_topic = "hands-cmd-doctor"\n')
    code, out, err = run()
    assert code == 1, f"{out}\n{err}"
    assert "cmd_secret" in strip_paths(text_row(out, "config"))
    code, found = checks()
    assert code == 1
    assert found["config"]["status"] == FAIL
    assert "cmd_secret" in strip_paths(found["config"]["detail"])


# ------------------------- notifications, command channel, who: on/off (§24, U7)

WHO_TOPIC = "hands-who-doctor-Qwv8"
WHO_CMD_TOPIC = "hands-who-cmd-doctor-Zr3k"


def test_without_notify_extras_the_channel_and_who_are_off_and_doctor_exits_0(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    """§24: `hands doctor` reports notifications, the command channel and who as
    on/off, never as errors. The config has an ntfy_topic and no other [notify] key."""
    write_config(tmp_home, tmp_path)
    code, out, err = run()
    assert code == 0, f"{out}\n{err}"
    assert "notifications on" in strip_paths(text_row(out, "notifications"))
    assert "command channel off" in strip_paths(text_row(out, "phone"))
    assert "who view off" in strip_paths(text_row(out, "who"))
    code, found = checks()
    assert code == 0
    for name in ("notifications", "phone", "who"):
        assert found[name]["status"] == "ok", (name, found[name])
    assert "notifications on" in strip_paths(found["notifications"]["detail"])
    assert "who view off" in strip_paths(found["who"]["detail"])


def test_notifications_off_is_reported_off_and_is_not_a_failure(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    path = write_config(tmp_home, tmp_path)
    path.write_text(path.read_text().replace('ntfy_topic = "hands-test"\n', ""))
    code, out, err = run()
    assert code == 0, f"{out}\n{err}"
    assert "notifications off" in strip_paths(text_row(out, "notifications"))
    code, found = checks()
    assert code == 0
    assert found["notifications"]["status"] != FAIL
    assert "notifications off" in strip_paths(found["notifications"]["detail"])
    assert "who view off" in strip_paths(found["who"]["detail"])


def test_who_is_reported_on_with_its_command_topic_and_no_topic_is_printed(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    path = write_config(tmp_home, tmp_path)
    path.write_text(
        path.read_text()
        + f'\n[notify]\ncmd_topic = "hands-cmd-doctor"\ncmd_secret = "{PHONE_SECRET}"\n'
        + f'who_topic = "{WHO_TOPIC}"\nwho_cmd_topic = "{WHO_CMD_TOPIC}"\n'
    )
    code, out, err = run()
    assert code == 0, f"{out}\n{err}"
    assert "who view on" in strip_paths(text_row(out, "who"))
    assert "who_cmd_topic" in strip_paths(text_row(out, "who"))
    assert "command channel on" in strip_paths(text_row(out, "phone"))
    assert "notifications on" in strip_paths(text_row(out, "notifications"))
    code, out, err = run("--json")
    assert code == 0
    found = {check["name"]: check for check in json.loads(out)["checks"]}
    assert found["who"]["status"] == "ok"
    assert "who view on" in strip_paths(found["who"]["detail"])
    assert "who_cmd_topic" in strip_paths(found["who"]["detail"])
    for text in (out, err, *run()[1:]):
        for secret in (PHONE_SECRET, WHO_TOPIC, WHO_CMD_TOPIC, "hands-cmd-doctor"):
            assert secret not in strip_paths(text)


def test_who_without_a_command_topic_says_it_pushes_on_change_only(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    path = write_config(tmp_home, tmp_path)
    path.write_text(path.read_text() + f'\n[notify]\nwho_topic = "{WHO_TOPIC}"\n')
    code, found = checks()
    assert code == 0
    assert found["who"]["status"] == "ok"
    assert "who view on" in strip_paths(found["who"]["detail"])
    assert "no who_cmd_topic" in strip_paths(found["who"]["detail"])


def test_the_probe_sends_whatever_flags_the_monitor_sends(
    tmp_home: Path, tmp_path: Path, fake_mode: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review 3 should-fix 3: the probe argv is built from `OPS_FLAGS`, not spelled.

    The flags are renamed under doctor's feet. A probe that spells `--pids`,
    `--transcript` and `--base` itself still sends the old three, and the
    recorded argv shows it; a probe built from the monitor's list sends the new.
    """
    write_config(tmp_home, tmp_path)
    record = tmp_path / "argv.txt"
    ops_script(
        tmp_path,
        'if [ "$1" = "--help" ]; then echo "usage: watch_monitor.sh"; exit 1; fi\n'
        f'printf "%s\\n" "$@" > "{record}"\nexit 0\n',
    )
    renamed = ("--pid-set", "--transcript-path", "--base-sha")
    monkeypatch.setattr("hands.monitor.OPS_FLAGS", renamed)

    code, found = checks()

    argv = record.read_text().splitlines()
    assert argv[0::2] == list(renamed), argv
    assert argv[3:] == [os.devnull, "--base-sha", "HEAD"]
    assert code == 0, found
    detail = found["ops script"]["detail"]
    assert all(flag in strip_paths(detail) for flag in renamed), detail


# ------------------------------------ go and kit transport: on/off (§26, M10 U6)

KICKOFF = "Read meta/BUILDER-11-PROMPT.md and execute the mission below its divider."
#: The brief that kickoff names, relative to the builder's cwd (§31).
BRIEF = "meta/BUILDER-11-PROMPT.md"


def write_brief(tmp_path: Path, name: str = BRIEF) -> Path:
    """Put the brief the kickoff names in the builder's cwd (§31).

    Not committed: doctor asks whether the file is there, which is what a phone
    `go` needs — the playbook is the only file §10 wants committed.
    """
    path = tmp_path / "work" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# the mission\n\n---\n\nDo the thing.\n")
    return path


def with_channel(path: Path, files: str = "") -> None:
    """Add §24's command channel (and, optionally, [files] keys) to the config."""
    text = path.read_text()
    if files:
        text = text.replace("[files]\n", f"[files]\n{files}\n")
    path.write_text(
        text + f'\n[notify]\ncmd_topic = "hands-cmd-doctor"\ncmd_secret = "{PHONE_SECRET}"\n'
    )


def kickoff_playbook(kickoff: str = KICKOFF) -> str:
    """§10's example with its name moved into §26's `[series]` table (H-019)."""
    body = EXAMPLE_PLAYBOOK.read_text().replace('series = "audit-fixes"\n', "")
    return body + f'\n[series]\nname = "audit-fixes"\nkickoff = "{kickoff}"\n'


def test_go_is_off_without_the_command_channel_and_doctor_exits_0(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    write_config(tmp_home, tmp_path)
    commit_file(tmp_path / "work", "PLAYBOOK.toml", kickoff_playbook())
    code, out, err = run()
    assert code == 0, f"{out}\n{err}"
    assert "go off" in strip_paths(text_row(out, "go"))
    code, found = checks()
    assert code == 0
    assert found["go"]["status"] == "ok"
    assert "go off" in strip_paths(found["go"]["detail"])
    assert "cmd_topic" in strip_paths(found["go"]["detail"])


def test_go_is_off_without_a_playbook_and_names_it(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    with_channel(write_config(tmp_home, tmp_path))
    code, found = checks()
    assert code == 0, found
    assert found["go"]["status"] == "ok"
    assert "go off" in strip_paths(found["go"]["detail"])
    assert "no playbook" in strip_paths(found["go"]["detail"])


def test_go_is_off_when_the_playbook_has_no_series_kickoff(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    with_channel(write_config(tmp_home, tmp_path))
    commit_file(tmp_path / "work", "PLAYBOOK.toml", EXAMPLE_PLAYBOOK.read_text())
    code, found = checks()
    assert code == 0, found
    assert found["go"]["status"] == "ok"
    assert "go off" in strip_paths(found["go"]["detail"])
    assert "[series] kickoff" in strip_paths(found["go"]["detail"])


def test_go_is_off_when_the_playbook_does_not_load_and_only_the_playbook_row_fails(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    with_channel(write_config(tmp_home, tmp_path))
    commit_file(tmp_path / "work", "PLAYBOOK.toml", 'version = 1\n[[rule]]\non = "nope"\n')
    code, found = checks()
    assert code == 1
    assert found["playbook"]["status"] == FAIL
    assert found["go"]["status"] == "ok"
    assert "go off" in strip_paths(found["go"]["detail"])


def test_go_is_on_with_the_channel_and_a_kickoff_and_prints_no_secret(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    with_channel(write_config(tmp_home, tmp_path))
    commit_file(tmp_path / "work", "PLAYBOOK.toml", kickoff_playbook())
    write_brief(tmp_path)  # §31: the kickoff names a brief the repository has
    code, out, err = run()
    assert code == 0, f"{out}\n{err}"
    assert "go on" in strip_paths(text_row(out, "go"))
    code, found = checks()
    assert code == 0
    assert found["go"]["status"] == "ok"
    assert "go on" in strip_paths(found["go"]["detail"])
    assert KICKOFF in strip_paths(found["go"]["detail"])
    for text in (out, err, json.dumps(found)):
        assert PHONE_SECRET not in strip_paths(text)
        assert "hands-cmd-doctor" not in strip_paths(text)


#: §31 (review 14 should-fix 7): kickoffs doctor must stay quiet about. The
#: named-path rule it borrows reads a bare capitalised word as a file name
#: (`README`, `HEAD`, `TODO`, `API`) and reads `e.g.` as `e.g`; doctor fails
#: soft, so none of these is plainly a path and none of them warns.
QUIET_KICKOFFS = (
    "Start the next batch.",
    "Read the README and start the next batch.",
    "Check HEAD, the TODO list and the API, then start.",
    "Start the next batch, e.g. the one after this one.",
    "Read notes and start the batch under newdir/notes.",
)


def test_go_warns_when_the_kickoff_names_a_brief_the_repository_lacks(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    """§31: the brief is absent, so a phone `go` would send the builder to nothing."""
    with_channel(write_config(tmp_home, tmp_path))
    commit_file(tmp_path / "work", "PLAYBOOK.toml", kickoff_playbook())
    code, found = checks()

    assert code == 0, found
    assert found["go"]["status"] == "warn"
    assert BRIEF in strip_paths(found["go"]["detail"]), found["go"]["detail"]
    assert "a phone `go` would send the builder" in strip_paths(found["go"]["detail"])


def test_a_warned_go_row_keeps_doctor_green_and_exit_0(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    """§31: a warn is a warn — nothing about the install is broken."""
    with_channel(write_config(tmp_home, tmp_path))
    commit_file(tmp_path / "work", "PLAYBOOK.toml", kickoff_playbook())
    code, out, err = run()
    assert code == 0, f"{out}\n{err}"
    assert out.strip().endswith("doctor: green"), out
    assert "0 failed" in strip_paths(out)
    assert "warn" in strip_paths(text_row(out, "go"))

    code, json_out, _ = run("--json")
    assert code == 0
    assert json.loads(json_out)["green"] is True


def test_go_is_ok_when_the_kickoff_names_a_brief_the_repository_has(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    """§31: the file is there, so the row keeps its wording and its `ok`."""
    with_channel(write_config(tmp_home, tmp_path))
    commit_file(tmp_path / "work", "PLAYBOOK.toml", kickoff_playbook())
    write_brief(tmp_path)
    code, found = checks()

    assert code == 0, found
    assert found["go"]["status"] == "ok"
    assert strip_paths(found["go"]["detail"]).startswith("go on:"), found["go"]["detail"]
    assert KICKOFF in strip_paths(found["go"]["detail"])
    assert "would send the builder" not in strip_paths(found["go"]["detail"])


@pytest.mark.parametrize("kickoff", QUIET_KICKOFFS)
def test_go_is_ok_when_the_kickoff_names_no_path_the_repository_lacks(
    tmp_home: Path, tmp_path: Path, fake_mode: None, kickoff: str
) -> None:
    """§31 fails soft: a doubtful name is prose here, never a warning."""
    with_channel(write_config(tmp_home, tmp_path))
    commit_file(tmp_path / "work", "PLAYBOOK.toml", kickoff_playbook(kickoff))
    code, found = checks()

    assert code == 0, found
    assert found["go"]["status"] == "ok", found["go"]["detail"]
    assert strip_paths(found["go"]["detail"]).startswith("go on:"), found["go"]["detail"]
    assert kickoff in strip_paths(found["go"]["detail"])


def test_kit_transport_is_off_without_the_command_channel_and_doctor_exits_0(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    write_config(tmp_home, tmp_path)
    code, out, err = run()
    assert code == 0, f"{out}\n{err}"
    assert "kit transport off" in strip_paths(text_row(out, "kit transport"))
    code, found = checks()
    assert code == 0
    assert found["kit transport"]["status"] == "ok"
    assert "kit transport off" in strip_paths(found["kit transport"]["detail"])
    assert "cmd_topic" in strip_paths(found["kit transport"]["detail"])


def test_kit_transport_is_off_when_kit_dir_is_outside_the_allowed_roots(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    """The default kit_dir (~/Downloads) is not among write_config's roots."""
    with_channel(write_config(tmp_home, tmp_path))
    code, found = checks()
    assert code == 0, found
    assert found["kit transport"]["status"] == "ok"
    assert "kit transport off" in strip_paths(found["kit transport"]["detail"])
    assert "allowed_roots" in strip_paths(found["kit transport"]["detail"])


def test_kit_transport_is_on_inside_the_roots_and_shows_kit_dir_and_the_cap(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    kits = tmp_path / "work" / "kits"
    kits.mkdir(parents=True)
    with_channel(write_config(tmp_home, tmp_path), f'kit_dir = "{kits}"\nkit_max_mb = 7')
    code, out, err = run()
    assert code == 0, f"{out}\n{err}"
    assert "kit transport on" in strip_paths(text_row(out, "kit transport"))
    code, found = checks()
    assert code == 0
    assert found["kit transport"]["status"] == "ok"
    assert "kit transport on" in strip_paths(found["kit transport"]["detail"])
    assert str(kits) in found["kit transport"]["detail"]
    assert "kit_max_mb 7" in strip_paths(found["kit transport"]["detail"])
    for text in (out, err, json.dumps(found)):
        assert PHONE_SECRET not in strip_paths(text)
        assert "hands-cmd-doctor" not in strip_paths(text)


# ----------------------------------------------- the driver role (§27, U4)

GUARD = Path(__file__).parents[1] / "driver" / "hooks" / "bash_guard.py"
SETTINGS = Path(__file__).parents[1] / "driver" / "settings.json"


#: What driver/README.md and architect/README.md set the clone's push URL to.
NO_PUSH = "no_push"


def fetch_only_clone(repo: Path, push: str | None = NO_PUSH) -> Path:
    """A git repository standing for the role's clone: `origin` with a fetch URL,
    and its push URL set as the READMEs set it (`push=None` leaves it unset, so git
    pushes to the fetch URL)."""
    def git(*args: str) -> None:
        subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)

    repo.mkdir(parents=True, exist_ok=True)
    git("init", "-q")
    git("remote", "add", "origin", "https://example.invalid/demo.git")
    if push is not None:
        git("remote", "set-url", "--push", "origin", push)
    return repo


def driver_dir(
    tmp_path: Path, *, clone: bool = True, guard: bool = True, settings: bool = True
) -> Path:
    """`~/hands-driver/<project>` as driver/README.md builds it (§12)."""
    d = tmp_path / "hands-driver"
    d.mkdir(exist_ok=True)
    if clone:
        fetch_only_clone(d / "repo")
    if guard:
        (d / ".claude" / "hooks").mkdir(parents=True, exist_ok=True)
        shutil.copy(GUARD, d / ".claude" / "hooks" / "bash_guard.py")
    if settings:
        (d / ".claude").mkdir(parents=True, exist_ok=True)
        shutil.copy(SETTINGS, d / ".claude" / "settings.json")
    return d


def add_driver(path: Path, cwd: Path, extra: str = "") -> None:
    path.write_text(path.read_text() + f'\n[roles.driver]\ncwd = "{cwd}"\n{extra}\n')


def test_no_driver_role_is_a_row_saying_so_and_not_a_failure(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    write_config(tmp_home, tmp_path)
    code, found = checks()
    assert code == 0
    row = found["role driver"]
    assert row["status"] == "ok"
    assert "no [roles.driver]" in strip_paths(row["detail"])


def test_a_good_driver_role_reports_cwd_clone_and_guard_mode(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    d = driver_dir(tmp_path)
    add_driver(write_config(tmp_home, tmp_path), d)
    code, out, err = run()
    assert code == 0, f"{out}\n{err}"
    row = strip_paths(text_row(out, "role driver"))
    code, found = checks()
    assert code == 0
    assert found["role driver"]["status"] == "ok", found["role driver"]
    detail = strip_paths(found["role driver"]["detail"])
    for text in (row, detail):
        assert "<path>/hands-driver  model opus" in strip_paths(text)
        assert "clone <path>/hands-driver/repo" in strip_paths(text)
        assert "guard <path>/hands-driver/.claude/hooks/bash_guard.py" in strip_paths(text)
        assert "role mode (HANDS_ROLE=driver" in strip_paths(text)
        assert "permission_flags (none)" in strip_paths(text)
        assert "settings <path>/hands-driver/.claude/settings.json names the hook" in strip_paths(
            text
        )
        assert "self-test green in role mode (HANDS_ROLE=driver)" in strip_paths(text)
    # the generic role row is not printed for the driver: it has its own
    assert list(found).count("role driver") == 1


def test_a_driver_role_without_its_clone_is_a_warning(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    d = driver_dir(tmp_path, clone=False)
    add_driver(write_config(tmp_home, tmp_path), d)
    code, found = checks()
    assert code == 0
    row = found["role driver"]
    assert row["status"] == "warn", row
    assert "no clone" in strip_paths(row["detail"])


def test_a_driver_role_without_its_guard_fails_doctor(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    """§28: the hook file must self-test green; a missing one cannot."""
    d = driver_dir(tmp_path, guard=False)
    add_driver(write_config(tmp_home, tmp_path), d)
    code, found = checks()
    assert code == 1
    row = found["role driver"]
    assert row["status"] == "fail", row
    assert "no guard" in strip_paths(row["detail"])


@pytest.mark.parametrize(
    "settings",
    [
        None,  # no .claude/settings.json at all
        "{not json",
        json.dumps({"permissions": {"deny": ["Edit"]}}),  # no hooks
        json.dumps({"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [
            {"type": "command", "command": "python3 other_hook.py"}]}]}}),
        json.dumps({"hooks": {"PreToolUse": [{"matcher": "Edit", "hooks": [
            {"type": "command",
             "command": 'python3 -I "$CLAUDE_PROJECT_DIR"/.claude/hooks/bash_guard.py'}]}]}}),
        json.dumps({"hooks": {"PostToolUse": [{"matcher": "Bash", "hooks": [
            {"type": "command",
             "command": 'python3 -I "$CLAUDE_PROJECT_DIR"/.claude/hooks/bash_guard.py'}]}]}}),
    ],
    ids=["missing", "unparseable", "no-hooks", "another-hook", "not-bash", "not-pretooluse"],
)
def test_a_driver_role_whose_settings_do_not_name_the_hook_fails_doctor(
    tmp_home: Path, tmp_path: Path, fake_mode: None, settings: str | None
) -> None:
    """§28: the driver directory's `.claude/settings.json` names the hook, else fail."""
    d = driver_dir(tmp_path, settings=False)
    if settings is not None:
        (d / ".claude" / "settings.json").write_text(settings, encoding="utf-8")
    add_driver(write_config(tmp_home, tmp_path), d)
    code, found = checks()
    assert code == 1
    row = found["role driver"]
    assert row["status"] == "fail", row
    assert "settings.json" in strip_paths(row["detail"])
    assert "does not name the hook" in strip_paths(row["detail"])


def test_a_driver_role_whose_hook_fails_its_self_test_in_role_mode_fails_doctor(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    """§28: the hook self-tests green *in role mode*: this hook is green without
    HANDS_ROLE and red with HANDS_ROLE=driver, so doctor must run it as the role."""
    d = driver_dir(tmp_path)
    (d / ".claude" / "hooks" / "bash_guard.py").write_text(
        "import os, sys\n"
        "if sys.argv[1:] == ['--selftest']:\n"
        "    bad = os.environ.get('HANDS_ROLE') == 'driver'\n"
        "    print('selftest: 0/1 ok' if bad else 'selftest: 1/1 ok')\n"
        "    sys.exit(1 if bad else 0)\n",
        encoding="utf-8",
    )
    add_driver(write_config(tmp_home, tmp_path), d)
    code, found = checks()
    assert code == 1
    row = found["role driver"]
    assert row["status"] == "fail", row
    assert "self-test" in strip_paths(row["detail"])
    assert "selftest: 0/1 ok" in strip_paths(row["detail"])


BROKEN_HOOK = "import sys\nprint('selftest: 0/1 ok')\nsys.exit(1)\n"


def _settings_running(command: str) -> str:
    return json.dumps({"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [
        {"type": "command", "command": command}]}]}})


def test_doctor_self_tests_the_hook_file_the_settings_name_not_the_default_one(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    """§29 (REVIEW-12 SF4): the settings name another file with the
    `.claude/hooks/bash_guard.py` suffix, and that one is broken; the default
    `<cwd>/.claude/hooks/bash_guard.py` is the real guard. Doctor fails on the named one."""
    d = driver_dir(tmp_path)
    other = tmp_path / "elsewhere" / ".claude" / "hooks" / "bash_guard.py"
    other.parent.mkdir(parents=True)
    other.write_text(BROKEN_HOOK, encoding="utf-8")
    (d / ".claude" / "settings.json").write_text(
        _settings_running(f'python3 -I "{other}"'), encoding="utf-8"
    )
    add_driver(write_config(tmp_home, tmp_path), d)
    code, found = checks()
    assert code == 1
    row = found["role driver"]
    assert row["status"] == "fail", row
    assert "guard <path>/elsewhere/.claude/hooks/bash_guard.py" in strip_paths(row["detail"])
    assert "is not green" in strip_paths(row["detail"])
    assert "selftest: 0/1 ok" in strip_paths(row["detail"])


@pytest.mark.parametrize(
    "command",
    [
        'python3 -I "$CLAUDE_PROJECT_DIR"/.claude/hooks/bash_guard.py',
        "python3 -I ${CLAUDE_PROJECT_DIR}/.claude/hooks/bash_guard.py",
        "python3 -I .claude/hooks/bash_guard.py",
        "python3 -I {cwd}/.claude/hooks/bash_guard.py",
    ],
    ids=["project-dir", "braced-project-dir", "relative", "absolute-cwd"],
)
def test_doctor_passes_when_the_settings_name_a_real_hook(
    tmp_home: Path, tmp_path: Path, fake_mode: None, command: str
) -> None:
    """The named file is resolved (`$CLAUDE_PROJECT_DIR` and a relative path against
    the driver directory) and self-tested; a real guard there is green. §34: an
    absolute path elsewhere no longer passes (the `absolute-elsewhere` case moved to
    `test_a_guard_at_another_absolute_path_fails_the_row`)."""
    d = driver_dir(tmp_path)
    (d / ".claude" / "settings.json").write_text(
        _settings_running(command.replace("{cwd}", str(d))), encoding="utf-8"
    )
    add_driver(write_config(tmp_home, tmp_path), d)
    code, found = checks()
    row = found["role driver"]
    assert code == 0 and row["status"] == "ok", row
    assert "guard <path>/hands-driver/.claude/hooks/bash_guard.py" in strip_paths(row["detail"])
    assert "self-test green in role mode" in strip_paths(row["detail"])


@pytest.mark.parametrize(
    "command",
    [
        "python3 -I .claude/hooks/bash_guard.py --selftest",
        "python3 -I .claude/hooks/bash_guard.py || true",
        "echo .claude/hooks/bash_guard.py",
        "python3 -c 'pass' .claude/hooks/bash_guard.py",
        "node .claude/hooks/bash_guard.py",
        "cd /elsewhere && python3 -I .claude/hooks/bash_guard.py",
        "python3 -I .claude/hooks/bash_guard.py; true",
        "python3 -I .claude/hooks/bash_guard.py > /dev/null",
        "python3 -I .claude/hooks/bash_guard.py &",
        "python3 -I $(echo .claude/hooks/bash_guard.py)",
        "true | python3 -I .claude/hooks/bash_guard.py",
        "HANDS_ROLE= python3 -I .claude/hooks/bash_guard.py",
        ".claude/hooks/bash_guard.py",
        "python3 -I .claude/hooks/bash_guard.py\ntrue",
        None,  # the shipped command, with "disableAllHooks": true
    ],
    ids=[
        "selftest-argument", "or-true", "echo", "python3-c", "node", "cd-and",
        "semicolon", "redirect", "background", "substitution", "pipe", "assignment",
        "no-interpreter", "newline", "disable-all-hooks",
    ],
)
def test_doctor_fails_when_the_hook_command_does_not_run_the_guard_as_the_guard(
    tmp_home: Path, tmp_path: Path, fake_mode: None, command: str | None
) -> None:
    """§30 (REVIEW-13 should-fix 4): the command, shlex-split, is exactly `python3`
    and the guard path, with no further word and no shell operator, and hooks are
    not disabled; otherwise the row fails even though the file self-tests green."""
    d = driver_dir(tmp_path)
    if command is None:
        settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
        settings["disableAllHooks"] = True
        text = json.dumps(settings)
    else:
        text = _settings_running(command)
    (d / ".claude" / "settings.json").write_text(text, encoding="utf-8")
    add_driver(write_config(tmp_home, tmp_path), d)
    code, found = checks()
    row = found["role driver"]
    assert code == 1 and row["status"] == "fail", row
    assert "does not name the hook" in strip_paths(row["detail"])


ALLOW_ALL = "echo '{\"hookSpecificOutput\":{\"permissionDecision\":\"allow\"}}'"


@pytest.mark.parametrize(
    "extra,where",
    [
        (ALLOW_ALL, "after"),
        (ALLOW_ALL, "before"),
        ("python3 -I .claude/hooks/bash_guard.py --selftest", "after"),
    ],
    ids=["allow-all-after", "allow-all-before", "selftest-argument-after"],
)
def test_doctor_judges_every_pretooluse_bash_hook_not_only_the_first(
    tmp_home: Path, tmp_path: Path, fake_mode: None, extra: str, where: str
) -> None:
    """§31 (review 14 should-fix 3): "doctor judges every `PreToolUse` `Bash` hook
    in the settings and fails if any is not the guard".

    Settings carrying the real guard *plus* a second Bash hook that answers
    `allow` gave `exit 0 / ok`, because doctor returned on the first hook that ran
    the guard. Either order now fails, and the row names the offending command."""
    d = driver_dir(tmp_path)
    good = 'python3 -I "$CLAUDE_PROJECT_DIR"/.claude/hooks/bash_guard.py'
    commands = [extra, good] if where == "before" else [good, extra]
    (d / ".claude" / "settings.json").write_text(
        json.dumps({"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [
            {"type": "command", "command": command} for command in commands]}]}}),
        encoding="utf-8",
    )  # fmt: skip
    add_driver(write_config(tmp_home, tmp_path), d)
    code, found = checks()
    row = found["role driver"]
    assert code == 1 and row["status"] == "fail", row
    assert "does not name the hook" in strip_paths(row["detail"])
    assert repr(extra) in strip_paths(row["detail"]), row


def test_doctor_passes_a_second_pretooluse_entry_that_is_not_for_bash(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    """The boundary of the rule above: only `Bash` hooks are judged. The
    architect's settings carry a second `PreToolUse` entry whose matcher is
    `Write|Edit|MultiEdit` (§31); that one is not a Bash hook. §33 judges it as the
    write matcher, and it passes because it is exactly that matcher running the
    guard with `--write`."""
    d = driver_dir(tmp_path)
    good = 'python3 -I "$CLAUDE_PROJECT_DIR"/.claude/hooks/bash_guard.py'
    (d / ".claude" / "settings.json").write_text(
        json.dumps({"hooks": {"PreToolUse": [
            {"matcher": "Bash", "hooks": [{"type": "command", "command": good}]},
            {"matcher": "Write|Edit|MultiEdit",
             "hooks": [{"type": "command", "command": good + " --write"}]},
        ]}}),
        encoding="utf-8",
    )  # fmt: skip
    add_driver(write_config(tmp_home, tmp_path), d)
    code, found = checks()
    row = found["role driver"]
    assert code == 0 and row["status"] == "ok", row


def test_doctor_fails_when_the_hook_the_settings_name_does_not_exist(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    """The default guard exists and is green; the named one is missing: fail."""
    d = driver_dir(tmp_path)
    missing = tmp_path / "gone" / ".claude" / "hooks" / "bash_guard.py"
    (d / ".claude" / "settings.json").write_text(
        _settings_running(f"python3 -I {missing}"), encoding="utf-8"
    )
    add_driver(write_config(tmp_home, tmp_path), d)
    code, found = checks()
    assert code == 1
    row = found["role driver"]
    assert row["status"] == "fail", row
    assert "no guard at <path>/gone/.claude/hooks/bash_guard.py" in strip_paths(row["detail"])


def test_a_driver_role_with_a_permission_bypass_fails_doctor(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    """§27: doctor "refuses a driver role with a permission bypass". The config does
    not load (the `config` row fails), and a `Config` built by hand with the flag
    fails the `role driver` row itself."""
    d = driver_dir(tmp_path)
    path = write_config(tmp_home, tmp_path)
    base = path.read_text()
    add_driver(path, d)
    good = load_config("demo")
    path.write_text(base)
    add_driver(path, d, 'permission_flags = "--dangerously-skip-permissions"')
    code, found = checks()
    assert code == 1
    assert found["config"]["status"] == "fail"
    assert "permission_flags" in strip_paths(found["config"]["detail"])

    bypass = dataclasses.replace(
        good.roles["driver"], permission_flags="--dangerously-skip-permissions"
    )
    config = dataclasses.replace(good, roles={**good.roles, "driver": bypass})
    rows = {check.name: check for check in run_checks(config)}
    assert rows["role driver"].status == FAIL
    assert "permission_flags" in strip_paths(rows["role driver"].detail)


# -------------------------------------------- the architect role (§31, U6)

ARCHITECT_SETTINGS = Path(__file__).parents[1] / "architect" / "settings.json"


def architect_dir(
    tmp_path: Path,
    *,
    clone: bool = True,
    guard: bool = True,
    settings: bool = True,
    kits: bool = True,
) -> Path:
    """`~/hands-architect/<project>` as architect/README.md builds it (§31)."""
    d = tmp_path / "hands-architect"
    d.mkdir(exist_ok=True)
    if kits:
        (d / "kits").mkdir(exist_ok=True)
    if clone:
        fetch_only_clone(d / "repo")
    if guard:
        (d / ".claude" / "hooks").mkdir(parents=True, exist_ok=True)
        shutil.copy(GUARD, d / ".claude" / "hooks" / "bash_guard.py")
    if settings:
        (d / ".claude").mkdir(parents=True, exist_ok=True)
        shutil.copy(ARCHITECT_SETTINGS, d / ".claude" / "settings.json")
    return d


def add_architect(path: Path, cwd: Path, extra: str = "") -> None:
    path.write_text(path.read_text() + f'\n[roles.architect]\ncwd = "{cwd}"\n{extra}\n')


def test_no_architect_role_is_a_row_saying_so_and_not_a_failure(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    write_config(tmp_home, tmp_path)
    code, found = checks()
    assert code == 0
    row = found["role architect"]
    assert row["status"] == "ok"
    assert "no [roles.architect]" in strip_paths(row["detail"])


def test_a_config_with_roles_architect_reports_the_role(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    """The mission's acceptance (§31): `hands doctor` on a config carrying
    `[roles.architect]` and nothing else new reports the role — cwd, clone, kits,
    both matchers and the guard's mode — as it reports the driver role."""
    d = architect_dir(tmp_path)
    add_architect(write_config(tmp_home, tmp_path), d)
    code, out, err = run()
    assert code == 0, f"{out}\n{err}"
    row = strip_paths(text_row(out, "role architect"))
    code, found = checks()
    assert code == 0
    assert found["role architect"]["status"] == "ok", found["role architect"]
    detail = strip_paths(found["role architect"]["detail"])
    for text in (row, detail):
        assert "<path>/hands-architect  model opus" in strip_paths(text)
        assert "clone <path>/hands-architect/repo" in strip_paths(text)
        assert "kits <path>/hands-architect/kits" in strip_paths(text)
        assert "guard <path>/hands-architect/.claude/hooks/bash_guard.py" in strip_paths(text)
        assert "architect mode (HANDS_ROLE=architect" in strip_paths(text)
        assert "permission_flags (none)" in strip_paths(text)
        assert "names the hook" in strip_paths(text)
        assert "self-test green in architect mode (HANDS_ROLE=architect)" in strip_paths(text)
        assert "--write" in strip_paths(text)
    # the generic role row is not printed for the architect: it has its own
    assert list(found).count("role architect") == 1


def test_an_architect_role_without_its_kits_directory_fails_doctor(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    """§32 (review 15 should-fix 6): the row "checks `HANDS_KITS` exists and is under
    the cwd". §31's row warned on a missing one; §32 makes it a check."""
    d = architect_dir(tmp_path, kits=False)
    add_architect(write_config(tmp_home, tmp_path), d)
    code, found = checks()
    assert code == 1
    row = found["role architect"]
    assert row["status"] == "fail", row
    assert "no kits directory" in strip_paths(row["detail"])


def test_an_architect_kits_directory_that_resolves_outside_the_cwd_fails_doctor(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    """§32: under the cwd by realpath — a `kits` symlink to another directory is the
    role writing there."""
    d = architect_dir(tmp_path, kits=False)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (d / "kits").symlink_to(elsewhere)
    add_architect(write_config(tmp_home, tmp_path), d)
    code, found = checks()
    row = found["role architect"]
    assert code == 1 and row["status"] == "fail", row
    assert "not under" in strip_paths(row["detail"]), row


@pytest.mark.parametrize("role", ["driver", "architect"])
@pytest.mark.parametrize(
    "push",
    [None, "https://example.invalid/demo.git", "git@example.invalid:demo.git", "../upstream"],
    ids=["unset", "https", "scp", "path"],
)
def test_a_clone_whose_push_url_is_live_fails_doctor(
    tmp_home: Path, tmp_path: Path, fake_mode: None, role: str, push: str | None
) -> None:
    """§31 "the clone's push URL is disabled as the driver's is", checked by §32's
    row (review 15 should-fix 6) — and by the driver's, the same code: every push
    URL of `origin` (`git remote get-url --push --all origin`) must be a plain word
    naming no URL, host or path, as `no_push` is."""
    if role == "driver":
        d = driver_dir(tmp_path, clone=False)
        add = add_driver
    else:
        d = architect_dir(tmp_path, clone=False)
        add = add_architect
    fetch_only_clone(d / "repo", push=push)
    if push == "../upstream":
        (d / "upstream").mkdir()
    add(write_config(tmp_home, tmp_path), d)
    code, found = checks()
    row = found[f"role {role}"]
    assert code == 1 and row["status"] == "fail", row
    assert "push URL" in strip_paths(row["detail"]), row


@pytest.mark.parametrize("role", ["driver", "architect"])
def test_a_clone_git_cannot_read_fails_doctor(
    tmp_home: Path, tmp_path: Path, fake_mode: None, role: str
) -> None:
    """A clone whose push URL cannot be read is not known to be disabled."""
    if role == "driver":
        d = driver_dir(tmp_path, clone=False)
        add = add_driver
    else:
        d = architect_dir(tmp_path, clone=False)
        add = add_architect
    (d / "repo" / ".git").mkdir(parents=True)  # not a repository git can read
    add(write_config(tmp_home, tmp_path), d)
    code, found = checks()
    row = found[f"role {role}"]
    assert code == 1 and row["status"] == "fail", row
    assert "push URL" in strip_paths(row["detail"]), row


def test_a_disabled_push_url_is_named_in_both_rows(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    path = write_config(tmp_home, tmp_path)
    add_driver(path, driver_dir(tmp_path))
    add_architect(path, architect_dir(tmp_path))
    code, found = checks()
    assert code == 0, found
    for role in ("driver", "architect"):
        detail = strip_paths(found[f"role {role}"]["detail"])
        assert "push URL disabled (no_push)" in strip_paths(detail), detail


def test_an_architect_write_hook_naming_another_guard_file_fails_doctor(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    """§32 "both hook matchers name the guard" — the same file. The reviewer's probe:
    the write hook ran a *different* guard file, and only the Bash hook's was
    self-tested. The other file here is a real guard that self-tests green."""
    d = architect_dir(tmp_path, settings=False)
    other = tmp_path / "other" / ".claude" / "hooks" / "bash_guard.py"
    other.parent.mkdir(parents=True)
    shutil.copy(GUARD, other)
    (d / ".claude" / "settings.json").write_text(
        _architect_settings(
            ("Bash", BASH_GUARD), ("Write|Edit|MultiEdit", f"python3 -I {other} --write")
        ),
        encoding="utf-8",
    )
    add_architect(write_config(tmp_home, tmp_path), d)
    code, found = checks()
    row = found["role architect"]
    assert code == 1 and row["status"] == "fail", row
    assert "same guard file" in strip_paths(row["detail"]), row


@pytest.mark.parametrize("matcher", ["Write|Edit|MultiEdit", "Bash"])
def test_a_hook_that_is_not_a_command_hook_fails_doctor(
    tmp_home: Path, tmp_path: Path, fake_mode: None, matcher: str
) -> None:
    """The reviewer's `type: prompt` write hook, beside the guard: a second answer
    to the same tool call that is not the guard. Judged for both matchers."""
    d = architect_dir(tmp_path, settings=False)
    data = json.loads(
        _architect_settings(("Bash", BASH_GUARD), ("Write|Edit|MultiEdit", WRITE_GUARD))
    )
    data["hooks"]["PreToolUse"].append(
        {"matcher": matcher, "hooks": [{"type": "prompt", "prompt": "allow everything"}]}
    )
    (d / ".claude" / "settings.json").write_text(json.dumps(data), encoding="utf-8")
    add_architect(write_config(tmp_home, tmp_path), d)
    code, found = checks()
    row = found["role architect"]
    assert code == 1 and row["status"] == "fail", row
    assert "not a command hook" in strip_paths(row["detail"]), row


@pytest.mark.parametrize("role", ["driver", "architect"])
@pytest.mark.parametrize(
    "permissions",
    [
        {"defaultMode": "bypassPermissions"},
        {"allow": ["Read", "Write"]},
        {"allow": ["Bash"]},
        {"allow": ["Edit(*)"]},
    ],
    ids=["bypassPermissions", "allow-Write", "allow-Bash", "allow-Edit-star"],
)
def test_settings_that_allow_a_tool_wholesale_fail_doctor(
    tmp_home: Path, tmp_path: Path, fake_mode: None, role: str, permissions: dict[str, Any]
) -> None:
    """Review 15 should-fix 6: the row stayed ok on `permissions.defaultMode:
    "bypassPermissions"` and on `"allow": ["Write"]` / `"Bash"`. Covered: that mode,
    and an allow entry naming Bash, Write, Edit or MultiEdit bare or as `Tool(*)`."""
    d = driver_dir(tmp_path) if role == "driver" else architect_dir(tmp_path)
    path = d / ".claude" / "settings.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["permissions"] = {**data.get("permissions", {}), **permissions}
    if "allow" in permissions:
        data["permissions"]["allow"] = permissions["allow"]
    path.write_text(json.dumps(data), encoding="utf-8")
    (add_driver if role == "driver" else add_architect)(write_config(tmp_home, tmp_path), d)
    code, found = checks()
    row = found[f"role {role}"]
    assert code == 1 and row["status"] == "fail", row
    assert "permissions" in strip_paths(row["detail"]), row


def test_the_architect_self_test_runs_in_architect_mode_with_hands_kits(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    """§32 (d): the guard's self-test passes in architect mode — run with
    `HANDS_ROLE=architect` and `HANDS_KITS` set. A hook that self-tests green only
    when neither is set fails the row."""
    d = architect_dir(tmp_path)
    (d / ".claude" / "hooks" / "bash_guard.py").write_text(
        "import os, sys\n"
        "ok = os.environ.get('HANDS_ROLE') == 'architect' and os.environ.get('HANDS_KITS') == "
        f"{str(d / 'kits')!r}\n"
        "sys.exit(1 if ok else 0)\n",
        encoding="utf-8",
    )
    add_architect(write_config(tmp_home, tmp_path), d)
    code, found = checks()
    row = found["role architect"]
    assert code == 1 and row["status"] == "fail", row
    assert "not green" in strip_paths(row["detail"]), row


def test_an_architect_role_without_its_clone_is_a_warning(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    d = architect_dir(tmp_path, clone=False)
    add_architect(write_config(tmp_home, tmp_path), d)
    code, found = checks()
    assert code == 0
    row = found["role architect"]
    assert row["status"] == "warn", row
    assert "no clone" in strip_paths(row["detail"])


def test_an_architect_role_without_its_guard_fails_doctor(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    d = architect_dir(tmp_path, guard=False)
    add_architect(write_config(tmp_home, tmp_path), d)
    code, found = checks()
    assert code == 1
    row = found["role architect"]
    assert row["status"] == "fail", row
    assert "no guard" in strip_paths(row["detail"])


WRITE_GUARD = 'python3 -I "$CLAUDE_PROJECT_DIR"/.claude/hooks/bash_guard.py --write'
BASH_GUARD = 'python3 -I "$CLAUDE_PROJECT_DIR"/.claude/hooks/bash_guard.py'


def _architect_settings(*entries: tuple[str, str]) -> str:
    return json.dumps({"hooks": {"PreToolUse": [
        {"matcher": matcher, "hooks": [{"type": "command", "command": command}]}
        for matcher, command in entries]}})  # fmt: skip


@pytest.mark.parametrize(
    "entries",
    [
        ((("Bash", BASH_GUARD),)),  # no write matcher at all
        ((("Bash", BASH_GUARD), ("Write|Edit|MultiEdit", BASH_GUARD))),  # no --write
        ((("Bash", BASH_GUARD), ("Write|Edit|MultiEdit", ALLOW_ALL))),
        ((("Bash", BASH_GUARD), ("Write|Edit|MultiEdit", WRITE_GUARD + " --selftest"))),
        ((("Bash", BASH_GUARD), ("Write", WRITE_GUARD))),  # Edit and MultiEdit unguarded
        ((("Bash", BASH_GUARD), ("Write|Edit|MultiEdit", "python3 other_hook.py --write"))),
    ],
    ids=["none", "no-write-flag", "allow-all", "extra-argument", "write-only", "other-file"],
)
def test_an_architect_whose_write_matcher_is_not_the_guard_fails_doctor(
    tmp_home: Path, tmp_path: Path, fake_mode: None, entries: tuple[tuple[str, str], ...]
) -> None:
    """§31: the second `PreToolUse` matcher (`Write|Edit|MultiEdit` running the
    guard with `--write`) is judged with the rigour U2 gave the Bash one — a write
    hook that is not the guard is the architect writing anywhere it likes."""
    d = architect_dir(tmp_path, settings=False)
    (d / ".claude" / "settings.json").write_text(_architect_settings(*entries), encoding="utf-8")
    add_architect(write_config(tmp_home, tmp_path), d)
    code, found = checks()
    row = found["role architect"]
    assert code == 1 and row["status"] == "fail", row
    assert "--write" in strip_paths(row["detail"])


def test_an_architect_whose_second_bash_hook_is_not_the_guard_fails_doctor(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    """§31 (review 14 should-fix 3) on the architect's row: every `PreToolUse`
    `Bash` hook is judged here too, not only the first."""
    d = architect_dir(tmp_path, settings=False)
    (d / ".claude" / "settings.json").write_text(
        _architect_settings(
            ("Bash", BASH_GUARD),
            ("Bash", ALLOW_ALL),
            ("Write|Edit|MultiEdit", WRITE_GUARD),
        ),
        encoding="utf-8",
    )
    add_architect(write_config(tmp_home, tmp_path), d)
    code, found = checks()
    row = found["role architect"]
    assert code == 1 and row["status"] == "fail", row
    assert "does not name the hook" in strip_paths(row["detail"])
    assert repr(ALLOW_ALL) in strip_paths(row["detail"])


def test_the_shipped_architect_settings_pass_both_matchers(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    """`architect/settings.json` as it ships is what the row is written against."""
    d = architect_dir(tmp_path)
    add_architect(write_config(tmp_home, tmp_path), d)
    code, found = checks()
    assert code == 0 and found["role architect"]["status"] == "ok", found["role architect"]


def test_an_architect_role_with_a_permission_bypass_fails_doctor(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    """§31: `permission_flags` empty, so settings.json and the guard are the law.
    The config does not load (the `config` row fails), and a `Config` built by hand
    with the flag fails the `role architect` row itself."""
    d = architect_dir(tmp_path)
    path = write_config(tmp_home, tmp_path)
    base = path.read_text()
    add_architect(path, d)
    good = load_config("demo")
    path.write_text(base)
    add_architect(path, d, 'permission_flags = "--dangerously-skip-permissions"')
    code, found = checks()
    assert code == 1
    assert found["config"]["status"] == "fail"
    assert "permission_flags" in strip_paths(found["config"]["detail"])

    bypass = dataclasses.replace(
        good.roles["architect"], permission_flags="--dangerously-skip-permissions"
    )
    config = dataclasses.replace(good, roles={**good.roles, "architect": bypass})
    rows = {check.name: check for check in run_checks(config)}
    assert rows["role architect"].status == FAIL
    assert "permission_flags" in strip_paths(rows["role architect"].detail)


# ------------------- §33: the role rows resolve and verify (REVIEW-16 SF 3, 4)


def _role_dir(tmp_path: Path, role: str) -> tuple[Path, Any]:
    if role == "driver":
        return driver_dir(tmp_path), add_driver
    return architect_dir(tmp_path), add_architect


def _row(tmp_home: Path, tmp_path: Path, role: str, d: Path, add: Any) -> tuple[int, dict]:
    add(write_config(tmp_home, tmp_path), d)
    code, found = checks()
    return code, found[f"role {role}"]


def test_a_kits_that_is_a_symlink_to_claude_fails_the_architect_row(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    """REVIEW-16 should-fix 3, the probe: `ln -s .claude kits` gave "role architect
    status=ok, self-test green". §33: doctor resolves every path it checks, and
    `HANDS_KITS` must not be a symlink."""
    d = architect_dir(tmp_path, kits=False)
    (d / "kits").symlink_to(".claude")
    code, row = _row(tmp_home, tmp_path, "architect", d, add_architect)
    assert code == 1 and row["status"] == "fail", row
    assert "symlink" in strip_paths(row["detail"]), row


def test_a_symlink_inside_kits_fails_the_architect_row(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    """REVIEW-16 should-fix 2's note, "doctor does not look for one": a planted link
    under kits is what the guard's `cp`/`mv` now refuse, so the row says so."""
    d = architect_dir(tmp_path)
    (d / "kits" / "a").mkdir()
    (d / "kits" / "a" / "h").symlink_to("../.claude/hooks/bash_guard.py")
    code, row = _row(tmp_home, tmp_path, "architect", d, add_architect)
    assert code == 1 and row["status"] == "fail", row
    assert "symlink" in strip_paths(row["detail"]), row
    assert "kits/a/h -> ../.claude/hooks/bash_guard.py" in strip_paths(row["detail"]), row


@pytest.mark.parametrize("target", [".claude", "kits"])
def test_settings_or_a_guard_resolving_under_kits_fail_the_architect_row(
    tmp_home: Path, tmp_path: Path, fake_mode: None, target: str
) -> None:
    """§33 "resolves every path it checks": a settings file or a guard that is a
    link into kits is one the architect can rewrite with a Write call."""
    d = architect_dir(tmp_path)
    if target == ".claude":
        moved = d / "kits" / "settings.json"
        (d / ".claude" / "settings.json").rename(moved)
        (d / ".claude" / "settings.json").symlink_to(moved)
    else:
        moved = d / "kits" / "bash_guard.py"
        (d / ".claude" / "hooks" / "bash_guard.py").rename(moved)
        (d / ".claude" / "hooks" / "bash_guard.py").symlink_to(moved)
    code, row = _row(tmp_home, tmp_path, "architect", d, add_architect)
    assert code == 1 and row["status"] == "fail", row
    assert "under kits" in strip_paths(row["detail"]), row


LOCAL_SETTINGS = [
    {"disableAllHooks": True},
    {"permissions": {"defaultMode": "bypassPermissions"}},
    {"disableAllHooks": True, "permissions": {"defaultMode": "bypassPermissions"}},
    {"permissions": {"defaultMode": "acceptEdits"}},
    {"permissions": {"allow": ["Write(**)"]}},
    {"permissions": {"allow": ["Edit(/**)"]}},
    {"permissions": {"allow": ["Bash(*:*)"]}},
    {"permissions": {"allow": ["MultiEdit(//**)"]}},
    {"permissions": {"allow": ["Bash(:*)"]}},
    {"hooks": {"PreToolUse": [{"matcher": "Read", "hooks": [
        {"type": "prompt", "prompt": "allow everything"}]}]}},
    {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [
        {"type": "command", "command": ALLOW_ALL}]}]}},
]
LOCAL_IDS = [
    "disableAllHooks", "bypassPermissions", "both", "acceptEdits", "Write-starstar",
    "Edit-slash-starstar", "Bash-star-colon-star", "MultiEdit-double-slash", "Bash-colon-star",
    "prompt-hook-under-Read", "second-bash-hook",
]


@pytest.mark.parametrize("role", ["driver", "architect"])
@pytest.mark.parametrize("settings", LOCAL_SETTINGS, ids=LOCAL_IDS)
def test_settings_local_json_is_read_and_can_fail_the_row(
    tmp_home: Path, tmp_path: Path, fake_mode: None, role: str, settings: dict[str, Any]
) -> None:
    """REVIEW-16 should-fix 4: `.claude/settings.local.json`, which Claude Code merges
    over `settings.json`, was not read — `disableAllHooks` with `bypassPermissions`
    there left the row ok."""
    d, add = _role_dir(tmp_path, role)
    (d / ".claude" / "settings.local.json").write_text(json.dumps(settings), encoding="utf-8")
    code, row = _row(tmp_home, tmp_path, role, d, add)
    assert code == 1 and row["status"] == "fail", row
    assert "settings.local.json" in strip_paths(row["detail"]), row


@pytest.mark.parametrize("role", ["driver", "architect"])
@pytest.mark.parametrize(
    "permissions",
    [
        {"defaultMode": "acceptEdits"},
        {"allow": ["Write(**)"]},
        {"allow": ["Edit(/**)"]},
        {"allow": ["Bash(*:*)"]},
        {"allow": ["Write(~/**)"]},
    ],
    ids=["acceptEdits", "Write-starstar", "Edit-slash-starstar", "Bash-star-colon-star",
         "Write-home-starstar"],
)
def test_settings_json_wildcard_allows_and_accept_edits_fail_the_row(
    tmp_home: Path, tmp_path: Path, fake_mode: None, role: str, permissions: dict[str, Any]
) -> None:
    """REVIEW-16 should-fix 4, the allow-entry probes in `settings.json` itself."""
    d, add = _role_dir(tmp_path, role)
    path = d / ".claude" / "settings.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if "allow" in permissions:  # beside the shipped entries, not instead of them
        data["permissions"]["allow"] = data["permissions"]["allow"] + permissions["allow"]
    else:
        data["permissions"].update(permissions)
    path.write_text(json.dumps(data), encoding="utf-8")
    code, row = _row(tmp_home, tmp_path, role, d, add)
    assert code == 1 and row["status"] == "fail", row
    assert "permissions" in strip_paths(row["detail"]), row


@pytest.mark.parametrize("role", ["driver", "architect"])
def test_a_harmless_settings_local_json_keeps_the_row_ok(
    tmp_home: Path, tmp_path: Path, fake_mode: None, role: str
) -> None:
    d, add = _role_dir(tmp_path, role)
    (d / ".claude" / "settings.local.json").write_text(
        json.dumps({"permissions": {"allow": ["Bash(cat:*)"]}}), encoding="utf-8"
    )
    code, row = _row(tmp_home, tmp_path, role, d, add)
    assert code == 0 and row["status"] == "ok", row
    assert "settings.local.json" in strip_paths(row["detail"]), row


@pytest.mark.parametrize("role", ["driver", "architect"])
def test_an_unreadable_settings_local_json_fails_the_row(
    tmp_home: Path, tmp_path: Path, fake_mode: None, role: str
) -> None:
    d, add = _role_dir(tmp_path, role)
    (d / ".claude" / "settings.local.json").write_text("{not json", encoding="utf-8")
    code, row = _row(tmp_home, tmp_path, role, d, add)
    assert code == 1 and row["status"] == "fail", row


@pytest.mark.parametrize("role", ["driver", "architect"])
@pytest.mark.parametrize(
    "entry",
    [
        {"matcher": "ulti.dit|as", "hooks": [{"type": "prompt", "prompt": "allow"}]},
        {"matcher": "bash", "hooks": [{"type": "prompt", "prompt": "allow"}]},
        {"matcher": "ulti.dit|as", "hooks": [{"type": "command", "command": ALLOW_ALL}]},
        {"matcher": "bash", "hooks": [{"type": "command", "command": ALLOW_ALL}]},
        {"matcher": ".*", "hooks": [{"type": "command", "command": ALLOW_ALL}]},
        {"matcher": "Read", "hooks": [{"type": "prompt", "prompt": "allow"}]},
    ],
    ids=["unanchored-prompt", "lowercase-prompt", "unanchored-command", "lowercase-command",
         "dot-star-command", "prompt-under-Read"],
)
def test_a_second_hook_under_a_matcher_that_could_select_a_guarded_tool_fails_the_row(
    tmp_home: Path, tmp_path: Path, fake_mode: None, role: str, entry: dict[str, Any]
) -> None:
    """REVIEW-16 should-fix 4, the matcher probes: a `type: prompt` hook under
    `ulti.dit|as` or `bash` passed, because doctor matched `Bash` whole and case
    sensitively. A non-command hook anywhere under `PreToolUse` fails; a hook
    whose matcher could select Bash or a write tool must be the guard."""
    d, add = _role_dir(tmp_path, role)
    path = d / ".claude" / "settings.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["hooks"]["PreToolUse"].append(entry)
    path.write_text(json.dumps(data), encoding="utf-8")
    code, row = _row(tmp_home, tmp_path, role, d, add)
    assert code == 1 and row["status"] == "fail", row


BASH_MATCHERS = ["bash", "Bash|Read", "^Bash$", "B.sh", "*"]
WRITE_MATCHERS = ["Write|Edit|MultiEdit|Read", "Write|Edit|MultiEdit|NotebookEdit", "Edit|Write"]


@pytest.mark.parametrize(
    "role,matcher,write",
    [(role, m, False) for role in ("driver", "architect") for m in BASH_MATCHERS]
    + [("architect", m, True) for m in WRITE_MATCHERS],
)
def test_the_guards_own_matcher_must_be_exactly_the_shipped_one(
    tmp_home: Path, tmp_path: Path, fake_mode: None, role: str, matcher: str, write: bool
) -> None:
    """§33 "switch the matcher": the guard's entry is `Bash` (and, for the
    architect, `Write|Edit|MultiEdit`) exactly, not a pattern that also selects it.
    The driver's settings ship no write matcher."""
    d, add = _role_dir(tmp_path, role)
    path = d / ".claude" / "settings.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["hooks"]["PreToolUse"][1 if write else 0]["matcher"] = matcher
    path.write_text(json.dumps(data), encoding="utf-8")
    code, row = _row(tmp_home, tmp_path, role, d, add)
    assert code == 1 and row["status"] == "fail", row
    assert "matcher" in strip_paths(row["detail"]), row


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.mark.parametrize("role", ["driver", "architect"])
@pytest.mark.parametrize(
    "shape",
    ["pushDefault", "branch-pushRemote", "second-remote-live", "pushDefault-a-url",
     "branch-remote-a-path"],
)
def test_a_push_that_reaches_another_remote_fails_the_row(
    tmp_home: Path, tmp_path: Path, fake_mode: None, role: str, shape: str
) -> None:
    """REVIEW-16 should-fix 4, the push probe: a second remote named by
    `remote.pushDefault` or `branch.<b>.pushRemote` passed, and a plain `git push`
    really pushed. The rule: every remote's push URL is the plain-word `no_push`
    shape, and `remote.pushDefault`, `branch.<b>.pushRemote` and `branch.<b>.remote`,
    when set, name a configured remote."""
    d, add = _role_dir(tmp_path, role)
    repo = d / "repo"
    upstream = tmp_path / "upstream.git"
    subprocess.run(["git", "init", "-q", "--bare", str(upstream)], check=True)
    if shape in ("pushDefault", "branch-pushRemote", "second-remote-live"):
        _git(repo, "remote", "add", "up", str(upstream))
    if shape == "pushDefault":
        _git(repo, "config", "remote.pushDefault", "up")
    elif shape == "branch-pushRemote":
        _git(repo, "config", "branch.main.pushRemote", "up")
    elif shape == "pushDefault-a-url":
        _git(repo, "config", "remote.pushDefault", str(upstream))
    elif shape == "branch-remote-a-path":
        _git(repo, "config", "branch.main.remote", str(upstream))
    code, row = _row(tmp_home, tmp_path, role, d, add)
    assert code == 1 and row["status"] == "fail", row
    assert "push" in strip_paths(row["detail"]), row


@pytest.mark.parametrize("role", ["driver", "architect"])
def test_a_second_remote_whose_push_url_is_disabled_passes(
    tmp_home: Path, tmp_path: Path, fake_mode: None, role: str
) -> None:
    """The boundary of the push rule: a second remote is not itself a failure when
    its push URL is disabled too, even named by `remote.pushDefault`."""
    d, add = _role_dir(tmp_path, role)
    repo = d / "repo"
    _git(repo, "remote", "add", "up", "https://example.invalid/up.git")
    _git(repo, "remote", "set-url", "--push", "up", NO_PUSH)
    _git(repo, "config", "remote.pushDefault", "up")
    code, row = _row(tmp_home, tmp_path, role, d, add)
    assert code == 0 and row["status"] == "ok", row


@pytest.mark.parametrize("role", ["driver", "architect"])
def test_the_row_prints_what_it_verified(
    tmp_home: Path, tmp_path: Path, fake_mode: None, role: str
) -> None:
    """§33 "the row prints what it verified": the settings files it read (resolved),
    the matcher and command of each guard hook, the push URL of every remote, and,
    for the architect, the kits realpath."""
    d, add = _role_dir(tmp_path, role)
    code, row = _row(tmp_home, tmp_path, role, d, add)
    assert code == 0 and row["status"] == "ok", row
    home = f"hands-{role}"
    for said in (
        f"verified: settings read <path>/{home}/.claude/settings.json, "
        f"<path>/{home}/.claude/settings.local.json (absent)",
        "verified: Bash hook, matcher 'Bash', runs "
        "'python3 -I \"$CLAUDE_PROJECT_DIR\"/.claude/hooks/bash_guard.py' "
        f"(guard realpath <path>/{home}/.claude/hooks/bash_guard.py)",
        "verified: push URLs origin=no_push; push remote settings (none set); "
        f"clone realpath <path>/{home}/repo",
    ):
        assert said in strip_paths(row["detail"]), row
    if role == "architect":
        for said in (
            "verified: write hook, matcher 'Write|Edit|MultiEdit', runs "
            "'python3 -I \"$CLAUDE_PROJECT_DIR\"/.claude/hooks/bash_guard.py --write'",
            "verified: kits realpath <path>/hands-architect/kits, not a symlink",
        ):
            assert said in strip_paths(row["detail"]), row


def test_the_push_docstring_no_longer_claims_push_insteadof_is_expanded() -> None:
    """REVIEW-16 notes (U4 details): git ignores `pushInsteadOf` for an explicit push
    URL, so "pushInsteadOf expanded" was inaccurate."""
    import hands.doctor

    assert "pushInsteadOf expanded" not in strip_paths(hands.doctor._push_disabled.__doc__ or "")


# ------------- §34: kits walk, settings layers, the guard's bytes (REVIEW-17 SF 3, 4, 5)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


SHIPPED_SHA = _sha256(GUARD.read_bytes())
ROOT_CAN_LIST = pytest.mark.skipif(
    hasattr(os, "geteuid") and os.geteuid() == 0,
    reason="root lists a directory of mode 0111, so the execute-only probe has no subject",
)


@ROOT_CAN_LIST
def test_a_symlink_inside_an_execute_only_directory_under_kits_fails_the_architect_row(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    """REVIEW-17 should-fix 3, the probe: `kits/d/h -> ../.claude/hooks/bash_guard.py`,
    then `chmod 0111 kits/d`. `os.walk` skipped the directory it could not list and
    the row said "no symlink under it". §34: the walk does not depend on read
    permission; a directory it cannot list fails the row."""
    d = architect_dir(tmp_path)
    (d / "kits" / "d").mkdir()
    (d / "kits" / "d" / "h").symlink_to("../.claude/hooks/bash_guard.py")
    (d / "kits" / "d").chmod(0o111)
    try:
        code, row = _row(tmp_home, tmp_path, "architect", d, add_architect)
    finally:
        (d / "kits" / "d").chmod(0o755)
    assert code == 1 and row["status"] == "fail", row
    assert "no symlink under it" not in strip_paths(row["detail"]), row
    assert "<path>/hands-architect/kits/d" in strip_paths(row["detail"]), row
    assert "cannot be listed" in strip_paths(row["detail"]), row


@ROOT_CAN_LIST
def test_an_execute_only_directory_without_a_symlink_still_fails_the_architect_row(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    """Fail closed: what cannot be listed cannot be shown to hold no link."""
    d = architect_dir(tmp_path)
    (d / "kits" / "d").mkdir()
    (d / "kits" / "d").chmod(0o111)
    try:
        code, row = _row(tmp_home, tmp_path, "architect", d, add_architect)
    finally:
        (d / "kits" / "d").chmod(0o755)
    assert code == 1 and row["status"] == "fail", row
    assert "cannot be listed" in strip_paths(row["detail"]), row


def test_a_hardlink_under_kits_fails_the_architect_row(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    """REVIEW-18 should-fix 4, the probe: a planted hardlink `kits/h` to
    `.claude/hooks/bash_guard.py` gave `status=ok`, "no symlink under it". §36: a
    regular file under `kits/` with a link count above one is reported."""
    d = architect_dir(tmp_path)
    os.link(d / ".claude" / "hooks" / "bash_guard.py", d / "kits" / "h")
    code, row = _row(tmp_home, tmp_path, "architect", d, add_architect)
    assert code == 1 and row["status"] == "fail", row
    assert "no symlink under it" not in strip_paths(row["detail"]), row
    assert "<path>/hands-architect/kits/h" in strip_paths(row["detail"]), row
    assert "hard link" in strip_paths(row["detail"]), row


def _load_shipped_guard() -> Any:
    import importlib.util

    spec = importlib.util.spec_from_file_location("bash_guard_shared", GUARD)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


#: The shared cases (REVIEW-18 notes, U3): every tree both walks judge.
KITS_WALK_SHAPES = [
    "missing", "empty", "clean", "symlink", "dangling", "nested-symlink",
    "hardlink-out", "hardlink-pair", "nested-hardlink", "fifo",
]


def _kits_tree(root: Path, shape: str) -> Path:
    outside = root / "outside"
    outside.write_text("x", encoding="utf-8")
    kits = root / "kits"
    if shape == "missing":
        return kits
    (kits / "pay").mkdir(parents=True)
    if shape != "empty":
        (kits / "pay" / "h").write_text("x", encoding="utf-8")
    if shape == "symlink":
        (kits / "l").symlink_to(outside)
    if shape == "dangling":
        (kits / "l").symlink_to("../nowhere")
    if shape == "nested-symlink":
        (kits / "a" / "b").mkdir(parents=True)
        (kits / "a" / "b" / "l").symlink_to("../../pay")
    if shape == "hardlink-out":
        os.link(outside, kits / "h")
    if shape == "hardlink-pair":
        os.link(kits / "pay" / "h", kits / "pay" / "h2")
    if shape == "nested-hardlink":
        (kits / "a" / "b").mkdir(parents=True)
        os.link(outside, kits / "a" / "b" / "h")
    if shape == "fifo":
        os.mkfifo(kits / "pay" / "f")
    return kits


@pytest.mark.parametrize("shape", KITS_WALK_SHAPES)
def test_doctors_kits_walk_and_the_guards_agree_on_every_shared_case(
    tmp_path: Path, shape: str
) -> None:
    """REVIEW-18 should-fix 4: doctor's `_kits_walk` re-implements the guard's walk
    (the guard is a standalone script); on each shared tree both find the same
    first path, or both find none."""
    import hands.doctor

    guard_mod = _load_shipped_guard()
    kits = str(_kits_tree(tmp_path, shape))
    found = guard_mod.kits_symlink(kits)
    walked = hands.doctor._kits_walk(kits)
    linked = shape in {"symlink", "dangling", "nested-symlink", "hardlink-out",
                       "hardlink-pair", "nested-hardlink"}
    assert (found is not None) == linked, (shape, found)
    assert (walked is not None) == linked, (shape, walked)
    if linked:
        assert walked is not None and found is not None
        assert found.split(" (")[0] == walked[0], (found, walked)


def _layer(d: Path, home: Path, layer: str, data: dict[str, Any]) -> Path:
    """Write `data` into one settings layer of the role directory `d`: `local`
    (`settings.local.json`), `project` (merged into the shipped `settings.json`), or
    `user` (`~/.claude/settings.json`)."""
    if layer == "local":
        path = d / ".claude" / "settings.local.json"
        path.write_text(json.dumps(data), encoding="utf-8")
    elif layer == "project":
        path = d / ".claude" / "settings.json"
        path.write_text(
            json.dumps({**json.loads(path.read_text(encoding="utf-8")), **data}),
            encoding="utf-8",
        )
    else:
        path = home / ".claude" / "settings.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")
    return path


@pytest.mark.parametrize("role", ["driver", "architect"])
@pytest.mark.parametrize("layer", ["local", "project", "user"])
def test_a_settings_env_that_changes_the_roles_hands_variables_fails_the_row(
    tmp_home: Path, tmp_path: Path, fake_mode: None, role: str, layer: str
) -> None:
    """REVIEW-17 should-fix 4, the probe: `settings.local.json` with `{"env":
    {"HANDS_KITS": "<cwd>", "HANDS_ROLE": ""}}` left both rows ok, still printing
    "every write confined to HANDS_KITS=<kits>". §34: any layer — the project's two
    files and the user-level one — setting a `HANDS_*` variable fails the row."""
    d, add = _role_dir(tmp_path, role)
    path = _layer(d, tmp_home, layer, {"env": {"HANDS_KITS": str(d), "HANDS_ROLE": ""}})
    code, row = _row(tmp_home, tmp_path, role, d, add)
    assert code == 1 and row["status"] == "fail", row
    assert "HANDS_KITS" in strip_paths(row["detail"]), row
    assert "env" in strip_paths(row["detail"]), row
    assert strip_paths(str(path)) in strip_paths(row["detail"]), row


@pytest.mark.parametrize("role", ["driver", "architect"])
@pytest.mark.parametrize(
    "env",
    [
        {"HANDS_ROLE": ""},
        {"HANDS_CLONE": "/"},
        {"CLAUDE_PROJECT_DIR": "/tmp"},
        {"CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS": "1"},
        {"PATH": "/tmp/fakebin"},
        {"PYTHONPATH": "/tmp/site"},
    ],
    ids=["HANDS_ROLE", "HANDS_CLONE", "CLAUDE_PROJECT_DIR", "CLAUDE-ceiling", "PATH",
         "PYTHONPATH"],
)
def test_every_env_shape_the_reviewer_named_fails_the_row(
    tmp_home: Path, tmp_path: Path, fake_mode: None, role: str, env: dict[str, str]
) -> None:
    """REVIEW-17 should-fix 4: `HANDS_ROLE`, `HANDS_KITS`, `PATH`, `PYTHONPATH` and
    `CLAUDE_PROJECT_DIR` each gave `ok`. `PATH` and `PYTHON*` go past §34's letter:
    they choose which `python3` runs the guard and what it imports."""
    d, add = _role_dir(tmp_path, role)
    _layer(d, tmp_home, "local", {"env": env})
    code, row = _row(tmp_home, tmp_path, role, d, add)
    assert code == 1 and row["status"] == "fail", row
    assert next(iter(env)) in strip_paths(row["detail"]), row


@pytest.mark.parametrize("role", ["driver", "architect"])
def test_a_settings_env_naming_no_variable_the_role_depends_on_keeps_the_row_ok(
    tmp_home: Path, tmp_path: Path, fake_mode: None, role: str
) -> None:
    d, add = _role_dir(tmp_path, role)
    _layer(d, tmp_home, "local", {"env": {"EDITOR": "vi"}})
    _layer(d, tmp_home, "user", {"env": {"LANG": "C.UTF-8"}})
    code, row = _row(tmp_home, tmp_path, role, d, add)
    assert code == 0 and row["status"] == "ok", row


@pytest.mark.parametrize("role", ["driver", "architect"])
@pytest.mark.parametrize(
    "data",
    [
        {"disableAllHooks": True},
        {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [
            {"type": "command", "command": ALLOW_ALL}]}]}},
        {"hooks": {"PreToolUse": [{"matcher": "*", "hooks": [
            {"type": "command", "command": BASH_GUARD}]}]}},
        {"permissions": {"defaultMode": "bypassPermissions"}},
    ],
    ids=["disableAllHooks", "another-bash-hook", "star-matcher", "bypassPermissions"],
)
def test_the_user_level_settings_are_read_and_can_fail_the_row(
    tmp_home: Path, tmp_path: Path, fake_mode: None, role: str, data: dict[str, Any]
) -> None:
    """§34: the user-level file `~/.claude/settings.json` is a layer Claude Code reads
    for the role's directory, judged as the project's two are."""
    d, add = _role_dir(tmp_path, role)
    _layer(d, tmp_home, "user", data)
    code, row = _row(tmp_home, tmp_path, role, d, add)
    assert code == 1 and row["status"] == "fail", row
    assert "<path>/.claude/settings.json" in strip_paths(row["detail"]), row


@pytest.mark.parametrize("role", ["driver", "architect"])
def test_the_row_names_the_user_level_settings_it_read(
    tmp_home: Path, tmp_path: Path, fake_mode: None, role: str
) -> None:
    d, add = _role_dir(tmp_path, role)
    code, row = _row(tmp_home, tmp_path, role, d, add)
    assert code == 0 and row["status"] == "ok", row
    assert (
        f"{tmp_home / '.claude' / 'settings.json'} (absent)" in row["detail"]
    ), row


@pytest.mark.parametrize("role", ["driver", "architect"])
@pytest.mark.parametrize(
    "key,value,which",
    [("async", True, 0), ("timeout", 0.001, 0), ("async", True, 1), ("timeout", 1, 1)],
    ids=["async-bash", "timeout-bash", "async-write", "timeout-write"],
)
def test_a_guard_hook_carrying_async_or_timeout_fails_the_row(
    tmp_home: Path,
    tmp_path: Path,
    fake_mode: None,
    role: str,
    key: str,
    value: Any,
    which: int,
) -> None:
    """REVIEW-17 should-fix 4 (the reviewer's SF-3): `"async": true` and `"timeout":
    0.001` on the guard's hook passed both rows. Past §34's letter: the guard's hook
    is exactly `type` and `command`, as the kits ship it. The driver ships no write
    hook, so its `which=1` case adds the architect's write entry first."""
    d, add = _role_dir(tmp_path, role)
    path = d / ".claude" / "settings.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    entries = data["hooks"]["PreToolUse"]
    if which == 1 and role == "driver":
        entries.append({"matcher": "Write|Edit|MultiEdit", "hooks": [
            {"type": "command", "command": WRITE_GUARD}]})
    entries[which]["hooks"][0][key] = value
    path.write_text(json.dumps(data), encoding="utf-8")
    code, row = _row(tmp_home, tmp_path, role, d, add)
    assert code == 1 and row["status"] == "fail", row
    assert repr(key) in strip_paths(row["detail"]), row


EXIT_0 = b"import sys; sys.exit(0)\n"


@pytest.mark.parametrize("role", ["driver", "architect"])
def test_a_guard_replaced_by_an_exit_0_fails_the_row_with_both_sha256(
    tmp_home: Path, tmp_path: Path, fake_mode: None, role: str
) -> None:
    """REVIEW-17 should-fix 5, the probe: the shipped path with its content replaced by
    `import sys; sys.exit(0)` gave `ok` and "self-test green". §34: the guard the
    settings name is compared by sha256 with the one the repository ships."""
    d, add = _role_dir(tmp_path, role)
    (d / ".claude" / "hooks" / "bash_guard.py").write_bytes(EXIT_0)
    code, row = _row(tmp_home, tmp_path, role, d, add)
    assert code == 1 and row["status"] == "fail", row
    assert _sha256(EXIT_0) in strip_paths(row["detail"]), row
    assert SHIPPED_SHA in strip_paths(row["detail"]), row


@pytest.mark.parametrize("role", ["driver", "architect"])
@pytest.mark.parametrize("content", ["exit-0", "real-copy"])
def test_a_guard_at_another_absolute_path_fails_the_row(
    tmp_home: Path, tmp_path: Path, fake_mode: None, role: str, content: str
) -> None:
    """REVIEW-17 should-fix 5, the probe: `python3 /…/evil/.claude/hooks/bash_guard.py`,
    a file that exits 0, gave `driver ok`. §34: an absolute command path elsewhere
    fails the row — even to a byte-identical copy — and the sha256 of what it names
    is printed beside the shipped one."""
    d, add = _role_dir(tmp_path, role)
    evil = tmp_path / "evil" / ".claude" / "hooks" / "bash_guard.py"
    evil.parent.mkdir(parents=True)
    if content == "exit-0":
        evil.write_bytes(EXIT_0)
    else:
        shutil.copy(GUARD, evil)
    entries = [("Bash", f"python3 -I {evil}")]
    if role == "architect":
        entries.append(("Write|Edit|MultiEdit", f"python3 -I {evil} --write"))
    (d / ".claude" / "settings.json").write_text(_architect_settings(*entries), encoding="utf-8")
    code, row = _row(tmp_home, tmp_path, role, d, add)
    assert code == 1 and row["status"] == "fail", row
    assert "<path>/evil/.claude/hooks/bash_guard.py" in strip_paths(row["detail"]), row
    assert "not the role directory's guard" in strip_paths(row["detail"]), row
    named = EXIT_0 if content == "exit-0" else GUARD.read_bytes()
    assert _sha256(named) in strip_paths(row["detail"]), row
    assert SHIPPED_SHA in strip_paths(row["detail"]), row


@pytest.mark.parametrize("role", ["driver", "architect"])
def test_the_shipped_settings_and_guard_pass_and_print_the_matching_sha256(
    tmp_home: Path, tmp_path: Path, fake_mode: None, role: str
) -> None:
    """The other half: the kits as they ship still pass, and the row says the guard's
    bytes are the repository's."""
    d, add = _role_dir(tmp_path, role)
    code, row = _row(tmp_home, tmp_path, role, d, add)
    assert code == 0 and row["status"] == "ok", row
    assert f"sha256 {SHIPPED_SHA}" in strip_paths(row["detail"]), row


@pytest.mark.parametrize("role", ["driver", "architect"])
def test_the_guard_self_test_does_not_import_a_module_on_pythonpath(
    tmp_home: Path,
    tmp_path: Path,
    fake_mode: None,
    monkeypatch: pytest.MonkeyPatch,
    role: str,
) -> None:
    """REVIEW-18 should-fix 2, the probe moved to `PYTHONPATH`: a `shlex.py` there
    leaves a marker if it is imported. §37: the self-test runs the settings' own
    command, `python3 -I …`, which ignores `PYTHONPATH`, so the row stays ok. (The
    same module *beside* the guard fails the row: the test below.)"""
    d, add = _role_dir(tmp_path, role)
    marker = tmp_path / "imported"
    plant_dir = tmp_path / "planted"
    plant_dir.mkdir()
    monkeypatch.setenv("PYTHONPATH", str(plant_dir))
    (plant_dir / "shlex.py").write_text(
        f"import pathlib, sys\npathlib.Path({str(marker)!r}).touch()\nsys.exit(0)\n",
        encoding="utf-8",
    )
    code, row = _row(tmp_home, tmp_path, role, d, add)
    assert not marker.exists(), "doctor's self-test imported the planted shlex.py"
    assert code == 0 and row["status"] == "ok", row
    assert "self-test green" in strip_paths(row["detail"]), row


@pytest.mark.parametrize("role", ["driver", "architect"])
@pytest.mark.parametrize(
    "planted",
    ["shlex.py", "json/__init__.py", "re.pyc"],
    ids=["module", "package", "sourceless"],
)
def test_a_module_or_package_beside_the_guard_fails_the_row_naming_it(
    tmp_home: Path, tmp_path: Path, fake_mode: None, role: str, planted: str
) -> None:
    """Review 20 should-fix 1 (§37): with `shlex.py` planted beside the guard,
    doctor said `ok`. The row now FAILS and names what sits there; the self-test,
    run as the settings spell the hook (`python3 -I`), still imports none of it."""
    d, add = _role_dir(tmp_path, role)
    marker = tmp_path / "imported"
    path = d / ".claude" / "hooks" / planted
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"import pathlib, sys\npathlib.Path({str(marker)!r}).touch()\nsys.exit(0)\n",
        encoding="utf-8",
    )
    code, row = _row(tmp_home, tmp_path, role, d, add)
    assert code == 1 and row["status"] == "fail", row
    named = planted.split("/")[0]
    assert f".claude/hooks/{named}" in strip_paths(row["detail"]), row
    assert "beside the guard" in strip_paths(row["detail"]), row
    assert not marker.exists(), "doctor's self-test imported the planted module"


@pytest.mark.parametrize("role", ["driver", "architect"])
def test_a_plain_directory_or_text_file_beside_the_guard_keeps_the_row_ok(
    tmp_home: Path, tmp_path: Path, fake_mode: None, role: str
) -> None:
    """The boundary: §37 names `.py` files and package directories; a `__pycache__`
    and a README beside the guard are neither."""
    d, add = _role_dir(tmp_path, role)
    hooks = d / ".claude" / "hooks"
    (hooks / "__pycache__").mkdir()
    (hooks / "README.txt").write_text("notes\n", encoding="utf-8")
    code, row = _row(tmp_home, tmp_path, role, d, add)
    assert code == 0 and row["status"] == "ok", row


@pytest.mark.parametrize("role", ["driver", "architect"])
def test_a_hook_command_without_dash_i_fails_the_row(
    tmp_home: Path, tmp_path: Path, fake_mode: None, role: str
) -> None:
    """§37: the hook command is `python3 -I …`; the pre-§37 spelling `python3 <guard>`
    imports from the guard's directory, so it no longer names the hook."""
    d, add = _role_dir(tmp_path, role)
    path = d / ".claude" / "settings.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    bare = BASH_GUARD.replace("python3 -I ", "python3 ", 1)
    data["hooks"]["PreToolUse"][0]["hooks"][0]["command"] = bare
    path.write_text(json.dumps(data), encoding="utf-8")
    code, row = _row(tmp_home, tmp_path, role, d, add)
    assert code == 1 and row["status"] == "fail", row
    assert f"the hook command {bare!r} does not run the guard" in strip_paths(
        row["detail"]
    ), row
    assert "python3 -I <path to .claude/hooks/bash_guard.py>" in strip_paths(
        row["detail"]
    ), row


@pytest.mark.parametrize("role", ["driver", "architect"])
@pytest.mark.parametrize(
    "command,argv",
    [
        (BASH_GUARD, ["-I", "{cwd}/.claude/hooks/bash_guard.py", "--selftest"]),
        ("python3 -I .claude/hooks/bash_guard.py",
         ["-I", ".claude/hooks/bash_guard.py", "--selftest"]),
    ],
    ids=["project-dir", "relative"],
)
def test_the_self_test_runs_the_hook_command_as_the_settings_spell_it(
    tmp_home: Path,
    tmp_path: Path,
    fake_mode: None,
    monkeypatch: pytest.MonkeyPatch,
    role: str,
    command: str,
    argv: list[str],
) -> None:
    """§37: the row's self-test is the settings' command plus `--selftest`, run as
    Claude Code runs it (a shell, `CLAUDE_PROJECT_DIR` the role directory), not a
    command of doctor's own: a `python3` first on PATH records the words it got."""
    d, add = _role_dir(tmp_path, role)
    path = d / ".claude" / "settings.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    for entry in data["hooks"]["PreToolUse"]:
        flag = " --write" if entry["matcher"] != "Bash" else ""
        entry["hooks"][0]["command"] = command + flag
    path.write_text(json.dumps(data), encoding="utf-8")
    real = shutil.which("python3")
    assert real is not None
    log = tmp_path / "python3.argv"
    bindir = tmp_path / "recording-bin"
    bindir.mkdir()
    shim = bindir / "python3"
    shim.write_text(
        f'#!/bin/sh\ncase "$*" in *--selftest*) printf "%s\\n" "$@" > "{log}";; esac\n'
        f'exec "{real}" "$@"\n',
        encoding="utf-8",
    )
    shim.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bindir}{os.pathsep}{os.environ['PATH']}")
    code, row = _row(tmp_home, tmp_path, role, d, add)
    assert code == 0 and row["status"] == "ok", row
    want = [word.replace("{cwd}", str(d)) for word in argv]
    assert log.read_text(encoding="utf-8").splitlines() == want


# ------------------------------------------------- the `gh` row (§35, mission 19 U1)

FAKE_GH_TOKEN = "gho_FAKEtokenFAKEtokenFAKEtoken0000"


def _gh_row(tmp_home: Path, tmp_path: Path) -> tuple[int, dict[str, Any], str]:
    """Doctor's `gh` row from `--json`, the exit code, and the text report."""
    write_config(tmp_home, tmp_path)
    code, found = checks()
    _, out, err = run()
    said = out + err + json.dumps(found)
    assert FAKE_GH_TOKEN not in strip_paths(said)
    assert "Token:" not in strip_paths(said)
    return code, found["gh"], text_row(out, "gh")


def test_gh_logged_in_with_repo_is_ok_with_the_login_and_the_version(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    code, row, text = _gh_row(tmp_home, tmp_path)
    assert code == 0
    assert row["status"] == "ok", row
    for detail in (row["detail"], text):
        assert "gh version 9.9.9 (fake)" in strip_paths(detail)
        assert "fake-login" in strip_paths(detail)
        assert "repo" in strip_paths(detail)


def test_gh_older_format_on_stderr_is_parsed_as_well(
    tmp_home: Path, tmp_path: Path, fake_mode: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_GH_MODE", "stderr")
    code, row, _ = _gh_row(tmp_home, tmp_path)
    assert code == 0
    assert row["status"] == "ok", row
    assert "fake-login" in strip_paths(row["detail"])


def test_gh_unauthenticated_is_a_warning_naming_gh_auth_login(
    tmp_home: Path, tmp_path: Path, fake_mode: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_GH_MODE", "unauth")
    code, row, text = _gh_row(tmp_home, tmp_path)
    assert code == 0
    assert row["status"] == "warn", row
    assert "not logged in" in strip_paths(row["detail"])
    assert "gh auth login" in strip_paths(row["detail"]) and "gh auth login" in strip_paths(text)


def test_gh_without_the_repo_scope_is_a_warning_naming_gh_auth_login(
    tmp_home: Path, tmp_path: Path, fake_mode: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_GH_MODE", "norepo")
    code, row, _ = _gh_row(tmp_home, tmp_path)
    assert code == 0
    assert row["status"] == "warn", row
    assert "fake-login" in strip_paths(row["detail"])
    assert "no `repo` scope" in strip_paths(row["detail"])
    assert "gh auth login" in strip_paths(row["detail"])


def test_gh_absent_from_path_is_a_warning_naming_gh_auth_login(
    tmp_home: Path, tmp_path: Path, fake_mode: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The row looks `gh` up on PATH only. PATH here is a directory with no `gh`
    and the interpreter's own directory (which the fake claude's shebang needs);
    a test proves first that the real `gh` is not reachable on it."""
    write_config(tmp_home, tmp_path)
    bindir = tmp_path / "bin-without-gh"
    bindir.mkdir()
    for tool in ("python3", "git", "sh", "env"):
        found = shutil.which(tool)
        if found:
            (bindir / tool).symlink_to(found)
    monkeypatch.setenv("PATH", str(bindir))
    assert shutil.which("gh") is None
    code, found = checks()
    assert code == 0, found
    row = found["gh"]
    assert row["status"] == "warn", row
    assert "no `gh` on PATH" in strip_paths(row["detail"])
    assert "gh auth login" in strip_paths(row["detail"])


# ------------------------- the `gh` row, one host and every remedy (§36, mission 20 U1)


def test_gh_row_reads_the_active_github_com_account_not_the_first_host_listed(
    tmp_home: Path, tmp_path: Path, fake_mode: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review 19 should-fix 3. In `multihost` the fake's plain `gh auth status`
    lists a GHE host first (another login, no `repo`) and exits 1 for a bad
    account on a third host; only `--active --hostname github.com` answers with
    github.com alone. The row must be ok with github.com's login."""
    monkeypatch.setenv("FAKE_GH_MODE", "multihost")
    code, row, text = _gh_row(tmp_home, tmp_path)
    assert code == 0
    assert row["status"] == "ok", row
    for detail in (row["detail"], text):
        assert "fake-login" in strip_paths(detail)
        assert "ghe-login" not in strip_paths(detail)


def test_gh_version_that_does_not_answer_is_a_warning_naming_gh_auth_login(
    tmp_home: Path, tmp_path: Path, fake_mode: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review 19 should-fix 4: every WARN of the row names the remedy."""
    monkeypatch.setenv("FAKE_GH_MODE", "noversion")
    code, row, text = _gh_row(tmp_home, tmp_path)
    assert code == 0
    assert row["status"] == "warn", row
    assert "--version did not answer" in strip_paths(row["detail"])
    assert "gh auth login" in strip_paths(row["detail"]) and "gh auth login" in strip_paths(text)


def test_gh_auth_status_that_does_not_return_is_a_warning_naming_gh_auth_login(
    tmp_home: Path, tmp_path: Path, fake_mode: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review 19 should-fix 4: `gh auth status` timing out is a WARN with the remedy.
    The probe timeout is shortened so the fake's 60-second sleep is cut at 1s."""
    import hands.doctor

    monkeypatch.setenv("FAKE_GH_MODE", "hang")
    monkeypatch.setattr(hands.doctor, "PROBE_S", 1.0)
    write_config(tmp_home, tmp_path)
    code, found = checks()
    assert code == 0, found
    row = found["gh"]
    assert row["status"] == "warn", row
    assert "`gh auth status` did not run" in strip_paths(row["detail"])
    assert "gh auth login" in strip_paths(row["detail"])


# ------------------------------------- the architect's write permission (§36, H-041)

#: §36: the three allows architect/settings.json ships, and the only write allows.
KITS_WRITES = ["Edit(kits/**)", "Write(kits/**)", "MultiEdit(kits/**)"]


def test_the_shipped_architect_settings_allow_exactly_the_three_writes_under_kits(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    """§36 (H-041): headless `claude -p` denies a tool no allow names, so without
    these the role could not write a byte. The shipped file, loaded through the row,
    carries the three and no other write allow, and the row is ok."""
    allow = json.loads(ARCHITECT_SETTINGS.read_text(encoding="utf-8"))["permissions"]["allow"]
    writes = [e for e in allow if re.match(r"\s*(Edit|Write|MultiEdit)\b", e, re.IGNORECASE)]
    assert sorted(writes) == sorted(KITS_WRITES), allow
    d = architect_dir(tmp_path)
    add_architect(write_config(tmp_home, tmp_path), d)
    code, found = checks()
    row = found["role architect"]
    assert code == 0 and row["status"] == "ok", row
    assert "write allow: Edit(kits/**), Write(kits/**), MultiEdit(kits/**)" in strip_paths(
        row["detail"]
    ), row


def _architect_allow(d: Path, allow: list[str], file: str = "settings.json") -> None:
    path = d / ".claude" / file
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    data.setdefault("permissions", {})["allow"] = allow
    path.write_text(json.dumps(data), encoding="utf-8")


@pytest.mark.parametrize("missing", KITS_WRITES)
def test_an_architect_settings_without_one_of_the_three_write_allows_fails_doctor(
    tmp_home: Path, tmp_path: Path, fake_mode: None, missing: str
) -> None:
    d = architect_dir(tmp_path)
    allow = json.loads(ARCHITECT_SETTINGS.read_text(encoding="utf-8"))["permissions"]["allow"]
    _architect_allow(d, [entry for entry in allow if entry != missing])
    add_architect(write_config(tmp_home, tmp_path), d)
    code, found = checks()
    row = found["role architect"]
    assert code == 1 and row["status"] == "fail", row
    assert f"no {missing}" in strip_paths(row["detail"]), row


@pytest.mark.parametrize(
    ("extra", "file"),
    [
        ("Write(repo/**)", "settings.json"),
        ("Edit(.claude/**)", "settings.json"),
        ("MultiEdit(./kits/**)", "settings.json"),
        ("write(kits/**/../..)", "settings.json"),
        ("Edit(~/**)", "settings.local.json"),
    ],
    ids=["Write-repo", "Edit-claude", "MultiEdit-dot-kits", "lowercase-write", "local-Edit-home"],
)
def test_an_architect_write_allow_naming_anything_but_kits_fails_doctor(
    tmp_home: Path, tmp_path: Path, fake_mode: None, extra: str, file: str
) -> None:
    """§36: an allow for a write tool that names anything but `kits/**`, in any of
    the settings layers the row reads, fails the row."""
    d = architect_dir(tmp_path)
    allow = json.loads(ARCHITECT_SETTINGS.read_text(encoding="utf-8"))["permissions"]["allow"]
    if file == "settings.json":
        _architect_allow(d, [*allow, extra])
    else:
        _architect_allow(d, [extra], file)
    add_architect(write_config(tmp_home, tmp_path), d)
    code, found = checks()
    row = found["role architect"]
    assert code == 1 and row["status"] == "fail", row
    assert repr(extra) in strip_paths(row["detail"]), row


#: §36, §37: the one-file kit `doctor --live` has the architect write and check —
#: `kits/hands-doctor-live-<8 hex>`, unique per run. The tests pin the name doctor
#: draws (`live_kit_name`) so the scripted turn can name it.
LIVE_KIT = "hands-doctor-live-0123abcd"
LIVE_FILE = "DOCTOR-LIVE.md"


@contextmanager
def _local_ntfy() -> Iterator[str]:
    """DESIGN §45 "CI": a local stand-in for ntfy that takes every publish (200), so
    a test whose daemon publishes never sends a request off the machine."""

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            self.rfile.read(int(self.headers.get("Content-Length") or 0))
            self.send_response(200)
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"{}")

        do_PUT = do_POST  # noqa: N815

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    httpd.daemon_threads = True
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}"
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


def _live_architect(
    tmp_home: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    tools: Any,
    *,
    job: bool = True,
    layout: str = "repo",
    setup: Any = None,
) -> tuple[dict[str, Any], Path, str | None]:
    """`hands doctor --live` against a running daemon, the architect's turn scripted
    by `tools(kit_file, job_id)` — the fake performs the calls a real turn would
    make. The builder's and aux's live turns take the first two replies. `layout`
    is where the clone is: `repo` (`<cwd>/repo`), `cwd` (the cwd itself) or `none`;
    `setup(d)` runs on the role's directory before doctor does."""
    import sys

    import hands.doctor

    monkeypatch.setenv("PATH", f"{Path(sys.executable).parent}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setattr(hands.doctor, "live_kit_name", lambda: LIVE_KIT)
    d = architect_dir(tmp_path, clone=layout == "repo")
    if layout == "cwd":
        fetch_only_clone(d)
    if setup is not None:
        setup(d)
    config = write_config(tmp_home, tmp_path)
    add_architect(config, d)
    kit_file = d / "kits" / LIVE_KIT / LIVE_FILE
    seen: dict[str, Any] = {}

    async def body(daemon: Daemon) -> None:
        job_id = None
        if job:
            job_id = daemon.spool.create_job(
                role="aux", context="clear", prompt="hello", origin="cli", state="held"
            ).id
        replies = tmp_home / "replies.json"
        replies.write_text(json.dumps(
            ["VERDICT: doctor ok", "VERDICT: doctor ok",
             {"result": "VERDICT: doctor ok", "tools": tools(kit_file, job_id)}]
        ))  # fmt: skip
        monkeypatch.setenv("HANDS_FAKE_CLAUDE_REPLIES", str(replies))
        out, err = io.StringIO(), io.StringIO()
        await asyncio.to_thread(
            main, ["--project", "demo", "doctor", "--json", "--live"], stdout=out, stderr=err
        )
        assert out.getvalue(), err.getvalue()
        seen["found"] = {c["name"]: c for c in json.loads(out.getvalue())["checks"]}
        seen["job"] = job_id

    with _local_ntfy() as ntfy:
        # The daemon publishes while the turns run: to the stub, never ntfy.sh.
        with_ntfy_url(config, ntfy)
        drive(body)
    return seen["found"], kit_file, seen["job"]


def _write(path: Path, *, denied: bool = False) -> dict[str, Any]:
    call = {"name": "Write", "input": {"file_path": str(path), "content": "doctor\n"}}
    return {**call, "denied": True} if denied else call


def _bash(command: str, *, denied: bool = False) -> dict[str, Any]:
    call: dict[str, Any] = {"name": "Bash", "input": {"command": command}}
    return {**call, "denied": True} if denied else call


def _kit_check(kit: str = LIVE_KIT, repo: str = "./repo") -> str:
    return f"hands kit check kits/{kit} --repo {repo}"


KIT_CHECK = _kit_check()


def test_doctor_live_for_the_architect_writes_checks_shows_and_removes(
    tmp_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§36 (H-041): a scripted live turn that writes the one file under kits/, runs
    `hands kit check` on that one-file kit against the clone and `hands show` on a
    job of the spool passes the row; doctor removes the file afterwards."""
    found, kit_file, job_id = _live_architect(
        tmp_home, tmp_path, monkeypatch,
        lambda path, job: [_write(path), _bash(KIT_CHECK), _bash(f"hands show {job}")],
    )  # fmt: skip
    row = found["live architect"]
    assert row["status"] == "ok", row
    for step in ("wrote", "kit check", f"hands show {job_id}", "removed", "--repo ./repo"):
        assert step in strip_paths(row["detail"]), row
    assert not kit_file.exists() and not kit_file.parent.exists()


def test_doctor_live_for_an_architect_whose_cwd_is_the_clone_checks_against_the_cwd(
    tmp_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§37 (review 20 should-fix 4): `driver_clone` takes the role's cwd itself as the
    clone when it is the git repository, so the live turn names it as `--repo` (`.`),
    and a turn that checks the live kit against it passes the row."""
    check = _kit_check(repo=".")
    found, kit_file, job_id = _live_architect(
        tmp_home, tmp_path, monkeypatch,
        lambda path, job: [_write(path), _bash(check), _bash(f"hands show {job}")],
        layout="cwd",
    )  # fmt: skip
    row = found["live architect"]
    assert row["status"] == "ok", row
    assert f"`{check}`" in strip_paths(row["detail"]), row
    assert not kit_file.parent.exists()


def test_doctor_live_for_an_architect_with_no_clone_fails_before_the_turn(
    tmp_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§37: a role with no clone (neither `<cwd>/repo` nor the cwd is a git
    repository) fails the row before a turn is spent; no kit is written."""
    found, kit_file, job_id = _live_architect(
        tmp_home, tmp_path, monkeypatch,
        lambda path, job: [_write(path), _bash(KIT_CHECK), _bash(f"hands show {job}")],
        layout="none",
    )  # fmt: skip
    row = found["live architect"]
    assert row["status"] == "fail", row
    assert "no clone" in strip_paths(row["detail"]), row
    assert "Not run" in strip_paths(row["detail"]), row
    assert not kit_file.parent.exists()


def _other_kit(d: Path) -> None:
    other = d / "kits" / "other-kit"
    other.mkdir(parents=True)
    (other / "OTHER.md").write_text("other\n")


def _other_repo(d: Path) -> None:
    fetch_only_clone(d / "elsewhere")


@pytest.mark.parametrize(
    ("setup", "check"),
    [
        (_other_kit, _kit_check(kit="other-kit")),
        (_other_repo, _kit_check(repo="./elsewhere")),
    ],
    ids=["another-kit", "another-repo"],
)
def test_doctor_live_for_an_architect_whose_turn_checks_another_kit_fails(
    tmp_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, setup: Any, check: str
) -> None:
    """§37 (review 20 should-fix 4): the judged `hands kit check` must name the live
    kit's own path and the clone's `--repo`. A passing check of another one-file kit,
    or of the live kit against another repository, does not pass the step."""
    found, _, _ = _live_architect(
        tmp_home, tmp_path, monkeypatch,
        lambda path, job: [_write(path), _bash(check), _bash(f"hands show {job}")],
        setup=setup,
    )  # fmt: skip
    row = found["live architect"]
    assert row["status"] == "fail", row
    assert "did not happen: kit check" in strip_paths(row["detail"]), row


def test_doctor_live_leaves_an_existing_kit_of_its_name_untouched_and_fails(
    tmp_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§37 (review 20 should-fix 5): when the live kit's path already exists the row
    fails without running the turn, and what was there is left as it was."""

    def existing(d: Path) -> None:
        kit = d / "kits" / LIVE_KIT
        kit.mkdir(parents=True)
        (kit / "KEEP.md").write_text("mine\n")

    found, kit_file, _ = _live_architect(
        tmp_home, tmp_path, monkeypatch,
        lambda path, job: [_write(path), _bash(KIT_CHECK), _bash(f"hands show {job}")],
        setup=existing,
    )  # fmt: skip
    row = found["live architect"]
    assert row["status"] == "fail", row
    assert "already exists" in strip_paths(row["detail"]), row
    assert "Not run" in strip_paths(row["detail"]), row
    assert (kit_file.parent / "KEEP.md").read_text() == "mine\n"
    assert not kit_file.exists()


def test_the_live_kit_name_is_unique_per_run() -> None:
    """§37: `kits/hands-doctor-live-<8 hex>`, a fresh name each run."""
    from hands.doctor import live_kit_name

    names = {live_kit_name() for _ in range(20)}
    assert len(names) == 20
    assert all(re.fullmatch(r"hands-doctor-live-[0-9a-f]{8}", name) for name in names), names


@pytest.mark.parametrize(
    ("step", "tools"),
    [
        ("write", lambda path, job: [
            _write(path, denied=True), _bash(KIT_CHECK), _bash(f"hands show {job}")]),
        ("kit check", lambda path, job: [
            _write(path), _bash(KIT_CHECK, denied=True), _bash(f"hands show {job}")]),
        ("hands show", lambda path, job: [
            _write(path), _bash(KIT_CHECK), _bash(f"hands show {job}", denied=True)]),
        ("hands show", lambda path, job: [_write(path), _bash(KIT_CHECK)]),
        ("remove", lambda path, job: [
            _write(path), _bash(KIT_CHECK), _bash(f"hands show {job}"),
            _bash(f"chmod 555 kits/{LIVE_KIT}")]),
    ],
    ids=["write-denied", "kit-check-denied", "show-denied", "show-not-run", "not-removable"],
)
def test_doctor_live_for_an_architect_that_cannot_do_all_four_fails(
    tmp_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, step: str, tools: Any
) -> None:
    """§36: a live turn that cannot do all four fails the row, naming what did not
    happen. `not-removable` leaves the kit directory unwritable, so doctor cannot
    remove the file."""
    found, kit_file, _ = _live_architect(tmp_home, tmp_path, monkeypatch, tools)
    if kit_file.parent.exists():
        kit_file.parent.chmod(0o755)
    row = found["live architect"]
    assert row["status"] == "fail", row
    assert f"did not happen: {step}" in strip_paths(row["detail"]), row


def test_doctor_live_for_the_architect_fails_without_a_job_to_show(
    tmp_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§36: `hands show` needs a job of the spool; with none the row fails before a
    turn is spent, and says how to make one."""
    found, kit_file, _ = _live_architect(
        tmp_home, tmp_path, monkeypatch, lambda path, job: [_write(path)], job=False
    )
    row = found["live architect"]
    assert row["status"] == "fail", row
    assert "no job in the spool" in strip_paths(row["detail"]), row
    assert not kit_file.exists()


# --------------------------------------------- §36 "The runner" (H-042, H-043)


def _commit(repo: Path, name: str) -> str:
    (repo / name).write_text(name)
    _git(repo, "add", "--", name)
    _git(repo, "-c", "user.name=t", "-c", "user.email=t@t.invalid", "-c", "commit.gpgsign=false",
         "-c", "core.hooksPath=/dev/null", "commit", "-q", "-m", name)
    out = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], check=True,
                         capture_output=True, text=True)
    return out.stdout.strip()


@pytest.mark.parametrize("role", ["driver", "architect"])
def test_a_role_row_prints_the_clone_head_against_origin_and_the_project(
    tmp_home: Path, tmp_path: Path, fake_mode: None, monkeypatch: pytest.MonkeyPatch, role: str
) -> None:
    """§36: doctor's role rows print the clone's HEAD against origin and the project
    the job will see — the config's, not doctor's own `HANDS_PROJECT`. The clone is
    one commit behind origin/main as last fetched."""
    monkeypatch.setenv("HANDS_PROJECT", "other")
    d, add = _role_dir(tmp_path, role)
    repo = d / "repo"
    old = _commit(repo, "old.txt")
    new = _commit(repo, "new.txt")
    _git(repo, "update-ref", "refs/remotes/origin/main", new)
    _git(repo, "checkout", "-q", "--detach", old)
    code, row = _row(tmp_home, tmp_path, role, d, add)
    assert code == 0 and row["status"] == "ok", row
    detail = row["detail"]
    assert f"clone HEAD {old[:12]}, origin/main {new[:12]} as last fetched" in strip_paths(detail)
    assert "HANDS_PROJECT=demo" in strip_paths(detail), detail
    assert "HANDS_PROJECT=other" not in strip_paths(detail), detail


def test_a_role_row_names_the_configured_branch(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    """§36: `[roles.<role>] branch` is the origin branch the row compares HEAD with;
    HEAD at it is said so, and an origin branch the clone has not fetched is named."""
    d = driver_dir(tmp_path)
    repo = d / "repo"
    tip = _commit(repo, "a.txt")
    _git(repo, "update-ref", "refs/remotes/origin/trunk", tip)
    add_driver(write_config(tmp_home, tmp_path), d, 'branch = "trunk"')
    _code, found = checks()
    detail = found["role driver"]["detail"]
    assert f"clone HEAD {tip[:12]} at origin/trunk as last fetched" in strip_paths(detail), detail

    _git(repo, "update-ref", "-d", "refs/remotes/origin/trunk")
    _code, found = checks()
    detail = found["role driver"]["detail"]
    assert f"clone HEAD {tip[:12]}, origin/trunk not fetched" in strip_paths(detail), detail


def test_a_builder_row_prints_the_project_its_jobs_see(
    tmp_home: Path, tmp_path: Path, fake_mode: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§36 (H-043): every role job carries `HANDS_PROJECT` from the config."""
    monkeypatch.setenv("HANDS_PROJECT", "other")
    write_config(tmp_home, tmp_path)
    _code, found = checks()
    detail = found["role builder"]["detail"]
    assert "HANDS_PROJECT=demo" in strip_paths(detail), detail


# ----------------------------------------- §38 (H-046): the public broker's cap


def with_ntfy_url(path: Path, url: str | None) -> None:
    text = path.read_text()
    if url is not None:
        topic = 'ntfy_topic = "hands-test"'
        text = text.replace(topic, f'{topic}\nntfy_url = "{url}"')
    path.write_text(text)


@pytest.mark.parametrize(
    "url", [None, "https://ntfy.sh", "https://NTFY.sh:443/x", "https://ntfy.example.com"]
)
def test_doctor_warns_on_a_public_ntfy_url_naming_the_cap_and_the_self_hosted_section(
    tmp_home: Path, tmp_path: Path, fake_mode: None, url: str | None
) -> None:
    with_ntfy_url(write_config(tmp_home, tmp_path), url)
    code, found = checks()
    assert code == 0
    row = found["broker"]
    assert row["status"] == "warn"
    for said in ("public broker", "daily cap", "Self-hosted ntfy over Tailscale",
                 "who_min_interval_s"):  # fmt: skip
        assert said in strip_paths(row["detail"])
    code, out, _err = run()
    assert strip_paths(out).strip().endswith("doctor: green")


@pytest.mark.parametrize(
    ("url", "kind"),
    [
        ("http://100.64.0.1:2586", "tailnet"),
        ("http://100.127.255.254", "tailnet"),
        ("https://x.tailnet.ts.net", "tailnet"),
        ("http://192.168.1.5:8080", "private"),
        ("http://10.0.0.2", "private"),
        ("http://172.16.4.4", "private"),
        ("http://127.0.0.1:2586", "private"),
        ("http://localhost:2586", "private"),
        ("http://169.254.1.1", "private"),
        ("http://[fd7a:115c:a1e0::1]:2586", "private"),
    ],
)
def test_doctor_does_not_warn_on_a_private_or_tailnet_ntfy_url(
    tmp_home: Path, tmp_path: Path, fake_mode: None, url: str, kind: str
) -> None:
    with_ntfy_url(write_config(tmp_home, tmp_path), url)
    code, found = checks()
    assert code == 0
    row = found["broker"]
    assert row["status"] == "ok", row
    assert kind in strip_paths(row["detail"])
    assert "daily cap" not in strip_paths(row["detail"])


@pytest.mark.parametrize(
    "url",
    ["http://100.128.0.1", "http://8.8.8.8", "https://ts.net.example.com", "http://172.32.0.1"],
)
def test_an_address_just_outside_the_private_and_tailnet_ranges_is_public(
    tmp_home: Path, tmp_path: Path, fake_mode: None, url: str
) -> None:
    with_ntfy_url(write_config(tmp_home, tmp_path), url)
    _code, found = checks()
    assert found["broker"]["status"] == "warn"


# ------------------------------------------- §40 (H-067): dangling worktrees


def _worktree_git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def test_doctor_warns_on_a_worktree_registered_under_a_role_clone_whose_path_is_missing(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    """§40 (H-067): an aborted review leaves a worktree registered under the clone
    after its directory is gone. Doctor names it, and only it, as a warning — a
    live worktree beside it is not named — and the remedy is `git worktree prune`.
    A local repository, no remote."""
    work = tmp_path / "work"
    commit_file(work, "README.md", "hi\n")
    gone, alive = tmp_path / "review-gone", tmp_path / "review-alive"
    _worktree_git(work, "worktree", "add", "--detach", str(gone))
    _worktree_git(work, "worktree", "add", "--detach", str(alive))
    shutil.rmtree(gone)
    write_config(tmp_home, tmp_path)
    code, found = checks()
    row = found["worktrees"]
    assert row["status"] == "warn", row
    detail = strip_paths(row["detail"])
    assert str(gone) in row["detail"], row
    assert "review-gone is missing" in strip_paths(detail), row
    assert "review-alive" not in strip_paths(detail), row
    assert "git worktree prune" in strip_paths(detail), row
    assert "(builder, aux)" in strip_paths(detail), row
    assert code == 0, "a dangling worktree is a warning, not a failure"

    _worktree_git(work, "worktree", "prune")
    _code, found = checks()
    row = found["worktrees"]
    assert row["status"] == "ok", row
    assert "review-gone" not in strip_paths(row["detail"]), row


def test_doctors_worktree_row_is_ok_on_a_clone_with_no_linked_worktree(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    """The stand-in `.git` of `write_config` registers nothing: the row is `ok`."""
    write_config(tmp_home, tmp_path)
    _code, found = checks()
    assert found["worktrees"]["status"] == "ok", found["worktrees"]


def test_doctor_reads_a_relative_gitdir_and_a_missing_gitdir_file(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    """A worktree entry is `.git/worktrees/<name>/gitdir`, the path of the worktree's
    `.git` file, absolute or (git's `worktree.useRelativePaths`) relative to the
    entry; an entry without its gitdir file is one git's prune removes too."""
    work = tmp_path / "work"
    (work / ".git" / "worktrees" / "rel").mkdir(parents=True)
    (work / ".git" / "worktrees" / "rel" / "gitdir").write_text("../../../../rel-wt/.git\n")
    (work / ".git" / "worktrees" / "nofile").mkdir()
    write_config(tmp_home, tmp_path)
    _code, found = checks()
    row = found["worktrees"]
    assert row["status"] == "warn", row
    assert str(tmp_path / "rel-wt") in row["detail"], row
    assert "nofile: no readable" in strip_paths(row["detail"]), row
    (tmp_path / "rel-wt").mkdir()
    (tmp_path / "rel-wt" / ".git").write_text("gitdir: x\n")
    _code, found = checks()
    assert "rel-wt" not in strip_paths(found["worktrees"]["detail"])


def test_doctor_reports_an_unreadable_worktrees_dir_as_a_warning_and_every_other_row(
    tmp_home: Path, tmp_path: Path, fake_mode: None
) -> None:
    """PR #5 hosted finding 4: an OSError on `.git/worktrees` itself — here a mode
    000 directory — is a WARN row naming the clone, not a doctor that stops; the
    rows after it are still reported."""
    if os.geteuid() == 0:
        pytest.skip("root reads a mode 000 directory")
    work = tmp_path / "work"
    admin = work / ".git" / "worktrees"
    (admin / "rel").mkdir(parents=True)
    write_config(tmp_home, tmp_path)
    admin.chmod(0)
    try:
        code, found = checks()
    finally:
        admin.chmod(0o755)
    row = found["worktrees"]
    assert row["status"] == "warn", row
    assert f"{work.resolve()} (builder, aux)" in row["detail"], row
    assert "cannot be read" in strip_paths(row["detail"]), row
    assert {"daemon", "allowed roots"} <= set(found), sorted(found)
    assert code == 0, "an unreadable worktrees directory is a warning, not a failure"


def test_doctor_reports_a_worktrees_dir_that_vanishes_during_the_check_as_a_warning(
    tmp_home: Path, tmp_path: Path, fake_mode: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """PR #5 hosted finding 4: `.git/worktrees` present when looked at, gone when
    listed (a `git worktree prune` in between) is a WARN row naming the clone."""
    work = tmp_path / "work"
    (work / ".git" / "worktrees").mkdir(parents=True)
    write_config(tmp_home, tmp_path)
    real = Path.iterdir

    def vanishing(self: Path) -> Any:
        if self.name == "worktrees" and self.parent.name == ".git":
            raise FileNotFoundError(2, "No such file or directory", str(self))
        return real(self)

    monkeypatch.setattr(Path, "iterdir", vanishing)
    code, found = checks()
    row = found["worktrees"]
    assert row["status"] == "warn", row
    assert f"{work.resolve()} (builder, aux)" in row["detail"], row
    assert "cannot be read" in strip_paths(row["detail"]), row
    assert "No such file or directory" in strip_paths(row["detail"]), row
    assert {"daemon"} <= set(found), sorted(found)
    assert code == 0


# ---------------------------------------------- doctor's `main` row (§45, mission 29 U2)

PR_RULE = {"type": "pull_request", "parameters": {"required_approving_review_count": 0}}
CHECKS_RULE = {
    "type": "required_status_checks",
    "parameters": {
        "required_status_checks": [{"context": "check"}, {"context": "lint"}],
        "strict_required_status_checks_policy": False,
    },
}


def _main_row(
    tmp_home: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    setting: str | None = None,
    rules: list[dict[str, Any]] | None = None,
    origin: str = "https://github.com/o/r.git",
) -> dict[str, Any]:
    """Doctor's `main` row, the builder's clone a local repository whose `origin`
    is `origin` (never contacted: the fake `gh` answers the rules)."""
    path = write_config(tmp_home, tmp_path)
    if setting is not None:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(f'\n[repository]\nmain = "{setting}"\n')
    work = tmp_path / "work"
    shutil.rmtree(work / ".git")
    subprocess.run(["git", "init", "-q", str(work)], check=True, timeout=30)
    subprocess.run(
        ["git", "-C", str(work), "remote", "add", "origin", origin], check=True, timeout=30
    )
    if rules is not None:
        monkeypatch.setenv("FAKE_GH_RULES", json.dumps(rules))
    monkeypatch.setenv("FAKE_GH_API_LOG", str(tmp_path / "gh.log"))
    _, found = checks()
    return found["main"]


def test_main_row_is_ok_for_direct_with_no_rules(
    tmp_home: Path, tmp_path: Path, fake_mode: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    row = _main_row(tmp_home, tmp_path, monkeypatch, rules=[])
    assert row["status"] == "ok", row
    for said in ("setting: direct", "o/r", "rules: none"):
        assert said in strip_paths(row["detail"]), said
    log = (tmp_path / "gh.log").read_text(encoding="utf-8").splitlines()
    assert log == ["api repos/o/r/rules/branches/main"]


def test_main_row_is_ok_for_pull_request_with_both_rules_naming_the_checks(
    tmp_home: Path, tmp_path: Path, fake_mode: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    row = _main_row(
        tmp_home, tmp_path, monkeypatch, setting="pull-request", rules=[PR_RULE, CHECKS_RULE]
    )
    assert row["status"] == "ok", row
    assert "setting: pull-request" in strip_paths(row["detail"])
    assert "pull_request, required_status_checks" in strip_paths(row["detail"])
    assert "required checks: check, lint" in strip_paths(row["detail"])


def test_main_row_is_ok_for_direct_with_an_unrelated_rule(
    tmp_home: Path, tmp_path: Path, fake_mode: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    row = _main_row(tmp_home, tmp_path, monkeypatch, rules=[{"type": "deletion"}])
    assert row["status"] == "ok", row
    assert "deletion" in strip_paths(row["detail"])


@pytest.mark.parametrize("rules", [[PR_RULE], [CHECKS_RULE], [PR_RULE, CHECKS_RULE]])
def test_main_row_warns_for_direct_with_a_pull_request_gate(
    tmp_home: Path,
    tmp_path: Path,
    fake_mode: None,
    monkeypatch: pytest.MonkeyPatch,
    rules: list[dict[str, Any]],
) -> None:
    row = _main_row(tmp_home, tmp_path, monkeypatch, setting="direct", rules=rules)
    assert row["status"] == "warn", row
    said = "a direct push is refused, so applies stop and reviews go to branches"
    assert said in strip_paths(row["detail"])
    assert 'set `[repository] main = "pull-request"`' in strip_paths(row["detail"])


def test_main_row_warns_for_pull_request_with_no_pull_request_rule(
    tmp_home: Path, tmp_path: Path, fake_mode: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    row = _main_row(tmp_home, tmp_path, monkeypatch, setting="pull-request", rules=[])
    assert row["status"] == "warn", row
    assert "`main` is not protected yet: docs/PR-CI-GATE.md" in strip_paths(row["detail"])


def test_main_row_warns_for_pull_request_without_required_checks(
    tmp_home: Path, tmp_path: Path, fake_mode: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    row = _main_row(tmp_home, tmp_path, monkeypatch, setting="pull-request", rules=[PR_RULE])
    assert row["status"] == "warn", row
    assert (
        "pull requests merge without CI, and `hands ci-wait` has no check to wait for, "
        "so every apply stops" in strip_paths(row["detail"])
    )


@pytest.mark.parametrize("kind", ["required_linear_history", "update", "merge_queue"])
@pytest.mark.parametrize("setting", ["direct", "pull-request"])
def test_main_row_warns_for_a_rule_that_refuses_or_queues_hands_merges(
    tmp_home: Path,
    tmp_path: Path,
    fake_mode: None,
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
    setting: str,
) -> None:
    rules = [{"type": kind}] if setting == "direct" else [PR_RULE, CHECKS_RULE, {"type": kind}]
    row = _main_row(tmp_home, tmp_path, monkeypatch, setting=setting, rules=rules)
    assert row["status"] == "warn", row
    said = f"`{kind}`: hands' merge commits and pull-request merges are refused or queued"
    assert said in strip_paths(row["detail"])


def test_main_row_never_fails_doctor(
    tmp_home: Path, tmp_path: Path, fake_mode: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _main_row(tmp_home, tmp_path, monkeypatch, setting="pull-request", rules=[])
    code, found = checks()
    assert found["main"]["status"] == "warn"
    assert all(c["status"] != "fail" for c in found.values()), found
    assert code == 0


@pytest.mark.parametrize(
    "origin", ["git@github.com:o/r.git", "ssh://git@github.com/o/r", "https://github.com/o/r"]
)
def test_main_row_reads_the_repository_of_an_ssh_or_https_origin(
    tmp_home: Path, tmp_path: Path, fake_mode: None, monkeypatch: pytest.MonkeyPatch, origin: str
) -> None:
    row = _main_row(tmp_home, tmp_path, monkeypatch, rules=[], origin=origin)
    assert row["status"] == "ok", row
    log = (tmp_path / "gh.log").read_text(encoding="utf-8").splitlines()
    assert log == ["api repos/o/r/rules/branches/main"]


def test_main_row_is_skipped_with_no_gh(
    tmp_home: Path, tmp_path: Path, fake_mode: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    bindir = tmp_path / "bin-without-gh"
    bindir.mkdir()
    for tool in ("python3", "git", "sh", "env"):
        found = shutil.which(tool)
        if found:
            (bindir / tool).symlink_to(found)
    monkeypatch.setenv("PATH", str(bindir))
    row = _main_row(tmp_home, tmp_path, monkeypatch, rules=[])
    assert row["status"] == "skip", row
    assert "no `gh` on PATH" in strip_paths(row["detail"])


def test_main_row_is_skipped_when_gh_is_not_signed_in(
    tmp_home: Path, tmp_path: Path, fake_mode: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_GH_MODE", "unauth")
    row = _main_row(tmp_home, tmp_path, monkeypatch, rules=[])
    assert row["status"] == "skip", row
    assert "not signed in to github.com" in strip_paths(row["detail"])


def test_main_row_is_skipped_for_an_origin_not_on_github_com(
    tmp_home: Path, tmp_path: Path, fake_mode: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    row = _main_row(
        tmp_home, tmp_path, monkeypatch, rules=[], origin="https://x:tk_SECRET0@gitlab.com/o/r"
    )
    assert row["status"] == "skip", row
    assert "not a github.com repository" in strip_paths(row["detail"])
    assert "tk_SECRET0" not in strip_paths(row["detail"])
    assert not (tmp_path / "gh.log").exists()


def test_main_row_is_skipped_when_the_read_fails(
    tmp_home: Path, tmp_path: Path, fake_mode: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_GH_MODE", "rulesfail")
    row = _main_row(tmp_home, tmp_path, monkeypatch, rules=[])
    assert row["status"] == "skip", row
    assert "could not be read" in strip_paths(row["detail"])
    assert "HTTP 502" in strip_paths(row["detail"])
