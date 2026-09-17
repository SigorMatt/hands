# BACKLOG — items the architect has committed to future missions

Maintained by the architect; the builder does not act on this file. Each
item names the mission it is scheduled for; unscheduled items say so.

## Mission 8 — DONE 2026-09-13 (review 8: blockers=0). Items 1–6 landed.

## Mission 9 — DONE 2026-09-13 (review 9: blockers=0).

## Mission 10 — DONE 2026-09-13 except who-by-pid (H-020; moved to 11).

## Mission 11 — DONE 2026-09-13 (review 11: blockers=5, the driver guard
   bypassable; driver role not enabled until mission 12).

## Mission 12 — DONE 2026-09-15 (review 12: blockers=3; the guard's comment hole).

## Mission 13 — DONE 2026-09-15 (review 13: blockers=4; the guard's heredoc hole).

## Mission 14 — DONE 2026-09-16 (review 14: blockers=2; role mode held; the command table).

## Mission 15 — DONE 2026-09-16 (review 15: blockers=4; the guard's `for`/`${…}` hole, role mode regressed; driver role disabled again).

## Mission 16 — DONE 2026-09-16 (review 16: blockers=2, neither the guard; driver role enabled 2026-09-17).

## Mission 17 — DONE 2026-09-17 (review 17: blockers=1, the start fold; autonomy path closed).

## Mission 18 (scheduled 2026-09-17) — closer: review 17, who "needs you" from current state. Spec: DESIGN v3.17 §34. After its review: enable the architect role.

- Review 11 blockers 1–5 and should-fix 1–9; the guard rewritten on shlex
  tokens; consult stops in the engine; H-022 resolved. Spec: DESIGN v3.11
  §28. After it: enable `[roles.driver]`, refresh the driver kit, first
  real consultation, then M5.

## (specified in DESIGN §31, scheduled as mission 15) the architect role (decided 2026-09-15; ROADMAP M4c)

1. `[roles.architect]`: cwd `~/hands-architect/<project>/` with a fetch-only
   clone; CLAUDE.md = `docs/ARCHITECT-INSTRUCTION.md` (role variant: reads
   the handbook from the clone; outputs are kits under `kits/`); guard role
   mode `HANDS_ROLE=architect`: read-only git, `hands kit check`, `hands
   kit file`, `hands show|jobs|inbox|pipeline|status`; writes only under
   `kits/`; no send, no approve, no push; `permission_flags` empty.
2. `hands kit file <zip>`: files a held apply job exactly as the phone's
   `kit` does, from a local path under the architect's `kits/`.
3. `[series] architect = "phone" | "role"` and `[series] autonomous = true`:
   in role mode with autonomous set, kit applies from the architect role
   are approved by the engine (`decided_by: playbook`) and the kickoff is
   sent after `kit applied`; the human's approval of the playbook is the
   standing approval.
4. Consult on review outcomes: `aux.done` rules with `then = "consult"`,
   `role = "architect"`; the architect's verdict vocabulary and follow-up
   rules; `[limits] max_architect_consults` per series.
5. Escalation conditions in `[series]`: `gate_failures = 2`,
   `escalate_on = ["blocker-unanswered", "milestone-missing",
   "budget-exhausted"]`; each stops with a reason naming the condition and
   the architect's last session id.
6. `hands doctor` reports the architect role like the driver role.

## (specified in DESIGN §33, scheduled as mission 17) talking to the architect (decided 2026-09-15; ROADMAP M4c)

1. `reply <secret> <text>` on `cmd_topic`: delivered as `hands send --role
   architect --context keep` to the architect's last session; its reply's
   text is published on `ntfy_topic` (title `architect`); one job per turn.
2. `docs/INTEGRATION.md`: self-hosting ntfy in a container on the laptop,
   reachable through the Tailscale tunnel; both topics configured with
   `ntfy_url`; access control on the server so topics need credentials.
3. The escalation notification carries the architect's last session id and
   the one-line `claude --resume` for the Code tab route.

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
