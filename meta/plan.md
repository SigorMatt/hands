# plan — mission 11 (review 10, the apply from the kit, the driver role)

Source: meta/BUILDER-11-PROMPT.md, DESIGN v3.10 §27 (with §6, §8, §10, §11,
§26), meta/reviews/REVIEW-10.md, meta/FINAL-REPORT-10.md §5, findings H-018 to
H-021. Units run in order; each ends with a commit and a push. `[x]` = done and
pushed, `[b]` = blocked (two failures).

Base of the mission: 0fef436 (`plan: mission 11 kit (DESIGN v3.10)`).

- [x] U0 Plan and corrections (`plan:`) e8daca8 — this file, meta/CHECKPOINT.md;
      H-018..H-021 v3.10 resolutions appended with status lines; REVIEW-10 SF7
      (a test pins docs/INTEGRATION.md's `done` statement to §6; phrase
      containment only)
- [x] U1 REVIEW-10 SF1, SF3, SF4, SF5, SF6 (§27) efe4d56 — descendant = the
      job's `HANDS_JOB=<id>` env mark in /proc (a member that cleared or hides
      its env leaves the group unsignalled); apply literal excuses only a plain
      `^VERDICT: kit applied` rule; aux.done placeholders tried as 0/1/12; any
      pre-fetch refusal after a good secret files `kit.refused`; zip caps 16/64
      MiB — `go` refused while the
      builder has a held job (message names it), rechecked after the playbook
      load; sweep signals a group only when its leader is the job's pid and all
      members are descendants (foreign-group test); `kit check`: apply-verdict
      exception never excuses a broken builder rule, `aux.done` rules checked
      against the protocol's `VERDICT: review …` line (H-021 per §27), paths
      outside the repo / absolute / `..` / a missing protocol path refused;
      malformed attachment URL refused before any fetch with `kit.refused`;
      INTEGRATION :304 name-clash wording
- [x] U2 Who by the sessions file (§27; H-020; REVIEW-10 blocker 1) 525dc66 —
      transcript by `<sessionId>.jsonl` (cwd project dir first, then any); bad
      or foreign sessions file = no file (`by directory`); job transcript = a
      session id held by any spool job record; another human's transcript can
      still show under `by directory`
- [x] U3 The apply from the kit (§27; REVIEW-10 SF2; H-018 `kit` origin and
      un-pause for `phone`/`kit`) d4bea98 — one `plan_apply` for kit check and
      daemon; commit message `KIT.md` first line else `plan: kit <stem>` (old
      `plan: mission <N> kit` gone); only the paths check blocks the apply; a
      busy builder does not; the prompt names the file where written, so
      byte-equal with kit check only for `~/Downloads/<same name>`
- [x] U4 The driver role (§8, §27) d491f6b — non-empty driver
      `permission_flags` refused at config load (doctor `config` row fails);
      HANDS_ROLE always `driver`; every send to the driver refused until U5's
      `consult`; role mode runs only `git` read-only and listed `hands`
      (no cat/ls/grep), send needs explicit `--context keep` and builder|aux;
      clone at `<cwd>/repo` or `<cwd>`, missing clone/guard a warning
- [x] U5 `consult` (§10, §27) c1d8ed5 — no driver role stops at fire time
      (not load); driver started through the daemon queue, not `Api.send`,
      ungated, origin playbook, context clear; `resolved` follow-up uses
      `notify` (§10 has no no-op); max_consults counts driver jobs after the
      last builder job whose prompt is the kickoff; consult.done/journal on any
      end but `limited`; fake_claude gains `exec`
- [ ] U6 This repository's playbook (BUILDER-12 kickoff, consult rules)
- [ ] U7 Final report — meta/FINAL-REPORT-11.md (drafted under meta/drafts/)

Review items by unit. REVIEW-10 blocker 1 → U2; SF1, SF3, SF4, SF5, SF6 → U1;
SF2 → U3 (§27 resolves it by the apply from the kit, so no separate finding);
SF7 → U0.

Scope choices (orchestrator's, from §27 where the brief's unit text is
shorter):
- H-021's `aux.done` check (§27 "verifies every `verdict` rule … `aux.done`
  included, against … the `VERDICT: review …` line") goes to U1 with SF4, the
  other half of the same check.
- H-018's `kit` origin and its un-pause go to U3, which creates the first
  `origin: kit` job; `phone` un-pause already exists (m10 U2).
- REVIEW-10 SF5's extra probes (`.GIT`, duplicate entries, NUL, size cap,
  unresolvable send paths) are beyond §27's list; U1 refuses what §27 names and
  may take the rest where simplest, stating what it did not take.

Dependencies. U3 builds on U1's kit check path rules (same refusals for the
zip) and on U1's `go` held-job rule (the apply job is the held one). U5 needs
U4's role. U6 needs U5's action and events. U2 is independent.

Findings. H-018..H-021 resolved by v3.10 (U0 status lines). H-001 and H-009
stay open.
