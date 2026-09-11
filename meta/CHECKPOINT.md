# CHECKPOINT

Mission: 2 (meta/BUILDER-2-PROMPT.md) — IN PROGRESS
Unit in progress: U2 Resume line optional (H-008, DESIGN §6, §10, §13)
Intent: `role.resume_line` loses its default. Absent, a builder limit resume
re-sends the limited job's own prompt (the agile-skills form, whose kickoff
line is checkpoint-driven); set, it sends the line (the spanweave form). Aux
is unchanged — always the same prompt again. §10's `resume` action reads the
same way. `hands doctor` reports which of the two behaviours each role has.
Done means: tests for both branches (absent and set), a doctor test,
./scripts/check green, one commit, pushed.
Tip: a67c4b0 + this meta commit; gate green (496 tests).
Done so far: U0, U3, U1. Remaining: U2, U4, U5, U6, U7, U8.
Standing constraints: one sub-agent per unit; commit and push every unit;
./scripts/check green before every commit; builders never edit DESIGN.md,
meta/plan.md or this file.
