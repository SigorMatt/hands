# BUILDER-4-PROMPT — hands mission 4: blockers and pipeline state

Kickoff line (the only way this mission is started or resumed):

    Read meta/BUILDER-4-PROMPT.md and execute the mission below its divider.

You are the builder for the `hands` repository. Read `DESIGN.md` (v3.3; §20
is this mission), `CLAUDE.md`, `meta/CHECKPOINT.md` (a unit in progress
means §R first), and `meta/reviews/REVIEW-3.md` in full: its three blockers
are U1–U3 and its should-fix items are named by unit below.

---

## Mission

Clear review 3's three blockers, make pipeline state behave as DESIGN §10
now specifies, harden the Bash guard properly, and close should-fix 1, 2,
4, 5, 8, 9, 10 and 11. Should-fix 3, 6 and 7 are deferred to a later
mission and are listed as such in the report. Finish with a report whose
first line the playbook can match.

## Execution model (binding)

Unchanged. Final reply: `VERDICT: mission 4 finished` | `VERDICT: mission 4
blocked <unit>` | `VERDICT: question <one line>`.

## Sub-agent brief (verbatim, plus the unit)

    You are implementing one unit of hands. Read, in this order: CLAUDE.md,
    DESIGN.md sections named by the unit, meta/CHECKPOINT.md, the review
    item(s) named by the unit (meta/reviews/REVIEW-3.md), then only the
    files the unit touches. Rules: the design is the spec; write the failing
    test before the code and confirm it fails; ./scripts/check green before
    you commit — run it three times for this mission, since review 3 found
    the gate non-deterministic; one commit, `<area>: <one line>` + a body
    naming the unit, the DESIGN sections and the review item; the body
    states only what the tests prove; push; never edit meta/plan.md,
    meta/CHECKPOINT.md or DESIGN.md; if the unit needs a design change, stop
    and write a memo to meta/findings/FINDINGS.md; report in ≤12 lines: sha,
    files, tests added, what is NOT proven.

## §R Recovery brief

As before.

## Units, in order

**U0 Plan and corrections.** `meta/plan.md`, `meta/CHECKPOINT.md` for
mission 4. Blocker 3: append to `meta/FINAL-REPORT-3.md` §3 a dated
correction line stating that the installed daemon was already the mission-2
build when the report was written (`hands --version` and `hands --help |
grep notify` are the evidence); do not rewrite the original text. Amend
H-010 in the ledger (append, never rewrite) with both observations: the CLI
warned "matches no known tool" at driver start on 2.1.268, and review 3
found `MultiEdit` in the permission-rule normalizer of 2.1.269; the
decision is to keep the rule.

**U1 Blocker 1 — guard scope (DESIGN §12, §20).** In
`driver/hooks/bash_guard.py`: the git allowlist (`ALLOWED_GIT_SUBCOMMANDS`,
minus forbidden flags) is applied to **every** `git` token anywhere in the
command, not only at a segment's first word; `find` with `-exec`,
`-execdir`, `-ok`, `-okdir` or `-delete` is forbidden; `MUTATING_GIT_SUBCOMMANDS`
and the first-level-only check are removed. `tests/test_bash_guard.py`
gains an **adversarial table written by the sub-agent without reading
`SELFTEST`** (should-fix 1): at least twenty cases of argument-position
git, second-level verbs (`remote add`, `notes add`, `submodule add`,
`update-index --add`, `config`), wrappers (`find -exec`, `xargs`, `env`,
`sh -c`), substitutions in double quotes, and the false positives that must
pass (`rev-parse <sha>^{commit}`, `log --grep=commit`, `show
origin/main:path`). `SELFTEST` also runs. `driver/settings.json` restores
`"MultiEdit"` in `permissions.deny` (should-fix 2). Gate: both tables green;
the commit body lists which adversarial cases failed against `ecdb0f3`.

**U2 Blocker 2 — a deterministic gate (should-fix 11).** Fix
`tests/test_daemon.py:556` to assert on the stall sentence (or its
absence) rather than on `"40"` in a line that carries a tmpdir path; audit
every assertion in `tests/test_daemon.py` and `tests/test_playbook.py`
that matches a bare number or a substring which a path or a counter could
contain, and pin them. Then run `./scripts/check` five times; the commit
body reports 5/5. Gate: 5/5 green.

**U3 Pipeline state (DESIGN §10, §20; should-fix 4).** (a) A `cli`-origin
send un-pauses the pipeline when the job **starts**, not when it is filed;
a held or queued send changes nothing; a job started by the playbook or by
the limit manager never clears a stop. (b) One `stop()` for every
component: the limit manager's `max_resumes` stop goes through the engine
and inherits the keep-first-reason rule; a later stop over an existing one
files an inbox event `stop.suppressed` with the would-be reason and sends
no notification. (c) `last_rule` is reset when a playbook with a different
sha256 loads. (d) `pipeline.resumed` payload says `by: start` or `by:
resume`. Gate: tests for gate-time no-op, start-time un-pause, playbook
job not un-pausing, limit stop over rule stop, and `last_rule` reset; the
engine-level end-to-end from mission 1 still passes.

**U4 Optional keys and doctor (should-fix 5, 8).** Empty strings are
refused at config load for `ops.monitor_cmd`, `server.ntfy_topic` and any
other optional string key, with a message naming the two valid choices;
`hands doctor` catches a config error and reports it as a failed `config`
row with the message, exit 1, instead of crashing. Gate: tests for each key
and for doctor.

**U5 `--prompt-file` refusals and driver rule 6 (should-fix 9, 10; DESIGN
§4, §12).** The client refuses a missing, unreadable, empty or over-10 MB
prompt file with a one-line error and exit 2, before contacting the daemon.
`driver/CLAUDE.md` rule 6 becomes the §12 text of DESIGN v3.3 (prompts the
architect wrote arrive as files the human places; the driver's own prompts
are short and quoted; the driver never plans to write a file). Remove the
contradictory sentence about metacharacters. Gate: tests for the four
refusals; a grep for "metacharacters" in `driver/` returns nothing.

**U6 Final report.** `meta/FINAL-REPORT-4.md`: what changed (sha per
unit), what tests prove, NOT PROVEN (mandatory), and a `## Review items`
table mapping review 3 blockers 1–3 and should-fix 1–11 to `closed <sha>` |
`deferred <mission>` | `not applicable <reason>`. Then the verdict line.

## Budget guidance

Under quota pressure yield U4, then U5. Never yield U0–U3, U6.

## Acceptance

- `./scripts/check` green on the pushed tip, three consecutive runs.
- `tests/test_bash_guard.py` has two tables and the adversarial one has
  at least twenty cases; `MUTATING_GIT_SUBCOMMANDS` does not exist.
- `driver/settings.json` denies `MultiEdit`; `driver/` contains no
  "metacharacters".
- `meta/FINAL-REPORT-3.md` §3 carries the dated correction; H-010 carries
  the amendment.
- `meta/FINAL-REPORT-4.md` exists with NOT PROVEN and the review-items
  table.
