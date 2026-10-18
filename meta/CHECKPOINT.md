# CHECKPOINT

Mission: 26 (meta/BUILDER-26-PROMPT.md, DESIGN v3.25 §42 with §27, §31,
§33, §36, §38; meta/reviews/REVIEW-25.md).
Branch: `mission-26`, from main 9877b57; every unit commits and pushes to
it; U5 opens the PR, reads the hosted review, fixes, returns the tree to main.

In progress: U0 (`plan:`) — meta/plan.md, this file, meta/journal.md,
meta/findings/FINDINGS.md (H-070, H-071 decided, scheduled for mission 27;
H-072 decided, closed by U4). Done means: entries exist, commit pushed,
`git branch -r` shows origin/mission-26.

Standing constraints: one foreground sub-agent per unit, commit and push every
unit to `mission-26`, ./scripts/check green three consecutive runs before each
commit (each a foreground call, 15-minute / 900000 ms timeout), explicit paths
only in `git add` (never `-A`), reports drafted under meta/drafts/, DESIGN.md
is not edited by builders (file a finding), sub-agents do not edit
meta/plan.md or this file, retry a failed unit once then `[b]`; a `refused:`
report is not retried. Not touched: the harness seam, review 25's should-fix
1-3, H-070/H-071 builds, a local-model harness, any M9 command, credential
profiles, the `builder.limited` rule; no host change.
