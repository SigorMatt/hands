# plan — mission 10 (the closed loop and the architect's tools)

Source: meta/BUILDER-10-PROMPT.md, DESIGN v3.9 §26 (with §4, §8, §10, §11,
§13), meta/reviews/REVIEW-9.md. Units run in order; each ends with a commit and
a push. `[x]` = done and pushed, `[b]` = blocked (two failures).

Base of the mission: 61e1486 (`plan: mission 10 kit (DESIGN v3.9, handbook,
templates)`).

- [x] U0 Plan and corrections (`plan:`) cbb8fc8 — this file, meta/CHECKPOINT.md;
      REVIEW-9 SF2 (docs/INTEGRATION.md `done` statement follows §6), SF4
      (H-017 dated correction, appended); H-018 filed (§26 decisions; gaps:
      `origin: phone` outside §6, `go` after a stop would not chain, SF2's
      code half)
- [x] U1 REVIEW-9 SF1 and SF3 (+ SF2 code half, H-018 gap 3) 17ba97e — kill
      tied to claude's recorded start time (also in the post-exit sweep); symlinked
      playbook still refused; other GIT_* vars still inherited
- [x] U2 `[series] kickoff` and `go` (§10, §11, §26; H-018 gaps 1, 2) 067b8fd —
      `[series]` table takes `name` + `kickoff` (TOML forbids `series = "…"`
      beside `[series]`; the templates as written do not parse): H-019 filed,
      templates reconciled in U5; gate runs done in a throwaway worktree because
      the root-playbook test needs PLAYBOOK.toml to match HEAD
- [x] U3 Kit transport (§26, §13) 6852751 — kit_dir outside roots refused on
      arrival (not at load); exclusive os.link to first free name; the phone
      channel reads no other command during a download (up to 300 s), untested
- [b] U4 Who by pid (§26) — blocked on DESIGN, H-020 (9f7effd, memo only): no
      transcript records a pid (470 transcripts, claude 2.1.270); the pid lives
      in ~/.claude/sessions/<pid>.json, a source §26 does not name. Not retried:
      a second run under the same rules stops at the same memo. No code changed
- [x] U5 `hands kit check`; handbook and templates against the code (§4, §26)
      9e962a4 — mission 10 kit passes (6 of 6); templates moved to `[series]
      name` (H-019); verdict check covers `builder.done` rules only, `aux.done`
      review rules counted but unchecked (H-021, §26 as written fails the kit);
      a kit with no brief fails the brief checks
- [x] U6 The closed loop in the docs; doctor rows (§26) 7c5e854 — the apply
      send comes from the laptop or driver (nothing on the phone starts it);
      doctor does not check kit_dir exists or builder busy
- [x] U7 Final report (the commit that carries this line) — meta/FINAL-REPORT-10.md
      (drafted under meta/drafts/); mission ends `blocked U4`

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
