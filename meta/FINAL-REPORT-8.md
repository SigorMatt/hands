# FINAL-REPORT-8 — hands mission 8: detectors, the phone channel, who

Mission: `meta/BUILDER-8-PROMPT.md`. Design: `DESIGN.md` v3.7, §24.
Reviews closed: `meta/reviews/REVIEW-7.md` (`VERDICT: review mission 7
blockers=1 should-fix=4`) and REVIEW-3 should-fix 3, 6, 7 (deferred twice).
Findings filed: H-015 (the phone channel decision), H-016 (§10's example
lacks the two new stop rules). H-014 gains a status paragraph (U1).

Base `da8df27` (`plan: mission 8 kit (DESIGN v3.7, claudewho prototype)`) —
green: ruff clean, **1235 passed**, cli smoke, `check: green`.
Tip `c41473c` (U7, the last commit that changes a gate input; the U8 commit
that carries this report is meta only) — ruff clean, **1424 passed**, cli
smoke, `check: green`, three consecutive runs by the builder before the U8
commit (the journal's U8 line), and three by each unit's sub-agent before its
own commit.

Nine units planned, nine landed. None blocked, none retried. Every product
unit is one commit; each is followed by a `meta:` bookkeeping commit that
touches only `meta/plan.md`, `meta/CHECKPOINT.md` and `meta/journal.md`,
except U7's, which rides in U8's commit together with this report. U0 is a
`plan:` commit, because it changes gate inputs (a test file) — review 7
should-fix 3. The report was drafted under `meta/drafts/` and moved in by
U8's commit; every `git add` named explicit paths.

This report is a snapshot. Per DESIGN §20, a claim here that later expires is
corrected by an appended dated line, never by a rewrite.

---

## 1. What changed, by unit

**U0 — `9ae7975` `plan: mission 8 plan; show's failure line pinned and H-015
filed`** (§6, §24; REVIEW-7 blocker 1). `meta/plan.md`, `meta/CHECKPOINT.md`.
Three tests drive `hands show` through `main` against a real daemon: a job
failed `harness_terminated` and one failed `nonzero_exit` (exit 3) each print
exactly one `failure  <reason>` line; a done job prints none (a null field is
not printed). H-015 records §24's phone channel decision and the brief's
operational additions. `meta/prototypes/claudewho.py` was already in place
from the kit.

**U1 — `df8c1fd` `runner: the terminating line is the harness's exact message
and never beats success`** (§2, §6, §24; REVIEW-7 should-fix 2, 4).
- The matcher is line-start, case-sensitive, digits + `s;`, with the `Set
  CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=` tail on the same line (the 2.1.270
  binary holds the message as one string).
- DESIGN v3.7 §6 (`DESIGN.md:244-245`): "a job with a `success` result,
  turns and exit 0 is `done` whatever else stderr says". So H-014's recorded
  shape of job `0mtygi953-ym63` (success, `num_turns` 59, exit 0, the line) is
  now `done`; the old test was renamed to assert that, and H-014 carries a
  status paragraph saying so (§5 item 1).
- The doc sweep decides text-ness by content (no NUL in the first 8192 bytes),
  reads every tracked file, excludes `meta/` history by path, and reads
  everything else under `meta/` — `BUILDER-*`, `REVIEW-PROTOCOL.md`,
  `BACKLOG.md`, `ROADMAP.md` and any future file. One named allowance:
  `meta/BUILDER-1-PROMPT.md`'s "background-wake check" (mission 1's retired
  doctor instruction); the test fails if the allowance stops matching.
- `tests/fake_claude.py` gains `no_turns` so the daemon and playbook tests that
  need a failed job still produce one.

**U2 — `68e1048` `monitor: file monitor.task_killed from a role job's
stream-json, once per task`** (§5, §24; backlog 1). The notice, quoted in
`tests/fixtures/task_killed.stream.jsonl` from two recorded hands stream logs
(2.1.269 and 2.1.270): a `system` `task_updated` with `patch.status "killed"`,
then a `system` `task_notification` with `status "stopped"`. Neither carries
the command line; it comes from the earlier `Bash` tool_use with the same
`tool_use_id`. The runner hands each parsed event to the monitor; either event
is the notice; builder and aux jobs are covered; one event per task per job
(a per-job memory capped at 1024). The event is a valid playbook `on` and
`wait --for` name. `docs/PLAYBOOK.md` and `docs/INTEGRATION.md` describe it.

**U3 — `4782a4a` `runner: per-job scope or process group, and
monitor.orphan_processes at job end`** (§5, §24; backlog 2). A probe picks
`systemd-run --user --scope --quiet --unit hands-<project>-<job>` when
`systemd-run` exists and the user manager answers, else
`start_new_session`. Unit names: characters outside `[A-Za-z0-9_-]` become
`_`, the project part is cut to 64. The live pid set is the scope's
`cgroup.procs` or the process group's members, passed to the ops script as
`--pids`. At job end (and on cancel) anything still alive is filed once as
`monitor.orphan_processes` with `{pid, cmdline}` (each capped at 1024
characters), then the scope is stopped or the group gets SIGTERM, a grace and
SIGKILL. An orphan holding the job's stdio no longer hangs job end. `hands
doctor` gains an `isolation` row naming the mode; the process-group text says
it is weaker. `tests/conftest.py` forces process-group mode.

**U4 — `7183478` `phone: ntfy command channel with nonce buttons and
decided_by phone`** (§8, §11, §13, §24; backlog 5; H-015). New
`src/hands/phone.py`: an outbound long-poll of `<ntfy_url>/<cmd_topic>/json`
with bounded-backoff reconnect and no replay of handled or pre-subscribe
messages. `approve`, `deny [reason]`, `pause`, `resume`, `status`, the token
being the last word, compared with `hmac.compare_digest`. A held job's
notification carries Approve/Deny `http` action buttons with a 32-byte
single-use nonce, per job, held only in daemon memory, dying on any decision
and on restart; `pause`/`resume`/`status` take only the secret. Decisions go
through the socket's path with `decided_by: phone`. A bad token, an unknown
command or a job that is not held is logged (without the token) and ignored.
Config load refuses `cmd_topic` without `cmd_secret`, a secret containing
whitespace, and `cmd_topic` equal to `ntfy_topic`; doctor's `phone` row
reports the channel on/off. `docs/INTEGRATION.md` has the setup.

**U5 — `6fcd7d7` `notify: doctor's probe argv from OPS_FLAGS, accepted()
int-only, notify refusal on the socket route`** (REVIEW-3 should-fix 3, 6, 7;
backlog 3). All three defects were present at the base. `monitor.ops_argv()`
builds the ops script's argv for both the monitor and doctor's probe, reading
`OPS_FLAGS` at run time (the `MONITOR_FLAGS` alias is gone). `accepted()`
counts only an integer 2xx as delivered; the two `Posts` test doubles return
200. `Api.notify`'s 403 shape (`delivered: false` + the code) is pinned
through the socket; the CLI renders it as `notify --test` does and
`cli.exit_code()` returns 1 when not delivered.

**U6 — `a93e3a7` `who: hands who prints the one-screen picture, handswho
pushes it on change and on request`** (§4, §11, §24; backlog 6). New
`src/hands/who.py`, ported from the prototype: the daemon's jobs, held gates,
pipeline and inbox from a new read-only `who` socket method; other `claude`
processes from /proc; interactive sessions' state from transcripts; labels
`role <r>`, `(your session)`, `driver:<project>`; the daemon → jobs →
processes and session → processes hierarchy; a two-scan debounce; the human's
own sessions never fingerprinted. `hands who` prints once (exit 0, also when
the daemon is down). `handswho` (a second console script) pushes to
`who_topic` on change and on `status`/`who`/`check`/`?` from
`who_cmd_topic`, exits 1 naming the key without `who_topic`, and takes no
secret (the commands run nothing; the reply is the picture). New
`systemd/handswho.service`; `scripts/check` smokes `handswho --help`.
`meta/prototypes/claudewho.py` and its ruff exclude are deleted.

**U7 — `c41473c` `docs: root playbook stops on the mission 8 detectors;
doctor reports notifications and who on/off`** (§10, §11, §13, §24; backlog
4). Root `PLAYBOOK.toml` maps `monitor.task_killed` and
`monitor.orphan_processes` to `stop` and has no `quiet_hours`. `hands doctor`
gains `notifications` and `who` rows, `ok` on or off; U4's `phone` row is the
command channel. `docs/INTEGRATION.md`'s optional section merges U4's and
U6's text; `docs/PLAYBOOK.md` and `README.md` updated. DESIGN §10's example
does not have the two rules, and its copies are pinned to it byte for byte, so
they are unchanged and H-016 asks the architect. `quiet_hours` support stays
in the code, since DESIGN §11 still describes it (§5 item 3).

**U8 — this file**, plus `meta/plan.md`, `meta/CHECKPOINT.md`,
`meta/journal.md` (U7's bookkeeping and U8's). No product code, no tests.

---

## 2. What the tests prove

Counts: base 1235 → U0 1238 → U1 1285 → U2 1300 → U3 1323 → U4 1367 → U5
1380 → U6 1416 → U7 1424. Each unit's sub-agent ran `./scripts/check` three
times before its commit; the builder ran it three more times at each unit's
sha before the bookkeeping commit that followed (and before U8's).

**U0.** `hands show` through `main` against a real daemon: one `failure` line
with the reason on `harness_terminated` and `nonzero_exit`, none on `done`.
Red by mutation (label renamed; line pointed at `state`).

**U1.** With `fake_claude`: the recorded H-014 shape is `done`; the
terminating line makes a job `failed`/`harness_terminated` when any one of
success, turns or exit 0 is missing. REVIEW-7's two over-match lines are
negatives verbatim, for the matcher and in a real run, with about 17 more
near-misses (missing tail, wrapped line, leading text or colour code, `ms`,
`1.5s`, a spaced unit, case changes). The sweep's classifier is table-tested
over synthetic paths and contents, and every tracked file is either swept or
excluded by a named path.

**U2.** The parser on the recorded fixture. Through the daemon with
`fake_claude`: the notice yields exactly one `monitor.task_killed` with the
command line; a repeated notice no second; two tasks two; an aux job is
covered; a normal run none. A `stop` rule on the event loads and pauses the
pipeline in the playbook engine; `wait --for task_killed` resolves to it.

**U3.** In process-group mode with real subprocesses: a double-forked orphan
(no `setsid`) run through the real daemon is filed once with its pid and
`sleep 300` and is dead by job end, also when it holds the job's pipes; a
cancelled job's orphan is filed and killed; a normal run files nothing; the
job gets its own group. Scope mode is spawned through a stand-in
`systemd-run` with the right argv. The probe, unit-name sanitising, cgroup
file parsing, the pid-set reader (zombies left out), the cmdline cap, the ops
script receiving `--pids`, doctor's `isolation` row both ways (text and
`--json`), and the event as a playbook rule and `wait --for` name.

**U4.** Over a mocked ntfy `/json` stream, no network: all five commands with
the secret; approve and deny with the nonce taken from the recorded button;
the nonce is 32 bytes, single-use, useless on another job, not spent by a
wrong token, dead after a laptop decision and after a restart;
`pause`/`resume`/`status` refuse a nonce; bad, unknown and not-held commands
are ignored and publish nothing; a reconnect does not replay; pre-subscribe
messages are not acted on. `decided_by: phone` is read back from `hands show
--json`, the job file and the `gate.decided` event. The secret appears in no
captured HTTP request (URL, headers, body) for daemon start, a held job with
buttons, both kinds of stop, the status reply, `notify --test` and the crash
notification, nor in job files, inbox or log (nor does the nonce, outside the
button). Doctor's channel on, off and refused.

**U5.** Doctor's probe with renamed flags sends the new names (it sent
`--pids/--transcript/--base` at the base); `accepted()` over a 10-value table,
and a publisher returning `None` is a failed delivery in the inbox and in
`send_test`; a 403 through the real socket renders as not delivered and
`exit_code` is 1. Each red at the base.

**U6.** The prototype's 7 self-test cases, one test each; the /proc reader
over a fake /proc; the transcript reader over a temp directory; an exact
rendering of a fixed process table and fixed daemon state (a running job with
a child, a queued job, a held gate, the inbox, another headless claude, your
session, a driver session); daemon-down, pipeline-stopped and
inbox-without-driver pictures; no fingerprint for your own session; a
two-scan debounce; no duplicate push of an identical picture; a push for each
of the four commands on a mocked `who_cmd_topic` stream; `hands who` through
`main` with the daemon down and against a real daemon; `handswho --help`; `who`
in §4's command list.

**U7.** The root `PLAYBOOK.toml` through the real loader maps both events to
`stop` and never mentions `quiet_hours`. `main(["doctor"])`, text and
`--json`: no extras → channel off, who off, exit 0; no `ntfy_topic` →
notifications off, exit 0; who topics set → who on, with no topic or secret
value in the output. Three doc pins for the new statements (the secret is
never in a notification, bad tokens are ignored, the process-group fallback is
weaker). Each red before its change.

---

## 3. NOT PROVEN

1. **Real systemd scope behaviour.** No test runs `systemd-run`; the suite
   forces process-group mode. The U3 sub-agent ran one scope by hand on this
   machine (the orphan was reported, the scope stopped, the orphan died);
   that is a witness, not a test. Reading a running scope's `cgroup.procs` as
   `--pids` during a job, the scope-stop timeout, the fallback kill when a run
   raises, and the pid-list cap are untested.
2. **Real ntfy command delivery.** No real ntfy `/json` stream has been read:
   its `since` semantics (by id and by time), keepalives, reconnect behaviour
   and clock drift between ntfy and this machine are mocked. The Approve/Deny
   buttons have never been shown or pressed on a phone. A phone approve into
   a full queue is untested. The secret-never-published property does not
   cover a playbook `notify` rule, an exhausted `max_resumes` stop, or
   notifications held by quiet hours.
3. **Real task-killed notice shape, as the harness's own reaping.** The two
   recorded instances are a task that died with its parent agent and one
   stopped by the `TaskStop` tool; a harness-initiated reap has not been
   observed. The stream does not say who killed a task, so `TaskStop` and a
   parent's death also file `monitor.task_killed` (and map to `stop`).
   Behaviour after the 1024-entry memory cap starts dropping is untested. The
   path from a running daemon's event to a pipeline stop is tested only in the
   playbook engine.
4. **H-014's recorded case is no longer caught by the runner.** Per §6 a
   success result with turns and exit 0 is `done` whatever stderr says, so a
   repeat of job `0mtygi953-ym63` would again be `done`; only the ceiling at 0
   (U1 of mission 7) and the hook guard against it, and `SendMessage` remains
   unhooked. A colour-coded or prefixed terminating line would not match; none
   has been observed.
5. **Process-group mode misses `setsid`.** A process that leaves the group is
   neither seen nor killed, and if it also holds the job's pipes the job still
   waits for it. Documented as weaker; scope mode is meant to cover it and is
   item 1.
6. **Phone channel edges.** The phone acts only on held jobs (a pending
   cancel gate stays with the laptop). After a daemon restart held jobs have
   no nonce until the secret is typed, and are not re-notified.
7. **`hands who` and `handswho` against live inputs.** Nothing ran against a
   live /proc, real transcripts, a real claude or real ntfy; the
   `handswho.service` unit has never been started; the long-running loop with
   the command stream open and its reconnect delays is untested. Transcript
   directory names assume every non-alphanumeric character becomes `-`, which
   is unwitnessed for `.` and `_` (H-001). A role cwd reached through a
   symlink may not get `(your session)`. `who_cmd_topic` is unauthenticated
   (DESIGN names no secret for it): anyone who knows it can trigger a push of
   the picture to `who_topic`. Doctor does not check that `handswho` is
   running.
8. **U5's socket route of `notify`** is tested through `_render` and
   `exit_code`, not through `main()`, which sends notify locally; the
   monitor's own use of `ops_argv` is covered only by its existing tests.
9. **Docs** are proven only as far as the pinned phrases and the sweep; a
   stale claim spelled with none of them passes.
10. **The installed and running `handsd`** was not rebuilt or restarted onto
    this code by this mission; `hands doctor` above ran from the source tree.
11. **H-001 and H-009 stay open**; H-016 is open for the architect.

---

## Review items

| Item | Status | Where |
|---|---|---|
| REVIEW-7 blocker 1 — `hands show`'s `failure` line has no test | closed | `9ae7975` (three tests through `main`: `harness_terminated`, `nonzero_exit`, `done`) |
| REVIEW-7 should-fix 1 — DESIGN v3.6 does not carry the harness-termination rule it cites | closed by the design | DESIGN v3.7 §24's first bullet; §2 (`DESIGN.md:114`), §6 (`:234`, `:242-245`), §13 (`:593`) now carry it; no builder change |
| REVIEW-7 should-fix 2 — the terminating-line matcher over-matches and overrides success | closed | `df8c1fd` (anchored matcher; the two lines pinned as negatives; success + turns + exit 0 is `done`, §6) |
| REVIEW-7 should-fix 3 — U0 committed as `meta:` though it changes gate inputs | closed | `9ae7975` is `plan:`; every `meta:` commit of this mission touches only plan, checkpoint, journal and (U8) this report |
| REVIEW-7 should-fix 4 — the sweep is a suffix list and skips live `meta/` instructions | closed | `df8c1fd` (content-based text-ness; `meta/` history excluded by path; `BUILDER-*`, `REVIEW-PROTOCOL.md`, `BACKLOG.md`, `ROADMAP.md` read) |
| REVIEW-3 should-fix 3 — doctor's probe argv hardcodes the flags | closed | `6fcd7d7` (`monitor.ops_argv()` over `OPS_FLAGS`) |
| REVIEW-3 should-fix 6 — `accepted()` calls a non-integer status delivered | closed | `6fcd7d7` (integer 2xx only) |
| REVIEW-3 should-fix 7 — `Api.notify`'s failure shape untested by any client | closed | `6fcd7d7` (403 through the socket; rendered; exit 1) |

---

## 4. Acceptance, checked

- `./scripts/check` green on the pushed tip, three consecutive runs: 1424
  passed, ruff clean, cli smoke, `check: green`, before U8's commit (the
  journal's U8 line), whose gate inputs are `c41473c`'s plus this report.
- Every unit commit's body lists every file it touches, and U0 is `plan:`:
  a script over `git rev-list da8df27..HEAD` (at the U7 bookkeeping state, 15
  commits: eight unit commits and seven `meta:` commits) compared each
  commit's `git show --name-only` with its body — 0 with an unlisted file.
  U8's commit lists its four files.
- `hands --help` lists `who`; `handswho --help` prints its usage (both driven
  by the builder with `uv run`).
- `hands doctor` on a config without `[notify]` extras: `uv run hands
  --project hands doctor` against `~/.hands/hands.toml` (no `cmd_topic`,
  `cmd_secret` or `who_topic`) prints `phone  command channel off`, `who  who
  view off`, `doctor: green`, exit 0; pinned by U7's tests through `main`.
- `PLAYBOOK.toml` has no `quiet_hours` and has `monitor.task_killed` → `stop`
  and `monitor.orphan_processes` → `stop` (U7's loader test; `grep`).
- `meta/prototypes/` is absent at the tip (deleted by `a93e3a7`).
- `meta/FINAL-REPORT-8.md` exists with NOT PROVEN (§3) and the table under
  `## Review items`.

---

## 5. For the architect

1. **§6's "whatever else stderr says" un-catches H-014's own case.** The
   recorded job had a success result, 59 turns, exit 0 and the terminating
   line; v3.7 §6 makes that `done`, and U1 followed it. If the intent was
   only to stop an unrelated line from failing a finished job, the anchored
   matcher already does that, and the precedence could be reconsidered.
2. **H-016.** §10's example lacks `monitor.task_killed` and
   `monitor.orphan_processes` → `stop`, which §24 says it gains; the root
   `PLAYBOOK.toml` has them, the verbatim copies cannot until §10 does.
3. **`quiet_hours`.** §24's conventions say "no `quiet_hours`", but §11 still
   describes the feature, and doctor's notification check still tells the
   human to run outside quiet hours. The code is kept; retiring it is a design
   edit first.
4. **`who_cmd_topic` has no secret** and `task_killed` cannot tell a harness
   reap from `TaskStop` (§3 items 3, 7): decide whether either matters.
5. **Phone channel after restart** re-mints no nonce and re-sends no held
   notification (§3 item 6).
