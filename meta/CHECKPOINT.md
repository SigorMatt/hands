# CHECKPOINT

Mission: 6 (meta/BUILDER-6-PROMPT.md) — IN PROGRESS
Unit in progress: U5 (should-fix 3-7)
Intent: one test per item. (3) `Runner.retained()` counts `last_argv` and
the docstring says what is and is not counted; `last_argv` is popped at job
end or bounded. (4) U2-of-mission-5's containment test is restored as a real
path-resolution test (a symlink out of `ops.repo`, `..` after resolution).
(5) The config helper-coverage scan binds every section, including new ones,
and the unknown-key refusal covers new sections. (6) The test audits exempt
by type, not by source text. (7) Both prompt routes refuse invalid UTF-8 at
the same place with the same message.
Done means: one test per item, `./scripts/check` green three consecutive
runs, one commit pushed. Under quota pressure items 5 and 6 yield first.
Tip: fba759b (`hooks: the comment suffix, the path-qualified daemonizer and
unreadable input`), U4 done — 1095 passed, selftest 65/65; the builder
re-drove the two closed bypasses (both exit 2), `ls # a & b` and `uv run
pytest` (still allowed), the documented `bash -c 'cmd &'` (still allowed)
and a non-string command (now exit 2, one line).
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
     `bash_guard.main()`'s stdin/exit-2 wiring has no test. The
     `bash -c 'cmd &'` / `sh -c` / `eval` class and the blind-spot list
     (`screen -dmS`, `tmux new -d`, `at`, `systemd-run`, a forking script, a
     daemonizer through a variable) stay allowed by design — documented in
     docs/INTEGRATION.md under "what the hook cannot see", not blocked.
  4. The guard's allow list still contains mutation vectors that carry no
     option and so survive U3's allowlist: `git branch <name>`, `git remote
     prune origin`, `git remote set-head origin main`, `git fetch origin
     main:main` and a forced refspec. The allowed options are themselves the
     remaining surface (U3's enumerated table).
Standing constraints: one sub-agent per unit, commit and push every unit,
./scripts/check green three consecutive runs before each commit, DESIGN.md
is not edited by builders (file a finding), sub-agents do not edit
meta/plan.md or this file.
