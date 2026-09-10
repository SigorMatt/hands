# CHECKPOINT

Mission: 1 (meta/BUILDER-1-PROMPT.md)
Unit in progress: U2 Fake claude and runner
Intent: the first unit that spawns a process. A fake `claude` under test
control, and the runner of DESIGN §2 that drives it and fills the job
record of §6.
Done means:
  - `tests/fake_claude.py`: executable, imitates
    `claude -p --output-format stream-json --verbose`, emits system/init
    with a session_id, honours `--resume <id>`, reads the prompt on stdin,
    and per a control string in the prompt can emit a given result, sleep,
    emit a rate-limit error event then exit, or block until SIGINT/SIGTERM
    (143 on TERM, 130 on INT).
  - `src/hands/runner.py`: spawns the §2 per-role invocation with the
    `claude` binary from config, parses stream-json line by line, records
    session_id, transcript_path, head_at_start/head_at_end, the verbatim
    result, verdict, stderr_tail, permission_denials, num_turns,
    duration_ms, total_cost_usd, exit_code. Cancel = SIGINT, wait
    cancel_grace_s, then SIGTERM.
  - Tests: clear, keep, keep refused (no session; session's last job not
    terminal), verbatim result, verdict extraction, limited detection,
    killed, and a job whose pid is gone at daemon start becoming orphaned.
  - `./scripts/check` green; one commit; pushed.
Standing constraints: execution model of BUILDER-1-PROMPT.md is binding;
one sub-agent per unit; commit and push every unit; ./scripts/check green;
no test may require a real `claude` binary; sub-agents never edit
meta/plan.md, meta/CHECKPOINT.md or DESIGN.md; design changes and product
facts that contradict the design are findings in meta/findings/FINDINGS.md
with evidence.
