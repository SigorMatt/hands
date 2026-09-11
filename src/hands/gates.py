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
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from hands.spool import now_iso

__all__ = [
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
#:     remote face of §9, which is deferred. The name is kept so the vocabulary of
#:     the record never has to change; nothing can produce it yet.
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
}

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
