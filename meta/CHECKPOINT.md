# CHECKPOINT

Mission: 7a (meta/BUILDER-7-PROMPT.md) — FINISHED
Unit in progress: none. U0..U6 all `[x]` in meta/plan.md.
Base: db0bd2c, red (2 failed, 1110 passed): the kit changed rule 8 and §10's
example; 169ce88 brought the disk to the kit before U0 (deviation recorded).
Done: U0 b77bc4d; U1 c00f0c0 (1156 passed); U2 09eed7c (1204 passed);
U3 da1ffb3 (1205 passed); U4 b29b1c7 (1233 passed); U5 f96938e (1235 passed);
U6 is the commit that carries this line (meta only).
Tip for the gate: f96938e — `./scripts/check` green three consecutive runs
at dfd9e6c and three more before U6's commit, 1235 passed.
Report: meta/FINAL-REPORT-7.md (NOT PROVEN in §3, `## Review items`,
acceptance in §4, the architect's list in §5).
Review 6 is closed: both blockers (blocker 2 for the report; `notify --test`'s
code path is unchanged, §3 item 6) and should-fix 1–6 (6 by DESIGN v3.6 §11).
Findings: H-014 decided and closed on disk (U1 runner/env/doctor, U2 hook),
with one gap for the architect: `SendMessage` continuing a sub-agent is the
path the hook cannot see. H-001 and H-009 open.
Standing constraints: one foreground sub-agent per unit, commit and push
every unit, ./scripts/check green three consecutive runs before each commit,
explicit paths only in `git add` (never `-A`), reports drafted under
meta/drafts/, DESIGN.md is not edited by builders (file a finding),
sub-agents do not edit meta/plan.md or this file.
