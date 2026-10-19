# plan — mission 27 (the separation follow-up: operations and safety fixes)

Source: meta/BUILDER-27-PROMPT.md, DESIGN v3.26 §43 (with §10, §12, §14,
§23, §24, §32, §33, §34, §36, §39, §41, §42), meta/reviews/REVIEW-26.md,
meta/reviews/REVIEW-25.md (should-fix 1). Branch `mission-27`, created from
`main` (1b822a5, `plan: mission 27 kit (DESIGN v3.26, the separation
follow-up)`). Units run in order; each ends with a commit and a push to
`mission-27`; the last unit opens the pull request, reads the hosted
review, and returns the tree to `main`. `[x]` = done and pushed, `[b]` =
blocked (two failures) or refused.

- [x] U0 b3e1e76 Plan, branch, findings and the report correction (`plan:`) — this
      file, meta/CHECKPOINT.md, meta/findings/FINDINGS.md (H-074, H-075,
      H-076 filed; H-070, H-071, H-073 statuses), meta/FINAL-REPORT-25.md
- [x] U1 f10c020 The base: the DESIGN copies, the intermittent test and review 26's
      untested refusals (§43; H-027, H-034, H-039, H-076) —
      tests/fixtures/playbook_example.toml, docs/PLAYBOOK.md,
      tests/test_playbook.py, tests/test_docs.py, tests/test_operations.py
      (+ product file of the race if any), the consult tests, FINDINGS
- [x] U2 32446f5 The owner file on every builder job (§43; §39, §41; H-073) —
      src/hands/daemon.py, src/hands/playbook.py, src/hands/limits.py,
      src/hands/api.py, src/hands/runner.py (if needed),
      docs/ARCHITECT-HANDBOOK.md §4, §14, §19, FINDINGS, tests
- [x] U3 3383ffe Background tasks off where the role's hook allows it (§43 rules
      1–5; H-074) — .claude/hooks/no_background.py, pyproject.toml,
      src/hands/runner.py, src/hands/doctor.py, src/hands/config.py (if
      needed), docs/INTEGRATION.md §21, README.md, CLAUDE.md (if needed),
      tests
- [x] U4 4130616 The protocols, the template and the guard's read set (§43 rule 6,
      H-070/H-071; H-074) — templates/REVIEW-PROTOCOL.md,
      meta/REVIEW-PROTOCOL.md, templates/BUILDER-N-PROMPT.md,
      docs/ARCHITECT-HANDBOOK.md §7, driver/hooks/bash_guard.py,
      architect/settings.json, architect/CLAUDE.md rule 10, FINDINGS, tests
- [x] U5 37bd194 A playbook change is the owner's (§43; H-075) —
      src/hands/playbook.py, src/hands/spool.py (if needed),
      src/hands/daemon.py, src/hands/kit.py, architect/CLAUDE.md rules 3
      and 8, docs/ARCHITECT-HANDBOOK.md §3, §6, §12,
      templates/PLAYBOOK-missions.toml, templates/BUILDER-N-PROMPT.md,
      FINDINGS, tests; never PLAYBOOK.toml
- [x] U6 38e44ee The operator table follows the code (§43; review 26 should-fix 2)
      — docs/ARCHITECT-HANDBOOK.md §19, tests/test_operator_table.py
- [x] U7 (this commit), later Final report, the pull request and the hosted review's findings —
      meta/FINAL-REPORT-27.md (drafted under meta/drafts/),
      meta/reviews/hosted/PR-<pr>/

Not in this mission (DESIGN §43): the harness seam and review 25's
should-fix 3 (mission 28); a local-model harness (mission 29); any M9
command and review 25's should-fix 2 (mission 30); Claude credential
profiles (the backlog); no change to docs/ARCHITECT-INSTRUCTION.md; no
host change.

Dependencies. Units run in order (shared files: playbook.py U2/U5,
daemon.py U2/U5, runner.py U2/U3, the handbook U2/U4/U5/U6, FINDINGS
U1–U5, templates/BUILDER-N-PROMPT.md U4/U5, architect/CLAUDE.md U4/U5).
U6's operator table reads the code after U1–U5. U7 last.
