# BUILDER-28-PROMPT — hands mission 28: a pause that holds the next step

Kickoff line (the only way this mission is started or resumed):

    Read the builder prompt with the highest mission number in the meta directory and execute the mission below its divider.

You are the builder for the `hands` repository. Read `DESIGN.md` (v3.27;
§44 is this mission, with §6, §10, §19, §31, §32, §33, §36, §38, §39 and
§43), `CLAUDE.md`, `meta/CHECKPOINT.md` (a unit in progress means §R
first), `meta/reviews/REVIEW-27.md`, `meta/findings/FINDINGS.md` (H-077),
`docs/ARCHITECT-HANDBOOK.md` and `docs/PLAYBOOK.md` in full.

---

## Mission

Make a human pause hold the next step instead of dropping it (DESIGN §44,
H-078, from another project's HF-017): under a pause sent by `pause`, a
role's end that would start the next step is kept, one per role, and
everything else is as under any pause and notified; `resume` rules still
continue the running step until a stop has been suppressed under the
pause; only `resume` ends a human pause and it replays
what was kept; and the engine publishes `at rest` once nothing is running
(U1, U2). Close review 27's three should-fix items (U2, U3) and
carry out the ruling on H-077 (U4). File H-078 and set H-077's status (U0).
It does NOT build the pull-request gate (mission 29), the harness seam or
review 25's should-fix 3 (mission 30), a local-model harness (mission 31),
any M9 command or review 25's should-fix 2 (mission 32), or Claude
credential profiles (the backlog); it does not change
`docs/ARCHITECT-INSTRUCTION.md` or this repository's `PLAYBOOK.toml`, and it
makes no host change. Finish with a report whose first line the playbook
can match.

## Branch (DESIGN §35)

Pull request. This mission runs on the branch `mission-28`. U0 creates it
from `main` (`git checkout main && git pull --ff-only && git checkout -b
mission-28`). Every unit commit goes to that branch and is pushed at once
(`git push -u origin mission-28` the first time). The last unit opens the
pull request — `gh pr create --base main --head mission-28 --title "mission
28: a pause that holds the next step" --body-file meta/FINAL-REPORT-28.md` —
waits for the hosted review, fixes what §44 allows, and the final reply's
verdict carries the PR number. Then return the working tree to `main` (`git
checkout main && git pull --ff-only`): the next kit apply and the next
kickoff run in this tree, on `main`.

## Execution model (binding)

- You are a thin orchestrator. You plan units, write the checkpoint,
  dispatch ONE sub-agent per unit (Task tool, foreground only), verify the
  unit cheaply, record one line, move on. You run nothing longer than `git
  status`, `git log --oneline -5`, `hands hosted-review <pr>` and
  `./scripts/check` yourself.
- Before each unit: write `meta/CHECKPOINT.md` (unit id, intent, what
  "done" means, standing constraints). After each unit: update it and
  append one line to `meta/journal.md`.
- Every unit ends with a commit AND a push, to `mission-28`. A unit commit
  carries only its own files and its body lists every one; never `git add
  -A`. The U0 commit uses the `plan:` prefix. Drafts of the final report
  live under `meta/drafts/` (git-ignored) until the last unit.
- Retry a failed unit once with the sub-agent's report attached; after two
  failures mark it `blocked` in `meta/plan.md` and continue with units that
  do not depend on it. A sub-agent that reports `refused: <one line>` is
  not retried: mark the unit `[b] refused` and continue likewise.
- Never edit product code yourself. Never edit `DESIGN.md` (file a finding
  instead).
- `./scripts/check` three times before every commit, each run its own
  foreground call with an explicit timeout of 15 minutes (900000 ms), the
  command written `./scripts/check; echo "check-exit=$?"` so its end shows
  in its output. If a run is moved to the background anyway, wait with one
  foreground command that blocks until the output file shows the marker —
  `until grep -q '^check-exit=' <file>; do sleep 5; done`, with an explicit
  timeout — never a `sleep` of 25 seconds or more as a command's first
  statement, never Monitor or a background task, and never end your turn
  before the run has finished.
- Your final reply begins with exactly one of: `VERDICT: mission 28
  finished pr=<number>` | `VERDICT: mission 28 blocked <unit>` | `VERDICT:
  question <one line>`.

## Sub-agent brief (give this to every unit sub-agent, verbatim, plus the unit)

    You are implementing one unit of hands. Read, in this order: CLAUDE.md,
    DESIGN.md sections named by the unit, meta/CHECKPOINT.md, the finding or
    review item(s) named by the unit, then only the files the unit touches.
    Rules: the design is the spec — where it is silent, choose the simplest
    thing and say so in the commit body; write the failing test before the
    code and confirm it fails; ./scripts/check green three times before you
    commit, each run a foreground call with a 15-minute (900000 ms)
    timeout, written `./scripts/check; echo "check-exit=$?"`; if a run is
    moved to the background anyway, wait with one foreground command that
    blocks until its output file shows the marker — `until grep -q
    '^check-exit=' <file>; do sleep 5; done`, with an explicit timeout —
    never a `sleep` of 25 seconds or more as a command's first statement,
    never Monitor or a background task, and never end your turn before the
    run has finished; one commit, `<area>: <one line>` + a body naming the
    unit, the DESIGN sections and the item, listing every file, and stating
    only what the tests prove — never a totality claim unless a test
    enumerates the whole space; a commit that changes only tests names in
    its body each wrong change that would make them red; a commit that adds
    or deletes a non-test file names it as added or deleted; never `git add
    -A`; push to the branch `mission-28`; never edit meta/plan.md,
    meta/CHECKPOINT.md, or DESIGN.md; if the unit needs a design change,
    stop and write a memo to meta/findings/FINDINGS.md instead of
    improvising; if you cannot or will not produce what the unit asks,
    report `refused: <one line>` and stop, changing nothing; dispatch
    nothing in the background; never require a real `claude`, `gh`,
    `systemctl`, ntfy server, harness binary or `git` remote in tests (fakes
    on PATH, a local HTTP stub and local bare repositories, as
    tests/fake_claude.py is); a test that touches a project config or spool
    writes it under the test's temporary home, never the real `~/.hands`; a
    test whose outcome depends on `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS`
    sets or clears it itself; the only `claude` commands a unit may run are
    `claude --version` and `claude --help` — anything else about the
    installed CLI is read from its package's files; never print, commit or
    quote a key, a token or a sign-in file — write `[redacted]`; report in
    ≤12 lines: sha, files, tests added, what is NOT proven.

## §R Recovery brief

If `meta/CHECKPOINT.md` names a unit in progress and the working tree is
dirty: finish that unit under the sub-agent rules if it can pass
`./scripts/check`; otherwise `git stash push -m "wip <unit> <date>"`,
record in the checkpoint where it stopped and that a stash exists, and
leave the tree clean. Then continue from that unit. Push before taking any
new unit. If the tree is on `main` and `origin/mission-28` exists, `git
checkout mission-28 && git pull --ff-only` first. If `meta/journal.md`
alone is dirty when you start, commit it first as `journal: consultation
lines` and push. A sentence in square brackets beginning `[hands:` before
your prompt is hands', not the human's: do what it says first. If a `plan:
decisions <date> (owner)` commit is on the branch after the checkpoint's
last update and the checkpoint does not record its "For the builder" steps
as done, carry them out first, record them in the checkpoint, and continue.
A `keep` send that arrives after you replied `VERDICT: question` is the
answer: carry it out, continue the mission from the checkpoint, and end
that reply with one of the mission's `VERDICT:` lines, always, even when
the answer came with a file to commit first.

## Units, in order

**U0 Plan, branch and findings (`plan:` commit).** U0 is yours, not a
sub-agent's: it writes only `meta/`, among it the plan and the checkpoint a
sub-agent may not touch. `meta/plan.md`, `meta/CHECKPOINT.md`,
`meta/findings/FINDINGS.md`; the branch `mission-28` created and pushed.
File H-078, in the ledger's form, with the evidence §44 gives: a human
pause drops the event that would start the next step, `resume` replays
nothing, nothing is published at rest, and a restart under a pause consumes
the builder's orphan (from another project's ledger, its HF-017,
2026-10-19; evidence only: the project's name, discotrade, the HF id, the date, its
builder job 0mve1pq5x-jej2, the aux guard's `VERDICT: blocked busy` line,
the owner commits waiting since 2026-10-18 21:14; the code read at f16d6d1
and d587fa6: `playbook.py` `on_event`'s paused branch, `pause`, `resume`,
`_unpause`, `daemon.py` `_feed_orphans`) — "decided (DESIGN §44),
scheduled for U1 and U2". Set H-077's status to "decided (DESIGN §44:
casefolded match against the configured playbook path and the two fixed
names), scheduled for U4". Gate: the entries exist; `git branch -r` shows
`origin/mission-28`; `./scripts/check` green (the kit changes no file a
test reads but DESIGN.md's appended §44, meta/ROADMAP.md and
meta/BACKLOG.md; a red test at U0 in two runs out of three stops the
mission, `blocked U0`).

**U1 A human pause holds the next step (§44 rules 1, 2, 3, 5 and 6; §6,
§10, §19, §29, §31, §32, §33, §38; H-078).** `src/hands/playbook.py` (the
engine: `on_event`'s paused branch, `stop`, `pause`, `resume`, `_unpause`,
`on_job_start`'s un-pause, `PipelineState` and its persistence,
`pipeline()`), `src/hands/api.py` and `src/hands/phone.py` (the `go` and
`consult` refusals under a human pause, the `resume` refusal when the
playbook does not load, `status` naming the human pause and the kept ends),
`src/hands/cli.py` (`hands pipeline`'s `kept` lines; `hands show` printing
`resumed_from`, which DESIGN §6 lists and the prose view omits), tests. A
human pause is `paused_by` `cli` or `phone` set by `pause`; any other stop
is not one and keeps today's behaviour. Under a human pause: a builder,
aux or driver `<role>.done` whose decision would send, consult or stop (a
rule's action, §10's own stop for no rule, no matching verdict or no
`VERDICT:` line) or the engine's kickoff after an apply the engine approved
is kept, one per role (a later end replaces the earlier, with a
`pipeline.kept_replaced` inbox event); a role's end whose decision is a
`notify` fires at once; a `resume` rule fires; `*.limited`, `job.held` and
`job.denied` fire nothing; an architect consultation's end is decided as
under any pause (no engine approval; its apply held for the human); a
driver's end under §28's enforced stop is that stop, not kept; every
stop the pause suppresses is also notified once (but not a `pause` over
the pause, nor a refused `resume`), the pause and the kept ends staying,
and from the first such stop on a `resume` rule fires nothing under that
pause (the mark persisted). Whether an end is kept is decided at arrival
with the playbook as loaded at that moment; §10's load at a job's start
is unchanged, and only H-044's reload at an engine-approved apply's end
waits for `resume`'s reload. A job of an un-pausing origin starting under a human pause
does not un-pause it; `go` and `consult` are refused under it, naming
`resume`; a `pause` over it is a no-op that keeps `paused_by` and the kept
ends. `resume` reloads the playbook first and is refused, the pause and
the kept ends staying, when a playbook file exists and does not load or
when ends are kept and there is no playbook; with no playbook and nothing
kept it un-pauses as today. Otherwise it un-pauses and decides the kept
ends in order as if each had just arrived, up to and including the first
that starts a job or stops (a replayed send the API refuses is §10's
could-not-send stop), and discards the rest (one `pipeline.kept_discarded`
inbox event), naming them in a notification. Kept ends, the `at rest`
mark and the suppressed-stop mark live in `pipeline.json`.
Tests, on a role-mode autonomous playbook unless named: a human pause while
the builder runs, its `builder.done` kept and no review started, then
`resume` starting the review; the same for a review's end (the
consultation kept until `resume`) and an engine-approved apply's end (the
kickoff kept); a consultation ending under the pause leaving its kit's
apply held for the human, no engine approval, and no engine kickoff after
the human approves; a `builder.done` whose rule is `stop` (a question)
kept and stopping at `resume`; a `notify` role end firing at once; the
human's own send under the pause replacing the kept `builder.done`; a
decisions kit's apply held, approved and ended under the pause without
un-pausing it, the kept end still kept and no stop for the hold; a monitor
tripwire's `stop` rule under the pause notified once, the kept end staying;
a `max_resumes` stop under the pause notified; a tripwire suppressed and
notified under the pause, then a restart, the orphaned builder NOT
resumed; a driver's `escalate` end under the pause notified and not kept;
an engine-approved apply that commits a playbook which does not load:
its end kept for the kickoff, then `resume` refused with the load's
reason; a replayed `keep` send the API refuses stopping the replay; `go`
and `consult` refused under a human pause; `pause` then `resume` with no
playbook and nothing kept un-pausing (doctor's install check); a second `pause` keeping everything, setting no suppressed-stop mark, and
a restart after it still resuming the orphaned builder; a playbook edited
and committed at rest used by the replay; `resume` refused while the
playbook does not load, then accepted after; two kept ends where the first
replayed stops and the second is discarded and named; two kept ends where
the first replayed starts a job and the second is discarded and named; a limited builder
under the pause resumed by §6 and its end kept; a restart under a human
pause resuming the orphaned builder through `builder.orphaned → resume`
and keeping the kept ends; a restart under a rule's stop resuming nothing
(today's behaviour); this repository's phone-mode `PLAYBOOK.toml` under a
pause (the review's `blockers=0` stop kept, then stopping at `resume`);
`hands pipeline`'s `kept` lines, `status`'s line, `hands show`'s
`resumed_from`; a pause over an existing stop still a no-op; an unpaused
pipeline unchanged. Gate: the tests; `./scripts/check` green.

**U2 At rest, the documents and the table's titles (§44 rule 4,
"Documentation", review 27 should-fix 3; §19).** `src/hands/playbook.py`
(and `src/hands/daemon.py` or `src/hands/limits.py` if the moment is
decided there), `docs/ARCHITECT-HANDBOOK.md` (§10, §14, §18, §19),
`docs/PLAYBOOK.md`, `docs/OPERATIONS.md`, `tests/test_operator_table.py`,
`meta/findings/FINDINGS.md` (H-078 resolved with U1's and this unit's
shas), tests. Under a human pause, the first moment no job is running,
queued or held and no §6 resume is scheduled, one notification titled
`hands: at rest`, naming each kept end (role, job id, verdict line cut to
100 characters) or saying none is kept; the moment checked when the pause
is sent and on every terminal transition of a job (done, failed, limited,
killed, orphaned, cancelled while running or queued, denied, a job the
runner could not spawn); once per pause, the mark persisted, and again
with the new list when a kept end is replaced after it; at once when the
pause finds nothing running. The handbook,
docs/PLAYBOOK.md and docs/OPERATIONS.md say what §44's documentation list
says. §19 gets rows for `at rest`, the `go` and `consult` refusals under a
human pause, a `resume` refused because the playbook does not load, a stop
notified under a human pause, and a replay that stopped with ends
discarded. The operator table's reader matches a title against the start
of a row's title, never anywhere in the column. Tests: `at rest` published
once when the kept builder's end arrives and nothing else runs; not while
a review runs, a hold waits on the human, or a §6 resume is scheduled; at
once for a pause over an idle pipeline; after a held job is denied and
nothing runs; after the human's own running job is cancelled, and after
a queued one is cancelled, and nothing else runs; after a job fails with
no resume rule; not again after a restart; again, with the new list, when a
kept end is replaced after it; its body naming the kept end; not
published under a stop that is not a human pause; the reader red when a
one-word title (`go`) has no row of its own and green with it. Gate: the
tests; `./scripts/check` green.

**U3 Review 27's two code should-fix items (§44 "Review 27's should-fix
items" 1 and 2; §43).** `src/hands/daemon.py` (`_held_reason`,
`_publish_held`), `src/hands/doctor.py` (both `--live` turns' environments:
the role turn and the architect's kits turn), `src/hands/runner.py` if
`job_env` needs a seam, tests. No zip read or hash for a hold's published
reason runs on the event loop: it runs in a worker thread, or is computed
off the loop before the notification is published. Both of `hands doctor
--live`'s turns build their environment through `runner.job_env` (or the
one decision it uses), so each carries what a real job carries. Tests: the
hold-reason read happens on a thread other than the loop's (red when it
runs on the loop); a held architect apply's notification still carries
§43's reason on both paths; each live turn with an inherited
`CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1` and a stale hook carries no value,
and the builder's live turn with the installed copy carries `=1`. Gate: the
tests; `./scripts/check` green.

**U4 H-077, ruled (§44 "H-077, ruled"; §26, §43).** `src/hands/spool.py`
(`stored_kit_playbooks`), `src/hands/playbook.py` (the engine passes the
configured path), `src/hands/kit.py` (`_owner_warning`, judging the
repository's playbook at the configured path too, and the line saying which
names were known), `meta/findings/FINDINGS.md` (H-077 resolved), tests. One
test of "carries the playbook": an entry whose casefolded path equals the
casefolded configured playbook path (`[playbook] path`, read as a
repository path) or either fixed name. `kit check`'s `playbook` check is
unchanged (it loads an entry at a fixed name only). Tests: `playbook.toml`,
`Playbook.toml`, `meta/playbook.toml` and `Meta/PLAYBOOK.toml` each held by
the engine and warned by `kit check`; a configured `ops/rules.toml` and
`OPS/Rules.toml` held under that configuration, and the WARN given when the
repository's playbook at `ops/rules.toml` is role mode with autonomy; `kit
check` without a configuration warning on the fixed names and saying it
knows only those; an ordinary kit unchanged. Gate: the tests;
`./scripts/check` green.

**U5 Final report, the pull request and the hosted review's findings.**
`meta/FINAL-REPORT-28.md` (drafted under `meta/drafts/`, moved in by this
commit): what changed (sha per unit), what tests prove, NOT PROVEN
(mandatory: no real phone `pause` and `resume` has run on a role-mode
series, no real `at rest` has reached a phone, no real restart under a
human pause has resumed a builder), and the `## Review items` section: review 27's
should-fix 1–3 with the units that closed them, H-077 closed by U4. Then
open the pull request (see Branch) and wait up to ten minutes for the bot,
the hosted reviewer, in one-minute foreground steps: `hands hosted-review
<pr>` exits 3 with "no bot comment yet", writing nothing, until the bot has
posted its Code Review comment, which is the wait, never a clean review;
exit 4 means the findings could not be parsed against the header counts, so
read the archived comment itself. The command archives the bot's words
under `meta/reviews/hosted/PR-<pr>/<k>/` and takes the verdict from the
Code Review comment only. Fix each finding that is within §44 by a
sub-agent under the sub-agent rules, committed and pushed to the branch; a
finding that needs a design decision is filed in `meta/findings/FINDINGS.md`,
never fixed in silence. Push, then write the `## Hosted review` table into
the final report, one row per finding, the finding verbatim and one
disposition: `fixed in <sha>` | `dismissed: <reason>` | `finding H-nnn
filed`; commit that table with the archive directory, push, and return the
tree to `main`. Then the verdict line.

## Acceptance

- `./scripts/check` green on the pushed tip, three consecutive runs.
- Every unit commit's body lists every file it touches; U0 is `plan:`.
- H-078 is filed and resolved; H-077 is resolved.
- Under a human pause a role's end that would start the next step is kept
  and replayed by `resume` (the first that starts a job or stops, the
  rest discarded and named), and every other stop is notified; a restart
  under a human pause resumes the orphaned builder unless a stop has
  been suppressed under that pause; `go` and `consult` are refused under a
  human pause (U1's tests).
- `hands: at rest` is published once per human pause, naming the kept
  event (U2's tests).
- No hold reason reads a zip on the event loop; `doctor --live` builds its
  environment as a job does; the table's reader matches titles at a row's
  start (U2's and U3's tests).
- A kit entry naming the playbook in another case, or the configured
  playbook path, is held and warned (U4's tests).
- `meta/FINAL-REPORT-28.md` exists with NOT PROVEN, the review-items
  section and the `## Hosted review` table.
- The PR from `mission-28` to `main` is open (`gh pr list --head mission-28
  --state open`), and the tree is on `main`.
