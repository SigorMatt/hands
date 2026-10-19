# CHECKPOINT

Mission: 28 (meta/BUILDER-28-PROMPT.md, DESIGN v3.27 §44 with §6, §10,
§19, §31, §32, §33, §36, §38, §39, §43; meta/reviews/REVIEW-27.md;
FINDINGS H-077, H-078).
Branch: `mission-28`, from main b943019; every unit commits and pushes to
it; U5 opens the PR, reads the hosted review, fixes, returns the tree to main.

Done: U0 (`plan:`) — plan, branch, findings (H-078 filed "decided (DESIGN
§44), scheduled for U1 and U2"; H-077 "decided (DESIGN §44 ...), scheduled
for U4"). Green 3/3 (5056). Pushed; `origin/mission-28` exists.

Next: U1 — a human pause holds the next step.

Standing constraints: one foreground sub-agent per unit, commit and push every
unit to `mission-28`, ./scripts/check green three consecutive runs before each
commit (each a foreground call, 15-minute / 900000 ms timeout, written
`./scripts/check; echo "check-exit=$?"`), explicit paths only in `git add`
(never `-A`), reports drafted under meta/drafts/, DESIGN.md is not edited by
builders (file a finding), sub-agents do not edit meta/plan.md or this file,
retry a failed unit once then `[b]`; a `refused:` report is not retried. Not
touched: the pull-request gate, the harness seam, review 25's should-fix 2
and 3, a local-model harness, any M9 command, credential profiles,
docs/ARCHITECT-INSTRUCTION.md, this repository's PLAYBOOK.toml; no host
change.
