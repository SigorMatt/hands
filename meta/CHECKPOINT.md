# CHECKPOINT

Mission: 3 (meta/BUILDER-3-PROMPT.md) — FINISHED 2026-09-12
Unit in progress: none
Intent: -
Done means: -
Tip: all of U0..U8 committed and pushed on `main`; `./scripts/check` green
(ruff + 618 tests + CLI smoke) and `bash_guard.py --selftest` 65/65.
`meta/FINAL-REPORT-3.md` holds the account. No order deviation, no unit
yielded, no unit blocked. Review should-fix 2-8 are closed by U0-U5 (item 1
by the brief's amended wording); U6 and U7 are DESIGN §19 work.
Findings: H-001 open (needs a capture from a dotted cwd). H-002, H-003,
H-005 fixed with no code change; H-004 a67c4b0, H-006 34b4ede, H-007
267ee01, H-008 8448b6f. H-009 and H-010 filed by mission 3 U0, both open
and both for the architect; H-010 carries a Status line recording that the
kit now diverges from DESIGN §12 by the mission brief's instruction.
Not proven, the two that matter most for the next mission (unchanged, and
now three missions old — see meta/FINAL-REPORT-3.md §3 for all twelve):
  1. None of mission 2's or mission 3's code has ever run outside the test
     suite — the installed daemon is still the mission-1 build. `uv tool
     install --force ~/git/hands` is what would put it under a real run.
  2. `hands notify --test` has never been run against a live ntfy topic; U5
     proved the status plumbing against httpx MockTransport, which is
     off-network by construction, so delivery is still unproven.
Standing constraints: one sub-agent per unit, commit and push every unit,
./scripts/check green before each commit, DESIGN.md is not edited by
builders (file a finding), sub-agents do not edit meta/plan.md or this file.
