# CHECKPOINT

Mission: 5 (meta/BUILDER-5-PROMPT.md) — IN PROGRESS
Unit in progress: U0 (plan and corrections)
Intent: write meta/plan.md and this file for mission 5; append to
meta/FINAL-REPORT-4.md §3 a dated correction of item 15 (the guard's
arbitrary-exec surface was not empty at 935a275, citing REVIEW-4 blocker 1);
append to H-011 the decision that the event is renamed
`pipeline.stop_suppressed`.
Done means: those four files written, `./scripts/check` green, one commit,
pushed.
Tip: 6c9440d, green here before U0 — ruff clean, 726 passed, cli smoke,
`check: green`.
Findings: H-001 open (needs a capture from a dotted cwd). H-009 open
(design-side; no builder unit can close it). H-011 open until U0 appends the
architect's decision — the kind becomes `pipeline.stop_suppressed`, outside
`stop`'s wake namespace; U5 makes the rename in code, tests and docs.
H-002..H-008 and H-010 closed in missions 2, 3 and 4.
Not proven, carried into this mission (see meta/FINAL-REPORT-4.md §3 and
REVIEW-4):
  1. Missions 3, 4 and 5's code have never run outside the test suite — the
     installed build is mission 2's. `uv tool install --force ~/git/hands`
     is what would put this mission's code under a real run.
  2. `hands notify --test` has never been run against a live ntfy topic.
  3. The guard has never run as a real Claude Code `PreToolUse` hook;
     `main()`'s stdin/exit-2 wiring has no test.
  4. The guard's allow list still contains write and mutation vectors the
     review named that no unit of this mission is asked to close
     (`git branch`, `git remote prune`, `git fetch --force <refspec>`);
     U8's NOT PROVEN states the remaining surface as the reviewer would.
Standing constraints: one sub-agent per unit, commit and push every unit,
./scripts/check green three consecutive runs before each commit, DESIGN.md
is not edited by builders (file a finding), sub-agents do not edit
meta/plan.md or this file.
