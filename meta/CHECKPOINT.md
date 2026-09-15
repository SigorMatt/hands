# CHECKPOINT

Mission: 12 (meta/BUILDER-12-PROMPT.md, DESIGN v3.11 §28 with §8, §10, §12,
§27) — close review 11 (blockers 1–5, should-fix 1–9).
Base: bb9aab5 (`plan: mission 12 kit (DESIGN v3.11)`).
Unit in progress: U0 Plan and bookkeeping (`plan:` commit).
Intent: meta/plan.md for mission 12; FINDINGS H-018..H-021 resolutions moved
into each finding's own section with status lines set in place (REVIEW-11
SF5); H-022 resolution (§28) appended to its section, status resolved; H-023
filed for U1-of-m11's sweep departure from §27 (blocker 3); REVIEW-11 SF4:
tests/test_docs.py pins INTEGRATION's `done` statement against each §6
`failure_reason` value (sub-agent).
Done means: those files changed, ./scripts/check green 3/3, one `plan:`
commit listing every file, pushed.
Done: none yet.
Findings: H-022 resolved by v3.11 (U0); H-023 filed (U0, code U4); H-001 and
H-009 open.
Standing constraints: one foreground sub-agent per product unit, commit and
push every unit, ./scripts/check green three consecutive runs before each
commit, explicit paths only in `git add` (never `-A`), reports drafted under
meta/drafts/, DESIGN.md is not edited by builders (file a finding), sub-agents
do not edit meta/plan.md or this file, retry a failed unit once then `[b]`.
