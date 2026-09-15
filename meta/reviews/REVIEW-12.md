# REVIEW-12 — cold review of hands mission 12

VERDICT: review mission 12 blockers=3 should-fix=9

Base `1875bae` (`review: mission 11`, the last `review:` commit on origin/main).
Range `1875bae..0f75521`: 13 commits.
- The architect's kit `bb9aab5`, which was not reviewed as a unit.
- Six builder unit commits: U0 `5ea7b9d` (`plan:`), U1 `3966f9b`, U2
  `e642552`, U3 `043413d`, U4 `7f86406`, U5 `1250817`.
- Six `meta:` bookkeeping commits, which were skipped: `1e8af0a`, `96c5488`,
  `fa1535c`, `464bd1d`, `cfb8fee`, `0f75521` (U6, the final report).

One sub-agent reviewed each unit commit, in a detached worktree at that commit.
Read beforehand: DESIGN v3.11 §28 (with §27, §6, §8, §10, §12),
`meta/BUILDER-12-PROMPT.md`, `meta/FINAL-REPORT-12.md`,
`meta/findings/FINDINGS.md` (H-022 to H-025) and `meta/reviews/REVIEW-11.md`.

`./scripts/check` passed on the first run at every unit commit. The pass counts
were 1733, 1882, 1916, 1980, 1982 and 1982. `git diff --stat 1250817 0f75521`
touches only `meta/`, so the tip's gate is U5's: `1982 passed` / `== cli smoke
==` / `check: green`. At every product unit the new tests fail when the product
change is reverted. U1's reds are mostly its signature change, so the probes
were also run through the parent hook. U4's reds are plumbing until the one
union is removed. No unit commit touches `DESIGN.md`. Only U0, the `plan:`
commit, touches `meta/plan.md` and `meta/CHECKPOINT.md`. Each commit body names
exactly the files the commit changes.

The mission's own verdict is `blocked U4`.

## Blockers

1. **§28's guard can still be bypassed in role mode, through a `#` comment (U1
   `3966f9b`, `driver/hooks/bash_guard.py:381`, `:278`).**
   - **The design.** §28 says the guard judges "the literal tokens `hands`,
     `git` and the rest would receive". Role mode refuses every `hands`
     subcommand not in §27's list, and any send whose `--context` is not `keep`.
   - **The code.** shlex runs with `commenters = ""`, and `_scan` has no comment
     state. An apostrophe inside `# …` therefore opens a quote that bash never
     sees, and the guard reads the next line as quoted text.
   - **Reproduced by the reviewer on the tip** (hook JSON on stdin,
     `HANDS_ROLE=driver`, `HANDS_CONSULT_ROLE=builder`). `hands go` alone exits
     2, but these exit 0:
     - `hands show x # it's` + newline + `hands go #'`. Real bash with a
       stand-in `hands` printed `RAN: hands show x` and `RAN: hands go`.
     - `hands show x # it's` + newline + `hands send --role builder --context
       clear m #'`.
   - **Normal mode too.** `touch /tmp/rev12-pwned` exits 2, but `ls # it's` +
     newline + `touch /tmp/rev12-pwned #'` exits 0 (the sub-agent confirmed
     that bash creates the file). The parent hook had the same hole.
   - **Claims the disk contradicts.**
     - The commit body and FINAL-REPORT-12 §3 item 2 say comments "are refused
       (fail-closed)". They are not.
     - The Review items table marks REVIEW-11 blocker 1 "closed".
     - The commit body lists "a backslash-newline before --context=clear" as a
       probe blocked only after this change. The parent hook already exited 2 on
       it in role mode (checked by the reviewer).

2. **§28's IDNA check accepts IDNA-invalid hosts, and handsd then fetches (U3
   `043413d`, `src/hands/phone.py:558-563`).**
   - **The design.** §28: "host non-empty and IDNA-valid … any failure files
     `kit.refused` with the reason and touches no network".
   - **The code.** "IDNA-valid" is httpx's `.host` decode, which checks only
     `xn--` labels.
   - **Reproduced by the reviewer on the tip.** `url_problem` returns `None`
     for each of these hosts, and `idna.encode` rejects every one:
     - `http://%zz/k.zip`
     - `http://-a.com/k.zip`
     - `http://a..b/k.zip`
     - `http://.com/k.zip`
     - a 300-character label
   - **The sub-agent ran them through `_kit`,** and 4 of them reached
     `fetch_kit`, which was stubbed. The review's three URLs are refused.
   - **Disclosed, but not as a design violation.** FINAL-REPORT-12 §3 item 4
     says only that "`exa_mple.com` passes". No finding was filed, and the
     Review items table marks REVIEW-11 blocker 2 "closed".

3. **REVIEW-11 blocker 3 is still open: the post-exit sweep kills a leaderless
   group on the `HANDS_JOB` mark (U4 `7f86406` stopped; H-023 and H-025 open;
   `src/hands/runner.py:983-1011`).**
   - **The design.** §28: "the `HANDS_JOB` mark alone never qualifies". The
     mark rule is still in the code.
   - **Stopping was right.** The U4 sub-agent reproduced H-025 independently:
     - `_sweep` runs after `proc.wait()` (`runner.py:614-624`).
     - With "leaderless → refuse", `test_a_cancelled_jobs_orphan_is_reported_and_killed`
       fails (`seen == []`), `[detached]` fails (0 events), and
       `[holding-its-pipes]` times out.
     - §28's rule read literally never signals a group after the reap. The
       proof H-025 offers is by session, not by pid chain, which is a design
       change.
   - **The report is honest.** It marks the blocker **open**, and the mission's
     verdict is `blocked U4`.
   - **Why it is still a blocker.** It remains one until the architect answers
     H-025 (options a/b/c, FINAL-REPORT-12 §5 item 1).

## Should-fix

1. **`kit check` does not judge every named file path (U3 `043413d`,
   `src/hands/kit.py:166-168`).**
   - **The design.** §28 covers "every file path a `send` prompt names … with
     the same path syntax the daemon uses". It is not silent here.
   - **The code.** A path is recognised only when it has an extension of two or
     more characters starting with a letter. Missing `meta/MISSING`,
     `meta/X.c`, `meta/MISSING.1st` and `Makefile` all pass, while the daemon's
     `_path_problem` accepts each of those names.
   - **Disclosed, but not filed.** The limit is in the commit body and §3 item
     4, but there is no finding. Widen the rule or file one.

2. **Role mode does not pin `git -C` to the clone (U1 `3966f9b`).**
   - **The design.** §28: "`git` may only be `-C <clone>` plus the read-only
     allowlist".
   - **The code.** `git -C /tmp log` exits 0 in role mode. The guard does not
     know the clone path.
   - **Disclosed, but not filed.** §3 item 2 mentions it, with no finding.
     Either pass the clone to the hook, for example in the role's environment
     as `HANDS_CONSULT_ROLE` is, or file a finding.

3. **A paused pipeline swallows the engine's consult stops (U2 `e642552`,
   `src/hands/playbook.py:926`).**
   - **The design.** §28: a consultation that ends in escalate, an unrecognised
     verdict, failed, killed, orphaned or limited "stops and notifies".
   - **The code.** `on_event` returns on `self.state.paused` before
     `driver_stop` is decided (read by the reviewer). The sub-agent probed a
     driver escalate or failure while a human had paused the pipeline:
     `consult.done` is filed, with no `pipeline.stop_suppressed` and no
     notification. Nobody is told that the consultation escalated.

4. **Doctor checks one hook file but approves the settings of another (U2,
   `src/hands/doctor.py:488` against `:432`).**
   - **What each check reads.** The settings check accepts any command
     containing `.claude/hooks/bash_guard.py`. The self-test always runs
     `<cwd>/.claude/hooks/bash_guard.py`.
   - **The gap.** A settings file whose command names a different file with that
     suffix passes. Doctor then reports the wiring of a hook it never tested.

5. **`max_consults` after an upgrade with the kickoff already renamed (U2,
   `playbook.py:873`).**
   - **The code.** A kickoff value is recorded only when a playbook loads at job
     start.
   - **The probe.** With an older spool and a playbook already renamed, only the
     new kickoff is known, so every earlier driver job counts. The sub-agent's
     probe counted 4 where 1 was intended.
   - **Why it matters now.** This repository's `PLAYBOOK.toml` already names
     BUILDER-13 (`1250817`), so mission 13 is the first one exposed. The limit
     is disclosed (§3 item 3), but the only test is for a rename after the
     upgrade. Seed the known kickoffs, for example from the committed
     `PLAYBOOK.toml` history or the `meta/BUILDER-*-PROMPT.md` kickoff lines,
     or have the architect accept the limit.

6. **The kit name is not shell-quoted in the apply prompt (U3,
   `src/hands/kit.py:924`).**
   - **The code.** `_is_kit_name` accepts `a$(x).zip`, `` a`x`.zip ``,
     `a;b.zip` and `a'b.zip`. They appear unquoted in `Apply ~/Downloads/<name>
     to this repository …`, while the commit message beside them is
     `shlex.quote`d.
   - **Disclosed.** §3 item 4 says so. The job is held for a human, but the
     prompt the builder runs can carry shell syntax.
   - **What to do.** Quote the name, or refuse shell metacharacters in it.

7. **The apply-verdict exception is narrower than §28's wording and has no
   finding (U3).**
   - **The design.** §28 excuses "a `builder.done` rule whose regex matches the
     literal `VERDICT: kit applied <sha>`".
   - **The code.** It excuses only the text `VERDICT: kit applied`, with an
     optional `^` and trailing space. `VERDICT: kit applied .*`,
     `…applied\b` and `(?i)…` all match the literal and are refused.
   - **Assessment.** This is stricter, which is REVIEW-11 SF7's intent, but
     §28 is not silent. File a finding so the next DESIGN revision states the
     exact-text rule.

8. **The `done` statement's order and precedence are not pinned (U0 `5ea7b9d`,
   `tests/test_docs.py:285`).**
   - **What the test compares.** It sorts the doc's `failure_reason` list
     before comparing it with §6's. A reordered list therefore passes, although
     the doc says "the first that holds, in that order".
   - **Still green.** These edits also pass:
     - "a cancel stays `killed`" changed to "becomes `done`";
     - "the terminating line wins" changed to "a `success` result wins".
   - **Covered.** Every per-value mutation the sub-agent tried, and REVIEW-11's
     three, turn it red.

9. **`hands who` can still show a just-ended job's transcript (U4 `7f86406`,
   `src/hands/who.py:557-562`).**
   - **The code.** The hands pids come from the daemon's `roles[*].running`.
   - **The gap.** A job that has just left `running`, but whose spool record
     never got a `session_id`, is excluded by neither set. Its transcript can
     still appear under `by directory`. This is the sub-agent's reading of the
     code; no probe was run.
   - **Not disclosed.** §3 item 5 lists only the handsd-down and stale-file
     cases.

## Notes

- **FINAL-REPORT-12 §3 NOT PROVEN against the sub-agents' findings:**
  - Item 1 (sweep) is accurate and reproduced (blocker 3).
  - Item 2 (guard) is contradicted on comments (blocker 1). Its `-C` and
    `--gate` limits match. `--gate` is not forbidden by §27.
  - Item 3 (consult) matches. It omits the paused case (should-fix 3) and the
    doctor substring (should-fix 4).
  - Item 4 (kit) understates the IDNA gap (blocker 2) and the named-path
    departure (should-fix 1). Its unquoted kit path and `~/Downloads`-only
    byte-equality match.
  - Item 5 (who) omits should-fix 9.
  - Items 6 and 7 match, and the sub-agents added only the order and precedence
    gaps (should-fix 8).
- **Review items table.**
  - The rows for blocker 1 ("closed") and blocker 2 ("closed") are contradicted
    by the disk.
  - The blocker 3 row ("open") and the blocker 4 and 5 rows are honest.
  - The SF6 row's "closed (extension ≥ 2 chars …)" states the limit, but the
    limit is a departure (should-fix 1).
- **U1, normal mode.** 12 REVIEW-11 probes are asserted *allowed* in normal
  mode, among them `& hands go`, quoted `--context=clear` and `--role aux`. The
  U1 sub-agent judged that right: §28's both-mode rules concern expansion, and
  those commands expand nothing. Of the 139 commands the parent's tables
  allowed, only the aux `--prompt-file` send under consult role builder is now
  refused, which is §28's rule. H-024's expansion-position reading is sensible
  and filed.
- **U1, `--cont keep`** exits 0 in role mode. That is argparse abbreviating
  `--context keep`, which is harmless.
- **U2's end-to-end coverage.** These ran end to end with a playbook that has
  no driver rules: escalate, unrecognised, failed, killed by cancel, killed
  before spawn, limited, and orphaned at start. A *missing* verdict is tested
  only at unit level. The sub-agent's attempts to remove a stop all still
  stopped: a verdict-less `driver.done` send, `^VERDICT: escalate` send, a
  `^VERDICT:` catch-all send, and a `driver.failed` send.
- **U2, a queued driver job that is cancelled.** By reading, it files
  `consult.done` and stops (`daemon.py:643`), but no test covers it.
- **U2, the counter.** A kit apply that started but failed counts as a new
  start (`playbook.py:1198`); a held-then-denied one does not.
- **U2, limited driver jobs are no longer resumed.** §6's resume prompts name
  only builder and aux, and §28 makes `driver.limited` a stop, so there is no
  conflict. The exception is recorded only in the commit body.
- **U3.** `http://a.com:+80/` is accepted, and httpx reports its port as `None`.
  An empty alternative, as in `(question|)`, passes unjudged.
- **U4's stop and H-025 are well founded.** The sub-agent brief allows a
  sub-agent to file a finding.
- **U5.** The brief-only acceptance kit reproduces: 6 of 6, exit 0, matching
  the body's transcript. It checks the repository's `PLAYBOOK.toml` rules (5
  builder, 2 aux, 2 driver) and skips only the kickoff comparison. A kit of
  `PLAYBOOK.toml` + BUILDER-12 fails only the kickoff check, as §27's
  convention expects. The U5 sub-agent's throwaway local commit `61a8bcc` was
  never pushed and is an unreferenced object.
- **U0.** H-023's citation `tests/test_runner.py:1144` points inside the
  `_last_resort` test, which starts at `:1138`.
- **No leftover worktrees.** `git worktree list` shows only the main checkout
  after the review.

## Per-commit verdicts

### 5ea7b9d (U0)

**5ea7b9d** (mission 12 U0, `plan:` commit) is **PASS on all four points, with test gaps**. My worktree is removed and the main checkout was not touched. The other `/tmp/rev12-*` worktrees are not mine.
1. **Unit and files: PASS.** The body names mission 12 U0 (BUILDER-12-PROMPT), DESIGN v3.11 §28 bookkeeping, §27 and §6, and REVIEW-11 blocker 5, blocker 3, should-fix 4 and should-fix 5. It lists all 4 files in `--stat`: meta/plan.md, meta/CHECKPOINT.md, meta/findings/FINDINGS.md and tests/test_docs.py.
2. **Test-first: PASS with gaps.** The test is new: the parent's test_docs.py doesn't have it. It fails on all three REVIEW-11 mutations. It also fails on every per-value change I tried: dropping `spawn_error` from the list, renaming `no_num_turns`, dropping the "could not be spawned" clause, and flipping each cause (non-zero exit to 0, without `num_turns` to with, subtype `error` to `success`, stderr to stdout, without a final result to with).
   - **Still passes:** reordering the `failure_reason` list, even though the doc says "the first that holds, in that order" (tests/test_docs.py:285 sorts the list before comparing).
   - **Still passes:** an added sentence "A job whose process crashed is `done`." The body admits this one.
   - **Still passes:** "a cancel stays `killed`" changed to "becomes `done`", and "the terminating line wins" changed to "a `success` result wins". Precedence is not pinned.
   - **Still passes:** "`error_max_turns` included" changed to "excluded". The older `error_subtype_rule` test covers this one, so it is not a new gap.
   - Doc restored after each run.
3. **Gate: PASS.** `./scripts/check` ends: `1733 passed in 135.98s (0:02:15)` / `== cli smoke ==` / `check: green`.
4. **Design conformance: PASS.**
   - Each of H-018 to H-022 now has its resolution in its own section and exactly one Status line (FINDINGS.md:994, 1038, 1111, 1152, 1212). The separate "Resolutions in DESIGN v3.10" section is gone. H-019's second status paragraph is now labelled "Progress" (:1027).
   - H-023 (:1214-1238) matches REVIEW-11 blocker 3, including the environment mark, disclosure without a finding, and `_last_resort`-only testing. Its quote of §28 is exact.
   - DESIGN.md and docs/ are not in the diff. plan.md and CHECKPOINT.md are allowed in a `plan:` commit.
   - Minor: the cited `tests/test_runner.py:1144` points inside the `_last_resort` test, which starts at :1138.

**Not proven:** whether each §28 quote matches for H-018 to H-021 (I checked only H-022 and H-023), the content of plan.md and CHECKPOINT.md, and whether the doc's reason order agrees with the runner (§6 gives no order apart from the termination line winning).

### 3966f9b (U1)

Review of 3966f9b (mission 12 U1, guard on shlex). Verdict: **FAIL**. The guard still misreads a `#` comment, so a quote inside the comment hides a later command. That gets a `hands go` past the role-mode guard, and a write past the normal-mode guard.

1. **Commit body: PASS.** It names mission 12 U1 and DESIGN §28's first block, with §27, §8, §12 and REVIEW-11 blocker 1. It lists both files in `--stat`.
2. **Test-first: PASS, with one wrong claim in the body.** With the parent guard, `tests/test_bash_guard.py` is red (167 failures). Most are the missing `consult_role` parameter. The 4 real normal-mode reds are the `$'…'`, brace, `x=…; $x` and `& hands open` probes. Running the probes directly through the hook (hook JSON on stdin; the hook exits 0 to allow, 2 to block):
   - **Role mode:** the parent allowed every REVIEW-11 probe except one; the new hook blocks all of them.
   - **Normal mode:** the new hook blocks `& hands open`, `$'…'`, the brace word and `x=…; $x`, and allows the rest.
   - **Wrong claim:** the body says the parent allowed the backslash-newline `--context=clear` probe. It did not: the parent already exited 2 in role mode.
3. **`./scripts/check`: PASS.** Tail: `1882 passed in 141.68s (0:02:21)` / `== cli smoke ==` / `check: green`.
4. **Design conformance:**
   - **(a) Probes: PASS.** Every probe is asserted blocked in role mode. In normal mode, 12 are asserted allowed: `& hands go`, `& approve`, the quoted and escaped `--context=clear`/`--file`, `--role aux`, and `--project`/`--socket`. I judge that right: §28's both-mode rules are about shell expansion, and those are ordinary human commands that expand nothing.
   - **(b) Allowed tables: PASS.** I checked all 139 commands the parent allowed. Only `hands send --role aux --context keep --prompt-file …` is now refused, and only when the consultation role is builder. That is §28's rule, and the case moved to `ROLE_SEND` under consult role aux.
   - **(c) Bypasses: FAIL.** `driver/hooks/bash_guard.py:381` sets `commenters = ""` and `_scan` (`:278`) has no comment state, so an apostrophe inside `# …` opens a quote that bash never sees. I confirmed in real bash with a stand-in `hands` script (not the real CLI). The parent hook has the same hole, but §28 requires this fix, and the body's claim that comments are "handled fail-closed" is false. Commands that exit 0:
     - Role mode: `hands show x # it's` + newline + `hands go #'`. Bash ran `hands go`.
     - Role mode: `hands show x # it's` + newline + `hands send --role builder --context clear m #'`. Bash ran the clear send.
     - Normal mode: `ls # it's` + newline + `touch /tmp/…/PWNED #'`. Bash created the file.
   - **The other role-mode attempts** from the list exited 2. Three exited 0 without breaking the design:
     - `--cont keep` is argparse reading `--context keep`.
     - `--gate x` is not forbidden by §27.
     - `git -C /tmp log` passes because the `-C` value is not pinned to the clone, which the body discloses. §28 says "`-C <clone>`", so this is a disclosed gap.
   - **(d) H-024: PASS.** Counting only characters where bash still expands them is sensible, is disclosed in the body and in FINDINGS H-024 (status open), and keeps every probe blocked.
   - **(e) PASS.** DESIGN.md, `meta/plan.md` and `meta/CHECKPOINT.md` are untouched; the commit changes only the two files.

**Not proven:** heredoc, `case` and arithmetic handling (only spot-checked); whether handsd sets `HANDS_CONSULT_ROLE` (that is U2); and whether a real claude session honours the hook. I removed my worktree; the other `/tmp/rev12-*` worktrees were left as they are.

### e642552 (U2)

e642552 (mission 12 U2): overall PASS. Three minor defects and three things not proven; the worktree is removed and the main checkout is clean.

1. **Body, PASS.** It names U2, §28's "Consult and the driver role" block, §27, §8, §10 and REVIEW-11 should-fix 1, 2, 3 and 8. The Files list matches `--stat` exactly (10 files). §6 is not in the header, although limits.py changes §6's resume; it appears only under "Choices".
2. **Test-first, PASS.** With the parent's src and the new tests, 37 fail and none on imports. Examples: the playbook refused `driver.killed` as an event, stop reasons lacked "§28", the killed end-to-end test timed out, and every doctor settings/guard/self-test case failed. src was restored afterwards.
3. **`./scripts/check`, PASS.** Tail: `1916 passed in 163.40s (0:02:43)` / `== cli smoke ==` / `check: green`.
4. **(a) Coverage, PASS with a gap.** These run end-to-end (real daemon, fake claude) with a playbook that has no driver rules: escalate, unrecognised, failed, killed by cancel while running, killed before spawn, limited, orphaned at daemon start. A missing verdict is tested only at unit level, with both playbooks.
5. **(b) Removing a stop, PASS.** Every attempt still stopped, sent nothing, and notified once:
   - a verdict-less `driver.done` rule with then="send" or "notify" (the test's `CARRY_ON` playbook);
   - my probes: `^VERDICT: escalate` with then="send", a `^VERDICT:` catch-all with then="send", and `driver.failed` with verdict `.*` then="send".
   - **Minor defect:** if a human has paused the pipeline, a driver escalate or failure files `consult.done` but no stop, no `pipeline.stop_suppressed` and no notification. `on_event` returns while paused (playbook.py:926) before the engine's stop is decided (probe P2).
6. **(c) Counter, PASS as disclosed.** A kit job that was held and then denied never started, so it does not count (probe). A kit apply that started but failed does count as a new start (playbook.py:1198), which is lenient against §28's "plan: kit apply".
   - A kickoff value is recorded only when a playbook loads (playbook.py:873). On the first run after upgrade, with the kickoff already renamed and an old spool, only the new value is known, so every driver job counts: my probe got 4 where 1 was intended. That errs toward stopping sooner and is disclosed, but the live repo's PLAYBOOK already names BUILDER-13 (1250817), so it applies there.
7. **(d) Driver job cancelled while queued, PASS by reading, untested.** `Daemon.cancel` → `_consultation_ended` → `on_job` files `consult.done` and the journal line, then the engine stops on `driver.killed` (daemon.py:643). The worker then skips the job because it is no longer queued, so nothing is filed twice.
8. **(e) Doctor, PASS.** The row fails for settings missing, unparseable, no hooks, another hook, not Bash, not PreToolUse; for a missing guard; for a red self-test; and for non-empty `permission_flags`. The self-test runs with the role's environment, and the test's hook is green without `HANDS_ROLE` and red with `HANDS_ROLE=driver`, which proves role mode is used.
   - **Minor defect:** the settings check only looks for `.claude/hooks/bash_guard.py` as a substring of the command (doctor.py:488), but the self-test always runs `<cwd>/.claude/hooks/bash_guard.py` (doctor.py:432). A command naming some other file with that suffix passes unverified.
9. **(f) Limited driver not resumed, PASS with a note.** §6 automates the limit resume but gives resume prompts only for builder and aux. §28 says a consultation ending in `driver.limited` stops and notifies, so a resume would run the driver after the stop. There is no real conflict, but the exception is written only in the commit body; no finding records it.
10. **(g) Docs and untouched files, PASS.** DESIGN.md, meta/plan.md and meta/CHECKPOINT.md are untouched; docs/PLAYBOOK.md and docs/INTEGRATION.md are updated.

**Not proven:** a real claude driver session honouring the hook; the queued-cancel path under test; an orphaned driver job at start with no playbook loaded.

### 043413d (U3)

**043413d: 2 FAIL, 4 PASS. Point 4a is blocker-grade: `url_problem` accepts hosts that aren't valid IDNA, and the daemon then goes to the network.**

1. **Body — PASS.** It names Mission 12 U3 and DESIGN v3.11 §28 (Kit transport block) with §12 and §27, plus REVIEW-11 B2 and SF6/7/9. It lists all 6 files in --stat.
2. **Test-first — PASS.** Tests run against the parent's `src/` (in a second worktree): 61 of the new tests fail, and all are behavioural `AssertionError`s. The only name error is `AttributeError: pattern_alternatives`. Nothing broke collection, so no shim was needed.
3. **`./scripts/check` — PASS.** Tail: `1980 passed in 174.30s (0:02:54)` / `== cli smoke ==` / `check: green`.
4a. **URLs — FAIL.** No exception escapes. The 3 review URLs, `[::1]:0`, `host:abc`, `user:pw@/`, `http:///`, `#frag\x00` and non-str inputs are all refused; uppercase `HTTP` and `exämple.com` are rightly accepted. But `url_problem` also accepts `http://%zz/`, `http://-a.com`, `http://a..b/`, `http://.com/` and a 300-char label, and `idna.encode` rejects every one of those hosts. Run through the `_kit` path (extra params on the existing test), 4 of them reached `fetch_kit` (fetch called, not refused). The rule lives at src/hands/phone.py:558-563: "IDNA-valid" only means httpx's own decode, which skips ASCII hosts. The body discloses that, but §28 is not silent here and no finding was filed. Also `http://a.com:+80/` is accepted and httpx reports its port as None (`+80` dropped).
4b. **Named paths — FAIL (departure not filed).** The quoted, trailing-comma and trailing-full-stop forms of `meta/MISSING.txt` fail, correctly. `meta/MISSING`, `meta/X.c`, `meta/MISSING.1st` and `Makefile` pass. The daemon's `_path_problem` accepts all of those names, so §28 ("every file path … same path syntax the daemon uses") is not silent. The rule needing a 2+ char extension that starts with a letter (src/hands/kit.py:166-168) is disclosed in the body but needs a finding.
4c. **Apply exception — PASS with a note.** Only one rule is excused: a second one fails and names the first, and an `aux.done` copy fails. `^VERDICT: kit applied [0-9a-f]+` fails, which is right because it does not match the literal `<sha>`. `VERDICT: kit applied .*` also fails even though it matches the literal. So does `(?i)…`, and so does `…applied\b`, which also matches it. The exact-text rule is stricter than §28's wording, though it is what SF7 intends; the body discloses it, but it deserves a finding.
4d. **KIT.md — PASS.** The 72/73-char limit, quotes, CR, empty, non-UTF-8 and the notice all behave as §28 says, and the message is `shlex.quote`d. Byte-equality holds only for `~/Downloads`, which is disclosed. The kit path itself is not quoted: `_is_kit_name` accepts `a$(x).zip`, `` a`x`.zip ``, `a;b.zip` and `a'b.zip`, and the prompt reads `Apply ~/Downloads/a b$(x) to this repository` (src/hands/kit.py:924). §28 doesn't require quoting it, but it is a risk.
4e. **Every alternative must match — PASS.** A reasonable reading: `(question|questoin)` and a top-level `…|^VERDICT: nope` fail, `(?:question|mission (?P<n>\d+) blocked)` passes. An empty branch like `(question|)` passes unjudged.
4f. **Untouched files — PASS.** DESIGN.md, meta/plan.md and meta/CHECKPOINT.md are not in the diff.

**Not proven:** the fetch for the accepted URLs was stubbed, so no real DNS or network access was observed. The shell-injection risk from the unquoted kit path is inferred, not exploited. Both review worktrees are removed and the main checkout is clean.

### 7f86406 (U4)

Review of 7f86406 (mission 12 U4 "who"). Verdict: PASS on all points. The who half is sound and H-025 reproduces.

1. **Body: PASS.** It names mission 12 U4, DESIGN v3.11 §28 "Process accounting (blocker 3) and who (blocker 4)", §27 (H-020) and §6. Its files list matches `--stat` exactly (docs/INTEGRATION.md, meta/findings/FINDINGS.md, src/hands/who.py, tests/test_who.py).
2. **Test-first: PASS.** With the parent's who.py, the test file fails only on plumbing (`TypeError: Sources.__init__() got an unexpected keyword argument 'session_of'`). At the commit, with only the hands-pid union removed, both probe cases go red on behaviour (`last: JOB-PROMPT-TEXT from the builder`). Restored.
3. **Gate: PASS.** The tail of `./scripts/check` was `1982 passed in 175.21s (0:02:55)` / `== cli smoke ==` / `check: green`. I ran it once, not three times.
4. **(a) who: PASS.**
   - The fallback now excludes the spool's ids plus `session_of(pid)` for every pid in `hands_pids` (src/hands/who.py:557-562).
   - Those pids come from the daemon's `roles[*].running`. The driver is a daemon role, so its running job is covered.
   - The sessions file is read safely: `session_id_for` opens only `<pid>.json` by name, checks `pid` and a basename `sessionId`, never opens `.key` and never lists the directory. The key-file test still asserts both.
   - Gap not disclosed: a job that just ended has left `running`. If its spool record never got a `session_id`, its transcript can still show under `by directory`. With handsd down only spool ids exclude, which is disclosed.
5. **(b) Sweep: PASS, and blocker 3 is still open.**
   - `_sweep` runs after `_until_exit` and `proc.wait()`, so claude has already been reaped (runner.py:614-624).
   - I made `_group_is_the_jobs` return False when the leader is gone (edit after runner.py:1007) and ran the three tests. `test_a_cancelled_jobs_orphan_is_reported_and_killed` failed (`seen == []`). `[detached]` failed (`len(events) == 1` → `0`). `[holding-its-pipes]` failed with an asyncio TimeoutError. This matches H-025. Reverted.
   - The reasoning holds: orphans are reparented to init or a subreaper, so no pid chain reaches the job's pid, and group mode has no cgroup. Its option (b), proof by session id, is not "by pid chain", so it would be a design change. Stopping with a finding was right under the brief's "if the unit needs a design change, stop and write a memo".
   - On disk the `HANDS_JOB` mark rule is still in runner.py:983-1011, and H-023 still says `Status: open (code: mission 12 U4)`.
6. **(c) Bookkeeping: PASS.** The brief (meta/BUILDER-12-PROMPT.md:57) allows a sub-agent to file a finding. DESIGN.md, meta/plan.md and meta/CHECKPOINT.md are not in the commit.

Not proven: the gate green three times in a row, the probe against a live daemon or a real ~/.claude, a stale sessions file from a reused pid, and every part of §28's sweep rule. The worktree is removed and the main checkout is clean.

### 1250817 (U5)

**Review of 1250817** (mission 12 U5, "playbook: kickoff names BUILDER-13; H-022's kit check exits 0"). Verdict: all five points pass, with no defects.

1. **PASS: body, file list and diff.** The body names mission 12 U5, DESIGN v3.11 §28 (Bookkeeping, H-022 resolved), §27 Conventions and §10, plus REVIEW-11 blocker 5. It lists both files from `--stat` (`PLAYBOOK.toml`, `tests/test_playbook.py`). The `PLAYBOOK.toml` diff is exactly the kickoff line at `PLAYBOOK.toml:7` (1 line out, 1 in), and the test change is only the pinned string and its docstring at `tests/test_playbook.py:242-250`.
2. **PASS: test-first.**
   - With the parent's `PLAYBOOK.toml` checked out and not committed, the test goes red only on `PlaybookNotCommitted` ("is dirty") at `src/hands/playbook.py:480`, which tells us nothing.
   - On a throwaway local commit with the old kickoff line, it goes red on the kickoff value itself: `AssertionError` at `tests/test_playbook.py:248`.
   - So the test really pins BUILDER-13, which backs the body's claim.
3. **PASS: `./scripts/check` at the commit.** Tail: `1982 passed in 172.32s (0:02:52)` / `== cli smoke ==` / `check: green`, exit code 0. The pass count matches the body's 1982.
4. **PASS: acceptance.**
   - **Brief-only kit** (`/tmp/rev12-u5-kit` holding only `meta/BUILDER-12-PROMPT.md`, `--repo .`): exit 0 with `kit check: pass (6 of 6 checks)`. The six check lines match the body's transcript word for word; only the kit name differs.
   - **Kit of `PLAYBOOK.toml` plus the brief:** exit 1. Only the playbook check fails: the kit's kickoff names BUILDER-13 but the brief's kickoff line names BUILDER-12. §27 says the kickoff names the next mission, so this is expected.
   - **Loader and scope:** the real `load_playbook` gives `hands-missions | Read meta/BUILDER-13-PROMPT.md ...`. Nothing else in `PLAYBOOK.toml` changed, and `DESIGN.md`, `meta/plan.md` and `meta/CHECKPOINT.md` are untouched.
   - **Repo playbook rules:** the brief-only form does run the repo's `PLAYBOOK.toml` rules. When the kit carries no playbook, `_check_playbook` returns the repo's playbook and `_check_verdicts` checks it (5 builder, 2 aux and 2 driver rules). It skips only the repo's kickoff comparison, which the body discloses.

**Not proven:**
- Nothing checks that the kickoff names a brief that exists; `meta/BUILDER-13-PROMPT.md` is absent, which the body discloses.
- The body's claim of three consecutive green runs was not re-checked; I ran the gate once.

**Cleanup:** my worktree and `/tmp` kit dirs are removed, and the main checkout is clean at 0f75521. The throwaway commit 61a8bcc was never pushed and is left unreferenced in the shared object store. Other `/tmp/rev12-*` worktrees exist that aren't mine; I left them alone.
