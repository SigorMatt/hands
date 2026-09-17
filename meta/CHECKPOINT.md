# CHECKPOINT

Mission: 18 (meta/BUILDER-18-PROMPT.md, DESIGN v3.17 §34 with §11, §26, §32,
§33; meta/reviews/REVIEW-17.md).
Base: fc376ab (`plan: mission 18 kit (DESIGN v3.17)`).

Unit in progress: U0 Plan and bookkeeping.
Intent: meta/plan.md and this file for mission 18; H-038 filed (H-037 is
taken) for REVIEW-17 blocker 1 with should-fix 6; FINAL-REPORT-17 §2's "both
denied" corrected by an appended dated block.
Done means: `plan:` commit carrying meta/plan.md, meta/CHECKPOINT.md,
meta/findings/FINDINGS.md, meta/FINAL-REPORT-17.md; ./scripts/check green
three consecutive runs; pushed.

Standing constraints: one foreground sub-agent per unit, commit and push every
unit, ./scripts/check green three consecutive runs before each commit, explicit
paths only in `git add` (never `-A`), reports drafted under meta/drafts/,
DESIGN.md is not edited by builders (file a finding), sub-agents do not edit
meta/plan.md or this file, retry a failed unit once then `[b]`. meta/plan.md,
meta/CHECKPOINT.md and meta/journal.md are updated between units and carried
by the U6 commit.
