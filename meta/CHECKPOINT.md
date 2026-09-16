# CHECKPOINT

Mission: 16 (meta/BUILDER-16-PROMPT.md, DESIGN v3.15 §32 with §6, §8, §12,
§30, §31).
Base: 31789c6 (`plan: mission 16 kit (DESIGN v3.15)`).
Done: U0 7de7520 (`plan:`; H-033 filed; H-030/031/032 resolutions; FR-15
§3.1 corrected; base-red fixes folded in); green 3/3 (3126).
U1 c7dafd2 — `$ { }` and unquoted reserved words refused in every mode before
tokenizing; plain-word rule over every row; role reads confined to HANDS_CLONE
+ ~/.hands/<project>/ (+ HANDS_KITS for the architect); green 3/3 (3594).
U2 7ce3189 — zip/unzip rows gone (mkdir -p, cp -r, mv only, under KITS);
`kit file <dir>` builds and checks the zip client-side, sends it to the daemon
method `kit_file`, which mints `kit_id`, stores the zip under the spool and
files the held apply (origin architect); phone `kit` also records a kit_id;
green 3/3 (3647). Open for U3: any same-user socket client can call
`kit_file` with an unchecked zip.
U3 f4fde48 — engine approves only a held apply with a spool-known kit_id filed
through `kit_file` during an open architect consultation (or its `next kit`
wait, same name); send refuses origin architect and roles driver/architect;
kickoff rule only for such an apply; `next kit` waits by kit_id+name within
kit_wait_s (in memory); rename refused unless max_architect_consults restated
(role mode); green 3/3 (3689).
U4 44410ea — role without [roles.architect] refused by handsd, doctor, kit
check/file; doctor rows check push URL, kits under cwd, same guard in both
command hooks, bypass/allow entries, architect-mode self-test; prompt carries
the first non-DONE milestone of the committed roadmap + its path; start
notifications folded into one; green 3/3 (3736).
U5 e091d0b — task_killed → notify pinned in PLAYBOOK.toml and both templates
(loader + engine), docs swept; DESIGN §10's example and §24 still say `stop`
and the fixture/PLAYBOOK.md copy must match §10 byte for byte: H-034 filed;
green 3/3 (3743).
U6 6939524 — kickoff names BUILDER-17; loads (20 rules); kit of BUILDER-16
brief `--repo .` 6 of 6, exit 0; green 3/3 (3743, in a temp worktree with the
change committed, same tree pushed).
U7 is the commit that carries this line (meta only): meta/FINAL-REPORT-16.md.
Mission 16 — FINISHED. Unit in progress: none. U0-U7 `[x]` in meta/plan.md.
Findings: H-033 filed and resolved; H-030, H-031, H-032 resolved; H-034 open
(DESIGN §10/§24 say `stop`); H-027, H-001, H-009 open.
Next: PLAYBOOK.toml names meta/BUILDER-17-PROMPT.md, which the architect ships.
Standing constraints: one foreground sub-agent per product unit, commit and
push every unit, ./scripts/check green three consecutive runs before each
commit, explicit paths only in `git add` (never `-A`), reports drafted under
meta/drafts/, DESIGN.md is not edited by builders (file a finding), sub-agents
do not edit meta/plan.md or this file, retry a failed unit once then `[b]`.
