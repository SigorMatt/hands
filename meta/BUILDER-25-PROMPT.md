# BUILDER-25-PROMPT — hands mission 25: closer for review 24

Kickoff line (the only way this mission is started or resumed):

    Read the builder prompt with the highest mission number in the meta directory and execute the mission below its divider.

You are the builder for the `hands` repository. Read `DESIGN.md` (v3.24; §41
is this mission, with §39, §40), `CLAUDE.md`, `meta/CHECKPOINT.md` (a unit
in progress means §R first), `meta/reviews/REVIEW-24.md` and
`docs/HARNESS-PROBE.md` in full.

---

## Mission

Close review 24's one blocker and eight should-fix items on the open branch
`mission-24` (pull request #5), correct the probe record as §41 says and
fill its unavailable rows where a sign-in now exists, and leave the branch
for review 25 to merge. It does NOT implement the backend seam, the
credential profiles, the polish round or any M9 command (missions 26 and
27), and it makes no host change (the AppArmor decision is the human's).
Finish with a report whose first line the playbook can match.

## Branch (DESIGN §35)

Pull request. This is a closer: it continues the open branch `mission-24`
(`git checkout mission-24 && git merge main`, merging `main` in first so
this kit's plan files are present). Every unit commit goes to that branch
and is pushed at once. The pull request #5 is already open, so the last
unit opens none: it pushes, reads the hosted review again, and the final
reply's verdict carries the open PR's number, from `gh pr list --head
mission-24 --state open --json number`. Then return the working tree to
`main` (`git checkout main && git pull --ff-only`): the next kit apply and
the next kickoff run in this tree, on `main`.

## Execution model (binding)

- You are a thin orchestrator. You plan units, write the checkpoint,
  dispatch ONE sub-agent per unit (Task tool, foreground only), verify the
  unit cheaply, record one line, move on. You run nothing longer than `git
  status`, `git log --oneline -5`, `hands hosted-review <pr>` and
  `./scripts/check` yourself.
- Before each unit: write `meta/CHECKPOINT.md` (unit id, intent, what
  "done" means, standing constraints). After each unit: update it and
  append one line to `meta/journal.md`.
- Every unit ends with a commit AND a push, to `mission-24`. A unit commit
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
  foreground call with an explicit timeout of 20 minutes.
- Your final reply begins with exactly one of: `VERDICT: mission 25
  finished pr=<number>` | `VERDICT: mission 25 blocked <unit>` | `VERDICT:
  question <one line>`.

## Sub-agent brief (give this to every unit sub-agent, verbatim, plus the unit)

    You are implementing one unit of hands. Read, in this order: CLAUDE.md,
    DESIGN.md sections named by the unit, meta/CHECKPOINT.md, the review
    item(s) named by the unit, then only the files the unit touches.
    Rules: the design is the spec — where it is silent, choose the simplest
    thing and say so in the commit body; write the failing test before the
    code and confirm it fails; ./scripts/check green three times before you
    commit, each run a foreground call with a 20-minute timeout; one
    commit, `<area>: <one line>` + a body naming the unit, the DESIGN
    sections and the item, listing every file, and stating only what the
    tests prove — never a totality claim unless a test enumerates the whole
    space; a commit that changes only tests names in its body each wrong
    change that would make them red; a commit that adds or deletes a
    non-test file names it as added or deleted; never `git add -A`; push to
    the branch `mission-24`; never edit meta/plan.md, meta/CHECKPOINT.md,
    or DESIGN.md; if the unit needs a design change, stop and write a memo
    to meta/findings/FINDINGS.md instead of improvising; if you cannot or
    will not produce what the unit asks, report `refused: <one line>` and
    stop, changing nothing; dispatch nothing in the background; never
    require a real `claude`, `gh`, `systemctl`, ntfy server, harness binary
    or `git` remote in tests (fakes on PATH, a local HTTP stub and local
    bare repositories, as tests/fake_claude.py is); never print, commit or
    quote a key, a token or a sign-in file — write `[redacted]`; report in
    ≤12 lines: sha, files, tests added, what is NOT proven.

## §R Recovery brief

If `meta/CHECKPOINT.md` names a unit in progress and the working tree is
dirty: finish that unit under the sub-agent rules if it can pass
`./scripts/check`; otherwise `git stash push -m "wip <unit> <date>"`,
record in the checkpoint where it stopped and that a stash exists, and
leave the tree clean. Then continue from that unit. Push before taking any
new unit. If the tree is on `main` and `origin/mission-24` exists, `git
checkout mission-24 && git pull --ff-only` first. A `keep` send that
arrives after you replied `VERDICT: question` is the answer: carry it out,
continue the mission from the checkpoint, and end that reply with one of
the mission's `VERDICT:` lines, always, even when the answer came with a
file to commit first. If `meta/journal.md` alone is dirty when you start,
commit it first as `journal: consultation lines` and push.

## Units, in order

**U0 Plan and branch (`plan:` commit).** `meta/plan.md`,
`meta/CHECKPOINT.md`; `git checkout mission-24 && git merge main` done and
pushed, so `git log --oneline -1 main` is an ancestor of the branch. Carry
review 24's blocker 1 and should-fix 1–8 by number into the units below;
record in `meta/findings/FINDINGS.md`, under H-062, that the session half
of the key is pinned by U3. Gate: `git merge-base --is-ancestor main
mission-24` exits 0; the entries exist.

**U1 The capture script (§41; blocker 1; should-fix 1).**
`scripts/capture-quota-stop.sh`, `docs/OPERATIONS.md` (its capture
section), tests. Every bounded command, `find` and the python read of the
record included, is routed through the one path that writes `(failed:
timed out after <n>s: <command>)` and goes on; redaction runs on the whole
collected text before any line is cut, and the cut happens afterwards.
Tests with fakes on PATH: a hanging `find` and a hanging `python3` each
produce the timeout line and no false "no job record" line; `-k 5` and the
timeouts on `find` and the record read are pinned (removing each turns a
test red); a planted secret that straddles byte 4000 of a line is absent
from the output in full; a URL-encoded form of a secret is redacted; the
by-value read of the notification password is pinned. Gate: the tests;
`./scripts/check` green.

**U2 The staged kit (§41; should-fix 2).** `src/hands/kit.py`,
`src/hands/api.py`, tests. The daemon refuses a staged name with `..`, a
symlink, a FIFO, a directory and a missing name, each as a `KitError` with
a reason, never an internal error; the file is opened with `O_NOFOLLOW |
O_NONBLOCK` and `fstat`ed before it is read; a `.part` the daemon refuses
is removed by the daemon. Tests: one per input above (the FIFO test must
not block: open with `O_NONBLOCK` and assert the refusal); the `.part`
removal through a socket client that is not the CLI. Gate: the tests;
`./scripts/check` green.

**U3 Three pins in the monitor, the api and the runner (§41; should-fix 6,
7, 8).** `src/hands/monitor.py`, `src/hands/api.py`, `src/hands/runner.py`,
tests. A transcript in which two sessions report the same task id raises
`task_killed` once per session; the 1024-entry memory's eviction is tested
(the oldest key leaves when the 1025th arrives). The ambiguous-prefix
refusal is tested with a typed text that contains a backslash and a secret
that contains one: the published and logged reason carry no part of the
secret. The prompt size cap counts the dispatch-time journal sentence: a
prompt exactly at the cap with a dirty `meta/journal.md` is refused with
the cap's reason, and the same prompt with a clean journal is sent. Gate:
the tests; `./scripts/check` green.

**U4 The warning and the stale worktree (§41; should-fix 4, 5).**
`src/hands/kit.py`, `templates/REVIEW-PROTOCOL.md`,
`meta/REVIEW-PROTOCOL.md`, `docs/ARCHITECT-HANDBOOK.md` §7, tests. The
kit-check WARN for a done rule without its orphaned rule prints when the
`playbook` line fails too, pinned. Both protocols define stale as §41 does
— a registered worktree whose path no longer exists, or a review worktree
under `/tmp` that is not this review's and is older than the current aux
job's start; never one of a review running concurrently or one a human
made — and pin the opening `git worktree remove --force` of stale ones and
the closing `git worktree prune` where each occurs (deleting either turns
a test red). The two protocol files differ only in the project's names;
the handbook carries the definition. Gate: the tests; `./scripts/check`
green.

**U5 The probe record (§41; should-fix 3).** `docs/HARNESS-PROBE.md`,
nothing else. Codex's VERDICT cell becomes `partial: printed while the task
failed` with a footnote pointing at the `workspace-write` run; the opening
claim reads "verbatim except where marked `…`". Then, with
`PATH=$HOME/.nvm/versions/node/v22.23.3/bin:$PATH` and the rules of §40's
probe (a scratch git repository under `/tmp`, the same task, keys and
tokens never printed): if `opencode models` shows a configured default
model, fill OpenCode's rows by the §40 procedure; if `DEEPSEEK_API_KEY` is
set in the environment (its presence only), fill dsh's rows; otherwise
leave each `unavailable` with the reason as it stands. One more Codex row,
appended under "Gaps" as resolved or left as a gap after one attempt: a
`codex exec --json -c approval_policy="on-request"` turn asked to run
`touch /tmp/outside-probe`, recording whether an approval event appears in
the stream, what the headless run did with it, and whether the file exists
afterwards (removed after). Every command and its output quoted, marked
where cut. Gate: the file's table and gaps are consistent with its body;
`grep -c redacted` reported; `./scripts/check` green.

**U6 Final report, the push and the hosted review's findings.**
`meta/FINAL-REPORT-25.md` (drafted under `meta/drafts/`, moved in by this
commit): what changed (sha per unit), what tests prove, NOT PROVEN
(mandatory), the `## Review items` table for review 24's blocker 1 and
should-fix 1–8. The pull request #5 is open: push, then wait up to ten
minutes for the bot in one-minute foreground steps — `hands hosted-review
5` diffs against the previous fetch; "no bot comment yet" (exit 3) is the
wait, never a clean review, and an unchanged Code Review comment after ten
minutes is recorded as "no re-review", not as clean; exit 4 means the
findings could not be parsed against the header counts, so read the
archived comment itself. Fix each finding that is within §41 by a
sub-agent under the sub-agent rules, committed and pushed to the branch; a
finding that needs a design decision is filed in
`meta/findings/FINDINGS.md`, never fixed in silence. Push, then write the
`## Hosted review` table into the final report, one row per finding of the
current Code Review comment, the finding verbatim and one disposition:
`fixed in <sha>` | `dismissed: <reason>` | `finding H-nnn filed` |
`unchanged since mission 24: <its disposition>`; commit that table with the
archive directory, push, and return the tree to `main`. Then the verdict
line, with the PR's number.

## Acceptance

- `./scripts/check` green on the pushed tip, three consecutive runs.
- Every unit commit's body lists every file it touches; U0 is `plan:`.
- `main` is an ancestor of `mission-24`.
- The capture script's timeout tests and the straddling-secret test exist
  and pass; no false "no job record" line on a timeout.
- `docs/HARNESS-PROBE.md`'s Codex VERDICT cell is `partial`, its opening
  claim is qualified, and the file contains no key or token (`grep -c
  redacted` reported).
- `meta/FINAL-REPORT-25.md` exists with NOT PROVEN, the review-items table
  and the `## Hosted review` table.
- PR #5 is still open (`gh pr list --head mission-24 --state open`), and
  the tree is on `main`.
