# CHECKPOINT

Mission: 5 (meta/BUILDER-5-PROMPT.md) — IN PROGRESS
Unit in progress: U1 (blocker 1 — the guard's git option policy)
Intent: in driver/hooks/bash_guard.py, accept only `-C <path>` and
`--no-pager` before the subcommand and refuse every other leading `-` token
naming the policy; refuse `--output`, `--output=…`, `--ext-diff`,
`--textconv`, `-O`, `--open-files-in-pager`, `--config-env` after it, in any
spelling; add `-fprint`, `-fprint0`, `-fprintf`, `-fls` to FIND_ACTION_FLAGS;
put REVIEW-4 blocker 1's exact probes in the adversarial table as blocked and
the four read-only commands the driver relies on as allowed.
Done means: both guard tables green, `./scripts/check` green three
consecutive runs, one commit whose body lists the probes blocked only after
this change, pushed.
Tip: 068a091 (U0), green — ruff clean, 726 passed, cli smoke, `check: green`.
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
