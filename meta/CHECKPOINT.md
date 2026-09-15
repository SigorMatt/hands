# CHECKPOINT

Mission: 14 (meta/BUILDER-14-PROMPT.md, DESIGN v3.13 §30 with §11, §12, §28,
§29) — the guard's language, review 13.
Base: c958a62 (`plan: mission 14 kit (DESIGN v3.13)`).
Unit in progress: none (U0 done in this commit; U1 next).
Intent: meta/plan.md and this file; H-026 filed (the guard's parser replaced
by the §30 language, review 11–13 history); FINAL-REPORT-13's REVIEW-11
blocker 1 row corrected by an appended dated line; REVIEW-13 should-fix 8:
`killed` wins over `limited` when both apply in one job, pinned in
docs/INTEGRATION.md and by a test that goes red when the runner's cancel and
limit checks are swapped.
Done means: those files changed; a sub-agent writes the should-fix 8 test
(and any doc/runner change) without committing; ./scripts/check green 3/3;
one `plan:` commit listing every file; pushed.
Done so far: U0 (this commit; 2284 tests). Next: U1 The guard's language.
Standing constraints: one foreground sub-agent per product unit, commit and
push every unit, ./scripts/check green three consecutive runs before each
commit, explicit paths only in `git add` (never `-A`), reports drafted under
meta/drafts/, DESIGN.md is not edited by builders (file a finding), sub-agents
do not edit meta/plan.md or this file, retry a failed unit once then `[b]`.
