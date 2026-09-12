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
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hands.config import Config, RoleConfig
from hands.monitor import OPS_FLAGS
from hands.playbook import PlaybookError, load_playbook, playbook_path
from hands.runner import build_argv

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
#: Seconds for one real `claude -p` turn. A one-line answer, not a task.
LIVE_S = 180.0
#: The live turn's prompt: one turn, no tools, and it exercises §10's VERDICT
#: contract at the same time.
LIVE_PROMPT = "Reply with exactly this line and nothing else:\nVERDICT: doctor ok\n"

#: What a script prints when it does not know a flag. Used to tell "this script
#: does not take `--pids`" apart from "it took them and then failed for its own
#: reasons" (no git repo at the probe's `--base`, for one).
_REFUSALS = ("unrecognized", "unrecognised", "unknown option", "invalid option", "illegal option")

#: The flags §5 gives the ops script, from the module that actually passes them:
#: doctor proves what the monitor will send, so there is one list, not two.
MONITOR_FLAGS = OPS_FLAGS


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
    found += [_role_check(role) for role in config.roles.values()]
    found += [_roots_check(config), _ops_check(config), _playbook_check(config)]
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
            f"{detail}\nno server.ntfy_topic: §11's notifications (stop, job.held, "
            "max_resumes, daemon crash) have nowhere to go, so you only learn you are "
            "needed by looking",
        )
    return Check("config", OK, f"{detail}; ntfy topic set")


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
    # H-008: the two limit-resume behaviours are invisible until a limit is hit.
    detail = (
        f"{role.cwd}  model {role.model}; permission_flags {flags}"
        f"\n{role.resume_behaviour} (§6)"
    )
    if not (role.cwd / ".git").exists():
        return Check(
            name,
            WARN,
            f"{detail}\n{role.cwd} is not a git repository: head_at_start/head_at_end "
            "stay empty (§2) and the built-in monitor has no commits to read (§5)",
        )
    return Check(name, OK, detail)


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
    step4 = (
        "DESIGN §14 step 4: the ops repo's monitor script must exist and accept "
        f"{', '.join(MONITOR_FLAGS)}"
    )
    if not path.exists():
        return Check("ops script", FAIL, f"{path} does not exist.\n{step4}")
    if not os.access(path, os.X_OK):
        return Check("ops script", FAIL, f"{path} is not executable (chmod +x).\n{step4}")

    helped = _run_probe([str(path), "--help"], cwd=config.ops.repo)
    if helped is not None and all(flag in helped.text for flag in MONITOR_FLAGS):
        return Check(
            "ops script", OK, f"{path} accepts {', '.join(MONITOR_FLAGS)} (from `--help`)"
        )

    probe = _run_probe(
        [
            str(path),
            "--pids",
            str(_impossible_pid()),
            "--transcript",
            os.devnull,
            "--base",
            "HEAD",
        ],
        cwd=config.ops.repo,
    )
    if probe is None:
        return Check("ops script", FAIL, f"cannot run {path}.\n{step4}")
    if probe.timed_out:
        return Check(
            "ops script",
            OK,
            f"{path} took {', '.join(MONITOR_FLAGS)} and started watching; the probe "
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
            f"{path} accepted {', '.join(MONITOR_FLAGS)} but exited {probe.code} on a "
            f"dead pid; that may be its way of saying the job is gone: {_tail(probe.text)}",
        )
    return Check("ops script", OK, f"{path} ran with {', '.join(MONITOR_FLAGS)} and exited 0")


def _playbook_check(config: Config) -> Check:
    """§10: no playbook is fine (nothing chains); a broken one is not."""
    path = playbook_path(config)
    try:
        book = load_playbook(path)
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
        f"auto_runs {runs}; sha256 {book.sha256[:12]}…",
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
        "  1. Subscribe your phone to the `server.ntfy_topic` of your config — the",
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
        "     delivery, not the event. Quiet hours delay notifications and never",
        "     actions (§11), so run this outside them.",
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
        "  `server.ntfy_topic` set there is nowhere for any of it to go. Until it",
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


def _run_probe(argv: list[str], *, cwd: Path | None) -> _Probe | None:
    """Run a short-lived probe. None when it could not be started at all."""
    try:
        proc = subprocess.run(
            argv,
            cwd=str(cwd) if cwd else None,
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
