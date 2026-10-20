# FINAL-REPORT-28 — mission 28: a pause that holds the next step

VERDICT: mission 28 finished pr=8

Source: meta/BUILDER-28-PROMPT.md, DESIGN v3.27 §44 (with §6, §10, §19,
§31, §32, §33, §36, §38, §39, §43), meta/reviews/REVIEW-27.md,
meta/findings/FINDINGS.md (H-077, H-078). Branch `mission-28`, from main
b943019. Gate: `./scripts/check` green three consecutive runs before every
unit commit: 5056 tests at U0, 5087 at U1, 5101 at U2, 5105 at U3, 5125 at
U4, 5132 at 58deee7 and 5137 at the final tip (885f07c plus this
commit), three consecutive green runs.

## 1. What changed (sha per unit)

| Unit | sha | What |
|---|---|---|
| U0 Plan, branch and findings | 4fed073 | `plan:` — plan, checkpoint; H-078 filed ("decided (DESIGN §44), scheduled for U1 and U2"); H-077 "decided (DESIGN §44 ...), scheduled for U4" |
| U1 A human pause holds the next step | d367373 | a human pause (`paused_by` `cli`/`phone`) keeps a builder/aux/driver end whose decision is a send, consult or stop (or the engine's kickoff after an engine-approved apply), one per role (`pipeline.kept_replaced`); a notify end fires at once; a `resume` rule fires until a stop is suppressed under the pause (the `suppressed_stop` mark); every suppressed stop notified once; a pause over it a quiet no-op; jobs of an un-pausing origin do not un-pause it; `go` and `consult` refused naming `resume`; `resume` reloads, is refused on a bad load or kept ends with no playbook, replays up to the first end that starts a job or stops and discards the rest (`pipeline.kept_discarded`, `hands: resume discarded kept ends`); `kept` and the mark in `pipeline.json`; `hands pipeline`'s `kept` lines, the phone's `status`, `hands show`'s `resumed_from`; tests/test_human_pause.py added |
| U2 At rest, the documents and the table's titles | adb061b | `hands: at rest` once per human pause at the first moment no job is running, queued or held and no §6 resume is scheduled, naming each kept end (verdict cut to 100) or none; the `at_rest` mark in `pipeline.json`, republished with the new list when a kept end is replaced after it; checked at the pause, after every job end the engine hears, a denial, a queued cancel and a spawn failure; handbook §10, §14, §18, §19; docs/PLAYBOOK.md "A human pause"; docs/OPERATIONS.md "A quiet moment"; the §19 reader matches a title at a row's start; H-078 resolved |
| U3 Review 27's two code should-fix items | 0892937 | §43's hold reason decided in a worker thread (`Daemon.decide_held_reason`, awaited before `job.held` is filed; `_publish_held` async; `_held_reason` removed); `runner.turn_env` is `job_env`'s decision less `HANDS_JOB`, and both `hands doctor --live` turns build their environment with it |
| U4 H-077, ruled | d20e511 | `spool.carries_playbook`: an entry whose casefolded path equals the casefolded configured playbook path (`playbook_repo_path`, the cwd's `--show-prefix` before `[playbook] path`, §38) or either fixed name; the engine's hold, its published reason and `kit check`'s `WARN playbook:` use it; the WARN judges the repository's playbook at the configured path too and names the paths it knows (the two fixed names only without a configuration); H-077 resolved |
| U5 Final report, the pull request and the hosted review | 8453b8a, 58deee7, 885f07c, (this commit) | this file (8453b8a); PR #8; `playbook:` 58deee7 (hosted findings 1, 3, 4, 6: a `pause` over a human pause records nothing; `at rest` checked after the daemon's start fold and after a §6 resume that ends without a job; a refused `resume` restores the playbook as loaded before it); `daemon:` 885f07c (hosted findings 2, 5: a hold approved or denied while its reason is computed is not announced; the owner's WARN reads the configured playbook at the repository root; docs/PLAYBOOK.md's pause sentence); the Hosted review table and archive meta/reviews/hosted/PR-8/1..4 (this commit) |

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
  untested (U2). Since 58deee7 a §6 resume that ends without a job is
  followed by the check (its test replaces the daemon's enqueue and sleep,
  no real queue failure), and the daemon's start checks it after its fold;
  an `at rest` due at a start is carried by the start notification, not
  published under its own title.
- The release routine's warning about a project paused at a restart is not
  in docs/OPERATIONS.md; nothing was retired, it is left for the install
  (U2).
- `defer_hold` still runs `kit_apply_problem` on the event loop (outside
  should-fix 1's scope: no zip read); the live turns' `HANDS_DOCS`,
  `HANDS_CLONE` and `HANDS_KITS` are not asserted (U3).
- Since 885f07c `kit check`'s WARN reads the configured playbook at the
  repository root (`git rev-parse --show-toplevel`; the directory passed in
  when git cannot name it); the two fixed names are still read under the
  directory passed in, untested below the root; when git cannot name the
  cwd's place the engine's prefix is taken as empty; no
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

## Hosted review

PR #8, `qodo-code-review[bot]`, read with `hands hosted-review 8`. Fetch 1
(Code Review comment 6278731380, at 8453b8a): Bugs 5, Rule violations 1,
Cross-repo conflicts 1, Skill insights 0; 7 of 7 open. Fetch 2 (updated
2026-10-19T23:12:02Z, at 58deee7): findings 1, 3, 4, 6 marked resolved.
Fetch 3: before the bot re-read 885f07c (the inline comments' metadata
moved). Fetch 4 (updated 2026-10-19T23:54:51Z, at 885f07c): Bugs 0, Rule
violations 0, Cross-repo conflicts 1; 1 of 7 open (7). Archive
meta/reviews/hosted/PR-8/1..4. Numbers are fetch 1's.

| # | Finding (verbatim, as the bot wrote it) | Disposition |
|---|---|---|
| 1 | Repeated pauses create false stop events — PlaybookEngine.pause() passes quiet=True for an already paused pipeline, but stop() still appends pipeline.stop_suppressed before checking that flag. A repeated pause therefore creates a suppressed-stop record even though the pause is meant to be a no-op, affecting the inbox and stop history without notifying the operator. | fixed in 58deee7 |
| 2 | Decided jobs receive late hold notices — Api.send and _publish_held await held-reason computation, then announce a hold without rechecking the job’s gate or current state. If another client approves or denies the job during that wait, the later notification describes a hold that no longer exists and can create new approval buttons. | fixed in 885f07c |
| 3 | Restarts can miss the quiet moment — check_at_rest runs when a pause is sent or a job ends, but startup does not run it for a restored human pause after resolving pending retries. If a pending limited job is not rescheduled and all persisted jobs are terminal, the unset at-rest mark has no subsequent job transition to trigger the notification. | fixed in 58deee7 |
| 4 | A failed retry hides the quiet moment — check_at_rest excludes a pause while a limit-resume task is scheduled, but nothing checks again when _resume_after fails without creating a job. If the retry fails while no other job is active, its suppressed stop is announced but the human never receives the at-rest notification for that pause. | fixed in 58deee7 |
| 5 | Nested builders miss a playbook warning — _owner_warning joins the repository-relative configured playbook path to its repo argument, but daemon-side kit filing passes the builder's working directory rather than the repository root. When that directory is below the root and the kit changes a custom-path playbook, the check looks beneath the directory twice and can omit the warning that the current autonomous playbook requires human ownership. | fixed in 885f07c |
| 6 | Ends arriving after a refused resume are lost — resume calls _load(stop_on_error=False), and a failed load sets self.playbook = None before it returns, while the human pause stays. After that, _under_human_pause returns early on `book is None`, so a builder/aux/driver end that arrives later is neither kept nor notified, and `resume` rules on orphaned or failed jobs stop firing; the next successful resume then has nothing to replay. | fixed in 58deee7 |
| 7 | Owner kits suggest a refused command — _under_human_pause fires Discotrade’s builder.done kit-applied notification immediately, leaving its instruction to send go unchanged. When an owner decisions kit finishes during a human pause, go is refused until the operator sends resume. | dismissed: this is DESIGN §44's rule (a decisions kit applied at rest commits and the kept end still waits; `go` is refused under a human pause, its refusal naming `resume`; "after approving the apply, the human sends `resume`, then `go`"), and the notify text is another project's playbook, not this repository's |

