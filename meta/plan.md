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
- [x] U2 Consult and the driver role, engine-side (§28; SF1, SF2, SF3, SF8)
      e642552 — escalate/unrecognised/failed/killed/orphaned/limited stop and
      notify in the engine whatever the driver rules; spawn failure = killed
      with consult.done; HANDS_CONSULT_ROLE set on the driver job; kickoff
      values seen kept in pipeline.json (recorded at playbook load on job
      start); "`plan:` kit apply" read as a started `origin: kit` builder
      job (prefix not read); limited driver job not resumed; doctor fails on
      settings/hook wiring, role-mode self-test red, permission_flags
- [x] U3 Kit transport and the apply (§28; blocker 2, SF6, SF7, SF9) 043413d
      — URL scheme/host IDNA/port/whitespace in the try, kit.refused, no
      fetch (the review's three URLs); named paths = words with a ≥2-char
      extension, kit then repo, placeholder paths syntax-checked only;
      apply exception only a pattern exactly `VERDICT: kit applied`; every
      regex alternative must match a literal (runs template stub updated);
      KIT.md line rules with default and notice; message shell-quoted;
      prompts byte-equal for the same `~/Downloads/<name>`, unequal for
      another kit_dir or a `-1` rename; BUILDER-12 kit `--repo .` 6/6 exit 0
- [b] U4 Sweep and who (§28; blockers 3, 4; H-023) 7f86406 — who half done:
      the directory fallback excludes every running hands job pid's
      sessions-file `sessionId` (reviewer's probe, two variants). Sweep half
      BLOCKED on design (H-025): the sweep runs after claude is reaped, so a
      live leader never exists and no pid chain reaches the job's pid; §28
      read literally kills nothing and three §24 orphan tests fail (one
      hangs on pipes). U1-of-m11's `HANDS_JOB` rule stays. Not retried: a
      design stop, the same rules reach the same memo
- [x] U5 This repository's playbook 1250817 — kickoff BUILDER-13 (one line);
      kickoff test moved to BUILDER-13, red first on a HEAD-equal playbook;
      kit of meta/BUILDER-12-PROMPT.md with `--repo .` 6 of 6, exit 0
      (blocker 5 per H-022); BUILDER-13 not yet written
- [x] U6 Final report (the commit that carries this line) —
      meta/FINAL-REPORT-12.md (drafted under meta/drafts/); mission ends
      `blocked U4` (sweep half, H-025)

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
