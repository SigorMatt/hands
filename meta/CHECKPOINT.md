# CHECKPOINT

Mission: 6 (meta/BUILDER-6-PROMPT.md) — IN PROGRESS
Unit in progress: U4 (should-fix 2 — the hook's three bypasses)
Intent: for each of the three bypasses review 5 names (`cmd &# note`,
`/usr/bin/nohup x`, `bash -c 'cmd &'` / `eval`), either close it in
`.claude/hooks/no_background.py` with a test, or — where a hook cannot close
it — list it in `docs/INTEGRATION.md` under a "what the hook cannot see"
heading and in the mission report's NOT PROVEN.
Done means: tests for the closed ones, the doc heading for the rest,
`./scripts/check` green three consecutive runs, one commit pushed.
Tip: 5ffbe33 (`driver: the guard's git policy is a per-subcommand option
allowlist`), U3 done — 1047 passed, selftest 100/100; the builder re-drove
the five reviewer probes (all BLOCK) and the four driver reads (all ALLOW)
against the guard directly.
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
  4. The guard's allow list still contains mutation vectors that carry no
     option and so survive U3's allowlist: `git branch <name>`, `git remote
     prune origin`, `git remote set-head origin main`, `git fetch origin
     main:main` and a forced refspec. The allowed options are themselves the
     remaining surface (U3's enumerated table).
Standing constraints: one sub-agent per unit, commit and push every unit,
./scripts/check green three consecutive runs before each commit, DESIGN.md
is not edited by builders (file a finding), sub-agents do not edit
meta/plan.md or this file.
