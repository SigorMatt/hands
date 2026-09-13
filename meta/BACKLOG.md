# BACKLOG — items the architect has committed to future missions

Maintained by the architect; the builder does not act on this file. Each
item names the mission it is scheduled for; unscheduled items say so.

## Mission 8 — DONE 2026-09-13 (review 8: blockers=0). Items 1–6 landed.

## Mission 9 — DONE 2026-09-13 (review 9: blockers=0).

## Mission 10 — the phone loop closed (decided 2026-09-13)

1. **`[series] kickoff`** in the playbook: the fixed kickoff line of the
   series (agile-skills form: the mission's kickoff line; spanweave form:
   `Execute WORKPLAN.md run N`, with N from the playbook's state).
2. **`go <secret>`** on `cmd_topic` sends that line as a `cli`-origin
   `clear` send to the builder; nothing else can be started from the
   phone. Recorded as `origin: phone`.
3. **Kit transport:** an ntfy message on `cmd_topic` with an attachment
   and the body `kit <secret>` is fetched by handsd into
   `files.kit_dir` (default `~/Downloads`) under the attachment's own
   name, size-capped (`files.kit_max_mb`, default 20), never executed,
   never unzipped; the inbox and the phone get `kit received <name>`.
4. **Who view:** an interactive session is matched to its transcript by
   pid (the transcript records it) rather than by directory, so a builder
   job in the same cwd is never shown under the human's session.
5. `docs/INTEGRATION.md`: the closed loop, step by step, phone only.
6. **The architect's handbook and `hands kit check`.**
   `docs/ARCHITECT-HANDBOOK.md`: what a kit is and how it is applied, the
   two plan forms (missions, runs) with a template brief and playbook for
   each, the `VERDICT:` contract and how playbook regexes must match the
   brief's final-reply lines, the review protocol, decisions files, PR per
   run with auto-merge, the closed phone loop. `templates/` ships the
   files. `hands kit check <zip|dir>`: playbook loads; every `verdict`
   regex has a matching literal among the brief's final-reply lines; the
   brief's kickoff line equals `[series] kickoff`; required files present;
   no `quiet_hours`; no "as before". Runnable from a fresh sandbox via
   `uv tool install git+https://github.com/SigorMatt/hands`, so an
   architect chat checks its kit before emitting it.
   `docs/ARCHITECT-INSTRUCTION.md` gains: clone hands, read the handbook,
   run `hands kit check`, before writing any kit.

## Mission 11 — the driver role and `consult` (decided 2026-09-13)

1. **A third role, `driver`**, headless, started by handsd on a `consult`
   action: cwd is its own directory with a fetch-only clone (as the
   interactive driver), `driver/CLAUDE.md` rules 1–10, and a guard
   tighter than the builder's: read-only git, `hands show|jobs|inbox|
   pipeline|status|tail`, `hands send --context keep` to the role that
   asked, `hands resume`; never `approve`, `deny`, `send --context clear`,
   `put`, or any write.
2. **`then = "consult"`** playbook action: sends the driver role the
   event, the job record and the last reply verbatim, asking for
   `VERDICT: resolved <action, citing the brief or DESIGN section>` or
   `VERDICT: escalate <reason>`; follow-up rules on `driver.done` match
   those; `escalate` and an unrecognised verdict stop and notify;
   `[limits] max_consults` per mission (default 2), then stop.
3. Which events may consult is the playbook's choice; the example routes
   `builder.done` with `^VERDICT: question` and an unrecognised builder
   verdict; never review outcomes, never held gates.
4. Every consultation is an inbox event and a ledger line the cold review
   reads and may grade; the driver role's reply is stored verbatim.

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
