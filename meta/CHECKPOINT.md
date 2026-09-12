# CHECKPOINT

Mission: 6 (meta/BUILDER-6-PROMPT.md) — IN PROGRESS
Unit in progress: U3 (should-fix 1 — the guard's per-subcommand option allowlist)
Intent: `driver/hooks/bash_guard.py` replaces its git option denylist with
the allowlist DESIGN §12 specifies — a table from allowed subcommand to
allowed options; any token beginning with `-` that is not in that
subcommand's table is refused; no option that names a program or a file is
listed; the `-C` value must not begin with `-` and must be a single path.
Done means: the adversarial table carries the reviewer's `--upload-pack=`,
`--exec=`, `branch --edit-description` and `-C --exec-path=` probes, each
asserted blocked, and the driver's read-only commands each asserted allowed;
`driver/settings.json` allow rules unchanged; the commit body enumerates the
allowed options per subcommand; `./scripts/check` green three consecutive
runs; one commit pushed.
Tip: 0042433 (`api: tail says when it was cut, and log is delivered in
pages`), U2 done — 942 passed; `tail -n 0` refused with exit 2, `truncated:
true` on both cut paths (re-driven by the builder: 2000 entries -> 1000
truncated, a wider-than-window trailing entry -> [] truncated).
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
