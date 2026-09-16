# plan — mission 15 (the guard's command table, close review 14, the architect role)

Source: meta/BUILDER-15-PROMPT.md, DESIGN v3.14 §31 (with §8, §10, §11, §12,
§26, §27, §30), meta/reviews/REVIEW-14.md, meta/BACKLOG.md "Mission 15 — the
architect role", and the `architect/` kit files (CLAUDE.md, README.md,
settings.json) that arrived with c958a62/1f8141c. Units run in order; each ends
with a commit and a push. `[x]` = done and pushed, `[b]` = blocked (two
failures).

Base of the mission: 1f8141c (`plan: mission 15 kit (DESIGN v3.14, architect
kit)`).

- [x] U0 Plan and bookkeeping (`plan:`) (the commit that carries this line) —
      this file, meta/CHECKPOINT.md; H-028 and H-029 filed; should-fix 7:
      `hands doctor`'s `go` row warns, still green and exit 0, when
      `[series] kickoff` plainly names a file the builder's cwd lacks;
      `spool.ORIGINS` gains `architect`, which DESIGN v3.14 §6 already lists
      and the base commit left red
- [ ] U1 The guard's command table (§31; blocker 1) — `ALLOWED_FIRST_WORDS`
      replaced by a per-command option table in both modes; the reviewer's
      three probes and a regenerated 10k fuzz corpus over the removed words
      blocked; every command in driver/CLAUDE.md and the two self-test tables
      still allowed
- [ ] U2 Notifications and doctor (§31; blocker 2; should-fix 1–6) — spacing on
      every branch with the ordinary-branch (`default_why`) test; one
      daemon-start notification listing re-minted holds; the limit pair
      documented as implemented; doctor judges every Bash `PreToolUse` hook;
      empty project name refused; the `max_consults` anchor's fields read back;
      the bare-name false-positive row pinned
- [ ] U3 Architect guard mode and `hands kit file` (§31) — `HANDS_ROLE=architect`
      in driver/hooks/bash_guard.py, the `--write` entry point,
      architect/settings.json verified against the CLI; `hands kit file <zip>`
      checks the kit against the role's clone, refuses a failing kit, else
      files the held apply with `origin: architect`
- [ ] U4 Series mode and autonomy (§31) — `[series] architect`, `autonomous`,
      `gate_failures`, `escalate_on`, `[limits] max_architect_consults`;
      engine approval of `origin: architect` holds as `decided_by: playbook`;
      the kickoff sent after `VERDICT: kit applied` by an engine rule;
      `architect = "role"` without `[roles.architect]` is a config error
- [ ] U5 Consult for the architect (§31) — `consult` with `role = "architect"`
      on `aux.done`; the prompt carries the event, the review's verdict line
      and its Blockers/Should-fix sections verbatim, the roadmap file and the
      instruction; `next kit` | `series complete` | `escalate` matched;
      escalation notification with the session id and the `claude --resume`
      line; `max_architect_consults` per series; `budget-exhausted` is the
      engine's
- [ ] U6 Docs and the templates — docs/INTEGRATION.md (the architect role, the
      switch point, the two-project note), docs/PLAYBOOK.md (new keys and
      events), both templates gain a commented architect block,
      docs/ARCHITECT-HANDBOOK.md §12 role-mode onboarding, `hands doctor`
      reports the architect role
- [ ] U7 This repository's playbook — `[series] kickoff` becomes BUILDER-16's
      line; `architect = "phone"` stated explicitly; nothing else
- [ ] U8 Final report (meta/FINAL-REPORT-15.md)

Review items by unit. REVIEW-14 blocker 1 → U1; blocker 2 → U2; should-fix 1,
2 → U2; should-fix 3, 4, 5, 6 → U2; should-fix 7 → U0.

Scope choices (orchestrator's):
- The brief names the two new findings H-027 and H-028, but H-027 was filed by
  mission 14 U5 and is open. The ledger is append-only and numbers are not
  reused, so they are filed as **H-028** (the guard's command table) and
  **H-029** (the architect role). The brief's intent — two findings, those two
  subjects — is unchanged.
- U0's should-fix 7 is product-tree work, so a sub-agent writes it without
  committing; the orchestrator commits it with the meta files as the one
  `plan:` commit (as missions 12, 13 and 14 U0 did).
- The mission's base commit 1f8141c is red: DESIGN v3.14 §6 lists
  `origin (…|kit|architect)` while `spool.ORIGINS` and
  `tests/test_docs.py::test_the_origin_listings_name_kit` carry the v3.10 list.
  The writer of an `architect`-origin job is U3, but a red base makes "green
  three times before every commit" impossible for every unit before it, so the
  one-word frozenset change and its test are folded into U0. Nothing reads or
  writes the value until U3.
- The mission-14 U1 fuzz corpus was not kept in the tree (no fixture, no test
  references it), so U1 regenerates one: ≥10k commands over the removed words
  and their options, all blocked, checked in as a fixture or a generator with a
  pinned seed.
- `architect/CLAUDE.md`, `architect/README.md` and `architect/settings.json`
  arrived with the kit and are not rewritten by a unit. U3 verifies
  settings.json against the CLI and fixes it only where the CLI differs; U6
  quotes README.md's switch point into docs/INTEGRATION.md.
- Review 14's Notes (the wording flaw in mission 14 U3's body, the counting
  basis of "18 rows", the unicode look-alikes) are observations, not items, and
  are not taken.

Dependencies. U1 rewrites the guard's table and U3 adds a third mode to the
same file: U1 first, and U3's architect table is expressed in U1's structure.
U4 and U5 both touch the playbook engine and `[series]`: U4 first. U6's docs
sweep runs after U3–U5 so it documents what exists. U7's gate is a kit check,
which U2's bare-name row could move: U7 after U2. U2 is independent of U1.

Findings. H-028 and H-029 filed by U0. H-027 stays open (it is the architect's
to resolve in DESIGN). H-001 and H-009 stay open.
