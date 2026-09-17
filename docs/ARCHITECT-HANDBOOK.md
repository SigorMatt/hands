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
4. A held builder job applies it: one plan-only commit, pushed. For a kit
   sent from the phone, handsd files that job itself; for a kit placed by
   hand, a gated `hands send` does. The human approves by phone button or
   through the driver.
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

The apply prompt:

    Apply ~/Downloads/<kit>.zip to this repository: unzip -o into the repo
    root (it replaces A and B and adds C), then one plan-only sub-agent
    makes a single commit '<message>' listing those files in its body, and
    pushes. Change nothing else. Reply with one line: VERDICT: kit applied <sha>.

The kit's file name and the message are shell-quoted (`shlex.quote`): a name
such as `a b.zip` is written `~/Downloads/'a b.zip'`; `m-12.zip` is unchanged.

The commit message is the first line of `KIT.md` at the kit's root, else
`plan: kit <name>`, the zip's file name without `.zip`; put the message you
want on `KIT.md`'s first line, in at most 72 characters with no quote
character. A line that breaks those rules, or is empty, gives the default, and
handsd tells the phone why. When the kit is sent from the phone
(`kit <secret>`), handsd files it as a held builder job (`origin: kit`, gate
reason `apply <name>`) with exactly this prompt, built by the same code as
`hands kit check`'s, and never unzips the kit itself; a kit with an entry that
is not a repository path is refused (`kit.refused`) and files no job. A kit
placed by hand is applied by a gated send of the same prompt. The architect
role (§12) stages the same entries as a directory and files it with `hands kit
file kits/<name>`, which builds the zip.

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
and since mission 11 `driver.done` and `driver.failed`.

Actions: `send` (role, context, prompt), `resume`, `notify` (message),
`stop` (message), and since mission 11 `consult` (`[limits] max_consults`,
default 2; docs/PLAYBOOK.md "Consult").

Rules are tried in order; the first match wins; an event with no matching
rule stops. So: specific verdict rules first, then a catch-all `stop` per
`*.done` event, then process rules (`orphaned`/`failed` → `resume`,
`orphan_processes` → `stop`, `task_killed` → `notify`, since a job that ends
`failed` is what stops), then `job.held`/`job.denied` →
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

It needs no daemon and no network, and no config unless the kit's playbook
sets `[series] architect = "role"`: that one is judged against the project's
config as `handsd` judges it at load, and fails where no config can be judged
(none, several and no `--project`, or one that is not valid TOML), so check a
role-mode kit where the project's config is (DESIGN §33). `--repo` defaults to the top
level of the git repository you run it in; a directory kit's files are
taken relative to the directory. It prints one line per check,
`PASS <name>: <reason>` or `FAIL <name>: <reason>`, in this order:

- `paths`: every entry is a repository path under the repo. That means
  relative, with no `..`, `.` or empty component, no NUL, no backslash and no
  drive letter. Nothing may sit under `.git` or `.claude`, at any depth and in
  any letter case (`.GIT`, `.Claude`): a kit does not write git's hooks or
  Claude Code's settings and hooks in the repository; no entry may be a symlink, no zip entry name may
  appear twice, and nothing may land outside the repo, or inside `.git` or
  `.claude`, through one of the repo's own symlinks. A zip entry is judged by
  its central-directory name, the one `unzip` extracts: an entry whose
  local-header name or Unicode Path extra field names another file, or whose
  non-ASCII name is not marked UTF-8, is refused (DESIGN §33). handsd judges a
  kit from the phone or from `hands kit file` by the same rules. No entry may
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
  `builder.done` matches at least one literal of the brief, with placeholders
  such as `<unit>` left as text, and every literal matches some such rule. The
  apply-verdict exception (DESIGN §29): exactly one builder.done rule may match
  the literal 'VERDICT: kit applied <sha>' and nothing in the vocabulary. That
  literal is the reply the apply prompt below asks for. So `^VERDICT: kit
  applied`, `VERDICT: kit applied .*`, `(?i)^verdict: kit applied` and
  `^VERDICT: kit` each pass as that one rule when no brief literal matches
  them. A second rule matching the literal and no brief literal fails, and so
  does `VERDICT: (kit applied|misison \d+ finished)`, whose `misison` branch
  does not match the literal. A rule that matches a brief literal, such as a
  catch-all `^VERDICT:` after the apply rule, is judged by the vocabulary even
  though it matches the literal too, and is not that one rule. Every other
  rule must match a vocabulary literal, and so must
  each alternative of its alternations: `(blockers=0|blokers=0)` fails on
  `blokers=0`, although its other branch matches. A rule on `aux.done` matches
  at least one `VERDICT: review …` line of the review protocol, which is found
  in the send prompts and in the files they name. Each placeholder of that
  line (`N`, `<k>`, `<m>`, `{n}`) is read as a count and tried as 0, 1 and 12,
  so `blockers=0` and `blockers=[1-9]` both match, and `blockers=none` does
  not. A rule on `driver.done` matches at least one of the driver's two lines,
  `VERDICT: resolved <what was sent, and the section cited>` and `VERDICT:
  escalate <reason>`, placeholders left as text. A verdict rule on any other
  event fails: kit check has no vocabulary for it.
- `wording`: the brief contains neither "as before" nor a "Budget
  guidance" section (a heading or a bold lead).
- `protocol`: every file path a `send` rule's prompt names is in the kit, or
  else inside the repo, whatever punctuation surrounds it and bare names
  included (DESIGN §28, §29, §30; `tests/fixtures/named_path_shapes.tsv`
  enumerates the shapes). DESIGN does not say what tells a bare name from an
  English word, so kit check splits the prompt at every character that is not
  a letter, a digit or one of `_ . / ~ { } + - : #` (whitespace, ASCII and
  Unicode quotes, brackets, `,` `;` `!` `?` `*` `|` `=` `@` `&` `…`), drops a
  `#anchor`, a trailing `.`, `:` or `/` and a `:line` or `:line:col`, and reads
  a word as a file path when it is a file the kit or the repo has, or, not
  being a directory there, when its last component has an extension holding a
  letter (`meta/X.c`, `WORKPLAN.md`), or when it holds a `/` and its first
  component is a directory of the kit or the repo (`meta/MISSING`) or it is
  not a repository path by the rules handsd applies to a kit's entries
  (`../X.md`, `~/X.md`, `/etc/passwd`, `./scripts/check`, `../{n}.md`), or
  when its last component before any `.` is a caps name (three or more
  capitals and `_`: `NOTES`, `MISSING.1`; `VERDICT` excepted) or a build-file
  name (`Makefile`, `Dockerfile`); those fail when missing, they are not
  skipped. What it cannot see: a missing lower-case name with no extension
  (`notes`, `newdir/notes`) reads as prose, like `origin/main`, and so does a
  word with a `:` left inside it (a URL). A word like `e.g.`, `github.com`,
  `API` or `Profile` is read as a path and fails, so rephrase it. A path with
  a `{placeholder}`, such as `meta/reviews/REVIEW-{n}.md`, names a different
  file per job, so only its syntax is checked.

When every check passes, it prints three things. First, the §3 apply prompt,
which names each file the kit replaces (the file exists in the repo) and each
file it adds. Second, the commit message: the first line of `KIT.md` at the
kit's root when that line is not empty, at most 72 characters, and has no
quote character or line break, else `plan: kit <name>` (the kit's file name
without `.zip`), and a `KIT.md:` line saying that shape and what this kit's
`KIT.md` gives, or why its line is not used. The prompt shell-quotes the
message. The prompt names the kit `~/Downloads/<kit>.zip`, where handsd writes
it with the default `kit_dir`; with another `kit_dir` handsd's prompt differs
in that location. Third, `kit check: pass (6 of 6 checks)`. A failing kit gets
no apply prompt. The exit status is 0 only when all six checks pass, and 1
otherwise. `--json` prints the same report as one object.

## 12. Onboarding a project

1. Laptop: `~/.hands/<project>.toml`; a `handsd` instance; a driver
   directory with a fetch-only clone; the `.claude/settings.json` and
   `no_background` hook in the driven repo (`docs/INTEGRATION.md`).
2. Phone: subscribe to the project's topics; keep its command secret.
3. Project in the Claude app: paste `docs/ARCHITECT-INSTRUCTION.md` with
   the parameters filled in.
4. First kit: the playbook, the brief or plan, the review protocol;
   `hands kit check` green; treat the first series as a shakeout.

### Running as the architect role (DESIGN §31)

One more step turns the phone architect — you, in this Project — into a role
handsd starts for itself: the human builds `~/hands-architect/<project>/` and
applies a playbook with `[series] architect = "role"`. `architect/README.md` is
that procedure, and `architect/CLAUDE.md` is the instruction the role runs
under; read it there rather than here. What changes for you:

- **One consultation, no memory.** handsd starts you on a review outcome
  (`aux.done`) with the review's `VERDICT:` line, its `## Blockers` and
  `## Should-fix` sections, the next unmet milestone of `meta/ROADMAP.md` (the
  first whose first line is not marked `DONE`) and the series' escalation
  conditions in the prompt. Everything else you read yourself, from
  `origin/<branch>` in `./repo`. Nothing carries over from the last one.
- **The kit is a directory in `kits/`, not a zip for the human.** `$HANDS_KITS`
  (`./kits`) is the only directory you may write to. Stage the kit as
  `kits/<name>/<repository paths>` — the entries of §3, each at its repository
  path under `kits/<name>/` — writing the files with the Write tool and
  arranging them with `mkdir -p`, `cp -r` and `mv`; there is no `zip` or `unzip`
  in your guard. `cp` and `mv` are refused while anything under `kits/` is a
  symlink, and every write is refused if `kits` itself is one (DESIGN §33); you
  cannot make one, so if the refusal names one, escalate. Then `hands kit check kits/<name> --repo ./repo`, and `hands kit
  file kits/<name>`, which builds the zip itself (`kits/<name>/meta/X.md` is the
  entry `meta/X.md`), runs the check again on that zip against the clone,
  refuses a failing kit with the check's output, and otherwise has handsd file
  the same held apply the phone's `kit` files, `origin: architect`, with a
  `kit_id` handsd mints. handsd keeps the zip at
  `~/.hands/<project>/kits/<kit_id>/<name>.zip`, and the apply prompt names it
  there, with what it replaces and adds judged against the builder's repository
  (`kit check`'s prompt names `~/Downloads/<name>.zip` and judges the clone). A symlink inside the directory refuses the kit; an empty
  directory carries nothing. handsd runs the check once more on the zip it
  stores, against the builder's repository, and refuses a failing kit with the
  check's output (DESIGN §33). Under `[series] autonomous` the engine approves
  that hold itself once your reply names it, and sends the kickoff, so a kit you
  file is a kit that runs.
- **One kit per consultation, under the name your verdict gives.** File at most
  one kit, and reply `VERDICT: next kit <name>` with exactly its name. A second
  kit, or a kit whose name your verdict does not state, is denied by the engine
  and your consultation ends `escalate` (DESIGN §33).
- **One verdict line, and it is read by the engine, not by a rule.** Reply with
  exactly one of `VERDICT: next kit <name>`, `VERDICT: series complete` or
  `VERDICT: escalate <reason>`. File the kit *before* you reply `next kit`:
  hands waits for the apply of the kit you name — filed during this
  consultation — for up to `[series] kit_wait_s` (default 600), and stops if
  none is filed.
- **When to escalate.** The conditions are written into the playbook:
  `gate_failures` (the same roadmap gate failing that many times in a row),
  `blocker-unanswered`, `milestone-missing`, and `budget-exhausted` — the
  series' `[limits] max_architect_consults` (default 12), which handsd counts
  and stops on by itself. A decision that would change the shape the human
  approved at the switch point is also an escalation. Escalating notifies the
  human with your session id and a `claude --resume` line.
- **You still write nothing but kits.** No product code, no repository edit, no
  `hands send`, `approve`, `deny`, `go` or `put`, no push: the guard refuses
  them in architect mode, and needing one is itself an escalation.

**Directory kits (H-030, resolved by DESIGN v3.15 §32).** Under §31 the role's
`zip` could store entries only under `kits/…`, which `hands kit check` saw as
valid repository paths. `zip` and `unzip` have left the guard, and `hands kit
file` builds the zip from the directory, so the entries are the paths you staged
under `kits/<name>/`. What is not proven is a real role session filing a kit that
a builder then applies; the tests drive the command and handsd with a fake
`claude`. A role-mode series is still an experiment: check what the apply prompt
says a kit would add before letting it run unattended.
