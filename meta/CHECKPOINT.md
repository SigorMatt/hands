# CHECKPOINT

Mission: 18 (meta/BUILDER-18-PROMPT.md, DESIGN v3.17 §34 with §11, §26, §32,
§33; meta/reviews/REVIEW-17.md).
Base: fc376ab (`plan: mission 18 kit (DESIGN v3.17)`).

Done: U0 23da451 (`plan:`; H-038 filed; FINAL-REPORT-17 corrected by a dated
block); green 3/3 (3935).

U1 45da318 — job.held never folded, published at once with buttons, title
only in the start notification; held-before-start jobs re-published with fresh
buttons; stop flushes and drains, cancel_all deleted; probes A/B2 red first;
H-039 filed (fold reading); green 3/3 (3937).

U2 88e8830 — kit.json sha256; approval re-hashes, kit.refused with both hashes;
kit_file locked per consultation, second refused before check; green 3/3 (3945).

U3 f846965 — lstat walk (guard + doctor), three settings layers, env/hook-key
checks, guard path + sha256 vs shipped (wheel carries it); green 3/3 (4000).

U4 2221151 — token refused without a non-public ntfy_url (every loader); who's
"needs YOU" from state now; green 3/3 (4030).

U5 f159d28 — kickoff names BUILDER-19; loads (20 rules); kit of BUILDER-18 brief
`--repo .` 6 of 6, exit 0; green 3/3 (4030).
U6 is the commit that carries this line (meta only): meta/FINAL-REPORT-18.md,
H-038 resolved line, H-039 filed.
Mission 18 — FINISHED. Unit in progress: none. U0-U6 `[x]` in meta/plan.md.
Findings: H-038 filed and resolved; H-039 open (§34's fold reading); H-037,
H-034, H-027, H-001, H-009 open.
Next: PLAYBOOK.toml names meta/BUILDER-19-PROMPT.md, which the architect ships.

Standing constraints: one foreground sub-agent per unit, commit and push every
unit, ./scripts/check green three consecutive runs before each commit, explicit
paths only in `git add` (never `-A`), reports drafted under meta/drafts/,
DESIGN.md is not edited by builders (file a finding), sub-agents do not edit
meta/plan.md or this file, retry a failed unit once then `[b]`. meta/plan.md,
meta/CHECKPOINT.md and meta/journal.md are updated between units and carried
by the U6 commit.
