# CHECKPOINT

Mission: 8 (meta/BUILDER-8-PROMPT.md, DESIGN v3.7 §24)
Done: U0 9ae7975 (1238 passed); U1 df8c1fd (1285 passed; per DESIGN §6
a success result + turns + exit 0 is `done` whatever stderr says, so
H-014's recorded shape is now `done` — H-014 carries the status paragraph).
Unit in progress: U2 `monitor.task_killed` (§5, §24; backlog 1).
Intent: the monitor tails each role job's stream-json for the harness's
task-killed notice (exact 2.1.x shape found and quoted in a test fixture)
and files `monitor.task_killed` with the task's command line, once per task;
`docs/PLAYBOOK.md` and the §10 example material gain the rule (`stop`) as
far as builders may edit (DESIGN.md is not edited).
Done means: one unit commit, pushed; a `fake_claude` emitting the notice
yields the event, a normal run yields none; ./scripts/check green three
consecutive runs.
Base: da8df27, green (1235 passed).
Standing constraints: one foreground sub-agent per unit, commit and push
every unit, ./scripts/check green three consecutive runs before each commit,
explicit paths only in `git add` (never `-A`), reports drafted under
meta/drafts/, DESIGN.md is not edited by builders (file a finding),
sub-agents do not edit meta/plan.md or this file.
