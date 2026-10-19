# FINAL-REPORT-27 — mission 27: the separation follow-up

VERDICT: mission 27 finished pr=7

Source: meta/BUILDER-27-PROMPT.md, DESIGN v3.26 §43 (with §10, §12, §14,
§23, §24, §32, §33, §34, §36, §39, §41, §42), meta/reviews/REVIEW-26.md,
meta/reviews/REVIEW-25.md (should-fix 1). Branch `mission-27`, from main
1b822a5. Gate: `./scripts/check` green three consecutive runs before every
unit commit (U0 excepted, red as the kit made it); at 38e44ee
5047 tests, and at the final tip (3ad66dd plus this report's commit) 5056
tests, three consecutive green runs and a fourth with
`CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1` in its environment.

## 1. What changed (sha per unit)

| Unit | sha | What |
|---|---|---|
| U0 Plan, branch, findings, the report correction | b3e1e76 | `plan:` — plan, checkpoint; H-074, H-075, H-076 filed; H-070/H-071 and H-073 statuses; the dated correction line in FINAL-REPORT-25 §3 (review 25 should-fix 1). Base red at its start, as expected: `test_the_fixture_is_section_10s_example_verbatim` alone, three runs |
| U1 The base | f10c020 | `tests/fixtures/playbook_example.toml` and docs/PLAYBOOK.md's verbatim block take §10's example (`monitor.task_killed` → notify); the rule-6 test is exact equality with DESIGN; docs/PLAYBOOK.md's H-034 sentence and pin gone; H-027, H-034, H-039 resolved by DESIGN v3.26 §43; H-076's race found and fixed in the tests; three consult refusal tests |
| U2 The owner file on every builder job | 32446f5 | §43's owner sentence at dispatch (worker thread, after the journal sentence, the cap counts both) for every builder job but an apply; `sent_prompt` strips hands' sentences for every reader §43 lists; handbook §4, §14, §19 route 4; H-073 resolved |
| U3 Background tasks off where the role's hook allows it | 3383ffe | `no_background.py` admits an omitted or null sub-agent flag under `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS` (1/true/yes/on), its Bash advice bounded by `BASH_MAX_TIMEOUT_MS`; the wheel ships `hands/shipped/no_background.py`; `config.background_tasks(role)` decides rules 3–5 for the runner and doctor; an inherited value reaches no job; docs/INTEGRATION.md §21 |
| U4 The protocols, the template and the guard's read set | 4130616 | both review protocols: what a report holds, "inside the gate's timeout", the wait rule; the brief template's sub-agent brief and handbook §7 carry the wait rule; the guard admits `ls -R`, `git ls-tree --name-only`, `git status --short`, `git log --date=<format>` (selftest 434/434); `git -C ./repo status` in the architect allow-list; rule 10 names Grep and Read; H-070, H-071, H-074 resolved |
| U5 A playbook change is the owner's | 37bd194 | `_release_kit` holds an architect-filed apply whose stored kit carries `PLAYBOOK.toml` or `meta/PLAYBOOK.toml` (after `kit_apply_problem` and `_kit_bytes_unchanged`), published with buttons and §43's reason through `publish_hold`; no engine kickoff after the human's approval; `hands kit check`'s `WARN playbook:`; architect/CLAUDE.md rules 3, 8; handbook §3, §6, §12; the templates' role-mode kickoff notes; H-075 resolved |
| U6 The operator table follows the code | 38e44ee | §19 gains the "not the committed copy" load stop, the phone's default-message follow-up, U5's hold (route 2, then `go`) and the no-message `stop` rule; fifteen rows reworded to the code's text; `tests/test_operator_table.py` reads the stop reasons and published lines of playbook/limits/daemon/phone by `ast` |
| U7 Final report | 94f709c, 3ad66dd, (this commit) | this file (94f709c); `playbook:` 3ad66dd (hosted findings 3, 4: one function, `published_hold_reason`, decides §43's reason for its cause only, on every path that publishes the hold, the start fold's republish and a hold filed over a paused pipeline included); H-077 filed (finding 1); the Hosted review table and archive meta/reviews/hosted/PR-7/1..3 (this commit) |

## 2. What the tests prove

- The fixture and docs/PLAYBOOK.md carry §10's example as DESIGN v3.26
  writes it; rule 6's quoting sentence equals DESIGN's exactly (U1).
- H-076: `kit_zip` stamps each entry with the current time to 2 seconds;
  the two staged-name tests compared their file with a second `kit_zip`
  call made after the daemon started, so the bytes differed when an even
  second passed between them. Delaying the start by 2.1 s made both fail
  every time; they now compare with the bytes they wrote, and a test that
  gives each `kit_zip` call its own timestamp pins it (U1).
- `consult` is refused while an architect job is queued; a state change
  while a phone `consult`'s attachment downloads refuses it and removes the
  file; a refused `consult` on an idle project with a dirty playbook stops
  the pipeline through §10's load with that load's reason (U1).
- A builder job but an apply carries §43's sentence, word for word,
  naming the owner files with no checkpoint update since, oldest first;
  none after the checkpoint is committed past it, for a nested or deleted
  owner file, without a tracked checkpoint, or after a side branch's
  checkpoint update merged into `HEAD`; an apply job and an apply's resume
  never; journal then owner sentence; the combined preface at the cap is
  refused with the cap's reason; a kickoff that carried the sentence still
  anchors `consults_used`; resumed jobs carry the sender's prompt alone;
  §36's listing and the job summary show neither sentence (U2).
- The hook admits an omitted or null flag under `1`, `true`, `TRUE`,
  ` yes `, `on` and refuses it under `0`, `false`, empty, absent, `2`; an
  explicit `true` is refused under every value; `--selftest` answers the
  same with the variable set and unset; the built wheel carries the hook; a
  builder, aux, driver and architect job's environment follows rules 4 and
  5 in every case U3 lists, an inherited value dropped; doctor's rows and
  statuses for each (U3). The suite passed with the variable set in the
  gate's own environment (U3 and the tip).
- Both protocols state what a report holds, "inside the gate's timeout"
  and the wait rule's three parts, and carry no twelve-line count or
  "20-minute"; the brief template keeps its twelve lines and the wait rule
  with a placeholder timeout; a kit from the templates passes `kit check` 6
  of 6; each of the four options is admitted in each guarded mode and each
  neighbour §43 names refused (U4).
- Under autonomy an architect-filed kit carrying `PLAYBOOK.toml`,
  `meta/PLAYBOOK.toml`, or a playbook switching to phone mode is held with
  buttons and §43's reason naming the path, the gate's reason `apply
  <name>`, also over a paused pipeline; a kit without one is approved as
  before; after the human approves, no engine kickoff and the `kit
  applied` rule fires; a denial as today; the kit-check WARN cases (U5).
- Every stop reason and published line the `ast` reader finds in
  playbook/limits/daemon/phone matches a §19 row or one of 12 exemptions,
  each naming where its text lives; removing the row for a literal ("paused
  by human"), an f-string that begins with a placeholder ("<event>: rule
  <i> cannot be rendered") or a reason through a name ("no rule matches the
  verdict") turns it red, naming the string (U6).

## 3. NOT PROVEN

- No real builder has run under the default, started a sub-agent through
  the fixed hook, or had a gate end at its timeout; that a real Claude Code
  honours `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS` as read from its binary.
- No project with the old hook has been doctor-checked on the laptop;
  `hands doctor --live`'s turn uses doctor's own environment plus the
  role's env table, not the new decision (U3).
- No real role-filed kit carrying a playbook has been held; no real
  architect session ran (U5). A kit filed over a paused pipeline and the
  start fold's republish read §43's reason since 3ad66dd; phone mode in
  force at filing is not tested, only role mode without `autonomous` at a
  start; a kit filed while paused that later breaks §33 has already been
  published with §43's reason, which cannot be known at filing (3ad66dd).
- A kit entry naming the playbook in another case (`playbook.toml`) is
  not held (H-077, open).
- No real decisions kit and `go` has run on a brief that predates the
  template; a phone `go` and the engine's kickoff after an apply carrying
  the owner sentence end to end; the apply-resume exemption was tested on
  held records, not a real limited or orphaned apply (U2).
- That the zip clock caused mission 26's two failures (their output was
  not kept); the two leads (`test_open_refuses_a_running_job`,
  `test_cancel_is_gated_by_default_and_approval_performs_it`) under load or
  as uid 0. U2 found and closed one gap behind the first lead:
  `tests/harness.py`'s `running_job` now waits until the record is
  `running` (the test failed once in that gap during U2's work).
- The §19 reader does not follow a string that reaches a receiver through
  an attribute, a container or another object's method (it shows as unread
  and must be exempted); a one-word title matches any row holding the word;
  `api.py`'s `notify --test` and handswho are not read (U6).
- That an agent follows the wait rule (U4).

## 4. Deviations

- U1 also changed `tests/test_phone.py` (the phone consult tests live
  there) and one existing test whose `stop` rule the example's new
  `notify` rule now matches first. U2 also changed `tests/harness.py`.
  U3's docs/INTEGRATION.md §21 summarises rule 6 too; README.md and
  CLAUDE.md were left unchanged (neither states the hook's rule). U4 also
  changed docs/INTEGRATION.md (the guard-language paragraph its test
  requires) and tests/test_docs.py. U5 also changed `src/hands/spool.py`
  (`PLAYBOOK_PATHS`), `tests/harness.py` (`playbookless_kit()`) and the
  test playbooks (a rule that never fires, so a playbookless kit passes).
  Each is listed in its commit's body.
- Where §43 is silent: "oldest first" sorts by commit time, then ancestor
  count, then path; an unreadable record in a `resumed_from` chain stops
  the walk at the last readable one (U2); the guard's option tables are
  shared by every mode, so the four options are admitted in normal mode
  too, and `--date` needs a non-empty value (U4); a stored zip that cannot
  be read after its hash matched is held for the human (U5); a placeholder
  whose name is only assigned plain strings stands for each of them, and
  the engine's `hold` and the notifier's `deliver` count as receivers (U6).
- U0's commit left the base test red, as the kit made it; U1 turned it
  green.

## Review items

| Item | Disposition |
|---|---|
| REVIEW-26 should-fix 1 — the intermittent `test_kit_apply_refuses_a_staged_name_with_dot_dot` | closed by U1 (f10c020, H-076: the race found in the tests and fixed, pinned) |
| REVIEW-26 should-fix 2 — §19 misses two lines the daemon writes | closed by U6 (38e44ee, the rows and the test that reads the code) |
| REVIEW-25 should-fix 1 — the correction line under FINAL-REPORT-25 §3 | closed by U0 (b3e1e76) |
| REVIEW-25 should-fix 2 — the capture script after a failed `find` | carried to mission 30 by DESIGN §43 |
| REVIEW-25 should-fix 3 — docs/HARNESS-PROBE.md's approval flag form | carried to mission 28 by DESIGN §43 |

## Hosted review

PR #7, `qodo-code-review[bot]`, read with `hands hosted-review 7`. Fetch 1
(Code Review comment 6258210146, updated 2026-10-19T02:14:21Z, at
94f709c): Bugs 3, Rule violations 1, Cross-repo conflicts 0, Skill
insights 0; 4 of 4 open. Fetch 2 (after 3ad66dd was pushed, before the bot
re-read it): the comment unchanged, the inline comments' line metadata
moved. Fetch 3 (updated 2026-10-19T02:51:32Z, at 3ad66dd): Bugs 1, Rule
violations 1; 2 of 4 open, findings 3 and 4 marked resolved. Archive
meta/reviews/hosted/PR-7/1..3. Numbers are fetch 1's.

| # | Finding (verbatim, as the bot wrote it) | Disposition |
|---|---|---|
| 1 | Role kits can rewrite the playbook by changing its case — Spool.stored_kit_playbooks (and kit._owner_warning) recognise only the exact names PLAYBOOK.toml and meta/PLAYBOOK.toml, so an entry such as playbook.toml, Playbook.toml or Meta/PLAYBOOK.toml passes _carries_no_playbook and the engine approves the apply. On a case-insensitive filesystem the apply's unzip -o writes that entry over the real playbook, which the apply then commits. The role can therefore raise its own max_architect_consults, drop a stop rule or change the kickoff without the human seeing it, which is exactly what H-075 was meant to stop. | finding H-077 filed |
| 2 | Reviewers cannot verify the reported run — The new meta/FINAL-REPORT-27.md records only seven-character commit prefixes and summarizes the gate without embedding its raw output. Because the report is the artifact reviewers use to validate the tip and tool claims, they cannot independently match the cited commits, counts, or messages to the run. | dismissed: every final report in this repository cites seven-character shas, which resolve uniquely in it and which the pull request links in full; the gate's form (`./scripts/check`, three runs, the test count) is the one the brief and REVIEW-PROTOCOL.md specify, and the reviewer re-runs the gate at each commit rather than reading pasted output |
| 3 | Paused playbook kits lose hold reasons — _owner_hold_reason reaches notifications only through _announce_hold, while defer_hold skips holds filed during a pause and startup republishes held jobs without a reason override. When either path handles a role-filed kit carrying a playbook, the human sees only apply <name>, not the playbook path and ownership reason. | fixed in 3ad66dd |
| 4 | Holds with other causes show the playbook-owner reason — _announce_hold now always passes reason=self._owner_hold_reason(job), so every buttoned hold of a kit that contains a playbook gets §43's "a change of the playbook is the owner's" reason. That includes kits that _escalate_kits is about to deny for a §33 violation, and kits that _kit_bytes_unchanged refused because the hash did not match. In those cases the human sees Approve/Deny buttons with a wrong reason for the hold, and the real cause shows only in a separate stop message. | fixed in 3ad66dd |
