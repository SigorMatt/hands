# CHECKPOINT

Mission: 23 (meta/BUILDER-23-PROMPT.md, DESIGN v3.22 §39 with §24, §27,
§31, §35, §38; meta/reviews/REVIEW-22.md; docs/QODO-EXTRACTION.md).
Branch: `mission-23` from main 23eff6c; every unit commits and pushes to
it; U10 opens the PR to main, reads the hosted review, fixes, and returns
the tree to main.

Unit in progress: U0 Plan, branch and findings (`plan:`).
Intent: meta/plan.md, this file, journal line, FINDINGS (H-055..H-060
filed; H-051..H-054 decided per §39); branch pushed.
Done means: entries exist; `git branch -r` shows origin/mission-23;
./scripts/check green 3/3.

Standing constraints: one foreground sub-agent per unit, commit and push every
unit to `mission-23`, ./scripts/check green three consecutive runs before each
commit (each a foreground call, 20-minute timeout), explicit paths only in
`git add` (never `-A`), reports drafted under meta/drafts/, DESIGN.md is not
edited by builders (file a finding), sub-agents do not edit meta/plan.md or
this file, retry a failed unit once then `[b]`. Not touched: the backend
seam, the polish round, any M8 roadmap work (mission 24).
