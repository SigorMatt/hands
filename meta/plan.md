# plan — mission 14 (the guard's language, close review 13)

Source: meta/BUILDER-14-PROMPT.md, DESIGN v3.13 §30 (with §11, §12, §28,
§29), meta/reviews/REVIEW-13.md, finding H-026. Units run in order; each ends
with a commit and a push. `[x]` = done and pushed, `[b]` = blocked (two
failures).

Base of the mission: c958a62 (`plan: mission 14 kit (DESIGN v3.13)`).

- [x] U0 Plan and bookkeeping (`plan:`) (this commit) — this file, meta/CHECKPOINT.md;
      H-026 filed; FINAL-REPORT-13 REVIEW-11 blocker 1 row corrected by a
      dated line; SF8 `killed` over `limited`: INTEGRATION clause and a
      PRECEDENCE row (runner unchanged; red on the limit-before-cancel swap)
- [ ] U1 The guard's language (§30; blocker 1; SF1) — pre-tokenize refusal
      of newline, CR, `<`, `>`, `#`, backtick, `$(`, `\`, `$'`, control
      characters (first offender + position); `$`/`!` in double quotes
      refused; comment/heredoc/redirection/expansion-position code and its
      tests removed; `git -C` pin by realpath; every review 11–13 probe
      blocked both modes; INTEGRATION one-paragraph language
- [ ] U2 Kit check names and who's configs (§30; blockers 2, 3) — bare
      relative names and handbook punctuation shapes in a fixture; `hands
      who` loads each config in its own try, broken one as a root line
- [ ] U3 Config edges (§30; blocker 4; SF6) — `[who] grace_s` finite and
      ≥ 0; project names `[A-Za-z0-9][A-Za-z0-9._-]{0,63}` (file name and
      `--project`)
- [ ] U4 Sweep, doctor, consult (§30; SF2, SF3, SF4, SF5) — unmarked
      session member is the job's; pipe-timeout test bound to the config;
      doctor checks the hook command names and runs the guard; max_consults
      anchor persisted in the spool
- [ ] U5 Notifications and the playbooks (§30; SF7) — 1.1 s between paired
      publishes; no `job.held → notify` rule in PLAYBOOK.toml or templates,
      a template with it still loads; retired unit references removed
      outside the changelog
- [ ] U6 This repository's playbook — `[series] kickoff` BUILDER-15; kit of
      BUILDER-14 `--repo .` exits 0
- [ ] U7 Final report (meta/FINAL-REPORT-14.md) — drafted under meta/drafts/

Review items by unit. REVIEW-13 blocker 1 → U1; blocker 2 → U2; blocker 3 →
U2; blocker 4 → U3; SF1 → U1; SF2, SF3, SF4, SF5 → U4; SF6 → U3; SF7 → U5;
SF8 → U0.

Scope choices (orchestrator's):
- U0's SF8 test is product-tree work, so a sub-agent writes it without
  committing; the orchestrator commits it with the meta files as the one
  `plan:` commit (as missions 12 and 13 U0 did).
- SF7's `DESIGN.md:644` (§14 layout, `systemd/handsd.service`) is outside a
  changelog section and builders may not edit DESIGN.md: U5 files a finding
  for it. `DESIGN.md:921` is in §24, a changelog section, and stays.
- REVIEW-13 Notes (numeric IPv4 spellings, confusables, the paused branch
  outside the engine try, who loading configs twice, a kickoff naming a
  missing brief, `ended` set at restart) are outside §30 and not taken
  unless a unit's sub-agent finds them in its path; U7 lists them.

Dependencies. U2 and U3 both touch config loading used by `hands who`; U2
first. U6's gate is a kit check, so it runs after U2. U1, U4, U5 are
independent of the others.

Findings. H-026 filed by U0 (resolved by DESIGN v3.13; code U1). H-001 and
H-009 stay open.
