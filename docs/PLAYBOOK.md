# The playbook — rule reference

`PLAYBOOK.toml` is the architect's plan for what needs no judgment (DESIGN
§10). hands executes it; anything outside it stops the pipeline and notifies
you. It lives in the project repo on the series branch, next to `WORKPLAN.md`
(agile-skills: `meta/PLAYBOOK.toml`), and `[playbook] path` in the config names
it relative to `roles.builder.cwd`.

It is applied like a decisions file: a **gated** `hands send` that you approve.
Approving that job is approving every launch the playbook may later make. hands
loads the tracked file from `roles.builder.cwd` when a job starts and records
its sha256 in every job it fires (`hands pipeline` shows it). Delete it at
series close with `WORKPLAN.md`.

No playbook is a legal state: hands runs the jobs you send and chains nothing.
A playbook that does not parse is not — the engine refuses to fire a rule out
of a half-read file, and `hands doctor` and `hands pipeline` both show the
error.

**The playbook must be committed.** When a job starts, hands compares the
file's bytes with `git show HEAD:./<playbook.path>` run in `roles.builder.cwd`
(DESIGN §10). A file edited after its commit is refused as **dirty**; a file
that is not in HEAD — never added, or `roles.builder.cwd` is not a git
repository — is refused as **untracked**. A refusal stops the pipeline like any
other stop: one `stop` event in the inbox and one notification, with a reason
that names both sha256s, for example

    the playbook is not the committed copy, so no rule can be trusted to fire:
    …/PLAYBOOK.toml is dirty: it differs from `git show HEAD:./PLAYBOOK.toml` in …:
    working sha256 <64 hex>, committed sha256 <64 hex>; commit it or restore the
    committed copy (§10)

(an untracked file says `committed sha256 none`, with git's own line). No rule
of a refused file fires. Commit the playbook — the gated `plan: playbook …`
job does — then `hands resume`. `hands doctor`'s playbook row is `ok` with
`committed` for the committed copy and fails with the same refusal otherwise.

---

## The file

    version = 1                  # required, must be 1
    series = "<name>"            # optional, free text; or the [series] table below

    [limits]
    auto_runs = [2, 3]           # run numbers hands may start on its own
    max_resumes = 3              # consecutive auto-resumes before a stop
    max_consults = 2             # driver consultations per mission (default 2)
    max_architect_consults = 12  # architect consultations per series (default 12)

    [[rule]]
    on = "<event>"               # required
    verdict = '<regex>'          # optional; matched against the job's VERDICT: line
    then = "<action>"            # required
    role = "builder" | "aux"     # a send needs one; a consult's is "driver"
                                 # (the default) or "architect"
    context = "clear" | "keep"   # a send defaults to "clear"; a consult is always "clear"
    prompt = "<text>"            # a send needs one; placeholders allowed
    message = "<text>"           # a notify needs one; a stop may have one
    run = "{n+1}"                # a send only; see below

Unknown keys are refused, at the top level, in `[series]`, in `[limits]` and in a
`[[rule]]`.

## The series and its kickoff (`[series]`)

    [series]
    name = "<name>"              # optional, free text
    kickoff = "<line>"           # optional; the line `go <secret>` sends
    architect = "phone"          # optional; "phone" (default) or "role" (§31)
    autonomous = false           # optional; default false
    gate_failures = 2            # optional; default 2
    escalate_on = ["blocker-unanswered", "milestone-missing", "budget-exhausted"]

`kickoff` is the series' fixed kickoff line (DESIGN §26). `go <secret>` on the
phone's `cmd_topic` sends exactly that line to the builder as a `clear` send,
and the job record says `origin: phone` (docs/INTEGRATION.md, the command
channel). The send goes through the same path as `hands send`, so the gate
patterns still apply. `go` is refused while the builder has a job running,
queued or held (DESIGN §27; the refusal names the job, and the builder is
checked again once the playbook is read), when there is no playbook (or it
cannot be loaded), and when the playbook has no `kickoff`.

The table's keys are `name`, `kickoff`, `architect`, `autonomous`,
`gate_failures` and `escalate_on`; the last four are §31's and are described
below. The series' name goes in the table as `name` when the table is used. TOML does
not allow `series = "<name>"` and a `[series]` table in the same file: the
parser refuses the second definition, so the playbook is refused as not valid
TOML. The top-level string still loads in a file with no table (the example
below uses it). This is hands' own choice where the design is silent (finding
H-019). Any other key in `[series]` is refused, naming it. An empty `name` or
`kickoff` (`""` or blanks only) is refused: leave the key out instead.

A `go` job or a kit's apply (`origin: kit`), like a `cli` send, un-pauses a
stopped pipeline when it starts, not when it is filed or held (DESIGN §27). A stopped pipeline still has its playbook, so `go` is accepted
while it is paused.

### The series' architect (DESIGN §31)

`architect = "phone" | "role"` (default `phone`) says which architect this
series has. The phone architect is the human's chat Project, which emits a kit
the human carries to the laptop; `role` is the headless architect handsd starts
itself (`[roles.architect]`, docs/INTEGRATION.md "The architect role"). A
playbook that sets `role` while the config has **no `[roles.architect]`** is a
config error, named when the engine loads the file and by `hands doctor`.

`autonomous` (default `false`) says the engine may release what that architect
files. With `architect = "role"` and `autonomous = true`:

- a **held** apply of `origin: architect` — the job `hands kit file` files — is
  approved by the engine (`decided_by: playbook`), whose gate reason names the
  approval it is acting on;
- `[series] kickoff` is sent to the builder when that apply replies `VERDICT:
  kit applied`.

Say it in the human's words before turning it on: **the human who approves an
`autonomous` playbook is approving every apply the architect files under it.**
The playbook is itself a gated apply, so that approval is a real one, made once.

`gate_failures` (default 2) is the number of times the same roadmap gate may
fail in a row before the architect escalates, and `escalate_on` is the closed
list of conditions it escalates on: `blocker-unanswered`, `milestone-missing`,
`budget-exhausted`. Both are carried in the architect's consult prompt, and the
first two are its judgement. hands enforces only the last: see `consult` below.

### The kickoff rule the engine adds (DESIGN §31)

Under `architect = "role"` with `autonomous = true`, the engine behaves as if a
rule

    [[rule]]
    on = "builder.done"
    verdict = '^VERDICT: kit applied'
    then = "send"
    role = "builder"
    context = "clear"
    prompt = "<[series] kickoff>"

stood at the top of the file. It is **not a rule anyone writes** — it is not in
the file, and writing it there changes nothing. It stands ahead of every rule in
the file because §10 fires the first rule that matches, and this is the one §31
promises will run; a playbook's own `^VERDICT: kit applied` rule (a `notify`, in
both templates) does not fire while autonomy is on, and the inbox records the
rule that did as `rule: -1`. The kickoff job's origin is `playbook`, like every
other job a rule starts, so it does not clear a stop. With `autonomous` set and
no `[series] kickoff` to send, the engine stops and says so.

## Events (`on`)

`builder.done`, `builder.failed`, `builder.limited`, `builder.orphaned`,
`aux.done`, `aux.failed`, `driver.done`, `driver.failed`, `driver.killed`,
`driver.orphaned`, `driver.limited`, `monitor.stall`, `monitor.tripwire`,
`monitor.task_killed`, `monitor.orphan_processes`, `job.held`, `job.denied`.

`driver.done`, `driver.failed`, `driver.killed`, `driver.orphaned` and
`driver.limited` (DESIGN §27, §28) are a consultation's driver job ending that
way. Every one of them but a resolved `driver.done` is a stop the engine
enforces; see `consult` below.

The list is closed: anything else is not a playbook event and fires nothing. A
job you cancelled yourself (`killed`) is not an event — you already know.

There is no `architect.*` event: `architect.done`, `architect.failed` and the
rest are how the engine names an architect consultation's end to itself, and
`architect.*` is not an event a rule can match — a rule naming one is refused
when the file is parsed. The engine reads the architect's verdict and follows
it (DESIGN §31, `consult` below), and a playbook neither can nor needs to.

`monitor.task_killed` (DESIGN §24) means a task inside a running role job — a
Bash command or a sub-agent — was killed before it finished. hands reads every
role job's stream-json, builder and aux, for the notice claude writes when that
happens and files one event per task, with its `task_id` and its command line
(`command`, taken from the `Bash` call that started it; empty when that call is
not in the stream). The stream does not say who killed the task: the harness
reaping it, the agent's own `TaskStop` and a killed parent agent look the same,
so the event's `cause` is always `unknown` (DESIGN §25). Work the job was
waiting on did not finish, so the rule is `stop`:

    [[rule]]
    on = "monitor.task_killed"
    then = "stop"

`monitor.orphan_processes` (DESIGN §24) means processes a role job started were
still alive after its `claude -p` exited. hands files one event per job, only
when there were any, listing each process's `pid`, command line and `killed`
(`processes`, each line cut to 1024 characters), and then kills those marked
`killed: true`. Where `systemd-run --user --scope` works, each job runs in its
own transient scope and the list is everything left in it, double forks
included. Elsewhere each job runs in its own process group, which is weaker: a
process is killed only when it is in the session the job led and started
before claude was last seen alive (DESIGN §29), so a process that called
`setsid` has left the group and is never killed; it is listed with `killed:
false` while it carries the job's `HANDS_JOB` mark. `hands doctor` says which
one is in force. Work the job left running did not finish with it, so the rule is
`stop` too:

    [[rule]]
    on = "monitor.orphan_processes"
    then = "stop"

An event with no matching rule stops anyway; each rule says it on purpose.
DESIGN §24 puts both in the example playbook, and this repository's own
`PLAYBOOK.toml` carries both.

`quiet_hours` is retired: a playbook whose `[limits]` sets it is refused at
load with a message saying so. Notifications are never delayed (§11).

## Actions (`then`)

| `then` | what happens |
|---|---|
| `send` | one `hands send` with `role`, `context` and the rendered `prompt`. It goes through the same API `hands send` uses, so §8's gate patterns still apply to a job hands starts on its own |
| `resume` | the resumed job's own prompt again, or the role's `resume_line` from the config when it sets one, counted against `max_resumes` |
| `notify` | one ntfy message (`message`), nothing else |
| `stop` | pause the pipeline, notify, write the reason to the inbox |
| `consult` | start a driver-role job whose prompt hands writes: the event, the job record and the role's last reply verbatim, with the question of DESIGN §27. See below |

Always a `stop`, whatever the rules say: an event with no matching rule, a
missing or unparseable `VERDICT:` line, an exhausted resume count, and any
failure inside the engine itself.

`hands resume` un-pauses the pipeline — whatever stopped it. So does a send you
make yourself, but only when that job **starts**: a send held at a gate or
waiting in the queue changes nothing, and a job the playbook or the limit
manager started never clears a stop. The `pipeline.resumed` event in the inbox
says which it was, `by = "resume"` or `by = "start"`.

Every stop, from any component — a rule, the engine itself, `hands pause`, an
exhausted `max_resumes` — goes through one `stop()`, and the first reason is the
one that is kept. A later stop over an existing one takes nothing: no change to
the reason or its timestamp, no second notification, and one
`pipeline.stop_suppressed` event in the inbox naming the reason it would have
set and the reason that was kept. That kind is in the `pipeline` namespace and
not in `stop`'s, so `hands wait --for stop,held` is not woken by a stop that was
deliberately not notified; `--for pipeline` waits for them. One exception
(DESIGN §29): a consultation that does not end resolved (see Consult) over a
paused pipeline is filed the same way, as `pipeline.stop_suppressed` carrying
the consult reason, and it also notifies, once, with `hands: a consultation
stopped over a paused pipeline`; no playbook rule fires for it.

`hands pause` is a stop you make yourself: it files the same `stop` event
(reason `paused by human`) and the same notification, which is what a
`hands wait --for stop,held` is woken by and what `hands doctor`'s
notification check (§11) uses to put an event on your phone. Over a pipeline that is
*already* stopped it is that later stop: it prints the reason it is already
stopped for, keeps that reason and its timestamp in `hands pipeline`, notifies
nobody, and leaves only the `pipeline.stop_suppressed` record.

## Consult (`then = "consult"`, DESIGN §27, §31)

A consult asks a role instead of stopping. There are two: the **driver**
(DESIGN §27), asked to resolve one event within its authority, and the
**architect** (DESIGN §31), asked on a review outcome to write the next kit.
Which one a rule asks is the rule's `role`: `role = "driver"` when the key is
absent, or `role = "architect"`. Either needs its own table in the config —
`[roles.driver]` or `[roles.architect]` (docs/INTEGRATION.md) — and a consult
naming a role this project does not configure is a stop, not a job.

The rule takes no `prompt` and no `run`, and `context`, when given, is `clear`:
every consultation is a fresh session with no memory of the last. Which events
a role may be consulted on is checked when the file is parsed: the driver on any
event but its own ends (a consult on `driver.done` or `driver.failed` is
refused), and the architect on `aux.done` only — the review outcome §31 names,
because its prompt is written out of a review.

### The driver's consultation (DESIGN §27)

When it fires, handsd starts a driver job with `origin: playbook`. It does not
go through `hands send`, which refuses the driver role, and it is not gated.
The prompt's first line names the event, the job and its role. It carries the job's id, role, state and verdict, the job's `result` verbatim,
the question "resolve within your authority, citing the mission file or DESIGN
section, or escalate", the one send the driver may make (`hands send --role
<role> --context keep` to the role the consultation is about), and the two
first lines its reply may begin with:

    VERDICT: resolved <what was sent, and the section cited>
    VERDICT: escalate <reason>

Always a `stop` instead, and no driver job: no `[roles.driver]` in the config
(checked when the rule fires, because the playbook does not see the config), an
event that carries no job, and a mission that has used `[limits]
max_consults` (default 2). The stop reason names `max_consults`. The mission is
counted from the later of two jobs (DESIGN §28): the last builder job whose
prompt equals any `[series] kickoff` value the pipeline has loaded, not a
resume of it, and the last kit apply that ran (a builder job of `origin: kit`
that started). Every kickoff value a loaded playbook carried is kept in the
spool's `pipeline.json`, so renaming the next kickoff does not freeze the count.
Every driver job after that start counts, except a §6 resume of one. A driver
job created before the daemon start `pipeline.json` keeps does not count either
(§29): the start is the latest of the kickoff, the kit apply and that daemon
start. The first daemon start that finds none recorded is kept as
`consults_since`, and a restart does not move it, so a restart mid-mission keeps
the count (§30). With none of them, every driver job in the spool counts.

The driver job's environment carries `HANDS_CONSULT_ROLE`, the role named on
the prompt's first line; the guard in role mode allows a send to that role only.
It also carries `HANDS_CLONE`, the driver's clone (`<cwd>/repo`, or the cwd when
that is the repository; absent with neither), and the guard in role mode allows
`git -C` on that path only (DESIGN §29).

Every consultation files `consult.sent` in the inbox when the driver job is
created and `consult.done` when it ends, with its terminal state and verdict
line: `done`, `failed`, `killed` (a cancel, or a job the runner could not
spawn), `orphaned` (its daemon died) or `limited`. A limited driver job is not
resumed: the consultation has ended. At the end, handsd also
appends one line to `meta/journal.md` under `roles.builder.cwd`, creating the
file and `meta/` when they are absent. The line is written to the working tree
and never committed by hands. The driver's reply is its job's `result`, stored
verbatim like every job's.

The stops are the engine's (DESIGN §28). A consultation that does not end in a
`driver.done` whose verdict begins `VERDICT: resolved ` stops and notifies:
`VERDICT: escalate <reason>` (the reason is in the stop), an unrecognised or
missing verdict, `driver.failed`, `driver.killed`, `driver.orphaned` and
`driver.limited`. A playbook needs no rule for any of them and cannot remove
one: when the first matching rule for such an event is itself a `stop`, that
rule is the stop and its message the reason; any other matching rule (a
`notify`, a `send`) does not fire, and the stop records it as `rule_not_fired`.

A resolved verdict goes to ordinary rules. §10 has no do-nothing action, so the
rule for `resolved` is a `notify`: the driver already sent its answer, and the
phone hears what it did. With no rule for it, a resolved verdict stops too
(§10). The escalate and `driver.failed` rules below only give the stops their
messages:

    [limits]
    max_consults = 2

    [[rule]]                  # a builder question → the driver
    on = "builder.done"
    verdict = '^VERDICT: question'
    then = "consult"

    [[rule]]                  # the driver answered with a keep send → nothing more
    on = "driver.done"
    verdict = '^VERDICT: resolved (?P<what>.+)'
    then = "notify"
    message = "Consult resolved: {what}"

    [[rule]]                  # the driver cannot decide → you
    on = "driver.done"
    verdict = '^VERDICT: escalate (?P<reason>.+)'
    then = "stop"
    message = "The driver escalated: {reason}"

    [[rule]]
    on = "driver.failed"
    then = "stop"

`hands kit check` checks a `verdict` rule on `driver.done` against those two
lines, placeholders left as text.

### The architect's consultation (DESIGN §31)

    [[rule]]                  # the review outcome → the architect
    on = "aux.done"
    verdict = '^VERDICT: review mission (?P<n>\d+) blockers='
    then = "consult"
    role = "architect"

handsd starts an architect job in the architect's directory, `context: clear`,
`origin: playbook`, exactly as it starts a driver one, and files `consult.sent`
and `consult.done` the same way. The prompt hands writes has four parts: the
event and the job record; the review's `VERDICT:` line and its `## Blockers` and
`## Should-fix` sections verbatim (the whole reply when a heading is missing);
`meta/ROADMAP.md` from the builder's cwd, verbatim; and the series' escalation
conditions (`gate_failures`, `escalate_on`, and which consultation of the budget
this is). Then the instruction — "write the next kit from ROADMAP and the
review, file it, or escalate" — and the three lines the reply may begin with:

    VERDICT: next kit <name>
    VERDICT: series complete
    VERDICT: escalate <reason>

The engine reads that verdict itself; no rule matches it, because `architect.*`
is not an event. `VERDICT: next kit <name>` waits for the apply the architect
filed with `hands kit file` during the consultation, and stops when it filed
none. `VERDICT: series complete` stops with that reason. `VERDICT: escalate
<reason>` stops and notifies with the reason, the architect's session id and the
`claude --resume <id>` line. An unrecognised or missing verdict, and an
architect job that ends `failed`, `killed`, `orphaned` or `limited`, stop too.

The budget is `max_architect_consults` (default 12) in `[limits]`, counted
**per series** — from the anchor written when the playbook loaded, not per mission as
the driver's `max_consults` is. When it is spent the engine stops by itself,
naming `budget-exhausted`, which is why that one condition of `escalate_on` is
hands' and the other two are the architect's judgement. `hands pipeline` prints
`architect <used> of max_architect_consults <n>` while the series is in role
mode.

## Verdict matching

`verdict` is a Python regex, searched against the job's `verdict` field — the
first line of `result` matching `^VERDICT:`. Rules for an event are read top to
bottom and the first match wins; a rule with no `verdict` matches any job for
that event, so it belongs last.

Every run prompt and review prompt must therefore *require* a first-line
`VERDICT:` in the vocabulary the playbook matches. The architect writes both,
so they agree by construction.

## Placeholders

In `prompt` and `message`:

- `{name}` — a named group of that rule's `verdict` regex.
- `{name+1}` — the same group as an integer, plus a literal. Integer
  arithmetic only.
- `{job.id}`, `{job.head_at_start}`, `{job.head_at_end}`, `{job.session_id}`.

A placeholder that names no group of the rule's own regex, and a `{job.…}`
field outside that list of four, are refused when the file is parsed — never
when the rule fires.

### The review base (DESIGN §23)

A cold review reads every commit after the last `review:` commit on the
branch. The reviewer computes that base itself, from disk:
`git log --oneline --grep='^review: ' -1`, or the mission's kit commit if no
review exists yet. hands does not compute it, and the review prompt names no
commit: §10's example says "commits since the last review: commit on the
branch", and the protocol the prompt points at says how to find it.

`{job.head_at_start}` is the wrong review base. It is where the job that
finished started, and that job may have resumed a mission mid-way — a limit
resume, a `builder.failed` → `resume`, a human re-kick — so it is the start of
that last job, not of the mission. Review 6 is the real case: its prompt's base
was itself a unit commit of the mission, and five of the mission's unit commits
fell outside the range and went unreviewed per commit.

`{job.head_at_start}` is right when you mean exactly the job that finished: a
per-job diff (`{job.head_at_start}..{job.head_at_end}`), a note naming where
that job began, a check of what that one job committed.

## `run = "<expr>"`

On a `send` only. It names, explicitly, the run number that send would start,
and hands refuses to launch unless that number is listed in `[limits]
auto_runs` — it stops instead. This is the decision you took at plan time: the
launches hands may make without you. hands does not parse `WORKPLAN.md` — the
architect lists the pre-planned runs because it knows them.

`<expr>` is the placeholder grammar above, narrowed to one named group of the
rule's own `verdict` regex, with optional integer arithmetic: `"{n}"` or
`"{n+1}"`. Nothing else is a run — not a literal (`"4"`), not a `{job.…}`
field, not two placeholders, not prose.

Refused when the file is parsed, never when the rule fires:

- `run` on a rule that is not a `send`;
- `run` with no `[limits] auto_runs`, or an empty one — there would be no run
  hands could ever start;
- `run` whose expression names a group the rule's `verdict` does not define,
  including a rule that carries no `verdict` at all;
- `run` that is not an expression of that grammar.

`only_if_run_in`, the older spelling, is refused outright with a message naming
`run`: a playbook written against it fails loudly rather than silently losing
its check.

## Counters

`hands pipeline` reports the file (path, sha256, series, rule count), whether
the pipeline is paused and why, the stop reason, `auto_runs` used/allowed,
resumes used per role against `max_resumes`, driver consultations used against
`max_consults`, architect consultations of this series against
`max_architect_consults` (only while `[series] architect = "role"`), and the
last rule that fired. The
last rule is cleared when a playbook with a different sha256 is loaded: rule 3
of the file that fired is not rule 3 of the new one.

---

## The example (DESIGN §10, verbatim)

A spanweave audit-fix series. This is byte-for-byte the example in DESIGN §10;
`tests/fixtures/playbook_example.toml` holds it and a test parses it, so it is
known to load.

    version = 1
    series = "audit-fixes"

    [limits]
    auto_runs = [2, 3]        # runs hands may start on its own; anything else stops
    max_resumes = 3           # consecutive auto-resumes before stop
    # no quiet_hours: notifications are never delayed (decision 2026-09-12)

    [[rule]]                  # run finished cleanly → cold review
    on = "builder.done"
    verdict = '^VERDICT: run (?P<n>\d+) finished'
    then = "send"
    role = "aux"
    context = "clear"
    prompt = "Review WORKPLAN.md commits since the last review: commit on the branch"

    [[rule]]                  # review clean and next run pre-planned → go
    on = "aux.done"
    verdict = '^VERDICT: review run (?P<n>\d+) blockers=0'
    then = "send"
    role = "builder"
    context = "clear"
    prompt = "Execute WORKPLAN.md run {n+1}"
    run = "{n+1}"                  # must be listed in auto_runs, else stop

    [[rule]]                  # blockers → you
    on = "aux.done"
    verdict = '^VERDICT: review run (?P<n>\d+) blockers=[1-9]'
    then = "stop"
    message = "Review of run {n} has blockers"

    [[rule]]                  # memos and questions → you
    on = "builder.done"
    verdict = '^VERDICT: (awaiting decision|question)'
    then = "stop"

    [[rule]]                  # limits are §6's; nothing to say here
    on = "builder.orphaned"
    then = "resume"

    [[rule]]
    on = "builder.failed"
    then = "resume"

    [[rule]]
    on = "monitor.tripwire"
    then = "stop"

    [[rule]]
    on = "monitor.task_killed"
    then = "stop"

    [[rule]]
    on = "monitor.orphan_processes"
    then = "stop"

Read it as a sentence: a clean run starts a cold review; a clean review of a
pre-planned run starts the next run; blockers, memos, questions, tripwires,
killed tasks and orphan processes stop and call you; failures and orphans resume themselves until `max_resumes`.
A rate limit is not in the playbook at all: §6 owns that resume and schedules
it for the reset.
