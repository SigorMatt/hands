# REVIEW-5 — cold review of mission 5 (review 4 and the daemon's memory)

Aux session, no mission context. Base `6c9440d` → `origin/main` `ffa4c65`
(tip of `main` `eb354e9`, the report commit). Protocol: `meta/REVIEW-PROTOCOL.md`.
Seven unit commits (U1–U7), one sub-agent each in its own detached worktree;
the nine `meta:` bookkeeping commits skipped, except that U0's two corrections
and U8's report — the products of `meta:` commits this mission's acceptance
names — were checked here by hand.

    VERDICT: review mission 5 blockers=2 should-fix=7

Read: `DESIGN.md` §21 (with §4, §7, §10, §12, §13, §2),
`meta/BUILDER-5-PROMPT.md`, `meta/FINAL-REPORT-5.md`,
`meta/findings/FINDINGS.md` (H-011, H-012, H-013),
`git log --oneline 6c9440d..origin/main`.

## Blockers

1. **U4 closed the prompt half of review 4's should-fix 3 and left the fault
   class open through the envelope, and two shipped sentences say otherwise.**
   `docs/INTEGRATION.md:238-240` now reads "Non-ASCII text is not escaped …
   and the daemon's line room is the cap plus a quarter, **so anything the
   client accepts fits**", and `src/hands/daemon.py:60-66` says "the quarter
   left over is the envelope's — method, id, role, `--file` writes, gate. **A
   quarter of the cap is 2.5 MiB, more than a command line can hold.**" A
   command line can hold more than that, because `--file PATH=CONTENT` is argv
   and JSON doubles a backslash. Verified here, arithmetic first:

       $ python3 -c "import subprocess; a=['x'*131000]*12; \
           print(subprocess.run(['/bin/true',*a]).returncode)"
       0                                   # 1 572 000 bytes of argv: execve accepts it
       # request = at-cap prompt + 12 --file values of backslashes
       wire: 13630051   limit: 13107200   over by: 522851

   The U4 sub-agent reproduced the same shape end-to-end against a real
   `handsd` (10 MiB − 1 KiB prompt + 16 `--file` args): `hands: [Errno 32]
   Broken pipe`, exit 1, nothing in the daemon log — each half alone exits 0.
   That is review 4 should-fix 3's own words, "fails somewhere other than at
   the path the human named", re-entered one field over, while
   `FINAL-REPORT-5.md` §4 marks should-fix 3 `closed 6d9664d` and §3 does not
   carry it. The unit's own work is sound and its prompt-side proof is strong
   (`_wire_bytes` is byte-exact against `json.dumps(ensure_ascii=False)` over
   every codepoint 0–0x2FFF); what is wrong is the claim of totality. Fix
   shape, either: measure the whole request on the wire before sending (the
   client already builds it), or narrow both sentences to the prompt and put
   the envelope in §3 and in H-012.

2. **U6's bound silently changes an answer the code deliberately gave, and the
   commit body and the report both say no answer changes.** `53bb986`'s body:
   "4 MiB is thousands of ordinary entries, far more than the 20 `-n` defaults
   to, **so no answer a caller sees today changes**"; `FINAL-REPORT-5.md` §3
   item 14: "No caller today asks for more than 20, **so no answer changes**".
   At the parent, `Api.tail` ended `"entries": entries[-n:] if n else entries`
   — `n = 0` meant *every* entry, an explicit branch, and `hands tail -n` is
   `type=int` with no lower bound (`src/hands/cli.py:261`). At the tip,
   `tail_entries` opens `want = MAX_TAIL_ENTRIES if n <= 0 else min(int(n),
   MAX_TAIL_ENTRIES)`, so `hands tail --role builder -n 0` on a transcript of
   more than 1000 entries now returns 1000 of them with nothing in the answer
   saying so. The same silence covers the other end the body does disclose: a
   transcript whose trailing entry is wider than `TAIL_WINDOW_BYTES` answers
   `[]` — the U6 sub-agent drove both. The bound itself is right and its
   measurement is the best evidence in this mission (tracemalloc peak flat at
   ~492 KB for 2 000 vs 200 000 events; 272 KB vs 139.8 MB against a 64 MB
   transcript). Fix shape: keep `n <= 0` meaning "all" (or refuse it), or carry
   a `truncated: true` in the answer — and correct the sentence either way.
   §4 says "last n transcript entries" and names no cap, so the cap is also
   worth one line there, which is the architect's.

## Should-fix

1. **The guard's arbitrary-exec surface still contains a wrapper of exactly the
   shape review 4 blocker 1 named, and both layers pass it.** Executed here
   against the tip (`check()` returning `None` = allowed), git 2.43.0:

       git ls-remote --upload-pack='touch /tmp/gpwnv/PWNED1' /tmp/gpwnv/src -> None
       git -C ./src fetch --upload-pack='touch …' /tmp/gpwnv/src            -> None
       $ ls -l /tmp/gpwnv/PWNED1
       -rw-rw-r-- 1 msi msi 0 Sep 12 16:06 /tmp/gpwnv/PWNED1      # it ran

   No `-c` and no config needed; `--exec=` is the synonym.
   `driver/settings.json` allows `Bash(git ls-remote:*)`, `Bash(git fetch:*)`
   and `Bash(git -C ./repo fetch:*)`, so the human is not asked either — the
   sentence blocker 1 wrote about `git diff --output=`. This is **not** a
   regression and **not** a failure of U1, which implemented §21's list
   exactly and completely; `FINAL-REPORT-5.md` §3 item 1 is honest that the
   surface "is not known to be empty", but its enumeration lists only mutation
   (`git branch`, `git remote prune`, `git fetch <refspec>`, `find`) and a
   reader will take the exec class as closed. Smaller, same family, all
   allowed at the tip: `git branch --edit-description` (launches `$EDITOR`,
   writes repo config) and `git -C ./repo -C --exec-path=/tmp/evil log` (the
   guard steps over the word after `-C` unjudged; inert only because git reads
   it as a directory).
2. **Three bypasses of the new hook are absent from the report's NOT PROVEN,
   and one input shape fails open.** Verified by driving `main()` here:
   `sleep 30 &# note` → exit 0, and bash really backgrounds it (`[1]+ Running
   sleep 0.2 &`); `/usr/bin/nohup ./long.sh` → exit 0 (the token match is
   unqualified `nohup` only); `bash -c 'sleep 30 &'` and `eval 'sleep 9 &'` →
   exit 0 (quoted text is blanked, which is the guard's model, but a role
   session writes that spelling). §3 item 3 lists `screen -dmS`, `tmux new -d`,
   `at`, `systemd-run`, a forking script and `echo a&b` — all confirmed
   allowed — so the list is incomplete rather than wrong. Separately, a
   `tool_input` that is a list or a non-string `command` raises and exits **1**
   (traceback on stderr), which Claude Code treats as non-blocking: the only
   shape that does not fail closed, against a body that says "exit 2 … for
   input it cannot parse". Not reachable from the real Bash tool today.
3. **`Runner.retained()` reports a bound its own docstring overstates.** The
   docstring says "Nothing counted here is per-event, so every count is bounded
   by the number of jobs **in flight**". `_procs`, `_running`, `_session_ready`
   and `_logs` are popped at the end of a run (`runner.py:348-350,397`);
   `last_argv` never is, so it holds one argv list per job for the daemon's
   life. Small (argv carries no prompt) and the direction of the unit is right,
   but it is a growth claim inside the unit about growth. The in-flight
   `_Parsed.result`, the 50-line stderr tail and asyncio's reader buffer are
   bounded but unreported by the method, so "everything the runner holds" (the
   commit body) reads wider than what it counts.
4. **U2's containment is lexical, and the commit removed the only coverage of
   two branches it says stay load-bearing.** A `monitor_cmd` that is a symlink
   inside `ops.repo` pointing outside it loads clean (`link.sh` → `outside/
   evil.sh`, `tosh` → `/bin/sh`), as does a traversal through a symlinked
   directory — there is no `resolve()`/`is_relative_to`. §3 item 12 discloses
   the symlink case honestly; what is not disclosed is that `doctor.py:245,247`
   ("does not exist" / "is not executable") are now uncovered by the whole
   suite on a coverage run — the one test that reached `:245` was repurposed by
   this commit, and its docstring still calls that row "the answer for a script
   deleted after the config was read". `monitor.py:560` ("is not a file") is
   uncovered too (pre-existing, and now unreachable by config).
5. **Three edges U5 left.** (a) The helper-coverage AST scan binds only
   sections that already call `_check_keys`: the sub-agent added a whole new
   `[extra]` section to the top-level key list and read `extra_t.get("sneaky2",
   "  pad  ")` raw — `tests/test_config.py` stayed green (76 passed), so a new
   section escapes both the scan and the unknown-key refusal. §3 item 10
   discloses the new-*helper* case, not the new-*section* case. (b) A state
   file whose `last_rule` carries no `playbook_sha256` at all is marked
   `stale: true` even when the loaded playbook is the one it fired under —
   untested, undocumented. (c) `_str_list` stripping reaches `gates.patterns`,
   which are case-sensitive substrings (`gates.py:127`), so a deliberate
   trailing space (`"rm "` to avoid `rmdir`) is silently widened to `"rm"`.
   Fail-safe in direction, but it is the one place padding was meaningful and
   nothing says so.
6. **U3's audits exempt by source text, not by type.** `status = "…"; assert
   "world" not in status` passes both audits (likewise `kinds`, `argv`),
   because `NOT_TEXT` matches the *name*; and the positive audit only fires on
   a str Constant or a Name, so `assert f"wo{'r'}ld" in out` and `assert
   ("wo"+"rld") in out` are invisible — both demonstrated live, neither present
   today. §3 item 9 states the class in general terms; these are its concrete
   shapes. Minor and checkable: `conftest`'s docstring says the root guard
   keeps paths of "fewer than two components (`/`, `/home`)" while the code is
   `len(parts) > 2`, i.e. fewer than three, and
   `test_strip_paths_never_strips_a_root_directory` checks `/` and `/home`
   but not `/tmp`.
7. **The two prompt routes still disagree on the encoding refusal.** Under
   `PYTHONUTF8=1`, non-UTF-8 bytes through `--stdin` become lone surrogates and
   die inside `_wire_bytes` as `hands: 'utf-8' codec can't encode characters…`
   with exit **1**, while the same bytes through `--prompt-file` give "not
   UTF-8 text" and exit **2**. U4 claims size and emptiness parity only, so
   this is unclaimed rather than false — but it is the same seam should-fix 3
   was about. Related and unpinned: the daemon's `bad request: Separator is
   found, but chunk is longer than limit` reply is never seen by a user (the
   client has already taken the broken pipe), which is what makes blocker 1
   silent.

## Notes

**The gate.** Green at the tip in this working tree, three consecutive runs:
`All checks passed!` / `929 passed in 58.45s, 52.61s, 52.64s` / `check: green`,
exit 0 each. `driver/hooks/bash_guard.py --selftest` → `selftest: 77/77 ok`,
`.claude/hooks/no_background.py --selftest` → `selftest: 50/50 ok`, exit 0 both.
Every unit commit is green at its own sha on the sub-agents' runs, and the
per-unit counts `FINAL-REPORT-5.md` §2 claims are exact to the number: 778,
789, 794, 804, 812, 818, 929 (= base 726 + 203). No sub-agent reproduced the
"three consecutive runs" claim per unit; each ran the gate once or twice, so
that part of the report rests on the builder's own runs.

**Test-first held on every product unit**, with only that unit's non-test
files reverted: U1 28 red (exactly the 28 the body lists as newly blocked; the
11 new allowed cases stayed green, correctly, as anti-over-refusal guards),
U2 10 red, U4 10 red (including the literal `Broken pipe` regression), U5 red
on all three concerns reverted separately (7 / 2 / 3 — and the two AST-scan
tests stayed green at the parent, so they pin a mechanism, not the fix),
U6 3 red plus a collection failure on `MAX_TAIL_ENTRIES`, U7 red at collection
plus one docs test. U3 is test-only: its load-bearing proof is that all four
instances its body names go red at the parent under a crafted `--basetemp`
(the review's two, plus `"for 40m"` and `"no progress and no liveness"`), and
that a newly added unstripped assertion fails both audits — both reproduced
independently here. 5/5 green under the five crafted basetemp values.

**Acceptance, checked item by item.** `grep -rn 'stop\.suppressed' src tests
docs driver` → nothing (exit 1); the remaining hits are historical `meta/`
prose. `meta/FINAL-REPORT-4.md` §3 carries the dated correction of item 15,
appended after an untouched original. `meta/FINAL-REPORT-5.md` exists with a
NOT PROVEN section and the review-items table. No unit commit touches
`DESIGN.md`, `meta/plan.md` or `meta/CHECKPOINT.md`; no `meta:` commit touches
`src/`, `tests/`, `docs/` or `driver/`. One commit per unit, `<area>: <one
line>` with a body naming the unit, the sections and the review item.

**§3 item 1 was re-executed, not read.** All six commands it lists as allowed
return `None` at the tip, and all five of review 4's probes plus the four
read-only driver commands behave as it says. The section is honest about what
it covers; should-fix 1 is what it does not cover.

**U6's audit claim is true.** At `53bb986^` the daemon wrote and flushed each
line to `<job>.stream.jsonl` through `_streams`/`_capture` — no list of events
existed in runner, daemon or api — and `Api.tail` did `path.read_text()` on
the whole transcript per call. So §21's premise ("never accumulated in memory"
as a change to make) was already half true, U6 is a reader fix plus a writer
relocation, and the 959 MB remains explained rather than diagnosed. The report
says exactly this, in §3 item 5 and §6 item 1, which is the right place for it.

**Review 4's should-fix 6 is still open as filed.** The report records it "not
applicable" on the brief's instruction and §3 item 15 says the keeper is
absent; the intersection is still 4 rows with the test asserting only
`>= 20 / >= 10 / >= 10`, over tables that grew to 102 and 77. One assertion.

**Carried, and correctly stated as carried:** REVIEW-3's should-fix 3, 6 and 7
remain deferred and nothing in this mission touched them; H-012 and H-013 are
filed with the architect; the installed build is still mission 2's, so this is
the third mission whose code has never run outside pytest. Both blockers above
are the kind of thing one real `hands send` and one real `hands tail` would
have shown.

## Per-commit verdicts

The seven sub-agent reports, verbatim. (U7's was returned with `&`, `<` and `>`
HTML-escaped by the harness; those characters are restored here so the probes
read as they were run. Two reports ran past the 12-line limit.)

### U1 — `50c466c`

    sha 50c466c — U1 "driver: the guard's git option policy (§21) and find's file-writing actions" (DESIGN §21 bullet 1, §12; REVIEW-4 blocker 1)
    test-first: PASS — reverting only driver/hooks/bash_guard.py to 50c466c^ gives "28 failed, 143 passed in 0.27s" in tests/test_bash_guard.py; the 28 red are exactly the 28 cases the commit body lists as "blocked only after this change"; all 11 new allowed cases stayed green, matching the body's claim. Restored, tree clean.
    gate: "== ruff ==\nAll checks passed!" / "778 passed in 28.25s" / "== cli smoke ==\ncheck: green" / EXIT=0. Body's other claims verified on disk: selftest 77/77 ok exit 0; ADVERSARIAL total 102 (69 block / 33 allow); SELFTEST 77; driver/settings.json untouched.
    design: CONFORMS to what §21 bullet 1 literally enumerates. Verified independently by importing the guard and calling check() myself, not via the test file: all 5 probes REVIEW-4 blocker 1 executed (git -c diff.external=…, git -c core.pager=touch, git diff --output=, git show HEAD --output=, find -fprint/-fprintf/-fls) are in ADVERSARIAL and blocked; all four brief-named driver reads return None. Over-refusal: none found against driver/CLAUDE.md or settings.json — every git/find line the kit's own docs use still passes; the pre-subcommand policy does newly refuse harmless globals (git -P, --version, --no-optional-locks, --literal-pathspecs, -C./path attached form), which is safe but is a behaviour change the body does not mention.
    forbidden: none touched — git show --stat lists only driver/hooks/bash_guard.py (+104/-25-ish) and tests/test_bash_guard.py. No DESIGN.md, meta/plan.md, meta/CHECKPOINT.md. Commit discipline OK: one commit, "<area>: <one line>", body names U1, §21/§12 and review 4 blocker 1; I found no claim the disk contradicts.
    NOT PROVEN: the arbitrary-exec class REVIEW-4 blocker 1 is about is NOT closed, only the wrappers named in §21. Live vector, confirmed by execution, not theory: `git ls-remote --upload-pack='touch /tmp/gpwn/PWNED1' /tmp/gpwn/src` and `git -C ./repo fetch --upload-pack='touch /tmp/gpwn2/PWNED' /tmp/gpwn2/src` each CREATED the file (git 2.43.0) while guard.check() returns None — no `-c` needed, no config needed. Worse than the fixed cases: `Bash(git ls-remote:*)`, `Bash(git fetch:*)` and `Bash(git -C ./repo fetch:*)` are all in driver/settings.json allow, so both layers pass it and the human is never asked — the exact sentence blocker 1 wrote about `git diff --output=`. `--exec=` (the fetch/ls-remote synonym) is allowed too. This is U8/NOT-PROVEN material at minimum, and arguably reopens blocker 1.
    NOT PROVEN (2): lesser holes still returning None — `git -C` steps over the next word unjudged, so `git -C ./repo -C --exec-path=/tmp/evil log` passes the guard (inert today only because git treats it as a chdir target and fails); `git branch --edit-description` passes and launches $EDITOR plus writes repo config; `git log -c core.pager=touch` passes (harmless as git parses it, but shows the post-subcommand scan does not know `-c`'s meaning). Non-holes I ruled out by execution: `ext::` without `-c` is refused by git itself ("transport 'ext' not allowed"), and `find -fprintf/tmp/out` attached is a find syntax error.
    NOT PROVEN (3): I ran ./scripts/check once (green), not the three consecutive runs the body reports; and the SELFTEST/ADVERSARIAL intersection is still 4 with the test asserting only >=20/>=10/>=10 (REVIEW-4 should-fix 6) — the brief assigns that to U3, so it is out of U1's scope, not a defect of this commit.

### U2 — `ce92ed6`

    sha ce92ed6 — U2 config: refuse an ops.monitor_cmd that is not a script in the ops repo (DESIGN §21 2nd bullet, with §5, §13; REVIEW-4 blocker 2)
    test-first: PASS — with src/hands/config.py + docs/INTEGRATION.md reverted to ce92ed6^, 10 failed: the 8 parametrized refusals in test_config.py, test_the_ops_repo_directory_can_never_be_the_monitor_script, and test_doctor.py::test_a_missing_ops_script_is_refused_before_doctor_can_report_on_it. test_docs/test_monitor changes stayed green (anti-regression, correctly so). Restored clean.
    gate: `== ruff ==` / `All checks passed!` / `789 passed in 30.17s` / `== cli smoke ==` / `check: green`, exit 0.
    design: conforms as written, lexically. My own loader-driving script (not the test names) confirms all 7 gate cases: `.`, `./`, `..`, `../x`, absolute, a directory, a non-executable file, a missing file all REFUSE with config path + `[ops]` + key + fix; `watch_monitor.sh` and `sub/nested.sh` LOAD with `monitor_path` naming them. Also refused: `sub/..`, `sub/../../outside/evil.sh`, `dir/`, `' watch_monitor.sh '`. Accepted (correctly): `./watch_monitor.sh`, `watch_monitor.sh/`.
    design holes (unguarded): the "under ops.repo" claim is lexical only — there is no `resolve()`/`is_relative_to`. A symlink inside ops.repo pointing OUT of it loads (`link.sh` -> outside/evil.sh; `tosh` -> /bin/sh), and so does a traversal through a symlinked directory (`linkdir/evil.sh` -> outside). `monitor_path` then names a script the ops repo does not hold. Untested and undisclosed in the commit body. `monitor_cmd` set with `repo` absent loads with no existence check (shape only; `monitor_path` is None, so harmless); `repo` set with `monitor_cmd` absent loads (correct, built-in monitor). `OpsConfig.__post_init__` is shape-only, so direct construction with `missing.sh` or `dir` still yields a bogus `monitor_path` — the body states this honestly.
    runtime branches: monitor.py's "does not exist" (:558) and "is not executable" (:562) are now proven post-load, as claimed. But doctor.py's equivalents at :245 and :247 are UNCOVERED by the whole suite (coverage run, term-missing) — the only test that hit :245 is the one this commit repurposed to assert the `config` row, and its own docstring still calls that row "still the answer for a script deleted after the config was read". monitor.py:560 ("is not a file") is also uncovered (pre-existing).
    forbidden: none touched — the commit changes only docs/INTEGRATION.md, src/hands/config.py, tests/test_{config,docs,doctor,monitor}.py. No DESIGN.md, meta/plan.md, meta/CHECKPOINT.md.
    discipline: one commit, `config: <one line>`, body names the unit, the DESIGN sections and the review item. "Fixed, not weakened" VERIFIED independently: I deleted the script the docs test creates and `test_the_integration_config_block_loads` went red at config.py:368 — the fixture really drives the refusal, it was not relaxed. The doctor/test_config/test_monitor fixtures likewise create or create-then-remove a real script.
    NOT PROVEN: (a) that a monitor_cmd resolves inside ops.repo — symlink and symlinked-directory escapes load clean, untested and not in the body's NOT PROVEN; (b) that doctor's run-time missing/non-executable ops-script rows still work — this commit removed their only coverage while the body implies they stay load-bearing; (c) the body's "green three consecutive runs (28.80s, 30.19s, 29.40s)" — I ran the gate twice, both green at 789 passed, so the count and greenness hold but not the three-run claim; (d) monitor.py's "is not a file" branch is unreachable-by-config now and untested.

### U3 — `e35a2e7`

    sha e35a2e7 — U3 "tests: every assertion compares against path-stripped text" (DESIGN §21 determinism bullet; review 4 should-fix 1, 2). Test-only: 15 files, all under tests/.
    test-first: PASS, reproduced independently. At parent b4dc0c0 all FOUR body claims go red: test_daemon.py:589 `--pids` (basetemp /tmp/pt-x/z--pids), test_playbook.py:347 `expected not in refusal` ("a send needs a prompt"), test_daemon.py:640 `"for 40m"`, test_daemon.py:661 `"no progress and no liveness"`. The review named only the first two; the two extras are real, not padding. Child green under all four plus "ntfy 403 handsd builder held 1340".
    test-first (audit): PASS. Appending `assert "world" not in out` to test_monitor.py fails BOTH audits; reverted. So a new unstripped assertion does fail the gate.
    gate: verbatim at e35a2e7 unmodified — `All checks passed!` / `794 passed in 30.00s` / `check: green`, exit 0. Re-run with `PYTEST_ADDOPTS='--basetemp="/tmp/pt-y/z--pids"'` — `794 passed in 41.50s` / `check: green`, exit 0. Four more crafted basetemps: 794 passed each. 5/5 green confirmed.
    design: conforms. `strip_paths` strips extras, tmp_path, basetemp, $HOME + `~/.hands` + `~/.hands/handsd.sock`, cwd, plus each resolved form, longest-first, prefix-only. Root guard is `len(parts) > 2`, so `/`, `/home`, `/tmp` survive — no vacuous strip found. Positive assertions whose left side is a call/subscript are deliberately left unstripped, so `assert str(script) in out` still bites. `203` helper uses across 13 files — body's count is exact.
    forbidden: none touched. `git show --stat` lists only tests/*; no DESIGN.md, meta/plan.md, meta/CHECKPOINT.md. One commit, correct `<area>: <line>` + body form, attribution present.
    commit discipline: no body claim contradicted by disk. 203/13, 794 passed, five basetemp values, four red instances, exempt-file reason — all verified.
    NOT PROVEN / holes:
      1. NOT_TEXT exempts by *source text*, not type. I added `status = "…"; assert "world" not in status` (same for `kinds`, `argv`) — BOTH audits pass silently. Today all three names really are dicts/lists, but a future string named `status` escapes the property entirely.
      2. The positive audit only fires when the left side is a str Constant or a Name. `assert f"wo{'r'}ld" in out` and `assert ("wo"+"rld") in out` are invisible to it (verified live). No such assertion exists today, so it is a future hole, not a live one.
      3. The `READS_THE_REPO` exemption (test_docs.py, test_bash_guard.py) is *declared*, not enforced — no test checks those files avoid run-chosen paths. I audited both by hand: sound today (test_docs.py takes `tmp_home` at :68 and runs subprocess at :214, but every assertion compares against repo text, a config object, or ROOT-relative strings). Nothing stops that from rotting.
      4. Minor: conftest docstring says "fewer than two components (`/`, `/home`)"; the code is `> 2`, i.e. fewer than three. Examples right, wording wrong. `test_strip_paths_never_strips_a_root_directory` checks only `/` and `/home`, not `/tmp`.
      5. I ran the plain gate once, not three times; the 3-run claim is consistent with what I saw but unreproduced at that count. Worktrees removed; main tree clean.

### U4 — `6d9664d`

    sha 6d9664d — U4 prompt delivery: one cap on both routes and on the wire (DESIGN §4 `send` row, §21; REVIEW-4 should-fix 3, 4, 5)
    test-first: PASS — reverting only cli.py, daemon.py, INTEGRATION.md, driver/CLAUDE.md to 6d9664d^ turns exactly the 10 tests this commit adds RED (9 in test_daemon.py, 1 in test_docs.py), incl. the literal regression `hands send --prompt-file …/cjk.txt failed: hands: [Errno 32] Broken pipe`; restored, tree clean.
    gate: `== ruff ==\nAll checks passed!` / `== pytest ==\n804 passed in 42.65s` / `== cli smoke ==` / `check: green`, exit 0.
    design: §4 says the client refuses "a missing, unreadable, non-regular, empty or over-10 MB file on either route (`--prompt-file` or `--stdin`), and the wire carries UTF-8 unescaped so the daemon's line room (cap plus one quarter) fits any accepted prompt". Those two halves contradict each other for escaping content, so §4 as written cannot be fully obeyed; measuring on the wire refuses an at-cap quote file that the first half's plain reading accepts — a real deviation, but the smallest one, and it makes the binding half true rather than approximately true. The builder was right to ship it AND file H-012 rather than stop: stopping would have left the exact broken pipe should-fix 3 demanded be fixed. All probes hold on the real CLI against a real handsd: 9 MiB CJK delivered (exit 0); at-cap quotes/NULs refused with both sizes (10485760 / 20971520 and 62914560); `--prompt-file` and `--stdin` refuse the same oversized bytes with the same message tail and exit 2; FIFO refused in 0.22 s, plus dir, socket, /dev/zero, all from `stat`; empty/whitespace/unreadable/missing/non-UTF-8 all exit 2; `hands --help` and INTEGRATION.md carry the exit-2 sentence. `_wire_bytes` is byte-exact vs `json.dumps(…, ensure_ascii=False)` over 4000 fuzzed strings and every codepoint 0–0x2FFF (0 mismatches) — no prompt-only escape trick beats the client check.
    design (hole): the claim that survives probing is only about the *prompt*. H-012 and the code comment both assert the leftover quarter "is the envelope's, which no `--file`-bearing command line can exceed" — that is FALSE. A near-cap prompt (10 MiB − 1 KiB, accepted) plus 16 `--file` args of backslashes (~1.9 MiB of argv, ARG_MAX 2 MiB here, which JSON doubles to ~3.9 MiB) makes a ~14.2 MiB line against a 13.1 MiB limit: `hands: [Errno 32] Broken pipe`, exit 1, nothing in the daemon log. Each half alone exits 0; only the combination fails. That is precisely the fault class should-fix 3 named, re-entered through the envelope, and INTEGRATION.md's new "anything the client accepts fits" is untrue as written.
    design (minor): under `PYTHONUTF8=1`, non-UTF-8 `--stdin` bytes become lone surrogates and die in `_wire_bytes` as `hands: 'utf-8' codec can't encode characters…` with exit 1, while the same bytes via `--prompt-file` give "not UTF-8 text" and exit 2 — the routes still disagree on the encoding refusal (the commit only claims size and emptiness parity, so this is unclaimed, not false).
    forbidden: none touched — the commit is docs/INTEGRATION.md, driver/CLAUDE.md, meta/findings/FINDINGS.md, src/hands/cli.py, src/hands/daemon.py, tests/test_daemon.py, tests/test_docs.py. No DESIGN.md, meta/plan.md or meta/CHECKPOINT.md. One commit, `cli: <one line>` + body naming unit, sections and review items, Co-Authored-By present.
    commit-body claims: every bullet I could check is true on disk; none overclaims. The overclaim lives in H-012's prose and in the two code comments (cli.py `_SHORT_ESCAPES` docstring, daemon.py `_LINE_LIMIT`) that say a command line cannot exceed 2.5 MiB.
    NOT PROVEN: I did not prove the cap is safe for the whole request — only for the prompt; the `--file` envelope overflow above is unguarded and untested at any layer. I did not check whether the daemon's `bad request: Separator is found, but chunk is longer than limit` reply is ever surfaced to a user (the client sees only the broken pipe). I did not exercise `--gate`, `keep` context, or a real `claude` binary; all runs used tests/fake_claude.py. Coverage of `_wire_bytes` beyond U+2FFF/U+E0FF/U+1F600/U+10FFFF is by argument (bytes ≥ 0x80 never need escaping), not by sweep.

### U5 — `06de18c`

    sha 06de18c — U5 Pipeline and config edges: stale `last_rule`, `pipeline.stop_suppressed`, two config edges (DESIGN §10, §11, §13, §21; REVIEW-4 should-fix 7, 8; H-011)
    test-first: PASS on all three concerns, each reverted separately and re-run. Rename (spool/daemon/docs reverted + playbook sed'd back to `stop.suppressed`) → 7 red (5 in test_playbook, 2 in test_wake incl. `test_for_stop_is_the_stop_kind_and_nothing_else`). Stale rule (cli.py reverted + `_shown_last_rule(book)` → `self.state.last_rule`) → 2 red (JSON + prose). Config (config.py reverted) → 3 red (`..._without_an_ops_repo_is_refused`, `..._unreachable_as_a_value_too`, `..._stored_stripped`); the two AST-scan tests stayed GREEN on the parent, so they pin a mechanism, not the fix.
    gate: `== ruff ==` / `All checks passed!` · `== pytest ==` / `812 passed in 45.26s` · `== cli smoke ==` / `check: green` · exit 0 (single run; the brief's three-consecutive-runs acceptance is for the mission tip, not proven here).
    design: conforms. H-011 acceptance holds — I ran `grep -rn 'stop\.suppressed' src tests docs driver` → rc 1, nothing; remaining hits are only historical meta/ prose (REVIEW-4, FINAL-REPORT-4, journal, the H-011 narrative above its Status line). Called directly: `resolve_kinds("stop") == {'stop'}`, `resolve_kinds("pipeline") == {'pipeline.resumed','pipeline.stop_suppressed'}`, `--for stop,held == {'stop','job.held'}`. EVENT_KINDS, `PlaybookEngine.stop`/`pause`, `Daemon._limit_stop`, docs/PLAYBOOK.md all renamed; PLAYBOOK.toml has no `on = "stop.suppressed"` rule and no fixture carries the old kind.
    design: should-fix 7 driven over a real in-process daemon + real CLI (6 states): same sha → no mark; different sha → `stale: true` in `--json` and `(stale: another playbook is loaded)` in the prose `last` line; state with no `last_rule_sha256` → back-filled from the record's own `playbook_sha256` (`from_dict`) and marked correctly; no playbook loaded at all → shown unmarked, `sha256: null`; no `last_rule` → `null` / "no rule has fired". Marked, not cleared: the record keeps every field and the state file on disk is unchanged after a stale display (verified by re-reading pipeline.json).
    design: should-fix 8 both edges hold. `[ops] monitor_cmd` with no `repo` refused at load (message names `[ops]`, `monitor_cmd`, `repo`, `omit`) *and* in `OpsConfig.__post_init__` (`OpsConfig(repo=None, monitor_cmd='w.sh')` raises). `[ops] repo` alone stays legal (`monitor_path=None`). Whitespace-only refused as blank everywhere I tried (`monitor_cmd`, `repo`, `ntfy_topic`, incl. NBSP); padded values strip and resolve (`'  w.sh  '` → `<repo>/w.sh`, `playbook.path`, `resume_line`, `allowed_roots`, `gates.patterns`).
    forbidden: none touched. `git show --stat 06de18c` = docs/PLAYBOOK.md, meta/findings/FINDINGS.md, src/hands/{cli,config,daemon,playbook,spool}.py, tests/{test_config,test_playbook,test_wake}.py. No DESIGN.md, no meta/plan.md, no meta/CHECKPOINT.md. The FINDINGS edit is a pure append of a dated Status line, as the body claims. Commit discipline is correct: one commit, `<area>: <one line>`, body names the unit + §§, co-author trailer present. I found no commit-body claim the disk contradicts.
    NOT PROVEN / holes: (1) **The AST scan is foolable.** I added a new `[extra]` section to the top-level `_check_keys` list and read `extra_t.get("sneaky2", "  pad  ")` raw, with no `_check_keys(extra_t, …)` — the whole of tests/test_config.py stayed green (76 passed). The scan skips the `scope == "config"` call by design, so the "every key `_check_keys` admits is read through a helper and no other" invariant only binds sections that already call `_check_keys`; a whole new section escapes both the scan and unknown-key refusal. (The in-section variant — key added to `_check_keys` + raw `.get` — *is* caught: `admitted - read` fires.)
    NOT PROVEN / holes: (2) **Stripping `_str_list` can widen a gate.** `gates.patterns` are case-sensitive substrings (gates.py:127), so a deliberate trailing space (`"rm "` to avoid `rmdir`) is now silently stripped to `"rm"`. Fail-safe direction (more gating, never less) but it is a case where padding was meaningful and no test or refusal mentions it.
    NOT PROVEN / holes: (3) A state file whose `last_rule` carries no `playbook_sha256` at all is marked `stale: true` even when the loaded playbook *is* the one it fired under — unprovable-vs-false-positive, undocumented, untested. (4) Nothing outside pytest/my harness ran: no installed build, no live driver, so the `--for stop` non-wake and the stale display are unwitnessed in a real session. (5) `_shown_last_rule` is display-only — `hands status` and any other consumer of `state.last_rule` still show the stale record unmarked; I did not audit those call sites.

### U6 — `53bb986`

    sha 53bb986 — U6 daemon memory: the runner writes stream-json to <job>.stream.jsonl as it arrives, never to memory (DESIGN §21 daemon-memory bullet, with §2/§6/§7)
    audit-claim: TRUE at 53bb986^ — daemon `_capture` already wrote+flushed each line to the file (daemon.py:395/461-470); no list of events exists in runner/daemon/api at the parent (runner keeps only `_Parsed` last result and stderr trimmed to 50). The unbounded readers are real: `Api.tail` did `path.read_text()` on the whole transcript per call (api.py:383) and `Api.log` at offset 0 still does. So U6 is a reader fix + a writer relocation, not the bug §21 implies; the 959 MB is explained plausibly, not proven, and the report says so.
    test-first: PASS — with only src/hands/{api,daemon,runner,spool}.py reverted to the parent: 3 failed, 45 passed in tests/test_runner.py (AttributeError `Spool.stream_path`), and tests/test_library.py fails collection (ImportError `MAX_TAIL_ENTRIES`), blocking its 3 new tail tests. Restored clean.
    gate: "== ruff == All checks passed! == pytest == 818 passed in 54.07s == cli smoke == check: green", exit 0 (matches the report's 818).
    design: CONFORMS. One writer only (`spool.stream_path`, grep-confirmed); flushed per line and visible mid-run (test_runner polls the file while the job runs; log -f test sees `init` live). Measured: tracemalloc peak during a full run is flat at ~492 KB for 2 000 vs 200 000 events (16.7 MB file) — nothing per-event, asyncio buffers included. `tail_entries` probed at every boundary: empty→[], missing→OSError→ApiError, short file, incomplete last line (returns the partial, same as before), non-JSON line, blank lines, exact-window file, 5000 entries→capped at 1000 — all correct; peak 272 KB vs 139.8 MB for the old read_text on a 64 MB transcript, identical answer. `on_stream_line`/`_streams`/`_capture` have no remaining callers anywhere.
    forbidden: none touched — the commit is meta/findings/FINDINGS.md + src/hands/{api,daemon,runner,spool}.py + tests/{fake_claude,test_library,test_runner}.py. DESIGN.md, meta/plan.md, meta/CHECKPOINT.md untouched. One commit, `<area>: <one line>` + unit/sections body.
    NOT PROVEN / holes: (1) body says "no answer a caller sees today changes" — contradicted by its own new test: `-n 0` used to mean "every entry" and now returns at most 1000, as does any `-n > 1000`; DESIGN §4 says "last n transcript entries" with no cap. (2) A transcript entry wider than 4 MiB makes `tail` return `[]` silently, with no marker that anything was dropped. (3) "retained() reports the length of everything the runner holds" is narrower than it reads: it counts the six per-job containers on the object, not the in-flight `_Parsed.result`, `stderr_lines`, or the 11 MiB asyncio reader limit (my probe shows these bounded, but they are unreported); `last_argv` is reported yet never evicted — one argv list per job for the daemon's life. (4) Untouched daemon-side growth outside §21's wording: `monitor.BlockBuffer._lines` accumulates an ops script's output until a blank line, `Notifier.queued` is unbounded during quiet hours, `Api.log` at offset 0 (H-013, filed and honest), `spool.events()`/`list_jobs()` read whole files per call. (5) The 959 MB itself: still unmeasured — no RSS before/after, so the causal story stays unproven, exactly as the body and report state.

### U7 — `ffa4c65`

    sha ffa4c65 — U7 No background tasks in role sessions: PreToolUse Bash hook + settings + doc rule (DESIGN §21 last bullet, §2)
    test-first: pass (as far as a single-commit unit allows). Deleting the two new `.claude/` files and reverting CLAUDE.md/docs/INTEGRATION.md to `ffa4c65^`: `tests/test_no_background.py` RED at collection (FileNotFoundError loading the hook, 0 of its ~110 params run), `tests/test_docs.py` 1 failed (`test_the_integration_doc_installs_the_no_background_hook_in_every_driven_repo`). Restored clean. Temporal ordering is unprovable from history (one commit).
    gate: `./scripts/check` at the unmodified commit — `== ruff ==` / `All checks passed!`, `== pytest ==` / `929 passed in 54.58s`, `== cli smoke ==` / `check: green`, exit 0. Selftest: `selftest: 50/50 ok`, exit 0. Matches the body's "929 passed" (I ran once, not three times).
    design: conforms on the specified surface. Driving `main()` as a subprocess: all 26 must-pass probes allowed, zero over-refusal (`&&`, `2>&1`, `&>`, `|&`, `1>&2`, quoted `&`, unquoted URL `&`, `sed 's/&/x/'`, `rg 'a & b'`, git/uv/pytest, every `scripts/check` line, `wait`, `jobs`). Blocks confirmed: `run_in_background` (bool/`"true"`/`"TRUE"`/1), `NOHUP=1 nohup x`, `setsid --fork`, `cmd & disown`, `disown -a`, trailing `&` with trailing spaces/newline, `( cmd & )`, `{ cmd & }`, `x=1 cmd &`, `&` after a `#` comment, `nohup` inside `$( )` and backticks, unbalanced quotes (fails closed, exit 2). `.claude/settings.json` is valid JSON, matcher is `PreToolUse`/`Bash`, command is `python3 "$CLAUDE_PROJECT_DIR"/.claude/hooks/no_background.py` — works from any cwd, and with `CLAUDE_PROJECT_DIR` unset python3 itself exits 2, so it fails closed (blocks everything) rather than open.
    design (bypasses): three real ones NOT admitted anywhere — (1) `/usr/bin/nohup ./x` allowed (token match only; `NOHUP=1 nohup x` is caught but a path-qualified daemonizer is not); (2) `cmd &# comment` allowed — I verified bash really does background it (`[1]+ Running sleep 0.2 &`), because `#` is not in the `");\n"`+whitespace after-set; (3) an inner shell in quotes: `bash -c 'cmd &'`, `sh -c "nohup ./x"`, `eval 'sleep 9 &'` all allowed, since quoted text is blanked. Uppercase `NOHUP ./x` allowed is correct (shell is case-sensitive). `screen -dmS`, `tmux new -d`, `at now`, `systemd-run`, `python -c os.fork()` are all allowed — confirmed, and meta/FINAL-REPORT-5.md NOT PROVEN item 3 admits exactly those.
    design (malformed): empty/whitespace/non-JSON stdin → exit 2 with a reason (intended, stated in the body). JSON that is a list/string/null, missing `tool_name`/`tool_input`, `tool_input: null`, non-Bash tool, missing command → exit 0. Hole: `tool_input` a list, or `command` a non-string (e.g. `123`), raises an uncaught `AttributeError`/`TypeError` → traceback on stderr, **exit 1**, which Claude Code treats as non-blocking — the only input shape that fails *open*. Not reachable from the real Bash tool, but it contradicts the "fail closed on input it cannot parse" stance. `run_in_background: ["true"]` also allowed. 200k-char commands handled correctly both ways.
    docs: CLAUDE.md has exactly one background bullet naming `run_in_background`/`nohup`/`foreground`/`timeout`; `docs/INTEGRATION.md` has the "No background tasks in a role session (§21)" section with the install recipe. Pinning is split: `tests/test_docs.py` pins INTEGRATION.md only; CLAUDE.md is pinned by `tests/test_no_background.py::test_claude_md_states_the_rule`. The commit body's "…pinned by tests/test_docs.py" reads as covering both — minor imprecision, the disk does pin both, just elsewhere.
    forbidden: none touched. `git show --stat` = 7 files: `.claude/hooks/no_background.py`, `.claude/settings.json`, `CLAUDE.md`, `docs/INTEGRATION.md`, `tests/test_determinism.py`, `tests/test_docs.py`, `tests/test_no_background.py`. No `DESIGN.md`, no `meta/`. Commit discipline good: one commit, `hooks: <one line>`, body names the unit and §21/§2.
    NOT PROVEN: (a) the hook has never run as a real Claude Code hook — exit-2 semantics are a subprocess contract only (the report says so); (b) `/usr/bin/nohup`, `cmd &#`, and `bash -c '… &'`/`eval` bypasses are real and are absent from the report's NOT PROVEN list — that list is therefore incomplete, not wrong; (c) the non-string-`command` exit-1 fail-open path is untested and undocumented; (d) no test proves any other driven repo installed the files (report item 4); (e) I ran the gate once, not the body's three consecutive runs.
