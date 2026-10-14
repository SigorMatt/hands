# REVIEW-19 — cold review of hands mission 19
reviewed: 5d587d9316d8cd5ee643e12c9f7bc37de2befd80

VERDICT: review mission 19 blockers=0 should-fix=5

Shape: direct. `gh pr list --head mission-19 --state open` returns `[]`, and
the brief says the mission commits to `main` ("reviewed under the direct
shape"). Base `724e8c5` (`review: mission 18`, the last `review:` commit on
origin/main). Commits under review (`git log --oneline 724e8c5..origin/main`):

    5d587d9 meta: mission 19 final report and bookkeeping
    5220e67 docs: [series] keys in the handbook, §9 as the PR flow, gh in INTEGRATION
    de56f62 flow: this repository's own flow — branch convention, protocol, playbook
    7929d9c templates: the pull-request flow in the brief, protocol and missions playbook
    b55dfb1 doctor: a `gh` row — version, login, `repo` scope; WARN with `gh auth login`
    1758b56 plan: mission 19 plan, the hosted-review gate, H-040
    21d62d9 plan: mission 19 kit (DESIGN v3.18)

One sub-agent ran for each unit commit (b55dfb1, 7929d9c, de56f62, 5220e67).
The `plan:` and `meta:` commits were read by the reviewer.

## Blockers

None.

## Should-fix

1. **The protocol's "no PR" branch accepts a PR mission whose PR was never
   opened.** templates/REVIEW-PROTOCOL.md:22 and meta/REVIEW-PROTOCOL.md:22
   say "Without one (a direct mission): the base is the last `review:` commit
   on `main`". Suppose a mission-20 builder pushes `mission-20` but never runs
   `gh pr create`, or dies before its last unit. `gh pr list --head mission-20
   --state open` then returns `[]`. The reviewer takes the direct shape and
   reviews `main` since `review: mission 19`, which holds only plan commits,
   and it can return `blockers=0` without reading any of the branch's code.
   The fix: the protocol takes the direct shape only when the brief says
   "direct". With no PR for a brief that names a branch, the review reports a
   blocker ("no pull request for mission-N") and goes no further.
2. **The protocol's base for a closer pulls in `main`'s own commits, and its
   commands hard-code `mission-N`.** The closer brief merges `main` into the
   open branch first (§35, templates/BUILDER-N-PROMPT.md). That puts `main`'s
   `review:` and `plan:` commits after the previous `reviewed:` sha, so
   `git log <reviewed>..origin/<branch>` lists them as commits under review.
   The protocol only tells sub-agents to skip `meta:` commits, so it would
   dispatch them for those too. In addition, templates/REVIEW-PROTOCOL.md:18-20
   write `origin/mission-N` literally; only line 15 says to substitute the
   closer's branch. The fix: name the branch once as `<branch>` and exclude
   `main`'s history, e.g. `git log <base>..origin/<branch> ^origin/main` (or
   `--first-parent`).
3. **Doctor's `gh` row misreads several hosts or accounts.**
   src/hands/doctor.py:537-544 take the first login line and the first
   `Token scopes:` line in the whole `gh auth status` output, whatever the
   host. A GitHub Enterprise host listed before github.com decides the row,
   so github.com with `repo` can show WARN "no `repo` scope". `gh auth
   status` also exits 1 when any one account on any host is bad, and the row
   then says "not logged in" even when the active github.com account is fine.
   Both are WARN-only, so nothing is falsely failed, but the row's message is
   wrong. The fix: `gh auth status --active --hostname github.com`. Both flags
   exist in gh 2.92.0 (`gh auth status --help`).
4. **docs/INTEGRATION.md:385-386 say more than the code does.** They say
   every `warn` of the row, including "a `gh --version` that does not
   answer", names the remedy `gh auth login`. The two warns at
   src/hands/doctor.py:529 (`--version did not answer`) and :534 (`gh auth
   status` did not run) do not name it. Either the code appends
   `GH_REMEDY` to them, or the doc stops claiming it.
5. **docs/PLAYBOOK.md:500-501 have a garbled sentence:** "the review prompt
   `templates/PLAYBOOK-missions.toml` and this repository's `PLAYBOOK.toml`
   ship says the protocol finds …". It needs rewording (e.g. "the review
   prompt that `templates/PLAYBOOK-missions.toml` and this repository's
   `PLAYBOOK.toml` ship says …").

## Hosted review

None. This mission is direct, with no pull request (`gh pr list --head
mission-19` returns `[]`), so there was no hosted review to read.

## Notes

- **Gate U0 checked against the forge.** PR #1 (`probe-qodo`) was created at
  2026-10-14T11:31:49Z and closed unmerged at 11:33:06Z. Both
  `qodo-code-review[bot]` issue comments are dated 11:32:18Z. That is a
  29-second delay, posted on open, which agrees with meta/plan.md "Gate U0".
  `git branch -a` and `git ls-remote origin` show no `probe-qodo`.
- **H-040 is reproduced.** This review also ran as a hands job (`HANDS_PROJECT=hands`,
  `HANDS_JOB` set), and every sub-agent's gate needed `env -u HANDS_PROJECT -u
  HANDS_JOB`. U1 added an autouse conftest fixture (tests/conftest.py) that
  could have cleared `HANDS_*` cheaply, but did not; it was out of U1's scope.
  The finding is still open and is mission 20's to close.
- **The gate counts agree with FINAL-REPORT-19 §1.** The sub-agents' single
  runs gave 4035 (U1), 4043 (U2), 4045 (U3) and 4052 (U4), all green. The tip
  5d587d9 differs from 5220e67 only under meta/. Each unit's "3/3" is still
  the builder's own claim; each sub-agent ran the gate once.
- **The U2 body says "8 tests" for tests/test_kit.py.** 7 new test functions
  were collected. The eighth case is the new row in
  tests/fixtures/named_path_shapes.tsv, run by the existing parametrized test
  (4035 → 4043 = 8). Consistent.
- **Coverage-only tests, as the bodies say.** The two `pr=` verdict tests and
  the six-of-six clone test (U2), and the docs `gh <cmd>` guard (U4), pass
  without the change. So kit.py needed no change, which matches the
  FINAL-REPORT. The U4 guard scans backticked spans only, not indented code
  blocks.
- **FINAL-REPORT-19 §NOT PROVEN agrees with what the sub-agents found.**
  - No `gh` call, merge or hosted-bot read is exercised by a test (items 1–3).
  - The doctor row is tested against the fake only (item 4; should-fix 3 is
    a case the fake does not model).
  - meta/BUILDER-20-PROMPT.md does not exist (item 6).
  - Nothing on disk contradicts the report.
- **For mission 20's protocol (minor).** The protocol never tells the
  reviewer to make sure it is on an up-to-date `main` (`git checkout main &&
  git pull --ff-only`) before it commits the review file. It relies on the
  builder having returned the tree there.
- **Forbidden files.** None of the unit commits touched DESIGN.md,
  meta/plan.md or meta/CHECKPOINT.md. DESIGN.md changed only in the
  architect's kit commit 21d62d9.

## Per-commit verdicts

**b55dfb1** (U1, doctor `gh` row): PASS, two minor defects.
1. Names mission 19 U1, DESIGN v3.18 §35 "`hands doctor` (code)"; matches BUILDER-19 U1.
2. Test-first: 5 tests (ok text+`--json`, old stderr format, unauthenticated, no `repo`, absent); with doctor.py reverted all 5 fail (KeyError `found["gh"]`).
3. Gate (`env -u HANDS_PROJECT -u HANDS_JOB ./scripts/check`): `4035 passed in 457.82s (0:07:37)`, `check: green`.
4. Conformance: never FAIL; a hang times out to WARN after 10.3s (PROBE_S=10); `Token:` lines dropped; `repo` matched whole-scope (`public_repo` alone → WARN); both formats parse; the autouse fixture only prepends the fake. Forbidden files untouched; body lists all 4 files.
Defects: doctor.py:537/:544, the first login/scopes line wins across hosts (GHE listed first → wrong WARN); doctor.py:538, one bad account makes `gh auth status` exit 1, so the row says "not logged in" though the active account is fine.
Not proven: real gh releases beyond the fake; `GH_TOKEN` without a scopes line → WARN "none reported" (acceptable); the `--version` timeout path is untested.

**7929d9c** (U2, templates): PASS, no blockers.
1. Named correctly; §35 "The builder", "The review", "Standing approval", plus §26, §31; body lists all 5 files; forbidden files untouched.
2. With templates/ reverted, 4 of the 7 new tests fail; `pr_literal_passes_the_verdicts_check`, `both_finished_literals…` and `six_of_six_against_a_clone` pass anyway (coverage-only, as claimed: kit.py needed no change).
3. Gate: `4043 passed in 471.04s (0:07:51)`, `check: green` (one run).
4. Conformance PASS: review committed to `main` before merge, `--merge` never squash, PR left open with blockers, verdict line unchanged, old "every commit after" phrase gone, `builder.done` regex unchanged, PLAYBOOK-runs.toml correctly unchanged.
Should-fix: REVIEW-PROTOCOL.md:18-20 hard-code `mission-N`; for a closer, `<reviewed>..origin/<branch>` includes main's merged review:/plan: commits; :22 "Without one (a direct mission)" also catches a PR mission whose PR was never opened; :71 has no check that the tree is on `main` before committing the review.
Not proven: real builder/reviewer behaviour, real `gh`, the bot, the merge, the closer path.

**de56f62** (U3, this repository's flow): PASS, no defects.
1. Mission 19 U3, §35 "The builder", "The review", "This repository"; body lists all 5 files.
2. Test-first: 2 new tests in test_docs.py (protocol == template with names; CLAUDE.md wording) and 2 tightened in test_playbook.py; with the 3 non-test files reverted all 4 fail (plus 4 own-playbook-matches-HEAD guards).
3. Gate: "All checks passed!" / `4045 passed in 427.63s (0:07:07)` / `check: green`.
4. `diff templates/REVIEW-PROTOCOL.md meta/REVIEW-PROTOCOL.md` differs only at lines 34–36 (`<owner>/<repo>` → `SigorMatt/hands`); PLAYBOOK.toml changes exactly 2 lines; loader gives 20 rules, kickoff BUILDER-20; a kit of BUILDER-19 with `--repo .` passes 6 of 6, rc=0; CLAUDE.md:14-19 matches the brief; forbidden files untouched.
Not proven: loaded via `load_playbook`, not `hands --project hands pipeline`; a self-built kit dir, not the architect's zip; BUILDER-20 does not exist yet.

**5220e67** (U4, docs): PASS, two minor should-fix.
1. Mission 19 U4 (Docs), §35 plus §31/§32 for `[series]`, closes HF-004; body lists all 4 files; forbidden files untouched.
2. With docs/ reverted the four new tests fail; the gh-commands guard passes on all three docs (guard only, as stated).
3. Gate: `4052 passed in 473.08s (0:07:53)` / `check: green`.
4. `[series]` defaults match playbook.py:852-858 and :194-206 (architect `phone`, autonomous false, gate_failures 2, escalate_on empty, kit_wait_s 600); every `hands` command and gh flag shown exists; the doctor row matches `_gh_check`; §9 matches §35 (merge commit, review before merge, subject, standing approval, direct option).
Should-fix: INTEGRATION.md:385-386 claims every warn names the remedy, but doctor.py:529 and :534 do not; PLAYBOOK.md:500-501 garbled sentence; cosmetic: ARCHITECT-HANDBOOK.md:6 not rewrapped.
Not proven: the §9 prose against a real builder, reviewer or bot; the guard skips indented code blocks.
