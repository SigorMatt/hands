# CHECKPOINT

Mission: 27 (meta/BUILDER-27-PROMPT.md, DESIGN v3.26 §43 with §10, §12,
§14, §23, §24, §32, §33, §34, §36, §39, §41, §42; meta/reviews/REVIEW-26.md,
meta/reviews/REVIEW-25.md should-fix 1).
Branch: `mission-27`, from main 1b822a5; every unit commits and pushes to
it; U7 opens the PR, reads the hosted review, fixes, returns the tree to main.

Done: U0 b3e1e76 (`plan:`) — plan, branch, findings (H-074, H-075, H-076 filed;
H-070/H-071 "decided (DESIGN §42, §43), scheduled for U4"; H-073 "decided
(DESIGN §43), scheduled for U2"), FINAL-REPORT-25 correction line. Pushed;
`origin/mission-27` exists.

Done: U1 f10c020 — §43's DESIGN copies (fixture, PLAYBOOK.md, rule-6 exact),
H-027/H-034/H-039 resolved; H-076 race found (kit_zip timestamps; tests
compared a second kit_zip call), fixed in tests, pinned; leads 20/20 green;
three consult refusal tests; green 3/3 (4839).

Done: U2 32446f5 — §43's owner sentence at dispatch for every builder job
but an apply; `sent_prompt` strip helper for every listed reader; handbook
§4/§14/§19; H-073 resolved; tests/harness.py `running_job` waits for a
running record (the gap test_open_refuses_a_running_job hit once — H-076's
lead; to be named in the final report); green 3/3 (4855).

Done: U3 3383ffe — hook rule 1, the wheel ships the hook, one decision
(`config.background_tasks`) for runner and doctor, rules 3–5; INTEGRATION
§21; green 3/3 + once with the variable (4937).

Done: U4 4130616 — both protocols' report contents, the gate's timeout and
the wait rule; brief template and handbook §7; the guard's four options
(selftest 434/434); allow-list; rule 10; H-070/H-071/H-074 resolved; green
3/3 (5008).

Done: U5 37bd194 — the engine holds an architect-filed kit carrying the
playbook (after kit_apply_problem and _kit_bytes_unchanged), §43's published
reason via publish_hold, no engine kickoff after the human approves; kit
check WARN; architect rules 3/8; handbook §3/§6/§12; templates; H-075
resolved; green 3/3 (5041). Not proven: a kit filed while the pipeline is
already paused is held by the daemon itself, reason `apply <name>` only.

Done: U6 38e44ee — §19 rows (load stop, phone follow-up, U5 hold, a
no-message stop rule) and the ast test over playbook/limits/daemon/phone
(12 exemptions; red with each of three rows removed); green 3/3 (5047).

Done: U7 94f709c (report), 3ad66dd (playbook: hosted findings 3, 4), (this
commit) the Hosted review table + archive PR-7/1..3; H-077 filed (finding
1); finding 2 dismissed; fetch 3: 2 of 4 open (1 and 2). Final tip gate
green 3/3 + once with CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1 (5056).
Mission 27 — FINISHED after this push; PR #7 open; tree returns to main.

Standing constraints: one foreground sub-agent per unit, commit and push every
unit to `mission-27`, ./scripts/check green three consecutive runs before each
commit (each a foreground call, 15-minute / 900000 ms timeout, written
`./scripts/check; echo "check-exit=$?"`), explicit paths only in `git add`
(never `-A`), reports drafted under meta/drafts/, DESIGN.md is not edited by
builders (file a finding), sub-agents do not edit meta/plan.md or this file,
retry a failed unit once then `[b]`; a `refused:` report is not retried. Not
touched: the harness seam, review 25's should-fix 2 and 3, a local-model
harness, any M9 command, credential profiles, docs/ARCHITECT-INSTRUCTION.md,
this repository's PLAYBOOK.toml; no host change.
