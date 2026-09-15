# CHECKPOINT

Mission: 13 (meta/BUILDER-13-PROMPT.md, DESIGN v3.12 §29 with §5, §12, §13,
§26, §28) — close review 12, the sweep (H-025 b), two projects on one laptop.
Base: 723dbeb (`plan: mission 13 kit (DESIGN v3.12)`).

Unit in progress: U7 This repository's playbook.
Intent: `[series] kickoff` in PLAYBOOK.toml becomes BUILDER-14's line
(`Read meta/BUILDER-14-PROMPT.md and execute the mission below its
divider.`); nothing else; the kickoff test moves to BUILDER-14.
Done means: the playbook loads; a kit of meta/BUILDER-13-PROMPT.md checked
with `hands kit check <kit> --repo .` exits 0; ./scripts/check 3/3; pushed.
Done: U0 b79d908 (1994); U1 eccc3a1 (2092); U2 ea7f1bc (2098); U3 126d4ff
(2196); U4 38022f2 (2235); U5 9ca89cf (2272); U6 8f79f98 (2283).

Standing constraints: one foreground sub-agent per product unit, commit and
push every unit, ./scripts/check green three consecutive runs before each
commit, explicit paths only in `git add` (never `-A`), reports drafted under
meta/drafts/, DESIGN.md is not edited by builders (file a finding), sub-agents
do not edit meta/plan.md or this file, retry a failed unit once then `[b]`.
