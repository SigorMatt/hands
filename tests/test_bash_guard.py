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
    ("git -C ./repo rev-parse 8448b6f^{commit}", True),
    ("git log --grep=commit -5", True),
    ("git -C ./repo show origin/main:meta/CHECKPOINT.md", True),
    ("git -C ./repo log --oneline --grep=push -20", True),
    # the human's workspace really is `~/git`: live commands, not hypotheticals
    ("ls ~/git", True),
    ("ls -la ~/git/hands", True),
    ("find ~/git/hands -name '*.py'", True),
    ("cat ~/git/hands/DESIGN.md", True),
    ("git -C ~/git/hands log --oneline -5", True),
    ("ls /home/msi/git", True),
    ("cat ~/git/hands/driver/hooks/bash_guard.py", True),
    ("git -C ~/git/hands show HEAD:DESIGN.md", True),
    # a `find` with no exec flag is fine
    ("find . -name '*.md'", True),
    ("find ~/git -maxdepth 1 -type d", True),
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
    ("git -C ./repo rev-parse abc^{commit}", True),
    ('git -C ./repo grep -n "git diff" origin/main -- docs', True),
    ("git --no-pager log --oneline -5", True),
    ("git --no-pager -C ./repo diff HEAD~1", True),
    # an allowlist refuses by absence: these read, and are refused anyway,
    # because §12 does not list them for `diff` or for `log`
    ("git -C ./repo diff --no-ext-diff HEAD", False),
    ("git -C ./repo diff --output-indicator-new=X HEAD", False),
    ("git -C ./repo log --no-textconv -1", False),
    # a `find` printing to stdout is still a read
    ("find . -name '*.md' -print", True),
    ("find ~/git/hands -type f -printf %p", True),
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
    ("git -C ./repo cat-file -e HEAD^{commit}", True),
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
