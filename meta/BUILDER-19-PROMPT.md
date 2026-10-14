# BUILDER-19-PROMPT — hands mission 19: the pull-request flow

Kickoff line (the only way this mission is started or resumed):

    Read meta/BUILDER-19-PROMPT.md and execute the mission below its divider.

You are the builder for the `hands` repository. Read `DESIGN.md` (v3.18; §35
is this mission, with §26, §31), `CLAUDE.md`, `meta/CHECKPOINT.md` (a unit
in progress means §R first), and `meta/reviews/REVIEW-18.md` in full.

---

## Mission

Build the pull-request flow of DESIGN §35: from mission 20 on, every mission
of this repository runs on a branch, opens a pull request, is reviewed with
the hosted review (Qodo) read as a second cold reviewer, and is merged by
the review on a clean verdict. This mission delivers the templates, this
repository's own protocol and playbook, doctor's `gh` row, and the docs. It
does NOT touch the engine, the guard, the roles, or review 18's should-fix
items (those are mission 20's). This mission itself commits to `main`
directly, as every mission before it; it is reviewed under the direct shape.
Its first unit is a gate: no hosted review on a probe PR within fifteen
minutes means the mission is blocked at U0 and nothing is built. Finish with
a report whose first line the playbook can match.

## Execution model (binding)

- You are a thin orchestrator. You plan units, write the checkpoint,
  dispatch ONE sub-agent per unit (Task tool, foreground only), verify the
  unit cheaply, record one line, move on. You run nothing longer than `git
  status`, `git log --oneline -5`, and `./scripts/check` yourself.
- Before each unit: write `meta/CHECKPOINT.md` (unit id, intent, what
  "done" means, standing constraints). After each unit: update it and
  append one line to `meta/journal.md`.
- Every unit ends with a commit AND a push, to `main`. A unit commit
  carries only its own files and its body lists every one; never `git add
  -A`. The U0 commit uses the `plan:` prefix. Drafts of the final report
  live under `meta/drafts/` (git-ignored) until the last unit.
- Retry a failed unit once with the sub-agent's report attached; after two
  failures mark it `blocked` in `meta/plan.md` and continue with units that
  do not depend on it. U0 is the exception: a blocked U0 ends the mission
  with `VERDICT: mission 19 blocked U0`.
- Never edit product code yourself. Never edit `DESIGN.md` (file a finding
  instead).
- `./scripts/check` three times before every commit, each run its own
  foreground call with an explicit timeout of 20 minutes (the harness moves
  a long foreground command to the background otherwise; discotrade
  finding HF-006).
- Your final reply begins with exactly one of: `VERDICT: mission 19
  finished` | `VERDICT: mission 19 blocked <unit>` | `VERDICT: question
  <one line>`.

## Sub-agent brief (give this to every unit sub-agent, verbatim, plus the unit)

    You are implementing one unit of hands. Read, in this order: CLAUDE.md,
    DESIGN.md sections named by the unit, meta/CHECKPOINT.md, the review
    item(s) named by the unit, then only the files the unit touches. Rules:
    the design is the spec — where it is silent, choose the simplest thing
    and say so in the commit body; write the failing test before the code
    and confirm it fails; ./scripts/check green three times before you
    commit, each run a foreground call with a 20-minute timeout; one
    commit, `<area>: <one line>` + a body naming the unit, the DESIGN
    sections and the item, listing every file, and stating only what the
    tests prove — never a totality claim unless a test enumerates the whole
    space; never `git add -A`; push; never edit meta/plan.md,
    meta/CHECKPOINT.md, or DESIGN.md; if the unit needs a design change,
    stop and write a memo to meta/findings/FINDINGS.md instead of
    improvising; dispatch nothing in the background; never require a real
    `claude` or a real `gh` in tests (a fake on PATH, as tests/fake_claude.py
    is); report in ≤12 lines: sha, files, tests added, what is NOT proven.

## §R Recovery brief

If `meta/CHECKPOINT.md` names a unit in progress and the working tree is
dirty: finish that unit under the sub-agent rules if it can pass
`./scripts/check`; otherwise `git stash push -m "wip <unit> <date>"`,
record in the checkpoint where it stopped and that a stash exists, and
leave the tree clean. Then continue from that unit. Push before taking any
new unit. If the checkpoint names U0 in progress with a probe PR open,
close that PR and delete `probe-qodo` (local and remote) before anything
else, and redo U0 from the start.

## Units, in order

**U0 Plan, bookkeeping and the gate (`plan:` commit).** `meta/plan.md`,
`meta/CHECKPOINT.md`. Then the gate, run by you (the orchestrator) with
read-and-wait commands only, no sub-agent: confirm `gh --version` and `gh
auth status` succeed for this user; create branch `probe-qodo` from
`main`; add one dated line to `docs/INTEGRATION.md` under its last
heading ("probe: hosted review, <date>"); commit as `probe: hosted review`
and push the branch; `gh pr create --base main --head probe-qodo --title
"probe: hosted review" --body "Probe for DESIGN §35 U0. Closed without
merging."` and note the number and the time; poll every 60 seconds (one
foreground `sleep 60` per poll; if the harness refuses `sleep`, use
`timeout 60 tail -f /dev/null` or simply repeat the poll) for up to 15
minutes: `gh api
repos/SigorMatt/hands/issues/<n>/comments --jq '.[] | select(.user.login |
test("qodo")) | .created_at'` and `gh api
repos/SigorMatt/hands/pulls/<n>/reviews --jq '.[] | select(.user.login |
test("qodo")) | .submitted_at'`. Record in `meta/plan.md` under "Gate U0":
the PR number, the open time, the first bot comment time, the delay in
seconds, and the trigger mode ("on open" when the bot posted with no
comment from you; otherwise "not on open"). Then `gh pr close <n>
--delete-branch` and `git checkout main`. If the bot posted nothing within
15 minutes, or `gh` is missing or unauthenticated: record that, close the
PR, delete the branch, return to `main`, commit U0 with the record, and
end the mission with `VERDICT: mission 19 blocked U0`. Otherwise commit U0
(`plan:`; plan, checkpoint, journal) on `main` and continue. Gate: the
record in `meta/plan.md`; `git branch -r` shows no `probe-qodo`.

**U1 Doctor's `gh` row (§35).** `src/hands/doctor.py`, tests. A row named
`gh`: `gh --version` and `gh auth status` run for the user handsd runs as,
the login and whether the token's scopes include `repo`; `gh` absent,
unauthenticated, or without `repo` is a WARN with the remedy (`gh auth
login`), never a FAIL; present and authenticated is OK with the login and
the version. The row runs `gh` found on PATH only; tests put a fake `gh`
on PATH (success, missing, unauthenticated, no `repo` scope) and never a
real one. `hands doctor --json` carries the row like the others. Gate:
tests for the four cases; `./scripts/check` green.

**U2 Templates (§35).** `templates/BUILDER-N-PROMPT.md`,
`templates/REVIEW-PROTOCOL.md`, `templates/PLAYBOOK-missions.toml`,
`templates/PLAYBOOK-runs.toml`, and `src/hands/kit.py` with tests. The
brief template: U0 creates `mission-N` from `main` (or continues the
branch a closer brief names, merging `main` in first); every unit pushes to
the branch; the last unit opens the PR with `gh pr create --base main
--head mission-N --title "mission N: <title>" --body-file
meta/FINAL-REPORT-N.md`, replies `VERDICT: mission N finished
pr=<number>`, and returns the tree to `main` (`git checkout main && git
pull --ff-only`); a brief may say "direct" instead, which is today's
behaviour. The protocol template: finds the PR itself (`gh pr list --head
mission-N --state open --json number,baseRefName,headRefOid`); with a PR
reviews its commits since the last reviewed tip, without one reviews
since the last `review:` commit on `main`; waits up to ten minutes in
one-minute foreground steps for the hosted review; `## Hosted review`
section with every bot finding verbatim and confirmed/dismissed with a
reason; `reviewed: <sha>` line; the review file committed to `main` and
pushed before any merge; on `blockers=0` merges with `gh pr merge
<number> --merge --subject "merge: mission N (PR #<number>)"` and runs
`git checkout main && git pull --ff-only`; with blockers leaves the PR
open and says so. The playbook templates: the review rule's prompt no
longer says "every commit after the last review: commit"; it says the
protocol finds the mission's commits (PR or main) itself; the `builder.done`
regex unchanged. `kit.py`: the vocabulary check accepts the literal
`VERDICT: mission N finished pr=<number>` against the unchanged regex (a
test with a brief carrying that literal passes the `verdicts` check; a
brief without `pr=` still passes). Gate: `hands kit check` on a kit built
from the new templates with placeholders filled passes 6 of 6 against a
clone of this repository; tests for the literal.

**U3 This repository's own flow (§35).** `CLAUDE.md`,
`meta/REVIEW-PROTOCOL.md`, `PLAYBOOK.toml`. CLAUDE.md: "One commit per
unit … Push immediately" becomes "to the mission's branch; the brief says
which; `main` moves by merges and by plan commits"; and the rule that the
working tree is left on `main` at mission end. The protocol: the template's
text from U2 with this repository's names. The playbook: `[series]
kickoff` names `meta/BUILDER-20-PROMPT.md`; the review rule's prompt as in
the template; nothing else. Gate: the playbook loads (`hands --project
hands pipeline` after the commit shows 20 rules, no error); a kit of this
brief checked with `--repo .` exits 0; `meta/REVIEW-PROTOCOL.md` and
`templates/REVIEW-PROTOCOL.md` differ only in the project's names.

**U4 Docs (§35).** `docs/ARCHITECT-HANDBOOK.md` §6 (the `[series]`
keys: `name`, `kickoff`, `architect`, `autonomous`, `gate_failures`,
`escalate_on`, `kit_wait_s`, finding HF-004 from discotrade) and §9
rewritten to the decided shape (the review merges, merge commit, the
protocol finds the PR, standing approval, the direct option);
`docs/INTEGRATION.md` (the `gh` prerequisite, doctor's row, the branch the
working tree must be on); `docs/PLAYBOOK.md` (the review prompt wording).
Gate: every command the docs show exists in `hands --help` or `gh`;
`./scripts/check` green.

**U5 Final report.** `meta/FINAL-REPORT-19.md` (drafted under
`meta/drafts/`, moved in by this commit): what changed (sha per unit),
what tests prove, NOT PROVEN (mandatory; at least: no mission has yet run
through the flow, and the merge step has never run), the gate record from
U0 repeated, and the `## Review items` table saying review 18's four
should-fix items are mission 20's. Then the verdict line.

## Acceptance

- `./scripts/check` green on the pushed tip, three consecutive runs.
- Every unit commit's body lists every file it touches; U0 is `plan:`.
- `meta/plan.md` records the probe PR, the bot's first comment time, the
  delay and the trigger mode; the branch `probe-qodo` is gone.
- `hands doctor` prints a `gh` row (test and the laptop).
- `PLAYBOOK.toml`'s kickoff names `meta/BUILDER-20-PROMPT.md` and the
  playbook loads with 20 rules.
- A kit built from the new templates passes `hands kit check` 6 of 6.
- `meta/FINAL-REPORT-19.md` exists with NOT PROVEN and the review-items
  table.
