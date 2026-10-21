# CHECKPOINT

Mission: 30 (meta/BUILDER-30-PROMPT.md, DESIGN v3.29 §46 with §43, §45,
§35; meta/reviews/REVIEW-29.md; FINDINGS H-081..H-085).
Branch: `mission-30`, from main e213c2e; every unit commits and pushes to
it; U4 opens the PR, waits for its `check` check and the hosted review,
fixes, returns the tree to main.

Done: U0 (`plan:`) — plan, branch, findings (H-081/H-082/H-083
decided and scheduled; H-084, H-085 filed). Green 3/3 (5366). Pushed;
`origin/mission-30` exists.

Standing constraints: one foreground sub-agent per unit, commit and push every
unit to `mission-30` (never `main`), ./scripts/check green three consecutive
runs before each commit (each a foreground call, 15-minute / 900000 ms
timeout, written `./scripts/check; echo "check-exit=$?"`), explicit paths
only in `git add` (never `-A`), reports drafted under meta/drafts/, DESIGN.md
is not edited by builders (file a finding), sub-agents do not edit
meta/plan.md or this file, retry a failed unit once then `[b]`; a `refused:`
report is not retried. No write to GitHub beyond pushing `mission-30` (and
U4's PR). Not touched: the ruleset or any repository setting, the harness
seam, review 25's should-fix 2 and 3, a local-model harness, any M9 command,
credential profiles, docs/ARCHITECT-INSTRUCTION.md, this repository's
PLAYBOOK.toml; no host change.
