# REVIEW-26 — cold review of mission 26 (the project separation), PR #6

reviewed: d3c4f151575026c8aa29c3f057cbf45d248b9c63

Shape: pull request (BUILDER-26 §Branch). Branch `mission-26`, PR #6 (base
`main`), first review of the branch: base = `git merge-base origin/main
origin/mission-26` = 9877b57. Commits under review (`git log
9877b57..origin/mission-26 ^origin/main`):

    d3c4f15 report: mission 26 hosted review dispositions, H-073, the PR #6 archive
    a5ca441 docs: route 5 sends the decisions kit without go; max_resumes reached is route 6
    73aa1b3 consult: a failed enqueue keeps the stop, a refused consult loads nothing and keeps no file
    ce2088b report: mission 26 final report
    79eb270 docs: the operator table, the instruction's rule 15 and H-072's raise
    592fc6e kit: hands kit check passes a decisions kit; hands kit file refuses one
    d222109 digest: hands digest and the phone's digest print one redacted line per project
    b956e2a consult: the phone's consult and hands consult start an architect consultation
    5c1c9c3 plan: mission 26 — plan, checkpoint, H-070..H-072

## Blockers

None.

## Should-fix

1. **The gate failed once in this review, in a test that fails intermittently.** At
   b956e2a (U1), `./scripts/check` ran red on its one run: `FAILED
   tests/test_operations.py::test_kit_apply_refuses_a_staged_name_with_dot_dot`, `1
   failed, 4737 passed in 387.08s`. The test passed alone and twice with its whole
   file, and a second full `uv run pytest` at that commit did not fail. It was green
   at the other five unit commits and at the tip. FINAL-REPORT-26 §4 discloses the
   same failure during U1's gate ("did not recur in eight further runs"). The test
   dates from mission 24 (2f9e219), and no mission-26 commit touches it. Both
   observed failures, the builder's and this review's, were at U1. No one has found
   the cause, so it is still possible that U1's changes (the fetch's extension in
   `src/hands/kit.py`, or the new tests in the suite) made it more likely.

   Why should-fix and not blocker: the gate is green at the tip that merges, and
   the failing test is outside the mission's diff. It is still a gate that can go
   red on an unchanged tree.

   Next mission: file a finding, find the race, and fix or pin it.
2. **The operator table (handbook §19) misses two lines the daemon writes.** §42
   requires "every stop and published line the engine, the limit manager and the
   daemon write themselves":
   - The playbook-load stop "the playbook **is not the committed copy**, so no rule
     can be trusted to fire: …" (`src/hands/playbook.py:1646`) is missing. It is the
     dirty or untracked playbook, the most ordinary of the four load stops. The row
     at `docs/ARCHITECT-HANDBOOK.md:922` lists only "cannot be read / does not agree
     / renames the series".
   - The phone's follow-up to a received kit, "apply <name>: <why>; the commit
     message is the default '<message>'" (`src/hands/phone.py:787`), has no row.

   FINAL-REPORT-26 §3 discloses the risk ("§19 may miss one written outside the
   templates"), so no claim is contradicted. A test that lists the stop reasons from
   the code would close the gap. handswho's `hands who` pushes are not counted here:
   handswho is its own process, not the engine, the limit manager or the daemon.

## Hosted review

**Archive and verdict.**
- The sub-agent ran `uv run hands hosted-review 6` in a worktree at
  `origin/mission-26` (d3c4f15). It exited 0 and archived to
  `meta/reviews/hosted/PR-6/3/` (k = 3).
- The verdict, taken from the Code Review comment 6250309209: **2 of 7 findings
  open**.
- Header as found: `🐞 Bugs (0)`, `📘 Rule violations (0)`, `🔗 Cross-repo
  conflicts (2)`, `📜 Skill insights (0)`.
- Between fetch 2 (the builder's) and fetch 3, the only change to the comment is
  the commit sha in its links (a5ca441 → d3c4f15). Findings 2–6 are struck through
  and marked resolved, and 1 and 7 are open.

**The bot's findings, verbatim.** Numbers are fetch 1's, as in the builder's table.

1. **Discotrade skips mid-mission rulings** [🔗 Cross-repo conflict, ≡ Correctness],
   `templates/BUILDER-N-PROMPT.md:98-101` (inline at :101). "The new decisions-kit
   route tells operators to apply an owner file and use `go`, relying on the added §R
   instruction to make the builder carry out its steps. Discotrade's active mission
   20 brief has an older §R without that instruction, so a mid-mission decisions kit
   can be committed while the resumed builder continues from its checkpoint without
   acting on the ruling." — Open.
   - **This review:** dismissed for this PR. The defect is real and needs a design
     decision (whether an older brief should be patched or the route should say so),
     which the builder filed as H-073. It is not mission 26's to fix in code.
   - **Builder:** finding H-073 filed. **Audit:** H-073 is present in
     `meta/findings/FINDINGS.md` (line 2728), open, with "Decision needed". Upheld.
2. **Failed consults leave the pipeline running** [🐞 Bug, ☼ Reliability],
   `src/hands/playbook.py:2542-2545`. "`_consult_for_human` persists an unpause
   before it calls `enqueue`, without restoring the stop if enqueue fails. A queue or
   spool failure can therefore leave a stopped pipeline running even though no
   architect consultation was created." — Resolved.
   - **This review:** confirmed and fixed.
   - **Builder:** fixed in 73aa1b3. **Audit:** the commit touches the anchor, and the
     comment shows the finding resolved. Upheld; see the Notes on the inbox's
     leftover `pipeline.resumed`.
3. **Exhausted jobs stay stopped after resume** [🐞 Bug, ≡ Correctness],
   `docs/ARCHITECT-HANDBOOK.md:908`. "The operator table tells a human to run
   `resume` after a `limits.max_resumes reached` stop, but that command only clears
   the pipeline pause. When the resume limit has been reached, the limit manager
   schedules no new builder job, so following this row does not restart the work."
   — Resolved.
   - **This review:** confirmed and fixed. The U4 sub-agent found the same defect
     independently at 79eb270 (§42 names "`max_resumes` reached" in route 6).
   - **Builder:** fixed in a5ca441. **Audit:** the commit touches the anchor, and the
     comment shows the finding resolved. Upheld.
4. **Ruling follow-ups refuse consultation** [🐞 Bug, ≡ Correctness],
   `docs/ARCHITECT-HANDBOOK.md:857-859`. "Route 5 says to send an owner kit using
   route 4 and then run `consult`, but route 4 ends by running `go`. If the human
   follows that sequence immediately, `go` starts a builder job and the new consult
   path refuses the request while that job is queued or running." — Resolved.
   - **This review:** confirmed and fixed. Dropping `go` from route 5 is required by
     §42's own refusal of `consult` while a builder job is queued, running or held.
   - **Builder:** fixed in a5ca441. **Audit:** the commit touches the anchor and makes
     no new design decision. Upheld.
5. **Rejected consults fill the kit directory** [🐞 Bug, ☼ Reliability],
   `src/hands/phone.py:624-628`. "`_consult_command` leaves the permanently linked
   attachment in `kit_dir` when UTF-8 decoding or the final consultation check
   refuses it. Repeated authenticated requests with invalid text, or requests
   refused after a state change during download, accumulate files even though no
   consultation starts." — Resolved.
   - **This review:** confirmed and fixed. The removal deletes only the name
     `_link_first_free` returned (`os.link`, never a replace).
   - **Builder:** fixed in 73aa1b3. **Audit:** the commit touches the anchor. Upheld.
6. **A refused consult can stop a running pipeline** [🐞 Bug, ☼ Reliability],
   `src/hands/api.py:569-576`. "`Api.consult_refusal` calls `engine.reload()`, which
   runs the full `PlaybookEngine._load()`, before it checks for a busy builder, aux or
   architect. `_load()` stops and pauses the pipeline when the playbook does not load
   (dirty, uncommitted, wrong config). It also swaps the in-memory playbook and clears
   `last_rule` in the middle of a running job. So a phone `consult` (asked twice,
   before and after the fetch) or a `hands consult` sent while the builder is working
   can stop the pipeline. It can also change which rules decide that builder's end,
   even though the consult itself is then refused as busy." — Resolved.
   - **This review:** confirmed and fixed. The busy, wait and empty refusals are now
     asked before any load. A consult refused by none of them on an idle project
     still loads the playbook, as a job's start does under §10 (see Notes).
   - **Builder:** fixed in 73aa1b3. **Audit:** the commit touches the anchor. Upheld.
7. **Discotrade consultations lack reviews** [🔗 Cross-repo conflict, ≡ Correctness],
   `src/hands/playbook.py:3406-3410` (inline at :3425). "`human_consult_prompt`
   replaces the review with a reason and starts the architect with no review job.
   Discotrade's standing architect instructions require a consultation on a review
   outcome and require reading the review it names, leaving that required input
   undefined when its operator uses the new `consult` command." — Open.
   - **This review:** dismissed. §42 defines a human-started consultation as one whose
     reason stands in place of a review, and `architect/CLAUDE.md` (b956e2a) says so.
     Another project's standing text is updated by the instruction paste §42 makes due
     after this release.
   - **Builder:** dismissed with that reason. **Audit:** the reason holds against §42.
     The audit notes that finding 1, also another project's older standing text, was
     filed rather than dismissed. Both dispositions are defensible: finding 1's gap
     sits in the route hands itself ships, finding 7's in that project's own
     instruction. Upheld.

**Coverage:** every finding has exactly one row in FINAL-REPORT-26's `## Hosted
review` table. None is missing, duplicated or left without a reason.

## Notes

**Schedule.** One sub-agent at a time; one `./scripts/check` at a time.

| Sub-agent | Start | End |
|---|---|---|
| hosted review, PR #6 | 17:42 | 17:43 |
| b956e2a (U1) | 17:43 | 18:06 |
| d222109 (U2) | 18:06 | 18:16 |
| 592fc6e (U3) | 18:16 | 18:24 |
| 79eb270 (U4) | 18:24 | 18:34 |
| 73aa1b3 (U5 fixes 2, 5, 6) | 18:34 | 18:42 |
| a5ca441 (U5 fixes 3, 4) | 18:43 | 18:50 |

All times are 2026-10-18 IDT.

**The reviewer's gate at the tip:** `./scripts/check` in a worktree at d3c4f15,
18:51–18:58. Green: `All checks passed!`, `4834 passed in 434.65s (0:07:14)`, `==
cli smoke ==`, `check: green`. The count matches FINAL-REPORT-26.

**Commits that are not units.**
- `plan:` 5c1c9c3 does what it says. It touches only `meta/` (plan, checkpoint,
  journal, findings), and H-070, H-071 and H-072 are filed with §42's evidence.
  `origin/mission-26` exists.
- `report:` ce2088b and d3c4f15 list only files under `meta/`, so they make no
  forbidden edit.
- No commit touches DESIGN.md. No unit commit touches `meta/plan.md` or
  `meta/CHECKPOINT.md`.

**NOT PROVEN (FINAL-REPORT-26 §3) against the sub-agents.** Every gap the
sub-agents met is already disclosed:
- `consult` refused while an architect job is queued: untested.
- `digest`'s `spool unreadable` branch: untested.
- §19 possibly missing a reason: should-fix 2 makes it concrete.
- The ntfy size limit on a long digest: untried.
- A restart during a human consultation: untried.

Three further items are not proven, and the report does not list them:
- The refusal caused by a state change during a phone `consult`'s download. Only
  the empty-reason refusal after the fetch is exercised; 73aa1b3's body says so.
- A refused `consult` on an idle project with a dirty playbook stops the pipeline
  through §10's load. Nothing tests it either way, though it is the deliberate
  choice in 73aa1b3's body.
- `digest`'s mission field takes the first digit run after `Mission:`, so
  `Mission: v2 of 26` would read `2`. §42 is silent on this.

**Observations, not findings.**
- After a failed enqueue, 73aa1b3 puts the stop back but leaves the
  `pipeline.resumed` event already filed. The inbox then reads "resumed" while the
  pipeline is paused. §42 is silent on this path. The commit body names the choice,
  as the brief's sub-agent rules allow where the design is silent.
- When several refusals hold, 73aa1b3 now reports the busy/wait/empty one before
  the mode one. §42 lists the refusals as a set, not an order.

**This review's own steps.**
- `git worktree prune` found no stale registered worktree. `/tmp/review-audit` is
  not registered with this clone and was left alone.
- The hosted archive fetched by this review, `meta/reviews/hosted/PR-6/3/`, is
  copied to `main` with this file.

## Per-commit verdicts

### hosted review (PR #6, k = 3)

```
Fetch k=3 (`uv run hands hosted-review 6` in /tmp/review26-hosted at d3c4f15, exit 0, archived meta/reviews/hosted/PR-6/3/); verdict taken from the Code Review comment: "2 of 7 findings open".
1. Coverage: all 7 bot findings have exactly one row in FINAL-REPORT-26's ## Hosted review; none missing or duplicated; fetch-1 counts (Bugs 5, Cross-repo 2, 7/7 open) match archive 1.
2. Fetch 2 → fetch 3: the only change in comment 6250309209 is the commit SHA in links (a5ca441 → d3c4f15); verdict stays 2/7; the 5 fixed are struck and marked ✓ Resolved; findings 1 (H-073) and 7 (dismissed) remain open — matches the table.
3. 73aa1b3 (findings 2, 5, 6) touches each anchor: _consult_for_human in playbook.py (~2529–2551), consult_refusal in api.py (~557–591), _consult_command in phone.py (~602–632). a5ca441 (findings 3, 4) touches docs/ARCHITECT-HANDBOOK.md ~855–863 and the max_resumes row ~905–913.
4. H-073 present in meta/findings/FINDINGS.md:2728, open, with a "Decision needed" section.
5. Finding 7 dismissal holds against §42 ("carries the human's reason in place of a review"; an architect/CLAUDE.md rule). Finding 1 is the same class (another project's older standing text) yet got a finding — inconsistent treatment, both defensible.
6. a5ca441 decides nothing new: §42's route 6 lists "max_resumes reached"; route 5's "without go / once the apply has ended" follows from §42's refusal of consult while a builder job is queued or held.
7. 73aa1b3 makes three choices §42 does not specify, recorded only in the commit body: (a) a failed enqueue restores the stop and writes no event; (b) refusal precedence busy/wait/empty before mode; (c) a consult passing every non-playbook check still runs engine.reload(), so a dirty playbook can stop the pipeline from consult. None contradicts §42; arguably finding-worthy. Finding 5's fix is cleanup only.
```

### b956e2a (U1)

```
1. Unit/sections: mission 26 U1, `consult` from the phone and the laptop. Body claims DESIGN v3.25 §42, plus §31, §33, §38 and H-058. Lists all 14 files in `git show --stat`; DESIGN.md, meta/plan.md, meta/CHECKPOINT.md untouched.
2. Test-first: PASS. 9 product/doc files reverted one by one: tests/test_consult.py fails to collect (ImportError: cannot import name 'HUMAN_REASON_HEADING'); 21 tests red across test_phone (12), test_docs (4), test_handbook (5). The 33 new test_bash_guard tests stay green (body says the guard is unchanged; they pin existing behaviour). git status --short empty after restore.
3. ./scripts/check: RED on its one run: `FAILED tests/test_operations.py::test_kit_apply_refuses_a_staged_name_with_dot_dot` / `1 failed, 4737 passed in 387.08s (0:06:27)`. Passed alone, twice with its whole file, and in a second full `uv run pytest`. Looks intermittent, not caused by this commit; cause not found.
4. §42 conformance: PASS. First line HUMAN_HEAD = `hands consult: consult on job none (role human)`; reason section "The human's reason for this consultation", verbatim; over MAX_PROMPT_BYTES raises ConsultRefused. Origin `playbook`; no §8 hold; _unpause("resume") only after consult_refusal and the engine's mode, budget, size checks; counted as used+1. consult.sent carries exactly the listed fields incl. reason_sha256, never the reason; consult.done about None; journal "on consult by the human". Refusals in §42's order, published via _refuse("consult", …). Attachment: is_basename_with_suffix(.md), 256 KiB cap, UTF-8; url/kit_dir/download checks the kit's own; first-free naming keeps the suffix; CLI same rules. Guard tests: neither guarded role admits `hands consult`. architect/CLAUDE.md rule 13 ends with routes 4 and 5, rule 14 added; handbook §16 describes consult and retires the recital.
5. NOT proven: a queued architect job as a refusal (only running and held tested); that the playbook-origin job is never §8-held at runtime (enqueue not traced); restart during a human consultation, a real ntfy attachment, a real claude; the cause of the failure in 3.
```

### d222109 (U2)

```
1. Unit/sections: mission 26 U2, `digest`. Body claims DESIGN v3.25 §42 "`digest`", plus §41's redact-then-cut rule and §39's H-058.
2. Test-first: PASS. Adds tests/test_digest.py and tests in test_phone.py, test_docs.py, test_bash_guard.py. Six product files reverted (digest.py removed, five from d222109~1): test_digest.py fails to collect (ImportError: cannot import name 'digest' from 'hands'); the phone digest test and 6 docs tests fail; the guard test stays green (guard unchanged per body). git status --short empty after restore.
3. Gate: GREEN. "All checks passed!", "4752 passed in 389.23s (0:06:29)", "check: green". The suspected intermittent test did not fail.
4. §42 conformance: PASS. One line per *.toml sorted by name with every field; status probe 2 s overall deadline; an unloadable config prints `<file>: does not load` (exception caught, message dropped). Redaction: every loadable project's cmd_secret and ntfy_token, any case, longest first; verdict and stop reason redacted whole before the first line is taken and cut to 60/100; joined line redacted again. Read-only: ReadOnlySpool creates no directories; engine built only to count; a test checks nothing under the temp home changes. Phone: `digest` in _SECRET_ONLY, published titled `digest` on ntfy_topic. Guard test covers driver (builder, aux) and architect (builder, human) across five forms. Temp home in tests; forbidden files untouched; body lists all 10 files.
5. NOT proven: the `spool unreadable` branch (body admits); ntfy's size limit on a long digest; architect count across a series rename; the mission regex takes the first digit run after `Mission:` (`Mission: v2 of 26` reads 2; §42 silent); the tmp_home fixture itself not read.
```

### 592fc6e (U3)

```
1. Unit: mission 26 U3, the decisions kit and the owner file on a resume. Claims DESIGN v3.25 §42 "The decisions kit", "The newest owner file, on a resume", route 4 of "The operator table", plus §28 for KIT.md's first line. Matches U3 of the brief.
2. Test-first: PASS. 8 tests added in tests/test_kit.py, tests/test_operations.py, tests/test_phone.py; with the 4 product files at 592fc6e~1 all 30 cases red (the 14 "judged as before" cases also fail on the parent's missing `.decisions` attribute, but they pin the parent's exact `FAIL brief` line). git status --short empty after restore.
3. Gate: GREEN. `4782 passed in 387.31s (0:06:27)`, `== cli smoke ==`, `check: green`. The suspected intermittent test did not show.
4. Design conformance: PASS. Recognition, the three checks' wording, paths/playbook/protocol, `6 of 6` with the plan-only apply prompt, and kit_file's refusal (DECISIONS_REFUSAL, after the check, filing nothing) match §42. The template §R sentence is word for word BUILDER-26's §R. Handbook §3, §4, §11 say what §42 asks. Edge cases (parent vs new check_kit): pass as decisions kits — a `meta/decisions/x-owner.md/` directory entry, CRLF or BOM KIT.md first line, surrounding whitespace on it, `meta/decisions/ -owner.md`, `meta/decisions/..-owner.md`, an empty owner file (space and `..` names are one non-empty component, so §42 allows them). Judged exactly as the parent — a file under `x-owner.md/`, `../evil.md`, `meta/decisions/../x-owner.md`, a duplicate owner entry, lowercase `kit.md`, `./meta/...`, a backslash name, `plan: decisions a b (owner)`, a README beside the owner file. Forbidden files untouched; body lists all 7 files.
5. NOT proven: end-to-end `hands kit apply` and the phone flow (rest on the commit's tests); whether a `<date>` of any non-space text suits the engine and §R; whether the refusal text reads well to the architect role.
```

### 79eb270 (U4)

```
1. Unit: mission 26 U4. Claims DESIGN v3.25 §42 "Who operates a project", "An HF report", "The operator table (handbook §19)", "The second onboarding shape (handbook §13)", "Documentation", and H-072. Body lists all 7 files in --stat.
2. Test-first: PASS. Adds tests/test_operator_table.py (41 tests); with the 6 non-test files at 79eb270~1 all 41 fail; restored, all pass; git status --short empty.
3. Gate: GREEN. `4823 passed in 378.57s (0:06:18)`, `== cli smoke ==`, `check: green`. The suspected intermittent test did not show.
4. Design conformance: one defect, three gaps.
 (a) Instruction: PASS. Diffed by hand: opening paragraph and rule 15 match §42 word for word (whitespace-normalised), rule 15 after rule 14, rules 3, 9, 12, 14 carry §42's sentences; no "driver" or "keep" left.
 (b) §19 route defect: the `limits.max_resumes reached: … is limited again` row is route 7 with `resume <secret>`; §42 puts "max_resumes reached" in route 6, and route 7's premise (a resume scheduled at the reset) is false for this stop (limits.py:388 fires only when none will be scheduled); playbook.resume() only un-pauses. [fixed later in a5ca441]
 (b) §19 missing rows: "the playbook is not the committed copy" (playbook.py ~1646); the `hands: kit received` follow-up "apply <name>: <why>; the commit message is the default …" (phone.py ~774); handswho's `hands who` / `hands who (requested)` pushes (who.py:106-107), arguably outside "engine, limit manager, daemon".
 (b) otherwise PASS: every template stop/notify has a row with four columns; budget exhausted, kit wait, escalation, usage-limit stop, `handsd started`, refused command, digest all present; routes fit §42; the HF report's form matches §42.
 (c) Handbook: PASS. §13 gains all three parts; §18 names consult and digest; §10's row and §14 give route 4 with `answer` as the shorter route, no driver.
 (d) Runbooks: PASS. OPERATIONS.md consult row (digest row at line 276, from U2); INTEGRATION.md H-072's raise and the CLI ceiling, confirmed by grep -a over the 2.1.302 binary (no cap; 600000 or the default when unset). Forbidden files untouched.
5. NOT proven: that §19 covers every reason string (grepped by hand; no test enumerates them from the code); any route end to end on a real phone.
```

### 73aa1b3 (U5, hosted-review findings 2, 5, 6)

```
1. Unit: mission 26 U5, PR #6 hosted-review findings 2, 5, 6. Claims DESIGN v3.25 §42 "`consult` from the phone and the laptop", with §10's load and stop. OK.
2. Test-first: OK. 3 tests (6 cases) added, all pass at the commit. Reverting playbook.py turns the enqueue-fails test red; reverting api.py turns both refused-as-busy cases red (dirty, recommitted); reverting phone.py turns 2 of 3 kit_dir cases red (the failed-fetch case stays green because fetch_kit already removes the partial temp file, as the body says). git status --short empty after restore.
3. ./scripts/check: GREEN. "4829 passed in 387.94s (0:06:27)", "check: green"; the intermittent test passed.
4. (a) Refusal order: conforms; §42 lists refusals without an order; the only observable change is which message wins when several hold; still published titled `consult`; architect-busy skipped without [roles.architect], which the mode check then refuses.
 (b) A consult can still stop the pipeline: with nothing busy and a non-empty reason, reload() runs and a dirty playbook stops the pipeline through _load; the consult is refused "no playbook is loaded …". Only with no job running, so nothing swapped under a running job; matches §10 and §42 ("the playbook in force"); the side-effect-free load was declined in the body.
 (c) After a failed enqueue the inbox keeps a `pipeline.resumed` while the pipeline is paused again; no new stop event; §42 silent; body admits.
 (d) File removal: safe; the removed path is exactly the name _link_first_free returned (os.link, never replaces).
 Files: the 5 the body lists are the 5 in --stat; forbidden files untouched.
5. NOT proven: a refusal by a state change during the download; a failure after the enqueue; the (b) case has no test either way.
```

### a5ca441 (U5, hosted-review findings 3, 4)

```
1. Unit: mission 26 U5, PR #6 hosted-review findings 3 and 4. Claims DESIGN v3.25 §42 "The operator table (handbook §19)"; body also covers handbook §16's owner-file sentence. Body lists both files in --stat; forbidden files untouched.
2. Test-first: PASS. With the old handbook all 5 new tests fail (route 5 sends, rows on route 5, blocked-mission row, §16, max_resumes row — the last `'the human alone — route 7' == "the project's chat — route 6"`). git status --short empty after restore.
3. Gate: GREEN. "4834 passed in 384.84s (0:06:24)", "== cli smoke ==", "check: green", rc=0.
4. (a) PASS. Route 5 still does what §42 says (owner file as route 4's kit, then consult) without route 4's `go`; required by §42's refusal of consult while a builder job is running, queued or held (Api.consult_refusal; kit_apply is a held builder job), so "once the apply has ended" is needed. §42 untouched.
 (b) PASS. The max_resumes-reached row is route 6 as §42 names; its text matches limits.py: on_limited schedules no resume, reschedule_pending skips a role at the limit, only a `done` resets the count (on_job_finished); `resume` would only clear the pause.
 (c) Still missing: "the playbook is not the committed copy" (playbook.py:1646) — absent; the load-stop row (§19 table) lists only "cannot be read / does not agree / renames"; §42 requires it. The phone's `hands: kit received` follow-up "apply <name>: <why>; the commit message is the default …" (phone.py:787) — absent; required by my reading. handswho's pushes — absent; not required (its own process).
5. NOT proven: that an operator follows this text; whether the `go` after the reset is itself limited; whether a playbook rule could fire a builder job when the apply ends (racing the consult); whether §42 counts the phone listener as "the daemon".
```
