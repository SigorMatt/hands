# plan — mission 26 (the project separation)

Source: meta/BUILDER-26-PROMPT.md, DESIGN v3.25 §42 (with §27, §31, §33,
§36, §38), meta/reviews/REVIEW-25.md. Branch `mission-26`, created from
`main` (9877b57, `plan: mission 26 kit (DESIGN v3.25, the project
separation)`). Units run in order; each ends with a commit and a push to
`mission-26`; the last unit opens the pull request, reads the hosted
review, and returns the tree to `main`. `[x]` = done and pushed, `[b]` =
blocked (two failures) or refused.

- [x] U0 Plan, branch and findings (`plan:`) — this file, meta/CHECKPOINT.md,
      meta/journal.md, meta/findings/FINDINGS.md (H-070, H-071, H-072) 5c1c9c3
- [x] U1 b956e2a `consult` from the phone and the laptop (§42; §31, §33, §38,
      H-058) — src/hands/phone.py, src/hands/api.py, src/hands/playbook.py,
      src/hands/daemon.py (if dispatch needs it), src/hands/cli.py,
      architect/CLAUDE.md, docs/ARCHITECT-HANDBOOK.md §16, README.md, tests
- [x] U2 d222109 `digest` (§42) — src/hands/digest.py, src/hands/cli.py,
      src/hands/phone.py, README.md, tests
- [x] U3 592fc6e The decisions kit and the owner file on a resume (§42; route 4) —
      src/hands/kit.py, src/hands/api.py, templates/BUILDER-N-PROMPT.md,
      docs/ARCHITECT-HANDBOOK.md §3, §4, §11, tests
- [x] U4 79eb270 The handbook, the instruction and the runbooks (§42; H-072) —
      docs/ARCHITECT-HANDBOOK.md §10, §13, §14, §18, §19,
      docs/ARCHITECT-INSTRUCTION.md, docs/OPERATIONS.md,
      docs/INTEGRATION.md, README.md, tests; closes H-072
- [x] U5 ce2088b, 73aa1b3, a5ca441, (this commit) Final report, the pull request and the hosted review's findings —
      meta/FINAL-REPORT-26.md (drafted under meta/drafts/),
      meta/reviews/hosted/PR-<pr>/

Not in this mission (DESIGN §42): the harness seam, review 25's should-fix
1 and 3, H-070 and H-071 (mission 27); a local-model harness (mission 28);
any M9 command and review 25's should-fix 2 (mission 29); Claude
credential profiles and the `builder.limited` rule (the backlog); no host
change.

Dependencies. Units run in order (shared files: phone.py U1/U2, cli.py
U1/U2, api.py U1/U3, the handbook U1/U3/U4, README.md U1/U2/U4). U4's
operator table is written from the code at its commit, so after U1-U3.
U5 last.
