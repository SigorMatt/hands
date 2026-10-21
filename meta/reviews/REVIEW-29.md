# REVIEW-29 — cold review of mission 29 (a `main` that takes pull requests only), PR #9

reviewed: 39d510a086ef2878e76cadd6b98fa25d79f82883

Shape: pull request (BUILDER-29 §Branch). Branch `mission-29`, PR #9 (base
`main`), first review of the branch: base = `git merge-base origin/main
origin/mission-29` = f7d61c8. The protocol followed is the one on `main`
when this review started (DESIGN §45 "This repository, and the other
project": mission 29's review commits to `main` and merges). Commits under
review (`git log f7d61c8..origin/mission-29 ^origin/main`):

    39d510a report: mission 29 hosted review dispositions, CI and the PR #9 archive
    e375630 cli: ci-wait's nine minutes count from the call's start and bound every read
    b3f5b91 tests: the crafted zip's ZipInfo.filename is asserted per Python version
    9fa853c report: mission 29 final report
    7e0914e playbook: at rest published again after the kept list changed
    897ec34 docs: the review, the brief and the architect under a pull-request main
    39e7976 playbook: an apply that did not land is the engine's stop; the CI's hold; the journal under pull-request
    cd0e13f kit: the apply's prompt by [repository] main, and an apply's resume re-sends it
    db5c000 cli: hands ci-wait, the [repository] main setting and doctor's main row
    624aff0 ci: run ./scripts/check on GitHub's runner; keep every test on the machine
    616f7e1 plan: mission 29 plan, branch and findings (H-079, H-080)

## Blockers

None.

## Should-fix

1. Three findings filed from the hosted review are open and need design
   decisions before the switch §45 schedules after this install: H-082
   (high; the `pull-request` apply prompt's case (b), §45 word for word,
   matches `main` itself, so an apply started on `main` commits there, has
   its push refused and stops — FINAL-REPORT-29 §3 says docs/PR-CI-GATE.md
   §5 step 2 must wait for it), H-081 (the review's merge does not tie the
   merged head to the reviewed one: mission 30's review is the first to
   merge on green checks) and H-083 (the CI hold names `.github/` and
   `scripts/check` only, not the gate's other inputs such as
   `pyproject.toml`, `uv.lock`, `tests/conftest.py`). Decide H-082 and
   H-081 in the design before `[repository] main = "pull-request"` is set
   for this repository.
2. Hosted finding 5 ("A missing pull request hides its review") was
   dismissed as conforming to §45, which is accurate, but the point it
   makes is a design inconsistency left on no record: §45 commits the
   rules-read failure's review "to the mission's branch when it exists",
   commits the no-pull-request `reviewed: none` review nowhere even when
   the branch exists, and has the architect read a review with blockers
   from `origin/<branch>`. File it as a finding (CLAUDE.md: DESIGN.md is
   not edited by builders; file a finding) rather than dismiss it.
3. `[repository] main` with a non-string value (e.g. `main = true`) is
   refused by `_str` with "must be a string", which does not name the two
   values (src/hands/config.py, db5c000); §45 "The setting": "any other
   value refuses to load, naming the two". No test covers a non-string.
4. Both review protocols (897ec34): when `main`'s rules cannot be read and
   the review file is committed to the mission's branch, nothing returns
   the tree to `main` afterwards (`git checkout main && git pull
   --ff-only` appears only under "The merge" with `pull_request`), so the
   next kit's apply could run on the branch. §45 is silent; file a finding.

## Hosted review

Archive `meta/reviews/hosted/PR-9/3/` (this review's fetch, at 39d510a; the
builder's fetches 1 and 2 are on the branch). `hands hosted-review 9`
exited 0. Verdict taken from the Code Review comment (issue-comment
6307244055, updated 2026-10-21T05:10:10Z): **5 of 7 findings open in the
Code Review comment** (1, 2, 5, 6, 7). Header: 🐞 Bugs (4) · 📘 Rule
violations (1) · 🔗 Cross-repo conflicts (0) · 📜 Skill insights (0). Diff
against fetch 2: only issue-comment 6307244055 changed, and only its
permalink sha (e3756303… → 39d510a…); no finding text or status changed.

1. "A review can merge unreviewed commits" `🐞 Bug` `≡ Correctness` —
   templates/REVIEW-PROTOCOL.md:275-279 (inline 4332716798 at :279) —
   "The review protocol waits for checks by pull request number and merges without verifying that the head still matches the commit its sub-agents reviewed. If the mission branch advances during the review, the review can record the earlier <b><i>headRefOid</i></b> while the later commit passes checks and is merged."
   → confirmed → carried as should-fix 1 (a design decision: the merge
   command is §45's word for word). Audit: builder filed H-081 — holds;
   H-081 is in FINDINGS.md, open (needs a design decision).
2. "Applies from main take the mission-branch path and fail" `🐞 Bug`
   `≡ Correctness` — src/hands/kit.py:227-230 (inline 4332716812 at :230) —
   "<b><i>PULL_REQUEST_APPLY</i></b> case (b) treats <b><i>main</i></b> as an in-flight mission branch because it is on <b><i>origin</i></b>, is not a <b><i>kit/</i></b> branch, and has no MERGED or CLOSED head pull requests. When an apply starts on <b><i>main</i></b> between missions, the builder commits and attempts to push there instead of opening the kit pull request; protected <b><i>main</i></b> refuses the push, and the resulting <b><i>kit not applied pr=none</i></b> reply stops the pipeline through <b><i>_apply_not_landed</i></b>."
   → confirmed → carried as should-fix 1 (the prompt is §45's word for
   word, cd0e13f's sub-agent compared it byte for byte; the defect is in
   the design). Audit: builder filed H-082 — holds; H-082 is in
   FINDINGS.md, open, high, and blocks the switch.
3. "~~Stalled checks can exceed the tool timeout~~" `✓ Resolved` —
   src/hands/cli.py:232-235 (inline 4332716808 at :235) —
   "<b><i>ci_wait</i></b> starts its nine-minute deadline only after authentication, origin, pull-request and rules reads, each of which can consume a subprocess timeout, and it starts a further checks read without bounding it by the remaining time. When those commands stall, one foreground call can run well beyond the stated nine minutes and exceed the role&#x27;s tool-call timeout before returning a wait or error result."
   → dismissed: fixed in e375630 and shown resolved by the bot. Audit:
   holds — e375630 touches the anchor (every read bounded by `left()`, the
   deadline taken before the first read); its sub-agent saw the new tests
   red with cli.py and forge.py reverted.
4. "~~Test subprocesses can hang indefinitely~~" `✓ Resolved` —
   tests/test_ci_wait.py:47-51 (inline 4332716790 at :51) —
   "The new test fixtures invoke <b><i>git</i></b> and <b><i>gh</i></b> through <b><i>subprocess.run</i></b> without an explicit timeout. A stalled local tool can block the test suite indefinitely, including repository setup in <b><i>tests/test_ci_wait.py</i></b> and <b><i>tests/test_doctor.py</i></b>."
   → dismissed: fixed in e375630 and shown resolved by the bot. Audit:
   holds — `timeout=30` on every `subprocess.run` of test_ci_wait.py and
   on the referenced test_doctor.py lines; five older calls in
   test_doctor.py still have none, which the body discloses.
5. "A missing pull request hides its review" `🐞 Bug` `≡ Correctness` —
   templates/REVIEW-PROTOCOL.md:64-65 (inline 4332716802 at :65) —
   "The no-open-PR branch of the review protocol writes a blocker file but, under <b><i>pull_request</i></b>, explicitly commits it nowhere even if the mission branch exists. When that blocker stops the pipeline, the architect is instructed to read the review from the mission branch, where the file is absent."
   → confirmed → carried as should-fix 2. Audit: builder dismissed it with
   the reason that §45 says the no-PR review is committed nowhere — the
   reason is accurate but incomplete: the inconsistency is in §45 and
   should have been filed as a finding.
6. "Kits can still weaken the gate their PR merges on" `🐞 Bug`
   `⛨ Security` — src/hands/spool.py:173-183 (inline 4332716818 at :183) —
   "<b><i>carries_ci</i></b> only treats an entry as CI when its casefolded path begins with <b><i>.github/</i></b> or equals <b><i>scripts/check</i></b>. The gate that <b><i>scripts/check</i></b> runs (<b><i>uv sync</i></b>, <b><i>ruff check .</i></b>, <b><i>pytest</i></b>) is also configured by <b><i>pyproject.toml</i></b>, <b><i>uv.lock</i></b> and <b><i>tests/conftest.py</i></b>. An architect-filed kit that changes one of those files (for example pytest <b><i>addopts</i></b>, a conftest that deselects tests, or ruff excludes) is still approved by the engine without a human hold, and its own pull request&#x27;s check then runs the weakened gate it merges on, which is the exact risk §45&#x27;s hold is meant to close."
   → confirmed → carried as should-fix 1 (`carries_ci` is exactly §45's
   two paths; widening it is a design decision). Audit: builder filed
   H-083 — holds; H-083 is in FINDINGS.md, open.
7. "Mission metadata breaks its own edit rule" `📘 Rule violation`
   `§ Compliance` — meta/plan.md:1-3 (inline 4332716794 at :3) —
   "The PR modifies <b><i>meta/plan.md</i></b> and <b><i>meta/CHECKPOINT.md</i></b> while the updated checkpoint states that sub-agents must not edit either file. The U0 metadata changes therefore leave the mission plan and checkpoint outside the repository&#x27;s stated authoring constraint."
   → dismissed: the rule binds sub-agents (CLAUDE.md "Sub-agents do not
   edit meta/plan.md or meta/CHECKPOINT.md"); the only commits touching
   them are 616f7e1 (`plan:`), 9fa853c and 39d510a (`report:`), the
   orchestrator's, and no unit commit lists either file. Audit: builder's
   dismissal and reason hold.

## Notes

- Gate at the tip, my one run, in a worktree at 39d510a
  (/tmp/review29-tip), 09:52:41–10:01:03: `5366 passed in 499.34s
  (0:08:19)`, `check: green`, `check-exit=0`.
- PR #9's `check` check at 39d510a: `check pass 5m45s
  https://github.com/SigorMatt/hands/actions/runs/39548012223/job/119050493370`
  (`gh pr checks 9`); `mergeStateStatus` CLEAN.
- Non-unit commits: 616f7e1 (`plan:`) read for what it says — it files
  H-079 and H-080, writes the plan and checkpoint, touches only meta/;
  9fa853c and 39d510a (`report:`) list only files under meta/ (`git show
  --stat`): no forbidden edit. No unit commit touches DESIGN.md,
  meta/plan.md or meta/CHECKPOINT.md; the only `.github/` change is U1's
  workflow, which the brief's U1 names.
- FINAL-REPORT-29 §3 NOT PROVEN against the sub-agents: consistent. Every
  item is confirmed unproven by the sub-agents (no ruleset, ci-wait never
  read real required checks, doctor row read only this repository's empty
  rules, no real builder/aux has followed the prompts or the protocol,
  gh's behaviour beyond the fake, the daemon path of U4's stop and U6's
  republication, the offline wheel-build skips). Its H-082 item is carried
  as should-fix 1.
- Readings the sub-agents raised, disclosed by the builder and not carried:
  under a human pause an apply that did not land is recorded as the
  pause's suppressed stop, so `resume` rules stop firing until a human
  `resume` (39e7976; FINAL-REPORT-29 §4, consistent with §44 rule 2); the
  engine's stop fires with no playbook file (§4); a `required_status_checks`
  rule with no contexts falls back to `--check`, and `failed:` names every
  failed check (db5c000, the body's "design silent" choices); e375630's
  `timeout=30` on test subprocess calls has no test that fails without it
  (the commit also changes product code, so the tests-only rule does not
  apply).
- U1's §45 `workflow`-scope sentence is in docs/INTEGRATION.md:51-53 at
  the tip (added by U5).
- Schedule (one sub-agent at a time; one `./scripts/check` at a time):
  - hosted review (PR #9, k=3): 08:17:01–08:19:01
  - 624aff0 (U1): 08:19:01–08:28:21
  - db5c000 (U2): 08:28:21–08:47:42
  - cd0e13f (U3): 08:47:42–08:57:12
  - 39e7976 (U4): 08:57:12–09:07:31
  - 897ec34 (U5): 09:07:31–09:20:00
  - 7e0914e (U6): 09:20:00–09:29:15
  - b3f5b91 (U7 CI fix, tests only): 09:29:15–09:38:50
  - e375630 (U7 hosted fixes): 09:38:50–09:52:41
  - my gate at the tip: 09:52:41–10:01:03

## Per-commit verdicts

### Hosted review sub-agent (worktree at 39d510a, `<k>` = 3)

Command `uv run hands hosted-review 9` → `hr-exit=0`, no wait needed.
"PR #9, qodo-code-review[bot]: issue-comments 2, reviews 1,
review-comments 7"; summary comment issue-comment 6307200086; Code Review
comment issue-comment 6307244055 (updated_at 2026-10-21T05:10:10Z).
Verdict: "5 of 7 findings open in the Code Review comment" (open: 1, 2, 5,
6, 7). Header: 🐞 Bugs (4) · 📘 Rule violations (1) · 🔗 Cross-repo
conflicts (0) · 📜 Skill insights (0). Diff vs fetch 2: only 6307244055's
permalink sha changed; inline 4332716812 byte-identical between fetches 2
and 3.

Findings and dispositions (verbatim texts above under ## Hosted review):
1. H-081 filed — holds; FINDINGS.md line 3022, "open (needs a design
   decision)", proposes `--match-head-commit`; the merge command is §45's
   word for word, so filing is correct.
2. H-082 filed — holds; line 3045, high, blocks the switch; kit.py:227
   carries case (b) as quoted; the text comes from the design, so filing
   is right; the defect stays open until that decision.
3. fixed in e375630 — holds; at the anchor the sign-in, origin,
   pull-request and rules reads take `timeout=left(...)` =
   `min(GH_TIMEOUT_S, remaining)`, refusing a read with no time left; bot
   marks it resolved.
4. fixed in e375630 — holds; every `subprocess.run` in test_ci_wait.py has
   `timeout=30`, as do test_doctor.py:3580-3581; five older calls in
   test_doctor.py still have none, disclosed in the body.
5. dismissed (§45 says the no-PR `reviewed: none` review is committed
   nowhere) — the reason is accurate but incomplete: §45's rules-read
   failure commits "to the mission's branch when it exists… and otherwise
   nowhere", and the architect reads with `git show
   origin/<branch>:meta/reviews/REVIEW-N.md`; should have been filed as a
   finding; suggest should-fix, not blocker.
6. H-083 filed — holds; line 3077; `carries_ci` is exactly §45's two paths
   (DESIGN:3823), so widening is a design decision.
7. dismissed (rule binds sub-agents) — holds; only 616f7e1, 9fa853c,
   39d510a touch the files, the orchestrator's commit types.

Audit points: no finding without a row; no fix missing its anchor or still
open; no dismissal without a reason (#5's incomplete); H-081/H-082/H-083
all present; no design decision fixed in silence (e375630's exit-code
choices are disclosed under "Choices" and stay within §45's exits); the
builder's account of fetches 1 (b3f5b91, nothing resolved) and 2
(e375630, 3 and 4 resolved) matches the archive.
Not proven: tests of e375630 (per-commit sub-agent); H-082 in practice;
kit.py case (b) letter for letter (covered by cd0e13f's sub-agent); who
authored the plan/checkpoint edits (inferred from commit types); the bot's
"Resolved" markers taken as its own judgement.

### 624aff0 (U1)

1. Unit: U1 of mission 29, DESIGN §45 "CI". PASS. The body lists all 7
   touched files (`.github/workflows/check.yml` added, `tests/test_ci.py`
   added, `tests/conftest.py`, `tests/test_doctor.py`,
   `tests/test_handbook.py`, `tests/test_no_background.py`,
   `tests/test_project_add.py`).
2. Test-first: PASS. With `check.yml` (absent at ~1) removed,
   `tests/test_ci.py` had 5 failures (FileNotFoundError); the off-machine
   test stayed green as expected. Gate claims: checkout pinned to
   `@v7.0.1` → `test_every_action_is_pinned_to_a_commit_sha` failed;
   `autouse` dropped → `test_a_request_to_another_host_fails_at_once`
   failed ("a request left the machine"); conftest.py reverted to ~1 → same
   test failed. Restored; `git status --short` empty each time.
3. Gate: GREEN. `5143 passed in 456.40s (0:07:36)`, `check: green`,
   `check-exit=0`.
4. Design conformance: PASS. Triggers `pull_request` and `push` to `main`;
   one job id and `name:` `check` on `ubuntu-latest`; `permissions:
   contents: read`; concurrency `check-${{ github.ref }}` with
   `cancel-in-progress: true`; `timeout-minutes: 30`; `run:
   ./scripts/check`. `git ls-remote` confirms checkout `3d3c42e5…` =
   `refs/tags/v7.0.1` (newest v7) and setup-uv `1c37ad07…` =
   `refs/tags/v10.3.0` (newest v10 listed; newer majors not checked), each
   with a `# vX.Y.Z` comment, pinned by the test. Proxy fixture sets
   HTTPS/HTTP_PROXY (both cases) to `127.0.0.1:9`, NO_PROXY/no_proxy to
   `localhost,127.0.0.1`, clears ALL_PROXY. Doctor live tests publish to a
   local stub. Three wheel tests skip only when `uv build --offline` stderr
   contains "was not found in the cache" (names a lack, no CI variable;
   named in the body). No forbidden file. Python 3.11 in the workflow
   (design silent; body explains).
Not proven: the workflow green on GitHub's runner and the check's
reported name from a real run; the bare `env -i` runs and the `log_cli`
scan (not repeated); that no other code path reaches the network; the skip
named in the final report; the docs/INTEGRATION.md `workflow`-scope
sentence (not in this commit).

### db5c000 (U2)

1. Unit — OK. U2 of mission 29: §45 "The setting", "`hands ci-wait <pr>
   [--check <name>]…`", "doctor's `main` row", plus §4, §13.
2. Test-first — OK. `src/hands/forge.py` (added) deleted and `config.py`,
   `cli.py`, `doctor.py`, `templates/config.toml` at ~1:
   `tests/test_ci_wait.py` failed to collect (ImportError on `forge`);
   `test_config.py` + `test_doctor.py` 33 FAILED. With `forge.py` restored
   and the rest reverted, `test_ci_wait.py` 28 FAILED. Restored one file
   per call; `git status --short` empty; the three files pass.
3. Gate — green. `5216 passed in 473.03s (0:07:53)`, `check: green`,
   `check-exit=0` (marker after `| tail`; `check: green` is the proof).
4. Design conformance — OK, three minor deviations. Setting: default
   `direct`; any other string (empty included) refused naming both. ci-wait:
   awaited = `required_status_checks` contexts, else `--check`, else exit 2
   with the exact message; `gh pr checks <pr> --repo <o>/<r> --json
   name,bucket,link`; exit 1 with "no checks reported on the '…' branch" =
   none yet; exits 0/1/3/2 as §45; one line per check then the last line in
   the four forms; 540 s limit, 30 s polls; non-awaited checks never
   decide. Doctor row after `gh`: ok for both agreeing cases (naming the
   checks), the four WARNs, never fails, skipped naming why for no gh, a
   non-github.com origin, no sign-in, a failed read. owner/repo: three
   forms fullmatched, `.git` stripped, other hosts None. Deviations:
   (1) a non-string value (`main = true`) refused by `_str` with "must be a
   string", not naming the two (config.py ~l.938); (2) a
   `required_status_checks` rule with an empty context list falls back to
   `--check` (§45 says "with no such rule"); (3) `failed:` lists every
   failed check joined by ", " (§45 `failed: <name>`); on an error only the
   last line is printed — both declared "design silent" in the body.
   `--stat` lists 9 files, none forbidden; body lists all 9 (forge.py,
   test_ci_wait.py as added).
Not proven: real gh 2.89 behaviour (`pr checks --json` exit 0 while
pending; the exact stderr before the first check); GitHub's real rules
payload; a run against SigorMatt/hands; the doctor row against a live
account.

### cd0e13f (U3)

1. Unit and sections: PASS. U3, §45 "The apply (§27), by the setting" plus
   §6, §10, §27, §32, §43. Files list matches the 11 files of `git show
   --stat`, `tests/test_apply_shape.py` marked added; nothing forbidden.
2. Test-first: PASS. The 7 non-test files reverted to ~1: 22 failures
   (16 test_apply_shape.py, 2 test_kit.py, 1 test_operations.py, 3
   test_phone.py); cases that should pass with the old code (a limited
   kickoff, an orphaned non-apply) stayed green. Restored; `git status
   --short` empty.
3. Gate: green. `5237 passed in 466.73s (0:07:46)`, `check: green`,
   `check-exit=0`.
4. Design conformance: PASS. §45's indented block joined with single
   spaces equals `PULL_REQUEST_APPLY` byte for byte (2651 characters each);
   `{title}`, `{body}`, `{subject}` filled and shell-quoted as §45 says.
   `direct` = old prompt + `DIRECT_REFUSED_PUSH` before "Change nothing
   else.", matching §45. `{branch}` = `kit/<stem>-<12 hex>`, stem rule as
   §45. `kit check` prints `sha256: <hex> (of the zip | of the zip hands
   kit file builds from this directory)` and `apply shape: <shape>
   (<why>)` then the prompt. The phone's `kit`, `hands kit file`
   (`Api._file_kit`) and `hands kit apply` (`Api.kit_apply`) pass
   `config.repository.main`. `chain_first` is §43's walk (moved from
   `Daemon.is_apply`); `builder_resume_prompt` re-sends the first job's
   prompt when it has a `kit_id`, else `resume_line`, used by the playbook
   resume and `LimitManager._resume`. §32: `_engine_applied_kit` reads the
   chain's first job.
Not proven: a real builder following either prompt, real gh/git; `kit
check` prints no sha256 for a failing kit (§45 silent); each of the 22
failures failing for the reason the body claims.

### 39e7976 (U4)

1. Unit — pass. U4: §45 "An apply that did not land (H-080)", "A kit that
   carries the CI is the owner's", "The journal under a `main` that takes
   pull requests only", plus §19, §31, §36, §39, §43, §44; H-080.
2. Test-first — pass. 5 non-test files reverted to ~1:
   `tests/test_apply_not_landed.py` failed at collection (`ImportError:
   cannot import name 'JOURNAL_REMINDER_PULL_REQUEST'`);
   `tests/test_operator_table.py` 2 failures (the CI hold row and the
   `the kit's apply did not land:` row). Restored; `git status --short`
   empty.
3. Gate — green. `5274 passed in 480.66s (0:08:00)`, `check: green`,
   `check-exit=0` (marker after `tail`; `check: green` under `set -euo
   pipefail` confirms).
4. Design conformance — pass, two readings. `_apply_not_landed` runs in
   `on_event` before the pause branch and any rule, only for a
   `builder.done` with `chain_first(...).kit_id`; test `^VERDICT: kit
   applied`; reason `the kit's apply did not land: {_cut(verdict, 200)}
   (§45)`, "no VERDICT: line" when none; unpaused `STOP_TITLE`; under a
   human pause once as `hands: a stop under a human pause`, any other
   pause once under `STOP_TITLE`; pause, reason, kept ends untouched;
   never kept. `carries_ci` per §45; reason exactly §45's; §43's wins when
   both; `WARN ci:` (JSON gains `ci_warnings`). `JOURNAL_REMINDER_PULL_REQUEST`
   word for word; `direct` unchanged; `_JOURNAL_REMINDER_RE` matches both.
   §19 rows pinned; H-080 resolved; nothing forbidden; body names all 7
   files. Reading (a): under a human pause the stop goes through `stop()`'s
   suppressed path (sets `suppressed_stop`, appends
   `pipeline.stop_suppressed`), so `resume` rules fire nothing until the
   human resumes — consistent with §44 rule 2, not said by §45. Reading
   (b): the stop is decided with no playbook file too — a reading.
Not proven: real builder verdict lines; the daemon end to end; each
behaviour's red beyond the missing import; `kit.files` names as
repository paths in every layout; `published_hold_reason` gating against
every hold path.

### 897ec34 (U5)

1. Unit and sections: pass. U5: §45 "The review", "The brief template and
   the architect", "docs/PR-CI-GATE.md", "Documentation"; completes U4's
   §19 row.
2. Test-first: pass. 9 non-test files reverted to ~1; `tests/test_docs_45.py`,
   `tests/test_docs.py`, `tests/test_bash_guard.py`: `80 failed, 1972
   passed in 20.37s` (every test_docs_45 test,
   `test_this_repositorys_claude_md_commits_to_the_missions_branch`,
   `test_architect_rule_1s_review_on_the_branch_is_a_line_the_guard_allows`).
   Restored; `git status --short` empty.
3. Gate: `5353 passed in 472.13s (0:07:52)`, `== cli smoke ==`, `check:
   green`, `check-exit=0` (marker after `| tail`).
4. Design conformance: pass. The two protocols are one text (only the 4
   timeout lines differ after swapping `SigorMatt/hands` for
   `<owner>/<repo>`). Rules read first with the exact `gh api … --jq
   '[.[].type] | join(" ")'`, retried a minute later; failure's blocker to
   the branch when it exists, else nowhere; without `pull_request` to
   `main`; with it the Direct blocker and the no-PR review committed
   nowhere, `hands ci-wait` at the reviewed tip with blocker and `## Notes`
   line, review + archive to the branch, the merge's wait (`hands ci-wait
   <number>; echo "ci-wait-exit=$?"`, at most seven calls), `the merge was
   not made: <last line>` and `review: mission N (not merged)`, return to
   `main` with blockers, the journal carry-over before `git checkout
   <branch>` (incl. the untracked case); `.github/`/`scripts/check`
   blocker in either shape. Brief template, architect rules 1 and 3 (guard
   allows `git -C ./repo show origin/<branch>:meta/reviews/REVIEW-N.md`,
   refuses `git fetch --depth 1`), handbook §3/§9/§10/§12/§18/§19, other
   docs and CLAUDE.md match. docs/PR-CI-GATE.md unchanged (only f7d61c8).
   Nothing forbidden; body names all 12 files, test_docs_45.py as added.
   Possible should-fix: after the rules-read failure committed to the
   branch, the protocol never returns the tree to `main`.
Not proven: a real reviewer or builder following the protocol or brief;
the `gh api` rules read and ci-wait against real GitHub; the phone
architect's shallow fetch. The tests check wording only.

### 7e0914e (U6)

1. Unit and sections: pass. U6, §45 "Review 28's should-fix items" item 1,
   §44 rule 4, H-079.
2. Test-first: pass. Six non-test files reverted to ~1; failing as
   expected: `test_docs_45::test_the_documents_say_at_rest_is_published_again_after_the_kept_list_changed`,
   `test_human_pause::test_a_restart_publishes_an_end_kept_after_the_mark_and_never_published`,
   `test_at_rest_is_published_again_when_a_laptop_send_to_the_aux_is_kept_after_it`,
   `test_an_end_kept_while_a_job_runs_is_published_the_next_moment_nothing_runs`,
   `test_at_rest_is_published_again_with_the_new_list_when_a_kept_end_is_replaced`;
   `test_at_rest_is_not_published_again_after_a_restart` passed at the
   parent (old behaviour; a regression guard). Restored; `git status
   --short` empty.
3. Gate: pass. `5357 passed in 478.91s (0:07:58)`, `check: green`,
   `check-exit=0`.
4. Design conformance: pass. `_keep` (the only place adding to
   `state.kept`) sets `kept_since_rest` whenever `at_rest` is set, for a
   new or a replaced end; `check_at_rest` republishes when the flag is set
   and the busy/resume checks pass, sets `at_rest = now_iso()`, clears the
   flag, saves; `_unpause` clears it (the only place `paused` becomes
   False); flag in `to_dict`/`from_dict`, `_save` uses `atomic_write`;
   daemon start calls `check_at_rest` (`daemon.py:297`). All five brief
   cases covered. Docs carry rule 4's "again"; H-079 resolved; nothing
   forbidden; body lists all 8 files.
Not proven: the daemon-level path (socket, ntfy); a restart feeding
orphans before its check (both said in the body); no test asserts that
`resume` clears `kept_since_rest`.

### b3f5b91 (U7 CI fix, tests only)

1. Unit and sections: pass. U7-fix, §45 "CI", §26/§43, §33; cause: PR #9's
   `check` failed on the runner's Python 3.11 in
   `test_unzip_writes_the_unicode_path_of_the_crafted_zip`.
2. Wrong changes: pass, all turn the test red. `_unicode_paths` wrong
   offset (`extra[8:`): `assert None == ['.git/hooks/pre-commit']`; skipped
   field id: `assert [] == [...]`; dropped field: `assert [] == [...]`;
   `tests/harness.py` `crafted_zip` with the central 0x7075 id overwritten:
   `assert [] == [...]`. `git status --short` empty after each restore.
   "A zipfile change" covered by real interpreters: 3.11.15 gives
   `docs/notes.md`, 3.12.13/3.13.14/3.14.6 give `.git/hooks/pre-commit`;
   3.11's `zipfile.py` contains no "7075". On ≥ 3.12 the test is no weaker.
   `tests/test_kit.py` under 3.11 printed only passing dots.
3. Gate: green. `5357 passed in 476.31s (0:07:56)`, `== cli smoke ==`,
   `check: green`, `check-exit=0`.
4. Design conformance: pass. Hermetic by `sys.version_info`, no CI
   variable, nothing skipped. `--stat` lists only `tests/test_kit.py`,
   named in the body; nothing forbidden.
Not proven: the runner's 3.11 behaving like local 3.11.15; 3.12 patches
before 3.12.13.

### e375630 (U7 hosted fixes)

1. Unit — PASS. U7-hosted, PR #9's hosted findings 3 and 4; §45 `hands
   ci-wait` and its exits, §36.
2. Test-first — PASS for finding 3: cli.py and forge.py at ~1 → `-k
   "slow_reads or stalled or no_time_left"` 9 failed (5 tests plus the
   4-way parametrized real-clock stall test). Restored; `git status
   --short` empty. Finding 4 (test timeouts): the body names no wrong
   change that would make tests red ("no test enforces one"); the commit
   as a whole changes product code.
3. Gate — GREEN. `5366 passed in 497.79s (0:08:17)`, `check: green`,
   `check-exit=0`.
4. Design conformance — PASS. `deadline = clock() + limit_s` before the
   first read; setup reads through `left()` (min(GH_TIMEOUT_S, left), or
   raises before the read); each poll's `budget = min(GH_TIMEOUT_S,
   deadline - clock())`, not started at ≤ 0; `origin_url`/`origin_repo`
   gained a timeout. A setup read cut short exits 2 (§45 "could not
   read"); a poll cut short by the limit exits 3, never a pass ("pending
   (not read before the limit)" when no poll answered); a full 120 s
   checks timeout with time left exits 2. No choice needed a design
   decision. `--stat`: cli.py, forge.py, tests/fake_gh.py,
   tests/test_ci_wait.py, tests/test_doctor.py, all listed; nothing
   forbidden.
Not proven: a stalled real gh or git (process tree holding the pipes);
wall time past the limit beyond the measured < 3 s; that the `timeout=30`
test calls guard anything; timeouts outside the ci-wait and doctor parts.
