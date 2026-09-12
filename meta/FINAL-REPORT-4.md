# FINAL-REPORT-4 — hands mission 4: blockers and pipeline state

Mission: `meta/BUILDER-4-PROMPT.md`. Design: `DESIGN.md` v3.3, §20.
Review closed: `meta/reviews/REVIEW-3.md`, `VERDICT: review mission 3
blockers=3 should-fix=11`.

Base `796e5ae` (`plan: mission 4 kit (DESIGN v3.3)`) — green here before U0:
ruff clean, **618 passed**, cli smoke, `check: green`.
Tip `8343b92` — ruff clean, **726 passed**, cli smoke, `check: green`, three
consecutive runs, verified by the builder at that sha. U6 adds this file and
nothing else, so the commit carrying it changes no gate input.

Seven units planned, seven landed. No unit yielded, none blocked, no order
deviation. One departure from one-commit-per-unit, recorded in §1 U5.

This report is a snapshot. Per DESIGN §20, a claim here that later expires is
corrected by an appended dated line, never by a rewrite — `FINAL-REPORT-3.md`
§3 now carries the first such correction.

---

## 1. What changed, by unit

**U0 — `8268539` `meta: mission 4 plan; the two corrections review 3 asked
for`.** Meta only; no product code, no tests, so the gate is the base's.

- `meta/plan.md`, `meta/CHECKPOINT.md` for mission 4.
- **Blocker 3.** `meta/FINAL-REPORT-3.md` §3 gains a dated correction line;
  the original text is untouched. Item 1 ("the installed daemon is still the
  mission-1 build") was already false when mission 3's report was written.
  Evidence re-run, not re-copied — which is the whole lesson the review drew:

      $ hands --version
      hands 0.1.0
      $ hands --help | grep notify
          notify           send one message to the configured ntfy topic (§4, §11)

  `notify` is mission 2's command (`44c345b`), absent from the mission-1
  build; the installed `spool.py` carries m2's `ORIGINS` too. The residue that
  survives is stated: **mission 3's** code has never run outside the test
  suite (`grep -c prompt-file` on the installed `cli.py` → `0`).
- **Should-fix 2.** `meta/findings/FINDINGS.md` H-010 amended by appending.
  Both observations are recorded with the command that reproduces each: the
  `matches no known tool` warning string, present in 2.1.268 and 2.1.269, and
  `MultiEdit` in 2.1.269's permission-rule table and deny-rule normalizer
  (`toolName==="MultiEdit"?"Edit"`). They are about different things — a rule
  that warns is not a tool name the binary does not know — and the decision
  recorded is to keep the rule.

**U1 — `935a275` `driver: the git allowlist applies to every git token; find
-exec is forbidden`.** Blocker 1, should-fix 1 and 2. Gate green 3/3, 681
passed.

- `driver/hooks/bash_guard.py`: `ALLOWED_GIT_SUBCOMMANDS` (minus
  `FORBIDDEN_GIT_FLAGS`) applies to **every** `git` token, not only a
  segment's first word; `find` with `-exec`, `-execdir`, `-ok`, `-okdir` or
  `-delete` is refused whatever the payload; `MUTATING_GIT_SUBCOMMANDS` and
  the first-level-only check are gone, and the docstring that described them
  with them.
- The false-positive half is load-bearing and was nearly the cost of the fix:
  once the allowlist reaches every token, a path token that ends in `/git`
  starts looking like an invocation — and the human's workspace really is
  `~/git`. A path counts as an invocation only as a segment's first word, so
  `ls ~/git`, `cat ~/git/hands/DESIGN.md` and `find ~/git/hands -name '*.py'`
  stay readable.
- `tests/test_bash_guard.py` gains `ADVERSARIAL`, a second table **owned by
  `tests/`** — composed from DESIGN §12/§20 before the guard file was opened,
  so it can disagree with the guard, which review should-fix 1 says the
  `SELFTEST` re-run never could.
- `driver/settings.json` denies `MultiEdit` again; `tests/test_docs.py`
  asserts it is present (red before the settings change); H-010 gains its
  closing `Status` line.
- **Correction to that commit's body:** it says the adversarial table has 61
  cases. It has 62 (40 block, 22 allow). The sub-agent reported the slip
  rather than amending pushed history; the count is corrected here.

**U2 — `667ea52` `tests: pin the assertions a tmpdir path could satisfy`.**
Blocker 2, should-fix 11. Test-side only; no product file touched. Gate green
**5/5** consecutive, 682 passed.

- The flake was reproduced first, at the parent, with the review's own
  command (`--basetemp=/tmp/pt-40/pytest-1340` → `1 failed` on
  `tests/test_daemon.py:556`), and the same command is `1 passed` after the
  fix. That before/after — not the 5/5 — is the evidence the flake is gone:
  the natural run counter never landed on a 40-bearing value during those
  five runs (1469–1473), so 5/5 alone would only mean "unobserved".
- The audit is the unit, not the one line: 246 assert statements read across
  `tests/test_daemon.py` and `tests/test_playbook.py`, 30 changed. A **second**
  live instance of the same fault was found and reproduced
  (`test_status_says_stall_detection_is_off_at_zero_minutes`, red under
  `--basetemp=.../pytest-1340m-off-on-send`), along with `"handsd" in err`
  satisfied by the socket path and `"playbook" in stop_reason` satisfied by
  the tmpdir name.
- One test added: `test_every_bad_playbook_is_pinned_to_a_refusal_only_it
  _makes` — each `BAD_PLAYBOOKS` expectation must match its own refusal and no
  other's. That is the invariant standing behind the 19 bare-word assertions
  it pinned, since a positive `in` assertion can be made falsely green by a
  path collision but never red, so it cannot be demonstrated by reproduction.

**U3 — `c108bfe` `playbook: one stop() for every component, and a cli job
un-pauses when it starts`.** Should-fix 4; DESIGN §10's "Stop → resume cycle"
as v3.3 writes it. Gate green 3/3, 692 passed.

- (a) The un-pause moved from file time (`Api.send` → `on_send`) to start time
  (`PlaybookEngine.on_job_start`), and narrowed to `UNPAUSE_ORIGINS = {"cli"}`.
  A held or queued send changes nothing; a `playbook`-, `limit`- or
  `driver`-origin job never clears a stop.
- (b) One `stop()`. `LimitManager` no longer writes its own `stop` event; its
  `max_resumes` stop reaches the engine through `on_stop` and inherits the
  keep-first-reason rule. A later stop over an existing one keeps the first
  reason and its timestamp, files `stop.suppressed` with the would-be reason,
  and sends no notification. `hands pause` over an existing stop is that same
  case and still answers `already_stopped`.
- (c) `last_rule` is cleared when a playbook with a different sha256 loads;
  `PipelineState` remembers the sha, and a state file written before that key
  existed round-trips without crashing.
- (d) `pipeline.resumed` says `by: start` or `by: resume`.
- Mission 1's `test_the_section_10_example_end_to_end` is unchanged and passes.
- This unit produced **H-011** (§6 below): `stop.suppressed` sits inside
  `stop`'s wake namespace, so `hands wait --for stop` now wakes on a stop that
  was deliberately not notified.

**U4 — `15eeb76` `config: refuse a blank optional key, and let doctor report a
config error`.** Should-fix 5 and 8. Gate green 3/3, 719 passed.

- Every optional string key in §13 was enumerated, not only the two the review
  named: `server.socket`, `server.ntfy_topic`, `server.ntfy_url`,
  `roles.<r>.{model,permission_flags,resume_line,cwd}`, `ops.repo`,
  `ops.monitor_cmd`, `playbook.path`, the items of `files.allowed_roots` and
  `gates.patterns`, `runner.claude`. All refuse a blank now except
  `permission_flags` (whose `""` is its default and means "no flags") and
  `cwd` (required, so "omit the key" is not one of the two choices — it gets a
  required-key message instead of the old misleading `got '.'`).
- The mechanism is the point: `_str`/`_opt_str`/`_str_list`/`_path` take a
  **required** `blank` keyword, so a newly added key cannot silently skip the
  check the way `monitor_cmd` skipped the one mission 3 added for
  `resume_line`.
- `hands doctor` catches `ConfigError` from `resolve_project`/`load_config`
  and reports it as a failed `config` row — text and `--json` — with exit 1,
  instead of crashing with a bare message. No other command's behaviour
  changed.

**U5 — `2fb3b7f` `cli: refuse an oversized prompt file at the path the human
named`, then `d348d07` `cli: a refused prompt file exits 2, like a wait that
gave up`.** Should-fix 9 and 10. Gate green 3/3 at each; 725 then 726 passed.

- **Two commits, not one.** The unit's sub-agent implemented the four refusals
  but exited **1**, not the 2 the mission brief specifies, and reported the
  deviation with its reasoning (`EXIT_TIMEOUT = 2` was documented as "told
  apart from every other failure (which is 1)"). The builder ruled for the
  brief: 2 was only ever returned on `hands wait`'s timeout path, `hands send`
  cannot time out that way, so nothing reads the code ambiguously. `d348d07`
  is that correction. The convention is one commit per unit; this is the
  departure, recorded rather than amended away.
- All four refusals (missing, unreadable, empty, over the cap) are now
  client-side, each a one-line error naming the path, exit 2, with no socket
  connection attempted. The cap reuses `runner.MAX_PROMPT_BYTES` and is
  checked by `stat`, without reading the file.
- `EXIT_REFUSED = 2` with `EXIT_TIMEOUT = EXIT_REFUSED` kept as the name
  `hands wait`'s readers (driver rule 8) know it by — one value, two
  spellings, pinned equal by a test so a later edit cannot split them.
- `driver/CLAUDE.md` rule 6 is DESIGN §12's rule 6 verbatim (a test asserts
  the equality, flattened), and the self-contradicting sentence — "Nothing
  with shell metacharacters goes on a command line", written in the same
  breath as `hands put <path> --content "<text>"` — is gone. Rule 3 and the
  "Starting a mission" section, which repeated the claim in other words, were
  brought into line. `grep -rn metacharacters driver/` returns nothing.

**U6 — this report**, then the verdict line.

---

## 2. What the tests prove

618 → 726 tests. Per unit: 681, 682, 692, 719, 725, 726.

**The guard (U1).** Two tables now, and only one of them is the guard's own.
`ADVERSARIAL` (62 cases: 40 block, 22 allow) was run against the old guard in
a throwaway worktree at `ecdb0f3`, where **14 failed** — the nine
`find -exec git …` second-level writes blocker 1 names (`remote add`,
`notes add`, `submodule add`, `bisect reset`, `sparse-checkout init`,
`update-index --add`, `branch -D`, `update-ref`, `gc --prune=now`), plus
`-execdir` twice, `-okdir`, `find . -delete` and `find . -name '*.pyc'
-delete`. The other 48 were green there and stay green here. No `SELFTEST`
expectation was changed to fit: 65/65, `--selftest` exits 0. The allowed half
proves the fix did not buy safety with usability — read-only git
(`rev-parse <sha>^{commit}`, `log --grep=commit`, `show origin/main:path`) and
reads of `~/git` still pass.

**The gate (U2).** The gate is deterministic under the reproduction that made
it flaky: `--basetemp=/tmp/pt-40/pytest-1340` was red at the parent and is
green at the tip, for the named test and for both files together. 30
assertions across the two files no longer match what a tmpdir path, a socket
path or a run counter could contain.

**Pipeline state (U3).** Each of the five gate cases the brief named has a
test: gate-time no-op, start-time un-pause (`by = "start"`, `was` = the reason
it cleared), a playbook/limit/driver job not un-pausing, a `max_resumes` stop
landing over a rule stop through the **real daemon wiring** (first reason and
timestamp kept, one `stop.suppressed`, no second notification), and the
`last_rule` reset on a different sha256. Also proved: a `max_resumes` stop
with nothing over it still files exactly one `stop` and one notification, and
an old state file round-trips.

**Config and doctor (U4).** 22 parametrized refusals (11 keys × `''` and
`'   '`), the specific bug review should-fix 5 described — an empty
`monitor_cmd` no longer makes the repo directory the monitor — and that
`permission_flags = ""` stays legal. Four doctor cases: the failed `config`
row in text and in `--json`, a missing config file, and `hands status`
unchanged.

**`--prompt-file` and the kit (U5).** All four refusals with `cli.call`
patched to raise: empty stdout, a one-line stderr naming the path, exit 2,
and the daemon never contacted. The cap is proved to be checked without
reading the file (`Path.read_bytes` patched to raise), and a file at exactly
the cap is sent. `EXIT_REFUSED == EXIT_TIMEOUT == 2` is pinned. Two docs
tests: kit rule 6 equals DESIGN §12 rule 6, and `driver/` never claims a
command line cannot hold punctuation.

---

## 3. NOT PROVEN

1. **None of mission 3's or mission 4's code has ever run outside the test
   suite.** Re-checked today, not carried forward: the installed build is
   mission **2**'s (`hands --help` lists `notify`; the installed `cli.py` has
   no `--prompt-file`). `uv tool install --force ~/git/hands` is what would
   put this mission's code under a real run. Largest gap in the project, and
   now two missions old.
2. **No request has ever left the machine.** `hands notify --test` against a
   live ntfy topic is still unrun; mission 3's proof was httpx `MockTransport`,
   off-network by construction. Carried forward, and the fact it asserts is
   about the network, not the disk, so it needs re-running, not re-copying.
3. **The guard has still never run as a real Claude Code `PreToolUse` hook.**
   `tests/test_bash_guard.py` proves `check()`'s verdicts against two tables;
   `main()`'s stdin/exit-2 wiring has no test, and Claude Code's own hook
   invocation is exercised by nothing.
4. **The `MultiEdit` deny rule is asserted on disk, not observed in a
   session.** H-010's amendment proves the name is in 2.1.269's rule table and
   normalizer by grepping the binary. What the CLI prints at driver start with
   the rule restored was not observed in this mission.
5. **U1's `~/git` false-positive fix is covered only for the shapes in the
   table.** A bare `git` token in argument position with no resolvable
   subcommand still blocks (fail-closed) — e.g. `grep --grep git` shapes. That
   is the safe direction, but it is a refusal no case pins as intended.
6. **U2's positive assertions cannot be demonstrated by reproduction.** An
   `assert x in out` can be made falsely *green* by a path collision, never
   red, so the 19 playbook pins rest on the new
   `test_every_bad_playbook_is_pinned_to_a_refusal_only_it_makes` invariant
   rather than on a red-then-green run. The audit covered the two named files
   only; the other eleven test files were not read.
7. **U3's "filed ≠ started" is proved through the §8 gate, not through the
   queue.** No test covers an ungated `cli` send sitting *queued* behind
   another job; the held-job case is the deterministic stand-in.
8. **Suppressed stops are not deduped by reason.** A repeated identical stop
   appends a `stop.suppressed` each time. Untested either way.
9. **`last_rule` is cleared only when a playbook actually loads with a
   different sha.** A deleted or unparseable playbook leaves the old
   `last_rule` in place; untested either way.
10. **`LimitManager.stop` with no `on_stop` seam now records nothing but a log
    line** — it no longer writes its own `stop` event. Only the daemon wiring
    is pinned, so a future caller that forgets the seam loses the event
    silently.
11. **U4's unresolved-project branch is exercised by hand only.**
    `project = None` → the `<project>` placeholder and `"config": ""` in the
    JSON row has no test.
12. **U5's "unreadable" is a directory and a non-UTF-8 file**, not a
    chmod-000 file (which would be vacuous under root). And no test pins that
    the daemon's cap and the client's can never drift apart other than by
    sharing the constant.
13. **The design says 10 MB and the code means 10 MiB.** `MAX_PROMPT_BYTES =
    10 * 1024 * 1024` = 10,485,760, so a file between 10,000,000 and
    10,485,760 bytes is accepted by a client whose help text says 10 MB. The
    constant was not changed — it is also the runner's and the daemon line
    limit's basis — and builders do not edit `DESIGN.md`. §6 below.
14. **`mypy` is still not in `./scripts/check`.** The gate is ruff + pytest +
    a CLI smoke test; no type checker has seen this mission's annotations.
    Carried forward from mission 3 and still true.
15. **`find -exec` is closed; the general wrapper question is not.** The guard
    now refuses `find`'s exec flags outright, which was the one arbitrary-exec
    vector left inside the allow list. Whether the allow list should contain
    `find` at all is the architect's question, not this mission's.

**Correction, 2026-09-12 (mission 5 U0; REVIEW-4 blocker 1).** Item 15's middle
clause is false. `find -exec` was closed at `935a275`, but the arbitrary-exec
surface inside the allow list was **not** empty there and is not empty at
`edf0bc2`. Re-run today against both (`check()` returning `None` = allowed):

    git -c diff.external='touch /tmp/gprobe-pwned' diff --ext-diff  -> None
    git -c core.pager=touch log                                     -> None
    git diff --output=/tmp/x                                        -> None
    git show HEAD --output=/tmp/x                                   -> None
    find . -fprint /tmp/out  (also -fprint0, -fprintf, -fls)        -> None

`git -c <key>=<cmd>` sets a config key for one invocation and `diff.external` /
`core.pager` are keys whose values git executes, so an allowed first-level
subcommand runs an arbitrary command; the reviewer confirmed the first live
(`/tmp/gprobe-pwned` created). `--output=` and `find -fprint*` are the write
half, against DESIGN §12's "never writes". None of these are regressions — the
pre-`935a275` guard allowed them too — so what item 15 got wrong is the
sentence, not the unit: it told the architect the surface was empty in the one
section whose job is to say what is not. The report is a snapshot and is not
rewritten (DESIGN §20); this line is the correction. Mission 5 U1 closes these
vectors in the guard and pins the reviewer's exact probes in the adversarial
table; what remains open after it is stated in `meta/FINAL-REPORT-5.md` §3.

---

## 4. Review items

`meta/reviews/REVIEW-3.md`, `VERDICT: review mission 3 blockers=3
should-fix=11`.

| Item | Status |
|---|---|
| Blocker 1 — U6 weakened the guard it was narrowing | closed `935a275` |
| Blocker 2 — the gate is not deterministic | closed `667ea52` |
| Blocker 3 — `FINAL-REPORT-3.md` §3 item 1 contradicted by disk | closed `8268539` |
| 1 — the guard test cannot fail on anything unforeseen | closed `935a275` |
| 2 — H-010's premise does not survive checking | closed `8268539` (evidence, both observations) and `935a275` (rule restored) |
| 3 — `doctor.py`'s probe argv still hardcodes the three flags | deferred, mission 5 (by the mission brief) |
| 4 — §6 can still overwrite a stop reason | closed `c108bfe` |
| 5 — `ops.monitor_cmd = ""` is the bug U4 just fixed, one dataclass down | closed `15eeb76` |
| 6 — `accepted()` calls a non-integer status delivered | deferred, mission 5 (by the mission brief) |
| 7 — `Api.notify`'s failure shape changed and no client tests it | deferred, mission 5 (by the mission brief) |
| 8 — `hands doctor` cannot report a config error | closed `15eeb76` |
| 9 — an oversized `--prompt-file` gets no client-side refusal | closed `2fb3b7f`, exit code corrected in `d348d07` |
| 10 — driver rule 6 is unusable as written, and contradicts itself | closed `2fb3b7f` |
| 11 — U2 strengthened four assertions and left their siblings loose | closed `667ea52` |

Nothing is marked *not applicable*: every item was either closed or deferred
by the brief's own instruction. The three deferrals are the brief's call, not
the builder's, and are named here so a deferral is written down rather than
hidden.

---

## 5. Acceptance, checked

1. **`./scripts/check` green on the pushed tip, three consecutive runs.** Yes
   — at `8343b92`, the last commit before this report: 726 passed each time
   (26.94s / 27.31s / 28.57s), ruff clean, cli smoke, `check: green`. This
   report's own commit adds one meta file and touches no gate input.
2. **`tests/test_bash_guard.py` has two tables, the adversarial one with ≥20
   cases; `MUTATING_GIT_SUBCOMMANDS` does not exist.** Yes — `SELFTEST` (65
   cases, run one per test) and `ADVERSARIAL` (62, with a test asserting the
   table cannot shrink below 20 or lose either verdict). `grep -rn
   MUTATING_GIT_SUBCOMMANDS` outside `meta/` returns nothing; inside `meta/`
   it survives only in mission-3 history and this mission's own briefs, which
   are snapshots and are not rewritten.
3. **`driver/settings.json` denies `MultiEdit`; `driver/` contains no
   "metacharacters".** Yes, both — the second verified by `grep -rn
   metacharacters driver/` returning nothing, and pinned by a test.
4. **`meta/FINAL-REPORT-3.md` §3 carries the dated correction; H-010 carries
   the amendment.** Yes, both by appending only.
5. **`meta/FINAL-REPORT-4.md` exists with NOT PROVEN and the review-items
   table.** This file.

---

## 6. For the architect

**H-011, filed by this mission** (`meta/findings/FINDINGS.md`). §20's
`stop.suppressed` is inside `stop`'s wake namespace: `resolve_kinds` matches a
name three ways and the third is `kind.startswith(f"{name}.")`, so `hands wait
--for stop` — what DESIGN §12 rule 8 tells the driver to arm — now resolves to
`{stop, stop.suppressed}`. The driver wakes on a stop that was deliberately
not notified. Small (the pipeline is already stopped, and rule 2 sends the
driver to the inbox first), but it is a design consequence, not a code choice;
the memo offers three ways out.

**Two exit-code spellings for one value.** `EXIT_REFUSED = 2` and
`EXIT_TIMEOUT = 2` are now the same constant. DESIGN §12 rule 8 still says
only "Exit code 2 is a timeout, not an event" — correct for the armed `hands
wait` it describes, and now incomplete as a statement about the CLI. Worth one
clause in §12 or an explicit decision that 2 means "the command refused before
it did anything".

**10 MB or 10 MiB.** §2/§4 say 10 MB; `MAX_PROMPT_BYTES` is 10 MiB, and it is
also the basis of the runner's check and the daemon's line limit. One word in
the design, or one constant in the code — the builder changed neither, because
either choice is the architect's.

**H-009 is still open** and still cannot be closed by a builder: §7's prose
example at `DESIGN.md:258` omits `--origin`, which §4's table and the code both
have. **H-001** is still open and needs a capture from a dotted cwd.

**What this mission cost, and what it bought.** Every one of review 3's three
blockers was real and cheap to fix; two of them (the guard hole, the flaky
assertion) were *found by the review and not by the gate*, and the third was a
sentence nobody re-ran. The pattern across both reviews is the same: a table
of expectations the tests own catches what a self-checking artifact cannot,
and a NOT PROVEN item that asserts a fact about the machine has to be
re-executed every mission or it rots in place. U1 and U2 are that lesson
turned into two tables and an audit; §3 items 1 and 2 above were re-run today
rather than copied from mission 3.

The gap that has now survived four missions is unchanged and is not a test
problem: **nothing since mission 2 has run outside pytest.** One
`uv tool install --force ~/git/hands` closes it, and every mission that does
not do it adds another mission's worth of code to what the installed daemon
has never executed.
