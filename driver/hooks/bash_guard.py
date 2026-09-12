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
Every `git` token is checked against the read-only subcommand allowlist,
wherever it sits: a wrapper puts the real command in argument position, so
`find . -exec git remote add ... \\;` is a `git remote add`. Git is an
allowlist of options per subcommand (DESIGN §12): each allowed subcommand
carries the exact options the driver needs, and any token beginning with `-`
that its row does not list is refused. That is the whole policy — a wrapper
option (`--upload-pack=`, `--exec=`, `--output`, `--ext-diff`, `--textconv`,
`--config-env`, `--edit-description`) is refused because it is not listed,
not because someone remembered to name it; denylists of git options lost
three rounds. No option whose value names a program or a file is listed.
Before the subcommand only `-C <path>` and `--no-pager` are accepted, and the
`-C` value is a single path that may not begin with `-`. Revisions, `rev:path`
and paths carry no leading dash, so `rev-parse <sha>^{commit}`,
`show origin/main:x` and `grep -e x -- docs` still read. A path token is not
an invocation — the human's workspace is `~/git`, and `ls ~/git` is a read.
`find` with `-exec`, `-execdir`, `-ok`, `-okdir` or `-delete` is forbidden
outright: those run commands (or delete) whatever the payload looks like, and
`-fprint`, `-fprint0`, `-fprintf` and `-fls` write a file at any path.

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
# DESIGN §12: the table from allowed subcommand to allowed options. A
# subcommand that is not a key is refused; for one that is, every token
# beginning with `-` that the row does not list is refused. The rows carry the
# exact options the driver needs and nothing else — in particular no option
# whose value names a program to run (`--upload-pack`, `--exec`, `--ext-diff`,
# `--textconv`, `--config-env`, `--edit-description`) or a file to write
# (`--output`, `-O`, `--open-files-in-pager`). The remaining surface is these
# options themselves.
GIT_SUBCOMMAND_OPTIONS = {
    "log": frozenset({"--oneline", "-n", "--grep", "--format", "--stat",
                      "--name-status"}),
    "show": frozenset({"--stat", "--name-status"}),
    "fetch": frozenset({"-q"}),
    "ls-remote": frozenset({"--heads", "--tags"}),
    "rev-parse": frozenset({"--verify", "--short"}),
    "diff": frozenset({"--stat", "--name-status", "--name-only"}),
    "grep": frozenset({"-n", "-c", "-l", "-i", "-e"}),
    "cat-file": frozenset({"-t", "-p", "-e"}),
    "ls-files": frozenset(),
    "ls-tree": frozenset(),
    "branch": frozenset({"--list"}),
    "remote": frozenset({"-v"}),
    "status": frozenset(),
}
# Not options, so the option allowlist cannot see them: the second word of an
# allowed subcommand can still be a mutating verb (`git remote add`,
# `git remote set-url`). Those stay refused by name.
MUTATING_GIT_ARGS = {"add", "set-url", "remove", "rename"}
# `find` runs a command per match (`-exec`, `-execdir`, `-ok`, `-okdir`),
# deletes (`-delete`) or writes its listing to a named file (`-fprint`,
# `-fprint0`, `-fprintf`, `-fls`). The payload is irrelevant: the flag is the
# write. `-print`/`-printf`/`-ls` write to stdout and are reads.
FIND_ACTION_FLAGS = {"-exec", "-execdir", "-ok", "-okdir", "-delete",
                     "-fprint", "-fprint0", "-fprintf", "-fls"}
# DESIGN §12/§21: before the subcommand only `-C <path>` and `--no-pager` are
# accepted; every other leading option is refused. `-c`, `--config-env`,
# `--exec-path`, `--git-dir` and friends each turn an allowlisted subcommand
# into something else — `git -c core.pager=touch log` runs `touch`. `-C`'s
# value is a single path: git itself takes it as the next word (`-C./x` and
# `-C=./x` are both "unknown option" to git 2.43), and it may not begin with
# `-`, or `git -C --exec-path=/tmp/evil log` would ride through unjudged.
GIT_PRE_FLAG_WITH_PATH = "-C"
GIT_ALLOWED_PRE_FLAGS = {"--no-pager"}
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


def git_subcommand(words, start: int):
    """Read the option area of the `git` at words[start - 1].

    Returns `(subcommand, index, refusal)`: the subcommand word and its index,
    or `refusal` set to the reason the option area is not acceptable. Only
    `-C <path>` and `--no-pager` may precede the subcommand (DESIGN §12/§21),
    and `-C`'s value must be a single path that does not begin with `-`: the
    word after `-C` used to be stepped over unjudged, which carried
    `git -C --exec-path=/tmp/evil log` through.
    """
    i = start
    while i < len(words):
        w = words[i].strip("()")
        if w == GIT_PRE_FLAG_WITH_PATH:
            if i + 1 >= len(words):
                return None, i, "`-C` with no path after it"
            value = words[i + 1].strip("()")
            if value.startswith("-"):
                return None, i, (f"the `-C` value must be a single path that does "
                                 f"not begin with `-`, not {value!r}")
            i += 2
            continue
        if w in GIT_ALLOWED_PRE_FLAGS:
            i += 1
            continue
        if w.startswith("-"):
            return None, i, (f"git option before the subcommand not allowed: {w!r} "
                             f"(only `-C <path>` and `--no-pager` may come before a "
                             f"git subcommand; `-c`, `--config-env` and the rest can "
                             f"make a read-only subcommand run a command)")
        return w, i, None
    return None, len(words), None


def unlisted_git_option(sub: str, word: str):
    """The post-subcommand token this subcommand's row does not list, or None.

    Only a token beginning with `-` is judged: a revision, a `rev:path` and a
    path carry no leading dash, and `--` separates paths from revisions. An
    option is allowed only if `GIT_SUBCOMMAND_OPTIONS[sub]` lists it, with
    `--grep=push` counting as `--grep`; for `log` alone, `-10` and `-n10` are
    the `-n` shorthand, which is what `driver/CLAUDE.md` itself tells the
    driver to run (`log --oneline origin/BRANCH -10`). Everything else is
    refused because it is not listed — including every option that names a
    program to run or a file to write.
    """
    w = word.strip("()")
    if not w.startswith("-") or w == "--":
        return None
    if w.split("=", 1)[0] in GIT_SUBCOMMAND_OPTIONS[sub]:
        return None
    if sub == "log" and re.fullmatch(r"-n?\d+", w):
        return None
    return w


def invocations(words, name):
    """Indexes of the tokens in `words` that invoke `name`.

    A bare `name` counts wherever it sits: a wrapper puts the real command in
    argument position (`find . -exec git push \\;`, `xargs git add`). A path
    ending in `/name` counts only as the segment's first word, because the
    human's workspace really is `~/git`: `ls ~/git` and `cat ~/git/x/DESIGN.md`
    name a directory, not a program, and a guard that refuses them is useless
    in a real driver session.
    """
    out = []
    for i, w in enumerate(words):
        bare = w.strip("()")
        if bare == name or (i == 0 and bare.endswith("/" + name)):
            out.append(i)
    return out


def git_violation(words, cmd):
    """Reason if any `git` in this segment is not a read-only invocation.

    The allowlist applies to every `git` token, not only to a segment's first
    word: at the first word alone the check has a hole the width of every
    wrapper (review 3 blocker 1). The subcommand position of each invocation is
    what is read, so a revision (`<sha>^{commit}`) or a pattern
    (`log --grep=push`) is still a word, not a verb.
    """
    for i in invocations(words, "git"):
        sub, at, refusal = git_subcommand(words, i + 1)
        if refusal is not None:
            return f"{refusal} in {cmd!r}"
        if sub not in GIT_SUBCOMMAND_OPTIONS:
            return f"git subcommand not allowed: {sub!r} in {cmd!r}"
        listed = sorted(GIT_SUBCOMMAND_OPTIONS[sub])
        for w in words[at + 1:]:
            bare = w.strip("()")
            if bare in MUTATING_GIT_ARGS:
                return f"git {sub} {bare} writes: {cmd!r}"
            opt = unlisted_git_option(sub, w)
            if opt is not None:
                return (f"git option not allowed for {sub!r}: {opt!r} in {cmd!r} "
                        f"(policy: DESIGN §12 lists the options each subcommand may "
                        f"carry — `{sub}` takes "
                        f"{', '.join(listed) if listed else 'no options'} — and every "
                        f"other option is refused because it is not listed)")
    return None


def find_action(words):
    """The `find` action flag in this segment, or None.

    `-exec`/`-execdir`/`-ok`/`-okdir` run a command per match and `-delete`
    removes files; a `find` without one of them only prints.
    """
    for i in invocations(words, "find"):
        for w in words[i + 1:]:
            if w.strip("()") in FIND_ACTION_FLAGS:
                return w.strip("()")
    return None


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
        reason = git_violation(words, cmd)
        if reason:
            return reason
        action = find_action(words)
        if action:
            return f"find {action}: {cmd!r}"
        w = words[0].strip("()")
        if not w:
            continue
        # variable expansions / loop variables are not commands
        if w.startswith("$") or re.match(r"^\d+$", w):
            continue
        if w == "git":
            continue  # every git token was checked above
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
    # a mutating verb is a verb only in the subcommand position: these read
    ("git -C ./repo rev-parse 8448b6f^{commit}", True),
    ("git -C ./repo rev-parse --verify HEAD^{commit}", True),
    ("git -C ./repo show 861097f^{commit} --stat", True),
    ("git log --grep=commit -5", True),
    ("git -C ./repo log --oneline --grep=push -20", True),
    # ... and these still write, wherever the verb hides
    ("git -c user.name=x commit -m y", False),
    ("git --git-dir=./repo/.git push origin main", False),
    ("git -C ./repo log --oneline -1 && git -C ./repo push", False),
    ("git -C ./repo status; git -C ./repo add -A", False),
    ("find . -name x -exec git push \\;", False),
    # ... and an option can be the write, with no verb at all (§21)
    ("git -c core.pager=vim log --oneline", False),
    ("git -c diff.external=cat diff", False),
    ("git --exec-path=/tmp/evil log", False),
    ("git diff --output /tmp/out", False),
    ("git show HEAD:x --textconv", False),
    ("git grep -Oless pattern", False),
    ("find . -type f -fprintf /tmp/list %p", False),
    ("find . -fls /tmp/listing", False),
    ("git --no-pager log --oneline -3", True),
    ("git --no-pager -C ./repo show HEAD --stat", True),
    ("find . -name '*.md' -printf %p", True),
    # ... and under the per-subcommand allowlist (§12) an option is refused
    # simply because its subcommand's row does not list it. These read, and
    # are refused anyway; the wrappers below are refused the same way, which
    # is the point — nobody has to have remembered them.
    ("git -C ./repo diff --no-ext-diff HEAD~1", False),
    ("git log --no-textconv -1", False),
    ("git status --porcelain", False),
    ("git branch -a", False),
    ("git ls-remote --upload-pack='touch /tmp/x/PWNED1' /tmp/x/src", False),
    ("git -C ./src fetch --upload-pack='touch /tmp/x/PWNED2' /tmp/x/src", False),
    ("git fetch --exec='touch /tmp/x/PWNED3' origin", False),
    ("git ls-remote --exec='touch /tmp/x/PWNED3' origin", False),
    ("git branch --edit-description", False),
    ("git fetch --force origin main:main", False),
    # the `-C` value is a single path and may not begin with `-`
    ("git -C ./repo -C --exec-path=/tmp/evil log", False),
    ("git -C --exec-path=/tmp/evil log", False),
    # the options each subcommand does carry, including the lines
    # driver/CLAUDE.md itself tells the driver to run
    ("git -C ./repo fetch && git -C ./repo log --oneline origin/main -10", True),
    ("git -C ./repo log --format=%H --name-status -n 5", True),
    ("git -C ./repo show --name-status HEAD", True),
    ("git ls-remote --heads origin", True),
    ("git -C ./repo rev-parse --short HEAD", True),
    ("git -C ./repo diff --stat --name-only HEAD~1", True),
    ("git -C ./repo grep -n -i -e pattern origin/main -- docs", True),
    ("git -C ./repo cat-file -p HEAD:DESIGN.md", True),
    ("git -C ./repo ls-files", True),
    ("git -C ./repo ls-tree HEAD", True),
    ("git -C ./repo branch --list", True),
    ("git -C ./repo remote -v", True),
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
    # the file routes: the prompt itself never reaches the command line (§4)
    ("hands send --role builder --context clear --prompt-file ~/Downloads/m3-kickoff.txt", True),
    ("hands send --role aux --context clear --prompt-file ./repo/meta/REVIEW-2.md --json", True),
    ("hands send --role builder --context keep --prompt-file ~/hands-driver/hands/answer.txt", True),
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
