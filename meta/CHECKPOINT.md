# CHECKPOINT

Mission: 23 (meta/BUILDER-23-PROMPT.md, DESIGN v3.22 §39 with §24, §27,
§31, §35, §38; meta/reviews/REVIEW-22.md; docs/QODO-EXTRACTION.md).
Branch: `mission-23` from main 23eff6c; every unit commits and pushes to
it; U10 opens the PR to main, reads the hosted review, fixes, and returns
the tree to main.

Done: U0 b7b5c10 (`plan:`) — H-055..H-060 filed, H-051..H-054 decided; green 3/3 (4387).

Done: U1 9c5d729 — who stores fp whenever the blanked picture equals the last published one; both-ways comparison pinned; [T,T,F,T] repro now [T,T,F,F]; green 3/3 (4391).

Done: U2 bcc3d53 — orphaned reply/answer published, answer re-sent as keep (origin playbook); start notification by orphan_reason; aux.orphaned in EVENTS + stop records aux + rule in PLAYBOOK.toml and both templates (21 rules); right-secret refusals published titled <command>; match_job_id in api.py (O->0, l/I->1, prefix>=4, ambiguous lists candidates) for approve/deny/cancel (answer/reply carry no id); hold id on own line; docs/PLAYBOOK.md event row; green 3/3 (4407).

Done: U3 e36d558 — builder.done consult regex judged on sample lines; owner fallbacks inclusive with notes; journal-dirty sentence on answer and cli keep/clear to builder; green 3/3 (4424). Carry to U9: the handbook's ruling round sentence (H-060's human half).

Done: U4 0c6d725 — progress reads CHECKPOINT at show-toplevel (falls back to cwd); README names ten commands; INTEGRATION progress bullet corrected; green 3/3 (4426).

Done: U5 59678ee — src/hands/hosted.py (added) + cli hosted-review [--bot]; fake gh recorded pages; archive per comment body+json at repo root PR-<n>/<k>/; categories, findings with anchors, summary id, verdict from Code Review only; diff by id; exit 3 no bot comment (also when no Code Review comment yet, archive kept); green 3/3 (4434).

Done: U6 dc9698e — both protocols: git rm -q -f (plain -q refuses a staged deletion) for files absent at <sha>, git status --short empty after; hosted-review step (fresh sub-agent, worktree at origin/<branch>, archive after the builder's, copied to main with the review); brief template last unit; handbook §9; git test of the restore; green 3/3 (4465).

Done: U7 2b4df10 — consult prompt names docs_root() handbook/templates paths; guard: architect reads under HANDS_DOCS, hands handbook allowed (architect only); settings allow; rule 2; help text; project.py unchanged (U10 already right, tests added); H-051, H-052 resolved, HF-002 in full; green 3/3 (4474). Carry to U9: INTEGRATION ~l.1157 architect hands commands lack handbook.

Done: U8 a09b85f — git clone -q -- <url>; failed clone/push-url removes everything created newest first, prints removed:, returns 1 before systemctl; pre-existing kept; rules 8 and 13 agree on escalate ruling: <what> + owner draft; green 3/3 (4479).

Done: U9 515b736 — no_background python3 -I (settings, copy line, self-test; planted json.py test); INTEGRATION restart/resume, hooks, pause, [server], handbook/HANDS_DOCS, ids, refusals; handbook status, restart, ids, ruling round; PLAYBOOK aux.orphaned; green 3/3 (4493).

Done: U10 d50af2a (report:) PR #4 opened; 1276251 seven hosted findings fixed (green 3/3, 4504); fetch 6 after the bot's in-place re-review: 4 of 11 open = 3 dismissed + H-061 filed.

U10 final report: commit (this commit): ## Hosted review table, H-061, archive PR-4/1..6, plan, checkpoint, journal.
Mission 23 — FINISHED after this push; tree returns to main. Open for the architect: H-061.

Standing constraints: one foreground sub-agent per unit, commit and push every
unit to `mission-23`, ./scripts/check green three consecutive runs before each
commit (each a foreground call, 20-minute timeout), explicit paths only in
`git add` (never `-A`), reports drafted under meta/drafts/, DESIGN.md is not
edited by builders (file a finding), sub-agents do not edit meta/plan.md or
this file, retry a failed unit once then `[b]`. Not touched: the backend
seam, the polish round, any M8 roadmap work (mission 24).
