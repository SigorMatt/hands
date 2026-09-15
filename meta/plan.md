# plan — mission 13 (close review 12, the sweep, two projects)

Source: meta/BUILDER-13-PROMPT.md, DESIGN v3.12 §29 (with §5, §12, §13, §26,
§28), meta/reviews/REVIEW-12.md, findings H-023, H-024, H-025. Units run in
order; each ends with a commit and a push. `[x]` = done and pushed, `[b]` =
blocked (two failures).

Base of the mission: 723dbeb (`plan: mission 13 kit (DESIGN v3.12)`).

- [x] U0 Plan and bookkeeping (`plan:`) (this commit) — this file, meta/CHECKPOINT.md;
      H-024 v3.12 reading, resolved; H-025 option (b) with §29 text; H-023
      closes with U2; SF8 table-driven `done` order and precedence test;
      FINAL-REPORT-12 §3 item 2 and REVIEW-11 blocker 1 row corrected
- [ ] U1 The guard: comments, the reading, the clone pin (§29; blocker 1,
      SF2; H-024)
- [ ] U2 The sweep after the reap (§29; H-025 b; H-023; blocker 3)
- [ ] U3 Kit transport and kit check (§29; blocker 2; SF1, SF6, SF7)
- [ ] U4 Consult edges (§29; SF3, SF4, SF5)
- [ ] U5 Who grace (§29; SF9)
- [ ] U6 Two projects on one laptop (§29)
- [ ] U7 This repository's playbook (kickoff BUILDER-14)
- [ ] U8 Final report (meta/FINAL-REPORT-13.md)

Review items by unit. REVIEW-12 blocker 1 → U1; blocker 2 → U3; blocker 3 →
U2; SF1, SF6, SF7 → U3; SF2 → U1; SF3, SF4, SF5 → U4; SF8 → U0; SF9 → U5.
REVIEW-11 blocker 1 → U1 (the comment hole reopened it); blocker 3 → U2.

Scope choices (orchestrator's):
- U0's SF8 test is product-tree work (tests/test_docs.py), so a sub-agent
  writes it without committing; the orchestrator commits it with the meta
  files as the one `plan:` commit (as mission 12 U0 did).
- REVIEW-12 Notes (`http://a.com:+80/`, empty alternative `(question|)`, a
  started-but-failed kit apply counting, queued-cancel driver untested) are
  outside §29 and not taken unless a unit's sub-agent finds them in its path.

Dependencies. U6 touches the spool paths every other unit reads, so it runs
after U1–U5. U5 (who grace) and U6 (`hands who` over every spool) both touch
who.py; U5 first. U7 needs U3 (kit check's named-path rules) since its gate
is a kit check. U1, U2, U3, U4 are independent of each other.

Findings. H-023 closes with U2. H-024 resolved by v3.12 (U0). H-025 option
(b) chosen by v3.12 (U0), code U2. H-001 and H-009 stay open.
