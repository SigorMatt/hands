# plan — mission 7a (review 6 and the harness)

Source: meta/BUILDER-7-PROMPT.md. Units run in order; each ends with a
commit and a push. `[x]` = done and pushed, `[b]` = blocked (two failures),
`[y]` = yielded under budget pressure.

Base of the mission: db0bd2c (`plan: mission 7a kit (DESIGN v3.6, review
base)`) — **red** here before U0: ruff clean, 2 failed, 1110 passed. The kit
changed two texts the suite pins verbatim (§12 rule 8 gained the exit-2
sentence; §10's example review prompt lost `{job.head_at_start}`).

Order deviation, recorded: 169ce88 (`driver: rule 8 and the §10 example
follow the v3.6 kit`) runs before U0, because no unit can pass the gate on a
red base. It makes `driver/CLAUDE.md` rule 8, the §10 fixture and
`docs/PLAYBOOK.md`'s copy follow the kit, and moves two playbook tests to the
new literal prompt. Green three runs after it: 1112 passed (65.04s, 62.45s,
59.88s). It takes the mechanical half of U5's example-rule change; U5 keeps
the prose.

- [x] U0 Plan and corrections — this file, meta/CHECKPOINT.md, `.gitignore`
      gains `meta/drafts/`; README's open-question sentence rewritten
      (blocker 1); dated correction to FINAL-REPORT-6 §1 U5 item 7 naming
      `notify --test` (blocker 2); root CLAUDE.md's foreground sub-agent
      line; H-014 filed with the decision
- [x] U1 Harness termination is `failed` — three failure signals,
      `failure_reason`, `CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0` unless the
      new `[roles.<r>] env` sets it, doctor reports it; `builder.failed →
      resume` end to end (§2, §6, §13, H-014)
- [x] U2 The hook covers background sub-agents (§2, §23)
- [x] U3 Doc-truth as a property — the sweep reads every tracked text file;
      the README and test_playbook wordings join the phrase list; the U6
      tests become non-circular (blocker 1, should-fix 1, 2)
- [x] U4 Client seams — one tree walk for UTF-8 and size; positionals
      refused under `job`/`path`/`prompt` (should-fix 4, 5)
- [ ] U5 Review base — docs/PLAYBOOK.md and the example describe "every
      commit after the last `review:` commit"; the kit's REVIEW-PROTOCOL
      verified unchanged (§10, §23)
- [ ] U6 Final report — meta/FINAL-REPORT-7.md (drafted under meta/drafts/),
      then the verdict line

Review items by unit. Blocker 1 → U0 (the README sentence) and U3 (the sweep
that would have seen it). Blocker 2 → U0 (the correction). Should-fix 1 → U3.
Should-fix 2 → U3 (non-circularity). Should-fix 3 → U0 (`.gitignore`) and the
execution model (drafts outside `git add`, explicit paths only). Should-fix 4
→ U4. Should-fix 5 → U4. Should-fix 6 → DESIGN v3.6 §11, which the architect
rewrote (§23 bullet 1); U6 records it as closed by the design, with no builder
unit.

Yield order under quota pressure: U4, then U3's non-circularity half. Never
yield U0–U2, U5, U6.

Findings. H-014 filed and decided by U0, closed on disk by U1 and U2. H-001
and H-009 stay open (as at mission 6's end).

Not this mission: mission 7b (detectors, the phone channel, `hands who`;
meta/BACKLOG.md).
