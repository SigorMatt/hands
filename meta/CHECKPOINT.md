# CHECKPOINT

Mission: 1 (meta/BUILDER-1-PROMPT.md) — FINISHED 2026-09-11
Unit in progress: none
Intent: -
Done means: -
Tip: all of U0..U11 committed and pushed on `main`; `./scripts/check`
green (ruff + 488 tests + CLI smoke); `meta/FINAL-REPORT-1.md` holds the
account, including the twelve NOT PROVEN items and the two acceptance
checks that are the human's to run:
  1. On the laptop with a real `claude`:
     `hands send --role builder --context clear 'Reply with exactly this
     line and nothing else: VERDICT: hello'` yields a record whose
     `result` is that line.
  2. From the driver session, the background-wake check that
     `hands doctor` prints (note finding H-007: `hands pause` writes no
     inbox event, so the check uses a gated send and `hands deny`).
Open for the architect: findings H-001, H-002, H-004, H-005, H-006, H-007
in meta/findings/FINDINGS.md.
Standing constraints: unchanged for the next mission — one sub-agent per
unit, commit and push every unit, ./scripts/check green, DESIGN.md is not
edited by builders.
