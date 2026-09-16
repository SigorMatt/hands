"""Gates — the human decision boundary (DESIGN §1 invariant 6, §6, §8).

A gated job enters `held` and waits, with no timeout, until a human decides it.
Two things live here and nowhere else:

* **what trips a gate** — `--gate <reason>` or a configured prompt pattern
  (`gate_reason`); the defaults cannot be switched off, which `config.py`
  enforces by taking the union rather than the config's list;
* **who may decide** — the authority table of §8, as `DECIDERS`, so a test can
  iterate it instead of re-describing it.

**What the daemon can and cannot know.** Both the CLI and the driver reach the
daemon as local clients of the same unix socket, owned by the same user. The
daemon cannot tell them apart and does not pretend to: `decided_by` records
*which path the caller declared*, and `--human-confirmed` is that declaration.
Its whole force is the quote — the driver must carry the human's own words, its
CLAUDE.md forbids inventing them, and the quote is stored verbatim on the record
so a human reading the job later can check it against what they actually said.
That is an audit trail, not an authentication mechanism, and nothing here should
be read as one.

`playbook` (§31) is the other authority §8's own table does not carry: the engine
approves a held apply of origin `architect` when the playbook in force sets
`[series] architect = "role"` and `autonomous = true`. What makes that a human
decision is one step removed — the human approved that playbook, at a gate like
any other — and the record says so in `decided_reason`, not in a quote.

`phone` (§24) is the exception, and it does not come through the socket at all:
`hands.phone` reads commands from ntfy, checks their token (the configured secret
or the held job's nonce), and only then decides through `Api.decide_from_phone`.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from hands.spool import now_iso

__all__ = [
    "DECIDED_BY",
    "DECIDERS",
    "DECISIONS",
    "GATE_KINDS",
    "Decider",
    "GateRefused",
    "decide",
    "decider_for",
    "gate_reason",
    "new_gate",
]


class GateRefused(Exception):
    """A decision hands will not accept, or a gate that is not there to decide."""


@dataclass(frozen=True)
class Decider:
    """One row of §8's authority table."""

    name: str
    requires_quote: bool
    available: bool
    note: str


#: §8, verbatim in structure:
#:   - `hands approve|deny <job>` run by you at the laptop: final; `decided_by: cli`.
#:   - `hands approve <job> --human-confirmed` run by the driver: the record stores
#:     `decided_by: driver` plus the quoted instruction. This is the phone path.
#:   - ntfy Approve/Deny buttons (`decided_by: button`) come with the optional
#:     remote face of §9, which is deferred. §8 still names it, so the row is
#:     kept, unavailable: `check_decider` refuses it, so no record carries it, and
#:     it is not in §6's record vocabulary (`DECIDED_BY`).
DECIDERS: dict[str, Decider] = {
    "cli": Decider(
        name="cli",
        requires_quote=False,
        available=True,
        note="you, at the laptop; final",
    ),
    "driver": Decider(
        name="driver",
        requires_quote=True,
        available=True,
        note="the phone path: --human-confirmed with the human's instruction quoted",
    ),
    "button": Decider(
        name="button",
        requires_quote=False,
        available=False,
        note="ntfy Approve/Deny buttons; part of the deferred remote face (§9)",
    ),
    #: §24: the ntfy command channel. Unlike `driver`, this one is authenticated —
    #: the command carried `cmd_secret` or the held job's single-use nonce — and it
    #: is never reachable over the socket: no API command takes a decider, and
    #: only `hands.phone` calls `Api.decide_from_phone`.
    "phone": Decider(
        name="phone",
        requires_quote=False,
        available=True,
        note="the ntfy command channel: cmd_secret or the held job's nonce (§24)",
    ),
    #: §31: the engine releasing a held apply of origin `architect` under a
    #: playbook that sets `[series] architect = "role"` and `autonomous = true`.
    #: Its authority is the human's approval of that playbook, which arrived as a
    #: kit and was gated like any other: approving an `autonomous` playbook is
    #: approving every apply the architect files under it. Like `phone`, it is not
    #: reachable over the socket — no API command takes a decider, and
    #: `Api.decide_from_playbook` is not in `COMMANDS` — and unlike `phone` it is
    #: narrowed twice more: only a job of origin `architect` (the API's check) and
    #: only while that playbook is in force (the engine's).
    "playbook": Decider(
        name="playbook",
        requires_quote=False,
        available=True,
        note=(
            'the engine, under a playbook with [series] architect = "role" and '
            "autonomous = true; the human's approval of the playbook is the "
            "standing approval (§31)"
        ),
    ),
}

#: Every `gate.decided_by` a record can carry: the available rows above — DESIGN
#: §6's `decided_by: cli|driver|phone` (review 8 should-fix 2, H-017) and §31's
#: `playbook`, which §6's record line does not yet list (H-031).
DECIDED_BY: tuple[str, ...] = tuple(name for name, row in DECIDERS.items() if row.available)

DECISIONS = ("approved", "denied")

#: What a gate is a gate *on*. A `send` gate holds the job itself (`held`); a
#: `cancel` gate holds the cancel request, not the job — §6's states have no
#: backwards edge, and a job that is running stays running until the cancel is
#: approved.
GATE_KINDS = ("send", "cancel")


def decider_for(*, human_confirmed: bool) -> str:
    """Which row of §8 a call claims. The flag is the claim; see the module docstring."""
    return "driver" if human_confirmed else "cli"


def check_decider(decided_by: str, quote: str | None) -> str | None:
    """Refuse a decision that §8's table does not allow. Returns the quote to store."""
    decider = DECIDERS.get(decided_by)
    if decider is None:
        raise GateRefused(f"unknown decider {decided_by!r}; §8 names {', '.join(DECIDERS)}")
    if not decider.available:
        raise GateRefused(f"{decided_by} decisions are {decider.note} and are not implemented")
    if decider.requires_quote and not (quote or "").strip():
        raise GateRefused(
            "--human-confirmed is the driver's path and needs --quote "
            '"<the human\'s instruction>": §8 accepts it only when a human '
            "message explicitly decided this job, and the quote is what the "
            "record keeps"
        )
    return quote


def gate_reason(prompt: str, *, explicit: str | None, patterns: Iterable[str]) -> str | None:
    """Why this send is gated, or None (§4, §8).

    `--gate <reason>` always gates and its reason is the human's own words. A
    configured pattern is a case-sensitive substring of the prompt (§4); the
    first one that matches names itself in the reason, so the held job says what
    tripped it.
    """
    if explicit is not None and explicit.strip():
        return explicit.strip()
    for pattern in patterns:
        if pattern in prompt:
            return f"the prompt matches the gate pattern {pattern!r} (§8)"
    return None


def new_gate(*, kind: str, reason: str) -> dict[str, Any]:
    """An undecided gate, in the shape §6 gives the `gate` field."""
    if kind not in GATE_KINDS:
        raise GateRefused(f"a gate is on {' or '.join(GATE_KINDS)}, not {kind!r}")
    return {
        "kind": kind,
        "reason": reason,
        "requested_at": now_iso(),
        "decision": None,
        "decided_by": None,
        "decided_at": None,
        "quote": None,
        "decided_reason": None,
    }


def decide(
    gate: dict[str, Any],
    *,
    decision: str,
    decided_by: str,
    quote: str | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    """Stamp a decision onto a gate, refusing what §8 refuses. Returns a new dict."""
    if decision not in DECISIONS:
        raise GateRefused(f"a gate is {' or '.join(DECISIONS)}, not {decision!r}")
    if gate.get("decided_by") is not None:
        raise GateRefused(
            f"this gate was already {gate.get('decision')} by {gate.get('decided_by')} "
            f"at {gate.get('decided_at')}"
        )
    stored = check_decider(decided_by, quote)
    return {
        **gate,
        "decision": decision,
        "decided_by": decided_by,
        "decided_at": now_iso(),
        "quote": stored,
        "decided_reason": reason,
    }
