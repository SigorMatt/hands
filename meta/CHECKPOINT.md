# CHECKPOINT

Mission: 9 (meta/BUILDER-9-PROMPT.md, DESIGN v3.8 §25)
Base: 0ead876 — RED (1 failed, 1423 passed): the §10 example fixture pin.
Done: U0 1c17d84 (green 3/3, 1424 passed; base repaired by copying §10's
example into the fixture and docs/PLAYBOOK.md per H-016); U1 4da83f8 (green
3/3, 1428 passed; termination line wins over success; §6 vocabularies pinned
against DESIGN.md; `DECIDED_BY` constant in gates.py); U2 7992c4d (green 3/3,
1432 passed; main() exit code through the socket route, `_last_resort` member
check, reconnect warning without the topic); U3 fd6ecbe (green 3/3, 1439
passed; playbook bytes compared with `git show HEAD:./<path>` in
roles.builder.cwd through the existing load-error stop; doctor row
committed/dirty/untracked; tests commit playbooks via a conftest helper);
U4 edb8e84 (green 3/3, 1430 passed; quiet_hours machinery removed from
notify/daemon/doctor/cli/api/docs, 10 tests deleted; `[limits] quiet_hours`
refused at load by name; config never had the key).

Unit in progress: U5 Phone channel after restart; detector payload (§25).
Intent: on daemon start, every job still `held` gets a fresh nonce and its
notification is re-sent with buttons; the `monitor.task_killed` payload
carries `cause: unknown` and the docs say why (the stream cannot tell a
harness reap from a `TaskStop`). `who_cmd_topic` stays secret-less by §25; no
code for it.
Done means: tests for re-mint and re-send on restart (old nonce refused, new
nonce accepted) and for `cause: unknown` in the payload; docs name why; check
green three consecutive runs; one commit listing every file; pushed.

Standing constraints: one foreground sub-agent per unit, commit and push
every unit, ./scripts/check green three consecutive runs before each commit,
explicit paths only in `git add` (never `-A`), reports drafted under
meta/drafts/, DESIGN.md is not edited by builders (file a finding),
sub-agents do not edit meta/plan.md or this file.
