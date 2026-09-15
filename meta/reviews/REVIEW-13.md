# REVIEW-13 — cold review of hands mission 13

VERDICT: review mission 13 blockers=4 should-fix=8

Base `093d1c9` (`review: mission 12`, the last `review:` commit on origin/main).
Tip `bae5639`. Unit commits reviewed, one sub-agent each, in a worktree at the
commit: b79d908 (U0), eccc3a1 (U1), ea7f1bc (U2), 126d4ff (U3), 38022f2 (U4),
9ca89cf (U5), 8f79f98 (U6), 0a14085 (U7). Not dispatched: 723dbeb (the
architect's kit: DESIGN.md, KIT.md, meta/ only) and the `meta:` commits c2b78c4,
3ece0a1, 62dbcac, 5efada4, 7797d7e, b3acb94, bae5639 (each touches only
meta/CHECKPOINT.md, meta/journal.md, meta/plan.md; bae5639 adds
meta/FINAL-REPORT-13.md). The reviewer re-ran every blocker's probe at the tip.

## Blockers

1. **The guard still has a working bypass: a heredoc desynchronises its quote
   state, in both modes (U1 `eccc3a1`; §12, §28, §29).**
   - **Why.** `_scan` in `driver/hooks/bash_guard.py` has no heredoc state, so
     a `'` inside a heredoc body opens a quote that bash never sees. Everything
     up to the next `'` is then one quoted word to the guard, and bash runs it.
   - **Reproduced at the tip,** normal mode, with the hook JSON on stdin:
     ```
     CMD=$'ls <<A\nls \'\nA\ntouch /tmp/rev13-me-pwned\nls "\'" <<\'true\'\n"\ntrue'
     hook normal exit=0 ; bash -c "$CMD" -> /tmp/rev13-me-pwned exists
     ```
   - **Role mode** (`HANDS_ROLE=driver`, `HANDS_CLONE` set): the same shape
     hides `hands go` and `hands send --role builder --context clear m`. The
     hook exits 0, and bash runs both.
   - **Not new.** The parent hook allows it too.
   - **What the report says.** FINAL-REPORT-13 §3.1 says only that "Heredoc …
     parsing [is] not modelled". The Review items table closes REVIEW-11
     blocker 1 ("guard bypass") as "closed (the comment hole)". §29 ends: "The
     driver role is enabled only after a review finds no guard hole." This
     review found one.

2. **`kit check` does not judge the bare relative names that §29 names, and a
   test pins `path:line` as not a path (U3 `126d4ff`; §29 Kit transport;
   REVIEW-12 should-fix 1).**
   - **§29's text:** "judges every file path a prompt names, including bare
     relative names and names inside parentheses".
   - **At the tip:**
     ```
     kit.named_paths('read NOTES', [], Path('.'))              -> []
     kit.named_paths('run Makefile', [], Path('.'))            -> []
     kit.named_paths('see meta/MISSING.md:12', [], Path('.'))  -> []
     ```
   - **`path:line` is pinned.** `tests/test_kit.py:970` asserts
     `("meta/X.md:12", [])`.
   - **End to end,** `hands kit check` exits 0 with "PASS protocol" when a send
     names any of these. The U3 sub-agent's probes:
     - `meta/MISSING.md:12`, `meta/MISSING.md#L3`, `“meta/MISSING.md”`;
     - `meta/MISSING.md…`, `--prompt-file=meta/MISSING.md`, `meta/MISSING.md|`;
     - the bare names `NOTES` and `MISSING.1`.
   - **The report contradicts §29.** FINAL-REPORT-13 §3.3 and the U3 body treat
     the bare names as a place where §29 is silent, but the text names them. No
     finding was filed. The Review items table marks REVIEW-12 should-fix 1
     "closed". The `path:line`, `#anchor`, `=`-joined, Unicode-quoted and
     `…`/`|`-suffixed misses are disclosed nowhere.

3. **`hands who` with several configs, none named, and the first one broken
   exits 1 (U6 `8f79f98`; §29 Two projects).**
   - **The claim.** The U6 body says: "A config that fails to load gets a line
     of its own. With several configs and none named, it starts from the first
     by name."
   - **The code.** At `src/hands/cli.py:741`, the fallback calls
     `load_config(names[0])` inside the `except ConfigError` handler, and
     nothing guards that call.
   - **The sub-agent's probe** (temp HOME, `alpha.toml` invalid, `beta.toml`
     valid):
     ```
     hands who                -> exit 1, 'hands: ~/.hands/alpha.toml is not valid TOML: ...'
     hands --project beta who -> exit 0, alpha shown as "config unreadable"
     ```
   - **Tests and disclosure.** No test covers a broken first config, and §3.6
     does not mention it.

4. **`[who] grace_s = nan` and `inf` load, and they hide the matched
   transcripts for good (U5 `9ca89cf`; §29 Bookkeeping; REVIEW-12
   should-fix 9).**
   - **The claims.** FINAL-REPORT-13 §2 U5 says "invalid values are refused at
     load". `docs/INTEGRATION.md:168-170` says "a number >= 0".
   - **At the tip**, `config.parse_config` on `[who] grace_s = <v>` gives
     `nan LOADED nan`, `inf LOADED inf` and `60 LOADED 60.0`.
   - **The effect.** In `src/hands/who.py:412`, `now - ended > nan` is never
     true, so a matched human session stays hidden forever.
   - **The tests don't prove the validation.** The four refusal rows added at
     `tests/test_config.py:660-663` (`-1`, `'60'`, `true`, `who = 60`) also
     pass on the parent, which refused the whole unknown `[who]` table.
   - **The cause.** The shared `_number` helper (`config.py:866-872`) checks
     only the type and `< 0`.

## Should-fix

1. **The `git -C` pin is lexical (U1 `eccc3a1`; §29 "pins `git -C` to the
   role's clone path"; REVIEW-12 should-fix 2).**
   - **The compare.** `driver/hooks/bash_guard.py:475` compares
     `os.path.abspath(value)` with `os.path.abspath(clone)`. abspath folds `..`
     as text, but the kernel follows symlinks.
   - **The probe.** With a symlink `link -> /tmp/rev13-evil/sub` committed in
     the clone, `git -C <clone>/link/.. status` is allowed in role mode. git
     then runs in `/tmp/rev13-evil` and executes that repository's
     `core.fsmonitor`: the marker file appeared.
   - **Also.** Each `-C` is checked alone, but git applies them cumulatively:
     `git -C repo -C repo` passes and runs in `repo/repo`.
   - **The fix.** Compare `realpath`, or allow only the exact spelling, and
     refuse a second `-C`.

2. **A process left in the job's session without the `HANDS_JOB` mark is not
   reported (U2 `ea7f1bc`; §29 sweep).**
   - **What §29 says:** "what remains after the sweep is reported as
     `monitor.orphan_processes` with `killed: false`".
   - **What the code does.** `src/hands/runner.py:1100` lists an unproven
     process only when it carries the mark. A process in the job's session that
     started at or after `last_seen` (the residual) and has no mark is
     therefore neither killed nor reported.
   - **The probe.** `_sweep` returned `[]`, `on_orphans` was called 0 times, and
     the process stayed alive.
   - **The fix.** A session id equal to the job's pid identifies the process
     without the mark, so the sweep can report it as `killed: false`.
   - **Why it matters in practice.** In the sub-agent's end-to-end group-mode
     runs without the test linger, a quick exit after the fork left the orphan
     alive (`killed: false`) in several of the runs.

3. **The pipe-timeout test does not bind job end to the configured value (U2;
   §29 `runner.pipe_timeout_s`).** The test at `tests/test_runner.py:1316`
   asserts `elapsed < DRAIN_S + timeout + 5.0`. The sub-agent replaced
   `timeout = self.config.runner.pipe_timeout_s` at `runner.py:757` with
   `timeout = 5.0`, and the test stayed green.

4. **Doctor goes green when the settings name the guard but the command does
   not run it as a guard (U4 `38022f2`; §29 Consult; the REVIEW-12
   should-fix 4 class).**
   - **The code.** `src/hands/doctor.py:511-519` takes any shlex word ending in
     `/.claude/hooks/bash_guard.py` and ignores the rest of the command, then
     self-tests that file with `python3`.
   - **Hook commands doctor reports ok (exit 0) but which enforce nothing:**
     - `python3 .claude/hooks/bash_guard.py --selftest`: the guard runs its
       self-test and never reads stdin, so every call is allowed;
     - `python3 .claude/hooks/bash_guard.py || true`;
     - `echo .claude/hooks/bash_guard.py`, `python3 -c 'pass' …`, `node …`;
     - `cd <elsewhere> && python3 .claude/hooks/bash_guard.py`;
     - settings with `"disableAllHooks": true`.
   - **Disclosure.** None of these are in §3.4.

5. **`max_consults` gives a fresh budget on every daemon restart mid-mission
   (U4; §29 Consult, should-fix 5).**
   - **The mechanism.** The floor is `record.created >= since`
     (`playbook.py:1213-1219`), and `since` is set at daemon start
     (`daemon.py:199`).
   - **The effect.** A recognised kickoff that is kept in `pipeline.json` still
     counts as 0 after a restart: the probe gave 2 used, then 0 (max 2). A
     driver job queued before the restart and run after it counts 0.
   - **The design text.** §29's "when no kickoff or apply has been seen since"
     supports this reading, and also "only when no recognised anchor exists".
   - **What's missing.** The body and §3.4 disclose the restart, but no finding
     asks the architect to settle the reading.

6. **Project names are not validated (U6 `8f79f98`; §29 Two projects).**
   `src/hands/config.py:394-404` puts no limit on the name, so:
   - `..` puts the spool at `~`: `handsd --project ..` created `~/jobs`,
     `~/roles` and `~/inbox.jsonl`.
   - `.` puts it at `~/.hands` and creates the flat layout, so every handsd
     refuses to start after that.
   - `a/b` nests the spool.
   - `jobs` or `roles` looks like the flat layout, and `hands migrate-spool`
     then moves that project's live spool.
   - §3.6 discloses only `jobs` and `roles`.

7. **References to the retired un-templated units remain (U6; §29 "the
   un-templated units are retired"):**
   - `docs/INTEGRATION.md:366` (`systemctl --user restart handsd`);
   - `docs/INTEGRATION.md:438` (`journalctl --user -u handsd`), pinned by
     `tests/test_docs.py:171`;
   - `src/hands/cli.py:893` (the migrate-spool refusal says
     `systemctl --user stop handsd`, even for a per-project daemon);
   - `DESIGN.md:644` and `DESIGN.md:921` (`handsd.service`,
     `handswho.service`). Builders may not edit DESIGN.md, and no finding was
     filed for these lines.

8. **Precedence between cancel and limit is still unpinned (U0 `b79d908`;
   REVIEW-12 should-fix 8).** The U0 sub-agent moved the limit check in
   `src/hands/runner.py:911-913` ahead of the cancel check, and the full suite
   still passed (1994). `docs/INTEGRATION.md:177-178` does not say which one
   wins. The Review items row discloses this ("cancel vs limit unpinned"), but
   the item asked for "the precedence of `killed`/`limited`", and this is that
   pair.

## Notes

- **Gates.** Each unit's `./scripts/check` was green once at its commit, under
  eight concurrent suites. The pass counts match the report: 1994, 2092, 2098,
  2196, 2235, 2272, 2283, 2283. This review did not reproduce FINAL-REPORT-13
  §4's 3/3 on the tip. bae5639 changes only meta/ over 0a14085, which was green.
- **Test-first.** Every unit's tests go red when its product change is reverted
  or mutated. For U0, which has no product file, the red came from REVIEW-12's
  mutations to the doc and the runner. For U7, restoring `PLAYBOOK.toml` in
  place fails on `PlaybookNotCommitted`; a parent worktree carrying only the
  new test fails on the value itself, as the body says.
- **Forbidden files.** No unit commit after U0 touches DESIGN.md, meta/plan.md
  or meta/CHECKPOINT.md. U0 is the orchestrator's `plan:` commit, which the
  brief allows. FINDINGS.md status lines were changed in place, which
  DESIGN.md:1140 allows; resolutions were appended. H-023 was open at U0 and
  resolved at U2.
- **Findings.** Mission 13 filed no new finding, yet §3.3 (bare names read as
  "§29 is silent") and §3.4 (the restart anchor) are readings the brief routes
  to a finding.
- **§3 NOT PROVEN against what the sub-agents found:**
  - **§3.1** understates the heredoc case: it is a working bypass, not just
    unmodelled parsing (blocker 1). The symlink `-C` escape is not disclosed
    (should-fix 1).
  - **§3.2** is confirmed. `os.pidfd_open` is absent in uv's Python 3.14.6, so
    only the fallback kill ran. The residual is disclosed; the unmarked,
    unreported case is not (should-fix 2).
  - **§3.3** discloses the bare `Makefile` case but calls the item closed
    (blocker 2).
  - **§3.4** is confirmed on both "no rule fires while paused" and "only the
    first hook". The doctor wrapper cases are not disclosed (should-fix 4).
  - **§3.5** does not disclose NaN/inf (blocker 4). Also undisclosed: a job
    whose end handsd missed gets `ended` set to the restart time, so the window
    [started, restart] can span hours and hide a human session begun in it for
    60 s after the restart.
  - **§3.6** does not disclose the broken first config (blocker 3) or the `..`,
    `.` and `a/b` names (should-fix 6).
  - **§3.7** is accurate.
- **U2 is otherwise conformant.** The mark is never sufficient in `_sweep`,
  `_kill_group` or `_last_resort`. `last_seen` advances on every poll, with a
  measured largest gap of 6 ticks. Start times use one clock base, and each is
  re-read before a signal. `pipe_timeout_s` defaults to 10 and is validated.
  The residual is documented at `docs/INTEGRATION.md:566-586`.
- **U3 hosts.**
  - `idna>=3` is an explicit dependency in pyproject.toml and uv.lock.
  - The five hosts are refused before any fetch.
  - Numeric IPv4 spellings (`0x7f.1`, `127.1`, `2130706433`) and single-script
    confusables pass as names; §29 is silent on both.
  - The apply exception conforms to §29's text, and two different rules that
    match the literal are refused in a probe, but no test covers that case.
- **U4.** The paused branch of `on_event` sits outside the `try/except` that
  turns an engine exception into a stop.
- **U6.** `hands who` loads every config twice (`_peers` plus `all_sources`). The
  units use `%i`, which is correct: `%I` would unescape `-`.
- **U7.** `meta/BUILDER-14-PROMPT.md` does not exist, and nothing flags a
  kickoff that names a missing brief. The design does not require such a check;
  §5.2 of the report asks the architect's kit to ship the brief.

## Per-commit verdicts

### b79d908 (U0)

```
REPORT
sha b79d908 (parent 723dbeb), mission 13 U0 "Plan and bookkeeping", plan: commit
1 Body PASS: names U0 / BUILDER-13-PROMPT, DESIGN v3.12 §29, §28, §6, REVIEW-12 SF8 and blocker-1 corrections; lists all 6 --stat files.
2 Test-first PASS: no product file changes, so red proven by mutation. Baseline 14 passed. Doc: reorder 3 failed, "becomes done" 2, "success wins" 5, limit clause 5. Runner: nonzero_exit before error_result 1, line before limit 1, harness_terminated last 1. Limit-before-cancel swap: 14 passed (unpinned).
3 ./scripts/check GREEN: "1994 passed in 262.17s (0:04:22)" / "== cli smoke ==" / "check: green". Run in a separate worktree while other reviewers were running.
4 Conformance PASS: FINAL-REPORT-12 +15/-0, two corrections dated 2026-09-15. FINDINGS +26/-3; the 3 removed lines are Status lines replaced in place, which §28 allows (DESIGN.md:1140). Resolutions appended in their own sections. H-023 "Status: open (closes with mission 13 U2)", as the body says. DESIGN.md untouched.
4 Precedence table: killed (3 runs), limited (3 runs), terminating line (1 run) pinned in doc and runner. Cancel vs limit unpinned repo-wide, as disclosed: the swap passes the full suite, 1994 passed.
NOT PROVEN: whether the orchestrator or a sub-agent wrote meta/plan.md and meta/CHECKPOINT.md. Every commit has one author (Matthew Sigurko) plus a Claude co-author line; only plan.md's "[x] U0 (this commit)" marks it as the plan: commit. spawn_error is checked only for its place in the list.
Note: at the parent, "becomes done" and "success wins" already fail (tests/test_docs.py:228-231, from 4da83f8); only the reorder slipped past the parent's suite. REVIEW-12 SF8's "still green" held only for the single test at :285.
```

### eccc3a1 (U1)

```
sha eccc3a1 (parent b79d908), mission 13 U1; worktrees removed, repo untouched
1 PASS  Body names U1 with DESIGN v3.12 §29 "The guard", §28, §27, §12 rule 6, REVIEW-12 B1/SF2 and H-024; its file list matches all 10 files in --stat
2 PASS  Tests red with the parent's product files (mostly the new clone= argument; the hook probes and HANDS_CLONE tests fail on behaviour).
        Every "newly blocked" probe: parent 0, commit 2. `ls # it's`+NL+`touch …` is correctly marked as already blocked in role mode
3 PASS  ./scripts/check: "2092 passed in 236.72s (0:03:56)" / "== cli smoke ==" / "check: green" (first run)
4a PASS `#` outside quotes refused in both modes; the message names the offset
4b FAIL candidate BLOCKER: a heredoc hides a second command; hook exits 0 in both modes, bash runs it (pre-existing, still open)
4c FAIL candidate BLOCKER (needs a committed symlink): the -C pin is lexical, so <clone>/link/.. escapes and git runs another repo's core.fsmonitor.
        handsd does set HANDS_CLONE (runner.job_env:950-956 via config.driver_clone, used at runner.py:583)
4d PASS All 298 parent-allowed rows stay allowed, except role-mode `git -C ~/git/hands` with clone ./repo, which the pin requires (the one table row that asserted it moved, as disclosed)
4e PASS DESIGN.md, meta/plan.md, meta/CHECKPOINT.md not in --stat
NOT PROVEN: that Claude Code runs Bash like `bash -c`/eval (both run the heredoc probe); that the hook inherits the job env; a real driver session
```

### ea7f1bc (U2)

```
sha ea7f1bc  mission 13 U2 "The sweep after the reap"
1 Unit/files: PASS. Body names U2 and DESIGN v3.12 §29, with §28, §24, §27 and §13; its Files list matches all 12 files in --stat.
2 Test-first: PASS. Parent code with the commit's tests: 12 failed. The new linger and wait-for-observation do not hide a broken sweep: a sweep that never kills, or no poll observation, fails all three §24 tests. SHOULD-FIX: the pipe-timeout bound is loose (test_runner.py:1316).
3 ./scripts/check: GREEN, "2098 passed in 271.07s (0:04:31)" / "check: green".
4 §29: PASS on a–h, one SHOULD-FIX. (a) session id == job pid AND start tick < _last_seen; _last_seen set on every _until_exit poll; clock = CLOCK_BOOTTIME ticks (probe: consistent). (b) the mark only adds killed:false entries in _sweep; _kill_group and _last_resort never read it. (c) start time re-read before each signal; pidfd path not taken. (d) default 10, refuses -1/True/"10", bounds _drain. (e) killed on every entry. (f) documented at INTEGRATION.md:566-586. (g) H-023 now resolved. (h) DESIGN.md, plan.md, CHECKPOINT.md untouched.
SHOULD-FIX (e): a session member left alive without HANDS_JOB is not reported at all (runner.py:1100), against §29 "what remains after the sweep is reported ... killed: false".
NOT PROVEN: the pidfd kill path (the uv venv's Python 3.14.6 has no os.pidfd_open; system python3 does); kernels before 5.3; loop stalls longer than 50 ms (measured max gap 6 ticks); real claude's Bash-tool session layout. How big the residual is in practice: in group mode, 3 of 6 end-to-end forks with no linger were left alive (killed:false).
```

### 126d4ff (U3)

```
REPORT
- sha 126d4ff, mission 13 U3 "Kit transport and kit check". The body claims DESIGN v3.12 §29 "Kit transport", with §28, §26, §27 and §12.
- 1 Body: PASS. It lists all 8 files in `--stat`.
- 2 Test-first: PASS. With the parent's src and docs, 77 tests fail (61 in test_kit, 16 in test_phone) and 236 pass. The worktree was restored afterwards.
- 3 Gate: PASS on the first run: `2196 passed in 277.33s (0:04:37)` / `== cli smoke ==` / `check: green`.
- 4a idna dependency: PASS. `idna>=3` is in pyproject.toml and in uv.lock (both the dependencies and requires-dist).
- 4b Hosts: PASS. The five hosts are refused before any fetch, and those tests are red at the parent. Of about 55 more hosts, nothing that `idna.encode` refuses got through. Notes follow in EVIDENCE.
- 4c Quoting: PASS. The name is `shlex.quote`d. handsd and kit check both build the prompt through `plan_apply`, and the byte-equality test includes `a$(x)`y`;'z.zip`.
- 4d Named paths: FAIL. Candidate BLOCKER, details below.
- 4e Apply exception: PASS. The code fits §29's text, a 16-row table test enumerates it, and two different rules that match the literal are refused (probed).
- 4f DESIGN.md, meta/plan.md and meta/CHECKPOINT.md are untouched: PASS.
- NOT PROVEN: which port httpx uses for `a.com:+80` (the port reads as None); whether a real resolver fetches `127.1`, `0x7f.1` or `2130706433`; a real ntfy fetch; byte equality for any kit_dir other than `~/Downloads`.
```

### 38022f2 (U4)

```
sha 38022f2  mission 13 U4 "Consult edges"; body cites DESIGN §29 Consult (SF3/4/5), §28, §27, §10, §11
1 PASS  the body lists all 7 files in `git show --stat` (3 src, 2 tests, 2 docs)
2 PASS  test-first: 34 failed / 7 passed on the selected tests with the parent's src+docs; 41 passed at the commit
3 PASS  ./scripts/check green: 2235 passed in 284.00s, "check: green"
4a PASS all 7 stop kinds x 4 playbook shapes file stop_suppressed with the reason and notify once; a limited driver is never resumed (limits.py:349)
4b SHOULD-FIX doctor goes green when the command runs no guard: --selftest, `|| true`, echo, python3 -c, node, cd <dir> &&, disableAllHooks
4c SHOULD-FIX a restart mid-mission resets consults 2->0 (max 2); a driver job queued before restart and run after counts 0
4d PASS  DESIGN.md, meta/plan.md, meta/CHECKPOINT.md untouched
NOT PROVEN, now confirmed: "no rule fires while paused, not even a stop rule"; "only the first hook checked" (only unsafe if the first hook is not the guard)
NOT PROVEN, open: whether a real Claude Code honours a hook at a non-default path or with args
Neither 4b nor 4c has a finding in meta/findings/FINDINGS.md (at 38022f2 or main)
Worktrees /tmp/rev13-38022f2 and /tmp/rev13-38022f2-tf removed
```

### 9ca89cf (U5)

```
REPORT
- **sha:** 9ca89cf, mission 13 U5 "Who grace".
- **1 Body: PASS.** It names U5, DESIGN §29 Bookkeeping (plus §28, §27, §26, §13) and REVIEW-12 should-fix 9, and it lists all 5 files in `--stat`.
- **2 Test-first: PASS, with one SHOULD-FIX.** With the parent's non-test files, 34 tests fail and 175 pass. All 29 new who tests and 5 of the 9 changed config tests are red. The 4 new "refused" config cases (`-1`, `'60'`, `true`, `who = 60`) pass on the parent too, so they don't prove the new validation. The builder's claim that 12 tests fail with the grace code disabled checks out: 12 failed.
- **3 Gate: PASS.** `./scripts/check` is green: 2272 passed.
- **4a Config: candidate BLOCKER.** The default is 60, and -1, -inf, bool and string are refused. `grace_s = nan` and `inf` load, and both hide the matched transcripts forever, which contradicts "a number >= 0" in the body and in docs/INTEGRATION.md:117.
- **4b Mechanism: PASS, with one SHOULD-FIX.** It ties a transcript to a job by session id, or by a time window: the transcript's first `timestamp` falls within the record's [`started`, `ended`]. A human session begun during that window is hidden until the grace passes; this is disclosed, and the hiding is bounded unless `grace_s` is NaN or inf. A missing timestamp is disclosed. Clock skew is not a real risk: every stamp comes from the same host in UTC. The SHOULD-FIX: if handsd is down when a job ends, its `ended` is never recorded, so the grace does not apply, and this is not disclosed.
- **4c Boundary: PASS.** Hidden at 60 s and 59.9999 s, shown at 60.001 s.
- **4d Docs: PASS.** docs/INTEGRATION.md has the config block, the who view and the limits paragraph. README only mentions who in passing.
- **4e Protected files: PASS.** DESIGN.md, meta/plan.md and meta/CHECKPOINT.md are not touched.
- **NOT proven:**
  - The grace path has never run on real data. The only real ended record without a session id has no `started`.
  - The builder's first NOT PROVEN item (a first `timestamp` within 20 lines) holds on real data for 37 of 37 clear-context jobs. The 3 jobs whose first timestamp comes before `started` are all `context=keep`, and those are excluded by session id anyway.
```

### 8f79f98 (U6)

```
sha 8f79f98, mission 13 U6 "Two projects on one laptop"; body cites DESIGN §29 (with §5, §13, §14, §26-§28).
1 body/claims: PASS. The file list covers all 19 files in --stat (8 src, 3 systemd incl. the rename, README, INTEGRATION, 8 tests).
2 test-first: PASS. Parent src/docs/units: 11 failed, 820 passed, 1 error (test_two_projects.py ImportError, 11 tests). At the commit: 842 passed.
3 gate: PASS. ./scripts/check green, 2283 passed.
4 design: PARTIAL.
  (a) PASS: nothing two daemons share. (b) PASS. (c) PASS: probes behave, event is spool.migrated.
  (d) FAIL: 3 live references to the retired unit name remain, 1 pinned by a test (SHOULD-FIX).
  (e) PARTIAL: projects found by globbing *.toml, but one broken config kills `hands who` (candidate BLOCKER).
  (f) PASS. (g) FAIL: project names are never checked (SHOULD-FIX). (h) PASS.
Candidate BLOCKER: the body says "A config that fails to load gets a line of its own"; with none named and the first config broken, `hands who` exits 1.
NOT PROVEN (the builder says so too): the units under real systemd (systemd-analyze only objected to the missing ~/.local/bin binary); who with two live daemons; an interrupted migration; an old daemon on a socket outside ~/.hands that no config names.
```

### 0a14085 (U7)

```
REPORT
- sha 0a14085 (parent 7797d7e; tip bae5639 changes only meta/). No BLOCKER and no SHOULD-FIX found.
- 1 PASS. Unit is mission 13 U7, "This repository's playbook". The body cites DESIGN v3.12 §10, §27 Conventions and §29 (roadmap: mission 14 is the architect role); the test docstring adds §26. The body lists both files in `--stat` (PLAYBOOK.toml, tests/test_playbook.py). The diff is exactly the kickoff line plus the pinned test value and its docstring.
- 2 PASS, with a caveat. Simply restoring PLAYBOOK.toml fails for the wrong reason: 4 root-playbook tests fail on `PlaybookNotCommitted`, because the loader rejects a dirty file. Done the way the body describes (a worktree at the parent with only the new test applied), the kickoff test fails on the value itself (`- BUILDER-14` / `+ BUILDER-13`).
- 3 PASS. `./scripts/check` at 0a14085: `2283 passed in 280.17s (0:04:40)` / `== cli smoke ==` / `check: green`, exit 0. `git diff --stat 0a14085 bae5639` shows only meta/CHECKPOINT.md, meta/FINAL-REPORT-13.md, meta/journal.md and meta/plan.md, so I did not run the check at bae5639.
- 4 PASS.
  - Gate: a zip holding only meta/BUILDER-13-PROMPT.md (byte-identical to HEAD's), checked with `uv run hands kit check <zip> --repo .`, gives `kit check: pass (6 of 6 checks)`, exit 0. The builder checked a directory; I checked a zip and got the same result.
  - The new line has the same form as the BUILDER-11, -12 and -13 lines.
  - DESIGN.md, meta/plan.md and meta/CHECKPOINT.md are untouched.
- 4, missing brief: meta/BUILDER-14-PROMPT.md does not exist (at 0a14085 meta/ holds BUILDER-1 to BUILDER-13 only). Nothing flags a kickoff that names a missing brief:
  - doctor's `go` row (src/hands/doctor.py:255-293) reports "go on" and prints the line.
  - phone `go` (src/hands/phone.py:329-360) sends it as is.
  - kit check does not compare the repo's kickoff (src/hands/kit.py:607).
  - Loading the playbook does not check that the file exists.
  - The design does not require such a check: §26 compares only a kit's kickoff with its brief, and §27 Conventions says only that the next kit ships the playbook line.
- NOT PROVEN: meta/FINAL-REPORT-13.md §3.7 and §5.2 state this correctly. Until the architect's kit lands, a phone `go` would send the builder to a brief that is not there. I did not rerun the check three times in a row (the 3/3 claim).
```
