# plan — mission 6 (close review 5)

Source: meta/BUILDER-6-PROMPT.md. Units run in order; each ends with a
commit and a push. `[x]` = done and pushed, `[b]` = blocked (two failures),
`[y]` = yielded under budget pressure.

Base of the mission: b950956 (`plan: mission 6 kit (DESIGN v3.5)`), green
here before U0 — ruff clean, 929 passed in 39.78s, cli smoke, `check: green`.

Every unit closes a named item of `meta/reviews/REVIEW-5.md`
(`VERDICT: review mission 5 blockers=2 should-fix=7`), except U6, which is
the DESIGN v3.5 wait retirement (§11, §12 rule 8) the review did not raise.

- [x] U0 Plan and corrections — this file, meta/CHECKPOINT.md, three dated
      corrections in `meta/FINAL-REPORT-5.md` §3 (blocker 1: should-fix 3 of
      review 4 was closed for the prompt, not the request; blocker 2:
      `tail -n 0` changed meaning and a wide trailing entry answers `[]`;
      should-fix 2: the three hook bypasses the report did not list), and
      the H-012 decision line (the client measures the whole request)
- [x] U1 Blocker 1 — the whole request measured on the wire before
      connecting, both prompt routes; the two sentences rewritten (§4, H-012)
- [x] U2 Blocker 2 — `tail -n` requires n ≥ 1, `truncated: true` when the
      cap or the window cut the answer, `log` pages (§4, §7, H-013)
- [x] U3 Should-fix 1 — the guard's git policy becomes a per-subcommand
      option allowlist (§12)
- [x] U4 Should-fix 2 — the three hook bypasses: closed with a test, or
      documented under "what the hook cannot see"
- [x] U5 Should-fix 3–7 — `retained()` counts `last_argv`; U2-of-mission-5's
      containment test becomes a real path-resolution test; the config
      helper scan binds every section; the audits exempt by type; both
      prompt routes refuse invalid UTF-8 at the same place
- [x] U6 Driver kit and doctor text — rule 8 in `driver/CLAUDE.md`, the
      doctor's wake-path text, `docs/INTEGRATION.md`, `driver/README.md`
      (§11, §12)
- [x] U7 Final report — meta/FINAL-REPORT-6.md, then the verdict line

No order deviation is planned: the base is green, so every unit is gated
normally and runs in the order above. U1 and U2 are independent of each
other; both touch the client/daemon seam, so they run before U5, whose
item 7 (the two routes' encoding refusal) sits on the same seam U1 rewrites.
U3 and U4 are hook/guard work and touch no `src/` file. U6 is documentation
plus `doctor.py`'s wake-path text.

Yield order under quota pressure (BUILDER-6-PROMPT "Budget guidance"): U5
items 5 and 6, then U4's documentation half. Never yield U0–U3, U6, U7.

Review items by unit. Blocker 1 → U1 (the code and the two sentences) and U0
(the report's correction). Blocker 2 → U2 (the code) and U0 (the
correction). Should-fix 1 → U3. Should-fix 2 → U4 (the code and the doc) and
U0 (the correction). Should-fix 3, 4, 5, 6, 7 → U5, one test per item.

Findings. H-012 is decided by U0's appended line (the client measures the
whole request as it goes on the wire) and closed on disk by U1. H-013 is
decided by DESIGN §4's `log` row in v3.5 (delivered in pages) and closed on
disk by U2. H-001 stays open (it needs a capture from a dotted cwd). H-009
stays open — design-side, and builders do not edit DESIGN.md.

Not this mission, by the brief: the backlog's mission-7 items (harness-kill
detection, per-job scope and orphan accounting, REVIEW-3's should-fix 3, 6
and 7, playbook rules). U7 lists them as deferred to mission 7, which is
where DESIGN §22 puts them.
