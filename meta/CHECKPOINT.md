# CHECKPOINT

Mission: 13 (meta/BUILDER-13-PROMPT.md, DESIGN v3.12 §29 with §5, §12, §13,
§26, §28) — close review 12, the sweep (H-025 b), two projects on one laptop.
Base: 723dbeb (`plan: mission 13 kit (DESIGN v3.12)`).

Unit in progress: U2 The sweep after the reap (§29; H-025 option b; H-023;
REVIEW-12 blocker 3, REVIEW-11 blocker 3).
Intent: descent = session id equals the job's pid and start time precedes the
last observation of the job's pid alive, or cgroup scope membership; the
`HANDS_JOB` mark alone never qualifies; `runner.pipe_timeout_s` (default 10)
bounds the pipe read at job end; leftovers reported as
`monitor.orphan_processes` with `killed: false`; residual in
docs/INTEGRATION.md.
Done means: the three §24 orphan tests pass (detached, holding pipes,
cancelled job); a leaderless marked group with a foreign session is left
alone; job end completes within the timeout with an orphan holding the pipes;
./scripts/check 3/3; pushed.
Done: U0 b79d908 (1994); U1 eccc3a1 (2092).

Standing constraints: one foreground sub-agent per product unit, commit and
push every unit, ./scripts/check green three consecutive runs before each
commit, explicit paths only in `git add` (never `-A`), reports drafted under
meta/drafts/, DESIGN.md is not edited by builders (file a finding), sub-agents
do not edit meta/plan.md or this file, retry a failed unit once then `[b]`.
