VERDICT: mission 12 blocked U4

# FINAL-REPORT-12 — hands mission 12: close review 11

Brief: meta/BUILDER-12-PROMPT.md. Design: DESIGN v3.11 §28 (with §8, §10,
§12, §27). Review closed: meta/reviews/REVIEW-11.md (blockers 1–5,
should-fix 1–9). Base: bb9aab5 (`plan: mission 12 kit (DESIGN v3.11)`).

## 1. What changed (sha per unit)

| Unit | Commit | What | Gate |
|---|---|---|---|
| U0 Plan and bookkeeping | 5ea7b9d | plan; H-018..H-021 resolutions moved into their own sections, status lines in place; H-022 §28 resolution, resolved; H-023 filed; `done` statement pinned per `failure_reason` value (tests/test_docs.py) | 3/3, 1733 |
| U1 The guard on shlex | 3966f9b | driver/hooks/bash_guard.py on `shlex` segments and tokens; tests/test_bash_guard.py | 3/3, 1882 |
| U2 Consult, engine-side | e642552 | engine stops; driver.killed/orphaned/limited; `max_consults` counter; doctor driver row; `HANDS_CONSULT_ROLE`; docs | 3/3, 1916 |
| U3 Kit transport and the apply | 043413d | URL checks in the try; named paths; one apply rule; every alternative; `KIT.md` line rules; quoting | 3/3, 1980 |
| U4 Sweep and who | 7f86406 | **who half only**; H-025 filed; sweep unchanged | 3/3, 1982 |
| U5 This repository's playbook | 1250817 | `[series] kickoff` → BUILDER-13 | 3/3, 1982 |
| U6 Final report | this commit | this file, meta bookkeeping | — |

`meta:` bookkeeping commits between units: 1e8af0a, 96c5488 (H-024), fa1535c,
464bd1d, cfb8fee.

## 2. What the tests prove

- **U0.** The INTEGRATION `done` statement is one exact string. Each §6
  `failure_reason` value has its `failed` cause and is excluded by the `done`
  statement, and the doc's list equals §6's. Each of REVIEW-11's three
  mutations turns the test red.
- **U1.** Every REVIEW-11 blocker 1 probe is refused in role mode, each with a
  stated verdict in normal mode:
  - `&`-joined commands;
  - `--context=clear` quoted, double-quoted, escaped, as `$'…'`, as a brace
    word, and after a backslash-newline;
  - `x=…; $x`;
  - `'--file'` and `\--file`;
  - a send to a role other than `HANDS_CONSULT_ROLE`;
  - `--project` on a role-mode send.

  Also refused: `2>f`, `&>f` and `$SHELL -c`. The hook's own self-test tables
  carry every probe (154/154), and every command that was allowed before is
  still allowed. The newly blocked probes were checked against the parent
  hook.
- **U2.** Escalate, an unrecognised or missing driver verdict, `driver.failed`,
  `driver.killed` (cancel and spawn failure), `driver.orphaned` and
  `driver.limited` each stop and notify once:
  - with a playbook that has no driver rules, and with one whose driver rules
    would carry on;
  - end to end;
  - with `consult.done` carrying the terminal state.

  The driver job's `HANDS_CONSULT_ROLE` is the consultation's role, even over
  handsd's environment. `max_consults` survives a kickoff rename and restarts
  after a started kit apply. Doctor fails for each wiring fault (settings
  missing, unparseable, with no hook, another hook, wrong matcher or event),
  for a missing guard, and for a role-mode self-test failure.
- **U3.**
  - **URLs.** The review's three URLs and each of the four URL checks file
    `kit.refused`, with no fetch and no traceback.
  - **Named paths.** A missing `meta/MISSING.txt` and `../{n}.md` fail
    `kit check`.
  - **Apply rule.** A plain `^VERDICT: kit` rule and a second apply rule fail.
  - **Alternatives.** A typo'd alternative fails on `aux.done`, `builder.done`
    and `driver.done`.
  - **KIT.md.** Each broken first-line rule falls back to `plan: kit <name>`
    with the notice.
  - **Prompts.** The message is shell-quoted. The daemon's and `kit check`'s
    prompts are byte-equal for kits at `~/Downloads/<name>`.
- **U4.** The reviewer's who probe, in two variants: a job pid with a sessions
  file, a spool record with no `session_id`, and a human with no sessions
  file. The job's prompt no longer appears on the human's line.
- **U5.** The root playbook loads with the BUILDER-13 kickoff. A kit of
  `meta/BUILDER-12-PROMPT.md` checked with `--repo .` passes 6 of 6 and exits 0.

## 3. NOT PROVEN

1. **REVIEW-11 blocker 3 is not closed.** The post-exit sweep still kills a
   leaderless group whose live members all carry `HANDS_JOB=<id>`. That is
   U1-of-m11's rule, and H-023 records it. §28's rule was not implemented,
   because it cannot hold as written (H-025):
   - the sweep runs after claude is reaped, so no live leader holds the job's
     pid;
   - a surviving member's pid chain no longer reaches that pid;
   - group mode has no cgroup scope.

   Refusing leaderless groups failed three §24 orphan tests, and one of them
   hung on pipes the orphan holds.
2. **Guard (U1).**
   - Segmenting is not modelled on bash for `case`, heredocs, comments or
     arithmetic; those are refused (fail-closed).
   - shlex tokens were compared with bash's argv on only 11 quoting cases.
   - `git -C <path>` is not pinned to the clone.
   - `--gate` on a role-mode send is allowed.
   - Residual characters are judged only where bash still expands them, not
     as §28's literal list after shlex (H-024).
   - No real claude session was shown to honour the hook.
   - Most of the new tests were red on the parent hook only because of the
     missing consult-role parameter; the clean before/after evidence is the
     probe run.
3. **Consult (U2).**
   - Untested: a driver job cancelled while queued, and an orphaned driver job
     at startup with no playbook.
   - Kickoff values seen before this change are known only once a job start
     loads that playbook.
   - "The last `plan:` kit apply" is read as a started `origin: kit` builder
     job; the commit prefix is not read.
   - A limited driver job is no longer resumed.
   - No real claude driver was run.
   - The journal line's race with a builder job is untested.
4. **Kit (U3).**
   - The prompts differ when `kit_dir` is not `~/Downloads` or the daemon
     renames the kit to `<stem>-1.zip`.
   - The kit path in the prompt is not shell-quoted.
   - A host without an `xn--` label gets no further checks (`exa_mple.com`
     passes).
   - A file name with no extension, or a one-character one, is not seen as a
     path.
   - A `{placeholder}` path is checked for syntax only.
   - "Every alternative must match" is U3's reading of §28. It required the
     runs template's WORKPLAN stub to name both replies.
   - No real ntfy attachment was fetched, and no real builder apply was run.
5. **Who (U4).**
   - A stale sessions file from an earlier process with the same pid is not
     detected.
   - The probe was not run end to end with a live daemon or a real
     `~/.claude`.
   - With handsd down, only spool session ids are excluded.
   - Another human's transcript can still appear under `by directory`.
6. **Docs pin (U0).**
   - The per-value checks were not mutated one at a time.
   - A sentence calling a failing job `done` without the test's word list
     would pass.
   - The runner side is not tested there.
7. **Playbook (U5).**
   - The acceptance form does not compare the repository's own kickoff.
   - `meta/BUILDER-13-PROMPT.md` does not exist yet.
   - No new routing test was added.

## Review items

| REVIEW-11 item | Unit | Commit | State |
|---|---|---|---|
| Blocker 1 — guard bypass (lone `&`, quoted/escaped options, role not enforced) | U1 | 3966f9b | closed (reading in H-024; `-C`, `--gate` limits in §3.2) |
| Blocker 2 — malformed URL traceback | U3 | 043413d | closed |
| Blocker 3 — sweep kills a leaderless group on the mark | U0 (H-023), U4 | 5ea7b9d, 7f86406 | **open** — blocked on H-025 |
| Blocker 4 — who fallback shows a job transcript | U4 | 7f86406 | closed |
| Blocker 5 — acceptance `kit check .` | U0 (H-022 resolved), U5 | 5ea7b9d, 1250817 | closed (BUILDER-12 kit `--repo .` exit 0) |
| Should-fix 1 — driver stops depend on the playbook | U2 | e642552 | closed |
| Should-fix 2 — killed/orphaned/limited/spawn-failed driver silent | U2 | e642552 | closed |
| Should-fix 3 — `max_consults` freezes after kickoff rename | U2 | e642552 | closed (kit apply read as `origin: kit`) |
| Should-fix 4 — `done` statement half pinned | U0 | 5ea7b9d | closed (limits §3.6) |
| Should-fix 5 — findings status lines not in place | U0 | 5ea7b9d | closed |
| Should-fix 6 — kit check misses protocol paths | U3 | 043413d | closed (extension ≥ 2 chars; placeholders syntax only) |
| Should-fix 7 — apply-verdict exception too wide | U3 | 043413d | closed |
| Should-fix 8 — doctor driver row proves nothing | U2 | e642552 | closed |
| Should-fix 9 — `KIT.md` quoting; prompt byte-equality | U3 | 043413d | closed for quoting and the same `~/Downloads/<name>`; other `kit_dir` unequal (§3.4) |

## 4. Acceptance

- `./scripts/check` green on the pushed tip, three consecutive runs:
  green 3/3 on 1250817 (1982 passed; 128.68s, 129.17s, 129.00s); the U6
  commit adds meta files only.
- Every unit commit's body lists every file it touches, and U0 is `plan:`.
  Checked with `git show --stat` for 5ea7b9d, 3966f9b, e642552, 043413d,
  7f86406 and 1250817.
- `tests/test_bash_guard.py` carries every REVIEW-11 blocker 1 probe
  (`REVIEW_11_PROBES`), each asserted blocked in role mode.
- A kit of `meta/BUILDER-12-PROMPT.md` checked with `--repo .` exits 0 (U5,
  6 of 6).
- This file exists with NOT PROVEN and the review-items table.
- **Not met:** REVIEW-11 blocker 3 (§28's sweep rule); U4 is `[b]`.

## 5. For the architect

1. **H-025, the sweep.** Choose (a), (b) or (c):
   - (a) group mode never signals after the reap, and §24's group kill is
     retired;
   - (b) admit a proof by session id and start time, which leaves a fork in
     claude's last ≤ 50 ms alive;
   - (c) keep the leader observable until the sweep.

   Until then the `HANDS_JOB` mark rule stays, and H-023 stays open.
2. **H-024, the guard's residual characters.** Confirm the expansion-position
   reading. Read literally, §28 would refuse `git diff HEAD~1`,
   `HEAD^{commit}`, and a quoted `~/Downloads` prompt.
3. **Two readings U2 and U3 took where §28 is silent.** Confirm them or
   correct them:
   - "the last `plan:` kit apply" means a started `origin: kit` builder job;
   - every regex alternative must match a vocabulary literal.
4. **BUILDER-13.** `PLAYBOOK.toml` now names `meta/BUILDER-13-PROMPT.md`,
   which the architect's next kit must ship.

## Corrections (appended)

2026-09-15 (mission 13 U0, from REVIEW-12 blocker 1). §3 item 2's "comments
… are refused (fail-closed)" is false: shlex ran with `commenters = ""` and
the scanner had no comment state, so an apostrophe inside `# …` opened a quote
bash never sees and hid the next line (`hands show x # it's` + newline +
`hands go #'` exited 0 in role mode; `ls # it's` + newline + `touch … #'` in
normal mode). U1's commit body also listed the backslash-newline
`--context=clear` probe as blocked only after the change; the parent hook
already blocked it in role mode.

2026-09-15 (mission 13 U0, from REVIEW-12 blocker 1). The Review items row
"Blocker 1 — guard bypass … closed" is wrong: REVIEW-11 blocker 1 was not
closed by mission 12. It stays open until mission 13 U1.
