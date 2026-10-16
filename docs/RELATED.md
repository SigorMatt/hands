# RELATED — other orchestrators, read against hands

One section per project the architect has read, so the roadmap can cite it
instead of re-reading it. Each section names the clone commit and the files
read; the code is not reviewed unless the section says so. Nothing here is a
decision; decisions live in DESIGN.md and the plan files.

## Gas Town (read 2026-10-16)

Source: a shallow clone of `github.com/gastownhall/gastown` at `649b832`
(2026-07-23; CHANGELOG head v1.2.1, 2026-06-06): README.md,
docs/overview.md, docs/why-these-features.md,
docs/concepts/propulsion-principle.md, docs/concepts/polecat-lifecycle.md,
docs/design/sandboxed-polecat-execution.md,
docs/agent-provider-integration.md, docs/reference.md (ACP section),
internal/config/agents.go and internal/acp/.

### What Gas Town claims to be

A workspace manager that keeps many interactive coding-agent sessions
(README: "scale comfortably to 20–30 agents") alive at once across many
repositories, and treats every action they take as structured data. Its stated
problem is enterprise visibility — "who did what, who's reliable, who can do
this, what's connected" (docs/why-these-features.md) — so its centre is a
work ledger (Beads issues stored in Dolt), an identity with a work history per
agent, and a hierarchy of AI roles supervising other AI roles: the Mayor
(coordinator and entry point — "just tell the Mayor"), a Witness per rig, a
Deacon patrolling across rigs, Dogs for chores, Boot for triage, a Refinery
that merges as a Bors-style queue, Polecats as workers. Escalations route
Deacon → Mayor → Overseer; the Overseer is the human and the last tier
(docs/design/escalation.md). Around that: a web dashboard, a TUI feed,
OpenTelemetry, and a federation network with reputation stamps (Wasteland).

The mechanism underneath is tmux. Agents run as interactive REPLs in panes;
work is dispatched by `send-keys` and read back by `capture-pane`, which the
provider guide itself calls "timing-sensitive and has no delivery
confirmation" (docs/agent-provider-integration.md, Tier 0). Persistence is a
git worktree per agent ("hooks") plus the ledger; context recovery is
`gt prime`, handoff, and "seance" over `.events.jsonl` logs. The sandbox
design of 2026-03-02 (docs/design/sandboxed-polecat-execution.md, status
Proposal) states that every polecat runs on the host under the user's UID with
full filesystem, network and credential access, and proposes exitbox/daytona
backends to change that. Go, ~1,200 source files, a 254-line go.mod; Dolt,
Beads and tmux are hard requirements of a native install.

### Where hands differs

The same four words, opposite choices.

- **Who supervises.** Gas Town supervises agents with agents and reaches the
  human last, by severity. hands has no AI supervisor: the playbook is a
  finite rule table over typed events (DESIGN §10, §28), every stop that
  needs judgement pauses the pipeline, and the human answers from the phone.
  The architect role is the one layer of AI about AI, and it is gated (§31)
  and consult-budgeted (§27).
- **Sessions.** Gas Town is built on long-lived interactive sessions kept
  warm in tmux, with handoff and seance to recover their context. hands runs
  headless one-shot jobs behind a guard hook, with a VERDICT line as the only
  output contract and `meta/CHECKPOINT.md` as the only memory; context is
  dropped on purpose (`--context clear`, fresh-context sub-agents in the
  review protocol). The failure mode Gas Town's propulsion principle exists
  to prevent — "polecat waits for confirmation, nothing happens" — is what
  hands' stop/apply/go cycle is.
- **Truth.** Gas Town's truth is the ledger database; the repository is one
  store among several. hands' truth is the branch: the plan files, the review
  file, the journal, the kit, the `plan:` commits. Nothing exists unless it is
  on disk in git (architect rule 6).
- **Scale and surface.** Twenty to thirty concurrent agents, many rigs, a
  dashboard, federation, telemetry. hands: one builder per project at a time,
  a reviewer, a phone, ntfy over Tailscale, a mode-600 secret file. hands'
  isolation (guard read roots, `python3 -I` hooks, the command secret, the
  held kit apply) is the thing Gas Town's sandbox document lists as a
  proposal.
- **Merge.** The Refinery merges automatically once gates pass; the human is
  not in the loop. In hands the cold review merges only a clean pull request
  (§35) and the human decides every design change.

Gas Town is a factory with AI foremen and the human as an escalation tier;
hands is a workbench with one bench-hand per project, a cold reviewer, and the
human as the only foreman, reachable by phone. They do not compete on one
axis, and nothing in Gas Town argues against hands' shape: its sandbox
proposal and its tmux caveat are two of hands' founding decisions written
down by the other side.

### What hands takes from it (M8a)

1. **The provider table.** `internal/config/agents.go` carries presets for
   claude, gemini, codex, kiro, cursor, auggie, amp, opencode, copilot, pi and
   omp — the launch command, the resume flags, hooks or no hooks per CLI —
   and docs/reference.md documents an "ACP-enabled custom agents" path
   (`opencode acp`) served by a proxy in `internal/acp/`. That is a maintained
   inventory of the four facts the M8a probe needs per harness (headless
   one-shot launch, session resume, a readable event stream, an enforceable
   permission mode). The probe brief cites it as a source to check against the
   laptop; nothing is imported.
2. **The integration ladder.** docs/agent-provider-integration.md's four
   tiers — zero (any terminal CLI), preset (launch and resume flags), hooks
   (context injection and tool guards), deep (non-interactive mode, session
   forking, a wrapper) — is a clean vocabulary for the backend seam's levels.
   hands' M8 requirements are their Tier 3; a harness that only reaches Tier
   1 cannot host a hands role.

## Conductor (read 2026-10-16)

Source: a shallow clone of `github.com/conductor-oss/conductor` at `c52919a`
(2026-10-12): README.md, ROADMAP.md, docs/architecture/durable-execution.md,
docs/devguide/ai/dynamic-workflows.md, conductor-agents.md,
human-in-the-loop.md, conductor-for-ai-assistants.md,
docs/documentation/api/agents.md.

### What Conductor claims to be

Netflix Conductor continued under Orkes: a durable execution engine. A
workflow is a versioned JSON graph of tasks; the server persists every step
(the definition snapshot, the workflow state, every task's input, output,
retries and worker id) to Redis, PostgreSQL, MySQL or Cassandra before the
next step runs; workers in any language poll queues, execute and report; the
control plane offers inspect, retry, pause, resume, terminate and rerun.
Delivery is at least once, so every side effect must be idempotent
(docs/architecture/durable-execution.md). The 2026 positioning is "durable
execution for workflows and agents": native `LLM_CHAT_COMPLETE`,
`CALL_MCP_TOOL` and vector tasks; a `HUMAN` task as a durable pause ("whether
the reviewer responds in 5 seconds or 5 days, execution resumes exactly where
it left off", docs/devguide/ai/human-in-the-loop.md); `DO_WHILE` agent loops
with iteration caps; "durable adaptive graphs" (plan → validate against an
allowlist → bounded fan-out → approval before writes → evaluate); and a
compiler that turns LangGraph, ADK or OpenAI-Agents code into a Conductor
graph so each LLM call is a visible task. Its flagship example is a governed
pull-request reviewer that gathers evidence in four persisted passes and asks
a human before posting one comment (docs/devguide/ai/dynamic-workflows.md).
Its page for AI assistants lists seven safe-authoring rules; the sixth is
"require approval before consequential writes". Java 21, a persistence
store and a broker are the floor of an install.

### Where hands differs

Not an opposite, as Gas Town is; a different layer, and in places hands'
own ideas in enterprise vocabulary.

- **What is orchestrated.** Conductor's unit is a function call or an LLM
  call; the agent is decomposed into graph nodes the engine owns. hands' unit
  is a whole coding-agent session, opaque, with one output contract (the
  VERDICT line); hands never sees inside a turn. Conductor's graph of an
  agent is the harness's business in hands' model.
- **Where state lives.** Conductor: a database, the engine the only writer,
  which is what makes retry and rerun exact. hands: the branch and
  `meta/CHECKPOINT.md`, the builder itself the writer, `--context clear` and
  §R recovery as the resume. Conductor's "execution pinned to its definition
  version" is hands' kit per mission; its "definition snapshot" is the
  `plan:` commit.
- **The human.** Conductor's `HUMAN` task is structurally hands' stop: the
  run halts with state preserved and resumes on an external signal. The
  difference is reach — Conductor exposes it as a REST update for a console;
  hands' is an ntfy button over a tailnet with a per-project secret (§8, §11,
  §38).
- **The playbook.** Conductor's graph is a complete DAG with runtime
  branching inside it. hands' playbook is a flat event→action table whose
  only runtime choice is the VERDICT vocabulary, and `auto_runs` lists only
  fully defined batches; everything else stops (§10). hands is deliberately
  the less expressive of the two.
- **The guard.** Conductor's safety is policy at the graph level: an
  allowlist of approved tools, bounded fan-out, iteration caps, approval
  before writes, a generated definition treated as untrusted. hands' guard is
  at the shell: a hook on every Bash call with a command table, read roots,
  `python3 -I` (§30, §32). Conductor trusts the worker process as code it
  does not inspect; hands treats the agent's process as the thing to contain.
- **Weight.** A JVM server, a database, a broker, a UI and seven SDKs, for a
  company's services. hands is one Python daemon per project on a laptop.
  Conductor's at-least-once-so-make-everything-idempotent is the price of its
  durability; hands pays with `max_resumes` and the checkpoint.

Conductor is a substrate on which a hands could be built — its governed
pull-request reviewer is the closest thing to a hands mission anyone else has
published — but it would be a hands whose unit is the LLM call, not the
session. hands keeps the session opaque because the harness already owns
the loop and the tool calls; what hands adds is the stop/apply/go cycle, the
cold review and the phone, which Conductor has no opinion about.

### What hands takes from it

1. **Vocabulary** for DESIGN §40 and the handbook: "durable pause",
   "execution pinned to its definition version", "bounded adaptive
   execution". Its seven safe-authoring rules are a compressed §8 and the
   guard's purpose; the sixth is the one-line reason the kit apply is held.
2. **The failure matrix** in docs/architecture/durable-execution.md (what
   persists at every step, what resumes after a restart, the consequences of
   at-least-once) is a template for the restart section mission 23 wrote in
   docs/INTEGRATION.md: hands should state the same table for itself (a
   daemon restart, a killed job, a stale checkpoint, a resume past
   `max_resumes`).
3. Nothing to integrate. The `agentspan` module is Conductor's AI runtime,
   unrelated to spanweave despite the name.
