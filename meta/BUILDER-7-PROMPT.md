# BUILDER-7-PROMPT — hands mission 7a: review 6 and the harness

Kickoff line (the only way this mission is started or resumed):

    Read meta/BUILDER-7-PROMPT.md and execute the mission below its divider.

You are the builder for the `hands` repository. Read `DESIGN.md` (v3.6; §23
is this mission), `CLAUDE.md`, `meta/CHECKPOINT.md` (a unit in progress
means §R first), `meta/reviews/REVIEW-6.md` in full, and the record of job
`0mtygi953-ym63` in `meta/FINAL-REPORT-6.md` (the harness termination).

---

## Mission

Clear review 6's two blockers, close its should-fix 1–6, and make hands
treat a harness termination as the failure it is. Mission 7b (detectors,
the phone channel, `hands who`) is separate and later. Finish with a report
whose first line the playbook can match.

## Execution model (binding)

Unchanged, plus one rule from review 6 should-fix 3: draft `meta/FINAL-
REPORT-N.md` outside the working tree (or under `meta/drafts/`, which
`.gitignore` excludes as of U0) and never `git add -A` while a draft exists
in the tree; a unit commit carries only its own files, and its body lists
every one. `./scripts/check` three times before every commit. Final reply:
`VERDICT: mission 7 finished` | `VERDICT: mission 7 blocked <unit>` |
`VERDICT: question <one line>`.

## Sub-agent brief (verbatim, plus the unit)

    You are implementing one unit of hands. Read, in this order: CLAUDE.md,
    DESIGN.md sections named by the unit, meta/CHECKPOINT.md, the review
    item(s) named by the unit (meta/reviews/REVIEW-6.md), then only the
    files the unit touches. Rules: the design is the spec; write the failing
    test before the code and confirm it fails; ./scripts/check green three
    times before you commit; one commit whose body lists every file it
    touches and states only what the tests prove — never a totality claim
    unless a test enumerates the whole space; never `git add -A`; push;
    never edit meta/plan.md, meta/CHECKPOINT.md or DESIGN.md; if the unit
    needs a design change, stop and write a memo to
    meta/findings/FINDINGS.md; report in ≤12 lines: sha, files, tests
    added, what is NOT proven. Dispatch nothing in the background.

## §R Recovery brief

As before.

## Units, in order

**U0 Plan and corrections.** `meta/plan.md`, `meta/CHECKPOINT.md`;
`.gitignore` gains `meta/drafts/`. Blocker 1: fix `README.md:116-118` to
say what DESIGN §11 and `hands doctor` now say (no open question, a
notification check). Blocker 2: append a dated correction to
`meta/FINAL-REPORT-6.md` §1 U5 item 7 naming `notify --test` as the second
refusal site. Root `CLAUDE.md` gains one line: sub-agents run in the
foreground, never in the background. Append to the ledger a new finding
H-014 describing the harness termination of `0mtygi953-ym63` (600 s
bg-wait ceiling, `exit_code 0`, `state done`, no verdict) with the
decision below.

**U1 Harness termination is `failed` (§2, §6, H-014).** The runner
classifies a job as `failed` when the process ends without a final
`result` event of subtype `success`/`error`, or when stderr carries the
harness's `terminating` line, or when `num_turns` is absent; `stderr_tail`
and a `failure_reason` field say which. The runner sets
`CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0` in the role environment when the
config does not set it (config `[roles.<r>] env` table, new, documented).
`hands doctor` reports the effective value per role. Gate: tests with
`fake_claude` exiting mid-turn, exiting with the `terminating` stderr line,
and exiting cleanly; the playbook end-to-end shows `builder.failed →
resume`.

**U2 The hook covers background sub-agents (§2).** `.claude/hooks/
no_background.py` matches the sub-agent tool as well as Bash (whatever the
tool is called in 2.1.x: `Task`, `Agent`, or both; find out and record it
in the hook's docstring) and refuses a call whose input asks for background
execution, with the same message shape. Self-test and
`tests/test_no_background.py` gain the cases. Gate: tests.

**U3 Doc-truth as a property (blocker 1, should-fix 1, 2).** The doc phrase
test scans every tracked text file (`git ls-files` filtered by extension),
not a list; the phrase list gains the README's wording and the
`test_playbook.py:689` wording; the two U6 regression tests are made
non-circular by asserting on the rendered doctor output and on the driver
file's rule 8 text rather than on the lists they were built from. Gate:
the test fails against `dca0820` and passes at the tip; the commit body
says which files the sweep now reads.

**U4 Client seams (should-fix 4, 5).** The UTF-8 check and the size
measurement walk the same tree through one helper (dict keys, nested lists,
nested dicts); a positional is refused under the name the human typed
(`job`, `path`, `prompt`), never an invented flag. Gate: tests for nested
shapes and for each positional.

**U5 Review base (§10, §23).** `docs/PLAYBOOK.md` and the example rule
describe the review prompt as "every commit after the last `review:`
commit"; the `{job.head_at_start}` placeholder stays available but the docs
say when it is wrong. `meta/REVIEW-PROTOCOL.md` in the kit already says
how the reviewer finds the base; verify the kit copy matches and change
nothing in it. Gate: docs; a test that the example playbook loads.

**U6 Final report.** `meta/FINAL-REPORT-7.md` (drafted under
`meta/drafts/`, moved in by this unit's own commit): what changed, what
tests prove, NOT PROVEN (mandatory), the `## Review items` table for
REVIEW-6 blockers 1–2 and should-fix 1–6. Then the verdict line.

## Budget guidance

Under quota pressure yield U4, then U3's non-circularity half. Never yield
U0–U2, U5, U6.

## Acceptance

- `./scripts/check` green on the pushed tip, three consecutive runs.
- No commit in this mission carries a file its body does not list.
- `README.md` and `docs/` contain no sentence saying the wake-path question
  is open or that doctor prints a wake procedure (the sweep proves it).
- `hands doctor` shows `CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0` for both
  roles on a config that does not set it.
- `meta/FINAL-REPORT-7.md` exists with NOT PROVEN and the review-items
  table.
