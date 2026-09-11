# CHECKPOINT

Mission: 3 (meta/BUILDER-3-PROMPT.md) — IN PROGRESS
Unit in progress: U4 Empty `resume_line` refused
Intent: `resume_line = ""` must be a config error, not a silent second
behaviour (review should-fix 5, DESIGN §6, §13, §19).
Done means: an empty `resume_line` is refused at load with a message naming
the two valid choices (omit the key, or give a non-empty line);
docs/INTEGRATION.md says so. Test. Gate green; committed and pushed.
Tip: 3cd2306 (U3) — gate green, 526 passed.
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
