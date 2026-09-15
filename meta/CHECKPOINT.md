# CHECKPOINT

Mission: 12 (meta/BUILDER-12-PROMPT.md, DESIGN v3.11 §28 with §8, §10, §12,
§27) — close review 11 (blockers 1–5, should-fix 1–9).
Base: bb9aab5 (`plan: mission 12 kit (DESIGN v3.11)`).
Unit in progress: U3 Kit transport and the apply (§28; REVIEW-11 blocker 2,
should-fix 6, 7, 9).
Intent: attachment URL validation entirely inside the try — scheme http(s),
host non-empty and IDNA-valid, port in range, no whitespace — any failure
files `kit.refused` with the reason and touches no network (the reviewer's
`http://xn--/k.zip`, `http://exa mple.com/k.zip`, `https://[::1]:99999/x`);
`kit check` resolves every file path a `send` prompt names against kit then
repo with the daemon's path syntax, whatever punctuation surrounds it (no
`.md`/`.toml`-only, no `{` skip); the apply-verdict exception applies to
exactly one `builder.done` rule whose regex matches `VERDICT: kit applied
<sha>`, every other rule must match a vocabulary literal (typo'd alternatives
and plain `^VERDICT: kit` fail); `KIT.md` first line is the commit message
only when ≤ 72 chars, no quote characters, no newline, non-empty, else the
default `plan: kit <name>` and the notification says so; the message is
shell-quoted in both the daemon's and `kit check`'s apply prompt.
Done means: tests for each, including byte-equality of the two prompts;
./scripts/check green 3/3; one commit listing every file; pushed.
Done: U0 5ea7b9d (1733 passed); U1 3966f9b (1882); U2 e642552 (1916).
Findings: H-022 resolved by v3.11 (U0); H-023 open (code U4); H-024 open (U1's
residual-character reading); H-001 and H-009 open.
Standing constraints: one foreground sub-agent per product unit, commit and
push every unit, ./scripts/check green three consecutive runs before each
commit, explicit paths only in `git add` (never `-A`), reports drafted under
meta/drafts/, DESIGN.md is not edited by builders (file a finding), sub-agents
do not edit meta/plan.md or this file, retry a failed unit once then `[b]`.
