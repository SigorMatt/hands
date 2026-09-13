# CHECKPOINT

Mission: 11 (meta/BUILDER-11-PROMPT.md, DESIGN v3.10 §27)
Unit in progress: U1 Review 10 should-fix 1, 3, 4, 5, 6 (§27).
Base: 0fef436. Done: U0 e8daca8 (1550 passed, green 3/3).
Intent: `go` refused while the builder has a held job (message names it),
rechecked after the playbook load; the post-exit sweep signals a group only
when its leader is the job's pid and every member is a descendant (foreign
group test); `kit check`: the apply-verdict exception never excuses a builder
rule that matches nothing, `aux.done` rules checked against the protocol's
`VERDICT: review …` line (H-021 per §27), paths outside the repo, absolute,
`..`, and a missing protocol path refused; a malformed attachment URL refused
before any fetch with an inbox event `kit.refused`; INTEGRATION's name-clash
wording (`<stem>-1.zip`).
Done means: one test per item, red first; `./scripts/check` green three
consecutive runs; one commit listing every file; pushed.
Standing constraints: one foreground sub-agent per product unit, commit and
push every unit, ./scripts/check green three consecutive runs before each
commit, explicit paths only in `git add` (never `-A`), reports drafted under
meta/drafts/, DESIGN.md is not edited by builders (file a finding), sub-agents
do not edit meta/plan.md or this file.
