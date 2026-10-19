# FINAL-REPORT-28 — mission 28: a pause that holds the next step

VERDICT: mission 28 finished pr=<pr>

Source: meta/BUILDER-28-PROMPT.md, DESIGN v3.27 §44 (with §6, §10, §19,
§31, §32, §33, §36, §38, §39, §43), meta/reviews/REVIEW-27.md,
meta/findings/FINDINGS.md (H-077, H-078). Branch `mission-28`, from main
b943019. Gate: `./scripts/check` green three consecutive runs before every
unit commit: 5056 tests at U0, 5087 at U1, 5101 at U2, 5105 at U3, 5125 at
U4 and at the final tip.

## 1. What changed (sha per unit)

| Unit | sha | What |
|---|---|---|
| U0 Plan, branch and findings | 4fed073 | `plan:` — plan, checkpoint; H-078 filed ("decided (DESIGN §44), scheduled for U1 and U2"); H-077 "decided (DESIGN §44 ...), scheduled for U4" |
| U1 A human pause holds the next step | d367373 | a human pause (`paused_by` `cli`/`phone`) keeps a builder/aux/driver end whose decision is a send, consult or stop (or the engine's kickoff after an engine-approved apply), one per role (`pipeline.kept_replaced`); a notify end fires at once; a `resume` rule fires until a stop is suppressed under the pause (the `suppressed_stop` mark); every suppressed stop notified once; a pause over it a quiet no-op; jobs of an un-pausing origin do not un-pause it; `go` and `consult` refused naming `resume`; `resume` reloads, is refused on a bad load or kept ends with no playbook, replays up to the first end that starts a job or stops and discards the rest (`pipeline.kept_discarded`, `hands: resume discarded kept ends`); `kept` and the mark in `pipeline.json`; `hands pipeline`'s `kept` lines, the phone's `status`, `hands show`'s `resumed_from`; tests/test_human_pause.py added |
| U2 At rest, the documents and the table's titles | adb061b | `hands: at rest` once per human pause at the first moment no job is running, queued or held and no §6 resume is scheduled, naming each kept end (verdict cut to 100) or none; the `at_rest` mark in `pipeline.json`, republished with the new list when a kept end is replaced after it; checked at the pause, after every job end the engine hears, a denial, a queued cancel and a spawn failure; handbook §10, §14, §18, §19; docs/PLAYBOOK.md "A human pause"; docs/OPERATIONS.md "A quiet moment"; the §19 reader matches a title at a row's start; H-078 resolved |
| U3 Review 27's two code should-fix items | 0892937 | §43's hold reason decided in a worker thread (`Daemon.decide_held_reason`, awaited before `job.held` is filed; `_publish_held` async; `_held_reason` removed); `runner.turn_env` is `job_env`'s decision less `HANDS_JOB`, and both `hands doctor --live` turns build their environment with it |
| U4 H-077, ruled | d20e511 | `spool.carries_playbook`: an entry whose casefolded path equals the casefolded configured playbook path (`playbook_repo_path`, the cwd's `--show-prefix` before `[playbook] path`, §38) or either fixed name; the engine's hold, its published reason and `kit check`'s `WARN playbook:` use it; the WARN judges the repository's playbook at the configured path too and names the paths it knows (the two fixed names only without a configuration); H-077 resolved |
| U5 Final report | (this commit) | this file; the plan, checkpoint and journal; then the pull request and the Hosted review table |

## 2. What the tests prove

- Under a human pause on a role-mode autonomous playbook: a `builder.done`
  is kept and no review starts, and `resume` starts the review; a review's
  end is kept (no consultation) until `resume`; an engine-approved apply's
  end is kept for the kickoff; a `builder.done` whose rule is `stop` is
  kept and stops at `resume`; a `notify` end fires at once; the human's own
  send replaces the kept `builder.done`; a consultation ending under the
  pause leaves its apply held for the human, with no engine approval and no
  engine kickoff after the human approves; a decisions kit's apply held,
  approved and ended under the pause does not un-pause it, the end stays
  kept, no stop for the hold (U1).
- Stops under a human pause: a monitor tripwire's `stop` rule and a
  `max_resumes` stop are notified once, the kept end staying; after a
  suppressed tripwire a restart does not resume the orphaned builder; a
  driver's `escalate` end is notified and not kept; a second `pause` keeps
  everything and sets no mark, and a restart after it still resumes the
  orphaned builder through `builder.orphaned → resume` with the kept ends
  kept (one test over a real daemon); a restart under a rule's stop resumes
  nothing; a limited builder is resumed by §6 and its end kept (U1).
- `resume`: refused with the load's reason when an engine-approved apply
  committed a playbook that does not load, then accepted once it loads; a
  playbook committed at rest is the one replayed under; with no playbook
  and nothing kept it un-pauses; two kept ends where the first replayed
  stops, or starts a job, discard and name the second; a replayed `keep`
  the API refuses stops the replay; this repository's phone-mode
  `PLAYBOOK.toml` keeps the review's `blockers=0` stop and stops at
  `resume`; `go` and `consult` are refused naming `resume` (engine, socket
  and phone); a pause over an existing stop is still a no-op; an unpaused
  pipeline is unchanged (U1).
- `hands: at rest`: published once when the kept builder's end arrives and
  nothing else runs; not while a review runs, a hold waits or a §6 resume
  is scheduled; at once for a pause over an idle pipeline; after a denial,
  after the human's own running job and a queued one are cancelled (over a
  real daemon), and after a job fails with no resume rule; not again after
  a restart; again, with the new list, when a kept end is replaced; its
  body naming the kept end; not under a stop that is not a human pause (U2).
- The §19 reader is red when a one-word title (`go`) has no row of its own
  and green with it (U2).
- The hold reason's zip reads at filing and at a start run on a thread
  other than the loop's (red with the fix reverted), and the published hold
  still carries §43's reason; each `doctor --live` turn with an inherited
  `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1` and a stale hook carries no
  value, and with the installed copy the builder and aux turns carry `=1`
  (U3).
- `playbook.toml`, `Playbook.toml`, `meta/playbook.toml` and
  `Meta/PLAYBOOK.toml` are each held by the engine and warned by `kit
  check`; a configured `ops/rules.toml` and `OPS/Rules.toml` are held under
  that configuration and warned when the repository's playbook there is
  role mode with autonomy; `kit check` without a configuration warns on the
  fixed names and says it knows only those; an ordinary kit draws no
  warning (U4).

## 3. NOT PROVEN

- No real phone `pause` and `resume` has run on a role-mode series; no real
  `at rest` has reached a phone; no real restart under a human pause has
  resumed a builder (the restart is a test over a daemon with
  tests/fake_claude.py). The live gate is another project's three owner
  commits after the install (DESIGN §44).
- §6's resume under a human pause is driven through the limit manager in an
  engine test, not a running daemon (U1).
- The `at rest` check after a job the runner could not spawn is wired but
  untested; a §6 resume that later gives up is a stop, not a job's end, so
  no `at rest` follows it (U2).
- The release routine's warning about a project paused at a restart is not
  in docs/OPERATIONS.md; nothing was retired, it is left for the install
  (U2).
- `defer_hold` still runs `kit_apply_problem` on the event loop (outside
  should-fix 1's scope: no zip read); the live turns' `HANDS_DOCS`,
  `HANDS_CLONE` and `HANDS_KITS` are not asserted (U3).
- handsd's `kit check` reads the configured playbook path from the
  repository root; with a builder cwd below the root its repository-side
  WARN would look in the wrong place (the engine's hold is not affected);
  when git cannot name the cwd's place the prefix is taken as empty; no
  case-insensitive filesystem has been tried; no end-to-end daemon test
  with a configured path; the handbook's §43 lines still name the two exact
  paths (U4).

## 4. Deviations

- U1 also changed `src/hands/spool.py` (the two new inbox kinds), the two
  §19 rows its new titles required, and eight existing tests that used
  `pause` for any stop (now a rule's stop), plus tests/test_wake.py.
- U2 decided the moment in `playbook.py` with calls from `limits.py`,
  `daemon.py` and `api.py`; four tests in tests/test_playbook.py expect the
  `at rest` that a pause over an idle pipeline now publishes; §19 gained a
  `kit` row and the `architect`/`builder` row was split so each title
  starts a row.
- U3 also changed `src/hands/api.py` (the reason decided before filing) and
  re-keyed one exemption in tests/test_operator_table.py.
- Where §44 is silent: no `pipeline.kept` inbox kind; a `resume` of a
  non-human stop does not reload; a replayed end "starts a job" when its
  rule records a fired job (U1); no inbox event for `at rest` (U2); a live
  turn carries no `HANDS_JOB` (U3); an empty prefix when git cannot name
  the cwd's place (U4). Each is in its commit's body.

## Review items

| Item | Disposition |
|---|---|
| REVIEW-27 should-fix 1 — the daemon computes §43's hold reason on the event loop | closed by U3 (0892937) |
| REVIEW-27 should-fix 2 — `doctor --live` bypasses `job_env` | closed by U3 (0892937) |
| REVIEW-27 should-fix 3 — the operator table's reader matches a one-word title by substring | closed by U2 (adb061b) |
| H-077 — a kit entry naming the playbook in another case | closed by U4 (d20e511) |
| H-078 — a human pause drops the event that would start the next step | closed by U1 (d367373) and U2 (adb061b) |
