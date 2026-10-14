# BUILDER-20-PROMPT — hands mission 20: the first role-mode series' findings

Kickoff line (the only way this mission is started or resumed):

    Read meta/BUILDER-20-PROMPT.md and execute the mission below its divider.

You are the builder for the `hands` repository. Read `DESIGN.md` (v3.19; §36
is this mission, with §31, §33, §34, §35), `CLAUDE.md`, `meta/CHECKPOINT.md`
(a unit in progress means §R first), `meta/reviews/REVIEW-19.md` and
`meta/reviews/REVIEW-18.md` in full.

---

## Mission

Fix what the first role-mode series found in the machinery (DESIGN §36):
the architect role's write permission, the roles' clones advanced by the
runner, `HANDS_PROJECT` on every role job, the engine's reload before an
autonomous apply's kickoff, the hold decided before it is published, the
phone's `answer` command, the job environment's timeouts, `cp` from the
clone into kits, project names in notifications; close review 19's five
should-fix items and review 18's four; make the tests hermetic (H-040).
This is the first mission run through a pull request: its review reads the
hosted review and merges. It does NOT touch onboarding, `hands project
add`, the instruction templates or the handbook's new sections (mission
21). Finish with a report whose first line the playbook can match.

## Branch (DESIGN §35)

Pull request. This mission runs on the branch `mission-20`. U0 creates it
from `main` (`git checkout main && git pull --ff-only && git checkout -b
mission-20`). Every unit commit goes to that branch and is pushed at once
(`git push -u origin mission-20` the first time). The last unit opens the
pull request — `gh pr create --base main --head mission-20 --title "mission
20: the first role-mode series' findings" --body-file
meta/FINAL-REPORT-20.md` — and the final reply's verdict carries its
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
  foreground call with an explicit timeout of 20 minutes. Until U1 lands,
  run it as `env -u HANDS_PROJECT -u HANDS_JOB ./scripts/check` (H-040) and
  say so in the commit body; from U1 on, plain `./scripts/check`.
- Your final reply begins with exactly one of: `VERDICT: mission 20
  finished pr=<number>` | `VERDICT: mission 20 blocked <unit>` | `VERDICT:
  question <one line>`.

## Sub-agent brief (give this to every unit sub-agent, verbatim, plus the unit)

    You are implementing one unit of hands. Read, in this order: CLAUDE.md,
    DESIGN.md sections named by the unit, meta/CHECKPOINT.md, the review or
    finding item(s) named by the unit, then only the files the unit touches.
    Rules: the design is the spec — where it is silent, choose the simplest
    thing and say so in the commit body; write the failing test before the
    code and confirm it fails; ./scripts/check green three times before you
    commit, each run a foreground call with a 20-minute timeout (as `env -u
    HANDS_PROJECT -u HANDS_JOB ./scripts/check` until the hermetic fixture
    of U1 is on the branch); one commit, `<area>: <one line>` + a body
    naming the unit, the DESIGN sections and the item, listing every file,
    and stating only what the tests prove — never a totality claim unless a
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
checkout mission-20 && git pull --ff-only` first. A `keep` send that
arrives after you replied `VERDICT: question` is the answer: carry it out,
continue the mission from the checkpoint, and end that reply with one of
the mission's `VERDICT:` lines, always, even when the answer came with a
file to commit first.

## Units, in order

**U0 Plan, branch and findings (`plan:` commit).** `meta/plan.md`,
`meta/CHECKPOINT.md`; the branch `mission-20` created and pushed. File in
`meta/findings/FINDINGS.md`, one entry each with the series' finding ids as
the evidence: H-041 the architect role cannot write (no allow for the write
tools; the `--write` hook only denies); H-042 the role's clone never
advances (`git fetch` only; `kit check --repo ./repo` judges the working
tree); H-043 no role job carries `HANDS_PROJECT`; H-044 the kickoff after
an autonomous apply comes from the pre-apply playbook (HF-001); H-045 a
hold for a kit the role filed is published with buttons before the engine
approves it. Carry review 19 should-fix 1–5 and review 18 should-fix 1–4
into the units below. Gate: the entries exist; `git branch -r` shows
`origin/mission-20`.

**U1 Hermetic tests and the small review-19 items (§36; H-040; review 19
should-fix 3, 4, 5).** `tests/conftest.py`: an autouse fixture that
removes every `HANDS_*` variable from the environment of every test;
`src/hands/doctor.py`: the `gh` row runs `gh auth status --active
--hostname github.com`, and every WARN of the row, including a
`--version` that does not answer, carries the remedy; `docs/INTEGRATION.md`
and `docs/PLAYBOOK.md` corrected as the review says. Gate: `HANDS_PROJECT=x
HANDS_JOB=y ./scripts/check` green; tests for the row with a fake `gh`
whose status output lists a GHE host first and whose exit is 1 for another
host.

**U2 The review protocol (§36; review 19 should-fix 1, 2; HF-007; HF-008).**
`templates/REVIEW-PROTOCOL.md` and `meta/REVIEW-PROTOCOL.md` together: the
direct shape only when the brief's Branch section says "Direct"; a brief
naming a branch with no open PR is blocker "no pull request for
<branch>" and the review stops there; the branch named once as `<branch>`;
commits under review `git log <base>..origin/<branch> ^origin/main`; a
tests-only commit reviewed by making each wrong change its body names in
the worktree and expecting red; per-commit sub-agents one at a time, one
`./scripts/check` each, the reviewer's own run once at the tip. Gate: the
two files differ only in the repository's names (`diff` after substituting
them); `hands kit check` of a kit built from the templates passes.

**U3 The architect role's write permission (§36; H-041).**
`architect/settings.json`: `permissions.allow` gains exactly
`"Edit(kits/**)"`, `"Write(kits/**)"`, `"MultiEdit(kits/**)"`;
`src/hands/doctor.py`: the architect row fails when any of the three is
absent or when any allow for `Edit`, `Write` or `MultiEdit` names anything
but `kits/**`; `doctor --live` for the architect writes one file under
`kits/`, runs `hands kit check` on a one-file kit against the clone, runs
`hands show` on a job of its spool, removes the file, and fails the row
when any of the four did not happen. Tests with the fake claude (a scripted
live turn that writes, and one that cannot). Gate: tests; the shipped
settings file passes the row.

**U4 The runner (§36; H-042, H-043).** `src/hands/runner.py`,
`src/hands/config.py` (`[roles.<role>] branch`, default `main`),
`src/hands/doctor.py`: before every architect and driver job, `git -C
<clone> fetch -q origin` then `git -C <clone> checkout -q --detach
origin/<branch>`; a failure fails the job before `claude` starts with the
git message in the record; every role job's environment carries
`HANDS_PROJECT` from the config's project name, never from handsd's
environment; doctor's role rows print the clone's HEAD against origin and
the project the job will see. Tests with a local bare repository as origin
(the clone behind by one commit is advanced; a clone whose origin is
unreachable fails the job). Gate: tests.

**U5 The engine (§36; H-044, H-045).** `src/hands/playbook.py`,
`src/hands/api.py`, `src/hands/daemon.py`: before deciding the
`builder.done` of an apply it approved itself, the engine reloads the
playbook from the committed file; the regression test is a scripted apply
that rewrites and commits the playbook's kickoff before replying `VERDICT:
kit applied`, after which the kickoff job's prompt is the committed line
(fails on 2017140, passes after); a playbook that no longer loads after the
apply stops the pipeline with the loader's reason. Under `autonomous`, a
hold for a kit the role filed is decided before anything is published: one
buttonless notification "kit <name> filed by the architect; apply approved
by the playbook" when approved; Approve/Deny buttons, unchanged from §34,
when not. Gate: both
tests red before, green after.

**U6 `answer <secret> <text>` (§36).** `src/hands/phone.py`,
`src/hands/api.py`, `src/hands/spool.py`, `src/hands/playbook.py`,
`src/hands/notify.py`, `docs/INTEGRATION.md`: the command as §36 states
it — delivered as a builder `keep` send of origin `phone`; un-pauses when
the job starts; never held by the §8 gate; refused and the refusal
published under `hands: answer` when the builder has no resumable session,
has a job running, queued or held, or the text is empty; an attachment
fetched into `kit_dir` by the kit transport's rules with the delivered text
ending in one sentence naming its path and the record keeping its sha256;
inbox event `answer.sent`; the builder's final reply published titled
`builder`, its `VERDICT:` firing the rules; the driver-escalation stop's
message keeps the builder's question verbatim; the architect's consult
prompt gains "Decided by the human since your last consultation" listing
every `answer`, every cli `--context keep` send to the builder and every
`meta/decisions/*-owner.md` committed since that consultation, verbatim.
Gate: tests for each sentence; a test that an `answer` whose text names a
decisions file is not held.

**U7 The job environment and the guard (§36; HF-006; HF-003).**
`src/hands/runner.py`, `src/hands/doctor.py`, `driver/hooks/bash_guard.py`
and its self-test, `docs/INTEGRATION.md`: builder and aux jobs carry
`BASH_DEFAULT_TIMEOUT_MS` and `BASH_MAX_TIMEOUT_MS` of `900000` unless the
role's env table sets them, doctor printing the effective values; architect
mode allows `cp`/`cp -r` with every source under `HANDS_CLONE` and every
target under `HANDS_KITS`, by realpath, refused while anything under
`HANDS_KITS` is a symlink or any source is one. Gate: self-test cases for
the new `cp` shapes (allowed, source outside the clone, target outside
kits, a symlink source); runner tests for the environment.

**U8 Review 18's four should-fix items (§36; review 18 should-fix 1–4).**
`src/hands/config.py` (non-ASCII in `ntfy_url` refused at load; the
public-broker check compares the folded host), `src/hands/doctor.py` (the
guard self-test under `python3 -I` with an empty `PYTHONPATH`),
`src/hands/api.py`/`src/hands/kit.py` (the kit record stores the sha256 of
the bytes `check_kit` read; a mismatch with the client's refuses the
filing), `driver/hooks/bash_guard.py` and doctor (a hardlinked regular
file under `kits/` refuses `cp` and `mv` and is reported). Gate: the
reviewer's four probes as tests.

**U9 Notifications and this repository's kickoff (§36).**
`src/hands/notify.py`, `src/hands/daemon.py`, `src/hands/doctor.py`,
`docs/INTEGRATION.md`, `PLAYBOOK.toml`: every title handsd publishes begins
with `<project>: `; the documented topic-generating lines carry the
project; doctor warns on a configured topic whose name lacks the project;
`[series] kickoff` of this repository's playbook becomes "Read the builder
prompt with the highest mission number in the meta directory and execute
the mission below its divider." and nothing else in the file changes. Gate:
tests for the title prefix and the warning; the playbook loads with 20
rules; a kit of a brief carrying the new kickoff line checked with `--repo
.` exits 0.

**U10 Final report and the pull request.** `meta/FINAL-REPORT-20.md`
(drafted under `meta/drafts/`, moved in by this commit): what changed (sha
per unit), what tests prove, NOT PROVEN (mandatory; at least: no `answer`
has been sent from a real phone, no real role job has had its clone
advanced by the runner), the `## Review items` table for REVIEW-19
should-fix 1–5 and REVIEW-18 should-fix 1–4. Then open the pull request
as the Branch section says, return the tree to `main`, and reply with the
verdict line carrying the PR number.

## Acceptance

- `./scripts/check` green on the pushed tip of `mission-20`, three
  consecutive runs, with `HANDS_PROJECT` set in the environment.
- Every unit commit's body lists every file it touches; U0 is `plan:`.
- H-041..H-045 filed; H-040 resolved by U1.
- `architect/settings.json` carries the three allows and doctor's architect
  row checks them.
- A test shows the kickoff after an autonomous apply is the committed
  playbook's line.
- A test shows an `answer` naming a decisions file is not held.
- `PLAYBOOK.toml`'s kickoff is the mission-less line and the playbook loads.
- `meta/FINAL-REPORT-20.md` exists with NOT PROVEN and the review-items
  table; the PR from `mission-20` to `main` is open and the tree is on
  `main`.
