# CHECKPOINT

Mission: 9 (meta/BUILDER-9-PROMPT.md, DESIGN v3.8 §25)
Base: 0ead876 — RED (1 failed, 1423 passed): the §10 example fixture pin.
Done: U0 1c17d84 (green 3/3, 1424 passed; base repaired by copying §10's
example into the fixture and docs/PLAYBOOK.md per H-016); U1 4da83f8 (green
3/3, 1428 passed; termination line wins over success; §6 vocabularies pinned
against DESIGN.md; `DECIDED_BY` constant in gates.py); U2 7992c4d (green 3/3,
1432 passed; main() exit code through the socket route, `_last_resort` member
check, reconnect warning without the topic).

Unit in progress: U3 Playbook must match the committed file (§10).
Intent: at load, the playbook file's bytes are compared with `git show
HEAD:<playbook.path>` in `role.cwd`; on a difference (or an untracked file)
the playbook is refused with a message naming both sha256s, the pipeline
stops with that reason, and the event says so. `hands doctor`'s playbook row
reports committed/dirty.
Done means: tests with a temp git repo for committed-and-clean (loads),
dirty (refused, both sha256s named, pipeline stopped, event), untracked
(refused); a dirty PLAYBOOK.toml is refused at job start; doctor row test;
check green three consecutive runs; one commit listing every file; pushed.

Standing constraints: one foreground sub-agent per unit, commit and push
every unit, ./scripts/check green three consecutive runs before each commit,
explicit paths only in `git add` (never `-A`), reports drafted under
meta/drafts/, DESIGN.md is not edited by builders (file a finding),
sub-agents do not edit meta/plan.md or this file.
