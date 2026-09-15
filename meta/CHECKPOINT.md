# CHECKPOINT

Mission: 13 (meta/BUILDER-13-PROMPT.md, DESIGN v3.12 §29 with §5, §12, §13,
§26, §28) — close review 12, the sweep (H-025 b), two projects on one laptop.
Base: 723dbeb (`plan: mission 13 kit (DESIGN v3.12)`).

Unit in progress: U4 Consult edges (§29; REVIEW-12 should-fix 3, 4, 5).
Intent: consult stops apply over a paused pipeline as
`pipeline.stop_suppressed` with the consult reason and a notification;
doctor reads the hook path from the driver directory's
`.claude/settings.json` and checks that file; `max_consults` counts from
daemon start when no kickoff or apply has been seen since.
Done means: tests; ./scripts/check 3/3; pushed.
Done: U0 b79d908 (1994); U1 eccc3a1 (2092); U2 ea7f1bc (2098); U3 126d4ff
(2196).

Standing constraints: one foreground sub-agent per product unit, commit and
push every unit, ./scripts/check green three consecutive runs before each
commit, explicit paths only in `git add` (never `-A`), reports drafted under
meta/drafts/, DESIGN.md is not edited by builders (file a finding), sub-agents
do not edit meta/plan.md or this file, retry a failed unit once then `[b]`.
