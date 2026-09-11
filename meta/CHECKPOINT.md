# CHECKPOINT

Mission: 1 (meta/BUILDER-1-PROMPT.md)
Unit in progress: U6 Monitor bridge
Intent: DESIGN §5 — every builder job is watched from outside the
process, one report per event, never an intervention. The ops repo's
script is the real monitor; the built-in stall detector is the fallback
when no script is configured.
Done means:
  - For every builder job, if `ops.monitor_cmd` is set, run
    `<ops.repo>/<monitor_cmd> --pids <pid list> --transcript <path>
    --base <head_at_start>` and file each blank-line-separated stdout
    block to the inbox as `monitor.<kind>`, `<kind>` = the block's first
    word lower-cased (`stall`, `tripwire`, else `event`). Blocks are
    filed verbatim.
  - If unset, run the built-in liveness/stall monitor of §5 (transcript
    mtime, `subagents/` dir mtime, process CPU ticks): no progress and no
    liveness for `monitor.stall_minutes` → one `monitor.stall` event,
    re-firing only after another interval.
  - Tripwires are external-only in this mission.
  - The monitor stops when the job ends.
  - Tests with a fake monitor script and with the built-in monitor at
    `stall_minutes = 0.01`.
  - `./scripts/check` green; one commit; pushed.
Standing constraints: execution model of BUILDER-1-PROMPT.md is binding;
one sub-agent per unit; commit and push every unit; ./scripts/check green;
no test may require a real `claude` binary and no test may wait a real
stall interval; sub-agents never edit meta/plan.md, meta/CHECKPOINT.md or
DESIGN.md; design changes and product facts that contradict the design
are findings in meta/findings/FINDINGS.md with evidence.
