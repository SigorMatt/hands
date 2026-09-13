# ARCHITECT HANDBOOK — writing kits that hands runs

For the architect of any project driven by hands. The Project instruction
(`docs/ARCHITECT-INSTRUCTION.md`) gives the rules; this handbook gives the
shapes. Read it once in full when onboarding a project; re-read §6 and §9
before every kit. `hands kit check` (§11) verifies what this handbook
describes.

## 1. What hands is, from where you sit

hands is a daemon on the human's laptop that runs the builder and the
reviewer as headless Claude Code sessions, one per prompt, and chains them
by a playbook you write. You never talk to the builder. You write files:
a mission brief (or a run kit), a playbook, decisions, design documents.
The human moves them to the laptop (or sends them from the phone), a gated
job applies them, a fixed kickoff line starts the work, and the playbook
takes it from there until a rule says stop. A stop reaches the human's
phone; the human comes to you; you read the branch and write the next kit.

Two things follow. First, everything you decide must be on disk, because
nothing else survives: the builder has no memory, hands has no opinions,
and your own context will be compacted. Second, the only interface between
your plan and the machinery is text that regexes can match: verdict lines,
kickoff lines, rule names. Get those exactly right and the rest is prose.

## 2. The loop

1. You read the branch (`git ls-remote`, shallow clone) and the review.
2. You emit a kit: a zip with files at their repository paths.
3. The human places it (`~/Downloads`) or sends it from the phone.
4. A gated `hands send` applies it: one plan-only commit, pushed. The
   human approves by phone button or through the driver.
5. The kickoff line starts the builder (`go` from the phone, or the
   driver).
6. The builder works unit by unit, commits and pushes each, ends with a
   `VERDICT:` line. The playbook chains the cold review. The reviewer
   commits one file and ends with its own `VERDICT:` line. The playbook
   stops with a message, or continues if you pre-planned the next step.
7. The phone buzzes. The human pastes the notification to you. Back to 1.

## 3. Kit anatomy

A kit is a zip whose entries are repository paths. Typical contents:

    DESIGN.md                       when the design changed (whole file)
    meta/BUILDER-N-PROMPT.md        the mission brief (missions form)
    WORKPLAN.md                     the series plan (runs form)
    PLAYBOOK.toml                   when rules or kickoff change (whole file)
    meta/REVIEW-PROTOCOL.md         when the review protocol changes
    decisions-YYYY-MM-DD.md         answers to memos, when any
    meta/BACKLOG.md, meta/ROADMAP.md   when they change

Rules: whole files, never patches; the same paths every time; nothing
executable; nothing the builder must "figure out". The apply prompt names
every file the kit touches and the commit message; `hands kit check` lists
them for you. A kit that changes `PLAYBOOK.toml` takes effect at the next
job start, and the daemon refuses a playbook that differs from the
committed copy, so the apply commit must include it.

The apply prompt (sent by the human or the driver, gated):

    Apply ~/Downloads/<kit>.zip to this repository: unzip -o into the repo
    root (it replaces A and B and adds C), then one plan-only sub-agent
    makes a single commit '<message>' listing those files in its body, and
    pushes. Change nothing else. Reply with one line: VERDICT: kit applied <sha>.

## 4. The two plan forms

**Missions** (agile-skills form; what hands is built with). The plan is a
brief, `meta/BUILDER-N-PROMPT.md`, with a fixed kickoff line that is also
the resume line:

    Read meta/BUILDER-N-PROMPT.md and execute the mission below its divider.

State lives in `meta/CHECKPOINT.md` (unit in progress), `meta/plan.md`
(units with checkboxes), `meta/journal.md`, `meta/findings/FINDINGS.md`
(the ledger), `meta/reviews/REVIEW-N.md`, `meta/FINAL-REPORT-N.md`. The
builder resumes from the checkpoint, so a limit or a termination costs
nothing but time. The template is `templates/BUILDER-N-PROMPT.md`.

**Runs** (spanweave form). The plan is `WORKPLAN.md` on the series
branch: §0 standing rules (sub-agent brief, cold review protocol, recovery
brief), §1 scope, §2 runs grouped from batches, §3–§5 batches, memos,
status. Kickoff `Execute WORKPLAN.md run N`; resume `Resume WORKPLAN.md`
(set `resume_line` in the project's hands config). Reviews are
`Review WORKPLAN.md commits since <base>`. The template playbook is
`templates/PLAYBOOK-runs.toml`.

Both forms need the same three things from you: a kickoff line that never
varies within a mission or run, a `VERDICT:` contract, and a playbook whose
regexes match it.

## 5. The VERDICT contract

Every builder brief and every review prompt requires the reply's first line
to begin with `VERDICT:` from a fixed vocabulary. hands stores that line as
`verdict`; the playbook matches it with `verdict = '<regex>'`. Write the
vocabulary and the regexes together, in the same sitting:

    brief:    VERDICT: mission 10 finished | VERDICT: mission 10 blocked <unit> | VERDICT: question <one line>
    playbook: '^VERDICT: mission (?P<n>\d+) finished'   → send the review
              '^VERDICT: mission (?P<n>\d+) blocked'    → stop
              '^VERDICT: question'                       → stop (or consult)

    review:   VERDICT: review mission N blockers=<k> should-fix=<m>
    playbook: '^VERDICT: review mission (?P<n>\d+) blockers=0'      → stop "reviewed clean" (or continue)
              '^VERDICT: review mission (?P<n>\d+) blockers=[1-9]'  → stop "has blockers"

A reply whose first line matches nothing hits the catch-all rule and stops
with "finished without a recognised verdict". Kit-apply jobs reply
`VERDICT: kit applied <sha>`; give them a `notify` rule so they don't stop.

Named groups (`(?P<n>\d+)`) become placeholders (`{n}`, `{n+1}`) in the
prompts your rules send.

## 6. Writing the playbook

Events: `builder.done`, `builder.failed`, `builder.limited` (handled by
hands itself; a rule is authorization only), `builder.orphaned`,
`aux.done`, `aux.failed`, `monitor.stall`, `monitor.tripwire`,
`monitor.task_killed`, `monitor.orphan_processes`, `job.held`, `job.denied`,
and after mission 11 `driver.done`.

Actions: `send` (role, context, prompt), `resume`, `notify` (message),
`stop` (message), and after mission 11 `consult`.

Rules are tried in order; the first match wins; an event with no matching
rule stops. So: specific verdict rules first, then a catch-all `stop` per
`*.done` event, then process rules (`orphaned`/`failed` → `resume`,
`task_killed`/`orphan_processes` → `stop`), then `job.held`/`job.denied` →
`notify`.

`[series] kickoff` names the fixed kickoff line; `go` from the phone sends
it. `[limits] auto_runs` lists the runs (or missions) that may start
without a human; anything not listed stops. `max_resumes` bounds automatic
resumes. Never `quiet_hours` (refused).

The review base: the review prompt tells the reviewer to find the last
`review:` commit itself (the protocol says how); never `{job.head_at_start}`,
which is wrong after a resume.

Continuing without a human: a rule on `aux.done` with `blockers=0` may
`send` the next kickoff (`run = "{n+1}"` checked against `auto_runs`), or,
in the PR shape (§9), a merge prompt and then the next kickoff.

## 7. The review protocol

A file the reviewer reads cold (`meta/REVIEW-PROTOCOL.md` or `WORKPLAN.md`
§0.2): find the base (last `review:` commit), one sub-agent per unit
commit in a worktree, prove tests go red on revert, run the gate at that
commit, check design conformance, write `## Blockers`, `## Should-fix`,
`## Notes`, `## Per-commit verdicts`, commit only the review file, reply
with the verdict line. Blockers are failed gates, missing tests, design
violations, or claims the disk contradicts; a claim that overreaches is a
blocker even when the code is right. Should-fix items wait for you.

## 8. Decisions files

Answers to memos, scope calls, corrections: `decisions-YYYY-MM-DD.md`
applied by a gated plan-only job like any kit. A decision that lives only
in chat does not exist; write it the same day.

## 9. PR per run, auto-merge on a clean review

For projects with a `main` worth protecting: each run branches from `main`,
the builder opens a PR at run end, the review runs on the branch, and on
`blockers=0` with green checks a playbook rule has the builder merge
(`gh pr merge --squash`) and, if listed, start the next run. The presence
of the merge rule in an approved playbook is the human's standing approval
of every merge it makes. Blockers, red checks, unrecognised verdicts stop.
`WORKPLAN.md` lives on the branch of the run in flight; branch protection
requires the checks.

## 10. What a stop means, and what to write next

| Stop reason | Read | Next kit |
|---|---|---|
| reviewed clean | the review's should-fix | next mission/run; carry should-fix into its U0 |
| has blockers | the review's blockers | a mission that closes them first |
| builder question | the job's `result` | usually a `keep` answer sent by the human/driver; a kit only if the plan changes |
| unrecognised verdict | the job's `result` and `stderr_tail` | fix the vocabulary or the brief |
| task_killed / orphan | the job record, the monitor event | a finding; rarely a kit |
| max_resumes exhausted | the job records | the environment, not the plan |

## 11. `hands kit check`

Run it before emitting any kit; from a fresh sandbox:

    uv tool install git+https://github.com/SigorMatt/hands
    hands kit check <kit.zip|dir> [--repo <clone>]

It checks: every entry is a repository path; the playbook loads and sets
no `quiet_hours`; every `verdict` regex in it matches at least one literal
line in the brief's final-reply vocabulary; the brief's kickoff line
equals `[series] kickoff`; the brief contains no "as before" and no budget
guidance; the review protocol is present when a rule sends a review. It
prints the apply prompt for the kit.

## 12. Onboarding a project

1. Laptop: `~/.hands/<project>.toml`; a `handsd` instance; a driver
   directory with a fetch-only clone; the `.claude/settings.json` and
   `no_background` hook in the driven repo (`docs/INTEGRATION.md`).
2. Phone: subscribe to the project's topics; keep its command secret.
3. Project in the Claude app: paste `docs/ARCHITECT-INSTRUCTION.md` with
   the parameters filled in.
4. First kit: the playbook, the brief or plan, the review protocol;
   `hands kit check` green; treat the first series as a shakeout.
