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
- [x] U1 The guard: comments, the reading, the clone pin (§29; blocker 1,
      SF2; H-024) eccc3a1 — `#` outside quotes refused in both modes with its
      offset (incl. `a#b`, `$#`, inside `$(…)`); braces count only with `,`
      or `..` (`HEAD@{1}` now allowed); in double quotes any `\` counts;
      role-mode `git -C` equals HANDS_CLONE after abspath (unset refuses);
      handsd sets HANDS_CLONE on the driver job (<cwd>/repo, else cwd if a
      repo); doctor self-test uses ./repo; REVIEW-12 probes blocked both
      modes; REVIEW-11 normal-mode allowed rows kept
- [x] U2 The sweep after the reap (§29; H-025 b; H-023; blocker 3) ea7f1bc —
      descent by sid == job pid and start ticks < last-seen-alive ticks
      (recorded at spawn, each 50 ms poll, sweep start) or cgroup scope;
      HANDS_JOB mark neither required nor sufficient (mark rule removed,
      H-023 resolved); per-process signal, every orphan entry carries
      `killed`; `runner.pipe_timeout_s` default 10; residual in INTEGRATION;
      two monitor orphan fakes linger 0.5 s and the cancel test waits for an
      observation after the fork (else the fork is in the residual interval)
- [x] U3 Kit transport and kit check (§29; blocker 2; SF1, SF6, SF7) 126d4ff
      — IP literals by ipaddress, names by idna.encode (reviewer's five
      refused pre-fetch; `a_b.com` now refused); kit file name shlex-quoted
      after `~/Downloads/`; kit.NAMED_PATH_RULE (exists, extension with a
      letter, or `/` with bad syntax or a known leading dir; 42-row table;
      missing bare `Makefile`, `newdir/NOTES` not caught; `e.g.`,
      `github.com` flagged); apply exception = first rule matching the
      literal and no vocabulary literal (vocabulary-matching rules judged
      as vocabulary, catch-all `^VERDICT:` kept); BUILDER-13 kit 6/6 exit 0
- [x] U4 Consult edges (§29; SF3, SF4, SF5) 38022f2 — engine's consult stop
      decided before the paused check: over a pause, one
      `pipeline.stop_suppressed` with the engine's reason and one
      notification (7 kinds × 4 playbook shapes, e2e escalate); no playbook
      rule fires while paused; doctor self-tests the first shlex word naming
      `.claude/hooks/bash_guard.py` ($CLAUDE_PROJECT_DIR / relative resolved
      against the driver dir, other `$` fails); max_consults anchor = latest
      of kickoff, kit apply, daemon start (restart mid-mission resets)
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
