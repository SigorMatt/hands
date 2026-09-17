"""The driver kit's Bash guard (§12) under the test suite (§19).

`driver/hooks/bash_guard.py` is a shipped artifact, not an installed module: it
is copied into the driver session's `.claude/hooks/` and run by Claude Code as a
PreToolUse hook. So it is loaded here by path, and every case of its own
`SELFTEST` table is run as a test, one case per test, so a regression names the
command it let through or refused.

That table ships with the guard, so on its own it can only agree with the guard
(review 3 should-fix 1). `ADVERSARIAL` below is the second table: expectations
`tests/` owns, written from DESIGN §12/§20/§21 without reading `SELFTEST`.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import unicodedata
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).parents[1]
GUARD = ROOT / "driver" / "hooks" / "bash_guard.py"


def _load_guard() -> ModuleType:
    spec = importlib.util.spec_from_file_location("bash_guard", GUARD)
    assert spec and spec.loader, f"cannot load the guard from {GUARD}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


guard = _load_guard()


def test_the_case_table_is_not_empty() -> None:
    # A guard whose table emptied would pass every parametrized case below.
    assert len(guard.SELFTEST) >= 50
    assert any(allowed for _, allowed in guard.SELFTEST)
    assert any(not allowed for _, allowed in guard.SELFTEST)


@pytest.mark.parametrize("cmd,allowed", guard.SELFTEST)
def test_selftest_case(cmd: str, allowed: bool) -> None:
    reason = guard.check(cmd)
    if allowed:
        assert reason is None, f"the guard blocked a read-only command: {cmd} -> {reason}"
    else:
        assert reason is not None, f"the guard allowed a writing command: {cmd}"


def test_the_files_own_selftest_reports_zero() -> None:
    # `python3 driver/hooks/bash_guard.py --selftest` is what a human runs.
    assert guard.selftest() == 0


def test_the_table_covers_the_prompt_file_route() -> None:
    """§4/§12: `--prompt-file` is the driver's normal route for prose, so the
    guard's own table has to prove it is not mistaken for something writing."""
    cases = [(cmd, allowed) for cmd, allowed in guard.SELFTEST if "--prompt-file" in cmd]
    assert cases, "the guard's SELFTEST has no `hands send --prompt-file` case"
    assert all(allowed for _, allowed in cases)


# --- ADVERSARIAL ------------------------------------------------------------
#
# An expectation table owned by `tests/`, composed from the policy in DESIGN
# §12/§20/§21 and from the mission brief's case list — deliberately written without
# reading the guard's own `SELFTEST`, so that it can disagree with the guard
# (review 3 should-fix 1). Blocks come from §20's rule that the git subcommand
# allowlist applies to every `git` token anywhere in a command and that `find`
# with `-exec`/`-execdir`/`-ok`/`-okdir`/`-delete`/`-fprint*`/`-fls` is
# forbidden, and from §12's git option policy (DESIGN v3.5 §22): only
# `-C <path>` and `--no-pager` before the subcommand, the `-C` value a single
# path that does not begin with `-`, and after the subcommand only the options
# §12 lists for that subcommand — every other token beginning with `-` is
# refused because it is not listed. The allowed cases are just as load-bearing:
# the driver's whole job is read-only git and reads of the human's `~/git`
# workspace, and a guard that refuses those is useless in a real session.
ADVERSARIAL: list[tuple[str, bool]] = [
    # --- git write behind a `find` wrapper: the argument position ---------
    (r"find . -exec git remote add origin https://x/y.git \;", False),
    (r"find . -exec git notes add -m x HEAD \;", False),
    (r"find . -exec git submodule add https://x/y.git \;", False),
    (r"find . -exec git bisect reset \;", False),
    (r"find . -exec git sparse-checkout init \;", False),
    (r"find . -exec git update-index --add x \;", False),
    (r"find . -exec git branch -D main \;", False),
    (r"find . -exec git update-ref refs/heads/main HEAD \;", False),
    (r"find . -exec git gc --prune=now \;", False),
    (r"find . -exec git push \;", False),
    (r"find . -exec git config user.email x@y.z \;", False),
    # --- second-level mutating verbs, bare -------------------------------
    ("git remote add origin https://x/y.git", False),
    ("git notes add -m x HEAD", False),
    ("git submodule add https://x/y.git", False),
    ("git update-index --add x", False),
    ("git config user.name x", False),
    ("git bisect reset", False),
    ("git sparse-checkout init", False),
    ("git update-ref refs/heads/main HEAD", False),
    ("git branch -D main", False),
    ("git gc --prune=now", False),
    ("git checkout -b claude/x", False),
    ("git stash", False),
    ("git -C ./repo push origin main", False),
    # --- the other `find` wrappers, payload irrelevant --------------------
    (r"find . -execdir git log --oneline \;", False),
    (r"find . -execdir echo hello \;", False),
    (r"find . -ok rm -rf build \;", False),
    (r"find . -okdir cat README.md \;", False),
    ("find . -delete", False),
    ("find . -name '*.pyc' -delete", False),
    # --- other wrappers carrying a git write ------------------------------
    ("echo main | xargs git push origin", False),
    ("ls | xargs -I{} git add {}", False),
    ("env GIT_DIR=.git git commit -m x", False),
    ("sh -c 'git push'", False),
    ('bash -c "git commit -am x"', False),
    # --- chaining ---------------------------------------------------------
    ("ls && git push", False),
    ("ls; git commit -m x", False),
    # --- command substitution inside double quotes ------------------------
    ('echo "$(git push)"', False),
    ('hands send builder "$(git commit -am x)" --context c', False),
    ("echo \"result: `git push origin main`\"", False),
    # --- FALSE POSITIVES: these must be ALLOWED ---------------------------
    ("git -C ./repo rev-parse 8448b6f^0", True),
    # ... except that §32 refuses a brace anywhere, `^{commit}` included
    ("git -C ./repo rev-parse 8448b6f^{commit}", False),
    ("git log --grep=commit -5", True),
    ("git -C ./repo show origin/main:meta/CHECKPOINT.md", True),
    ("git -C ./repo log --oneline --grep=push -20", True),
    # the human's workspace really is `~/git`: live commands, not hypotheticals
    ("ls ~/git", True),
    ("ls -la ~/git/hands", True),
    ("find ~/git/hands -name '*.py'", False),
    ("cat ~/git/hands/DESIGN.md", True),
    ("git -C ~/git/hands log --oneline -5", True),
    ("ls /home/msi/git", True),
    ("cat ~/git/hands/driver/hooks/bash_guard.py", True),
    ("git -C ~/git/hands show HEAD:DESIGN.md", True),
    # §31: `find` left the command table, so even a `find` that only prints is
    # refused now — by name, before any of its own flags are read
    ("find . -name '*.md'", False),
    ("find ~/git -maxdepth 1 -type d", False),
    # ordinary read-only driver traffic
    ("git fetch origin", True),
    ("git status", True),
    ("git diff HEAD~1", True),
    ("git ls-remote origin", True),
    ("hands inbox", True),
    ("cat meta/CHECKPOINT.md", True),
    # §12 rule 6: quoted prose is text, even when it names a writing command
    ('hands send builder "run ./scripts/check and git commit the result" --context c', True),
    ("hands send --prompt-file ~/Downloads/U1.md builder --context c", True),
    # --- §21: git options before the subcommand -------------------------
    # Only `-C <path>` and `--no-pager` may precede a git subcommand. `-c`
    # sets a config key for one invocation, and `diff.external`/`core.pager`
    # are keys whose values git *executes*, so an allowlisted subcommand runs
    # an arbitrary command (review 4 blocker 1: the first of these created
    # /tmp/gprobe-pwned). The payload is quoted, so the guard sees it as text —
    # the option is the write, whatever it carries.
    ("git -c diff.external='touch /tmp/gprobe-pwned' diff --ext-diff", False),
    ("git -c core.pager=touch log", False),
    ('git -c protocol.ext.allow=always fetch "ext::sh -c touch% /tmp/x"', False),
    ("git --config-env=core.pager=EVIL log", False),
    ("git --config-env core.pager=EVIL log", False),
    ("git --exec-path=/tmp/evil status", False),
    ("git --git-dir=./repo/.git log --oneline", False),
    ("git --work-tree=/tmp status", False),
    ("git --namespace=x log", False),
    ("git -p log", False),
    ("git --paginate log", False),
    ("git -C ./repo -c core.pager=touch log", False),
    ("find . -exec git -c core.pager=touch log \\;", False),
    # --- §21: git options after the subcommand ---------------------------
    # `--output` writes a file at any path; `--ext-diff`/`--textconv` run a
    # configured command; `-O`/`--open-files-in-pager` run the pager.
    ("git diff --output=/tmp/x", False),
    ("git show HEAD --output=/tmp/x", False),
    ("git diff --output /tmp/x", False),
    ("git -C ./repo log -p --output=/tmp/x", False),
    ("git diff --ext-diff", False),
    ("git log --ext-diff -1", False),
    ("git show --textconv HEAD:x.bin", False),
    ("git grep --textconv -n x", False),
    ("git grep -O less pattern", False),
    ("git grep --open-files-in-pager pattern", False),
    ("git log --config-env=core.pager=EVIL", False),
    # --- §21: `find`'s writing actions, alongside the exec ones -----------
    ("find . -fprint /tmp/out", False),
    ("find . -fprint0 /tmp/out", False),
    ("find . -type f -fprintf /tmp/out %p", False),
    ("find . -fls /tmp/out", False),
    ("find ~/git -name '*.md' -fprint /tmp/list", False),
    # --- the read-only git the driver actually relies on: ALLOWED ---------
    ("git -C ./repo show origin/main:src/hands/config.py", True),
    ("git -C ./repo log --grep=commit", True),
    ("git -C ./repo rev-parse abc^0", True),
    ("git -C ./repo rev-parse abc^{commit}", False),
    ('git -C ./repo grep -n "git diff" origin/main -- docs', True),
    ("git --no-pager log --oneline -5", True),
    ("git --no-pager -C ./repo diff HEAD~1", True),
    # an allowlist refuses by absence: these read, and are refused anyway,
    # because §12 does not list them for `diff` or for `log`
    ("git -C ./repo diff --no-ext-diff HEAD", False),
    ("git -C ./repo diff --output-indicator-new=X HEAD", False),
    ("git -C ./repo log --no-textconv -1", False),
    # §31: a `find` printing to stdout was a read until v3.14; `find` is not a
    # row of the command table, so it is refused by name
    ("find . -name '*.md' -print", False),
    ("find ~/git/hands -type f -printf %p", False),
    # --- §12: the wrappers an allowlist refuses by absence ----------------
    # `--upload-pack=`/`--exec=` name the program git runs on the other end
    # of a fetch or an ls-remote; review 5 should-fix 1 executed the first two
    # against the tip and both created their file. No denylist entry blocks
    # them here: they are refused because `ls-remote` carries only `--heads`
    # and `--tags`, and `fetch` only `-q`.
    ("git ls-remote --upload-pack='touch /tmp/x/PWNED1' /tmp/x/src", False),
    ("git -C ./src fetch --upload-pack='touch /tmp/x/PWNED2' /tmp/x/src", False),
    ("git fetch --exec='touch /tmp/x/PWNED3' origin", False),
    ("git ls-remote --exec='touch /tmp/x/PWNED3' origin", False),
    ("git fetch --upload-pack=touch origin", False),
    ("git branch --edit-description", False),
    # the `-C` value is a path, so it may not begin with `-`: the guard used
    # to step over the word after `-C` unjudged (review 5 should-fix 1).
    ("git -C ./repo -C --exec-path=/tmp/evil log", False),
    ("git -C --exec-path=/tmp/evil log", False),
    ("git -C", False),
    # --- §12: options that are not listed for their subcommand ------------
    # None of these runs a program; each is refused for the same reason, that
    # §12 does not list it. That is the point of an allowlist.
    ("git fetch --force origin main:main", False),
    ("git fetch --all", False),
    ("git branch -a", False),
    ("git branch --contains HEAD", False),
    ("git remote --verbose", False),
    ("git log -p -1", False),
    ("git log --follow DESIGN.md", False),
    ("git show -s --format=%H HEAD", False),
    ("git diff --cached", False),
    ("git grep -A2 pattern", False),
    ("git cat-file --batch", False),
    ("git ls-files -z", False),
    ("git ls-tree -r HEAD", False),
    ("git rev-parse --git-dir", False),
    ("git status --porcelain", False),
    ("git ls-remote --upload-pack=x", False),
    # --- §12: the options each subcommand does carry: ALLOWED -------------
    ("git -C ./repo log --oneline -n 5", True),
    ("git -C ./repo log --format=%H -n 5", True),
    ("git -C ./repo log --stat -1", True),
    ("git -C ./repo log --name-status HEAD -- docs", True),
    ("git -C ./repo show --stat HEAD", True),
    ("git -C ./repo show --name-status HEAD", True),
    ("git -C ./repo fetch -q", True),
    ("git ls-remote --heads origin", True),
    ("git ls-remote --tags origin", True),
    ("git -C ./repo rev-parse --verify HEAD", True),
    ("git -C ./repo rev-parse --short HEAD", True),
    ("git -C ./repo diff --stat HEAD~1", True),
    ("git -C ./repo diff --name-status HEAD~1", True),
    ("git -C ./repo diff --name-only HEAD~1", True),
    ("git -C ./repo grep -c pattern", True),
    ("git -C ./repo grep -l pattern", True),
    ("git -C ./repo grep -i -n pattern", True),
    ("git -C ./repo grep -e pattern origin/main -- docs", True),
    ("git -C ./repo cat-file -t HEAD", True),
    ("git -C ./repo cat-file -p HEAD:DESIGN.md", True),
    ("git -C ./repo cat-file -e HEAD^0", True),
    ("git -C ./repo cat-file -e HEAD^{commit}", False),
    ("git -C ./repo ls-files", True),
    ("git -C ./repo ls-tree HEAD", True),
    ("git -C ./repo branch --list", True),
    ("git -C ./repo remote -v", True),
    ("git -C ./repo status", True),
    # --- the git the driver kit's own docs tell the driver to run ---------
    # driver/CLAUDE.md rule 2 and its "Starting a mission" section; a line the
    # guard refuses here is a line the driver cannot run at all.
    ("git -C ./repo fetch", True),
    ("git -C ./repo fetch && git -C ./repo log --oneline origin/main -10", True),
    ("git -C ./repo log --oneline origin/main -10", True),
]


@pytest.mark.parametrize("cmd,allowed", ADVERSARIAL)
def test_adversarial_case(cmd: str, allowed: bool) -> None:
    """DESIGN §20/§21: the allowlist applies to every `git` token, only
    `-C <path>` and `--no-pager` may precede a git subcommand and the
    file-writing / command-running options are refused after it; `find`'s
    `-exec` and `-fprint` families are forbidden — checked against
    expectations `tests/` owns."""
    reason = guard.check(cmd)
    if allowed:
        assert reason is None, f"the guard blocked a read-only command: {cmd} -> {reason}"
    else:
        assert reason is not None, f"the guard allowed a writing command: {cmd}"


# The option table DESIGN §12's guard bullet enumerates, transcribed here from
# the design text. It is the whole allowed surface: every other token beginning
# with `-` is refused for that subcommand.
DESIGN_12_OPTIONS: dict[str, set[str]] = {
    "log": {"--oneline", "-n", "--grep", "--format", "--stat", "--name-status"},
    "show": {"--stat", "--name-status"},
    "fetch": {"-q"},
    "ls-remote": {"--heads", "--tags"},
    "rev-parse": {"--verify", "--short"},
    "diff": {"--stat", "--name-status", "--name-only"},
    "grep": {"-n", "-c", "-l", "-i", "-e"},
    "cat-file": {"-t", "-p", "-e"},
    "ls-files": set(),
    "ls-tree": set(),
    "branch": {"--list"},
    "remote": {"-v"},
    "status": set(),
}

# Options whose value names a program to run or a file to write. §12: these are
# never listed — the guard refuses them by absence, not by name, because three
# rounds of denylists each missed one (review 5 should-fix 1 missed
# `--upload-pack`).
NAMES_A_PROGRAM_OR_A_FILE = {
    "--upload-pack", "--exec", "--receive-pack", "--upload-archive", "--output",
    "--ext-diff", "--textconv", "--config-env", "--edit-description",
    "-O", "--open-files-in-pager", "--exec-path", "--git-dir", "--work-tree",
}
# git's global `-c <name>=<value>` is not in the set above because `grep -c`
# is a different option with the same spelling (count, not config). The global
# one is refused by the rule before the subcommand, which is its own case.


def test_the_guard_carries_the_option_table_design_12_enumerates() -> None:
    """§12: a table from allowed subcommand to allowed options, and that table
    is the remaining surface — so the test names every row of it."""
    table = {sub: set(opts) for sub, opts in guard.GIT_SUBCOMMAND_OPTIONS.items()}
    assert table == DESIGN_12_OPTIONS


def test_no_listed_option_names_a_program_or_a_file() -> None:
    """§12: option values that name programs or files are never listed."""
    for sub, opts in guard.GIT_SUBCOMMAND_OPTIONS.items():
        overlap = set(opts) & NAMES_A_PROGRAM_OR_A_FILE
        assert not overlap, f"{sub} lists {sorted(overlap)}"


@pytest.mark.parametrize("sub", sorted(DESIGN_12_OPTIONS))
def test_the_global_config_option_is_refused_before_every_subcommand(sub: str) -> None:
    """`grep -c` is a count, but git's global `-c` sets a config key whose
    value git can execute — it is refused before the subcommand, everywhere."""
    assert guard.check(f"git -c core.pager=touch {sub}") is not None


@pytest.mark.parametrize("sub", sorted(DESIGN_12_OPTIONS))
def test_an_unlisted_option_is_refused_for_every_allowed_subcommand(sub: str) -> None:
    """The allowlist is the policy: an option no row lists is refused wherever
    it is spelled, whether or not anyone thought of it."""
    for option in ("--upload-pack=touch", "--exec=touch", "--output=/tmp/x",
                   "--ext-diff", "--config-env=core.pager=EVIL",
                   "--never-heard-of-this-option"):
        cmd = f"git {sub} {option}"
        assert guard.check(cmd) is not None, f"the guard allowed {cmd}"


def test_the_adversarial_table_is_independent_of_the_guard() -> None:
    # It is the tests' own table: it must not shrink to the guard's, and it
    # must carry both verdicts.
    assert len(ADVERSARIAL) >= 20
    assert sum(1 for _, allowed in ADVERSARIAL if allowed) >= 10
    assert sum(1 for _, allowed in ADVERSARIAL if not allowed) >= 10


# --- ROLE MODE (DESIGN §27) ------------------------------------------------
#
# With `HANDS_ROLE=driver` in the environment the guard is in role mode: the
# driver started by handsd to resolve one consultation. §27's allowlist is
# read-only git; `hands show|jobs|inbox|pipeline|status|tail|kit check`;
# `hands send --context keep` to the role named in the consultation; `hands
# resume`; everything else refused, including `approve`, `deny`, `pause`, `go`,
# `put`, any `--context clear` send, and every write. Choices where §27 is
# silent, pinned here: a send with no `--context` is refused (only an explicit
# `keep` passes); the keep target is builder or aux, never driver, and a send
# with no `--role` is refused; `--file` on a send writes a file, so it is
# refused. §31 settles the words: role mode is the guard's command table minus
# the `hands` subcommands §27 withholds, so the read-only inspection rows
# (`cat`, `ls`, `grep`, ...) read here as they do in the human's session, with
# the options their rows list and no others.
#: §29: the role's clone in these tables, as `HANDS_CLONE` (driver/CLAUDE.md's CLONE).
CLONE = "./repo"

ROLE_MODE: list[tuple[str, bool]] = [
    # read-only git: whatever the guard already treats as read-only
    ("git status", True),
    ("git -C ./repo log --oneline -5", True),
    ("git -C ./repo diff --stat HEAD~1", True),
    ("git -C ./repo show origin/main:DESIGN.md", True),
    ("git -C ./repo grep -n consult origin/main -- DESIGN.md", True),
    ("git -C ./repo fetch -q", True),
    ("git commit -m x", False),
    ("git -C ./repo push", False),
    ("git reset --hard HEAD~1", False),
    ("git -c core.pager=touch log", False),
    # the hands reads §27 lists
    ("hands show job-1", True),
    ("hands show job-1 --json", True),
    ("hands --json show job-1", True),
    ("hands --project hands jobs --role builder -n 5", True),
    ("hands inbox", True),
    ("hands inbox --json", True),
    ("hands pipeline", True),
    ("hands status --json", True),
    ("hands tail --role builder -n 20", True),
    ("hands kit check ./repo/kit.zip --repo ./repo", True),
    # §32 (should-fix 7): a role's reads are confined to the clone and the spool
    ("hands kit check ~/Downloads/kit.zip --repo ./repo", False),
    ("hands resume", True),
    # send: only an explicit keep, only to builder or aux
    ("hands send --role builder --context keep 'Answer: use §27, then continue.'", True),
    ("hands send --role builder --context keep --prompt-file ./repo/answer.txt", True),
    ("hands send --role builder --context keep --prompt-file ~/Downloads/answer.txt", False),
    ("hands send --role=builder --context=keep 'ok'", True),
    ("hands --json send --context keep --role builder 'ok'", True),
    ("hands send --role builder --context clear 'Execute run 2'", False),
    ("hands send --role builder --context=clear 'Execute run 2'", False),
    ("hands send --role builder 'no context'", False),
    ("hands send --role builder --context keep --context clear 'last one wins'", False),
    ("hands send --role builder --context keep --cont clear 'an abbreviation'", False),
    ("hands send --context keep 'no role'", False),
    ("hands send --role driver --context keep 'to itself'", False),
    ("hands send --role builder --role driver --context keep 'last one wins'", False),
    ("hands send --role builder --context keep --file ./x=y 'a write'", False),
    ("hands send --role builder --context keep --fi ./x=y 'an abbreviated write'", False),
    # every other hands command is refused, the authority ones by name
    ("hands approve job-1 --human-confirmed --quote 'yes'", False),
    ("hands deny job-1 --human-confirmed --quote 'no'", False),
    ("hands pause", False),
    ("hands go", False),
    ("hands put ./x --content y", False),
    ("hands cancel job-1 --reason x", False),
    ("hands open job-1", False),
    ("hands kit", False),
    ("hands", False),
    ("hands --socket /tmp/s approve job-1", False),
    ("hands --bogus show job-1", False),
    ("git status && hands approve job-1 --human-confirmed --quote 'y'", False),
    ("hands inbox; hands go", False),
    ("echo $(hands pause)", False),
    ("HANDS_PROJECT=x hands deny job-1", False),
    # every write, and every command word §27 does not list
    ("echo x > f", False),
    ("echo x >> f", False),
    ("rm -rf repo", False),
    ("touch f", False),
    ("cat x | tee f", False),
    ("python3 -c 'print(1)'", False),
    ("claude -p hi", False),
    # §31: role mode is the same table, so the inspection rows read here too
    ("cat ./repo/DESIGN.md", True),
    ("ls ./repo", True),
    ("git -C ./repo log --oneline -5 | head -1", True),
    # ... with their listed options only, and the removed words still refused
    ("cat -n ./repo/DESIGN.md", False),
    ("head -c 20 ./repo/DESIGN.md", False),
    ("sort -o /tmp/x ./repo/DESIGN.md", False),
    ("find . -name '*.md'", False),
    ("pwd", False),
]

ROLE_MODE_ALLOWED_HANDS = {"show", "jobs", "inbox", "pipeline", "status", "tail", "kit", "resume",
                           "send"}


@pytest.mark.parametrize("cmd,allowed", ROLE_MODE)
def test_role_mode_case(cmd: str, allowed: bool) -> None:
    """DESIGN §27: the driver role's allowlist, from `tests/`' own table. §28:
    the consultation named builder, so `HANDS_CONSULT_ROLE` is `builder`. §29: the
    clone is `./repo`, so `HANDS_CLONE` is `./repo`."""
    reason = guard.check(cmd, role="driver", consult_role="builder", clone=CLONE)
    if allowed:
        assert reason is None, f"role mode blocked an allowed command: {cmd} -> {reason}"
    else:
        assert reason is not None, f"role mode allowed a refused command: {cmd}"


def test_the_role_mode_table_names_every_listed_hands_command_and_both_verdicts() -> None:
    named = {cmd.split()[1] for cmd, ok in ROLE_MODE if ok and cmd.startswith("hands ")
             and not cmd.split()[1].startswith("-")}
    named |= {"send", "jobs"}  # listed behind a global option above
    assert named == ROLE_MODE_ALLOWED_HANDS
    assert sum(1 for _, ok in ROLE_MODE if ok) >= 15
    assert sum(1 for _, ok in ROLE_MODE if not ok) >= 30


# Without HANDS_ROLE the guard is the human driver's guard, unchanged: a spot
# check of the same commands under today's rules.
HUMAN_MODE_SPOT_CHECK: list[tuple[str, bool]] = [
    ("git status", True),
    ("git commit -m x", False),
    ("git -C ./repo push", False),
    ("hands approve job-1 --human-confirmed --quote 'yes'", True),
    ("hands send --role builder --context clear 'Execute run 2'", True),
    ("hands send --role builder 'no context'", True),
    ("hands pause", True),
    ("hands go", True),
    ("hands open job-1", False),
    ("cat ./repo/DESIGN.md", True),
    ("git -C ./repo log --oneline -5 | head -1", True),
    ("echo x > f", False),
]


@pytest.mark.parametrize("cmd,allowed", HUMAN_MODE_SPOT_CHECK)
def test_without_a_role_the_same_commands_follow_todays_rules(cmd: str, allowed: bool) -> None:
    for reason in (guard.check(cmd), guard.check(cmd, role=None)):
        assert (reason is None) == allowed, (cmd, reason)


def run_hook(monkeypatch: pytest.MonkeyPatch, cmd: str, role: str | None) -> int:
    import io
    import json

    if role is None:
        monkeypatch.delenv("HANDS_ROLE", raising=False)
    else:
        monkeypatch.setenv("HANDS_ROLE", role)
    monkeypatch.setattr("sys.argv", ["bash_guard.py"])
    monkeypatch.setattr(
        "sys.stdin", io.StringIO(json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd}}))
    )
    return guard.main()


def test_the_hook_takes_role_mode_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """§27: role mode is `HANDS_ROLE=driver` in the environment the hook runs in."""
    assert run_hook(monkeypatch, "hands pause", None) == 0
    assert run_hook(monkeypatch, "hands pause", "") == 0
    assert run_hook(monkeypatch, "hands pause", "driver") == 2
    assert run_hook(monkeypatch, "hands status", "driver") == 0


def test_an_unknown_hands_role_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    assert guard.check("hands status", role="builder") is not None
    assert run_hook(monkeypatch, "hands status", "Driver") == 2


# --- §28: THE GUARD ON WHAT THE SHELL DELIVERS -------------------------------
#
# Review 11 blocker 1: the guard judged a quote-stripped string, so a quoted or
# escaped option word, a lone `&`, `$'…'`, a brace word and an assignment all
# reached `hands` unjudged. Every probe the review executed is below, with the
# verdict it must get in each mode. `None` in the normal-mode column never
# occurs: every probe has a normal-mode verdict, because a probe allowed there
# is still a command the human's session may run (`hands go` is its right).
# Normal mode refuses only what it refused before (writes, `open`) plus the
# §28 rules that hold in both modes ($'…', brace words, assignments, residual
# expansion characters). HANDS_CONSULT_ROLE is `builder` in role mode.
REVIEW_11_PROBES: list[tuple[str, bool]] = [
    # (command, blocked in normal mode) -- always blocked in role mode
    ("hands show x & hands go", False),
    ("hands jobs & hands approve j1 --human-confirmed --quote yes", False),
    ("hands show & hands open x", True),
    ("hands send --role builder --context keep '--context=clear' m", False),
    ('hands send --role builder --context keep "--context=clear" m', False),
    # §30: a backslash is refused before tokenizing, so the escaped spellings
    # are refused in normal mode too
    ("hands send --role builder --context keep \\--context=clear m", True),
    ("hands send --role builder --context keep $'--context=clear' m", True),
    ("hands send --role builder --context keep {--context=clear,m}", True),
    ("x=--context=clear; hands send --role builder --context keep $x m", True),
    ("hands send --role builder --context keep '--file' a=b m", False),
    ("hands send --role builder --context keep \\--file a=b m", True),
    # "to the role named in the consultation": --role other than HANDS_CONSULT_ROLE
    ("hands send --role aux --context keep m", False),
    # and to another project: the CLI accepts --project before and after `send`
    ("hands send --project other --role builder --context keep m", False),
    ("hands --project other send --role builder --context keep m", False),
    ("hands send --role builder --context keep --project=other m", False),
    ("hands send --role builder --context keep --socket /tmp/other.sock m", False),
]


@pytest.mark.parametrize("cmd,blocked_normal", REVIEW_11_PROBES)
def test_review_11_probe_is_blocked_in_role_mode(cmd: str, blocked_normal: bool) -> None:
    reason = guard.check(cmd, role="driver", consult_role="builder", clone=CLONE)
    assert reason is not None, f"role mode allowed a review 11 probe: {cmd}"


@pytest.mark.parametrize("cmd,blocked_normal", REVIEW_11_PROBES)
def test_review_11_probe_in_normal_mode(cmd: str, blocked_normal: bool) -> None:
    reason = guard.check(cmd)
    assert (reason is not None) == blocked_normal, (cmd, reason)


def test_the_guards_own_tables_carry_every_review_11_probe() -> None:
    """§28: the self-test carries every probe review 11 executed, in both modes
    where applicable."""
    role = dict(guard.ROLE_SELFTEST)
    normal = dict(guard.SELFTEST)
    for cmd, blocked_normal in REVIEW_11_PROBES:
        assert role.get(cmd) is False, f"ROLE_SELFTEST lacks the blocked probe {cmd!r}"
        if blocked_normal:
            assert normal.get(cmd) is False, f"SELFTEST lacks the blocked probe {cmd!r}"


# §28, the rules behind the probes, one family at a time. (command, allowed) in
# both modes unless the table says role mode.
SHELL_DELIVERY_BOTH_MODES: list[tuple[str, bool]] = [
    # segments: every separator, a lone `&` included
    ("git status & git push", False),
    ("git status & git -C ./repo log --oneline -1", True),
    ("git status |& git push", False),
    ("(git status) && (git push)", False),
    ("git status; (git push)", False),
    # a quoted separator is text, not a separator
    ("git -C ./repo grep -n 'a;b' origin/main", True),
    ("git -C ./repo grep -n 'a|b&c(d)' origin/main", True),
    # unbalanced quotes
    ("git log 'oops", False),
    ('git log "oops', False),
    # leading assignments, with a command and alone
    ("GIT_PAGER=touch git log", False),
    ("x=1 git status", False),
    ("x=1; git status", False),
    ("x=1", False),
    # residual expansion characters in git argument position (unquoted)
    ("git log $x", False),
    ("git log ${x}", False),
    ("git log --grep=a{b,c}", False),
    ("git log -- *.py", False),
    ("git log -- x?", False),
    ("git log -- [ab]", False),
    ("git log HEAD^!", False),
    ("git log --grep=x=~/y", False),
    # ... and the same characters where the shell does not expand them
    ("git -C ./repo log -- '*.py'", True),
    ("git -C ./repo grep -n -e '*x' origin/main", True),
    ('git -C ./repo grep -n -e "a*b?[c]~" origin/main', True),
    ("git -C ./repo diff --stat HEAD~1", True),
    ("git -C ./repo rev-parse HEAD^0", True),
    # §32: `$` and braces are refused anywhere, quoted or not
    ("git -C ./repo grep -n -e '$x' origin/main", False),
    ("git -C ./repo rev-parse HEAD^{commit}", False),
    ("git -C ./repo rev-parse HEAD^{}", False),
    # the command word itself is what the shell delivers
    ("'git' push", False),
    ("$SHELL -c 'git push'", False),
    ("$GIT push", False),
]


@pytest.mark.parametrize("cmd,allowed", SHELL_DELIVERY_BOTH_MODES)
def test_the_shell_delivery_rules_hold_in_both_modes(cmd: str, allowed: bool) -> None:
    for role in (None, "driver"):
        reason = guard.check(cmd, role=role, consult_role="builder", clone=CLONE)
        assert (reason is None) == allowed, (role, cmd, reason)


# `hands` in both modes: the same residual-character and assignment rules, and
# the subcommand read past the global options' values.
HANDS_BOTH_MODES: list[tuple[str, bool]] = [
    ("hands show $x", False),
    ("hands show x{a,b}", False),
    ("hands show 'x{a,b}'", False),  # §32: a brace anywhere
    ("hands show job-*", False),
    ("hands show 'job-*'", True),
    ("HANDS_PROJECT=other hands show x", False),
    ("hands show $'x'", False),
    ("'hands' show x", True),
    ("hands show x & hands tail --role builder -n 5", True),
]

HANDS_NORMAL_MODE: list[tuple[str, bool]] = [
    # the subcommand is read past a global option's value
    ("hands --project x open y", False),
    ("hands --project=x open y", False),
    ("hands --socket /tmp/s --json open y", False),
    ("hands 'open' y", False),
    ("hands --project x show y", True),
    # quoted prose is text: characters the shell leaves alone inside quotes
    ("hands send --role builder --context clear 'Did it pass? Run *all* [the] checks!'", True),
    ('hands send --role builder --context clear "Did it pass? Run *all* [the] checks"', True),
    # ... but never a `$` or a brace, quoted or not (§32)
    ("hands send --role builder --context clear 'Did it pass? Run {checks}'", False),
    # ... except the ones it still expands inside double quotes
    ('hands send --role builder --context clear "costs $5"', False),
    ('hands send --role builder --context clear "run `id`"', False),
]


@pytest.mark.parametrize("cmd,allowed", HANDS_BOTH_MODES)
def test_hands_rules_that_hold_in_both_modes(cmd: str, allowed: bool) -> None:
    for role in (None, "driver"):
        reason = guard.check(cmd, role=role, consult_role="builder", clone=CLONE)
        assert (reason is None) == allowed, (role, cmd, reason)


@pytest.mark.parametrize("cmd,allowed", HANDS_NORMAL_MODE)
def test_hands_in_normal_mode(cmd: str, allowed: bool) -> None:
    reason = guard.check(cmd)
    assert (reason is None) == allowed, (cmd, reason)


# Role mode's send: exactly one --context, literally `keep`; exactly one --role,
# equal to HANDS_CONSULT_ROLE; no --project or --socket (the send goes to the
# consultation's own project, which the CLI resolves without them). (command,
# HANDS_CONSULT_ROLE, allowed)
ROLE_SEND: list[tuple[str, str | None, bool]] = [
    ("hands send --role builder --context keep m", "builder", True),
    ("hands send --role aux --context keep --prompt-file ./repo/answer.txt", "aux", True),
    ("hands send --role aux --context keep --prompt-file ~/Downloads/answer.txt", "aux", False),
    ("hands send --role=aux --context=keep m", "aux", True),
    ("hands send --role builder --context keep m", "aux", False),
    ("hands send --role aux --context keep m", "builder", False),
    ("hands send --role builder --context keep m", None, False),
    ("hands send --role builder --context keep m", "", False),
    ("hands send --role driver --context keep m", "driver", False),
    ("hands send --role builder --role builder --context keep m", "builder", False),
    ("hands send --role builder --context keep --context keep m", "builder", False),
    ("hands send --role builder --context 'keep' m", "builder", True),
    ("hands send --role builder --context kee m", "builder", False),
    ("hands send --role builder --context=keep= m", "builder", False),
    ("hands send --role builder --context m", "builder", False),
    ("hands send --role builder --context keep -- --context=clear", "builder", False),
    ("hands send --role builder --context keep --fil a=b m", "builder", False),
    ("hands send --role builder --context keep --proj other m", "builder", False),
]


@pytest.mark.parametrize("cmd,consult,allowed", ROLE_SEND)
def test_role_mode_send(cmd: str, consult: str | None, allowed: bool) -> None:
    reason = guard.check(cmd, role="driver", consult_role=consult, clone=CLONE)
    assert (reason is None) == allowed, (cmd, consult, reason)


def test_the_hook_takes_the_consult_role_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """§28: the role the consultation named reaches the guard as
    HANDS_CONSULT_ROLE; unset or empty, no send passes in role mode."""
    send = "hands send --role aux --context keep m"
    monkeypatch.setenv("HANDS_CONSULT_ROLE", "aux")
    assert run_hook(monkeypatch, send, "driver") == 0
    monkeypatch.setenv("HANDS_CONSULT_ROLE", "builder")
    assert run_hook(monkeypatch, send, "driver") == 2
    monkeypatch.setenv("HANDS_CONSULT_ROLE", "")
    assert run_hook(monkeypatch, send, "driver") == 2
    monkeypatch.delenv("HANDS_CONSULT_ROLE")
    assert run_hook(monkeypatch, send, "driver") == 2
    assert run_hook(monkeypatch, "hands status", "driver") == 0
    # the human's session never needed it
    assert run_hook(monkeypatch, send, None) == 0


def test_the_selftest_runs_role_mode_with_a_consult_role() -> None:
    """ROLE_SELFTEST's sends are judged with a named consultation role, so the
    table proves a send can pass, not only that every send is refused."""
    assert guard.SELFTEST_CONSULT_ROLE
    assert any(ok and cmd.startswith("hands send") for cmd, ok in guard.ROLE_SELFTEST)


# --- §30: THE GUARD'S LANGUAGE (review 13 blocker 1; H-026) -------------------
#
# The driver's shell is one line. Before any tokenizing the guard refuses a
# command containing a newline, a carriage return, `<`, `>`, `#`, a backtick,
# `$(`, `\`, `$'` or any control character, in any position (quoted or not),
# naming the first offender and its position; `$` and `!` inside double quotes
# are refused the same way. What remains is words and '…'/"…" quotes. Every
# probe of reviews 12 and 13 is refused this way in both modes; review 11's
# are in REVIEW_11_PROBES above.
REVIEW_12_PROBES: list[str] = [
    "hands show x # it's\nhands go #'",
    "hands show x # it's\nhands send --role builder --context clear m #'",
    "ls # it's\ntouch /tmp/rev12-pwned #'",
]

# REVIEW-13 blocker 1, verbatim: bash's decoding of
# CMD=$'ls <<A\nls \'\nA\ntouch /tmp/rev13-me-pwned\nls "\'" <<\'true\'\n"\ntrue'
# followed by the same shape hiding the role-mode commands the review names.
REVIEW_13_PROBE = "ls <<A\nls '\nA\ntouch /tmp/rev13-me-pwned\nls \"'\" <<'true'\n\"\ntrue"
REVIEW_13_PROBES: list[str] = [
    REVIEW_13_PROBE,
    "ls <<A\nls '\nA\nhands go\nls \"'\" <<'true'\n\"\ntrue",
    "ls <<A\nls '\nA\nhands send --role builder --context clear m\nls \"'\" <<'true'\n\"\ntrue",
    "hands status <<A\nhands show '\nA\nhands go\nhands show \"'\" <<'true'\n\"\ntrue",
]


def _both_modes(cmd: str, clone: str | None = CLONE) -> list[tuple[str | None, str | None]]:
    return [(role, guard.check(cmd, role=role, consult_role="builder", clone=clone))
            for role in (None, "driver")]


@pytest.mark.parametrize("cmd", REVIEW_12_PROBES)
def test_review_12_probe_is_blocked_in_both_modes_naming_the_hash(cmd: str) -> None:
    for role, reason in _both_modes(cmd):
        assert reason is not None, f"a review 12 probe was allowed ({role}): {cmd!r}"
        assert f"a `#` at position {cmd.index('#')}" in reason, (role, cmd, reason)


@pytest.mark.parametrize("cmd", REVIEW_13_PROBES)
def test_review_13_probe_is_blocked_in_both_modes_naming_the_first_angle(cmd: str) -> None:
    for role, reason in _both_modes(cmd):
        assert reason is not None, f"a review 13 probe was allowed ({role}): {cmd!r}"
        assert f"a `<` at position {cmd.index('<')}" in reason, (role, cmd, reason)


@pytest.mark.parametrize("cmd", REVIEW_13_PROBES)
def test_review_13_probe_is_blocked_by_the_hook_in_both_modes(
    monkeypatch: pytest.MonkeyPatch, cmd: str
) -> None:
    monkeypatch.setenv("HANDS_CONSULT_ROLE", "builder")
    monkeypatch.setenv("HANDS_CLONE", CLONE)
    assert run_hook(monkeypatch, cmd, None) == 2
    assert run_hook(monkeypatch, cmd, "driver") == 2


def test_the_hook_file_refuses_the_review_13_probe_naming_its_position(tmp_path: Path) -> None:
    """The shipped file, run as Claude Code runs it: hook JSON on stdin, exit 2,
    the refusal on stderr naming the first offender and its position."""
    stdin = json.dumps({"tool_name": "Bash", "tool_input": {"command": REVIEW_13_PROBE}})
    base = {k: v for k, v in os.environ.items() if not k.startswith("HANDS_")}
    for extra in ({}, {"HANDS_ROLE": "driver", "HANDS_CONSULT_ROLE": "builder",
                       "HANDS_CLONE": str(tmp_path)}):
        done = subprocess.run([sys.executable, str(GUARD)], input=stdin, capture_output=True,
                              text=True, env={**base, **extra}, timeout=30, check=False)
        assert done.returncode == 2, (extra, done.stdout, done.stderr)
        assert "a `<` at position 3" in done.stderr, (extra, done.stderr)


def test_the_guards_own_tables_carry_every_review_13_probe() -> None:
    role, normal = dict(guard.ROLE_SELFTEST), dict(guard.SELFTEST)
    for cmd in REVIEW_13_PROBES:
        assert role.get(cmd) is False, f"ROLE_SELFTEST lacks the blocked probe {cmd!r}"
        assert normal.get(cmd) is False, f"SELFTEST lacks the blocked probe {cmd!r}"


#: (label the refusal names, the offending text). The whole list §30 names.
LANGUAGE_OFFENDERS: list[tuple[str, str]] = [
    ("a newline", "\n"),
    ("a carriage return", "\r"),
    ("a `<`", "<"),
    ("a `>`", ">"),
    ("a `#`", "#"),
    ("a backtick", "`"),
    ("a backslash", "\\"),
    ("a `$`", "$"),  # §32: `$(`, `$'` and every other `$` shape
    ("a `{`", "{"),
    ("a `}`", "}"),
]


@pytest.mark.parametrize("label,offender", LANGUAGE_OFFENDERS)
@pytest.mark.parametrize("shape", ["hands show a{}b", "hands show 'a{}b'", 'hands show "a{}b"'])
def test_each_refused_character_is_refused_quoted_or_not(
    label: str, offender: str, shape: str
) -> None:
    cmd = shape.format(offender)
    position = cmd.index(offender)
    for role, reason in _both_modes(cmd):
        assert reason is not None and f"{label} at position {position}" in reason, (
            role, cmd, reason)


#: Every code point in Unicode's control category (Cc): U+0000–U+001F, U+007F,
#: U+0080–U+009F. A newline and a carriage return carry their own names.
CONTROL_CHARACTERS = [chr(c) for c in range(0x110000) if unicodedata.category(chr(c)) == "Cc"]


def test_the_control_character_list_is_the_whole_category() -> None:
    assert len(CONTROL_CHARACTERS) == 65
    assert "\t" in CONTROL_CHARACTERS and "\x00" in CONTROL_CHARACTERS


@pytest.mark.parametrize("char", CONTROL_CHARACTERS, ids=lambda c: f"U+{ord(c):04X}")
def test_every_control_character_is_refused_naming_its_position(char: str) -> None:
    label = {"\n": "a newline", "\r": "a carriage return"}.get(
        char, f"a control character U+{ord(char):04X}")
    for cmd in (f"hands status{char}", f"hands show 'x{char}'"):
        for role, reason in _both_modes(cmd):
            assert reason is not None and f"{label} at position {cmd.index(char)}" in reason, (
                role, cmd, reason)


#: (command, the first offender's label, its position). Review 12 and 13
#: probes, the commands tables used to allow that use a character §30 refuses,
#: and the commands tables used to block through the removed comment,
#: substitution, escape and redirection handling, which the language now
#: refuses before any of that could run.
REFUSED_BY_THE_LANGUAGE: list[tuple[str, str, int]] = [
    # reviews 12 and 13
    ("hands show x # it's\nhands go #'", "a `#`", 13),
    ("hands show x # it's\nhands send --role builder --context clear m #'", "a `#`", 13),
    ("ls # it's\ntouch /tmp/rev12-pwned #'", "a `#`", 3),
    (REVIEW_13_PROBE, "a `<`", 3),
    # allowed before §30; each needs a character §30 plainly refuses
    ('sleep 20; kill -0 "$(pgrep -f handsd)" && echo alive || echo dead', "a `$`", 19),
    ("ls probe.txt 2>&1", "a `>`", 14),
    ("for i in $(seq 1 3); do echo $i; done", "a `$`", 9),
    ("git status 2>/dev/null", "a `>`", 12),
    ('hands send --role builder --context clear --gate "apply kit" "Apply ~/Downloads/k.zip '
     "(it replaces DESIGN.md), then commit 'plan: kit (v3.1)' and push. Reply: VERDICT: kit "
     'applied <sha>."', "a `<`", 180),
    ("hands send --role aux --context clear 'Review commits since abc123; report blockers=0 "
     "or blockers>0 (count them)'", "a `>`", 97),
    ('echo "a > b"', "a `>`", 8),
    ("echo '$(rm -rf x)'", "a `$`", 6),
    ('kill -0 "$(jq -r .pid ~/.hands/jobs/0mtxb7ecx.json)" && echo alive', "a `$`", 9),
    ("hands send --role builder --context clear --stdin < ~/Downloads/m2-send.txt", "a `<`", 50),
    ("hands send --role builder --context keep \\--context=clear m", "a backslash", 41),
    ("hands send --role builder --context keep \\--file a=b m", "a backslash", 41),
    ("hands send --role builder --context clear 'fix #12'", "a `#`", 47),
    ("hands send --role builder --context keep 'fix #12'", "a `#`", 46),
    ('hands send --role builder --context keep "fix #12"', "a `#`", 46),
    ("hands show x\\#y", "a backslash", 12),
    ("git -C ./repo log --grep='#12'", "a `#`", 26),
    ("git -C ./repo grep -n a\\&b origin/main", "a backslash", 23),
    ("git status 2>&1", "a `>`", 12),
    ("git -C ./repo log --grep=\\$x\\*\\?\\[a\\]\\{b,c\\}\\!", "a backslash", 25),
    # blocked before §30 by parsing the language no longer has
    ("git status\ngit push", "a newline", 10),
    ("echo $(git push)", "a `$`", 5),
    ("echo `git push`", "a backtick", 5),
    ('echo "$(git status; git push)"', "a `$`", 6),
    ('echo "`git push`"', "a backtick", 6),
    ("echo $(echo $(git push))", "a `$`", 5),
    ("git status \\\n; git push", "a backslash", 11),
    ("git log --oneline -1 \\\n--output=/tmp/x", "a backslash", 21),
    ("git log --oneline -1 \\", "a backslash", 21),
    ("echo $(git status", "a `$`", 5),
    ("echo `git status", "a backtick", 5),
    ("git log $'--output=/tmp/x'", "a `$`", 8),
    ("git log --grep=$'a'", "a `$`", 15),
    ('git log "$x"', "a `$`", 9),
    ("git log `echo -1`", "a backtick", 8),
    ('git log "--grep=\\x"', "a backslash", 16),
    ("g\\it push", "a backslash", 1),
    ("git status 2>probe.txt", "a `>`", 12),
    ("git status &> probe.txt", "a `>`", 12),
    ("git status &>probe.txt", "a `>`", 12),
    ("echo hi 2>probe.txt", "a `>`", 9),
    ("hands status # a note", "a `#`", 13),
    ("git -C ./repo log --oneline -1 # a note", "a `#`", 31),
    ("hands show a#b", "a `#`", 12),
    ("hands show x #", "a `#`", 13),
    ("# only a comment", "a `#`", 0),
    ("hands show x\n# it's", "a newline", 12),
    ('hands show "x" #"', "a `#`", 15),
    ("hands show x $#", "a `$`", 13),
    ('hands show "$(hands status # it\'s)"', "a `$`", 12),
    ("hands show `hands status #`", "a backtick", 11),
    ("hands show x ; # y", "a `#`", 15),
    ("hands show 'a#b' c#d", "a `#`", 13),
    ('hands show "$(hands status # x)"', "a `$`", 12),
    ("hands show `hands \\$x #`", "a backtick", 11),
    ("git -C ./repo log --grep=\\\\$x", "a backslash", 25),
    ('git -C ./repo log --grep="a`true`"', "a backtick", 27),
    ('git -C ./repo log --grep="a\\"b"', "a backslash", 27),
    ('git -C ./repo log --grep="a\\x"', "a backslash", 27),
    # the first offender is the one named; quotes
    ("echo a > b # c", "a `>`", 7),
    ('hands send --role builder --context clear "costs $5"', "a `$`", 49),
    ('hands send --role builder --context clear "hi!"', "a `!` inside double quotes", 45),
    ("hands send 'oops", "an unbalanced `'` quote", 11),
    ('git log "oops', 'an unbalanced `"` quote', 8),
    ("hands show 'x' \"a$'\"", "a `$`", 17),
]


@pytest.mark.parametrize("cmd,label,position", REFUSED_BY_THE_LANGUAGE)
def test_the_language_refuses_naming_the_first_offender_and_its_position(
    cmd: str, label: str, position: int
) -> None:
    offender = {"a newline": "\n", "a backslash": "\\", "a backtick": "`"}.get(label)
    if offender is None:
        offender = label.split("`")[1]
    assert cmd[position:].startswith(offender), (cmd, label, position)
    for role, reason in _both_modes(cmd):
        assert reason is not None and f"{label} at position {position}" in reason, (
            role, cmd, reason)


#: What the language still allows: glob characters and `!` outside double
#: quotes are not refused before tokenizing (the plain-word rule judges them,
#: §28, §32), and quoted text without a refused character is text.
ALLOWED_BY_THE_LANGUAGE: list[tuple[str, bool]] = [
    ("hands send --role builder --context keep 'costs 5! (a|b; c&d)'", True),
    ('hands send --role builder --context keep "a*b?[c]~ (x|y; z&w)"', True),
    ("hands send --role builder --context keep 'say \"hi\"'", True),
    ('hands send --role builder --context keep "it\'s"', True),
    ("git -C ./repo grep -n -e '*x' origin/main", True),
    ("hands show x*", False),
    ("hands show x!", False),
]


@pytest.mark.parametrize("cmd,allowed", ALLOWED_BY_THE_LANGUAGE)
def test_what_the_language_leaves_to_the_word_rules(cmd: str, allowed: bool) -> None:
    for role, reason in _both_modes(cmd):
        assert (reason is None) == allowed, (role, cmd, reason)
        if reason is not None:
            assert "position" not in reason, (role, cmd, reason)


#: The parsing §30 makes unreachable is gone from the file, not only bypassed.
REMOVED_FROM_THE_GUARD = ["_scan", "strip_redirect_noise", "strip_quoted", "UnbalancedQuotes",
                          "SUBSTITUTED", "DOUBLE_QUOTE_LIVE",
                          # §32: what `$`, braces and reserved words make unreachable
                          "REFUSED_SEQUENCES", "BRACE_EXPANSION", "SHELL_KEYWORDS",
                          "command_start"]


def test_the_parsing_the_language_makes_unreachable_is_removed() -> None:
    for name in REMOVED_FROM_THE_GUARD:
        assert not hasattr(guard, name), f"the guard still carries {name}"
    source = GUARD.read_text(encoding="utf-8").lower()
    assert source.count("heredoc") == 0
    assert "offset" not in source
    assert "`" not in guard.RESIDUAL and "\\" not in guard.RESIDUAL
    assert not set("${}") & guard.RESIDUAL, "§32 refuses these before tokenizing"
    assert set(guard.REFUSED_IN_DOUBLE_QUOTES) == {"!"}


@pytest.mark.parametrize("cmd", REVIEW_12_PROBES)
def test_review_12_probe_is_blocked_by_the_hook_in_both_modes(
    monkeypatch: pytest.MonkeyPatch, cmd: str
) -> None:
    monkeypatch.setenv("HANDS_CONSULT_ROLE", "builder")
    monkeypatch.setenv("HANDS_CLONE", CLONE)
    assert run_hook(monkeypatch, cmd, None) == 2
    assert run_hook(monkeypatch, cmd, "driver") == 2


def test_the_guards_own_tables_carry_every_review_12_probe() -> None:
    role, normal = dict(guard.ROLE_SELFTEST), dict(guard.SELFTEST)
    for cmd in REVIEW_12_PROBES:
        assert role.get(cmd) is False, f"ROLE_SELFTEST lacks the blocked probe {cmd!r}"
        assert normal.get(cmd) is False, f"SELFTEST lacks the blocked probe {cmd!r}"
    assert role.get("git -C /tmp log") is False
    assert guard.SELFTEST_CLONE == CLONE


# H-024 as §29 states it, for what the §30 language leaves: `git` and `hands`
# argument words in both modes, (clause, command, allowed). There is no
# backslash clause: a backslash is refused before tokenizing.
H024_CLAUSES: list[tuple[str, str, bool]] = [
    ("single quotes", "git -C ./repo log --grep='*?[a]!~'", True),
    ("single quotes", "git -C ./repo log --grep='a'*", False),
    ("double quotes", 'git -C ./repo log --grep="a*b?[c]~"', True),
    ("double quotes", 'git -C ./repo log --grep="$x"', False),
    ("double quotes", 'git -C ./repo log --grep="a!b"', False),
    # §32 retires H-024's brace reading: a brace is refused anywhere, so the
    # shapes it once allowed are refused with the rest
    ("braces", "git -C ./repo log HEAD@{1}", False),
    ("braces", "git -C ./repo rev-parse HEAD^{commit}", False),
    ("braces", "hands show x{1}", False),
    ("braces", "hands show x{a}y}", False),
    ('braces', 'hands show x{"a,b"}', False),
    ("braces", "hands show x{a,b}", False),
    ("braces", "hands show x{1..3}", False),
    ("braces", "hands show x{a,{b}}", False),
    ("tilde", "git -C ./repo diff --stat HEAD~1", True),
    ("tilde", "hands show ~/x", True),
    ("tilde", "hands show a~b", True),
    ("tilde", "hands show a=~/x", False),
    ("tilde", "hands show a:~/x", False),
]


@pytest.mark.parametrize("clause,cmd,allowed", H024_CLAUSES)
def test_h024_reading_clause(clause: str, cmd: str, allowed: bool) -> None:
    for role, reason in _both_modes(cmd):
        assert (reason is None) == allowed, (clause, role, cmd, reason)


def test_h024_every_clause_has_an_allowed_and_a_refused_example() -> None:
    assert {ok for c, _, ok in H024_CLAUSES if c == "braces"} == {False}  # §32
    for clause in {c for c, _, _ in H024_CLAUSES} - {"braces"}:
        verdicts = {ok for c, _, ok in H024_CLAUSES if c == clause}
        assert verdicts == {True, False}, clause


# §29, §30: role mode pins `git -C` to the role's clone (HANDS_CLONE). Both
# sides are compared as `os.path.realpath` (symlinks resolved, joined to the
# hook's working directory); no tilde is expanded, so a `-C ~/…` equals only a
# HANDS_CLONE spelled the same. git applies several `-C` one after the other,
# so role mode refuses a second `-C` (REVIEW-13 should-fix 1). (command,
# HANDS_CLONE, allowed in role mode)
ABS_CLONE = "/home/u/hands-driver/hands/repo"
CLONE_PIN: list[tuple[str, str | None, bool]] = [
    ("git -C /tmp log", ABS_CLONE, False),
    (f"git -C {ABS_CLONE} log --oneline -1", ABS_CLONE, True),
    (f"git -C {ABS_CLONE}/ log", ABS_CLONE, True),
    (f"git -C {ABS_CLONE}/../repo log", ABS_CLONE, True),
    (f"git -C {ABS_CLONE}/.. log", ABS_CLONE, False),
    (f"git -C {ABS_CLONE} -C /tmp log", ABS_CLONE, False),
    (f"git -C /tmp -C {ABS_CLONE} log", ABS_CLONE, False),
    (f"git -C {ABS_CLONE} -C {ABS_CLONE} log", ABS_CLONE, False),
    ("git -C repo -C repo log", "./repo", False),
    ("git -C ./repo -C . log", "./repo", False),
    (f"git -C {ABS_CLONE}x log", ABS_CLONE, False),
    ("git -C ./repo log", "./repo", True),
    ("git -C repo log", "./repo", True),
    ("git -C ./repo/.. log", "./repo", False),
    ("git -C ~/git/hands log --oneline -1", "~/git/hands", True),
    ("git -C ~/git/hands log --oneline -1", "./repo", False),
    ("git -C ./repo log", None, False),
    ("git -C ./repo log", "", False),
    ("git status", None, True),
    ("git -C ./repo status && git -C /tmp status", "./repo", False),
]


@pytest.mark.parametrize("cmd,clone,allowed", CLONE_PIN)
def test_role_mode_pins_git_dash_c_to_the_clone(
    cmd: str, clone: str | None, allowed: bool
) -> None:
    reason = guard.check(cmd, role="driver", consult_role="builder", clone=clone)
    assert (reason is None) == allowed, (cmd, clone, reason)


@pytest.mark.parametrize("cmd,clone,allowed", CLONE_PIN)
def test_normal_mode_does_not_pin_git_dash_c(cmd: str, clone: str | None, allowed: bool) -> None:
    for reason in (guard.check(cmd, clone=clone), guard.check(cmd)):
        assert reason is None, (cmd, reason)


def test_a_relative_dash_c_is_resolved_against_the_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    clone = str(tmp_path / "repo")
    role = {"role": "driver", "consult_role": "builder", "clone": clone}
    assert guard.check("git -C ./repo log --oneline -5", **role) is None
    assert guard.check("git -C repo log", **role) is None
    assert guard.check(f"git -C {clone} log", **role) is None
    assert guard.check("git -C ../repo log", **role) is not None
    assert guard.check("git -C /tmp log", **role) is not None


def test_the_hook_takes_the_clone_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """§29: HANDS_CLONE in the hook's environment; unset or empty, every `git -C`
    is refused in role mode, and the human's session never needs it."""
    monkeypatch.setenv("HANDS_CONSULT_ROLE", "builder")
    monkeypatch.setenv("HANDS_CLONE", ABS_CLONE)
    assert run_hook(monkeypatch, f"git -C {ABS_CLONE} log", "driver") == 0
    assert run_hook(monkeypatch, "git -C /tmp log", "driver") == 2
    monkeypatch.setenv("HANDS_CLONE", "")
    assert run_hook(monkeypatch, f"git -C {ABS_CLONE} log", "driver") == 2
    monkeypatch.delenv("HANDS_CLONE")
    assert run_hook(monkeypatch, f"git -C {ABS_CLONE} log", "driver") == 2
    assert run_hook(monkeypatch, "git status", "driver") == 0
    assert run_hook(monkeypatch, "git -C /tmp log", None) == 0


def test_role_mode_refuses_a_second_dash_c_by_name() -> None:
    reason = guard.check("git -C ./repo -C ./repo log", role="driver", consult_role="builder",
                         clone=CLONE)
    assert reason is not None and "second `-C`" in reason, reason
    assert guard.check("git -C ./repo -C ./repo log") is None


def test_role_mode_pins_git_dash_c_by_realpath_through_a_real_symlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """REVIEW-13 should-fix 1: with `link -> <evil>/sub` in the clone,
    `<clone>/link/..` is the clone to `abspath` and `<evil>` to the kernel."""
    root = tmp_path.resolve()
    clone = root / "clone"
    clone.mkdir()
    subprocess.run(["git", "init", "-q", str(clone)], check=True, timeout=30)
    evil = root / "evil"
    (evil / "sub").mkdir(parents=True)
    (clone / "link").symlink_to(evil / "sub")
    escape = f"{clone}/link/.."
    assert os.path.abspath(escape) == str(clone)
    assert os.path.realpath(escape) == str(evil)
    role = {"role": "driver", "consult_role": "builder", "clone": str(clone)}
    assert guard.check(f"git -C {escape} status", **role) is not None
    assert guard.check(f"git -C {escape}/ status", **role) is not None
    monkeypatch.chdir(root)
    assert guard.check("git -C clone/link/.. status", **role) is not None
    assert guard.check("git -C clone/link/../link/.. status", **role) is not None
    # the clone itself, and the clone reached through a symlink, still pass
    assert guard.check(f"git -C {clone} status", **role) is None
    assert guard.check("git -C clone status", **role) is None
    alias = root / "alias"
    alias.symlink_to(clone)
    assert guard.check(f"git -C {alias} status", **role) is None
    assert guard.check(f"git -C {clone} status", role="driver", consult_role="builder",
                       clone=str(alias)) is None
    # and through the hook, with HANDS_CLONE in the environment
    monkeypatch.setenv("HANDS_CONSULT_ROLE", "builder")
    monkeypatch.setenv("HANDS_CLONE", str(clone))
    assert run_hook(monkeypatch, f"git -C {escape} status", "driver") == 2
    assert run_hook(monkeypatch, f"git -C {clone} status", "driver") == 0


# --- §31: THE GUARD'S COMMAND TABLE (review 14 blocker 1; H-028) -------------
#
# `ALLOWED_FIRST_WORDS` was a bare set of words: outside `git` and `hands` no
# option table was applied, so an allowed word took any option it liked and
# `sort`/`uniq` wrote a file and ran a program in normal mode. §31 replaces the
# set with a table from each command the driver's rules name to the options it
# may take, in both modes; a word not in the table is refused by name.

#: REVIEW-14 blocker 1, the three writes/executions the reviewer reproduced at
#: the tip through the shipped file with hook JSON on stdin. The blocker prints
#: the third with `<big file>`, which is the review's placeholder for the path
#: it ran (REVIEW-14 §4 names it: `/tmp/rev14probe/big.txt`); `<` is refused by
#: §30's language, so the shape that matters is the `--compress-program=`
#: option itself, and the spelling below is the one the review executed.
REVIEW_14_PROBES: list[str] = [
    "sort -o /tmp/rev14-probe/Z1 /etc/hostname",
    "uniq /etc/hostname /tmp/rev14-probe/W5",
    "sort -S 1k --compress-program=/tmp/rev14-probe/prog /tmp/rev14-probe/big.txt",
]


@pytest.mark.parametrize("cmd", REVIEW_14_PROBES)
def test_review_14_probe_is_refused_in_both_modes(cmd: str) -> None:
    """§31: `sort` and `uniq` left the table, so each probe is refused by name."""
    for role, reason in _both_modes(cmd):
        assert reason is not None, f"a review 14 probe was allowed ({role}): {cmd!r}"
        assert repr(cmd.split()[0]) in reason, (role, cmd, reason)


@pytest.mark.parametrize("cmd", REVIEW_14_PROBES)
def test_review_14_probe_is_refused_by_the_shipped_file_in_both_modes(
    tmp_path: Path, cmd: str
) -> None:
    """The way the review ran them: the shipped file, hook JSON on stdin."""
    stdin = json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd}})
    base = {k: v for k, v in os.environ.items() if not k.startswith("HANDS_")}
    for extra in ({}, {"HANDS_ROLE": "driver", "HANDS_CONSULT_ROLE": "builder",
                       "HANDS_CLONE": str(tmp_path)}):
        done = subprocess.run([sys.executable, str(GUARD)], input=stdin, capture_output=True,
                              text=True, env={**base, **extra}, timeout=30, check=False)
        assert done.returncode == 2, (extra, cmd, done.stdout, done.stderr)


def test_the_guards_own_tables_carry_every_review_14_probe() -> None:
    role, normal = dict(guard.ROLE_SELFTEST), dict(guard.SELFTEST)
    for cmd in REVIEW_14_PROBES:
        assert normal.get(cmd) is False, f"SELFTEST lacks the blocked probe {cmd!r}"
        assert role.get(cmd) is False, f"ROLE_SELFTEST lacks the blocked probe {cmd!r}"


#: §31's table, transcribed from the design text: the command, and every option
#: it may take (a value-taking option by its own spelling, `-n` for `-n <int>`).
#: `git` and `hands` carry their existing tables, judged by their own rules, so
#: their rows list no flat option.
DESIGN_31_TABLE: dict[str, set[str]] = {
    "cat": set(),
    "ls": {"-l", "-a", "-la", "-1"},
    "head": {"-n"},
    "tail": {"-n"},
    "wc": {"-l", "-c", "-w"},
    "grep": {"-n", "-c", "-i", "-l", "-E", "-F", "-e", "-r"},
    "jq": {"-r", "-c", "-e"},
    "pgrep": {"-f", "-a", "-l"},
    "sleep": set(),
    "date": set(),
    "echo": set(),
    "kill": {"-0"},
    "git": set(),
    "hands": set(),
}

#: §31: "everything else leaves the table". `pwd` is in neither of §31's lists;
#: the table is closed ("a word not in it is refused by name"), so it leaves too.
REMOVED_WORDS: list[str] = [
    "sort", "uniq", "cut", "tr", "find", "stat", "diff", "printf", "basename",
    "dirname", "realpath", "tty", "id", "whoami", "uptime", "which", "test",
    "[", "seq", "true", "false", "pwd",
]


def test_the_guard_carries_the_command_table_design_31_enumerates() -> None:
    """§31: the table is the whole allowed surface, so the test names every row."""
    assert not hasattr(guard, "ALLOWED_FIRST_WORDS"), "the bare word set is still there"
    table = {name: set(row.flags) | set(row.values)
             for name, row in guard.COMMAND_TABLE.items()}
    assert table == DESIGN_31_TABLE


def test_no_listed_option_of_the_command_table_takes_a_program_or_a_file() -> None:
    """§31: no listed option takes a value that names a program or a file to
    write. The two that take a value take an integer and a grep pattern."""
    takes_a_value = {name: sorted(row.values) for name, row in guard.COMMAND_TABLE.items()
                     if row.values}
    assert takes_a_value == {"grep": ["-e"], "head": ["-n"], "tail": ["-n"]}


@pytest.mark.parametrize("word", REMOVED_WORDS)
def test_a_removed_word_is_refused_by_name_in_both_modes(word: str) -> None:
    for cmd in (f"{word} /etc/hostname", f"ls ./repo; {word}",
                f"cat ./repo/DESIGN.md | {word} -n"):
        for role, reason in _both_modes(cmd):
            assert reason is not None, (role, cmd)
            assert repr(word) in reason, (role, cmd, reason)


#: §31: the table in both modes. Role mode is the same table minus the `hands`
#: subcommands §27 withholds, so the read-only rows read in role mode too —
#: the one thing this unit makes more permissive.
TABLE_BOTH_MODES: list[tuple[str, bool]] = [
    ("cat ./repo/DESIGN.md", True),
    ("cat ./repo/DESIGN.md ./repo/SPEC.md", True),
    ("cat -n ./repo/DESIGN.md", False),
    ("ls ./repo", True),
    ("ls -la ./repo", True),
    ("ls -l -1 ./repo", True),
    ("ls -R ./repo", False),
    ("head -n 20 ./repo/DESIGN.md", True),
    ("head -20 ./repo/DESIGN.md", True),
    ("head -n20 ./repo/DESIGN.md", True),
    ("head -c 20 ./repo/DESIGN.md", False),
    ("head -n x ./repo/DESIGN.md", False),
    ("tail -n 5 ./repo/inbox.jsonl", True),
    ("tail -f ./repo/inbox.jsonl", False),
    ("wc -l -c -w ./repo/DESIGN.md", True),
    ("wc -m ./repo/DESIGN.md", False),
    ("grep -n -i -e consult ./repo/DESIGN.md", True),
    ("grep -r -E -F -c -l pattern ./repo", True),
    ("grep -f /tmp/patterns ./repo/DESIGN.md", False),
    ("grep -o consult ./repo/DESIGN.md", False),
    ("grep --include=*.md consult ./repo", False),
    ("jq -r -c -e .result ./repo/x.json", True),
    ("jq -r '.result' ./repo/x.json", True),
    ("jq --rawfile x /etc/hostname . ~/.hands/jobs/x.json", False),
    ("jq -f /tmp/prog ~/.hands/jobs/x.json", False),
    ("pgrep -f -a -l handsd", True),
    ("pgrep -F /tmp/pidfile handsd", False),
    ("sleep 20", True),
    ("sleep 20 30", False),
    ("sleep 2s", False),
    ("date", True),
    ("date +%s", True),
    ("date -s 2026-01-01", False),
    ("echo alive", True),
    ("echo -n alive", False),
    ("kill -0 1234", True),
    ("kill -0", False),
    ("kill -9 1234", False),
    ("kill 1234", False),
]


@pytest.mark.parametrize("cmd,allowed", TABLE_BOTH_MODES)
def test_the_command_table_holds_in_both_modes(cmd: str, allowed: bool) -> None:
    for role, reason in _both_modes(cmd):
        assert (reason is None) == allowed, (role, cmd, reason)


def test_role_mode_reads_with_the_tables_inspection_rows() -> None:
    """§31: "role mode is the same table minus `hands` subcommands §27
    withholds" — so the read-only rows the guard refused in role mode before
    this unit read there now. This is the one widening in U1."""
    for cmd in ("cat ./repo/DESIGN.md", "ls ./repo", "head -n 5 ./repo/DESIGN.md",
                "grep -n consult ./repo/DESIGN.md", "wc -l ./repo/DESIGN.md",
                "git -C ./repo log --oneline -5 | head -1"):
        assert guard.check(cmd, role="driver", consult_role="builder", clone=CLONE) is None, cmd


def test_role_mode_still_withholds_what_section_27_withholds() -> None:
    """The widening is the inspection rows and nothing else: §27's withheld
    `hands` subcommands, a clear send and `--no-pager` stay refused (§28)."""
    for cmd in ("hands go", "hands approve job-1 --human-confirmed --quote 'yes'",
                "hands deny job-1 --human-confirmed --quote 'no'", "hands pause",
                "hands put ./x --content y", "hands open job-1",
                "hands send --role builder --context clear 'Execute run 2'",
                "git --no-pager log --oneline -3", "git -C /tmp log"):
        assert guard.check(cmd, role="driver", consult_role="builder",
                           clone=CLONE) is not None, cmd


# --- §31: the fuzz corpus over the removed words -----------------------------
#
# The mission 14 U1 corpus was not kept in the tree, so this regenerates one
# from a pinned seed: every command is built from a word §31 removes and that
# word's real options, the write-shaped and execute-shaped ones first, and
# every one must be refused in both modes, by name. The generator avoids every
# character §30 refuses and every word `FORBIDDEN_PATTERNS` names, so what
# refuses each command is the table itself and not the language or a pattern.
FUZZ_SEED = 20260916
FUZZ_COUNT = 10_000

FUZZ_PATHS = ["/etc/hostname", "./repo/DESIGN.md", "~/.hands/inbox.jsonl",
              "/tmp/g1/out", "meta/plan.md", "."]
FUZZ_PROGRAMS = ["/tmp/g1/prog", "./prog", "/tmp/g1/p2"]

#: word -> its real options, `{path}`/`{prog}` filled by the generator.
REMOVED_WORD_OPTIONS: dict[str, list[str]] = {
    "sort": ["-o {path}", "-o{path}", "--output={path}", "--compress-program={prog}",
             "-S 1k", "--parallel=2", "--files0-from={path}", "-u", "-n", "-r",
             "-k 2", "-t :", "-c", "-m", "--random-source={path}"],
    "uniq": ["-c", "-d", "-u", "-i", "-f 1", "-s 2", "-w 3", "--group", "-z"],
    "cut": ["-d :", "-f 1", "-c 1-3", "-b 2", "--output-delimiter=;", "-s",
            "--complement", "-z"],
    "tr": ["-d", "-s", "-c", "-t", "--delete", "a-z A-Z"],
    "find": ["-name x", "-type f", "-maxdepth 1", "-exec {prog} ;", "-execdir {prog} ;",
             "-ok {prog} ;", "-okdir {prog} ;", "-delete", "-fprint {path}",
             "-fprint0 {path}", "-fprintf {path} %p", "-fls {path}", "-print",
             "-printf %p", "-ls", "-newer {path}"],
    "stat": ["-c %n", "-f", "--format=%n", "--printf=%n", "-L", "-t",
             "--file-system", "--cached=never"],
    "diff": ["-u", "-r", "-q", "--to-file={path}", "--from-file={path}",
             "--brief", "--unified=3", "-y", "--color=never", "--label x"],
    "printf": ["%s", "-v x", "%s%s", "--", "a%sb"],
    "basename": ["-a", "-s .md", "-z", "--suffix=.md"],
    "dirname": ["-z", "--zero"],
    "realpath": ["-e", "-m", "-s", "--relative-to={path}", "-z", "-q"],
    "tty": ["-s", "--silent", "--quiet"],
    "id": ["-u", "-g", "-n", "-G", "-Z", "--zero"],
    "whoami": ["--version", "--help"],
    "uptime": ["-p", "-s", "-h"],
    "which": ["-a", "--all", "-s", "--skip-alias"],
    "test": ["-f {path}", "-d {path}", "-x {prog}", "-z x", "-n x", "x = y"],
    "[": ["-f {path} ]", "-x {prog} ]", "x = y ]"],
    "seq": ["-f %g", "-s :", "-w", "--separator=:", "1 10", "-t x"],
    "true": ["--version", "--help"],
    "false": ["--version", "--help"],
    "pwd": ["-L", "-P", "--logical"],
}

#: Where the word sits: alone, as a later segment's head, behind a pipe, in a
#: subshell, and in front of a command the table does allow.
FUZZ_SHAPES = [
    "{cmd}",
    "ls ./repo; {cmd}",
    "{cmd} && ls",
    "cat ./repo/DESIGN.md | {cmd}",
    "( {cmd} )",
    "hands status && {cmd}",
    "{cmd} | wc -l",
    "git -C ./repo log --oneline -1 && {cmd}",
]


def fuzz_corpus(seed: int = FUZZ_SEED, count: int = FUZZ_COUNT) -> list[tuple[str, str]]:
    """`(word, command)` pairs, generated deterministically from `seed`."""
    import random

    rng = random.Random(seed)
    words = sorted(REMOVED_WORD_OPTIONS)
    out: list[tuple[str, str]] = []
    for _ in range(count):
        word = rng.choice(words)
        options = REMOVED_WORD_OPTIONS[word]
        chosen = [options[i] for i in sorted(rng.sample(range(len(options)),
                                                        rng.randint(0, min(3, len(options)))))]
        parts = [word]
        for option in chosen:
            parts.append(option.format(path=rng.choice(FUZZ_PATHS),
                                       prog=rng.choice(FUZZ_PROGRAMS)))
        for _ in range(rng.randint(0, 2)):
            parts.append(rng.choice(FUZZ_PATHS))
        cmd = " ".join(parts)
        out.append((word, rng.choice(FUZZ_SHAPES).format(cmd=cmd,
                                                         path=rng.choice(FUZZ_PATHS))))
    return out


def test_the_fuzz_corpus_is_deterministic_and_covers_every_removed_word() -> None:
    corpus = fuzz_corpus()
    assert len(corpus) == FUZZ_COUNT >= 10_000
    assert corpus == fuzz_corpus(), "the corpus is not reproducible from its seed"
    assert {word for word, _ in corpus} == set(REMOVED_WORD_OPTIONS)
    assert set(REMOVED_WORD_OPTIONS) == set(REMOVED_WORDS)
    # the write-shaped and execute-shaped options are really in it
    joined = "\n".join(cmd for _, cmd in corpus)
    for shape in ("-o /tmp/g1/out", "--compress-program=", "-exec ", "-execdir ",
                  "-delete", "-fprintf ", "--to-file=", "--output-delimiter=",
                  "-S 1k", "-a ", "-f "):
        assert shape in joined, f"the corpus never generates {shape!r}"


def test_every_fuzz_command_is_refused_by_name_in_both_modes() -> None:
    """§31: a word not in the table is refused by name — 10,000 commands over
    the removed words and their real options, in both modes."""
    for word, cmd in fuzz_corpus():
        for role in (None, "driver"):
            reason = guard.check(cmd, role=role, consult_role="builder", clone=CLONE)
            assert reason is not None, (role, cmd)
            assert repr(word) in reason, (role, cmd, reason)


# --- §12, §31: every command line the driver kit tells the driver to run -----

#: `driver/CLAUDE.md`'s parameter block, as the shipped block fills it.
KIT_PARAMETERS = {"CLONE": "./repo", "BRANCH": "main", "PROJECT": "hands"}
#: A span carrying one of these is the kit's placeholder syntax, not a command.
PLACEHOLDER_CHARACTERS = "<>[]|"


def driver_kit_command_lines(text: str | None = None) -> list[str]:
    """The command lines `driver/CLAUDE.md` shows, with its parameters filled.

    Two shapes: an indented line of a command block (its second column, the
    description, cut at the first run of two spaces) and an inline `code` span.
    A span with `<…>`, `[…]` or `|` in it is the kit's placeholder syntax
    (`hands show <job>`), which is not a command line and is left out.
    """
    import re as _re

    if text is None:
        text = (ROOT / "driver" / "CLAUDE.md").read_text(encoding="utf-8")
    spans = [_re.split(r"\s{2,}", line.strip())[0]
             for line in text.splitlines() if line.startswith("    ") and line.strip()]
    spans += [span.strip() for span in _re.findall(r"`([^`\n]+)`", text)]
    out = []
    for span in spans:
        for name, value in KIT_PARAMETERS.items():
            span = _re.sub(rf"\b{name}\b", value, span)
        head = span.split(" ", 1)[0] if " " in span else ""
        if head not in guard.COMMAND_TABLE:
            continue
        if any(c in span for c in PLACEHOLDER_CHARACTERS):
            continue
        words = span.split()
        if len(words) < 2:
            continue  # a bare word, not a command line
        if head == "git" and not set(words) & set(guard.GIT_SUBCOMMAND_OPTIONS):
            continue  # prose about an option (`git -C`), with no subcommand in it
        out.append(span)
    return sorted(set(out))


def test_every_command_line_the_driver_kit_shows_passes_the_guard() -> None:
    """§12: `driver/CLAUDE.md` is the driver's contract. A line it shows that
    the guard refuses is a line the driver cannot run at all (§31)."""
    lines = driver_kit_command_lines()
    assert len(lines) >= 8, lines
    assert "git -C ./repo fetch && git -C ./repo log --oneline origin/main -10" in lines
    assert any(line.startswith("hands send --role builder --context clear ") for line in lines)
    for line in lines:
        assert guard.check(line) is None, f"the kit shows a line the guard refuses: {line}"


# --- §31: ARCHITECT MODE (H-029) --------------------------------------------
#
# With `HANDS_ROLE=architect` the guard guards the architect ROLE: the read-only
# table, `hands kit check` and `hands kit file`, and `mkdir|cp|mv` only when every
# path argument is under `HANDS_KITS` (§32: `zip` and `unzip` left the table). It
# never sends, approves, denies, goes, puts, pauses, resumes or opens, and it never
# pushes. Writes are a
# second `PreToolUse` matcher (`--write`), allowed only under `HANDS_KITS`.
# Choices where §31 is silent, pinned here: the `hands` surface is the one
# `architect/settings.json` allows (show, jobs, inbox, pipeline, status, kit
# check, kit file) — the role's own shipped instruction — so `tail` and `resume`
# are refused, `resume` being denied by those settings outright; a KITS command
# takes at least one path argument; and the options are the minimum a staged
# directory kit needs (`mkdir -p`, `cp -r`, `mv` with none), none of which names
# another path or makes a link (§32).
KITS = "./kits"
ARCHITECT = {"role": "architect", "consult_role": "builder", "clone": CLONE, "kits": KITS}

ARCHITECT_MODE: list[tuple[str, bool]] = [
    # the read-only table, as the driver role has it
    ("cat ./repo/DESIGN.md", True),
    ("ls -la ./kits", True),
    ("head -n 40 ./repo/meta/ROADMAP.md", True),
    ("grep -n -e ROADMAP ./repo/DESIGN.md", True),
    ("git -C ./repo fetch -q", True),
    ("git -C ./repo log --oneline origin/main -10", True),
    ("git -C ./repo show origin/main:DESIGN.md", True),
    ("git -C /tmp log", False),
    ("git -C ./repo push", False),
    ("git commit -m x", False),
    ("cat -n ./repo/DESIGN.md", False),
    ("pwd", False),
    ("find . -name '*.md'", False),
    ("sort -o ./kits/x ./repo/DESIGN.md", False),
    # the two `hands` commands §31 adds
    ("hands kit check ./kits/m16 --repo ./repo", True),
    ("hands kit file ./kits/m16", True),
    ("hands --json kit file ./kits/m16", True),
    # §31 is silent; §27's reason for a role's send holds for the one command
    # that files work: the two options that leave the role's own project are
    # refused on `kit file`, and kept on the `kit check` that writes nothing.
    ("hands --project other kit file ./kits/m16", False),
    ("hands kit file --project=other ./kits/m16", False),
    ("hands kit file --socket /tmp/other.sock ./kits/m16", False),
    ("hands --project other kit check ./kits/m16", True),
    ("hands show job-1 --json", True),
    ("hands jobs --role builder -n 5", True),
    ("hands inbox", True),
    ("hands pipeline", True),
    ("hands status --json", True),
    # ... and every authority command, by name
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
    ("hands cancel job-1 --reason x", False),
    ("hands kit", False),
    ("hands kit apply ./kits/m16.zip", False),
    # the three words architect mode adds, with every path under KITS
    ("mkdir -p ./kits/m16/meta", True),
    ("mkdir ./kits/m16", True),
    ("cp -r ./kits/m16 ./kits/m17", True),
    ("cp ./kits/a ./kits/b", True),
    ("mv ./kits/a ./kits/b", True),
    # §32 (REVIEW-15 blocker 2, H-030): `zip` and `unzip` left the table
    ("zip -r ./kits/m16.zip ./kits/m16", False),
    ("zip -r kits/m.zip kits/m16", False),
    ("unzip -o ./kits/m16.zip -d ./kits/out", False),
    ("unzip ./kits/m16.zip", False),
    ("unzip -o kits/attack.zip", False),
    ("unzip -o ./kits/attack.zip", False),
    ("unzip kits/attack.zip", False),
    # ... and refused as soon as one path argument is not under KITS
    ("mkdir -p /tmp/evil", False),
    ("mkdir -p ./kits/../evil", False),
    ("cp ./repo/DESIGN.md ./kits/DESIGN.md", False),
    ("cp ./kits/a /tmp/b", False),
    ("mv ./kits/a ../a", False),
    ("zip -r /tmp/m16.zip ./kits/m16", False),
    ("zip -r ./kits/m16.zip /etc", False),
    ("unzip -o ./kits/m16.zip -d /tmp/out", False),
    ("unzip /tmp/m16.zip", False),
    ("mkdir", False),
    ("zip -r", False),
    # ... and with only the options the three rows list: none names another path
    # or makes a link (§32)
    ("zip -T ./kits/m16.zip", False),
    ("zip --unzip-command=/tmp/prog ./kits/m16.zip", False),
    ("zip -r ./kits/m16.zip ./kits/m16 -x ./kits/m16/x", False),
    ("cp -a ./kits/a ./kits/b", False),
    ("cp --parents ./kits/a ./kits/b", False),
    ("mv -f ./kits/a ./kits/b", False),
    ("mkdir -m 777 ./kits/a", False),
    ("mkdir --mode=777 ./kits/a", False),
    ("mkdir -v ./kits/a", False),
    ("cp -t ./kits/b ./kits/a", False),
    ("cp -t./kits/b ./kits/a", False),
    ("cp --target-directory=./kits/b ./kits/a", False),
    ("cp --target-directory ./kits/b ./kits/a", False),
    ("cp -rt ./kits/b ./kits/a", False),
    ("cp -S .bak ./kits/a ./kits/b", False),
    ("cp --suffix=.bak ./kits/a ./kits/b", False),
    ("cp -b ./kits/a ./kits/b", False),
    ("cp --backup=numbered ./kits/a ./kits/b", False),
    ("cp -s ./kits/a ./kits/b", False),
    ("cp -l ./kits/a ./kits/b", False),
    ("cp --symbolic-link ./kits/a ./kits/b", False),
    ("cp -L ./kits/a ./kits/b", False),
    ("cp -r -- ./kits/a ./kits/b", False),
    ("mv -t ./kits/b ./kits/a", False),
    ("mv --target-directory=./kits/b ./kits/a", False),
    ("mv -S .bak ./kits/a ./kits/b", False),
    ("mv -b ./kits/a ./kits/b", False),
    ("mv --backup ./kits/a ./kits/b", False),
    ("unzip -p ./kits/m16.zip", False),
    ("unzip -l ./kits/m16.zip", False),
    # ... and the mutations §31 never gives it stay refused, under KITS or not
    ("rm -rf ./kits/m16", False),
    ("touch ./kits/m16/x", False),
    ("chmod 777 ./kits/m16", False),
    ("ln -s /etc ./kits/etc", False),
    ("rmdir ./kits/m16", False),
    ("install ./kits/a ./kits/b", False),
    ("echo x > ./kits/m16/x", False),
    ("cat ./repo/DESIGN.md | tee ./kits/DESIGN.md", False),
    ("python3 -c 'print(1)'", False),
    ("claude -p hi", False),
    ("ls; rm -rf ./kits", False),
    ("mkdir ./kits/a && rm -rf /", False),
]


@pytest.mark.parametrize("cmd,allowed", ARCHITECT_MODE)
def test_architect_mode_case(cmd: str, allowed: bool) -> None:
    """§31: the architect role's surface, from `tests/`' own table."""
    reason = guard.check(cmd, **ARCHITECT)
    if allowed:
        assert reason is None, f"architect mode blocked an allowed command: {cmd} -> {reason}"
    else:
        assert reason is not None, f"architect mode allowed a refused command: {cmd}"


#: §31: the `hands` subcommands architect mode allows — `architect/settings.json`'s
#: own allow list, which is the role's shipped instruction.
ARCHITECT_HANDS = {"show", "jobs", "inbox", "pipeline", "status", "kit"}
#: Refused by name (§31), `resume` and `tail` with them: the settings deny
#: `hands resume` and allow neither.
ARCHITECT_REFUSED_HANDS = ["send", "approve", "deny", "go", "put", "pause", "resume",
                           "open", "tail"]


def test_the_architect_mode_table_names_both_verdicts_and_every_allowed_hands() -> None:
    named = {cmd.split()[1] for cmd, ok in ARCHITECT_MODE
             if ok and cmd.startswith("hands ") and not cmd.split()[1].startswith("-")}
    named |= {"kit"}  # listed behind a global option above
    assert named == ARCHITECT_HANDS
    assert sum(1 for _, ok in ARCHITECT_MODE if ok) >= 15
    assert sum(1 for _, ok in ARCHITECT_MODE if not ok) >= 30


@pytest.mark.parametrize("sub", ARCHITECT_REFUSED_HANDS)
def test_architect_mode_refuses_the_authority_subcommands_by_name(sub: str) -> None:
    reason = guard.check(f"hands {sub} job-1", **ARCHITECT)
    assert reason is not None and sub in reason, (sub, reason)


def test_architect_mode_refuses_every_push_and_every_git_write() -> None:
    for cmd in ("git -C ./repo push", "git push origin main", "git -C ./repo commit -m x",
                "git -C ./repo add -A", "git remote set-url origin x",
                "git -c core.pager=touch log", "git -C ./repo checkout main"):
        assert guard.check(cmd, **ARCHITECT) is not None, cmd


def test_architect_mode_pins_git_dash_c_to_the_clone_as_role_mode_does() -> None:
    assert guard.check("git -C ./repo log --oneline -1", **ARCHITECT) is None
    assert guard.check("git -C ./kits log", **ARCHITECT) is not None
    assert guard.check("git -C ./repo -C ./repo log", **ARCHITECT) is not None
    assert guard.check("git -C ./repo log", role="architect", consult_role=None,
                       clone=None, kits=KITS) is not None


#: §31: "every path argument under `HANDS_KITS`", decided as role mode decides
#: `git -C`: `os.path.realpath` containment, relative paths joined to the hook's
#: cwd, no `~` expansion. (command, HANDS_KITS, allowed)
ABS_KITS = "/home/u/hands-architect/hands/kits"
KITS_PIN: list[tuple[str, str | None, bool]] = [
    (f"mkdir -p {ABS_KITS}/m16", ABS_KITS, True),
    (f"cp -r {ABS_KITS}/m16 {ABS_KITS}/m17", ABS_KITS, True),
    (f"mkdir -p {ABS_KITS}", ABS_KITS, True),
    (f"mkdir -p {ABS_KITS}/../evil", ABS_KITS, False),
    (f"mkdir -p {ABS_KITS}/..", ABS_KITS, False),
    ("mkdir -p /tmp/evil", ABS_KITS, False),
    (f"cp {ABS_KITS}/a /tmp/b", ABS_KITS, False),
    ("mkdir -p ~/kits/m16", ABS_KITS, False),  # no `~` is expanded
    (f"mkdir -p {ABS_KITS}/m16", None, False),  # unset: nothing in the group passes
    (f"mkdir -p {ABS_KITS}/m16", "", False),
    (f"cp -r {ABS_KITS}/m16 {ABS_KITS}/m17", None, False),
    (f"mv {ABS_KITS}/m16 {ABS_KITS}/m17", ABS_KITS, True),
    (f"mv {ABS_KITS}/m16 {ABS_KITS}/..", ABS_KITS, False),
    # §32: gone from the table, under the kits directory or not
    (f"zip -r {ABS_KITS}/m16.zip {ABS_KITS}/m16", ABS_KITS, False),
    (f"unzip -o {ABS_KITS}/m16.zip -d {ABS_KITS}/out", ABS_KITS, False),
]


@pytest.mark.parametrize("cmd,kits,allowed", KITS_PIN)
def test_architect_mode_confines_every_path_argument_to_hands_kits(
    cmd: str, kits: str | None, allowed: bool
) -> None:
    reason = guard.check(cmd, role="architect", consult_role="builder", clone=CLONE, kits=kits)
    assert (reason is None) == allowed, (cmd, kits, reason)


#: §28: a word the shell expands after the guard read it is not the path the
#: guard judged — `./kits/{a,../../evil}` is one path to the guard and two to
#: bash, the second of them outside the kits directory. The KITS rows carry the
#: same residual-character rule `git` and `hands` arguments carry.
KITS_EXPANSION = [
    "mkdir -p ./kits/{a,../../evil}",
    "mkdir ./kits/{m16,../evil}",
    "cp -r ./kits/x ./kits/{a,../../etc}",
    "cp -r ./kits/{a,../../etc/passwd} ./kits/b",
    "mkdir -p ./kits/x{1..3}",
    "mkdir -p ./kits/a?b",
    "mkdir -p ./kits/*",
    "mv ./kits/m16 ./kits/{a,../../evil}",
]


@pytest.mark.parametrize("cmd", KITS_EXPANSION)
def test_architect_mode_refuses_a_path_the_shell_would_still_expand(cmd: str) -> None:
    reason = guard.check(cmd, **ARCHITECT)
    assert reason is not None, f"architect mode allowed an expandable path: {cmd}"
    # §32: a brace is refused before tokenizing; a glob is not a plain word
    assert "expand" in reason or "a `{` at position" in reason, reason


def test_a_quoted_path_under_kits_is_a_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """The other half of §28: inside quotes none of those characters is
    expanded, so a kit whose name carries one is still filed."""
    assert guard.check("mkdir -p './kits/a*b'", **ARCHITECT) is None
    assert guard.check("mkdir -p './kits/{a,b}'", **ARCHITECT) is not None  # §32
    assert guard.check('mkdir -p "./kits/m16 draft"', **ARCHITECT) is None


@pytest.mark.parametrize("cmd,kits,allowed", KITS_PIN)
def test_the_kits_words_are_architect_modes_alone(
    cmd: str, kits: str | None, allowed: bool
) -> None:
    """The three words exist only in architect mode: normal mode and the driver
    role refuse every one of them, whatever HANDS_KITS says."""
    for role in (None, "driver"):
        reason = guard.check(cmd, role=role, consult_role="builder", clone=CLONE, kits=kits)
        assert reason is not None, (role, cmd)


def test_architect_mode_confinement_is_by_realpath_through_a_real_symlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A symlink out of the kits directory lands where the kernel takes it."""
    root = tmp_path.resolve()
    kits = root / "kits"
    (kits / "m16").mkdir(parents=True)
    evil = root / "evil"
    evil.mkdir()
    (kits / "link").symlink_to(evil)
    mode = {"role": "architect", "consult_role": "builder", "clone": CLONE, "kits": str(kits)}
    assert guard.check(f"mkdir -p {kits}/m16/meta", **mode) is None
    assert guard.check(f"mkdir -p {kits}/link/x", **mode) is not None
    assert guard.check(f"mv {kits}/m16 {kits}/link/m16", **mode) is not None
    assert guard.check(f"cp {kits}/m16/a {kits}/link/a", **mode) is not None
    monkeypatch.chdir(root)
    assert guard.check("mkdir -p kits/m16/meta", **mode) is None
    assert guard.check("mkdir -p kits/link/x", **mode) is not None
    assert guard.check("mkdir -p kits/../evil", **mode) is not None


def test_the_hook_takes_architect_mode_and_the_kits_from_the_environment(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    """§31: `HANDS_ROLE=architect` and `HANDS_KITS` in the hook's environment."""
    monkeypatch.setenv("HANDS_KITS", ABS_KITS)
    monkeypatch.setenv("HANDS_CLONE", ABS_CLONE)
    assert run_hook(monkeypatch, f"mkdir -p {ABS_KITS}/m16", "architect") == 0
    assert run_hook(monkeypatch, "mkdir -p /tmp/evil", "architect") == 2
    assert run_hook(monkeypatch, f"hands kit file {ABS_KITS}/m16", "architect") == 0
    assert run_hook(monkeypatch, "hands go", "architect") == 2
    assert run_hook(monkeypatch, f"mkdir -p {ABS_KITS}/m16", "driver") == 2
    assert run_hook(monkeypatch, f"mkdir -p {ABS_KITS}/m16", None) == 2
    monkeypatch.delenv("HANDS_KITS")
    assert run_hook(monkeypatch, f"mkdir -p {ABS_KITS}/m16", "architect") == 2
    assert run_hook(monkeypatch, "hands status", "architect") == 0


# --- §31: the second matcher, Write|Edit|MultiEdit --------------------------
#
# Claude Code names the path `file_path` for Write, Edit and MultiEdit. Any
# other shape, any other tool and any other mode fails closed.
WRITE_MATCHER: list[tuple[dict[str, object], str | None, bool]] = [
    ({"tool_name": "Write", "tool_input": {"file_path": f"{ABS_KITS}/m16/KIT.md"}},
     ABS_KITS, True),
    ({"tool_name": "Edit", "tool_input": {"file_path": f"{ABS_KITS}/m16/KIT.md"}},
     ABS_KITS, True),
    ({"tool_name": "MultiEdit", "tool_input": {"file_path": f"{ABS_KITS}/m16/KIT.md"}},
     ABS_KITS, True),
    ({"tool_name": "Write", "tool_input": {"file_path": ABS_KITS}}, ABS_KITS, True),
    ({"tool_name": "Write", "tool_input": {"file_path": "/tmp/evil"}}, ABS_KITS, False),
    ({"tool_name": "Write", "tool_input": {"file_path": f"{ABS_KITS}/../evil"}},
     ABS_KITS, False),
    ({"tool_name": "Write", "tool_input": {"file_path": "~/kits/x"}}, ABS_KITS, False),
    ({"tool_name": "Write", "tool_input": {"file_path": f"{ABS_KITS}/x"}}, None, False),
    ({"tool_name": "Write", "tool_input": {"file_path": f"{ABS_KITS}/x"}}, "", False),
    # a shape the guard does not recognise
    ({"tool_name": "Write", "tool_input": {}}, ABS_KITS, False),
    ({"tool_name": "Write", "tool_input": {"file_path": ""}}, ABS_KITS, False),
    ({"tool_name": "Write", "tool_input": {"file_path": 7}}, ABS_KITS, False),
    ({"tool_name": "Write", "tool_input": {"path": f"{ABS_KITS}/x"}}, ABS_KITS, False),
    ({"tool_name": "Write", "tool_input": []}, ABS_KITS, False),
    ({"tool_name": "Write"}, ABS_KITS, False),
    ({}, ABS_KITS, False),
    # any other tool
    ({"tool_name": "NotebookEdit", "tool_input": {"notebook_path": f"{ABS_KITS}/x.ipynb"}},
     ABS_KITS, False),
    ({"tool_name": "Bash", "tool_input": {"command": "ls"}}, ABS_KITS, False),
    ({"tool_name": "write", "tool_input": {"file_path": f"{ABS_KITS}/x"}}, ABS_KITS, False),
]


@pytest.mark.parametrize("data,kits,allowed", WRITE_MATCHER)
def test_the_write_matcher_allows_only_paths_under_hands_kits(
    data: dict[str, object], kits: str | None, allowed: bool
) -> None:
    reason = guard.write_violation(data, role="architect", kits=kits)
    assert (reason is None) == allowed, (data, kits, reason)


@pytest.mark.parametrize("data,kits,allowed", WRITE_MATCHER)
def test_the_write_matcher_fails_closed_outside_architect_mode(
    data: dict[str, object], kits: str | None, allowed: bool
) -> None:
    for role in (None, "", "driver", "builder", "Architect"):
        assert guard.write_violation(data, role=role, kits=kits) is not None, (role, data)


def run_write_hook(monkeypatch: pytest.MonkeyPatch, data: object, role: str | None) -> int:
    import io as _io
    import json as _json

    if role is None:
        monkeypatch.delenv("HANDS_ROLE", raising=False)
    else:
        monkeypatch.setenv("HANDS_ROLE", role)
    monkeypatch.setattr("sys.argv", ["bash_guard.py", "--write"])
    monkeypatch.setattr("sys.stdin", _io.StringIO(_json.dumps(data)))
    return guard.main()


def test_the_write_entry_point_reads_the_hook_json_on_stdin(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HANDS_KITS", ABS_KITS)
    allowed = {"tool_name": "Write", "tool_input": {"file_path": f"{ABS_KITS}/KIT.md"}}
    outside = {"tool_name": "Write", "tool_input": {"file_path": "/tmp/evil"}}
    assert run_write_hook(monkeypatch, allowed, "architect") == 0
    assert run_write_hook(monkeypatch, outside, "architect") == 2
    assert run_write_hook(monkeypatch, allowed, "driver") == 2
    assert run_write_hook(monkeypatch, allowed, None) == 2
    monkeypatch.delenv("HANDS_KITS")
    assert run_write_hook(monkeypatch, allowed, "architect") == 2


def test_the_write_entry_point_fails_closed_on_unparsable_input(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    import io as _io

    monkeypatch.setenv("HANDS_ROLE", "architect")
    monkeypatch.setenv("HANDS_KITS", ABS_KITS)
    monkeypatch.setattr("sys.argv", ["bash_guard.py", "--write"])
    monkeypatch.setattr("sys.stdin", _io.StringIO("{not json"))
    assert guard.main() == 2


def test_the_shipped_file_judges_both_matchers_in_architect_mode(tmp_path: Path) -> None:
    """The way Claude Code runs them: the shipped file, hook JSON on stdin."""
    kits = tmp_path / "kits"
    kits.mkdir()
    base = {k: v for k, v in os.environ.items() if not k.startswith("HANDS_")}
    env = {**base, "HANDS_ROLE": "architect", "HANDS_KITS": str(kits),
           "HANDS_CLONE": str(tmp_path / "repo")}
    cases = [
        ([], {"tool_name": "Bash", "tool_input": {"command": f"mkdir -p {kits}/m16"}}, 0),
        ([], {"tool_name": "Bash", "tool_input": {"command": "mkdir -p /tmp/evil"}}, 2),
        ([], {"tool_name": "Bash", "tool_input": {"command": "hands go"}}, 2),
        (["--write"], {"tool_name": "Write", "tool_input": {"file_path": f"{kits}/KIT.md"}}, 0),
        (["--write"], {"tool_name": "Write", "tool_input": {"file_path": "/tmp/evil"}}, 2),
        (["--write"], {"tool_name": "NotebookEdit", "tool_input": {"file_path": f"{kits}/x"}}, 2),
    ]
    for argv, data, expected in cases:
        done = subprocess.run([sys.executable, str(GUARD), *argv], input=json.dumps(data),
                              capture_output=True, text=True, env=env, timeout=30, check=False)
        assert done.returncode == expected, (argv, data, done.stdout, done.stderr)


def test_the_guards_own_architect_table_carries_both_verdicts() -> None:
    assert len(guard.ARCHITECT_SELFTEST) >= 30
    assert any(ok for _, ok in guard.ARCHITECT_SELFTEST)
    assert any(not ok for _, ok in guard.ARCHITECT_SELFTEST)
    assert len(guard.WRITE_SELFTEST) >= 4
    assert {ok for _, _, ok in guard.WRITE_SELFTEST} == {True, False}


@pytest.mark.parametrize("cmd,allowed", guard.ARCHITECT_SELFTEST)
def test_architect_selftest_case(cmd: str, allowed: bool) -> None:
    reason = guard.check(cmd, role=guard.ARCHITECT_ROLE,
                         consult_role=guard.SELFTEST_CONSULT_ROLE,
                         clone=guard.SELFTEST_CLONE, kits=guard.SELFTEST_KITS,
                         spool=guard.SELFTEST_SPOOL)
    assert (reason is None) == allowed, (cmd, reason)


def test_the_bare_word_set_is_gone_from_the_file_as_well_as_the_module() -> None:
    """The mission's acceptance line: the file has no `ALLOWED_FIRST_WORDS`."""
    assert not hasattr(guard, "ALLOWED_FIRST_WORDS"), "the bare word set is still there"
    assert "ALLOWED_FIRST_WORDS" not in GUARD.read_text(encoding="utf-8")


# --- §31: `architect/settings.json` against the CLI and the guard ------------

ARCHITECT_KIT = ROOT / "architect"


def architect_settings() -> dict:
    return json.loads((ARCHITECT_KIT / "settings.json").read_text(encoding="utf-8"))


def test_the_architect_settings_allow_exactly_the_hands_commands_the_guard_allows() -> None:
    """§31: "verify it against the CLI and fix it if the CLI differs" — the
    settings' `hands` allow list and the guard's architect surface are one list."""
    settings = architect_settings()
    allowed = {entry[len("Bash(hands "):-len(":*)")].split()[0]
               for entry in settings["permissions"]["allow"]
               if entry.startswith("Bash(hands ")}
    assert allowed == ARCHITECT_HANDS
    assert "Bash(hands kit check:*)" in settings["permissions"]["allow"]
    assert "Bash(hands kit file:*)" in settings["permissions"]["allow"]
    denied = {entry[len("Bash(hands "):-len(":*)")].split()[0]
              for entry in settings["permissions"]["deny"]
              if entry.startswith("Bash(hands ")}
    assert denied <= set(ARCHITECT_REFUSED_HANDS)
    for sub in denied:
        assert guard.check(f"hands {sub} x", **ARCHITECT) is not None, sub


def test_every_bash_command_the_architect_settings_allow_is_a_word_the_guard_has() -> None:
    """A word the settings allow that the guard has no row for would be a
    permission the role can never use."""
    words = {entry[len("Bash("):entry.index(":*)")].split()[0]
             for entry in architect_settings()["permissions"]["allow"]
             if entry.startswith("Bash(")}
    for word in words:
        assert word in guard.COMMAND_TABLE or word in guard.KITS_TABLE, word


def test_the_architect_settings_wire_both_matchers_to_the_guard() -> None:
    entries = architect_settings()["hooks"]["PreToolUse"]
    by_matcher = {entry["matcher"]: entry["hooks"][0]["command"] for entry in entries}
    assert set(by_matcher) == {"Bash", "Write|Edit|MultiEdit"}
    assert by_matcher["Bash"].endswith("bash_guard.py")
    assert by_matcher["Write|Edit|MultiEdit"].endswith("bash_guard.py --write")


def test_every_command_line_the_architect_kit_shows_passes_the_guard(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`architect/CLAUDE.md` is the role's contract (§31): a line it shows that
    the guard refuses is a line the architect cannot run at all. Since DESIGN
    v3.15 §32 a kit is a directory, `kits/<name>`, filed with `hands kit file <dir>`."""
    import re as _re

    monkeypatch.chdir(tmp_path)
    text = (ARCHITECT_KIT / "CLAUDE.md").read_text(encoding="utf-8")
    spans = [span.strip() for span in _re.findall(r"`([^`\n]+)`", text)]
    lines = []
    for span in spans:
        span = span.replace("kits/<name>", "kits/m16").replace("KITS", "./kits")
        head = span.split(" ", 1)[0]
        if head not in guard.COMMAND_TABLE and head not in guard.KITS_TABLE:
            continue
        if any(c in span for c in PLACEHOLDER_CHARACTERS) or len(span.split()) < 2:
            continue
        lines.append(span)
    assert "git -C ./repo fetch" in lines
    assert "hands kit file kits/m16" in lines
    assert "hands kit check kits/m16 --repo ./repo" in lines
    for line in lines:
        assert guard.check(line, **ARCHITECT) is None, f"the kit shows a refused line: {line}"


# --- §32: THE GUARD'S LANGUAGE, FINISHED (review 15 blocker 1, should-fix 7; H-033)
#
# Besides §30's refusals the guard refuses `$` anywhere, `{` and `}` anywhere,
# and every reserved word of the shell appearing as a word, in every mode,
# before tokenizing. What remains is words, '…'/"…" quotes and `; && || | &`:
# no expansion, no control flow, no redirection, no comment. The option tables
# judge every word, values included, and a word the shell would still expand is
# not a plain word. Role and architect modes are strict subsets, and their
# reads are confined to the clone and the spool's own paths (and, for the
# architect, `HANDS_KITS`).
#
# "As a word" is read the way bash splits words: outside quotes, on spaces and
# on `; & | ( )`. A reserved word inside quotes (`grep -e 'done' f`) is not a
# word bash can read as a reserved word — a quoted word never is — so it stays
# text; the language keeps no control flow either way, because the unquoted
# spelling, the only one bash acts on, is refused.

#: The §32 list, transcribed from the design text.
DESIGN_32_RESERVED_WORDS = {"for", "while", "until", "if", "then", "else", "elif", "fi",
                            "do", "done", "case", "esac", "select", "function", "in",
                            "time", "coproc", "!", "[[", "]]"}

#: The role's spool in the check()-level tables (`~/.hands/<project>/`).
SPOOL = "/home/u/.hands/hands"

#: The three modes, as `check()` keyword arguments.
MODES: dict[str, dict[str, str | None]] = {
    "normal": {"role": None, "consult_role": "builder", "clone": CLONE, "kits": KITS,
               "spool": SPOOL},
    "driver": {"role": "driver", "consult_role": "builder", "clone": CLONE, "kits": KITS,
               "spool": SPOOL},
    "architect": {"role": "architect", "consult_role": "builder", "clone": CLONE,
                  "kits": KITS, "spool": SPOOL},
}
ROLE_MODES_ONLY = ("driver", "architect")


def _all_modes(cmd: str) -> list[tuple[str, str | None]]:
    return [(mode, guard.check(cmd, **kwargs)) for mode, kwargs in MODES.items()]


#: REVIEW-15 blocker 1, verbatim, and the U1 sub-agent's variants.
REVIEW_15_PROBES: list[str] = [
    "for a in '$x'; do echo; done; for c in ${a%x}'(touch${IFS}/tmp/rev15-tip/PWN)'; "
    "do echo ${c@P}; done",
    "for a in '$x'; do echo; done; for c in ${a%x}'(touch${IFS}/tmp/rev15-tip/PWN)'; "
    "do cat ${c@P}; done",
    "for a in '$x'; do echo; done; for c in ${a%x}'(touch${IFS}/tmp/rev15-tip/PWN)'; "
    "do ls ${c@P}; done",
    "for o in -f; do tail $o /etc/hostname; done",
    "for o in --files0-from=F; do wc $o; done",
    "for o in -f; do grep $o F x; done",
    "for s in '%s --set=2020-01-01'; do date +$s; done",
]

#: §32: "`wc --files0-from=`, `grep -f`, `date --set`, `tail -f` outside `hands log`
#: are not in the tables and are refused by name". (command, the name the refusal carries)
REFUSED_BY_NAME_32: list[tuple[str, str]] = [
    ("wc --files0-from=F", "--files0-from=F"),
    ("wc --files0-from=./repo/F", "--files0-from=./repo/F"),
    ("grep -f F x", "-f"),
    ("grep -f ./repo/F ./repo/x", "-f"),
    ("date --set=2020-01-01", "--set=2020-01-01"),
    ("date +%s --set=2020-01-01", "--set=2020-01-01"),
    ("date -s 2020-01-01", "-s"),
    ("tail -f /etc/hostname", "-f"),
    ("tail -f ./repo/DESIGN.md", "-f"),
]


def test_the_guard_carries_the_reserved_words_design_32_enumerates() -> None:
    assert set(guard.RESERVED_WORDS) == DESIGN_32_RESERVED_WORDS


@pytest.mark.parametrize("cmd", REVIEW_15_PROBES)
def test_review_15_probe_is_refused_before_tokenizing_in_all_three_modes(cmd: str) -> None:
    for mode, reason in _all_modes(cmd):
        assert reason is not None, f"a review 15 probe was allowed ({mode}): {cmd!r}"
        assert "before tokenizing" in reason, (mode, cmd, reason)


def _hook_env(tmp_path: Path, mode: str) -> dict[str, str]:
    base = {k: v for k, v in os.environ.items() if not k.startswith("HANDS_")}
    if mode == "normal":
        return base
    return {**base, "HANDS_ROLE": mode, "HANDS_CONSULT_ROLE": "builder",
            "HANDS_CLONE": str(tmp_path / "repo"), "HANDS_KITS": str(tmp_path / "kits")}


def _run_shipped(tmp_path: Path, cmd: str, mode: str) -> subprocess.CompletedProcess[str]:
    stdin = json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd}})
    return subprocess.run([sys.executable, str(GUARD)], input=stdin, capture_output=True,
                          text=True, env=_hook_env(tmp_path, mode), cwd=tmp_path, timeout=30,
                          check=False)


#: REVIEW-15 blocker 2 (§32, H-030): the reviewer's three `unzip` probes, which
#: extracted into the role's cwd — the parent of `HANDS_KITS` — over the guard and
#: its settings, and the `zip` H-030 names, whose entries were never repository paths.
REVIEW_15_ARCHIVE_PROBES = [
    "unzip -o kits/attack.zip",
    "unzip -o ./kits/attack.zip",
    "unzip kits/attack.zip",
    "zip -r kits/m.zip kits/m16",
]


@pytest.mark.parametrize("cmd", REVIEW_15_ARCHIVE_PROBES)
def test_review_15_blocker_2_probe_is_refused_by_name_by_the_shipped_file_in_all_three_modes(
    tmp_path: Path, cmd: str
) -> None:
    """As the reviewer ran them: the shipped file, hook JSON on stdin, an architect
    directory with `kits/` under it (`HANDS_KITS=<cwd>/kits`)."""
    (tmp_path / "kits" / "m16").mkdir(parents=True)
    (tmp_path / "kits" / "attack.zip").write_bytes(b"PK")
    word = cmd.split()[0]
    for mode in MODES:
        done = _run_shipped(tmp_path, cmd, mode)
        assert done.returncode == 2, (mode, cmd, done.stderr)
        assert f"command not in the guard's table: {word!r}" in done.stderr, (mode, done.stderr)


def test_zip_and_unzip_are_rows_of_no_table_and_the_kits_rows_name_no_path() -> None:
    """§32: `unzip` and `zip` leave the table; `mkdir`, `cp`, `mv` remain with no
    option that names another path or makes a link. The final option lists."""
    for word in ("zip", "unzip"):
        assert word not in guard.COMMAND_TABLE and word not in guard.KITS_TABLE, word
        assert word not in guard.KITS_WORDS, word
    assert set(guard.KITS_TABLE) == {"mkdir", "cp", "mv"}
    assert set(guard.KITS_WORDS) == set(guard.KITS_TABLE)
    options = {name: (set(row.flags), dict(row.values)) for name, row in guard.KITS_TABLE.items()}
    assert options == {"mkdir": ({"-p"}, {}), "cp": ({"-r"}, {}), "mv": (set(), {})}
    assert all(row.kits for row in guard.KITS_TABLE.values())
    selftest = dict(guard.ARCHITECT_SELFTEST)
    for probe in REVIEW_15_ARCHIVE_PROBES:
        assert selftest.get(probe) is False, f"the guard's self-test does not carry {probe!r}"


#: Every probe of reviews 11–15, with the modes it is refused in. Review 11's
#: probes attacked role mode; twelve of them are commands the human's session
#: may run (`hands go`, a clear send, `--project`), which §28 left allowed there
#: and REVIEW-12 judged right, so their normal-mode verdict is the table's.
def _every_review_probe() -> list[tuple[str, tuple[str, ...]]]:
    probes: list[tuple[str, tuple[str, ...]]] = []
    for cmd, blocked_normal in REVIEW_11_PROBES:
        probes.append((cmd, tuple(MODES) if blocked_normal else ROLE_MODES_ONLY))
    for cmd in [*REVIEW_12_PROBES, *REVIEW_13_PROBES, *REVIEW_14_PROBES, *REVIEW_15_PROBES]:
        probes.append((cmd, tuple(MODES)))
    return probes


@pytest.mark.parametrize("cmd,modes", _every_review_probe())
def test_every_review_11_to_15_probe_is_refused_by_the_shipped_file(
    tmp_path: Path, cmd: str, modes: tuple[str, ...]
) -> None:
    """The way the reviews ran them: the shipped file, hook JSON on stdin."""
    for mode in modes:
        done = _run_shipped(tmp_path, cmd, mode)
        assert done.returncode == 2, (mode, cmd, done.stdout, done.stderr)


def test_every_review_11_to_15_probe_is_refused_in_the_architects_mode_too() -> None:
    for cmd, _ in _every_review_probe():
        assert guard.check(cmd, **MODES["architect"]) is not None, cmd


@pytest.mark.parametrize("cmd,name", REFUSED_BY_NAME_32)
def test_the_options_section_32_names_are_refused_by_name_in_all_three_modes(
    cmd: str, name: str
) -> None:
    for mode, reason in _all_modes(cmd):
        assert reason is not None and repr(name) in reason, (mode, cmd, reason)


def test_tail_dash_f_is_hands_logs_alone() -> None:
    assert guard.check("hands log -f builder") is None
    assert guard.check("tail -f ./repo/DESIGN.md") is not None


@pytest.mark.parametrize("char", ["$", "{", "}"])
@pytest.mark.parametrize("shape", ["hands show a{}b", "hands show 'a{}b'", 'hands show "a{}b"',
                                   "cat ./repo/{}", "echo {}", "{} ls"])
def test_a_dollar_or_a_brace_is_refused_anywhere_naming_its_position(
    char: str, shape: str
) -> None:
    cmd = shape.format(char)
    position = cmd.index(char)
    for mode, reason in _all_modes(cmd):
        assert reason is not None and f"a `{char}` at position {position}" in reason, (
            mode, cmd, reason)
        assert "before tokenizing" in reason, (mode, cmd, reason)


RESERVED_WORD_POSITIONS = ["{w} ls", "ls; {w}", "ls ;{w}", "echo {w}", "hands status && {w} x",
                           "cat ./repo/x|{w}", "({w})", "ls & {w}", "ls||{w} ls", "echo a {w} b"]


@pytest.mark.parametrize("word", sorted(DESIGN_32_RESERVED_WORDS))
@pytest.mark.parametrize("shape", RESERVED_WORD_POSITIONS)
def test_a_reserved_word_is_refused_as_a_word_in_every_position(word: str, shape: str) -> None:
    cmd = shape.format(w=word)
    at = shape.index("{w}")
    for mode, reason in _all_modes(cmd):
        assert reason is not None, (mode, cmd)
        assert f"the reserved word `{word}` at position {at}" in reason, (mode, cmd, reason)


#: A reserved word inside quotes, or inside a longer word, is not a word bash can
#: read as reserved: it is text. (command, allowed in every mode)
RESERVED_WORD_AS_TEXT: list[tuple[str, bool]] = [
    ("grep -n -e 'done' ./repo/DESIGN.md", True),
    ('grep -n -e "for" ./repo/DESIGN.md', True),
    ("grep -n -e 'if x then y' ./repo/DESIGN.md", True),
    ("grep -n -e done ./repo/DESIGN.md", False),
    ("cat ./repo/done", True),
    ("cat ./repo/in", True),
    ("cat ./repo/ in", False),
    ("grep -n -e d'one' ./repo/DESIGN.md", True),
    ("grep -n -e fi ./repo/DESIGN.md", False),
    ("git -C ./repo log --oneline --grep=done -1", True),
    ("git -C ./repo log --oneline --grep done -1", False),
]


@pytest.mark.parametrize("cmd,allowed", RESERVED_WORD_AS_TEXT)
def test_a_reserved_word_inside_quotes_or_a_longer_word_is_text(cmd: str, allowed: bool) -> None:
    for mode, reason in _all_modes(cmd):
        assert (reason is None) == allowed, (mode, cmd, reason)


#: §32's fuzz corpus: reserved words and `$`/brace shapes, in every segment
#: position, mixed with commands the table allows and every separator.
LANGUAGE_FUZZ_SEED = 20260917
LANGUAGE_FUZZ_COUNT = 10_000
FUZZ_TABLE_COMMANDS = [
    "cat ./repo/DESIGN.md", "ls -la ./repo", "head -n 5 ./repo/DESIGN.md",
    "tail -n 5 ./repo/DESIGN.md", "wc -l ./repo/DESIGN.md", "grep -n -e x ./repo/DESIGN.md",
    "jq -r .result ./repo/x.json", "echo alive", "date +%s", "sleep 1", "kill -0 1",
    "pgrep -f handsd", "hands status", "hands show job-1", "git -C ./repo log --oneline -1",
    "git -C ./repo fetch -q",
]
FUZZ_EXPANSIONS = [
    "$x", "${x}", "${c@P}", "${a%x}", "${IFS}", "$IFS", "$'x'", "$(id)", "$((1+1))", "$[1]",
    "$1", "$@", "$*", "$$", "$?", "$-", "$#", "${!x}", "${x:-id}", "${#x}", "${x@Q}",
    "'$x'", '"$x"', "a$b", "-$o", "+$s", "--x=$y", "{a,b}", "x{1..3}", "{", "}", "'{'",
    '"}"', "{a,b}c", "a}", "{ ls; }", "'${c@P}'", "${a%x}'(touch${IFS}/tmp/x)'",
]
FUZZ_CONTROL_FLOW = [
    "for x in a; do {cmd}; done", "for x in -f; do {cmd}; done", "while {cmd}; do {cmd}; done",
    "until {cmd}; do {cmd}; done", "if {cmd}; then {cmd}; fi",
    "if {cmd}; then {cmd}; elif {cmd}; then {cmd}; else {cmd}; fi",
    "case x in x) {cmd};; esac", "select x in a; do {cmd}; done", "function f ( ) ( {cmd} )",
    "time {cmd}", "coproc {cmd}", "! {cmd}", "[[ -f x ]] && {cmd}", "{cmd} && [[ x ]]",
]
FUZZ_SEPARATORS = ["; ", " && ", " || ", " | ", " & ", ";", "&&", "||", "|", "&"]


def language_fuzz_corpus(seed: int = LANGUAGE_FUZZ_SEED,
                         count: int = LANGUAGE_FUZZ_COUNT) -> list[tuple[str, str]]:
    """`(kind, command)` pairs, generated deterministically from `seed`."""
    import random

    rng = random.Random(seed)
    words = sorted(DESIGN_32_RESERVED_WORDS)
    out: list[tuple[str, str]] = []
    for _ in range(count):
        kind = rng.choice(["expansion", "reserved", "control"])
        segments = [rng.choice(FUZZ_TABLE_COMMANDS) for _ in range(rng.randint(1, 3))]
        at = rng.randrange(len(segments))
        if kind == "expansion":
            offender = rng.choice(FUZZ_EXPANSIONS)
            place = rng.choice(["segment", "argument", "command"])
            if place == "segment":
                segments.insert(at, offender)
            elif place == "argument":
                segments[at] = f"{segments[at]} {offender}"
            else:
                segments[at] = f"{offender} {segments[at]}"
        elif kind == "reserved":
            offender = rng.choice(words)
            place = rng.choice(["segment", "argument", "command"])
            if place == "segment":
                segments.insert(at, offender)
            elif place == "argument":
                segments[at] = f"{segments[at]} {offender}"
            else:
                segments[at] = f"{offender} {segments[at]}"
        else:
            template = rng.choice(FUZZ_CONTROL_FLOW)
            filled = template
            while "{cmd}" in filled:
                filled = filled.replace("{cmd}", rng.choice(FUZZ_TABLE_COMMANDS), 1)
            segments[at] = filled
        cmd = segments[0]
        for segment in segments[1:]:
            cmd += rng.choice(FUZZ_SEPARATORS) + segment
        out.append((kind, cmd))
    return out


def test_the_language_fuzz_corpus_is_deterministic_and_covers_every_shape() -> None:
    corpus = language_fuzz_corpus()
    assert len(corpus) == LANGUAGE_FUZZ_COUNT >= 10_000
    assert corpus == language_fuzz_corpus(), "the corpus is not reproducible from its seed"
    joined = "\n".join(cmd for _, cmd in corpus)
    for shape in [*FUZZ_EXPANSIONS, *(t.split("{cmd}")[0] for t in FUZZ_CONTROL_FLOW)]:
        assert shape in joined, f"the corpus never generates {shape!r}"
    for word in DESIGN_32_RESERVED_WORDS:
        assert any(word in cmd.replace(";", " ").replace("|", " ").replace("&", " ").split()
                   for kind, cmd in corpus if kind == "reserved"), word
    assert {kind for kind, _ in corpus} == {"expansion", "reserved", "control"}


def test_every_language_fuzz_command_is_refused_before_tokenizing_in_all_three_modes() -> None:
    """§32: 10,000 commands over the reserved words and the `$`/brace shapes."""
    for _, cmd in language_fuzz_corpus():
        for mode, reason in _all_modes(cmd):
            assert reason is not None, (mode, cmd)
            assert "before tokenizing" in reason, (mode, cmd, reason)


def test_what_the_language_leaves_is_the_table() -> None:
    """The control group for the corpus: every table command it mixes in is
    allowed on its own and joined by every separator, in every mode that has it."""
    for cmd in FUZZ_TABLE_COMMANDS:
        for mode, reason in _all_modes(cmd):
            assert reason is None, (mode, cmd, reason)
    for separator in FUZZ_SEPARATORS:
        cmd = f"cat ./repo/DESIGN.md{separator}git -C ./repo log --oneline -1"
        for mode, reason in _all_modes(cmd):
            assert reason is None, (mode, cmd, reason)


#: §32: a value that is not a plain word is refused in every row, not only in
#: `git` and `hands`: bash expands `*` to `-f` when a file of that name exists.
NOT_A_PLAIN_WORD: list[str] = [
    "tail -n 5 *", "cat ./repo/*", "head ./repo/?", "wc -l ./repo/[ab]", "grep -n -e x *",
    "ls ./repo/x!", "echo a=~/x", "cat x:~/y",
]


#: With `extglob` on (a shell snapshot may carry it) `@(…)` and `+(…)` are
#: patterns whose inner words the segment split would judge as commands.
EXTGLOB: list[tuple[str, int]] = [
    ("tail -n 1 @(-f)", 11), ("ls ./repo/+(cat)", 11), ("cat ./repo/x'y'(ls)", 15),
    ("echo a(b)", 6),
]


@pytest.mark.parametrize("cmd,position", EXTGLOB)
def test_a_parenthesis_joined_to_a_word_is_refused_before_tokenizing(
    cmd: str, position: int
) -> None:
    for mode, reason in _all_modes(cmd):
        assert reason is not None and f"joined to the word before it at position {position}" in (
            reason), (mode, cmd, reason)
    assert guard.check("echo 'it (works)'") is None
    assert guard.check("ls ./repo && (hands status)") is None


@pytest.mark.parametrize("cmd", NOT_A_PLAIN_WORD)
def test_a_word_the_shell_would_still_expand_is_refused_in_every_row(cmd: str) -> None:
    for mode, reason in _all_modes(cmd):
        assert reason is not None and "expand" in reason, (mode, cmd, reason)


# --- §32 should-fix 7: role-mode reads confined to the clone and the spool ----

CONFINED = "reads are confined to the clone and the spool"

#: REVIEW-15 should-fix 7's probes, and the other path-taking rows.
READS_OUTSIDE: list[str] = [
    "cat ~/.ssh/id_rsa",
    "cat /proc/self/environ",
    "grep -r x /",
    "cat /etc/shadow",
    "head -n 1 /etc/hostname",
    "tail -n 1 /etc/hostname",
    "wc -l /etc/hostname",
    "jq -r .x /etc/x.json",
    "grep -n -e x /etc/hostname",
    "grep -n x /etc/hostname",
    "ls /",
    "ls -la ~",
    "ls",
    "grep -r x",
    "cat ./repo/../CLAUDE.md",
    "cat ./repo/DESIGN.md /etc/hostname",
    "cat /home/u/.hands/hands.toml",
    "cat /home/u/.hands/other/inbox.jsonl",
    "git -C ./repo diff /etc/hostname /dev/null",
    "git -C ./repo diff --stat ../x ./y",
    "git diff CLAUDE.md .claude/settings.json",
    "git -C ./repo fetch -q /home/u/git/private",
    "hands send --role builder --context keep --prompt-file ~/.ssh/id_rsa",
    "hands kit check ~/Downloads/kit.zip",
    "hands --project other kit check /etc/hostname",
    "hands --json kit check --repo ./repo /etc/hostname",
    "hands kit check --repo=/etc ./repo/kit.zip",
    "hands --prompt-file=/etc/hostname show job-1",
    "cat ~root/.ssh/id_rsa",
    "cat ~+/repo/DESIGN.md",
    "git -C ./repo log -- ../../x",
    "hands kit check ./repo --repo /home/u/git/other",
    "hands --socket /tmp/other.sock status",
]

READS_INSIDE: list[str] = [
    "cat ./repo/DESIGN.md",
    "cat repo/DESIGN.md ./repo/meta/plan.md",
    "head -n 5 ./repo/DESIGN.md",
    "tail -n 5 /home/u/.hands/hands/inbox.jsonl",
    "wc -l ./repo/DESIGN.md",
    "grep -r -n -e consult ./repo",
    "grep -n consult ./repo/DESIGN.md",
    "jq -r .result /home/u/.hands/hands/jobs/0mtxb7ecx.json",
    "ls -la ./repo",
    "ls /home/u/.hands/hands/jobs",
    "cat '/home/u/.hands/hands/jobs/x.json'",
    "git -C ./repo diff --stat HEAD~1",
    "git -C ./repo show origin/main:DESIGN.md",
    "git -C ./repo grep -n consult origin/main -- DESIGN.md",
    "hands status",
]

#: A read with no path reads stdin, which in this language only a pipe from
#: another judged segment can fill: allowed.
STDIN_READS: list[str] = [
    "hands status | grep -n -e daemon",
    "git -C ./repo log --oneline -5 | head -n 1",
    "hands show job-1 --json | jq -r .result",
    "cat ./repo/DESIGN.md | wc -l",
    "cat ./repo/DESIGN.md | tail -n 2",
]


@pytest.mark.parametrize("cmd", READS_OUTSIDE)
@pytest.mark.parametrize("mode", ROLE_MODES_ONLY)
def test_role_mode_reads_outside_the_clone_and_the_spool_are_refused_saying_so(
    mode: str, cmd: str
) -> None:
    reason = guard.check(cmd, **MODES[mode])
    assert reason is not None, (mode, cmd)
    assert CONFINED in reason, (mode, cmd, reason)


@pytest.mark.parametrize("cmd", [*READS_INSIDE, *STDIN_READS])
@pytest.mark.parametrize("mode", ROLE_MODES_ONLY)
def test_role_mode_reads_inside_the_clone_or_the_spool_are_allowed(mode: str, cmd: str) -> None:
    reason = guard.check(cmd, **MODES[mode])
    assert reason is None, (mode, cmd, reason)


@pytest.mark.parametrize("cmd", ["cat ~/.ssh/id_rsa", "cat /proc/self/environ", "grep -r x /"])
def test_normal_mode_reads_are_not_confined_by_this_item(cmd: str) -> None:
    assert guard.check(cmd, **MODES["normal"]) is None


def test_the_architect_also_reads_its_kits_directory_and_the_driver_does_not() -> None:
    for cmd in ("ls -la ./kits", "cat ./kits/m16/KIT.md", "hands kit check kits/m16 --repo ./repo"):
        assert guard.check(cmd, **MODES["architect"]) is None, cmd
    for cmd in ("ls -la ./kits", "cat ./kits/m16/KIT.md"):
        reason = guard.check(cmd, **MODES["driver"])
        assert reason is not None and CONFINED in reason, (cmd, reason)


@pytest.mark.parametrize("mode", ROLE_MODES_ONLY)
def test_role_mode_reads_fail_closed_with_no_confinement_named(mode: str) -> None:
    bare = {**MODES[mode], "clone": None, "spool": None, "kits": None}
    for cmd in ("cat ./repo/DESIGN.md", "ls ./repo", f"cat {SPOOL}/inbox.jsonl"):
        reason = guard.check(cmd, **bare)
        assert reason is not None and CONFINED in reason, (mode, cmd, reason)
    empty = {**MODES[mode], "clone": "", "spool": "", "kits": ""}
    assert guard.check("cat ./repo/DESIGN.md", **empty) is not None
    # only the clone unset: the spool still reads, the clone does not
    no_clone = {**MODES[mode], "clone": None}
    assert guard.check(f"cat {SPOOL}/inbox.jsonl", **no_clone) is None
    assert guard.check("cat ./repo/DESIGN.md", **no_clone) is not None
    # a stdin read names no path and needs no confinement
    assert guard.check("hands status | grep -n -e daemon", **bare) is None


@pytest.mark.parametrize("mode", ROLE_MODES_ONLY)
def test_role_mode_jq_may_not_read_the_environment(mode: str) -> None:
    reason = guard.check("jq -r '.|env' ./repo/x.json", **MODES[mode])
    assert reason is not None and "env" in reason, reason
    assert guard.check("jq -r '.|env' ./repo/x.json", **MODES["normal"]) is None


def test_role_mode_reads_are_confined_by_realpath_through_a_real_symlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path.resolve()
    clone = root / "repo"
    clone.mkdir()
    (clone / "DESIGN.md").write_text("x\n", encoding="utf-8")
    secret = root / "secret"
    secret.mkdir()
    (secret / "id_rsa").write_text("k\n", encoding="utf-8")
    (clone / "link").symlink_to(secret)
    monkeypatch.chdir(root)
    for mode in ROLE_MODES_ONLY:
        kwargs = {**MODES[mode], "clone": str(clone)}
        assert guard.check("cat repo/DESIGN.md", **kwargs) is None
        for cmd in ("cat repo/link/id_rsa", f"cat {clone}/link/id_rsa", "ls repo/link",
                    "grep -r x repo/link", "cat repo/link/../../secret/id_rsa"):
            reason = guard.check(cmd, **kwargs)
            assert reason is not None and CONFINED in reason, (mode, cmd, reason)


def test_the_hook_derives_the_spool_the_way_hands_derives_the_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The role's environment names no spool; `hands` finds its project from
    `$HANDS_PROJECT`, else the only `~/.hands/*.toml`. The guard reads the same two
    and confines reads to `~/.hands/<project>/`; anything else names no spool."""
    home = tmp_path / "home"
    (home / ".hands" / "alpha" / "jobs").mkdir(parents=True)
    (home / ".hands" / "alpha.toml").write_text("", encoding="utf-8")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HANDS_CONSULT_ROLE", "builder")
    monkeypatch.setenv("HANDS_CLONE", str(tmp_path / "repo"))
    monkeypatch.setenv("HANDS_KITS", str(tmp_path / "kits"))
    monkeypatch.delenv("HANDS_PROJECT", raising=False)
    inbox = "cat ~/.hands/alpha/inbox.jsonl"
    for role in ROLE_MODES_ONLY:
        assert run_hook(monkeypatch, inbox, role) == 0, role
        assert run_hook(monkeypatch, "cat ~/.hands/alpha.toml", role) == 2, role
        assert run_hook(monkeypatch, "ls ~/.hands", role) == 2, role
        assert run_hook(monkeypatch, "cat ~/.ssh/id_rsa", role) == 2, role
    # two configs and no HANDS_PROJECT: no spool is named, so none reads
    (home / ".hands" / "beta.toml").write_text("", encoding="utf-8")
    assert run_hook(monkeypatch, inbox, "driver") == 2
    monkeypatch.setenv("HANDS_PROJECT", "alpha")
    assert run_hook(monkeypatch, inbox, "driver") == 0
    assert run_hook(monkeypatch, "cat ~/.hands/beta/inbox.jsonl", "driver") == 2
    for bad in ("", "..", "a/b"):
        monkeypatch.setenv("HANDS_PROJECT", bad)
        assert run_hook(monkeypatch, inbox, "driver") == 2, bad
    assert guard.spool_dir() is None


@pytest.mark.parametrize("cmd", ["cat ~/.ssh/id_rsa", "cat /proc/self/environ", "grep -r x /"])
@pytest.mark.parametrize("mode", ROLE_MODES_ONLY)
def test_should_fix_7_probes_are_refused_by_the_shipped_file_saying_so(
    tmp_path: Path, mode: str, cmd: str
) -> None:
    done = _run_shipped(tmp_path, cmd, mode)
    assert done.returncode == 2, (mode, cmd, done.stdout, done.stderr)
    assert CONFINED in done.stderr, (mode, cmd, done.stderr)
    inside = _run_shipped(tmp_path, "cat ./repo/DESIGN.md", mode)
    assert inside.returncode == 0, (mode, inside.stderr)


def test_role_and_architect_modes_are_strict_subsets_of_normal_mode() -> None:
    """§32: every command a role mode allows, normal mode allows too — over every
    command in this file's tables and both corpora."""
    commands = {cmd for cmd, _ in guard.SELFTEST} | {cmd for cmd, _ in guard.ROLE_SELFTEST}
    commands |= {cmd for cmd, _ in guard.ARCHITECT_SELFTEST}
    commands |= {cmd for cmd, _ in [*ADVERSARIAL, *ROLE_MODE, *TABLE_BOTH_MODES,
                                    *RESERVED_WORD_AS_TEXT, *SHELL_DELIVERY_BOTH_MODES,
                                    *HANDS_BOTH_MODES]}
    commands |= {*READS_INSIDE, *READS_OUTSIDE, *STDIN_READS, *FUZZ_TABLE_COMMANDS}
    commands |= {cmd for cmd, _, _ in ROLE_SEND}
    # the architect's `mkdir|cp|mv` rows are table rows of that mode
    # alone (§31, U2's), not language, so they are the one exception
    commands = {c for c in commands if c.split(" ")[0] not in guard.KITS_TABLE}
    for cmd in sorted(commands):
        normal = guard.check(cmd, **MODES["normal"])
        for mode in ROLE_MODES_ONLY:
            if guard.check(cmd, **MODES[mode]) is None:
                assert normal is None, (mode, cmd, normal)


def test_every_command_line_the_driver_kits_role_section_shows_passes_in_role_mode() -> None:
    """driver/CLAUDE.md "As a role": what it tells the driver ROLE to run passes
    the guard in driver mode, not only in the human's session."""
    text = (ROOT / "driver" / "CLAUDE.md").read_text(encoding="utf-8")
    section = text.split("## As a role", 1)[1]
    lines = driver_kit_command_lines(section)
    assert {"hands show", "hands jobs", "hands resume"} <= set(lines), lines
    for line in lines:
        reason = guard.check(line, **MODES["driver"])
        assert reason is None, f"the role section shows a refused line: {line} -> {reason}"


def test_no_kit_command_line_uses_what_section_32_refuses() -> None:
    """Every command line both kit files show, in its own mode, is free of `$`,
    braces and reserved words — none of them needed the rule weakened."""
    for line in driver_kit_command_lines():
        assert guard.language_problem(line) is None, line
    text = (ARCHITECT_KIT / "CLAUDE.md").read_text(encoding="utf-8")
    import re as _re

    text = text.replace("kits/<name>", "kits/m16")
    spans = [span.strip() for span in _re.findall(r"`([^`\n]+)`", text)]
    for span in spans:
        if span.split(" ", 1)[0] in guard.COMMAND_TABLE and len(span.split()) >= 2:
            assert guard.language_problem(span) is None, span


# --- §33: architect-mode cp/mv and a symlink (REVIEW-16 should-fix 2, 3) ----
#
# The guard resolved the destination directory, not the file `cp` writes: with a
# relative symlink already inside `kits/` (planted by something else — the
# architect cannot make one), `cp -r kits/a/h kits/` moved it up a level so it
# pointed out of kits, and `cp kits/pay/h kits/` then wrote through it over the
# guard. And a `kits` that is itself a link to `.claude` let the write matcher
# pass `<cwd>/.claude/settings.json`.
GUARD_TEXT = GUARD.read_text(encoding="utf-8")


def _architect_cwd(tmp_path: Path) -> Path:
    """An architect directory as the reviewer built it: the guard under
    `.claude/hooks/`, a `kits/pay/h` whose content would neuter it."""
    cwd = tmp_path / "arch"
    (cwd / ".claude" / "hooks").mkdir(parents=True)
    (cwd / ".claude" / "hooks" / "bash_guard.py").write_text(GUARD_TEXT, encoding="utf-8")
    (cwd / ".claude" / "settings.json").write_text("{}", encoding="utf-8")
    (cwd / "kits" / "pay").mkdir(parents=True)
    (cwd / "kits" / "pay" / "h").write_text("# NEUTERED\n", encoding="utf-8")
    return cwd


def _architect_hook(cwd: Path, data: dict[str, object], *argv: str) -> int:
    base = {k: v for k, v in os.environ.items() if not k.startswith("HANDS_")}
    env = {**base, "HANDS_ROLE": "architect", "HANDS_KITS": str(cwd / "kits"),
           "HANDS_CLONE": str(cwd / "repo")}
    done = subprocess.run([sys.executable, str(cwd / ".claude" / "hooks" / "bash_guard.py"),
                           *argv], input=json.dumps(data), capture_output=True, text=True,
                          env=env, cwd=cwd, timeout=30, check=False)
    return done.returncode


def _guarded_bash(cwd: Path, cmd: str) -> int:
    """The shipped hook judges `cmd`; only when it allows it does real bash run it,
    in the architect's cwd, as Claude Code would."""
    code = _architect_hook(cwd, {"tool_name": "Bash", "tool_input": {"command": cmd}})
    if code == 0:
        subprocess.run(["bash", "-c", cmd], cwd=cwd, capture_output=True, timeout=30,
                       check=False)
    return code


REVIEW_16_CP_PROBES = ["cp -r kits/a/h kits/", "cp kits/pay/h kits/"]


def test_review_16_should_fix_2_probe_is_refused_and_the_guard_file_is_unchanged(
    tmp_path: Path,
) -> None:
    """The reviewer's sequence, verbatim, under real bash: `kits/a/h ->
    ../.claude/hooks/bash_guard.py` planted (dangling, inside kits), then the two
    `cp` commands. Both are refused and the guard is still the guard."""
    cwd = _architect_cwd(tmp_path)
    (cwd / "kits" / "a").mkdir()
    (cwd / "kits" / "a" / "h").symlink_to("../.claude/hooks/bash_guard.py")
    codes = [_guarded_bash(cwd, cmd) for cmd in REVIEW_16_CP_PROBES]
    assert codes == [2, 2], codes
    assert (cwd / ".claude" / "hooks" / "bash_guard.py").read_text(encoding="utf-8") == GUARD_TEXT
    assert not (cwd / "kits" / "h").is_symlink()


#: `(planted link under kits, its target, command)`: every way the probe's class
#: writes or moves through a link — a link pointing out already, a link inside a
#: directory `cp -r` or `mv` carries, and a link inside the tree `cp -r` merges into.
KITS_LINK_SHAPES = [
    ("h", "../.claude/hooks/bash_guard.py", "cp kits/pay/h kits/"),
    ("h", "../.claude/hooks/bash_guard.py", "cp kits/pay/h kits/h"),
    ("h", "../.claude/hooks/bash_guard.py", "mv kits/pay/h kits/h"),
    ("a/h", "../.claude/hooks/bash_guard.py", "mv kits/a/h kits/"),
    ("a/h", "../.claude/hooks/bash_guard.py", "cp -r kits/a kits/b"),
    ("a/h", "../.claude/hooks/bash_guard.py", "mv kits/a kits/pay/a"),
    ("dst/pay/h", "../../../.claude/hooks/bash_guard.py", "cp -r kits/pay kits/dst"),
    ("link", "../.claude", "cp -r kits/pay kits/other"),
]


@pytest.mark.parametrize("link,target,cmd", KITS_LINK_SHAPES)
def test_architect_cp_and_mv_are_refused_while_kits_holds_a_symlink(
    tmp_path: Path, link: str, target: str, cmd: str
) -> None:
    """§33, the rule stated: in architect mode `cp` and `mv` are refused while
    anything under `HANDS_KITS` is a symlink, wherever it sits and wherever it
    points; `mkdir` still runs (it moves nothing and writes no file content)."""
    cwd = _architect_cwd(tmp_path)
    planted = cwd / "kits" / link
    planted.parent.mkdir(parents=True, exist_ok=True)
    planted.symlink_to(target)
    assert _guarded_bash(cwd, cmd) == 2, cmd
    assert (cwd / ".claude" / "hooks" / "bash_guard.py").read_text(encoding="utf-8") == GUARD_TEXT
    kits = str(cwd / "kits")
    reason = guard.check(f"{cmd.replace('kits/', kits + '/')}", role="architect",
                         consult_role="builder", clone=str(cwd / "repo"), kits=kits)
    # a link already pointing out is refused by realpath; the rest by §33's rule
    assert reason is not None and ("symlink" in reason or "not '" in reason), reason
    assert guard.check(f"mkdir -p {kits}/m17", role="architect", consult_role="builder",
                       clone=str(cwd / "repo"), kits=kits) is None


def test_architect_cp_and_mv_run_on_a_kits_tree_without_a_symlink(tmp_path: Path) -> None:
    """The other half: a clean kits tree stages a kit as before, under real bash."""
    cwd = _architect_cwd(tmp_path)
    for cmd in ("mkdir -p kits/m17/meta", "cp -r kits/pay kits/m17/pay",
                "cp kits/pay/h kits/m17/meta/h", "mv kits/m17/meta/h kits/m17/h"):
        assert _guarded_bash(cwd, cmd) == 0, cmd
    assert (cwd / "kits" / "m17" / "h").read_text(encoding="utf-8") == "# NEUTERED\n"
    assert (cwd / "kits" / "m17" / "pay" / "h").is_file()


@pytest.mark.parametrize("spelling", ["kits", "kits/", "./kits", "sub/../kits"])
def test_a_hands_kits_that_is_a_symlink_refuses_every_kits_row_and_the_write_matcher(
    tmp_path: Path, spelling: str
) -> None:
    """REVIEW-16 should-fix 3: `ln -s .claude kits`, then the write matcher for
    `<cwd>/.claude/settings.json` exited 0. §33: `HANDS_KITS` must not be a
    symlink; with one, `mkdir`, `cp`, `mv` and every write are refused."""
    cwd = tmp_path / "arch"
    (cwd / ".claude" / "hooks").mkdir(parents=True)
    (cwd / ".claude" / "hooks" / "bash_guard.py").write_text(GUARD_TEXT, encoding="utf-8")
    (cwd / ".claude" / "settings.json").write_text("{}", encoding="utf-8")
    (cwd / "sub").mkdir()
    (cwd / "kits").symlink_to(".claude")
    settings = str(cwd / ".claude" / "settings.json")
    write = {"tool_name": "Write", "tool_input": {"file_path": settings}}
    assert _architect_hook(cwd, write, "--write") != 0
    kits = os.path.join(str(cwd), spelling)
    assert guard.write_violation(
        {"tool_name": "Write", "tool_input": {"file_path": f"{cwd}/kits/settings.json"}},
        role="architect", kits=kits) is not None
    for cmd in (f"mkdir -p {cwd}/kits/x", f"cp {cwd}/kits/settings.json {cwd}/kits/y",
                f"mv {cwd}/kits/settings.json {cwd}/kits/y"):
        reason = guard.check(cmd, role="architect", consult_role="builder",
                             clone=str(cwd / "repo"), kits=kits)
        assert reason is not None and "symlink" in reason, (spelling, cmd, reason)
    # reads under it are not what §33 names; the refusal is of the kits rows
    assert guard.check("hands status", role="architect", consult_role="builder",
                       clone=str(cwd / "repo"), kits=kits) is None


def test_the_guards_selftest_carries_the_review_16_symlink_rows() -> None:
    """The guard's own self-test (which doctor runs) plants both shapes in a
    scratch directory and judges them, so a copy of the guard without the rule
    is not green."""
    names = {cmd for _, cmd, _ in guard.SYMLINK_SELFTEST}
    assert any(cmd.startswith("cp") for cmd in names)
    assert any(cmd.startswith("mv") for cmd in names)
    assert any(cmd.startswith("--write") for cmd in names)
    assert any(ok for _, _, ok in guard.SYMLINK_SELFTEST)
    assert any(not ok for _, _, ok in guard.SYMLINK_SELFTEST)
    assert guard.symlink_selftest() == 0
