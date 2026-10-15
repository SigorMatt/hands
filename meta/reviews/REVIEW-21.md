# REVIEW-21 — cold review of hands mission 21
reviewed: 2b5a7fcbdc07abf89d1c2ed60186650fd73dc478

VERDICT: review mission 21 blockers=0 should-fix=3

Shape: pull request, closer. `meta/BUILDER-21-PROMPT.md` names the open branch
`mission-20`. `gh pr list --head mission-20 --state open` returns PR #2 (base
`main`, headRefOid `2b5a7fc`). For a closer the base is the `reviewed:` sha of
the branch's previous review, REVIEW-20: `62f5618`. Commits under review,
first-parent (`git log --oneline 62f5618..origin/mission-20`):

    2b5a7fc report: mission 21 final report
    37d2c51 playbook: an engine-approved apply that removes the playbook stops the pipeline
    3dc5a32 protocol: the revert step checks out <sha>~1 for the listed files; no stash
    056f044 doctor, api: socket sends cannot claim origin phone; the live kit is the clone's and doctor's own
    97d1666 guard: the live hook runs python3 -I; --write refuses writes through a hardlink
    44f7494 runner: the cancel race — judge transitions on disk, reload after the advance
    24aaba3 plan: mission 21 plan, branch mission-20 continued, H-046..H-048
    5dfab55 Merge branch 'main' into mission-20

The merge brings in `8bacc66` (review: mission 20) and `1c68883` (the kit). The
protocol I followed is the one on `main` at review time. Its revert step still
says "`git stash` the non-test files", and U4 rewrites that on the branch. Every
sub-agent used `git checkout <sha>~1 -- <files>` instead, which is U4's wording,
because a fresh worktree has nothing to stash.

One sub-agent ran per unit commit (U1–U5), each in its own worktree. I read the
`plan:` (U0) and `report:` (U6) commits myself.

## Blockers

None.

## Should-fix

1. **U1's body and FINAL-REPORT-21 §2 overstate the daemon test (44f7494).**
   - The U1 body says the new daemon test "fails without the spool change (the
     job ended `done`)". FINAL-REPORT-21 §2 says "The daemon test is red without
     either half of the change."
   - On disk it is not. With only `src/hands/spool.py` reverted to `44f7494~1`,
     `test_a_cancel_during_the_clone_advance_ends_killed_and_spawns_nothing`
     passes. The U1 sub-agent found this and I re-ran it: `-k cancel`, 4 passed.
     The runner's own reload covers that path.
   - So no daemon-level test needs the on-disk judgement in `Spool.transition`.
   - The spool half is still proven at unit level: `test_spool`'s stale-object
     test is red without it.
   - I carry this as should-fix, not a blocker, because the product behaviour
     each half claims is tested. Only the report's sentence about which test is
     red is false.
   - Fix: correct the sentence in the next report. Optionally add a daemon test
     whose stale transition comes from a caller other than the runner's
     post-advance path.
2. **The protocol's new revert step fails for a commit that adds a non-test file
   (3dc5a32; §37 shares it).**
   - If a listed file does not exist at `<sha>~1`, `git checkout <sha>~1 --
     <files>` exits 1 with `pathspec … did not match`. It then reverts none of
     the files, not even the ones that existed (the U4 sub-agent showed this in
     a scratch repo).
   - A sub-agent that misses the error runs the tests against unreverted code,
     sees green, and reads that as "the tests are not test-first".
   - The opposite failure is the dangerous one: it hides a weak test behind a
     red run caused by the missing file.
   - DESIGN §37 prescribes this exact wording, so the fix is a finding: files
     the commit adds are removed (`git rm -q --cached` plus delete, or `rm`),
     not checked out from the parent.
   - Note the protocol's own wording differs from §37's by one word: "run the
     commit's new tests" against "run the new tests". Harmless.
3. **docs/INTEGRATION.md still spells the hook as `python3 <path>` (97d1666).**
   - docs/INTEGRATION.md:1135 has `python3 <path to .claude/hooks/bash_guard.py>
     --write`, and the U2 sub-agent reports the same around :261-265. Doctor now
     accepts only `python3 -I <guard>`, so a settings file written by hand from
     the doc FAILS doctor.
   - It fails closed: the hook never runs unprotected.
   - FINAL-REPORT-21 §3 discloses this as "left over" for mission 22, but no
     finding records it. Mission 22's rewrite of the document should carry it
     by name.

## Hosted review

`qodo-code-review[bot]` reviewed PR #2 once, on 2026-10-14T21:51Z: review on
`62f5618` plus nine inline comments. It posted no new review on mission 21's
commits. It did edit its summary comment 6179289830 at 2026-10-15T03:03:56Z,
25 s after the tip `2b5a7fc` was pushed, re-scoring the same nine findings at
the tip. Each finding is quoted verbatim by its title, numbered as in the
updated summary:

1. "A live check deletes an existing kit" (marked "✓ Resolved" by the bot):
   **confirmed resolved, not carried.**
   - It was REVIEW-20 should-fix 5. The U3 sub-agent verified the fix at 056f044:
     an exclusive `mkdir` of `kits/hands-doctor-live-<8 hex>`, an existing path
     FAILS the row and is left untouched, and only the directory doctor created
     is removed.
2. "Cancelled architect or driver jobs can start running anyway" (marked
   "✓ Resolved"): **confirmed resolved, not carried.**
   - It was REVIEW-20 blocker 1. The U1 sub-agent verified 44f7494: a cancel
     during a slow fake advance ends `killed`, spawns nothing, and files nothing
     after `job.killed`.
3. "Fake shell commands can block tests indefinitely" (tests/fake_claude.py):
   **dismissed.**
   - The reason is as in REVIEW-20: the scripted commands are each test's own
     fixture. A stuck one hangs the gate visibly, cannot make it pass falsely,
     and nothing ships from tests/.
4. "Code review depends on shell-history checks"
   (templates/REVIEW-PROTOCOL.md): **dismissed.**
   - The reason is as in REVIEW-20: DESIGN §35/§36/§37 specify the protocol's git
     commands. They are its content, not shell history.
5. "Socket sends can publish as phone answers" (marked "✓ Resolved"):
   **confirmed resolved, not carried.**
   - It was REVIEW-20 should-fix 3. The U3 sub-agent verified that `Api.send`
     refuses `origin: phone`, naming `answer`.
   - It also verified that the new `Api.go_builder` is outside `COMMANDS` and
     `KIT_METHODS`, so `Api.method` never hands it to a socket client.
6. "Driver jobs alter the repository before work" (src/hands/runner.py):
   **dismissed.**
   - The reason is as in REVIEW-20: §36 "The runner" requires handsd to advance
     the clone before every architect and driver job. The driver's read-only
     rule governs the role's own commands under the guard.
7. "The mission report omits auditable evidence" (meta/FINAL-REPORT-20.md):
   **dismissed.**
   - The reason is as in REVIEW-20: short shas are the repository's convention,
     and the review records the full tip as `reviewed:`.
   - This review's sub-agents reproduced the gate counts (4227, 4251, 4258,
     4260, 4261 passed).
8. "Architect can edit outside files through a planted hard link" (marked
   "✓ Resolved"): **confirmed resolved, not carried.**
   - It was REVIEW-20 should-fix 2. The U2 sub-agent verified 97d1666 and tried
     six bypasses, all refused: MultiEdit on an absolute path, a `..` spelling, a
     new file while a hardlink sits deep under kits, an edit into a missing
     folder, a write through an outside symlink, and an unlistable subdirectory.
   - The architect's Bash table has no `ln`, so it cannot create a hardlink
     after the check.
9. "Live architect check fails when the clone is the role's own folder" (marked
   "✓ Resolved"): **confirmed resolved, not carried.**
   - It was REVIEW-20 should-fix 4. The U3 sub-agent verified that `--repo` is
     `driver_clone`'s answer (`.` for the cwd-as-clone layout) and that a row
     with no clone FAILS before the turn.

## Notes

- **Gate.** Every unit commit is green at its own sha: U1 4227, U2 4251, U3 4258,
  U4 4260 and U5 4261 passed, each `check: green`, with no flakes even though the
  five sub-agents ran concurrently.
  - The tip `2b5a7fc` differs from `37d2c51` only in meta/ files
    (CHECKPOINT, FINAL-REPORT-21, journal, plan), so the U5 run covers the
    tip's code.
- **U0 (24aaba3).** It follows the merge of `main` (5dfab55) as the brief
  requires.
  - It files H-046, H-047 and H-048 in meta/findings/FINDINGS.md, each `Status:
    open (scheduled for mission 22)`.
  - It touches only meta/plan.md, meta/CHECKPOINT.md, meta/journal.md and
    FINDINGS.md, all of them listed in its body.
- **Forbidden files.** No unit commit touches DESIGN.md. Only the orchestrator's
  `plan:` and `report:` commits touch meta/plan.md and meta/CHECKPOINT.md.
- **Review items table.** Every row of FINAL-REPORT-21's table (REVIEW-20 blocker
  1, should-fix 1–6, the note on U5) is borne out by the sub-agent of the unit it
  names. Should-fix 1 above concerns a sentence in §2, not a row of that table.
- **Report §NOT PROVEN against the sub-agents.** Everything the report lists is
  confirmed as unproven, and nothing it claims as proven was contradicted except
  should-fix 1. The sub-agents add:
  - U1: `save_job(job)` at runner.py:664 and :933 still writes the whole
    in-memory object without consulting disk. No path changing state in those
    windows was found, but none is ruled out.
  - U3: argv judging accepts `--repo X`, `--repo=X` and `--project X`. Any other
    value-taking flag would be miscounted as the kit path, which fails a genuine
    check and never passes a false one.
  - U3: if the role replaced `kits/` itself with a symlink during the turn,
    cleanup would remove the same-named directory at the target. The role's
    settings make this unlikely, and it is untested.
  - U5: a human-approved apply that deletes the playbook still ends chaining with
    no stop. That is outside §37's "the engine approved itself", and it is
    unpinned.
  - U5: a non-default `playbook.path` in the reason is untested.
  - U2: a hook directory whose path contains a space is untested.
- **Tooling.** In a fresh worktree `uv run pytest` fails to spawn pytest until
  the `dev` extra is synced. `./scripts/check` does that sync itself, so this is
  not a gate defect.

## Per-commit verdicts

**U1 44f7494** — PASS on 1–4. One commit-body claim is false.
1. Unit: mission 21 U1, "The cancel race"; §37 with §6; REVIEW-20 blocker 1.
2. Test-first: PASS. With both halves reverted, both new tests are red
   (`'done' == 'killed'`; `DID NOT RAISE IllegalTransition`). With runner.py
   alone reverted, the daemon test is red (the worker logs the refused
   transition at daemon.py:655). With spool.py alone reverted, only the
   stale-object test is red and the daemon test PASSES, contrary to the body.
3. Gate: green. `4227 passed in 519.57s (0:08:39)`, `check: green`.
4. Design: PASS. spool.py:653 reloads by id and judges on disk, and a stale
   caller writes nothing (byte-identical). runner.py:625-630 reloads after the
   advance with no await before the transition, and when the job is not `queued`
   it raises RunnerError and spawns nothing. All 7 transition callers were
   checked; none depends on in-memory edits before transition.
NOT proven: an end-to-end need for the spool half; other callers' windows;
`save_job` at runner.py:664/:933 writes the object without a disk check.

**U2 97d1666** — PASS on 1–4. Defect in the docs only.
1. Unit: mission 21 U2; §37 "The live hook" and "Writes through a hardlink";
   REVIEW-20 should-fix 1, 2; REVIEW-18 should-fix 2, 4. Six files, as listed.
2. Test-first: PASS. With the four product files at `~1`, 23 new cases are red.
   Three stay green by design: the clean-kits write, the PYTHONPATH case, and a
   plain directory or text file beside the guard.
3. Gate: green. `4251 passed in 529.42s (0:08:49)`, `check: green`.
4. Design: PASS.
   - Both settings files read `python3 -I "$CLAUDE_PROJECT_DIR"/.claude/hooks/bash_guard.py`
     (`--write` for the write hook).
   - `_beside_the_guard` FAILS the row naming the entry.
   - The self-test runs the settings' command via `/bin/sh -c`.
   - `write_link_problem` refuses nlink>1 targets and every write while the kits
     walk reports anything. Six bypasses were tried and all refused.
   - No other shipped file spells the hook without `-I`.
Defect: docs/INTEGRATION.md:261-265 and :1135 still say `python3 <path>`. It
fails closed.
NOT proven: Claude Code running the hook via `/bin/sh` with the role's cwd and
environment; a hardlink created between the check and the write by another
process; a hook path that contains a space.

**U3 056f044** — PASS on 1–4. No defects.
1. Unit: mission 21 U3; §37 "Provenance of an `answer`" and "`doctor --live`
   for the architect", with §32; REVIEW-20 should-fix 3, 4, 5.
2. Test-first: PASS. With the product files at `~1`, the new tests are red. With
   `live_kit_name` stubbed into the old doctor.py, the six new live tests are
   still red on behaviour.
3. Gate: green. `4258 passed in 515.14s (0:08:35)`, `check: green`.
4. Design: PASS.
   - `Api.send` refuses `origin: phone`, naming `answer` (api.py:220).
   - `go_builder` is outside `COMMANDS` and `KIT_METHODS`, so `Api.method`
     (api.py:185) never dispatches it. No other `send` with origin phone remains.
   - `--repo` comes from `driver_clone` (doctor.py:2051-2059), and a row with no
     clone FAILS before the turn.
   - `_kit_check_names` (doctor.py:1986) requires the kit path and the clone.
   - The kit name comes from `secrets.token_hex(4)` and is created with an
     exclusive `mkdir`. An existing path FAILS the row and is left untouched.
   - Cleanup (doctor.py:2138) does not follow a symlinked kit dir.
NOT proven: a real claude turn; argv forms beyond the three; `kits/` replaced by
a symlink during the turn.

**U4 3dc5a32** — PASS, with a gap that §37 shares.
1. Unit: U4; §37 "The protocol's revert step"; REVIEW-20 should-fix 6.
2. Test-first: PASS. `test_the_protocol_reverts_by_checkout_and_never_says_stash`
   (tests/test_kit.py:1033) is red for both files at `~1` (assert at :1040) and
   green when they are restored.
3. Gate: green. `4260 passed in 529.34s (0:08:49)`.
4. Design: PASS.
   - The sentence matches §37, except "the commit's new tests".
   - No "stash" appears in either file, in any case.
   - The two files differ only at lines 41-43 (`<owner>/<repo>` against
     `SigorMatt/hands`), and nothing else changed.
   - Gap: when a listed file is new at `<sha>`, `git checkout <sha>~1 -- a b`
     exits 1 with a pathspec error and reverts nothing (templates/ and
     meta/REVIEW-PROTOCOL.md:57-59). This needs a finding.
NOT proven: a sub-agent following the step; commits that rename or delete files.

**U5 37d2c51** — PASS on 1–4. No defects.
1. Unit: mission 21 U5; §37 "An apply that leaves no playbook", §36 "The engine"
   (H-044); the REVIEW-20 note on U5.
2. Test-first: PASS.
   `test_end_to_end_an_apply_that_removes_the_playbook_stops_the_pipeline` is red
   with playbook.py at `~1` (TimeoutError: no stop) and green when it is
   restored.
3. Gate: green. `4261 passed in 498.65s (0:08:18)`, exit 0.
4. Design: PASS.
   - The stop sits inside the existing `builder.done` + `_engine_applied_kit`
     branch (playbook.py:1634-1641).
   - It fires only when no book and no load error exist, which `load_playbook`
     produces only on `FileNotFoundError` (:596-598).
   - `_load`'s stop is unchanged.
   - The reason is `config.playbook.path` as configured.
   - §10 no-playbook mode cannot reach it.
   - The test asserts that no kickoff was sent.
NOT proven: a non-default or absolute `playbook.path`; a deleted but uncommitted
playbook; a human-approved apply that deletes the playbook (no stop, outside §37).
