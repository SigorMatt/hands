# CHECKPOINT

Mission: 1 (meta/BUILDER-1-PROMPT.md)
Unit in progress: U1 Config and spool
Intent: give every later unit its two foundations — the project config of
DESIGN §13 and the spool of §6/§7/§11 (job records, role state, inbox,
path confinement). No process is spawned in this unit.
Done means:
  - `src/hands/config.py` loads `~/.hands/<project>.toml` (§13), expands
    `~`, validates roles (builder, aux) and allowed roots, and supplies a
    default for every optional key.
  - `src/hands/spool.py`: job records as JSON files under `~/.hands/jobs/`,
    atomic writes (tmp + os.replace + fsync), the state machine of §6 with
    illegal transitions refused, `~/.hands/roles/<role>.json`
    (`last_session_id`, `last_job`), an append-only inbox with per-event
    ack, and `resolve_under_roots` rejecting `..`, absolute escapes and
    symlinks leaving the roots.
  - Tests for every transition (legal and illegal), an atomic write under
    a simulated crash, and confinement escapes.
  - `./scripts/check` green; one commit; pushed.
Standing constraints: execution model of BUILDER-1-PROMPT.md is binding;
one sub-agent per unit; commit and push every unit; ./scripts/check green;
sub-agents never edit meta/plan.md, meta/CHECKPOINT.md or DESIGN.md;
design changes are findings in meta/findings/FINDINGS.md.
