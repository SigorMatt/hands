# CHECKPOINT

Mission: 22 (meta/BUILDER-22-PROMPT.md, DESIGN v3.21 §38 with §26, §31,
§33, §36, §37; meta/reviews/REVIEW-21.md). Branch: `mission-22` from main
7ddc0e8; every unit commits and pushes to it; U12 opens the PR to main.

Unit in progress: U0 Plan, branch and findings (`plan:` commit).
Intent: meta/plan.md, this file, journal line; H-049, H-050 filed;
H-037, H-046, H-047, H-048 set "in progress (mission 22, U<n>)".
Done means: the entries exist; committed and pushed; `git branch -r` shows
`origin/mission-22`.

Standing constraints: one foreground sub-agent per unit, commit and push every
unit to `mission-22`, ./scripts/check green three consecutive runs before each
commit (each a foreground call, 20-minute timeout), explicit paths only in
`git add` (never `-A`), reports drafted under meta/drafts/, DESIGN.md is not
edited by builders (file a finding), sub-agents do not edit meta/plan.md or
this file, retry a failed unit once then `[b]`. Not touched: the guard's
language, the review merge step, other agent backends.
