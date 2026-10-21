"""DESIGN §45 "`hands ci-wait <pr> [--check <name>]…`" and the reading of
GitHub it shares with doctor's `main` row (`hands.forge`).

Every test runs the fake `gh` (tests/fake_gh.py) in a local repository whose
`origin` is a github.com URL that is never contacted: `ci-wait` reads the URL
only, and every `gh` call goes to the stand-in. The clock and the sleep are the
test's, so a nine-minute wait takes no time; a sleep may change what the fake
answers next, as a check registering or finishing between two polls.
"""

from __future__ import annotations

import io
import json
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from conftest import strip_paths
from hands import cli, forge
from hands.cli import main as hands_main

REQUIRES_CHECK = json.dumps(
    [
        {"type": "deletion", "ruleset_source_type": "Repository", "ruleset_id": 1},
        {"type": "pull_request", "parameters": {"required_approving_review_count": 0}},
        {
            "type": "required_status_checks",
            "parameters": {
                "required_status_checks": [{"context": "check", "integration_id": 15368}],
                "strict_required_status_checks_policy": False,
            },
        },
    ]
)
LINK = "https://github.com/o/r/actions/runs/1/job/2"
OTHER_LINK = "https://github.com/o/r/actions/runs/3/job/4"


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True, timeout=30)
    subprocess.run(
        ["git", "-C", str(root), "remote", "add", "origin", "https://github.com/o/r.git"],
        check=True, timeout=30,
    )  # fmt: skip
    monkeypatch.chdir(root)
    monkeypatch.setenv("FAKE_GH_API_LOG", str(tmp_path / "gh.log"))
    monkeypatch.setenv("FAKE_GH_CHECKS", str(tmp_path / "checks.json"))
    return root


@pytest.fixture
def checks_file(tmp_path: Path) -> Callable[[list[dict[str, str]] | None], None]:
    """Set what `gh pr checks` answers; None removes the file (none reported yet)."""

    def _set(entries: list[dict[str, str]] | None) -> None:
        path = tmp_path / "checks.json"
        if entries is None:
            path.unlink(missing_ok=True)
        else:
            path.write_text(json.dumps(entries), encoding="utf-8")

    return _set


class Clock:
    """A clock whose sleep advances it, and may run a step first."""

    def __init__(self, steps: dict[int, Callable[[], None]] | None = None) -> None:
        self.now = 1000.0
        self.sleeps: list[float] = []
        self.steps = steps or {}

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds
        step = self.steps.get(len(self.sleeps))
        if step is not None:
            step()


def wait(*names: str, pr: int = 7, clock: Clock | None = None) -> tuple[int, list[str]]:
    out = io.StringIO()
    clock = clock or Clock()
    code = cli.ci_wait(pr, list(names), out=out, clock=clock, sleep=clock.sleep)
    return code, out.getvalue().splitlines()


def entry(name: str, bucket: str, link: str = LINK) -> dict[str, str]:
    return {"bucket": bucket, "link": link, "name": name}


# ----------------------------------------------- owner/repo from origin (§45)


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/o/r.git",
        "git@github.com:o/r.git",
        "ssh://git@github.com/o/r",
        "https://github.com/o/r",
        "git@github.com:o/r",
        "ssh://git@github.com/o/r.git",
    ],
)
def test_owner_repo_of_a_github_com_origin_in_https_or_ssh_form(url: str) -> None:
    assert forge.owner_repo(url) == "o/r"


@pytest.mark.parametrize(
    "url",
    [
        "https://gitlab.com/o/r.git",
        "git@ghe.example.invalid:o/r.git",
        "/srv/git/r.git",
        "file:///srv/git/r.git",
        "https://github.com/o",
        "https://github.com.evil.invalid/o/r.git",
        "",
    ],
)
def test_an_origin_not_on_github_com_names_no_repository(url: str) -> None:
    assert forge.owner_repo(url) is None


def test_the_required_checks_are_the_contexts_of_the_rule() -> None:
    rules = json.loads(REQUIRES_CHECK)
    assert forge.required_checks(rules) == ["check"]
    assert forge.rule_types(rules) == ["deletion", "pull_request", "required_status_checks"]
    assert forge.required_checks([]) == []


# ------------------------------------------------ the rules require `check`


@pytest.mark.parametrize(
    ("bucket", "code", "last"),
    [
        ("pass", 0, "ci-wait: passed"),
        ("skipping", 0, "ci-wait: passed"),
        ("fail", 1, "ci-wait: failed: check"),
        ("cancel", 1, "ci-wait: failed: check"),
    ],
)
def test_with_the_rules_requiring_check_its_bucket_decides(
    repo: Path, checks_file, monkeypatch: pytest.MonkeyPatch, bucket: str, code: int, last: str
) -> None:
    monkeypatch.setenv("FAKE_GH_RULES", REQUIRES_CHECK)
    checks_file([entry("check", bucket)])
    got, lines = wait()
    assert got == code, lines
    assert lines == [f"check  {bucket}  {LINK}", last]


def test_pending_at_the_limit_is_still_waiting_exit_3(
    repo: Path, checks_file, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_GH_RULES", REQUIRES_CHECK)
    checks_file([entry("check", "pending")])
    clock = Clock()
    got, lines = wait(clock=clock)
    assert got == 3, lines
    assert lines == [f"check  pending  {LINK}", "ci-wait: waiting: check"]
    # nine minutes at most, polling every thirty seconds
    assert sum(clock.sleeps) == 540
    assert set(clock.sleeps) == {30}


def test_not_reported_at_the_limit_is_waiting_not_an_error(
    repo: Path, checks_file, monkeypatch: pytest.MonkeyPatch
) -> None:
    """gh 2.89 answers `no checks reported on the '<branch>' branch`, exit 1,
    until the first check registers: none reported yet, never an error."""
    monkeypatch.setenv("FAKE_GH_RULES", REQUIRES_CHECK)
    checks_file(None)
    probe = subprocess.run(
        ["gh", "pr", "checks", "7", "--json", "name,bucket,link"],
        capture_output=True, text=True, timeout=30,
    )  # fmt: skip
    assert probe.returncode == 1
    assert probe.stderr.strip() == "no checks reported on the 'feature' branch"
    got, lines = wait()
    assert got == 3, lines
    assert lines == ["check  pending  (not reported yet)", "ci-wait: waiting: check"]


def test_a_check_that_registers_and_passes_meanwhile_ends_the_wait(
    repo: Path, checks_file, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_GH_RULES", REQUIRES_CHECK)
    checks_file(None)
    clock = Clock(
        {
            2: lambda: checks_file([entry("check", "pending")]),
            4: lambda: checks_file([entry("check", "pass")]),
        }
    )
    got, lines = wait(clock=clock)
    assert got == 0, lines
    assert lines[-1] == "ci-wait: passed"
    assert clock.sleeps == [30, 30, 30, 30]


def test_another_check_passing_does_not_pass_the_wait(
    repo: Path, checks_file, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_GH_RULES", REQUIRES_CHECK)
    checks_file([entry("qodo", "pass", OTHER_LINK), entry("check", "pending")])
    got, lines = wait()
    assert got == 3, lines
    assert lines == [f"check  pending  {LINK}", "ci-wait: waiting: check"]


def test_another_check_failing_does_not_fail_the_wait(
    repo: Path, checks_file, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_GH_RULES", REQUIRES_CHECK)
    checks_file([entry("qodo", "fail", OTHER_LINK), entry("check", "pass")])
    got, lines = wait()
    assert got == 0, lines
    assert lines == [f"check  pass  {LINK}", "ci-wait: passed"]


def test_with_rules_a_check_flag_does_not_replace_the_required_ones(
    repo: Path, checks_file, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_GH_RULES", REQUIRES_CHECK)
    checks_file([entry("qodo", "pass", OTHER_LINK), entry("check", "fail")])
    got, lines = wait("qodo")
    assert got == 1, lines
    assert lines[-1] == "ci-wait: failed: check"


def test_the_rules_are_read_for_the_pull_requests_base(
    repo: Path, checks_file, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("FAKE_GH_PR_BASE", "trunk")
    checks_file([entry("check", "pass")])
    got, _ = wait("check")
    assert got == 0
    log = (tmp_path / "gh.log").read_text(encoding="utf-8")
    assert "api repos/o/r/rules/branches/trunk" in strip_paths(log)


# ---------------------------------------------------- no rules: `--check`


@pytest.mark.parametrize(
    ("bucket", "code", "last"),
    [
        ("pass", 0, "ci-wait: passed"),
        ("skipping", 0, "ci-wait: passed"),
        ("fail", 1, "ci-wait: failed: check"),
        ("cancel", 1, "ci-wait: failed: check"),
        ("pending", 3, "ci-wait: waiting: check"),
    ],
)
def test_with_no_rules_the_named_check_is_waited_for_the_same_way(
    repo: Path, checks_file, bucket: str, code: int, last: str
) -> None:
    """GitHub answers `[]` for the rules of an unprotected branch."""
    checks_file([entry("qodo", "pass", OTHER_LINK), entry("check", bucket)])
    got, lines = wait("check")
    assert got == code, lines
    assert lines == [f"check  {bucket}  {LINK}", last]


def test_with_no_rules_a_named_check_not_reported_is_waiting(repo: Path, checks_file) -> None:
    checks_file(None)
    got, lines = wait("check")
    assert got == 3, lines
    assert lines == ["check  pending  (not reported yet)", "ci-wait: waiting: check"]


def test_with_no_rules_and_no_check_flag_there_is_nothing_to_wait_for(
    repo: Path, checks_file
) -> None:
    checks_file([entry("check", "pass")])
    got, lines = wait()
    assert got == 2, lines
    assert lines == [
        "ci-wait: error: no check to wait for: main's rules require none and no --check "
        "was given"
    ]


def test_several_checks_named_each_decides(repo: Path, checks_file) -> None:
    checks_file([entry("a", "pass"), entry("b", "pending")])
    got, lines = wait("a", "b", "c")
    assert got == 3, lines
    assert lines == [
        f"a  pass  {LINK}",
        f"b  pending  {LINK}",
        "c  pending  (not reported yet)",
        "ci-wait: waiting: b, c",
    ]
    checks_file([entry("a", "fail"), entry("b", "pending"), entry("c", "cancel")])
    got, lines = wait("a", "b", "c")
    assert got == 1, lines
    assert lines[-1] == "ci-wait: failed: a, c"


# ------------------------------------------------------------ the errors (2)


def test_no_gh_is_exit_2_with_the_reason(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bindir = tmp_path / "bin-without-gh"
    bindir.mkdir()
    for tool in ("git", "python3"):
        found = shutil.which(tool)
        if found:
            (bindir / tool).symlink_to(found)
    monkeypatch.setenv("PATH", str(bindir))
    assert shutil.which("gh") is None
    got, lines = wait("check")
    assert got == 2, lines
    assert lines == ["ci-wait: error: no `gh` on PATH"]


def test_not_signed_in_is_exit_2_with_the_reason(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_GH_MODE", "unauth")
    got, lines = wait("check")
    assert got == 2, lines
    assert len(lines) == 1
    assert lines[0].startswith("ci-wait: error: `gh` is not signed in to github.com: ")
    assert "gh auth login" in strip_paths(lines[0])


def test_an_unknown_pull_request_is_exit_2_with_the_reason(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_GH_PRS", "7")
    got, lines = wait("check", pr=404)
    assert got == 2, lines
    assert lines == [
        "ci-wait: error: pull request #404: GraphQL: Could not resolve to a PullRequest "
        "with the number of 404. (repository.pullRequest)"
    ]


def test_rules_that_cannot_be_read_are_exit_2(
    repo: Path, checks_file, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_GH_MODE", "rulesfail")
    checks_file([entry("check", "pass")])
    got, lines = wait("check")
    assert got == 2, lines
    assert len(lines) == 1
    assert lines[0].startswith("ci-wait: error: main's rules: ")
    assert "HTTP 502" in strip_paths(lines[0])


def test_an_origin_not_on_github_com_is_exit_2(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    subprocess.run(
        ["git", "remote", "set-url", "origin", "https://gitlab.com/o/r.git"],
        check=True, timeout=30,
    )  # fmt: skip
    got, lines = wait("check")
    assert got == 2, lines
    assert lines == ["ci-wait: error: origin is not a github.com repository"]


def test_a_tokened_origin_is_never_printed(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    subprocess.run(
        ["git", "remote", "set-url", "origin", "https://x:tk_SECRET0@gitlab.com/o/r.git"],
        check=True, timeout=30,
    )  # fmt: skip
    got, lines = wait("check")
    assert got == 2
    assert "tk_SECRET0" not in strip_paths("\n".join(lines))


# ------------------------------------- the limit bounds the whole call (§45)


class Stalls:
    """`subprocess.run` for `hands.forge`: each `git` or `gh` call takes `takes`
    seconds of the test's clock; one that would take longer than the timeout it
    was given times out at that timeout, as a stalled tool does."""

    def __init__(self, clock: Clock, takes: float) -> None:
        self.clock = clock
        self.takes = takes
        self.calls: list[tuple[str, float, float]] = []  # (command, started, timeout)
        self.real = subprocess.run

    def __call__(self, argv: list[str], **kwargs):  # type: ignore[no-untyped-def]
        timeout = kwargs["timeout"]
        command = " ".join(Path(argv[0]).name.split() + argv[1:3])
        self.calls.append((command, self.clock.now, timeout))
        if self.takes > timeout:
            self.clock.now += timeout
            raise subprocess.TimeoutExpired(argv, timeout)
        self.clock.now += self.takes
        return self.real(argv, **kwargs)


@pytest.fixture
def stalls(monkeypatch: pytest.MonkeyPatch) -> Callable[[Clock, float], Stalls]:
    def _make(clock: Clock, takes: float) -> Stalls:
        runner = Stalls(clock, takes)
        monkeypatch.setattr(forge.subprocess, "run", runner)
        return runner

    return _make


def bounded(runner: Stalls, clock: Clock, start: float, limit: float) -> None:
    """Every read was given no more than the time left, and the call ended by the limit."""
    for command, started, timeout in runner.calls:
        assert 0 < timeout <= start + limit - started, (command, started, timeout)
        assert timeout <= forge.GH_TIMEOUT_S
    assert clock.now <= start + limit


def test_slow_reads_before_the_first_poll_count_against_the_nine_minutes(
    repo: Path, checks_file, monkeypatch: pytest.MonkeyPatch, stalls
) -> None:
    """Each read takes 100 s: four before the first poll (sign-in, origin, the
    pull request, the rules) use 400 of the 540, so the poll after one sleep has
    10 s left, stalls and ends the call at the limit as still waiting."""
    monkeypatch.setenv("FAKE_GH_RULES", REQUIRES_CHECK)
    checks_file([entry("check", "pending")])
    clock = Clock()
    runner = stalls(clock, 100.0)
    out = io.StringIO()
    code = cli.ci_wait(7, [], out=out, clock=clock, sleep=clock.sleep)
    assert code == 3, out.getvalue()
    assert out.getvalue().splitlines() == [f"check  pending  {LINK}", "ci-wait: waiting: check"]
    bounded(runner, clock, 1000.0, 540.0)
    assert clock.now == 1540.0
    assert [c for c, _, _ in runner.calls] == [
        "gh auth status", "git -C " + str(repo), "gh pr view",
        "gh api repos/o/r/rules/branches/main", "gh pr checks", "gh pr checks",
    ]  # fmt: skip
    assert runner.calls[-1][2] == 10.0
    assert clock.sleeps == [30.0]


def test_a_read_of_the_pull_request_stalled_at_the_limit_is_an_error(
    repo: Path, checks_file, stalls
) -> None:
    """Sign-in and origin take 200 of a 250 s limit: the pull request's read is
    given the 50 s left, stalls, and the call ends at the limit with exit 2 (it
    could not read the pull request)."""
    checks_file([entry("check", "pass")])
    clock = Clock()
    runner = stalls(clock, 100.0)
    out = io.StringIO()
    code = cli.ci_wait(7, ["check"], out=out, clock=clock, sleep=clock.sleep, limit_s=250.0)
    assert code == 2, out.getvalue()
    lines = out.getvalue().splitlines()
    assert len(lines) == 1
    assert lines[0].startswith("ci-wait: error: gh pr view did not answer within 50 s")
    bounded(runner, clock, 1000.0, 250.0)
    assert clock.now == 1250.0


def test_no_time_left_before_a_read_is_an_error_and_the_read_never_starts(
    repo: Path, checks_file, stalls
) -> None:
    checks_file([entry("check", "pass")])
    clock = Clock()
    runner = stalls(clock, 100.0)
    out = io.StringIO()
    code = cli.ci_wait(7, ["check"], out=out, clock=clock, sleep=clock.sleep, limit_s=200.0)
    assert code == 2, out.getvalue()
    assert out.getvalue().splitlines() == [
        "ci-wait: error: pull request #7: not read, the 200 s limit was reached"
    ]
    assert [c for c, _, _ in runner.calls][-1].startswith("git")
    bounded(runner, clock, 1000.0, 200.0)


def test_a_first_poll_stalled_at_the_limit_is_still_waiting(
    repo: Path, checks_file, monkeypatch: pytest.MonkeyPatch, stalls
) -> None:
    """The first checks read is given the 50 s left and stalls: exit 3, each
    awaited check pending and not read, never a pass and never an error."""
    monkeypatch.setenv("FAKE_GH_RULES", REQUIRES_CHECK)
    checks_file([entry("check", "pass")])
    clock = Clock()
    runner = stalls(clock, 100.0)
    out = io.StringIO()
    code = cli.ci_wait(7, [], out=out, clock=clock, sleep=clock.sleep, limit_s=450.0)
    assert code == 3, out.getvalue()
    assert out.getvalue().splitlines() == [
        "check  pending  (not read before the limit)",
        "ci-wait: waiting: check",
    ]
    bounded(runner, clock, 1000.0, 450.0)
    assert clock.now == 1450.0


def test_a_checks_read_stalled_with_time_left_is_still_an_error(
    repo: Path, checks_file, monkeypatch: pytest.MonkeyPatch, stalls
) -> None:
    """A read given gh's own 120 s, not cut short by the limit, that does not
    answer is a read that failed: exit 2, as before."""
    monkeypatch.setenv("FAKE_GH_RULES", REQUIRES_CHECK)
    checks_file([entry("check", "pass")])
    clock = Clock()
    runner = stalls(clock, 0.0)
    real = runner.real

    def checks_stall(argv: list[str], **kwargs):  # type: ignore[no-untyped-def]
        if argv[1:3] == ["pr", "checks"]:
            clock.now += kwargs["timeout"]
            raise subprocess.TimeoutExpired(argv, kwargs["timeout"])
        return real(argv, **kwargs)

    monkeypatch.setattr(forge.subprocess, "run", checks_stall)
    out = io.StringIO()
    code = cli.ci_wait(7, [], out=out, clock=clock, sleep=clock.sleep)
    assert code == 2, out.getvalue()
    assert out.getvalue().splitlines() == [
        "ci-wait: error: gh pr checks did not answer within 120 s"
    ]


@pytest.mark.parametrize(
    ("stall", "code", "last"),
    [
        ("auth status", 2, "ci-wait: error: gh auth status did not answer within "),
        ("pr view", 2, "ci-wait: error: gh pr view did not answer within "),
        ("api", 2, "ci-wait: error: gh api repos/o/r/rules/branches/main did not answer within "),
        ("pr checks", 3, "ci-wait: waiting: check"),
    ],
)
def test_a_stalled_gh_ends_the_call_by_the_limit_on_the_real_clock(
    repo: Path, checks_file, monkeypatch: pytest.MonkeyPatch, stall: str, code: int, last: str
) -> None:
    """The fake `gh` sleeps 60 s on one command; with a 2 s limit, timed by
    the real clock, the whole call ends within the limit and a margin for
    killing the stalled process."""
    import time

    monkeypatch.setenv("FAKE_GH_RULES", REQUIRES_CHECK)
    monkeypatch.setenv("FAKE_GH_STALL", stall)
    checks_file([entry("check", "pass")])
    out = io.StringIO()
    started = time.monotonic()
    got = cli.ci_wait(7, [], out=out, limit_s=2.0, interval_s=0.1)
    took = time.monotonic() - started
    assert got == code, out.getvalue()
    assert out.getvalue().splitlines()[-1].startswith(last)
    assert took < 2.0 + 1.0, took


# ---------------------------------------------------------------- the command


def test_the_command_line_takes_the_pr_and_repeated_check_flags(
    repo: Path, checks_file, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    checks_file([entry("check", "pass"), entry("lint", "skipping")])
    out, err = io.StringIO(), io.StringIO()
    code = hands_main(
        ["ci-wait", "7", "--check", "check", "--check", "lint"], stdout=out, stderr=err
    )
    assert code == 0, (out.getvalue(), err.getvalue())
    assert out.getvalue().splitlines() == [
        f"check  pass  {LINK}",
        f"lint  skipping  {LINK}",
        "ci-wait: passed",
    ]
    log = (tmp_path / "gh.log").read_text(encoding="utf-8").splitlines()
    assert "pr checks 7 --repo o/r --json name,bucket,link" in [strip_paths(x) for x in log]
    # read-only: GETs and reads only
    assert all(line.split()[0] in ("api", "pr") for line in log)
    assert not any("-X" in strip_paths(line) or "--method" in strip_paths(line) for line in log)


def test_the_command_waits_with_the_module_limit_and_interval(
    repo: Path, checks_file, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The defaults are the module's nine minutes and thirty seconds, read when
    the command runs, so a test can shorten them."""
    assert (cli.CI_WAIT_LIMIT_S, cli.CI_WAIT_INTERVAL_S) == (540.0, 30.0)
    # the limit counts from the call's start, the reads before the first poll too
    monkeypatch.setattr(cli, "CI_WAIT_LIMIT_S", 3.0)
    monkeypatch.setattr(cli, "CI_WAIT_INTERVAL_S", 0.5)
    checks_file([entry("check", "pending")])
    out = io.StringIO()
    code = hands_main(["ci-wait", "7", "--check", "check"], stdout=out, stderr=io.StringIO())
    assert code == 3
    assert out.getvalue().splitlines()[-1] == "ci-wait: waiting: check"


def test_the_help_names_the_exit_codes() -> None:
    from hands.cli import build_parser

    sub = next(a for a in build_parser()._actions if a.dest == "command")
    parser = sub.choices["ci-wait"]  # type: ignore[attr-defined]
    text = strip_paths(" ".join([parser.description, *(a.help or "" for a in parser._actions)]))
    for said in ("required_status_checks", "--check", "nine minutes", "thirty seconds"):
        assert said in strip_paths(text), said
