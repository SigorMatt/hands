# CHECKPOINT

Mission: 11 (meta/BUILDER-11-PROMPT.md, DESIGN v3.10 §27)
Unit in progress: U6 This repository's playbook.
Base: 0fef436. Done: U0 e8daca8 (1550); U1 efe4d56 (1573); U2 525dc66 (1588);
U3 d4bea98 (1613); U4 d491f6b (1699); U5 c1d8ed5 (1717, green 3/3).
Intent: `PLAYBOOK.toml`: `[series] kickoff` becomes BUILDER-12's line;
`[limits] max_consults = 2`; `builder.done` with `^VERDICT: question` and the
unrecognised-verdict catch-all route to `consult` (role driver), with the two
`driver.done` follow-up rules (resolved → notify, escalate → stop) and
`driver.failed` → stop; `[roles.driver]` added to `docs/INTEGRATION.md`'s
example config with cwd `~/hands-driver/hands`.
Done means: the playbook loads; `hands kit check` on the repository's own
files exits 0; `./scripts/check` green three consecutive runs; one commit
listing every file; pushed.
Standing constraints: one foreground sub-agent per product unit, commit and
push every unit, ./scripts/check green three consecutive runs before each
commit, explicit paths only in `git add` (never `-A`), reports drafted under
meta/drafts/, DESIGN.md is not edited by builders (file a finding), sub-agents
do not edit meta/plan.md or this file.
