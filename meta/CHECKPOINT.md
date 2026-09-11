# CHECKPOINT

Mission: 4 (meta/BUILDER-4-PROMPT.md) — IN PROGRESS
Unit in progress: U5 (--prompt-file refusals and driver rule 6)
Intent: the client refuses a missing, unreadable, empty or over-10 MB prompt
file with a one-line error and exit 2, before contacting the daemon;
`driver/CLAUDE.md` rule 6 becomes the §12 text of DESIGN v3.3, and the
contradictory sentence about metacharacters goes.
Done means: tests for the four refusals; `grep -rn metacharacters driver/`
returns nothing; ./scripts/check green three times; one commit, pushed.
Tip: U0 (8268539, meta only), U1 (935a275), U2 (667ea52), U3 (c108bfe) and
U4 (15eeb76) committed and pushed on `main`; 719 passed at U4's tip, gate green
three consecutive runs. U2's flake reproduction
(`--basetemp=/tmp/pt-40/pytest-1340`) is green where it was red. Base 796e5ae
was green here at 618 passed.
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
