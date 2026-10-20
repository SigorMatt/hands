# CHECKPOINT

Mission: 28 (meta/BUILDER-28-PROMPT.md, DESIGN v3.27 §44 with §6, §10,
§19, §31, §32, §33, §36, §38, §39, §43; meta/reviews/REVIEW-27.md;
FINDINGS H-077, H-078).
Branch: `mission-28`, from main b943019; every unit commits and pushes to
it; U5 opens the PR, reads the hosted review, fixes, returns the tree to main.

Done: U0 (`plan:`) — plan, branch, findings (H-078 filed "decided (DESIGN
§44), scheduled for U1 and U2"; H-077 "decided (DESIGN §44 ...), scheduled
for U4"). Green 3/3 (5056). Pushed; `origin/mission-28` exists.

Done: U1 d367373 — human pause (paused_by cli/phone) keeps role ends one per
role in pipeline.json, notify ends fire, resume rules fire until a stop is
suppressed (marked), suppressed stops notified; go/consult refused naming
resume; resume reloads/refuses/replays/discards; kept lines, status,
show resumed_from; §19 rows for the two new titles; 30 tests in
tests/test_human_pause.py + 1 phone; 8 older tests moved from pause to a
rule's stop; green 3/3 (5087). Not proven: at rest (U2); §6 resume only in
an engine test.

Done: U2 adb061b — `hands: at rest` once per human pause (mark in
pipeline.json; republished on a kept end replaced after it), checked at
pause, job ends, deny, queued cancel, spawn failure (playbook, limits,
daemon, api); handbook §10/§14/§18/§19 (rows at rest, go, consult, resume
refused, kit; architect/builder row split), PLAYBOOK.md "A human pause",
OPERATIONS.md "A quiet moment"; table reader matches at a row's start;
H-078 resolved; green 3/3 (5101). Not proven: the check after a spawn
failure (untested); a §6 resume that gives up later is a stop, no at rest;
the release routine's paused-at-restart warning is not in OPERATIONS.md,
left for the install.

Done: U3 0892937 — hold reason computed in a worker thread
(Daemon.decide_held_reason awaited in Api.send before job.held is filed;
_publish_held async; _held_reason removed); runner.turn_env shared by
job_env and both doctor --live turns; 3 tests + 1 doctor (2 hook states),
red with the fix reverted; green 3/3 (5105). Not proven: defer_hold still
runs kit_apply_problem on the loop; HANDS_DOCS/CLONE/KITS of live turns.

Done: U4 d20e511 — spool.carries_playbook (casefolded configured path via
playbook_repo_path + the two fixed names) for the engine hold, the published
reason and kit check's WARN; kit check names the known paths, without a
configuration only the fixed names; H-077 resolved; green 3/3 (5125). Not
proven: handsd's kit check reads the configured path root-relative when the
cwd is below the root; git unable to name the prefix; a real
case-insensitive filesystem; the handbook's §43 lines still name the two
exact paths.

Done: U5 8453b8a (report), 58deee7 (playbook: hosted findings 1, 3, 4, 6),
885f07c (daemon: hosted findings 2, 5; docs/PLAYBOOK.md), (this commit) the
Hosted review table + archive PR-8/1..4; finding 7 dismissed (§44 rule 3);
fetch 4: 1 of 7 open (7). Final tip gate green 3/3 (5137).
Mission 28 — FINISHED after this push; PR #8 open; tree returns to main.

Standing constraints: one foreground sub-agent per unit, commit and push every
unit to `mission-28`, ./scripts/check green three consecutive runs before each
commit (each a foreground call, 15-minute / 900000 ms timeout, written
`./scripts/check; echo "check-exit=$?"`), explicit paths only in `git add`
(never `-A`), reports drafted under meta/drafts/, DESIGN.md is not edited by
builders (file a finding), sub-agents do not edit meta/plan.md or this file,
retry a failed unit once then `[b]`; a `refused:` report is not retried. Not
touched: the pull-request gate, the harness seam, review 25's should-fix 2
and 3, a local-model harness, any M9 command, credential profiles,
docs/ARCHITECT-INSTRUCTION.md, this repository's PLAYBOOK.toml; no host
change.
