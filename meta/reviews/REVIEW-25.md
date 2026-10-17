# REVIEW-25 — cold review of hands mission 25
reviewed: fbe58a581216722428b701ab2e5b2f0346790fbc

VERDICT: review mission 25 blockers=0 should-fix=3

Shape: pull request, a closer. `meta/BUILDER-25-PROMPT.md` §Branch says
"Pull request. This is a closer: it continues the open branch
`mission-24`". `gh pr list --head mission-24 --state open` returns PR #5
(base `main`, headRefOid `fbe58a5`). The base is the `reviewed:` sha of
REVIEW-24, `53b62cc`. The commits under review (`git log --oneline
53b62cc..origin/mission-24 ^origin/main`):

    fbe58a5 report: mission 25 final report, hosted review dispositions, the PR #5 archive
    4f46bda docs: probe record corrected; re-checks and one Codex approval row
    f0eb0d0 protocol: stale worktree defined; the WARN with a failing playbook line pinned
    f53ec39 tests: pin task_killed's session key and eviction, the ambiguous reason's quoting, the cap's journal share
    2f9e219 kit: staged kit names refused as KitErrors; refused .part removed by handsd
    11cd19c ops: capture script records every timeout; redaction before the cut
    4523e8a plan: mission 25 — plan, checkpoint, H-062 note
    cc2a9e5 Merge branch 'main' into mission-24

One hosted-review sub-agent first, then one sub-agent per unit commit (U1
11cd19c, U2 2f9e219, U3 f53ec39, U4 f0eb0d0, U5 4f46bda), one at a time. I
read the `plan:` commit (U0, 4523e8a) and the `report:` commit (U6,
fbe58a5) myself, and skipped the merge commit cc2a9e5. No commit is a
human-supplied `fixtures:` unit or a `plan: decisions` commit.

## Blockers

None.

## Should-fix

1. **f0eb0d0 (U4) and meta/FINAL-REPORT-25.md §3: the record says less
   than the disk shows about the WARN pin.**
   - The commit body says the mutation `… if book is not None and
     playbook_check.ok` turns the test red in "the no-kickoff case". The
     report's NOT PROVEN says "The kickoff-differs case of the U4 warning
     test did not go red under the `playbook_check.ok` mutation".
   - The U4 sub-agent made that mutation at src/hands/kit.py:1352. Both
     parametrized cases (kickoff differs, no kickoff) went red on
     `len(warns) == 1` (0 found).
   - The record understates the pin rather than overclaiming it. Still, a
     NOT PROVEN line that the disk disproves misleads the next reader
     about which case is unpinned.
   - Fix: correct the report's line (or say which mutation left the case
     green).
2. **11cd19c (U1): after a failed `find`, the capture returns before the
   inbox tail** (scripts/capture-quota-stop.sh:126-128).
   - The inbox tail does not need a job id, but a `find` timeout or failure
     now drops it from the file, along with everything else after the job
     record section. The script is meant to record the first real
     usage-limit stop.
   - The commit body discloses this as a design-silent choice, so it is not
     a blocker.
   - Fix: write the timeout line in the job-record section, skip only what
     needs the record, and still capture the inbox tail. Pin that with the
     hanging-`find` test.
3. **4f46bda (U5): the approval row names a flag form that differs from
   the command it quotes** (docs/HARNESS-PROBE.md:358 vs :556).
   - :358 and the commit body give `-c approval_policy="on-request"`. The
     command actually run and quoted at :556 is `-c
     approval_policy='"on-request"'`, which is the shell quoting that works.
   - Also, a stray line break at :359-360 ("The" / "top-level").
   - Fix: name the form that was run.

## Hosted review

Archive `meta/reviews/hosted/PR-5/6/`, written by the hosted-review
sub-agent's `uv run hands hosted-review 5` in a worktree at
`origin/mission-24` (fbe58a5), exit 0 on the first run (no wait). Verdict
the command took from the Code Review comment: **`verdict: 1 of 9 findings
open in the Code Review comment`**.

Header at fetch 6: `🐞 Bugs (0)  📘 Rule violations (1)  🔗 Cross-repo
conflicts (0)  📜 Skill insights (0)`.
- Against fetch 5, only Code Review comment 6229613578 changed (updated_at
  14:51:09Z → 15:13:10Z), and only its code links moved (4f46bda →
  fbe58a5). The finding text and the struck states are identical.
- The one real change of the closer came at fetch 4 (against REVIEW-24's
  fetch 3): finding 1 went from open (Cross-repo conflict) to struck `✓
  Resolved`, and the Cross-repo count went from 1 to 0. No mission-25
  commit touches runner.py, so the bot re-judged its own finding. The
  report's row admits the strike. Its narrative does not mention the
  header change.

Findings as the command printed them (the current comment's numbering,
the builder's too):

1. "~~Discotrade misses journal reminders~~ ✓ Resolved"
   (src/hands/runner.py[R653-656]). "Runner.run() records the new journal
   preface in the running job but still writes job.prompt, without the
   preface, to Claude. When a discotrade builder answer or CLI send starts
   while meta/journal.md is dirty, the builder misses the instruction to
   commit it before continuing the mission, despite the job record saying
   that instruction was delivered."
   - **Dismissed** (as in REVIEW-24): `job` is rebound by the transition,
     so the prefaced prompt is written. The bot now strikes it itself.
   - Builder: "unchanged since mission 24: dismissed (now struck)".
     **Audit: holds.**
2. "~~Doctor fails on unreadable worktree data~~ ✓ Resolved"
   (src/hands/doctor.py[1837]). "_worktrees_check calls admin.iterdir()
   without handling filesystem errors, although it handles unreadable
   individual worktree records. If a role clone's worktree directory is
   unreadable or disappears during the check, hands doctor exits with a
   generic error instead of reporting its other checks."
   - **Confirmed, fixed in the PR** (9b351a8, upheld by REVIEW-24).
   - Builder: unchanged, fixed in 9b351a8. **Audit: holds.**
3. "~~A restarted kickoff no longer resets the consult count~~ ✓ Resolved"
   (src/hands/daemon.py[R715-719]). "wants_journal_sentence leaves out
   kickoffs only through the in-memory Daemon.kickoffs set. When a hands go
   job (origin cli) is still held or queued across a daemon restart and the
   journal is dirty, the runner rewrites the stored prompt to
   <sentence>\n\n<kickoff>. consults_used recognises a kickoff by
   record.prompt.strip() in kickoffs, so that job no longer resets the
   consultation count, and the pipeline can stop early on max_consults."
   - **Confirmed, fixed in the PR** (b940d6d). §41 now adopts the
     design-silent choice.
   - Builder: unchanged, fixed in b940d6d. **Audit: holds.**
4. "~~Old spool state is skipped after migration~~ ✓ Resolved"
   (docs/OPERATIONS.md[317]). "The new-machine procedure extracts the
   archive and proceeds to daemon startup without running `hands
   migrate-spool` for the flat spool layout that this runbook also
   describes. When the archived state predates per-project spools, the
   daemon reads the new per-project directory instead of the restored jobs,
   roles, inbox and pipeline files."
   - **Confirmed, fixed in the PR** (9b351a8).
   - Builder: unchanged, fixed in 9b351a8. **Audit: holds.**
5. "Sub-agents alter protected metadata" (`📘 Rule violation § Compliance`,
   meta/plan.md[R13-15]). "meta/plan.md and meta/CHECKPOINT.md are changed
   in the U0 plan unit even though the mission's standing constraint
   forbids sub-agents from editing them. The protected metadata therefore
   has a sub-agent-authored change in this PR, contrary to the repository
   workflow requirement." Open.
   - **Dismissed.** Among mission 25's commits only 4523e8a (`plan:`, U0)
     and fbe58a5 (`report:`, U6) touch either file. Both are the
     orchestrator's (BUILDER-25-PROMPT.md, Execution model). No sub-agent
     commit (11cd19c, 2f9e219, f53ec39, f0eb0d0, 4f46bda) touches them.
   - Builder: dismissed with that reason. **Audit: holds.** The builder's
     commit list predates fbe58a5, which also edits plan.md as the
     orchestrator's report, so the reason stands; the row just doesn't
     mention it.
6. "~~Quota capture can abort and leave an empty file~~ ✓ Resolved"
   (scripts/capture-quota-stop.sh[R216-218]). "The script cuts transcript,
   stream-json, grep and inbox lines with cut -c1-4000, then pipes
   everything into a Python redactor that calls sys.stdin.read() in text
   mode. GNU cut -c counts bytes, so a long line whose 4000th byte falls
   inside a multi-byte UTF-8 character (—, § and similar are common in this
   project's transcripts) is split mid-character; under a UTF-8 locale
   stdin decodes strictly, the redactor raises UnicodeDecodeError, and the
   capture fails, leaving only the empty $out that noclobber already
   created."
   - **Confirmed, fixed in the PR** (9b351a8). 11cd19c moved the cut inside
     the redactor, which keeps it fixed.
   - Builder: unchanged, fixed in 9b351a8. **Audit: holds.**
7. "~~Restored held jobs block the kickoff step~~ ✓ Resolved"
   (docs/OPERATIONS.md[331]). "The migration procedure instructs the
   operator to run hands go after startup without first resolving any
   restored builder jobs. When the restored spool contains a held builder
   apply—the condition the preceding step says the start notification can
   announce—Api.kickoff refuses the command because the builder is busy."
   - **Confirmed, fixed in the PR** (9b351a8).
   - Builder: unchanged, fixed in 9b351a8. **Audit: holds.**
8. "~~Kits over about 9.4 MiB can't be applied from the laptop~~ ✓
   Resolved" (src/hands/kit.py[R1495-1501]). "apply_run accepts zips up to
   [files] kit_max_mb (20 MiB by default) and base64-encodes the entire kit
   into one socket request, while call checks that request against the
   daemon's 12.5 MiB LINE_LIMIT. A zip above roughly 9.4 MiB can therefore
   pass the kit-size check but be refused before reaching the daemon with
   an "over the daemon's line room" message, even though the phone's kit
   path accepts the same file."
   - **Confirmed, fixed in the PR** (b940d6d).
   - Builder: unchanged, fixed in b940d6d. **Audit: holds.**
9. "~~Quota capture can hang indefinitely~~ ✓ Resolved"
   (scripts/capture-quota-stop.sh[R69-74]). "capture-quota-stop.sh runs
   hands and journalctl directly without a timeout wrapper. A hung daemon
   or journal query therefore leaves the foreground capture process
   waiting indefinitely instead of reaching its redaction and output
   steps."
   - **Confirmed, fixed in the PR** (9b351a8). 11cd19c finished the job
     (REVIEW-24 blocker 1), so no command is now left unrecorded.
   - Builder: unchanged, fixed in 9b351a8. **Audit: holds.**

Every finding has one row. No H-nnn was filed. Nothing that needed a design
decision was fixed in silence.

## Notes

- **Gate (my one run).** `./scripts/check` passed at the tip `fbe58a5` in a
  fresh worktree (/tmp/rev25/tip): `4659 passed in 470.78s (0:07:50)`, `==
  cli smoke ==`, `check: green`, exit 0.
  - `git diff --name-only 4f46bda fbe58a5` touches only meta/ (the report,
    the bookkeeping, and the archive PR-5/4..5), so the tip's code is
    4f46bda's.
  - Unit counts at each sha: U1 4641, U2 4649, U3 4654, U4 4659, U5 4659,
    tip 4659. U2's 4649 and the tip's 4659 match the report.
- **Review 24's items.** All nine are closed as the report's `## Review
  items` table says. Blocker 1 and should-fix 1 were proven by the U1
  sub-agent's reverts and mutations, should-fix 2 by U2's, should-fix 6–8
  by U3's four named wrong changes, should-fix 4–5 by U4's, and should-fix
  3 by reading (U5). The H-062 note is in FINDINGS.md (4523e8a). `main`
  20aac9f is an ancestor of the branch (cc2a9e5).
- **NOT PROVEN, read against the sub-agents.**
  - The report's §3 holds except for the U4 line (should-fix 1).
  - The U2 sub-agent read the no-builder refusal path's `.part` removal in
    the code (it sits inside the `try` whose `finally` removes the entry).
    It is still untested, as the report says.
  - A socket caller can still name another client's in-flight `.part`, or
    a hardlink, and have the daemon read and delete it. That is same-user
    and disclosed.
  - The remaining redactor bypasses (double JSON escaping, lowercase
    percent-encoding, JSON `\/`, a secret split across lines) are carried
    unchanged.
- **The U5 gate.** The report discloses that U5's three gate runs ran in
  one foreground call. The U5 sub-agent's own run was green at 4659.
- **Schedule (UTC, 2026-10-17; one sub-agent at a time, so only one
  `./scripts/check` runs inside the 20-minute cap).** Start and end as each
  sub-agent reported them from `date -u`:
  - hosted review 15:13:56–15:14:33 (no gate)
  - U1 11cd19c 15:15:16–15:28:00
  - U2 2f9e219 15:28:25–15:36:42
  - U3 f53ec39 15:37:07–16:01:42
  - U4 f0eb0d0 16:02:09–16:09:42
  - U5 4f46bda 16:10:13–16:20:08
  - my gate at the tip 16:20:25–16:28:20
- **A gate run moved to the background (H-069).** The U3 sub-agent called
  `./scripts/check` without an explicit timeout. The harness moved the run
  to the background after 300 s. The sub-agent waited for it in the
  foreground, without starting a second run, and its output shows exit 0.
  So only one gate ran at a time, but the run was not a foreground call as
  the rules want. The U4 and U5 prompts named the 1200000 ms timeout
  explicitly, and those runs stayed in the foreground. Reviewer prompts
  should always name the timeout.
- **Protocol version.** I followed meta/REVIEW-PROTOCOL.md on `main`
  (20aac9f), as the prompt asked. f0eb0d0 adds the stale-worktree
  definition on the branch. Before starting, `git worktree list` showed only
  the main tree. I remove my /tmp/rev25 worktrees after this commit.

## Per-commit verdicts

**Hosted review** (15:13:56–15:14:33)

> Every one of the 9 findings has a disposition row that holds up, and I found no defects in the builder's dispositions. The command exited 0, wrote archive k = 6, and gave the verdict "1 of 9 findings open".
>
> - **Run:** `uv run hands hosted-review 5` in /tmp/rev25/hosted (detached at origin/mission-24, fbe58a5) exited 0 with no retries. It wrote meta/reviews/hosted/PR-5/6/.
> - **Verdict line printed:** `verdict: 1 of 9 findings open in the Code Review comment` (finding 5 is the open one).
> - **Header categories:** 🐞 Bugs (0), 📘 Rule violations (1), 🔗 Cross-repo conflicts (0), 📜 Skill insights (0).
> - **Fetch 6 against fetch 5:** only Code Review comment 6229613578 changed (updated_at 14:51:09Z -> 15:13:10Z). The change is just the code links moving from 4f46bda to fbe58a5. The finding text and struck states are identical.
> - **Fetch 4 against fetch 3:** the one real change happened here. Finding 1 went from open (🔗 Cross-repo conflict) to struck ✓ Resolved, and the Cross-repo count went 1 -> 0. No mission-25 commit touches runner.py, so this was the bot's own re-evaluation. The table's "unchanged since mission 24: dismissed (now struck …)" admits the strike. The narrative above the table doesn't mention the fetch 3 -> 4 header change.
> - **Every row is present:** numbering in FINAL-REPORT-25 follows the current comment, and each title matches the FINAL-REPORT-24 row upheld by REVIEW-24. The fixes are 9b351a8 for 2, 4, 6, 7, 9 and b940d6d for 3, 8; each commit touches its finding's anchor file, and the comment shows all of them struck. The dismissals of 1 and 5 carry reasons. No H-nnn finding was filed, so FINDINGS.md has nothing to check. Nothing that needed a design decision was fixed in silence.
> - **Finding 5's dismissal holds:** among mission-25 commits, only 4523e8a (the `plan:` commit) and fbe58a5 (the builder's U6 report commit) touch meta/plan.md or meta/CHECKPOINT.md. None of the sub-agent commits do (11cd19c, 2f9e219, f53ec39, f0eb0d0, 4f46bda). The dismissal's commit list predates fbe58a5, which the bot re-reviewed last and which edits plan.md. That edit is the orchestrator's, so the reason stands; it just isn't mentioned.
> - **Small extra:** 11cd19c ("redaction before the cut") changed the capture script further, beyond finding 6's fix. It isn't in the hosted table, which is fine since the finding was already struck.

**U1 11cd19c** (15:15:16–15:28:00)

> U1 review of 11cd19c (mission 25, the capture script): I found no blockers. One minor should-fix candidate, below.
>
> 1. **Unit and sections: pass.** The body names mission 25 U1 and DESIGN §41 "The blocker, in the capture script" and "Documentation" (§40 for context). It covers REVIEW-24 blocker 1 and should-fix 1. Only three files changed: the script, `docs/OPERATIONS.md` and `tests/test_runbook.py`. DESIGN.md, meta/plan.md and meta/CHECKPOINT.md are untouched.
> 2. **Test-first revert: pass.** With the parent's script and docs restored, the hung-find, hung-record-read and straddling-secret tests went red. The URL-encoded and ntfy.password tests stayed green, which is expected: they pin redaction the parent already did. After restoring, `git status --short` was empty. I had to run `uv sync --extra dev` first, because the fresh worktree had no pytest.
> 3. **Gate: pass.** `./scripts/check` ran once. Pytest summary: `4641 passed in 390.77s (0:06:30)`. Final line: `check: green`.
> 4. **Design conformance: pass.** `find` and the python3 record read both go through `fetch` (`scripts/capture-quota-stop.sh:103`), which takes its failure line from `failed`; on a timeout the "no job record" and "no transcript" lines are not written. Redaction runs on the whole text first, then each line is cut to 4000 bytes. Each mutation turned its test red: dropping `-k 5`, unbounding `fetch`, unbounding `find` alone, removing the `quote()` form, dropping the ntfy.password read, cutting before redacting. The `docs/OPERATIONS.md` capture section matches the script. No body claim is contradicted by the disk.
>
> **Should-fix candidate (minor):** after a failed `find`, the script returns at `scripts/capture-quota-stop.sh:126-128`, so the inbox tail is not captured, even though it doesn't need a job id. The body discloses this as a design-silent choice.
>
> **Notes:** `fetch` sends stderr to `/dev/null` (`:103`), so a non-timeout failure is recorded with its exit status only. A first unbounding attempt with `command find` failed with exit 127 under `timeout` and was discarded; redone as real unbounding, red.
>
> **Not proven:** a real usage-limit stop, and the redactor bypasses the body lists as remaining (double JSON escaping, lowercase percent-encoding, JSON `\/`, a secret split across lines).

**U2 2f9e219** (15:28:25–15:36:42)

> **2f9e219 (mission 25 U2): holds on all four points. No blocker or should-fix candidates.**
>
> 1. **Unit — holds.** It is U2, "the staged kit". It cites DESIGN §41 "`hands kit apply`'s staging (should-fix 2)" with §40, and REVIEW-24 should-fix 2. It touches `src/hands/kit.py`, `src/hands/api.py` and `tests/test_operations.py`.
> 2. **Test-first — holds.** With `kit.py` and `api.py` reverted to the parent, 4 of the 8 new tests fail: symlink, FIFO, directory, and the bad-name removal case. The other 4 (`..`, missing name, over-cap, failing-kit) pass on the parent because it already behaved that way. After restoring, `git status --short` is empty and `.venv` does not appear.
> 3. **Gate — holds.** `./scripts/check` exits 0: `4649 passed in 392.04s (0:06:32)`; final line `check: green`.
> 4. **Design conformance — holds.** `..`, symlink, FIFO, directory and missing name each come back as a hands error with a reason, never an internal error. The file is opened `O_NOFOLLOW|O_NONBLOCK` and `fstat`ed before it is read (`kit.py:1500-1532`). The removal is in the `finally` at `api.py:752`; the tests use a raw socket client. Four mutations each go red, then were restored: dropping `O_NOFOLLOW` (symlink test), dropping `O_NONBLOCK` (FIFO test, through its guard, no hang), disabling the `staged_path` check (dot-dot test), dropping the `finally` removal (5 tests). `is_staged_name` refuses `/`, `\`, `..` and NUL, so `remove_staged` cannot unlink anything outside `kit_dir`. DESIGN.md, meta/plan.md and meta/CHECKPOINT.md are untouched; the body's "8 tests" and "4649 passed" match.
>
> **Not proven:** the no-builder refusal's removal is untested; reading the code, it sits inside the `try`, so it is removed. A socket caller can name another client's in-flight `.part` (or a hardlink) and have the daemon read and delete it; same-user, as the body discloses.
>
> **Nit:** a `kit_dir` that does not resolve is now reported before a bad kit name, an ordering change the body does not mention.

**U3 f53ec39** (15:37:07–16:01:42)

> f53ec39 passes review: verdict ACCEPT, with no blockers.
>
> 1. **Unit and sections: correct.** U3 of mission 25 ("three pins in the monitor, the api and the runner"). Claims §41 "Smaller rulings", plus §40 (H-062), §39 (H-059, H-060), §2 and §21, and REVIEW-24 should-fix 6, 7 and 8. Only `tests/test_monitor.py` and `tests/test_phone.py` change (+131 lines).
> 2. **All four wrong changes turn their test red** (made, run, restored; `git status --short` empty after every restore): `observe` key `("", kill.task_id)` → two-sessions test fails; `_remember` capping at `TASK_MEMORY + 1` → eviction test fails; `{typed!r}` (`api.py:211`) → backslash-secret test fails; cap counting only `job.prompt` (`runner.py:618`) → only `[dirty]` fails, at `tests/test_phone.py:3189`. With the source restored, all five new cases pass.
> 3. **`./scripts/check`: green.** "4654 passed in 448.55s (0:07:28)", final line "check: green". I forgot the tool's timeout, so the harness moved the run to the background after 300s. It was not restarted: I waited for it in the foreground and the output file shows exit 0. It ran once.
> 4. **Design conformance: matches §41 and the brief.** Two sessions (sess-a, sess-b) fed the same notice twice each, interleaved; exact list checked: each raises bar46gi30 and bs3zkkxlo once. Eviction: t0 still remembered while the memory holds exactly 1024; after the 1025th, t1 still suppressed and t0 raised again. The ambiguous prefix uses `r"Qm7\Zr4\Wk9\Tp2"` as both typed id and `cmd_secret`; published title, message and caplog checked for every substring of 4+ characters. The cap prompt is exactly `"x" * MAX_PROMPT_BYTES`; clean: nothing prepended, done; dirty: killed before start with the §2 cap reason. DESIGN.md, meta/ and src/ untouched; body claims match disk.
>
> Should-fix candidates, minor: the typed text is the secret itself, so typed text with a backslash that is not the secret is not covered (the brief allows this reading); the planted job records are `"{}"` stubs (disclosed).
>
> Not proven: which assertion fires in the M1–M3 failures (only FAILED seen), and the three items the body lists as not proven.

**U4 f0eb0d0** (16:02:09–16:09:42)

> **f0eb0d0** (mission 25 U4) passes on all four points. No blockers and no should-fix items, only one nit in the commit body.
>
> 1. **Unit:** pass. U4 "The warning and the stale worktree", DESIGN §41 "Smaller rulings" and "Documentation", REVIEW-24 should-fix 4 and 5; matches BUILDER-25-PROMPT.md:149-161. kit.py unchanged, explained (the warning was already unconditional), and the code bears that out.
> 2. **Test-first revert:** pass. All three non-test files exist at `f0eb0d0~1`; reverting them turns the protocol test red in both cases (templates and meta) and the handbook §7 test red. The kit-WARN test stays green on revert, as expected. With the mutation `... if book is not None and playbook_check.ok else []` at src/hands/kit.py:1352, both cases go red on `len(warns) == 1` (0 found). **Nit:** the body's "(the no-kickoff case)" understates this: kickoff-differs goes red too.
> 3. **Gate:** pass, exit 0. `4659 passed in 385.87s (0:06:25)`; final line `check: green`.
> 4. **Design conformance:** pass. The definition matches §41 in both protocol files (lines 11-15) and handbook §7 (around line 215); the protocol adds "and you leave it", harmless. Deleting the opening `git worktree remove --force`, the closing `--force`, the closing `prune`, or the definition (closing paragraph at lines 182-184) each turns the test red in both files; deleting the handbook §7 definition goes red. The protocol files differ only at lines 59-61, `<owner>/<repo>` vs `SigorMatt/hands`. DESIGN.md, meta/plan.md, meta/CHECKPOINT.md and src/ unchanged; other body claims match disk.
>
> **Not proven:** whether a reviewer can tell a concurrent or human-made worktree apart, or knows when the current aux job started. The body admits this; the design is silent on how.

**U5 4f46bda** (16:10:13–16:20:08)

> 4f46bda (mission 25 U5): **no blocker; one should-fix candidate.**
>
> 1. **PASS.** U5 (mission 25), DESIGN §41 "The probe record, corrected (should-fix 3)" and "What the probe established", §40's probe procedure, REVIEW-24 should-fix 3. File list matches: `docs/HARNESS-PROBE.md`, modified.
> 2. **PASS.** No tests changed. The only test that reads the file is `tests/test_docs.py:2835`, and it checks only that the file exists. With the file reverted to `4f46bda~1`, `tests/test_docs.py` still gave 169 passed, so nothing pins the content, as the brief's reading-only gate allows. Restored; `git status --short` empty.
> 3. **PASS.** Run once in the foreground: `4659 passed in 490.52s (0:08:10)`; final line `check: green`.
> 4. **PASS, with nits.** Codex VERDICT cell `partial: printed while the task failed[^verdict]`, footnote at :524 pointing at the first `workspace-write` run; opening claim at :8 "verbatim except where marked `…`". The four annotated quotes now carry `…` (:60, :264, :426, :435). OpenCode and dsh re-checks quoted at :93-118, both rows `unavailable` with reasons; only the presence of `DEEPSEEK_API_KEY` checked (`unset`). The Codex approval row under Gaps (:546-576): no approval event, no `command_execution` item, bwrap failed, exit 0, `/tmp/outside-probe` absent before and after, `rm -f` afterwards; confirmed absent now. Table, footnote, Gaps and body (:358-360) agree. `grep -c redacted` = **3**. No key, token or sign-in content; email-shaped strings are the scratch repo's dummy commit email (:19, :550) and npm package names. DESIGN.md, meta/plan.md, meta/CHECKPOINT.md untouched.
>
> **Should-fix candidate (minor):** `docs/HARNESS-PROBE.md:358` and :556: the text and the commit body give `-c approval_policy="on-request"`, but the command run (:556) is `-c approval_policy='"on-request"'`, the correct shell quoting; the doc should name that form. Stray line break at :359-360 ("The" / "top-level").
>
> **Not proven:** that the quoted Codex, OpenCode and dsh outputs are real (no harness run); "./scripts/check green three times" in the body; that the approval run's stderr had only the one line.
