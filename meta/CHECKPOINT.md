# CHECKPOINT

Mission: 8 (meta/BUILDER-8-PROMPT.md, DESIGN v3.7 §24)
Done: U0 9ae7975 (1238 passed); U1 df8c1fd (1285 passed; per DESIGN §6
a success result + turns + exit 0 is `done` whatever stderr says, so
H-014's recorded shape is now `done`); U2 68e1048 (1300 passed; notice is
`system` task_updated status killed / task_notification status stopped,
command line from the matching Bash tool_use; root PLAYBOOK.toml left to U7);
U3 4782a4a (1323 passed; process-group mode tested, scope mode via a stub
systemd-run; conftest forces process-group mode; doctor `isolation` row).
Unit in progress: U4 The phone channel (§8, §11, §24; backlog 5; H-015).
Intent: `[notify]` keys per §24; `handsd` long-polls `cmd_topic`
(`/json?since=…`), reconnecting on error; `approve <job> <secret|nonce>`,
`deny <job> [reason] <secret|nonce>`, `pause <secret>`, `resume <secret>`,
`status <secret>`; per-held-job 32-byte single-use nonce dying with the job
on Approve/Deny action buttons; the long-term secret never in a
notification; decisions `decided_by: phone`; bad secret/nonce logged and
ignored, never answered; doctor reports channel on/off and refuses
`cmd_topic` without `cmd_secret`; docs/INTEGRATION.md setup.
Done means: one unit commit, pushed; mocked-ntfy tests for every command,
the nonce lifecycle, secret-never-in-notification, and the `decided_by:
phone` record; ./scripts/check green three consecutive runs.
Base: da8df27, green (1235 passed).
Standing constraints: one foreground sub-agent per unit, commit and push
every unit, ./scripts/check green three consecutive runs before each commit,
explicit paths only in `git add` (never `-A`), reports drafted under
meta/drafts/, DESIGN.md is not edited by builders (file a finding),
sub-agents do not edit meta/plan.md or this file.
