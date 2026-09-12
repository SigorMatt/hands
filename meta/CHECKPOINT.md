# CHECKPOINT

Mission: 5 (meta/BUILDER-5-PROMPT.md) — IN PROGRESS
Unit in progress: U5 (pipeline and config edges)
Intent: `hands pipeline` marks `last_rule` with `stale: true` when its
`playbook_sha256` differs from the loaded one; the suppressed-stop event is
renamed `pipeline.stop_suppressed` everywhere (code, tests, docs); the two
config edges of REVIEW-4 should-fix 8 (`[ops] monitor_cmd` with no
`ops.repo`; every accepted value stored unstripped) are closed as mission 4
U4 closed the blank-value edge — by a mechanism a new key cannot skip.
Done means: tests for each; `grep -rn 'stop\.suppressed' src tests docs
driver` returns nothing; `./scripts/check` green three consecutive runs; one
commit, pushed.
Tip: 6d9664d (U4), green 3/3 — 804 passed, `check: green`.
Findings: H-001 open (needs a capture from a dotted cwd). H-009 open
(design-side; no builder unit can close it). H-011 decided by U0 (068a091):
the kind becomes `pipeline.stop_suppressed`, outside `stop`'s wake namespace;
U5 makes the rename in code, tests and docs. H-012 filed by U4 (6d9664d):
§4's "cap plus one quarter" does not cover JSON escaping, so U4 measures the
cap on the wire — design-side, open.
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
