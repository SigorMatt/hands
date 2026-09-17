# CHECKPOINT

Mission: 17 (meta/BUILDER-17-PROMPT.md, DESIGN v3.16 §33 with §8, §11, §26,
§31, §32; meta/reviews/REVIEW-16.md).
Base: 0b8447e (`plan: mission 17 kit (DESIGN v3.16)`), green (3743 passed).
Done: U0 c5b5416 (`plan:`; H-035, H-036 filed; H-034 and FR-16 corrected by
dated lines; SF8 sweep text); green 3/3 (3747).
U1 f6f7f26 — handsd checks the kit it files (kit.json check pass); engine
decides a consultation's hold at the verdict; >1 kit or wrong name → all denied
+ escalate; kit check fails with no/two/invalid config (phone sandbox kit now
fails; docs say check at the laptop); green 3/3 (3761).
U2 6f05e4e — one zip-name judge (central names, mismatches, .git/.claude any
case/depth) for kit check, kit_file, phone; green 3/3 (3784).
U3 2a08e42 — guard cp/mv refuse symlinks under/as HANDS_KITS; doctor role rows
verify settings(.local), matchers, push remotes, kits realpath; green 3/3 (3879).
U4 c6380ab — milestone heading DONE rule on a fixture; start folds queued jobs'
publishes (≤5 s) into one notification; green 3/3 (3897).
U5 de17a7e — `reply` via Api.reply_architect (phone-only); refusals; answer
titled `architect`; kit_file refused during a reply job; green 3/3 (3908).
U6 4775880 — ntfy_token bearer on publish/subscribe/who/notify --test; doctor
on/off; INTEGRATION self-hosted section; buttons carry no token (H-037 to file
in U8); green 3/3 (3935).
U7 63ac5c3 — kickoff names BUILDER-18; loads (20 rules); kit of BUILDER-17
brief `--repo .` 6 of 6, exit 0; green 3/3 (3935).
U8 is the commit that carries this line (meta only): meta/FINAL-REPORT-17.md,
H-035/H-036 resolved lines, H-037 filed.
Mission 17 — FINISHED. Unit in progress: none. U0-U8 `[x]` in meta/plan.md.
Findings: H-035, H-036 filed and resolved; H-037 open (buttons carry no ntfy
token); H-034, H-027, H-001, H-009 open.
Next: PLAYBOOK.toml names meta/BUILDER-18-PROMPT.md, which the architect ships.


Standing constraints: one foreground sub-agent per unit, commit and push every
unit, ./scripts/check green three consecutive runs before each commit, explicit
paths only in `git add` (never `-A`), reports drafted under meta/drafts/,
DESIGN.md is not edited by builders (file a finding), sub-agents do not edit
meta/plan.md or this file, retry a failed unit once then `[b]`. meta/plan.md,
meta/CHECKPOINT.md and meta/journal.md are updated between units and carried
by the U8 commit.
