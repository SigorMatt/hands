# FINAL REPORT — mission 1 (the hands core)

Builder's report for the mission in `meta/BUILDER-1-PROMPT.md`. Written at
tip `1ca707b` (+ this commit). It is a confession, not a release note: every
claim below is either backed by a named test I ran, by a command I ran while
writing this, or it is in NOT PROVEN. The design is `DESIGN.md`; this report
does not restate it.

The one fact to carry out of here: **no real `claude` process has ever run
under hands.** The entire suite runs against `tests/fake_claude.py`. Every
sentence below that sounds like "hands drives Claude Code" means "hands
drives a stand-in that imitates the parts of `claude -p --output-format
stream-json` the design names".

---

## 1. What changed

Eleven units, one commit each, all pushed. (`meta/*` bookkeeping commits sit
between them; they are not listed.)

**U0 Scaffold — `bff77ec`.** `pyproject.toml` (Python ≥ 3.11, hatchling,
src layout, `httpx` the only runtime dependency, console script `hands`),
the package skeleton, `scripts/check` (uv sync → ruff → pytest → `hands
--help` / `handsd --help` smoke, `set -euo pipefail`), and
`tests/conftest.py`'s `tmp_home` fixture, which repoints `HOME` so no test
can touch the real `~/.hands`.

**U1 Config and spool — `6fda083`.** `config.py` loads
`~/.hands/<project>.toml`, expands `~`, defaults every optional key and
**refuses** unknown sections and keys (a hand-edited file's typo is otherwise
a silent misconfiguration). `spool.py` is the whole on-disk state: job
records as JSON under `~/.hands/jobs/` written atomically (tmp + fsync +
`os.replace` + dir fsync), §6's state machine as a data table with illegal
edges refused, `roles/<role>.json`, an append-only `inbox.jsonl` with acks in
a second append-only file, and `resolve_under_roots()` — the single path
confinement helper every file command goes through.

**U2 Fake claude and runner — `ed6438b`.** `tests/fake_claude.py` is the
stand-in the rest of the mission is measured against: it refuses an
invocation that is not `-p --output-format stream-json`, emits `system`/`init`
with a session id, honours `--resume`, and obeys `FAKE:` control lines in the
prompt (result text, sleep, stderr, junk, rate-limit event, exit code,
permission denials, block until SIGINT/SIGTERM → 130/143). `runner.py` takes
one queued job to a terminal state and fills the §6 record: `session_id`,
derived `transcript_path`, `head_at_start`/`head_at_end` via `git
--no-optional-locks rev-parse HEAD`, the **verbatim** result, the `VERDICT:`
line, `stderr_tail`, `permission_denials`, `num_turns`, `duration_ms`,
`total_cost_usd`, `exit_code`. Cancel is SIGINT → `cancel_grace_s` → SIGTERM.
`reconcile_orphans()` is the startup sweep.

**U3 Daemon, local API, CLI — `1e4429a`.** `daemon.py`: asyncio unix-socket
server, newline-delimited JSON-RPC 2.0, one running job per role, FIFO queue
bounded by `queue_depth`, queued jobs re-admitted and running jobs orphaned
at startup, graceful shutdown. `api.py`: exactly one method per §4 command
(`Api.COMMANDS`). `cli.py`: the same twenty commands as a thin client with
`--json` and a readable form. `handsd --project <name>`.

**U4 Files and gates — `3d27480`.** `files.py` (`put`/`get`/`ls`, `send
--file path=content`, and `put --from`) — every path through
`resolve_under_roots`, every write recorded as `{path, sha256, bytes}`.
`gates.py` holds what trips a gate (`--gate`, or a case-sensitive prompt
pattern; a config can only widen the default set, never narrow it) and §8's
authority table as data the tests iterate. A gated send is born `held` and
takes no queue slot; `denied` is terminal; `--human-confirmed` is a
*declaration* that must carry `--quote`, stored verbatim — an audit trail,
not authentication, and `gates.py` says so out loud.

**U5 Limits — `b667786`.** `limits.py`: `is_limit_notice` (deliberately
tight — a false positive marks a `done` job `limited` and spends a resume),
`parse_reset_at` (ISO with Z / offset / naive, "resets at <time>" with and
without a date, "try again in N minutes"; past, unparseable, or more than
seven days ahead all → None → `limits.backoff_minutes`), and `LimitManager`
— one `limit` inbox event, a resume at reset + 60 s, one `resume` event, and
a `stop` once `limits.max_resumes` consecutive resumes pass without a `done`.
The raw notice is stored always, whatever the parser makes of it.

**U6 Monitor bridge — `37d4e2a`.** `monitor.py` runs one monitor per
**builder** job and stops it when the job ends; it never signals, cancels or
sends. With `ops.monitor_cmd` set it runs `<ops.repo>/<monitor_cmd> --pids
<pids> --transcript <path> --base <head_at_start>` and files each
blank-line-separated stdout block as `monitor.<kind>` verbatim. Without it,
the built-in detector samples transcript mtime, the `subagents/` dir, CPU
ticks from `/proc/<pid>/stat`, `.git/index`, HEAD and the stash list; a
constant sample for `monitor.stall_minutes` fires one `monitor.stall` and
re-arms.

**U7 Playbook engine — `36f9bd3`.** `playbook.py` loads
`<roles.builder.cwd>/<playbook.path>` when a job starts and stamps its
sha256 on every job it fires. Each §10 event is answered by the first rule
whose `on` and `verdict` regex match; placeholders (`{name}`, `{name+k}`,
`{job.*}`) render into the prompt. **Everything else is a `stop`** — no rule,
no verdict, an unparseable verdict, a run outside `auto_runs`, a
placeholder that will not resolve, a send the daemon refuses, exhausted
resumes — and a stop pauses the engine, records the reason, writes the inbox
event and notifies. The pause is persisted, so a restart does not resume a
chain nobody is watching. `hands pause|resume|pipeline`.

**U8 Wake path and notifications — `4a3d302`.** The spool now calls listeners
on every appended event and the daemon fans them out to one queue per armed
wait, so `hands wait --for <kinds>` is a real subscription, not a poll. The
event is returned and **not** acked; exit 2 on timeout, distinguishable from
1. `notify.py` publishes to ntfy over `httpx` for `stop`, `job.held`,
exhausted `max_resumes` and daemon start/crash, with `quiet_hours` delaying
(never suppressing) delivery and an hourly heartbeat while a job runs. This
unit also closed U5's restart gap (`reschedule_pending`) and a shutdown hang
(an armed wait is a handler that never returns).

**U9 Job library — `8cc2356`.** `hands jobs` with `--role/--grep/--since/-n`
(`--grep` is the prompt only, and a `--since` it cannot read is refused
rather than silently matching nothing), `hands show`, `hands open` (the API
*describes* the `claude --resume` invocation; the CLI execs it — refused for
a running job, a session another job holds, or no session at all), `hands log
<job>` / `log -f <role>` (byte-offset poll, never a half line, stays with the
job it started on), and `hands tail` over the recorded transcript.

**U10 Install surface — `9096b50`.** `systemd/handsd.service` (user unit,
`EnvironmentFile=%h/.config/hands.env`, absolute `ExecStart`,
`Restart=on-failure`). `doctor.py` runs in the **client**, not the daemon
(§14 step 1 is before `handsd` exists): binary + `--version`, role cwds,
allowed roots, the ops script's three flags, the playbook, the socket, and a
real one-turn `claude -p` per role that is off unless `--live` and refused
outright under `HANDS_DOCTOR_FAKE=1`. It prints — it cannot run — §11's
background-wake procedure. `README.md`, `docs/INTEGRATION.md`,
`docs/PLAYBOOK.md`, and a `driver/` kit corrected to match the CLI that
actually exists.

---

## 2. What is proven by tests

488 tests, all passing — the real number from the `./scripts/check` run
quoted in §4 below, not from memory. What follows is what would actually
break a test if the behaviour broke.

**The two acceptance end-to-end tests** (both re-run on their own while
writing this report; both pass):

- `tests/test_daemon.py::test_send_wait_result_end_to_end` — a real daemon on
  a real unix socket in `tmp_home`, the CLI driving it from a thread: `hands
  send --role builder --context clear` → `hands wait` → `hands result` gives
  the multi-line result back **verbatim**. In the same file: a second send to
  a busy builder queues and a third is refused, the aux queue accepts four
  and refuses the fifth.
- `tests/test_playbook.py::test_the_section_10_example_end_to_end` — §10's
  example playbook, carried verbatim from `DESIGN.md` and guarded by
  `test_the_fixture_is_section_10s_example_verbatim`, driven over a real
  daemon and `fake_claude`: run 2 finished → review sent → `blockers=0` →
  run 3 sent → run 4 is not in `auto_runs` → stop.

Everything in the list runs against `tests/fake_claude.py`.

- **Spool integrity.** Every legal and every illegal §6 transition pairwise;
  atomic write under a simulated crash (a half-written record is never
  visible); inbox append/ack; confinement escapes — `..`, absolute paths and
  symlinks leaving the roots — over every file command, table-driven.
- **Config.** Defaults, `~` expansion, §13's own example, and the refusals of
  unknown keys.
- **Runner.** `clear`, `keep`, `keep` refused both ways (no session; the
  session's last job not terminal), §2's flag set, the verbatim result,
  verdict extraction, `limited` from the retry event and from the result
  notice, killed by SIGINT and by SIGTERM escalation, orphan reconciliation,
  stderr tail, denials, and the transcript-path rule. Heads are proven
  against a **real** `git init`ed repo (`test_heads_are_recorded_...`) —
  git is the one external binary the tests really use.
- **Gates.** Each default pattern; §8's authority table as a parametrised
  table; `denied` is terminal; and that nothing else releases a `held` job —
  not a second send, not `resume`, not a queue slot opening, not a daemon
  restart, not `cancel`. "Written before spawn" is proved by the spawned
  process reading the file (`FAKE:cat`), not by a timestamp.
- **Limits.** Every notice shape the parser claims, the shapes it must *not*
  match (prose about rate limiting), the consecutive-resume counter, and the
  stop at `max_resumes`. All with an injected clock: the asserted fact is the
  *scheduled* delay — no test waits out a limit.
- **Monitor.** The ops bridge gets the three flags and blocks arrive as they
  happen, block kind classification, a missing / non-executable / dying
  script each becoming an inbox event rather than a fallback; the built-in
  detector stalls and re-fires at `stall_minutes = 0.01`; only builder jobs
  are watched; the daemon stops the monitor at job end.
- **Wake and notify.** `wait --for` returns the event, does not ack it,
  returns an unacked event that arrived first, never returns an acked one,
  and times out with exit 2; quiet hours queue and flush at the window end
  with an injected clock; a heartbeat lands only while a job runs; an owed
  limit resume is rescheduled at daemon start.
- **Library.** Filtering (role, grep, since, -n, composed), the `--since`
  refusal, the readable job line, `open`'s argv and its three refusals, the
  captured stream, and a real follow of a running job that drains and exits
  when the job is cancelled.
- **Doctor and docs.** Doctor green in fake mode; a sentinel script proves
  doctor spawns **nothing** without `--live` and nothing at all in fake mode;
  the ops-script probe's pass/warn/fail cases; every `hands <command>` named
  in README / INTEGRATION / PLAYBOOK / driver exists in `Api.COMMANDS`;
  INTEGRATION's config block actually parses; PLAYBOOK carries §10's example
  byte-for-byte; the driver's deny-list and bash-guard selftest.
- **Surface.** `test_help_lists_every_command_of_section_4` and
  `test_the_api_method_names_are_exactly_the_command_names` pin §4's twenty
  commands to `Api.COMMANDS`, `cli._PARAMS` and `hands --help` together, so
  the three cannot drift.

---

## 3. NOT PROVEN

Mandatory section, and the honest one. Nothing here is a to-do list item I
forgot; each is a claim the tests do not make.

1. **Everything that needs a real `claude`.** No `claude -p` has ever been
   run under hands — not once, in any unit. `tests/fake_claude.py` stands in
   everywhere, and `CLAUDE.md` forbids a test requiring the real binary. So:
   the §2 invocation is asserted as an argv, never accepted by the real CLI;
   stream-json parsing is proven against the events the fake emits, in the
   shapes I believe the real one uses; `session_id`, `--resume`, `num_turns`,
   `total_cost_usd`, `is_error` and `permission_denials` are all fake-shaped.
   `hands doctor --live` is the only thing in the repo that would spend a
   real turn, and two tests exist specifically to prove it *refuses* to.
   H-003 verified §2's six flags exist in claude 2.1.268 by reading
   `--help` — that is the strongest real-product evidence in the mission, and
   it is still not a run.
2. **The real transcript path** (finding H-001). `project_dir_name` is
   `re.sub(r"[^a-zA-Z0-9]", "-", cwd)`, derived from the
   `~/.claude/projects` directories on *this* machine. Four rules have
   witnesses; `.` in a cwd has none — no project on this machine comes from a
   dotted path. The field is derived and never opened by hands, so the blast
   radius is `hands tail` for a dotted cwd, but the rule is a prediction.
3. **The real limit notice text.** The widened `is_limit_notice` and
   `parse_reset_at` are validated against strings read out of the installed
   claude binary (`Usage limit reached · continuing automatically at 3pm`,
   the `toLocaleTimeString`/`toLocaleString` shapes) plus hand-authored
   variants. **No limit has ever been hit under hands.** A real notice in a
   shape I did not predict is stored raw (good) and falls back to
   `backoff_minutes` (acceptable) — but the resume-at-reset path itself has
   never run on a real reset time. Nor has any test waited a real interval:
   the clock is injected everywhere.
4. **The driver wake path** (§11, §16). Whether a finished background `Bash`
   task wakes an *idle* interactive Claude Code session is **untested and
   unknown** — it cannot be tested from inside this repo, and the whole
   driver model of §12 rests on it. `hands doctor` prints the procedure for a
   human to run from a driver session; it cannot run it. Related: finding
   H-007 — §11's "fake event" has no command behind it, and `hands pause`
   (the obvious candidate) writes no inbox event at all, so it cannot be the
   trigger; the procedure uses a gated send instead.
5. **The ops-repo monitor script contract.** `--pids/--transcript/--base` has
   only ever been answered by `tests/fake_monitor.py`, which I wrote to the
   same reading of §5 as the bridge. No real `watch_monitor.sh` exists in any
   ops repo I can see. If the real script names its flags differently, spells
   the pid list differently (hands sends one comma-separated argument), or
   does not blank-line-separate its blocks, the bridge is wrong in a way no
   test here can catch. Doctor's flag probe helps at install time; it is not
   proof.
6. **ntfy.** Only a recording transport has ever been posted to. No HTTP
   request has left this machine in any test; the URL shape
   (`<ntfy_url>/<topic>`), the title/message split, quiet-hours delay and the
   best-effort failure path are all asserted against a fake `post`. Whether a
   real ntfy server accepts these and whether the phone rings is unproven.
7. **The systemd unit.** Never started, never `enable`d, never `daemon-reload`ed.
   I ran `systemd-analyze verify systemd/handsd.service` while writing this:
   its only complaint is `Command /home/msi/.local/bin/handsd is not
   executable: No such file or directory` — because hands is not installed on
   this machine. So the unit is syntactically accepted, and the install step
   that would make it true (`uv tool install ~/git/hands`) has not been run
   here; U10 only verified that `uv tool install` prints "Installed 2
   executables: hands, handsd" into a throwaway `UV_TOOL_DIR`.
8. **`hands open`.** The argv is asserted; `exec` is injected in tests and
   never actually performed. No interactive `claude --resume` has been
   launched by hands.
9. **`hands tail`.** The transcript it reads in the test is one the test
   wrote. hands has never tailed a transcript Claude Code produced.
10. **Concurrency and endurance.** Every test is a short, single-daemon,
    fake-fast run. No test runs two daemons, a multi-hour job, a real
    multi-turn builder, a large spool (`hands jobs` over thousands of
    records), or a disk-full / permission-denied spool write. Crash safety is
    proven for one simulated crash point in `Spool`, not for the daemon as a
    whole.
11. **The remote face (§9) does not exist**, by mission scope —
    `src/hands/remote/` is absent. `button` appears in §8's authority table
    marked unavailable.
12. **`--human-confirmed` is not authentication.** The daemon cannot tell the
    CLI from the driver session; both are local clients of the same socket,
    same uid. `decided_by` records what the caller *declared*. Nothing proves
    a human said the stored `--quote`.

---

## 4. Gate verdicts

`./scripts/check`, run by me at tip `1ca707b` while writing this report:

    == ruff ==      All checks passed!
    == pytest ==    488 passed in 25.00s
    == cli smoke == (hands --help, handsd --help)
    check: green            [exit 0]

The mission's Acceptance list, item by item:

| # | Acceptance item | Verdict | Evidence |
|---|---|---|---|
| 1 | `./scripts/check` green on the pushed tip | **true** | the run above (ruff clean, 488 passed, smoke green, exit 0); re-run green with this commit before pushing |
| 2 | The U3 and U7 end-to-end tests pass against `fake_claude` | **true** | `tests/test_daemon.py::test_send_wait_result_end_to_end` and `tests/test_playbook.py::test_the_section_10_example_end_to_end`, re-run on their own: 2 passed |
| 3 | `hands --help` lists every command of DESIGN §4 | **true** | ran `uv run hands --help`: all twenty of send, wait, result, jobs, show, open, log, cancel, put, get, ls, tail, inbox, pipeline, approve, deny, pause, resume, status, doctor. Pinned by `test_help_lists_every_command_of_section_4` |
| 4 | `meta/FINAL-REPORT-1.md` exists with a non-empty NOT PROVEN section | **true** | this file, §3, twelve entries |
| 5a | Human gate: real `claude`, `hands send --role builder --context clear 'Reply with exactly this line…'` yields that `result` | **NOT RUN — the human's to run** | no real `claude` has ever run under hands (NOT PROVEN 1). The nearest proof is the same round trip against `fake_claude` (acceptance 2) |
| 5b | Human gate: from the driver session, a background `hands wait --for stop` wakes the session when `hands pause` is run | **NOT RUN — the human's to run, and one part of it is known false** | background wake is untested and unknown (NOT PROVEN 4). Note before running it: `hands pause` writes **no** inbox event (finding H-007), so it will not wake anything. Use the gated-send procedure `hands doctor` prints |

Everything else in the mission brief: U0–U10 all `[x]` in `meta/plan.md`,
none blocked, none yielded. The optional remote face (§9) is out of scope and
absent as instructed.

---

## 5. Findings

`meta/findings/FINDINGS.md`, seven entries. Six are open; all six are open
because they are *questions for someone else*, not because work is pending.

| id | one line | status | who answers |
|---|---|---|---|
| H-001 | The `.` case of the `~/.claude/projects` dir dashing has no witness on this machine; the rule is a prediction | open | **human/machine** — needs one real capture from a cwd containing a dot |
| H-002 | §6 calls the limit field an "error category"; on the wire it is `error`, inside `type: "system"`, `subtype: "api_retry"` | open | **architect** — wording of §6; code already reads `error` with a `category` fallback |
| H-003 | All six flags §2 names exist in claude 2.1.268 with that spelling | fixed — verification record, nothing to change | — |
| H-004 | §6's `origin` vocabulary (`driver\|playbook\|cli`) has no value for a job hands creates for itself; `playbook` used as least-wrong, `resumed_from` is the real identifier | open | **architect** — wants a fourth value (`limit`) if §6 is revised |
| H-005 | §6's automatic limit resume and §10's `builder.limited → resume` are the same resume; U7 makes §6 the owner and the rule the authorisation | open | **architect** — §10 should say which unit owns it |
| H-006 | §10 never says which value `only_if_run_in = "auto_runs"` checks; U7 reads the prompt's single group placeholder and refuses anything else at load time | open | **architect** — an explicit `run = "{n+1}"` key would need no inference |
| H-007 | §11's "fake event" for the wake check has no command behind it; `hands pause` writes no event, and doctor cannot file one | open | **architect** (name the procedure or the command) — and it directly affects the **human's** 5b gate above |

No finding was rejected, none tombstoned, and nothing was silently adapted:
every place the design was silent is named in a commit body, and every place
it was wrong or ambiguous is one of the seven above.
