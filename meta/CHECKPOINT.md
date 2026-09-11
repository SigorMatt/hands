# CHECKPOINT

Mission: 4 (meta/BUILDER-4-PROMPT.md) — FINISHED 2026-09-12
Unit in progress: none
Intent: -
Done means: -
Tip: all of U0..U6 committed and pushed on `main`. `./scripts/check` green
three consecutive runs at 8343b92 (ruff + 726 tests + cli smoke) and
`bash_guard.py --selftest` 65/65. meta/FINAL-REPORT-4.md holds the account.
No order deviation, no unit yielded, no unit blocked; one departure from
one-commit-per-unit (U5 landed as 2fb3b7f then d348d07), recorded in the
report. Review 3's three blockers are closed by 935a275, 667ea52 and 8268539;
should-fix 1, 2, 4, 5, 8, 9, 10 and 11 are closed; should-fix 3, 6 and 7 are
deferred to a later mission by the mission brief.
Findings: H-001 open (needs a capture from a dotted cwd). H-011 filed after
U3: `stop.suppressed` falls inside `stop`'s wake namespace, so `hands wait
--for stop` wakes on a stop that was deliberately not notified — design-side,
open. H-009 open
(design-side; no builder unit can close it). H-010 closed by U1 (935a275): the rule is back in
`driver/settings.json` and `tests/test_docs.py` asserts it; the memo carries
U0's amendment and U1's closing Status line. H-002..H-008 closed in missions 2 and 3.
Not proven, carried into this mission (see meta/FINAL-REPORT-3.md §3, as
corrected by the dated line U0 appended):
  1. Mission 3's code has never run outside the test suite — the installed
     build is mission 2's (it has `notify`, it has no `--prompt-file`).
     `uv tool install --force ~/git/hands` is what would put this mission's
     code under a real run.
  2. `hands notify --test` has never been run against a live ntfy topic;
     delivery is still unproven, the httpx MockTransport test being
     off-network by construction.
  3. The guard has never run as a real Claude Code `PreToolUse` hook;
     `main()`'s stdin/exit-2 wiring has no test.
Standing constraints: one sub-agent per unit, commit and push every unit,
./scripts/check green before each commit (three consecutive runs this
mission — review 3 found the gate non-deterministic), DESIGN.md is not edited
by builders (file a finding), sub-agents do not edit meta/plan.md or this
file.
