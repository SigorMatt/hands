# CHECKPOINT

Mission: 4 (meta/BUILDER-4-PROMPT.md) — IN PROGRESS
Unit in progress: U3 (pipeline state)
Intent: DESIGN §10 as v3.3 states it — a `cli`-origin send un-pauses only when
the job STARTS (held or queued changes nothing, and a playbook- or
limit-started job never clears a stop); one `stop()` for every component, the
limit manager's `max_resumes` stop included, keeping the first reason and
filing `stop.suppressed` (no notification) for a later stop over an existing
one; `last_rule` reset when a playbook with a different sha256 loads;
`pipeline.resumed` says `by: start` or `by: resume`.
Done means: tests for gate-time no-op, start-time un-pause, a playbook job not
un-pausing, a limit stop over a rule stop, and the `last_rule` reset; mission
1's engine-level end-to-end still passes; ./scripts/check green three times;
one commit, pushed.
Tip: U0 (8268539, meta only), U1 (935a275) and U2 (667ea52) committed and
pushed on `main`. U2's gate was five consecutive green runs at 682 passed, and
the flake reproduction (`--basetemp=/tmp/pt-40/pytest-1340`) is green where it
was red. Base 796e5ae was green here at 618 passed.
Findings: H-001 open (needs a capture from a dotted cwd). H-009 open
(design-side; no builder unit can close it). H-010 closed by U1 (935a275): the rule is back in
`driver/settings.json` and `tests/test_docs.py` asserts it; the memo carries
U0's amendment and U1's closing Status line. H-002..H-008 closed in missions 2 and 3.
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
