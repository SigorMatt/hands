# CHECKPOINT

Mission: 2 (meta/BUILDER-2-PROMPT.md) — IN PROGRESS
Unit in progress: U1 Origin `limit` (H-004, DESIGN §6, §4)
Intent: `ORIGINS` gains `limit`; a limit resume is filed with
`origin = "limit"` instead of the least-wrong `playbook`; `hands jobs
--origin <o>` filters on it; the `resume` inbox event carries `origin`.
`resumed_from` keeps its present meaning and is unchanged.
Done means: a test that `jobs --origin` filters, and a test that a limit
resume's record has `origin == "limit"` and that its inbox `resume` event
carries the origin; ./scripts/check green; one commit; pushed.
Tip: 34b4ede + the meta commit after it; gate green (494 tests).
Standing constraints: one sub-agent per unit; commit and push every unit;
./scripts/check green before every commit; builders never edit DESIGN.md,
meta/plan.md or this file.
