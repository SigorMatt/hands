# plan — mission 12 (close review 11)

Source: meta/BUILDER-12-PROMPT.md, DESIGN v3.11 §28 (with §8, §10, §12, §27),
meta/reviews/REVIEW-11.md, findings H-022, H-023. Units run in order; each ends
with a commit and a push. `[x]` = done and pushed, `[b]` = blocked (two
failures).

Base of the mission: bb9aab5 (`plan: mission 12 kit (DESIGN v3.11)`).

- [x] U0 Plan and bookkeeping (`plan:`) 5ea7b9d — this file, meta/CHECKPOINT.md;
      FINDINGS: H-018..H-021 resolutions moved into their own sections, status
      lines in place (SF5); H-022 §28 resolution, resolved; H-023 filed
      (blocker 3); SF4 `done` statement pinned per `failure_reason` value
- [x] U1 The guard on shlex (§28; blocker 1) 3966f9b — shlex segments and
      tokens; every REVIEW-11 probe blocked in role mode (verdict stated in
      normal mode), plus `2>f`, `&>f`, `$SHELL -c`, `--project` on a role send;
      self-test 154/154; residual characters counted in expansion position
      only (H-024); unset HANDS_CONSULT_ROLE refuses every role send; `-C`
      not pinned to the clone; `--gate` on a role send allowed
- [ ] U2 Consult and the driver role, engine-side (§28; SF1, SF2, SF3, SF8) —
      engine stops, driver.killed/orphaned/limited events, max_consults
      counter, doctor driver row, HANDS_CONSULT_ROLE in the driver job's
      environment; docs/PLAYBOOK.md, docs/INTEGRATION.md
- [ ] U3 Kit transport and the apply (§28; blocker 2, SF6, SF7, SF9) — URL
      checks in the try, kit check named paths, apply-verdict exception to
      one rule, KIT.md line rules and shell-quoting
- [ ] U4 Sweep and who (§28; blockers 3, 4; H-023)
- [ ] U5 This repository's playbook — kickoff BUILDER-13; kit of
      meta/BUILDER-12-PROMPT.md with `--repo .` exits 0 (blocker 5 per H-022)
- [ ] U6 Final report — meta/FINAL-REPORT-12.md

Review items by unit. REVIEW-11 blocker 1 → U1; blocker 2 → U3; blockers 3, 4
→ U4; blocker 5 → U0 (H-022 resolution) and U5 (the acceptance form); SF1,
SF2, SF3, SF8 → U2; SF4, SF5 → U0; SF6, SF7, SF9 → U3.

Scope choices (orchestrator's):
- U0's SF4 test is product-tree work (tests/test_docs.py), so a sub-agent
  writes it without committing; the orchestrator commits it with the meta
  files as the one `plan:` commit.
- REVIEW-11 Notes (sessions-file staleness, journal-line race, resolved
  `notify` buzz) are outside §28 and not taken.

Dependencies. U5 needs U2 (the playbook must load under the engine-side
stops) and U3 (kit check's named-path and verdict rules). U1, U3, U4 are
independent of each other.

Findings. H-022 resolved by v3.11 (U0). H-023 filed (U0), code U4. H-001 and
H-009 stay open.
