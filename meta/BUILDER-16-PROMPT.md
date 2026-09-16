# BUILDER-16-PROMPT — hands mission 16: the guard's language finished, review 15

Kickoff line (the only way this mission is started or resumed):

    Read meta/BUILDER-16-PROMPT.md and execute the mission below its divider.

You are the builder for the `hands` repository. Read `DESIGN.md` (v3.15; §32
is this mission, with §6, §8, §12, §30, §31), `CLAUDE.md`,
`meta/CHECKPOINT.md` (a unit in progress means §R first),
`meta/reviews/REVIEW-15.md` in full, and findings H-030, H-031, H-032.

---

## Mission

Finish the guard's language so that nothing outside its tables can run in
any mode; close review 15's four blockers and seven should-fix items;
resolve H-030 (`hands kit file <dir>`), H-031 and H-032. Finish with a
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
- Your final reply begins with exactly one of: `VERDICT: mission 16
  finished` | `VERDICT: mission 16 blocked <unit>` | `VERDICT: question
  <one line>`.

## Sub-agent brief (give this to every unit sub-agent, verbatim, plus the unit)

    You are implementing one unit of hands. Read, in this order: CLAUDE.md,
    DESIGN.md sections named by the unit, meta/CHECKPOINT.md, the review or
    finding named by the unit, then only the files the unit touches. Rules:
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
`meta/CHECKPOINT.md`. File H-033 (the guard's language finished, review
15 blocker 1, with the review 11–15 history in five lines). Append the
§32 resolutions to H-030, H-031, H-032 and set their status lines.
Correct FINAL-REPORT-15 §3.1's claims about the guard and `unzip` by
appended dated lines.

**U1 The guard's language, finished (§32; blocker 1; should-fix 7).**
Refuse `$`, `{`, `}` anywhere and every reserved word as a word, in every
mode, before tokenizing; the tables judge every word including values;
role-mode reads confined to the clone and the spool's paths with a
refusal that says so. Remove the code the language makes unreachable.
Every probe of reviews 11–15 blocked in all three modes, including the
`for`/`${c@P}` shapes verbatim; every command in the driver's and the
architect's CLAUDE.md allowed; a fuzz corpus over the reserved words and
`$`/brace shapes (10k commands) all refused. `docs/INTEGRATION.md`'s
paragraph states the whole language. Gate: tables and fuzz green; the
commit body lists what was removed.

**U2 Architect mode and `hands kit file <dir>` (§32; blocker 2; H-030).**
`unzip` and `zip` leave the tables; `mkdir`/`cp`/`mv` confined as §32
says; `hands kit file <dir>` builds the zip from a staged directory under
`HANDS_KITS`, checks it against the role's clone, refuses a failing kit
with the check's output, and files the held apply with `origin:
architect` and a daemon-minted `kit_id`. The reviewer's `unzip` probes
are refused. `architect/CLAUDE.md`, `architect/README.md` and
`docs/ARCHITECT-HANDBOOK.md` say directory kits. Gate: tests.

**U3 Autonomy and origins (§32; blocker 3; should-fix 1, 2, 3; H-032).**
Engine approval only for a daemon-created apply with a known `kit_id`
under a role-mode autonomous playbook; a socket client cannot set
`origin: architect` (refused with a message); the kickoff-after-apply
rule fires only for such an apply; `next kit` waits for the filed
`kit_id` with `[series] kit_wait_s`; the budget anchors to `[series]
name`, rename refused unless `max_architect_consults` is restated;
`Api.send` refuses direct sends to `driver` and `architect`. Gate:
end-to-end tests including the reviewer's probes (a held job with
forged origin is not approved).

**U4 Config, doctor, prompt, notifications (§32; blocker 4; should-fix 4,
5, 6).** `architect = "role"` without `[roles.architect]` refused by the
loader and by `kit check`; doctor's architect row checks the four things
§32 lists; the consult prompt carries the next unmet milestone and the
roadmap path; daemon start publishes exactly one notification (test binds
the count). Gate: tests.

**U5 Playbook severity (§32).** `monitor.task_killed → notify` in the
example, this repository's playbook and both templates (the kit already
changed them; verify and pin); `docs/PLAYBOOK.md` explains why. Gate:
docs sweep; the playbooks load.

**U6 This repository's playbook.** `[series] kickoff` becomes
BUILDER-17's line; nothing else. Gate: loads; a kit of this brief checked
with `--repo .` exits 0.

**U7 Final report.** `meta/FINAL-REPORT-16.md` (drafted under
`meta/drafts/`, moved in by this commit): what changed (sha per unit),
what tests prove, NOT PROVEN (mandatory), the `## Review items` table for
REVIEW-15 blockers 1–4 and should-fix 1–7. Then the verdict line.

## Acceptance

- `./scripts/check` green on the pushed tip, three consecutive runs.
- Every unit commit's body lists every file it touches; U0 is `plan:`.
- The guard refuses `$`, `{`, `}` and every reserved word in all three
  modes (tests); no `unzip` row exists.
- `hands kit file` accepts only a directory under `HANDS_KITS`.
- `meta/FINAL-REPORT-16.md` exists with NOT PROVEN and the review-items
  table.
