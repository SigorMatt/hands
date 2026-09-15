# BUILDER-13-PROMPT — hands mission 13: close review 12, the sweep, two projects

Kickoff line (the only way this mission is started or resumed):

    Read meta/BUILDER-13-PROMPT.md and execute the mission below its divider.

You are the builder for the `hands` repository. Read `DESIGN.md` (v3.12; §29
is this mission, with §5, §12, §13, §26, §28), `CLAUDE.md`,
`meta/CHECKPOINT.md` (a unit in progress means §R first),
`meta/reviews/REVIEW-12.md` in full, and findings H-023, H-024, H-025.

---

## Mission

Close review 12's three blockers and nine should-fix items, finish the
sweep half of mission 12's U4 as H-025 option (b) specifies, and make hands
run two projects on one laptop with a per-project spool and templated
units. Finish with a report whose first line the playbook can match.

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
- Your final reply begins with exactly one of: `VERDICT: mission 13
  finished` | `VERDICT: mission 13 blocked <unit>` | `VERDICT: question
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
`meta/CHECKPOINT.md`. H-024: append the v3.12 reading to its section and
resolve. H-025: append "option (b) chosen" and the §29 text. H-023: note it
closes with U2. Should-fix 8: the `done` statement pinned by a table over
every `failure_reason` value and the precedence of `killed`/`limited`.
Correct FINAL-REPORT-12 §3 item 2 and its Review items row (REVIEW-11
blocker 1 was not closed) by appended dated lines.

**U1 The guard: comments, the reading, the clone pin (§29; blocker 1;
should-fix 2; H-024).** Refuse any `#` outside quotes in both modes with a
message naming the position; implement H-024's expansion-position reading
exactly as §29 states it; in role mode `git -C` must equal `HANDS_CLONE`.
Add every review 12 blocker-1 probe (comment with an apostrophe then a
second line, in both modes) and the review 11 probes, all asserted
blocked; keep every allowed command allowed. Gate: both tables green; the
commit body lists which probes were blocked only after this change, and
does not claim any that the parent already blocked (verify against the
parent hook).

**U2 The sweep after the reap (§29; H-025 b; H-023; blocker 3).** Descent
= session id equals the job's pid and start time precedes the last
observation of the job's pid alive, or cgroup scope membership; the mark
alone never qualifies; `pipe_timeout_s`; unkilled leftovers reported with
`killed: false`; the residual documented in `docs/INTEGRATION.md`. Gate: the
three §24 orphan tests pass (detached, holding pipes, cancelled job), a
leaderless marked group with a foreign session is left alone, and job end
completes within the timeout with an orphan holding the pipes.

**U3 Kit transport and kit check (§29; blocker 2; should-fix 1, 6, 7).**
`idna.encode` as the host check with the reviewer's five hosts refused
before any fetch; the kit name shell-quoted; `kit check` judges every
named path including bare names and names in parentheses; the
apply-verdict exception stated and enumerated. Gate: tests.

**U4 Consult edges (§29; should-fix 3, 4, 5).** Consult stops apply over a
paused pipeline as `pipeline.stop_suppressed` with the consult reason and a
notification; doctor reads the hook path from the driver directory's
settings and checks that file; `max_consults` counts from daemon start
when nothing else anchors it. Gate: tests.

**U5 Who grace (§29; should-fix 9).** `who.grace_s` (default 60): a
transcript of a job that ended within the grace is excluded from the
directory fallback. Gate: test.

**U6 Two projects on one laptop (§29).** Per-project spool under
`~/.hands/<project>/`; `hands migrate-spool` moves the flat layout to
`~/.hands/hands/` and files an inbox event; `handsd` refuses the flat
layout with the migration instruction; templated units
`systemd/handsd@.service` and `systemd/handswho@.service` reading
`~/.config/hands/<project>.env`; the un-templated units removed; `hands
who` reads every project's spool; `docs/INTEGRATION.md` describes two
daemons and the shared subscription. Gate: tests for the layout, the
migration, and the refusal; `hands who` with two fixture spools shows two
roots.

**U7 This repository's playbook.** `[series] kickoff` becomes
BUILDER-14's line; nothing else. Gate: loads; a kit of this brief checked
with `--repo .` exits 0.

**U8 Final report.** `meta/FINAL-REPORT-13.md` (drafted under
`meta/drafts/`, moved in by this commit): what changed (sha per unit),
what tests prove, NOT PROVEN (mandatory), the `## Review items` table for
REVIEW-12 blockers 1–3 and should-fix 1–9, and REVIEW-11 blockers 1 and 3
(which this mission closes). Then the verdict line.

## Acceptance

- `./scripts/check` green on the pushed tip, three consecutive runs.
- Every unit commit's body lists every file it touches; U0 is `plan:`.
- `tests/test_bash_guard.py` carries every review 12 blocker-1 probe,
  asserted blocked in both modes.
- `systemd/` contains only templated units.
- `meta/FINAL-REPORT-13.md` exists with NOT PROVEN and the review-items
  table.
