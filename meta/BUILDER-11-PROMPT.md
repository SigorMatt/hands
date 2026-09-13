# BUILDER-11-PROMPT — hands mission 11: review 10, the apply from the kit, the driver role

Kickoff line (the only way this mission is started or resumed):

    Read meta/BUILDER-11-PROMPT.md and execute the mission below its divider.

You are the builder for the `hands` repository. Read `DESIGN.md` (v3.10; §27
is this mission, with §6, §8, §10, §11, §26), `CLAUDE.md`,
`meta/CHECKPOINT.md` (a unit in progress means §R first),
`meta/reviews/REVIEW-10.md` in full, `meta/FINAL-REPORT-10.md` §5, and
findings H-018 to H-021.

---

## Mission

Close review 10's blocker (`hands who` by the sessions file) and its seven
should-fix items; make `handsd` create the held apply job from a received
kit; add the driver role and the `consult` playbook action with its
follow-up events; give this repository's playbook its consult rules and
the next kickoff. Finish with a report whose first line the playbook can
match.

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
- Your final reply begins with exactly one of: `VERDICT: mission 11
  finished` | `VERDICT: mission 11 blocked <unit>` | `VERDICT: question
  <one line>`.

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
`meta/CHECKPOINT.md`. Append to H-018, H-019, H-020, H-021 the v3.10
resolutions (§27) and set their status lines. Review 10 should-fix 7: a
test pins `docs/INTEGRATION.md`'s `done` statement to §6.

**U1 Review 10 should-fix 1, 3, 4, 5, 6 (§27).** `go` refused while the
builder has a held job (message names it); the post-exit sweep signals a
group only when its leader is the job's pid and every member is a
descendant, with a foreign-group test; `kit check`: the apply-verdict
exception never excuses a builder rule that matches nothing, and paths
outside the repo, absolute, `..`, and a missing protocol path are refused;
a malformed attachment URL is refused before any fetch with an inbox event
`kit.refused`. Gate: one test per item.

**U2 Who by the sessions file (§27; H-020; review 10 blocker 1).**
`hands who` reads `~/.claude/sessions/<pid>.json` for each interactive
`claude` pid, takes its `sessionId`, and attributes that transcript; with
no sessions file the line says `transcript: by directory` and a transcript
belonging to a hands job (known pids) is never attributed to a session.
Gate: a fixture with two transcripts in one directory and two sessions
files attributes each by pid; the job-in-same-cwd case shows nothing under
the human's session.

**U3 The apply from the kit (§27; review 10 should-fix 2).** On
`kit.received`, `handsd` lists the zip's entries, computes replaced/added
against `role.builder.cwd`, takes the commit message from `KIT.md`'s first
line (else `plan: kit <name>`), builds the standard apply prompt (the exact
shape `docs/ARCHITECT-HANDBOOK.md` §3 gives, files named, `VERDICT: kit
applied <sha>` required), and creates a **held** builder job with `origin:
kit` and gate reason `apply <name>`; the notification carries the buttons.
A zip with entries outside the repo, absolute, or with `..` is refused
(`kit.refused`). `hands kit check` prints the same prompt and writes the
expected `KIT.md` shape in its output. Gate: tests for the prompt text
(byte-equal between `kit check` and the daemon), the held job, the
refusals.

**U4 The driver role (§8, §27).** `[roles.driver]` in config: cwd, no
permission bypass (`permission_flags` must be empty; doctor refuses
otherwise), `env` adds `HANDS_ROLE=driver`. `driver/hooks/bash_guard.py`
gains role mode: when `HANDS_ROLE=driver`, the allowlist is §27's (read-only
git; `hands show|jobs|inbox|pipeline|status|tail|kit check`; `hands send`
only with `--context keep`; `hands resume`; everything else refused,
including `approve`, `deny`, `pause`, `go`, `put`, any `--context clear`).
`driver/CLAUDE.md` gains a short "As a role" section: you were started by
handsd to resolve one consultation; answer within your authority or
escalate; first line `VERDICT: resolved …` | `VERDICT: escalate …`.
`hands doctor` reports the role. Gate: guard tests for role mode (a table
of allowed and refused commands); doctor refusal test.

**U5 `consult` (§10, §27).** Playbook action `consult`: sends the driver
role a prompt carrying the event, the job record (id, role, verdict,
result verbatim) and the instruction from §27; events `driver.done` and
`driver.failed`; `[limits] max_consults` (default 2) per mission counted
from the last kickoff; exceeded → stop with reason; follow-up rules on
`driver.done` with `^VERDICT: resolved` (then nothing: the driver already
acted) and `^VERDICT: escalate` (stop, message with the reason); an
unrecognised driver verdict stops. Every consultation files
`consult.sent`/`consult.done` inbox events and appends one line to
`meta/journal.md` in `role.builder.cwd` (plan-only commit is not required;
the line is written to the working tree and the next builder commit
carries it). `docs/PLAYBOOK.md`, `docs/INTEGRATION.md`, `kit check` (knows
`consult`, `driver.done`, `driver.failed`). Gate: an end-to-end test with
`fake_claude` as the driver: question → consult → resolved (keep sent to
the builder); question → consult → escalate (stop); a third consult in one
mission → stop.

**U6 This repository's playbook.** `PLAYBOOK.toml`: `[series] kickoff`
becomes BUILDER-12's line; `[limits] max_consults = 2`; `builder.done`
with `^VERDICT: question` and the unrecognised-verdict catch-all route to
`consult` (role driver), with the two follow-up rules; `[roles.driver]`
added to `docs/INTEGRATION.md`'s example config with cwd
`~/hands-driver/hands`. Gate: the playbook loads; `hands kit check` on the
repository's own files exits 0.

**U7 Final report.** `meta/FINAL-REPORT-11.md` (drafted under
`meta/drafts/`, moved in by this commit): what changed (sha per unit),
what tests prove, NOT PROVEN (mandatory: a real consultation, a real
apply-from-kit from a phone), the `## Review items` table for REVIEW-10
blocker 1 and should-fix 1–7. Then the verdict line.

## Acceptance

- `./scripts/check` green on the pushed tip, three consecutive runs.
- Every unit commit's body lists every file it touches; U0 is `plan:`.
- `hands who` on a fixture with a job and a session in one cwd attributes
  nothing of the job to the session (test).
- `PLAYBOOK.toml` names BUILDER-12 and has `consult` rules; `hands kit
  check .` exits 0.
- `meta/FINAL-REPORT-11.md` exists with NOT PROVEN and the review-items
  table.
