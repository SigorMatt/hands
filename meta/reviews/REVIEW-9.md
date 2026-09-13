# REVIEW-9 — cold review of hands mission 9

VERDICT: review mission 9 blockers=0 should-fix=4

Base `65baa2b` (`review: mission 8`, the last `review:` commit on origin/main).
Range `65baa2b..114f99d`: 12 commits. They are the architect's kit `0ead876`,
six builder unit commits (U0 `1c17d84`, U1 `4da83f8`, U2 `7992c4d`, U3
`fd6ecbe`, U4 `edb8e84`, U5 `f96c88b`) and five `meta:` bookkeeping commits
(`f0368f0`, `39a2b0a`, `48bcd92`, `30d4440`, `114f99d`). One sub-agent reviewed
each unit commit, in a detached worktree at that commit. Read beforehand: DESIGN
v3.8 §25 (with §6, §8, §10, §11), `meta/BUILDER-9-PROMPT.md`,
`meta/FINAL-REPORT-9.md`, `meta/findings/FINDINGS.md` (H-014, H-016, H-017).

## Blockers

None. `./scripts/check` is green at every unit commit (1424, 1428, 1432, 1439,
1430, 1435 passed). At the pushed tip `114f99d`, the reviewer ran it and got
`1435 passed in 78.83s` / `== cli smoke ==` / `check: green`. Every unit's new
or changed tests go red when its product change is reverted, or, for U2's SF1
(which has no product change), when the brief's mutation is applied. No unit
commit touches `DESIGN.md`. Only U0, the builder's `plan:` commit that the brief
assigns them to, touches `meta/plan.md` and `meta/CHECKPOINT.md`. The four
acceptance lines hold at the tip:
- check is green;
- every commit body names every file;
- `grep -n prototypes pyproject.toml` returns nothing (exit 1);
- `test_a_dirty_playbook_is_refused_at_job_start` runs through the real daemon.

The disks contradicted no claim in FINAL-REPORT-9's §1, §2 or §4. Should-fix 1
qualifies the review-items table's `closed` for REVIEW-8 should-fix 3.

## Should-fix

1. **REVIEW-8 should-fix 3 is implemented as asked, but the check cannot
   prevent the kill it was filed for (U2 `7992c4d`, `src/hands/runner.py:694-698`).**
   - **Why the check changes nothing.** On Linux, a pid number is not handed
     out again while any process still has it as its process-group id. So
     `group_pids(job.pid)` (`monitor.py:355`) is non-empty exactly when a group
     with that id exists, which is exactly when `os.killpg` would succeed.
   - **Both outcomes are the same as before U2.** With an empty group, `killpg`
     used to fail with ESRCH, and the existing `contextlib.suppress(OSError)`
     already swallowed that. With a non-empty group whose id was reused by a new
     session leader after claude was reaped, U2's code still sends SIGKILL.
   - **The new comment gets this backwards.** "An empty group's id may already
     be another session leader's" cannot happen: if another session leader
     holds that id, the group is not empty.
   - **What the report claims.** FINAL-REPORT-9's review-items table marks the
     item `closed`. §3 item 4 admits only that the race was not reproduced and
     that the two steps are not atomic.
   - **Where the error started.** REVIEW-8's suggested remedy was the flawed
     part; the builder followed the brief exactly.
   - **What to do.** Either keep the pid reserved until the sweep (for example,
     sweep the group before reaping claude), or tie the kill to the original
     group (for example, the leader's start time). Otherwise, mark the item
     partly closed and correct the comment.
2. **`docs/INTEGRATION.md:121-123` (added by U1 `4da83f8`) says a job is `done`
   only with "a final `result` event of subtype `success`". The runner
   disagrees.** `runner.py:895-897` counts any `error_*` subtype as a final
   result and fails it only when `is_error` is true. So a result with subtype
   `error_max_turns`, `is_error` false, `num_turns` and exit 0 is `done`.
   - §6 says a result of subtype `error` is `failed`/`error_result`.
   - Every error-subtype test (`tests/test_runner.py:438-447`) uses
     `FAKE:error`, which always sets `is_error: true`
     (`tests/fake_claude.py:39`), so this combination is untested.
   - The code dates from mission 7a; U1's doc sentence and its claim to pin §6
     are new.
   - The reviewer established this by reading the code, not by running it.
   - Either fail on the subtype as well as `is_error`, or make the doc and a test
     say what the code does.
3. **U3's git check inherits the daemon's environment and compares raw bytes
   (`fd6ecbe`, `src/hands/playbook.py:379-403`).**
   - **It can fail open.** `subprocess.run(["git", "show", …])` passes
     `GIT_DIR` and `GIT_WORK_TREE` through. If handsd runs with `GIT_DIR`
     pointing at another repository whose HEAD has an identical file, an
     untracked playbook loads. The U3 sub-agent reproduced this.
   - **It can fail closed.** A clean playbook is refused as dirty in two cases,
     both reproduced by the U3 sub-agent: when it is committed as a symlink, and
     when it has CRLF line endings under `core.autocrlf=true` (in both,
     `git status` shows clean).
   - **The report.** FINAL-REPORT-9 §3 item 5 lists autocrlf and filters as
     untested. It does not list the `GIT_DIR` bypass or the symlink case.
   - **What to do.** Clear `GIT_*` from the child environment. Decide, and file
     if needed, whether the comparison is against the blob or against what
     `git status` considers clean.
4. **H-017 misquotes DESIGN v3.7 (U0 `1c17d84`, `meta/findings/FINDINGS.md:900-901`).**
   It says v3.7 §6 listed `gate` as `{reason, decided_by: cli|driver|button,
   decided_at, quote?}`. v3.7 (`git show 0ead876^:DESIGN.md`, line 235) has
   `{reason, decided_by: cli|driver|button, decided_at}`; `quote?` first appears
   in v3.8. Append a dated correction line (§20: never rewrite).

## Notes

- **Kit `0ead876`** is the architect's, not a unit. It is the only commit in the
  range that touches `DESIGN.md` (v3.8), and it also replaces `meta/BACKLOG.md`
  and adds `meta/BUILDER-9-PROMPT.md`. It was red, as FINAL-REPORT-9 says: the
  U0 reviewer confirmed that
  `tests/test_playbook.py::test_the_fixture_is_section_10s_example_verbatim`
  fails at `0ead876` (`test_playbook.py:185`). U0 copied §10's example into the
  fixture and the doc to make it green. That goes beyond the brief, and it is
  recorded.
- **File lists.** A per-commit `git show --name-only` over the range matches
  each unit commit's body. Each `meta:` commit touches only `meta/plan.md`,
  `meta/CHECKPOINT.md` and `meta/journal.md`, plus `meta/FINAL-REPORT-9.md` in
  `114f99d`.
- **U4's gate grep, as literally written, is not met, and that is not counted
  as a blocker.** At the tip, `git grep -n quiet_hours -- src tests docs driver`
  returns the refusal (`src/hands/playbook.py:120`) and its test
  (`tests/test_playbook.py:413-424`), plus four other hits:
  - `tests/fixtures/playbook_example.toml:7` and `docs/PLAYBOOK.md:234`, which
    carry §10's own comment "no quiet_hours: …", pinned byte for byte to the
    DESIGN text the kit introduced;
  - `docs/PLAYBOOK.md:103`, the refusal sentence;
  - `docs/ARCHITECT-INSTRUCTION.md:58`, "Playbooks never set `quiet_hours`".

  All four state that the feature is gone. The first two cannot be removed
  without breaking a design pin. A case-insensitive sweep found no surviving
  delay path and no doc that still describes quiet hours. The gap is disclosed
  in FINAL-REPORT-9 §3 item 7 and §5 item 4. The gate needs rewording, not the
  code.
- **Doc pin (U0).** Reverting only `docs/PLAYBOOK.md` at `1c17d84` leaves every
  test green, so the doc's verbatim block is untested. A one-off script found it
  byte-identical to §10's example. Disclosed in §3 item 8.
- **U3 probes that go beyond the report's NOT PROVEN.** The U3 reviewer checked
  these in scratch repositories:
  - `meta/PLAYBOOK.toml`, a `cwd` below the repository root and a
    `sub/../PLAYBOOK.toml` path all load when clean and are refused when dirty;
  - an edit that keeps the same size and a restored mtime is still refused,
    because the playbook is loaded again at every job start with no cache;
  - staged-only, no-commit, outside-the-repository, untracked-symlink and
    git-missing cases are all refused.

  Confirmed as reported: the synchronous `git show` can block the event loop for
  up to 10 s; a deleted but committed playbook loads as "no playbook"; the
  timeout path is untested.
- **U5.** The re-sent `job.held` has the same title and payload keys in the same
  order as `Api.send`. It writes no duplicate inbox event and does not re-run
  the playbook, and the old nonce is still refused.
  - A gated send that arrives between the socket bind (`daemon.py:185`) and
    `_renotify_held()` (`daemon.py:207`) gets its notification twice with the
    same nonce. This is harmless and untested.
  - With `cmd_topic` set but no `ntfy_topic`, a nonce is minted that is never
    published.
  - ntfy being down at restart leaves only an inbox `notify` record (§3 item 3).
- **Other log lines (SF4's neighbourhood).** The §25 bullet covers the phone
  reconnect warning only, and that is closed. Paths this mission did not change
  (the report says they were not audited):
  - `who.py:682` logs the `who_cmd_topic` URL in its reconnect warning (that
    topic is secret-less by §25);
  - `who.py:627` and `notify.py:369`/`380` log publish-failure exception text
    (`380` also writes it to the inbox); the text carries a topic URL only if
    the exception does;
  - `notify --test` shows the `ntfy_topic` URL on purpose.
- **`hands.gates.DECIDED_BY`** is read only by `tests/test_docs.py`; no product
  code uses it. Every `decided_by` still goes through `check_decider`, which
  refuses the unavailable `button` row. §8 still says `decided_by: button`
  (FINAL-REPORT-9 §5 item 3).
- **U1.** A grep of src, docs, driver, README, CLAUDE.md and PLAYBOOK.toml
  found no leftover "success wins" wording.
- **U4.** No test covers doctor's playbook row for a playbook that sets
  `quiet_hours`; it goes through the generic `PlaybookError` path
  (`doctor.py:409-410`). The no-topic and publish-order tests survive the
  `_route` → `_has_topic` rename (`tests/test_wake.py:290`, `:342`, `:364`).
- **Nit.** After U0, H-016 has both a plain `Status:` line and a bold status
  paragraph (`FINDINGS.md:861`, `:863` at `1c17d84`).
- **Method.** To revert product changes, the sub-agents used
  `git checkout <sha>^ -- <files>`, ran the tests, then ran
  `git checkout <sha> -- .` and confirmed a clean tree. They did not use
  `git stash`, because the six ran in parallel worktrees and the stash is
  shared across worktrees. Every worktree was removed afterwards.
- **FINAL-REPORT-9 §3 (NOT PROVEN) against the sub-agents.** It agrees with what
  they found, and it is honest about U2's narrow closures, U3's untested git
  edges, U4's gate and U0's doc pin. It does not list:
  - the SF3 check changes no outcome (should-fix 1);
  - the `error_*`/`is_error` false case and U1's doc claim (should-fix 2);
  - the `GIT_DIR` bypass and the symlink false refusal (should-fix 3);
  - H-017's misquote (should-fix 4);
  - U5's startup-window duplicate (Notes).

## Per-commit verdicts

### 1c17d84 (U0)

Review of 1c17d84 (mission 9 U0): the commit passes all four points, with two small wording defects in FINDINGS.md.

1. **Scope: PASS.** The body names mission 9 U0 and claims DESIGN v3.8 §25 (whole), §6 (job record and rules) and §10 (Events list and Example). `git show --stat` lists exactly the 6 files the body names: docs/PLAYBOOK.md, meta/CHECKPOINT.md, meta/findings/FINDINGS.md, meta/plan.md, tests/fixtures/playbook_example.toml and tests/test_playbook.py. DESIGN.md and pyproject.toml are untouched.
2. **Test-first: PASS, with one gap.**
   - Reverting only the fixture turns 2 tests red: `test_the_fixture_is_section_10s_example_verbatim` and `test_the_example_parses_into_the_rules_of_section_10`. Reverting the fixture and the doc together gives the same 2.
   - Reverting only docs/PLAYBOOK.md leaves test_docs and test_playbook fully green, so no test covers the doc block change. This matches the commit body and the final report, which both say the doc pin only checks that each line appears somewhere in the page.
   - Restored with `git checkout 1c17d84 -- .`; `git status` was clean.
   - The "kit was red" claim holds: in a separate worktree at 0ead876, `FAILED tests/test_playbook.py::test_the_fixture_is_section_10s_example_verbatim` (AssertionError at test_playbook.py:185).
3. **Gate: PASS.** `./scripts/check` at 1c17d84 ended with `1424 passed in 115.96s (0:01:55)`, then `== cli smoke ==`, then `check: green` (exit 0). This matches the body's pass count.
4. **Design conformance: PASS, with two defects.**
   - A one-off script shows the fixture is §10's example byte for byte (the test's extraction plus a trailing newline). The docs/PLAYBOOK.md verbatim block matches it too, with an empty diff.
   - The H-014 and H-016 quotes of DESIGN v3.8 §6 and §25 match the text exactly.
   - H-017's code claims hold. `FAILURE_REASONS` in runner.py:193-199 has the six names; `spawn_error` is at runner.py:571; `decide_from_phone` passes `"phone"` at api.py:589; `button` is in gates.py `DECIDERS`. The runner still returns `done` when a success result also has the termination line (runner.py:897), as H-014 says.
   - `grep -n prototypes pyproject.toml` is empty at 0ead876^, at 0ead876 and at 1c17d84.
   - Defect: H-017 misquotes v3.7 at FINDINGS.md:885. It gives the gate as `{reason, decided_by: cli|driver|button, decided_at, quote?}`, but v3.7 (0ead876^ DESIGN.md:235) says `{reason, decided_by: cli|driver|button, decided_at}`, without `quote?`. The `quote?` field only arrived in v3.8.
   - Minor: H-016 now carries two status lines, a plain one at FINDINGS.md:861 and a bold paragraph at :863.
   - Cosmetic: the "Read it as a sentence" line in docs/PLAYBOOK.md now runs past the page's usual wrap width.

Not proven: no test covers the verbatim block in docs/PLAYBOOK.md (the builder admits this). I did not review what plan.md and CHECKPOINT.md say. Both worktrees are removed; nothing in /home/msi/git/hands was edited.

### 4da83f8 (U1)

Review of 4da83f8 (mission 9 U1: termination precedence and the §6 vocabularies). I changed nothing in the repo and the worktree is removed.

1. **Scope: PASS.** The commit claims DESIGN §6, §25 and §2, and findings H-014 and H-017. `git show --stat` lists the same 8 files as the commit message. DESIGN.md, meta/plan.md and meta/CHECKPOINT.md are untouched.
2. **Tests fail without the change: PASS.** With runner.py, gates.py, INTEGRATION.md and FINDINGS.md reverted to the parent, 5 of 336 tests failed: the runner's H-014 shape test, `test_show_prints_the_failure_line_of_a_failed_job[harness_terminated]`, the playbook `builder.failed → resume` test, and both new test_docs tests. After restoring, `git status` was clean.
3. **`./scripts/check`: PASS.** Last lines: `1428 passed in 101.90s (0:01:41)` / `== cli smoke ==` / `check: green`.
4. **Match with §6/§25: PASS, with notes.**
   - `_final_state` (src/hands/runner.py:874-887) decides cancel → `killed`, then limit → `limited`. `_failure_reason` (:891) then returns `harness_terminated` whenever the line is present, even with a `success` result.
   - The daemon test really goes through `hands show`.
   - A grep of src, docs, driver, README, CLAUDE.md and PLAYBOOK.toml found no leftover "success wins" or "v3.7 §6" wording.
   - `failure_reason` is only set by the runner, always from `FAILURE_REASONS`. `decided_by` is only set through `check_decider`, which refuses `button` because its row is unavailable.
   - `DECIDED_BY` is not used by any product code: it is exported and only read by tests/test_docs.py. The commit admits this, so it is a note, not a defect.

**Not proven, or small gaps:**
- (a) docs/INTEGRATION.md now says `done` needs subtype `success`, but the code disagrees. `_is_final_subtype` (runner.py:237-242) still accepts `error_*`, so an `error_max_turns` result with `is_error` false, turns and exit 0 comes out `done`. This comes from reading the code; I didn't run it, and no test covers it.
- (b) As the commit says, no real harness termination and no real claude binary were tested.
- (c) §8 still says `decided_by: button`, which §6's list leaves out. That wording is in the design, not a code defect.

### 7992c4d (U2)

Verdict on 7992c4d (mission 9 U2): points 1–3 pass. Point 4 passes for the files and SF4, but SF3's fix doesn't stop the pid-reuse kill that REVIEW-8 described.

1. **Unit and sections: PASS.** The body names U2, REVIEW-8 should-fix 1, 3, 4 and DESIGN §25 (plus §4/§9, §5/§24, §11/§24). Its file list matches `git show --stat` exactly: runner.py, phone.py and three test files, with no cli.py change.
2. **Test-first: PASS.** With runner.py and phone.py taken from the parent, all three new test cases fail. Both SF3 cases fail on `assert [] == [424242]`. The SF4 test fails with the warning `HTTPStatusError: Client error '403 Forbidden' for url 'https://ntfy.example/hands-cmd-test/json?since=123'`. For SF1, changing cli.py:753 to `return 0` makes `test_main_returns_the_exit_code_of_the_socket_answer` fail (`assert 0 == 7`); I only ran tests/test_wake.py, since there is no test_cli file. After restoring, the tree was clean.
3. **Check: PASS**, green on the first run. The final lines were `1432 passed in 131.66s (0:02:11)` / `== cli smoke ==` / `check: green`, exit 0.
4. **Design conformance:**
   - **Forbidden files:** DESIGN.md, meta/plan.md and meta/CHECKPOINT.md are untouched.
   - **SF1:** the test is meaningful. `tests/harness.py:57` calls the real `main()` against a real daemon over the socket. The spy only proves `exit_code` is wired in; no real command on that route returns non-zero, as the body admits.
   - **SF4:** closes the §25 bullet. The phone reconnect warning is now built only from the exception type and status (`phone.py:289-298`).
   - **Other paths that still log exception text** (outside the bullet, older than this commit, not audited by the builder):
     - `who.py:682` puts the `who_cmd_topic` URL into its reconnect warning. The design calls that topic secret-less, so this is low severity.
     - `who.py:627` and `notify.py:369`→`380` (which also writes it to the inbox) log exception text on publish failure. That text could carry the `ntfy_topic` URL, but only if the exception includes it, because `http_post` returns non-2xx codes instead of raising.
     - `notify.py:239/242/244` show the `ntfy_topic` URL on purpose in `notify --test`.
   - **Defect, SF3 (`runner.py:694`):** the membership check can't tell claude's group from a reused one. `group_pids` (`monitor.py:355`) matches any live process with that group id. On Linux a pid isn't reused while a group with that id still has members. So a non-empty result is either the original group (safe to kill) or a new session leader that took the pid, which is still killed. An empty result would only have made `killpg` fail harmlessly. Checking before killing also leaves a gap between the read and the kill. The body admits both steps remain but claims the fix addresses the reuse case; closing it would need a pidfd or the job's own start time.
   - **Scope mode:** no matching problem. `systemctl stop` targets a unit name built from the job id (`runner.py:256`), not a reusable pid.
   - **Not proven:** `_last_resort` is only called directly, never through `run()`'s exception path; scope mode has no test; SF4 isn't tested against a real ntfy refusal.

Worktree /tmp/r9-u2 is removed and the main checkout is clean.

### fd6ecbe (U3)

fd6ecbe (mission 9 U3, "Playbook must match the committed file"; DESIGN §10 first paragraph plus "Stop -> resume cycle", §13 `[playbook]` path, §25). Verdict: **PASS** on all points, with two small defects and a few gaps listed below.

1. **Scope: PASS.** `git show --stat` matches the body's list exactly: 7 files, +304/-16. DESIGN.md, meta/plan.md and meta/CHECKPOINT.md are untouched.
2. **Test-first: PASS.** With src and docs reverted to fd6ecbe^, test_playbook plus test_doctor gave "8 failed, 130 passed". The 8 failures are all new tests, including the daemon job-start test. Restored, they gave "138 passed", and `git status` was clean.
3. **Gate: PASS.** `./scripts/check` at fd6ecbe ended with "1439 passed in 121.58s (0:02:01)", "== cli smoke ==", "check: green".
4. **Design conformance: PASS.**
   - **(a) Load at job start:** there is no cache. daemon.py:419 calls `on_job_start` for every job, and that calls `_load()` every time (playbook.py:691-703). A dirty edit with the same size and a restored mtime was still refused.
   - **(b) Path resolution:** checked in scratch repos, and it works. `meta/PLAYBOOK.toml`, a cwd below the repo root (spec `HEAD:./meta/PLAYBOOK.toml`) and `sub/../PLAYBOOK.toml` all load when clean and are refused when dirty.
   - **(c) sha256 on fired jobs:** still stamped (playbook.py:882/937). It equals the raw working-file sha, which the check has already made equal to the committed one.
   - **(d) Daemon path:** `test_a_dirty_playbook_is_refused_at_job_start` goes through the real daemon (send, wait, stop reason, one inbox stop event, one job).
   - **(e) Untracked still loading:** refused in every case I tried: untracked, staged but not committed, no commits, not a repo, playbook outside the repo, untracked symlink, and git missing from PATH ("committed sha256 unknown").

**Defects:**
- **`GIT_DIR` bypass** (playbook.py:381, `subprocess.run` inherits the environment): if the daemon runs with `GIT_DIR` pointing at another repo that has an identical committed file, an untracked playbook loads. Reproduced. Clearing `GIT_DIR`/`GIT_WORK_TREE` would close it.
- **False refusals** (playbook.py:403, raw bytes compared with the HEAD blob):
  - a CRLF file under `core.autocrlf=true` is refused as dirty while `git status` is clean;
  - a committed symlink is also refused as dirty.

**Not proven:** the git timeout path is untested. The synchronous `subprocess.run` inside async `_load` can block the event loop for up to 10 s. A playbook deleted from disk but still committed loads as "no playbook" (confirmed), which the report already lists as a known gap. The `GIT_DIR` bypass is not in the report's NOT PROVEN list.

Cleanup: the worktree at /tmp/r9-u3 and my scratch dirs are removed. /tmp/r9-u1 belongs to another reviewer and was left alone.

### edb8e84 (U4)

Commit edb8e84 (mission 9, unit U4): **PASS**, with one open item about the gate wording and nothing wrong in the code.

1. **Unit and file list: PASS.** The body names U4 and DESIGN §11, §10, §13 and §25. `git show --stat` lists the same 11 files as the body. DESIGN.md, meta/plan.md and meta/CHECKPOINT.md were not touched.
2. **Test-first: PASS.** With the non-test files put back to edb8e84^, the new test `test_a_committed_playbook_that_sets_quiet_hours_is_refused_at_load_and_stops` fails with `Failed: DID NOT RAISE PlaybookError`. It passes once restored, and `git status` came back clean. The removed test code is 10 tests, all about quiet hours: the window test (6 cases), unreadable window, delay to window end, shared flush, and `notify --test` not delayed. With 1 added, 1439 → 1430 checks out. Other coverage is still there:
   - The no-topic path after the rename to `_has_topic`: `test_with_no_topic_nothing_is_published` (tests/test_wake.py:290).
   - Publish order: tests/test_wake.py:342 and :364.
   - The renamed repo-playbook test still checks the detector `stop` rules; it only lost its quiet_hours asserts.
3. **`./scripts/check`: PASS.** Last lines: `1430 passed in 133.41s (0:02:13)` / `== cli smoke ==` / `check: green`.
4. **Design conformance: PASS.**
   - **Delay:** notify.py has no queue, flush, clock or delayed sleep left; its only sleep is `asyncio.sleep(0)` in the drain loop (:325). daemon.py's sleeps are the startup `sleep(0)` (:225) and the heartbeat (:570), neither of which holds a notification.
   - **Refusal:** the daemon runs the same `PlaybookEngine`, whose load-refusal path (playbook.py:1123-1127) the new test drives. It checks paused, the stop reason carrying both halves of the message, a single `stop` event, and that a notification went out.
   - **Probes:** the playbook refuses `[limits] quiet_hours` by name, even when it isn't a string. At the top level or in a `[[rule]]` it gets the generic unknown-key refusal. The config (`parse_config`) refuses `quiet_hours` in `[limits]`, `[notify]` and at the top level.
   - **Case-insensitive grep:** beyond the refusal (src/hands/playbook.py:120) and its test (tests/test_playbook.py:413-435), the only hits naming the feature are:
     - DESIGN §10's comment copied verbatim in tests/fixtures/playbook_example.toml:7 and docs/PLAYBOOK.md:233.
     - The refusal sentence at docs/PLAYBOOK.md:102.
     - Rule 11 at docs/ARCHITECT-INSTRUCTION.md:58.

     All four say the feature is gone or refused. Every other hit is unrelated: "quietly", `kill_quietly`, `--quiet`. driver/, README.md and PLAYBOOK.toml have none, and no doc still says quiet hours exist.

Not proven or open:
- The gate grep is not met word for word (4 extra hits above). They look justified: the §10 copy is pinned by a test and the others state the refusal. Whether that satisfies the brief is your call.
- No test checks that doctor's playbook row shows this refusal; it goes through the generic `PlaybookError` path at doctor.py:409-410.
- The daemon-level stop is proven only through the engine, and nothing shows a notification is never delayed except that the delaying code is gone. The commit body says both of these itself.

The review worktree is removed and the other reviewers' worktrees are untouched.

### f96c88b (U5)

**f96c88b** (mission 9 U5): **PASS**. Nothing is blocking; there is one low-severity window and a few things the tests don't cover.

1. **Scope: PASS.** The body names U5 and cites §25, §24, §8, §11, §5 and §10. `git show --stat` lists the same 8 files as the body (3 src, 2 docs, 3 tests). DESIGN.md, `meta/plan.md` and `meta/CHECKPOINT.md` are untouched.
2. **Test-first: PASS.** With the src and docs files reverted, the three test files gave `8 failed, 124 passed`. That is 7 product failures (`test_the_nonce_dies_with_the_daemon`, the restart re-send test, the cause test, 4 daemon-path kill cases) plus the docs pin, which matches the "7 + docs pin" claim. The two negative restart tests pass either way, which is expected. After `git checkout f96c88b -- .` the tree was clean and all passed.
3. **`./scripts/check`: PASS.** Final lines: `1435 passed in 111.79s (0:01:51)` / `== cli smoke ==` / `check: green`.
4. **Design conformance: PASS**, point by point:
   - **(a) Same notification:** it uses the same title (`NOTIFY_KINDS["job.held"]`) and the same payload keys in the same order, so the message text is identical. Tags are always `robot`, and `http_post` never sets priority or click, so those can't differ. Only `send` gates live on a job record (`GATE_KINDS=("send","cancel")`), so `gate` is always `"send"`, as in `Api.send`. `notifier.notify` is called directly, so no duplicate `job.held` inbox event is written and the playbook's `on_event` isn't re-run. A failed delivery inboxes a `notify` event without the buttons, same as the original path.
   - **(b) Ordering:** `phone.start()` sets the `since` floor before `_renotify_held` runs, and publishing happens later in a task, so a button press can't be missed. A pre-restart message is dropped by the floor, and an old nonce is refused regardless.
   - **(c) Never-sent notification:** a job whose original notification never went out is still covered. The re-send loops over every `held` record in the spool, whatever happened to the first send.
   - **(d) §24 not weakened:** the old nonce is still refused (asserted in both changed tests), the typed secret still works, and a new nonce only decides its own job (a deny on job two with job one's nonce is refused).
   - **(e) `cause`:** the `task_killed` payload carries `cause="unknown"` (`monitor.py:659`), and PLAYBOOK.md and INTEGRATION.md say so and why. There is no formal payload schema to be inconsistent with.

**Defect, low severity:** the socket is bound before `await self.limits.reschedule_pending()` (`daemon.py:~199`), and `_renotify_held()` runs later, at `daemon.py:207`. A gated send that arrives in that gap gets its nonce and notification from `_on_event`. `_renotify_held` then reuses the same nonce (`phone.py:118`) and publishes a second, identical notification. It's a duplicate, not a security problem, and it is untested.

**Not proven:** ntfy being down at restart (the re-send just becomes a `notify` inbox event, and there is no retry); a phone decision racing the re-send; and a config with `cmd_topic` set but no `ntfy_topic`, where a nonce is minted but never published (harmless).

The worktree `/tmp/r9-u5` has been removed; nothing in `/home/msi/git/hands` was edited.
