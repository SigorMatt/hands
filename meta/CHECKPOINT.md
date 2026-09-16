# CHECKPOINT

Mission: 15 (meta/BUILDER-15-PROMPT.md, DESIGN v3.14 §31 with §8, §10, §11,
§12, §26, §27, §30) — IN PROGRESS.
Base: 1f8141c (`plan: mission 15 kit (DESIGN v3.14, architect kit)`).
Unit in progress: none (U0 is the commit that carries this line).
Intent: write meta/plan.md and this file; file H-028 (the guard's command
table, review 14 blocker 1) and H-029 (the architect role, §31); close review
14 should-fix 7 — `hands doctor` warns when `[series] kickoff` names a brief
the repository lacks.
Done means: plan and checkpoint written; both findings appended to
meta/findings/FINDINGS.md; a failing test for the doctor warning written first
and then green; `./scripts/check` green three consecutive runs; one `plan:`
commit carrying exactly those files plus the doctor change, pushed.
Note on numbering: the brief names H-027 and H-028; H-027 is taken (mission 14
U5, open), so the ledger's next free numbers H-028 and H-029 are used.
Done: U0 (this `plan:` commit) — plan, checkpoint, H-028 and H-029; doctor's
`go` row warns on a kickoff naming an absent file (review 14 should-fix 7);
`spool.ORIGINS` gains `architect` (DESIGN v3.14 §6 already lists it and the
base commit was red without it); green 3/3 (2605 tests).
Findings: H-027 open (DESIGN §12 rule 6 and §14's layout line, which builders
may not edit); H-001 and H-009 open.
Next: U1, the guard's command table (§31, review 14 blocker 1).
Standing constraints: one foreground sub-agent per product unit, commit and
push every unit, ./scripts/check green three consecutive runs before each
commit, explicit paths only in `git add` (never `-A`), reports drafted under
meta/drafts/, DESIGN.md is not edited by builders (file a finding), sub-agents
do not edit meta/plan.md or this file, retry a failed unit once then `[b]`.
