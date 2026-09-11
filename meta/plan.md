# plan — mission 2 (the shakeout)

Source: meta/BUILDER-2-PROMPT.md. Units run in order; each ends with a
commit and a push. `[x]` = done and pushed, `[b]` = blocked (two failures),
`[y]` = yielded under budget pressure.

Base of the mission: 59e7ac7 (`plan: mission 2 kit`).

- [x] U0 Plan — this file, meta/CHECKPOINT.md reset, H-008 entered in the ledger
- [ ] U1 Origin `limit` — ORIGINS + `jobs --origin` + resume event (H-004, §6, §4)
- [ ] U2 Resume line optional — `role.resume_line` has no default (H-008, §6)
- [ ] U3 Explicit `run` key — load-time check, `only_if_run_in` refused (H-006, §10)
- [ ] U4 Pause files an event — `stop`/`pipeline.resumed`, doctor wake procedure (H-007, §11)
- [ ] U5 `hands notify --test` — one real ntfy message, prints the HTTP status (§4)
- [ ] U6 Status wording — `queue_depth` is capacity; `queue_capacity` alias in JSON
- [ ] U7 Retire bootstrap — delete bootstrap/, purge every dispatch.sh mention
- [ ] U8 Final report — meta/FINAL-REPORT-2.md, then the verdict line

Order deviation, recorded: **U3 runs first**, before U1 and U2. The mission
base 59e7ac7 is already red —
`tests/test_playbook.py::test_the_fixture_is_section_10s_example_verbatim`
compares `tests/fixtures/playbook_example.toml` against DESIGN §10's example
byte for byte, and the kit commit rewrote that example to the `run` key. No
unit can reach a green gate until U3 lands, so U3 goes first and every later
unit is gated normally. Nothing else about the units changes.

Yield order under quota pressure (BUILDER-2-PROMPT "Budget guidance"):
U6, then U5. Never yield U0–U4, U7, U8.

Findings touched: H-004 (U1), H-008 (U2), H-006 (U3), H-007 (U4).
H-001, H-002, H-003, H-005 get a current status line in U8 or as their
unit lands; the ledger is append-only, so a status change is an appended
`Status:` line under the entry.
