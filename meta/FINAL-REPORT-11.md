VERDICT: mission 11 blocked U6

# FINAL-REPORT-11 — hands mission 11 (review 10, the apply from the kit, the driver role)

Brief: meta/BUILDER-11-PROMPT.md. Design: DESIGN v3.10 §27 (with §6, §8, §10,
§11, §26). Base: 0fef436 (`plan: mission 11 kit (DESIGN v3.10)`).

The mission is blocked on one acceptance line only: `hands kit check .` does
not exit 0 on this repository (H-022). Every unit's code is committed and
pushed, and `./scripts/check` is green.

## 1. What changed (sha per unit)

| Unit | Commit | Tests after | What |
|---|---|---|---|
| U0 | e8daca8 | 1550 | `plan:`: plan, checkpoint; H-018..H-021 v3.10 resolutions appended; REVIEW-10 SF7 docs test |
| U1 | efe4d56 | 1573 | REVIEW-10 SF1, SF3, SF4, SF5, SF6: `go` on a held builder job, the sweep, kit check verdicts and paths, malformed URL |
| U2 | 525dc66 | 1588 | `hands who` through `~/.claude/sessions/<pid>.json` (H-020; REVIEW-10 blocker 1) |
| U3 | d4bea98 | 1613 | a kit from the phone files its apply as a held builder job, `origin: kit` |
| U4 | d491f6b | 1699 | `[roles.driver]`, the guard's role mode, `driver/CLAUDE.md` "As a role", doctor row |
| U5 | c1d8ed5 | 1717 | `then = "consult"`, `driver.done`/`driver.failed`, `[limits] max_consults`, inbox and journal |
| U6 | 089e72f | 1732 | `PLAYBOOK.toml`: kickoff BUILDER-12, consult rules; INTEGRATION `[roles.driver]`; H-022 filed |
| U7 | (this commit) | 1732 | this report |

Each `meta: Un done; checkpoint Un+1` commit carries only meta/plan.md,
meta/CHECKPOINT.md and meta/journal.md. Each unit commit's body names every
file it changes; the orchestrator checked this for every unit (`git show
--name-only` against the body).

## 2. What the tests prove

- **U0.** `docs/INTEGRATION.md` contains §6's `error` subtype phrases (`error`
  subtype fails, `error_max_turns` whatever `is_error`, `done` needs `success`
  with `num_turns`), and DESIGN §6 contains `error_result`. The test is red with
  the doc at cbb8fc8^.
- **U1.**
  - `go` is refused while the builder has a held job, and the refusal names it.
    A job enqueued during a patched playbook load also blocks it.
  - The sweep and the last resort leave alone a stranger's group whose leader
    is gone. The same group is still killed when its members carry the job's
    `HANDS_JOB=<id>` mark.
  - kit check fails the review's typo probe `VERDICT: (kit applied|misison \d+
    finished)`, and it checks `aux.done` rules against the protocol's `VERDICT:
    review …` line.
  - kit check refuses `.GIT` in any case, duplicate zip entries, NUL in a name,
    entries over 16 MiB each or 64 MiB in total, and `../`, `~/`, absolute or
    `..` send paths.
  - A malformed attachment URL is refused with no fetch and no traceback. It
    files `kit.refused`, and the URL is in no log, publish or spool file.
- **U2.**
  - With two transcripts in one directory and two sessions files, each pid gets
    its own transcript.
  - A hands job in the human's cwd shows nothing under the human's session,
    with and without the human's sessions file. Without the file the line says
    `transcript: by directory`.
  - No `.key` file is opened and the sessions directory is never listed
    (checked by recording opens and listings).
- **U3.** The apply prompt is byte-equal between `kit check` and the daemon,
  with and without `KIT.md`. The job is held, role builder, `origin: kit`, gate
  `apply <stem>`, with buttons, and nothing runs before approve. Replaced vs
  added is computed against a fixture cwd. `..`, absolute, `.git`, duplicate,
  symlink-escape and not-a-zip kits give `kit.refused` and no job. A `kit`
  origin job un-pauses the pipeline when it starts.
- **U4.** The guard's role mode passes a table of allowed and refused commands
  (§27's list, plus writes, `cat`, `--context clear` and a send with no
  `--context`). Without `HANDS_ROLE` the same commands follow today's rules.
  A driver job's process gets `HANDS_ROLE=driver` (fake_claude). A driver role
  with `permission_flags` does not load, and doctor fails. `hands send --role
  driver` is refused.
- **U5.** End to end with fake_claude as the driver:
  - question → consult → the driver runs `hands send --context keep` and
    replies `resolved` → no stop, with `consult.sent`/`consult.done` in the
    inbox and one journal line in the builder's cwd;
  - question → consult → `escalate` → stop with the reason;
  - a third consult in one mission → stop naming `max_consults`, with no
    driver job.

  Unit tests: an unrecognised driver verdict stops; `driver.failed` stops; the
  prompt carries the reply verbatim; the count resets at the kickoff.
- **U6.** The root playbook loads. It names BUILDER-12, has `max_consults = 2`,
  and routes `^VERDICT: question` and the `^VERDICT:` catch-all to consult
  with `driver.done` follow-ups. It never consults on `aux.done` (engine
  tests).

## 3. NOT PROVEN

1. **A real consultation.** No real claude has run as the driver, followed the
   consult prompt, or obeyed the guard's role mode. Every driver in the tests
   is fake_claude.
2. **A real apply from a kit sent from a phone.** No real ntfy attachment has
   been fetched, and no real builder has applied a kit (fake_claude unzips
   nothing). The phone-only loop (kit → buttons → `go` → buzz) has not been run
   end to end.
3. **`hands kit check .` exit 0** (the acceptance line). It exits 1; see H-022
   and §5.
4. **U1.** No real kernel pid reuse was tested. A group member that cleared
   or hides its environment leaves its group unsignalled and unreported, and
   checking and signalling are still two steps. The load race was tested with
   an injected enqueue, not a real `hands send`. The directory-kit size cap has
   no test, and kit check was not run on a case-insensitive filesystem.
   Protocol placeholders are tried only as 0, 1 and 12.
5. **U2.** Not tested against a real `~/.claude` or `/proc`, or against another
   Claude Code version's sessions-file format. Jobs recorded in another spool
   are not excluded, nor is a job whose transcript appears before its session
   id is saved. Under `by directory`, another human's transcript can still show.
6. **U3.** handsd reads only `KIT.md` from the zip, so a corrupt entry is found
   only when the builder unzips. The daemon's prompt equals `kit check`'s only
   when the kit is at `~/Downloads/<same name>`. A busy builder does not block
   the held apply.
7. **U4.** The guard table does not cover every shell spelling.
8. **U5.** Untested: `consult.done` for a driver job that is killed, orphaned
   by a restart, or limited and resumed; two consults while the driver is
   busy; consults on monitor or `job.held` events.
9. **U6.** Untested: handsd loading this `PLAYBOOK.toml` under the real
   `~/.hands` config (the tests use a tmp config).

## Review items

| Item | Unit | Status |
|---|---|---|
| REVIEW-10 blocker 1 (`hands who` by pid) | U2 525dc66 | closed per §27 (sessions file); limits in §3 item 5 |
| REVIEW-10 should-fix 1 (`go` beside a held job; load race) | U1 efe4d56 | closed; race tested with an injected enqueue |
| REVIEW-10 should-fix 2 (apply step not phone-only) | U3 d4bea98 | closed by §27's apply from the kit; the loop is not run for real (§3 item 2) |
| REVIEW-10 should-fix 3 (sweep kills a vacated foreign group) | U1 efe4d56 | closed, with limits (the env mark; §3 item 4) |
| REVIEW-10 should-fix 4 (apply-literal exception) | U1 efe4d56 | closed; typo probe fails |
| REVIEW-10 should-fix 5 (kit check paths, sizes, send paths) | U1 efe4d56 | closed; directory-kit cap untested |
| REVIEW-10 should-fix 6 (InvalidURL, INTEGRATION :304) | U1 efe4d56 | closed |
| REVIEW-10 should-fix 7 (`done` statement unpinned) | U0 e8daca8 | closed; phrase containment only |

## 4. Acceptance

- `./scripts/check` green on the pushed tip, three consecutive runs: see §6.
- Every unit commit's body lists every file it touches; U0 is `plan:`
  (e8daca8): met, checked per unit.
- `hands who` on a fixture with a job and a session in one cwd attributes
  nothing of the job to the session: met (U2 tests).
- `PLAYBOOK.toml` names BUILDER-12 and has `consult` rules: met (U6).
  `hands kit check .` exits 0: **not met** (H-022).
- `meta/FINAL-REPORT-11.md` exists with NOT PROVEN and the review-items table:
  met by this commit.

## 5. For the architect

1. **H-022.** Say what "`hands kit check .` exits 0" means:
   - (a) the brief-in-force kit (`meta/BUILDER-11-PROMPT.md`, `--repo .`),
     which exits 0 today without comparing the kickoff;
   - (b) mission 12's kit (`PLAYBOOK.toml` + `meta/BUILDER-12-PROMPT.md`),
     whose brief must carry `VERDICT: question`;
   - (c) a repository mode for `kit check` (skip `.git`, pick the brief the
     kickoff names), which is a DESIGN change.
2. **`consult` on `resolved` uses `notify`.** §10 has no do-nothing action, so
   the phone hears about every resolved consultation. Say whether that is
   wanted.
3. **`max_consults` counting.** It counts driver jobs after the last builder
   job whose prompt equals the kickoff line; with no kickoff sent, every driver
   job counts. §27 says "per mission" without saying how a mission starts.
4. **Role mode refuses `cat`, `ls`, `grep`.** The driver reads its clone only
   through `git show` and `git grep`. §27's allowlist does not list them.
5. **The sweep's descendant test** is the job's environment mark, not a parent
   chain. A process that clears its environment escapes the kill (and the
   report).
6. **The busy-builder apply.** A kit that arrives while the builder is running
   still files a held apply behind it. §27 is silent.

## 6. Gate on the tip

The tip's product tree is 089e72f; U7 changes only meta/. `./scripts/check`
was green three consecutive runs before U7's commit, each `1732 passed` / `==
cli smoke ==` / `check: green` (117.33s, 113.58s, 110.30s). It was run again
three times with this report in place before the commit.
