# CHECKPOINT

Mission: 1 (meta/BUILDER-1-PROMPT.md)
Unit in progress: U4 Files and gates
Intent: the human-decision boundary. Files move only inside the allowed
roots; gated work waits in `held` until a human decision releases it, and
nothing else can release it.
Done means:
  - `hands put/get/ls` confined to `files.allowed_roots` (reuse
    `spool.resolve_under_roots`), sha256 and bytes reported per §4.
  - `--file path=content` on `send`, written before spawn, recorded in
    `files_written`.
  - Gate triggers: `--gate reason` or `gates.patterns` (case-sensitive
    substring match on the prompt) put the job in `held`; U3's temporary
    refusal of pattern-matching prompts is replaced by real gating.
  - `cancel` gated per `roles.<role>.cancel_gated`.
  - `approve`/`deny` with the authority table of DESIGN §8: the CLI
    decision is final (`decided_by: cli`); `--human-confirmed` (the driver
    path) requires `--quote "<the human's instruction>"` and stores it
    (`decided_by: driver`); a `held` job cannot be released any other way;
    `denied` is terminal; gating on the default patterns cannot be
    disabled.
  - Table-driven tests for the authority table and for confinement.
  - `./scripts/check` green; one commit; pushed.
Standing constraints: execution model of BUILDER-1-PROMPT.md is binding;
one sub-agent per unit; commit and push every unit; ./scripts/check green;
no test may require a real `claude` binary; sub-agents never edit
meta/plan.md, meta/CHECKPOINT.md or DESIGN.md; design changes and product
facts that contradict the design are findings in meta/findings/FINDINGS.md
with evidence.
