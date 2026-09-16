# FINAL-REPORT-16 — the guard's language finished, review 15

VERDICT: mission 16 finished

Brief: meta/BUILDER-16-PROMPT.md. Design: DESIGN v3.15 §32 (with §6, §8, §10,
§12, §30, §31). Review closed: meta/reviews/REVIEW-15.md (blockers 1–4,
should-fix 1–7). Findings resolved: H-030, H-031, H-032, H-033. Filed: H-033
(U0), H-034 (U5, open). Base 31789c6 (`plan: mission 16 kit (DESIGN v3.15)`).

## 1. What changed (sha per unit)

| Unit | Commit | What | Gate |
|---|---|---|---|
| U0 Plan and bookkeeping | 7de7520 | plan, checkpoint; H-033 filed; §32's resolutions appended to H-030, H-031, H-032 with status lines set; FINAL-REPORT-15 §3.1 corrected by a dated block; the red base (5 failures from the kit and U0's own H-030 status line) brought green in tests and docs/INTEGRATION.md, no product code; H-031's equality restored | 3/3, 3126 |
| U1 The guard's language, finished | c7dafd2 | `$`, `{`, `}` anywhere and every unquoted reserved word refused before tokenizing in all three modes; the plain-word rule judges every row's words and values; role-mode reads confined to the clone and `~/.hands/<project>/` (plus `HANDS_KITS` for the architect), the refusal says so; removed: `REFUSED_SEQUENCES`, double-quote `$` handling, `$ { }` from the residual set, `BRACE_EXPANSION` and `residual()`'s brace branch, `SHELL_KEYWORDS` and `command_start` (the `for`-segment skip), the per-row `residual_violation` calls; INTEGRATION states the whole language | 3/3, 3594 |
| U2 Architect mode and `hands kit file <dir>` | 7ce3189 | `zip` and `unzip` rows of no table; `mkdir -p`, `cp -r`, `mv` only, every path under `HANDS_KITS`; `kit file <dir>` builds the zip from a directory under `HANDS_KITS`, checks it against `HANDS_CLONE`, refuses a failing kit with the check's output, sends it to the daemon method `kit_file`, which mints `kit_id`, stores the zip outside `KITS` and files the held apply (`origin: architect`); job records carry `kit_id`; README's `&& cd` setup line fixed; directory kits in the architect docs | 3/3, 3647 |
| U3 Autonomy and origins | f4fde48 | engine approval only for a held apply whose `kit_id` the daemon minted and linked to an architect consultation; `send` refuses `origin: architect` and roles `driver`/`architect` (H-032); the kickoff rule only for such an apply; `next kit <name>` waits for that name's `kit_id` within `[series] kit_wait_s` (default 600); a series rename refused unless `max_architect_consults` is written | 3/3, 3689 |
| U4 Config, doctor, prompt, notifications | 44410ea | `architect = "role"` without `[roles.architect]` refused by `handsd` (exit 1), doctor and `kit check`/`kit file`; doctor's role rows check the push URL, command hooks naming one guard file, bypass mode and broad allow entries, `kits/` under the cwd, the architect-mode self-test; the consult prompt carries the first milestone not marked DONE of the committed roadmap and its path; start-time publishes folded into one notification | 3/3, 3736 |
| U5 Playbook severity | e091d0b | `monitor.task_killed → notify` pinned in PLAYBOOK.toml and both templates (loader and engine); four docs corrected with the reason; H-034 filed (DESIGN §10's example and §24 still say `stop`) | 3/3, 3743 |
| U6 This repository's playbook | 6939524 | `[series] kickoff` names meta/BUILDER-17-PROMPT.md; nothing else; the committed file loads (20 rules); a kit of meta/BUILDER-16-PROMPT.md checked `--repo .` passes 6 of 6, exit 0 | 3/3, 3743 |
| U7 Final report | (this commit) | this file, and the mission's meta bookkeeping (plan, checkpoint, journal) | 3/3, 3743 |

## 2. What the tests prove

- **The language (U1).** Through the shipped file with hook JSON on stdin, in
  normal, driver and architect mode: REVIEW-15's `for`/`${c@P}` probe and its
  `cat`/`ls` variants, `for o in -f; do tail $o /etc/hostname; done`, the
  `wc`/`grep`/`date` variants are refused; the probes of reviews 11–14 are
  refused in both role modes and, except 12 of review 11's role-authority
  probes (sends and decisions the human's own session is meant to run, §28),
  in normal mode; a 10,000-command corpus with a pinned seed (20260917) over
  the reserved words and `$`/brace shapes is refused in all three modes; every
  command line in driver/CLAUDE.md and architect/CLAUDE.md is allowed in its
  mode; REVIEW-15 should-fix 7's reads (`cat ~/.ssh/id_rsa`, `cat
  /proc/self/environ`, `grep -r x /`) are refused in both role modes with the
  confinement message, and a read inside the clone is allowed. Self-test
  370/370 at U1. 486 tests were red against the parent guard.
- **Architect mode (U2).** `unzip -o kits/attack.zip`, `unzip -o
  ./kits/attack.zip`, `unzip kits/attack.zip` and `zip -r kits/m.zip kits/m16`
  exit 2 in all three modes. `kit file` refuses a zip, a file, a path outside
  `HANDS_KITS`, `..`, an escaping symlink, unset or empty `HANDS_KITS`; a
  directory's zip has repository-path entries; a failing kit is refused with
  the check's output and nothing is filed; a passing kit is held with `origin:
  architect` and a `kit_id` in the spool, over a real daemon socket; the daemon
  refuses a client-supplied `kit_id`, a bad name, bad base64 and an escaping
  zip.
- **Autonomy (U3).** Nine kinds of forged architect-origin hold are not
  approved; the reviewer's raw-socket `send` with `origin: architect` is
  refused end to end, and a kit-less held job injected into the spool is not
  approved end to end; consult → `kit_file` → engine approval → `kit applied`
  → kickoff works, including a kit filed after the architect's job ended; a
  `cli` job replying `VERDICT: kit applied deadbee` starts no kickoff; `next
  kit` stops at `kit_wait_s` in six cases including the reviewer's done-aux and
  denied-`bar` probes; m17 → m18 → m17 keeps the count; `hands send --role
  architect` and `--role driver` exit non-zero.
- **Config, doctor, prompt, notifications (U4).** The reviewer's repro
  (committed role + autonomous playbook, config without `[roles.architect]`)
  now makes `handsd` exit 1, doctor fail and `kit check` fail; doctor fails a
  write hook naming another guard file, a `type: prompt` hook, a live push URL,
  `bypassPermissions`, a Bash/Write allow entry and kits outside the cwd; the
  prompt carries one milestone and the roadmap path, and the driver's prompt is
  unchanged; start publishes one notification for a plain start, re-minted
  holds and an orphaned consult. 29 of U4's 47 new cases were red first; the
  rest are coverage.
- **Playbooks (U5, U6).** The three shipped playbooks map `task_killed` to
  `notify` through the loader and the engine (one notification, no pause), a
  failed aux job stops and a failed builder job with no resumes left stops;
  these are coverage, since the kit had already made the change. The kickoff
  pin was red on the value in a worktree at the parent.

## 3. NOT PROVEN

**3.1 The guard against a real session.** No real Claude Code session ran the
hook. That the string Claude Code hands the hook is the string bash runs, and
under which shell options, is still assumed; U1 ran 2,750 guard-allowed
commands under real bash with extglob and found nothing run that the guard did
not allow, which is a sample, not the space. The fuzz corpus and the probe
tables prove the shapes they enumerate. The realpath checks are
time-of-check: a path can change between the guard and the command. In role
mode `hands --project <other>` still reaches another project, and `pgrep -a
-f` prints other processes' command lines, which can carry secrets. The
driver and architect roles stay behind §30's condition: a review that finds
no hole in this language.

**3.2 The architect's kit authority is a same-user boundary.** `kit_file` is
accepted only while an architect consultation is open (or its `next kit`
wait, for that name), and the daemon links the `kit_id` to that job. The daemon
cannot tell the architect's process from another process of the same user
calling the socket during that window, or from one writing the spool
directly. The daemon does not re-run the kit check; the client's check is the
check. No real architect has filed a kit a builder then applied.

**3.3 `next kit`'s wait is in memory.** A daemon restart during the wait
forgets it, and nothing stops the series; the wait is not restart-proof.

**3.4 The budget.** A rename that writes `[limits] max_architect_consults`
resets the count by §32's own rule, and a kit the engine approves can carry
that rename. The rename rule applies in role mode only.

**3.5 Doctor.** The push-URL check reads `git remote get-url --push --all
origin`; `pushInsteadOf` rewrites that `get-url` does not show, and other
remotes, are not judged. The hook checks assume Claude Code matches hook
matchers as whole patterns. No real Claude Code session met these settings.

**3.6 The roadmap milestone.** "Not marked DONE" is `DONE` on the milestone's
first line. On this repository's roadmap that reads M4b ("mission 10 DONE …")
as done although its later missions are not; M4, unmarked, comes first, so the
prompt names M4. Other roadmap shapes are untested.

**3.7 Notifications.** The one-notification start is proven for publishes made
during start; a task the start schedules that publishes after it returns is
not folded. No real ntfy delivery was observed.

**3.8 The example playbook (H-034).** §32 says the example playbook maps
`task_killed` to `notify`; DESIGN §10's example and §24 still say `stop`, and
tests/fixtures/playbook_example.toml and docs/PLAYBOOK.md's closing copy must
equal §10 byte for byte, so they say `stop` too. That half of U5 waits for the
architect's DESIGN edit.

**3.9 The next brief.** meta/BUILDER-17-PROMPT.md does not exist; the architect
ships it. Doctor's `go` row warns about it when the command channel is on; a
phone `go` before it lands would send the builder to a missing file.

## Review items

| Item | Unit | Commit | State |
|---|---|---|---|
| REVIEW-15 blocker 1 — `for` segments unjudged and `${…}` unchecked: the guard ran a program in all three modes; `$o` bypassed the option tables | U1 | c7dafd2 | closed (`$`, braces and reserved words leave the language; probes refused in all three modes; §3.1) |
| REVIEW-15 blocker 2 — architect `unzip` with no `-d` wrote over the guard and its settings | U2 | 7ce3189 | closed (`zip`/`unzip` rows removed; `kit file <dir>`; the three probes refused) |
| REVIEW-15 blocker 3 — the engine approved any held job of origin `architect`, and any socket client could set it | U3 | f4fde48 | closed (daemon-minted `kit_id` linked to a consultation; `send` refuses the origin; same-user boundary, §3.2) |
| REVIEW-15 blocker 4 — `architect = "role"` without `[roles.architect]` not a config error before the engine's first load | U4 | 44410ea | closed (`handsd`, doctor and `kit check` refuse it; the doc claims now have behavioural tests) |
| REVIEW-15 should-fix 1 — the kickoff rule fires on any builder's `kit applied` | U3 | f4fde48 | closed (only for an engine-approved architect apply; the `deadbee` probe starts nothing) |
| REVIEW-15 should-fix 2 — `next kit` accepts any later architect-origin job | U3 | f4fde48 | closed (that name's `kit_id`, `kit_wait_s`; the wait is in memory, §3.3) |
| REVIEW-15 should-fix 3 — the budget resets when the series is renamed | U3 | f4fde48 | closed as §32 words it (rename refused unless the budget is restated; §3.4) |
| REVIEW-15 should-fix 4 — the whole ROADMAP in the prompt | U4 | 44410ea | closed (the next milestone not marked DONE, from the committed file, plus the path; §3.6) |
| REVIEW-15 should-fix 5 — two notifications at start with an orphaned consult; the published-kinds sentence wrong | U4 | 44410ea | closed (folded into one, count bound; sentence corrected; §3.7) |
| REVIEW-15 should-fix 6 — doctor's architect row misses four cases | U4 | 44410ea | closed (all four, plus the push URL in the driver row; §3.5) |
| REVIEW-15 should-fix 7 — role-mode reads reach any path | U1 | c7dafd2 | closed (confined to the clone and the spool, plus `KITS` for the architect; the refusal says so) |

## 4. Acceptance

- `./scripts/check` green on the pushed tip, three consecutive runs: green 3/3
  on the U6 tree 6939524 with this commit's meta files in place (3743 passed;
  202.38s, 198.66s, 199.17s). This commit adds meta files only.
- Every unit commit's body lists every file it touches: checked for 7de7520,
  c7dafd2, 7ce3189, f4fde48, 44410ea, e091d0b and 6939524 against `git show
  --name-only` (each path or its file name appears in the body); U0 is `plan:`.
- The guard refuses `$`, `{`, `}` and every reserved word in all three modes
  (U1's tests and fuzz corpus); no `unzip` row exists (the word appears in
  driver/hooks/bash_guard.py only in comments, refusal text and probe rows).
- `hands kit file` accepts only a directory under `HANDS_KITS` (U2's tests).
- This file exists with NOT PROVEN and the review-items table.
- One deviation from the brief's words, disclosed: U5 could not make DESIGN
  §10's example say `notify` (H-034); U6 ran its three gate runs in a
  temporary worktree with the change committed locally, because the
  root-playbook tests read only the committed file, and pushed the same tree.

## 5. For the architect

- H-034: §10's example rule and §24's sentence still say `stop`; the finding
  carries the replacement rule and what the next builder updates.
- H-027, H-001 and H-009 stay open.
- meta/BUILDER-17-PROMPT.md is named by the playbook's kickoff and does not
  exist yet.
- The review §30 asks for: the driver and architect roles are enabled after a
  review finds no hole in the language U1 built.
