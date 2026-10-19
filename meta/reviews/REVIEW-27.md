# REVIEW-27 — cold review of mission 27 (the separation follow-up), PR #7

reviewed: 317983b9c7d54528909fc1df7a4508322b821b93

Shape: pull request (BUILDER-27 §Branch). Branch `mission-27`, PR #7 (base
`main`), first review of the branch: base = `git merge-base origin/main
origin/mission-27` = 1b822a5. Commits under review (`git log
1b822a5..origin/mission-27 ^origin/main`):

    317983b report: mission 27 hosted review dispositions, H-077, the PR #7 archive
    3ad66dd playbook: §43's hold reason for its cause only, on every path that publishes it
    94f709c report: mission 27 final report
    38e44ee docs: the operator table follows the code — §19's rows read out of the source by ast
    37bd194 playbook: a playbook change is the owner's — no engine approval of a kit carrying it
    4130616 protocols: report contents, the gate's timeout, the wait rule; the guard's four read-only options
    3383ffe runner: background tasks off where the role's hook allows it (H-074)
    32446f5 daemon: name the owner file on every builder job but an apply (H-073)
    f10c020 tests: the DESIGN copies of §43, H-076's zip-clock race, review 26's consult refusals
    b3e1e76 plan: mission 27 U0 — plan, branch, findings H-074..H-076, the report-25 correction

## Blockers

None.

## Should-fix

1. **The daemon computes §43's hold reason on the event loop** (3ad66dd).
   `_held_reason` (called from `_on_event`, whose docstring says it "must be
   cheap") and `_publish_held` (inside `async start()`) load the job, run
   `kit_apply_problem`, and for an architect hold read the stored zip's
   entries and hash the whole zip, calling `load_playbook` from disk when
   no playbook is loaded yet. The engine's paths for the same reason use
   `asyncio.to_thread`; the daemon's do not. Kit size bounds the cost. Move
   these calls to a worker thread, or record the trade-off in a finding.
   FINAL-REPORT-27's NOT PROVEN does not mention it.
2. **`hands doctor --live` does not build its turn's environment the way a job is built** (3383ffe).
   doctor.py:2104 builds `{**os.environ, **role.spawn_env}` and bypasses
   `runner.job_env`. The live turn therefore carries doctor's own inherited
   `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS` and never gets rule 4's `=1`
   default. A real job does neither (§43 rules 4 and 5). NOT PROVEN discloses
   it. File a finding, or route the live turn through `job_env`.
3. **The §19 reader matches one-word titles too loosely** (38e44ee).
   `tests/test_operator_table.py` checks each piece with a substring
   search over the Notification column. A one-word title ("go", "kit") is
   matched by any row that contains the word, so a new published line with
   such a title and no row of its own leaves the test green. NOT PROVEN
   discloses it. Match a title against the start of a row's title.

## Hosted review

Archive k=4 (this review's fetch; written as `meta/reviews/hosted/PR-7/4/` in the review's worktree, not committed: the prompt for this review allowed committing REVIEW-27.md only). `hands
hosted-review 7` exited 0 on the first run, so there was no wait. The
verdict taken from the Code Review comment (issue-comment 6258210146,
updated 2026-10-19T03:29:23Z): **2 of 4 findings open**. Categories: Bugs 1,
Rule violations 1, Cross-repo conflicts 0, Skill insights 0. Against k=3
the only change is the bot's code links moving from 3ad66dd to 317983b.
After resolving them, the bot renumbered: fetch 4's #3 and #4 are fetch 1's
#4 and #3. The builder's table uses fetch 1's numbers, which are used below.

1. Role kits can rewrite the playbook by changing its case `🐞 Bug` `⛨ Security` — src/hands/spool.py:578-583 (inline review-comment 4309801219 at src/hands/spool.py:583):
   "Spool.stored_kit_playbooks (and kit._owner_warning) recognise only the exact names PLAYBOOK.toml and meta/PLAYBOOK.toml, so an entry such as playbook.toml, Playbook.toml or Meta/PLAYBOOK.toml passes _carries_no_playbook and the engine approves the apply. On a case-insensitive filesystem the apply's unzip -o writes that entry over the real playbook, which the apply then commits. The role can therefore raise its own max_architect_consults, drop a stop rule or change the kickoff without the human seeing it, which is exactly what H-075 was meant to stop."
   → **dismissed for this mission**: §43 names the two paths exactly, so
   widening the match is a design decision. The builder filed it as H-077
   (open, "Decision needed"). Audit: sound. H-077 is in FINDINGS.md, and
   nothing was fixed without a decision. The owner should weigh H-077's
   "low" severity, which rests on hands running on case-sensitive Linux,
   against the bot's Security tag.
2. Reviewers cannot verify the reported run `📘 Rule violation` `✧ Quality` — meta/FINAL-REPORT-27.md:8-11 (inline review-comment 4309801210 at meta/FINAL-REPORT-27.md:12):
   "The new meta/FINAL-REPORT-27.md records only seven-character commit prefixes and summarizes the gate without embedding its raw output. Because the report is the artifact reviewers use to validate the tip and tool claims, they cannot independently match the cited commits, counts, or messages to the run."
   → **dismissed**: each seven-character sha in the report resolves uniquely
   (the sub-agent checked), and this protocol re-runs the gate at every
   commit rather than reading pasted output. Audit: the builder's dismissal
   gives a reason, and the reason is sound.
3. Paused playbook kits lose hold reasons — src/hands/playbook.py:2134-2136 (inline review-comment 4309801214):
   "_owner_hold_reason reaches notifications only through _announce_hold, while defer_hold skips holds filed during a pause and startup republishes held jobs without a reason override. When either path handles a role-filed kit carrying a playbook, the human sees only apply <name>, not the playbook path and ownership reason."
   → **resolved, fixed in 3ad66dd**. Audit: the commit touches the anchor
   file and both paths (the daemon's `_on_event`/`_held_reason` and
   `_publish_held`). The bot marks it resolved. The per-commit sub-agent
   saw the path tests go red with the fix reverted. Should-fix 1 concerns
   how this fix computes the reason.
4. Holds with other causes show the playbook-owner reason — src/hands/playbook.py:2134-2136 (inline review-comment 4309801223):
   "_announce_hold now always passes reason=self._owner_hold_reason(job), so every buttoned hold of a kit that contains a playbook gets §43's "a change of the playbook is the owner's" reason. That includes kits that _escalate_kits is about to deny for a §33 violation, and kits that _kit_bytes_unchanged refused because the hash did not match. In those cases the human sees Approve/Deny buttons with a wrong reason for the hold, and the real cause shows only in a separate stop message."
   → **resolved, fixed in 3ad66dd**. Audit: one function,
   `published_hold_reason`, now decides the reason for its own cause only.
   The §33 and hash-mismatch tests go red with the fix reverted, and the
   bot marks the finding resolved.

## Notes

- Gate at the tip under review (my one run, worktree at 317983b):
  `./scripts/check` → `5056 passed in 478.64s (0:07:58)`, `check: green`,
  `check-exit=0`. Every per-commit run was green as well (below).
- Commits read, not reviewed as units: b3e1e76 (`plan:` U0) does what it
  says: it files H-074..H-076, sets the H-070/H-071/H-073 statuses and adds
  the FINAL-REPORT-25 correction line, and touches only `meta/`. 94f709c and
  317983b (`report:`): `git show --stat` lists only `meta/` files, so no
  forbidden edit.
- NOT PROVEN, read against the sub-agents' findings. The report's items
  match what the sub-agents could not prove: a real builder under the
  default, the old hook doctor-checked on the laptop, a real held role kit,
  phone mode at filing, H-077, the zip clock as the cause of mission 26's
  failures, and the §19 reader's limits. One item is missing: should-fix 1,
  the event-loop cost.
- Observations, not raised:
  - U2's strip helper would also strip a human prompt that itself begins
    with hands' exact sentence. §43 defines the strip by the leading text,
    so this is the design's own consequence.
  - U4 admits the four guard options in normal mode too, because the
    option tables are shared. They are read-only options, and §30 restricts
    characters, not options, so it conflicts with nothing. Only `ls -r`'s
    refusal is pinned in normal mode.
  - U6's exemption check requires only a reason longer than 40 characters.
    All 12 exemptions were judged legitimate.
  - U5's `_owner_hold_reason` read the zip on the event loop; 3ad66dd
    replaced it.
- The review commits this file only, as the prompt for this review asked;
  the k=4 archive is not committed (the protocol would also allow it). Stale worktrees at the start: none.
- Schedule (one sub-agent at a time; one `./scripts/check` at a time inside
  the gate's timeout):
  - hosted-review sub-agent (PR #7): 06:29:58 – 06:30:50
  - f10c020 (U1): 06:31:00 – 06:40:48
  - 32446f5 (U2): 06:40:48 – 06:50:16
  - 3383ffe (U3): 06:50:16 – 07:09:30
  - 4130616 (U4): 07:09:30 – 07:19:24
  - 37bd194 (U5): 07:19:24 – 07:40:13
  - 38e44ee (U6): 07:40:13 – 07:49:36
  - 3ad66dd (U7 hosted fix): 07:49:36 – 07:59:12
  - my gate at the tip: 07:59:12 – 08:07:14

## Per-commit verdicts

**Hosted review (PR #7, k=4):** `hands hosted-review 7` exited 0 at 317983b
and wrote k=4. Verdict: "2 of 4 findings open in the Code Review comment".
Against k=3, only the code links changed (3ad66dd → 317983b). Numbering
trap: the bot swapped #3 and #4 after resolving them; the table uses fetch
1's numbers. No missing rows (4 findings, 4 rows). The fixes for 3 and 4 in
3ad66dd touch the anchor file, and the bot shows both resolved. Dismissal 2
gives a sound reason, and every sha resolves uniquely. Filed finding 1
(H-077) is in FINDINGS.md, open, with "Decision needed", and was correctly
left unfixed. Nothing that needed a decision was fixed silently. NOT
proven: the 3ad66dd tests at the tip (not run by this sub-agent); whether
the bot's "resolved" reflects a re-analysis.

**f10c020 (U1):** 1 claims §43 (wording, intermittent test, review 26
items), §10/§12/§24/§42, H-027/H-034/H-039/H-076 — pass. 2 test-first: the
reverted fixture, docs and FINDINGS turn 4 tests red; each of the body's
three api.py mutations turns its test red; restoring the old H-076
comparison turns both clock cases red — pass. 3 gate: `4839 passed in
423.42s`, `check: green`, `check-exit=0`. 4 conformance: §10 notify rule,
H-034 sentence and pin gone, rule-6 exact equality, three refusal tests,
statuses "resolved by DESIGN v3.26 §43"; file list matches 8 files; no
forbidden file — pass. NOT proven: that the zip clock caused mission 26's
failures; the two leads under load or as uid 0.

**32446f5 (U2):** 1 claims §43 owner file, §39, §41, H-073; body lists 11
files; nothing forbidden — pass. 2 test-first: with the 7 non-test files
reverted (plus stubs so the tests import), 14 new tests are red; restore
clean — pass. 3 gate: `4855 passed in 431.90s`, `check: green`,
`check-exit=0`. 4 conformance: the sentence is word for word; candidates,
the per-file A..HEAD query, oldest first (tie-break disclosed), the apply
exemption through `resumed_from`, journal first, the cap counts both,
`to_thread` at dispatch, one helper `sent_prompt` for every reader, and
`--grep` searches the whole record — pass. NOT proven: phone `go` and the
engine's kickoff end to end; the api.py summary change on its own;
tie-break under clock skew.

**3383ffe (U3):** 1 claims §43 rules 1–5, §21/§23/§34/§36, H-074; 10
files, none added or deleted; nothing forbidden — pass. 2 test-first: with
the revert, test_no_background fails at collection, 21 runner and 18
doctor tests are red, and the wheel test is red with pyproject reverted —
pass. 3 gate: `4937 passed in 449.56s`, `check: green`, `check-exit=0`; the
three files with the variable set: `782 passed in 144.14s`. 4 conformance:
rules 1–5 hold; one function `config.background_tasks` serves both runner
and doctor; WARN never FAIL; the inherited value is dropped — pass. NOT
proven: a real Claude Code honouring the variable; a resume re-decides
through `job_env`, untested. Should-fix: `doctor --live` bypasses `job_env`.

**4130616 (U4):** 1 claims §43 rule 6 and "H-070 and H-071, built",
§30/§42; 12 files; nothing forbidden — pass. 2 test-first: 55 new or
changed tests are red with the 9 files reverted; restore clean — pass. 3
gate: `5008 passed in 437.82s`, `check: green`, `check-exit=0`. 4
conformance: both protocols carry the report contents, the gate's timeout
and the wait rule word for word in all 4 places (placeholder in the
template); the brief keeps ≤12 lines; the guard admits the four options and
refuses the neighbours (selftest 434/434); the allow-list and rule 10 —
pass. They are also admitted in normal mode (shared tables, no conflict);
no normal-mode admit is pinned. NOT proven: that agents follow the wait
rule.

**37bd194 (U5):** 1 claims §43 "A playbook change is the owner's",
§26/§31–§34/§36; 14 files; PLAYBOOK.toml untouched — pass. 2 test-first:
29 cases red with the 8 files reverted; the 3 behaviour-preserving tests
pass, as they should — pass. 3 gate: `5041 passed in 456.43s`, `check:
green`, `check-exit=0`. 4 conformance: the check sits in `_release_kit`
after `kit_apply_problem` and `_kit_bytes_unchanged`; the exact paths; the
gate reason stays `apply <name>`; `publish_hold(reason=)` carries the §43
sentence, also on the paused branch; kit-check WARN; docs and templates —
pass. Gaps fixed later in 3ad66dd: the §43 reason for other causes, and the
daemon's start and paused-filing publishes. NOT proven: a real role
session.

**38e44ee (U6):** 1 claims §43 operator table, §42, review 26 should-fix 2;
2 files; nothing forbidden — pass. 2 test-first: 5 tests red with the
handbook reverted; removing "paused by human" (literal), "<event>: rule <i>
cannot be rendered: <error>" (leading placeholder) or "no rule matches the
verdict" (through a name), or adding `self.stop("zzz brand new reason")`,
each turns it red; the body names these wrong changes — pass. 3 gate:
`5047 passed in 466.14s`, `check: green`, `check-exit=0`. 4 conformance:
receivers as §43 names them; the reading rules; 12 legitimate exemptions;
the three required rows, U5's pinned to route 2 then `go` — pass. NOT
proven: attribute or container paths; api.py `notify --test`. Should-fix:
loose one-word title match; a weak check of the exemption reasons.

**3ad66dd (U7 hosted fix):** 1 claims §43, §34, §36, H-075; 4 files;
nothing forbidden — pass. 2 test-first: 7 tests red with both src files
reverted (paused-before-filing ×3, §33, hash mismatch, start fold, the
operator-table exemption); restore clean — pass. 3 gate: `5056 passed in
465.29s`, `check: green`. 4 conformance: `published_hold_reason` alone
decides the reason, for its own cause only; every publishing path asks it;
nothing is published twice; the §19 row still passes — pass. NOT proven:
phone mode at filing; the event-loop cost of a large zip. Should-fix: the
daemon paths compute the reason synchronously on the event loop.
