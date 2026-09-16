# BUILDER-15-PROMPT — hands mission 15: the guard's table, review 14, the architect role

Kickoff line (the only way this mission is started or resumed):

    Read meta/BUILDER-15-PROMPT.md and execute the mission below its divider.

You are the builder for the `hands` repository. Read `DESIGN.md` (v3.14; §31
is this mission, with §8, §10, §11, §12, §26, §27, §30), `CLAUDE.md`,
`meta/CHECKPOINT.md` (a unit in progress means §R first),
`meta/reviews/REVIEW-14.md` in full, `architect/` (three files that arrive
with this kit), and `meta/BACKLOG.md` ("Mission 15 — the architect role").

---

## Mission

Apply the one-line method to the guard's command table; close review 14's
two blockers and seven should-fix items; build the architect role: its
guard mode, `hands kit file`, the playbook's `architect` and `autonomous`
settings with engine-side approval and kickoff, `consult` for the
architect with its verdicts and escalation conditions. Finish with a
report whose first line the playbook can match.

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
- Your final reply begins with exactly one of: `VERDICT: mission 15
  finished` | `VERDICT: mission 15 blocked <unit>` | `VERDICT: question
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

**U0 Plan and bookkeeping (`plan:` commit).** `meta/plan.md`,
`meta/CHECKPOINT.md`. File H-027 (the guard's command table, review 14
blocker 1) and H-028 (the architect role, §31). Should-fix 7: `hands
doctor` warns when `[series] kickoff` names a brief the repository lacks.

**U1 The guard's command table (§31; blocker 1).** Replace
`ALLOWED_FIRST_WORDS` with the per-command option tables §31 lists, in
both modes; the same loop that judges `git` and `hands` judges every
command; a word not in the table is refused by name; the reviewer's three
probes and the U1 fuzz corpus (from the mission 14 report, if it was
kept; else regenerate 10k commands over the removed words and their
options) are in the tests, all blocked; every command in the driver's
CLAUDE.md and the two self-test tables remains allowed. Update the
guard's docstring and refusal text to say what is true. Gate: tables
green; the commit body lists the removed words and the probes.

**U2 Notifications and doctor (§31; blocker 2; should-fix 1–6).** Spacing
on every branch with the ordinary-branch test; one daemon-start
notification listing re-minted holds; the limit pair documented as
implemented; doctor judges every Bash `PreToolUse` hook; empty project
name refused; the anchor's fields read back in a test; the bare-name
false-positive row pinned. Gate: one test per item.

**U3 Architect guard mode and `hands kit file` (§31).** `HANDS_ROLE=architect`
mode in `driver/hooks/bash_guard.py`: the driver's read-only table plus
`hands kit check|file`, `mkdir|cp|mv|zip|unzip` with every path argument
under `HANDS_KITS`; a `--write` entry point for the Write/Edit/MultiEdit
matcher that allows only paths under `HANDS_KITS`; `architect/settings.json`
as shipped in the kit (verify it against the CLI and fix it if the CLI
differs). `hands kit file <zip>`: path under `HANDS_KITS`, runs the kit
check against the role's clone, refuses a failing kit with the check's
output, else files the held apply exactly as the phone's `kit` does with
`origin: architect`. Gate: guard tests in architect mode (allowed and
refused tables, the write matcher); `kit file` tests for the refusal and
the held job.

**U4 Series mode and autonomy (§31).** `[series] architect`, `autonomous`,
`gate_failures`, `escalate_on`, `[limits] max_architect_consults`; in role
mode with `autonomous`, held applies of origin `architect` approved by the
engine as `decided_by: playbook`, and the kickoff sent after `VERDICT: kit
applied` by an engine rule; `architect = "role"` without
`[roles.architect]` is a config error; the playbook that sets `autonomous`
is gated like any kit (it is: it arrives in a kit). Gate: an end-to-end
test with `fake_claude` as builder and architect: kit filed → approved by
the engine → applied → kickoff sent.

**U5 Consult for the architect (§31).** `consult` with `role =
"architect"` on `aux.done`: the prompt carries the event, the review's
verdict line and its Blockers/Should-fix sections verbatim, the roadmap
file, and the instruction; the engine matches `next kit`, `series
complete`, `escalate`; `escalate` and `series complete` stop with their
reasons, the escalation notification carrying the session id and a
`claude --resume <id>` line; `max_architect_consults` per series; the
`budget-exhausted` condition is the engine's. Gate: end-to-end tests for
each verdict with `fake_claude` as the architect.

**U6 Docs and the templates.** `docs/INTEGRATION.md`: the architect role,
the switch point (from `architect/README.md`), the two-project note
carried forward; `docs/PLAYBOOK.md`: the new keys and events;
`templates/PLAYBOOK-missions.toml` and `-runs.toml` gain a commented
architect block; `docs/ARCHITECT-HANDBOOK.md` §12 gains the role-mode
onboarding; `hands doctor` reports the architect role. Gate: docs sweep;
templates load with the block uncommented.

**U7 This repository's playbook.** `[series] kickoff` becomes
BUILDER-16's line; `architect = "phone"` stated explicitly; nothing else.
Gate: loads; a kit of this brief checked with `--repo .` exits 0.

**U8 Final report.** `meta/FINAL-REPORT-15.md` (drafted under
`meta/drafts/`, moved in by this commit): what changed (sha per unit),
what tests prove, NOT PROVEN (mandatory: a real architect consultation, a
real `kit file` from a role), the `## Review items` table for REVIEW-14
blockers 1–2 and should-fix 1–7. Then the verdict line.

## Acceptance

- `./scripts/check` green on the pushed tip, three consecutive runs.
- Every unit commit's body lists every file it touches; U0 is `plan:`.
- `driver/hooks/bash_guard.py` has no `ALLOWED_FIRST_WORDS`; the reviewer's
  three probes are in the tests, blocked in both modes.
- `hands --help` lists `kit file`; `hands doctor` on a config with
  `[roles.architect]` reports the role.
- `meta/FINAL-REPORT-15.md` exists with NOT PROVEN and the review-items
  table.
