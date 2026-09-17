# BUILDER-18-PROMPT — hands mission 18: close review 17

Kickoff line (the only way this mission is started or resumed):

    Read meta/BUILDER-18-PROMPT.md and execute the mission below its divider.

You are the builder for the `hands` repository. Read `DESIGN.md` (v3.17; §34
is this mission, with §11, §26, §32, §33), `CLAUDE.md`, `meta/CHECKPOINT.md`
(a unit in progress means §R first), and `meta/reviews/REVIEW-17.md` in
full.

---

## Mission

Close review 17's blocker and seven should-fix items, and make `hands who`
report "needs you" from current state. Finish with a report whose first
line the playbook can match.

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
- Your final reply begins with exactly one of: `VERDICT: mission 18
  finished` | `VERDICT: mission 18 blocked <unit>` | `VERDICT: question
  <one line>`.

## Sub-agent brief (give this to every unit sub-agent, verbatim, plus the unit)

    You are implementing one unit of hands. Read, in this order: CLAUDE.md,
    DESIGN.md sections named by the unit, meta/CHECKPOINT.md, the review
    item(s) named by the unit, then only the files the unit touches. Rules:
    the design is the spec — where it is silent, choose the simplest thing
    and say so in the commit body; write the failing test before the code
    and confirm it fails; ./scripts/check green three times before you
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

**U0 Plan and bookkeeping (`plan:` commit).** `meta/plan.md`,
`meta/CHECKPOINT.md`. File H-037 (the start fold dropped a held job's
buttons, review 17 blocker 1). Correct FINAL-REPORT-17 §2's "both denied"
claim by an appended dated line.

**U1 The start fold (§34; blocker 1; should-fix 6).** `job.held` never
folds and always carries its buttons; the start notification lists holds
by title only; a stop inside the window flushes the fold and cancels
nothing queued; `cancel_all` removed from that path. Gate: the reviewer's
two probes (a job held at 0.3 s during a start; a stop at 2 s) as tests,
asserting `actions=True` on the held publish and the start notification's
survival.

**U2 The kit record (§34; should-fix 1, 2).** `kit.json` stores the sha256
of the checked bytes; engine approval re-hashes and refuses a mismatch
with `kit.refused`; `kit_file` serialized per consultation, the second
refused before checking. Gate: tests including a byte flip between check
and approval.

**U3 Symlinks and doctor (§34; should-fix 3, 4, 5).** The `lstat` walk
from the root; doctor reads every settings layer and fails on disabled
hooks, altered matcher, hostile `env`, or a different command; the
self-test check runs the guard at the named path and compares its sha256
with the repository's copy. Gate: the reviewer's probes as tests
(execute-only directory; `settings.local.json` with `env`; a foreign guard
that exits 0).

**U4 The token and who (§34; should-fix 7; backlog mission 18 item 1).**
`ntfy_token` refused without an explicit non-public `ntfy_url`; `hands
who`'s "needs YOU" is current state only. Gate: tests.

**U5 This repository's playbook.** `[series] kickoff` becomes
BUILDER-19's line; nothing else. Gate: loads; a kit of this brief checked
with `--repo .` exits 0.

**U6 Final report.** `meta/FINAL-REPORT-18.md` (drafted under
`meta/drafts/`, moved in by this commit): what changed (sha per unit),
what tests prove, NOT PROVEN (mandatory), the `## Review items` table for
REVIEW-17 blocker 1 and should-fix 1–7. Then the verdict line.

## Acceptance

- `./scripts/check` green on the pushed tip, three consecutive runs.
- Every unit commit's body lists every file it touches; U0 is `plan:`.
- A job held during a start publishes with buttons (test).
- `meta/FINAL-REPORT-18.md` exists with NOT PROVEN and the review-items
  table.
