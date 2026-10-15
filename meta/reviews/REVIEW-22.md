# REVIEW-22 — cold review of hands mission 22
reviewed: baa0b6eadb0678e8440170938277fbc46d184dfa

VERDICT: review mission 22 blockers=0 should-fix=12

Shape: pull request, first review of the branch. `meta/BUILDER-22-PROMPT.md`
§Branch says "Pull request" on `mission-22`. `gh pr list --head mission-22
--state open` returns PR #3 (base `main`, headRefOid `baa0b6e`). The base is
`git merge-base origin/main origin/mission-22` = `7ddc0e8` (the kit). The
commits under review (`git log --oneline 7ddc0e8..origin/mission-22
^origin/main`):

    baa0b6e report: mission 22 final report
    9fae4ee docs: the self-hosted corrections, python3 -I everywhere, handbook §13-§18
    f1936b1 project: hands project add <name> --repo <url> [--dry-run]
    b6e2511 docs: the installed handbook and templates; hands handbook; HANDS_DOCS on every role job
    7df5bce templates: the owner-decisions file, the keep-after-question rule, the human-supplied unit and the Purpose block
    cfb7e71 protocol: revert per file (checkout at the parent or rm); Notes carry the schedule; owner and human-supplied commits
    22a2ef5 playbook: since-last-consultation is git log <sha>..HEAD; owner paths via ls-files --full-name
    f16c331 phone: progress <secret>, the tenth command, publishes the builder's job, branch, last commits and checkpoint line
    69364de playbook: a blocked mission consults the architect role
    96d3fbb daemon: a daemon stop records its running jobs orphaned and the next start feeds them to the engine
    5f3b7ad who, doctor: handswho publishes on change only, with a floor; doctor warns on a public broker
    3feb89b notify: the Approve/Deny buttons carry the bearer when ntfy_token is set
    759f605 plan: mission 22 plan, branch mission-22, H-049 and H-050

One sub-agent per unit commit (U1–U11), one at a time. I read the `plan:` (U0)
and `report:` (U12) commits myself.

## Blockers

None.

## Should-fix

1. **U2 (5f3b7ad): the blanked-picture comparison, H-046's headline
   mechanism, is held by no test.**
   - With `who.py`, `config.py` and `doctor.py` reverted to the parent, the
     scan-level tests the brief names still pass: times-only scans publish
     once, a real change publishes, two changes 10 s apart, a request inside
     the floor. The parent's fingerprint already excluded times and already
     had a 60 s gap.
   - Mutating the new comparison to `changed = fp != self.fp` leaves all of
     tests/test_who.py green.
   - The parts that are proven: the 429 floor (red when the stamp moves back
     to success-only), `blank_times`, the config key and doctor.
   - Fix: a test whose fingerprint changes while the blanked picture does not,
     or the reverse, so the new half is pinned.
2. **U2 (5f3b7ad): a stale stored fingerprint lets the human's own session
   cause a push, against §24 ("the human's own sessions shown but never
   fingerprinted"; who.py:923/931).**
   - `self.fp` is stored only on a publish.
   - If a publish fires while a peer session's debounce is pending, the next
     scan's fingerprint changes but its blanked picture does not, so nothing
     publishes and the stored fingerprint stays stale.
   - After that, a change in the human's own session alone (picture only)
     satisfies "both differ" and publishes.
   - The sub-agent reproduced this with the real `Debounce`, scans
     `[True, True, False, True]`, and I re-read the repro.
   - FINAL-REPORT-22 §3 discloses the stale fingerprint, but not that it
     breaks §24.
   - Fix: store `fp` whenever the blanked picture equals the last published
     one.
3. **U3 (96d3fbb): a phone `reply` (architect) or `answer` (builder) that a
   daemon stop ends is never published (daemon.py:661-664).**
   - `_run` returns early on `orphaned` before `_reply_ended`, and
     `_feed_orphans` calls only `playbook.on_job`.
   - Before this commit such a job ended `killed` and the phone was told.
   - A builder `answer` (context `keep`) is re-sent by a
     `builder.orphaned → resume` rule with context clear.
   - Untested. The hosted review's finding 4 says the same.
4. **U3 (96d3fbb): the start notification says "which a daemon stop
   orphaned" for every resumed orphan (daemon.py:290-294).** That includes
   crash orphans that `reconcile_orphans` found, whose `orphan_reason` is
   null. The hosted review's finding 7 says the same.
5. **U4 (69364de): the load-time "the verdict regex names blocked" check is a
   substring test on the pattern text (`BLOCKED not in verdict.pattern`,
   playbook.py:1117).**
   - It accepts patterns that consult on non-blocked replies: `not-blocked`,
     `unblocked`, `^(?!.*blocked)`, `(blocked|finished)`. Those would give a
     finished reply to the architect under the "blocked verdict" heading.
   - It refuses `(?i)…BLOCKED`.
   - §38 asks only that `kit check` accept the rule, so the load refusal is
     the builder's own addition. The body says so, but no finding records it.
   - Fix: judge the compiled regex against sample verdict lines, and file the
     refusal for the design.
6. **U5 (f16c331): `progress` reads `<builder cwd>/meta/CHECKPOINT.md`, not
   the working tree's root.**
   - A builder cwd below the repository root, the case §38 fixes for owner
     files in U6, answers "no checkpoint" while the file exists at the root.
   - README.md:131-133's phone-command list also omits `progress` (and
     `answer`, which it lacked before).
7. **U6 (22a2ef5): two fallbacks are no longer inclusive.**
   - An owner file committed since the consultation but no longer tracked at
     HEAD is now silently omitted. Before, it was listed with a "no committed
     copy" note.
   - An unknown or garbage-collected recorded sha gives an error line and
     lists no owner files, where the method's own stated rule is that every
     commit counts.
   - The body discloses the first. §36 says "every … file committed since".
8. **U7 (cfb7e71): the new revert step's restore fails for a file the commit
   deletes (templates/REVIEW-PROTOCOL.md:67-70 and meta/).**
   - Such a file exists at the parent, so the step checks it out.
   - `git checkout <sha> -- <the same files>` then stops with "pathspec did
     not match" and restores none of the files. The sub-agent showed this in
     a scratch repo.
   - This is H-049's failure turned around, and the step does not require a
     clean `git status` afterwards.
   - It needs a finding, since §38 prescribes the wording: `git rm` a file
     absent at `<sha>`, then check the tree is clean.
9. **U8 (7df5bce): architect/CLAUDE.md rule 13 makes a design decision
   without a finding.**
   - The role never files an owner file in a kit; it escalates "under rule 8"
     with a draft.
   - Rule 8's conditions do not include a ruling (a builder's
     `VERDICT: question`, a blocked mission), so a role following it
     literally finds no matching condition.
   - §38 says only that both instructions tell the architect to answer
     rulings with the owner file.
10. **U9 (b6e2511): HF-002 is recorded "resolved" in FINDINGS while H-051
    says the role half does not work.**
    - The final report says "resolved as far as the files ship and the
      variable is set"; FINDINGS does not qualify it.
    - architect/CLAUDE.md rule 2 now sends the role to `$HANDS_DOCS/…`. The
      sub-agent confirmed that the role's guard refuses `echo $HANDS_DOCS`,
      `hands handbook`, `printenv`, `env` and `cat` of the handbook. So until
      H-051 is ruled, the role has no handbook it can read.
    - The `hands handbook` help text (cli.py:361) says the handbook's
      directory is `$HANDS_DOCS`, but it is `$HANDS_DOCS/docs`.
    - Fix: mark HF-002 partly resolved, pointing at H-051.
11. **U10 (f1936b1): `hands project add` passes the URL to `git clone`
    without `--`, and a failed clone leaves a project that cannot be
    re-added.**
    - `--repo '--upload-pack=…'` is parsed as an option (project.py:285). It
      ran nothing only because the clone path did not exist yet. The URL is
      the human's own argument, so the risk is low.
    - After a failed clone, these are left behind and the command does not
      say what to remove: the config and secret, the unit, both role
      directories with settings, guard and CLAUDE.md, `kits/`, and
      `handsd@<name>` enabled. A re-run is refused as "exists".
    - Untested. The hosted review's finding 5 says the same.
12. **U11 (9fae4ee): one shipped hook is still spelled without `-I`.**
    - `.claude/settings.json:9` runs
      `python3 "$CLAUDE_PROJECT_DIR"/.claude/hooks/no_background.py`.
    - docs/INTEGRATION.md:1535-1546 tells every role's cwd to copy that file,
      and its self-test line also lacks `-I`.
    - `no_background.py` imports json, re and sys, so it is open to the same
      planted-module attack `-I` closed for the guard.
    - §38's rule names only the guard, so this needs a finding, not a silent
      fix.

## Hosted review

`qodo-code-review[bot]` posted "Qodo is busy working" at 15:04:53Z. It then
posted a review on the tip `baa0b6e` at 15:09:47Z, with seven inline comments
and a summary comment (6195302298). The findings, quoted verbatim by their
titles:

1. "Readers see the verdict too late" (meta/FINAL-REPORT-22.md:3):
   **dismissed.**
   - The playbook matches the builder's reply, not the report file
     (PLAYBOOK.toml `^VERDICT: mission (?P<n>\d+) finished`).
   - The report's shape, a title line and then the VERDICT line, is the one
     every earlier report uses (FINAL-REPORT-21 included).
2. "Test evidence lacks raw command output" (meta/FINAL-REPORT-22.md:128):
   **dismissed.**
   - As in REVIEW-20 and REVIEW-21: short shas are the repository's
     convention, and this review records the full tip as `reviewed:`.
   - The sub-agents reproduced every gate count the report gives: 4269, 4300,
     4308, 4317, 4322, 4324, 4338, 4349, 4359 and 4387. They also supplied
     U7's count, 4330, which the report says was not reported.
3. "Dry-run omits a repository command" (src/hands/project.py:246):
   **dismissed.**
   - The dry run's line for each clone already says
     `git clone <url>; push URL no_push`, so both effects of the real run are
     named.
   - §38 asks the dry run to print "what it would write", and the brief asks
     for "every path". Both hold.
4. "Phone replies cut off by a daemon stop are never answered"
   (src/hands/daemon.py:664): **confirmed → carried as should-fix 3.**
5. "A failed clone leaves a project that cannot be re-added"
   (src/hands/project.py:289): **confirmed → carried as should-fix 11.** That
   item includes the bot's `--` remark, which the U10 sub-agent reproduced.
6. "Discotrade planning misses its roadmap" (src/hands/project.py:36):
   **dismissed.**
   - `DEFAULT_PARAMETERS` are hands' own conventions, documented as the
     human's to edit. The command prints the filled instruction for the human
     to check, and then the verification question.
   - Under the §38 separation rule, another project's layout is evidence,
     never a default in hands' files.
   - The role reads `meta/ROADMAP.md` itself through the engine's consult
     prompt (playbook.py:226), whatever PLAN says.
7. "Start notice blames a daemon stop for crash orphans"
   (src/hands/daemon.py:294): **confirmed → carried as should-fix 4.**

## Notes

- **Gate (my one run).** `./scripts/check` passed at the tip `baa0b6e` in a
  fresh worktree: `4387 passed in 341.82s (0:05:41)`, `== cli smoke ==`,
  `check: green`, exit 0.
  - `git diff 9fae4ee baa0b6e` touches only meta/ files (CHECKPOINT,
    FINAL-REPORT-22, FINDINGS, journal, plan), so the tip's code is U11's.
  - Every unit commit is green at its own sha: U1 4269, U2 4300, U3 4308,
    U4 4317, U5 4322, U6 4324, U7 4330, U8 4338, U9 4349, U10 4359,
    U11 4387.
- **Schedule (UTC, 2026-10-15; one sub-agent at a time, so only one
  `./scripts/check` runs inside the 20-minute cap).** Each start and end is
  taken from my clock reads and the sub-agent's reported duration, to the
  minute:
  - U1 3feb89b 15:06–15:14
  - U2 5f3b7ad 15:14–15:23
  - U3 96d3fbb 15:23–15:38
  - U4 69364de 15:38–15:47
  - U5 f16c331 15:47–15:55
  - U6 22a2ef5 15:55–16:02
  - U7 cfb7e71 16:02–16:10
  - U8 7df5bce 16:10–16:17
  - U9 b6e2511 16:17–16:25
  - U10 f1936b1 16:26–16:34
  - U11 9fae4ee 16:34–16:43
  - My gate at the tip: 16:43–16:49
- **Protocol version.** I followed the protocol on `main` (7ddc0e8). Its
  revert step is the single `git checkout <sha>~1 -- <files>` that U7
  replaces.
  - That wording fails for the commits that add non-test files (U8
    `templates/DECISIONS-owner.md`; U10 `src/hands/project.py` and
    `templates/config.toml`).
  - So every sub-agent used U7's per-file form instead: `git checkout <sha>~1
    -- <file>` when `git cat-file -e <sha>~1:<file>` holds, else `rm`. Each
    then confirmed a clean `git status` after the restore.
  - I also kept the schedule U7 requires (above).
- **U0 (759f605).**
  - It files H-049 and H-050 and sets H-037 and H-046..H-048 to
    "in progress (mission 22, U<n>)".
  - It touches only meta/plan.md, meta/CHECKPOINT.md, meta/journal.md and
    FINDINGS.
  - The branch exists on origin.
- **U12 (baa0b6e).**
  - It adds FINAL-REPORT-22 with §NOT PROVEN and the `## Review items` table,
    and files H-054.
  - The table's three rows are borne out: should-fix 1 by the §2 sentence,
    should-fix 2 by U7, should-fix 3 by U11. The U11 sub-agent's grep found
    no `python3 <` or `-I`-less guard spelling left; should-fix 12 is a
    different hook.
- **Forbidden files.** No unit commit touches DESIGN.md, meta/plan.md or
  meta/CHECKPOINT.md; only the `plan:` and `report:` commits touch the last
  two. Every unit body lists every file in its `--stat`, and every added file
  is named as added.
- **Files outside the brief's lists, all named in their bodies and judged
  sound:**
  - U1: `config.py`, which holds the token refusal the brief requires.
  - U10: `templates/config.toml`, since no config template existed, and the
    `pyproject.toml` force-includes.
  - U11: `architect/README.md` and `driver/README.md`, carrying the `-I`
    spelling. Only the architect one is pinned by a test.
  - Units that left a listed file unchanged, each with the body saying so:
    U1 `phone.py`, U3 `playbook.py`, U4 `kit.py`, U8 `kit.py`.
- **Report §NOT PROVEN against the sub-agents.** Everything listed is
  confirmed unproven, and nothing the report claims as proven was
  contradicted. Should-fix 1 concerns which code proves a behaviour, not the
  behaviour itself. The sub-agents add:
  - U1: tokens containing `=` or quotes in ntfy's short form.
  - U2: an IPv4-mapped IPv6 private address (`::ffff:10.0.0.1`) is warned on.
  - U3: `daemon_stop` outranks a limit that arrives during the stop
    (`_final_state`), untested.
  - U4: no committed test drives the architect's end after a blocked consult.
    The sub-agent's throwaway probe showed escalate, series complete and a
    `next kit` with no kit filed each stop correctly.
  - U5: "last ended" means the terminal builder job with the newest id.
  - U6: a garbage-collected sha end to end; playbook.py's git calls run
    synchronously on the loop (up to 10 s each), as the file's existing calls
    do.
  - U8: the six-of-six test shows tolerance only.
  - U9: the wheel test needs hatchling in the uv cache (`--offline`).
  - U10: `add(home=…)` is not passed to `load_config` or doctor; the two
    copies of the secret can drift.
  - U11: the `driver/README.md` change and handbook §17's "up front" sentence
    are present but unpinned.
- **Findings filed by the mission (H-051..H-054).** Each claim was checked on
  disk by the sub-agent of its unit, and each is open for the architect:
  - H-051: the guard refuses all three routes.
  - H-052: the reading matches §31 and the by-hand recipe. Recommendation:
    confirm it in the next DESIGN.
  - H-053: `Daemon.status` lists every configured role.
  - H-054: config.py:596-608 refuses only a key set in both tables.
  - U11's body calls the `[server] ntfy_topic` case "design-silent", which it
    is not; H-054 corrects that in U12.
- **Minor.** The report's U8 line names templates/BUILDER-N-PROMPT.md twice.
  The protocol text has a stray line break at "the / sub-agent" (lines
  75-76).
- **Per-commit verdicts.** These are the sub-agents' reports reflowed into
  the point-by-point shape below. No claim, count, line reference or
  classification was changed or dropped.
- **Merge.** With no blockers, this review merges PR #3 with a merge commit.

## Per-commit verdicts

**U1 3feb89b** — PASS on 1–4. No defects.
1. Unit: mission 22 U1, "The buttons carry the token", H-037; the body claims DESIGN §38 with §26 and §33.
2. Test-first: PASS. 4 new tests (8 cases) in tests/test_ntfy_token.py, all pass at the commit. Reverted alone: notify.py → 2 red (the [token] held-job case, the actions_header test); config.py → 3 red (comma, semicolon, both); doctor.py → 2 red (both doctor cases). The no-token cases stay green on revert, correctly ("as before"). Tree clean after each restore.
3. Gate: green. `4269 passed in 336.48s (0:05:36)`, ruff clean, CLI smoke green.
4. Design: PASS. The only actions are phone.actions() (Approve/Deny), leaving by three paths (daemon.py:396 held now, :769 the event path, :252 re-publishing a failed start), all through Notifier._publish → http_post → actions_header(actions, token). who.py and send_test publish no actions; the start fold carries no buttons (§34). The bearer is added on the wire, not to the action dicts, so the spool never holds it (tested against a deny-all transport). The doctor line appears only when the command channel is on. config.py outside the brief's list is right (the refusal at load lives in _ntfy_token) and does not print the value. The body covers every file; DESIGN.md, plan, CHECKPOINT untouched.
Note: the INTEGRATION "The buttons" paragraph (:673) is not updated here (U11's job).
NOT proven: the ntfy app sending the headers on a real press; short-form parsing of tokens with `=` or quotes.

**U2 5f3b7ad** — PASS on 1, 3, 4; 2 partly proven. Two should-fix.
1. Unit: mission 22 U2, H-046; claims DESIGN §38 "handswho publishes on change only", §24, §33. 8 files in --stat, all in the body, none added; DESIGN.md, plan, CHECKPOINT untouched.
2. Test-first: partly proven. With who.py, config.py, doctor.py at the parent, the config, doctor, blank_times, 429-floor and floor-from-config tests go red (26 failures); tree clean after restore. But the scan-level tests (times-only scans publish once, a real change, two changes 10 s apart, a request inside the floor, own session) pass on the parent's code too. Mutating the blanked comparison to `changed = fp != self.fp` leaves all of test_who.py green. Moving the floor stamp back to success-only turns test_a_refused_publish_is_not_retried_inside_the_floor red.
3. Gate: green. `4300 passed in 324.65s (0:05:24)`.
4. Design: the three points asked about hold. A deferred change is not lost: self.fp and self.shown are stored only after a successful publish (who.py:931), so a deferred, refused or blanked-equal scan stores nothing and the first scan past the floor publishes. "Both must differ" suppresses nothing visible: the fingerprint holds no times, and everything in it is printed. Classification correct: 100.64.0.0/10, RFC 1918, 127/8, ::1, 169.254/16, fe80::/10, fc00::/7, localhost, `.ts.net` (not bare ts.net). Undisclosed gap: `::ffff:10.0.0.1` is warned on.
SHOULD-FIX 1 (who.py:923): the blanked-picture half is untested and nearly redundant with the time-free fingerprint.
SHOULD-FIX 2 (who.py:923/931): a stale stored fp lets the human's own session cause a push, against §24. Reproduced with a scripted build_summary and the real Debounce: [True, True, False, True]. Fix: store fp whenever the blanked picture equals the last published one.
NOT proven: a real broker or 429; time formats other than age()'s and the header clock.

**U3 96d3fbb** — PASS on 1–4. Two should-fix.
1. Unit: mission 22 U3, "A daemon stop does not strand the builder" (H-047); claims DESIGN §38 with §2, §6, §28, §31.
2. Test-first: PASS. daemon.py, runner.py, spool.py, FINDINGS at the parent → 7 red (6 in test_daemon_stop plus test_spool::test_job_record_has_exactly_the_design_fields). The idle-stop and pre-§38-orphan tests stay green, as expected. daemon.py alone → the stop, resume and max_resumes tests red; runner.py alone → 4 red including the _final_state test. Tree clean.
3. Gate: green. `4308 passed in 334.29s (0:05:34)`.
4. Design: PASS. spool.transition(...,"orphaned") sets orphan_fed=False on every path, reconcile_orphans included, so crash orphans of every role reach PlaybookEngine.on_job once, after the workers are up. An orphaned driver hits driver_stop (CONSULT_STOP_STATES); an orphaned architect goes _architect_end → _architect_stop, with no playbook.py change; the reconciled-driver end-to-end test (test_playbook.py:2992) now runs through _feed_orphans and passes. A human cancel wins in _final_state (runner.py:1048); `killed` comes only from a cancel or the queued-RunnerError path, never from a stop. orphan_reason and orphan_fed are §6-consistent, the field pin is updated, and pre-§38 records load (null). The body lists every file and names the added test file; no forbidden file touched.
SHOULD-FIX 1 (daemon.py:661): the early return for `orphaned` skips _reply_ended, and _feed_orphans only calls on_job, so a phone reply/answer ended by a stop is never published; a builder `answer` (context keep) is re-sent with a clear context by a resume rule.
SHOULD-FIX 2 (daemon.py:290-294): "which a daemon stop orphaned" is written for crash orphans too.
NOT proven: a driver or architect orphaned by a stop; the 5-second spawn window; daemon_stop outranking a limit during the stop; a real restart.

**U4 69364de** — PASS on 1–4. Should-fix on the load check.
1. Unit: mission 22 U4, "A blocked mission consults the role" (H-048); the body names DESIGN §38 and §31.
2. Test-first: PASS. playbook.py, the missions template, docs/PLAYBOOK.md and FINDINGS at the parent → 10 new or changed tests red; tree clean after restore. Each half reverted alone fails its own tests: load refusal (2 cases), prompt branch, template (kit and docs tests), docs pin. The phone-mode test is green at the parent too, as expected (it pins existing behaviour).
3. Gate: green. `4317 passed in 343.12s (0:05:43)`.
4. Design: PASS. CONSULT_EVENTS[ARCHITECT] == ("aux.done","builder.done"). The prompt swaps only the subject block (playbook.py:3131); roadmap, decisions, conditions, instruction and verdicts are unchanged. One shared architect_consults_used count; the budget test proves it. kit.py is untouched and the kit test passes 6 of 6. The architect's end path is event-agnostic: a throwaway probe showed escalate, series complete and `next kit` with no kit each stop with the §31/§32 reason, and consult.done records event builder.done. No forbidden file (or this repo's PLAYBOOK.toml) touched; 7 files listed.
SHOULD-FIX 1 (playbook.py:1117): `BLOCKED not in verdict.pattern` on the regex text accepts `not-blocked`, `unblocked`, `^(?!.*blocked)`, `(blocked|finished)` and refuses `(?i)…BLOCKED`, `bl[o]cked`, `\x62locked`. Fix: test the compiled regex against sample verdicts.
SHOULD-FIX 2: the load refusal is not asked for by §38 (it says kit check accepts); it is disclosed as design-silent but needs a finding.
Minor: for a blocked consult ARCHITECT_INSTRUCTION still says "write the next kit from ROADMAP and the review", which the design keeps unchanged.
NOT proven: a real architect's answer to a blocked prompt; the daemon end to end (the engine ran against a recorder).

**U5 f16c331** — PASS on 1–4. Two small should-fix.
1. Unit: mission 22 U5, `progress <secret>`, the tenth phone command; claims DESIGN §38 with §26. No forbidden file; 6 files, all listed, none added.
2. Test-first: PASS. phone.py, api.py, INTEGRATION.md, PLAYBOOK.md at the parent → tests/test_phone.py fails to import (PROGRESS_TITLE). Alone: api.py → the 3 answer tests red; `progress` out of _SECRET_ONLY → all 4 progress tests red; both docs → both doc pins red; PLAYBOOK.md alone → the new pin red. The wrong-secret test stays green with api.py reverted (the refusal is before the api). Tree clean.
3. Gate: green. `4322 passed in 342.22s (0:05:42)`, `check: green`.
4. Design: PASS. `progress` goes through the same _SECRET_ONLY path: exactly two words, hmac.compare_digest in _is_secret (phone.py:665), refusals logged without the secret (asserted); a nonce or extra word is refused. Read-only: it reads running_job_id and spool.list_jobs, files no job, writes nothing (asserted). git runs via subprocess.run with a 10 s timeout inside asyncio.to_thread. progress_report is outside Api.COMMANDS and KIT_METHODS, so method() returns None for it. "ten" is consistent in phone.py, INTEGRATION.md and the docs test; no "nine" left.
SHOULD-FIX 1: README.md:131-133 lists approve, deny, pause, resume, status but not progress (nor answer, before this commit); no count is stated.
SHOULD-FIX 2: _checkpoint_line reads <builder cwd>/meta/CHECKPOINT.md, so a cwd below the root says "no checkpoint" while the file exists.
Minor: "last ended" is the terminal builder job with the newest id.
NOT proven: git missing or timing out, the 200-character cut, the hour form of the age.

**U6 22a2ef5** — PASS on 1–4. Two small should-fix.
1. Unit: mission 22 U6, review 20's two notes on U6; DESIGN §38 "Two small corrections…" with §36. Only src/hands/playbook.py and tests/test_playbook.py, both listed; no forbidden file.
2. Test-first: PASS. playbook.py at ~1 → both new tests red (KeyError 'head'; a missing a/b/meta/decisions/001-owner.md block). With the `head` assertion deleted, the 2001-dated commit after the consultation is still missing under the old --since code, so the log half is proven on its own. Tree clean.
3. Gate: green. `4324 passed in 343.59s (0:05:43)`, `check: green`.
4. Design: conforms; the body and FINAL-REPORT-22 match the code. Only the architect's consult.sent counts (matched on payload.job against the newest architect job; a driver's never matches). No earlier consultation → every commit counts, as before; a missing or None `head` too. A rebased but present sha lists the commits after the merge base (correct or too much, never too little). An unknown sha: no crash; the prompt shows "could not be listed: fatal: Invalid revision range …" and no owner files. git calls are timed out (GIT_SHOW_TIMEOUT_S=10) and synchronous, as the file's existing calls are.
SHOULD-FIX 1 (_owner_decisions): an owner file committed since but untracked at HEAD is now silently omitted (probe returned []); before it was listed with "no committed copy".
SHOULD-FIX 2 (human_decisions/_owner_decisions): an unknown or GC'd sha falls back to an error line, not "every commit counts".
NOT proven: a GC'd sha through the engine end to end; the loop blocked up to 10 s per hung git call.

**U7 cfb7e71** — PASS on 1–4. One should-fix.
1. Unit: mission 22 U7; claims DESIGN §38 "The protocol's revert step for a file the commit adds", "The reviewer's schedule is written down", "The owner-decisions round, as a template" (the exception), "Human-supplied content"; H-049, H-050, review 21 should-fix 2.
2. Test-first: PASS. templates/REVIEW-PROTOCOL.md, meta/REVIEW-PROTOCOL.md, FINDINGS (all exist at the parent) at cfb7e71~1 → test_the_protocol_reverts_by_checkout_and_never_says_stash red on all 8 cases (2 files × 4 sentences). Tree clean after restore.
3. Gate: green. `4330 passed in 339.98s (0:05:39)`, `check: green` (the count the builder's sub-agent did not report).
4. Design: PASS. All four §38 sentences in both files. The diff of the two files is only lines 41-43 (`<owner>/<repo>` / `SigorMatt/hands`). `grep -i stash` finds nothing. No forbidden file; 4 files listed, none added. The FINAL-REPORT-22 U7 claims match the disk.
Literal follow-through: rm of an added file then `git checkout <sha> -- <files>` restores it, tree clean (rc=0).
SHOULD-FIX (templates/REVIEW-PROTOCOL.md:67-70, same in meta/): for a file the commit deletes, the restore `git checkout <sha> -- <files>` fails with "pathspec did not match" and restores none; the edited file stayed at the parent content and the deleted file staged as A. No clean-status check is required. Fix: `git rm` a file absent at <sha>, then a clean-status check.
Minor: step 4 does not tell the sub-agent to check the "added" naming; Per-commit verdicts for the two no-sub-agent commit kinds are unspecified; a stray break "the / sub-agent" at :75-76; the pin checks stash/Stash/STASH only.
NOT proven: a reviewer following the steps; the owner and human-supplied rules on a real commit of either kind.

**U8 7df5bce** — PASS on 1–4. Two should-fix.
1. Unit: U8, DESIGN §38 "The owner-decisions round, as a template", "Human-supplied content", the Purpose sentence of "Onboarding". All 5 files listed; templates/DECISIONS-owner.md named ADDED; kit.py unchanged, as the body says. No forbidden file.
2. Test-first: PASS. The 3 changed files at ~1 and DECISIONS-owner.md removed → all 8 new tests red, both parametrized cases of each instruction test included. Tree clean after restore. Limit: the six-of-six test goes red only because the template is missing; it is a tolerance test.
3. Gate: green. `4338 passed in 352.42s (0:05:52)`.
4. Design: PASS. The owner template has O-n continued from the last owner file, the precedence header before the first O-n, "Findings closed:", "For the builder" last and called the only section the builder reads. Its review claim is backed by templates/REVIEW-PROTOCOL.md:55 (U7) and :57. The human-supplied shape has every §38 phrase. §R matches §38's keep rule clause by clause and is word-for-word meta/BUILDER-22-PROMPT.md:98-102. The Purpose block is the first content after `# Architect` in architect/CLAUDE.md and the first of the pasted block in docs/ARCHITECT-INSTRUCTION.md.
SHOULD-FIX 1 (architect/CLAUDE.md:72-81, rule 13): in the role variant the answer is only a draft, "never file one in a kit"; a design-level choice that belongs in a finding.
SHOULD-FIX 2 (architect/CLAUDE.md:55-61 vs :79): rule 13 says "escalate under rule 8", but rule 8's conditions do not cover a ruling (a builder question, a blocked mission).
Minor: the report's U8 line names BUILDER-N-PROMPT.md twice.
NOT proven: an architect or builder acting on the words; kit check rejecting anything new; rule 13's escalate-with-draft path with a `keep` send.

**U9 b6e2511** — PASS on 1–4. Three should-fix; H-051 open and correctly filed.
1. Unit: mission 22 U9, DESIGN §38 "Onboarding" (handbook and templates), HF-002, HF-004, HF-005. All 10 files listed, tests/test_handbook.py named added; no forbidden file.
2. Test-first: PASS. Alone: runner.py → the 4 HANDS_DOCS job tests red; cli.py → the 2 `hands handbook` tests and the wheel test red ("invalid choice: 'handbook'"); pyproject.toml → the wheel test; the handbook → the §12 test; each instruction → its own test; config.py → collection error. The §6 test stays green against the old handbook, as the body says (a pin; SERIES_KEYS has 7 keys, in order). Tree clean.
3. Gate: green. `4349 passed in 340.70s (0:05:40)`. The wheel test takes 0.9 s; `--offline` really blocks the network (fails with an empty UV_CACHE_DIR, succeeds from the synced cache).
4. Design: docs_root() is the repo root from a checkout or editable install and hands/shipped/ from a wheel; the test runs `hands handbook` both ways. HANDS_DOCS contains docs/ and templates/, matching the instructions' $HANDS_DOCS/docs/… and $HANDS_DOCS/templates/. H-051 is real: the guard (HANDS_ROLE=architect) refuses `echo $HANDS_DOCS`, `hands handbook`, `cat <handbook>`, `printenv`, `env`; architect/CLAUDE.md:33 tells the role what it cannot do today, as §38 mandates, filed open and disclosed.
SHOULD-FIX 1: HF-002 is "resolved" in FINDINGS while H-051 says the role half does not work; mark it partly resolved, pointing at H-051.
SHOULD-FIX 2: rule 2 used to point at the clone's handbook, which the role could read; until H-051 is settled the role has no readable handbook.
SHOULD-FIX 3 (cli.py:361): the help says the directory is $HANDS_DOCS; the handbook's is $HANDS_DOCS/docs.
NOT proven: a pip or uv tool install from the wheel; a real architect reading through $HANDS_DOCS; a build without hatchling in the uv cache.

**U10 f1936b1** — PASS on 1–4. Three should-fix.
1. Unit: mission 22 U10, `hands project add <name> --repo <url> [--dry-run]`; claims DESIGN §38 "Onboarding", §31, INTEGRATION setup steps 2, 3, 5, 6. All 8 files listed, the three new ones "(added)"; no forbidden file.
2. Test-first: PASS. All non-test files reverted (added ones removed) → tests/test_project_add.py fails to collect (ModuleNotFoundError hands.project) and 2 test_docs tests red. templates/config.toml and pyproject.toml alone → 3 red (the create test, the empty-role-directory test, the wheel test); pyproject.toml alone → the wheel test red. Tree clean.
3. Gate: green. `4359 passed in 353.93s (0:05:53)`, `check: green`.
4. Design: PASS. Secret and config are created with os.open(O_CREAT|O_EXCL, 0o600) (project.py:157), 600/600 on disk, no 0644 window. check_project_name `[A-Za-z0-9][A-Za-z0-9._-]{0,63}` refuses ../x, /, empty, a leading -. `ext::` is blocked by git's default protocol.allow. The guard is copied 664, fine: both settings run `python3 -I "$CLAUDE_PROJECT_DIR"/.claude/hooks/bash_guard.py`. H-052 is handled correctly (filed open, disclosed; matches §31 and the by-hand recipe); recommend the architect confirm it in the next DESIGN. The duplicated cmd_secret does not contradict §38 (both copies 600, disclosed).
SHOULD-FIX 1 (project.py:285): no `--` before the URL; `--repo '--upload-pack=touch X;false'` was taken as an option (nothing ran only because the path did not exist yet).
SHOULD-FIX 2: with both clones failing, the config, secret, unit, both role directories, kits/ and handsd@demo enabled are left behind; a re-run is refused "exists … nothing written", with no recovery advice; untested.
SHOULD-FIX 3 (minor): the two secret copies can drift on rotation; no finding.
NOT proven: real systemd, a remote URL, a started daemon; `add(home=…)` is not passed to load_config/doctor (harmless from the CLI).

**U11 9fae4ee** — PASS on 1–4. Two should-fix.
1. Unit: mission 22 U11 "Docs"; claims DESIGN §38 ("The handbook's new sections", "Human-supplied content", "progress", "The buttons carry the token") and review 21 should-fix 3.
2. Test-first: PASS. The 7 non-test files (all exist at the parent) reverted → all 23 new tests red except test_the_handbooks_reading_claims_are_the_codes (which tests code). Tree clean. architect/README.md alone → the switch-point test red; driver/README.md alone → nothing red (its -I change is unpinned).
3. Gate: green. `4387 passed in 343.06s (0:05:43)`.
4. Design: PASS. 9 files listed, none added; no forbidden file. H-053 is true (Daemon.status loops over config.roles, daemon.py:180, 918; _status_block cli.py:555 and status_summary phone.py:699 print every role) and handbook §18 claims nothing about hiding it. H-054 is true (config.py:596-608 refuses only a key in both tables; INTEGRATION:1040-1048 says so with the real error text). Every §38 item is present: image (INTEGRATION:960, 979, 1022), no cert domain (1012-1024), base-url first (960-965), [server] migration (1040-1048), who grants (988-1000), WebSockets (1026-1027), -I (307, 1111, 1197, 1259), role-mode default (918-925, 1188), what is proven (1084-1100, 1649-1662), buttons (946-953, 742); handbook onboarding (504), ruling round (523), separation (559), re-firing (568), human-supplied incl. up front (587-594), send/status/jobs/auto-runs/progress (601-620); PLAYBOOK blocked consult (328, 453-471), auto-runs and progress (603-607, 99). Separation holds: discotrade appears only at HANDBOOK:566, :592 as name, unit, ruling id, date. Both READMEs outside the list are right.
SHOULD-FIX 1: the body calls the [server] ntfy_topic case design-silent; §38 says it refuses to load; no finding until H-054 in U12.
SHOULD-FIX 2: .claude/settings.json:9 runs `python3 "$CLAUDE_PROJECT_DIR"/.claude/hooks/no_background.py` without -I; INTEGRATION:1543-1546 copies it to every role's cwd; needs a finding.
NOT proven: the ntfy, Tailscale, WebSockets steps against a real install; jobs newest-first pinned only via the docstring; §17's "up front" sentence unpinned.
