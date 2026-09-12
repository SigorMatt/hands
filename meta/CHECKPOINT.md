# CHECKPOINT

Mission: 8 (meta/BUILDER-8-PROMPT.md, DESIGN v3.7 §24)
Unit in progress: U0 Plan and corrections.
Intent: plan and checkpoint; H-015 records the phone channel decision (§24);
a test pins `hands show`'s `failure` line through `main([..., "show", <job>])`
on a failed job and on a done job (REVIEW-7 blocker 1).
Done means: one `plan:` commit carrying meta/plan.md, meta/CHECKPOINT.md,
meta/findings/FINDINGS.md and the test file(s), pushed; ./scripts/check green
three consecutive runs.
Base: da8df27, green (1235 passed).
Standing constraints: one foreground sub-agent per unit, commit and push
every unit, ./scripts/check green three consecutive runs before each commit,
explicit paths only in `git add` (never `-A`), reports drafted under
meta/drafts/, DESIGN.md is not edited by builders (file a finding),
sub-agents do not edit meta/plan.md or this file.
