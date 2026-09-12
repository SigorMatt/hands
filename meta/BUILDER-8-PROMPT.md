# BUILDER-8-PROMPT — hands mission 8: detectors, the phone channel, who

Kickoff line (the only way this mission is started or resumed):

    Read meta/BUILDER-8-PROMPT.md and execute the mission below its divider.

You are the builder for the `hands` repository. Read `DESIGN.md` (v3.7; §24
is this mission, with §2, §4, §5, §6, §8, §11, §13), `CLAUDE.md`,
`meta/CHECKPOINT.md` (a unit in progress means §R first),
`meta/reviews/REVIEW-7.md` in full, and `meta/BACKLOG.md` (items 1–6,
scheduled here). The claudewho prototype this mission folds in is at
`meta/prototypes/claudewho.py` after U0 places it there from the kit.

---

## Mission

Close review 7's blocker and should-fix 1–4; detect harness-killed tasks
and orphaned processes; add the ntfy command channel with authenticated
approvals; fold claudewho into hands as `hands who` and `handswho`; close
REVIEW-3's three deferred items. Finish with a report whose first line the
playbook can match.

## Execution model (binding)

- You are a thin orchestrator. You plan units, write the checkpoint,
  dispatch ONE sub-agent per unit (Task tool, **foreground only**), verify
  the unit cheaply, record one line, move on. You run nothing longer than
  `git status`, `git log --oneline -5`, and `./scripts/check` yourself.
- Before each unit: write `meta/CHECKPOINT.md` (unit id, intent, what
  "done" means, standing constraints). After each unit: update it and
  append one line to `meta/journal.md`.
- Every unit ends with a commit AND a push. Unpushed work does not exist.
  A unit commit carries only its own files and its body lists every one;
  never `git add -A`. The U0 commit uses the `plan:` prefix. Drafts of the
  final report live under `meta/drafts/` (git-ignored) until U-last.
- Retry a failed unit once with the sub-agent's report attached; after two
  failures mark it `blocked` in `meta/plan.md` and continue with units that
  do not depend on it.
- Never edit product code yourself. Never edit `DESIGN.md` (file a finding
  instead).
- `./scripts/check` three times before every commit.
- Your final reply begins with exactly one of: `VERDICT: mission 8
  finished` | `VERDICT: mission 8 blocked <unit>` | `VERDICT: question <one
  line>`.

## Sub-agent brief (give this to every unit sub-agent, verbatim, plus the unit)

    You are implementing one unit of hands. Read, in this order: CLAUDE.md,
    DESIGN.md sections named by the unit, meta/CHECKPOINT.md, the review or
    backlog item named by the unit, then only the files the unit touches.
    Rules: the design is the spec — where it is silent, choose the simplest
    thing and say so in the commit body; write the failing test before the
    code and confirm it fails; ./scripts/check green three times before you
    commit; one commit, `<area>: <one line>` + a body naming the unit, the
    DESIGN sections and the item, listing every file, and stating only what
    the tests prove — never a totality claim unless a test enumerates the
    whole space; never `git add -A`; push; never edit meta/plan.md,
    meta/CHECKPOINT.md, or DESIGN.md; if the unit needs a design change,
    stop and write a memo to meta/findings/FINDINGS.md instead of
    improvising; dispatch nothing in the background; report in ≤12 lines:
    sha, files, tests added, what is NOT proven.

## §R Recovery brief

If `meta/CHECKPOINT.md` names a unit in progress and the working tree is
dirty: finish that unit under the sub-agent rules if it can pass
`./scripts/check`; otherwise `git stash push -m "wip <unit> <date>"`,
record in the checkpoint where it stopped and that a stash exists, and
leave the tree clean. Then continue from that unit. Push before taking any
new unit.

## Units, in order

**U0 Plan and corrections (`plan:` commit).** `meta/plan.md`,
`meta/CHECKPOINT.md`; `meta/prototypes/claudewho.py` placed from the kit
(read-only reference for U6); ledger entry H-015 for the phone channel
decision (§24). Review 7 blocker 1: pin `hands show`'s `failure` line
through `main([..., "show", <job>])` on a failed job and on a done job.

**U1 Review 7 should-fix 2, 3, 4 (§6).** The terminating-line matcher is
anchored to the harness's exact message shape (line start, the `s;`
unit, the `Set CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS` tail) and never
overrides a job that has a `success` result, turns and exit 0; the two
over-match lines from the review are pinned as negatives. The doc sweep
reads every tracked file except binaries, excludes `meta/` history by
path but includes live instruction files under `meta/` (`BUILDER-*`,
`REVIEW-PROTOCOL.md`, `BACKLOG.md`, `ROADMAP.md`). Gate: tests.

**U2 `monitor.task_killed` (§5, §24; backlog 1).** The monitor tails each
role job's stream-json for the harness's task-killed notice (find the
exact shape in 2.1.x and quote it in a test fixture) and files
`monitor.task_killed` with the task's command line, once per task.
`docs/PLAYBOOK.md` and the §10 example gain the rule (`stop`). Gate: a
`fake_claude` emitting the notice yields the event; a normal run yields
none.

**U3 Per-job scope and orphan accounting (§5, §24; backlog 2).** The runner
starts each `claude -p` inside `systemd-run --user --scope --quiet
--unit hands-<project>-<job>` when `systemd-run` is available and the
user manager answers, else in a new process group (`start_new_session`);
`hands doctor` says which is in force. The monitor reads the scope's
`cgroup.procs` (or the process group) for the live pid set and passes it
as `--pids`; at job end, anything still alive in the set is filed as
`monitor.orphan_processes` with command lines, then the scope is stopped
(`systemctl --user stop`) or the group is killed. Gate: tests with the
process-group path (systemd may be absent in CI); a test with a
double-forking `fake_claude` proves the orphan is found and killed.

**U4 The phone channel (§8, §11, §24; backlog 5; H-015).** `[notify]`
section per §24 (`ntfy_url`, `ntfy_topic`, `cmd_topic`, `cmd_secret`,
`who_topic`, `who_cmd_topic`); `handsd` subscribes to `cmd_topic` with an
outbound long-poll (`/json?since=…`), reconnecting on error; commands
`approve <job> <secret|nonce>`, `deny <job> [reason] <secret|nonce>`,
`pause <secret>`, `resume <secret>`, `status <secret>`; a per-held-job
32-byte nonce, single-use, dying with the job, carried by Approve/Deny
action buttons on the held-job notification; the long-term secret never
appears in any notification; decisions record `decided_by: phone`; a bad
secret or nonce is logged and ignored, never answered. `hands doctor`
reports the channel on/off and refuses a `cmd_topic` without a
`cmd_secret`. `docs/INTEGRATION.md` gains the setup. Gate: tests with a
mocked ntfy stream for every command, the nonce lifecycle, and the
secret-never-in-notification property; the U4 sub-agent proves the
`decided_by: phone` record.

**U5 REVIEW-3 deferrals (backlog 3).** Should-fix 3 (doctor's hardcoded
flags), 6 (`accepted()` type), 7 (`Api.notify` failure shape) of
`meta/reviews/REVIEW-3.md`. Gate: one test each.

**U6 `hands who` and `handswho` (§4, §11, §24; backlog 6).** Port
`meta/prototypes/claudewho.py` into `src/hands/who.py`: this daemon's
jobs, held gates, pipeline and inbox come from the daemon's own state over
the socket (not by shelling out to `hands`); other `claude` processes from
/proc; interactive sessions' state from transcripts; the hierarchy,
labels, debounce and fingerprint rules of §24; `hands who` prints once;
`handswho` (a second console script) pushes on change and on
`status`/`who`/`check`/`?` from `who_cmd_topic`; `systemd/handswho.service`
optional. The prototype file is then deleted in this unit's commit. Gate:
the prototype's self-test cases ported; a rendering test with a fixed
process table and fixed daemon state.

**U7 Playbook and docs (backlog 4).** The §10 example and `PLAYBOOK.toml`
gain `monitor.task_killed` and `monitor.orphan_processes` → `stop`, and
lose `quiet_hours`; `docs/PLAYBOOK.md`, `docs/INTEGRATION.md` (optional
notifications, command channel, who), `README.md` updated; `hands doctor`
reports notifications, command channel and who as on/off. Gate: the
example loads; docs sweep green.

**U8 Final report.** `meta/FINAL-REPORT-8.md` (drafted under
`meta/drafts/`, moved in by this commit): what changed (sha per unit),
what tests prove, NOT PROVEN (mandatory: real systemd scope behaviour,
real ntfy command delivery, real task-killed notice shape), the `## Review
items` table for REVIEW-7 blocker 1 and should-fix 1–4 (1 is closed by
DESIGN v3.7, say so) and REVIEW-3 3, 6, 7. Then the verdict line.

## Acceptance

- `./scripts/check` green on the pushed tip, three consecutive runs.
- Every unit commit's body lists every file it touches; U0 is `plan:`.
- `hands --help` lists `who`; `handswho --help` works; `hands doctor` on a
  config without `[notify]` extras reports the channel and who as off, exit 0.
- `PLAYBOOK.toml` has no `quiet_hours` and has the two new stop rules.
- `meta/prototypes/` is empty or absent at the tip.
- `meta/FINAL-REPORT-8.md` exists with NOT PROVEN and the review-items
  table.
