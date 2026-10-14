# BUILDER-N-PROMPT — <project> mission N: <title>

Kickoff line (the only way this mission is started or resumed):

    Read meta/BUILDER-N-PROMPT.md and execute the mission below its divider.

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
the kit's plan files are present). Every unit commit goes to that branch and
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
has no `pr=`.

## Execution model (binding)

- You are a thin orchestrator. You plan units, write the checkpoint,
  dispatch ONE sub-agent per unit (Task tool, foreground only), verify the
  unit cheaply, record one line, move on. You run nothing longer than `git
  status`, `git log --oneline -5`, and `./scripts/check` yourself.
- Before each unit: write `meta/CHECKPOINT.md` (unit id, intent, what
  "done" means, standing constraints). After each unit: update it and
  append one line to `meta/journal.md`.
- Every unit ends with a commit AND a push. A unit commit carries only its
  own files and its body lists every one; never `git add -A`. The U0 commit
  uses the `plan:` prefix. Drafts of the final report live under
  `meta/drafts/` (git-ignored) until the last unit.
- Retry a failed unit once with the sub-agent's report attached; after two
  failures mark it `blocked` in `meta/plan.md` and continue with units that
  do not depend on it.
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
    commit; one commit, `<area>: <one line>` + a body naming the unit, the
    DESIGN sections and the item, listing every file, and stating only what
    the tests prove — never a totality claim unless a test enumerates the
    whole space; never `git add -A`; push (to the mission's branch, see
    Branch); never edit meta/plan.md,
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
`meta/CHECKPOINT.md`; carry the previous review's should-fix items here or
into the units that close them; ledger entries for decisions taken.

**U1 <name> (<DESIGN sections>; <review/backlog item>).** <What the unit
delivers, in one paragraph. Name the files it touches.> Gate: <tests that
prove it; a command whose output is the evidence>.

**U2 …**

**U-last Final report.** `meta/FINAL-REPORT-N.md` (drafted under
`meta/drafts/`, moved in by this commit): what changed (sha per unit),
what tests prove, NOT PROVEN (mandatory), the `## Review items` table for
the previous review's blockers and should-fix. On a pull-request mission it
then opens the pull request (see Branch) and returns the tree to `main`.
Then the verdict line.

## Acceptance

- `./scripts/check` green on the pushed tip, three consecutive runs.
- Every unit commit's body lists every file it touches; U0 is `plan:`.
- <One line per thing the mission promised, each checkable by a command.>
- `meta/FINAL-REPORT-N.md` exists with NOT PROVEN and the review-items
  table.
- On a pull-request mission: the PR from `mission-N` to `main` is open
  (`gh pr list --head mission-N --state open`), and the tree is on `main`.
