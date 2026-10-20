"""DESIGN §45 "CI": the workflow that runs the gate on GitHub's runner, and the
suite's promise that no test sends a request off the machine."""

import re
import time
from pathlib import Path

import httpx

from conftest import strip_paths

WORKFLOW = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "check.yml"


def _text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_the_workflow_runs_on_pull_requests_and_pushes_to_main() -> None:
    text = _text()
    assert re.search(r"(?m)^on:\s*$", text), text
    assert re.search(r"(?m)^  pull_request:\s*$", text), text
    assert re.search(r"(?m)^  push:\s*\n    branches:\s*\[\s*main\s*\]\s*$", text), text


def test_the_workflow_has_one_job_whose_id_and_name_are_check() -> None:
    text = _text()
    jobs = re.findall(r"(?m)^  ([A-Za-z0-9_-]+):\s*$", text.split("\njobs:\n", 1)[1])
    assert jobs == ["check"], jobs
    assert re.search(r"(?m)^jobs:\n  check:\n    name: check$", text), text
    assert re.search(r"(?m)^    runs-on: ubuntu-latest$", text), text


def test_the_workflow_runs_the_gate() -> None:
    assert re.search(r"(?m)^ +(?:- )?run: \./scripts/check$", _text())


def test_the_workflow_reads_only_and_is_bounded() -> None:
    text = _text()
    assert re.search(r"(?m)^permissions:\n  contents: read$", text), text
    assert re.search(r"(?m)^    timeout-minutes: 30$", text), text
    assert re.search(
        r"(?m)^concurrency:\n  group: .*\$\{\{ github\.ref \}\}.*\n  cancel-in-progress: true$",
        text,
    ), text


def test_every_action_is_pinned_to_a_commit_sha() -> None:
    uses = re.findall(r"(?m)^\s*(?:- )?uses:\s*(\S+)(.*)$", _text())
    assert {name.split("@", 1)[0] for name, _ in uses} == {
        "actions/checkout",
        "astral-sh/setup-uv",
    }, uses
    for name, rest in uses:
        assert re.fullmatch(r"[^@\s]+@[0-9a-f]{40}", name), name
        assert re.fullmatch(r"\s+# v\d+\.\d+\.\d+\s*", rest), (name, rest)


def test_a_request_to_another_host_fails_at_once() -> None:
    """The autouse fixture in conftest.py points every proxy variable at a port
    nothing listens on, so a request off the machine is refused, not sent."""
    started = time.monotonic()
    try:
        httpx.get("https://ntfy.sh/hands-off-machine-probe", timeout=30)
    except (httpx.ProxyError, httpx.ConnectError) as exc:
        # The refusal is the proxy port's: a missing network fails by name
        # resolution or a timeout instead, which this does not accept.
        assert "Connection refused" in strip_paths(str(exc)), repr(exc)
    else:
        raise AssertionError("a request left the machine")
    assert time.monotonic() - started < 5
