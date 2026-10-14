# CHECKPOINT

Mission: 19 (meta/BUILDER-19-PROMPT.md, DESIGN v3.18 §35 with §26, §31;
meta/reviews/REVIEW-18.md). Direct: every unit commits and pushes to `main`.
Base: 21d62d9 (`plan: mission 19 kit (DESIGN v3.18)`).

Done: U0 (the `plan:` commit that carries this line) — gate passed: probe PR
SigorMatt/hands#1 opened 11:31:49Z, qodo-code-review[bot] first comment
11:32:18Z (29 s, on open); PR closed, `probe-qodo` deleted local and remote.

H-040 filed (the gate is run as `env -u HANDS_PROJECT -u HANDS_JOB
./scripts/check`; with them set, 12 test_kit tests fail). Green 3/3 (4030).

Unit in progress: none. Next: U1 doctor's `gh` row (§35).

Standing constraints: one foreground sub-agent per unit, commit and push every
unit (to `main`, this mission), ./scripts/check green three consecutive runs
before each commit (each a foreground call, 20-minute timeout), explicit
paths only in `git add` (never `-A`), reports drafted under meta/drafts/,
DESIGN.md is not edited by builders (file a finding), sub-agents do not edit
meta/plan.md or this file, retry a failed unit once then `[b]` (a blocked U0
ends the mission). No engine, guard, role or REVIEW-18 should-fix changes.
