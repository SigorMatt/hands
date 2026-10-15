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

import getpass
import hashlib
import importlib.machinery
import json
import os
import re
import secrets
import shlex
import shutil
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import hands.monitor
import hands.runner
from hands.config import (
    ARCHITECT_ROLE,
    BASH_TIMEOUT_ENV,
    BG_WAIT_CEILING_ENV,
    CLONE_ENV,
    DRIVER_ROLE,
    GUARDED_ROLES,
    KITS_ENV,
    PROJECT_ENV,
    ROLE_ENV,
    Config,
    RoleConfig,
    driver_clone,
)
from hands.kit import named_paths
from hands.playbook import (
    GIT_ENV_CLEARED,
    PlaybookError,
    check_series_roles,
    load_playbook,
    playbook_path,
)
from hands.runner import build_argv
from hands.spool import Spool, SpoolError, resolve_under_roots

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
#: §30: the one interpreter a driver hook command may name before the guard's
#: path; the command driver/settings.json ships is `python3 -I <guard>`.
GUARD_INTERPRETER = "python3"
#: §37 (review 20 should-fix 1): the one option between the interpreter and the
#: guard's path — isolated mode, so the live hook ignores the user site,
#: `PYTHONPATH` and the guard's own directory as an import root.
GUARD_ISOLATED = "-I"
#: §37: what the self-test runs when the settings name no guard (the row has
#: failed already): the command the kits ship.
GUARD_COMMAND = f'{GUARD_INTERPRETER} {GUARD_ISOLATED} "$CLAUDE_PROJECT_DIR"/{GUARD_HOOK}'
#: §31: the architect's second `PreToolUse` matcher and the one argument its hook
#: command carries — `python3 -I <guard> --write`, the write judge, which the driver
#: has no equivalent of. The matcher `architect/settings.json` ships selects all
#: three tools; doctor asks that each of them be judged, however it is spelled.
WRITE_FLAG = "--write"
WRITE_TOOLS: tuple[str, ...] = ("Write", "Edit", "MultiEdit")
#: §36 (H-041): the one specifier an allow for a write tool may carry in the
#: architect's settings, and so the three allows architect/settings.json ships —
#: headless `claude -p` denies a tool no allow names, and the `--write` hook only
#: ever denies, so without them the role cannot write a byte.
KITS_SPECIFIER = "kits/**"
#: §36, §37: the one-file kit `doctor --live` has the architect write under `kits/`
#: and check, `kits/hands-doctor-live-<8 hex>`, a fresh name each run
#: (`live_kit_name`). Doctor creates the directory and removes it (the role cannot:
#: its settings deny `rm`); a path of that name already there fails the row.
LIVE_KIT_PREFIX = "hands-doctor-live-"
LIVE_FILE = "DOCTOR-LIVE.md"
LIVE_CONTENT = "doctor"
#: §36: what `hands kit check` prints for a one-file kit it read against a repository.
LIVE_KIT_CHECKED = "PASS paths: 1 files"
#: §31, §32: the push URL driver/README.md and architect/README.md give the clone.
NO_PUSH = "no_push"
#: §32 (review 15 should-fix 6), §33: tools a settings file must not allow
#: wholesale — bare, or with a specifier of wildcards alone — in a guarded role's
#: directory.
WHOLESALE_TOOLS: tuple[str, ...] = ("Bash", "Write", "Edit", "MultiEdit")
#: §33 (review 16 should-fix 4): the settings files Claude Code merges in a project
#: directory, both read — the first must exist, the second may not.
SETTINGS_FILES: tuple[str, ...] = ("settings.json", "settings.local.json")
#: §34 (review 17 should-fix 4): the user-level settings file, the third layer Claude
#: Code reads for every project directory, under `$HOME`. Optional, as the local one is.
USER_SETTINGS = Path(".claude") / "settings.json"
#: §34: a settings `env` naming one of these fails a role row. `HANDS_*` and `CLAUDE_*`
#: are §34's; `PATH` and `PYTHON*` go past it — they choose the `python3` that runs
#: the guard and what that interpreter imports before the guard's first line.
ENV_PREFIXES: tuple[str, ...] = ("HANDS_", "CLAUDE_", "PYTHON")
ENV_NAMES: tuple[str, ...] = ("PATH",)
#: §34 (review 17 should-fix 4): the keys a guard hook carries, exactly as the kits
#: ship it. `async` and `timeout` are what the reviewer probed.
GUARD_HOOK_KEYS = frozenset({"type", "command"})
#: §34 (review 17 should-fix 5): where doctor finds the guard the repository ships —
#: the copy a wheel carries (`pyproject.toml` force-includes it), then the
#: repository's own file beside the source tree `uv sync` installs from.
SHIPPED_GUARDS: tuple[Path, ...] = (
    Path(__file__).resolve().parent / "shipped" / "bash_guard.py",
    Path(__file__).resolve().parents[2] / "driver" / "hooks" / "bash_guard.py",
)
#: §33: the matchers the guard's entries carry, exactly as the kits ship them.
BASH_MATCHER = "Bash"
WRITE_MATCHER = "Write|Edit|MultiEdit"
#: §33: permission modes that let a guarded tool call past the permission prompt.
BYPASS_MODES: tuple[str, ...] = ("bypassPermissions", "acceptEdits")
#: §30: a hook command containing any of these (outside the two
#: `$CLAUDE_PROJECT_DIR` spellings) is more than `python3 -I <guard>` to a shell.
_HOOK_SHELL_CHARS = frozenset(";&|<>`()\\*?[]{}!~#$\n\r")
#: Seconds for one real `claude -p` turn. A one-line answer, not a task.
LIVE_S = 180.0
#: The live turn's prompt: one turn, no tools, and it exercises §10's VERDICT
#: contract at the same time.
LIVE_PROMPT = "Reply with exactly this line and nothing else:\nVERDICT: doctor ok\n"

#: §31: a file extension — a `.` and two or more letters or digits at the end of a
#: name. `WORKPLAN.md` has one; `e.g` does not.
_EXTENSION_RE = re.compile(r"\.[A-Za-z0-9]{2,}\Z")

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
    found += [_claude_check(config), _gh_check()]
    found += [
        _role_check(role, config.project)
        for role in config.roles.values()
        if role.name not in GUARDED_ROLES
    ]
    found += [_driver_check(config), _architect_check(config)]
    found += [_roots_check(config), _ops_check(config), _isolation_check(config)]
    found += [_playbook_check(config), _notifications_check(config), _phone_check(config)]
    found += [_go_check(config), _kit_check(config), _who_check(config)]
    found += [_topics_check(config)]
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

    §33: the row's second line says whether `[notify] ntfy_token` is set — on or
    off, never the token.
    """
    token = _token_line(config)
    if not config.notify.ntfy_topic:
        return Check(
            "notifications",
            OK,
            "notifications off: no ntfy_topic ([notify], or [server]), so handsd "
            f"notifies nobody (§11, §24)\n{token}",
        )
    return Check(
        "notifications",
        OK,
        "notifications on: handsd publishes stop, job.held, an exhausted max_resumes "
        "and daemon start/crash to ntfy_topic (§11); `hands notify --test` proves "
        f"the transport\n{token}",
    )


def _token_line(config: Config) -> str:
    """§33: `[notify] ntfy_token` on or off. The value is never part of it."""
    if config.notify.ntfy_token:
        return (
            "ntfy token on: [notify] ntfy_token is sent as a bearer on every publish "
            "and subscription (handsd, handswho, `hands notify --test`) (§33)"
        )
    return (
        "ntfy token off: no [notify] ntfy_token, so publishes and subscriptions carry "
        "no Authorization header; a server whose topics require a token refuses them (§33)"
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
        f"{config.project}`, or systemd/handswho@.service as `handswho@{config.project}`, "
        "off unless enabled (§24, §29)",
    )


#: §36: the topic keys whose names should carry the project, and the shape the
#: documented setup lines give each.
TOPIC_SHAPES = (
    ("ntfy_topic", "hands-<project>-…"),
    ("cmd_topic", "hands-<project>-cmd-…"),
    ("who_topic", "who-<project>-…"),
    ("who_cmd_topic", "whocmd-<project>-…"),
)


def _topics_check(config: Config) -> Check:
    """§36: a configured topic whose name lacks the project is a warning, never a
    failure. "Lacks" is the simplest reading: the project name is not a substring
    of the topic. The keys are named; the topics are never printed."""
    notify = config.notify
    lacking = [
        (key, shape)
        for key, shape in TOPIC_SHAPES
        if (topic := getattr(notify, key)) and config.project not in topic
    ]
    if not lacking:
        return Check(
            "topics",
            OK,
            f"every configured ntfy topic carries the project {config.project} (§36)",
        )
    keys = ", ".join(key for key, _ in lacking)
    shapes = "; ".join(f"{key} = \"{shape}\"" for key, shape in lacking)
    return Check(
        "topics",
        WARN,
        f"[notify] {keys}: the topic name does not carry the project {config.project}, "
        "so two projects' topics on one phone are told apart only by the title (§36)"
        f"\nremedy: a fresh name with the project in it — {shapes}, with "
        f"<project> = {config.project} (docs/INTEGRATION.md); hands works either way",
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
        "held job's notification carries Approve/Deny buttons with a single-use nonce; "
        "`reply <secret> <text>` resumes the architect's last session when "
        "[roles.architect] is configured (§33)"
    )
    if not notify.ntfy_topic:
        return Check(
            "phone",
            WARN,
            f"{detail}\nno ntfy_topic: the held-job notifications that carry the buttons "
            "and the answer to `status` have nowhere to go",
        )
    return Check("phone", OK, detail)


def _plainly_missing(kickoff: str, cwd: Path) -> list[str]:
    """The files `kickoff` plainly names that are not in `cwd`, in order (§31).

    The naming rule is `hands.kit.named_paths`, the one `kit check` reads a send
    prompt with, run with no kit — but doctor fails soft where that check fails
    closed, so it judges only the names that plainly are paths. A name is judged
    when it is a repository path (relative, no `..`, no `~`, no placeholder) and
    either holds a `/` or ends in an extension. Everything the rule reads as a
    bare name (`README`, `HEAD`, `TODO`, `PASS`) or as `e.g` is prose here: a
    doubtful name must not warn, a missing `meta/BUILDER-16-PROMPT.md` must.
    """
    seen: list[str] = []
    for name in named_paths(kickoff, (), cwd):
        if name in seen or name.startswith(("/", "~")) or "{" in name or "}" in name:
            continue
        if ".." in name.split("/") or not ("/" in name or _EXTENSION_RE.search(name)):
            continue
        seen.append(name)
    return [name for name in seen if not (cwd / name).is_file()]


def _go_check(config: Config) -> Check:
    """§26's `go`, on or off — `ok` or `warn`, never a failure from here.

    On means what `hands.phone` needs to accept a `go`: the command channel, and
    the playbook in force loading (by the same loader, from the builder's cwd)
    with a `[series] kickoff`. A playbook that does not load is the `playbook`
    row's failure; here it is only why `go` is off. Whether a builder job is
    running, queued or held is a moment, not an install, so it is not checked.

    §31 (review 14 should-fix 7): `go` on, with a kickoff naming a file the
    builder's cwd does not have, is the one `warn` here — the phone would send
    the builder to a brief that is not there. It is a warning and not a failure
    because nothing about the *install* is broken, and because the naming is
    read out of English (`_plainly_missing`), which no rule can do exactly.
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
    detail = (
        f"go on: `go <secret>` on cmd_topic sends the builder, clear, origin phone: "
        f"{book.kickoff}\nrefused while a builder job is running, queued or held (§27)"
    )
    cwd = config.role("builder").cwd
    missing = _plainly_missing(book.kickoff, cwd)
    if missing:
        names = ", ".join(missing)
        return Check(
            "go",
            WARN,
            f"{detail}\nthe kickoff names {names}, which "
            f"{'are' if len(missing) > 1 else 'is'} not in {cwd}: a phone `go` "
            f"would send the builder to a file that is not there (§31)",
        )
    return Check("go", OK, detail)


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


#: §35: the remedy every non-OK `gh` row names.
GH_REMEDY = "run `gh auth login` as this user"

#: `gh auth status`: "Logged in to <host> account <login>" (gh 2.40+) or
#: "Logged in to <host> as <login>" (older).
_GH_LOGIN_RE = re.compile(r"Logged in to \S+ (?:account|as) (\S+)")
_GH_SCOPES_RE = re.compile(r"Token scopes:\s*(.*)")


def _gh_run(path: str, *args: str) -> subprocess.CompletedProcess[str] | str:
    """`gh <args>`, argv only, no stdin, no prompt; the result or why it could not run."""
    env = {**os.environ, "GH_PROMPT_DISABLED": "1", "NO_COLOR": "1"}
    try:
        return subprocess.run(
            [path, *args],
            env=env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=PROBE_S,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return str(exc)


def _gh_said(text: str) -> str:
    """What `gh` printed, with every `Token:` line dropped (the token is never shown)."""
    kept = [line for line in text.splitlines() if "Token:" not in line and line.strip()]
    return _tail("\n".join(kept), 2)


def _gh_check() -> Check:
    """§35, §36: `gh --version` and `gh auth status --active --hostname github.com`
    for the user this process runs as (handsd's, when the daemon answers `doctor`):
    the login and whether the token's scopes include `repo`. Absent, unanswering,
    unauthenticated or without `repo` is a warning naming the remedy, never a
    failure — a project may commit direct. Only the `gh` on PATH is run."""
    try:
        user = getpass.getuser()
    except (KeyError, OSError):
        user = f"uid {os.getuid()}"
    path = shutil.which("gh")
    if path is None:
        return Check(
            "gh",
            WARN,
            f"no `gh` on PATH for user {user}: the pull-request flow (§35) needs it; "
            f"install the GitHub CLI and {GH_REMEDY}",
        )
    version = _gh_run(path, "--version")
    if isinstance(version, str) or version.returncode != 0:
        said = version if isinstance(version, str) else _gh_said(version.stderr)
        return Check("gh", WARN, f"{path} --version did not answer: {said}\n{GH_REMEDY}")
    lines = (version.stdout or version.stderr).strip().splitlines()
    head = lines[0] if lines else "gh (no version printed)"
    # §36: the active account of github.com only — a GHE host listed first, or a
    # bad account on another host (which makes plain `gh auth status` exit 1),
    # must not decide the row.
    status = _gh_run(path, "auth", "status", "--active", "--hostname", "github.com")
    if isinstance(status, str):
        return Check(
            "gh",
            WARN,
            f"{head}  ({path})\n`gh auth status` did not run: {status}\n{GH_REMEDY}",
        )
    # gh 2.92 prints the status on stdout; older versions printed it on stderr.
    text = f"{status.stdout or ''}\n{status.stderr or ''}"
    login = _GH_LOGIN_RE.search(text)
    if status.returncode != 0 or login is None:
        return Check(
            "gh",
            WARN,
            f"{head}  ({path})\nnot logged in as user {user}: {_gh_said(text)}\n{GH_REMEDY}",
        )
    found = _GH_SCOPES_RE.search(text)
    scopes = (
        [part.strip().strip("'\"") for part in found.group(1).split(",")] if found else []
    )
    if "repo" not in scopes:
        listed = ", ".join(scope for scope in scopes if scope) or "none reported"
        return Check(
            "gh",
            WARN,
            f"{head}  ({path})\nlogged in as {login.group(1)} (user {user}), "
            f"no `repo` scope in the token (scopes: {listed})\n"
            f"{GH_REMEDY} and grant the `repo` scope",
        )
    return Check(
        "gh",
        OK,
        f"{head}  ({path})\nlogged in as {login.group(1)} (user {user}); "
        "token scopes include `repo`",
    )


def _project_line(project: str) -> str:
    """§36 (H-043): the project a role's jobs see, whatever doctor itself inherited."""
    return (
        f"env {PROJECT_ENV}={project} (the config's project, in every job's environment; §36)"
    )


def _bash_timeout_lines(role: RoleConfig) -> str:
    """§36 (HF-006): the Bash limits a builder or aux job really runs with, one line
    each; nothing for a role hands does not set them on."""
    lines = ""
    for name in BASH_TIMEOUT_ENV:
        if name not in role.spawn_env:
            continue
        source = (
            f"set by [roles.{role.name}.env]"
            if name in role.env
            else "hands' default: a foreground gate is not moved to the background"
        )
        lines += f"\nenv {name}={role.spawn_env[name]} ({source}; §36)"
    return lines


def _role_check(role: RoleConfig, project: str) -> Check:
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
        f"{_bash_timeout_lines(role)}"
        f"\n{_project_line(project)}"
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

    §28: the row proves the wiring, and fails otherwise: the settings name the hook
    (a `PreToolUse` entry whose matcher is exactly `Bash` and whose command is
    exactly `python3 -I <.claude/hooks/bash_guard.py>`, §30, §37, with hooks not disabled),
    and that hook file self-tests green (`--selftest`, exit 0) run with the role's
    own environment, so with `HANDS_ROLE=driver`.

    §33 (review 16 should-fix 4): the settings are `.claude/settings.json` and
    `.claude/settings.local.json`, the two Claude Code merges in the project
    directory, both read (`_load_settings`); a matcher that could select a guarded
    tool must be the guard's exact one; every remote's push is disabled
    (`_push_disabled`); and the row ends with the `verified:` lines — what it read
    and found, resolved.

    §34 (review 17 should-fix 4, 5): the user-level `~/.claude/settings.json` is a
    third layer (`_load_settings`); a layer's `env` naming a variable the role
    depends on fails (`_settings_env`), as does a guard hook with keys beyond `type`
    and `command` (`_guard_hook_extras`); the guard must be the role directory's
    own file with the shipped guard's sha256 (`_guard_selftest`, `_guard_bytes`).
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
    verified: list[str] = []
    clone = _clone_lines(role, failures, warnings, verified)

    settings_path = role.cwd / ".claude" / "settings.json"
    loaded = _load_settings(role.cwd)
    if loaded.problem is None:
        verified.append(f"settings read {', '.join(loaded.read)}")
    named, problem, command = _settings_name_the_guard(loaded, role.cwd)
    if problem is None:
        settings = f"settings {settings_path} names the hook"
        verified.append(_hook_verified("Bash", BASH_MATCHER, command, named))
    else:
        settings = (
            f"settings {settings_path} does not name the hook ({problem}): copy "
            "driver/settings.json again (§28)"
        )
        failures.append(settings)
    wholesale = _settings_allow_wholesale(loaded)  # §32, §33
    if wholesale is not None:
        settings += (
            f"\nsettings {settings_path}: {wholesale}; copy driver/settings.json again"
        )
        failures.append(wholesale)
    env_problem = _settings_env(loaded)  # §34
    if env_problem is not None:
        settings += f"\nsettings: {env_problem}; remove it"
        failures.append(env_problem)
    # §33: the driver ships no write matcher; one that is there is judged as the
    # architect's is, so a write hook that is not the guard fails here too.
    write_named, write_problem, _ = _settings_name_the_write_guard(
        loaded, role.cwd, required=False
    )
    if write_problem is None:
        write_problem = _same_guard(named, write_named)
    if write_problem is not None:
        settings += f"\nwrite matcher ({write_problem}): copy driver/settings.json again (§33)"
        failures.append(write_problem)

    # §29: the self-test runs on the file the settings name, not on a default path;
    # only when they name none is the default the one reported.
    hook = named if named is not None else role.cwd / GUARD_HOOK
    mode = f"{ROLE_ENV}={role.spawn_env[ROLE_ENV]}"
    guard, green = _guard_selftest(
        hook,
        command=command if named is not None else None,
        cwd=role.cwd,
        env={**os.environ, **role.spawn_env},
        mode=mode,
        words="role mode",
    )
    if not green:
        failures.append(guard)

    detail = (
        f"{role.cwd}  model {role.model}; permission_flags (none)"
        f"\n{_project_line(config.project)}"
        f"\n{clone}\n{settings}\n{guard}"
        f"\nguard mode: role mode ({mode} in every driver-role job's environment; §27)"
        + "".join(f"\nverified: {line}" for line in verified)
    )
    status = FAIL if failures else WARN if warnings else OK
    return Check(name, status, detail)


def _architect_check(config: Config) -> Check:
    """§31: the architect role — cwd, its clone, its kits directory, both hook
    matchers and the guard's mode — and no bypass.

    Written as closely to `_driver_check` as the difference allows, and reads the
    same way in the report. Two things the driver has no equivalent of:

    - `kits/` beside the clone. The runner sets `HANDS_KITS` to `<cwd>/kits`;
      §32 (review 15 should-fix 6) has the row check that it exists and resolves
      under the cwd. §33 (review 16 should-fix 2, 3): it is not a symlink (a link
      to `.claude` put the role's own settings under it), nothing under it is one
      (the guard refuses `cp` and `mv` while one is), and no path this row checks —
      `.claude`, its hooks directory, either settings file, either guard file, the
      clone — resolves under it, where a Write call could change it.
    - a **second** `PreToolUse` matcher: exactly `Write|Edit|MultiEdit`, running the
      guard with `--write` (§31). Every entry whose matcher could select a writing
      tool must be that one, running exactly `python3 -I <guard> --write`, because a
      write hook that is not the guard is the architect writing wherever it likes.

    §32 adds, to both this row and the driver's where they share code: the clone's
    push URL is disabled (`_push_disabled`); every hook under `PreToolUse` is a
    command hook; no permission setting allows a guarded tool wholesale
    (`_settings_allow_wholesale`); and here, both matchers run the same guard file,
    the one self-tested with `HANDS_ROLE=architect` and `HANDS_KITS` set.
    """
    name = f"role {ARCHITECT_ROLE}"
    role = config.roles.get(ARCHITECT_ROLE)
    if role is None:
        return Check(
            name,
            OK,
            "no [roles.architect]: no consult can start an architect role (§31); the "
            "architect the human talks to on the phone is unaffected",
        )
    if role.permission_flags:
        return Check(
            name,
            FAIL,
            f"{role.cwd}  permission_flags {role.permission_flags}\n§31: the architect role "
            "runs with permission_flags empty, so settings.json and the Bash guard are "
            "the law; remove it from [roles.architect]",
        )
    if not role.cwd.is_dir():
        return Check(name, FAIL, f"cwd {role.cwd} does not exist; §31 [roles.architect] cwd")
    warnings: list[str] = []
    failures: list[str] = []
    verified: list[str] = []
    clone = _clone_lines(role, failures, warnings, verified)

    # The runner's own expression (`hands.runner.job_env`), so the row names the
    # path the job really gets as `HANDS_KITS`.
    kits_dir = role.cwd / "kits"
    kits, kits_ok = _kits_line(kits_dir, role.cwd)
    if kits_ok:
        verified.append(
            f"kits realpath {os.path.realpath(kits_dir)}, not a symlink, and no symlink "
            "or hard link under it"
        )
    else:
        failures.append(kits)

    settings_path = role.cwd / ".claude" / "settings.json"
    loaded = _load_settings(role.cwd)
    if loaded.problem is None:
        verified.append(f"settings read {', '.join(loaded.read)}")
    named, problem, command = _settings_name_the_guard(loaded, role.cwd)
    if problem is None:
        settings = f"settings {settings_path} names the hook"
        verified.append(_hook_verified("Bash", BASH_MATCHER, command, named))
    else:
        settings = (
            f"settings {settings_path} does not name the hook ({problem}): copy "
            "architect/settings.json again (§31)"
        )
        failures.append(settings)
    wholesale = _settings_allow_wholesale(loaded)  # §32, §33
    if wholesale is not None:
        settings += (
            f"\nsettings {settings_path}: {wholesale}; copy architect/settings.json again"
        )
        failures.append(wholesale)
    env_problem = _settings_env(loaded)  # §34
    if env_problem is not None:
        settings += f"\nsettings: {env_problem}; remove it"
        failures.append(env_problem)

    allows = _settings_write_allows(loaded)  # §36 (H-041)
    if allows is None:
        verified.append(
            "write allow: " + ", ".join(f"{tool}({KITS_SPECIFIER})" for tool in WRITE_ALLOWS)
        )
    else:
        settings += f"\nsettings: {allows}; copy architect/settings.json again (§36)"
        failures.append(allows)

    write_named, write_problem, write_command = _settings_name_the_write_guard(
        loaded, role.cwd, required=True
    )
    if write_problem is None:
        write_problem = _same_guard(named, write_named)  # §32 (c)
    if write_problem is None:
        write = f"write matcher: {', '.join(WRITE_TOOLS)} run the guard with {WRITE_FLAG}"
        verified.append(_hook_verified("write", WRITE_MATCHER, write_command, write_named))
    else:
        write = (
            f"write matcher ({write_problem}): every PreToolUse hook for "
            f"{', '.join(WRITE_TOOLS)} must be exactly `{GUARD_INTERPRETER} {GUARD_ISOLATED} "
            f"<path to {GUARD_HOOK}> {WRITE_FLAG}` under the matcher {WRITE_MATCHER!r}, and all "
            "three must be judged; copy architect/settings.json again (§31, §33)"
        )
        failures.append(write)

    # §33: nothing this row checks may resolve under kits, where the role writes.
    checked = [
        role.cwd / ".claude",
        role.cwd / ".claude" / "hooks",
        *(role.cwd / ".claude" / file for file in SETTINGS_FILES),
        *(path for path in (named, write_named, driver_clone(role.cwd)) if path is not None),
    ]
    exposed = [
        path for path in checked
        if (path.exists() or path.is_symlink()) and _under_realpath(path, kits_dir)
    ]  # fmt: skip
    if kits_dir.exists() and exposed:
        inside = (
            f"{exposed[0]} resolves to {os.path.realpath(exposed[0])}, under kits "
            f"{os.path.realpath(kits_dir)}: the architect's writes would reach it (§33)"
        )
        kits += f"\n{inside}"
        failures.append(inside)

    # §29: the self-test runs on the file the settings name, not on a default path.
    hook = named if named is not None else role.cwd / GUARD_HOOK
    mode = f"{ROLE_ENV}={role.spawn_env[ROLE_ENV]}"
    guard, green = _guard_selftest(
        hook,
        command=command if named is not None else None,
        cwd=role.cwd,
        env={**os.environ, **role.spawn_env, KITS_ENV: str(kits_dir)},
        mode=mode,
        words="architect mode",
    )
    if not green:
        failures.append(guard)

    detail = (
        f"{role.cwd}  model {role.model}; permission_flags (none)"
        f"\n{_project_line(config.project)}"
        f"\n{clone}\n{kits}\n{settings}\n{write}\n{guard}"
        f"\nguard mode: architect mode ({mode} in every architect-role job's environment; "
        f"§31), and every write confined to {KITS_ENV}={kits_dir}"
        + "".join(f"\nverified: {line}" for line in verified)
    )
    status = FAIL if failures else WARN if warnings else OK
    return Check(name, status, detail)


def _clone_lines(
    role: RoleConfig, failures: list[str], warnings: list[str], verified: list[str]
) -> str:
    """The clone's lines of a role row (§29, §31, §32, §33, §36), shared by both rows."""
    cwd = role.cwd
    found = driver_clone(cwd)  # §29, §31: the same path the job gets as HANDS_CLONE
    if found is None:
        clone = f"no clone: neither {cwd / 'repo'} nor {cwd} is a git repository"
        warnings.append(clone)
        return clone
    push, disabled, shown = _push_disabled(found)
    if disabled:
        verified.append(shown)
    else:
        failures.append(push)
    return f"clone {found}\n{_head_line(found, role.branch)}\n{push}"


def _head_line(clone: Path, branch: str) -> str:
    """§36 (H-042): the clone's HEAD against `origin/<branch>`, as last fetched.

    Read from the clone's own refs: doctor does not fetch. Informational — the
    runner fetches and checks out `origin/<branch>` before every job, and a clone
    that cannot be advanced fails that job, so the row's status does not change.
    """
    def short(ref: str) -> str | None:
        proc = _git(clone, "rev-parse", "--verify", "-q", f"{ref}^{{commit}}")
        if isinstance(proc, str) or proc.returncode != 0:
            return None
        return proc.stdout.strip()[:12] or None

    head = short("HEAD") or "(no commit)"
    origin = short(f"refs/remotes/origin/{branch}")
    if origin is None:
        compared = f"clone HEAD {head}, origin/{branch} not fetched"
    elif origin == head:
        compared = f"clone HEAD {head} at origin/{branch} as last fetched"
    else:
        compared = f"clone HEAD {head}, origin/{branch} {origin} as last fetched"
    return (
        f"{compared} (the runner fetches origin and checks out origin/{branch} "
        "before every job; §36)"
    )


def _kits_line(kits_dir: Path, cwd: Path) -> tuple[str, bool]:
    """§32, §33: the architect's kits line, and whether it holds.

    `kits` exists, is not a symlink, resolves under the cwd, and nothing under it
    (walked, links not followed) is a symlink or (§36) a hard-linked regular file.
    """
    real, base = os.path.realpath(kits_dir), os.path.realpath(cwd)
    if kits_dir.is_symlink():
        where = "" if _under_realpath(kits_dir, cwd) else f", not under {base}"
        return (
            f"kits {kits_dir} is a symlink resolving to {real}{where}: {KITS_ENV} must be "
            "a plain directory under the role's cwd, and the guard refuses every "
            "architect write through a link (§32, §33)",
            False,
        )
    if not kits_dir.is_dir():
        return (
            f"no kits directory at {kits_dir}: {KITS_ENV} names it, and §32 asks that it "
            "exist under the cwd; `mkdir -p` it (architect/README.md)",
            False,
        )
    if not _under_realpath(kits_dir, cwd):
        return (
            f"kits {kits_dir} resolves to {real}, not under {base}: {KITS_ENV} must be a "
            "directory under the role's cwd (§32)",
            False,
        )
    found = _kits_walk(str(kits_dir))
    if found is not None:
        path, why = found
        if why is not None and why.startswith(_HARDLINK):
            return (
                f"kits {kits_dir} holds a hard link, {path} ({why}): the guard refuses cp "
                "and mv until it is gone, since cp onto it writes into the file the other "
                "name shares, and nothing the architect runs made it (§36)",
                False,
            )
        if why is None:
            return (
                f"kits {kits_dir} holds a symlink, {path} -> {os.readlink(path)}: the "
                "guard refuses cp and mv until it is gone, and nothing the architect "
                "runs made it (§33)",
                False,
            )
        return (
            f"kits {kits_dir}: {path} {why}, so it cannot be shown to hold no symlink: the "
            "guard refuses cp and mv until it can be walked (§34)",
            False,
        )
    return f"kits {kits_dir}", True


_HARDLINK = "a regular file with"


def _kits_walk(kits: str) -> tuple[str, str | None] | None:
    """§34 (review 17 should-fix 3): the guard's `kits_symlink` walk, the same steps
    (`driver/hooks/bash_guard.py` is a standalone script doctor cannot import): the
    first path under `kits` that is a symlink (`(path, None)`), a regular file with
    a link count above one (§36, review 18 should-fix 4: `(path, "a regular file
    with N hard links")`), or that the walk cannot judge (`(path, why)`), or None.
    tests/test_doctor.py runs both walks over the same trees.

    `os.lstat` on every path from the root down decides what each one is; a
    directory that cannot be listed (mode 0111) and a path that cannot be stat'ed
    are returned, never skipped, so read permission cannot hide a link. A missing
    root holds nothing, as the guard reads it; the caller has already failed it.
    """
    pending = [kits]
    while pending:
        top = pending.pop()
        try:
            info = os.lstat(top)
            mode, links = info.st_mode, info.st_nlink
        except FileNotFoundError:
            if top == kits:
                return None
            return top, "cannot be stat'ed: it vanished during the walk"
        except OSError as exc:
            return top, f"cannot be stat'ed: {exc.strerror}"
        if stat.S_ISLNK(mode):
            return top, None
        if stat.S_ISREG(mode) and links > 1:
            return top, f"{_HARDLINK} {links} hard links"
        if not stat.S_ISDIR(mode):
            continue
        try:
            names = os.listdir(top)
        except OSError as exc:
            return top, f"is a directory that cannot be listed: {exc.strerror}"
        pending.extend(os.path.join(top, name) for name in sorted(names, reverse=True))
    return None


def _hook_verified(kind: str, matcher: str, command: str | None, named: Path | None) -> str:
    """§33: one `verified:` line for a guard hook — matcher, command, resolved file."""
    real = os.path.realpath(named) if named is not None else "(none)"
    return f"{kind} hook, matcher {matcher!r}, runs {command!r} (guard realpath {real})"


def _same_guard(named: Path | None, write_named: Path | None) -> str | None:
    """§32 (c): both matchers name *the* guard — one file, the one self-tested."""
    if (
        named is not None
        and write_named is not None
        and os.path.realpath(named) != os.path.realpath(write_named)
    ):
        return (
            f"the Bash hook runs {named} and the write hook runs {write_named}: both must "
            "run the same guard file"
        )
    return None


def _guard_selftest(
    hook: Path,
    *,
    command: str | None,
    cwd: Path,
    env: dict[str, str],
    mode: str,
    words: str,
) -> tuple[str, bool]:
    """`<hook> --selftest`, run in the role's own environment (§28, §29, §31): the
    `guard` lines of the row, and whether it was green.

    The one place the guard's self-test is run, so the driver's row and the
    architect's cannot drift apart in how hard they look.

    §34 (review 17 should-fix 5): an exit 0 is not the guard. `hook` is the exact
    path the settings name; it must be the role directory's own guard
    (`<cwd>/.claude/hooks/bash_guard.py`, compared by realpath), so an absolute
    command path elsewhere fails, and its bytes must hash (sha256) to the guard the
    repository ships (`SHIPPED_GUARDS`), with both hashes printed when they differ.
    The self-test still runs on that same path, whatever the hashes say.

    §37 (review 20 should-fix 1): the self-test is the hook `command` exactly as the
    settings spell it, plus `--selftest`, run as Claude Code runs a hook — through
    `/bin/sh -c` in `cwd`, with `CLAUDE_PROJECT_DIR` naming `cwd` — not a command of
    doctor's own (the command the kits ship when the settings name none). The
    command is `python3 -I …` (`_guard_command_path`), so the guard and the standard
    library run, not a module on `PYTHONPATH`. And any importable module or package
    beside the guard (`_beside_the_guard`) fails the row, named.
    """
    if not hook.is_file():
        return (
            f"no guard at {hook}: nothing narrows the role's Bash calls (driver/README.md)",
            False,
        )
    lines = [f"guard {hook}"]
    green = True
    own = cwd / GUARD_HOOK
    if os.path.realpath(hook) != os.path.realpath(own):
        lines.append(
            f"the settings run {hook}, not the role directory's guard {own}: a hook "
            "command naming a guard elsewhere fails the row (§34)"
        )
        green = False
    same, said_bytes = _guard_bytes(hook)
    lines.append(said_bytes)
    green = green and same
    beside = _beside_the_guard(hook)
    if beside is not None:
        lines.append(beside)
        green = False
    spelled = command if command is not None else GUARD_COMMAND
    probe = _run_probe(
        ["/bin/sh", "-c", f"{spelled} --selftest"],
        cwd=cwd,
        env={**env, "CLAUDE_PROJECT_DIR": str(cwd)},
    )
    if probe is not None and probe.code == 0 and not probe.timed_out:
        lines.append(f"self-test green in {words} ({mode})")
        return "\n".join(lines), green
    said = (
        "could not be run" if probe is None
        else "timed out" if probe.timed_out
        else f"exit {probe.code}"
    )
    tail = "" if probe is None else "\n" + "\n".join(probe.text.strip().splitlines()[-5:])
    lines.append(
        f"self-test in {words} ({mode}) is not green ({said}): "
        f"copy driver/hooks/bash_guard.py again (§28){tail}"
    )
    return "\n".join(lines), False


def _beside_the_guard(hook: Path) -> str | None:
    """§37 (review 20 should-fix 1): what sits beside the guard that Python could
    import in its place — the first entry of the guard's directory (as the settings
    name it and as it resolves) that is a module file (any suffix
    `importlib.machinery.all_suffixes()` lists: `.py`, `.pyc`, an extension module)
    or a package directory (one holding an `__init__` module), other than the guard
    itself — named in the line saying so, or None. A directory that cannot be listed
    is returned as what fails: the row cannot say it holds nothing."""
    suffixes = tuple(importlib.machinery.all_suffixes())
    real = os.path.realpath(hook)
    for folder in dict.fromkeys((str(hook.parent), os.path.dirname(real))):
        try:
            names = sorted(os.listdir(folder))
        except OSError as exc:
            return (
                f"the guard's directory {folder} cannot be listed ({exc.strerror}), so "
                "what Python could import beside the guard is not known (§37)"
            )
        for name in names:
            path = os.path.join(folder, name)
            if os.path.realpath(path) == real:
                continue
            package = os.path.isdir(path) and any(
                os.path.exists(os.path.join(path, "__init__" + suffix)) for suffix in suffixes
            )
            if package or (not os.path.isdir(path) and name.endswith(suffixes)):
                kind = "a package directory" if package else "a module file"
                return (
                    f"{path} sits beside the guard {hook}: {kind} there could be imported in "
                    "the guard's place; remove it, the hook directory holds the guard alone "
                    "(§37)"
                )
    return None


def _guard_bytes(hook: Path) -> tuple[bool, str]:
    """§34: whether `hook`'s bytes are the guard the repository ships, and the line
    saying so — both sha256 on a mismatch, or why either could not be read."""
    try:
        named = hashlib.sha256(hook.read_bytes()).hexdigest()
    except OSError as exc:
        return False, f"guard {hook} cannot be read to hash it ({type(exc).__name__}) (§34)"
    shipped = next((path for path in SHIPPED_GUARDS if path.is_file()), None)
    if shipped is None:
        return False, (
            f"guard {hook} sha256 {named}; the guard the repository ships is not found "
            f"({', '.join(str(path) for path in SHIPPED_GUARDS)}), so it is not known to "
            "be that guard (§34)"
        )
    try:
        want = hashlib.sha256(shipped.read_bytes()).hexdigest()
    except OSError as exc:
        return False, f"the shipped guard {shipped} cannot be read ({type(exc).__name__}) (§34)"
    if named != want:
        return False, (
            f"guard {hook} sha256 {named} is not the guard the repository ships, "
            f"{shipped} sha256 {want}: copy driver/hooks/bash_guard.py again (§34)"
        )
    return True, f"guard sha256 {named}, the same bytes as {shipped} (§34)"


@dataclass(frozen=True)
class _Settings:
    """§33: the settings files of a role's directory, as Claude Code merges them.

    `loaded` is each file that exists, with its JSON object; `read` names every
    file for the `verified:` line (`<path>`, `<path> -> <realpath>`, or `<path>
    (absent)`); `problem` is why they cannot be judged, or None.
    """

    loaded: list[tuple[Path, dict[str, Any]]]
    read: list[str]
    problem: str | None


def _load_settings(cwd: Path) -> _Settings:
    """`<cwd>/.claude/settings.json` (required), `settings.local.json` (optional) and,
    §34, the user-level `~/.claude/settings.json` (optional), each a JSON object
    (§28, §33, §34). An unreadable optional file is a problem, not an absence: Claude
    Code would still try to merge it. The user-level file is read once when the
    role's cwd is the home directory itself."""
    loaded: list[tuple[Path, dict[str, Any]]] = []
    read: list[str] = []
    layers = [cwd / ".claude" / file for file in SETTINGS_FILES]
    user = Path.home() / USER_SETTINGS
    if all(os.path.abspath(user) != os.path.abspath(layer) for layer in layers):
        layers.append(user)
    for index, path in enumerate(layers):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            if index == 0:
                return _Settings(loaded, read, "no such file")
            read.append(f"{path} (absent)")
            continue
        except (OSError, ValueError) as exc:
            return _Settings(loaded, read, f"{path} is not readable JSON: {type(exc).__name__}")
        if not isinstance(data, dict):
            return _Settings(loaded, read, f"{path} is not a JSON object")
        real = os.path.realpath(path)
        read.append(str(path) if real == str(path) else f"{path} -> {real}")
        loaded.append((path, data))
    return _Settings(loaded, read, None)


def _pretooluse(settings: _Settings) -> tuple[list[tuple[Path, Any]] | None, str | None]:
    """The `hooks.PreToolUse` entries of every settings file, each with its file, or
    None and why there are none to judge (§28, §30, §33).

    §33: `"disableAllHooks"` set to anything but false in either file runs no hook;
    an entry that is not an object, a `hooks` that is not a list, and any hook
    anywhere under `PreToolUse` that is not a command hook (`type: prompt`, `http`,
    none) fail, whatever its matcher — a second answer to a tool call, not the
    guard's.
    """
    if settings.problem is not None:
        return None, settings.problem
    entries: list[tuple[Path, Any]] = []
    for path, data in settings.loaded:
        if data.get("disableAllHooks") not in (None, False):
            return None, f'"disableAllHooks" is set in {path}, so no hook runs'
        hooks = data.get("hooks")
        if hooks is None:
            continue
        found = hooks.get("PreToolUse") if isinstance(hooks, dict) else None
        if found is None and isinstance(hooks, dict):
            continue
        if not isinstance(found, list):
            return None, f"hooks.PreToolUse in {path} is not a list"
        for entry in found:
            if not isinstance(entry, dict) or not isinstance(entry.get("hooks"), list):
                return None, f"a PreToolUse entry in {path} is not a matcher and a hook list"
            for hook in entry["hooks"]:
                other = _not_a_command_hook(hook)
                if other is not None:
                    return None, f"{other} (in {path})"
            entries.append((path, entry))
    if not entries:
        return None, "no hooks.PreToolUse"
    return entries, None


def _settings_name_the_guard(
    settings: _Settings, cwd: Path
) -> tuple[Path | None, str | None, str | None]:
    """The hook file the settings wire as the `PreToolUse` command hook for `Bash`
    (§28, §29, §30), None, and its command; or None, why not, and None.

    §30: the command must run the file *as the guard*. `shlex` splits it into
    exactly three words, `python3` (the interpreter driver/settings.json ships),
    `-I` (§37) and a path that is `.claude/hooks/bash_guard.py` or ends in
    `/.claude/hooks/bash_guard.py`, with `$CLAUDE_PROJECT_DIR` (or
    `${CLAUDE_PROJECT_DIR}`) standing for `cwd` and a relative path read against
    `cwd`, where Claude Code runs the hook. Any other `$`, a shell operator,
    redirection, glob, escape or newline anywhere in the command, a further
    argument (`--selftest`), or another interpreter does not run the guard.

    §31 (review 14 should-fix 3): *every* `PreToolUse` hook for `Bash` is judged.
    §33 (review 16 should-fix 4): "for `Bash`" is read broadly — every entry whose
    matcher *could* select Bash (`_may_select`: absent, empty, `*`, an alternative
    equal to `Bash` in any case, or a regular expression that finds `Bash`
    unanchored and case-insensitively, or one that does not compile) — and such an
    entry's matcher must be exactly `Bash`, the shipped one. With several Bash
    hooks that all run the guard file, the first is the one self-tested."""
    entries, unreadable = _pretooluse(settings)
    if entries is None:
        return None, unreadable, None
    guards: list[tuple[Path, str]] = []
    offenders: list[str] = []
    for path, entry in entries:
        matcher = entry.get("matcher")
        if not _may_select(matcher, "Bash"):
            continue
        if matcher != BASH_MATCHER:
            return None, (
                f"the matcher {matcher!r} in {path} could select Bash and is not exactly "
                f"{BASH_MATCHER!r}: the guard's entry is the only one that selects Bash, "
                "under that matcher (§33)"
            ), None
        for hook in entry["hooks"]:
            extra = _guard_hook_extras(hook, path)
            if extra is not None:
                return None, extra, None
            command: str = hook["command"]
            named = _guard_command_path(command, cwd)
            if named is None:
                offenders.append(command)
            else:
                guards.append((named, command))
    if offenders:
        return None, (
            f"the hook command {offenders[0]!r} does not run the guard: every PreToolUse "
            f"Bash hook must be exactly `{GUARD_INTERPRETER} {GUARD_ISOLATED} <path to "
            f"{GUARD_HOOK}>` (§31, §37)"
        ), None
    if not guards:
        return None, f"no PreToolUse command hook for Bash runs {GUARD_HOOK}", None
    if len({os.path.realpath(guard) for guard, _ in guards}) > 1:
        return None, (
            "the PreToolUse Bash hooks run more than one guard file (§32: the same guard file)"
        ), None
    return guards[0][0], None, guards[0][1]


def _settings_name_the_write_guard(
    settings: _Settings, cwd: Path, *, required: bool
) -> tuple[Path | None, str | None, str | None]:
    """§31: the architect's second matcher — exactly `Write|Edit|MultiEdit`, running
    `python3 -I <guard> --write` — the guard file it names, None, and its command; or
    None, why not, and None.

    The Bash rule of `_settings_name_the_guard`, applied to the tools that write:
    every entry whose matcher could select one of `WRITE_TOOLS` (`_may_select`)
    must carry exactly the matcher `Write|Edit|MultiEdit` (§33) and run exactly the
    guard with `--write`. With `required` (the architect) there must be one; without
    (the driver, whose settings ship none) none is fine, and one that is there is
    judged the same way.
    """
    entries, unreadable = _pretooluse(settings)
    if entries is None:
        return None, unreadable, None
    guards: list[tuple[Path, str]] = []
    offenders: list[str] = []
    for path, entry in entries:
        matcher = entry.get("matcher")
        selects = [tool for tool in WRITE_TOOLS if _may_select(matcher, tool)]
        if not selects:
            continue
        if matcher != WRITE_MATCHER:
            return None, (
                f"the matcher {matcher!r} in {path} could select {', '.join(selects)} and is "
                f"not exactly {WRITE_MATCHER!r} (§33)"
            ), None
        for hook in entry["hooks"]:
            extra = _guard_hook_extras(hook, path)
            if extra is not None:
                return None, extra, None
            command: str = hook["command"]
            named = _guard_command_path(command, cwd, flag=WRITE_FLAG)
            if named is None:
                offenders.append(command)
            else:
                guards.append((named, command))
    if offenders:
        return None, (
            f"the hook command {offenders[0]!r} does not run the guard with {WRITE_FLAG}"
        ), None
    if not guards:
        if not required:
            return None, None, None
        return None, (
            f"no PreToolUse command hook for {', '.join(WRITE_TOOLS)} runs {GUARD_HOOK} "
            f"{WRITE_FLAG}"
        ), None
    if len({os.path.realpath(guard) for guard, _ in guards}) > 1:
        return None, "the write hooks run more than one guard file (§32: the same guard file)", None
    return guards[0][0], None, guards[0][1]


def _guard_hook_extras(hook: dict[str, Any], path: Path) -> str | None:
    """§34 (review 17 should-fix 4): a hook under a matcher that selects a guarded
    tool carries exactly `type` and `command`, as the kits ship it — why not, or
    None. Past §34's letter, which names the command: `"async": true` or a short
    `"timeout"` changes whether the guard's answer arrives before the call runs."""
    extra = sorted(set(hook) - GUARD_HOOK_KEYS)
    if not extra:
        return None
    return (
        f"the guard's hook in {path} carries {', '.join(repr(key) for key in extra)}: a "
        f"guard hook is exactly {sorted(GUARD_HOOK_KEYS)}, as the kits ship it (§34)"
    )


def _not_a_command_hook(hook: Any) -> str | None:
    """§32 (review 15 should-fix 6), §33: a hook under `PreToolUse` that is not a
    command hook (`type: prompt`, `http`, none) is a second answer to a tool call,
    and not the guard's; why, or None for a command hook."""
    if (
        isinstance(hook, dict)
        and hook.get("type") == "command"
        and isinstance(hook.get("command"), str)
    ):
        return None
    kind = hook.get("type") if isinstance(hook, dict) else None
    return (
        f"a {kind!r} hook is not a command hook running the guard: every hook under "
        "PreToolUse must be a command hook (§32, §33)"
    )


def _settings_env(settings: _Settings) -> str | None:
    """§34 (review 17 should-fix 4): a settings layer whose `env` sets a variable the
    role depends on — why, or None.

    Claude Code applies a settings `env` to the session it starts, and the guard
    reads `HANDS_ROLE`, `HANDS_KITS`, `HANDS_CLONE`, `HANDS_CONSULT_ROLE` and
    `HANDS_PROJECT` from its environment, and runs as `python3
    "$CLAUDE_PROJECT_DIR"/…`. Doctor cannot tell which `CLAUDE_*` variable Claude Code
    passes to a hook or what it changes there, so any `HANDS_*` or `CLAUDE_*` name
    fails — doubt fails the row, as `_may_select` reads matchers — and so do `PATH`
    and `PYTHON*` (`ENV_PREFIXES`, `ENV_NAMES`). An `env` that is not an object is
    not judged and fails too. A name set to the value the runner gives it still
    fails: a settings file cannot know the role's per-directory values."""
    for path, data in settings.loaded:
        if "env" not in data:
            continue
        env = data["env"]
        if not isinstance(env, dict):
            return f"env in {path} is not an object, so what it sets is not known (§34)"
        for name in sorted(env):
            if name in ENV_NAMES or name.startswith(ENV_PREFIXES):
                return (
                    f"env in {path} sets {name}={env[name]!r}: a settings env must not set "
                    f"{', '.join(prefix + '*' for prefix in ENV_PREFIXES)} or "
                    f"{', '.join(ENV_NAMES)}, which the role and its guard depend on (§34)"
                )
    return None


#: §33: an allow rule — a tool name and an optional `(specifier)`.
_ALLOW_RULE = re.compile(r"\s*(\w+)\s*(?:\((.*)\))?\s*", re.DOTALL)


def _allows_wholesale(entry: str) -> bool:
    """§32, §33: an allow entry naming one of `WHOLESALE_TOOLS` (in any case) bare,
    or with a specifier that holds no letter or digit — `Tool(*)`, `Write(**)`,
    `Edit(/**)`, `Edit(~/**)`, `Bash(*:*)`, `Bash(:*)` — which names no command or
    path, only wildcards and roots."""
    match = _ALLOW_RULE.fullmatch(entry)
    if match is None:
        return False
    tool, specifier = match.group(1), match.group(2)
    if tool.lower() not in {name.lower() for name in WHOLESALE_TOOLS}:
        return False
    return specifier is None or re.search(r"[A-Za-z0-9]", specifier) is None


#: §36: the order the three write allows are named in, as architect/settings.json
#: ships them.
WRITE_ALLOWS: tuple[str, ...] = ("Edit", "Write", "MultiEdit")


def _settings_write_allows(settings: _Settings) -> str | None:
    """§36 (H-041): the architect's allows for the write tools, over every settings
    layer the row reads (Claude Code merges their allow lists): `Edit(kits/**)`,
    `Write(kits/**)` and `MultiEdit(kits/**)` must each be there, and an allow for
    any of the three tools — its name compared in any case — must carry exactly
    that specifier, spelled exactly so. Why not, or None."""
    if settings.problem is not None:
        return None  # the hook check already fails the row on it
    found: set[str] = set()
    for path, data in settings.loaded:
        permissions = data.get("permissions")
        allow = permissions.get("allow") if isinstance(permissions, dict) else None
        for entry in allow if isinstance(allow, list) else []:
            match = _ALLOW_RULE.fullmatch(entry) if isinstance(entry, str) else None
            if match is None or match.group(1).lower() not in {t.lower() for t in WRITE_TOOLS}:
                continue
            if match.group(1) in WRITE_TOOLS and entry == f"{match.group(1)}({KITS_SPECIFIER})":
                found.add(match.group(1))
                continue
            return (
                f"permissions.allow in {path} names {entry!r}: an allow for "
                f"{', '.join(WRITE_ALLOWS)} names {KITS_SPECIFIER} and nothing else (§36)"
            )
    missing = [f"{tool}({KITS_SPECIFIER})" for tool in WRITE_ALLOWS if tool not in found]
    if missing:
        return (
            f"permissions.allow has no {', no '.join(missing)}: headless claude -p denies "
            "a tool no allow names, so the role cannot write under kits/ (§36)"
        )
    return None


def _settings_allow_wholesale(settings: _Settings) -> str | None:
    """§32 (review 15 should-fix 6), §33 (review 16 should-fix 4): the permission
    settings, in either settings file, that let a guarded role past its settings
    wholesale — `permissions.defaultMode` of `bypassPermissions` or `acceptEdits`,
    or an allow entry `_allows_wholesale` reads as a guarded tool with no command or
    path named — why, or None. A narrower allow (`Bash(git log:*)`) is the settings'
    own business, and the guard still judges every call."""
    for path, data in settings.loaded:
        permissions = data.get("permissions")
        if not isinstance(permissions, dict):
            continue
        mode = permissions.get("defaultMode")
        if mode in BYPASS_MODES:
            return f"permissions.defaultMode is {mode!r} in {path} (§32, §33)"
        allow = permissions.get("allow")
        for entry in allow if isinstance(allow, list) else []:
            if isinstance(entry, str) and _allows_wholesale(entry):
                return (
                    f"permissions.allow in {path} names {entry!r}, allowing the tool "
                    "wholesale (§32, §33)"
                )
    return None


def _git(clone: Path, *args: str) -> subprocess.CompletedProcess[str] | str:
    """`git -C <clone> <args>` with the git variables cleared; the result, or why it
    could not run."""
    env = {name: value for name, value in os.environ.items() if name not in GIT_ENV_CLEARED}
    try:
        return subprocess.run(
            ["git", "-C", str(clone), *args],
            env=env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=PROBE_S,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return str(exc)


def _said(proc: subprocess.CompletedProcess[str] | str) -> str:
    """What a `_git` call that did not answer said."""
    if isinstance(proc, str):
        return proc
    return _tail(proc.stderr, 1) or f"exit {proc.returncode}"


#: §33: the config keys that choose where a plain `git push` goes.
_PUSH_KEYS = r"^(remote\.pushdefault|branch\..*\.(pushremote|remote))$"


def _push_disabled(clone: Path) -> tuple[str, bool, str]:
    """§31, §32, §33 (review 16 should-fix 4): no push from the clone reaches a
    repository. The row's line, whether that holds, and the `verified:` line.

    The rule: `origin` exists; every remote git lists (`git remote`) has push URLs
    (`git remote get-url --push --all <remote>`) that are each a plain word — no
    `/`, `\\`, `:` or `@`, so no URL, host or path — naming nothing in the clone's
    directory, as `no_push` is (driver/README.md and architect/README.md set it
    with `git remote set-url --push origin no_push`); and `remote.pushDefault`,
    `branch.<b>.pushRemote` and `branch.<b>.remote`, where set, each name one of
    those remotes (or `.`, the clone itself), since a name that is not a remote is
    pushed to as a URL or a path. An unset push URL prints the fetch URL, which is
    not a plain word. Git not answering is not known to be disabled. A
    `pushInsteadOf` rewrite is not read: git ignores it for an explicit push URL."""
    fix = f"set it with `git -C {clone} remote set-url --push <remote> {NO_PUSH}` (§31, §32, §33)"
    listed = _git(clone, "remote")
    if isinstance(listed, str) or listed.returncode != 0:
        said = _said(listed)
        return f"push URL of origin not known to be disabled (git remote: {said}): {fix}", False, ""
    remotes = [line.strip() for line in listed.stdout.splitlines() if line.strip()]
    if "origin" not in remotes:
        return f"push URL of origin not known to be disabled (no origin remote): {fix}", False, ""
    shown: list[str] = []
    origin: list[str] = []
    for remote in ["origin", *sorted(name for name in remotes if name != "origin")]:
        proc = _git(clone, "remote", "get-url", "--push", "--all", remote)
        if isinstance(proc, str) or proc.returncode != 0:
            return (
                f"push URL of {remote} not known to be disabled (`git remote get-url --push "
                f"{remote}`: {_said(proc)}): {fix}",
                False,
                "",
            )
        urls = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
        live = [
            url for url in urls
            if any(char in url for char in "/\\:@") or (clone / url).exists()
        ]  # fmt: skip
        if not urls or live:
            return (
                f"push URL of {remote} is live ({', '.join(live or urls) or '(none)'}): {fix}",
                False,
                "",
            )
        if remote == "origin":
            origin = urls
        shown.append(f"{remote}={','.join(urls)}")
    keys = _git(clone, "config", "-z", "--get-regexp", _PUSH_KEYS)
    if isinstance(keys, str) or keys.returncode not in (0, 1):
        return f"push remote not known (git config: {_said(keys)}): {fix}", False, ""
    chosen: list[str] = []
    for item in keys.stdout.split("\0") if keys.returncode == 0 else []:
        if not item:
            continue
        key, _, value = item.partition("\n")
        if value != "." and value not in remotes:
            return (
                f"push goes elsewhere: {key} is {value!r}, which is not a remote of the clone, "
                f"so a plain `git push` pushes to it as a URL or a path: {fix}",
                False,
                "",
            )
        chosen.append(f"{key}={value}")
    others = f"; other remotes {', '.join(shown[1:])} disabled too" if shown[1:] else ""
    return (
        f"push URL disabled ({', '.join(origin)}){others}",
        True,
        f"push URLs {' '.join(shown)}; push remote settings {', '.join(chosen) or '(none set)'}; "
        f"clone realpath {os.path.realpath(clone)}",
    )


def _under_realpath(path: Path, root: Path) -> bool:
    """`path` is `root` or below it once both are resolved (§32)."""
    real, base = os.path.realpath(path), os.path.realpath(root)
    return real == base or real.startswith(base.rstrip(os.sep) + os.sep)


def _guard_command_path(command: str, cwd: Path, *, flag: str | None = None) -> Path | None:
    """The guard file `command` runs as `python3 -I <guard>` and nothing else (§30,
    §37), or None. With `flag` (§31's `--write`), that word and only that word follows
    the path: the write matcher's command is `python3 -I <guard> --write`. §37: `-I`
    is required, as the second word; without it the live hook imports from the
    guard's directory, the user site and `PYTHONPATH`."""
    plain = command.replace("${CLAUDE_PROJECT_DIR}", "").replace("$CLAUDE_PROJECT_DIR", "")
    if any(char in _HOOK_SHELL_CHARS for char in plain):
        return None
    try:
        words = shlex.split(command)
    except ValueError:
        return None
    wanted = 3 if flag is None else 4
    if len(words) != wanted or words[:2] != [GUARD_INTERPRETER, GUARD_ISOLATED]:
        return None
    if flag is not None and words[3] != flag:
        return None
    word = words[2].replace("${CLAUDE_PROJECT_DIR}", str(cwd))
    word = word.replace("$CLAUDE_PROJECT_DIR", str(cwd))
    if not (word == GUARD_HOOK or word.endswith("/" + GUARD_HOOK)):
        return None
    return cwd / word  # an absolute word replaces cwd


def _may_select(matcher: Any, tool: str) -> bool:
    """§33 (review 16 should-fix 4): could this hook matcher select `tool`? Read
    broadly, so that doubt fails the row rather than passing it: absent, empty or
    `*`; not a string; an `|`-alternative equal to the name in any case; a regular
    expression that finds the name unanchored and case-insensitively (`ulti.dit|as`
    finds `Bash`); or one that does not compile."""
    if matcher is None or matcher in ("", "*") or not isinstance(matcher, str):
        return True
    if any(part.strip().lower() == tool.lower() for part in matcher.split("|")):
        return True
    try:
        return re.search(matcher, tool, re.IGNORECASE) is not None
    except re.error:
        return True


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

    §32 (review 15 blocker 4): nor is one this config cannot honour — `[series]
    architect = "role"` without `[roles.architect]` fails the row with the config
    error `check_series_roles` raises, which names both files (and handsd refuses to
    start on it).
    """
    path = playbook_path(config)
    try:
        book = load_playbook(path, cwd=config.role("builder").cwd)
        if book is not None:
            check_series_roles(book, config)
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
            f"`systemctl --user start handsd@{config.project}` (systemd/handsd@.service)",
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
    """One real `claude -p` turn for a role — the only check that costs anything.

    §36 (H-041): the architect's turn is not the one-line answer; see
    `_architect_live`."""
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
    if role.name == ARCHITECT_ROLE:
        return _architect_live(config, role)
    # the environment a role job gets (§23)
    turn = _live_turn(config, role, LIVE_PROMPT, {**os.environ, **role.spawn_env})
    if isinstance(turn, Check):
        return turn
    result, _ = turn
    first = str(result.get("result", "")).strip().splitlines()
    return Check(
        name,
        OK if not result.get("is_error") else FAIL,
        f"one turn in {role.cwd}: {first[0] if first else '(empty result)'}  "
        f"[session {result.get('session_id')}, {result.get('num_turns')} turn(s), "
        f"${result.get('total_cost_usd')}]",
    )


def _live_turn(
    config: Config, role: RoleConfig, prompt: str, env: dict[str, str]
) -> tuple[dict[str, Any], str] | Check:
    """§2's invocation exactly, as argv, in the role's cwd: the turn's `result` event
    and its whole stdout, or the failed `live <role>` row."""
    name = f"live {role.name}"
    argv = build_argv(config, role)
    try:
        proc = subprocess.run(
            argv,
            input=prompt,
            cwd=str(role.cwd),
            env=env,
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
    return result, proc.stdout


def live_kit_name() -> str:
    """§37: the live kit's name, unique per run: `hands-doctor-live-<8 hex>`."""
    return f"{LIVE_KIT_PREFIX}{secrets.token_hex(4)}"


def _kit_check_names(argv: list[str], cwd: Path, kit: Path, clone: Path) -> bool:
    """§37: does this `hands kit check` argv name the live kit's own path and, as an
    explicit `--repo`, the clone? Relative paths are the role's cwd's, where the turn
    runs. Any other kit or repository, or no `--repo`, is not the live check."""
    if argv[:3] != ["hands", "kit", "check"]:
        return False
    positional: list[str] = []
    repo: str | None = None
    words = iter(argv[3:])
    for word in words:
        if word == "--repo":
            repo = next(words, None)
        elif word.startswith("--repo="):
            repo = word.removeprefix("--repo=")
        elif word == "--project":
            next(words, None)
        elif not word.startswith("-"):
            positional.append(word)
    if len(positional) != 1 or not repo:
        return False

    def same(named: str, path: Path) -> bool:
        return (cwd / named).resolve() == path.resolve()

    return same(positional[0], kit) and same(repo, clone)


def _architect_live(config: Config, role: RoleConfig) -> Check:
    """§36 (H-041): the architect's live turn does the role's work in miniature —
    writes one file under `kits/` with the Write tool, runs `hands kit check` on that
    one-file kit against the clone, and runs `hands show` on a job of its spool —
    and doctor then removes the file. Each is judged from what happened, not from
    the reply: the file on disk with its content, the tool calls and their results
    in the turn's stream, and the path gone afterwards. Any of the four missing
    fails the row.

    §37: `--repo` is the clone `driver_clone` resolves for the role (`.` when the
    cwd is the clone), and the row FAILS before the turn when there is none; only a
    `hands kit check` naming the live kit's path and that `--repo` counts. The kit is
    `kits/hands-doctor-live-<8 hex>`; doctor creates that directory (exclusively, so
    an existing path FAILS the row and the turn is not run) and removes only it.

    The turn's environment is an architect job's (`hands.runner.job_env`: the role's
    `spawn_env`, `HANDS_CLONE`, `HANDS_KITS`) plus `HANDS_PROJECT`, the config's
    project, so `hands show` reaches this project's daemon. The design is silent on
    who removes the file; the role cannot (its settings deny `rm`), so doctor does.
    """
    name = f"live {role.name}"
    kits_dir = role.cwd / "kits"
    kit = kits_dir / live_kit_name()
    target = kit / LIVE_FILE
    try:
        jobs = Spool(config.spool_root).list_jobs()
    except (OSError, SpoolError) as exc:
        return Check(name, FAIL, f"cannot read the spool for a job to show: {exc}")
    if not jobs:
        return Check(
            name,
            FAIL,
            "no job in the spool for the turn's `hands show`: run one job (`hands send "
            "--role aux ...`) and run `hands doctor --live` again (§36). Not run",
        )
    job_id = jobs[-1].id
    if not kits_dir.is_dir() or kits_dir.is_symlink():
        return Check(name, FAIL, f"no kits directory {kits_dir} to write under (§31, §36)")
    clone = driver_clone(role.cwd)
    if clone is None:
        return Check(
            name,
            FAIL,
            f"no clone for the turn's `hands kit check --repo`: neither {role.cwd / 'repo'} "
            f"nor {role.cwd} is a git repository (§29, §37). Not run",
        )
    repo = "." if clone == role.cwd else f"./{clone.relative_to(role.cwd)}"
    if kit.exists() or kit.is_symlink():
        return Check(
            name,
            FAIL,
            f"{kit} already exists; doctor removes only a kit it created, so it leaves "
            "this one as it is (§37). Not run",
        )
    try:
        kit.mkdir()
    except OSError as exc:
        return Check(name, FAIL, f"cannot create {kit} for the turn: {exc} (§37). Not run")
    kit_check = f"hands kit check kits/{kit.name} --repo {repo}"
    show = f"hands show {job_id}"
    prompt = (
        "hands doctor --live: prove this role can do its work. Do exactly these three "
        "things, in order, and nothing else:\n"
        f"1. With the Write tool, create the file {target} whose whole content is the "
        f"one word: {LIVE_CONTENT}\n"
        f"2. Run this Bash command (it reports FAIL for a kit with no brief; that is "
        f"expected): {kit_check}\n"
        f"3. Run this Bash command: {show}\n"
        "Do not remove the file; hands doctor removes it. Then reply with exactly this "
        "line and nothing else:\nVERDICT: doctor ok\n"
    )
    env = {**os.environ, **role.spawn_env, KITS_ENV: str(kits_dir), "HANDS_PROJECT": config.project}
    env[CLONE_ENV] = str(clone)
    turn = _live_turn(config, role, prompt, env)
    if isinstance(turn, Check):
        _remove_live_kit(kit)
        return turn
    result, stdout = turn
    calls = _tool_calls(stdout)

    done: list[str] = []
    missing: list[str] = []
    try:
        wrote = target.is_file() and target.read_text(encoding="utf-8").strip() == LIVE_CONTENT
    except (OSError, UnicodeDecodeError):
        wrote = False
    (done if wrote else missing).append("write")
    checked = any(
        _kit_check_names(argv, role.cwd, kit, clone) and LIVE_KIT_CHECKED in text
        for argv, text, _ in calls
    )
    (done if checked else missing).append("kit check")
    shown = any(
        argv[:3] == ["hands", "show", job_id] and not error and f"job {job_id}" in text.splitlines()
        for argv, text, error in calls
    )
    (done if shown else missing).append("hands show")
    problem = _remove_live_kit(kit)
    (done if problem is None else missing).append("remove")

    words = {
        "write": f"wrote {target}",
        "kit check": f"ran `{kit_check}` on the one-file kit against the clone",
        "hands show": f"ran `{show}`",
        "remove": f"removed {kit}" if problem is None else f"could not remove {kit}: {problem}",
    }
    detail = (
        f"one turn in {role.cwd}  [session {result.get('session_id')}, "
        f"{result.get('num_turns')} turn(s), ${result.get('total_cost_usd')}]"
        + "".join(f"\n{words[step]}" for step in done)
    )
    if result.get("is_error"):
        missing.append("a successful turn")
    if missing:
        detail += (
            f"\ndid not happen: {', '.join(missing)}; the architect role must write under "
            "kits/, run hands kit check and hands show (§36): check the row above and "
            "architect/settings.json"
        )
        if problem is not None:
            detail += f"\n{words['remove']}"
        return Check(name, FAIL, detail)
    return Check(name, OK, detail)


def _remove_live_kit(kit: Path) -> str | None:
    """Remove doctor's one-file kit (§36), a link or a directory; why not, or None."""
    try:
        if kit.is_symlink() or kit.is_file():
            kit.unlink()
        elif kit.exists():
            shutil.rmtree(kit)
    except OSError as exc:
        return str(exc)
    if kit.exists() or kit.is_symlink():
        return f"{kit} is still there"
    return None


def _tool_calls(stdout: str) -> list[tuple[list[str], str, bool]]:
    """Every Bash call of a stream-json turn (§2) that has a result: its command as
    words, the result's text and whether the result is an error."""
    commands: dict[str, str] = {}
    calls: list[tuple[list[str], str, bool]] = []
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        message = event.get("message") if isinstance(event, dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        for block in content if isinstance(content, list) else []:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use" and block.get("name") == "Bash":
                tool_input = block.get("input")
                command = tool_input.get("command") if isinstance(tool_input, dict) else None
                if isinstance(command, str):
                    commands[str(block.get("id"))] = command
            elif block.get("type") == "tool_result":
                command = commands.get(str(block.get("tool_use_id")))
                if command is None:
                    continue
                try:
                    argv = shlex.split(command)
                except ValueError:
                    continue
                text = _result_text(block.get("content"))
                calls.append((argv, text, bool(block.get("is_error"))))
    return calls


def _result_text(content: Any) -> str:
    """A tool_result's content: a string, or a list of text blocks."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            str(part.get("text", "")) for part in content if isinstance(part, dict)
        )
    return ""


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
