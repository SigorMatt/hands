# CHECKPOINT

Mission: 6 (meta/BUILDER-6-PROMPT.md) — FINISHED
Unit in progress: none. U0..U7 all `[x]` in meta/plan.md.
Tip: 3dd3403 (`docs: the sentences outside the grep that still said the driver
waits`) plus this commit, which is meta only. `./scripts/check` green three
consecutive runs at 3dd3403: ruff clean, 1112 passed in 63.06s / 61.32s /
62.41s, cli smoke, `check: green`. `driver/hooks/bash_guard.py --selftest` is
100/100; `.claude/hooks/no_background.py --selftest` is 65/65.
Report: meta/FINAL-REPORT-6.md (NOT PROVEN in §3, review items in §4,
acceptance in §5, the architect's list in §6).
Review 5 is closed: both blockers and all seven should-fix items, except
should-fix 5's lettered edges (b) and (c), which this mission's brief did not
name and which are open and unscheduled — FINAL-REPORT-6 §4 says so.
Findings: H-001 open (needs a capture from a dotted cwd). H-009 open
(design-side; no builder unit can close it). H-012 closed by U1, H-013 closed
by U2. H-002..H-008, H-010 and H-011 closed in missions 2..5.
Two things a next mission should know before it starts:
  1. DESIGN §11 still carries the v3.4 text U6 retired, on both sides of the
     decision paragraph that retires it. The disk follows the decision
     paragraph and §22. FINAL-REPORT-6 §6 item 1 puts it to the architect.
  2. The installed build is still mission 2's, so four missions of code have
     never run outside pytest, and ntfy has never delivered a message.
     FINAL-REPORT-6 §3 items 9 and 10.
Standing constraints: one sub-agent per unit, commit and push every unit,
./scripts/check green three consecutive runs before each commit, DESIGN.md
is not edited by builders (file a finding), sub-agents do not edit
meta/plan.md or this file.
