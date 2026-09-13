# CHECKPOINT

Mission: 10 (meta/BUILDER-10-PROMPT.md, DESIGN v3.9 §26)
Unit in progress: U1 REVIEW-9 should-fix 1 and 3, plus should-fix 2's code
half (H-018 gap 3).
Intent:
- SF1: the REVIEW-8 SF3 last-resort group kill (`src/hands/runner.py`
  `_last_resort`, ~694) must not SIGKILL a process group whose id was reused
  after claude was reaped. REVIEW-9 SF1 explains why a membership check changes
  no outcome on Linux; tie the kill to the original group (for example, sweep
  before reaping, or the leader's start time) and prove it with a fixture that
  passes on the parent commit and fails on this one's.
- SF3: the playbook HEAD comparison (`src/hands/playbook.py` ~379-403) runs git
  with GIT_DIR, GIT_WORK_TREE, GIT_INDEX_FILE removed from the child env and
  `-c core.autocrlf=false`, and compares bytes after normalizing line endings.
  Tests include a CRLF-checked-out copy and a GIT_DIR pointing elsewhere.
- SF2 code half: `_failure_reason` returns `error_result` for a final result
  whose subtype is `error` or `error_*` whatever `is_error` says (§6;
  docs/INTEGRATION.md already says so since cbb8fc8). Red first.
Done means: one commit (`<area>: …`), body names U1, §26/§6/§10 and REVIEW-9
SF1/SF2/SF3, lists every file; pushed; ./scripts/check green 3/3.
Base: 61e1486.
Done: U0 cbb8fc8 (1435 passed).
Standing constraints: one foreground sub-agent per product unit, commit and
push every unit, ./scripts/check green three consecutive runs before each
commit, explicit paths only in `git add` (never `-A`), reports drafted under
meta/drafts/, DESIGN.md is not edited by builders (file a finding), sub-agents
do not edit meta/plan.md or this file.
