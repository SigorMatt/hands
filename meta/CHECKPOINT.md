# CHECKPOINT

Mission: 6 (meta/BUILDER-6-PROMPT.md) — IN PROGRESS
Unit in progress: U1 (blocker 1 — the whole request on the wire)
Intent: the client builds the request, measures its wire bytes, and refuses
with exit 2 before connecting when the total exceeds the daemon's line room;
both prompt routes; the two false sentences rewritten.
Done means: the reviewer's reproduction (at-cap prompt plus twelve `--file`
values of backslashes) refuses on the client with exit 2 and an untouched
daemon log, a request just under the limit succeeds, `./scripts/check` green
three consecutive runs, one commit pushed.
Tip: bb9d8fb (`meta: mission 6 plan; review 5's three corrections and the
H-012 decision`), U0 done; green three consecutive runs (929 passed).
Findings: H-001 open (needs a capture from a dotted cwd). H-009 open
(design-side; no builder unit can close it). H-012 decided by DESIGN v3.5 §4
and §22: the client measures the whole request on the wire before connecting;
U0 appends the decision, U1 makes it true on disk. H-013 decided by DESIGN
v3.5 §4's `log` row: `log` is delivered in pages; U2 makes it true on disk.
H-002..H-008, H-010 and H-011 closed in missions 2..5.
Not proven, carried into this mission (see meta/FINAL-REPORT-5.md §3):
  1. Missions 3, 4 and 5's code have never run outside the test suite — the
     installed build is mission 2's.
  2. `hands notify --test` has never been run against a live ntfy topic.
  3. Neither hook has run as a real Claude Code `PreToolUse` hook;
     `bash_guard.main()`'s stdin/exit-2 wiring has no test.
  4. The guard's allow list still contains write and mutation vectors
     (`git branch`, `git remote prune`, `git fetch --force <refspec>`) that
     U3's option allowlist does not by itself remove — an allowed option on
     an allowed subcommand stays allowed.
Standing constraints: one sub-agent per unit, commit and push every unit,
./scripts/check green three consecutive runs before each commit, DESIGN.md
is not edited by builders (file a finding), sub-agents do not edit
meta/plan.md or this file.
