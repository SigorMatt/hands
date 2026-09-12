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
notifications/who rows left to U7); U5 6fcd7d7 (1380 passed; all three
REVIEW-3 defects present at base and fixed); U6 a93e3a7 (1416 passed;
src/hands/who.py, read-only `who` socket method, handswho script,
systemd/handswho.service; prototype deleted; who_cmd_topic has no secret).
Unit in progress: U7 Playbook and docs (backlog 4).
Intent: root PLAYBOOK.toml gains `monitor.task_killed` and
`monitor.orphan_processes` → `stop` and has no `quiet_hours`; the §10 example
copies stay byte-for-byte DESIGN v3.7 §10; docs/PLAYBOOK.md,
docs/INTEGRATION.md (optional notifications, command channel, who), README.md
updated; `hands doctor` reports notifications, command channel and who as
on/off, never errors; on a config without `[notify]` extras the channel and
who are off, exit 0.
Done means: one unit commit, pushed; the example loads; docs sweep green;
./scripts/check green three consecutive runs.
Base: da8df27, green (1235 passed).
Standing constraints: one foreground sub-agent per unit, commit and push
every unit, ./scripts/check green three consecutive runs before each commit,
explicit paths only in `git add` (never `-A`), reports drafted under
meta/drafts/, DESIGN.md is not edited by builders (file a finding),
sub-agents do not edit meta/plan.md or this file.
