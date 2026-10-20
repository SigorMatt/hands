# BUILDER-29-PROMPT — hands mission 29: a `main` that takes pull requests only

Kickoff line (the only way this mission is started or resumed):

    Read the builder prompt with the highest mission number in the meta directory and execute the mission below its divider.

You are the builder for the `hands` repository. Read `DESIGN.md` (v3.28;
§45 is this mission, with §6, §8, §10, §13, §27, §31, §32, §35, §36, §39,
§43 and §44), `CLAUDE.md`, `meta/CHECKPOINT.md` (a unit in progress means
§R first), `meta/reviews/REVIEW-28.md`, `meta/findings/FINDINGS.md`,
`meta/REVIEW-PROTOCOL.md`, `docs/PR-CI-GATE.md`,
`docs/ARCHITECT-HANDBOOK.md` and `docs/PLAYBOOK.md` in full.

---

## Mission

Build what lets a project's `main` take pull requests only without
breaking hands (DESIGN §45): CI on GitHub's runner, with no test reaching
off the machine (U1); a per-project setting, `[repository] main`, a command
that waits for a pull request's checks, `hands ci-wait <pr>`, and doctor's
`main` row (U2); a kit's apply through a pull request of its own under that
setting, and a resumed apply that finds it again (U3); the engine's stop
for an apply that did not land, the owner's hold on a kit that carries the
CI, and the journal sentence for that shape (U4); the review protocol
committing to the mission's branch and merging on green checks where
`main` takes pull requests only, with the brief template, the architect and
the documents (U5); and review 28's should-fix 1 (U6). File H-079 and H-080
(U0). It does NOT create the ruleset, change this repository's setting or
touch GitHub's settings (the human and the aux do that after the install,
by docs/PR-CI-GATE.md), and it does not build the harness seam or review
25's should-fix 3 (mission 30), a local-model harness (mission 31), any M9
command or review 25's should-fix 2 (mission 32), or Claude credential
profiles (the backlog); it does not change `docs/ARCHITECT-INSTRUCTION.md`
or this repository's `PLAYBOOK.toml`, and it makes no host change. Finish
with a report whose first line the playbook can match.

## Branch (DESIGN §35)

Pull request. This mission runs on the branch `mission-29`. U0 creates it
from `main` (`git checkout main && git pull --ff-only && git checkout -b
mission-29`). Every unit commit goes to that branch and is pushed at once
(`git push -u origin mission-29` the first time). No ruleset exists during
this mission and the setting is `direct`, but nothing of the mission is
pushed to `main`. The last unit opens the pull request — `gh pr create
--base main --head mission-29 --title "mission 29: a main that takes pull
requests only" --body-file meta/FINAL-REPORT-29.md` — waits for its CI
check and the hosted review, fixes what §45 allows, and the final reply's
verdict carries the PR number. Then return the working tree to `main` (`git
checkout main && git pull --ff-only`): the next kit apply and the next
kickoff run in this tree, on `main`.

## Execution model (binding)

- You are a thin orchestrator. You plan units, write the checkpoint,
  dispatch ONE sub-agent per unit (Task tool, foreground only), verify the
  unit cheaply, record one line, move on. You run nothing longer than `git
  status`, `git log --oneline -5`, `hands hosted-review <pr>`, `uv run
  hands ci-wait <pr> --check check`, U7's one `gh api` read of the check
  runs and `./scripts/check` yourself.
- Before each unit: write `meta/CHECKPOINT.md` (unit id, intent, what
  "done" means, standing constraints). After each unit: update it and
  append one line to `meta/journal.md`.
- Every unit ends with a commit AND a push, to `mission-29`. A unit commit
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
  foreground call with an explicit timeout of 15 minutes (900000 ms), the
  command written `./scripts/check; echo "check-exit=$?"` so its end shows
  in its output. If a run is moved to the background anyway, wait with one
  foreground command that blocks until the output file shows the marker —
  `until grep -q '^check-exit=' <file>; do sleep 5; done`, with an explicit
  timeout — never a `sleep` of 25 seconds or more as a command's first
  statement, never Monitor or a background task, and never end your turn
  before the run has finished.
- `hands ci-wait` exists only in this branch's code until the install: run
  it as `uv run hands ci-wait <pr> --check check` from the repository root,
  one foreground call at a time (each returns within nine minutes), again
  while it exits 3, at most seven calls.
- Your final reply begins with exactly one of: `VERDICT: mission 29
  finished pr=<number>` | `VERDICT: mission 29 blocked <unit>` | `VERDICT:
  question <one line>`.

## Sub-agent brief (give this to every unit sub-agent, verbatim, plus the unit)

    You are implementing one unit of hands. Read, in this order: CLAUDE.md,
    DESIGN.md sections named by the unit, meta/CHECKPOINT.md, the finding or
    review item(s) named by the unit, then only the files the unit touches.
    Rules: the design is the spec — where it is silent, choose the simplest
    thing and say so in the commit body; write the failing test before the
    code and confirm it fails; ./scripts/check green three times before you
    commit, each run a foreground call with a 15-minute (900000 ms)
    timeout, written `./scripts/check; echo "check-exit=$?"`; if a run is
    moved to the background anyway, wait with one foreground command that
    blocks until its output file shows the marker — `until grep -q
    '^check-exit=' <file>; do sleep 5; done`, with an explicit timeout —
    never a `sleep` of 25 seconds or more as a command's first statement,
    never Monitor or a background task, and never end your turn before the
    run has finished; one commit, `<area>: <one line>` + a body naming the
    unit, the DESIGN sections and the item, listing every file, and stating
    only what the tests prove — never a totality claim unless a test
    enumerates the whole space; a commit that changes only tests names in
    its body each wrong change that would make them red; a commit that adds
    or deletes a non-test file names it as added or deleted; never `git add
    -A`; push to the branch `mission-29`; never edit meta/plan.md,
    meta/CHECKPOINT.md, or DESIGN.md; if the unit needs a design change,
    stop and write a memo to meta/findings/FINDINGS.md instead of
    improvising; if you cannot or will not produce what the unit asks,
    report `refused: <one line>` and stop, changing nothing; dispatch
    nothing in the background; never require a real `claude`, `gh`,
    `systemctl`, ntfy server, harness binary or `git` remote in tests (fakes
    on PATH — tests/fake_gh.py and tests/fake_claude.py — a local HTTP stub
    and local bare repositories), and never let a test send a request off
    the machine; never write to GitHub beyond pushing the branch
    `mission-29` (no ruleset, no repository setting, no API call that
    changes anything) and never push to `main`; a test that touches a project
    config or spool writes it under the test's temporary home, never the
    real `~/.hands`; a test whose outcome depends on
    `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS` sets or clears it itself; the
    only `claude` commands a unit may run are `claude --version` and
    `claude --help`; never print, commit or quote a key, a token or a
    sign-in file — write `[redacted]`; report in ≤12 lines: sha, files,
    tests added, what is NOT proven.

## §R Recovery brief

If `meta/CHECKPOINT.md` names a unit in progress and the working tree is
dirty: finish that unit under the sub-agent rules if it can pass
`./scripts/check`; otherwise `git stash push -m "wip <unit> <date>"`,
record in the checkpoint where it stopped and that a stash exists, and
leave the tree clean. Then continue from that unit. Push before taking any
new unit. If the tree is on `main` and `origin/mission-29` exists, `git
checkout mission-29 && git pull --ff-only` first. If `meta/journal.md`
alone is dirty when you start, commit it, on its own, as `journal:
consultation lines` on `mission-29` — on `main`, after U0's step has
created or checked out that branch — and push the branch, never `main`. A
sentence in square brackets beginning `[hands:` before your prompt is
hands', not the human's: do what it says first. If a `plan: decisions
<date> (owner)` commit is on the branch after the checkpoint's last update
and the checkpoint does not record its "For the builder" steps as done,
carry them out first, record them in the checkpoint, and continue. A `keep`
send that arrives after you replied `VERDICT: question` is the answer:
carry it out, continue the mission from the checkpoint, and end that reply
with one of the mission's `VERDICT:` lines, always, even when the answer
came with a file to commit first.

## Units, in order

**U0 Plan, branch and findings (`plan:` commit).** U0 is yours, not a
sub-agent's: it writes only `meta/`, among it the plan and the checkpoint a
sub-agent may not touch. `meta/plan.md`, `meta/CHECKPOINT.md`,
`meta/findings/FINDINGS.md`; the branch `mission-29` created and pushed.
File, in the ledger's form:
- H-079 — `hands: at rest` is not published again when an end of another
  role is kept after it (REVIEW-28 should-fix 1, 2026-10-20; §44 rule 4,
  `_keep` clearing the mark on a replacement only, adb061b) — "decided
  (DESIGN §45: again at the first moment nothing runs after the kept list
  changed), scheduled for U6";
- H-080 — an apply that did not land meets the playbook's rules (this
  repository's catch-all consults the driver; the templates stop with
  "Builder finished without a recognised verdict"), and under a human pause
  §44 rule 1 keeps it as the builder's end, replacing the kept end (found
  by the architect reading 1acc9e0 on 2026-10-20: `_engine_rules`,
  `_under_human_pause`) — "decided (DESIGN §45: the engine's own stop,
  never kept), scheduled for U4".
Gate: the entries exist; `git branch -r` shows `origin/mission-29`;
`./scripts/check` green (the kit changes no file a test reads but
DESIGN.md's appended §45 and version line, meta/ROADMAP.md,
meta/BACKLOG.md, KIT.md, meta/BUILDER-29-PROMPT.md and the added
docs/PR-CI-GATE.md, and the architect ran the gate green on the kit
applied to 1acc9e0; a red test at U0 in two runs out of three stops the
mission, `blocked U0`).

**U1 CI on GitHub's runner (§45 "CI").** `.github/workflows/check.yml`
(added), the tests that reach off the machine or fail in a bare run, a test
pinning the workflow's text. The workflow runs `./scripts/check` on
`pull_request` and on `push` to `main`, in one job whose id and `name:` are
both `check`, on `ubuntu-latest`, with `permissions: contents: read`, a
`concurrency` group per ref with `cancel-in-progress: true`,
`timeout-minutes: 30`, and `actions/checkout` and `astral-sh/setup-uv` each
pinned to the full 40-hexadecimal commit sha of its latest release with the
version in a trailing comment (read the sha from the action's repository
with `git ls-remote`, never invented). A test reads the file as text and
pins: the two triggers, the job id and name `check`, `./scripts/check` as
the run step, the permissions, the timeout, and every `uses:` pinned to a
40-hexadecimal sha. Then:
- keep every test on the machine: an autouse fixture in `tests/conftest.py`
  sets `HTTPS_PROXY` and `HTTP_PROXY` (and their lower-case forms) to
  `http://127.0.0.1:9` and `NO_PROXY`/`no_proxy` to `localhost,127.0.0.1`
  for every test, and a test proves that a request to another host fails at
  once under it; then find the tests that tried to leave the machine: run
  `uv run pytest -o log_cli=true --log-cli-level=WARNING` once and read its
  output for proxy and publish failures (`ProxyError`, `publish failed`,
  `ConnectError`), which a passing test otherwise hides; point each such
  test that means to publish at a local stub (a test config whose
  `ntfy_url` was left at its public default, the doctor live tests among
  them);
- run the gate the way GitHub's runner sees this repository, with nothing
  of this laptop's: `env -i HOME="$(mktemp -d)" LANG=C.UTF-8
  PATH="$(dirname "$(command -v uv)"):/usr/local/bin:/usr/bin:/bin"
  ./scripts/check; echo "check-exit=$?"` (a fresh home: no `~/.hands`, no
  git identity, no uv cache, no `claude`). A test that fails there and not
  in the usual run is made hermetic (it sets what it needs: a git identity
  by environment, a temporary home, a fake on PATH); a test that needs
  something GitHub's runner lacks is skipped by a condition that names that
  lack (never by a CI variable), and each such skip is named in the commit
  body.
Gate: the bare run green three times; the usual `./scripts/check` green
three times; the `log_cli` run shows no proxy, connect or publish failure;
the workflow test red when a `uses:` is pinned to a tag; the off-machine
test red when the fixture is removed. If pushing the
workflow file is refused for the `workflow` scope, stop the mission:
`VERDICT: question the gh token lacks the workflow scope that pushing
.github/workflows/check.yml over https needs (gh auth refresh -s
workflow)`.

**U2 The setting, `hands ci-wait` and doctor's `main` row (§45 "The
setting", "`hands ci-wait <pr> [--check <name>]…`", "doctor's `main` row";
§4, §13).** `src/hands/config.py` (`[repository] main`, `direct` by default,
any other value refused naming the two), `src/hands/forge.py` (added: the
reading of GitHub through `gh` that `ci-wait` and doctor share — the
`owner/repo` of a github.com `origin` in https or ssh form, a branch's
effective rules, the required checks' names, a pull request's checks),
`src/hands/cli.py` (`hands ci-wait <pr> [--check <name>]…`, a client
command, with its awaited names, exit codes, per-check lines and last line
exactly as §45 gives them; one call waits at most nine minutes, polling
every thirty seconds, the limit, the interval and the clock injectable for
tests), `src/hands/doctor.py` (the `main` row), `templates/config.toml`
(the key, commented, with its default), `tests/fake_gh.py` (rules, a pull
request's checks, and `gh pr checks` with no check registered answering
exactly as gh 2.89 does: exit 1, "no checks reported on the '<branch>'
branch" on stderr), tests. Tests: the setting's default, both values, and
a refused third; `ci-wait` with the rules requiring `check`: reported
`pass` → 0, `fail` → 1, `cancel` → 1, `skipping` → 0, `pending` at the
limit → 3, not yet reported at the limit → 3 (gh's "no checks reported"
read as none yet, not as an error), another check passing meanwhile not
passing it, another check failing not failing it; with no rules: `--check
check` waited for by name the same way, and no `--check` → 2 naming that
there is no check to wait for; no `gh`, not signed in, an unknown pull
request → 2 with the reason; the per-check lines and the last line of each
outcome; the doctor row ok for `direct` with no rules and for
`pull-request` with `pull_request` and `required_status_checks` (naming the
checks), a WARN for each of §45's four disagreements, and skipped (naming
why) with no `gh`, no sign-in, a non-github.com `origin` and a failed read;
`owner/repo` from `https://github.com/o/r.git`, `git@github.com:o/r.git`
and `ssh://git@github.com/o/r`. Gate: the tests; `./scripts/check` green.

**U3 The apply by the setting, and its resume (§45 "The apply (§27), by the
setting"; §6, §10, §27, §43).** `src/hands/kit.py` (`apply_prompt` and
`plan_apply` taking the shape and the zip's sha256; the `direct` prompt's
added sentence; `kit check` printing the sha256 — of the zip, or of
`build_zip`'s bytes for a directory kit — and the configured shape's prompt,
saying which), `src/hands/daemon.py`, `src/hands/api.py` and
`src/hands/phone.py` (the configured shape and the zip's sha256 wherever an
apply's prompt is built: the phone's `kit`, `hands kit apply`, `hands kit
file`), `src/hands/playbook.py` and `src/hands/limits.py` (a resume of an
apply — a `resume` rule on `builder.orphaned` or `builder.failed`, and §6's
limit resume — re-sends the apply's own prompt, never `resume_line`, the
apply found by §43's chain walk; §32's test of an apply the engine approved
asked of the chain's first job, so the engine's kickoff follows a resumed
apply that lands), the handbook's §3 quotation of the `direct` prompt and
every test that pins it, tests. Tests: the `direct` prompt with exactly the
added sentence and otherwise byte for byte as it was; the `pull-request`
prompt word for word as §45 gives it, for a kit named `a b.c.zip` (branch
`kit/a-b-c-<12 hex>`, subject `merge: kit a-b-c (PR #<pr>)`), for a stem
over 40 characters (cut), and for the same name with other bytes (another
branch); under a role-mode autonomous playbook, an engine-approved apply
orphaned, resumed and landing followed by the engine's kickoff; the phone's `kit`, `hands kit apply` and
the architect's `hands kit file` each filing that prompt under
`pull-request`; `kit check` printing the sha256 and the `direct` prompt
without a configuration, the configured one with it, naming the shape, and
for a directory kit the sha256 `hands kit file` files; an orphaned, a failed
and a limited apply each resumed with its own prompt under a config that
sets `resume_line`; a limited kickoff still resumed with `resume_line` (as
today). Gate: the tests; `./scripts/check` green.

**U4 An apply that did not land, the CI's hold, the journal sentence (§45
"An apply that did not land (H-080)", "A kit that carries the CI is the
owner's", "The journal under a `main` that takes pull requests only"; §19,
§31, §36, §39, §43, §44).** `src/hands/playbook.py` (the engine's decision
on an apply's `builder.done` that did not land, before any playbook rule,
an apply counted by §43's chain walk; over an unpaused pipeline a stop, over
a paused one one publication, never kept; the journal sentence's
`pull-request` wording and §36's reader recognising both), `src/hands/spool.py`
and `src/hands/kit.py` (a role-filed kit carrying an entry under `.github/`
or `scripts/check` held with §45's reason, §43's reason when it carries the
playbook too; `kit check`'s `WARN ci:` line), the handbook's §19
(the row for the apply that did not land, as §45's "Documentation" gives
it, and the hold row naming the CI's reason) with
`tests/test_operator_table.py`'s pins, `meta/findings/FINDINGS.md` (H-080
resolved), tests. Tests: under this repository's phone-mode `PLAYBOOK.toml`
an apply ending `VERDICT: kit not applied pr=12 a check failed` stops with
§45's reason and consults no driver; under a role-mode autonomous playbook
the same end stops and sends no kickoff; an apply ending with no `VERDICT:`
line stops naming it; a resumed apply's failed end stops the same way; a
landed apply decided as today (the `kit applied` notify; the engine's
kickoff); a `hands send` replying `VERDICT: kit not applied` (not an apply)
meeting the playbook's rules only; under a human pause an apply that did
not land published once as a stop under the pause, the pause and the kept
builder end unchanged; over a pipeline stopped by a rule, an apply that did
not land published once and the stop's reason unchanged; a role-filed kit
carrying `.github/workflows/x.yml` (and `.GitHub/x`, and `scripts/check`)
held with the CI's reason and warned by `kit check`, one carrying both the
playbook and `.github/` held with the playbook's reason and warned on both,
an ordinary kit unchanged; the journal
sentence's `pull-request` wording word for word, the `direct` wording
unchanged, both stripped where §36 strips hands' sentences. Gate: the
tests (the operator table's every-stop test green with the new row);
`./scripts/check` green.

**U5 The review protocol, the brief template, the architect and the
documents (§45 "The review", "The brief template and the architect",
"docs/PR-CI-GATE.md", "Documentation").** `meta/REVIEW-PROTOCOL.md` and
`templates/REVIEW-PROTOCOL.md` (one text, the template with `<owner>/<repo>`
and the brief's timeout as today), `templates/BUILDER-N-PROMPT.md`,
`architect/CLAUDE.md` (rules 1 and 3), `docs/ARCHITECT-HANDBOOK.md` (§3, §9,
§10, §12, §18, §19 beyond U4's rows), `docs/INTEGRATION.md`,
`docs/OPERATIONS.md`, `docs/PLAYBOOK.md`, `CLAUDE.md`, tests (the docs and
handbook pins). The protocol says what §45's "The review" says: its first
step reads `main`'s rules once (`gh api
repos/<owner>/<repo>/rules/branches/main --jq '[.[].type] | join(" ")'`,
this repository's copy with `SigorMatt/hands`), with the retry and the
failure's blocker; then, under `pull_request`: the Direct blocker, the
no-pull-request case committed nowhere, the wait for the checks at the
reviewed tip and its blocker and `## Notes` line, the review and the
archive committed to the branch, the merge's wait and the `not merged`
blocker, the return to `main` with blockers, and the journal's lines
carried over before its `git checkout <branch>`; and, in every shape, the
`.github/` and `scripts/check` blocker among the forbidden edits. The
template's Direct paragraph, its Branch section's closer step (the
journal's lines carried over before `git checkout <branch>`), its §R's
journal rule and its last unit's sentence say what §45 says.
`architect/CLAUDE.md` rule 1 says where a review with blockers is on a
repository whose `main` takes pull requests only (`git show
origin/<branch>:meta/reviews/REVIEW-N.md`, the form its guard allows), and
rule 3 that a kit there keeps its gate green, never rewords pinned design
text, and carries no `.github/` file and no `scripts/check` unless the
human asked. The handbook, the other documents and `CLAUDE.md` say what
§45's "Documentation" lists; the review-with-blockers row of §19 gives
both `git show` forms. `docs/PR-CI-GATE.md` is the kit's, as it is: point to it, do
not change it. Gate: the tests; `./scripts/check` green.

**U6 At rest after the kept list changed (§45 "Review 28's should-fix
items" 1; §44 rule 4; H-079).** `src/hands/playbook.py` (and
`src/hands/daemon.py` if the moment is decided there), the documents that
quote rule 4's "again" (the handbook's §19 `at rest` row, docs/PLAYBOOK.md,
docs/OPERATIONS.md), `meta/findings/FINDINGS.md` (H-079 resolved), tests.
Tests: `at rest` published with the kept builder end; then a laptop send to
the aux under the pause whose end is kept publishes it again, naming both
ends, once the aux job has ended; a replacement after the publication
publishes it again (as today); no publication while a job runs, and the
next moment nothing runs publishes the changed list; a restart with no end
kept after the mark publishes nothing; a restart with an end kept after
the mark and never published publishes it. Gate: the tests;
`./scripts/check` green.

**U7 Final report, the pull request, its checks and the hosted review's
findings.** `meta/FINAL-REPORT-29.md` (drafted under `meta/drafts/`, moved
in by this commit): what changed (sha per unit), what tests prove, NOT
PROVEN (mandatory: no ruleset exists, so no apply has merged through a
pull request under the gate and `hands ci-wait` has never read required
checks from real rules; doctor's `main` row has read only this repository's
rules with none set), and the `## Review items` section: review 28's
should-fix 1 closed by U6, should-fix 2 answered by §45 (the reading is
the design, nothing changed), H-079 closed by U6, H-080 closed by U4. Then
open the pull request (see Branch). Wait for its CI check: `uv run hands
ci-wait <pr> --check check; echo "ci-wait-exit=$?"`, one foreground call
at a time, again while it exits 3, at most seven calls. On a failed check,
read its log (`gh run view <run> --log-failed`), fix the cause within §45
by a sub-agent under the sub-agent rules, committed and pushed to the
branch, and wait again; a failure that needs a design decision is filed,
never fixed in silence. Then wait up to ten minutes for the bot, the hosted
reviewer, in one-minute foreground steps: `hands hosted-review <pr>` exits
3 with "no bot comment yet", writing nothing, until the bot has posted its
Code Review comment, which is the wait, never a clean review; exit 4 means
the findings could not be parsed against the header counts, so read the
archived comment itself. The command archives the bot's words under
`meta/reviews/hosted/PR-<pr>/<k>/` and takes the verdict from the Code
Review comment only. Fix each finding that is within §45 by a sub-agent
under the sub-agent rules, committed and pushed to the branch; a finding
that needs a design decision is filed in `meta/findings/FINDINGS.md`, never
fixed in silence. After the last fix, wait for the CI check again as above
until it exits 0. Then write into the final report the `## Hosted review`
table, one row per finding, the finding verbatim and one disposition:
`fixed in <sha>` | `dismissed: <reason>` | `finding H-nnn filed`, and a
`## CI` section naming the check as GitHub reported it at the last code
commit — its name, the app that reported it and the app's id, its
conclusion, the run's link, read with `gh api
repos/SigorMatt/hands/commits/<sha>/check-runs --jq '.check_runs[] |
[.name, .app.slug, .app.id, .conclusion, .html_url] | @tsv'` (a read) — the
name and app docs/PR-CI-GATE.md will require; commit them with the archive
directory, push, and wait for the CI check once more on that last commit as
above. Return the tree to `main`. Then the verdict line, and right after it
the last `ci-wait` line. If that last wait does not end in exit 0, the
verdict is `VERDICT: mission 29 blocked U7`, with that line.

## Acceptance

- `./scripts/check` green on the pushed tip, three consecutive runs, and
  the bare-environment run (U1) green on it once.
- The pull request's `check` check passed at the pushed tip: the final
  reply's last `ci-wait` line reads `ci-wait: passed`; the final report's
  `## CI` section names the check and its app.
- Every unit commit's body lists every file it touches; U0 is `plan:`.
- H-079 and H-080 are filed and resolved.
- No test sends a request off the machine (U1's proxied run).
- `[repository] main` loads, defaults to `direct` and refuses a third value;
  `hands ci-wait` waits for the required or named checks and exits 0, 1, 3
  and 2 as §45 gives them; doctor's `main` row is ok, warns or is skipped as
  §45 gives it (U2's tests).
- Under `pull-request` every apply's prompt is §45's word for word, under
  `direct` it has exactly the added sentence; a resumed apply re-sends its
  own prompt (U3's tests).
- An apply that did not land stops, or is published once over a paused
  pipeline, is never kept, and consults no one; a role-filed kit carrying
  `.github/` is held for the human; the journal sentence has its
  `pull-request` wording (U4's tests).
- Both review protocols, the brief template, `architect/CLAUDE.md`, the
  handbook and the documents say what §45 says (U5's tests).
- `hands: at rest` is published again after the kept list changed (U6's
  tests).
- `meta/FINAL-REPORT-29.md` exists with NOT PROVEN, the review-items
  section, the `## Hosted review` table and the `## CI` section.
- The PR from `mission-29` to `main` is open (`gh pr list --head mission-29
  --state open`), and the tree is on `main`.
