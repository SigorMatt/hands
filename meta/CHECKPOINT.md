# CHECKPOINT

Mission: 9 (meta/BUILDER-9-PROMPT.md, DESIGN v3.8 §25)
Base: 0ead876 — RED (1 failed, 1423 passed): the §10 example fixture pin.
Done: U0 1c17d84 (green 3/3, 1424 passed; base repaired by copying §10's
example into the fixture and docs/PLAYBOOK.md per H-016); U1 4da83f8 (green
3/3, 1428 passed; termination line wins over success; §6 vocabularies pinned
against DESIGN.md; `DECIDED_BY` constant in gates.py).

Unit in progress: U2 Review 8 should-fix 1, 3, 4.
Intent: `main()`'s exit code pinned through the socket route for one
command (SF1); `_last_resort` checks `group_pids` before `killpg` and never
signals a group with no members (SF3); the phone channel's reconnect warning
logs the exception type and status only, and a test asserts the topic string
is absent (SF4).
Done means: each item has a test that goes red on the old code (SF1 by
mutation of `return exit_code(...)`); check green three consecutive runs; one
commit listing every file; pushed.

Standing constraints: one foreground sub-agent per unit, commit and push
every unit, ./scripts/check green three consecutive runs before each commit,
explicit paths only in `git add` (never `-A`), reports drafted under
meta/drafts/, DESIGN.md is not edited by builders (file a finding),
sub-agents do not edit meta/plan.md or this file.
