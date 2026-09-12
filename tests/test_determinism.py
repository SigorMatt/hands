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
which keep every assertion in `tests/` using it. What an audit exempts, it
exempts for what the expression *is* — a list, a dict, a string constant however
it is built — not for the way it is spelled; the third test drives the shapes
that slipped through when the judgement was by source text (review 5
should-fix 6).
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
# element and a path cannot be a member of anything. A claim about the value,
# so `_exempt` withdraws it from any name the file assigns text to.
NOT_TEXT = {
    "kinds": "a list of event kinds",
    "argv": "a command line, as a list of arguments",
    "harness.kinds()": "a list of event kinds",
    "runner.last_argv[job.id]": "a command line, as a list of arguments",
    "blocks(monitor_events(spool))": "a list of monitor block reasons",
    "status": "the `hands status` record, a dict: `in` tests for a key",
    "scan.sections": "the section names config.py admits, a set",
}


def _asserted_comparisons(tree: ast.AST) -> list[tuple[int, ast.Compare]]:
    """Every `in` / `not in` comparison inside an `assert` in one test file."""
    found: list[tuple[int, ast.Compare]] = []
    for node in ast.walk(tree):
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


def _is_text(node: ast.expr) -> bool:
    """Is this expression a string constant, however it is spelled?

    Review 5 should-fix 6: the positive audit only knew a written literal and a
    bare name, so `assert f"wo{'r'}ld" in out` and `assert ("wo" + "rld") in
    out` were invisible to it — the same expectation, built rather than written.

    An f-string or a sum that interpolates a *value* is not one of these: it is
    the `assert str(script) in out` shape, an assertion that a path the run chose
    reached the output, and stripping the text it is compared against would be
    what breaks it. So every piece has to be constant for the whole to count.
    """
    if isinstance(node, ast.Constant):
        return isinstance(node.value, str)
    if isinstance(node, ast.JoinedStr):  # an f-string, in pieces or whole
        return all(
            _is_text(part.value) if isinstance(part, ast.FormattedValue) else _is_text(part)
            for part in node.values
        )
    if isinstance(node, ast.BinOp):  # "wo" + "rld"
        return _is_text(node.left) and _is_text(node.right)
    return False


def _names_holding_text(tree: ast.AST) -> set[str]:
    """Every name this file ever assigns text to (review 5 should-fix 6).

    `NOT_TEXT` exempts a name because of what it *holds* — a list of event kinds,
    an argv, a record — so the exemption is withdrawn the moment the file assigns
    text to that name. `status = "…"; assert "world" not in status` passed both
    audits while `status` was in `NOT_TEXT` on the strength of its spelling.
    """
    named: set[str] = set()
    for node in ast.walk(tree):
        targets: list[ast.expr] = []
        value: ast.expr | None = None
        if isinstance(node, ast.Assign):
            targets, value = list(node.targets), node.value
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign, ast.NamedExpr)):
            targets, value = [node.target], node.value
        elif isinstance(node, (ast.For, ast.AsyncFor)) and isinstance(
            node.iter, (ast.Tuple, ast.List, ast.Set)
        ):
            # `for status in ("a", "b"):` binds the elements, not the sequence.
            targets = [node.target]
            value = next((item for item in node.iter.elts if _is_text(item)), None)
        if value is None or not _is_text(value):
            continue
        named |= {target.id for target in targets if isinstance(target, ast.Name)}
    return named


def _exempt(node: ast.expr, text_names: frozenset[str]) -> bool:
    """A comparison against a literal collection is an equality test, not a search.

    Or against one of `NOT_TEXT`'s values — unless this file assigns text to that
    name, in which case the claim `NOT_TEXT` makes about it is not true here.
    """
    if isinstance(node, (ast.Tuple, ast.List, ast.Set, ast.Dict, ast.ListComp, ast.SetComp)):
        return True
    if ast.unparse(node) not in NOT_TEXT:
        return False
    return not (isinstance(node, ast.Name) and node.id in text_names)


def _negative_offenders(source: str, where: str) -> list[str]:
    """`assert X not in <text>` against text no one stripped, in one file."""
    tree = ast.parse(source)
    text_names = frozenset(_names_holding_text(tree))
    offenders = []
    for lineno, node in _asserted_comparisons(tree):
        if not isinstance(node.ops[0], ast.NotIn):
            continue
        target = node.comparators[0]
        if _is_stripped(target) or _exempt(target, text_names):
            continue
        offenders.append(f"{where}:{lineno}: `not in {ast.unparse(target)}`")
    return offenders


def _positive_offenders(source: str, where: str) -> list[str]:
    """`assert "200" in <text>` against text no one stripped, in one file."""
    tree = ast.parse(source)
    text_names = frozenset(_names_holding_text(tree))
    offenders = []
    for lineno, node in _asserted_comparisons(tree):
        if not (_is_text(node.left) or isinstance(node.left, ast.Name)):
            continue
        target = node.comparators[0]
        if _is_stripped(target) or _exempt(target, text_names):
            continue
        offenders.append(f"{where}:{lineno}: `{ast.unparse(node.left)} in {ast.unparse(target)}`")
    return offenders


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_every_negative_assertion_compares_against_stripped_text() -> None:
    """`assert X not in <text>` is the half of the fault that goes red."""
    offenders = [
        offender
        for path in _audited()
        for offender in _negative_offenders(_source(path), path.name)
    ]
    assert not offenders, "negative assertions that a crafted path can make red:\n" + "\n".join(
        offenders
    )


def test_every_literal_expectation_compares_against_stripped_text() -> None:
    """`assert "200" in <text>` is the half that goes green and stays green.

    The rule covers a literal however it is built — written, f-string or
    concatenation — and a loop variable holding one. A comparison whose left side
    is a call or a subscript is left alone: those are the assertions that a path
    *is* in the output (`assert str(script) in out`), which are the reason the
    helper strips prefixes instead of whole lines.
    """
    offenders = [
        offender
        for path in _audited()
        for offender in _positive_offenders(_source(path), path.name)
    ]
    assert not offenders, "expectations a path can satisfy vacuously:\n" + "\n".join(offenders)


#: The shapes review 5 should-fix 6 drove past both audits, and the shapes that
#: must stay exempt beside them: `caught` is whether an audit must name the line.
CRAFTED = [
    pytest.param('status = "a note"\nassert "world" not in status\n', True, id="text_named_status"),
    pytest.param("assert f\"wo{'r'}ld\" in out\n", True, id="an_f_string_expectation"),
    pytest.param('assert ("wo" + "rld") in out\n', True, id="a_concatenated_expectation"),
    pytest.param('kinds = [e["type"] for e in events]\nassert "wake" not in kinds\n', False,
                 id="a_name_holding_a_list"),
    pytest.param('assert "wake" in strip_paths(out)\n', False, id="stripped_text"),
    pytest.param('assert f"wake {n}" in strip_paths(out)\n', False, id="a_stripped_f_string"),
]


@pytest.mark.parametrize("source,caught", CRAFTED)
def test_the_audits_judge_the_value_a_name_holds_not_the_way_it_is_spelled(
    source: str, caught: bool
) -> None:
    """§21 (review 5 should-fix 6): both holes the reviewer drove, closed.

    `NOT_TEXT` matched the *spelling*, so `status = "…"; assert "world" not in
    status` passed both audits (likewise `kinds`, `argv`) — the exemption is a
    claim about the value, and this file assigns it text. And the positive audit
    only fired on a written literal or a bare name, so an f-string and a
    concatenation were invisible. Neither shape is in `tests/` today, which is
    why they are spelled here rather than found there.
    """
    offenders = _negative_offenders(source, "crafted.py") + _positive_offenders(
        source, "crafted.py"
    )
    assert bool(offenders) == caught, f"audits said {offenders} for:\n{source}"


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
    """`/`, `/home` or `/tmp` as a prefix would delete the text instead of the path.

    `/tmp` is the one that is really at risk: it is `--basetemp`'s parent, so it
    is the shortest form the loop can ever be handed.
    """
    assert strip_paths("a / b and /home too, /tmp as well") == "a / b and /home too, /tmp as well"
