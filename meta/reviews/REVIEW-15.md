# REVIEW-15 — cold review of hands mission 15

VERDICT: review mission 15 blockers=4 should-fix=7

Base `02d1360` (`review: mission 14`, the last `review:` commit on origin/main).
Tip `17b12fe`. Unit commits reviewed, one sub-agent each, in a `git worktree` at
the commit: 1a48e11 (U0, the orchestrator's `plan:` commit), d32f409 (U1),
6b27320 (U2), adf3d7a (U3), c9ccc18 (U4), 9ed931b (U5), f798521 (U6), fd1a2dd
(U7). Not dispatched: 1f8141c (the architect's mission-15 kit) and 17b12fe (U8,
the `meta:` commit that adds meta/FINAL-REPORT-15.md and the held bookkeeping).
The reviewer re-ran blockers 1, 2 and 4 at the tip, and read blocker 3's code
path at the tip.

## Blockers

1. **The guard still runs an arbitrary program, now in role mode too: a `for`
   segment is not judged, and `${…}` in the arguments of a table row is not
   checked (U1 `d32f409`; §30, §31 "No listed option takes a value that names a
   program or a file to write", §27 role mode).**
   - **Reproduced at the tip**, shipped file, hook JSON on stdin:
     ```
     for a in '$x'; do echo; done; for c in ${a%x}'(touch${IFS}/tmp/rev15-tip/PWN)'; do echo ${c@P}; done
       normal exit=0 · HANDS_ROLE=driver exit=0 · HANDS_ROLE=architect exit=0
       run under bash: /tmp/rev15-tip/PWN created
     ```
     The U1 sub-agent found the same shape with `cat ${c@P}` and `ls ${c@P}`,
     and ran `id` with it. `${c@P}` expands to a `$(…)` that bash then runs. The
     `for` segment gets through unjudged. §28's check on `$`/`{` in arguments
     applies only to the `git` and `hands` rows, so the same shape with `git` is
     refused.
   - **Regression in role mode.** The guard at the parent `1a48e11` refuses this
     command in driver role mode (exit 2, "command not allowed for the driver
     role (§27): 'echo'") and allows it in normal mode. U1's widening ("Role mode
     is the same table") let the hole into the driver role. §30 says the driver
     role is enabled only after a review finds no hole in the guard's language.
   - **The option tables are bypassed the same way.** `for o in -f; do tail $o
     /etc/hostname; done` exits 0 in normal and driver mode at the tip. The row
     checks the literal `$o`. The sub-agent also got `wc --files0-from=`, `grep
     -f`, and `date +%s --set=…` through (date tried to set the clock; the kernel
     refused).
   - **What the disk contradicts.** The guard's docstring says "a segment the
     guard allows has no way to write". The commit body says "No listed option
     takes a value that names a program or a file to write". FINAL-REPORT-15
     §3.1 says "what is proven is that the listed commands take only the listed
     options". No finding covers it.

2. **Architect mode lets `unzip` write outside `HANDS_KITS`, over the guard
   itself (U3 `adf3d7a`; §31 "only with every path argument under
   `HANDS_KITS`").**
   - **Reproduced at the tip.** In an architect directory with `kits/` under it,
     `HANDS_ROLE=architect HANDS_KITS=<cwd>/kits`:
     ```
     unzip -o kits/attack.zip      -> exit 0
     unzip -o ./kits/attack.zip    -> exit 0
     unzip kits/attack.zip         -> exit 0
     run: <cwd>/.claude/settings.json      now {"overwritten":true}
          <cwd>/.claude/hooks/bash_guard.py now "# neutered"
     ```
   - **Why it works.** The `unzip` row confines only the path *arguments* (the
     zip, and a `-d` value if one is given). It never requires `-d`, so the
     default destination is the cwd, `~/hands-architect/<project>/`, which is
     the *parent* of `HANDS_KITS`.
   - **Why it matters.** `architect/settings.json` runs the hook as `python3
     "$CLAUDE_PROJECT_DIR"/.claude/hooks/bash_guard.py`. One allowed command can
     replace the guard and the settings that name it, and every later call runs
     unguarded.
   - **What the disk contradicts.** The guard's own text says "the architect
     writes only under $HANDS_KITS". §31 does not list `unzip` among the
     confined words at all (`mkdir`, `cp`, `zip`, `mv`); the brief's U3 added
     it. FINAL-REPORT-15 §3.1 does not mention it.

3. **The engine approves any held job of origin `architect`, not a held apply,
   and any socket client can set that origin (U4 `c9ccc18`; §31 "held apply jobs
   of origin `architect` are approved by the engine", §8).**
   - **The code.** `Api.decide_from_playbook` (`src/hands/api.py:607-632`)
     checks only `origin == "architect"` and `state == "held"`, and the engine
     checks the same two things (`src/hands/playbook.py:1462-1473`). Nothing
     checks that the gate is `apply <name>`. Its own docstring calls it "a held
     apply the architect role filed".
   - **Who can set the origin.** `Api.send` is in `COMMANDS` and takes `origin`
     from the wire (`api.py:146`, `:187`). Its only check is `spool.ORIGINS`
     membership, and `architect` is in that set.
   - **Repro (U4 sub-agent, end to end, real daemon + fake_claude, under the
     unit's autonomous playbook).** A raw socket client sent `{"method":"send",
     "params":{"role":"builder","context":"clear","origin":"architect",
     "prompt":"gh pr create … decisions-2026.md"}}`. There was no kit check and
     no `hands kit file`. The job was held on §8's default pattern, then released
     `{"decided_by":"playbook","decision":"approved"}` with no human, and ran to
     `done`.
   - **Reach and scope.** §8 says gating on the default patterns cannot be
     disabled. Any same-user process can reach this, including a builder session
     running with bypassed permissions. The driver cannot, because CLI `send` has
     no `--origin`. The hole is latent today: no shipped playbook sets
     `autonomous`.
   - **What the disk contradicts.** FINAL-REPORT-15 §3.3 says "It is narrow —
     one origin, one playbook state". The origin is a label the client supplies,
     and no test refuses a non-apply `architect` hold.

4. **`[series] architect = "role"` without `[roles.architect]` is not a config
   error anywhere before the engine's first load, and two shipped docs say doctor
   reports it (U4 `c9ccc18`, U6 `f798521`; §31 "a `[series] architect = "role"`
   without `[roles.architect]` is a config error").**
   - **The code.** `check_series_roles` is called only from
     `PlaybookEngine._load` (`src/hands/playbook.py:1225`). `hands doctor`'s
     playbook check never calls it (`grep check_series_roles src/` shows only
     playbook.py).
   - **Repro (U4 and U6 sub-agents).** A committed playbook with `architect =
     "role"` and `autonomous = true`, and a config with no `[roles.architect]`,
     gives `hands doctor` "playbook ok … doctor: green", exit 0. At daemon start
     `hands pipeline` reports loaded=true, error=None. The pipeline stops only on
     the first event.
   - **What the disk contradicts.** `docs/INTEGRATION.md:786` says "a config
     error, named in the stop and in `hands doctor`". `docs/PLAYBOOK.md:105` says
     "named when the engine loads the file and by `hands doctor`".
     `tests/test_docs.py:1471-1475` pins only that section's "no
     `[roles.architect]`" fragment, so the doctor clause went through the U6
     docs sweep unchecked. The U6 sub-agent's report below reads the pin as
     covering the whole sentence; the reviewer checked it at the tip, and it
     covers only the fragment.

## Should-fix

1. **The engine's kickoff rule fires on any builder's `VERDICT: kit applied`
   (U4; §31 "`[series] kickoff` is sent after `VERDICT: kit applied`").**
   `_engine_rules` (`src/hands/playbook.py:1401`) matches any `builder.done`
   whose verdict matches `^VERDICT: kit applied`, from any origin.
   - Probe: a plain `hands send` job (origin `cli`) replying `VERDICT: kit
     applied deadbee` fired `rule: -1` and started a kickoff of origin
     `playbook`.
   - The prompt is always the fixed `[series] kickoff`, so the harm is low, but
     the rule is not tied to the apply the engine released.

2. **`next kit` accepts any later job of origin `architect` as "the apply the
   architect filed" (U5; §31 "`next kit` waits for the apply the architect
   filed").** `_filed_apply` (`src/hands/playbook.py:1876-1888`) checks neither
   role, hold, gate nor kit name, and the `<name>` in `VERDICT: next kit <name>`
   is captured but never compared.
   - A done `aux` job of origin `architect` satisfies `next kit foo`.
   - A denied apply named `bar` also satisfies it.
   - The series does not stall silently, because §10's default stop catches the
     denial.

3. **The architect's budget resets when the series is renamed, and under
   autonomy the architect can do the renaming (U5; §31 `max_architect_consults`
   "per series").** The anchor is keyed only on `[series] name` (around
   `playbook.py:1272`).
   - Probe m17 → m18 → m17 gives used=0.
   - A kit the architect files can rename the series, and the engine approves
     that kit itself (blocker 3's authority). So the one escalation condition the
     engine enforces (`budget-exhausted`) can be reset by the party it bounds.
   - Neither the commit body nor FINAL-REPORT-15 §3 discloses this.

4. **The whole ROADMAP goes into the prompt, where §31 says "the roadmap's next
   milestone" (U5).** This is disclosed in the body and the docstring
   (`playbook.py:1703-1709`), but no finding was filed, and a builder does not
   get to decide a design deviation.
   - The body's "read like the playbook" is also inaccurate. The roadmap is read
     from the working tree, and the playbook loads only the committed file (§10).

5. **Daemon start can still publish two notifications within one second, and the
   doc names the wrong set of published kinds (U2; §31 notifications, REVIEW-14
   should-fix 1 and 2).**
   - With an orphaned consult driver job present, a start published `hands: the
     pipeline stopped` and then `hands: handsd started` 7 ms apart.
   - `docs/INTEGRATION.md` says "`job.held` is the only inbox event kind hands
     publishes by itself". But `stop` is an inbox event (`spool.py:128`) that is
     always published, as the same paragraph says itself.

6. **Doctor's architect row misses things it is there to catch (U6; §31 "`hands
   doctor` reports the architect role as it reports the driver role").** The row
   stays `ok` in four cases:
   - A write hook that points at a *different* guard file. `doctor.py:590`
     discards `_write_named`, so only the Bash hook's file is self-tested.
   - `permissions.defaultMode: "bypassPermissions"`, or `"allow": ["Write"]` /
     `"Bash"` in the settings.
   - A `type: prompt` write hook.
   - A clone whose push URL is live. §31 says "the clone's push URL is disabled
     as the driver's is", and neither the architect row nor the driver row
     checks it; the driver row's gap is not new.

7. **Role-mode reads now reach any path, and nothing discloses it (U1, U3; §31
   "Role mode is the same table").** `cat ~/.ssh/id_rsa`, `cat
   /proc/self/environ`, `cat /etc/shadow` (permission aside) and `grep -r x /`
   exit 0 in driver and architect mode, while `git -C` stays pinned to the
   clone.
   - This is §31 read literally, so it is not a design violation.
   - But FINAL-REPORT-15 §3.1 describes the widening as "read in the driver
     role" and does not say that a role can now read every secret the user can.
   - It wants a finding so the architect decides it rather than inherits it.

## Notes

- **Gates.** `./scripts/check` was green once at each of the eight unit commits,
  and every pass count matches FINAL-REPORT-15 §1 exactly: 2605 (U0), 2721 (U1),
  2751 (U2), 3013 (U3), 3063 (U4), 3092 (U5), 3126 (U6), 3126 (U7). The guard
  self-test gave 235/235 at U1 and 315/315 at U3. This review did not reproduce
  §4's "3/3"; 17b12fe changes only meta/ over fd1a2dd, which was green.
- **Test-first.** Every unit's tests go red when its product change is reverted:
  - U0: 3 failed, including `test_go_warns_when_the_kickoff_names_a_brief_the_repository_lacks`. The claim that base 1f8141c was red on `test_the_origin_listings_name_kit` is confirmed.
  - U1: 79 failed.
  - U2: 14 failed, one per item.
  - U3: 16 failed plus a collection error in test_bash_guard.py.
  - U4: a collection error in test_playbook.py, and 7 failed in test_gates.py and test_docs.py.
  - U5: a collection error, then 31 failed with the parent playbook.py and a stub.
  - U6: 35 failed.
  - U7: the kickoff value and then `KeyError: 'architect'`, in a parent worktree carrying only the new test. The wrong red, `PlaybookNotCommitted`, was reproduced too.

  One caveat: U2's should-fix 6 rows and its `hands who` named-broken test cannot
  go red by revert. The body says so; they are coverage, not fixes.
- **Forbidden files.** No unit commit touches `DESIGN.md`. Only U0, the
  orchestrator's `plan:` commit, touches `meta/plan.md` and `meta/CHECKPOINT.md`,
  which the brief allows. `meta/findings/FINDINGS.md` only gains lines in U0
  (H-028, H-029), U3 (H-030), U4 (H-031) and U6 (H-032). U0's use of H-028/H-029
  where the brief says H-027/H-028 is right: H-027 was already filed at
  FINDINGS.md:1367.
- **Commit bodies.** Seven of eight list exactly the files in `git show --stat`.
  U3 omits its four test paths by name, as FINAL-REPORT-15 §4 discloses. Wording
  flaws that are not items above:
  - U0 says "five kickoffs" and lists six tokens.
  - U7's "the `go` row now warns" is true only when `cmd_topic`/`cmd_secret` are
    set; otherwise the row is `ok go off`.
  - U5's code comment "first line of the reply" does not match the code: the
    verdict is the first line anywhere in the reply that matches `^VERDICT:`.
  - U6 says "every doc that describes the role says what is not proven", but
    `docs/PLAYBOOK.md` never mentions H-030.
  - U6 says the switch point is "carried verbatim"; only the setup block is, and
    INTEGRATION paraphrases the deliverables and the hand-back step.
- **Confirmed sound.**
  - **U1.** The REVIEW-14 probes exit 2 in both modes with no file written and
    no program run. `COMMAND_TABLE` matches §31 row by row. Combined options and
    long options not in a row are refused.
  - **U2.** The kit trio is spaced on both `default_why` branches, and the test
    really binds the no-KIT.md branch. The empty project name is refused on all
    ten entry shapes with `~/.hands` unchanged. Doctor fails a second Bash hook on
    ten matcher spellings.
  - **U3.** The authority refusals hold (send/approve/deny/go/put/resume/pause,
    `git push`, `remote set-url`, `kit file --project`). Zip-slip entries (`../`,
    absolute, symlink) into `-d kits/…` are neutralised. Realpath containment
    refuses a symlink out of `kits/` for cp/mv/mkdir/unzip `-d` and `--write`.
    H-030 is confirmed: `zip -r kits/m.zip kits/m16/DESIGN.md` gives entry
    `kits/m16/DESIGN.md`.
  - **U4.** No approval happens while paused, for another origin, under
    `phone`, or with `autonomous = false`. A hold filed before the switch stays
    held. The H-031 test still fails on a fifth value.
  - **U5.** Review text cannot steer the engine directly, because only the
    architect job's verdict is matched. The escalate text carries the reason, the
    session id and `claude --resume <id>`, and reaches the phone through `stop()`.
    The budget is checked before enqueue and survives a restart. The driver
    prompt is byte-identical to the parent's over 72 combinations.
  - **U6.** Both templates load with their blocks uncommented. `kit file` is in
    `hands --help`.
  - **U7.** The playbook diff is exactly the kickoff line plus `architect =
    "phone"`, and `kit check` of the BUILDER-15 brief gives 6 of 6, exit 0.
- **Smaller observations, not items.**
  - **U0.** Doctor's missing-brief check skips `..` paths, mangles `<N>`
    placeholders ("names -PROMPT.md"), and tests the builder's cwd on disk rather
    than the committed tree.
  - **U2.** The 1.1 s is counted from the hand-off of the spawned held POST, not
    from delivery. Doctor passes a second Bash hook whose matcher is `"bash"`,
    `" Bash"`, a JSON list, or a non-command hook type. Whether Claude Code would
    select Bash with those is not proven.
  - **U4.** The `escalate_on` default is empty, while §31 lists three
    conditions; the body states that choice.
  - **U5.** `limits.py:358,413` never resume any limited architect-role job,
    consultation or not.
  - **U7.** The committed kickoff names `meta/BUILDER-16-PROMPT.md`, which does
    not exist yet. That follows §27's convention and precedent; doctor now warns.
- **FINAL-REPORT-15 §3 NOT PROVEN against what the sub-agents found:**
  - **§3.0** is accurate.
  - **§3.1** is accurate on the corpus limit and the hook-string assumption. It
    does not disclose the `for`/`${…@P}` execution or the `$o` option bypass
    (blocker 1), architect `unzip` with no `-d` (blocker 2), or unbounded
    role-mode reads (should-fix 7). Its "the listed commands take only the listed
    options" is contradicted by `for o in -f; do tail $o F; done`.
  - **§3.2 (H-030)** is confirmed.
  - **§3.3** calls the authority "narrow — one origin". The origin is
    client-supplied and the job need not be an apply (blocker 3). The
    budget-reset path (should-fix 3) widens it further.
  - **§3.4** is accurate. Only `budget-exhausted` is the engine's, and it can be
    reset (should-fix 3).
  - **§3.5 (H-032)** is accurate.
  - **§3.6** is accurate on the lost buttons and the anchor. It does not disclose
    the orphaned-consult double publish at start (should-fix 5).
  - **§3.7** is accurate as worded: the test pins only a fragment of the doctor
    sentence. But the "~20 doc claims pinned" did not stop two shipped docs from
    saying doctor names a config error it does not check (blocker 4).
- **Review 14 items.**
  - Blocker 1's three probes are closed, but the class is not (blocker 1 here).
  - Blocker 2 is closed.
  - Should-fix 1 is closed for held jobs but not for every start (should-fix 5
    here).
  - Should-fix 2 is closed, with one inaccurate sentence (should-fix 5 here).
  - Should-fix 3, 4, 5 and 6 are closed as §31 words them.
  - Should-fix 7 is closed; doctor warns only with the command channel on.

## Per-commit verdicts

### 1a48e11 (U0)

```
REPORT
sha 1a48e11 (parent 1f8141c), mission 15 U0 "Plan and bookkeeping" (plan: mission 15 — the guard's command table, review 14, the architect role). It claims DESIGN v3.14 §31 with §6, §26 and §10, plus REVIEW-14 should-fix 7.
1 Body PASS: the body names all 8 files in `--stat` (docs/INTEGRATION.md, meta/CHECKPOINT.md, meta/findings/FINDINGS.md, meta/plan.md, src/hands/doctor.py, src/hands/spool.py, tests/test_docs.py, tests/test_doctor.py), with none missing and none extra. One wording slip: it says "five kickoffs" and then lists six tokens. QUIET_KICKOFFS does hold 5 kickoffs.
2 Test-first PASS: with doctor.py, spool.py and INTEGRATION.md reverted to 1f8141c, the result is "3 failed, 165 passed in 13.03s". Failing: `tests/test_doctor.py::test_go_warns_when_the_kickoff_names_a_brief_the_repository_lacks` ("assert 'ok' == 'warn'"), `tests/test_doctor.py::test_a_warned_go_row_keeps_doctor_green_and_exit_0` ("assert 'warn' in '  ok    go ...'"), `tests/test_docs.py::test_the_origin_listings_name_kit` (the ORIGINS frozenset lacks 'architect'). After restoring, the tree was clean. The body's claim that the base was red holds: 1f8141c alone gives "1 failed, 159 passed in 12.97s" on `test_the_origin_listings_name_kit` (the old string is no longer in DESIGN, which says `...|kit|architect)` at line 227).
3 ./scripts/check GREEN: "2605 passed in 337.56s (0:05:37)" / "check: green". This matches the body's 2605.
4 Conformance PASS (§31 "Should-fix 3–7" last clause, REVIEW-14 sf7): all of these warn with exit 0 and the name in the detail: "Read meta/BUILDER-16-PROMPT.md and execute the mission below its divider.", "Read ./meta/X.md" (printed as `./meta/X.md`), "Read meta/X.md.", "read \`meta/X.md\`", "docs/missing.md". The same check outside the doctor run also warns on "Read meta/BUILDER-99-PROMPT.md and execute", `"…"`, `(…)`, `meta/X.md:12`, `meta/brief.txt#section`, "WORKPLAN.md", lowercase "workplan.md" and "docs/missing". These stay ok: the brief present, a directory named `meta/X.md`, `../X.md`, `meta/../meta/X.md`, `/abs`, `~/`, `{n}` placeholders, "Read BRIEF", "Read src".
4 Conformance, minor gaps (none blocking): (a) `..` paths are skipped silently, so a kickoff pointing outside the repo is never warned. (b) The body says placeholders are excluded, but only `{}` ones are. "Read meta/BUILDER-<N>-PROMPT.md" warns with a mangled name, "the kickoff names -PROMPT.md". (c) Doctor looks for the file on disk in the builder's cwd, not in the repository, so an untracked brief counts as present. (d) `meta\X.md` is read as `X.md`. No false negative turned up on realistic kickoff shapes.
4 Conformance PASS (DESIGN/findings): DESIGN.md is untouched (empty diff). FINDINGS.md only adds lines: `grep '^-[^-]'` finds nothing. Using H-028/H-029 instead of the brief's H-027/H-028 is justified: at 1f8141c, FINDINGS.md:1367 already has "## H-027 — two DESIGN lines name things missions 13 and 14 retired", and the ledger never reuses numbers.
NOT PROVEN: The body's "green three consecutive runs" (I ran the gate once). The branch where several files are missing, which only the code covers. That `architect` in ORIGINS has no effect today. The CLI probes ran through the test harness helpers with a temporary HOME, not a hand-built config. Worktree /tmp/rev15-1a48e11 and the temporary one for the parent are both removed. Other rev15-* worktrees are still listed but are not mine.
```

### d32f409 (U1)

```
REPORT
sha d32f409 (parent 1a48e11), mission 15 U1 "The guard's command table" (guard: a command table replaces the allowed-word set)
1 Body PASS: it names U1, DESIGN v3.14 §31 first paragraph (with §12, §27, §28, §30), REVIEW-14 blocker 1 and H-028. Its file list is exactly the 4 files in `git show --stat` (driver/hooks/bash_guard.py, tests/test_bash_guard.py, driver/CLAUDE.md, docs/INTEGRATION.md). DESIGN.md, meta/plan.md and meta/CHECKPOINT.md are untouched (empty diff).
2 Test-first PASS: with the 3 product files at the parent, "79 failed, 839 passed in 19.19s". Failing tests include "test_review_14_probe_is_refused_by_the_shipped_file_in_both_modes[sort -o /tmp/rev14-probe/Z1 /etc/hostname]", "test_a_removed_word_is_refused_by_name_in_both_modes[uniq]", "test_every_fuzz_command_is_refused_by_name_in_both_modes", "test_role_mode_case[cat ./repo/DESIGN.md-True]" and "test_no_listed_option_of_the_command_table_takes_a_program_or_a_file". After restoring: tree clean, "954 passed in 18.31s".
3 ./scripts/check GREEN: "2721 passed in 312.08s (0:05:12)" / "check: green". Selftest: "selftest: 235/235 ok".
4 Conformance: COMMAND_TABLE matches §31 row by row. `tail -f` is refused everywhere; §31's "-f only for hands log" is `hands log -f`, which the hands row handles. Two things read wider than §31 and the body discloses both: `-n5`/`-1`, and jq's filter being anything that starts with `.` (`jq '.|$ENV'` and `'.|input_filename'` exit 0 in both modes). Combined options not in a row are refused (`ls -al`, `grep -rn` exit 2), which is narrower than the design.
4 REVIEW-14 probes: all 3 give exit 2 in both modes through the shipped file on stdin ("command not in the guard's table: 'sort'"/'uniq'). No Z1 or W5 file was created and prog did not run.
4 Refused as expected (exit 2 in both modes): `grep -rf`, `ls -laR`, `grep --include=`/`--file=`, `ls --color`, `date -s`/`--set=`/`-f`, `jq -f`/`--from-file`/`--rawfile`/`-n`, `head -c`, `head -n -5`, `tail -n +5`, `wc --files0-from=`, `pgrep -F`/`--pidfile`, `kill -0 -1`, `kill -0 1 -9`, `sleep 1e9`/`inf`, `echo -e`/`-n`, `grep -e x -- -f`. Allowed and harmless: `grep -e -f x`, `grep -ef x f`, `kill -0 0`, `cat -`, `sleep 99999999` (a hang).
4 HOLE, arbitrary execution (BLOCKER): `for a in '$x'; do echo; done; for c in ${a%x}'(touch${IFS}/tmp/rev15-probe-u1/PWN_ECHO)'; do echo ${c@P}; done`
  - The hook exits 0 in both modes (role mode: HANDS_ROLE=driver, HANDS_CLONE and HANDS_CONSULT_ROLE set). Under bash 5.2 it created PWN_ECHO.
  - The same shape with `cat ${c@P}` and `ls ${c@P}` also exits 0 in both modes and created PWN_CAT and PWN_LS. With `(id)` in place of the touch, `id` ran.
  - Cause: the `for` segment is skipped unjudged, and the §28 check on `$`/`{` in arguments applies only to `hands`/`git`, so `${c@P}` expands to a `$(...)` that bash runs. The same shape with `git ... ${c@P}` is refused.
  - The parent guard allows the same command in normal mode (exit 0), so that side is old. It refused it in role mode (exit 2, "'echo'"), so U1's widening brings the hole into role mode.
4 Option-table bypass: `for o in -f; do tail $o F; done`, `for o in --files0-from=F; do wc $o; done` and `for o in -f; do grep $o F x; done` exit 0 in both modes, because the row checks the literal `$o`. `for s in '%s --set=2020-01-01'; do date +$s; done` also exits 0 in both modes; under bash, date tried to set the clock and the kernel refused ("cannot set date: Operation not permitted").
4 Role-mode reads, as observed: there is no path limit on reads. `cat /etc/shadow`, `cat ~/.ssh/id_rsa`, `cat /proc/self/environ` and `grep -r x /` all exit 0 in role mode, while `git -C` stays pinned to the clone. That is §31's "same table" taken literally. The docstring's "a segment the guard allows has no way to write" and the refusal text's "no listed option takes a value that names a program or a file to write" are false in practice, given the `${c@P}` execution.
NOT PROVEN: whether Claude Code runs the command string in bash exactly as tested here; that jq 1.7 has no write or exec builtin (none found); a full fuzz of `${…}` forms (`@P`, indirection, arithmetic subscripts) across all rows. I created and then deleted /tmp/rev14-probe for the probes. The evidence files are in /tmp/rev15-probe-u1/. The worktree is removed.
```

### 6b27320 (U2)

```
REPORT
sha 6b27320 (parent d32f409), mission 15 U2 "Notifications and doctor" (DESIGN §31 "Notifications (blocker 2, should-fix 1, 2)" and "Should-fix 3–7", plus §11/§25/§26/§27/§30; closes REVIEW-14 blocker 2 and should-fix 1–6)
1 Body PASS: the "Files:" list is exactly the 14 files in `--stat` (596+/95-). DESIGN.md, meta/plan.md and meta/CHECKPOINT.md are untouched (empty diff).
2 Test-first PASS: with the 6 src/hands/*.py files and docs/INTEGRATION.md reverted, "14 failed, 894 passed in 157.78s". One failure per item: B2 `test_the_ordinary_kit_with_no_kit_md_spaces_all_three_of_its_publishes`; SF1 `test_a_daemon_start_publishes_one_notification_listing_the_re_minted_held_jobs`; SF2 `test_the_integration_doc_states_the_limit_pair_as_it_is_implemented`; SF3 `test_doctor_judges_every_pretooluse_bash_hook_not_only_the_first[allow-all-before]`; SF4 `test_an_empty_project_name_is_refused_at_every_entry_that_takes_one`; SF5 `test_a_pipeline_json_written_before_the_anchor_had_fields_still_reads`. Three tests stay green after the revert, as the body concedes: `test_the_shapes_fixture_pins_the_bare_name_rules_false_positives`, `test_hands_who_named_alpha_when_alpha_is_the_broken_one_exits_1` and `test_doctor_passes_a_second_pretooluse_entry_that_is_not_for_bash`. SF6 is coverage only; no revert can turn it red. Restored; the worktree was clean.
3 ./scripts/check GREEN: "2751 passed in 178.44s (0:02:58)" / "check: green" (EXIT=0). This matches the body's 2751.
4 B2 PASS: every kit branch that publishes is now spaced. Receipt → sleep 1.1 → `_file_apply`; the no-KIT.md branch and the unusable-first-line branch (both `default_why`) → sleep → answer. The refusal and failed-apply paths only write `kit.refused`, which publishes nothing. The test really binds the no-KIT.md branch (`kit_zip(good_entries(None))`, and it asserts the "apply mission-11: " answer). Two caveats: (a) the 1.1 s is counted from when the held POST is handed to a background task, not from when it lands, so a held POST slower than 1.1 s can still arrive second; (b) a user playbook's own `job.held` notify rule (allowed, not shipped) still publishes in the same instant as the hold.
4 SF1 PARTIAL: with only held jobs, start publishes exactly one notification ("hands: handsd started", with the held ids, no buttons, nonces re-minted). The loss of buttons is confirmed, and §31 accepts it ("listed inside it rather than each published"). But I probed a start with an orphaned consult driver job and got two publishes 7 ms apart: `'hands: the pipeline stopped'` at 2661239.836, then `'hands: handsd started'` at .843. That older path still breaks "daemon start publishes one notification". §31's list-held-jobs clause contradicts §25's re-send (DESIGN.md:943); §31 is the later rule.
4 SF2 PASS with one inaccuracy: `NOTIFY_KINDS={"job.held"}`, `EVENTS` has no resume, and the limits.py:308 `max(PAIR_SPACING_S, …)` floor are all stated correctly. The doc's claim that "`job.held` is the only inbox event kind hands publishes by itself" is contradicted by `stop`: it is an inbox event (spool.py:128) that is always published, which the same paragraph says itself.
4 SF3 PASS for the review's case. Doctor failed (exit 1) on a second Bash hook with matcher `"*"`, `""`, none, `"Bash|Read"`, `".*"`, `"Ba.*"`, `"Bash.*"`, `"(?i)bash"`, `"mcp__.*|Bash"`, and on the allow hook placed before the guard. It passed (exit 0/ok) for `"bash"`, `"B"`, `"Read"`, `" Bash"`, `"Bash "`, a list matcher `["Bash"]`, and a second hook of type `prompt`, `http` or with no type. Doctor judges a matcher by whether the whole pattern matches `Bash` exactly, and it skips any hook that is not a command hook.
4 SF4 PASS: all ten shapes exit 1 with `project name '' does not match [A-Za-z0-9][A-Za-z0-9._-]{0,63} …`: `hands --project "" status|who|doctor`, `HANDS_PROJECT= hands status|who|doctor`, `handsd --project ""`, `HANDS_PROJECT= handsd`, `handswho --project ""`, `HANDS_PROJECT= handswho`. The control (no name given) falls to alpha. `~/.hands` was unchanged; only uv's cache appeared in the temp HOME.
4 SF5 PASS: the test reads `{"daemon_start": started[0], "job": about.id}` back off pipeline.json, the older bare-string shape still reads, and both REVIEW-14 cases are disclosed in the `ConsultAnchor` docstring but not fixed. SF6 PASS: the fixture has all 17 rows, and the `hands who` named-broken test exists (coverage only).
NOT PROVEN: whether Claude Code matches hook matchers as whole patterns or unanchored regex, or trims spaces. If unanchored, shapes like `"B.s"` or `"Ba+"` select Bash and doctor would miss them. Also not proven: ntfy ordering over a real network, and Claude Code's precedence when several hooks answer.
```

### adf3d7a (U3)

```
REPORT
sha adf3d7a (parent 6b27320), mission 15 U3 "Architect guard mode and `hands kit file`"

1 Body PASS: 11 files in `--stat` match the body's product-file prose (bash_guard.py, cli/config/kit/phone/runner.py, FINDINGS.md); the four test files (tests/test_bash_guard.py, test_config.py, test_kit.py, test_runner.py) are described in the "Tests (red first)" paragraph but named by no path — the known, disclosed omission, confirmed exactly those four.

2 Test-first PASS: reverting the 6 non-test product files to parent → tests/test_config.py+test_kit.py+test_runner.py: "16 failed, 580 passed in 57.89s"; tests/test_bash_guard.py: "1 error in 0.83s" (collection ERROR: "AttributeError: module 'bash_guard' has no attribute 'ARCHITECT_SELFTEST'"). Named failures include test_an_architect_role_loads_beside_the_others, test_the_architect_role_is_always_architect_whatever_its_env_says, test_an_architect_role_with_permission_flags_does_not_load[both], test_kit_file_refuses_a_path_that_is_not_under_hands_kits[outside/dotdot/symlink], test_kit_file_refuses_when_hands_{kits,clone}_is_unset, test_kit_file_{does_not_file_a_failing_kit…,json_says…,files_the_held_apply…}, test_the_phone_and_the_architect_file_one_apply_with_two_origins, test_an_architect_job_carries_its_role_clone_and_kits, test_hands_help_lists_kit_file, test_hands_kit_help_lists_both_subcommands. Restored → clean.

3 ./scripts/check GREEN: "3013 passed in 208.28s (0:03:28)" / "check: green" (exit 0, ruff "All checks passed!"); selftest 315/315 ok in normal AND architect mode.

4 Authority (architect mode, real KITS+CLONE): send/approve/deny/go/put/resume/pause/open, `hands wait`, `kit apply`, `git push`, `git -C <clone> push`, `git remote set-url`, `hands kit file --project/--socket` all exit 2; kit check/file/show/jobs/inbox/pipeline/status and read-only `git -C ./repo` allowed. `git -C` realpath-pinned to HANDS_CLONE.
4 KITS confinement holds for cp/mv/mkdir/zip and for `unzip … -d <dir>`: source-outside, `-r`/`/tmp/out`/`../`, `zip /etc/hostname`, `zip -T`/`--unzip-command`/`-@`/`-x`, `cp -t`/`--target-directory`/`-s`/`-l`/`--remove-destination`, `mkdir -m`, `ln` (still "file mutation"), `unzip -x/-l/-Z` all exit 2. Zip-slip (`../`, absolute, symlink-entry) into `-d kits/slip` is neutralized by Info-ZIP. Realpath `under()` correctly refuses cp/mv/mkdir/unzip and `--write` Write through a symlink-in-kits whose target is outside (existing-parent case). `--write` matcher fails closed on non-architect mode, non-string/empty file_path, missing tool_input, NotebookEdit, Bash, non-dict, unset HANDS_KITS. Config: HANDS_ROLE forced to "architect" over env table, permission_flags refused at load, HANDS_CLONE/HANDS_KITS forced from cwd by runner (never env table/handsd env). phone.py now sends `apply_params(plan,"kit")` — shared with kit file's `apply_params(plan,"architect")`, only `origin` differs. H-030 confirmed: `zip -r kits/m.zip kits/m16/DESIGN.md` yields entry `kits/m16/DESIGN.md`, not a repo path; no `cd` in table. Read-only surface = driver's: `cat /home/msi/.ssh/id_rsa` and `grep -r … ~/.ssh` allowed (reads any secret) — §31 grants "the driver's read-only table", so by design, not a hole. DESIGN.md, meta/plan.md, meta/CHECKPOINT.md untouched.

4 FINDING (guard hole — writes outside HANDS_KITS): `unzip` with no `-d` is guard-allowed and extracts into the hook's cwd, which is the architect sandbox `~/hands-architect/<project>/` — the PARENT of HANDS_KITS (`<cwd>/kits`), not under it. Command `unzip -o kits/attack.zip` → guard exit 0; running it for real extracted a crafted zip and OVERWROTE `<cwd>/.claude/settings.json` ("OVERWRITTEN BY UNZIP") and `<cwd>/.claude/hooks/bash_guard.py` ("# neutered guard"), plus `<cwd>/DESIGN.md`, `<cwd>/sub/x.txt`. (`../` entries are stripped by Info-ZIP, but plain relative entries like `.claude/...` land in cwd.) The KITS_TABLE `unzip` row confines only the path ARGUMENTS (the zip, and the `-d` value) — it never requires `-d` and never confines the default destination. Since Claude Code re-executes the hook file per tool call, overwriting `.claude/hooks/bash_guard.py`/`settings.json` neuters the guard on the next call = full confinement escape. This contradicts the file's own docstring/error text ("the architect writes only under $HANDS_KITS") and architect/settings.json's `Bash(unzip:*)` which relies on the guard to confine.

NOT PROVEN: no real Claude Code session drove either hook (Write/Edit/MultiEdit payload shapes taken from field name `file_path`; MultiEdit shape unobserved); no handsd-started architect role, so env+guard+`kit file` not exercised end-to-end together outside tests; H-030 means the role's intended repo-path kit is not demonstrable; TOCTOU between the guard's realpath check and the later actual write is inherent and untested.
```

### c9ccc18 (U4)

```
REPORT
sha c9ccc18 (parent adf3d7a), mission 15 U4 "Series mode and autonomy" (playbook: series mode, and the engine approves the architect's applies). It covers §31 bullets 4 and 6 and "Escalation conditions", plus §8, §10, §26, §27 and §6.
1 Body PASS: the 9 files listed in the body match `git show --stat` exactly (+935/-41). DESIGN.md, meta/plan.md and meta/CHECKPOINT.md are unchanged. FINDINGS.md only gains lines (0 removed; H-031 added).
2 Test-first PASS: with the 5 product files put back to the parent, `tests/test_playbook.py` fails to collect: "E   ImportError: cannot import name 'AUTONOMOUS_APPROVAL' from 'hands.playbook'". `test_gates.py` + `test_docs.py`: "7 failed, 112 passed": `test_the_decider_vocabulary_is_section_8s`, `test_the_playbook_decider_releases_the_architects_hold`, `test_the_playbook_decider_releases_nothing_but_an_architects_hold[cli|kit|phone|playbook]`, `test_the_code_vocabularies_are_section_6s_lists`. Files restored; worktree clean.
3 ./scripts/check GREEN: "3063 passed in 369.16s (0:06:09)" / "check: green". This matches the body's 3063.
4 AUTHORITY HOLE, CONFIRMED end to end (real daemon + fake_claude): any socket client can get a gate the §8 default patterns force released with no human. `Api.send` (api.py:146 `origin: str = "cli"`, passed through at :187) is in `COMMANDS` and takes `origin` from the wire. Its only check is `spool.py:469`, which accepts any value in ORIGINS, "architect" included. `decide_from_playbook` (api.py:607-632) checks only origin == architect (:621) and state == held (:627), never that the gate is `apply <name>`. The engine checks the same two things at playbook.py:1324. My repro sent over the raw socket (`hands.cli.call`, no kit check, not `hands kit file`) `{"method":"send","params":{"role":"builder","context":"clear","origin":"architect","prompt":"gh pr create … decisions-2026.md"}}` under the unit's AUTONOMOUS playbook. The job came back held, then ran to done with gate `{"decided_by":"playbook","decision":"approved","reason":"the prompt matches the gate pattern 'decisions-' (§8)"}`. This undoes §8's "gating on the default patterns cannot be disabled" and the "and over nothing else" claim in the docstring at api.py:615.
4 Who can reach it: the builder role, which README.md:70 shows running `--dangerously-skip-permissions`; aux and any process of the same user can too. The driver cannot: CLI `send` has no `--origin` (only `jobs` has one, cli.py:246), and the guard's `send_violation` applies. The architect is limited to `hands kit file`, which checks the kit on the client side only, so the daemon just trusts the label. The phone path sets `kit`, and `put` takes no origin. The body's "no socket client can reach it" is true of the method but not of the authority.
4 Also correct, all tested: nothing is approved while paused, for another origin, under "phone" mode, or with autonomous=false. A hold filed before the playbook became autonomous stays held after the switch, a daemon restart and `hands resume` (repro: "STATE held True"). A refused approval stops the pipeline.
4 Kickoff rule: `_engine_rules` (playbook.py:1263, prepended at :1226) matches ANY `builder.done` with `^VERDICT: kit applied`, from any origin. Repro: a plain `hands send` job (origin cli) replying "VERDICT: kit applied deadbee" fired `rule: -1` and started a `playbook`-origin kickoff. A phone-route kit applied under autonomy would do the same. The prompt is always the fixed `[series] kickoff`, so the harm is low, but the rule is not tied to the apply the engine approved. It does take precedence over the playbook's own rule (test and inbox show -1 before 1).
4 `architect="role"` without `[roles.architect]`: it is enforced only in `PlaybookEngine._load`, which runs at the first event or job start and stops the pipeline (repro F). At daemon start `hands pipeline` reports loaded=true, error=None, paused=false, and `hands doctor`'s playbook row is "ok" with exit 0 (repro D). `kit check` never looks. So it is not "a config error" as §31 says; the body defers doctor to U6.
4 Defaults: gate_failures=2 follows §31's example. escalate_on=() is not what §31 says: it names three conditions, including one "the engine stops on … itself". Nothing enforces either yet (U5/U7, stated). H-031: test_docs.py still pins §6 as `["cli","driver","phone"]` and asserts `set(DECIDED_BY) == {*deciders,"playbook"}` with len+1, so a fifth value still fails.
NOT PROVEN: a real builder session actually opening the socket (shown only by the same-user socket client and the README flags); the CLI `hands kit file` path; U6's doctor row. My repro test file was deleted and the worktree removed.
```

### 9ed931b (U5)

```
REPORT
sha 9ed931b (parent c9ccc18), mission 15 U5 "Consult for the architect" (subject: "playbook: the architect is consulted on the review outcome"; DESIGN §31 consult role=architect plus escalation conditions, §27, §10, §11, §8)
1 Body PASS: the listed files (src/hands/{playbook,config,daemon,limits,cli}.py, tests/test_playbook.py) are exactly the 6 files in `git show --stat` (1231+/56-). DESIGN.md, meta/plan.md and meta/CHECKPOINT.md are untouched (empty diff).
2 Test-first PASS: reverting the 5 product files gives a collection error, "ImportError: cannot import name 'ARCHITECT' from 'hands.playbook'". Parent playbook.py plus a stub of the 6 imported names gives "31 failed, 248 passed in 122.58s". The failures include test_end_to_end_next_kit_waits_for_the_apply_the_architect_filed, test_end_to_end_escalate_notifies_with_the_reason_the_session_and_the_resume_line, test_the_budget_is_the_engines_own_stop, test_the_architect_budget_is_counted_per_series_not_per_mission, test_every_other_architect_end_stops_and_notifies[limited-None-ended limited] and test_end_to_end_a_driver_job_that_cannot_spawn_files_consult_done_and_stops (an expectation that moved, the journal line). Restored; worktree clean.
3 ./scripts/check GREEN: "3092 passed in 232.61s (0:03:52)" / "check: green". This matches the body's 3092.
4 Roadmap: playbook.py:1709 puts the whole `meta/ROADMAP.md` into the prompt, not "the roadmap's next milestone". This is a deviation. The body and docstring (playbook.py:1703-1705) disclose it, but no finding exists (FINDINGS.md has no roadmap entry). "Read like the playbook" is not accurate: the file is read from the working tree, while the playbook loads only the committed file.
4 Verdict matching: `job.verdict` is the first line anywhere in the reply matching `^VERDICT:` (runner.py:252-259), then an anchored regex (playbook.py:201, 170). The code comment's "first line of the reply" is not what happens. Probes: an architect reply quoting `VERDICT: review mission 3 blockers=0` before its own verdict stops with "is none of ..." (safe). With two VERDICT lines the first wins. Review text only goes into the prompt; the engine matches only the architect job's verdict (1831), so a review cannot steer the engine directly. The `<name>` in `next kit` is captured but never compared.
4 `_filed_apply` (1876-1888) accepts any later job with origin "architect". It does not check role, hold, gate or kit name. Probe: a done `aux` job of origin architect satisfies `next kit foo` (not paused, no notify). A denied apply named "bar" also satisfies it. The series still does not stall silently: `job.denied` or `builder.failed` with no rule hits §10's default stop. Under autonomous=false, `job.held` with no rule stops and the human decides, which is fine.
4 Escalate: probe gives the verbatim reason "architect.done: the architect escalated: blocker-unanswered: x — session sess-arch-1; continue it in the architect's directory with `claude --resume sess-arch-1` (§31)". It reaches the phone through `stop()`→`_notify` (daemon.py:138 `notify=self.notifier.notify`), not through NOTIFY_KINDS. Paused pipeline: the escalate and `limited` ends are suppressed and still notify "hands: a consultation stopped over a paused pipeline".
4 Budget: the budget check runs before enqueue (1644); probe shows 0 enqueued and "(budget-exhausted)". It survives a restart: a second engine read the anchor back, used=2. It is keyed only on `[series] name` (1269). Probe m17→m18→m17 gives used=0, so renaming the series resets the count. Under autonomous, the architect could therefore reset its own budget with a kit it files and the engine approves. Not disclosed.
4 Driver prompt is byte for byte unchanged: parent and commit `consult_prompt` are identical over 72 combinations of event, state, verdict and result. Side effect, disclosed only in part: limits.py:358 and 413 now never resume *any* limited architect-role job, including one a human sends that is not a consultation.
NOT PROVEN: a real architect producing a usable kit (H-030 open); concurrency of an autonomously approved apply that finishes before the architect's job ends; review shapes beyond the two fixtures.
```

### f798521 (U6)

```
REPORT
sha f798521 (parent 9ed931b), mission 15 U6 "Docs and the templates" (plus doctor's architect row); DESIGN §31 with §12, §14, §26, §27, §29, §10
1 Body PASS: the file list in the body is the same 11 files as `git show --stat` (1239+/61-). DESIGN.md, meta/plan.md and meta/CHECKPOINT.md are untouched. FINDINGS.md only gains lines (35/0, H-032).
2 Test-first PASS: with doctor.py, kit.py, docs/ and templates/ reverted to the parent, the three test files gave "35 failed, 468 passed in 53.17s". The failures include `test_a_config_with_roles_architect_reports_the_role`, 6x `test_an_architect_whose_write_matcher_is_not_the_guard_fails_doctor[...]`, `test_kit_file_says_who_releases_the_hold_not_that_a_human_decides_it`, 2x `test_each_template_loads_with_its_architect_block_uncommented[...]` and `test_the_handbook_section_12_onboards_the_architect_role`. After restoring, the tree was clean and all three files passed.
3 ./scripts/check GREEN: "3126 passed in 292.81s (0:04:52)" / "check: green"
4 Doctor row: the shipped settings are ok. These are all judged fail: no write matcher; "Write|Edit" alone ("no PreToolUse command hook for MultiEdit"); `--write` missing; a permissive second hook in the same entry or a separate one; a non-guard hook on `*`; `disableAllHooks`. "Write" plus a separate "Edit|MultiEdit" is correctly ok. `HANDS_ROLE=architect` needs no check because `RoleConfig.spawn_env` (config.py:201) always sets it.
4 Doctor gaps (probed): the row stays **ok** with `permissions.defaultMode: "bypassPermissions"`, with `"allow": ["Write"]` or `"Bash"` added, with a non-command (`type: prompt`) write hook, and with a write hook pointing at a different absolute guard file. That last one passes because doctor.py:590 throws away `_write_named`, so only the Bash hook's file is self-tested. The push URL is not checked for either role: a clone whose push URL is the real origin was ok (doctor.py has no push check), so §31's "push URL is disabled as the driver's is" is not verified. The driver row has the same gap, so this is not new.
4 Docs claim the disk contradicts: docs/INTEGRATION.md:786 ("a config error, named in the stop and in `hands doctor`") and docs/PLAYBOOK.md:105 ("…and by `hands doctor`"). `_playbook_check` (doctor.py:919) never calls `check_series_roles`, which only the engine calls (playbook.py:1225). Probe: a committed playbook with `architect = "role"`, `autonomous = true` and no `[roles.architect]` gave doctor "playbook ok", "role architect ok", "doctor: green". §31's doctor bullet asks for this config error, and test_docs.py:1473 pins the false sentence as a string.
4 Other doc samples match the code: the defaults 12 and 2; the three verdicts; architect consult only on `aux.done` (a `builder.done` consult is refused at parse); an `architect.done` rule is refused at parse; `unzip` in architect mode (bash_guard.py:251,865; §31 lists only mkdir/cp/zip/mv); the pipeline counter (cli.py:596); H-030 in INTEGRATION and the handbook; handbook §12 onboarding at docs/ARCHITECT-HANDBOOK.md:310. docs/PLAYBOOK.md does not mention H-030 (0 hits), which contradicts the body's "every doc that describes the role says what is not proven".
4 Switch point: the setup block is verbatim, but the section at INTEGRATION.md:764 paraphrases the deliverables and the hand-back step. Only three sentences are pinned verbatim, so the body's "carried verbatim" is only partly true. Templates: I uncommented the blocks myself, committed them and ran the real `load_playbook`. Both load as role, autonomous, 2, ESCALATE_ON, 12, with the consult on `aux.done` first among the `aux.done` rules. `hands --help` and `hands kit --help` list `kit file`. The `kit file` output (kit.py:1316) now names both releases and still says "held builder job (gate: apply …, origin: architect)".
4 The "~20 claims" docs tests: the values (constants, keys, verdicts, defaults) are checked against code and would catch drift. The behaviour claims ("by `hands doctor`", "refused when parsed", "stops when it filed none") are only string checks, and one of them already locks in a false claim.
NOT PROVEN: a real architect role run; Claude Code's own matcher semantics (doctor assumes the matcher regex must match the whole tool name); whether a bypass mode in settings.json weakens hooks at runtime. Worktree /tmp/rev15-f798521 removed.
```

### fd1a2dd (U7)

```
REPORT
sha fd1a2dd (parent f798521), mission 15 U7 "This repository's playbook". The body cites DESIGN v3.14 §26, §27 Conventions, §31 and §10.
1 Body PASS: the body lists PLAYBOOK.toml and tests/test_playbook.py, which is exactly what `git show --stat` shows ("2 files changed, 13 insertions(+), 4 deletions(-)"). The PLAYBOOK.toml diff is only the kickoff line going from 15 to 16, plus `architect = "phone"` and its two comment lines ("# §31: the architect is the human in a chat Project, not a role handsd starts." / "# That is the default; this series states it."). There is no `autonomous`, `gate_failures`, `escalate_on`, `max_architect_consults` or rule.
2 Test-first PASS: I used a separate worktree at f798521 (/tmp/rev15-f798521 was already taken) with only fd1a2dd's test file copied in. Red: "E - Read meta/BUILDER-16-PROMPT.m / E + Read meta/BUILDER-15-PROMPT.m", at tests/test_playbook.py:291 AssertionError. That is the kickoff value, not PlaybookNotCommitted. After a local commit changing only the kickoff line: ">       assert table["architect"] == "phone", ..." / "E       KeyError: 'architect'", at tests/test_playbook.py:297. The loader asserts `book.architect == "phone"` and `autonomous is False` passed there because of the defaults, so only the raw-table check turns red. I also confirmed the wrong red the body describes: with PLAYBOOK.toml edited but not committed, 4 root-playbook tests fail with "hands.playbook.PlaybookNotCommitted: …PLAYBOOK.toml is dirty…(§10)".
3 ./scripts/check GREEN: "3126 passed in 367.21s (0:06:07)" / "check: green". This matches the body's 3126.
4 Kickoff PASS: "Read meta/BUILDER-16-PROMPT.md and execute the mission below its divider." has the same form as fa8fbae (15) and 0a14085 (14), and as the line at the top of BUILDER-15-PROMPT.md. `architect = "phone"` is §31's default. The test pins the `[series]` keys to exactly ["architect","kickoff","name"].
4 Kit gate PASS: the zip has one entry, meta/BUILDER-15-PROMPT.md (8650 bytes, `cmp`-identical to HEAD). `uv run hands kit check <zip> --repo .` with a temp HOME printed six PASS rows: paths, playbook, brief (kickoff 'Read meta/BUILDER-15-PROMPT.md …'), verdicts, wording, protocol. It ended with "kit check: pass (6 of 6 checks)" and exit 0. The playbook row says "its kickoff is not compared", so the new BUILDER-16 line is not checked by this gate.
4 Doctor: with a minimal config (builder cwd = worktree, no [notify]), the go row is "ok go off: no [notify] cmd_topic and cmd_secret…" and does not warn. The warning appears only once `cmd_topic` and `cmd_secret` are set: "warn go … the kickoff names meta/BUILDER-16-PROMPT.md, which is not in /tmp/rev15-fd1a2dd: a phone `go` would send the builder to a file that is not there (§31)". The result was "doctor: green", exit 0. The body's "doctor still exits 0" holds, but its unqualified "`go` row now warns" is true only when the command channel is on.
4 Absent brief: this is not a defect of U7. §27 Conventions requires the next mission's line, and precedent matches: fa8fbae named BUILDER-15 before 1f8141c added that brief. It is still REVIEW-14 should-fix 7's situation, now warned about but not blocked: a phone `go` before the architect ships BUILDER-16-PROMPT.md sends the builder to a missing file. DESIGN.md, meta/plan.md and meta/CHECKPOINT.md are unchanged between f798521 and fd1a2dd.
NOT PROVEN: nothing checks that `architect = "phone"` behaves differently at run time, and no real phone `go` was sent. The body's "`hands pipeline` prints the playbook block" was not re-run. Only root-playbook tests were run red; I did not run the full suite at f798521. My two worktrees are removed and the main checkout is clean. The other /tmp/rev15-* worktrees are not mine and I left them.
```
