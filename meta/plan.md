# plan — mission 19 (the pull-request flow; a hosted second reviewer)

Source: meta/BUILDER-19-PROMPT.md, DESIGN v3.18 §35 (with §26, §31),
meta/reviews/REVIEW-18.md. Units run in order; each ends with a commit
and a push, to `main` (this mission is "direct", §35 "This repository").
`[x]` = done and pushed, `[b]` = blocked (two failures).

Base of the mission: 21d62d9 (`plan: mission 19 kit (DESIGN v3.18)`).

- [x] U0 Plan, bookkeeping and the gate (`plan:`) (this commit) — this file,
      meta/CHECKPOINT.md, meta/journal.md; probe PR from `probe-qodo`, the
      bot's first comment within 15 minutes, recorded under "Gate U0"; PR
      closed, branch deleted
- [x] U1 Doctor's `gh` row (§35) b55dfb1 — src/hands/doctor.py, tests; fake `gh` on
      PATH: success, missing, unauthenticated, no `repo` scope; WARN never
      FAIL; `--json` carries it
- [x] U2 Templates (§35) 7929d9c — templates/BUILDER-N-PROMPT.md,
      templates/REVIEW-PROTOCOL.md, templates/PLAYBOOK-missions.toml,
      templates/PLAYBOOK-runs.toml, src/hands/kit.py, tests; the `pr=<number>`
      literal passes `verdicts`; a filled kit passes 6 of 6 against a clone
- [x] U3 This repository's own flow (§35) de56f62 — CLAUDE.md,
      meta/REVIEW-PROTOCOL.md, PLAYBOOK.toml (kickoff BUILDER-20, review
      prompt); loads with 20 rules; kit `--repo .` exit 0
- [x] U4 Docs (§35) 5220e67 — docs/ARCHITECT-HANDBOOK.md §6 and §9,
      docs/INTEGRATION.md, docs/PLAYBOOK.md
- [x] U5 Final report (meta/FINAL-REPORT-19.md) (the commit that carries this line) — drafted under meta/drafts/

Review items. REVIEW-18's should-fix 1–4 are mission 20's (the brief: this
mission does not touch the engine, the guard, the roles or those items).

Findings. H-040 filed by U0: twelve tests/test_kit.py tests fail when
`HANDS_PROJECT`/`HANDS_JOB` are set (this mission runs as a hands job); every
gate of this mission is `env -u HANDS_PROJECT -u HANDS_JOB ./scripts/check`.
H-039, H-037, H-034, H-027, H-001, H-009 stay open.

Dependencies. U2's protocol template is U3's source; U1 before U4 (the docs
name doctor's row); U5 last.

## Gate U0

Run by the orchestrator, 2026-10-14, `gh` 2.92.0, logged in as SigorMatt
(scopes `gist`, `read:org`, `repo`, `workflow`).

- PR: SigorMatt/hands#1, `probe-qodo` → `main`, one line appended to
  docs/INTEGRATION.md ("probe: hosted review, 2026-10-14"), commit
  `probe: hosted review`.
- Opened: 2026-10-14T11:31:49Z (`gh pr view 1 --json createdAt`).
- First bot comment: 2026-10-14T11:32:18Z, `qodo-code-review[bot]`, two
  issue comments at the same second ("PR Summary by Qodo"; "Code Review by
  Qodo": Bugs 0, Rule violations 0, Requirement gaps 0). No entry under
  `pulls/1/reviews` by the second poll (11:32:57Z).
- Delay: 29 seconds.
- Trigger mode: on open (the bot posted with no comment from me).
- Closed: `gh pr close 1 --delete-branch`; local branch deleted; `git fetch
  --prune` then `git branch -a` shows no `probe-qodo`.
