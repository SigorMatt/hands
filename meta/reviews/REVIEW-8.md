# REVIEW-8 — cold review of hands mission 8

VERDICT: review mission 8 blockers=0 should-fix=4

Base `910b372` (`review: mission 7`, the last `review:` commit on
origin/main). Range `910b372..94913ac`: 17 commits. That is the architect's kit
`da8df27`, eight unit commits (U0 `9ae7975`, U1 `df8c1fd`, U2 `68e1048`, U3
`4782a4a`, U4 `7183478`, U5 `6fcd7d7`, U6 `a93e3a7`, U7 `c41473c`) and eight
`meta:` bookkeeping commits. One sub-agent reviewed each unit commit, in a
detached worktree at that commit. Read beforehand: DESIGN v3.7 §24 (with §4,
§6, §10, §11), `meta/BUILDER-8-PROMPT.md`, `meta/FINAL-REPORT-8.md`,
`meta/findings/FINDINGS.md` (H-014, H-015, H-016).

## Blockers

None. `./scripts/check` is green at every unit commit, and at the pushed tip
`94913ac` it is `1424 passed` / `== cli smoke ==` / `check: green` (run by the
reviewer). Every unit adds tests that go red when its product change is reverted
or mutated. No unit commit touches `DESIGN.md`, `meta/plan.md` or
`meta/CHECKPOINT.md`. No claim in FINAL-REPORT-8 was found contradicted by the
disk.

## Should-fix

1. **REVIEW-3 should-fix 7 is closed only below `main()` (U5 `6fcd7d7`).**
   `src/hands/cli.py:753` (`return exit_code(command, result)`) is not pinned by
   any test. The reviewer changed it to `return 0` in a worktree at the tip and
   ran the whole suite: `uv run --extra dev pytest`, exit 0. The review-items
   table marks the item `closed`; §3 item 8 admits the route is tested only
   through `_render` and `exit_code`. Pin the socket route's exit code through
   `main()` for at least one command, or mark the item partly closed.
2. **DESIGN v3.7 §6's vocabularies disagree with the code, and no finding
   covers v3.7.** §6 lists `failure_reason` as `harness_terminated | nonzero_exit
   | no_result`. The code writes `harness_terminated`, `nonzero_exit`,
   `no_final_result`, `error_result`, `no_num_turns` and `spawn_error`
   (`src/hands/runner.py`). §6's `gate` is `decided_by: cli|driver|button`, but
   U4 records `phone` (`src/hands/api.py:589`; §24 asks for it). H-014's mission
   7a status paragraph names the code's reasons, but the architect wrote v3.7 §6
   after it. U0 and U1 both claim §6 and left the gap unreported. Neither
   mismatch was introduced by this mission's diff. File a finding so the design
   or the wire names are reconciled; the driver reads these fields verbatim.
3. **`_last_resort` kills a process group it has not checked (U3 `4782a4a`).**
   `src/hands/runner.py:679-695` sends `os.killpg(job.pid, SIGKILL)` in group mode
   with no membership check. The normal path only signals a group that still has
   members (`_kill_group`, `runner.py:940`). If `run()` raises after claude was
   reaped, the pid can have been reused by another `start_new_session` leader,
   such as another hands job, and that group would be killed. The window is small
   and no test covers it. Check `group_pids(job.pid)` first.
4. **The phone channel's reconnect warning can write `cmd_topic` to the journal
   (U4 `7183478`).** `src/hands/phone.py:159-162` logs `f"{type(exc).__name__}:
   {exc}"`. `notify.http_stream` calls `response.raise_for_status()`
   (`src/hands/notify.py`), and httpx puts the full request URL
   (`<ntfy_url>/<cmd_topic>/json?since=…`) in that exception's text. Per
   `docs/INTEGRATION.md:275-277`, "anyone who can read `cmd_topic` can read your
   secret". The token is kept out of the log, but the topic that reveals it is
   not. Log the exception type and status code without the URL, and add a test
   that the topic is absent from the warning.

## Notes

- **Kit `da8df27`** is the architect's and is not a unit. It is the only commit
  in the range that touches `DESIGN.md` (v3.7). `meta:` commits touch only
  `meta/plan.md`, `meta/CHECKPOINT.md` and `meta/journal.md`, plus
  `meta/FINAL-REPORT-8.md` in `94913ac`. U0 `9ae7975` is `plan:`, as §24
  requires. A scripted check found no commit in the range touching a file its
  body does not name. `pyproject.toml` gains only the `handswho` script; the
  runtime dependencies are still `httpx` alone.
- **Acceptance** at the tip: `hands --help` lists `who`; `handswho --help` works;
  doctor without `[notify]` extras reports phone and who off, exit 0 (U7
  reviewer, temp HOME); `PLAYBOOK.toml` has both stop rules (lines 98, 103) and
  no `quiet_hours`; `meta/prototypes/` is absent. All confirmed.
- **FINAL-REPORT-8 §3 NOT PROVEN against the sub-agents.** It is consistent, and
  the three mandatory items (real systemd scope, real ntfy delivery, real
  task-killed shape) are present. The sub-agents found these, which §3 does not
  list:
  (a) The phone replay floor is `when < started_at` (`phone.py:189`), so a
  message stamped in the same second as a restart is acted on.
  (b) The U2 fixture leaves out the second, `local_agent` kill (no command) that
  the real 0mtygi953 stream carries next to the Bash kill. A task notification
  with status `failed` is not tested; the code matches only `stopped`.
  (c) In scope mode, the `live_pids` branch (`runner.py:488`) and a scope sweep
  that finds processes are untested. §3 item 1 covers this in general terms.
  (d) Anyone who can read `ntfy_topic` sees `cmd_topic` in a held job's button
  URL, and can then read typed secrets still cached there. This follows from §24
  and is stated in `docs/INTEGRATION.md:275-279`, not in the report.
  (e) The `handswho` picture carries the human's last transcript prompt (70
  characters) and command lines (60 characters), as the prototype did.
  `docs/INTEGRATION.md` warns about it.
- **`who` (U6 `a93e3a7`).** A requested push skips `min_gap` (`who.py:612`), and
  its scan counts toward the two-scan debounce (`who.py:609`). One timed scan
  plus a command can therefore settle a session state, where the prototype only
  flagged the next timed scan. `who_cmd_topic` takes no secret (DESIGN names
  none), so anyone who knows it can force pushes without limit. For the
  architect, with FINAL-REPORT §5.4. §4's `who [--daemon]` is implemented. The
  brief says "over the socket" and §24 says "in-process"; the code agrees with
  both, because the daemon builds the picture in its own process and the client
  reads it over the socket.
- **H-016 is correct and larger than filed.** §10's example lacks the two stop
  rules, and so does §10's `### Events` list (`DESIGN.md:356-359`), which still
  omits `monitor.task_killed` and `monitor.orphan_processes`. U2's brief asked
  for the §10 example rule; U2 put it in `docs/PLAYBOOK.md` prose, and no finding
  was filed until U7.
- **Quiet hours.** `src/hands/doctor.py:550` still tells the human "Quiet hours
  delay notifications … so run this outside them". §11 v3.7 says "notifications
  are never delayed". This predates U7 and is disclosed in FINAL-REPORT §5.3.
- **Doctor "never as errors".** The new `notifications` and `who` rows are always
  `ok`. The `phone` row shows `warn`, with exit 0, when `cmd_topic` is set
  without `ntfy_topic`. A `cmd_topic` without `cmd_secret` fails the `config`
  row, exit 1, as §24 and the brief require.
- **U4 goes beyond the brief**, and says so in its body: config load also refuses
  a secret containing whitespace, a `cmd_topic` equal to `ntfy_topic`, and the
  same ntfy key in both `[server]` and `[notify]`.
- **U3** meets the brief's gate: the double fork in `fake_claude.py:206` has no
  `setsid`, so it stays in the group. A `setsid` escape is untested in both modes
  (FINAL-REPORT §3 item 5).
- **H-014's own case is now `done`** under v3.7 §6's precedence, as FINAL-REPORT
  §5.1 raises for the architect.
- Nit: `tests/test_runner.py:830`, the `"isolated": 1,` entry, is mis-indented
  inside a dict literal. This is harmless and `ruff check` does not flag it.

## Per-commit verdicts

sha 9ae7975 U0 — Plan and corrections (`plan:` commit); DESIGN §6, §24 (the body also cites §8, §11)
1 unit/sections: PASS. The body's "Files:" list names all 4 files that `git show --name-only` reports: meta/CHECKPOINT.md, meta/findings/FINDINGS.md, meta/plan.md, tests/test_daemon.py. meta/prototypes/claudewho.py is present from da8df27 and unchanged, as claimed. Three tests drive `hands show` through the CLI against a real daemon: failed harness_terminated and failed nonzero_exit each print exactly one `  failure  <reason>` line, and a done job prints none. H-015 matches DESIGN §24 "the phone channel" point by point: the `[notify]` keys, the outbound long-poll, the five commands, `status` published to `ntfy_topic`, `cmd_secret` as the last word, the 32-byte single-use nonce, the secret never in a notification, `decided_by: phone`, and "Nothing but commands and status lines". Nothing is invented or dropped. The additions (reconnect, ignore a bad secret or nonce, the doctor checks) are correctly credited to BUILDER-8-PROMPT U4, not §24. Its quotes from §8 (DESIGN.md:304-307) and meta/BACKLOG.md (item 5, lines 26-32; line 59) are verbatim.
2 test-first: PASS by mutation, since the commit has no product change. Baseline: `uv run pytest tests/test_daemon.py -k show_prints` gave 3 passed. M1, deleting the `("failure", "failure_reason")` row in src/hands/cli.py:395: 2 FAILED (both failed-job cases), done-job test green. M2, printing `failure_reason` even when null (edit to the `if value not in (None, "")` check): 1 FAILED (done-job test). After `git checkout 9ae7975 -- src/hands/cli.py` the tree was clean and the tests went back to 3 passed.
3 check: "1238 passed in 67.96s (0:01:07)" / "== cli smoke ==" / "check: green", exit 0. One run, clean tree, and the count matches the commit's claim.
4 design/forbidden files: PASS. DESIGN.md is untouched. meta/plan.md and meta/CHECKPOINT.md changed, which the builder's U0 commit may do. The `plan:` prefix follows §24's rule for U0 commits.
NOT proven: (a) the other failure reasons (no_final_result, error_result, no_num_turns, spawn_error) through `show`, and the `--json` route, as the body itself says. (b) DESIGN §6 (§6 line 16 of DESIGN.md) lists `harness_terminated | nonzero_exit | no_result` but the code uses no_final_result, error_result and more. That mismatch predates this commit and belongs in a finding, not here. (c) The done-job case is not specified by the design; the test pins the code's existing behaviour. (d) The claim "green three times" was not re-run three times. (e) I did not read the contents of plan.md or CHECKPOINT.md. The worktree is removed and the main tree is clean.

sha df8c1fd U1: the terminating line is the harness's exact message and never beats success; DESIGN §2, §6, §24 (REVIEW-7 should-fix 2 and 4)
1 unit/sections: PASS. The matcher is `re.match` on "Background tasks still running after [0-9]+s; terminating\. Set CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=", case-sensitive (runner.py:124-133). Both REVIEW-7 over-match lines are pinned verbatim as `REVIEW_7_OVER_MATCHES` (test_runner.py). The sweep sniffs for a NUL in the first 8192 bytes. The `BUILDER-1-PROMPT.md` allowance has a stale-check. `no_turns` is in fake_claude and H-014 has its status paragraph. The body names all 7 files that `--name-only` shows. Should-fix 3 is explicitly left to U0.
(a) DESIGN §6 says: "Precedence: a cancel stays `killed` and a limit stays `limited` even when the termination line is present; a job with a `success` result, turns and exit 0 is `done` whatever else stderr says." `_failure_reason` (runner.py:655-663) matches this. The "succeeded" test (success, no is_error, num_turns, exit 0) only guards `harness_terminated`. It could not matter for the other reasons: each of those already needs one of the three conditions to fail. Only a stderr line can contradict success, and that is what §6 covers.
(b) It does not over-exclude. 20 tracked paths are excluded: DESIGN.md, tests/test_docs.py, meta/CHECKPOINT.md, meta/plan.md, meta/journal.md, meta/FINAL-REPORT-1..7.md, meta/findings/FINDINGS.md, meta/prototypes/claudewho.py, meta/reviews/REVIEW-2..7.md. meta/drafts/ is untracked. These are swept: meta/BACKLOG.md, ROADMAP.md, REVIEW-PROTOCOL.md, BUILDER-1..8-PROMPT.md, CLAUDE.md, driver/CLAUDE.md, .claude/settings.json, .claude/hooks/no_background.py, driver/hooks/bash_guard.py.
2 test-first: PASS. With `git checkout df8c1fd^ -- src/hands/runner.py`, `uv run pytest tests/test_runner.py tests/test_docs.py tests/test_daemon.py tests/test_playbook.py` gave "18 failed, 300 passed": the 0mtygi953 `'failed' == 'done'` test, both over-match run tests and 15 matcher negatives. After `git checkout df8c1fd -- .` it gave "318 passed" with a clean tree. The sweep is test-only, so I used a mutation instead: putting `meta/` back as a single exclusion turned 7 test_docs tests red (5 live-meta classifier cases, the tree test, the sweep test). The 5 "missing one of the three" cases already passed at the parent, so they guard against regression rather than show red.
3 check: "1285 passed in 76.05s (0:01:16)" / "== cli smoke ==" / "check: green", exit 0, first run.
4 design/forbidden files: PASS. The commit does not touch DESIGN.md, meta/plan.md or meta/CHECKPOINT.md; FINDINGS.md is the only meta file it changes.
NOT proven: No real harness termination was seen. The exact message was not re-read from the claude binary; the tests' `TERMINATING` constant matches the message given in the brief. A coloured or prefixed real line would now go unmatched. "Turns" is read as `num_turns is not None`, so 0 turns counts, which DESIGN does not spell out. The §6 reason list (`no_result`) differs from the code's names (`no_final_result`, `error_result`, `no_num_turns`); that gap is older than this commit, not a defect of it. Worktree removed; main is clean.

sha 68e1048 U2 — monitor.task_killed from each role job's stream-json, once per task; DESIGN §5, §10, §24 (BACKLOG item 1)
1 unit/sections: PASS. (a) The fixture really is copied from real logs: all 7 `system` lines appear word for word in ~/.hands/jobs/0mtygi953-ym63 (2.1.269) and 0mtyvy78g-yq73 (2.1.270), and both `Bash` tool_use items match log lines 1406 and 608. Builder and aux are both covered, repeats are filed once per job, and the event is accepted by playbook `on` and `wait --for`. (d) The commit body lists exactly the 12 files the commit touches.
2 test-first: PASS. With the 7 product/doc files reverted: test_monitor.py fails to import (`cannot import name 'TaskKillWatch'`), and 4 tests fail in test_playbook/test_spool. With only daemon.py reverted: 5 failed, 1 passed (the normal run passes, every kill case fails). Restored: `275 passed in 17.49s`.
3 check: `1300 passed in 134.60s (0:02:14)` / `== cli smoke ==` / `check: green` (green on the first run, no rerun needed)
4 design/forbidden files: PASS. DESIGN.md, meta/plan.md and meta/CHECKPOINT.md are not touched. (c) The brief's rule was not added to the §10 example. That example and its copies in tests/fixtures/playbook_example.toml and docs/PLAYBOOK.md must stay word for word, so the `stop` rule went into the PLAYBOOK.md text instead (docs/PLAYBOOK.md:67). No finding was filed at this commit; U7 filed H-016 later, still open.
NOT proven / defects:
- (b) No over-match on normal completion. Across 53 local jobs there are 510 completed, 4 failed and 3 stopped notices, and each stopped notice pairs with a killed update. The completed case is tested (tests/test_monitor.py:458); "failed" is not, though the code matches only "stopped" (src/hands/monitor.py:199).
- By design it over-matches: a task the agent stops itself with TaskStop (fixture case B) is filed as a kill, so the playbook stops. This is documented; the stream cannot tell the cases apart.
- Real-log case A was a sub-agent killed with its Bash task just before the job's result. It also shows up as a second, `local_agent` kill with no command (0mtygi953 line 1410), which the fixture leaves out.
- Not observed: the harness killing a task on its own; the full daemon-to-playbook stop path; what happens once TASK_MEMORY=1024 is exceeded.
- Worktree /tmp/r8-u2 removed.

sha 4782a4a U3 — per-job scope or process group, and monitor.orphan_processes at job end; DESIGN §5, §24 (backlog 2)
1 unit/sections: Matches the brief and the §24 text. Scope mode wraps the command in `systemd-run --user --scope --quiet --unit hands-<project>-<job>`; group mode uses `start_new_session`. `--pids` comes from `runner.live_pids`, one event is filed, then the scope is stopped or the group gets SIGTERM, then SIGKILL. (a) The set is read at job end, not collected during the run. Claude's own pid is left out because it has already been reaped. The group is only signalled when it still has live members, and a group id cannot be reused while it has members. (d) The doctor `isolation` row is `ok` in both modes and says the group is weaker. (e) The commit body lists all 15 files it touches.
2 test-first: Red, then green. Reverting the 8 non-test files (keeping tests, fake_claude and conftest new) gave `278 errors`: import errors, plus the autouse conftest fixture failing because `detect_isolation` is missing, so this red proves little on its own. Restored: `422 passed` over runner/monitor/doctor/spool/playbook. The real proof of the kill was a mutation: making `_kill_group` a no-op and removing the last-resort killpg failed 3 tests (both double-fork tests and the cancelled-job orphan test) on `assert not process_live(pid)`. (c) So the product kills the orphan; test teardown does not.
3 check: `1323 passed in 84.12s (0:01:24)` / `== cli smoke ==` / `check: green` (exit 0, first run, clean tree)
4 design/forbidden files: DESIGN.md, meta/plan.md and meta/CHECKPOINT.md are not touched. Conforms; see the double-fork gap below.
NOT proven: (b) Tests never run scope mode, which production picks on any machine with a working user manager. conftest.py:110 forces group mode everywhere. Only the scope argv is tested, through a stand-in `systemd-run`; the stand-in `systemctl` prints nothing, so a scope sweep that finds processes, `systemctl --user stop`, and the scope branch of `live_pids` (runner.py:488) are untested. (c) The double fork in fake_claude.py:206 never calls setsid, so it stays in the group. That meets the brief's gate but not §24's claim that only the scope catches a double fork; a setsid escape is untested in either mode. Possible defect, runner.py:695: `_last_resort` sends killpg SIGKILL to `job.pid` without checking the group still has members. If run() raises after claude was reaped and the pid was reused as another job's group leader, that job would be killed. The window is tiny and there is no test for it. Nit: tests/test_runner.py:830 is mis-indented (ruff check does not catch it). Cleanup: the /tmp/r8-u3 worktree is removed and no `sleep 300` process was left.

sha 7183478 U4 — phone: ntfy command channel with nonce buttons and decided_by phone; DESIGN §8, §11, §13, §24 (H-015)
1 unit/sections: PASS. Secret compared with `hmac.compare_digest` and kept out of `repr`, logs, notifications, spool and doctor. Nonce is `secrets.token_urlsafe(32)`, in memory only, single-use, bound to one job, dropped on every `gate.decided` and on stop; a held job can only leave through a decision, since held has only queued/denied edges and cancel refuses it. Bad commands publish nothing. Buttons send exactly `approve|deny <job> <nonce>` to cmd_topic. pyproject untouched. Commit body lists all 15 files.
2 test-first: PASS. Product files reverted to 7183478^ and phone.py deleted: test_phone fails to collect (ImportError `http_stream`); config/doctor/gates show "17 failed, 152 passed". Restored: "198 passed" (4 files). Two mutants were caught: removing the pre-subscription time filter fails the before-subscription test; not spending the nonce fails 3 tests (single-use, laptop approve, laptop deny).
3 check: "1367 passed in 147.59s (0:02:27)" / "== cli smoke ==" / "check: green"
4 design/forbidden files: DESIGN.md, meta/plan.md and meta/CHECKPOINT.md not touched. (f) The cmd_topic-without-cmd_secret refusal is in config load, so doctor fails its config row (exit 1, tested) and handsd will not start; the phone row itself only says on/off (matches §24 "never as errors"). Three refusals were added beyond the brief: a secret containing a space, cmd_topic equal to ntfy_topic, and the same ntfy key in both [server] and [notify].
NOT proven: (d) The restart replay guard is first `since=<start unix secs>` plus ignoring messages timed before start (phone.py:143,189). It is tested only with fake timestamps (start−60 and start−1), not with a real restart facing an old cached `approve <job> <secret>`. A message stamped in the same second as start still passes (`<`, not `<=`). Real ntfy `since=` behaviour, clock skew and buttons on a real phone are all unproven. Low: the reconnect warning at phone.py:159 logs the full exception text, and httpx status errors include the URL, so cmd_topic can land in the daemon journal. Design-inherent, and stated in docs/INTEGRATION.md: every held notification on ntfy_topic contains the cmd_topic URL, so anyone reading ntfy_topic can find cmd_topic and read typed secrets still cached there. Not covered by tests: playbook `notify` rule, max_resumes and quiet-hours flush notifications; phone approve into a full queue. Both worktrees removed (/tmp/r8-u4 and the extra /tmp/r8-u4-tf/wt I used for the revert run).

sha 6fcd7d7 U5: notify, doctor's probe argv from OPS_FLAGS, `accepted()` int-only, notify refusal on the socket route; DESIGN §4, §5, §9, §11, §14 step 4, §19
1 unit/sections: PASS. SF3 as written is closed: the probe goes through `monitor.ops_argv`, which reads OPS_FLAGS at call time, and a test pins the probe argv. The `MONITOR_FLAGS` alias is gone from src/tests/docs; it only survives in historical meta/ (FINAL-REPORT-3.md, REVIEW-3.md). SF6 is closed by the review's own second option ("fix the double"): both `Posts` doubles return 200, and `bool` is excluded (`True` → not delivered, pinned in the table). SF7 is closed: a 403 now goes through the real socket with `cli.call`, and `_render` has a notify branch. The commit body lists all 7 files.
2 test-first: PASS. I reverted the 4 product files to 6fcd7d7^ and ran the 13 new test cases: 7 failed, one or more per item. SF3: the probe test. SF6: `accepted` for None, True, "200" and 200.0, plus the no-status publisher test. SF7: the socket test, where the base printed a raw JSON dump. The 6 that stayed green are the plain int rows (200/202/299/199/300/403), which the base already got right. After `git checkout 6fcd7d7 -- .` the tree was clean and all 13 passed.
3 check: `1380 passed in 144.28s (0:02:24)` / `== cli smoke ==` / `check: green`. Green on the first run; the tree was still clean afterwards.
4 design/forbidden files: PASS. The commit does not touch DESIGN.md, meta/plan.md or meta/CHECKPOINT.md. §9 (the CLI and the API are the same surface) and §19 (a non-2xx fails) are now true on the socket route as well.
NOT proven:
- SF7 is only partly closed through `main()`. I changed `src/hands/cli.py:734` (`return exit_code(command, result)`) to `return 0` and tests/test_wake.py stayed fully green, so main's generic-route wiring is unpinned. The commit admits this, and today the route can't be reached for notify.
- No test renames OPS_FLAGS and checks the monitor's own argv (`monitor.py:716`); the commit admits this too.
- Cosmetic only: `doctor.py` now has 3 blank lines where the alias was, and `ops_argv` has a single blank line before `DEFAULT_POLL_S` (`monitor.py:~96`). Ruff doesn't flag either.
- I did not rerun the commit's mutation claim (making `Api.notify` raise `ApiError` on a refusal).
- I could not recover the exact pytest summary line for the red run; my `tail`/`grep` dropped it. The 7/13 count comes from the listed FAILED cases.

sha a93e3a7 U6 — `hands who` and `handswho`; DESIGN §4, §11, §24 (backlog item 6)
1 unit/sections: PASS. (a) Every one of the prototype's 7 self-test cases has a ported test with the same assertions. Case 2 builds a new file instead of appending to the old one, but the lines the check reads are identical. Cases 1, 3 and 4 add extra assertions. (b) Deliberate changes, all listed in the commit body: one project instead of every ~/.hands config; `(your session)` now matches a cwd at or under a role directory, not only an exact match; driver = a directory under ~/hands-driver/<name>, not any cwd containing "hands-driver"; transcript folder names turn every non-alphanumeric into `-`; sha256 instead of sha1; heartbeat and flags dropped; a command pushes at once. One quiet fix: the prototype kept only the last role's cwd. Which sessions get fingerprinted is unchanged. (c) The `who` socket method only reads. It returns job summaries (first prompt line ≤120 chars), gate reason, pipeline and inbox ids/kinds. No cmd_secret; nonces live only in phone.py's memory, never in job records. (d) The client reads over the socket and the daemon builds the answer in its own process. Nothing shells out to `hands`, so the brief and §24 agree in practice. (e) The service is off unless enabled: `enable --now` is only a step in the file's header, and no script enables it. (f) `handswho = "hands.who:main"`, still no dependency beyond httpx, prototype and its ruff exclude both removed. (g) The commit body lists all 14 files; `--name-status` shows exactly 14.
2 test-first: PASS. I reverted all product files, restored the prototype and deleted who.py and handswho.service, keeping the new tests. `pytest tests/test_who.py`: import error at collection (all 35 tests red). `tests/test_daemon.py` + `tests/test_docs.py`: 4 failed, 129 passed (the §4 help list, API method names, the handswho unit test, the doc sweep). After `git checkout a93e3a7 -- .` and removing the prototype again, the tree was clean and the three files gave 168 passed.
3 check: `1416 passed in 98.79s (0:01:38)` / `== cli smoke ==` / `check: green` (first run, clean tree)
4 design/forbidden files: PASS. §4 already lists `who [--daemon]` (DESIGN.md:180). The commit touches none of DESIGN.md, meta/plan.md or meta/CHECKPOINT.md.
NOT proven: (1) Drift I confirmed with a probe: a `status`/`who`/`check`/`?` command runs a full scan, and that scan counts toward the two-scan debounce (src/hands/who.py:639 → :609). One timed scan plus a command seconds later settles a session state. The prototype only set a flag for the next timed scan. It's minor because the requested push shows the picture anyway. (2) Pushes you ask for skip the 60 s gap, and who_cmd_topic has no secret, so anyone who knows that topic can trigger unlimited pushes (who.py:612). (3) The pushed text includes the human's last transcript prompt (70 chars) and command lines (60 chars), which can carry tokens. The prototype did the same and docs/INTEGRATION.md warns about it, but it strains §24's "nothing but commands and status lines". (4) Untested, as the commit itself says: live /proc, real transcripts, real ntfy, the reconnect backoff, the systemd unit.

sha c41473c U7 — Playbook and docs (backlog 4); DESIGN §10, §11, §13, §24
1 unit/sections: PASS. `PLAYBOOK.toml` gains both `stop` rules and has no `quiet_hours`. doctor gains `notifications` and `who` rows, and README and both docs are updated. H-016 is correct: §10's example ends with `on = "monitor.tripwire"` / `then = "stop"`, has neither new rule, and its copies are pinned byte for byte. Filing a finding follows CLAUDE.md. quiet_hours is still read in `playbook.py:378` and `notify.py:348`, which §11 allows ("exists but no playbook of this project sets it"). No doc tells anyone to set it.
2 test-first: PASS. With the 5 product files set back to c41473c^, all 8 new tests fail (1 playbook, 3 docs, 4 doctor). With the commit restored, the 3 test files pass: 183 passed.
3 check: `1424 passed in 118.56s (0:01:58)` / `== cli smoke ==` / `check: green` (one run, clean tree)
4 design/forbidden files: PASS. The commit does not touch DESIGN.md, meta/plan.md or meta/CHECKPOINT.md. The body's file list matches the 9 files in `--stat`. Doc claims I checked against src hold: what gets notified (notify.py:3), `status` answered on ntfy_topic (phone.py:28), `decided_by: phone` (api.py:582), who's 4 command words (who.py:80), leftover processes listed then killed (runner.py:30), handswho.service optional.
NOT proven: acceptance, all pass under a temp HOME: `hands --help` lists `who`; `handswho --help` exits 0; doctor with only ntfy_topic shows notifications on, phone off, who off, 0 failed, exit 0; no `quiet_hours` in `PLAYBOOK.toml`; `meta/prototypes` absent.
"Never as errors" holds only in part. The two new rows are always `ok`, but the `phone` row still shows `warn` when cmd_topic is set without ntfy_topic (doctor.py `_phone_check`, U4; still exit 0). A cmd_topic without cmd_secret fails the `config` row and exits 1, which §24 requires and INTEGRATION.md states.
Stale wording the sweep missed: doctor.py:550 still prints "Quiet hours delay notifications and never actions… so run this outside them", which conflicts with §11 "notifications are never delayed". It predates U7 (56bef531) and is minor.
A who_cmd_topic without who_topic just shows "who view off" and does not mention the unused key.
Not checked: a real ntfy delivery, and that handswho actually runs.
