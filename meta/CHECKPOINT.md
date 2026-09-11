# CHECKPOINT

Mission: 3 (meta/BUILDER-3-PROMPT.md) — IN PROGRESS
Unit in progress: U2 Tests that can fail
Intent: make four assertions that cannot fail actually fail (review
should-fix 3 and 8).
Done means: the four `BAD_PLAYBOOKS` cases in tests/test_playbook.py pin the
refusal on `run = "..."` or on the sentence, not on the bare substring `run`;
three of them are confirmed failing against `34b4ede^` in a worktree and the
commit body says so; the `queue_capacity` alias test asserts on aux (queue
depth 4), not builder (1). Gate green; committed and pushed.
Tip: 87bb7f8 (U1) — gate green, 523 passed.
Findings: H-001 open (needs a capture from a dotted cwd). H-002, H-003,
H-005 fixed with no code change; H-004 a67c4b0, H-006 34b4ede, H-007
267ee01, H-008 8448b6f. H-009, H-010 filed by this unit, both open and
both for the architect.
Not proven, carried forward from mission 2 and still true at the base:
  1. None of mission 2's code has ever run outside the test suite — the
     installed daemon is the mission-1 build. `uv tool install --force
     ~/git/hands` is what would put it under a real run.
  2. `hands notify --test` has never been run against a live ntfy topic.
Standing constraints: one sub-agent per unit, commit and push every unit,
./scripts/check green before each commit, DESIGN.md is not edited by
builders (file a finding), sub-agents do not edit meta/plan.md or this file.
