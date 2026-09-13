# CHECKPOINT

Mission: 10 (meta/BUILDER-10-PROMPT.md, DESIGN v3.9 §26)
Unit in progress: U4 Who by pid (§26, §11 who view, §4 `who`).
Intent: `hands who` (src/hands/who.py) matches each interactive `claude`
process to its transcript through the pid the transcript records (find the
field in a real transcript's first entry under ~/.claude/projects and quote it,
redacted of content, in a test fixture); falls back to the newest transcript in
the directory only when no pid match exists, and the line says so
(`transcript: by directory`). A job in the same directory as the human's session
is never shown under it.
Done means: one commit, body names U4, §26, lists every file; a fixture with two
transcripts in one directory, one per pid, attributes each correctly; the
fallback line tested; pushed; ./scripts/check green 3/3.
Base: 61e1486.
Done: U0 cbb8fc8 (1435 passed); U1 17ba97e (1443); U2 067b8fd (1461);
U3 6852751 (1501).
Carried to U5: H-019 — templates/PLAYBOOK-*.toml carry `series = "…"` beside
`[series]`, which TOML refuses; the loader takes `[series] name`.
Carried to U7 NOT PROVEN: the phone channel reads no other command during a kit
download (up to 300 s); real ntfy attachment delivery; real `go` from a phone.
Standing constraints: one foreground sub-agent per product unit, commit and
push every unit, ./scripts/check green three consecutive runs before each
commit, explicit paths only in `git add` (never `-A`), reports drafted under
meta/drafts/, DESIGN.md is not edited by builders (file a finding), sub-agents
do not edit meta/plan.md or this file.
