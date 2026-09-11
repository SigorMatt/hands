# CHECKPOINT

Mission: 1 (meta/BUILDER-1-PROMPT.md)
Unit in progress: U7 Playbook engine
Intent: the reason hands exists — the architect's pre-planned steps run
without a human, and anything outside them stops the pipeline and calls
one. DESIGN §10 is the whole specification; read it twice.
Done means:
  - `src/hands/playbook.py` loads `<roles.builder.cwd>/<playbook.path>`
    when a job starts and records its sha256 on every job it fires.
  - Rules per §10: `on`, optional `verdict` regex with named groups,
    `then` in `send | resume | notify | stop`, placeholders `{name}`,
    `{name+k}` integer arithmetic, `{job.*}`, `only_if_run_in =
    "auto_runs"`.
  - Unmatched event, missing or unparseable verdict, exhausted limits →
    `stop`. `stop` pauses the engine, records the reason, writes the inbox
    event.
  - `hands pause` / `hands resume`; `hands pipeline` per §4 (path,
    sha256, series, paused?, auto-runs used/allowed, resumes used, last
    rule fired, current stop reason).
  - `origin = playbook` on fired jobs.
  - Table-driven tests including the §10 example playbook end to end
    against `fake_claude`: run finished -> review sent -> blockers=0 ->
    run 3 sent -> run 4 not in auto_runs -> stop.
  - `./scripts/check` green; one commit; pushed.
Standing constraints: execution model of BUILDER-1-PROMPT.md is binding;
one sub-agent per unit; commit and push every unit; ./scripts/check green;
no test may require a real `claude` binary; sub-agents never edit
meta/plan.md, meta/CHECKPOINT.md or DESIGN.md; design changes and product
facts that contradict the design are findings in meta/findings/FINDINGS.md
with evidence.
