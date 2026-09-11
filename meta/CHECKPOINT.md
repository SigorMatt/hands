# CHECKPOINT

Mission: 4 (meta/BUILDER-4-PROMPT.md) — IN PROGRESS
Unit in progress: U6 (final report)
Intent: meta/FINAL-REPORT-4.md — what changed (a sha per unit), what the tests
prove, NOT PROVEN (mandatory), and a `## Review items` table mapping review 3's
blockers 1-3 and should-fix 1-11 to `closed <sha>` | `deferred <mission>` |
`not applicable <reason>`. Then the verdict line.
Done means: the report exists, the gate is green on the pushed tip three
consecutive runs, and the mission's five acceptance criteria are checked.
Tip: U0 (8268539, meta only), U1 (935a275), U2 (667ea52), U3 (c108bfe),
U4 (15eeb76) and U5 (2fb3b7f, then the follow-up d348d07) committed and pushed
on `main`; 726 passed at U5's tip, gate green three consecutive runs. U2's
flake reproduction (`--basetemp=/tmp/pt-40/pytest-1340`) is green where it was
red. Base 796e5ae was green here at 618 passed.
Findings: H-001 open (needs a capture from a dotted cwd). H-011 filed after
U3: `stop.suppressed` falls inside `stop`'s wake namespace, so `hands wait
--for stop` wakes on a stop that was deliberately not notified — design-side,
open. H-009 open
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
