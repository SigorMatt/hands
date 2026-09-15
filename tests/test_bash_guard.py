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
# refused; the read-only inspection words of the human driver's guard (`cat`,
# `ls`, `grep`, ...) are not on §27's list, so they are refused — the role
# reads the clone with `git show`/`git grep`/`git cat-file`.
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
    ("hands kit check ~/Downloads/kit.zip --repo ./repo", True),
    ("hands resume", True),
    # send: only an explicit keep, only to builder or aux
    ("hands send --role builder --context keep 'Answer: use §27, then continue.'", True),
    ("hands send --role builder --context keep --prompt-file ~/Downloads/answer.txt", True),
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
    ("cat ./repo/DESIGN.md", False),
    ("ls ./repo", False),
    ("git -C ./repo log --oneline -5 | head -1", False),
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
    ("hands send --role builder --context keep \\--context=clear m", False),
    ("hands send --role builder --context keep $'--context=clear' m", True),
    ("hands send --role builder --context keep {--context=clear,m}", True),
    ("x=--context=clear; hands send --role builder --context keep $x m", True),
    ("hands send --role builder --context keep '--file' a=b m", False),
    ("hands send --role builder --context keep \\--file a=b m", False),
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
    ("git status\ngit push", False),
    ("(git status) && (git push)", False),
    ("git status; (git push)", False),
    ("echo $(git push)", False),
    ("echo `git push`", False),
    ('echo "$(git status; git push)"', False),
    ('echo "`git push`"', False),
    ("echo $(echo $(git push))", False),
    # the backslash-newline the shell deletes before it splits words
    ("git status \\\n; git push", False),
    ("git log --oneline -1 \\\n--output=/tmp/x", False),
    # an escaped or quoted separator is text, not a separator
    ("git -C ./repo grep -n 'a;b' origin/main", True),
    ("git -C ./repo grep -n a\\&b origin/main", True),
    # unparsable: unbalanced quotes, an unterminated substitution
    ("git log 'oops", False),
    ('git log "oops', False),
    ("git log --oneline -1 \\", False),
    ("echo $(git status", False),
    ("echo `git status", False),
    # leading assignments, with a command and alone
    ("GIT_PAGER=touch git log", False),
    ("x=1 git status", False),
    ("x=1; git status", False),
    ("x=1", False),
    # `$'…'` words, anywhere a word can be
    ("git log $'--output=/tmp/x'", False),
    ("git log --grep=$'a'", False),
    # residual expansion characters in git argument position
    ("git log $x", False),
    ("git log ${x}", False),
    ('git log "$x"', False),
    ("git log `echo -1`", False),
    ("git log --grep=a{b,c}", False),
    ("git log -- *.py", False),
    ("git log -- x?", False),
    ("git log -- [ab]", False),
    ("git log HEAD^!", False),
    ('git log "--grep=\\x"', False),
    ("git log --grep=x=~/y", False),
    # ... and the same characters where the shell does not expand them
    ("git log -- '*.py'", True),
    ("git -C ./repo grep -n -e '$x' origin/main", True),
    ('git -C ./repo grep -n -e "a*b?[c]{d,e}~" origin/main', True),
    ("git -C ./repo diff --stat HEAD~1", True),
    ("git -C ./repo rev-parse HEAD^{commit}", True),
    ("git -C ./repo rev-parse HEAD^{}", True),
    # the command word itself is what the shell delivers
    ("'git' push", False),
    ("g\\it push", False),
    ("$SHELL -c 'git push'", False),
    ("$GIT push", False),
    # writes by redirection that the old pattern let through
    ("git status 2>probe.txt", False),
    ("git status &> probe.txt", False),
    ("git status &>probe.txt", False),
    ("echo hi 2>probe.txt", False),
    ("git status 2>/dev/null", True),
    ("git status 2>&1", True),
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
    ("hands show 'x{a,b}'", True),
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
    ("hands send --role builder --context clear 'Did it pass? Run *all* [the] {checks}!'", True),
    ('hands send --role builder --context clear "Did it pass? Run *all* [the] {checks}"', True),
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
    ("hands send --role aux --context keep --prompt-file ~/Downloads/answer.txt", "aux", True),
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


# --- §29: THE GUARD (review 12 blocker 1, should-fix 2; H-024) ---------------
#
# A `#` outside quotes anywhere is refused in both modes, naming its offset:
# a comment is where an unbalanced quote hides a second command from a
# tokenizer. "Outside quotes" is bash's quoting (not in single quotes, not in
# double quotes, not after a backslash), judged in every context the shell
# parses, so inside `$(…)` and backticks too. A `#` inside a word (`a#b`) is
# not a bash comment, but §29 says "anywhere", so it is refused as well.
REVIEW_12_PROBES: list[str] = [
    "hands show x # it's\nhands go #'",
    "hands show x # it's\nhands send --role builder --context clear m #'",
    "ls # it's\ntouch /tmp/rev12-pwned #'",
]


def _both_modes(cmd: str, clone: str | None = CLONE) -> list[tuple[str | None, str | None]]:
    return [(role, guard.check(cmd, role=role, consult_role="builder", clone=clone))
            for role in (None, "driver")]


@pytest.mark.parametrize("cmd", REVIEW_12_PROBES)
def test_review_12_probe_is_blocked_in_both_modes_naming_the_comment(cmd: str) -> None:
    for role, reason in _both_modes(cmd):
        assert reason is not None, f"a review 12 probe was allowed ({role}): {cmd!r}"
        assert f"offset {cmd.index('#')}" in reason, (role, cmd, reason)


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


# (command, allowed) in both modes.
COMMENTS: list[tuple[str, bool]] = [
    ("hands status # a note", False),
    ("git -C ./repo log --oneline -1 # a note", False),
    ("hands show a#b", False),
    ("hands show x #", False),
    ("# only a comment", False),
    ("hands show x\n# it's", False),
    ('hands show "x" #"', False),
    ("hands show x $#", False),
    ('hands show "$(hands status # it\'s)"', False),
    ("hands show `hands status #`", False),
    ("hands show x ; # y", False),
    # quoted or escaped, a `#` is text
    ("hands send --role builder --context keep 'fix #12'", True),
    ('hands send --role builder --context keep "fix #12"', True),
    ("hands show x\\#y", True),
    ("git -C ./repo log --grep='#12'", True),
]


@pytest.mark.parametrize("cmd,allowed", COMMENTS)
def test_a_hash_outside_quotes_is_refused_in_both_modes(cmd: str, allowed: bool) -> None:
    for role, reason in _both_modes(cmd):
        assert (reason is None) == allowed, (role, cmd, reason)
        if not allowed:
            assert "#" in reason and "offset" in reason, (role, cmd, reason)


@pytest.mark.parametrize(
    "cmd,offset",
    [
        ("hands status # a note", 13),
        ("hands show x\n# it's", 13),
        ("hands show 'a#b' c#d", 18),
        ('hands show "$(hands status # x)"', 27),
        # inside backticks `\$` loses its backslash first; the offset is still the
        # command's own
        ("hands show `hands \\$x #`", 22),
    ],
)
def test_the_refusal_names_the_offset_of_the_first_unquoted_hash(cmd: str, offset: int) -> None:
    assert cmd[offset] == "#"
    for role, reason in _both_modes(cmd):
        assert reason is not None and f"offset {offset}" in reason, (role, cmd, reason)


# H-024 as §29 states it, one clause at a time, for `git` and `hands` argument
# words in both modes: (clause, command, allowed).
H024_CLAUSES: list[tuple[str, str, bool]] = [
    ("single quotes", "git -C ./repo log --grep='$x*?[a]{b,c}!~'", True),
    ("single quotes", "git -C ./repo log --grep='a'$x", False),
    ("backslash", "git -C ./repo log --grep=\\$x\\*\\?\\[a\\]\\{b,c\\}\\!", True),
    ("backslash", "git -C ./repo log --grep=\\\\$x", False),
    ("double quotes", 'git -C ./repo log --grep="a*b?[c]{d,e}~"', True),
    ("double quotes", 'git -C ./repo log --grep="$x"', False),
    ("double quotes", 'git -C ./repo log --grep="a`true`"', False),
    ("double quotes", 'git -C ./repo log --grep="a\\"b"', False),
    ("double quotes", 'git -C ./repo log --grep="a\\x"', False),
    ("double quotes", 'git -C ./repo log --grep="a!b"', False),
    ("braces", "git -C ./repo log HEAD@{1}", True),
    ("braces", "git -C ./repo rev-parse HEAD^{commit}", True),
    ("braces", "hands show x{1}", True),
    ("braces", "hands show x{a}y}", True),
    ('braces', 'hands show x{"a,b"}', True),
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
    for clause in {c for c, _, _ in H024_CLAUSES}:
        verdicts = {ok for c, _, ok in H024_CLAUSES if c == clause}
        assert verdicts == {True, False}, clause


def test_h024_a_character_after_a_backslash_does_not_count_inside_double_quotes() -> None:
    """Inside double quotes the backslash itself counts (§29 lists it); the `$` it
    escapes does not."""
    reason = guard.check('git log --grep="\\$x"')
    assert reason is not None and "carries \\ the shell" in reason, reason


# §29: role mode pins `git -C` to the role's clone (HANDS_CLONE). Both sides are
# compared as `os.path.abspath` (normpath joined to the hook's working
# directory); no tilde is expanded, so a `-C ~/…` equals only a HANDS_CLONE
# spelled the same. (command, HANDS_CLONE, allowed in role mode)
ABS_CLONE = "/home/u/hands-driver/hands/repo"
CLONE_PIN: list[tuple[str, str | None, bool]] = [
    ("git -C /tmp log", ABS_CLONE, False),
    (f"git -C {ABS_CLONE} log --oneline -1", ABS_CLONE, True),
    (f"git -C {ABS_CLONE}/ log", ABS_CLONE, True),
    (f"git -C {ABS_CLONE}/../repo log", ABS_CLONE, True),
    (f"git -C {ABS_CLONE}/.. log", ABS_CLONE, False),
    (f"git -C {ABS_CLONE} -C /tmp log", ABS_CLONE, False),
    (f"git -C /tmp -C {ABS_CLONE} log", ABS_CLONE, False),
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
