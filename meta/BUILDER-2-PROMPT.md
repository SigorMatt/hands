# BUILDER-2-PROMPT — hands mission 2: the shakeout

Kickoff line (the only way this mission is started or resumed):

    Read meta/BUILDER-2-PROMPT.md and execute the mission below its divider.

You are the builder for the `hands` repository. This mission is dispatched
by hands itself (`hands send`), so you are the first builder that hands has
ever run; behave exactly as in mission 1. Read `DESIGN.md` (now v3.1, §18
lists what changed), `CLAUDE.md`, `meta/CHECKPOINT.md` (if it names a unit
in progress you are resuming: run §R first), `meta/FINAL-REPORT-1.md` §3
(NOT PROVEN) and `meta/findings/FINDINGS.md` H-001–H-008.

---

## Mission

Land the code changes DESIGN v3.1 §18 implies, retire the bootstrap files,
add the one new command, and finish with a report whose first line the
playbook can match. Small units; the point of this mission is as much to
exercise hands (dispatch, monitor, wake, playbook chaining into a cold
review) as to change code.

## Execution model (binding)

Unchanged from mission 1: thin orchestrator; ONE sub-agent per unit; write
`meta/CHECKPOINT.md` before each unit and update it after; one line per unit
in `meta/journal.md`; every unit ends with a commit AND a push; retry once,
then `blocked`; never edit product code yourself; never edit `DESIGN.md`
(file a finding). Your final reply begins with exactly one of:

    VERDICT: mission 2 finished
    VERDICT: mission 2 blocked <unit>
    VERDICT: question <one line>

The first form is matched by `PLAYBOOK.toml` and chains a cold review; use
it only when every unit is `[x]` and the acceptance below holds.

## Sub-agent brief (verbatim, plus the unit)

    You are implementing one unit of hands. Read, in this order: CLAUDE.md,
    DESIGN.md sections named by the unit, meta/CHECKPOINT.md, the finding(s)
    named by the unit, then only the files the unit touches. Rules: the
    design is the spec; write the failing test before the code and confirm
    it fails; ./scripts/check green before you commit; one commit, `<area>:
    <one line>` + a body naming the unit, the DESIGN sections and the
    finding; push; never edit meta/plan.md, meta/CHECKPOINT.md or DESIGN.md;
    if the unit needs a design change, stop and write a memo to
    meta/findings/FINDINGS.md; report in ≤12 lines: sha, files, tests added,
    what is NOT proven.

## §R Recovery brief

As mission 1: finish the unit if it can pass the gate, else stash as
`wip <unit> <date>`, record where it stopped, leave the tree clean, push.

## Units, in order

**U0 Plan.** Fill `meta/plan.md` for mission 2 from this list; reset
`meta/CHECKPOINT.md` for mission 2. Update each finding's `Status` line as
its unit lands (append a status line; the ledger is append-only).

**U1 Origin `limit` (H-004, DESIGN §6, §4).** `ORIGINS` gains `limit`;
limit resumes are filed with it; `hands jobs --origin <o>` filters; the
`resume` inbox event carries `origin`. Existing `resumed_from` unchanged.
Gate: tests for the filter and for a limit resume's record.

**U2 Resume line optional (H-008, §6).** `role.resume_line` has no default.
When absent, a builder limit resume re-sends the limited job's prompt;
when set, it sends the line. Aux unchanged (always the same prompt).
`hands doctor` reports which behaviour each role has. Gate: tests for both.

**U3 Explicit `run` key (H-006, §10).** Rules take `run = "<expr>"` (the
expression grammar of placeholders: named groups and `{name+k}`); at load
time a rule with `run` is refused if `[limits] auto_runs` is empty or the
expression uses a group the rule's `verdict` does not define. `only_if_run_in`
is refused at load with a message naming `run`. `docs/PLAYBOOK.md` updated.
Gate: table-driven tests; the DESIGN §10 example (now with `run`) still
passes end to end.

**U4 Pause files an event (H-007, §11).** `hands pause` files a `stop`
inbox event with reason `paused by human` (and notifies, like any stop);
`hands resume` files `pipeline.resumed`. `hands doctor`'s wake procedure
offers `hands pause` as the simplest event and keeps the gated send.
Gate: a `wait --for stop` returns on `pause`.

**U5 `hands notify --test` (§4).** Sends one message to the configured
topic through the real transport; prints the HTTP status. Refuses when
`ntfy_topic` is unset. Gate: transport mocked in tests; the command exists in
`hands --help`.

**U6 Status wording and monitor limitation.** `hands status` output and
`--json` document `queue_depth` as capacity (rename nothing; add a one-line
note in the human output and a `queue_capacity` alias in JSON if cheap).
Gate: test on the output.

**U7 Retire bootstrap.** Delete `bootstrap/`; remove the bootstrap section
and every `dispatch.sh` mention from `driver/CLAUDE.md`, `driver/README.md`,
`README.md`, `docs/INTEGRATION.md`; `driver/settings.json` drops the
`./dispatch.sh` allow rule; `driver/hooks/bash_guard.py` drops it from
`ALLOWED_FIRST_WORDS` and its self-test. Gate: `grep -rn dispatch.sh` over
the repo returns nothing; self-test green.

**U8 Final report.** `meta/FINAL-REPORT-2.md`: what changed (sha per unit),
what tests prove, NOT PROVEN (mandatory), findings status. Then the verdict
line.

## Budget guidance

Under quota pressure yield U6, then U5. Never yield U0–U4, U7, U8.

## Acceptance

- `./scripts/check` green on the pushed tip.
- `grep -rn 'dispatch.sh\|only_if_run_in' --include='*' . ` returns only
  ledger/report lines (history), nothing in code, docs or driver files.
- `hands --help` lists `notify`.
- `meta/FINAL-REPORT-2.md` exists with a non-empty NOT PROVEN section.
- Every finding H-001–H-008 has a current `Status` line (`fixed <sha>`,
  `open` with a reason, or `rejected <reason>`).
