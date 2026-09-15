"""`hands doctor` — the install check (DESIGN §4, §11, §14).

§4 gives doctor five jobs: the claude binary, the ops script's flags, the
allowed roots, a one-turn `claude -p` per role, and the notification check of
§11. Three properties shape the code below.

**Doctor runs without a daemon.** §14 step 1 is "write the config; `hands
doctor`" — before `handsd` has ever been started. So the checks live here, in a
module the CLI calls directly, and the daemon is itself one of the things
checked: unreachable is a *warning*, not a failure.

**Only one check can spend money, and it is off by default.** A real one-turn
`claude -p` per role is the only thing in this repo that consumes the human's
subscription, so it runs only with `hands doctor --live`, and never when
`HANDS_DOCTOR_FAKE=1` says the configured binary is a stand-in. Every other
check is free and always runs. No test may run the live turn against a real
binary, and `tests/test_doctor.py` proves the skip by pointing `runner.claude`
at a script that leaves a file behind if it is ever spawned.

**The notification check of §11 is not runnable by hands.** §11 retired the
driver's background wait — "ntfy is the human's doorbell; the human's `check`
is the driver's" — so what is left to check is the doorbell, and that ends on a phone
this process cannot see. Doctor therefore prints the procedure with the exact
commands and the clear-up step, for the human to run once at the laptop.

**A config that will not load is a check result, not a crash** (§20, review 3
should-fix 8). Doctor is the one command whose job is explaining a broken
config, so the CLI hands the `ConfigError` back here as a failed `config` row
(`config_error`) and prints the same report it always prints. Everything below
therefore takes the project name and the config path rather than a `Config`:
when there is no `Config`, there is still a report.

Statuses: `ok`, `warn` (worth knowing, not broken), `skip` (deliberately not
run), `fail` (this install will not work). `hands doctor` exits 1 if anything
failed, 0 otherwise.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import hands.monitor
import hands.runner
from hands.config import (
    BG_WAIT_CEILING_ENV,
    DRIVER_ROLE,
    ROLE_ENV,
    Config,
    RoleConfig,
    driver_clone,
)
from hands.playbook import PlaybookError, load_playbook, playbook_path
from hands.runner import build_argv
from hands.spool import SpoolError, resolve_under_roots

__all__ = [
    "FAKE_ENV",
    "Check",
    "config_error",
    "render",
    "report",
    "run_checks",
    "wake_procedure",
]

#: Set to 1 when the configured `runner.claude` is a stand-in (the test suite
#: points it at `tests/fake_claude.py`). It disables exactly one check: the live
#: turn. Everything else runs for real against the stand-in, which is the point.
FAKE_ENV = "HANDS_DOCTOR_FAKE"

OK, WARN, SKIP, FAIL = "ok", "warn", "skip", "fail"

#: Seconds for the free probes (`claude --version`, the ops script).
PROBE_S = 10.0
#: §28: the hook the driver directory's settings.json must run before every Bash call.
GUARD_HOOK = ".claude/hooks/bash_guard.py"
#: Seconds for one real `claude -p` turn. A one-line answer, not a task.
LIVE_S = 180.0
#: The live turn's prompt: one turn, no tools, and it exercises §10's VERDICT
#: contract at the same time.
LIVE_PROMPT = "Reply with exactly this line and nothing else:\nVERDICT: doctor ok\n"

#: What a script prints when it does not know a flag. Used to tell "this script
#: does not take `--pids`" apart from "it took them and then failed for its own
#: reasons" (no git repo at the probe's `--base`, for one).
_REFUSALS = ("unrecognized", "unrecognised", "unknown option", "invalid option", "illegal option")



@dataclass(frozen=True)
class Check:
    """One line of the report: what was checked, how it went, and the evidence."""

    name: str
    status: str
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "status": self.status, "detail": self.detail}


def is_fake() -> bool:
    return os.environ.get(FAKE_ENV, "") not in ("", "0")


# ------------------------------------------------------------- the checks


def run_checks(
    config: Config,
    *,
    live: bool = False,
    socket_path: Path | None = None,
    daemon: dict[str, Any] | None = None,
) -> list[Check]:
    """Every check of §4, in the order a human reads them.

    `daemon` is how the daemon itself answers `doctor` over the API (§9's face
    wraps the same method): it describes the process that is already serving,
    instead of having it connect to its own socket.
    """
    found = [_config_check(config)]
    found += [_claude_check(config)]
    found += [_role_check(role) for role in config.roles.values() if role.name != DRIVER_ROLE]
    found += [_driver_check(config)]
    found += [_roots_check(config), _ops_check(config), _isolation_check(config)]
    found += [_playbook_check(config), _notifications_check(config), _phone_check(config)]
    found += [_go_check(config), _kit_check(config), _who_check(config)]
    found += [_daemon_check(config, socket_path, daemon)]
    found += [_live_check(config, role, live=live) for role in config.roles.values()]
    return found


def config_error(exc: Exception, path: Path | None) -> Check:
    """The `config` row when the config does not load at all (§4, §20).

    The name is `config` — the row a `--json` caller already reads — so a broken
    config is the same check failing, not a different report shape.
    """
    where = f"{path}: " if path is not None and str(path) not in str(exc) else ""
    return Check(
        "config",
        FAIL,
        f"{where}{exc}\nthe config does not load, so none of doctor's other checks "
        "could run; fix the line above and run `hands doctor` again (§13)",
    )


def _config_check(config: Config) -> Check:
    roles = ", ".join(sorted(config.roles))
    detail = (
        f"{config.path} — project {config.project}; roles {roles}; "
        f"socket {config.server.socket}"
    )
    if not config.server.ntfy_topic:
        return Check(
            "config",
            WARN,
            f"{detail}\nno ntfy_topic ([notify], or [server]): §11's notifications "
            "(stop, job.held, max_resumes, daemon crash) have nowhere to go, so you only "
            "learn you are needed by looking",
        )
    return Check("config", OK, f"{detail}; ntfy topic set")


def _notifications_check(config: Config) -> Check:
    """§11, §24: notifications on or off — `ok` either way, never a failure.

    Off is already a warning on the `config` row, which says what is lost; this
    row is the on/off answer §24 asks doctor for. The topic is not printed.
    """
    if not config.notify.ntfy_topic:
        return Check(
            "notifications",
            OK,
            "notifications off: no ntfy_topic ([notify], or [server]), so handsd "
            "notifies nobody (§11, §24)",
        )
    return Check(
        "notifications",
        OK,
        "notifications on: handsd publishes stop, job.held, an exhausted max_resumes "
        "and daemon start/crash to ntfy_topic (§11); `hands notify --test` proves "
        "the transport",
    )


def _who_check(config: Config) -> Check:
    """§24: the who view on or off — `ok` either way, never a failure.

    On means `who_topic` is set, so `handswho` has somewhere to push. Doctor does
    not see whether `handswho` is running; it says how it is started. Neither
    topic is printed.
    """
    notify = config.notify
    if not notify.who_topic:
        return Check(
            "who",
            OK,
            "who view off: no [notify] who_topic, so `handswho` has nowhere to push; "
            "`hands who` still prints the picture at the terminal (§24)",
        )
    asks = (
        "`status`, `who`, `check` or `?` on who_cmd_topic asks for it"
        if notify.who_cmd_topic
        else "no who_cmd_topic, so it pushes on change only"
    )
    return Check(
        "who",
        OK,
        f"who view on: `handswho` pushes the picture to who_topic when it changes; {asks}"
        f"\nnot checked here: whether handswho is running — `handswho --project "
        f"{config.project}`, or systemd/handswho.service, off unless enabled (§24)",
    )


def _phone_check(config: Config) -> Check:
    """§24's command channel, on or off — never a failure from here.

    A `cmd_topic` without a `cmd_secret` does not load at all, so that refusal is
    the failed `config` row (`config_error`), not this one. Neither the secret nor
    the topics are printed: both are only as private as nobody else seeing them.
    """
    notify = config.notify
    if not notify.channel:
        return Check(
            "phone",
            OK,
            "command channel off: no [notify] cmd_topic, so handsd takes no commands "
            "from the phone (§24)",
        )
    detail = (
        "command channel on: handsd subscribes to [notify] cmd_topic and takes approve, "
        "deny, pause, resume and status; a typed command ends with cmd_secret, and a "
        "held job's notification carries Approve/Deny buttons with a single-use nonce"
    )
    if not notify.ntfy_topic:
        return Check(
            "phone",
            WARN,
            f"{detail}\nno ntfy_topic: the held-job notifications that carry the buttons "
            "and the answer to `status` have nowhere to go",
        )
    return Check("phone", OK, detail)


def _go_check(config: Config) -> Check:
    """§26's `go`, on or off — `ok` either way, never a failure from here.

    On means what `hands.phone` needs to accept a `go`: the command channel, and
    the playbook in force loading (by the same loader, from the builder's cwd)
    with a `[series] kickoff`. A playbook that does not load is the `playbook`
    row's failure; here it is only why `go` is off. Whether a builder job is
    running, queued or held is a moment, not an install, so it is not checked.
    """
    if not config.notify.channel:
        return Check(
            "go",
            OK,
            "go off: no [notify] cmd_topic and cmd_secret, so the phone cannot send the "
            "kickoff (§26)",
        )
    path = playbook_path(config)
    try:
        book = load_playbook(path, cwd=config.role("builder").cwd)
    except PlaybookError:
        return Check(
            "go",
            OK,
            "go off: the playbook does not load (see the playbook row), so `go` is refused (§26)",
        )
    if book is None:
        return Check("go", OK, f"go off: no playbook at {path}, so no [series] kickoff (§26)")
    if book.kickoff is None:
        return Check(
            "go", OK, f"go off: {path} has no [series] kickoff, so `go` has nothing to send (§26)"
        )
    return Check(
        "go",
        OK,
        f"go on: `go <secret>` on cmd_topic sends the builder, clear, origin phone: "
        f"{book.kickoff}\nrefused while a builder job is running, queued or held (§27)",
    )


def _kit_check(config: Config) -> Check:
    """§26's kit transport, on or off — `ok` either way, never a failure from here.

    On means the command channel is on and `[files] kit_dir` resolves inside
    `[files] allowed_roots`, the check `hands.phone` makes before a download.
    Whether ntfy serves an attachment is not checked: doctor sends nothing.
    """
    files = config.files
    if not config.notify.channel:
        return Check(
            "kit transport",
            OK,
            "kit transport off: no [notify] cmd_topic and cmd_secret, so no kit is taken "
            "from the phone (§26)",
        )
    try:
        resolve_under_roots(files.kit_dir, files.allowed_roots)
    except SpoolError:
        return Check(
            "kit transport",
            OK,
            f"kit transport off: [files] kit_dir {files.kit_dir} is outside [files] "
            "allowed_roots, so every kit is refused; list it there (§26)",
        )
    return Check(
        "kit transport",
        OK,
        f"kit transport on: `kit <secret>` with a .zip attached is fetched into kit_dir "
        f"{files.kit_dir}; kit_max_mb {files.kit_max_mb}\nnever unzipped or run; "
        "`kit received <name> <bytes> <sha256>` answers on ntfy_topic (§26)",
    )


def _claude_check(config: Config) -> Check:
    """The binary of §2 exists and answers `--version` (free; always run)."""
    name = config.runner.claude
    path = shutil.which(name) or (name if os.path.isfile(name) else None)
    if path is None:
        return Check(
            "claude",
            FAIL,
            f"no `{name}` on PATH: the runner spawns `{name} -p …` for every job (§2). "
            "Install Claude Code, or set [runner] claude to its absolute path (§13)",
        )
    if not os.access(path, os.X_OK):
        return Check("claude", FAIL, f"{path} is not executable")
    try:
        # argv, never a shell string: the path comes from the human's own config.
        proc = subprocess.run(
            [path, "--version"], capture_output=True, text=True, timeout=PROBE_S
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return Check("claude", FAIL, f"{path} --version did not answer: {exc}")
    version = (proc.stdout or proc.stderr).strip().splitlines()
    if proc.returncode != 0 or not version:
        return Check(
            "claude", FAIL, f"{path} --version exited {proc.returncode}: {_tail(proc.stderr)}"
        )
    fake = f"  [{FAKE_ENV}=1: a stand-in, not the real binary]" if is_fake() else ""
    return Check("claude", OK, f"{version[0]}  ({path}){fake}")


def _role_check(role: RoleConfig) -> Check:
    """§2: every job is spawned in `role.cwd`, and hands reads git HEAD there."""
    name = f"role {role.name}"
    if not role.cwd.is_dir():
        return Check(name, FAIL, f"cwd {role.cwd} does not exist; §13 [roles.{role.name}] cwd")
    flags = role.permission_flags or "(none)"
    # §23 (H-014): the ceiling a role job really runs with, not handsd's own.
    source = (
        f"set by [roles.{role.name}] env"
        if BG_WAIT_CEILING_ENV in role.env
        else "hands' default: claude -p waits for the tasks it started, never terminates"
    )
    # H-008: the two limit-resume behaviours are invisible until a limit is hit.
    detail = (
        f"{role.cwd}  model {role.model}; permission_flags {flags}"
        f"\n{role.resume_behaviour} (§6)"
        f"\nenv {BG_WAIT_CEILING_ENV}={role.spawn_env[BG_WAIT_CEILING_ENV]} ({source}; §23)"
    )
    if not (role.cwd / ".git").exists():
        return Check(
            name,
            WARN,
            f"{detail}\n{role.cwd} is not a git repository: head_at_start/head_at_end "
            "stay empty (§2) and the built-in monitor has no commits to read (§5)",
        )
    return Check(name, OK, detail)


def _driver_check(config: Config) -> Check:
    """§27, §28: the driver role — cwd, its clone, the guard's wiring — and no bypass.

    Always one `role driver` row. No `[roles.driver]` is `ok`: nothing consults.
    A non-empty `permission_flags` does not load (config.py), so the failure a
    human sees is the `config` row; this row fails the same way for a `Config`
    built without the loader. The clone is `<cwd>/repo`, where driver/README.md
    puts it, or `<cwd>` itself when that is the git repository; missing, it warns.

    §28: the row proves the wiring, and fails otherwise: `<cwd>/.claude/settings.json`
    names the hook (a `PreToolUse` entry whose matcher selects `Bash` and whose
    command runs `.claude/hooks/bash_guard.py`), and that hook file self-tests
    green (`--selftest`, exit 0) run with the role's own environment, so with
    `HANDS_ROLE=driver`.
    """
    name = f"role {DRIVER_ROLE}"
    role = config.roles.get(DRIVER_ROLE)
    if role is None:
        return Check(
            name,
            OK,
            "no [roles.driver]: no consult can start a driver role (§27); the human's "
            "driver session is unaffected",
        )
    if role.permission_flags:
        return Check(
            name,
            FAIL,
            f"{role.cwd}  permission_flags {role.permission_flags}\n§27: the driver role "
            "runs with permission_flags empty, so settings.json and the Bash guard are "
            "the law; remove it from [roles.driver]",
        )
    if not role.cwd.is_dir():
        return Check(name, FAIL, f"cwd {role.cwd} does not exist; §27 [roles.driver] cwd")
    warnings: list[str] = []
    failures: list[str] = []
    found = driver_clone(role.cwd)  # §29: the same path the job gets as HANDS_CLONE
    if found is not None:
        clone = f"clone {found}"
    else:
        clone = f"no clone: neither {role.cwd / 'repo'} nor {role.cwd} is a git repository"
        warnings.append(clone)

    settings_path = role.cwd / ".claude" / "settings.json"
    named, problem = _settings_name_the_guard(settings_path, role.cwd)
    if problem is None:
        settings = f"settings {settings_path} names the hook"
    else:
        settings = (
            f"settings {settings_path} does not name the hook ({problem}): copy "
            "driver/settings.json again (§28)"
        )
        failures.append(settings)

    # §29: the self-test runs on the file the settings name, not on a default path;
    # only when they name none is the default the one reported.
    hook = named if named is not None else role.cwd / GUARD_HOOK
    mode = f"{ROLE_ENV}={role.spawn_env[ROLE_ENV]}"
    if not hook.is_file():
        guard = f"no guard at {hook}: nothing narrows the role's Bash calls (driver/README.md)"
        failures.append(guard)
    else:
        probe = _run_probe(
            [shutil.which("python3") or sys.executable, str(hook), "--selftest"],
            cwd=role.cwd,
            env={**os.environ, **role.spawn_env},
        )
        if probe is not None and probe.code == 0 and not probe.timed_out:
            guard = f"guard {hook}\nself-test green in role mode ({mode})"
        else:
            said = (
                "could not be run" if probe is None
                else "timed out" if probe.timed_out
                else f"exit {probe.code}"
            )
            tail = "" if probe is None else "\n" + "\n".join(probe.text.strip().splitlines()[-5:])
            guard = (
                f"guard {hook}\nself-test in role mode ({mode}) is not green ({said}): "
                f"copy driver/hooks/bash_guard.py again (§28){tail}"
            )
            failures.append(guard)

    detail = (
        f"{role.cwd}  model {role.model}; permission_flags (none)"
        f"\n{clone}\n{settings}\n{guard}"
        f"\nguard mode: role mode ({mode} in every driver-role job's environment; §27)"
    )
    status = FAIL if failures else WARN if warnings else OK
    return Check(name, status, detail)


def _settings_name_the_guard(path: Path, cwd: Path) -> tuple[Path | None, str | None]:
    """The hook file `path` wires as a `PreToolUse` command hook for `Bash` (§28,
    §29), and None; or None and why not, in a few words.

    The file is read from the command itself: `shlex` splits it, and the first word
    that is `.claude/hooks/bash_guard.py` or ends in `/.claude/hooks/bash_guard.py` is
    the file, with `$CLAUDE_PROJECT_DIR` (or `${CLAUDE_PROJECT_DIR}`) standing for
    `cwd` and a relative path read against `cwd`, where Claude Code runs the hook.
    A word with any other `$` is not a path doctor can resolve. With several such
    hooks, the first is the one checked."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, "no such file"
    except (OSError, ValueError) as exc:
        return None, f"not readable JSON: {type(exc).__name__}"
    hooks = data.get("hooks") if isinstance(data, dict) else None
    entries = hooks.get("PreToolUse") if isinstance(hooks, dict) else None
    if not isinstance(entries, list):
        return None, "no hooks.PreToolUse"
    unresolved: str | None = None
    for entry in entries:
        if not isinstance(entry, dict) or not _matches_bash(entry.get("matcher")):
            continue
        for hook in entry.get("hooks") or []:
            if not (
                isinstance(hook, dict)
                and hook.get("type") == "command"
                and isinstance(hook.get("command"), str)
            ):
                continue
            try:
                words = shlex.split(hook["command"])
            except ValueError:
                continue
            for word in words:
                word = word.replace("${CLAUDE_PROJECT_DIR}", str(cwd))
                word = word.replace("$CLAUDE_PROJECT_DIR", str(cwd))
                if not (word == GUARD_HOOK or word.endswith("/" + GUARD_HOOK)):
                    continue
                if "$" in word:
                    unresolved = unresolved or word
                    continue
                return cwd / word, None  # an absolute word replaces cwd
    if unresolved is not None:
        return None, f"the hook path {unresolved!r} names a variable doctor cannot resolve"
    return None, f"no PreToolUse command hook for Bash runs {GUARD_HOOK}"


def _matches_bash(matcher: Any) -> bool:
    """A hook matcher that selects the Bash tool: absent, empty, `*`, or a pattern
    matching `Bash` whole."""
    if matcher is None or matcher in ("", "*"):
        return True
    if not isinstance(matcher, str):
        return False
    try:
        return re.fullmatch(matcher, "Bash") is not None
    except re.error:
        return matcher == "Bash"


def _roots_check(config: Config) -> Check:
    """§4: `put`/`get`/`ls` are confined to these, so a missing one is a dead end."""
    missing = [root for root in config.files.allowed_roots if not root.is_dir()]
    listed = ", ".join(str(root) for root in config.files.allowed_roots)
    if missing:
        return Check(
            "allowed roots",
            FAIL,
            "these files.allowed_roots (§13) do not exist: "
            + ", ".join(str(root) for root in missing)
            + f"\nconfigured: {listed}",
        )
    return Check("allowed roots", OK, listed)


def _ops_check(config: Config) -> Check:
    """§5, §14 step 4: the ops script takes `--pids`, `--transcript`, `--base`.

    Asked in the cheapest way that cannot start a real watch: `--help` first, and
    if that says nothing about the three flags, one probe run with a pid that
    cannot exist, stopped after a few seconds. Neither spends a turn.
    """
    path = config.ops.monitor_path
    if path is None:
        return Check(
            "ops script",
            SKIP,
            "no [ops] repo + monitor_cmd in the config: hands watches builder jobs with "
            "its built-in stall detector instead (§5)",
        )
    # §5's flags, read from the module that sends them and at call time, and the
    # probe argv built by the same `ops_argv` the monitor uses: doctor proves what
    # the monitor will send, so there is one list and one argv (review 3 should-fix 3).
    flags = hands.monitor.OPS_FLAGS
    named = ", ".join(flags)
    step4 = f"DESIGN §14 step 4: the ops repo's monitor script must exist and accept {named}"
    if not path.exists():
        return Check("ops script", FAIL, f"{path} does not exist.\n{step4}")
    if not os.access(path, os.X_OK):
        return Check("ops script", FAIL, f"{path} is not executable (chmod +x).\n{step4}")

    helped = _run_probe([str(path), "--help"], cwd=config.ops.repo)
    if helped is not None and all(flag in helped.text for flag in flags):
        return Check(
            "ops script", OK, f"{path} accepts {named} (from `--help`)"
        )

    probe = _run_probe(
        hands.monitor.ops_argv(path, (str(_impossible_pid()), os.devnull, "HEAD")),
        cwd=config.ops.repo,
    )
    if probe is None:
        return Check("ops script", FAIL, f"cannot run {path}.\n{step4}")
    if probe.timed_out:
        return Check(
            "ops script",
            OK,
            f"{path} took {named} and started watching; the probe "
            f"stopped it after {PROBE_S:.0f}s (a dead pid, so no job was touched)",
        )
    lowered = probe.text.lower()
    if probe.code != 0 and any(word in lowered for word in _REFUSALS):
        return Check(
            "ops script", FAIL, f"{path} refused the flags: {_tail(probe.text)}\n{step4}"
        )
    if probe.code != 0:
        return Check(
            "ops script",
            WARN,
            f"{path} accepted {named} but exited {probe.code} on a "
            f"dead pid; that may be its way of saying the job is gone: {_tail(probe.text)}",
        )
    return Check("ops script", OK, f"{path} ran with {named} and exited 0")


def _isolation_check(config: Config) -> Check:
    """§24: which per-job isolation the runner would use here. Informational only.

    Probed now, the way the runner probes it when it starts its first job. Both
    answers are `ok`: the process group is weaker, not broken.
    """
    if hands.runner.detect_isolation() == hands.runner.SCOPE:
        return Check(
            "isolation",
            OK,
            "scope: each `claude -p` runs under `systemd-run --user --scope --unit "
            f"hands-{config.project}-<job>`\nthe monitor's --pids is the scope's "
            "cgroup.procs; a process that double-forks or calls setsid is still in it, "
            "so at job end it is filed as monitor.orphan_processes and the scope is "
            "stopped (§24)",
        )
    return Check(
        "isolation",
        OK,
        "process group: `systemd-run --user --scope` could not start a scope here (no "
        "systemd-run, no cgroup v2, or no user manager answering)\neach `claude -p` "
        "starts in a new process group; this is weaker: a process that calls setsid "
        "leaves the group, so it is not in --pids and not killed at job end, and is "
        "filed as monitor.orphan_processes with killed: false only while it carries "
        "HANDS_JOB (§24, §29)",
    )


def _playbook_check(config: Config) -> Check:
    """§10: no playbook is fine (nothing chains); a broken one is not.

    §25: nor is a dirty or untracked one — the row fails with the refusal, which
    says `dirty` or `untracked` and names both sha256s; `ok` means committed.
    """
    path = playbook_path(config)
    try:
        book = load_playbook(path, cwd=config.role("builder").cwd)
    except PlaybookError as exc:
        return Check("playbook", FAIL, str(exc))
    if book is None:
        return Check(
            "playbook",
            SKIP,
            f"no {path}: hands runs the jobs you send and chains nothing (§10). "
            "A series gets one from the architect with the plan kit",
        )
    runs = ", ".join(str(number) for number in book.auto_runs) or "none"
    return Check(
        "playbook",
        OK,
        f"{path}\nseries {book.series or '(unnamed)'}; {len(book.rules)} rule(s); "
        f"auto_runs {runs}; max_consults {book.max_consults}; sha256 {book.sha256[:12]}…\n"
        "committed: the file matches `git show HEAD:<path>` in roles.builder.cwd (§10)",
    )


def _daemon_check(
    config: Config, socket_path: Path | None, daemon: dict[str, Any] | None
) -> Check:
    """Reachable is nice; unreachable is a warning, because §14 step 1 runs first."""
    if daemon is not None:
        return Check(
            "daemon",
            OK,
            f"handsd {daemon.get('version')} is answering on {daemon.get('socket')} "
            f"(pid {daemon.get('pid')})",
        )
    where = socket_path or config.server.socket
    from hands.cli import ClientError, call  # deferred: the CLI imports this module

    try:
        status = call(Path(where), "status", {}, project=config.project)
    except ClientError as exc:
        return Check(
            "daemon",
            WARN,
            f"{exc}\nnothing is wrong with the config; start it with "
            f"`handsd --project {config.project}`, or "
            f"`systemctl --user start handsd` (systemd/handsd.service)",
        )
    running = status.get("daemon", {})
    jobs = sum(1 for role in status.get("roles", {}).values() if role.get("running"))
    return Check(
        "daemon",
        OK,
        f"handsd {running.get('version')} on {where} (pid {running.get('pid')}); "
        f"{jobs} job(s) running; {status.get('inbox', {}).get('unacked')} unread inbox event(s)",
    )


def _live_check(config: Config, role: RoleConfig, *, live: bool) -> Check:
    """One real `claude -p` turn for a role — the only check that costs anything."""
    name = f"live {role.name}"
    if is_fake():
        return Check(
            name,
            SKIP,
            f"{FAKE_ENV}=1: {config.runner.claude} is a stand-in, so a turn against it "
            "would prove nothing about your subscription. Not run",
        )
    if not live:
        return Check(
            name,
            SKIP,
            "not run: `hands doctor --live` spends one turn of your subscription per "
            "role. Every other check here is free",
        )
    argv = build_argv(config, role)
    try:
        proc = subprocess.run(  # §2's invocation exactly, as argv
            argv,
            input=LIVE_PROMPT,
            cwd=str(role.cwd),
            env={**os.environ, **role.spawn_env},  # the environment a role job gets (§23)
            capture_output=True,
            text=True,
            timeout=LIVE_S,
        )
    except subprocess.TimeoutExpired:
        return Check(name, FAIL, f"no answer in {LIVE_S:.0f}s from: {' '.join(argv)}")
    except OSError as exc:
        return Check(name, FAIL, f"cannot spawn {argv[0]}: {exc}")
    result = _result_event(proc.stdout)
    if result is None:
        return Check(
            name,
            FAIL,
            f"the turn ended {proc.returncode} with no result event; §2's invocation was "
            f"`{' '.join(argv)}`: {_tail(proc.stderr)}",
        )
    first = str(result.get("result", "")).strip().splitlines()
    return Check(
        name,
        OK if not result.get("is_error") else FAIL,
        f"one turn in {role.cwd}: {first[0] if first else '(empty result)'}  "
        f"[session {result.get('session_id')}, {result.get('num_turns')} turn(s), "
        f"${result.get('total_cost_usd')}]",
    )


# ----------------------------------------------- the notification check (§11)


def wake_procedure(project: str) -> list[str]:
    """§11's notification check, for the human to run once at the laptop.

    §11 answered the wake-path question by retiring the driver's background
    wait: ntfy is the human's doorbell, and the human's `check` is the driver's.
    So the thing hands still cannot check for itself is delivery — the event has
    to arrive on a phone this process cannot see. Two events will file one
    without spending a turn (H-007): `hands pause`, which files a `stop`
    (`paused by human`) and is cleared by `hands resume` — one command, no job —
    or a **held job**, gated by `--gate` so it never runs, cleared with `hands
    deny`. The second is the only one that witnesses a real `job.held`.
    """
    return [
        "Notification check (§11) — hands cannot run this one: it ends on your phone.",
        "Run it once, by hand, on a new install.",
        "",
        "  The driver arms no wait and does not poll (§11): ntfy is your doorbell —",
        "  `stop`, `job.held`, an exhausted `max_resumes`, daemon start/crash — and",
        "  your message `check` is the driver's. So what is worth proving here is",
        "  that an event you did not ask for reaches you.",
        "",
        "  1. Subscribe your phone to the `ntfy_topic` of your config — the",
        "     ntfy app, or the topic's page in a browser — and allow its",
        "     notifications. Then put the phone down.",
        "",
        "  2. At the laptop, file an event. The simplest is a pause: it files a",
        "     `stop` event (reason `paused by human`, §11), needs no job and no",
        "     playbook, and costs nothing:",
        "",
        f"         hands --project {project} pause",
        "",
        "     Or, to file a real `job.held` instead, a gated send — held for a",
        "     human (§8), so it never starts a turn and costs nothing either:",
        "",
        f"         hands --project {project} send --role aux --context clear \\",
        '             --gate "doctor notification check" "doctor notification check — do not run"',
        "",
        "  3. The phone should show it within seconds. `hands inbox` at the laptop",
        "     shows the same event either way — what is being checked is the",
        "     delivery, not the event. Notifications are never delayed (§11).",
        "",
        "  4. Clear it, whatever the answer:",
        "",
        f"         hands --project {project} resume            # after the pause",
        f"         hands --project {project} deny <job> --reason \"doctor notification check\"",
        f"         hands --project {project} resume            # after the gated send",
        "",
        "     (after a gated send, `resume` matters only if a playbook was loaded:",
        "     an unplanned job.held also stops the pipeline, §10.)",
        "",
        "  If nothing arrived: `hands notify --test` sends one message over the same",
        "  transport and prints the HTTP status ntfy answered with, and with no",
        "  `ntfy_topic` set there is nowhere for any of it to go. Until it",
        "  works you learn you are needed by opening the Code tab and sending",
        "  `check` yourself.",
    ]


# ------------------------------------------------------------- the rendering


def render(project: str, found: list[Check], *, live: bool) -> str:
    """The readable report. `--json` prints the same facts as data."""
    width = max((len(check.name) for check in found), default=0)
    lines = [f"hands doctor — project {project}", ""]
    for check in found:
        head, *rest = check.detail.splitlines() or [""]
        lines.append(f"  {check.status:<4}  {check.name:<{width}}  {head}")
        lines += [f"  {'':<4}  {'':<{width}}  {line}" for line in rest]
    counted = {
        status: sum(1 for check in found if check.status == status)
        for status in (OK, WARN, SKIP, FAIL)
    }
    lines += [
        "",
        f"  {counted[OK]} ok, {counted[WARN]} warning(s), {counted[SKIP]} skipped, "
        f"{counted[FAIL]} failed",
    ]
    if not live and not is_fake():
        lines.append("  (the one-turn `claude -p` per role is only run by `hands doctor --live`)")
    lines += ["", *wake_procedure(project), ""]
    lines.append(
        "doctor: green" if not counted[FAIL] else f"doctor: {counted[FAIL]} check(s) failed"
    )
    return "\n".join(lines)


def report(
    project: str, path: Path | None, found: list[Check], *, live: bool
) -> dict[str, Any]:
    """The `--json` form: what the driver (and §9's MCP face) would read."""
    return {
        "project": project,
        "config": str(path) if path is not None else "",
        "live": live,
        "fake": is_fake(),
        "checks": [check.to_dict() for check in found],
        "green": not any(check.status == FAIL for check in found),
        "wake_check": wake_procedure(project),
    }


# --------------------------------------------------------------- internals


@dataclass(frozen=True)
class _Probe:
    code: int
    text: str
    timed_out: bool


def _run_probe(
    argv: list[str], *, cwd: Path | None, env: dict[str, str] | None = None
) -> _Probe | None:
    """Run a short-lived probe. None when it could not be started at all."""
    try:
        proc = subprocess.run(
            argv,
            cwd=str(cwd) if cwd else None,
            env=env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=PROBE_S,
            start_new_session=True,
        )
    except subprocess.TimeoutExpired as exc:
        return _Probe(code=-1, text=_decode(exc.stdout) + _decode(exc.stderr), timed_out=True)
    except OSError:
        return None
    return _Probe(
        code=proc.returncode, text=(proc.stdout or "") + (proc.stderr or ""), timed_out=False
    )


def _decode(raw: Any) -> str:
    if raw is None:
        return ""
    return raw.decode("utf-8", "replace") if isinstance(raw, bytes) else str(raw)


def _impossible_pid() -> int:
    """A pid no process can have: `pid_max` is exclusive on Linux."""
    try:
        return int(Path("/proc/sys/kernel/pid_max").read_text().strip())
    except (OSError, ValueError):  # pragma: no cover - not Linux
        return 4194304


def _result_event(stdout: str) -> dict[str, Any] | None:
    """The `result` event of a stream-json turn (§2), or None."""
    for line in reversed(stdout.splitlines()):
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event, dict) and event.get("type") == "result":
            return event
    return None


def _tail(text: str | None, lines: int = 3) -> str:
    if not text:
        return "(nothing on stderr)"
    return " / ".join(text.strip().splitlines()[-lines:])
