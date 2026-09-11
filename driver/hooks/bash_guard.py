#!/usr/bin/env python3
"""bash_guard.py — PreToolUse hook for the hands DRIVER session.

Claude Code runs this before every Bash tool call. It reads the hook JSON on
stdin, extracts the command, and exits 2 (block, with the reason on stderr)
unless every command segment starts with an allowed word and the command
contains no way to write: no redirection, no tee, no in-place edits, no
interpreters, no direct `claude`. `hands open` is blocked too: it execs an
interactive `claude --resume`, which is a direct claude by another name.
Quoted text is stripped before inspection: prose inside quotes is text, but
$(...) and backticks inside double quotes are still executed and still checked.

Self-test: python3 bash_guard.py --selftest
"""
import json
import re
import sys

ALLOWED_FIRST_WORDS = {
    "hands",
    "cat", "ls", "jq", "pgrep", "sleep", "date", "echo", "head", "tail",
    "wc", "grep", "true", "false", "test", "[", "seq", "pwd", "which",
    "stat", "find", "diff", "sort", "uniq", "cut", "tr", "printf", "basename",
    "dirname", "realpath", "tty", "id", "whoami", "uptime",
}
ALLOWED_GIT_SUBCOMMANDS = {
    "fetch", "log", "show", "diff", "status", "ls-remote", "rev-parse",
    "cat-file", "ls-files", "ls-tree", "branch", "remote", "describe",
    "shortlog", "blame", "grep", "name-rev",
}
FORBIDDEN_GIT_FLAGS = {"--prune", "--delete", "-d", "-D", "-m", "-M",
                       "add", "set-url", "remove", "rename", "--set-upstream"}
# `hands open <job>` execs `claude --resume <id>` in the role's directory
# (DESIGN §7): an interactive session inside the driver's Bash call, and a way
# past the `claude` block. The driver reads jobs with show/log/tail instead.
FORBIDDEN_HANDS_SUBCOMMANDS = {"open"}
SHELL_KEYWORDS = {"for", "while", "until", "do", "done", "if", "then", "else",
                  "elif", "fi", "in", "break", "continue", "!", "{", "}", "("}

FORBIDDEN_PATTERNS = [
    (r"(?<![0-9&<>])>{1,2}(?!&[12])", "output redirection"),
    (r"\btee\b", "tee"),
    (r"\bsed\s+(-[a-zA-Z]*i|--in-place)", "sed -i"),
    (r"(^|[\s;&|(`])(rm|mv|cp|touch|mkdir|rmdir|chmod|chown|ln|truncate|dd|install)\b", "file mutation"),
    (r"(^|[\s;&|(`])(python3?|perl|ruby|node|bash|sh|zsh|eval|exec|source|xargs|env|sudo|su)\b", "interpreter or wrapper"),
    (r"(^|[^\w./-])claude\b", "direct claude"),
    (r"\bkill\b(?!\s+-0\b)", "kill other than -0"),
    (r"\bgit\b.*\b(push|commit|add|checkout|switch|reset|stash|rebase|merge|cherry-pick|revert|clean|worktree|config|tag|am|apply|restore|rm|mv|init|clone|pull)\b", "mutating git"),
]

SPLIT_RE = re.compile(r"\|\||&&|;|\||\n|\$\(|`|\(\s*")


class UnbalancedQuotes(Exception):
    pass


def strip_quoted(cmd: str) -> str:
    """Return the command with quoted text removed.

    Text inside single quotes is literal to bash and is dropped entirely.
    Inside double quotes only $(...) and `...` are executed, so those parts
    are kept and the rest is dropped. Unbalanced quotes raise: the shell
    would wait for more input, and the guard fails closed.
    """
    out = []
    i, n = 0, len(cmd)
    while i < n:
        c = cmd[i]
        if c == "\\" and i + 1 < n:
            i += 2
            continue
        if c == "'":
            j = cmd.find("'", i + 1)
            if j < 0:
                raise UnbalancedQuotes("single quote")
            out.append("''")
            i = j + 1
            continue
        if c == '"':
            j = i + 1
            kept = []
            while j < n and cmd[j] != '"':
                if cmd[j] == "\\" and j + 1 < n:
                    j += 2
                    continue
                if cmd.startswith("$(", j):
                    depth, k = 0, j
                    while k < n and cmd[k] != '"':
                        if cmd.startswith("$(", k):
                            depth += 1
                            k += 2
                            continue
                        if cmd[k] == ")":
                            depth -= 1
                            k += 1
                            if depth == 0:
                                break
                            continue
                        k += 1
                    kept.append(" " + cmd[j:k] + " ")
                    j = k
                    continue
                if cmd[j] == "`":
                    k = cmd.find("`", j + 1)
                    if k < 0 or k > cmd.find('"', j):
                        raise UnbalancedQuotes("backtick")
                    kept.append(" " + cmd[j:k + 1] + " ")
                    j = k + 1
                    continue
                j += 1
            if j >= n:
                raise UnbalancedQuotes("double quote")
            out.append('"' + "".join(kept) + '"')
            i = j + 1
            continue
        out.append(c)
        i += 1
    return "".join(out)


def strip_redirect_noise(cmd: str) -> str:
    # Allowed: 2>&1, 2>/dev/null, >/dev/null, 1>&2 — they write nothing.
    cmd = re.sub(r"\s*[12]?>\s*/dev/null", " ", cmd)
    cmd = re.sub(r"\s*[12]?>&[12]", " ", cmd)
    return cmd


def first_word(segment: str):
    words = segment.strip().split()
    if len(words) >= 2 and words[0] in ("for", "select"):
        words = words[2:]  # drop the loop variable
    while words and (words[0] in SHELL_KEYWORDS or words[0].endswith(";")):
        words = words[1:]
    # skip leading VAR=value assignments
    while words and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", words[0]):
        words = words[1:]
    return words


def check(cmd: str):
    """Return None if allowed, else a reason string."""
    try:
        bare = strip_quoted(cmd)
    except UnbalancedQuotes as e:
        return f"unbalanced quotes ({e}): {cmd!r}"
    noise_free = strip_redirect_noise(bare)
    for pat, why in FORBIDDEN_PATTERNS:
        if re.search(pat, noise_free):
            return f"{why}: {cmd!r}"
    for raw in SPLIT_RE.split(bare):
        words = first_word(raw)
        if not words:
            continue
        w = words[0].strip("()")
        if not w:
            continue
        # variable expansions / loop variables are not commands
        if w.startswith("$") or re.match(r"^\d+$", w):
            continue
        if w == "git":
            sub = None
            i = 1
            while i < len(words):
                if words[i] == "-C":
                    i += 2
                    continue
                if words[i].startswith("-"):
                    i += 1
                    continue
                sub = words[i]
                break
            if sub not in ALLOWED_GIT_SUBCOMMANDS:
                return f"git subcommand not allowed: {sub!r} in {cmd!r}"
            if any(f in words for f in FORBIDDEN_GIT_FLAGS):
                return f"git flag not allowed in {cmd!r}"
            continue
        if w == "hands":
            sub = next((x for x in words[1:] if not x.startswith("-")), None)
            if sub in FORBIDDEN_HANDS_SUBCOMMANDS:
                return f"hands {sub} starts an interactive session: {cmd!r}"
            continue
        if w == "kill":
            if len(words) < 2 or words[1] != "-0":
                return f"kill other than -0: {cmd!r}"
            continue
        if w not in ALLOWED_FIRST_WORDS:
            return f"command not allowed for the driver: {w!r} in {cmd!r}"
    return None


SELFTEST = [
    # (command, allowed?)
    ("git -C ./repo log --oneline -1", True),
    ("git -C ./repo fetch -q && git -C ./repo log --oneline origin/main -15", True),
    ("hands inbox --json", True),
    ("hands send --role builder --context clear 'Execute WORKPLAN.md run 2'", True),
    ("sleep 20; kill -0 \"$(pgrep -f handsd)\" && echo alive || echo dead", True),
    ("cat ~/.hands/jobs/0mtxb7ecx.json ~/.hands/inbox.jsonl", True),
    ("ls probe.txt 2>&1", True),
    ("jq -r '.result' ~/.hands/jobs/0mtxb7ecx.json", True),
    ("for i in $(seq 1 3); do echo $i; done", True),
    ("git -C ./repo show origin/main:meta/CHECKPOINT.md", True),
    ("git status 2>/dev/null", True),
    ("hands wait --for stop,held --timeout 3600", True),
    ("echo hi > probe.txt", False),
    ("echo hi >> probe.txt", False),
    ("cat x | tee probe.txt", False),
    ("sed -i 's/a/b/' CLAUDE.md", False),
    ("rm probe.txt", False),
    ("touch probe.txt", False),
    ("git -C ./repo push", False),
    ("git commit -m x", False),
    ("git -C ./repo fetch && git -C ./repo checkout main", False),
    ("git remote set-url origin x", False),
    ("claude -p 'hi'", False),
    ("python3 -c 'open(\"x\",\"w\")'", False),
    ("bash -c 'echo hi > x'", False),
    ("ls; kill 1234", False),
    ("echo $(rm -rf x)", False),
    ("cat file `touch x`", False),
    ("xargs rm < list", False),
    ("mkdir -p a", False),
    ("cp a b", False),
    ("mv a b", False),
    ("git -C ./repo branch -D main", False),
    ("git clone https://example.com/x", False),
    # prose inside quotes is text, not shell
    ("hands send --role builder --context clear --gate \"apply kit\" \"Apply ~/Downloads/k.zip (it replaces DESIGN.md), then commit 'plan: kit (v3.1)' and push. Reply: VERDICT: kit applied <sha>.\"", True),
    ("hands send --role aux --context clear 'Review commits since abc123; report blockers=0 or blockers>0 (count them)'", True),
    ("hands approve JOBID --human-confirmed --quote \"Approve job JOBID (my words)\"", True),
    ("echo \"a > b\"", True),
    ("echo \"a\" > b", False),
    ("echo 'it (works)'", True),
    # command substitution inside double quotes still executes
    ("hands send --role aux \"$(rm -rf x)\"", False),
    ("echo \"`touch x`\"", False),
    ("echo '$(rm -rf x)'", True),
    ("kill -0 \"$(jq -r .pid ~/.hands/jobs/0mtxb7ecx.json)\" && echo alive", True),
    # unbalanced quotes fail closed
    ("echo \"unterminated", False),
    ("hands send 'oops", False),
    ("hands show job-1 --json", True),
    ("hands log job-1", True),
    ("hands open job-1", False),
    ("hands --json open job-1", False),
    # stdin route
    ("hands send --role builder --context clear --stdin < ~/Downloads/m2-send.txt", True),
    ("cat ~/Downloads/m2-send.txt | hands send --role builder --context clear --stdin", True),
]


def selftest() -> int:
    bad = 0
    for cmd, expected in SELFTEST:
        reason = check(cmd)
        ok = (reason is None) == expected
        if not ok:
            bad += 1
            print(f"FAIL expected {'allow' if expected else 'block'}: {cmd}  -> {reason}")
    print(f"selftest: {len(SELFTEST) - bad}/{len(SELFTEST)} ok")
    return 1 if bad else 0


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        return selftest()
    try:
        data = json.load(sys.stdin)
    except Exception as e:  # malformed input: fail closed
        print(f"bash_guard: cannot parse hook input ({e}); blocking", file=sys.stderr)
        return 2
    if data.get("tool_name") != "Bash":
        return 0
    cmd = (data.get("tool_input") or {}).get("command", "")
    reason = check(cmd)
    if reason is None:
        return 0
    print(f"bash_guard blocked this command ({reason}). The driver may only run "
          f"hands, read-only git, and read-only inspection commands; "
          f"it never writes. If the task needs a write, say 'this is for aux' and stop.",
          file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
