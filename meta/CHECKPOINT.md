# CHECKPOINT

Mission: 29 (meta/BUILDER-29-PROMPT.md, DESIGN v3.28 §45 with §6, §8, §10,
§13, §27, §31, §32, §35, §36, §39, §43, §44; meta/reviews/REVIEW-28.md;
FINDINGS H-079, H-080; docs/PR-CI-GATE.md).
Branch: `mission-29`, from main f7d61c8; every unit commits and pushes to
it; U7 opens the PR, waits for its `check` check and the hosted review,
fixes, returns the tree to main.

Done: U0 (`plan:`) — plan, branch, findings (H-079 "decided (DESIGN §45
...), scheduled for U6"; H-080 "decided (DESIGN §45 ...), scheduled for
U4"). Green 3/3 (5137). Pushed; `origin/mission-29` exists.

Next: U1 CI on GitHub's runner.

Standing constraints: one foreground sub-agent per unit, commit and push every
unit to `mission-29` (never `main`), ./scripts/check green three consecutive
runs before each commit (each a foreground call, 15-minute / 900000 ms
timeout, written `./scripts/check; echo "check-exit=$?"`), explicit paths
only in `git add` (never `-A`), reports drafted under meta/drafts/, DESIGN.md
is not edited by builders (file a finding), sub-agents do not edit
meta/plan.md or this file, retry a failed unit once then `[b]`; a `refused:`
report is not retried. No write to GitHub beyond pushing `mission-29` (and
U7's PR). Not touched: the ruleset or any repository setting, the harness
seam, review 25's should-fix 2 and 3, a local-model harness, any M9 command,
credential profiles, docs/ARCHITECT-INSTRUCTION.md, docs/PR-CI-GATE.md, this
repository's PLAYBOOK.toml; no host change.
