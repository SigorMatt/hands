# CHECKPOINT

Mission: 2 (meta/BUILDER-2-PROMPT.md) — IN PROGRESS
Unit in progress: none (U0 done; U3 is next — see the order deviation in
meta/plan.md: the mission base is red until U3 lands)
Intent: -
Done means: -
Tip: mission base 59e7ac7. `./scripts/check` is RED at the base:
`tests/test_playbook.py::test_the_fixture_is_section_10s_example_verbatim`
fails because DESIGN §10's example now uses `run = "{n+1}"` and the fixture
still says `only_if_run_in`. U3 fixes it; U1, U2, U4.. follow.
Standing constraints: one sub-agent per unit; commit and push every unit;
./scripts/check green before every commit; builders never edit DESIGN.md,
meta/plan.md or this file.
