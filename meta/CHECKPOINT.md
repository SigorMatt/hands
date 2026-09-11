# CHECKPOINT

Mission: 1 (meta/BUILDER-1-PROMPT.md)
Unit in progress: U8 Wake path and notifications
Intent: DESIGN §11 — the driver is not a poller. A background
`hands wait --for stop,held` returns when hands needs a human, and ntfy
tells the human when the driver cannot.
Done means:
  - `hands wait --for <kinds> [--timeout s]`: subscribe over the socket,
    return on the first inbox event of a listed kind; the event is
    returned, not acked.
  - `src/hands/notify.py`: ntfy publish over `httpx` for `stop`,
    `job.held`, `max_resumes` exhausted, daemon start/crash.
    `quiet_hours` delays delivery (a scheduler flushes at the window end)
    and never delays actions. Hourly heartbeat event while any job runs.
  - Tests: `wait` returns on the event and times out otherwise; quiet
    hours delay; ntfy mocked (no network in tests).
  - `./scripts/check` green; one commit; pushed.
Standing constraints: execution model of BUILDER-1-PROMPT.md is binding;
one sub-agent per unit; commit and push every unit; ./scripts/check green;
no test may make a network call, require a real `claude` binary, or wait a
real hour; sub-agents never edit meta/plan.md, meta/CHECKPOINT.md or
DESIGN.md; design changes and product facts that contradict the design are
findings in meta/findings/FINDINGS.md with evidence.
