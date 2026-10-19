# plan — mission 28 (a pause that holds the next step)

Source: meta/BUILDER-28-PROMPT.md, DESIGN v3.27 §44 (with §6, §10, §19,
§31, §32, §33, §36, §38, §39, §43), meta/reviews/REVIEW-27.md,
meta/findings/FINDINGS.md (H-077, H-078). Branch `mission-28`, created from
`main` (b943019, `plan: mission 28 kit (DESIGN v3.27, a pause that holds
the next step)`). Units run in order; each ends with a commit and a push to
`mission-28`; the last unit opens the pull request, reads the hosted
review, and returns the tree to `main`. `[x]` = done and pushed, `[b]` =
blocked (two failures) or refused.

- [x] U0 (this commit) Plan, branch and findings (`plan:`) — this file,
      meta/CHECKPOINT.md, meta/findings/FINDINGS.md (H-078 filed; H-077
      "decided (DESIGN §44 ...), scheduled for U4")
- [ ] U1 A human pause holds the next step (§44 rules 1, 2, 3, 5, 6; §6,
      §10, §19, §29, §31, §32, §33, §38; H-078) — src/hands/playbook.py,
      src/hands/api.py, src/hands/phone.py, src/hands/cli.py, tests
- [ ] U2 At rest, the documents and the table's titles (§44 rule 4,
      "Documentation", review 27 should-fix 3; §19) — src/hands/playbook.py
      (daemon.py / limits.py if the moment is decided there),
      docs/ARCHITECT-HANDBOOK.md §10, §14, §18, §19, docs/PLAYBOOK.md,
      docs/OPERATIONS.md, tests/test_operator_table.py, FINDINGS (H-078
      resolved), tests
- [ ] U3 Review 27's two code should-fix items (§44 items 1, 2; §43) —
      src/hands/daemon.py, src/hands/doctor.py, src/hands/runner.py (if a
      seam is needed), tests
- [ ] U4 H-077, ruled (§44; §26, §43) — src/hands/spool.py,
      src/hands/playbook.py, src/hands/kit.py, FINDINGS (H-077 resolved),
      tests
- [ ] U5 Final report, the pull request and the hosted review's findings —
      meta/FINAL-REPORT-28.md (drafted under meta/drafts/),
      meta/reviews/hosted/PR-<pr>/

Not in this mission (DESIGN §44): the pull-request gate (mission 29); the
harness seam and review 25's should-fix 3 (mission 30); a local-model
harness (mission 31); any M9 command and review 25's should-fix 2 (mission
32); Claude credential profiles (the backlog); no change to
docs/ARCHITECT-INSTRUCTION.md or this repository's PLAYBOOK.toml; no host
change.

Dependencies. Units run in order (shared files: playbook.py U1/U2/U4,
daemon.py U2/U3, FINDINGS U2/U4). U2's `at rest` builds on U1's human
pause state. U5 last.
