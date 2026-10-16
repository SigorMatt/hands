# BUILDER-24-PROMPT — hands mission 24: M8a, the harness probe and the seam's shape; the day's findings; operations

Kickoff line (the only way this mission is started or resumed):

    Read the builder prompt with the highest mission number in the meta directory and execute the mission below its divider.

You are the builder for the `hands` repository. Read `DESIGN.md` (v3.23; §40
is this mission, with §2, §23, §33, §35, §38, §39), `CLAUDE.md`,
`meta/CHECKPOINT.md` (a unit in progress means §R first),
`meta/reviews/REVIEW-23.md`, `docs/RELATED.md` and `docs/QODO-EXTRACTION.md`
in full.

---

## Mission

Run the harness probe on the laptop's three installed candidate harnesses
and record it (§40, U1); give the laptop the two phone-only commands,
`hands go` and `hands kit apply` (U2); de-duplicate the monitor's
`task_killed` and make the transcript path follow `CLAUDE_CONFIG_DIR` (U3,
H-062, H-063); close review 23's should-fix items 3–9 (U4, U5); warn on a
playbook that lacks `aux.orphaned` (U6, H-061); carry four findings from
another project's reviews into the templates and the handbook (U7,
H-066..H-069); write docs/OPERATIONS.md, the human's runbook (U8); correct
the docs (U9); open the pull request and read its hosted review (U10). It
does NOT implement the backend seam, the credential profiles, the polish
round or any M9 command: those are missions 25 and 26, designed in §41 from
this mission's probe record. Finish with a report whose first line the
playbook can match.

## Branch (DESIGN §35)

Pull request. This mission runs on the branch `mission-24`. U0 creates it
from `main` (`git checkout main && git pull --ff-only && git checkout -b
mission-24`). Every unit commit goes to that branch and is pushed at once
(`git push -u origin mission-24` the first time). The last unit opens the
pull request — `gh pr create --base main --head mission-24 --title "mission
24: M8a probe, the day's findings, operations" --body-file
meta/FINAL-REPORT-24.md` — waits for the hosted review, fixes what §40
allows, and the final reply's verdict carries the PR number. Then return
the working tree to `main` (`git checkout main && git pull --ff-only`): the
next kit apply and the next kickoff run in this tree, on `main`.

## Execution model (binding)

- You are a thin orchestrator. You plan units, write the checkpoint,
  dispatch ONE sub-agent per unit (Task tool, foreground only), verify the
  unit cheaply, record one line, move on. You run nothing longer than `git
  status`, `git log --oneline -5`, `hands hosted-review <pr>` and
  `./scripts/check` yourself.
- Before each unit: write `meta/CHECKPOINT.md` (unit id, intent, what
  "done" means, standing constraints). After each unit: update it and
  append one line to `meta/journal.md`.
- Every unit ends with a commit AND a push, to `mission-24`. A unit commit
  carries only its own files and its body lists every one; never `git add
  -A`. The U0 commit uses the `plan:` prefix. Drafts of the final report
  live under `meta/drafts/` (git-ignored) until the last unit.
- Retry a failed unit once with the sub-agent's report attached; after two
  failures mark it `blocked` in `meta/plan.md` and continue with units that
  do not depend on it. A sub-agent that reports `refused: <one line>` is
  not retried: mark the unit `[b] refused` and continue likewise.
- Never edit product code yourself. Never edit `DESIGN.md` (file a finding
  instead).
- `./scripts/check` three times before every commit, each run its own
  foreground call with an explicit timeout of 20 minutes.
- Your final reply begins with exactly one of: `VERDICT: mission 24
  finished pr=<number>` | `VERDICT: mission 24 blocked <unit>` | `VERDICT:
  question <one line>`.

## Sub-agent brief (give this to every unit sub-agent, verbatim, plus the unit)

    You are implementing one unit of hands. Read, in this order: CLAUDE.md,
    DESIGN.md sections named by the unit, meta/CHECKPOINT.md, the finding or
    review item(s) named by the unit, then only the files the unit touches.
    Rules: the design is the spec — where it is silent, choose the simplest
    thing and say so in the commit body; write the failing test before the
    code and confirm it fails; ./scripts/check green three times before you
    commit, each run a foreground call with a 20-minute timeout; one
    commit, `<area>: <one line>` + a body naming the unit, the DESIGN
    sections and the item, listing every file, and stating only what the
    tests prove — never a totality claim unless a test enumerates the whole
    space; a commit that changes only tests names in its body each wrong
    change that would make them red; a commit that adds or deletes a
    non-test file names it as added or deleted; never `git add -A`; push to
    the branch `mission-24`; never edit meta/plan.md, meta/CHECKPOINT.md,
    or DESIGN.md; if the unit needs a design change, stop and write a memo
    to meta/findings/FINDINGS.md instead of improvising; if you cannot or
    will not produce what the unit asks, report `refused: <one line>` and
    stop, changing nothing; dispatch nothing in the background; never
    require a real `claude`, `gh`, `systemctl`, ntfy server, harness binary
    or `git` remote in tests (fakes on PATH, a local HTTP stub and local
    bare repositories, as tests/fake_claude.py is); never print, commit or
    quote a key, a token or a sign-in file — write `[redacted]`; report in
    ≤12 lines: sha, files, tests added, what is NOT proven.

## §R Recovery brief

If `meta/CHECKPOINT.md` names a unit in progress and the working tree is
dirty: finish that unit under the sub-agent rules if it can pass
`./scripts/check`; otherwise `git stash push -m "wip <unit> <date>"`,
record in the checkpoint where it stopped and that a stash exists, and
leave the tree clean. Then continue from that unit. Push before taking any
new unit. If the tree is on `main` and `origin/mission-24` exists, `git
checkout mission-24 && git pull --ff-only` first. A `keep` send that
arrives after you replied `VERDICT: question` is the answer: carry it out,
continue the mission from the checkpoint, and end that reply with one of
the mission's `VERDICT:` lines, always, even when the answer came with a
file to commit first. If `meta/journal.md` alone is dirty when you start,
commit it first as `journal: consultation lines` and push.

## Units, in order

**U0 Plan, branch and findings (`plan:` commit).** `meta/plan.md`,
`meta/CHECKPOINT.md`; the branch `mission-24` created and pushed. File in
`meta/findings/FINDINGS.md`, each with the evidence §40 gives: H-062 the
monitor raises `task_killed` once per transcript line, not once per task,
and for a job the daemon itself stops (2026-10-16 13:45 twice on an
orphaned builder; 16:05 three times within 120 ms on one review job); H-063
`runner.transcript_path_for` names `~/.claude/projects` and ignores
`CLAUDE_CONFIG_DIR`; H-064 §39's lenient-id command list named `answer` and
`reply`, which carry no job id — decided in §40, the code's behaviour is
the design; H-065 the architect's read roots are `$HANDS_DOCS/docs` and
`$HANDS_DOCS/templates`, narrower than §39 — decided in §40, and H-051's
Status line is corrected to say so; H-066 a sub-agent may refuse to author
what a unit asks and no escalation condition anticipated it (from another
project's ledger, its HF-009, 2026-10-14; evidence only: the project's
name, the date, the finding id); H-067 git worktrees of aborted review
sessions are left registered (its HF-010, reviews 13–15); H-068 the review
protocol's skip list does not name `plan:`, `journal:` or `report:` (its
HF-011); H-069 a reviewer's sub-agent ran the gate twice, in the
background, or returned before it finished (its HF-012, review 15). H-061
gains "decided (DESIGN §40, mission 24 U6)". Carry review 23's should-fix
3–9 by number into the units below; items 1 and 2 are H-064 and H-065.
Gate: the entries exist; `git branch -r` shows `origin/mission-24`.

**U1 The harness probe (§40; docs/RELATED.md Gas Town section).** A new
`docs/HARNESS-PROBE.md`, nothing else. The sub-agent works in a fresh
scratch git repository it creates under `/tmp` (one commit, one file),
never in this tree, with `PATH=$HOME/.nvm/versions/node/v22.23.3/bin:$PATH`
on every harness command, and the same task for every harness: "create a
file `probe.txt` containing the word ok and commit nothing; your reply's
first line must be exactly `VERDICT: probe ok`". It first records the
versions it finds (`codex --version`, `opencode --version`, `dsh
--version`, `node --version`, `claude --version`) and, per harness, the
sign-in state as a provider name only (`codex login status`; `opencode
auth list` or the provider configuration's presence; `DEEPSEEK_API_KEY`
set or not — never its value). A harness that is not signed in gets
`unavailable: not signed in` in every row and the sub-agent moves on. For
each available harness it discovers the invocations from `--help` and the
installed package's documentation, then records, as §40 lists: the exact
one-shot headless command, its exit status and the first and last five
lines of its event stream (Codex: `codex exec` with its JSON output flag
and its most restrictive sandbox that still lets the task write in the
working directory; OpenCode: `opencode run` with its JSON format and the
configured default model (`opencode models`; none configured means
`unavailable: no model configured`); dsh: `dsh --profile headless --json`); the resume
command (Codex's `exec resume` or its documented equivalent; OpenCode's
session flags; dsh's `--session-id`) with a second turn asking "what did
you create?", and whether the answer names the file; the session store's
path and the shape of one session file (keys of its first record, not its
contents); what happened, under that sandbox or permission setting, to a
turn asked to run `touch /tmp/outside-probe` and to one asked to run `curl
--version` — refused by the harness, asked about and how a headless run
answered, or ran; whether the final message's first line was `VERDICT:
probe ok` verbatim; the harness's documented output on a usage limit (its
docs and source, quoted with the path; not provoked); its telemetry and
session-upload switches (dsh: `DSH_TELEMETRY_DISABLED` and the
`dsh_session_log` wire extension's switch, with the config catalog path);
and ACP: a built-in mode (`opencode acp`, dsh's `acp` profile) or an
adapter package (Codex: name and version, installed or not, from `npm view`
only, nothing installed by the probe). The record ends with a table, one
row per harness and one column per requirement of §40 (one-shot, resume,
readable stream, enforceable permission, VERDICT), each cell `yes`, `no`
or `partial: <why>`, and a `Gaps` list of what the probe could not
observe. Every command and its output are quoted verbatim, keys and tokens
as `[redacted]`. Gate: `docs/HARNESS-PROBE.md` exists with every row of
every harness filled or marked unavailable; `grep -c redacted` is reported;
`./scripts/check` green (the docs test does not read this file's claims).

**U2 `hands go` and `hands kit apply` (§40; §29; §32).** `src/hands/cli.py`,
`src/hands/api.py`, `src/hands/kit.py` or `src/hands/phone.py` as the
existing kit path dictates, `README.md`, tests. `hands go` sends the
playbook's `[series] kickoff` line to the builder as a `clear` send with
`origin: cli`, refused with the phone's reason while a builder job is
running, queued or held, through the same code the phone's `go` uses.
`hands kit apply <zip>` runs the kit check, refuses a failing kit with the
check's output, copies the zip into `[files] kit_dir` under its own name
unless it is already there (refusing to overwrite another file), and files the apply prompt as a held builder job
with `origin: kit`, exactly as the phone's `kit` path does after the fetch;
the hold is published as any hold is, and `hands approve <job>` releases
it. README's command list names both. Tests: `go` refused while a builder
is held; `go` sends the kickoff with `origin: cli`; `kit apply` of a
failing kit files nothing; `kit apply` of a passing kit files a held job
whose prompt is the check's apply prompt and whose record names the copied
zip. Gate: the tests; `./scripts/check` green.

**U3 The monitor and the runner (§40; §2; H-062, H-063).**
`src/hands/monitor.py`, `src/hands/runner.py`, `src/hands/daemon.py` if the
stop path needs it, tests. `task_killed` is raised once per killed task,
keyed by the task's id in the transcript, across scans; it is not raised for
a job the daemon is stopping (the record becomes `orphaned`, as §38 says).
`transcript_path_for` takes the job's environment: `$CLAUDE_CONFIG_DIR/
projects/<dashed cwd>/<session>.jsonl` when the role's `env` sets it,
`~/.claude/projects/…` otherwise, and the runner records the path in the
job record before the first scan. Tests: a transcript with the same killed
task on three scans raises once; two killed tasks raise twice; a daemon
stop raises nothing for the job it orphans; a role with `CLAUDE_CONFIG_DIR`
in its env table has its transcript path under it and the monitor reads a
transcript written there by the fake claude. Gate: the tests;
`./scripts/check` green.

**U4 The hosted-review command's proofs (§39; review 23 should-fix 3, 4,
5).** `src/hands/hosted.py`, `src/hands/phone.py`, `src/hands/api.py`,
tests and fixtures. A fixture with a review body headed "Code Review" and
an inline comment headed "Code Review" (both ignored) and one with two Code
Review issue comments (the newest wins) pin "the verdict from the Code
Review comment only"; a fixture whose header counts one finding and whose
only finding is struck through expects exit 4; the refusal's redaction
runs before the reason is formatted (or the typed id is formatted with
`str`, never `repr`), with a test whose secret contains a backslash and
whose published and logged reason contain no part of it. Gate: the tests;
`./scripts/check` green.

**U5 The engine, the docs' claim and two unpinned behaviours (§39; review
23 should-fix 6, 7, 8, 9).** `src/hands/api.py`, `src/hands/daemon.py` or
`src/hands/runner.py` as the dispatch path dictates, `docs/INTEGRATION.md`,
`src/hands/project.py`, tests. The commit-the-journal sentence is decided
when the send is dispatched, not when it is enqueued, so a held or queued
send carries it only if `meta/journal.md` is dirty at dispatch (a test: dirty
at enqueue, committed before dispatch, no sentence; and the reverse).
docs/INTEGRATION.md says what `_decide` does: a malformed `approve` or
`deny` is answered only when its last word is the secret; with a nonce it is
logged and not published (the doc changes, not the code). An instruction
test pins architect rule 2's text (reverting `architect/CLAUDE.md` alone
turns it red). `project add` tests: the dry run's `git clone -- {repo}`
text asserts the `--`; a fake `git` whose `remote set-url` fails makes the
command report a failed clone and remove what it created. Gate: the tests;
`./scripts/check` green.

**U6 The playbook without `aux.orphaned` (§40; H-061).** `src/hands/kit.py`
(or wherever the playbook checks live), `src/hands/playbook.py`,
`docs/PLAYBOOK.md`, tests. `hands kit check` prints a `WARN` line, and the
engine logs one at load, for a playbook with a rule on `aux.done` and none
on `aux.orphaned`, and likewise for `builder.done` without
`builder.orphaned`; neither refuses the playbook; the check's `playbook`
line still passes. docs/PLAYBOOK.md says so. Tests: each pairing warns;
both rules present warns nothing; a kit with such a playbook passes 6 of 6
with the warning printed. Gate: the tests; `./scripts/check` green.

**U7 The templates and the handbook on refusals, worktrees, the skip list
and the gate (§40; H-066..H-069).** `templates/BUILDER-N-PROMPT.md`,
`templates/REVIEW-PROTOCOL.md`, `meta/REVIEW-PROTOCOL.md`,
`architect/CLAUDE.md`, `docs/ARCHITECT-HANDBOOK.md` §7 and §17, tests. The
brief template's sub-agent rules gain the `refused: <one line>` sentence
and its execution model the `[b] refused` rule, both as this brief has
them; `architect/CLAUDE.md` rule 8's escalation conditions gain "a unit no
agent will author", answered `VERDICT: escalate ruling: human-supplied
content`, naming the human-supplied unit shape; both protocols' reviewer
starts with `git worktree prune` and removes stale review worktrees of
earlier reviews it finds under `/tmp`, and ends by removing its own; the
skip list reads `plan:` (read for what it says), `meta:`, `journal:` and
`report:` (read for forbidden edits only, never reviewed as a unit),
`review:` and merge commits; the per-commit sub-agent rules say "run
`./scripts/check` once, in the foreground, and report only when every
command has finished"; the handbook says each of these. The two protocol
files differ only in the project's names. Tests: the sentence-pinning tests
cover each new sentence; a kit from the templates passes `kit check` 6 of
6. Gate: the tests; `./scripts/check` green.

**U8 docs/OPERATIONS.md (§40).** A new `docs/OPERATIONS.md` and a `doctor`
row, `src/hands/doctor.py`, tests. The document is the human's runbook for
every project on the machine, written from the code as it is at this
commit: (1) the inventory — the `uv tool` install, `~/.hands/<project>.toml`,
the spool `~/.hands/<project>/` with every file or directory the spool
module defines classified as regenerable, must-carry or safe to drop and
the series' state of record named as the project's branch, the user units
and linger, the role directories and what each holds, the builder's clones,
the notification server's files, the kit directory, the harness sign-ins;
(2) the secrets table — one row per kind of secret the machinery or its
sign-ins use (the notification user's password and token, each project's
command secret, the notification server's user database, each harness's
sign-in per profile, `gh`, the git push credential, the tailnet node), with
where it lives, its file mode, how it is obtained again and whether it can
be regenerated — and no value, example or pattern of a value anywhere;
(3) the runbooks — a usage-limit stop (what the stop looks like; `bash
scripts/capture-quota-stop.sh <project>`, a read-only script this unit
adds, which writes `~/quota-capture-<project>-<time>.txt` with `hands
status`, `jobs -n 5`, `pipeline`, the newest job record or the one named
as its second argument, the job's stream-json tail and its lines about a
limit, the transcript's tail, the daemon journal's lines about the job, and
the inbox's tail, after redacting the project's command secret, the
notification token and password by value and keys and bearer tokens by
pattern; then wait for the reset and `go`; after M8b, the profiles), no phone (the table of every phone command and its
laptop form, `go` and `kit apply` included, and the notification server's
web page), a planned migration (what to export by hand until M9, the
secrets checklist, the order of logins, `hands doctor`, one kickoff), a
disaster (what the branch holds, what the unit in progress loses, re-filing
a kit that was in flight, re-firing a review that was in flight, where the
consult budget's count of record lives — settled from the code), and a
release install (the steps the architect's routine performs today, each as
a command). `hands doctor` gains a WARN row for a worktree registered under
a role's clone whose path no longer exists (H-067). Tests: the docs test
pins the runbook headings and the secrets table's columns and asserts the
file contains no string shaped like a token (the test enumerates the
shapes it checks); the capture script against a fake `hands` on PATH and a
fake spool holding a planted secret and a planted key, whose output names
neither; the doctor row on a fake clone with a dangling worktree entry. Gate: the tests; `./scripts/check` green.

**U9 The docs (§40).** `docs/INTEGRATION.md`, `docs/ARCHITECT-HANDBOOK.md`
§18, `README.md`, tests. INTEGRATION: the `[roles.<role>].env` PATH note
for harnesses installed under nvm, `hands go` and `hands kit apply`, the
transcript path under `CLAUDE_CONFIG_DIR`, the kit-check warning, and a
pointer to docs/OPERATIONS.md and docs/RELATED.md. The handbook's §18 names
`hands go` and `hands kit apply`. The docs test pins each sentence. Gate:
the tests; `./scripts/check` green.

**U10 Final report, the pull request and the hosted review's findings.**
`meta/FINAL-REPORT-24.md` (drafted under `meta/drafts/`, moved in by this
commit): what changed (sha per unit), what tests prove, NOT PROVEN
(mandatory: the probe's rows that are `unavailable` or `partial`, and that
no real harness ran in the tests), the `## Review items` table for review
23's should-fix 1–9 (1 and 2 as findings decided in §40). Then open the
pull request (see Branch) and wait up to ten minutes for the bot, the
hosted reviewer, in one-minute foreground steps: `hands hosted-review <pr>`
exits 3 with "no bot comment yet", writing nothing, until the bot has
posted its Code Review comment, which is the wait, never a clean review;
exit 4 means the findings could not be parsed against the header counts,
so read the archived comment itself. The command archives the bot's words
under `meta/reviews/hosted/PR-<pr>/<k>/` and takes the verdict from the
Code Review comment only. Fix each finding that is within §40 by a
sub-agent under the sub-agent rules, committed and pushed to the branch; a
finding that needs a design decision is filed in
`meta/findings/FINDINGS.md`, never fixed in silence. Push, then write the
`## Hosted review` table into the final report, one row per finding, the
finding verbatim and one disposition: `fixed in <sha>` | `dismissed:
<reason>` | `finding H-nnn filed`; commit that table with the archive
directory, push, and return the tree to `main`. Then the verdict line.

## Acceptance

- `./scripts/check` green on the pushed tip, three consecutive runs.
- Every unit commit's body lists every file it touches; U0 is `plan:`.
- `docs/HARNESS-PROBE.md` exists with a filled row for every requirement
  of §40 per harness, or `unavailable: not signed in`, and contains no
  key or token (`grep -c redacted` reported in the final report).
- `hands go` and `hands kit apply <zip>` exist and are tested as U2 says.
- A transcript under `$CLAUDE_CONFIG_DIR/projects/` is read by the monitor
  (U3's test); `task_killed` is raised once per task.
- `hands kit check` prints a WARN on a playbook with `aux.done` and no
  `aux.orphaned` rule and still passes it.
- `docs/OPERATIONS.md` exists with the inventory, the secrets table and
  the five runbooks; `scripts/capture-quota-stop.sh` exists and its test
  proves the redaction.
- `meta/FINAL-REPORT-24.md` exists with NOT PROVEN, the review-items
  table and the `## Hosted review` table.
- The PR from `mission-24` to `main` is open (`gh pr list --head mission-24
  --state open`), and the tree is on `main`.
