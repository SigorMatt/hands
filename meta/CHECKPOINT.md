# CHECKPOINT

Mission: 1 (meta/BUILDER-1-PROMPT.md)
Unit in progress: U3 Daemon, local API, CLI
Intent: make hands usable end to end — the daemon that owns the roles and
the queue, the local JSON-RPC surface of DESIGN §4, and the thin CLI that
the driver actually types.
Done means:
  - `src/hands/daemon.py`: asyncio, unix socket at `server.socket`,
    newline-delimited JSON-RPC 2.0, one running job per role, FIFO queue
    with `queue_depth`, orphan reconciliation at startup, graceful
    shutdown. `handsd --project <name>` entry point.
  - `src/hands/api.py`: a method for every command in §4 (methods that
    belong to later units may return a documented "not implemented yet"
    error, but the method names and shapes must be the ones the MCP face
    of §9 would wrap).
  - `src/hands/cli.py`: `hands <command>` as a thin client with `--json`
    and a readable form; `hands status`.
  - The daemon persists each job's captured stream so `hands log` (U9)
    has something to read.
  - End-to-end test in `tmp_home`: daemon against `fake_claude`,
    `hands send --role builder --context clear`, `hands wait`,
    `hands result` shows the verbatim result; a second `send` to the busy
    role queues; the aux queue accepts 4.
  - `./scripts/check` green; one commit; pushed.
Standing constraints: execution model of BUILDER-1-PROMPT.md is binding;
one sub-agent per unit; commit and push every unit; ./scripts/check green;
no test may require a real `claude` binary; sub-agents never edit
meta/plan.md, meta/CHECKPOINT.md or DESIGN.md; design changes and product
facts that contradict the design are findings in meta/findings/FINDINGS.md
with evidence.
