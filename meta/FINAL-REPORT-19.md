# FINAL-REPORT-19 — the pull-request flow; a hosted second reviewer

VERDICT: mission 19 finished

Brief: meta/BUILDER-19-PROMPT.md. Design: DESIGN v3.18 §35 (with §26, §31).
Review read: meta/reviews/REVIEW-18.md (blockers 0, should-fix 4; all four are
mission 20's, see "Review items"). Shape: direct. Every unit committed and
pushed to `main`, as the brief and §35 "This repository" say. Base 21d62d9
(`plan: mission 19 kit (DESIGN v3.18)`). Findings: H-040 filed (U0, open). H-039,
H-037, H-034, H-027, H-001 and H-009 stay open.

The gate environment (H-040). This mission ran as a hands builder job, so it
inherited `HANDS_PROJECT` and `HANDS_JOB`. With them set, 12 tests in
tests/test_kit.py fail at the base (`12 failed, 4018 passed`), because the
`kit file` CLI picks up the project from `$HANDS_PROJECT`. Every gate in this
mission, the orchestrator's and the sub-agents', was `env -u HANDS_PROJECT -u
HANDS_JOB ./scripts/check`, and every commit body says so.

## 1. What changed (sha per unit)

- U0 1758b56 (`plan:`): meta/plan.md, meta/CHECKPOINT.md, meta/journal.md,
  H-040. It also ran the gate (record in §4 below). Green 3/3, 4030 passed.
- U1 b55dfb1 (`doctor:`): doctor has a `gh` row right after `claude`. It runs
  `gh --version` and `gh auth status`, with `gh` found on PATH only, and reads
  both output streams.
  - OK shows the version, the path, the login and the user.
  - WARN, naming `gh auth login`, when `gh` is absent, unauthenticated, or has
    no `repo` scope. Never FAIL.
  - The `Token:` line is never repeated.
  - tests/fake_gh.py, plus an autouse conftest fixture that puts the fake first
    on PATH for every test.
  - Green 3/3, 4035 passed.
- U2 7929d9c (`templates:`):
  - The brief template: a `mission-N` branch from `main` (or continuing the
    branch a closer brief names, with `main` merged in first); units push to
    the branch; the last unit runs `gh pr create … --body-file
    meta/FINAL-REPORT-N.md`, replies `VERDICT: mission N finished
    pr=<number>`, then `git checkout main && git pull --ff-only`; the "direct"
    option.
  - The protocol template:
    - It finds the PR itself (`gh pr list --head mission-N --state open …`).
    - With a PR, the base is the merge-base with `main` or the previous
      `reviewed:` sha. Without one, it is the last `review:` commit on `main`.
    - It reads the hosted review, waiting up to 10 one-minute steps.
    - The review file gains `## Hosted review` and a `reviewed: <sha>` line,
      and is committed to `main` before any merge.
    - On `blockers=0` it runs `gh pr merge <n> --merge --subject "merge:
      mission N (PR #<n>)"`. With blockers the PR stays open.
  - The missions playbook template's review prompt now says the protocol finds
    the commits itself. The `builder.done` regex is unchanged.
  - Not changed:
    - src/hands/kit.py: it already accepted the `pr=<number>` literal; the
      tests prove it.
    - templates/PLAYBOOK-runs.toml: its prompt never said "every commit
      after".
  - The builder's choice: a closer whose PR is still open opens no second PR
    and replies with the open PR's number.
  - Green 3/3, 4043 passed.
- U3 de56f62 (`flow:`):
  - CLAUDE.md: unit commits go to the mission's branch, which the brief names
    (`mission-N`, or `main` for a direct brief). `main` moves by merges and
    plan commits. The tree is left on `main` at mission end.
  - meta/REVIEW-PROTOCOL.md is the template with `SigorMatt/hands` (`diff`:
    one hunk, the three `gh api` lines).
  - PLAYBOOK.toml: the kickoff names meta/BUILDER-20-PROMPT.md, and the review
    prompt is the template's.
  - Green 3/3, 4045 passed.
- U4 5220e67 (`docs:`):
  - ARCHITECT-HANDBOOK §6 lists all seven `[series]` keys with their defaults
    (closes discotrade HF-004 on hands' side).
  - §9 is retitled "A pull request per mission; the review merges a clean one
    (DESIGN §35)" and covers the merge commit (never a squash), the standing
    approval and the direct option.
  - INTEGRATION covers the `gh` prerequisite, doctor's `gh` row, and the tree
    being on `main` between missions.
  - PLAYBOOK: the review-base wording matches the shipped prompt.
  - Green 3/3, 4052 passed.
- U5 (this commit): this report and the mission's meta bookkeeping (plan,
  checkpoint, journal).

## 2. What the tests prove

- Doctor's `gh` row, in five tests in tests/test_doctor.py. They cover OK
  (text and `--json`), the older stderr format, unauthenticated, no `repo`
  scope, and absent. Each test asserts the status, an exit 0, the remedy, and
  that the fake token is not printed.
- The verdict vocabulary. `test_a_brief_with_the_pr_literal_passes_the_verdicts_check`
  and `…both_finished_literals_passes_and_one_without_pr_still_does` show that
  a brief with `VERDICT: mission N finished pr=<number>` passes `verdicts`
  against the unchanged regex, and a brief without `pr=` still does. Both
  passed before any template edit, so kit.py needed no change.
- The templates.
  - `test_the_filled_missions_templates_pass_six_of_six_against_a_clone_of_this_repository`
    fills the brief, protocol and missions-playbook templates and runs `kit
    check` against a `git clone` of this repository: 6 of 6.
  - The U2 sub-agent also ran it by hand against /tmp/hands-u2-clone, as a
    directory and as a zip: `kit check: pass (6 of 6 checks)`, exit 0.
  - Phrase tests pin each §35 step in the brief and protocol templates, and pin
    the protocol's one review literal as the unchanged verdict line.
- This repository.
  - Tests pin meta/REVIEW-PROTOCOL.md as the template with `<owner>/<repo>`
    replaced, CLAUDE.md's branch rule and return-to-`main` rule, the BUILDER-20
    kickoff, and the review prompt and finished regex as the template's. All
    were red first.
  - By hand, `hands --project hands pipeline` gives `series hands-missions  20
    rule(s)`, no error.
  - A kit of meta/BUILDER-19-PROMPT.md with `--repo .` gives 6 of 6, exit 0.
- The docs. Four tests pin handbook §6 (every key and its default), handbook §9
  (the §35 shape, no `--squash`), INTEGRATION's `gh` sections and the PLAYBOOK
  review-base wording; all four were red first. A three-case test keeps every
  `gh <cmd>` the docs show inside the set the flow uses. It was coverage only:
  it passed before the edits.

## 3. NOT PROVEN

1. **No mission has yet run through the flow.** No builder has created a
   `mission-N` branch, opened a PR at its last unit, or replied with `pr=`.
   Mission 20 is the first.
2. **The merge step has never run.** No review has run `gh pr merge --merge`,
   committed a review file to `main` before a merge, or brought the tree level
   after one. The protocol's PR branch, its `reviewed:` base for a closer, and
   its ten-minute wait are text and phrase tests only.
3. **The hosted review was seen once, on a one-line docs PR** (PR #1, §4). Its
   delay on a mission-sized PR, its inline `pulls/<n>/comments` and `reviews`
   entries (none existed by the second poll), and whether the reviewer's `gh
   api` reads parse what it posts are unproven.
4. **Doctor's `gh` row** is tested only against the fake's two output formats.
   It was checked by hand once against real gh 2.92.0 on this laptop: `ok gh …
   logged in as SigorMatt (user msi); token scopes include repo`. Not tested:
   other `gh` versions, several accounts or hosts, and doctor answered over
   the API as handsd's user.
5. **The prompt that reviews this mission.** §35 says the review rule fires with
   the prompt loaded when the mission started (the old one), and the protocol
   on disk handles the no-PR shape. Neither the daemon's reload nor that review
   has run.
6. **meta/BUILDER-20-PROMPT.md does not exist.** The kickoff names it, and the
   architect ships it, as in mission 18 U5.
7. **H-040.** The gate is red inside a hands job unless `HANDS_*` is unset.
   The tests do not fix their own environment.
8. **"3/3"** is each sub-agent's own report (and the orchestrator's for U0 and
   the tip). No reviewer has reproduced it.

## Review items

| Item | Unit | Commit | State |
|---|---|---|---|
| REVIEW-18 should-fix 1 — a Unicode full stop in `ntfy_url` gets the token past the public-broker check | — | — | mission 20's (BACKLOG item 9; this mission does not touch it) |
| REVIEW-18 should-fix 2 — a module planted beside the guard shadows one it imports; doctor passes | — | — | mission 20's (the guard and doctor's self-test are out of scope) |
| REVIEW-18 should-fix 3 — the kit record hashes the bytes the client sent, not the bytes checked | — | — | mission 20's (the engine is out of scope) |
| REVIEW-18 should-fix 4 — a hardlink under `kits/` lets `cp` overwrite the guard | — | — | mission 20's (the guard is out of scope) |

## 4. Acceptance

- The gate on the pushed tip: `./scripts/check` (HANDS_* unset, H-040) green
  three consecutive runs, 4052 passed each.
- Every unit commit's body lists every file it touches. This was checked
  against `git show --name-only` for 1758b56, b55dfb1, 7929d9c, de56f62 and
  5220e67, and nothing was missing. U0 is `plan:`.
- **Gate U0**, as recorded in meta/plan.md:
  - `gh` 2.92.0, authenticated as SigorMatt with the `repo` scope.
  - The probe PR SigorMatt/hands#1, from `probe-qodo` (one dated line in
    docs/INTEGRATION.md, on that branch only), was opened at
    2026-10-14T11:31:49Z.
  - `qodo-code-review[bot]` posted its first comments at 11:32:18Z: "PR
    Summary by Qodo" and "Code Review by Qodo" (Bugs 0, Rule violations 0,
    Requirement gaps 0).
  - The delay was 29 seconds. The trigger mode was "on open".
  - The PR was closed with `--delete-branch`, and `git branch -a` shows no
    `probe-qodo`.
- `hands doctor` prints a `gh` row: the tests in §2, and the laptop line in
  §3.4.
- PLAYBOOK.toml's kickoff names meta/BUILDER-20-PROMPT.md, and the playbook
  loads with 20 rules.
- A kit built from the new templates passes `hands kit check` 6 of 6 (a test,
  and by hand).
- This file exists with NOT PROVEN and the review-items table.

## 5. For the architect

- Mission 20 is the first pull-request mission. Its brief should not say
  "direct". Its U0 creates `mission-20` from `main`, and its review is the
  first to read a hosted review and to merge.
- REVIEW-18's four should-fix items and BACKLOG mission 20's list are waiting
  for it.
- H-040 is a cheap fix: an autouse fixture that clears `HANDS_*`. Every
  builder hands dispatches inherits those variables. Without the fix, a brief
  needs to tell the builder to unset them.
- The bot posted on open in 29 seconds, so the protocol's ten-minute wait
  leaves a wide margin.
