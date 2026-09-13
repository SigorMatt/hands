# BACKLOG — items the architect has committed to future missions

Maintained by the architect; the builder does not act on this file. Each
item names the mission it is scheduled for; unscheduled items say so.

## Mission 8 — DONE 2026-09-13 (review 8: blockers=0). Items 1–6 landed.

## Mission 9 — DONE 2026-09-13 (review 9: blockers=0).

## Mission 10 — DONE 2026-09-13 except who-by-pid (H-020; moved to 11).

## Mission 11 (scheduled 2026-09-13)

- Review 10 blocker 1 and should-fix 1–7; the apply from the kit; the
  driver role and `consult`; this repository's playbook with consult rules
  and the BUILDER-12 kickoff. Spec: DESIGN v3.10 §27.

## Unscheduled

- **PR reviewer as a second verdict source.** A hosted PR review (bot or
  action) is one more cold reviewer whose verdict the playbook reads via
  `gh pr view`/checks; hands' own review could post as a PR review. A
  playbook rule and one tool, after M5's first auto-merge works.

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
