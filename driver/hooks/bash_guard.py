#!/usr/bin/env python3
r"""bash_guard.py — PreToolUse hook for the hands DRIVER session.

Claude Code runs this before every Bash call. It reads the hook JSON on stdin,
takes the command out of it, and exits 2 (block, with the reason on stderr)
unless every command segment is one of the commands the table below lists,
carrying only the options that command's row lists. What is allowed is exactly
that: `hands` and read-only `git` by their own tables, and `cat`, `ls`, `head`,
`tail`, `wc`, `grep`, `jq`, `pgrep`, `sleep`, `date`, `echo` and `kill -0` with
the options §31 gives them. No listed option takes a value that names a program
to run or a file to write, and the language below (§32) has no expansion,
control flow or redirection, so an allowed segment runs a table command with
table options and nothing else. A word the table does not list is
refused by name. `hands open` is blocked too: it execs an interactive
`claude --resume`, which is a direct claude by another name.

The command table (DESIGN §31). Until v3.14 the words outside `git` and `hands`
were a bare set with no option table at all, and `sort -o F`, `uniq A B` and
`sort --compress-program=P` wrote a file, wrote a file and ran a program
(REVIEW-14 blocker 1, H-028). `COMMAND_TABLE` replaces
that set: `sort`, `uniq`, `cut`, `tr`, `find`, `stat`, `diff`, `printf`,
`basename`, `dirname`, `realpath`, `tty`, `id`, `whoami`, `uptime`, `which`,
`test`, `[`, `seq`, `true`, `false` and `pwd` left it. `tee`, an in-place
`sed`, an interpreter, a file mutation and a direct `claude` are refused by
name as well, wherever in the command they are written.

The guard's language (DESIGN §30, §32). The driver's shell is one line of
words and quotes, not a script. Before any tokenizing the guard refuses a
command that contains any of these, in any position, quoted or not:
- a newline, a carriage return, or any other control character (Unicode
  category Cc);
- `<`, `>`, `#`, a backtick, `\`, `$`, `{` or `}`;
- a `!` inside double quotes, and an unquoted `(` joined to the word before it
  (`@(…)`, `+(…)`: an extglob pattern, not a plain word);
- a reserved word of the shell appearing as a word: `for while until if then
  else elif fi do done case esac select function in time coproc ! [[ ]]`.
"As a word" is as bash splits words: outside quotes, on spaces and on
`; & | ( )`. A quoted reserved word (`grep -e 'done' f`) is text, because bash
never reads a quoted word as a reserved one; the unquoted spelling, the only one
bash acts on, is refused, so the language has no control flow either way.
The refusal names the first offending character and its position, or the
reserved word and its position, and an unbalanced quote is refused at the
position where it opened. What is left is words, '…'/"…" quotes and the
separators `; && || | &`: no expansion, no control flow, no redirection and no
comment, so a segment the guard allows runs only a table command with table
options.

The command splits into segments on `;`, `&` (which covers `&&` and a lone
`&`), `|` (which covers `||`) and parentheses, all outside quotes. Each segment
is tokenized with `shlex` in POSIX mode, so `hands`, `git` and the rest are
judged on the literal words they would receive: `'--context=clear'` and
`"--context=clear"` are both the option `--context=clear`.

Every word after a segment's command word, in every row and every mode, must
be a plain word (§28, §32): one the shell does not expand after the guard read
it. With `$` and braces gone, that means no unquoted `*`, `?`, `[` or `!`, and
no unquoted `~` after `=` or `:` (a leading `~` is a home directory, never an
option). `tail -n 5 *` is refused because bash would make `*` a file named
`-f`. Leading assignments are refused anywhere: `x=… cmd`, and `x=…` alone.

Every `git` token is checked against the read-only subcommand allowlist,
wherever it sits. A wrapper puts the real command in argument position, so
`find . -exec git remote add ... ';'` is a `git remote add`.

Git is an allowlist of options per subcommand (DESIGN §12). Each allowed
subcommand carries the exact options the driver needs, and any token
beginning with `-` that its row does not list is refused. That is the whole
policy. A wrapper option (`--upload-pack=`, `--exec=`, `--output`,
`--ext-diff`, `--textconv`, `--config-env`, `--edit-description`) is refused
because it is not listed, not because someone remembered to name it; denylists
of git options lost three rounds. No listed option takes a value that names a
program or a file.

Before the subcommand only `-C <path>` and `--no-pager` are accepted. The
`-C` value is a single path that may not begin with `-`. Revisions, `rev:path`
and paths carry no leading dash, so `rev-parse <sha>^0`,
`show origin/main:x` and `grep -e x -- docs` still read. A path token is not
an invocation: the human's workspace is `~/git`, and `ls ~/git` is a read.

`find` is not a row of the command table, so a `find` at the head of a segment
is refused by name (§31). A `find` in argument position — a wrapper shape — is
judged as the `git` tokens are: `-exec`, `-execdir`, `-ok` and `-okdir` run
commands, `-delete` deletes, and `-fprint`, `-fprint0`, `-fprintf` and `-fls`
write a file at any path, so any of them refuses the segment.

Role mode (DESIGN §27, §28, §31). With `HANDS_ROLE=driver` in the environment,
the guard guards the driver ROLE, a headless session handsd starts to resolve
one consultation. It is the same command table, minus the `hands` subcommands
§27 withholds:
- read-only git, by the table above, with `-C <path>` the only option allowed
  before the subcommand, pinned to the role's clone;
- `hands show|jobs|inbox|pipeline|status|tail|kit check`;
- `hands send`, judged below;
- `hands resume`;
- the read-only inspection rows of the table (`cat`, `ls`, `head`, `tail`,
  `wc`, `grep`, `jq`, `pgrep`, `sleep`, `date`, `echo`, `kill -0`), with the
  options their rows list. Before v3.14 role mode refused these, because §27
  lists only the `hands` and `git` surface; §31 makes role mode the same table
  as the human's session, so the role reads its clone with `cat` and `grep` as
  well as with `git show`, `git grep` and `git cat-file`.

`git -C <path>` is pinned to the role's clone (§29, §30):
- The value's `os.path.realpath` must equal `HANDS_CLONE`'s. Symlinks and `..`
  resolve as the kernel resolves them, and a relative path joins the hook's
  working directory, which is the role's cwd.
- No `~` is expanded, so `-C ~/x` fails closed unless `HANDS_CLONE` is spelled
  the same.
- A second `-C` is refused, because git applies each `-C` relative to the one
  before it.
- With `HANDS_CLONE` unset or empty, every `git -C` is refused.
A `git` without `-C` runs in the role's cwd and is judged by the table alone.

Reads are confined (§32, review 15 should-fix 7). In role and architect mode
every path a row reads must be under the clone (`HANDS_CLONE`) or the spool's
own directory, `~/.hands/<project>/` — and, in architect mode only, under
`HANDS_KITS` — decided as `git -C` is: `os.path.realpath` containment, a
relative path joined to the hook's working directory (for `git`, to its `-C`
value), and a leading unquoted `~` expanded as bash expands it. The paths are:
every file word of `cat`, `head`, `tail`, `wc`; `ls`'s words, or `.` when it
has none; `grep`'s file words (all words when `-e` gives the pattern), or `.`
under `-r` with none; `jq`'s words after its filter; every `git` word after the
subcommand that is not an option (git reads a path outside the repository
through `diff`, and another repository through `fetch`/`ls-remote`); and `hands`'
`--prompt-file`, `--socket`, `--repo` values and the kit a `kit check|file`
names. A read with no path reads stdin, which in this language only a pipe from
another judged segment fills, and is allowed. The role's environment names no
spool, so the guard finds the project the way `hands` does — `$HANDS_PROJECT`,
else the only `~/.hands/*.toml` — and with neither (or a name outside
`[A-Za-z0-9][A-Za-z0-9._-]{0,63}`) no spool is named. A root that is unset or
empty confines nothing, so with none every path read is refused. A role's `jq`
filter may not name `env`, which reads the environment as `/proc/self/environ`
would. Normal mode's reads are not confined.

A send carries exactly one `--context`, whose literal value is `keep`, and
exactly one `--role`, equal to `HANDS_CONSULT_ROLE`: the role the consultation
named, taken from the environment. With that variable unset or empty, no send
passes. A send may not name `--project` or `--socket` (it goes to the
consultation's own project) or `--file` (it writes a file). argparse accepts
an unambiguous prefix of an option, so the guard reads `--cont clear` as
`--context clear` and `--fi` as `--file`.

Everything else is refused. That covers the `hands` subcommands, by name
(`approve`, `deny`, `pause`, `go`, `put`), every `git` option the subcommand
table does not list, and every command word the table does not carry. Any
other non-empty `HANDS_ROLE` fails closed.

Architect mode (DESIGN §31, §32, H-029, H-030). With `HANDS_ROLE=architect` the guard
guards the architect ROLE, a headless session handsd starts to write one kit:
- the read-only rows of the table above, and read-only `git` with `-C` pinned
  to `HANDS_CLONE` exactly as role mode pins it;
- `hands kit check` and `hands kit file`, plus the reads
  `hands show|jobs|inbox|pipeline|status`. That is the `hands` surface
  `architect/settings.json` — the role's own shipped instruction — allows, so
  `tail` is not in it and `resume` (which those settings deny outright) is not
  either. Never `send`, `approve`, `deny`, `go`, `put`, `pause`, `open`, and
  never a push: the clone's push URL is disabled as the driver's is;
- `mkdir`, `cp` and `mv` — `KITS_TABLE`, this mode's rows and no other
  mode's — with **every path argument** under `HANDS_KITS` and only the
  options a staged directory kit needs: `mkdir -p`, `cp -r`, and `mv` with
  none. No listed option names another path or makes a link, so `cp -t`,
  `--target-directory`, `-S`/`--suffix`, `-b`/`--backup`, `-s`, `-l`, `mkdir
  -m` and the rest are refused because they are not listed. "Under
  `HANDS_KITS`" is decided as `git -C` is: `os.path.realpath` containment,
  relative paths joined to the hook's working directory, no `~` expanded, and
  with `HANDS_KITS` unset or empty nothing in that group passes. Every word is
  a plain word, as in every row: `./kits/*` is one path here and many to bash.
- `zip` and `unzip` are rows of no table (§32, REVIEW-15 blocker 2): an
  `unzip` writes where its entries say, relative to the cwd — the parent of
  `HANDS_KITS` — whatever its arguments are, so they are refused by name in
  every mode. The architect stages a directory `kits/<name>/<repository
  paths>` and files it with `hands kit file kits/<name>`, which builds the zip
  itself.
`FORBIDDEN_PATTERNS` refuses `mkdir|cp|mv|…` as a file mutation before any
tokenizing, so that row drops exactly these three words in architect mode and
keeps them everywhere else (`rm`, `touch`, `chmod`, `ln` and the rest stay
refused in every mode, under `HANDS_KITS` or not). File content is created
only through the write matcher below.

The write matcher (DESIGN §31): `python3 bash_guard.py --write` is the second
`PreToolUse` hook, for `Write|Edit|MultiEdit`. It reads the same hook JSON on
stdin, takes the tool's `file_path`, and allows it only in architect mode and
only under `HANDS_KITS`. Any other tool name, any payload shape it does not
recognise, and any other mode fail closed.

Self-test: python3 bash_guard.py --selftest
"""
import json
import os
import re
import shlex
import sys
import unicodedata

# DESIGN §31: the set of allowed first words is gone. `COMMAND_TABLE`, further
# down with the loop that consults it, is a row per command with the options it
# may take; a word that is not a row is refused by name.
#
# DESIGN §12: a table from each allowed subcommand to its allowed options. A
# subcommand that is not a key is refused. For one that is, every token that
# begins with `-` and is not in its row is refused. The rows carry the exact
# options the driver needs and nothing else. In particular, no listed option
# takes a value that names a program to run (`--upload-pack`, `--exec`,
# `--ext-diff`, `--textconv`, `--config-env`, `--edit-description`) or a file
# to write (`--output`, `-O`, `--open-files-in-pager`). What remains open is
# these listed options themselves.
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
# `find` runs a command for each match (`-exec`, `-execdir`, `-ok`, `-okdir`),
# deletes (`-delete`), or writes its listing to a named file (`-fprint`,
# `-fprint0`, `-fprintf`, `-fls`). The payload does not matter: the flag itself
# is the write. `-print`, `-printf` and `-ls` write to stdout and are reads.
FIND_ACTION_FLAGS = {"-exec", "-execdir", "-ok", "-okdir", "-delete",
                     "-fprint", "-fprint0", "-fprintf", "-fls"}
# DESIGN §12, §21: before the subcommand only `-C <path>` and `--no-pager` are
# accepted, and every other leading option is refused. `-c`, `--config-env`,
# `--exec-path`, `--git-dir` and the like each turn an allowlisted subcommand
# into something else: `git -c core.pager=touch log` runs `touch`. `-C` takes
# a single path as its value, and git itself takes it as the next word
# (`-C./x` and `-C=./x` are both "unknown option" to git 2.43). The value may
# not begin with `-`, or `git -C --exec-path=/tmp/evil log` would ride through
# unjudged. Role mode (§28) accepts `-C <path>` alone, and only once (§30).
GIT_PRE_FLAG_WITH_PATH = "-C"
GIT_ALLOWED_PRE_FLAGS = {"--no-pager"}
# `hands open <job>` execs `claude --resume <id>` in the role's directory
# (DESIGN §7). That is an interactive session inside the driver's Bash call,
# and a way past the `claude` block. The driver reads jobs with
# show/log/tail instead.
FORBIDDEN_HANDS_SUBCOMMANDS = {"open"}
# DESIGN §27, §28, role mode: the environment variables, the one mode value,
# and the allowlist. `send` and `kit` are judged by their arguments below.
ROLE_ENV = "HANDS_ROLE"
CONSULT_ROLE_ENV = "HANDS_CONSULT_ROLE"
CLONE_ENV = "HANDS_CLONE"  # §29: role mode's `git -C` must name this path
KITS_ENV = "HANDS_KITS"  # §31: architect mode's writes must land under this path
DRIVER_ROLE = "driver"
ARCHITECT_ROLE = "architect"  # §31: the third mode value
#: The two modes handsd starts: both pin `git -C` to the role's clone.
ROLE_MODES = (DRIVER_ROLE, ARCHITECT_ROLE)
ROLE_HANDS_SUBCOMMANDS = {"show", "jobs", "inbox", "pipeline", "status", "tail", "resume"}
#: §31: the `hands` reads architect mode has, which is `architect/settings.json`'s
#: own allow list. `kit` is judged by its own subcommand below (`check` and
#: `file`, never `apply`), and `send` is not here at all.
ARCHITECT_HANDS_SUBCOMMANDS = {"show", "jobs", "inbox", "pipeline", "status"}
ARCHITECT_KIT_SUBCOMMANDS = ("check", "file")
ROLE_SEND_TARGETS = {"builder", "aux"}
# `hands` options that may come before the subcommand. Two take a value, one
# does not.
HANDS_VALUE_OPTIONS = ("--project", "--socket")
HANDS_FLAG_OPTIONS = ("--json",)
#: §32: the reserved words of the shell. Any of them appearing as a word is
#: refused before tokenizing, in every mode.
RESERVED_WORDS = ("!", "[[", "]]", "case", "coproc", "do", "done", "elif", "else", "esac",
                  "fi", "for", "function", "if", "in", "select", "then", "time", "until",
                  "while")
#: §32, should-fix 7: how the guard finds the spool a role's reads may reach —
#: the project `hands` itself would mean (§29: `$HANDS_PROJECT`, else the only
#: `~/.hands/*.toml`), and that project's `~/.hands/<project>/`.
PROJECT_ENV = "HANDS_PROJECT"
PROJECT_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")

# Read on the command with its quoted text removed (`unquoted`). No pattern
# for redirection: a `<` or `>` never gets this far (§30).
#
# §31: the words the mutation row refuses, wherever they are written. The three
# `KITS_TABLE` carries are dropped from it in architect mode — and only there —
# because that mode judges them by their path arguments instead; everything
# else in the row (`rm`, `touch`, `chmod`, `ln`, ...) is refused in every mode.
MUTATION_WORDS = ("rm", "mv", "cp", "touch", "mkdir", "rmdir", "chmod", "chown",
                  "ln", "truncate", "dd", "install")
KITS_WORDS = ("mkdir", "cp", "mv")  # §32: `zip` and `unzip` left the table


def _mutation_row(words):
    return (r"(^|[\s;&|(])(" + "|".join(words) + r")\b", "file mutation")


def _patterns(mutation_words):
    return [
        (r"\btee\b", "tee"),
        (r"\bsed\s+(-[a-zA-Z]*i|--in-place)", "sed -i"),
        _mutation_row(mutation_words),
        (r"(^|[\s;&|(])(python3?|perl|ruby|node|bash|sh|zsh|eval|exec|source|xargs|env|sudo|su)\b", "interpreter or wrapper"),
        (r"(^|[^\w./-])claude\b", "direct claude"),
        (r"\bkill\b(?!\s+-0\b)", "kill other than -0"),
    ]


FORBIDDEN_PATTERNS = _patterns(MUTATION_WORDS)
ARCHITECT_PATTERNS = _patterns([w for w in MUTATION_WORDS if w not in KITS_WORDS])


def patterns_for(role):
    """§31: the pre-tokenizing patterns this mode reads."""
    return ARCHITECT_PATTERNS if role == ARCHITECT_ROLE else FORBIDDEN_PATTERNS

# §30, §32: the language. These are refused in any position, quoted or not,
# before any tokenizing. `$` covers every expansion bash starts with it (`$x`,
# `${…}`, `$(…)`, `$'…'`, `$((…))`), and `{`/`}` every brace expansion and
# group.
REFUSED_CHARACTERS = {
    "\n": "a newline",
    "\r": "a carriage return",
    "<": "a `<`",
    ">": "a `>`",
    "#": "a `#`",
    "`": "a backtick",
    "\\": "a backslash",
    "$": "a `$`",
    "{": "a `{`",
    "}": "a `}`",
}
# §30: interactive bash still history-expands this inside double quotes.
REFUSED_IN_DOUBLE_QUOTES = frozenset("!")
QUOTES = frozenset("'\"")

# §28, §32: the characters the shell may still expand in a word the guard has
# read, outside quotes: a glob, and a `~` after `=` or `:`. A word carrying one
# is not a plain word.
RESIDUAL = frozenset("~*?[!")
GLOB = frozenset("*?[!")
# What the mask hides inside quotes.
MASKED = RESIDUAL
# Where bash tilde-expands inside a word: after `=` (an argument shaped like an
# assignment, `a=~/x`) and, in assignments, after `:`.
TILDE_EXPANDED = re.compile(r"[=:]~")
SEPARATORS = frozenset(";&|()")
# §32: where bash ends a word outside quotes, in this language.
WORD_BREAKS = SEPARATORS | {" "}
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\[[^\]]*\])?\+?=")


class Refused(Exception):
    """The command cannot be judged as the shell would run it."""


def language_problem(cmd: str):
    """§30, §32: what makes `cmd` more than one line of words and quotes, or None.

    Returns the first offending character and its position (the index in
    `cmd`), else an unbalanced quote, else the first reserved word appearing as
    a word and its position. Quote state is tracked only for the double-quote
    rule, the unbalanced quote and the word split; nothing else can change it,
    since there are no escapes.
    """
    quote, opened = None, 0
    for i, c in enumerate(cmd):
        label = REFUSED_CHARACTERS.get(c)
        if label is None and unicodedata.category(c) == "Cc":
            label = f"a control character U+{ord(c):04X}"
        if label is None and quote == '"' and c in REFUSED_IN_DOUBLE_QUOTES:
            label = f"a `{c}` inside double quotes"
        if label is None and quote is None and c == "(" and i and cmd[i - 1] not in WORD_BREAKS:
            # bash with `extglob` reads `@(…)`, `+(…)` as a pattern: not a plain
            # word (§32); without it, a syntax error — nothing is lost
            label = "a `(` joined to the word before it"
        if label is not None:
            return f"{label} at position {i}"
        if quote is None and c in QUOTES:
            quote, opened = c, i
        elif c == quote:
            quote = None
    if quote is not None:
        return f"an unbalanced `{quote}` quote at position {opened}"
    for at, word in bare_words(cmd):
        if word in RESERVED_WORDS:
            return f"the reserved word `{word}` at position {at}"
    return None


def bare_words(cmd: str):
    """§32: `(position, text)` for each word as bash splits words outside
    quotes — on a space and on `; & | ( )` — with its quote characters kept, so a
    quoted word never equals a reserved one. Only for balanced quotes."""
    out: list[tuple[int, str]] = []
    quote, start = None, None
    for i, c in enumerate(cmd):
        if quote is None and c in WORD_BREAKS:
            if start is not None:
                out.append((start, cmd[start:i]))
                start = None
            continue
        if start is None:
            start = i
        if quote is None and c in QUOTES:
            quote = c
        elif c == quote:
            quote = None
    if start is not None:
        out.append((start, cmd[start:]))
    return out


def unquoted(cmd: str) -> str:
    """The command with each quoted span replaced by `''`, which is what
    FORBIDDEN_PATTERNS reads. Only for a command `language_problem` passed:
    its quotes balance, and nothing escapes them."""
    return re.sub(r"'[^']*'|\"[^\"]*\"", "''", cmd)


def segments(cmd: str):
    """The command's segments, each as a `(raw, mask)` pair of strings (§30).

    A segment ends at every separator outside quotes: `;`, `&`, `|`, `(` and
    `)`. `raw` is the segment as written. `mask` is the same text with every
    MASKED character inside quotes replaced by `_`, so `shlex` splits both
    into the same words, and the mask shows which expansion characters are
    unquoted. Only for a command `language_problem` passed.
    """
    out: list[tuple[str, str]] = []
    raw: list[str] = []
    mask: list[str] = []
    quote = None
    for c in cmd:
        if quote is None and c in SEPARATORS:
            out.append(("".join(raw), "".join(mask)))
            raw, mask = [], []
            continue
        raw.append(c)
        if quote is None:
            mask.append(c)
            if c in QUOTES:
                quote = c
        elif c == quote:
            mask.append(c)
            quote = None
        else:
            mask.append("_" if c in MASKED else c)
    out.append(("".join(raw), "".join(mask)))
    return out


def shell_words(text: str):
    """`shlex` POSIX words, split on spaces. Every other blank is a control
    character, which `language_problem` refused."""
    lex = shlex.shlex(text, posix=True)
    lex.whitespace_split = True
    lex.whitespace = " "
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
    """The expansion characters the shell would still act on in this word (§28,
    §32): an unquoted glob character, or an unquoted `~` after `=` or `:`."""
    found = {c for c in mask if c in GLOB}
    if TILDE_EXPANDED.search(mask[1:] if mask.startswith("~") else mask):
        found.add("~")
    return sorted(found)


def residual_violation(values, masks, start: int, name: str, cmd: str):
    """The reason a word after the `name` at `start` gets expanded after the
    guard read it, or None."""
    for value, mask in zip(values[start + 1:], masks[start + 1:], strict=True):
        found = residual(mask)
        if found:
            return (f"{name} argument {value!r} carries {' '.join(found)} the shell would "
                    f"expand after the guard read it, so it is not a plain word (§28, "
                    f"§32): {cmd!r}")
    return None


def clone_problem(value: str, clone):
    """§29, §30: why role mode's `git -C value` is not the role's clone, or None.

    Both sides are compared after `os.path.realpath`, so `<clone>/link/..` is
    wherever the kernel takes it, not the clone that `abspath` would fold it to.
    """
    if not clone:
        return (f"role mode pins `git -C` to the role's clone, and {CLONE_ENV} is not set "
                f"(§29), not {value!r}")
    if os.path.realpath(value) != os.path.realpath(clone):
        return (f"role mode pins `git -C` to the role's clone ({CLONE_ENV}={clone!r}, "
                f"compared by realpath, §29, §30), not {value!r}")
    return None


def under(value: str, root: str) -> bool:
    """Is `value` the directory `root` or something inside it? (§31)

    Both sides are compared after `os.path.realpath`, so a symlink and a `..`
    land where the kernel takes them and a relative path joins the hook's
    working directory, which is the role's cwd. No `~` is expanded.
    """
    here = os.path.realpath(value)
    there = os.path.realpath(root)
    return here == there or here.startswith(there + os.sep)


def kits_problem(value: str, kits, name: str):
    """§31: why `name`'s path argument `value` is not under `HANDS_KITS`, or None."""
    if not kits:
        return (f"architect mode runs `{name}` only on paths under the role's kits "
                f"directory, and {KITS_ENV} is not set (§31), so {value!r} is refused")
    if not under(value, kits):
        return (f"`{name}` takes only path arguments under the role's kits directory "
                f"({KITS_ENV}={kits!r}, compared by realpath, §31), not {value!r}")
    return None


def spool_dir():
    """§32 (should-fix 7): the spool a role's reads may reach, or None.

    The role's environment names no spool, so this finds the project the way
    `hands` does (§29): `$HANDS_PROJECT` when it is set, else the only
    `~/.hands/*.toml`. A name outside the project pattern, an empty one, or no
    single config names no spool, and reads under a spool are then refused.
    """
    hands = os.path.join(os.path.expanduser("~"), ".hands")
    project = os.environ.get(PROJECT_ENV)
    if project is None:
        try:
            stems = [name[:-len(".toml")] for name in os.listdir(hands)
                     if name.endswith(".toml")]
        except OSError:
            return None
        if len(stems) != 1:
            return None
        project = stems[0]
    if not PROJECT_NAME.fullmatch(project):
        return None
    return os.path.join(hands, project)


class Reads:
    """§32 (review 15 should-fix 7): the roots a role's reads are confined to.

    The clone (`HANDS_CLONE`), the spool (`spool_dir`) and, in architect mode
    only, `HANDS_KITS`. A root that is unset or empty confines nothing, so with
    none of them every path read is refused. Only the role modes build one.
    """

    def __init__(self, role, clone, spool, kits):
        self.role, self.clone, self.spool, self.kits = role, clone, spool, kits
        roots = [clone, spool] + ([kits] if role == ARCHITECT_ROLE else [])
        self.roots = [root for root in roots if root]

    def problem(self, word: str, mask: str, name: str, cmd: str, base=None):
        """Why `name` may not read `word`, or None. A leading unquoted `~` is
        expanded as bash expands it; a relative path joins `base` (git's `-C`
        value) or the hook's working directory."""
        path = os.path.expanduser(word) if mask.startswith("~") else word
        if base is not None:
            path = os.path.join(base, path)
        if any(under(path, root) for root in self.roots):
            return None
        kits = (f", {KITS_ENV}={self.kits!r}" if self.role == ARCHITECT_ROLE else "")
        also = " (and the architect's kits directory)" if self.role == ARCHITECT_ROLE else ""
        return (f"`{name}` reads {word!r}, and in role mode reads are confined to the clone "
                f"and the spool{also} ({CLONE_ENV}={self.clone!r}, spool {self.spool!r}"
                f"{kits}; compared by realpath, §32): {cmd!r}")

    def first_problem(self, paths, name: str, cmd: str, base=None):
        for word, mask in paths:
            problem = self.problem(word, mask, name, cmd, base)
            if problem is not None:
                return problem
        return None


def git_subcommand(words, start: int, role=None, clone=None):
    """Read the option area of the `git` at words[start - 1].

    Returns `(subcommand, index, path, refusal)`: the subcommand word, its
    index and the `-C` value (or None), or `refusal` set to the reason the
    option area is not acceptable. Only
    `-C <path>` and `--no-pager` may come before the subcommand (DESIGN §12,
    §21). `-C`'s value must be a single path that does not begin with `-`: the
    word after `-C` used to be stepped over unjudged, which carried
    `git -C --exec-path=/tmp/evil log` through. Role mode (§28) allows only
    one `-C <path>`, and the path must be the role's clone (§29, §30,
    `clone_problem`).
    """
    pinned_mode = role in ROLE_MODES
    pre_flags = set() if pinned_mode else GIT_ALLOWED_PRE_FLAGS
    seen_path, path = False, None
    i = start
    while i < len(words):
        w = words[i]
        if w == GIT_PRE_FLAG_WITH_PATH:
            if i + 1 >= len(words):
                return None, i, None, "`-C` with no path after it"
            if pinned_mode and seen_path:
                return None, i, None, ("a second `-C` is refused in role mode: git applies "
                                       "each `-C` relative to the one before (§30)")
            value = words[i + 1]
            if value.startswith("-"):
                return None, i, None, (f"the `-C` value must be a single path that does "
                                       f"not begin with `-`, not {value!r}")
            if pinned_mode:
                pinned = clone_problem(value, clone)
                if pinned is not None:
                    return None, i, None, pinned
            seen_path, path = True, value
            i += 2
            continue
        if w in pre_flags:
            i += 1
            continue
        if w.startswith("-"):
            allowed = ("only `-C <path>` may come before a git subcommand in role mode"
                       if pinned_mode else
                       "only `-C <path>` and `--no-pager` may come before a git subcommand")
            return None, i, None, (f"git option before the subcommand not allowed: {w!r} "
                                   f"({allowed}; `-c`, `--config-env` and the rest can "
                                   f"make a read-only subcommand run a command)")
        return w, i, path, None
    return None, len(words), path, None


def unlisted_git_option(sub: str, word: str):
    """The token after the subcommand that this subcommand's row does not
    list, or None.

    Only a token beginning with `-` is judged: a revision, a `rev:path` or a
    path carries no leading dash, and `--` separates paths from revisions. An
    option is allowed only if `GIT_SUBCOMMAND_OPTIONS[sub]` lists it, with
    `--grep=push` counting as `--grep`. For `log` alone, `-10` and `-n10` count
    as the `-n` shorthand, which is what `driver/CLAUDE.md` itself tells the
    driver to run (`log --oneline origin/BRANCH -10`). Everything else is
    refused because it is not listed, including every option that names a
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

    A bare `name` counts wherever it sits, because a wrapper puts the real
    command in argument position (`find . -exec git push ';'`,
    `xargs git add`). A path ending in `/name` counts only as the segment's
    first word, because the human's workspace really is `~/git`: `ls ~/git`
    and `cat ~/git/x/DESIGN.md` name a directory, not a program, and a guard
    that refuses them is useless in a real driver session.
    """
    return [i for i, w in enumerate(words)
            if w == name or (i == 0 and w.endswith("/" + name))]


def git_violation(words, masks, cmd, role=None, clone=None, reads=None):
    """The reason some `git` in this segment is not a read-only invocation,
    or None.

    The allowlist applies to every `git` token, not only to a segment's first
    word: checking only the first word leaves a hole as wide as every wrapper
    (review 3 blocker 1). What is read is each invocation's subcommand
    position, so a revision (`<sha>^0`) or a pattern (`log --grep=push`) is
    still a word, not a verb. In role mode (§32) every word after the
    subcommand that is not an option is a path git may read — `diff` reads
    two files outside a repository, `fetch` another repository — so it must
    resolve, from the `-C` value, under the clone or the spool.
    """
    for i in invocations(words, "git"):
        sub, at, path, refusal = git_subcommand(words, i + 1, role, clone)
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
        if reads is not None:
            paths = [(w, m) for w, m in zip(words[at + 1:], masks[at + 1:], strict=True)
                     if not w.startswith("-")]
            problem = reads.first_problem(paths, "git", cmd, base=path)
            if problem is not None:
                return problem
    return None


def find_action(words):
    """The `find` action flag in this segment, or None.

    `-exec`, `-execdir`, `-ok` and `-okdir` run a command for each match, and
    `-delete` removes files. A `find` with none of them only prints.
    """
    for i in invocations(words, "find"):
        for w in words[i + 1:]:
            if w in FIND_ACTION_FLAGS:
                return w
    return None


def option_is(word: str, name: str) -> bool:
    """Does argparse read `word` (before any `=`) as the option `name`?

    argparse takes an unambiguous prefix of a long option as that option, so
    `--cont` is `--context`. The word needs two dashes and at least one letter.
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
    and the values `--project` and `--socket` take (§28: values are read from
    the tokens)."""
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


#: §32: the `hands` options whose value is a path the CLI reads (or, for
#: `--socket`, connects to), and the `kit` subcommands whose word is a kit it reads.
HANDS_PATH_OPTIONS = ("--prompt-file", "--socket", "--repo")
KIT_VALUE_OPTIONS = ("--repo", "--project", "--socket")


def hands_paths(args, amasks):
    """§32: `(word, mask)` for every path this `hands` invocation reads."""
    paths = []
    for i, a in enumerate(args):
        if not any(option_is(a, name) for name in HANDS_PATH_OPTIONS):
            continue
        if "=" in a:
            paths.append((a.split("=", 1)[1], amasks[i].split("=", 1)[1]))
        elif i + 1 < len(args):
            paths.append((args[i + 1], amasks[i + 1]))
    i = hands_subcommand(args)
    if args[i:i + 2] in (["kit", "check"], ["kit", "file"]):
        i += 2
        while i < len(args):
            a = args[i]
            if any(option_is(a, name) for name in KIT_VALUE_OPTIONS):
                i += 1 if "=" in a else 2
                continue
            if not a.startswith("-"):
                paths.append((a, amasks[i]))
            i += 1
    return paths


def hands_violation(words, masks, cmd, role=None, consult_role=None, reads=None):
    """The reason this `hands` invocation (words[0]) is refused, or None."""
    args = words[1:]
    i = hands_subcommand(args)
    if role not in ROLE_MODES:
        sub = next((a for a in args[i:] if not a.startswith("-")), None)
        if sub in FORBIDDEN_HANDS_SUBCOMMANDS:
            return f"hands {sub} starts an interactive session: {cmd!r}"
        return None
    if reads is not None:
        problem = reads.first_problem(hands_paths(args, masks[1:]), "hands", cmd)
        if problem is not None:
            return problem
    if i >= len(args) or args[i].startswith("-"):
        got = args[i] if i < len(args) else "nothing"
        return f"hands needs an allowed subcommand in role mode, got {got!r}: {cmd!r}"
    if role == ARCHITECT_ROLE:
        return architect_hands_violation(args, args[i], args[i + 1:], cmd)
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


def architect_hands_violation(args, sub, rest, cmd):
    """§31: the `hands` surface of architect mode, or None.

    `kit check` and `kit file`, and the reads `architect/settings.json` allows.
    Everything else is refused by name, `send` with the authority commands:
    the architect files a kit and replies, and never drives a role.
    """
    if sub in ARCHITECT_HANDS_SUBCOMMANDS:
        return None
    if sub == "kit":
        if rest and rest[0] in ARCHITECT_KIT_SUBCOMMANDS:
            if rest[0] == "file":
                # §31 is silent here; §27's reason for the driver's send holds:
                # the job is filed in the role's own project, so the two options
                # that leave it are refused. `kit check` writes nothing and
                # reads neither, so it keeps them.
                for name in HANDS_VALUE_OPTIONS:
                    if any(option_is(a, name) for a in args):
                        return (f"hands kit file {name} leaves the architect's own "
                                f"project, refused (§27's rule for a role's send): {cmd!r}")
            return None
        return (f"only `hands kit check` and `hands kit file` are allowed for the "
                f"architect role (§31): {cmd!r}")
    return (f"hands {sub} is not allowed for the architect role (§31: kit check, kit "
            f"file, show, jobs, inbox, pipeline, status — never send, approve, deny, "
            f"go, put, pause, resume or open): {cmd!r}")


def send_violation(args, rest, cmd, consult_role):
    """§28: a send in role mode carries exactly one `--context`, literally
    `keep`, and exactly one `--role`, equal to HANDS_CONSULT_ROLE."""
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


# --- DESIGN §31: the command table ------------------------------------------
#
# A bare set of allowed first words applied no option table outside `git` and
# `hands`, so an allowed word took any option it liked — and those options
# write files and run programs: `sort -o F` created a file, `uniq A B` created
# a file, and `sort --compress-program=P` executed P (REVIEW-14 blocker 1,
# H-028). The table below is what the driver may run, in both modes, and it is
# closed the way `GIT_SUBCOMMAND_OPTIONS` is closed: a word that is not a row
# is refused by name, and for a word that is one, every token beginning with
# `-` that its row does not list is refused. No listed option takes a value
# that names a program to run or a file to write — the only two that take a
# value take an integer (`head`/`tail -n`) and a pattern (`grep -e`).
#
# `sort`, `uniq`, `cut`, `tr`, `find`, `stat`, `diff`, `printf`, `basename`,
# `dirname`, `realpath`, `tty`, `id`, `whoami`, `uptime`, `which`, `test`, `[`,
# `seq`, `true`, `false` and `pwd` are not rows: they left the table. §31 names
# all of them but `pwd`, which it names in neither list; the table is closed,
# so `pwd` leaves with them.
INTEGER = re.compile(r"[0-9]+")
COUNT_SHORTHAND = re.compile(r"-[0-9]+")


class Command:
    """One row of the table: what a command word may carry (§31).

    `flags` are the options that take no value. `values` maps an option to the
    predicate its value must satisfy, read from the next word or attached to
    the option (`-n5`). `words` judges the words that are not options, or is
    None when any word may follow (a path, a pattern). `count` also allows the
    `-<int>` spelling of `-n <int>`, which is how `head -1` is written, as
    `git log -10` already is.

    `judge` replaces the option reading for `git` and `hands`, whose arguments
    carry semantics a flat row cannot express (a subcommand and its own option
    table, a `--context` value, the role a consultation named). They are
    reached through this same lookup: the table is the one place a command word
    is allowed, in both modes.
    """

    def __init__(self, flags=(), values=(), words=None, count=False, judge=None,
                 kits=False, reads=None, private=None):
        self.flags = frozenset(flags)
        self.values = dict(values)
        self.words = words
        self.count = count
        self.judge = judge
        # §32 (should-fix 7), role modes only: `reads(plain, args)` gives the
        # `(word, mask)` paths this command reads, each confined by `Reads`, and
        # `private(name, plain, cmd)` refuses what reads the environment.
        self.reads = reads
        self.private = private
        # §31: a `KITS_TABLE` row. Every path argument of this command — each
        # word that is not an option, and the value of every option it takes,
        # since all of those name a path too — must be under `HANDS_KITS`, and
        # it takes at least one.
        self.kits = kits

    def listed(self) -> str:
        return ", ".join(sorted(self.flags | set(self.values))) or "no options"


def an_integer(value: str) -> bool:
    return INTEGER.fullmatch(value) is not None


def any_value(value: str) -> bool:
    """`grep -e <pat>`: a pattern is any word. It names no program and no file."""
    return True


def one_integer(name, plain, cmd):
    """§31: `sleep` takes one integer."""
    if len(plain) != 1 or not an_integer(plain[0]):
        return f"`{name}` takes one integer (§31), not {plain}: {cmd!r}"
    return None


def a_format(name, plain, cmd):
    """§31: `date` takes no options, and no argument but a `+FORMAT`."""
    if len(plain) > 1 or (plain and not plain[0].startswith("+")):
        return f"`{name}` takes nothing or one `+FORMAT` (§31), not {plain}: {cmd!r}"
    return None


def a_pid(name, plain, cmd):
    """§31: `kill -0 <pid>`. `-0` is the only signal (FORBIDDEN_PATTERNS refuses
    a `kill` that is not followed by it) and the pid is a number."""
    if not plain or not all(an_integer(w) for w in plain):
        return f"`{name} -0` takes a pid (§31), not {plain}: {cmd!r}"
    return None


def a_filter(name, plain, cmd):
    """§31's `.` in jq's row: the first word that is not an option is the
    filter, a `.` expression; the words after it are the files it reads."""
    if not plain:
        return f"`{name}` needs a `.` filter (§31): {cmd!r}"
    if not plain[0].startswith("."):
        return f"`{name}`'s filter is a `.` expression (§31), not {plain[0]!r}: {cmd!r}"
    return None


def every_word(plain, args):
    """`cat`, `head`, `tail`, `wc`: every word is a file (`-` is stdin)."""
    return [(word, mask) for word, mask in plain if word != "-"]


def listed_or_here(plain, args):
    """`ls`: its words, or the working directory when it has none."""
    return plain or [(".", ".")]


def grep_files(plain, args):
    """`grep`: the words after the pattern (every word when `-e` gives it), or
    the working directory under `-r` when there are none."""
    given = any(a == "-e" or (a.startswith("-e") and len(a) > 2) for a in args)
    files = plain if given else plain[1:]
    if not files and "-r" in args:
        return [(".", ".")]
    return files


def after_the_filter(plain, args):
    """`jq`: the words after its filter."""
    return plain[1:]


JQ_ENVIRONMENT = re.compile(r"\benv\b")


def no_environment(name, plain, cmd):
    """§32, role modes: jq's `env` reads the environment, as `/proc/self/environ`
    would, so a role's filter may not name it."""
    if plain and JQ_ENVIRONMENT.search(plain[0][0]):
        return (f"`{name}`'s filter names `env`, which reads the environment; in role mode "
                f"reads are confined to the clone and the spool (§32): {cmd!r}")
    return None


def git_command(words, masks, cmd, role, consult_role, reads=None):
    """`git`'s row: every `git` token in the segment, wherever it sits, was
    already judged against `GIT_SUBCOMMAND_OPTIONS` by `git_violation`."""
    return None


COMMAND_TABLE = {
    # `hands` and `git` with their existing tables, reached by the same lookup
    "hands": Command(judge=hands_violation),
    "git": Command(judge=git_command),
    # the read-only inspection commands the driver's rules name, each with the
    # options §31 lists and no others
    "cat": Command(reads=every_word),
    "ls": Command(flags={"-l", "-a", "-la", "-1"}, reads=listed_or_here),
    "head": Command(values={"-n": an_integer}, count=True, reads=every_word),
    "tail": Command(values={"-n": an_integer}, count=True, reads=every_word),
    "wc": Command(flags={"-l", "-c", "-w"}, reads=every_word),
    "grep": Command(flags={"-n", "-c", "-i", "-l", "-E", "-F", "-r"},
                    values={"-e": any_value}, reads=grep_files),
    "jq": Command(flags={"-r", "-c", "-e"}, words=a_filter, reads=after_the_filter,
                  private=no_environment),
    "pgrep": Command(flags={"-f", "-a", "-l"}),
    "sleep": Command(words=one_integer),
    "date": Command(words=a_format),
    "echo": Command(),
    "kill": Command(flags={"-0"}, words=a_pid),
}

# §31, §32, architect mode only: the three words that arrange a staged directory
# kit under `HANDS_KITS` (`kits/<name>/<repository paths>`, whose file content
# the write matcher creates), each with the minimum that needs and no more.
# Every path argument is confined to that directory (`Command.kits`). No option
# here takes a value, so none names another path (`cp -t`, `--target-directory`,
# `-S`), and none makes a link (`cp -s`, `-l`): each is refused because it is
# not listed. `zip` and `unzip` are not rows (§32, REVIEW-15 blocker 2): `unzip`
# wrote into the cwd, the parent of `HANDS_KITS`, and `hands kit file` builds
# the zip itself. These rows exist in no other mode, where the three words
# remain what `FORBIDDEN_PATTERNS` calls them — a file mutation.
KITS_TABLE = {
    "mkdir": Command(flags={"-p"}, kits=True),
    "cp": Command(flags={"-r"}, kits=True),
    "mv": Command(kits=True),
}


def value_option(row, word):
    """The row's value-taking option this word spells, and the value attached to
    it (`-n5`), or `(None, None)`. An attached value of None means the value is
    the next word."""
    if word in row.values:
        return word, None
    for option in sorted(row.values):
        if word.startswith(option) and len(word) > len(option):
            return option, word[len(option):]
    return None, None


def option_violation(name, row, args, amasks, cmd, kits=None, reads=None):
    """The reason this command's words are not the ones its row lists, or None.

    Every token beginning with `-` must be listed by the row; what is left are
    the plain words (paths, patterns), judged by the row's `words` rule when it
    has one. This is `unlisted_git_option`'s policy for the rest of the table:
    an option is refused because it is not listed, not because someone
    remembered to name it.

    For a `KITS_TABLE` row (§31) every one of those words, and every value its
    options take, must also be a path under `HANDS_KITS`. In a role mode
    (`reads`, §32) the paths the row reads must be under the clone or the spool.
    """
    plain, i = [], 0
    while i < len(args):
        word = args[i]
        if not word.startswith("-") or word == "-":
            plain.append((word, amasks[i]))
            i += 1
            continue
        if word in row.flags:
            i += 1
            continue
        if row.count and COUNT_SHORTHAND.fullmatch(word):
            i += 1
            continue
        option, attached = value_option(row, word)
        if option is None:
            return (f"option not allowed for {name!r}: {word!r} in {cmd!r} (policy: "
                    f"DESIGN §31 lists the options each command may carry — `{name}` "
                    f"takes {row.listed()} — and every other option is refused because "
                    f"it is not listed)")
        if attached is None:
            if i + 1 >= len(args):
                return f"`{name} {option}` with no value: {cmd!r}"
            attached, i = args[i + 1], i + 2
        else:
            i += 1
        if not row.values[option](attached):
            return (f"the value of `{option}` for `{name}` is not one §31 allows: "
                    f"{attached!r} in {cmd!r}")
        if row.kits:
            problem = kits_problem(attached, kits, name)
            if problem is not None:
                return f"{problem}: {cmd!r}"
    if row.kits:
        if not plain:
            return f"`{name}` takes at least one path under {KITS_ENV} (§31): {cmd!r}"
        for word, _ in plain:
            problem = kits_problem(word, kits, name)
            if problem is not None:
                return f"{problem}: {cmd!r}"
    if row.words is not None:
        reason = row.words(name, [word for word, _ in plain], cmd)
        if reason is not None:
            return reason
    if reads is not None:
        if row.private is not None:
            reason = row.private(name, plain, cmd)
            if reason is not None:
                return reason
        if row.reads is not None:
            return reads.first_problem(row.reads(plain, args), name, cmd)
    return None


def judge(words, marks, cmd, role, consult_role, clone=None, kits=None, reads=None):
    """The reason this segment's words are refused, or None.

    One loop for every command word (§31). The segment's command word is looked
    up in COMMAND_TABLE, and a word that is not a row is refused by name; every
    word after it must be a plain word (§32); each `git` token is judged
    wherever it sits, because a wrapper puts the real command in argument
    position; then the row judges its own words. The same table judges every
    mode: role mode is it minus the `hands` subcommands §27 withholds, which
    `hands_violation` applies from inside `hands`' row, and with its reads
    confined (`reads`, §32).
    """
    if not words:
        return None
    if ASSIGNMENT.match(words[0]):
        return f"a leading assignment ({words[0]!r}) is refused (§28): {cmd!r}"
    name = words[0]
    row = COMMAND_TABLE.get(name)
    if row is None and role == ARCHITECT_ROLE:
        row = KITS_TABLE.get(name)  # §31, §32: these three rows exist in this mode only
    if row is None:
        table = dict(COMMAND_TABLE, **KITS_TABLE) if role == ARCHITECT_ROLE else COMMAND_TABLE
        who = "the architect" if role == ARCHITECT_ROLE else "the driver"
        return (f"command not in the guard's table: {name!r} in {cmd!r} (§31: {who} "
                f"runs {', '.join(sorted(table))}, each with the options that "
                f"table lists; a word not in it is refused by name)")
    reason = residual_violation(words, marks, 0, name, cmd)
    if reason:
        return reason
    reason = git_violation(words, marks, cmd, role, clone, reads)
    if reason:
        return reason
    # `find` is not a row, so this reaches only a `find` in argument position —
    # a wrapper shape, kept as the git scan above is kept (DESIGN §20, §21).
    action = find_action(words)
    if action:
        return f"find {action}: {cmd!r}"
    if row.judge is not None:
        return row.judge(words, marks, cmd, role, consult_role, reads)
    return option_violation(name, row, words[1:], marks[1:], cmd, kits, reads)


def check(cmd: str, role=None, consult_role=None, clone=None, kits=None, spool=None):
    """Return None if allowed, else a reason string.

    `role` is `HANDS_ROLE`: None for the human's driver session, `driver` for
    §27's role mode, `architect` for §31's, and anything else is refused
    outright (fail closed). `consult_role` is `HANDS_CONSULT_ROLE`, `clone` is
    `HANDS_CLONE`, `kits` is `HANDS_KITS` and `spool` is `spool_dir()`; only the
    role modes read them. The language comes first (§30, §32): a command that is
    not one line of words, quotes and separators is refused before any
    tokenizing, naming the first offender and its position.
    """
    if role is not None and role not in ROLE_MODES:
        known = " or ".join(repr(name) for name in ROLE_MODES)
        return f"unknown {ROLE_ENV} {role!r} (only {known} is a mode): {cmd!r}"
    problem = language_problem(cmd)
    if problem is not None:
        return (f"refused before tokenizing: {problem} (§30, §32: the driver's shell is "
                f"one line of words, quotes and `; && || | &` — no expansion, control flow, "
                f"redirection or comment): {cmd!r}")
    bare = unquoted(cmd)
    for pat, why in patterns_for(role):
        if re.search(pat, bare):
            return f"{why}: {cmd!r}"
    reads = Reads(role, clone, spool, kits) if role in ROLE_MODES else None
    try:
        for raw, mask in segments(cmd):
            values, masks = tokens(raw, mask)
            reason = judge(values, masks, cmd, role, consult_role, clone, kits, reads)
            if reason:
                return reason
    except Refused as e:
        return f"{e}, refused (§28): {cmd!r}"
    return None


# --- DESIGN §31: the second matcher, Write|Edit|MultiEdit --------------------
#
# Claude Code names the path of a Write, an Edit and a MultiEdit `file_path` in
# the tool's input. This reads that one field and nothing else: a payload whose
# shape it does not recognise is refused, not guessed at.
WRITE_TOOLS = ("Write", "Edit", "MultiEdit")
WRITE_PATH_KEY = "file_path"


def write_violation(data, role=None, kits=None):
    """§31: the reason this Write/Edit/MultiEdit call is refused, or None.

    Allowed only in architect mode, and only for a path under `HANDS_KITS`.
    Every other mode, every other tool name and every shape this does not
    recognise fails closed, so the matcher can only ever narrow what
    `settings.json` already allows.
    """
    if role != ARCHITECT_ROLE:
        return (f"a write is allowed only in architect mode ({ROLE_ENV}={role!r}, §31), "
                f"and only under {KITS_ENV}")
    tool = data.get("tool_name") if isinstance(data, dict) else None
    if tool not in WRITE_TOOLS:
        return (f"the write matcher judges {' | '.join(WRITE_TOOLS)}, not {tool!r} "
                f"(§31: any other tool fails closed)")
    tool_input = data.get("tool_input")
    if not isinstance(tool_input, dict):
        return f"the {tool} call carries no tool_input object (§31: fail closed)"
    path = tool_input.get(WRITE_PATH_KEY)
    if not isinstance(path, str) or not path:
        return (f"the {tool} call carries no {WRITE_PATH_KEY} the guard can read "
                f"({path!r}, §31: fail closed)")
    return kits_problem(path, kits, tool)


# §30: review 13 blocker 1's `<<` shape, verbatim (bash's decoding of the
# reviewer's `$'…'` string), then the same shape hiding a clear send and a `go`.
REVIEW_13_SHAPES = [
    "ls <<A\nls '\nA\ntouch /tmp/rev13-me-pwned\nls \"'\" <<'true'\n\"\ntrue",
    "ls <<A\nls '\nA\nhands go\nls \"'\" <<'true'\n\"\ntrue",
    "ls <<A\nls '\nA\nhands send --role builder --context clear m\nls \"'\" <<'true'\n\"\ntrue",
    "hands status <<A\nhands show '\nA\nhands go\nhands show \"'\" <<'true'\n\"\ntrue",
]

# §31: the three writes/executions REVIEW-14 blocker 1 reproduced at the tip,
# through this file with hook JSON on stdin, in normal mode. The blocker prints
# the third with `<big file>`, its placeholder for the path it ran (REVIEW-14 §4
# names it); `<` is refused by §30, so what matters is the option itself.
REVIEW_14_PROBES = [
    "sort -o /tmp/rev14-probe/Z1 /etc/hostname",
    "uniq /etc/hostname /tmp/rev14-probe/W5",
    "sort -S 1k --compress-program=/tmp/rev14-probe/prog /tmp/rev14-probe/big.txt",
]

# §32: REVIEW-15 blocker 1, verbatim — a `for` segment went unjudged and `${c@P}`
# ran a `$(…)`; `$o` carried an option past its row — and the U1 sub-agent's
# `cat`/`ls` variants. Each is refused before tokenizing, in every mode.
#: REVIEW-15 blocker 2 (§32, H-030): `unzip` extracted into the role's cwd, the
#: parent of `HANDS_KITS`, over this file and its settings; `zip` stored entries
#: under `kits/…`, never at repository paths. Refused by name in every mode.
REVIEW_15_ARCHIVE_PROBES = [
    "unzip -o kits/attack.zip",
    "unzip -o ./kits/attack.zip",
    "unzip kits/attack.zip",
    "zip -r kits/m.zip kits/m16",
]

REVIEW_15_PROBES = [
    "for a in '$x'; do echo; done; for c in ${a%x}'(touch${IFS}/tmp/rev15-tip/PWN)'; do echo ${c@P}; done",
    "for a in '$x'; do echo; done; for c in ${a%x}'(touch${IFS}/tmp/rev15-tip/PWN)'; do cat ${c@P}; done",
    "for a in '$x'; do echo; done; for c in ${a%x}'(touch${IFS}/tmp/rev15-tip/PWN)'; do ls ${c@P}; done",
    "for o in -f; do tail $o /etc/hostname; done",
    "for o in --files0-from=F; do wc $o; done",
    "for o in -f; do grep $o F x; done",
    "for s in '%s --set=2020-01-01'; do date +$s; done",
]

SELFTEST = [
    # (command, allowed?)
    ("git -C ./repo log --oneline -1", True),
    ("git -C ./repo fetch -q && git -C ./repo log --oneline origin/main -15", True),
    ("hands inbox --json", True),
    ("hands send --role builder --context clear 'Execute WORKPLAN.md run 2'", True),
    ("sleep 20; kill -0 \"$(pgrep -f handsd)\" && echo alive || echo dead", False),
    ("sleep 20; pgrep -f handsd && echo alive || echo dead", True),
    ("cat ~/.hands/jobs/0mtxb7ecx.json ~/.hands/inbox.jsonl", True),
    ("ls probe.txt 2>&1", False),
    ("jq -r '.result' ~/.hands/jobs/0mtxb7ecx.json", True),
    ("for i in $(seq 1 3); do echo $i; done", False),
    ("for i in 1 2 3; do echo $i; done", False),  # §32: `$` and reserved words
    ("git -C ./repo show origin/main:meta/CHECKPOINT.md", True),
    ("git status 2>/dev/null", False),
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
    ("git -C ./repo rev-parse 8448b6f^0", True),
    ("git -C ./repo rev-parse --verify HEAD^0", True),
    ("git -C ./repo show 861097f --stat", True),
    # ... and §32 refuses a brace anywhere, `^{commit}` included
    ("git -C ./repo rev-parse 8448b6f^{commit}", False),
    ("git log --grep=commit -5", True),
    ("git -C ./repo log --oneline --grep=push -20", True),
    # ... and these still write, wherever the verb hides
    ("git -c user.name=x commit -m y", False),
    ("git --git-dir=./repo/.git push origin main", False),
    ("git -C ./repo log --oneline -1 && git -C ./repo push", False),
    ("git -C ./repo status; git -C ./repo add -A", False),
    ("find . -name x -exec git push \\;", False),
    ("find . -name x -exec git push ';'", False),
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
    # ... and `find` is no longer a word the driver has at all (§31): the row
    # that allowed a printing `find` before this unit is a block now
    ("find . -name '*.md' -printf %p", False),
    # ... and under the per-subcommand allowlist (§12) an option is refused
    # simply because its subcommand's row does not list it. These read, and
    # are refused anyway. The wrappers below are refused the same way, which
    # is the point: nobody has to have remembered them.
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
    # prose inside quotes is text, not shell, unless it holds a character §30
    # refuses in any position (`<`, `>`, `#`, ...): such prose goes as a file
    ("hands send --role builder --context clear --gate \"apply kit\" \"Apply ~/Downloads/k.zip (it replaces DESIGN.md), then commit 'plan: kit (v3.1)' and push. Reply: VERDICT: kit applied <sha>.\"", False),
    ("hands send --role builder --context clear --gate \"apply kit\" \"Apply ~/Downloads/k.zip (it replaces DESIGN.md), then commit 'plan: kit (v3.1)' and push. Reply: VERDICT: kit applied SHA.\"", True),
    ("hands send --role aux --context clear 'Review commits since abc123; report blockers=0 or blockers>0 (count them)'", False),
    ("hands send --role aux --context clear 'Review commits since abc123; report blockers=0 or more (count them)'", True),
    ("hands approve JOBID --human-confirmed --quote \"Approve job JOBID (my words)\"", True),
    ("echo \"a > b\"", False),
    ("echo \"a\" > b", False),
    ("echo 'it (works)'", True),
    # §30: `$(` and a backtick are refused wherever they are, quoted or not
    ("hands send --role aux \"$(rm -rf x)\"", False),
    ("echo \"`touch x`\"", False),
    ("echo '$(rm -rf x)'", False),
    ("kill -0 \"$(jq -r .pid ~/.hands/jobs/0mtxb7ecx.json)\" && echo alive", False),
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
    # the stdin route: §30, `--prompt-file` replaced `--stdin <`; a pipe still reads
    ("hands send --role builder --context clear --stdin < ~/Downloads/m2-send.txt", False),
    ("cat ~/Downloads/m2-send.txt | hands send --role builder --context clear --stdin", True),
    # §28: review 11's probes, as the human's session judges them. `go`,
    # `approve`, a clear send and `--file` are the human session's to run, so
    # only the probes refused in both modes (and `open`) are blocked here;
    # ROLE_SELFTEST blocks every one. §30 refuses the backslash spellings.
    ("hands show x & hands go", True),
    ("hands jobs & hands approve j1 --human-confirmed --quote yes", True),
    ("hands show & hands open x", False),
    ("hands send --role builder --context keep '--context=clear' m", True),
    ("hands send --role builder --context keep \"--context=clear\" m", True),
    ("hands send --role builder --context keep \\--context=clear m", False),
    ("hands send --role builder --context keep $'--context=clear' m", False),
    ("hands send --role builder --context keep {--context=clear,m}", False),
    ("x=--context=clear; hands send --role builder --context keep $x m", False),
    ("hands send --role builder --context keep '--file' a=b m", True),
    ("hands send --role builder --context keep \\--file a=b m", False),
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
    # §29, §30: review 12's probes; a `#` is refused in any position
    ("hands show x # it's\nhands go #'", False),
    ("hands show x # it's\nhands send --role builder --context clear m #'", False),
    ("ls # it's\ntouch /tmp/rev12-pwned #'", False),
    ("hands status # a note", False),
    ("hands show a#b", False),
    ("hands send --role builder --context clear 'fix #12'", False),
    ("hands send --role builder --context clear 'fix no. 12'", True),
    ("git -C ./repo log HEAD@{1} --oneline -1", False),  # §32: a brace anywhere
    ("git log --grep=x{a,b}", False),
    # §30: review 13's `<<` shapes, in both modes
    *[(shape, False) for shape in REVIEW_13_SHAPES],
    ("hands send --role builder --context clear 'costs $5!'", False),  # §32: `$` anywhere
    ("hands send --role builder --context clear 'costs 5 dollars!'", True),
    ("hands send --role builder --context clear \"costs $5\"", False),
    ("hands send --role builder --context clear \"done!\"", False),
    # §31: the command table. The three writes and the execution REVIEW-14
    # reproduced through this file, and the words they used, which left it
    *[(probe, False) for probe in REVIEW_14_PROBES],
    ("sort ~/.hands/inbox.jsonl", False),
    ("uniq ~/.hands/inbox.jsonl", False),
    ("cut -d : -f 1 /etc/hostname", False),
    ("stat --printf=%n ./repo/DESIGN.md", False),
    ("diff --to-file=/tmp/out a b", False),
    ("which -a python3", False),
    ("pwd", False),
    # ... and a listed word takes the listed options and no others
    ("cat ~/.hands/inbox.jsonl", True),
    ("cat -n ~/.hands/inbox.jsonl", False),
    ("ls -la ~/git/hands", True),
    ("ls -R ~/git/hands", False),
    ("head -n 20 ./repo/DESIGN.md", True),
    ("git -C ./repo log --oneline -5 | head -1", True),
    ("head -c 20 ./repo/DESIGN.md", False),
    ("tail -n 5 ~/.hands/inbox.jsonl", True),
    ("tail -f ~/.hands/inbox.jsonl", False),  # §31: `-f` is `hands log`'s alone
    ("hands log -f builder", True),
    ("wc -l -c -w ./repo/DESIGN.md", True),
    ("wc -m ./repo/DESIGN.md", False),
    ("grep -r -n -i -e consult ./repo", True),
    ("grep -o consult ./repo/DESIGN.md", False),
    ("grep -f /tmp/patterns ./repo/DESIGN.md", False),
    ("jq -r .result ~/.hands/jobs/0mtxb7ecx.json", True),
    ("jq --slurpfile x /etc/hostname . ~/.hands/jobs/0mtxb7ecx.json", False),
    ("pgrep -f -a -l handsd", True),
    ("sleep 20", True),
    ("sleep 20 30", False),
    ("date +%s", True),
    ("date -s 2026-01-01", False),
    ("echo alive", True),
    ("echo -n alive", False),
    ("kill -0 1234", True),
    ("kill -0", False),
    # §32: `$`, braces and reserved words, anywhere, and every probe of review 15
    *[(probe, False) for probe in REVIEW_15_PROBES],
    ("echo ${c@P}", False),
    ("cat '${x}'", False),
    ("ls {a,b}", False),
    ("while true; do echo; done", False),
    ("if hands status; then hands go; fi", False),
    ("! hands status", False),
    ("echo done", False),
    ("grep -n -e 'done' ./repo/DESIGN.md", True),  # a quoted reserved word is text
    # ... the options §32 names, refused by name, and a word that is not plain
    ("wc --files0-from=F", False),
    ("grep -f F x", False),
    ("date +%s --set=2020-01-01", False),
    ("tail -n 5 *", False),
    # ... and normal mode's reads are not confined
    ("cat /proc/self/environ", True),
]


# The role the consultation named, as the self-test's HANDS_CONSULT_ROLE, the
# role's clone, as its HANDS_CLONE (driver/CLAUDE.md's CLONE), and the spool a
# role's reads may reach (§32), as `spool_dir()` would name project `hands`'s.
SELFTEST_CONSULT_ROLE = "builder"
SELFTEST_CLONE = "./repo"
SELFTEST_SPOOL = "/home/u/.hands/hands"

# Role mode (§27, §28): `check(cmd, role="driver", consult_role="builder")`.
ROLE_SELFTEST = [
    ("git -C ./repo log --oneline -5", True),
    ("git -C ./repo rev-parse HEAD^0", True),
    ("git -C ./repo rev-parse HEAD^{commit}", False),
    ("hands show job-1 --json", True),
    ("hands send --role builder --context keep 'Answer per DESIGN §27.'", True),
    ("hands send --role=builder --context=keep 'Answer per DESIGN §27.'", True),
    ("hands kit check ./repo/kit.zip", True),
    ("hands kit check ~/Downloads/kit.zip", False),  # §32: reads confined
    ("hands resume", True),
    ("hands send --role builder --context clear 'Execute run 2'", False),
    ("hands approve job-1 --human-confirmed --quote 'yes'", False),
    ("hands go", False),
    # §31: role mode is the same table, so the read-only rows read here too —
    # this row was a block before this unit, when §27's list alone was the
    # allowlist and every inspection word was refused
    ("cat ./repo/DESIGN.md", True),
    ("ls ./repo", True),
    ("git -C ./repo log --oneline -5 | head -1", True),
    ("grep -n -e consult ./repo/DESIGN.md", True),
    # ... with the same options and no others, and the same words missing
    ("cat -n ./repo/DESIGN.md", False),
    ("grep -f /tmp/patterns ./repo/DESIGN.md", False),
    *[(probe, False) for probe in REVIEW_14_PROBES],
    ("pwd", False),
    ("find . -name '*.md' -printf %p", False),
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
    # §29: every probe review 12 executed, a `#` anywhere, and the clone pin
    ("hands show x # it's\nhands go #'", False),
    ("hands show x # it's\nhands send --role builder --context clear m #'", False),
    ("ls # it's\ntouch /tmp/rev12-pwned #'", False),
    ("hands status # a note", False),
    ("hands show a#b", False),
    ("git -C /tmp log", False),
    ("git -C ./repo/.. log", False),
    ("git -C repo log --oneline -1", True),
    # §30: review 13's `<<` shapes, and one `-C` only (git applies them in turn)
    *[(shape, False) for shape in REVIEW_13_SHAPES],
    ("git -C ./repo -C ./repo log", False),
    ("git -C repo -C repo log --oneline -1", False),
    # §32: `$`, braces and reserved words, and every probe of review 15
    *[(probe, False) for probe in REVIEW_15_PROBES],
    ("grep -n -e 'done' ./repo/DESIGN.md", True),
    # §32 (should-fix 7): reads confined to the clone and the spool
    ("cat ~/.ssh/id_rsa", False),
    ("cat /proc/self/environ", False),
    ("grep -r x /", False),
    ("ls", False),
    ("cat /home/u/.hands/hands/inbox.jsonl", True),
    ("cat /home/u/.hands/hands.toml", False),
    ("git -C ./repo diff /etc/hostname /dev/null", False),
    ("hands send --role builder --context keep --prompt-file /etc/hostname", False),
    ("hands status | grep -n -e daemon", True),
    ("jq -r '.|env' ./repo/x.json", False),
]


# The role's kits directory, as the self-test's HANDS_KITS (architect/CLAUDE.md's
# KITS). Relative, like the clone: `under` resolves both against the same cwd.
SELFTEST_KITS = "./kits"

# Architect mode (§31): `check(cmd, role="architect", kits="./kits")`.
ARCHITECT_SELFTEST = [
    # the read-only table, as the driver role has it
    ("git -C ./repo fetch && git -C ./repo log --oneline origin/main -10", True),
    ("git -C ./repo show origin/main:meta/ROADMAP.md", True),
    ("git -C ./repo grep -n -e ROADMAP origin/main -- docs", True),
    ("cat ./repo/DESIGN.md", True),
    ("ls -la ./kits", True),
    ("head -n 40 ./repo/meta/ROADMAP.md", True),
    ("wc -l ./kits/m16/KIT.md", True),
    ("git -C /tmp log", False),
    ("git -C ./repo push", False),
    ("git commit -m x", False),
    ("cat -n ./repo/DESIGN.md", False),
    ("pwd", False),
    # the two `hands` commands §31 adds, and the reads the settings allow
    ("hands kit check ./kits/m16 --repo ./repo", True),
    ("hands kit file ./kits/m16", True),
    ("hands --project other kit file ./kits/m16", False),
    ("hands kit file --socket /tmp/other.sock ./kits/m16", False),
    ("hands --project other kit check ./kits/m16", True),
    ("hands show job-1 --json", True),
    ("hands jobs --role builder -n 5", True),
    ("hands inbox", True),
    ("hands pipeline", True),
    ("hands status --json", True),
    # ... and every command that drives a role or decides a gate, by name
    ("hands send --role builder --context keep 'do it'", False),
    ("hands send --role builder --context clear 'do it'", False),
    ("hands approve job-1 --human-confirmed --quote 'yes'", False),
    ("hands deny job-1 --human-confirmed --quote 'no'", False),
    ("hands go", False),
    ("hands put ./kits/x --content y", False),
    ("hands pause", False),
    ("hands resume", False),
    ("hands open job-1", False),
    ("hands tail --role builder -n 20", False),
    ("hands kit apply ./kits/m16.zip", False),
    # the three words this mode adds, every path argument under HANDS_KITS
    ("mkdir -p ./kits/m16/meta", True),
    ("cp -r ./kits/m16 ./kits/m17", True),
    ("mv ./kits/m16/BRIEF.md ./kits/m16/meta/BRIEF.md", True),
    ("mkdir -p /tmp/evil", False),
    ("mkdir -p ./kits/../evil", False),
    ("cp ./repo/DESIGN.md ./kits/DESIGN.md", False),
    ("mv ./kits/a ../a", False),
    ("mkdir", False),
    # §32 (REVIEW-15 blocker 2, H-030): `zip` and `unzip` are rows of no table
    *[(probe, False) for probe in REVIEW_15_ARCHIVE_PROBES],
    ("zip -r ./kits/m16.zip ./kits/m16", False),
    ("unzip -o ./kits/m16.zip -d ./kits/out", False),
    # §28: a word the shell would still expand is not the path the guard read
    ("mkdir -p ./kits/{m16,../evil}", False),
    ("mkdir -p ./kits/*", False),
    ("mkdir -p './kits/m16 x'", True),
    ("mkdir -p './kits/{m16,x}'", False),  # §32: a brace anywhere
    # ... with only the options those rows list
    ("cp -a ./kits/a ./kits/b", False),
    ("mkdir -m 777 ./kits/a", False),
    # §32: no option that names another path or makes a link
    ("cp -t ./kits/b ./kits/a", False),
    ("cp --target-directory=./kits/b ./kits/a", False),
    ("cp -S .bak ./kits/a ./kits/b", False),
    ("cp --backup=numbered ./kits/a ./kits/b", False),
    ("cp -s ./kits/a ./kits/b", False),
    ("cp -l ./kits/a ./kits/b", False),
    ("mv -t ./kits/b ./kits/a", False),
    ("mv -S .bak ./kits/a ./kits/b", False),
    # ... and the mutations §31 never gives it, under the kits directory or not
    ("rm -rf ./kits/m16", False),
    ("touch ./kits/m16/x", False),
    ("chmod 777 ./kits/m16", False),
    ("ln -s /etc ./kits/etc", False),
    ("echo x > ./kits/m16/x", False),
    ("cat ./repo/DESIGN.md | tee ./kits/DESIGN.md", False),
    ("python3 -c 'print(1)'", False),
    ("claude -p hi", False),
    ("mkdir ./kits/a && rm -rf /", False),
    # §30's language holds here too, and §32's
    *[(shape, False) for shape in REVIEW_13_SHAPES],
    *[(probe, False) for probe in REVIEW_14_PROBES],
    *[(probe, False) for probe in REVIEW_15_PROBES],
    # §32 (should-fix 7): reads confined to the clone, the spool and the kits
    ("cat ./kits/m16/KIT.md", True),
    ("cat ~/.ssh/id_rsa", False),
    ("cat /proc/self/environ", False),
    ("grep -r x /", False),
    ("cat /home/u/.hands/hands/jobs/x.json", True),
]

# The write matcher (§31): `(tool_name, file_path, allowed)` in architect mode.
WRITE_SELFTEST = [
    ("Write", "./kits/m16/KIT.md", True),
    ("Edit", "./kits/m16/DESIGN.md", True),
    ("MultiEdit", "./kits/m16/PLAYBOOK.toml", True),
    ("Write", "./kits", True),
    ("Write", "./repo/DESIGN.md", False),
    ("Write", "./kits/../repo/DESIGN.md", False),
    ("Write", "/tmp/evil", False),
    ("Write", "~/kits/x", False),
    ("Write", "", False),
    ("NotebookEdit", "./kits/m16/x.ipynb", False),
    ("Bash", "./kits/m16/KIT.md", False),
]


def selftest() -> int:
    bad = 0
    cases = [(cmd, expected, None) for cmd, expected in SELFTEST]
    cases += [(cmd, expected, DRIVER_ROLE) for cmd, expected in ROLE_SELFTEST]
    cases += [(cmd, expected, ARCHITECT_ROLE) for cmd, expected in ARCHITECT_SELFTEST]
    for cmd, expected, role in cases:
        reason = check(cmd, role=role, consult_role=SELFTEST_CONSULT_ROLE,
                       clone=SELFTEST_CLONE, kits=SELFTEST_KITS, spool=SELFTEST_SPOOL)
        ok = (reason is None) == expected
        if not ok:
            bad += 1
            mode = f" [{ROLE_ENV}={role}]" if role else ""
            print(f"FAIL expected {'allow' if expected else 'block'}{mode}: {cmd!r}  -> {reason}")
    for tool, path, expected in WRITE_SELFTEST:
        data = {"tool_name": tool, "tool_input": {WRITE_PATH_KEY: path}}
        reason = write_violation(data, role=ARCHITECT_ROLE, kits=SELFTEST_KITS)
        if (reason is None) != expected:
            bad += 1
            print(f"FAIL expected {'allow' if expected else 'block'} [--write]: "
                  f"{tool} {path!r}  -> {reason}")
    total = len(cases) + len(WRITE_SELFTEST)
    print(f"selftest: {total - bad}/{total} ok")
    return 1 if bad else 0


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        return selftest()
    write = len(sys.argv) > 1 and sys.argv[1] == "--write"
    try:
        data = json.load(sys.stdin)
    except Exception as e:  # malformed input: fail closed
        print(f"bash_guard: cannot parse hook input ({e}); blocking", file=sys.stderr)
        return 2
    role = os.environ.get(ROLE_ENV) or None
    kits = os.environ.get(KITS_ENV) or None
    if write:
        # §31: the Write|Edit|MultiEdit matcher. Nothing here is judged as a
        # command; only the path is read, and only architect mode has a path
        # it may write to at all.
        reason = write_violation(data if isinstance(data, dict) else {}, role=role, kits=kits)
        if reason is None:
            return 0
        print(f"bash_guard blocked this write ({reason}). The architect writes only under "
              f"${KITS_ENV}, its kits directory; the repository is read through its clone "
              f"and changed by filing a kit (`hands kit file`). If the task needs a write "
              f"anywhere else, reply VERDICT: escalate <reason>.", file=sys.stderr)
        return 2
    if data.get("tool_name") != "Bash":
        return 0
    cmd = (data.get("tool_input") or {}).get("command", "")
    consult_role = os.environ.get(CONSULT_ROLE_ENV) or None
    clone = os.environ.get(CLONE_ENV) or None
    spool = spool_dir() if role in ROLE_MODES else None
    reason = check(cmd, role=role, consult_role=consult_role, clone=clone, kits=kits,
                   spool=spool)
    if reason is None:
        return 0
    if role == ARCHITECT_ROLE:
        print(f"bash_guard blocked this command ({reason}). The architect role may only run "
              f"the guard's read-only table (§31) — read-only git (`git -C` only on "
              f"${CLONE_ENV}), hands "
              f"{'|'.join(sorted(ARCHITECT_HANDS_SUBCOMMANDS))}, hands kit check, hands kit "
              f"file, and {', '.join(sorted(set(COMMAND_TABLE) - {'hands', 'git'}))} with "
              f"the options their rows list — plus "
              f"{', '.join(sorted(KITS_TABLE))} with every path argument under "
              f"${KITS_ENV} — never zip or unzip (§32): stage kits/<name> and file it "
              f"with `hands kit file kits/<name>`, which builds the zip. Its reads are "
              f"confined to the clone and the spool "
              f"({spool or 'none named'}) and ${KITS_ENV}, and the command is one line of "
              f"words, quotes and ; && || | & (§32). It never sends, approves, denies, "
              f"goes, puts or pushes. If the "
              f"kit needs more, reply VERDICT: escalate <reason>.", file=sys.stderr)
        return 2
    if role is not None:
        print(f"bash_guard blocked this command ({reason}). The driver role may only run "
              f"the guard's command table (§31), minus the hands subcommands §27 "
              f"withholds: read-only git (`git -C` only on ${CLONE_ENV}), "
              f"hands show|jobs|inbox|pipeline|status|tail|kit check, "
              f"hands send --context keep to the role the consultation named "
              f"(${CONSULT_ROLE_ENV}), hands resume, and "
              f"{', '.join(sorted(set(COMMAND_TABLE) - {'hands', 'git'}))} with the "
              f"options their rows list; its reads are confined to the clone and the "
              f"spool ({spool or 'none named'}), and the command is one line of words, "
              f"quotes and ; && || | & (§32). If the consultation needs more, reply "
              f"VERDICT: escalate <reason>.",
              file=sys.stderr)
        return 2
    print(f"bash_guard blocked this command ({reason}). The driver may only run the "
          f"guard's command table (§31): {', '.join(sorted(COMMAND_TABLE))}, each with "
          f"the options that command's row lists and no others — a word not in the "
          f"table is refused by name, no listed option takes a value that names a "
          f"program or a file to write, and the command is one line of words, quotes and "
          f"; && || | & with no $, braces or reserved words (§32). If the task needs "
          f"anything else, say 'this is "
          f"for aux' and stop.",
          file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
