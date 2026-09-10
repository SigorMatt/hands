# BUILDER-1-PROMPT — hands mission 1: the core

Kickoff line (the only way this mission is started or resumed):

    Read meta/BUILDER-1-PROMPT.md and execute the mission below its divider.

You are the builder for the `hands` repository. Read `DESIGN.md` in full
before anything else; it is the specification. Read `CLAUDE.md`. Then read
`meta/CHECKPOINT.md`: if it names a unit in progress, you are resuming —
run the recovery brief (§R) before taking any new unit.

---

## Mission

Deliver the hands core as specified in DESIGN.md §2–§8 and §10–§15: the
daemon, the local API, the CLI, the runner, the monitor bridge, limit
handling, the playbook engine, the job library, the wake path, notifications,
`doctor`, the systemd unit, and the docs. The optional remote face (§9) is
out of scope; leave `src/hands/remote/` absent.

At the end of this mission a human must be able to install hands on the
laptop, start the driver session from `driver/`, and run `hands send`,
`hands wait`, `hands result`, `hands inbox`, `hands pipeline` against real
`claude -p` processes, with a playbook chaining a run into a cold review.

## Execution model (binding)

- You are a thin orchestrator. You plan units, write the checkpoint, dispatch
  ONE sub-agent per unit (Task tool), verify the unit cheaply, record one
  line, move on. You run nothing longer than `git status`, `git log
  --oneline -5`, and `./scripts/check` yourself.
- Before each unit: write `meta/CHECKPOINT.md` (unit id, intent, what "done"
  means, standing constraints). After each unit: update it and append one
  line to `meta/journal.md`.
- Every unit ends with a commit AND a push. Unpushed work does not exist.
- Retry a failed unit once with the sub-agent's report attached; after two
  failures mark it `blocked` in `meta/plan.md` and continue with units that
  do not depend on it.
- Never edit product code yourself. Never edit `DESIGN.md` (file a finding
  instead, §F).
- Your reply when the mission ends (or halts) begins with one line:
  `VERDICT: mission 1 finished` | `VERDICT: mission 1 blocked <unit>` |
  `VERDICT: question <one line>`.

## Sub-agent brief (give this to every unit sub-agent, verbatim, plus the unit)

    You are implementing one unit of the hands core. Read, in this order:
    CLAUDE.md, DESIGN.md sections named by the unit, meta/CHECKPOINT.md,
    then only the files the unit touches. Rules: the design is the spec —
    where it is silent, choose the simplest thing and say so in the commit
    body; write the failing test before the code and confirm it fails;
    ./scripts/check must be green before you commit; one commit,
    `<area>: <one line>` + a body naming the unit and the DESIGN sections;
    push; never edit meta/plan.md, meta/CHECKPOINT.md, or DESIGN.md; if the
    unit needs a design change, stop and write a memo to
    meta/findings/FINDINGS.md instead of improvising; report in ≤12 lines:
    sha, files, tests added, what is NOT proven.

## §R Recovery brief

Dirty tree after an interruption: finish the unit under the sub-agent rules
if it can pass `./scripts/check`, else `git stash` as `wip <unit> <date>` and
record where it stopped in the checkpoint. Leave the tree clean. Push.

## §F Findings

Anything the design gets wrong, leaves ambiguous, or that a product fact
contradicts (a CLI flag that does not exist, a stream-json field with another
name) is a numbered finding in `meta/findings/FINDINGS.md`, with evidence
(command and output). Do not silently adapt; file it and choose the simplest
compatible behaviour.

## Units, in order

Unit ids are U0–U11. `meta/plan.md` is yours: fill it from this list in U0
and keep the checkboxes true.

**U0 Scaffold.** `pyproject.toml` (Python ≥ 3.11, `uv`, package `hands`,
entry point `hands = hands.cli:main`, deps: `httpx` only; stdlib `asyncio`,
`tomllib`, `sqlite3`/`json` as needed), `src/hands/__init__.py`,
`scripts/check` (ruff + pytest + `hands --help` smoke; exit non-zero on any
failure), `.gitignore`, `tests/conftest.py` with a `tmp_home` fixture that
points `HOME` and `~/.hands` at a temp dir. Gate: `./scripts/check` green
with one trivial test.

**U1 Config and spool.** `config.py`: load `~/.hands/<project>.toml` (§13),
expand `~`, validate roles and allowed roots, defaults for every optional
key. `spool.py`: job records as JSON files under `~/.hands/jobs/`, atomic
writes, the state machine of §6 with illegal transitions refused,
`roles/<role>.json` (`last_session_id`, `last_job`), an append-only inbox
with per-event ack, and a path-confinement helper (`resolve_under_roots`)
that rejects `..`, absolute escapes and symlinks leaving the roots. Gate:
tests for every transition, atomic write under a crash simulation, and
confinement escapes.

**U2 Fake claude and runner.** `tests/fake_claude.py`: an executable that
imitates `claude -p --output-format stream-json`: emits a `system`/`init`
event with a `session_id`, honours `--resume <id>` (same id back), reads the
prompt from stdin, and per a control string in the prompt can: emit a
`result` with given text, sleep N seconds, emit a rate-limit error in the
shape of an `api_retry`/`error` event followed by exit, or block until
SIGINT/SIGTERM (exit 143 on TERM, 130 on INT). `runner.py`: spawn the
per-role invocation of §2 with `claude` resolved from config (default
`claude`), parse stream-json line by line, record `session_id`,
`transcript_path` (`~/.claude/projects/<dashed cwd>/<session_id>.jsonl`,
compute the dashing the way Claude Code does and file a finding if
uncertain), `head_at_start`/`head_at_end` via `git rev-parse HEAD` in
`role.cwd` (`--no-optional-locks`), the verbatim `result`, `verdict` (first
line matching `^VERDICT:`), `stderr_tail`, `permission_denials`,
`num_turns`, `duration_ms`, `total_cost_usd`, `exit_code`. Cancel = SIGINT,
wait `cancel_grace_s` (default 20), SIGTERM. Gate: tests for clear, keep,
keep refused (no session; session's last job not terminal), verbatim
result, verdict extraction, limited detection, killed, and a job whose pid
is gone at daemon start becoming `orphaned`.

**U3 Daemon, local API, CLI.** `daemon.py`: asyncio, unix socket at
`server.socket`, newline-delimited JSON-RPC 2.0; one running job per role,
FIFO queue with `queue_depth`; graceful shutdown. `api.py`: methods for
every command in §4. `cli.py`: `hands <command>` as a thin client with
`--json` and readable output; `hands status`. `handsd --project <name>`.
Gate: end-to-end test in `tmp_home` — start the daemon against
`fake_claude`, `hands send --role builder --context clear`, `hands wait`,
`hands result` shows the verbatim result; a second `send` to the busy role
queues; aux queue accepts 4.

**U4 Files and gates.** `hands put/get/ls` confined to `files.allowed_roots`;
`--file path=content` on `send` written before spawn; gate triggers
(`--gate reason` or `gates.patterns`, case-sensitive substring match on the
prompt) → `held`; `cancel` gated per `role.cancel_gated`; `approve`/`deny`
with the authority table of §8: CLI decision final; `--human-confirmed`
requires `--quote "<the human's instruction>"` and stores it; a `held` job
cannot be released any other way; `denied` is terminal. Gate: table-driven
tests for the authority table and confinement.

**U5 Limits.** Detect `limited` from a rate-limit error event or a limit
notice in `result`. Store the raw notice always. Parse a reset time
defensively (ISO timestamps; "resets at <time>" with and without date;
"try again in N minutes"); when parseable, schedule the resume at that time
+ 60 s, else after `limits.backoff_minutes`. Builder resume =
`role.resume_line` as a new `clear` job with `resumed_from`; aux resume =
same prompt again. Stop after `limits.max_resumes` consecutive resumes
without a `done`. Inbox event per limit and per resume. Gate: tests for
each notice shape, the counter, and the stop.

**U6 Monitor bridge.** For every builder job: if `ops.monitor_cmd` is set,
run `<ops.repo>/<monitor_cmd> --pids <pid list> --transcript <path> --base
<head_at_start>` and file each blank-line-separated stdout block to the
inbox as `monitor.<kind>` where `<kind>` is the block's first word
lower-cased (`stall`, `tripwire`, or `event` if unrecognised). If unset, run
the built-in liveness/stall monitor of §5 (transcript mtime, `subagents/`
dir mtime, process CPU ticks; no progress and no liveness for
`monitor.stall_minutes` → one `monitor.stall` event; re-fires after another
interval). Tripwires are external-only in this mission. Stop the monitor
when the job ends. Gate: tests with a fake monitor script and with the
built-in monitor at `stall_minutes = 0.01`.

**U7 Playbook engine.** `playbook.py`: load `<role.builder.cwd>/<playbook.path>`
when a job starts (record its sha256 on every job it fires); rules per §10:
`on`, optional `verdict` regex with named groups, `then` ∈ `send | resume |
notify | stop`, placeholders `{name}`, `{name+k}` integer arithmetic,
`{job.*}`, `only_if_run_in = "auto_runs"`; unmatched event, missing or
unparseable verdict, exhausted limits → `stop`; `stop` pauses the engine,
records the reason, writes the inbox event; `hands pause|resume`; `hands
pipeline`. `origin = playbook` on fired jobs. Gate: table-driven tests
including the example playbook of §10 end to end against `fake_claude`
(run finished → review sent → blockers=0 → run 3 sent → run 4 not in
auto_runs → stop).

**U8 Wake path and notifications.** `hands wait --for <kinds> [--timeout s]`:
subscribe over the socket and return on the first inbox event of a listed
kind (the event is returned, not acked). `notify.py`: ntfy publish over
`httpx` for `stop`, `job.held`, `max_resumes` exhausted, daemon
start/crash; `quiet_hours` delays delivery (a scheduler flushes at the
window end), never actions; hourly heartbeat event while any job runs.
Gate: tests that `wait` returns on the event and times out otherwise; quiet
hours delay; ntfy mocked.

**U9 Job library.** `hands jobs [--role] [--grep] [--since] [-n]`, `hands
show`, `hands open` (execs `claude --resume <session_id>` in `role.cwd`;
refused while the job is `running`), `hands log <job>` (the captured
stream) and `hands log -f <role>` (streams the running job's events). Gate:
tests for filtering, refusal, and streaming.

**U10 Install surface.** `systemd/handsd.service` (user unit, `--project`
from an environment file), `hands doctor` (claude binary and version, ops
script accepts the three flags, allowed roots exist, one-turn `claude -p`
per role — skipped with a clear message when `HANDS_DOCTOR_FAKE=1` points
at `fake_claude`; prints the background-wake check procedure for the human
to run from the driver session), `docs/INTEGRATION.md` (DESIGN §14 steps as
a checklist), `docs/PLAYBOOK.md` (rule reference + the §10 example),
`README.md` (what hands is, install, first run). Verify `driver/` matches
the CLI surface and fix `driver/` if the CLI differs. Gate: `hands doctor`
runs green in fake mode in tests; docs reviewed by the sub-agent against
`hands --help`.

**U11 Final report.** `meta/FINAL-REPORT-1.md`: what changed, what was
proven by tests, what is NOT proven (mandatory: everything that needs a real
`claude`, the real transcript path, the real limit notice text, the driver
wake path), honest gate verdicts, the findings list. Then reply with the
verdict line.

## Budget guidance

Under quota pressure, yield in this order: U9, U10 (except `README.md` and
the systemd unit), U6 external-monitor variant, U8 quiet hours. Never yield
U0–U3, U4, U7, U11. A usable `send`/`wait`/`result`/`inbox` with the
playbook engine is the minimum that lets mission 2 be driven by hands.

## Acceptance

- `./scripts/check` green on the pushed tip.
- The U3 and U7 end-to-end tests pass against `fake_claude`.
- `hands --help` lists every command in DESIGN.md §4.
- `meta/FINAL-REPORT-1.md` exists with a non-empty NOT PROVEN section.
- Human gate (not yours to run; report it as not proven): on the laptop,
  with real `claude`, `hands send --role builder --context clear 'Reply
  with exactly this line and nothing else: VERDICT: hello'` yields a record
  whose `result` is that line; from the driver session, `hands wait --for
  stop` in the background wakes the session when `hands pause` is run.
