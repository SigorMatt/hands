# BUILDER-14-PROMPT — hands mission 14: the guard's language, review 13

Kickoff line (the only way this mission is started or resumed):

    Read meta/BUILDER-14-PROMPT.md and execute the mission below its divider.

You are the builder for the `hands` repository. Read `DESIGN.md` (v3.13; §30
is this mission, with §11, §12, §28, §29), `CLAUDE.md`, `meta/CHECKPOINT.md`
(a unit in progress means §R first), and `meta/reviews/REVIEW-13.md` in
full.

---

## Mission

Replace the guard's parser with a language small enough to have no corners:
one line, no redirection, no comments, no escapes, no substitutions. Close
review 13's four blockers and eight should-fix items. Space paired
notifications and remove the held-notify rule from the playbooks. Finish
with a report whose first line the playbook can match.

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
- Your final reply begins with exactly one of: `VERDICT: mission 14
  finished` | `VERDICT: mission 14 blocked <unit>` | `VERDICT: question
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
`meta/CHECKPOINT.md`. File H-026: the guard's parser replaced by a
language (§30), with the review 11–13 history in three lines. Correct
FINAL-REPORT-13's Review items row for REVIEW-11 blocker 1 by an appended
dated line. Should-fix 8: pin `killed` over `limited`.

**U1 The guard's language (§30; blocker 1; should-fix 1).** Before any
tokenizing, refuse a command containing a newline, carriage return, `<`,
`>`, `#`, a backtick, `$(`, `\`, `$'`, or any control character, naming
the first offender and its position; refuse `$` and `!` inside double
quotes; keep `shlex` for the rest and the segment split on `;`, `&&`,
`||`, `|`, `&`. Remove the comment, heredoc, redirection and
expansion-position code that the language makes unreachable, and the
tests that tested it, replacing them with tests of the refusals. Role
mode's `git -C` pin compares `realpath`s. Keep every allowed command in
the tables allowed; every probe of reviews 11, 12 and 13 blocked in both
modes, including the heredoc shape verbatim. `docs/INTEGRATION.md` states
the language in one paragraph. Gate: both tables green; the commit body
lists what was removed and shows the reviewer's heredoc probe refused with
its position.

**U2 Kit check names and who's configs (§30; blockers 2, 3).** `kit check`
judges bare relative names and the punctuation shapes of the handbook's
prompts, enumerated in a fixture; `hands who` loads each config in its own
try and renders a broken one as a root line. Gate: tests including the
reviewer's inputs.

**U3 Config edges (§30; blocker 4; should-fix 6).** `[who] grace_s` finite
and non-negative; project names match `[A-Za-z0-9][A-Za-z0-9._-]{0,63}`
(config file name and `--project`), refused with a message otherwise.
Gate: tests.

**U4 Sweep, doctor, consult (§30; should-fix 2, 3, 4, 5).** The
session-without-mark case pinned as the job's; the pipe-timeout test
binds to the configured value; doctor verifies the hook command names the
guard file and runs its self-test; `max_consults` persists its anchor in
the spool across a restart. Gate: one test each.

**U5 Notifications and the playbooks (§30).** A 1.1 s wait between the two
publishes of one cause (kit receipt then held apply; limit then resume);
`PLAYBOOK.toml` and both templates carry no `job.held → notify` rule (the
kit already removed them; verify and pin with a `kit check` test that a
template with the rule still loads, since other projects may keep it);
retire references to the un-templated units outside the changelog
(should-fix 7). Gate: tests; docs sweep.

**U6 This repository's playbook.** `[series] kickoff` becomes
BUILDER-15's line; nothing else. Gate: loads; a kit of this brief checked
with `--repo .` exits 0.

**U7 Final report.** `meta/FINAL-REPORT-14.md` (drafted under
`meta/drafts/`, moved in by this commit): what changed (sha per unit),
what tests prove, NOT PROVEN (mandatory), the `## Review items` table for
REVIEW-13 blockers 1–4 and should-fix 1–8. Then the verdict line.

## Acceptance

- `./scripts/check` green on the pushed tip, three consecutive runs.
- Every unit commit's body lists every file it touches; U0 is `plan:`.
- `driver/hooks/bash_guard.py` contains no heredoc, comment or
  expansion-position handling; `grep -c heredoc` on it returns 0 outside
  the refusal message and tests.
- Every probe of reviews 11–13 is in `tests/test_bash_guard.py`, asserted
  blocked.
- `meta/FINAL-REPORT-14.md` exists with NOT PROVEN and the review-items
  table.
