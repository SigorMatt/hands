# CHECKPOINT

Mission: 12 (meta/BUILDER-12-PROMPT.md, DESIGN v3.11 §28 with §8, §10, §12,
§27) — close review 11 (blockers 1–5, should-fix 1–9).
Base: bb9aab5 (`plan: mission 12 kit (DESIGN v3.11)`).
Unit in progress: U1 The guard on shlex (§28; REVIEW-11 blocker 1).
Intent: rewrite the segment and token logic of driver/hooks/bash_guard.py on
`shlex` POSIX tokens: segments split on `;`, `&&`, `||`, `|`, a lone `&`,
newlines, `$(`, backticks, subshell parentheses; option values read from
tokens; tokens in `hands`/`git` argument positions with residual `$`, backtick,
`{`, `}`, `\`, non-leading `~`, `*`, `?`, `[`, `!` refused; leading
assignments and `$'…'` refused; unparsable commands refused; role mode: every
`hands send` carries exactly one `--context` of literal `keep` and a `--role`
equal to `HANDS_CONSULT_ROLE`, other `hands` subcommands outside §27's list
refused by name, `git` only `-C <clone>` plus the read-only allowlist.
Done means: every command allowed before stays allowed (both self-test tables
and tests/test_bash_guard.py); every REVIEW-11 blocker 1 probe asserted
blocked in both modes where applicable; the interactive driver's guard (same
file) fixed; ./scripts/check green 3/3; one commit whose body lists every file
and the probes blocked only after this change; pushed.
Done: U0 5ea7b9d (1733 passed).
Findings: H-022 resolved by v3.11 (U0); H-023 open (code U4); H-001 and H-009
open.
Standing constraints: one foreground sub-agent per product unit, commit and
push every unit, ./scripts/check green three consecutive runs before each
commit, explicit paths only in `git add` (never `-A`), reports drafted under
meta/drafts/, DESIGN.md is not edited by builders (file a finding), sub-agents
do not edit meta/plan.md or this file, retry a failed unit once then `[b]`.
