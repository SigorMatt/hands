# CHECKPOINT

Mission: 6 (meta/BUILDER-6-PROMPT.md) — IN PROGRESS
Unit in progress: U2 (blocker 2 — tail semantics and log paging)
Intent: `hands tail -n` requires n >= 1 (0 and negatives refused with exit
2); the answer carries `truncated: true` whenever the 1000-entry cap or the
read window cut it, and the human output says so in one line; `hands log
<job>` reads the log file in pages of bounded size and the client prints
them in order.
Done means: tests for `-n 0`, for a 2000-entry transcript (truncated), for a
trailing entry wider than the window (truncated, not `[]`), and for `log`
over a 64 MB file with bounded peak memory measured by `tracemalloc`;
`./scripts/check` green three consecutive runs; one commit pushed.
Tip: 81e4cd2 (`client: measure the whole request before connecting`), U1
done — 936 passed; the reviewer's reproduction refuses with exit 2 before
connecting (re-driven by the builder through the real CLI: "the request is
13630014 bytes on the wire, over the daemon's 13107200 byte line room").
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
