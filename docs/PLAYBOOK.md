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

---

## The file

    version = 1                  # required, must be 1
    series = "<name>"            # optional, free text

    [limits]
    auto_runs = [2, 3]           # run numbers hands may start on its own
    max_resumes = 3              # consecutive auto-resumes before a stop
    quiet_hours = "23:00-07:00"  # notifications delayed; actions never are

    [[rule]]
    on = "<event>"               # required
    verdict = '<regex>'          # optional; matched against the job's VERDICT: line
    then = "<action>"            # required
    role = "builder" | "aux"     # a send needs one
    context = "clear" | "keep"   # a send defaults to "clear"
    prompt = "<text>"            # a send needs one; placeholders allowed
    message = "<text>"           # a notify needs one; a stop may have one
    run = "{n+1}"                # a send only; see below

Unknown keys are refused, at the top level, in `[limits]` and in a `[[rule]]`.

## Events (`on`)

`builder.done`, `builder.failed`, `builder.limited`, `builder.orphaned`,
`aux.done`, `aux.failed`, `monitor.stall`, `monitor.tripwire`, `job.held`,
`job.denied`.

The list is closed: anything else is not a playbook event and fires nothing. A
job you cancelled yourself (`killed`) is not an event — you already know.

## Actions (`then`)

| `then` | what happens |
|---|---|
| `send` | one `hands send` with `role`, `context` and the rendered `prompt`. It goes through the same API `hands send` uses, so §8's gate patterns still apply to a job hands starts on its own |
| `resume` | the resumed job's own prompt again, or the role's `resume_line` from the config when it sets one, counted against `max_resumes` |
| `notify` | one ntfy message (`message`), nothing else |
| `stop` | pause the pipeline, notify, write the reason to the inbox |

Always a `stop`, whatever the rules say: an event with no matching rule, a
missing or unparseable `VERDICT:` line, an exhausted resume count, and any
failure inside the engine itself.

`hands resume`, or the next `hands send` you make yourself, un-pauses the
pipeline — whatever stopped it. The engine's own sends do not.

`hands pause` is a stop you make yourself: it files the same `stop` event
(reason `paused by human`) and the same notification, which is what wakes a
driver blocked on `hands wait --for stop,held`. Over a pipeline that is
*already* stopped it does nothing at all: it prints the reason it is already
stopped for, keeps that reason and its timestamp in `hands pipeline`, and files
no second event and no second notification.

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
resumes used per role against `max_resumes`, and the last rule that fired.

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
    quiet_hours = "23:00-07:00"   # notifications delayed, actions not

    [[rule]]                  # run finished cleanly → cold review
    on = "builder.done"
    verdict = '^VERDICT: run (?P<n>\d+) finished'
    then = "send"
    role = "aux"
    context = "clear"
    prompt = "Review WORKPLAN.md commits since {job.head_at_start}"

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

Read it as a sentence: a clean run starts a cold review; a clean review of a
pre-planned run starts the next run; blockers, memos, questions and tripwires
stop and call you; failures and orphans resume themselves until `max_resumes`.
A rate limit is not in the playbook at all: §6 owns that resume and schedules
it for the reset.
