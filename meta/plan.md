# plan — mission 9 (close review 8)

Source: meta/BUILDER-9-PROMPT.md, DESIGN v3.8 §25 (with §6, §10, §11). Units
run in order; each ends with a commit and a push. `[x]` = done and pushed,
`[b]` = blocked (two failures).

Base of the mission: 0ead876 (`plan: mission 9 kit (DESIGN v3.8)`) — RED:
1 failed, 1423 passed. `tests/test_playbook.py::test_the_fixture_is_section_10s_example_verbatim`
fails because v3.8 added `monitor.task_killed` and `monitor.orphan_processes`
→ `stop` to §10's example (H-016 closed by §25) and the fixture copy predates
it. No unit in the brief copies the block; U0 cannot commit on red, so U0
carries H-016's own direction (copy into the fixture and the doc, extend the
rule list, drop the "carries neither yet" sentence). Recorded as a deviation.

The `meta/prototypes/` ruff exclude is already absent from `pyproject.toml`
at the base (removed by mission 8 U6, a93e3a7); `grep -n prototypes
pyproject.toml` returns nothing. U0 records this; there is nothing to remove.

- [ ] U0 Plan and corrections (`plan:`) — this file, meta/CHECKPOINT.md;
      H-014 and H-016 get the v3.8 resolutions (§25); H-017 filed for
      review 8 should-fix 2 (`fixed by DESIGN v3.8`); §10 example copied
      into tests/fixtures/playbook_example.toml and docs/PLAYBOOK.md (base red)
- [ ] U1 Termination precedence and vocabularies (§6, §25; H-014)
- [ ] U2 Review 8 should-fix 1, 3, 4
- [ ] U3 Playbook must match the committed file (§10)
- [ ] U4 `quiet_hours` retired (§11, §25)
- [ ] U5 Phone channel after restart; detector payload (§25)
- [ ] U6 Final report — meta/FINAL-REPORT-9.md (drafted under meta/drafts/)

Review items by unit. REVIEW-8 should-fix 1, 3, 4 → U2. Should-fix 2 →
DESIGN v3.8 §6 (H-017) and U1. FINAL-REPORT-8 §5 item 1 → U1; item 2
(H-016) → U0; item 3 → U4; item 4 → U5 (`cause: unknown`; `who_cmd_topic`
stays secret-less by §25, no code); item 5 → U5.

Dependencies. U4 touches the playbook loader and notify; after U3 (loader).
U5 touches the phone channel; after U2 (phone warning). U1 is independent.

Findings. H-017 filed by U0. H-001 and H-009 stay open.
