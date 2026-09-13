# BUILDER-10-PROMPT — hands mission 10: the closed loop and the architect's tools

Kickoff line (the only way this mission is started or resumed):

    Read meta/BUILDER-10-PROMPT.md and execute the mission below its divider.

You are the builder for the `hands` repository. Read `DESIGN.md` (v3.9; §26
is this mission, with §4, §8, §10, §11, §13), `CLAUDE.md`,
`meta/CHECKPOINT.md` (a unit in progress means §R first),
`meta/reviews/REVIEW-9.md` in full, `docs/ARCHITECT-HANDBOOK.md` and
`templates/` (both arrive with this kit; U5 checks them against the code).

---

## Mission

Close review 9's four should-fix items; add `[series] kickoff` and the
phone's `go`; add kit transport by ntfy attachment; match sessions to
transcripts by pid in `hands who`; ship `hands kit check` and verify the
handbook and templates against the code; describe the closed loop in the
docs. Finish with a report whose first line the playbook can match.

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
- Your final reply begins with exactly one of: `VERDICT: mission 10
  finished` | `VERDICT: mission 10 blocked <unit>` | `VERDICT: question
  <one line>`.

## Sub-agent brief (give this to every unit sub-agent, verbatim, plus the unit)

    You are implementing one unit of hands. Read, in this order: CLAUDE.md,
    DESIGN.md sections named by the unit, meta/CHECKPOINT.md, the review or
    backlog item named by the unit, then only the files the unit touches.
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
`meta/CHECKPOINT.md`. Review 9 should-fix 2 (`docs/INTEGRATION.md`'s
`done` statement matches §6) and 4 (H-017 quotes v3.7 correctly; append,
never rewrite). File H-018 for the closed-loop decisions (§26).

**U1 Review 9 should-fix 1 and 3.** The REVIEW-8 should-fix 3 check fails
on the condition it guards (prove it with a fixture that would have passed
before); the HEAD comparison of the playbook runs git with a scrubbed
environment (no `GIT_DIR`, `GIT_WORK_TREE`, `GIT_INDEX_FILE`;
`-c core.autocrlf=false`) and compares bytes after normalizing line
endings. Gate: tests including a CRLF-checked-out copy.

**U2 `[series] kickoff` and `go` (§10, §11, §26).** The playbook loader
accepts `[series] kickoff = "<line>"` (optional; unknown keys in
`[series]` refused). The phone channel accepts `go <secret>`: refused with
a logged reason when no playbook is loaded, when `[series] kickoff` is
absent, or when the builder has a running or queued job; otherwise sends
that line as a `clear` send with `origin: phone` and answers on
`ntfy_topic` with the job id. `docs/PLAYBOOK.md` and `docs/INTEGRATION.md`
updated; `PLAYBOOK.toml` of this repository gains `[series] kickoff =
"Read meta/BUILDER-11-PROMPT.md and execute the mission below its
divider."` (the next mission's line; kits update it). Gate: tests for each
refusal and the happy path; the playbook end-to-end still passes.

**U3 Kit transport (§26).** A `cmd_topic` message with body `kit <secret>`
and an attachment: handsd fetches the attachment URL (ntfy's
`attachment.url`), refuses names that are not a `.zip` basename, refuses
sizes over `[files] kit_max_mb` (default 20) before downloading (ntfy
reports the size), writes to `[files] kit_dir` (default `~/Downloads`,
must be an allowed root) atomically (temp file, rename), never unzips,
never executes, and files `kit.received` to the inbox and a notification
`kit received <name> <bytes> <sha256>`; a name that already exists is
written with a numeric suffix, never overwritten. Gate: tests with a
mocked ntfy stream and a local HTTP server for the attachment: happy path,
oversize, bad name, duplicate name, missing secret.

**U4 Who by pid (§26).** `hands who` matches each interactive `claude`
process to its transcript through the pid the transcript records (find
the field in a real transcript's first entry and quote it in a test
fixture), falling back to the newest transcript only when no pid match
exists and saying so in the line (`transcript: by directory`). Gate: a
fixture with two transcripts in one directory, one per pid, attributes
each correctly.

**U5 `hands kit check` (§4, §26).** Implement the checks §26 lists as a
CLI command that works without a daemon; it reads the brief's final-reply
vocabulary from the lines following "Your final reply begins with" (or
"Reply with one of") and the playbook's `verdict` regexes, and prints the
apply prompt (§3 of the handbook) listing every file. Then run it on the
kit that applied this mission (the files at the kit commit) and on
`templates/` filled with placeholders, and fix the handbook or templates
where the code contradicts them; anything you cannot reconcile is a
finding, not a silent edit. Gate: tests for each check with a passing kit
and one failing kit per check; `hands kit check` green on this mission's
kit files.

**U6 The closed loop in the docs (§26).** `docs/INTEGRATION.md`: the loop
end to end from the phone (send kit, approve, `go`, wait for the buzz),
the driver as inspector; `README.md` updated; `hands doctor` reports
`go` and kit transport as on/off. Gate: docs sweep green.

**U7 Final report.** `meta/FINAL-REPORT-10.md` (drafted under
`meta/drafts/`, moved in by this commit): what changed (sha per unit),
what tests prove, NOT PROVEN (mandatory: real ntfy attachment delivery,
real `go` from a phone), the `## Review items` table for REVIEW-9
should-fix 1–4. Then the verdict line.

## Acceptance

- `./scripts/check` green on the pushed tip, three consecutive runs.
- Every unit commit's body lists every file it touches; U0 is `plan:`.
- `hands --help` lists `kit`; `hands kit check` on this mission's kit
  files exits 0.
- `PLAYBOOK.toml` carries `[series] kickoff` naming BUILDER-11.
- `meta/FINAL-REPORT-10.md` exists with NOT PROVEN and the review-items
  table.
