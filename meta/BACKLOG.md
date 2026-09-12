# BACKLOG — items the architect has committed to future missions

Maintained by the architect; the builder does not act on this file. Each
item names the mission it is scheduled for; unscheduled items say so.

## Mission 6

1. **Harness-killed background tasks are detected.** The monitor watches
   each role job's stream-json for the harness's task-killed notice and
   files `monitor.task_killed` with the task's command line. The example
   playbook maps it to `stop`. (Origin: 2026-09-12 discussion; the harness
   reaps background tasks on its own schedule, DESIGN §11/§21.)
2. **Per-job systemd scope and orphan accounting.** The runner starts each
   `claude -p` in its own transient scope (`systemd-run --user --scope`);
   the monitor reads the scope's `cgroup.procs` for the live pid set (and
   passes it as `--pids`), and at job end files `monitor.orphan_processes`
   with the command lines of anything still in the scope, then kills the
   scope. Cgroup membership survives double forks, so this catches what the
   `PreToolUse` hook (mission 5 U7) cannot see. Fallback when systemd is
   unavailable: process-group accounting, documented as weaker.
3. REVIEW-3 should-fix 3, 6, 7 (doctor hardcoded flags; `accepted()`
   type; `Api.notify` failure shape), deferred twice; close them.
4. Playbook example gains `monitor.task_killed` and
   `monitor.orphan_processes` rules; `docs/PLAYBOOK.md` updated.

## Unscheduled

- **tmux wake channel.** `handsd` (or a small watcher) sends a fixed
  `check` + Enter into the driver's tmux pane on `stop`/`held`, removing
  the human's message from the idle-time wake. Risk: `Enter` answers any
  open dialog in that pane. Decide from how many idle-time pokes the human
  actually makes across missions 5–7.
- **Remote MCP face** (DESIGN §9). Only if a chat brain as a second driver
  is wanted.
- **Authenticated approvals.** `decided_by: driver` is a declaration
  (DESIGN §8); authentication belongs to the remote face if built.
- **Driver guard: self-noise.** The driver's own gated send wakes its own
  wait; harmless, could be filtered by job origin.
