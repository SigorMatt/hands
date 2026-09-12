# BUILDER-5-PROMPT — hands mission 5: review 4 and the daemon's memory

Kickoff line (the only way this mission is started or resumed):

    Read meta/BUILDER-5-PROMPT.md and execute the mission below its divider.

You are the builder for the `hands` repository. Read `DESIGN.md` (v3.4; §21
is this mission), `CLAUDE.md`, `meta/CHECKPOINT.md` (a unit in progress
means §R first), `meta/reviews/REVIEW-4.md` in full, and finding H-011.

---

## Mission

Clear review 4's two blockers, close its should-fix 1–5, 7 and 8 (6 is a
note on method and is answered by U3's independent table), resolve H-011,
stop the daemon's memory growing with a job's transcript, and forbid
background tasks in role sessions by hook. Deferred
from review 3 and still deferred: should-fix 3, 6, 7 of REVIEW-3 (say so in
the report). Finish with a report whose first line the playbook can match.

## Execution model (binding)

Unchanged. Run `./scripts/check` three times before every commit. Final
reply: `VERDICT: mission 5 finished` | `VERDICT: mission 5 blocked <unit>`
| `VERDICT: question <one line>`.

## Sub-agent brief (verbatim, plus the unit)

    You are implementing one unit of hands. Read, in this order: CLAUDE.md,
    DESIGN.md sections named by the unit, meta/CHECKPOINT.md, the review
    item(s) named by the unit (meta/reviews/REVIEW-4.md), then only the
    files the unit touches. Rules: the design is the spec; write the failing
    test before the code and confirm it fails; ./scripts/check green three
    times before you commit; one commit, `<area>: <one line>` + a body
    naming the unit, the DESIGN sections and the review item, stating only
    what the tests prove; push; never edit meta/plan.md, meta/CHECKPOINT.md
    or DESIGN.md; if the unit needs a design change, stop and write a memo
    to meta/findings/FINDINGS.md; report in ≤12 lines: sha, files, tests
    added, what is NOT proven.

## §R Recovery brief

As before.

## Units, in order

**U0 Plan and corrections.** `meta/plan.md`, `meta/CHECKPOINT.md` for
mission 5. Append to `meta/FINAL-REPORT-4.md` §3 a dated correction of
item 15: the guard's arbitrary-exec surface was not empty at `935a275`
(`git -c diff.external=<cmd> diff`, `git diff --output=<path>`,
`find -fprint`), citing REVIEW-4 blocker 1. Append to H-011 the decision:
the event is renamed `pipeline.stop_suppressed`.

**U1 Blocker 1 — git option policy (DESIGN §12, §21).** In
`driver/hooks/bash_guard.py`: before the subcommand, only `-C <path>` and
`--no-pager` are accepted; any other token beginning with `-` is refused
with a message naming the policy. After the subcommand, `--output`,
`--output=…`, `--ext-diff`, `--textconv`, `-O`, `--open-files-in-pager`
and `--config-env` (in any spelling, `=` or separate) are refused.
`FIND_ACTION_FLAGS` gains `-fprint`, `-fprint0`, `-fprintf`, `-fls`.
`tests/test_bash_guard.py`'s adversarial table gains the reviewer's exact
probes from REVIEW-4 blocker 1, each proven to be blocked, plus the
read-only commands the driver relies on, each proven to pass
(`git -C ./repo show origin/main:src/hands/config.py`, `git -C ./repo log
--grep=commit`, `git -C ./repo rev-parse abc^{commit}`, `git -C ./repo
grep -n "git diff" origin/main -- docs`). `driver/settings.json`'s allow
rules are unchanged; the guard is the layer that decides. Gate: both
tables green; the commit body lists which probes were blocked only after
this change.

**U2 Blocker 2 — monitor_cmd shape (§21).** `Config` refuses at load an
`ops.monitor_cmd` that is absolute, contains `..`, or does not name an
existing executable regular file under `ops.repo`; `monitor_path` returns
only a validated path. The existing test that documents the unreachable
state is rewritten to prove it. Gate: tests for `.`, `..`, absolute, a
directory, a non-executable file, a missing file, and a valid script.

**U3 Determinism as a property (should-fix 1, 2).** Every negative
assertion in `tests/` that compares against text which may embed a path
(`tmp_path`, `basetemp`, the socket path, the ops repo path) compares
after stripping those prefixes through one shared helper in
`tests/conftest.py`; the helper is used at `test_daemon.py:509` and
`test_playbook.py:345` and everywhere the audit finds. Then
`./scripts/check` is run five times with five different `--basetemp`
values, two of them crafted to contain `--pids` and `a send needs a
prompt`. Gate: 5/5 green; the commit body lists the values.

**U4 Prompt delivery (should-fix 3, 4, 5; §4).** The client sends the
request with `ensure_ascii=False`; the daemon's line room is the cap plus a
quarter; the same size check applies to `--stdin`; a non-regular file
(directory, FIFO, device, socket) is refused before opening, by `stat`;
`docs/INTEGRATION.md` and `hands --help` say exit 2 means the client did
not deliver a completed request (refusal or timeout). Gate: tests with a
9 MiB CJK file, a 10 MiB file of quotes, an at-cap NUL file, a FIFO, and
the same oversized prompt on both routes refusing at the same place.

**U5 Pipeline and config edges (should-fix 7, 8; H-011).** `hands
pipeline` marks `last_rule` with `stale: true` when its `playbook_sha256`
differs from the loaded one; the suppressed-stop event is renamed
`pipeline.stop_suppressed` everywhere (code, tests, docs); the two config
edges in should-fix 8 are closed the way U4 of mission 4 closed the first.
Gate: tests.

**U6 Daemon memory (§21).** Find where the runner or daemon accumulates a
job's stream-json (lists of events, captured stdout, log buffers) and
replace it with streaming writes to the job's log file under `~/.hands/`,
keeping in memory only the last N events needed for `tail` and the final
`result`. `hands log <job>` and `hands log -f` read the file. Gate: a test
with `fake_claude` emitting 200 000 events checks that the runner's
retained structures stay bounded (assert on the length of what is
retained, not on RSS); the commit body reports the daemon's RSS before and
after on a real run if one is available, else says NOT PROVEN.

**U7 No background tasks in role sessions (§21).** Add to this repository
`.claude/settings.json` with a `PreToolUse` hook on `Bash` running
`.claude/hooks/no_background.py`, which reads the hook JSON and exits 2
(reason on stderr) when `tool_input.run_in_background` is true or the
command daemonizes by hand (`nohup`, `setsid`, `disown`, a trailing `&`
outside quotes, `&` before `)`), telling the agent to run the command in
the foreground with a timeout. The hook has a `--selftest` and
`tests/test_no_background.py` runs it. `CLAUDE.md` states the rule in one
line. `docs/INTEGRATION.md` says every project that hands drives installs
the same two files. Gate: tests; `./scripts/check` itself still runs (it is
foreground).

**U8 Final report.** `meta/FINAL-REPORT-5.md`: what changed (sha per
unit), what tests prove, NOT PROVEN (mandatory, and it must describe the
guard's remaining surface as the reviewer would), and a `## Review items`
table mapping REVIEW-4 blockers 1–2 and should-fix 1–8 to `closed <sha>` |
`deferred <mission>` | `not applicable <reason>`, plus REVIEW-3's deferred
3, 6, 7. Then the verdict line.

## Budget guidance

Under quota pressure yield U6, then U5's config edges. Never yield U0–U4,
U7, U8.

## Acceptance

- `./scripts/check` green on the pushed tip, three consecutive runs.
- The adversarial table contains every probe REVIEW-4 blocker 1 executed,
  and each is asserted blocked.
- `grep -rn 'stop\\.suppressed' src tests docs driver` returns nothing.
- `meta/FINAL-REPORT-4.md` §3 carries the dated correction of item 15.
- `meta/FINAL-REPORT-5.md` exists with NOT PROVEN and the review-items
  table.
