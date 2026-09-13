# CHECKPOINT

Mission: 9 (meta/BUILDER-9-PROMPT.md, DESIGN v3.8 §25)
Base: 0ead876 — RED (1 failed, 1423 passed): the §10 example fixture pin,
because v3.8 added the two detector rules to §10's example.

Unit in progress: U0 Plan and corrections (`plan:` commit).
Intent: plan and checkpoint; H-014 and H-016 get the v3.8 resolutions from
§25; H-017 filed for REVIEW-8 should-fix 2 with status `fixed by DESIGN
v3.8`; §10's example (now with the two stop rules) copied verbatim into
tests/fixtures/playbook_example.toml and the verbatim block of
docs/PLAYBOOK.md, the example rule-list test extended, the "carries neither
yet" sentence dropped. The prototypes ruff exclude is already gone (m8 U6).
Done means: `./scripts/check` green three consecutive runs; one `plan:`
commit whose body lists every file; pushed.

Standing constraints: one foreground sub-agent per unit, commit and push
every unit, ./scripts/check green three consecutive runs before each commit,
explicit paths only in `git add` (never `-A`), reports drafted under
meta/drafts/, DESIGN.md is not edited by builders (file a finding),
sub-agents do not edit meta/plan.md or this file.
