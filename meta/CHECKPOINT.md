# CHECKPOINT

Mission: 8 (meta/BUILDER-8-PROMPT.md, DESIGN v3.7 §24)
Done: U0 9ae7975 (1238 passed); U1 df8c1fd (1285 passed; per DESIGN §6
a success result + turns + exit 0 is `done` whatever stderr says, so
H-014's recorded shape is now `done`); U2 68e1048 (1300 passed; notice is
`system` task_updated status killed / task_notification status stopped,
command line from the matching Bash tool_use; root PLAYBOOK.toml left to U7).
Unit in progress: U3 Per-job scope and orphan accounting (§5, §24; backlog 2).
Intent: the runner starts each `claude -p` inside `systemd-run --user
--scope --quiet --unit hands-<project>-<job>` when available and the user
manager answers, else `start_new_session`; `hands doctor` says which is in
force; the monitor reads the scope's `cgroup.procs` (or the process group)
for the live pid set and passes it as `--pids`; at job end anything still
alive is filed `monitor.orphan_processes` with command lines, then the scope
is stopped or the group killed.
Done means: one unit commit, pushed; process-group path tested; a
double-forking `fake_claude` proves the orphan is found and killed;
./scripts/check green three consecutive runs.
Base: da8df27, green (1235 passed).
Standing constraints: one foreground sub-agent per unit, commit and push
every unit, ./scripts/check green three consecutive runs before each commit,
explicit paths only in `git add` (never `-A`), reports drafted under
meta/drafts/, DESIGN.md is not edited by builders (file a finding),
sub-agents do not edit meta/plan.md or this file.
