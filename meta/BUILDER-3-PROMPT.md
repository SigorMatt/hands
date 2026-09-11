# BUILDER-3-PROMPT — hands mission 3: close the review

Kickoff line (the only way this mission is started or resumed):

    Read meta/BUILDER-3-PROMPT.md and execute the mission below its divider.

You are the builder for the `hands` repository. Read `DESIGN.md` (v3.2; §19
lists what this mission implements), `CLAUDE.md`, `meta/CHECKPOINT.md` (a
unit in progress means you are resuming: run §R first), and
`meta/reviews/REVIEW-2.md` in full — its eight should-fix items are most of
this mission, and each unit below names the item it closes.

---

## Mission

Close review should-fix 2–8, fix the Bash guard's false positive, add
`hands send --prompt-file`, and put the guard under the test suite. No new
behaviour beyond DESIGN §19. Finish with a report whose first line the
playbook can match.

## Execution model (binding)

Unchanged from missions 1 and 2. Your final reply begins with exactly one of
`VERDICT: mission 3 finished` | `VERDICT: mission 3 blocked <unit>` |
`VERDICT: question <one line>`.

## Sub-agent brief (verbatim, plus the unit)

    You are implementing one unit of hands. Read, in this order: CLAUDE.md,
    DESIGN.md sections named by the unit, meta/CHECKPOINT.md, the review
    item named by the unit (meta/reviews/REVIEW-2.md), then only the files
    the unit touches. Rules: the design is the spec; write the failing test
    before the code and confirm it fails; ./scripts/check green before you
    commit; one commit, `<area>: <one line>` + a body naming the unit, the
    DESIGN sections and the review item; push; never edit meta/plan.md,
    meta/CHECKPOINT.md or DESIGN.md; if the unit needs a design change, stop
    and write a memo to meta/findings/FINDINGS.md; report in ≤12 lines: sha,
    files, tests added, what is NOT proven.

## §R Recovery brief

As before.

## Units, in order

**U0 Plan.** `meta/plan.md` and `meta/CHECKPOINT.md` for mission 3. Fix
`meta/journal.md:17` (should-fix 6): replace the unreachable sha with the
reachable one, `3c5d880`, and add a one-line note that the original entry
was amended.

**U1 Status describes the deciding monitor (should-fix 2, §4).** `hands
status` prints the built-in stall rule only when `monitor.source == builtin`;
for `ops` it prints the script path and the three flags it is given; for
`stall_minutes = 0` it says detection is off. Gate: tests for all three.

**U2 Tests that can fail (should-fix 3 and 8).** The four `BAD_PLAYBOOKS`
assertions pin the refusal message on `run = "..."` or on the sentence,
not on the substring `run`; confirm three of them fail against `34b4ede^`
in a worktree and say so in the commit body. The `queue_capacity` alias test
asserts on aux (depth 4), not builder. Gate: the tests, and the commit body
evidence.

**U3 Pause keeps the first reason (should-fix 4, §10).** `hands pause` on a
pipeline already stopped for another reason is a no-op that prints the
existing reason and files no event and no notification; `hands pipeline`
keeps showing the original stop. Gate: tests for pause-after-rule-stop and
pause-after-held.

**U4 Empty `resume_line` refused (should-fix 5, §6).** `resume_line = ""`
is a config error at load with a message naming the two valid choices (omit
the key, or a non-empty line). `docs/INTEGRATION.md` says so. Gate: test.

**U5 notify status on failure (should-fix 7, §4).** `hands notify --test`
prints `ntfy <code> <url>` for any HTTP response, 2xx or not, and exits 1
only on non-2xx or transport error; one test drives a real `httpx`
`MockTransport` returning 403. Gate: tests; the `-> int` return verified
against httpx rather than a monkeypatch.

**U6 Guard fix and guard tests (§19).** In `driver/hooks/bash_guard.py`:
the mutating-git check moves out of `FORBIDDEN_PATTERNS` into the git
subcommand logic (subcommand position only), so `git -C ./repo rev-parse
<sha>^{commit}` and `git log --grep=commit` pass while `git commit`,
`git -C ./repo push` and `git -c x=y commit` are blocked; add those cases
to `SELFTEST`. New `tests/test_bash_guard.py` imports the hook by path and
runs every `SELFTEST` case, so `./scripts/check` covers the guard.
`driver/settings.json` drops the `MultiEdit` deny rule (no such tool in
2.1.x; Claude Code warns at start). Gate: the new test file green; self-test
green.

**U7 `hands send --prompt-file PATH` (§4, §12).** The CLI reads the prompt
from the file (UTF-8, any readable path; the CLI is a client, not the
daemon, so no root confinement) and sends it byte-for-byte; mutually
exclusive with `--stdin` and the positional prompt. `driver/CLAUDE.md` rule 6
becomes: prompts and long content travel as files (`--prompt-file`,
`hands put`); `docs/INTEGRATION.md` and the driver's command list updated;
`bash_guard` self-test gains a `--prompt-file` case. Gate: tests including
a prompt containing `>`, `(`, quotes and a newline arriving verbatim in the
job record.

**U8 Final report.** `meta/FINAL-REPORT-3.md`: what changed (sha per
unit), what tests prove, NOT PROVEN (mandatory), and a `## Review items`
table mapping should-fix 1–8 to `closed <sha>` | `not applicable
<reason>` (1 is the brief's, closed by this file's acceptance wording).
Then the verdict line.

## Budget guidance

Under quota pressure yield U1, then U5. Never yield U0, U2, U3, U6, U7, U8.

## Acceptance

- `./scripts/check` green on the pushed tip.
- `only_if_run_in` appears only at the refusal site in `src/hands/playbook.py`,
  in the tests that pin that refusal, and in `docs/PLAYBOOK.md`'s migration
  note; `dispatch.sh` appears only in `DESIGN.md` and `meta/`.
- `hands send --help` lists `--prompt-file`; `tests/test_bash_guard.py`
  exists and is collected by pytest.
- `meta/FINAL-REPORT-3.md` exists with a non-empty NOT PROVEN section and
  the review-items table.
