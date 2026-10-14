# REVIEW-20 — cold review of hands mission 20
reviewed: 62f5618a00c1d6f2e37548daf9915ac9a0d3558a

VERDICT: review mission 20 blockers=1 should-fix=6

Shape: pull request. `gh pr list --head mission-20 --state open` returns PR #2
(base `main`, headRefOid `62f5618`). This is the branch's first review, so the
base is `git merge-base origin/main origin/mission-20` = `238a57b` (`plan:
mission 20 kit (DESIGN v3.19)`). Commits under review (`git log --oneline
238a57b..origin/mission-20`):

    62f5618 report: mission 20 final report
    2e9a6ca notify: titles and topics name the project; the mission-less kickoff
    6a3f2f2 review-18: non-ASCII ntfy_url, isolated guard self-test, checked-bytes kit hash, hardlinks under kits
    61a2417 guard: architect cp from the clone into the kits; builder/aux Bash timeouts 900000
    187e38e phone: answer <secret> <text> delivers a keep send to the builder
    337db9a engine: reload the committed playbook after its own apply; decide a role kit's hold before publishing
    de2e34c runner: advance the role's clone to origin/<branch>; HANDS_PROJECT from the config
    0eb37bc architect: allow the three writes under kits/; doctor judges them, live too
    7326386 protocol: direct only when the brief says so; no PR is a blocker; <branch>
    4752ace tests: hermetic HANDS_* environment; doctor's gh row reads github.com's active account
    1977864 plan: mission 20 plan, branch mission-20, H-041..H-045

The protocol followed is the one on `main` at review time (meta/REVIEW-PROTOCOL.md
at 238a57b). U2 rewrites it on the branch, but that text is not on `main` until
the merge. One sub-agent ran per unit commit (U1–U9), each in its own worktree.
I read the `plan:` (U0) and `report:` (U10) commits myself.

## Blockers

1. **A cancelled architect or driver job can run anyway (U4, de2e34c).** This
   breaks DESIGN §6 "a cancel stays `killed`" and the §6 edge table, where
   `killed` is terminal.
   - At src/hands/runner.py:613-620, `Runner.run` awaits `advance_clone` before
     the job leaves `queued`. That is a `git fetch` plus a `git checkout`, each
     bounded at `ADVANCE_TIMEOUT_S` = 300 s.
   - The job has already left `_waiting`. A `hands cancel` in that window takes
     the queued branch of `Daemon.cancel` (src/hands/daemon.py:838-847): it
     writes `killed`, files `job.killed` and ends the consultation.
   - When the fetch returns, `self.spool.transition(job, "running", …)` checks
     the edge against the in-memory record read before the await
     (src/hands/spool.py:647: `record = … else job`). That record is still
     `queued`, so the transition overwrites `killed` with `running`, and claude
     is spawned for a cancelled job whose consultation the engine has already
     closed.
   - The U4 sub-agent reproduced this at runner level (final record `done`, not
     `killed`). The hosted review raised it independently (finding 2).
   - The window existed before, at milliseconds (the `_isolation` / `_git_head`
     awaits). U4 widens it to a network fetch.
   - Fix: reload the record after the advance and stop if it is no longer
     `queued`, or enter `running` before advancing so cancel takes the in-flight
     path. Add a test that cancels during a slow fake advance and expects
     `killed` and no spawn.

## Should-fix

1. **The live hook is still shadowable, and doctor now says it is fine (U8,
   6a3f2f2).**
   - src/hands/doctor.py:1104 runs the guard's self-test as `python3 -I` with
     `PYTHONPATH=""`, which matches §36's letter.
   - The hook Claude Code actually runs is still `python3 <guard>`. With a
     `shlex.py` planted beside the guard, the U8 sub-agent saw that hook exit 0
     on `rm -rf`, while the `-I` self-test is green and the row is `ok`.
     tests/test_doctor.py:2555 pins that `ok`.
   - So REVIEW-18 should-fix 2's probe still defeats the live guard. Doctor's
     green now certifies a hook that allows everything.
   - FINAL-REPORT-20 §3.8 discloses this. It needs a finding: fail the row on
     any `.py` file or package beside the guard, or put `-I` in the hook command.
2. **Write/Edit/MultiEdit write through a hardlink under `kits/` (U3 + U8).**
   - U3 gives the architect `Edit(kits/**)`, `Write(kits/**)` and
     `MultiEdit(kits/**)`.
   - U8's `st_nlink > 1` refusal applies to the `cp`/`mv` rows only.
     `write_violation` (driver/hooks/bash_guard.py:1363) checks realpath
     containment alone, so a regular file `kits/h` hardlinked to the guard
     passes the `--write` hook.
   - §36 names only `cp` and `mv`, so this is not a design violation, but it is
     the same attack REVIEW-18 should-fix 4 described. It was raised by the
     hosted review (finding 8) and the U8 sub-agent.
   - Whether Claude Code writes in place is not proven. File a finding: refuse a
     write target with `st_nlink > 1`, or refuse every write while
     `kits_symlink(kits, hardlinks=True)` reports anything.
3. **A socket client can make a job look like a human's phone `answer` (U6,
   187e38e).**
   - `is_builder_answer` (src/hands/spool.py:871-875) decides from role, context
     and `origin == "phone"`.
   - `Api.send` (src/hands/api.py:193-223) refuses only `origin: architect` from
     socket clients, so a raw socket `send` of a builder `keep` job with
     `origin: "phone"` passes.
   - Its reply is then published titled `builder`, and its prompt is listed to
     the architect under "Decided by the human since your last consultation".
   - §32 already closed the same provenance hole for `architect`. The hosted
     review raised this one (finding 7).
   - Fix: refuse `origin: phone` on `send` as `architect` is refused, or mark
     answers with a field only `answer_builder` sets.
4. **`doctor --live` for the architect judges the wrong repo, and judges it
   weakly (U3, 0eb37bc).**
   - src/hands/doctor.py:1947 hard-codes `hands kit check … --repo ./repo`, but
     `driver_clone` (src/hands/config.py:195-202) also accepts the role's cwd
     itself as the clone. On that supported layout the turn checks a missing
     `./repo` and the row fails on a valid setup (hosted finding 9).
   - The success test only looks at `argv[:3] == ["hands","kit","check"]` plus
     the `PASS paths: 1 files` substring. So a `hands kit check` of any one-file
     kit, against any repo, passes the step.
   - Fix: pass `--repo` the resolved clone, fail when there is none, and require
     the live kit's path in the judged command.
5. **`doctor --live` deletes an existing kit (U3, 0eb37bc).**
   - src/hands/doctor.py:1944-1946 remove `kits/hands-doctor-live` recursively
     before the turn, whatever it holds.
   - A diagnostic should not destroy a directory it did not create. Use a unique
     per-run name, or refuse when the path exists (hosted finding 1).
6. **The protocol's revert step does not work as written (U2, 7326386; the
   sentence is older than U2, U2 kept it).**
   - templates/REVIEW-PROTOCOL.md:57 and meta/REVIEW-PROTOCOL.md:57 tell the
     sub-agent to "`git stash` the non-test files". In a fresh worktree at the
     commit there is nothing uncommitted to stash.
   - Every sub-agent of this review used `git checkout <sha>~1 -- <non-test
     files>`, then restored the files. The text should say that.

## Hosted review

`qodo-code-review[bot]` posted on PR #2 at 21:51:44Z: the summary comment
6179289830, "🐞 Bugs (5) 📘 Rule violations (4)", plus review 5525172643 with
nine inline comments. Each finding is quoted verbatim by its title:

1. "A live check deletes an existing kit" (src/hands/doctor.py:1946):
   **confirmed** → should-fix 5.
2. "Cancelled architect or driver jobs can start running anyway"
   (src/hands/runner.py:620): **confirmed** → blocker 1. The U4 sub-agent
   reproduced it separately.
3. "Driver jobs alter the repository before work" (src/hands/runner.py:618):
   **dismissed**. §36 "The runner" requires exactly this: handsd's runner
   advances the clone before every architect and driver job. The driver's
   read-only rule governs the role's own commands under the guard, not
   handsd's.
4. "Code review depends on shell-history checks"
   (templates/REVIEW-PROTOCOL.md:18): **dismissed**. The protocol is a
   procedure, and DESIGN §35/§36 specify its commands (`git log
   <base>..origin/<branch> ^origin/main`, the merge-base). The commands are the
   protocol's content, not shell history.
5. "The mission report omits auditable evidence"
   (meta/FINAL-REPORT-20.md:36): **dismissed**. Short shas are this
   repository's convention; the review records the full tip as `reviewed:`. The
   gate counts were reproduced by this review's sub-agents and by the tip run
   (see Notes). Embedding raw output is not required by the brief or the design.
6. "Fake shell commands can block tests indefinitely" (tests/fake_claude.py:256):
   **dismissed**. The scripted commands are each test's own fixture. A stuck one
   hangs the gate visibly and cannot make it pass falsely, and nothing ships
   from tests/.
7. "Socket sends can publish as phone answers" (src/hands/spool.py:875):
   **confirmed** → should-fix 3.
8. "Architect can edit outside files through a planted hard link"
   (architect/settings.json:32): **confirmed** → should-fix 2. It is outside
   §36's letter, which names `cp`/`mv`, so it is not a blocker.
9. "Live architect check fails when the clone is the role's own folder"
   (src/hands/doctor.py:1947): **confirmed** → should-fix 4.

## Notes

- **Gate at the tip.** I ran `./scripts/check` once at 62f5618 in a worktree,
  with `HANDS_PROJECT=hands` and `HANDS_JOB` set (this review is itself a hands
  job): `4225 passed in 364.75s (0:06:04)` / `check: green`. The tip differs
  from 2e9a6ca only under meta/.
- **The sub-agents' single runs** were 4059, 4076, 4092, 4105, 4110, 4131,
  4180, 4212 and 4225, all green. They match FINAL-REPORT-20 §1 wherever it
  gives a count; U3's count is not in the journal, and the run gave 4092. Each
  unit's "3/3" (§3.12) is still the builder's own claim.
- **Test-first holds for every unit.** Reverting each commit's product files
  turned its new tests red: U1 7, U2 18, U3 15, U4 13, U5 3, U6 22, U7 14, U8 25
  and U9 11+.
  - The tests that stay green are the ones the bodies call "as before" pins: U5's
    two not-approved holds, and U3's `Edit(~/**)`, which the older wholesale
    check already rejects.
- **FINAL-REPORT-20 §NOT PROVEN agrees with what the sub-agents found.** Items
  1–7 and 10–13 are as stated.
  - Item 8 (live hook without `-I`) is real and was reproduced; it is carried as
    should-fix 1.
  - Item 9 (`apply_from_zip` re-reads the path) is as stated.
  - Nothing on disk contradicts the report.
  - The report does not mention the cancel race (blocker 1).
- **Forbidden files.** No unit commit (U1–U9) touched DESIGN.md, meta/plan.md or
  meta/CHECKPOINT.md. Only the orchestrator's U0/U10 touched plan and
  checkpoint. Every unit body lists every file in its diff.
- **Disclosed departures.** U9 touched README.md (one `ntfy_topic` setup line,
  which §36 covers) and docs/PLAYBOOK.md, and committed before its three runs.
  Both are named in the body and the report. U7 left runner.py unchanged
  because `spawn_env` already feeds `job_env`.
- **Minor observations, not counted:**
  - U4: the `ADVANCE_TIMEOUT_S` definition sits between `FAILURE_REASONS`'s
    `#:` doc block and the tuple (runner.py ~216-235).
  - U5: an apply that deletes the playbook ends chaining with no stop (§10's
    no-playbook path), while §36 says a playbook that no longer loads stops the
    pipeline.
  - U6: "since the last consultation" uses `git log --since`, which goes by
    committer date and so depends on the clock. It also compares repo-root paths
    to `meta/decisions`, which breaks for a cwd below the repo root.
  - U6: "titled builder" is published for `answer` jobs only, a defensible
    reading of §36's paragraph.
  - U7: a trailing-slash symlink source (`cp -r repo/dl/ kits/dl`) passes
    because `lstat` follows the slash. No link lands in kits.
  - U9: the `topics` row reads "lacks" as not being a substring (§3.10), and
    the U5 approval line publishes as `<project>: hands: kit …`.
  - docs/ARCHITECT-HANDBOOK.md still describes the old review range. That is
    mission 21's, as FINAL-REPORT-20 §5 says.
- **With blocker 1, the PR stays open.** Not merged.

## Per-commit verdicts

**4752ace** (U1): PASS, no defects.
1. Unit: mission 20 U1, hermetic tests and doctor's gh row. Claims DESIGN §36 "Hermetic tests (H-040)" and "Doctor's `gh` row", plus review 19 should-fix 3, 4, 5. PASS
2. Test-first: with `HANDS_PROJECT=x HANDS_JOB=y`, restoring the parent's `src/hands/doctor.py`, `docs/INTEGRATION.md`, `docs/PLAYBOOK.md` and `tests/conftest.py` makes all 7 new tests fail (2 in test_hermetic.py, 3 gh tests in test_doctor.py, 2 in test_docs.py). Restored, all 7 pass. Without the `HANDS_*` vars the hermetic tests pass regardless, as the module docstring says. PASS
3. Gate (`HANDS_PROJECT=x HANDS_JOB=y ./scripts/check`, one run): `4059 passed in 498.72s (0:08:18)` … `== cli smoke ==` … `check: green`. PASS
4. Conformance: `gh auth status --active --hostname github.com` at `src/hands/doctor.py:536`; every row WARN now names the `gh auth login` remedy, including `--version did not answer` (:530) and `auth status did not run` (:538-542); the conftest fixture is autouse and clears every `HANDS_*`; PLAYBOOK sentence reworded; H-040 resolved. No DESIGN.md / meta/plan.md / meta/CHECKPOINT.md touch; the body lists all 9 files. PASS
NOT proven: real `gh` output for `--active --hostname` (fake only, as the body says); a `gh` too old for `--active` would show "not logged in" rather than "unsupported flag". It is still a WARN with the remedy, minor and untested.

**7326386** (U2): PASS, no blockers; one minor should-fix that predates the commit.
1. Unit: mission 20 U2, review protocol. Claims DESIGN §36 "The review protocol" and §35 "The review", review 19 should-fix 1 and 2, HF-007, HF-008. The body lists all 3 files. PASS
2. Test-first: with both protocol files reverted to `7326386~1`, test_kit.py + test_docs.py give 18 FAILED (16 parametrized §36 sentence tests, the branch-named-once test, the updated §35 test). Restored clean. PASS
3. Gate: `./scripts/check` (`env -u HANDS_PROJECT -u HANDS_JOB`), one run: `4076 passed in 508.62s (0:08:28)` / `== cli smoke ==` / `check: green`. PASS
4. Conformance: every §36 sentence is present and coherent: Direct only on "Direct" (template L10–14); no PR gives blocker "no pull request for <branch>" and stops (L23–26); `<branch>` named once; `git log <base>..origin/<branch> ^origin/main` with the merge-base (L27–32); tests-only commits get their wrong changes made and red expected, naming none is a blocker (L58–62); sub-agents one at a time, one check each, the reviewer's own run once at the tip (L50–52, 63, 69–71). The template vs meta `diff` after `<owner>/<repo>`→`SigorMatt/hands` is empty. Forbidden files untouched. PASS
Defects: minor should-fix (predates the commit): `templates/REVIEW-PROTOCOL.md:57` (and the meta copy) says to `git stash` the non-test files, which cannot work in a fresh worktree at the commit; `git checkout <sha>~1 -- <non-test files>` is what works. Drift the body admits: docs/PLAYBOOK.md and docs/ARCHITECT-HANDBOOK.md still use `mission-N` without `^origin/main`.
NOT proven: no reviewer has run against the new text; the kit-check gate was not run on its own (`test_the_filled_missions_templates_pass_six_of_six…` at test_kit.py:1056 passed inside the suite); a brief that neither says "Direct" nor names a branch is not covered.

**0eb37bc** (U3): PASS with two minor gaps, no blocking defects.
1. Unit: PASS. U3 "The architect role's write permission", §36 with §31, H-041 resolved. The body lists all 6 files; DESIGN.md / meta/plan.md / meta/CHECKPOINT.md untouched.
2. Test-first: PASS. With `architect/settings.json` and `src/hands/doctor.py` reverted to `0eb37bc~1`, 15 architect tests go red: shipped settings, each of the 3 missing allows, 4 bad specifiers, the live pass, all 5 live-failure cases, and the empty spool. `Edit(~/**)` stays green, as expected, because the older wholesale check (§32/§33) already rejects it. Restored clean.
3. Gate: PASS. `4092 passed in 433.89s (0:07:13)` / `== cli smoke ==` / `check: green`.
4. Conformance: PASS. Settings add exactly `Edit(kits/**)`, `Write(kits/**)`, `MultiEdit(kits/**)`. `_settings_write_allows` fails on a missing allow, a bare `Write`, other case, `./kits/**` or spacing. `_architect_live` judges the write from the file and content on disk, judges kit check and show from the stream, removes the kit itself, and names the missing step. A turn that only claims success cannot pass.
Minor defects: the live check matches only `argv[:3] == ["hands","kit","check"]` plus `LIVE_KIT_CHECKED` in the text, so any one-file kit check passes; it should also require `kits/hands-doctor-live` and `--repo`/the clone path. It also ignores the result's `is_error`, deliberately (the FAIL for no brief), so everything rests on one substring.
NOT proven: a real `claude -p` turn under the real permission layer and guard (body admits it); that Claude Code resolves `kits/**` against the role's cwd; `--repo ./repo` assumes `<cwd>/repo` (if `driver_clone` falls back to the cwd, the row fails).

**de2e34c** (U4): conformant and green, with one real defect (D1) the commit makes much worse.
1. Unit/sections: §36 "The runner" + §31, §29 (no clone), §6 (failure vocabulary). The body lists all 8 files; DESIGN.md / meta/plan.md / meta/CHECKPOINT.md untouched.
2. Test-first: PASS. With runner.py, config.py and doctor.py reverted to `de2e34c~1`, 13 new tests are red: 8 test_runner (driver/architect advance, trunk branch, unreachable origin ×2, HANDS_PROJECT ×3), 4 test_doctor, 1 test_config. Restored clean.
3. `./scripts/check`: green, `4105 passed in 397.15s (0:06:37)` / `== cli smoke ==` / `check: green`.
4. Conformance: PASS. fetch, then `checkout -q --detach origin/<branch>`, for driver and architect only; `branch` defaults to main and is stripped; HANDS_PROJECT is set last in `job_env` (wins over handsd env and the role env table); doctor prints HEAD vs origin and `env HANDS_PROJECT=`. The event loop is not blocked: `advance_clone` (runner.py ~1258) uses `asyncio.create_subprocess_exec` + `wait_for(300 s)` and kills/reaps on timeout. Failure records are coherent (failed / spawn_error / no pid / HEAD unchanged); `stderr_tail` starts "cannot advance the clone (§36): git -C …", not with the bare git command the body describes.
D1 (real, reproduced): the job stays `queued` on disk during the advance (runner.py ~613–620, up to 2×300 s) but is already out of `_waiting`. A `hands cancel` takes daemon.py:818's queued branch (writes `killed`, emits `job.killed`, ends the consultation), then the runner transitions its stale in-memory `queued` object to `running`, overwrites `killed` and spawns claude. Probe: final record `done`, not `killed`. The window existed before (ms); now it is a network fetch. Fix: reload or re-check after the advance, or go `running` first.
D2 (cosmetic): `ADVANCE_TIMEOUT_S` sits between `FAILURE_REASONS`'s `#:` doc block and the tuple (runner.py ~216–235).
NOT proven: the timeout path and a network remote (the body says so); a checkout refused by local changes; D1 through a live handsd + `hands cancel` (shown at runner level).

**337db9a** (U5): approve, no blocking defects.
1. Unit/sections: PASS. U5, DESIGN §36 "The engine" with §33/§34, H-044/H-045. The body lists all 7 files (matches `--stat`); DESIGN.md / meta/plan.md / meta/CHECKPOINT.md untouched.
2. Test-first: PASS. With playbook.py, api.py and daemon.py reverted to `337db9a~1`, three new tests fail: kickoff_after_an_apply, no_longer_loads_after_the_apply, and the hold test's `[approved]`. The other two hold cases (another name, hash mismatch) pass before and after, as the body says; they pin "Approve/Deny unchanged". Restored clean.
3. Gate: PASS. `./scripts/check` (`env -u HANDS_PROJECT -u HANDS_JOB`), one run: "4110 passed in 446.68s (0:07:26)" / "== cli smoke ==" / "check: green".
4. Conformance: PASS. The reload (playbook.py:1575) runs only for a `builder.done` where `_engine_applied_kit` holds (decided_by playbook, approved, `kit_apply_problem` None), after the paused check; a load failure stops via `_load` with the loader's message. daemon.py:753 skips publishing a deferred `job.held` (synchronous listener, so nothing is published before the decision). The approved text is the design's plus the existing "hands: " prefix, disclosed. No path strands a deferred hold: a failed or crashed consultation escalates and publishes; a pause at filing means no deferral, and a later pause is caught in `_release_kit`; a kit filed during `kit_wait` is published by `_decide_kits`' `finally` `_publish_undecided`; no longer autonomous publishes it; a restart republishes with buttons. Minor: an apply that deletes playbook.toml gives `load_playbook` None and no stop (playbook.py:1580ff), which is arguable against "no longer loads → stop".
NOT proven: the paused, approve-failure, non-autonomous-at-end and filed-during-the-wait paths are traced by reading only, with no tests (the body says so); no real ntfy or phone.

**187e38e** (U6): pass, no blocking defects.
1. Unit/sections: U6, DESIGN §36 "`answer <secret> <text>`" with §8, §26, §33, §34. The file list matches the stat (9 files); DESIGN.md / meta/plan.md / meta/CHECKPOINT.md untouched; notify.py unchanged, justified by `Daemon._reply_ended` (daemon.py:173-177).
2. Test-first: PASS. Reverting api/daemon/phone/playbook/spool/INTEGRATION.md makes 22 tests red: 13 test_phone (every refusal, the attachments, `test_an_answer_whose_text_names_a_decisions_file_is_not_held` with its held cli-keep control), 8 test_playbook (escalation-question stops, the decided section), 1 test_docs. Restored, all green.
3. `./scripts/check` at 187e38e: "4131 passed in 413.42s (0:06:53)" / "== cli smoke ==" / "check: green".
4. Conformance: PASS on every sentence. Builder keep, origin phone, never gated (the `ungated` flag, api.py:258-264); un-pauses on start ("phone" is in `UNPAUSE_ORIGINS`); all refusals (empty, running/queued/held, no resumable session); the attachment via the shared `_fetch` rules, the path sentence, sha256 in `files_written`; `answer.sent`; `VERDICT:` fires rules; both escalation stops keep the question verbatim; the "Decided by the human…" block sits after the review markers.
Probes: "titled builder" is published for answer jobs only (`is_builder_answer`), and tests confirm plain cli builder jobs publish nothing; this is a defensible reading, as the sentence sits in the answer paragraph. Restarts: "since last consultation" is computed from the spool and git each time, with no in-memory state. Race: the refusal check is re-run in `answer_builder`, with no await before `daemon.enqueue` in `_send` (api.py:381-385, 241-289), so it is closed.
Minor: playbook.py:520-527 uses `git log --since` (committer date: clock skew or a rebase could include or drop a decision file); playbook.py:544-546 compares repo-root-relative paths to `meta/decisions`, so a builder cwd in a subdirectory would miss every owner file.
NOT proven: the decided list across a real daemon restart; an attachment fetch failing mid-transfer during an answer; a non-builder "asked" job in `escalation_question`.

**61a2417** (U7): PASS, no blocking defects.
1. Unit/sections: PASS. U7, §36 "The job environment (HF-006)" and "The guard (HF-003)", §30/§32/§33. The body lists all 8 files (matches `--stat`); DESIGN.md / meta/plan.md / meta/CHECKPOINT.md untouched. The brief named `runner.py`; it is unchanged because `config.py`'s `spawn_env` feeds `runner.job_env`.
2. Test-first: PASS. Reverting `bash_guard.py`/`config.py`/`doctor.py` to `~1` turns 14 tests red: 8 test_bash_guard (new cp shapes, realpath, real-bash run, self-test rows), 2 test_config, 2 test_doctor, 2 test_runner. Restored, `bash_guard.py --selftest` gives `selftest: 405/405 ok`.
3. `./scripts/check` at 61a2417, one run: `4180 passed in 518.69s (0:08:38)` / `== cli smoke ==` / `check: green`.
4. Conformance/security: PASS. About 55 crafted commands through the guard (HANDS_ROLE=architect, real dirs, stdin JSON).
   - Refused: `-t`, `--target-directory=`, `-T`, `-l`/`--link`, `-s`/`--symbolic-link`, `--parents`, `-a`, `--preserve=links`, `-P`, `-L`, `-rL`, `-R`, `-rf`, `--`, a lone `-`; globs, braces, `$`, backticks, backslashes, redirects, `HANDS_CLONE=` prefix, `~`, `/proc/self/root/...`; a symlink source (quoted or not), `repo/../.claude/...`, `kits/../out`, an extra target outside, mixed clone/other roots, a single path word, and a whole-clone `cp -r repo` when the clone holds any link.
   - Allowed and harmless: an option after the paths (`cp a kits/x -r`), the target being `HANDS_KITS` itself, `kits/../repo` source spelling, `;` chains.
   - A hardlinked pair inside a source dir lands in kits as separate files (nlink 1, GNU cp 9.4).
   - No accepted command writes outside kits or plants a link.
   - Timeouts: builder/aux get 900000 for both names unless the env table overrides; driver/architect get none from hands; doctor prints each value with its source on the builder/aux rows.
Minor: a trailing-slash symlink source is allowed: `cp -r repo/dl/ kits/dl` (dl → a dir in the clone) passes because `lstat` follows the trailing slash in `bash_guard.py` `source_problem`/`kits_symlink`. That differs from the letter of "refused when a source is one", but cp copies a plain dir and no link lands in kits. Also `cp -r repo/.git kits/g` is allowed (design-silent), and a FIFO in the clone is recreated in kits. Doctor prints the Bash limits only on builder/aux rows; DESIGN's "on each row" is ambiguous.
NOT proven: TOCTOU races between the guard check and cp; write-through to a pre-existing hardlink already in kits (U8's scope; kits-only cp had the same exposure before); a live `claude` job honouring `BASH_*_TIMEOUT_MS`.

**6a3f2f2** (U8): conforms to the design, with one should-fix and one design-text gap.
U8, mission 20 (review 18 should-fix 1–4; DESIGN §36 "Review 18's four should-fix items", §34); 10 files, all listed in the body; DESIGN.md / meta/plan.md / meta/CHECKPOINT.md untouched. Test-first: reverting the five product files fails all 25 new tests (11 ntfy_token, 7 doctor, 1 playbook, 6 bash_guard). Restored: `./scripts/check` → `4212 passed in 524.78s (0:08:44)` / `== cli smoke ==` / `check: green`.
(a) ntfy_url: OK. Any non-ASCII is refused at load (config.py:582), so the NFKC+U+3002 fold is defence in depth. U+FF0E and U+FF61 NFKC to U+3002, and U+2024/U+FE52 to "."; every non-ASCII url among 33 probes was counted public and refused. ASCII probes (`%2E`, backslash-@, `#@`, `?@`, userinfo, trailing dots) all matched httpx's real host, so none gets a token past the check.
(b) doctor self-test: matches the letter, but review 18's probe still passes. Should-fix. doctor.py:1104 runs `python3 -I` with empty PYTHONPATH, but the live hook command must stay plain `python3 <guard>` (§30). With `shlex.py` planted beside the guard, the live hook exits 0 on `rm -rf` (allowed) while `-I` exits 2. Doctor reports "self-test green"/`ok` for a live hook that allows everything (tests/test_doctor.py:2555 asserts that `ok`). Disclosed under "Not proven"; needs a finding: fail on any `.py`/package beside the guard, or allow `-I` in the hook command.
(c) kit hash: OK. kit.py `_open_zip` reads once and hashes the same bytes; api.py:527-534 refuses a client mismatch and records `report.sha256`. `apply_from_zip` (kit.py:1255) still re-reads the stored path after the check, as disclosed.
(d) hardlinks: cp/mv OK; Write/Edit not covered. `cp`, `cp -r`, `mv` and clone→kits `cp` are refused; `ln` is refused as file mutation and `cp -l` is refused; `mkdir` runs; doctor's `_kits_walk` reports it, and a shared-case test pins it to the guard. Gap: `write_violation` (bash_guard.py:1363) allows `Write`/`Edit`/`MultiEdit` on `./kits/h` when `kits/h` is a hardlink to the guard, because realpath stays in kits. If Claude Code writes in place, this writes into the guard. §36 names only cp/mv, so this is outside the design text, but it is the same attack class and should get a finding.
NOT proven: whether Claude Code's Write/Edit write in place (follow a hardlink) or replace the file; the swap-back race between check, apply and approval (the engine re-hash is not tested).

**2e9a6ca** (U9): passes all four points, no blocking defects.
1. Unit/sections: pass. U9, §36 "Notifications name the project" + "This repository's kickoff", and it also carries §36 "The review protocol" into `docs/PLAYBOOK.md`. That file and `README.md` are outside the brief's list but named and justified in the body (README's single `ntfy_topic` setup line is covered by §36). `daemon.py` is listed but untouched; the body explains that start and crash already go through the Notifier. DESIGN.md / meta/plan.md / meta/CHECKPOINT.md untouched; every diff file is in the body.
2. Test-first: pass. With the product files reverted to `2e9a6ca~1`, all 11 tests in `test_notify_project.py` fail, plus 3 in `test_docs.py` and many in test_playbook/test_phone/test_wake/test_ntfy_token. The kit-check test gives "kit check: FAIL (1 of 6 checks failed)".
3. Gate: green. `4225 passed in 494.39s (0:08:14)` / `== cli smoke ==` / `check: green`.
4. Conformance: pass. The prefix is applied at the only two publishers, `notify.py:364` (`Notifier._publish`) and `notify.py:218` (`send_test`, used by the CLI and by API `api.py:1196`); phone.py's httpx use is kit fetch only, so there is no bypass; handswho (`who.py:901`) keeps its root line, as §36 says. All four topic shapes appear in INTEGRATION.md and README.md. The topics row WARNs, never FAILs, and never prints a topic. The `PLAYBOOK.toml` diff is exactly the kickoff line; `load_playbook` gives 20 rules and the new kickoff; the `hands kit check --repo` test against this repository passes.
Not defects, but worth noting: the U5 approval line becomes `<project>: hands: kit <name> filed…` (`playbook.py:1853`), and every other `hands: …` title gets the same double prefix. This matches §36 ("begins with `<project>: `") but is redundant on the phone. "Lacks" is read as not being a substring (`doctor.py:343`), which is lenient: a project `a` passes almost any topic. Held notes, the inbox record of a failed publish and the start fold's list keep the raw title (a chosen reading; §36 is silent).
NOT proven: that TITLES covers every title handsd can raise; real ntfy phone rendering.
