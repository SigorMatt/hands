# CHECKPOINT

Mission: 1 (meta/BUILDER-1-PROMPT.md)
Unit in progress: U9 Job library
Intent: DESIGN §7 — the spool is the session library; searching prompts
is searching work items. Make the finished work findable and re-openable
without ever resuming a live session.
Done means:
  - `hands jobs [--role r] [--grep pat] [--since d] [-n]` filtering over
    the spool.
  - `hands show <job>` (the full record).
  - `hands open <job>`: execs `claude --resume <session_id>` in
    `roles.<role>.cwd`; refused while the job is `running` (§2: never
    resume a session whose job is still running).
  - `hands log <job>` (the captured stream file) and `hands log -f <role>`
    (streams the running job's events live).
  - `hands tail --role r -n` if it falls out cheaply (§4); if it does not,
    say so rather than half-doing it.
  - Tests for filtering, the refusal, and streaming.
  - `./scripts/check` green; one commit; pushed.
Standing constraints: execution model of BUILDER-1-PROMPT.md is binding;
one sub-agent per unit; commit and push every unit; ./scripts/check green;
no test may require a real `claude` binary or exec one; sub-agents never
edit meta/plan.md, meta/CHECKPOINT.md or DESIGN.md; design changes and
product facts that contradict the design are findings in
meta/findings/FINDINGS.md with evidence.
