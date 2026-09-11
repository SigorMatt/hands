# CHECKPOINT

Mission: 2 (meta/BUILDER-2-PROMPT.md) — IN PROGRESS
Unit in progress: U6 Status wording and monitor limitation (DESIGN §4, §5)
Intent: `hands status` documents `queue_depth` as capacity, not contents —
DESIGN §4's status row now says so. Rename nothing: add a one-line note in
the human output and a `queue_capacity` alias in `--json` if it is cheap.
Record the monitor limitation honestly where the human reads status.
Done means: a test on the output (human and JSON), ./scripts/check green,
one commit, pushed.
Tip: 44c345b + this meta commit; gate green (518 tests).
Done so far: U0, U3, U1, U2, U4, U5. Remaining: U6, U7, U8.
Standing constraints: one sub-agent per unit; commit and push every unit;
./scripts/check green before every commit; builders never edit DESIGN.md,
meta/plan.md or this file.
