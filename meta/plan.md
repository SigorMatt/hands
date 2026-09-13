# plan — mission 10 (the closed loop and the architect's tools)

Source: meta/BUILDER-10-PROMPT.md, DESIGN v3.9 §26 (with §4, §8, §10, §11,
§13), meta/reviews/REVIEW-9.md. Units run in order; each ends with a commit and
a push. `[x]` = done and pushed, `[b]` = blocked (two failures).

Base of the mission: 61e1486 (`plan: mission 10 kit (DESIGN v3.9, handbook,
templates)`).

- [ ] U0 Plan and corrections (`plan:`) — this file, meta/CHECKPOINT.md;
      REVIEW-9 SF2 (docs/INTEGRATION.md `done` statement follows §6), SF4
      (H-017 dated correction, appended); H-018 filed (§26 decisions; gaps:
      `origin: phone` outside §6, `go` after a stop would not chain, SF2's
      code half)
- [ ] U1 REVIEW-9 SF1 and SF3 (+ SF2 code half, H-018 gap 3)
- [ ] U2 `[series] kickoff` and `go` (§10, §11, §26; H-018 gaps 1, 2)
- [ ] U3 Kit transport (§26, §13)
- [ ] U4 Who by pid (§26)
- [ ] U5 `hands kit check`; handbook and templates against the code (§4, §26)
- [ ] U6 The closed loop in the docs; doctor rows (§26)
- [ ] U7 Final report — meta/FINAL-REPORT-10.md (drafted under meta/drafts/)

Deviation. REVIEW-9 SF2 said "fail on the subtype, or make the doc say what the
code does"; §26 says the doc matches §6, and §6 fails an `error` result. A
doc that follows §6 over code that does not would overclaim, so U1 also
carries the runner change (H-018 gap 3). Between U0 and U1 the doc is ahead of
the code by that one case.

Review items by unit. REVIEW-9 SF1, SF3 → U1; SF2 → U0 (doc) + U1 (code);
SF4 → U0.

Dependencies. U2 and U3 both touch the phone channel (`cmd_topic`) and U3
adds `[files]` keys; U3 after U2. U5 reads `[series] kickoff` (after U2). U6
reports `go` and kit transport in doctor (after U2, U3). U1 and U4 are
independent.

Findings. H-018 filed by U0. H-001 and H-009 stay open.
