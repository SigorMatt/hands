"""U7: the no-background PreToolUse hook of this repository (§2, §21).

DESIGN §21: "Role sessions never use background tasks (§2, §21): the harness
reaps them, so a builder sub-agent's long background job could die silently
mid-mission. A `PreToolUse` hook in every driven repository refuses
`run_in_background` and hand-rolled daemonization; foreground Bash with a
timeout is the only way to run something long."

`.claude/hooks/no_background.py` is a hook, not an installed module: Claude Code
runs it as a subprocess with the hook JSON on stdin. So it is exercised twice
here — as a module loaded by path (its `check()` and its own `SELFTEST` table,
one case per test) and as a real subprocess whose stdin is hook JSON and whose
exit code is what blocks a tool call. The subprocess half is the part
`tests/test_bash_guard.py` never had for `driver/hooks/bash_guard.py`.

`ADVERSARIAL` is a second table, owned by `tests/` and written from §21 rather
than from the hook's own table, so that it can disagree with the hook.
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).parents[1]
HOOK = ROOT / ".claude" / "hooks" / "no_background.py"
SETTINGS = ROOT / ".claude" / "settings.json"
CHECK = ROOT / "scripts" / "check"


def _load_hook() -> ModuleType:
    spec = importlib.util.spec_from_file_location("no_background", HOOK)
    assert spec and spec.loader, f"cannot load the hook from {HOOK}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


hook = _load_hook()


def run_hook(payload: object, *args: str) -> subprocess.CompletedProcess[str]:
    """Run the hook the way Claude Code does: a subprocess fed hook JSON."""
    text = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.run(
        [sys.executable, str(HOOK), *args],
        input=text,
        capture_output=True,
        text=True,
        timeout=60,
    )


def bash_event(command: str, **tool_input: object) -> dict[str, object]:
    return {
        "session_id": "s1",
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": command, **tool_input},
    }


# ------------------------------------------------------------ the two files


def tracked() -> set[str]:
    out = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout
    return {name for name in out.split("\0") if name}


def test_both_files_are_installed_in_this_repository_and_tracked() -> None:
    """§21: the hook holds only if it is in the repository the role works in."""
    assert HOOK.is_file(), "this repository is driven by hands: it needs the §21 hook"
    assert SETTINGS.is_file()
    names = tracked()
    assert ".claude/hooks/no_background.py" in names, "the hook must be committed"
    assert ".claude/settings.json" in names, "the settings must be committed"


def test_the_settings_run_the_hook_before_every_bash_call() -> None:
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
    entries = settings["hooks"]["PreToolUse"]
    matching = [e for e in entries if e.get("matcher") == "Bash"]
    assert matching, "settings.json has no PreToolUse hook matching Bash"
    commands = [h["command"] for e in matching for h in e["hooks"] if h["type"] == "command"]
    assert any("no_background.py" in c for c in commands), commands
    for command in commands:
        if "no_background.py" in command:
            assert ".claude/hooks/no_background.py" in command
            assert "python3" in command


# ------------------------------------------------------- the hook's own table


def test_the_hooks_case_table_is_not_empty() -> None:
    assert len(hook.SELFTEST) >= 30
    assert any(allowed for _, allowed in hook.SELFTEST)
    assert any(not allowed for _, allowed in hook.SELFTEST)


@pytest.mark.parametrize("cmd,allowed", hook.SELFTEST)
def test_selftest_case(cmd: str, allowed: bool) -> None:
    reason = hook.check(cmd)
    if allowed:
        assert reason is None, f"the hook blocked a foreground command: {cmd!r} -> {reason}"
    else:
        assert reason is not None, f"the hook allowed a background command: {cmd!r}"


def test_the_files_own_selftest_reports_zero() -> None:
    assert hook.selftest() == 0


def test_the_selftest_flag_runs_the_table_in_a_subprocess() -> None:
    done = run_hook("", "--selftest")
    assert done.returncode == 0, done.stdout + done.stderr
    assert "selftest:" in done.stdout


# --- ADVERSARIAL ------------------------------------------------------------
#
# The tests' own expectations, composed from §21 ("refuses `run_in_background`
# and hand-rolled daemonization") and from the unit's case list, written without
# reading the hook's `SELFTEST`. The allowed half is as load-bearing as the
# blocked half: a hook that refuses `&&`, `2>&1` or an `&` in a URL would stop a
# role session from running the gate at all.
ADVERSARIAL: list[tuple[str, bool]] = [
    # --- a trailing `&` is a background job -------------------------------
    ("sleep 100 &", False),
    ("sleep 100&", False),
    ("uv run pytest &", False),
    ("./scripts/check > /tmp/out 2>&1 &", False),
    ("uv run handsd --project hands &", False),
    ("sleep 5 & echo started", False),
    ("ls; uv run pytest &", False),
    ("uv run pytest > /tmp/log &\necho started", False),
    # --- `&` before `)`: a backgrounded subshell ---------------------------
    ("( sleep 300 & )", False),
    ("(./scripts/check &)", False),
    ("(cd /tmp && ./run.sh &)", False),
    ("{ sleep 300 & }", False),
    # --- the daemonizing words --------------------------------------------
    ("nohup ./scripts/check", False),
    ("nohup uv run pytest > /tmp/out 2>&1 &", False),
    ("setsid ./scripts/check", False),
    ("setsid --fork uv run handsd", False),
    ("./run.sh & disown", False),
    ("disown -a", False),
    ("nohup python3 -m http.server 8000", False),
    # --- backgrounding inside a substitution still runs --------------------
    ('echo "$(sleep 100 &)"', False),
    ("echo `sleep 100 &`", False),
    # --- FALSE POSITIVES: these are foreground and must be ALLOWED ---------
    ("./scripts/check", True),
    ("uv run pytest && uv run ruff check .", True),
    ("uv run pytest tests/test_no_background.py -q", True),
    ("timeout 600 ./scripts/check", True),
    ("uv run pytest 2>&1 | tail -20", True),
    ("ls > /tmp/out 2>&1", True),
    ("uv run hands --help >/dev/null", True),
    ("echo done 1>&2", True),
    ("ls &> /tmp/out", True),
    ("git log --oneline -5 | head -3", True),
    ("git commit -m 'runner: the log & the spool'", True),
    ('grep -rn "nohup" src tests', True),
    ("echo 'run it in the background with &'", True),
    ('echo "a && b"', True),
    ("curl -s 'https://example.com/?a=1&b=2'", True),
    ("curl -s https://example.com/?a=1&b=2", True),
    ("for f in src/hands/*.py; do echo $f; done", True),
    ("test -f DESIGN.md && echo yes", True),
    ("cat docs/nohup-notes.md", True),
    ("python3 .claude/hooks/no_background.py --selftest", True),
    ("wait", True),
    ("jobs", True),
    # --- a comment hides nothing (review 5 should-fix 2) -------------------
    ("sleep 30 &# note", False),
    ("uv run pytest &  # start the gate", False),
    ("./scripts/check &# run it", False),
    # --- a daemonizer keeps its meaning when it is spelled as a path -------
    ("/usr/bin/nohup ./long.sh", False),
    ("/usr/bin/setsid --fork uv run handsd", False),
    ("env X=1 /bin/nohup ./run.sh", False),
    # --- FALSE POSITIVES: comment text is text, and so is a path that only
    #     ends in one of the words -----------------------------------------
    ("ls # a & b", True),
    ("uv run pytest -q  # then nohup ./x & disown", True),
    ("# a note about & and setsid", True),
    ("make -j2 # &", True),
    ("echo ${#PATH} && ls", True),
    ("curl -s http://example.com/page#frag", True),
    ("cat docs/nohup-notes.md", True),
    ("./scripts/disown-notes.sh", True),
]


@pytest.mark.parametrize("cmd,allowed", ADVERSARIAL)
def test_adversarial_case(cmd: str, allowed: bool) -> None:
    """§21: `run_in_background` and hand-rolled daemonization are refused, and
    nothing else is — checked against expectations `tests/` owns."""
    reason = hook.check(cmd)
    if allowed:
        assert reason is None, f"the hook blocked a foreground command: {cmd!r} -> {reason}"
    else:
        assert reason is not None, f"the hook allowed a background command: {cmd!r}"


def test_the_adversarial_table_is_independent_of_the_hook() -> None:
    assert len(ADVERSARIAL) >= 20
    assert sum(1 for _, allowed in ADVERSARIAL if allowed) >= 10
    assert sum(1 for _, allowed in ADVERSARIAL if not allowed) >= 10


def test_a_heredoc_body_is_text_not_a_command() -> None:
    """Writing a file whose text mentions a background job is not a background
    job: the body of a heredoc never reaches the shell as a command."""
    assert hook.check("cat > /tmp/x <<'EOF'\nrun it with &\nnohup ./x\nEOF") is None
    # ... but the command carrying the heredoc is still read.
    assert hook.check("cat > /tmp/x <<'EOF' &\nbody\nEOF") is not None


def test_unbalanced_quotes_fail_closed() -> None:
    assert hook.check('echo "unterminated') is not None


# --------------------------------------------------- the run_in_background flag


def test_the_flag_is_refused_whatever_the_command_is() -> None:
    """§21's first half: the Bash tool's own background mode."""
    assert hook.check("ls", run_in_background=True) is not None
    assert hook.check("ls", run_in_background=False) is None
    assert hook.check("ls") is None


def test_the_flag_is_read_in_every_spelling_json_may_carry() -> None:
    for value in (True, "true", "True", 1):
        assert hook.check("ls", run_in_background=value) is not None, value
    for value in (False, "false", "", None, 0):
        assert hook.check("ls", run_in_background=value) is None, value


# ------------------------------------------------------- main(), as a subprocess


def test_main_blocks_the_background_flag_with_exit_2() -> None:
    done = run_hook(bash_event("uv run pytest", run_in_background=True))
    assert done.returncode == 2, done
    assert "run_in_background" in done.stderr
    assert "foreground" in done.stderr and "timeout" in done.stderr


def test_main_blocks_hand_rolled_daemonization_with_exit_2() -> None:
    for command in ("uv run pytest &", "nohup ./scripts/check", "(sleep 300 &)"):
        done = run_hook(bash_event(command))
        assert done.returncode == 2, (command, done)
        assert "foreground" in done.stderr and "timeout" in done.stderr


def test_main_allows_a_foreground_command_silently() -> None:
    done = run_hook(bash_event("timeout 900 ./scripts/check"))
    assert done.returncode == 0, done
    assert done.stderr == ""


def test_main_ignores_tools_other_than_bash() -> None:
    done = run_hook(
        {"tool_name": "Read", "tool_input": {"file_path": "/tmp/x &", "run_in_background": True}}
    )
    assert done.returncode == 0, done


def test_main_fails_closed_on_input_it_cannot_parse() -> None:
    done = run_hook("{not json")
    assert done.returncode == 2, done
    assert done.stderr.strip()


def test_main_treats_a_missing_command_as_nothing_to_block() -> None:
    done = run_hook({"tool_name": "Bash", "tool_input": {}})
    assert done.returncode == 0, done


# ------------------------------------------------------------- the gate itself


def test_the_gate_survives_its_own_hook() -> None:
    """The unit's gate: `./scripts/check` is foreground, so the hook must let
    every line of it — and the way a session invokes it — through."""
    for n, line in enumerate(CHECK.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        assert hook.check(stripped) is None, f"scripts/check:{n} would be blocked: {stripped}"
    assert hook.check("./scripts/check") is None
    assert hook.check("timeout 1800 ./scripts/check") is None


def test_claude_md_states_the_rule() -> None:
    """The unit: CLAUDE.md states the rule, so a session that never reads
    settings.json still knows it before the hook has to say no."""
    text = ROOT.joinpath("CLAUDE.md").read_text(encoding="utf-8")
    bullets = [b for b in re.split(r"\n(?=- )", text) if "background" in b]
    assert len(bullets) == 1, "CLAUDE.md must state the no-background rule once"
    rule = re.sub(r"\s+", " ", bullets[0])
    for word in ("run_in_background", "nohup", "foreground", "timeout"):
        assert word in rule, f"the CLAUDE.md rule does not name {word!r}: {rule}"


# ------------------------------- the three bypasses of review 5 should-fix 2


def test_a_comment_does_not_hide_a_trailing_ampersand() -> None:
    """`sleep 30 &# note` is a background job: `&` ends the command and `#`,
    starting a word, opens a comment. It was allowed (review 5 should-fix 2)."""
    for cmd in ("sleep 30 &# note", "sleep 30 & # note", "./scripts/check &# run it"):
        assert hook.check(cmd) is not None, f"the hook allowed a background command: {cmd!r}"


def test_a_comment_is_text_and_is_not_read_as_shell() -> None:
    """The other half of the same fix: nothing after an opening `#` runs, so a
    comment that talks about `&`, `nohup` or `setsid` must not block the call."""
    for cmd in (
        "ls # a & b",
        "uv run pytest # then nohup ./x & disown",
        "echo hi; # setsid & disown",
        "make -j2 # &",
        "# a whole line of note about & and nohup",
        "uv run pytest\nls # a & b",
    ):
        assert hook.check(cmd) is None, f"the hook blocked a foreground command: {cmd!r}"


def test_a_comment_ends_at_its_own_line() -> None:
    """A comment reaches the end of its line and no further: the next line of a
    multi-line command is still shell."""
    assert hook.check("ls # a note\nuv run pytest") is None
    assert hook.check("ls # a note\nuv run pytest &") is not None


def test_a_hash_that_does_not_start_a_word_is_not_a_comment() -> None:
    """bash opens a comment only at the start of a word, so `${#x}`, a URL
    fragment and `\"a\"#b` are not comments — and an `&` after them still bites."""
    assert hook.check("echo ${#PATH} && ls") is None
    assert hook.check("curl -s http://example.com/page#frag") is None
    assert hook.check('echo "a"#b &') is not None
    assert hook.check("echo a\\#b &") is not None


def test_a_path_qualified_daemonizer_is_the_same_daemonizer() -> None:
    """`/usr/bin/nohup ./long.sh` was allowed because the token match was the
    bare word only (review 5 should-fix 2): the basename carries the meaning."""
    for cmd in (
        "/usr/bin/nohup ./long.sh",
        "/usr/bin/setsid --fork uv run handsd",
        "env X=1 /bin/nohup ./run.sh",
        "../bin/nohup ./run.sh",
        'echo "$(/usr/bin/nohup ./run.sh)"',
    ):
        assert hook.check(cmd) is not None, f"the hook allowed a daemonizer: {cmd!r}"


def test_a_path_that_merely_ends_in_the_word_is_not_the_word() -> None:
    for cmd in (
        "cat docs/nohup-notes.md",
        "ls tools/setsid.md",
        "./scripts/disown-notes.sh",
        "cat /etc/nohup.conf.d/x",
    ):
        assert hook.check(cmd) is None, f"the hook blocked a foreground command: {cmd!r}"


def test_the_basename_rule_costs_a_file_named_exactly_after_a_daemonizer() -> None:
    """Deliberate, and the price of the fix above: the hook cannot tell the
    program from the same path in argument position, so reading the file blocks
    too. The refusal is the safe direction and is stated in the hook."""
    assert hook.check("ls -l /usr/bin/nohup") is not None


def test_the_hooks_own_table_pins_the_two_closed_bypasses() -> None:
    cases = dict(hook.SELFTEST)
    assert cases.get("sleep 30 &# note") is False
    assert cases.get("/usr/bin/nohup ./long.sh") is False
    assert cases.get("ls # a & b") is True
    assert len(hook.SELFTEST) >= 58, "the selftest table did not grow with the fix"


def test_the_selftest_subprocess_reports_every_case_of_the_grown_table() -> None:
    done = run_hook("", "--selftest")
    assert done.returncode == 0, done.stdout + done.stderr
    match = re.search(r"selftest: (\d+)/(\d+) ok", done.stdout)
    assert match, done.stdout
    total = str(len(hook.SELFTEST) + 1)
    assert match.group(1) == total and match.group(2) == total, done.stdout
    assert int(total) >= 59


# ----------------------------------------- the input shape that failed open


#: Hook payloads that no real Bash tool call produces — `tool_input` is always
#: an object and `command` a string — but which the hook used to read straight
#: into an `AttributeError`/`TypeError`: a traceback on stderr and exit 1, which
#: Claude Code treats as non-blocking. Review 5 should-fix 2: the one shape that
#: failed open, against a hook whose stance is exit 2 on input it cannot parse.
UNREADABLE_INPUTS: list[dict[str, object]] = [
    {"tool_name": "Bash", "tool_input": ["uv run pytest &"]},
    {"tool_name": "Bash", "tool_input": "uv run pytest &"},
    {"tool_name": "Bash", "tool_input": 7},
    {"tool_name": "Bash", "tool_input": {"command": 123}},
    {"tool_name": "Bash", "tool_input": {"command": ["uv", "run", "pytest", "&"]}},
    {"tool_name": "Bash", "tool_input": {"command": {"cmd": "nohup ./x"}}},
    {"tool_name": "Bash", "tool_input": {"command": "ls", "run_in_background": ["true"]}},
    {"tool_name": "Bash", "tool_input": {"command": "ls", "run_in_background": {"y": 1}}},
]


@pytest.mark.parametrize("payload", UNREADABLE_INPUTS)
def test_main_fails_closed_on_a_tool_input_it_cannot_read(payload: dict[str, object]) -> None:
    done = run_hook(payload)
    assert done.returncode == 2, (payload, done)
    assert "Traceback" not in done.stderr, done.stderr
    assert done.stderr.strip() and done.stderr.strip().count("\n") == 0, done.stderr


def test_main_still_allows_the_shapes_that_carry_no_command() -> None:
    """The fix must not turn "nothing to block" into a block: an absent or null
    `tool_input` or `command`, and any tool that is not Bash, still exit 0."""
    for payload in (
        {"tool_name": "Bash", "tool_input": None},
        {"tool_name": "Bash", "tool_input": {}},
        {"tool_name": "Bash", "tool_input": {"command": None}},
        {"tool_name": "Bash", "tool_input": {"command": ""}},
        {"tool_name": "Bash"},
        {"tool_name": "Read", "tool_input": {"command": 123}},
        {"tool_name": "Read", "tool_input": ["x"]},
        ["not", "a", "hook", "event"],
        "null",
    ):
        done = run_hook(payload)
        assert done.returncode == 0, (payload, done)
