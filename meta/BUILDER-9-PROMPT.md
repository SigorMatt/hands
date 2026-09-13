# BUILDER-9-PROMPT — hands mission 9: close review 8

Kickoff line (the only way this mission is started or resumed):

    Read meta/BUILDER-9-PROMPT.md and execute the mission below its divider.

You are the builder for the `hands` repository. Read `DESIGN.md` (v3.8; §25
is this mission, with §6, §10, §11), `CLAUDE.md`, `meta/CHECKPOINT.md` (a
unit in progress means §R first), `meta/reviews/REVIEW-8.md` in full,
`meta/FINAL-REPORT-8.md` §5, and findings H-014, H-016.

---

## Mission

Close review 8's four should-fix items and the five decisions of
FINAL-REPORT-8 §5 as DESIGN v3.8 §25 resolves them, retire `quiet_hours`,
make the daemon refuse a playbook that differs from the committed file, and
drop the stale ruff exclude. Finish with a report whose first line the
playbook can match.

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
- Your final reply begins with exactly one of: `VERDICT: mission 9
  finished` | `VERDICT: mission 9 blocked <unit>` | `VERDICT: question <one
  line>`.

## Sub-agent brief (give this to every unit sub-agent, verbatim, plus the unit)

    You are implementing one unit of hands. Read, in this order: CLAUDE.md,
    DESIGN.md sections named by the unit, meta/CHECKPOINT.md, the review or
    report item named by the unit, then only the files the unit touches.
    Rules: the design is the spec — where it is silent, choose the simplest
    thing and say so in the commit body; write the failing test before the
    code and confirm it fails; ./scripts/check green three times before you
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

**U0 Plan and corrections (`plan:` commit).** `meta/plan.md`,
`meta/CHECKPOINT.md`. Append to H-016 and H-014 the v3.8 resolutions
(§25). File H-017 for review 8 should-fix 2 (the §6 vocabularies) with
status `fixed by DESIGN v3.8`. Remove the `meta/prototypes/` ruff exclude
from `pyproject.toml`.

**U1 Termination precedence and vocabularies (§6, §25; H-014).** The
termination line wins over a `success` result (only `killed` and `limited`
keep precedence); `failure_reason` and `decided_by` values are exactly the
§6 lists; `docs/INTEGRATION.md` names them. Gate: the H-014 fixture (success
result, turns, exit 0, terminating line) is `failed/harness_terminated`;
the review-7 over-match lines stay negatives.

**U2 Review 8 should-fix 1, 3, 4.** `main()`'s exit code pinned through
the socket route for one command; `_last_resort` checks `group_pids`
before `killpg` and never signals a group with no members; the phone
channel's reconnect warning logs the exception type and status only, and a
test asserts the topic string is absent. Gate: tests.

**U3 Playbook must match the committed file (§10).** At load, the file's
bytes are compared with `git show HEAD:<playbook.path>` in `role.cwd`; on
a difference (or an untracked file) the playbook is refused with a message
naming both sha256s, the pipeline stops with that reason, and the event
says so. `hands doctor`'s playbook row reports committed/dirty. Gate:
tests with a temp repo: committed and clean, dirty, untracked.

**U4 `quiet_hours` retired (§11, §25).** Remove the feature from
`notify.py`, the playbook loader (a `quiet_hours` key is refused at load
with a message), the config, doctor's notification text, `docs/PLAYBOOK.md`
and `docs/INTEGRATION.md`; delete its tests. Gate: `grep -rn quiet_hours
src tests docs driver` returns only the refusal and its test.

**U5 Phone channel after restart; detector payload (§25).** On daemon
start, every job still `held` gets a fresh nonce and its notification is
re-sent with buttons; `monitor.task_killed` payload carries `cause:
unknown` and the docs say why. Gate: tests.

**U6 Final report.** `meta/FINAL-REPORT-9.md` (drafted under
`meta/drafts/`, moved in by this commit): what changed (sha per unit),
what tests prove, NOT PROVEN (mandatory), the `## Review items` table for
REVIEW-8 should-fix 1–4 and FINAL-REPORT-8 §5 items 1–5. Then the verdict
line.

## Acceptance

- `./scripts/check` green on the pushed tip, three consecutive runs.
- Every unit commit's body lists every file it touches; U0 is `plan:`.
- `grep -n prototypes pyproject.toml` returns nothing.
- A dirty `PLAYBOOK.toml` is refused at job start (test).
- `meta/FINAL-REPORT-9.md` exists with NOT PROVEN and the review-items
  table.
