# FINAL-REPORT-25 — mission 25: closer for review 24

VERDICT: mission 25 finished pr=5

Source: meta/BUILDER-25-PROMPT.md, DESIGN v3.24 §41 (with §39, §40),
meta/reviews/REVIEW-24.md, docs/HARNESS-PROBE.md. Branch `mission-24`
(PR #5, still open); main 20aac9f merged in first (cc2a9e5), so `main` is
an ancestor of the branch. Gate: `./scripts/check` green three consecutive
runs before every commit (4659 tests at the tip).

## 1. What changed (sha per unit)

| Unit | sha | What |
|---|---|---|
| U0 Plan and branch | 4523e8a | `plan:` — main merged; plan, checkpoint; H-062 note (session half pinned by U3) |
| U1 The capture script | 11cd19c | `find` and the python3 record read go through the path that writes `(failed: timed out after <n>s: …)`; the 4000-byte cut moved inside the redactor, after redaction; docs/OPERATIONS.md capture section |
| U2 The staged kit | 2f9e219 | `staged_path` refuses a bad name as `KitError`; `read_staged` opens `O_NOFOLLOW \| O_NONBLOCK` and `fstat`s before reading; `Api.kit_apply` removes the refused `.part` in a `finally` |
| U3 Three pins | f53ec39 | tests only — monitor.py, api.py and runner.py already behaved as §41 rules |
| U4 The warning and the stale worktree | f0eb0d0 | stale defined in both protocols and handbook §7; kit.py unchanged (the warning already printed unconditionally), pinned |
| U5 The probe record | 4f46bda | Codex VERDICT `partial: printed while the task failed` + footnote; "verbatim except where marked `…`"; OpenCode/dsh re-checked; one Codex approval row under Gaps |
| U6 Final report | (this commit) | this file, the `## Hosted review` table, archive meta/reviews/hosted/PR-5/4..5 |

## 2. What the tests prove

- A `find` that hangs (ignoring SIGTERM) and a python3 record read that
  hangs each write the timeout line and neither "(no job record under …)"
  nor "(no record, or it names no transcript)"; removing `-k 5`, unbounding
  `find` or the record read, or calling `find` outside the timeout path
  each turns a test red (U1).
- A secret and a key straddling byte 4000 of a line leave no prefix in the
  output and the line is still cut; a URL-encoded secret is redacted; a
  password present only in `~/.hands/ntfy.password` is redacted (U1).
- Through a raw socket client (not the CLI), a staged name with `..`, a
  symlink, a FIFO, a directory and a missing name each come back as a
  hands refusal with a reason, never an internal error; the FIFO test has a
  10 s guard and goes red, without hanging, when `O_NONBLOCK` is dropped;
  dropping `O_NOFOLLOW` or disabling `is_staged_name` turns a test red; the
  daemon removes a `.part` it refuses for a bad kit name, a size over
  `kit_max_mb` and a failing check (U2).
- Two sessions reporting the same task id each raise `task_killed` once
  (red with `key = ("", task_id)`); the 1025th remembered kill evicts the
  oldest (U3).
- An ambiguous-prefix refusal whose typed text and secret contain a
  backslash publishes and logs no part of the secret (red with
  `{typed!r}`) (U3).
- A prompt exactly at the size cap with a dirty `meta/journal.md` is
  refused with the cap's reason; with a clean journal it is sent (red when
  only `job.prompt` is counted) (U3).
- The kit-check WARN for a done rule without its orphaned rule prints, and
  is listed by `--json`, when the `playbook` line fails (red under `… and
  playbook_check.ok` for the no-kickoff case) (U4).
- Both protocols define stale in their opening paragraph with the opening
  `git worktree remove --force <path>`, and the closing paragraph carries
  its `--force` and `git worktree prune`; deleting any of them, or the
  definition, turns a test red in each file; the two files still differ
  only in the project's names; handbook §7 carries the definition (U4).

## 3. NOT PROVEN

- No real usage-limit stop has been captured; the capture script is proven
  only against fakes. Redactor gaps REVIEW-24 lists remain untested:
  double JSON escaping, lowercase percent-encoding, JSON `\/`, a secret
  split across lines (U1).
- After a failed `find`, the capture stops at the job record section, so
  the inbox tail is not captured then (a design-silent choice, U1).
- The `.part` removal on the no-builder refusal path, a hardlink, a device
  node and a concurrent `place_kit` temp file as the staged name (U2).
- That a real claude ever reports one task id in two sessions; the task
  memory across a daemon restart (it starts empty) (U3).
- The kickoff-differs case of the U4 warning test did not go red under the
  `playbook_check.ok` mutation; only the no-kickoff case pins it (U4).
  Correction 2026-10-18 (mission 27 U0, review 25 should-fix 1): REVIEW-25
  found that both parametrized cases, kickoff differs and no kickoff, went
  red under the `playbook_check.ok` mutation at src/hands/kit.py:1352; both
  cases pin it.
- How a reviewer tells a concurrent or human-made worktree apart, or
  learns the aux job's start; the protocol states the rule only (U4).
- docs/HARNESS-PROBE.md's internal consistency is checked by reading, no
  test; what a Codex approval event looks like in `--json` (no confining
  sandbox starts on this machine without a host change); every OpenCode
  and dsh row needing a live model call (U5). `grep -c redacted
  docs/HARNESS-PROBE.md` = 3.
- U5's three gate runs ran in one foreground call, not three (each green,
  4659).

## 4. Deviations

- U3 and U4 changed no product code: the code already did what §41 rules,
  and the review items were unpinned behaviour; each mutation was made by
  editing and seen red.
- U3's ambiguous-prefix test plants two job record files named after the
  secret plus a suffix, because real job ids never contain a backslash.

## Review items

| REVIEW-24 item | Unit | Disposition |
|---|---|---|
| Blocker 1 — `find` and the python3 record read time out with no timeout line, then write a false "no record" line; `-k 5` and those timeouts unpinned | U1 | fixed in 11cd19c |
| Should-fix 1 — cut before redaction lets a straddling secret's prefix through; URL-encoded and by-value forms unpinned | U1 | fixed in 11cd19c |
| Should-fix 2 — staged-name checks unpinned; FIFO blocks, directory is an internal error, refused `.part` left | U2 | fixed in 2f9e219 |
| Should-fix 3 — Codex VERDICT cell `yes`; "verbatim" overclaimed | U5 | fixed in 4f46bda |
| Should-fix 4 — WARN with a failing `playbook` line unpinned | U4 | fixed in f0eb0d0 (test only) |
| Should-fix 5 — stale undefined; opening remove and closing prune unpinned | U4 | fixed in f0eb0d0 |
| Should-fix 6 — `task_killed` session half and eviction unpinned | U3 | fixed in f53ec39 (test only) |
| Should-fix 7 — ambiguous reason's `str` quoting unpinned | U3 | fixed in f53ec39 (test only) |
| Should-fix 8 — journal sentence's share of the cap unpinned | U3 | fixed in f53ec39 (test only) |

## Hosted review

PR #5, `qodo-code-review[bot]`, read with `hands hosted-review 5` after
U5's push. The bot edited its Code Review issue comment 6229613578 in
place twice during the mission: fetch 4 (updated 2026-10-17T14:28:30Z,
links at f0eb0d0) and fetch 5 (updated 2026-10-17T14:51:09Z, links at the
tip 4f46bda). Header at fetch 5: Bugs 0, Rule violations 1, Cross-repo
conflicts 0, Skill insights 0; verdict "1 of 9 findings open". Fetch 5 was
fetched three times; the two byte-identical repeats were removed, so the
archive is meta/reviews/hosted/PR-5/4..5. No new finding was raised; no
fix was needed. Numbers are the current comment's.

| # | Finding (title as the bot wrote it) | Disposition |
|---|---|---|
| 1 | Discotrade misses journal reminders | unchanged since mission 24: dismissed (now struck `✓ Resolved` by the bot) |
| 2 | Doctor fails on unreadable worktree data | unchanged since mission 24: fixed in 9b351a8 |
| 3 | A restarted kickoff no longer resets the consult count | unchanged since mission 24: fixed in b940d6d |
| 4 | Old spool state is skipped after migration | unchanged since mission 24: fixed in 9b351a8 |
| 5 | Sub-agents alter protected metadata | unchanged since mission 24: dismissed — and again for mission 25: meta/plan.md and meta/CHECKPOINT.md were written by the orchestrator in the `plan:` commit 4523e8a, which the brief makes their author; no sub-agent commit (11cd19c, 2f9e219, f53ec39, f0eb0d0, 4f46bda) touches either, per each commit's file list |
| 6 | Quota capture can abort and leave an empty file | unchanged since mission 24: fixed in 9b351a8 |
| 7 | Restored held jobs block the kickoff step | unchanged since mission 24: fixed in 9b351a8 |
| 8 | Kits over about 9.4 MiB can't be applied from the laptop | unchanged since mission 24: fixed in b940d6d |
| 9 | Quota capture can hang indefinitely | unchanged since mission 24: fixed in 9b351a8 |
