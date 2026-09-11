# CHECKPOINT

Mission: 3 (meta/BUILDER-3-PROMPT.md) — IN PROGRESS
Unit in progress: U6 Guard fix and guard tests
Intent: fix the Bash guard's false positive and put the guard under the test
suite (DESIGN §19, §12).
Done means: in driver/hooks/bash_guard.py the mutating-git check leaves
FORBIDDEN_PATTERNS for the git subcommand logic (subcommand position only),
so `git -C ./repo rev-parse <sha>^{commit}` and `git log --grep=commit` pass
while `git commit`, `git -C ./repo push` and `git -c x=y commit` are blocked;
those cases are in SELFTEST; a new tests/test_bash_guard.py imports the hook
by path and runs every SELFTEST case; driver/settings.json drops the
MultiEdit deny rule (memo H-010 already filed). Gate green; pushed.
Tip: 861097f (U5) — gate green, 539 passed.
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
