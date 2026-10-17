# REVIEW-24 — cold review of hands mission 24
reviewed: 53b62cc3cc42af9da538ad58d6edb222dca2369b

VERDICT: review mission 24 blockers=1 should-fix=8

Shape: pull request, first review of the branch. `meta/BUILDER-24-PROMPT.md`
§Branch says "Pull request" on `mission-24`. `gh pr list --head mission-24
--state open` returns PR #5 (base `main`, headRefOid `53b62cc`). The base is
`git merge-base origin/main origin/mission-24` = `de407f2` (the kit). The
commits under review (`git log --oneline de407f2..origin/mission-24
^origin/main`):

    53b62cc report: mission 24 hosted review dispositions, the PR #5 archive
    9b351a8 ops, doctor: capture bounded by timeout, decoded with replace; worktrees OSError a WARN; migration runbook
    b940d6d kit, daemon: kit apply stages the zip in kit_dir; the kickoff exemption decided from the record
    a4e3da6 report: mission 24 final report and bookkeeping
    6fc7e6e docs: INTEGRATION's nvm PATH, go/kit apply, transcript path; handbook §11 §18
    c6b70c1 ops: docs/OPERATIONS.md, the quota-stop capture script and doctor's worktrees row
    649417d templates: refusals, review worktrees, the skip list and the gate sentence
    529b91f playbook: warn, never refuse, on a done rule without its orphaned rule
    24ac73d daemon: the journal sentence decided at dispatch; INTEGRATION's _decide sentence; rule 2 and project add pinned
    8c081d0 hosted: pin the Code Review-only verdict, exit 4 when all struck, and str-quoted job ids
    6f373cd monitor: task_killed once per task of a transcript, none on a daemon stop; transcript path under CLAUDE_CONFIG_DIR
    b003bee cli: hands go and hands kit apply, the phone's go and kit from a terminal
    f558f0f docs: the harness probe record (M8a, §40)
    f959c62 plan: mission 24 — plan, checkpoint, findings H-062..H-069

One hosted-review sub-agent first, then one sub-agent per unit commit (U1–U9
and U10's two fix commits b940d6d and 9b351a8), one at a time. I read the
`plan:` commit (U0, f959c62) and the two `report:` commits (a4e3da6,
53b62cc) myself. None of the commits is a human-supplied `fixtures:` unit or
a `plan: decisions` commit.

## Blockers

1. **9b351a8 (U10, hosted finding 2): the capture script's claim that a
   timed-out command is recorded in the file is false for two of the
   commands it names.**
   - The commit body says "hands status/jobs/pipeline, journalctl, find,
     cat, tail, grep and python3's read of the record run under `timeout -k
     5 $HANDS_CAPTURE_TIMEOUT` … A timeout is written to the file as
     `(failed: timed out after <n>s: <command>)` and the capture goes on."
     The script header (scripts/capture-quota-stop.sh:15-18) says the same.
   - `find` (scripts/capture-quota-stop.sh:105) and the python3 read of the
     record (:143) run under `bounded` alone, never through `failed`. A
     timeout there writes no timeout line.
   - Worse, the file then says something false. A timed-out `find` falls
     through to "(no job record under …)" (:112). A timed-out python3 read
     prints "(no record, or it names no transcript)" (:151). The 9b351a8
     sub-agent reproduced both with a fake `find` and a fake `python3` that
     sleep.
   - This script exists to record the first real usage-limit stop as the
     fixture (§40), so a false "no job record" defeats its purpose.
   - Also unpinned: `-k 5`, and the timeout on `find` and on the python3
     read. Dropping any of them leaves every test green.
   - Fix: route both through `failed` (or mark the section). Add a test with
     a hanging `find` and a hanging `python3` that expects the timeout line.

## Should-fix

1. **c6b70c1 (U8), still present at the tip: the capture script cuts each
   line to 4000 bytes before redacting it, so the start of a secret that
   straddles the cut reaches the file.**
   - `cut -c1-"$CUT"` runs at scripts/capture-quota-stop.sh:127, 136, 153,
     161, 164 and 169. The whole collection then goes to the redactor.
   - A command secret, notification token or key whose last bytes fall past
     byte 4000 is cut. The fixed-string and pattern matches then miss it,
     and its prefix is written to a file meant to be sent to someone. The U8
     sub-agent reproduced this.
   - Also unpinned (the U8 sub-agent removed each and every test stayed
     green): the URL-encoded form (:192) and the by-value read of
     `~/.hands/ntfy.password` (:181).
   - Fix: redact before cutting, or cut inside the redactor after redaction.
     Add a test that plants a secret across byte 4000, and tests for the
     URL-encoded and by-value forms.
2. **b940d6d (U10, hosted finding 8): the daemon-side checks on the staged
   kit name are unpinned, and two inputs break `read_staged`.**
   - Disabling the staged-name check (`is_staged_name`,
     src/hands/kit.py:1443; called from `Api.kit_apply`), or dropping
     `O_NOFOLLOW` (src/hands/kit.py:1489), leaves every test green.
   - No test covers a name with `../`, a symlink, a non-regular file or a
     missing file.
   - If the staged name is a FIFO, `os.open` (no `O_NONBLOCK`) blocks a
     worker thread forever.
   - If it is a directory, `os.fdopen` raises `IsADirectoryError` before the
     `S_ISREG` check, and the `finally` unlink raises again. The caller gets
     an internal error, not a `KitError`.
   - The daemon's early refusals leave the `.part` file in place for a
     caller other than the CLI (the CLI's own `finally` removes it).
   - The socket is local, so the exposure is small. But the commit body
     claims this validation.
   - Fix: tests for traversal, a symlink, a FIFO, a directory and a missing
     name; open with `O_NONBLOCK` and fstat before reading.
3. **f558f0f (U1): the probe record's `VERDICT` cell for Codex says `yes`,
   which hides the observation §41 most needs.**
   - Under `workspace-write`, Codex answered `VERDICT: probe ok` without
     writing `probe.txt` (docs/HARNESS-PROBE.md:141). The table at :459-461
     still says `yes`. The verdict line was verbatim, but it was false.
   - The record's opening claim that every command and output is quoted
     "verbatim" (:5-6) also does not hold. Lines 214, 376 and 385-391 are
     reflowed or shortened with `…`; each is marked, but the claim as
     written is wrong.
   - §41 will be written from this record, and the seam's choice depends on
     whether a harness's VERDICT can be trusted.
   - Fix: `partial: printed while the task failed` (or a footnote), and say
     "verbatim except where marked `…`".
4. **529b91f (U6): the kit-check warning for a kit whose `playbook` line
   fails is unpinned.**
   - Making the warning conditional on the playbook check passing (`… and
     playbook_check.ok`, src/hands/kit.py:1344) leaves tests/test_kit.py
     green.
   - The commit body claims the warning prints in that case too.
   - Fix: a test with a failing playbook line that still prints the WARN.
5. **649417d (U7): both protocols tell the reviewer to remove "each stale
   review worktree", and never define stale.**
   - templates/REVIEW-PROTOCOL.md:8-10 and meta/REVIEW-PROTOCOL.md (same
     lines). As written, any `/tmp` worktree registered in the clone
     qualifies, including one of a review running concurrently or one a
     human made.
   - The removal commands themselves are unpinned: deleting the opening
     `git worktree remove --force <path>` and the closing `git worktree
     prune` leaves every test green, because the `--force` pin is still met
     by the closing paragraph.
   - Fix: define stale (its path missing, or not this review's and older
     than the current aux job), and pin both commands where they occur.
6. **6f373cd (U3): the session half of the `task_killed` key is unpinned.**
   - With `key = ("", kill.task_id)` (src/hands/monitor.py:717), every test
     stays green, so nothing proves that two sessions reporting the same task
     id each raise.
   - The 1024-entry memory also starts empty after a restart, and its
     eviction is untested.
   - Fix: a test with the same task id in two sessions.
7. **8c081d0 (U4): the "is ambiguous" reason's `str` quoting is unpinned.**
   - Changing src/hands/api.py:210 back to `{typed!r}` leaves every test
     green, as the commit body itself admits.
   - It is the one remaining refusal that quotes the typed id. The risk is
     low: a secret containing a backslash cannot be a prefix of two job ids.
     It is the same bypass REVIEW-23 should-fix 5 named.
   - Fix: an ambiguous-prefix test whose typed text contains a backslash.
8. **24ac73d (U5): the journal sentence's share of the prompt size cap is
   unpinned.**
   - Counting only `job.prompt` against the cap (src/hands/runner.py ~618,
     at 24ac73d) leaves every test green. A prompt just under the cap
     becomes larger than the cap once the dispatch-time sentence is
     prefixed.
   - (The other gap the U5 sub-agent found, claude reading the unprefaced
     prompt, is closed by b940d6d's `FAKE:stdin` test.)
   - Fix: a test with a prompt at the cap and a dirty journal.

## Hosted review

Archive `meta/reviews/hosted/PR-5/3/`, written by the hosted-review
sub-agent's `uv run hands hosted-review 5` in a worktree at
`origin/mission-24` (53b62cc), exit 0 on the first run (no wait). Verdict
the command took from the Code Review comment: **`verdict: 2 of 9 findings
open in the Code Review comment`**.

Header at fetch 3: `🐞 Bugs (0)  📘 Rule violations (1)  🔗 Cross-repo
conflicts (1)  📜 Skill insights (0)`; fetch 1's was Bugs 6, Rule
violations 2, Cross-repo 1, Skill 0. The diff against fetch 2 shows one
change: Code Review comment 6229613578 was edited in place (updated_at
05:26:44Z → 05:48:54Z), and only its permalinks moved (9b351a8 → 53b62cc).
No ids were added or removed, and nothing more was struck.

The bot reordered the findings after the push. Below they are numbered as the
command printed them, with fetch 1's number (the report's table) in brackets.

1. [1] "Discotrade misses journal reminders" (`🔗 Cross-repo conflict`,
   src/hands/runner.py:653-656). "Runner.run() records the new journal
   preface in the running job but still writes job.prompt, without the
   preface, to Claude." Open.
   - **Dismissed.** `job = self.spool.transition(current, "running",
     prompt=…)` (runner.py:654) rebinds `job`, so `_write_prompt(proc,
     job.prompt)` writes the prefaced prompt.
   - Builder: dismissed with that reason and the test
     `test_claude_reads_the_prompt_the_running_record_keeps`. **Audit:
     holds.** The test exists (tests/test_phone.py:3144), is parametrized
     dirty/clean, and asserts that claude read back the record's prompt. The
     b940d6d sub-agent saw `[dirty]` go red when the runner writes the
     unprefaced prompt.
2. [4] "~~Doctor fails on unreadable worktree data~~ ✓ Resolved"
   (src/hands/doctor.py:1837). "_worktrees_check calls admin.iterdir()
   without handling filesystem errors."
   - **Confirmed, fixed in the PR** (9b351a8). Changing `except OSError` to
     `PermissionError` turned the vanishing-directory test red.
   - Builder: fixed in 9b351a8. **Audit: holds.**
3. [9] "~~A restarted kickoff no longer resets the consult count~~ ✓
   Resolved" (src/hands/daemon.py:715-719). "wants_journal_sentence leaves
   out kickoffs only through the in-memory Daemon.kickoffs set."
   - **Confirmed, fixed in the PR** (b940d6d). The restart test is red
     before the fix.
   - The fix treats a cli send whose text equals a kickoff line as a
     kickoff. That is design-silent and disclosed (see Notes).
   - Builder: fixed in b940d6d. **Audit: holds.**
4. [5] "~~Old spool state is skipped after migration~~ ✓ Resolved"
   (docs/OPERATIONS.md:317). "The new-machine procedure extracts the archive
   and proceeds to daemon startup without running `hands migrate-spool`."
   - **Confirmed, fixed in the PR** (9b351a8). The step was missing. The
     consequence the bot gave is wrong: handsd refuses a flat layout.
   - Builder: fixed in 9b351a8, noting the corrected consequence. **Audit:
     holds.**
5. [3] "Sub-agents alter protected metadata" (`📘 Rule violation`,
   meta/plan.md:13-15). "meta/plan.md and meta/CHECKPOINT.md are changed in
   the U0 plan unit even though the mission's standing constraint forbids
   sub-agents from editing them." Open.
   - **Dismissed.** Only f959c62 (`plan:`, U0), a4e3da6 and 53b62cc
     (`report:`) touch either file. All three are the orchestrator's
     (BUILDER-24-PROMPT.md:46-51), and no unit commit touches them.
   - Builder: dismissed with that reason. **Audit: holds.**
6. [7] "~~Quota capture can abort and leave an empty file~~ ✓ Resolved"
   (scripts/capture-quota-stop.sh:216-218). "The script cuts … lines with
   cut -c1-4000, then pipes everything into a Python redactor that calls
   sys.stdin.read() in text mode."
   - **Confirmed, fixed in the PR** (9b351a8: `errors="replace"`, and the
     file is removed when the redaction fails). The same cut-before-redact
     order is behind **should-fix 1**.
   - Builder: fixed in 9b351a8. **Audit: holds.**
7. [6] "~~Restored held jobs block the kickoff step~~ ✓ Resolved"
   (docs/OPERATIONS.md:331). "The migration procedure instructs the operator
   to run hands go after startup without first resolving any restored
   builder jobs."
   - **Confirmed, fixed in the PR** (9b351a8, steps 11-12, pinned).
   - Builder: fixed in 9b351a8. **Audit: holds.**
8. [8] "~~Kits over about 9.4 MiB can't be applied from the laptop~~ ✓
   Resolved" (src/hands/kit.py:1495-1501). "apply_run accepts zips up to
   [files] kit_max_mb (20 MiB by default) and base64-encodes the entire kit
   into one socket request."
   - **Confirmed, fixed in the PR** (b940d6d; the large-kit test is red
     before the fix). The new staging path's checks are unpinned:
     **should-fix 2**.
   - Builder: fixed in b940d6d. **Audit: holds.**
9. [2] "~~Quota capture can hang indefinitely~~ ✓ Resolved"
   (scripts/capture-quota-stop.sh:69-74). "capture-quota-stop.sh runs hands
   and journalctl directly without a timeout wrapper."
   - **Confirmed, fixed in the PR** (9b351a8). Two of the bounded commands
     do not record their timeout, as claimed: **blocker 1**.
   - Builder: fixed in 9b351a8. **Audit: the bound holds; the "recorded in
     the file" half does not.**

Every finding has exactly one row in the report's `## Hosted review` table,
and each fix commit touches its finding's anchor. Every dismissal has a
reason that holds. No H-nnn was filed for a hosted finding. No fix needed a
design decision beyond §40 except finding 3's kickoff-equality choice, which
is design-silent and disclosed.

## Notes

- **Gate (my one run).** `./scripts/check` passed at the tip `53b62cc` in a
  fresh worktree (/tmp/rev24/tip): `4636 passed in 379.54s (0:06:19)`, `==
  cli smoke ==`, `check: green`, exit 0.
  - `git diff 9b351a8 53b62cc` touches only meta/ (CHECKPOINT,
    FINAL-REPORT-24, journal, plan, and the archive `meta/reviews/hosted/PR-5/1..2/`),
    so the tip's code is 9b351a8's.
  - Every unit commit is green at its own sha: U1 4504, U2 4511, U3 4518,
    U4 4523, U5 4530, U6 4542, U7 4576, U8 4614, U9 4625, b940d6d 4629,
    9b351a8 4636. Each equals the report's count.
- **Schedule (UTC, 2026-10-17; one sub-agent at a time, so only one
  `./scripts/check` runs inside the 20-minute cap).** Start and end as each
  sub-agent reported them from `date -u`:
  - hosted review 05:50–05:53 (no gate)
  - U1 f558f0f 05:54–06:02
  - U2 b003bee 06:03–06:14
  - U3 6f373cd 06:14–06:22
  - U4 8c081d0 06:22–06:30
  - U5 24ac73d 06:30–06:53
  - U6 529b91f 06:53–07:03
  - U7 649417d 07:03–07:12
  - U8 c6b70c1 07:13–07:28
  - U9 6fc7e6e 07:28–07:37
  - U10 b940d6d 07:37–07:46
  - U10 9b351a8 07:46–07:55
  - my gate at the tip 07:55–08:02
- **Protocol version.** I followed meta/REVIEW-PROTOCOL.md on `main`
  (de407f2), as the prompt asked. U7 (649417d) rewrites it on the branch:
  worktree prune and stale-worktree removal, and the H-068 skip list. I
  pruned (`git worktree prune`) before starting, and my worktrees are
  under /tmp/rev24/. The commits I read myself (one `plan:`, two `report:`)
  are the ones the new skip list also exempts.
- **U0 (f959c62, `plan:`), read by me.** H-062..H-069 are filed
  (FINDINGS.md:2548-2661 on the branch), H-061 is decided, and H-051's
  Status line is corrected. `origin/mission-24` exists. The brief's gate
  holds.
- **Report commits (a4e3da6, 53b62cc), read by me.** They touch meta/ only.
  The report has §1 with a sha per unit, NOT PROVEN (it names the
  `unavailable`/`partial` probe rows and that no real harness ran in the
  tests), the `## Review items` table (REVIEW-23 should-fix 1–9) and the
  `## Hosted review` table. `grep -c redacted docs/HARNESS-PROBE.md` = 3,
  as reported.
- **Acceptance.** Every unit body lists every file it touches (all eleven
  sub-agents checked against `--stat`). `hands go` and `hands kit apply`
  exist and are tested. The monitor reads a transcript under
  `$CLAUDE_CONFIG_DIR/projects/` through the daemon. `kit check` warns and
  still passes 6/6. OPERATIONS.md has the inventory, the secrets table and
  five runbooks. Its spool items, file modes and the consult count's
  location were checked against the code by the U8 sub-agent.
- **NOT PROVEN, checked against the sub-agents.** The report's list stands.
  The sub-agents add:
  - blocker 1, and should-fix 2, 4, 6, 7 and 8 (the unpinned behaviours);
  - `kit apply` leaves a copied zip in `kit_dir` with no job when
    `apply_from_zip` or the §8 gate refuses after `place_kit` (api.py
    `kit_apply`; design-silent);
  - a cancel already under way when a daemon stop arrives also suppresses
    `task_killed` (monitor.py:720);
  - the 2026-10-16 burst of three raises within 120 ms for one job may have
    had a cause other than repeats, since notices within one job were
    already de-duplicated;
  - an `aux.orphaned` rule carrying a `verdict` regex silences the H-061
    warning though it may never fire on an orphaned job;
  - OpenCode got no live run (the probe read "configured default model" as
    the config file's `model` key, disclosed);
  - the capture redactor's minor bypasses for hand-edited secrets with
    special characters: double JSON escaping, lowercase percent-encoding,
    JSON `\/`, and a secret split across lines.
- **Design-silent choice without a finding.** b940d6d treats a cli send
  whose text equals a kickoff line as a kickoff, as `consults_used` already
  did. It is stated in the commit body and NOT PROVEN, as the sub-agent
  rules allow. Two sub-agents suggest a short finding; not carried.
- **The PR is left open** (blockers=1). The review file and
  `meta/reviews/hosted/PR-5/3/` are committed to `main`.

## Per-commit verdicts

**Hosted review** (05:50–05:53)

> The audit found no gaps: all nine findings have a row in the builder's table, and every disposition holds.
>
> **Audit**
> - Ran from 05:50:03 to 05:53:41 UTC. Worktree is at `/tmp/rev24/hosted` (origin/mission-24, HEAD 53b62cc), left in place. Nothing was committed there; the only untracked path is the new archive.
> - I wrote k=**3**: `/tmp/rev24/hosted/meta/reviews/hosted/PR-5/3/` (2 issue comments, 1 review, 9 review comments).
> - `hands hosted-review 5` exited **0** on the first try; there was no exit 3 to wait out.
> - Verdict line it printed: `verdict: 2 of 9 findings open in the Code Review comment`.
> - Header categories as found: 🐞 Bugs (0), 📘 Rule violations (1), 🔗 Cross-repo conflicts (1), 📜 Skill insights (0). Fetch 1 had Bugs 6, Rule violations 2, Cross-repo 1, Skill 0, which matches what the builder wrote.
> - The diff against fetch 2 shows one change: Code Review comment 6229613578 was edited in place (updated_at 05:26:44Z → 05:48:54Z). Only its permalinks moved, from sha 9b351a8 to 53b62cc. No ids were added or removed, and nothing more was struck.
> - The bot reordered the findings after the push. The table uses fetch 1's numbers (current number → fetch 1 number): 1→1, 2→4, 3→9, 4→5, 5→3, 6→7, 7→6, 8→8, 9→2. Each one has exactly one row.
> - The two fix commits do touch the anchor files of the findings they claim. b940d6d touches kit.py and daemon.py plus their tests. 9b351a8 touches the capture script, doctor.py and OPERATIONS.md plus their tests. All seven fixed findings now show `✓ Resolved`. The fix tests pass: test_operations, test_doctor, test_runbook and the finding-1 test.
> - No H-nnn was filed for any hosted finding, so nothing can be missing from FINDINGS.md. H-062..H-069 are all present there.
> - No fix was made in silence. b940d6d's two design-silent choices are stated in its commit body and in the report's not-proven list:
>   - A cli send whose text equals a kickoff line is treated as a kickoff.
>   - The kit is staged as `.hands-kit-*.part` in kit_dir. This matches §40's "copies it into [files] kit_dir", and the `kit_apply` payload is not in DESIGN's protocol table.
>   - Neither has its own finding. That is acceptable, but the reviewer may want one for the kickoff-equivalence choice.
>
> (Its nine findings, verbatim with anchors and audits, are reproduced in `## Hosted review` above.)

**U1 f558f0f** (05:54–06:02)

> f558f0f (docs: the harness probe record, M8a §40): no blocker; 3 should-fix candidates. Started 05:54:50 UTC, ended 06:02:22 UTC.
>
> 1. **Unit and sections: PASS.** The unit is mission 24 U1, the harness probe, claiming DESIGN §40 ("The harness probe", "The seam, as far as it is decided") and the docs/RELATED.md Gas Town section. The stat shows one added file, `docs/HARNESS-PROBE.md`, and the body names it as Added.
> 2. **Test-first: N/A.** The commit is docs only with no tests, which is what U1 asks for. As a mutation I deleted the file: `test_docs.py::test_the_sweep_reads_every_tracked_text_file...` went red, but only because a tracked file was missing from disk. The sweep reads the file for pinned phrases and does not check its claims, so that matches the brief. The restore was clean (`git status` empty).
> 3. **Gate: PASS** (exit 0). Pytest line: `4504 passed in 370.41s (0:06:10)`. Final line: `check: green`.
> 4. **Design conformance: PASS.** DESIGN.md, meta/plan.md and meta/CHECKPOINT.md are untouched, and the probe ran in a /tmp scratch repo. The body matches the disk on versions, sign-in providers, the Codex bwrap failure and the OpenCode/dsh unavailability.
> 5. **Record vs brief: PASS.** It has every U1 row, the requirements table and a Gaps list. `grep -c redacted` = 3. There are no keys, tokens, account emails or sign-in file contents; only the auth.json path, key names and thread ids appear. The Codex yes cells (one-shot, resume, VERDICT) are each backed by a quoted run, and "permission: no" and "stream: partial" match the quoted evidence. The 36-record session count adds up.
>
> Should-fix candidates:
> - **Verbatim claim:** `docs/HARNESS-PROBE.md:5-6` says every command and output is verbatim, but lines 214, 376 and 385-391 are reflowed or shortened with `…`. Each is marked, but the claim is wrong as written.
> - **VERDICT cell:** the `yes` at line 461 hides that under workspace-write Codex printed `VERDICT: probe ok` after the write failed (line 141). That matters for §41 because the verdict line alone is not trustworthy. It would be better as a partial or a footnote in the table.
> - **OpenCode model reading (judgment call):** the probe read "configured default model" as a `model` key in the config file, so it ran no OpenCode call. The body discloses this, but the result is that §41 gets no live OpenCode evidence. The brief's pointer to `opencode models` could be read the other way.
>
> Nit: dsh's usage-limit, telemetry and ACP rows (`:445-447`) are filled from its docs rather than marked `unavailable: not signed in` as "every row" says. They are labelled as documentary, so this is harmless.
>
> Not proven: every claim about harness behaviour. The live runs cannot be replayed, I did not re-run any harness, and no test checks the record's content.

**U2 b003bee** (06:03–06:14)

> Commit b003bee passes all four points, with one should-fix that a later commit (b940d6d) fixes. Started 06:03:05 UTC, ended 06:14:00 UTC.
>
> 1. **PASS: unit and files.** The body names mission 24 U2 and DESIGN §40 "Operations the human performs without an agent", §29 and §32. It lists all 9 files in the stat, and `tests/test_operations.py` is named as added. Nothing was deleted.
> 2. **PASS: test-first.** I reverted the 5 non-test files (all exist at b003bee~1). All 7 tests in `test_operations.py` went red, and so did `test_phone.py::test_go_checks_the_builder_again_after_the_playbook_load`, because it patches `api_mod.load_playbook`, which the old code does not have. `test_gates.py` and `test_docs.py` stayed green, which is expected: the gates test now calls `_send`, which already existed, and the docs test only accepts more names. After restoring, `git status --short` was empty.
> 3. **PASS: `./scripts/check` green at b003bee.** Pytest summary: `4511 passed in 328.50s (0:05:28)`. Final line: `check: green`.
> 4. **PASS: design conformance.** DESIGN.md, `meta/plan.md` and `meta/CHECKPOINT.md` are untouched, and nothing the body claims is contradicted by the files.
>    - **`hands go` and the phone's `go`:** both run one code path, `Api.kickoff`, with origin cli and phone. It checks for a running, queued or held builder job before and after the playbook load.
>    - **`kickoff` cannot be called over the socket:** it is not in COMMANDS, KIT_METHODS or OPERATIONS.
>    - **`kit apply` as filed:** it checks a scratch copy and refuses a failing kit with the check's lines. It copies through `place_kit`, which never overwrites another file and files a same-bytes zip where it is. It files the apply held, origin kit, with a minted kit_id, and its prompt names `~/Downloads/<name>.zip`. `hands approve` releases it, and README lists both commands.
>    - **`go_builder`, `_builder_busy`, `_is_kit_name`:** none is referenced anywhere outside historical meta reports and reviews.
>    - **Mutations:** ignoring held jobs in `builder_busy` turned two tests red. Removing the `report.ok` refusal in `kit_apply` turned one red. Neither stayed green.
>
> - **Should-fix, transport:** `hands kit apply` sends the zip as base64 in one socket line (`src/hands/kit.py:546`, `src/hands/api.py:258`). The daemon's line limit is `runner.LINE_LIMIT` (prompt cap + 1/4, `src/hands/runner.py:151`), so a kit over about 9.4 MiB cannot be applied even though `kit_max_mb` defaults to 20. The client does not measure the request first, so the daemon refuses it at `readline`. b940d6d fixes this (its finding 8).
> - **Minor, leftover zip:** in `src/hands/api.py` `kit_apply` (~line 308), `place_kit` runs before `apply_from_zip` and `file_apply`. If either of those then refuses (a KitError, or the §8 gate), the copied zip stays in kit_dir without a job. The design does not say whether that is allowed.
> - **Not proven:**
>   - `test_operations.py` does not test `hands go` refused while a builder job is running or queued; only the phone's tests cover that, through the shared code.
>   - No test shows that a `place_kit` refusal leaves no temp file behind.
>   - No real claude run was made.
>
> The gate log is at `/tmp/rev24/check-b003bee.log`. The worktree is removed, and `/tmp/rev24/hosted` was not touched.

**U3 6f373cd** (06:14–06:22)

> **6f373cd** (mission 24 U3: the monitor and the runner). Verdict: all four points pass, no blocker. Started 06:14:29 UTC, ended 06:22:18 UTC.
>
> 1. **Pass.** The body names U3, §40 (H-062, H-063), §2 and §38. It lists all 9 files in `--stat`, says correctly that no file was added or deleted, and sets both findings' Status lines to resolved-by-code.
> 2. **Pass (test-first).** I reverted monitor.py, runner.py, daemon.py and FINDINGS.md to 6f373cd~1. Six of the new tests went red: both dedup tests (one task, two tasks), the daemon-stop test, the monitor-reads-under-CLAUDE_CONFIG_DIR test, and both runner path tests. Only the cancel control stayed green, which is expected: it already raised once before the change. After restoring, `git status --short` was empty.
> 3. **Pass.** `./scripts/check` ran once in the foreground. Pytest summary: `4518 passed in 349.76s (0:05:49)`. Final line: `check: green`.
> 4. **Pass.** The code matches the §40 text and the brief's U3. DESIGN.md, meta/plan.md and meta/CHECKPOINT.md are untouched, and nothing the body claims is contradicted on disk.
> 5. **Unit checks.**
>    - Mutations that went red: dropping the dedup check (2 tests), dropping the stopping check, ignoring the role env (2 tests), keying by job id, and taking a relative CLAUDE_CONFIG_DIR from somewhere other than the cwd.
>    - **Should-fix candidate (test gap, minor), src/hands/monitor.py:717.** If I take the session out of the key (`key = ("", kill.task_id)`), every test stays green. Nothing proves that two sessions with the same task id each raise. Real task ids are random (`bar46gi30` in the fixture), so a collision is unlikely.
>    - Eviction: the 1024-entry memory drops its oldest key once full. It also starts empty after a daemon restart. In both cases a later `keep` job that re-emits an old notice would raise it again. This is bounded and not tested.
>    - **Nit, monitor.py:720 with runner.py:746.** If a human's cancel is already under way when the daemon stop arrives, the job is in both sets. Its record stays `killed`, but its `task_killed` is suppressed anyway.
>    - The path is recorded at the init event, from `job_env` (handsd's environment plus the role's env table), before `wait_for_session` releases the monitor. The through-the-daemon test checks that the recorded path is under the role's dir, that the fake claude wrote the file there, that the ops monitor read its first line, and that `~/.claude` was never created.
>
> **Not proven:**
> - Whether a real claude's `--resume` stream actually repeats old kill notices. The dedup test gets its repeats because the fake claude re-emits the notice for every job.
> - Whether a real claude emits kill notices on SIGINT.
> - How `~` in CLAUDE_CONFIG_DIR is handled; the code uses the value as written.
> - That this change fixes the incident's 3 raises in 120 ms for one job. Notices for the same task inside one job were already deduplicated before this commit, so that burst may have had a different cause.
>
> The gate log is at `/tmp/rev24/check-6f373cd.log` and the mutation script at `/tmp/rev24/mut6f.sh`. The worktree is removed.

**U4 8c081d0** (06:22–06:30)

> sha 8c081d0 passes all four points, with no blocker. Start 06:22:48 UTC, end 06:30:11 UTC (2026-10-17).
>
> 1. **PASS.** The body names unit U4 (mission 24), DESIGN §39, and REVIEW-23 should-fix 3, 4 and 5. It lists all 3 files in `--stat` (`src/hands/api.py`, `tests/test_hosted.py`, `tests/test_phone.py`); none were added or deleted. You pointed me to §40, but the brief's U4 text says §39, so the body is right.
> 2. **PASS.** With `api.py` reverted to 8c081d0~1, the backslash-secret test in `test_phone.py` went red: the log showed `no such job 'Qm7\\Zr4\\Wk9\\Tp2'`. The 4 new `test_hosted.py` cases stayed green, as expected, because they only pin `hosted.py`, which this commit does not touch. Each mutation the body names turned its test red:
>    - dropping `kind == "issue-comment"` from `_is_code_review`: both parametrized cases red;
>    - `max`->`min` at `hosted.py:276`: red;
>    - `not open_`->`not current` at `hosted.py:427`: red.
>    After restoring, `git status --short` was empty.
> 3. **PASS.** Gate: `4523 passed in 351.27s (0:05:51)`, final line `check: green`.
> 4. **PASS.** The commit does what U4 asks: it formats the typed id with `str` in backticks, never `repr`, in both `match_job_id` reasons. It does not touch `DESIGN.md`, `meta/plan.md` or `meta/CHECKPOINT.md`, and nothing on disk contradicts the body.
> 5. **Redaction:** confirmed that no 4+ character piece of the secret reaches a published title, message or the log. I checked the other refusals that could quote typed text:
>    - the remaining `!r` reasons in `api.py` that the phone can reach quote only the stored origin or kit name, never what was typed;
>    - `reply` and `answer` refusals skip `_redact` (`phone.py:484-486`, `phone.py:529-531`), but their reasons quote no typed text. That is worth a note, not a defect.
>
> **Should-fix candidate:** `src/hands/api.py:209`. Changing the "is ambiguous" reason back to `{typed!r}` leaves every related test green, as the body admits. The risk is low, since a secret containing a backslash can't be a prefix of two job ids.
>
> **Not proven:** the "is ambiguous" quoting, the laptop CLI's wording, and that a future refusal reason quoting typed text on the `reply`/`answer` paths would be redacted.

**U5 24ac73d** (06:30–06:53)

> **Review of 24ac73d** (mission 24 U5; DESIGN §39 H-060, H-058, H-051, `git clone --`, and §40 `hands go`; REVIEW-23 should-fix 6-9). Started 06:30:39 UTC, ended 06:53:23 UTC. Verdict: **pass**, with two should-fix candidates (test gaps, not code bugs).
>
> 1. **Body vs files: pass.** The body lists all 9 files in `--stat` and says none were added or deleted, which is true.
> 2. **Test-first: pass.**
>    - With the 4 non-test files at 24ac73d~1, three tests went red: the test_docs `_decide`-sentence test and both cases of `test_the_journal_sentence_is_decided_when_the_send_is_dispatched`.
>    - Five stayed green, as expected, because they pin behaviour that already existed: the go/kickoff test, kit rule 2, both project_add tests, and the progress test.
>    - Each mutation the body names turns its test red: `architect/CLAUDE.md` reverted to 2b4df10~1 alone, the `--` dropped from the dry run, and `set-url` taken out of the failure condition.
>    - After restoring, `git status --short` was empty.
> 3. **Gate: pass.** `4530 passed in 370.55s (0:06:10)`; final line `check: green`.
> 4. **Design: conforms.** DESIGN.md, meta/plan.md and meta/CHECKPOINT.md are untouched.
>    - The sentence is decided in `Daemon._run` at dispatch, with git in `asyncio.to_thread`. A held job is stored and announced with the human's prompt alone.
>    - INTEGRATION.md now matches `phone.py` `_decide` (lines 411-414).
>    - The runner writes the transitioned record's prompt to claude, so the record and stdin match.
>    - The progress-test change only adds a wait for the `started` stamp before the existing assertions. It does not weaken them.
>
> **Mutations that stayed red:** git called on the event loop (no `to_thread`), the record not getting the preface, and the kickoff exemption removed.
>
> **Should-fix candidates:**
> - `src/hands/runner.py:699`: writing `current.prompt` (no preface) to claude while the record keeps the preface stays green (355 tests passed). Nothing checks that claude actually reads the sentence; only the record is checked.
> - `src/hands/runner.py:618`: counting only `job.prompt` against the size cap stays green (1096 tests passed). The preface's share of the cap is unpinned.
>
> **Note:** `src/hands/daemon.py:196` keeps the kickoff exemption in memory, which the body states. After a daemon restart, a `hands go` job gets the sentence. Its prompt then no longer equals the kickoff, so the kickoff match in `playbook.py:2563` also misses it. b940d6d later replaced this, as the brief notes.
>
> **Not proven:** real git timing off the event loop, and any restart behaviour.
>
> The worktree is removed; `/tmp/rev24/hosted` was not touched. The gate log is in `/tmp/rev24/gate-24ac73d.log`.

(The first candidate is closed at the tip by b940d6d's `FAKE:stdin` test;
the second is should-fix 8.)

**U6 529b91f** (06:53–07:03)

> **529b91f** (mission 24 U6, H-061, DESIGN §40 with §39 and §10). Started 06:53:51 UTC, ended 07:03:04 UTC (2026-10-17). No blockers.
>
> 1. **PASS.** The body names the unit and its sections, and lists all 6 files from `--stat` (none added or deleted).
> 2. **PASS (test-first).** With the 4 non-test files put back to `~1`, both test files failed at collection on the `orphaned_rule_warnings` import, so everything was red. I then added a temporary stub returning `[]` (my addition, not in the commit) to see each test on its own. Red: both kit pairing tests, the warn-twice test, the both-present kit test (missing JSON `warnings` key), the repo-playbook-in-force test, and both engine logs-a-warning tests. Green, as expected: the shipped-playbooks-warn-nothing tests (3 cases), engine-both-present, and no-done-rule. After restoring, `git status --short` was empty.
> 3. **Gate green.** `4542 passed in 379.29s (0:06:19)`; final line `check: green`.
> 4. **PASS.** The code matches §40 and the brief's U6 text. DESIGN.md, meta/plan.md and meta/CHECKPOINT.md were not touched, and nothing on disk contradicts the body. Mutation: warning even with no done rule went red (caught by `test_a_playbook_without_done_rules_warns_nothing`).
>    - **Mutation that stayed green (should-fix candidate):** I made kit check warn only when the `playbook` line passes (src/hands/kit.py:1344, `... and playbook_check.ok`). `tests/test_kit.py` stayed fully green. The body's claim that it also warns "for a kit's playbook whose line fails too" is therefore not pinned by any test.
> 5. **PASS.**
>    - The WARN line comes after the check lines, the `--json` output has a `warnings` key (`[]` when there is nothing to warn of), and `_load` logs each warning with `log.warning` (src/hands/playbook.py:1625).
>    - Neither refuses: the kit still passes 6 of 6, the engine is not paused and sends nothing.
>    - docs/PLAYBOOK.md:215 says so. Both rules present gives no warning, and the two templates and this repo's PLAYBOOK.toml warn nothing.
>    - What "a rule on aux.done" means: rules match an event only by exact name (`on` must be one of `EVENTS`, playbook.py:1159; matched with `rule.on == event`). There are no glob or regex event forms, so no rule can cover `aux.orphaned` by pattern. `verdict` is a regex on the reply text, not on the event name.
>    - Edge case: an `aux.orphaned` rule that carries a `verdict` regex still silences the warning, even though it may never fire on an orphaned job. This is minor and I did not check it by running anything.
>
> **Not proven:**
> - The warning for a kit whose `playbook` line fails (no test).
> - The engine logs again on every reload; that is by design, not checked by a test.
> - The warning is shown on daemon start only if `_load` runs there, which I did not trace.

**U7 649417d** (07:03–07:12)

> Commit 649417d (mission 24 U7: templates on refusals, review worktrees, the skip list and the gate sentence) passes all four points, with no blocker and one should-fix candidate. Started 2026-10-17 07:03:28 UTC, ended 07:12:43 UTC.
>
> 1. **Commit body: pass.** It names unit U7, DESIGN §40 "Four findings carried from another project's reviews", the §38 human-supplied unit, and findings H-066..H-069. It lists all 7 files in `git show --stat`, all modified, none added or deleted, which matches the disk.
> 2. **Test-first: pass.** I reverted the 6 non-test files to 649417d~1 and ran `tests/test_kit.py`. All 36 new or changed tests went red (brief ×2, rule 8, 18 protocol sentence pins, 2 order pins, 13 handbook pins). None of the new tests stayed green. After restoring, `git status --short` was empty.
> 3. **Gate: pass.** `./scripts/check` ran once in the foreground, exit 0. Pytest summary: `4576 passed in 381.26s (0:06:21)`. Final line: `check: green`.
> 4. **Design conformance: pass.** The changes match §40 and the U7 brief text.
>    - DESIGN.md, `meta/plan.md` and `meta/CHECKPOINT.md` are untouched.
>    - Nothing the body claims is contradicted by the disk.
>    - Mutating `[b] refused` to `[b] blocked` in the brief template turned the tests red.
>    - One mutation stayed green: removing the `git worktree remove --force <path>` command from the opening paragraph and the trailing `git worktree prune` from the closing paragraph, in both protocols. The tests only pin sentences, and the `--force` pin is still satisfied by the closing paragraph.
> 5. **Unit-specific: pass.**
>    - The `refused:` sentence and the `[b] refused` rule match `meta/BUILDER-24-PROMPT.md` word for word.
>    - Rule 8 has the new condition, the `VERDICT: escalate ruling: human-supplied content` answer, and the human-supplied unit shape (`~/Downloads/<name>/`).
>    - The skip list matches §40.
>    - Step 3 carries the gate sentence word for word, and the old §36 wording is pinned as absent.
>    - Handbook §7 and §17 say each of these.
>    - Diffing the two protocol files shows only the `<owner>/<repo>` vs `SigorMatt/hands` lines differ.
>    - The kit check 6/6 tests and the filled-template tests pass (9 passed).
>    - The protocol stays consistent: the final removal comes after the hosted-review directory is copied out of its worktree and after the merge.
>
> **Should-fix candidate:** `templates/REVIEW-PROTOCOL.md:8-10` (and the same lines in `meta/REVIEW-PROTOCOL.md`) never defines "stale". As written, any `/tmp` worktree registered in the clone qualifies, including one belonging to a concurrently running review or a human-run review on the same clone. A criterion such as "path missing, or not added by a running job" would close this.
>
> **Not proven:**
> - That aux jobs are serialised, so nothing else is using the clone's `/tmp` worktrees when the opening removal runs.
> - That a reviewer or sub-agent actually obeys any of these rules; the commit body says this itself.
> - The "file outside `meta/` is a forbidden edit" reading is the builder's own choice where the design is silent. It matches every recent `meta:`/`journal:`/`report:` commit; only b77bc4d (mission 7a) broke it.
>
> The gate log is at `/tmp/rev24/p7-check.log`. The worktree is removed, the main tree is clean, and `/tmp/rev24/hosted` was not touched.

**U8 c6b70c1** (07:13–07:28)

> I found no blockers in c6b70c1 (U8: OPERATIONS.md, the quota-stop capture script, doctor's worktrees row). There are two should-fix candidates, both in the capture script's redaction.
>
> 1. **Body:** pass. It names U8 and the sections DESIGN §40 Operations, Credential profiles and Four findings (the H-067 half), plus §23, §33 and H-067. It lists all 7 files from `--stat` and marks the 3 new ones as added.
> 2. **Test-first:** pass. With the 4 non-test files reverted or removed, all 32 new or changed tests went red: every test in `test_runbook.py`, the 3 new doctor tests, and 2 tests in `test_docs.py`. The `test_docs` sweep test also going red was expected, since the tracked files were gone. After restoring, `git status --short` was empty.
> 3. **Gate:** pass, exit 0. Pytest summary `4614 passed in 374.20s (0:06:14)`; final line `check: green`.
> 4. **Design conformance:** pass. DESIGN.md, `meta/plan.md` and `meta/CHECKPOINT.md` are untouched. These OPERATIONS.md claims match the code:
>    - the spool items match `spool.py`, including `FLAT_ITEMS`, `kits/` and `handsd.sock`;
>    - config and `cmd_secret` are mode 600 (`project.py:200`), the secret comes from `token_urlsafe`, and `kit_dir` defaults to `~/Downloads`;
>    - the wheel's `shipped/` layout matches, and `handswho@.service` is not in the wheel;
>    - the consult budget's count lives in `jobs/` plus the `consults_since`/`series_since` anchors in `pipeline.json` (`playbook.py:1556-1690`).
>
>    The secrets table has the five columns, one row per kind, and no values. All five runbooks are present, and the no-phone table covers every phone and who command word.
>
>    Mutations: with the doctor's missing-path check disabled, the tests went red. Removing both JSON-escape forms from the redactor also went red. Removing the URL-encoded form, or the by-value read of `~/.hands/ntfy.password`, stayed green.
>
> **Should-fix 1 (script, still present at 9b351a8):** lines are cut to 4000 bytes before redaction (`scripts/capture-quota-stop.sh:101,108,125,133,139`). A secret or key that straddles byte 4000 loses its tail, no longer matches, and its prefix ends up in the file. I reproduced this.
>
> **Should-fix 2 (test gap):** the tests do not cover the URL-encoded form (`capture-quota-stop.sh:192`) or the by-value read of `ntfy.password` (`:181`). The planted password only sits behind a `"password":` key, so the pattern-based redaction catches it either way (`tests/test_runbook.py:284`).
>
> **Minor redactor bypasses I reproduced:** these all need a secret with special characters, which only a hand-edited secret would have (generated ones are urlsafe). They are double JSON escaping, lowercase percent-encoding, a JSON `\/` escape, and a secret split across lines. The secret never shows in the filename. Error output to the terminal from `tail`/`find` names only paths.
>
> **Doctor:** the warning on a dangling worktree, "ok after prune", relative gitdir entries and locked worktrees are all handled. At this commit, an OSError from `iterdir` is not caught.
>
> **What 9b351a8 fixes:** it adds timeouts to every read, decodes with errors="replace" so a non-UTF-8 byte no longer crashes the capture and leaves an empty file, turns the `iterdir` OSError into a WARN, and adds a `hands migrate-spool` step plus a step to decide a held job to the migration runbook.
>
> **Not proven:** a real usage-limit stop, the runbooks on a real machine, ntfy's web page, linger, and the doc's mode claims for the laptop's files.
>
> **Times:** start Sat Oct 17 07:13:42 UTC 2026, end 07:28:13 UTC 2026. The worktree is removed and `/home/msi/git/hands` was left unmodified. The gate log is at `/tmp/rev24/p8-check.log`.

(Line numbers are c6b70c1's; at the tip the cuts are at :127, 136, 153,
161, 164, 169. Both candidates are should-fix 1.)

**U9 6fc7e6e** (07:28–07:37)

> **6fc7e6e** (U9 docs): pass on all four points. No blockers and no should-fix items. Start 07:28:44 UTC, end 07:37:09 UTC.
>
> 1. **PASS.** The unit is mission 24 U9, against DESIGN §40 "Documentation", "The harness probe", "Operations…", H-063 and H-061, plus the carried H-067 row and review 23 should-fix 7. The body lists all 5 files in the stat. None were added or deleted.
> 2. **PASS.** It adds 11 tests (10 functions, one run for two docs). With README, both docs and phone.py reverted to 6fc7e6e~1, all 11 went red and none stayed green. After restoring, `git status --short` was empty.
> 3. **PASS.** `4625 passed in 382.10s (0:06:22)`, final line `check: green`.
> 4. **PASS.** It covers the brief's U9 text and §40's handbook items (the §17 `refused:` line and the skip list were already there from U7). DESIGN.md, meta/plan.md and meta/CHECKPOINT.md are untouched. Three mutations all went red: swapping the merge order in `job_env` (runner.py:1127), ignoring `CLAUDE_CONFIG_DIR` in `transcript_path_for` (runner.py:273), and renaming the `WARN playbook:` print (kit.py:1390).
> 5. **Unit-specific checks all hold.**
>    - **PATH note:** the role's PATH replaces handsd's, because `job_env` puts `spawn_env` over `os.environ`. Nothing is expanded, because the value is copied as a string. The example value works: Popen looks up argv[0] on the env it is given, and `systemd-run --scope` passes that env on; the example includes `/usr/bin`, which has `systemd-run`, `git` and `python3`. The doc's "those two" is accurate: codex and dsh are `#!/usr/bin/env node` scripts on disk, and opencode is a native ELF.
>    - **Doctor:** its claude row uses `shutil.which` on doctor's own PATH, as the doc says.
>    - **phone.py:** only the docstring changed; the module's AST minus the docstring is identical to the parent's.
>
> **Not proven:** that a harness under nvm, or a bare `[runner] claude`, actually runs on a role's PATH (no real harness runs in the tests; the body says so). The node shebang is not recorded in docs/HARNESS-PROBE.md or tested; I only checked it on disk. The kit apply copy/refuse wording is pinned as strings only in test_docs; tests/test_operations.py is meant to cover the behaviour and was not reviewed here. Worktree removed; /tmp/rev24/hosted untouched.

**U10 b940d6d** (07:37–07:46)

> b940d6d (U10, PR #5 hosted findings 1, 8 and 9; claims DESIGN §40, §39 (H-060) and §28). Start 07:37:32 UTC, end 07:46:20 UTC.
>
> 1. **PASS.** The body lists all 8 files in the stat and says none were added or deleted, which is true.
> 2. **PASS.** I reverted the 5 source files. The restart-kickoff test went red on prompt/consults, and the large-kit test went red with "13983398 bytes on the wire, over the daemon's 13107200 byte line room". `test_claude_reads_the_prompt_the_running_record_keeps[dirty/clean]` stayed green, which is expected because the body says finding 1 was not a defect and the test only pins current behaviour. After restoring, `git status` was empty.
> 3. **PASS.** Gate: `4629 passed in 366.57s (0:06:06)`; final line `check: green`.
> 4. **PASS with gaps.** No forbidden files were touched, and nothing the body claims is contradicted on disk.
>    - `is_staged_name` rejects `../`, absolute paths, slashes, backslashes and NUL. `O_NOFOLLOW` refuses a symlink. Reading is capped at kit_max_mb.
>    - Nothing scans kit_dir for kits. The phone's temp files end in `.hands-kit-*.zip`, which the `.part` check never accepts.
>    - The U2 tests still pass for the same-bytes and other-file cases of the final name, since `place_kit` is unchanged.
>    - Restart survival is proven by the new test.
>    - The FAKE:stdin mutation (runner writes the unprefaced prompt) made `[dirty]` red, as the task expected; `[clean]` stayed green, also as expected.
>
> **Should-fix (tests):** two mutations stayed green across `tests/test_operations.py` and `test_kit.py`: disabling the staged-name check at `src/hands/api.py:733`, and dropping `O_NOFOLLOW` at `src/hands/kit.py:1489`. No test covers path traversal, symlinks, non-regular files or a `staged` name that does not exist, so the daemon-side validation the body claims is not pinned.
>
> **Should-fix (robustness), `src/hands/kit.py:1485` (`read_staged`):**
> - If the staged name is a FIFO, `os.open` without `O_NONBLOCK` blocks forever. I confirmed a probe still blocked after 3s. It hangs one `to_thread` worker and the request, and the file is never unlinked.
> - If the staged name is a directory, `os.fdopen` raises `IsADirectoryError` before the `S_ISREG` check. The `finally` unlink at `api.py:753` then raises again. The caller gets an internal error instead of a `KitError`.
>
> **.part removal:** the daemon refuses an invalid name, a missing builder role or a bad kit_dir before its `finally`, so it does not remove the `.part` file on those paths. The CLI's `finally` removes it on every path, so this only matters for a non-CLI socket caller.
>
> **Kickoff choice:** treating a cli send whose text equals a kickoff value as a kickoff is something the design does not address. The body says so openly, and it matches what `consults_used` already does. I would file a short finding (a nit, not a blocker).
>
> **Not proven:**
> - A hardlink or a concurrent `place_kit` temp file named `.hands-kit-*.part` being read and deleted by a socket caller (both share the same prefix and suffix).
> - That the CLI and daemon configs resolve the same kit_dir.
> - Kickoff behaviour when `self.playbook` is None at dispatch.

**U10 9b351a8** (07:46–07:55)

> Commit 9b351a8 passes points 1–4, with one should-fix: two of the capture script's timeouts are not recorded in the output file. Started 07:46:47 UTC, ended 07:55:36 UTC.
>
> 1. **PASS.** The body names the unit as mission 24 U10, fixing PR #5 hosted findings 2, 4, 5, 6 and 7, under DESIGN §40 (and H-067's doctor half). It lists all 5 files in `--stat`, and none of them was added or deleted.
> 2. **PASS.** With `docs/OPERATIONS.md`, `scripts/capture-quota-stop.sh` and `src/hands/doctor.py` reverted to 9b351a8~1, all 7 new tests went red and none stayed green: 2 doctor tests, 2 runbook doc pins, and the hung, multibyte and failed-redactor capture tests. After restoring, `git status --short` was empty.
> 3. **PASS.** `./scripts/check` exited 0. Pytest: `4636 passed in 369.95s (0:06:09)`. Final line: `check: green`.
> 4. **PASS with gaps.** DESIGN.md, `meta/plan.md` and `meta/CHECKPOINT.md` are untouched. Every command the runbook names exists with those arguments: `hands migrate-spool` (no args), `hands jobs --role builder -n 5`, `hands approve <job>`, `hands deny <job> --reason`. `hands cancel` does refuse a held job (`Api.cancel`), `hands go` is refused by `builder_busy` while a builder job is running, queued or held, and migrate-spool's job runs before the handsd start step. The doctor fix is sound: changing `except OSError` to `PermissionError` turned the vanishing-directory test red. The output file is created as mode 600 under `umask 077`, and the redactor writes once, only after reading all its input, so no unredacted partial file is ever on disk.
>    - Mutations that stayed green: dropping `-k 5` from `timeout`, and removing the timeout from `find` and from the python3 read of the job record. No test pins those.
>
> **Should-fix (contradicts the body and the script header's "one that times out is recorded in the file"):**
> - `scripts/capture-quota-stop.sh:105`: a timed-out `find` is not marked. It falls through to line 112's "(no job record under …)", which is false. I reproduced this with a fake `find` that sleeps.
> - `scripts/capture-quota-stop.sh:143`: a timed-out read of the job record leaves `transcript` empty. Line 151 then prints "(no record, or it names no transcript)", which is misleading. Reproduced the same way.
>
> **Not proven:** that the process-group kill reaches grandchildren that call setsid, that a real `hands migrate-spool` on a restored archive succeeds (the body says this too), and the mode-000 doctor test was not checked running as root, where it skips.
>
> The worktree is removed; `/tmp/rev24/hosted` was not touched. The full gate log is at `/tmp/rev24/check-9b351a8.log`.

(The sub-agent's should-fix is carried as blocker 1: the protocol counts a
claim the disk contradicts as a blocker, and the claim is in the commit body
as well as the script.)
