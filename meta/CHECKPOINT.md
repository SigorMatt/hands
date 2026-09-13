# CHECKPOINT

Mission: 11 (meta/BUILDER-11-PROMPT.md, DESIGN v3.10 §27)
Unit in progress: U5 `consult` (§10, §27).
Base: 0fef436. Done: U0 e8daca8 (1550); U1 efe4d56 (1573); U2 525dc66 (1588);
U3 d4bea98 (1613); U4 d491f6b (1699, green 3/3).
Intent: playbook action `consult` sends the driver role a prompt with the
event, the job record (id, role, verdict, result verbatim) and §27's
instruction; events `driver.done` and `driver.failed`; `[limits]
max_consults` (default 2) per mission counted from the last kickoff; exceeded
→ stop with reason; follow-up rules on `driver.done`: `^VERDICT: resolved`
(nothing more) and `^VERDICT: escalate` (stop, message with the reason); an
unrecognised driver verdict and `driver.failed` stop. Every consultation files
`consult.sent`/`consult.done` inbox events and appends one line to
`meta/journal.md` in `role.builder.cwd` (working tree only). Driver reply
stored verbatim in its job record. docs/PLAYBOOK.md, docs/INTEGRATION.md, kit
check knows `consult`, `driver.done`, `driver.failed`. U4 refuses every send
to the driver: `consult` needs its own path.
Done means: end-to-end test with fake_claude as the driver: question →
consult → resolved (keep sent to the builder); question → consult → escalate
(stop); a third consult in one mission → stop; `./scripts/check` green three
consecutive runs; one commit listing every file; pushed.
Standing constraints: one foreground sub-agent per product unit, commit and
push every unit, ./scripts/check green three consecutive runs before each
commit, explicit paths only in `git add` (never `-A`), reports drafted under
meta/drafts/, DESIGN.md is not edited by builders (file a finding), sub-agents
do not edit meta/plan.md or this file.
