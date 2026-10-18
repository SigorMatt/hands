# CHECKPOINT

Mission: 26 (meta/BUILDER-26-PROMPT.md, DESIGN v3.25 §42 with §27, §31,
§33, §36, §38; meta/reviews/REVIEW-25.md).
Branch: `mission-26`, from main 9877b57; every unit commits and pushes to
it; U5 opens the PR, reads the hosted review, fixes, returns the tree to main.

Done: U0 5c1c9c3 (`plan:`) — plan, checkpoint, H-070/H-071 (mission 27), H-072 (closed by U4); origin/mission-26 pushed; green 3/3 (4659).

Done: U1 b956e2a — phone `consult` + `hands consult` start an architect job of origin playbook via the engine; refusals titled consult; budget, un-pause, consult.sent/done fields, journal line; architect/CLAUDE.md rule 14 + rule 13 routes 4/5; handbook §16; also docs/INTEGRATION.md command list; green 3/3 (4738; one unrelated flake in test_operations staged '..' once, not reproduced). Not proven: refusal while architect queued, restart mid human consult.

Done: U2 d222109 — new src/hands/digest.py; `hands digest` (+--json) and phone `digest <secret>`; redact before cut; unloadable config by file only; down daemon; guard pin; OPERATIONS.md no-phone `digest` row (consult row left for U4); green 3/3 (4752).

Done: U3 592fc6e — kit.py recognises a decisions kit (6 of 6, plan-only apply prompt), 14 non-decisions variants judged as before; kit apply and phone kit file the apply; api kit_file refuses it; template §R owner-file sentence pinned; handbook §3, §4, §11; green 3/3 (4782).

Done: U4 79eb270 — handbook §10 row, §13, §14, §18, new §19 operator table (tests/test_operator_table.py, 41 tests); instruction opening, rules 3/9/12/14, rule 15 pinned to §42; OPERATIONS consult row; INTEGRATION H-072 (no CLI ceiling in 2.1.302); H-072 resolved-by-doc; green 3/3 (4823).

In progress: U5 final report, the PR and the hosted review. meta/FINAL-REPORT-26.md moved in (report: commit), then `gh pr create`, `hands hosted-review <pr>` in one-minute steps up to ten minutes, fixes by sub-agent within §42, the `## Hosted review` table + archive committed, tree back to main. Done means: PR open, table committed and pushed, tree on main.

Standing constraints: one foreground sub-agent per unit, commit and push every
unit to `mission-26`, ./scripts/check green three consecutive runs before each
commit (each a foreground call, 15-minute / 900000 ms timeout), explicit paths
only in `git add` (never `-A`), reports drafted under meta/drafts/, DESIGN.md
is not edited by builders (file a finding), sub-agents do not edit
meta/plan.md or this file, retry a failed unit once then `[b]`; a `refused:`
report is not retried. Not touched: the harness seam, review 25's should-fix
1-3, H-070/H-071 builds, a local-model harness, any M9 command, credential
profiles, the `builder.limited` rule; no host change.
