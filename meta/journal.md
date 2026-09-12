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
2026-09-12  m5 U1 Guard git option policy  50c466c  green 3/3 (778 tests); blocker 1 closed; ADVERSARIAL 102, SELFTEST 77; find -fprint*/-fls forbidden
2026-09-12  m5 U2 ops.monitor_cmd shape  ce92ed6  green 3/3 (789 tests); blocker 2 closed; relative, no .., executable regular file under ops.repo
2026-09-12  m5 U3 Determinism as a property  e35a2e7  green 3/3 + 5/5 crafted basetemps (794 tests); should-fix 1 and 2 closed; strip_paths + two AST audits
2026-09-12  m5 U4 Prompt delivery  6d9664d  green 3/3 (804 tests); should-fix 3, 4, 5 closed; ensure_ascii=False, wire cap on both routes, S_ISREG, exit-2 docs; H-012 filed
2026-09-12  m5 U5 Pipeline and config edges  06de18c  green 3/3 (812 tests); should-fix 7 and 8 closed; H-011 closed: pipeline.stop_suppressed; last_rule stale: true
2026-09-12  m5 U6 Daemon memory  53bb986  green 3/3 (818 tests); DESIGN 21; the runner writes the stream to the job log, retains 0 events; tail reads a window; H-013 filed
2026-09-12  m5 U7 No background tasks  ffa4c65  green 3/3 (929 tests); DESIGN 21; PreToolUse hook refuses run_in_background and hand-rolled daemonization
2026-09-12  m6 U0 Plan and corrections  bb9d8fb  meta only (929 tests green 3/3); FINAL-REPORT-5 §3 carries blocker 1, blocker 2 and should-fix 2 corrections; H-012 decided: the client measures the whole request
2026-09-12  m6 U1 The whole request on the wire  81e4cd2  green 3/3 (936 tests); blocker 1 closed; the client measures gate, --file payloads and envelope and refuses with exit 2 before connecting; H-012 closed
2026-09-12  m6 U2 tail semantics, log paging  0042433  green 3/3 (942 tests); blocker 2 closed; -n >= 1, truncated: true when cap or window cut it, log delivered in pages; H-013 closed
2026-09-12  m6 U3 Guard git option allowlist  5ffbe33  green 3/3 (1047 tests); should-fix 1 closed; per-subcommand allowlist, selftest 100/100, ADVERSARIAL gains --upload-pack=/--exec=/--edit-description/-C --exec-path=
2026-09-12  m6 U4 Hook bypasses  fba759b  green 3/3 (1095 tests); should-fix 2 closed; selftest 65/65; comment-suffix & and path-qualified nohup blocked, unreadable tool_input exits 2; the inner-shell class documented
2026-09-12  m6 U5 Five REVIEW-5 edges  44e42ba  green 3/3 (1109 tests); should-fix 3, 4, 5, 6, 7 closed; last_argv bounded, ops containment resolves, the section scan binds, audits exempt by type, both prompt routes refuse non-UTF-8
2026-09-12  m6 U5 follow-up  3809fcf  green 3/3 (1109 tests); U5's own NOT PROVEN closed: a prompt argument and every string in params refuse non-UTF-8 under the name it was typed as
2026-09-12  m6 U6 Driver kit and doctor text  56bef53  green 3/3 (1112 tests); DESIGN v3.5 §11, §12 rule 8, §22; kit rule 8 == design rule 8, doctor prints a notification check, not a background wake
2026-09-12  m6 U6 follow-up  3dd3403  green 3/3 (1112 tests); 19 sentences in 8 files that still said the driver arms or blocks on a wait; comments/docstrings/prose only, no behaviour
2026-09-12  m6 U7 Final report  0f046ea  green 3/3 (1112 tests); mission 6 finished (entry amended: it was written with 7abcb32, the pre-amend commit, which is unreachable from main — the same defect REVIEW-3 should-fix 6 named)
2026-09-12  m7a pre-U0 kit drift  169ce88  green 3/3 (1112 tests); base db0bd2c red 2/1112: rule 8 and the §10 example follow DESIGN v3.6
2026-09-12  m7a U0 Plan and corrections  b77bc4d  green 3/3 (1112 tests); README open question gone (blocker 1); FINAL-REPORT-6 §1 U5 item 7 corrected (blocker 2); H-014 filed and decided
2026-09-12  m7a U1 Harness termination is failed  c00f0c0  green 3/3 (1156 tests); terminating line / no final result / no num_turns → failed with failure_reason; BG_WAIT_CEILING=0 unless [roles.<r>] env sets it; doctor shows it; builder.failed → resume end to end
2026-09-12  m7a U2 Hook covers sub-agents  09eed7c  green 3/3 (1204 tests); matcher Bash|Agent|Task; Agent/Task refused unless run_in_background is literally false (2.1.269 backgrounds an omitted flag); SendMessage documented as unseen
2026-09-12  m7a U3 Doc-truth as a property  da1ffb3  green 3/3 (1205 tests); the sweep reads 50 of 79 tracked files by rule (git ls-files, text extensions + #!; meta/, DESIGN.md, tests/test_docs.py excluded); red at dca0820 on README and test_playbook; doctor and rule 8 asserted from their own text
2026-09-12  m7a U4 Client seams  b29b1c7  green 3/3 (1233 tests); one walk (_carried) feeds size and UTF-8, dict keys and any depth; positionals refused as "a job/path/prompt argument", flags keep their option string
