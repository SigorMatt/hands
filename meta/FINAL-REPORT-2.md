# FINAL REPORT — mission 2 (the shakeout)

Builder's report for the mission in `meta/BUILDER-2-PROMPT.md`. Written at tip
`d3c0d6d` (+ this commit). Same rule as mission 1: every claim below is backed
by a named test, by a command I ran while writing this, or it is in §3 NOT
PROVEN. `DESIGN.md` is v3.1; §18 lists what the architect changed, and this
mission landed the code those changes imply. This report does not restate the
design.

Mission 1's report is `meta/FINAL-REPORT-1.md`; its §3 is still the main list
of what hands cannot claim. §3 below says which of its twelve items mission 2
moved and carries the rest forward by reference rather than retyping them.

One fact that mission 1 could not state and this one can: **a real `claude -p`
has now run under hands** — this mission was dispatched by `hands send` and
this builder is a job in the spool. That is an observation of the machine, not
a test result, and §3 item 1 bounds exactly what it does and does not prove.

---

## 1. What changed

Eight units, one commit each, all pushed. Listed in the order they **landed**,
which is not the order the mission brief numbers them.

**U0 Plan — `3c5d880`** (`meta: mission 2 plan, checkpoint and H-008 in the
ledger`). `meta/plan.md` rewritten for mission 2, `meta/CHECKPOINT.md` reset,
and **H-008 entered in `meta/findings/FINDINGS.md`** — it was filed by the
architect in DESIGN v3.1 §18 and had no ledger entry at all, so without U0 the
mission's "every finding H-001..H-008 has a current `Status` line" acceptance
check could not even be evaluated. `meta/` only.

**Order deviation: U3 ran first, before U1 and U2.** A reviewer walking `git
log` sees `34b4ede` land before `a67c4b0` and should not read that as a skipped
unit. The mission base `59e7ac7` (`plan: mission 2 kit`) was already **red**:
`tests/test_playbook.py::test_the_fixture_is_section_10s_example_verbatim`
compares `tests/fixtures/playbook_example.toml` against DESIGN §10's example
byte for byte, and the kit commit rewrote that example to the `run` key. No
unit could have reached a green gate until U3 landed. The deviation was written
into `meta/plan.md` in U0, before any unit ran. Nothing else about the units
changed; U1, U2, U4–U7 ran in their briefed order after it.

**U3 Explicit `run` key — `34b4ede`** (`playbook: an explicit `run = "<expr>"`
key replaces only_if_run_in`; H-006, §10). `Rule.run`, `run_ref()` (the
expression grammar: one named group of the rule's own `verdict`, `{n}` or
`{n+1}`), `run_number()` evaluating that key instead of inferring a run from
the prompt, `_act_send` reading `rule.run`. A rule with `run` is refused at load
when `[limits] auto_runs` is absent or empty, when the expression names a group
the rule's `verdict` does not define (including a rule with no `verdict`), when
`then` is not `send`, or when the value is not an expression of that grammar.
`only_if_run_in` is refused **before** the unknown-key check, with a message
naming `run`. `docs/PLAYBOOK.md` updated; the §10 fixture regenerated from the
design's own bytes.

**U1 Origin `limit` — `a67c4b0`** (`limits: a limit resume's origin is `limit`,
and `jobs --origin` filters on it`; H-004, §6, §4). `ORIGINS` gains `limit`;
`LimitManager._resume` files with it and its `resume` inbox event carries
`origin`; a §10 `resume` rule on `failed`/`orphaned` stays `playbook` and its
event carries `origin` too. `hands jobs --origin <o>` added — the filter did
**not** exist from mission 1's U9, so this unit added the api parameter, its
validation against the four-value vocabulary, the CLI flag and the ARGS
mapping. `resumed_from` unchanged. `driver/CLAUDE.md`'s `jobs` flag list
updated (it is the only doc that lists them).

**U2 Resume line optional — `8448b6f`** (`config: `resume_line` is optional;
absent, a limit resume re-sends the prompt`; H-008, §6). `resume_line: str |
None` with no default (`DEFAULT_RESUME_LINE` deleted). The rule lives in one
place, `RoleConfig.resume_prompt(prompt)`, which both §6's limit resume
(`limits.py:459`) and §10's `resume` action (`playbook.py:806`) call, so the two
paths cannot drift: builder gets the line when set, otherwise the limited job's
own prompt; aux is unchanged and ignores a `resume_line` set on it. `hands
doctor`'s role check prints which behaviour each role has
(`RoleConfig.resume_behaviour`), because a limit is otherwise the first time
the difference is visible. `docs/INTEGRATION.md`, `docs/PLAYBOOK.md` updated.

**U4 Pause files an event — `267ee01`** (`playbook: `hands pause` files a `stop`
event, `hands resume` a `pipeline.resumed``; H-007, §11). `pause()` now goes
through the engine's own `stop()` with reason `paused by human` and `by = hands
pause`, so it files the `stop` inbox event and notifies like any other stop —
and inherits `stop()`'s "one stop, one notification", so a second pause files
nothing. It works with no playbook file at all, which is what makes it usable
as the install-time wake check. `pipeline.resumed` added to `EVENT_KINDS` and
filed by `hands resume` and by a send that un-pauses (`by = "a send"`);
resuming an un-paused pipeline is a silent no-op. `paused_by` stays `"cli"` for
a hand pause so `hands pipeline` still distinguishes it from a rule stop. A
resume is inboxed but not published — §11 does not list it. Doctor's wake
procedure now offers `hands pause` first and keeps the gated send.

**U5 `hands notify --test` — `44c345b`** (`notify: `hands notify --test` sends
one real ntfy message and prints the status`; §4). `notify.send_test`,
`NotifyError`, `TEST_TITLE`, `DEFAULT_TEST_MESSAGE`; `http_post` now returns the
status code. It runs **in the client, not over the socket** — doctor's own
reason: §14 step 1 is the install-time proof and must work before `handsd` is
up. `Api.notify` is the §9 half for daemon-only callers and calls the same
function; the readable output says the message was "sent by the CLI itself, not
handsd" so the situation stays legible. Quiet hours are deliberately not
consulted: §11 delays notifications, never actions. Refuses with exit 1, naming
`ntfy_topic` and the config file, when no topic is configured, and sends
nothing in that case. `driver/CLAUDE.md` was deliberately *not* given the
command — a driver session should not ping the human's phone.

**U6 Status wording — `bde33fe`** (`status: say `queue_depth` is capacity and
what the monitor can see`). `queue_depth` is unchanged in name, value and
meaning — the driver's key still reads — and a `queue_capacity` alias was added
to the JSON. The human output now says "capacity" out loud, and the monitor
line changed from "stall after 40m" (which implied more than §5 claims) to
"stall = no progress and no liveness for 40m", plus a note that a busy-wait on
a nested run is not a stall and that the monitor does not judge the work.

**U7 Retire bootstrap — `d973ece`** (`driver: retire bootstrap mode`). Deleted
`bootstrap/dispatch.sh`; the driver kit's "Bootstrap mode" section became
"Starting a mission" — `hands send --role builder --context clear "<fixed
kickoff line>"`, arm the background wait, read via `inbox`/`show`/`result`,
verify against the read-only clone, and a rate limit is §6's to resume, never
the driver's. `driver/README.md` no longer copies the script in and says
`hands` must be installed first; `driver/settings.json` dropped the
`./dispatch.sh` allow rule; `driver/hooks/bash_guard.py` dropped it from
`ALLOWED_FIRST_WORDS` and its self-test, and four stale
`~/.hands/bootstrap/<n>.json|.pid` example paths in that self-test were swapped
for current ones. `README.md` and `docs/INTEGRATION.md` needed no edit — neither
ever named the dispatcher or bootstrap mode, contrary to what the mission brief
assumed.

**U8 Final report — this commit.** `meta/FINAL-REPORT-2.md` only.

`meta/*` bookkeeping commits sit between the units and are not listed; every
unit is one sub-agent, one commit, pushed. No unit was retried, none was
blocked, none was yielded (the budget guidance named U6 then U5 as the ones to
drop; both landed). The orchestrator wrote no product code; it wrote the plan,
the checkpoints, the journal lines, H-008's ledger entry (`3c5d880`) and the
current `Status:` lines for H-001, H-002 and H-005 (`d3c0d6d`).

---

## 2. What the tests prove

488 tests at mission 1's tip (the number quoted in `meta/FINAL-REPORT-1.md` §4);
**521 now**, from the `./scripts/check` run in §5 below. +33. Every one of them
still runs against `tests/fake_claude.py` and `tests/fake_monitor.py`; nothing
in the suite talks to a network or to a real `claude`.

What the new tests actually carry, unit by unit:

**U3.** `tests/test_playbook.py::test_the_fixture_is_section_10s_example_verbatim`
is the only thing that ties `tests/fixtures/playbook_example.toml` to DESIGN
§10's bytes; it was confirmed red at the mission base and green after the
fixture was regenerated. `test_the_example_parses_into_the_rules_of_section_10`
now asserts `book.rules[1].run == "{n+1}"`. Eight new cases in the
`BAD_PLAYBOOKS` table prove the load-time refusals one at a time — `run` on a
non-`send` (message names `send`), no `auto_runs`, empty `auto_runs`, a group
the `verdict` does not define, a rule with no `verdict` at all, a literal `"3"`,
`{job.id}`, and `only_if_run_in` in two shapes (both asserting the message
contains `run`). `test_the_run_key_is_read_not_the_prompt` is the one that
carries H-006's actual claim: a prompt with *two* placeholders (`"run {n+1}
follows run {n}"`) is legal and `run = "{n+1}"` alone decides the check — the
inference is gone, not merely renamed. `test_the_section_10_example_end_to_end`
(run 2 → review → run 3 → run 4 outside `auto_runs` → stop) passes unchanged
with the new key, over a real daemon and socket.

**U1.** `tests/test_library.py::test_jobs_filters_by_origin` proves the new
filter selects; `::test_jobs_refuses_an_origin_outside_section_6s_vocabulary`
proves a misspelled origin is refused rather than silently matching nothing.
`tests/test_limits.py` proves a limit resume's *record* is `origin == "limit"`
and that its `resume` inbox event carries the same value;
`tests/test_playbook.py` proves an orphan-resume event is still
`origin == "playbook"`, so the two resume paths are distinguishable on the wire.
These are the only claims made: the filter, the two record values, the two
events.

**U2.** `tests/test_limits.py::test_a_limited_builder_is_resumed_with_the_resume_line`
and `::test_a_limited_builder_without_a_resume_line_is_sent_its_own_prompt_again`
are the two branches of H-008, both through `LimitManager` with an injected
clock; `::test_a_limited_aux_job_ignores_a_resume_line` pins that aux is
unchanged even when a config sets the key on it.
`tests/test_playbook.py::test_a_resume_rule_without_a_resume_line_resends_the_jobs_own_prompt`
proves §10's action reads the same rule as §6's. Two `tests/test_doctor.py`
tests prove `hands doctor` names the behaviour each role has.
`tests/test_config.py` proves `resume_line is None` by default. All were
confirmed failing before the code.

**U4.** `tests/test_wake.py::test_wait_for_stop_wakes_on_a_hand_pause` is the
mission's gate for H-007 and the strongest of this set: a real daemon on a real
socket, a `hands wait --for stop,held` armed, `hands pause` run, the wait
returns the `stop` event. `::test_a_resume_files_the_pipeline_resumed_event`
proves the inbox order (`stop`, then `pipeline.resumed`);
`::test_a_hand_pause_notifies_like_any_other_stop` proves exactly one
notification through a real daemon. At engine level:
`test_a_hand_pause_files_a_stop_event_and_notifies` (reason `paused by human`,
`by=hands pause`), `test_pausing_an_already_paused_pipeline_files_one_event`,
`test_a_pause_works_with_no_playbook_at_all`,
`test_resuming_a_pipeline_that_is_not_paused_files_nothing`, and the
send-unpause filing `pipeline.resumed` with `by="a send"`.
`tests/test_doctor.py::test_the_wake_procedure_offers_hands_pause` proves
doctor prints `hands pause` and `paused by human` and still prints `--gate` and
`deny <job>`. What none of them prove is in §3 item 4.

**U5.** Eight tests in `tests/test_wake.py`, every one with the transport
mocked — one message to the configured topic with the status printed, the
`--json` shape, the default message when `--test` has no argument, the refusal
with no `ntfy_topic` (exit 1, names the key and the config file, sends
nothing), `hands notify` with no `--test` (exit 1, names `--test`), a failed
publish reported with exit 1, no delay under a `quiet_hours` window covering
the whole day, and `Api.notify` sending through the daemon's own transport.
`tests/test_daemon.py`'s `SECTION_4` list gained `notify`, which is what keeps
`Api.COMMANDS`, `cli._PARAMS` and `hands --help` from drifting apart.

**U6.** One test:
`tests/test_daemon.py::test_status_says_queue_depth_is_capacity_and_what_the_monitor_sees`.
It asserts `queue_capacity == queue_depth` in the JSON (so the alias cannot
drift from the key it aliases), that `queued` is the contents, and that the
human output contains `capacity`, `queue_depth`, `no progress and no liveness`
and `busy-wait on a nested run is not a stall`. It is a test on *strings in the
output*: it proves the wording is there, not that the wording is true of a real
monitor.

**U7.** `tests/test_docs.py::test_the_bootstrap_dispatcher_is_gone_from_the_repo`
greps every `git ls-files` path, exempting only `DESIGN.md` and `meta/`, with
the needle built at runtime so the test file is not itself a hit — this is the
test that stands behind §5's acceptance check 2, and it encodes the same
exemption DESIGN §18 grants ("§15 stays as history").
`::test_the_driver_kit_does_not_mention_bootstrap_mode` covers the kit's prose.
The bash guard's self-test still passes 52/52, standalone and via
`tests/test_docs.py::test_the_driver_bash_guard_selftest_passes`.

Everything mission 1's §2 listed as proven is still proven; no test was
deleted, and the only assertions that changed are the three that the design
changed under them (the §10 example's rule list, `rules[1].run`, and
`resume_line`'s default).

---

## 3. NOT PROVEN

Mandatory section, and the honest one. Nothing here is a to-do list item I
forgot; each is a claim the tests do not make.

### What mission 2 changed about mission 1's list

**Item 1 ("everything that needs a real `claude`") no longer holds as
written — but read the bounds.** Mission 2 was dispatched by hands itself, and
the evidence is on this machine rather than in the suite. This builder session's
shell is a descendant of the job that started it:

    $ ps -o pid,ppid,cmd -p 1697917 1687693
        PID    PPID CMD
    1697917 1687693 claude -p --output-format stream-json --verbose --model opus
                    --dangerously-skip-permissions --permission-prompts none
    1687693    2675 /home/msi/.local/share/uv/tools/hands/bin/python
                    /home/msi/.local/bin/handsd --project hands

(PPID 2675 is `systemd --user`.) `~/.hands/jobs/` holds four real records: an
aux job that returned `VERDICT: hello` verbatim (`num_turns = 1`,
`total_cost_usd = 0.078…`), a denied gated aux job (`doctor wake check`), a
builder job that applied the mission-2 kit (`num_turns = 9`, `head_at_end =
59e7ac7…`), and this one, `state = running`. `~/.hands/inbox.jsonl` holds the
matching eight events, including a real `job.held` → `gate.decided`
(`decided_by: "driver"`, with the quote) → `job.denied` cycle, a real approval,
two `job.done`, and a heartbeat. The three recorded `transcript_path` values all
exist on disk. So: mission 1's acceptance gate 5a **has been run and passed**,
the §2 argv is accepted by the real CLI exactly as `runner._argv` builds it,
`session_id` / `--resume` addressing / `num_turns` / `total_cost_usd` /
`head_at_start`/`head_at_end` / the verbatim result are real-shaped, and the
systemd user unit of item 7 is **running** (item 7's "never started, never
enabled" is stale). What this still does **not** prove: no limit has been hit,
so item 3 is untouched; no job has failed or been orphaned in the real spool;
`hands open`, `hands tail` and `log -f` have not been run against these real
sessions (items 8 and 9 stand); the `.` case of the transcript dir is still
unwitnessed (item 2 stands — `-home-msi-git-hands` is one more witness for the
rules that already had witnesses, and none for the dot). And **none of the code
this mission wrote has ever run outside the test suite**: the installed daemon
serving this session is the *mission-1* build (`grep ORIGINS
…/site-packages/hands/spool.py` → `frozenset({"driver", "playbook", "cli"})`,
and `only_if_run_in` still appears 15 times in its `playbook.py`), so U1–U7's
behaviour is proven by tests only, exactly as if hands had never run.

**Item 4 (the driver wake path), the `hands pause` half:** fixed as a defect.
H-007 was right — `hands pause` wrote no inbox event and therefore could not
wake anything. It now files a real `stop` (U4), and
`tests/test_wake.py::test_wait_for_stop_wakes_on_a_hand_pause` proves a
`wait --for stop,held` returns on it. The **rest of item 4 is unchanged and
still open**: whether a finished background `Bash` task wakes an *idle*
interactive Claude Code session (§16) is exercised only through `hands wait`
in-process, has never been observed, and cannot be tested from inside this
repo. DESIGN v3.1 §18 records that open question as "answered: proven (§16)";
**this repository contains no evidence of that**, and nothing in mission 2
produced any. The architect's proof, whatever it was, is outside these tests.

**Item 6 (ntfy):** narrowed, not closed. `hands notify --test` now exists and is
the command that *would* prove delivery (U5; README and `docs/INTEGRATION.md`
now say so). It has never been run against a live topic from this repository —
see below.

**Items 2, 3, 5, 8, 9, 10, 11, 12 carry forward unchanged**, by reference to
`meta/FINAL-REPORT-1.md` §3. In particular item 5 (the ops-repo monitor script
contract has only ever been answered by `tests/fake_monitor.py`), item 10 (no
concurrency, endurance, large-spool or disk-full testing), item 11 (the §9
remote face does not exist) and item 12 (`--human-confirmed` is a declaration,
not authentication — and note `gate.decided` in the real spool above records
`decided_by: "driver"` on a decision a human made at a terminal, which is
exactly the confusion item 12 describes).

### New to mission 2

1. **No real HTTP request has ever left this repository.** Every ntfy test,
   including all eight of U5's, mocks the transport. The status code a real
   ntfy server returns, `raise_for_status` handling of a non-2xx, and whether
   the phone rings are all unverified. `Api.notify` is exercised as a method,
   never over an actual socket round trip.
2. **No limit has been hit under hands, still.** Both of U2's `resume_line`
   branches and U1's `origin = "limit"` are proven with an injected clock and a
   fake sleep; the daemon end-to-end test now pins `resume_line` in its config.
   The live `~/.hands/hands.toml` *sets* `resume_line` for the builder, so even
   if a real limit were hit today it would exercise the branch that was already
   the old default — the absent-`resume_line` branch that H-008 was filed for
   has no real-world exercise at all.
3. **`resume_line = ""` is treated as absent.** That is U2's choice, not
   something §6 states. A config that sets an empty string gets the re-send
   behaviour with no warning.
4. **`hands doctor`'s aux line for a role that sets `resume_line`** merely notes
   the key is unused rather than warning about it.
5. **`--origin driver` is never exercised against a real driver-issued send** —
   no client sets `origin="driver"` yet. The limit-origin job in the library
   test is filed straight into the spool rather than produced by a live
   `LimitManager` inside the daemon (the end-to-end limit path is covered
   separately in `tests/test_limits.py`, with a fake clock). No test asserts
   that a §9 remote face or an ntfy template renders the new `origin` key.
6. **`run` with a non-integer group text is untested.** It is reachable only via
   a `verdict` regex whose named group can match non-digits; the
   `PlaceholderError` path there has no test.
7. **The prose in `docs/PLAYBOOK.md` beyond the example block is not
   machine-checked.** `tests/test_docs.py` checks that every `hands <cmd>` named
   in the docs exists and that PLAYBOOK carries §10's example byte-for-byte; the
   surrounding explanation of the `run` grammar is unverified English.
8. **The status wording tests are string tests.** No real `claude` and no real
   `watch_monitor.sh` has ever produced a `hands status` block; the monitor
   fields come from `tests/fake_monitor.py`. Nothing verifies that the driver
   actually *parses* `--json` correctly — only that `queue_capacity` is present.
9. **Quiet-hours behaviour for a pause** is inherited from `Notifier` and
   covered by the existing quiet tests on the same `hands: the pipeline stopped`
   title; it is not re-tested end to end through the daemon.
10. **No real driver session has run the rewritten kit.** `driver/CLAUDE.md`'s
    new "Starting a mission" section and `driver/README.md`'s copy-paste recipe
    are checked only by the docs tests (every `hands <cmd>` they name exists) and
    by the bash guard's self-test — not by a live Claude Code session loading the
    new `driver/settings.json`.
11. **The mission-2 acceptance grep does not hold as literally written.** See §5
    check 2. This is a deviation, stated there with its evidence.

---

## 4. Findings status

`meta/findings/FINDINGS.md`, eight entries, all with a current `Status` line
(the ledger is append-only, so a change is an appended line, not an edit). Two
were closed by DESIGN v3.1 itself rather than by any code this mission wrote.

| id | current status | why |
|---|---|---|
| H-001 | **open** | The `.` case of the `~/.claude/projects` dir dashing still has no witness: no project directory on this machine comes from a dotted path, and mission 2 added none. Closing it is an observation, not a change. Blast radius unchanged (`hands tail` for a dotted cwd). |
| H-002 | **fixed — by DESIGN v3.1, not by a unit** | §6 now says the limit event's field is `error` (`system`/`api_retry`), which is what `runner._on_event` already read. No code changed; the `category` fallback stays because it costs nothing. |
| H-003 | **fixed — nothing to change** | A verification record from mission 1: all six flags §2 names exist in claude 2.1.268. Unchanged. |
| H-004 | **fixed `a67c4b0`** | DESIGN v3.1 §6 spells the vocabulary `driver\|playbook\|cli\|limit`; U1 added the value, filed limit resumes with it, put `origin` on both `resume` events and added the `jobs --origin` filter. |
| H-005 | **fixed — by DESIGN v3.1 §10 plus U3 (`34b4ede`)** | The design now states outright that §6 owns the limit resume and a `resume` rule on `builder.limited` is authorization that enqueues nothing — which is what mission 1's U7 already implemented. U3 removed the `builder.limited` rule from the §10 example fixture with the design; `test_a_limited_job_leaves_the_resume_to_section_6` keeps its own `LIMITED_BOOK` so the authorization path is still proven. |
| H-006 | **fixed `34b4ede`** | §10 took the explicit `run = "<expr>"` key; U3 implemented it with load-time refusals and refuses `only_if_run_in` by name. The inference from the prompt is gone. |
| H-007 | **fixed `267ee01`** | §11 named the procedure; U4 routed `hands pause` through `stop()` so it files the event and notifies, added `pipeline.resumed`, and gave doctor the `hands pause` wake check while keeping the gated send (still the only way to witness a real `job.held`). |
| H-008 | **fixed `8448b6f`** | Filed by the architect in DESIGN v3.1 §18 and **absent from the ledger until U0 entered it** in `3c5d880` — it is the one finding with no mission-1 provenance. U2 made `resume_line` optional with the rule in one place, `RoleConfig.resume_prompt`. |

Nothing was rejected, nothing tombstoned, nothing silently adapted. Every place
the design was silent is named in a commit body.

---

## 5. Acceptance

The mission brief's five checks. Four hold. The second does not hold as
literally written, and why is below — it is a deviation, not an oversight.

**1. `./scripts/check` green on the pushed tip.** Ran at `d3c0d6d` while
writing this; re-run with this commit before pushing.

    $ ./scripts/check
    == ruff ==
    All checks passed!
    == pytest ==
    ........................................................................ [ 13%]
    ........................................................................ [ 27%]
    ........................................................................ [ 41%]
    ........................................................................ [ 55%]
    ........................................................................ [ 69%]
    ........................................................................ [ 82%]
    ........................................................................ [ 96%]
    .................                                                       [100%]
    521 passed in 26.59s
    == cli smoke ==
    check: green

**2. `grep -rn 'dispatch.sh\|only_if_run_in' --include='*' .` returns only
ledger/report lines — DOES NOT HOLD as written.** `dispatch.sh` holds. The
`only_if_run_in` half cannot, and was not made to.

    $ grep -rn 'dispatch\.sh' --include='*' .
    DESIGN.md:572:      bootstrap/dispatch.sh          # v0 dispatcher used by mission 1 (§15)
    DESIGN.md:605:   `docs/ARCHITECT-INSTRUCTION.md`, and `bootstrap/dispatch.sh`.
    DESIGN.md:606:2. `dispatch.sh` v0 is hands before hands exists: ~20 lines that run
    DESIGN.md:612:   `dispatch.sh` with the fixed kickoff line, checks the spool later (a
    DESIGN.md:649:- Bootstrap sequence with `dispatch.sh` v0 and the driver from mission 1
    DESIGN.md:672:- Bootstrap mode retired: `bootstrap/dispatch.sh` and the driver's
    meta/journal.md:24:2026-09-11  U7 Retire bootstrap  d973ece  green (521 tests); dispatch.sh gone from code, docs and driver
    meta/BUILDER-2-PROMPT.md:98:and every `dispatch.sh` mention from `driver/CLAUDE.md`, `driver/README.md`,
    meta/BUILDER-2-PROMPT.md:100:`./dispatch.sh` allow rule; `driver/hooks/bash_guard.py` drops it from
    meta/BUILDER-2-PROMPT.md:101:`ALLOWED_FIRST_WORDS` and its self-test. Gate: `grep -rn dispatch.sh` over
    meta/BUILDER-2-PROMPT.md:115:- `grep -rn 'dispatch.sh\|only_if_run_in' --include='*' . ` returns only
    meta/plan.md:16:- [x] U7 Retire bootstrap — delete bootstrap/, purge every dispatch.sh mention

Every hit is `DESIGN.md` or `meta/`. DESIGN §18 says "§15 stays as history", so
the six design hits are the architect's own instruction, and `meta/` is the
builder's record. No code, doc or driver file names it, and
`tests/test_docs.py::test_the_bootstrap_dispatcher_is_gone_from_the_repo`
enforces that over every tracked path.

    $ grep -rn 'only_if_run_in' --include='*' .
    DESIGN.md:663:- H-006: `only_if_run_in` is replaced by an explicit `run = "<expr>"` key,
    docs/PLAYBOOK.md:115:`only_if_run_in`, the older spelling, is refused outright with a message naming
    src/hands/playbook.py:391:    if "only_if_run_in" in table:
    src/hands/playbook.py:396:            f'{where}: only_if_run_in is gone; §10 spells the check as run = "{{n+1}}" — '
    tests/test_playbook.py:276:    ("only_if_run_in at all", 'version = 1\n[limits]\nauto_runs = [2]\n[[rule]]\n'
    tests/test_playbook.py:278:     'prompt = "run {n+1}"\nonly_if_run_in = "auto_runs"', "run"),
    tests/test_playbook.py:279:    ("only_if_run_in on its own", 'version = 1\n[[rule]]\non = "builder.done"\n'
    tests/test_playbook.py:280:     'then = "stop"\nonly_if_run_in = "auto_runs"', "run"),
    meta/BUILDER-1-PROMPT.md:162:`{job.*}`, `only_if_run_in = "auto_runs"`; unmatched event, missing or
    meta/CHECKPOINT.md:8:hold as literally written (`grep only_if_run_in`, because U3's own gate
    meta/FINAL-REPORT-1.md:322:| H-006 | §10 never says which value `only_if_run_in = "auto_runs"` checks; U7 reads the prompt's single group placeholder and refuses anything else at load time | open | **architect** — an explicit `run = "{n+1}"` key would need no inference |
    meta/BUILDER-2-PROMPT.md:76:expression uses a group the rule's `verdict` does not define. `only_if_run_in`
    meta/BUILDER-2-PROMPT.md:115:- `grep -rn 'dispatch.sh\|only_if_run_in' --include='*' . ` returns only
    meta/findings/FINDINGS.md:198:## H-006 — §10 does not say which value `only_if_run_in = "auto_runs"` checks
    meta/findings/FINDINGS.md:205:    DESIGN.md:370  only_if_run_in = "auto_runs"   # {n+1} must be listed above, else stop
    meta/findings/FINDINGS.md:213:playbook whose `only_if_run_in` rule has anything other than exactly one such
    meta/findings/FINDINGS.md:215:ambiguity can never reach a running pipeline. `only_if_run_in` also takes no
    meta/findings/FINDINGS.md:224:expression names a group the `verdict` does not define; `only_if_run_in` is
    meta/plan.md:12:- [x] U3 Explicit `run` key — load-time check, `only_if_run_in` refused (H-006, §10)

Three of those hits are not history: `src/hands/playbook.py:391,396`,
`tests/test_playbook.py:276-280`, and `docs/PLAYBOOK.md:115`. **The mission's
two criteria conflict.** U3's own gate — from the same brief, and from DESIGN
§18 — is that a playbook written against the old key must be *refused at load
with a message naming `run`*:

    src/hands/playbook.py:391
        if "only_if_run_in" in table:
            # §10 replaced the inferred check with an explicit key (H-006). Naming
            # the replacement here is the point: an old playbook must fail loudly
            # rather than quietly lose the check it thought it had.
            raise PlaybookError(
                f'{where}: only_if_run_in is gone; §10 spells the check as run = "{{n+1}}" — '
                ...

A refusal keyed on a string takes the literal string; its two table tests take
it to assert the refusal fires; `docs/PLAYBOOK.md` takes it to tell an operator
why their playbook was refused. **The refusal was kept.** Deleting it to satisfy
the grep would make a playbook whose run check has silently vanished load
cleanly and chain unchecked runs — precisely the failure H-006 was filed about.
The honest reading of the criterion is "nothing *uses* `only_if_run_in`", and
that is true: it appears in the source exactly once, as the name of a thing that
is refused.

**3. `hands --help` lists `notify`.** Holds.

    $ uv run hands --help
    …
        status           daemon, roles, running jobs, monitor state
        notify           send one message to the configured ntfy topic (§4, §11)
        doctor           check the install end to end (§4, §14)

Pinned by `tests/test_daemon.py`'s `SECTION_4` list and
`test_help_lists_every_command_of_section_4`, so `Api.COMMANDS`, `cli._PARAMS`
and the help text cannot drift.

**4. `meta/FINAL-REPORT-2.md` exists with a non-empty NOT PROVEN section.**
Holds — this file; §3 has eleven new items plus the carried-forward eight.

**5. Every finding H-001–H-008 has a current `Status` line.** Holds.

    $ grep -n '^## H-\|^Status:' meta/findings/FINDINGS.md
    10:## H-001 — transcript path: the `.` case of the project-dir dashing is unwitnessed
    46:Status: open
    48:Status: open — no unit in mission 2 touched it, and nothing on this machine
    55:## H-002 — §6 calls the limit field an "error category"; on the wire it is `error`
    81:Status: open
    83:Status: fixed — by DESIGN v3.1 itself, not by a mission-2 unit. §6 now reads
    90:## H-003 — every flag DESIGN §2 names exists in claude 2.1.268
    111:Status: fixed — nothing to change
    115:## H-004 — §6's `origin` vocabulary has no value for a limit resume
    146:Status: open
    147:Status: fixed a67c4b0 — DESIGN v3.1 §6 spells the vocabulary `driver|playbook|cli|limit`.
    156:## H-005 — §6's automatic limit resume and §10's `builder.limited → resume` are the same resume
    186:Status: open
    188:Status: fixed 34b4ede — by DESIGN v3.1 §10 plus mission 2 U3. §10 now states
    198:## H-006 — §10 does not say which value `only_if_run_in = "auto_runs"` checks
    220:Status: open
    221:Status: fixed 34b4ede — DESIGN v3.1 §10 took the explicit key. Mission 2 U3:
    229:## H-007 — §11's "fake event" for the wake check has no command behind it
    259:Status: open
    260:Status: fixed 267ee01 — DESIGN v3.1 §11 named the procedure. Mission 2 U4: `hands pause`
    272:## H-008 — `role.resume_line` has a default, so a limit resume cannot re-send the limited prompt
    307:Status: open
    308:Status: fixed 8448b6f — mission 2 U2: `role.resume_line` is `str | None` with no default

(The earlier `Status: open` line under each entry is mission 1's; the ledger is
append-only, so the *last* line under an entry is its current status. §4 above
is that reading.)

Every unit is `[x]` in `meta/plan.md`; none blocked, none yielded.
