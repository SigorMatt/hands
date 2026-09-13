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

`[series]` holds two keys: `name`, the series' name, and `kickoff`, the
fixed kickoff line that `go` from the phone sends. A top-level
`series = "<name>"` still loads, but never beside a `[series]` table: TOML
refuses the key twice. `[limits] auto_runs` lists the runs (or missions) that may start
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

It needs no daemon, no config and no network. `--repo` defaults to the top
level of the git repository you run it in; a directory kit's files are
taken relative to the directory. It prints one line per check,
`PASS <name>: <reason>` or `FAIL <name>: <reason>`, in this order:

- `paths`: every entry is a repository path under the repo. That means
  relative, with no `..`, `.` or empty component, no NUL, no backslash and no
  drive letter. Nothing may sit under `.git` in any letter case (`.GIT`), no
  entry may be a symlink, no zip entry name may appear twice, and nothing may
  land outside the repo through one of the repo's own symlinks. No entry may
  be over 16 MiB and the kit not over 64 MiB, by the sizes the zip declares,
  read before any content is.
- `playbook`: the playbook in force is the kit's `PLAYBOOK.toml` or
  `meta/PLAYBOOK.toml`, else the repo's at the same paths. It is parsed by
  the engine's own loader, which refuses `quiet_hours`. The committed-copy
  comparison is skipped, because a kit is not committed yet. A kit's
  playbook must also set `[series] kickoff` to exactly the brief's kickoff
  line; the repo's kickoff is not compared.
- `brief`: the kit carries exactly one brief, `meta/BUILDER-<N>-PROMPT.md`
  (missions) or `WORKPLAN.md` (runs). Its kickoff line is the first
  indented line after "Kickoff line". Its final-reply vocabulary is every
  backticked literal in the paragraph after "Your final reply begins with"
  or "Reply with one of". The paragraph's lines are joined first, so a
  literal may wrap.
- `verdicts`: every `verdict` regex of the playbook is checked (DESIGN §27,
  finding H-021). Matching uses `re.search`, as the engine does. A rule on
  `builder.done` matches at least one literal of the brief, with
  placeholders such as `<unit>` left as text, and every literal matches some
  such rule. A builder rule that matches no literal of the brief passes only
  if it exists for the apply: its pattern is plain text (an optional `^`, no
  other regex syntax) found in `VERDICT: kit applied <sha>`, the reply the
  apply prompt below asks for, such as `^VERDICT: kit applied`. A pattern
  like `VERDICT: (kit applied|mission \d+ finished)` is not excused, because
  its other branch is never checked. A rule on `aux.done` matches at least
  one `VERDICT: review …` line of the review protocol, which is found in the
  send prompts and in the files they name. Each placeholder of that line
  (`N`, `<k>`, `<m>`, `{n}`) is read as a count and tried as 0, 1 and 12, so
  `blockers=0` and `blockers=[1-9]` both match, and `blockers=none` does not.
  A verdict rule on any other event fails: kit check has no vocabulary for
  it.
- `wording`: the brief contains neither "as before" nor a "Budget
  guidance" section (a heading or a bold lead).
- `protocol`: every file a `send` rule's prompt names is in the kit or inside
  the repo. A named file is a `.md` or `.toml` path without a
  `{placeholder}`, such as `meta/REVIEW-PROTOCOL.md`. A named path that is
  not a repository path (`../X.md`, `~/X.md`, `/X.md`) fails; it is not
  skipped.

When every check passes, it prints three things. First, the §3 apply
prompt, which names each file the kit replaces (the file exists in the
repo) and each file it adds. Second, the commit message: `plan: mission <N>
kit`, or `plan: kit <name>` when the kit has no mission brief. Third,
`kit check: pass (6 of 6 checks)`. A failing kit gets no apply prompt. The
exit status is 0 only when all six checks pass, and 1 otherwise. `--json`
prints the same report as one object.

## 12. Onboarding a project

1. Laptop: `~/.hands/<project>.toml`; a `handsd` instance; a driver
   directory with a fetch-only clone; the `.claude/settings.json` and
   `no_background` hook in the driven repo (`docs/INTEGRATION.md`).
2. Phone: subscribe to the project's topics; keep its command secret.
3. Project in the Claude app: paste `docs/ARCHITECT-INSTRUCTION.md` with
   the parameters filled in.
4. First kit: the playbook, the brief or plan, the review protocol;
   `hands kit check` green; treat the first series as a shakeout.
