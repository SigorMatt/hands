# plan — mission 3 (close the review)

Source: meta/BUILDER-3-PROMPT.md. Units run in order; each ends with a
commit and a push. `[x]` = done and pushed, `[b]` = blocked (two failures),
`[y]` = yielded under budget pressure.

Base of the mission: fa409e6 (`plan: mission 3 kit (DESIGN v3.2)`), green
here (ruff clean, 521 passed, cli smoke) before U0.

Every unit but U0 closes a named should-fix of `meta/reviews/REVIEW-2.md`.

- [x] U0 Plan — this file, meta/CHECKPOINT.md reset, journal.md:17 sha fixed (should-fix 6)
- [x] U1 Status describes the deciding monitor (should-fix 2, §4)
- [ ] U2 Tests that can fail (should-fix 3 and 8)
- [ ] U3 Pause keeps the first reason (should-fix 4, §10, §19)
- [ ] U4 Empty `resume_line` refused (should-fix 5, §6, §19)
- [ ] U5 notify status on failure (should-fix 7, §4, §19)
- [ ] U6 Guard fix and guard tests (§19)
- [ ] U7 `hands send --prompt-file PATH` (§4, §12, §19)
- [ ] U8 Final report — meta/FINAL-REPORT-3.md, then the verdict line

No order deviation is planned: the base is green, so every unit is gated
normally and runs in the order above.

Yield order under quota pressure (BUILDER-3-PROMPT "Budget guidance"):
U1, then U5. Never yield U0, U2, U3, U6, U7, U8.

Review items closed by unit: 1 by the brief's own acceptance wording (the
architect amended it — `only_if_run_in` is now allowed at the refusal site,
its tests and the migration note), 2 by U1, 3 and 8 by U2, 4 by U3, 5 by U4,
6 by U0, 7 by U5. U6 and U7 are DESIGN §19 work, not review items.

Findings filed by this mission's U0, both design-side (builders may not edit
DESIGN.md, so they are memos, not units): H-009 (§4's prose example line at
DESIGN.md:258 omits `--origin`, carried over from REVIEW-2 Notes), H-010
(§12 requires `MultiEdit` in the driver deny list; the tool does not exist in
Claude Code 2.1.x, and U6's brief directs the opposite).
