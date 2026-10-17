# CHECKPOINT

Mission: 25 (meta/BUILDER-25-PROMPT.md, DESIGN v3.24 §41 with §39, §40;
meta/reviews/REVIEW-24.md; docs/HARNESS-PROBE.md).
Branch: `mission-24` (PR #5, open), main 20aac9f merged in at cc2a9e5;
every unit commits and pushes to it; U6 opens no PR, reads the hosted
review again, fixes, and returns the tree to main.

Done: U0 (`plan:`) — main merged at cc2a9e5, H-062 note; green 3/3 (4636).

Standing constraints: one foreground sub-agent per unit, commit and push every
unit to `mission-24`, ./scripts/check green three consecutive runs before each
commit (each a foreground call, 20-minute timeout), explicit paths only in
`git add` (never `-A`), reports drafted under meta/drafts/, DESIGN.md is not
edited by builders (file a finding), sub-agents do not edit meta/plan.md or
this file, retry a failed unit once then `[b]`. Not touched: the backend
seam, the credential profiles, the polish round, any M9 command (missions 26
and 27), no host change (AppArmor is the human's).
