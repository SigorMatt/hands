# plan — mission 4 (blockers and pipeline state)

Source: meta/BUILDER-4-PROMPT.md. Units run in order; each ends with a
commit and a push. `[x]` = done and pushed, `[b]` = blocked (two failures),
`[y]` = yielded under budget pressure.

Base of the mission: 796e5ae (`plan: mission 4 kit (DESIGN v3.3)`), green
here before U0 — ruff clean, 618 passed, cli smoke, `check: green`.

Every unit closes a named item of `meta/reviews/REVIEW-3.md`
(`VERDICT: review mission 3 blockers=3 should-fix=11`).

- [x] U0 Plan and corrections — this file, meta/CHECKPOINT.md, the dated
      correction in meta/FINAL-REPORT-3.md §3 (blocker 3), the H-010
      amendment (should-fix 2's evidence, both observations)
- [x] U1 Guard scope: the allowlist applies to every `git` token; `find`
      `-exec`/`-execdir`/`-ok`/`-okdir`/`-delete` forbidden; `MultiEdit`
      restored (blocker 1, should-fix 1 and 2; §12, §20)
- [x] U2 A deterministic gate: test_daemon.py:556 and every loose numeric or
      path-shaped assertion pinned; 5/5 runs of ./scripts/check (blocker 2,
      should-fix 11)
- [x] U3 Pipeline state: un-pause at job start, one `stop()`, `stop.suppressed`,
      `last_rule` reset, `by: start|resume` (should-fix 4; §10, §20)
- [x] U4 Optional keys and doctor: empty strings refused, `hands doctor`
      reports a config error instead of crashing (should-fix 5, 8)
- [x] U5 `--prompt-file` refusals and driver rule 6 (should-fix 9, 10; §4, §12)
- [x] U6 Final report — meta/FINAL-REPORT-4.md, then the verdict line

No order deviation is planned: the base is green, so every unit is gated
normally and runs in the order above. U1 and U2 are independent of each
other; U2 runs second anyway, because a gate that fails one run in ten makes
every later unit's green a sample rather than a property.

Yield order under quota pressure (BUILDER-4-PROMPT "Budget guidance"):
U4, then U5. Never yield U0, U1, U2, U3, U6.

Review items by unit. Blocker 1 → U1. Blocker 2 → U2. Blocker 3 → U0.
Should-fix 1 → U1 (the adversarial table), 2 → U1 (the `MultiEdit` rule) and
U0 (the H-010 evidence), 4 → U3, 5 and 8 → U4, 9 and 10 → U5, 11 → U2.
Should-fix 3 (doctor's probe argv hardcodes the three flags), 6
(`accepted()` treats a non-integer status as delivered) and 7 (`Api.notify`'s
failure shape has no client test) are **deferred by the brief** to a later
mission; U6 lists them as such in the report's review-items table.

Findings. H-010 is amended by U0 with both observations (the CLI's "matches
no known tool" warning on 2.1.268, and `MultiEdit` in 2.1.269's
permission-rule normalizer) and the decision to keep the rule; U1 closes it
on disk. H-009 stays open — it is design-side and builders do not edit
DESIGN.md. H-001 stays open (it needs a capture from a dotted cwd).
