# CHECKPOINT

Mission: 17 (meta/BUILDER-17-PROMPT.md, DESIGN v3.16 §33 with §8, §11, §26,
§31, §32; meta/reviews/REVIEW-16.md).
Base: 0b8447e (`plan: mission 17 kit (DESIGN v3.16)`), green (3743 passed).

Unit in progress: U0 Plan and bookkeeping (`plan:` commit).
Intent: meta/plan.md and this file; H-035 (daemon runs the check it approves
on; REVIEW-16 blocker 1) and H-036 (zip names; blocker 2) filed — H-034 is
already taken; FINAL-REPORT-16's review-items row for REVIEW-15 blocker 3 and
§3.2 corrected by appended dated lines; should-fix 8 (templates' task_killed
messages, docs/PLAYBOOK.md:585, the stale test docstring, H-034's "byte for
byte" overstatement by an appended line).
Done means: those files changed, append-only in reports and findings,
./scripts/check green 3/3, one `plan:` commit listing every file, pushed.

Standing constraints: one foreground sub-agent per unit, commit and push every
unit, ./scripts/check green three consecutive runs before each commit, explicit
paths only in `git add` (never `-A`), reports drafted under meta/drafts/,
DESIGN.md is not edited by builders (file a finding), sub-agents do not edit
meta/plan.md or this file, retry a failed unit once then `[b]`.
