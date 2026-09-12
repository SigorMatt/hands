# hands — DESIGN v3.4

Machinery that replaces the human relay between the planning brain and the two
Claude Code roles (builder, aux) on the Ubuntu laptop, and that keeps a series
moving without a human while everything goes by plan. Working name: `hands`.
The method it serves is described in WORKING-MODEL.md (agile-skills) and
OPERATING-MODEL.md (spanweave); hands changes the topology, not the method.
v3.4 (2026-09-12) folds in the mission 4 review; changes are in §21;
earlier changes in §20, §19, §18, §17.

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
| `send` | `--role builder\|aux --context clear\|keep [--file path=content…] [--gate reason] [--prompt-file path\|--stdin\|prompt]` | job id, state. `--prompt-file` is the normal route for prose: the prompt never touches a command line; the client refuses a missing, unreadable, non-regular, empty or over-10 MB file on either route (`--prompt-file` or `--stdin`), and the wire carries UTF-8 unescaped so the daemon's line room (cap plus one quarter) fits any accepted prompt; exit 2 means "the client did not deliver a completed request" (a refusal or a timeout) |
| `wait` | `<job>\|--for event-kind [--timeout s]` | job record when terminal / the event; used by the driver in the background (§11) |
| `result` | `<job>` | job record |
| `jobs` | `[--role r] [--origin o] [--grep pat] [--since d] [-n]` | recent job summaries |
| `show` / `open` / `log` | `<job>` / `<job>` / `<job>\|-f <role>` | record / `claude --resume` (refused while running) / captured stream |
| `cancel` | `<job> --reason` | held for human unless `role.cancel_gated: false` |
| `put` / `get` / `ls` | path, content or `--from file` / path / path | sha256 and bytes / content / entries — confined to allowed roots |
| `tail` | `--role r -n` | last n transcript entries of the role's current or last session |
| `inbox` | `[--ack]` | unread events, verbatim (§11) |
| `pipeline` | — | active playbook (path, sha256, series), paused?, auto-runs used/allowed, resumes used, last rule fired, current stop reason |
| `approve` / `deny` | `<job> [--reason]` | per §8; from the driver only with `--human-confirmed` |
| `pause` / `resume` | — | pause/unpause the playbook engine |
| `status` | — | daemon, roles, running jobs, monitor state (`queue_depth` is capacity; `queued` is contents) |
| `notify` | `--test "<message>"` | sends one ntfy message to the configured topic; the first real proof of delivery |
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

    id, role, context, created, started, ended, origin (driver|playbook|cli|limit)
    prompt, files_written, session_id, transcript_path, pid, exit_code
    head_at_start, head_at_end
    result            # the `result` field of the final message, untouched
    verdict           # the first line of result matching ^VERDICT: (or null)
    stderr_tail       # last 50 lines
    permission_denials, num_turns, duration_ms, total_cost_usd
    limit             # {category, message, reset_at} when state == limited
    gate              # {reason, decided_by: cli|driver|button, decided_at}
    resumed_from      # job id, when this job is an auto-resume

Rules:
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
starts and records its sha256 in every job it fires. Deleted at series close
with `WORKPLAN.md`.

### Events

`builder.done`, `builder.failed`, `builder.limited`, `builder.orphaned`,
`aux.done`, `aux.failed`, `monitor.stall`, `monitor.tripwire`, `job.held`,
`job.denied`.

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
    quiet_hours = "23:00-07:00"   # notifications delayed, actions not

    [[rule]]                  # run finished cleanly → cold review
    on = "builder.done"
    verdict = '^VERDICT: run (?P<n>\d+) finished'
    then = "send"
    role = "aux"
    context = "clear"
    prompt = "Review WORKPLAN.md commits since {job.head_at_start}"

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

**Wake-up — the driver is not a poller.** After dispatching or after
reporting to you, the driver runs `hands wait --for stop,held` as a Claude
Code *background* Bash task and goes idle. When hands emits such an event,
the command returns, Claude Code delivers the background result to the
driver session, and the driver acts: reads the inbox, verifies, reports,
re-arms the wait. While the playbook is chaining runs, nothing wakes the
driver and nothing needs to. `hands doctor` prints the procedure for this check (a gated send, which
files a real `job.held` without spending a turn, or `hands pause`, which
files a `stop` event with reason `paused by human`; H-007) and the driver
session confirming it woke;

Observed 2026-09-12 on Claude Code 2.1.268: the harness kills idle
background tasks intermittently (a control `sleep 3600` died alongside the
wait, with 70% of memory free; the "low memory" text it prints does not
describe the machine). Each kill wakes the session for one recovery turn.
So the wait is armed only while a job is running or queued; when the
pipeline is idle or stopped, nothing is armed and the human's next message,
prompted by the ntfy notification, is the wake.
if background completion does not wake an idle session on your Claude Code
version, the fallback is a `hands wait` with a long timeout re-issued by the
driver, or you opening the Code tab after the ntfy notification.

**Notifications** (ntfy, in scope — it is how you learn you are needed):
`stop`, `job.held`, `max_resumes` exhausted, daemon start/crash. Not for
routine progress. `quiet_hours` delays them; actions are never delayed.
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
  8. After every dispatch or report, re-arm `hands wait --for stop,held` in
     the background and stop talking.
  9. Reports to the human start with a `VERDICT:` line; deviations are
     flagged, not acted on; retract on contradicting evidence.
  10. Design changes, new batches, playbook edits and decisions files are not
      yours to write; say "this is for the architect" and stop.
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
