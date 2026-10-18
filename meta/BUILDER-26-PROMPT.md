# BUILDER-26-PROMPT — hands mission 26: the project separation, a project operated from its own chat

Kickoff line (the only way this mission is started or resumed):

    Read the builder prompt with the highest mission number in the meta directory and execute the mission below its divider.

You are the builder for the `hands` repository. Read `DESIGN.md` (v3.25;
§42 is this mission, with §27, §31, §33, §36 and §38), `CLAUDE.md`,
`meta/CHECKPOINT.md` (a unit in progress means §R first),
`meta/reviews/REVIEW-25.md`, `docs/ARCHITECT-HANDBOOK.md` and
`docs/OPERATIONS.md` in full.

---

## Mission

Make a project operable from its own chat and the phone, without the hands
Project chat (§42): `consult` from the phone and the laptop in place of the
aux recital (U1); `digest` (U2); the decisions-kit route and the owner file
read on a resume (U3); and the handbook's operator table, the HF report's
form, the second onboarding shape and who operates a project, with the
Project instruction's new opening, four reworded rules and rule 15 (U4).
File H-070..H-072, carried from another project's ledger, and close H-072
(U0, U4). It does NOT build the harness seam, review 25's should-fix 1
and 3, H-070 or H-071 (mission 27), a local-model harness (mission
28), any M9 command or review 25's should-fix 2 (mission 29), or Claude
credential profiles and the
`builder.limited` rule (the backlog), and it makes no host change. Finish with a report whose first line the
playbook can match.

## Branch (DESIGN §35)

Pull request. This mission runs on the branch `mission-26`. U0 creates it
from `main` (`git checkout main && git pull --ff-only && git checkout -b
mission-26`). Every unit commit goes to that branch and is pushed at once
(`git push -u origin mission-26` the first time). The last unit opens the
pull request — `gh pr create --base main --head mission-26 --title "mission
26: the project separation" --body-file meta/FINAL-REPORT-26.md` — waits
for the hosted review, fixes what §42 allows, and the final reply's verdict
carries the PR number. Then return the working tree to `main` (`git
checkout main && git pull --ff-only`): the next kit apply and the next
kickoff run in this tree, on `main`.

## Execution model (binding)

- You are a thin orchestrator. You plan units, write the checkpoint,
  dispatch ONE sub-agent per unit (Task tool, foreground only), verify the
  unit cheaply, record one line, move on. You run nothing longer than `git
  status`, `git log --oneline -5`, `hands hosted-review <pr>` and
  `./scripts/check` yourself.
- Before each unit: write `meta/CHECKPOINT.md` (unit id, intent, what
  "done" means, standing constraints). After each unit: update it and
  append one line to `meta/journal.md`.
- Every unit ends with a commit AND a push, to `mission-26`. A unit commit
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
  foreground call with an explicit timeout of 15 minutes (900000 ms).
- Your final reply begins with exactly one of: `VERDICT: mission 26
  finished pr=<number>` | `VERDICT: mission 26 blocked <unit>` | `VERDICT:
  question <one line>`.

## Sub-agent brief (give this to every unit sub-agent, verbatim, plus the unit)

    You are implementing one unit of hands. Read, in this order: CLAUDE.md,
    DESIGN.md sections named by the unit, meta/CHECKPOINT.md, the finding or
    review item(s) named by the unit, then only the files the unit touches.
    Rules: the design is the spec — where it is silent, choose the simplest
    thing and say so in the commit body; write the failing test before the
    code and confirm it fails; ./scripts/check green three times before you
    commit, each run a foreground call with a 15-minute (900000 ms)
    timeout; one commit, `<area>: <one line>` + a body naming the unit, the
    DESIGN sections and the item, listing every file, and stating only what
    the tests prove — never a totality claim unless a test enumerates the
    whole space; a commit that changes only tests names in its body each
    wrong change that would make them red; a commit that adds or deletes a
    non-test file names it as added or deleted; never `git add -A`; push to
    the branch `mission-26`; never edit meta/plan.md, meta/CHECKPOINT.md,
    or DESIGN.md; if the unit needs a design change, stop and write a memo
    to meta/findings/FINDINGS.md instead of improvising; if you cannot or
    will not produce what the unit asks, report `refused: <one line>` and
    stop, changing nothing; dispatch nothing in the background; never
    require a real `claude`, `gh`, `systemctl`, ntfy server, harness binary
    or `git` remote in tests (fakes on PATH, a local HTTP stub and local
    bare repositories, as tests/fake_claude.py is); a test that touches a
    project config or spool writes it under the test's temporary home,
    never the real `~/.hands`; the only `claude` commands a unit may run
    are `claude --version` and `claude --help` — anything else about the
    installed CLI is read from its package's files; never print, commit or
    quote a key, a token or a sign-in file — write `[redacted]`; report in
    ≤12 lines: sha, files, tests added, what is NOT proven.

## §R Recovery brief

If `meta/CHECKPOINT.md` names a unit in progress and the working tree is
dirty: finish that unit under the sub-agent rules if it can pass
`./scripts/check`; otherwise `git stash push -m "wip <unit> <date>"`,
record in the checkpoint where it stopped and that a stash exists, and
leave the tree clean. Then continue from that unit. Push before taking any
new unit. If the tree is on `main` and `origin/mission-26` exists, `git
checkout mission-26 && git pull --ff-only` first. If `meta/journal.md`
alone is dirty when you start, commit it first as `journal: consultation
lines` and push. If a `plan: decisions <date> (owner)` commit is on the
branch after the checkpoint's last update and the checkpoint does not
record its "For the builder" steps as done, carry them out first, record
them in the checkpoint, and continue. A `keep` send that arrives after you
replied `VERDICT: question` is the answer: carry it out, continue the
mission from the checkpoint, and end that reply with one of the mission's
`VERDICT:` lines, always, even when the answer came with a file to commit
first.

## Units, in order

**U0 Plan, branch and findings (`plan:` commit).** `meta/plan.md`,
`meta/CHECKPOINT.md`, `meta/findings/FINDINGS.md`; the branch `mission-26`
created and pushed. File, each with the evidence §42 gives: H-070
per-commit reports run past the review protocol's twelve lines (from
another project's ledger, its HF-013, its review 18, 2026-10-17; evidence
only: the project's name, the date, the finding id) — "decided (DESIGN
§42), scheduled for mission 27"; H-071 the architect role's guard refused
every command holding `#`, `{` or a backslash, and the options `ls -R`,
`git ls-tree --name-only`, `git status --short` and `git log
--date=<format>` (its HF-014, its consultations 22 and 23) — "decided
(DESIGN §42), scheduled for mission 27"; H-072 a gate run on a shared
machine took 1281 s, past a brief's 20-minute timeout and hands' 15-minute
default (its HF-006, the 2026-10-17 update) — "decided (DESIGN §42),
closed by U4". Gate: the entries exist; `git branch -r` shows
`origin/mission-26`.

**U1 `consult` from the phone and the laptop (§42 "`consult` from the
phone and the laptop"; §31, §33, §38, H-058).** `src/hands/phone.py` (the
command; the fetch and first-free naming taking the extension from the
name rule), `src/hands/api.py`, `src/hands/playbook.py` (the engine
starting the consultation by its `consult` action's path, the prompt's
section in place of a review, `consult.sent`), `src/hands/daemon.py` if
dispatch needs it, `src/hands/cli.py`, `architect/CLAUDE.md`,
`docs/ARCHITECT-HANDBOOK.md` §16, `README.md`, tests (the guard's in
`tests/test_bash_guard.py`). `consult <secret>
<text>` with an optional `.md` attachment under §42's name and size rules,
fetched into `kit_dir` and read as UTF-8; the prompt as §42 says, its first
line exactly `hands consult: consult on job none (role human)`, the reason
under the heading `The human's reason for this consultation`, refused over
`MAX_PROMPT_BYTES`. The engine starts it, in a branch of its `consult`
action with no event job, the architect prompt builder factored to take
either a job or the human's reason: an architect job of origin `playbook`,
never `phone` (a phone-origin architect job is a `reply`,
`is_architect_reply`); no §8 hold; the command un-pauses a stopped pipeline
after its refusals pass and before the engine starts the job; counted
against `max_architect_consults`; `consult.sent` with every field §42
lists (`about: null`, `role: "human"`, `consulted: "architect"`, `event:
"consult"`, `verdict: null`, `rule: null`, `consults`, `max_consults`,
`requested_by`, `head`, `reason_sha256`), never the reason; `consult.done`
with `about: null` and `role: "human"`, and the journal line §42 gives;
every refusal §42 lists, published titled `consult`. `hands
consult [--file <path>] [<text>]` through the socket, `requested_by: cli`,
the same refusals, the file read under the same rules. Neither guarded
role's guard admits `hands consult` (a guard test pins it).
`architect/CLAUDE.md` gains the rule on a human-started consultation and
its rule 13's last sentence names routes 4 and 5 of §42. The handbook's
§16 describes `consult` and retires the recital. Tests: a phone consult in
role mode starts one architect job of origin `playbook` whose prompt holds
the reason and no review section; an attached `.md` is appended and lands
in `kit_dir` under its `.md` name; each refusal; the budget counts it and
refuses at the limit; the pipeline un-pauses; the engine reads its `next
kit` verdict and `hands kit file` accepts its kit as any consultation's;
`consult.sent` carries each field §42 lists; `consult.done` and the
journal line read `consult by the human`, never `job none`; the architect
guard with `HANDS_CONSULT_ROLE=human` still refuses every send and admits
its read set; a review's
consultation is unchanged (its prompt and events match main's); the cli
twin; the guard refusal. Gate: the
tests; `./scripts/check` green.

**U2 `digest` (§42 "`digest`").** A new `src/hands/digest.py` (or the CLI
module the code's layout dictates), `src/hands/cli.py`,
`src/hands/phone.py`, `README.md`, tests. `hands digest` prints one line
per loadable project config in name order with the fields §42 lists, and a
line naming a config that did not load by its file only, never with the
loader's message; it needs no daemon (a down daemon reads `down`). `digest
<secret>` on any project's `cmd_topic` publishes the same lines titled
`digest` on that project's `ntfy_topic`. Every line is redacted of every
loadable project's `cmd_secret` and `ntfy_token` before any field is cut. Neither guarded role's guard admits `hands digest` (a
guard test pins it). Tests: two fake projects with spools, one paused with
a stop, one running a builder; a config that does not load whose bad value
is a secret-shaped string, absent from the output; a down daemon; a planted
secret straddling the 100-character cut of a stop reason is absent in
full; the phone publish. Gate: the tests; `./scripts/check` green.

**U3 The decisions kit and the owner file on a resume (§42 "The decisions
kit", "The newest owner file, on a resume"; route 4).**
`src/hands/kit.py`, `src/hands/api.py`, `templates/BUILDER-N-PROMPT.md`,
`docs/ARCHITECT-HANDBOOK.md` (§3, §4, §11), tests. `hands kit check`
recognises a decisions kit as §42 defines it and passes it 6 of 6 with the
plan-only apply prompt, each of `brief`, `verdicts` and `wording` saying
why it applies no brief; a kit with any other entry beside the owner
files is judged unchanged; `hands kit apply` takes a decisions kit the
same way; `hands kit file` refuses one with a reason (`src/hands/api.py`
where `kit_file` checks). The brief template's §R gains the owner-file
sentence as this brief's §R has it. Tests: a decisions kit (one owner file
and a `KIT.md` reading `plan: decisions <date> (owner)`) passes `kit check`
6 of 6 and its apply prompt names that file and that commit message; the
same kit built with directory entries (as `zip -r` writes them) passes
too; it is not a decisions kit, and is judged as main judges it, when it
adds any other file (a `README.md`, a `PLAYBOOK.toml`), lacks `KIT.md`, has
a `KIT.md` with another first line, holds `meta/decisions/a/b-owner.md` or
`meta/decisions/-owner.md`, or is `KIT.md` alone; `hands kit apply` of a
decisions kit files the held apply; the phone's `kit` path files the same
apply; `hands kit file` refuses a decisions kit; the sentence-pinning test
covers the new §R sentence; a kit from the templates passes `kit check` 6
of 6. Gate: the tests; `./scripts/check` green.

**U4 The handbook, the instruction and the runbooks (§42 "Who operates a
project", "An HF report", "The operator table", "The second onboarding
shape", "Documentation"; H-072).** `docs/ARCHITECT-HANDBOOK.md` (§10's
builder-question row, §13, §14, §18, a new §19),
`docs/ARCHITECT-INSTRUCTION.md`, `docs/OPERATIONS.md`,
`docs/INTEGRATION.md`, `README.md`, tests. §19, the operator table, is
written from the code and the templates at this commit: one row per `stop`
and `notify` message of `templates/PLAYBOOK-missions.toml` and
`templates/PLAYBOOK-runs.toml`, and one per stop and published line the
engine, the limit manager and the daemon write themselves, each with the
four columns and one of §42's eight routes; a row for `digest`'s fields;
and the HF report's form as §42 gives it. §13 gains the second onboarding
shape, who operates a project, and the hands Project's playbook check; §18
names `consult` and `digest`; §10's builder-question row and §14 give route
4 with `answer` as the shorter route after `VERDICT: question`, and name no
driver. `docs/ARCHITECT-INSTRUCTION.md`: the opening
paragraph replaced, rules 3, 9, 12 and 14 reworded, and rule 15 added,
exactly as §42 gives them (the blocks' indentation matched to the file's).
docs/OPERATIONS.md: the no-phone table's `consult` and `digest` rows.
docs/INTEGRATION.md: H-072's raise of the two timeouts, with the CLI's own
ceiling if it has one (read from the installed package's files; say how
found). Tests: every template playbook message appears in §19's table
(placeholders as the table writes them); the table's columns; the HF
report's form; the instruction's opening, the four reworded rules and rule
15 pinned word for word to §42's text; a real `hands project add` with
fakes (as the H-052 tests run it) prints the instruction with rule 15; the
no-phone rows; the H-072 sentence. Gate: the tests; `./scripts/check`
green.

**U5 Final report, the pull request and the hosted review's findings.**
`meta/FINAL-REPORT-26.md` (drafted under `meta/drafts/`, moved in by this
commit): what changed (sha per unit), what tests prove, NOT PROVEN
(mandatory: no real phone sent `consult` or `digest`, no real decisions kit
was applied, and no project chat has yet answered a notification from the
operator table), and the `## Review items` section saying that review 25's
should-fix 1 and 3 are carried to mission 27 and 2 to mission 29 by DESIGN
§42. Then open
the pull request (see Branch) and wait up to ten minutes for the bot, the
hosted reviewer, in one-minute foreground steps: `hands hosted-review <pr>`
exits 3 with "no bot comment yet", writing nothing, until the bot has
posted its Code Review comment, which is the wait, never a clean review;
exit 4 means the findings could not be parsed against the header counts,
so read the archived comment itself. The command archives the bot's words
under `meta/reviews/hosted/PR-<pr>/<k>/` and takes the verdict from the
Code Review comment only. Fix each finding that is within §42 by a
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
- `consult <secret> <text>` and `hands consult` have the engine start one
  architect consultation of origin `playbook`, counted against the budget,
  refused as §42 lists (U1's tests).
- `hands digest` and `digest <secret>` print and publish one redacted line
  per project (U2's tests).
- `hands kit check` passes a decisions kit 6 of 6 and `hands kit apply` and
  the phone's `kit` path file its apply; the brief template's §R carries
  the owner-file sentence (U3's tests).
- `docs/ARCHITECT-INSTRUCTION.md`'s opening paragraph, rules 3, 9, 12 and
  14 and rule 15 are §42's text word for word; the handbook has §19's
  operator table with every template playbook message in it and the HF
  report's form.
- `meta/FINAL-REPORT-26.md` exists with NOT PROVEN, the review-items
  section and the `## Hosted review` table.
- The PR from `mission-26` to `main` is open (`gh pr list --head mission-26
  --state open`), and the tree is on `main`.
