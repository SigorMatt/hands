"""The `hands` command — a thin JSON-RPC client for the daemon (DESIGN §3, §4).

There is no logic here that the daemon does not also have: the CLI parses the
command line of §4, sends one JSON-RPC request over `server.socket`, and prints
the answer as JSON (`--json`, what the driver reads) or as a readable block
(what you read). Every command of §4 is registered; the ones a later unit
implements answer with an error that names that unit.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import socket
import sys
import time
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TextIO

from hands import __version__, doctor
from hands import notify as notify_mod
from hands.api import TIMEOUT as TIMEOUT_CODE
from hands.config import Config, ConfigError, load_config, resolve_project
from hands.spool import ORIGINS

__all__ = [
    "EXIT_TIMEOUT",
    "FOLLOW_INTERVAL_S",
    "ClientError",
    "build_parser",
    "call",
    "exec_session",
    "main",
]

#: `hands wait` that timed out, told apart from every other failure (which is 1).
#: The driver runs `hands wait --for stop,held` in the background (§11) and has
#: to know whether it was woken or simply gave up waiting.
EXIT_TIMEOUT = 2

#: How often `hands log -f` asks the daemon for the rest of the stream (§7).
#: A poll, not a subscription: the answer is a file the daemon is appending to,
#: and one request per fifth of a second is cheaper than a second protocol.
FOLLOW_INTERVAL_S = 0.2


class ClientError(Exception):
    """The daemon could not be reached, or answered with an error."""

    def __init__(self, message: str, *, code: int | None = None) -> None:
        super().__init__(message)
        #: The JSON-RPC error code the daemon answered with, when it answered.
        self.code = code


# --------------------------------------------------------------- the client


def call(
    socket_path: Path, method: str, params: dict[str, Any], *, project: str = ""
) -> Any:
    """One newline-delimited JSON-RPC 2.0 request, one response (§3)."""
    request = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        try:
            sock.connect(str(socket_path))
        except OSError as exc:
            hint = f" (start it with `handsd --project {project}`)" if project else ""
            raise ClientError(
                f"no daemon on {socket_path}: {exc}; is handsd running?{hint}"
            ) from exc
        with sock.makefile("rw", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(request) + "\n")
            stream.flush()
            line = stream.readline()
    finally:
        sock.close()
    if not line:
        raise ClientError(f"the daemon closed the connection without answering {method}")
    try:
        response = json.loads(line)
    except json.JSONDecodeError as exc:
        raise ClientError(f"the daemon answered with something that is not JSON: {exc}") from exc
    if isinstance(response, dict) and "error" in response:
        error = response["error"]
        raise ClientError(str(error.get("message", error)), code=error.get("code"))
    if not isinstance(response, dict) or "result" not in response:
        raise ClientError(f"the daemon answered without a result: {line.strip()}")
    return response["result"]


# ---------------------------------------------------------------- the parser


def _common() -> argparse.ArgumentParser:
    """Flags accepted before *and* after the command name.

    `SUPPRESS` defaults matter: without them the sub-parser's default would
    overwrite a value given before the command (`hands --json send …`).
    """
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--json", action="store_true", default=argparse.SUPPRESS, help="print JSON, not prose"
    )
    common.add_argument(
        "--project",
        default=argparse.SUPPRESS,
        help="project named by ~/.hands/<project>.toml (default: $HANDS_PROJECT, "
        "or the only config there is)",
    )
    common.add_argument(
        "--socket", default=argparse.SUPPRESS, help="override server.socket from the config"
    )
    return common


def build_parser() -> argparse.ArgumentParser:
    common = _common()
    parser = argparse.ArgumentParser(
        prog="hands",
        parents=[common],
        description=(
            "hands — dispatch prompts to headless Claude Code roles, monitor them, "
            "and chain pre-planned steps by a playbook."
        ),
    )
    parser.add_argument("--version", action="version", version=f"hands {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="command")

    def command(name: str, help_text: str) -> argparse.ArgumentParser:
        return sub.add_parser(name, parents=[common], help=help_text, description=help_text)

    send = command("send", "queue a prompt for a role")
    send.add_argument("--role", required=True, help="builder or aux")
    send.add_argument("--context", required=True, choices=["clear", "keep"])
    send.add_argument(
        "--file",
        action="append",
        metavar="PATH=CONTENT",
        help="write this file under files.allowed_roots before the job runs (repeatable)",
    )
    send.add_argument(
        "--gate", metavar="REASON", help="hold the job until a human decides it (§8)"
    )
    send.add_argument(
        "--prompt-file",
        metavar="PATH",
        help="read the prompt from this file (UTF-8), sent byte for byte; §4's "
        "normal route for prose, since the prompt never touches a command line",
    )
    send.add_argument("--stdin", action="store_true", help="read the prompt from stdin")
    send.add_argument("prompt", nargs="?", help="the prompt; or --prompt-file/--stdin")

    wait = command("wait", "block until a job is terminal, or an event arrives")
    wait.add_argument("job", nargs="?")
    wait.add_argument(
        "--for",
        dest="for_",
        metavar="KINDS",
        help="inbox event kinds, comma-separated (e.g. stop,held); returns the "
        f"event unacked, and exits {EXIT_TIMEOUT} if --timeout expires",
    )
    wait.add_argument("--timeout", type=float, metavar="S")

    command("result", "the job record").add_argument("job")
    command("show", "the job record").add_argument("job")

    jobs = command("jobs", "recent job summaries")
    jobs.add_argument("--role")
    jobs.add_argument(
        "--origin",
        metavar="O",
        help=f"who asked for the job: {'|'.join(sorted(ORIGINS))} (§6)",
    )
    jobs.add_argument(
        "--grep", metavar="PAT", help="case-insensitive substring of the prompt (§7)"
    )
    jobs.add_argument("--since", metavar="D", help="an age (30m, 6h, 2d, 1w) or a date")
    jobs.add_argument("-n", type=int, default=20)

    open_ = command(
        "open",
        "resume a finished job's session: execs `claude --resume <id>` in the role's cwd "
        "(--json prints the invocation instead of running it)",
    )
    open_.add_argument("job")

    log = command("log", "the captured stream-json of a job, verbatim")
    log.add_argument("job", nargs="?")
    log.add_argument(
        "-f",
        dest="role",
        metavar="ROLE",
        help="follow the role's running job, printing each stream-json line as it is written",
    )

    cancel = command("cancel", "stop a job")
    cancel.add_argument("job")
    cancel.add_argument("--reason")

    put = command("put", "write a file under the allowed roots")
    put.add_argument("path")
    put.add_argument("--content", help="the text to write")
    put.add_argument(
        "--from", dest="from_", metavar="FILE", help="copy this file (also under the roots)"
    )
    command("get", "read a file under the allowed roots").add_argument("path")
    command("ls", "list a directory under the allowed roots").add_argument("path")

    tail = command("tail", "the last transcript entries of a role's session")
    tail.add_argument("--role", required=True)
    tail.add_argument("-n", type=int, default=20)

    command("inbox", "unread events").add_argument(
        "--ack", action="store_true", help="mark the events it printed as read"
    )
    command("pipeline", "the active playbook and its counters")

    for name in ("approve", "deny"):
        gate = command(name, f"{name} a held job (§8)")
        gate.add_argument("job")
        gate.add_argument("--reason")
        gate.add_argument(
            "--human-confirmed",
            dest="human_confirmed",
            action="store_true",
            help="the driver's path: only with a quoted human instruction",
        )
        gate.add_argument("--quote", help="the human's instruction, verbatim")

    command("pause", "pause the playbook engine")
    command("resume", "unpause the playbook engine")
    command("status", "daemon, roles, running jobs, monitor state")
    notify = command("notify", "send one message to the configured ntfy topic (§4, §11)")
    notify.add_argument(
        "--test",
        nargs="?",
        const=notify_mod.DEFAULT_TEST_MESSAGE,
        metavar="MESSAGE",
        help="publish this message (or a default line) to server.ntfy_topic now and "
        "print the HTTP status — the proof that delivery works",
    )
    check = command("doctor", "check the install end to end (§4, §14)")
    check.add_argument(
        "--live",
        action="store_true",
        help="also run one real `claude -p` turn per role — the only check that spends "
        f"your subscription; refused when ${doctor.FAKE_ENV}=1",
    )
    return parser


#: command → the params it sends, named as §4 names them (§9: the MCP face of
#: §9 wraps these methods, so the wire names are the CLI's names).
_PARAMS: dict[str, Any] = {
    "send": lambda a: {
        "role": a.role,
        "context": a.context,
        "prompt": a.prompt,
        "file": a.file,
        "gate": a.gate,
    },
    "wait": lambda a: {"job": a.job, "for": a.for_, "timeout": a.timeout},
    "result": lambda a: {"job": a.job},
    "show": lambda a: {"job": a.job},
    "jobs": lambda a: {
        "role": a.role, "origin": a.origin, "grep": a.grep, "since": a.since, "n": a.n,
    },  # fmt: skip
    "open": lambda a: {"job": a.job},
    "log": lambda a: {"job": a.job, "role": a.role},  # `-f` adds `offset`; see _follow
    "cancel": lambda a: {"job": a.job, "reason": a.reason},
    "put": lambda a: {"path": a.path, "content": a.content, "from": a.from_},
    "get": lambda a: {"path": a.path},
    "ls": lambda a: {"path": a.path},
    "tail": lambda a: {"role": a.role, "n": a.n},
    "inbox": lambda a: {"ack": a.ack},
    "pipeline": lambda a: {},
    "approve": lambda a: {
        "job": a.job,
        "reason": a.reason,
        "human_confirmed": a.human_confirmed,
        "quote": a.quote,
    },
    "deny": lambda a: {
        "job": a.job,
        "reason": a.reason,
        "human_confirmed": a.human_confirmed,
        "quote": a.quote,
    },
    "pause": lambda a: {},
    "resume": lambda a: {},
    "status": lambda a: {},
    "notify": lambda a: {"test": a.test},
    "doctor": lambda a: {"live": a.live},
}


# -------------------------------------------------------------- the printing


def _job_block(record: dict[str, Any]) -> str:
    lines = [f"job {record.get('id')}"]
    for label, key in (
        ("role", "role"),
        ("context", "context"),
        ("state", "state"),
        ("origin", "origin"),
        ("created", "created"),
        ("started", "started"),
        ("ended", "ended"),
        ("session", "session_id"),
        ("exit", "exit_code"),
        ("verdict", "verdict"),
    ):
        value = record.get(key)
        if value not in (None, ""):
            lines.append(f"  {label:<8} {value}")
    gate = record.get("gate")
    if gate:
        decided = (
            f"{gate.get('decision')} by {gate.get('decided_by')} at {gate.get('decided_at')}"
            if gate.get("decided_by")
            else "waiting for a human (§8)"
        )
        lines.append(f"  gate     {gate.get('kind')}: {gate.get('reason')}")
        lines.append(f"           {decided}")
        if gate.get("quote"):
            lines.append(f"           quote: {gate['quote']}")
    result = record.get("result")
    if result:
        lines.append("  result")
        lines += [f"    {line}" for line in str(result).splitlines()]
    stderr_tail = record.get("stderr_tail")
    if stderr_tail:
        lines.append("  stderr")
        lines += [f"    {line}" for line in str(stderr_tail).splitlines()]
    return "\n".join(lines)


def _event_line(event: dict[str, Any]) -> str:
    """One inbox event, spelled as `hands inbox` spells it (§11)."""
    return (
        f"{event['id']}  {event['created']}  {event['kind']}  "
        f"{json.dumps(event['payload'], sort_keys=True)}"
    )


def _status_block(result: dict[str, Any]) -> str:
    daemon = result.get("daemon", {})
    lines = [
        f"handsd {daemon.get('version')}  project {daemon.get('project')}  "
        f"pid {daemon.get('pid')}",
        f"  socket   {daemon.get('socket')}",
        f"  started  {daemon.get('started')}",
    ]
    for role, state in result.get("roles", {}).items():
        running = state.get("running")
        what = f"running {running['id']} ({running['state']})" if running else "idle"
        queued = len(state.get("queued", []))
        lines.append(
            f"  {role:<8} {what}; queued {queued}/{state.get('queue_depth')}  {state.get('cwd')}"
        )
    monitor = result.get("monitor", {})
    watching = monitor.get("watching") or []
    lines.append(
        f"  monitor  {monitor.get('source')} ({monitor.get('cmd') or 'built-in'}); "
        f"{_monitor_rule(monitor)}; watching {len(watching)}"
    )
    lines.append(f"  inbox    {result.get('inbox', {}).get('unacked')} unread")
    # §4: the two numbers on a role line are not the same kind of thing, and §5
    # is narrower than "the monitor watches the run". Say both where they are read.
    lines.append(
        "  note     queued N/M is jobs waiting now / the configured capacity"
        " (roles.<role>.queue_depth, in --json also queue_capacity)."
    )
    lines.append(f"  note     {_monitor_note(monitor)}")
    return "\n".join(lines)


def _monitor_rule(monitor: dict[str, Any]) -> str:
    """What the monitor that is actually deciding decides on (§5, §19).

    With `[ops]` configured the ops script holds the rule and hands only fills
    its flags, so `monitor.stall_minutes` describes nothing that is running.
    """
    if monitor.get("source") == "ops":
        flags = " ".join(monitor.get("flags") or ())
        return f"the script decides; hands fills {flags}"
    minutes = monitor.get("stall_minutes")
    if not minutes:
        return "stall detection off (monitor.stall_minutes = 0)"
    # `:g` so the line shows the number the operator configured (40, not 40.0).
    return f"stall = no progress and no liveness for {minutes:g}m"


def _monitor_note(monitor: dict[str, Any]) -> str:
    """§5 again: the note under the line must describe the same monitor."""
    if monitor.get("source") == "ops":
        return (
            "hands files what the script prints, block for block, verbatim;"
            " the rules are the ops repo's, not hands'."
        )
    return (
        "the monitor sees liveness and progress only: a busy-wait on"
        " a nested run is not a stall, and it does not judge the work."
    )


def _pipeline_block(result: dict[str, Any]) -> str:
    """§4's pipeline fields, in the order §4 lists them."""
    book = result.get("playbook") or {}
    where = book.get("path")
    lines = [
        f"playbook {where}"
        + (f"  series {book.get('series')}" if book.get("series") else "")
        + (f"  {book.get('rules')} rule(s)" if book.get("loaded") else "  (not loaded)")
    ]
    if book.get("sha256"):
        lines.append(f"  sha256   {book['sha256']}")
    if book.get("error"):
        lines.append(f"  error    {book['error']}")
    paused = result.get("paused")
    by = result.get("paused_by")
    lines.append(f"  paused   {'yes' if paused else 'no'}" + (f" ({by})" if paused and by else ""))
    if result.get("stop_reason"):
        lines.append(f"  stop     {result['stop_reason']}  [{result.get('stopped_at')}]")
    auto = result.get("auto_runs") or {}
    used, allowed = auto.get("used") or [], auto.get("allowed") or []
    lines.append(
        f"  auto-runs {len(used)}/{len(allowed)} used"
        f"  (started {_numbers(used)}; allowed {_numbers(allowed)})"
    )
    resumes = result.get("resumes") or {}
    counts = ", ".join(f"{role} {n}" for role, n in (resumes.get("used") or {}).items())
    lines.append(f"  resumes  {counts or 'none'} of max_resumes {resumes.get('max_resumes')}")
    rule = result.get("last_rule")
    if rule:
        fired = f" -> job {rule['fired_job']}" if rule.get("fired_job") else ""
        lines.append(
            f"  last     rule {rule.get('rule')} on {rule.get('on')}: "
            f"{rule.get('then')}{fired}  [{rule.get('fired_at')}]"
        )
    else:
        lines.append("  last     no rule has fired")
    return "\n".join(lines)


def _job_line(row: dict[str, Any]) -> str:
    """One job, one line: id, role, state, age, and what it was for (§4, §7).

    The verdict is what a human scanning the library is looking for; when a job
    has none (it is still running, or it never printed one) the first line of the
    prompt stands in, because §7's library is searched by prompt.
    """
    what = row.get("verdict") or row.get("prompt_line") or ""
    return (
        f"{row['id']}  {row['role']:<8} {row['state']:<9} "
        f"{_age(row.get('created')):>5}  {what}"
    )


def _age(created: str | None) -> str:
    """How long ago, in the coarsest unit that still says something."""
    if not created:
        return "?"
    try:
        then = datetime.strptime(created, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=UTC)
    except ValueError:
        return "?"
    seconds = max(0, int((datetime.now(UTC) - then).total_seconds()))
    for size, unit in ((86400, "d"), (3600, "h"), (60, "m")):
        if seconds >= size:
            return f"{seconds // size}{unit}"
    return f"{seconds}s"


def _numbers(values: list[Any]) -> str:
    return ", ".join(str(value) for value in values) or "none"


def _render(command: str, result: Any) -> str:
    if command == "wait" and isinstance(result, dict) and "kind" in result:
        return _event_line(result)  # `wait --for` answers with an event, not a job
    if command in (
        "result", "show", "wait", "send", "cancel", "approve", "deny"
    ) and isinstance(result, dict):
        return _job_block(result)
    if command in ("put", "get") and isinstance(result, dict):
        head = f"{result.get('path')}  {result.get('bytes')} bytes  sha256 {result.get('sha256')}"
        return f"{head}\n{result['content']}" if command == "get" else head
    if command == "ls" and isinstance(result, dict):
        entries = result.get("entries", [])
        if not entries:
            return f"{result.get('path')} is empty"
        return "\n".join(
            f"{entry['type']:<5} {str(entry.get('bytes') or '-'):>10}  "
            f"{entry.get('modified') or '':<21} {entry['name']}"
            for entry in entries
        )
    if command == "status" and isinstance(result, dict):
        return _status_block(result)
    if command in ("pipeline", "pause", "resume") and isinstance(result, dict):
        if result.get("already_stopped"):
            # §19: the pause was a no-op. Say so and say why the pipeline stopped —
            # a bare pipeline block reads as "I have just stopped it".
            return f"already stopped: {result.get('stop_reason')}\n{_pipeline_block(result)}"
        return _pipeline_block(result)
    if command == "jobs" and isinstance(result, dict):
        rows = result.get("jobs", [])
        if not rows:
            return "no jobs"
        return "\n".join(_job_line(row) for row in rows)
    if command == "log" and isinstance(result, dict):
        lines = result.get("lines") or []
        if not lines:
            return (
                f"no captured stream for job {result.get('job')} "
                f"({result.get('state')}): {result.get('path')}"
            )
        return "\n".join(lines)  # stream-json, verbatim: hands captured it, it does not re-render
    if command == "tail" and isinstance(result, dict):
        entries = result.get("entries") or []
        header = f"transcript {result.get('path')}  (job {result.get('job')})"
        return "\n".join([header, *entries])
    if command == "inbox" and isinstance(result, dict):
        events = result.get("events", [])
        if not events:
            return "inbox empty"
        return "\n".join(_event_line(event) for event in events)
    return json.dumps(result, indent=2, sort_keys=True)


# ------------------------------------------------------------------- the CLI


def exec_session(argv: Sequence[str], cwd: str) -> None:
    """Become `claude --resume <id>` in the role's cwd (§7). Never returns.

    This is the one place hands replaces itself with another program: `hands
    open` exists to hand a human an interactive session, and an interactive
    session is not something a daemon can hold on their behalf.
    """
    os.chdir(cwd)
    os.execvp(argv[0], list(argv))  # the argv is the daemon's answer, never a shell string


def main(
    argv: Sequence[str] | None = None,
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
    stdin: TextIO | None = None,
    exec_fn: Callable[[Sequence[str], str], None] | None = None,
) -> int:
    out = sys.stdout if stdout is None else stdout
    err = sys.stderr if stderr is None else stderr
    parser = build_parser()
    args = parser.parse_args(argv)
    command = getattr(args, "command", None)
    if command is None:
        parser.print_help(out)
        return 0

    as_json = getattr(args, "json", False)
    try:
        if command == "send":
            args.prompt = _prompt_of(args, sys.stdin if stdin is None else stdin)
        project = resolve_project(getattr(args, "project", None))
        config = load_config(project)
        override = getattr(args, "socket", None)
        socket_path = Path(override).expanduser() if override else config.server.socket
        # §14 step 1 is "write the config; `hands doctor`" — before handsd has
        # ever been started, so doctor is the one command the CLI answers itself.
        # The daemon is a *check*, not a precondition (see hands/doctor.py).
        if command == "doctor":
            return _doctor(config, socket_path, live=args.live, out=out, as_json=as_json)
        # §4's `notify --test` is the same story: it is the proof that ntfy works,
        # and it has to work at an install, before (or without) a running daemon.
        if command == "notify":
            return _notify(config, args.test, out=out, as_json=as_json)
        # §7: `hands log -f <role>` is a follow, and a follow is many requests.
        if command == "log" and args.role:
            if args.job:
                raise ValueError(
                    f"hands log takes a job id or -f <role>, not both (got {args.job!r})"
                )
            return _follow(socket_path, args.role, project=project, out=out)
        params = {
            key: value for key, value in _PARAMS[command](args).items() if value is not None
        }
        result = call(socket_path, command, params, project=project)
        # §7: `hands open` *is* the resume. With --json it is only described —
        # the driver reads JSON and has no terminal to be replaced by (§12).
        if command == "open" and not as_json:
            (exec_fn or exec_session)(result["argv"], result["cwd"])
            return 0
    except ClientError as exc:
        print(f"hands: {exc}", file=err)
        # §11: a background `wait --for` that timed out is not a failure of hands,
        # and the driver re-arms rather than reporting it.
        return EXIT_TIMEOUT if exc.code == TIMEOUT_CODE else 1
    except (ConfigError, ValueError, OSError, notify_mod.NotifyError) as exc:
        print(f"hands: {exc}", file=err)
        return 1
    print(json.dumps(result, sort_keys=True) if as_json else _render(command, result), file=out)
    return 0


def _doctor(
    config: Config, socket_path: Path, *, live: bool, out: TextIO, as_json: bool
) -> int:
    """`hands doctor` (§4, §11, §14): run the checks here, in the client.

    Exit 1 when a check failed; a warning (no daemon yet, no ntfy topic) is not a
    failure, because §14 runs doctor on a config the daemon has never seen.
    """
    found = doctor.run_checks(config, live=live, socket_path=socket_path)
    if as_json:
        print(json.dumps(doctor.report(config, found, live=live), sort_keys=True), file=out)
    else:
        print(doctor.render(config, found, live=live), file=out)
    return 1 if any(check.status == doctor.FAIL for check in found) else 0


def _notify(config: Config, message: str | None, *, out: TextIO, as_json: bool) -> int:
    """`hands notify --test` (§4, §11): one real ntfy message, sent from the client.

    Not over the socket, for the same reason as doctor: the point of the command
    is to prove delivery at an install (§14 step 1), when handsd may not be
    running — a proof you cannot run until the daemon is up proves the wrong
    thing. Nothing is lost by that: the topic and the URL are config (§13), and
    the transport is `hands.notify.http_post`, the one §11 itself uses. What the
    daemon adds — quiet hours — is exactly what a `--test` must not have: §11
    delays notifications, never actions, and a message a human asked for at a
    terminal is an action.
    """
    if message is None:
        raise ValueError(
            'hands notify takes --test "<message>" (its only mode today, §4); '
            "with no message it sends a default line"
        )
    result = asyncio.run(notify_mod.send_test(config, message))
    print(json.dumps(result, sort_keys=True) if as_json else _notify_block(result), file=out)
    # §19: the status is printed whatever it was, and a non-2xx still fails. A
    # refusal is a fact about the topic (wrong token, wrong URL), not a crash, so
    # it is reported in the same shape as a success — with a code and an exit 1.
    return 0 if result["delivered"] else 1


def _notify_block(result: dict[str, Any]) -> str:
    """What ntfy answered, and who sent it — the daemon's notifications are its own."""
    last = (
        "  sent by the CLI itself, not handsd, and not delayed by quiet hours (§11)"
        if result["delivered"]
        else "  ntfy did not accept it: nothing was delivered to the topic"
    )
    return "\n".join(
        [
            f"ntfy {result['status']}  {result['url']}",
            f"  title    {result['title']}",
            f"  message  {result['message']}",
            last,
        ]
    )


def _follow(socket_path: Path, role: str, *, project: str, out: TextIO) -> int:
    """`hands log -f <role>`: the running job's stream-json, line by line (§7).

    The first request names the role and so refuses a role with nothing running;
    every later one names the *job* it answered with, so a follow stays with the
    job it started on and stops when that job does — it does not silently jump to
    whatever the role runs next. Lines are printed exactly as captured: this is
    the only rendering that cannot drop information.
    """
    params: dict[str, Any] = {"role": role, "offset": 0}
    try:
        while True:
            result = call(socket_path, "log", params, project=project)
            for line in result["lines"]:
                print(line, file=out, flush=True)
            params = {"job": result["job"], "offset": result["offset"]}
            if not result["running"] and not result["lines"]:
                return 0  # the job is terminal and its stream is drained
            if not result["lines"]:
                time.sleep(FOLLOW_INTERVAL_S)
    except KeyboardInterrupt:  # pragma: no cover - a human stopping a watch
        return 0  # Ctrl-C ends the watch and nothing else: watching is read-only


#: §4's `send` row: `[--prompt-file path|--stdin|prompt]`. Spelled once so the
#: refusals name all three routes, whichever of them the caller reached for.
_PROMPT_ROUTES = "--prompt-file PATH, --stdin, or a prompt argument"


def _read_prompt_file(where: str) -> str:
    """§4/§12: the prompt travels as a file, so no shell ever parses it.

    The bytes are sent exactly as they are — a trailing newline included, the
    way `--stdin` sends what it was piped. Only an empty (or all-whitespace)
    file is refused: `Api.send` refuses an empty prompt anyway (§6), and
    catching it here names the file that was empty.

    This is the one path where hands reads a file without `files.py`'s
    allowed-roots check, and that is deliberate, not an oversight: those roots
    confine what the *daemon* writes and reads on a role's behalf, while this
    read is the CLI's own, running as the human who typed the command. A human
    is not confined to their own roles' roots.
    """
    path = Path(where).expanduser()
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ValueError(f"--prompt-file {path}: {exc.strerror or exc}") from exc
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"--prompt-file {path}: not UTF-8 text ({exc})") from exc
    if not text.strip():
        raise ValueError(f"--prompt-file {path} is empty; refusing to send an empty prompt")
    return text


def _prompt_of(args: argparse.Namespace, stdin: TextIO) -> str:
    """§4: `[--prompt-file path|--stdin|prompt]` — exactly one of the three."""
    given = [
        name
        for name, used in (
            ("--prompt-file", args.prompt_file is not None),
            ("--stdin", args.stdin),
            ("a prompt argument", args.prompt is not None),
        )
        if used
    ]
    if len(given) > 1:
        raise ValueError(f"give {_PROMPT_ROUTES} — one of them, not {' and '.join(given)}")
    if args.prompt_file is not None:
        return _read_prompt_file(args.prompt_file)
    if args.stdin:
        return stdin.read()
    if args.prompt is None:
        raise ValueError(f"send needs a prompt: {_PROMPT_ROUTES}")
    return args.prompt
