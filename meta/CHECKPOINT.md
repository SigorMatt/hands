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
REVIEW-3 defects present at base and fixed; monitor.ops_argv shared with
doctor; accepted() integer 2xx only; notify socket route renders + exit 1).
Unit in progress: U6 `hands who` and `handswho` (§4, §11, §24; backlog 6).
Intent: port meta/prototypes/claudewho.py into src/hands/who.py — this
daemon's jobs, held gates, pipeline and inbox from the daemon's own state
over the socket; other `claude` processes from /proc; interactive sessions'
state from transcripts; §24 hierarchy, labels, debounce, fingerprint rules;
`hands who` prints once; `handswho` console script pushes on change and on
`status`/`who`/`check`/`?` from `who_cmd_topic`; optional
systemd/handswho.service; the prototype deleted in the unit commit.
Done means: one unit commit, pushed; the prototype's self-test cases ported;
a rendering test with a fixed process table and fixed daemon state;
./scripts/check green three consecutive runs.
Base: da8df27, green (1235 passed).
Standing constraints: one foreground sub-agent per unit, commit and push
every unit, ./scripts/check green three consecutive runs before each commit,
explicit paths only in `git add` (never `-A`), reports drafted under
meta/drafts/, DESIGN.md is not edited by builders (file a finding),
sub-agents do not edit meta/plan.md or this file.
