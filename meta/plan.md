# plan — mission 25 (closer for review 24)

Source: meta/BUILDER-25-PROMPT.md, DESIGN v3.24 §41 (with §39, §40),
meta/reviews/REVIEW-24.md, docs/HARNESS-PROBE.md. A closer: it continues
the open branch `mission-24` (PR #5), `main` merged in first. Units run in
order; each ends with a commit and a push to `mission-24`; the last unit
opens no pull request, reads the hosted review of PR #5 again, and returns
the tree to `main`. `[x]` = done and pushed, `[b]` = blocked (two failures).

Base of the mission: 20aac9f (`plan: mission 25 kit (DESIGN v3.24, closer)`),
merged into mission-24 at cc2a9e5.

- [x] U0 Plan and branch (`plan:`) (this commit) — this file, meta/CHECKPOINT.md,
      meta/journal.md, meta/findings/FINDINGS.md (H-062 note)
- [ ] U1 The capture script (blocker 1; should-fix 1) —
      scripts/capture-quota-stop.sh, docs/OPERATIONS.md, tests
- [ ] U2 The staged kit (should-fix 2) — src/hands/kit.py, src/hands/api.py,
      tests
- [ ] U3 Three pins: monitor, api, runner (should-fix 6, 7, 8) —
      src/hands/monitor.py, src/hands/api.py, src/hands/runner.py, tests
- [ ] U4 The warning and the stale worktree (should-fix 4, 5) —
      src/hands/kit.py, templates/REVIEW-PROTOCOL.md,
      meta/REVIEW-PROTOCOL.md, docs/ARCHITECT-HANDBOOK.md §7, tests
- [ ] U5 The probe record (should-fix 3) — docs/HARNESS-PROBE.md
- [ ] U6 Final report, the push and the hosted review's findings —
      meta/FINAL-REPORT-25.md (drafted under meta/drafts/),
      meta/reviews/hosted/PR-5/

Review items (REVIEW-24). Blocker 1 → U1; should-fix 1 → U1; 2 → U2;
3 → U5; 4, 5 → U4; 6, 7, 8 → U3.

Dependencies. Units run in order (shared files: kit.py U2/U4, api.py
U2/U3). U6 last.
