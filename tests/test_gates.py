"""U4: human gates (DESIGN §1 invariant 6, §4, §6, §8).

A gated job enters `held` and only a human decision releases it. The authority
table of §8 is data here (`hands.gates.DECIDERS`) and data in the tests, so the
two can be iterated against each other rather than described twice in prose.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from hands.config import DEFAULT_GATE_PATTERNS
from hands.daemon import Daemon
from hands.gates import DECIDERS
from harness import BLOCK, PROJECT, cli, config_body, drive, fails, ok, running_job


@pytest.fixture
def workdir(tmp_path: Path) -> Path:
    d = tmp_path / "work"
    d.mkdir(exist_ok=True)
    return d


@pytest.fixture
def project(tmp_home: Path, workdir: Path) -> str:
    """Defaults everywhere: cancel is gated (§4) and the gate patterns are §4's."""
    (tmp_home / ".hands" / f"{PROJECT}.toml").write_text(config_body(tmp_home, workdir))
    return PROJECT


@pytest.fixture
def project_extra_patterns(tmp_home: Path, workdir: Path) -> str:
    """A project that adds one pattern — and tries to drop the five defaults."""
    body = config_body(
        tmp_home,
        workdir,
        extra="""
[gates]
patterns = ["rm -rf"]
""",
    )
    (tmp_home / ".hands" / f"{PROJECT}.toml").write_text(body)
    return PROJECT


@pytest.fixture
def project_ungated_cancel(tmp_home: Path, workdir: Path) -> str:
    body = config_body(tmp_home, workdir, builder="cancel_gated = false")
    (tmp_home / ".hands" / f"{PROJECT}.toml").write_text(body)
    return PROJECT


SEND = ("send", "--role", "builder", "--context", "clear")


async def send_gated(prompt: str = "please open the PR now") -> dict:
    job = await ok(*SEND, prompt)
    assert job["state"] == "held", f"{prompt!r} should have been gated: {job}"
    return job


# --------------------------------------------------------------- triggering


@pytest.mark.parametrize("pattern", DEFAULT_GATE_PATTERNS)
def test_each_default_pattern_holds_the_job(project: str, pattern: str) -> None:
    async def body(daemon: Daemon) -> None:
        job = await send_gated(f"please {pattern} today")
        assert job["gate"]["reason"]
        assert pattern in job["gate"]["reason"]
        assert job["gate"]["decided_by"] is None
        assert job["gate"]["decided_at"] is None
        kinds = [event["kind"] for event in (await ok("inbox"))["events"]]
        assert "job.held" in kinds
        assert (await ok("status"))["roles"]["builder"]["queued"] == []

    drive(body)


def test_the_match_is_case_sensitive(project: str) -> None:
    async def body(daemon: Daemon) -> None:
        job = await ok(*SEND, "FAKE:result please OPEN THE pr now")
        assert job["state"] in {"queued", "running"}
        assert job["gate"] is None

    drive(body)


def test_the_gate_flag_holds_the_job_with_its_reason(project: str) -> None:
    async def body(daemon: Daemon) -> None:
        job = await ok(*SEND, "--gate", "touches production", "FAKE:result x")
        assert job["state"] == "held"
        assert job["gate"]["reason"] == "touches production"

    drive(body)


def test_a_project_may_add_patterns_but_not_remove_the_defaults(
    project_extra_patterns: str,
) -> None:
    """§8: "gating on the default patterns cannot be disabled"."""

    async def body(daemon: Daemon) -> None:
        await send_gated("now rm -rf the tree")  # the project's addition
        await send_gated("open the PR please")  # a default it tried to drop

    drive(body)


def test_a_held_job_never_spawns(project: str, workdir: Path) -> None:
    marker = workdir / "ran.txt"

    async def body(daemon: Daemon) -> None:
        job = await send_gated(f"open the PR\nFAKE:cat {marker}")
        for _ in range(5):
            assert (await ok("result", job["id"]))["state"] == "held"
        assert (await ok("result", job["id"]))["started"] is None
        assert (await ok("result", job["id"]))["pid"] is None

    drive(body)


# ------------------------------------------------- the authority table (§8)


@dataclass(frozen=True)
class Case:
    label: str
    flags: tuple[str, ...]
    accepted: bool
    decided_by: str | None = None
    quote: str | None = None
    because: str = ""


QUOTE = 'Matthew said: "approve job 1, apply it"'

AUTHORITY = [
    Case("laptop CLI", (), True, decided_by="cli"),
    Case(
        "driver with a quote",
        ("--human-confirmed", "--quote", QUOTE),
        True,
        decided_by="driver",
        quote=QUOTE,
    ),
    Case(
        "driver with no quote",
        ("--human-confirmed",),
        False,
        because="--quote",
    ),
    Case(
        "driver with an empty quote",
        ("--human-confirmed", "--quote", "   "),
        False,
        because="--quote",
    ),
    Case("a quote without the flag is still the CLI", ("--quote", QUOTE), True,
         decided_by="cli", quote=QUOTE),
]


@pytest.mark.parametrize("case", AUTHORITY, ids=lambda c: c.label)
@pytest.mark.parametrize("decision", ["approve", "deny"])
def test_the_authority_table_of_section_8(project: str, case: Case, decision: str) -> None:
    async def body(daemon: Daemon) -> None:
        job = await send_gated()
        if not case.accepted:
            err = await fails(decision, job["id"], *case.flags)
            assert case.because in err, err
            assert (await ok("result", job["id"]))["state"] == "held"
            return
        decided = await ok(decision, job["id"], *case.flags)
        gate = decided["gate"]
        assert gate["decided_by"] == case.decided_by
        assert gate["decided_at"]
        assert gate["decision"] == ("approved" if decision == "approve" else "denied")
        assert gate["quote"] == case.quote  # verbatim, or absent
        if decision == "deny":
            assert decided["state"] == "denied"
        else:
            assert decided["state"] in {"queued", "running", "done"}
        kinds = [event["kind"] for event in (await ok("inbox"))["events"]]
        assert "gate.decided" in kinds

    drive(body)


def test_the_decider_vocabulary_is_section_8s(project: str) -> None:
    """`button` is §9's deferred remote face: named, and not reachable."""
    assert set(DECIDERS) == {"cli", "driver", "button"}
    assert DECIDERS["cli"].requires_quote is False
    assert DECIDERS["driver"].requires_quote is True
    assert DECIDERS["cli"].available and DECIDERS["driver"].available
    assert not DECIDERS["button"].available


def test_a_denied_job_is_terminal(project: str) -> None:
    async def body(daemon: Daemon) -> None:
        job = await send_gated()
        assert (await ok("deny", job["id"], "--reason", "no"))["state"] == "denied"
        for argv in (
            ["approve", job["id"]],
            ["deny", job["id"]],
            ["approve", job["id"], "--human-confirmed", "--quote", QUOTE],
            ["cancel", job["id"]],
        ):
            err = await fails(*argv)
            assert "denied" in err, err
        assert (await ok("result", job["id"]))["state"] == "denied"
        kinds = [event["kind"] for event in (await ok("inbox"))["events"]]
        assert "job.denied" in kinds

    drive(body)


def test_nothing_else_releases_a_held_job(project: str) -> None:
    """§8: "Nothing else releases a `held` job"."""

    async def body(daemon: Daemon) -> None:
        held = await send_gated()

        # not a second send of the same prompt (it is gated too, and is a new job)
        again = await send_gated()
        assert again["id"] != held["id"]

        # not `hands resume` (the playbook engine)
        await fails("resume")

        # not a queue slot opening: run a job to completion on the same role
        other = await ok(*SEND, "FAKE:result unrelated")
        assert (await ok("wait", other["id"]))["state"] == "done"

        # not cancel — it is pointed back at the decision
        err = await fails("cancel", held["id"])
        assert "approve" in err and "deny" in err

        assert (await ok("result", held["id"]))["state"] == "held"

    drive(body)


def test_a_held_job_survives_a_daemon_restart_still_held(project: str) -> None:
    async def body(daemon: Daemon) -> None:
        body.held = (await send_gated())["id"]  # type: ignore[attr-defined]

    drive(body)

    async def after(daemon: Daemon) -> None:
        job = await ok("result", body.held)  # type: ignore[attr-defined]
        assert job["state"] == "held", "a restart must not release a gate"
        assert (await ok("status"))["roles"]["builder"]["queued"] == []

    drive(after)


# ------------------------------------------------- approval joins the queue


def test_approval_enters_the_normal_path(project: str) -> None:
    async def body(daemon: Daemon) -> None:
        job = await send_gated("open the PR\nFAKE:result released")
        released = await ok("approve", job["id"])
        assert released["state"] in {"queued", "running"}
        done = await ok("wait", job["id"])
        assert done["state"] == "done"
        assert done["result"] == "released"
        assert done["gate"]["decided_by"] == "cli"  # the decision survives the run

    drive(body)


def test_approval_respects_the_roles_queue_depth(project: str) -> None:
    """§6: builder queue depth is 1; a held job takes no slot until it is approved."""

    async def body(daemon: Daemon) -> None:
        await ok(*SEND, BLOCK)
        await running_job("builder")
        filler = await ok(*SEND, "FAKE:result filler")
        assert filler["state"] == "queued"

        held = await send_gated("open the PR\nFAKE:result late")
        err = await fails("approve", held["id"])
        assert "queue" in err.lower()
        assert (await ok("result", held["id"]))["state"] == "held"

    drive(body)


# --------------------------------------------------------- the cancel gate


def test_cancel_is_gated_by_default_and_approval_performs_it(project: str) -> None:
    async def body(daemon: Daemon) -> None:
        job = await ok(*SEND, BLOCK)
        await running_job("builder")

        asked = await ok("cancel", job["id"], "--reason", "wrong branch")
        assert asked["state"] == "running", "the gated cancel must not kill anything yet"
        assert asked["gate"]["decision"] is None
        kinds = [event["kind"] for event in (await ok("inbox"))["events"]]
        assert "gate.requested" in kinds

        killed = await ok("approve", job["id"], "--human-confirmed", "--quote", QUOTE)
        assert killed["state"] == "killed"

    drive(body)


def test_a_denied_cancel_leaves_the_job_running(project: str) -> None:
    async def body(daemon: Daemon) -> None:
        job = await ok(*SEND, BLOCK)
        await running_job("builder")
        await ok("cancel", job["id"], "--reason", "second thoughts")

        kept = await ok("deny", job["id"], "--reason", "let it finish")
        assert kept["state"] == "running", "denying a cancel denies the cancel, not the job"
        assert (await ok("result", job["id"]))["state"] == "running"

        # and the gate is spent: a new cancel must be asked for again
        err = await fails("approve", job["id"])
        assert "no gate" in err.lower() or "nothing" in err.lower()

    drive(body)


def test_cancel_is_immediate_when_cancel_gated_is_false(project_ungated_cancel: str) -> None:
    async def body(daemon: Daemon) -> None:
        job = await ok(*SEND, BLOCK)
        await running_job("builder")
        assert (await ok("cancel", job["id"]))["state"] == "killed"

    drive(body)


def test_approve_needs_something_to_decide(project: str) -> None:
    async def body(daemon: Daemon) -> None:
        done = await ok(*SEND, "FAKE:result fine")
        await ok("wait", done["id"])
        err = await fails("approve", done["id"])
        assert "no gate" in err.lower() or "nothing" in err.lower()

    drive(body)


def test_the_readable_form_shows_the_gate(project: str) -> None:
    async def body(daemon: Daemon) -> None:
        job = await send_gated()
        code, out, _ = await cli("result", job["id"])
        assert code == 0
        assert "held" in out
        assert "waiting for a human" in out

        await ok("approve", job["id"], "--human-confirmed", "--quote", QUOTE)
        code, out, _ = await cli("result", job["id"])
        assert "approved by driver" in out
        assert QUOTE in out, "the human's instruction is stored verbatim (§8)"

    drive(body)


def test_an_explicit_gate_reason_wins_over_the_pattern(project: str) -> None:
    async def body(daemon: Daemon) -> None:
        job = await ok(*SEND, "--gate", "my own reason", "open the PR")
        assert job["state"] == "held"
        assert job["gate"]["reason"] == "my own reason"

    drive(body)
