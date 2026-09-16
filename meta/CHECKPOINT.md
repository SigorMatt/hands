# CHECKPOINT

Mission: 15 (meta/BUILDER-15-PROMPT.md, DESIGN v3.14 §31 with §8, §10, §11,
§12, §26, §27, §30) — FINISHED.
Base: 1f8141c (`plan: mission 15 kit (DESIGN v3.14, architect kit)`).
Unit in progress: none. U0-U8 `[x]` in meta/plan.md.
Note on numbering: the brief names H-027 and H-028; H-027 is taken (mission 14
U5, open), so the ledger's next free numbers H-028 and H-029 are used.
Done: U0 1a48e11 (the `plan:` commit) — plan, checkpoint, H-028 and H-029; doctor's
`go` row warns on a kickoff naming an absent file (review 14 should-fix 7);
`spool.ORIGINS` gains `architect` (DESIGN v3.14 §6 already lists it and the
base commit was red without it); green 3/3 (2605 tests). U1 d32f409 —
COMMAND_TABLE replaces ALLOWED_FIRST_WORDS in both modes, the three probes
blocked, a 10k fuzz corpus (seed 20260916) blocked, role mode widened to the
read-only rows per §31; green 3/3 (2721 tests). U2 6b27320 — blocker 2 and should-fix 1-6, one
test per item, each red first; green 3/3 (2751 tests). U3 adf3d7a — architect guard mode,
the `--write` matcher, `[roles.architect]`, `hands kit file`; H-030 filed
(§31's words cannot make a zip's entries repository paths); green 3/3 (3013).
U4 c9ccc18 — the `[series]` keys, the engine's `decided_by: playbook` approval
of `origin: architect` holds, the engine-added kickoff rule, the e2e gate;
H-031 filed (§6's `decided_by` vocabulary is three values, §31 needs four).
U5 9ed931b — consult generalised to the architect on `aux.done`, the four-part
prompt, the three verdicts, the per-series budget the engine spends itself;
green 3/3 (3092 tests). U6 f798521 — doctor's architect row, the docs sweep,
both templates' architect block, `kit file`'s corrected line; H-032 filed
(a laptop `hands send --role architect` is not refused); green 3/3 (3126).
U7 fd1a2dd — kickoff names BUILDER-16, `architect = "phone"` stated; the kit
check of this brief exits 0 (6 of 6); green 3/3 (3126 tests). U8 is the commit
that carries this line (meta only), green 3/3 (3126) on fd1a2dd.
Findings: H-027 open (DESIGN §12 rule 6 and §14's layout line, which builders
may not edit); H-030 open and material — the architect role cannot produce the
artifact its own instruction asks for until the architect picks one of the
memo's three resolutions; H-031 open (§6's `decided_by` vocabulary); H-032
open (a laptop `hands send --role architect` is not refused, and it meets
mission 16's `reply`); H-001 and H-009 open. H-028 and H-029 are resolved by
v3.14.
Report: meta/FINAL-REPORT-15.md (what changed, what the tests prove, NOT
PROVEN, `## Review items`, acceptance, for the architect).
Review 14 closed: blocker 1 (U1), blocker 2 (U2); should-fix 1-6 (U2),
should-fix 7 (U0).
Next: PLAYBOOK.toml names meta/BUILDER-16-PROMPT.md, which the architect
ships; `hands doctor` warns about it today, as U0's should-fix 7 machinery is
meant to.
Standing constraints: one foreground sub-agent per product unit, commit and
push every unit, ./scripts/check green three consecutive runs before each
commit, explicit paths only in `git add` (never `-A`), reports drafted under
meta/drafts/, DESIGN.md is not edited by builders (file a finding), sub-agents
do not edit meta/plan.md or this file, retry a failed unit once then `[b]`.
