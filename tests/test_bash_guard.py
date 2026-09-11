"""The driver kit's Bash guard (§12) under the test suite (§19).

`driver/hooks/bash_guard.py` is a shipped artifact, not an installed module: it
is copied into the driver session's `.claude/hooks/` and run by Claude Code as a
PreToolUse hook. So it is loaded here by path, and every case of its own
`SELFTEST` table is run as a test, one case per test, so a regression names the
command it let through or refused.
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
