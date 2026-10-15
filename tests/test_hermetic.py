"""DESIGN §36 "Hermetic tests" (H-040): no test sees the `HANDS_*` variables of
the environment that runs the suite — a builder dispatched by hands carries
`HANDS_PROJECT` and `HANDS_JOB`, and the gate must be the same inside a job and
outside one. `tests/conftest.py` clears them with an autouse fixture.

These tests prove something only when the suite runs with a `HANDS_*` variable
set (the gate of mission 20 U1 runs as `HANDS_PROJECT=x HANDS_JOB=y
./scripts/check`); outside a job they pass whatever conftest does.
"""

import os
import subprocess
import sys


def test_no_hands_variable_is_in_the_environment_of_a_test() -> None:
    leaked = sorted(name for name in os.environ if name.startswith("HANDS_"))
    assert leaked == [], f"the test environment carries {leaked}"


def test_no_hands_variable_reaches_a_child_process_of_a_test() -> None:
    probe = "import os; print([k for k in os.environ if k.startswith('HANDS_')])"
    out = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert out == "[]", f"a child of a test inherits {out}"
