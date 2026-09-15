# CHECKPOINT

Mission: 12 (meta/BUILDER-12-PROMPT.md, DESIGN v3.11 §28 with §8, §10, §12,
§27) — BLOCKED ON U4 SWEEP HALF (H-025)
Base: bb9aab5 (`plan: mission 12 kit (DESIGN v3.11)`).
Unit in progress: none. U0–U3, U5, U6 `[x]` in meta/plan.md; U4 `[b]`.
Done: U0 5ea7b9d (1733 passed); U1 3966f9b (1882); U2 e642552 (1916);
U3 043413d (1980); U4 7f86406 who half (1982); U5 1250817 (1982); U6 is the
commit that carries this line (meta only).
Open: REVIEW-11 blocker 3. The post-exit sweep still kills a leaderless
group on the `HANDS_JOB` mark (H-023): §28's rule cannot hold after claude is
reaped (no live leader, no pid chain to the job's pid, no cgroup scope in
group mode), and refusing leaderless groups fails three §24 orphan tests, one
hanging on pipes. H-025 gives options a/b/c. Not retried: a design stop.
Report: meta/FINAL-REPORT-12.md (what changed, what tests prove, NOT PROVEN,
`## Review items`, acceptance, for the architect).
Review 11 closed: blockers 1 (U1), 2 (U3), 4 (U4), 5 (U0, U5); should-fix
1, 2, 3, 8 (U2), 4, 5 (U0), 6, 7, 9 (U3). Open: blocker 3 (H-025).
Findings: H-022 resolved by v3.11 (U0); H-023 open (waits on H-025); H-024
open (U1's residual-character reading); H-025 open; H-001 and H-009 open.
Standing constraints: one foreground sub-agent per product unit, commit and
push every unit, ./scripts/check green three consecutive runs before each
commit, explicit paths only in `git add` (never `-A`), reports drafted under
meta/drafts/, DESIGN.md is not edited by builders (file a finding), sub-agents
do not edit meta/plan.md or this file, retry a failed unit once then `[b]`.
