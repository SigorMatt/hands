# CHECKPOINT

Mission: 24 (meta/BUILDER-24-PROMPT.md, DESIGN v3.23 §40 with §2, §23,
§33, §35, §38, §39; meta/reviews/REVIEW-23.md; docs/RELATED.md;
docs/QODO-EXTRACTION.md).
Branch: `mission-24` from main de407f2; every unit commits and pushes to
it; U10 opens the PR to main, reads the hosted review, fixes, and returns
the tree to main.

Done: U0 (`plan:`) — H-062..H-069 filed, H-061/H-064/H-065 decided, H-051 Status corrected; origin/mission-24 pushed; green 3/3 (4504).

Done: U1 f558f0f — docs/HARNESS-PROBE.md; Codex 0.163.0 probed (one-shot, resume, VERDICT yes; stream partial; permission no: bwrap sandbox fails to start on this laptop, danger-full-access ran touch and curl); OpenCode unavailable: no model configured (ACP built in); dsh unavailable: not signed in; grep -c redacted = 3; green 3/3 (4504).

Done: U2 b003bee — Api.kickoff(origin) shared by phone go and `hands go` (Api.OPERATIONS); Api.kit_apply (check, copy into kit_dir, held builder job origin kit); README; 7 tests; green 3/3 (4511).

Done: U3 6f373cd — task_killed once per (session, task id), none while the daemon stops the job; transcript path from handsd env + role env CLAUDE_CONFIG_DIR, recorded when claude reports its session, before the first scan; H-062/H-063 resolved-by-code; green 3/3 (4518). Note: the inbox showed the 10-16 bursts were mostly distinct task ids.

Done: U4 8c081d0 — Code Review only (review body, inline ignored), newest wins, exit 4 all-struck, typed id quoted with str (backslash secret test); each pinned against the review's mutation; green 3/3 (4523).

Done: U5 24ac73d — journal sentence decided at job start (worker thread), held prompt is the human's alone, kickoff ids exempt (in memory); INTEGRATION _decide sentence; rule 2 pinned; project add `--` and set-url failure pinned; green 3/3 (4530). Carry to U9: phone.py docstring ~l.132 still claims a malformed nonce line is answered.

Done: U6 529b91f — playbook.orphaned_rule_warnings shared by kit check (WARN lines + json warnings) and engine load (logs each load); PLAYBOOK.md; H-061 resolved-by-code; green 3/3 (4542).

Done: U7 649417d — brief template refused rules; rule 8 human-supplied content; both protocols prune first / remove own last, skip list, gate-once sentence; handbook §7 §17; H-066/H-068/H-069 resolved-by-doc, H-067 protocol half; green 3/3 (4576).

Done: U8 c6b70c1 — docs/OPERATIONS.md (added), scripts/capture-quota-stop.sh (added), doctor `worktrees` WARN; tests/test_runbook.py (added); H-067 resolved; orchestrator check: 5 real secret values on disk, 0 in OPERATIONS/HARNESS-PROBE/script; green 3/3 (4614). Carry to U9: INTEGRATION §4 doctor `worktrees` row.

Done: U9 6fc7e6e — INTEGRATION nvm PATH (replaces, unexpanded), go/kit apply, CLAUDE_CONFIG_DIR transcript, doctor worktrees, kit WARN, pointers; handbook §11 §18; README; phone.py docstring; green 3/3 (4625).

In progress: U10 final report (report: commit), PR mission-24 -> main,
hosted review wait (<=10 one-minute steps), fixes, ## Hosted review table,
archive, tree back to main. Done means: PR open, table committed, on main.

Standing constraints: one foreground sub-agent per unit, commit and push every
unit to `mission-24`, ./scripts/check green three consecutive runs before each
commit (each a foreground call, 20-minute timeout), explicit paths only in
`git add` (never `-A`), reports drafted under meta/drafts/, DESIGN.md is not
edited by builders (file a finding), sub-agents do not edit meta/plan.md or
this file, retry a failed unit once then `[b]`; `refused:` → `[b] refused`,
no retry. Not touched: the backend seam, credential profiles, the polish
round, any M9 command (missions 25, 26).
