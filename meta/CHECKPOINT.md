# CHECKPOINT

Mission: 7a (meta/BUILDER-7-PROMPT.md) — IN PROGRESS
Unit in progress: U4 (client seams).
Done: U0 b77bc4d; U1 c00f0c0 (1156 passed); U2 09eed7c (1204 passed);
U3 da1ffb3 (1205 passed).
Base: db0bd2c, red (2 failed, 1110 passed): the kit changed rule 8 and §10's
example. 169ce88 brought the disk to the kit before U0; green three runs,
1112 passed (65.04s / 62.45s / 59.88s). meta/plan.md records the deviation.
Findings: H-014 filed by U0 (harness termination recorded as `done`),
decided by DESIGN v3.6 §23. H-001 and H-009 open.
Standing constraints: one foreground sub-agent per unit, commit and push
every unit, ./scripts/check green three consecutive runs before each commit,
explicit paths only in `git add` (never `-A`), reports drafted under
meta/drafts/, DESIGN.md is not edited by builders (file a finding),
sub-agents do not edit meta/plan.md or this file.
