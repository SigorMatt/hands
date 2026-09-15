VERDICT: mission 13 finished

# FINAL-REPORT-13 — hands mission 13: close review 12, the sweep, two projects

Brief: meta/BUILDER-13-PROMPT.md. Design: DESIGN v3.12 §29 (with §5, §12,
§13, §26, §28). Reviews closed: meta/reviews/REVIEW-12.md (blockers 1–3,
should-fix 1–9) and REVIEW-11 blockers 1 and 3. Findings: H-023, H-024,
H-025. Base: 723dbeb (`plan: mission 13 kit (DESIGN v3.12)`).

## 1. What changed (sha per unit)

| Unit | Commit | What | Gate |
|---|---|---|---|
| U0 Plan and bookkeeping | b79d908 | plan; H-024 resolved (v3.12 reading); H-025 option (b); H-023 closes with U2; `done` order and precedence table (tests/test_docs.py); FINAL-REPORT-12 corrections | 3/3, 1994 |
| U1 The guard | eccc3a1 | `#` outside quotes refused in both modes; H-024 reading clause by clause; role-mode `git -C` pinned to `HANDS_CLONE`, which handsd sets | 3/3, 2092 |
| U2 The sweep after the reap | ea7f1bc | descent by session id and start time or cgroup scope; mark rule removed; `runner.pipe_timeout_s`; `killed` on every orphan entry | 3/3, 2098 |
| U3 Kit transport and kit check | 126d4ff | host by `ipaddress` or `idna.encode`; kit name quoted; `NAMED_PATH_RULE`; apply exception | 3/3, 2196 |
| U4 Consult edges | 38022f2 | consult stops over a paused pipeline; doctor tests the hook the settings name; daemon-start anchor for `max_consults` | 3/3, 2235 |
| U5 Who grace | 9ca89cf | `[who] grace_s` excludes a just-ended job's transcripts | 3/3, 2272 |
| U6 Two projects on one laptop | 8f79f98 | per-project spool; `hands migrate-spool`; handsd refuses the flat layout; templated units; `hands who` over every project | 3/3, 2283 |
| U7 This repository's playbook | 0a14085 | `[series] kickoff` → BUILDER-14 | 3/3, 2283 |
| U8 Final report | this commit | this file, meta bookkeeping | — |

`meta:` bookkeeping commits between units: c2b78c4, 3ece0a1, 62dbcac,
5efada4, 7797d7e, b3acb94.

## 2. What the tests prove

- **U0.** The doc's `failure_reason` list is compared unsorted with the
  runner's `FAILURE_REASONS`. One row per value checks its position in the list
  and that `_final_state` records it when it and later values hold. Rows pin
  the `killed`, `limited` and terminating-line precedence clauses in order.
  Each of REVIEW-12's three mutations, tried one at a time, turns a row red.
- **U1.**
  - Every REVIEW-12 blocker-1 probe is blocked in both modes, and the refusal
    names the offset.
  - Newly blocked; the parent hook allowed each:
    - normal mode: the three probes, a plain comment and `a#b`;
    - role mode: the two `hands` probes, the same `#` cases and
      `git -C /tmp log`.
  - Each §29 reading clause has an allowed and a refused example.
  - `git -C` must equal `HANDS_CLONE` after `abspath`; unset refuses.
  - handsd sets `HANDS_CLONE` on the driver job for three clone layouts.
  - Every REVIEW-11 probe stays blocked in role mode.
- **U2.**
  - The three §24 orphan tests pass through the session proof: detached,
    holding its pipes, and the cancelled job.
  - A leaderless group in a foreign session that carries the job's mark is
    left alone through `_sweep`, `_kill_group` and `_last_resort`.
  - A session member is killed only if it started before the last
    observation.
  - Job end finishes within `pipe_timeout_s` while a setsid'd orphan holds the
    pipes; the orphan is reported `killed: false`.
- **U3.**
  - The reviewer's five hosts are refused through `_kit` with no fetch.
  - A name host is refused exactly when `idna.encode` refuses it, in a table.
  - Kit names with `$(x)`, a backtick, `;` or `'` are quoted, and the
    daemon's and `kit check`'s prompts stay byte-equal.
  - The path rule has a 42-row table and the apply exception a 16-row one.
  - A kit of BUILDER-13 checked with `--repo .` passes 6 of 6 and exits 0.
- **U4.**
  - Each of the seven consult stop kinds, under four playbook shapes, files one
    `pipeline.stop_suppressed` with the engine's reason and one notification
    while paused; an escalate under a human pause does the same end to end.
  - Doctor fails on a broken hook the settings name while the default hook is
    green, and on a named file that does not exist; four spellings of a real
    hook pass.
  - The reviewer's `max_consults` probe counts 0.
- **U5.** The reviewer's who case, with the daemon idle and down: hidden at 0,
  59 and 60 s after the job ends, shown at 60.001 s. Grace values 0, 10 and 600
  are checked on both sides of the boundary; invalid values are refused at load.
- **U6.**
  - Two projects get disjoint spool paths and sockets.
  - A flat fixture migrates with one `spool.migrated` event and nothing left
    flat; a second run is a no-op; an existing target or a live socket
    refuses.
  - handsd refuses each of the five flat items, exits 1 naming
    `hands migrate-spool`, and serves nothing.
  - `hands who` with two fixture spools shows two roots.
  - `systemd/` holds only the two templated units.
- **U7.** `load_playbook` on the repository gives the BUILDER-14 kickoff; the kickoff
  test was red on the value itself against the committed BUILDER-13 line. A
  kit of `meta/BUILDER-13-PROMPT.md` alone, checked with `--repo .`, passes 6
  of 6 and exits 0.

## 3. NOT PROVEN

1. **Guard (U1).**
   - No real claude session was shown to honour the hook, with or without
     `HANDS_CLONE`.
   - The relative `git -C ./repo` comparison assumes Claude Code runs the hook
     in the role's Bash working directory.
   - Heredoc, `case` and arithmetic parsing are not modelled.
   - The brace, tilde and double-quote rules match bash only on the tabled
     examples. The brace rule is wider than bash (`{a},{b}` counts), and
     `"a\"b"` is now refused.
   - `a#b` and `$#` are refused although bash does not read them as comments,
     because §29 says "anywhere".
2. **Sweep (U2).**
   - A fork inside a real job's last poll interval was produced only with a
     hand-set observation. That residual is left alive by design.
   - This Python has no `os.pidfd_open`, so only the fallback kill (re-check
     start time, then `kill`) ran.
   - Kernels older than 5.3 are untested.
   - Children a proven process forks after the sweep read `/proc` are not
     signalled.
   - Two monitor orphan fakes now linger 0.5 s after forking, and the cancel
     test waits for an observation after the fork. Without that, the fork
     falls in the unprovable interval.
3. **Kit (U3).**
   - The path rule is shown only on its table, this repository's briefs and
     the templates.
   - A missing bare `Makefile`, or `newdir/NOTES` where neither kit nor repo
     has `newdir/`, is not caught.
   - `e.g.` and `github.com` are flagged as missing paths.
   - Excused apply rule, U3's reading: the first rule that matches the literal
     and no vocabulary literal, with every alternative matching the literal. A
     rule that also matches the vocabulary is judged as vocabulary, so the
     catch-all `^VERDICT:` stays.
   - `a_b.com` is now refused.
   - IPv6 zone ids and `a.com:+80` are untested.
   - No real ntfy attachment was fetched.
4. **Consult (U4).**
   - No real claude session was run with a hook at a non-default path.
   - Doctor checks only the first hook that names the guard.
   - A daemon restart mid-mission restarts the `max_consults` count.
   - A driver job queued before a restart and run after it is untested.
   - So is a job created in the same millisecond as the daemon start.
   - The end-to-end paused case depends on a 2 s driver sleep.
   - While paused, no playbook rule fires, not even a matching stop rule.
5. **Who (U5).**
   - Untested: whether a real `claude -p` job's transcript carries a
     `timestamp` in its first 20 lines.
   - Untested: whether Claude Code removes the sessions file at exit.
   - Stated in the docs, untested with a real session: a human session begun
     in the role's directory during the job stays hidden until the grace ends.
6. **Two projects (U6).**
   - The units were not run under a real systemd.
   - `hands who` was not run with two live daemons.
   - An interrupted migration can leave a partial move, because items move one
     at a time.
   - A project named `jobs` or `roles` would look like the flat layout.
   - An old daemon on a socket outside `~/.hands` that no config names is not
     detected by the migration.
   - The driver guard does not name `migrate-spool`; role mode refuses it as
     an unlisted subcommand.
7. **Playbook (U7).** `meta/BUILDER-14-PROMPT.md` does not exist yet, and nothing
   checks that the kickoff names a brief that exists. The acceptance form
   does not compare the repository's own kickoff. No new routing test.

## Review items

| Item | Unit | Commit | State |
|---|---|---|---|
| REVIEW-12 blocker 1 — `#` comment hides a command | U1 | eccc3a1 | closed |
| REVIEW-12 blocker 2 — IDNA-invalid hosts fetched | U3 | 126d4ff | closed |
| REVIEW-12 blocker 3 — sweep kills on the mark | U0 (H-025 b), U2 | b79d908, ea7f1bc | closed (residual: a fork in the last poll interval, §3.2) |
| REVIEW-12 should-fix 1 — kit check misses named paths | U3 | 126d4ff | closed (limits §3.3) |
| REVIEW-12 should-fix 2 — `git -C` not pinned | U1 | eccc3a1 | closed |
| REVIEW-12 should-fix 3 — paused pipeline swallows consult stops | U4 | 38022f2 | closed |
| REVIEW-12 should-fix 4 — doctor checks another hook file | U4 | 38022f2 | closed |
| REVIEW-12 should-fix 5 — `max_consults` after a renamed kickoff | U4 | 38022f2 | closed (a restart re-anchors, §3.4) |
| REVIEW-12 should-fix 6 — kit name unquoted | U3 | 126d4ff | closed |
| REVIEW-12 should-fix 7 — apply exception narrower than §28 | U3 | 126d4ff | closed (reading §3.3) |
| REVIEW-12 should-fix 8 — `done` order and precedence | U0 | b79d908 | closed (cancel vs limit unpinned) |
| REVIEW-12 should-fix 9 — who shows a just-ended job | U5 | 9ca89cf | closed (limits §3.5) |
| REVIEW-11 blocker 1 — guard bypass | U1 | eccc3a1 | closed (the comment hole) |
| REVIEW-11 blocker 3 — sweep on the mark | U2 | ea7f1bc | closed; H-023 resolved |

## 4. Acceptance

- `./scripts/check` green on the pushed tip, three consecutive runs:
  green 3/3 on the U8 tree over b3acb94 (2283 passed; 155.47s, 161.27s,
  152.21s). The U8 commit adds meta files only.
- Every unit commit's body lists every file it touches, and U0 is `plan:`.
  Checked against `git show --stat` for b79d908, eccc3a1, ea7f1bc, 126d4ff,
  38022f2, 9ca89cf, 8f79f98 and 0a14085.
- `tests/test_bash_guard.py` carries every review 12 blocker-1 probe, each
  asserted blocked in both modes (U1).
- `systemd/` contains only `handsd@.service` and `handswho@.service` (U6).
- This file exists with NOT PROVEN and the review-items table.

## 5. For the architect

1. **Readings to confirm.**
   - U1: `#` is refused anywhere outside quotes, including `a#b` and `$#`.
   - U2: the `HANDS_JOB` mark is neither required nor sufficient; a marked
     process that isn't proven is reported `killed: false`.
   - U3: which `builder.done` rule is the excused apply rule, and
     `NAMED_PATH_RULE`.
   - U4: no playbook rule fires over a pause, and the notification title.
   - U5: the transcript time-window mechanism.
   - U6: the name `spool.migrated`, what moves, and who's discovery from
     `~/.hands/*.toml`.
2. **BUILDER-14.** `PLAYBOOK.toml` names `meta/BUILDER-14-PROMPT.md`, which
   the architect's next kit must ship.
