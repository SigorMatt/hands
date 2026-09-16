# REVIEW-14 — cold review of hands mission 14

VERDICT: review mission 14 blockers=2 should-fix=7

Base `4192af1` (`review: mission 13`, the last `review:` commit on origin/main).
Tip `041f647`. Unit commits reviewed, one sub-agent each, in a `git worktree` at
the commit: f9e0729 (U0, the orchestrator's `plan:` commit), 9a5bc75 (U1),
e79e770 (U2), 599b993 (U3), 2ad4356 (U4), 104666d (U5), fa8fbae (U6). Not
dispatched: c958a62 (the architect's mission-14 kit) and 041f647 (U7, the `meta:`
commit that adds meta/FINAL-REPORT-14.md and the held bookkeeping). The reviewer
re-ran both blockers' probes at the tip.

## Blockers

1. **The guard still writes and still runs an arbitrary program in normal mode:
   an allowed first word takes unchecked options (U1 `9a5bc75`; §12, §28, §30;
   the guard's own docstring).**
   - **Why.** `ALLOWED_FIRST_WORDS` (`driver/hooks/bash_guard.py:110-116`) admits
     `sort`, `uniq`, `cut`, `tr`, `find`, `stat`, … as bare words. §30's language
     removes redirection, so nothing in the command *looks* like a write — but
     these commands write and execute through their own options, and outside
     `git`/`hands` no option table is applied in normal mode. The file's comment
     at `:117-122` states the principle ("no listed option takes a value that
     names a program to run") and applies it only to git's rows.
   - **Reproduced at the tip**, normal mode, hook JSON on stdin, shipped file:
     ```
     sort -o /tmp/rev14-probe/Z1 /etc/hostname                          -> exit 0 ; Z1 created
     uniq /etc/hostname /tmp/rev14-probe/W5                             -> exit 0 ; W5 created
     sort -S 1k --compress-program=/tmp/rev14-probe/prog <big file>     -> exit 0 ; prog EXECUTED (its marker file appeared)
     ```
     The U1 sub-agent found the same three independently, in a differential fuzz
     of 80k generated commands.
   - **What the disk contradicts.** `driver/hooks/bash_guard.py:7` — a line U1
     edited, adding the §30 parenthetical — says the guard blocks "unless every
     command segment starts with an allowed word and the command has **no way to
     write**: no redirection (a `<` or `>` is refused anywhere, §30), no tee, no
     in-place edit, no interpreter". The refusal text at `:929-930` tells the
     driver "hands, read-only git, and **read-only inspection** commands; it
     never writes."
   - **Scope, stated plainly.** Role mode refuses all three (`exit 2`), so this
     is not a role-mode hole: §30's "the driver role is enabled after a review
     finds no guard hole in the one-line language" is not failed by it. It is
     also **pre-existing** — the parent guard at `4192af1` allows the same three
     commands with the same exit codes — and §30 does not name it. It is a
     blocker because it is a working write-and-execute bypass of the guard in the
     mode that ships and is in use today, of a claim the shipped file makes in
     its own words, restated by this unit; because the mission's subject is
     exactly the guard's completeness; and because FINAL-REPORT-14 §3.1 discloses
     only unquoted `$` (`echo $i`), not this, and no finding was filed. §30's
     method — a language small enough to have no corners — was applied to the
     *syntax* and not to `ALLOWED_FIRST_WORDS`, which is still a denylist-shaped
     surface.

2. **The kit pair is unspaced on the ordinary branch, and the test picks the
   other one (U5 `104666d`; §30 Notifications, decision 2026-09-15).**
   - **§30's rule.** "when the daemon publishes two notifications for one cause
     (a kit receipt and its held apply; a limit and its resume), it waits 1.1 s
     between them so ntfy's per-second timestamps order them."
   - **The code.** `src/hands/phone.py:440` waits `PAIR_SPACING_S` between the
     `kit received` receipt and `_file_apply`. But `_file_apply` then publishes
     `job.held` (through `api.send` → the spool event → `_on_event` → notify) and
     **immediately** answers `KIT_TITLE` a second time at `phone.py:466-471`,
     with no wait:
     ```
     if plan.default_why is not None:   # phone.py:466
         text = f"apply {plan.name}: {plan.default_why}; the commit message is the default …"
         await self.daemon.notifier.answer(KIT_TITLE, text)
     ```
     So one cause produces **three** publishes with one gap, and the last two land
     inside one second, which is the exact condition §30 exists to remove.
   - **When.** `default_why` is set whenever the kit carries no `KIT.md`, or its
     first line is not usable (`src/hands/kit.py:1022-1026`). A kit with no
     `KIT.md` is the ordinary case, not an edge.
   - **The test chose the branch that hides it.**
     `tests/test_phone.py:1897-1899`: "With a KIT.md the apply has no default to
     explain, so the receipt is the only `kit received` answer and the pair is the
     whole sequence." The assertion filters `order` down to two publishes and one
     sleep, so it would pass either way.
   - **What the report says.** §2 U5 claims "The receipt → `sleep 1.1` → held
     publish sequence" is proven, and §3.5 discloses only the network and
     clock-skew limits. The `default_why` branch is disclosed nowhere, and no
     finding was filed.

## Should-fix

1. **Daemon start publishes N+1 notifications in one second (U5; §11, §25,
   §30).** `src/hands/daemon.py:207-222` publishes "hands: handsd started" and
   then calls `_renotify_held()`, which publishes a `job.held` per held job with
   no wait. One restart with held jobs is one cause and several publishes inside
   one second — the same ordering problem §30 names.
2. **`docs/INTEGRATION.md` states the limit pair as two published
   notifications, and today nothing is published (U5).** `NOTIFY_KINDS` is
   `{"job.held"}` (`src/hands/daemon.py:82`), so the `limit` event and its resume
   publish nothing absent a playbook `notify` rule, and no shipped playbook has
   one. `limits.resume_delay_s` orders the *scheduler's* delay, not a published
   pair. FINAL-REPORT-14 §3.5 concedes this; the shipped doc, which a human
   reads, does not.
3. **Doctor judges only the first PreToolUse Bash hook (U4 `2ad4356`; §30
   should-fix 4; the REVIEW-13 should-fix 4 class).** All fifteen of REVIEW-13's
   non-enforcing hook commands now fail, and `disableAllHooks` fails — that item
   is closed. But doctor returns on the first hook that runs the guard and never
   judges the rest: settings carrying the real guard *plus* a second Bash hook
   `echo '{"hookSpecificOutput":{"permissionDecision":"allow"}}'` give
   `exit 0 / ok`. Whether that neuters the guard depends on Claude Code's
   multi-hook precedence, so it is a gap in doctor's inspection, not a proven
   bypass — and it is disclosed nowhere in §3.4. (Fail-closed in the other
   direction: `python3 -u <guard>` and `exec python3 <guard>` are rejected though
   they do run the guard.)
4. **An empty project name is not refused, it is ignored (U3 `599b993`; §30
   should-fix 6).** `resolve_project` (`src/hands/config.py:445-449`) tests
   truthiness, so `hands --project ""` and `HANDS_PROJECT=""` fall through to the
   next source and the command silently acts on a *different* project. `""` does
   not match `[A-Za-z0-9][A-Za-z0-9._-]{0,63}`; `load_config("")` refuses it, but
   no CLI entry reaches that. Every non-empty probe (`..`, `.`, `a/b`, `-a`, 65
   characters, `café`) is refused on all three binaries and leaves a temp HOME
   byte-identical.
5. **The persisted `max_consults` anchor is thinner than it reads (U4; §30
   should-fix 5).** `daemon_start` leaves an unreadable `pipeline.json`
   byte-identical, but any later `_save()` (a pause, a stop) rewrites that file
   *with* the in-memory anchor; and a deleted or rotated `pipeline.json`
   re-anchors to the next daemon start, so the count restarts. The restart case
   §30 names is closed; these two are undisclosed.
6. **The bare-name rule's false positives are prose, not a pinned row (U2
   `e79e770`; §30 blocker 2).** `tests/fixtures/named_path_shapes.tsv` has 65
   rows and pins no false positive, so the boundary lives only in
   `kit.NAMED_PATH_RULE`'s text. The class is wider than the five the report
   names (`API`, `CLI`, `HEAD`, `TODO`, `Profile`): `PASS`, `FAIL`, `NOT`,
   `GREEN`, `VERDICTS` and `README` all read as paths. It is fail-closed and no
   shipped prompt trips one, but a later change could widen or narrow it
   unnoticed. Also untested: `hands who` when the *named* project is the broken
   config among valid ones.
7. **`[series] kickoff` names a brief that does not exist, and nothing flags it
   (U6 `fa8fbae`).** `meta/BUILDER-15-PROMPT.md` is absent. `hands doctor` prints
   the kickoff happily; `kit check`'s playbook check says outright "its kickoff is
   not compared"; `_check_protocol` reads send-rule prompts only; `load_playbook`
   does no existence check; phone `go` (`src/hands/phone.py:354`) only rejects a
   null kickoff. A phone `go` today sends the builder to a missing brief. §3.6 and
   §5.3 disclose it and the design does not require the check — REVIEW-13's U7
   note therefore stands unclosed for a second mission.

## Notes

- **Gates.** `./scripts/check` was green once at each of the seven unit commits,
  under seven concurrent suites, and every pass count matches FINAL-REPORT-14 §1
  exactly: 2284 (U0), 2437 (U1), 2524 (U2), 2569 (U3), 2588 (U4), 2597 (U5), 2597
  (U6). Ruff and the CLI smoke were green in each. This review did not reproduce
  §4's "3/3"; 041f647 changes only meta/ over fa8fbae, which was green.
- **Test-first.** Every unit's tests go red when its product change is reverted:
  U0 5 rows (see below), U1 183 failed, U2 42 failed, U3 exactly the 39 new
  refusal rows, U4 17 failed, U5 2 collection errors plus 5 failures (and 3
  behavioural failures when only `limits.py`/`phone.py` are reverted), U6 the
  kickoff value itself in a parent worktree carrying only the new test — not
  `PlaybookNotCommitted`, as the body says. Three caveats, none of them a
  blocker: U0's shared order assert reddens all 5 PRECEDENCE rows, not only the
  new one, where the body says "the row was red" (the mutation is exact — moving
  the limit check ahead of the cancel check fails 1 of 2284); U4's SF3
  pipe-timeout test is a test-only strengthening that cannot go red by revert, so
  the mutation carries it (`timeout = 5.0` fails both rows, `0.2` fails the 1.5 s
  row, `1.5` fails the 0.2 s row — no single hardcode passes); U4's SF4 rows
  `[semicolon]` and `[substitution]` were already green at the parent.
- **Forbidden files.** No unit commit after U0 touches `DESIGN.md`,
  `meta/plan.md` or `meta/CHECKPOINT.md`. U0 is the orchestrator's `plan:`
  commit, which the brief allows to write the plan and the checkpoint; it does
  not touch `DESIGN.md`. `meta/FINAL-REPORT-13.md` is append-only at U0 (numstat
  `10 0`, zero deletions), a dated 2026-09-16 correction that keeps REVIEW-11
  blocker 1 open until U1. `meta/findings/FINDINGS.md` gains H-026 at U0 and
  H-027 at U5 with zero deleted lines.
- **Commit bodies.** All seven list exactly the files in `git show --stat`, no
  more and no less. One wording flaw: U3's body says the 39 rows "failed there;
  the new tests themselves pass at the parent" — self-contradictory; disk says
  the first half.
- **Findings.** H-026 is filed with the 11–13 history as three bullets and
  resolved by v3.13. H-027 is filed and open, and its seam is sound: the U5
  sub-agent confirmed `kit_rule(6) == design_rule(6).replace(STALE_QUOTED_CLAUSE,
  GUARD_REFUSAL_CLAUSE)` substitutes one clause only, a companion test asserts
  the replacement is present, so any other divergence in rule 6 still fails. It
  hides no drift and becomes a no-op once DESIGN §12 rule 6 is corrected. Neither
  blocker above has a finding.
- **The guard, beyond blocker 1.** Every §30 refusal holds through the shipped
  file on stdin in both modes: 224 runs (9 offenders × 7 positions, quoted and
  unquoted) all exit 2, all 65 Cc code points exit 2, `$`/`!` in double quotes
  exit 2. REVIEW-13's four heredoc shapes and REVIEW-12's five probes: exit 2 in
  both modes. REVIEW-11's eleven: exit 2 in role mode. A differential fuzz of 80k
  generated commands, 18,000 of them sampled and actually executed under real
  bash with argv-logging stand-ins on a private PATH, produced 11,925 real
  invocations and **every one was itself allowed by the guard's own `judge()` in
  that mode** — bash never ran a command the guard did not see. `${…}`, `$[…]`,
  extglob, `case`, brace words, `sh -c`/`env`/`xargs`/`command`/`builtin`/`exec`/
  `find -exec`, partially-quoted command names, `git -c core.pager=`,
  `--exec-path`, `--config-env`, `-c alias.x=!cmd`, `--ext-diff`, `| less` are all
  refused. `git fetch "ext::…"` is hook-allowed but bash refuses it
  (`transport 'ext' not allowed`). Unicode look-alikes (`＜ ＄ ｀ ＃`) pass and are
  inert. The `git -C` realpath pin holds on a real symlink clone, and a second
  `-C` is refused by name. The parent's whole corpus was replayed: 433 commands ×
  2 modes, **0** parent-blocked rows now allowed. §3.1 says 18 rows moved from
  allowed to blocked; the independent replay counts 21 distinct commands
  tightened, each genuinely refused by §30's text — a counting basis, not a
  discrepancy in kind.
- **should-fix 7 (the retired units) is fully closed.** A whole-tree sweep for
  `handsd.service`, `handswho.service`, `-u handsd`, `restart handsd` and `stop
  handsd` leaves zero unfixed leftovers: `DESIGN.md:644` and `:921` (H-027), the
  meta/ history and `tests/fixtures/kit-mission-10/DESIGN.md` (captured), the
  sweep test itself, and `docs/INTEGRATION.md:91-92`, which names the un-templated
  units as things the human must *remove*. `src/hands/cli.py:908`,
  `src/hands/doctor.py:718` and `docs/INTEGRATION.md:30,391,463` are all
  templated `handsd@<project>` now.
- **The kit commit.** `c958a62` (the architect's) is not a builder unit and was
  not dispatched, but it is the commit that removed the `job.held → notify` rule
  from `PLAYBOOK.toml` and both templates; U5 verifies and pins that, and a
  playbook that *keeps* the rule still parses and gives `kit check` exit 0. U5
  changes no playbook file, as its body says.
- **§3 NOT PROVEN against what the sub-agents found:**
  - **§3.1** is accurate on what it names, and its "the claim is that the nine
    refusals remove the constructs bash needs" survived an 18,000-command
    execution differential. It does not disclose blocker 1: the language was made
    corner-free, `ALLOWED_FIRST_WORDS` was not.
  - **§3.2** is confirmed in both directions. The disclosed false positives and
    misses are all real, the shipped prompts and briefs 8–14 still pass, and the
    false-positive class is wider than the five named (should-fix 6).
  - **§3.3** is confirmed; `jobs`/`roles` do still match, and in a temp HOME
    `handsd --project jobs` creates `~/.hands/jobs/`, after which another project
    refuses to start and `migrate-spool` orphans that spool — the effect
    REVIEW-13 should-fix 6 named, which §30 chose not to refuse. It does not
    disclose the empty name (should-fix 4).
  - **§3.4** is confirmed on doctor's settings scope and on the vacated stranger
    ("a report, never a kill") — though the sub-agent's probe shows the
    over-report fires in the realistic case, with `_last_seen` set, not only in
    the test's. It does not disclose the first-hook gap (should-fix 3) or the
    anchor's thinness (should-fix 5).
  - **§3.5** does not disclose the `default_why` branch (blocker 2) or the
    daemon-start burst (should-fix 1), and `docs/INTEGRATION.md` overstates the
    limit half (should-fix 2).
  - **§3.6** is accurate and understated: nothing anywhere in the stack flags a
    kickoff naming a missing brief (should-fix 7).
  - **§3.7** is accurate.
- **U6 is otherwise clean.** The `PLAYBOOK.toml` diff is exactly the one kickoff
  line, in the same form as the -11/-12/-13/-14 lines and §27's convention, and
  the body's acceptance probe reproduces byte for byte: `hands kit check <kit>
  --repo .` → six PASS lines, "pass (6 of 6 checks)", exit 0.

## Per-commit verdicts

### f9e0729 (U0)

```
REPORT
sha f9e0729 (parent c958a62), mission 14 U0 "Plan and bookkeeping", plan: commit
1 Body PASS: names U0/BUILDER-14-PROMPT, DESIGN v3.13 §30 (with §6, §28), REVIEW-13 SF8 + the REVIEW-11 blocker-1 row; body lists exactly the 7 files in --stat (docs/INTEGRATION.md, meta/{CHECKPOINT,FINAL-REPORT-13,journal,plan}.md, meta/findings/FINDINGS.md, tests/test_docs.py) — no more, no less; "The runner was not changed" holds (src/ absent from --stat).
2 Test-first PASS: with docs/INTEGRATION.md at parent: "FAILED tests/test_docs.py::test_the_doc_states_each_precedence_clause_and_the_runner_applies_it[killed-over-limited]" / "AssertionError: the precedence clauses are out of order  assert [0, 28, 62, -1, 170] == [-1, 0, 28, 62, 170]" / "5 failed, 1 passed, 69 deselected" (the shared order assert reddens all 5 rows, not only the new one — body says only "the row was red", true but understated). Mutation (limit check moved ahead of cancel in _final_state): full suite "1 failed, 2283 passed in 201.86s" — only [killed-over-limited], "assert ('limited', None) == ('killed', None)". Mutation reverted; tree clean.
3 ./scripts/check GREEN: "2284 passed in 243.85s (0:04:03)" / "== cli smoke ==" / "check: green" (one run; body's "green 3/3" not independently verified)
4 Conformance PASS: §30 clause "Cancel-versus-limit precedence is pinned: `killed` wins over `limited` when both apply in one job (should-fix 8)" is rendered verbatim-in-substance in the doc sentence and pinned by 4 runs (result±line, line+exit 1, no result/no exit) all asserting ("killed", None); §30 already present at parent c958a62 and DESIGN.md is untouched by this commit; meta/plan.md + meta/CHECKPOINT.md touched but explicitly allowed for the orchestrator's U0; H-026 filed in meta/findings/FINDINGS.md with the 11/12/13 history as exactly three bullets and "Status: resolved by DESIGN v3.13 (code: mission 14 U1)"; meta/FINAL-REPORT-13.md is append-only (numstat "10 0", zero deletion lines) adding a "## Corrections (appended)" dated 2026-09-16 line that keeps REVIEW-11 blocker 1 open until U1.
NOT PROVEN: the body's "green 3/3" (I ran the gate once); that the runtime path (job record `limit` field, limit resume, inbox events, notifications) behaves for a job that was both cancelled and limited — only the pure `_final_state` return is pinned, and only for those 4 field combinations; DESIGN §6's own precedence sentence still says only "a cancel stays killed and a limit stays limited" and was not updated (allowed — DESIGN is off-limits here, and §30 carries the pin).
```

### 9a5bc75 (U1)

```
REPORT
sha 9a5bc75 (parent f9e0729), mission 14 U1 "The guard's language"
1 Body PASS: names U1, DESIGN v3.13 §30 + §12 r6/§28/§29, REVIEW-13 b1+sf1, H-026; its 5-file list == `git show --stat` exactly (bash_guard.py, tests/test_bash_guard.py, tests/test_docs.py, docs/INTEGRATION.md, driver/README.md).
2 Test-first PASS: reverting only the 3 product files gives "183 failed, 639 passed in 15.09s", e.g. `test_the_language_refuses_naming_the_first_offender_and_its_position[hands send 'oops-an unbalanced `'` quote-11]`, `test_role_mode_pins_git_dash_c_by_realpath_through_a_real_symlink`, `test_the_parsing_the_language_makes_unreachable_is_removed`, `test_docs.py::test_the_integration_doc_states_the_guards_language_in_one_paragraph`. Restored clean.
3 ./scripts/check GREEN: "== ruff ==/All checks passed!", "2437 passed in 247.00s (0:04:06)", "check: green"; selftest: `selftest: 189/189 ok`.
4 Conformance PASS: through the SHIPPED file on stdin, 224 runs (9 offenders x 7 positions incl. single- and double-quoted x both modes) all exit 2; all 65 Cc code points exit 2; `$`/`!` in double quotes exit 2 both modes. REVIEW-13's 4 heredoc shapes: exit 2 both modes. REVIEW-12's 5 probes: exit 2 both modes. REVIEW-11's 11 probes: exit 2 in role mode (normal-mode allows are §28's human-session set). Forbidden files: DESIGN.md/meta/plan.md/meta/CHECKPOINT.md untouched. `grep -c heredoc` = 0; all six removed names absent from the guard; only one bash_guard.py in the tree. Audit claim reproduced independently: 433 distinct parent-table commands x 2 modes = 866 pairs through both guards -> 0 parent-blocked-now-allowed, 21 distinct commands tightened (all `<` `>` `#` `\` `$(`), each genuinely refused by §30's text.
4 Hole hunt: NO hole in the §30 language or in role mode. Differential fuzz (80k generated commands; 11,098 hook-allowed in role mode and 23,203 in normal mode, 18,000 sampled and actually run under real bash with argv-logging stand-ins for hands/git/touch/rm/sh/sort/env/xargs/python3/claude on a private PATH): 11,925 real invocations, and every one is itself allowed by the guard's own `judge()` in that mode — bash never ran a command the guard did not see. Probed and refused: heredocs, `$(`/backtick, `\`, `#`, `$'`, `${…}`, `$[…]`, `$x`, extglob `@(…)`, `case`, brace words, `sh -c`/`env`/`xargs`/`command`/`builtin`/`exec`/`find -exec`, partially-quoted command names (`e'n'v`, `'touch'`), `git -c core.pager=`, `--exec-path`, `--config-env`, `-c alias.x=!cmd`, `--ext-diff`, `| less`; `git fetch/ls-remote "ext::touch …"` IS hook-allowed in both modes but bash refuses it (`fatal: transport 'ext' not allowed`, default git config), so no effect. Unicode look-alikes (`＜ ＄ ｀ ＃`) are allowed and are inert to bash. ONE real but NORMAL-MODE-ONLY and PRE-EXISTING hole (parent guard allows it identically, so not introduced here, and role mode refuses it): `sort` and `uniq` are in ALLOWED_FIRST_WORDS with no option check — `sort -o /tmp/rev14probe/Z1 /etc/hostname` hook exit 0 (role exit 2) and bash created the file; `uniq /etc/hostname /tmp/rev14probe/W5` hook exit 0, file created; `sort -S 1k --compress-program=/tmp/rev14probe/prog /tmp/rev14probe/big.txt` hook exit 0 and bash EXECUTED that program (its marker file appeared). This contradicts the guard docstring's "no way to write" and INTEGRATION.md's "read-only inspection commands" for the human's session, but does not touch §30's language or the §29/§30 role-mode gate.
4 -C pin: PASS. Real `git init` clone at /tmp/rev14probe/clone with `link -> /tmp/rev14probe/evil/sub`; kernel chdir confirms `<clone>/link/..` lands in /tmp/rev14probe/evil. Role mode: `git -C <clone>/link/.. status` exit 2 ("compared by realpath"), `<clone>/.. ` exit 2, `/tmp` exit 2, HANDS_CLONE unset exit 2; second `-C` refused by name (`git -C <clone> -C <clone> status` and `-C <clone> -C .`) exit 2. Still allowed: the clone itself, the clone reached through a symlink, HANDS_CLONE spelled as the symlink with `-C` the real path, trailing slash, `/./`, and a `git` with no `-C`.
NOT PROVEN: that Claude Code hands the hook the exact string bash runs (the commit says so too); that no further bash grammar desynchronises the language beyond what 18,000 executed commands sampled; the driver-role gate rests on role mode, where I found nothing, but the `sort`/`uniq` gap shows ALLOWED_FIRST_WORDS itself is still a denylist-shaped surface in normal mode and should get a finding; DESIGN §12 rule 6 and driver/CLAUDE.md still say the guard "treats quoted text as text", which is now false — the commit body discloses this and edits neither file.
```

### e79e770 (U2)

```
REPORT
sha e79e770 (parent 9a5bc75), mission 14 U2 "Kit check names and who's configs"
1 Body PASS: names U2, DESIGN v3.13 §30 (blockers 2-4 para), §29 (Kit transport; Two projects), §26; its "Files:" list is exactly the 8 files of `git show --stat` (kit.py, cli.py, who.py, test_kit.py, test_two_projects.py, fixtures/named_path_shapes.tsv, ARCHITECT-HANDBOOK.md, INTEGRATION.md).
2 Test-first PASS: product files reverted to e79e770^ -> "42 failed, 236 passed in 2.36s", incl. `test_the_named_path_rule_table[meta/X.md:12-named41]`, `test_the_named_path_shapes_fixture[NOTES-named35]`, `test_review_13s_inputs_fail_protocol_end_to_end[run Makefile-Makefile]`, `test_hands_who_with_a_broken_first_config_and_none_named_renders_the_others`, `test_hands_who_with_every_config_broken_exits_1_naming_each`. Restored; tree clean.
3 ./scripts/check GREEN: "2524 passed in 267.25s (0:04:27)" / "check: green" (matches the body's 2524).
4 Blocker 2 PASS: all ten REVIEW-13 probes now name a path — read NOTES->[NOTES]; run Makefile->[Makefile]; see meta/MISSING.md:12, #L3, “…”, …, --prompt-file=, | -> [meta/MISSING.md]; NOTES->[NOTES]; MISSING.1->[MISSING.1]. End to end, kit (BUILDER-14 brief + PLAYBOOK.toml whose send says "(and NOTES) … meta/MISSING.md#L3") -> exit 1, only `FAIL protocol: rule 0 names NOTES, which is in neither the kit nor the repo; rule 0 names meta/MISSING.md, …`. Shipped prompts unharmed: named_paths over PLAYBOOK.toml + both templates yields only meta/REVIEW-PROTOCOL.md, meta/reviews/REVIEW-{n}.md, WORKPLAN.md (no new names); `uv run hands kit check <kit with meta/BUILDER-14-PROMPT.md> --repo .` -> EXIT=0, 6/6 PASS; briefs 8-14 all exit 0, 1-7 fail only on brief/verdicts/wording, exactly as the body claims.
4 Blocker 3 PASS: temp HOME, alpha.toml invalid + beta.toml valid. `hands who` -> exit 0, beta renders ("handsd (daemon, project beta)") and alpha is a root line `alpha: config error /tmp/h14/.hands/alpha.toml is not valid TOML: Expected '=' after a key in a key/value pair (at line 1, column 5)`. `hands --project beta who` -> exit 0, same alpha line after the beta root; `--json` -> exit 0, daemons {"beta": null}, picture holds the alpha line. Both broken -> exit 1, stdout empty, stderr `hands: alpha: config error …` then `beta: config error …`.
4 Conformance: parentheses judged — `(meta/MISSING.md)`, `read (NOTES) now`, `(newdir/NOTES)` all yield the name. Disclosed false positives confirmed real (API, CLI, HEAD, TODO, Profile) and the class is wider than the five named: PASS, FAIL, NOT, GREEN, VERDICTS, README all read as paths (fail-closed, per §27; no shipped prompt trips one). Disclosed misses all confirmed real (notes, newdir/notes, REVIEW-13, `git show rev:path`, `_path_`); found no worse miss — lower-case names with an extension or under an existing directory (meta/missing.md, scripts/check) are still caught. Docs (handbook §11, INTEGRATION.md) state the rule and both limits accurately. Forbidden files untouched: DESIGN.md, meta/plan.md, meta/CHECKPOINT.md not in the diff.
NOT PROVEN: the fixture claims to enumerate the shapes but pins no false-positive row (API/HEAD/TODO/PASS are described in NAMED_PATH_RULE prose only), so a later change could silently widen or narrow them unnoticed; no test covers `hands who` when the *named* project's config is the broken one alongside valid others; the all-broken exit-1 behaviour is a builder choice where DESIGN is silent (disclosed in the body, no finding filed); English prose beyond the fixture's 16 sampled rows is not enumerated (the body says so).
```

### 599b993 (U3)

```
REPORT
sha 599b993 (parent e79e770), mission 14 U3 "Config edges"
1 Body PASS: claims §30 (blocker 4, should-fix 6) + §13/§29; "Files:" lists exactly the 4 files in --stat (config.py, tests/test_config.py, tests/test_two_projects.py, docs/INTEGRATION.md). Flaw: the Tests clause is self-contradictory — "...failed there; the new tests themselves pass at the parent". Disk says the first half.
2 Test-first PASS: with config.py+INTEGRATION.md at the parent, `uv run pytest tests/test_config.py tests/test_two_projects.py` = "39 failed, 148 passed in 2.21s" — exactly the 39 new refusal rows go red, not a doc test: test_who_grace_must_be_finite[nan|+nan|-nan|inf|+inf|-inf], test_every_number_key_refuses_non_finite[{nan,inf,-inf}-{monitor-stall_minutes,limits-backoff_minutes,runner-cancel_grace_s,runner-pipe_timeout_s,who-grace_s}], test_a_project_name_outside_the_pattern_is_refused_naming_it_and_the_pattern[..|.|a/b||65a|-a|.a|_a|é|café|a b|a\n], test_handsd_refuses_a_project_name_outside_the_pattern_and_creates_nothing[..|.|a/b|-a], test_hands_and_handswho_refuse_a_bad_project_from_the_flag_and_the_environment, test_hands_who_shows_a_config_whose_file_name_is_outside_the_pattern_as_a_config_error. Files restored; worktree clean.
3 ./scripts/check GREEN: "2569 passed in 265.52s (0:04:25)" / "check: green"
4 Blocker 4 PASS: parse_config REFUSES nan/+nan/-nan/inf/+inf/-inf/1e400 for all five keys, e.g. "<path>: [who] grace_s must be a finite number, got nan" / "[runner] pipe_timeout_s must be a finite number, got inf"; `Nan` is a TOMLDecodeError before config sees it. `_int` keys are int-only so unreachable. INTEGRATION.md:180-181 = "a finite number >= 0 / (`nan` and `inf` are refused, §30)"; no other key's doc line ever claimed otherwise.
4 SF6 PASS (one gap): in a temp HOME, handsd `--project ..|.|a/b|-a|65chars|café` → exit 1, "handsd: project name '..' does not match [A-Za-z0-9][A-Za-z0-9._-]{0,63} (a letter or digit, then up to 63 letters, digits, '.', '_' or '-')"; same for `hands --project .. status`, `handswho --project ..`, and HANDS_PROJECT=..|a/b on all three. Every probe left the temp HOME byte-identical (no ~/jobs, ~/roles, ~/inbox.jsonl). `hands who` with `-x.toml` and `café.toml` beside a good config → exit 0 with root lines "-x: config error project name '-x' does not match ..." and the same for café. GAP: an EMPTY name is not refused at any CLI entry — `--project ""` and `HANDS_PROJECT=""` are falsy, so resolve_project never passes them to load_config and silently falls back to the only/another project; only load_config("") (tested directly) refuses.
4 Conformance: no resolve_project hole found — all three call sites (cli.py:733, daemon.py:877, who.py:1020) call load_config on the returned name immediately, `hands migrate-spool` takes no --project, `_peers`/`_first_loadable` go through load_config, and spool_root re-checks; I could not get `..`, `.` or `/` through any entry point. jobs/roles: the pattern does admit them and INTEGRATION.md:55-56 says "do not use them" — but in a temp HOME `handsd --project jobs` STARTS and creates `~/.hands/jobs/`, after which `handsd --project beta` refuses ("holds the flat spool of an older hands (jobs)") and `hands migrate-spool` moved that live spool to `~/.hands/hands/`, orphaning it from jobs.toml. REVIEW-13 SF6 named that exact effect, so this unit only documents it. Forbidden files untouched: DESIGN.md, meta/plan.md, meta/CHECKPOINT.md all absent from the diff.
NOT PROVEN: doctor's report on a refused name; commands other than status/who/handsd/handswho/migrate-spool; whether a live (non-temp) flat spool corrupts, since I only ran the jobs probe inside a temp HOME; whether the empty-name fallback is intended (no test or doc line covers it).
```

### 2ad4356 (U4)

```
REPORT
sha 2ad4356 (parent 599b993), mission 14 U4 "Sweep, doctor, consult"
1 Body PASS: names U4, §30 with §24/§28/§29, REVIEW-13 SF2-5; its "Files:" list is exactly the 9 paths in `git show --stat` (runner/doctor/playbook/daemon, 3 test files, INTEGRATION.md, PLAYBOOK.md).
2 Test-first PASS (with 2 caveats): product files reverted -> "17 failed, 397 passed in 56.74s". RED: test_a_session_member_without_the_mark_is_judged_by_session_and_start_time_alone[started-at-the-last-observation]; test_doctor_fails_when_the_hook_command_does_not_run_the_guard_as_the_guard[selftest-argument|or-true|echo|python3-c|node|cd-and|redirect|background|pipe|assignment|no-interpreter|newline|disable-all-hooks]; test_max_consults_counts_from_the_daemon_start_when_no_kickoff_was_seen_since; test_end_to_end_a_restarted_daemon_counts_consults_from_its_start; test_a_daemon_restart_mid_mission_keeps_the_consult_count. Caveats: SF3's pipe-timeout test stays GREEN at the parent (it is a test-only strengthening, so revert cannot prove it - mutation does, below); SF4 rows [semicolon] and [substitution] were already GREEN at the parent.
3 ./scripts/check GREEN: "2588 passed in 204.24s (0:03:24)" / "check: green" (exit 0; matches the body's claim).
4 SF2 PASS / SF3 PASS: SF2 - `_job_processes` no longer reads the mark for proof; an unmarked sleep in the job's session is killed+reported when started before `_last_seen` and reported killed:false, left alive, in the same tick (new test green; 9/9 sweep tests green). The new guards do not re-open REVIEW-13's gap: `reused` only suppresses a session whose pid a non-claude process now holds. SF3 - mutating runner.py:759: `timeout = 5.0` fails BOTH rows [0.2] and [1.5]; `timeout = 0.2` fails [1.5]; `timeout = 1.5` fails [0.2]. Bound from both sides; no single hardcode passes. Reverted after each.
4 SF4 PASS / SF5 PASS: all 15 REVIEW-13 hook commands now give exit=1, status=fail, detail "does not name the hook (the hook command '...' does not run the guard: it must be exactly `python3 <path to .claude/hooks/bash_guard.py>`)"; disableAllHooks:true gives '"disableAllHooks" is set, so no hook runs'. The 4 legitimate spellings still pass. SF5 - `consults_since` is persisted in pipeline.json, a persisted anchor wins over a later daemon start (probe: anchor 2026-01-01 survives a second engine started 2026-02-02); an unreadable `{not json` file is left byte-identical by `daemon_start`, anchor held in memory only.
4 Conformance PASS: DESIGN.md, meta/plan.md, meta/CHECKPOINT.md untouched. Residual holes, both over-reporting (safe direction, no kill): (a) REVIEW-10 SF3's vacated-stranger row only stays silent because that test leaves `_last_seen` unset; with `_last_seen` set - which a real job always has, `_observe_alive` runs every 50 ms - my probe had `_sweep` report the stranger's group as `monitor.orphan_processes` killed:false (needs pid reuse of the job's pid, so very rare, but the "claude was never observed holding it" guard does not cover the realistic case). (b) doctor returns on the FIRST PreToolUse Bash hook that runs the guard and never judges the others: settings carrying the real guard plus a second Bash hook `echo '{"hookSpecificOutput":{"permissionDecision":"allow"}}'` is exit=0/ok. Whether that neuters the guard depends on Claude Code's multi-hook precedence, so it is a gap in doctor's inspection, not a proven bypass. Also false negatives (fail-closed): `python3 -u <guard>` and `exec python3 <guard>` are rejected though they do run the guard.
NOT PROVEN: that `_state_unreadable` protects the anchor beyond `daemon_start` - any later `_save()` (a pause, a stop) rewrites the unreadable file WITH the anchor (probe B); that deleting/rotating pipeline.json preserves the anchor - it re-anchors to the next daemon start (probe D), and a file without the key reads back None; that doctor covers settings.local.json or user-level settings (body discloses this); that the doctor table enumerates every non-enforcing shell command (body discloses this); the guard's own semantics - doctor only runs `--selftest` on whatever file the command names, so a green-self-testing fake guard at that path still passes; real-world timing of SF3 (0.2 s row has only 0.05 s lower slack, so it may flake on a loaded machine).
```

### 104666d (U5)

```
REPORT
sha 104666d (parent 2ad4356), mission 14 U5 "Notifications and the playbooks"
1 Body PASS: names U5 + §30 (Notifications para, decision 2026-09-15, should-fix 7) with §11/§10/§12; its "Files:" list = all 13 in --stat, none missing/extra. FINDINGS.md edit is allowed (CLAUDE.md routes DESIGN changes to a finding) and is purely additive: `git show -- meta/findings/FINDINGS.md | grep '^-'` yields zero deletions (H-027 appended, no status line rewritten).
2 Test-first PASS: reverting all 7 product/doc files → "ERROR tests/test_limits.py" + "ERROR tests/test_phone.py" ("E ImportError: cannot import name 'PAIR_SPACING_S' from 'hands.notify'"), "Interrupted: 2 errors during collection"; the 3 collectible modules gave "5 failed, 545 passed" — test_driver_rule_6_is_the_design_section_12_rule_6, test_no_driver_kit_file_still_promises_that_quoting_makes_text, test_no_shipped_file_tells_a_human_to_run_an_un_templated_unit, test_the_integration_doc_says_paired_notifications_are_spaced, test_the_integration_doc_has_one_optional_section_for_notify_channel_and_who. Re-reverting only limits.py+phone.py (keeping the constant) gave behavioural red, not import red: "3 failed, 181 passed" — test_a_resume_is_never_scheduled_inside_ntfys_one_second_stamp, test_the_manager_sleeps_the_spacing_before_a_resume_with_no_backoff, test_a_kit_receipt_and_its_held_apply_are_spaced_for_ntfys_timestamps. (test_kit.py/test_playbook.py stayed green under revert — they pin the kit commit's playbooks, they are not this commit's red.)
3 ./scripts/check GREEN: "2597 passed in 256.51s (0:04:16)" / "check: green"; tree clean at 104666d.
4 Spacing PASS-with-gap: both sites present — phone.py:440 `await self.sleep(PAIR_SPACING_S)` between `notifier.answer(KIT_TITLE…)` and `_file_apply`; limits.py:308 `max(PAIR_SPACING_S, backoff_minutes*60)`, reached by both on_limited (l.368) and reschedule_pending (l.430). Constant = 1.1, defined once (notify.py:56), imported elsewhere. Floor is a no-op for real waits: backoff>0 ⇒ ≥60 s, and the reset-known branch (l.310) returns `…+RESUME_GRACE_S`(60.0) unfloored — grace and backoff untouched. CONFIRMED the limit "pair" is not a published pair: NOTIFY_KINDS = {"job.held"} only (daemon.py:82), so the `limit` event and the resume publish nothing absent a playbook `notify` rule — the floor orders the scheduler's delay, exactly as the report concedes. TWO UNSPACED one-cause pairs found: (a) phone.py:442-472 — when the kit has a default commit message, `_file_apply` publishes `job.held` (via api.send → _on_event → notify, which spawns and returns at once) and then immediately `answer(KIT_TITLE, "apply …: <why>…")`, same second, on the very path this unit fixed; the new test dodges it by choosing a KIT.md kit ("the apply has no default to explain… the pair is the whole sequence"). (b) daemon.py:207-222 — "hands: handsd started" then `_renotify_held()` publishes a `job.held` per held job with no wait, one restart, N+1 publishes in one second.
4 Playbooks PASS: `git grep job.held PLAYBOOK.toml templates/*.toml` = no hits; c958a62 (mission 14 kit) really removed the identical 4-line `on="job.held" then="notify"` block from PLAYBOOK.toml, templates/PLAYBOOK-missions.toml and templates/PLAYBOOK-runs.toml; this commit changes no playbook file. Ran it myself: filled missions template + the held rule appended → `hands kit check` EXIT=0, 6 PASS, 0 FAIL.
4 SF7 PASS: sweep hits = DESIGN.md:644, DESIGN.md:921 → DESIGN, both named by H-027; meta/BUILDER-1-PROMPT.md:185, meta/BUILDER-8-PROMPT.md:137, meta/FINAL-REPORT-1.md:117,256, meta/FINAL-REPORT-8.md:122,255, meta/plan.md:46, meta/reviews/REVIEW-7.md:231, REVIEW-8.md:179,188, REVIEW-13.md:171-177, meta/findings/FINDINGS.md:1371,1401,1404 → history (exempt); tests/fixtures/kit-mission-10/DESIGN.md:644,921 → captured kit (exempt); tests/test_docs.py:171,1131,1139 → the sweep/pin itself; systemd/handsd@.service:14, src/hands/doctor.py:718, src/hands/cli.py:908, docs/INTEGRATION.md:30,391,463 → all templated `handsd@<project>`, fixed; src/hands/daemon.py:891 "then start handsd again." → prose, names no unit, not a leftover; docs/INTEGRATION.md:91-92 names `handsd.service`/`handswho.service` as units the human must REMOVE → intentional, not a leftover. ZERO unfixed leftovers. H-027 seam: genuine no-op-once-fixed — its probe reproduces verbatim on the shipped guard (`"see #3"` → "a `#` at position 47", exit 2), and `kit_rule(6) == design_rule(6).replace(STALE_QUOTED_CLAUSE, GUARD_REFUSAL_CLAUSE)` substitutes one clause only, so any other divergence in rule 6 (either side) still fails; a companion test also asserts GUARD_REFUSAL_CLAUSE is present, so the kit cannot drop it. It hides no drift.
4 Forbidden PASS: DESIGN.md, meta/plan.md, meta/CHECKPOINT.md absent from --stat.
NOT PROVEN: that ntfy really orders 1.1 s-apart publishes (no network, no phone) and that 1.1 s survives clock skew — the body concedes both; the limit pair end to end (no publish exists to order today); that 1.1 s is enough given `notify()` spawns delivery as a task, so the *publish* order, not just the call order, is unpinned; and whether the two unspaced pairs above are in or out of §30's "two notifications for one cause" — the body claims "two sites" and does not disclose either. `docs/INTEGRATION.md` states the pairs as "a kit receipt and the held apply… and a limit and the resume it schedules", which overstates the limit half (nothing is published). SF7's exemption is all of DESIGN.md, not just its changelog; no CHANGELOG file exists in the tree.
```

### fa8fbae (U6)

```
REPORT
sha fa8fbae (parent 104666d), mission 14 U6 "This repository's playbook"
1 Body PASS: cites §30 (architect = mission 15), §10, §27; lists both --stat files (PLAYBOOK.toml, tests/test_playbook.py); PLAYBOOK.toml diff is exactly the one kickoff line ("Gate: nothing else" honoured); mirrors 0a14085/1250817 (same 2-file shape).
2 Test-first PASS: worktree at 104666d + only fa8fbae's tests/test_playbook.py, nothing committed -> 1 failed, 17 passed; "AssertionError ... - Read meta/BUILDER-15-PROMPT.m / ? ^ / + Read meta/BUILDER-14-PROMPT.m" at tests/test_playbook.py:260 — the VALUE, not PlaybookNotCommitted. Wrong red reproduced too: editing PLAYBOOK.toml in place gives "4 failed, 14 passed" with "PlaybookNotCommitted: /tmp/rev14-u6-parent/PLAYBOOK.toml is dirty: it differs from `git show HEAD:./PLAYBOOK.toml` ... (§10)" on all four root-playbook tests.
3 ./scripts/check GREEN: "2597 passed in 261.07s (0:04:21)" / "check: green", exit 0 (ruff + CLI smoke green).
4 Conformance PASS: kickoff reads exactly "Read meta/BUILDER-15-PROMPT.md and execute the mission below its divider." — identical form to the -11/-12/-13/-14 lines and to §27 Conventions ("the next mission's line"); one-line diff confirmed; DESIGN.md, meta/plan.md, meta/CHECKPOINT.md untouched (commit touches 2 files only).
4 Missing brief: meta/BUILDER-15-PROMPT.md is absent and NOTHING flags it. Probed: `hands doctor` prints "ok go ... Read meta/BUILDER-15-PROMPT.md ..."; phone `go` (src/hands/phone.py:354) only rejects a null kickoff; `kit check`'s protocol check reads send-rule prompts only (src/hands/kit.py:941 `_check_protocol`/`_named_files`) and its playbook check says outright "its kickoff is not compared"; load_playbook does no existence check. Mission 14 left REVIEW-13 item 4 unaddressed — but the body discloses it in NOT PROVEN, and the design does not require the check (§26 compares only a kit's kickoff to its brief). Standing operational gap: a phone `go` today sends the builder to a brief that is not there.
4 Kit check PASS: kit under /tmp holding only meta/BUILDER-14-PROMPT.md byte-identical to the tree's -> 6 PASS lines identical to the body's (paths/playbook/brief/verdicts/wording/protocol), "kit check: pass (6 of 6 checks)", exit 0.
NOT PROVEN: I ran ./scripts/check once, not the body's three consecutive runs. I checked a directory kit, not a .zip. No test in the repo pins the U6 kit-check acceptance (it is a manual probe). Both review worktrees removed; /home/msi/git/hands untouched and clean.
```
