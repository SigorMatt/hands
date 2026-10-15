# BUILDER-21-PROMPT — hands mission 21: closer for review 20

Kickoff line (the only way this mission is started or resumed):

    Read the builder prompt with the highest mission number in the meta directory and execute the mission below its divider.

You are the builder for the `hands` repository. Read `DESIGN.md` (v3.20; §37
is this mission, with §6, §32, §35, §36), `CLAUDE.md`, `meta/CHECKPOINT.md`
(a unit in progress means §R first), and `meta/reviews/REVIEW-20.md` in
full.

---

## Mission

Close review 20 (DESIGN §37): the cancel race during the clone advance
(blocker 1), the live hook that a planted module still shadows, writes
through a hardlink under `kits/`, the provenance of a phone `answer`,
`doctor --live` for the architect judging the right clone and never
deleting a kit it did not make, the protocol's revert step, and the apply
that leaves no playbook. It also files the findings the laptop raised while
mission 20 ran (H-046..H-048), which mission 22 builds. It does NOT touch
onboarding, `hands project add`, the handbook's new sections, `handswho` or
the notification docs (mission 22). Finish with a report whose first line
the playbook can match.

## Branch (DESIGN §35)

Pull request. This mission is a closer: it continues the open branch
`mission-20`, whose pull request #2 is open. U0 continues it (`git checkout
main && git pull --ff-only && git checkout mission-20 && git pull --ff-only
&& git merge main`), merging `main` in first so this kit's plan files and
`meta/reviews/REVIEW-20.md` are present; a merge conflict is a `VERDICT:
question`, never a resolution you invent. Every unit commit goes to
`mission-20` and is pushed at once. The last unit opens no pull request: it
pushes, takes the open PR's number from `gh pr list --head mission-20
--state open --json number`, and the final reply's verdict carries that
number. Then return the working tree to `main` (`git checkout main && git
pull --ff-only`): the next kit apply and the next kickoff run in this tree,
on `main`.

## Execution model (binding)

- You are a thin orchestrator. You plan units, write the checkpoint,
  dispatch ONE sub-agent per unit (Task tool, foreground only), verify the
  unit cheaply, record one line, move on. You run nothing longer than `git
  status`, `git log --oneline -5`, and `./scripts/check` yourself.
- Before each unit: write `meta/CHECKPOINT.md` (unit id, intent, what
  "done" means, standing constraints). After each unit: update it and
  append one line to `meta/journal.md`.
- Every unit ends with a commit AND a push, to `mission-20`. A unit commit
  carries only its own files and its body lists every one; never `git add
  -A`. The U0 commit uses the `plan:` prefix. Drafts of the final report
  live under `meta/drafts/` (git-ignored) until the last unit.
- Retry a failed unit once with the sub-agent's report attached; after two
  failures mark it `blocked` in `meta/plan.md` and continue with units that
  do not depend on it.
- Never edit product code yourself. Never edit `DESIGN.md` (file a finding
  instead).
- `./scripts/check` three times before every commit, each run its own
  foreground call with an explicit timeout of 20 minutes.
- Your final reply begins with exactly one of: `VERDICT: mission 21
  finished pr=<number>` | `VERDICT: mission 21 blocked <unit>` | `VERDICT:
  question <one line>`.

## Sub-agent brief (give this to every unit sub-agent, verbatim, plus the unit)

    You are implementing one unit of hands. Read, in this order: CLAUDE.md,
    DESIGN.md sections named by the unit, meta/CHECKPOINT.md, the review
    item(s) named by the unit in meta/reviews/REVIEW-20.md, then only the
    files the unit touches. Rules: the design is the spec — where it is
    silent, choose the simplest thing and say so in the commit body; write
    the failing test before the code and confirm it fails; ./scripts/check
    green three times before you commit, each run a foreground call with a
    20-minute timeout; one commit, `<area>: <one line>` + a body naming the
    unit, the DESIGN sections and the review item, listing every file, and
    stating only what the tests prove — never a totality claim unless a
    test enumerates the whole space; a commit that changes only tests names
    in its body each wrong change that would make them red; never `git add
    -A`; push to the branch `mission-20`; never edit meta/plan.md,
    meta/CHECKPOINT.md, or DESIGN.md; if the unit needs a design change,
    stop and write a memo to meta/findings/FINDINGS.md instead of
    improvising; dispatch nothing in the background; never require a real
    `claude`, `gh` or `git` remote in tests (fakes on PATH and local bare
    repositories, as tests/fake_claude.py is); report in ≤12 lines: sha,
    files, tests added, what is NOT proven.

## §R Recovery brief

If `meta/CHECKPOINT.md` names a unit in progress and the working tree is
dirty: finish that unit under the sub-agent rules if it can pass
`./scripts/check`; otherwise `git stash push -m "wip <unit> <date>"`,
record in the checkpoint where it stopped and that a stash exists, and
leave the tree clean. Then continue from that unit. Push before taking any
new unit. If the tree is on `main` and `origin/mission-20` exists, `git
checkout mission-20 && git pull --ff-only` first; if `main` has commits the
branch lacks, `git merge main` before the next unit (a conflict is a
`VERDICT: question`). A `keep` send that arrives after you replied
`VERDICT: question` is the answer: carry it out, continue the mission from
the checkpoint, and end that reply with one of the mission's `VERDICT:`
lines, always, even when the answer came with a file to commit first.

## Units, in order

**U0 Plan, the branch and the findings (`plan:` commit).** `meta/plan.md`,
`meta/CHECKPOINT.md`; the branch `mission-20` continued with `main` merged
in, as the Branch section says. File in `meta/findings/FINDINGS.md`, one
entry each, status `open`, scheduled for mission 22, with the evidence §37
gives: H-046 `handswho` publishes every ~20 s and spends the public
broker's daily cap; H-047 a `handsd` restart kills the running builder job
and nothing resumes it; H-048 under `autonomous` a builder's `blocked`
verdict stops for the human instead of consulting the role. Carry review
20's blocker 1 and should-fix 1–6 into the units below by their numbers.
Gate: the three entries exist; `git log --oneline -3` on `mission-20` shows
the merge of `main` and this commit; `git status` clean.

**U1 The cancel race (§37; §6; review 20 blocker 1).** `src/hands/spool.py`,
`src/hands/runner.py`, tests. `Spool.transition` reloads the record by id
from disk before judging the edge and judges it against that record; a
caller holding a stale object gets `IllegalTransition` from the on-disk
state, and the updates it carries are not written. The runner reloads the
job after `advance_clone` returns; when the state is no longer `queued` it
spawns nothing and leaves the record as it is. Tests: a cancel during a
slow fake advance (an `advance_clone` that waits on an event) ends with the
record `killed`, no spawn, and no inbox event after `job.killed`; a
transition from a stale object against a changed on-disk record raises.
Gate: both tests; `./scripts/check` green.

**U2 The live hook and writes through a hardlink (§37; review 20
should-fix 1, 2; REVIEW-18 should-fix 2, 4).** `driver/settings.json`,
`architect/settings.json`, `driver/hooks/bash_guard.py`,
`src/hands/doctor.py`, tests. The hook commands become `python3 -I
"$CLAUDE_PROJECT_DIR"/.claude/hooks/bash_guard.py` and the same with
`--write`; doctor's guard row FAILS, naming the file, when any `.py` file
or package directory other than the guard sits beside it, and its self-test
runs the hook command as the settings file spells it. The `--write` hook
refuses a target that exists with `st_nlink > 1` and refuses every write
while `kits_symlink(kits, hardlinks=True)` reports anything, naming the
link. Tests: a planted `shlex.py` beside the guard makes the row FAIL and
the hook, run as the settings command, still refuses `rm -rf`; a write to
a hardlinked file under `kits/` is refused; a write while another hardlink
exists under `kits/` is refused; the settings files parse and both commands
start with `python3 -I`. Gate: the tests; `./scripts/check` green.

**U3 Provenance and `doctor --live` (§37; review 20 should-fix 3, 4, 5).**
`src/hands/api.py`, `src/hands/doctor.py`, tests. `Api.send` refuses
`origin: phone` from a socket client with a message naming `answer` as the
only path that sets it; the daemon's `answer` path is unchanged. The
architect's live turn passes `--repo <the clone driver_clone resolves>`
(the cwd when the cwd is the clone), FAILS before the turn when there is
none, and judges the `hands kit check` only when its argv names the live
kit's path and that `--repo`; the live kit is `kits/hands-doctor-live-<8
hex>`, unique per run, the row FAILS without running when the path exists,
and only the directory it created is removed. Tests: a socket send with
origin phone is refused and files no job; the live check with a cwd-as-
clone layout passes and with no clone fails; a turn that checks another kit
fails the step; a pre-existing kit directory of the chosen name is left
untouched and the row fails. Gate: the tests; `./scripts/check` green.

**U4 The protocol's revert step (§37; review 20 should-fix 6).**
`templates/REVIEW-PROTOCOL.md`, `meta/REVIEW-PROTOCOL.md`, tests. The
revert step reads: in the worktree at the commit, `git checkout <sha>~1 --
<the non-test files the body lists>`, run the commit's new tests and
expect red, then `git checkout <sha> -- <the same files>`; no "stash"
remains in either file. The test that pins the protocol's sentences pins
this one; the two files differ only in the project's names. Gate: the
test; `./scripts/check` green.

**U5 The apply that leaves no playbook (§37; review 20 note on U5).**
`src/hands/playbook.py`, tests. After an apply the engine approved itself,
a committed tree without the playbook file stops the pipeline with the
reason "the apply removed PLAYBOOK.toml" (the path as configured); the
reload's existing stop for a playbook that no longer loads is unchanged.
Test: a scripted apply that deletes and commits away the playbook, then
the pipeline is stopped with that reason and no kickoff is sent. Gate: the
test; `./scripts/check` green.

**U6 Final report.** `meta/FINAL-REPORT-21.md` (drafted under
`meta/drafts/`, moved in by this commit): what changed (sha per unit), what
tests prove, NOT PROVEN (mandatory; at least: the cancel race through a
live `handsd` and a real `hands cancel`; the `-I` hook under a real Claude
Code turn; a real phone has not sent anything since U3), the `## Review
items` table for REVIEW-20 blocker 1 and should-fix 1–6 with the unit that
closed each, and the three findings filed for mission 22. Push, take the
open PR's number as the Branch section says, return the tree to `main`,
and reply with the verdict line carrying that number.

## Acceptance

- `./scripts/check` green on the pushed tip of `mission-20`, three
  consecutive runs.
- Every unit commit's body lists every file it touches; U0 is `plan:` and
  follows a merge of `main` into `mission-20`.
- H-046, H-047, H-048 filed as open, scheduled for mission 22.
- A test shows a cancel during the advance ends `killed` with no spawn.
- Both settings files' hook commands begin with `python3 -I`, and a planted
  module beside the guard fails doctor's guard row.
- A socket send with `origin: phone` is refused.
- `doctor --live` for the architect uses the resolved clone and a unique
  kit name.
- Neither protocol file says "stash".
- `meta/FINAL-REPORT-21.md` exists with NOT PROVEN and the review-items
  table; PR #2 is still the branch's open pull request and the tree is on
  `main`.
