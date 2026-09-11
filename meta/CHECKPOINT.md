# CHECKPOINT

Mission: 2 (meta/BUILDER-2-PROMPT.md) — IN PROGRESS
Unit in progress: U3 Explicit `run` key (H-006, DESIGN §10)
Intent: replace `only_if_run_in` with an explicit `run = "<expr>"` key on a
send rule, checked when the playbook is loaded; refuse `only_if_run_in` at
load with a message naming `run`; update tests/fixtures/playbook_example.toml
to DESIGN §10's rewritten example and docs/PLAYBOOK.md.
Done means: table-driven load-time tests (no auto_runs; a group the verdict
does not define; `only_if_run_in` refused), the §10 example passes end to
end, ./scripts/check green, one commit, pushed.
Tip: 3c5d880 (U0). The gate is RED until this unit lands — the fixture test
`test_the_fixture_is_section_10s_example_verbatim` is the failure.
Standing constraints: one sub-agent per unit; commit and push every unit;
./scripts/check green before every commit; builders never edit DESIGN.md,
meta/plan.md or this file.
