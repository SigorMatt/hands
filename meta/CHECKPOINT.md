# CHECKPOINT

Mission: 8 (meta/BUILDER-8-PROMPT.md, DESIGN v3.7 §24)
Done: U0 9ae7975 (1238 passed).
Unit in progress: U1 Review 7 should-fix 2, 3, 4 (§6, §24).
Intent: the terminating-line matcher is anchored to the harness's exact
message (line start, the `s;` unit, the `Set
CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS` tail) and never overrides a job with a
`success` result, `num_turns` and exit 0; REVIEW-7's two over-match lines are
pinned as negatives. The doc sweep reads every tracked file except binaries
(content, not suffix), excludes `meta/` history by path, includes live
instruction files under `meta/` (`BUILDER-*`, `REVIEW-PROTOCOL.md`,
`BACKLOG.md`, `ROADMAP.md`). Should-fix 3 is met by U0's `plan:` prefix.
Done means: one unit commit, pushed; tests prove the above; ./scripts/check
green three consecutive runs.
Base: da8df27, green (1235 passed).
Standing constraints: one foreground sub-agent per unit, commit and push
every unit, ./scripts/check green three consecutive runs before each commit,
explicit paths only in `git add` (never `-A`), reports drafted under
meta/drafts/, DESIGN.md is not edited by builders (file a finding),
sub-agents do not edit meta/plan.md or this file.
