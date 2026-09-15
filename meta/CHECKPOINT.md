# CHECKPOINT

Mission: 13 (meta/BUILDER-13-PROMPT.md, DESIGN v3.12 §29 with §5, §12, §13,
§26, §28) — FINISHED.
Base: 723dbeb (`plan: mission 13 kit (DESIGN v3.12)`).
Unit in progress: none. U0–U8 `[x]` in meta/plan.md.
Done: U0 b79d908 (1994); U1 eccc3a1 (2092); U2 ea7f1bc (2098); U3 126d4ff
(2196); U4 38022f2 (2235); U5 9ca89cf (2272); U6 8f79f98 (2283); U7 0a14085
(2283); U8 is the commit that carries this line (meta only).
Report: meta/FINAL-REPORT-13.md (what changed, what tests prove, NOT PROVEN,
`## Review items`, acceptance, for the architect).
Review 12 closed: blockers 1 (U1), 2 (U3), 3 (U0, U2); should-fix 1, 6, 7
(U3), 2 (U1), 3, 4, 5 (U4), 8 (U0), 9 (U5). Review 11 blockers 1 (U1) and 3
(U2) closed.
Findings: H-023 resolved (U2); H-024 resolved by v3.12 (U0, code U1); H-025
resolved by v3.12 option (b) (U0, code U2); H-001 and H-009 open.
Next: PLAYBOOK.toml names meta/BUILDER-14-PROMPT.md, which the architect ships.
Standing constraints: one foreground sub-agent per product unit, commit and
push every unit, ./scripts/check green three consecutive runs before each
commit, explicit paths only in `git add` (never `-A`), reports drafted under
meta/drafts/, DESIGN.md is not edited by builders (file a finding), sub-agents
do not edit meta/plan.md or this file, retry a failed unit once then `[b]`.
