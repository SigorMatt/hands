# plan — mission 23 (review 22, the four findings, the hosted review read mechanically)

Source: meta/BUILDER-23-PROMPT.md, DESIGN v3.22 §39 (with §24, §27, §31,
§35, §38), meta/reviews/REVIEW-22.md, docs/QODO-EXTRACTION.md. Units run in
order; each ends with a commit and a push to `mission-23`; the last unit
opens the pull request to `main` (§35), reads the hosted review with `hands
hosted-review` and fixes its findings. `[x]` = done and pushed, `[b]` =
blocked (two failures).

Base of the mission: 23eff6c (`plan: mission 23 kit (DESIGN v3.22)`).

- [x] U0 Plan, branch and findings (`plan:`) (this commit) — this file, meta/CHECKPOINT.md,
      meta/journal.md, meta/findings/FINDINGS.md (H-055..H-060 filed;
      H-051..H-054 decided)
- [ ] U1 The who watcher (should-fix 1, 2) — src/hands/who.py, tests
- [ ] U2 Orphans, refusals and ids (should-fix 3, 4; H-057, H-058, H-059) —
      src/hands/daemon.py, src/hands/playbook.py, src/hands/phone.py,
      src/hands/notify.py, PLAYBOOK.toml, templates/PLAYBOOK-missions.toml,
      templates/PLAYBOOK-runs.toml, tests
- [ ] U3 The engine's small fixes (should-fix 5, 7; H-060) —
      src/hands/playbook.py, src/hands/api.py, tests
- [ ] U4 `progress` and the README (should-fix 6) — src/hands/phone.py,
      README.md, tests
- [ ] U5 `hands hosted-review <pr>` — src/hands/cli.py, src/hands/hosted.py
      (new), tests
- [ ] U6 The protocol and the brief template (should-fix 8; H-055) —
      templates/REVIEW-PROTOCOL.md, meta/REVIEW-PROTOCOL.md,
      templates/BUILDER-N-PROMPT.md, docs/ARCHITECT-HANDBOOK.md §9, tests
- [ ] U7 H-051 and H-052 (should-fix 10; HF-002) — src/hands/playbook.py,
      driver/hooks/bash_guard.py, architect/settings.json, architect/CLAUDE.md,
      src/hands/cli.py, src/hands/project.py, meta/findings/FINDINGS.md, tests
- [ ] U8 `project add` after a failed clone; the role's rulings
      (should-fix 9, 11) — src/hands/project.py, architect/CLAUDE.md, tests
- [ ] U9 Hooks and docs (should-fix 12; H-053, H-054, H-056) —
      .claude/settings.json, docs/INTEGRATION.md, docs/ARCHITECT-HANDBOOK.md,
      docs/PLAYBOOK.md, tests
- [ ] U10 Final report, the pull request and the hosted review's findings —
      meta/FINAL-REPORT-23.md (drafted under meta/drafts/),
      meta/reviews/hosted/PR-<n>/

Review items (REVIEW-22 should-fix). 1, 2 → U1; 3, 4 → U2; 5, 7 → U3;
6 → U4; 8 → U6; 9, 11 → U8; 10 → U7; 12 → U9.

Findings. H-051, H-052, HF-002 → U7; H-053, H-054, H-056 → U9; H-055 → U6;
H-057, H-058, H-059 → U2; H-060 → U3.

Dependencies. All units run in order (shared files: playbook.py U2/U3/U7,
phone.py U2/U4, project.py U7/U8, architect/CLAUDE.md U7/U8, cli.py U5/U7,
ARCHITECT-HANDBOOK.md U6/U9). U10 last; it uses U5's command.
