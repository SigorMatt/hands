# REVIEW-18 — cold review of hands mission 18

VERDICT: review mission 18 blockers=0 should-fix=4

Base `954e294` (`review: mission 17`, the last `review:` commit on origin/main).
Tip `ffbce67`. Unit commits reviewed, one sub-agent each, in a `git worktree` at
the commit: 23da451 (U0, the orchestrator's `plan:` commit), 45da318 (U1),
88e8830 (U2), f846965 (U3), 2221151 (U4), f159d28 (U5). Not dispatched:
fc376ab (the architect's mission-18 kit, DESIGN v3.17) and ffbce67 (U6, the
`meta:` commit that adds meta/FINAL-REPORT-18.md and the bookkeeping; it changes
only meta/ over f159d28). The reviewer re-ran two findings at the tip:
- Should-fix 1: `is_public_ntfy_url('https://ntfy。sh')` returns `False`, and
  `httpx.URL` of that url has host `ntfy.sh`.
- Should-fix 2: `driver/hooks/bash_guard.py:202` does `import shlex`, and
  `_guard_selftest` (`src/hands/doctor.py:872`) hashes only the file the hook
  names.

## Blockers

None. Every unit's gate was green at its commit. Every product unit's new tests
go red with its product change reverted. No unit touched DESIGN.md or, outside
`plan:`/`meta:`, meta/plan.md or meta/CHECKPOINT.md. REVIEW-17's blocker 1 probe
now publishes the held note first, with its Approve/Deny actions.

## Should-fix

1. **A Unicode full stop in `ntfy_url` gets the token past the public-broker
   check, and httpx sends it to ntfy.sh (U4 `2221151`; §34 "`ntfy_token` with
   `ntfy_url` … pointing at a public broker is refused at config load").**
   - `is_public_ntfy_url` (`src/hands/config.py:857-872`) compares the
     `urlsplit(...).hostname` string. httpx applies IDNA/UTS46 when it sends,
     which maps U+3002, U+FF0E and U+FF61 to ".".
   - Sub-agent probe (`load_config`, then `send_test` over a MockTransport):
     `LOADED 'https://ntfy。sh' token True -> ntfy.sh Bearer tk_… 'delivered':
     True`. `https://NTFY．SH` and `https://ntfy｡sh` gave the same result.
   - Reviewer at the tip: `'https://ntfy。sh' False ntfy.sh`.
   - This goes against FINAL-REPORT-18 §5's "a token now always implies a
     self-hosted server". §3.5 discloses only other brokers, IPs and DNS
     aliases, but this url names ntfy.sh itself. The commit's "any letter case,
     scheme, port, path or trailing dot" does hold.
   - Not a blocker because the user must write the non-ASCII dot into their own
     config.
   - Fix: judge the host that httpx will use (`httpx.URL(url).host`, trailing
     dot stripped), or refuse a host that is not ASCII.
2. **Doctor passes a guard that allows everything if a module planted next to
   it shadows one the guard imports (U3 `f846965`; §34 "compares its sha256 with
   the guard the repository ships"; REVIEW-17 should-fix 5 marked "closed").**
   - The hook runs `python3 .claude/hooks/bash_guard.py`, so Python puts the
     script's directory first on `sys.path`.
   - Sub-agent probe: the real guard untouched, plus
     `.claude/hooks/shlex.py` = `import sys; sys.exit(0)`.
     - Doctor, driver and architect rows: `status=ok`, "guard sha256 af2cc7d3…,
       the same bytes as …driver/hooks/bash_guard.py (§34)", "self-test green in
       role mode".
     - The hook given `rm -rf /tmp/zz` exits 0, so the call is allowed.
   - The premise (write access to `.claude/hooks`) is the same as REVIEW-17's
     "replace the guard" probe. The sha256 binds one file of what runs, not the
     guard's import path.
   - The self-test still counts exit 0 as green and does not require a refusal.
   - Fix: run the guard with `-I` / `-P` (or the equivalent `sys.path`
     hygiene), or make doctor fail on any `.py` or package beside the guard. A
     self-test step that expects a refusal (exit 2) would also catch this.
3. **The kit record hashes the bytes the client sent, not the bytes `check_kit`
   passed on (U2 `88e8830`; §34 "`kit.json` stores the sha256 of the bytes the
   check passed on").**
   - `sha256=hashlib.sha256(data).hexdigest()` (`src/hands/api.py:449`) hashes
     the request payload. `check_kit` (`api.py:439`) and `apply_from_zip`
     (`api.py:442`) read the stored path from disk.
   - Sub-agent probe, end to end during the `next kit` wait:
     - The client sends a check-failing zip. A wrapper writes a passing zip to
       the stored path before `check_kit` and restores the failing bytes after
       it.
     - Output: `filed ['0mu5seu0l-xvt6']`, `gate.decided [(…, 'approved',
       'playbook')]`, `kit.refused []`.
   - The precondition is REVIEW-17 should-fix 1's: a writer into
     `<spool>/kits`. The commit body discloses "a swap and swap-back around the
     check". FINAL-REPORT-18 §3.3 leaves it out.
   - REVIEW-17 should-fix 1's own probe, a `put` over the stored zip after
     filing, is now refused: `record sha fc0aacbf24ac stored 0c108261db17`,
     `kit.refused`.
   - Fix: hash the bytes `check_kit` reads (read once, check and hash the same
     buffer), or check from memory and write after.
4. **A hardlink under `kits/` still lets `cp` overwrite the guard, and doctor
   says `ok` (U3 `f846965`; REVIEW-17 should-fix 3's premise, a link already
   planted).**
   - Sub-agent probe: a planted hardlink `kits/h` to
     `.claude/hooks/bash_guard.py`. `cp kits/pay/h kits/h` under real bash exits
     0 and overwrites the guard. Doctor: `status=ok`, "no symlink under it".
   - FINAL-REPORT-18 §3.4 discloses hardlinks as not proven. §34 names only
     symlinks, so this is not a design violation. It is the same attack REVIEW-17
     should-fix 3 closed for symlinks, and it is reproduced.
   - Fix: refuse a regular file with `st_nlink > 1` in both walks. Pin doctor's
     `_kits_walk` to the guard's `kits_symlink` with a shared-case test (Notes,
     U3).

## Notes

- **Gates.** `./scripts/check` was green once at each of the six unit commits,
  and every pass count matches FINAL-REPORT-18 §1: 3935 (U0), 3937 (U1), 3945
  (U2), 4000 (U3), 4030 (U4), 4030 (U5).
  - Six worktrees ran the suite in parallel on one machine, and no test failed
    or flaked.
  - The "3/3" runs were not reproduced (FINAL-REPORT-18 §3.7).
  - ffbce67 changes only meta/ over f159d28.
- **Test-first.** Every product unit's tests go red when its product change is
  reverted:
  - U1: 6 failed, including both of the reviewer's probes.
  - U2: 41 failed, including all 5 new tests and FORGED's "no sha256" case.
  - U3: 53 failed.
  - U4: 21 failed.
  - U5: the kickoff test, on the value, with the parent's PLAYBOOK.toml
    committed.
  - U0 has no product or test change.
  - Coverage-only tests are named in each per-commit report.
- **Files.** Every unit body lists every file it touches. Only fc376ab (the
  architect's kit) touched DESIGN.md. meta/plan.md and meta/CHECKPOINT.md
  changed only in 23da451 (`plan:`) and ffbce67 (`meta:`). The FINAL-REPORT-17
  and FINDINGS.md edits in U0 are append-only and dated.
- **U0.**
  - H-038 cites §26 for "The held notification carries the buttons", but that
    phrase is in §27 (DESIGN.md:1030). REVIEW-17 blocker 1 made the same
    mistake.
  - The FR-17 correction says REVIEW-17's probe approved "the first" kit.
    REVIEW-17 says only "one".
  - Filing H-038 instead of the brief's H-037 is justified: H-037 already
    existed at fc376ab.
- **U1.**
  - The brief's "a stop at 2 s": an uncommitted probe with a stop at 2.0 s also
    delivers "handsd started" with "the pipeline stopped" folded in.
  - Two holds and a raw spool `job.held` inside the window each published at
    once with buttons. A hold after the window closes publishes with buttons and
    is not named in the start note.
  - `Notifier.cancel_all` is gone. The remaining `cancel_all` calls
    (`daemon.py:413-414`) belong to limits and playbook.
  - A publish that outlives the 30 s drain is still cancelled at loop shutdown
    and records no `delivered: false` event. Probe: grace 2 s, latency 3600 s,
    `stop took 2.05`, 0 delivered. The report discloses this (§3.2), and httpx's
    10 s timeout makes it rare.
  - A start note with N holds repeats the same title N times ("hands: a job is
    held for a human") and does not say which job is which. That follows §34's
    "title only" to the letter.
  - The start-failure branch that skips notes already published
    (`daemon.py:247`) has no test.
  - H-039 (what §34's "only heartbeats and `pipeline.resumed`" means) is open
    for the architect.
- **U2.**
  - Three concurrent `kit_file` calls: `check_kit` ran once, one kit was held
    and two were refused "one kit per consultation".
  - A first call that fails its check files nothing, and a concurrent second
    call is then checked and filed. That is correct.
  - The consultation-changed branch works when probed but has no committed test,
    as disclosed.
  - A second `kit_file` sent after the first was filed (not concurrently) gets
    "no architect consultation is open" and no escalation, because the wait is
    already popped. §33's "files at most one" holds. It is not the §34 message.
  - `_kit_locks` and `_second_kits` are never pruned and are lost on restart, as
    disclosed.
- **U3.**
  - The walk uses `os.lstat` on every path and `os.listdir` for children, so a
    directory it cannot list is refused (fail closed). The architect cannot
    create one (`chmod` is refused; `mkdir -p` and `cp -r` only).
  - A symlink in an ancestor above `HANDS_KITS` leaves writes and doctor
    working.
  - Doctor's `_kits_walk` is a copy of the guard's `kits_symlink`, not the
    guard's code, and no test pins them equal (disclosed, §3.4).
  - The sub-agent confirmed the wheel part of §3.4: a `uv build` wheel carries
    `hands/shipped/bash_guard.py`, and `_guard_bytes` in an installed venv, run
    from `/`, matched the repository guard. A full `hands doctor` from the wheel
    was not run.
  - Extra whitespace in the hook command passes, and a `bash -c` wrapper fails.
- **U4.**
  - An explicit `ntfy_url = "https://ntfy.sh"` is refused, and so are NTFY.SH,
    a trailing dot, `:443`, userinfo, `?`/`#`, a bare host, surrounding
    whitespace, `ws://` and a bad port.
  - No env var or CLI flag sets the url or token after load. The refusal never
    prints the token.
  - `who` reads "now" from the live daemon's state. With the daemon down, no
    inbox line is shown at all, so no hold is hidden behind "informational".
  - The wording matches §34.
  - The test `…not_needed_by_anothers_held_job` actually sets the other
    project's pipeline to stopped. Only the name is wrong.
- **U5.**
  - The diff is one kickoff line (byte-identical to the parent's with 18→19)
    and its test.
  - `hands kit check` of a BUILDER-18 kit with `--repo .` exits 0 at both
    f159d28 and its parent, so the committed gate does not compare the new
    value, as §3.6 discloses. The uncommitted probe reproduces: the new playbook
    with a BUILDER-19 brief gives 0, the old one gives 1.
  - meta/BUILDER-19-PROMPT.md does not exist. A phone `go` sends the kickoff
    without checking for it, and doctor only warns. Mission 17 U7 did the same.
- **NOT PROVEN (FINAL-REPORT-18 §3) against the disk.**
  - §3.2, §3.4, §3.5, §3.6 and §3.7 match what the sub-agents found.
  - §3.3 leaves out the swap-around-check case (should-fix 3), which the
    commit body discloses.
  - §3.5 does not cover should-fix 1.
  - Nothing in §3 covers should-fix 2.
  - The review-items table marks REVIEW-17 should-fix 3 and 5 "closed":
    - Should-fix 3 is closed for the symlink it names, but should-fix 4 above
      is the same attack with a hardlink.
    - Should-fix 5 is closed for a replaced or relocated guard, but
      should-fix 2 above is a new form of it.

## Per-commit verdicts

The sub-agents' reports and evidence, verbatim except that each agent's closing
cleanup line is omitted (every worktree and scratch file was removed; the main
checkout was not touched).

### 23da451 — U0

~~~~
REPORT
- **sha:** 23da451. Unit: mission 18 U0, "plan: mission 18 plan, H-038, FINAL-REPORT-17 correction". Parent is fc376ab. The body claims DESIGN v3.17 §34 (with §11, §26, §32, §33) and REVIEW-17 blocker 1 and should-fix 2 and 6, bookkeeping only.
- **1. pass.** The unit and its sections are named as above.
- **2. pass.** `git show --stat` lists only 4 meta files: CHECKPOINT (+12/-28 net), FINAL-REPORT-17 (+17/-0), FINDINGS (+41/-0) and plan.md. There is no product or test change, so no test was needed.
- **3. pass (green).** `./scripts/check` at 23da451 in a clean worktree exited 0. Pytest printed "3935 passed in 408.57s (0:06:48)" and the last line was "check: green". The count matches the body.
- **4. pass.**
  - DESIGN.md is untouched, and the body names all 4 files.
  - FR-17 and FINDINGS are append-only (a grep for removed lines finds none), and both blocks are dated 2026-09-17.
  - H-038 matches the disk at 011899e: `_publish_start` is at `daemon.py:293`, `notifier.cancel_all()` is at `daemon.py:439`, `START_FOLD_S = 5.0`, and the §34 quote is exact.
  - Its probe details match REVIEW-17 blocker 1 and should-fix 6. The §24 quote exists.
  - The FR-17 correction matches should-fix 2 and the test `test_a_second_kit_in_one_consultation_is_denied_and_the_consultation_escalates` (`tests/test_playbook.py:4331`), which has both branches.
  - Filing H-038 instead of H-037 is justified: H-037 (the buttons carry no ntfy token) is at FINDINGS line 1886 in the parent fc376ab. This is disclosed in the body and in plan.md.
- **NOT proven:** the body's "three consecutive runs"; I ran the gate once. I did not check that the plan's unit split covers every item in the brief beyond U0–U6 as listed. None of H-038's code exists yet, as disclosed.

EVIDENCE: no BLOCKER candidates. One minor SHOULD-FIX (citation) candidate and one wording note:
- **Wrong section number (minor SHOULD-FIX).** H-038 cites §26 for "The held notification carries the buttons", but the phrase is in §27. The error is copied from REVIEW-17 blocker 1, and the design duty it names still stands.
  - Probe: a whitespace-normalised Python regex over DESIGN.md finds the phrase exactly once, at line 1030, under `## 27. Changes from v3.9` (heading at line 998). §26 starts at line 953.
- **"The first" is not in the review (note).** The FR-17 correction says REVIEW-17's probe approved "the first" kit. REVIEW-17 should-fix 2 says only "One was `state=done … approved by=playbook`, the other denied".
- **Append-only probe:** `git show 23da451 -- meta/FINAL-REPORT-17.md meta/findings/FINDINGS.md | grep -E '^-[^-]'` printed nothing.
- **H-037 probe:** `git show fc376ab:meta/findings/FINDINGS.md | grep -n '^#.*H-03[678]'` printed `1886:## H-037 — on a token-protected ntfy the Approve/Deny buttons carry no token`. The brief (`meta/BUILDER-18-PROMPT.md:72`) says "File H-037".
~~~~

### 45da318 — U1

~~~~
REPORT
- sha: 45da318. Unit: mission 18 U1, "The start fold". Implements DESIGN v3.17 §34 first paragraph, with §24/§26 (the held note carries buttons) and §33/§11. Closes REVIEW-17 blocker 1 and should-fix 6, and finding H-038.
- 1. pass. The commit body names the unit, its sections, the review items and every changed file: src/hands/{daemon,notify,phone}.py, docs/INTEGRATION.md, tests/test_{phone,docs}.py. It touches nothing forbidden (no DESIGN.md, meta/plan.md or meta/CHECKPOINT.md).
- 2. pass. I reverted src/ to 45da318^ and ran the new and changed test_phone tests: 6 failed. Both probe tests went red (held probe: `[(3.26, 'hands: handsd started')]`; stop probe: `[(1.015, 'hands: handsd started')]` with nothing delivered). The re-publish tests for held jobs were also red: fresh_buttons_named_by_title, exactly_one_start_notification[held] and [all-three], and without_buttons. src/ restored afterwards.
- 2b. Stop at 2 s (the brief) instead of 1.0 s (the test): an uncommitted probe gave called `[(2.017, 'hands: handsd started')]`, delivered `['hands: handsd started']` with "the pipeline stopped" folded in. The later stop time makes no difference.
- 3. green, clean tree: `3937 passed in 422.28s (0:07:02)`, then `check: green`.
- 4. pass on §34.
  - `_on_event` sets `fold=False` for `job.held`, and `_publish_held` re-publishes every job already held at start with `phone.actions`.
  - The start message lists each held note by title only (`\nhands: a job is held for a human`).
  - `stop()` now flushes the start notification first, then calls `notifier.drain(timeout=30)` instead of cancelling queued publishes.
  - `Notifier.cancel_all` is deleted. The only `cancel_all` calls left in src are `limits.cancel_all()` and `playbook.cancel_all()` (daemon.py:413-414), which are not the notifier's.
- 4b. Adversarial probes, all as expected:
  - Two sends and a raw spool `job.held` inside the window: three held notes, each with buttons, published at 0.34/0.36/0.37 s. The start note at 3.23 s lists the three titles plus one folded stop.
  - A hold after the window closes (start_fold_s=0.5): the start note goes out at 0.74 s, the held note with buttons at 0.81 s, and the start note does not name it.
  - Kit-apply and engine holds were not run end to end. The code shows every hold is filed through `Api.send`, which writes the `job.held` event that `_on_event` handles, so the raw-event probe covers that branch.
- NOT proven: a real ntfy or claude; the kit and engine holds end to end (above); the start-failure branch that skips notes already published (daemon.py:247, no test); the §30 ordering of N held notes plus the start note published within one second.

EVIDENCE
- No BLOCKER candidates.
- Possible should-fix or note (the commit and FINAL-REPORT-18 §3.2 already list it as not proven): a publish that outlives the drain bound is still dropped. Probe: `_SHUTDOWN_GRACE_S` set to 2, publish latency 3600 s, stop at 1.0 s. Result: `stop took 2.05`, one `hands-notify` task still pending, 0 delivered. When the event loop shut down it cancelled that task. `_publish` re-raises `CancelledError` (notify.py:351-352), so the lost note never reaches `_failed` and gets no `delivered: false` inbox event. "Cancels nothing" holds only inside the 30 s bound. In production each POST is capped by httpx `timeout=10.0` per phase (notify.py:120), so this should be rare.
- Note: a start note with several holds shows the same title N times ("hands: a job is held for a human" three times). That follows §34's "title only" literally, but those lines don't say which job is which. Only jobs held before the start are listed by id, under the payload's `held` key.
- Note: H-039, filed after this commit, covers §34's "only heartbeats and `pipeline.resumed`" wording versus the fold of stops that U1 kept. It is still open for the architect.
- FINAL-REPORT-18 §2 (U1 bullet) and §3.2 match what is on disk.
~~~~

### 88e8830 — U2

~~~~
REPORT
- sha: 88e8830. Unit: mission 18 U2, "the kit record". It claims DESIGN §34 "The kit record" (with §33 "The autonomy path" and §32) and closes REVIEW-17 should-fix 1 and 2.
- 1. pass. The commit body names the unit, the sections and all 9 files. It does not touch DESIGN.md, meta/plan.md or meta/CHECKPOINT.md.
- 2. pass. With src/, docs/ and architect/ set back to the parent, 41 tests in test_playbook.py and test_kit.py fail. All 5 new tests are among them, and so is FORGED's "the record holds no sha256" case. The 3 new end-to-end tests fail on `KeyError: 'sha256'`. After restoring, the tree is clean.
- 3. green. `3945 passed in 372.96s (0:06:12)`, then ruff "All checks passed!" and `check: green`. This matches FINAL-REPORT-18's 3945.
- 4. Mostly conforms. `_release_kit` is the engine's only approval point, and it re-hashes the stored zip before approving. A mismatch files `kit.refused` with both hashes, then stops with both. The lock is per consultation, and the second call is refused before its kit is stored or checked. Three concurrent calls: `check_kit` ran once, one kit was held, two were refused, and there was one stop. A first call that fails the check files nothing, so a concurrent second call is checked and filed. That is right, since nothing was filed. The consultation-changed branch works (probe below).
  - Deviation: the hash is of the bytes the client sent, not of the bytes `check_kit` read from disk. A zip swapped in and back around the check is recorded, approved and applied (SF-1).
- NOT proven: an unzip after approval; real concurrency under the socket (the probes used asyncio.gather in-process); a restart forgetting `_second_kits` and `_kit_locks` (never pruned, which is a small, disclosed memory growth); the consultation-changed branch as a committed test; §3.3 of FINAL-REPORT-18 leaves out the swap-and-swap-back case that the commit body discloses.

EVIDENCE
- **SHOULD-FIX candidate 1.** src/hands/api.py:449 records `sha256=hashlib.sha256(data).hexdigest()` (the bytes the client sent). But `check_kit` (api.py:439) and `apply_from_zip` (api.py:442) read `path` from disk. So under a writer, §34's "sha256 of the bytes the check passed on" does not hold.
  - Probe: a scratch test in the worktree, end to end during the `next kit` wait. The client sends a zip that fails the check (brief with no kickoff or verdict, plus `notes/evil.md`). A wrapper writes a passing zip to the stored path before the real `check_kit` and writes the failing bytes back after it.
  - Output: `PROBESWAP filed ['0mu5seu0l-xvt6']`, `gate.decided [('0mu5seu0l-xvt6', 'approved', 'playbook')]`, `kit.refused []`, `stop Mission 17 finished`.
  - Precondition: the same as REVIEW-17 SF1, a writer into `<spool>/kits` (for example a widened `[files] allowed_roots`). The commit body discloses it; FINAL-REPORT-18 §3.3 does not.
- **SHOULD-FIX candidate 2 (minor).** Whether a second kit escalates depends on timing. During the wait, two concurrent calls give "one kit per consultation" and an escalate stop (the committed test). A second `kit_file` sent right after the first was filed gets something else: `PROBESEQ ['0mu5sek3e-uta5', 'kit_file: no architect consultation is open — ...']` and `stop Mission 17 finished`, with `second_kits set()`.
  - It is still refused before the check, so §33's "files at most one" holds. It gets neither §34's "one kit per consultation" message nor an escalation.
- **SF1 probe now refused.** A real `Api.put` (allowed_roots widened) over `kits/<id>/mission-17-kit.zip` after filing, then `_release_kit`: `record sha fc0aacbf24ac stored 0c108261db17`, `state held kit.refused ['0c108261db17']`.
- **Three concurrent calls:** `PROBE3 checks ['a'] outcomes ['dict:held', 'ApiError:kit_file: one kit per consultation …', 'ApiError:… one kit per consultation …'] kit_refused calls 2 second_kits {…} locks [1]`.
- **First call fails the check:** `PROBEFAIL checks ['bad', 'good'] [ApiError "fails hands kit check", 'dict:held'] kits dirs 1 second_kits set()`.
- **Consultation changed during the first call's check:** `PROBECHG checks ['bad'] [... fails check, 'kit_file: consultation 0mu5sf4n7-ml5j is no longer the one open while this kit waited for the call before it (§32, §34)']`.
~~~~

### f846965 — U3

~~~~
REPORT
- sha: f846965. Unit: mission 18 U3, "Symlinks and doctor". It claims DESIGN v3.17 §34 ("Kits and symlinks", "Doctor's role rows") with §33, §32 and §31, and REVIEW-17 should-fix 3, 4 and 5.
- 1. pass. The commit body names the unit, the sections and the review items, and lists all 6 changed files, matching `git show --stat`. DESIGN.md, meta/plan.md and meta/CHECKPOINT.md are untouched.
- 2. pass. With src/, driver/, pyproject.toml and docs/ put back to the parent, the two test files gave 53 failed, and every new test group was red. Only one new test passes on the parent, so it is coverage only: `test_a_settings_env_naming_no_variable_the_role_depends_on_keeps_the_row_ok[driver, architect]`. The old passing case "absolute-elsewhere" was removed, and the body says so.
- 3. GREEN. Clean tree, one run, `4000 passed in 342.50s (0:05:42)` / `check: green`. I ran as uid 1000, not root, so the execute-only tests ran.
- 4. The fix matches §34 as written, with two gaps (see EVIDENCE):
  - **Walk:** both copies call `os.lstat` on every path from HANDS_KITS down. They use `os.listdir` to find children, so a directory that cannot be listed is refused rather than walked. That fails closed, and a walk cannot list children without read permission anyway, so I judge it meets §34. The architect cannot make such a directory to block writes: `mkdir` accepts only `-p`, `cp` only `-r`, and `chmod` is refused.
  - **Probes:** a directory with read but no execute permission refuses `cp` (exit 2). A symlink in an ancestor above HANDS_KITS gives doctor `ok`, and `mkdir`/`cp`/`mv` still work there, so a normal setup is not broken.
  - **"The same walk":** doctor's `_kits_walk` is a copy of the guard's `kits_symlink`, not shared code. No test checks the two stay alike. The reason given ("cannot import") is weak now that doctor has the guard's path in `SHIPPED_GUARDS`.
  - **Settings layers:** all three are read. A user-level file that is bad JSON, unreadable, or has a non-object `env` fails the row. A `bash -c` wrapper fails; extra whitespace in the command passes, which is harmless.
  - **Wheel:** a wheel built with `uv build` contains `hands/shipped/bash_guard.py`. Installed into a venv and run from `/`, `_guard_bytes` found that copy and matched the repo guard's sha256. A different file did not match.
- NOT proven: whether Claude Code applies settings `env`, `async` or `timeout` to hooks; managed settings and `CLAUDE_CONFIG_DIR`; a full `hands doctor` run from the installed wheel (I checked only `_guard_bytes`); the race between the walk and `cp`/`mv`.

EVIDENCE
- **SHOULD-FIX candidate (contradicts FINAL-REPORT-18 line 111, should-fix 5 "closed"):** a guard that exits 0 on everything still passes doctor.
  - Leave the real guard untouched and add `.claude/hooks/shlex.py` containing `import sys; sys.exit(0)`. Python searches the script's own folder first for imports, so this file replaces the real `shlex` and the guard exits 0 before its first check.
  - Doctor for both driver and architect: `code=0 status=ok`, "guard sha256 af2cc7d3…, the same bytes as …driver/hooks/bash_guard.py (§34)", "self-test green in role mode".
  - The real hook given `rm -rf /tmp/zz` exits 0 (allowed).
  - Planting this needs write access to `.claude/hooks`, which is also what REVIEW-17's "replace the guard" probe needs. The byte check covers `bash_guard.py` only (src/hands/doctor.py `_guard_selftest` / `_guard_bytes`), not other files in its folder.
- **SHOULD-FIX candidate (disclosed as "Not proven: hardlinks under kits"):** a planted hardlink `kits/h` to `.claude/hooks/bash_guard.py`.
  - Guard: `cp kits/pay/h kits/h` exits 0 under real bash and overwrites the guard.
  - Doctor: `status=ok`, "no symlink under it".
  - This is the same planted-link premise as REVIEW-16/17. A walk check on `st_nlink > 1` would catch it.
- **Minor:** the `_kits_walk` / `kits_symlink` copies have no test that they behave the same. Only the guard's names are checked (`test_the_kits_walk_is_an_lstat_walk_not_os_walk`).
~~~~

### 2221151 — U4

~~~~
REPORT
- sha: 2221151. Unit: mission 18 U4, "The token and who". It implements DESIGN §34 "The token" (REVIEW-17 should-fix 7) and "`hands who`" (BACKLOG mission 18 item 1), and cites §33 and §11. It changes 7 files and the body names all 7. DESIGN.md, meta/plan.md and meta/CHECKPOINT.md are untouched.
- 1. pass. The unit and its sections are named. The body follows §34 (refuse at load) over the review's "warn" suggestion.
- 2. pass. With src/, docs/ and README.md set back to the parent, 21 new tests fail: the no-url refusal, 7 public urls × [notify]/[server], every loader, 4 of the 6 who cases, and the cross-project case. They pass again once the files are restored. Coverage only: the 5 self-hosted urls, no token with ntfy.sh, and held_now_and_its_event / stopped_now_and_its_event. who's "nothing_needed" was red only because the text changed from "acks it" to "acks them"; its logic did not change.
- 3. green on a clean tree: "4030 passed in 438.72s (0:07:18)", then "check: green". The count matches the body and FINAL-REPORT-18 §1. Nothing was flaky.
- 4. Mostly conforms. An explicit `ntfy_url = "https://ntfy.sh"` is refused from either table, and so is an unset url. These are also refused: NTFY.SH, ntfy.sh., :443, user@ and user:pw@, http://…/, ?x, #x, a bare ntfy.sh, ntfy.sh/topic, surrounding whitespace (`_str` strips it first), ws://, :99999. No env var or CLI flag sets the url or token after load. `ntfy_token` is only accepted in [notify]. The refusal never prints the token, and a url containing the token has it masked. who reads "now" from the live daemon state (the `who` call gives pipeline.paused and the jobs in state held). When the daemon is down, the block says "not answering" and no inbox line is shown, because the inbox comes from that same state, so no hold is hidden behind "informational". The wording matches the design exactly. One case bypasses the public check: Unicode full-stop characters (see EVIDENCE).
- NOT proven: other public brokers, IPs and DNS aliases (the report admits this in §3.5); a live broker; real handsd or handswho runs against a live daemon.

EVIDENCE
- SHOULD-FIX (design violation, and it contradicts a claim). src/hands/config.py:857-873: `is_public_ntfy_url` checks `urlsplit(url).hostname` as a string, but httpx applies IDNA/UTS46, which turns U+3002, U+FF0E and U+FF61 into ".". The probe was a temporary pytest file in the worktree, since deleted. It used the test_ntfy_token helpers, then `load_config`, then `send_test` over a MockTransport. Output:
  `LOADED 'https://ntfy。sh' token True -> ntfy.sh Bearer tk_U6selfhostedBearer0123456789ab … 'delivered': True`
  `LOADED 'https://NTFY．SH' token True -> ntfy.sh Bearer tk_… 'delivered': True`
  `LOADED 'https://ntfy｡sh' token True -> ntfy.sh Bearer tk_…`
  `REFUSED 'https://ntfy.sh' …`
  So a config names ntfy.sh as the broker, loads with the token, and the bearer is sent to ntfy.sh. That breaks §34 and FINAL-REPORT-18 §5's "a token now always implies a self-hosted server". It also goes beyond the aliases and IPs that §3.5 admits, because this is the same hostname. The body's claim of "any letter case, scheme, port, path or trailing dot" does hold. Fix: compare `httpx.URL(url).host` (normalised, trailing dot stripped), or refuse a host that is not ASCII.
- NOTE (not a blocker). The test in tests/test_who.py named `…not_needed_by_anothers_held_job` actually sets the other project's pipeline to stopped. The mismatch is in the name, not the coverage.
~~~~

### f159d28 — U5

~~~~
REPORT
- sha: f159d28. Unit: mission 18 U5, this repository's playbook (`[series] kickoff` now names BUILDER-19). It cites DESIGN §26 (`[series] kickoff`, `kit check`), §27 Conventions (the playbook carries the next mission's line) and §34 (mission 18).
- 1. pass: the commit body names the unit, the DESIGN sections and both changed files.
- 2. pass: I committed the parent's PLAYBOOK.toml in the worktree. `test_the_repositorys_own_playbook_carries_the_series_kickoff` then failed on the value itself (`- Read meta/BUILDER-19-PROMPT.m / + Read meta/BUILDER-18-PROMPT.m`), not with PlaybookNotCommitted. After resetting to f159d28 it passed.
- 3. green on a clean tree. Summary line: `4030 passed in 434.30s (0:07:14)`, then `check: green`.
- 4. pass: the diff is `PLAYBOOK.toml | 2 +-` and `tests/test_playbook.py | 4 ++--`, nothing else. DESIGN.md and meta/ are untouched. The new kickoff line is byte-identical to the parent's line with 18 changed to 19. The playbook loads as `hands-missions`, BUILDER-19 kickoff, 20 rules (20 `[[rule]]` blocks), architect phone, autonomous False. The gate reproduces: a zip of meta/BUILDER-18-PROMPT.md checked with `--repo .` gives `kit check: pass (6 of 6 checks)`, exit 0.
- 4b. The report's weak-gate disclosure is accurate: the same zip at the parent 2221151 also gives 6 of 6, exit 0. The check itself prints "its kickoff is not compared, §26 compares a kit's". I also reproduced the uncommitted probe. A kit with the new PLAYBOOK.toml and a BUILDER-19 brief exits 0. The same brief with the parent's PLAYBOOK.toml exits 1 with `FAIL playbook: ... kickoff 'Read meta/BUILDER-18-PROMPT.md ...' is not the brief's kickoff line 'Read meta/BUILDER-19-PROMPT.md ...'`.
- 4c. Missing file: a phone `go` sends the builder to a file that does not exist yet. `phone.py:_go` sends the kickoff without checking that the brief exists, and `doctor.py:401-410` gives only a WARN, which §31 allows. Mission 17 U7 (63ac5c3) did the same, since BUILDER-18 did not exist then either. §27 expects the next mission's kit to ship the brief, so this is a known, disclosed gap, not a violation.
- NOT proven: no real phone `go` or daemon run; the BUILDER-19 brief in the probe is made up.

EVIDENCE
No BLOCKER or SHOULD-FIX candidates. Key probes:
- `diff <(git show f159d28^:PLAYBOOK.toml | grep '^kickoff' | sed 's/BUILDER-18/BUILDER-19/') <(grep '^kickoff' PLAYBOOK.toml)` printed BYTE-IDENTICAL.
- `HOME=<empty> uv run hands kit check mission-18.zip --repo .` exited 0 at both f159d28 and 2221151, each with `kit check: pass (6 of 6 checks)`.
- `ls /home/msi/git/hands/meta/BUILDER-19-PROMPT.md` returned "No such file or directory". This matches FINAL-REPORT-18 §3.6.
- No test failed, so nothing needed a re-run.
~~~~
