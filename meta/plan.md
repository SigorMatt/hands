# plan — mission 24 (M8a: the harness probe and the seam's shape; the day's findings; operations)

Source: meta/BUILDER-24-PROMPT.md, DESIGN v3.23 §40 (with §2, §23, §33,
§35, §38, §39), meta/reviews/REVIEW-23.md, docs/RELATED.md,
docs/QODO-EXTRACTION.md. Units run in order; each ends with a commit and a
push to `mission-24`; the last unit opens the pull request to `main` (§35),
reads the hosted review with `hands hosted-review` and fixes its findings.
`[x]` = done and pushed, `[b]` = blocked (two failures), `[b] refused` = a
sub-agent refused.

Base of the mission: de407f2 (`plan: mission 24 kit (DESIGN v3.23)`).

- [x] U0 Plan, branch and findings (`plan:`) (this commit) — this file,
      meta/CHECKPOINT.md, meta/journal.md, meta/findings/FINDINGS.md
      (H-062..H-069 filed; H-064, H-065 decided; H-061 decided; H-051 Status corrected)
- [x] U1 f558f0f The harness probe — docs/HARNESS-PROBE.md (new)
- [x] U2 b003bee `hands go` and `hands kit apply` — src/hands/cli.py, api.py,
      kit.py/phone.py, README.md, tests
- [x] U3 6f373cd The monitor and the runner (H-062, H-063) — src/hands/monitor.py,
      runner.py, daemon.py, tests
- [x] U4 8c081d0 The hosted-review command's proofs (should-fix 3, 4, 5) —
      src/hands/hosted.py, phone.py, api.py, tests, fixtures
- [x] U5 24ac73d The engine, the docs' claim, two unpinned behaviours (should-fix
      6, 7, 8, 9) — api.py/daemon.py/runner.py, docs/INTEGRATION.md,
      project.py, tests
- [x] U6 529b91f The playbook without `aux.orphaned` (H-061) — kit.py, playbook.py,
      docs/PLAYBOOK.md, tests
- [x] U7 649417d Templates and handbook: refusals, worktrees, skip list, gate
      (H-066..H-069) — templates/BUILDER-N-PROMPT.md,
      templates/REVIEW-PROTOCOL.md, meta/REVIEW-PROTOCOL.md,
      architect/CLAUDE.md, docs/ARCHITECT-HANDBOOK.md §7 §17, tests
- [x] U8 c6b70c1 docs/OPERATIONS.md, the capture script, the doctor row (H-067) —
      docs/OPERATIONS.md (new), scripts/capture-quota-stop.sh (new),
      src/hands/doctor.py, tests
- [x] U9 6fc7e6e The docs — docs/INTEGRATION.md, docs/ARCHITECT-HANDBOOK.md §18,
      README.md, tests
- [x] U10 (this commit) Final report, the pull request and the hosted review's findings —
      meta/FINAL-REPORT-24.md, meta/reviews/hosted/PR-<n>/

Review items (REVIEW-23 should-fix). 1 → H-064, 2 → H-065 (decided in §40,
U0); 3, 4, 5 → U4; 6, 7, 8, 9 → U5.

Findings. H-061 → U6; H-062, H-063 → U3; H-064, H-065 → U0 (decided);
H-066, H-068, H-069 → U7; H-067 → U7, U8.

Dependencies. Units run in order (shared files: api.py U2/U4/U5, phone.py
U2/U4, kit.py U2/U6, docs/INTEGRATION.md U5/U9, handbook U7/U9, README
U2/U9). U1 is independent of the rest. U10 last.
