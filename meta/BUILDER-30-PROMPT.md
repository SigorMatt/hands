# BUILDER-30-PROMPT — hands mission 30: the gate's follow-up before the switch

Kickoff line (the only way this mission is started or resumed):

    Read the builder prompt with the highest mission number in the meta directory and execute the mission below its divider.

You are the builder for the `hands` repository. Read `DESIGN.md` (v3.29;
§46 is this mission, with §43, §45 and §35), `CLAUDE.md`,
`meta/CHECKPOINT.md` (a unit in progress means §R first),
`meta/reviews/REVIEW-29.md`, `meta/findings/FINDINGS.md` (H-081, H-082,
H-083), `meta/REVIEW-PROTOCOL.md`, `templates/REVIEW-PROTOCOL.md` and
`docs/ARCHITECT-HANDBOOK.md` in full.

---

## Mission

Close what stops this repository's switch to a `main` that takes pull
requests only (DESIGN §46): the `pull-request` apply prompt's case (b) no
longer matching `main` (H-082) and the setting's refusal naming its two
values (review 29's should-fix 3) (U1); the engine approving plan files
only, which replaces §45's CI hold (H-083) (U2); the review merging the
head it reviewed (H-081), its file on the failure paths committed to the
mission's branch when it exists (H-084), the tree returned to `main`
after them (H-085), and a confirmed bug in the pull request's own code
blocking its merge (the human's decision of 2026-10-21) (U3). File H-084 and H-085 and set the three open
findings' status (U0). It does NOT switch this repository's setting, create
the ruleset or touch GitHub's settings (the human and the aux do that after
the install, by docs/PR-CI-GATE.md §5), and it does not build the harness
seam or review 25's should-fix 3 (mission 31), a local-model harness
(mission 32), any M9 command or review 25's should-fix 2 (mission 33), or
Claude credential profiles (the backlog); it does not change
`docs/ARCHITECT-INSTRUCTION.md` or this repository's `PLAYBOOK.toml`, and it
makes no host change. Finish with a report whose first line the playbook
can match.

## Branch (DESIGN §35)

Pull request. This mission runs on the branch `mission-30`. U0 creates it
from `main` (`git checkout main && git pull --ff-only && git checkout -b
mission-30`). Every unit commit goes to that branch and is pushed at once
(`git push -u origin mission-30` the first time). This repository's setting
is still `direct` and no ruleset exists, but nothing of the mission is
pushed to `main`. The last unit opens the pull request — `gh pr create
--base main --head mission-30 --title "mission 30: the gate's follow-up
before the switch" --body-file meta/FINAL-REPORT-30.md` — waits for its CI
check and the hosted review, fixes what §46 allows, and the final reply's
verdict carries the PR number. Then return the working tree to `main` (`git
checkout main && git pull --ff-only`): the next kit apply and the next
kickoff run in this tree, on `main`.

## Execution model (binding)

- You are a thin orchestrator. You plan units, write the checkpoint,
  dispatch ONE sub-agent per unit (Task tool, foreground only), verify the
  unit cheaply, record one line, move on. You run nothing longer than `git
  status`, `git log --oneline -5`, `hands hosted-review <pr>`, `uv run
  hands ci-wait <pr> --check check`, U4's one `gh api` read of the check
  runs and `./scripts/check` yourself.
- Before each unit: write `meta/CHECKPOINT.md` (unit id, intent, what
  "done" means, standing constraints). After each unit: update it and
  append one line to `meta/journal.md`.
- Every unit ends with a commit AND a push, to `mission-30`. A unit commit
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
- Run `hands ci-wait` from this branch's code: `uv run hands ci-wait <pr>
  --check check` from the repository root, one foreground call at a time
  (each returns within nine minutes), again while it exits 3, at most seven
  calls.
- Your final reply begins with exactly one of: `VERDICT: mission 30
  finished pr=<number>` | `VERDICT: mission 30 blocked <unit>` | `VERDICT:
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
    -A`; push to the branch `mission-30`; never edit meta/plan.md,
    meta/CHECKPOINT.md, or DESIGN.md; if the unit needs a design change,
    stop and write a memo to meta/findings/FINDINGS.md instead of
    improvising; if you cannot or will not produce what the unit asks,
    report `refused: <one line>` and stop, changing nothing; dispatch
    nothing in the background; never require a real `claude`, `gh`,
    `systemctl`, ntfy server, harness binary or `git` remote in tests (fakes
    on PATH — tests/fake_gh.py and tests/fake_claude.py — a local HTTP stub
    and local bare repositories), and never let a test send a request off
    the machine (the suite's proxy fixture stays); never write to GitHub
    beyond pushing the branch `mission-30` (no ruleset, no repository
    setting, no API call that changes anything) and never push to `main`; a
    test that touches a project config or spool writes it under the test's
    temporary home, never the real `~/.hands`; a test whose outcome depends
    on `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS` sets or clears it itself; the
    only `claude` commands a unit may run are `claude --version` and `claude
    --help`; never print, commit or quote a key, a token or a sign-in file —
    write `[redacted]`; report in ≤12 lines: sha, files, tests added, what
    is NOT proven.

## §R Recovery brief

If `meta/CHECKPOINT.md` names a unit in progress and the working tree is
dirty: finish that unit under the sub-agent rules if it can pass
`./scripts/check`; otherwise `git stash push -m "wip <unit> <date>"`,
record in the checkpoint where it stopped and that a stash exists, and
leave the tree clean. Then continue from that unit. Push before taking any
new unit. If the tree is on `main` and `origin/mission-30` exists, `git
checkout mission-30 && git pull --ff-only` first. If `meta/journal.md`
alone is dirty when you start, commit it, on its own, as `journal:
consultation lines` on `mission-30` — on `main`, after U0's step has
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
`meta/findings/FINDINGS.md`; the branch `mission-30` created and pushed.
Set the status of H-082 to "decided (DESIGN §46: case (b) begins `On a
branch that is neither main nor a kit/ one`), scheduled for U1", of H-083
to "decided (DESIGN §46: the engine approves plan files only, replacing
§45's CI hold; the human, 2026-10-21), scheduled for U2", and of H-081 to
"decided (DESIGN §46: the moved-branch blocker and `--match-head-commit`,
in every review of a pull request), scheduled for U3". File, in the
ledger's form:
- H-084 — under `pull_request` the review of a missing pull request, and of
  a Direct brief, is committed nowhere while the review of a failed rules
  read goes to the branch, and the architect reads a review with blockers
  from the branch (REVIEW-29 should-fix 2, from PR #9's hosted finding 5,
  2026-10-21; meta/REVIEW-PROTOCOL.md at 4d32d35, "`main`'s rules" and "The
  commits under review") — "decided (DESIGN §46: a failed rules read's
  review, and under `pull_request` a missing pull request's, to the brief's
  branch when it exists on origin, never `main`, else nowhere; a Direct
  brief's under `pull_request` nowhere), scheduled for U3";
- H-085 — nothing returns the tree to `main` after the review commits to
  the branch on a failure path (REVIEW-29 should-fix 4, 2026-10-21; both
  protocols at 4d32d35) — "decided (DESIGN §46: a review that checked out
  the branch ends on `main`), scheduled for U3".
Record review 29's should-fix 3 in the plan as U1's. Gate: the entries
exist; `git branch -r` shows `origin/mission-30`; `./scripts/check` green
(the kit changes no file a test reads but DESIGN.md's appended §46 and
version line, meta/ROADMAP.md, meta/BACKLOG.md, KIT.md and
meta/BUILDER-30-PROMPT.md, and the architect ran the gate green on the kit
applied to 4d32d35; a red test at U0 in two runs out of three stops the
mission, `blocked U0`).

**U1 Case (b), and the setting's refusal (§46 "H-082", review 29's
should-fix 3; §45 "The apply (§27), by the setting", "The setting").**
`src/hands/kit.py` (`PULL_REQUEST_APPLY`: case (b) begins `(b) On a branch
that is neither \`main\` nor a \`kit/\` one, that is on \`origin\`` — the
backticks round `main`, `kit/` and `origin` as the prompt's other names
have them — the rest unchanged), `src/hands/config.py` (`[repository]
main` refused naming the two values whatever the value's type: `[repository]
main must be "direct" or "pull-request", got <the value>`), the handbook's
§3 quotation of the prompt and every test that pins it,
`meta/findings/FINDINGS.md` (H-082 resolved), tests. Tests: the prompt word
for word with the new case (b), its phrase "neither `main` nor a `kit/`
one" pinned; `main = true`, `main = 1` and `main = "squash"` each refused
with the message naming both values. Gate: the tests; `./scripts/check`
green.

**U2 The engine approves plan files only (§46 "H-083"; §31, §32, §43,
§45).** `src/hands/spool.py` (`is_plan_file(entry, named)`, the one test
§46 gives, in exact case, and `Spool.stored_kit_non_plan(kit_id, name,
named)`, the stored kit's file entries that fail it, read as §43's are;
`carries_ci` and `stored_kit_ci` removed), `src/hands/playbook.py`
(`_release_kit` approves only a kit whose file entries are all plan files
and that carries no playbook, `named` being the paths the playbook in
force's rule prompts name; `plan_hold_reason(name, path)`, §46's reason word
for word, with §43's taking precedence when the kit carries the playbook;
`ci_hold_reason` removed), `src/hands/daemon.py` if the reason is decided
there, `src/hands/kit.py` (`hands kit check`'s `WARN owner:` line naming
every file entry that is not a plan file and does not carry the playbook,
under the condition of its `WARN playbook:` line, in place of `WARN ci:`;
the `--json` key `ci_warnings` renamed `owner_warnings`),
`architect/CLAUDE.md` (rule 3: the parenthesis and the `PLAYBOOK.toml`
sentence replaced by §46's sentence word for word, the `.github/` clause
dropped, the rest kept; rule 8's list gaining §46's item; and the test that
pins the dropped clause moved to the new sentence), `named` computed as
§46 says (`kit.named_paths` over the `send` rules' prompts of the
repository's playbook in force, placeholders ignored),
the handbook's §3, §12 and §19 (the hold row's reason) with
`tests/test_operator_table.py`'s pins, docs/PLAYBOOK.md, docs/INTEGRATION.md,
`templates/PLAYBOOK-missions.toml` and `templates/PLAYBOOK-runs.toml` (their
comments), as §46's "Documentation" lists, `meta/findings/FINDINGS.md`
(H-083 resolved), tests. Tests, on a role-mode autonomous playbook: a kit
of `KIT.md`, `DESIGN.md`, `meta/BUILDER-31-PROMPT.md` and
`meta/decisions/x-owner.md` approved by the engine and followed by its
kickoff (as today); `WORKPLAN.md` and `decisions-2026-10-21.md` at the root
approved; kits each carrying one of `docs/x.md`, `.github/workflows/x.yml`,
`scripts/check`, `pyproject.toml`, `uv.lock`, `tests/conftest.py`,
`src/x.py`, `SPEC.md`, `meta/conftest.py`, `meta/REVIEW-PROTOCOL.md` (named
by the playbook's review rule), `Meta/x.md` and `Design.md` (exact case)
held for the human with §46's reason naming that path, and after the
human's approval no engine kickoff; a kit carrying `PLAYBOOK.toml` and
`docs/x.md` held with §43's reason; `meta/PLAYBOOK.toml` held with §43's
reason; `kit check`'s `WARN owner:` line naming every non-plan file entry
but the playbook for a role-mode autonomous repository and absent for a
phone-mode one; the new hold row of §19 pinned as route 2 then `go`, as
`test_the_owner_hold_row_is_route_2_then_go` pins §43's; an ordinary phone
kit unchanged. Gate: the tests (the operator table's every-line test green
with the new reason); `./scripts/check` green.

**U3 The review merges what it reviewed, its failure paths, and the
blocker for a bug in the pull request's own code (§46 "H-081", "A confirmed
bug in the pull request's own code blocks its merge", review 29's should-fix
2 and 4; §35, §45 "The review").** `meta/REVIEW-PROTOCOL.md` and
`templates/REVIEW-PROTOCOL.md` (one text, the template with `<owner>/<repo>`
and the brief's timeout as today), `templates/BUILDER-N-PROMPT.md` (its last
unit: one sentence after the pinned "a finding that needs a design decision
is filed in `meta/findings/FINDINGS.md`, never fixed in silence", which
stays intact and in its place — such a finding in the pull request's own
code blocks the merge until the closer fixes it), the
handbook's §9 and §19 where they quote the merge, the failure paths or what
a blocker is,
`meta/findings/FINDINGS.md` (H-081, H-084, H-085 resolved), tests (the
protocol, docs and handbook pins). The protocols say, in every review of a
pull request (its file going to `main` or to the branch; not in the direct
shape, not for a `reviewed: none` review): before the review's commit, `git
fetch origin` and `git rev-parse origin/<branch>` equal to the whole
`reviewed:` sha, else the moved-branch blocker and no merge, and a refused
push of the review's commit is the same blocker, with §46's steps (rebase
onto the new tip, the blocker committed as `review: mission N (branch
moved)` and pushed, or nothing more committed when that fails too); the
merge `gh pr merge
<number> --merge --match-head-commit <sha> --subject "merge: mission N (PR
#<number>)"`, `<sha>` the whole sha of the reviewed tip when the review went
to `main` and of the review's own commit (`git rev-parse HEAD` after its
push) when it went to the branch; a merge refused or not made adds the `not
merged` blocker, committed where the review was, counted in the reply. The
failure paths, as §46's should-fix 2 says: the review of a failed rules read
(whatever the rules), and under `pull_request` that of a missing pull
request, committed to the branch the brief names when it exists on `origin`
(`git ls-remote --exit-code --heads origin <branch>`), never to `main`, else
nowhere; that of a Direct brief under `pull_request` nowhere. In every
shape: a review that checked out the mission's branch ends with `git
checkout main && git pull --ff-only`. And in the protocols' definition of
a blocker and their `## Hosted review` dispositions, §46's merge rule word
for word in substance: what a defect is; a confirmed defect in what the
pull request adds or changes, or one at the base that it makes reachable
or relies on, is a blocker even when the design prescribes it; any other
defect at the base, shown by the base's text or one test or command in a
worktree at the merge-base (never the gate), is a should-fix marked "to be
filed" (the review commits nothing more); in the direct shape a defect in
the commits under review is a blocker; the section says which each
confirmed finding is, and why. Tests pin the definition and the three
cases in both protocols.
Tests: the protocols' pinned phrases for each of these; the template and
this repository's copy agreeing but for the repository and the timeout.
Gate: the tests; `./scripts/check` green.

**U4 Final report, the pull request, its checks and the hosted review's
findings.** `meta/FINAL-REPORT-30.md` (drafted under `meta/drafts/`, moved
in by this commit): what changed (sha per unit), what tests prove, NOT
PROVEN (mandatory: no ruleset exists, so no apply has gone through a pull
request under the gate and no review has merged with `--match-head-commit`
on GitHub), and the `## Review items` section: review 29's should-fix 1
closed by U1 (H-082), U2 (H-083) and U3 (H-081), should-fix 2 by U3 (H-084),
should-fix 3 by U1, should-fix 4 by U3 (H-085). Then open the pull request
(see Branch). Wait for its CI check: `uv run hands ci-wait <pr> --check
check; echo "ci-wait-exit=$?"`, one foreground call at a time, again while
it exits 3, at most seven calls. On a failed check, read its log (`gh run
view <run> --log-failed`), fix the cause within §46 by a sub-agent under
the sub-agent rules, committed and pushed to the branch, and wait again; a
failure that needs a design decision is filed, never fixed in silence.
Then wait up to ten minutes for the bot, the hosted reviewer, in
one-minute foreground steps: `hands hosted-review <pr>` exits 3 with "no
bot comment yet", writing nothing, until the bot has posted its Code Review
comment, which is the wait, never a clean review; exit 4 means the findings
could not be parsed against the header counts, so read the archived
comment itself. The command archives the bot's words under
`meta/reviews/hosted/PR-<pr>/<k>/` and takes the verdict from the Code
Review comment only. Fix each finding that is within §46 by a sub-agent
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
[.name, .app.slug, .app.id, .conclusion, .html_url] | @tsv'` (a read);
commit them with the archive directory, push, and wait for the CI check
once more on that last commit as above. Return the tree to `main`. Then the
verdict line, and right after it the last `ci-wait` line. If that last wait
does not end in exit 0, the verdict is `VERDICT: mission 30 blocked U4`,
with that line.

## Acceptance

- `./scripts/check` green on the pushed tip, three consecutive runs.
- The pull request's `check` check passed at the pushed tip: the final
  reply's last `ci-wait` line reads `ci-wait: passed`; the final report's
  `## CI` section names the check and its app.
- Every unit commit's body lists every file it touches; U0 is `plan:`.
- H-081, H-082, H-083, H-084 and H-085 are resolved.
- The `pull-request` apply prompt's case (b) excludes `main`; the setting's
  refusal names both values (U1's tests).
- A role-filed kit with any file entry that is not a plan file waits for the
  human with §46's reason, and §45's CI hold is gone into it (U2's tests).
- Both review protocols block on a moved branch, merge with
  `--match-head-commit`, commit their failure-path reviews to the branch
  when it exists, end on `main`, and make a confirmed defect in the pull
  request's own code a blocker (U3's tests).
- `meta/FINAL-REPORT-30.md` exists with NOT PROVEN, the review-items
  section, the `## Hosted review` table and the `## CI` section.
- The PR from `mission-30` to `main` is open (`gh pr list --head mission-30
  --state open`), and the tree is on `main`.
