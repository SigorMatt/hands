# plan — mission 21 (closer for review 20)

Source: meta/BUILDER-21-PROMPT.md, DESIGN v3.20 §37 (with §6, §32, §35,
§36), meta/reviews/REVIEW-20.md. Units run in order; each ends with a
commit and a push to `mission-20` (closer: continues PR #2, §35).
`[x]` = done and pushed, `[b]` = blocked (two failures).

Base of the mission: 1c68883 (`plan: mission 21 kit (DESIGN v3.20)`),
merged into `mission-20` at 5dfab55.

- [x] U0 Plan, the branch and the findings (`plan:`) (this commit) — this
      file, meta/CHECKPOINT.md, meta/journal.md, meta/findings/FINDINGS.md
      (H-046..H-048, open, mission 22)
- [ ] U1 The cancel race (review 20 blocker 1) — src/hands/spool.py,
      src/hands/runner.py, tests
- [ ] U2 The live hook and writes through a hardlink (review 20 should-fix
      1, 2; REVIEW-18 should-fix 2, 4) — driver/settings.json,
      architect/settings.json, driver/hooks/bash_guard.py,
      src/hands/doctor.py, tests
- [ ] U3 Provenance and `doctor --live` (review 20 should-fix 3, 4, 5) —
      src/hands/api.py, src/hands/doctor.py, tests
- [ ] U4 The protocol's revert step (review 20 should-fix 6) —
      templates/REVIEW-PROTOCOL.md, meta/REVIEW-PROTOCOL.md, tests
- [ ] U5 The apply that leaves no playbook (review 20 note on U5) —
      src/hands/playbook.py, tests
- [ ] U6 Final report (meta/FINAL-REPORT-21.md) — drafted under meta/drafts/

Review items. REVIEW-20 blocker 1 → U1; should-fix 1, 2 → U2; should-fix
3, 4, 5 → U3; should-fix 6 → U4; the note on U5 → U5.

Findings. H-046, H-047, H-048 filed by U0, open, scheduled for mission 22.

Dependencies. U2 and U3 both touch src/hands/doctor.py (run in order);
U6 last. Final unit opens no PR: PR #2 stays the branch's open PR.
