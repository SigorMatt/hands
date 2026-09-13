# CHECKPOINT

Mission: 11 (meta/BUILDER-11-PROMPT.md, DESIGN v3.10 §27) — BLOCKED ON U6
ACCEPTANCE (H-022)
Unit in progress: none. U0–U7 `[x]` in meta/plan.md; U6's `kit check .` exit 0
is open.
Base: 0fef436.
Done: U0 e8daca8 (1550 passed); U1 efe4d56 (1573); U2 525dc66 (1588);
U3 d4bea98 (1613); U4 d491f6b (1699); U5 c1d8ed5 (1717); U6 089e72f (1732);
U7 is the commit that carries this line (meta only).
Open: `hands kit check .` on this repository exits 1 (H-022, filed in 089e72f):
the directory holds `.git/` and eleven briefs, and the kickoff names
BUILDER-12, which does not exist. A kit of meta/BUILDER-11-PROMPT.md alone
with `--repo .` passes 6 of 6. Not retried: the same rules stop at the same
memo. Needs the architect to say what the acceptance line means.
Report: meta/FINAL-REPORT-11.md (what changed, what tests prove, NOT PROVEN,
`## Review items`, acceptance, for the architect).
Review 10 closed: blocker 1 (U2), should-fix 1, 3, 4, 5, 6 (U1), 2 (U3), 7 (U0).
Findings: H-018..H-021 resolved by v3.10 (U0 status lines); H-022 open;
H-001 and H-009 open.
Standing constraints: one foreground sub-agent per product unit, commit and
push every unit, ./scripts/check green three consecutive runs before each
commit, explicit paths only in `git add` (never `-A`), reports drafted under
meta/drafts/, DESIGN.md is not edited by builders (file a finding), sub-agents
do not edit meta/plan.md or this file.
