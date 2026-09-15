# CHECKPOINT

Mission: 12 (meta/BUILDER-12-PROMPT.md, DESIGN v3.11 §28 with §8, §10, §12,
§27) — close review 11 (blockers 1–5, should-fix 1–9).
Base: bb9aab5 (`plan: mission 12 kit (DESIGN v3.11)`).
Unit in progress: U5 This repository's playbook.
Intent: `PLAYBOOK.toml` `[series] kickoff` becomes "Read
meta/BUILDER-13-PROMPT.md and execute the mission below its divider.";
nothing else in it changes. `hands kit check` on a kit made of
meta/BUILDER-12-PROMPT.md with `--repo .` exits 0 (H-022's acceptance form).
Done means: the playbook loads (tests that pin the kickoff updated);
the check exits 0 and its output is in the commit body; ./scripts/check green
3/3; one commit listing every file; pushed.
Done: U0 5ea7b9d (1733 passed); U1 3966f9b (1882); U2 e642552 (1916);
U3 043413d (1980).
Blocked: U4 7f86406 — who half done (1982); sweep half blocked on H-025
(§28's sweep rule cannot hold after claude is reaped). Not retried.
Findings: H-022 resolved by v3.11 (U0); H-023 open (sweep unchanged, H-025);
H-024 open (U1's residual-character reading); H-025 open (sweep, U4); H-001
and H-009 open.
Standing constraints: one foreground sub-agent per product unit, commit and
push every unit, ./scripts/check green three consecutive runs before each
commit, explicit paths only in `git add` (never `-A`), reports drafted under
meta/drafts/, DESIGN.md is not edited by builders (file a finding), sub-agents
do not edit meta/plan.md or this file, retry a failed unit once then `[b]`.
