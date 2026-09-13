# CHECKPOINT

Mission: 11 (meta/BUILDER-11-PROMPT.md, DESIGN v3.10 §27)
Unit in progress: U2 Who by the sessions file (§27; H-020; REVIEW-10 blocker 1).
Base: 0fef436. Done: U0 e8daca8 (1550); U1 efe4d56 (1573, green 3/3).
Intent: `hands who` reads `~/.claude/sessions/<pid>.json` for each interactive
`claude` pid, takes its `sessionId` (reads only `pid` and `sessionId`, never a
`.key` file), and attributes that transcript; with no sessions file the line
says `transcript: by directory` and a transcript belonging to a hands job
(known pids) is never attributed to a session.
Done means: a fixture with two transcripts in one directory and two sessions
files attributes each by pid; the job-in-same-cwd case shows nothing under the
human's session; `./scripts/check` green three consecutive runs; one commit
listing every file; pushed.
Standing constraints: one foreground sub-agent per product unit, commit and
push every unit, ./scripts/check green three consecutive runs before each
commit, explicit paths only in `git add` (never `-A`), reports drafted under
meta/drafts/, DESIGN.md is not edited by builders (file a finding), sub-agents
do not edit meta/plan.md or this file.
