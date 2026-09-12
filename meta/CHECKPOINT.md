# CHECKPOINT

Mission: 6 (meta/BUILDER-6-PROMPT.md) — IN PROGRESS
Unit in progress: U6 (driver kit and doctor text)
Intent: DESIGN v3.5 §11 and §12 rule 8 — the driver arms no background wait.
`driver/CLAUDE.md` carries the v3.5 rule 8 verbatim from DESIGN §12 (the kit
copy is the source of truth; verify it matches). `hands doctor`'s wake-path
text no longer instructs arming a background wait: it describes ntfy as the
human's doorbell and the human's `check` as the driver's, and offers the
gated-send or `hands pause` procedure as a one-time notification test.
`docs/INTEGRATION.md` and `driver/README.md` say the same.
Done means: `grep -rn 'background' driver/ docs/ src/hands/doctor.py` returns
no instruction to arm one; a test pins the rule-8 text and the doctor's
wake-path text; `./scripts/check` green three consecutive runs; one commit
pushed.
Tip: 3809fcf (`client: every string a request carries is refused for not
being UTF-8 where the prompt is`), U5 done and its own NOT PROVEN closed —
1109 passed, three consecutive runs. U5 landed in two commits: 44e42ba (the
five edges) and 3809fcf (the argv route and every string in `params`), the
second red at the first.
Findings: H-001 open (needs a capture from a dotted cwd). H-009 open
(design-side; no builder unit can close it). H-012 closed by U1, H-013 closed
by U2. H-002..H-008, H-010 and H-011 closed in missions 2..5.
Not proven, carried into U7's report:
  1. Missions 3, 4, 5 and 6's code have never run outside the test suite —
     the installed build is mission 2's.
  2. `hands notify --test` has never been run against a live ntfy topic.
  3. Neither hook has run as a real Claude Code `PreToolUse` hook;
     `bash_guard.main()`'s stdin/exit-2 wiring has no test. The
     `bash -c 'cmd &'` / `sh -c` / `eval` class and the blind-spot list
     (`screen -dmS`, `tmux new -d`, `at`, `systemd-run`, a forking script, a
     daemonizer through a variable) stay allowed by design — documented in
     docs/INTEGRATION.md under "what the hook cannot see", not blocked.
  4. The guard's allow list still contains mutation vectors that carry no
     option and so survive U3's allowlist: `git branch <name>`, `git remote
     prune origin`, `git remote set-head origin main`, `git fetch origin
     main:main` and a forced refspec. The allowed options are themselves the
     remaining surface (U3's enumerated table).
  5. The UTF-8 refusals are driven in-process with the strings `PYTHONUTF8=1`
     produces, not under a real `PYTHONUTF8=1` subprocess.
Standing constraints: one sub-agent per unit, commit and push every unit,
./scripts/check green three consecutive runs before each commit, DESIGN.md
is not edited by builders (file a finding), sub-agents do not edit
meta/plan.md or this file.
