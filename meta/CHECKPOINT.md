# CHECKPOINT

Mission: 16 (meta/BUILDER-16-PROMPT.md, DESIGN v3.15 §32 with §6, §8, §12,
§30, §31).
Base: 31789c6 (`plan: mission 16 kit (DESIGN v3.15)`).
Unit in progress: U0 Plan and bookkeeping (`plan:` commit) — committing.
Base was red (5 failures from the kit and U0's H-030 status line); a sub-agent
fixed four tests and docs/INTEGRATION.md without product code, folded into U0;
green 3/3 (3126 tests) before the commit.
Intent: meta/plan.md and this file for mission 16; H-033 filed (the guard's
language finished, review 15 blocker 1, reviews 11–15 in five lines); §32's
resolutions appended to H-030, H-031, H-032 with status lines set;
FINAL-REPORT-15 §3.1's claims about the guard and `unzip` corrected by
appended dated lines.
Done means: those files committed as one `plan:` commit whose body lists every
file, pushed, `./scripts/check` green three consecutive runs first.
Standing constraints: one foreground sub-agent per product unit, commit and
push every unit, ./scripts/check green three consecutive runs before each
commit, explicit paths only in `git add` (never `-A`), reports drafted under
meta/drafts/, DESIGN.md is not edited by builders (file a finding), sub-agents
do not edit meta/plan.md or this file, retry a failed unit once then `[b]`.
