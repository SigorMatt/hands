#!/usr/bin/env python3
"""no_background.py — PreToolUse hook for a repository that hands drives.

DESIGN §21 (and §2): role sessions never use background tasks. The harness
reaps them, so a builder sub-agent's long background job dies silently
mid-mission and the mission goes on believing it ran. Claude Code runs this
hook before every Bash tool call: it reads the hook JSON on stdin and exits 2
(block, with the reason on stderr) when the call asks for the Bash tool's own
`run_in_background`, or when the command daemonizes by hand — `nohup`,
`setsid`, `disown`, a trailing `&` outside quotes, or an `&` before `)`.
Foreground Bash with a timeout is the only way to run something long.

What is not daemonization, and must keep working, or the role cannot run its
own gate: `&&`, `2>&1`, `1>&2`, `&>`, `|&`, an `&` inside single or double
quotes, and a literal `&` in an unquoted URL (`?a=1&b=2` — the `&` there is
followed by more of the argument, not by the end of a command). Quoted text is
text and heredoc bodies are text; `$(...)` and backticks are still commands and
are still read, inside double quotes as well as outside.

Install this file and the `.claude/settings.json` beside it in every repository
hands drives (docs/INTEGRATION.md). Hooks run under
`--dangerously-skip-permissions`, so this holds for builder and aux alike.

Self-test: python3 no_background.py --selftest
"""
import json
import re
import sys

#: Words that turn a foreground command into a detached one. A bare token
#: anywhere counts: a wrapper puts the real command in argument position
#: (`env X=1 nohup ./run.sh`, `xargs -I{} setsid {}`). A path that merely ends
#: in one of them (`docs/nohup-notes.md`) is not this token, and quoted prose
#: is dropped before the tokens are read, so `grep -rn "nohup" src` still runs.
DAEMONIZERS = {"nohup", "setsid", "disown"}

#: Shell punctuation that separates tokens without whitespace around it.
PUNCTUATION_RE = re.compile(r"([;()|&{}])")

#: `&`-shaped text that is a redirection or a boolean, never a background job.
NOISE = [
    (re.compile(r"&&"), "  "),  # `a && b`
    (re.compile(r"\|&"), "  "),  # `a |& b`: a pipe, stderr included
    (re.compile(r"[0-9]*>&[0-9-]+"), " "),  # `2>&1`, `1>&2`, `>&-`
    (re.compile(r"&>>?"), " "),  # `&> file`, `&>> file`
]

#: A heredoc introducer: `<<EOF`, `<<-EOF`, `<< 'EOF'`, `<<"EOF"`. `<<<` is a
#: here-string, not a heredoc, and does not match (the char after `<<` is `<`).
HEREDOC_RE = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")

#: What the agent is told instead. Named once: the block message and the
#: `--selftest` output say the same thing.
ADVICE = (
    "Role sessions never run background tasks (DESIGN §21): the harness reaps "
    "them, so a long background job can die silently mid-mission and nothing "
    "says so. Run it in the foreground instead, with a timeout — the Bash "
    "tool's own `timeout` parameter (milliseconds, up to 20 minutes), or "
    "`timeout <seconds> <command>` — and split work that cannot fit into "
    "steps that each finish."
)


class UnbalancedQuotes(Exception):
    pass


def strip_heredocs(cmd: str) -> str:
    """Return the command with every heredoc body removed.

    The body of `cat > f <<'EOF' … EOF` is data the command reads, not shell:
    an `&` or an unbalanced quote in it is text. The introducer line is kept —
    the command carrying the heredoc is still a command, and `<<'EOF' &` is
    still a background job.
    """
    out: list[str] = []
    rest = cmd
    while True:
        match = HEREDOC_RE.search(rest)
        if not match:
            out.append(rest)
            return "".join(out)
        delimiter = match.group(2)
        newline = rest.find("\n", match.end())
        if newline < 0:  # no body on this command line: nothing to strip
            out.append(rest)
            return "".join(out)
        out.append(rest[: newline + 1])
        body = rest[newline + 1 :]
        lines = body.split("\n")
        for i, line in enumerate(lines):
            if line.strip() == delimiter:
                rest = "\n".join(lines[i + 1 :])
                break
        else:
            return "".join(out)  # unterminated body: all of it is text


def strip_quoted(cmd: str) -> str:
    """Return the command with quoted text blanked out.

    Characters inside quotes become spaces, so the shell's structure (`&`, `(`,
    `)`, `;`) survives while prose does not: `echo 'run it &'` keeps no `&`.
    Inside double quotes `$(…)` and backticks are still executed, so their text
    is kept and read like any other command. Unbalanced quotes raise: the shell
    would wait for more input, and the hook fails closed.
    """
    out: list[str] = []
    stack: list[str] = []  # "'", '"', "$(", "`", "("
    i, n = 0, len(cmd)
    while i < n:
        c = cmd[i]
        quoted = bool(stack) and stack[-1] in ("'", '"')
        if c == "\\" and i + 1 < n and stack[-1:] != ["'"]:
            out.append("  ")
            i += 2
            continue
        if stack[-1:] == ["'"]:
            if c == "'":
                stack.pop()
            out.append(" " if c != "\n" else "\n")
            i += 1
            continue
        if c == "'" and not quoted:
            stack.append("'")
            out.append(" ")
            i += 1
            continue
        if c == '"':
            if stack[-1:] == ['"']:
                stack.pop()
            else:
                stack.append('"')
            out.append(" ")
            i += 1
            continue
        if cmd.startswith("$(", i):
            stack.append("$(")
            out.append("  ")
            i += 2
            continue
        if c == "`":
            if stack[-1:] == ["`"]:
                stack.pop()
            else:
                stack.append("`")
            out.append(" ")
            i += 1
            continue
        if c == "(" and not quoted:
            stack.append("(")
            out.append("(")
            i += 1
            continue
        if c == ")" and not quoted:
            if stack[-1:] in (["("], ["$("]):
                stack.pop()
            out.append(")")
            i += 1
            continue
        out.append(" " if quoted and c != "\n" else c)
        i += 1
    if any(frame in ("'", '"', "`") for frame in stack):
        raise UnbalancedQuotes(", ".join(sorted(set(stack))))
    return "".join(out)


def strip_noise(cmd: str) -> str:
    """Remove the `&`-shaped text that is a boolean or a redirection."""
    for pattern, replacement in NOISE:
        cmd = pattern.sub(replacement, cmd)
    return cmd


def background_operator(cmd: str) -> bool:
    """True if a bare `&` in this (already stripped) command backgrounds it.

    An `&` is the background operator when nothing of the same word follows it:
    at the end, before whitespace, or before `)`, `;` or a newline. An `&` glued
    between two argument characters is a literal — that is the unquoted URL
    (`?a=1&b=2`), which bash would background too but which the unit takes as
    text, and which no role session means as a daemon.
    """
    for match in re.finditer(r"&", cmd):
        after = cmd[match.end() : match.end() + 1]
        if after == "" or after in ");\n" or after.isspace():
            return True
    return False


def is_true(value: object) -> bool:
    """Whether the hook JSON's `run_in_background` says yes, in any spelling."""
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes"}
    if isinstance(value, bool):
        return value
    return value == 1


def check(cmd: str, run_in_background: object = False) -> str | None:
    """Return None if the call may run, else the reason it is a background job."""
    if is_true(run_in_background):
        return "run_in_background is true"
    if not cmd or not cmd.strip():
        return None
    try:
        bare = strip_noise(strip_quoted(strip_heredocs(cmd)))
    except UnbalancedQuotes as e:
        return f"unbalanced quotes ({e}): {cmd!r}"
    for token in PUNCTUATION_RE.sub(r" \1 ", bare).split():
        if token in DAEMONIZERS:
            return f"{token}: {cmd!r}"
    if background_operator(bare):
        return f"`&` backgrounds the command: {cmd!r}"
    return None


SELFTEST = [
    # (command, allowed?)
    # --- the ordinary foreground work of a role session -------------------
    ("./scripts/check", True),
    ("uv run pytest", True),
    ("uv run pytest tests/test_no_background.py::test_selftest_case", True),
    ("uv run ruff check . && uv run pytest -q", True),
    ("timeout 1800 ./scripts/check", True),
    ("git commit -m 'runner: the log & the spool'", True),
    ("git log --oneline -5 | head -3", True),
    ("uv run pytest 2>&1 | tail -20", True),
    ("uv run hands --help >/dev/null", True),
    ("echo failed 1>&2", True),
    ("ls &> /tmp/out", True),
    ("ls > /tmp/out 2>&1", True),
    ("for f in src/hands/*.py; do echo $f; done", True),
    ("test -f DESIGN.md && echo yes", True),
    ("if grep -q x README.md; then echo found; fi", True),
    ("python3 .claude/hooks/no_background.py --selftest", True),
    # --- text that merely says `&` or names a daemonizer -------------------
    ("echo 'run it in the background with &'", True),
    ('echo "a && b"', True),
    ('grep -rn "nohup" src tests', True),
    ("cat docs/nohup-notes.md", True),
    ("git log --grep='setsid' --oneline", True),
    ("curl -s 'https://example.com/?a=1&b=2'", True),
    ("curl -s https://ntfy.sh/x?title=a&message=b", True),
    ("cat > /tmp/x <<'EOF'\nrun it with &\nnohup ./x\nEOF", True),
    # --- a trailing `&` is a background job --------------------------------
    ("sleep 100 &", False),
    ("sleep 100&", False),
    ("uv run pytest &", False),
    ("uv run pytest > /tmp/log 2>&1 &", False),
    ("uv run handsd --project hands &", False),
    ("sleep 5 & echo started", False),
    ("ls; ./scripts/check &", False),
    ("./scripts/check &\necho started", False),
    ("cat > /tmp/x <<'EOF' &\nbody\nEOF", False),
    # --- `&` before `)`: a backgrounded subshell ---------------------------
    ("( sleep 300 & )", False),
    ("(./scripts/check &)", False),
    ("(cd /tmp && ./run.sh &)", False),
    ("{ sleep 300 & }", False),
    # --- the daemonizing words ---------------------------------------------
    ("nohup ./scripts/check", False),
    ("nohup uv run pytest > /tmp/out 2>&1 &", False),
    ("setsid ./scripts/check", False),
    ("setsid --fork uv run handsd", False),
    ("./run.sh & disown", False),
    ("disown -a", False),
    ("env X=1 nohup ./run.sh", False),
    # --- a substitution is still a command ---------------------------------
    ('echo "$(sleep 100 &)"', False),
    ("echo `sleep 100 &`", False),
    ('echo "$(nohup ./run.sh)"', False),
    # --- fail closed --------------------------------------------------------
    ('echo "unterminated', False),
    ("echo 'unterminated", False),
]


def selftest() -> int:
    bad = 0
    for cmd, expected in SELFTEST:
        reason = check(cmd)
        if (reason is None) != expected:
            bad += 1
            print(f"FAIL expected {'allow' if expected else 'block'}: {cmd!r} -> {reason}")
    if check("ls", run_in_background=True) is None:
        bad += 1
        print("FAIL expected block: run_in_background=true")
    print(f"selftest: {len(SELFTEST) + 1 - bad}/{len(SELFTEST) + 1} ok")
    return 1 if bad else 0


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        return selftest()
    try:
        data = json.load(sys.stdin)
    except Exception as e:  # malformed input: fail closed
        print(f"no_background: cannot parse hook input ({e}); blocking", file=sys.stderr)
        return 2
    if not isinstance(data, dict) or data.get("tool_name") != "Bash":
        return 0
    tool_input = data.get("tool_input") or {}
    reason = check(
        tool_input.get("command") or "",
        run_in_background=tool_input.get("run_in_background", False),
    )
    if reason is None:
        return 0
    print(f"no_background blocked this Bash call ({reason}). {ADVICE}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
