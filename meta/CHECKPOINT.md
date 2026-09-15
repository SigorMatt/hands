# CHECKPOINT

Mission: 13 (meta/BUILDER-13-PROMPT.md, DESIGN v3.12 §29 with §5, §12, §13,
§26, §28) — close review 12, the sweep (H-025 b), two projects on one laptop.
Base: 723dbeb (`plan: mission 13 kit (DESIGN v3.12)`).

Unit in progress: U1 The guard: comments, the reading, the clone pin (§29;
REVIEW-12 blocker 1, should-fix 2; H-024).
Intent: refuse any `#` outside quotes in both modes naming the position;
H-024's expansion-position reading exactly as §29 states it; role-mode
`git -C` must equal `HANDS_CLONE`; every review 12 blocker-1 probe and every
review 11 probe asserted blocked in both modes; allowed tables stay allowed.
Done means: tests green, ./scripts/check 3/3, commit body lists the probes
blocked only after this change (checked against the parent hook), pushed.
Done: U0 `plan:` commit (1994 passed, 3/3).

Standing constraints: one foreground sub-agent per product unit, commit and
push every unit, ./scripts/check green three consecutive runs before each
commit, explicit paths only in `git add` (never `-A`), reports drafted under
meta/drafts/, DESIGN.md is not edited by builders (file a finding), sub-agents
do not edit meta/plan.md or this file, retry a failed unit once then `[b]`.
