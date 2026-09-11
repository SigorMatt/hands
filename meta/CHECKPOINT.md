# CHECKPOINT

Mission: 3 (meta/BUILDER-3-PROMPT.md) — IN PROGRESS
Unit in progress: U5 notify status on failure
Intent: `hands notify --test` must report the HTTP status on the failure
path too (review should-fix 7, DESIGN §4 `notify` row, §11, §19).
Done means: `ntfy <code> <url>` is printed for any HTTP response, 2xx or not;
exit 1 only on non-2xx or transport error; one test drives a real httpx
MockTransport returning 403, so `http_post`'s `-> int` return is verified
against httpx rather than a monkeypatch. Gate green; committed and pushed.
Tip: 9cd6108 (U4) — gate green, 530 passed.
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
