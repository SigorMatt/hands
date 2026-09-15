#!/usr/bin/env python3
r"""bash_guard.py — PreToolUse hook for the hands DRIVER session.

Claude Code runs this before every Bash tool call. It reads the hook JSON on
stdin, extracts the command, and exits 2 (block, with the reason on stderr)
unless every command segment starts with an allowed word and the command
contains no way to write: no redirection, no tee, no in-place edits, no
interpreters, no direct `claude`. `hands open` is blocked too: it execs an
interactive `claude --resume`, which is a direct claude by another name.

What the shell delivers (DESIGN §28). The guard does not judge a quote-stripped
string: it splits the command into segments on every separator the shell obeys
outside quotes — `;`, `&&`, `||`, `|`, a lone `&`, newlines, subshell
parentheses — and on `$(` and backticks wherever they still execute (inside
double quotes too; a substitution is its own segment, and its place in the
word around it is a `$`). Each segment is tokenized with `shlex` in POSIX mode,
so `hands`, `git` and the rest are judged on the literal words they would
receive: `'--context=clear'`, `"--context=clear"` and `\--context=clear` are
all the option `--context=clear`. A command `shlex` cannot parse (unbalanced
quotes, a trailing backslash) or with an unterminated substitution is refused.
A backslash-newline is deleted first, as the shell deletes it.

For `hands` and `git` in both modes, a token in argument position that still
carries `$`, a backtick, `{`, `}`, `\`, `~` (not leading), `*`, `?`, `[` or
`!` where the shell would still expand it is refused, because the expansion
happens after the guard saw the word. "Where the shell would still expand it"
is bash's quoting: nothing inside single quotes and nothing escaped by a
backslash; inside double quotes only `$`, the backtick, `\` and `!` (§12 rule
6: quoted text is text). Two spellings the shell leaves literal are not
refused: a brace group of letters only (git's `HEAD^{commit}`; bash
brace-expands only a comma or `..` list), and a `~` inside a word that does
not follow `=` or `:` (git's `HEAD~1`; bash tilde-expands only a word's start
and after those two). Leading assignments (`x=… cmd`, and `x=…` alone) and
`$'…'` words are refused anywhere.

Every `git` token is checked against the read-only subcommand allowlist,
wherever it sits: a wrapper puts the real command in argument position, so
`find . -exec git remote add ... \;` is a `git remote add`. Git is an
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

Role mode (DESIGN §27, §28): with `HANDS_ROLE=driver` in the environment the
guard guards the driver ROLE, a headless session handsd starts to resolve one
consultation, and the allowlist narrows to §27's: read-only git (the table
above, with `-C <path>` the only option before the subcommand),
`hands show|jobs|inbox|pipeline|status|tail|kit check`, `hands send`, and
`hands resume`. A send carries exactly one `--context`, whose literal value is
`keep`, and exactly one `--role`, equal to `HANDS_CONSULT_ROLE` — the role the
consultation named, from the environment; with that variable unset or empty
no send passes. A send may not name `--project` or `--socket` (it goes to the
consultation's own project) or `--file` (it writes a file). Everything else is
refused, the `hands` subcommands by name: `approve`, `deny`, `pause`, `go`,
`put`, and every command word that is not `git` or `hands` — the read-only
inspection words above included, since §27 does not list them; the role reads
its clone with `git show`/`git grep`/`git cat-file`. argparse accepts an
unambiguous prefix of an option, so `--cont clear` is read as `--context
clear` and `--fi` as `--file`. Any other non-empty `HANDS_ROLE` fails closed.

Self-test: python3 bash_guard.py --selftest
"""
import json
import os
import re
import shlex
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
# Role mode (§28) accepts `-C <path>` alone.
GIT_PRE_FLAG_WITH_PATH = "-C"
GIT_ALLOWED_PRE_FLAGS = {"--no-pager"}
# `hands open <job>` execs `claude --resume <id>` in the role's directory
# (DESIGN §7): an interactive session inside the driver's Bash call, and a way
# past the `claude` block. The driver reads jobs with show/log/tail instead.
FORBIDDEN_HANDS_SUBCOMMANDS = {"open"}
# DESIGN §27/§28, role mode: the environment variables, the one mode value, and
# the allowlist. `send` and `kit` are judged by their arguments below.
ROLE_ENV = "HANDS_ROLE"
CONSULT_ROLE_ENV = "HANDS_CONSULT_ROLE"
DRIVER_ROLE = "driver"
ROLE_HANDS_SUBCOMMANDS = {"show", "jobs", "inbox", "pipeline", "status", "tail", "resume"}
ROLE_SEND_TARGETS = {"builder", "aux"}
# `hands` options that may precede the subcommand: two take a value, one does not.
HANDS_VALUE_OPTIONS = ("--project", "--socket")
HANDS_FLAG_OPTIONS = ("--json",)
SHELL_KEYWORDS = {"do", "done", "if", "then", "else", "elif", "fi", "while",
                  "until", "in", "break", "continue", "!", "{", "}"}

FORBIDDEN_PATTERNS = [
    # after `strip_redirect_noise`: every `>` left is a write, `2>f` and `&>f`
    # included (the old look-behind let a digit or `&` before `>` through)
    (r">{1,2}(?!&[12])", "output redirection"),
    (r"\btee\b", "tee"),
    (r"\bsed\s+(-[a-zA-Z]*i|--in-place)", "sed -i"),
    (r"(^|[\s;&|(`])(rm|mv|cp|touch|mkdir|rmdir|chmod|chown|ln|truncate|dd|install)\b", "file mutation"),
    (r"(^|[\s;&|(`])(python3?|perl|ruby|node|bash|sh|zsh|eval|exec|source|xargs|env|sudo|su)\b", "interpreter or wrapper"),
    (r"(^|[^\w./-])claude\b", "direct claude"),
    (r"\bkill\b(?!\s+-0\b)", "kill other than -0"),
]

# §28: the characters the shell may still expand in a word the guard has read.
RESIDUAL = frozenset("$`{}\\~*?[!")
# Inside double quotes bash still gives these their meaning; the rest of
# RESIDUAL is literal there.
DOUBLE_QUOTE_LIVE = frozenset("$`\\!")
# A brace group of letters only is never a brace expansion (that needs a comma
# or `..`): git's `HEAD^{commit}` and `HEAD^{}`.
BRACE_LITERAL = re.compile(r"\{[A-Za-z]*\}")
# Where bash tilde-expands inside a word: after `=` (an assignment-shaped
# argument, `a=~/x`) and, in assignments, after `:`.
TILDE_EXPANDED = re.compile(r"[=:]~")
SEPARATORS = frozenset(";&|\n()")
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\[[^\]]*\])?\+?=")
# The mark a substitution leaves in the word around it: a `$` the residual
# check sees.
SUBSTITUTED = "$_"


class UnbalancedQuotes(Exception):
    pass


class Refused(Exception):
    """The command cannot be judged as the shell would run it."""


def strip_quoted(cmd: str) -> str:
    """Return the command with quoted text removed.

    Used only for the FORBIDDEN_PATTERNS pass; the words are judged from the
    `shlex` tokens of `segments`. Text inside single quotes is literal to bash
    and is dropped entirely. Inside double quotes only $(...) and `...` are
    executed, so those parts are kept and the rest is dropped. Unbalanced
    quotes raise: the shell would wait for more input, and the guard fails
    closed.
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


def segments(cmd: str):
    """The command's segments as `(raw, mask)` string pairs (§28).

    A segment ends at every separator the shell obeys outside quotes: `;`,
    `&` (so `&&` and a lone `&`), `|`, a newline, `(` and `)`. The `&` of a
    redirection (`2>&1`, `&>`) is not a separator. `$(…)` and backticks, which
    execute outside single quotes, become segments of their own, scanned
    recursively, and leave `$_` in the word around them. `raw` is the segment
    as the shell reads it; `mask` is the same text with every RESIDUAL
    character the shell will not expand (single-quoted, backslash-escaped, or
    literal inside double quotes) replaced by `_`, so `shlex` splits both into
    the same words. Raises `Refused` for unbalanced quotes, a trailing
    backslash, an unterminated substitution and a `$'…'` word.
    """
    out: list[tuple[str, str]] = []
    _scan(cmd, 0, out, closer=None)
    return out


def _scan(cmd: str, i: int, out: list, closer):
    raw: list[str] = []
    mask: list[str] = []
    quote = None
    depth = 0
    after_redirect = False
    n = len(cmd)

    def put(r: str, m=None, redirect: bool = False) -> None:
        nonlocal after_redirect
        raw.append(r)
        mask.append(r if m is None else m)
        after_redirect = redirect

    def flush() -> None:
        out.append(("".join(raw), "".join(mask)))
        raw.clear()
        mask.clear()

    while i < n:
        c = cmd[i]
        nxt = cmd[i + 1] if i + 1 < n else ""
        if quote == "'":
            if c == "'":
                quote = None
                put(c)
            else:
                put(c, "_" if c in RESIDUAL else c)
            i += 1
            continue
        if c == "\\":
            if not nxt:
                raise Refused("a trailing backslash")
            if nxt == "\n":  # a line continuation: the shell deletes both
                i += 2
                continue
            if quote == '"':
                put(c + nxt)
            else:
                put(c + nxt, c + ("_" if nxt in RESIDUAL else nxt))
            i += 2
            continue
        if quote is None and c == "$" and nxt == "'":
            raise Refused("a $'…' word")
        if c == "`":
            j = i + 1
            while j < n and cmd[j] != "`":
                j += 2 if cmd[j] == "\\" else 1
            if j >= n:
                raise Refused("an unterminated backtick")
            # inside backticks `\\`, `\``, `\$` lose their backslash first
            _scan(re.sub(r"\\([\\`$])", r"\1", cmd[i + 1:j]), 0, out, closer=None)
            put(SUBSTITUTED)
            i = j + 1
            continue
        if c == "$" and nxt == "(":
            i = _scan(cmd, i + 2, out, closer=")")
            put(SUBSTITUTED)
            continue
        if quote == '"':
            if c == '"':
                quote = None
                put(c)
            else:
                put(c, c if c in DOUBLE_QUOTE_LIVE or c not in RESIDUAL else "_")
            i += 1
            continue
        if c in "'\"":
            quote = c
            put(c)
            i += 1
            continue
        if c == ")" and closer == ")" and depth == 0:
            flush()
            return i + 1
        if c in SEPARATORS:
            if c == "&" and (after_redirect or nxt == ">"):
                put(c)
                i += 1
                continue
            if c == "(":
                depth += 1
            elif c == ")" and depth > 0:
                depth -= 1
            flush()
            after_redirect = False
            i += 1
            continue
        put(c, redirect=c in "<>")
        i += 1
    if quote is not None:
        raise Refused(f"unbalanced {quote} quote")
    if closer is not None:
        raise Refused("an unterminated $(")
    flush()
    return n


def shell_words(text: str):
    """`shlex` POSIX words, split on the blanks bash splits on (not a carriage return)."""
    lex = shlex.shlex(text, posix=True)
    lex.whitespace_split = True
    lex.whitespace = " \t\n"
    lex.commenters = ""
    try:
        return list(lex)
    except ValueError as e:
        raise Refused(f"unparsable ({e})") from None


def tokens(raw: str, mask: str):
    """The segment's words and, index for index, their masks."""
    values, masks = shell_words(raw), shell_words(mask)
    if len(values) != len(masks):
        raise Refused("the words could not be read unambiguously")
    return values, masks


def residual(mask: str):
    """The expansion characters the shell would still act on in this word."""
    word = BRACE_LITERAL.sub(lambda m: "_" * len(m.group()), mask)
    found = sorted({c for c in word if c in RESIDUAL and c != "~"})
    if word.startswith("~"):
        word = word[1:]
    if TILDE_EXPANDED.search(word):
        found.append("~")
    return found


def residual_violation(values, masks, start: int, name: str, cmd: str):
    """Reason if a word after the `name` at `start` is expanded after the guard read it."""
    for value, mask in zip(values[start + 1:], masks[start + 1:], strict=True):
        found = residual(mask)
        if found:
            return (f"{name} argument {value!r} carries {' '.join(found)} the shell would "
                    f"expand after the guard read it (§28): {cmd!r}")
    return None


def command_start(values) -> int:
    """Index of the segment's command word, past shell keywords.

    `for NAME in WORDS` and `select NAME in WORDS` carry words, not a command:
    the whole segment is skipped (a substitution in the list is a segment of
    its own and is judged there).
    """
    i = 0
    if values and values[0] in ("for", "select"):
        if len(values) >= 3 and values[2] == "in":
            return len(values)
        i = 2
    while i < len(values) and values[i] in SHELL_KEYWORDS:
        i += 1
    return i


def git_subcommand(words, start: int, role=None):
    """Read the option area of the `git` at words[start - 1].

    Returns `(subcommand, index, refusal)`: the subcommand word and its index,
    or `refusal` set to the reason the option area is not acceptable. Only
    `-C <path>` and `--no-pager` may precede the subcommand (DESIGN §12/§21),
    and `-C`'s value must be a single path that does not begin with `-`: the
    word after `-C` used to be stepped over unjudged, which carried
    `git -C --exec-path=/tmp/evil log` through. In role mode (§28) only
    `-C <path>`.
    """
    pre_flags = set() if role == DRIVER_ROLE else GIT_ALLOWED_PRE_FLAGS
    i = start
    while i < len(words):
        w = words[i]
        if w == GIT_PRE_FLAG_WITH_PATH:
            if i + 1 >= len(words):
                return None, i, "`-C` with no path after it"
            value = words[i + 1]
            if value.startswith("-"):
                return None, i, (f"the `-C` value must be a single path that does "
                                 f"not begin with `-`, not {value!r}")
            i += 2
            continue
        if w in pre_flags:
            i += 1
            continue
        if w.startswith("-"):
            allowed = ("only `-C <path>` may come before a git subcommand in role mode"
                       if role == DRIVER_ROLE else
                       "only `-C <path>` and `--no-pager` may come before a git subcommand")
            return None, i, (f"git option before the subcommand not allowed: {w!r} "
                             f"({allowed}; `-c`, `--config-env` and the rest can "
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
    if not word.startswith("-") or word == "--":
        return None
    if word.split("=", 1)[0] in GIT_SUBCOMMAND_OPTIONS[sub]:
        return None
    if sub == "log" and re.fullmatch(r"-n?\d+", word):
        return None
    return word


def invocations(words, name):
    """Indexes of the tokens in `words` that invoke `name`.

    A bare `name` counts wherever it sits: a wrapper puts the real command in
    argument position (`find . -exec git push \\;`, `xargs git add`). A path
    ending in `/name` counts only as the segment's first word, because the
    human's workspace really is `~/git`: `ls ~/git` and `cat ~/git/x/DESIGN.md`
    name a directory, not a program, and a guard that refuses them is useless
    in a real driver session.
    """
    return [i for i, w in enumerate(words)
            if w == name or (i == 0 and w.endswith("/" + name))]


def git_violation(words, masks, cmd, role=None):
    """Reason if any `git` in this segment is not a read-only invocation.

    The allowlist applies to every `git` token, not only to a segment's first
    word: at the first word alone the check has a hole the width of every
    wrapper (review 3 blocker 1). The subcommand position of each invocation is
    what is read, so a revision (`<sha>^{commit}`) or a pattern
    (`log --grep=push`) is still a word, not a verb.
    """
    for i in invocations(words, "git"):
        reason = residual_violation(words, masks, i, "git", cmd)
        if reason:
            return reason
        sub, at, refusal = git_subcommand(words, i + 1, role)
        if refusal is not None:
            return f"{refusal} in {cmd!r}"
        if sub not in GIT_SUBCOMMAND_OPTIONS:
            return f"git subcommand not allowed: {sub!r} in {cmd!r}"
        listed = sorted(GIT_SUBCOMMAND_OPTIONS[sub])
        for w in words[at + 1:]:
            if w in MUTATING_GIT_ARGS:
                return f"git {sub} {w} writes: {cmd!r}"
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
            if w in FIND_ACTION_FLAGS:
                return w
    return None


def option_is(word: str, name: str) -> bool:
    """Does argparse read `word` (before any `=`) as the option `name`?

    argparse takes an unambiguous prefix of a long option as that option, so
    `--cont` is `--context`. Two dashes and at least one letter are required.
    """
    head = word.split("=", 1)[0]
    return len(head) > 2 and head.startswith("--") and name.startswith(head)


def option_values(args, name: str):
    """Every value given to the long option `name` in `args`, as argparse reads it."""
    values = []
    for i, a in enumerate(args):
        if not option_is(a, name):
            continue
        if "=" in a:
            values.append(a.split("=", 1)[1])
        else:
            values.append(args[i + 1] if i + 1 < len(args) else "")
    return values


def hands_subcommand(args):
    """Index of the subcommand in `hands`' arguments, past the global options
    and the values `--project`/`--socket` take (§28: values read from tokens)."""
    i = 0
    while i < len(args):
        a = args[i]
        if any(option_is(a, name) for name in HANDS_VALUE_OPTIONS):
            i += 1 if "=" in a else 2
            continue
        if any(option_is(a, name) for name in HANDS_FLAG_OPTIONS):
            i += 1
            continue
        break
    return i


def hands_violation(words, masks, cmd, role=None, consult_role=None):
    """Reason this `hands` invocation (words[0]) is refused, or None."""
    reason = residual_violation(words, masks, 0, "hands", cmd)
    if reason:
        return reason
    args = words[1:]
    i = hands_subcommand(args)
    if role != DRIVER_ROLE:
        sub = next((a for a in args[i:] if not a.startswith("-")), None)
        if sub in FORBIDDEN_HANDS_SUBCOMMANDS:
            return f"hands {sub} starts an interactive session: {cmd!r}"
        return None
    if i >= len(args) or args[i].startswith("-"):
        got = args[i] if i < len(args) else "nothing"
        return f"hands needs an allowed subcommand in role mode, got {got!r}: {cmd!r}"
    sub, rest = args[i], args[i + 1:]
    if sub in ROLE_HANDS_SUBCOMMANDS:
        return None
    if sub == "kit":
        if rest and rest[0] == "check":
            return None
        return f"only `hands kit check` is allowed in role mode: {cmd!r}"
    if sub == "send":
        return send_violation(args, rest, cmd, consult_role)
    return (f"hands {sub} is not allowed for the driver role (§27: show, jobs, inbox, "
            f"pipeline, status, tail, kit check, send --context keep, resume): {cmd!r}")


def send_violation(args, rest, cmd, consult_role):
    """§28: a role-mode send carries exactly one `--context`, literally `keep`,
    and exactly one `--role`, equal to HANDS_CONSULT_ROLE."""
    if not consult_role:
        return (f"role mode sends only to the role the consultation named, and "
                f"{CONSULT_ROLE_ENV} is not set: {cmd!r}")
    if any(option_is(a, "--file") for a in rest):
        return f"hands send --file writes a file, refused in role mode: {cmd!r}"
    for name in HANDS_VALUE_OPTIONS:
        if any(option_is(a, name) for a in args):
            return (f"hands send {name} leaves the consultation's project, refused in "
                    f"role mode: {cmd!r}")
    contexts = option_values(rest, "--context")
    if contexts != ["keep"]:
        return (f"role mode sends with exactly one --context, and it is keep (§27, §28), "
                f"got {contexts or 'no --context'}: {cmd!r}")
    roles = option_values(rest, "--role")
    if roles != [consult_role] or consult_role not in ROLE_SEND_TARGETS:
        return (f"role mode sends keep only to the role the consultation named "
                f"({CONSULT_ROLE_ENV}={consult_role!r}, §28), got "
                f"{roles or 'no --role'}: {cmd!r}")
    return None


def judge(values, masks, cmd, role, consult_role):
    """Reason this segment's words are refused, or None."""
    at = command_start(values)
    words, marks = values[at:], masks[at:]
    if not words:
        return None
    if ASSIGNMENT.match(words[0]):
        return f"a leading assignment ({words[0]!r}) is refused (§28): {cmd!r}"
    reason = git_violation(words, marks, cmd, role)
    if reason:
        return reason
    action = find_action(words)
    if action:
        return f"find {action}: {cmd!r}"
    w = words[0]
    if role == DRIVER_ROLE:
        if w == "git":
            return None  # every git token was checked above
        if w != "hands":
            return f"command not allowed for the driver role (§27): {w!r} in {cmd!r}"
        return hands_violation(words, marks, cmd, role, consult_role)
    if w == "git":
        return None
    if w == "hands":
        return hands_violation(words, marks, cmd)
    if w == "kill":
        if len(words) < 2 or words[1] != "-0":
            return f"kill other than -0: {cmd!r}"
        return None
    if w not in ALLOWED_FIRST_WORDS:
        return f"command not allowed for the driver: {w!r} in {cmd!r}"
    return None


def check(cmd: str, role=None, consult_role=None):
    """Return None if allowed, else a reason string.

    `role` is `HANDS_ROLE`: None for the human's driver session, `driver` for
    §27's role mode, and anything else is refused outright (fail closed).
    `consult_role` is `HANDS_CONSULT_ROLE`, read only in role mode.
    """
    if role is not None and role != DRIVER_ROLE:
        return f"unknown {ROLE_ENV} {role!r} (only {DRIVER_ROLE!r} is a mode): {cmd!r}"
    try:
        bare = strip_quoted(cmd)
    except UnbalancedQuotes as e:
        return f"unbalanced quotes ({e}): {cmd!r}"
    noise_free = strip_redirect_noise(bare)
    for pat, why in FORBIDDEN_PATTERNS:
        if re.search(pat, noise_free):
            return f"{why}: {cmd!r}"
    try:
        for raw, mask in segments(cmd):
            values, masks = tokens(raw, mask)
            reason = judge(values, masks, cmd, role, consult_role)
            if reason:
                return reason
    except Refused as e:
        return f"{e}, refused (§28): {cmd!r}"
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
    # §28: review 11's probes, as the human's session judges them. `go`,
    # `approve`, a clear send and `--file` are the human session's to run, so
    # only the probes §28 refuses in both modes (and `open`) are blocked here;
    # ROLE_SELFTEST blocks every one.
    ("hands show x & hands go", True),
    ("hands jobs & hands approve j1 --human-confirmed --quote yes", True),
    ("hands show & hands open x", False),
    ("hands send --role builder --context keep '--context=clear' m", True),
    ("hands send --role builder --context keep \"--context=clear\" m", True),
    ("hands send --role builder --context keep \\--context=clear m", True),
    ("hands send --role builder --context keep $'--context=clear' m", False),
    ("hands send --role builder --context keep {--context=clear,m}", False),
    ("x=--context=clear; hands send --role builder --context keep $x m", False),
    ("hands send --role builder --context keep '--file' a=b m", True),
    ("hands send --role builder --context keep \\--file a=b m", True),
    ("hands send --role aux --context keep m", True),
    ("hands send --project other --role builder --context keep m", True),
    ("hands --project other send --role builder --context keep m", True),
    ("hands send --role builder --context keep --project=other m", True),
    ("hands send --role builder --context keep --socket /tmp/other.sock m", True),
    # §28: the words the shell delivers, not a quote-stripped string
    ("hands --project x open y", False),
    ("git status & git push", False),
    ("git log $x", False),
    ("git log -- '*.py'", True),
    ("git -C ./repo diff --stat HEAD~1", True),
    ("GIT_PAGER=touch git log", False),
    ("git status 2>probe.txt", False),
    ("git status &> probe.txt", False),
    ("$SHELL -c 'git push'", False),
]


# The role the consultation named, as the self-test's HANDS_CONSULT_ROLE.
SELFTEST_CONSULT_ROLE = "builder"

# Role mode (§27, §28): `check(cmd, role="driver", consult_role="builder")`.
ROLE_SELFTEST = [
    ("git -C ./repo log --oneline -5", True),
    ("git -C ./repo rev-parse HEAD^{commit}", True),
    ("hands show job-1 --json", True),
    ("hands send --role builder --context keep 'Answer per DESIGN §27.'", True),
    ("hands send --role=builder --context=keep 'Answer per DESIGN §27.'", True),
    ("hands kit check ~/Downloads/kit.zip", True),
    ("hands resume", True),
    ("hands send --role builder --context clear 'Execute run 2'", False),
    ("hands approve job-1 --human-confirmed --quote 'yes'", False),
    ("hands go", False),
    ("cat ./repo/DESIGN.md", False),
    ("echo x > f", False),
    ("git --no-pager log --oneline -3", False),
    # §28: every probe review 11 executed
    ("hands show x & hands go", False),
    ("hands jobs & hands approve j1 --human-confirmed --quote yes", False),
    ("hands show & hands open x", False),
    ("hands send --role builder --context keep '--context=clear' m", False),
    ("hands send --role builder --context keep \"--context=clear\" m", False),
    ("hands send --role builder --context keep \\--context=clear m", False),
    ("hands send --role builder --context keep $'--context=clear' m", False),
    ("hands send --role builder --context keep {--context=clear,m}", False),
    ("x=--context=clear; hands send --role builder --context keep $x m", False),
    ("hands send --role builder --context keep '--file' a=b m", False),
    ("hands send --role builder --context keep \\--file a=b m", False),
    ("hands send --role aux --context keep m", False),
    ("hands send --project other --role builder --context keep m", False),
    ("hands --project other send --role builder --context keep m", False),
    ("hands send --role builder --context keep --project=other m", False),
    ("hands send --role builder --context keep --socket /tmp/other.sock m", False),
]


def selftest() -> int:
    bad = 0
    cases = [(cmd, expected, None) for cmd, expected in SELFTEST]
    cases += [(cmd, expected, DRIVER_ROLE) for cmd, expected in ROLE_SELFTEST]
    for cmd, expected, role in cases:
        reason = check(cmd, role=role, consult_role=SELFTEST_CONSULT_ROLE)
        ok = (reason is None) == expected
        if not ok:
            bad += 1
            mode = f" [{ROLE_ENV}={role}]" if role else ""
            print(f"FAIL expected {'allow' if expected else 'block'}{mode}: {cmd}  -> {reason}")
    print(f"selftest: {len(cases) - bad}/{len(cases)} ok")
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
    role = os.environ.get(ROLE_ENV) or None
    consult_role = os.environ.get(CONSULT_ROLE_ENV) or None
    reason = check(cmd, role=role, consult_role=consult_role)
    if reason is None:
        return 0
    if role is not None:
        print(f"bash_guard blocked this command ({reason}). The driver role may only run "
              f"read-only git, hands show|jobs|inbox|pipeline|status|tail|kit check, "
              f"hands send --context keep to the role the consultation named "
              f"(${CONSULT_ROLE_ENV}), and hands resume (§27, §28). "
              f"If the consultation needs more, reply VERDICT: escalate <reason>.",
              file=sys.stderr)
        return 2
    print(f"bash_guard blocked this command ({reason}). The driver may only run "
          f"hands, read-only git, and read-only inspection commands; "
          f"it never writes. If the task needs a write, say 'this is for aux' and stop.",
          file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
