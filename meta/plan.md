# plan — mission 20 (the first role-mode series' findings)

Source: meta/BUILDER-20-PROMPT.md, DESIGN v3.19 §36 (with §31, §33, §34,
§35), meta/reviews/REVIEW-19.md, meta/reviews/REVIEW-18.md. Units run in
order; each ends with a commit and a push to `mission-20` (pull-request
mission, §35). `[x]` = done and pushed, `[b]` = blocked (two failures).

Base of the mission: 238a57b (`plan: mission 20 kit (DESIGN v3.19)`).

- [x] U0 Plan, branch and findings (`plan:`) (this commit) — this file,
      meta/CHECKPOINT.md, meta/journal.md, meta/findings/FINDINGS.md
      (H-041..H-045); branch `mission-20` pushed
- [x] U1 Hermetic tests; review 19 should-fix 3, 4, 5 (H-040) 4752ace —
      tests/conftest.py, src/hands/doctor.py (`gh` row), docs/INTEGRATION.md,
      docs/PLAYBOOK.md
- [x] U2 The review protocol (review 19 should-fix 1, 2; HF-007; HF-008) 7326386 —
      templates/REVIEW-PROTOCOL.md, meta/REVIEW-PROTOCOL.md
- [x] U3 The architect role's write permission (H-041) 0eb37bc —
      architect/settings.json, src/hands/doctor.py
- [x] U4 The runner (H-042, H-043) de2e34c — src/hands/runner.py,
      src/hands/config.py, src/hands/doctor.py
- [x] U5 The engine (H-044, H-045) 337db9a — src/hands/playbook.py,
      src/hands/api.py, src/hands/daemon.py
- [x] U6 `answer <secret> <text>` 187e38e — src/hands/phone.py, api.py, spool.py,
      playbook.py, notify.py, docs/INTEGRATION.md
- [x] U7 The job environment and the guard (HF-006; HF-003) 61a2417 —
      src/hands/runner.py, src/hands/doctor.py, driver/hooks/bash_guard.py,
      docs/INTEGRATION.md
- [x] U8 Review 18 should-fix 1–4 6a3f2f2 — config.py, doctor.py, api.py/kit.py,
      bash_guard.py
- [x] U9 Notifications and this repository's kickoff 2e9a6ca — notify.py,
      daemon.py, doctor.py, docs/INTEGRATION.md, PLAYBOOK.toml
- [x] U10 Final report and the pull request (this commit) — meta/FINAL-REPORT-20.md
      (drafted under meta/drafts/); `gh pr create`; tree back to `main`

Review items. REVIEW-19 should-fix 1, 2 → U2; 3, 4, 5 → U1. REVIEW-18
should-fix 1–4 → U8.

Findings. H-041..H-045 filed by U0. H-040 resolved by U1. Until U1 lands
the gate is `env -u HANDS_PROJECT -u HANDS_JOB ./scripts/check`.

Dependencies. U1 first (hermetic gate). U4 before U7 (both touch the
runner's job environment). U3, U4, U7, U8, U9 all touch doctor.py: run in
order, never concurrently. U5 before U6 (both in the engine). U10 last.
