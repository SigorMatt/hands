# REVIEW-4 — cold review of mission 4 (blockers and pipeline state)

Aux session, no mission context. Base `796e5ae` → `origin/main` `edf0bc2`.
Protocol: `meta/REVIEW-PROTOCOL.md`. Six unit commits (U1, U2, U3, U4 and U5's
two), one sub-agent each in its own detached worktree; the eight `meta:`
bookkeeping commits skipped, except that U0's two corrections — the only
product of a `meta:` commit this mission's acceptance names — were checked
here, by hand.

    VERDICT: review mission 4 blockers=2 should-fix=8

Read: `DESIGN.md` §20 (with §4, §10, §12, §13), `meta/BUILDER-4-PROMPT.md`,
`meta/FINAL-REPORT-4.md`, `meta/findings/FINDINGS.md`,
`git log --oneline 796e5ae..origin/main`.

## Blockers

1. **`FINAL-REPORT-4.md` §3 item 15 makes a safety claim about the guard that
   the guard contradicts.** It reads: "The guard now refuses `find`'s exec
   flags outright, **which was the one arbitrary-exec vector left inside the
   allow list**." Executed against the tip's `driver/hooks/bash_guard.py`
   (`check()` returning `None` = allowed):

       git -c diff.external='touch /tmp/gprobe-pwned' diff --ext-diff  -> None
       git -c core.pager=touch log                                     -> None
       git diff --output=/tmp/x                                        -> None
       git show HEAD --output=/tmp/x                                   -> None
       find . -fprint /tmp/out   (also -fprintf, -fls)                 -> None

   The first is not hypothetical: run in a throwaway repo it created
   `/tmp/gprobe-pwned` (`-rw-rw-r-- 1 msi msi 0 Sep 12 02:20`). `git -c` sets
   a config key for one invocation, and `diff.external` / `core.pager` are
   config keys whose values git executes — so a first-level subcommand that is
   on the allowlist (`diff`, `log`, `show`) runs an arbitrary command, exactly
   the shape blocker 1 of review 3 was about, reached by a different wrapper.
   `--output=` and `find -fprint` are the write half: they create a file at any
   path, which is what `driver/CLAUDE.md` rule 1 and DESIGN §12 say the driver
   can never do. Worse for one of them: `git diff --output=/tmp/x` also matches
   `driver/settings.json`'s `"Bash(git diff:*)"` allow rule, so the human is
   not even asked — both layers pass it. `find -fprint` and `git -c …` do not
   match an allow rule, so they would prompt.
   None of these are regressions — the old guard allowed them too — and the
   fix the mission was asked for (allowlist on every `git` token, `find`'s exec
   flags forbidden) is complete and proven. What is wrong is the sentence: it
   tells the architect the arbitrary-exec surface is now empty when it is not,
   and it is in the section whose whole job is to say what is not proven. Fix
   shape, either: refuse `-c`/`--config-env` and `--output`/`--ext-diff` on a
   git token and `find`'s `-fprint*`/`-fls` with the exec flags (a few lines,
   and the adversarial table is the place to pin them), or correct the claim to
   "`find -exec` is closed; `git -c <key>=<cmd>` and `--output=` are the
   arbitrary-exec and write vectors still inside the allow list, and the
   general wrapper question is the architect's." One of those, not neither.

2. **U4's own test claims a state is unreachable that is reachable, and it is
   review 3 should-fix 5's exact end state.**
   `tests/test_config.py:381-390`,
   `test_an_empty_monitor_cmd_cannot_make_the_ops_repo_the_monitor`, docstring:
   "`OpsConfig(repo=Path('/x'), monitor_cmd="").monitor_path` was `/x` — a
   directory as the monitor script. **No config can reach that state now.**"
   The blank is indeed refused, and that closes the item as filed. But
   `OpsConfig.monitor_path` is still `self.repo / self.monitor_cmd`
   (`src/hands/config.py:117-121`) with no check on the shape of the value, so:

       $ uv run python -c "…OpsConfig(repo=Path('/x/ops'), monitor_cmd=v).monitor_path"
       '.'    -> /x/ops          # the ops repo directory: the state the test says is gone
       './'   -> /x/ops
       ' x '  -> '/x/ops/ x '    # values are blank-checked, then stored unstripped

   `monitor_cmd = "."` loads clean, `MonitorSource` flips to `"ops"`
   (`src/hands/monitor.py:312`), `hands status` reports a directory as the
   deciding script and builder jobs go unwatched behind "is not a file"
   (`monitor.py:559`) — review 3 should-fix 5 verbatim, one input over. The
   probability a human writes `"."` is low and the severity of the sentence is
   not: this is the mission that was called to account for claims that do not
   survive checking, and `meta/FINAL-REPORT-4.md` §3 does not carry it. Fix
   shape: refuse a `monitor_cmd` that is not a relative file path (or make
   `monitor_path` require `is_file()`), or narrow the docstring to the blank it
   actually proves — and say the rest in NOT PROVEN.

## Should-fix

1. **The fault class blocker 2 of review 3 named is still live in two negative
   assertions, one of them U2's own new test.** Both were driven red at
   `667ea52` with a crafted `--basetemp`: `tests/test_daemon.py:509`
   (`assert "--pids" not in out`, on the line below the one U2 pinned at 508 —
   red under `--basetemp=/tmp/ptY/z--pids`, the `handsd.sock` path satisfying
   it) and `tests/test_playbook.py:345`, inside
   `test_every_bad_playbook_is_pinned_to_a_refusal_only_it_makes` itself
   (`assert expected not in refusal`, compared against refusals that embed
   `tmp_path` — red under `--basetemp="/tmp/ptX/a send needs a prompt"`). Both
   need a crafted path, not a run counter, so the gate is deterministic in
   practice and blocker 2 is closed; but the unit's own invariant test carries
   the defect it was written to stamp out. Strip the path prefix before
   comparing.
2. **The false-green half of that class is untouched, in files the audit did
   not open.** `FINAL-REPORT-4.md` §3 item 6 discloses the scope honestly ("the
   other eleven test files were not read"), and the survey found what that
   implies: positive short-substring assertions a tmpdir path can satisfy
   vacuously — `tests/test_wake.py:662` (`"200" in out`),
   `tests/test_library.py:94` (`"2d" in err`), `tests/test_doctor.py:122`
   (`"0 failed"`), plus one-word positives at `test_daemon.py:74,200`,
   `test_library.py:147,148,322`, `test_gates.py:357`. These cannot make the
   gate red, only falsely green, which is why no run will ever find them.
3. **`--prompt-file`'s cap and the socket's line limit are different limits, so
   a file under the cap can still fail away from the path the human named.**
   The client refuses on raw `st_size` against `MAX_PROMPT_BYTES`
   (`src/hands/cli.py:793-800`) while the daemon's reader caps the
   **JSON-escaped** line at `MAX_PROMPT_BYTES + 1 MiB`
   (`src/hands/daemon.py:63`) and the client writes `json.dumps(request)` with
   `ensure_ascii` at its default (`cli.py:99`) — so every 3-byte CJK character
   becomes 6 bytes on the wire. A 9 MiB CJK file (under the cap) and a 10 MiB
   file of `"` or NULs (at the cap) both die at `hands: [Errno 32] Broken
   pipe`, with nothing in the daemon log: review 3 should-fix 9's own words,
   "fails somewhere other than at the path the human named". The at-cap test
   passes because it uses `b"x"`, the one content that does not inflate. Cap
   the escaped length, or raise the daemon's room, or say the cap is bytes of
   ASCII. Same file, same seam: `--stdin` gets no client-side check at all
   (`cli.py:833`), so the identical oversized prompt refuses at the path on one
   route and at the daemon on the other.
4. **A non-regular prompt file hangs the client forever.** `cli.py:793` trusts
   `st_size` and never checks `S_ISREG`, so a FIFO reports 0 bytes, passes all
   four refusals, and `path.read_bytes()` (`cli.py:803`) blocks with no writer.
   Confirmed at the tip: `timeout 6 … _read_prompt_file('/tmp/fifoprobe')` →
   exit 124. With a writer it sends any size, cap or no cap. One `S_ISREG`
   test, and a case in the refusal table.
5. **Exit 2 is now two things and the docs say it is one.**
   `docs/INTEGRATION.md:121` still reads "It is the one command that does this
   — every other command exits 1 with the message alone", which `d348d07` made
   false; `docs/INTEGRATION.md:222` still says `--prompt-file` refusals exit
   "non-zero"; `driver/CLAUDE.md:52` tells the driver "Exit code 2 is a
   timeout, not an event: re-arm and say nothing" — correct for rule 8's `hands
   wait`, and rule 6 (the `--prompt-file` rule, `driver/CLAUDE.md:41-46`) is
   exactly where the driver will now meet a 2 that is not a timeout. The
   collision is machine-inert today (`TIMEOUT_CODE` is raised only inside the
   `wait` handler, `src/hands/api.py:193,203`; nothing in `src/` or `scripts/`
   reads the CLI's exit code) and `tests/test_daemon.py:354-355` pins the two
   constants equal — the cost is entirely on the one reader that is an LLM. One
   clause in rule 6 and a corrected line in `INTEGRATION.md`. (`FINAL-REPORT-4`
   §6 raises the design half of this with the architect, which is right; the
   two doc lines are the builder's half.)
6. **`ADVERSARIAL`'s independence is real but not as clean as claimed, and
   nothing keeps it.** The table disagreed with the old guard 14 times, which
   is the substance and it holds. But 4 of its 22 allowed cases are
   byte-identical to `SELFTEST` rows — `git -C ./repo rev-parse
   8448b6f^{commit}`, `git log --grep=commit -5`, `git -C ./repo show
   origin/main:meta/CHECKPOINT.md`, `git -C ./repo log --oneline --grep=push
   -20` — so "composed … before the guard file was opened"
   (`FINAL-REPORT-4.md` §1 U1) is not literally credible; three of the four are
   quoted verbatim in `REVIEW-3.md:363`, which the sub-agent brief *requires*
   it to read, so the likely route is the review, not the guard. The keeper is
   what is missing: `test_the_adversarial_table_is_independent_of_the_guard`
   asserts only `>= 20 / >= 10 / >= 10`, so nothing would notice the table
   drifting into a copy of the guard's. Assert the intersection stays small, or
   name the four as deliberate overlap.
7. **`hands pipeline` can print a `last_rule` from a playbook that is no longer
   the playbook.** The sha comparison that clears `last_rule` lives in `_load`
   (`src/hands/playbook.py:653-658`), but `pipeline()`'s lazy load bypasses it
   (`playbook.py:1029-1033`), so on a restarted daemon that has not started a
   job the command prints the new file's sha next to the old file's rule —
   demonstrated: `rules: 1`, `sha fa9528b8`, `last_rule.rule = 0` with
   `playbook_sha256 6df1445d`. Self-diagnosable (the record carries its own
   sha) and cleared by the next job start. §10 (c) is met; this is the display.
8. **Two smaller config edges U4 left, both the same shape as the one it
   fixed.** `[ops] monitor_cmd` with no `ops.repo` loads and is silently
   ignored (`monitor_path` → `None`) while `config.py:64`'s own comment asserts
   §5 means "both keys, or neither" and the refusal text promises the script
   will be used; and every accepted value is stored unstripped, so
   `playbook.path = " P.toml "` and `gates.patterns = [" x "]` keep their
   padding after passing a blank check that used `strip()`. Also unpinned
   (`FINAL-REPORT-4.md` §3 item 11 names the doctor branch): `hands doctor` with
   `project = None` — verified by hand here, it does not crash (`project
   <project>`, `"config": ""`, exit 1) — and the fact that a future key added
   with a raw `table.get(...)` still skips the `blank=` mechanism, since
   `OPTIONAL_STRING_KEYS` is hand-maintained and nothing asserts helper
   coverage.

## Notes

**The gate.** Green at the tip here, three consecutive runs in this working
tree: `All checks passed!` / `726 passed in 38.79s, 38.48s, 39.4s` / `check:
green`, exit 0 each. Every unit commit is green at its own sha on the runs the
sub-agents made, and the per-unit counts `FINAL-REPORT-4.md` §2 claims are
exact to the number: 681, 682, 692, 719, 725, 726. `bash_guard.py --selftest`
→ `selftest: 65/65 ok`, exit 0. The full suite also stays green under a
hostile `--basetemp` (`/tmp/pt-hostile-40-stop-playbook/pytest-1340`), which is
the natural-counter class review 3's blocker 2 was about.

**Test-first held everywhere it could.** Each product unit's tests went red
with only that unit's non-test files reverted: U1 15 failed (the 14 adversarial
cases + the `MultiEdit` docs test), U3 12 failed across all four parts of §10,
U4 25 of 84, U5a 5 of 6, U5b 7 once the reverted `EXIT_REFUSED` import was
shimmed (without the shim the module is uncollectable, which masks the red
rather than proving it — worth knowing for the next unit that moves a
constant). The cases that stayed green with the product reverted are
anti-over-refusal guards, correctly so, and each sub-agent named them.
U2 is test-only, so the load-bearing proof is the flake instead: red at the
parent under `--basetemp=/tmp/pt-40/pytest-1340`, green at `667ea52`, and the
second instance (`test_status_says_stall_detection_is_off_at_zero_minutes`)
reproduced red at the parent too. Both reproduced independently here.

**Review 3's three blockers are closed, and I checked the closures, not the
claims.** Blocker 1: the tip's 62-case table run against `git show
ecdb0f3:driver/hooks/bash_guard.py` fails exactly 14 times, the set matching
the report's list item for item, and 0 times against the tip; the allowlist now
reaches a `git` token behind `;`, `|`, newline, `&&`, `( )`, `{ }`, `$( )`,
backticks, `-C`, `--git-dir=`, a `GIT_DIR=` assignment and `/usr/bin/xargs`.
Blocker 2: above. Blocker 3: the dated correction is appended to
`FINAL-REPORT-3.md` §3 with the original text untouched (`git diff
796e5ae:… HEAD:…` is +23 lines, -0), and its facts are re-run, not re-copied —
I re-ran them today and they still hold: installed `hands 0.1.0` at
`~/.local/share/uv/tools/hands/…/hands/` (mtime `Sep 11 23:35`) has m2's
`ORIGINS = frozenset({"driver", "playbook", "cli", "limit"})`, `grep -c
prompt-file cli.py` → `0` and no `stop.suppressed`/`UNPAUSE_ORIGINS` in
`playbook.py`. So `FINAL-REPORT-4.md` §3 item 1 is true and is now **two**
missions of code deep, not one.

**Acceptance, independently checked.** Two guard tables, `SELFTEST` (65) and
`ADVERSARIAL` (62: 40 block, 22 allow), the second ≥20 with both verdicts;
`grep -rn MUTATING_GIT_SUBCOMMANDS` outside `meta/` → nothing;
`driver/settings.json` denies `Edit`, `Write`, `MultiEdit`, `NotebookEdit`;
`grep -rn metacharacters driver/` → nothing; `driver/CLAUDE.md` rule 6 is
byte-verbatim DESIGN §12 rule 6 (re-diffed independently); H-010 carries U0's
appended amendment and U1's closing line; H-011 is filed. No unit commit
touches `DESIGN.md`, `meta/plan.md` or `meta/CHECKPOINT.md` — verified for all
fourteen commits in the range, and `DESIGN.md` is untouched across the whole
of it.

**On the counts in U1's commit body.** It says the adversarial table has 61
cases and that 47 were green at `ecdb0f3`; it is 62 and 48. `FINAL-REPORT-4.md`
§1 U1 corrects the first and states the second correctly, and the journal line
says 62. Recording the slip in the report rather than amending pushed history
is the right call and the reason it costs a note here instead of an item.

**On U5 landing as two commits.** The sub-agent shipped the four refusals at
exit **1** — a knowing deviation from a brief that spells out 2 — reported it
with its reasoning, and the builder ruled for the brief in `d348d07`. Both
halves are green and load-bearing at their own shas, the departure is recorded
in the report and the checkpoint, and the outcome is the brief's. Worth one
sentence for the pattern only: `meta/CHECKPOINT.md`'s "Done means … one commit,
pushed" was the standing line for that unit and is not itself flagged as unmet.

**§3 NOT PROVEN holds up, item by item, with one inaccuracy and one falsehood.**
Fifteen items; the ones checkable from disk are accurate — item 3 (`main()`'s
stdin/exit-2 wiring has no test: true, `tests/test_bash_guard.py` never imports
`main`), item 5 (the fail-closed `~/git` residue), items 7-10 (each named
exactly what the U3 sub-agent then found by execution), item 11, item 14 (`mypy`
is still not in `scripts/check`: true, the gate is `uv sync`, ruff, pytest, two
`--help` calls). Item 13's substance is right and its wording is not: the code
means 10 MiB and DESIGN §2/§4 say 10 MB, but the client's help text does not
say "10 MB" — it interpolates the constant (`src/hands/cli.py:176-177`), so it
says `10485760` and the exit code. Item 15 is blocker 1. Anticipating a finding
in NOT PROVEN and then having the reviewer confirm it (items 7-10, and item 6
which is should-fix 2 here) is the section working as designed.

**What the mission got right that is worth keeping.** The adversarial table is
the review's should-fix 1 answered in substance and not in letter: it is the
only artifact in the repo that could have caught blocker 1, and it did, 14
times, against the old guard. U2 treated "the gate flaked" as an audit of 246
assertions rather than as one line to patch, found a second live instance
itself, and then wrote the invariant test standing behind the 19 pins it could
not demonstrate red. U3's five gate cases each exist, and the `max_resumes`
stop is proven through the real daemon wiring rather than through the engine in
isolation. U4 enumerated §13 instead of the two keys the review named, and the
required `blank=` keyword is a mechanism rather than a fix — a new key cannot
silently skip the check, which is precisely how `monitor_cmd` skipped mission
3's. Both remaining blockers are sentences, not code.

## Per-commit verdicts

The sub-agents' reports, verbatim.

    sha 935a275 — U1 guard scope, DESIGN §12 (driver kit / settings deny) + §20 (guard scope, adversarial table, MultiEdit)
    1 identity: claim matches diff. 5 files, no scope creep: guard applies ALLOWED_GIT_SUBCOMMANDS to every `git` token via new invocations()/git_violation(); FIND_ACTION_FLAGS added; MUTATING_GIT_SUBCOMMANDS + first-level-only check deleted; settings.json re-adds MultiEdit; docstring updated; FINDINGS H-010 gets an appended Status line (no rewrite). §20 names -exec/-execdir/-ok/-delete; commit also forbids -okdir (superset, stricter — fine).
    2 test-first: load-bearing. Reverting only driver/ to 8268539 (whose guard logic is byte-identical to ecdb0f3, differing only by 3 SELFTEST rows): 15 failed, 126 passed → restored: 141 passed. Failures = the 14 named adversarial cases + test_docs::test_the_driver_denies_every_writing_tool. ADVERSARIAL is 62 cases (40 block / 22 allow), not 61 as the body says, and "the other 47 were green" should be 48 — an off-by-one miscount in the body, not a behaviour error. Not trivially guard-satisfiable: it disagreed with the old guard 14 times. Independence is imperfect: 4 of the 22 allowed cases are verbatim SELFTEST strings (incl. `git -C ./repo rev-parse 8448b6f^{commit}`), so "written without reading SELFTEST" is not literally credible; the meta-test only asserts >=20/>=10/>=10, so it would not catch drift toward SELFTEST.
    3 gate: `./scripts/check` green 3/3 consecutive runs at 935a275 — ruff `All checks passed!`, `681 passed in 32.80s / 37.69s / 31.06s`, `check: green`. `--selftest` prints `selftest: 65/65 ok`, exit 0.
    4 conformance: allowlist now applied to every `git` token (verified: `ls; git push`, `ls | git push`, newline, `&&`, `( git push )`, `{ git push; }`, `$(...)`/backticks in double quotes, `git -C /x push`, `git --git-dir=... commit`, `GIT_DIR=x git push`, `/usr/bin/xargs git push` all blocked). All five find flags forbidden. `grep -rn MUTATING_GIT_SUBCOMMANDS` outside meta/: no hits (survives only in meta/ prose, as the body says). settings.json denies Edit/Write/MultiEdit/NotebookEdit. DESIGN.md, meta/plan.md, meta/CHECKPOINT.md untouched.
    5 claims: verified by execution. Tip's 62-case table against `git show ecdb0f3:driver/hooks/bash_guard.py` → exactly 14 failures, all allow-but-must-block, and the set matches the body's list item-for-item (9 second-level git writes behind -exec, -execdir twice, -okdir, 2 -delete). Same table against the tip guard → 0 failures. `find . -ok rm -rf build \;` was already blocked at ecdb0f3 by the rm pattern, so it is correctly absent from the 14.
    NOT PROVEN / holes the NEW guard ALLOWS against §12's "never writes, never mutates a repo" (all also allowed by the old guard, so pre-existing, not regressions — but the find ones sit inside the surface U1 claims to close "whatever the payload looks like"): `find . -fprint /tmp/out` (also -fprintf, -fls) — confirmed live, wrote 1170 bytes; `git -c diff.external='touch /tmp/x' diff --ext-diff` — confirmed live, arbitrary command execution, the quoted payload is stripped as "text" by design; `git diff --output=/tmp/x` and `git show HEAD --output=/tmp/x` — confirmed live, wrote 83 bytes; `git branch newbranch` / `git branch -f main origin/main` — confirmed live ref creation, since only -d/-D/-m/-M are in FORBIDDEN_GIT_FLAGS; `git remote prune origin`, `git remote set-head`, `git fetch --force origin main:main`. Also still carried from the checkpoint: the guard has never run as a real PreToolUse hook and `main()`'s stdin/exit-2 wiring has no test — untouched by U1.

    sha 667ea52 — U2 "tests: pin the assertions a tmpdir path could satisfy" (a deterministic gate)
    1 identity: only `tests/test_daemon.py` (+18/-7) and `tests/test_playbook.py` (+117/-36); `git show --name-only` lists nothing else — no `src/`, no `driver/`. Claim of test-side-only holds.
    2 load-bearing: reproduced independently. Parent 935a275 + review's command = `1 failed` at test_daemon.py:556 (`'40' is contained here: /tmp/pt-40/pytest-1340/...watch_monitor.sh`); same command at 667ea52 = `1 passed`. Second claimed instance also red at parent (`--basetemp=.../pytest-1340m-off-on-send` → `'0m' ... handsd.sock`), green here.
    2b MISSED, triggered red: `tests/test_daemon.py:509 assert "--pids" not in out` — same fault class, in the audited file, on the line directly below the one U2 pinned (508). Under `--basetemp=/tmp/ptY/z--pids` `test_status_says_queue_depth_is_capacity_and_what_the_monitor_sees` goes RED (matched `handsd.sock` path). Crafted-only (needs a literal `--pids` in the path), not a natural-counter hit.
    2c MISSED, triggered red: the unit's own new test repeats the fault — `tests/test_playbook.py:345 assert expected not in refusal` compares against refusals that embed `tmp_path`. Under `--basetemp="/tmp/ptX/a send needs a prompt"` it goes RED ("send with no prompt's expectation also matches not toml"). Fix would be to strip the path prefix before comparing.
    2d survey of the 12 remaining `not in` asserts repo-wide: no digit-bearing negative assertion on path-bearing output survives anywhere, so the *natural* (run-counter) red class is closed. `test_wake.py:741` and `test_library.py:150` did NOT go red under crafted `"ntfy "` / `"FAKE:"` basetemps. What does survive in the 11 unaudited files is the false-GREEN half: positive short/digit substrings a tmpdir path can satisfy vacuously — `test_wake.py:662 "200" in out`, `test_library.py:94 "2d" in err`, `test_doctor.py:122 "0 failed"`, plus one-word positives (`test_daemon.py:74,200`, `test_library.py:147,148,322`, `test_gates.py:357`). Unit did not touch or mention these.
    3 gate: `./scripts/check` run 3x at 667ea52, all green, verbatim `682 passed in 37.63s / 37.25s / 40.42s`, `All checks passed!`, `check: green`, exit 0 each. (I ran 3, not 5; the 5/5 claim is consistent with what I saw but unreproduced at that count.)
    4 conformance: `DESIGN.md`, `meta/plan.md`, `meta/CHECKPOINT.md` untouched. `test_every_bad_playbook_is_pinned_to_a_refusal_only_it_makes` exists and bites twice: loosening `"a notify needs a message"` → `"then must be one of"` fails the own-refusal leg; loosening `"unknown key(s) in the playbook: rules"` → `"unknown key"` fails the cross-case leg ("also matches unknown rule key"). Both mutations reverted; worktree left clean.
    5 claims: 246 asserts = exact (`grep -c "assert "` → 111 + 135). 30 changed = reconstructs exactly (19 BAD_PLAYBOOKS + 3 STOPS + 5 test_daemon assert sites + 3 test_playbook assert sites). 681→682 collected across parent→commit = exactly the one test added; parent suite green at 681. Second live instance reproduced verbatim. `"handsd" in err` / `"playbook" in stop_reason` path-satisfaction claims are true by inspection.
    NOT PROVEN: 5/5 (I ran 3/3); the unit's audit stopped at the two named files while the false-green half of the same fault class is untouched in 11 others; and the fault class is still live in two negative asserts at this commit (`test_daemon.py:509`, `test_playbook.py:345` — the new pin test itself), both of which I drove red with a crafted `--basetemp`.

    sha c108bfe — U3 pipeline state, DESIGN §10 ("Stop → resume cycle") + §20
    1 identity: body matches diff exactly — `UNPAUSE_ORIGINS={"cli"}` checked in `on_job_start` (playbook.py:629), `on_send` deleted (api.py:145-148), one `stop()` with `write_event` gone (playbook.py:952-968), `last_rule_sha256` on `PipelineState`, `limits.stop` no longer writes the event (limits.py:429-441) and reaches the engine via `daemon.py:451`. Nothing forbidden touched (no DESIGN.md, no meta/); docs/PLAYBOOK.md updated to match.
    2 test-first: `git checkout 7ccc374 -- src/` → **12 failed, 172 passed** across test_playbook/test_limits/test_wake. Red covers all four brief parts: (a) `test_a_cli_job_un_pauses_the_pipeline_when_it_starts`, `test_a_send_filed_while_stopped_un_pauses_only_when_its_job_starts` (real daemon, gate→approve); (b) `test_a_stop_over_a_stop_…suppressed`, `test_a_limit_stop_over_a_rule_stop_keeps_the_first_reason`, `test_pausing_an_already_paused_…`, `test_resumes_stop_after_max_resumes…`; (c) `test_last_rule_is_cleared_when_a_playbook_with_another_sha_loads`, `test_a_state_file_from_an_older_build…`; (d) `test_a_resume_files_a_pipeline_resumed_event`. Green-either-way (guards, not load-bearing, correctly so): `test_a_job_the_pipeline_started_itself_never_clears_a_stop[playbook|limit|driver]`, `test_a_limit_stop_with_no_stop_over_it_still_files_its_event_and_notifies`, `test_last_rule_survives_a_restart_under_the_same_playbook`. No claimed behaviour is untested.
    3 gate: `./scripts/check` → `== ruff ==  All checks passed!` / `== pytest ==  692 passed in 32.33s` / `== cli smoke ==` / `check: green` (one run; body claims three).
    4 conformance: (a) correct — the only un-pause seam is `on_job_start`, called in `Daemon._run` *after* the `state != "queued"` check (daemon.py:384-399), so filed/held/queued cannot clear a stop and a queued job clears only at dequeue; (b) correct and verified over the real daemon: `max_resumes` goes engine-side, keep-first-reason, one `stop` + one notification, `stop.suppressed` carries `reason`+`kept`+payload, zero extra posts; (c) correct on content-sha; (d) `by: start|resume`, `was` = cleared reason. §10's exact wording is met, including cli-only (`driver` origin has no producer today: `api.send` defaults `origin="cli"`, `--origin` is a `jobs` filter only, `RESUME_ORIGIN="limit"`), so the driver's real path is `cli` and the pipeline stays clearable. Deviation: §11's event-kind list does not contain `stop.suppressed` — the name is the brief's, not the design's; the design only says "recorded in the inbox only".
    5 probing: (i) **`hands pipeline` can report a `last_rule` from a file that is gone.** `pipeline()`'s lazy load (playbook.py:1029-1033) bypasses the sha comparison that lives in `_load` (playbook.py:653-658), so on a restarted daemon that has not run a job, `hands pipeline` prints the new file's sha next to the old file's rule — demonstrated: reported `rules: 1`, `sha fa9528b8`, `last_rule.rule = 0` with `playbook_sha256 6df1445d`. Self-diagnosable (the record carries its own sha) and the next job start clears it; low. (ii) an unreadable playbook while paused files one `stop.suppressed` per job start (`_load` → `stop()`, playbook.py:645) — demonstrated 4 events from 4 starts, notifications still 1; bounded by limit-origin resumes, low. (iii) a same-reason repeat stop now files `stop.suppressed` where the old code was silent (deliberate; `on_event` is paused-gated at playbook.py:696 so rules cannot storm it). (iv) a `cli` job filed *before* the stop existed still clears it at start — literal §10, but the human never answered that stop. (v) `--for stop` now resolves to `{stop, stop.suppressed}` via the namespace rule in `resolve_kinds` (spool.py:140-144, unchanged code), so a no-op `hands pause` wakes an idle driver; filed as H-011 in the *next* commit (4207f76), not in this one. (vi) `LimitManager.stop` with `on_stop=None` now records nothing in the inbox (log line only) — documented in the docstring, unreachable via `Daemon` (always wired, daemon.py:101-102), untested.
    NOT PROVEN: gate run once here, not the three consecutive runs the body claims; the queued-behind-a-running-job un-pause is proven by code path (`_run`) not by execution; nothing ran outside pytest (no installed build, no live driver), so the `stop.suppressed` wake and the `hands pipeline` stale-rule display are unwitnessed in a real session.

    sha 15eeb76 — U4 blank optional keys refused + doctor reports a config error, DESIGN §13/§4/§20 (review 3 should-fix 5, 8)
    1 identity: body claim matches diff exactly; 7 files, none forbidden (no DESIGN.md, meta/plan.md, meta/CHECKPOINT.md). Both halves (a) config refusal, (b) doctor row, are present and separable.
    2 test-first: `git checkout 4207f76 -- src/` → 25 of 84 RED in test_config.py+test_doctor.py (20 of 22 blank-key params, monitor_cmd-as-ops-dir, 4 doctor). Green-with-product-reverted, correctly: resume_line[empty/blanks] (mission 3 already refused it — anti-regression on the refactor, not new) and test_empty_permission_flags_stay_legal. Every claimed behaviour is load-bearing somewhere. src/ restored, tree clean.
    3 gate: `./scripts/check` at 15eeb76 → "== ruff ==\nAll checks passed!\n== pytest ==\n719 passed in 38.06s\n== cli smoke ==\ncheck: green". Matches the body's 719. Note the gate has no mypy and no `ruff format`.
    4 conformance: I enumerated §13 myself — server.socket/ntfy_topic/ntfy_url, roles.<r>.cwd|model|permission_flags|resume_line, ops.repo/monitor_cmd, playbook.path, files.allowed_roots, gates.patterns (+ non-§13 runner.claude). Executed the loader per key × {"", "   "}: ALL refused with path+section+key+"omit…"/"non-empty…", incl. roles.aux.* which the test table omits. No key missed. cwd refuses blanks with a required-key message (names "absolute path or one starting with ~", not omit/give — correct, not two-choices). permission_flags accepts "" and "   " (shlex→()), exempt as claimed. Every string key in config.py goes through _str/_opt_str/_str_list/_path; `blank` is keyword-only and REQUIRED (TypeError, not a type error, so it survives the mypy-less gate); only one `blank=None` call site (config.py:445); _str_list's `blank: str` cannot opt out. doctor: broken config → text "fail config" row + exit 1; `--json` same check name, green=false, 7-key schema; other commands (status/jobs/inbox/pipeline/pause) all still exit 1 with the bare "hands: …" on stderr.
    5 probing: (a) OVERCLAIM — tests/test_config.py:385 says "No config can reach that state now", but `monitor_cmd = "."` (or `"./"`) gives monitor_path == the ops *directory* (`/ops`), the exact review-3 should-fix-5 end state, via config.py:117-121 doing `repo / monitor_cmd` with no path-shape check; `".."`/`"/"` land elsewhere non-file. Downstream `is_file()` still leaves builder jobs unwatched while status reports a directory as the deciding script. Blanks are strip-detected but values are stored unstripped, so `monitor_cmd = " x "` → `/ops/ x ` and `playbook.path = " P.toml "`, `gates.patterns = [" x "]` keep their padding. (b) Sibling hole, same class, un-refused: `[ops] monitor_cmd` with no `repo` loads fine and is silently ignored (monitor_path None) — while config.py:64's own comment asserts §5 means "both keys, or neither" and the refusal text promises the script will be used; §5 does not actually state that rule. (c) blank inside files.allowed_roots / gates.patterns lists: refused, message names both choices. whitespace ops.repo: refused as blank ("  ") or as non-absolute ("."); NBSP counts as blank via str.strip(). (d) project=None branch (two configs, no --project/$HANDS_PROJECT) does NOT crash: text "hands doctor — project <project>", json config: "", exit 1 — I verified it by execution; untested in the suite, as the report admits.
    NOT PROVEN: the ops-directory-as-monitor state is still reachable by `monitor_cmd = "."` despite the test asserting it is not (fix: refuse a monitor_cmd that is not a bare relative filename, or make monitor_path require is_file); doctor's project=None branch and the padding-preserved values have no test; a future key added with a raw `table.get(...)` instead of the helpers still skips the check — the OPTIONAL_STRING_KEYS table is hand-maintained and nothing asserts helper coverage.

    sha 2fb3b7f — U5a `--prompt-file` refusals + driver rule 6, DESIGN §4 (`send` row), §12 r6, §20
    1 identity: body matches diff exactly (cli.py stat-then-cap gate, driver rule 6 replaced, 2 test files); only `driver/CLAUDE.md`, `src/hands/cli.py`, `tests/test_daemon.py`, `tests/test_docs.py` touched — DESIGN.md, meta/plan.md, meta/CHECKPOINT.md untouched.
    2 test-first: with `git checkout bc13f8d -- src/ driver/`, 5 of 6 new/changed tests go RED — `test_send_refuses_an_oversized_prompt_file`, `test_the_prompt_file_cap_is_checked_without_reading_the_file`, `test_no_bad_prompt_file_ever_reaches_the_daemon`, `test_driver_rule_6_is_the_design_section_12_rule_6`, `test_the_driver_kit_never_claims_a_command_line_cannot_hold_punctuation`. `test_a_prompt_file_at_exactly_the_cap_is_sent` stays GREEN at the parent (an anti-over-refusal guard, not load-bearing). Restored; worktree clean.
    3 gate: `./scripts/check` at 2fb3b7f green, one run — `All checks passed!` / `725 passed in 39.65s` / `check: green` (body claims 3 consecutive; I ran 1, matching count).
    4 conformance: all four refusals execute client-side, one line, path named, stdout empty, and no connect is attempted (valid files print "no daemon on …", refusals never do) — but every one **exits 1, not the exit 2 the brief and meta/CHECKPOINT.md "Intent" require**. The body argues for 1 on its own reasoning; that is a knowing deviation from the brief, corrected only by d348d07. Rule 6 in `driver/CLAUDE.md` is byte-verbatim DESIGN §12 rule 6 (I re-diffed independently: MATCH True); `grep -rni metacharacter driver/` returns nothing.
    5 probing: cap is `runner.MAX_PROMPT_BYTES`, one constant, so no client/runner drift for regular files; cap+1 refused, cap sent; symlink follows to target size (refused); whitespace-only refused as "empty"; non-UTF-8 refused; unstattable dir and mode-000 file refuse "Permission denied"; BOM file is sent verbatim (U+FEFF kept). Two real holes: (a) **FIFO/size-0-reporting files bypass the cap entirely** — `src/hands/cli.py:765` trusts `st_size`, never checks `S_ISREG`, so a FIFO reports 0, passes, then `path.read_bytes()` (cli.py:775) **blocks forever** with no writer (killed at 10 s, exit 124) and happily sends 11 MiB with one; (b) the client caps *raw file bytes* while `daemon.py:63` caps the *JSON-escaped* line at cap+1 MiB, so escape inflation breaks the "refuses exactly what the daemon would" claim: a 9 MiB CJK file (under cap) and a 10 MiB file of `"` or NULs (at cap) both die at `hands: [Errno 32] Broken pipe` with nothing in the daemon log — precisely review-3 should-fix 9's "fails somewhere other than at the path the human named". The at-cap test passes only because it uses `b"x"`, the one content that does not inflate. `MAX_PROMPT_BYTES = 10*1024*1024` (runner.py:63) is 10 MiB while §2/§4 say "10 MB" (body admits this); `send --help` never states the cap.
    NOT PROVEN: gate determinism (1 run, not the body's 3); `--prompt-file` under a real installed build (checkpoint NOT PROVEN 1 still stands); no test covers FIFO/non-regular files or a JSON-inflating at-cap prompt, so both findings above are live at this sha and untested at tip.

    sha d348d07 — U5b `--prompt-file` refusals exit 2, DESIGN §4 send row, §12, §20 (review 3 should-fix 9/10)
    1 identity: body's claim matches the diff exactly (src/hands/cli.py + tests/test_daemon.py only; no DESIGN.md, no meta/, no driver/ touched). Exit 2 is not from DESIGN — DESIGN states no exit codes; it is mandated verbatim by meta/BUILDER-4-PROMPT.md:104 and meta/CHECKPOINT.md:5, so 2fb3b7f's exit 1 was the deviation and this corrects it. Departure from one-commit-per-unit is only *named* ("follow-up to 2fb3b7f"), never justified; CHECKPOINT's "Done means: … one commit, pushed" is now unmet and not flagged.
    2 test-first: reverting `git checkout 2fb3b7f -- src/` gives ImportError (EXIT_REFUSED absent) → whole module uncollectable, so the red is masked. Shimming `EXIT_REFUSED=EXIT_TIMEOUT=2` into the test file exposes the real red: **7 failed** (test_daemon.py missing / directory / not_utf8 / empty / oversized / cap_checked_without_reading / no_bad_prompt_file_ever_reaches_the_daemon), all `assert 1 == 2`. Load-bearing.
    3 gate: `./scripts/check` at d348d07 — "All checks passed!" / "726 passed in 40.54s" / "check: green". Matches the body's 726.
    4 conformance: verified by execution under a sandbox HOME with a nonexistent socket — missing, directory, empty, 10485761-byte, non-UTF-8 and chmod-000 all exit **2**, one stderr line naming the absolute path, empty stdout, daemon never contacted (a *valid* file on the same config exits 1 at the connect). Collision is real but machine-inert: `TIMEOUT_CODE` is raised only at api.py:193,203, both inside the `wait` handler, so `send` never produced 2 before and `wait` has no `--prompt-file`; nothing in src/ or scripts/ reads the CLI's exit code (driver/hooks/bash_guard.py's exit 2 is the Claude Code hook protocol, unrelated). The one reader is prose: driver/CLAUDE.md:52-53 "Exit code 2 is a timeout, not an event: re-arm and say nothing" — scoped to rule 8's `hands wait`, but rule 6 (driver/CLAUDE.md:41-46) is exactly where an LLM driver will now get 2 from a missing kit file, and this commit did not add a clause there. That is the one actionable gap.
    5 probing: constants pinned equal and to 2 at tests/test_daemon.py:354-355, and `wait`'s 2 is pinned independently as a literal at tests/test_wake.py:132,143 — a future split is caught twice. Inconsistency: three other pure client-side refusals still exit 1 — two prompt routes (cli.py:829), no prompt (cli.py:835), `log <job> -f <role>` (cli.py:622) — the first two deliberately, pinned with new messages; so the rule is narrowly "prompt-file refusal", while the new constant docstring (cli.py:45-50) claims the broader "the command refused before it did anything". Route asymmetry: an oversized or empty prompt via `--stdin` gets no client check (cli.py:833) and exits 1 from the daemon — same fact, different code. Docs: exit 2 appears only in `hands send --help` (verified); docs/INTEGRATION.md:222 still says only "exits non-zero", and docs/INTEGRATION.md:121 ("every other command exits 1 with the message alone") is now literally false; README has no exit-code text. tests/test_docs.py checks INTEGRATION.md but not exit codes, so nothing catches this drift.
    NOT PROVEN: that a real LLM driver reading rule 8 will not swallow a rule-6 `send` exit 2 (untestable here); the `wait`-timeout side of the shared code was not re-executed at this sha (only its literal-2 tests were run, inside the 726).
