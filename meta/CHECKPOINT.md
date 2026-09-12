# CHECKPOINT

Mission: 5 (meta/BUILDER-5-PROMPT.md) — IN PROGRESS
Unit in progress: U7 (no background tasks in role sessions)
Intent: add `.claude/settings.json` with a `PreToolUse` hook on `Bash`
running `.claude/hooks/no_background.py`, which reads the hook JSON and
exits 2 (reason on stderr) when `tool_input.run_in_background` is true or
the command daemonizes by hand (`nohup`, `setsid`, `disown`, a trailing `&`
outside quotes, `&` before `)`), telling the agent to run the command in the
foreground with a timeout; a `--selftest` and `tests/test_no_background.py`
that runs it; one line in CLAUDE.md; `docs/INTEGRATION.md` says every
project hands drives installs the same two files.
Done means: tests; `./scripts/check` itself still runs (it is foreground);
green three consecutive runs; one commit, pushed.
Tip: 53bb986 (U6), green 3/3 — 818 passed, `check: green`.
Findings: H-001 open (needs a capture from a dotted cwd). H-009 open
(design-side; no builder unit can close it). H-011 decided by U0 (068a091):
the kind becomes `pipeline.stop_suppressed`, outside `stop`'s wake namespace;
U5 makes the rename in code, tests and docs. H-011 closed on disk by U5 (06de18c).
H-013 filed by U6 (53bb986):
`hands log <job>` at offset 0 still materializes a whole transcript; it needs
a §7 paging contract — design-side, open. H-012 filed by U4 (6d9664d):
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
