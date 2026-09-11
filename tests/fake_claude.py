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
    FAKE:sleep <seconds>   sleep this long after the init event
    FAKE:block             block until SIGINT (exit 130) or SIGTERM (exit 143)
    FAKE:ignore-int        with FAKE:block, ignore SIGINT so only SIGTERM ends it
    FAKE:rate-limit <msg>  emit system/api_retry with error "rate_limit", then exit
    FAKE:no-result         exit without emitting a `result` event
    FAKE:error <msg>       emit an error-subtype `result` (is_error true)
    FAKE:exit <code>       exit with this code (default 0)
    FAKE:turns <n>         num_turns of the result event
    FAKE:cost <usd>        total_cost_usd of the result event
    FAKE:duration <ms>     duration_ms of the result event
    FAKE:denial <tool>     add a permission_denials entry (repeatable)

The event shapes follow the schemas in the real binary (claude 2.1.268): the
init event is `{"type":"system","subtype":"init",…}`, the retry event is
`{"type":"system","subtype":"api_retry","error":"rate_limit",…}` where `error`
is an enum that includes `rate_limit`, and the result event is
`{"type":"result","subtype":"success",…}` with `result`, `num_turns`,
`duration_ms`, `total_cost_usd` and `permission_denials`.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
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


def _result(one) -> str | None:  # noqa: ANN001
    """`FAKE:cat <path>` proves a file was on disk *before* claude was spawned."""
    path = one("cat")
    if path is None:
        return one("result", "ok")
    try:
        with open(path, encoding="utf-8") as handle:
            return handle.read()
    except OSError:
        return f"MISSING:{path}"


def main(argv: list[str]) -> int:
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
    common = {
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
    if "error" in directives:
        emit({**common, "subtype": "error_during_execution", "is_error": True,
              "errors": [one("error", "") or ""]})
        return exit_code or 1
    emit({**common, "subtype": "success", "is_error": False, "result": _result(one)})
    return exit_code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
