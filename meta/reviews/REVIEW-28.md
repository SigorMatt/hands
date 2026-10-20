# REVIEW-28 — cold review of mission 28 (a pause that holds the next step), PR #8

reviewed: 45ed9c90002079771b7009cab92137618d4e0576

Shape: pull request (BUILDER-28 §Branch). Branch `mission-28`, PR #8 (base
`main`), first review of the branch: base = `git merge-base origin/main
origin/mission-28` = b943019. Commits under review (`git log
b943019..origin/mission-28 ^origin/main`):

    45ed9c9 report: mission 28 hosted review dispositions and the PR #8 archive
    885f07c daemon: a hold decided while its reason is computed is never announced; the owner's WARN reads the configured playbook at the repository root
    58deee7 playbook: a pause over the human pause records nothing; at rest after a start or a failed §6 resume; a refused resume keeps the playbook
    8453b8a report: mission 28 final report
    d20e511 kit: the playbook carried in any letter case or at the configured path is the owner's
    0892937 daemon: §43's hold reason off the event loop; doctor --live turns built as a job's env
    adb061b playbook: a human pause publishes `hands: at rest`; the docs and §19's titles
    d367373 playbook: a human pause holds the next step and resume replays it
    4fed073 plan: mission 28 plan, branch and findings (H-078 filed, H-077 decided)

## Blockers

None.

## Should-fix

1. §44 rule 4 republishes `hands: at rest` only "when a kept end is
   replaced after it" (`_keep` clears the mark on a replacement only,
   src/hands/playbook.py, U2 adb061b). An end of a role with nothing kept
   yet that is kept after `at rest` has been published — e.g. the human's
   own cli send to the aux under the pause, which does not un-pause it, and
   whose `aux.done` is then kept — publishes nothing, so the list the human
   (or a project chat guarding on `at rest`) relies on is stale. The code
   follows the design's letter; the gap is in §44 itself: file a finding
   for the architect (republish when the kept list changes after the mark,
   not only on a replacement).
2. meta/FINAL-REPORT-28.md §4 "Deviations — where §44 is silent" lists
   U1–U4's readings only and omits 58deee7's design-silent choice (under a
   human pause with the playbook file present but not loading, a role's end
   is kept, its §10 decision being the load's stop). The choice is named in
   58deee7's body and judged sound by its sub-agent, but the report's list
   of silent readings is incomplete.

## Hosted review

Archive `meta/reviews/hosted/PR-8/5/` (this review's fetch, at 45ed9c9;
the builder's fetches 1..4 are on the branch). Verdict taken from the Code
Review comment (issue-comment 6278731380, updated 2026-10-20T00:24:29Z):
1 of 7 findings open (finding 7, dismissed by the builder). Header: 🐞 Bugs
(0), 📘 Rule violations (0), 🔗 Cross-repo conflicts (1), 📜 Skill insights
(0); at fetch 1 (8453b8a): Bugs 5, Rule violations 1, Cross-repo conflicts
1. Numbering below is the comment's current order; the builder's table
uses fetch 1's (current → builder: 1→2, 2→4, 3→3, 4→6, 5→1, 6→5, 7→7).

1. "Decided jobs receive late hold notices" (✓ Resolved), src/hands/api.py:446-447 —
   "Api.send and _publish_held await held-reason computation, then announce a hold without rechecking the job’s gate or current state. If another client approves or denies the job during that wait, the later notification describes a hold that no longer exists and can create new approval buttons."
   → confirmed and fixed in 885f07c (builder #2); not carried. Audit: OK —
   885f07c touches the anchor (`still_held`), the comment shows it resolved;
   885f07c's sub-agent confirms the five new tests red without the fix.
2. "A failed retry hides the quiet moment" (✓ Resolved), src/hands/playbook.py:3581-3583 —
   "check_at_rest excludes a pause while a limit-resume task is scheduled, but nothing checks again when _resume_after fails without creating a job. If the retry fails while no other job is active, its suppressed stop is announced but the human never receives the at-rest notification for that pause."
   → confirmed and fixed in 58deee7 (builder #4); not carried. Audit: OK
   (`on_no_resume` / `_resume_ended` wired to `check_at_rest`).
3. "Restarts can miss the quiet moment" (✓ Resolved), src/hands/playbook.py:3575-3582 —
   "check_at_rest runs when a pause is sent or a job ends, but startup does not run it for a restored human pause after resolving pending retries. If a pending limited job is not rescheduled and all persisted jobs are terminal, the unset at-rest mark has no subsequent job transition to trigger the notification."
   → confirmed and fixed in 58deee7 (builder #3); not carried. Audit: OK
   (`check_at_rest` after the daemon's start fold).
4. "Ends arriving after a refused resume are lost" (✓ Resolved), src/hands/playbook.py:3503-3508 —
   "resume calls _load(stop_on_error=False), and a failed load sets self.playbook = None before it returns, while the human pause stays. After that, _under_human_pause returns early on `book is None, so a builder/aux/driver end that arrives later is neither kept nor notified, and resume` rules on orphaned or failed jobs stop firing; the next successful resume then has nothing to replay." (the bot's markup garbled, as printed)
   → confirmed and fixed in 58deee7 (builder #6); not carried (U1's
   sub-agent found the same defect independently at d367373). Audit: OK, with
   the note carried as should-fix 2 (the design-silent `load_error` reading
   absent from the report's §4).
5. "Repeated pauses create false stop events" (✓ Resolved), src/hands/playbook.py:3478-3480 —
   "PlaybookEngine.pause() passes quiet=True for an already paused pipeline, but stop() still appends pipeline.stop_suppressed before checking that flag. A repeated pause therefore creates a suppressed-stop record even though the pause is meant to be a no-op, affecting the inbox and stop history without notifying the operator."
   → confirmed and fixed in 58deee7 (builder #1); not carried. Audit: OK —
   matches §44 rules 2 and 3.
6. "Nested builders miss a playbook warning" (✓ Resolved), src/hands/kit.py:913-917 —
   "_owner_warning joins the repository-relative configured playbook path to its repo argument, but daemon-side kit filing passes the builder's working directory rather than the repository root. When that directory is below the root and the kit changes a custom-path playbook, the check looks beneath the directory twice and can omit the warning that the current autonomous playbook requires human ownership."
   → confirmed and fixed in 885f07c (builder #5); not carried. Audit: OK
   (`_repository_root`; fallback named in the body and NOT PROVEN).
7. "Owner kits suggest a refused command" (🔗 Cross-repo conflict, open), src/hands/playbook.py:2082-2083 —
   "_under_human_pause fires Discotrade’s builder.done kit-applied notification immediately, leaving its instruction to send go unchanged. When an owner decisions kit finishes during a human pause, go is refused until the operator sends resume."
   → dismissed: it is DESIGN §44 rule 3 (a decisions kit applied at rest
   commits and the kept end still waits; `go` refused under a human pause
   naming `resume`; "after approving the apply, the human sends `resume`,
   then `go`"), and the text is another project's playbook, not this
   repository's. Audit: OK, the builder's dismissal holds; not proven
   whether the other project's owner is told to change its notify text.

## Notes

- Gate at the tip (`/tmp/review28-tip` at 45ed9c9), my one run:
  `5137 passed in 451.32s (0:07:31)`, `== cli smoke ==`, `check: green`.
- Meta commits read for forbidden edits (`git show --stat`): 4fed073
  (`plan:`), 8453b8a and 45ed9c9 (`report:`) list only files under `meta/`.
  4fed073 read for what it says: H-078 filed, H-077 decided, plan and
  checkpoint written. No human-supplied commit.
- U1's sub-agent found at d367373 that an end arriving while the playbook
  does not load was dropped, and U3's found a race between the hold reason's
  await and a decision; both are the hosted findings 4 and 1 above, fixed at
  the tip by 58deee7 and 885f07c and tested there, so neither is carried.
  U2's should-fix (a), no `at rest` check after a failed §6 resume, is hosted
  finding 2, fixed in 58deee7.
- FINAL-REPORT-28 §NOT PROVEN read against the sub-agents: consistent. The
  spawn-failure `at rest` check is wired and untested (report and U2's
  sub-agent agree); `defer_hold`'s `kit_apply_problem` on the loop reads no
  zip (U3's sub-agent confirms); no case-insensitive filesystem tried. Not
  carried beyond that: an entry reaching the playbook through a symlinked
  directory is not caught by the name test (outside H-077's ruling, which is
  about names; U4's sub-agent); a hold published then decided during the
  start's fold can still be listed in the start notification's held list
  (a stale title, not an announcement; 885f07c's sub-agent).
- Schedule (one sub-agent at a time, one `./scripts/check` at a time):
  - hosted-review sub-agent: 03:24:52 – 03:26:47
  - d367373 (U1): 03:26:47 – 03:47:51
  - adb061b (U2): 03:47:51 – 04:16:11
  - 0892937 (U3): 04:16:11 – 04:27:07
  - d20e511 (U4): 04:27:07 – 04:38:25
  - 58deee7 (U5, hosted fixes 1, 3, 4, 6): 04:38:25 – 04:49:36
  - 885f07c (U5, hosted fixes 2, 5): 04:49:36 – 05:02:15
  - my tip gate: 05:02:15 – 05:09:50

## Per-commit verdicts

### Hosted-review sub-agent (PR #8, at 45ed9c9, wrote `<k>` = 5)

I fetched PR #8 at head **45ed9c90002079771b7009cab92137618d4e0576** and wrote archive **`<k>` = 5**, at `meta/reviews/hosted/PR-8/5/` in /tmp/review28-hosted. The command exited 0. It took the verdict **1 of 7 findings open** from the Code Review comment: only finding 7, which the builder dismissed. All seven findings have a correct disposition: the six fixes touch their anchors and are struck through as resolved, and the dismissal holds against DESIGN §44. The one gap is that the report's deviations list leaves out one design-silent choice made in a fix (audit point 5).

- **Worktree:** /tmp/review28-hosted, detached at `origin/mission-28`, sha 45ed9c90002079771b7009cab92137618d4e0576. Nothing committed and the worktree is left in place. `git status --short` shows only `?? meta/reviews/hosted/PR-8/5/`.
- **Command:** `uv run hands hosted-review 8; echo "hr-exit=$?"` gave `hr-exit=0` on the first run, with no wait.
- **Fetch:** `qodo-code-review[bot]`: issue-comments 2, reviews 1, review-comments 7. Summary comment is issue-comment 6278653866. Code Review comment is issue-comment 6278731380, updated_at 2026-10-20T00:24:29Z. The bot re-read the PR at 45ed9c9, the head under review; the comment's trailing commit link now names it.
- **Archive written:** `meta/reviews/hosted/PR-8/5/`, 20 files: 10 bodies plus their JSON.
- **Verdict from the Code Review comment:** 1 of 7 findings open (finding 7).
- **Header categories:** 🐞 Bugs (0), 📘 Rule violations (0), 🔗 Cross-repo conflicts (1), 📜 Skill insights (0). Fetch 1, at 8453b8a, showed Bugs 5, Rule violations 1, Cross-repo conflicts 1, Skill insights 0.
- **Diff against fetch 4:** only issue-comment 6278731380 changed. Every permalink moved from 885f07c to 45ed9c9, plus the tip line and the commit link. No finding's status changed between fetch 4 and fetch 5.

**Numbering.** The command numbers findings in the comment's current order. The builder's table uses fetch 1's numbering, and says so. The mapping (current → builder) is: 1→2, 2→4, 3→3, 4→6, 5→1, 6→5, 7→7. I checked this against the `<summary>` lines of fetch 1 and fetch 5.

Findings, verbatim as the command printed them:

1. `<s>Decided jobs receive late hold notices</s> <code>✓ Resolved</code>` at src/hands/api.py:446-447 — resolved — inline: review-comment 4319501181 at src/hands/api.py:452
   "<b><i>Api.send</i></b> and <b><i>_publish_held</i></b> await held-reason computation, then announce a hold without rechecking the job’s gate or current state. If another client approves or denies the job during that wait, the later notification describes a hold that no longer exists and can create new approval buttons."
   - Builder: #2, fixed in 885f07c.
   - Verdict: **OK.** 885f07c adds a hunk at api.py `@@ -446,0 +447,5 @@` (the anchor) and daemon.py `@@ -432,2 +432,21 @@` (`still_held`). The comment shows it resolved.
2. `<s>A failed retry hides the quiet moment</s> <code>✓ Resolved</code>` at src/hands/playbook.py:3581-3583 — resolved — inline: review-comment 4319501194 at src/hands/playbook.py:3599
   "<b><i>check_at_rest</i></b> excludes a pause while a limit-resume task is scheduled, but nothing checks again when <b><i>_resume_after</i></b> fails without creating a job. If the retry fails while no other job is active, its suppressed stop is announced but the human never receives the at-rest notification for that pause."
   - Builder: #4, fixed in 58deee7.
   - Verdict: **OK.** 58deee7 adds `on_no_resume` and `_resume_ended` in limits.py, wired to `check_at_rest` in daemon.py. The anchor names `check_at_rest`'s exclusion; the fix is the missing re-check on the path the finding names. The comment shows it resolved.
3. `<s>Restarts can miss the quiet moment</s> <code>✓ Resolved</code>` at src/hands/playbook.py:3575-3582 — resolved — inline: review-comment 4319501186 at src/hands/playbook.py:3598
   "<b><i>check_at_rest</i></b> runs when a pause is sent or a job ends, but startup does not run it for a restored human pause after resolving pending retries. If a pending limited job is not rescheduled and all persisted jobs are terminal, the unset at-rest mark has no subsequent job transition to trigger the notification."
   - Builder: #3, fixed in 58deee7.
   - Verdict: **OK.** 58deee7 adds `check_at_rest` after the daemon's start fold, which is the startup path the finding names. The comment shows it resolved.
4. `<s>Ends arriving after a refused resume are lost</s> <code>✓ Resolved</code>` at src/hands/playbook.py:3503-3508 — resolved — inline: review-comment 4319501206 at src/hands/playbook.py:3523
   "<b><i>resume</i></b> calls <b><i>_load(stop_on_error=False)</i></b>, and a failed load sets <b><i>self.playbook = None</i></b> before it returns, while the human pause stays. After that, <b><i>_under_human_pause</i></b> returns early on `book is None<b><i>, so a builder/aux/driver end that arrives later is neither kept nor notified, and </i></b>resume` rules on orphaned or failed jobs stop firing; the next successful <b><i>resume</i></b> then has nothing to replay." (The bot's own markup is garbled here, printed as is.)
   - Builder: #6, fixed in 58deee7.
   - Verdict: **OK, with a note.** 58deee7 touches the anchor (`@@ -3502,0 +3514,3`, `-3504,0 +3519`, `-3510,0 +3526`). `resume` now saves and restores `(playbook, load_error, _loaded)` on refusal, and `_under_human_pause` is changed at `@@ -2063`/`-2064`. The comment shows it resolved.
   - The fix makes one choice where the design is silent: with `load_error` set, a role's end is kept. That choice is named in the commit body but missing from FINAL-REPORT-28 §4 "Where §44 is silent", which lists only U1–U4 readings. See audit point 5.
5. `<s>Repeated pauses create false stop events</s> <code>✓ Resolved</code>` at src/hands/playbook.py:3478-3480 — resolved — inline: review-comment 4319501178 at src/hands/playbook.py:3480
   "<b><i>PlaybookEngine.pause()</i></b> passes <b><i>quiet=True</i></b> for an already paused pipeline, but <b><i>stop()</i></b> still appends <b><i>pipeline.stop_suppressed</i></b> before checking that flag. A repeated pause therefore creates a suppressed-stop record even though the pause is meant to be a no-op, affecting the inbox and stop history without notifying the operator."
   - In fetch 1 this was a 📘 Rule violation citing "Rule 3263077: Code must conform to DESIGN.md unless explicitly excepted in FINDINGS.md".
   - Builder: #1, fixed in 58deee7.
   - Verdict: **OK.** 58deee7 rewrites the anchor (`@@ -3478,3 +3486,6`): `pause` over a human pause returns `already_stopped` without calling `stop()`, and `quiet` is removed from `stop()` (`@@ -3426,2`, `-3433`). This matches §44 rules 2 and 3 ("Two no-ops are not stops and are not notified: a `pause` over the human pause..."). The comment shows it resolved.
6. `<s>Nested builders miss a playbook warning</s> <code>✓ Resolved</code>` at src/hands/kit.py:913-917 — resolved — inline: review-comment 4319501199 at src/hands/kit.py:917
   "<b><i>_owner_warning</i></b> joins the repository-relative configured playbook path to its <b><i>repo</i></b> argument, but daemon-side kit filing passes the builder&#x27;s working directory rather than the repository root. When that directory is below the root and the kit changes a custom-path playbook, the check looks beneath the directory twice and can omit the warning that the current autonomous playbook requires human ownership."
   - Builder: #5, fixed in 885f07c.
   - Verdict: **OK.** 885f07c touches the anchor (kit.py `@@ -914,2 +924,10`, `@@ -917 +935`) and adds `_repository_root` at `@@ -891,0 +892,10`. The comment shows it resolved. The design-silent fallback (no git root means the argument is the root) is named in the commit body and in NOT PROVEN.
7. `Owner kits suggest a refused command <code>🔗 Cross-repo conflict</code> <code>≡ Correctness</code>` at src/hands/playbook.py:2082-2083 — inline: review-comment 4319501211 at src/hands/playbook.py:2092
   "<b><i>_under_human_pause</i></b> fires Discotrade’s <b><i>builder.done</i></b> kit-applied notification immediately, leaving its instruction to send <b><i>go</i></b> unchanged. When an owner decisions kit finishes during a human pause, <b><i>go</i></b> is refused until the operator sends <b><i>resume</i></b>."
   - Still **open** in the Code Review comment. The bot rated relevance "●● Moderate" and itself recommends "Update Discotrade's notification ... Keep the immediate notification behavior in hands."
   - Builder: #7, dismissed. Reason: §44's rule; the notify text belongs to another project's playbook.
   - Verdict: **OK, the dismissal holds.** DESIGN.md §44 rule 3 (line ~3527): "a decisions kit applied at rest commits and the kept end still waits. `go` and `consult` are refused under a human pause ... naming `resume`". DESIGN.md line 3573-3575: "after approving the apply, the human sends `resume`, then `go`." The text in question is in SigorMatt/discotrade PLAYBOOK.toml [35-42], not in this repository.
   - Not proven: the dismissal does not record whether anyone will tell the discotrade owner to change that text.

Audit per point:

1. **Every finding has exactly one row: OK.** There are 7 findings and 7 rows. The numbering is fetch 1's and is stated as such.
2. **Each fix touches its anchor and the comment no longer shows it open: OK.** All six fixes touch their anchor or the code path the finding names, and all six are struck through and `✓ Resolved` in fetch 5. The bot re-read the PR at 45ed9c9.
3. **The dismissal has a reason that holds against §44: OK.** Finding 7's reason cites §44 rule 3 and the "resume, then go" sentence, and both check out.
4. **Filed findings exist in FINDINGS.md: not applicable.** No H-nnn was filed for a hosted finding. In the mission's FINDINGS.md diff, H-077 and H-078 were only moved to resolved.
5. **No design decision fixed in silence: OK, with one gap.** Both fix commits name their design-silent choices in their bodies, so nothing was fixed in silence: 58deee7, finding 4 (command #4 / builder #6): a role's end is kept while `load_error` is set; 885f07c, finding 6 (command #6 / builder #5): the git-root fallback. The gap is that FINAL-REPORT-28 §4 "Where §44 is silent" lists U1–U4 readings only. It leaves out the `load_error` keep reading. The git-root fallback does appear, in NOT PROVEN. This is minor: a should-fix for the report, not a blocker.

Not proven:

- I did not run `./scripts/check` or any of the fix commits' tests. Whether each fix is test-first is the per-commit sub-agents' job.
- I did not read the fixes for correctness beyond whether they touch the anchor. "Resolved" is the bot's judgement.
- Fetches 2–4 were not re-diffed one against another. I compared fetch 1 against fetch 5 directly, plus the command's diff of fetch 4 against fetch 5.
- I did not look at the discotrade repository.

### d367373 (U1)

**Per-commit review: d367373** ("playbook: a human pause holds the next step and resume replays it")

**1. Unit and sections.** This is U1 of mission 28 (H-078). It implements DESIGN §44 rules 1, 2, 3, 5 and 6, plus §44's "`hands show` prints `resumed_from`". The body also cites §6, §10, §19, §29, §31, §32, §33 and §38. Rule 4 (`at rest`) is left to U2, as the brief assigns.

**2. Test-first: confirmed.** I reverted all six listed non-test files to d367373~1; each existed there.
- `tests/test_human_pause.py` fails at collection on the reverted code: `ImportError: cannot import name 'KEPT_DISCARDED_TITLE'`.
- To count the behavioural failures, I temporarily appended stubs for the three missing names (`SUPPRESSED_HUMAN_TITLE`, `KEPT_DISCARDED_TITLE`, `ResumeRefused`) to the reverted `playbook.py`. Result: **28 of 30 red**. The 2 that passed are controls of unchanged behaviour: `test_a_restart_under_a_rules_stop_resumes_nothing` and `test_pause_then_resume_with_no_playbook_and_nothing_kept_un_pauses`.
- The new phone test `test_under_a_phone_pause_go_consult_and_a_refused_resume_are_answered_titled` is red. Running the changed files (test_playbook, test_consult, test_phone, test_wake) also turns `test_wake.py::test_for_stop_is_the_stop_kind_and_nothing_else` red.
- I restored with `git checkout d367373 -- <6 files>`. `git status --short` was empty afterwards.

**3. Gate at the commit: green.** `./scripts/check` run once, output verbatim:
```
5087 passed in 510.79s (0:08:30)
== cli smoke ==
check: green
check-exit=0
```

**4. Design conformance: conforms except for one deviation.**
- **Rule 1:** conforms. The engine's kickoff rule sits at the top of the candidates, so an engine-approved apply's end is kept, decided with the playbook loaded at arrival. Ends are kept one per role and a later end replaces the earlier, with `pipeline.kept_replaced`. A `notify` decision fires at once. An enforced driver stop is handled before the human-pause branch, so it is never kept.
- **Rule 2:** conforms. `resume` rules fire until `suppressed_stop` is set. `*.limited`, `job.held` and `job.denied` fire nothing; architect holds get no engine approval because the paused branch returns first. Every stop suppressed under the pause is notified once. Consult stops use §29's title and the rest use `SUPPRESSED_HUMAN_TITLE`. `pause` over the pause passes `quiet=True`, so it is neither notified nor marked.
- **Rule 3:** conforms. `on_job_start` does not un-pause a human pause, while §10's load at job start is unchanged. `go` and `consult` are refused naming `resume`, in `api.kickoff`, `consult_refusal` and `engine.consult_human`.
- **Rule 5:** conforms. `resume` reloads with `stop_on_error=False` and refuses on a load error, or when ends are kept and there is no playbook. With no playbook and nothing kept, it un-pauses as today. The replay runs through `on_event` up to and including the first end that fires a job or stops, then discards the rest with an inbox event and a notification.
- **Rule 6:** conforms. `kept` and `suppressed_stop` are persisted, shown in `pipeline()`, `hands pipeline` and the phone's `status`, and the unreadable-state stop says the pause is lost with it. `hands show` now prints `resumed_from`.
- **Forbidden files:** none touched (no `DESIGN.md`, `meta/plan.md` or `meta/CHECKPOINT.md`).

**Deviation (should-fix-worthy): a role end is dropped while the playbook file does not load.**
- **Where:** `src/hands/playbook.py:1975-1979`, in `_under_human_pause`: `if book is None ... return  # fires nothing`.
- **Why it happens:** a failed `_load` sets `self.playbook = None` (line ~1798). That includes the reload made by a refused `resume`, and the reload when a job starts under the pause.
- **Scenario:** the human pauses and builder end A is kept. An owner commit leaves a broken playbook, and the `resume` is refused. The builder job running at that time then ends (end B). B is neither kept nor notified, only logged. When a later `resume` loads, it replays the older end A instead of the builder's newest end.
- **Rules broken:** rule 1 ("a later end of the same role replaces the earlier one"; §10's own stop is kept) and rule 2's "nothing is silent".
- **Scope:** only an absent playbook file should drop ends, as §10's no-playbook path does today; a file that exists but does not load should not.

**Not proven:**
- I did not run the deviation above. It comes from reading the code; no test covers an end arriving while `load_error` is set under a human pause.
- The replay's "a replayed send the API refuses is §10's could-not-send stop" relies on the existing `_act_send` path; I did not trace it.
- §6's limit-scheduled resume under the pause is tested on the engine only (the body says so).
- Rule 4 and the `at rest` mark are absent by design (U2).

The worktree `/tmp/review28-d367373` is left in place, clean apart from the ignored `.venv`.

(Reviewer: the deviation is hosted finding 4, fixed and tested in 58deee7; not carried.)

### adb061b (U2)

The commit holds up: test-first is confirmed, the gate is green, and I found no blocker. There are two should-fix-level gaps around when the at-rest check runs.

**sha:** adb061b (worktree left at `/tmp/review28-adb061b`, `git status --short` empty)

**1. Unit and sections (pass).** Unit U2 of mission 28 (H-078). It claims DESIGN §44 rule 4 ("At rest is published"), §44 "Documentation" and review 27 should-fix 3, with §19, §6 and §10.

**2. Test-first (pass).** All 8 listed non-test files exist at adb061b~1. I reverted them and ran the tests:
- `tests/test_human_pause.py` + `tests/test_operator_table.py`: `12 failed, 84 passed`.
- Of the 12 new test ids in `test_human_pause` (cancel test has `[running]`/`[queued]`), 10 went red. The two that stayed green, `..._not_published_while_a_hold_waits...` and `..._while_a_section_6_resume_is_scheduled`, only assert that nothing is published, so they cannot fail against code that publishes nothing. That is expected.
- `test_operator_table`: `test_the_reader_finds_the_published_titles_of_go_and_consult` and the existing `test_every_stop_reason_and_published_line_of_the_code_has_a_row` went red. The new `test_a_one_word_title_needs_a_row_of_its_own` stayed green, which is expected because the reader it tests is in the test file and was not reverted.
- The 4 changed tests in `test_playbook.py` (32 ids with parameters): `31 failed, 1 passed`.
- Restore was clean.

The body's named wrong change is accurate. With everything restored, deleting the `go` row (`docs/ARCHITECT-HANDBOOK.md:1054`) makes `test_operator_table` red: `assert not ["phone.py:524: 'go'"]`, 1 failed, 53 passed. With the old reader from adb061b~1 and the same row deleted, the test is green (1 passed). So should-fix 3 is fixed.

**3. Gate (green), verbatim:**
```
== ruff ==
All checks passed!
== pytest ==
5101 passed in 509.00s (0:08:28)
== cli smoke ==
check: green
check-exit=0
```

**4. Design conformance (pass, with should-fix notes).**
- **Rule 4 is met as written.** `check_at_rest` (`src/hands/playbook.py:3538`) reads the spool for running, queued or held jobs and `LimitManager.resume_scheduled()` for §6 resumes. It runs: from `pause()`, both for a new pause and a pause over one; after every `on_job` (in a `finally`), which covers done, failed, limited, killed while running, orphaned when a daemon start feeds it, and a consultation's end; after a cancel while queued (`daemon.py:979`), a spawn failure (`daemon.py:704`) and a denial (`api.py:1479`), which is the only path to `denied`.
- The mark is persisted in `pipeline.json` and cleared by `_unpause`; `_keep` clears it when a kept end is replaced, which republishes. The body names role, job id and verdict cut to 100, or says none is kept.
- **Documentation:** the handbook's §10, §14, §18 and §19 all have their rows; `docs/PLAYBOOK.md` and `docs/OPERATIONS.md` ("A quiet moment") are done. The release routine's warning is not in the repository, and the body defers it to the install, which matches "retired once this is installed".
- **Forbidden files:** none touched (no `DESIGN.md`, `meta/plan.md` or `meta/CHECKPOINT.md`).

Deviations:
- **Should-fix (a), `src/hands/limits.py:461-472`, rule 4 "the first moment".** When a scheduled §6 resume fails (`_resume_after` falls to `stop`), the last thing blocking at rest goes away but no check runs. `hands: at rest` is then never published until another pause or terminal job, so a human waiting for it waits indefinitely. The design's list of check points does not name this case and the body admits it, so the letter is met but not the intent.
- **Should-fix (b), `src/hands/playbook.py:2105`, rule 4 "naming each kept end".** The mark is cleared only when a kept end is replaced. If a different role's end is kept for the first time after at rest (for example the human's own cli send to aux, which does not un-pause), no new notification goes out, so the list the human relies on is stale. The design literally says "only when a kept end is replaced", so this is a gap in §44 itself, worth filing as a finding.

**Not proven:**
- No test covers the spawn-failure check under a human pause (the body says so).
- Nothing checks at daemon start beyond feeding orphans. That is fine by the letter of rule 4 and has no test.
- I did not exercise `limited` as the terminal end that makes the pipeline at rest (resume at `max_resumes`, so no resume task is created).
- The publish is read by tests, not by a phone.
- I did not check the wording of the PLAYBOOK and OPERATIONS docs beyond the diff.

(Reviewer: (a) is hosted finding 2, fixed in 58deee7, as is the start check (hosted finding 3); (b) is carried as should-fix 1.)

### 0892937 (U3)

**sha** 0892937. Unit: mission 28 U3, review 27's should-fix items 1 and 2 (DESIGN §44 "Review 27's should-fix items" 1 and 2; §43). Worktree left at /tmp/review28-0892937.

**1. Unit and sections: PASS.** The commit body names U3, §44 items 1 and 2, §43 and REVIEW-27 Should-fix 1 and 2. That matches the U3 entry of BUILDER-28-PROMPT. `api.py` is not in the brief's file list, but the body lists it and it is where the filing path lives.

**2. Test-first: PASS.** All four product files exist at `~1`. I reverted api.py, daemon.py, doctor.py and runner.py and ran the new tests plus test_operator_table.py. 5 failed:
- `test_the_start_folds_hold_reason_reads_the_zip_off_the_event_loop` ("the zip was read on the event loop", 2 == 0)
- `test_the_filing_hold_reason_reads_the_zip_off_the_event_loop` (same)
- `test_each_live_turn_carries_the_background_variable_a_job_carries[installed]` and `[differs]` (got `{'builder': '1', 'aux': '1', 'architect': '1'}`)
- `test_operator_table.py::test_every_string_the_reading_cannot_follow_is_an_exemption_with_a_reason` (the re-keyed exemption)

After `git checkout 0892937 -- <4 files>`, `git status --short` was empty.

**3. Gate: GREEN.** `./scripts/check` at 0892937, verbatim:
```
== ruff ==
All checks passed!
== pytest ==
5105 passed in 520.41s (0:08:40)
== cli smoke ==
check: green
check-exit=0
```

**4. Design conformance: PASS, with one should-fix-worthy note.**
- The only place that files `job.held` is api.py:447, and `decide_held_reason` (daemon.py:901) runs `published_hold_reason` through `asyncio.to_thread` before that event is filed.
- `_on_event` (daemon.py:893) now only pops the stored reason.
- `_publish_held` (daemon.py:426) uses `to_thread`. The engine's own calls (playbook.py:2391, 2404, 2449, 2521) already did.
- What still runs on the loop is `kit_apply_problem` in `defer_hold`, `_approve_architect_hold` and `_release_kit`. It reads kit.json and the job list and checks that the zip file exists (`is_file`), but it never reads or hashes the zip, so §44 item 1's rule holds.
- Both doctor `--live` turns now build their env with `runner.turn_env`, which is `job_env`'s whole decision; `job_env` calls it and adds `HANDS_JOB`. For the architect turn the old `HANDS_KITS` (`role.cwd/"kits"`) and `HANDS_CLONE` (`driver_clone(role.cwd)`) values are the same as before (doctor.py:2205/2221 against runner.py:1163-1170).
- No forbidden file touched: none of DESIGN.md, meta/plan.md or meta/CHECKPOINT.md.

**Should-fix-worthy deviation** (api.py:444-446, `await self.daemon.decide_held_reason(job)`). Before this commit, `enqueue` was followed by the `job.held` filing with no await in between. Now there is a thread hop there, while the job is already saved as `held` and visible over the socket. A `hands approve <id>` that lands in that gap would record `gate.decided` before `job.held`. Then `job.held` is published with fresh buttons for a job that is already decided, and `playbook.on_event("job.held")` runs for a job that is no longer held. Phone buttons cannot hit this window, because their nonce is minted later in `_on_event`. The window is milliseconds and no test covers it. It breaks the order "a hold is published when it is filed" (§34/§36) only in this race. A cheap fix is to re-check that the job is still held before filing.

**Minor:** `_publish_held` lists the held jobs once and then awaits once per job, so a job decided during the start fold can still be republished. A reason kept in `_held_reasons` leaks if `append_event` raises. Neither is blocker-worthy.

**Not proven:**
- The race above, either way.
- Thread safety of `_book_in_force` / `load_playbook` reading engine state from a worker thread.
- The live turns' `HANDS_DOCS`, `HANDS_CLONE`, `HANDS_KITS` and `HANDS_JOB`-absent: the new test does not assert them (the body says so).
- A real `claude` live turn.

(Reviewer: the race and the start-fold republish are hosted finding 1, fixed and tested in 885f07c; not carried.)

### d20e511 (U4)

The commit is conformant and I found no blocker. One should-fix-level gap is outside what the ruling asks for (below).

**sha** d20e511 ("kit: the playbook carried in any letter case or at the configured path is the owner's")

**1. Unit and sections: PASS.** Mission 28 U4, H-077 ruled. It claims DESIGN §44 "H-077, ruled", §26, §43, and §38 for reading the configured path as a repository path. The files match the U4 entry of BUILDER-28-PROMPT.

**2. Test-first: PASS (red).** All four listed files exist at d20e511~1 and were checked out from there. The new tests were run (5 in tests/test_playbook.py, 3 in tests/test_kit.py):
- tests/test_kit.py: 10 FAILED. These are the letter-case WARN test (×8: configured or no configuration, by 4 names) and the configured-path WARN test (×2: `ops/rules.toml`, `OPS/Rules.toml`).
- tests/test_playbook.py: a collection ERROR (`ImportError: cannot import name 'playbook_repo_path'`).
- Extra check on behaviour: I put back only the old exact-name match inside `carries_playbook`. That gave 6 FAILED in test_playbook: the letter-case hold ×4 and the configured-path hold ×2.
- Restored with `git checkout d20e511 -- <files>`; `git status --short` was empty both times.

**3. Gate: GREEN.**
```
== ruff ==
All checks passed!
== pytest ==
5125 passed in 522.07s (0:08:42)
== cli smoke ==
check: green
check-exit=0
```

**4. Design conformance: PASS.**
- **One test.** `spool.carries_playbook` (src/hands/spool.py:156) casefolds and compares against the configured path and both fixed names.
- **Engine.** The engine's hold (`_carries_no_playbook`) and its published reason (`published_hold_reason`, which the daemon's `decide_held_reason` also uses) both go through `PlaybookEngine._stored_kit_playbooks` (playbook.py:2516).
- **WARN.** kit check's WARN (`_owner_warning`, kit.py:909) uses the same test. It now judges the repository's playbook at the configured path as well as the fixed names (kit.py:913-919).
- **No configuration.** kit check then says it knows only the two fixed names (kit.py:925-929).
- **`playbook` check unchanged.** `_check_playbook` (kit.py:827, 859) is untouched and still uses exact `PLAYBOOK_PATHS`, as §44 requires.
- **No exact-name comparison left** in the hold or the WARN.
- **Path normalisation is sound.** Kit entries with `./`, `//`, `..`, a backslash or an absolute path are already refused by `_path_problem`. The configured path is normalised with `posixpath.normpath` after the `--show-prefix` prefix. Config refuses absolute and `~` paths. The test covers `../` inside and past the root, and a cwd two levels down.
- **Forbidden files.** DESIGN.md, meta/plan.md and meta/CHECKPOINT.md are not touched. FINDINGS.md marks H-077 resolved.

**Deviations**
- None blocker-worthy.
- Should-fix-worthy, at most as a finding (the ruling is about names, so this is not a breach): the test compares entry names only. An entry that reaches the playbook through a symlink in the repository is not caught. For example, `m/PLAYBOOK.toml` where the repo has `m -> meta`, or where the configured file is itself a symlink. `_landing_problem` (kit.py) resolves symlinks only to look for tooling directories.
- Note: `check_kit` now resolves and loads a config, and runs git, for every kit (kit.py:1476), not only role-mode ones. Any ConfigError is caught, so nothing fails. This is in line with §44.

**Not proven**
- Behaviour on a real case-insensitive filesystem.
- `hands kit check` resolving a different project's config than the handsd that will apply the kit; it would then judge under another `[playbook] path`.
- The empty-prefix fallback when git cannot run in the builder cwd (the design is silent there) has no test.
- No real role-filed kit has been held end to end through the daemon.

The worktree is left in place at /tmp/review28-d20e511.

(Reviewer: the symlink case is outside H-077's ruling; noted, not carried.)

### 58deee7 (U5, hosted findings 1, 3, 4, 6)

**58deee7**: mission 28 U5, the fix for PR #8 hosted findings 1, 3, 4 and 6. It claims DESIGN §44 rules 1–5, with §6, §10 and §19. Worktree left at /tmp/review28-58deee7.

**1. Unit and sections.** The body names the unit, the four findings and the sections. It lists every file it touches, and `git show --stat` agrees: playbook.py, limits.py, daemon.py, test_human_pause.py, test_playbook.py.

**2. Test-first: PASS.** All three product files exist at 58deee7~1, and I reverted them to it. I ran the 7 new tests in tests/test_human_pause.py and the changed `test_pausing_an_already_paused_pipeline_files_one_event`. Result: **6 red, 2 green.**
- The 5 red in test_human_pause are the ones the body claims: `pause_over_the_human_pause_files_no_suppressed_stop`; `daemon_start_under_a_human_pause_with_nothing_owed_publishes_at_rest`; `section_6_resume_that_fails_without_a_job_is_followed_by_at_rest`; `after_a_refused_resume_a_later_end_is_still_kept_and_rules_still_fire`; `end_arriving_while_the_playbook_does_not_load_is_kept_and_the_stop_notified`.
- The changed test_playbook test is also red. The body's "five red" counts only test_human_pause, so this is not a contradiction.
- The 2 green are the guards, as the body says: `pause_over_another_stop_still_files_its_suppressed_stop` and `no_playbook_file_fires_nothing`.
- After `git checkout 58deee7 -- <3 files>`, `git status --short` was empty.
- The first two pytest runs exited 2 before any test ran. The new worktree had no venv ("Failed to spawn: `pytest`"); after `uv sync --extra dev` the run above went through.

**3. Gate: GREEN.** I ran it once, after the restore. The tail of the output:
```
5132 passed in 494.38s (0:08:14)
== cli smoke ==
check: green
check-exit=0
```

**4. Design conformance: PASS, no deviations.**
- **Pause over a human pause (rules 2, 3).** `pause` returns `already_stopped` before reaching `stop()` (playbook.py ~3486). It files no `pipeline.stop_suppressed`, sends no notification and sets no `suppressed_stop`; `paused_by` and the kept ends stay. It calls `check_at_rest()`, which the "checked when the pause is sent" clause allows, and the mark stops a second publish. A pause over another stop still goes through `stop()` and files its record, as §19 says. The removed `quiet` flag has no other users.
- **At rest after the daemon's start (rule 4).** daemon.py:297 checks after `reschedule_pending()` and `_feed_orphans()`, with the workers up. Held and queued jobs count as busy, so publishing before the held-job republish is safe.
- **At rest after a §6 resume that ends without a job (rule 4).** In limits.py `_schedule`, `_tasks.discard` is registered before `_resume_ended`, so `resume_scheduled()` is already false when the check runs. The failed resume's stop is awaited inside `_resume_after` before it returns False, so the stop is filed before `at rest`. A cancelled task checks nothing.
- **Refused resume (rules 1, 5).** Both refusal paths restore `(playbook, load_error, _loaded)` (playbook.py ~3516–3527); the pause and the kept ends are not touched. `_load`'s failure path changes no other state, since the kickoffs, `last_rule` and `max_resumes` updates run only after a successful load.
- **The design-silent choice is sound.** A role's end is kept when `load_error` is set (playbook.py ~2071). §10 makes an unloadable playbook a stop, rule 1 lists "§10's own stop" as a kept decision, and rule 2 already notified that load's stop. With no playbook file, §10 chains nothing, so the end would at most notify and is not kept. A driver end under §28's enforced stop is handled before `_under_human_pause`, so it is never kept, as rule 1 requires.
- **Forbidden files:** none touched (DESIGN.md, meta/plan.md, meta/CHECKPOINT.md).

**Not proven:**
- **Old playbook kept after a refusal (minor, not a deviation).** Suppose a playbook was loaded, then its file was deleted while ends were kept. The refused `resume` restores the old in-memory playbook, and later ends are decided with it. Rule 5 calls a refused resume a no-op, which supports this, but no test drives it.
- **A reload on the next event after a refusal.** When nothing had loaded before the refused `resume` (`_loaded` False), the next event reloads with `stop_on_error=True`. That files a suppressed stop and sets the mark, which then blocks `resume` rules. This is consistent with "as before", but untested.
- **`at rest` at start goes out before `phone.start()`.** I did not check how the notification is delivered in that order on a real phone.
- **Live behaviour.** No real restart or §6 resume under a human pause has been run against a phone.

### 885f07c (U5, hosted findings 2, 5)

I reviewed commit 885f07c. It passes on all four points, with no blocker-worthy or should-fix-worthy deviation.

- **Sha:** 885f07c303503a8c482a70590464790ae8b9e919 (worktree left at /tmp/review28-885f07c, `git status --short` empty).

**1. Unit and DESIGN sections.** Mission 28 U5, the fix of PR #8 hosted findings 2 and 5, plus one stale sentence in docs/PLAYBOOK.md. It claims DESIGN §44 (review 27's should-fix 1; "H-077, ruled"), §34, §38 and §43. The body lists src/hands/api.py, daemon.py, kit.py, docs/PLAYBOOK.md, tests/test_playbook.py and tests/test_kit.py, which matches `git show --stat`.

**2. Test-first: pass, 5 red.** All four product files exist at 885f07c~1; I reverted them and ran the commit's three new tests (five cases with the parametrization). All five failed:
- test_playbook.py::test_a_send_decided_while_its_hold_reason_is_computed_is_not_announced[approved] and [denied]
- test_playbook.py::test_a_held_job_decided_while_the_start_computes_its_reason_is_not_republished[approved] and [denied]
- test_kit.py::test_the_daemons_kit_check_from_a_builder_cwd_below_the_root_warns_for_the_configured_path

Across the whole of both test files, those five were the only failures. After `git checkout 885f07c -- <4 files>`, `git status --short` was empty.

**3. Gate: green.**
```
5137 passed in 535.61s (0:08:55)
== cli smoke ==
check: green
check-exit=0
```

**4. Design conformance: pass.**
- **Api.send (api.py:447-451):** a job approved or denied during the reason's await gets no `job.held` event, no engine `job.held`, no notification and no nonce, and its kept reason is dropped. The await only really yields for an architect-origin hold the engine did not defer. Deferred and non-architect holds return without yielding, so they have no window, and nothing leaks into `_deferred_holds`.
- **Start republish (daemon.py:429-439):** a job decided while its reason is computed is skipped and left out of the held list. Its nonce is only minted in `publish_hold`, so it gets none.
- **Remaining window:** between `still_held` and the publish there is no await in either path. So no decided hold is announced and no reason leaks.
- **Kit WARN (kit.py:927-936):** the configured `[playbook]` path is read under `git_toplevel(repo)`, falling back to `repo` where git cannot say. This matches §44's H-077 ruling and §38's repository-path reading. The fixed names are still read under `repo`, as before.
- **Doc:** the new docs/PLAYBOOK.md sentence (a pause over a human pause records nothing, no `pipeline.stop_suppressed`, no notification) matches §44 rules 2 and 3 and the code (playbook.py:3486-3490).
- **Forbidden files:** none touched (no DESIGN.md, meta/plan.md or meta/CHECKPOINT.md).

**Observations, not deviations:**
- daemon.py:429-439 and 316-320: a hold that is published, and then decided while a later held job's reason is computed or during the start's fold window, is still listed in the start notification's held list. That is a stale title, not an announcement of a decided hold, and it is outside finding 2.
- kit.py:930: the `name == configured` test sends a fixed name under `root` when it equals the configured string. It can only matter when repo != root, where `playbook_repo_path` gives a different string, so it has no effect.
- Paths that are not resolved (a symlinked repo against git's realpath toplevel) could defeat the "judged once" de-duplication, at worst giving a duplicate WARN name.

**Not proven:**
- A decision landing between `still_held` and the publish (there is no await there, so it is argued, not tested).
- The fixed names read from a cwd below the repository root.
- Cancelling a held job (refused by §8).
- The fold-window held list described above.
- The doc's "no notification" ignores §44 rule 4's once-per-pause at-rest publish from `check_at_rest`, which is correct under rule 4.
