# CHECKPOINT

Mission: 2 (meta/BUILDER-2-PROMPT.md) — IN PROGRESS
Unit in progress: U7 Retire bootstrap (DESIGN §15, §12, §14)
Intent: delete `bootstrap/`; remove the bootstrap section and every
`dispatch.sh` mention from `driver/CLAUDE.md`, `driver/README.md`,
`README.md`, `docs/INTEGRATION.md`; `driver/settings.json` drops the
`./dispatch.sh` allow rule; `driver/hooks/bash_guard.py` drops it from
`ALLOWED_FIRST_WORDS` and from its self-test. DESIGN §15 stays as history
and is not edited.
Done means: `grep -rn dispatch.sh` over the repo returns nothing outside
meta/ (ledger and reports are history); the bash guard self-test is green;
./scripts/check green; one commit; pushed.
Tip: bde33fe + this meta commit; gate green (519 tests).
Done so far: U0, U3, U1, U2, U4, U5, U6. Remaining: U7, U8.
Standing constraints: one sub-agent per unit; commit and push every unit;
./scripts/check green before every commit; builders never edit DESIGN.md,
meta/plan.md or this file.
