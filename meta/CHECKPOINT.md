# CHECKPOINT

Mission: 21 (meta/BUILDER-21-PROMPT.md, DESIGN v3.20 §37 with §6, §32,
§35, §36; meta/reviews/REVIEW-20.md). Closer: every unit commits and pushes
to `mission-20` (PR #2 open). Base: 1c68883, merged into mission-20 at 5dfab55.

Done: U0 24aaba3 (`plan:`) — H-046..H-048 filed; green 3/3 (4225).

Done: U1 44f7494 — Spool.transition judges the on-disk record; runner
reloads after advance_clone, no spawn unless queued (RunnerError); cancel
during slow advance ends killed (inbox: job.killed, then §28 consult.done +
stop, nothing after the cancel); green 3/3 (4227).

Done: U2 97d1666 — hooks `python3 -I`; doctor accepts only that form,
self-tests the settings' own command via /bin/sh, FAILS on a module/package
beside the guard; --write refuses nlink>1 regular files and any write while
the kits walk reports; green 3/3 (4251). Left: docs/INTEGRATION.md still
spells `python3 <path>` (outside U2's files; note in the report).

Done: U3 056f044 — socket send with origin phone refused (names answer);
phone `go` now via Api.go_builder (not a socket command; design silent);
architect live: --repo <resolved clone>, FAIL with none, kit check judged
only on live kit + that repo; kits/hands-doctor-live-<8 hex>, FAIL if it
exists, removes only its own; INTEGRATION live paragraph corrected; 3/3 (4258).

Done: U4 3dc5a32 — both protocols: checkout <sha>~1 -- <files>, red,
checkout <sha> -- <files>; no "stash"; pin test both files; 3/3 (4260).

Done: U5 37d2c51 — an engine-approved apply that removes the playbook
stops with "the apply removed <path>", no rule fires; 3/3 (4261).

U6 is the commit that carries this line (meta only): meta/FINAL-REPORT-21.md,
plan, checkpoint, journal.
Mission 21 — FINISHED. Unit in progress: none. U0-U6 `[x]` in meta/plan.md.
PR #2 (mission-20) stays the open PR. Findings H-046..H-048 open (mission 22).
Next: review of mission 21 on PR #2; mission 22 (onboarding + H-046..H-048).

Standing constraints: one foreground sub-agent per unit, commit and push every
unit to `mission-20`, ./scripts/check green three consecutive runs before each
commit (each a foreground call, 20-minute timeout), explicit paths only in
`git add` (never `-A`), reports drafted under meta/drafts/, DESIGN.md is not
edited by builders (file a finding), sub-agents do not edit meta/plan.md or
this file, retry a failed unit once then `[b]`. No onboarding, `hands project
add`, handbook sections, handswho or notification docs (mission 22). The last
unit opens no PR; tree returns to main at the end.
