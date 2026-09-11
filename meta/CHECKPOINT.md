# CHECKPOINT

Mission: 2 (meta/BUILDER-2-PROMPT.md) — IN PROGRESS
Unit in progress: U5 `hands notify --test` (DESIGN §4, §11)
Intent: `hands notify --test "<message>"` sends one message to the
configured topic through the real transport and prints the HTTP status —
the first real proof of delivery. It refuses when `ntfy_topic` is unset.
Done means: the transport is mocked in tests (no HTTP request leaves this
machine), the command is listed in `hands --help`, the refusal is tested,
./scripts/check green, one commit, pushed.
Tip: 267ee01 + this meta commit; gate green (510 tests).
Done so far: U0, U3, U1, U2, U4. Remaining: U5, U6, U7, U8.
Standing constraints: one sub-agent per unit; commit and push every unit;
./scripts/check green before every commit; builders never edit DESIGN.md,
meta/plan.md or this file.
