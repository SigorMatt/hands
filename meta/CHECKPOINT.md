# CHECKPOINT

Mission: 3 (meta/BUILDER-3-PROMPT.md) — IN PROGRESS
Unit in progress: U7 `hands send --prompt-file PATH`
Intent: add `hands send --prompt-file PATH` (DESIGN §4, §12, §19) so prompts
never travel on a command line.
Done means: the CLI reads the prompt from the file (UTF-8, any readable path
— the CLI is a client, not the daemon, so no root confinement) and sends it
byte for byte; mutually exclusive with `--stdin` and the positional prompt;
driver/CLAUDE.md rule 6 becomes "prompts and long content travel as files"
(`--prompt-file`, `hands put`); docs/INTEGRATION.md and the driver command
list updated; bash_guard SELFTEST gains a `--prompt-file` case. Tests include
a prompt containing `>`, `(`, quotes and a newline arriving verbatim in the
job record. Gate green; pushed.
Tip: ecdb0f3 (U6) — gate green, 603 passed; guard selftest 62/62.
Findings: H-001 open (needs a capture from a dotted cwd). H-002, H-003,
H-005 fixed with no code change; H-004 a67c4b0, H-006 34b4ede, H-007
267ee01, H-008 8448b6f. H-009, H-010 filed by this unit, both open and
both for the architect.
Not proven, carried forward from mission 2 and still true at the base:
  1. None of mission 2's code has ever run outside the test suite — the
     installed daemon is the mission-1 build. `uv tool install --force
     ~/git/hands` is what would put it under a real run.
  2. `hands notify --test` has never been run against a live ntfy topic.
Standing constraints: one sub-agent per unit, commit and push every unit,
./scripts/check green before each commit, DESIGN.md is not edited by
builders (file a finding), sub-agents do not edit meta/plan.md or this file.
