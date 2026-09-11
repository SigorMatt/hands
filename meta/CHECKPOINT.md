# CHECKPOINT

Mission: 1 (meta/BUILDER-1-PROMPT.md)
Unit in progress: U5 Limits
Intent: the shared-subscription fact of DESIGN §6 — a limit is a
wall-clock event, so hands waits it out and resumes by itself rather than
asking a human who is limited too.
Done means:
  - Detect `limited` from a rate-limit error event or a limit notice in
    `result`; store the raw notice always (see finding H-002 on the field
    name).
  - Parse a reset time defensively: ISO timestamps; "resets at <time>"
    with and without a date; "try again in N minutes". When parseable,
    schedule the resume at that time + 60 s, else after
    `limits.backoff_minutes`.
  - Builder resume = `roles.builder.resume_line` as a new `clear` job with
    `resumed_from`; aux resume = the same prompt again.
  - Stop after `limits.max_resumes` consecutive resumes without a `done`,
    and notify (the inbox event now; ntfy in U8).
  - One inbox event per limit and per resume.
  - Tests for each notice shape, the counter, and the stop.
  - `./scripts/check` green; one commit; pushed.
Standing constraints: execution model of BUILDER-1-PROMPT.md is binding;
one sub-agent per unit; commit and push every unit; ./scripts/check green;
no test may require a real `claude` binary and no test may sleep for a
real limit interval; sub-agents never edit meta/plan.md,
meta/CHECKPOINT.md or DESIGN.md; design changes and product facts that
contradict the design are findings in meta/findings/FINDINGS.md with
evidence.
