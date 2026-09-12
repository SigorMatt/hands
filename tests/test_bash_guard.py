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
# forbidden, and from §21's git option policy: only `-C <path>` and
# `--no-pager` before the subcommand, and no `--output`/`--ext-diff`/
# `--textconv`/`-O`/`--open-files-in-pager`/`--config-env` after it. The allowed
# cases are just as load-bearing: the driver's whole job is read-only git and
# reads of the human's `~/git` workspace, and a guard that refuses those is
# useless in a real session.
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
    ("git status --porcelain", True),
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
    # the refusals are by exact option, not by prefix: these read
    ("git -C ./repo diff --no-ext-diff HEAD", True),
    ("git -C ./repo diff --output-indicator-new=X HEAD", True),
    ("git -C ./repo log --no-textconv -1", True),
    # a `find` printing to stdout is still a read
    ("find . -name '*.md' -print", True),
    ("find ~/git/hands -type f -printf %p", True),
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


def test_the_adversarial_table_is_independent_of_the_guard() -> None:
    # It is the tests' own table: it must not shrink to the guard's, and it
    # must carry both verdicts.
    assert len(ADVERSARIAL) >= 20
    assert sum(1 for _, allowed in ADVERSARIAL if allowed) >= 10
    assert sum(1 for _, allowed in ADVERSARIAL if not allowed) >= 10
