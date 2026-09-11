# CHECKPOINT

Mission: 2 (meta/BUILDER-2-PROMPT.md) — FINISHED 2026-09-11
Unit in progress: none
Intent: -
Done means: -
Tip: all of U0..U8 committed and pushed on `main`; `./scripts/check` green
(ruff + 521 tests + CLI smoke). `meta/FINAL-REPORT-2.md` holds the account.
Order deviation on the record: U3 ran first, because the mission base was
red until it landed (meta/plan.md says why).
Findings: H-001 open (needs a capture from a dotted cwd — an observation,
not a change); H-002, H-003 fixed with no code change; H-004 a67c4b0,
H-005/H-006 34b4ede, H-007 267ee01, H-008 8448b6f.
Not proven, the two that matter most for the next mission:
  1. None of U1..U7's code has ever run outside the test suite — the
     installed daemon serving this session is the mission-1 build. A
     reinstall (`uv tool install --force ~/git/hands`) is what would put
     this mission's code under a real run.
  2. `hands notify --test` exists but has never been run against a live
     ntfy topic; that is the one command that would prove delivery.
Standing constraints: unchanged for the next mission — one sub-agent per
unit, commit and push every unit, ./scripts/check green, DESIGN.md is not
edited by builders.
