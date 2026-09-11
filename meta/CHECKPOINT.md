# CHECKPOINT

Mission: 2 (meta/BUILDER-2-PROMPT.md) — IN PROGRESS
Unit in progress: U8 Final report
Intent: write meta/FINAL-REPORT-2.md — what changed (a sha per unit), what
the tests prove, NOT PROVEN (mandatory, non-empty), findings status, and the
acceptance checks with their actual results including the one that cannot
hold as literally written (`grep only_if_run_in`, because U3's own gate
requires the refusal to name the old key).
Done means: the file exists with a non-empty NOT PROVEN section,
./scripts/check green, one commit, pushed; then the orchestrator's verdict
line.
Tip: d973ece + this meta commit; gate green (521 tests).
Done so far: U0, U3, U1, U2, U4, U5, U6, U7. Remaining: U8.
Standing constraints: one sub-agent per unit; commit and push every unit;
./scripts/check green before every commit; builders never edit DESIGN.md,
meta/plan.md or this file.
