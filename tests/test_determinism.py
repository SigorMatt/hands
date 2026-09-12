"""The gate is deterministic as a property, not as a sample (DESIGN §21).

Review 4 should-fix 1 and 2. A test that compares a literal against text
carrying a path the *environment* chose — pytest's `--basetemp`, the per-test
`tmp_path`, `~/.hands/handsd.sock`, the ops repo — is only as reliable as that
path. Two live instances were driven red with a crafted `--basetemp`
(`assert "--pids" not in out` under `/tmp/ptY/z--pids`, and
`assert expected not in refusal` under `/tmp/ptX/a send needs a prompt`), and
the false-green half of the same fault (`assert "200" in out`, satisfied by a
digit in the path) cannot go red at all, so no run will ever report it.

The answer is one helper, `conftest.strip_paths`, and the two audits below,
which keep every assertion in `tests/` using it.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from conftest import strip_paths

TESTS = Path(__file__).parent

# Files whose assertions read artifacts checked into the repository — the
# driver kit, the systemd unit, the docs, the guard's own case table, the §21
# hook and its settings. No path a run creates can reach that text, so there is
# nothing to strip: `test_no_background.py`'s subprocess output is the hook's
# refusal of a command the test itself spelled, not of anything an environment
# chose.
READS_THE_REPO = frozenset({"test_docs.py", "test_bash_guard.py", "test_no_background.py"})

# This file's own subject is the helper, so its assertions read text that has
# already been through it.
NOT_AUDITED = READS_THE_REPO | {"test_determinism.py"}

# Not text: sequences of exact tokens, where `in` is an equality test on an
# element and a path cannot be a member of anything.
NOT_TEXT = {
    "kinds": "a list of event kinds",
    "argv": "a command line, as a list of arguments",
    "harness.kinds()": "a list of event kinds",
    "runner.last_argv[job.id]": "a command line, as a list of arguments",
    "blocks(monitor_events(spool))": "a list of monitor block reasons",
    "status": "the `hands status` record, a dict: `in` tests for a key",
}


def _asserted_comparisons(path: Path) -> list[tuple[int, ast.Compare]]:
    """Every `in` / `not in` comparison inside an `assert` in one test file."""
    found: list[tuple[int, ast.Compare]] = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if not isinstance(node, ast.Assert):
            continue
        for inner in ast.walk(node.test):
            if isinstance(inner, ast.Compare) and len(inner.ops) == 1:
                if isinstance(inner.ops[0], (ast.In, ast.NotIn)):
                    found.append((inner.lineno, inner))
    return found


def _audited() -> list[Path]:
    files = [p for p in sorted(TESTS.glob("*.py")) if p.name not in NOT_AUDITED]
    assert len(files) > 10, "the audit stopped finding test files"
    return files


def _is_stripped(node: ast.expr) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "strip_paths"
    )


def _exempt(node: ast.expr) -> bool:
    """A comparison against a literal collection is an equality test, not a search."""
    if isinstance(node, (ast.Tuple, ast.List, ast.Set, ast.Dict, ast.ListComp, ast.SetComp)):
        return True
    return ast.unparse(node) in NOT_TEXT


def test_every_negative_assertion_compares_against_stripped_text() -> None:
    """`assert X not in <text>` is the half of the fault that goes red."""
    offenders = []
    for path in _audited():
        for lineno, node in _asserted_comparisons(path):
            if not isinstance(node.ops[0], ast.NotIn):
                continue
            target = node.comparators[0]
            if _is_stripped(target) or _exempt(target):
                continue
            offenders.append(f"{path.name}:{lineno}: `not in {ast.unparse(target)}`")
    assert not offenders, "negative assertions that a crafted path can make red:\n" + "\n".join(
        offenders
    )


def test_every_literal_expectation_compares_against_stripped_text() -> None:
    """`assert "200" in <text>` is the half that goes green and stays green.

    The rule covers a literal and a loop variable holding one. A comparison
    whose left side is a call or a subscript is left alone: those are the
    assertions that a path *is* in the output (`assert str(script) in out`),
    which are the reason the helper strips prefixes instead of whole lines.
    """
    offenders = []
    for path in _audited():
        for lineno, node in _asserted_comparisons(path):
            literal = isinstance(node.left, ast.Constant) and isinstance(node.left.value, str)
            if not (literal or isinstance(node.left, ast.Name)):
                continue
            target = node.comparators[0]
            if _is_stripped(target) or _exempt(target):
                continue
            offenders.append(
                f"{path.name}:{lineno}: `{ast.unparse(node.left)} in {ast.unparse(target)}`"
            )
    assert not offenders, "expectations a path can satisfy vacuously:\n" + "\n".join(offenders)


def test_strip_paths_removes_every_path_the_run_injects(
    tmp_home: Path, tmp_path: Path, tmp_path_factory: pytest.TempPathFactory
) -> None:
    """The four the environment chooses: basetemp, tmp_path, the socket, the ops repo."""
    basetemp = tmp_path_factory.getbasetemp()
    socket = tmp_home / ".hands" / "handsd.sock"
    ops = tmp_path / "ops"
    text = (
        f"daemon on {socket}\n"
        f"base {basetemp}\n"
        f"builder idle; queued 0/1  {tmp_path / 'work'}\n"
        f"the script decides: {ops / 'watch_monitor.sh'}\n"
    )
    stripped = strip_paths(text, ops)
    for injected in (str(socket), str(basetemp), str(tmp_path), str(ops)):
        assert injected not in stripped, f"{injected} survived the strip"
    # Only the prefix goes: what the product printed is still there to assert on.
    assert "daemon on" in stripped
    assert "queued 0/1" in stripped
    assert "watch_monitor.sh" in stripped


def test_strip_paths_removes_the_home_and_the_working_directory(tmp_home: Path) -> None:
    """`tmp_home` moves both, so both are the environment's choice, not the product's."""
    stripped = strip_paths(f"config {tmp_home}/.hands/demo.toml ran in {Path.cwd()}")
    assert str(tmp_home) not in stripped
    assert str(Path.cwd()) not in stripped
    assert "demo.toml" in stripped


def test_strip_paths_never_strips_a_root_directory() -> None:
    """`/` or `/home` as a prefix would delete the text instead of the path."""
    assert strip_paths("a / b and /home too") == "a / b and /home too"
