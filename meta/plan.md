# plan — mission 5 (review 4 and the daemon's memory)

Source: meta/BUILDER-5-PROMPT.md. Units run in order; each ends with a
commit and a push. `[x]` = done and pushed, `[b]` = blocked (two failures),
`[y]` = yielded under budget pressure.

Base of the mission: 6c9440d (`plan: mission 5 kit (DESIGN v3.4, backlog)`),
green here before U0 — ruff clean, 726 passed in 28.72s, cli smoke,
`check: green`.

Every unit closes a named item of `meta/reviews/REVIEW-4.md`
(`VERDICT: review mission 4 blockers=2 should-fix=8`), except U6 and U7,
which are DESIGN §21 items the review did not raise.

- [ ] U0 Plan and corrections — this file, meta/CHECKPOINT.md, the dated
      correction of `meta/FINAL-REPORT-4.md` §3 item 15 (blocker 1), the
      H-011 decision line (`pipeline.stop_suppressed`)
- [ ] U1 Blocker 1 — git option policy in the guard, `find -fprint*`/`-fls`,
      the reviewer's exact probes in the adversarial table (§12, §21)
- [ ] U2 Blocker 2 — `ops.monitor_cmd` shape refused at load (§21)
- [ ] U3 Determinism as a property — one path-stripping helper in
      `tests/conftest.py` used by every negative assertion; 5 runs of
      `./scripts/check` under 5 crafted `--basetemp` values (should-fix 1, 2)
- [ ] U4 Prompt delivery — `ensure_ascii=False`, line room, `--stdin`
      symmetry, `S_ISREG`, the exit-2 sentence in the docs (should-fix 3, 4,
      5; §4)
- [ ] U5 Pipeline and config edges — `last_rule` `stale: true`, the
      `pipeline.stop_suppressed` rename, the two config edges (should-fix 7,
      8; H-011)
- [ ] U6 Daemon memory — stream-json streamed to the job log, bounded
      retention (§21)
- [ ] U7 No background tasks in role sessions — `.claude/settings.json` +
      `.claude/hooks/no_background.py` in this repository (§2, §21)
- [ ] U8 Final report — meta/FINAL-REPORT-5.md, then the verdict line

No order deviation is planned: the base is green, so every unit is gated
normally and runs in the order above. U1 and U2 are independent; U3 runs
before U4–U6 because a gate that a crafted path can flip makes every later
unit's green a sample rather than a property, and U4–U6 all add tests that
compare against text carrying a tmpdir path.

Yield order under quota pressure (BUILDER-5-PROMPT "Budget guidance"): U6,
then U5's config edges. Never yield U0–U4, U7, U8.

Review items by unit. Blocker 1 → U1 (the code) and U0 (the report's
correction). Blocker 2 → U2. Should-fix 1 and 2 → U3. Should-fix 3, 4, 5 →
U4. Should-fix 7 → U5; should-fix 8 → U5. Should-fix 6 (`ADVERSARIAL`'s
independence) is **answered by U3's independent table** per the brief and is
a note on method, not a code item; U8 records it as such. REVIEW-3's
should-fix 3 (doctor's probe argv hardcodes the three flags), 6
(`accepted()` treats a non-integer status as delivered) and 7 (`Api.notify`'s
failure shape has no client test) stay **deferred by the brief**; U8 lists
them again as deferred.

Findings. H-011 is closed on disk by U0's appended decision (the event is
renamed `pipeline.stop_suppressed`) and by U5's rename in code, tests and
docs. H-001 stays open (it needs a capture from a dotted cwd). H-009 stays
open — design-side, and builders do not edit DESIGN.md.
