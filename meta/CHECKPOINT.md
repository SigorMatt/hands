# CHECKPOINT

Mission: 22 (meta/BUILDER-22-PROMPT.md, DESIGN v3.21 §38 with §26, §31,
§33, §36, §37; meta/reviews/REVIEW-21.md). Branch: `mission-22` from main
7ddc0e8; every unit commits and pushes to it; U12 opens the PR to main.

Done: U0 759f605 (`plan:`) — H-049, H-050 filed; green 3/3 (4261).

Done: U1 3feb89b — bearer in the short action form on every http action with a token; config refuses , or ; in the token; doctor phone row buttons wording; H-037 resolved-by-code; green 3/3 (4269).

Done: U2 5f3b7ad — who publishes only when fingerprint and time-blanked picture both differ, floor who_min_interval_s (60) unless requested; refused publish starts the floor; doctor broker row warns on public ntfy_url; H-046 resolved-by-code; green 3/3 (4300).

Done: U3 96d3fbb — daemon stop records running jobs orphaned (orphan_reason daemon_stop on the record, reason on the inbox event); orphan_fed flag, fed once after queued jobs re-admitted; start notification names the resumed job; playbook.py unchanged; H-047 resolved-by-code; green 3/3 (4308).

Done: U4 69364de — CONSULT_EVENTS[ARCHITECT] gains builder.done; blocked prompt with verdict + reply between REPLY markers; consult on builder.done refused at load without a blocked verdict regex; template role-mode rule, phone-mode stop; kit.py unchanged (engine parser); PLAYBOOK.toml unchanged; H-048 resolved-by-code; green 3/3 (4317).

Done: U5 f16c331 — progress: tenth secret-only command, titled progress; Api.progress_report outside COMMANDS; builder line, branch + log -3, checkpoint line or no checkpoint; non-repo cwd one plain line; green 3/3 (4322).

Done: U6 22a2ef5 — consult.sent records head of the builder cwd; human_decisions uses git log <sha>..HEAD, no --since; owner paths via git ls-files --full-name in the cwd; untracked owner file now omitted; green 3/3 (4324).

Done: U7 cfb7e71 — both protocols: per-file revert (checkout <sha>~1 if it exists via git cat-file -e, else rm), added files named as added; Notes schedule lines + reason; owner-decisions exception; human-supplied by git show --stat; pin test 8 cases; H-049, H-050 resolved-by-doc; green 3/3.

Done: U8 7df5bce — templates/DECISIONS-owner.md added; brief template §R keep rule + human-supplied unit shape; Purpose block (FOR/NOT/DECIDES) atop both instructions + ruling paragraph; kit.py unchanged (already tolerant); green 3/3 (4338).

Done: U9 b6e2511 — docs/ and templates/ force-included under hands/shipped/; hands handbook [--templates]; HANDS_DOCS on every role job; §6 keys == SERIES_KEYS test; §12 laptop check + silent first apply; HF-002/004/005 noted resolved; H-051 filed open (role cannot learn HANDS_DOCS' value under the guard); green 3/3 (4349).

Done: U10 f1936b1 — src/hands/project.py and templates/config.toml added; project add writes config+secret (600), role dirs with shipped settings/guard, no_push clones, enables handsd@<name> (fake systemctl), runs doctor (exit 0 regardless), prints instruction + question last; dry-run writes nothing; refusals; H-052 filed open (role CLAUDE.md from architect/CLAUDE.md, not ARCHITECT-INSTRUCTION.md); green 3/3 (4359).

Done: U11 9fae4ee — INTEGRATION self-hosted corrections, python3 -I everywhere (review 21 should-fix 3), handbook §13-§18, PLAYBOOK auto-runs; role READMEs aligned; H-053 filed open; green 3/3 (4387).

U12 is the commit that carries this line: meta/FINAL-REPORT-22.md, plan,
checkpoint, journal, FINDINGS (H-054). Tip green 3/3 (4387).
Mission 22 — FINISHED. Unit in progress: none. U0-U12 `[x]` in meta/plan.md.
PR mission-22 -> main opened by this unit. Open findings for the architect:
H-051, H-052, H-053, H-054.

Standing constraints: one foreground sub-agent per unit, commit and push every
unit to `mission-22`, ./scripts/check green three consecutive runs before each
commit (each a foreground call, 20-minute timeout), explicit paths only in
`git add` (never `-A`), reports drafted under meta/drafts/, DESIGN.md is not
edited by builders (file a finding), sub-agents do not edit meta/plan.md or
this file, retry a failed unit once then `[b]`. Not touched: the guard's
language, the review merge step, other agent backends.
