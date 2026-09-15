VERDICT: mission 14 finished

# FINAL-REPORT-14 — hands mission 14: the guard's language, review 13

Brief: meta/BUILDER-14-PROMPT.md. Design: DESIGN v3.13 §30 (with §11, §12,
§28, §29). Review closed: meta/reviews/REVIEW-13.md (blockers 1–4, should-fix
1–8). Findings: H-026 filed and resolved by v3.13 (code U1); H-027 filed, open
(DESIGN lines a builder may not edit). Base: c958a62 (`plan: mission 14 kit
(DESIGN v3.13)`).

## 1. What changed (sha per unit)

| Unit | Commit | What | Gate |
|---|---|---|---|
| U0 Plan and bookkeeping | f9e0729 | plan; H-026 filed with the review 11–13 history; FINAL-REPORT-13's REVIEW-11 blocker 1 row corrected by a dated line; should-fix 8: `killed` wins over `limited` (docs/INTEGRATION.md + a PRECEDENCE row) | 3/3, 2284 |
| U1 The guard's language | 9a5bc75 | nine refusals before tokenizing, each naming the first offender and its position; `$`/`!` in double quotes; the comment, heredoc, redirection and expansion-position code removed; `git -C` by realpath, second `-C` refused | 3/3, 2437 |
| U2 Kit check names and who's configs | e79e770 | `kit check` judges bare relative names and the handbook's punctuation shapes (65-row fixture); `hands who` loads each config in its own try, a broken one as a root line | 3/3, 2524 |
| U3 Config edges | 599b993 | every config number must be finite (`nan`/`inf` refused); project names match `[A-Za-z0-9][A-Za-z0-9._-]{0,63}` at the flag, the environment and discovery | 3/3, 2569 |
| U4 Sweep, doctor, consult | 2ad4356 | the session-and-start-time proof needs no mark; the pipe-timeout test binds to the configured value; doctor's hook command must run the guard; the `max_consults` anchor persists | 3/3, 2588 |
| U5 Notifications and the playbooks | 104666d | 1.1 s between the two publishes of one cause; no shipped `job.held → notify` rule, one that keeps it still loads; the retired units leave the docs; H-027 | 3/3, 2597 |
| U6 This repository's playbook | fa8fbae | `[series] kickoff` → BUILDER-15; the BUILDER-14 kit check exits 0 | 3/3, 2597 |
| U7 Final report | this commit | this file, meta bookkeeping | — |

The mission's meta bookkeeping (meta/plan.md, meta/CHECKPOINT.md,
meta/journal.md) was held uncommitted between units and lands with this
commit, so mission 14 has no `meta:` commits between units.

## 2. What the tests prove

- **U0.** A `killed-over-limited` row in the PRECEDENCE table checks the
  clause is in docs/INTEGRATION.md's sentence, in order, and that
  `_final_state` returns `("killed", None)` for four runs where a cancel and a
  detected limit both hold. Moving the limit check ahead of the cancel check —
  REVIEW-13's mutation, which left the whole suite green — turns only this row
  red. The runner was not changed; it already checked cancel first.
- **U1.** The language, not the parser, is tested:
  - each of the nine refused characters or sequences (newline, CR, `<`, `>`,
    `#`, backtick, `$(`, `\`, `$'`), quoted and unquoted; all 65 Unicode
    control characters; a 69-row table giving the first offender and its
    position;
  - REVIEW-13's heredoc probe verbatim and three variants that hide `hands go`
    or a `--context clear` send, blocked in both modes through `check()`,
    through the hook, and through the shipped file run as a subprocess. The
    refusal is `a \`<\` at position 3`;
  - should-fix 1: a real symlink inside a `git init` clone — `<clone>/link/..`
    is refused — and a second `-C` refused by name;
  - the removed functions are gone and `grep -c heredoc` gives 0.
- **U2.** 65 fixture rows through `named_paths`, a check that the fixture
  holds REVIEW-13's ten probes and four real send prompts word for word, and
  those ten probes end to end: `hands kit check` exits 1, only `protocol`
  fails, and it names the missing file. Three `hands who` tests: several
  configs and none named, `--project beta` (text and `--json`), and all
  configs broken.
- **U3.** 39 refusal tests, each red at the parent for the value or the name
  itself: six `grace_s` spellings of `nan`/`inf`, non-finite for every one of
  the five number keys, and the reviewer's names (`..`, `.`, `a/b`, empty,
  65 characters, leading `-`/`.`/`_`, non-ASCII). `handsd --project ..`, `.`,
  `a/b` and `-a` exit 1 and leave the temp HOME unchanged.
- **U4.** One test each: an unmarked process in the job's session is killed
  and reported; the pipe timeout bound to the configured value at 0.2 s and
  1.5 s, where no single hardcode passes both rows (`timeout = 5.0` fails
  both, `0.2` fails the 1.5 s row); a 15-row doctor table of hook commands
  that name the guard but do not run it, plus `disableAllHooks`; two daemons
  over one spool — 2 consults used, restart, still 2, the next refused.
- **U5.** The receipt → `sleep 1.1` → held publish sequence, and the limit
  delay floor at the scheduler; no shipped playbook or template carries a
  `job.held` rule, while one that keeps it still loads and passes `kit check`;
  a sweep for the retired unit names; a driver-kit quoted-text sweep.
- **U6.** The kickoff test pins BUILDER-15 and is red on the value in a
  worktree at 104666d carrying only the test. A kit holding
  meta/BUILDER-14-PROMPT.md checked with `--repo .` gives `pass (6 of 6)`,
  exit 0.

## 3. NOT PROVEN

**3.1 The guard (U1).** The language is a definition, and only the definition
is proven. Not proven: that Claude Code hands the hook the exact string bash
runs; that no construct left inside the language (unquoted `${…}`, `$[…]`,
extglob, `case`) can desynchronise a quote — the claim is that the nine
refusals remove the constructs bash needs for it, not that every bash corner
was enumerated. Unquoted `$` outside `hands`/`git` arguments is still allowed
in normal mode (`echo $i`). REVIEW-11's probes are role-mode bypasses and stay
allowed in normal mode, where they are the human's own commands, per §28;
they are blocked in role mode. 18 rows moved from allowed to blocked (`2>&1`,
`$(pgrep …)`, `--stdin <`, `'fix #12'` among them): §30 plainly refuses each,
and no blocked row became allowed. The second `-C` is refused in role mode
only.

**3.2 Kit check (U2).** The bare-name rule is a syntactic guess. False
positives: a missing all-caps word of three or more letters in a send prompt
(`API`, `CLI`, `HEAD`, `TODO`) and capitalised `*file` words (`Profile`) now
fail kit check, and the architect has to rephrase. Misses: a lower-case bare
name (`notes`), a caps name with digits or `-` (`REVIEW-13`), `git show
rev:path` shapes, `_path_` emphasis. The corpus measured is four send prompts
plus the briefs BUILDER-8..14; the prose rows are a sample, not every English
word.

**3.3 Config (U3).** `hands` commands other than `status` and `who` are not
tested against a refused name, nor is what `hands doctor` shows for one. The
pattern still allows `jobs` and `roles` — §30 does not refuse them —
and docs/INTEGRATION.md says not to use them.

**3.4 Sweep, doctor, consult (U4).** Doctor reads only the driver directory's
`.claude/settings.json`: `settings.local.json` and user-level settings,
including a `disableAllHooks` there, are unread. The doctor table does not
enumerate every command a shell could run. A vacated stranger session created
after claude was observed alive would be over-reported as `killed: false` —
a report, never a kill. The queued-before-restart driver job counts by
timestamp only, not end to end. No real Claude Code session and no real
systemd were exercised.

**3.5 Notifications (U5).** Nothing reaches the network: that ntfy actually
orders two real messages 1.1 s apart, and that 1.1 s survives clock skew
between this machine and ntfy, are unproven. The limit pair is proven at the
scheduler, not from an observed published pair, because no shipped playbook
notifies on `builder.limited` today.

**3.6 The playbook (U6).** `meta/BUILDER-15-PROMPT.md` does not exist. Nothing
checks that a kickoff names an existing brief (REVIEW-13's note on U7 stands),
and the new value is pinned only by the updated test.

**3.7 REVIEW-13 notes not taken.** Outside §30 and untouched by this mission:
numeric IPv4 spellings and single-script confusables passing as host names;
the paused branch of `on_event` sitting outside the engine's try/except;
`hands who` loading every config twice; a job whose end handsd missed getting
`ended` set to the restart time.

## Review items

| Item | Unit | Commit | State |
|---|---|---|---|
| REVIEW-13 blocker 1 — heredoc desynchronises the guard's quote state | U1 | 9a5bc75 | closed (the language, §3.1) |
| REVIEW-13 blocker 2 — `kit check` misses bare relative names | U2 | e79e770 | closed (limits §3.2) |
| REVIEW-13 blocker 3 — `hands who` exits 1 on a broken first config | U2 | e79e770 | closed |
| REVIEW-13 blocker 4 — `grace_s = nan`/`inf` load | U3 | 599b993 | closed |
| REVIEW-13 should-fix 1 — `git -C` pin is lexical | U1 | 9a5bc75 | closed (realpath; second `-C` refused in role mode) |
| REVIEW-13 should-fix 2 — unmarked session member unreported | U4 | 2ad4356 | closed (§3.4) |
| REVIEW-13 should-fix 3 — pipe-timeout test unbound | U4 | 2ad4356 | closed |
| REVIEW-13 should-fix 4 — doctor green on a hook that enforces nothing | U4 | 2ad4356 | closed (limits §3.4) |
| REVIEW-13 should-fix 5 — `max_consults` reset by a restart | U4 | 2ad4356 | closed (persisted anchor wins) |
| REVIEW-13 should-fix 6 — project names unvalidated | U3 | 599b993 | closed (`jobs`/`roles` still match, §3.3) |
| REVIEW-13 should-fix 7 — retired un-templated units referenced | U5 | 104666d | closed outside the changelog; DESIGN lines → H-027 |
| REVIEW-13 should-fix 8 — cancel versus limit unpinned | U0 | f9e0729 | closed (`killed` wins) |

## 4. Acceptance

- `./scripts/check` green on the pushed tip, three consecutive runs: green
  3/3 on the U7 tree over fa8fbae (2597 passed; 158.77s, 166.78s, 160.09s).
  This commit adds meta files only.
- Every unit commit's body lists every file it touches, checked against `git
  show --stat` for f9e0729, 9a5bc75, e79e770, 599b993, 2ad4356, 104666d and
  fa8fbae. U0 is the `plan:` commit.
- `driver/hooks/bash_guard.py` contains no heredoc, comment or
  expansion-position handling; `grep -c heredoc` on it returns 0.
- Every probe of reviews 11–13 is in `tests/test_bash_guard.py`, asserted
  blocked (reviews 12 and 13 in both modes; review 11 in role mode, §3.1).
- This file exists with NOT PROVEN and the review-items table.

## 5. For the architect

1. **H-027 is open** and needs DESIGN lines only you may edit: §12 rule 6's
   "the guard treats quoted text as text", which the §30 language makes false
   for a quoted character from the refused set, and §14's layout line naming
   `systemd/handsd.service`, retired in mission 13. Until §12 rule 6 is
   corrected, `tests/test_docs.py` pins the driver kit to DESIGN's rule with
   that one clause substituted; the substitution becomes a no-op once you fix
   it.
2. **Readings to confirm.** U1: review 11's probes stay allowed in normal
   mode, and a second `-C` is refused in role mode only. U2: the bare-name
   rule (3+ capitals or `_`, except `VERDICT`; `<Cap>…file`) and its false
   positives. U3: `jobs` and `roles` still match the project pattern. U4: a
   persisted `max_consults` anchor wins, and daemon start anchors only when
   none is persisted. U5: the 1.1 s spacing is an injected sleep for the kit
   pair and a delay floor for the limit pair.
3. **BUILDER-15.** `PLAYBOOK.toml` names `meta/BUILDER-15-PROMPT.md`, which
   the architect's next kit must ship. Nothing checks that a kickoff names an
   existing brief.
