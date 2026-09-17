# REVIEW-17 — cold review of hands mission 17

VERDICT: review mission 17 blockers=1 should-fix=7

Base `2e43378` (`review: mission 16`, the last `review:` commit on origin/main).
Tip `011899e`. Unit commits reviewed, one sub-agent each, in a `git worktree` at
the commit: c5b5416 (U0, the orchestrator's `plan:` commit), f6f7f26 (U1),
6f05e4e (U2), 2a08e42 (U3), c6380ab (U4), de17a7e (U5), 4775880 (U6), 63ac5c3
(U7). Not dispatched: 0b8447e (the architect's mission-17 kit) and 011899e (U8,
the `meta:` commit that adds meta/FINAL-REPORT-17.md and the bookkeeping); U7's
sub-agent checked 011899e's report and findings against the disk. The reviewer
read the code behind blocker 1 and should-fix 5 at the tip: `_publish_start`
(`src/hands/daemon.py:293-309`) folds each note's title and message, not its
actions, and `_guard_selftest` (`src/hands/doctor.py:816`) counts exit 0 as
green, while `_guard_command_path` (`doctor.py:1183-1203`) accepts any absolute
path that ends in `/.claude/hooks/bash_guard.py`.

## Blockers

1. **A job held during the start fold window gets no Approve/Deny buttons (U4
   `c6380ab`; §24 "a held-job notification carries Approve/Deny action
   buttons", §26 "The held notification carries the buttons").** A start that
   re-admits queued jobs now holds back every notification for up to
   `START_FOLD_S` (5 s). It then publishes one "handsd started" that lists the
   held notes by title and message only. The held job's actions are dropped
   (`daemon.py:293-309` at the tip; `notify.py:257-258` at c6380ab). The "decide
   with `hands approve`" text is added only for jobs that were held *before* the
   start (`daemon.py:264-271` at c6380ab).
   - Sub-agent probe: a real Daemon, a queued builder job (`FAKE:sleep 3`), and
     an aux job gated at 0.3 s. `held job … held at 0.42`, then one publish at
     3.2 s, `title='hands: handsd started' actions=False`, whose message holds
     `hands: a job is held for a human: phone test`.
   - The human gets no button and no nonce. Only a typed `approve <job>
     <secret>` still works.
   - FINAL-REPORT-17 §3.7 discloses it ("a hold inside the window is listed
     without its buttons"). No finding covers it, so by CLAUDE.md the design
     wins.
   - Fix: publish a held note's actions (or the held note itself) even inside
     the window. Or file a finding and let the architect change §26.

## Should-fix

1. **The kit record does not bind the bytes it checked (U1 `f6f7f26`; §33 "the
   engine approves only an apply whose stored `kit_id` records a passing
   check").** `kit.json` holds `check: pass` but no sha256 (`spool.py:498` at
   f6f7f26), and `kit_apply_problem` checks only `check` and that the zip exists
   (`spool.py:855-858`).
   - Sub-agent probe: a real daemon with `[files] allowed_roots` covering the
     home directory. `kit_file foo` of a passing kit, then a socket `put` over
     `<spool>/kits/<id>/foo.zip` with a check-failing zip. Result: `stored zip
     now passes check_kit? False` and `apply job state=done gate=approved
     by=playbook`.
   - The default roots refuse the `put`, which is why this is not a blocker.
   - Fix: record the checked zip's sha256 and compare it at approval and apply.
2. **Two concurrent `kit_file` calls in one consultation: the first kit is
   engine-approved and applied (U1 `f6f7f26`).**
   - FINAL-REPORT-17 §2 says "two kits in one consultation → both denied,
     `escalate`", and `kit_filed`'s docstring says "no second kit is accepted"
     (`playbook.py:2244`).
   - Cause: `_consultation_for` (`api.py:332`) runs before the slow `check_kit`
     (`api.py:344`), and the wait is popped only afterwards (`api.py:356`).
   - Probe: two `kit_file foo` tasks during the `next kit` wait. Both were held.
     One was `state=done … approved by=playbook`, the other denied, and the stop
     reason was "filed 2 kits".
   - §33's minimum (the second is denied and the consultation escalates) holds.
     The report's claim does not. §3.3 lists concurrency as not proven.
   - Fix: serialise `kit_file` per consultation, or take the slot before the
     check.
3. **A symlink inside an execute-only directory under `kits/` is invisible to
   the guard and to doctor (U3 `2a08e42`; REVIEW-16 should-fix 2 and 3).**
   `kits_symlink` (`driver/hooks/bash_guard.py:549`) and doctor's `_kits_line`
   both use `os.walk`, which silently skips a directory it cannot list.
   - Probe: `kits/d/h -> ../.claude/hooks/bash_guard.py`, then `chmod 0111
     kits/d`. `cp -r kits/d/h kits/ && cp kits/pay/h kits/` exits 0, and under
     real bash it overwrote the guard.
   - Doctor printed `ok` and "no symlink under it".
   - The premise is the same as REVIEW-16's: a link already planted. The
     architect cannot `chmod` or `ln`.
   - Fix: fail closed on a walk error (`onerror`), in both places.
4. **Doctor's role rows pass settings that change how the guard runs (U3
   `2a08e42`; §33 "fails a role row when the settings disable a hook …").**
   - Doctor reads no `env` key. `settings.local.json` with `{"env":
     {"HANDS_KITS": "<cwd>", "HANDS_ROLE": ""}}`, or with `PATH`, `PYTHONPATH`
     or `CLAUDE_PROJECT_DIR`, gives `ok` on both rows. It still prints "every
     write confined to HANDS_KITS=<kits>".
   - Run with those values, the shipped guard allows a `--write` to
     `.claude/settings.json` and `hands approve 1`, or it exits 1 (which does
     not block).
   - `"async": true` and `"timeout": 0.001` on the guard hook also pass
     (`_not_a_command_hook`, `doctor.py:998-1004` at 2a08e42).
   - Whether Claude Code applies these to hooks was not run. FINAL-REPORT-17
     §3.6 does not list them.
5. **Doctor's self-test accepts any guard that exits 0, at any path (U3
   `2a08e42`; §33 "resolves every path it checks and fails a role row when the
   settings … name a different command").**
   - `_guard_command_path` returns `cwd / word`, so an absolute path elsewhere
     that ends in `/.claude/hooks/bash_guard.py` is accepted.
   - `_guard_selftest` counts only `probe.code == 0` (`doctor.py:816` at the
     tip).
   - Probes: `python3 /tmp/…/evil/.claude/hooks/bash_guard.py` (a file that
     exits 0) in the driver's settings gave `driver ok`. The shipped path with
     its content replaced by `import sys; sys.exit(0)` gave `ok` and "self-test
     green".
   - The rule predates this commit. The row now prints the realpath it
     "verified", but it does not require that path to be the role directory's
     guard.
6. **A stop inside the fold window can drop the start notification and
   everything folded into it (U4 `c6380ab`).** `stop()` publishes the start
   notification, then `notifier.cancel_all()` (`daemon.py:439` at the tip)
   cancels the delivery still in flight.
   - Probe: queued failing aux and blocked builder jobs, 0.5 s publish latency,
     stop at 1.0 s. At c6380ab: `called: [(1.03, 'hands: handsd started')]` and
     nothing was delivered. With the parent's daemon.py, "handsd started" and
     "the pipeline stopped" were both delivered.
   - The code comment and commit body say "named in its message, never
     dropped". §3.7 says only "may not deliver".
7. **A token with the default `ntfy_url` is silent (U6 `4775880`; §33 "Free text
   about a project never crosses a public broker once this is set").**
   - Probe: `ntfy_token` set and `ntfy_url` absent. `send_test` posts to
     `https://ntfy.sh/hands-x` with the bearer. Doctor says `ntfy token on` and
     `ok`.
   - Refusing would be wrong, because ntfy.sh accounts use tokens. But nothing
     tells the user that the token and all free text go to the public broker.
   - Fix: name the host on the doctor line, or warn when the token is set with
     the public URL (`config.py:73`, `config.py:549-552`).

## Notes

- **Gates.** `./scripts/check` was green once at each of the eight unit commits.
  Every pass count matches FINAL-REPORT-17 §1: 3747 (U0), 3761 (U1), 3784 (U2),
  3879 (U3), 3897 (U4), 3908 (U5), 3935 (U6), 3935 (U7). This review did not
  reproduce the "3/3" runs. 011899e changes only meta/ over 63ac5c3, which was
  green.
- **Test-first.** Every product unit's tests go red when its product change is
  reverted:
  - U0: 3 failed. This needs the parent's templates committed; otherwise
    `PlaybookNotCommitted`.
  - U1: 195 failed. The engine unit tests fail on signatures, as disclosed.
  - U2: 22 failed.
  - U3: 86 failed (85 of 95 new cases, plus a docs pin).
  - U4: 12 of 34 selected.
  - U5: 12 failed, after an import patch.
  - U6: 25 failed.
  - U7: the kickoff test, on the value, with the parent's PLAYBOOK.toml
    committed.
  - Coverage-only tests are named in each per-commit report.
- **Files.** Every unit body lists every file it touches. No unit touched
  DESIGN.md. meta/plan.md and meta/CHECKPOINT.md changed only in c5b5416
  (`plan:`) and 011899e (`meta:`). The FINAL-REPORT-16 and FINDINGS.md edits
  are append-only apart from status lines.
- **U0.** The body says meta/plan.md and meta/CHECKPOINT.md are "unchanged
  here", but the diff changes them. The sweep claim holds.
- **U1.**
  - When two kits are filed, the first is also denied. That is the builder's
    reading where §33 is silent, and no finding records it. The race in
    should-fix 2 does not apply it.
  - `kit check` judges a role-mode playbook against whichever config resolves,
    not the one whose builder is `--repo`.
  - A crash after the architect ends `done` but before the engine's end leaves
    the kit held, with no stop. Nothing approves it.
- **U2.** No candidates.
  - The reviewer's zip and many variants are refused on all three paths: 0x7075
    in either header, mismatched names, duplicates, a symlink entry followed by
    a file through it, `.Claude`, and concatenated archives.
  - §3.5's "several end-of-central-directory records" did not reproduce as a
    split between Python and info-zip 6.00; both pick the same directory.
  - H-036's code line says `_zip_entries` is "the only reader of
    `orig_filename`". Its helper `_names_problem` (`kit.py:426`) also reads it.
- **U3.** The guard refused every other cp/mv spelling and writer tried:
  - `-t`, `--target-directory=`, `-T`, `-P`, `-a`, `-s`, `-l`, and `..` paths
  - `ln -s … && cp`, `tee`, `>`, `install`, `unzip`, `tar`, `rsync`
  - A hardlink planted under `kits` does let `cp` and `--write` rewrite the
    guard; §3.6 lists hardlinks as not covered.
  - Doctor lets `"hooks": {}`, `PreToolUse: []`, defaultMode `dontAsk`/`plan`
    and `Write(/home/**)` pass.
- **U4.**
  - The heading rule reads `(DONE)`, lower-case `done`, `**DONE**`, and a DONE
    on a wrapped heading's second line as not done.
  - It reads `NOT DONE` inside the bold title and `— DONE-criteria` as done.
  - On this repository's meta/ROADMAP.md the prompt names M4 (mission 8, never
    marked DONE). That is right by the rule, but stale.
  - With a queued job, every restart's start notification now arrives up to
    5 s late. A queued job ending after 5 s gets its own second notification,
    which is the designed bound.
- **U5.** No candidates.
  - The escalation line is pinned by a mission-16 test
    (`tests/test_playbook.py:5049-5083`).
  - The last session is the most recent consultation's.
  - A reply's `VERDICT: next kit` opens no kit wait.
  - `reply_architect` is not a socket method.
  - The secret is compared with `hmac.compare_digest`.
  - "Verbatim" drops the text's leading whitespace, since `\s+` is the
    separator. Inner and trailing whitespace, CRLF, unicode and 200 KB texts are
    stored exactly.
  - Refusal covers queued and held architect jobs as well as running ones,
    which is stricter than §33.
  - A gated reply's text appears in the held notification. A denied reply
    publishes nothing titled `architect`.
- **U6.** Every outbound HTTP call (`http_post`, `http_stream`, `fetch_kit`)
  carries the bearer when it is set, and `fetch_kit` does so only for
  `ntfy_url`'s origin.
  - Redirects are not followed; a 302 to another host never saw the token.
  - The token appears in no repr, doctor output, httpx error or role job
    environment.
  - H-037 is rightly a finding, not a design violation.
  - The container and server.yml steps look right but were not run.
- **U7.** The gate is weak, as §3.8 admits: the same kit check passes at
  4775880. A stronger probe confirms the new value: a kit carrying the new
  PLAYBOOK.toml plus a BUILDER-18 brief passes, and the old playbook fails on
  the kickoff. meta/BUILDER-18-PROMPT.md does not exist yet, so a phone `go`
  now names a missing file.
- **FINAL-REPORT-17 §3 NOT PROVEN against what the sub-agents found.**
  - §3.1 and §3.2 (real `reply`, real ntfy) stand. No sub-agent could run
    either.
  - §3.3 lists concurrent `kit_file` as untested. It is now shown to approve
    one kit of two (should-fix 2). The byte swap after the check is not listed
    (should-fix 1).
  - §3.4 stands.
  - §3.5: the EOCD gap did not reproduce with info-zip. The filesystem aliases
    stand.
  - §3.6 omits settings `env`, hook `async`/`timeout`, an unlistable directory
    under `kits`, and a guard at another path or one that only exits 0
    (should-fix 3–5).
  - §3.7 understates two things. The lost buttons are a design violation
    (blocker 1), and the stop drop was reproduced (should-fix 6).
  - §3.8 stands.
- The architect role stays off until this review (§33). Blocker 1 and
  should-fix 1–5 bear on that decision.

## Per-commit verdicts

The sub-agents' reports and evidence, verbatim except that inner code fences
are removed and each agent's closing cleanup line is omitted (every worktree
and scratch directory was removed; the main checkout was not touched).

### c5b5416 — U0

~~~~
REPORT
- **sha:** c5b5416. Unit: mission 17 U0, "plan: mission 17 plan, H-035/H-036, FR-16 corrections, sweep text". Its parent is 0b8447e.
- **1. pass.** The body names U0 as the plan and bookkeeping commit, DESIGN v3.16 §33 (sweep text) with §32's last paragraph, and REVIEW-16 blockers 1–2 (bookkeeping only) and should-fix 8.
- **2. pass.** I reverted the templates and docs/PLAYBOOK.md to the parent and committed that locally, since load_playbook refuses a template that differs from HEAD. Three tests failed on the value:
  - `names_no_cause`, both templates: `names a cause (['harness'])`
  - `killed_task_notifies_here`: "does not name H-034"
  - Coverage only (green either way): the PLAYBOOK.toml case, and the docstring-only change to `task_killed_cause_is_always_unknown`.
- **3. pass.** `./scripts/check` on a clean tree at c5b5416: "3747 passed in 244.76s (0:04:04)", last line "check: green". The count matches the body and FINAL-REPORT-17.
- **4. pass.**
  - DESIGN.md is untouched. meta/plan.md and meta/CHECKPOINT.md changed, which a `plan:` commit may do.
  - The body lists all 9 files that `git show --name-only` shows.
  - FINAL-REPORT-16.md (+22/-0) and FINDINGS.md (+92/-0) are append-only, and both new blocks are dated 2026-09-17.
  - Both corrections match REVIEW-16 blockers 1–2 and should-fix 1, 5 and 8, and the disk: FR-16 line 130's "closed", §3.2's "the client's check is the check", §2's "escaping zip", §3.8's "byte for byte", `api.py:267` has no `check_kit`, and `kit.py:381/432/1112` use `orig_filename`.
  - The quotes from §33 and §32 in H-035 and H-036 are exact, and H-034 already existed, as disclosed.
  - The sweep claim holds (NOTE 3).
- **NOTE 1.** The body says meta/plan.md and meta/CHECKPOINT.md are "unchanged here", but the diff changes them (+42/-84 and +19/-42). The wording probably means the sub-agent did not edit them; it is allowed for `plan:`.
- **NOTE 2.** A plain file revert makes the template tests red for the wrong reason (`PlaybookNotCommitted`), so red-first needs a local commit of the parent files. The test's cause words (`CAUSE_WORDS`) leave out "backgrounded" and apply to rule messages only.
- **NOTE 3.** The sweep claim holds. In templates, docs, PLAYBOOK.toml, README.md, driver/ and architect/, every mention of a harness or reap next to `task_killed` is hedged ("cannot say who killed it"), and the only two messages that named the harness are gone. Left as disclosed: the `daemon.py:125` comment and the tests/fixtures/kit-mission-10 template copies.
- **NOT proven:** that no other text (src comments, phone or notify output) names a cause. The body's "3/3" runs were not reproduced; I ran the gate once. None of H-035's or H-036's code exists at this commit, as disclosed.

EVIDENCE: there are no BLOCKER or SHOULD-FIX candidates. Supporting probes:
- **Red-first:** `git checkout c5b5416^ -- templates/PLAYBOOK-missions.toml templates/PLAYBOOK-runs.toml docs/PLAYBOOK.md`, then a local commit, then `uv run pytest tests/test_playbook.py tests/test_docs.py` gave:
  `FAILED tests/test_playbook.py::test_each_shipped_playbook_task_killed_message_names_no_cause[PLAYBOOK-missions.toml]`
  `FAILED ...[PLAYBOOK-runs.toml]`
  `FAILED tests/test_docs.py::test_the_sentence_under_the_verbatim_example_says_a_killed_task_notifies_here`
  Without the local commit, the failure is instead `hands.playbook.PlaybookNotCommitted: .../templates/PLAYBOOK-missions.toml is dirty`.
- **Append-only:** `git diff --numstat c5b5416^ c5b5416` shows `22 0 meta/FINAL-REPORT-16.md` and `92 0 meta/findings/FINDINGS.md`, and a grep for removed lines in those two files counts 0.
- **Sweep grep:** `grep -rniE "harness|reap|taskstop|timed? ?out|backgrounded|killed" templates docs PLAYBOOK.toml README.md driver architect` finds `task_killed` messages only at `templates/*:118/127` and `PLAYBOOK.toml:135`, each "A task inside a role job was killed". The other hits are hedged: `docs/PLAYBOOK.md:194-198`, `docs/INTEGRATION.md:912-916`, `README.md:117`. The `timeout` hits are `hands wait --timeout`.
- **§10 copy:** the §10 block from DESIGN.md is an exact substring of docs/PLAYBOOK.md (`True`), so its "stays byte for byte" (line 232) holds on disk.
~~~~

### f6f7f26 — U1

~~~~
REPORT
sha f6f7f26 (parent 0b8447e-line base; `kit: handsd checks the kit it files; one kit per consultation, as named`)
1. PASS: this is mission 17 U1, "The daemon checks what it approves". It claims DESIGN §33 "The autonomy path" bullets 1 and 3 (with §32, §31, §8, §26), and closes REVIEW-16 blocker 1 and should-fix 1 and 5 (H-035).
2. PASS: with the parent's version of all 12 non-test files restored, the 4 changed test files gave `195 failed, 610 passed in 36.63s`. All 10 new test functions were red. The e2e and test_kit tests failed on behaviour (`AssertionError: a kit that fails the check was filed`, `AssertionError: done`). The engine unit tests failed only on signatures (`TypeError … unexpected keyword argument 'deny'`, then `Spool.store_kit() missing … 'consultation'`), as the body says. The test_gates change (deny_from_playbook is not a socket command) passes either way, so it only adds coverage.
3. PASS: `./scripts/check` exit 0 once on a clean tree: `3761 passed in 251.66s (0:04:11)` / `check: green`.
4. PASS with candidates: the body lists all 17 files. DESIGN.md, meta/plan.md and meta/CHECKPOINT.md are untouched. On disk: `kit_file` runs `check_kit` on the stored file against the builder's cwd with the daemon's config, and deletes a refused kit. No socket method or spool path lets a check-failing kit get engine-approved under default roots. `kit check` judges role mode with `check_series_roles` and says "judged as handsd does at load (§33)". Bad or non-UTF-8 zips leave nothing behind. A restart while the architect runs denies the held kit and escalates, so it is safe.
- SHOULD-FIX: `kit.json` records `check: pass` but not the sha256 of the checked zip, and `kit_apply_problem` never compares one. So a socket `put` over `<spool>/kits/<id>/foo.zip` after the check gets check-failing bytes engine-approved. This needs `[files] allowed_roots` to cover `~/.hands`; default roots refuse the `put`.
- SHOULD-FIX: two concurrent `kit_file foo` calls during the next-kit wait are both accepted. The first is approved and applied, the second is denied and the pipeline escalates. This contradicts FINAL-REPORT-17 §2's "two kits in one consultation → both denied" and `kit_filed`'s docstring "no second kit is accepted" (playbook.py:2244). §33 and the gate ("the second denied") are still met.
- NOTE: denying the first kit too when two are filed is a reading the builder chose ("where §33 is silent"), and no finding records it. §33's text denies "the apply", singular. It also isn't applied consistently: in the race above the first kit is approved.
- NOTE: `kit check` judges against whichever config resolves (`--project`, `$HANDS_PROJECT`, or the only one), not the config whose builder is `--repo`. A single config serving another repo prints PASS "as handsd does at load". The commit's own test_kit fixture does the same (builder cwd tmp_path, repo tmp_path/repo).
- NOTE: if the daemon crashes after the architect ends `done` but before the engine's end runs, the kit stays held after restart with the pipeline not paused and no stop. Nothing approves it.
NOT proven: a real architect session; the double notify when a violating kit is held as the consultation ends; a `kit_file` cancelled mid-check; a hold deferred over a paused pipeline and then resumed.

EVIDENCE
SF-1: stored zip swapped after the check. Real daemon, fake_claude, role + autonomous playbook (tests' `architect_project`). The architect's `exec` does a raw-socket `kit_file foo` (passing kit), then a socket `put {"path": <spool>/kits/<kit_id>/foo.zip, "from_": bad.zip}` where bad.zip is harness `UNCHECKED_KIT`; reply `VERDICT: next kit foo`. The second case adds `[files] allowed_roots = ["<home>", "<workdir>"]`. Output:
[swap:default roots] put: REFUSED: '…/home/.hands/demo/kits/b3aadbd3b0ceb216/foo.zip' resolves to …/home
[swap:default roots] apply job state=done gate=approved by=playbook
[swap:allowed_roots includes home] put: {'path': '…/home/.hands/demo/kits/cf08a4ce4da7d059/foo.zip', 'sha256': '1f74559d…',
[swap:allowed_roots includes home] record: {'check': 'pass', 'consultation': '0mu4wqjih-wuub', 'kit_id': 'cf08a4ce4da7d059', 'name': 'foo'}
[swap:allowed_roots includes home] stored zip now passes check_kit? False; bytes == bad.zip? True
[swap:allowed_roots includes home] apply job state=done gate=approved by=playbook
[swap:allowed_roots includes home] stop_reason=Mission 17 finished
Refs: src/hands/spool.py:498 (record has no hash), spool.py:855-858 (checks only `check` and that the zip exists), src/hands/api.py:344-349 (check, then `apply_from_zip` re-reads the path, then the record is written).

SF-2: concurrent `kit_file` during the wait. Same e2e setup, reply `VERDICT: next kit foo`. The engine's `sleep` seam starts two independent tasks, `asyncio.create_task(daemon.api.kit_file(name="foo", zip=<passing>))` ×2. Output:
[concurrent-wait] kit_file results: [('dict', ('0mu4woioe-tek3', 'held')), ('dict', ('0mu4woins-923p', 'held'))]
  builder   origin=architect state=done     kit_id=a40a8f4ca55e07d7 decision=approved by=playbook
  builder   origin=architect state=denied   kit_id=004cc38d3f94f576 decision=denied by=playbook
[concurrent-wait] stop_reason: architect.done: the architect's consultation 0mu4woiik-a6aj ends escalate (§33): it filed 2 kits ('foo', 'foo'), and a consultation may file at most one; the engine denies 0mu4woioe-tek3 — session ad4f2319-…
[concurrent-wait] gate.decided: [('0mu4woins-923p', 'approved'), ('0mu4woioe-tek3', 'denied')]
Why: `_consultation_for` (api.py:332) runs before the slow `check_kit` (api.py:344), and `kit_filed` pops the wait only afterwards (api.py:356). `_decide_kits` (playbook.py:1712-1744) approves as soon as it counts one kit.
~~~~

### 6f05e4e — U2

~~~~
REPORT (sha 6f05e4e)
1. Unit/sections: PASS. U2 Zip names; DESIGN v3.16 §33 "The autonomy path" 2nd bullet (with §32); REVIEW-16 blocker 2; H-036.
2. Test-first: PASS. Reverting the 4 non-test files (kit.py + 3 docs) to parent → 22 failed, 460 passed in test_kit.py+test_phone.py; at the commit all 482 pass. The `unzip_writes_the_unicode_path` witness is coverage-only (green either way; disclosed) — it proves the attack, not the product.
3. Gate: GREEN. `3784 passed in 245.51s`, final line `check: green` (one clean run).
4. Design/scope: PASS. Central-directory name is the judge; local-header/0x7075/non-UTF8 disagreements and `.git`/`.claude`/outside-repo landings refused; one judge `_zip_entries` shared by `kit check` (`_read_zip`), `apply_from_zip` (phone path `phone.py:456`, `Api.kit_file` `api.py:344-347`). No caller outside the judge reads `orig_filename` (confirmed by grep). Body lists all 7 touched files; no DESIGN.md/plan.md/CHECKPOINT.md touched.

Adversarial probes (all defended):
- Concat/prepended archives: Python and info-zip `unzip` pick the SAME central directory in both orderings I tried (malicious-first→both take benign last; benign-first→both take malicious last and the judge refuses `.git`). The disclosed "several end records" gap did not reproduce against info-zip 6.00.
- symlink entry `l -> .git` then `l/hooks/pre-commit`: symlink entry flagged, whole kit refused (nothing written).
- 0x7075 field naming `.git` (both headers), duplicate names, `.claude`/`.Claude`/`docs/.claude`, symlink-into-.git/.claude through a repo symlink: all refused.

Candidates: none. No BLOCKER, no SHOULD-FIX.

NOT PROVEN (as the body/§3.5 disclose, and I could not exercise here): NTFS trailing-dot/space and HFS+ ignorable-code-point spellings of `.git`/`.claude`, and case-folded duplicates on a case-insensitive filesystem (Linux/ext4 + info-zip only tested); behavior against non-info-zip extractors.
~~~~

### 2a08e42 — U3

~~~~
REPORT
sha 2a08e42 (parent 6f05e4e). 1 PASS: this is mission 17 U3, "Architect mode and doctor". It claims DESIGN §33 (REVIEW-16 should-fix 2, 3, 4), plus §32, §31 and §30.
2 PASS: with the parent's product and docs files restored, the 3 changed test files gave 86 FAILED (85 of the 95 new cases, plus the changed docs pin). At the commit they gave 1969 passed. 10 new cases stay green either way, e.g. `test_architect_cp_and_mv_run_on_a_kits_tree_without_a_symlink`; these only add coverage.
3 PASS: `./scripts/check` ran once, clean tree: "3879 passed in 274.24s (0:04:34)", last line "check: green".
4 PASS with holes: DESIGN.md and meta/ are untouched, the body lists all 7 files, and the reviewer's probes are tests. The guard refused every cp/mv spelling I tried (list in NOTE 2). Two claims are wrong on disk (SF-1, SF-2).
SHOULD-FIX 1: a link planted inside a directory with mode 0111 under kits is invisible to the guard's and doctor's `os.walk`. `cp -r kits/d/h kits/ && cp kits/pay/h kits/` exits 0, and under real bash it overwrote the guard. Doctor gives ok and prints "no symlink under it".
SHOULD-FIX 2: doctor never reads the settings' `env`. With settings.local.json setting `HANDS_ROLE`, `HANDS_KITS`, `PATH`, `PYTHONPATH` or `CLAUDE_PROJECT_DIR`, both rows are ok and still print "every write confined to HANDS_KITS=<kits>". Those values make the guard let `hands approve 1` through, allow a Write to .claude/settings.json, or exit 1.
SHOULD-FIX 3: doctor does not judge the extra keys on the guard's hook. `"async": true` and `"timeout": 0.001` both pass both rows. Whether these stop the guard from blocking inside Claude Code was not run.
SHOULD-FIX 4: "self-test green" only means exit 0 (doctor.py:797). The driver row passes when the guard is replaced by `import sys; sys.exit(0)`, and when the command names a different absolute `/…/.claude/hooks/bash_guard.py` that exits 0. §33 says a different command fails the row. The rule is older than this commit.
NOTE 1: a hardlink planted under kits lets `cp` and `--write` rewrite the guard (the builder listed hardlinks as not proven). A symlinked parent of HANDS_KITS is harmless. The builder's "95 cases, 85 red" count checks out.
NOTE 2: the guard refused `-t`, `--target-directory=`, `-T`, `--no-dereference`, `-P`, `-a`, `-s`, `-l`, `..` paths, `ln -s … && cp`, `mkdir; ln -s`, `ln`, `tee`, `>`, `install`, `unzip`, `tar`, `rsync` and `touch`. Doctor fails the row for `.*`, `Bash|Edit`, hooks under PostToolUse only, an extra argument, a different script, and `disableAllHooks:"true"`. It lets `"hooks":{}`, `PreToolUse:[]`, defaultMode `dontAsk`/`plan`/`BypassPermissions` and `Write(/home/**)` pass.
NOT PROVEN: Claude Code applying settings `env`, `async` or `timeout` to hooks; how it merges `hooks:{}`; a real Claude session; the gap between the guard's decision and the command running.

EVIDENCE
SF-1. The walk is at driver/hooks/bash_guard.py:549 (`kits_symlink`) and src/hands/doctor.py:747 (`_kits_line`). `os.walk` skips a directory it cannot list and raises no error.
Setup: an architect directory with the guard at .claude/hooks/, `kits/pay/h` = "# NEUTERED", `kits/d/h -> ../.claude/hooks/bash_guard.py`, then `chmod 0111 kits/d`. The hook was fed as tests/test_bash_guard.py feeds it: HANDS_ROLE=architect, HANDS_KITS=<cwd>/kits, HANDS_CLONE=<cwd>/repo. When the hook exited 0, the command ran under `bash -c`.
== planted link in an execute-only dir kits/d (mode 0111), one command line
   exit 0  'cp -r kits/d/h kits/ && cp kits/pay/h kits/'
   guard file changed: True
== same, two separate calls
   exit 0  'cp -r kits/d/h kits/'
   exit 2  'cp kits/pay/h kits/'  bash_guard blocked this command (`cp` is refused while anything under HANDS_KITS is a symlink ('…/kits/h') …
   guard file changed: False
Doctor on the same tree (architect_dir, fake mode):
XONLY 0 ok
kits <tmp>/hands-architect/kits
verified: kits realpath <tmp>/hands-architect/kits, not a symlink, and no symlink under it

SF-2. Doctor reads no `env` key anywhere: `_load_settings` at doctor.py:826, `_pretooluse` at 851, and the "guard mode" line at 695.
Input: settings.local.json `{"env": {"HANDS_KITS": "<cwd>", "HANDS_ROLE": ""}}`.
ENV 0 ok
…
guard mode: architect mode (HANDS_ROLE=architect in every architect-role job's environment; §31), and every write confined to HANDS_KITS=<tmp>/hands-architect/kits
verified: settings read …/.claude/settings.json, …/.claude/settings.local.json
Every env shape (`HANDS_ROLE:""`, `HANDS_KITS:"/"`, `PATH:<fakebin>`, `PYTHONPATH:<dir with sitecustomize>`, `CLAUDE_PROJECT_DIR`) gave `ok` on both the driver and architect rows.
The shipped guard run under `env -i` with those values:
HANDS_KITS=<cwd>, --write <cwd>/.claude/settings.json      -> exit 0   (HANDS_KITS=<cwd>/kits: exit 2)
HANDS_ROLE= (empty), Bash 'hands approve 1'                -> exit 0   (HANDS_ROLE=architect: exit 2)
PYTHONPATH=site, Bash 'git -C repo push origin HEAD'       -> "Fatal Python error: init_import_site…"  exit 1  (only exit 2 blocks)

SF-3. `_not_a_command_hook` (doctor.py:998-1004) checks only `type` and `command`. The driver's shipped settings.json with `"async": true, "timeout": 0.001` added to the guard hook gave `ASYNC 0 ok`. The same happened on the architect row, with the keys on both hooks.

SF-4. doctor.py:797 is `if probe is not None and probe.code == 0 and not probe.timed_out:`.
With `.claude/hooks/bash_guard.py` replaced by `import sys; sys.exit(0)`:
EXIT0 0 ok
guard <tmp>/hands-driver/.claude/hooks/bash_guard.py
self-test green in role mode (HANDS_ROLE=driver)
The driver's settings.json command `python3 /tmp/r17/2a08e42-probe/evil/.claude/hooks/bash_guard.py`, a file that exits 0, also gave `driver ok`. The architect row fails that one only because its two hooks then name different files.
~~~~

### c6380ab — U4

~~~~
REPORT (≤12 lines)
sha c6380ab. 1 PASS: this is mission 17 U4, "Prompt and notifications". It implements DESIGN §33 (with §32, §11 and §26) and closes REVIEW-16 should-fix 6 and 7.
2 PASS: with the parent's src/ and docs/ restored, 12 of the 34 selected tests fail (22 pass): 8 playbook, 3 start shapes (two publishes each), 1 bound test (TypeError on `start_fold_s`). The docs test fails when only docs are restored. Tests that pass either way (coverage only): all-done, none, the 5 "True" first-line cases, and the renamed old milestone test.
3 PASS: `./scripts/check` gives "3897 passed in 281.29s (0:04:41)" and ends "check: green".
4 PARTIAL: the body lists all 9 files, and DESIGN.md and meta/ are untouched. The heading rule and the one-publish shapes hold. Two claims about the fold window do not hold (candidates below).
BLOCKER candidate: a job held inside the fold window (up to 5 s after a start that re-admits queued jobs) never gets a notification with Approve/Deny buttons. §24 says "a held-job notification carries Approve/Deny action buttons" and §26 says "The held notification carries the buttons". No finding covers this. It is disclosed in the body and in FINAL-REPORT §3.7, and the folded line says nothing about how to decide the job.
SHOULD-FIX candidate: a stop inside the window drops the start notification and every notification folded into it, including "the pipeline stopped". The parent delivered both. This contradicts the body's "named, never dropped" and "publishes the start notification at once"; §3.7 only says "may not deliver".
NOTE: on the real meta/ROADMAP.md the prompt names M4 ("— mission 8.", not marked DONE). That is right by the rule, but the milestone is 9 missions old. Once M4 is marked, the prompt names M4b, so should-fix 6 is fixed.
NOTE: shapes the rule misreads. Read as not done: "(DONE)", lower-case "done"/"Done", "**DONE**", and a DONE on the heading's second line (M4c's real heading wraps). Read as done: "NOT DONE" inside the bold title, "— DONE-criteria", "— mission 15 is not finished, DONE only in part". "UNDONE" and "— NOT DONE" are read correctly.
NOTE: a queued job that ends after 5 s gets its own second notification (probe: start at 5.02 s, stop at 5.45 s). This is the designed bound. With a queued real job, every restart's start notification now arrives about 5 s late.
NOT PROVEN: the 5 s bound under a real claude or a real ntfy; a kit apply held inside the window; phone `status` answers, which bypass the hold.

EVIDENCE
Scratch test in the worktree (since deleted), using a real Daemon via `phone_drive` and `queued_at_start` from tests/test_phone.py. `TimedRecorder` is a Recorder that logs the time of each call, waits a set latency, then records the delivery. `uv run pytest -o addopts="" -q -s tests/test_zz_probe_c6380ab.py`:

- **Probe A: hold inside the window (the BLOCKER candidate).** A queued builder job runs `FAKE:sleep 3\nFAKE:result ok`; at 0.3 s the probe calls `held()` (an aux job gated "phone test").
  [A] held job 0mu4wm8bl-rlup held at 0.42
  [A] called: [(3.2, 'hands: handsd started')]
  [A] delivered t=3.2 title='hands: handsd started' actions=False
  [A]   message='demo on …/handsd.sock\nWhile starting, handsd raised 2 more notification(s):\nhands: a job is held for a human: phone test\nrole: aux\njob: 0mu4wm8bl-rlup\nhands: the pipeline stopped: job.held: …'
  - Code: src/hands/daemon.py:257-262 and 285-300 (`_publish_start`) and src/hands/notify.py:257-258, where a held note's `actions` are kept and then dropped in the message.
  - The "decide with `hands approve`" text is built only for jobs still held when the start began: daemon.py:264-271.

- **Probe B2: stop inside the window (the SHOULD-FIX candidate).** A queued aux job runs `FAKE:exit 1` and a queued builder job runs `FAKE:block`. Each publish takes 0.5 s, and the daemon is stopped at 1.0 s.
  (at c6380ab)
  [B2] pipeline at stop: aux.failed: the playbook has no rule for it, …
  [B2] called: [(1.03, 'hands: handsd started')]
  (parent's daemon.py)
  [B2] called: [(0.02, 'hands: handsd started'), (0.18, 'hands: the pipeline stopped')]
  [B2] delivered t=0.52 title='hands: handsd started' actions=False
  [B2] delivered t=0.68 title='hands: the pipeline stopped' actions=False
  - Same setup with `FAKE:block` alone and a 0.5 s publish: `called: [(0.51, 'hands: handsd started')]` and nothing delivered. With an instant publish it was delivered at 0.52.
  - Cause: `stop()` publishes the start notification at daemon.py:385-389, then `notifier.cancel_all()` at daemon.py:431 cancels the delivery still in flight.

- **Probe C: a job ending after the window (NOTE).** A queued builder job runs `FAKE:sleep 5.3\nFAKE:exit 1` with the default window.
  [C] called: [(5.02, 'hands: handsd started'), (5.45, 'hands: the pipeline stopped')]

- **Heading rule (NOTEs).** `uv run python` calling `_heading_done` and `next_milestone` (src/hands/playbook.py:229-235, 692-707):
  False '- **M4c** — the architect role (DONE)'
  False '- **M4c The architect** — done 2026-09-18'
  True '- **M4c The architect NOT DONE** — mission 15'
  True '- **M4c The architect** — mission 15 is not finished, DONE only in part'
  True '- **M4c The architect** — DONE-criteria below'
  False '- **M4c** — **DONE** 2026-09-18'
  False '- **M4c The architect** — UNDONE'
  wrapped heading, DONE on 2nd line -> - **M4c The architect role** — missions 15 and 16 (decided 2026-09-15;
  real: - **M4 Detectors and the phone channel** — mission 8. Harness-killed
  real, M4 marked: - **M4b The closed loop** — mission 10 DONE 2026-09-13 (go, kit transport,
~~~~

### de17a7e — U5

~~~~
REPORT (≤12 lines): sha de17a7e
1. Pass. The unit is mission 17 U5, `reply` on the command channel. It claims §33 (first two "talking to the architect" bullets), plus §26, §31/§32 (H-032, `kit_file`), §6 and §11. The body lists all 12 changed files, and none of them is DESIGN.md or anything in meta/.
2. Pass. With the parent's 9 non-test files restored, `tests/test_phone.py` fails at import (it needs `ARCHITECT_TITLE`). With that import patched: `12 failed, 474 passed`. Restored: `486 passed`. Every new or changed test goes red, so none is coverage-only.
3. Pass. `./scripts/check` on a clean tree: `3908 passed in 318.48s (0:05:18)`, final line `check: green`.
4. Pass. What the body and FINAL-REPORT-17 claim for U5 matches the disk.
   - **Escalation line:** the claimed test is real (`tests/test_playbook.py:5049-5083`). It asserts the escalating job's `session_id` and `f"claude --resume {session}"` in the stop notification (`playbook.py:_resume_line`). That test is from mission 16, not this commit.
   - **Last session:** after consultations sess-A then sess-B, a reply resumes sess-B.
   - **No bypass by the architect's answer:** a reply answering `VERDICT: next kit evil-kit` leaves `kit_wait()` None and the pipeline unpaused, a later `kit_file` is refused, and the consult count is unchanged.
   - **Socket clients:** `Api.method("reply_architect")` is None. `send` with `reply:true` gets -32602 (unexpected keyword). `send` with role architect and `origin:"phone"` gets H-032's refusal.
   - **Secret:** compared with `hmac.compare_digest`. At DEBUG level, neither the secret nor the reply text appears in the log.
   - **Gate:** a gated reply is held with `origin: phone`, and a second reply is then refused ("job held").
- NOTE: "verbatim" stops at the separator. Leading spaces, leading newlines and a leading NBSP of the text are stripped (`phone.py` `_REPLY_RE` `\s+`). Inner and trailing whitespace, CRLF, unicode, a 200 KB text and command-word texts (`approve …`, `reply <secret> …`, `go`) are all stored exactly. The commit body documents this choice.
- NOTE: the design says refuse while a consultation is "running". The code also refuses while any architect job is queued or held, and during a `next kit` wait. That is stricter and matches "one job per turn".
- NOTE: a gated reply puts its text in the "a job is held for a human" notification on ntfy_topic, as any held job does. If a human denies a held reply, nothing is published under title `architect`. This is partly admitted in the commit's NOT PROVEN.
- NOT PROVEN: a real ntfy server, phone or `claude --resume`; whether a real resume keeps the same session id; a reply cancelled while queued, or orphaned by a daemon restart, publishing nothing; that a gated reply has no side effects under a loaded playbook's `job.held` rule (I only probed with no playbook loaded).

EVIDENCE: no BLOCKER or SHOULD-FIX candidates, so none is required. For the verbatim note, the probe was a throwaway pytest in the worktree (since deleted) that sent `reply <SECRET> <t>` through the fake stream and compared `spool.load_job(id).prompt` with `t`. Its output:
VERBATIM '   leading spaces kept?' DIFF got='leading spaces kept?' done
VERBATIM '\n\nleading newlines kept?' DIFF got='leading newlines kept?' done
VERBATIM '\xa0starts with nbsp' DIFF got='starts with nbsp' done
VERBATIM 'trailing  \n\n  ' EQUAL done
VERBATIM 'line1\r\nline2\r\n' EQUAL done
~~~~

### 4775880 — U6

~~~~
REPORT
- **sha 4775880.** Unit: mission 17 U6, self-hosted ntfy. It claims DESIGN §33 (third bullet), plus §11, §13, §21, §24 and §26.
- **1. Unit and sections: pass.** The commit body names the unit and the sections, and lists all 9 changed files. It changes no DESIGN.md, meta/plan.md or meta/CHECKPOINT.md.
- **2. Test-first: pass.** I put back the parent's src/, docs and README and ran tests/test_ntfy_token.py and tests/test_config.py: `25 failed, 173 passed`. With the commit's files back, everything passes. Three new tests pass either way, so they are only coverage: the `[no_token]` notification test, `notify_test_without_the_token_prints_the_401_and_exits_1`, and the `[no_token]` command-channel test.
- **3. `./scripts/check`: pass.** `3935 passed in 320.10s (0:05:20)`; the last line is `check: green`.
- **4. Design conformance: pass.**
  - All outbound HTTP in src/ goes through three functions: `http_post`, `http_stream` and `fetch_kit`. Every caller passes the token: Notifier `_publish` (which covers `answer`, `deliver` and the crash path), `send_test`, the phone `cmd_topic` stream (the token is re-read on each reconnect), and WhoPusher publish and subscribe. `fetch_kit` gets it only for URLs on `ntfy_url`'s own origin. There is no curl in systemd/ or templates.
  - Redirects are not followed.
  - I found the token in no repr, doctor output, httpx error text or role job env.
  - The report's claims match the disk.
- **SHOULD-FIX candidate:** a token set with the default `ntfy_url` loads silently. The bearer and all free text then go to https://ntfy.sh, and doctor still says `ntfy token on` with status ok, with no warning. §33's "never crosses a public broker once this is set" can look true when it is not. Refusing would be wrong, because ntfy.sh accounts do use tokens; a warning, or naming the host on that doctor line, would fix it.
- **NOTE:** H-037 (Approve/Deny buttons carry no token) is rightly a finding, not a design violation. §33 only says the bearer goes on publish and subscribe. Putting it in a button's headers would put the token in every held notification and in the server's cache, and that is the architect's call. The typed-command fallback is documented.
- **NOTE:** The docs' server steps look right from what I know of ntfy (not run): binwiloo/ntfy `serve`, `auth-file`, `auth-default-access: "deny-all"`, `attachment-cache-dir` with `base-url`, `ntfy user add`, `ntfy access hands 'hands-*' read-write`, `ntfy token add` (needs ntfy 2.0 or later).
- **NOTE:** `attachment_token` checks scheme, host and port only. With `ntfy_url` = `https://h/ntfy`, any path on host h gets the token. That is the same server, so this is acceptable.
- **NOT PROVEN:** no real ntfy server, container, Tailscale tunnel or phone app. Unknown: whether a real ntfy asks for auth on `/file/` downloads, whether the app signs in with a token, and whether it adds its sign-in to a button's request.

EVIDENCE
SHOULD-FIX (token with the default public URL). This probe ran as a temporary test file in the worktree and has been deleted. The config was `[notify]` with `ntfy_topic = "hands-x"` and `ntfy_token = "tk_U6selfhostedBearer0123456789ab"`, and no `ntfy_url`. The probe loaded it, called `send_test(cfg, "m", post=recorder)`, then ran `hands --json doctor` with `HANDS_DOCTOR_FAKE=1`. Output:
url https://ntfy.sh https://ntfy.sh token set True
send_test -> {'topic': 'hands-x', 'url': 'https://ntfy.sh/hands-x', ..., 'status': 200, 'delivered': True} [('https://ntfy.sh/hands-x', True)]
config ok | .../demo.toml — project demo; roles aux, builder; socket .../handsd.sock; ntfy topic set
notifications ok | notifications on: ... / ntfy token on: [notify] ntfy_token is sent as a bearer on every publish and subscription (handsd, handswho, `hands notify --test`) (§33)
TOKEN in doctor: False
repr has token: False
Code: `src/hands/config.py:73` sets `DEFAULT_NTFY_URL = "https://ntfy.sh"`; `src/hands/config.py:549-552` resolves the URL and never checks it against the token; `src/hands/doctor.py` `_token_line` checks only whether the token is set.

Supporting probe, redirects: server A answers 302 to server B, and I called `http_post`, `http_stream` and `fetch_kit` against A with the token.
post status 302 A saw [('POST', '/t', 'Bearer tk_U6selfhostedBearer0123456789ab')] B saw []
stream exc HTTPStatusError False
fetch exc _KitRefused False
B saw after all []
The token never reached B and never appeared in exception text. httpx is 0.28.1, which does not follow redirects by default.

Supporting probe, `attachment_token` edge cases:
- Token sent: `https://NTFY.example` and `https://ntfy.example:443`.
- No token: `http://` (scheme downgrade), `ntfy.example@evil.example`, `evil.example/https://ntfy.example/`, `ntfy.example.evil.example`, `xn--ntfy-9ra.example`, `ntfy.example\@evil.example`.
~~~~

### 63ac5c3 — U7

~~~~
REPORT
- sha 63ac5c3, "playbook: kickoff names BUILDER-18". The main checkout was not modified. The worktree and all /tmp/r17/63ac5c3-* scratch files have been removed.
- 1 Unit/sections: PASS. It is mission 17 U7 (this repository's playbook) and claims DESIGN v3.16 §26 ([series] kickoff; kit check) and §33. The diff is exactly PLAYBOOK.toml (1 line) and tests/test_playbook.py (2 lines), and the body lists both.
- 2 Test-first: PASS. In a scratch clone with the parent's PLAYBOOK.toml *committed*, tests/test_playbook.py gives `1 failed, 348 passed`: only the kickoff test fails, and it fails on the value (`- Read meta/BUILDER-18-PROMPT.m / + Read meta/BUILDER-17-PROMPT.m`). At the commit it gives `349 passed`. Reverting the file without committing gives the uninformative red the body warned about: 6 tests fail with `PlaybookNotCommitted` (§10). The unit adds no new tests, so none is coverage-only.
- 3 `./scripts/check`: PASS, `3935 passed in 317.86s (0:05:17)`; final line `check: green`, exit 0.
- 4 Design conformance: PASS. The kickoff is byte-equal to the shape of BUILDER-17-PROMPT.md's "Kickoff line" with 18 for 17, which follows §27's Conventions. It is the exact prompt that phone `go` and the engine send (phone.py:394, playbook.py:1673), and §28 anchors `max_consults` on every kickoff value seen, so renaming it is safe. No DESIGN.md, meta/plan.md or meta/CHECKPOINT.md was touched.
  - Loads gate: `load_playbook` gives `hands-missions`, the BUILDER-18 kickoff, `phone`, `False`, 20 rules, exit 0.
  - Kit check gate: a zip holding only meta/BUILDER-17-PROMPT.md, checked with `--repo .`, passes 6 of 6 and exits 0. This holds with an empty HOME, with the real HOME, and as a directory kit.
- NOTE: the gate is weak, as FINAL-REPORT §3.8 admits. The same zip checked against the 4775880 tree and code also passes 6 of 6 and exits 0, because the kit carries no playbook and the kickoff is never compared.
- NOTE: a stronger probe shows the new value is correct. A kit carrying the new PLAYBOOK.toml plus a BUILDER-18 brief made by replacing 17 with 18 in BUILDER-17-PROMPT.md passes (exit 0). The old playbook with that brief fails (exit 1, kickoff mismatch), and so does the new playbook with the BUILDER-17 brief.
- NOTE, checks on 011899e (all consistent):
  - Every §1 sha and subject matches `git log`. Every pass count matches the tests collected at that sha: 3743, 3747, 3761, 3784, 3879, 3897, 3908, 3935, 3935. The U2 and U6 counts appear only in the journal, not in their commit bodies.
  - The Review items table covers REVIEW-16 blockers 1–2 and should-fix 1–8.
  - §3 NOT PROVEN includes a real `reply` round trip (§3.1) and a real self-hosted ntfy (§3.2).
  - The FINDINGS.md diff removes only the two `Status: open` lines; everything else is added.
  - H-035 and H-036 are marked resolved, and their code lines match the disk (api.py:408, spool.py:135/868, kit.py:461/539/1251/361/379, `deny_from_playbook` not in COMMANDS). One small inexactness: `orig_filename` is also read at kit.py:426 in `_names_problem`, a helper of the judge, not only in `_zip_entries` itself.
- NOT PROVEN:
  - The gate does not tell the new value from the old one.
  - meta/BUILDER-18-PROMPT.md does not exist, so a phone `go` would point the builder at a missing file.
  - No real daemon, phone `go`, or engine kickoff-after-apply ran with this file.
  - Doctor's `go` warning was not re-run.

EVIDENCE: no BLOCKER or SHOULD-FIX candidates, so no probes are required. For the NOTE on the weak gate: running `hands kit check <zip of meta/BUILDER-17-PROMPT.md> --repo .` on the 4775880 tree with its own src (PYTHONPATH=src, empty HOME) printed `PASS playbook: the kit carries no playbook; the repo's PLAYBOOK.toml is in force (loads, no quiet_hours; its kickoff is not compared, §26 compares a kit's)` … `kit check: pass (6 of 6 checks)`, exit=0.
~~~~
