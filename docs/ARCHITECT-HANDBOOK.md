# ARCHITECT HANDBOOK — writing kits that hands runs

For the architect of any project driven by hands. The Project instruction
(`docs/ARCHITECT-INSTRUCTION.md`) gives the rules; this handbook gives the
shapes. Read it once in full when onboarding a project; re-read §6 (the
playbook) and §9 (the pull-request flow) before every kit. `hands kit check` (§11) verifies what this handbook
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

A **decisions kit** carries a ruling the builder needs in the middle of a
mission (DESIGN §42): a zip holding only the owner file
`meta/decisions/<date>-owner.md` (or several, each
`meta/decisions/<name>-owner.md` with `<name>` one path component) and a
`KIT.md` whose first line is `plan: decisions <date> (owner)`, so the apply
commits under the message the brief's §R looks for. It has no brief and no
playbook; directory entries, as a recursive zip writes them, are allowed.
The human sends it like any kit (`kit <secret>` with the zip, or `hands kit
apply <zip>` at the laptop), approves the apply, then `go <secret>`. The architect
role does not file one: `hands kit file` refuses it, because an owner file
is the human's word.

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
A ruling in the middle of a mission arrives as a decisions kit (§3): its
apply commits `plan: decisions <date> (owner)`, and the template's §R tells
the resumed builder to carry out that owner file's "For the builder" steps
first when the checkpoint does not record them as done, record them, and
continue. hands names the owner file itself as well (DESIGN §43): every
builder job but an apply is dispatched with one sentence before its prompt
naming each owner file committed with no update of `meta/CHECKPOINT.md`
since, oldest first, until the builder commits the checkpoint after it — so
a decisions kit and `go` works whatever brief the mission runs from, one
written before §R gained its sentence among them.

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

`[series]` holds seven keys, every one optional; any other key is refused,
naming it (docs/PLAYBOOK.md "The series and its kickoff" is the reference).
The list below is every key `hands.playbook` accepts, each with the default
its loader gives a playbook that leaves the key out; a test holds the two
together (HF-004):

- `name` (no default): the series' name, free text. In role mode it is what
  the architect's budget counts for; renaming it is refused unless `[limits]`
  restates `max_architect_consults`.
- `kickoff` (no default): the fixed kickoff line that `go` from the phone
  sends, and that the engine sends after an approved apply in autonomous
  role mode. Without it, `go` is refused.
- `architect` (default `phone`): `phone` is you in the chat Project, emitting
  kits the human carries; `role` is the headless architect handsd starts on a
  review outcome (`[roles.architect]` must exist, or it is a config error).
- `autonomous` (default `false`): with `architect = "role"`, the engine itself
  approves the apply of the kit the architect role filed (`decided_by:
  playbook`) and then sends `kickoff`. Approving such a playbook is approving
  every apply it makes.
- `gate_failures` (default 2): how many times in a row one roadmap gate may
  fail before the architect escalates; a positive integer, stated in the
  architect's prompt and judged by the architect.
- `escalate_on` (default none): the escalation conditions, a list from
  `blocker-unanswered`, `milestone-missing` and `budget-exhausted`; any other
  name is refused. The engine stops on `budget-exhausted` itself; the other
  two are the architect's judgement.
- `kit_wait_s` (default 600): the seconds `VERDICT: next kit <name>` waits
  for the architect's kit to be filed before the pipeline stops, naming the
  key; a positive number.

A top-level `series = "<name>"` still loads, but never beside a `[series]`
table: TOML refuses the key twice. An empty `name` or `kickoff` is refused:
leave the key out instead. `[limits] auto_runs` lists the runs (or missions) that may start
without a human; anything not listed stops. `max_resumes` bounds automatic
resumes. Never `quiet_hours` (refused).

The review base: the review prompt tells the reviewer that the protocol
finds the mission's commits itself — its pull request, or `main` since the
last `review:` commit (the protocol says how; §9); never
`{job.head_at_start}`, which is wrong after a resume.

Continuing without a human: a rule on `aux.done` with `blockers=0` may
`send` the next kickoff (`run = "{n+1}"` checked against `auto_runs`). In
the pull-request shape (§9) the review has already merged the PR by then, so
the next kickoff starts from a `main` that has the mission's code.

## 7. The review protocol

A file the reviewer reads cold (`meta/REVIEW-PROTOCOL.md` or `WORKPLAN.md`
§0.2): find the commits (the mission's pull request, or `main` since the
last `review:` commit; §9), read the hosted review when there is a PR, one
sub-agent per unit commit in a worktree, prove tests go red on revert, run
the gate at that commit, check design conformance, write `## Blockers`,
`## Should-fix`, `## Notes`, `## Per-commit verdicts` (and
`## Hosted review` with a PR), commit only the review file, merge a clean PR (§9),
reply with the verdict line. Blockers are failed gates, missing tests, design
violations, or claims the disk contradicts; a claim that overreaches is a
blocker even when the code is right. Should-fix items wait for you.

Three rules of the protocol carry other projects' reviews (DESIGN §40). The
reviewer starts with `git worktree prune`, removes each stale review
worktree an earlier, aborted review left under `/tmp`, and ends by removing
its own (DESIGN §41). A worktree is stale when it is registered under the
clone and its path no longer exists, or when it is a review worktree under
`/tmp` that is not this review's and is older than the current aux job's
start; a worktree of a review running concurrently, or one a human made, is
never stale. Not every commit is a unit: `plan:` (read for what it says),
`meta:`, `journal:` and `report:` (read for forbidden edits only, never
reviewed as a unit), `review:` and merge commits get no sub-agent, and a
human-supplied commit is checked by `git show --stat` alone (§17). And
each per-commit sub-agent is told to run `./scripts/check` once, in the
foreground, and report only when every command has finished.

## 8. Decisions files

Answers to memos, scope calls, corrections: `decisions-YYYY-MM-DD.md`
applied by a gated plan-only job like any kit. A decision that lives only
in chat does not exist; write it the same day.

## 9. A pull request per mission; the review merges a clean one (DESIGN §35)

The branch logic lives in the brief and the review protocol, not in the
engine: the playbook still reads one `VERDICT:` line and fires one rule.
`templates/BUILDER-N-PROMPT.md` and `templates/REVIEW-PROTOCOL.md` carry
both shapes below; keep the one the mission uses.

**The builder.** The mission runs on a branch `mission-N`, created from
`main` at U0 (a closer mission instead continues the open branch its brief
names, merging `main` in first so the kit's plan files are there). Every
unit commit goes to that branch and is pushed at once. The last unit opens
the pull request — `gh pr create --base main --head mission-N --title
"mission N: <title>" --body-file meta/FINAL-REPORT-N.md` — and the final
reply carries its number: `VERDICT: mission N finished pr=<number>`. The
playbook's `'^VERDICT: mission (?P<n>\d+) finished'` matches that line by
prefix, and `hands kit check` accepts the `pr=<number>` placeholder. The
builder then returns the tree to `main` with `git checkout main && git pull
--ff-only`, because the next kit apply and the next kickoff run in that tree
on `main`.

**The hosted review, fixed in its own pull request (DESIGN §39).** Before
that return to `main`, the last unit waits up to ten minutes for the bot,
runs `hands hosted-review <pr>` (the method of docs/QODO-EXTRACTION.md as a
command), fixes the findings that are within the design and pushes; a
finding that needs a design decision is filed, never fixed in silence. The
final report's `## Hosted review` table gives each finding one disposition:
`fixed in <sha>` | `dismissed: <reason>` | `finding H-nnn filed`, and the
archive of the builder's fetch is committed on the branch with it.

**The review.** The review prompt names no PR and no commit: the protocol
finds the mission's pull request itself (`gh pr list --head mission-N --state
open --json number,baseRefName,headRefOid`). With a PR it reviews the PR's
commits since the last reviewed tip (`git log <base>..origin/mission-N`: the
merge-base with `main` for a first review, the `reviewed:` sha of the
previous REVIEW file for a closer); without one, every commit on `main` since
the last `review:` commit, as before. Before writing, the reviewer reads the
hosted review on the PR by command: a fresh-context sub-agent runs `hands
hosted-review <pr>` in a worktree at the branch. The command fetches the
bot's issue comments, reviews and review comments (`gh api
repos/<owner>/<repo>/issues/<pr>/comments`, `pulls/<pr>/reviews`,
`pulls/<pr>/comments`, every page), archives each body byte for byte under
`meta/reviews/hosted/PR-<n>/<k>/`, which is committed with the review file,
diffs it against the previous fetch by comment id, and takes the verdict
from the Code Review comment only, because the bot edits that comment in
place after a push and leaves its inline comments as they were. Exit 3,
"no bot comment yet", is the wait, never a clean review: the sub-agent waits
in the foreground up to ten minutes for the bot. It then audits the
builder's dispositions against the archive and the edited comment. The
reviewer treats the bot as a second cold reviewer: `REVIEW-N.md` gains a
`## Hosted review` section listing each bot finding verbatim as confirmed
(carried as blocker k or should-fix m) or dismissed (with the reason), with
the audit of its disposition, and `reviewed: <sha>` on its first line after
the title.

**The merge.** The review file is committed to `main` before any merge (as
`review: mission N`, pushed at once), so your clone reads it from `main` whatever
happens to the branch. On `blockers=0` the reviewer merges the PR itself —
`gh pr merge <number> --merge --subject "merge: mission N (PR #<number>)"`
— and brings the tree level with `git checkout main && git pull
--ff-only`. A merge commit, never a squash: the per-unit commits are what the
next cold review's sub-agents work on, one per commit. With blockers the PR
stays open and the reply says so; your next kit is a closer mission whose
brief names the branch to continue, and its review merges when clean. The
verdict line is unchanged: `VERDICT: review mission N blockers=<k>
should-fix=<m>`. The merge is inside the review job on purpose: a human
merging later would let the next kickoff start from a `main` without the
mission's code.

**Standing approval.** The human's approval of a playbook whose review
protocol merges on a clean review is the standing approval of every merge it
makes, as approving an autonomous playbook is approving every kit apply
(DESIGN §31; §6 above). A project that wants a human on every merge leaves the merge step out
of its protocol; the human merges from the phone's GitHub app, and the next
kickoff waits for `go`.

**Direct.** A brief that says "direct" keeps the old shape: commits go to
`main`, the final reply is `VERDICT: mission N finished` with no `pr=`, and
the protocol takes its "no PR" branch. `hands doctor`'s `gh` row warns, and
does not fail, without `gh`, because a project may commit direct
(docs/INTEGRATION.md §4).

## 10. What a stop means, and what to write next

| Stop reason | Read | Next kit |
|---|---|---|
| reviewed clean | the review's should-fix | next mission/run; carry should-fix into its U0 |
| has blockers | the review's blockers | a mission that closes them first |
| builder question | the job's `result` | an owner file as a decisions kit (§3), then `go <secret>`: route 4 of §19; after `VERDICT: question`, `answer <secret> <text>` with the zip attached is the shorter route; a plan kit only if the plan changes |
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

A `WARN playbook: <sentence>` line follows the check lines when the playbook
in force has a rule on `aux.done` and none on `aux.orphaned`, or on
`builder.done` and none on `builder.orphaned` (DESIGN §40, H-061): a
warning, not a check, so the kit still passes and the exit status is
unchanged; `--json` lists the sentences under `warnings`. A playbook you
write carries both orphaned rules (§12, "A restart kills running work").

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

A decisions kit (§3; DESIGN §42) is recognised before the checks run: every
file entry is `KIT.md` or an owner file `meta/decisions/<name>-owner.md`
(`<name>` one non-empty path component; directory entries aside, and an
entry the path rules refuse counts as another entry), with at least one
owner file, and `KIT.md`'s first line passes the rules above and reads
`plan: decisions <date> (owner)`. Then `brief` says it is a decisions kit
and needs no brief, `verdicts` that it carries no vocabulary and the
playbook in force is unchanged, and `wording` that it holds no brief;
`paths`, `playbook` (the repo's is in force) and `protocol` run as for any
kit, and a passing one ends `kit check: pass (6 of 6 checks)` with the
plan-only apply prompt. `--json` says `"decisions": true`. A kit with any
other entry, such as a `README.md` or a `PLAYBOOK.toml`, is judged as every
other kit, and without a brief it fails. `hands kit apply` takes a decisions
kit the same way; `hands kit file` refuses one with a reason, nothing filed.

## 12. Onboarding a project

1. Laptop: `~/.hands/<project>.toml`; a `handsd` instance; a driver
   directory with a fetch-only clone; the `.claude/settings.json` and
   `no_background` hook in the driven repo (`docs/INTEGRATION.md`).
2. Phone: subscribe to the project's topics; keep its command secret.
3. Project in the Claude app: paste `docs/ARCHITECT-INSTRUCTION.md` with
   the parameters filled in.
4. First kit: the playbook, the brief or plan, the review protocol;
   `hands kit check` green; treat the first series as a shakeout.

The handbook and the templates you read are the installed hands' own:
`hands handbook` prints this file's path and `hands handbook --templates`
the templates directory, and every role job carries their directory as
`$HANDS_DOCS` (`$HANDS_DOCS/docs/ARCHITECT-HANDBOOK.md`,
`$HANDS_DOCS/templates/`). A copy in a project's clone is not the hands
that runs the project and may be older (HF-002).

**A restart kills running work (DESIGN §38, §39).** A restart of handsd
kills every running job of the project, not only the builder's: a run, a
review and a consultation alike end `orphaned`, and the next start hands each
to the playbook once. The shipped playbooks carry `builder.orphaned → resume`
and `aux.orphaned → resume`, so a killed run or review is re-sent to a fresh
context, bounded by `[limits] max_resumes`; a playbook you write should carry
both. An orphaned consultation is not resumed: it stops. Restart between jobs
when you can (docs/INTEGRATION.md, "Run handsd").

**The laptop check of a role-mode plan kit (HF-005).** A kit whose playbook
sets `[series] architect = "role"` is judged against the project's hands
config, which a chat sandbox does not have, so its playbook check fails
there (DESIGN §33). Before that kit is applied, the human runs, at the
laptop, `hands kit check <kit> --repo <clone>` — the kit as it will be
sent, against the project's clone — and sends it only when every check
passes.

**The first plan kit's apply is silent.** Under `[series] autonomous` the
engine's own `builder.done` rule approves the apply of a kit the role filed
(`decided_by: playbook`), the first plan kit included, so no Approve or
Deny reaches the phone for it: the first thing the phone sees is the
kickoff the engine sends after the apply. Approving such a playbook is
approving that apply too.

### Running as the architect role (DESIGN §31)

One more step turns the phone architect — you, in this Project — into a role
handsd starts for itself: the human builds `~/hands-architect/<project>/` and
applies a playbook with `[series] architect = "role"`. `architect/README.md` is
that procedure, and `architect/CLAUDE.md` is the instruction the role runs
under; read it there rather than here. What changes for you:

- **One consultation, no memory.** handsd starts you on a review outcome
  (`aux.done`) with the review's `VERDICT:` line, its `## Blockers` and
  `## Should-fix` sections, the next unmet milestone of `meta/ROADMAP.md` (the
  first whose heading is not marked `DONE`; `— mission 10 DONE` marks a
  sub-mission, not the milestone) and the series' escalation
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
  `hands kit file` in the same consultation is refused by handsd as "one kit per
  consultation" before it is checked (DESIGN §34); a kit whose name your verdict
  does not state is denied by the engine; either way your consultation ends
  `escalate` (DESIGN §33).
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
- **The human may answer by `reply`.** `reply <secret> <text>` on `cmd_topic`
  resumes your last session with the human's text, verbatim, as one job
  (`origin: phone`), and your final message goes to the phone titled
  `architect` (DESIGN §33). A reply is a conversation, not a consultation: no
  verdict is read from it and it may not file a kit (`hands kit file` is refused
  while it runs); what you agree on goes into the next kit, filed during the
  next consultation. It is refused while a consultation runs or its `next kit`
  wait is open, and before you have a session.
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

## 13. The onboarding shape

Three chats touch a project, and each writes one kind of thing (DESIGN §38):

- **The human's Project chat writes the plan kit.** It runs under
  `docs/ARCHITECT-INSTRUCTION.md` with the Parameters and the Purpose block
  filled, and emits the first kit: the playbook, the brief or plan, the review
  protocol and the roadmap (§12). At the laptop, `hands project add <name>
  --repo <url>` has already written the config, the topics, the secret and the
  role directories (docs/INTEGRATION.md).
- **From the switch point the role writes every kit.** The switch point is the
  apply of a playbook with `[series] architect = "role"` (§12, "Running as the
  architect role"). After it the Project chat writes no kit; it answers the
  human, and a ruling it gives goes into an owner file (§14).
- **The hands architect audits kits only for hands-shaped content**: verdict
  lines, kickoff lines, playbook rules, the paths a prompt names, the shapes of
  §3 and §6, and `hands kit check`'s six checks. It does not judge the
  project's design, code or domain; those belong to the project's own chat.

**Who operates a project (DESIGN §42).** Three places can take a
notification: the project's own Claude Project chat, the laptop's aux session,
and the hands Project chat.

- **The project's own chat operates that project**, as well as designing it.
  It reads a pasted notification, reads the branch, decides, writes the file
  the decision needs (a kit, an owner file) and gives the human the exact phone
  command, or, when the phone has none, a self-contained aux prompt that names
  `--project <project>`. It keeps the project's state board in its own Project
  docs. Its vehicle is the Project instruction (`docs/ARCHITECT-INSTRUCTION.md`,
  rule 15) and the handbook of the hands installed in its own sandbox (rule
  13), not a skill. It answers from §19's operator table.
- **The laptop's aux is hands for every project**: one interactive Claude Code
  session that runs a self-contained prompt and decides nothing.
- **The hands Project chat keeps hands' own missions and the operations of the
  whole machine**: installs and upgrades, restarts that touch every project, the
  Claude accounts, a migration, the notification server. It does not operate
  another project: a project's notification brought to it is sent back to that
  project's chat. It receives from each project only that project's HF reports
  (§19, "An HF report"), takes them into the next hands kit as evidence only
  (§15), and, before a release install restarts every daemon, asks the human to
  check that no project's review or consultation is running.

The aim is phone commands only for a project's routine operations.

**The hands Project's playbook check.** The hands Project checks the
hands-facing parts of every new playbook — a project's first plan kit and each
series switch point: the playbook's rules, both orphaned rules and the
blocked→consult rule among them, the verdict vocabulary, the kickoff, the
review protocol against the template, the paths a prompt names — and never a
mission kit.

**The second onboarding shape (DESIGN §42).** An existing project whose
architect and workers the human relays by hand is reshaped into mission form
before hands drives it: the `meta/` layout (checkpoint, plan, journal,
findings, reviews), briefs from `templates/BUILDER-N-PROMPT.md` with their
`VERDICT:` lines, the review protocol from `templates/REVIEW-PROTOCOL.md`, a
roadmap of what exists and what remains, and a playbook from
`templates/PLAYBOOK-missions.toml` carrying both orphaned rules and the
blocked→consult rule. The project's own chat writes that plan kit from the
repository as it stands — its history is left as it is, never rewritten — and
the hands Project checks its hands-facing parts as it checks a first plan kit;
the rest of onboarding is §12's. Such a project is onboarded only after M9's
rehearsal (mission 29); the first is agile-skills, stopped mid-work.

## 14. The ruling round

A ruling is a question only the human (the owner) can answer. End to end:

1. **The stop.** The builder replies `VERDICT: question <one line>`, and the
   playbook's rule on it stops (`templates/PLAYBOOK-missions.toml`: "The
   builder has a question"). The phone gets the stop; the job's `result` holds
   the question in full.
2. **The owner file.** The human takes the question to the Project chat, which
   answers with `templates/DECISIONS-owner.md` filled in as
   `meta/decisions/<date>-owner.md`: `O-<n>` numbers continued from the last
   owner file on the branch, the precedence header (the file wins over DESIGN
   and every earlier decision), a "Findings closed:" line, each ruling as
   Asked and Decided, and last "For the builder", the exact steps, which is the
   only section the builder is told to read.
3. **The send: route 4 of §19.** The owner file travels as a decisions kit
   (§3): a zip holding `meta/decisions/<date>-owner.md` and a `KIT.md` whose
   first line is `plan: decisions <date> (owner)`, checked by `hands kit check`
   like any kit. From the phone: `kit <secret>` with the zip attached, Approve
   the apply's hold, then `go <secret>`. At the laptop: `hands kit apply <zip>`,
   `hands approve <job>`, then `hands go`. The apply commits the file as `plan:
   decisions <date> (owner)`, the one commit the review protocol reads for what
   it says it does and does not review as a unit. When the builder's last job
   is the one that asked (`VERDICT: question`), `answer <secret> <text>` with
   the zip attached is the shorter route: the text goes to that session as a
   `keep` send naming the file and telling the builder to carry out its "For
   the builder" steps (the zip is fetched to `kit_dir`, never unzipped; the
   delivered text ends with its path), and the builder commits the file itself.
   After an escalation the builder's tree holds the consultation's uncommitted
   journal line (DESIGN §27, §39, H-060), so the builder is told to commit a
   dirty `meta/journal.md` first, on its own, as `journal: <consultation>`. On
   an `answer` and on a `hands send` to the builder, hands puts that sentence
   before the text itself while the file is dirty; the kit's apply and `go`
   carry no such sentence, and a ruling sent any other way says it.
4. **The §8 hold, answered by typing.** A laptop send whose text matches a
   gate pattern (`Apply ~/Downloads/`, `decisions-`, `playbook-`, …) is held
   for a human, and the apply of a kit the human sends is filed held. Answer it with the Approve
   button, by typing `approve <job> <secret>` on `cmd_topic`, or with `hands
   approve <job>` at the laptop. The phone's `answer` is never held: its secret
   is the approval. A job id, on the phone and at the laptop alike, is matched
   case-insensitively, with `O` read as `0` and `l` or `I` as `1`, and a unique
   prefix of four or more characters is accepted (DESIGN §39, H-059). A command
   with the right secret that handsd refuses (no such job, a job not held, no
   resumable session) is answered on `ntfy_topic` titled `<command>` with the
   reason; only a wrong or missing secret stays silent (H-058).
5. **The resume.** The brief template's §R recovery rule: after `go`, the
   builder starts from the checkpoint, and if a `plan: decisions <date>
   (owner)` commit is on the branch after the checkpoint's last update and the
   checkpoint does not record its "For the builder" steps as done, it carries
   them out first, records them in the checkpoint, and continues. hands does
   not rely on §R alone: at the dispatch of every builder job but an apply it
   puts one sentence before the prompt naming each owner file that has had no
   checkpoint update since it was last committed, oldest first (DESIGN §43),
   after the journal sentence when both are due; it stops once the builder
   commits the checkpoint. After an
   `answer`, a `keep` send that follows `VERDICT: question` is the answer: the
   builder carries it out and continues the mission from `meta/CHECKPOINT.md`.
   Either way the reply ends with one of the brief's `VERDICT:` lines, always,
   even when a file had to be committed first; that line fires the playbook's
   rules as any builder end does. In role mode the architect's next
   consultation lists the owner file under "Decided by the human since your
   last consultation".

## 15. The separation rule

Another project appears in hands' files (DESIGN, findings, docs, templates,
tests, kits written for hands) only as evidence: name, commit, date, review
number, finding id. Never its content: no code, design text, domain terms,
fixtures or prompts copied from it. A rule that a project's experience
motivates is written in hands' own terms and cites the project as evidence,
as §17 does: "discotrade mission 13 U4 and its ruling O-21, 2026-10-15".

## 16. Re-firing a consultation after a stop

The architect role is started by a `consult` rule or by the `consult` command,
both through the engine (DESIGN §42). A direct send to it, `hands send --role
architect`, is refused by design (H-032), and the phone's `reply` is a
conversation, not a consultation: no verdict is read from it and it files no
kit (§12). To have the role consult after a ruling or a stop, in role mode:

    consult <secret> <reason>              (from the phone; a .md may be attached)
    hands consult [--file <path>] [<reason>]   (at the laptop)

The engine starts one architect job of origin `playbook` whose prompt is the
architect's consult prompt — the roadmap's next unmet milestone, the series'
escalation conditions, what the human decided since the last consultation, the
handbook and templates paths — with the review's sections replaced by "The
human's reason for this consultation", holding the reason verbatim (the text,
then the attached or named `.md` file's text: a plain `.md` name, at most 256
KiB, UTF-8). Its first line is `hands consult: consult on job none (role
human)`. The secret is the approval: nothing is held. The command un-pauses a
stopped pipeline, the consultation counts against `[limits]
max_architect_consults`, its verdict is read as a review's consultation's is
(`next kit`, `series complete`, `escalate`) and its kit is filed and applied as
any. It is refused, and the refusal published titled `consult`, outside role
mode, while any architect, builder or aux job is running, queued or held or a
`next kit` wait is open, with an empty reason, with the budget spent, and over
the prompt cap. Commit an owner file first, as a decisions kit, when the
consultation is to answer a ruling: send it by `kit <secret>` and Approve it without `go`
(a `go` starts a builder job, and the consult is refused while it runs), and
send the `consult` once its apply has ended (at the laptop `hands kit apply
<zip>`, `hands approve <job>`, then `hands consult`). Reciting a review-shaped reply through the
aux role is retired: `consult` replaces it. A blocked mission needs neither
when the playbook carries the role-mode rule on the builder's blocked verdict
(docs/PLAYBOOK.md, "The architect's consultation").

## 17. Human-supplied content

Attack-shaped test content (hostile corpora for a sandbox, exploit-shaped
fixtures and the like) is authored by no agent in the chain: a builder's
sub-agents, a project's architect chat and the hands architect chat were each
stopped on it by a safety classifier (discotrade mission 13 U4 and its ruling
O-21, 2026-10-15). A design that needs such a suite names the human-supplied
unit up front, or is reshaped so that no agent has to author the content.

The unit's shape is in `templates/BUILDER-N-PROMPT.md`: it names the files,
their repository paths and the commit message; the human places them under
`~/Downloads/<name>/`; the builder copies and commits them by path without
opening them; and the review checks that commit by `git show --stat` alone.

When no plan anticipated it — a sub-agent stops on a text the unit asks for
— the refusal path takes over (DESIGN §40). The brief's sub-agent rules say
that a sub-agent that cannot or will not produce what the unit asks reports
`refused: <one line>` and stops, changing nothing; the orchestrator does not
retry it, marks the unit `[b] refused` and continues with the units that do
not depend on it, and the mission ends `VERDICT: mission N blocked <unit>`.
Under `autonomous` that blocked verdict consults the architect role, whose
rule 8 names the condition, a unit no agent will author: it replies
`VERDICT: escalate ruling: human-supplied content`, files no kit, and names
the human-supplied unit above that would carry the content.

## 18. Reading hands: `send`, `jobs`, `pipeline`, `progress`

- **`hands send` takes the prompt as a plain argument**, after the flags:
  `hands send --role builder --context keep "<text>"`. There is no `--prompt`
  flag; prose with quotes goes through `--prompt-file <path>` or `--stdin`.
- **`hands status`** prints one line per configured role, the architect's
  included (DESIGN §39, H-053): running a job, or idle, and `queued N/M`. It says nothing about how far the work has got.
- **`hands jobs` lists newest first**, 20 by default (`-n`), filtered by
  `--role`, `--origin`, `--grep` (the prompt) and `--since`.
- **`hands pipeline`'s `auto-runs` counts only the runs a `send` rule with
  `run =` started** (DESIGN §10). The engine's kickoff, a phone `go`, a resume
  and a human's send are not counted, so `auto-runs 0/3 used` does not mean
  nothing has run.
- **`progress <secret>`** on `cmd_topic` is the phone's answer to "how far":
  the builder's running job and its age (or the last ended job and its
  verdict), the working tree's branch and `git log --oneline -3`, and the
  first line of `meta/CHECKPOINT.md` naming a unit in progress, or "no
  checkpoint". It is read-only and starts no job (DESIGN §38).
- **`hands go` and `hands kit apply <zip>`** are the phone's `go` and `kit` at
  the laptop (DESIGN §40). `go` sends the playbook's `[series] kickoff` line
  to the builder as a `clear` send with `origin: cli`, refused while a builder
  job is running, queued or held; `kit apply` checks the kit as `hands kit
  check` does, refuses a failing one, copies a passing one into `[files]
  kit_dir` and files its apply as a held builder job (`origin: kit`) that
  `hands approve <job>` releases. The architect role's guard allows neither:
  they are the human's commands for when the phone is away.
- **`hands consult [--file <path>] [<reason>]` and `consult <secret>
  <reason>`** start one architect consultation in role mode whose prompt
  carries the human's reason in place of a review (§16; DESIGN §42). The
  secret is the approval, nothing is held, and a refusal is published titled
  `consult`.
- **`hands digest` and `digest <secret>`** print, and on the phone publish
  titled `digest`, one line per project configured on the machine: its daemon,
  pipeline, mission, builder and newest verdict, consultations used of the
  budget, and last stop (§19's `digest` row says what each field means). It is
  read-only, needs no daemon, and redacts every project's `cmd_secret` and
  `ntfy_token` before a field is cut.
- **docs/OPERATIONS.md is the human's runbook** for a hands machine: what it
  holds, its secrets by kind, a usage-limit stop, operating without the
  phone, a migration, a disaster and a release install. **docs/RELATED.md
  records** two readings of other orchestrators, Gas Town and Conductor, that
  the harness work cites (DESIGN §40). Neither is a design; DESIGN.md is.

## 19. The operator table

For the human and for the project's chat (DESIGN §42): one row per
notification hands writes — every `stop` and `notify` message of
`templates/PLAYBOOK-missions.toml` and `templates/PLAYBOOK-runs.toml`, and
every stop and published line the engine, the limit manager and the daemon
write themselves — with who answers it and the route at the phone and at the
laptop. The project's chat answers a pasted notification from this table
(the Project instruction's rule 15). Every title on the phone begins
`<project>: `, which the table leaves out. A playbook `stop` and every stop
the engine makes is titled `hands: the pipeline stopped` and its message is
the stop's reason; a playbook `notify` is titled `hands: <message>`. A
placeholder is written `<n>`, `<job>`, and so on. At the laptop a command
takes `--project <project>` when the machine has more than one project; the
table leaves it out, and an aux prompt names it.

The routes:

1. **Nothing to do.** A kit applied; a kit filed by the architect whose apply
   the playbook approved; a consultation resolved; `handsd started` naming the
   jobs it resumed.
2. **A hold.** The Approve or Deny button, or typed `approve <job> <secret>` /
   `deny <job> <secret>`; at the laptop `hands approve <job>` / `hands deny
   <job>`.
3. **A kit.** `kit <secret>` with the zip attached, Approve, then `go
   <secret>` for a mission or run kit; at the laptop `hands kit apply <zip>`,
   `hands approve <job>`, `hands go`.
4. **A ruling the builder needs in the middle of a mission** (its question, a
   driver's escalation, a blocked mission the human rules on). The project
   chat's owner file travels as a decisions kit: a zip holding
   `meta/decisions/<date>-owner.md` and a `KIT.md` whose first line is `plan:
   decisions <date> (owner)`, checked by `hands kit check` like any kit and
   sent by route 3 (§3), then `go <secret>`: the builder starts from the
   checkpoint, and hands itself names the owner file before the builder's
   prompt (DESIGN §43: every builder job but an apply, while no checkpoint
   update follows the file's commit), so it carries out its "For the builder"
   steps first whatever brief the mission runs from; the brief's §R says so
   too (§14). When the builder's last job is the one
   that asked (`VERDICT: question`), `answer <secret> <text>` with the zip
   attached is the shorter route. At the laptop: `hands kit apply <zip>`,
   `hands approve <job>`, then `hands go`.
5. **A consultation the role must make after a ruling or a stop** (an
   architect escalation, whatever its reason — a ruling, a change of shape, an
   unanswered blocker, a missing milestone, human-supplied content — or a
   blocked mission under a playbook without the blocked→consult rule): any
   owner file first, as route 4's decisions kit — `kit <secret>` with the zip
   attached, Approve — but without `go <secret>`: a `go` starts a builder job,
   and `consult` is refused while a builder job is queued, running or held
   (the apply is one, until it ends). Then, once the apply has ended (its `Kit
   applied` row), `consult <secret> <reason>` (§16). At the laptop: `hands kit
   apply <zip>`, `hands approve <job>`, then `hands consult`, without `hands
   go`.
6. **A stop the project's chat reads before deciding** (a failed job, an
   orphaned consultation, an unrecognised verdict, `max_resumes` reached,
   processes left behind, a tripwire, a review a restart killed under a
   playbook without `aux.orphaned`): `progress <secret>` and `status
   <secret>`, then route 3, 4 or 5, or `go <secret>` when the branch shows the
   work can continue as it stands; a killed review is re-sent by the aux
   prompt the table gives (the playbook's review prompt, sent to the aux
   role). A defect of hands found on the way is an HF report (below).
7. **A usage-limit stop.** Under the shipped playbooks a builder's limit stops
   the pipeline (no rule names `builder.limited`), while the limit manager's
   resume is scheduled at the reset and runs anyway. The human keeps the stop's
   capture for the hands Project (`bash scripts/capture-quota-stop.sh
   <project>` from the hands repository, docs/OPERATIONS.md), then `resume
   <secret>` (at the laptop `hands resume`), so the resumed job's end fires the
   playbook's rules. This row is rewritten when credential profiles are built.
8. **A machine-wide event** (a daemon down, the notification server
   unreachable, a sign-in lost, an install due): the hands Project.

A review outcome in role mode consults the role by itself; the human sees only
its consequences.

| Notification | Who answers | Phone | Laptop |
|---|---|---|---|
| `hands: Kit applied; the next kickoff is the driver's` (missions template) | nobody — route 1 | nothing; a mission kit's route 3 ends with `go <secret>` | nothing; route 3 ends with `hands go` |
| `hands: Kit applied` (runs template) | nobody — route 1 | nothing; a run kit's route 3 ends with `go <secret>` | nothing; route 3 ends with `hands go` |
| `hands: kit <name> filed by the architect; apply approved by the playbook` | nobody — route 1 | nothing: the engine sends the kickoff | nothing |
| `hands: A held job was denied` | nobody — route 1 | nothing: a denial is somebody's decision already | nothing |
| `hands: the pipeline stopped` — Mission <n> reviewed clean; next mission is the architect's | the project's chat — route 3 | the next mission's kit: `kit <secret>` with the zip, Approve, `go <secret>` | `hands kit apply <zip>`, `hands approve <job>`, `hands go` |
| `hands: the pipeline stopped` — Mission <n> review has blockers | the project's chat — route 3 | a mission that closes the blockers first, by route 3 | `hands kit apply <zip>`, `hands approve <job>`, `hands go` |
| `hands: the pipeline stopped` — Run <n> review has blockers | the project's chat — route 3 | a run that closes the blockers first, by route 3 | `hands kit apply <zip>`, `hands approve <job>`, `hands go` |
| `hands: the pipeline stopped` — Mission <n> blocked; see the builder's reply | the project's chat — route 4 | `progress <secret>`; the owner file as a decisions kit: `kit <secret>` with the zip, Approve, then `go <secret>`. In role mode under a playbook without the blocked→consult rule, instead: `kit <secret>` with the zip, Approve without `go <secret>`, and once the apply has ended `consult <secret> <reason>` (route 5) | `hands kit apply <zip>`, `hands approve <job>`, `hands go`; for route 5 instead `hands kit apply <zip>`, `hands approve <job>`, then `hands consult` without `hands go` |
| `hands: the pipeline stopped` — Run <n> blocked | the project's chat — route 4 | as for a blocked mission | as for a blocked mission |
| `hands: the pipeline stopped` — The builder has a question | the project's chat — route 4 | the decisions kit: `kit <secret>` with the zip, Approve, `go <secret>`; or, the shorter route, `answer <secret> <text>` with the zip attached | `hands kit apply <zip>`, `hands approve <job>`, `hands go`; or `hands send --role builder --context keep "<text>"` |
| `hands: the pipeline stopped` — The builder needs a decision | the project's chat — route 4 | as for "The builder has a question" | as for "The builder has a question" |
| `hands: the pipeline stopped` — Builder finished without a recognised verdict | the project's chat — route 6 | `progress <secret>`, `status <secret>`; then a kit that fixes the vocabulary or the brief (route 3), or `go <secret>` | `hands jobs --role builder -n 1`, `hands status`; then route 3 or `hands go` |
| `hands: the pipeline stopped` — Aux finished without a recognised verdict | the project's chat — route 6 | `progress <secret>`, `status <secret>`; none to re-send a review: give the aux prompt | aux prompt: `hands --project <project> send --role aux --context clear "<the playbook's review prompt, <n> filled>"` |
| `hands: the pipeline stopped` — Aux job failed | the project's chat — route 6 | `status <secret>`; none to re-send the review: give the aux prompt | aux prompt: `hands --project <project> jobs --role aux -n 1`, then the review prompt re-sent as above |
| `hands: A task inside a role job was killed` | the project's chat — route 6 | `progress <secret>`; nothing more unless a stop follows | `hands jobs -n 3` |
| `hands: Builder looks stalled` | the project's chat — route 6 | `progress <secret>`; nothing more unless it stays stalled | `hands who`, `hands status` |
| `hands: the pipeline stopped` — Processes outlived their job | the project's chat — route 6 | `status <secret>`, `progress <secret>`; then `go <secret>` or route 3 | `hands who`, `hands status`, then `hands go` |
| `hands: the pipeline stopped` — Tripwire fired | the project's chat — route 6 | `progress <secret>`; then route 3, 4 or 5 | `hands jobs -n 3`, `hands status` |
| `hands: a job is held for a human` — <reason>, `role:`, `job:`, the job id on its own line | the human alone — route 2 | the Approve or Deny button, or `approve <job> <secret>` / `deny <job> [reason] <secret>` | `hands approve <job>` / `hands deny <job> --reason "<reason>"` |
| `hands: kit received` — kit received <name> <bytes> <sha256> | the human alone — route 3 | Approve the apply's hold (its own notification), then `go <secret>` | `hands approve <job>`, `hands go` |
| `hands: handsd started` — <project> on <socket>, then `Resumed: <role> job <job>, from job <job> …` | nobody — route 1 | nothing; a line folded in under `While starting, handsd raised …` is answered by its own row | `hands status` |
| `hands: handsd crashed` — <error type>: <message> | the hands Project — route 8 | nothing to send; give it to the hands Project | `journalctl --user -u handsd@<project>` for the hands Project |
| nothing arrives, or a `digest` line reads `daemon down` | the hands Project — route 8 | `digest <secret>` on another project's `cmd_topic` | `hands digest` |
| `hands: the pipeline stopped` — paused by human | nobody — route 1 | `resume <secret>` when it should go on | `hands resume` |
| `hands: the pipeline stopped` — builder.limited: the playbook has no rule for it, and §10 stops for anything it did not pre-plan | the human alone — route 7 | after the capture, `resume <secret>` | `bash scripts/capture-quota-stop.sh <project>` from the hands repository, then `hands resume` |
| `hands: the pipeline stopped` — limits.max_resumes reached: <role> has been resumed <k> time(s) with no `done` in between and is limited again | the project's chat — route 6 | `progress <secret>`, `status <secret>`. No resume is scheduled for the role and none is re-armed at a restart, so `resume` would only clear the pause; the role's resume count is cleared only by a `done`, so a job limited again before one stops at once. After the limit's reset: for the builder `go <secret>` (it starts from the checkpoint), or route 3, 4 or 5; for the aux, the aux prompt that re-sends the review. The capture is worth keeping for the hands Project (route 7's) | `bash scripts/capture-quota-stop.sh <project>` from the hands repository for the hands Project; `hands jobs --role <role> -n 3`, `hands status`; after the limit's reset `hands go` for the builder, or for the aux the aux prompt: `hands --project <project> send --role aux --context clear "<the playbook's review prompt, <n> filled>"` |
| `hands: the pipeline stopped` — could not resume <role> after its limit: <error> | the project's chat — route 6 | `status <secret>`; an HF report | `hands jobs --role <role> -n 1` |
| `hands: the pipeline stopped` — <event>: <role> has already been resumed <k> time(s) with no `done` in between and [limits] max_resumes is <m> | the project's chat — route 6 | `progress <secret>`, `status <secret>`; then `go <secret>` or route 3 | `hands jobs --role <role> -n 3`, then `hands go` |
| `hands: the pipeline stopped` — <event>: the playbook has no rule for it, and §10 stops for anything it did not pre-plan (any other event) | the project's chat — route 6 | `progress <secret>`; then a kit whose playbook has the rule (route 3), or `go <secret>` | `hands pipeline`, then route 3 or `hands go` |
| `hands: the pipeline stopped` — <event>: every rule for it matches on a verdict and <what>; §10 stops on a missing or unparseable VERDICT: | the project's chat — route 6 | `progress <secret>`; then route 3, or `go <secret>` | `hands jobs -n 1`, then route 3 or `hands go` |
| `hands: the pipeline stopped` — <event>: no rule matches the verdict '<verdict>' | the project's chat — route 6 | `progress <secret>`; then a kit that fixes the vocabulary or the playbook (route 3) | `hands jobs -n 1`, then route 3 |
| `hands: the pipeline stopped` — the playbook cannot be read, does not agree with this project's configuration, or renames the series without restating the architect's budget, so no rule can be trusted to fire: <error> | the project's chat — route 6 | a kit whose playbook loads (route 3), checked first at the laptop | `hands kit check <kit> --repo <clone>`, then route 3 |
| `hands: the pipeline stopped` — the apply removed <playbook path> | the project's chat — route 6 | a kit that restores the playbook (route 3) | route 3 |
| `hands: the pipeline stopped` — <event>: the playbook engine failed (<error>) | the project's chat — route 6 | `status <secret>`; an HF report; then `go <secret>` | `hands pipeline`, then `hands go` |
| `hands: the pipeline stopped` — <event>: rule <i> cannot be rendered: <error> | the project's chat — route 6 | a kit whose playbook's rule renders (route 3) | route 3 |
| `hands: the pipeline stopped` — <event>: rule <i> would start run <run>, which [limits] auto_runs does not list (<runs>); §10 stops for a run nobody pre-planned | the project's chat — route 3 | a run kit that plans it, or a playbook listing it, by route 3 | route 3 |
| `hands: the pipeline stopped` — <event>: rule <i> could not send to <role>, could not resume <role>, or could not start the <role>: <error> | the project's chat — route 6 | `status <secret>`; an HF report if the error is hands' own; then `go <secret>` | `hands status`, `hands doctor`, then `hands go` |
| `hands: the pipeline stopped` — <event>: rule <i> is a resume and the event carries no job to resume, or is a consult and the event carries no job to consult about | the project's chat — route 6 | a kit whose playbook puts the rule on a job's event (route 3) | route 3 |
| `hands: the pipeline stopped` — <event>: rule <i> is a consult and this project configures no [roles.<role>] | the project's chat — route 6 | a kit without the consult rule (route 3), or the aux prompt that adds the role | aux prompt: add the `[roles.<role>]` table docs/INTEGRATION.md gives to `~/.hands/<project>.toml`, then `systemctl --user restart handsd@<project>` between jobs |
| `hands: the pipeline stopped` — <event>: rule <i> would start consultation <k> of this series and [limits] max_architect_consults is <b> (§31): the series' consult budget is exhausted (budget-exhausted) | the project's chat — route 3 | the next kit by route 3, its playbook restating the budget if the series goes on in role mode | route 3 |
| `hands: the pipeline stopped` — <event>: rule <i> would start consultation <k> of this mission and [limits] max_consults is <b> (§27) | the project's chat — route 6 | `progress <secret>`; then route 3 or 4 | route 3 or 4 |
| `hands: the pipeline stopped` — <event>: the architect escalated: <reason> — session <id>; continue it in the architect's directory with `claude --resume <id>` (§31) | the project's chat — route 5 | any owner file first as a decisions kit: `kit <secret>` with the zip, Approve without `go <secret>`; once the apply has ended, `consult <secret> <reason>` | `hands kit apply <zip>`, `hands approve <job>`, then `hands consult` without `hands go` |
| `hands: the pipeline stopped` — <event>: the architect's consultation <job> ends escalate (§33): <why>; … | the project's chat — route 5 | as for "the architect escalated": any owner file as a decisions kit, Approve without `go <secret>`; once the apply has ended, `consult <secret> <reason>` | as for "the architect escalated": `hands kit apply <zip>`, `hands approve <job>`, then `hands consult` without `hands go` |
| `hands: the pipeline stopped` — <event>: the architect replied series complete: the roadmap's gates are met and there is no next kit, so the pipeline stops (§31) | the project's chat — route 3 | the next series' kit by route 3, or nothing | route 3 |
| `hands: the pipeline stopped` — <event>: the consultation's architect job ended <state>, and a consultation that does not end in a verdict stops (§31) | the project's chat — route 6 | `status <secret>`; then `consult <secret> <reason>` (route 5) | `hands jobs --role architect -n 1`, then `hands consult` |
| `hands: the pipeline stopped` — <event>: the architect's reply has no VERDICT: line, or the architect's verdict '<verdict>' is none of … | the project's chat — route 6 | `status <secret>`; then `consult <secret> <reason>` (route 5) or route 3 | `hands jobs --role architect -n 1`, then `hands consult` or route 3 |
| `hands: the pipeline stopped` — <event>: the architect replied '<verdict>' and no apply of kit '<name>' was filed for its consultation (job <job>) within [series] kit_wait_s = <s> (§32) | the project's chat — route 6 | `status <secret>`; then `consult <secret> <reason>` (route 5) or route 3 | `hands jobs --role architect -n 1`, then `hands consult` or route 3 |
| `hands: the pipeline stopped` — job.held: the engine could not approve the architect's apply <job>: <error>, or <job> is the architect's apply under an autonomous playbook and this engine has no approve seam | the human alone — route 2 | the hold follows with its buttons: Approve or Deny it, then `resume <secret>` | `hands approve <job>` or `hands deny <job>`, then `hands resume` |
| `hands: the pipeline stopped` — job.held: the architect's apply <job> is not approved: the stored zip of kit_id <kit> has sha256 <a>, and the kit check passed on sha256 <b> (§34); the hold is the human's | the human alone — route 2 | Deny the hold that follows; an HF report | `hands deny <job> --reason "<reason>"` |
| `hands: a consultation stopped over a paused pipeline` — <reason> | the project's chat — route 6 | the pipeline stays paused; answer the reason by its own row | as the reason's own row |
| `hands: the pipeline stopped` — driver.<state>: the driver escalated: <reason> (§27, §28); the <role>'s question (job <job>), verbatim: … | the project's chat — route 4 | as for "The builder has a question" | as for "The builder has a question" |
| `hands: the pipeline stopped` — driver.<state>: the consultation's driver job ended <state>, the driver's reply has no VERDICT: line, or the driver's verdict '<verdict>' is neither resolved nor escalate | the project's chat — route 6 | `progress <secret>`; then route 3 or 4 | route 3 or 4 |
| `<command>` — <command> refused: <why> (a refused phone command; `reply` and `answer` are titled `hands: reply` and `hands: answer`) | the project's chat — route 6 | the corrected command, once the reason is read | the laptop form, which refuses the same |
| `hands: go`, `hands: answer`, `hands: reply`, `hands: consult` — go: builder job <job> <state> (and its kin) | nobody — route 1 | nothing: the job's end is its own row | nothing |
| `architect` — the architect's reply to a `reply`; `builder` — the builder's final reply to an `answer` | nobody — route 1 | nothing: the builder's verdict fires the playbook's rules | nothing |
| `hands: status`, `progress` — the answer to `status <secret>`, `progress <secret>` | nobody — route 1 | nothing | nothing |
| `hands: notify --test` — <message> | nobody — route 1 | nothing: it proves the topic | nothing |
| `digest` — one line per project: `<project> \| daemon up\|down \| pipeline running\|paused \| mission <n>\|- \| builder running <job> <age>\|idle, verdict <line>\|none \| architect\|driver <used>/<budget> \| stop <time> <reason>\|no stop`; a config that does not load is one line, `<file>: does not load` | nobody — route 1 | `digest <secret>` asks for it. The fields: the daemon is `up` when its socket answers `status` within two seconds, else `down`; the pipeline `running` or `paused`; the mission the number on the first `Mission:` line of the builder's `meta/CHECKPOINT.md`, else `-`; the builder `running <job> <age>` or `idle`, with the newest builder job's verdict cut to 60 characters; the consultations `architect <used>/<budget>` in role mode, else `driver <used>/<budget>`; the last stop's time and the first line of its reason cut to 100 characters, or `no stop`. Every project's `cmd_secret` and `ntfy_token` is redacted before a field is cut | `hands digest` |
| HF report — a defect of hands met on the way (below) | the project's chat — route 6 | nothing to send: the file goes to the hands Project | nothing to run: the file goes to the hands Project |

### An HF report

A defect of hands that a project meets is recorded in that project's ledger as
an HF-nnn entry and handed to the hands Project as one file,
`HF-<n>-report.md`, holding evidence only (DESIGN §42):

- the HF id and its date;
- the project's name;
- the hands build it ran: `hands --version` and the commit the last install named;
- what hands did: the notifications, job ids, command lines and their output as they appeared;
- what the project expected of hands;
- the commit, review number or consultation number where it was seen;
- the project's interim workaround if any, named by what it does to hands, never by the project's content.

No product design, code, domain term or fixture goes into it (§15). The hands
Project files it as H-nnn citing the HF id.
