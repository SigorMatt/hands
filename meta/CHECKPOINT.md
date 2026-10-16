# CHECKPOINT

Mission: 24 (meta/BUILDER-24-PROMPT.md, DESIGN v3.23 §40 with §2, §23,
§33, §35, §38, §39; meta/reviews/REVIEW-23.md; docs/RELATED.md;
docs/QODO-EXTRACTION.md).
Branch: `mission-24` from main de407f2; every unit commits and pushes to
it; U10 opens the PR to main, reads the hosted review, fixes, and returns
the tree to main.

In progress: U0 (`plan:`) — plan, checkpoint, findings H-062..H-069 filed,
H-061/H-064/H-065 decided, H-051 Status corrected. Done means: committed and
pushed, `origin/mission-24` exists.

Standing constraints: one foreground sub-agent per unit, commit and push every
unit to `mission-24`, ./scripts/check green three consecutive runs before each
commit (each a foreground call, 20-minute timeout), explicit paths only in
`git add` (never `-A`), reports drafted under meta/drafts/, DESIGN.md is not
edited by builders (file a finding), sub-agents do not edit meta/plan.md or
this file, retry a failed unit once then `[b]`; `refused:` → `[b] refused`,
no retry. Not touched: the backend seam, credential profiles, the polish
round, any M9 command (missions 25, 26).
