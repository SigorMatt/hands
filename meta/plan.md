# plan — mission 8 (detectors, the phone channel, who)

Source: meta/BUILDER-8-PROMPT.md, DESIGN v3.7 §24. Units run in order; each
ends with a commit and a push. `[x]` = done and pushed, `[b]` = blocked (two
failures).

Base of the mission: da8df27 (`plan: mission 8 kit (DESIGN v3.7, claudewho
prototype)`) — green: ruff clean, 1235 passed, cli smoke, `check: green`. The
kit already placed `meta/prototypes/claudewho.py` (ruff excludes it).

- [x] U0 Plan and corrections (`plan:`) 9ae7975 — this file, meta/CHECKPOINT.md;
      the prototype verified in place; H-015 (phone channel decision, §24);
      `hands show`'s `failure` line pinned on a failed and a done job
      (review 7 blocker 1)
- [x] U1 Review 7 should-fix 2, 3, 4 df8c1fd — anchored terminating-line matcher that
      never overrides success; the two over-match lines as negatives; the doc
      sweep reads every tracked non-binary file, `meta/` history excluded by
      path, live `meta/` instructions included (§6, §24)
- [x] U2 `monitor.task_killed` (§5, §24; backlog 1) 68e1048
- [x] U3 Per-job scope and orphan accounting (§5, §24; backlog 2) 4782a4a
- [x] U4 The phone channel (§8, §11, §24; backlog 5; H-015) 7183478
- [x] U5 REVIEW-3 deferrals: should-fix 3, 6, 7 (backlog 3) 6fcd7d7
- [ ] U6 `hands who` and `handswho` (§4, §11, §24; backlog 6); prototype
      deleted
- [ ] U7 Playbook and docs (backlog 4)
- [ ] U8 Final report — meta/FINAL-REPORT-8.md (drafted under meta/drafts/)

Review items by unit. REVIEW-7 blocker 1 → U0. Should-fix 1 → DESIGN v3.7
§24 (the architect moved the rule into §2, §6, §13); no builder unit.
Should-fix 2 → U1. Should-fix 3 → U0's `plan:` prefix, and U1 carries the
convention check if a test is cheap. Should-fix 4 → U1. REVIEW-3 should-fix
3, 6, 7 → U5.

Dependencies. U2 and U3 touch the monitor; U3 after U2. U4 before U6
(handswho shares the `[notify]` section and the ntfy client). U7 after U2,
U3, U4, U6. U1, U5 are independent.

Findings. H-015 filed by U0. H-001 and H-009 stay open.
