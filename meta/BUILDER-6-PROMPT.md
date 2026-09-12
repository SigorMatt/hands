# BUILDER-6-PROMPT — hands mission 6: close review 5

Kickoff line (the only way this mission is started or resumed):

    Read meta/BUILDER-6-PROMPT.md and execute the mission below its divider.

You are the builder for the `hands` repository. Read `DESIGN.md` (v3.5; §22
is this mission), `CLAUDE.md`, `meta/CHECKPOINT.md` (a unit in progress
means §R first), `meta/reviews/REVIEW-5.md` in full, and findings H-012,
H-013.

---

## Mission

Clear review 5's two blockers, close its should-fix 1–7, and land the
driver-wait retirement in the driver kit and doctor text. The backlog's
mission-7 items are not this mission. Finish with a report whose first line
the playbook can match.

## Execution model (binding)

Unchanged. `./scripts/check` three times before every commit. Final reply:
`VERDICT: mission 6 finished` | `VERDICT: mission 6 blocked <unit>` |
`VERDICT: question <one line>`.

## Sub-agent brief (verbatim, plus the unit)

    You are implementing one unit of hands. Read, in this order: CLAUDE.md,
    DESIGN.md sections named by the unit, meta/CHECKPOINT.md, the review
    item(s) named by the unit (meta/reviews/REVIEW-5.md), then only the
    files the unit touches. Rules: the design is the spec; write the failing
    test before the code and confirm it fails; ./scripts/check green three
    times before you commit; one commit, `<area>: <one line>` + a body
    naming the unit, the DESIGN sections and the review item, stating only
    what the tests prove — never a totality claim ("everything", "no answer
    changes", "anything the client accepts") unless a test enumerates the
    whole space; push; never edit meta/plan.md, meta/CHECKPOINT.md or
    DESIGN.md; if the unit needs a design change, stop and write a memo to
    meta/findings/FINDINGS.md; report in ≤12 lines: sha, files, tests
    added, what is NOT proven.

## §R Recovery brief

As before.

## Units, in order

**U0 Plan and corrections.** `meta/plan.md`, `meta/CHECKPOINT.md` for
mission 6. Append dated corrections to `meta/FINAL-REPORT-5.md` §3 for
blocker 1 (should-fix 3 of review 4 was closed for the prompt, not the
request), blocker 2 (`tail -n 0` changed meaning; a wide trailing entry
answers `[]`), and should-fix 2 (the three hook bypasses the report did
not list). Append to H-012 the decision: the client measures the whole
request.

**U1 Blocker 1 — the whole request on the wire (§4, H-012).** The client
builds the request, measures its wire bytes (the exact bytes it will write,
including `--file` payloads, gate, envelope), and refuses with a one-line
error and exit 2 before connecting when the total exceeds the daemon's
line room; the message names the total, the limit, and which part is
largest. Both prompt routes. `docs/INTEGRATION.md:238-240` and the
`daemon.py` comment are rewritten to say what is measured. Gate: the
reviewer's reproduction (at-cap prompt plus twelve `--file` values of
backslashes) refuses on the client with exit 2 and the daemon log is
untouched; a request just under the limit succeeds.

**U2 Blocker 2 — tail semantics (§4, §7, H-013).** `hands tail -n` requires
`n ≥ 1` (0 and negatives refused with exit 2); the answer carries
`truncated: true` whenever the 1000-entry cap or the read window cut it,
and the human output says so in one line; `hands log <job>` reads the log
file in pages of bounded size and the client prints them in order, so no
single message carries a whole transcript. Gate: tests for `-n 0`, for a
2000-entry transcript (truncated), for a trailing entry wider than the
window (truncated, not `[]`), and for `log` over a 64 MB file with bounded
peak memory measured by `tracemalloc` as U6 of mission 5 did.

**U3 Guard: per-subcommand option allowlist (§12; should-fix 1).**
`driver/hooks/bash_guard.py` replaces its git option denylist with the
allowlist DESIGN §12 specifies: a table from allowed subcommand to allowed
options; any token beginning with `-` that is not in the subcommand's
table is refused; option values that name programs or files are never
listed; the `-C` value must not begin with `-` and must be a single path.
The adversarial table gains the reviewer's `--upload-pack=`, `--exec=`,
`branch --edit-description`, and `-C --exec-path=` probes, each asserted
blocked, and the driver's read-only commands each asserted allowed.
`driver/settings.json` allow rules unchanged. Gate: both tables green; the
commit body enumerates the allowed options per subcommand (this is the
surface, and the report's NOT PROVEN says so).

**U4 Hook bypasses (should-fix 2).** For each of the three bypasses review
5 names, either close it in `.claude/hooks/no_background.py` with a test,
or, where closing is not possible from a hook, list it in
`docs/INTEGRATION.md` under a "what the hook cannot see" heading and in the
report's NOT PROVEN. Gate: tests for the closed ones; the doc for the rest.

**U5 Should-fix 3–7.** (3) `Runner.retained()` counts `last_argv` and the
docstring says what is and is not counted; `last_argv` is popped at job end
or bounded. (4) U2-of-mission-5's containment test is restored as a real
path-resolution test (symlink out of `ops.repo`, `..` after resolution).
(5) The config helper-coverage scan binds every section, including new
ones, and the unknown-key refusal covers new sections. (6) The test audits
exempt by type, not by source text. (7) Both prompt routes refuse invalid
UTF-8 at the same place with the same message. Gate: one test per item.

**U6 Driver kit and doctor text (§11, §12).** `driver/CLAUDE.md` carries
the v3.5 rule 8 (the kit copy is the source of truth; verify it matches
DESIGN §12). `hands doctor`'s wake-path text no longer instructs arming a
background wait; it describes ntfy as the human's doorbell and `check` as
the driver's, and offers the gated-send or `hands pause` procedure as a
one-time notification test. `docs/INTEGRATION.md` and `driver/README.md`
say the same. Gate: `grep -rn 'background' driver/ docs/ src/hands/doctor.py`
returns no instruction to arm one.

**U7 Final report.** `meta/FINAL-REPORT-6.md`: what changed (sha per
unit), what tests prove, NOT PROVEN (mandatory; the guard's surface is the
enumerated option table), and a `## Review items` table mapping REVIEW-5
blockers 1–2 and should-fix 1–7 to `closed <sha>` | `deferred <mission>` |
`not applicable <reason>`. Then the verdict line.

## Budget guidance

Under quota pressure yield U5 items 5 and 6, then U4's documentation half.
Never yield U0–U3, U6, U7.

## Acceptance

- `./scripts/check` green on the pushed tip, three consecutive runs.
- The reviewer's blocker-1 reproduction refuses on the client; the
  reviewer's should-fix-1 probes are in the adversarial table and blocked.
- `driver/CLAUDE.md` rule 8 equals DESIGN §12 rule 8.
- `meta/FINAL-REPORT-5.md` §3 carries the three dated corrections.
- `meta/FINAL-REPORT-6.md` exists with NOT PROVEN and the review-items
  table.
