# CHECKPOINT

Mission: 19 (meta/BUILDER-19-PROMPT.md, DESIGN v3.18 §35 with §26, §31;
meta/reviews/REVIEW-18.md). Direct: every unit commits and pushes to `main`.
Base: 21d62d9 (`plan: mission 19 kit (DESIGN v3.18)`).

Done: U0 (the `plan:` commit that carries this line) — gate passed: probe PR
SigorMatt/hands#1 opened 11:31:49Z, qodo-code-review[bot] first comment
11:32:18Z (29 s, on open); PR closed, `probe-qodo` deleted local and remote.

H-040 filed (the gate is run as `env -u HANDS_PROJECT -u HANDS_JOB
./scripts/check`; with them set, 12 test_kit tests fail). Green 3/3 (4030).

U1 b55dfb1 — doctor `gh` row (version, login, repo scope; WARN + `gh auth
login`); fake gh on PATH via autouse conftest fixture; green 3/3 (4035);
laptop: `ok gh … logged in as SigorMatt (user msi); token scopes include repo`.

U2 7929d9c — brief, protocol and missions-playbook templates carry §35;
kit.py unchanged (already accepts `pr=<number>`, tests prove it); runs
playbook unchanged (its prompt never said "every commit after"); filled kit
6 of 6 against a clone (a test); green 3/3 (4043).

U3 de56f62 — CLAUDE.md branch rule and tree-on-main rule; protocol = template
with SigorMatt/hands (one hunk); kickoff BUILDER-20, review prompt = template's;
pipeline 20 rules; kit of BUILDER-19 `--repo .` 6 of 6; green 3/3 (4045).

U4 5220e67 — handbook §6 seven [series] keys with defaults (HF-004), §9 the
PR flow; INTEGRATION gh prerequisite, doctor's row, tree on main; PLAYBOOK
review-base wording; green 3/3 (4052).
U5 is the commit that carries this line (meta only): meta/FINAL-REPORT-19.md,
plan, checkpoint, journal.
Mission 19 — FINISHED. Unit in progress: none. U0-U5 `[x]` in meta/plan.md.
Findings: H-040 filed (open). H-039, H-037, H-034, H-027, H-001, H-009 open.
Next: PLAYBOOK.toml names meta/BUILDER-20-PROMPT.md, which the architect
ships; mission 20 is the first pull-request mission.

Standing constraints: one foreground sub-agent per unit, commit and push every
unit (to `main`, this mission), ./scripts/check green three consecutive runs
before each commit (each a foreground call, 20-minute timeout), explicit
paths only in `git add` (never `-A`), reports drafted under meta/drafts/,
DESIGN.md is not edited by builders (file a finding), sub-agents do not edit
meta/plan.md or this file, retry a failed unit once then `[b]` (a blocked U0
ends the mission). No engine, guard, role or REVIEW-18 should-fix changes.
