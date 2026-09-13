# REVIEW-11 — cold review of hands mission 11

VERDICT: review mission 11 blockers=5 should-fix=9

Base `16e679d` (`review: mission 10`, the last `review:` commit on origin/main).
Range `16e679d..4ababb1`: 15 commits.
- The architect's kit `0fef436`.
- Seven builder unit commits: U0 `e8daca8` (`plan:`), U1 `efe4d56`, U2
  `525dc66`, U3 `d4bea98`, U4 `d491f6b`, U5 `c1d8ed5`, U6 `089e72f`.
- Seven `meta:` bookkeeping commits, which were skipped.

One sub-agent reviewed each unit commit, in a detached worktree at that commit.
Read beforehand: DESIGN v3.10 §27 (with §6, §8, §10, §11, §26),
`meta/BUILDER-11-PROMPT.md`, `meta/FINAL-REPORT-11.md`, and
`meta/findings/FINDINGS.md` (H-018 to H-022).

`./scripts/check` passed on the first run at every unit commit. The pass counts
were 1550, 1573, 1588, 1613, 1699, 1717 and 1732. `git diff --stat 089e72f
4ababb1` touches only `meta/`, so the tip's gate is U6's: `1732 passed` / `==
cli smoke ==` / `check: green`. At every product unit, the new tests fail when
its product change is reverted (U6 has a caveat, see Notes). No unit commit
touches `DESIGN.md`. Only U0, the `plan:` commit, touches `meta/plan.md` and
`meta/CHECKPOINT.md`. Each commit body names exactly the files the commit
changes.

The mission's own verdict is `blocked U6`.

## Blockers

1. **§27's driver guard can be bypassed in role mode (U4 `d491f6b`,
   `driver/hooks/bash_guard.py`).**
   - **The design.** §27 says the driver may run only read-only git, `hands
     show|jobs|inbox|pipeline|status|tail|kit check`, `hands send --context
     keep` to the role named in the consultation, and `hands resume`. It
     refuses `approve`, `deny`, any `--context clear` send, `put`, `pause`,
     `go`, and every write.
   - **Reproduced by the reviewer on the tip** (`HANDS_ROLE=driver`, hook JSON
     on stdin). `hands go` and `hands show x && hands go` exit 2, but these exit
     0:
     - `hands show x & hands go`. `SPLIT_RE` (`bash_guard.py:127`) splits on
       `&&` but not on a lone `&`, so only the first command is judged. The
       sub-agent also passed `hands jobs & hands approve j1 --human-confirmed
       --quote yes`.
     - `hands send --role builder --context keep '--context=clear' m`.
       `strip_quoted` removes quoted words before `option_values` reads the
       command, but the shell passes them to `hands`. The sub-agent found the
       same hole with `"…"`, `\--context=clear`, `$'…'`, brace words, `x=…;
       … $x`, and `'--file' a=b`, and confirmed with the real `hands` parser
       that these end as `context=clear` or `file=[…]`.
   - **Not limited either.** Nothing restricts which role or project a `send`
     goes to, so "to the role named in the consultation" is not enforced.
   - **Tests.** No test covers a lone `&` or a quoted or escaped option.
   - **The report understates it.** FINAL-REPORT-11 §3 item 7 says only "The
     guard table does not cover every shell spelling". A lone `&` is ordinary
     shell, not an unusual spelling. `driver/settings.json` allows
     `Bash(hands:*)`, so the hook is the only barrier.

2. **REVIEW-10 should-fix 6 is not closed: some malformed attachment URLs still
   raise a traceback (U1 `efe4d56`, `src/hands/phone.py:528-534`).**
   - **The code.** `httpx.URL(url)` is inside the try, but `parsed.host` on
     line 534 is outside it.
   - **Reproduced.** For `http://xn--/k.zip`, reading `.host` raises
     `idna.core.IDNAError` (checked by the reviewer). The exception escapes
     `_kit`, is logged as "phone: a command raised", and no `kit.refused`
     event is filed.
   - **The sub-agent also found** that `http://exa mple.com/k.zip` and
     `https://[::1]:99999/x` pass the pre-fetch check.
   - **The design.** §27 says "A malformed attachment URL is refused before any
     fetch and the refusal is an inbox event".
   - **The report.** FINAL-REPORT-11 §2 says "no traceback", and the Review
     items table marks SF6 "closed". The disk contradicts both.

3. **The post-exit sweep kills a group whose leader is gone (U1 `efe4d56`,
   `src/hands/runner.py`).**
   - **The design.** §27 says the sweep "signals only a group whose leader is
     the job's own pid and whose members are all descendants".
   - **The code.** When no process holds the leader pid, it still kills the
     group if every live member carries `HANDS_JOB=<id>`. That tests an
     environment mark, not descent. Any process can set the mark, and a member
     that clears its environment stops the sweep.
   - **Disclosed, but no finding filed.** FINAL-REPORT-11 §5 item 5 raises it
     as a note for the architect, but there is no H- entry, although the rules
     require a finding when a unit departs from the design.
   - **Tests.** Killing a marked, leaderless group is tested only through
     `_last_resort` (`tests/test_runner.py:1144`), never through
     `_sweep`/`_kill_group`.

4. **In the fallback, `hands who` can show a job's transcript under the human's
   session (U2 `525dc66`, `src/hands/who.py:385`, `:551`).**
   - **The design and brief.** §27 says a pid with no sessions file "is never
     attributed a job's transcript". The brief says "a transcript belonging to
     a hands job (known pids) is never attributed to a session".
   - **The code.** `by directory` excludes only session ids already in the
     spool (`exclude`). `hands_pids` is used to drop processes from the list,
     but their own `~/.claude/sessions/<pid>.json` is never read to exclude
     their transcripts.
   - **The sub-agent's probe:** job pid 100 had a sessions file naming its
     session, its spool record had no `session_id` yet, and the human had no
     sessions file. The job's prompt was shown on the human's line.
   - **Disclosed, not fixed.** FINAL-REPORT-11 §3 item 5 mentions "a job whose
     transcript appears before its session id is saved". The fix is within the
     unit's authority: exclude the `sessionId` of each hands pid's sessions file.

5. **A mission acceptance line fails: `hands kit check .` exits 1 (U6
   `089e72f`; H-022, open).**
   - **Reproduced** by the U6 sub-agent. The whole-tree kit fails on paths,
     playbook, brief, verdicts and wording, and passes protocol.
     `meta/BUILDER-11-PROMPT.md` alone with `--repo .` passes 6 of 6, but its
     kickoff is not compared. `PLAYBOOK.toml` plus BUILDER-11 fails only the
     kickoff check (BUILDER-12 vs BUILDER-11).
   - **Stopping was right.** Meeting the line needs a BUILDER-12 brief (the
     architect's job) or a repository mode for `kit check` (a DESIGN change).
     The verdict `blocked U6` is honest.
   - **Why it is still a blocker.** The line stays failed until the architect
     answers H-022 (options a/b/c in FINAL-REPORT-11 §5 item 1).

## Should-fix

1. **§27's stops for the driver depend on the playbook (U5 `c1d8ed5`,
   `src/hands/playbook.py` `_rule`/`_match`).**
   - **The design.** §27: "`escalate`, an unrecognised verdict, and
     `driver.failed` stop and notify".
   - **The code.** The engine stops only when no rule matches.
     `parse_playbook` and `kit check` both accept a playbook that carries on
     instead: a verdict-less `driver.done` → `notify`, `verdict='^VERDICT:
     escalate'` → `notify`, or `driver.failed` → `send`. Such a playbook
     escalates without stopping.
   - **What to do.** Refuse such rules at load or in `kit check`, or file a
     finding saying the stop belongs to the playbook.

2. **A driver job that ends any other way is silent (U5, `playbook.py:871-897`).**
   - **Killed, orphaned or limited.** Only `driver.done` and `driver.failed`
     are events. For `driver.killed`, `driver.orphaned` or `driver.limited`,
     `on_event` returns at "not one of §10's events". `consult.done` is filed,
     but there is no stop and no notification, so the builder that asked the
     question waits with nobody told.
   - **Spawn failure.** A driver job that fails to spawn (`daemon.py:455-468`)
     never reaches `on_job`, so it gets no `consult.done` and no journal line.
   - **Tests.** None cover these cases.

3. **`max_consults` stops resetting once `PLAYBOOK.toml` names the next mission
   (U5 `consults_used`, `playbook.py:1149`, with U6's kickoff).**
   - **How it counts.** It counts driver jobs after the last builder job whose
     prompt equals the current kickoff.
   - **The consequence.** From the moment a mission's unit moves the kickoff to
     the next mission (U6 did this), no builder job matches, and every driver
     job in the spool counts. The tail of mission 12 could then hit the limit
     of 2 on consults made in earlier missions.
   - **Open question.** FINAL-REPORT-11 §5 item 3 asks how a mission starts;
     this needs the architect's answer and a test.

4. **REVIEW-10 should-fix 7 is only half pinned (U0 `e8daca8`,
   `tests/test_docs.py:233`).**
   - **What bites.** The test goes red with the doc at `cbb8fc8^`, and when
     `error_max_turns` is flipped to excluded.
   - **What does not.** It stays green with three contradicting edits to
     `docs/INTEGRATION.md`:
     - "none of those is `done`" changed to "is `killed`" (`:130`);
     - "claude exited 0" changed to "exited non-zero";
     - an added sentence that a result with `is_error` false "is `done` even
       with an `error` subtype".
   - **What to do.** Pin the `done` statement as one string, as SF7 asked.

5. **The H-018..H-021 status lines were not updated in place (U0,
   `meta/findings/FINDINGS.md:987,1020,1089,1121`).**
   - **What U0 did.** It added a new section at `:1123-1151` with the
     resolutions.
   - **What is left.** Each finding's own `Status:` line still says `fixing` or
     `open`, while the brief said "set their status lines". A reader who finds
     a finding by its heading sees it as open.

6. **`kit check` still passes some missing protocol paths (U1, `src/hands/kit.py`
   `_NAMED_FILE_RE`, `:699`).**
   - **The design.** §27 refuses "a protocol path a rule names that the kit or
     repo lacks".
   - **The gaps.** Only `.md` and `.toml` names are checked, so a missing
     `meta/MISSING.txt` (a case REVIEW-10 listed) exits 0. Any name with `{`
     is skipped as a placeholder, so `../{n}.md` passes unjudged.

7. **The apply-verdict check still excuses some weak rules (U1, REVIEW-10 SF4).**
   - **What works.** The review's typo probe now fails.
   - **What still passes.** A plain `^VERDICT: kit` `builder.done` rule is
     excused as matching the apply literal. An `aux.done` rule with a typo'd
     alternative (`(blockers=0|blokers=0)`) passes, because one matching
     branch is enough.

8. **Doctor's driver "guard mode" row proves nothing (U4, `src/hands/doctor.py`).**
   - **How it is built.** The mode comes from `spawn_env`, so it always reads
     `driver`. The hook is checked only for containing the text `HANDS_ROLE`.
     Nothing checks that the driver's `.claude/settings.json` actually wires
     the hook up.
   - **What §27 asks.** That doctor report the guard mode.

9. **The apply prompt from `KIT.md` (U3 `d4bea98`, `kit.py`
   `kit_md_line`/`apply_prompt`).**
   - **Quoting.** `KIT.md`'s first line goes into the quoted commit message
     unescaped and with no length cap. A `'` garbles the prompt the builder
     receives.
   - **Byte-equality.** The daemon's prompt equals `kit check`'s only when the
     kit sits at `~/Downloads/<same name>`, because `kit check` hardcodes
     `KIT_DIR_SHOWN`. This is disclosed in §3 item 6.
   - **The claim.** "what the architect saw is what runs" holds only in that
     case.

## Notes

- **§3 NOT PROVEN, compared with the sub-agents' findings:**
  - Item 7 (U4) understates blocker 1.
  - Item 4 (U1) does not mention the IDNA traceback (blocker 2), and item 4's
    sweep limits do not say that the implementation departs from §27
    (blocker 3).
  - Item 5 (U2) does disclose blocker 4's case.
  - Items 1–3, 6, 8 and 9 match what the sub-agents found.
  - The Review items table's SF6 row ("closed") is contradicted by the disk.
    The SF7 row ("phrase containment only") is honest.
- **The lone-`&` hole predates role mode.** The guard in normal mode also
  passes `hands show & hands open x`. The fix is the same `SPLIT_RE` change.
- **U2 has no staleness check on sessions files.** A leftover `<pid>.json` from
  an earlier process with the same pid attributes an old transcript. §27 is
  silent on this.
- **U5's end-to-end driver does not set `HANDS_ROLE`.** `fake_claude` runs the
  real `hands send --context keep`, but the guard is not exercised end to end.
- **U5's journal line** is appended synchronously to `role.builder.cwd/meta/
  journal.md`. A builder job running at the same time can overwrite it. This is
  untested.
- **U5's `resolved` rule is `notify`,** so the phone buzzes on every resolved
  consultation (FINAL-REPORT-11 §5 item 2, for the architect).
- **U6's test-first reds are partly confounded.** Tests that load
  `PLAYBOOK.toml` also fail on a reverted working copy because of
  `PlaybookNotCommitted`, not only because the rules are missing. The cleanly
  red cases (question, unrecognised verdict, driver resolved/escalate,
  INTEGRATION driver cwd) are enough.
- **U6's rule order is correct.** `finished`, `kit applied` and `blocked` come
  before `question` and the `^VERDICT:` catch-all. Nothing consults on
  `aux.done`, `aux.failed`, `job.held` or monitor events. `driver.failed` and
  unrecognised driver verdicts stop (`PLAYBOOK.toml:67`, `:72`).
- **U3 conforms.** `handsd` extracts nothing and reads only `KIT.md` in memory.
  One function (`plan_apply` → `apply_prompt`) builds the prompt for both
  `kit check` and the daemon, and the gate reason and default message use the
  same name.
- **U4 config and doctor conform.** `permission_flags` is refused at config
  load and by doctor. `HANDS_ROLE=driver` is set last in `spawn_env`, so
  neither the config nor the daemon's environment can remove it. `hands send
  --role driver` is refused. Many compound spellings are refused correctly:
  `;`, `&&`, `|`, `$(…)`, backticks, newlines, `git -c core.pager=…`,
  `--output=`, `git config`, `env HANDS_ROLE= …`, `uv run hands go`, and
  `/usr/bin/hands go`.
- **No leftover worktrees.** `git worktree list` shows only the main checkout
  after the review.

## Per-commit verdicts

### e8daca8 (U0)

**e8daca8** (mission 11 U0, `plan:` commit, parent 0fef436). Point 3 passes, point 2 fails, points 1 and 4 pass with defects. My worktree is removed (the other `/tmp/rev11-*` worktrees aren't mine and I left them).

1. **Unit and sections: PASS.** The body names U0 of meta/BUILDER-11-PROMPT.md, DESIGN v3.10 §27 and §6, REVIEW-10 should-fix 7 and H-018..H-021. It lists all 4 files that `--stat` shows.
2. **Test-first: FAIL for REVIEW-10 should-fix 7's purpose.** The new test is `test_the_integration_doc_states_section_6s_error_subtype_rule` (tests/test_docs.py:233). It passes on the commit. It fails with docs/INTEGRATION.md from cbb8fc8^ (assert at :248), as the builder said, and it fails when `error_max_turns` included becomes excluded. But it stays green on three wrong docs:
   - INTEGRATION.md:130 "none of those is `done`" changed to "is `killed`";
   - :130 "claude exited 0" changed to "exited non-zero";
   - an added sentence saying a result with `is_error` false "is `done` even with an `error` subtype".

   So the `done` statement itself is not pinned, and a doc that contradicts §6 still passes. Should-fix 7 asked that the doc and `_failure_reason` "cannot part again unseen", which this doesn't achieve. The body's "Not proven" line admits the contradiction case, but the review item is marked "closed". The test should at least pin "is `done`: claude exited 0 with a final `result` of subtype `success` carrying `num_turns`" as one string. The tree was restored after each mutation.
3. **Gate: PASS**, first run, rc=0: `1550 passed in 124.94s (0:02:04)` / `== cli smoke ==` / `check: green`.
4. **Design conformance: PASS with a defect.** No DESIGN.md is touched, and plan.md and CHECKPOINT.md are allowed in the orchestrator's `plan:` commit. The four resolutions (FINDINGS.md:1123-1151) quote §27 faithfully; for H-018 and H-019 the quotes are exact. H-018's mention of the held-job `go` refusal really comes from §27's should-fix list, not from H-018, but it says so. H-020 adds a note of its own about `entrypoint`/`.key` that §27 does not contain. The defect: they sit in a new section at the end of the file, not under each finding. The old status lines were left as they were:
   - :987 H-018 "fixing"
   - :1020 H-019 "open"
   - :1089 H-020 "open (U4 blocked on DESIGN)"
   - :1121 H-021 "open"

   Someone reading a finding in place still sees it as open. That is weaker than "set their status lines".

**Not proven:** why `-k section_6s` picks up 2 tests (I didn't dig), and whether the runner-side test in test_runner.py matches this doc pin.

### efe4d56 (U1)

**efe4d56** (mission 11 U1; §27 with §26, §6, §10; REVIEW-10 should-fix 1, 3, 4, 5, 6; H-021). Both of my worktrees are removed.

1. **Unit, sections, files: PASS.** The body names U1, §27 and H-021, and its 13 files match `git diff --name-only` exactly. DESIGN.md, meta/plan.md and meta/CHECKPOINT.md are untouched.
2. **Test-first: PASS.** I reverted `src/` to the parent. The old runner has no `JOB_ENV`, so I added that one name to let test_runner collect. 33 tests went red, covering every item: SF1 held-job `go` and the re-check after the load; SF3 the strangers' group (sweep and last resort) and the `HANDS_JOB` env test; SF4 the probe rule, the three aux.done tests and the passing-kit test; SF5 `.GIT`/`.Git`, duplicate name, NUL, both size caps, the 4 send-path cases and the symlinked protocol; SF6 the 3 malformed URLs and the 8 pre-fetch `kit.refused` cases. No item stayed green. Tree restored clean.
3. **Gate: PASS** on the first run. Tail: `1573 passed in 126.69s (0:02:06)` / `== cli smoke ==` / `check: green`.
4. **Conformance: PASS with defects.**
   - **SF6 defect (malformed URL).** At `src/hands/phone.py:482`, `parsed.host` is read outside the try at :478-481. `http://xn--/k.zip` raises `idna.IDNAError` from there. It escapes `_kit` and is logged as a traceback ("phone: a command raised", :254) with no `kit.refused` event, which is the same class of failure as should-fix 6. The IDNA message did not contain the URL in my probe. `http://exa mple.com/k.zip` and `https://[::1]:99999/x` also pass the pre-fetch check.
   - **SF3 sweep: a design deviation with no finding.** When the leader holds the pid with the recorded start time, the rule is sound: session members descend from claude. When no process holds the pid, it kills the group if every live member carries `HANDS_JOB=<id>`. §27 says "whose leader is the job's own pid", so it is not silent there, and a leaderless group with an env mark in place of descent needs a finding. The mark is a stand-in, not a parent chain: any process can set it, and a member that clears its environment blocks the sweep. The marked, leaderless group being killed is tested only through `_last_resort` (`tests/test_runner.py:1144`), never through `_sweep`/`_kill_group`.
   - **SF5, a protocol path the kit or repo lacks:** refused for `.md`/`.toml` (a missing `meta/MISSING.md` exits 1). Still passing (exit 0), from `src/hands/kit.py:110` and the `{`-skip at :608: a missing `meta/MISSING.txt` (REVIEW-10 listed `.txt`), and `../{n}.md`, which the placeholder skip ignores.
   - **SF4:** the typo probe fails as claimed. Two weaker rules still pass: the plain pattern `^VERDICT: kit` gets the apply exception, and an aux.done rule with a typo'd branch (`(blockers=0|blokers=0)`) passes because matching one branch is enough.

**Not proven:** a real pid reuse, a real `hands send` racing `go`, a real ntfy attachment, the directory-kit size cap, and behaviour on a case-insensitive filesystem.

### 525dc66 (U2)

Review of 525dc66 (`who: match a session to its transcript through ~/.claude/sessions/<pid>.json`): acceptable as a first cut, but the brief's gate is only partly met in the fallback.

1. **Unit and design sections: pass.** The commit body names mission 11 U2, DESIGN v3.10 §27 (H-020), §4 `who` row, §11, §24, §26, REVIEW-10 blocker 1 and FINDINGS H-020.
2. **Test-first: pass.** Against the parent `who.py`, all 15 new test cases fail (35 failed, 15 passed in `test_who.py`). Against the parent `INTEGRATION.md`, `test_docs.py` has 1 failure and 58 passes. At the commit, both files pass (109).
3. **Gate: pass on the first run.** `./scripts/check` ended with `1588 passed in 153.09s (0:02:33)`, `== cli smoke ==`, `check: green`, exit 0.
4. **Conformance: mostly pass.** `DESIGN.md`, `meta/plan.md` and `meta/CHECKPOINT.md` are untouched, and the commit body lists all 4 files. `sessionId` is checked against `[A-Za-z0-9][A-Za-z0-9_-]*` before any path is built; `..`, `../x`, `a/b`, `*`, `[ab]`, `x.jsonl`, `-rf`, newline and NUL are all rejected. A sessions file naming a missing transcript gives `state unknown` with no directory fallback, which is sane. Only `pid` and `sessionId` are read, and the `.key` file is never opened.
   - **Defect (medium), `src/hands/who.py:551` and `:385`.** In the `by directory` fallback, a job's transcript is excluded only if the spool record already holds its `session_id`. The brief says jobs are identified by known pids, and `hands_pids` (`:550`) is never used for this. I probed it: job pid 100 has `sessions/100.json` naming its session, the spool record has no `session_id` yet, and the human has no sessions file. The job's prompt was shown under the human's line. Fix: also exclude the `sessionId` from each hands pid's `<pid>.json`.
   - **Defect (low), `src/hands/who.py:371-380`.** A sessions-file match has no age or staleness check. With a leftover `200.json` from a crashed, earlier process of the same pid, a 60s-old session was shown a week-old transcript's state. §27 doesn't address this.

**Not proven:** a real `~/.claude` or other Claude Code versions (the file's shape comes from one 2.1.270 sample); jobs recorded in another spool; the probe above in an end-to-end run with the daemon up; and, as the builder disclosed, another human's transcript can still appear under `by directory`.

Both of my worktrees are removed and `/home/msi/git/hands` is clean. The other `/tmp/rev11-*` worktrees still listed were not mine.

### d4bea98 (U3)

**d4bea98**, mission 11 U3, "the apply from the kit". The commit body cites DESIGN v3.10 §27 and H-018, plus §6/§8/§10/§11/§26. **Verdict: accept, no blocking defects.**

1. **Test-first: red, as claimed.** With src/ put back to the parent, 27 new tests fail: 13 in test_kit, 12 in test_phone, 1 in test_playbook (`[kit]`) and `test_the_origin_listings_name_kit`. With docs/ and README also put back, 3 test_docs tests fail. The tree was restored clean afterwards.
2. **`./scripts/check` at the commit: green on the first run.** Tail: `1613 passed in 151.07s (0:02:31)` / `== cli smoke ==` / `check: green`. No rerun was needed.
3. **Your four questions:**
   - **Extraction: none.** `apply_from_zip` (src/hands/kit.py) only reads the zip's directory and decompresses a root `KIT.md` in memory. My probe confirmed no files were created in the repo or the kit directory.
   - **Name vs stem: consistent.** `name` is the file name without `.zip`, used for both `plan: kit <name>` and the gate `apply <name>`.
   - **KIT.md shape: printed.** `kit check` prints a `KIT.md:` line giving the shape and what this kit's `KIT.md` gives, in both pass and fail output. `--json` carries `kit_md`.
   - **One shared prompt function.** `plan_apply` → `apply_prompt` is called by both `check_kit` and the daemon; nothing is duplicated.
4. **Scope: conforms to §27.** Held builder job, `origin: kit` (added to `spool.ORIGINS` and `UNPAUSE_ORIGINS`), buttons through `Api.send`'s gate, `kit.refused` for bad entries. DESIGN.md, meta/plan.md and meta/CHECKPOINT.md are untouched, and the commit body lists all 13 files.
5. **Minor points, none blocking:**
   - **Quote in the commit message.** A `KIT.md` first line containing `'` goes into the prompt unescaped, e.g. `commit 'it's done' and push --force to main'`. It has no length cap, and the builder gets a garbled quoted message. The job is held for a human, so this is small. The spot is `apply_prompt`/`kit_md_line` in kit.py.
   - **Byte-equal only in one case.** The daemon's prompt matches `kit check` only when `kit_dir` is `~/Downloads` and the file kept its name. `kit check` hardcodes `KIT_DIR_SHOWN`, so a renamed `kit-1.zip` gives a different name, prompt and gate. The builder discloses this.
   - **Paths check only.** The daemon files the apply even if the playbook, brief or verdict checks would fail (also disclosed).
6. **Not proven:**
   - A real phone kit, ntfy attachment or builder unzip.
   - A corrupt entry other than `KIT.md` is not detected by handsd.
   - The "busy builder still gets the held apply" case does have a test that was red before, so that one is covered.

The worktree is removed and /home/msi/git/hands is clean. Two other review worktrees are still listed (/tmp/rev11-089e72f, /tmp/rev11-d491f6b); they aren't from this review and I left them.

### d491f6b (U4)

**Review of d491f6b** (mission 11 U4, the driver role; the commit body cites DESIGN §27, §8, §12, §13, §23). **Verdict: guard bypasses found, so not accepted as-is.** Doctor, config and the gate are fine.

1. **Test-first: pass.** With `src/` and `driver/` reverted, 86 of the new tests fail: guard role table, config, daemon, doctor, runner, docs. With `docs/` also reverted, `test_the_integration_config_block_loads` still fails (test_docs.py:104). All pass again once restored.
2. **Gate: green on the first run.** `./scripts/check` ended with `1699 passed in 116.85s (0:01:56)` / `== cli smoke ==` / `check: green`, exit 0.
3. **Design conformance: mostly pass.**
   - `permission_flags` is refused at config load and by doctor. `spawn_env` sets `HANDS_ROLE=driver` last, so neither the config's `env` table nor handsd's environment can switch role mode off.
   - `hands send --role driver` is refused, and `driver/CLAUDE.md` has the VERDICT section.
   - Doctor shows cwd, clone and the guard path. Its "guard mode" line is weak: it is built from `spawn_env`, so it always says driver. It only checks that the hook file contains the text `HANDS_ROLE`, and never checks that `.claude/settings.json` wires the hook up.
   - DESIGN.md, meta/plan.md and meta/CHECKPOINT.md are untouched, and the commit body lists all 13 files.
4. **Correctly refused** (exit 2): `;`, `&&`, `|`, `$(...)`, backticks, newlines, `git -c core.pager=touch log`, `git log/diff --output=f`, `git config`, `env HANDS_ROLE= hands go`, `--context keep --context clear`, `--context=clear`, `--cont clear`, `--c=clear`, `uv run hands go`, `/usr/bin/hands go`, `hands --json go`.

**Bypasses found.** Each was run through the guard with `HANDS_ROLE=driver` and got exit 0. For the `send` cases I checked with the real `hands` argument parser that it ends up with `context=clear` or `file=['a=b']`. `driver/settings.json` allows `Bash(hands:*)`, so as far as I can tell (not tested against a real claude session) nothing else stops these:
- **A single `&`**: `hands show x & hands go` and `hands jobs & hands approve j1 --human-confirmed --quote yes`. `SPLIT_RE` (bash_guard.py ~line 127) splits on `&&` but not on a lone `&`, so only the first command is judged. The same hole already existed without role mode, e.g. `hands show & hands open x`.
- **Quoted or escaped options**, which the guard strips before reading while the shell keeps them:
  - `hands send --role builder --context keep '--context=clear' m`, and the same with `"..."`, `\--context=clear`, `$'--context=clear'` or `{--context=clear,m}`
  - `x=--context=clear; hands send --role builder --context keep $x m`
  - `... --context keep '--file' a=b m` and `\--file a=b m`
  
  The cause is in `strip_quoted` (~line 145, which drops `\` together with the next character) feeding `option_values`/`hands_role_violation` (~lines 344–390). Those only look at the words left over, and `$x` and brace words go unjudged.

**Not proven:** none of the new tests cover a lone `&` or quoted/escaped options. The guard doesn't limit `--project other` or `--gate` on a send, so it can't enforce "to the role named in the consultation". Nothing shows a real claude session honours the hook.

Both worktrees are removed and `/home/msi/git/hands` was not modified.

### c1d8ed5 (U5)

**c1d8ed5, U5 `consult` (DESIGN §27 bullets 2-3, §10, §11, §6): PASS with should-fixes.** It passes the gate and matches the design in the normal path. The §27 rule that escalate, an unrecognised verdict and `driver.failed` always stop is only guaranteed by the example playbook, not by the engine.

1. **Test-first: red as expected.** Against the parent's `src/`, `tests/test_playbook.py` fails to load (it imports `consult_prompt`, `CONSULT_QUESTION` and `DRIVER_VERDICTS`), so all 11 new playbook tests are red. Both new tests in `tests/test_kit.py` fail (the parent refuses `max_consults`). After `git checkout HEAD -- .` the tree was clean.
2. **Gate: green on the first run.** `./scripts/check` tail: `1717 passed in 162.17s` / `== cli smoke ==` / `check: green`.
3. **Design conformance:**
   - **Question text:** exactly §27's (`playbook.py:116`), pinned by a test.
   - **Driver reply stored verbatim:** yes, as the job's `result`; the end-to-end test checks `driver["result"] == resolved`.
   - **Resolved end-to-end test is real:** the scripted driver runs the real `hands send --context keep`, and the test checks that the new builder job reuses the first builder job's session. The `exec` addition to `tests/fake_claude.py` doesn't make anything pass on its own. It doesn't set `HANDS_ROLE=driver`, so the driver guard isn't exercised.
   - **Stops depend on the playbook (should-fix).** The engine stops only because the example playbook has no catch-all `driver.done` rule and no `driver.failed` rule. I checked that `parse_playbook` accepts all of these, and kit check doesn't catch them either (it only looks at rules that have a `verdict`):
     - `on="driver.done"` with no verdict and `then="notify"`;
     - `verdict='^VERDICT: escalate'` with `then="notify"`;
     - `on="driver.failed"` with `then="notify"` or `"send"`.
     With any of these, an escalation, unrecognised verdict or failure goes on without a stop, which breaks §27. The fix belongs in `_rule` (around `playbook.py:621`) or in kit check.
   - **Killed driver jobs stop nothing (should-fix).** Only `driver.done` and `driver.failed` are events (`playbook.py:100-101`). A driver job that is killed or orphaned files `consult.done`, then `on_event` returns without a stop, so the builder waits and nobody is notified. A driver job that can't be spawned (`daemon.py:455-468`) never reaches `on_job`, so it gets no `consult.done` and no journal line.
   - **Journal:** the path is fixed to `roles.builder.cwd/meta/journal.md`, so nothing is written outside that directory. The daemon appends synchronously, but a builder job running at the same time (for example the driver's own keep send) can edit the same file and overwrite the line. This is minor and untested.
   - **Limit and resolved rule:** `max_consults` counting works as the architect described, and the resolved rule does notify, so the phone buzzes on every resolved consult.
4. **Protected files:** `DESIGN.md`, `meta/plan.md` and `meta/CHECKPOINT.md` are untouched. The commit body lists all 11 changed files.

**Not proven:** `consult.done` for a driver job that is killed, orphaned, limited then resumed, or fails to spawn; two consults while the driver is busy; consults on monitor or `job.held` events; a real claude driver under role mode.

The review worktree `/tmp/rev11-c1d8ed5` is removed. The other `/tmp/rev11-*` worktrees still listed aren't this review's.

### 089e72f (U6)

I reviewed 089e72f (U6, this repository's playbook; DESIGN §27, §10, §13). It is conformant, and `blocked U6` was the right verdict: H-022's diagnosis holds. I found no defects in the product files. Your list's "Scrutinize" questions are answered under point 4.

1. **Unit and sections:** the commit body names U6 and DESIGN §27, §10 and §13, and lists all 5 files. It touches no DESIGN.md, meta/plan.md or meta/CHECKPOINT.md.
2. **Test-first: red as expected, with one caveat.** With PLAYBOOK.toml and INTEGRATION.md reverted, 10 of the selected tests failed. The ones that are cleanly red are the question, unrecognised-verdict and no-VERDICT builder cases, driver resolved and escalate, and the INTEGRATION driver cwd. The caveat: the tests that read PLAYBOOK.toml through the loader also fail on a reverted working copy only because the loader refuses a playbook that differs from HEAD (`PlaybookNotCommitted`). That includes two older ones, so those reds are confounded and not proven for the right reason. The aux/never-consult cases pass either way, which fits their role as regression guards.
3. **`./scripts/check`:** green on the first run, `1732 passed in 155.43s`, `check: green`, exit 0. No rerun was needed.
4. **Design conformance: pass.**
   - **Rule order:** rules match top to bottom (playbook.py:935). Finished, kit applied and blocked come before question and the `^VERDICT:` catch-all (PLAYBOOK.toml:14-50), so nothing is shadowed and those verdicts never reach the catch-all.
   - **Catch-all scope:** because it needs a `VERDICT:` line, it only catches unrecognised verdicts; a reply with no `VERDICT:` line still stops per §10.
   - **Driver follow-ups:** resolved notifies, escalate stops, any other driver verdict stops (:67) and `driver.failed` stops (:72).
   - **Nothing else consults:** `aux.done`, `aux.failed`, `job.held` and the monitor events are notify or stop only.
   - **Kickoff change and `max_consults`:** `consults_used` (playbook.py:1149) counts driver jobs after the last builder job whose prompt equals the current kickoff. Now that the kickoff names BUILDER-12, no job matches, so every driver job in the spool counts. Today that is harmless: `~/.hands/jobs` holds no driver jobs, only the BUILDER-10 and BUILDER-11 kickoff jobs. From mission 12 on, though, each mission's tail after its playbook unit will count every earlier consult and can hit the limit of 2. That comes from the design, not this unit, and should be flagged to the architect.
   - **H-022 reproduced:**
     - `kit check .` exits 1: paths, playbook, brief, verdicts and wording FAIL; protocol PASS. In a fresh worktree the paths failures are `.git` plus `.venv` symlinks rather than 1896 `.git` entries, but the cause is the same.
     - A kit of BUILDER-11 alone with `--repo .` passes 6 of 6, exit 0, but its kickoff is not compared.
     - PLAYBOOK.toml plus BUILDER-11 fails only the kickoff check (BUILDER-12 vs BUILDER-11), exit 1.
     - PLAYBOOK.toml alone fails 4 checks, exit 1.
   - **Could U6 have met the gate itself?** Only by reading the gate as the brief-in-force kit, which does exit 0 but doesn't compare the kickoff. Otherwise it would take writing BUILDER-12 (the architect's job) or changing `kit.py` (a design change), both outside U6's authority. Recording the passing form and blocking was correct.

**Not proven:** a real driver consultation, handsd loading this file under the real config, and a red run on committed reverted files.

The worktree /tmp/rev11-089e72f and my /tmp kits are removed. Another worktree, /tmp/rev11-d491f6b, is still there; it isn't mine and I left it alone.
