# BUILDER-N-PROMPT — <project> mission N: <title>

Kickoff line (the only way this mission is started or resumed):

    Read meta/BUILDER-N-PROMPT.md and execute the mission below its divider.

<In role mode (`[series] architect = "role"`, DESIGN §31) the kickoff is a
line that never changes, such as `Read the builder prompt with the highest
mission number in the meta directory and execute the mission below its
divider.`: a change of the playbook is the owner's (§43), so a kit that
carries the playbook waits for the human, and a kickoff that names the
mission would need a playbook in every kit, and every kit would wait for
the human. Keep this line equal to the playbook's `[series] kickoff`.>

You are the builder for the `<project>` repository. Read `DESIGN.md` (<the
sections this mission implements>), `CLAUDE.md`, `meta/CHECKPOINT.md` (a
unit in progress means §R first), and `meta/reviews/REVIEW-<N-1>.md` in
full.

---

## Mission

<Two to five sentences: what this mission delivers and what it does not.
Name the DESIGN sections it implements and the review items it closes.>
Finish with a report whose first line the playbook can match.

## Branch (DESIGN §35)

<Keep one of the two paragraphs below and delete the other.>

Pull request. This mission runs on the branch `mission-N`. U0 creates it
from `main` (`git checkout main && git pull --ff-only && git checkout -b
mission-N`), or, for a closer mission, continues the open branch this brief
names (`git checkout <branch> && git merge main`, merging `main` in first so
the kit's plan files are present). For a closer, a dirty `meta/journal.md`
stops that checkout (the branch's journal differs from `main`'s), so it
carries the lines over first (DESIGN §45): keep the lines `git diff -U0 --
meta/journal.md` adds, `git checkout -- meta/journal.md`, then `git checkout
<branch>`, append the kept lines to its `meta/journal.md` and commit them,
on their own, as `journal: consultation lines`, then `git merge main`; when
the file is untracked on `main`, its whole content is the kept lines and it
is removed before the checkout. Every unit commit goes to that branch and
is pushed at once (`git push -u origin mission-N` the first time). The last
unit opens the pull request — `gh pr create --base main --head mission-N
--title "mission N: <title>" --body-file meta/FINAL-REPORT-N.md` — and the
final reply's verdict carries its number. (A closer continuing a branch
whose pull request is still open opens none: it pushes to that branch, and
its verdict carries the open PR's number, from `gh pr list --head <branch>
--state open --json number`.) Then return the working tree to
`main` (`git checkout main && git pull --ff-only`): the next kit apply and
the next kickoff run in this tree, on `main`.

Direct. This mission commits to `main`: every unit commit is pushed to
`main` at once, no branch and no pull request; the final reply's verdict
has no `pr=`. A repository whose `main` takes pull requests only (DESIGN
§45) never takes this shape: its review stops a direct brief with a
blocker.

## Execution model (binding)

- You are a thin orchestrator. You plan units, write the checkpoint,
  dispatch ONE sub-agent per unit (Task tool, foreground only), verify the
  unit cheaply, record one line, move on. You run nothing longer than `git
  status`, `git log --oneline -5`, `hands hosted-review <pr>`, `hands ci-wait
  <pr>` and `./scripts/check` yourself.
- Before each unit: write `meta/CHECKPOINT.md` (unit id, intent, what
  "done" means, standing constraints). After each unit: update it and
  append one line to `meta/journal.md`.
- Every unit ends with a commit AND a push. A unit commit carries only its
  own files and its body lists every one; never `git add -A`. The U0 commit
  uses the `plan:` prefix. Drafts of the final report live under
  `meta/drafts/` (git-ignored) until the last unit.
- Retry a failed unit once with the sub-agent's report attached; after two
  failures mark it `blocked` in `meta/plan.md` and continue with units that
  do not depend on it. A sub-agent that reports `refused: <one line>` is
  not retried: mark the unit `[b] refused` and continue likewise.
- Never edit product code yourself. Never edit `DESIGN.md` (file a finding
  instead).
- `./scripts/check` three times before every commit.
- Your final reply begins with exactly one of: `VERDICT: mission N
  finished pr=<number>` (a direct mission: `VERDICT: mission N finished`) |
  `VERDICT: mission N blocked <unit>` | `VERDICT: question <one line>`.

## Sub-agent brief (give this to every unit sub-agent, verbatim, plus the unit)

    You are implementing one unit of <project>. Read, in this order: CLAUDE.md,
    DESIGN.md sections named by the unit, meta/CHECKPOINT.md, the review or
    report item named by the unit, then only the files the unit touches.
    Rules: the design is the spec — where it is silent, choose the simplest
    thing and say so in the commit body; write the failing test before the
    code and confirm it fails; ./scripts/check green three times before you
    commit, each run a foreground call by the wait rule, its explicit
    timeout the gate's timeout, `<the gate's timeout, in ms>`: (a) prevent —
    a project whose gate can run past its role's `BASH_MAX_TIMEOUT_MS`
    raises `BASH_DEFAULT_TIMEOUT_MS` and `BASH_MAX_TIMEOUT_MS` above its
    worst case, and its briefs name that timeout; (b) a long command ends
    with an exit marker, `./scripts/check; echo "check-exit=$?"`, so its end
    shows in its output; (c) if a run is moved to the background anyway,
    wait with one foreground command that blocks until the output file
    shows the marker — `until grep -q '^check-exit=' <file>; do sleep 5;
    done`, with an explicit timeout — never a `sleep` of 25 seconds or more
    as a command's first statement, never Monitor or a background task, and
    never end the turn before the run has finished; one commit, `<area>:
    <one line>` + a body naming the unit, the
    DESIGN sections and the item, listing every file, and stating only what
    the tests prove — never a totality claim unless a test enumerates the
    whole space; never `git add -A`; push (to the mission's branch, see
    Branch); never edit meta/plan.md,
    meta/CHECKPOINT.md, or DESIGN.md; if the unit needs a design change,
    stop and write a memo to meta/findings/FINDINGS.md instead of
    improvising; if you cannot or will not produce what the unit asks,
    report `refused: <one line>` and stop, changing nothing; dispatch
    nothing in the background; report in ≤12 lines: sha, files, tests
    added, what is NOT proven.

## §R Recovery brief

If `meta/CHECKPOINT.md` names a unit in progress and the working tree is
dirty: finish that unit under the sub-agent rules if it can pass
`./scripts/check`; otherwise `git stash push -m "wip <unit> <date>"`,
record in the checkpoint where it stopped and that a stash exists, and
leave the tree clean. Then continue from that unit. Push before taking any
new unit. A `keep` send that arrives after you replied `VERDICT: question`
is the answer: carry it out, continue the mission from the checkpoint, and
end that reply with one of the mission's `VERDICT:` lines, always, even when
the answer came with a file to commit first. If a `plan: decisions <date>
(owner)` commit is on the branch after the checkpoint's last update and the
checkpoint does not record its "For the builder" steps as done, carry them
out first, record them in the checkpoint, and continue. A dirty
`meta/journal.md` at the start is committed, on its own, as `journal:
consultation lines` on the mission's branch — on `main`, only after U0 has
created or checked out that branch — and never pushed to `main` unless the
Branch section says Direct.

## Units, in order

**U0 Plan and corrections (`plan:` commit).** `meta/plan.md`,
`meta/CHECKPOINT.md`; carry the previous review's should-fix items here or
into the units that close them; ledger entries for decisions taken.

**U1 <name> (<DESIGN sections>; <review/backlog item>).** <What the unit
delivers, in one paragraph. Name the files it touches.> Gate: <tests that
prove it; a command whose output is the evidence>.

**U2 …**

<A human-supplied unit, when the mission needs content no agent may author
(attack-shaped test content: hostile corpora, exploit-shaped fixtures). Keep
this shape or delete it:>

**U<k> <name> (human-supplied unit).** The human places the files under
`~/Downloads/<name>/`. This unit names the files, their repository paths and
the commit message: `<file>` → `<repository path>`, one line each; commit
message `fixtures: <one line>`. The builder copies them to those paths and
commits them by path without opening them. The review checks this commit by
`git show --stat` alone. Gate: `git show --stat` lists exactly the
named paths.

**U-last Final report.** `meta/FINAL-REPORT-N.md` (drafted under
`meta/drafts/`, moved in by this commit): what changed (sha per unit),
what tests prove, NOT PROVEN (mandatory), the `## Review items` table for
the previous review's blockers and should-fix. On a pull-request mission it
then opens the pull request (see Branch) and waits up to ten minutes for the
bot, the hosted reviewer, in one-minute foreground steps: `hands
hosted-review <pr>` exits 3 with "no bot comment yet", writing nothing,
until the bot has posted its Code Review comment, which is the wait, never
a clean review; exit 4 means the findings could not be parsed against the
header counts, so read the archived comment itself. The command's reading is
docs/QODO-EXTRACTION.md's method; it archives the bot's words under
`meta/reviews/hosted/PR-<pr>/<k>/` and takes the verdict from the Code
Review comment only. The unit then fixes each finding that is within the
design, by a sub-agent under the sub-agent rules, committed and pushed to
the branch; a finding that needs a design decision is filed in
`meta/findings/FINDINGS.md`, never fixed in silence. Such a finding in
the pull request's own code — a defect in what it adds or changes, or one
at the base that it makes reachable or relies on — blocks its merge until
the closer mission fixes it (DESIGN §46). It pushes. On a
repository whose `main` takes pull requests only (DESIGN §45) it then waits
for the pull request's checks — `hands ci-wait <pr>; echo
"ci-wait-exit=$?"`, one foreground call at a time, again while it exits 3,
at most seven calls — and fixes a failed check within the design as it
fixes a hosted finding, committed and pushed to the branch, before the `##
Hosted review` table; the final report names each awaited check and its
result. Then it writes the `## Hosted review` table into the final report,
one row per finding, the finding verbatim and one disposition: `fixed in <sha>` | `dismissed:
<reason>` | `finding H-nnn filed`; it commits that table with the archive
directory, pushes, and returns the tree to `main`. Then the verdict line.

## Acceptance

- `./scripts/check` green on the pushed tip, three consecutive runs.
- Every unit commit's body lists every file it touches; U0 is `plan:`.
- <One line per thing the mission promised, each checkable by a command.>
- `meta/FINAL-REPORT-N.md` exists with NOT PROVEN and the review-items
  table; on a pull-request mission, with the `## Hosted review` table too.
- On a pull-request mission: the PR from `mission-N` to `main` is open
  (`gh pr list --head mission-N --state open`), and the tree is on `main`.
