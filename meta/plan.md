# plan — mission 18 (review 17; who "needs you" from current state)

Source: meta/BUILDER-18-PROMPT.md, DESIGN v3.17 §34 (with §11, §26, §32,
§33), meta/reviews/REVIEW-17.md. Units run in order; each ends with a commit
and a push. `[x]` = done and pushed, `[b]` = blocked (two failures).

Base of the mission: fc376ab (`plan: mission 18 kit (DESIGN v3.17)`).

- [ ] U0 Plan and bookkeeping (`plan:`) — this file, meta/CHECKPOINT.md;
      H-038 filed (the start fold drops a held job's buttons, blocker 1 with
      should-fix 6); FINAL-REPORT-17 §2's "both denied" (and §3.7) corrected
      by an appended dated block
- [ ] U1 The start fold (§34; blocker 1; should-fix 6) — `job.held` never
      folded, published at once with buttons; start notification lists holds
      by title only; a stop in the window flushes the fold, cancels nothing
      queued; `cancel_all` off that path; the reviewer's two probes as tests
- [ ] U2 The kit record (§34; should-fix 1, 2) — `kit.json` sha256 of the
      checked bytes; engine approval re-hashes, `kit.refused` on mismatch;
      `kit_file` serialized per consultation, second refused before checking
- [ ] U3 Symlinks and doctor (§34; should-fix 3, 4, 5) — lstat walk from the
      root (guard and doctor); doctor reads every settings layer, fails on
      disabled hooks, altered matcher, hostile `env`, different command;
      self-test runs the named guard and compares sha256 with the repo's
- [ ] U4 The token and who (§34; should-fix 7; backlog mission 18 item 1) —
      `ntfy_token` refused without an explicit non-public `ntfy_url`; `hands
      who`'s "needs YOU" from current state only
- [ ] U5 This repository's playbook — `[series] kickoff` names
      meta/BUILDER-19-PROMPT.md; loads; kit of the BUILDER-18 brief `--repo .`
      exits 0
- [ ] U6 Final report (meta/FINAL-REPORT-18.md) — drafted under meta/drafts/,
      moved in with the mission's meta bookkeeping; H-038 code line and status

Review items by unit. REVIEW-17 blocker 1 → U1; should-fix 6 → U1; should-fix
1, 2 → U2; should-fix 3, 4, 5 → U3; should-fix 7 → U4.

Scope choices (orchestrator's):
- Numbering. The brief says "File H-037", but H-037 already exists (mission 17
  U8: Approve/Deny buttons carry no ntfy token). Blocker 1 is filed as H-038;
  every reference in this mission uses that number.
- Should-fix 7. REVIEW-17 says refusing would be wrong; DESIGN v3.17 §34 says
  refuse at config load. The design wins (CLAUDE.md).
- REVIEW-17's Notes (heading-rule shapes, hardlinks, `kit check`'s config
  choice, a crash between done and the engine's end, `"hooks": {}` and
  defaultMode shapes) are observations, not items, and are not taken unless
  a unit's own work touches them.

Dependencies. U1 edits daemon/notifier start; U2 edits api/spool/engine kit
path; U3 edits the guard and doctor; U4 edits config, doctor's token line and
who. U3 and U4 both touch doctor: U3 before U4. U5 and U6 last.

Findings. H-038 filed by U0 (code U1). H-037, H-034, H-027, H-001, H-009 stay
open.
