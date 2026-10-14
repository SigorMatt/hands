# CHECKPOINT

Mission: 20 (meta/BUILDER-20-PROMPT.md, DESIGN v3.19 §36 with §31, §33,
§34, §35; meta/reviews/REVIEW-19.md, meta/reviews/REVIEW-18.md).
Pull request: every unit commits and pushes to `mission-20`.
Base: 238a57b (`plan: mission 20 kit (DESIGN v3.19)`).

Unit in progress: U0 — plan, branch and findings (`plan:` commit).
Done means: meta/plan.md, this file, meta/journal.md and H-041..H-045 in
meta/findings/FINDINGS.md committed as `plan:` on `mission-20`;
`git branch -r` shows `origin/mission-20`.

Standing constraints: one foreground sub-agent per unit; commit and push
every unit to `mission-20`; ./scripts/check green three consecutive runs
before each commit (each a foreground call, 20-minute timeout; as `env -u
HANDS_PROJECT -u HANDS_JOB ./scripts/check` until U1 lands); explicit paths
only in `git add` (never `-A`); reports drafted under meta/drafts/;
DESIGN.md is not edited by builders (file a finding); sub-agents do not
edit meta/plan.md or this file; retry a failed unit once then `[b]`. Not
this mission: onboarding, `hands project add`, the instruction templates,
the handbook's new sections (mission 21).
