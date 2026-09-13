# CHECKPOINT

Mission: 11 (meta/BUILDER-11-PROMPT.md, DESIGN v3.10 §27)
Unit in progress: U3 The apply from the kit (§27; REVIEW-10 should-fix 2;
H-018 `kit` origin).
Base: 0fef436. Done: U0 e8daca8 (1550); U1 efe4d56 (1573); U2 525dc66 (1588,
green 3/3).
Intent: on `kit.received`, `handsd` lists the zip's entries, computes
replaced/added against `role.builder.cwd`, takes the commit message from
`KIT.md`'s first line (else `plan: kit <name>`), builds the standard apply
prompt (docs/ARCHITECT-HANDBOOK.md §3 shape, files named, `VERDICT: kit
applied <sha>`), creates a held builder job with `origin: kit` and gate reason
`apply <name>`; the notification carries the buttons. A zip with entries
outside the repo, absolute, or `..` is refused (`kit.refused`). `hands kit
check` prints the same prompt and writes the expected `KIT.md` shape. `kit`
is a job origin and un-pauses the pipeline when the job starts (H-018 v3.10).
Done means: tests for the prompt text (byte-equal between `kit check` and the
daemon), the held job, the refusals; `./scripts/check` green three
consecutive runs; one commit listing every file; pushed.
Standing constraints: one foreground sub-agent per product unit, commit and
push every unit, ./scripts/check green three consecutive runs before each
commit, explicit paths only in `git add` (never `-A`), reports drafted under
meta/drafts/, DESIGN.md is not edited by builders (file a finding), sub-agents
do not edit meta/plan.md or this file.
