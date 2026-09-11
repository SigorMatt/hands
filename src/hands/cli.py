"""The `hands` command — a thin JSON-RPC client for the daemon (DESIGN §3, §4).

There is no logic here that the daemon does not also have: the CLI parses the
command line of §4, sends one JSON-RPC request over `server.socket`, and prints
the answer as JSON (`--json`, what the driver reads) or as a readable block
(what you read). Every command of §4 is registered; the ones a later unit
implements answer with an error that names that unit.
"""

from __future__ import annotations

import argparse
import json
import socket
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, TextIO

from hands import __version__
from hands.config import ConfigError, load_config, resolve_project

__all__ = ["ClientError", "build_parser", "call", "main"]


class ClientError(Exception):
    """The daemon could not be reached, or answered with an error."""


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
        raise ClientError(str(error.get("message", error)))
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
    send.add_argument("--stdin", action="store_true", help="read the prompt from stdin")
    send.add_argument("prompt", nargs="?", help="the prompt; or use --stdin")

    wait = command("wait", "block until a job is terminal, or an event arrives")
    wait.add_argument("job", nargs="?")
    wait.add_argument("--for", dest="for_", metavar="KINDS", help="event kinds (unit U8)")
    wait.add_argument("--timeout", type=float, metavar="S")

    command("result", "the job record").add_argument("job")
    command("show", "the job record").add_argument("job")

    jobs = command("jobs", "recent job summaries")
    jobs.add_argument("--role")
    jobs.add_argument("--grep", metavar="PAT", help="substring of the prompt")
    jobs.add_argument("--since", metavar="D", help="e.g. 2d, 6h, or a date")
    jobs.add_argument("-n", type=int, default=20)

    command("open", "the `claude --resume` line for a job").add_argument("job")

    log = command("log", "the captured stream of a job or role")
    log.add_argument("job", nargs="?")
    log.add_argument("-f", dest="role", metavar="ROLE", help="follow a role's current job")

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
    command("doctor", "check the install end to end")
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
    "jobs": lambda a: {"role": a.role, "grep": a.grep, "since": a.since, "n": a.n},
    "open": lambda a: {"job": a.job},
    "log": lambda a: {"job": a.job, "role": a.role},
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
    "doctor": lambda a: {},
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
    lines.append(f"  monitor  {monitor.get('note') if not monitor.get('implemented') else 'on'}")
    lines.append(f"  inbox    {result.get('inbox', {}).get('unacked')} unread")
    return "\n".join(lines)


def _render(command: str, result: Any) -> str:
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
    if command == "jobs" and isinstance(result, dict):
        rows = result.get("jobs", [])
        if not rows:
            return "no jobs"
        return "\n".join(
            f"{row['id']}  {row['state']:<9} {row['role']:<8} {row['created']}  "
            f"{row.get('prompt_line', '')}"
            for row in rows
        )
    if command == "inbox" and isinstance(result, dict):
        events = result.get("events", [])
        if not events:
            return "inbox empty"
        return "\n".join(
            f"{event['id']}  {event['created']}  {event['kind']}  "
            f"{json.dumps(event['payload'], sort_keys=True)}"
            for event in events
        )
    return json.dumps(result, indent=2, sort_keys=True)


# ------------------------------------------------------------------- the CLI


def main(
    argv: Sequence[str] | None = None,
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
    stdin: TextIO | None = None,
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
        params = {
            key: value for key, value in _PARAMS[command](args).items() if value is not None
        }
        result = call(socket_path, command, params, project=project)
    except (ClientError, ConfigError, ValueError) as exc:
        print(f"hands: {exc}", file=err)
        return 1
    print(json.dumps(result, sort_keys=True) if as_json else _render(command, result), file=out)
    return 0


def _prompt_of(args: argparse.Namespace, stdin: TextIO) -> str:
    """§4: `[--stdin|prompt]` — one of the two, never both, never neither."""
    if args.stdin and args.prompt is not None:
        raise ValueError("give a prompt or --stdin, not both")
    if args.stdin:
        return stdin.read()
    if args.prompt is None:
        raise ValueError("send needs a prompt (or --stdin)")
    return args.prompt
