# CHECKPOINT

Mission: 11 (meta/BUILDER-11-PROMPT.md, DESIGN v3.10 §27)
Unit in progress: U4 The driver role (§8, §27).
Base: 0fef436. Done: U0 e8daca8 (1550); U1 efe4d56 (1573); U2 525dc66 (1588);
U3 d4bea98 (1613, green 3/3).
Intent: `[roles.driver]` in config: cwd, `permission_flags` must be empty
(doctor refuses otherwise), `env` adds `HANDS_ROLE=driver`.
`driver/hooks/bash_guard.py` role mode when `HANDS_ROLE=driver`: read-only git;
`hands show|jobs|inbox|pipeline|status|tail|kit check`; `hands send` only with
`--context keep`; `hands resume`; everything else refused, including
`approve`, `deny`, `pause`, `go`, `put`, any `--context clear`.
`driver/CLAUDE.md` "As a role" section (started by handsd to resolve one
consultation; answer within authority or escalate; first line `VERDICT:
resolved …` | `VERDICT: escalate …`). `hands doctor` reports the role (cwd,
clone, guard mode).
Done means: guard tests for role mode (a table of allowed and refused
commands); doctor refusal test; `./scripts/check` green three consecutive
runs; one commit listing every file; pushed.
Standing constraints: one foreground sub-agent per product unit, commit and
push every unit, ./scripts/check green three consecutive runs before each
commit, explicit paths only in `git add` (never `-A`), reports drafted under
meta/drafts/, DESIGN.md is not edited by builders (file a finding), sub-agents
do not edit meta/plan.md or this file.
