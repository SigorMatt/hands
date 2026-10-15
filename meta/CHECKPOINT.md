# CHECKPOINT

Mission: 21 (meta/BUILDER-21-PROMPT.md, DESIGN v3.20 §37 with §6, §32,
§35, §36; meta/reviews/REVIEW-20.md). Closer: every unit commits and pushes
to `mission-20` (PR #2 open). Base: 1c68883, merged into mission-20 at 5dfab55.

Unit in progress: U0 Plan, the branch and the findings (`plan:`).
Done means: H-046..H-048 filed open for mission 22; `git log --oneline -3`
on mission-20 shows the merge of main and this commit; tree clean; pushed.

Standing constraints: one foreground sub-agent per unit, commit and push every
unit to `mission-20`, ./scripts/check green three consecutive runs before each
commit (each a foreground call, 20-minute timeout), explicit paths only in
`git add` (never `-A`), reports drafted under meta/drafts/, DESIGN.md is not
edited by builders (file a finding), sub-agents do not edit meta/plan.md or
this file, retry a failed unit once then `[b]`. No onboarding, `hands project
add`, handbook sections, handswho or notification docs (mission 22). The last
unit opens no PR; tree returns to main at the end.
