# CHECKPOINT

Mission: 27 (meta/BUILDER-27-PROMPT.md, DESIGN v3.26 §43 with §10, §12,
§14, §23, §24, §32, §33, §34, §36, §39, §41, §42; meta/reviews/REVIEW-26.md,
meta/reviews/REVIEW-25.md should-fix 1).
Branch: `mission-27`, from main 1b822a5; every unit commits and pushes to
it; U7 opens the PR, reads the hosted review, fixes, returns the tree to main.

Done: U0 (the `plan:` commit) — plan, branch, findings (H-074, H-075, H-076 filed;
H-070/H-071 "decided (DESIGN §42, §43), scheduled for U4"; H-073 "decided
(DESIGN §43), scheduled for U2"), FINAL-REPORT-25 correction line. Pushed;
`origin/mission-27` exists.

Next: U1 — the base (DESIGN copies, H-076, review 26's untested refusals).

Base at U0's start (red, expected): three gate runs at 1b822a5, each
`1 failed, 4833 passed`, the one red test
`tests/test_playbook.py::test_the_fixture_is_section_10s_example_verbatim` —
the kit's DESIGN edit to §10's example (`monitor.task_killed` → notify)
while `tests/fixtures/playbook_example.toml` still carries the old rule.
U0 commits only meta/ with it red; U1 turns it green. No other test red in
any of the three runs (H-076 evidence: none of the intermittent tests
failed).

Standing constraints: one foreground sub-agent per unit, commit and push every
unit to `mission-27`, ./scripts/check green three consecutive runs before each
commit (each a foreground call, 15-minute / 900000 ms timeout, written
`./scripts/check; echo "check-exit=$?"`), explicit paths only in `git add`
(never `-A`), reports drafted under meta/drafts/, DESIGN.md is not edited by
builders (file a finding), sub-agents do not edit meta/plan.md or this file,
retry a failed unit once then `[b]`; a `refused:` report is not retried. Not
touched: the harness seam, review 25's should-fix 2 and 3, a local-model
harness, any M9 command, credential profiles, docs/ARCHITECT-INSTRUCTION.md,
this repository's PLAYBOOK.toml; no host change.
