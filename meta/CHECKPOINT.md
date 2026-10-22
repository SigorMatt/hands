# CHECKPOINT

Mission: 30 (meta/BUILDER-30-PROMPT.md, DESIGN v3.29 §46 with §43, §45,
§35; meta/reviews/REVIEW-29.md; FINDINGS H-081..H-085).
Branch: `mission-30`, from main e213c2e; every unit commits and pushes to
it; U4 opens the PR, waits for its `check` check and the hosted review,
fixes, returns the tree to main.

Done: U0 (`plan:`) — plan, branch, findings (H-081/H-082/H-083
decided and scheduled; H-084, H-085 filed). Green 3/3 (5366). Pushed;
`origin/mission-30` exists.

Done: U1 16723ad — PULL_REQUEST_APPLY case (b) "neither `main` nor a
`kit/` one" (word-for-word test built from §45 with §46's block); config
`_choice` refuses any non-value of any type naming both (repr of the
value); handbook §3; H-082 resolved; green 3/3 (5370). Not proven: a real
builder on `main` taking (c).

Done: U2 8b3aa60 — spool.is_plan_file / stored_kit_non_plan /
stored_kit_files; playbook.plan_hold_reason (§43's wins; named_paths by an
import inside the engine method); kit.send_named_paths, WARN owner:,
owner_warnings; CI hold removed; architect rules 3/8; handbook §3/§12/§19;
PLAYBOOK.md, INTEGRATION.md, templates; tests/test_plan_files.py added;
harness playbookless_kit no longer carries meta/REVIEW-PROTOCOL.md; H-083
resolved; green 3/3 (5390). Not proven: daemon end to end with a held
non-plan kit; a builder cwd below the repo root.

Done: U3 2a2442e — both protocols (moved-branch blocker and refused-push
steps, --match-head-commit merge, not merged with or without the rule,
failure paths to the branch via ls-remote, Direct brief nowhere, `## A
defect (DESIGN §46)`, `## The end (every shape)` on main); brief template
sentence; handbook §9/§19; tests/test_docs_46.py added; H-081, H-084,
H-085 resolved; green 3/3 (5459). Not proven: a real reviewer following
it; gh refusing a moved head. Left unchanged (outside §46's list):
architect/CLAUDE.md rule 1, handbook §7's blocker list.

Done: U4 b1ad99d (report), PR #10; check passed at b1ad99d; hosted fetch
1: 4 findings — 1, 3 fixed in 676aa1b (protocol: check after the pull,
HEAD = reviewed; not-merged push recovery), 4 fixed in 5a3a5a4
(casefolded named exclusion), 2 dismissed (orchestrator's own files);
fetch 2: 1 of 4 open (the dismissed one); check passed at 5a3a5a4
(github-actions 15368); H-086 filed (not-merged on main, both refusals);
green 3/3 (5475); (this commit) the Hosted review and CI sections +
archive PR-10/1..2.
Mission 30 — FINISHED after this push and its check; tree returns to main.

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
