# FINAL-REPORT-18 — review 17, who "needs you" from current state

VERDICT: mission 18 finished

Brief: meta/BUILDER-18-PROMPT.md. Design: DESIGN v3.17 §34 (with §11, §26,
§32, §33). Review closed: meta/reviews/REVIEW-17.md (blocker 1, should-fix
1–7). Backlog: mission 18 item 1 (`hands who`). Findings: H-038 filed (U0) and
resolved (code U1); H-039 filed after U1 (open, the architect's). H-037,
H-034, H-027, H-001, H-009 stay open. Base fc376ab (`plan: mission 18 kit
(DESIGN v3.17)`), green (3935 passed).

Numbering. The brief says "File H-037"; H-037 already existed (mission 17 U8,
the buttons carry no ntfy token), so blocker 1 is H-038 throughout.

## 1. What changed (sha per unit)

| Unit | Commit | What | Gate |
|---|---|---|---|
| U0 Plan and bookkeeping | 23da451 | plan, checkpoint; H-038 filed; FINAL-REPORT-17 §2's "both denied" (and §3.7) corrected by an appended dated block | 3/3, 3935 |
| U1 The start fold | 45da318 | `job.held` never folded: published at once with its buttons, held before or during the start, named by title only in "handsd started"; a stop flushes the start notification and drains pending publishes; `Notifier.cancel_all` removed | 3/3, 3937 |
| U2 The kit record | 88e8830 | `kit.json` records the sha256 of the stored, checked bytes; engine approval re-hashes and refuses a mismatch (`kit.refused` with both hashes); a record without the hash is not approved; `kit_file` serialized per consultation, the second refused "one kit per consultation" before it is stored or checked | 3/3, 3945 |
| U3 Symlinks and doctor | f846965 | guard and doctor walk `HANDS_KITS` with `os.lstat`, an unlistable directory or un-stat-able path refuses; doctor reads `settings.json`, `settings.local.json`, `~/.claude/settings.json`, fails `env` naming `HANDS_*`/`CLAUDE_*` (and `PATH`, `PYTHON*`) and guard hooks with keys beyond `type`/`command`; the self-test runs the guard at the named path, which must be the role directory's, and compares its sha256 with the shipped guard (the wheel now carries it) | 3/3, 4000 |
| U4 The token and who | 2221151 | `ntfy_token` refused at load without an explicit `ntfy_url` or with a public one (`ntfy.sh` or a subdomain), message names the url and not the token; `hands who` says "needs YOU" only when the driver's project is stopped now or has a job held now | 3/3, 4030 |
| U5 This repository's playbook | f159d28 | `[series] kickoff` names meta/BUILDER-19-PROMPT.md; nothing else; loads (20 rules, phone, not autonomous); a kit of meta/BUILDER-18-PROMPT.md checked `--repo .` passes 6 of 6, exit 0 | 3/3, 4030 |
| U6 Final report | (this commit) | this file; H-038 code line and status; H-039 filed; plan, checkpoint, journal | 3/3, 4030 |

## 2. What the tests prove

- **The start fold (U1).** With a real Daemon, the reviewer's probe A (a
  queued builder job `FAKE:sleep 3`, an aux job gated at 0.3 s):
  `test_a_job_held_inside_the_start_fold_window_is_published_at_once_with_its_buttons`
  sees the held note published first, with Approve/Deny actions for that job,
  before "handsd started", which names it by title only; red first (the first
  publish was "handsd started" at 3.13 s). Probe B2 (queued failing aux and
  blocked builder, 0.5 s publish latency, stop at 1.0 s):
  `test_a_stop_inside_the_start_fold_window_delivers_the_start_notification`
  sees "handsd started" delivered with "the pipeline stopped" folded in; red
  first (nothing delivered). A job held before the start is re-published with
  fresh buttons (three adjusted tests, red on the parent).
- **The kit record (U2).** A byte of the stored zip flipped after `check_kit`
  returns: before, approved and applied end to end; now held, with
  `kit.refused` carrying both hashes, whether the engine decides on the hold
  or at the consultation's end. A `kit.json` without a sha256 is not approved.
  Two concurrent `kit_file` calls, during the `next kit` wait and while the
  architect runs: `check_kit` ran once, one kit filed, the other refused; the
  consultation escalates.
- **Symlinks and doctor (U3).** The reviewer's execute-only probe (a link in a
  mode-0111 directory under `kits`) under real bash leaves the guard untouched,
  and doctor's architect row fails; `env` with `HANDS_KITS`/`HANDS_ROLE` in
  each of the three settings layers fails both rows, as do six further env
  names, four bad user-level files and `async`/`timeout` on a guard hook; a
  guard replaced by an exit-0 file fails with both sha256 printed; a guard at
  another absolute path fails, even an exact copy; the shipped driver and
  architect settings pass. All red first except a harmless-env case.
- **The token and who (U4).** A token with no `ntfy_url`, and with seven
  public-url variants in `[notify]` and `[server]`, is refused by handsd,
  handswho, `hands notify --test`, `hands who` and doctor (text and `--json`),
  naming the url, printing no token and sending no request; five self-hosted
  urls load (coverage only). `who`: `job.held`/`stop` events with nothing held
  or stopped now read "informational"; a held job or a stopped pipeline now
  reads "needs YOU"; another project's stop does not change this driver's line.
- **Playbook (U5).** The kickoff pin was red on the value with the old file
  committed; the committed file loads; the kit check passes 6 of 6. A probe
  not committed: the new playbook with a BUILDER-19 brief exits 0, the old
  playbook with that brief exits 1.

## 3. NOT PROVEN

1. **Real ntfy, phone and claude.** No real ntfy server, phone app or Claude
   Code session ran any unit's path: the held notification's buttons, the
   stop's drain, the token refusal against a live broker, `who` against a
   live daemon (its tests use a stand-in state).
2. **The fold's other kinds (H-039).** §34 says the fold holds back only
   heartbeats and `pipeline.resumed`; neither is an ntfy notification here.
   U1 took `job.held` out of §33's fold and kept the rest (e.g. "the pipeline
   stopped" still folds into "handsd started"). A kit apply or an engine hold
   inside the window, and a publish hanging past the 30 s drain, are
   untested; a shutdown can now take up to 30 s longer.
3. **The kit record.** Nothing re-hashes the zip between approval and the
   builder's unzip (§34 names approval only). The marker for a refused second
   kit is in memory and is lost on a daemon restart. Only two concurrent calls
   are tested; the re-check of the consultation after the lock has no test.
4. **Doctor.** Whether Claude Code applies settings `env`, `async` or
   `timeout` to hooks was not run. Managed settings and a user folder moved by
   `CLAUDE_CONFIG_DIR` are not read; env names outside the checked prefixes
   (`LD_PRELOAD`, `BASH_ENV`) pass; hardlinks under `kits` and the race
   between the walk and `cp`/`mv` are not covered; doctor's copy of the walk
   is not pinned equal to the guard's; the execute-only tests skip as root;
   that a built wheel carries `hands/shipped/bash_guard.py` was checked by
   hand, not by a test.
5. **Public brokers.** Only `ntfy.sh` and its subdomains are recognised as
   public; other public brokers, IP addresses or DNS aliases of ntfy.sh are
   not refused. Doctor's `ntfy token` line is unchanged.
6. **U5's committed gate is weak**: the kit carries no playbook, so the new
   kickoff value is compared only by the uncommitted probe, whose brief was
   made by changing 18 to 19 in the kickoff line alone.
   meta/BUILDER-19-PROMPT.md does not exist; the architect ships it.
7. **This mission's gate runs.** The three runs before each unit commit were
   the sub-agents' (U1–U5) and the orchestrator's (U0, U6); no reviewer has
   reproduced them.

## Review items

| Item | Unit | Commit | State |
|---|---|---|---|
| REVIEW-17 blocker 1 — a job held during the start fold window gets no Approve/Deny buttons | U1 | 45da318 | closed (a `job.held` is published at once with its buttons, title only in the start notification; the reviewer's probe is a test asserting the actions; H-038; §3.2) |
| REVIEW-17 should-fix 1 — the kit record does not bind the bytes it checked | U2 | 88e8830 | closed (sha256 in `kit.json`, re-hashed at approval, `kit.refused` with both hashes; byte-flip test; approval-to-unzip gap §3.3) |
| REVIEW-17 should-fix 2 — two concurrent `kit_file` calls: the first kit is approved | U2 | 88e8830 | closed (serialized per consultation, second refused before the check; FINAL-REPORT-17 §2 corrected in U0 23da451; §3.3) |
| REVIEW-17 should-fix 3 — a symlink inside an execute-only directory under `kits/` is invisible | U3 | f846965 | closed (`os.lstat` walk from the root, unlistable refused, guard and doctor; the reviewer's probe under real bash) |
| REVIEW-17 should-fix 4 — doctor passes settings that change how the guard runs | U3 | f846965 | closed (three settings layers; `env` naming `HANDS_*`, `CLAUDE_*`, `PATH`, `PYTHON*` fails; `async`/`timeout` fail; Claude Code's own behaviour not run, §3.4) |
| REVIEW-17 should-fix 5 — doctor's self-test accepts any guard that exits 0, at any path | U3 | f846965 | closed (the role directory's guard only, sha256 compared with the shipped guard, both printed) |
| REVIEW-17 should-fix 6 — a stop inside the fold window drops the start notification | U1 | 45da318 | closed (stop flushes and drains, `cancel_all` removed; the reviewer's timings as a test) |
| REVIEW-17 should-fix 7 — a token with the default `ntfy_url` is silent | U4 | 2221151 | closed (refused at load per §34, not warned as the review suggested; the design wins; §3.5) |

## 4. Acceptance

- `./scripts/check` green on the pushed tip, three consecutive runs: 4030
  passed each (f159d28's tree plus this commit's meta files).
- Every unit commit's body lists every file it touches (checked against `git
  show --name-only` for 23da451 through f159d28); U0 is `plan:`.
- A job held during a start publishes with buttons:
  `tests/test_phone.py::test_a_job_held_inside_the_start_fold_window_is_published_at_once_with_its_buttons`.
- This file exists with NOT PROVEN and the review-items table.

## 5. For the architect

- H-039: confirm U1's reading of §34's fold (everything but `job.held` still
  folds) or name the kinds that must publish at once.
- H-037 is still open (the buttons carry no ntfy token); with U4's refusal a
  token now always implies a self-hosted server.
- U3 went past §34's letter: `PATH`/`PYTHON*` env and hook keys beyond
  `type`/`command` fail the row, and any `CLAUDE_*` name fails, not only
  those the role depends on.
- U1 reverses §31's no-re-send: a job held before a restart is published
  again with fresh buttons, as §34 says.
- H-034 (§10/§24 `stop`), H-027, H-001, H-009 stay open.
- The architect role is enabled after this mission's review (§34).
