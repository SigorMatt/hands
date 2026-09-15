# BUILDER-12-PROMPT — hands mission 12: close review 11

Kickoff line (the only way this mission is started or resumed):

    Read meta/BUILDER-12-PROMPT.md and execute the mission below its divider.

You are the builder for the `hands` repository. Read `DESIGN.md` (v3.11; §28
is this mission, with §8, §10, §12, §27), `CLAUDE.md`, `meta/CHECKPOINT.md`
(a unit in progress means §R first), `meta/reviews/REVIEW-11.md` in full,
and findings H-022, H-023 (U0 files it).

---

## Mission

Close review 11's five blockers and nine should-fix items. The largest is
the driver guard, which is rewritten around `shlex` tokens so that what the
guard judges is what the shell delivers. Finish with a report whose first
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
- Your final reply begins with exactly one of: `VERDICT: mission 12
  finished` | `VERDICT: mission 12 blocked <unit>` | `VERDICT: question
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
`meta/CHECKPOINT.md`. H-022: append its resolution (§28) to its own
section and set its status line. H-018–H-021: move the resolutions U0 of
mission 11 filed in a separate section into each finding's own section and
update the status lines in place (should-fix 5). File H-023 for the sweep's
departure from §27 (blocker 3). Should-fix 4: pin the `done` statement
against each `failure_reason` value.

**U1 The guard on shlex (§28; blocker 1).** Rewrite the segment and token
logic of `driver/hooks/bash_guard.py` as §28 specifies: `shlex` POSIX
tokenization, segments split on every separator including a lone `&`,
option values read from tokens, refusal of tokens with residual expansion
characters in `hands`/`git` argument positions, refusal of leading
assignments and `$'…'`, role mode's `--context keep` and
`HANDS_CONSULT_ROLE` role check, refusal of unparsable commands. Keep every
existing allowed command allowed (the two self-test tables and
`tests/test_bash_guard.py` say which); add every probe REVIEW-11 blocker 1
lists, asserted blocked in both modes. Gate: both tables green; the commit
body lists the probes that were blocked only after this change.

**U2 Consult and the driver role, engine-side (§28; should-fix 1, 2, 3, 8).**
The stops for `escalate`, an unrecognised driver verdict and
`driver.failed` live in the engine; `driver.killed`, `driver.orphaned`,
`driver.limited` are events that stop and notify with `consult.done`
carrying the terminal state; `max_consults` counts from the later of the
last kickoff-line job (any kickoff value seen) and the last `plan:` apply;
doctor's driver row checks the settings file names the hook, the hook
self-tests green in role mode, and `permission_flags` is empty, else
`fail`. `docs/PLAYBOOK.md` and `docs/INTEGRATION.md` updated. Gate: an
end-to-end test per stop with a playbook that has no driver rules; a
counter test across a renamed kickoff; a doctor test for each failure.

**U3 Kit transport and the apply (§28; blocker 2, should-fix 6, 7, 9).** URL
validation inside the try with the four checks; `kit.refused` for every
failure including the reviewer's three URLs; `kit check` resolves named
file paths against kit then repo with the daemon's syntax; the
apply-verdict exception narrowed to the one rule; `KIT.md` line rules
(≤ 72, no quotes, no newline, non-empty) with the default and the notice,
and shell-quoting of the message in both the daemon's and `kit check`'s
prompt. Gate: tests for each, including byte-equality of the two prompts.

**U4 Sweep and who (§28; blockers 3, 4; H-023).** The sweep signals a group
only with a live leader that is the job's pid, or when every live member
descends by pid chain (or cgroup membership); the mark alone never
qualifies; test through `_sweep`/`_kill_group` with a leaderless marked
group left alone and a descendant group killed. `hands who`'s directory
fallback excludes every hands pid's `sessionId`; test with the reviewer's
probe (job pid with a sessions file, spool without `session_id`, human with
none). Gate: tests.

**U5 This repository's playbook.** `PLAYBOOK.toml`: `[series] kickoff`
becomes BUILDER-13's line; nothing else changes. `hands kit check` on a
kit made of `meta/BUILDER-12-PROMPT.md` with `--repo .` exits 0 (the
acceptance form H-022 settles). Gate: the playbook loads; the check exits
0 and its output is in the commit body.

**U6 Final report.** `meta/FINAL-REPORT-12.md` (drafted under
`meta/drafts/`, moved in by this commit): what changed (sha per unit),
what tests prove, NOT PROVEN (mandatory), the `## Review items` table for
REVIEW-11 blockers 1–5 and should-fix 1–9. Then the verdict line.

## Acceptance

- `./scripts/check` green on the pushed tip, three consecutive runs.
- Every unit commit's body lists every file it touches; U0 is `plan:`.
- `tests/test_bash_guard.py` contains every probe REVIEW-11 blocker 1 lists,
  each asserted blocked.
- A kit of `meta/BUILDER-12-PROMPT.md` checked with `--repo .` exits 0.
- `meta/FINAL-REPORT-12.md` exists with NOT PROVEN and the review-items
  table.
