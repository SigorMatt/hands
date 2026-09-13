# CHECKPOINT

Mission: 10 (meta/BUILDER-10-PROMPT.md, DESIGN v3.9 §26) — BLOCKED ON U4
Unit in progress: none. U0–U3, U5–U7 `[x]` in meta/plan.md; U4 `[b]`.
Base: 61e1486, green (1435 passed).
Done: U0 cbb8fc8 (1435 passed); U1 17ba97e (1443); U2 067b8fd (1461);
U3 6852751 (1501); U5 9e962a4 (1538); U6 7c5e854 (1549); U7 is the commit that
carries this line (meta only).
Blocked: U4 on DESIGN (H-020, memo 9f7effd): no transcript records a pid; the
pid is in ~/.claude/sessions/<pid>.json, which §26 does not name. Not retried.
Needs a DESIGN revision, then a unit; `hands who` still matches by directory.
Tip for the gate: 7c5e854, `./scripts/check` green three consecutive runs before
U7's commit, 1549 passed.
Report: meta/FINAL-REPORT-10.md (NOT PROVEN in §3, `## Review items`,
acceptance in §4, the architect's list in §5).
Review 9 closed: should-fix 1 (with limits), 2, 3 (symlink case open), 4.
Findings: H-018 filed and its gaps closed by U1/U2; H-019 filed (templates
reconciled by U5); H-020 open (blocks U4); H-021 open (kit check checks
builder.done verdict rules only). H-001 and H-009 open.
Deviation: REVIEW-9 SF2's code half went into U1 (H-018 gap 3).
Standing constraints: one foreground sub-agent per product unit, commit and
push every unit, ./scripts/check green three consecutive runs before each
commit, explicit paths only in `git add` (never `-A`), reports drafted under
meta/drafts/, DESIGN.md is not edited by builders (file a finding), sub-agents
do not edit meta/plan.md or this file.
