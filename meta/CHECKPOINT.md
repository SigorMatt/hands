# CHECKPOINT

Mission: 12 (meta/BUILDER-12-PROMPT.md, DESIGN v3.11 §28 with §8, §10, §12,
§27) — close review 11 (blockers 1–5, should-fix 1–9).
Base: bb9aab5 (`plan: mission 12 kit (DESIGN v3.11)`).
Unit in progress: U4 Sweep and who (§28; REVIEW-11 blockers 3, 4; H-023).
Intent: the post-exit sweep signals a group only when its leader is alive and
is the job's pid (with the recorded start time), or when every live member is
a descendant of the job by pid chain (or a member of the job's cgroup scope);
the `HANDS_JOB` environment mark alone never qualifies; `hands who`'s
directory fallback excludes the `sessionId` of every hands pid's
`~/.claude/sessions/<pid>.json` as well as the spool's session ids.
Done means: tests through `_sweep`/`_kill_group` — a leaderless marked group
left alone, a descendant group killed; the reviewer's who probe (job pid with
a sessions file, spool record without `session_id`, human with none) shows no
job transcript on the human's line; ./scripts/check green 3/3; one commit
listing every file, naming H-023; pushed.
Done: U0 5ea7b9d (1733 passed); U1 3966f9b (1882); U2 e642552 (1916);
U3 043413d (1980).
Findings: H-022 resolved by v3.11 (U0); H-023 open (code U4); H-024 open (U1's
residual-character reading); H-001 and H-009 open.
Standing constraints: one foreground sub-agent per product unit, commit and
push every unit, ./scripts/check green three consecutive runs before each
commit, explicit paths only in `git add` (never `-A`), reports drafted under
meta/drafts/, DESIGN.md is not edited by builders (file a finding), sub-agents
do not edit meta/plan.md or this file, retry a failed unit once then `[b]`.
