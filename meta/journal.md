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
2026-09-11  U0 Plan  3c5d880  meta only; base gate RED until U3 (§10 example fixture)
            (this entry named its own sha, so the commit was amended; the original
             857f6f2 is unreachable from main. Corrected by mission 3 U0.)
2026-09-11  U3 Explicit run key  34b4ede  green (494 tests); H-006 fixed; base gate green again
2026-09-11  U1 Origin limit  a67c4b0  green (496 tests); H-004 fixed; --origin did not exist, added
2026-09-11  U2 Resume line optional  8448b6f  green (501 tests); H-008 fixed; one rule in RoleConfig.resume_prompt
2026-09-11  U4 Pause files an event  267ee01  green (510 tests); H-007 fixed; wait --for stop wakes on pause
2026-09-11  U5 hands notify --test  44c345b  green (518 tests); client-side, not over the socket; no real HTTP yet
2026-09-11  U6 Status wording  bde33fe  green (519 tests); queue_capacity alias; monitor line matches §5
2026-09-11  U7 Retire bootstrap  d973ece  green (521 tests); dispatch.sh gone from code, docs and driver
2026-09-11  U8 Final report  f636e81  green (521 tests); mission 2 finished
2026-09-12  U0 Plan  efc501b  meta only; journal sha fixed (should-fix 6); H-009, H-010 filed
2026-09-12  U1 Status monitor  87bb7f8  green (523 tests); should-fix 2 closed; OPS_FLAGS is one list
2026-09-12  U2 Tests that can fail  4fb1f35  green (523 tests); should-fix 3 and 8 closed; 4/4 red at 34b4ede^
2026-09-12  U3 Pause keeps first reason  3cd2306  green (526 tests); should-fix 4 closed; no-op exits 0
2026-09-12  U4 Empty resume_line refused  9cd6108  green (530 tests); should-fix 5 closed; whitespace-only refused too
2026-09-12  U5 notify status on failure  861097f  green (539 tests); should-fix 7 closed; real httpx MockTransport
2026-09-12  U6 Guard fix and guard tests  ecdb0f3  green (603 tests); selftest 62/62 in pytest; MultiEdit rule dropped (H-010)
2026-09-12  U7 send --prompt-file  45400e8  green (618 tests); DESIGN 19; prompt byte for byte over the socket
2026-09-12  U8 Final report  8c365b6  green (618 tests); mission 3 finished
2026-09-12  U0 Plan and corrections  8268539  meta only; FINAL-REPORT-3 §3 corrected (blocker 3); H-010 amended (should-fix 2)
2026-09-12  U1 Guard scope  935a275  green (681 tests); blocker 1 closed; ADVERSARIAL table of 62 owns its own verdicts; MultiEdit back
2026-09-12  U2 Deterministic gate  667ea52  green 5/5 (682 tests); blocker 2 and should-fix 11 closed; 30 assertions pinned
2026-09-12  U3 Pipeline state  c108bfe  green 3/3 (692 tests); should-fix 4 closed; un-pause at start; stop.suppressed; H-011 filed
2026-09-12  U4 Optional keys and doctor  15eeb76  green 3/3 (719 tests); should-fix 5 and 8 closed; 11 optional keys refuse a blank
2026-09-12  U5 prompt-file refusals, rule 6  2fb3b7f  green 3/3 (725 tests); should-fix 9 and 10 closed; driver rule 6 is §12's text
2026-09-12  U5 follow-up  d348d07  green 3/3 (726 tests); the four refusals exit 2 as the brief asks; EXIT_REFUSED == EXIT_TIMEOUT == 2
2026-09-12  U6 Final report  f9d353d  green 3/3 (726 tests); mission 4 finished
2026-09-12  m5 U0 Plan and corrections  068a091  meta only; FINAL-REPORT-4 item 15 corrected (blocker 1); H-011 decided: pipeline.stop_suppressed
