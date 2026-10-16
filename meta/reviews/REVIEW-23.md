# REVIEW-23 — cold review of hands mission 23
reviewed: 94ab38cb5639d751d4ffea65aea1513f9877b771

VERDICT: review mission 23 blockers=0 should-fix=9

Shape: pull request, first review of the branch. `meta/BUILDER-23-PROMPT.md`
§Branch says "Pull request" on `mission-23`. `gh pr list --head mission-23
--state open` returns PR #4 (base `main`, headRefOid `94ab38c`). The base is
`git merge-base origin/main origin/mission-23` = `23eff6c` (the kit). The
commits under review (`git log --oneline 23eff6c..origin/mission-23
^origin/main`):

    94ab38c report: mission 23 hosted review dispositions, H-061, the PR #4 archive
    1276251 hosted, phone, guard, api: the hosted review's findings on PR #4
    d50af2a report: mission 23 final report
    515b736 docs: no_background runs as python3 -I; restart, kits' hooks, [server], ids, ruling round
    a09b85f project: a failed clone in project add removes what it created; the role escalates rulings
    2b4df10 architect: consult prompt names the installed handbook; guard reads HANDS_DOCS
    dc9698e protocol: restore git-rms a deleted file; hosted review by command; brief fixes it in the PR
    59678ee hosted: hands hosted-review <pr> reads the bot's review mechanically
    0c6d725 progress: read the checkpoint at the repository root; README names ten commands
    e36d558 playbook: blocked-consult regex judged on samples; inclusive owner fallbacks; journal reminder
    bcc3d53 daemon: orphaned replies published, aux.orphaned resumed, refusals answered, lenient ids
    9c5d729 who: store the fingerprint whenever the blanked picture equals the published one
    b7b5c10 plan: mission 23 plan, branch mission-23, H-055..H-060 filed, H-051..H-054 decided

One sub-agent per unit commit (U1–U9 and U10's fix commit 1276251), one at
a time. I read the `plan:` commit (U0, b7b5c10) and the two `report:`
commits (d50af2a, 94ab38c) myself.

## Blockers

None.

## Should-fix

1. **U2 (bcc3d53): §39's lenient ids for `answer` and `reply` are not
   built, and no finding records the departure.**
   - §39 says "A job id in `approve`, `deny`, `answer`, `reply` and
     `cancel` is matched…". `answer <secret> <text>` and `reply <secret>
     <text>` carry no job id (phone.py:10-20, dispatch phone.py:371-374), so
     the builder applied lenient matching to `approve`, `deny`, `cancel` only.
   - The reading is sound, but it is recorded only in the commit body, the
     report's Deviations, a parenthesis in H-059's Status line and a
     docstring. CLAUDE.md: "the design wins unless a finding in
     meta/findings/FINDINGS.md says otherwise".
   - Same state: `reply`/`answer` refusals keep the titles `hands: reply` /
     `hands: answer` where §39 says titled `<command>`.
   - Fix: a finding asking the architect to correct §39's command list (and
     the title wording), so DESIGN and the code agree.
2. **U10 (1276251): the architect's read roots are narrower than §39 says,
   with no finding.**
   - §39 (H-051 ruling): "the guard's read roots gain `HANDS_DOCS`".
     bash_guard.py `DOCS_SUBDIRS` / `Reads.__init__` admits only
     `$HANDS_DOCS/docs` and `$HANDS_DOCS/templates`.
   - The narrowing answers hosted finding "Architects can read unrelated
     hands files" (in a source-tree install `docs_root()` is the repository
     root) and is more restrictive, so it is safe. But it is a design change
     made inside the PR: the brief's U10 says fix findings "within §39", and
     §39 says one "that needs a design decision is filed, never fixed in
     silence". It is stated in the commit body and the report only.
   - H-051's Status line (FINDINGS.md:2313) still says "architect mode's read
     roots gain `HANDS_DOCS`", now stale.
   - Fix: file a finding for the architect to adopt the narrower roots in
     DESIGN, and correct H-051's Status line.
3. **U5 / U10 (59678ee, 1276251): "the verdict from the Code Review comment
   only" is held by no test.**
   - Two sub-agents mutated it independently. Dropping `kind ==
     "issue-comment"` from `_is_code_review` (hosted.py:222 at the tip) leaves
     all 16 hosted tests green. So does `max`→`min` in `_code_review`
     (hosted.py:276), which would take the oldest of two Code Review comments.
   - §39 makes this the command's central rule ("takes the verdict from the
     Code Review comment only"), and the protocol relies on it.
   - Fix: a fixture with a review body or inline comment headed "Code Review"
     (must be ignored) and one with two Code Review issue comments (newest
     wins).
4. **U10 (1276251): exit 4 is half-proven.**
   - The commit claims exit 4 when the header counts findings above zero and
     no parsed finding is open. Only the "nothing parsed" half is tested.
   - Changing `not open_` to `not current` (hosted.py ~431) leaves every test
     green, so "header > 0, every parsed finding resolved" — the case where
     the bot reset nothing but struck everything — is unpinned.
   - Fix: a fixture whose header counts 1 and whose only finding is struck
     through, expecting exit 4.
5. **U10 (1276251): the secret redaction can be bypassed by a backslash.**
   - `_refuse` → `_redact` (phone.py:713) cuts `re.escape(secret)` out of the
     reason. The no-such-job reason quotes the typed id with `{typed!r}`
     (api.py ~196), and repr doubles a backslash, so a secret containing `\`
     no longer matches and is published and logged nearly verbatim.
   - Config only requires the secret to be one word, so this is reachable.
     The report's NOT PROVEN says "the redaction removes the full secret
     only", which does not cover this.
   - Fix: redact before formatting (or format the typed id with `str`, not
     `repr`), with a test using a secret that contains `\`.
6. **U3 (e36d558): the journal reminder is decided when a send is enqueued,
   not when it runs.**
   - api.py:340-346 prefixes the prompt at `_send`. A held or queued send
     can carry a stale "commit `meta/journal.md` first" sentence after the
     journal was committed, and the hold notification shows hands' sentence
     inside the human's prompt.
   - The report's NOT PROVEN names "on a held cli send" as unproven; this is
     the concrete consequence.
   - Fix: decide at dispatch, or say in the sentence that it is conditional.
7. **U9 (515b736) / U10 (1276251): docs/INTEGRATION.md says a malformed
   line carrying a nonce is answered; the code keeps it silent.**
   - INTEGRATION.md:760-766: "A command carrying the right secret (or, for
     `approve` and `deny`, the job's nonce) that handsd refuses — … a
     malformed line — is published".
   - phone.py:410-414 (`_decide`): a malformed `approve`/`deny` is refused
     only when its last word is the secret; with a nonce it is
     `_ignore`d (logged, not published).
   - Fix: one of the two; the doc is the cheaper change.
8. **U7 (2b4df10): `architect/CLAUDE.md` rule 2 (Read the paths the prompt
   names) is held by no test.** Reverting that file alone leaves the guard,
   handbook, docs, kit and project_add tests green. The brief's U7 lists the
   rule; the docs tests pin every other sentence of this mission. Fix: an
   instruction test pinning rule 2's text.
9. **U8 (a09b85f): two parts of the failed-clone behaviour are unpinned.**
   - The dry run's `git clone -- {plan.repo}` text (project.py:300): dropping
     the `--` changes no test result.
   - "A failed push-URL step counts as a failed clone" (project.py ~343-346):
     taking `set-url` out of the failure condition changes no test result.
     In that case the message still says "the clone of <url> failed".
   - Fix: a dry-run assertion on `--`, and a fake `git` whose `remote
     set-url` fails.

## Hosted review

`qodo-code-review[bot]` on PR #4, read with `gh api` (issue comments,
review comments and reviews, `--paginate`) at about 00:43Z. Three sources:
the summary issue comment 6204582348 (updated 2026-10-15T23:41:04Z), the
Code Review issue comment 6204626963 (edited in place, latest
2026-10-16T00:42:37Z, its footer naming the tip `94ab38c`), and one
`COMMENTED` review 5541251475 with eleven inline comments (all
2026-10-15T23:44:39Z, unchanged since). The Code Review header at the tip:
`🐞 Bugs (0)  📘 Rule violations (3)  🔗 Cross-repo conflicts (1)
📜 Skill insights (0)`; seven of eleven findings struck through `✓
Resolved`, four open. The bot's in-place re-review of `94ab38c` (00:42Z) is
later than the builder's last archived fetch (`PR-4/6`, comment
`updated_at` 00:19:46Z); its open set is the same four, so the builder's
table still holds. The findings, quoted verbatim by their titles, with the
current comment's number (the report's table uses fetch 5's numbers, given
in brackets):

1. [2] "Discotrade reviews stop after restarts" (`🔗 Cross-repo conflict`,
   src/hands/playbook.py:153): **dismissed** for hands — the fix lives in
   another repository's playbook, which hands does not edit (§38's
   separation rule). Builder's disposition: finding H-061 filed — **audit:
   holds**; H-061 is in FINDINGS.md (line 2523, Status open) and cites the
   archived comment.
2. [1] "~~A refused phone command can expose its secret~~ ✓ Resolved"
   (src/hands/phone.py:426): **confirmed, fixed in the PR** (1276251; the
   U10 sub-agent saw its test go red with phone.py reverted). Residual gap
   carried as **should-fix 5**. Builder's disposition: fixed in 1276251 —
   **audit: holds**; the fix touches the anchor (`_refuse`) and the comment
   shows it resolved.
3. [7] "~~Architects can read unrelated hands files~~ ✓ Resolved"
   (driver/hooks/bash_guard.py:653): **confirmed, fixed in the PR**
   (1276251). Builder's disposition: fixed in 1276251 — **audit: the fix
   holds, but it needed a design decision (narrower than §39's roots) and no
   finding was filed**; carried as **should-fix 2**.
4. [6] "~~A failed archive leaves a false review fetch~~ ✓ Resolved"
   (src/hands/hosted.py:158): **confirmed, fixed in the PR** (1276251; red
   when the archive is written straight into `<k>`). Builder's disposition:
   fixed in 1276251 — **audit: holds.**
5. [8] "~~A misparsed Code Review reads as a clean review~~ ✓ Resolved"
   (src/hands/hosted.py:386): **confirmed, fixed in the PR** (1276251; exit 4
   red when its branch is removed). Half its claim is untested: carried as
   **should-fix 4**. Builder's disposition: fixed in 1276251 — **audit:
   holds.**
6. [5] "Hosted reviews hide the verdict" (`📘 Rule violation`,
   src/hands/hosted.py:333): **dismissed.** The rule it cites ("Prefix
   human-visible reports with a `VERDICT:` line") is for agent replies; a
   tool printing `VERDICT:` would be matched by the playbook's verdict rules
   as an agent verdict. The command's verdict is its last line and exit
   status. Builder's disposition: dismissed with that reason — **audit:
   holds.**
7. [3] "The review command alters the repository" (`📘 Rule violation`,
   src/hands/hosted.py:156): **dismissed.** §39 requires the command to
   archive under `meta/reviews/hosted/PR-<n>/<k>/` and the reviewer to
   commit it; the "read-only driver" rule is about the driver role's guard,
   not a `hands` subcommand run by the builder or reviewer. Builder's
   disposition: dismissed with that reason — **audit: holds.**
8. [4] "Reports omit auditable tool evidence" (`📘 Rule violation`,
   meta/FINAL-REPORT-23.md:18): **dismissed**, as in REVIEW-20, 21 and 22:
   short shas are the repository's convention, this review records the full
   tip, and the sub-agents reproduced every gate count the report gives
   (4391, 4407, 4424, 4426, 4434, 4465, 4474, 4479, 4493, 4504). Builder's
   disposition: dismissed with that reason — **audit: holds.**
9. [11] "~~A send to the builder can stall the daemon on git~~ ✓ Resolved"
   (src/hands/api.py:340): **confirmed, fixed in the PR** (1276251; the
   `asyncio.to_thread` test goes red with api.py reverted; real timing not
   proven). Builder's disposition: fixed in 1276251 — **audit: holds.**
10. [10] "~~Each wait-loop retry writes another archive~~ ✓ Resolved"
    (src/hands/hosted.py:376): **confirmed, fixed in the PR** (1276251; red
    with both not-yet checks removed). Builder's disposition: fixed in
    1276251, fetches 1-4 kept as its evidence — **audit: holds**; `PR-4/1..4`
    hold only the placeholder and summary comments, as the report says.
11. [9] "~~A finding titled with 'Resolved' counts as fixed~~ ✓ Resolved"
    (src/hands/hosted.py:57): **confirmed, fixed in the PR** (1276251; red
    with bare `Resolved` back in `_STRUCK`). Builder's disposition: fixed in
    1276251 — **audit: holds.**

Every finding has one row in the report's `## Hosted review` table; no
fix's commit misses its anchor; every dismissal has a reason; the one filed
finding exists. The only disposition that needed a design decision is
finding 3 (should-fix 2).

## Notes

- **Gate (my one run).** `./scripts/check` passed at the tip `94ab38c` in a
  fresh worktree: `4504 passed in 363.53s (0:06:03)`, `== cli smoke ==`,
  `check: green`, exit 0.
  - `git diff 1276251 94ab38c` touches only meta/ (CHECKPOINT,
    FINAL-REPORT-23, FINDINGS, journal, plan, and the archive
    `meta/reviews/hosted/PR-4/1..6/`), so the tip's code is 1276251's.
  - Every unit commit is green at its own sha: U1 4391, U2 4407, U3 4424,
    U4 4426, U5 4434, U6 4465, U7 4474, U8 4479, U9 4493, U10 4504 — each
    equal to the report's count.
- **Schedule (UTC, 2026-10-16; one sub-agent at a time, so only one
  `./scripts/check` runs inside the 20-minute cap).** Start and end as each
  sub-agent reported them from `date -u`:
  - U1 9c5d729 00:43–00:50
  - U2 bcc3d53 00:50–01:06
  - U3 e36d558 01:06–01:13
  - U4 0c6d725 01:14–01:26 (the sub-agent started the gate a second time
    by mistake and discarded it; two runs, sequential, no overlap)
  - U5 59678ee 01:26–01:33
  - U6 dc9698e 01:33–01:41
  - U7 2b4df10 01:41–01:49
  - U8 a09b85f 01:50–01:57
  - U9 515b736 01:57–02:05
  - U10 1276251 02:05–02:16
  - My gate at the tip: 02:16–02:22
- **Protocol version.** I followed the protocol on `main` (23eff6c), as the
  prompt asked, and committed only this file. U6 and 1276251 rewrite the
  protocol on the branch: from the next review on, the hosted review is read
  by a fresh sub-agent running `hands hosted-review <pr>` and its archive is
  committed with the review file. This review read the bot with `gh api`
  directly and wrote no archive. The sub-agents used the branch's restore
  (`git rm -q -f` for a file absent at `<sha>`, then `git status --short`
  empty); no unit commit deletes a file, so the two wordings agree here.
- **U0 (b7b5c10, `plan:`), read by me.** H-055..H-060 filed, H-051..H-054
  set to "decided (DESIGN §39, mission 23 U<n>)", `origin/mission-23`
  exists. The brief's gate holds.
- **Report commits (d50af2a, 94ab38c), read by me.** The report has NOT
  PROVEN, the `## Review items` table (REVIEW-22 should-fix 1–12, each
  named by its unit) and the `## Hosted review` table. The Deviations
  (`git rm -q -f`; `answer`/`reply` carry no id) are confirmed on disk by
  the U6 and U2 sub-agents; the second lacks a finding (should-fix 1).
- **Acceptance.** Every unit body lists every file it touches (all ten
  sub-agents checked against `--stat`); the orphaned-review resume
  (test_daemon_stop.py:333) and `aux.orphaned → resume` in PLAYBOOK.toml
  hold; `Omv9a9z9a-arir` resolves and a refused `approve` is published;
  `hands hosted-review` archives two fetches and diffs them on fixtures;
  both protocols `git rm` and require a clean status, neither says "stash".
- **NOT PROVEN, checked against the sub-agents.** The report's list stands.
  The sub-agents add: the verdict-source rule unpinned (should-fix 3); exit
  4's second half (should-fix 4); `progress` with a nested cwd is tested at
  `_checkpoint_line`, not end to end through the phone; the "next apply and
  `go` un-pause a clean-review stop" sentence is checked as text only; an
  ambiguous prefix from the phone is tested at `match_job_id` only; the
  wrong-secret silence test uses only nonexistent job ids; the new
  INTEGRATION wording on `show-toplevel` is unpinned.
- **Nits, not carried.** hosted.py:364-374 duplicates the "Code Review
  comment is not there yet" check and message; the handbook's §18 `status`
  bullet has an unwrapped long line.

## Per-commit verdicts

**U1 9c5d729** (00:43–00:50)

> Start 00:43 UTC. Review of 9c5d729: no blockers and no should-fix items.
>
> 1. **Unit:** the commit body names mission 23 U1, the who watcher: DESIGN §39 ("Review 22's should-fix items") with §24 and §38, and REVIEW-22 should-fix 1 and 2. The files it lists, `src/hands/who.py` and `tests/test_who.py`, are exactly the two in `--stat`. Both claims, verified against §39 and the brief:
>    - **Fix (who.py:925-929):** `self.fp = fp` is stored whenever `shown == self.shown`.
>    - **Publish condition (who.py:924):** still requires both the fingerprint and the blanked picture to differ, unchanged.
> 2. **Test-first: passes.**
>    - **Reverting `who.py` to the parent turned two tests red:** the stored-fingerprint test and Review 22's reproduction.
>    - **The reproduction returned exactly `[True, True, False, True]`** with the fix reverted (assert at test_who.py:1334). With the fix it returns `[True, True, False, False]` and posts 2 messages, so the human's own session alone publishes nothing.
>    - **The two comparison tests stayed green under the revert**, which is expected: should-fix 1 asked for a test of a comparison that already existed. I confirmed they hold it with the mutations the body names:
>      - `changed = fp != self.fp` turns the fingerprint-only test red (test_who.py:1263).
>      - `changed = shown != self.shown` turns the picture-only test red (test_who.py:1280).
>    - So the comparison is pinned in both directions: fingerprint changes while the picture doesn't, and the reverse. Restores left `git status --short` empty.
> 3. **Gate:** `./scripts/check` is green. Pytest summary line: `4391 passed in 357.91s (0:05:57)`. Final line: `check: green`.
> 4. **Design conformance: passes.** The change matches §39 and the brief's U1 text, and nothing forbidden was touched (DESIGN.md, meta/plan.md, meta/CHECKPOINT.md). Nothing in the commit body is contradicted by the disk, including the test count ("four tests"). The disclosed design silence (the fingerprint is also stored on a request scan or inside the floor) is a reasonable reading of "whenever".
>
> **Not proven:** the reproduction runs on scripted transcripts and `clock=1000.0` with `min_gap=0`, so it does not exercise the floor and no real phone or ntfy server was involved. A failed requested publish still stores the fingerprint when the picture is unchanged; that is harmless and no test covers it.
>
> The worktree is removed. End 00:50 UTC.

**U2 bcc3d53** (00:50–01:06)

> Start 00:50 UTC. bcc3d53 passes all four points. There are no blockers and one low should-fix candidate (the `answer`/`reply` deviation, see (a)).
>
> 1. **Unit:** mission 23 U2, "Orphans, refusals and ids". The body claims §39 (should-fix items, H-057, H-058/H-059) plus §38's orphan machinery, REVIEW-22 should-fix 3 and 4, and H-057, H-058, H-059. The body lists all 14 files in the stat.
> 2. **Test-first: PASS.** I reverted all 9 product and data files to SHA~1. 15 of the 16 new tests went red. The one that stayed green is `test_a_refused_command_with_a_wrong_or_missing_secret_stays_silent`, which is expected: it checks that nothing is published, which was already true before the change. Two kinds of red were side effects rather than real failures. Some existing `test_playbook` tests went red only because the reverted `PLAYBOOK.toml` is dirty and trips `PlaybookNotCommitted`. Four existing phone tests went red on purpose: they now expect the published `<cmd> refused` message. After the restore, `git status --short` was empty.
> 3. **Gate: GREEN.** `4407 passed in 360.53s (0:06:00)` / `check: green`
> 4. **Conformance: PASS.** DESIGN.md, `meta/plan.md` and `meta/CHECKPOINT.md` were not touched. Your focus points:
>    - **(a)** The deviation is true. `src/hands/phone.py:10-20` gives `reply <secret> <text>` and `answer <secret> <text>`, and the dispatch at `phone.py:371-374` takes no job id. The CLI has no id for either. Lenient ids are in approve/deny via `phone.py:420`, and cancel/decide via `api.py` `match_job_id`.
>      - It was not filed as its own finding. It shows up only in the commit body, the final report, a parenthetical in the H-059 Status line in FINDINGS.md (origin/mission-23, ~line 2495: "(answer and reply carry no id)"), and the `match_job_id` docstring.
>      - §39 and the brief (`BUILDER-23-PROMPT.md:135`) still list `answer` and `reply`. Under CLAUDE.md's "design wins unless a finding says otherwise", that is the should-fix candidate.
>      - A second deviation is in the same state, noted in the body and never filed: `reply`/`answer` refusals keep the titles `hands: reply`/`hands: answer`, where §39 says `<command>`.
>    - **(b)** Proven. `tests/test_daemon_stop.py:333`: a stop leaves the aux job as `orphaned`/`daemon_stop`/`keep`. The next start re-sends the same prompt with context `clear` and origin `playbook`, and the start notification says "which a daemon stop orphaned". The max_resumes=0 bound is held at `:377`. This uses a tmp-playbook rule (`AUX_RESUME`); the shipped playbooks are covered separately in (e).
>    - **(c)** Proven. `tests/test_phone.py:3306`: `Omv9a9z9a-arir` resolves to `0mv9a9z9a-arir`. Line 3311 shows the ambiguous prefix `Omv9a9z9` refused with both candidates named. Lines 3228 and 3242 are the end-to-end phone approve and deny.
>    - **(d)** Proven. `test_phone.py:3181`: refusals for no such job, malformed, and not held are published titled with their command, on the events topic, and never carry the secret. Line 3206: wrong or missing secret publishes nothing. That silence test only uses nonexistent job ids, not a real held job.
>    - **(e)** Present. `PLAYBOOK.toml:111`, `templates/PLAYBOOK-runs.toml:112` and `templates/PLAYBOOK-missions.toml:129` each carry `aux.orphaned → resume`. `tests/test_kit.py:2635` parses each with exactly one such rule. Kit check accepts them: the existing filled-template kit-check tests stay green.
>
> Not proven: a live handsd restart with a real review, a real ntfy server, or any running daemon on this code (the commit body says so too). An ambiguous prefix sent from the phone is covered at the `match_job_id` level only, not end to end.
>
> Worktree removed. End 01:06 UTC.

**U3 e36d558** (01:06–01:13)

> I reviewed e36d558 (U3) and found no blockers; the gate is green.
>
> 1. **Unit and sections:** the body names mission 23 U3, §39 ("Review 22's should-fix items" and the H-060 paragraph), with §27 and §36/§38, REVIEW-22 should-fix 5 and 7, and H-060. It lists all four files in the stat: `src/hands/playbook.py`, `src/hands/api.py`, `tests/test_playbook.py`, `tests/test_phone.py`.
> 2. **Test-first:** confirmed. With both product files reverted to e36d558~1, 13 of 17 new test cases fail: the regex cases `(?i)`, a class, not-blocked, unblocked, lookahead, blocked|finished and any-mission; both owner-fallback tests; the §36 listing strip; and the dirty answer, dirty keep and dirty clear sends. The 4 that pass are expected to pass on old code too: the plain `blocked` regex and the three clean-journal cases. Restored, and `git status --short` was empty.
> 3. **`./scripts/check`:** `4424 passed in 357.58s (0:05:57)`, final line `check: green`.
> 4. **Design conformance:** it matches §39 and the brief.
>    - **Consult-rule regex:** it is compiled, then searched against `VERDICT: mission 1 blocked U2` (must match) and `VERDICT: mission 1 finished` (must not). `_choose` matches rules with `.search` the same way. `(?i)` loads.
>    - **Owner-file fallbacks:** both are inclusive with a note. A sha that `rev-parse --verify` rejects lists every owner file under a note naming the sha. A file touched since the consultation but untracked at HEAD is listed with a note and no text.
>    - **Journal prefix:** it is added only when `git status --porcelain -- meta/journal.md` prints something. It applies to `answer` and to cli builder sends, keep and clear, after §8's gate has judged the sender's text. `answer.sent` keeps the human's text alone, and aux is never prefixed.
>    - DESIGN.md, `meta/plan.md` and `meta/CHECKPOINT.md` are untouched, and nothing in the body contradicts the disk.
>
> **Not proven** (the body says so too): a builder cwd below the repository root for the journal check, the prefix on a held cli send, and a git call that times out. The body's choice to count an untracked journal as dirty has no test.
>
> Should-fix candidates (minor):
> - `src/hands/api.py:340-346`: the reminder is decided when the send is enqueued, not when it runs. A held or queued send can carry a stale "commit it first" line after the journal was committed. The hold notification would also show hands' sentence inside the prompt.
> - `src/hands/playbook.py` `journal_reminder`: it makes a blocking `git` subprocess call (up to `GIT_SHOW_TIMEOUT_S`) and reads the whole inbox via `spool.events()` inside the async `_send` path.
>
> The worktree is removed. Times (UTC): start 01:06, end 01:13.

(The second candidate is hosted finding 9, fixed in 1276251; the first is
should-fix 6.)

**U4 0c6d725** (01:14–01:26)

> Start 01:14 UTC. Commit 0c6d725, U4 `progress` and the README. Verdict: ACCEPT, with no blocker.
>
> 1. **Unit and sections:** the body names mission 23 U4, DESIGN §39 with §38 (`progress`), and REVIEW-22 should-fix 6. It lists all 6 files in `--stat`: README.md, docs/INTEGRATION.md, src/hands/api.py, src/hands/phone.py, tests/test_docs.py, tests/test_phone.py.
> 2. **Test-first holds.** I reverted the 4 non-test files to SHA~1 (all existed there), and both new tests went red:
>    - `test_phone.py::test_progress_reads_the_checkpoint_at_the_repository_root_below_it` failed with `'no checkpoint' == 'checkpoint: ...'` (test_phone.py:1249). It uses a cwd at `repo/sub/deeper`, two levels below the root, and a decoy `meta/CHECKPOINT.md` under the cwd that must not be read.
>    - `test_docs.py::test_the_readme_phone_command_list_names_all_ten_commands` failed with "README's command list omits `progress`" (test_docs.py:657).
>    - No new test stayed green. After the restore, `git status --short` was empty.
> 3. **`./scripts/check` is green:** "4426 passed in 359.84s (0:05:59)", ruff "All checks passed!", exit 0. The script's last line is `echo "check: green"`, but I captured only the exit code, not that line. I also started the gate a second time by mistake (output thrown away), so it ran twice instead of once.
> 4. **Design conformance holds.**
>    - **Checkpoint location:** api.py:1425 `_checkpoint_root` runs `git -C <cwd> rev-parse --show-toplevel` with the existing timeout, and api.py:1450 uses it. That matches §39 ("at the repository root (`git rev-parse --show-toplevel` of the builder's cwd)") and the brief's U4.
>    - **README:** it names all ten commands and says "ten commands". The docs test also pins phone.py's own list to the same ten, in the same order.
>    - **Forbidden files:** DESIGN.md, meta/plan.md and meta/CHECKPOINT.md are untouched. Nothing in the commit body contradicts the disk.
>
> Not proven:
> - The test calls `_checkpoint_line` directly. No phone or daemon test runs `progress` with a nested builder cwd. The call site at api.py:1347 is a plain pass-through, so this is a low risk.
> - As the body itself admits, a git that hangs, a submodule cwd and a linked-worktree cwd are untested.
> - The new docs wording in INTEGRATION.md and phone.py ("at the repository root … show-toplevel") is not pinned by any test.
>
> Should-fix candidates (minor): add an end-to-end `progress` test with a nested cwd, and a docs assertion for the `show-toplevel` wording in INTEGRATION.md. The worktree is removed. End 01:26 UTC.

**U5 59678ee** (01:26–01:33)

> Start 01:26 UTC. Commit 59678ee. **Verdict: acceptable, no blocker, 3 should-fix items.**
>
> 1. **Unit and sections:** this is U5 `hands hosted-review <pr>`. The body claims §39 "The hosted review, read mechanically", §35's hosted second reviewer and docs/QODO-EXTRACTION.md. The body's file list matches `git show --stat` (hosted.py, cli.py, fake_gh.py, 10 fixture pages, test_hosted.py, test_docs.py). No forbidden file was touched (DESIGN.md, meta/plan.md, meta/CHECKPOINT.md).
> 2. **Test-first: proven.** With `rm src/hands/hosted.py` and cli.py taken from SHA~1, all 8 tests in test_hosted.py went red, plus 2 in test_docs.py (client commands; sweep). Restored, `git status --short` empty. Every focus item has a test: first fetch, second fetch after the in-place edit, no comments (exit 3, no meta/), two-page pagination, unseen category, gh failure (exit 1). The second-fetch test checks the diff by id, both updated_at values, the changed lines, added 4004, vanished 4003 and "resolved since 1". Targeted mutations went red for the resolved diff, vanished ids, the open count and pagination.
>    - **Not proven: "verdict from the Code Review comment only".** Dropping the `kind == "issue-comment"` check at hosted.py:189 stays green, as does picking the oldest instead of the newest Code Review comment (hosted.py:235). No test has a decoy review or inline body headed "Code Review", or two Code Review comments.
> 3. **`./scripts/check`: green.** `4434 passed in 341.34s (0:05:41)`, final line `check: green`.
> 4. **Design conformance and claims:** it conforms to §39 and U5. I found nothing in the body that the disk contradicts. Archiving and exiting 3 when there is no Code Review comment is declared design-silent in the body, and it does not break the U5 rule, which only covers "no bot comment yet". One code docstring is contradicted: hosted.py:61 says "nothing was written" on failure, but `archive()` (hosted.py:157-164) creates the directory before writing, so a write error leaves a partial `<k>/` that the next run diffs against.
>
> Should-fix candidates (each one later fixed by 1276251):
> - hosted.py:57 — `_STRUCK` matches a bare `Resolved` substring, so an open finding whose title contains "Resolved" counts as resolved.
> - hosted.py:380-389 — the parsed findings are never checked against the header counts. A Code Review comment whose findings don't match `_FINDING` (line 53) prints "no finding open (it numbers none)" and exits 0, a false clean.
> - hosted.py:156-164 — the archive is not atomic (as in point 4).
>
> End 01:33 UTC. The worktree /tmp/rev23/wt-59678ee is removed.

**U6 dc9698e** (01:33–01:41)

> Start: 01:33 UTC
>
> **dc9698e**, U6 "The protocol and the brief template", is approved. I found no blocker and no should-fix.
>
> 1. **Unit and sections:** The commit body names mission 23 U6. It claims §39 (the revert step, "The hosted review, read mechanically", "The hosted review's findings are fixed in the pull request they belong to"), §35, REVIEW-22 should-fix 8, and H-055. It lists all six files in `git show --stat`, and none of them was deleted.
> 2. **Test-first: passed.**
>    - I reverted the four product files one at a time; all four existed at the parent.
>    - These went red: `test_the_protocol_restores_per_file_and_reads_the_hosted_review_by_command` (all 28 cases), `test_the_protocol_reverts_by_checkout_and_never_says_stash` (2 cases), `test_the_brief_templates_last_unit_reads_and_fixes_the_hosted_review` and `test_the_handbook_section_9_reads_the_hosted_review_by_command`.
>    - `test_the_protocols_revert_and_restore_leave_a_clean_tree_for_add_edit_delete` stayed green. That is expected, because it tests git's behaviour, not a product file.
>    - After restoring, `git status --short` was empty. The focused tests, including both six-of-six kit-check tests, passed (44 passed). So a kit made from the templates passes `kit check` 6 of 6.
> 3. **`./scripts/check`: green.** The pytest summary was `4465 passed in 370.69s (0:06:10)` and the last line was `check: green`.
> 4. **Design conformance: OK.**
>    - **Protocol files:** The two protocol files differ only on lines 48-50 (`<owner>/<repo>` vs `SigorMatt/hands`). Neither contains "stash".
>    - **Revert/restore:** The restore `git rm`s each listed file absent at `<sha>`. It then checks out the other files at `<sha>`, and it stops if `git status --short` is not empty.
>    - **Hosted-review step:** One fresh-context sub-agent runs `hands hosted-review <pr>` and cites docs/QODO-EXTRACTION.md. It takes the verdict from the Code Review comment only and treats exit 3 "no bot comment yet" as the wait. It audits the `## Hosted review` dispositions, and the review commit carries the archive.
>    - **Command:** The command exists at this commit, with `EXIT_NOT_YET = 3` at `src/hands/hosted.py:38`.
>    - **Brief template:** The last unit opens the PR, waits up to ten minutes, runs the command, fixes, pushes, writes the disposition table and returns to `main`, in that order.
>    - **Forbidden files:** DESIGN.md, meta/plan.md and meta/CHECKPOINT.md are untouched, and the disk contradicts no claim in the body.
> - **The `-f` deviation is justified.** I checked it in a scratch repo (git 2.43.0). After the parent checkout staged the deleted file (`A  deleted.py`), plain `git rm -q` refused with "has changes staged in the index… use --cached… or -f" (rc=1). `--cached` left the file untracked, so the tree was still not clean. `git rm -q -f` returned 0 and left the tree clean. Forcing is safe because the file only holds the parent's committed content. The deviation is recorded in the commit body, FINAL-REPORT-23.md lines 197-199, and FINDINGS.md around line 2412.
> - **Not proven:** That reviewers and builders follow the wording, and how the real bot behaves. The commit body says this itself. The hand-off of the reviewer's `<k>` copy from the branch worktree to `main` is a design-silent choice that no test exercises.
>
> The worktree is removed.
>
> End: 01:41 UTC

**U7 2b4df10** (01:41–01:49)

> Start 01:41 UTC.
>
> **Commit:** 2b4df10, U7 (H-051, H-052, HF-002; REVIEW-22 should-fix 10).
>
> 1. **Sections (pass).** The body claims §39 "Rulings on H-051..H-054" plus §31, §32 and §38 "Onboarding". It lists all 10 files in the stat, and none were added or deleted.
> 2. **Test-first (pass, one gap).**
>    - With the 6 product files reverted, 7 tests went red: `test_architect_mode_case[hands handbook --templates-True]`, `test_the_architect_settings_allow_exactly_the_hands_commands_the_guard_allows`, `test_the_architect_reads_under_hands_docs_and_nowhere_else`, `test_the_architect_runs_hands_handbook_and_the_driver_role_does_not`, `test_the_shipped_file_reads_hands_docs_from_the_environment`, `test_hands_handbook_help_names_the_directory_as_it_is` and `test_the_architect_prompt_names_the_installed_handbook_and_templates`. The two new `test_project_add` tests stayed green, as the body says, because H-052's part is tests-only.
>    - I tried each of the three wrong changes the body names in `project.py` and all went red: writing the CLAUDE.md from `docs/ARCHITECT-INSTRUCTION.md` (`project.py:124`) broke both tests; skipping `fill_parameters` (line 278) and printing the instruction before doctor each broke the filled-variant test.
>    - Restore was clean.
>    - **Not proven:** the new rule 2 in `architect/CLAUDE.md` (lines 33-40) is held by no test. Reverting just that file left the guard, handbook, docs, kit and project_add test files green.
> 3. **`./scripts/check` (green).** "4474 passed in 361.44s (0:06:01)", then "check: green".
> 4. **Design conformance (pass).**
>    - The prompt paths come from `docs_root()`, which is the same value `runner.py:1100` exports as HANDS_DOCS.
>    - `..` traversal, a look-alike prefix (`{DOCS}x/...`), and HANDS_DOCS unset or empty are all refused, in tests.
>    - The `hands handbook` help names `$HANDS_DOCS/docs/…`, and FINDINGS now marks H-051, H-052 and HF-002 resolved.
>    - The claim that `project.py` is unchanged checks out on disk. Its last change is f1936b1 (mission 22). It already writes the CLAUDE.md from the role variant (`project.py:124`), fills the Parameters (`project.py:277-278`), prints the dry-run "from" source (`project.py:244`) and prints the instruction after doctor (`project.py:225`).
>    - DESIGN.md, `meta/plan.md` and `meta/CHECKPOINT.md` are untouched. The Read tool is allowed without restriction in `architect/settings.json`.
>
> **Should-fix candidates (minor):**
> - Rule 2's text has no pinning test.
> - The driver role is left out of HANDS_DOCS read access by the builder's interpretation, since §39 does not say which modes get it. The body states this.
> - `docs/INTEGRATION.md`'s architect surface list is not updated; the body admits this.
>
> **Blockers:** none.
>
> End 01:49 UTC.

(The first candidate is should-fix 8. The INTEGRATION architect surface
list names `HANDS_DOCS` at the tip, INTEGRATION.md:1210, after U9 and
1276251.)

**U8 a09b85f** (01:50–01:57)

> Started 01:50 UTC. Commit a09b85f passes all four points, with no blocker. Two should-fix candidates are listed below.
>
> 1. **Unit and sections:** this is mission 23 U8 (`project add` after a failed clone; the role's rulings). The body claims DESIGN §39, §38 "Onboarding" and §31, plus REVIEW-22 should-fix 9 and 11. It lists all 4 files in `--stat`, adds none and deletes none.
> 2. **Test-first:** pass. With `src/hands/project.py` and `architect/CLAUDE.md` reverted to SHA~1, all 5 new tests went red, each for the intended reason:
>    - `test_a_failed_clone_leaves_nothing_and_a_rerun_creates_the_project`
>    - `test_a_failed_second_clone_removes_the_first_and_both_role_directories`
>    - `test_a_failed_clone_keeps_what_was_there_before`
>    - `test_the_clone_puts_double_dash_before_the_url` (the argv had no `--`)
>    - `test_kit.py::test_the_role_escalates_a_ruling_with_a_drafted_owner_file` (rule 8 had no "ruling")
>
>    After the restore, `git status --short` was empty. The tests use a fake `git` on PATH, a local bare repo in tmp, and missing local paths, never a real remote.
> 3. **`./scripts/check`:** green. "All checks passed!" / "4479 passed in 375.01s (0:06:15)" / "check: green".
> 4. **Design conformance:** pass. The commit matches §39 and the brief:
>    - Both clones run `git clone -q -- <url> <path>`.
>    - A failed clone removes config, secret, env, unit, both role directories and kits/, newest first, prints "removed:" with each path, and runs no systemctl. The body states openly the design-silent choice that the unit is never enabled rather than disabled afterwards.
>    - A re-run succeeds, and files that were there before the command survive byte for byte.
>    - Rules 8 and 13 agree on `VERDICT: escalate ruling: <what>` with a draft at `kits/<name>/meta/decisions/<date>-owner.md`, which the human "adopts or rewrites".
>    - DESIGN.md, meta/plan.md and meta/CHECKPOINT.md are untouched. I found no claim in the body that the disk contradicts.
>
> **Not proven (held by no test, each confirmed by a mutation that left `tests/test_project_add.py` green):**
> - **Should-fix candidate (minor):** the dry run's `git clone -- {plan.repo}` text at `src/hands/project.py:300`. Dropping the `--` from that line changes no test result.
> - **Should-fix candidate (minor):** "a failed push-URL step counts as a failed clone" (`project.py:~343-346`). Taking set-url out of the failure condition changes no test result. The body states this as a design choice but nothing pins it.
> - In that push-URL case, the message still says "the clone of <url> failed" (`project.py:~254`). This is cosmetic.
> - The body itself declares as not proven a rollback after a kill or a failed removal, and that it leaves `docs/ARCHITECT-INSTRUCTION.md` and the handbook's ruling round unchanged.
>
> The worktree is removed. Ended 01:57 UTC.

**U9 515b736** (01:57–02:05)

> Start 01:57 UTC. SHA 515b736, U9 Hooks and docs. Verdict: points 1–4 all pass, no blockers.
>
> 1. **Unit and sections: pass.** The body names mission 23 U9 and these §39 subsections: Rulings H-051..H-054, Review 22's should-fix items (the no_background sentence), H-057, H-058/H-059, H-060 (handbook half), the hosted review, and Documentation. The body lists all 6 files in `--stat` (none added or deleted).
> 2. **Test-first: pass.** I reverted the 4 product files (`.claude/settings.json`, `docs/INTEGRATION.md`, `docs/ARCHITECT-HANDBOOK.md`, `docs/PLAYBOOK.md`) and ran the 14 new tests. 13 went red, including `test_no_background.py::test_the_settings_command_runs_the_hook_isolated_from_a_planted_module`, which runs the real settings command with and without `-I` against a planted `json.py`. One stayed green, `test_the_handbook_cites_the_extraction_method_and_the_same_pr_fix_round`, as expected: the body says U6 wrote that text and this commit only pins it. After the restore, `git status --short` was empty.
> 3. **`./scripts/check`: green.** `4493 passed in 372.88s (0:06:12)`, then `check: green`.
> 4. **Design conformance: pass.** Each doc sentence you asked about matches the code:
>    - **Both tables:** the test runs `load_config` and gets the "set in both" refusal.
>    - **status:** it loops over every configured role (`daemon.py:921`).
>    - **Kits:** `driver/settings.json` has 1 hook and `architect/settings.json` has 2, the second being `--write`.
>    - **Restart:** a stop records running jobs as `daemon_stop` orphans and queued jobs stay queued (`daemon.py:480-485`). The resume sends the builder's `resume_line`, the review's prompt to a fresh context, and a phone `answer` as `keep` (`playbook.py:2278-2287`). An orphaned consultation stops (`CONSULT_STOP_STATES`, `playbook.py:192`).
>    - **Refusals:** answered through `_refuse` (`phone.py:439`), including every `go` refusal.
>    - **Lenient ids:** `match_job_id` (`api.py:174`, `MIN_ID_PREFIX=4`) is used by phone approve/deny and laptop approve/deny/cancel.
>
>    No forbidden file was touched (DESIGN.md, meta/plan.md, meta/CHECKPOINT.md).
>
> Not proven by tests:
> - The "next apply and `go` un-pause a clean-review stop" sentence is only checked as text plus the template's `stop` rule.
> - That the start notification reports a consultation's stop is my reading of the notifier hold-and-fold, not tested.
> - The body already says the restart prose is not checked against a live handsd.
>
> Nits, not blockers:
> - DESIGN §39 lists `answer`/`reply` among the lenient-id commands. They carry no id, which `INTEGRATION.md` states correctly. DESIGN is wrong there, so a finding may be worth filing.
> - `INTEGRATION.md` says a malformed command carrying an approve/deny nonce gets an answer. In fact a malformed `approve <nonce>` stays silent, because only the secret is checked on a malformed line (`phone.py:410-414`).
> - The handbook's §18 `status` bullet has an unwrapped long line.
>
> Worktree removed. End 02:05 UTC.

(The first nit is should-fix 1; the second, which I re-read at the tip
(INTEGRATION.md:760-766, phone.py:410-414), is should-fix 7.)

**U10 1276251** (02:05–02:16)

> Start 02:05 UTC. Review of 1276251 (U10, the hosted review's in-design findings on PR #4).
>
> 1. **Unit and sections:** the body names U10 and §39 "The hosted review, read mechanically", "Phone refusals are answered", "Rulings on H-051..H-054" (H-051) and "The consult journal line", plus docs/QODO-EXTRACTION.md. Its file list matches `--stat` exactly (13 files). This fits the brief's U10 ("fix the findings that are within §39 … naming the finding by its title"). PASS.
> 2. **Test-first:** I reverted the product files one at a time. Every one of the seven findings has a test that goes red.
>    - Whole-file reverts: phone.py turns finding 1's test red, api.py finding 11's, bash_guard.py finding 7's (with the shipped-env test and the test_docs pin), cli.py and INTEGRATION.md their help/doc pins.
>    - The whole-file hosted.py revert can't be read cleanly: cli.py uses `hosted_mod.EXIT_UNPARSED`, so every CLI test dies with an AttributeError. I mutated each finding's anchor line instead, and each went red alone: 6 (archive straight into `<k>`), 8 (exit-4 branch off), 9 (bare `Resolved` back in `_STRUCK`), 10 (both not-yet checks off), and the inline case-fold.
>    - Reverting the REVIEW-PROTOCOL.md copies and BUILDER-N-PROMPT.md turns nothing red. They are docs and no test pins them.
>    - The tree was clean after each restore.
> 3. **Gate:** `./scripts/check` is GREEN: "4504 passed in 362.95s (0:06:02)" and "check: green". The 4504 matches the body's count.
> 4. **Conformance:** DESIGN.md, meta/plan.md and meta/CHECKPOINT.md are untouched. Two departures:
>    - **(a) should-fix, a design decision made without a finding:** §39 (DESIGN ~2072) says the read roots "gain `HANDS_DOCS`". bash_guard.py `DOCS_SUBDIRS`/`Reads.__init__` narrows that to `$HANDS_DOCS/docs` and `$HANDS_DOCS/templates`. The reason is sound and the effect is more restrictive: `docs_root()` is the repository root in a source-tree install. But FINDINGS.md at origin/mission-23 has no finding for it. The narrowing is stated only in the commit body and the 94ab38c report. H-051's Status line (FINDINGS.md:2313) still says "read roots gain HANDS_DOCS", which is now stale. CLAUDE.md requires a finding for this.
>    - **(b) still open, as U5 found:** no test pins the verdict to the issue comment alone. Dropping `kind == "issue-comment"` from `_is_code_review` (hosted.py:222) leaves all 16 hosted tests green. So does `max`→`min` in `_code_review` (hosted.py:276), which would pick the oldest of two Code Review comments. No fixture has a review or inline body headed "Code Review", or two Code Review comments.
>    - **(c) holds, with one gap:** `_redact` (phone.py:713) is applied in `_refuse`, so the ambiguous-id error (api.py:196) is covered. Its candidates are real job ids, and the typed id is redacted. Ignore paths log the resolved id or fixed text, never the typed id. Gap (nit): the message quotes the id with `{typed!r}`, and repr doubles a backslash. A secret containing `\` would therefore pass `re.escape(secret)` and be published nearly verbatim. The config only requires the secret to be one word, so this is possible.
>    - **(d) half-proven, should-fix:** exit 4 with nothing parsed is tested. The other half of the claim, header > 0 with every parsed finding resolved, is not. Changing `not open_` to `not current` at hosted.py ~431 leaves every test green.
>    - **Nit:** the "Code Review comment is not there yet" check and its message are duplicated verbatim (hosted.py:364-368 and 369-374).
>
> Not proven: that a slow git doesn't stall the loop (the test proves a worker thread is used, not timing); redaction of a nonce or of a prefix of the secret; the bot's header-reset behaviour beyond the recorded fixtures (the body says the same). No blocker. The worktree is removed. End 02:16 UTC.

(Departures (a), (b), (c) and (d) are should-fix 2, 3, 5 and 4.)
