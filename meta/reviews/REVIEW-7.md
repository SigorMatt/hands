# REVIEW-7 — cold review of mission 7a (review 6 and the harness)

Aux session, no mission context. Base `5dedd45` (`review: mission 6`, the last
`review:` commit: `git log --oneline --grep='^review: ' -1`) → `origin/main`
`ded8952`. Protocol: `meta/REVIEW-PROTOCOL.md`.

    VERDICT: review mission 7 blockers=1 should-fix=4

Read: `DESIGN.md` §23 (with §2, §6, §10, §13), `meta/BUILDER-7-PROMPT.md`,
`meta/FINAL-REPORT-7.md`, `meta/findings/FINDINGS.md` (H-014),
`meta/reviews/REVIEW-6.md`, `git log --oneline 5dedd45..origin/main`.

**Scope.** 15 commits. One sub-agent per unit commit, each in its own detached
worktree: `169ce88` (pre-U0), `b77bc4d` (U0), `c00f0c0` (U1), `09eed7c` (U2),
`da1ffb3` (U3), `b29b1c7` (U4), `f96938e` (U5). `b77bc4d` carries a `meta:`
prefix but is U0 and changes gate inputs, so it was reviewed as a unit
(should-fix 3). Skipped: the architect's kit `db0bd2c` (checked by hand, Notes
1) and seven `meta:` bookkeeping commits (`2955a20`, `7e84bd9`, `12b96c7`,
`57844f9`, `dfd9e6c`, `105aa27`, `ded8952`). Each of those touches only
`meta/CHECKPOINT.md`, `meta/plan.md`, `meta/journal.md`, `meta/FINAL-REPORT-7.md`.
Unlike review 6, every unit commit of the mission is inside the base.

## Blockers

1. **`hands show`'s new `failure` line has no test.** `c00f0c0`'s body and
   `FINAL-REPORT-7.md` §1 U1 both claim "`hands show` gains a `failure`
   line". The line exists: `src/hands/cli.py:395`, `("failure",
   "failure_reason")`. No test drives `show` and asserts on it. The only `show`
   calls in `tests/` are `test_daemon.py:313` and `:748`, which assert
   `prompt`, and `:1092`/`:1194`, which test UTF-8 refusal labels. The
   `c00f0c0` sub-agent confirmed the absence independently. §3 item 4 of the
   report discloses it, but a disclosure is not a test, and the protocol
   counts a missing test for a claimed behaviour as a blocker. `hands show` is
   how a human reads a job record, and this line is the only place the human
   route shows *why* a job failed (`harness_terminated` vs `nonzero_exit`). A
   regression that dropped or mislabelled the line would pass the gate. Pin it
   through `main([... "show", <job>])` on a failed job and on a done job (no
   line, or `failure -`, whichever the code does).

## Should-fix

1. **DESIGN v3.6 does not carry the rule this mission implements. It lives
   only in H-014, while the mission cites §2, §6 and §13.** §23 says
   "Harness termination of a role job is `failed`, not `done` (§2, §6)".
   But §2 (`DESIGN.md:77-122`) still states the 10-minute ceiling as a bare
   fact without saying hands disables it. §6's job record ("returned verbatim,
   stored forever") does not list `failure_reason` and no §6 rule gives the
   three failure conditions. §13's `[roles.<r>]` example has no `env` table.
   `grep -n 'failure_reason\|harness_terminated\|BG_WAIT' DESIGN.md` hits only
   §2's ceiling sentence. The decision is on disk in H-014 and the brief, which
   `CLAUDE.md` allows, so the code is not in breach. Still, `c00f0c0`'s body
   ("DESIGN §2, §6, §13, §23"), H-014's decision heading ("DESIGN v3.6 §2, §6,
   §23") and FINAL-REPORT-7 §1 U1 all cite sections that do not say what is
   cited. `FINAL-REPORT-7` §5 does not raise this with the architect. The
   builder's U1 precedence decision should also go into those section bodies:
   a cancel stays `killed` and a limit stays `limited` even with the
   terminating line. It is recorded in H-014's status and a code comment
   (`runner.py` `_final_state`), not in DESIGN.

2. **The terminating-line matcher over-matches, and a match overrides a
   successful result.** `src/hands/runner.py:124-127` is an unanchored
   `re.search`, `IGNORECASE`, with a free `[a-z]*` unit. Run at the tip:

       is_harness_termination('background tasks still running after 3 retries; terminating the loop')  -> True
       is_harness_termination('grep said: Background tasks still running after 600s; terminating.')    -> True

   `_failure_reason` checks `harness_terminated` first. So any such stderr
   line turns a job with a `success` result, `num_turns` and exit 0 into
   `failed`/`harness_terminated`, and the §10 example's `builder.failed →
   resume` then re-runs a finished mission. Real claude's stderr is harness
   text, so the risk is low. But the report's "refuses five other lines" has
   no quoted or near-miss case among them. Anchor the shape to the harness's
   exact message (a line start, `s;` unit, the `Set
   CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS` tail) and pin the two lines above as
   negatives.

3. **U0 was committed as `meta:` although it changes gate inputs, and the
   protocol skips `meta:` commits.** `b77bc4d` (`meta: mission 7a plan;
   review 6's two blockers corrected and H-014 filed`) changes `README.md`,
   root `CLAUDE.md` and `.gitignore` alongside plan/checkpoint/journal/findings.
   `README.md` is read by the doc sweep and `CLAUDE.md` by
   `tests/test_no_background.py`. `CLAUDE.md` says "one commit per unit:
   `<area>: <one line>`". `REVIEW-PROTOCOL.md` says "skip `meta:` bookkeeping
   commits". A reviewer who applied that literally would never review review 6's
   blocker-1 fix. `FINAL-REPORT-7.md:19-20` says each unit is "followed by a
   `meta:` bookkeeping commit … that changes no gate input". That is true of
   the followers, but it leaves out that U0 itself is a `meta:` commit that does
   change gate inputs. Split product/doc corrections from bookkeeping in future
   missions, or have the report name the exception.

4. **The "every tracked text file" sweep is a suffix allow-list plus a blanket
   `meta/` exclusion, and one excluded file is live instruction, not history.**
   `tests/test_docs.py:266` keeps only `.md .py .toml .json .txt .service` (+
   `#!` files), and `:272` excludes `meta/` whole "as history (§20)". At the tip
   that reads every non-`meta/`, non-`DESIGN.md` text file (50 of 79 at
   `da1ffb3`, confirmed). But `meta/REVIEW-PROTOCOL.md` is not history.
   `PLAYBOOK.toml:15` sends every aux review to it, and this mission's kit
   rewrote it, yet it is unswept. A future tracked `*.sh`, `*.yml`, `*.rst`,
   `*.cfg` or `*.ini` would also be skipped silently. The `U3` sub-agent probed
   `scripts/new.sh`, `.github/workflows/ci.yml`, `docs/NOTES.rst`: none swept.
   The `>= 40` floor (`:315`) would not notice. DESIGN §23 says "every tracked
   text file, not a list". Report §3 item 5 concedes "tracked files outside the
   extension/`#!` rule are unread" but not that live instructions under `meta/`
   are. Either sweep `meta/REVIEW-PROTOCOL.md` and the `BUILDER-*-PROMPT.md`
   files (or exclude only reports, journal and reviews), and decide text-ness
   by content (no NUL in the first block) rather than by suffix.

## Notes

1. **Kit `db0bd2c`** (architect; allowed to edit `DESIGN.md`). It changed
   `DESIGN.md`, `PLAYBOOK.toml`, `meta/REVIEW-PROTOCOL.md`, `meta/BACKLOG.md`,
   `meta/ROADMAP.md`, `meta/BUILDER-7-PROMPT.md`, and its body lists all six.
   It left the suite red (2 failed, both tests that pin DESIGN verbatim); the
   `169ce88` sub-agent reproduced exactly those two at `169ce88^`. `169ce88`
   repaired it legitimately: the tests that read DESIGN were not edited, only
   the two that fire the fixture. The brief has one false premise. It sends the
   builder to "the record of job `0mtygi953-ym63` in `meta/FINAL-REPORT-6.md`",
   but that file has no mention of the job (`grep 'ym63\|terminat'` is empty at
   `b77bc4d` and at the tip). H-014 correctly cites the job JSON and the
   transcript instead; the `b77bc4d` sub-agent checked both against disk.

2. **The gate at the tip, re-run by me at `ded8952` (= `origin/main`):** ruff
   `All checks passed!`, `1235 passed in 64.38s (0:01:04)`, `== cli smoke ==`,
   `check: green`, exit 0 (one run). It matches the report's 1235. Every unit
   commit is green at its own sha (Per-commit verdicts).

3. **Commit bodies and forbidden files, over all 15 commits.** A script
   compared each commit's `git show --name-only` with its body, and no commit
   carries a file its body does not name. That confirms FINAL-REPORT-7 §4's
   second criterion and review 6 should-fix 3. No builder unit commit touches
   `DESIGN.md`, `meta/plan.md` or `meta/CHECKPOINT.md`. `c00f0c0` and `09eed7c`
   touch `meta/findings/FINDINGS.md`, as the brief asks. The worktree was clean
   and no review worktree remained after the sub-agents finished.

4. **NOT PROVEN (§3) read against the sub-agents.** It holds up, and several
   items predicted exactly what was found:
   - **Item 1:** nothing ran live. The `09eed7c` sub-agent confirmed from the
     installed binary, now **2.1.270** rather than 2.1.269, that the tool is
     `Agent` with alias `Task`, that `run_in_background!==!1` counts as
     background, and that the matcher is split on `|` after
     `/^[a-zA-Z0-9_|]+$/`. It could not confirm that this check is what decides
     launch mode, or that exit 2 blocks a launch.
   - **Item 2:** the `SendMessage` gap is recorded honestly in the hook
     docstring, `docs/INTEGRATION.md`, H-014 and the report.
   - **Item 4:** confirmed. `runner._event_payload` carries no
     `failure_reason`, and the missing `show` test is blocker 1.
   - **Item 5:** confirmed and wider. Two probe sentences in `doctor.py` passed
     all three doc tests: "have the driver keep a listener on the event stream
     so it hears the stop the moment it lands", and "The driver does not poll,
     so first have it arm a wait for the stop event" (the second defeats the
     negation check at `tests/test_doctor.py` ~482). "Whether an idle Claude
     session is roused by a finished task remains undecided." appended to
     README also passes.
   - **Item 8:** understated. `_typed_names` (`cli.py:958`, `functools.cache`)
     is called on every request, not only on refusals. If argparse's private
     `_actions` changed, a valid `hands result` would raise an uncaught
     `AttributeError` (traceback, not exit 1). A key the parser does not know
     is labelled by its bare key (`files: not UTF-8 text`); that is latent,
     since no command sends one.
   - **Items 6 and 7** (`notify --test`, `put --from`) are unchanged:
     `notify --test $'hi\xff'` still exits 1 blaming the ntfy URL.
   - **Item 10:** this review is the first run of the new base rule. It found
     the base at `5dedd45`, and the range held every unit commit of the
     mission.

5. **Checked and sound.**
   - **U1:** reading "error" as the `error_*` family is defensible and is
     recorded in H-014. One consequence goes unstated: an `error_*` subtype
     with `is_error` false, `num_turns` set and exit 0 is `done`, so "three
     `error_*` subtypes are `error_result`" rests on `fake_claude` always
     setting `is_error`.
   - **U1 env table:** it accepts any variable name (`PATH`, `LD_PRELOAD`).
     The config is the owner's own file, so this is not a hole.
   - **U2:** 76 identical payloads (the old 65-case selftest plus odd shapes)
     gave byte-identical exit/stdout/stderr on the old and new hook. Agent and
     Task fail closed on unreadable, empty or non-UTF-8 stdin. Only the JSON
     boolean `false` passes.
   - **U4:** across 3000 random nested requests plus hand probes (non-str keys,
     NaN/inf, a float or None `id`), `_wire_size` equals
     `len(json.dumps(req, ensure_ascii=False).encode())` for the whole request.
     Real subprocess refusals read `a job argument` / `a path argument` /
     `a prompt argument`, exit 2, matching the usage line's `job` / `path` /
     `[prompt]`.
   - **U5:** `git diff db0bd2c f96938e -- meta/REVIEW-PROTOCOL.md` is empty.
     DESIGN §10's example and the fixture say "commits since the last review:
     commit on the branch", while root `PLAYBOOK.toml` says "every commit after
     the last review: commit on origin/main". Same meaning, and a stale local
     branch can only widen the range. The new `PLAYBOOK.toml` test was never
     honestly red; its mutation stand-in was reproduced red.

6. **U0's new sentences are unpinned at `b77bc4d`.** With `README.md` or
   `CLAUDE.md` reverted, `tests/test_docs.py` and `tests/test_no_background.py`
   stay green. U3's sweep later catches README's retired wording. Nothing pins
   `CLAUDE.md`'s "Sub-agents run in the foreground" sentence.

## Per-commit verdicts

sha 169ce88 — pre-U0 fix (not a numbered unit) that makes the tree follow the v3.6 kit, DESIGN §12 rule 8, §10 (example review prompt), §23 (review base)
1 claim check: the body matches the disk. Rule 8 now ends with the exit-2 sentence and the separate exit-2 paragraph is deleted. The fixture and the docs/PLAYBOOK.md example carry "since the last review: commit on the branch". test_playbook.py adds `REVIEW_PROMPT`, used in 2 tests. test_docs.py changes only a docstring. The "base red: 2 failed" claim holds: the full tree at 169ce88^ fails exactly `test_docs.py::test_driver_rule_8_is_the_design_section_12_rule_8` and `test_playbook.py::test_the_fixture_is_section_10s_example_verbatim`.
2 test-first: PASS (the red is legitimate). Reverting driver/CLAUDE.md and docs/PLAYBOOK.md fails `test_the_playbook_doc_carries_the_section_10_example_verbatim` ("the §10 example line is missing: 'prompt = \"Review WORKPLAN.md commits since the last review: commit on the branch\"'") and `test_driver_rule_8_is_the_design_section_12_rule_8` ("- n approval. `hands` exit 2 means the client did not deliver a completed request: a refusal or a timeout, not an event. + n approval."). Reverting only the fixture (it is product: §10's bytes) fails 4 tests: `test_the_playbook_doc_carries_the_section_10_example_verbatim`, `test_the_fixture_is_section_10s_example_verbatim`, `test_a_matching_rule_sends_with_origin_playbook_and_the_sha` (prompt 'since abc123') and `test_the_section_10_example_end_to_end` (prompt 'since f39dcd6…'). The two playbook tests were edited, but only to follow the fixture, which is itself pinned to DESIGN by an untouched test that went red on the kit commit. The tests that read DESIGN directly were not changed, so this is not a test edited to pass. Restored each time; `git status --porcelain` empty.
3 ./scripts/check: green — "== ruff == All checks passed!", "1112 passed in 106.18s (0:01:46)", "== cli smoke ==", "check: green" (exit 0)
4 forbidden/conformance: the commit touches only the 5 files its body lists; DESIGN.md, meta/plan.md and meta/CHECKPOINT.md are untouched. Rule 8 kit vs DESIGN is equal whitespace-normalised; the raw bytes differ only in indentation and line wrap ("for a / short wait", "the client / did not"). The fixture equals the §10 block exactly after stripping the 4-space indent and outer whitespace (the test's own comparison). docs/PLAYBOOK.md contains the whole fixture as one contiguous 4-space-indented block. The one `{job.head_at_start}` left in docs/PLAYBOOK.md (line 107) is the §10 placeholder list, which is correct.
5 NOT proven: no defect found. The deleted kit paragraph's "(bad prompt file, oversized request)" examples are gone from driver/CLAUDE.md, but §12 rule 8 has no such text, so that matches the design. The next check shows `test_the_docs_say_what_exit_2_means` still passes without them. The per-test pytest summary line was not captured in the targeted runs, only the FAILED lines. Timing differs from the body's figures (106s vs ~60s), with no effect on the result. "U5 still owns the playbook prose about the review base" was not checked in this commit. Worktree removed; other /tmp/hands-rev7-* worktrees from sibling reviews are still registered.

sha b77bc4d — mission 7a U0 "Plan and corrections", DESIGN §11, §20, §23; REVIEW-6 blocker 1, blocker 2, should-fix 3; H-014 filed
1 claim check: the body lists all 8 files the diff touches and says no src/, tests/ or driver/ file changed, which is true. Each brief item is done: README, the FINAL-REPORT-6 correction, .gitignore `meta/drafts/`, the CLAUDE.md line, H-014.
2 test-first: N-A. The commit adds no tests. With README.md reverted to b77bc4d^, test_docs + test_no_background stay green (177 passed): nothing at this commit catches the retired sentence. With CLAUDE.md alone reverted, test_no_background stays green (157 passed); test_no_background.py:309-317 only requires one bullet naming run_in_background/nohup/foreground/timeout. Restored; porcelain empty.
3 ./scripts/check: green — "1112 passed in 109.67s (0:01:49)", "== cli smoke ==", "check: green", exit 0.
4 conformance: (a) README no longer calls the wake question open or says doctor prints a wake procedure (only :79 and :116-118 mention it). :116-118 matches DESIGN §11 ("no wake, by decision", notification check) and doctor.py:413-441 (pause files a `stop`, a gated send files `job.held`). (b) FINAL-REPORT-6: 14 lines added, none deleted or changed, dated 2026-09-12, cites §20. Its claim holds: `_checked_request` (cli.py:1029-1030) runs `_utf8_bytes` on every params string before `_wire_size`, and `notify.http_post` (notify.py:140) encodes without that check. Reproduced here: `notify --test $'hi\xff'` exits 1 with "http://127.0.0.1:1/rev-probe-topic did not take the message: UnicodeEncodeError…"; `send` exits 2 "a prompt argument: not UTF-8 text". No other client-side string-encode site found in cli.py or notify.py. (c) .gitignore has `meta/drafts/`. (d) CLAUDE.md:21 has the sentence, inside the one existing bullet.
4 cont.: (e) H-014 matches ~/.hands/jobs/0mtygi953-ym63.json (started/ended timestamps, done, exit 0, 59 turns, verdict null, the stderr line) and the transcript (5 Agent calls all run_in_background false, SendMessage at 15:37:38.514Z, no background-asking input). (f) The `meta:` label on a commit that changes README.md and CLAUDE.md is a convention defect: both are gate inputs read by test_docs and test_no_background. FINAL-REPORT-7:19-20 says each unit is followed by a `meta:` bookkeeping commit that "changes no gate input". That is about the follow-up commits, not literally about U0, but U0 is itself a `meta:` commit that does change gate inputs, so the report leaves that unsaid.
5 NOT proven / defects: (i) FINAL-REPORT-6 has no record of job 0mtygi953-ym63 at b77bc4d or at main (grep "ym63|terminat" finds nothing), yet BUILDER-7-PROMPT.md:9-10 sends the builder there. The brief's premise is wrong, and H-014 correctly cites the job JSON and the transcript instead. This is a defect in the brief, not in this commit. (ii) No test pins the new README sentence or the CLAUDE.md sub-agent sentence at this commit; deleting either keeps the gate green (step 2). (iii) The commit's "green three consecutive runs, 1112 passed" was not re-run 3x; one run matched the count. (iv) The README's "proves a `stop` or a `held` job reaches the phone" is a human procedure, never run here. (v) H-014's own gap stays open: a SendMessage continuation is not a background-asking input. Worktree removed; main is clean. Other /tmp/hands-rev7-* worktrees for other commits are still registered and were not touched.

sha c00f0c0 — U1 of mission 7a (harness termination is `failed`), claims DESIGN §2, §6, §13, §23 and H-014
1 claim check: Confirmed against disk. The body names all 13 files (the tests by short name), and FINAL-REPORT-7 §1 U1, §2 U1 and §3 items 1 and 4 match the diff and the tests.
2 test-first: PASS. With the six product files reverted: `test_runner.py` fails to collect (`ImportError: cannot import name 'is_harness_termination' from 'hands.runner'`); the other four files give 22 FAILED. With the two missing names injected, test_runner has 25 FAILED, including `test_the_exact_shape_of_job_0mtygi953_is_failed_harness_terminated` (`AssertionError: assert 'done' == 'failed'`, test_runner.py:338). `test_a_harness_terminated_builder_job_is_failed_and_the_example_resumes_it` also fails (`assert [('builder', 'cli')] == [('builder', ..., 'playbook')]`, test_playbook.py:1406). After restore, `git status --porcelain` was empty.
3 ./scripts/check: green — "1156 passed in 110.34s (0:01:50)", "== cli smoke ==", "check: green".
4 forbidden/conformance: No DESIGN.md, meta/plan.md or meta/CHECKPOINT.md. (a) All three conditions are implemented as written (runner.py `_failure_reason`, `_is_final_subtype`); reading "error" as the `error_*` family is defensible and recorded in H-014's status paragraph. (b) DESIGN §6/§23 say nothing on killed/limited vs the terminating line. H-005 (§6 owns the limit resume) supports limited-wins, but it is the builder's own decision, written into H-014's status and not raised as an architect question. (c) DESIGN §13 is unchanged (builders may not edit it). The env table appears only in docs/INTEGRATION.md and H-014's decision. `spawn_env = {**DEFAULT_ROLE_ENV, **env}` over `os.environ`: a config value wins, handsd's own 600000 is overridden to 0, other inherited vars still pass, all tested. Any valid name can be set (PATH, LD_PRELOAD, ANTHROPIC_API_KEY); the config is hand-edited by its owner, so this is a note, not a hole. (d) doctor shows the effective value per role in text and `--json` (test_doctor.py:236, 256), and `--live` uses the same env (:272). (e) `failure_reason` is in the job record; `_event_payload` (runner.py:234) has only job/role/state/session_id/verdict, so the report is right. No test in tests/ exercises `hands show`'s `failure` line (cli.py:394), as reported.
5 NOT proven / defects:
- (f) The matcher over-matches (runner.py:125, `[a-z]*` unit): `is_harness_termination` is True for "background tasks still running after 3 retries; terminating the loop" and for a line quoting the message. Such a line wins over a success result, so the job becomes failed/harness_terminated and `builder.failed → resume` fires. Risk is low because claude's stderr carries harness text, not tool output; no test covers it.
- An `error_*` subtype with `is_error` false, num_turns set and exit 0 is `('done', None)` by direct probe of `_final_state`. That fits the design text, but the report's "error_* are error_result" rests on fake_claude always setting `is_error` true.
- No real claude run: the ceiling=0 wait, the line format and the subtype names are unobserved. Precedence (b) has no architect sign-off.

sha 09eed7c — U2 of mission 7a ("the hook covers background sub-agents"), DESIGN §2, §21, §23; H-014
1 claim check: PASS. The hook matches `Agent` and `Task` and blocks (exit 2) unless the input has the JSON boolean `run_in_background: false`. The brief's "find the name and record it in the docstring" is done. §23 (DESIGN.md:818-819) asks for this. The body lists all 6 changed files, and none of them is DESIGN.md, meta/plan.md or meta/CHECKPOINT.md.
2 test-first: PASS. With the hook, settings and doc reverted to 09eed7c^, `pytest tests/test_no_background.py tests/test_docs.py` stops at collection with 1 error: `AttributeError: module 'no_background' has no attribute 'SUBAGENT_SELFTEST'`. I reran the test file with the table copied in so it could collect; it failed with `settings.json has no PreToolUse hook matching Agent`, `no attribute 'SUBAGENT_TOOLS'`, `the hook's docstring does not record 'Agent'`, and `assert 0 == 2` for Agent/Task payloads. test_docs alone: `FAILED ...test_the_integration_doc_lists_what_the_no_background_hook_cannot_see` (`the blind-spot list does not name 'SendMessage'`). I did not capture the total failure counts. After restoring, `git status --porcelain` was empty.
3 ./scripts/check: green — "1204 passed in 114.68s (0:01:54)", "== cli smoke ==", "check: green". `--selftest` prints "selftest: 65/65 ok" and "selftest (Agent, Task): 12/12 ok", exit 0.
4 conformance: (a) I sent 76 identical payloads to the old and new hook: the 65 old selftest commands, run_in_background true/"true"/[1], odd tool_input shapes, non-Bash tools, non-dict JSON, bad JSON, empty stdin. Exit code, stdout and stderr all matched byte for byte. (b) Agent and Task behave the same. Exit 2 for true, omitted, null, "false", 0.0, a missing or null tool_input ("omitted" reason), and a list flag or list tool_input ("no_background: ... blocking"). Exit 0 only for false. Unparseable, empty, closed or invalid-UTF-8 stdin all exit 2, so it fails closed. It never exits 0 for a call the harness would run in the background. The one exception: duplicate keys true-then-false pass, but JSON.parse also keeps the last value, so the harness sees false too. (c) Confirmed by grepping the installed binary, which is now 2.1.270, not the 2.1.269 cited: `ht="Agent"`, `Yg="Task"`, `aliases:[Yg]`, `{Task:"Agent"}`, `(k.name===ht||k.name===Yg)){...k.input?.run_in_background!==!1)h.add(k.id)`. The matcher rule is `/^[a-zA-Z0-9_|]+$/` then `e.split("|")...flatMap((d)=>Rwe(Yu(d),r))`, where Yu maps Task to Agent. "Subagents run in the background by default" is also in the binary. The PreToolUse input is `{hook_event_name:"PreToolUse",tool_name:e,tool_input:r,...}`. (d) settings.json matcher is `Bash|Agent|Task`, and the INTEGRATION.md paragraph says the same. (e) The SendMessage gap is recorded honestly in the docstring, INTEGRATION.md, H-014, the body, and FINAL-REPORT-7 §3 items 2 and 3. (f) The block message tells the agent to "pass `run_in_background: false`" and to split the work.
5 NOT proven (no defects found): Nothing was run live. I could not confirm three things: what `tool_name` the harness sends when the model calls `Task` (either name is blocked, so it doesn't matter); that exit 2 actually blocks an Agent launch; and that the `!==!1` check I found is the code that decides launch mode, not just a set used for print-mode wait logic. The 85/27 transcript counts were not recounted. The 2.1.269 facts were checked against 2.1.270 only. SendMessage continuation stays open.

sha da1ffb3 — U3 of mission 7a (doc-truth as a property); DESIGN §11, §22, §23; REVIEW-6 blocker 1, should-fix 1, should-fix 2
1 claim check: the body matches the disk. Only tests/test_docs.py, tests/test_doctor.py and the tests/test_playbook.py docstring changed, and the body lists all three. At da1ffb3 swept_files() reads 50 of 79 tracked files, confirmed. Excluded: .gitignore, uv.lock, DESIGN.md, tests/test_docs.py and 25 meta/ files. No .yaml, .sh, .cfg or .ini files are tracked today. .claude/settings.json, .claude/hooks/no_background.py, PLAYBOOK.toml, driver/*, scripts/check and systemd/handsd.service are all read.
2 test-first: PASS. At dca0820 with da1ffb3's test_docs.py and test_doctor.py copied in, test_nothing_shipped_says_the_driver_arms_or_blocks_on_a_wait is red: "README.md: 'wakes an idle interactive claude code session' / README.md: 'prints the procedure that answers it' / tests/test_playbook.py: 'driver blocked on' / tests/test_playbook.py: 'not woken by a pause'". 'background bash task' does not appear because the new test_doctor.py was copied too. 4 other failures are later-unit tests in the copied files (3 bg-wait ceiling tests, 1 no-background-hook doc test), not U3. At 56bef53^ both notification-check tests are red, but only on the first assert ("doctor prints no notification check" / 'Notification check (§11)' missing), so that red never exercises the wait or negation logic. Mutation M1 does. Worktrees restored, porcelain empty, all removed.
3 ./scripts/check: green — "1205 passed in 123.49s (0:02:03) / == cli smoke == / check: green"
4 forbidden/conformance: DESIGN.md, meta/plan.md and meta/CHECKPOINT.md are untouched. Without git on PATH both sweep tests FAIL with FileNotFoundError 'git'; with GIT_DIR=/nonexistent they FAIL with CalledProcessError 128, so neither passes. Mutation M1 (doctor text says "run `hands wait --for stop,held` in the background"): both doctor tests red, 'wait' is outside the allowed set. The command allow-list is independent of the old output, so that half of the non-circularity claim holds.
5 NOT proven / defects:
 (i) The suffix allow-list at tests/test_docs.py SWEPT_SUFFIXES (~l.246) is a list in disguise for future files. If tracked, scripts/new.sh, .github/workflows/ci.yml, docs/NOTES.rst, conf/hands.cfg and setup.ini would all be skipped (probe: of those plus README.md, only README.md is swept). The ">= 40" floor would not notice. That falls short of §23's "every tracked text file".
 (ii) The meta/ exclusion is too broad. meta/REVIEW-PROTOCOL.md is live instruction, not history: PLAYBOOK.toml:15 tells the reviewer to read it, and this mission edited it (f96938e). It is unswept. DESIGN.md is excluded whole, not just its §11 History paragraph.
 (iii) M2: this doctor.py sentence stays green on all 3 tests: "Before step 2, have the driver keep a listener on the event stream so it hears the stop the moment it lands." The arming check is a keyword heuristic.
 (iv) M3: "The driver does not poll, so first have it arm a wait for the stop event." stays green. This confirms the per-sentence negation hole at tests/test_doctor.py ~l.482-484.
 (v) M4: appending "Whether an idle Claude session is roused by a finished task remains undecided." to README.md stays green, confirming report §3 item 5.
 (vi) Delivery of a notification to a phone over ntfy is still not witnessed.

sha b29b1c7 — U4 of mission 7a (client seams), claims DESIGN §4, §23 and REVIEW-6 should-fix 4 (UTF-8 check and size walk used different trees) and 5 (positionals got invented flag names)
1 claim check: PASS. Only `src/hands/cli.py` and `tests/test_daemon.py` changed, and the body lists both. `_carried` is the single walk that both `_checked_request` and `_wire_size`/`_wire_parts` read. Labels come from the parser via `_typed_names`. The commit adds 28 tests: 3 walk tests, 14 positional cases and 11 flag cases.
2 test-first: PASS. With the parent's cli.py, 17 of the 28 fail and all 17 are behavioural (no ImportError or AttributeError). The nested shape fails with `E   UnicodeEncodeError: 'utf-8' codec can't encode character '\udcff' in position 4: surrogates not allowed` (test_daemon.py:1027). The label test fails with `('wait', 'job', PromptError("--job: not UTF-8 text (...)"))` (:1184), and put gets `hands: --path: not UTF-8 text`. The other 11 already passed at the parent: send's prompt (already "a prompt argument") and 10 of 11 flags (not `-f`, which the parent labelled `--role`). The tree was restored and `git status --porcelain` was empty.
3 ./scripts/check: green, `1233 passed in 66.98s (0:01:06)` / `== cli smoke ==` / `check: green`
4 forbidden/conformance: (a) Real subprocess, `PYTHONUTF8=1`, throwaway HOME and a socket that doesn't exist: `hands result $'job-\xff'` and `show` give `hands: a job argument: not UTF-8 text ('utf-8' codec can't encode character '\udcff' in position 4: surrogates not allowed)`, exit 2. `put`/`get $'drop/\xff'` give `hands: a path argument: ...` exit 2, `send ... $'hi\xff'` gives `hands: a prompt argument: ...` exit 2, and `--content`/`-f` keep their flag names. (b) Usage prints `hands result ... job`, `put ... path` and `send ... [prompt]`, so "a job argument" uses the name the human sees. (c) Across 3000 random nested trees plus hand probes, `_wire_size` never differed from `len(json.dumps(req, ensure_ascii=False).encode())` for the whole request, envelope included. The probes covered non-str keys (int, float, None, True, 10**30, inf), NaN/inf values, bools, None, tuples, escapes, CJK/emoji, a float or None `id`, and params as a list or string. (e) Valid input and the H-012 tests are still green. (f) `hands notify --test $'hi\xff'` is unchanged: `hands: http://127.0.0.1:1/rev-probe-topic did not take the message: UnicodeEncodeError: ...`, exit 1. (g) The commit does not touch DESIGN.md, meta/plan.md or meta/CHECKPOINT.md.
5 NOT proven / defects:
- (d) Missing dest: there is no KeyError. `_named` (cli.py ~985) falls back to the bare key, so `{"files": bad}` on send says `files: not UTF-8 text` and an unknown command says `job:`. That is neither a flag nor "a X argument" (latent: no command sends such a key today).
- The private-API dependency sits on every request, not only on refusals. `_carried` calls `_named`, which calls `_typed_names`, which calls `build_parser()._actions` (cli.py:969), for each params part. With `_actions` gone, a valid `result` request raises AttributeError, which `main` does not catch, so the user gets a traceback instead of the request. If only the `_SubParsersAction` isinstance check misses, the labels silently become `{}` and every refusal says `job:`. No test pins either case.
- `_wire_parts` names the largest single string, not the largest part, so a nested part's size would be split across its strings (latent).
- The 28 tests run in-process; my subprocess probes above cover only result, show, put, get, send, log -f and put --content.
- `notify --test` (REVIEW-6 blocker 2) and `put --from` content checks are out of scope, and the commit body says so.

sha f96938e — U5 of mission 7a (review base); claims DESIGN §10 (Placeholders, example review prompt) and the §23 review-base bullet; fixes REVIEW-6's scope note.
1 claim check: PASS. It changes 3 files (docs/PLAYBOOK.md, tests/test_docs.py, tests/test_playbook.py) and the body lists all 3. The docs gain "The review base (DESIGN §23)"; the §10 example block, PLAYBOOK.toml and the fixture are unchanged, as the body says.
2 test-first: PASS. With docs/PLAYBOOK.md reverted to f96938e^, the new doc test fails: `AssertionError: docs/PLAYBOOK.md's prose does not say 'every commit after the last \`review:\` commit' (§23)`. The new PLAYBOOK.toml test was never red on its own, as the body admits. I repeated its mutation (prompt changed to "every commit since {job.head_at_start}"): `FAILED ...test_the_repositorys_own_playbook_loads_and_its_review_reads_from_the_last_review`, `assert 'head_at_start' not in 'Read meta/R...t specifies.'` (test_playbook.py:225). Tree restored; `git status --porcelain` empty.
3 ./scripts/check: green. "All checks passed!" / "1235 passed in 89.56s (0:01:29)" / "check: green", exit 0.
4 forbidden/conformance: (a) "The example playbook loads" is met by the root PLAYBOOK.toml (new test, via load_playbook). The §10 example was already covered before this commit by test_the_example_parses_into_the_rules_of_section_10 (parse_playbook only), the end-to-end tests and the verbatim fixture/doc tests. The wording differs but means the same: DESIGN §10, the fixture and the docs block say "commits since the last review: commit on the branch"; root PLAYBOOK.toml says "every commit after the last review: commit on origin/main".
  (b) The prose matches REVIEW-PROTOCOL's command and its kit-commit fallback. It says "on the branch" like the protocol, but PLAYBOOK.toml says "on origin/main". The protocol's `git log --grep -1` reads local HEAD, then `<base>..origin/main`, so a stale local branch only makes the range wider (reviews more); it cannot skip commits.
  (c) The docs on `{job.head_at_start}` agree with §10 (still one of four job fields) and with §23 ("not {job.head_at_start}").
  (d) `git diff db0bd2c f96938e -- meta/REVIEW-PROTOCOL.md` is empty (0 bytes); no commit in db0bd2c..f96938e touches it.
  (e) grep -rn of README.md, docs/, driver/, CLAUDE.md, scripts/ finds no other text about the review base or head_at_start.
  (f) The commit does not touch DESIGN.md, meta/plan.md or meta/CHECKPOINT.md.
5 NOT proven: (i) The brief asks that "the example rule" use the "every commit after" wording. DESIGN §10's example still says "commits since", and it cannot be edited, so the only thing U5 changed in product terms is docs prose. (ii) The PLAYBOOK.toml test had no honest red; only the mutation stands in. (iii) One required phrase, "`{job.head_at_start}`, `{job.head_at_end}`", was already in docs/PLAYBOOK.md:107 before the commit, so it adds no red. The test checks phrases, not meaning. (iv) No real aux review has run against a resumed mission. (v) Minor wording mismatch between PLAYBOOK.toml:15 ("origin/main") and docs/PLAYBOOK.md:115-116 / the protocol ("on the branch"); not a defect. Worktree removed; main is clean.
