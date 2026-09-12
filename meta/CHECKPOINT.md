# CHECKPOINT

Mission: 8 (meta/BUILDER-8-PROMPT.md, DESIGN v3.7 §24)
Done: U0 9ae7975 (1238 passed); U1 df8c1fd (1285 passed; per DESIGN §6
a success result + turns + exit 0 is `done` whatever stderr says, so
H-014's recorded shape is now `done`); U2 68e1048 (1300 passed; notice is
`system` task_updated status killed / task_notification status stopped,
command line from the matching Bash tool_use; root PLAYBOOK.toml left to U7);
U3 4782a4a (1323 passed; process-group mode tested, scope mode via a stub
systemd-run; conftest forces process-group mode; doctor `isolation` row);
U4 7183478 (1367 passed; src/hands/phone.py; cmd_topic without cmd_secret
refused at config load; `decided_by: phone` read back three ways; doctor
notifications/who rows left to U7).
Unit in progress: U5 REVIEW-3 deferrals (backlog 3).
Intent: meta/reviews/REVIEW-3.md should-fix 3 (doctor's hardcoded flags),
6 (`accepted()` type), 7 (`Api.notify` failure shape).
Done means: one unit commit, pushed; one test each; ./scripts/check green
three consecutive runs.
Base: da8df27, green (1235 passed).
Standing constraints: one foreground sub-agent per unit, commit and push
every unit, ./scripts/check green three consecutive runs before each commit,
explicit paths only in `git add` (never `-A`), reports drafted under
meta/drafts/, DESIGN.md is not edited by builders (file a finding),
sub-agents do not edit meta/plan.md or this file.
