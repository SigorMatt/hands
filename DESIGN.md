# hands — DESIGN v3.28

Machinery that replaces the human relay between the planning brain and the two
Claude Code roles (builder, aux) on the Ubuntu laptop, and that keeps a series
moving without a human while everything goes by plan. Working name: `hands`.
The method it serves is described in WORKING-MODEL.md (agile-skills) and
OPERATING-MODEL.md (spanweave); hands changes the topology, not the method.
v3.19 (2026-10-14) folds in the first role-mode series' findings and the
mission 19 review; changes are in §36; earlier changes in §35–§17.

Status: proposal, 2026-09-10. Items marked DECIDED were settled in discussion.

---

## 0. Why this topology (recorded so the reasoning survives)

The Claude app and Claude Code run the same model in different harnesses. The
app's defaults favour dialogue and exposition, keep tool output out of the
context, and give Projects with instructions and memory that follow you
across phone and desktop. Claude Code's defaults favour action, fill context
with tool output, and are strongest at execution. Neither is "optimized for
long-horizon reasoning": that comes from disk-over-context and the repo-sync
rule, which hold in either harness.

Decision: use each where it is strongest and split the brain in two.
- The **architect** is a chat in this Claude Project: it designs missions,
  playbooks and decisions with the human, and its only outputs are files for
  the repo. It never drives.
- The **driver** is a Claude Code session on the laptop, reachable from the
  phone via remote control: it dispatches, monitors, verifies and reports.
  It never designs and never edits a repo.
- The handoff between them is files in the repo, which is already the rule
  for everything else. This removes the per-prompt relay (the bottleneck)
  without needing a public endpoint. Moving a design artifact to the laptop
  once per mission is not the bottleneck.
- If the laptop is out of reach, a fresh chat with the public repo URL and a
  sandbox clone covers planning; this Project keeps the design continuity.
- A chat brain as *driver* (the app talking to hands through a remote MCP
  server) remains possible as a later layer over the same core (§9). It is
  not built until experience with the Code driver says it is worth its
  tunnel.

---

## 1. What it replaces, what it must not touch

Replaces (OPERATING-MODEL §11, WORKING-MODEL §9): routing prompts to the
named role with the stated clear/keep rule; copying files onto the machine;
returning replies verbatim; monitoring runs; handling limit resets; detecting
builder state without asking the builder; and chaining the pre-planned steps
of a series (run → cold review → next run) so no human is needed while the
plan holds.

Retains for the human: series planning and decisions with the architect,
go/no-go on verdicts and gate stamps, direction and scope calls, vetoes,
applying a decisions file or a playbook, answering builder questions that are
judgment calls, acting on tripwires, opening PRs.

Invariants preserved (WORKING-MODEL §10), and how:

| # | Invariant | How hands satisfies it |
|---|---|---|
| 1 | Prompts are the only interface; clear/keep executed faithfully | `hands send` is the only way to reach a role; `clear` = fresh `claude -p`, `keep` = `claude -p --resume <id>`; `keep` is refused when the role has no resumable session |
| 2 | Replies return verbatim, files both ways | job records carry the `result` field of Claude Code's JSON output untouched; files are moved with sha256 |
| 3 | The brain's repo-sync loop stays independent | hands has no git commands for the brain and never summarizes; the driver verifies from its own read-only clone, the architect from its sandbox clone |
| 4 | One-report watches stay one-report | the per-job monitor reports each event once to the inbox; it never intervenes |
| 5 | Two sessions, sub-agents inside the builder | roles are fixed in config: `builder`, `aux`; one running job per role. The driver is not a role hands runs |
| 6 | Human decision points stay human | gated jobs enter `held`; only a human decision releases them (§8). The playbook moves *pre-planned* launches to plan time, where you approve the playbook itself |
| 7 | Disk-over-context; no competing state store | hands keeps routing state only (job records, session ids, pids, transcript paths) under `~/.hands/`; the playbook lives in the project repo |
| 8 | Confession culture unfiltered | no classification of replies beyond matching the reply's own `VERDICT:` line |

Added by hands: the **driver never writes** — enforced by Claude Code
permissions in the driver's own directory, not by prose (§12).

---

## 2. Session model — DECIDED: headless with resume

Builder and aux run as `claude -p` processes, one per prompt, not as
persistent interactive sessions. The driver is an ordinary interactive
session and is not managed by hands.

- `clear` = new session. `keep` = `--resume <session_id>` of the role's last
  session. The directive is structural, not trusted.
- A builder question ends the process with the question as `result`. The
  answer is a `keep` send.
- A limit hit ends the process with the notice as `result` (§6).
- The `system/init` event of `--output-format stream-json` yields the session
  id; the transcript path follows from it.
- SIGTERM leaves the turn unfinished and `--resume` continues it; the
  recovery brief (`WORKPLAN.md` §0.4) applies unchanged.

Facts relied on (code.claude.com/docs/en/headless, read 2026-09-10): `-p`
uses the subscription login unless `--bare`; `--resume` accepts a session id
from any directory, or the absolute transcript path; `-p` stays open while a
background subagent runs (10-minute idle ceiling,
`CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS`); a `Monitor` watch inside `-p` is
capped at minutes; SIGTERM exits 143 and records no result for the turn;
SIGINT ends the turn first; `--continue` refuses a session that is still
running.

Consequences:
- Never pass `--bare`: CLAUDE.md, agents, hooks and the sub-agent model must
  load exactly as they do today.
- Monitoring is done by hands from outside the process (§5).
- Sub-agents run in the foreground. `claude -p` waits for a *background*
  sub-agent at most `CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS` (600 s by
  default) and then terminates the whole session with a progress note as
  its result (observed 2026-09-12, mission 6, job `0mtygi953-ym63`). hands
  sets that variable to `0` in every role job's environment unless the
  config's `[roles.<r>] env` table overrides it; the `PreToolUse` hook in
  every driven repository refuses background sub-agents as it refuses
  background Bash; and a session the harness terminates is filed `failed`
  (§6), so the playbook's `resume` rule applies.
- Cancel = SIGINT, wait, then SIGTERM. Resuming after a cancel is allowed.
- Never resume a session whose job is still running. For a live job use
  `hands log -f <role>`; for a finished one, `hands open <job>` (§7).

Per-role invocation (from config, never from the driver):

    cd <role.cwd>
    claude -p [--resume <id>] --output-format stream-json --verbose \
      --model <role.model> <role.permission_flags> --permission-prompts none

Effort and context size stay in your existing settings.json. The prompt
arrives on stdin (10 MB cap; long content is written as a file first and
named in the prompt). hands records `git rev-parse HEAD` in `role.cwd` at
job start and end as `head_at_start`/`head_at_end` — facts about its own
job, used to fill playbook placeholders. This is hands' only git use.

---

## 3. Components — DECIDED: CLI-first core, optional remote face

    architect (chat, this Project)      ── files in the repo ──►  laptop
                                                                    │
    driver (Claude Code session, own dir, remote control on)         │
        │  Bash: hands <command>  (and `hands wait` in the background)
        ▼
    handsd  (user daemon, unix socket ~/.hands/handsd.sock)
      ├─ api         local JSON-RPC over the socket; the CLI is a thin client
      ├─ runner      spawns claude -p per job, one per role, stream-json parser
      ├─ monitor     per-builder-job liveness + tripwires (§5)
      ├─ playbook    event → action engine (§10)
      ├─ spool       ~/.hands/jobs/<id>.json, ~/.hands/roles/<role>.json, inbox
      ├─ notify      ntfy publisher
      └─ [optional]  mcp/ + oauth/ + gate/ behind a tunnel (§9, later)

    hands (CLI): send, wait, result, jobs, show, open, log, cancel,
                 put, get, ls, tail, inbox, pipeline, approve, deny,
                 pause, resume, status, doctor, token (optional face only)

Runtime state is the spool only; it survives daemon restarts. A running job
whose process is gone on restart is marked `orphaned` with its session id.

---

## 4. Command surface (the whole of it)

Mirrors the prompt catalogue (OPERATING-MODEL §10). Every command prints
JSON with `--json` (the driver uses that) or a readable form for you.

| Command | Args | Returns |
|---|---|---|
| `send` | `--role builder\|aux --context clear\|keep [--file path=content…] [--gate reason] [--prompt-file path\|--stdin\|prompt]` | job id, state. `--prompt-file` is the normal route for prose: the prompt never touches a command line; the client refuses a missing, unreadable, non-regular, empty or over-10 MB file on either route (`--prompt-file` or `--stdin`); the client then measures the **whole request** as it will go on the wire (prompt, `--file` payloads, gate, envelope) and refuses before connecting if it exceeds the daemon's line room, so a request never fails inside the socket (H-012); exit 2 means "the client did not deliver a completed request" (a refusal or a timeout) |
| `wait` | `<job>\|--for event-kind [--timeout s]` | job record when terminal / the event; used by the driver in the background (§11) |
| `result` | `<job>` | job record |
| `jobs` | `[--role r] [--origin o] [--grep pat] [--since d] [-n]` | recent job summaries |
| `show` / `open` / `log` | `<job>` / `<job>` / `<job>\|-f <role>` | record / `claude --resume` (refused while running) / captured stream, delivered in pages so a whole transcript is never one message (H-013) |
| `cancel` | `<job> --reason` | held for human unless `role.cancel_gated: false` |
| `put` / `get` / `ls` | path, content or `--from file` / path / path | sha256 and bytes / content / entries — confined to allowed roots |
| `tail` | `--role r -n` (n ≥ 1; capped at 1000) | last n transcript entries of the role's current or last session; `truncated: true` when the cap or the read window cut the answer short |
| `inbox` | `[--ack]` | unread events, verbatim (§11) |
| `pipeline` | — | active playbook (path, sha256, series), paused?, auto-runs used/allowed, resumes used, last rule fired, current stop reason |
| `approve` / `deny` | `<job> [--reason]` | per §8; from the driver only with `--human-confirmed` |
| `pause` / `resume` | — | pause/unpause the playbook engine |
| `status` | — | daemon, roles, running jobs, monitor state (`queue_depth` is capacity; `queued` is contents) |
| `notify` | `--test "<message>"` | sends one ntfy message to the configured topic; the first real proof of delivery |
| `kit check` | `<zip\|dir> [--repo path]` | validates a kit before it is sent (§26): paths, playbook loads, verdict regexes match the brief's vocabulary, kickoff equals `[series] kickoff`, no `quiet_hours`, no "as before"; prints the apply prompt |
| `who` | `[--daemon]` | the one-screen picture: this daemon's jobs and pipeline, every other `claude` process from /proc, interactive sessions' waiting/working state from their transcripts; `--daemon` (also the `handswho` entry point) pushes it on change and on request (§11) |
| `doctor` | — | claude binary, ops script flags, allowed roots, one-turn `claude -p` per role, background-wake check (§11) |

Gating is triggered by `--gate` or by configured prompt patterns (defaults:
`Apply ~/Downloads/`, `decisions-`, `playbook-`, `gh pr create`, `open the
PR`). Cancel is gated by default.

---

## 5. Monitoring — DECIDED: built into hands, no arming

With headless runs, `finished`, `builder gone` and `waiting on user` are the
process exiting with a result. What remains from the watcher is stall
detection and the commit tripwires, and hands starts those with every builder
job automatically:

- **Liveness**: transcript mtime, `subagents/` mtime, process CPU ticks,
  measured independently of progress. A busy-wait on a nested run is not a
  stall.
- **Progress**: new local commits, `.git/index` mtime (stat before any git
  command, `--no-optional-locks`), stash list.
- **Stall**: no progress and no liveness for `monitor.stall_minutes`
  (default 40) → one `monitor.stall` event, re-fires only after another
  interval.
- **Tripwires** on every new commit (the rules in your ops repo, unchanged):
  non-`plan:` commit touches the plan; code touched while the batch is a
  memo; serialized shape changed without explanation; landed on `main`;
  stash grew; `Batch <ID>` names a batch outside the run → one
  `monitor.tripwire` event per sha.

Implementation: hands invokes the ops repo's `watch_monitor.sh` with
`--pids`, `--transcript` and `--base` filled from the job record (the ops
script gains those flags; its `lastPrompt` derivation stays as a fallback
for manual use). hands tails the script's stdout and files each event block
to the inbox verbatim. The aux session no longer arms anything; the combined
status+arm prompt is retired.

---

## 6. Job lifecycle and limits

States: `held` → `queued` → `running` → `done` | `failed` | `limited` |
`killed` | `orphaned`; `held` → `denied`.

Job record (returned verbatim, stored forever):

    id, role, context, created, started, ended, origin (driver|playbook|cli|limit|phone|kit|architect)
    prompt, files_written, session_id, transcript_path, pid, exit_code
    head_at_start, head_at_end
    result            # the `result` field of the final message, untouched
    verdict           # the first line of result matching ^VERDICT: (or null)
    stderr_tail       # last 50 lines
    permission_denials, num_turns, duration_ms, total_cost_usd
    limit             # {category, message, reset_at} when state == limited
    failure_reason    # when failed: harness_terminated | nonzero_exit |
                      # no_final_result | error_result | no_num_turns | spawn_error
    gate              # {reason, decided_by: cli|driver|phone|playbook, decided_at, quote?}
    resumed_from      # job id, when this job is an auto-resume

Rules:
- A job is `failed` when the process ends without a final `result` event
  (`no_final_result`), with a `result` of subtype `error` (`error_result`),
  without `num_turns` (`no_num_turns`), when it exits non-zero without a
  limit (`nonzero_exit`), when it could not be spawned (`spawn_error`), or
  when stderr carries the harness's own termination line, anchored to its
  exact shape (`harness_terminated`). Precedence: a cancel stays `killed`
  and a limit stays `limited`; otherwise the termination line wins even
  over a `success` result, because the harness ends the session mid-turn
  and the "result" is whatever the model had said last (H-014's own case).
  With the bg-wait ceiling disabled the line should never appear; if it
  does, `resume` is the right reaction.
- One running job per role. A `send` to a busy role is queued (FIFO);
  builder queue depth 1, aux 4 (configurable).
- `keep` resumes `roles/<role>.json: last_session_id`; refused if absent or
  if that session's last job is not terminal. `clear` starts a new session.
- Terminal states write an inbox event and, where the playbook says so, an
  ntfy notification.

**Limits — DECIDED: automatic, no nudge.** All parties share one
subscription, so the driver and architect are limited whenever the builder
is; the reset is a wall-clock fact. hands detects a limit from a
`system`/`api_retry` event whose `error` field is `rate_limit` (there is no
`category` field on the wire; H-002) or from the limit notice in `result`,
parses the reset time, sleeps until then, and sends a new `clear` job with
`origin = limit` and `resumed_from` set: for the builder the prompt is
`role.resume_line` when the config sets one (`Resume WORKPLAN.md` for the
spanweave form), otherwise the limited job's own prompt (right for the
agile-skills form, whose kickoff line is checkpoint-driven; H-008); for aux it
is always the same prompt again. §6 is the sole owner of the limit resume;
the playbook never issues a second one (H-005). If no reset time is parseable, it retries on
`limits.backoff_minutes`. After `limits.max_resumes` consecutive resumes
without a terminal `done`, it stops and notifies. Every resume is an inbox
event.

---

## 7. Job library — DECIDED

The spool is the session library. Every job record holds the prompt, the
session id and the transcript path, so searching prompts is searching work
items (prompts name the run and batches).

    hands jobs [--role builder] [--grep "run 3"] [--since 2d]
    hands show <job>            # the full record
    hands open <job>            # claude --resume <session_id>; refused while running
    hands log -f builder        # live rendering of the running job's stream-json
    hands log <job>             # the captured stream of a finished job

`~/.hands/jobs/` is small JSON and is never pruned. Transcripts are Claude
Code's own files under `~/.claude/projects/`; hands stores their paths.

---

## 8. Human gates — DECIDED: discussion first, human decision final

A gated job enters `held` and hands notifies you (ntfy). Held jobs have no
timeout. Discussion first is the normal path: from the phone you open the
driver (Code tab) or the architect (this Project); the driver can show the
held job, the files it would apply and the inbox; the architect can read the
branch from its sandbox. You then decide.

Authority, without the optional remote face:
- `hands approve|deny <job>` run by you at the laptop: final; `decided_by: cli`.
- `hands approve <job> --human-confirmed` run by the driver: accepted only
  when your message in the driver session explicitly approves that job id;
  the driver's CLAUDE.md forbids it otherwise, and the record stores
  `decided_by: driver` plus the quoted instruction. This is the phone path.
- Nothing else releases a `held` job; gating on the default patterns cannot
  be disabled.
- `decided_by: driver` is a declaration, not authentication: the daemon
  cannot tell a driver quoting the human from a driver inventing a quote.
  The quote is the audit trail, and the driver's CLAUDE.md is the control.
  Authenticated approval belongs to the remote face (§9), if it is built.

With the optional remote face (§9), ntfy Approve/Deny buttons are added and
are final (`decided_by: button`), winning over a driver approval that has
not yet started the job.

Gated by default: decisions files, playbook files, PR opening, cancel.

---

## 9. Optional remote face (deferred)

Everything in §3–§8 works on the laptop with no network exposure. If a chat
brain is later wanted as a second driver, add a layer over the same daemon:

- MCP over Streamable HTTP bound to 127.0.0.1, exposed only through a
  tunnel (Tailscale Funnel or Cloudflare Tunnel), toggled by
  `hands expose on|off`.
- claude.ai custom connectors expect OAuth 2.1 with dynamic client
  registration and PKCE; hands would be its own single-user authorization
  server (passphrase, optional TOTP, opaque tokens hashed at rest, short
  TTL, `hands token revoke`), with Origin validation and rate limiting.
- The MCP tools mirror the command surface of §4 one-to-one.
- Gate endpoints for ntfy buttons (nonce as credential).
- Blast radius, stated plainly: a valid token lets the caller run `claude -p`
  with permissions bypassed, as your user, in the configured role
  directories. Treat it like an SSH key; keep `expose off` when idle;
  mcpgate can front the port later.

The only thing the core must do now to keep this cheap: the daemon's local
API and the CLI must be the same surface the MCP tools would wrap.

---

## 10. The playbook — DECIDED: pre-planned steps run without a human

The playbook is the architect's plan for what needs no judgment. hands
executes it; anything outside it stops the pipeline and notifies you. It
lives in the project repo on the series branch (`PLAYBOOK.toml` next to
`WORKPLAN.md`; agile-skills: `meta/PLAYBOOK.toml`), is written by the
architect as a file, moved to the laptop with the plan kit, and applied like
a decisions file: a gated `hands send --role builder "Apply … as
PLAYBOOK.toml with one plan-only sub-agent (single commit `plan: playbook …`,
push)"`. Your approval of that job is your approval of every launch the
playbook may make. hands loads the tracked file from `role.cwd` when a job
starts, refuses it when it differs from the committed copy (`git show
HEAD:<path>`; an unzipped, uncommitted playbook was found in force on
2026-09-12), and records its sha256 in every job it fires. Deleted at series close
with `WORKPLAN.md`.

### Events

`builder.done`, `builder.failed`, `builder.limited`, `builder.orphaned`,
`aux.done`, `aux.failed`, `monitor.stall`, `monitor.tripwire`,
`monitor.task_killed`, `monitor.orphan_processes`, `job.held`, `job.denied`.

### Actions

`send` (role, context, prompt with placeholders), `resume` (the same
prompt again, or the role's resume line when configured; counted against
`max_resumes`; for `failed` and `orphaned` jobs only, since `limited` is
owned by §6 and a `resume` rule on `builder.limited` is accepted as an
authorization that enqueues nothing), `notify` (ntfy, with a
message), `stop` (pause the pipeline, notify, record the reason). Unmatched
events, missing or unparseable `VERDICT:` lines, and exhausted limits are
always `stop`.

### Placeholders

Named groups from the matched verdict regex (`{n}`, integer arithmetic
allowed: `{n+1}`), and job fields: `{job.id}`, `{job.head_at_start}`,
`{job.head_at_end}`, `{job.session_id}`.

### Example (spanweave audit-fix series)

    version = 1
    series = "audit-fixes"

    [limits]
    auto_runs = [2, 3]        # runs hands may start on its own; anything else stops
    max_resumes = 3           # consecutive auto-resumes before stop
    # no quiet_hours: notifications are never delayed (decision 2026-09-12)

    [[rule]]                  # run finished cleanly → cold review
    on = "builder.done"
    verdict = '^VERDICT: run (?P<n>\d+) finished'
    then = "send"
    role = "aux"
    context = "clear"
    prompt = "Review WORKPLAN.md commits since the last review: commit on the branch"

    [[rule]]                  # review clean and next run pre-planned → go
    on = "aux.done"
    verdict = '^VERDICT: review run (?P<n>\d+) blockers=0'
    then = "send"
    role = "builder"
    context = "clear"
    prompt = "Execute WORKPLAN.md run {n+1}"
    run = "{n+1}"                  # must be listed in auto_runs, else stop

    [[rule]]                  # blockers → you
    on = "aux.done"
    verdict = '^VERDICT: review run (?P<n>\d+) blockers=[1-9]'
    then = "stop"
    message = "Review of run {n} has blockers"

    [[rule]]                  # memos and questions → you
    on = "builder.done"
    verdict = '^VERDICT: (awaiting decision|question)'
    then = "stop"

    [[rule]]                  # limits are §6's; nothing to say here
    on = "builder.orphaned"
    then = "resume"

    [[rule]]
    on = "builder.failed"
    then = "resume"

    [[rule]]
    on = "monitor.tripwire"
    then = "stop"

    [[rule]]
    on = "monitor.task_killed"
    then = "notify"
    message = "A task inside a role job was killed"

    [[rule]]
    on = "monitor.orphan_processes"
    then = "stop"

The `VERDICT:` line contract is the prompt contract's existing one-line
verdict, made literal: every builder run prompt and every aux review prompt
requires the reply's first line to begin with `VERDICT:` in the vocabulary
the playbook matches. The architect writes both the prompts and the
playbook, so they agree by construction. The `run` key names the value
checked against `auto_runs` explicitly (H-006); a rule with `run` but no
`auto_runs`, or whose expression cannot be computed from the verdict's named
groups, is refused when the playbook is loaded, never when it fires. hands
does not parse `WORKPLAN.md`; the architect lists the pre-planned runs in
`auto_runs` because it knows §2.

### What this changes in the method

- The launch decision for runs listed in `auto_runs` is taken at plan time.
- The unattended cold review runs the standard §0.2 protocol without the
  architect's run-specific questions; those come at the next planning round.
- Should-fix findings do not become batches on their own (shaping batches is
  architect work); they wait in the review file.
- Independent verification of milestone claims happens when the driver wakes
  on the next stop or when you next open the architect, not before the next
  auto-started run; the aux cold review is the in-line check.

### Stop → resume cycle

On `stop`, hands pauses the pipeline, notifies you, and writes the reason to
the inbox; the driver wakes (§11), reads the inbox, verifies the branch from
its clone, and reports to you with a `VERDICT:` line and a recommendation.
You decide with the driver (small: a `keep` answer, a run prompt) or take it
to the architect (large: a decisions file, a corrected playbook, a scope
call), whose output comes back as files. `hands resume` un-pauses the pipeline; so
does a `cli`-origin send, but only when that job **starts** (a held or
queued send changes nothing), and a stop is never cleared by a job the
playbook or the limit manager started. Every stop, from any component, goes
through one `stop()` that keeps the first reason and files one
notification; a later stop over an existing one is recorded in the inbox
only, as `pipeline.stop_suppressed` (outside the `stop` wake namespace;
H-011). `last_rule` is cleared when a different playbook file is loaded.

---

## 11. Inbox, wake-up, notifications

The inbox is an append-only event list in the spool, read by `hands inbox`
and acknowledged per event. Event kinds: job terminal (with verdict),
monitor event (verbatim block), playbook rule fired, stop (reason), gate
decided, limit/resume, heartbeat (hourly while any job runs, so silence is
distinguishable from death).

**Wake-up — there is none, by decision.** The driver arms no background
task. ntfy is the human's doorbell (every `stop` and every `held` job
reaches the phone); the human's `check` in the Code tab is the driver's;
`hands wait <job> --timeout <s>` remains a foreground tool for short waits
after an approval. `hands doctor` prints a one-time *notification* check (a
gated send, which files a real `job.held` without spending a turn, or
`hands pause`, which files a `stop`), not a wake procedure.

History, kept so the decision is not relitigated: a background `hands wait
--for stop,held` did wake an idle driver session on Claude Code 2.1.268
(observed 2026-09-11), but the harness kills idle background tasks
intermittently (a control `sleep 3600` died alongside the wait with 70% of
memory free; the "low memory" text it prints does not describe the
machine), and each kill costs a driver turn, the only thing in hands that
costs tokens. Narrowing the wait to in-flight work still cost a turn every
few minutes during a mission. The wake-path question is answered: it works
and it is not worth its price on Claude Code 2.1.x.

**Notifications** (ntfy, in scope — it is how you learn you are needed):
`stop`, `job.held`, `max_resumes` exhausted, daemon start/crash. Not for
routine progress. Notifications are never delayed: `quiet_hours` is retired (decision
2026-09-12; a playbook that sets it is refused at load with a message).
Topic: random, private; ntfy.sh or self-hosted (§16).

---

## 12. The driver kit — artifact

hands ships `driver/` with everything the driver session needs, generic with
a parameter block (project name, repo URL, branch, plan file, ops repo,
playbook path):

- `driver/CLAUDE.md` — the driver's instruction:
  1. You never edit any repository and never write outside `~/hands-driver/`.
     Your only actions are `hands` commands and read-only git in your clone.
  2. On any message about a run or series, and on every wake: `hands inbox`
     first, then `git fetch` and read the plan and open questions in full
     from your clone. Files win over memory. If the fetch fails, say so and
     do not proceed on memory.
  3. Every instruction to a role goes through `hands send` with an explicit
     `--context`. Never ask the human to paste anything.
  4. Every run prompt and review prompt requires a first-line `VERDICT:` in
     the vocabulary of the active playbook (`hands pipeline`).
  5. Gated sends are announced before sending. `hands approve
     --human-confirmed` only when the human's message in this session
     explicitly approves that job id; quote it.
  6. Prompts the architect wrote arrive as files (the human places the
     kit under `~/Downloads`); send them with `hands send --prompt-file`.
     Prompts you compose yourself are short and go in quotes; quoting
     makes no character safe: one from the guard's refused set is refused
     inside quotes too. You cannot create files, so never plan
     on writing a prompt file yourself; if a prompt needs to be a file and
     is not one, say so and stop.
  7. Verify milestone claims against the remote before reporting them.
  8. Never arm a background task. After a dispatch or a report, stop
     talking. The human's message `check` is your wake: run rule 2 and
     report. `hands wait <job> --timeout <s>` in the foreground is fine for
     a short wait after an approval. `hands` exit 2 means the client did not
     deliver a completed request: a refusal or a timeout, not an event.
  9. Reports to the human start with a `VERDICT:` line; deviations are
     flagged, not acted on; retract on contradicting evidence.
  10. Design changes, new batches, playbook edits and decisions files are not
      yours to write; say "this is for the architect" and stop.
- The Bash guard treats git as an allowlist of options per subcommand:
  each allowed subcommand carries the exact options the driver needs
  (`log`: `--oneline`, `-n`, `--grep=`, `--format=`, `--stat`,
  `--name-status`, revisions and paths; `show`: `--stat`, `--name-status`,
  `rev:path`; `fetch`: `-q`, a remote name; `ls-remote`: `--heads`,
  `--tags`, a remote; `rev-parse`: `--verify`, `--short`; `diff`:
  `--stat`, `--name-status`, `--name-only`; `grep`: `-n`, `-c`, `-l`,
  `-i`, `-e`; `cat-file`: `-t`, `-p`, `-e`; `ls-files`, `ls-tree`,
  `branch --list`, `remote -v`, `status`) and anything else, including
  every option that names a program or a file to write
  (`--upload-pack`, `--exec`, `--output`, `--ext-diff`, `--textconv`,
  `--config-env`, `-c`, `--edit-description`), is refused because it is
  not listed. The `-C` value must be a path that does not begin with `-`.
  The remaining surface is the listed options themselves, which the report
  enumerates. (Review 5 should-fix 1: denylists of git options lost three
  rounds.)
- `driver/settings.json` — enforcement: `permissions.deny` for Edit, Write,
  MultiEdit, NotebookEdit (MultiEdit stays: it is a known permission-rule
  name in 2.1.x even where the CLI warns; H-010 as amended); `permissions.allow` for `Bash(hands *)`,
  `Bash(git fetch *)`, `Bash(git log *)`, `Bash(git show *)`,
  `Bash(git diff *)`, `Bash(git ls-remote *)`, `Bash(git status *)`,
  `Bash(cat *)`, `Bash(ls *)`; everything else asks. The driver's working
  directory is `~/hands-driver/<project>/` containing only CLAUDE.md,
  settings, and a read-only clone under `repo/` (fetch only, no push URL).
- `driver/README.md` — starting the session with remote control on, and how
  the phone Code tab is used.
- `docs/ARCHITECT-INSTRUCTION.md` — the instruction for this Project:
  outputs are files for the repo (missions, playbooks, decisions, design
  docs), never prompts for pasting; read the branch with git in the sandbox
  before planning; state what is not on disk. Also usable by an ad hoc chat
  when the laptop is out of reach.

---

## 13. Configuration (`~/.hands/<project>.toml`)

    [server]
    socket = "~/.hands/handsd.sock"
    ntfy_topic = "…"
    ntfy_url = "https://ntfy.sh"

    [roles.builder]
    cwd = "~/git/spanweave"
    model = "opus"
    permission_flags = "--dangerously-skip-permissions"
    resume_line = "Resume WORKPLAN.md"
    queue_depth = 1
    cancel_gated = true

    [roles.aux]
    cwd = "~/git/spanweave"
    model = "opus"
    permission_flags = "--dangerously-skip-permissions"
    queue_depth = 4
    # [roles.aux.env] overrides the environment hands gives the role; hands
    # sets CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0 unless a table sets it.

    [ops]
    repo = "~/spanweave-ops"
    monitor_cmd = "watch_monitor.sh"

    [monitor]
    stall_minutes = 40

    [limits]
    backoff_minutes = 30

    [playbook]
    path = "PLAYBOOK.toml"        # relative to roles.builder.cwd

    [files]
    allowed_roots = ["~/git/spanweave", "~/Downloads", "~/spanweave-ops"]

    [gates]
    patterns = ["Apply ~/Downloads/", "decisions-", "playbook-", "gh pr create", "open the PR"]

One config per project (agile-skills: `meta/` paths, `harness/ops/`
commands). `handsd --project spanweave`.

---

## 14. Repository layout and integration

    hands/
      README.md  DESIGN.md  CHANGELOG.md
      pyproject.toml                 # python ≥3.11, uv; stdlib asyncio + tomllib, httpx
      src/hands/
        daemon.py  api.py  runner.py  spool.py  monitor.py  playbook.py
        notify.py  cli.py  config.py
        remote/                      # optional face (§9), empty until wanted
      systemd/handsd@.service  systemd/handswho@.service  # user units, per project
      driver/CLAUDE.md  driver/settings.json  driver/README.md
      docs/ARCHITECT-INSTRUCTION.md  docs/INTEGRATION.md  docs/PLAYBOOK.md
      meta/                          # hands' own missions, checkpoint, ledger,
                                     # in the agile-skills form
      bootstrap/dispatch.sh          # v0 dispatcher used by mission 1 (§15)
      tests/                         # runner against a fake `claude`; spool state
                                     # machine; playbook engine; gate authority
                                     # table; path confinement; wake path

Per project, once:
1. Write the config; `hands doctor`.
2. Create `~/hands-driver/<project>/` from `driver/`, fill the parameter
   block, clone the repo read-only under `repo/`, start the session with
   remote control on.
3. Replace this Project's instruction with `docs/ARCHITECT-INSTRUCTION.md`.
4. Ops repo: `watch_monitor.sh` accepts `--pids`, `--transcript`, `--base`;
   `status_check.sh` is no longer needed by hands.
5. Plan kit gains `PLAYBOOK.toml`; run and review prompts gain the
   `VERDICT:` first-line requirement.
6. Retire: the status+arm aux prompt, the `~/Downloads` relay of prompts
   (files still land there, once per planning round), the "name the session
   and say clear context" preference (enforced by the CLI now).

Unchanged: `WORKPLAN.md` §0–§5, `meta/*`, the sub-agent brief, the recovery
brief, the cold-review protocol, the tripwire rules, the decisions-file
approval semantics.

---

## 15. Bootstrap — DECIDED

Build hands with the method itself, driven by a Code driver from day one:

1. Finish this design here. The architect (this Project) produces the kit:
   `meta/BUILDER-1-PROMPT.md` (units: config + spool; runner against a fake
   `claude`; local API + CLI; monitor bridge; limits; playbook engine; job
   library; wake path; ntfy; systemd; driver kit; docs), `driver/` (§12),
   `docs/ARCHITECT-INSTRUCTION.md`, and `bootstrap/dispatch.sh`.
2. `dispatch.sh` v0 is hands before hands exists: ~20 lines that run
   `claude -p` detached with JSON output into `~/.hands/bootstrap/<n>.json`
   and print the job number. The driver's `settings.json` allows it.
3. On the laptop: create the repo, add the kit, start the driver session in
   `~/hands-driver/hands/` with remote control on.
4. From the phone's Code tab: "kick off mission 1". The driver runs
   `dispatch.sh` with the fixed kickoff line, checks the spool later (a
   background `sleep`+`cat`, or you nudging it — the wake path is itself a
   mission-1 unit), verifies the pushed branch from its clone, and reports.
5. Mission 2 onward uses the real `hands`, the playbook, and the wake path.
   Whether to add the remote face (§9) is decided from that experience.

Manual relay during bootstrap is limited to: moving the kit once, and the
one-time checks in step 4.

---

## 16. Open questions

- ANSWERED 2026-09-11, yes: a background `hands wait --for stop,held` woke
  an idle driver session on Claude Code 2.1.268 within seconds of a real
  `job.held` event (driver report, job 0mtxb7ecx-fbmx).
- ntfy.sh with a random topic vs self-hosted ntfy.
- Builder queue depth > 1 (a queued builder prompt is a scheduling decision
  the method currently makes in chat).
- Whether the driver should also run the `hands doctor`-style checks on a
  schedule (daemon health) or leave that to systemd.

---

## 17. Changes from v2

- §0 added: the architect/driver split and the reasoning behind it; the
  chat brain is no longer the driver.
- Core is CLI + local API over a unix socket; the remote MCP face, OAuth,
  tunnel and ntfy buttons are an optional deferred layer (§3, §9).
- Driver independence enforced by Claude Code permissions in its own
  directory with a read-only clone; the driver kit is a shipped artifact
  (§12), replacing the v2 "brain project instruction".
- Gates work without a tunnel: laptop CLI, or the driver with
  `--human-confirmed` quoting your instruction (§8).
- Wake-up: `hands wait --for …` as a background task in the driver session,
  verified by `hands doctor` (§11).
- Bootstrap sequence with `dispatch.sh` v0 and the driver from mission 1
  (§15).
- Job record `origin` and `decided_by` vocab updated; `status`/`doctor`/
  `pause`/`resume` commands added (§4, §6).

---

## 18. Changes from v3 (mission 1 findings)

- H-002: the limit event's field is `error`, not a category (§6).
- H-004: `origin` gains `limit` (§6); `hands jobs --origin`.
- H-005: §6 is the sole owner of the limit resume; a playbook `resume`
  rule applies to `failed`/`orphaned`, and on `limited` is authorization
  only (§10). The example playbook drops its `builder.limited` rule.
- H-006: `only_if_run_in` is replaced by an explicit `run = "<expr>"` key,
  checked at load time (§10).
- H-007: `hands pause` files a `stop` event (`paused by human`); the wake
  check may use it or a gated send (§11).
- H-008 (architect): `role.resume_line` is optional; absent, a limit
  resume re-sends the limited job's prompt, which is the agile-skills
  kickoff line (§6).
- `hands notify --test` added (§4); `status` documents capacity vs contents.
- Open question on the wake path answered: proven (§16).
- Bootstrap mode retired: `bootstrap/dispatch.sh` and the driver's
  bootstrap section are removed (§15 stays as history).

---

## 19. Changes from v3.1 (mission 2 review)

- `hands send --prompt-file PATH` (§4); the driver's rule 6 sends prose as
  files (§12). The Bash guard is quote-aware since `14507ca`, but files are
  the route that needs no guard at all.
- `decided_by: driver` documented as a declaration (§8).
- A pause over an already-stopped pipeline keeps the first stop reason and
  files no second notification (review should-fix 4).
- `resume_line = ""` is refused at config load (should-fix 5).
- `hands notify --test` prints the HTTP status on the failure path too
  (should-fix 7).
- `hands status` describes whichever monitor is deciding (should-fix 2).
- Guard: the mutating-git check applies to the subcommand position only, so
  `rev-parse <sha>^{commit}` passes; the self-test lives in `tests/`.
- Wake path: a background wait can be killed by the host under memory
  pressure; the driver's rule 2 (inbox first on every wake) is the recovery,
  observed once on 2026-09-11.

---

## 20. Changes from v3.2 (mission 3 review, driver observations)

- Pipeline state (§10): a stop is cleared only by `hands resume` or by a
  `cli`-origin send when it starts; never at gate time, never by a
  playbook- or limit-started job. One `stop()` for every component; the
  first reason is kept; `last_rule` resets on a new playbook file. (Driver
  observations 2026-09-11/12; review 3 should-fix 4.)
- Guard (§12): the git subcommand allowlist applies to every `git` token
  anywhere in a command, not only at a segment's first word; `find` with
  `-exec`/`-execdir`/`-ok`/`-delete` is forbidden. (Review 3 blocker 1.)
- Guard tests: `tests/test_bash_guard.py` carries an adversarial table
  written independently of `SELFTEST`. (Review 3 should-fix 1.)
- `MultiEdit` deny rule restored (should-fix 2; H-010 amended with both
  observations: the CLI warning and the binary's rule table).
- Empty strings are refused wherever a key is optional (`monitor_cmd`,
  `resume_line`, `ntfy_topic`), and `hands doctor` reports a config error
  instead of crashing. (Should-fix 5, 8.)
- `--prompt-file` size cap (§4). (Should-fix 9.)
- Driver rule 6 rewritten to match what the driver can do. (Should-fix 10.)
- Playbook example gains a `kit applied` rule so applying a kit is a notify,
  not a stop.
- Reports are snapshots; a report whose claim expires is corrected by an
  appended dated line, never rewritten. (Review 3 blocker 3.)

---

## 21. Changes from v3.3 (mission 4 review)

- Guard git policy (§12): before the subcommand only `-C <path>` and
  `--no-pager` are allowed; any other leading option (`-c`, `--config-env`,
  `--exec-path`, `--git-dir`, …) is refused. After the subcommand,
  `--output`, `--output=…`, `--ext-diff`, `--textconv`, `-O`,
  `--open-files-in-pager` and `--config-env` are refused. `find` also
  refuses `-fprint`, `-fprint0`, `-fprintf`, `-fls`. The NOT PROVEN section
  of a report states the surface honestly; review 4 blocker 1.
- `ops.monitor_cmd` must be a relative path without `..` naming an
  executable regular file under `ops.repo` at load; review 4 blocker 2.
- H-011: the suppressed-stop event is `pipeline.stop_suppressed`.
- Prompt cap semantics and exit-code meaning made explicit (§4); the same
  check on both routes; a non-regular file is refused before opening.
- Negative assertions in tests compare against path-stripped text; the
  gate's determinism is a property, not a sample (review 4 should-fix 1, 2).
- `hands pipeline` marks `last_rule` `stale: true` when its playbook sha256
  is not the loaded one (should-fix 7).
- Daemon memory: stream-json events are written to the job's log file as
  they arrive and never accumulated in memory; the daemon's resident size
  must not grow with a job's transcript (peak 959 MB observed on a 60-turn
  mission).
- Operational: a mission's builder and sub-agents add several `claude`
  processes; idle sessions from other projects should be closed while a
  mission runs, or the driver's background wait gets killed and re-armed
  on every memory dip, a turn each time (56 observed).
- Wake path (§11): the driver arms its wait only while work is in flight;
  idle sessions arm nothing. Grounded in the 2026-09-12 diagnostic.
- Role sessions never use background tasks (§2, §21): the harness reaps
  them, so a builder sub-agent's long background job could die silently
  mid-mission. A `PreToolUse` hook in every driven repository refuses
  `run_in_background` and hand-rolled daemonization; foreground Bash with a
  timeout is the only way to run something long. Hooks run under
  `--dangerously-skip-permissions`, so this holds for builder and aux.

---

## 22. Changes from v3.4 (mission 5 review, wait retired)

- Driver wait retired (§11, §12 rule 8): the human's `check` is the wake.
- Guard git policy becomes a per-subcommand option allowlist (§12).
- Prompt cap: the client measures the whole request on the wire before
  connecting (§4; review 5 blocker 1, H-012).
- `tail`: `n ≥ 1`, cap 1000, `truncated: true` when cut (§4; review 5
  blocker 2). `log` pages (H-013).
- Backlog items 1–4 (harness-kill detection, per-job scope and orphan
  accounting, REVIEW-3 deferrals, playbook rules) move to mission 7 so
  mission 6 stays a review-closing mission.

---

## 23. Changes from v3.5 (mission 6 review, harness termination)

- §11 rewritten without its self-contradiction: no wake, by decision; the
  history kept in one paragraph (review 6 should-fix 6).
- Harness termination of a role job is `failed`, not `done` (§2, §6); the
  bg-wait ceiling is disabled for role jobs; the hook covers background
  sub-agents; root `CLAUDE.md` says sub-agents run in the foreground.
- Review base: the cold review reads the commits since the last `review:`
  commit on the branch, computed by the reviewer, not `{job.head_at_start}`
  of the job that finished — a resumed mission's last job starts mid-mission
  (review 6 scope note). The protocol and the playbook example say so.
- Reports are drafted outside the tree or excluded from `git add`; a unit
  commit never carries another unit's draft (review 6 should-fix 3).
- Doc-truth sweeps compare every tracked text file, not a list (review 6
  blocker 1, should-fix 1); positionals are refused under the name the
  human typed (should-fix 5); the UTF-8 check walks the same tree the size
  measurement walks (should-fix 4).

---

## 24. Changes from v3.6 (mission 7a review; mission 8 specification)

Review 7a items:
- §2, §6, §13 now carry the harness-termination rule the changelog claimed
  (review 7 should-fix 1); the terminating-line matcher is anchored to the
  harness's exact message and never overrides a successful result
  (should-fix 2); a mission's U0 commit uses the `plan:` prefix, since it
  changes gate inputs (should-fix 3); the doc sweep reads every tracked
  file except binary ones, with `meta/` history excluded by path but live
  instruction files under `meta/` included (should-fix 4); `hands show`'s
  `failure` line is pinned by a test (review 7 blocker 1).

Mission 8, the detectors:
- `monitor.task_killed`: the monitor watches each role job's stream-json
  for the harness's task-killed notice and files the event with the task's
  command line.
- Per-job scope: the runner starts each `claude -p` inside a transient
  systemd user scope (`systemd-run --user --scope`) when available, else a
  new process group; the monitor reads the scope's `cgroup.procs` for the
  live pid set (and passes it as `--pids`); at job end anything still in
  the scope is filed as `monitor.orphan_processes` with its command lines,
  then the scope is killed. Cgroup membership survives double forks; the
  process-group fallback does not, and `hands doctor` says which is in
  force.
- The example playbook maps `monitor.orphan_processes` to `stop` (§32:
  `monitor.task_killed` maps to `notify`, since the detector cannot tell
  a reap from a `TaskStop`).

Mission 8, the phone channel (§8, §11):
- `[notify]` config section: `ntfy_url`, `ntfy_topic` (events, as today),
  `cmd_topic` (commands, optional), `cmd_secret` (required when `cmd_topic`
  is set), `who_topic`, `who_cmd_topic` (optional). All topics random.
- `handsd` subscribes to `cmd_topic` (outbound long-poll; no ingress) and
  accepts `approve <job>`, `deny <job> [reason]`, `pause`, `resume`,
  `status` (answered by publishing a status summary to `ntfy_topic`).
  Typed commands carry `cmd_secret` as their last word; a held-job
  notification carries Approve/Deny action buttons that publish
  `approve <job> <nonce>` / `deny <job> <nonce>` where the nonce is 32
  random bytes minted per held job, single-use, dying with the job; the
  long-term secret is never placed in a notification. Decisions taken this
  way are `decided_by: phone`, the first authenticated approval path
  (§8's declaration limitation applies to the driver only).
- Nothing but commands and status lines ever travels either topic.

Mission 8, `hands who` (§4, §11): the claudewho prototype (2026-09-12)
folded in; reads this daemon's state in-process; labels roles `role <r>`,
the human's own interactive session in a role directory `(your session)`,
driver directories `driver:<project>`; a hierarchy of daemon → jobs →
processes and session → processes; session states debounced over two
scans; the human's own sessions shown but never fingerprinted; pushes on
change and on a `status`/`who`/`check`/`?` command on `who_cmd_topic`;
ships as an optional user unit `handswho@.service` (per project, §29), off
unless enabled;
`hands doctor` reports notifications, the command channel and who as
on/off, never as errors.

Conventions (docs/ARCHITECT-INSTRUCTION.md): mission files are
self-contained (the sub-agent brief and §R written out every time); no
budget guidance, since limits pause and resume; no `quiet_hours`; the
architect reads the branch on ntfy and writes the next kit from disk.

---

## 25. Changes from v3.7 (mission 8 review and open decisions)

- §6 vocabularies reconciled with the wire: `failure_reason` and
  `decided_by` list what the code writes (review 8 should-fix 2). The
  termination-line precedence is reversed back to H-014's reading: it wins
  over a `success` result (FINAL-REPORT-8 §5 item 1).
- H-016 closed: §10's events list and example carry the two detector rules.
- `quiet_hours` retired from the code, §11, doctor's text and the config
  (FINAL-REPORT-8 §5 item 3); a playbook setting it is refused.
- Playbook must match the committed file (§10).
- Phone channel after a daemon restart: nonces are re-minted for every job
  still `held` and their notifications re-sent with fresh buttons
  (FINAL-REPORT-8 §5 item 5). `who_cmd_topic` stays secret-less: its words
  are read-only (item 4). `monitor.task_killed` cannot tell a harness reap
  from a `TaskStop`; the event says so in its payload (`cause: unknown`).
- Review 8 should-fix 1, 3, 4: `main()`'s exit code pinned on the socket
  route; `_last_resort` checks group membership before `killpg`; the
  reconnect warning never carries the topic URL.
- Stale `meta/prototypes/` ruff exclude removed.

---

## 26. Changes from v3.8 (mission 9 review; mission 10 specification)

Review 9 items: the REVIEW-8 should-fix 3 check is made to fail on the
condition it guards; `docs/INTEGRATION.md`'s statement of when a job is
`done` matches §6; the HEAD comparison of the playbook runs git with a
clean environment (`-c core.autocrlf=false`, no `GIT_DIR`/`GIT_WORK_TREE`
inherited) and compares normalized bytes; H-017 quotes v3.7 correctly.

Mission 10, the closed phone loop:
- `[series] kickoff` in the playbook names the series' fixed kickoff line.
  `go <secret>` on `cmd_topic` sends exactly that line as a `clear` send to
  the builder, `origin: phone`; there is no other way to start work from
  the phone, and `go` is refused while a job is running or queued for the
  builder, or while a playbook is not loaded.
- Kit transport: a message on `cmd_topic` whose body is `kit <secret>` and
  which carries an ntfy attachment is fetched by handsd into
  `[files] kit_dir` (default `~/Downloads`) under the attachment's own
  name (sanitized to a basename; `.zip` only), size-capped by `[files]
  kit_max_mb` (default 20), never unzipped, never executed; an inbox event
  and a notification say `kit received <name> <bytes> <sha256>`. The
  apply remains a gated job with buttons.
- `hands who` matches an interactive session to its transcript by pid,
  which the transcript's first line records, never by directory; a job in
  the same directory as the human's session is never shown under it.
- `docs/INTEGRATION.md` describes the loop end to end, phone only.

Mission 10, the architect's tooling:
- `docs/ARCHITECT-HANDBOOK.md` and `templates/` (a mission brief, a
  missions playbook, a runs playbook, a review protocol) are the
  architect's onboarding; the instruction gains rule 13 (clone, read,
  `kit check` before emitting).
- `hands kit check <zip|dir> [--repo path]`: every entry is a repository
  path under the given repo (or the current one); if the kit carries a
  playbook it loads under the current engine, sets no `quiet_hours`, and
  its `[series] kickoff` equals the kickoff line the brief fixes; every
  `verdict` regex of the playbook in force (the kit's, else the repo's)
  matches at least one literal in the brief's final-reply vocabulary, and
  every verdict literal in the brief matches some rule; the brief contains
  neither "as before" nor a "Budget guidance" section; when a rule sends a
  review, the protocol file it names exists. Output: one line per check,
  the apply prompt for the kit, exit 0 only when everything passes. It
  runs anywhere hands installs, including an architect's sandbox.

---

## 27. Changes from v3.9 (mission 10 review; mission 11 specification)

Resolutions of the mission 10 findings and review:
- H-020: `hands who` matches an interactive `claude` process to its
  transcript through `~/.claude/sessions/<pid>.json`, whose `sessionId`
  names the transcript; the transcript remains the source of the session's
  state; when no sessions file exists for a pid the line says
  `transcript: by directory` and is never attributed a job's transcript.
- H-021: `hands kit check` verifies every `verdict` rule of the playbook,
  `aux.done` included, against the vocabulary the review protocol
  specifies (the `VERDICT: review …` line), and refuses a kit whose brief or
  protocol vocabulary a rule cannot match; a broken builder rule is never
  excused by the apply-verdict exception (review 10 should-fix 4).
- H-019: the playbook's `[series]` table is `name` and `kickoff`; a bare
  `series = "…"` string remains accepted as the name.
- H-018: `phone` and `kit` are job origins (§6); a job of either origin
  un-pauses the pipeline when it starts, as a `cli` one does.
- `go` is refused while the builder has a running, queued or **held** job
  (should-fix 1). The post-exit sweep signals only a group whose leader is
  the job's own pid and whose members are all descendants (should-fix 3).
  `kit check` refuses paths outside the repo, absolute paths, `..`, and a
  protocol path a rule names that the kit or repo lacks (should-fix 5). A
  malformed attachment URL is refused before any fetch and the refusal is
  an inbox event (should-fix 6). `docs/INTEGRATION.md`'s `done` statement
  is pinned by a test (should-fix 7).

Mission 11, the apply from the kit (review 10 should-fix 2):
- When `kit <secret>` receives a zip, `handsd` creates a **held** builder
  job whose prompt is the standard apply prompt built from the zip: the
  files it replaces and adds (from the zip's entries against the repo), the
  commit message (the first line of a `KIT.md` inside the zip, else `plan:
  kit <name>`), the plan-only sub-agent, the `VERDICT: kit applied <sha>`
  reply; `origin: kit`; gate reason `apply <name>`. The held notification
  carries the buttons. The zip itself is never unzipped by `handsd`; the
  builder does that. `hands kit check` writes `KIT.md`'s expected shape
  and prints the same prompt, so what the architect saw is what runs.
- The loop is then phone-only: kit → buttons → `go` → buzz.

Mission 11, the driver role and `consult` (§8, §10, §11):
- A third role, `driver`: headless, started by `handsd` only through a
  `consult` action; cwd is the driver directory (`~/hands-driver/<project>`)
  with its fetch-only clone, `driver/CLAUDE.md`, and the driver guard in
  **role mode** (`HANDS_ROLE=driver` in the environment): read-only git,
  `hands show|jobs|inbox|pipeline|status|tail|kit check`, `hands send
  --context keep` to the role named in the consultation, `hands resume`;
  refused: `approve`, `deny`, any `--context clear` send, `put`, `pause`,
  `go`, and every write. No permission bypass: the role runs with
  `permission_flags` empty so `settings.json` and the hook are the law.
- `then = "consult"`: sends the driver role the event, the job record and
  the role's last reply verbatim, with the question "resolve within your
  authority, citing the mission file or DESIGN section, or escalate". The
  reply's first line is `VERDICT: resolved <what was sent, and the section
  cited>` or `VERDICT: escalate <reason>`. Events `driver.done` and
  `driver.failed`; follow-up rules match those verdicts; `escalate`, an
  unrecognised verdict, and `driver.failed` stop and notify. `[limits]
  max_consults` per mission (default 2); exceeded → stop. Every
  consultation is an inbox event and a `meta/journal.md` line, and the
  driver's reply is stored verbatim in the job record for the cold review.
- Which events consult is the playbook's choice. The example routes
  `builder.done` with `^VERDICT: question` and an unrecognised builder
  verdict to `consult`; never review outcomes, never held gates, never
  `aux.done`.
- `hands doctor` reports the driver role (cwd, clone, guard mode) and
  refuses a driver role with a permission bypass.

Conventions: this repository's `PLAYBOOK.toml` sets `[series] kickoff` to
the next mission's line; each kit that ships a new mission also ships the
playbook line.

---

## 28. Changes from v3.10 (mission 11 review)

The guard, rewritten around what the shell delivers (review 11 blocker 1):
- The guard no longer inspects a quote-stripped string. It tokenizes the
  command with `shlex` (POSIX mode), splits segments on `;`, `&&`, `||`,
  `|`, a lone `&`, newlines, `$(`, backticks and subshell parentheses, and
  judges each segment's words as the literal tokens `hands`, `git` and the
  rest would receive. A command `shlex` cannot parse (unbalanced quotes)
  is refused.
- For `hands` and `git` in both modes: option values are read from the
  tokens (`--context keep`, `--context=keep`), and a token in argument
  position that still contains `$`, a backtick, `{`, `}`, `\`, `~` (not
  leading), `*`, `?`, `[` or `!` after `shlex` processing is refused,
  because the shell would expand it after the guard saw it. Leading
  assignments (`x=… cmd`) are refused. `$'…'` words are refused.
- Role mode (`HANDS_ROLE=driver`) additionally requires every `hands send`
  to carry exactly one `--context` whose literal value is `keep`, and a
  `--role` naming the role the consultation named (passed to the driver in
  its environment as `HANDS_CONSULT_ROLE`); every other `hands` subcommand
  not in §27's list is refused by name; `git` may only be `-C <clone>` plus
  the read-only allowlist.
- The self-test and `tests/test_bash_guard.py` carry every probe review 11
  executed (`&`-joined commands, quoted and escaped option words, `$'…'`,
  brace words, assignments), each asserted blocked in both modes where
  applicable. The interactive driver's guard is the same file and gets the
  same fix.

Consult and the driver role (should-fix 1–3, 8):
- The stops §27 promises for `escalate`, an unrecognised driver verdict and
  `driver.failed` are enforced by the engine, not by rules the playbook may
  omit; a playbook may add rules on `driver.done` for its own messages, but
  cannot remove those stops.
- `driver.killed`, `driver.orphaned` and `driver.limited` are events; a
  consultation that ends in any of them stops and notifies, and `consult.done`
  carries the terminal state.
- `max_consults` counts from the most recent job whose prompt equals *any*
  `[series] kickoff` value seen in the pipeline's history, or the last
  `plan:` kit apply, whichever is later, so renaming the next kickoff does
  not freeze the count.
- Doctor's driver row proves the wiring: the driver directory's
  `.claude/settings.json` names the hook, the hook file self-tests green in
  role mode, and the role's `permission_flags` is empty; otherwise `fail`.

Kit transport and the apply (blocker 2, should-fix 6, 7, 9):
- Attachment URL validation happens entirely inside the try; scheme must be
  `http(s)`, host non-empty and IDNA-valid, port in range, no whitespace; any
  failure files `kit.refused` with the reason and touches no network.
- `kit check` resolves every file path a `send` prompt names against the
  kit and then the repo, with the same path syntax the daemon uses; a name
  neither has is a failure, whatever punctuation surrounds it.
- The apply-verdict exception applies to exactly one rule: a `builder.done`
  rule whose regex matches the literal `VERDICT: kit applied <sha>`; every
  other rule must match a vocabulary literal.
- `KIT.md`'s first line becomes the commit message only when it is ≤ 72
  characters, contains no quote characters or newlines, and is not empty;
  otherwise the default `plan: kit <name>` is used and the notification says
  so. The apply prompt built by the daemon and by `kit check` shell-quotes
  the message.

Process accounting (blocker 3) and who (blocker 4):
- The post-exit sweep signals a group only when its leader is alive and is
  the job's pid, or when every live member is a descendant by pid chain (or
  a member of the job's cgroup scope); the `HANDS_JOB` mark alone never
  qualifies. H-023 records the departure U1 made.
- `hands who`'s directory fallback excludes the `sessionId` of every hands
  pid's `~/.claude/sessions/<pid>.json` as well as the spool's session ids.

Bookkeeping (blocker 5, should-fix 4, 5):
- H-022 resolved: the acceptance meant a kit of the mission's brief checked
  against the repository passes; `kit check` stays a kit checker.
- Findings' status lines are updated in place; a resolution appends to the
  finding's own section, never to a separate one.
- The `docs/INTEGRATION.md` `done` statement is pinned against each
  `failure_reason` value, not only against the text.

---

## 29. Changes from v3.11 (mission 12 review; two projects on one laptop)

The guard (review 12 blocker 1; H-024):
- A `#` outside quotes anywhere in the command is refused, in both modes.
  A driver has no use for comments, and a comment is where an unbalanced
  quote can hide a second command from a tokenizer. Fail closed: the
  refusal names the position.
- H-024's reading is the text: an expansion character counts only where
  bash would still expand it; never inside single quotes or after a
  backslash; inside double quotes only `$`, a backtick, `\` and `!`;
  brace words only with a comma or `..`; a non-leading `~` only after `=`
  or `:`. Every review 11 and review 12 probe stays blocked.
- Role mode pins `git -C` to the role's clone path (from
  `HANDS_CLONE` in the environment) (review 12 should-fix 2).

The sweep after the reap (review 11 blocker 3, review 12 blocker 3; H-025
option b; H-023): a live process descends from the job when its session id
is the job's pid and its start time precedes the last moment the job's pid
was observed alive, or when it is a member of the job's cgroup scope; the
`HANDS_JOB` mark is corroboration and never sufficient alone. The residual
is a fork inside the job's last poll interval, documented in
`docs/INTEGRATION.md`. Job end reads the pipes with a bounded timeout
(`runner.pipe_timeout_s`, default 10) so an unkilled orphan cannot stall it;
what remains after the sweep is reported as `monitor.orphan_processes` with
`killed: false`.

Kit transport (review 12 blocker 2, should-fix 1, 6, 7): "IDNA-valid" means
`idna.encode(host)` succeeds (the `idna` package is a dependency of httpx and
becomes an explicit one); the kit name is shell-quoted in the apply prompt
like the message; `kit check` judges every file path a prompt names,
including bare relative names and names inside parentheses; the
apply-verdict exception is stated in the code's terms: exactly one
`builder.done` rule may match the literal `VERDICT: kit applied <sha>` and
nothing in the vocabulary, and a test enumerates it.

Consult (should-fix 3, 4, 5): the engine's consult stops apply whether or
not the pipeline is paused (a stop over a paused pipeline is
`pipeline.stop_suppressed` with the consult reason, and notifies); doctor
checks the hook file that the driver directory's `.claude/settings.json`
actually names; `max_consults` also counts from the daemon start when no
kickoff or apply has been seen since.

Bookkeeping (should-fix 8, 9): the `done` statement's order and precedence
are pinned by a table-driven test; `hands who` excludes a job's transcript
for `who.grace_s` (default 60) after the job ends.

Two projects on one laptop:
- The spool is per project: `~/.hands/<project>/` holds `jobs/`, `roles/`,
  the inbox and nonces; `handsd` refuses to start on the old flat layout
  after offering the migration (`hands migrate-spool`, which moves the
  flat contents to `~/.hands/hands/` and records the move in the inbox).
- Templated user units `handsd@<project>.service` and
  `handswho@<project>.service`, each reading `~/.config/hands/<project>.env`;
  the un-templated units are retired.
- `hands who` reads every project's spool and shows each daemon as a root.
- `docs/INTEGRATION.md` describes two daemons, and states the one shared
  resource, the subscription, and how each playbook's `auto_runs` meters it.

Roadmap renumbering: mission 13 is this closer (review 12, the sweep, the
two-project layout); the architect role is mission 14; `reply` and the
self-hosted ntfy are mission 15. The driver role is enabled only after a
review finds no guard hole.

---

## 30. Changes from v3.12 (mission 13 review; the guard's language)

The guard (review 13 blocker 1, and the pattern of reviews 11–13):
- The driver's shell is a line, not a script. The guard refuses, before any
  tokenizing, a command containing a newline or carriage return, `<` or
  `>` in any position, `#`, a backtick, `$(`, `\`, `$'`, or any control
  character; the refusal names the first offending character and position.
  What remains is one line of words and `'…'`/`"…"` quotes, which `shlex`
  tokenizes without ambiguity; segments split on `;`, `&&`, `||`, `|`,
  `&`. Heredocs, comments, escapes, substitutions and redirections do not
  exist in that language, so no quote can be desynchronised by them. The
  driver never needed any of them (`--prompt-file` replaced `--stdin <`;
  `2>&1` is not needed because the guard's commands do not redirect).
- Inside double quotes only `$` and `!` remain to refuse; `$` in a
  double-quoted word is refused in both modes (there is no legitimate
  `$VAR` in a driver command; `HANDS_*` values are given to `hands` by the
  daemon, not typed).
- The two self-test tables and `tests/test_bash_guard.py` keep every probe
  of reviews 11, 12 and 13 blocked and add the reviewer's heredoc shape.
  `docs/INTEGRATION.md` states the language in one paragraph so a reviewer
  can attack the definition rather than the parser.
- Role mode's `git -C` pin compares resolved paths (`realpath`) against the
  resolved `HANDS_CLONE` (should-fix 1).

Review 13 blockers 2–4 and should-fix 2–8:
- `kit check` judges bare relative names and names in any punctuation the
  handbook's prompts use; a fixture enumerates the shapes (blocker 2).
- `hands who` with several configs and none named: each config is loaded in
  its own try; a broken one becomes a root line `<project>: config error
  <reason>` and the others render (blocker 3).
- `[who] grace_s` must be a finite non-negative number; `nan`/`inf` are
  refused at load (blocker 4).
- A process in the job's session without the mark is still the job's
  (session-and-start-time is the proof; the mark corroborates only), and a
  test pins it (should-fix 2). The pipe-timeout test binds job end to the
  configured value (should-fix 3). Doctor's driver row verifies the hook
  command in the settings names the guard file and that the file's
  self-test passes (should-fix 4). `max_consults` persists its anchor in
  the spool so a daemon restart mid-mission keeps the count (should-fix 5).
  Project names match `[A-Za-z0-9][A-Za-z0-9._-]{0,63}` (should-fix 6).
  References to the retired un-templated units are removed everywhere but
  the changelog (should-fix 7). Cancel-versus-limit precedence is pinned:
  `killed` wins over `limited` when both apply in one job (should-fix 8).

Notifications (decision 2026-09-15): when the daemon publishes two
notifications for one cause (a kit receipt and its held apply; a limit and
its resume), it waits 1.1 s between them so ntfy's per-second timestamps
order them. The `job.held → notify` rule is removed from this repository's
playbook and from both templates; the daemon's held notification with
buttons is the one message.

Roadmap: mission 14 is this closer; the architect role is mission 15;
`reply` and self-hosted ntfy are mission 16. The driver role is enabled
after a review finds no guard hole in the one-line language.

---

## 31. Changes from v3.13 (mission 14 review; the architect role)

The guard's command table (review 14 blocker 1): the one-line method
applies to the words as it applied to the syntax. `ALLOWED_FIRST_WORDS` is
replaced by a table of exactly the commands the driver's rules name, each
with the options it may take, in both modes: `cat` (no options), `ls`
(`-l -a -la -1`), `head`/`tail` (`-n <int>`; `-f` only for `hands log`),
`wc` (`-l -c -w`), `grep` (`-n -c -i -l -E -F -e <pat> -r`; never `-f`,
`--include`, `-o`... only the listed), `jq` (`-r -c -e .`; never `-f`,
`--rawfile`, `--slurpfile`, `--argfile`), `pgrep` (`-f -a -l`), `sleep`
(one integer), `date` (no options or `+FORMAT`), `echo` (no options),
`kill -0 <pid>`, `hands` and `git` with their existing tables. Everything
else (`sort`, `uniq`, `cut`, `tr`, `find`, `stat`, `diff`, `printf`,
`basename`, `dirname`, `realpath`, `tty`, `id`, `whoami`, `uptime`,
`which`, `test`, `[`, `seq`, `true`, `false`) leaves the table; a word not
in it is refused by name. No listed option takes a value that names a
program or a file to write. Role mode is the same table minus `hands`
subcommands §27 withholds. The reviewer's three probes and the U1
sub-agent's fuzz corpus are in the tests.

Notifications (blocker 2, should-fix 1, 2): the 1.1 s spacing applies on
every branch that publishes the kit pair, with a test that binds it to the
ordinary branch; daemon start publishes one notification, and re-minted
held jobs are listed inside it rather than each published; the limit pair
is documented as it is implemented.

Should-fix 3–7: doctor judges every `PreToolUse` `Bash` hook in the
settings and fails if any is not the guard; an empty project name is
refused, not ignored; the `max_consults` anchor stores the job id and the
daemon start time it derives from, and a test reads them back; the
bare-name rule's false positives are a pinned fixture row; `hands doctor`
warns when `[series] kickoff` names a brief the repository lacks.

Mission 15, the architect role (§8, §10, §11, §26, §27):
- `[roles.architect]`: cwd `~/hands-architect/<project>/` with a fetch-only
  clone under `repo/` and a `kits/` directory; `CLAUDE.md` is
  `architect/CLAUDE.md` from the kit (the instruction's role variant);
  `permission_flags` empty; env `HANDS_ROLE=architect`,
  `HANDS_CLONE=<cwd>/repo`, `HANDS_KITS=<cwd>/kits`.
- Guard architect mode: the driver's read-only table plus `hands kit check`
  and `hands kit file`; `mkdir`, `cp`, `zip`, `mv` only with every path
  argument under `HANDS_KITS`; Write/Edit/MultiEdit tool calls (a second
  `PreToolUse` matcher) allowed only for paths under `HANDS_KITS`; never
  `hands send`, `approve`, `deny`, `go`, `put`; never a push. The clone's
  push URL is disabled as the driver's is.
- `hands kit file <zip>`: from a path under `HANDS_KITS`, files a held apply
  job exactly as the phone's `kit` does (`origin: architect`, the same
  prompt from the zip's entries and `KIT.md`), after running the kit check
  itself and refusing a failing kit.
- `[series] architect = "phone" | "role"` (default `phone`) and
  `[series] autonomous = true|false` (default `false`). In role mode with
  `autonomous`, held apply jobs of origin `architect` are approved by the
  engine (`decided_by: playbook`), and `[series] kickoff` is sent after
  `VERDICT: kit applied` (a `builder.done` rule the engine adds, not the
  playbook). The human's approval of the playbook is the standing
  approval; a playbook that sets `autonomous` is itself gated as any kit is.
- `consult` with `role = "architect"` on review outcomes (`aux.done`), with
  the event, the review's verdict and blockers/should-fix sections
  verbatim, the roadmap's next milestone, and the instruction "write the
  next kit from ROADMAP and the review, file it, or escalate". Verdict
  vocabulary: `VERDICT: next kit <name>` | `VERDICT: series complete` |
  `VERDICT: escalate <reason>`. Follow-up in the engine: `next kit` waits
  for the apply the architect filed; `series complete` stops with that
  reason; `escalate` stops and notifies with the reason and the architect's
  session id and the `claude --resume` line; `[limits]
  max_architect_consults` per series (default 12).
- Escalation conditions written into `[series]` and enforced by the engine:
  `gate_failures = 2` (the same roadmap gate failing twice in a row, judged
  by the architect and stated in its escalate reason), `escalate_on =
  ["blocker-unanswered", "milestone-missing", "budget-exhausted"]`; the
  architect's CLAUDE.md names them and the engine stops on the budget one
  itself.
- `hands doctor` reports the architect role as it reports the driver role;
  a `[series] architect = "role"` without `[roles.architect]` is a config
  error.
- `architect/` in the repository: `CLAUDE.md`, `settings.json`, `README.md`
  (the switch-point procedure and the deliverables of the handbook §12).

---

## 32. Changes from v3.14 (mission 15 review; the guard's language, finished)

The guard's language, final (review 15 blocker 1; reviews 11–15):
- Besides §30's refusals, the guard refuses `$` anywhere, `{` and `}`
  anywhere, and any of the shell's reserved words appearing as a word
  (`for while until if then else elif fi do done case esac select function
  in time coproc ! [[ ]]`), in every mode. What remains is words, `'…'` and
  `"…"` quotes, and the separators `; && || | &`. There is no expansion,
  no control flow, no redirection and no comment in that language, so a
  segment the guard allows can run only a table command with table options.
- The option tables judge every word, including values, after that rule;
  a value that is not a plain word is refused (`wc --files0-from=`, `grep
  -f`, `date --set`, `tail -f` outside `hands log` are not in the tables
  and are refused by name).
- Role and architect modes are strict subsets of that language; the
  driver-role regression is closed by construction. §30's condition stands:
  the driver role and the architect role are enabled after a review finds
  no hole in this language. `docs/INTEGRATION.md` states the language in
  full in one paragraph and lists the tables.

Architect mode (blocker 2; H-030): `unzip` leaves the table; `zip` leaves
the table; the architect stages a directory `kits/<name>/<repository
paths>` and files it with `hands kit file <dir>`, which builds the zip
itself, checks it, and files the held apply (`origin: architect`). `mkdir`,
`cp`, `mv` remain, every path argument under `HANDS_KITS` and no option that
names another path. The Write/Edit matcher remains the only way to create
file content.

Autonomy (blocker 3, should-fix 1, 2, 3): the engine approves a held job
only when it is an apply hands itself created from a kit filed by the
architect role (a `kit_id` the daemon minted, checked against the spool),
never by origin alone, and only when the current playbook is in role mode
with `autonomous`; a socket client cannot set `origin: architect`. The
engine's kickoff-after-apply rule fires only for an apply of that kind.
`next kit` waits for the specific apply the architect filed (its `kit_id`),
and stops if none is filed within `[series] kit_wait_s` (default 600). The
architect's budget anchors to the playbook's `[series] name`, and a rename
is refused unless `[limits] max_architect_consults` is restated.

Config and doctor (blocker 4, should-fix 6): `[series] architect = "role"`
without `[roles.architect]` is a config error at load, refused by `handsd`
and by `hands kit check` when the kit carries the playbook; doctor's
architect row checks the clone's push URL is disabled, `HANDS_KITS` exists
and is under the cwd, both hook matchers name the guard, and the guard's
self-test passes in architect mode.

Consult prompt and notifications (should-fix 4, 5, 7): the architect's
prompt carries the roadmap's next unmet milestone (the first whose gate
is not marked DONE), not the whole file, plus the file's path; daemon
start publishes exactly one notification and a test binds the count; the
guard's role-mode reads are confined to the clone and the spool's own
paths, and the refusal says so.

H-031: `playbook` is a `decided_by` value (§6). H-032: `Api.send` refuses a
direct send to any role whose start is the engine's (`driver`,
`architect`); they are started by `consult` only.

`monitor.task_killed`: the detector cannot tell a reap from a `TaskStop` or
from the harness backgrounding a long foreground command and reaping it;
the example playbook and this repository's map it to `notify`, and a job
that ends `failed` is what stops.

---

## 33. Changes from v3.15 (mission 16 review; talking to the architect)

The guard held review 16 (no blocker names it). The driver role is enabled
as of 2026-09-17; the architect role stays off until this mission's review.

The autonomy path (review 16 blockers 1, 2; should-fix 1, 5):
- `kit_file` runs `check_kit` on the bytes it stores, against the builder's
  clone, and refuses a failing kit with the check's output; the engine
  approves only an apply whose stored `kit_id` records a passing check;
  a consultation may file at most one kit, and its name must equal the
  name the architect's `VERDICT: next kit <name>` states, else the apply
  is denied by the engine and the consultation ends `escalate`.
- Zip entries are judged by the central directory's names, which are what
  extraction uses; an entry whose local-header name differs from its
  central-directory name is refused, as is any name that resolves into
  `.git/`, `.claude/`, or outside the repository; both the daemon and
  `kit check` share the one judge.
- `kit check` on a kit that carries a role-mode playbook judges the
  playbook's role requirements against the repository's config the way
  `handsd` will at load, and says so.

Architect mode and doctor (should-fix 2, 3, 4): `cp`/`mv` refuse a target
that resolves through a symlink to outside `HANDS_KITS`, and `HANDS_KITS`
itself must not be a symlink; doctor resolves every path it checks and
fails a role row when the settings disable a hook, switch the matcher, or
name a different command; the row prints what it verified.

Consult prompt, notifications, sweep text (should-fix 6, 7, 8): the "next
unmet milestone" is the first roadmap entry whose heading is not marked
DONE, and a test pins it on a fixture roadmap; daemon start publishes one
notification even when a queued job starts within the same second; the
sweep's messages name no cause.

Mission 17, talking to the architect (backlog; ROADMAP M4c):
- `reply <secret> <text>` on `cmd_topic`: delivered as `hands send --role
  architect --context keep` to the architect's last session (refused when
  no session exists or a consultation is running); the reply's text is
  published on `ntfy_topic` with title `architect`; one job per turn,
  `origin: phone`; the text is stored verbatim in the job record.
- The escalation notification carries the architect's last session id and
  the exact `claude --resume <id>` line for the Code tab route.
- Self-hosted ntfy: `docs/INTEGRATION.md` describes running ntfy in a
  container on the laptop with access control (topics require a token),
  reachable through the Tailscale tunnel; `[notify] ntfy_url` and
  `[notify] ntfy_token` (sent as a bearer on publish and subscribe); the
  phone app subscribes with the same token. Free text about a project
  never crosses a public broker once this is set.

---

## 34. Changes from v3.16 (mission 17 review)

The start fold (review 17 blocker 1, should-fix 6): the daemon's start fold
holds back everything the jobs it re-admits publish, except a `job.held`
(H-039; worded so in §43). A `job.held` is never folded: it is published at
once, with its buttons, whether the job was held before or during the
start; the start notification lists it by title only. A `stop` inside the
fold window flushes the fold first and cancels nothing that was already
queued to publish; `cancel_all` is removed from that path. Tests bind both
with the reviewer's timings.

The kit record (should-fix 1, 2): `kit.json` stores the sha256 of the bytes
the check passed on, and engine approval re-hashes the stored zip and
refuses a mismatch (`kit.refused` with both hashes); `kit_file` calls are
serialized per consultation under a lock, the second refused as "one kit
per consultation" before it is checked, and the report's "both denied"
claim is replaced by what the test proves.

Kits and symlinks (should-fix 3): the symlink walk under `HANDS_KITS` uses
`os.lstat` on every path component from the root down and does not depend
on directory read permission; a component that cannot be stat'ed is
refused; doctor's `_kits_line` uses the same walk.

Doctor's role rows (should-fix 4, 5): doctor reads every settings layer
Claude Code reads for the role's directory (`settings.json`,
`settings.local.json`, and the user-level file), fails the row when any
layer disables hooks, alters the `PreToolUse` matcher, sets an `env` that
changes `HANDS_*` or `CLAUDE_*` variables the role depends on, or names a
different hook command; the self-test check runs the guard at the exact
path the settings name and compares its sha256 with the guard the
repository ships, printing both on mismatch.

The token (should-fix 7): `ntfy_token` with `ntfy_url` unset or pointing
at a public broker is refused at config load with a message naming the
url; the token is only accepted alongside an explicit `ntfy_url`.

`hands who` (backlog, mission 18 item 1): the driver's inbox line says
"needs YOU" only when the pipeline is stopped now or a job is held now;
unread events alone say "informational, the driver acks them on its next
check".

The architect role is enabled after this mission's review.

## 35. Changes from v3.17 (the pull-request flow; a hosted second reviewer)

Decided 2026-10-12 with the human, written 2026-10-14. Until now every
project hands drives, this repository included, commits straight to `main`:
one commit per unit, pushed at once (CLAUDE.md). The roadmap's "PR per run,
auto-merge on a clean review" was a sentence for the spanweave integration
and nothing implemented it. The human has an automated review on every pull
request of his repositories (Qodo, `qodo-code-review[bot]`, which posts a
summary, a review and inline comments on its own within minutes of a PR
opening; verified 2026-10-14 on spanweave-zoo #2: 111 seconds). A pull
request per mission makes that a second cold reviewer, from a different
model, that the aux review reads and either confirms or dismisses with a
reason. This section is the shape. It changes templates, the review
protocol, this repository's own playbook and `hands doctor`; the engine
does not change.

**Why not in the engine.** The branch logic belongs to the brief and the
review protocol, which are the project's files, because what a mission
branches from and what a review merges are plan facts that differ per
project and per mission (a closer mission continues an open branch). The
engine keeps reading one `VERDICT:` line and firing one rule; nothing in
`playbook.py` learns the word "branch". The one new mechanical piece is
doctor's `gh` row.

**The builder (brief template, this repository's CLAUDE.md).** A mission
runs on a branch `mission-N`, created from `main` at U0 (or, for a closer
mission, continuing the open branch the brief names, with `main` merged in
first so the kit's plan files are present). Every unit commit goes to that
branch and is pushed at once, as before. The last unit opens the pull
request — `gh pr create --base main --head mission-N --title "mission N:
<title>" --body-file meta/FINAL-REPORT-N.md` — and the final reply's
verdict carries its number: `VERDICT: mission N finished pr=<number>`. The
builder then returns the working tree to `main` (`git checkout main && git
pull --ff-only`), because the next kit apply and the next kickoff run in
that tree on `main`. The playbook's regex `^VERDICT: mission (?P<n>\d+)
finished` matches the longer line by prefix; `kit check`'s vocabulary check
accepts the `pr=<number>` placeholder as it accepts `<unit>`. A mission
whose brief says "direct" (this repository's mission 19, the one that
builds the flow) commits to `main` as before and replies without `pr=`.

**The review (review-protocol template, this repository's protocol).** The
protocol finds the mission's pull request itself: `gh pr list --head
mission-N --state open --json number,baseRefName,headRefOid`. With a PR,
the commits under review are the PR's own since the last reviewed tip
(`git log <base>..origin/mission-N`, where base is the merge-base with
`main` for a first review of the branch, or the `reviewed:` sha the
previous REVIEW file recorded for a closer); without one, the base is the
last `review:` commit on `main` as before, so the protocol is one text
for both shapes. The reviewer reads the hosted review before writing:
`gh api repos/<owner>/<repo>/issues/<pr>/comments`, `pulls/<pr>/comments`
and `pulls/<pr>/reviews`; when none from the bot is there yet it waits, in
the foreground, up to ten minutes in one-minute steps. `REVIEW-N.md` gains
a `## Hosted review` section listing every bot finding verbatim with one
of: confirmed → carried as blocker k or should-fix m; dismissed → the
reason; and `reviewed: <sha>` on its first line after the title. The
review file is committed to `main` as `review: mission N` and pushed,
before any merge, so the architect's clone and the phone architect read it
from `main` whatever happens to the branch. Then: with `blockers=0`, the
reviewer merges the PR itself — `gh pr merge <number> --merge --subject
"merge: mission N (PR #<number>)"` — and brings the local tree level
(`git checkout main && git pull --ff-only`), so the next kickoff starts
from a `main` that has the code; a merge commit, never a squash, because
the per-unit commits are what the next cold review's sub-agents work on.
With blockers, the PR stays open and the reply says so; the closer
mission's brief names the branch to continue and its review merges when
clean. The merge is inside the review job on purpose: a human merging
later from the GitHub app would let the next kickoff start from a `main`
without the mission's code. The verdict line is unchanged:
`VERDICT: review mission N blockers=<k> should-fix=<m>`.

**Standing approval.** The human's approval of a playbook whose review
protocol merges on a clean review is the standing approval of every merge
it makes, as the approval of an autonomous playbook is of every kit apply
(§31). A project that wants a human on every merge leaves the merge step
out of its protocol and merges from the phone's GitHub app; the next
kickoff then waits for `go`.

**`hands doctor` (code).** A `gh` row: `gh --version`, `gh auth status`
for the user handsd runs as, the login, and whether the token's scopes
include `repo`; absent or unauthenticated is a warning, not a failure,
since a project may commit direct; the row names the remedy (`gh auth
login`). Tests use a fake `gh` on PATH as they use the fake claude.

**This repository.** Mission 19 builds the above on `main` directly and
is reviewed under the direct shape (the protocol's "no PR" branch; the
review rule fires with the prompt loaded when the mission started, which
is the old one, and the protocol on disk handles both). Its U0 is the
gate: a probe PR from branch `probe-qodo`, one line in a doc, must draw
the bot's review within fifteen minutes; the trigger mode and the delay
are recorded in `meta/plan.md`; no review within the window is `VERDICT:
mission 19 blocked U0`, and nothing of the flow is built on a reviewer
that is not there. From mission 20 on, every mission of this repository
is a pull request; mission 20 is the first, and its review the first to
read a hosted review.

**Not changed.** The kickoff line, the kit apply, the engine's rules, the
driver and architect roles, the guard. The architect role's clone reads
`main`; a mission's branch is invisible to it until merged, which is
correct: the role plans from reviewed, merged state.

## 36. Changes from v3.18 (the first role-mode series; mission 19 review)

The first series run in role mode by another project (2026-10-12 to
2026-10-14; the evidence is that project's findings HF-001..HF-008 and its
reviews, cited by id only) found, in the order it hit them, that the
architect role could not write, that its clone never advanced, that no role
job carried `HANDS_PROJECT`, that the kickoff after an autonomous apply came
from the playbook loaded before the apply, that the hold for a kit the role
filed was announced with buttons before the engine approved it, that a
builder's question could be answered only from the laptop, that the
harness backgrounds a long foreground gate, and that the role may not copy
a file from its clone into a kit. Each was worked around on the laptop by
hand; this section is the fix for each, with the mission 19 review's five
should-fix items and the mission 18 review's four. Mission 20 builds it.

**Hermetic tests (H-040).** Every builder hands dispatches inherits
`HANDS_PROJECT` and `HANDS_JOB`, and twelve `kit file` tests resolved the
project from them. `tests/conftest.py` clears every `HANDS_*` variable for
every test (an autouse fixture), so the gate is the same inside a job and
outside one. Until that unit lands, mission 20's gate runs as `env -u
HANDS_PROJECT -u HANDS_JOB ./scripts/check`.

**The review protocol (mission 19 should-fix 1, 2; HF-007; HF-008).** The
protocol takes the direct shape only when the brief's Branch section says
"Direct"; a brief that names a branch and has no open pull request is a
blocker ("no pull request for mission-N") and the review goes no further.
The branch is named once, as `<branch>`, and the commits under review
exclude `main`'s own history: `git log <base>..origin/<branch>
^origin/main`. A unit commit that changes only tests is reviewed by making,
in the worktree and without committing, each wrong change the commit body
names and expecting red; the body of a tests-only commit must name them.
Per-commit sub-agents run one at a time, never concurrently, and each runs
`./scripts/check` once at its commit; the reviewer's own run count is one,
at the tip. The templates and this repository's protocol change together.

**Doctor's `gh` row (mission 19 should-fix 3, 4).** `gh auth status
--active --hostname github.com`; every WARN of the row, including a
`gh --version` that does not answer, names the remedy. docs/PLAYBOOK.md's
garbled sentence (should-fix 5) is reworded.

**The architect role's write permission (H-041).** `architect/settings.json`
allows exactly `Edit(kits/**)`, `Write(kits/**)` and `MultiEdit(kits/**)`;
headless `claude -p` without a bypass denies any tool not allowed, and the
`--write` hook only ever denies, so without these the role could not write
a byte. Doctor's architect row fails when any of the three is missing or
when an allow for a write tool names anything but `kits/**`; `doctor --live`
for the architect writes one file under `kits/`, runs `hands kit check` on a
one-file kit against the clone, runs `hands show` on a job of its spool,
and removes the file; a live turn that cannot do all four fails the row.

**The runner (H-042, H-043).** Before every architect and driver job the
runner advances the role's clone: `git -C <clone> fetch -q origin` then
`git -C <clone> checkout -q --detach origin/<branch>`, where `<branch>` is
the config's `[roles.<role>] branch` (default `main`); a clone that cannot
be advanced fails the job before `claude` starts, with the git message in
the record. Every role job's environment carries `HANDS_PROJECT`, set from
the config's project name and never from handsd's environment; doctor's
role rows print the clone's HEAD against origin and the project the job
will see. The guard's project resolution is unchanged and now always has a
value.

**The engine (H-044, the stale kickoff; H-045, the hold).** Before deciding
the `builder.done` of an apply it approved itself, the engine reloads the
playbook from the committed file, so the kickoff it sends is the one the
kit just committed; a playbook that no longer loads after the apply stops
the pipeline with the loader's reason. The regression test is the shape
the series found: a scripted apply that rewrites and commits the playbook's
kickoff before replying `VERDICT: kit applied`, after which the kickoff job's
prompt must be the committed line. Under `autonomous`, the engine decides a
hold for a kit the role filed before anything is published: the human sees
one buttonless notification, "kit <name> filed by the architect; apply
approved by the playbook", never Approve/Deny buttons for a decision already
taken; a hold the engine does not approve (the kit's name is not the one
the verdict named, the hash mismatches) is published with buttons as
before.

**`answer <secret> <text>` (the phone answers the builder).** The ninth
command on `cmd_topic`. It is delivered as `hands send --role builder
--context keep "<text>"` would be, to the builder's last session, one job
of origin `phone`, and it un-pauses a stopped pipeline when the job starts,
as a cli send does, because answering the question is answering the stop.
The secret is the approval: an `answer` is not held by the §8 gate whatever
its text says. It is refused, and the refusal published under `hands:
answer`, when the builder has no resumable session, has a job running,
queued or held, or the text is empty. A file attached to the message is
fetched into `kit_dir` as a kit is, judged by the same size and name rules,
and the delivered text ends with one sentence naming its path; the record
keeps the sha256. The text and the attachment's name and hash are filed as
an inbox event `answer.sent`. The builder's final reply is published on
`ntfy_topic` titled `builder`, and its `VERDICT:` line fires the playbook's
rules as any builder end does. The stop the driver's escalation produces
keeps the builder's question verbatim in its message, so the question and
the answer are on one screen. Every `answer`, every cli `--context keep`
send to the builder, and every `meta/decisions/*-owner.md` file committed
since the architect's last consultation are listed verbatim in its next
consult prompt under "Decided by the human since your last consultation",
beside the review's verdict and sections: the role is told, not left to
notice a ledger line.

**The job environment (HF-006).** Builder and aux jobs carry
`BASH_DEFAULT_TIMEOUT_MS` and `BASH_MAX_TIMEOUT_MS`, both `900000`, unless
the role's `[roles.<role>.env]` sets them, as `CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS`
is set; doctor prints the effective values on each row. The harness moves a
foreground command past its default limit to the background, where the
no-background hook cannot see it; a three-minute gate was moved so.

**The guard (HF-003).** Architect mode allows `cp` (and `cp -r`) with
every source under `HANDS_CLONE` and every target under `HANDS_KITS`, judged
by realpath as the kits-only `cp` is, refused while anything under
`HANDS_KITS` is a symlink and when a source is one; nothing else in the
table changes. The role can now re-issue a file by copying it and editing
the copy instead of regenerating it.

**Review 18's four should-fix items.** A Unicode full stop or any
non-ASCII character in `ntfy_url` is refused at config load (the
public-broker check compares the host after NFKC normalisation and ASCII
folding, and refuses what does not fold). Doctor's guard self-test runs
with `-I` (isolated mode) and an empty `PYTHONPATH`, so a module planted
beside the guard is not imported. The kit record stores the sha256 of the
bytes `check_kit` read, not the client's; the two are compared and a
mismatch refuses the filing. A hardlink under `kits/` (link count above one
on a regular file) refuses `cp` and `mv` as a symlink does, and doctor's
kits walk reports it.

**Notifications name the project.** Every title handsd publishes begins
with `<project>: `; `handswho` keeps its root line. The documented setup
lines generate topic names that carry the project (`hands-<project>-…`,
`hands-<project>-cmd-…`, `who-<project>-…`, `whocmd-<project>-…`), and doctor
warns, never fails, on a configured topic whose name lacks it.

**This repository's kickoff.** `[series] kickoff` becomes "Read the builder
prompt with the highest mission number in the meta directory and execute
the mission below its divider.", so no later kit re-issues the playbook to
move a number; every brief from mission 21 on carries that line as its
kickoff.

**Mission 21 (specified next).** The onboarding half of the same findings:
the role reads the handbook and templates from the installed hands rather
than the project's clone (HF-002); `hands project add`; the Purpose block in
both instruction templates; the owner-decisions file as a template with the
review protocol's one-commit exception; the brief template's recovery rule
for a `keep` answer; the handbook's onboarding shape, the ruling round, the
separation rule (another project appears in hands' files only as evidence),
re-firing a consultation; HF-004, HF-005 and the first plan kit's silent
apply in the docs.

## 37. Changes from v3.19 (mission 20 review; the closer; the notification move)

Mission 20 was the first mission run through a pull request (PR #2), and
the flow held: the cold review found the pull request itself, read the
hosted review's nine findings as claims, confirmed four of them (one as the
blocker, which its own sub-agent had reproduced separately), dismissed
five with reasons, and left the PR open on `blockers=1 should-fix=6`
(REVIEW-20, `reviewed: 62f5618`). Mission 21 is the closer: it continues
the branch `mission-20` and its review merges when clean. The onboarding
half that §36 named "mission 21" moves to mission 22, together with what
the laptop found on 2026-10-14 while mission 20 ran (below). Roadmap
renumbering: mission 21 is this closer; mission 22 is the onboarding half
and the operational findings; M5–M8 are unchanged.

**The cancel race (review 20 blocker 1).** `Spool.transition` judges every
edge against the record on disk, never against the caller's object: it
reloads the job by id before testing the edge, and a caller whose record is
stale gets `IllegalTransition` from the on-disk state. That closes the
window everywhere §6 allowed it in milliseconds and §36's advance widened
to a network fetch. The runner, in addition, reloads the record after
`advance_clone` returns and, when the job is no longer `queued`, leaves it
as it is and spawns nothing: a `hands cancel` during the advance ends in
`killed`, the consultation the engine closed stays closed, and no `claude`
starts. The regression test cancels during a slow fake advance and expects
`killed`, no spawn, and the inbox event the cancel filed and nothing after
it.

**The live hook (review 20 should-fix 1; REVIEW-18 should-fix 2, again).**
The hook command in `driver/settings.json` and `architect/settings.json` is
`python3 -I "$CLAUDE_PROJECT_DIR"/.claude/hooks/bash_guard.py` (and `--write`),
so the guard Claude Code runs ignores the user site and `PYTHONPATH` as
doctor's self-test does; doctor's guard row additionally FAILS when any
`.py` file or any package directory other than the guard itself sits beside
it, naming the file, and the row's self-test runs the hook command as the
settings file spells it, not a command of its own. A planted `shlex.py`
beside the guard is then both inert and reported.

**Writes through a hardlink (review 20 should-fix 2).** The `--write` hook
refuses a target that exists with a link count above one, and refuses every
write while the kits walk (`kits_symlink(kits, hardlinks=True)`) reports
anything, as `cp` and `mv` are refused; the refusal names the link. Doctor's
kits walk is unchanged.

**Provenance of an `answer` (review 20 should-fix 3).** `Api.send` refuses
`origin: phone` from a socket client as it refuses `origin: architect`
(§32): only the daemon's own `answer` path sets it. A raw socket send
cannot be published as the builder's answer or listed to the architect as
a human decision.

**`doctor --live` for the architect (review 20 should-fix 4, 5).** The
live turn names the clone `driver_clone` resolves for the role (the cwd
itself when that is the clone) as `--repo`, and the row FAILS before the
turn when the role has no clone. The judged `hands kit check` must name the
live kit's own path and that `--repo`; a check of any other kit does not
pass the step. The live kit's name is unique per run,
`kits/hands-doctor-live-<8 hex>`; the row refuses to run, and FAILS, when
that path already exists, and it removes only the directory it created.

**The protocol's revert step (review 20 should-fix 6).** Both protocol
files say what every sub-agent of review 20 did: in the worktree at the
commit, `git checkout <sha>~1 -- <the non-test files the body lists>`,
run the new tests and expect red, then `git checkout <sha> -- <the same
files>`; "stash" leaves the text.

**An apply that leaves no playbook (review 20 note on U5).** After an apply
the engine approved itself, a playbook file that is absent from the
committed tree stops the pipeline with the reason "the apply removed
PLAYBOOK.toml", as one that no longer loads stops with the loader's reason;
§36's sentence covers both.

**What the laptop found while mission 20 ran (mission 22).** Recorded here
so the numbering is on disk; the entries are filed by mission 21's U0 and
built by mission 22. H-046: both `handswho` units published every ~20 s
because the who text's relative-time line counts as a change, and ~350
publishes an hour from one address spent the public broker's free daily
cap (429) for the daemons' own stops and holds too; `handswho` publishes on
a real state change only, compared without the relative-time text, with a
floor on the interval, and doctor WARNS on a public `ntfy_url` that the cap
exists and names the self-hosted path. H-047: a `handsd` restart kills the
running builder job and nothing resumes it (the `task_killed` rule only
notifies), so every install cost a `go` from the phone; the daemon
re-queues the kickoff for a builder job its own stop killed, bounded as
`resume` is. H-048: under `autonomous`, a builder's `blocked` verdict stops
for the human, who can only re-fire the role through the aux by hand; the
playbook may consult the architect on `builder.done` with a `blocked`
verdict, the consult prompt carrying the builder's reply in place of a
review, counted against the same budget. The self-hosted ntfy of §33 was
set up on 2026-10-14 from docs/INTEGRATION.md and the doc was wrong in the
image name (`binwiederhier/ntfy`), silent on a tailnet without a
certificate domain (bind the container to the tailnet address, plain http
over Tailscale), on `base-url` before the first start, on configs written
before `[notify]` existed (an `ntfy_topic` left under `[server]` refuses to
load), and on the access rule (`hands-*` must cover the who topics too);
mission 22 corrects it and makes the self-hosted server the documented
default for role mode. A phone `progress <secret>` (job id and age, the
working tree's branch, the last three commit subjects, the checkpoint's
unit line) replaces the aux's read-only line, because `status` says only
running or idle and `pipeline`'s `auto-runs` counts playbook-started runs
only. The §36 list for the onboarding half is unchanged and is mission
22's with these.

## 38. Changes from v3.20 (mission 21 review; the operational findings; the onboarding half)

Mission 21 closed review 20 and was merged by its own review (PR #2,
REVIEW-21 `reviewed: 2b5a7fc`, `blockers=0 should-fix=3`): the M4d gate is
met. The same two days produced the operational findings §37 recorded
(H-046, H-047, H-048, filed open by mission 21's U0), one finding that was
on file since mission 17 and became live the moment the notifications moved
to an authenticated server (H-037), review 21's three should-fix items, and
the onboarding half that §36 specified and §37 deferred. Mission 22 builds
all of it; it is the last mission of M4d. Roadmap: mission 22 as below;
M5–M8 unchanged.

**The buttons carry the token (H-037; review 21 of the move).** On the
self-hosted server every Approve and Deny button fails with 403, because
the `http` action the hold notification carries has no `headers` and the
server denies anonymous publishing. When `[notify] ntfy_token` is set, every
action hands publishes carries `headers.Authorization=Bearer <token>` in
ntfy's short action form, beside `method=POST` and `body=…`; without a token
the actions are as before. The token is already the subscriber's own (the
phone reads the events topic with it), so nothing new is exposed by carrying
it in an action the same subscriber receives. Doctor's `phone` row says
whether the buttons are authenticated ("buttons: bearer on" | "buttons: no
token; a token-protected server refuses them"). The test reads the published
`Actions` header and finds the bearer on both actions.

**`handswho` publishes on change only (H-046).** Both who daemons published
every ~20 s because the picture's relative-time text ("N minutes since the
last write") changed on every scan, and ~350 publishes an hour from one
address spent the public broker's free daily cap for the daemons' own stops
and holds too. The watcher compares the picture with every relative-time
rendering blanked, publishes only when that comparison differs, and never
publishes twice within `[notify] who_min_interval_s` (default 60) unless a command
on `who_cmd_topic` requested it; the picture the phone receives still shows
the times. Doctor WARNS on a public `ntfy_url` (the default broker, or any
host that is not on a private address or the tailnet) with the cap and the
self-hosted path named; it does not fail.

**A daemon stop does not strand the builder (H-047).** A `handsd` stop ends
its running jobs; today their records become `killed`, which is terminal
and which no rule resumes, so every restart cost a `go` from the phone. Now
a job the daemon's own stop ends is recorded `orphaned` with `reason:
daemon_stop` (the process is still signalled as §2 requires), `killed` stays
the record of a cancel, and at the next start every job reconciled or
recorded as orphaned is fed to the engine as `<role>.orphaned` once the
workers are up, so the playbook's `builder.orphaned → resume` rule re-sends
the kickoff from a fresh context, bounded by `max_resumes` as every resume
is, and an orphaned consultation stops as §28 and §31 say. The start
notification names what was resumed. A daemon that was stopped with the
builder idle resumes nothing.

**A blocked mission consults the role (H-048).** Under `[series] architect
= "role"` a builder's `VERDICT: mission N blocked <unit>` stopped for the
human, who could reach the role only by having the aux role recite a
review-shaped text. The architect may now be consulted on `builder.done` as
well as on `aux.done` (`CONSULT_EVENTS`), and the consult prompt written for
a builder's end says so: in place of the review's sections it carries the
builder's verdict line and its full reply between the markers, headed "The
builder's blocked verdict and its reply", with the roadmap milestone, the
conditions and the instruction as before; the role's verdict vocabulary is
unchanged, the consultation counts against the same budget, and `kit check`
accepts a consult rule on a `builder.done` blocked verdict for the architect.
`templates/PLAYBOOK-missions.toml` carries that rule in its role-mode
variant with a comment, and the phone-mode variant keeps the stop; this
repository's playbook, phone mode, keeps its stop.

**`progress <secret>` (the tenth command).** `status` says running or idle;
progress lives in the repository. `progress` publishes, titled `progress`:
the builder's current job id and age (or the last ended job and its
verdict), the working tree's branch and tip (`git -C <builder cwd> rev-parse
--abbrev-ref HEAD` and `log --oneline -3`), and the first line of
`meta/CHECKPOINT.md` that names a unit in progress (or "no checkpoint").
Read-only; it starts no job. The handbook says what
`pipeline`'s `auto-runs` counts and that `jobs` lists newest first.

**The protocol's revert step for a file the commit adds (review 21
should-fix 2; H-049).** `git checkout <sha>~1 -- <files>` fails for a file
that does not exist at the parent and then reverts none of the listed files,
so a sub-agent that misses the error tests unreverted code. The step now
reads: for each non-test file the body lists, `git checkout <sha>~1 --
<file>` when the file exists at `<sha>~1`, else `rm` it; then run the
commit's new tests and expect red; then `git checkout <sha> -- <files>`. The
template and this repository's protocol change together, and the sentence
of §37 that prescribed the old wording is superseded here.

**The reviewer's schedule is written down (H-050).** REVIEW-21 ran its five
per-commit sub-agents concurrently although the protocol says one at a time
(HF-008). The protocol's Notes section now requires one line per sub-agent
with its start and end time, and says the rule's reason (one `./scripts/check`
at a time inside the 20-minute cap); a review whose Notes lack the schedule
is itself a should-fix for the next review. The merge step is unchanged.

**Two small corrections from review 20's notes on U6.** "Since the last
consultation" is computed from the sha the last consultation recorded
(`git log <sha>..HEAD`), not from `git log --since`; and the decisions-path
comparison is made on repository-root-relative paths taken from `git
ls-files --full-name`, so a builder cwd below the repository root sees its
owner files.

**The owner-decisions round, as a template (§36's deferred half).**
`templates/DECISIONS-owner.md`: `O-n` numbering continued from the last
owner file on the branch, a precedence header (this file wins over DESIGN
and earlier decisions), a "Findings closed:" line, and a last section "For
the builder" with the exact steps, which is the only section the builder is
told to read; the review-protocol template's one-commit exception for `plan:
decisions <date> (owner)` (the commit is read for what it says it does and
is not reviewed as a unit); the brief template's recovery rule: a `keep`
send after `VERDICT: question` is the answer, carried out, the mission
continued from the checkpoint, a `VERDICT:` line always, even when a file
had to be committed first; both instruction templates carry the paragraph
that tells a project's architect to answer rulings with this file.

**Human-supplied content (§37's evidence, the handbook).** Attack-shaped
test content — hostile corpora for a sandbox, exploit-shaped fixtures and
the like — is authored by no agent in the chain: a builder's sub-agents, a
project's architect chat and the hands architect chat were each stopped on
it by a safety classifier (discotrade mission 13 U4 and its ruling O-21,
2026-10-15). The brief template gains a "human-supplied unit" shape: the
unit names the files, their paths and the commit message, the human places
them under `~/Downloads/<name>/`, the builder copies and commits them by
path without opening them, and the review protocol checks such a commit by
`git show --stat` alone. The handbook's rule: a design that needs such a
suite names the human-supplied unit up front, or is reshaped so that no
agent has to author the content.

**Onboarding (HF-002, HF-004, HF-005; `hands project add`).** The installed
hands ships `docs/ARCHITECT-HANDBOOK.md` and `templates/` as package data;
`hands handbook` prints the path of the installed handbook and `hands
handbook --templates` the templates directory, and the runner exports
`HANDS_DOCS=<that directory>` to every role job, so the architect role reads
the handbook and the templates of the hands that runs it, never a pinned
copy in its clone (HF-002); `architect/CLAUDE.md` and
`docs/ARCHITECT-INSTRUCTION.md` say so. The handbook's §6 lists every
`[series]` key with its default and meaning (HF-004, verified against
`playbook.py`), and §12 names the laptop check of a role-mode plan kit —
`hands kit check <kit> --repo <clone>` before the apply (HF-005) — and the
first plan kit's silent apply (the engine's own `builder.done` rule
approves it; the first thing the phone sees is the kickoff). `hands project
add <name> --repo <url>` does what docs/INTEGRATION.md's setup section does
by hand: writes `~/.hands/<name>.toml` from the installed config template
with four generated topics carrying the project name and a command secret
in `~/.hands/<name>.cmd_secret` (mode 600), creates `~/hands-driver/<name>/`
and `~/hands-architect/<name>/` with the shipped settings and guard and a
fetch-only clone of `<url>` whose push URL is `no_push`, writes the
architect's `CLAUDE.md` from `docs/ARCHITECT-INSTRUCTION.md` with the
Parameters filled, enables `handsd@<name>` (and leaves `handswho@<name>`
for the human to enable), runs doctor, and ends by printing the filled
Project instruction for pasting with its verification question ("What are
your Parameters?"). It refuses an existing project or a non-empty
directory, and `--dry-run` prints what it would write. The Purpose block
is a standard slot in both instruction templates: three lines the human
fills (what the project is for, what it is not, who decides), kept
verbatim at the top of the instruction.

**The handbook's new sections.** The onboarding shape (the human's Project
chat writes the plan kit; from the switch point the role writes every kit;
the hands architect audits kits only for hands-shaped content); the ruling
round end to end (the stop, the owner file, the send, the §8 hold answered
by typing, the resume); the separation rule (another project appears in
hands' files only as evidence — name, commit, date, review number, finding
id — never its content); re-firing a consultation after a stop (the aux
role recites a review-shaped reply; a direct send to the architect is
refused by design); `hands send` takes the prompt as a plain argument;
`status` hides the architect row, `jobs` lists newest first. docs/
INTEGRATION.md is corrected from the 2026-10-14 setup: the image is
`binwiederhier/ntfy`; a tailnet without a certificate domain binds the
container to the tailnet address and uses plain http over Tailscale;
`base-url` is set before the first start; a config written before
`[notify]` existed carries `ntfy_topic` under `[server]` and refuses to load
until it is moved; the access rule `hands-*` must cover the who topics; the
phone app's WebSockets option is fine with no proxy in front; the hook is
spelled `python3 -I <guard>` everywhere (review 21 should-fix 3); the
self-hosted server is the documented default for role mode, with what is
proven (publish, subscribe, typed commands, attachments, buttons after this
mission) stated as such. Review 21 should-fix 1 is a sentence in
FINAL-REPORT-21; mission 22's report says which test is red without the
spool half (the unit test in `test_spool`) and claims nothing wider.

## 39. Changes from v3.21 (mission 22 review; the roadmap reordered; the hosted review read mechanically)

Mission 22 closed M4d: its review merged PR #3 itself (REVIEW-22 `reviewed:
baa0b6e`, `blockers=0 should-fix=12`), the buttons carry the token, a daemon
stop no longer strands the builder, a blocked mission consults the role,
`hands project add` exists, and the handbook ships inside the install. The
day it was installed produced the rest of this section: twelve should-fix
items, four findings the builder left open (H-051..H-054), a review lost to
a daemon restart, two phone-command failures that cost an hour each, and a
method for reading the hosted review that the human brought from another
repository. Mission 23 builds it all, and the roadmap below it changes
order.

**Roadmap (decided 2026-10-15).** M8, other coding agents as backends, moves
ahead of M6 and M7: an integration should meet a backend that was shaken
down on a series whose failures cost nothing, and a different model as the
cold reviewer removes the shared-blind-spot problem before spanweave. Mission
24 is M8a: a laptop probe as a gate (the first unit, run by the orchestrator
with read-and-wait commands: a headless one-shot run of the second backend,
its event stream parsed, a session resumed, its sandbox and approval
behaviour recorded, its transcript read the way the monitor reads Claude
Code's), then the design of the backend seam from what the probe found —
`[roles.<role>] backend = "claude" | "codex"`, the runner and the monitor
behind it, a guard story per backend (Codex has sandbox modes and approval
policies, not tool hooks; the driver and architect roles stay on Claude
until a review finds no hole in the Codex guard, as role mode was gated),
doctor rows per backend, a per-role `model` setting, the VERDICT contract
unchanged; and an optional "polish round" a playbook may switch on: on
`aux.done` with `blockers=0` and should-fix items, one bounded builder job
on the same branch fixes what the review marked fixable, a re-review of the
delta follows, then the merge — off by default, the reviewer never writing
code. A probe that fails on resume or transcripts makes the design say so
and evaluate ACP instead. Mission 25 (and a closer if needed) is M8b, the
seam and both implementations. M5b is discotrade's second series on the
Codex backend — no new pet project: the run/review loop on a repository with
history is the harder shakedown, and `project add` and a first plan kit are
backend-agnostic and proven — started at a series switch point (a new
playbook with `backend` per role, approved by the human; never a mid-series
swap), builder on Codex and reviewer on Claude first, the architect role on
Claude. Then M6, M7, with the backend chosen per role per project.

**Rulings on H-051..H-054.** H-051: the architect's consult prompt names the
installed handbook's and templates' absolute paths (handsd knows them: the
same values it exports as `HANDS_DOCS`), the guard's read roots gain
`HANDS_DOCS` so `cat` works there, the architect's `hands` subcommands gain
`handbook`, and `architect/CLAUDE.md` tells the role to Read the paths the
prompt names; `hands handbook`'s help text names the directory as it is
(`$HANDS_DOCS/docs/…`); HF-002 is then resolved in full. H-052: the reading
mission 22's U10 took is the design — the role directory's `CLAUDE.md` is
`architect/CLAUDE.md` with the Parameters filled, and the phone instruction
is what the command prints for pasting. H-053: §38's sentence was wrong;
`status` prints one line per configured role, the architect's included, and
the handbook says so (the observation behind it was a `head -6` cutting the
list). H-054: §38's sentence was wrong; the loader reads `[server]` as the
fallback for a config written before `[notify]` and refuses only a key set
in both tables, and docs/INTEGRATION.md says that and tells the migration to
move the key.

**Review 22's should-fix items.** The who watcher pins its blanked-picture
comparison with a test whose fingerprint changes while the blanked picture
does not and the reverse, and stores the fingerprint whenever the blanked
picture equals the last published one, so a human session alone never
publishes (§24). A `reply` or `answer` a daemon stop orphans is published to
the phone as its end, and a builder `answer` is re-sent as a `keep`, never
as a clear. The start notification names a daemon stop only for jobs whose
`orphan_reason` says so; a crash orphan is named as found. The load-time
check of an architect consult rule on `builder.done` judges the compiled
regex against sample verdict lines (`VERDICT: mission 1 blocked U2` must
match, `VERDICT: mission 1 finished` must not) and the design records the
refusal here. `progress` reads `meta/CHECKPOINT.md` at the repository root
(`git rev-parse --show-toplevel` of the builder's cwd) and README lists all
ten phone commands. The two owner-file fallbacks are inclusive again: a file
committed since the consultation but no longer tracked is listed with a
note, and an unknown recorded sha lists every owner file with a note rather
than none. The protocol's revert step handles a file the commit deletes:
`git rm -q` a listed file absent at `<sha>` before the restore, and `git
status --short` must be empty after it (H-055). `architect/CLAUDE.md` rule
13 and rule 8 agree: a ruling the role cannot make is an escalation with the
reason `ruling: <what>` and a drafted owner file under
`kits/<name>/meta/decisions/`, which the human adopts or rewrites. `hands
project add` clones with `git clone -- <url>`, and a failed clone removes
everything the command created (config, secret, unit, both role directories,
`kits/`, the enabled unit) and says so, so a re-run is possible. The
`no_background.py` hook runs as `python3 -I` in `.claude/settings.json`, in
docs/INTEGRATION.md's copy line and in its self-test (H-056), under the same
rule as the guard.

**A killed review is resumed (H-057).** A daemon restart on 2026-10-15 killed
a running review an hour in, and nothing resumed it, because `aux.orphaned`
is not an event and no rule covers it. `aux.orphaned` joins the events, the
daemon's own stop records an aux job orphaned as it does a builder's (§38),
both playbook templates and this repository's playbook carry `aux.orphaned →
resume` (the review's prompt re-sent to a fresh context, bounded by
`max_resumes`), and the handbook's install section says a restart kills every
running job, not only the builder's.

**Phone refusals are answered; job ids are lenient (H-058, H-059).** A
command carrying the right secret that handsd refuses — "no such job", "the
builder has a job held", "no resumable session" — is published on
`ntfy_topic` titled `<command>` with the reason; only a command with a
wrong or missing secret stays silent. A job id in `approve`, `deny`,
`answer`, `reply` and `cancel` is matched case-insensitively with `O` read as
`0` and `l` or `I` as `1`, and a unique prefix of four or more characters is
accepted; the hold notification prints the id on a line of its own.

**The consult journal line after an escalation (H-060).** §27 appends a line
to the builder's `meta/journal.md` for every consultation, and the builder's
next commit carries it; after an escalation no builder commit follows, and
the next ruling send meets a dirty tree. The resume path tells the builder
to commit a dirty `meta/journal.md` first (`journal: <consultation>`), and
the handbook's ruling round says the same for a human who sends the ruling.

**The hosted review, read mechanically (review 22 and PR #3; the method in
docs/QODO-EXTRACTION.md).** The bot posts three things: a summary comment
with no findings, a "Code Review" comment that is the canonical numbered
list with header counts, and a `COMMENTED` review with one inline comment
per finding. After a push it edits the Code Review comment in place —
findings struck through, counts reset, permalinks moved — posts nothing new,
and leaves the inline comments as they were. So the protocol's reading is
now a command, `hands hosted-review <pr>`: it fetches the issue comments,
the reviews and the review comments of the pull request, every page,
filtered to the bot's login, archives each body byte for byte with its raw
JSON under `meta/reviews/hosted/PR-<n>/<k>/` (committed with the review
file), diffs a later fetch against the previous one by comment id (changed
bodies with their `updated_at`, ids added or vanished), takes the verdict
from the Code Review comment only, lists the header categories as found
(PR #3 carried "Cross-repo conflicts", a category the protocol never named),
and reports "no bot comment yet" as a state to wait on, never as clean. The
reviewer runs it as a fresh-context sub-agent, and every finding keeps its
disposition line. Tests use a fake `gh`.

**The hosted review's findings are fixed in the pull request they belong
to.** The brief template's last unit opens the pull request, waits for the
bot (ten minutes, the protocol's cap), runs `hands hosted-review`, fixes the
findings that are within the design, pushes, and records a disposition per
finding in the final report's `## Hosted review` table: fixed in `<sha>`,
dismissed with a reason, or a finding filed. The cold review then audits
those dispositions against the archive and the edited comment and reviews
the final state of the branch; a finding that needs a design decision is
filed, never fixed in silence. The cold review's own should-fix items stay
with the next mission by default; the polish round of M8a is the switch for
projects that want them closed before the merge.

**Documentation.** docs/INTEGRATION.md: a restart kills every running job
of the project and what resumes what; the driver kit has one hook and the
architect kit two; a clean-review stop pauses the pipeline and the next
apply with `go` un-pauses it; the `[server]` fallback. The handbook: the
items above, and `docs/QODO-EXTRACTION.md` cited where the protocol reads
the bot. The instruction paste for every Project follows mission 22's
install and is not repeated here.

## 40. Changes from v3.22 (mission 23 review; M8a: the harness probe and the seam's shape; credential profiles; operations)

Mission 23 merged PR #4 by its own review (REVIEW-23 `reviewed: 94ab38c`,
`blockers=0 should-fix=9`; the hosted review's eleven findings each carried
a disposition the review audited and upheld) and was installed on
2026-10-16 13:45. The restart that installed it was the first real proof of
§38's H-047: the builder it orphaned on another project was re-sent from its
checkpoint by that project's `builder.orphaned → resume` rule. The same day
produced the rest of this section: a roadmap decision taken in chat on
2026-10-15 and 2026-10-16, the harnesses installed on the laptop for the M8a
probe, the shape of credential profiles, the operations the human must be
able to perform without an agent, two readings of other orchestrators
(docs/RELATED.md), and the findings of the day. Mission 24 builds the
decided parts and runs the probe; the seam's final choice is §41, written
from the probe's record.

**Roadmap (decided 2026-10-16).** After M8a (mission 24) come M8b (mission
25, a closer if needed), then **M9 "a machine is replaceable"** (mission
26), then M5b, M6, M7. M9 is new: the machinery that lets a hands machine be
rebuilt — planned or after a disaster — from an export, a secrets checklist
and the branches, proven by a rehearsal on a purpose-built Ubuntu VM. The
notification server stays on the laptop and is addressed by its MagicDNS
name rather than the tailnet address, so a replacement machine with the same
hostname inherits the phone's subscriptions (an M9 unit; the config edit may
be made by hand earlier).

**The harness probe (mission 24 U1) and its record.** The three candidate
harnesses were installed on the laptop on 2026-10-16: `@openai/codex`
0.163.0 (`codex-cli 0.163.0`), `opencode-ai` 1.19.2 and `@deepseek-ai/dsh`
0.2.0-rc.2, under Node v22.23.3 installed with nvm 0.40.8 because dsh
requires `node ^22.19 || >=24` and the laptop ran v18. Two consequences
bind the probe and the seam: the three binaries live under
`~/.nvm/versions/node/v22.23.3/bin`, which is not on the PATH of a job
handsd spawns (systemd reads no shell profile), so a harness profile carries
its PATH prefix and the probe's commands carry it explicitly; and dsh's own
documentation says its requests carry a `dsh_session_log` wire extension
that may expose the session's working directory, prompts, tool arguments
and results to the endpoint unless the composition disables it, and names
`DSH_TELEMETRY_DISABLED`, so a dsh profile disables both before any hands
role runs on it. The probe is one unit, run by a sub-agent of the builder in
a scratch git repository under `/tmp`, never in a project's tree, with the
same small task on every harness: create one file, reply with a first line
`VERDICT: probe ok`. For each harness it records, in `docs/HARNESS-PROBE.md`
(a dated record, not a design): the exact one-shot headless command and its
exit status; the event stream it printed (its first and last five lines,
the shape of a tool call and of the final message); the resume command and
whether a second turn saw the first; where the session store is and what a
session file holds; what happened to a shell command that writes outside
the working directory and to one hands' guard table refuses (`curl`), under
the harness's most restrictive sandbox or permission setting that still
lets the task run — whether it was refused by the harness, asked about
(and how a headless run answers), or ran; whether the first line of the
final message was `VERDICT: probe ok` verbatim; the harness's documented
output when a usage limit is reached (from its docs and source, not
provoked); its telemetry and session-upload switches; whether it speaks
ACP (a built-in `acp` mode or a separately installed adapter, with the
package and version); and the sign-in state as a provider name only. A
harness that is not signed in is recorded as `unavailable: not signed in`
for every row and is not a failure of the unit; Codex must be signed in
before the kickoff, because it is the first backend. The sub-agent never
prints a key, a token or a sign-in file; a row that would need one says
`[redacted]`. The record decides §41: which seam (a per-harness headless
runner behind one interface, or hands as an ACP client receiving the
permission requests), and in which order the roles move (reviewer first,
then driver, then builder, the architect last and only after a review finds
no hole in that harness's guard, as role mode was gated).

**The seam, as far as it is decided.** The seam is at the harness, never at
the model: `[roles.<role>] harness = "claude" | "codex" | "opencode" |
"dsh"` names what runs the role, and an opaque per-role harness profile —
a directory, a PATH prefix, environment variables — says how; hands never
interprets a model name, and a model served locally later is a change in
the harness's configuration, not in hands. Four requirements hold for every
harness: a headless one-shot invocation with a session that can be resumed;
an event stream or transcript the monitor can read (its stall and
task-killed detection); a permission mode the guard can enforce; and the
VERDICT contract unchanged. Two seams are candidates. A per-harness runner
puts each harness's one-shot command, transcript reader and guard mechanism
(a Claude Code hook today; a Codex sandbox and approval policy; an OpenCode
plugin; a dsh policy plugin) behind one interface in `runner.py` and
`monitor.py`. hands as an ACP client creates the session, prompts, reads
one semantic update stream for every harness, and receives the permission
requests, so the guard runs inside hands with one table for every harness
and no per-harness hook. The prior is ACP, provided the probe shows that
each harness routes shell commands through permission requests under its
sandbox mode rather than running some silently; the risk either way is
adapter maturity and version drift, met by pinning versions in the profile.
Already harness-blind and untouched by the choice: kits, VERDICT, the
playbook, the phone, the pull-request flow, the hosted review. Claude-shaped
today and to be made neutral in M8b: the Bash guard, the monitor's
transcript reader, and the brief and review-protocol templates' references
to the Task tool and to `git worktree`. Two readings of other orchestrators
are recorded in docs/RELATED.md: Gas Town's provider presets and its ACP
proxy are the checklist the probe verifies, and its four integration tiers
name the level a harness must reach to host a hands role (their third);
Conductor's vocabulary ("a durable pause", "pinned to its definition
version", "bounded adaptive execution") and its failure matrix are borrowed
for docs/OPERATIONS.md. Nothing of either is imported.

**Credential profiles (decided 2026-10-16; implemented in M8b).** A profile
is a harness sign-in as a directory plus environment: for Claude Code a
`CLAUDE_CONFIG_DIR` holding one login, for Codex a `CODEX_HOME`, for dsh a
`DSH_HOME`. hands holds the path, never a secret; the human signs each
profile in once. Configuration: `[profiles.<name>] harness = …, home = …`
and `[roles.<role>] profiles = [<ordered names>]`. The semantics, in the
human's words, are "restart with another subscription if the current runs
out and they stop mid-something", never "never stop": when a job ends on a
usage limit the monitor classifies the end as `quota` (with the reset time
when the harness prints one), the daemon marks that profile exhausted until
then, and the job is re-sent from its checkpoint on the first non-exhausted
profile of the role's list — the `orphaned → resume` path, a fresh context,
§R recovery — because a different configuration directory has a different
session store and `--resume <session>` cannot follow. A builder loses
nothing it had committed; a review loses its partial sub-agent work, since
the protocol writes only at the end, which is why the reviewer sits on the
deepest pool. A role whose every profile is exhausted stops, and the stop
names the earliest reset. A profile whose reset has passed is eligible
again, and because the rule picks the first eligible profile in the list
and not the next one, a reset first profile wins its workers back. Pools are
for continuity, not parallelism: the job model's serialisation is
unchanged. A limit is per account, not per role, so the order protects the
architect: with three subscriptions A, B and C the architect and the driver
are pinned to A, the builder and the aux list B, C and then A — or B and C
only, in which case the pipeline waits for a reset rather than ever touching
A. The evidence that three accounts may be held is Anthropic support's
emailed reply to the human (before 2026-10-16): multiple Claude accounts
with Max plans are allowed, up to three verified with one phone number and
the same payment card, and chats and projects do not transfer between them.
Metered usage — extra usage on a plan, or an API key — is not in the plan:
the point of the pool is to use the subscriptions to the full. The
mechanism stays kind-neutral (a profile is a directory), but no API-key
profile is planned and no spend field exists. Doctor shows one row per
profile (signed in or not, exhausted until when); `status` and the start
notification name the profile a job runs on. Two things are stated rather
than assumed: the exact text a harness prints at its limit is observable
only at a real limit, so the probe records the documented formats, the
first real stop on the laptop is the fixture (the human captures it with
`scripts/capture-quota-stop.sh`, docs/OPERATIONS.md), and an end the classifier
does not recognise stays `failed`; and until `runner.transcript_path_for`
honours `CLAUDE_CONFIG_DIR` (mission 24 U3, H-063) a role on a second
configuration directory would blind the monitor, which is why no manual
rotation is attempted on an older build.

**Operations the human performs without an agent (mission 24 U8;
docs/OPERATIONS.md).** The machinery must be operable from a terminal when
the phone is away and from a plain shell when every subscription is out.
Every phone command has a laptop form; two were phone-only and gain
commands in mission 24 U2: `hands go` sends the playbook's `[series]
kickoff` line to the builder as a `clear` send with `origin: cli`, refused
while a builder job is running, queued or held, exactly as the phone's `go`;
`hands kit apply <zip>` checks the kit as `hands kit check` does, copies it
into `[files] kit_dir` and files the apply prompt as a held builder job
(`origin: kit`), which `hands approve` releases — the phone's kit path
without the phone. docs/OPERATIONS.md is the human's runbook, written for
every project on the machine: the inventory of what a hands machine holds
(the install, each project's configuration and spool, the user units, the
role directories, the builder's clones, the notification server, the kit
directory, the harness sign-ins) with each spool file classified as
regenerable, must-carry or safe to drop and the series' state of record
named (the branch); a table of secrets by kind — what it is, where it
lives, how it is obtained again, whether it can be regenerated — with no
values, ever; and the runbooks: a usage-limit stop (today: wait for the
reset, then `go`; after M8b: sign in each profile once, the daemon
rotates), operating without the phone, a planned migration, a disaster,
and a release install. M9 turns the migration runbook into commands
(`hands export`, `hands import`, `hands upgrade`, `hands project refresh`)
and updates the document; mission 24 writes the version that is true of the
machinery it ships with.

**Rulings on review 23's should-fix items 1 and 2.** Should-fix 1: §39's
sentence listed `answer` and `reply` among the commands whose job id is
matched leniently; they carry no job id (`answer <secret> <text>`), so the
lenient matching applies to `approve`, `deny` and `cancel`, and a refused
`reply` or `answer` is published under the title hands gives every
published line of that command — the code's behaviour is the design (H-064
records the departure as decided here). Should-fix 2: the architect's read
roots are `$HANDS_DOCS/docs` and `$HANDS_DOCS/templates`, narrower than
§39's "read roots gain `HANDS_DOCS`", because in a source-tree install the
docs root is the repository and the role would read unrelated hands files;
the narrower roots are the design (H-065), and H-051's Status line is
corrected to say so.

**H-061, the playbook that lacks `aux.orphaned`.** `hands kit check` and the
engine's load warn, and do not refuse, on a playbook that has a rule on
`aux.done` and none on `aux.orphaned` (and likewise `builder.done` without
`builder.orphaned`): a project whose playbook predates §39 keeps running,
and its owner learns at the next kit check that a killed review would stop
its pipeline. hands never edits another project's playbook; that project
adds the rule at its next switch point.

**The monitor's `task_killed`, de-duplicated (H-062).** On 2026-10-16 the
monitor raised `monitor.task_killed` twice within a second for a builder
the daemon's own stop had orphaned, and three times within 120 ms for one
review job whose single sub-agent ended and which went on to finish; each
raise fired the playbook's rule and published a line. The monitor raises
`task_killed` once per killed task, keyed by the task's id in the
transcript, and never for a job the daemon is stopping (the stop's record
is `orphaned`, which the next start hands to the playbook).

**The transcript path follows the configuration directory (H-063).**
`runner.transcript_path_for` wrote `~/.claude/projects/<dashed cwd>/` by
name; a role whose `env` sets `CLAUDE_CONFIG_DIR` keeps its transcripts
under that directory's `projects/`, so the monitor read nothing. The path
is computed from the job's environment: `$CLAUDE_CONFIG_DIR/projects/…`
when the variable is set for the role, `~/.claude/projects/…` otherwise,
and the runner records the path it will read in the job record before the
first scan. This is the prerequisite of every profile and of the manual
rotation by configuration directory.

**Four findings carried from another project's reviews (HF-009..HF-012 in
its ledger; H-066..H-069 here; evidence only).** A sub-agent may decline to
author what a unit asks — on 2026-10-14 a safety classifier stopped two
sub-agents and a phone architect on texts a plan assumed any agent would
write — and no escalation condition anticipated it (H-066): the brief
template's sub-agent rules say that a sub-agent that cannot or will not
produce what the unit asks reports `refused: <one line>` and stops; the
orchestrator marks the unit `[b] refused` and continues with units that do
not depend on it; the mission's verdict is `blocked <unit>`; under
`autonomous` the blocked verdict consults the architect role (§38), whose
escalation conditions gain "a unit no agent will author", answered with
`VERDICT: escalate ruling: human-supplied content` and the human-supplied
unit shape of §38. Reviews leave git worktrees registered under the
project's clone after an aborted session (H-067): the protocol's reviewer
starts with `git worktree prune` and removes stale review worktrees it
finds under `/tmp` from earlier reviews, ends by removing its own, and
`hands doctor` warns on a worktree registered under a role's clone whose
path is missing. The protocol's skip list named `meta:` and merge commits
only, while `plan:`, `journal:` and `report:` commits occur on every
mission (H-068): the list is `plan:` (read for what it says, as §38 says of
an owner file), `meta:`, `journal:` and `report:` (read for forbidden edits
only, never reviewed as a unit), `review:` and merge commits. And a
reviewer's sub-agent may run the gate twice, or in the background, or
return before a run finished (H-069): the protocol's sub-agent rules say
"run `./scripts/check` once, in the foreground, and report only when every
command has finished", which this repository's reviews already observe.

**Documentation.** docs/OPERATIONS.md is new (above). docs/INTEGRATION.md:
the `[roles.<role>].env` table's PATH note for harnesses installed under
nvm; `hands go` and `hands kit apply`; the transcript path under
`CLAUDE_CONFIG_DIR`; a pointer to docs/OPERATIONS.md. The handbook: the
refusal path and the `refused:` line (§17 gains it), the skip list, the
kit-check warning on a playbook without `aux.orphaned`, `hands go` and
`hands kit apply` in §18, docs/RELATED.md and docs/OPERATIONS.md cited.
docs/RELATED.md and docs/HARNESS-PROBE.md are new. The instruction paste is
not due: docs/ARCHITECT-INSTRUCTION.md does not change in this mission.

## 41. Changes from v3.23 (mission 24 review; the closer; what the probe found)

Mission 24 ran on branch `mission-24` and opened PR #5; its hosted review
posted nine findings, seven fixed in the pull request and two dismissed,
every disposition upheld by the cold review. REVIEW-24 (`reviewed:
53b62cc`) found one blocker and eight should-fix items, so the pull request
stays open and mission 25 is a closer: it continues `mission-24`, closes
the nine items, corrects the probe record, and leaves the branch for review
25 to merge. M8b moves to mission 26 and M9 to mission 27; nothing else in
the roadmap's order changes.

**The blocker, in the capture script.** `scripts/capture-quota-stop.sh`
exists to record the first real usage-limit stop as the `quota`
classifier's fixture (§40), so what it writes must be true. The review
found that `find` and the python read of the job record run under the
timeout bound but not through the path that writes `(failed: timed out
after <n>s: <command>)`, so a timeout there falls through to "(no job
record under …)" or "(no record, or it names no transcript)" — a false
statement in a file meant to be sent to someone. Every bounded command is
routed through the one path that records a timeout, the `-k 5` and the
timeouts on `find` and on the record read are pinned by tests with a
hanging fake, and (should-fix 1) redaction happens before any line is cut:
the redactor runs on the whole text first and cuts afterwards, so a secret
straddling the 4000-byte mark is removed whole. Tests plant a secret across
byte 4000, a URL-encoded form of a secret, and the by-value read of the
notification password.

**`hands kit apply`'s staging (should-fix 2).** The daemon-side checks on a
staged kit name are pinned: a name with `..`, a symlink, a FIFO, a directory
and a missing name are each refused as a `KitError`, never an internal
error; the file is opened with `O_NOFOLLOW | O_NONBLOCK` and `fstat`ed
before it is read, so a FIFO cannot hold a worker thread; and the daemon
removes a `.part` file it refuses, so a caller other than the CLI leaves
nothing behind.

**The probe record, corrected (should-fix 3).** Codex's VERDICT cell is
`partial: printed while the task failed` — under `workspace-write` the
model printed `VERDICT: probe ok` after the write it was asked for had
failed, with the failure in its second line. That is the observation §42
needs most: a harness's verdict line is a claim like any other, and a role
on such a harness is graded by the review and the pull-request checks, not
by its verdict. The record's opening claim reads "verbatim except where
marked `…`". If OpenCode has a default model configured or dsh is signed in
when the closer runs, the unit fills those harnesses' rows by the same
procedure as §40; otherwise the rows stay `unavailable`, which is not a
failure of the unit. The unit also tries one row the probe left as a gap
when it costs one command: `codex exec` under `-c approval_policy="on-request"`
with `--json`, recording whether an approval event appears in the stream
and what a headless run does with it.

**What the probe established, as facts for §42.** On this laptop Codex's
confining sandboxes (`read-only`, `workspace-write`) do not start: the
kernel's `apparmor_restrict_unprivileged_userns=1` (the distribution's
default) blocks Codex's bundled bubblewrap, and `codex exec` asks nothing in
any mode. The only mode that runs the task is `danger-full-access`, in which
a write outside the working directory and `curl` both ran unasked. So
Codex's enforceable permission is `no` as the machine stands, and the
decision is the human's, outside hands: an AppArmor profile that allows
Codex's bubblewrap (narrow), or the machine-wide sysctl (broad). §42 is
written for whichever is chosen, and until a confining mode runs, a Codex
role's guard story is hands' own — the ACP route, if the adapter
(`@zed-industries/codex-acp`, 0.16.0 on the registry, not installed)
routes commands as permission requests — or no Codex role at all. One-shot
and resume are `yes` (`codex exec --json`, `codex exec resume <id>`, the
session store under `~/.codex/sessions`); the stream is `partial` (a
command the sandbox failed to start leaves no `command_execution` item,
only the agent's prose); the limit output is known only from the binary's
strings (`usage_limit_reached`, `Try again at`, `reset_after_seconds`)
until a real stop is captured. OpenCode and dsh are unobserved.

**Smaller rulings.** The kit-check warning for a done rule without its
orphaned rule prints whether or not the `playbook` line passes, pinned by
a test (should-fix 4). "Stale", for the protocol's worktree cleanup, is
defined: a worktree registered under the clone whose path no longer
exists, or a review worktree under `/tmp` that is not this review's and is
older than the current aux job's start; a worktree of a review running
concurrently or one a human made is not stale, and both commands — the
opening `git worktree remove --force` of stale ones and the closing `git
worktree prune` — are pinned where they occur (should-fix 5). The
`task_killed` key's session half is pinned by a test in which two sessions
report the same task id and each raises once, and the memory's eviction is
tested (should-fix 6). The ambiguous-prefix refusal's `str` quoting is
pinned by a typed text containing a backslash (should-fix 7). The prompt
size cap counts the dispatch-time journal sentence: a prompt at the cap
with a dirty journal is refused, pinned (should-fix 8). The hosted review's
finding 3 was fixed with a design-silent choice the design now adopts: a
cli send whose text equals the playbook's kickoff line is a kickoff for the
purposes of the journal sentence and the consult count, as the phone's `go`
is.

**Documentation.** docs/OPERATIONS.md's capture section says what the
script records on a timeout and that redaction precedes cutting; the
handbook's §7 carries the definition of a stale worktree. The instruction
paste is not due.

## 42. Changes from v3.24 (mission 25 review; the project separation: a project operated from its own chat)

Mission 25 closed review 24 on the branch `mission-24`. REVIEW-25
(`reviewed: fbe58a5`, `blockers=0 should-fix=3`; the hosted review's nine
findings each with an upheld disposition) merged PR #5 itself (594b8ee),
which closed M8a, and the build was installed on both daemons on 2026-10-17
at 20:40; the restart orphaned another project's builder and that project's
`builder.orphaned → resume` rule re-sent it from its checkpoint, the second
proof of §38's H-047. This section holds the operation of a project from its
own chat (designed 2026-10-17 18:45–20:27, made the whole of mission 26 on
2026-10-18), the roadmap reordered around it, the decisions kept on disk
for later missions, and three findings carried from another project's
ledger.

**Roadmap (decided 2026-10-18 01:33, 03:08–03:12 and 11:41: separation
first, small missions).** In the human's words, all planned work that does not
contribute to project separation is postponed, and separation comes
first; and missions are kept small — not split into micro-missions, but
never large just because they can be, so they are easier to review and
their bugs easier to address. Mission 26 is the project separation: a
project operated from its own chat and the phone, without the hands
Project chat. Mission 27 is M8b, the harness seam of §40 and §41, with
Codex first: the second backends wanted are Codex and a harness for a
local model (OpenCode or dsh, or both), and the local one is mission 28,
M8b's second mission, OpenCode first. The aux re-checked both on
2026-10-18 at 03:28, correcting the probe's `unavailable` rows of
2026-10-17: OpenCode is signed in to an inference provider through a
credential file under `$HOME` (a job `handsd` starts sees it), has a
default model and answered a headless one-shot; dsh's key is exported only
for interactive shells and dsh has no credentials file, so no hands job
could reach it until the human writes one (with dsh's session-log
extension and telemetry disabled, §40). Mission 29 is M9
(§40). Then M5b (the other project's second series, its builder on
Codex), a project started from scratch (once mission 26 is installed;
no gate on credential profiles), and the migration of an in-progress,
hand-relayed project — agile-skills, stopped mid-work — in the second
onboarding shape, after M9 and when the human says it is ready; that
replaces M7's integration. Moved to the backlog: Claude credential
profiles, until a usage limit actually hits (the human's current models
spend a subscription far more slowly, 2026-10-18), and M6, spanweave,
which the human develops without hands for now.

The host decision of 2026-10-17 21:21 (a narrow AppArmor profile for
Codex's bundled bubblewrap) is superseded on 2026-10-18 at 03:08: Codex
runs on this machine as Claude Code does, unconfined (its
`danger-full-access` mode, as Claude Code runs the unguarded roles with
its permission bypass); the machine is the sandbox and the branch is the
record. No AppArmor profile is made, and no doctor row checks one. The
guarded roles (driver, architect) stay on Claude Code until a harness
guard has been reviewed, as §40 ordered; a role on Codex is graded by the
review and the pull-request checks, not by its verdict line (§41).

On 2026-10-18 at 11:41 the human numbered the local-model harness 28
and moved M9 to 29 (at 03:08 M9 was 28 and the local harness had no
number). This supersedes the order of 2026-10-17 20:27 (mission 26 the
separation with credential profiles, 27 the seam, 28 M9) and §41's (M8b = mission 26
as the seam, M9 = mission 27). Never built, in any mission: a harness
chosen per mission, two jobs of one role in parallel, balancing by
remaining quota (it cannot be observed), a fallback to metered usage, and
a switch of profile anywhere but at a resume point.

**Who operates a project.** Three places can take a notification: the
project's own Claude Project chat, the laptop's aux session, and the hands
Project chat. Since 2026-10-18 01:45 another project has been operated this
way by interim documents in its own Project (an operations document and an
interim rule 15); this mission makes the arrangement hands' own, and the
instruction paste after its release retires the interim documents.

- **The project's own chat operates that project**, as well as designing
  it. It reads a pasted notification, reads the branch, decides, writes the
  file the decision needs (a kit, an owner file) and gives the human the
  exact phone command, or, when the phone has none, a self-contained aux
  prompt that names `--project <project>`. It keeps the project's state
  board in its own Project docs. Its vehicle is the Project instruction
  (`docs/ARCHITECT-INSTRUCTION.md`, rule 15 below) and the handbook of the
  hands installed in its own sandbox (rule 13), not a skill: a claude.ai
  skill reaches Claude Code on the laptop only after an explicit sync, the
  aux needs none, and loading one in a phone Project chat was not
  confirmed, whereas the instruction with the installed handbook was proven
  from the phone on 2026-10-17, when another project's chat wrote its owner
  file from the installed template.
- **The laptop's aux is hands for every project**: one interactive Claude
  Code session that runs a self-contained prompt and decides nothing.
- **The hands Project chat keeps hands' own missions and the operations of
  the whole machine**: installs and upgrades, restarts that touch every
  project, the Claude accounts, a migration, the notification server. It
  does not operate another project: a project's notification brought to it
  is sent back to that project's chat. It receives from each project only
  that project's HF reports (below), takes them into the next hands kit as
  evidence only (handbook §15), and, before a release install restarts
  every daemon, asks the human to check that no project's review or
  consultation is running. It checks the hands-facing parts of every new
  playbook — a project's first plan kit and each series switch point: the
  playbook's rules, both orphaned rules and the blocked→consult rule among
  them, the verdict vocabulary, the kickoff, the review protocol against the
  template, the paths a prompt names — and never a mission kit.

The aim is phone commands only for a project's routine operations.

**An HF report.** A defect of hands that a project meets is recorded in that
project's ledger as an HF-nnn entry and handed to the hands Project as one
file, `HF-<n>-report.md`, holding evidence only: the HF id and its date,
the project's name, the hands build it ran (`hands --version` and the
commit the last install named), what hands did — the notifications, job ids, command
lines and their output as they appeared — and what the project expected
of hands, the commit, review number or consultation number where it was
seen, and the project's interim workaround if any, named by what it does to
hands, never by the project's content. No product design, code, domain term
or fixture goes into it. The handbook gives the form; the hands Project
files it as H-nnn citing the HF id.

**The operator table (handbook §19).** The handbook gains a section
written for the human and for the project's chat: one row per notification
hands writes — every `stop` and `notify` message of the shipped playbook
templates, and every stop and published line the engine, the limit manager
and the daemon write themselves (the budget exhausted, the kit wait, a
consultation's escalation, a usage-limit stop, `handsd started`, a refused
phone command, a `digest`) — in four columns: the notification as it reads
on the phone (its title and first words), who answers it (nobody, the human
alone, the project's chat, the hands Project), the phone route, and the
laptop route (the commands, or the aux prompt). The rows use these routes:

1. **Nothing to do.** A kit applied; a kit filed by the architect whose
   apply the playbook approved; a consultation resolved; `handsd started`
   naming the jobs it resumed.
2. **A hold.** The Approve or Deny button, or typed `approve <job>
   <secret>` / `deny <job> <secret>`; at the laptop `hands approve <job>` /
   `hands deny <job>`.
3. **A kit.** `kit <secret>` with the zip attached, Approve, then `go
   <secret>` for a mission or run kit; at the laptop `hands kit apply
   <zip>`, `hands approve <job>`, `hands go`.
4. **A ruling the builder needs in the middle of a mission** (its
   question, a driver's escalation, a blocked mission the human rules on).
   The project chat's owner file travels as a decisions kit: a zip holding
   `meta/decisions/<date>-owner.md` and a `KIT.md` whose first line is
   `plan: decisions <date> (owner)`, checked by `hands kit check` like any
   kit and sent by route 3 (below, "The decisions kit"), then `go
   <secret>`: the builder starts from the
   checkpoint, and the brief's §R makes it carry out the newest owner
   file's "For the builder" steps first (below). When the builder's last
   job is the one that asked (`VERDICT: question`), `answer <secret> <text>`
   with the zip attached is the shorter route. At the laptop: `hands kit
   apply <zip>`, `hands approve <job>`, then `hands go`.
5. **A consultation the role must make after a ruling or a stop** (an
   architect escalation, whatever its reason — a ruling, a change of
   shape, an unanswered blocker, a missing milestone, human-supplied
   content — or a blocked mission
   under a playbook without the blocked→consult rule): any owner file first,
   as route 4's kit; then `consult <secret> <reason>` (below); at the
   laptop `hands consult`.
6. **A stop the project's chat reads before deciding** (a failed job, an
   orphaned consultation, an unrecognised verdict, `max_resumes` reached,
   processes left behind, a tripwire, a review a restart killed under a
   playbook without `aux.orphaned`): `progress <secret>` and `status
   <secret>`, then route 3, 4 or 5, or `go <secret>` when the branch shows
   the work can continue as it stands; a killed review is re-sent by the aux
   prompt the table gives (the playbook's review prompt, sent to the aux
   role). A defect of hands found on the way is an HF report.
7. **A usage-limit stop.** Under the shipped playbooks a builder's limit
   stops the pipeline (no rule names `builder.limited`), while §6's resume
   is scheduled at the reset and runs anyway. The human keeps the stop's
   capture for the hands Project (`bash scripts/capture-quota-stop.sh
   <project>` from the hands repository, docs/OPERATIONS.md), then `resume
   <secret>` (at the laptop `hands resume`), so the resumed job's end fires
   the playbook's rules. This row is rewritten when credential profiles
   are built (the backlog).
8. **A machine-wide event** (a daemon down, the notification server
   unreachable, a sign-in lost, an install due): the hands Project.

A review outcome in role mode consults the role by itself; the human sees
only its consequences. The table's `digest` row says what each field of a
digest line means, and an `HF report` row gives the report's form.

**The second onboarding shape (handbook §13).** An existing project whose
architect and workers the human relays by hand is reshaped into mission
form before hands drives it: the `meta/` layout (checkpoint, plan, journal,
findings, reviews), briefs from `templates/BUILDER-N-PROMPT.md` with their
`VERDICT:` lines, the review protocol from `templates/REVIEW-PROTOCOL.md`,
a roadmap of what exists and what remains, and a playbook from
`templates/PLAYBOOK-missions.toml` carrying both orphaned rules and the
blocked→consult rule. The project's own chat writes that plan kit from the
repository as it stands — its history is left as it is, never rewritten —
and the hands Project checks its hands-facing parts as it checks a first
plan kit; the rest of onboarding is §12's. Such a project is onboarded only
after M9's rehearsal (mission 29); the first is agile-skills, stopped
mid-work.

**`consult` from the phone and the laptop.** The architect role has been
started by a `consult` rule only (§31, H-032). §42 amends that: it is
started by a `consult` rule or by the `consult` command below, both through
the engine, and `Api.send` still refuses the architect role from every
client. After a ruling, the next
consultation has been re-fired through the aux role reciting a
review-shaped reply (handbook §16), three times so far (2026-10-15, and
twice on 2026-10-17). A command replaces the recital.

`consult <secret> <text>` on `cmd_topic`, its secret the second word as
`reply`'s and `answer`'s are, starts one architect consultation whose
prompt carries, in place of a review, the human's reason: the text after
the secret and, when the message carries an ntfy attachment, the attached
file's text after it. The attachment is checked as a kit's is
(`url_problem`, `kit_dir` inside `allowed_roots`, the reported size, the
download capped while it streams and ending at exactly that size), under
its own name rule — a printable basename ending in lowercase `.md`, with no
`/` or `\`, no leading dot and a non-empty stem — and a size of at most
256 KiB; it is fetched into `kit_dir` as a kit is and read as UTF-8, and a
refused or undecodable attachment refuses the command. The kit path's
fetch and its first-free naming assume `.zip` today; they take the
extension from the name rule in force. The prompt is §31's architect
consult prompt — the roadmap's next unmet milestone, the series' escalation
conditions, the human decisions since the last consultation, the handbook
and templates paths — with the review's sections replaced by one section
headed `The human's reason for this consultation`, holding the reason
verbatim; a prompt over `hands.runner.MAX_PROMPT_BYTES` is refused with the
cap's reason. The prompt's first line is exactly `hands consult: consult on
job none (role human)`, the shape `consult_head` reads; the runner sets
the job's `HANDS_CONSULT_ROLE` from it to `human`, which changes nothing in
architect mode, where the guard refuses every send whatever that variable
says.

The command is a request to the engine, not a send. An architect job of
origin `phone` is a `reply` (§33, `is_architect_reply`): it would not
un-pause, not count against the budget, not be read for a verdict, and
would make `hands kit file` refuse the kit. So the engine starts the
consultation itself, in a branch of its `consult` action that has no event
job: the action today stops when its event carries no job, and its prompt
and record are built from that job, so the architect's prompt builder is
factored to take either a review (or blocked) job or the human's reason.
The job is an architect job of origin `playbook` like every other
consultation:
counted against `[limits] max_architect_consults`, read for its verdict
(`next kit`, `series complete`, `escalate`), its kit filed and applied as
any. The secret is the approval: no §8 hold. Once every refusal below has
been passed, the command un-pauses a stopped pipeline itself, as `resume
<secret>` does, and then has the engine start the consultation. Its
`consult.sent` event holds, field by field: `job` (the architect job),
`about: null`, `role: "human"`, `consulted: "architect"`, `event:
"consult"`, `verdict: null`, `rule: null`, `consults` and `max_consults`
(the count including this one, and the budget), `requested_by` (`phone`
or `cli`), `head` — the builder's HEAD, as every architect consultation's
does, so the next one's "since" is right — and `reason_sha256`, never the
reason. When it ends, `consult.done` carries `about: null` (not the head
line's `none`) and `role: "human"`, and the journal line reads
`consult <job> (architect <state>) on consult by the human: <verdict>`.

It is refused, and the refusal published titled `consult` (H-058): when the
playbook in force does not set `[series] architect = "role"` or the project
configures no `[roles.architect]`; while an architect job is running,
queued or held, or a consultation's `next kit` wait is open; while a
builder or aux job is running, queued or held (a consultation decides what
a stopped series does next); when the reason is empty; and when the budget
is spent, with the budget's reason. `hands consult [--file <path>]
[<text>]` is its twin at the laptop, through the daemon's socket
(`requested_by: cli`), with the same refusals; the CLI reads the file under
the same name and size rules. Neither guarded role's guard admits `hands
consult`.

`architect/CLAUDE.md` gains a rule: a consultation the human started (its
first line names `role human`) carries the human's reason in place of a
review; read the branch as rule 1 says and answer it as a review outcome is
answered — the next kit, `series complete`, or an escalation — and the
consultation counts against the budget. Its rule 13's last sentence names
routes 4 and 5 (the owner file as a decisions kit, then `go` or `consult`)
in place of the `keep` send. The handbook's §16 describes `consult` and
retires the recital.

**`digest`.** `hands digest` prints one line per project configured on the
machine — every `~/.hands/<project>.toml` that loads, in name order — and
needs no daemon. Each line holds: the project; the daemon, `up` when its
socket answers `status` within two seconds, else `down`; the pipeline,
`running` or `paused`; the mission, the number on the first line of the
builder's `meta/CHECKPOINT.md` (at its repository root) that begins
`Mission:`, else `-`; the builder, `running <job> <age>` or `idle`, with the
newest builder job's verdict line cut to 60 characters; the consultations
used and the budget, `architect <used>/<budget>` in role mode, else `driver
<used>/<budget>`; and the last stop's time and the first line of its
reason cut to 100 characters, or `no stop`. It reads each project's spool
and repository, read-only. `digest <secret>` on any project's `cmd_topic`
publishes the same lines on that project's `ntfy_topic`, titled `digest`.
Every line is redacted — every loadable project's `cmd_secret` and
`ntfy_token`, by value — before anything is cut, and only then are
the fields cut to their lengths, as §41 ruled for the capture script. A
project whose config does not load gets one line naming the file only:
never the file's contents and never the loader's message, which can quote
a value. Neither guarded role's guard admits `hands digest`. Like `status`
and `progress`, its publish answers a command; it is not one of the kinds
§11 publishes unprompted (`stop`, `job.held`), and neither is `consult`'s
refusal.

**The newest owner file, on a resume.** Route 4 needs one sentence in the
brief template's §R recovery brief: if a `plan: decisions <date> (owner)`
commit is on the branch after the checkpoint's last update and the
checkpoint does not record its "For the builder" steps as done, carry them
out first, record them in the checkpoint, and continue. This repository's
briefs carry it from this mission on.

**The decisions kit.** The phone's `kit` path already files the apply of
a zip with no brief (`apply_from_zip` lists entries and needs none), but
`hands kit check` fails such a kit on `brief`, `verdicts` and `wording`,
and the instruction's rule 13 forbids sending a kit that fails the check.
So `hands kit check` recognises a decisions kit — a kit whose every file
entry (directory entries aside; an entry the path rules refuse counts as
another entry) is either `KIT.md` or a file `meta/decisions/<name>-owner.md`
whose `<name>` is one non-empty path component, the shape the engine's
owner-file glob reads; with at least one such file; no playbook; and a
`KIT.md` whose first line passes §28's rules and reads `plan: decisions
<date> (owner)`, so the apply commits under the message §R looks for — and
passes it: `brief` says it is a decisions
kit and needs no brief, `verdicts` that it carries no vocabulary and the
playbook in force is unchanged, `wording` that it holds no brief, and
`paths`, `playbook` and `protocol` run as for any kit; the report ends `kit
check: pass (6 of 6 checks)` with the plan-only apply prompt. A kit with
any other entry is judged as before §42. `hands kit apply` takes it the
same way, so route 4 has a laptop form. `hands kit file`, the architect
role's filing, refuses a decisions kit with a reason: an owner file is the
human's word, and one the role filed would be listed to the next
consultation as decided by the human and carried out by §R. The
handbook's §3, §4 and §11 say so.

**Findings carried from another project's ledger (its HF-013, HF-014 and
the 2026-10-17 update of its HF-006, discotrade; H-070..H-072 here;
evidence only).**

- **H-070, a report's twelve lines** (decided here, built in mission 27).
  Per-commit reports ran past the protocol's twelve lines (that project's
  review 18). A count nothing enforces is not a rule: both review protocols
  drop it and say what a report holds — the sha, a verdict per point, what
  is not proven, and for the hosted-review sub-agent every finding
  verbatim. The brief template keeps its twelve lines, which budget the
  orchestrator's context over a whole mission.
- **H-071, the architect's guard on read-only commands** (decided here,
  built in mission 27). At two consultations (that project's 22 and 23,
  2026-10-17) the guard refused every command holding `#`, `{` or a
  backslash, so a Markdown heading or a pattern could not be searched for,
  and refused `ls -R`, `git ls-tree --name-only`, `git status --short` and
  `git log --date=<format>`. The characters stay refused (§30: quoting
  makes no character safe). A search of content goes through the Grep and
  Read tools, which the role has and the Bash guard does not judge, and
  `architect/CLAUDE.md` rule 10 will say so. The four options are read-only
  and will be admitted — in the guard's option sets, for both guarded
  modes, and in the architect's settings allow-list — each pinned with its
  neighbours still refused. A project runs without it (its role worked
  around each refusal), and a guard change is the unit a review weighs
  hardest, so it waits for mission 27, which makes the guard
  harness-neutral.
- **H-072, a gate past the timeout on a shared machine** (decided and done
  here). A gate run on a shared machine took 1281 s, past the 20 minutes a
  brief names and the 15 minutes hands gives builder and aux jobs by
  default (`BASH_MAX_TIMEOUT_MS`, §36). A project whose gate runs longer
  raises `BASH_DEFAULT_TIMEOUT_MS` and `BASH_MAX_TIMEOUT_MS` in its
  `[roles.builder.env]` and `[roles.aux.env]` — an edit of its own config at
  the laptop, an aux prompt its own chat gives — and its briefs name a
  timeout no longer than that. The builder reads the installed CLI's
  package files for a ceiling of its own on that variable;
  docs/INTEGRATION.md states the raise and the ceiling if there is one.
  hands' default is unchanged, and from this mission hands' own briefs name
  15 minutes (900000 ms), the default's own value, in place of 20; the
  review protocols' "20-minute cap" wording is aligned in mission 27,
  which rewrites both protocols for H-070.

**Decided and kept on disk for later missions.** Claude credential
profiles — in the backlog until a usage limit actually hits; the mission
that builds them writes them in full — as agreed 2026-10-16 23:14 and
refined by kit 26's cold review of 2026-10-17: a machine-level registry
`~/.hands/profiles/profiles.toml` (inside a directory, because every
`~/.hands/*.toml` is read as a project; `profiles` a reserved project
name) and a shared exhaustion state `~/.hands/profiles/state.json`
(written under an exclusive `fcntl` lock on `~/.hands/profiles/state.lock`,
atomically; read by every project's daemon); a profile is a harness, an
optional `home` (the job's `CLAUDE_CONFIG_DIR`; none means the default
sign-in), an absolute `path_prefix` and an `env` that may not set
`CLAUDE_CONFIG_DIR`, `PATH`, `HOME`, `HANDS_*`, the variables hands sets
itself or any `ANTHROPIC_*` name; `[roles.<r>] profiles` per role, the
first eligible profile chosen at dispatch; a limit (§6's `limited`, which
§40 calls `quota`) marks the profile and resumes at once on the next
eligible one from the checkpoint, a builder `keep` job resumed with the
kickoff, or the role waits for the earliest reset (§40's "stops" read as
waiting; no pipeline stop); a `keep` send refused on an exhausted profile;
an unspawned job when no profile is eligible; the start notification,
`status` and `who` naming or reading the profile; a
`builder.limited → notify` rule in the shipped playbooks (no new publish
kind; `aux.limited` stays outside §10's events); the trailer
`Hands-Profile: <name>`, a should-fix only when another commit of the
mission carries it; doctor's rows per profile and each profile home's
settings layer for a guarded role; the classifier read from the installed
CLI with a fixture slot for the first capture. The default pool: the
architect and the driver `["claude-A"]`, the builder and the aux
`["claude-B", "claude-C", "claude-A"]`; account A is the human's
interactive account, protected only by leaving it off the workers' lists;
no metered usage.

Mission 27 (the seam with Codex) also carries: review 25's should-fix 1
(the correction line under meta/FINAL-REPORT-25.md §3's NOT PROVEN line
on the U4 warning test) and 3 (docs/HARNESS-PROBE.md naming the approval
flag in the form that ran, `-c approval_policy='"on-request"'`, and
losing its stray line break), because it re-probes Codex; H-070 and
H-071, because it makes the protocols and the guard harness-neutral; and
the three findings whose DESIGN wording lags the code, H-027 (§12 rule
6's quoting sentence and §14's un-templated unit names), H-034 (§10's
example maps `monitor.task_killed` to `stop`; §32 says `notify`) and
H-039 (§34's start fold: the fold holds back everything but `job.held`,
as the code does), written into its section by its kit. Mission 29 (M9)
carries review 25's should-fix 2: after a failed `find`,
`scripts/capture-quota-stop.sh` writes its timeout line in the job-record
section, skips only what needs the record, and still captures the
inbox's tail, pinned by the hanging-`find` test. Dropped on 2026-10-18,
because the interactive driver session they served is retired: the tmux
wake channel and the driver guard's self-noise filter (BACKLOG,
Unscheduled).

**Documentation.** The handbook: §3, §4 and §11 name the decisions kit;
§10's row for a builder question and §14, the ruling round, give route 4
(the decisions kit, then `go`) with `answer` as the shorter route after
`VERDICT: question`, and name no driver; §13 gains the second onboarding
shape, who operates a project and the hands Project's playbook check; §16 is
`consult`; §18 names `consult` and `digest`; §19 is the operator table with
the HF report's form. docs/ARCHITECT-INSTRUCTION.md: the opening paragraph,
rules 3, 9, 12 and 14 reworded and rule 15, verbatim below.
docs/OPERATIONS.md: the no-phone table gains `consult` and `digest`.
docs/INTEGRATION.md: H-072. README.md: the commands. **The instruction
paste is due** after this release for every Project, hands and discotrade;
in discotrade's it replaces the interim rule 15, and its interim operations
document is retired.

The instruction's opening paragraph, which replaces "You are the ARCHITECT
… from files you write.":

    You are the ARCHITECT for the project named below. You design missions,
    playbooks, decisions and design documents with the human, and you
    operate the project with the human from this chat. You never drive
    execution: hands, on the human's laptop, runs the project's roles from
    the files you write. Besides files, the only text you give the human to
    send is a phone command or, when the phone has none, a self-contained
    prompt for the laptop's aux session, each complete and verbatim.

Four rules that stay are reworded, so the instruction names neither a
driver session nor a `keep` send for a ruling. In rule 3, "Short
instructions for the driver or aux sessions, and this Project instruction
itself, are chat text by nature" becomes "Short instructions for the aux
session, phone commands, and this Project instruction itself, are chat
text by nature". Rule 9 becomes "When the human reports what the aux
session or a role said, treat the report as a claim like any other and
verify it from the branch." In rule 12, "the driver's `check` is for
runtime state that is not in the repository" becomes "`status`, `progress`
and `digest` are for runtime state that is not in the repository". In rule
14, "Deliver it as a file; it is committed as `plan: decisions <date>
(owner)`, and the human sends the builder a `keep` that names it." becomes
"Deliver it as a file and as a decisions kit — a zip holding the file at
its repository path and a `KIT.md` whose first line is `plan: decisions
<date> (owner)` — and give the route rule 15's table names for it." The
rest of each rule stands.

Its new rule 15, after rule 14:

    15. When the human pastes a hands notification — a stop, a hold, an
        escalation, a usage-limit stop, a digest — answer from the operator
        table in the handbook of the hands installed in your sandbox:
        install it by rule 13's command first if this chat has not, and
        `hands handbook` prints the handbook's path. Say who answers it,
        then give this project's route in full: the phone command exactly
        as it is typed or, when the table gives none, the aux prompt,
        self-contained and naming `--project <PROJECT>`. Read the branch
        before answering a stop (rule 12). A defect of hands itself is filed
        as an HF-nnn entry in this project's ledger (in hands' own ledger,
        an H-nnn entry) and handed to the hands Project as an
        `HF-<n>-report.md` in the handbook's form, evidence only; it is
        never fixed or worked around in this project's code. The operations
        of the whole machine — installs, restarts of every project, the
        Claude accounts, a migration — are the hands Project's: say so, and
        give nothing to send for them unless this is that Project.

## 43. Changes from v3.25 (mission 26 review; the separation follow-up: operations and safety fixes)

REVIEW-26 (`reviewed: d3c4f15`, `blockers=0 should-fix=2`; the hosted
review's seven findings, two open at the end, one filed as H-073 and one
dismissed against §42) merged PR #6 itself (f16d6d1) on 2026-10-18 at
19:00, and the build was installed on both daemons at 19:34; the restart
orphaned another project's builder, which was resumed from its checkpoint
(§38, H-047). That evening the release's hand-over (the instruction paste
and a fresh chat) was given to each project's chat. This
section holds what the separation's first day showed a project's operation
needs from hands: the owner file read on every builder job, background
tasks turned off where the role's hook allows it, a playbook change kept
for the owner, H-070 and H-071 built, the DESIGN wording three findings
asked for, and review 26's two should-fix items. Evidence from another
project is cited by its HF ids, commits, dates and job ids only.

**Roadmap (decided 2026-10-18 18:52 and 19:22).** On 2026-10-18 at 18:52
the human split the next mission. Mission 27 is the separation follow-up,
this section: operations and safety fixes. Mission 28 is M8b, the harness
seam with Codex (§40, §41, §42's "Codex runs unconfined"), and it carries
review 25's should-fix 3 because it re-probes Codex. Mission 29 is M8b's
second mission, a harness for a local model, OpenCode first. Mission 30 is
M9 and carries review 25's should-fix 2. This supersedes §42's numbering
(27 the seam, 28 the local harness, 29 M9; set 2026-10-18 at 11:41). Review
25's should-fix 1, H-070, H-071 and the DESIGN wording of H-027, H-034 and
H-039, which §42 gave to the seam mission, are this mission's. At 19:22 the
human kept mission 27 as one mission of about seven units, two themes —
operating a project, and the safety of a role's session — and did not split
it. The standing rule of §42 holds: small missions, one theme each, sized
for review. Everything after M9 is as §42 orders it.

**The owner file on every builder job (H-073).** Route 4 (§42) sends an
owner file as a decisions kit and then `go`; the builder carries out the
file's "For the builder" steps because the brief's §R says so. A brief
written before the mission-26 template has no such sentence, so the builder
would resume from its checkpoint, the ruling committed and never carried
out (H-073, filed by mission 26 U5 from PR #6's hosted review; decided by
the human 2026-10-18 13:26). hands makes route 4 independent of the brief,
by the dispatch-time mechanism §39 built for a dirty journal (H-060):

- When a builder job is dispatched, hands asks the builder's repository,
  in a worker thread as §39's journal check does, which owner files have
  had no checkpoint update since they were last committed. The candidates
  are the files tracked at `HEAD` that match the engine's owner-file glob,
  `meta/decisions/<name>-owner.md` with `<name>` one non-empty path
  component (paths relative to the repository root, as §38 reads the owner
  files); a nested `meta/decisions/a/b-owner.md` is not one, nor is a file
  deleted at `HEAD`. For each, `A` is the newest commit that touched it
  (`git log -1 --format=%H -- <file>`), and the file is named when no commit
  in `A..HEAD` touched `meta/CHECKPOINT.md` (`git log -1 --format=%H A..HEAD
  -- meta/CHECKPOINT.md` prints nothing). The files are named in the order
  of their `A`, oldest first. This is asked per file, not from one newest
  checkpoint commit, so that after a merge an owner file carried out on the
  merged side, its checkpoint update with it, is not named again; any
  query with the same answer will do. Two outcomes follow and are meant: a
  later commit that changes an owner file (an edit, or a rename to a new
  path) is a new ruling, named again until a checkpoint update follows it;
  and a commit that changes an owner file and the checkpoint together
  names the file, because `A..HEAD` leaves `A` out — the checkpoint update
  that records the steps comes in a later commit, as the builder's does
  after a decisions kit, which commits owner files only. With
  `meta/CHECKPOINT.md` not tracked
  at `HEAD`, or no file named, there is no sentence. A git failure gives no
  sentence either; the job runs as it would without one.
- With any, one sentence goes before the prompt:

      [hands: an owner file was committed after the last update of meta/CHECKPOINT.md: <files>. Carry out the "For the builder" steps of each, oldest first, record them in the checkpoint and commit it, then do what follows.]

  where `<files>` are the paths, root-relative, joined by `, `. Once the
  builder records the steps and commits the checkpoint, a checkpoint update
  follows each file and the sentence stops. It is decided from git alone,
  and hands keeps no state for it.
- It is decided at dispatch, never at enqueue, as §39's journal sentence
  is, for every builder job — a kickoff (`go` from the phone or the
  laptop, the engine's kickoff after an apply), a resume (after a limit or
  an orphaned job, and a playbook `resume`), a cli send, an `answer` —
  except an apply, which must change nothing but the kit's files: a job
  with a `kit_id`, or a resume of one. A resume carries no `kit_id` (§6's
  limit resume and §10's `resume` action enqueue without it), so the test
  follows `resumed_from` back to the first job of the chain and asks it
  whether it has a `kit_id`. When both
  sentences apply, the journal sentence comes first, then this one, each
  followed by a blank line, and the prompt cap (§2's `MAX_PROMPT_BYTES`,
  §41) counts both: a job over it is refused with the cap's reason, as
  today.
- What a stored prompt says it was sent with. The runner writes the
  sentences into the record it moves to `running` (§39), so every reader of
  a stored builder prompt that asks what the job was sent reads it through
  one helper that strips hands' leading sentences — the journal sentence
  and this one, in any order, each followed by a blank line — and nothing
  else. The kickoff test (`is_kickoff`, and `consults_used`'s search for the
  last kickoff), a resume's prompt (§6's limit resume and §10's `resume`
  action, its `answer` branch among them, which re-send the job's prompt),
  §36's listing of the human's sends in a consult prompt, and the one-line
  summary of a job that `hands jobs` and `status` show read it that way.
  Without that, a kickoff that carried the sentence would no longer count
  as a kickoff for the consultation budget, and a resumed job would carry a
  sentence that is no longer true, then get it a second time (the journal
  sentence already does, on a resumed `answer`). `hands jobs --grep`
  searches the stored record as it is, hands' sentences included: it
  searches what was delivered.
- The brief template's §R sentence (§42) stays, for the builder's own
  reading of the checkpoint. The handbook's §4, §14 (the resume step) and
  §19's route 4 add that hands itself names the owner file before the
  builder's prompt, so a decisions kit and `go` is route 4 on every
  project, whatever brief its mission runs from.

**Background tasks off where the role's hook allows it (H-074; another
project's HF-015 and HF-016).** HF-015 (2026-10-18): a builder's long gate
reached its timeout, the harness moved the command to the background, and
nothing hands ships gave the builder a sanctioned way to wait for it.
HF-016 (the same day): to stop the backgrounding, that project set
`CLAUDE_CODE_DISABLE_BACKGROUND_TASKS` on the hands chat's advice, and its
builder could not start a sub-agent, because hands' own hook refused every
call (one stop; the variable was removed again). The facts, read from the
binary of Claude Code 2.1.300 on
2026-10-18 (its strings; nothing run) and confirmed for the `Agent` schema
by that project's probe under 2.1.302:

- The refusal of a `sleep` is Claude Code's own guard, not hands' hook: a
  Bash command whose first statement is `sleep N` with N of 25 seconds or
  more, alone or followed by other commands, is refused, with advice to use
  Monitor or `run_in_background` and not to chain shorter sleeps.
- For a command moved to the background, the harness advises: keep working
  if there is other work; if waiting is all that is left, wait with one
  foreground shell command that blocks until the output file shows what is
  needed, rather than checking on it repeatedly. Its result reaches the
  agent only if it finishes before the agent ends its turn.
- `BASH_MAX_TIMEOUT_MS` has no upper ceiling (§42, H-072), and the
  effective timeout of a call is the smaller of the timeout it passes and
  `BASH_MAX_TIMEOUT_MS`.
- `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS` counts as set only when its value,
  trimmed, is `1`, `true`, `yes` or `on`, in any case. Set, it makes the
  harness's background check true: a command that reaches its timeout is
  not moved to the background and ends at its timeout; the `sleep` guard is
  off (it runs only while background tasks are enabled); a sub-agent always
  launches in the foreground; continuing one with `SendMessage` runs inline
  (which closes the hole H-014 left open, a call the hook cannot see); and
  the `Agent` tool's schema has no `run_in_background`, so a flag the model
  passes is stripped before the hook sees it.
- `.claude/hooks/no_background.py` refuses a sub-agent call whose flag is
  omitted or null (§23, H-014: omitted is the background default), so under
  the variable every sub-agent call is refused. A hook command's
  environment is the session's, so the hook can read the variable.
- A driven repository commits its own copy of the hook (docs/INTEGRATION.md;
  that project's copy is its commit 3fbed1d, 2026-10-11, the same bytes as
  hands' main), so a fixed hook reaches a project only when that project
  commits it.

The rules, in the order they are built:

1. **The hook admits an omitted flag under the variable.** `no_background.py`
   admits an `Agent` or `Task` call whose `run_in_background` is omitted or
   null when `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS` in its own environment
   is, trimmed and in any case, `1`, `true`, `yes` or `on` — Claude Code's
   set, nothing wider, so the hook never admits what the CLI would still
   background. `true` and every non-boolean value stay refused under the
   variable as without it; without the variable nothing changes. Its Bash
   advice drops "up to 20 minutes" (§42 lifted that ceiling) and says the
   timeout the call passes is bounded by `BASH_MAX_TIMEOUT_MS`. `main` reads
   the variable once and passes its state to the sub-agent check as an
   argument; the check never reads the environment itself, so each
   `--selftest` case names the state it runs under, the table runs both,
   and `--selftest` gives the same answer in a session with the variable
   and in one without it.
2. **The wheel ships the hook.** `pyproject.toml` force-includes
   `.claude/hooks/no_background.py` as `hands/shipped/no_background.py`, as
   it does the guard (§34). "The installed hands' copy" is that file, or,
   for a hands run from its source tree, the repository's own
   `.claude/hooks/no_background.py` beside it, in that order (§34's
   `SHIPPED_GUARDS` order). A copy compared with itself proves nothing:
   when the copy found is the role's own file (the same realpath, as when
   handsd runs from the very clone the builder works in), there is no
   installed hands' copy for that role, and rules 3 and 4 treat it so.
3. **Doctor warns on a copy that is not the installed hands' copy** (the
   human's decision, 2026-10-18 21:0x: keep the warn). For the builder and
   the aux, `hands doctor`'s role row compares `<cwd>/.claude/hooks/
   no_background.py` with the installed hands' copy by sha256. A copy that
   differs, or is absent, makes the row a WARN — never a FAIL — naming both
   files and both sha256 values, and saying that the project's repository
   commits its own copy, which is copied from the installed one at a stop
   with no job running, then `python3 -I <hook> --selftest`. When the
   installed hands' copy cannot be found, the row says so and warns.
4. **The default is conditional** (the human's decision, 2026-10-18 21:0x).
   hands sets `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1` in a builder or aux
   job's environment only when that role's cwd carries a
   `no_background.py` that admits the omitted flag, which rule 3's
   comparison decides: the role's copy is the installed hands' copy.
   Otherwise hands leaves the variable unset, and doctor warns (rule 3).
   Why conditional: a default that reached a project before its chat
   committed the fixed hook would bring HF-016 back at the install; this
   way a project with the old hook keeps working, with the warn and
   without the variable. It is decided when the job is dispatched, as the
   runner builds the job's environment, never at enqueue; the driver and
   the architect are never given it by default.
5. **The role's env table decides over the default, either way.** A
   `[roles.builder.env]` or `[roles.aux.env]` that names the variable sets
   it to its value, whatever the hook (so `0` turns it off, since only
   `1`/`true`/`yes`/`on` count as on). Reading taken: a value handsd itself
   inherited is not passed to any role's job — a builder or aux job carries
   the variable only from its env table or from rule 4, a driver or
   architect job only from its env table — so a variable in the daemon's
   own environment cannot bring HF-016 back past the hook check.
   Doctor's builder and aux rows print the variable as the job will carry
   it: its value and source (`set by [roles.<r>.env]`, `hands' default: the
   hook admits an omitted sub-agent flag`) or `unset` with the reason; a
   table that sets it on over a copy that is not the installed hands' copy
   is a WARN naming HF-016's effect (every sub-agent call refused).
6. **The wait rule, where the harness can still background.** Written into
   the brief template's sub-agent brief, both review protocols (their
   hosted-review and per-commit sub-agents) and the handbook's §7, and into
   this repository's briefs: (a) prevent — a project whose gate can run
   past its role's `BASH_MAX_TIMEOUT_MS` raises `BASH_DEFAULT_TIMEOUT_MS`
   and `BASH_MAX_TIMEOUT_MS` above its worst case (§42, H-072), and its
   briefs name that timeout; (b) a long command ends with an exit marker,
   `./scripts/check; echo "check-exit=$?"`, so its end shows in its output;
   (c) if a run is moved to the background anyway, wait with one foreground
   command that blocks until the output file shows the marker — `until grep
   -q '^check-exit=' <file>; do sleep 5; done`, with an explicit timeout —
   never a `sleep` of 25 seconds or more as a command's first statement,
   never Monitor or a background task, and never end the turn before the
   run has finished. In the brief template the timeout is a placeholder the
   brief fills (`<the gate's timeout, in ms>`), as the template's other
   blanks are; this repository's briefs and protocol write 15 minutes
   (900000 ms).

docs/INTEGRATION.md's §21 paragraph says all six, and that a release which
changes the hook is copied into each project's repository by that project.
The suite passes with the variable set in the gate's own environment and
without it: once this release is installed, this repository's own builder
runs its gate under the default.

**A playbook change is the owner's (H-075).** Under `[series] architect =
"role"` with `autonomous = true` the engine approves every apply of a kit
the architect role filed (`decided_by: playbook`), judging its provenance
(`kit_apply_problem`, §32–§34) and never its content. A kit that carries
the playbook in force would be approved too, so the role could raise its
own `max_architect_consults`, drop a stop rule or change the kickoff, and
the human would never see it. The human's approval of the switch-point
playbook (§31) covers the applies made under it, not a rewrite of it
(found 2026-10-18 while checking another project's budget raise; scheduled
by the human 17:24).

- The engine does not approve an architect-filed apply whose stored kit
  carries `PLAYBOOK.toml` or `meta/PLAYBOOK.toml` (the paths `hands kit
  check` reads, §26), whatever its bytes. The check is the engine's
  approval's, made in `_release_kit` after `kit_apply_problem` has accepted
  the apply and `_kit_bytes_unchanged` has verified the stored zip, so the
  entries read are those of the bytes the check passed on; never inside
  `kit_apply_problem`: that function says whether
  an apply is one hands filed from the role's kit, and the `next kit` wait
  (`_kit_filed_for`), `defer_hold` and the `job.held` path all ask it, so a
  playbook-carrying kit stays a filed kit to all of them. The apply stays
  held and is published with its Approve and Deny buttons, as every hold
  the engine does not approve is (§36). The gate's reason stays `apply
  <name>` (`kit_apply_problem` reads it); the published notification's
  reason reads `apply <name>: the kit carries <path>, the playbook in
  force; a change of the playbook is the owner's (§43)`, passed to the
  daemon's hold seam (`publish_hold`) as a parameter. It reads so wherever
  the engine publishes such a hold it does not approve, a paused pipeline's
  among them (where `_release_kit` publishes the hold before any other
  check). The consultation
  itself ends as it would (`next kit <name>` naming that kit is no
  escalation); only the approval is the human's.
- Once the human approves it, the engine's kickoff-after-apply does not fire
  (it is for applies the engine approved, `_engine_applied_kit`, §32); the
  playbook's own `kit applied` rule fires, and the human sends `go`. A
  denial takes the path a denial takes today. The missions playbook
  template's comment on that rule ("under an autonomous architect series
  this rule does not fire") says it fires for an apply the human approved.
  This repository's own `PLAYBOOK.toml` is not edited by the mission: a
  change of the playbook in force is the owner's, which is this section's
  point.
- `hands kit check` prints a `WARN playbook:` line for a kit that carries
  a playbook when the repository's playbook in force before the apply, or
  the kit's own, sets `architect = "role"` with `autonomous = true`: filed
  by the role, its apply waits for the human (the engine judges under the
  playbook in force when the kit is filed, so a kit that switches a series
  back to phone mode is held too).
- A change of the budget, a rule or the kickoff is the owner's: a direct
  `plan:` commit by the human between jobs, or an apply the human
  approves. For the role it is an escalation, rule 8's "a decision would
  change the shape the human approved at the switch point":
  `architect/CLAUDE.md` rule 3 no longer lists `PLAYBOOK.toml` among a
  kit's entries and rule 8 says a change of the playbook is that shape.
  The handbook's §3 (the kit's entries), §6, §12 and §19 say so.
- The consequence, stated in the role-mode templates and the handbook's
  §12: a series in role mode needs a kickoff line that never changes, such
  as this repository's `Read the builder prompt with the highest mission
  number in the meta directory and execute the mission below its
  divider.`, because a kickoff that names the mission would need
  a playbook in every kit, and every kit would wait for the human.

**H-070 and H-071, built (decided in §42).** Both review protocols drop
the twelve-line count and say what a report holds: the sha, a verdict per
point and what is not proven; for the hosted-review sub-agent, every
finding verbatim with its verdict on the builder's disposition. The brief
template keeps its twelve lines. The protocols' "one run at a time fits
inside the 20-minute cap" becomes "inside the gate's timeout": in this
repository's protocol, 15 minutes (900000 ms), the timeout hands' briefs
name since §42; in the template, the timeout the project's briefs name
(hands' default 15 minutes). The guard admits `ls -R`, `git ls-tree
--name-only`, `git status --short` and `git log --date=<format>`, in its
option sets for both guarded modes, each pinned with its neighbours still
refused (`ls -r`, `git ls-tree --name-status`, `git status --porcelain`, a
`--date` with no value); `architect/settings.json`'s allow-list gains `git
-C ./repo status`; `architect/CLAUDE.md` rule 10 says a search of content
goes through the Grep and Read tools, which the Bash guard does not judge.
The characters stay refused (§30).

**The intermittent test (H-076; review 26 should-fix 1).**
`tests/test_operations.py::test_kit_apply_refuses_a_staged_name_with_dot_dot`
failed twice in mission 26, both times at its U1 commit (b956e2a), and was
green alone, with its file and at every other commit; it dates from mission
24 (2f9e219). A gate that can go red on an unchanged tree is a gate nobody
can read. The mission files H-076, finds the race and fixes it, or, if no
cause can be found, pins it: the test's run repeated in a loop under the
conditions of the suite, with the result in the finding. Either way the
finding says what was found. Two more tests failed under load in the
architect's sandbox on 2026-10-18 (run as uid 0, at f16d6d1 and with this
section's kit applied) and passed alone:
`tests/test_library.py::test_open_refuses_a_running_job` and
`tests/test_gates.py::test_cancel_is_gated_by_default_and_approval_performs_it`.
They are leads for the same search, not findings of their own until the
laptop shows them.

**The operator table follows the code (review 26 should-fix 2).** §42
asked for every stop and published line the engine, the limit manager and
the daemon write themselves; two had no row: the playbook-load stop "the
playbook is not the committed copy, so no rule can be trusted to fire: …"
and the phone's follow-up to a received kit "apply <name>: <why>; the
commit message is the default '<message>'". Both get rows, and so does the
hold this section adds. A test lists the stop reasons and published lines
from the code itself — every string or f-string passed as a stop's reason
or a publish's title or message in the engine, the limit manager, the
daemon and the phone — and requires each in a row of §19, so a line added
without a row turns the test red. The receivers that count: the engine's
and the limit manager's `stop`, the daemon's `_limit_stop`, and the
notifier's `notify` and `answer` and the engine's `_notify`; a `.stop`
on another object (`self.monitors.stop(job_id)`) is no pipeline stop. A
reason that arrives as a parameter is read at the callers that pass it,
and a helper whose returned string becomes a reason (`_architect_stop`
and its like) is read by its `return` statements. How each is read: an f-string is its
text with each placeholder written `<…>`, as the table writes a
placeholder, and matched on its literal pieces in order, so the
escalation's `f"{event}: the architect escalated: {reason} — …"` is
matched on "the architect escalated:" and what follows it; a reason
passed through a name is traced to the literals
assigned to that name in the same function, or listed as an exemption
naming where its literals are; a title passed as a constant
(`NOTIFY_KINDS[...]`, a module constant) is read as the constant's value.
An exemption list is allowed, each entry with its reason. The test is not
green by construction: removing one row turns it red, shown for three rows
— a literal reason, an f-string that begins with a placeholder, and a
reason passed through a name. handswho's pushes stay out: it is its own
process.

**The DESIGN wording, written here (H-027, H-034, H-039).** §12 rule 6's
quoting sentence reads "quoting makes no character safe: one from the
guard's refused set is refused inside quotes too", as `driver/CLAUDE.md`
rule 6 has said since mission 14. §14's layout names the templated units,
`systemd/handsd@.service` and `systemd/handswho@.service`, and §24's
optional who unit is `handswho@.service`. §10's example maps
`monitor.task_killed` to `notify` with a message, as this repository's
playbook and both templates have since mission 16 (§32), and §24 says the
example maps `monitor.orphan_processes` to `stop`. §34's start fold reads
as the code has done since mission 18: it holds back everything a
re-admitted job publishes except a `job.held`, which is published at once
with its buttons. The copies follow: `tests/fixtures/playbook_example.toml`
and the verbatim block in `docs/PLAYBOOK.md` take §10's example, the test
that lists the example's rules and the sentence under the verbatim copy
say `notify`, and `docs/PLAYBOOK.md`'s H-034 sentence and its pin go. The
three findings are resolved by this text.

**Review 25's should-fix 1.** A dated correction line under
`meta/FINAL-REPORT-25.md` §3's NOT PROVEN line on the U4 warning test:
REVIEW-25 found that both parametrized cases, kickoff differs and no
kickoff, went red under the `playbook_check.ok` mutation, so both pin it.

**Review 26's NOT PROVEN items and observations, weighed.** A test for
`consult` refused while an architect job is queued, and one for a refusal
caused by a state change while a phone `consult`'s attachment downloads.
A refused `consult` on an idle project with a dirty playbook stops the
pipeline through §10's load, which is the right stop (the playbook in force
is not the committed copy, whatever command found it); a test pins it.
After a failed enqueue the inbox keeps a `pipeline.resumed` while the
pipeline is paused again: the inbox is a log of what happened, in order,
and `hands pipeline` is the state; it stands. `digest`'s mission field
takes the first digit run after `Mission:`, which is the checkpoint's own
first line in every brief hands ships; it stands.

**Documentation.** The handbook: §4, §14 and §19's route 4 (hands names
the owner file itself), §6 (the playbook change is the owner's), §7 (the
wait rule; the protocols' report contents), §12 (the role-mode kickoff
that never changes; the hold of a kit that carries the playbook), §19 (the
rows above). docs/INTEGRATION.md: §21's paragraph on the hook, the
variable, the default and the copy. `architect/CLAUDE.md`: rules 3, 8 and
10. The templates: the brief template's sub-agent brief (the wait rule) and
its kickoff note for role mode, both review protocols, the missions
playbook template's architect block (the kickoff note). README.md where it
names the hook's rule. **No instruction paste is due** after this release:
`docs/ARCHITECT-INSTRUCTION.md` does not change. The hand-over to each
project's chat names the fixed hook and the doctor warn, and that project
commits the installed copy when its chat decides to.

## 44. Changes from v3.26 (mission 27 review; a pause that holds the next step)

REVIEW-27 (`reviewed: 317983b`, `blockers=0 should-fix=3`; the hosted
review's four findings: two fixed in the pull request, one dismissed, one
filed as H-077) merged PR #7 itself (d587fa6) on 2026-10-19 at 08:08. The
install was split per project for the first time, because another project's
autonomous series is never idle for long: the shared steps and hands' own
part went in on 2026-10-19 (doctor green, the builder and aux rows carrying
`CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1` by §43's default), and that
project's part waits for its own quiet moment. This section holds the
roadmap as decided on 2026-10-19, a pause that holds the next step instead
of dropping it (H-078, from that project's HF-017), review 27's three
should-fix items and the ruling on H-077.

**Roadmap (decided 2026-10-19 01:42 and 19:3x).** At 01:42 the human asked
for GitHub to enforce a pull-request-only `main` with CI passing, built into
the next mission "so that we do it the right way and nothing blows up", and
then applied to another project. At 19:3x he split that next mission:
mission 28 is this section — the pause, review 27's should-fix items and
H-077, small, so that the other project's waiting commits and the pause's
live test come sooner; mission 29 is the pull-request gate; mission 30 is
M8b, the harness seam with Codex (+ review 25's should-fix 3); mission 31 is
M8b's second mission, a local-model harness, OpenCode first; mission 32 is
M9 (+ review 25's should-fix 2). This supersedes §43's numbering (28 the
seam, 29 the local harness, 30 M9). Everything after M9 is as §42 orders it.

**The pull-request gate (mission 29; decided 2026-10-19 01:42, written in
full by its kit).** The facts it starts from, read from the branch on
2026-10-19: nothing stops a direct push to this repository's `main` — every
kit apply (`plan:`) and every `review: mission N` commit goes straight to
it; this repository has no CI (no `.github/`), its gate is `./scripts/check`
on the laptop, and the hosted reviewer posts comments. A ruleset with no
bypass would therefore refuse the review's own commit and the next kit
apply, and a required check would never report. The basis is a ruleset
template proven on another repository (October 2026): `pull_request` with
0 approvals and `require_extra_approval_for_unattributed_changes: false`,
`required_status_checks` named from check runs GitHub actually reported
and pinned to the reporting app, `non_fast_forward`, `deletion`, no bypass
actors, `~DEFAULT_BRANCH`, verified by `current_user_can_bypass: never`,
never tested with a direct push. Mission 29 builds, so the gate breaks
nothing: a CI workflow running `./scripts/check` on pull requests, green on
GitHub's runner; a per-project setting for how `main` moves, `direct`
(today, the default) or `pull-request`, under which a kit apply and a
decisions kit land through a pull request merged once CI passes (the
approval of the apply is the merge decision), the review commits
`REVIEW-N.md` to the mission's branch before it merges, and no `journal:`
line lands on `main` directly; the template in the repository as
`docs/PR-CI-GATE.md`, with the rule that the hosted reviewer's check is
never required; doctor's report of the setting against the branch's rules.
The gate itself is created by the aux after that release is installed. A
project on the direct shape (another project's missions commit straight to
`main` and it has no CI) switches at a quiet moment of its own, after
mission 28's pause has been tested there, so that a failure in either is
attributable to one change.

**A pause that holds the next step (H-078; another project's HF-017).** In
an autonomous series a builder job spans a whole mission, so the first job
boundary is the mission's end, and the review, the consultation, the kit's
apply and the next kickoff follow each other within moments. A human who
needs the working tree quiet (for an owner commit) has no way to stop the series at the next boundary: `pause`
is a stop (§10) and running jobs go on, but a paused pipeline drops every
event it receives (`on_event` logs "fires nothing" and returns), `resume`
replays nothing, and nothing says when the series has come to rest.
Reading the code on 2026-10-19 also showed the sharper case: a daemon
start feeds each orphan once and marks it fed before the engine hears it,
so a restart while the pipeline is paused consumes the builder's orphan
and nothing ever resumes it. Evidence: that project's HF-017 (2026-10-19),
its builder job 0mve1pq5x-jej2 running a whole mission while three owner
commits waited from 2026-10-18 21:14, an aux guard replying `VERDICT:
blocked busy`.

The rule, decided by the human on 2026-10-19 (02:2x: a human pause holds,
the rest is published, `resume` replays; no new command). A human pause is
a pause sent by `pause`, from the phone or the laptop (`paused_by` `phone`
or `cli`); every other stop (`paused_by` `stop`) keeps §10 as it is. What
a human pause holds is the series' next step, which in every series starts
from a role's end; everything else under a human pause is as under any
pause today, with nothing left silent.

1. **A role's end waits.** Under a human pause, the end of a builder, aux
   or driver job (`<role>.done`) whose decision would do anything but
   notify — a rule's `send`, `consult` or `stop`, §10's own stop when no
   rule matches, no verdict matches or there is no `VERDICT:` line, or the
   engine's kickoff after an apply the engine approved — is kept, not
   decided: its kind, its job and its verdict line. Kept ends are one per
   role, in arrival order: a later end of the same role replaces the earlier
   one and takes the later place (one inbox event, `pipeline.kept_replaced`,
   names both), since a role's newest end is where the series goes on from.
   A role's end whose decision is a `notify` fires at once. Whether an end
   would send, consult, stop or notify is decided at its arrival with the
   playbook as loaded at that moment — rule matching and the engine's own
   rule, executed for nothing. §10's load when a job starts is unchanged;
   what waits is H-044's reload at an engine-approved apply's end (§36),
   which happens instead in `resume`'s reload (rule 5); so an
   engine-approved apply's end is kept for the engine's
   kickoff, which comes before the playbook's `kit applied` notify as it
   does unpaused. A driver consultation's end that §28's enforced stop
   covers (an escalation, no verdict, not resolved) is that stop, handled
   by rule 2, never kept.
2. **Everything else is as under any pause, and nothing is silent.** A
   rule whose action is `resume` (on `*.orphaned` or `*.failed`) fires under
   a human pause, bounded by `max_resumes` as always, so a daemon restart
   during a human pause resumes the builder it killed — until a stop has
   been suppressed under that pause: from then on, recorded with the pause,
   a `resume` rule fires nothing, as under any other stop today, since a
   tripwire or a failure the human has been told of must not be resumed
   past without the human. A
   `*.limited` event is §6's: §6 schedules its resume whatever the pause.
   A `job.held` or `job.denied` fires nothing: a hold is published with its
   buttons, as under any pause. An architect consultation that ends under a
   human pause is decided as under any pause today: the engine approves no
   kit, so its kit's apply is held for the human, and after the human
   approves it no engine kickoff follows. Every stop that a paused pipeline
   suppresses — a `stop` rule on any other event (a monitor tripwire, a
   `*.failed` with no resume rule), a resume's own stop (`max_resumes`
   reached, an enqueue that fails), the limit manager's, a driver
   consultation's enforced stop, a consultation's escalation or its kit
   wait — is, under a human pause, also notified once, as §29's consult stop
   over a paused pipeline already is; the human pause and the kept ends
   stay. Two no-ops are not stops and are not notified: a `pause` over the
   human pause, and a refused `resume` (rule 5). The step already running
   finishes: a driver consultation running when the pause was sent makes
   its own send (in phone mode, a `keep` answer to the builder's question),
   that builder job runs, and its end is kept in its turn; `at rest` waits
   for it.
3. **Only `resume` ends a human pause.** A job of an un-pausing origin
   (`UNPAUSE_ORIGINS`: a cli send, a phone `answer` or `go`, a kit's apply)
   that starts under a human pause does not un-pause it, so a decisions kit
   applied at rest commits and the kept end still waits. `go` and `consult`
   are refused under a human pause, published titled as their refusals are
   (§39, H-058), naming `resume`. A `pause` over a human pause is a no-op
   that keeps `paused_by` and the kept ends; a `pause` over another stop
   stays a no-op (§19).
4. **At rest is published.** Under a human pause, the first moment no job
   is running, queued or held and no §6 resume is scheduled, the engine
   publishes one notification titled `hands: at rest`, naming each kept end
   (role, job id, its verdict line cut to 100 characters) or saying none is
   kept. The moment is checked when the pause is sent and whenever a job
   reaches a terminal state, however it got there — done, failed, limited,
   killed, orphaned, cancelled while running or queued, denied, or a job
   the runner could not spawn — not
   only on the §10 events. Once per human pause, the mark recorded with the
   pause so a restart does not publish it again; published again only when
   a kept end is replaced after it, with the new list. It is the cue a
   project chat's commit prompts guard on, instead of polling `jobs`.
5. **`resume` replays.** `resume` reloads the playbook first (`reload()`),
   so an owner commit made at rest is the playbook replayed under. A
   playbook file that exists and does not load, or no playbook while ends
   are kept, refuses the `resume` with the load's reason: the human pause
   and the kept ends stay until a `resume` that loads. With no playbook and
   nothing kept, `resume` un-pauses as today (doctor's install check,
   `pause` then `resume`, runs before any playbook exists). Otherwise
   `resume` un-pauses and decides the kept ends in order, as if each had
   just arrived — a rule's action, §10's stop, or the engine's kickoff —
   up to and including the first whose decision starts a job or stops the
   pipeline; a replayed send the API refuses (a `keep` to a role whose last
   job has not ended) is §10's stop for a send that could not be made. The
   ends after that one are discarded (one inbox event,
   `pipeline.kept_discarded`) and named in a notification, so one replay
   starts at most one step and nothing kept outlives the human pause.
6. **The state persists and shows.** The kept ends, the `at rest` mark and
   the mark that a stop was suppressed under the pause (rule 2) live in
   `pipeline.json` with the pause, so a daemon restart forgets
   neither; an unreadable `pipeline.json` loses them, as it loses the pause
   today (§10's unreadable-state stop), and that stop says so. `hands
   pipeline` prints one `kept` line per end, and the phone's `status` names
   the human pause and the kept ends.

This departs from one line of HF-017's expectations ("a stop that arrives
first replaces the armed one"): under a human pause, a role's end whose
rule is `stop` waits and is named in `at rest`, and every other stop is
notified while the pause holds; the pause stays one state with one way
out. A consultation that ends under a human pause leaves its kit to the
human, as any pause does today: after approving the apply, the human sends
`resume`, then `go`.

**Review 27's should-fix items.**
1. The daemon computes §43's hold reason on the event loop: `_held_reason`
   (from `_on_event`, which must be cheap) and `_publish_held` (in `start`)
   load the job, run `kit_apply_problem` and, for an architect hold, read
   the stored zip's entries and hash it. The engine's paths use a worker
   thread; the daemon's must too: no zip read or hash on the event loop.
   Pinned by a test that fails when the read runs on the loop's thread.
2. `hands doctor --live` builds its turn's environment as `{**os.environ,
   **role.spawn_env}`, outside `runner.job_env`, so the live turn carries an
   inherited `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS` and never §43's default;
   the architect's live turn (its kits check) builds its own the same way.
   Both live turns' environments are built by `job_env` (or the one
   decision it uses), as a real job's is.
3. The operator table's reader (§43) matches a one-word title by substring
   over the Notification column, so a new published line titled `go` or
   `kit` with no row of its own leaves the test green. A title is matched
   against the start of a row's title.

**`hands show` prints `resumed_from`.** §6 lists `resumed_from` as a job's
field, and `hands show --json` carries it, but the prose view omits it, so a
human reading which job a restart's resume came from must ask for JSON
(found by the aux on 2026-10-19 while checking another project's install).
The prose view prints it when it is set.

**H-077, ruled (the human, 2026-10-19 19:3x).** A role-filed kit entry naming
the playbook in another case (`playbook.toml`, `Meta/PLAYBOOK.toml`)
passed §43's check, and on a case-insensitive filesystem would overwrite
the playbook in force. Reading the configuration on 2026-10-19 found a
second gap: the playbook's path is configurable (`[playbook] path`,
relative to the builder's cwd, read here as a repository path with the
cwd's own place in the repository before it, as §38 reads the owner
files), and a kit carrying a configured path other
than the two fixed names is not caught either. The ruling: an entry counts
as carrying the playbook when its path, casefolded, equals the casefolded
configured playbook path or either of the two fixed names
(`PLAYBOOK.toml`, `meta/PLAYBOOK.toml`). The engine's hold (§43) and `hands
kit check`'s `WARN playbook:` line use that one test, and the WARN judges
the repository's playbook at the configured path as well as the fixed
names; `kit check` without a project configuration knows the two fixed
names only and says so. `kit check`'s `playbook` check still loads only an
entry at a fixed name: on the case-sensitive filesystems hands runs on, a
case-variant entry is another file, not the playbook in force, so it is
held and warned, not validated.

**The live gate, after the install (decided 2026-10-19 02:26).** Another
project's three owner commits (HF-017) wait for this release, and are its
live test there: `pause <secret>` while its builder runs, the `at rest`
notification naming the kept end, the commits made at rest by that
project's chat, `resume <secret>`, the kept end decided and its step
started, all read
back from that project's branch and `hands pipeline`/`inbox`. Nothing is
paused there before this release is installed.

**Documentation.** The handbook: §10 (a human pause holds a role's end
that would start the next step; everything else is as under any pause,
and notified), §14
(a ruling committed at rest), §18 (`hands pipeline`'s `kept` lines), §19
(rows for `at rest`, the `go` and `consult` refusals under a human pause,
a `resume` refused because the playbook does not load, a stop notified
under a human pause, and a replay that stopped with ends discarded). docs/PLAYBOOK.md
(the paused pipeline, the kept ends, `resume`). docs/OPERATIONS.md (a
quiet moment: `pause`, wait for `at rest`, commit, `resume`). The release
routine's warning about a project paused at a restart is retired once
this is installed. No instruction paste is due: `docs/ARCHITECT-INSTRUCTION.md`
does not change.

## 45. Changes from v3.27 (mission 28 review; a `main` that takes pull requests only)

REVIEW-28 (`reviewed: 45ed9c9`, `blockers=0 should-fix=2`; the hosted
review's seven findings: six fixed in the pull request, one dismissed)
merged PR #8 itself (1acc9e0) on 2026-10-20 at 05:12. The release was
installed on both daemons at 22:10 the same day in one step, both projects
being stopped with no job running (the review's rule-9 stop here, an
escalation there). This section holds the pull-request gate decided on
2026-10-19 at 01:42 and written here, review 28's two should-fix items,
and a gap in how an apply that fails is decided (H-080).

**Review 28's should-fix items.**
1. §44 rule 4 publishes `hands: at rest` again only "when a kept end is
   replaced after it". An end of a role with nothing kept yet, kept after
   the mark (a laptop `hands send` to the aux under the pause, whose
   `aux.done` is then kept), publishes nothing, and the list the human or a
   project chat guards on is stale (H-079). Rule 4 now reads: once per human
   pause at the first moment nothing runs, and **again, with the new list,
   at the first such moment after the kept list has changed** — an end kept
   or an end replaced after the last publication. The mark records when it
   was last published; a restart publishes nothing unless an end was kept
   after the mark.
2. FINAL-REPORT-28 §4 lists U1–U4's readings and omits one made by 58deee7:
   under a human pause, with the playbook file present and not loading
   (`load_error` set), a role's end is kept, its §10 decision being the
   load's stop. That reading is the design: §10's stop for a playbook that
   does not load is a stop like any other, and rule 1 keeps a role's end
   whose decision is a stop. Nothing to change.

**The facts the gate starts from (read from the branch on 2026-10-20).**
Every change reaches this repository's `main` by one of five commits, and
the pull-request gate (a GitHub ruleset with `pull_request` and
`required_status_checks`, no bypass, docs/PR-CI-GATE.md) refuses every one
of them pushed directly:
- a kit's apply (`plan:`, and `plan: decisions <date> (owner)`): a builder
  job in the builder's tree, on whatever branch it is on, which commits and
  pushes (§27, §42) — on `main` for every kit sent between missions;
- the review's file (`review: mission N`, with the hosted review's archive):
  the aux commits it to `main` before any merge (§35, §39);
- the merge of a mission's pull request (`gh pr merge --merge`), which the
  gate allows once the required checks have passed;
- a `journal:` commit: every consultation appends one line to
  `meta/journal.md` in the builder's tree (§27), committed by the builder
  when hands' sentence (§39, H-060) or its brief's §R tells it to — on
  `main` when the consultation came between missions, as every architect
  consultation does in role mode;
- a mission whose brief says "Direct" (§35), whose unit commits go to `main`.
This repository has no CI (no `.github/`); its gate is `./scripts/check`
on the laptop. And a kit can turn the gate red on purpose: kit 27 reworded
DESIGN text a test pins (H-034's fixture), and its mission's U1 made the
test green again.

So the gate breaks nothing only when, before it exists, hands can do each of
those five things through a pull request whose CI has passed. This section
builds that, behind a per-project setting that defaults to today's shape:
installing this release changes nothing until the human switches a project.

**The setting.** `[repository] main = "direct" | "pull-request"` in the
project's config (`~/.hands/<project>.toml`), `direct` by default; any
other value refuses to load, naming the two. It says how `main` moves for
hands: `direct`, as today; `pull-request`, only through pull requests,
merged once their checks have passed. handsd reads it at start, like every
key, so a change takes a restart. It decides the apply's prompt and the
journal sentence below, and doctor's `main` row compares it with `main`'s
rules on GitHub. Nothing else in hands reads it: the review protocol, a
project file, reads `main`'s rules from GitHub itself (below). A project
whose setting and rules disagree is warned by doctor, and an apply whose
push is refused stops (below).

**`hands ci-wait <pr> [--check <name>]…` (the checks, read mechanically).**
A client command, like `hands hosted-review` (§39), run in a clone whose
`origin` is the pull request's repository, through `gh` only, read-only.
The checks it waits for, by name: the `context` of each entry of the
`required_status_checks` rule in the base branch's effective rules (`gh api
repos/<owner>/<repo>/rules/branches/<base>`); with no such rule, the names
given with `--check`; with neither, it waits for nothing and exits 2 ("no
check to wait for: <base>'s rules require none and no --check was given"),
so a merge never follows a guess. It reads the pull request's checks with
`gh pr checks <pr> --json name,bucket,link`, which exits 0 whatever the
checks' buckets are, and exits 1 with "no checks reported on the
'<branch>' branch" until the first check registers: `ci-wait` reads that
message as none reported yet, and any other failure as an error. An awaited
check not reported yet is pending. One call waits at most nine minutes, so
that it fits one foreground tool call under any role's bash timeout (§36),
polling every thirty seconds, and exits:
- `0` — passed: every awaited check has completed as `pass` or
  `skipping`;
- `1` — failed: an awaited check completed as `fail` or `cancel`;
- `3` — still waiting at the end of the nine minutes (an awaited check
  pending or not reported yet): the wait, never a pass; the caller calls it
  again;
- `2` — no check to wait for, or it could not read the pull request, the
  rules or the checks (no `gh`, not signed in, no such pull request).
At the end of the call it prints one line per awaited check (name, bucket,
link), then a last line `ci-wait: passed | failed: <name> | waiting:
<names> | error: <reason>`. A check the rules do not require (a hosted
reviewer's, if one posts one) is never awaited and never decides.

**The apply (§27), by the setting.** Under `direct` the prompt is today's
with one sentence added before "Change nothing else.": `If the push is
refused, undo that commit (git reset --keep HEAD~1) and reply instead with
one line: VERDICT: kit not applied pr=none <why, in one line>.` — so a
refused push leaves no unpushed commit behind. Under `pull-request` it is,
word for word, with `{location}`, `{touched}` and `{message}` as today,
`{branch}`, `{title}` the commit message shell-quoted, `{body}` and
`{subject}` below:

    Apply {location} to this repository, whose `main` takes pull requests
    only (DESIGN §45). First, where the working tree is. (a) On `{branch}`,
    this kit's own branch: go on below from the step not done yet (`gh pr
    list --head {branch} --state all --json number,state` names its pull
    request and whether it merged). (b) On another branch, not a `kit/` one,
    that is on `origin` (`git ls-remote --exit-code --heads origin <that
    branch>`) and whose pull requests, if it has any, are all open (`gh pr
    list --head <that branch> --state all --json state` names none `MERGED`
    or `CLOSED`), a mission is in flight on it: unzip
    -o into the repo root (it {touched}), then one plan-only sub-agent makes
    a single commit {message} listing those files in its body, and pushes
    that branch; reply with one line: VERDICT: kit applied <sha>; if that
    push is refused, undo the commit (`git reset --keep HEAD~1`) and reply
    with one line: VERDICT: kit not applied pr=none <why, in one line>. (c)
    On any other branch: `git checkout main`. Then, on `main`: `git pull
    --ff-only`, and the first of these that holds. If `gh pr list --head
    {branch} --state merged --json number,mergeCommit` names a merged pull
    request, the kit is on `main` already: reply with one line: VERDICT: kit
    applied <its merge commit's sha>. If `gh pr list --head {branch} --state
    open --json number` names an open one: `git checkout {branch}` and go on
    below from the step not done yet. If `git ls-remote --exit-code --heads
    origin {branch}` finds the branch: `git checkout -B {branch}
    origin/{branch}` and go on below from the step not done yet. Else: `git
    checkout -B {branch}`, unzip -o into the repo root (it {touched}), one
    plan-only sub-agent makes a single commit {message} listing those files
    in its body, `git push -u origin {branch}`, and `gh pr create --base
    main --head {branch} --title {title} --body {body}`. Then wait for its
    checks: `hands ci-wait <pr>; echo "ci-wait-exit=$?"`, one foreground
    call at a time, again while it exits 3, at most seven calls. When it
    exits 0: `gh pr merge <pr> --merge --delete-branch --subject {subject}`,
    then `git checkout main && git pull --ff-only`, and reply with one line:
    VERDICT: kit applied <sha>, the merge commit's sha. If it exits 1 or 2,
    if the seventh call still exits 3, or if the push, the pull request or
    the merge is refused: leave the pull request, if there is one, open,
    `git checkout main`, and reply with one line: VERDICT: kit not applied
    pr=<pr, or none> <why, in one line>. If `gh` or `git` cannot answer one
    of the questions above, reply with one line: VERDICT: kit not applied
    pr=none <its error, in one line>. Change nothing else.

- `{branch}` is `kit/<stem>-<hash>`: `<stem>` the kit's file name without
  `.zip`, each character outside `A-Z a-z 0-9 _ -` replaced by `-` (a dot
  too, so the branch is always a valid ref name), cut to 40 characters;
  `<hash>` the first 12 hexadecimal digits of the zip's sha256. Two kits of
  one name never share a branch, and the same bytes sent again find their
  own pull request, merged or open, or their own branch.
- `{body}` is `Kit <file name> (sha256 <the whole digest>), applied by
  hands (DESIGN §45): it {touched}.`, shell-quoted.
- `{subject}` is `merge: kit <stem> (PR #<pr>)`, `<stem>` as in `{branch}`,
  shell-quoted, with `<pr>` left for the builder to fill.
- `hands kit check` prints the kit's sha256 — of the zip, or, for a
  directory kit, of the zip `hands kit file` builds from it (`build_zip`:
  the same bytes for the same files on the machine that files it) — and
  the prompt of the shape the project's configuration gives when it knows
  the project, else the `direct` one, saying which.
- A mission in flight is the branch case (b): a decisions kit sent while a
  mission's builder asked a question lands on the mission's branch, as it
  does today, and reaches `main` with the mission's pull request — a branch
  U0 has pushed with no commit of its own yet included. A branch that was
  never pushed, a branch whose pull request has merged (a finished
  mission's, left checked out) or was closed (an abandoned one), and another
  kit's are left for `main` (c).
- **A resume of an apply** — after a restart (`builder.orphaned`), a
  failure (`builder.failed`) or a usage limit (§6) — re-sends the apply's
  own prompt, never `[roles.builder] resume_line`, and is an apply as §43
  counts one (a job with a `kit_id`, or a resume of one, the chain followed
  back by `resumed_from`). The prompt above finds the kit's branch, its
  pull request open or merged, and goes on from there; it never starts a
  second pull request for the same bytes. §32's test of an apply the engine
  approved is asked of the chain's first job, so a resumed apply that lands
  is followed by the engine's kickoff as the first would have been.
- The gate's patterns (§8) are unchanged: the apply is filed held as
  today, and its prompt naming `gh pr create` changes nothing.

**A kit that carries the CI is the owner's.** Under the gate, a pull
request's check runs the workflow, and the gate script it calls, from the
pull request's own branch, so a kit that rewrote either could weaken the
check its own pull request is merged on. §43's hold extends to them: a
role-filed kit with an entry whose casefolded path begins `.github/` or
equals `scripts/check` (the gate every hands brief names) is not approved
by the engine; its apply is held for the human with the reason `apply
<name>: the kit carries <path>, the repository's CI; a change of the CI is
the owner's (§45)` — or §43's playbook reason when it carries the playbook
too — and `hands kit check` prints a `WARN ci:` line for any kit that
carries one. In a mission, a unit commit that changes a file under
`.github/` or `scripts/check` that no unit of the brief names is a blocker
for the review (below).

**An apply that did not land (H-080).** An apply's end goes to the
playbook's rules like any `builder.done`. When it did not land, this
repository's catch-all `^VERDICT:` consults the driver about a "question"
that is not one, and the templates' last rule stops with "Builder finished
without a recognised verdict", which says nothing of the kit; and under a
human pause, §44 rule 1 keeps that end as the builder's, replacing the kept
end of the mission it was sent beside. Under the gate the case becomes
ordinary (a red check, a refused push or merge). The rule, for both shapes:
the `builder.done` of an apply as §43 counts one (above) whose reply does
not begin `VERDICT: kit applied` is the engine's to decide, before any
playbook rule. On an unpaused pipeline it stops it: `the kit's apply did
not land: <its VERDICT: line cut to 200 characters, or "no VERDICT:
line"> (§45)`, titled as every engine stop is, with a row of its own in the
operator table. Over a pipeline already paused it does not stop it again:
it publishes that reason once — under a human pause as §44 rule 2's `hands:
a stop under a human pause`, under any other pause titled as a stop — and
the pause, its reason and any kept ends stay. It is the engine's own, like
the limit manager's stop: never kept, and it never replaces a kept end. An
apply that landed is decided as today: the playbook's `kit applied` rule,
or the engine's kickoff after an apply it approved (§31; kept under a human
pause, §44 rule 1).

**The journal under a `main` that takes pull requests only.** A commit
made on `main` and never pushed would break every later `git pull
--ff-only` once `origin/main` moves without it, so under `pull-request` the
consultation's line is committed only on a branch. hands' sentence (§39,
put before a cli send or an `answer` to the builder while
`meta/journal.md` is dirty) reads, word for word, under `pull-request`:

    [hands: meta/journal.md is uncommitted in your working tree (`git
    status --porcelain` shows it): on a branch other than `main`, commit it
    first, on its own, as `journal: <consultation>`; this repository's
    `main` takes pull requests only, so on `main` leave it uncommitted for
    the next mission's branch. Then do what follows.]

(one line in the prompt; wrapped here). Under `direct` it is unchanged, and
§36's reader recognises both. The brief template's §R gains the same rule
for the kickoff, which hands' sentence never precedes: a dirty
`meta/journal.md` at the start is committed, on its own, as `journal:
consultation lines` on the mission's branch — on `main`, after U0 has
created or checked out that branch — and never pushed to `main` unless the
brief's Branch section says Direct.

A dirty `meta/journal.md` also stops `git checkout` of a branch whose
journal differs from `main`'s — a closer's open branch, or the review's
checkout of the mission's branch — since every unit appended to it there.
So the template's Branch section (a closer's `git checkout <branch> && git
merge main`) and the review protocol (its `git checkout <branch>`) carry
the lines over first: the lines `git diff -U0 -- meta/journal.md` adds are
kept, `git checkout -- meta/journal.md` restores the file, the branch is
checked out, the kept lines are appended to its `meta/journal.md`, and they
are committed, on their own, as `journal: consultation lines`. When the file
is untracked on `main` (a project's first consultation created it), its
whole content is the kept lines and it is removed before the checkout. A
new branch made from `main` needs none of it: its journal is `main`'s.

**The review (the review protocol, the template and this repository's
copy).** The protocol's first step, before it reads the brief, reads once
whether `main` takes pull requests only, from GitHub, not from hands: `gh
api repos/<owner>/<repo>/rules/branches/main --jq '[.[].type] | join(" ")'`
names `pull_request` when it does. If the read fails, it is tried once more
a minute later; if that fails too, the review goes no further: one blocker,
"`main`'s rules could not be read: <the error>", the review file committed
to the mission's branch when it exists (a push to a branch is never refused
by the gate) and otherwise nowhere, and the reply carries the blocker.
- Without `pull_request`, the review is committed as today: to `main`,
  before any merge.
- With it:
  - a brief that says "Direct" is a blocker, "a direct mission on a `main`
    that takes pull requests only", and the review goes no further; with no
    open pull request for the brief's branch, the `reviewed: none` review is
    committed nowhere (`main` refuses it, and the branch may not exist), and
    the reply carries its blocker;
  - before writing, the reviewer waits for the pull request's checks at the
    reviewed tip (`hands ci-wait <number>`, as the merge below does): an
    end other than exit 0 is a blocker (a failed gate, or a gate not shown
    green), and the command's last line goes in `## Notes`;
  - the review file and the hosted review's archive are committed to the
    mission's branch, never to `main`: `git checkout <branch> && git pull
    --ff-only`, the archive copied in, one commit `review: mission N`,
    pushed to the branch, before any merge. A clean review lands on `main`
    with the merge; a review with blockers stays on the open branch, which
    the closer continues, so the closer's review finds it there;
  - the merge, with `blockers=0`: the review's own commit has started the
    checks again, so the reviewer first waits for them — `hands ci-wait
    <number>; echo "ci-wait-exit=$?"`, one foreground call at a time, again
    while it exits 3, at most seven calls — and merges only on exit 0, as
    today (`gh pr merge <number> --merge --subject "merge: mission N (PR
    #<number>)"`, then `git checkout main && git pull --ff-only`). On any
    other end it does not merge: it adds a blocker to `REVIEW-N.md`, `the
    merge was not made: <the command's last line>`, commits it to the
    branch as `review: mission N (not merged)`, pushes, and replies with
    that blocker counted. A clean verdict always means a merged mission;
  - with blockers, the reviewer returns the tree to `main` (`git checkout
    main && git pull --ff-only`), so the next kit's apply runs on `main`.
- With or without it, a unit commit that changes a file under `.github/`
  or `scripts/check` which no unit of the brief names is a blocker (read
  with `git show --stat`, like a forbidden edit).

**The brief template and the architect.** The template's Direct paragraph
says that a repository whose `main` takes pull requests only never takes
that shape, and its §R says the journal rule above. Its last unit carries a
sentence the architect keeps on such a repository: after the hosted
review's fixes are pushed, the unit waits for the pull request's checks
(`hands ci-wait <pr>`, as above) and fixes a failed check within the design
as it fixes a hosted finding, before the `## Hosted review` table; the
final report names each awaited check and its result. For the architect,
phone or role, on a repository whose `main` takes pull requests only:
- A kit must leave the gate green, because its apply merges only on green
  checks and nothing bypasses the gate. Where the architect can run the
  gate (the phone architect's sandbox), it runs it on the kit applied to a
  clone before sending it. A kit never rewords design text a test pins: the
  new wording is written in the kit's own section, and the mission's units
  move the code, its copies and the pinning tests to it. A kit carries no
  file under `.github/` and no `scripts/check` unless the human asked for
  it (it is held for the human, above).
- A review with blockers is on the mission's branch. The architect role's
  clone is whole and fetched before every job (§36), so its rule 1 in
  `architect/CLAUDE.md` gives `git show
  origin/<branch>:meta/reviews/REVIEW-N.md`, for such a repository only (on
  any other, the review is on `main` as today); its guard allows no other
  form of `git fetch`. The phone architect, from a shallow single-branch
  clone, runs `git fetch --depth 1 origin <branch>`, then `git show
  FETCH_HEAD:meta/reviews/REVIEW-N.md` (the handbook's §19 row).

**doctor's `main` row.** `hands doctor` prints one row, `main`: the setting,
and `main`'s effective rules read through `gh api
repos/<owner>/<repo>/rules/branches/main` (a GET; `<owner>/<repo>` from the
builder's clone's `origin`, a github.com URL in https or ssh form), each
rule type named. The row is ok when they agree: `direct` with none of the
rules below, or `pull-request` with `pull_request` and
`required_status_checks` (naming the required checks). It warns, never
fails, on:
- `direct` with a `pull_request` or `required_status_checks` rule — a
  direct push is refused, so applies stop and reviews go to branches: set
  `pull-request`;
- `pull-request` with no `pull_request` rule — `main` is not protected yet:
  docs/PR-CI-GATE.md;
- `pull-request` with `pull_request` and no `required_status_checks` —
  pull requests merge without CI, and `hands ci-wait` has no check to wait
  for, so every apply stops;
- either setting with `required_linear_history`, `update` or
  `merge_queue` — hands' merge commits and pull-request merges are refused
  or queued by it.
With no `gh`, no sign-in, an `origin` that is not on github.com, or a
failed read, the row is skipped, naming why; the `gh` row already warns
about `gh`.

**CI.** `.github/workflows/check.yml` runs `./scripts/check` on every pull
request and on every push to `main`, on GitHub's hosted Ubuntu runner, in
one job whose id and `name:` are both `check`, so the check it reports is
named `check`. Other than the triggers it holds: `permissions: contents:
read`; a `concurrency` group per ref that cancels a superseded run;
`timeout-minutes: 30`; `actions/checkout` and `astral-sh/setup-uv`, each
pinned to the full commit sha of its latest release with the version in a
comment. A test that fails only on the runner is made hermetic; a test that
needs what the runner lacks is skipped by a condition naming that lack
(never by a CI variable), named in the commit body and the final report;
and no test sends a request off the machine. An autouse fixture of the
suite sets `HTTPS_PROXY` and `HTTP_PROXY` to a port nothing listens on,
with `NO_PROXY` naming only `localhost` and `127.0.0.1`, so a request to any
other host fails at once in every run, on the laptop and on the runner; and
a test whose configuration leaves `ntfy_url` at its public default (the
doctor live tests among them) and means to publish is pointed at a local
stub. The check's reported name is read from a real run, never from the
YAML: docs/PR-CI-GATE.md step 3. The git user that pushes the workflow file
needs GitHub's `workflow` scope when it pushes over HTTPS with the `gh`
token (`gh auth status` lists the scopes; `gh auth refresh -s workflow`
adds it); docs/INTEGRATION.md's `gh` paragraph says so.

**docs/PR-CI-GATE.md.** The ruleset template proven on another repository
in October 2026 (rules, defaults, the procedure and its pitfalls), carried
into this repository whole by this section's kit with two additions: the
hosted reviewer's check, if it reports one, is never required (its verdict
is read by the review, not by the gate, and a reviewer that is slow or down
would block every merge); and a section for hands that gives the order a
project switches in, with no job of the project running, queued or held
(`hands jobs`; an apply filed before the switch keeps the prompt it was
filed with):
1. the CI workflow on `main`, its check green on a pull request;
2. `[repository] main = "pull-request"` and a restart of the project's
   `handsd` (doctor's row then warns that `main` is not protected yet);
3. the procedure, requiring the CI workflow's check only (doctor's row is
   then ok).
Undoing it is the owner's: the ruleset disabled in GitHub's settings, then
the setting set back to `direct` and the daemon restarted, with no apply in
between (the setting still `pull-request` and no rule to wait for, an apply
would stop).

**This repository, and the other project.** Mission 29 runs as missions
have run: its kit's apply commits to `main`, its review commits to `main`
and merges mission 29's pull request — the gate does not exist yet, and the
review that runs is the protocol on `main` when it starts. That pull request
is the first whose CI runs, and its last unit waits for the `check` check by
name (`hands ci-wait <pr> --check check`, no rules existing yet) and makes
it green. After its install, with no job running, queued or held: the human
sets `main = "pull-request"` for this repository and restarts
`handsd@hands`; the aux runs docs/PR-CI-GATE.md for `SigorMatt/hands`,
requiring the `check` check only, from the check runs the merge's push to
`main` reported. The next kit's apply is the first through a pull request,
and mission 30 is the first mission whose review commits to its branch and
merges on green checks. The other project, whose missions commit straight
to `main` and which has no CI, switches at a later quiet moment of its own,
after mission 28's pause has been tested there, in the same order (its CI,
then its missions in the pull-request shape and its review protocol from the
installed template, then the setting, then the procedure), so that a
failure in either is attributable to one change. Until then it is on
`direct`, and of this release only these reach it: an apply that did not
land stops with its reason (H-080), a resumed apply re-sends its own prompt
and is followed by the engine's kickoff when it lands, a role-filed kit
that carries `.github/` or `scripts/check` waits for the human, and the
`direct` apply prompt's added sentence.

**Documentation.** The handbook: §3 (the apply's two prompts; the kit's
branch; a kit that keeps its gate green; a kit that carries `.github/` or
`scripts/check`),
§9 (a `main` that takes pull requests only: what moves `main`, the review
on the branch, the waits, the journal), §10 (the stop for an apply that did
not land), §12 (a project switching, the order), §18 (`hands ci-wait`), §19
(the row for the apply that did not land: the project's chat's, route 3 —
read the pull request's checks; a flaky check re-run and, once green, the
pull request merged and `go` sent; a kit that breaks the gate closed and
corrected; the review-with-blockers row saying where the review is on such
a repository, both `git show` forms; the CI hold in the hold row). docs/INTEGRATION.md (the
`[repository]` key in step 3, the `workflow` scope, doctor's `main` row).
docs/OPERATIONS.md (a runbook, "Switching `main` to pull requests only",
and "A quiet moment" step 3: under `pull-request` a commit at rest is a
decisions kit, whose apply goes through its own pull request).
docs/PLAYBOOK.md (the engine's stop for an apply that did not land).
`templates/config.toml` (the key, commented, with its default). This
repository's `CLAUDE.md` (`main` moves by merges, and by plan and review
commits only while the setting is `direct`; branch protection follows
docs/PR-CI-GATE.md). `architect/CLAUDE.md` rules 1 and 3, so the install
refreshes the architect's `CLAUDE.md`. `docs/ARCHITECT-INSTRUCTION.md`
does not change: no instruction paste is due.

**Not changed.** The engine's rules beyond an apply's end; the kickoff;
§35's mission shape (a branch per mission, the review merging a clean
one); the gate's patterns; the driver and architect guards; how a
consultation is started. hands never creates, edits or reads back a
ruleset by any call but doctor's and `ci-wait`'s GETs: the gate is the
human's, made by the aux from docs/PR-CI-GATE.md.

**The gate of the mission (after its install; the human's and the aux's).**
The setting and the ruleset for this repository, doctor's `main` row ok,
`current_user_can_bypass: never`; then kit 30's apply through a pull
request merged on green checks, and mission 30's review committed to its
branch and its merge made on green checks — read back from the branch and
the pull requests. Declared met from the branch, never from memory.
