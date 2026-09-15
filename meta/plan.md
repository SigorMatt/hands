# plan — mission 14 (the guard's language, close review 13)

Source: meta/BUILDER-14-PROMPT.md, DESIGN v3.13 §30 (with §11, §12, §28,
§29), meta/reviews/REVIEW-13.md, finding H-026. Units run in order; each ends
with a commit and a push. `[x]` = done and pushed, `[b]` = blocked (two
failures).

Base of the mission: c958a62 (`plan: mission 14 kit (DESIGN v3.13)`).

- [x] U0 Plan and bookkeeping (`plan:`) f9e0729 — this file, meta/CHECKPOINT.md;
      H-026 filed; FINAL-REPORT-13 REVIEW-11 blocker 1 row corrected by a
      dated line; SF8 `killed` over `limited`: INTEGRATION clause and a
      PRECEDENCE row (runner unchanged; red on the limit-before-cancel swap)
- [x] U1 The guard's language (§30; blocker 1; SF1) 9a5bc75 — pre-tokenize refusal
      of newline, CR, `<`, `>`, `#`, backtick, `$(`, `\`, `$'`, control
      characters (first offender + position); `$`/`!` in double quotes
      refused; comment/heredoc/redirection/expansion-position code and its
      tests removed; `git -C` pin by realpath; every review 11–13 probe
      blocked both modes; INTEGRATION one-paragraph language; second `-C`
      refused in role mode; 18 allowed rows moved to blocked (`2>&1`,
      `$(…)`, `--stdin <`, `'fix #12'`); REVIEW-11 probes (role-mode
      bypasses) stay allowed in normal mode per §28
- [x] U2 Kit check names and who's configs (§30; blockers 2, 3) e79e770 — bare
      relative names and handbook punctuation shapes in a fixture; `hands
      who` loads each config in its own try, broken one as a root line;
      rule 4 bare names: 3+ capitals/`_` (not VERDICT) or `<Cap>…file`;
      65-row tests/fixtures/named_path_shapes.tsv; all configs broken exits
      1; missing `API`/`HEAD` in a send now fails, `notes`/`REVIEW-13` missed
- [x] U3 Config edges (§30; blocker 4; SF6) 599b993 — `[who] grace_s` finite and
      ≥ 0; project names `[A-Za-z0-9][A-Za-z0-9._-]{0,63}` (file name and
      `--project`); `_number` refuses non-finite for all five number keys;
      name checked in load_config and spool_root (flags, $HANDS_PROJECT,
      who discovery as a config error line); exit 1; `jobs`/`roles` still
      match (INTEGRATION says not to use them)
- [x] U4 Sweep, doctor, consult (§30; SF2, SF3, SF4, SF5) 2ad4356 — unmarked
      session member is the job's; pipe-timeout test bound to the config;
      doctor checks the hook command names and runs the guard; max_consults
      anchor persisted in the spool as `consults_since` (a persisted anchor
      wins; daemon start anchors only when pipeline.json has none); doctor
      15-row table; pipe timeout 2 rows (0.2 s, 1.5 s) no hardcode passes both
- [x] U5 Notifications and the playbooks (§30; SF7) 104666d — 1.1 s between paired
      publishes; no `job.held → notify` rule in PLAYBOOK.toml or templates,
      a template with it still loads; retired unit references removed
      outside the changelog; notify.PAIR_SPACING_S = 1.1 (kit: injected
      sleep between receipt and held apply; limit: resume_delay_s floor);
      H-027 filed for DESIGN.md:541, :644, :921; test_docs pins the kit to
      DESIGN rule 6 with the quoted-text clause substituted
- [x] U6 This repository's playbook fa8fbae — `[series] kickoff` BUILDER-15,
      one line; kickoff test red on the value at a worktree on 104666d; kit of
      meta/BUILDER-14-PROMPT.md `--repo .` pass 6 of 6, exit 0
- [x] U7 Final report (meta/FINAL-REPORT-14.md) (the commit that carries this
      line) — drafted under meta/drafts/; carries the mission's meta
      bookkeeping; mission 14 finished

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
- U1 left `driver/CLAUDE.md` rule 6 and DESIGN §12 rule 6 saying the guard
  "treats quoted text as text", no longer true for quoted `<`, `>`, `#`: U5
  fixes driver/CLAUDE.md in its docs sweep and files a finding for §12.
- REVIEW-13 Notes (numeric IPv4 spellings, confusables, the paused branch
  outside the engine try, who loading configs twice, a kickoff naming a
  missing brief, `ended` set at restart) are outside §30 and not taken
  unless a unit's sub-agent finds them in its path; U7 lists them.

Dependencies. U2 and U3 both touch config loading used by `hands who`; U2
first. U6's gate is a kit check, so it runs after U2. U1, U4, U5 are
independent of the others.

Findings. H-026 filed by U0 (resolved by DESIGN v3.13; code U1). H-001 and
H-009 stay open.
