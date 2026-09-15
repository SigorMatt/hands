# CHECKPOINT

Mission: 13 (meta/BUILDER-13-PROMPT.md, DESIGN v3.12 §29 with §5, §12, §13,
§26, §28) — close review 12, the sweep (H-025 b), two projects on one laptop.
Base: 723dbeb (`plan: mission 13 kit (DESIGN v3.12)`).

Unit in progress: U3 Kit transport and kit check (§29; REVIEW-12 blocker 2,
should-fix 1, 6, 7).
Intent: `idna.encode(host)` as the host check (idna an explicit dependency),
the reviewer's five hosts refused before any fetch; the kit name shell-quoted
in the apply prompt; `kit check` judges every named path including bare
relative names and names in parentheses; the apply-verdict exception stated
in the code's terms and enumerated by a test.
Done means: tests; ./scripts/check 3/3; pushed.
Done: U0 b79d908 (1994); U1 eccc3a1 (2092); U2 ea7f1bc (2098).

Standing constraints: one foreground sub-agent per product unit, commit and
push every unit, ./scripts/check green three consecutive runs before each
commit, explicit paths only in `git add` (never `-A`), reports drafted under
meta/drafts/, DESIGN.md is not edited by builders (file a finding), sub-agents
do not edit meta/plan.md or this file, retry a failed unit once then `[b]`.
