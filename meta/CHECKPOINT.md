# CHECKPOINT

Mission: 4 (meta/BUILDER-4-PROMPT.md) — IN PROGRESS
Unit in progress: U2 (a deterministic gate)
Intent: tests/test_daemon.py:556 asserts on the stall sentence (or its absence),
not on the bare substring "40" in a line that also carries a tmpdir path; every
other assertion in tests/test_daemon.py and tests/test_playbook.py that matches
a bare number or a substring a path or a counter could contain is pinned.
Done means: ./scripts/check run five times, 5/5 green, reported in the commit
body; the deterministic reproduction (--basetemp with a 40-bearing name) is
green too; one commit, pushed.
Tip: U0 (8268539, meta only) and U1 (935a275) committed and pushed on `main`.
U1 was green three consecutive runs, 681 passed; `bash_guard.py --selftest`
65/65. Base 796e5ae was green here at 618 passed.
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
