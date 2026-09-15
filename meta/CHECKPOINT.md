# CHECKPOINT

Mission: 14 (meta/BUILDER-14-PROMPT.md, DESIGN v3.13 §30 with §11, §12, §28,
§29) — FINISHED.
Base: c958a62 (`plan: mission 14 kit (DESIGN v3.13)`).
Unit in progress: none. U0-U7 `[x]` in meta/plan.md.
Done: U0 f9e0729 (2284); U1 9a5bc75 (2437); U2 e79e770 (2524); U3 599b993
(2569); U4 2ad4356 (2588); U5 104666d (2597); U6 fa8fbae (2597); U7 is the
commit that carries this line (meta only), green 3/3 (2597).
Report: meta/FINAL-REPORT-14.md (what changed, what tests prove, NOT PROVEN,
`## Review items`, acceptance, for the architect).
Review 13 closed: blockers 1 (U1), 2 and 3 (U2), 4 (U3); should-fix 1 (U1),
2-5 (U4), 6 (U3), 7 (U5), 8 (U0). REVIEW-11 blocker 1 closed by U1's
language; FINAL-REPORT-13's row for it corrected by U0.
Findings: H-026 resolved by v3.13 (code U1); H-027 open (DESIGN §12 rule 6
and §14's `systemd/handsd.service` line, which builders may not edit); H-001
and H-009 open.
Next: PLAYBOOK.toml names meta/BUILDER-15-PROMPT.md, which the architect ships.
Standing constraints: one foreground sub-agent per product unit, commit and
push every unit, ./scripts/check green three consecutive runs before each
commit, explicit paths only in `git add` (never `-A`), reports drafted under
meta/drafts/, DESIGN.md is not edited by builders (file a finding), sub-agents
do not edit meta/plan.md or this file, retry a failed unit once then `[b]`.
