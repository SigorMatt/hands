# plan — mission 30 (the gate's follow-up before the switch)

Source: meta/BUILDER-30-PROMPT.md, DESIGN v3.29 §46 (with §43, §45, §35),
meta/reviews/REVIEW-29.md, meta/findings/FINDINGS.md (H-081, H-082, H-083;
H-084, H-085 filed here). Branch `mission-30`, created from `main`
(e213c2e, `plan: mission 30 kit (DESIGN v3.29, the follow-up of the
gate)`). Units run in order; each ends with a commit and a push to
`mission-30`; the last unit opens the pull request, waits for its `check`
check and the hosted review, and returns the tree to `main`. `[x]` = done
and pushed, `[b]` = blocked (two failures) or refused.

- [x] U0 (this commit) Plan, branch and findings (`plan:`) — this file,
      meta/CHECKPOINT.md, meta/findings/FINDINGS.md (H-081, H-082, H-083
      decided; H-084, H-085 filed)
- [x] U1 16723ad Case (b), and the setting's refusal (§46 "H-082"; review 29's
      should-fix 3 is U1's; §45) — src/hands/kit.py, src/hands/config.py,
      handbook §3 quotation, FINDINGS (H-082 resolved), tests
- [x] U2 8b3aa60 The engine approves plan files only (§46 "H-083"; §31, §32, §43,
      §45) — src/hands/spool.py, playbook.py, daemon.py (if needed),
      kit.py, architect/CLAUDE.md, handbook §3/§12/§19 +
      tests/test_operator_table.py, docs/PLAYBOOK.md, docs/INTEGRATION.md,
      templates/PLAYBOOK-missions.toml, templates/PLAYBOOK-runs.toml,
      FINDINGS (H-083 resolved), tests
- [x] U3 2a2442e The review merges what it reviewed, its failure paths, and the
      blocker for a bug in the pull request's own code (§46 "H-081", "A
      confirmed bug ...", review 29's should-fix 2 and 4; §35, §45) —
      meta/REVIEW-PROTOCOL.md, templates/REVIEW-PROTOCOL.md,
      templates/BUILDER-N-PROMPT.md, handbook §9/§19, FINDINGS (H-081,
      H-084, H-085 resolved), tests
- [ ] U4 Final report, the pull request, its checks and the hosted review's
      findings — meta/FINAL-REPORT-30.md (drafted under meta/drafts/),
      meta/reviews/hosted/PR-<pr>/

Review 29's should-fix items: 1 → U1 (H-082), U2 (H-083), U3 (H-081);
2 → U3 (H-084); 3 → U1; 4 → U3 (H-085).

Not in this mission (DESIGN §46): switching this repository's setting,
creating the ruleset or touching GitHub's settings (the human and the aux,
docs/PR-CI-GATE.md §5, after the install); the harness seam and review 25's
should-fix 3 (mission 31); a local-model harness (mission 32); any M9
command and review 25's should-fix 2 (mission 33); Claude credential
profiles (the backlog); no change to docs/ARCHITECT-INSTRUCTION.md or this
repository's PLAYBOOK.toml; no host change.

Dependencies. Units run in order (shared files: kit.py U1/U2, handbook
U1/U2/U3, FINDINGS U1/U2/U3). U4 last.
