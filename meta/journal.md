# journal

One line per unit, appended by the builder: date, unit, sha, verdict.

2026-09-11  U0 Scaffold  bff77ec  green (ruff+pytest+cli smoke)
2026-09-11  U1 Config and spool  6fda083  green (186 tests)
2026-09-11  U2 Fake claude and runner  ed6438b  green (229 tests); findings H-001..H-003
2026-09-11  U3 Daemon, local API, CLI  1e4429a  green (249 tests); e2e over the real socket
2026-09-11  U4 Files and gates  3d27480  green (293 tests); authority table table-driven
2026-09-11  U5 Limits  b667786  green (341 tests); finding H-004 (origin of a self-made job)
2026-09-11  U6 Monitor bridge  37d4e2a  green (361 tests); ops-script contract untested against a real script
2026-09-11  U7 Playbook engine  36f9bd3  green (421 tests); §10 example end to end; findings H-005, H-006
2026-09-11  U8 Wake path and notifications  4a3d302  green (451 tests); U5 restart gap closed
2026-09-11  U9 Job library  8cc2356  green (465 tests); tail implemented too
2026-09-11  U10 Install surface  9096b50  green (488 tests); finding H-007 (pause writes no event)
2026-09-11  U11 Final report  530de9d  green (488 tests); mission 1 finished
