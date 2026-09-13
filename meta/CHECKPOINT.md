# CHECKPOINT

Mission: 8 (meta/BUILDER-8-PROMPT.md, DESIGN v3.7 §24) — FINISHED
Unit in progress: none. U0..U8 all `[x]` in meta/plan.md.
Base: da8df27, green (1235 passed).
Done: U0 9ae7975 (1238 passed); U1 df8c1fd (1285); U2 68e1048 (1300);
U3 4782a4a (1323); U4 7183478 (1367); U5 6fcd7d7 (1380); U6 a93e3a7 (1416);
U7 c41473c (1424); U8 is the commit that carries this line (meta only).
Tip for the gate: c41473c — `./scripts/check` green three consecutive runs
before U8's commit, 1424 passed.
Report: meta/FINAL-REPORT-8.md (NOT PROVEN in §3, `## Review items`,
acceptance in §4, the architect's list in §5).
Review 7 closed (blocker 1; should-fix 1 by DESIGN v3.7; 2–4); REVIEW-3
should-fix 3, 6, 7 closed.
Findings: H-015 filed (decided; closed on disk by U4); H-016 open for the
architect (§10's example lacks the two stop rules). H-001 and H-009 open.
Standing constraints: one foreground sub-agent per unit, commit and push
every unit, ./scripts/check green three consecutive runs before each commit,
explicit paths only in `git add` (never `-A`), reports drafted under
meta/drafts/, DESIGN.md is not edited by builders (file a finding),
sub-agents do not edit meta/plan.md or this file.
