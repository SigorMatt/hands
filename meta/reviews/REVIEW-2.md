# REVIEW-2 — cold review of mission 2 (the shakeout)

Aux session, no mission context. Base `59e7ac7` → `origin/main` `46ef79d`.
Protocol: `meta/REVIEW-PROTOCOL.md`. Seven unit commits, one sub-agent each in
its own detached worktree; `meta:` bookkeeping commits skipped.

    VERDICT: review mission 2 blockers=0 should-fix=8

## Blockers

None.

Every unit commit is green on `./scripts/check` at its own sha (494 → 496 →
501 → 510 → 518 → 519 → 521), every unit's tests were confirmed load-bearing by
reverting only that commit's product files and watching them go red, no unit
commit touches `DESIGN.md`, `meta/plan.md` or `meta/CHECKPOINT.md`, and the
pushed tip is green here too (`ruff` clean, `521 passed in 34.48s`, `check:
green`). The acceptance criterion that does not hold is Should-fix 1, not a
blocker, for the reason recorded in Notes.

## Should-fix

1. **Acceptance check 2 fails as written, and the brief is what is wrong.**
   `meta/BUILDER-2-PROMPT.md:115` requires `grep -rn 'dispatch.sh\|only_if_run_in'`
   to return only ledger/report lines. `dispatch.sh` holds (13 hits, all
   `DESIGN.md` §15/§18 and `meta/`). `only_if_run_in` does not: `src/hands/playbook.py:391,396`,
   `tests/test_playbook.py:276-280`, `docs/PLAYBOOK.md:115`. The builder kept
   the refusal and said so in `FINAL-REPORT-2.md` §5 — that is the right call,
   because the same brief's U3 *requires* a playbook with the old key to be
   refused by name, which needs the literal string. But `VERDICT: mission 2
   finished` is gated on "the acceptance below holds", and one line of it does
   not. The architect should amend the criterion (e.g. "no `only_if_run_in`
   outside the refusal site and its tests") so the next mission is not asked to
   satisfy two rules that contradict each other.

2. **`hands status` states the built-in stall rule even when the monitor is the
   ops script.** `cli.py:366` prints `stall = no progress and no liveness for
   {stall_minutes}m` unconditionally, but `monitor.status()` reports
   `source: "ops"` whenever `ops.monitor_path` is set, and the ops script is
   invoked with `--pids/--transcript/--base` only (`monitor.py:403-415`) —
   `stall_minutes` is never passed to it and `monitor.py:476` is the built-in
   path. On an ops install the line describes a rule that is not the one
   deciding. `stall_minutes = 0` (detection off, `monitor.py:478`) prints "for
   0m". Pre-existing in shape ("stall after 40m" had the same flaw) but U6 made
   the claim more specific and therefore larger. The U6 test only exercises
   `source: builtin`.

3. **Four of U3's `BAD_PLAYBOOKS` cases assert a substring that cannot fail.**
   `run that is not an expression`, `run naming a job field`, and both
   `only_if_run_in` cases assert only `"run" in str(exc)`
   (`tests/test_playbook.py:271-280`). `only_if_run_in` literally contains
   "run", so the pre-U3 generic `unknown key(s) in rule 1: ...` message also
   satisfies it — three of the four still pass against `34b4ede^`. The
   behaviour is real (`playbook.py:396` names the replacement key), but the
   brief's gate "`only_if_run_in` is refused at load with a message naming
   `run`" is not pinned by any test. `FINAL-REPORT-2.md` §2 says these cases
   "prove the load-time refusals one at a time"; for these four they do not.
   Assert on `run = "{n+1}"` or on the sentence, not on `run`.

4. **`hands pause` over a pipeline already stopped for another reason silently
   rewrites the reason.** `stop()`'s guard is `paused and stop_reason == reason`
   (`playbook.py:907`), so a hand pause after a rule stop or a `job.held` stop
   passes it, overwrites `stop_reason`/`stopped_at` with `paused by human`, and
   emits a second notification. `hands pipeline` then no longer shows why the
   pipeline actually stopped (it survives only in the inbox). Untested; a real
   behaviour change against the old flag-only pause. Either refuse, or keep the
   first reason.

5. **`resume_line = ""` is silently "re-send the prompt".** `config.py:356`
   (`_opt_str(...) or None`) folds an empty string into absent. Disclosed in
   `FINAL-REPORT-2.md` §3 new-item 3, but neither tested nor mentioned in
   `docs/INTEGRATION.md` (which says only "optional, no default"). An operator
   who writes `resume_line = ""` gets the other branch with no warning.

6. **`meta/journal.md:17` cites a sha that is not in `main`'s history.** U0 is
   recorded as `857f6f2`; that commit was amended (the amend is the line itself
   — the journal entry named its own sha) and `main` carries `3c5d880`.
   `857f6f2` is unreachable from any ref. `FINAL-REPORT-2.md` §1 and
   `meta/plan.md` both have it right; only the journal is untraceable. Write
   `(pending)` or the unit name and fix it in the next commit.

7. **U5's "prints the HTTP status" only ever prints a 2xx.** `http_post` calls
   `raise_for_status()`, and `send_test` wraps any exception into `NotifyError`
   → exit 1, so a 403 or 404 from ntfy is reported as a failure, not as a
   status. No test drives a real HTTP error status (the failure test injects
   `OSError`), and `http_post` itself is monkeypatched in all eight tests, so
   the new `-> int` return is unverified against httpx. Narrow the sentence, or
   print the code on the failure path too.

8. **U6's alias assertion cannot catch a hardcoded value.**
   `test_status_says_queue_depth_is_capacity_and_what_the_monitor_sees:360`
   asserts `queue_capacity == queue_depth` for `builder`, where both are 1; a
   literal `"queue_capacity": 1` would pass. Assert it on a role with a
   non-default depth (aux is 4).

## Notes

**Why check 2 is not a blocker.** The protocol lists "a failed gate" as a
blocker. This one is a self-contradictory criterion inside the brief, was
disclosed with its evidence in the report *before* the verdict line was
claimed, and satisfying it literally would make a playbook whose run check
silently vanished load cleanly — the exact failure H-006 was filed about. Every
gate that tests the work rather than the brief is green.

**The report's §3 NOT PROVEN holds up under checking.** I spot-checked its
strongest self-limiting claim: the installed daemon serving the mission is
still the mission-1 build —
`/home/msi/.local/share/uv/tools/hands/.../hands/spool.py:91` reads
`ORIGINS = frozenset({"driver", "playbook", "cli"})` and its `playbook.py` has
15 `only_if_run_in` hits. So "none of U1–U7's code has ever run outside the
test suite" is accurate as written. The real spool corroborates the rest:
`~/.hands/jobs/` and `~/.hands/inbox.jsonl` carry a genuine
`job.held` → `gate.decided` → `job.denied` cycle, an approval, `job.done`s and
a heartbeat (now 9 jobs / 10 events, including the `playbook.rule` that chained
this review).

**What §3 does not cover.** Should-fix 2, 3, 4, 6 and 8 are not in it. Items 2
and 4 are behaviours, not coverage gaps, so §3 was the wrong place for them
anyway; item 3 is the one place the report claims more than the tests deliver
("prove the load-time refusals one at a time"). Should-fix 1, 5 and part of 7
*are* in §3 (items 11, 3, 1) and were accurately described.

**Append-only ledger.** H-002, H-003 and H-005 carry `Status: fixed` with no
sha because DESIGN v3.1 closed them rather than a unit; H-007's and H-008's
`fixed` lines gained their shas in the later `meta:` commits. Each entry's last
`Status:` line is its current one, as the report says. All eight findings have
one. Not a defect — recording it so a later reader does not read the stale
`Status: open` lines as current.

**Design-side staleness, for a finding, not for a builder.** `DESIGN.md:258`'s
prose example still reads `hands jobs [--role builder] [--grep "run 3"]
[--since 2d]` with no `--origin`, though the §4 command table at `DESIGN.md:159`
has it. Builders do not edit `DESIGN.md`; this needs a memo.

**`pipeline.resumed` is a new event kind.** §11 enumerates kinds in prose and
does not list it, but `EVENT_KINDS` is documented as closed-and-extensible and
`gate.requested`/`notify`/`job.denied` already extend that prose list; the unit
brief mandates the kind by name. It is not matched by `--for stop,held`, so a
resume cannot spuriously wake the driver. Conformant.

**Order deviation.** U3 landed before U1/U2. `meta/plan.md` and
`FINAL-REPORT-2.md` §1 both record it with the reason (the mission base was red
until the §10 fixture matched the design). Verified: the base `59e7ac7` rewrote
DESIGN §10's example, and `test_the_fixture_is_section_10s_example_verbatim` is
byte-exact against it. Correct handling.

## Per-commit verdicts

The ≤12-line sub-agent reports, verbatim, in the order the units landed.

---

sha 34b4ede — U3 `run = "<expr>"` replaces `only_if_run_in` (DESIGN §10 Example/Placeholders/Actions; H-006)
1. unit/sections: matches `meta/BUILDER-2-PROMPT.md` U3 exactly (run key, expression grammar, load-time refusal when `auto_runs` empty or group undefined, `only_if_run_in` refused naming `run`, `docs/PLAYBOOK.md` updated, §10 example still passes end to end). Files: `src/hands/playbook.py`, `docs/PLAYBOOK.md`, `tests/test_playbook.py`, `tests/fixtures/playbook_example.toml`.
2. test-first: PASS — with `src/hands/playbook.py`+`docs/PLAYBOOK.md` reverted to 34b4ede^ and tests kept, `uv run pytest tests/test_playbook.py -q` is RED: 20 failures, first `PlaybookError: ...unknown key(s) in rule 1: run; known keys are on, verdict, then, role, context, prompt, message, only_if_run_in`. Load-bearing new cases that fail for product reasons (not just the fixture): `[run on a non-send]`, `[run with no auto_runs]`, `[run with an empty auto_runs]`, `[run naming a group the verdict does not define]`, `[only_if_run_in at all]`, and `test_the_run_key_is_read_not_the_prompt`.
3. scripts/check: green — `== pytest ==` … `494 passed in 30.61s`, `== cli smoke ==`, `check: green` (ruff: `All checks passed!`).
4. conformance: PASS — I re-extracted DESIGN §10's fenced example and diffed it against `tests/fixtures/playbook_example.toml`: **IDENTICAL** byte for byte (including the dropped `builder.limited` rule and the added `builder.failed` rule). `run_ref()` narrows the §10 placeholder grammar to a verdict named group with optional `+k`; `PlaybookEngine` now reads `rule.run` instead of re-parsing the prompt. Forbidden files: none — `DESIGN.md`, `meta/plan.md`, `meta/CHECKPOINT.md` untouched (DESIGN.md last changed in 59e7ac7, the plan kit, which already carried `run = "{n+1}"` and the H-006 paragraph).
5. NOT proven / concerns:
   - Four of the nine new BAD_PLAYBOOKS cases assert only the substring `"run"` in the message (`run that is not an expression`, `run naming a job field`, `only_if_run_in at all`, `only_if_run_in on its own`). Since `only_if_run_in` literally contains "run", these assertions are near-vacuous — three of them (`not an expression`, `job field`, `only_if_run_in on its own`) still PASSED against the reverted pre-commit code, i.e. they are not load-bearing. The behaviours are real in the code; the tests just don't pin the right message.
   - `run` is opt-in: a `send` rule that omits `run` starts whatever the prompt says with **no** `auto_runs` check at all. That matches the §10 wording ("a rule with `run` but no `auto_runs` … is refused"), but nothing in this commit or §10 forces a `send` to carry `run`, so "runs hands may start on its own" is not structurally enforced.
   - `parse_ref` accepts `{n-1}` so `run = "{n-1}"` is legal; §10 only shows `{n+1}`. Harmless, undocumented in `docs/PLAYBOOK.md` (which says "optional integer arithmetic: `{n}` or `{n+1}`").
   - Out of this commit's scope, but adjacent: at `main`, `meta/findings/FINDINGS.md` H-006 has **two** Status lines — a stale `Status: open` immediately followed by `Status: fixed 34b4ede …`. Introduced by a later parent commit, not by 34b4ede.

---

sha a67c4b0 — U1 "limits: a limit resume's origin is `limit`, and `jobs --origin` filters on it" (DESIGN §6, §4)
1. unit/sections: `meta/BUILDER-2-PROMPT.md:63` U1 = ORIGINS gains `limit`; limit resumes filed with it; `hands jobs --origin <o>` filters; `resume` inbox event carries `origin`; `resumed_from` unchanged; gate = tests for filter + limit-resume record. DESIGN.md:215 (`origin (driver|playbook|cli|limit)`), :240 (`origin = limit` and `resumed_from` set), :159 (`jobs [--role r] [--origin o] …`), :659 (v3.1 changelog names H-004). H-004 read at FINDINGS.md:112-142.
2. test-first: PASS — with only the 6 product files reverted to a67c4b0^ and tests kept, 5 RED: `AssertionError: assert 'playbook' == 'limit'` (test_limits.py::test_a_limited_builder_is_resumed_with_the_resume_line), `KeyError: 'origin'` (test_limits.py::test_one_inbox_event_per_limit_and_per_resume and test_playbook.py::test_a_resume_rule_on_an_orphan_resends_the_resume_line), `hands.spool.SpoolError: origin must be one of ['cli', 'driver', 'playbook'], got 'limit'` (test_library.py::test_jobs_filters_by_origin), `SystemExit: 2` (test_library.py::test_jobs_refuses_an_origin_outside_section_6s_vocabulary). Tree restored with `git checkout a67c4b0 -- .` (clean).
3. scripts/check: green — `== ruff ==` / `All checks passed!` … `== pytest ==` / `496 passed in 28.94s` … `== cli smoke ==` / `check: green`.
4. conformance: PASS — `ORIGINS = frozenset({"driver", "playbook", "cli", "limit"})` (spool.py:93) matches §6:215; `RESUME_ORIGIN = "limit"` used for both the enqueued job and the `resume` event payload (limits.py:465, :477) matches §6:240; §10 rule-issued resume keeps `origin = ORIGIN` = `playbook` (playbook.py:831) and is asserted by a test, so H-005 is genuinely untouched; `--origin` added to §4's `jobs` in cli.py:167-171 + api.py:238-239 with refusal naming all four; `origin` was already in `_SUMMARY_FIELDS` so filtered output is self-evidencing; `resumed_from` untouched. FINDINGS.md appends a `Status: fixed` line while leaving `Status: open` — that is the brief's stated append-only ledger convention (same shape as H-006 at :202-203), not a defect. Forbidden files: none (DESIGN.md, meta/plan.md, meta/CHECKPOINT.md all absent from `git show --stat`).
5. NOT proven / concerns: (a) no test covers the `limit` origin flowing through `hands status` or through daemon/api `send` — only `create_job` direct writes and the limit manager; a client is still free to pass `origin="limit"` to `send` since api.py:139 does no client-side narrowing, and nothing forbids it (DESIGN doesn't either, so this is a note, not a defect). (b) `test_jobs_filters_by_origin` builds the `limit`/`playbook` rows via `spool.create_job` rather than by driving the real limit manager, so the filter test and the resume-record test are independent — acceptable, since test_limits.py covers the real path. (c) DESIGN.md:258's example line still shows `hands jobs [--role builder] [--grep …] [--since 2d]` without `--origin`; that's DESIGN's own prose, which builders must not edit, so it is a design-side staleness for a finding, not a commit defect. (d) §9's remote face is deferred with no code, so H-004's "the §9 remote face does not know the value" concern is untestable here.

---

sha 8448b6f — U2 `resume_line` is optional; absent, a limit resume re-sends the prompt (DESIGN §6 "Limits", §10 "Actions", §13)
1. unit/sections: matches `meta/BUILDER-2-PROMPT.md` U2 ("`role.resume_line` has no default… `hands doctor` reports which behaviour each role has. Gate: tests for both") and finding H-008 (`meta/findings/FINDINGS.md:245`). DESIGN.md §6 already carries the v3.1 rule: builder gets `role.resume_line` "when the config sets one… otherwise the limited job's own prompt (…H-008); for aux it is always the same prompt again"; §10 says `resume` = "the same prompt again, or the role's resume line when configured".
2. test-first: PASS — reverting only `src/hands/{config,doctor,limits,playbook}.py` to `8448b6f^`, keeping tests, gives RED: 6 failures — `test_limits.py::test_a_limited_builder_without_a_resume_line_is_sent_its_own_prompt_again`, `test_config.py::test_full_config_loads_every_field` (AttributeError: no `resume_prompt`), `test_config.py::test_every_optional_key_has_a_default`, both new `test_doctor.py` role-check tests, and `test_playbook.py::test_a_resume_rule_without_a_resume_line_resends_the_jobs_own_prompt` (`assert [('Resume WORKPLAN.md','clear')] == [('p','clear')]`). Both branches, aux-ignores-a-line, and doctor are each covered by a distinct test.
3. scripts/check: green — `All checks passed!` / `501 passed in 33.40s` / `== cli smoke ==` / `check: green`.
4. conformance: PASS — §6 limit resume (`src/hands/limits.py:459`) and §10 `resume` action (`src/hands/playbook.py:806`) both call `role.resume_prompt(job.prompt)`; aux path untouched in both. `hands doctor` role detail gains a `…(§6)` line. docs/INTEGRATION.md and docs/PLAYBOOK.md updated to match. Forbidden files: none — commit touches only docs/, meta/findings/FINDINGS.md, src/, tests/.
5. NOT proven / concerns:
   - One-place claim VERIFIED: `grep` over `src/` + `driver/` shows `resume_line` is read outside `config.py` nowhere; the only consumers are the two `resume_prompt` call sites plus `resume_behaviour` for doctor.
   - `resume_line = ""` silently becomes `None` (`_opt_str(...) or None`, `config.py:356`) i.e. "re-send the prompt". Defensible, but it is **untested and undocumented** — the doctor test helper only writes the key when truthy, and docs/INTEGRATION.md says only "optional, no default". A project that sets an empty line gets the other behaviour with no error or warning.
   - Not covered: a §10 `resume` on an **aux** job with a `resume_line` set (only the §6 limits path has that guard test).
   - H-008 now ends with a stale `Status: open` line immediately followed by `Status: fixed —` (FINDINGS.md:280-281). This matches the existing repo convention (H-002, H-006 do the same), but unlike those it cites no sha.

---

sha 267ee01 — U4 `hands pause` files a `stop` event, `hands resume` a `pipeline.resumed` (DESIGN §11, §10, §4)
1. unit/sections: Commit body and `meta/BUILDER-2-PROMPT.md:81` agree — U4 (H-007, §11); body adds §10 "stop → resume cycle" and §4. §11 asks doctor to check the wake path with "a fake event"; H-007 said no command filed one (`pause` set `state.paused` and wrote nothing). Fix matches the finding's direction and the unit text exactly.
2. test-first: PASS — 7 new tests + 1 strengthened, incl. the mission gate `tests/test_wake.py::test_wait_for_stop_wakes_on_a_hand_pause` (end-to-end `wait --for stop,held` then `ok("pause")`). Reverting only `src/hands/{playbook,spool,doctor}.py` to 267ee01^ with tests kept → RED, 9 failures: gate test hangs to `asyncio.exceptions.CancelledError` (30s wait never returns), `test_a_resume_files_a_pipeline_resumed_event`, `test_a_hand_pause_notifies_like_any_other_stop`, 5 playbook tests (`ValueError`/unpack), and `test_the_wake_procedure_offers_hands_pause` (`'paused by human' not in out`). Restored to 267ee01, tree clean.
3. scripts/check: green — `== ruff ==  All checks passed!` / `510 passed in 31.38s` / `== cli smoke ==` / `check: green`.
4. conformance: PASS — §11 enumerates kinds in prose ("job terminal, monitor event, playbook rule fired, stop (reason), gate decided, limit/resume, heartbeat"); `EVENT_KINDS` is explicitly "Closed on purpose: a unit that needs a new kind adds it here", and precedent kinds (`gate.requested`, `notify`, `job.denied`) already extend the prose list, so `pipeline.resumed` is legitimately addable — and the unit brief mandates it by name. It does not collide with the existing job-level `resume` kind, does not widen the playbook rule vocabulary (`EVENTS` in playbook.py is a separate hardcoded tuple), and is not matched by `--for stop,held`, so a resume cannot spuriously wake the driver. `_unpause`'s new `if not self.state.paused: return` is safe because every `stop()` sets `paused=True`, so `resume` still clears a rule/job.held-caused stop. Forbidden files: none (DESIGN.md, meta/plan.md, meta/CHECKPOINT.md untouched; only FINDINGS.md under meta/).
5. NOT proven / concerns: (a) untested edge — `pause` while already stopped for a *different* reason passes `stop()`'s dedupe guard and overwrites `state.stop_reason`/`stopped_at` with `paused by human`, losing the original reason from `hands pipeline` (it survives only in the inbox) and emitting a second stop notification; no test covers it. Low severity, but it is a real behaviour change vs the old flag-only pause. (b) The §11 wake check itself is inherently human-run (needs an idle interactive Claude Code session); only the event-filing half is machine-proven. (c) H-007's `Status: fixed` line carries no sha, unlike the other fixed findings (H-003/H-005/H-008) — self-reference, cosmetic. (d) No doc outside DESIGN.md/FINDINGS.md enumerates event kinds, so nothing else was left stale.

---

sha 44c345b — U5 `hands notify --test` sends one real ntfy message and prints the status (DESIGN §4 command table row `notify`, §11 Notifications)
1. unit/sections: matches `meta/BUILDER-2-PROMPT.md` U5 ("one message to configured topic through real transport; prints HTTP status; refuses when `ntfy_topic` unset; transport mocked; in `hands --help`"). §4 row and §11 ("quiet_hours delays them; actions are never delayed") both read on disk and both honoured.
2. test-first: PASS — 8 new tests in `tests/test_wake.py` + `SECTION_4` in `tests/test_daemon.py`. Reverting only `src/hands/api.py`+`src/hands/cli.py` (notify.py kept, so imports resolve) makes all 8 RED: `SystemExit`/`AttributeError: 'Api' object has no attribute 'notify'`. Reverting all product files also reddens `test_daemon.py::test_help_lists_every_command_of_section_4` and `..._api_method_names_are_exactly_the_command_names` (`At index 9 diff: 'open' != 'notify'`). Tree restored with `git checkout 44c345b -- .` (clean).
3. scripts/check: green — `== ruff ==\nAll checks passed!` / `518 passed in 36.49s` / `== cli smoke ==` / `check: green`.
4. conformance: PASS — client-side (no daemon needed, like `doctor`), `Api.notify` mirrors it via `daemon.notifier.post` so §9's one-method-per-command test holds; refusal raises `NotifyError` *before* any send (test asserts `posts.sent == []`, exit 1, message names `ntfy_topic` and `demo.toml`); exactly one `send` call per invocation; quiet-hours bypass covered by a playbook with `00:00-23:59`. Forbidden files: none (7 files: README.md, docs/INTEGRATION.md, src/hands/{api,cli,notify}.py, tests/{test_daemon,test_wake}.py — DESIGN.md, meta/plan.md, meta/CHECKPOINT.md untouched). No real network request was made; tests monkeypatch `hands.notify.http_post`.
5. NOT proven / concerns:
   - Non-2xx is handled, but as a *failure*, not a printed status: `http_post` calls `response.raise_for_status()` and `send_test` wraps any exception in `NotifyError` → exit 1. So the advertised "prints the HTTP status" only ever prints a 2xx. No test drives an actual HTTP error status; the failure test injects `OSError("no route to host")`.
   - `http_post` itself is never executed under test (all tests replace it), so the new `-> int` return (`int(response.status_code)` read after the `async with` client closes) is unverified against real httpx; only the stand-in `StatusPosts` proves the status plumbing.
   - `post` is typed `Callable[..., Awaitable[Any]]`, so a transport returning `None` yields `"status": None` / `ntfy None` in the readable block. Cosmetic, unguarded.
   - End-to-end delivery to a real topic remains unproven by construction — README/`docs/INTEGRATION.md` say so explicitly ("`hands notify --test` is the command that changes that, and it has not been run here"), which is accurate.
   - No substantiated defect found.

---

sha bde33fe — U6 "status: say `queue_depth` is capacity and what the monitor can see" (DESIGN §4 `status` row, §5)
1. unit/sections: matches `meta/BUILDER-2-PROMPT.md` U6 ("document `queue_depth` as capacity (rename nothing; add a one-line note in human output and a `queue_capacity` alias in JSON if cheap). Gate: test on the output"). DESIGN.md §4 status row literally says "(`queue_depth` is capacity; `queued` is contents)"; §5 defines stall as "no progress and no liveness for `monitor.stall_minutes`" and "A busy-wait on a nested run is not a stall".
2. test-first: PASS — one new test `tests/test_daemon.py::test_status_says_queue_depth_is_capacity_and_what_the_monitor_sees`. Reverting daemon.py only → `E KeyError: 'queue_capacity'` (line 360). Reverting cli.py only → `AssertionError: assert 'capacity' in '...monitor  builtin (built-in); stall after 40.0m...'`. Both product edits are load-bearing; restored after.
3. scripts/check: green — `All checks passed!` / `519 passed in 30.79s` / `check: green`.
4. conformance: PASS — `queue_depth` is genuinely capacity: `daemon.py:328 _check_depth` compares `len(self._waiting[role]) >= config.role(role).queue_depth` and refuses; `cli.py:360` prints `queued {len(queued)}/{queue_depth}`. `queue_capacity` is the same value, additive, `queue_depth` untouched (driver + §13 key intact). Monitor wording is true of `monitor.py:_builtin`/`_sample`: one combined sample of transcript mtime, `subagents/` mtime, `cpu_ticks`, `.git/index` mtime, HEAD, stash — unchanged for `stall_minutes` → stall; CPU ticks mean a busy-wait keeps the sample moving. Forbidden files: none (only docs/INTEGRATION.md, driver/CLAUDE.md, src/hands/cli.py, src/hands/daemon.py, tests/test_daemon.py).
5. NOT proven / concerns:
   - The monitor note is printed unconditionally, but `monitor.status()` reports `source: "ops"` when `ops.monitor_cmd` is set, and the ops script is invoked with only `--pids/--transcript/--base` (`monitor.py:403-415`) — `stall_minutes` is never passed to it. So on the ops path "stall = no progress and no liveness for 40m" describes hands' built-in rule, not the script that actually decides. Pre-existing ("stall after 40m" had the same flaw) but the new wording is more specific and therefore a larger claim. Not covered by any test; the test only exercises `source: builtin`.
   - `stall_minutes = 0` means detection is off (`monitor.py:478`) yet status would read "stall = no progress and no liveness for 0m". Untested.
   - "it does not judge the work" sits alongside §5 tripwires, which do evaluate each new commit against rules (plan touched, landed on `main`, stash grew). Defensible as "does not judge quality", but the line is absolute.
   - No test asserts the JSON `queue_capacity` tracks a non-default value (e.g. aux's 4) or that no consumer regressed on `queue_depth`; alias equality is asserted only for builder where both are 1 — a hardcoded `"queue_capacity": 1` would also pass.
   - Doc edits (docs/INTEGRATION.md, driver/CLAUDE.md) are ungated by any test.

---

sha d973ece — U7 "driver: retire bootstrap mode" (DESIGN §18 "Bootstrap mode retired"; body also cites §12, §14; §15 kept as history)
1. unit/sections: matches `meta/BUILDER-2-PROMPT.md` U7 scope exactly. Diff: `bootstrap/dispatch.sh` deleted (47 lines), `driver/CLAUDE.md` bootstrap section → "Starting a mission", `driver/README.md` drops the cp/remove-dispatch steps, `driver/settings.json` drops `"Bash(./dispatch.sh:*)"`, `driver/hooks/bash_guard.py` drops `"./dispatch.sh"` from `ALLOWED_FIRST_WORDS` + 4 selftest cases (3 replaced with real `~/.hands/jobs/...` cases), `tests/test_docs.py` +46. DESIGN §18 last bullet states exactly this; §15 untouched, consistent with the body.
2. test-first: PASS — two new tests, `test_the_bootstrap_dispatcher_is_gone_from_the_repo` (greps every `git ls-files` path, excluding `DESIGN.md`/`meta/`, for a runtime-built `"dispatch"+".sh"` so the test isn't its own hit) and `test_the_driver_kit_does_not_mention_bootstrap_mode`. With only the product/driver files reverted to d973ece^ and tests kept: `2 failed` — `AssertionError: bootstrap/ must be deleted (§18)` and the driver-kit one on `driver/CLAUDE.md` still containing `# during bootstrap: ./dispatch.sh`. Load-bearing in both directions.
3. scripts/check: green on a clean `git reset --hard d973ece` tree — `== pytest == ... 521 passed in 29.00s`, `== cli smoke ==`, `check: green`. Standalone guard: `python3 driver/hooks/bash_guard.py --selftest` → `selftest: 52/52 ok` (exit 0), matching the commit body's "52/52".
4. conformance: PASS — `grep -rn 'dispatch\.sh' --include='*' .` returns 13 hits, all in `DESIGN.md` (6, §15/§18 history) and `meta/` (plan.md 1, CHECKPOINT.md 3, BUILDER-2-PROMPT.md 3). Zero in code, docs, driver files. A case-insensitive `bootstrap` grep likewise hits only DESIGN.md, meta/, and the new tests' own identifiers. Forbidden files: none — DESIGN.md, meta/plan.md, meta/CHECKPOINT.md are not in the commit's 6-file stat.
5. NOT proven / concerns (all minor, no substantiated defect):
   - Report's "README.md and docs/INTEGRATION.md needed no edit" is substantiated: `git show d973ece^:docs/INTEGRATION.md` has zero `bootstrap`/`dispatch` hits; `d973ece^:README.md` has one hit, line 3 `"a user daemon and a CLI that dispatch prompts"` — the English verb, not the script. Nothing to remove.
   - New doc claims spot-checked against code/design and hold: `hands send --role builder --context clear` is real (`--context {clear,keep}` in `--help`), and "hands sleeps until the reset and re-sends it itself" matches DESIGN §6/H-005 ("§6 is the sole owner of the limit resume").
   - Test coverage is narrower than the prose: the repo-wide grep test only looks for the literal `dispatch.sh`, not the word `bootstrap`; the `bootstrap` check covers only `driver/CLAUDE.md` and `driver/README.md`, so top-level `README.md`/`docs/INTEGRATION.md` are unguarded against a future reintroduction (harmless today since neither ever mentioned it).
   - `HISTORY = ("DESIGN.md", "meta/")` is used with `str.startswith`, so a future `DESIGN.md.bak` would be silently exempt. Cosmetic.
   - Not proven by me: that the rewritten driver instructions actually work in a live driver session (no driver run is exercised by any test); and `driver/README.md` now has an awkwardly short rewrapped line ("...read-only git, or a read-only") — cosmetic only.
