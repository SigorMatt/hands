# plan — mission 22 (the operational findings and the onboarding half)

Source: meta/BUILDER-22-PROMPT.md, DESIGN v3.21 §38 (with §26, §31, §33,
§36, §37), meta/reviews/REVIEW-21.md. Units run in order; each ends with a
commit and a push to `mission-22`; the last unit opens the pull request to
`main` (§35). `[x]` = done and pushed, `[b]` = blocked (two failures).

Base of the mission: 7ddc0e8 (`plan: mission 22 kit (DESIGN v3.21)`).

- [x] U0 Plan, branch and findings (`plan:`) (this commit) — this file, meta/CHECKPOINT.md,
      meta/journal.md, meta/findings/FINDINGS.md (H-049, H-050 filed;
      H-037, H-046..H-048 in progress)
- [ ] U1 The buttons carry the token (H-037) — src/hands/notify.py,
      src/hands/phone.py, src/hands/doctor.py, tests
- [ ] U2 `handswho` on change only; doctor's broker warning (H-046) —
      src/hands/who.py, src/hands/config.py, src/hands/doctor.py,
      docs/INTEGRATION.md, tests
- [ ] U3 A daemon stop does not strand the builder (H-047) —
      src/hands/daemon.py, src/hands/runner.py, src/hands/spool.py,
      src/hands/playbook.py, tests
- [ ] U4 A blocked mission consults the role (H-048) — src/hands/playbook.py,
      src/hands/kit.py, templates/PLAYBOOK-missions.toml, docs/PLAYBOOK.md,
      tests
- [ ] U5 `progress <secret>` — src/hands/phone.py, src/hands/api.py,
      docs/INTEGRATION.md, docs/PLAYBOOK.md, tests
- [ ] U6 Review 20's two notes on U6 — src/hands/playbook.py, tests
- [ ] U7 The protocols (H-049, H-050; review 21 should-fix 2) —
      templates/REVIEW-PROTOCOL.md, meta/REVIEW-PROTOCOL.md, tests
- [ ] U8 The templates — templates/DECISIONS-owner.md (new),
      templates/BUILDER-N-PROMPT.md, docs/ARCHITECT-INSTRUCTION.md,
      architect/CLAUDE.md, src/hands/kit.py, tests
- [ ] U9 The installed handbook and templates (HF-002, HF-004, HF-005) —
      pyproject.toml, src/hands/cli.py, src/hands/runner.py,
      src/hands/config.py, architect/CLAUDE.md, docs/ARCHITECT-INSTRUCTION.md,
      docs/ARCHITECT-HANDBOOK.md, tests
- [ ] U10 `hands project add` — src/hands/cli.py, src/hands/project.py (new),
      docs/INTEGRATION.md, tests
- [ ] U11 Docs (review 21 should-fix 3) — docs/INTEGRATION.md,
      docs/ARCHITECT-HANDBOOK.md, docs/PLAYBOOK.md, README.md, tests
- [ ] U12 Final report and the pull request — meta/FINAL-REPORT-22.md
      (drafted under meta/drafts/)

Review items. REVIEW-21 should-fix 1 → U12 (the report's sentence);
should-fix 2 → U7 (H-049); should-fix 3 → U11.

Findings. H-037 → U1; H-046 → U2; H-047 → U3; H-048 → U4; H-049, H-050 →
U7; HF-002, HF-004, HF-005 → U9.

Dependencies. All units run in order (shared files: doctor.py U1/U2,
playbook.py U3/U4/U6, phone.py U1/U5, kit.py U4/U8, cli.py U9/U10,
INTEGRATION.md U2/U5/U10/U11). U12 last.
