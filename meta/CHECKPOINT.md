# CHECKPOINT

Mission: 1 (meta/BUILDER-1-PROMPT.md)
Unit in progress: U10 Install surface
Intent: everything a human needs to put hands on the laptop and trust it —
the systemd unit, `hands doctor`, the docs, and a driver kit that matches
the CLI that now exists.
Done means:
  - `systemd/handsd.service` (user unit, `--project` from an environment
    file).
  - `hands doctor` (DESIGN §4, §11, §14): claude binary and version; the
    ops script accepts `--pids`, `--transcript`, `--base`; allowed roots
    exist; a one-turn `claude -p` per role — skipped with a clear message
    when `HANDS_DOCTOR_FAKE=1` points at `tests/fake_claude.py`; and it
    prints the background-wake check procedure for the human to run from
    the driver session.
  - `docs/INTEGRATION.md` (DESIGN §14 steps as a checklist),
    `docs/PLAYBOOK.md` (rule reference + the §10 example), `README.md`
    (what hands is, install, first run).
  - `driver/` verified against the CLI surface that now exists; fix
    `driver/` where the CLI differs (driver/CLAUDE.md, settings.json,
    README.md).
  - Tests: `hands doctor` green in fake mode.
  - `./scripts/check` green; one commit; pushed.
Standing constraints: execution model of BUILDER-1-PROMPT.md is binding;
one sub-agent per unit; commit and push every unit; ./scripts/check green;
no test may call a real `claude`, spend quota, or touch the network;
sub-agents never edit meta/plan.md, meta/CHECKPOINT.md or DESIGN.md;
design changes and product facts that contradict the design are findings
in meta/findings/FINDINGS.md with evidence.
