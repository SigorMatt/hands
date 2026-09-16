# BUILDER-17-PROMPT — hands mission 17: review 16, talking to the architect

Kickoff line (the only way this mission is started or resumed):

    Read meta/BUILDER-17-PROMPT.md and execute the mission below its divider.

You are the builder for the `hands` repository. Read `DESIGN.md` (v3.16; §33
is this mission, with §8, §11, §26, §31, §32), `CLAUDE.md`,
`meta/CHECKPOINT.md` (a unit in progress means §R first), and
`meta/reviews/REVIEW-16.md` in full.

---

## Mission

Close review 16's two blockers and eight should-fix items, then add
`reply` on the command channel and the self-hosted ntfy option. Finish
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
- Your final reply begins with exactly one of: `VERDICT: mission 17
  finished` | `VERDICT: mission 17 blocked <unit>` | `VERDICT: question
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
`meta/CHECKPOINT.md`. File H-034 (the daemon must run the check it
approves on, review 16 blocker 1) and H-035 (zip names, blocker 2).
Correct FINAL-REPORT-16's review-items row for REVIEW-15 blocker 3 and
its §3.2 text by appended dated lines. Should-fix 8: the sweep's messages
name no cause; the finding's overstatement corrected by an appended line.

**U1 The daemon checks what it approves (§33; blocker 1; should-fix 1,
5).** `kit_file` runs `check_kit` on the stored bytes against the
builder's clone and refuses a failing kit with the output; the engine
approves only an apply whose `kit_id` records a passing check; one kit
per consultation, named as the architect's verdict names it, else denied
and `escalate`; `kit check` judges a role-mode playbook's role
requirements against the repository's config. Gate: the reviewer's
end-to-end probe (a raw-socket `kit_file` of a failing kit during a
consultation) is not approved; a passing kit is; two kits in one
consultation → the second denied.

**U2 Zip names (§33; blocker 2).** One judge over central-directory
names, shared by the daemon and `kit check`; local/central mismatch
refused; resolution into `.git/`, `.claude/`, or outside the repository
refused. Gate: the reviewer's crafted zip refused by both; a clean zip
accepted.

**U3 Architect mode and doctor (§33; should-fix 2, 3, 4).** `cp`/`mv`
refuse symlink escapes and a symlinked `HANDS_KITS`; doctor resolves
paths and fails a role row when settings disable or redirect a hook,
printing what it verified. Gate: the reviewer's probes as tests.

**U4 Prompt and notifications (§33; should-fix 6, 7).** The next unmet
milestone is the first roadmap entry not marked DONE, pinned on a fixture
roadmap; daemon start publishes exactly once even with a queued job
starting in the same second. Gate: tests.

**U5 `reply` (§33).** `reply <secret> <text>` on `cmd_topic` → `hands send
--role architect --context keep` to the architect's last session, refused
when none exists or a consultation is running; the reply's text published
on `ntfy_topic` with title `architect`; `origin: phone`; the text stored
verbatim. The escalation notification carries the session id and the
`claude --resume <id>` line. Gate: tests with a mocked stream and
`fake_claude` as the architect: a round trip, the two refusals.

**U6 Self-hosted ntfy (§33).** `[notify] ntfy_token` sent as a bearer on
publish and on the command/who subscriptions; `docs/INTEGRATION.md`
describes running ntfy in a container with access control and reaching it
through the Tailscale tunnel, and moving the topics; `hands notify --test`
uses the token. Gate: tests with a mocked server that requires the
bearer.

**U7 This repository's playbook.** `[series] kickoff` becomes
BUILDER-18's line; nothing else. Gate: loads; a kit of this brief checked
with `--repo .` exits 0.

**U8 Final report.** `meta/FINAL-REPORT-17.md` (drafted under
`meta/drafts/`, moved in by this commit): what changed (sha per unit),
what tests prove, NOT PROVEN (mandatory: a real `reply` round trip, a real
self-hosted ntfy), the `## Review items` table for REVIEW-16 blockers 1–2
and should-fix 1–8. Then the verdict line.

## Acceptance

- `./scripts/check` green on the pushed tip, three consecutive runs.
- Every unit commit's body lists every file it touches; U0 is `plan:`.
- A kit that fails `hands kit check` is never engine-approved (test).
- `hands doctor` shows the ntfy token as on/off; `reply` documented.
- `meta/FINAL-REPORT-17.md` exists with NOT PROVEN and the review-items
  table.
