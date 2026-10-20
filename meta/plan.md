# plan — mission 29 (a `main` that takes pull requests only)

Source: meta/BUILDER-29-PROMPT.md, DESIGN v3.28 §45 (with §4, §6, §8, §10,
§13, §27, §31, §32, §35, §36, §39, §43, §44), meta/reviews/REVIEW-28.md,
meta/findings/FINDINGS.md (H-079, H-080), docs/PR-CI-GATE.md. Branch
`mission-29`, created from `main` (f7d61c8, `plan: mission 29 kit (DESIGN
v3.28, main by pull requests only)`). Units run in order; each ends with a
commit and a push to `mission-29`; the last unit opens the pull request,
waits for its `check` check and the hosted review, and returns the tree to
`main`. `[x]` = done and pushed, `[b]` = blocked (two failures) or refused.

- [x] U0 (this commit) Plan, branch and findings (`plan:`) — this file,
      meta/CHECKPOINT.md, meta/findings/FINDINGS.md (H-079, H-080 filed)
- [ ] U1 CI on GitHub's runner (§45 "CI") — .github/workflows/check.yml
      (added), tests/conftest.py (off-machine fixture), tests that leave the
      machine or fail in a bare run, a workflow pin test
- [ ] U2 The setting, `hands ci-wait` and doctor's `main` row (§45; §4,
      §13) — src/hands/config.py, src/hands/forge.py (added),
      src/hands/cli.py, src/hands/doctor.py, templates/config.toml,
      tests/fake_gh.py, tests
- [ ] U3 The apply by the setting, and its resume (§45; §6, §10, §27, §43)
      — src/hands/kit.py, daemon.py, api.py, phone.py, playbook.py,
      limits.py, the handbook's §3 quotation, tests
- [ ] U4 An apply that did not land, the CI's hold, the journal sentence
      (§45; §19, §31, §36, §39, §43, §44; H-080) — src/hands/playbook.py,
      spool.py, kit.py, handbook §19 + tests/test_operator_table.py,
      FINDINGS (H-080 resolved), tests
- [ ] U5 The review protocol, the brief template, the architect and the
      documents (§45) — meta/REVIEW-PROTOCOL.md,
      templates/REVIEW-PROTOCOL.md, templates/BUILDER-N-PROMPT.md,
      architect/CLAUDE.md, docs/ARCHITECT-HANDBOOK.md, docs/INTEGRATION.md,
      docs/OPERATIONS.md, docs/PLAYBOOK.md, CLAUDE.md, tests
- [ ] U6 At rest after the kept list changed (§45 item 1; §44 rule 4;
      H-079) — src/hands/playbook.py (daemon.py), handbook §19,
      docs/PLAYBOOK.md, docs/OPERATIONS.md, FINDINGS (H-079 resolved), tests
- [ ] U7 Final report, the pull request, its checks and the hosted review's
      findings — meta/FINAL-REPORT-29.md (drafted under meta/drafts/),
      meta/reviews/hosted/PR-<pr>/

Not in this mission (DESIGN §45): creating the ruleset, changing this
repository's setting or GitHub's settings; the harness seam and review 25's
should-fix 3 (mission 30); a local-model harness (mission 31); any M9
command and review 25's should-fix 2 (mission 32); Claude credential
profiles (the backlog); no change to docs/ARCHITECT-INSTRUCTION.md,
docs/PR-CI-GATE.md or this repository's PLAYBOOK.toml; no host change.

Dependencies. Units run in order (shared files: playbook.py U3/U4/U6,
kit.py U3/U4, handbook U3/U4/U5/U6, FINDINGS U4/U6). U2's `ci-wait` is used
by U7. U3's chain-walk apply test is used by U4. U7 last.
