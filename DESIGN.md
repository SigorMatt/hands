# hands — DESIGN v3.15

Machinery that replaces the human relay between the planning brain and the two
Claude Code roles (builder, aux) on the Ubuntu laptop, and that keeps a series
moving without a human while everything goes by plan. Working name: `hands`.
The method it serves is described in WORKING-MODEL.md (agile-skills) and
OPERATING-MODEL.md (spanweave); hands changes the topology, not the method.
v3.15 (2026-09-16) folds in the mission 15 review and finishes the guard's
language; changes are in §32; earlier changes in §31–§17.

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
    then = "stop"

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
     Prompts you compose yourself are short and go in quotes; the guard
     treats quoted text as text. You cannot create files, so never plan
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
      systemd/handsd.service         # user unit
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
- The example playbook maps `monitor.task_killed` and
  `monitor.orphan_processes` to `stop`.

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
ships as an optional user unit `handswho.service`, off unless enabled;
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
