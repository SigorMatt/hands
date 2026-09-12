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

The sub-agent tool too (DESIGN §23, finding H-014): Claude Code runs this hook
before every sub-agent call and exits 2, with the same message shape, unless
the call's input carries `run_in_background: false` — the JSON boolean.
What the tool is called, read from Claude Code 2.1.269 (`claude --version`;
the installed binary's own source, 2026-09-12):
- The tool is `Agent`, with `Task` as its alias (`name:"Agent"`,
  `aliases:["Task"]`, and a legacy-name table `{Task:"Agent"}`). The harness's
  own background check tests `name === "Agent" || name === "Task"`, so a
  `tool_use` named `Task` can still arrive; both are covered. In this
  project's transcripts (~/.claude/projects/-home-msi-git-hands/*.jsonl) every
  sub-agent call is named `Agent`: 85 of them, and none named `Task`.
- A sub-agent runs in the background unless the input says otherwise: the
  harness counts a call as background when `run_in_background !== false`, and
  the tool's description says "Subagents run in the background by default".
  The transcripts agree: 27 `Agent` calls under 2.1.269 omit the flag, and
  all 27 came back "Async agent launched". So an omitted flag, a null, and any
  value that is not the boolean `false` (`"false"`, `0`) ask for the
  background and are refused. An absent or empty `tool_input` is refused on
  the same reading, where an absent Bash command runs nothing and passes.
- A matcher made only of `[a-zA-Z0-9_|]` is split on `|` into exact tool
  names, so `.claude/settings.json` matches `Bash|Agent|Task`.

Where it stops (docs/INTEGRATION.md, "What the hook cannot see"): the hook reads
one command line as shell text. It never runs it, never resolves a variable, and
takes quoted text as text — so `bash -c 'sleep 30 &'`, `eval`, `screen -dmS`,
`tmux new -d`, `at`, `systemd-run`, a script that forks, and a daemonizer that
arrives through a variable all pass. That is the model's boundary, not a bug to
patch here: reading quoted text as shell would block `git commit -m '… & …'` and
`grep -rn "nohup" src`, which a role session needs.
`SendMessage` also passes. Continuing a finished sub-agent with it runs that
sub-agent in the background (H-014's actual cause, job `0mtygi953-ym63`), but
the call has no background input to refuse: it names an agent and a message,
not a mode. Refusing it would stop a role from ever continuing a sub-agent, so
the hook does not match it. A role session can therefore still leave a
background sub-agent running with a foreground-only hook installed.

What is not daemonization, and must keep working, or the role cannot run its
own gate: `&&`, `2>&1`, `1>&2`, `&>`, `|&`, an `&` inside single or double
quotes, and a literal `&` in an unquoted URL (`?a=1&b=2` — the `&` there is
followed by more of the argument, not by the end of a command). Quoted text is
text, heredoc bodies are text, and a `#` comment is text; `$(...)` and backticks
are still commands and are still read, inside double quotes as well as outside.

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

#: Where a word can begin, and so where an unquoted `#` opens a comment that
#: runs to the end of the line. bash starts a word at the start of input, after
#: whitespace, or after one of its metacharacters — `echo a"b"#c` is the single
#: word `a#c`, and `${#x}` is a parameter expansion, so neither is a comment.
WORD_BREAK = " \t\r\n;|&()<>"

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

#: The sub-agent tool's names in Claude Code 2.1.x: `Agent`, and `Task`, its
#: alias (module docstring). `.claude/settings.json` matches the same names.
SUBAGENT_TOOLS = ("Agent", "Task")

#: What the agent is told when a sub-agent call asks for the background: the
#: same shape as `ADVICE`, with the sub-agent's own way to stay in the foreground.
SUBAGENT_ADVICE = (
    "Role sessions never run background tasks (DESIGN §21): the harness reaps "
    "them, so a background sub-agent can die silently mid-mission and nothing "
    "says so. Run the sub-agent in the foreground instead — pass "
    "`run_in_background: false`, since a sub-agent runs in the background when "
    "the flag is omitted — and split work that cannot fit into steps that each "
    "finish."
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
    A `#` that starts a word outside quotes opens a comment, and the rest of its
    line goes the same way — `ls # a & b` backgrounds nothing, and `sleep 30 &#
    note` is left as the background job bash reads it to be.
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
        if c == "#" and not quoted and (i == 0 or cmd[i - 1] in WORD_BREAK):
            end = cmd.find("\n", i)
            end = n if end < 0 else end
            out.append(" " * (end - i))
            i = end
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
    at the end, before whitespace, or before `)`, `;`, `#` or a newline. (A `#`
    there always opens a comment, since `&` ends the word: `sleep 30 &# note` is
    a background job. Comments are blanked before this runs, so the `#` case
    only remains inside a substitution.) An `&` glued
    between two argument characters is a literal — that is the unquoted URL
    (`?a=1&b=2`), which bash would background too but which the unit takes as
    text, and which no role session means as a daemon.
    """
    for match in re.finditer(r"&", cmd):
        after = cmd[match.end() : match.end() + 1]
        if after == "" or after in ");#\n" or after.isspace():
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
        # `/usr/bin/nohup ./x` is `nohup ./x`: the path is how it is spelled,
        # not what it is. The cost is that reading the file by that exact name
        # (`ls -l /usr/bin/nohup`) is refused too — the safe direction.
        if "/" in token and token.rsplit("/", 1)[1] in DAEMONIZERS:
            return f"{token}: {cmd!r}"
    if background_operator(bare):
        return f"`&` backgrounds the command: {cmd!r}"
    return None


def check_subagent(tool_input: dict) -> str | None:
    """Return None if the sub-agent call runs in the foreground, else why not.

    Only the JSON boolean `false` is foreground: Claude Code counts a sub-agent
    as background when `run_in_background !== false` (module docstring), so an
    omitted flag is the background default, and `"false"` or `0` are not false.
    """
    if "run_in_background" not in tool_input or tool_input["run_in_background"] is None:
        return (
            "run_in_background is omitted, and a sub-agent runs in the background "
            "unless it says false"
        )
    value = tool_input["run_in_background"]
    if value is False:
        return None
    if value is True:
        return "run_in_background is true"
    return f"run_in_background is {value!r}, not the boolean false"


SUBAGENT_SELFTEST = [
    # (sub-agent tool_input, allowed?)
    ({"run_in_background": False}, True),
    (
        {"prompt": "Implement U2.", "subagent_type": "general-purpose", "run_in_background": False},
        True,
    ),
    ({"run_in_background": True}, False),
    ({"prompt": "Implement U2.", "run_in_background": True}, False),
    # --- omitted is the background default ---------------------------------
    ({}, False),
    ({"prompt": "Implement U2.", "subagent_type": "general-purpose"}, False),
    ({"run_in_background": None}, False),
    # --- only the boolean false is false -----------------------------------
    ({"run_in_background": "false"}, False),
    ({"run_in_background": "true"}, False),
    ({"run_in_background": 0}, False),
    ({"run_in_background": 1}, False),
    ({"run_in_background": ""}, False),
]


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
    # --- a comment is text too ----------------------------------------------
    ("ls # a & b", True),
    ("uv run pytest -q  # then nohup ./x & disown", True),
    ("# a note about & and setsid", True),
    ("make -j2 # &", True),
    ("ls # a note\nuv run pytest", True),
    ("echo ${#PATH} && ls", True),
    ("curl -s http://example.com/page#frag", True),
    ("./scripts/disown-notes.sh", True),
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
    # --- ...and a comment hides no `&` --------------------------------------
    ("sleep 30 &# note", False),
    ("./scripts/check &# run it", False),
    ("uv run pytest &  # start the gate", False),
    ("ls # a note\nuv run pytest &", False),
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
    # --- a daemonizer spelled as a path is the same daemonizer --------------
    ("/usr/bin/nohup ./long.sh", False),
    ("/usr/bin/setsid --fork uv run handsd", False),
    ("env X=1 /bin/nohup ./run.sh", False),
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
    bad_subagent = 0
    for tool_input, expected in SUBAGENT_SELFTEST:
        reason = check_subagent(tool_input)
        if (reason is None) != expected:
            bad_subagent += 1
            print(f"FAIL expected {'allow' if expected else 'block'}: {tool_input!r} -> {reason}")
    total = len(SUBAGENT_SELFTEST)
    print(f"selftest ({', '.join(SUBAGENT_TOOLS)}): {total - bad_subagent}/{total} ok")
    return 1 if bad or bad_subagent else 0


def main_subagent(tool_name: str, tool_input: object) -> int:
    """The sub-agent half of `main`: exit 2 unless the call stays in the foreground.

    A `tool_input` that is not an object, or a flag of a type JSON booleans are
    never read from, fails closed in one line, as it does for Bash. An absent or
    null `tool_input` is an omitted flag — the background default — and is
    refused with the advice, not waved through as an absent Bash command is.
    """
    if tool_input is None:
        tool_input = {}
    if not isinstance(tool_input, dict):
        kind = type(tool_input).__name__
        print(f"no_background: tool_input is {kind}, not an object; blocking", file=sys.stderr)
        return 2
    background = tool_input.get("run_in_background")
    if background is not None and not isinstance(background, (bool, str, int, float)):
        print("no_background: run_in_background has the wrong type; blocking", file=sys.stderr)
        return 2
    reason = check_subagent(tool_input)
    if reason is None:
        return 0
    print(
        f"no_background blocked this {tool_name} call ({reason}). {SUBAGENT_ADVICE}",
        file=sys.stderr,
    )
    return 2


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        return selftest()
    try:
        data = json.load(sys.stdin)
    except Exception as e:  # malformed input: fail closed
        print(f"no_background: cannot parse hook input ({e}); blocking", file=sys.stderr)
        return 2
    if isinstance(data, dict) and data.get("tool_name") in SUBAGENT_TOOLS:
        return main_subagent(data["tool_name"], data.get("tool_input"))
    if not isinstance(data, dict) or data.get("tool_name") != "Bash":
        return 0
    # A Bash call whose `tool_input` or `command` is not the shape the tool
    # documents is input this hook cannot parse, so it fails closed like any
    # other: exit 2, one line, no traceback. Claude Code reads exit 1 as
    # non-blocking, so raising here would let the call through. No real Bash
    # tool call produces these shapes.
    tool_input = data.get("tool_input")
    if tool_input is None:
        tool_input = {}
    if not isinstance(tool_input, dict):
        kind = type(tool_input).__name__
        print(f"no_background: tool_input is {kind}, not an object; blocking", file=sys.stderr)
        return 2
    command = tool_input.get("command")
    if command is None:
        command = ""
    background = tool_input.get("run_in_background", False)
    if not isinstance(command, str) or not isinstance(background, (bool, str, int, float)):
        print(
            "no_background: command or run_in_background has the wrong type; blocking",
            file=sys.stderr,
        )
        return 2
    reason = check(command, run_in_background=background)
    if reason is None:
        return 0
    print(f"no_background blocked this Bash call ({reason}). {ADVICE}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
