# CHECKPOINT

Mission: 2 (meta/BUILDER-2-PROMPT.md) — IN PROGRESS
Unit in progress: U4 Pause files an event (H-007, DESIGN §11, §10)
Intent: `hands pause` files a `stop` inbox event with reason `paused by
human` and notifies, like any stop; `hands resume` files `pipeline.resumed`.
`hands doctor`'s background-wake procedure offers `hands pause` as the
simplest event to fire, and keeps the gated send as the alternative.
Done means: a test that `hands wait --for stop` returns on `pause`, a test
for the `pipeline.resumed` event and the notification, a doctor test on the
procedure text, ./scripts/check green, one commit, pushed.
Tip: 8448b6f + this meta commit; gate green (501 tests).
Done so far: U0, U3, U1, U2. Remaining: U4, U5, U6, U7, U8.
Standing constraints: one sub-agent per unit; commit and push every unit;
./scripts/check green before every commit; builders never edit DESIGN.md,
meta/plan.md or this file.
