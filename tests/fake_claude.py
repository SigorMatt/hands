#!/usr/bin/env python3
"""A stand-in for the `claude` CLI (DESIGN §2), so no test needs the real binary.

It imitates `claude -p --output-format stream-json --verbose`: it refuses an
invocation that is not that shape, emits a `system`/`init` event carrying a
session id, honours `--resume <id>` by giving the same id back, reads the prompt
from stdin, and then does whatever the prompt's control lines ask for.

Control lines are lines of the prompt that begin with `FAKE:`. Everything after
the directive is its argument, with `\\n` read as a newline and `\\\\` as a
backslash, so a multi-line result fits on one line of a test:

    FAKE:session <id>      use this session id (ignored when --resume is given)
    FAKE:result <text>     the text of the `result` event (default "ok")
    FAKE:cat <path>        result is that file's content, or MISSING:<path>
    FAKE:stderr <text>     write this to stderr before anything else
    FAKE:junk <text>       emit this as a raw, non-JSON stdout line
    FAKE:events <n>        emit n small `assistant` events after the init event
    FAKE:task-killed <task-id> <command>
                           emit a `Bash` tool_use of <command> and the harness's
                           task-killed notice for it (repeatable; see below)
    FAKE:orphan <pidfile> [keep-stdio]
                           double-fork a `sleep 300` that outlives this process,
                           without setsid (so it stays in the process group),
                           and write its pid to <pidfile> once it has exec'd;
                           its stdio goes to /dev/null unless `keep-stdio`,
                           which leaves it holding this process's pipes
    FAKE:sleep <seconds>   sleep this long after the init event
    FAKE:block             block until SIGINT (exit 130) or SIGTERM (exit 143)
    FAKE:ignore-int        with FAKE:block, ignore SIGINT so only SIGTERM ends it
    FAKE:rate-limit <msg>  emit system/api_retry with error "rate_limit", then exit
    FAKE:no-result         exit without emitting a `result` event
    FAKE:no-turns          leave `num_turns` out of the result event
    FAKE:subtype <s>       the result event's subtype (default "success", or
                           "error_during_execution" with FAKE:error); with no
                           argument the event carries no subtype at all
    FAKE:env <NAME>        result is the value of $NAME as this process saw it,
                           or UNSET:<NAME> (proves what the runner passed)
    FAKE:error <msg>       emit an error-subtype `result` (is_error true)
    FAKE:exit <code>       exit with this code (default 0)
    FAKE:turns <n>         num_turns of the result event
    FAKE:cost <usd>        total_cost_usd of the result event
    FAKE:duration <ms>     duration_ms of the result event
    FAKE:denial <tool>     add a permission_denials entry (repeatable)

A prompt hands writes itself (a playbook rule, DESIGN §10) carries no control
lines, so a scripted reply can also be queued outside the prompt: point
`$HANDS_FAKE_CLAUDE_REPLIES` at a JSON file holding a list of result strings and
each invocation takes the next one, in order (the position is kept in a sibling
`.used` file, under a lock). `FAKE:` directives in the prompt still win, and an
exhausted queue falls back to the default result. An entry may also be an object,
`{"result": <text>, "stderr": <text>}`: its `stderr` is written to stderr when the
entry is taken, which is how a playbook-issued job ends the way the harness ends
one it terminates (H-014); `"no_turns": true` in it leaves `num_turns` out of the
result event, as `FAKE:no-turns` does; `"task_killed": [[<task-id>, <command>], …]`
in it emits the task-killed notice for each pair before the result, as
`FAKE:task-killed` does; `"exec": [<argv>…]` in it runs that command (stdin from
/dev/null, output to this process's stderr) before the result is emitted, which
is how a scripted driver role performs its `hands send --context keep` (§27). A
reply is taken only on the path that emits a
successful result, so a prompt with `FAKE:error`, `FAKE:no-result` or
`FAKE:rate-limit` leaves the queue where it was.

The event shapes follow the schemas in the real binary (claude 2.1.268): the
init event is `{"type":"system","subtype":"init",…}`, the retry event is
`{"type":"system","subtype":"api_retry","error":"rate_limit",…}` where `error`
is an enum that includes `rate_limit`, and the result event is
`{"type":"result","subtype":"success",…}` with `result`, `num_turns`,
`duration_ms`, `total_cost_usd` and `permission_denials`.

The task-killed notice is the sequence recorded in real stream logs and quoted
in `tests/fixtures/task_killed.stream.jsonl` (claude 2.1.269 and 2.1.270): an
`assistant` event carrying the `Bash` tool_use, `system`/`task_started`,
`system`/`task_updated` with `patch.status` "killed", and
`system`/`task_notification` with `status` "stopped".
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import signal
import subprocess
import sys
import time
import uuid

DIRECTIVE = "FAKE:"


def unescape(text: str) -> str:
    out: list[str] = []
    i = 0
    while i < len(text):
        char = text[i]
        if char == "\\" and i + 1 < len(text):
            nxt = text[i + 1]
            if nxt == "n":
                out.append("\n")
                i += 2
                continue
            if nxt == "\\":
                out.append("\\")
                i += 2
                continue
        out.append(char)
        i += 1
    return "".join(out)


def parse_directives(prompt: str) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for line in prompt.splitlines():
        if not line.startswith(DIRECTIVE):
            continue
        body = line[len(DIRECTIVE) :]
        name, _, arg = body.partition(" ")
        found.setdefault(name.strip(), []).append(unescape(arg))
    return found


def emit(event: dict[str, object]) -> None:
    sys.stdout.write(json.dumps(event) + "\n")
    sys.stdout.flush()


def emit_many(count: int, session_id: str) -> None:
    """`FAKE:events <n>`: n minimal `assistant` events, as cheaply as possible.

    The memory gate of DESIGN §21 needs a transcript of 200 000 events and the
    suite has to stay fast, so these are built by string concatenation from one
    prefix rather than by `json.dumps` per event, and flushed once at the end.
    They are still well-formed stream-json lines carrying the session id, which
    is all the runner reads from an event it has no rule for.
    """
    if count <= 0:
        return
    prefix = '{"type":"assistant","session_id":"' + session_id + '","n":'
    write = sys.stdout.write
    for n in range(count):
        write(prefix + str(n) + "}\n")
    sys.stdout.flush()


def emit_task_killed(session_id: str, task_id: str, command: str) -> None:
    """The recorded shape of a Bash command's task being killed (see the fixture)."""
    tool_use_id = f"toolu_fake_{task_id}"
    emit(
        {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": tool_use_id,
                        "name": "Bash",
                        "input": {"command": command, "run_in_background": True},
                    }
                ],
            },
            "parent_tool_use_id": None,
            "session_id": session_id,
        }
    )
    emit(
        {
            "type": "system",
            "subtype": "task_started",
            "task_id": task_id,
            "tool_use_id": tool_use_id,
            "description": command,
            "is_backgrounded": True,
            "task_type": "local_bash",
            "uuid": str(uuid.uuid4()),
            "session_id": session_id,
        }
    )
    emit(
        {
            "type": "system",
            "subtype": "task_updated",
            "task_id": task_id,
            "patch": {"status": "killed", "end_time": int(time.time() * 1000)},
            "uuid": str(uuid.uuid4()),
            "session_id": session_id,
        }
    )
    emit(
        {
            "type": "system",
            "subtype": "task_notification",
            "task_id": task_id,
            "tool_use_id": tool_use_id,
            "status": "stopped",
            "output_file": f"/tmp/fake-claude/tasks/{task_id}.output",
            "summary": command,
            "uuid": str(uuid.uuid4()),
            "session_id": session_id,
        }
    )


#: What `FAKE:orphan` leaves running: a command line a test can assert on exactly.
ORPHAN_ARGV = ["sleep", "300"]


def double_fork_orphan(pidfile: str, *, keep_stdio: bool) -> None:
    """`FAKE:orphan`: a grandchild that outlives this process (DESIGN §24).

    No `setsid`: the grandchild stays in this process's group, which is what the
    process-group fallback can see. Returns only after the grandchild has exec'd
    (the close-on-exec pipe reaches EOF), so its command line is already
    `sleep 300` when this process emits its result and exits.
    """
    read_end, write_end = os.pipe()  # non-inheritable: closed by exec
    middle = os.fork()
    if middle == 0:
        os.close(read_end)
        grandchild = os.fork()
        if grandchild == 0:
            if not keep_stdio:
                devnull = os.open(os.devnull, os.O_RDWR)
                for fd in (0, 1, 2):
                    os.dup2(devnull, fd)
            try:
                os.execvp(ORPHAN_ARGV[0], ORPHAN_ARGV)
            finally:
                os._exit(127)
        with open(pidfile, "w", encoding="utf-8") as handle:
            handle.write(str(grandchild))
        os._exit(0)
    os.close(write_end)
    while os.read(read_end, 1024):
        pass
    os.close(read_end)
    os.waitpid(middle, 0)


def parse_argv(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("-p", "--print", action="store_true")
    parser.add_argument("--output-format")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("-r", "--resume")
    parser.add_argument("--model")
    parser.add_argument("--permission-prompts")
    args, _rest = parser.parse_known_args(argv)
    if not args.print:
        parser.error("fake_claude: -p/--print is required")
    if args.output_format != "stream-json":
        parser.error(
            "fake_claude: --output-format stream-json is required, "
            f"got {args.output_format!r}"
        )
    return args


def install_block_handlers(ignore_int: bool) -> None:
    """Arm the exit codes DESIGN §2 expects: 143 on SIGTERM, 130 on SIGINT.

    Armed before the init event is emitted, so a caller that waits for the
    session id knows the handlers are already in place.
    """

    def die(code: int):  # noqa: ANN202 - builds a signal handler
        def handler(signum: int, frame: object) -> None:
            os._exit(code)

        return handler

    signal.signal(signal.SIGTERM, die(143))
    signal.signal(signal.SIGINT, signal.SIG_IGN if ignore_int else die(130))


def park() -> None:
    while True:
        time.sleep(0.02)


def _scripted() -> object | None:
    """The next reply of `$HANDS_FAKE_CLAUDE_REPLIES`, or None.

    The queue is consumed in invocation order, which is what a chained playbook
    run needs: two aux reviews can carry the same prompt and different verdicts.
    """
    path = os.environ.get("HANDS_FAKE_CLAUDE_REPLIES")
    if not path:
        return None
    try:
        with open(path, encoding="utf-8") as handle:
            replies = json.load(handle)
    except (OSError, ValueError):
        return None
    with open(path + ".used", "a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        handle.seek(0)
        taken = len([line for line in handle.read().splitlines() if line])
        if taken >= len(replies):
            return None
        handle.write("x\n")
        handle.flush()
    return replies[taken]


def _reply() -> tuple[str | None, dict[str, object]]:
    """The next scripted reply's result text and its entry (`{}` for a bare string),
    writing its `stderr` first if it has one."""
    entry = _scripted()
    if isinstance(entry, dict):
        stderr = entry.get("stderr")
        if isinstance(stderr, str) and stderr:
            sys.stderr.write(stderr if stderr.endswith("\n") else stderr + "\n")
            sys.stderr.flush()
        result = entry.get("result")
        return (None if result is None else str(result)), entry
    return (None if entry is None else str(entry)), {}


def _result(one) -> tuple[str, dict[str, object]]:  # noqa: ANN001
    """The result text, and the scripted reply entry it came from (`{}` if none).

    `FAKE:cat <path>` proves a file was on disk *before* claude was spawned."""
    name = one("env")
    if name is not None:
        return os.environ.get(name, f"UNSET:{name}"), {}
    path = one("cat")
    if path is None:
        given = one("result")
        if given:
            return given, {}
        text, entry = _reply()
        return text or "ok", entry
    try:
        with open(path, encoding="utf-8") as handle:
            return handle.read(), {}
    except OSError:
        return f"MISSING:{path}", {}


#: What `claude --version` prints, in the shape the real binary uses
#: ("2.1.268 (Claude Code)"). `hands doctor` runs this check for real even in
#: fake mode, so the stand-in has to answer it (DESIGN §4).
VERSION_LINE = "2.1.268 (Claude Code stand-in)"


def main(argv: list[str]) -> int:
    if argv and argv[0] == "--version":
        print(VERSION_LINE)
        return 0
    args = parse_argv(argv)
    prompt = sys.stdin.read() if not sys.stdin.isatty() else ""
    directives = parse_directives(prompt)

    def one(name: str, default: str | None = None) -> str | None:
        values = directives.get(name)
        return values[0] if values else default

    for text in directives.get("stderr", []):
        sys.stderr.write(text if text.endswith("\n") else text + "\n")
    sys.stderr.flush()

    if "block" in directives:
        install_block_handlers("ignore-int" in directives)

    session_id = args.resume or one("session") or str(uuid.uuid4())
    emit(
        {
            "type": "system",
            "subtype": "init",
            "cwd": os.getcwd(),
            "session_id": session_id,
            "model": args.model or "unknown",
            "tools": [],
            "mcp_servers": [],
            "permissionMode": "default",
            "slash_commands": [],
            "claude_code_version": "fake",
            "uuid": str(uuid.uuid4()),
            # Not a real field: the tests assert on the invocation of DESIGN §2.
            "argv": argv,
        }
    )

    for text in directives.get("junk", []):
        sys.stdout.write(text + "\n")
        sys.stdout.flush()

    emit_many(int(one("events", "0") or 0), session_id)

    for spec in directives.get("task-killed", []):
        task_id, _, command = spec.partition(" ")
        emit_task_killed(session_id, task_id, command)

    for spec in directives.get("orphan", []):
        pidfile, _, mode = spec.partition(" ")
        double_fork_orphan(pidfile, keep_stdio=mode.strip() == "keep-stdio")

    if "sleep" in directives:
        time.sleep(float(one("sleep", "0") or 0))

    if "block" in directives:
        park()

    exit_code = int(one("exit", "0") or 0)

    if "rate-limit" in directives:
        emit(
            {
                "type": "system",
                "subtype": "api_retry",
                "attempt": 1,
                "max_retries": 3,
                "retry_delay_ms": 60000,
                "error_status": 429,
                "error": "rate_limit",
                "message": one("rate-limit", "") or "",
                "session_id": session_id,
                "uuid": str(uuid.uuid4()),
            }
        )
        return exit_code or 1

    if "no-result" in directives:
        return exit_code

    denials = [
        {"tool_name": tool, "tool_use_id": f"toolu_{n}", "tool_input": {}}
        for n, tool in enumerate(directives.get("denial", []))
    ]
    common: dict[str, object] = {
        "type": "result",
        "duration_ms": int(one("duration", "1234") or 1234),
        "duration_api_ms": 1000,
        "num_turns": int(one("turns", "1") or 1),
        "total_cost_usd": float(one("cost", "0.0") or 0.0),
        "permission_denials": denials,
        "stop_reason": None,
        "usage": {},
        "modelUsage": {},
        "session_id": session_id,
        "uuid": str(uuid.uuid4()),
    }
    if "no-turns" in directives:
        del common["num_turns"]

    def subtyped(event: dict[str, object], default: str) -> dict[str, object]:
        subtype = one("subtype", default)
        return {**event, "subtype": subtype} if subtype else event

    if "error" in directives:
        emit(subtyped({**common, "is_error": True, "errors": [one("error", "") or ""]},
                      "error_during_execution"))
        return exit_code or 1
    text, entry = _result(one)
    if entry.get("no_turns") is True:
        common.pop("num_turns", None)
    command = entry.get("exec")
    if isinstance(command, list) and command:
        ran = subprocess.run(
            [str(part) for part in command],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            check=False,
        )
        sys.stderr.write(f"exec exit {ran.returncode}\n{ran.stdout}{ran.stderr}")
        sys.stderr.flush()
    killed = entry.get("task_killed")
    for pair in killed if isinstance(killed, list) else []:
        emit_task_killed(session_id, str(pair[0]), str(pair[1]))
    emit(subtyped({**common, "is_error": False, "result": text}, "success"))
    return exit_code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
