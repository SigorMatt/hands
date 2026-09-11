# CHECKPOINT

Mission: 4 (meta/BUILDER-4-PROMPT.md) — IN PROGRESS
Unit in progress: U1 (guard scope)
Intent: the git subcommand allowlist applies to every `git` token anywhere in
the command, not only at a segment's first word; `find` with `-exec`,
`-execdir`, `-ok`, `-okdir` or `-delete` is forbidden;
`MUTATING_GIT_SUBCOMMANDS` and the first-level-only check are gone;
`tests/test_bash_guard.py` gains an adversarial table of ≥20 cases written
without reading `SELFTEST`; `driver/settings.json` denies `MultiEdit` again.
Done means: both tables green, `--selftest` green, ./scripts/check green three
times, one commit naming which adversarial cases failed against `ecdb0f3`,
pushed.
Tip: U0 committed and pushed on `main` (meta only). Base 796e5ae was green
here: ruff clean, 618 passed, cli smoke, `check: green`.
Findings: H-001 open (needs a capture from a dotted cwd). H-009 open
(design-side; no builder unit can close it). H-010 amended by U0 with both
observations and the decision to keep the `MultiEdit` rule — still open until
U1 puts it on disk. H-002..H-008 closed in missions 2 and 3.
Not proven, carried into this mission (see meta/FINAL-REPORT-3.md §3, as
corrected by the dated line U0 appended):
  1. Mission 3's code has never run outside the test suite — the installed
     build is mission 2's (it has `notify`, it has no `--prompt-file`).
     `uv tool install --force ~/git/hands` is what would put this mission's
     code under a real run.
  2. `hands notify --test` has never been run against a live ntfy topic;
     delivery is still unproven, the httpx MockTransport test being
     off-network by construction.
  3. The guard has never run as a real Claude Code `PreToolUse` hook;
     `main()`'s stdin/exit-2 wiring has no test.
Standing constraints: one sub-agent per unit, commit and push every unit,
./scripts/check green before each commit (three consecutive runs this
mission — review 3 found the gate non-deterministic), DESIGN.md is not edited
by builders (file a finding), sub-agents do not edit meta/plan.md or this
file.
