# FINAL-REPORT-9 — hands mission 9: close review 8

Mission: `meta/BUILDER-9-PROMPT.md`. Design: `DESIGN.md` v3.8, §25 (with §6,
§10, §11). Reviews closed: `meta/reviews/REVIEW-8.md` (`VERDICT: review
mission 8 blockers=0 should-fix=4`) should-fix 1–4, and the five decisions of
`meta/FINAL-REPORT-8.md` §5 as §25 resolves them. Findings: H-017 filed
(REVIEW-8 should-fix 2, status `fixed by DESIGN v3.8`, then closed on disk by
U1). H-014 gains two status paragraphs (U0, U1). H-016 is closed (U0).

Base `0ead876` (`plan: mission 9 kit (DESIGN v3.8)`) was **red**: 1 failed,
1423 passed. The failure was
`tests/test_playbook.py::test_the_fixture_is_section_10s_example_verbatim`,
because v3.8 added the two detector stop rules to §10's example and no unit in
the brief copied the block into its pinned copies. U0 carried H-016's
direction (copy the block, extend the rule list, drop the "carries neither
yet" sentence), so U0 could commit green. This deviates from the brief and is
recorded in `meta/plan.md`.

Tip `f96c88b` (U5, the last commit that changes a gate input; the U6 commit
that carries this report is meta only): **1435 passed**, `check: green`,
three consecutive runs by the builder before the U6 commit. Each unit's
sub-agent ran `./scripts/check` green three consecutive runs before its own
commit, and the builder ran three more on each unit's sha before the `meta:`
commit that followed it.

Seven units planned (U0–U6), seven landed. None blocked, none retried. Every
product unit is one commit. Each of U1–U4 is followed by a `meta:`
bookkeeping commit that touches only `meta/plan.md`, `meta/CHECKPOINT.md` and
`meta/journal.md`. U0 and U1 share one (`f0368f0`). U5's bookkeeping rides in
U6's commit together with this report. U0 is a `plan:` commit. The report was
drafted under `meta/drafts/` and moved in by U6's commit. Every `git add`
named explicit paths.

This report is a snapshot. Per DESIGN §20, a claim here that later expires is
corrected by an appended dated line, never by a rewrite.

---

## 1. What changed, by unit

**U0 — `1c17d84` `plan: mission 9 plan; H-014/H-016 v3.8 resolutions; H-017;
§10 example copies`** (§6, §10, §25; REVIEW-8 should-fix 2; FINAL-REPORT-8 §5
items 1, 2). `meta/plan.md`, `meta/CHECKPOINT.md`. H-014 gains a v3.8
paragraph quoting §6's reversed precedence and noting the runner still said
`done` until U1. H-016 is closed. H-017 is filed for §6's vocabularies, with
its code values checked by grep. §10's example is copied into
`tests/fixtures/playbook_example.toml` and the verbatim block of
`docs/PLAYBOOK.md`. `test_the_example_parses_into_the_rules_of_section_10`
now expects `monitor.task_killed → stop` and `monitor.orphan_processes →
stop`. The brief's `meta/prototypes/` ruff exclude was already absent at the
base (removed by mission 8 U6 `a93e3a7`), so `pyproject.toml` is unchanged.

**U1 — `4da83f8` `runner: termination line wins over success; §6
vocabularies pinned`** (§2, §6, §25; FINAL-REPORT-8 §5 item 1; REVIEW-8
should-fix 2; H-014, H-017). `_failure_reason` returns `harness_terminated`
whenever stderr carried the terminating line, with no exception for a
`success` result. `_final_state` still decides `killed` and `limited` first.
The anchored, case-sensitive matcher is unchanged. A new constant,
`hands.gates.DECIDED_BY` (`cli|driver|phone`), holds the available deciders.
§8 still names `button`, so its row stays in `DECIDERS`, marked unavailable,
and `check_decider` refuses it. `docs/INTEGRATION.md` names the full
`failure_reason` list, the `decided_by` list and the precedence rule.

**U2 — `7992c4d` `runner, phone, cli: review 8 should-fix 1, 3, 4`** (§4, §5,
§9, §11, §24, §25).
- SF1: a new test drives `main()` against a real daemon and socket. No
  command that reaches the socket route returns a non-zero code today (the
  client answers `notify` itself). The test therefore swaps
  `hands.cli.exit_code` for a spy that returns 7 for `pipeline`. There is no
  product change to `cli.py`.
- SF3: in group mode, `runner._last_resort` calls `os.killpg` only when
  `group_pids(job.pid)` is non-empty, as `_kill_group` does.
- SF4: the phone reconnect warning logs the exception type, plus `HTTP
  <status>` when the exception has a response with an integer status code.
  The exception text, which carries the URL, is not logged.

**U3 — `fd6ecbe` `playbook: refuse a playbook that differs from HEAD`** (§10,
§13, §25). This is not a review item; it is listed here only, not in the
review-items table. `load_playbook(path, cwd=)` reads the file, then runs `git
show HEAD:./<path relative to cwd>` in `cwd` (a synchronous subprocess with a
10 s timeout and no new dependency). The engine and doctor pass
`roles.builder.cwd`. Outcomes:
- different bytes: `PlaybookNotCommitted`, "`<path>` is dirty", with the
  working and committed sha256;
- git exits non-zero (not in HEAD, no commit, not a repository): refused as
  untracked, with git's first stderr line and `committed sha256 none`;
- git cannot run or times out: refused, `committed sha256 unknown`;
- a missing file is still no playbook, and git is not consulted.

The refusal goes through the engine's existing load-error path: one stop, with
the reason "the playbook is not the committed copy, so no rule can be trusted
to fire: …", one `stop` event and one notification. Doctor's playbook row
fails with the refusal text, and its `ok` result adds a `committed` line.
There is no bypass switch. `tests/conftest.py` gains `commit_file()`, and the
existing playbook and doctor tests now commit their playbooks.

**U4 — `edb8e84` `notify, playbook: retire quiet_hours; refuse it at load`**
(§10, §11, §13, §25; FINAL-REPORT-8 §5 item 3; REVIEW-8 Notes, "Quiet
hours"). `quiet_hours` leaves `LIMIT_KEYS` and the `Playbook` dataclass. A
`[limits]` table carrying it is refused by name (`RETIRED_LIMIT`) with
"[limits] quiet_hours is retired (decision 2026-09-12): notifications are
never delayed (§11); remove the key". At the top level or in a `[[rule]]`, the
key gets the existing unknown-key refusal. `notify.py` loses `QuietWindow`,
`parse_quiet_hours`, the queue, the flush task and the clock/sleep/quiet_hours
parameters. `daemon.py` stops passing the key. Doctor's notification check,
`cli.py`'s `notify --test` text, `api.py` and both docs no longer describe
quiet hours. The config never had the key, and `config.py` already refuses
unknown `[limits]` keys, so it is unchanged. Ten tests were deleted and one
added (1439 → 1430).

**U5 — `f96c88b` `phone, monitor: re-mint held nonces on start; task_killed
cause unknown`** (§5, §8, §10, §11, §24, §25; FINAL-REPORT-8 §5 items 4, 5).
`Daemon.start()` calls `_renotify_held()`. When the command channel is on, it
mints a fresh nonce through `PhoneChannel` for every job whose record is
`held`. It then re-publishes that job's `job.held` notification with
Approve/Deny buttons, rebuilt from the job record in `Api.send`'s shape.
Without `cmd_topic` nothing is re-sent: the design is silent there, and that
notification never had buttons. `monitor.task_killed` carries `cause:
"unknown"`. `docs/PLAYBOOK.md` and `docs/INTEGRATION.md` say why (the stream
cannot tell a harness reap from the agent's own `TaskStop`), and
INTEGRATION.md says a restart re-sends held notifications. `who_cmd_topic`
gets no code change, per §25's decision (item 4).

**U6 — this file**, plus `meta/plan.md`, `meta/CHECKPOINT.md` and
`meta/journal.md` (U5's bookkeeping and U6's). No product code, no tests.

---

## 2. What the tests prove

Counts: base 1423 passed + 1 failed → U0 1424 → U1 1428 → U2 1432 → U3 1439
→ U4 1430 → U5 1435.

**U0.** The fixture equals §10's example, and it parses into the nine listed
(on, then) pairs. Every fixture line appears 4-space-indented somewhere in
`docs/PLAYBOOK.md`. The extended rule-list test was red against the old
fixture.

**U1.** With `fake_claude`, the recorded shape of `0mtygi953-ym63` (success,
`num_turns` 59, exit 0, the terminating line) is `failed`/`harness_terminated`
in three places: the runner, `hands show` against a daemon, and the §10
example's `builder.failed → resume` over a real daemon. All three were red
before the code change. Both REVIEW-7 over-match lines leave a success job
`done`. The existing limit-over-line and cancel-over-line tests stay green.
§6's two lists, parsed from `DESIGN.md`, equal `FAILURE_REASONS` and
`DECIDED_BY`. `docs/INTEGRATION.md` carries every value and the precedence
rule.

**U2.**
- SF1: `main()` returns 7 for `pipeline` and 0 for `status` through the real
  socket, and the spy saw exactly the daemon's JSON answers. The test is red
  when `return exit_code(command, result)` becomes `return 0`.
- SF3, a test called directly on `_last_resort`: with no members,
  `group_pids` is asked about `job.pid` and there is no `killpg`; with
  members, there is one SIGKILL to `job.pid`. Both cases were red before the
  change.
- SF4: an `httpx.HTTPStatusError` (403) and an `httpx.ConnectError`, each
  carrying the `cmd_topic` URL in its text, are pushed through a fake stream.
  No `hands.phone` log line contains the topic, and the warnings read
  `HTTPStatusError: HTTP 403` and `ConnectError`. Red before the change on the
  topic assertion.

**U3.** All in a temp git repository (`conftest.commit_file()`):
- A committed, clean playbook loads, with the engine not paused and no event.
- A dirty one is refused naming both sha256s. The pipeline stops, the `stop`
  event and the notification carry the reason, and no rule fires.
- An untracked one is refused and stops the pipeline.
- One outside any git repository is refused.
- `test_a_dirty_playbook_is_refused_at_job_start` (`tests/test_playbook.py`)
  runs through the real daemon: `send` produces the stop reason, one inbox
  `stop` event and no second job.
- Doctor's row is `ok` with `committed` when clean, fails with both sha256s
  when dirty (`test_a_dirty_playbook_fails_the_row_naming_both_sha256s`), and
  fails when untracked.

**U4.** A committed playbook whose `[limits]` sets `quiet_hours` is refused
by `load_playbook` with both halves of the message, and the engine's
load-refusal stop carries them as its reason. It was red before the loader
change (DID NOT RAISE). Deleted: the quiet-window parametrized test (6
cases), the unreadable window, delay-to-window-end, two notifications sharing
one flush, and `notify --test` not being delayed by quiet hours. The
repository playbook test and the docs file-reference check drop their
`quiet_hours` assertions.

**U5.** The test runs `Daemon.start()` twice over one spool, with a recording
publisher and a fake ntfy stream. Two held jobs get exactly two held
publishes; an approved-then-done job and an ungated job get none. Each
publish has buttons for its own job, with a nonce that differs from the
pre-restart one and contains no secret. The old nonce is refused. The new
nonce approves (and denies) with `decided_by: phone` and is bound to its job.
A restart with no held job re-sends nothing, and a restart without the channel
re-sends no held notification. `test_the_nonce_dies_with_the_daemon` now
expects a fresh nonce for the still-held job instead of an empty nonce table.
`cause` is `"unknown"` for both recorded fixture kills (A, a Bash kill; B,
`TaskStop`) and for the `fake_claude` kills through the daemon. Both docs pin
the sentence. Seven tests failed before the product change, and the docs pin
failed with the doc edits stashed.

---

## 3. NOT PROVEN

1. **Real harness termination, still.** No real harness termination has been
   observed under U1's code. No real claude with the ceiling at 0 has been
   seen waiting instead of terminating. Everything runs through `fake_claude`.
   A coloured or prefixed terminating line would not match; none has been
   observed.
2. **The `task_killed` cause.** `cause` is a constant, so the event still
   cannot tell a harness reap from `TaskStop` or a parent's death, and a
   harness-initiated reap has still never been observed.
3. **Real phone and ntfy.** No real phone or ntfy took part in U2, U4 or U5.
   U5's re-sends are fired as asyncio tasks. If ntfy is down at restart, only
   an inbox record is left; that is untested. A phone decision racing the
   re-send is untested. The rebuilt payload is checked for job, role, state,
   reason and gate; it may differ from the original `job.held` in other
   fields.
4. **U2's should-fix closures are narrower than the defects.**
   - SF1 pins the route's wiring with a substituted `exit_code`, because no
     command reaching the socket route returns non-zero today.
   - SF3: `_last_resort` is tested by direct call, not through `run()`'s
     exception path. The pid-reuse race is not reproduced. The membership
     read and the `killpg` are still two steps, not atomic. Scope mode's last
     resort is unchanged and untested.
   - SF4 is tested with two exception types from a fake stream, not a real
     ntfy refusal. Other daemon log lines were not audited for the topic.
5. **U3's git check.** Untested: the git-timeout and git-missing refusals; a
   `cwd` below the repository root; a playbook path with a subdirectory or
   `..`; line-ending or filter settings (`core.autocrlf`, clean filters) that
   make working bytes differ from `git show`. `git show` runs synchronously
   and can block the daemon's event loop for up to its 10 s timeout. A
   playbook deleted from the working tree but present in HEAD loads as "no
   playbook" (§5 item 1). `hands pipeline`'s rendering of the refusal is
   checked only through the engine.
6. **U4.** The named refusal is tested only for `[limits]`; the top level and
   `[[rule]]` get the generic unknown-key refusal. No test proves that nothing
   delays a notification; that rests on the removal of the code that did. No
   real ntfy was used.
7. **U4's gate, as literally written, is not met.** `grep -rn quiet_hours src
   tests docs driver` at the tip returns the refusal
   (`src/hands/playbook.py:120`, `RETIRED_LIMIT`) and its test
   (`tests/test_playbook.py:413-424`), plus four hits that are not the
   feature:
   - `tests/fixtures/playbook_example.toml:7` and `docs/PLAYBOOK.md:234`:
     §10's example comment "no quiet_hours: …", pinned byte for byte to
     DESIGN;
   - `docs/PLAYBOOK.md:103`: the sentence stating the refusal;
   - `docs/ARCHITECT-INSTRUCTION.md:58`: the architect convention "Playbooks
     never set `quiet_hours`".

   At `edb8e84` the two `docs/PLAYBOOK.md` hits were lines 102 and 233; U5
   added a line above them. Each extra is a refusal statement or DESIGN
   verbatim text.
8. **U0's doc pin is weak.** `test_the_playbook_doc_carries_the_section_10_example_verbatim`
   checks that each line appears somewhere in `docs/PLAYBOOK.md`, so it cannot
   prove the verbatim block is complete. The page's prose already showed both
   new rules, so the pin would pass without the block change. The block was
   compared to the fixture by a one-off script, not a test.
9. **§8 still names `button`.** §6 lists `cli|driver|phone`, and
   `DECIDED_BY` is pinned to §6, but §8 (`DESIGN.md:313-314`) still says
   `decided_by: button`. The code keeps `button` as an unavailable row that
   `check_decider` refuses (§5 item 3).
10. **Docs** are proven only as far as the pinned phrases and the sweep; a
    stale claim spelled with none of them passes.
11. **The installed and running `handsd`** was not rebuilt or restarted onto
    this code, so no restart re-mint has run outside the tests.
12. **Carried from FINAL-REPORT-8 §3 and not touched by this mission:** real
    systemd scope behaviour; a `setsid` escape in process-group mode; `hands
    who`/`handswho` against live inputs; H-001 and H-009 stay open.

---

## Review items

| Item | Status | Where |
|---|---|---|
| REVIEW-8 should-fix 1: `main()`'s exit code on the socket route is unpinned | closed | `7992c4d` (`test_main_returns_the_exit_code_of_the_socket_answer`, through `main()` and a real socket; wiring pinned with a substituted `exit_code`, since no socket command returns non-zero today, §3 item 4) |
| REVIEW-8 should-fix 2: §6's `failure_reason` and `decided_by` vocabularies disagree with the wire | closed by the design | DESIGN v3.8 §6 + H-017 (U0 `1c17d84`); `4da83f8` pins the code (`FAILURE_REASONS`, `DECIDED_BY`) and `docs/INTEGRATION.md` to §6's lists |
| REVIEW-8 should-fix 3: `_last_resort` calls `killpg` on an unchecked group | closed | `7992c4d` (group mode checks `group_pids` first; tested by direct call; check-then-kill not atomic, scope mode untouched, §3 item 4) |
| REVIEW-8 should-fix 4: the reconnect warning can carry `cmd_topic` | closed | `7992c4d` (type and `HTTP <status>` only; topic absent for two exception types; other log lines not audited, §3 item 4) |
| FINAL-REPORT-8 §5 item 1: termination-line precedence | closed | DESIGN v3.8 §6; `4da83f8` (H-014's shape is `failed`/`harness_terminated`) |
| FINAL-REPORT-8 §5 item 2: H-016, §10's example lacks the detector rules | closed | DESIGN v3.8 §10; `1c17d84` (copies updated, rule list extended) |
| FINAL-REPORT-8 §5 item 3: `quiet_hours` | closed | DESIGN v3.8 §11; `edb8e84` (removed; refused at load). The gate grep as written is not met; the extras are refusal or DESIGN-verbatim text (§3 item 7) |
| FINAL-REPORT-8 §5 item 4: `who_cmd_topic` has no secret; `task_killed` cannot tell a reap from `TaskStop` | partly closed | §25 decides `who_cmd_topic` stays secret-less (no code); `f96c88b` adds `cause: "unknown"`. The inability remains and is now stated (§3 item 2) |
| FINAL-REPORT-8 §5 item 5: phone channel after restart | closed | `f96c88b` (held jobs re-minted and re-notified on start; no real phone, §3 item 3) |

The playbook-must-match-HEAD requirement (§10, §25) is not a review item. It
is described in §1 (U3, `fd6ecbe`) and §2, and its acceptance line is in §4,
not in this table.

---

## 4. Acceptance, checked

- **Check green on the pushed tip, three consecutive runs:** `f96c88b`, 1435
  passed, `check: green`, three consecutive runs by the builder before the U6
  commit. U6's gate inputs are `f96c88b`'s plus meta files.
- **Every unit commit's body lists every file it touches, and U0 is `plan:`.**
  A script over `git rev-list 0ead876..f96c88b` (10 commits: six unit commits
  and four `meta:` commits) checked each path from `git show --name-only`
  against the commit's full message body, as a literal substring. Zero commits
  have an unlisted file. File counts: `1c17d84` 6, `4da83f8` 8, `f0368f0` 3,
  `7992c4d` 5, `39a2b0a` 3, `fd6ecbe` 7, `48bcd92` 3, `edb8e84` 11, `30d4440`
  3, `f96c88b` 8. The substring test proves each path is named, not that the
  body lists only those paths. `1c17d84` is `plan:`. U6's commit is to list its
  four files; it did not exist when this was checked.
- **`grep -n prototypes pyproject.toml` returns nothing** (run at the tip:
  no output, exit 1).
- **A dirty `PLAYBOOK.toml` is refused at job start (test):**
  `tests/test_playbook.py::test_a_dirty_playbook_is_refused_at_job_start`
  (`fd6ecbe`). Through the real daemon, `send` produces the stop reason, one
  inbox `stop` event and no second job.
- **`meta/FINAL-REPORT-9.md` exists with NOT PROVEN and the review-items
  table:** §3 and `## Review items` above, moved in from `meta/drafts/` by
  U6's commit.

---

## 5. For the architect

1. **A deleted but committed playbook loads as "no playbook"** (U3). A
   missing file skips the git check, so removing `PLAYBOOK.toml` from the
   working tree turns chaining off silently, even though HEAD has one. The
   design did not decide against this; decide whether it should be refused.
   U3 also chose to refuse a playbook outside any git repository, the
   simplest reading of §10.
2. **U3's `git show` blocks the daemon's event loop** for up to 10 s (it is a
   synchronous subprocess). Say whether load may block, or should run off the
   loop.
3. **§8 still names `button`** (`DESIGN.md:313-314`, `decided_by: button`),
   while §6 lists `cli|driver|phone`. The code keeps an unavailable `button`
   row to match §8.
4. **U4's gate grep** cannot return "only the refusal and its test" while
   §10's example carries the comment "no quiet_hours: …" (pinned into two
   copies) and `docs/ARCHITECT-INSTRUCTION.md` states the convention. Reword
   the gate, or the comment, next time.
5. **U0's doc pin** is line containment anywhere in `docs/PLAYBOOK.md`. If
   the verbatim block matters, the pin should compare the block itself.
6. **Restart re-send without the command channel** sends nothing (U5's
   choice). Confirm that a restart need not re-notify held jobs when there
   are no buttons.
7. **The base kit was red** (§10's example changed with no unit copying it).
   A kit that edits a pinned DESIGN block should name the unit that copies it.
