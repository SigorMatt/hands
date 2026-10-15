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

## Mission 18 — DONE 2026-09-17 (review 18: blockers=0, should-fix=4; the architect role enabled 2026-09-18).

## Mission 19 — DONE 2026-10-14 (review 19: blockers=0, should-fix=5; installed 2026-10-14).

## Mission 20 — BUILT 2026-10-14 on branch mission-20 (PR #2); review 20 (2026-10-15): blockers=1, should-fix=6; the PR stays open. Items 1–7, 9 (HF-003 only), the review-18 items and the title/topic item below landed; items 8 (HF-002, HF-004, HF-005, the silent first apply) and 10 are mission 22's.

## Mission 21 (scheduled 2026-10-15) — closer for review 20. Spec: DESIGN v3.20 §37. Continues mission-20; its review merges PR #2.

1. Review 20 blocker 1: the cancel race during the clone advance —
   `Spool.transition` judges the on-disk record; the runner re-reads after
   the advance and spawns nothing for a job no longer queued.
2. Review 20 should-fix 1, 2: `python3 -I` in both hook commands and
   doctor failing on a module beside the guard; the `--write` hook refuses
   hardlinked targets and any write while a link exists under `kits/`.
3. Review 20 should-fix 3, 4, 5: `origin: phone` refused from a socket
   client; `doctor --live` judges the resolved clone, a unique kit name,
   removes only what it made.
4. Review 20 should-fix 6: the protocol's revert step as the sub-agents did
   it (`git checkout <sha>~1 -- <files>`).
5. Review 20's note on U5: an apply that leaves no playbook stops.
6. Files H-046, H-047, H-048 for mission 22.

## Mission 22 (scheduled 2026-10-15) — the operational findings of 2026-10-14 and the onboarding half. Spec: DESIGN §37 last paragraph and §36 "Mission 21 (specified next)". Kit after mission 21 is installed.

1. H-046: `handswho` publishes on a real state change only, compared
   without the relative-time text, with a floor on the interval; doctor
   WARNS on a public `ntfy_url` naming the daily cap and the self-hosted
   path. The laptop's who units stay stopped until this ships.
2. H-047: the daemon re-queues the kickoff for a builder job its own stop
   killed, bounded as `resume` is; the install routine stops costing a `go`.
3. H-048: under `autonomous`, a `blocked` builder verdict may consult the
   architect role (playbook rule), the consult prompt carrying the
   builder's reply in place of a review, against the same budget.
4. docs/INTEGRATION.md "Self-hosted ntfy over Tailscale" corrected from the
   2026-10-14 setup: the image `binwiederhier/ntfy`; no certificate domain
   → bind the tailnet address, plain http over Tailscale; `base-url` before
   the first start; `ntfy_topic` left under `[server]` refuses to load (the
   migration removes it); the access rule covers the who topics; the phone
   app's WebSockets option is fine without a proxy; the self-hosted server
   is the documented default for role mode.
5. Phone `progress <secret>`: job id and age, the working tree's branch,
   the last three commit subjects, the checkpoint's unit line. Handbook:
   `pipeline`'s `auto-runs` counts playbook-started runs only; `jobs`
   lists newest first.
6. Review 20's minor notes on U6: "since the last consultation" by the
   consultation's recorded sha rather than `git log --since`; the decisions
   path comparison for a builder cwd below the repository root.
7. Handbook: sub-agents refuse to author attack-shaped test content (a
   safety classifier; evidence: discotrade mission 13 U4, 2026-10-15), so a
   brief delivers such a suite as generated fixtures from a neutral spec;
   re-firing a consultation goes through the aux role's reply, never a
   direct send to the architect (refused by §31).
8. The onboarding half, as §36 lists it: HF-002 (handbook and templates
   from the installed hands), `hands project add`, the Purpose block,
   `templates/DECISIONS-owner.md` with the protocol's one-commit exception,
   the brief template's recovery rule for a `keep` answer, the handbook's
   onboarding shape, ruling round and separation rule, HF-004, HF-005, the
   first plan kit's silent apply. INSTRUCTION PASTE DUE after mission 22.


1. The architect role's write permission: `architect/settings.json` allows
   `Edit(kits/**)`, `Write(kits/**)`, `MultiEdit(kits/**)` and nothing wider;
   doctor checks exactly those; `doctor --live` for the architect writes and
   removes one file under `kits/` (laptop workaround applied 2026-10-12).
2. The runner advances the architect's (and driver's) clone to
   `origin/<branch>` before every job; doctor reports HEAD vs origin
   (laptop workaround: a transient timer pulling every minute).
3. The runner sets `HANDS_PROJECT` from the config on every role job, never
   from the environment; doctor's role rows print it (laptop workaround:
   the unit's env file).
4. HF-001: the engine reloads the playbook before deciding an apply's
   `builder.done` under autonomy; discotrade's probe test as the regression
   test; a mission-less kickoff line for this repository's playbook.
5. `answer <secret> <text>` on the command topic → `hands send --role
   builder --context keep`, origin phone, un-pauses, not held by the §8
   gate (the secret is the approval), with an optional attached file landed
   in `kit_dir`; the builder's final reply published titled `builder`;
   every answer and every owner decisions file since the architect's last
   consultation listed verbatim in its next consult prompt.
6. The hold notification under autonomy: decide before publishing; a
   buttonless "kit filed by the architect; apply approved by the playbook".
7. HF-006: `BASH_DEFAULT_TIMEOUT_MS` and `BASH_MAX_TIMEOUT_MS` set for
   builder and aux jobs unless the role's env table overrides them; the
   brief template's explicit gate timeout.
8. HF-002: the role reads the handbook and templates from the installed
   hands, not from the project's clone. HF-003: `cp` from `HANDS_CLONE` into
   `HANDS_KITS`. HF-004, HF-005: docs. The first plan kit's silent apply:
   docs. `doctor --live` exercises a real write, check and project lookup.
9. Review 18 should-fix 1–4: the Unicode full stop in `ntfy_url`; the guard
   module planted beside it; the kit record's bytes; the hardlink under
   `kits/`.
10. Project name in every notification title and in generated topic names
    (doctor warns); `hands project add <name> --repo <url>` ending with the
    filled instruction printed for pasting and the verification question;
    the Purpose block as a slot in both instruction templates;
    `templates/DECISIONS-owner.md`; the review-protocol template's
    one-commit exception for `plan: decisions <date> (owner)`; the brief
    template's recovery brief: a `keep` send after `VERDICT: question` is
    the answer, carried out, mission continued, a VERDICT line always; the
    onboarding shape and the ruling round in the handbook.

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
