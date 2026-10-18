# BUILDER-27-PROMPT — hands mission 27: the separation follow-up, operations and safety fixes

Kickoff line (the only way this mission is started or resumed):

    Read the builder prompt with the highest mission number in the meta directory and execute the mission below its divider.

You are the builder for the `hands` repository. Read `DESIGN.md` (v3.26;
§43 is this mission, with §10, §12, §14, §23, §24, §32, §33, §34, §36, §39,
§41 and §42), `CLAUDE.md`, `meta/CHECKPOINT.md` (a unit in progress means
§R first), `meta/reviews/REVIEW-26.md`, `meta/reviews/REVIEW-25.md`
(should-fix 1), `docs/ARCHITECT-HANDBOOK.md` and `docs/INTEGRATION.md` in
full.

---

## Mission

Close what the separation's first day showed a project's operation needs
from hands (DESIGN §43): the owner file named before every builder job but
an apply, with hands' sentences stripped wherever a stored prompt is read
(U2, H-073); `no_background.py` admitting an omitted sub-agent flag under
`CLAUDE_CODE_DISABLE_BACKGROUND_TASKS`, the wheel shipping the hook,
doctor's warn on a copy that is not the installed hands' copy, and the
variable set by default only where the role's copy is that copy (U3,
H-074); the review protocols' report contents and the wait rule, and the
guard's four read-only options (U4, H-070, H-074, H-071); a role-filed
kit that carries the playbook held for the human (U5, H-075); the operator
table's missing rows and a test that reads the reasons from the code (U6,
review 26 should-fix 2). U1 makes the base green and steady: the copies of
the DESIGN wording §43 writes (H-027, H-034, H-039), the intermittent test
(H-076, review 26 should-fix 1) and review 26's untested refusals. U0 files
H-074..H-076 and corrects FINAL-REPORT-25 (review 25 should-fix 1). It does
NOT build the harness seam or review 25's should-fix 3 (mission 28), a
local-model harness (mission 29), any M9 command or review 25's should-fix
2 (mission 30), or Claude credential profiles (the backlog); it does not
change `docs/ARCHITECT-INSTRUCTION.md`, and it makes no host change. Finish
with a report whose first line the playbook can match.

## Branch (DESIGN §35)

Pull request. This mission runs on the branch `mission-27`. U0 creates it
from `main` (`git checkout main && git pull --ff-only && git checkout -b
mission-27`). Every unit commit goes to that branch and is pushed at once
(`git push -u origin mission-27` the first time). The last unit opens the
pull request — `gh pr create --base main --head mission-27 --title "mission
27: the separation follow-up" --body-file meta/FINAL-REPORT-27.md` — waits
for the hosted review, fixes what §43 allows, and the final reply's verdict
carries the PR number. Then return the working tree to `main` (`git
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
- Every unit ends with a commit AND a push, to `mission-27`. A unit commit
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
- Your final reply begins with exactly one of: `VERDICT: mission 27
  finished pr=<number>` | `VERDICT: mission 27 blocked <unit>` | `VERDICT:
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
    -A`; push to the branch `mission-27`; never edit meta/plan.md,
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
new unit. If the tree is on `main` and `origin/mission-27` exists, `git
checkout mission-27 && git pull --ff-only` first. If `meta/journal.md`
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

**U0 Plan, branch, findings and the report correction (`plan:` commit).**
U0 is yours, not a sub-agent's: it writes only `meta/`, among it the plan
and the checkpoint a sub-agent may not touch. `meta/plan.md`,
`meta/CHECKPOINT.md`, `meta/findings/FINDINGS.md`,
`meta/FINAL-REPORT-25.md`; the branch `mission-27` created and pushed. File,
each with the evidence §43 gives and in the ledger's form: H-074 a long gate
backgrounded with no sanctioned wait, and the variable that stops the
backgrounding refused by hands' own hook (from another project's ledger, its
HF-015 and HF-016, 2026-10-18; evidence only: the project's name, the HF
ids, the date, its commit 5ca133c, its jobs 0mvdoby7d-j90u,
0mvdxwh7s-y3e4 and 0mvdxy6xp-ysvh, its hook copy's commit 3fbed1d; the
Claude Code 2.1.300 facts §43 lists) — "decided (DESIGN §43), scheduled
for U3 and U4"; H-075 a role-filed kit that carries the playbook is approved
by the engine under autonomy (found 2026-10-18 by the architect while
checking another project's budget raise) — "decided (DESIGN §43),
scheduled for U5"; H-076
`tests/test_operations.py::test_kit_apply_refuses_a_staged_name_with_dot_dot`
fails intermittently (REVIEW-26 should-fix 1: twice at b956e2a, once in the
builder's U1 gate and once in the review's run, `1 failed, 4737 passed`;
green alone, with its file and at every other commit; from mission 24,
2f9e219; and, as leads, in the architect's sandbox on 2026-10-18 at
f16d6d1 and with this kit applied, run as uid 0 on a loaded machine,
`tests/test_library.py::test_open_refuses_a_running_job` failed in both
full-suite runs and passed alone, and
`tests/test_gates.py::test_cancel_is_gated_by_default_and_approval_performs_it`
failed in one full-suite run and once alone, then passed alone) — "open,
scheduled for U1". Set H-073's status to "decided (DESIGN §43), scheduled for U2" and
H-070's and H-071's to "decided (DESIGN §42, §43), scheduled for U4".
Append under `meta/FINAL-REPORT-25.md` §3's NOT PROVEN line on the U4
warning test one dated line: `Correction 2026-10-<dd> (mission 27 U0,
review 25 should-fix 1): REVIEW-25 found that both parametrized cases,
kickoff differs and no kickoff, went red under the playbook_check.ok
mutation at src/hands/kit.py:1352; both cases pin it.` (the date the day
you write it; the quoting as the file's own). The base: the kit's DESIGN
edit to §10's example turns exactly one test red,
`tests/test_playbook.py::test_the_fixture_is_section_10s_example_verbatim`
(the fixture still carries the old rule; read in the architect's sandbox
with this kit applied); U0 records it in the checkpoint as red at its start
and why, commits only `meta/` with it red, and U1 turns it green. Any other
test red at U0 in two runs out of three stops the mission (`blocked U0`);
one red once and green twice is H-076's evidence, recorded in it. Gate: the entries
exist; `git branch -r` shows `origin/mission-27`.

**U1 The base: the DESIGN copies, the intermittent test and review 26's
untested refusals (§43 "The DESIGN wording, written here", "The
intermittent test", "Review 26's NOT PROVEN items and observations,
weighed"; H-027, H-034, H-039, H-076).** `tests/fixtures/playbook_example.toml`,
`docs/PLAYBOOK.md`, `tests/test_playbook.py`, `tests/test_docs.py`,
`tests/test_operations.py` and the product file the race is in if one is,
`tests/test_consult.py` (or the file the consult tests live in),
`meta/findings/FINDINGS.md`. The fixture and `docs/PLAYBOOK.md`'s verbatim
block take §10's example as §43 writes it; the test that lists the
example's rules says `("monitor.task_killed", "notify")`; the sentence
under the verbatim copy says the example and this repository both notify
on a killed task; `docs/PLAYBOOK.md`'s H-034 sentence and its pin in
`tests/test_docs.py` go; the rule-6 test's clause replacement, now a no-op,
becomes exact equality with DESIGN's rule; H-027's, H-034's and H-039's
statuses read "resolved by DESIGN v3.26 §43" with this commit's copies
named. H-076: find the race in
`test_kit_apply_refuses_a_staged_name_with_dot_dot` (and look at the
leads' tests with the same eye) and fix it in the test or the code; if no
cause can be found, run the test in a loop under the suite's conditions,
record the count and the result in H-076, and pin what can be pinned;
either way H-076 says what was found and its status what was done. Tests,
none of them changing product code unless one shows a defect: `consult`
refused while an architect job is queued; a refusal caused by a state
change while a phone `consult`'s attachment downloads; a refused `consult`
on an idle project with a dirty playbook stops the pipeline through §10's
load, with that load's reason. Gate: the base's red tests green; the
tests; `./scripts/check` green.

**U2 The owner file on every builder job (§43 "The owner file on every
builder job"; §39, §41; H-073).** `src/hands/daemon.py` (the dispatch
preface), `src/hands/playbook.py` (the owner files with no checkpoint update
since, the sentence, the strip helper and its readers), `src/hands/limits.py`
(the limit resume's prompt), `src/hands/api.py` (the job summary's prompt
line), `src/hands/runner.py` if the preface needs it,
`docs/ARCHITECT-HANDBOOK.md` (§4, §14's resume step and §19's route 4: hands
names the owner file itself; §R stays), `meta/findings/FINDINGS.md` (H-073
fixed), tests. When a builder job but an apply is dispatched, the sentence
§43 gives, word for word, goes before the prompt naming the owner files
§43's per-file question finds, after the journal sentence when both apply;
it is decided at dispatch, in a worker thread, and the cap counts both. An
apply is a job with a `kit_id` or a resume of one, found by following
`resumed_from` to the chain's first job. One helper strips hands' leading
sentences (the journal sentence and this one, in either order, each with
its blank line) and is what `is_kickoff`, `consults_used`, the limit
resume, the playbook `resume` action (its `answer` branch too), §36's
listing of the human's sends and the job summary line of `hands jobs` and
`status` read; `hands jobs --grep` searches the stored record whole.
Tests: a kickoff after a decisions-kit apply carries the sentence naming
the file; after the checkpoint is committed past it, none; two owner files
named oldest first; an apply job never, nor a limited or orphaned apply's
resume; a nested `meta/decisions/a/b-owner.md` and a deleted owner file are
not named; no tracked checkpoint, no sentence; an owner file committed and
then followed by a checkpoint update on a side branch merged into `HEAD` is
not named; journal and owner sentences together, in that order; at the
prompt cap the combined preface is refused with the cap's reason; a kickoff
that carried the sentence still anchors `consults_used` and still is a
kickoff; an orphaned or limited job that carried it, an orphaned `answer`
that carried the journal sentence among them, is resumed with the sender's
prompt alone (and gets a sentence again only if it is still true at its
dispatch); §36's listing and the job summary line show neither sentence.
Gate: the tests; `./scripts/check` green.

**U3 Background tasks off where the role's hook allows it (§43 rules 1–5;
§21, §23, §34, §36; H-074).** `.claude/hooks/no_background.py`,
`pyproject.toml` (the force-include), `src/hands/runner.py` (the job's
environment), `src/hands/doctor.py` (the builder and aux rows; the shipped
copy found as §34's `SHIPPED_GUARDS` is), `src/hands/config.py` if the
names belong there, `docs/INTEGRATION.md` (§21's paragraph),
`README.md` where it names the hook's rule, `CLAUDE.md`'s
background-task line if it needs the variable named, tests
(`tests/test_no_background.py`, `tests/test_runner.py`,
`tests/test_doctor.py`). Rule 1: the hook admits an `Agent` or `Task` call
whose flag is omitted or null when the variable in its environment is,
trimmed and in any case, `1`, `true`, `yes` or `on`; `true` and every
non-boolean value stay refused under it; without it nothing changes; its
Bash advice drops "up to 20 minutes"; `main` reads the variable once and
passes its state to the sub-agent check, which never reads the
environment, and each selftest case names the state it runs under, so
`--selftest` answers the same with the variable set and unset. Rule 2: the
wheel carries the hook as `hands/shipped/no_background.py`; a copy found
that is the role's own file (the same realpath) is no installed copy for
that role. Rule 3: doctor's builder and aux rows compare the cwd's hook
with the installed hands' copy by sha256 and WARN, never FAIL, on a copy
that differs or is absent, or when no installed copy is found, naming both
files and both hashes and the copy step. Rule 4: the runner sets
`CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1` for a builder or aux job only when
the role's copy is the installed hands' copy, decided at dispatch; never by
default for the driver or the architect. Rule 5: the role's env table wins
either way; a value handsd inherited reaches no role's job; doctor prints
the variable as the job will carry it, with its source, and WARNs on a
table that sets it on over a copy that is not the installed hands' copy.
One function decides rules 3–5 for both the runner and doctor. Tests: the
hook's admitted spellings (`1`, `true`, `TRUE`, ` yes `, `on`) and refused
ones (`0`, `false`, empty, absent, `2`) with an omitted flag, a null flag,
an explicit `true` and an explicit `false`, through `main` in a subprocess
with the environment set; `--selftest` exit 0 in a subprocess with the
variable `1` and with it absent; the built wheel carries the hook (read
from the build's file list, as the guard's is checked); a builder job's
environment carries `=1` with the installed copy in its cwd, lacks it with
a differing copy, with no hook and when the only copy found is the role's
own file, carries the table's value either way, and lacks a value only
handsd's own environment carried — for the builder, the aux, the driver
and the architect alike; doctor's rows for each of those cases and their
statuses. Gate: the tests; `./scripts/check` green three times, and once
more with `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1` in its environment.

**U4 How a role's session runs and waits: the protocols, the template and
the guard's read set (§43 rule 6, "H-070 and H-071, built"; §30, §42;
H-070, H-071, H-074).** `templates/REVIEW-PROTOCOL.md`,
`meta/REVIEW-PROTOCOL.md`, `templates/BUILDER-N-PROMPT.md` (the sub-agent
brief), `docs/ARCHITECT-HANDBOOK.md` (§7),
`driver/hooks/bash_guard.py`, `architect/settings.json`,
`architect/CLAUDE.md` (rule 10), `meta/findings/FINDINGS.md` (H-070 and
H-071 fixed, and H-074 fixed with U3's and this unit's shas), tests (`tests/test_kit.py` or where the protocol sentences
are pinned, `tests/test_bash_guard.py`, `tests/test_doctor.py` if the
allow-list is checked there). Both protocols drop the twelve-line count
and say what a report holds, as §43 does, and say "inside the gate's
timeout" as §43 gives it for each; the wait rule's three parts (a), (b),
(c) go into both protocols' sub-agent steps, the brief template's
sub-agent brief and the handbook's §7, word for word where §43 quotes
them, the timeout written as §43 says for each (a placeholder in the
template, 15 minutes in this repository's protocol); `tests/test_kit.py`'s
pin of "20-minute cap" follows. The guard admits `ls -R`, `git ls-tree --name-only`, `git status
--short` and `git log --date=<format>` in both guarded modes; the
allow-list gains `git -C ./repo status`; rule 10 names the Grep and Read
tools for a search of content. Tests: the report-contents sentence and the
wait rule's sentences pinned in both protocols and the template; no
`≤12 lines`, no `≤12-line` and no `20-minute` left in either protocol; the brief template
keeps its twelve lines; a kit from the templates still passes `kit check`
6 of 6; each admitted option in each guarded mode, each neighbour §43 names
still refused, and the guard's selftest totals updated. Gate: the tests;
`./scripts/check` green.

**U5 A playbook change is the owner's (§43 "A playbook change is the
owner's"; §26, §31–§34, §36; H-075).** `src/hands/playbook.py` (the
engine's approval), `src/hands/spool.py` if the stored kit's entries are
read there, `src/hands/daemon.py` (the hold's reason, if the published
hold needs a parameter), `src/hands/kit.py` (the WARN),
`architect/CLAUDE.md` (rules 3 and 8), `docs/ARCHITECT-HANDBOOK.md` (§3,
§6, §12), `templates/PLAYBOOK-missions.toml` (the role-mode kickoff note,
and the `kit applied` rule's comment) and `templates/BUILDER-N-PROMPT.md`
(the role-mode kickoff note), `meta/findings/FINDINGS.md` (H-075 fixed),
tests; never this repository's `PLAYBOOK.toml`. The engine does not approve
an architect-filed apply whose stored kit carries `PLAYBOOK.toml` or
`meta/PLAYBOOK.toml`: the check is made in `_release_kit` after
`kit_apply_problem` accepts the apply and `_kit_bytes_unchanged` verifies
the zip, never inside `kit_apply_problem`; the gate's reason stays `apply
<name>`; the hold is published with its buttons and the reason §43 gives,
passed to the daemon's hold seam as a parameter, wherever the engine
publishes such a hold, a paused pipeline's included; once the human approves it, no engine
kickoff, the playbook's `kit applied` rule fires; `hands kit check` prints
the `WARN playbook:` line §43 describes. Tests: under autonomy an
architect-filed kit carrying `PLAYBOOK.toml`, one carrying
`meta/PLAYBOOK.toml`, and one whose playbook switches the series to phone
mode, are held with buttons, the published reason naming the path, the
gate's reason still `apply <name>`, and not approved by the engine; the
same over a paused pipeline, its published reason naming the path too; one
without a playbook is approved by the engine, unchanged; the consultation's
end is not an escalation and the `next kit` wait does not stop for a kit
"not filed"; after the human approves the held one, no engine kickoff and
the `kit applied` rule fires; a denial as today; the kit-check WARN when
the repository's playbook or the kit's own is role mode with autonomy, and
none for a kit that carries no playbook or one judged entirely in phone
mode; a kit from the templates still passes `kit check` 6 of 6. Gate: the
tests; `./scripts/check` green.

**U6 The operator table follows the code (§43 "The operator table follows
the code"; §42; review 26 should-fix 2).** `docs/ARCHITECT-HANDBOOK.md`
(§19), `tests/test_operator_table.py`. Rows, each with its four columns and
one of the eight routes: the playbook-load stop "the playbook is not the
committed copy, so no rule can be trusted to fire: …"; the phone's
follow-up "apply <name>: <why>; the commit message is the default
'<message>'"; the hold of U5 (route 2, then `go`); and any other stop or
published line U1–U5 added. The test reads the source of the engine, the
limit manager, the daemon and the phone (`src/hands/playbook.py`,
`src/hands/limits.py`, `src/hands/daemon.py`, `src/hands/phone.py`, and
any module those call to stop or publish) by `ast`: every string or
f-string passed as a stop's reason or a publish's title or message to the
receivers §43 names, read as §43 says — a parameter at its callers, a
helper's returned string at its `return` statements, an f-string with each placeholder written `<…>` and matched
on its literal pieces in order, a reason passed through a name traced to
the literals assigned to it in the same function, a constant title read as
its value — found in a row of §19; an exemption list, each entry with its
reason. The commit body names the wrong changes that would turn it red (a
stop reason added without a row; a row removed). Gate: the test red with
one row removed and green with it, shown for three rows — a literal
reason, an f-string that begins with a placeholder, a reason passed
through a name; `./scripts/check` green.

**U7 Final report, the pull request and the hosted review's findings.**
`meta/FINAL-REPORT-27.md` (drafted under `meta/drafts/`, moved in by this
commit): what changed (sha per unit), what tests prove, NOT PROVEN
(mandatory: no real builder has run under the default, started a
sub-agent through the fixed hook, or had a gate end at its timeout; no
project with the old hook has been doctor-checked on the laptop; no real
role-filed kit carrying a playbook has been held; no real decisions kit
and `go` has run on a brief that predates the template), and the `## Review
items` section: review 26's should-fix 1 and 2 with the units that closed
them, review 25's should-fix 1 closed by U0, 2 carried to mission 30 and 3
to mission 28 by DESIGN §43. Then open the pull request (see Branch) and
wait up to ten minutes for the bot, the hosted reviewer, in one-minute
foreground steps: `hands hosted-review <pr>` exits 3 with "no bot comment
yet", writing nothing, until the bot has posted its Code Review comment,
which is the wait, never a clean review; exit 4 means the findings could
not be parsed against the header counts, so read the archived comment
itself. The command archives the bot's words under
`meta/reviews/hosted/PR-<pr>/<k>/` and takes the verdict from the Code
Review comment only. Fix each finding that is within §43 by a sub-agent
under the sub-agent rules, committed and pushed to the branch; a finding
that needs a design decision is filed in `meta/findings/FINDINGS.md`, never
fixed in silence. Push, then write the `## Hosted review` table into the
final report, one row per finding, the finding verbatim and one
disposition: `fixed in <sha>` | `dismissed: <reason>` | `finding H-nnn
filed`; commit that table with the archive directory, push, and return the
tree to `main`. Then the verdict line.

## Acceptance

- `./scripts/check` green on the pushed tip, three consecutive runs, and
  once with `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1` in its environment.
- Every unit commit's body lists every file it touches; U0 is `plan:`.
- H-074, H-075 and H-076 are filed; H-027, H-034, H-039, H-070, H-071,
  H-073, H-074, H-075 and H-076 carry the status their unit gave them.
- A builder job but an apply carries §43's owner sentence when an owner
  file was committed after the checkpoint's last update, and no reader of a
  stored prompt mistakes hands' sentences for the sender's (U2's tests).
- The hook admits an omitted flag under the variable's true spellings only;
  the wheel ships it; a builder or aux job carries the variable only by §43's
  rules 4 and 5; doctor warns on a copy that is not the installed hands'
  copy (U3's tests).
- Both review protocols state what a report holds, the wait rule and the
  gate's timeout; the guard admits the four options (U4's tests).
- A role-filed kit carrying the playbook is held for the human (U5's tests).
- §19 has a row for every stop and published line the code writes, held by
  a test that reads the code (U6).
- `meta/FINAL-REPORT-27.md` exists with NOT PROVEN, the review-items
  section and the `## Hosted review` table.
- The PR from `mission-27` to `main` is open (`gh pr list --head mission-27
  --state open`), and the tree is on `main`.
