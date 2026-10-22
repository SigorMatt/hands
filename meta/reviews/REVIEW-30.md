# REVIEW-30 — cold review of mission 30 (the gate's follow-up before the switch), PR #10

reviewed: b4b01d1322fbdc1d93504f8f2acab709ff66dffb

Shape: pull request (BUILDER-30 §Branch). Branch `mission-30`, PR #10 (base
`main`, head b4b01d1), first review of the branch: base = `git merge-base
origin/main origin/mission-30` = e213c2e. `main`'s rules, read once from
GitHub (`gh api repos/SigorMatt/hands/rules/branches/main`): the read
succeeded and named no rule, so no `pull_request` — this review is committed
to `main` before the merge. The protocol followed is the one on `main` when
this review started (DESIGN §46: "Mission 30's own review runs the protocol
on `main` when it starts, so the rule is in force from mission 31's
review"); §46's defect rule and moved-branch check are therefore not this
review's rules, though their substance was weighed. Commits under review
(`git log e213c2e..origin/mission-30 ^origin/main`):

    b4b01d1 report: mission 30 hosted review dispositions, CI and the PR #10 archive
    5a3a5a4 spool: the named exclusion of a plan file compares casefolded
    676aa1b docs: the moved-branch check comes after the pull, a refused not-merged push recovers
    b1ad99d report: mission 30 final report
    2a2442e docs: the review merges what it reviewed, its failure paths, a defect blocks
    8b3aa60 playbook: the engine approves plan files only
    16723ad kit: case (b) is neither main nor a kit/ branch; [repository] main refused naming the two
    4c769fd plan: mission 30 plan, branch and findings (H-084, H-085)

## Blockers

None.

## Should-fix

1. The `not merged` blocker's refused-push recovery is a design extension
   made without a design decision, and its leftover is open. 676aa1b (hosted
   finding 2/fetch-1 finding 3) applies §46's refused-push steps, which §46
   names for the review's own commit only, to the `not merged` commit's push
   ("the design names them for the review's commit; this applies them to the
   not-merged blocker's push"); no finding records that reading, and its
   main-path leftover is H-086 (open, "needs a design decision": a review on
   `main` whose `not merged` push and rebase both fail leaves local `main`
   ahead, so `git pull --ff-only` diverges). Under §46's defect rule, in
   force from mission 31's review, this is a defect in text this pull request
   adds and would be a blocker; under this review's protocol it is a design
   gap, filed. The next kit amends the design for both (the recovery of the
   `not merged` push, and H-086's reset of local `main` or stop). Two wording
   slips in the same text: the new sentence's parenthesis "(the branch moved
   after the review's commit was pushed)" is wrong on the `main` path, where
   `main` moved; H-086 says "review: commits" where only the `not merged`
   commit is unpushed.
2. The casefolded exclusion of a `send`-named path (5a3a5a4, hosted finding
   4) is a reading of a point §46 leaves silent ("in its exact case" is
   attached to the plan forms; the named exclusion's case is unstated) and
   is in the safe direction (more kits held; `Design.md` and `Meta/x.md`
   still held), but DESIGN.md does not say it and H-083's resolved status in
   meta/findings/FINDINGS.md still describes the exclusion as "not in
   `named`" in exact case. The next kit states it in the design (as H-077
   did for the playbook) and the ledger follows.
3. To be filed: `kit.named_paths` does not normalise the paths a prompt
   names, so a review prompt that names `./meta/REVIEW-PROTOCOL.md` (or
   `meta//REVIEW-PROTOCOL.md`) yields that literal string, and
   `is_plan_file` then treats both `meta/REVIEW-PROTOCOL.md` and
   `meta/review-protocol.md` as plan files — a role kit could overwrite the
   protocol with no human hold. Shown by direct calls in a worktree at
   5a3a5a4 (the 5a3a5a4 sub-agent); not live (no shipped playbook or
   template names `./meta/`), and it is what §46 prescribes ("as `kit
   check`'s `protocol` check finds them"). The named paths should be compared
   normalised (a leading `./` stripped, `//` collapsed).
4. Documentation that reads wrong after U3/676aa1b: the handbook §19 "review
   has blockers" row puts "under `pull_request` that of a missing pull
   request … a Direct brief's under `pull_request`" inside a sentence that
   begins "On any other repository" (repositories without `pull_request`);
   handbook §9's summary says the moved-branch check runs "after the branch
   is checked out and pulled" on both paths, where on the `main` path no
   branch is checked out; and H-082's status in FINDINGS.md lists
   `tests/test_docs_45.py` among its tests, which 16723ad does not touch (it
   pins handbook §3 only by comparison with the constant).
5. To be filed: two texts outside §46's "Documentation" list are now stale,
   as FINAL-REPORT-30 §4 itself says — architect/CLAUDE.md rule 1 still says
   a review with blockers is on the branch only under `pull_request`, while
   the review of a failed rules read now goes to the branch whatever the
   rules; and handbook §7's list of blockers does not name §46's confirmed
   defect. The next kit names them for its documentation list.

## Hosted review

Archive `<k>` = 3 (meta/reviews/hosted/PR-10/3/, 12 files, fetched at
b4b01d1; the builder's fetches 1 at b1ad99d and 2 at 5a3a5a4). `hands
hosted-review 10` exited 0. Verdict, from the Code Review comment
(issue-comment 6330956739, updated_at 2026-10-22T03:47:33Z) only: "1 of 4
findings open in the Code Review comment" — the open one is the dismissed
"Sub-agents edit protected mission metadata". Categories: 🐞 Bugs (0), 📘 Rule
violations (1), 🔗 Cross-repo conflicts (0), 📜 Skill insights (0). Diff
against fetch 2: only the Code Review comment changed (its code links
re-pointed from 5a3a5a4 to b4b01d1); no finding added, dropped or changed
state. The bot renumbered between fetches 1 and 2 (fetch 1's #2 and #3 are
swapped now); the builder's table uses fetch 1's numbers and says so; below,
the bot's current numbers, with the table's row.

1. `<s>Reviewers can merge unreviewed changes</s> <code>✓ Resolved</code>`
   at meta/REVIEW-PROTOCOL.md:270-272 (inline review-comment 4343871272 at
   :272)
   > The moved-branch check compares <b><i>origin/&lt;branch&gt;</i></b> with <b><i>reviewed:</i></b> before the protocol&#x27;s later `git pull --ff-only`, which can advance the local branch after that comparison. If someone pushes in that interval, the review commit is placed on the unreviewed tip, its push succeeds, and <b><i>--match-head-commit</i></b> accepts that review commit for the merge.

   Confirmed → a defect in what the pull request adds (U3's text, 2a2442e;
   the U3 sub-agent found the same gap independently); fixed in 676aa1b,
   not carried. Audit of the builder's disposition (table row 1, "fixed in
   676aa1b"): holds — 676aa1b touches the anchor, the check is now the last
   step before the commit, after the pull, with HEAD (or HEAD^ under the
   `journal:` commit) equal to the reviewed sha; both paths traced with no
   remaining window; the bot shows it resolved; within §46.
2. `<s>A moved head prevents saving the blocker</s> <code>✓ Resolved</code>`
   at meta/REVIEW-PROTOCOL.md:331-335 (inline review-comment 4343871276 at
   :335)
   > The new <b><i>not merged</i></b> path requires a blocker commit on the branch but gives no recovery step if that commit&#x27;s push is refused. When the head moves after the review commit was pushed, <b><i>--match-head-commit</i></b> refuses the merge and the local branch is behind the remote, so pushing the required blocker commit is non-fast-forward.

   Confirmed → a defect in what the pull request adds (U3); fixed in
   676aa1b on the branch path; the design extension and the main-path
   leftover (H-086) carried as should-fix 1. Audit (table row 3, "fixed in
   676aa1b"): fixed at the anchor and the bot shows it resolved, but the fix
   needed a design call — §46's steps extended to the `not merged` push,
   disclosed in the commit body and FINAL-REPORT-30 §4, not filed — and its
   leftover H-086 is filed and open, not mentioned in the table.
3. `Sub-agents edit protected mission metadata <code>📘 Rule violation</code> <code>§ Compliance</code>`
   at meta/plan.md:1-4 (inline review-comment 4343871266 at :4)
   > The U0 plan commit modifies <b><i>meta/plan.md</i></b> and <b><i>meta/CHECKPOINT.md</i></b>, despite the mission&#x27;s standing constraint that sub-agents must not edit those files. Protected planning state can therefore be rewritten by an automated unit, leaving later builders with metadata that does not reflect the designated owner&#x27;s checkpoint or plan.

   Dismissed → the two files are touched only by the orchestrator's
   `plan:`/`report:` commits (4c769fd, b1ad99d, b4b01d1, by `git log
   e213c2e..origin/mission-30 -- meta/plan.md meta/CHECKPOINT.md`), and the
   brief makes U0 the orchestrator's ("U0 is yours, not a sub-agent's").
   Audit (table row 2, "dismissed: …"): the reason is given and holds
   against the disk; same as PR #9's finding 7; still open in the bot's
   comment, as a dismissed finding is.
4. `<s>Role kits can overwrite the review protocol by changing its case</s> <code>✓ Resolved</code>`
   at src/hands/spool.py:188-190
   > <b><i>is_plan_file</i></b> excludes a <b><i>meta/*.md</i></b> entry only when it matches a <b><i>send</i></b>-named path in exact case (<b><i>entry not in set(named)</i></b>), so <b><i>meta/review-protocol.md</i></b> or <b><i>meta/Review-Protocol.md</i></b> counts as a plan file even when the review rule names <b><i>meta/REVIEW-PROTOCOL.md</i></b>. On a case-insensitive builder filesystem (macOS default) the apply&#x27;s <b><i>unzip -o</i></b> writes that entry over the real protocol and commits it. The engine approves the apply with no human hold, so the role can rewrite the reviewer&#x27;s procedure (merge rules, blocker rules). This is the same hole H-077 closed for the playbook by casefolding in <b><i>carries_playbook</i></b>.

   Confirmed → a defect (security gap) in what the pull request adds (U2,
   8b3aa60); fixed in 5a3a5a4, the design's silence on the case carried as
   should-fix 2 and the adjacent `./meta/` gap as should-fix 3. Audit (table
   row 4, "fixed in 5a3a5a4"): fixed at the anchor, correct, the bot shows
   it resolved; a reading of a silent point in the safe direction, disclosed
   in the commit body, docstring and FINAL-REPORT-30 §4, not in DESIGN.md or
   H-083's status.

## Notes

- Gate at the reviewed tip, run once by this review in a worktree at
  b4b01d1 (/tmp/review30-tip): `5475 passed in 497.48s (0:08:17)` / `== cli
  smoke ==` / `check: green`. Every unit commit's gate was green too (see
  the per-commit verdicts).
- No `pull_request` rule on `main`, so the protocol's `hands ci-wait` before
  writing does not apply; for the record, `gh pr view 10` at the time of
  writing: head b4b01d1, `MERGEABLE`, check `check` `SUCCESS` (and
  FINAL-REPORT-30 §CI: `check`, github-actions, app id 15368, success at
  5a3a5a4).
- Non-unit commits: 4c769fd (`plan:`) read for what it says — plan,
  checkpoint, H-081..H-083 decided and scheduled, H-084 and H-085 filed;
  files all under `meta/`. b1ad99d and b4b01d1 (`report:`), `git show
  --stat`: every file under `meta/` (the final report, plan, checkpoint,
  journal, findings, the PR-10 archive 1 and 2) — no forbidden edit. No unit
  commit touches DESIGN.md, meta/plan.md, meta/CHECKPOINT.md, `.github/` or
  `scripts/check`.
- FINAL-REPORT-30 §NOT PROVEN against the sub-agents: confirmed as stated
  (no ruleset, so no apply through a gated pull request and no
  `--match-head-commit` merge observed; the protocol's text pinned, not its
  following; the daemon path of the plan-files hold untested; the refusal
  tested for three value types; casefold on a case-sensitive filesystem
  only; H-086). The sub-agents add: `main = "squash"` was refused before U1
  too (that case guards a regression, it does not prove the change); the
  phone-kit test checks `published_hold_reason` only; `kit check` reads the
  playbook under the repository root but calls `send_named_paths` with
  `--repo`/cwd; the `./meta/` normalisation gap (should-fix 3).
- The defect rule of §46 is not this review's (see the head); weighed by it,
  should-fix 1 (H-086 and the unfiled extension) would be a blocker from
  mission 31's review on.
- Schedule (one sub-agent at a time, so one `./scripts/check` at a time
  inside the gate's 15-minute (900000 ms) timeout):
  - hosted review (PR #10): 06:53:51 – 06:56:46
  - 16723ad (U1): 06:56:58 – 07:06:46
  - 8b3aa60 (U2): 07:06:46 – 07:18:26
  - 2a2442e (U3): 07:18:26 – 07:29:31
  - 676aa1b (U4 fix): 07:29:31 – 07:39:40
  - 5a3a5a4 (U4 fix): 07:39:40 – 07:49:31
  - the reviewer's own gate at b4b01d1: 07:49:31 – 07:57:52

## Per-commit verdicts

### Hosted review sub-agent (PR #10)

I fetched at b4b01d1322fbdc1d93504f8f2acab709ff66dffb; `hands hosted-review 10` exited 0 (`hr-exit=0`) and wrote `<k>` = 3. Each of the bot's four findings has a row in the builder's table. The three fixes touch their anchors and the bot shows them resolved. The one dismissal holds against the disk, and no new finding appeared by id.

Points the reviewer must weigh:
- **Finding 4:** the casefold fix goes against §46's literal "in its exact case".
- **Finding 2:** its fix extends §46's refused-push steps to the `not merged` push.
- **H-086:** a filed, open, blocker-class leftover of the finding 2 fix.

**Fetch:** the worktree is `/tmp/review30-hosted`, at detached `origin/mission-30` = b4b01d1322fbdc1d93504f8f2acab709ff66dffb. It is left in place, and `meta/reviews/hosted/PR-10/3/` is untracked there, ready to copy.

**Command result:**
- The PR has, from qodo-code-review[bot]: issue-comments 2, reviews 1, review-comments 3.
- Archived: `meta/reviews/hosted/PR-10/3/` (12 files: 6 bodies, 6 JSON).
- Summary comment: issue-comment 6330887732.
- Code Review comment: issue-comment 6330956739, updated_at 2026-10-22T03:47:33Z.
- Categories: 🐞 Bugs (0), 📘 Rule violations (1), 🔗 Cross-repo conflicts (0), 📜 Skill insights (0).
- **Diff against 2:** only 6330956739 changed (updated_at 03:14:59Z → 03:47:33Z). The only change is the bot re-pointing its code links from commit 5a3a5a4 to b4b01d1. No finding was added, dropped or changed state.
- **Verdict, taken from the Code Review comment:** "1 of 4 findings open in the Code Review comment". The open one is finding 3.
- The three fetches anchor at: fetch 1 b1ad99d (02:07:24Z, 4 open); fetch 2 5a3a5a4 (03:14:59Z, 1 open); fetch 3 b4b01d1 (03:47:33Z, 1 open).

**Numbering note:** the bot renumbered between fetches 1 and 2. In fetch 1, #2 was "Sub-agents edit…" and #3 was "A moved head…"; now they are swapped. The builder's table uses fetch 1's numbering and says so ("1, 2 (fetch 1's 3) and 4 marked resolved"). Below I use the bot's current numbering and give the table's row number.

#### The bot's findings (verbatim as the command printed them) and my verdict on each disposition

**1.** `<s>Reviewers can merge unreviewed changes</s> <code>✓ Resolved</code>` at meta/REVIEW-PROTOCOL.md:270-272, resolved; inline: review-comment 4343871272 at meta/REVIEW-PROTOCOL.md:272
> The moved-branch check compares <b><i>origin/&lt;branch&gt;</i></b> with <b><i>reviewed:</i></b> before the protocol&#x27;s later `git pull --ff-only`, which can advance the local branch after that comparison. If someone pushes in that interval, the review commit is placed on the unreviewed tip, its push succeeds, and <b><i>--match-head-commit</i></b> accepts that review commit for the merge.

- **Builder (table row 1):** fixed in 676aa1b.
- **My verdict: disposition holds.**
  - 676aa1b touches meta/REVIEW-PROTOCOL.md at the anchor, plus templates/REVIEW-PROTOCOL.md, docs/ARCHITECT-HANDBOOK.md and tests/test_docs_46.py.
  - The check is now the last step before the commit, after the checkout and pull. On the branch path it also requires `git rev-parse HEAD`, or `HEAD^` under the `journal: consultation lines` commit, to equal the reviewed sha.
  - I traced both paths and found no remaining window. On the main path, `--match-head-commit <reviewed sha>` covers it. On the branch path, the commit sits on the reviewed tip, a refused push is the blocker, and the merge matches the review's commit.
  - The bot shows it resolved.
  - This stays inside §46 ("before it commits its file"; §46 does not fix the order relative to the pull).
- **§46 class:** a defect in what the PR adds (U3's text, 2a2442e) → blocker-class. It is fixed.

**2.** `<s>A moved head prevents saving the blocker</s> <code>✓ Resolved</code>` at meta/REVIEW-PROTOCOL.md:331-335, resolved; inline: review-comment 4343871276 at meta/REVIEW-PROTOCOL.md:335
> The new <b><i>not merged</i></b> path requires a blocker commit on the branch but gives no recovery step if that commit&#x27;s push is refused. When the head moves after the review commit was pushed, <b><i>--match-head-commit</i></b> refuses the merge and the local branch is behind the remote, so pushing the required blocker commit is non-fast-forward.

- **Builder (table row 3):** fixed in 676aa1b.
- **My verdict: fixed at the anchor, but the fix needed a design call and only partly got one.**
  - 676aa1b edits the "A merge that is refused or not made" paragraph (old lines 332-336). A refused `not merged` push now takes §46's refused-push steps.
  - §46 names those steps only for the review's own commit. Applying them to the `not merged` push is a design extension. It is disclosed in the commit body and in FINAL-REPORT-30 §4 "Deviations and readings", but not filed.
  - Its leftover was filed as H-086: on the main path, after two refusals, local `main` is left ahead and `git pull --ff-only` fails. H-086 is in meta/findings/FINDINGS.md, open, "needs a design decision", and the table does not mention it. It is the same added text failing its own purpose, so by §46's rule H-086 is a blocker-class defect in what the PR adds, filed and open.
  - Minor wording slip: the new sentence says "(the branch moved…)" even in the case where it was `main` that moved.
  - The bot shows it resolved.
- **§46 class:** a defect in what the PR adds (U3) → blocker-class. It is fixed on the branch path; the main-path leftover (H-086) is open.

**3.** `Sub-agents edit protected mission metadata <code>📘 Rule violation</code> <code>§ Compliance</code>` at meta/plan.md:1-4; inline: review-comment 4343871266 at meta/plan.md:4
> The U0 plan commit modifies <b><i>meta/plan.md</i></b> and <b><i>meta/CHECKPOINT.md</i></b>, despite the mission&#x27;s standing constraint that sub-agents must not edit those files. Protected planning state can therefore be rewritten by an automated unit, leaving later builders with metadata that does not reflect the designated owner&#x27;s checkpoint or plan.

- **Builder (table row 2):** dismissed: meta/plan.md and meta/CHECKPOINT.md were written by the orchestrator in the U0 `plan:` commit (CLAUDE.md "meta/ is the builder's state"); no sub-agent edited them, as PR #9's finding 7.
- **My verdict: the dismissal has a reason, and it holds against the disk.**
  - `git log --format='%h %s' e213c2e..origin/mission-30 -- meta/plan.md meta/CHECKPOINT.md` lists only these three commits, all orchestrator `plan:`/`report:` commits; no unit commit touches the two files:
    - 4c769fd plan: mission 30 plan, branch and findings (H-084, H-085)
    - b1ad99d report: mission 30 final report
    - b4b01d1 report: mission 30 hosted review dispositions…
  - meta/BUILDER-30-PROMPT.md:155 says "U0 is yours, not a sub-agent's: it writes only `meta/`, among it the plan and the checkpoint a sub-agent may not touch".
  - FINAL-REPORT-29 row 7 is the same dismissal ("Mission metadata breaks its own edit rule").
  - It is still open in the bot's comment, as a dismissed finding should be.
- **§46 class:** not a defect.

**4.** `<s>Role kits can overwrite the review protocol by changing its case</s> <code>✓ Resolved</code>` at src/hands/spool.py:188-190, resolved
> <b><i>is_plan_file</i></b> excludes a <b><i>meta/*.md</i></b> entry only when it matches a <b><i>send</i></b>-named path in exact case (<b><i>entry not in set(named)</i></b>), so <b><i>meta/review-protocol.md</i></b> or <b><i>meta/Review-Protocol.md</i></b> counts as a plan file even when the review rule names <b><i>meta/REVIEW-PROTOCOL.md</i></b>. On a case-insensitive builder filesystem (macOS default) the apply&#x27;s <b><i>unzip -o</i></b> writes that entry over the real protocol and commits it. The engine approves the apply with no human hold, so the role can rewrite the reviewer&#x27;s procedure (merge rules, blocker rules). This is the same hole H-077 closed for the playbook by casefolding in <b><i>carries_playbook</i></b>.

- **Builder (table row 4):** fixed in 5a3a5a4.
- **My verdict: fixed at the anchor and correct, but it departs from the design's literal text without a finding.**
  - 5a3a5a4 changes `is_plan_file` in src/hands/spool.py (lines 182-196) to `entry.casefold() not in {name.casefold() for name in named}`, and adds tests/test_plan_files.py.
  - A `Meta/…` prefix fails the exact-case `meta/` test, so it is not a plan file and is held, which is the safe direction.
  - `uv run --extra dev pytest -q tests/test_plan_files.py tests/test_docs_46.py` passed: 124 tests, nothing failed.
  - The bot shows it resolved.
  - However, §46 defines a plan file as one whose path, "in its exact case", is one of the forms, and that includes the `meta/` clause. The builder chose "the stricter reading (casefold, as H-077)". That is disclosed in the commit body, the docstring and FINAL-REPORT-30 §4, but no finding was filed.
  - §46's rule for a defect the design prescribes is "its kit correcting the design first". DESIGN.md's text and the code now disagree.
  - FINDINGS.md H-083's Status still describes the exclusion as "not in `named`" (exact case) and was not updated.
- **§46 class:** a defect in what the PR adds (U2, 8b3aa60, a security gap) → blocker-class. It is fixed in code; the design text still needs correcting.

#### Verdict per audit point
1. **A finding with no row:** none. All four have a row. H-086, born of finding 2's fix, is reported in FINAL-REPORT-30 §3 but not in the table.
2. **A fix that misses its anchor, or that the comment still shows open:** none. 676aa1b touches REVIEW-PROTOCOL.md at both anchors and 5a3a5a4 touches spool.py at its anchor. The bot shows 1, 2 and 4 resolved at b4b01d1.
3. **A dismissal with no reason, or a reason that fails:** none. The one dismissal (bot #3) has a reason, and the git log and BUILDER-30-PROMPT.md:155 confirm it.
4. **A filed finding absent from FINDINGS.md:** none. H-086 is present (meta/findings/FINDINGS.md:3139), open.
5. **A fix that needed a design decision, made without one:** two partial cases. Both are disclosed in commit bodies and FINAL-REPORT-30 §4, but neither is filed:
   - Bot #4 casefolds against §46's literal "in its exact case".
   - Bot #2 extends §46's refused-push steps to the `not merged` push; its main-path leftover is filed as H-086.

   Neither is silent in the strict sense; the reviewer must judge whether a disclosed reading is enough. The table's claim that all three confirmed findings are defects in what the PR adds is correct.
6. **Blocker-class leftover:** H-086 (open) is a defect in text this PR added (676aa1b), so by §46's rule it is blocker-class.

#### Not proven
- That a sub-agent did not write the U0 commit. All commits are authored "Matthew Sigurko"; the evidence is the brief's assignment and the commit prefixes, not who actually wrote it.
- How the casefold fix behaves on a real case-insensitive filesystem, and on Unicode look-alike paths.
- That a reviewer follows the reordered protocol. The tests only pin the sentences and their order.
- That CI is green at b4b01d1. I did not run `ci-wait` or the full gate; I ran only the two test files above.
- Whether the bot would re-raise anything on a fresh full review. It edits its comment in place, and its "resolved" marks are its own judgement.

### 16723ad (U1)

Review of 16723ad: no blockers, one should-fix. The worktree is removed.

**Review: 16723ad** (`kit: case (b) is neither main nor a kit/ branch; [repository] main refused naming the two`)

1. **Unit — OK.** Mission 30 U1, "Case (b), and the setting's refusal". It claims DESIGN §46 "H-082" and review 29's should-fix 3 (§46 item 3), plus §45 "The apply (§27), by the setting" and "The setting". The files it touches match the body and the brief's U1 list: `src/hands/kit.py`, `src/hands/config.py`, `docs/ARCHITECT-HANDBOOK.md`, `meta/findings/FINDINGS.md`, `tests/test_apply_shape.py`, `tests/test_config.py`.
2. **Test-first — RED as expected.** I reverted the 4 non-test files one checkout each (all exist at `~1`) and ran `tests/test_apply_shape.py`, `tests/test_config.py` and `tests/test_docs_45.py`. Four tests failed:
   - `test_the_pull_request_prompt_is_section_45s_word_for_word`
   - `test_the_pull_request_prompts_case_b_is_neither_main_nor_a_kit_branch`
   - `test_a_repository_main_of_any_type_is_refused_naming_the_two[true-True]`
   - `...[1-1]`

   The `["squash"]` case passes on the reverted code, which is expected: the old code already refused strings with this message, so that case guards against a regression rather than proving the change. `test_docs_45` stays green on the revert because handbook §3 is compared to `kit.PULL_REQUEST_APPLY`, and both went back together. After restoring with `git checkout 16723ad -- <file>` for each file, `git status --short` was empty.
3. **Gate — GREEN.** `./scripts/check` at 16723ad ended `5370 passed in 492.82s (0:08:12)`, `== cli smoke ==`, `check: green`, `check-exit=0`.
4. **Design conformance — OK, with one should-fix.**
   - **Case (b) is word for word.** In `PULL_REQUEST_APPLY` it now begins "(b) On a branch that is neither `main` nor a `kit/` one, that is on `origin`", with the backticks the brief asks for. The rest of §45's prompt is unchanged: the word-for-word test rebuilds the expected prompt from §45's block with §46's indented block put in place of the old case (b), and asserts the old opening occurs exactly once.
   - **The phrase is pinned.** A test pins "neither `main` nor a `kit/` one", asserts "another branch" is gone, and checks the filled prompt. Handbook §3 is updated and pinned through `test_docs_45`.
   - **The refusal is right.** `config._choice` refuses any value of any type (bool, int, empty string, unknown string) with `[repository] main must be "direct" or "pull-request", got <repr>`. The default is still `"direct"` (`MAIN_SETTINGS[0]`), and `" direct "` is still stripped and accepted. Showing the value as `repr` is a choice the body discloses (§46 just says `<the value>`).
   - **Every test the brief asks for is present**: the prompt word for word, the phrase pinned, and `true`, `1` and `"squash"` each refused naming both values. `_choice` is registered in the loader-helper scan.
   - **Nothing forbidden touched.** No change to `DESIGN.md`, `meta/plan.md`, `meta/CHECKPOINT.md`, `.github/` or `scripts/check`.

**Should-fix (minor, documentation accuracy):**
- H-082's new Status line in `meta/findings/FINDINGS.md` lists `tests/test_docs_45.py` under "Tests", but the commit does not touch that file. It pins the handbook only indirectly, by comparing it to the constant.
- The handbook edit leaves one over-long wrapped line ("names none `MERGED` or `CLOSED`), a mission is in flight on it: unzip -o into the"). This is cosmetic; the test flattens whitespace, so it does not affect the pin.

**Blockers:** none.

**Not proven:**
- How a real builder on `main` acts on the new prompt; the body says so itself. No test runs the apply end to end under `pull-request`.
- The other forms of case (b), `kit/` exclusion and the `origin`/open-PR conditions, are pinned only as text, not as behaviour.

### 8b3aa60 (U2)

**Review of 8b3aa60, "playbook: the engine approves plan files only"**

1. **Unit:** mission 30 U2, item H-083. The body claims DESIGN §46 "H-083", plus §31, §32, §43 and §45. This matches meta/BUILDER-30-PROMPT.md U2. **PASS.**

2. **Test-first: PASS.** I reverted ten files to 8b3aa60~1, one checkout each: architect/CLAUDE.md, the three docs, FINDINGS.md, kit.py, playbook.py, spool.py and both templates. All ten existed at the parent. Then I ran the six changed or added test files, and they went red:
   - tests/test_plan_files.py fails at collection: `ImportError: cannot import name 'plan_hold_reason' from 'hands.playbook'`.
   - test_docs_45: 2 FAILED (rule 3's plan-files sentence, handbook §3).
   - test_operator_table: 1 FAILED (the §46 row).
   - test_playbook: `..._is_held_as_no_plan_file` FAILED. The 4 `test_each_shipped_playbook_*` failures come from the template revert itself (the loader likely refuses a working copy that differs from HEAD); they are not pins of U2's wording.
   - test_consult and test_apply_not_landed: green, as expected (only fixtures or removals changed there).
   
   After restoring, `git status --short` was empty.

3. **Gate: GREEN.** `5390 passed in 507.04s (0:08:27)` / `== cli smoke ==` / `check: green` / `check-exit=0`.

4. **Design conformance: PASS, no blockers.**
   - **The one test:** `spool.is_plan_file` uses exact case. It accepts KIT.md, DESIGN.md, WORKPLAN.md, a root `decisions-[^/]+\.md`, or a `meta/…*.md` that is not in `named`.
   - **Stored-kit reading:** `Spool.stored_kit_non_plan` reads the central directory and skips directory entries. `stored_kit_files` is an added helper, and the body names it.
   - **Hold reason:** `plan_hold_reason` matches §46 word for word. It names the first entry in sorted order, and §43's reason takes precedence when the kit carries the playbook. `carries_ci`, `stored_kit_ci` and `ci_hold_reason` are removed.
   - **`named`:** `kit.send_named_paths` runs `named_paths` over each `send` rule's prompt and leaves placeholder paths out. The engine uses `_book_in_force()`, the repository's playbook, never the kit's. `kit check` uses the first repository playbook that loads, in the order configured path, PLAYBOOK.toml, meta/PLAYBOOK.toml; the design is silent there and the body says so. The import inside the function is named in the body, as §46 requires.
   - **`kit check`:** prints one `WARN owner:` line under `WARN playbook:`'s condition, and the `--json` key `ci_warnings` is now `owner_warnings`.
   - **architect/CLAUDE.md:** rule 3 is word for word. The parenthesis, the PLAYBOOK.toml sentence and the `.github/` clause are gone, and the rest of the rule stays. Rule 8 gains "a kit that would need a file other than a plan file (rule 3)".
   - **Documentation:** handbook §3 keeps the architect's `.github/` and `scripts/check` rule. §12 and §19, docs/PLAYBOOK.md, docs/INTEGRATION.md and both template comments are updated as §46 "Documentation" lists.
   - **Tests the brief asks for:** all present in tests/test_plan_files.py — the approved plan kit, WORKPLAN.md and the decisions file, all 12 held paths with no kickoff after a human's approval, the two playbook kits held with §43's reason, `WARN owner:` for role-mode autonomous and none for phone mode, the §19 row as route 2 then `go`, and the phone kit.
   - **Forbidden files:** DESIGN.md, meta/plan.md, meta/CHECKPOINT.md, `.github/` and `scripts/check` are all untouched. The body's file list matches `git show --stat` (17 files).

**Should-fix (minor, not a blocker):**
- `test_an_ordinary_phone_kit_is_unchanged` only checks that `published_hold_reason` returns None for a held kit with origin `kit`. It does not apply a phone kit end to end, so "unchanged" is weakly shown.
- In `_plan_warning`, the configured playbook is read under the repository root, but `send_named_paths` is called with `repo` (the `--repo`/cwd path). This only matters when the cwd sits below the root. The body lists that case as not proven.

**Not proven:**
- The daemon end to end with a held non-plan kit (the body says so).
- `named` with a builder cwd below the repository root (the body says so).
- A prompt that names a file in another form (for example `./meta/REVIEW-PROTOCOL.md`) is not normalised, so that file would count as a plan file. This is consistent with §46's "as `kit check`'s `protocol` check finds them", but no test covers it.

The worktree /tmp/review30-8b3aa60 has been removed.

### 2a2442e (U3)

Review of 2a2442e ("docs: the review merges what it reviewed, its failure paths, a defect blocks"). All four points pass, and nothing reaches blocker level. I raise one should-fix and two minor ones.

1. **Unit and sections: OK.** This is mission 30 U3. It claims DESIGN §46 "H-081", "Review 29's should-fix items" 2 and 4, and "A confirmed bug in the pull request's own code blocks its merge", plus §35 and §45 "The review". It covers items H-081, H-084 and H-085. This matches the brief's U3.

2. **Test-first: red, as expected.** All five non-test files exist at 2a2442e~1. I reverted each one with its own checkout: templates/REVIEW-PROTOCOL.md, meta/REVIEW-PROTOCOL.md, templates/BUILDER-N-PROMPT.md, docs/ARCHITECT-HANDBOOK.md and meta/findings/FINDINGS.md. `uv run pytest -q` on tests/test_docs_46.py, tests/test_docs_45.py, tests/test_docs.py and tests/test_kit.py then went red:
   - every case of test_docs_46: each PROTOCOL_46 key in both protocols, the old "nowhere" being gone, the check-before-commit order, the end section, the brief sentence, and the handbook §9 and §19 pins;
   - test_docs_45's two moved missing-PR pins;
   - test_docs.py::test_the_handbook_section_9_is_the_pull_request_flow_of_section_35;
   - test_kit.py::test_the_protocol_template_finds_the_pr_reads_the_hosted_review_and_merges.

   I restored each file with its own checkout of 2a2442e, and `git status --short` was empty afterwards. The existing whole-file equality test at tests/test_docs.py:2160 checks that the template and the meta copy agree.

3. **Gate at 2a2442e: green.** `5459 passed in 507.29s (0:08:27)` / `== cli smoke ==` / `check: green` / `check-exit=0`.

4. **Design conformance: conforms, with the should-fix below.**
   - The text matches §46: the moved-branch blocker wording, the refused-push steps (rebase, `review: mission N (branch moved)`, `git rebase --abort`, back to main, `git branch -f <branch> origin/<branch>`), the `--match-head-commit` merge with the reviewed tip on main or the review's own commit on the branch, `not merged` with or without the rule committed where the review was, and the failure paths (failed rules read whatever the rules, missing PR under `pull_request` to the branch via ls-remote, never main, else nowhere; Direct under `pull_request` nowhere).
   - Also matching: `## The end (every shape)`, the defect definition with its three cases, and the Hosted review saying which case and why.
   - The brief template's new sentence comes directly after the intact "never fixed in silence" one. Handbook §9 and §19 are updated.
   - The template and the meta copy differ only in owner/repo and the timeout.
   - Under a failed rules read, a Direct brief's review goes nowhere. The design does not say this; the body declares it as the builder's choice.
   - The commit touches no DESIGN.md, meta/plan.md, meta/CHECKPOINT.md, `.github/` or `scripts/check`. Nothing in the body is contradicted by the disk.

**Should-fix 1: a timing gap in the moved-branch check (pull_request shape).**
- The check paragraph (templates/REVIEW-PROTOCOL.md:268-285) comes before the step "git checkout <branch> && git pull --ff-only" (line 298). A reviewer following the text in order fetches and compares, and only then pulls.
- If a commit lands on the branch between the compare and the pull, the fast-forward pull silently takes it in. The review's commit then pushes without refusal, so the refused-push path never fires.
- The merge's `--match-head-commit` names the review's own commit, so gh merges the unreviewed commit beneath it. That is H-081's hole, narrowed to a short window.
- §46 orders it the same way ("before it commits its file"), and test_the_moved_branch_check_comes_before_the_reviews_commit only pins the text order.
- Fix: after the pull on the branch, require `git rev-parse HEAD^` (or HEAD before the review's commit) to equal the `reviewed:` sha, or check out the reviewed sha instead of pulling.
- Under the protocol's own new defect rule, this is arguably a blocker: a security gap in added text, even though the design prescribes it. The lead reviewer should decide, and the fix would need §46 changed first.

**Should-fix 2 (minor): the handbook §19 "review has blockers" row is self-contradictory.** It puts "under `pull_request` that of a missing pull request … a Direct brief's under `pull_request`" inside the sentence that begins "On any other repository", which means repositories without `pull_request`. The meaning can be recovered, but it reads wrong.

**Nit:** in the protocol's Hosted review dispositions (line 255), "which case of 'A defect' it is" fits badly for a confirmed finding that is not a defect, such as a missing test.

**Not proven:**
- that a reviewer follows the text;
- that gh's `--match-head-commit` refuses a moved head (the body says so too);
- that the refused-push rebase recovery works with the carried `journal:` commit;
- handbook §7 and architect/CLAUDE.md rule 1 do not mention the defect blocker. The body declares them unchanged, and I found no other blocker list that contradicts the change.

The worktree /tmp/review30-2a2442e has been removed.

(Reviewer's note: should-fix 1 of this report is the hosted reviewer's finding 1, fixed at the tip by 676aa1b; not carried.)

### 676aa1b (U4, hosted findings 1 and 3)

**676aa1b**: docs: the moved-branch check comes after the pull, a refused not-merged push recovers

1. **Unit: PASS.** U4 fixes PR #10's hosted findings 1 and 3 (archive meta/reviews/hosted/PR-10/1/). It claims DESIGN §46 "H-081" and §45 "The review". Files: meta/REVIEW-PROTOCOL.md, templates/REVIEW-PROTOCOL.md, docs/ARCHITECT-HANDBOOK.md, tests/test_docs_46.py. The body lists exactly the files `--stat` shows.
2. **Test-first: PASS (red when reverted).** I put the three doc files back to 676aa1b~1 one at a time. `uv run pytest -q tests/test_docs_46.py` then gave 12 FAILED: the 5 new pins x {templates, meta} in test_both_protocols_carry_section_46s_review, plus test_the_moved_branch_check_comes_after_the_pull[templates] and [meta]. That matches the body's "all twelve". After restoring, `git status --short` was empty.
3. **Gate at 676aa1b: GREEN.** `5471 passed in 509.91s (0:08:29)` / `== cli smoke ==` / `check: green` / `check-exit=0`.
4. **Design conformance: PASS with should-fixes.**
   - **Finding 1 is closed on both paths.**
     - File to main: the check now runs after `git checkout main && git pull --ff-only` and before the commit. The merge was already pinned to the reviewed sha by `--match-head-commit`.
     - File to branch: the check runs after the checkout and pull. It requires origin/<branch> == the whole reviewed sha, and HEAD == reviewed, or HEAD^ == reviewed when HEAD is the `journal: consultation lines` commit. So the review's commit sits on the reviewed tip, with or without the journal commit.
     - A push after the check is refused and goes to the existing branch-moved path. The merge then names the review's own commit.
     - The HEAD condition is a refinement of §46's "before it commits its file"; it does not contradict §46.
   - **Finding 3 goes beyond §46.** §46 gives the refused-push steps only for the review's commit. Applying them to the `not merged` push is a design decision. The body says so openly, but no finding records it; H-086 covers only the main-path leftover. Not a blocker: nothing in §46 is contradicted.
   - **H-086 is correct in substance.** On main, after the failed rebase/push, the not-merged commit stays on local main and `git pull --ff-only` diverges. Two small points:
     - Only one commit is unpushed there (`not merged`; `review: mission N` was already pushed), not "review: commits".
     - "can fail" fits: when the rebase fails, the pull diverges for certain; only when the rebase succeeds but the push fails for another reason is local main ahead without a failing pull.
   - **Template and meta agree** except owner/repo (lines 24, 92-94) and the timeout (lines 123, 141, 184, 264).
   - **Forbidden files: none touched.** No DESIGN.md, meta/plan.md, meta/CHECKPOINT.md, .github/ or scripts/check.

**Should-fix**
- **S1:** File a finding, or have the next kit amend §46, for the not-merged refused-push recovery the protocol now prescribes. It is a design gap filled by the builder (676aa1b body: "the design names them for the review's commit; this applies them to the not-merged blocker's push").

**Nits (not raised)**
- In the main case the new sentence's parenthesis "(the branch moved after the review's commit was pushed)" is wrong: there the refused push is to `main`, because `main` moved.
- The handbook §9 summary says the check runs "after the branch is checked out and pulled" for both paths. On the main path the branch is not checked out.
- For a HEAD mismatch, "<its tip>" in the blocker text does not say whether it means local HEAD or origin.
- One protocol line is unwrapped ("<reviewed sha> → <its tip>", commit the file as below, ...).

**Not proven**
- The tests only check that these sentences exist and come in this order. They do not show that a reviewer follows them.
- No run against real GitHub: no `--match-head-commit` refusal, no refused push, no rebase recovery.
- The journal-commit ordering is not exercised, including the pre-existing double checkout between "Carrying the journal's lines over" and the pull paragraph.
- No review step handles a failed `git pull --ff-only` before the check; this predates the commit.

The worktree /tmp/review30-676aa1b has been removed.

### 5a3a5a4 (U4, hosted finding 4)

**Review of 5a3a5a4**: `spool: the named exclusion of a plan file compares casefolded`

1. **Unit and sections: PASS.** This is U4 of meta/BUILDER-30-PROMPT.md. It fixes PR #10's hosted finding 4 ("Role kits can overwrite the review protocol by changing its case"). It claims DESIGN §46 "H-083" and follows §44's H-077 casefold precedent. The body lists src/hands/spool.py (`is_plan_file`) and tests/test_plan_files.py, which matches `--stat` (2 files, +57/-2).

2. **Test-first: PASS.** I reverted only src/hands/spool.py to 5a3a5a4~1 and ran `uv run pytest -q tests/test_plan_files.py -k another_case`. All 4 new tests failed: the two parametrized `test_a_named_path_in_another_case_is_not_a_plan_file` cases, `test_a_kit_carrying_the_named_protocol_in_another_case_is_held`, and `test_kit_check_warns_owner_for_the_named_protocol_in_another_case` (`ValueError: not enough values to unpack`). With the file restored, the same 4 pass. `git status --short` was empty after the restore.

3. **Gate at 5a3a5a4: GREEN.** `5475 passed in 502.26s (0:08:22)` / `== cli smoke ==` / `check: green` / `check-exit=0`.

4. **Design conformance: PASS, with one should-fix.**
   - **Reading of §46.** The phrase "in its exact case" is attached to the plan forms, and its stated reason ("a Linux builder lands `Design.md` beside `DESIGN.md`") is about being too generous to forms like `Design.md`. §46 never says what case the named exclusion should compare in, so casefolding it is a reading of a silent point, not a violation.
   - **Direction.** It is the safe direction. More entries fail the plan test, so more kits are held. The plan forms stay exact case (`Design.md` is still not a plan file), and an entry like `META/x.md` still fails the `meta/` prefix test and is held. The choice matches H-077 for `carries_playbook`.
   - **Ledger.** No finding was filed for this reading, and H-083's status line in FINDINGS.md (resolved by U2) was not updated to mention the casefold. The reading is recorded only in the commit body, the `is_plan_file` docstring and FINAL-REPORT-30.md's NOT PROVEN / deviations section (b4b01d1). That is acceptable because DESIGN is silent here, but it is a small gap in the ledger.
   - **`kit check` WARN owner.** It uses the same test: kit.py:1038-1043 calls `send_named_paths` and then `is_plan_file`, the same pair the engine uses (playbook.py:2659-2667 into spool.py:645). The new kit-check test exercises it.
   - **Forbidden files.** Nothing forbidden was touched: no change to DESIGN.md, meta/plan.md, meta/CHECKPOINT.md, `.github/` or scripts/check.

**Should-fix: a path the fix misses.** This is not a blocker because it predates this commit and is literally what §46 prescribes ("as `kit check`'s protocol check finds them"). `named_paths` does not normalise paths. I ran it against a repo holding `meta/REVIEW-PROTOCOL.md`:
- The prompt `Follow ./meta/REVIEW-PROTOCOL.md now.` yields `{'./meta/REVIEW-PROTOCOL.md'}`.
- The prompt `meta//REVIEW-PROTOCOL.md` yields `{'meta//REVIEW-PROTOCOL.md'}`.
- In both cases `is_plan_file` returns True for `meta/review-protocol.md` and also for the exact-case `meta/REVIEW-PROTOCOL.md`.

So a playbook whose review prompt names the protocol through `./` (or a doubled slash) lets the engine approve a kit that overwrites the protocol with no human hold. The shipped templates and PLAYBOOK.toml contain no `./meta/`, so it is not live today. A finding should be filed: compare the named paths in normalised form, at least stripping a leading `./` and collapsing `//`.

**Blockers:** none.

**Not proven:**
- Behaviour on a real case-insensitive filesystem; the suite runs on a case-sensitive one, as the body says.
- Casefold is not Unicode normalisation (NFC/NFD names on macOS).
- The `./` gap is shown through direct calls to `named_paths` and `is_plan_file`, not end to end through the engine.

The worktree /tmp/review30-5a3a5a4 is removed. Nothing was committed or pushed.
