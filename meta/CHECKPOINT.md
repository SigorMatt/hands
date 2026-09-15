# CHECKPOINT

Mission: 12 (meta/BUILDER-12-PROMPT.md, DESIGN v3.11 §28 with §8, §10, §12,
§27) — close review 11 (blockers 1–5, should-fix 1–9).
Base: bb9aab5 (`plan: mission 12 kit (DESIGN v3.11)`).
Unit in progress: U2 Consult and the driver role, engine-side (§28; REVIEW-11
should-fix 1, 2, 3, 8).
Intent: the engine enforces the stops for `escalate`, an unrecognised driver
verdict and `driver.failed` whatever the playbook's rules (a playbook may add
`driver.done` rules, not remove the stops); `driver.killed`,
`driver.orphaned`, `driver.limited` are events that stop and notify, with
`consult.done` carrying the terminal state (and a driver job that fails to
spawn still gets consult.done/journal); `max_consults` counts from the later
of the last job whose prompt equals any `[series] kickoff` value seen and the
last `plan:` kit apply; doctor's driver row fails unless the driver
directory's `.claude/settings.json` names the hook, the hook self-tests green
in role mode, and `permission_flags` is empty; the driver job's environment
carries `HANDS_CONSULT_ROLE` (the role the consultation names; U1's guard
refuses every role send without it); docs/PLAYBOOK.md and docs/INTEGRATION.md
updated.
Done means: an end-to-end test per stop with a playbook that has no driver
rules; a counter test across a renamed kickoff; a doctor test for each
failure; ./scripts/check green 3/3; one commit listing every file; pushed.
Done: U0 5ea7b9d (1733 passed); U1 3966f9b (1882).
Findings: H-022 resolved by v3.11 (U0); H-023 open (code U4); H-024 open (U1's
residual-character reading); H-001 and H-009 open.
Standing constraints: one foreground sub-agent per product unit, commit and
push every unit, ./scripts/check green three consecutive runs before each
commit, explicit paths only in `git add` (never `-A`), reports drafted under
meta/drafts/, DESIGN.md is not edited by builders (file a finding), sub-agents
do not edit meta/plan.md or this file, retry a failed unit once then `[b]`.
