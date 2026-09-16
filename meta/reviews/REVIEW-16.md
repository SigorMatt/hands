# REVIEW-16 — cold review of hands mission 16

VERDICT: review mission 16 blockers=2 should-fix=8

Base `308c396` (`review: mission 15`, the last `review:` commit on origin/main).
Tip `ffac5e1`. Unit commits reviewed, one sub-agent each, in a `git worktree` at
the commit: 7de7520 (U0, the orchestrator's `plan:` commit), c7dafd2 (U1),
7ce3189 (U2), f4fde48 (U3), 44410ea (U4), e091d0b (U5), 6939524 (U6). Not
dispatched: 31789c6 (the architect's mission-16 kit) and ffac5e1 (U7, the
`meta:` commit that adds meta/FINAL-REPORT-16.md and the bookkeeping). The
reviewer read blocker 1's code path at the tip (`src/hands/api.py:267-330`: no
kit check in `kit_file`). The reviewer reproduced blocker 2 at the tip: a zip
built with Python 3.14.6, `hands.kit.apply_from_zip` on it, then `unzip -o` in a
scratch repository.

## Blockers

1. **A socket client can still file an `origin: architect` apply that the engine
   approves, and the kit does not have to pass the kit check (U2 `7ce3189`, U3
   `f4fde48`; §32 "a socket client cannot set `origin: architect`", "`hands kit
   file <dir>`, which builds the zip itself, checks it, and files the held
   apply"; REVIEW-15 blocker 3).**
   - **The code at the tip.** `Api.kit_file` (`src/hands/api.py:267-330`) checks
     the name, the base64, the size and the entry paths (through
     `apply_from_zip`), and that an architect consultation is open. It never runs
     `check_kit`. The docstring says the zip is the one "the client built … and
     checked", but the daemon only trusts that. `kit_file` is a socket method, and
     the job it files carries `origin: architect` and a daemon-minted `kit_id`.
     That is exactly what the engine approves.
   - **Repro (U3 sub-agent, end to end).** Setup: a real daemon, fake_claude, and
     the committed role + autonomous playbook. While the architect job ran, a
     raw-socket `kit_file` filed two zips, `foo` and `bar`. Each carried
     `.claude/hooks/bash_guard.py`, `.claude/settings.json`, `DESIGN.md` and a
     `PLAYBOOK.toml`, and no brief. Result: both were `decided_by=playbook`, and
     `check_kit` on each gave `ok=False failed=[playbook, brief, verdicts,
     wording]`.
   - **Who opens the window.** Any socket client can start a consultation, as the
     tests do: `send --role aux` whose reply is a review verdict.
   - **Missing test.** U3's own end-to-end kit fails the check (4 of 6) and is
     approved. No test binds "a kit that fails `hands kit check` is not
     approved".
   - **What the disk contradicts.**
     - FINAL-REPORT-16's review-items table marks REVIEW-15 blocker 3 "closed".
     - §3.2 says only that the daemon "cannot tell the architect's process from
       another process of the same user" and that "the client's check is the
       check".
     - Neither says that a check-failing kit touching the guard and its settings
       is engine-approved with no human.
     - docs/INTEGRATION.md and docs/PLAYBOOK.md say neither.
     - The fix is small and local: the daemon runs the kit check on the bytes it
       stores, against the builder's clone.

2. **A zip whose entry names disagree gets past the daemon's and the kit check's
   path rules and writes into `.git` (U2 `7ce3189` relies on it; FINAL-REPORT-16
   §2 "the daemon refuses … an escaping zip"; U2 body "the check's paths rule
   refuses .git").**
   - **Why it works.** `src/hands/kit.py` judges `info.orig_filename`
     (`kit.py:381`, `:432`, `:1112`), the name in the local header. But `unzip`
     and Python's `ZipInfo.filename` use the Info-ZIP Unicode Path extra field
     (0x7075) when one is present.
   - **Reproduced at the tip.**
     ```
     filename= .git/hooks/pre-commit orig= docs/notes.md
     apply_from_zip -> Apply(name='evil', adds=['docs/notes.md'], prompt="Apply ~/evil.zip to this
       repository: unzip -o into the repo root (it adds docs/notes.md), …")
     unzip -o ../evil.zip ->  extracting: .git/hooks/pre-commit
     -rwxr-xr-x … r/.git/hooks/pre-commit        (the next `git commit` ran it)
     ```
     The U2 sub-agent got the same kit filed over the socket `kit_file`: held,
     origin architect, the prompt naming only `docs/notes.md`.
   - **Reach.**
     - The phone's kit path: a human approves an apply prompt that names a file
       other than the one written.
     - Blocker 1's socket path: engine-approved with no human.
     - The architect's own `hands kit file` builds its zip itself, so it cannot
       craft this.
   - **Scope.** The rule predates mission 16. But the mission's new daemon method
     rests on it, and FINAL-REPORT-16 §2 claims an escaping zip is refused. No
     test covers an entry whose two names differ.

## Should-fix

1. **One consultation can file any number of kits, of any name, and the engine
   approves each (U3; §32 "`next kit` waits for the specific apply the architect
   filed (its `kit_id`)").**
   - Probe (U3 sub-agent): `foo` and `bar` were both filed during one architect
     job and both engine-approved, although the verdict was `VERDICT: next kit
     foo`.
   - The body discloses that approval happens at filing ("such a kit may already
     have been approved"). FINAL-REPORT-16 does not.
   - Kits from an earlier consultation are correctly not counted.

2. **Architect-mode `cp` writes through a symlink already inside `kits/` (U2;
   §32 "every path argument under `HANDS_KITS`").**
   - The guard resolves the destination directory, not the file `cp` writes.
   - Probe (U2 sub-agent): with `kits/a/h -> ../.claude/hooks/bash_guard.py`
     planted (a symlink that dangles inside kits), two allowed commands replace
     the guard with "# NEUTERED" under real bash:
     - `cp -r kits/a/h kits/` moves the relative link up one level, so it now
       points out of kits.
     - `cp kits/pay/h kits/` then writes through it.
   - The architect cannot create a symlink from nothing, so something else has to
     plant it. Doctor does not look for one.

3. **Doctor passes a `kits` that is a symlink to `.claude`, and the guard then
   lets the architect write its own settings and hook (U4; §32 "`HANDS_KITS`
   exists and is under the cwd").**
   - Probe (U4 sub-agent): after `ln -s .claude kits`, doctor gives "role
     architect status=ok, self-test green".
   - The guard's `--write` in architect mode then exits 0 for
     `<cwd>/.claude/settings.json`.
   - This meets §32's words, since the realpath is under the cwd. But the row
     exists to catch exactly this.

4. **Doctor's role rows stay `ok` on settings that switch off what they check
   (U4; §32 doctor; FINAL-REPORT-16 §3.5 understates it).** Probes (U4 sub-agent):
   - **Push remote.** A second remote named by `remote.pushDefault` or
     `branch.<b>.pushRemote` passes doctor, and a plain `git push` really pushed.
     §3.5 says "other remotes … are not judged" but does not say a plain push
     reaches one.
   - **Local settings.** `.claude/settings.local.json` with `disableAllHooks` and
     `bypassPermissions` is not read.
   - **Allow entries.** `Write(**)`, `Edit(/**)`, `Bash(*:*)` and `acceptEdits`
     pass.
   - **Matchers.** A `type: prompt` hook passes under an unanchored regex matcher
     (`ulti.dit|as`) or under `bash`.

5. **`hands kit check` passes a role-mode kit it has not judged (U4; §32
   "refused … by `hands kit check` when the kit carries the playbook").** Probe
   (U4 sub-agent):
   - Setup: two project configs and no `--project`/`HANDS_PROJECT`, or one config
     that is not valid TOML.
   - Result: exit 0, with `PASS playbook: … is not judged against
     [roles.architect]: no hands config resolves here`.
   - The body chose this for the phone architect's sandbox. §32 does not allow
     it, and no finding records the choice. An unparseable config is not that
     sandbox.

6. **The consult prompt's "next unmet milestone" rule is not §32's rule, and no
   finding records the change (U4; §32 "the first whose gate is not marked
   DONE").**
   - `next_milestone` (`src/hands/playbook.py:655-680`) treats a milestone as
     done when `DONE` is on its first line.
   - On this roadmap that marks M4b done because of "mission 10 DONE", although
     its gate is not marked. With M4 marked DONE, the prompt skips M4b and names
     M4c.
   - The docstring itself says "a `DONE` further down an entry is a
     sub-mission's", and the first line of M4b is a sub-mission's.
   - FINAL-REPORT-16 §3.6 discloses the M4b reading. REVIEW-15 should-fix 4
     already said a builder does not get to decide a design deviation; it wants a
     finding.

7. **Daemon start still publishes twice within a quarter second when a queued job
   fails at once (U4; §32 "daemon start publishes exactly one notification";
   REVIEW-15 should-fix 5).**
   - Probe (U4 sub-agent), a real Daemon, phone on:
     - A queued consult driver job with no verdict: `0.016 hands: handsd
       started`, then `0.205 hands: the pipeline stopped`.
     - A queued failing builder job and a failing aux job: 0.24 s apart.
   - §3.7 discloses the class ("a task the start schedules that publishes after
     it returns"). This is the phone-side shape REVIEW-15 should-fix 5 was
     about.

8. **U5's sweep left text that still names a cause, and its finding overstates a
   pin (U5; §32 last paragraph; H-034).**
   - **Template messages.** Both templates' `task_killed` message is still "The
     harness killed a task inside a role session"
     (`templates/PLAYBOOK-missions.toml:118`, `templates/PLAYBOOK-runs.toml:127`).
     §32 says the detector cannot tell a reap from a `TaskStop` or a backgrounded
     foreground command.
   - **An unhedged sentence.** `docs/PLAYBOOK.md:585` still says "killed tasks and
     orphan processes stop and call you", with no H-034 note beside it.
   - **A stale test docstring.** The docstring of
     `test_both_docs_say_the_task_killed_cause_is_always_unknown` still says it
     checks what the example maps the event to.
   - **The pin is weaker than claimed.** H-034, the U5 body and FINAL-REPORT-16
     §3.8 say docs/PLAYBOOK.md's closing copy "must equal §10 byte for byte". The
     test only checks that each fixture line appears somewhere in the doc. Changed
     to `notify`, all of test_docs.py stays green. Keeping `stop` is still right
     (the heading says verbatim), but the stated reason is not what the test
     binds.

## Notes

- **Gates.** `./scripts/check` was green once at each of the seven unit commits,
  and every pass count matches FINAL-REPORT-16 §1: 3126 (U0), 3594 (U1), 3647
  (U2), 3689 (U3), 3736 (U4), 3743 (U5), 3743 (U6). Guard self-test 370/370 at
  U1. This review did not reproduce the "3/3" runs; ffac5e1 changes only meta/
  over 6939524, which was green.
- **Test-first.** Every product unit's tests go red when its product change is
  reverted:
  - U1: 505 failed in the two touched test files.
  - U2: 36 failed.
  - U3: 57 failed.
  - U4: 34 failed plus an import error in test_playbook.py; 7 more with a stub.
    That is 41, not the "29 of the new cases" the body and FINAL-REPORT-16 §2
    give.
  - U5: 2 docs tests; its playbook pins are coverage, as disclosed.
  - U6: the kickoff value, in a worktree where the parent's PLAYBOOK.toml is
    committed.
  - U0: its test edits follow the kit. Against the base's non-test files, 2 fail.
- **U0 wording.**
  - "The base 31789c6 was red (5 failures)": the base alone gives 4. The 5th is
    U0's own H-030 status line, which CHECKPOINT, the journal and FINAL-REPORT-16
    §1 word correctly.
  - The bullet "tests/test_docs.py: … the switch-point setup line" describes a
    change made in docs/INTEGRATION.md only.
  - The FINAL-REPORT-15 correction says the `for o in -f` probe exits 0 "in
    normal and driver mode"; at 17b12fe it also exits 0 in architect mode.
  - The H-033 history and the appended corrections are otherwise accurate and
    append-only.
- **The language (§30's condition).** The U1 sub-agent found no hole in the
  language itself. It probed control characters as separators, partial quoting,
  backslashes, backticks, every redirection, `((`/`[[`/`!`, globs and extglob,
  leading assignments, the option tables' file and program values, and role-mode
  read confinement. Each probe was confirmed against real bash.
  - The holes this review found are in the authority around the architect
    (blockers 1–2, should-fix 1–3), not in the language.
  - §30's condition is about the language. Those items still stand between the
    architect role and being enabled.
- **Over-refusals (usability, not holes).** `echo git`, `cat -- file`, combined
  short flags such as `grep -ni`, and `echo -e` are refused.
- **The budget (§3.4).** "Restated" is the key present with any value. A playbook
  that already writes `max_architect_consults`, as the docs/PLAYBOOK.md example
  and the test book do, renames with a one-line change: the count drops to 0 and
  the kit is engine-approved. This is §32's wording, and FINAL-REPORT-16
  discloses it, so it is not a should-fix. The architect should decide whether
  "restated" means what REVIEW-15 should-fix 3 asked for.
- **Events that fire nothing (not U5's doing).** In all three shipped playbooks,
  an aux job that ends `orphaned`, `limited` or `killed` fires no rule: no stop,
  no notify. Those are not §10 events. "A job that ends `failed` is what stops"
  holds for builder (after `max_resumes`), aux, driver and architect.
- **U2 details.**
  - Nested kit directories (`kits/m16/meta`, `kits/deep/m17`) are accepted;
    the docstring says `kits/<name>`.
  - The stored zip sits in a 0700 directory under the spool, out of the
    architect's reach.
  - Absolute, `..`, symlink and `.git` header names are refused over the socket.
- **U4 details.**
  - A `pushInsteadOf` rewrite of `no_push` is not a hole, because git ignores it
    for an explicit push URL. The doctor docstring's "pushInsteadOf expanded" is
    inaccurate.
  - A role playbook committed after start still stops the engine.
- **U6's kit-check gate is weak.** The kit carries no playbook, so its kickoff is
  "not compared". The gate would pass the same way at e091d0b, as REVIEW-15 said
  of 15 U7. meta/BUILDER-17-PROMPT.md does not exist; doctor's `go` row warns
  only when the command channel is on (§3.9).
- **Forbidden files.** No unit commit touches `DESIGN.md`. Only U0, the `plan:`
  commit, touches `meta/plan.md` and `meta/CHECKPOINT.md`. Every unit body lists
  every file in `git show --stat`.
- **NOT PROVEN against the disk.**
  - §3.1 holds; nothing new was found in the language.
  - §3.2 understates it (blocker 1).
  - §3.3 was not exercised.
  - §3.4 holds.
  - §3.5 understates it (should-fix 4).
  - §3.6 holds as disclosure (should-fix 6).
  - §3.7 understates the shape (should-fix 7).
  - §3.8 overstates the pin (should-fix 8).
  - §3.9 holds.

## Per-commit verdicts

### 7de7520 — U0

```
sha 7de7520 (parent 31789c6). This is the mission 16 U0 `plan:` commit. **Verdict: no blocker candidates. There are three note-level wording inaccuracies (items c, d, e below).**

1. **Unit.** U0 Plan and bookkeeping. It claims DESIGN v3.15 §32 (with §6, §30, §31), REVIEW-15 blockers 1 and 2 and should-fix 7, and findings H-030 through H-033. **Pass.**
2. **Test-first.**
   - **The base:** the three test files you named give 4 failures at 31789c6, and the full suite gives the same 4 and nothing else: the architect-kit guard line, the `decided_by` list, the switch-point setup line, and the `task_killed` playbook test.
   - **The 5th failure** comes only from this commit's own change. Old tests against 7de7520's non-test files give 4 failures, now including the "H-030 open" test, while the switch-point test passes.
   - **New tests against the base's non-test files:** 2 failures (the switch-point test and the H-030 status test).
   - **New tests against the pre-kit files at 308c396** (DESIGN.md, PLAYBOOK.toml, architect/): 7 failures.
   - The `decided_by`, playbook and guard-line tests are coverage against the base, since the kit had already made those changes. The guard test only proves the guard's verdict on the lines, which the body says. **Pass.**
3. **`./scripts/check`** on a clean tree at 7de7520: "All checks passed!", "3126 passed in 178.96s (0:02:58)", "check: green", exit 0. **Pass.**
4. **Conformance.** **Pass, with notes.**
   - **Files touched:** no src/, driver/ or DESIGN.md. plan.md and CHECKPOINT.md are allowed here. The body names all 9 files from `--stat`.
   - **Append-only:** in FINAL-REPORT-15 and FINDINGS.md, the only removed lines are the three old `Status: open` lines of H-030, H-031 and H-032.
   - **H-033's five-line history** matches REVIEW-11 to 15, FINAL-REPORT-13 and H-026.
   - **The FINAL-REPORT-15 §3.1 correction** matches REVIEW-15 blockers 1 and 2 and should-fix 7. I re-ran the probes against the old guards and confirmed them (EVIDENCE below). §31 does not name `unzip` (grep).
   - **The resolutions** added to H-030, H-031 and H-032 match §32's text.
   - (a) **Scope, note.** The brief's U0 covers meta files only, but this `plan:` commit also carries tests/ and docs/INTEGRATION.md. The body gives the reason (red base) and plan.md cites mission 15 U0 as precedent.
   - (b) **Note.** INTEGRATION.md copied README's broken setup line, where the `&& cd` sits after the `#` so the `cd` never runs. The body discloses this only for README. The equality test forced the copy, and origin/main shows U2 fixed both files.
5. **Not proven:** that the base alone was red with 5 failures. On disk it is 4, plus 1 caused by U0 itself (item c).

EVIDENCE:
- (c) **"The base 31789c6 was red (5 failures)".** Base full suite: 4 FAILED, as listed in point 2. The 5th (`test_the_integration_doc_names_h_030_while_it_is_open`) fails only with U0's FINDINGS.md status line in place. CHECKPOINT and the journal word this correctly ("from the kit and U0's H-030 status line").
- (d) **Body bullet "tests/test_docs.py: … the switch-point setup line matches architect/README.md as shipped".** test_docs.py's diff has only two hunks: `decided_by` and the H-030 test. That fix is in docs/INTEGRATION.md only.
- (e) **The correction says `for o in -f; do tail $o /etc/hostname; done` "exits 0 in normal and driver mode".** At 17b12fe it also exits 0 in architect mode, so the line understates it. It matches REVIEW-15's own wording.
  - Probe: the shipped guard file at each commit, hook JSON on stdin.
    - guard at 17b12fe, P1 = `for a in '$x'; do echo; done; for c in ${a%x}'(touch${IFS}/tmp/.../PWN)'; do echo ${c@P}; done`: normal exit=0, driver exit=0, architect exit=0. `bash -c P1` created PWN.
    - guard at 17b12fe, P2 = the `for o in -f` probe: normal 0, driver 0, architect 0.
    - guard at 17b12fe, `cat /proc/self/environ`: normal 0, driver 0, architect 0.
    - guard at 1a48e11 (the parent): P1, P2 and cat give driver exit=2 and normal exit=0. That supports "the parent refused it" for the driver role. That commit had no architect mode.

Both worktrees and the probe directory have been removed. The main checkout was not touched.
```

### c7dafd2 — U1

```
REVIEW — c7dafd2 (mission 16 U1, "guard: $, braces and reserved words leave the language; role reads confined")

1. Unit/sections: mission 16 U1 "The guard's language, finished". Implements DESIGN v3.15 §32 (with §30, §31, §27, §12); closes REVIEW-15 blocker 1 + should-fix 7, finding H-033. PASS.
2. Test-first: RED confirmed. Reverting only driver/hooks/bash_guard.py to the parent turns 505 tests red across the two touched test files (test_bash_guard.py + test_docs.py); commit body claims 486 for the whole suite. Not coverage-only. PASS.
3. Gate: `./scripts/check` green on the clean commit — "3594 passed in 232.84s", "check: green"; guard --selftest 370/370. PASS.
4. Design conformance: PASS. I tried hard to break §32's claim that an allowed segment "can run only a table command with table options" and could not.
5. Report below.

NOT broken (all BLOCK unless noted), via the shipped file with hook JSON on stdin, confirmed against real bash in /tmp/rev16-u1:
- Language: control chars TAB/CR/VT/FF; NBSP-as-separator caught via the `in` keyword; partial-quote keywords (`f'o'r … in …`) caught by `in`; quoted `'done'` correctly stays text; extglob `@(`/`!(`; backslash, backtick, `$`, `{`/`}`; redirections `> < >> >| <<< &>` and `2>&1`; `#` comment; `((`, `[[ ]]`, `!`; glob `* ? [ !` and brace expansion `{a,b}`/`{1..3}`; leading assignments and env-prefixed commands (`FOO=x cat`, `PAGER=cat git log`).
- Table options: no row option names a program or writable file — git per-subcommand allowlist refuses `--output/--ext-diff/--exec/-c core.pager`; `grep -f`, `tail -f`, `date --set`, `jq --rawfile`, combined `-ni` all refused; `printf`/`true`/`sort`/`uniq` left the table.
- Role/architect read confinement: outside-clone, `..`, `~`/`~root`, in-clone symlink escapes (realpath), `/proc/self/environ`, `jq env`/`input`, `git -C` outside, `git diff --no-index`, `hands --prompt-file=/etc/x` and `kit check ~/Downloads` all BLOCK; clone/spool reads, stdin-pipe reads, and architect `ls kits/` ALLOW. Write matcher allows only architect writes under HANDS_KITS.
- Removals confirmed absent: REFUSED_SEQUENCES, BRACE_EXPANSION, SHELL_KEYWORDS, command_start; REFUSED_IN_DOUBLE_QUOTES reduced to `!`. Body lists all 5 files in `--stat`; no forbidden file touched (DESIGN.md, meta/plan.md, meta/CHECKPOINT.md absent from the diff). Strict-subset test honestly excludes the architect-only KITS_TABLE rows.

Verdict: PASS. No blockers, no security hole found.

Notes (not blockers): treating any `git` token as an invocation over-refuses benign `echo git` (BLOCK); `cat -- file`, combined short flags (`grep -ni`), and `echo -e` are also over-refused — usability costs, not holes. Info-leak gaps (`pgrep -a -f`, `hands --project <other>` reaching another daemon, TOCTOU realpath) are real but already disclosed in the commit body / FINAL-REPORT §3.1; nothing new surfaced.
```

### 7ce3189 — U2

```
REPORT 7ce3189 (parent c2dafd2 is wrong; the parent is c7dafd2): mission 16 U2, "Architect mode and `hands kit file <dir>`".

1. **Unit and sections: PASS.** The body names DESIGN §32 "Architect mode" and the kit_id sentence of "Autonomy", with §31, §6 and §26, plus REVIEW-15 blocker 2 and H-030. It names all 19 files in `--stat`. DESIGN.md, meta/plan.md and meta/CHECKPOINT.md are untouched.
2. **Test-first: PASS.** I put the 13 non-test files back to the parent and ran the six changed test files: **36 failed**. The failures include the three-mode blocker-2 probe (4), `test_architect_mode_case` (7), the kit-file refusals (5), the symlink refusal (2), the daemon kit_id refusal, the directory-namelist test, 3 docs pins and the spool field test. Restored, the same files give **2607 passed**.
3. **Gate: GREEN.** `3647 passed in 227.64s (0:03:47)`, then `check: green`, matching the body.
4. **Guard: PASS on the brief's shapes, with one hole that needs a symlink already in kits.** I ran each probe through the shipped guard in architect mode, then under real bash when allowed:
   - The three unzip probes and `zip -r` exit 2.
   - Refused: `mkdir -p kits/a/../../.claude/x` (quoted too), `\/` escapes, `?` and `[.]` globs, `--`, `'-t'`, `-t/tmp`, `~/kits`, a cp source outside kits, `kits/../ab2`, `mv … .`.
   - Allowed but harmless: `mv kits/ab kits` and `mv kits kits/f` (bash errors), `cp -r kits kits/sub` (copies inside kits).
   - The Write/Edit/MultiEdit matcher refuses `..` escapes and a dangling symlink out, and NotebookEdit fails closed.
   - **Should-fix candidate:** the guard checks where the destination directory resolves, not the final file cp writes. If kits already holds a relative symlink, even a dangling one that points inside kits, `cp -r kits/a/h kits/` moves it one level up so it points outside, and `cp kits/pay/h kits/` then writes through it. That overwrote `.claude/hooks/bash_guard.py`. The architect cannot create a symlink from nothing, so this needs one planted by something else.
5. **`hands kit file` and the daemon: PASS as disclosed, with one hole that predates this unit.**
   - The client refuses unset or empty HANDS_KITS, `..`, a symlink out, a zip, a file, the kits dir (with or without a trailing slash), a missing path, `m16/..` and `.hidden`.
   - Over a real daemon socket, `kit_file` refuses absolute, `..`, symlink and `.git` entries.
   - The kit_id is minted by the daemon, the stored zip sits under `<spool>/kits/<id>/` in a 0700 directory, and the guard lets the architect write only under kits, so it cannot change the stored zip.
   - At this commit, a raw socket `kit_file` with an unchecked zip (only `src/hands/evil.py`) is filed held with origin architect. A raw `send` with `origin: architect` is also still accepted (kit_id null). The body discloses the first; both are U3's to close.
   - **Should-fix candidate (predates this unit; affects the phone path too):** the daemon checks zip entry names from the header, but `unzip` and Python's `filename` use the Unicode Path extra field instead. A zip whose header says `docs/notes.md` but whose extra field says `.git/hooks/pre-commit` gets filed, the apply prompt says "adds docs/notes.md", and `unzip -o` writes an executable `.git/hooks/pre-commit`.
   - **Note:** nested directories such as `kits/m16/meta` and `kits/deep/m17` are accepted, although the docstring says `kits/<name>`.
6. **Docs: PASS.** architect/CLAUDE.md rule 3, the handbook §3 end, §12 and the H-030 paragraph say directory kits. The README and INTEGRATION setup line now runs `&& cd` before the comment. Handbook §1/§2 still say "a kit is a zip", which fits the phone path.

**NOT PROVEN:** a real Claude session using these hooks; the body's 3/3 gate runs (I ran it once); whether U3 blocks either raw-socket route or the Unicode Path entry. The worktree and sandbox are removed.

EVIDENCE:
# architect dir with kits/a/h -> ../.claude/hooks/bash_guard.py (dangling inside kits), kits/pay/h = "# NEUTERED"
ALLOW: cp -r kits/a/h kits/      bash rc=0   # kits/h -> ../.claude/... now resolves to <cwd>/.claude/hooks/bash_guard.py
ALLOW: cp kits/pay/h kits/       bash rc=0
$ cat arch/.claude/hooks/bash_guard.py
# NEUTERED

# ZipInfo("docs/notes.md") with extra 0x7075 -> ".git/hooks/pre-commit", mode 0755
python filename= .git/hooks/pre-commit orig= docs/notes.md
apply_from_zip OK: adds ['KIT.md', 'docs/notes.md'] replaces []
raw socket kit_file -> {"origin":"architect","state":"held","prompt":"Apply ~/.hands/demo/kits/1df3…/kunicodepathdotgit.zip … (it adds docs/notes.md) …"}
$ unzip -o evil.zip   ->  extracting: .git/hooks/pre-commit
-rwxr-xr-x … repo/.git/hooks/pre-commit

raw kit_file {"name":"kuncheckedsrconly","zip":<zip of src/hands/evil.py only>} -> origin architect, state held, kit_id 42cfd3369d170c21
raw send {"role":"builder","origin":"architect","gate":"apply x",…} -> origin architect, state held, kit_id null
kit_file absolute / a/../b / S_IFLNK entry / .git/hooks/pre-commit -> REFUSED (an absolute path | a .. component | a symlink | a path inside .git)
```

### f4fde48 — U3

```
Review of f4fde48 (mission 16 U3, "Autonomy and origins"). Verdict: one blocker candidate, two should-fix candidates. The gate is green.

1. **Unit:** PASS. It claims DESIGN §32 "Autonomy (blocker 3, should-fix 1, 2, 3)" and H-032, with §31, §8, §6, §10 and §27. It says it closes REVIEW-15 blocker 3 and should-fix 1–3.
2. **Test-first:** PASS. With `src/`, `templates/` and `docs/` reverted to the parent, 57 of the changed tests fail (46 test_playbook, 5 test_docs, 3 test_kit, 2 test_daemon, 1 test_gates), including all the e2e and forgery cases.
3. **Gate:** PASS, one run on a clean tree: `3689 passed in 220.33s (0:03:40)`, then `check: green`.
4. **Conformance:** mostly PASS, with the gaps below.
   - **Socket and job paths (your probe 1):** nothing a socket client sends sets `origin: architect`, a `kit_id` or `decided_by: playbook`. `send` refuses all three, `approve` takes no decider, `decide_from_playbook` and `file_apply` are not reachable by name, and limit resumes don't copy `kit_id`.
   - **Kit reuse (probe 3):** closed. No socket path sets a `kit_id`, and a second job carrying one is refused.
   - **Kickoff (probe 4):** fires only for an apply the engine approved from a filed kit.
   - **H-032 (probe 7):** closed; the commit's test for it goes red on revert.
   - **No forbidden files:** DESIGN.md, meta/plan.md and meta/CHECKPOINT.md are untouched.
   - **Commit body:** it lists all 15 files in `git show --stat`.
   - **BLOCKER candidate, unchecked kit approved (probe 2).** While an architect consultation runs, a raw socket `kit_file` with a zip that fails `hands kit check` is approved by the engine and applied. The daemon never runs the check itself, so §32's "builds the zip itself, checks it, and files the held apply" and "a socket client cannot set origin: architect" hold only for the CLI. Any socket client can open that window too, with `send --role aux` and a review verdict, as the tests do. FINAL-REPORT-16 §3.2 discloses "the client's check is the check", which is weaker than what the disk shows. The docs don't say it at all. The commit's own e2e kit also fails the check (4 of 6) and is approved.
   - **SHOULD-FIX candidate, several kits per consultation (probe 5).** Nothing limits how many kits, or which names, are filed while the architect runs. In my probe, kits `foo` and `bar` were both approved although the verdict was `next kit foo`. Kits from an earlier consultation are correctly not counted.
   - **SHOULD-FIX candidate, budget reset (probe 6).** "Restated" means the key is present with any value. A playbook that already writes `max_architect_consults`, as the docs/PLAYBOOK.md example and the test book do, can rename with a one-line change; the count drops to 0 and the kit is still approved. That matches §32's words, but not what REVIEW-15 should-fix 3 asked for (disclosed in §3.4).
5. **Not proven:** a real `hands kit file` session; a daemon restart during `kit_wait_s`; H-032 on a real config with a driver role (my probe config had none, so I rely on the commit's test).

EVIDENCE (blocker, probes 2 and 5): I ran a real daemon with fake_claude and the committed role + autonomous playbook. The architect's scripted `exec` called the socket's `kit_file` twice, for `foo` and `bar`. Each zip held `.claude/hooks/bash_guard.py`, `.claude/settings.json`, `DESIGN.md` and a `PLAYBOOK.toml`, and no brief. It then replied `VERDICT: next kit foo`.
builder architect kit_id=17ffbe0242206853 gate="apply foo" decided_by=playbook state=done
  check_kit(zip) ok=False failed=[playbook, brief, verdicts, wording]
builder architect kit_id=c2f28cb256f8168f gate="apply bar" decided_by=playbook state=running
  check_kit(zip) ok=False failed=[playbook, brief, verdicts, wording]
stop: builder.done: rule -1 could not send to builder: ... queue_depth is 1
The commit's own FILE_APPLY zip, checked against a fresh repo:
check_kit ok=False [paths True, playbook False, brief False, verdicts False, wording True, protocol False]
Socket probes:
send kit_id=…              -> TypeError: unexpected keyword 'kit_id'
send origin=architect      -> ApiError "origin 'architect' is handsd's own … (§32)"
send role=architect        -> ApiError "… started by handsd only through a playbook `consult` (§27, §32)"
approve decided_by=playbook -> TypeError
method('decide_from_playbook'), method('file_apply') -> None
Rename (probe 6): `test_a_series_rename_that_restates_the_budget_moves_the_anchor` asserts `architect_consults_used() == 0` after only the name changes in a book that already writes `max_architect_consults = 12`.

The worktree `/tmp/rev16-f4fde48` and my probe file are removed, and nothing in `/home/msi/git/hands` was changed.
```

### 44410ea — U4

```
**Review of 44410ea** (mission 16 U4, "Config, doctor, prompt, notifications"). Overall: the gate is green, but I found one blocker candidate and four should-fix candidates.

1. **Unit and sections: PASS.** The commit claims DESIGN §32 "Config and doctor" and "Consult prompt and notifications" (with §31, §11, §10), closing REVIEW-15 blocker 4 and should-fix 4, 5, 6.
2. **Test-first: PASS, but the count in the body is wrong.** With src/ reverted, 34 cases fail across test_daemon, test_docs, test_doctor, test_kit and test_phone. test_playbook fails to import (`next_milestone`); with a stub, 7 of its cases fail. That is 41 red, not the "29 of the new cases" the body and FINAL-REPORT-16 give. The cases the body calls coverage only do pass on the old code.
3. **`./scripts/check`: green** on a clean tree, one run: "3736 passed in 224.79s (0:03:44)" and "check: green".
4. **Design conformance: PARTIAL.**
   - **Blocker 4:** the reviewer's repro is closed for handsd, doctor and `kit check`. A role playbook committed after start still stops the engine.
   - **Blocker candidate (roadmap rule; the report calls it closed):** §32 asks for "the first whose gate is not marked DONE". The code reads "DONE on the milestone's first line", and no finding was filed for that change.
     - At this commit it names M4 (mission 8), whose gate is not marked, so that answer is literally correct.
     - But it treats M4b as done only because its first line says "mission 10 DONE", although M4b's gate is not marked. That contradicts the code's own docstring, which says a sub-mission's DONE is not the milestone's.
     - Mark M4 DONE and the prompt skips M4b and names M4c.
   - **Should-fix candidate (kit check):** `kit check` passes a role-mode kit, exit 0, marked "not judged", on a laptop with two project configs and no `--project`, or with a config that doesn't parse. §32 says "refused"; no finding covers this choice.
   - **Should-fix candidate (kits symlink):** a `kits` link to `.claude` passes doctor, and the guard then lets the architect write `.claude/settings.json` and its own hook file. Links to `.` or `repo` fail only because the self-test happens to go red, not the kits check.
   - **Should-fix candidate (two notifications):** start still publishes twice within a second when a dead daemon left a queued job. The stop came 0.20–0.24 s after "handsd started" for a queued consult driver job, a failing builder job and a failing aux job. The report discloses this (§3.7), but it is the shape REVIEW-15 should-fix 5 complained about.
   - **Should-fix candidate (doctor gaps, disclosed):** doctor stays ok with a second live remote that `remote.pushDefault` or `branch.<b>.pushRemote` points to (a plain `git push` really pushed). It also stays ok with `.claude/settings.local.json` setting `disableAllHooks` plus `bypassPermissions`, with `Write(**)`, `Edit(/**)`, `Bash(*:*)` or `acceptEdits`, and with a `type: prompt` hook under an unanchored regex matcher (`ulti.dit|as`) or `bash`.
   - **Held up:** a `pushInsteadOf` rewrite of `no_push` is not a hole, because git ignores it for an explicit push URL (the push failed on `no_push`). The doctor docstring's "pushInsteadOf expanded" is still inaccurate. `DISABLE`, a local path, `file://`, `..`, a second push URL, `insteadOf`, `Bash|Write`, `*` with a prompt hook, and a relative plus `$CLAUDE_PROJECT_DIR` guard path all behave correctly.
   - **Forbidden files:** DESIGN.md, meta/plan.md and meta/CHECKPOINT.md are untouched. The body lists all 15 files in the stat.
5. **Not proven:** real Claude Code matcher semantics and whether allow entries matter under hooks; real ntfy delivery; roadmap shapes other than this one.

EVIDENCE:
- **Roadmap:** `next_milestone(git show 44410ea:meta/ROADMAP.md)` gives COUNT 9 and names `- **M4 Detectors and the phone channel** — mission 8. …`. With M4's line changed to "mission 8 DONE." it names `- **M4c The architect role** …`, skipping M4b (first line "mission 10 DONE 2026-09-13", gate unmarked).
- **Kit check:** with `~/.hands/demo.toml` and `other.toml`, `HANDS_PROJECT` unset and a role kit, the result is exit 0 and `PASS playbook: … its [series] architect = "role" is not judged against [roles.architect]: no hands config resolves here (<path> configures several projects (demo, other); …)`. A demo.toml that is not valid TOML also gives exit 0 and the same "not judged" line.
- **Kits symlink:**
  - `ln -s .claude kits`, then doctor: role architect status=ok, self-test green.
  - Then `{"tool_name":"Write","tool_input":{"file_path":"<cwd>/.claude/settings.json"}}` piped to `HANDS_ROLE=architect HANDS_KITS=<cwd>/kits python3 .claude/hooks/bash_guard.py --write` exits 0.
  - With a real kits directory the same write exits 2 (blocked).
- **Notifications:** Recorder timings from a real Daemon with phone on and playbook `version = 1`:
  - Queued consult driver job: `0.016 hands: handsd started`, then `0.205 hands: the pipeline stopped | driver.done: the driver's reply has no VERDICT: line`.
  - Queued builder job with `FAKE:exit 1`: `0.016 started`, then `0.24 the pipeline stopped | builder.failed …`.
  - Orphaned builder job and a pipeline stopped before the restart: one publish each.
- **Second remote:** `git remote add up <bare>; git config remote.pushDefault up` leaves doctor at "push URL disabled (no_push)" status=ok, and `git push up HEAD:refs/heads/main` created `refs/heads/main` in the bare repository.

The worktree at /tmp/rev16-44410ea and the probe files are removed; nothing in /home/msi/git/hands was changed.
```

### e091d0b — U5

```
**e091d0b review (mission 16 U5, "Playbook severity"): no blocker candidates.** It claims DESIGN §32's last paragraph, plus §10 (the example) and §24 (the detector). Worktree `/tmp/rev16-e091d0b` has been removed.

1. **Unit and sections:** named correctly. The commit touches none of DESIGN.md, `meta/plan.md` or `meta/CHECKPOINT.md`, and its body lists all 7 files in `--stat`.
2. **Test-first:** confirmed as claimed.
   - With `README.md` and `docs/` put back to the parent, 2 tests in `tests/test_docs.py` went red (the detectors-doc test and `test_no_doc_still_says_a_killed_task_stops_the_series`). With the files restored they passed.
   - The playbook pins are coverage only, since the product files were already `notify` at the parent. Setting `templates/PLAYBOOK-missions.toml`'s rule back to `stop` made both new tests fail for that file (2 red).
3. **Gate:** `./scripts/check` at a clean e091d0b gave `3743 passed in 247.14s (0:04:07)` and `check: green`. I ran it once, not the 3 times the body claims.
4. **Design conformance**
   - **(1) The pin is real, so H-034 was right.** `test_the_fixture_is_section_10s_example_verbatim` compares the fixture to §10's block exactly. The fixture can't say `notify` without a DESIGN edit, which builders may not make.
     - **Note:** the `docs/PLAYBOOK.md` copy is not pinned byte for byte, contrary to what H-034 and the commit say. That test only checks each fixture line appears somewhere in the doc. I changed the copy to `notify` plus a message and all of `tests/test_docs.py` still passed. Leaving the copy as `stop` is still right, because its heading says verbatim.
   - **(2) H-034 is filed correctly.** Its quotes from §10, §24 ("Mission 8, the detectors", last bullet) and §32 match DESIGN. The format matches the other findings, it is `Status: open`, and the direction it gives is sound.
   - **(3) The docs sweep missed some text** (should-fix candidate). The four listed sentences are gone, but the new test checks only those four. Still in the tree:
     - `src/hands/playbook.py:128-130`, the EVENTS comment: "§24: the example playbook maps both to `stop`". The body says the sweep covered docs/, templates/, driver/, architect/ and README, not src/.
     - `docs/PLAYBOOK.md:585`, under the verbatim block: "killed tasks and orphan processes stop and call you". It is unhedged; H-034 leaves it for the next builder.
     - Both templates' message is "The harness killed a task inside a role session", which names a killer §32 says cannot be known.
     - `PLAYBOOK.toml:130-131` says the work "did not finish with it".
     - The docstring of `test_both_docs_say_the_task_killed_cause_is_always_unknown` still says it checks "what the example maps it to", but it no longer checks that.
     - driver/, architect/ and `.claude/` have no such text.
   - **(4) "A job that ends `failed` is what stops" holds in all three playbooks.**
     - **Builder:** a probe chaining `failed` jobs through the engine stopped after 2 resumes for `PLAYBOOK.toml` and the missions template, and after 3 for the runs template, each naming `max_resumes`.
     - **Aux:** `aux.failed` stops in all three.
     - **Driver:** `driver.failed` stops through the engine's enforced stop (and a rule in `PLAYBOOK.toml`).
     - **Architect:** an architect job that ends `failed` stops through the engine.
     - **Note, not U5's doing:** an aux job that ends `orphaned`, `limited` or `killed` is not one of §10's events. In all three playbooks it fires nothing: no stop, no notify.
5. **Not proven:** that a killed task that mattered really ends its job `failed`, the detector under a real harness, and the 3/3 gate runs.

EVIDENCE:
- Doc-copy probe: `sed -i '577s/then = "stop"/then = "notify"\n    message = "A task inside a role job was killed"/' docs/PLAYBOOK.md`, then `uv run pytest -q tests/test_docs.py` printed all dots through `[100%]` with no failure.
- Builder chain probe on `PLAYBOOK-runs.toml`: `[(0,1,False),(1,2,False),(2,3,False),(3,3,True)]`, stop reason "builder has already been resumed 3 time(s) with no `done` in between and [limits] max_resumes is 3".
- Aux probe: states `orphaned`, `limited` and `killed` gave `paused False`, `notified []`, `enqueued []` for all three playbooks.
```

### 6939524 — U6

```
6939524: no blocker and no should-fix. Every point passes, and the gate is green: `3743 passed in 251.64s (0:04:11)` / `check: green` (one run on a clean tree).

1. **Unit.** Mission 16 U6, this repository's playbook. The body cites DESIGN v3.15 §27 Conventions, §10, §26 and §32. The brief's text is "`[series] kickoff` becomes BUILDER-17's line; nothing else."
2. **Test-first: PASS.** I checked out PLAYBOOK.toml from e091d0b and committed it locally in the worktree. Across the six test files that read the root playbook (test_playbook, doctor, phone, kit, config, docs) the result was `1 failed, 1192 passed`. The one failure is the kickoff test, red on the value: `- Read meta/BUILDER-17-PROMPT.m / + Read meta/BUILDER-16-PROMPT.m`. I also confirmed the "wrong red" the body describes: editing the file without committing gives `5 failed, 318 passed`, all 5 `PlaybookNotCommitted`.
3. **Gate: green** (the line above).
4. **Conformance: PASS.**
   - **Diff:** 2 files, 3+/3-. PLAYBOOK.toml changes only the kickoff line. The body names both files. DESIGN.md, meta/plan.md and meta/CHECKPOINT.md are untouched.
   - **Loader:** the real loader on the committed file prints `hands-missions | Read meta/BUILDER-17-PROMPT.md and execute the mission below its divider. | phone | False | 20`, exit 0. The file has 20 `[[rule]]` blocks, matching the body.
   - **Kit check:** the zip's single entry is `cmp`-identical to the brief at 6939524. It passed 6 of 6, exit 0 (output below).
5. **Other claims.**
   - **Doctor warning:** holds. `_go_check` in src/hands/doctor.py returns WARN only when the command channel is on. `_plainly_missing` on the committed kickoff returns `['meta/BUILDER-17-PROMPT.md']`, and that file does not exist.
   - **Stale BUILDER-16 references:** none in README, docs, templates, KIT.md or CLAUDE.md. The remaining BUILDER-16 strings are test fixtures (the synthetic `AUTONOMOUS` playbook in tests/test_playbook.py around lines 3097, 3223, 3531 and 3573, and a kit entry in tests/test_gates.py:240), a doctor.py:299 docstring example, and history under meta/. None claims to be this repository's next kickoff.

**Not proven / notes:**
- **Weak kit-check gate (note):** the kit carries no playbook, so kit check says "its kickoff is not compared". The new BUILDER-17 line is not tested by that gate, and it would pass the same way at e091d0b. REVIEW-15 said the same about 15 U7.
- **Output is condensed (note):** the body's kit-check output is a one-line summary, not the verbatim rows.
- **Missing brief (note):** meta/BUILDER-17-PROMPT.md does not exist yet. This follows the convention (the architect ships it), but a phone `go` sent before it arrives would point the builder at a missing file.
- **Not exercised:** a real daemon, a real phone `go`, `hands pipeline`, and the three-run green (I ran the gate once).

EVIDENCE (kit check output):
$ HOME=$(mktemp -d) uv run hands kit check /tmp/rev16-6939524-kit.zip --repo .
PASS paths: 1 files, every one a repository path under .
PASS playbook: the kit carries no playbook; the repo's PLAYBOOK.toml is in force (loads, no quiet_hours; its kickoff is not compared, §26 compares a kit's)
PASS brief: meta/BUILDER-16-PROMPT.md: kickoff 'Read meta/BUILDER-16-PROMPT.md and execute the mission below its divider.'; final-reply literals VERDICT: mission 16 finished | VERDICT: mission 16 blocked <unit> | VERDICT: question <one line>
PASS verdicts: 5 builder.done verdict rules and the brief's 3 literals match each other; rule 1 matches the apply prompt's 'VERDICT: kit applied <sha>'; 2 aux.done verdict rule(s) match the review protocol's 'VERDICT: review mission N blockers=<k> should-fix=<m>' (placeholders read as counts); 2 driver.done verdict rule(s) match the driver's 'VERDICT: resolved <what was sent, and the section cited>' | 'VERDICT: escalate <reason>'
PASS wording: meta/BUILDER-16-PROMPT.md has no "as before" and no "Budget guidance" section
PASS protocol: every file a send names is present or a placeholder path: meta/REVIEW-PROTOCOL.md (repo), meta/reviews/REVIEW-{n}.md (a placeholder path, not read)
apply prompt: ... (plan: kit rev16-6939524-kit)
kit check: pass (6 of 6 checks)
exit=0

I removed the worktree `/tmp/rev16-6939524` and the temporary zip. The main checkout was not touched.
```
