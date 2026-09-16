# plan — mission 16 (the guard's language finished, review 15)

Source: meta/BUILDER-16-PROMPT.md, DESIGN v3.15 §32 (with §6, §8, §12, §30,
§31), meta/reviews/REVIEW-15.md, findings H-030, H-031, H-032. Units run in
order; each ends with a commit and a push. `[x]` = done and pushed, `[b]` =
blocked (two failures).

Base of the mission: 31789c6 (`plan: mission 16 kit (DESIGN v3.15)`).

- [x] U0 Plan and bookkeeping (`plan:`) (the commit that carries this line) — this file, meta/CHECKPOINT.md;
      H-033 filed (the guard's language finished, reviews 11–15); §32's
      resolutions appended to H-030, H-031, H-032 and their status lines set;
      FINAL-REPORT-15 §3.1 corrected by appended dated lines (the guard's
      `for`/`${…}` execution and `$o` option bypass, unbounded role-mode
      reads, architect `unzip` with no `-d`)
- [ ] U1 The guard's language, finished (§32; blocker 1; should-fix 7) —
      `$`, `{`, `}` and every reserved word refused before tokenizing in
      every mode; the tables judge every word including values; role-mode
      reads confined to the clone and the spool's paths with a refusal that
      says so; unreachable code removed and listed; every probe of reviews
      11–15 blocked in all three modes; every command of driver/CLAUDE.md and
      architect/CLAUDE.md allowed; a 10k fuzz corpus over reserved words and
      `$`/brace shapes refused; docs/INTEGRATION.md states the whole language
- [ ] U2 Architect mode and `hands kit file <dir>` (§32; blocker 2; H-030) —
      `unzip` and `zip` rows removed; `mkdir`/`cp`/`mv` confined with no
      option naming another path; `kit file <dir>` under `HANDS_KITS` builds
      the zip, checks it against the clone, refuses a failing kit with the
      check's output, files the held apply (`origin: architect`, a
      daemon-minted `kit_id`); the reviewer's `unzip` probes refused;
      architect/CLAUDE.md, architect/README.md, docs/ARCHITECT-HANDBOOK.md say
      directory kits
- [ ] U3 Autonomy and origins (§32; blocker 3; should-fix 1, 2, 3;
      H-032) — engine approval only for a daemon-created apply with a known
      `kit_id` under role + autonomous; a socket client cannot set `origin:
      architect`; the kickoff rule fires only for such an apply; `next kit`
      waits for the filed `kit_id` within `[series] kit_wait_s` (default
      600); the budget anchored to `[series] name`, a rename refused unless
      `max_architect_consults` is restated; `Api.send` refuses `driver` and
      `architect`; end-to-end tests including the reviewer's forged-origin probe
- [ ] U4 Config, doctor, prompt, notifications (§32; blocker 4; should-fix 4,
      5, 6) — `architect = "role"` without `[roles.architect]` refused by the
      loader (`handsd`) and by `kit check`; doctor's architect row checks the
      push URL, `HANDS_KITS` under the cwd, both matchers naming the guard,
      the guard's architect-mode self-test; the consult prompt carries the
      next unmet milestone and the roadmap's path; daemon start publishes
      exactly one notification (count bound by a test); the INTEGRATION
      sentence on published kinds corrected
- [ ] U5 Playbook severity (§32) — `monitor.task_killed → notify` verified and
      pinned in the example, this repository's playbook and both templates;
      docs/PLAYBOOK.md says why
- [ ] U6 This repository's playbook — `[series] kickoff` becomes BUILDER-17's
      line; nothing else; loads; a kit of this brief checked `--repo .` exits 0
- [ ] U7 Final report (meta/FINAL-REPORT-16.md) — drafted under meta/drafts/,
      moved in by this commit with the mission's meta bookkeeping

Review items by unit. REVIEW-15 blocker 1 → U1; blocker 2 → U2; blocker 3 →
U3; blocker 4 → U4; should-fix 1, 2, 3 → U3; should-fix 4, 5, 6 → U4;
should-fix 7 → U1.

Scope choices (orchestrator's):
- H-032's resolution (refuse direct sends to `driver` and `architect`) is
  product work and goes with U3.
- The base commit 31789c6 is red (5 failures): the kit changed
  architect/CLAUDE.md's `kit file` line, architect/README.md's setup line,
  DESIGN §6's `decided_by` list and PLAYBOOK.toml's `monitor.task_killed`
  mapping, and U0's own H-030 status line trips the doc test that kept
  INTEGRATION.md naming H-030 open. A red base makes "green three times before
  every commit" impossible, so a sub-agent brought the four tests and
  INTEGRATION.md's two passages in line without product code, and they are
  folded into the U0 `plan:` commit (as mission 15 U0 did). H-031's equality
  therefore lands in U0, not U3; U5 still verifies and pins all four playbooks.
- architect/README.md's first setup line, as the kit shipped it, puts the
  comment before `&& cd ~/hands-architect/<project>`, so the `cd` never runs
  and the following `cp` lines run in the wrong directory. U2 edits that file
  for directory kits and fixes the line (the switch-point pin in
  tests/test_docs.py moves with it).
- Review 15's Notes (U0's doctor brief-check gaps, doctor's matcher spellings,
  U4's empty `escalate_on` default, limits never resuming architect jobs, the
  commit-body wording flaws) are observations, not items, and are not taken.

Dependencies. U1 rewrites the guard's language and U2 edits architect mode in
the same file: U1 first. U3 files applies with a `kit_id` that U2's `kit file`
mints through the daemon: U2 first. U4's doctor row self-tests the guard's
architect mode as U1 and U2 leave it: after both. U5 and U6 touch playbooks
only. U7 last.

Findings. H-033 filed by U0. H-030, H-031, H-032 resolved by DESIGN v3.15
(code: H-030 U2, H-031 U0, H-032 U3). H-027, H-001 and H-009 stay open.
