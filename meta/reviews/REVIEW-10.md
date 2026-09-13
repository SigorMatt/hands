# REVIEW-10 — cold review of hands mission 10

VERDICT: review mission 10 blockers=1 should-fix=7

Base `9f1e009` (`review: mission 9`, the last `review:` commit on origin/main).
Range `9f1e009..25392ff`: 15 commits.
- The architect's kit `61e1486`.
- Seven builder unit commits: U0 `cbb8fc8` (`plan:`), U1 `17ba97e`, U2
  `067b8fd`, U3 `6852751`, U4 `9f7effd` (a findings memo only), U5 `9e962a4`,
  U6 `7c5e854`.
- Seven `meta:` bookkeeping commits, which were skipped.

One sub-agent reviewed each unit commit, in a detached worktree at that commit.
Read beforehand: DESIGN v3.9 §26 (with §4, §6, §10, §11, §13),
`meta/BUILDER-10-PROMPT.md`, `meta/FINAL-REPORT-10.md`, and
`meta/findings/FINDINGS.md` (H-017 to H-021).

`./scripts/check` is green at every unit commit: 1435, 1443, 1461, 1501, 1501,
1538 and 1549 passed. `git diff --stat 7c5e854 25392ff` touches only `meta/`,
so the tip's gate is U6's: `1549 passed` / `== cli smoke ==` / `check: green`.
Every product unit's new tests go red when its product change is reverted. No
unit commit touches `DESIGN.md`. Only U0, the `plan:` commit, touches
`meta/plan.md` and `meta/CHECKPOINT.md`. Each commit body names exactly the
files the commit changes.

## Blockers

1. **§26's `hands who` bullet is not met (U4 `9f7effd`; `src/hands/who.py`
   `Transcripts.__call__`).**
   - **The design.** §26 says `hands who` matches a session to its transcript
     "by pid, … never by directory; a job in the same directory as the human's
     session is never shown under it".
   - **The code.** At the tip, `who.py` still picks the newest `*.jsonl` in the
     process's working-directory folder. U4's gate, a two-transcripts fixture
     attributed by pid, does not exist.
   - **Disclosed, and the builder is not at fault.** The mission's own verdict
     is `blocked U4`, and FINAL-REPORT-10 §3 item 4 and §5 item 1 say so. The
     docs state that `who` matches by directory (`docs/INTEGRATION.md:397-399`,
     `:687`); nothing overclaims.
   - **§26's premise is false on disk.** The U4 reviewer re-ran H-020's evidence
     read-only on 471 transcripts:
     - no first line, and no key at any depth on 138,635 lines, records a pid;
     - the pid lives in `~/.claude/sessions/<pid>.json`, whose `sessionId` names
       the transcript for all 3 live processes.
   - **Stopping was right.** The sub-agent rules (brief, "if the unit needs a
     design change, stop and write a memo") call for a memo.
   - **What to do.** The architect decides H-020, and U4 is then re-run against
     that decision. This stays a blocker until then, because the design's
     guarantee does not hold.

## Should-fix

1. **`go` is accepted while a builder job is held, including the kit's own
   apply (U2 `067b8fd`, `src/hands/phone.py:310-331`, `src/hands/daemon.py:354-374`).**
   - **What `go` checks.** `_go` refuses only when `status()` shows a running
     job or a non-empty `queued` list. A gated job is created `held` and never
     joins `_waiting`.
   - **This follows the letter of §26.** §26 says "running or queued", and §6
     lists `held` as its own state.
   - **It breaks the loop INTEGRATION describes.** Step 3 makes the apply a held
     builder job. A `go` pressed before Approve starts the next mission's
     kickoff on a kit that is not applied. Approving afterwards queues the apply
     behind it.
   - **Two further gaps:**
     - with a kickoff that matches a gate pattern, a second `go` makes a second
       held job;
     - `await asyncio.to_thread(load_playbook, …)` sits between the queue check
       and `Api.send`, and nothing is checked again, so a `hands send` in that
       window gives two builder jobs. The docstring's "nothing awaited before
       it" is true but hides this.
   - **Not tested, not disclosed.** Neither case is tested, and neither docs
     page says a held job does not block `go`. FINAL-REPORT-10 §3 item 7 names
     only the gated-kickoff case.
   - **What to do.** Refuse `go` while a builder job is held (file a finding,
     since §26 names only running or queued), check again after the load, and
     add tests for both.
2. **The loop's apply step departs from §26's "phone only" without a finding
   (U6 `7c5e854`, `docs/INTEGRATION.md:357-365`).**
   - **The departure.** Step 3 says "The apply is sent from the laptop or by the
     driver. Today, nothing on the phone can start the apply". §26 says the
     loop is described "end to end, phone only".
   - **The departure is forced.** §26 gives no phone command that sends a
     prompt.
   - **It is recorded only in FINAL-REPORT-10 §5 item 8.** That item calls it
     "step 4"; in the doc it is step 3. H-001 to H-021 do not cover it.
     CLAUDE.md requires a finding for a design gap.
   - **A test comment contradicts the doc.** `tests/test_docs.py:233` calls the
     section "phone only" while it pins the sentence that says otherwise.
   - **What to do.** File the finding, and correct the comment and the report's
     step number with an appended line.
3. **The post-exit sweep can still kill a foreign group (U1 `17ba97e`,
   `src/hands/runner.py:955-969`).**
   - **The rule.** `_group_is_the_jobs` returns true when no process holds the
     pid (`now is None`).
   - **The failing sequence.**
     1. claude is reaped.
     2. A new session leader takes the pid, forks, then exits and is reaped.
     3. Its children now form a live group with that id, but no process holds
        the pid.
     4. The sweep reads `None` and SIGKILLs that group.
   - **The docstring's reasoning** ("every member left joined while the id was
     reserved") does not cover this case.
   - **Likelihood.** Very unlikely, because the sweep runs milliseconds after
     the reap. It is still the kind of kill REVIEW-9 should-fix 1 was about.
   - **Not listed as a limit.** FINAL-REPORT-10 §3 item 5 and the review-items
     table's "closed, with limits" do not name it.
   - **What to do.** Sweep before reaping claude, or tie the sweep to a member
     whose start time is recorded. Or record the limit and fix the docstring.
4. **`kit check`'s apply-verdict exception passes a broken builder rule (U5
   `9e962a4`, `src/hands/kit.py:395-400`).**
   - **The exception.** A `builder.done` rule that matches no brief literal
     passes if it matches `VERDICT: kit applied <sha>`.
   - **The failing case.** The reviewer's probe rule `VERDICT: (kit
     applied|misison \d+ finished)` has a typo in its second branch, so it can
     never match the builder's real verdict. `hands kit check` still printed
     PASS and exited 0.
   - **This goes beyond H-021.** H-021 is about review (`aux.done`) rules. This
     exception weakens §26's "every `verdict` regex … matches at least one
     literal in the brief's final-reply vocabulary" for builder rules too.
   - **What to do.** Accept the apply literal only for a rule whose regex has
     no match against the brief's literals *and* that exists for the apply
     (for example, one whose action names the apply). Otherwise, name this
     weakening in H-021 and handbook §11.
5. **`kit check`'s paths and protocol checks pass inputs they should refuse
   (U5 `9e962a4`, `src/hands/kit.py` `_check_paths` :275, the zip reader
   :183, the send-path regex :82).** All found by the reviewer's probes:
   - **Paths that pass:**
     - `.GIT/config`, which is a real `.git` path on a case-insensitive
       filesystem;
     - a zip with a duplicate entry name, silently collapsed;
     - an entry name containing NUL.
   - **No size cap.** A 300 MB entry passed, with a 642 MB memory peak.
   - **Unchecked send paths.** The protocol check silently skips `../X.md`,
     `~/X.md` and `.txt` paths named in a send prompt, so they pass without
     being checked.
   - **Disclosure.** FINAL-REPORT-10 §3 item 9 names only the `.md`/`.toml`
     limit.
   - **What to do.** Refuse the paths above and add a per-entry and a total
     size cap. A send path the check cannot resolve should fail, not be
     skipped.
6. **Kit transport: a malformed URL escapes the refusal path, and INTEGRATION
   contradicts itself on duplicate names (U3 `6852751`).**
   - **A malformed URL is logged in full.**
     - `fetch_kit` catches `httpx.HTTPError`, but `httpx.InvalidURL` (httpx
       0.28.1) derives from `Exception` directly.
     - An `attachment.url` such as `http://[::1` passes the http(s) scheme
       check, is raised out of `fetch_kit`, and reaches
       `log.exception("phone: a command raised")` (`phone.py:249-250`).
     - The traceback can carry the sender's URL. The `_kit` docstring says "a
       refusal names the check, never the attachment's name or URL".
     - The temp file is still removed.
   - **INTEGRATION contradicts itself.** `docs/INTEGRATION.md:304` says a name
     clash becomes `<name>-1.zip`, `<name>-2.zip`. The code writes
     `<stem>-1.zip` (`kit.zip` → `kit-1.zip`), which `:356` states correctly.
     The pre-fetch refusal list also omits the non-http(s) URL.
   - **What to do.** Catch `InvalidURL` (or check the URL with `httpx.URL`
     before fetching) and refuse it without the text, add a test, and fix
     `:304`.
7. **No test pins INTEGRATION's `done` statement (U0 `cbb8fc8`,
   `docs/INTEGRATION.md:121-129`).**
   - **The gap.** With the file reverted to `cbb8fc8^`, `tests/test_docs.py`
     stays green (55 passed).
   - **Why it matters.** REVIEW-9 should-fix 2 was exactly this sentence
     drifting from the runner. U1 now makes the runner follow §6, but the
     sentence that drifted is still unpinned.
   - **What to do.** Add a docs test that asserts the doc states §6's `error`
     subtype rule, so the doc and `_failure_reason` cannot part again unseen.

## Notes

- **Kit `61e1486`** is the architect's, not a unit. It is the only commit in the
  range that touches `DESIGN.md` (v3.9). The U5 reviewer confirmed that
  `tests/fixtures/kit-mission-10/` is byte-identical (`cmp`) to the ten files
  at `61e1486`.
- **Acceptance.** The U5 reviewer ran `hands kit check` on the `git archive
  61e1486` kit files at `9e962a4`. It printed six PASS lines, the apply prompt,
  `commit message: plan: mission 10 kit` and `kit check: pass (6 of 6
  checks)`, and exited 0. The verdicts line reports 4 `builder.done` rules
  matched, rule 1 only through the apply literal (should-fix 4), and 2
  `aux.done` rules not matched (H-021).
- **U0.**
  - H-017's correction is append-only, dated, and quotes `0ead876^:DESIGN.md:235`
    correctly.
  - H-018's three gaps hold against the code at `cbb8fc8`. The reviewer ran
    `_failure_reason(error_max_turns, is_error=False, num_turns, exit 0)` and
    got `None`, so between `cbb8fc8` and `17ba97e` the doc was ahead of the
    code, as the report says.
  - Minor: H-018's decision list attributes to §26 some items that come only
    from the brief: unknown `[series]` keys refused, `go` refused without a
    kickoff, the atomic write and the numeric suffix. It also leaves out §26's
    "never shown under it" clause.
- **U1.**
  - The start time is read correctly (field 22 of `/proc/<pid>/stat`,
    `monitor.py:379`), right after spawn (`runner.py:586`).
  - `_lf` turns CRLF into LF only, so a lone CR can only cause a false refusal.
    A change that differs only in line endings compares equal, which is
    harmless because `tomllib` normalizes the same way.
  - `-c core.autocrlf=false` likely has no effect on `git show` of a blob.
  - Inherited `GIT_COMMON_DIR`/`GIT_OBJECT_DIRECTORY`, the symlink refusal and
    the git timeout are disclosed (§3 item 6).
  - The playbook sha256 stored on a job is of the working bytes, not the
    committed blob.
- **U2.**
  - The refusal tests go red before U2 only on their log line; "no job, no
    answer" already held.
  - Reverting the docs alone breaks no test.
  - `phone` in `ORIGINS`/`UNPAUSE_ORIGINS` is filed (H-018 gaps 1, 2), and §6
    line 227 still lists four origins.
  - H-019 is accurate: `tomllib` refuses `series = "x"` followed by `[series]`.
  - The secret is compared with `hmac.compare_digest` and appears in no
    publish, spool file or log.
- **U3.**
  - Names that pass `_is_kit_name`:
    - non-ASCII letters, including Cyrillic look-alikes;
    - a leading space;
    - a `:`;
    - a 304-character name, which is downloaded in full before `os.link`
      fails with ENAMETOOLONG (the temp file is removed).
  - A holder of the secret can point `attachment.url` at `http://127.0.0.1`;
    §26 is silent. Redirects are refused.
  - The file is mode 0o600 even with umask 0.
  - The temp file is removed after ENOSPC and after a cancellation mid-stream.
  - Two concurrent fetches of one name gave `kit.zip` and `kit-1.zip`.
  - The config bad-value tests would have passed before U3, as the report
    says; only the blank `kit_dir` cases were red.
  - The event-loop test holds back the headers only, not a slow body.
- **U4.** The commit body credits the stop to "the unit's brief", but the stop
  rule is the general sub-agent rule. The U4 brief's `transcript: by directory`
  fallback conflicts with §26's "never by directory"; H-020's "Needs" covers
  this.
- **U5.**
  - `kit check` hardcodes `PLAYBOOK.toml` and `meta/PLAYBOOK.toml`, while the
    engine reads the configurable `playbook.path`.
  - A kit and repo with no playbook fail `playbook`, `verdicts` and
    `protocol`, which is stricter than §26.
  - The handbook §3 apply prompt matches the code word for word.
  - `kit.py` imports no network module.
- **U6.** Doctor's `kit transport` row does not check that `kit_dir` is a
  directory, which `phone.py:368` requires, so doctor can say "on" while every
  kit is refused. Doctor also does not reflect the running/queued refusal of
  `go`. Both are disclosed in the body and in §3 item 10.
- **Method.**
  - To revert product changes, the sub-agents used
    `git checkout <sha>^ -- <files>` (or deleted the files the commit adds),
    ran the tests, then ran `git checkout <sha> -- .` and confirmed a clean
    tree. They did not use `git stash`, because seven reviewers ran in parallel
    worktrees and the stash is shared across worktrees.
  - Each ran `./scripts/check` once, not three times.
  - All worktrees were removed; `git worktree list` shows only the main
    checkout.
- **FINAL-REPORT-10 §3 (NOT PROVEN) against the sub-agents.**
  - It is honest about the blocked U4, the mocked ntfy and phone, U1's
    simulated reuse and inherited `GIT_*`, U3's blocking download, U5's H-021
    scope, and doctor's gaps.
  - It does not list:
    - the held-job `go` and the load race (should-fix 1);
    - the missing finding for the non-phone apply step (should-fix 2);
    - the reused-then-vacated sweep kill (should-fix 3);
    - the apply-literal exception accepting a broken rule (should-fix 4);
    - the `kit check` path and size gaps (should-fix 5);
    - the `InvalidURL` traceback and INTEGRATION `:304` (should-fix 6);
    - the unpinned `done` sentence (should-fix 7).
  - The review-items table's "closed" for REVIEW-9 should-fix 2 holds for the
    code but not for a test of the doc (should-fix 7). Its "closed, with
    limits" for should-fix 1 omits should-fix 3's case.

## Per-commit verdicts

### cbb8fc8 (U0)

**cbb8fc8** (mission 10 U0, `plan:` commit). Four points pass; point 2 fails because no test pins the new doc statement.

1. **Unit and sections: PASS.** The body names U0 of meta/BUILDER-10-PROMPT.md, DESIGN v3.9 §26 and §6, and REVIEW-9 should-fix 2 and 4. Its file list (plan.md, CHECKPOINT.md, docs/INTEGRATION.md, FINDINGS.md) matches `git show --name-only` exactly.
2. **Test-first: FAIL (nothing pins it).** With docs/INTEGRATION.md reverted to cbb8fc8^, `tests/test_docs.py` stays green: `55 passed`, rc=0. It is the only test that reads INTEGRATION (test_docs.py:201-213), and it only checks the six `failure_reason` names, `decided_by` and two precedence phrases. The body admits "No test changed". Tree restored, `git status` clean.
3. **Gate: PASS**, first run: `1435 passed in 112.98s (0:01:52)` / `== cli smoke ==` / `check: green`. This matches the base count in FINAL-REPORT-10.
4. **Design conformance: PASS, with notes.**
   - **`done` statement.** INTEGRATION.md:121-129 now says failed "with a `result` of subtype `error` (claude's `error_*` family, … whatever its `is_error` says)". §6 (DESIGN.md:241-246) says "with a `result` of subtype `error` (`error_result`)". The failure list and precedence match. "whatever its `is_error` says" is the builder's reading; §6 does not mention `is_error`.
   - **H-017 correction.** The diff is additions only (0 removed lines) and dated. Its quote matches `0ead876^:DESIGN.md:235`, `{reason, decided_by: cli|driver|button, decided_at}`.
   - **H-018 gaps.** All three hold. Gap 1: spool.py:93 `ORIGINS` has no `phone`, and api.py:273 refuses other origins. Gap 2: playbook.py:112 `UNPAUSE_ORIGINS={"cli"}`, playbook.py:705 un-pauses only for those, and :779 fires nothing while paused. Gap 3: runner.py:895-897 fails only on `is_error`.
   - **Doc ahead of the runner: confirmed by running it.** `_failure_reason` with `error_max_turns`, `is_error=False`, `num_turns` set and exit 0 returns `None`, so the job ends `done`. The body and plan record this deviation.
   - **DESIGN.md** was not touched (empty diff).
   - **Minor.** H-018 calls its decision list "DESIGN v3.9 §26", but some items come only from the brief, not §26: unknown `[series]` keys refused, `go` refused without a kickoff, the `~/Downloads` allowed root, atomic write, numeric suffix. It also leaves out some §26 items: a same-directory job is never shown under the human's session, INTEGRATION describes the loop, and the handbook/templates.

**Not proven:** no test covers the INTEGRATION `done` wording. I did not review what meta/plan.md or CHECKPOINT.md say. Worktree removed; the main checkout was not modified.

### 17ba97e (U1)

Commit 17ba97e: the gate is green and all five points pass, but the sweep has one soundness gap, covered in 4b. Line numbers are at 17ba97e. The worktree is removed and the main checkout is clean.

1. **PASS.** The body names mission 10 U1, DESIGN §26, §6, §10 and §24/§25, and REVIEW-9 should-fix 1, 3 and the code half of 2. `git show --name-only` lists the same 5 files as the body: `src/hands/monitor.py`, `src/hands/playbook.py`, `src/hands/runner.py`, `tests/test_playbook.py`, `tests/test_runner.py`.
2. **PASS.** With the 3 source files reverted to the parent, 7 tests fail: `test_an_error_subtype_fails_as_an_error_even_when_is_error_is_false` ×3 (`done`, expected `failed`), `test_the_last_resort_leaves_a_reused_group_alone` (sleep got -9), `test_the_sweep_leaves_a_reused_group_alone` (reported as an orphan), `test_a_crlf_checkout_of_an_lf_commit_loads` (refused as dirty), and `test_git_dir_in_the_daemons_environment_does_not_vouch_for_an_untracked_playbook` (did not raise). Each of the four behaviours has at least one red test, and each fails for the reason the body gives. Files restored, `git status` clean.
3. **PASS.** `./scripts/check` tail, verbatim: `1443 passed in 130.11s (0:02:10)` / `== cli smoke ==` / `check: green`. One run, exit 0.
4. **a) PASS.** `monitor.py:379` reads field 22 of `/proc/<pid>/stat` correctly (index 19 after the last `)`). It is recorded at `runner.py:586`, right after the spawn and before the prompt is written. If claude exits that fast, a zombie keeps its start time; if already reaped, `None` is stored, which is harmless when no one holds the pid. A reuse would only match if it came within the same 10 ms tick and inside that microsecond window.
   **b) PASS with a gap.** In the sweep (`runner.py:604-605`, after `proc.wait()`), "no process holds the pid" counts as the job's group (`runner.py:969`). That is sound for leftovers of claude's own group, since the kernel keeps the id reserved while members exist. It is unsound in one case: claude is reaped, a foreign session leader takes the pid, forks, exits and is reaped. Its members then form a group with that id, the check reads `None`, and the group is killed. So SF1's concern is closed when the reusing leader is alive but not when it has already exited. The docstring's reasoning (`runner.py:960-966`) misses this; it is very unlikely because the sweep runs milliseconds after the reap.
   **c) PASS.** `GIT_DIR`, `GIT_WORK_TREE` and `GIT_INDEX_FILE` are removed (`playbook.py:147,390`), and `-c core.autocrlf=false` is passed (`playbook.py:393`), though it likely changes nothing for `git show` of a blob. Other variables such as `GIT_COMMON_DIR` and `GIT_OBJECT_DIRECTORY` are still inherited, which meets §26's wording but not REVIEW-9's "clear GIT_*". `_lf` only turns CRLF into LF (`playbook.py:424`). A lone CR is left alone, and `\r\r\n` becomes `\r\n`, which can only cause a false refusal. A change that differs only in line endings does compare equal. That is acceptable, because `tomllib.loads` does the same CRLF-to-LF replace first, so both sides parse identically. Minor: the sha256 stored on each job is of the working bytes (`playbook.py:480`), not the committed file.
   **d) PASS.** `runner.py:916` is `if parsed.is_error or parsed.subtype != "success"`, reached only for subtypes `success`, `error` or `error_*` (`runner.py:914`). A `success` result with `is_error` true is still `error_result`. Limit and cancel still take precedence (`runner.py:903-905`). This matches §6.
   **e) PASS.** DESIGN.md, `meta/plan.md` and `meta/CHECKPOINT.md` are not in the commit.
5. **Not proven:**
   - A real pid reuse by the kernel (the tests fake it with a start time one tick earlier).
   - The race between the check and the kill.
   - The reused-then-vacated case from 4b, which has no test.
   - Scope mode.
   - A committed symlink is still refused as dirty.
   - The git timeout path.
   - The effect of the other inherited `GIT_*` variables.

### 067b8fd (U2)

067b8fd: `go` from the phone and `[series]` are built and tested, but a *held* builder job does not block `go`. The worktree was clean and has been removed; nothing in the main checkout changed.

1. **Unit, sections, files: PASS.** The body names mission 10 U2 and DESIGN §10, §11, §26 (plus §6, §20, §24/§25). The 11 files it lists are exactly the 11 files the commit changes.
2. **Test-first: PASS.** With the old `src/hands/*.py` restored (with or without the old PLAYBOOK.toml), `tests/test_phone.py` fails to collect because it imports `GO_TITLE`. With that one constant added to the old `phone.py`, 22 tests fail. That includes all 7 go tests (happy path, no playbook, no kickoff, running, queued, bad/missing secret or nonce, go after a stop), the 6 `[series]` refusals and both `--origin phone` tests. The refusal tests go red only on the log line; "no job, no answer" already held before. The repo-playbook tests also fail on the old loader, so they are not a clean check of HEAD. Reverting the docs alone breaks nothing: `tests/test_docs.py` stays green. Restored clean each time.
3. **`./scripts/check`: PASS.** Tail: `1461 passed in 127.32s (0:02:07)` / `== cli smoke ==` / `check: green`.
4a. **Exact line: PASS.** `phone.py` `_go` passes `prompt=book.kickoff` to `Api.send` with nothing added, and the test checks the job record's prompt equals the kickoff. I did not check whether the runner later adds anything to a `clear` prompt.
4b. **Running/queued check: PARTIAL.** The check reads `status()`, whose `queued` is the in-memory `_waiting` list (daemon.py:678).
   - **Two `go`s on the stream:** they cannot both create jobs. Messages are handled one at a time (phone.py:171), and an ungated send joins `_waiting` without awaiting anything.
   - **Held jobs are not counted:** a gated job skips the queue (daemon.py:359-373), so `go` is accepted beside a held builder job. If the kickoff matches a gate pattern, a second `go` makes a second held job. Found by reading the code, not run.
   - **Race window:** `await asyncio.to_thread(load_playbook)` sits between the check and the send, and nothing is rechecked. A `hands send` in that window gives two builder jobs. The docstring's "nothing awaited before it" is true but hides this. Not run.
4c. **Secret: PASS.** Compared with `hmac.compare_digest` (phone.py:300). The happy-path test finds it in no publish, spool file or log line.
4d. **Only `go` starts work: PASS** in this commit. `resume` only un-pauses (playbook.py:1140); `approve` releases an existing held job and makes no new one.
4e. **`phone` origin: PASS.** Both additions are filed as H-018 gaps 1 and 2 and referenced in the code comments (spool.py:93, playbook.py:114). §6 line 227 still lists four origins, pending the next DESIGN revision.
4f. **`[series]` loader and H-019: PASS.** Unknown keys, blanks and non-strings are refused and pinned by tests. H-019 is accurate: `tomllib` refuses `series="x"` followed by `[series]` with `Cannot overwrite a value`.
4g. **Docs: PASS with a gap.** docs/PLAYBOOK.md and docs/INTEGRATION.md match the code, but neither says a held builder job does not block `go`.
4h. **Forbidden files: PASS.** DESIGN.md, meta/plan.md, meta/CHECKPOINT.md and templates/ are untouched. FINDINGS.md is append-only (33 lines added, 0 removed).

**Not proven:** a real ntfy stream or phone; `go` with a gated kickoff (the double held job); the `hands send` race during the playbook load; the queued refusal through the stream (the test calls the handler directly).

### 6852751 (U3)

**6852751: PASS overall. Three minor issues found, none a security hole.**

1. **Unit and files: PASS.** The body claims mission 10 U3, §26 (plus §13, §11, §24/§25, §20). It lists 7 files, and `git show --name-only` shows the same 7. DESIGN.md and meta/ are untouched.
2. **Test-first: PASS.** With phone.py, config.py and spool.py reverted, test_phone.py fails at import (`KIT_TITLE`). With that name stubbed, all 28 kit tests are red, covering all five gate cases (happy path, oversize, bad name, duplicate name, missing secret). In config/docs, 6 tests are red. Restored; `git status` clean.
3. **Gate: PASS.** `./scripts/check` tail: `1501 passed in 117.40s (0:01:57)` / `== cli smoke ==` / `check: green`.
4. **Probes:**
   - **(a) Names: PASS, one gap.** NUL, `/`, `\`, `..`, leading dot, `.ZIP`, `\n`, U+202E and U+200B are all refused, never rewritten (phone.py `_is_kit_name`). Accepted: non-ASCII letters (including Cyrillic look-alikes), `" .zip"` and `:`. A 304-character name also passes the check, so the file is downloaded before `os.link` fails with ENAMETOOLONG; the temp file is removed.
   - **(b) Size: PASS.** Missing, bool, float, string and negative sizes are refused before any request. The cap is enforced again while streaming (my chunked-body probe was refused at 1 MiB), and the body must end at exactly the reported size.
   - **(c) kit_dir: PASS.** `resolve_under_roots` uses realpath (spool.py:355). A symlinked kit_dir that points outside the roots is refused; one outside that points inside is accepted as the resolved path.
   - **(d) Atomic write: PASS.** Temp file in kit_dir, then `os.link`, never an overwrite. Two concurrent fetches of the same name gave `kit.zip` and `kit-1.zip`. The temp file was removed after a write failure (ENOSPC), a too-long name, and a cancellation mid-stream.
   - **(e) URL: PASS.** Only http(s) is accepted, so a holder of the secret can still point it at `http://127.0.0.1` (§26 is silent). A 302 is refused, not followed (httpx 0.28.1).
   - **(f) Secret: PASS.** Compared with `hmac.compare_digest`. The tests show it is in no publish, spool file or log line.
   - **(g) Blocking: PASS.** Timeouts are 30 s per operation and 300 s for the whole download. `command()` is awaited inline, so the command loop waits for the download. `test_the_daemon_answers_its_socket_while_a_kit_download_is_in_flight` proves `hands status` answers while the server holds the response back before its headers.
   - **(h) Never unzipped or run: PASS.** The file is 0o600 even with umask 0, and nothing unzips or executes it.
   - **(i) Messages: PASS.** The text is exactly `kit received <name> <bytes> <sha256>` and the inbox event is `kit.received`.
   - **(j) INTEGRATION.md: minor FAIL.** It says a clash becomes `<name>-1.zip`, but the code writes `<stem>-1.zip` (`kit.zip` becomes `kit-1.zip`). Its pre-fetch refusal list also leaves out the non-http(s) URL.
   - **(k) Config tests: PASS, the report's claim holds.** The seven new bad-value strings (relative or number `kit_dir`; `kit_max_mb` of 0, -5, '20', 2.5, true) passed before U3. The blank `kit_dir` cases did fail.
5. **Also found:** an invalid URL such as `http://[::1` raises httpx `InvalidURL`, which is not an `HTTPError`. It escapes `fetch_kit` and is logged as a traceback ("phone: a command raised"), which can print the sender's URL even though the `_kit` docstring says a refusal never names it. The temp file is still removed.

**Not proven:**
- A real ntfy attachment.
- The 300 s timeout path.
- A filesystem without hard links.
- An approve arriving during a download.
- The event loop staying responsive while the body is streaming (the test only holds back the headers).
- A crash between link and unlink.

The worktree is removed and the scratch probe file deleted. Nothing was committed or stashed.

### 9f7effd (U4)

Verdict on `9f7effd9131888086e82bf40a4cb1f94067d8118`: the memo holds up and stopping was the right call, but U4's goal was not met. Unit is mission 10 U4, "who by pid"; the commit claims §26 (`hands who` bullet), the §4 `who` row, §11 and §24.

1. **Files: PASS.** Only `meta/findings/FINDINGS.md` changed, matching the body's file list. The diff is 63 lines added, 0 removed, appended after H-019. `DESIGN.md`, `meta/plan.md` and `meta/CHECKPOINT.md` are untouched.
2. **Test-first: N/A.** No product code and no test changed. The U4 gate (two transcripts in one directory, each matched to its pid) is **not met**.
3. **Check: PASS**, green on the first run so nothing was rerun. Tail: `1501 passed in 145.05s (0:02:25)` / `== cli smoke ==` / `check: green`.
4a. **First lines: PASS.** 471 transcripts now (memo: 470). First lines: 354 queue-operation, 93 custom-title, 22 mode, 2 ai-title, with the same key sets as the memo. None has a pid.
4b. **Pid-like keys: PASS, and stronger than the memo.** I searched every nested key on all 138,635 lines, including the payloads the memo skipped. The only matches were `totalAPIDuration` and `totalAPIDurationWithoutRetries` (112 each).
4c. **Sessions files: PASS.** `~/.claude/sessions/` has 3 `<pid>.json` files plus 3 `.key` files (not read). Pids 1351527 and 2688390 are `entrypoint` `cli`; 2868777 is `sdk-cli`; all three are `kind` `interactive`. All three are live, match `pgrep -x claude`, and name an existing transcript. The files carry more keys than the memo lists (for example `pidDomain`, `messagingSocketPath`, `bridgeSessionId`, `tmux`); the memo's "..." covers that.
4d. **No overclaim: PASS.** README.md and `docs/INTEGRATION.md` never say `hands who` matches by pid. `Transcripts.__call__` in `src/hands/who.py` (around line 287) picks the newest `*.jsonl` in the process's working-directory folder, if recent enough. That is matching by directory, exactly what §26 forbids.
4e. **Severity, "Needs" and stopping: PASS.** Medium severity is fair: it blocks a promised unit, and a job can still be shown under the human's session. "Needs" covers the three decisions DESIGN must make: where the pid comes from, what happens when that file is missing, and whether `entrypoint` may be used. Stopping was right: reading an undocumented sessions file next to a credential-like `.key` file is a design choice, and the sub-agent rules (brief lines 58–59) say to stop and write a memo. Minor wording issues:
   - The commit body and memo credit the stop to "the unit's brief", but the U4 text has no stop clause; the general sub-agent rule does.
   - The U4 brief allows a `transcript: by directory` fallback, while §26 says "never by directory". The memo's "Needs" does cover this.

**Not proven:**
- Whether the sessions files exist on other Claude Code versions, or for sessions that have ended.
- Whether `entrypoint` reliably tells a job from a human session (only 3 processes seen).
- The memo's own per-pid grep (its evidence item 3); I ran a different key search instead.
- The body's "green 3/3"; I ran the check once.

The worktree is removed and the main checkout is clean.

### 9e962a4 (U5)

**9e962a4 (mission 10 U5): PASS, with minor gaps and nothing blocking.** I changed nothing in the main checkout; the scratch worktree is removed and was clean before removal.

1. **Unit and file list: PASS.** Mission 10 U5, claiming DESIGN §4 `kit check` row, §26 and §10, plus findings H-019 and H-021. The 18 files in the body match `git show --name-only` exactly.
2. **Test-first: PASS.** With `kit.py` removed and `cli.py` reverted, `tests/test_kit.py` and `tests/test_docs.py` go red (many FAILED lines; the summary count was cut off in my output). I switched off the fail branch of each check in turn, and the matching tests went red every time:
   - paths: 4 tests (.git, zip symlink, dir symlink, repo-symlink escape);
   - kickoff mismatch: 1;
   - verdicts: 3;
   - wording: 2;
   - protocol: 1;
   - the `kit applied` escape hatch: 1 (test_kit.py:358).
   The `quiet_hours` refusal is the engine's own parser, so I did not mutate it. The tree was clean after restoring.
3. **`./scripts/check`: PASS.** Tail: `1538 passed in 142.57s (0:02:22)` / `== cli smoke ==` / `check: green`, exit 0.
4. **Conformance and probes: PASS, with minor gaps.**
   - **(a) §26 checks.** Each maps to a function in `kit.py`: `_check_paths` :275, `_check_playbook` :305, `_check_verdicts` :385, `_check_wording` :427, `_check_protocol` :440. It prints one line per check and exits 0 only when all pass (:542–565). `cli.py` handles `kit` before any config is read, and it passed with an empty HOME. §26 says every verdict regex is checked; the code checks only `builder.done` rules (kit.py:390). That narrowing is filed as H-021, and handbook §11 and final report §3 item 9 disclose it.
   - **Escape hatch (kit.py:398).** A `builder.done` rule that matches no brief literal passes if it matches `VERDICT: kit applied <sha>`. H-021's "Chosen" paragraph discloses this, but it goes beyond H-021's stated subject (review verdicts). It lets a typo'd rule through: my probe added `VERDICT: (kit applied|misison \d+ finished)` and still got exit 0.
   - **(b) Kit with no playbook.** The repo's playbook is in force and its kickoff is not compared (kit.py:337–352), which matches §26's "if the kit carries a playbook". If neither kit nor repo has a playbook, `playbook`, `verdicts` and `protocol` all FAIL; that is stricter than §26.
     - The engine reads the playbook from the configurable `playbook.path`; kit check hardcodes `PLAYBOOK.toml` and `meta/PLAYBOOK.toml`.
   - **(c) Zip safety.** Entries are read into memory and never extracted.
     - Fail as expected: `../outside`, `/etc/passwd`, `.git/config`, `sub/.git/hooks/x`, `./x`, `C:foo`, a zip symlink.
     - Pass, but should not: `.GIT/config` (a real `.git` path on a case-insensitive filesystem), a duplicate entry name (silently collapsed, kit.py:183), and a name containing NUL.
     - No size cap: a 300 MB entry passed and peaked at 642 MB of memory.
     - The protocol check silently skips `../X.md`, `~/X.md` and `.txt` names in send prompts (regex at :82), so they pass without being checked.
   - **(d) Network: PASS.** kit.py imports only `json`, `os`, `re`, `stat`, `subprocess` (for git), `zipfile` and `hands.playbook`.
   - **(e) Fixture: PASS.** All ten files are byte-identical to 61e1486 (`cmp`), and `DESIGN.md` at 9e962a4 is identical to 61e1486's.
   - **(f) Real kit: PASS, exit 0.** Six PASS lines (paths 10 files; playbook uses the repo's `PLAYBOOK.toml`; brief shows 3 literals; verdicts says 4 `builder.done` rules match, rule 1 through the apply literal, 2 `aux.done` rules not matched per H-021; wording; protocol finds `meta/REVIEW-PROTOCOL.md` in the repo). Then the apply prompt, `commit message: plan: mission 10 kit`, and `kit check: pass (6 of 6 checks)`.
   - **(g) Templates and handbook: PASS.** The move to `[series] name` is H-019's planned U5 step, recorded on its status line. Handbook §6 and §11 match the code, and the code's apply prompt matches handbook §3 word for word. I found no silent deviation.
   - **(h) Forbidden files: PASS.** `DESIGN.md`, `meta/plan.md` and `meta/CHECKPOINT.md` are untouched, and `FINDINGS.md` has 0 deleted lines.

**Not proven:** a run from a fresh `uv tool install`; review (`aux.done`) verdict checking; the runs form beyond a stub `WORKPLAN.md`; behaviour on Windows or a case-insensitive filesystem; a kit that has no brief.

### 7c5e854 (U6)

**7c5e854**: 4 of the 5 points pass. Point 4 fails because the change to §26's "phone only" loop has no finding in FINDINGS.md.

1. **PASS** Unit is mission 10 U6, claiming DESIGN §26, §11 and §4. The files in `git show --name-only` are the 5 the body lists (README.md, docs/INTEGRATION.md, src/hands/doctor.py, tests/test_docs.py, tests/test_doctor.py).
2. **PASS** With doctor.py reverted, all 8 new tests in `tests/test_doctor.py` fail. With INTEGRATION.md and README.md reverted, 2 tests in `tests/test_docs.py` fail (`...closed_phone_loop_once`, `...readme_names_kit_check_go...`). Files restored and `git status` clean both times; the first attempt errored because the new venv had no pytest, so I re-ran after installing the dev extra.
3. **PASS** Tail of `./scripts/check`: `1549 passed in 126.52s (0:02:06)` / `== cli smoke ==` / `check: green`, exit 0, tree clean afterwards. `git diff --stat 7c5e854 25392ff` touches only meta/ files (CHECKPOINT.md, FINAL-REPORT-10.md, journal.md, plan.md), so the tip's gate equals this one.
4. **FAIL**
   - **(a)** §26 says the loop is "phone only"; INTEGRATION.md step 3 (lines ~359-366) sends the apply from the laptop or the driver. H-001..H-021 are present at both 7c5e854 and 25392ff, and none records this. H-018 lists §26 decisions and gaps 1-3, not this one; FINDINGS.md is unchanged at the tip. The deviation appears only in FINAL-REPORT-10 §5 item 8, which also calls it "step 4" when it is step 3. `tests/test_docs.py:233` still describes the section as "phone only" while pinning "nothing on the phone can start the apply".
   - **(b)** Mostly PASS. The `go` row matches `phone.py` `_go` (doctor.py:243-278): channel on, same loader from the builder's cwd, no playbook, and no kickoff are each an off reason; the running/queued refusal is only printed, not checked. The `kit transport` row checks `resolve_under_roots` (`PathEscape` is a subclass of `SpoolError`). Mismatch: `phone.py:368` also refuses a `kit_dir` that is not a directory, which doctor does not check, so doctor can say "on" while every kit is refused. This is disclosed in the commit body and report §3 item 10. Neither row prints a topic or the secret; tests assert this for both "on" cases.
   - **(c)** PASS, no overclaim. The only "pid" hits for `hands who` are INTEGRATION.md:398 and :687, which both say it matches by directory (H-020); the other "pid" hits in docs/ are unrelated. Real ntfy delivery and a real `go` are listed as not proven.
   - **(d)** PASS. The doc's `kit <secret>` and `go <secret>` fit `phone.py:127,259-270` (exactly 2 words, secret last). The attachment fields `name`, `size`, `url` match `phone.py:345-363`. The curl `Message:` header form is consistent with ntfy but has never been run.
   - **(e)** PASS. DESIGN.md, meta/plan.md and meta/CHECKPOINT.md are not touched.
5. **Not proven:** the curl command, a real ntfy attachment fetch, a real `go` or Approve button from a phone, and the loop run end to end. The loop section is only checked for the presence of pinned phrases. Separately I confirmed that the titles, the `Apply ~/Downloads/` gate pattern and the "Kit applied" message in PLAYBOOK.toml exist in the code.

The worktree at /tmp/rev10-7c5e854 has been removed, and the main checkout is clean.
