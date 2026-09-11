# REVIEW-3 — cold review of mission 3 (close the review)

Aux session, no mission context. Base `fa409e6` → `origin/main` `3251c69`.
Protocol: `meta/REVIEW-PROTOCOL.md`. Seven unit commits, one sub-agent each in
its own detached worktree; the nine `meta:` bookkeeping commits skipped.

    VERDICT: review mission 3 blockers=3 should-fix=11

## Blockers

1. **U6 weakened the guard it was narrowing, and the commit body says it did
   not.** `ecdb0f3`'s body states "Every case the old guard blocked is still
   blocked." It is false. `mutating_git()`
   (`driver/hooks/bash_guard.py:174-184`) reads only the *first-level* git
   subcommand, so a mutating second-level verb behind a read-only-looking first
   word now passes where the old `\bgit\b.*\b(push|commit|add|…)\b` regex
   matched it. Verified at the tip by loading the hook and calling `check()`:

       find . -exec git remote add origin https://x/y.git \;   NEW: ALLOW   OLD: block
       find . -exec git notes add -m x HEAD \;                 NEW: ALLOW   OLD: block
       find . -exec git submodule add https://x/y.git \;       NEW: ALLOW   OLD: block
       find . -exec git bisect reset \;                        NEW: ALLOW   OLD: block
       find . -exec git sparse-checkout init \;                NEW: ALLOW   OLD: block
       find . -exec git update-index --add x \;                NEW: ALLOW   OLD: block

   (`OLD` = `git show ecdb0f3^:driver/hooks/bash_guard.py`, same harness.) The
   hole is bounded — at the *first* word the allowlist
   (`ALLOWED_GIT_SUBCOMMANDS`, `FORBIDDEN_GIT_FLAGS`, `bash_guard.py:28-34`)
   still blocks every one of these bare (`git remote add …` → `git flag not
   allowed`), so the regression reaches only through `find -exec` and the other
   argument positions where `mutating_git()` is the sole check. It is still a
   net loss of coverage introduced by a change whose stated purpose was to
   refuse *less*, asserted safe in the commit body and in `FINAL-REPORT-3.md` §1
   ("`mutating_git()` scans every `git` token in a segment, so `find . -exec git
   push \;` stays blocked as the regex had it" — true for `push`, not for the
   six above). Fix shape: apply `ALLOWED_GIT_SUBCOMMANDS` to every `git` token,
   not only to a segment's first word. (`find . -exec git branch -D main \;`,
   `… git update-ref …`, `… git gc --prune=now \;` pass under **both** guards —
   pre-existing, not this commit's doing, and the same fix closes them.)

2. **The gate is not deterministic: `./scripts/check` fails on roughly one run
   in ten.** `tests/test_daemon.py:556` (added by `87bb7f8`, U1) asserts
   `"40" not in out.split("monitor  ")[1].splitlines()[0]` — meaning "the
   built-in `stall_minutes = 40` is not stated" — but that line also carries the
   ops script's path, which lives under the pytest tmpdir. Whenever pytest's run
   counter contains `40`, the assertion matches the path and the gate goes red.
   The U4 sub-agent hit it naturally (`pytest-1340`); I reproduced it
   deterministically at the tip:

       $ uv run pytest "tests/test_daemon.py::test_status_names_the_ops_script_and_its_flags_when_ops_decides" \
             -q --basetemp=/tmp/pt-40/pytest-1340
       >       assert "40" not in out.split("monitor  ")[1].splitlines()[0]
       E       AssertionError: assert '40' not in 'ops (/tmp/p...; watching 0'
       E         'ops (/tmp/pt-40/pytest-1340/test_status_names_the_ops_scri0/ops/watch_monitor.sh);
       E          the script decides; hands fills --pids --transcript --base; watching 0'
       tests/test_daemon.py:556: AssertionError
       $ ... --basetemp=/tmp/pt-xx/pytest-1339      # control
       .                                                                [100%]

   `/tmp/pytest-of-msi/` is at `pytest-1367` today, so the next natural hit is
   the 1400s. Every "green" in this mission is a sample from a distribution, not
   a property. Assert `"40m"`, or strip the script path before the check.

3. **`FINAL-REPORT-3.md` §3 item 1 is contradicted by disk.** It reads "Nothing
   in missions 2 or 3 has ever run outside the test suite. The installed daemon
   is still the mission-1 build, as REVIEW-2 verified against the installed
   `spool.py`." REVIEW-2 was right when it wrote that; it stopped being true
   eight minutes later. The installed package
   (`~/.local/share/uv/tools/hands/lib/python3.14/site-packages/hands/`, mtime
   `2026-09-11 23:35:22`, i.e. after `88b0e91 review: mission 2` at 23:27 and
   before `fa409e6 plan: mission 3 kit` at 23:57) is a **mission-2** build:

       spool.py:93   ORIGINS = frozenset({"driver", "playbook", "cli", "limit"})   # a67c4b0, m2 U1
       config.py     resume_prompt                                                # 8448b6f, m2 U2
       playbook.py   pipeline.resumed  (absent at the mission-1 tip 530de9d)       # 267ee01, m2 U4
       api.py        def notify                                                    # 44c345b, m2 U5

   and it ran: the live spool has two `pipeline.resumed` events
   (`~/.hands/inbox.jsonl` `e000021`), a kind that does not exist in mission-1
   code, and the daemon serving them (`pid 1763453`, started `23:54:03`,
   `/home/msi/.local/share/uv/tools/hands/bin/python`) is the process that
   dispatched mission 3 itself (`e000022`, `VERDICT: mission 3 finished`) and
   this review (`e000023`). So mission 2's code *has* run outside the test
   suite, and the sentence carried forward verbatim from `FINAL-REPORT-2.md` §3
   went stale without being re-checked. The residue is true and worth keeping:
   **mission 3's** code has never run outside the test suite — the installed
   `cli.py` has no `--prompt-file`, `playbook.py` no `already_stopped`,
   `monitor.py` no `OPS_FLAGS`. Rewrite item 1 to that, and with it §6's closing
   recommendation, whose premise ("Three missions of code have now been gated
   only by the test suite") is the same false sentence.

Everything else about the gates holds. Every unit commit is green at its own
sha on the runs the sub-agents made (523 → 523 → 526 → 530 → 539 → 603 → 618),
every product unit's tests were confirmed load-bearing by reverting only that
commit's non-test files and watching them go red, no unit commit touches
`DESIGN.md`, `meta/plan.md` or `meta/CHECKPOINT.md` (`DESIGN.md` is untouched
across the whole range), and the pushed tip is green here too — `ruff … All
checks passed!`, `618 passed in 34.68s`, `check: green`, with
`python3 driver/hooks/bash_guard.py --selftest` → `selftest: 65/65 ok`. The
mission's four acceptance criteria all hold; the test counts the report claims
(521 at the base, 618 at the tip) are exact.

## Should-fix

1. **`tests/test_bash_guard.py` cannot fail on anything the author did not
   already think of.** It loads the hook by path and re-runs the product file's
   own `SELFTEST` table (`tests/test_bash_guard.py:22-46`), so its verdicts are
   the guard's own. Reverting the product file for the test-first check reverted
   the ten new cases with it, and all 52 remaining parametrized cases were
   **green against the unfixed guard** — the only load-bearing assertion in the
   whole file was `tests/test_docs.py::test_the_driver_denies_every_writing_tool`
   (the `MultiEdit` one). `assert len(guard.SELFTEST) >= 50`
   (`tests/test_bash_guard.py:35`) would not notice twelve cases being deleted.
   DESIGN §19's "the self-test lives in `tests/`" is satisfied in letter. An
   expectation table owned by `tests/` — which is exactly what would have caught
   blocker 1 — is what satisfies it in substance.

2. **H-010's premise does not survive checking, and two decisions rest on it.**
   The memo says "Claude Code 2.1.x has no `MultiEdit` tool … the CLI warns
   about an unknown tool in `permissions.deny` when the driver session starts",
   and on that basis U6 removed a live deny rule and the architect is asked to
   strike `MultiEdit` from DESIGN §12. In the installed
   `~/.local/share/claude/versions/2.1.269`, `MultiEdit` is a **known
   permission-rule tool name**: `WKr=["Write","Edit","MultiEdit","NotebookEdit"],
   tGt=new Set(WKr)`, the deny-rule normalizer `r.toolName==="Write"||
   r.toolName==="NotebookEdit"||r.toolName==="MultiEdit"?"Edit"`, the
   `filePath` input map and the progress-verb map all carry it; I found no
   "unknown tool in permissions.deny" string at all. That it is not *offered* to
   a model today is a different claim from the one the memo makes. The report's
   own NOT PROVEN 5 flags the risk ("If the premise is wrong, U6 removed a live
   deny rule") — it is now evidence, not a risk. Re-verify before the architect
   amends §12.

3. **`doctor.py`'s probe argv still hardcodes the three flags.** `MONITOR_FLAGS
   = OPS_FLAGS` (`src/hands/doctor.py:76`) single-sources the `--help` check and
   the messages, but the probe that actually runs the script still spells
   `"--pids", …, "--transcript", …, "--base", "HEAD"` literally
   (`doctor.py:232-241`). So `FINAL-REPORT-3.md` §1's "what doctor probes for is
   what the monitor sends" is true of the report and not of the probe; changing
   `OPS_FLAGS` desyncs it silently, and no test pins the probe argv against it.

4. **U3's fix is pause-shaped, and §6 can still overwrite a stop reason.**
   `stop()`'s dedupe guard is unchanged (`src/hands/playbook.py:907`), and the
   limit manager bypasses the engine's paused gate (`src/hands/limits.py:429-437`
   → `src/hands/daemon.py:449` → `playbook.stop(...)`), so a `max_resumes`
   exhaustion over an existing stop still rewrites `stop_reason`/`stopped_at`
   and fires a second notification — the same defect class as review should-fix
   4, one seam over. Outside DESIGN §19's literal wording, untested either way,
   and the report's NOT PROVEN 7 names it.

5. **`ops.monitor_cmd = ""` is the bug U4 just fixed, in the next dataclass
   down.** `_opt_str` returns `""`, not `None` (`src/hands/config.py:409-412`),
   and `OpsConfig.monitor_path` only tests `is None` (`config.py:117-119`), so
   `Path('/x') / '' == Path('/x')`: an empty `monitor_cmd` with `ops.repo` set
   makes the *repo directory* the monitor. `MonitorSource` then flips to `"ops"`
   (`src/hands/monitor.py:312`), U1's new status line reports a directory as the
   deciding script, and builder jobs go unwatched behind "is not a file"
   (`monitor.py:559`). Verified:
   `OpsConfig(repo=Path('/x'), monitor_cmd="").monitor_path` → `PosixPath('/x')`.

6. **`accepted()` calls a non-integer status delivered.** `if isinstance(status,
   bool) or not isinstance(status, int): return True`
   (`src/hands/notify.py:152-154`). The carve-out exists to keep a legacy test
   double green (`tests/test_wake.py:226-234`, a `Posts` that returns `None`),
   so product code is shaped by a double, and a real transport regression that
   returns `None` would count as a successful delivery. Narrow it to the
   double, or fix the double.

7. **`Api.notify`'s failure shape changed and no client tests it.** A 403 now
   returns `delivered: false` instead of raising `ApiError`
   (`src/hands/api.py:658-662`); the only `Api` test uses a 200
   (`tests/test_wake.py:861-871`). The generic socket path returns 0
   unconditionally (`src/hands/cli.py:604-605`) with no `notify` branch in
   `_render`, so a socket caller would get exit 0 and a raw dict where the CLI
   exits 1. Latent today — `cli.py:576-579` intercepts before the socket — but
   it is a divergence §9 will inherit.

8. **`hands doctor` is the one command that cannot report a config error.**
   `load_config` runs inside the same `try` as the command
   (`src/hands/cli.py:571-572` → the handler at `:601`), so U4's new
   `resume_line` refusal — like every other `ConfigError` — makes `doctor` exit
   1 with the message instead of reporting it as a failed check. Consistent with
   the existing shape, and precisely counterproductive for the command whose job
   is explaining a broken config.

9. **An oversized `--prompt-file` gets no client-side refusal.** Missing,
   directory, non-UTF-8 and empty all refuse by name (`src/hands/cli.py:701-726`),
   but `MAX_PROMPT_BYTES` is enforced only at run time
   (`src/hands/runner.py:283-285`) and the socket reader caps at
   `MAX_PROMPT_BYTES + 1 MiB` (`src/hands/daemon.py:63,166`). A >11 MiB file
   fails somewhere other than at the path the human named; untested.

10. **Driver rule 6 is unusable as written, and contradicts itself.** The
    report's NOT PROVEN 6 is verified true on disk: the driver cannot write
    (`driver/settings.json:4-6` denies Edit/Write/NotebookEdit, `:14-18` denies
    `rm/mv/cp/touch/tee`) and `hands put --from` is root-confined
    (`src/hands/files.py:76-77`), so a prompt file must already exist in `CLONE`
    or be placed by the human. Separately, `driver/CLAUDE.md:42-44` says
    "Nothing with shell metacharacters goes on a command line" while prescribing
    `hands put <path> --content "<text>"` in the same breath. (The `>`-blocked
    caveat U7 deleted really is obsolete — `hands put notes.md --content "step 2
    > notes"` is allowed by the guard today.) Wording, not behaviour, but rule 6
    is the half of §19 no run has exercised.

11. **U2 strengthened four assertions and left their siblings loose.** The four
    the review named now pin the sentence
    (`tests/test_playbook.py:239-241,286-290`), and that is the unit's whole
    scope. The neighbouring `run` cases still assert bare substrings —
    `"send"`, `"auto_runs"` (twice, so `run with no auto_runs` and `run with an
    empty auto_runs` cannot be told apart), `"{k+1}"`, `"verdict"`
    (`tests/test_playbook.py:269-278`). They do fail at `34b4ede^`, so they are
    not vacuous, just not pinned. Worth the same treatment while the reason is
    fresh.

## Notes

**On blocker 1's severity.** It is a blocker because the protocol names "a claim
the disk contradicts" and the claim here is a safety claim in a security
control — but the exposure is narrow, not open. Every regressed command needs a
wrapper that puts `git` somewhere other than a segment's first word, and
`find -exec` is the only such wrapper the allow list still permits. The U6
sub-agent's own summary of it is the right one: `-exec` is the single remaining
arbitrary-exec vector inside the allow list, and every hole above runs through
it. Whether `find -exec` should be reachable at all is a bigger question than
this mission, and belongs to the architect.

**On blocker 3's provenance.** The false sentence was inherited, not invented:
`FINAL-REPORT-2.md` §3 said it, REVIEW-2 checked it and confirmed it, and the
human reinstalled between the two missions. Mission 3 carried it forward marked
"Carried forward from mission 2 unchanged", which is honest about its origin and
silent about its age. The lesson is narrow and cheap: a NOT PROVEN item that
asserts a fact about the machine has to be re-run, not re-copied — the check
here was one `grep ORIGINS` against the installed `spool.py`, the same command
REVIEW-2 used.

**The rest of §3 NOT PROVEN holds up.** Twelve items, and the ones I could check
are accurate: item 4 (the guard has never run as a real `PreToolUse` hook —
`main()`'s stdin/exit-2 wiring has no test) is true; item 5 flagged exactly the
premise that should-fix 2 now disproves; item 6 was verified true on disk by the
U7 sub-agent; item 7 anticipates should-fix 4; item 11 (`mypy` is not in
`./scripts/check`) is true — `scripts/check` is `uv sync`, ruff, pytest, two
`--help` calls; item 12 correctly says the general `-exec` hole is unchanged,
which is the ground blocker 1 stands on. Items 9 and 10 name real costs. This is
a strong NOT PROVEN section; blocker 3 is one stale sentence in it, not its
character.

**What the report over-claims, in one place each.** §1 U1: "what doctor probes
for is what the monitor sends" (should-fix 3). §1 U6: "`mutating_git()` scans
every `git` token in a segment, so `find . -exec git push \;` stays blocked as
the regex had it" — true of `push`, and the sentence is doing work it cannot do
for `remote add` (blocker 1). §2 U6: "the five new mutating cases already passed
under the old regex, which is what proves the fix did not weaken it" — five
cases prove five cases; six others it did not try went the other way. Each is
one clause, and each is the kind that a table of expectations in `tests/` would
have caught rather than a reviewer.

**Where the evidence was unusually good.** U2's commit body records the
worktree, the command and both count lines, and I reproduced them to the number:
old assertions against `34b4ede^` → `5 failed, 18 passed, 49 deselected`, new
assertions → `8 failed, 15 passed, 49 deselected`. U5's `MockTransport` test is
the real thing — the real `http_post` through a real `httpx` client with only
the transport replaced — which is precisely what review item 7 asked for and the
narrowest possible reading of it. U7's byte-for-byte gate asserts the prompt in
*both* the send reply and `hands show`, and the no-root-confinement decision is
sound rather than merely disclosed: the path is resolved client-side
(`cli.py:571-572`) and only the content crosses the socket, so unlike `put
--from` the daemon never reads a path it was handed.

**H-009 and H-010 were filed before the units that needed them**, which is the
procedure the mission brief asks for and the reason U6 did not have to stop. The
ledger's append-only convention (a stale `Status: open` above the current
`Status:` line) continues; as REVIEW-2 recorded, that is the convention, not a
defect.

**Bookkeeping.** Nine `meta:` commits, one per unit plus the plan and the
report, skipped per the protocol. Should-fix 6 of REVIEW-2 is properly closed:
`meta/journal.md:17-19` now cites `3c5d880` (reachable) and says the original
entry was amended; `857f6f2` still exists as an object but `git merge-base
--is-ancestor 857f6f2 origin/main` fails, as the note claims. Acceptance
criterion 2 — the one mission 2 could not satisfy — holds as amended:
`only_if_run_in` outside `DESIGN.md` and `meta/` is exactly
`src/hands/playbook.py:391,396`, `tests/test_playbook.py:235,241,286-290` and
`docs/PLAYBOOK.md:122`; `dispatch.sh` appears nowhere outside them.

## Per-commit verdicts

The ≤12-line sub-agent reports, verbatim, in the order the units landed.

---

sha 87bb7f8 — U1 status describes the deciding monitor (DESIGN §4 status row, §5, §19; review should-fix 2)
1. unit/sections: PASS. Brief (`meta/BUILDER-3-PROMPT.md:52-55`) asks for three cases; all three exist — ops branch `src/hands/cli.py:385-387`, zero `cli.py:388-390`, builtin `cli.py:392`; `_monitor_note` follows the same branch (`cli.py:394-404`). Closes should-fix 2 exactly (old unconditional `cli.py:366` line gone). Beyond the brief but small and in-spirit: `OPS_FLAGS` hoisted (`monitor.py:55-58`), `_external` argv now zip-built (`monitor.py:418-425`), `doctor.MONITOR_FLAGS = OPS_FLAGS` (`doctor.py:74-76`), `docs/INTEGRATION.md:175-180`.
2. test-first: PASS. Reverted the 4 product files to `87bb7f8^`, kept tests: `3 failed, 1 passed, 17 deselected in 0.26s`; `E KeyError: 'flags'` (test_daemon.py:412), `E AssertionError: assert 'for 40m' in '...'` (:371), `E AssertionError: assert 'off' in '...'` (:438). Load-bearing: `test_status_names_the_ops_script_and_its_flags_when_ops_decides`, `test_status_says_stall_detection_is_off_at_zero_minutes`, and the U6 test's new `"for 40m"`/`monitor["source"]=="builtin"`. Not load-bearing: `assert "--pids" not in out` (:373, passes pre-change). Restored with `git checkout 87bb7f8 -- .`; `git status --porcelain` empty.
3. scripts/check: green. `== ruff ==` / `All checks passed!`; `== pytest ==` / `523 passed in 26.76s`; `== cli smoke ==`; `check: green`.
4. conformance: PASS. §5's flag list is now single-sourced where the invocation is built and dispatch is exclusive (`monitor.py:365-368`), so "the script decides" is true on disk; §5's verbatim-block wording matches `_file`/`_read_blocks`; §19 bullet satisfied. Forbidden files: `git show --stat` touches only `docs/INTEGRATION.md`, `src/hands/{cli,doctor,monitor}.py`, `tests/test_daemon.py` — no `DESIGN.md`, no `meta/`.
5. NOT proven / concerns:
- Commit body overstates doctor: `doctor.py:232-241` still hardcodes `--pids/--transcript/--base` in the *probe* argv, so only the `--help` check and messages follow `OPS_FLAGS`; changing `OPS_FLAGS` silently desyncs the probe. No test pins probe argv against `OPS_FLAGS`.
- `cli.py:388-390`: `if not minutes` also fires when `stall_minutes` is absent/None, printing "monitor.stall_minutes = 0" for an unknown value. Negative is impossible (`config.py:418-419`), so only a malformed payload hits it; untested.
- `cli.py:386` `monitor.get("flags") or ()` degrades to "hands fills " (empty) if a daemon omits `flags`; untested. `flags` is a new `status --json` key with no doc outside the code (`monitor.py:327`).
- Body says the built-in rule prints "only for `source == builtin`"; code prints it for anything not `"ops"` — equivalent today (`monitor.py:312` yields only those two), but not what the body claims.
- Only `hands status` text was checked; I did not verify a real ops script run end-to-end (`tests/fake_monitor.py` predates this commit and is used only for config shape here).

---

sha 4fb1f35 — U2 "tests: make the four run/only_if_run_in assertions able to fail" (DESIGN §10 `run`/H-006, §4 status row; review should-fix 3, 8)
1. unit/sections: PASS — matches `meta/BUILDER-3-PROMPT.md:57-62` U2 verbatim (four `BAD_PLAYBOOKS` cases pin the sentence or `run = "{n+1}"`; alias asserted on aux depth 4) and REVIEW-2.md:48-58 (item 3) + :90-94 (item 8). `git show --stat` = `tests/test_daemon.py` (+9/-1), `tests/test_playbook.py` (+18/-4) only — **no product code**. New constants `tests/test_playbook.py:239-241` are copied verbatim from the two refusal sites `src/hands/playbook.py:236-237` and `:396`. Mission acceptance criterion holds: `only_if_run_in` outside `meta/`/`DESIGN.md` appears only at playbook.py:391,396, docs/PLAYBOOK.md:115, and these tests.
2. test-can-fail: PASS, both halves reproduced by me. (a) `git checkout 34b4ede^ -- src/ docs/` (34b4ede^ = 779b188), tests kept at 4fb1f35: `uv run pytest tests/test_playbook.py -k invalid_playbook --tb=no` → **`8 failed, 15 passed, 49 deselected in 0.13s`**, all four review-named cases among them (`[run that is not an expression]`, `[run naming a job field]`, `[only_if_run_in at all]`, `[only_if_run_in on its own]`), e.g. `assert 'only_if_run_in is gone; §10 spells the check as run = "{n+1}"' in '...rule 0: only_if_run_in belongs on a send, not on a stop'` (tests/test_playbook.py:303). With the OLD assertions (`git checkout b38c910 -- tests/test_playbook.py`, same old src): **`5 failed, 18 passed, 49 deselected in 0.27s`** — the three still-passing ones are exactly the three the review named. Both counts match the commit body's "5 failed, 18 passed" / "8 failed, 15 passed" exactly. (Whole file vs old src: `29 failed, 43 passed` — unrelated drift, not a claim.) Restored with `git checkout 4fb1f35 -- .`, tree clean.
   (b) alias: `sed -i '635s/.../"queue_capacity": 1,/' src/hands/daemon.py` → **RED**, `E assert 1 == 4` at `/tmp/rev3-4fb1f35/tests/test_daemon.py:366` — byte-identical to the body's claim. Extra check the body does not make: hardcoding `4` is *also* caught — `E assert 4 != 4` at `tests/test_daemon.py:368` via `aux["queue_capacity"] != builder["queue_capacity"]`. And the OLD (b38c910) assertion **passed** under the `1` hardcode (`1 passed, 20 deselected`), confirming review item 8 was real. Reverted; tree clean.
3. scripts/check: green — `== ruff ==` / `All checks passed!` / `== pytest ==` / `523 passed in 24.71s` / `== cli smoke ==` / `check: green`. Matches the body's "523 passed".
4. conformance: PASS — test-only; the §10 refusal messages and the §4 `queue_capacity` alias are unchanged in product code. Unit gate "confirm three of them fail against `34b4ede^` in a worktree and say so in the commit body" is genuinely met: the body records the command (`git worktree add /tmp/u2-pre 34b4ede^`, `pytest -k invalid_playbook`), both count lines, both FAILED lists, and the worktree removal — `git worktree list` shows no stale `/tmp/u2-pre`. Forbidden files: none — `DESIGN.md`, `meta/plan.md`, `meta/CHECKPOINT.md` all absent from `git show --stat 4fb1f35`.
5. NOT proven / concerns:
   - Pinning is real but not total: the assertion is still a substring (`tests/test_playbook.py:303`, `assert expected in str(caught.value)`), so the `where` prefix (path + rule index) and the trailing clause of the `only_if_run_in` message ("— an expression over the rule's own verdict groups, checked against [limits] auto_runs") stay unpinned. Both `only_if_run_in` cases assert the *same* constant, so nothing distinguishes the send-rule case from the stop-rule case beyond the refusal firing before `_check_keys`.
   - Out of the unit's four, but adjacent and untouched: the sibling `run` cases still assert bare substrings — `"send"`, `"auto_runs"` (twice: `run with no auto_runs` and `run with an empty auto_runs` share it and cannot be told apart), `"{k+1}"`, `"verdict"` (`tests/test_playbook.py:269-278`). They do fail at 34b4ede^, so not vacuous, just not sentence-pinned.
   - Cosmetic: `tests/test_daemon.py:362` calls aux depth 4 "the §6/§13 default", but the value comes from the fixture's explicit `queue_depth = 4` at `tests/harness.py:42`; the *default* path is covered elsewhere (`tests/test_config.py:140`). The test would be identical if the default changed.
   - The two expected-message constants are hand-copied rather than imported (correct — importing would make the test tautological), so they are a manual mirror of `playbook.py:236-237,396` that only the test run keeps honest.

---

sha 3cd2306 — U3 a pause over an already-stopped pipeline keeps the first reason (DESIGN §10, §11, §19, §4 pause/resume row; review should-fix 4)
1. unit/sections: PASS — matches the U3 brief and should-fix 4 (`hands pause` over an existing stop is a no-op that prints the reason, files no event/notification). Both gate tests exist: `tests/test_playbook.py:797` pause-after-rule-stop, `tests/test_playbook.py:822` pause-after-held, plus `:864` resume-after-rule-stop. Shared oracle `assert_pause_is_a_no_op` (`tests/test_playbook.py:806`) asserts reason, `stopped_at`, inbox ids and ntfy posts all unchanged; I probed it for vacuity (injected `assert notified` — still green, so the "no second notification" check is real).
2. test-first: PASS — `git checkout 3cd2306^ -- src/hands/{playbook,api,cli}.py docs/PLAYBOOK.md`, tests at 3cd2306: `FAILED tests/test_playbook.py::test_a_pause_after_a_rule_stop_keeps_the_first_reason` / `FAILED ...test_a_pause_after_a_held_job_stop_keeps_the_first_reason` / `FAILED ...test_a_resume_still_clears_a_stop_whatever_its_reason` — `3 failed, 72 deselected in 0.81s` (e.g. `AssertionError: assert 'a rule said so' in 'playbook ...'`). Reverting `cli.py` alone: `2 failed, 1 passed` — both `playbook.py:937-938` (the early return) and `cli.py:502-505` (the `already stopped:` line) are load-bearing. Restored with `git checkout 3cd2306 -- .`; `git status --short` empty.
3. scripts/check: green — `== ruff ==` / `All checks passed!` / `== pytest ==` / `526 passed in 33.31s` / `== cli smoke ==` / `check: green`.
4. conformance: PASS — `playbook.py:937` `if self.state.paused: return {**self.pipeline(), "already_stopped": True}` writes nothing (no `_save`, no `append_event`, no `_notify`), so `stop_reason`/`stopped_at` and `paused_by` survive and `pipeline()` (`playbook.py:996-999`) keeps reporting the original stop. Running-pipeline pause is untouched below the guard (`playbook.py:939-941` → `stop()` → `stop` event + notify); `tests/test_wake.py:153` (wakes `--for stop,held`, reason `paused by human`) and `tests/test_wake.py:416` (notifies like any other stop) still pass in the 526. Exit 0 is defensible: `cli.py:603-605` reserves non-zero for errors/`EXIT_TIMEOUT`, DESIGN §4/§19 specify no failure semantics for a no-op, and the output is not silent. Forbidden files: none touched — `git show --stat` lists only `docs/PLAYBOOK.md`, `src/hands/api.py`, `src/hands/cli.py`, `src/hands/playbook.py`, `tests/test_playbook.py`.
5. NOT proven / concerns:
   - `stop()`'s dedupe guard is unchanged (`playbook.py:907`, `paused and stop_reason == reason`), so the "first reason wins" rule holds for the pause direction only. §6's limit manager bypasses the engine's paused gate: `limits.py:429-437` → `daemon.py:449` → `playbook.stop(...)`, so a `max_resumes` exhaustion while the pipeline is already stopped still overwrites `stop_reason`/`stopped_at` and fires a second notification (plus its own `stop` event at `limits.py:431`). Same defect class as should-fix 4, outside §19's literal wording; untested either way.
   - `already_stopped` is consumed correctly (`cli.py:502`, `.get`, and `--json` emits it via `cli.py:604`), but it is emitted only when true and only by `pause`, so a driver must use `.get`; the key is in no doc (`docs/PLAYBOOK.md` describes the behaviour, not the JSON field) and `driver/CLAUDE.md:84` is unchanged.
   - Behaviour change not called out in the brief: a second `hands pause` over a hand pause used to print a bare pipeline block, now prints `already stopped: paused by human`. Covered by the docstring's "by an earlier pause", untested.
   - Not proven: nothing verifies the no-op against a stop recorded by a previous daemon process (state reloaded from disk); all three tests pause within one daemon lifetime.

---

sha 9cd6108 — U4 an empty `resume_line` is refused at load, not read as absent (DESIGN §6 "Limits", §13, §19; review should-fix 5)
1. unit/sections: PASS — commit body names U4/should-fix 5/§6/§13/§19; matches brief. `config.py:365-380` `_resume_line` raises at load naming both choices; `docs/INTEGRATION.md:60-64` says "`resume_line = ""` (or blanks only) is refused at load … Omit the key, or give a non-empty line". Gate: 4 new tests `tests/test_config.py:249-288`.
2. test-first: PASS — reverted `src/hands/config.py`+`docs/INTEGRATION.md` to 9cd6108^, tests at 9cd6108: `..............FFF....................  [100%]` / `E  Failed: DID NOT RAISE ConfigError` at `test_config.py:257`, `:270`, `:279` / `3 failed, 34 passed`. Load-bearing: `test_an_empty_resume_line_is_refused`, `test_a_whitespace_only_resume_line_is_refused`, `test_an_empty_resume_line_on_aux_is_refused_too`. `test_an_empty_ntfy_topic_is_still_legal` is green on both sides (a non-leak pin, not proof). Restored `git checkout 9cd6108 -- .`; `git status --short` empty.
3. scripts/check: red then green — run 1: `FAILED tests/test_daemon.py::test_status_names_the_ops_script_and_its_flags_when_ops_decides` / `assert '40' not in 'ops (/tmp/p...; watching 0'` / `1 failed, 529 passed`. NOT U4's: the assert `"40" not in out…` (`test_daemon.py:429`, from 87bb7f8 = U2/should-fix 2) matched the pytest tmpdir `pytest-1340`. Run 2: `530 passed in 27.79s` … `check: green`. Flaky-by-path, unrelated to this unit.
4. conformance: PASS — `ConfigError` raised inside `_role` via `config.py:357`, i.e. at load; message is `f"{path}: {where} resume_line must not be empty, got {value!r}; either omit the key entirely … or give a non-empty line"` — same `{path}: {where}` shape as every other error in the file, `where = "[roles.<name>]"` (`config.py:337`). Whitespace refused (`not value.strip()`, `:374`). `_opt_str` (`:409-412`) byte-identical to 9cd6108^; `ntfy_topic = ""` stays legal with a test (`test_config.py:285`). Forbidden files: none — `git show --stat` = `docs/INTEGRATION.md`, `src/hands/config.py`, `tests/test_config.py` only.
5. NOT proven / concerns:
   - Same silent-empty bug left behind on `ops.monitor_cmd`: `monitor_cmd = ""` with `ops.repo` set makes `monitor_path` = the ops repo dir itself (`config.py:117-119`, `Path('/x') / '' == Path('/x')`), so `MonitorSource` flips to `"ops"` (`monitor.py:312`) and builder jobs go unwatched with only "is not a file" (`monitor.py:559`). Exactly U4's rationale, untouched and untested.
   - `ntfy_topic = ""` is *pinned* legal but still silently folds to "no notifications" (`notify.py:249`); only `hands doctor` surfaces it (`doctor.py:126`). Deliberate per the brief, but the asymmetry with `resume_line` is undocumented.
   - `RoleConfig.resume_behaviour:99` `if self.resume_line` is not dead (aux-with-a-line branch is reachable) but is now truthiness where `resume_prompt:93` uses `is None`; harmless only because `""` is now impossible. No test covers the aux "(resume_line is set, but only the builder uses it)" string.
   - Error surfacing verified by reading only, not by running: `handsd` prints `handsd: <msg>` exit 1 (`daemon.py:817-820`); `hands doctor` never reaches `_doctor` because `load_config` is inside the same `try` (`cli.py:568` → `cli.py:601`), so a bad `resume_line` makes doctor unusable rather than reported as a failed check — consistent with all other config errors, but it means the one command meant to explain config problems cannot explain this one.
   - The call-site comment `config.py:355-356` says "Empty is refused above (§19)"; `_resume_line` is defined *below* (`:365`). Cosmetic.

---

sha 861097f — U5 `hands notify --test` prints the HTTP status on the failure path too (DESIGN §4 notify row, §11, §19; review should-fix 7)
1. unit/sections: PASS — commit body names U5, §4/§11/§19 and should-fix 7. Brief met: `http_post` drops `raise_for_status()` and returns any code (`src/hands/notify.py:117-142`), `accepted()` judges 2xx (`:146-155`), `_notify` returns `0 if result["delivered"] else 1` (`src/hands/cli.py:643-647`) and prints `ntfy {status}  {url}` on both paths (`:649-663`). MockTransport test is REAL: `tests/test_wake.py:747-775` calls the real `http_post` with `transport=httpx.MockTransport(...)` at 200/202/403/404/500 and asserts httpx's own `status_code`, path, `Title`, body; `:777-791` runs the real `send_test` over `partial(http_post, transport=refusing_transport(403))` — only httpx's transport replaced, no monkeypatch of `http_post`.
2. test-first: PASS — reverted only README.md, docs/INTEGRATION.md, src/hands/{api,cli,notify}.py to `861097f^`, tests kept: `9 failed, 41 passed in 2.79s`; `FAILED test_http_post_answers_with_the_status_httpx_saw[200|202|403|404|500]` (`TypeError: http_post() got an unexpected keyword argument 'transport'`), `FAILED test_send_test_reports_a_403_as_a_status_not_a_failure`, `FAILED test_a_refused_publish_prints_the_code_and_exits_nonzero` (`assert 0 == 1`), `FAILED test_a_refused_publish_carries_the_status_in_json` (`assert 0 == 1`), `FAILED test_a_background_notification_ntfy_refuses_still_fails` (`assert [] == ['notify']`). Restored with `git checkout 861097f -- .`, `git status` clean. Load-bearing: those 9 (5 parametrized + 4).
3. scripts/check: GREEN — `== ruff ==` / `All checks passed!` / `== pytest ==` / `539 passed in 32.00s` / `== cli smoke ==` / `check: green`.
4. conformance: PASS — §11 intact on disk: `Notifier._publish` reads the status and routes a non-2xx to `_failed(note, f"ntfy answered {status}")`, the same branch as an exception, which logs, appends a `notify` inbox event with `delivered: False` and returns False without raising (`src/hands/notify.py:291-321`); driven by `tests/test_wake.py:824-843` (status 500 → one `notify` event, `delivered is False`, `"500" in error`). Transport error: `send_test` still raises `NotifyError` with the `<url> did not take the message: <type>: <detail>` shape (`notify.py:192-196`), exit 1 via `cli.py:601-603`, pinned by `tests/test_wake.py:725-744` which also asserts no `ntfy ` line is printed. Crash path also funnels through `Notifier.deliver` (`src/hands/daemon.py:841-848`), so no caller of `http_post` outside `send_test`/`_publish` relied on `raise_for_status()`. Forbidden files: none — `git show --stat` = README.md, docs/INTEGRATION.md, src/hands/{api,cli,notify}.py, tests/test_wake.py; DESIGN.md, meta/plan.md, meta/CHECKPOINT.md untouched.
5. NOT proven / concerns:
   - `accepted()` returns True for any non-int (`notify.py:152-154`): a "no opinion" carve-out that exists to keep the legacy `Posts` double, which returns `None` (`tests/test_wake.py:226-234`), green. A real transport regression returning `None` would count as delivered — product code shaped by a test double.
   - `Api.notify`'s failure shape DID change (a 403 now returns `delivered: false` instead of raising `ApiError`; documented at `src/hands/api.py:658-662`) and is UNTESTED — the only Api test uses `StatusPosts(status=200)` (`tests/test_wake.py:861-871`).
   - Socket/§9 face left inconsistent: the generic client path returns 0 unconditionally (`src/hands/cli.py:604-605`) and `_render` has no `notify` branch (`:480-520`), so a socket caller of `notify` would get exit 0 and a raw dict for a 403 where the CLI exits 1. Not reachable from today's CLI (`cli.py:576-579` intercepts before the socket), so latent, not live.
   - No single test proves the CLI exits 1 on a *real* httpx 403: the CLI 403/404 tests monkeypatch `StatusPosts` (`tests/test_wake.py:801,814`) and the real-httpx 403 test stops at `send_test` (`:789`). The two halves meet only by inspection.
   - `tests/test_wake.py:725-744` (transport error) passes on the pre-change code too — a regression guard, not test-first evidence for this unit.
   - README.md and docs/INTEGRATION.md claims (`ntfy 403 … exits 1`) are gated by no test in this repo; verified by reading only.

---

sha ecdb0f3 — U6 the mutating-git check applies to the git subcommand position only (DESIGN §19 guard bullet, §12 driver kit)
1. unit/sections: PASS — every brief item present: regex dropped from `FORBIDDEN_PATTERNS` (`driver/hooks/bash_guard.py:62` old line gone) and re-homed as `MUTATING_GIT_SUBCOMMANDS` (:39-43) + `GIT_GLOBAL_FLAGS_WITH_ARG` (:46) read via `git_subcommand()` (:155-171)/`mutating_git()` (:174-184), called at `check()` :201; 10 SELFTEST cases added (:266-277, table 52→62); `tests/test_bash_guard.py` loads by path (:22-27) and parametrizes every case (:40-46); `driver/settings.json` drops `"MultiEdit"`; commit body names unit + §19/§12.
2. test-first: PARTIAL (PASS for settings.json, FAIL as proof of the guard fix). Red run (product at ecdb0f3^, `tests/` at ecdb0f3): `63 items, 1 failed` — only `tests/test_docs.py::test_the_driver_denies_every_writing_tool` — `> assert "MultiEdit" not in deny` / `E AssertionError: assert 'MultiEdit' not in ['Edit', 'Write', 'MultiEdit', 'NotebookEdit', ...]  tests/test_docs.py:121`. All 52 `test_selftest_case` params were GREEN against the unfixed guard. Load-bearing: only that one docs test. Does NOT prove the guard fix: `SELFTEST` lives in the product file, so reverting it reverted the 10 new cases with it; `tests/test_bash_guard.py` asserts nothing of its own (it re-runs whatever table ships), so it cannot go red on a guard behavior the author did not already encode. I re-created the red manually — the 10 new cases against the ecdb0f3^ guard: `new-cases: 5/10 ok`, e.g. `FAIL expected allow: git -C ./repo rev-parse 8448b6f^{commit}  -> mutating git: ...`, same for `rev-parse --verify HEAD^{commit}`, `show 861097f^{commit} --stat`, `log --grep=commit -5`, `log --oneline --grep=push -20`; the 5 adversarial mutating cases were already blocked, so they add no red. Restored with `git checkout ecdb0f3 -- .`, `git status --porcelain` empty.
3. scripts/check + selftest: green. `603 passed in 31.53s` / `== cli smoke ==` / `check: green`; `python3 driver/hooks/bash_guard.py --selftest` → `selftest: 62/62 ok`, `exit=0`.
4. conformance + adversarial probe: FAIL (one real, bounded regression). Correct: all 5 new reads ALLOW; blocked — `git commit -m x`, `git -C ./repo push`, `git -c x=y commit`, `git --git-dir=./repo/.git push origin main`, `find . -exec git push \;`, plus my own `git --exec-path=/x push`, `git --exec-path /x push`, `git -C x -c y=z commit`, `GIT_DIR=x git commit`, `git  commit  -m x`, `ls && git push`, `ls ; git push`, `echo $(git push)`, `` echo `git push` ``, `ls | git commit`, `GIT commit`, `git COMMIT -m x`, `/usr/bin/git push`, `find . -exec /usr/bin/git push \;`, `\git push`, `git -c alias.p=push p`, `git --no-pager commit -m x`, `git -P commit`, `git -C x -C y commit`, `git log ...; git commit --amend`. **HOLE (regression vs ecdb0f3^):** the scan only reads the first-level subcommand, so a mutating *second-level* verb behind an allowed first word now passes where the old regex blocked it — NEW=ALLOW/OLD=block for `find . -exec git remote add origin https://x/y.git \;`, `find . -exec git notes add -m x HEAD \;`, `find . -exec git submodule add https://x/y.git \;`, `find . -exec git bisect reset \;`, `find . -exec git sparse-checkout init \;`, `find . -exec git update-index --add x \;`. So the commit body's "Every case the old guard blocked is still blocked" is false. Pre-existing in both guards (not caused here, still open): `find . -exec git update-ref|gc|branch -D|symbolic-ref|reflog expire|remote set-url ... \;` and `git -C ./repo fetch origin +refs/x:refs/x`. `driver/settings.json` deny (Edit, Write, NotebookEdit, `Bash(git push:*)`, …) and `tests/test_docs.py:117-121` agree; H-010 Status (meta/findings/FINDINGS.md:383-386) records that §12 line 503 still lists MultiEdit while the kit no longer does — design/kit disagreement left for the architect, as the brief directs. Forbidden files: none touched — `git show --stat` lists only `driver/hooks/bash_guard.py`, `driver/settings.json`, `meta/findings/FINDINGS.md`, `tests/test_bash_guard.py`, `tests/test_docs.py`; DESIGN.md, meta/plan.md, meta/CHECKPOINT.md untouched.
5. NOT proven / concerns:
- Should-fix: `mutating_git()` (`driver/hooks/bash_guard.py:180-184`) checks one token deep; six `find -exec` commands the old guard refused now pass (list above). Fix shape: when the resolved subcommand is `remote|notes|submodule|bisect|sparse-checkout|update-index|reflog|worktree`-class, read the next non-flag word too, or (better) apply `ALLOWED_GIT_SUBCOMMANDS` to *every* git token, not only a segment's first word.
- The guard's test file is self-referential: it re-runs the product file's own table, so it cannot fail on an unanticipated command. The "self-test lives in tests/" §19 bullet is satisfied in letter; an independent expectation table in `tests/` would be the real gate. `assert len(guard.SELFTEST) >= 50` (tests/test_bash_guard.py:35) would not notice 12 cases being deleted.
- Not proven: that the hook behaves identically under Claude Code's real PreToolUse JSON path (only `check()` is exercised); that Claude Code 2.1.x has no `MultiEdit` tool (H-010's premise is asserted, never demonstrated in-repo); that `find`/`-exec` should be allowed at all — it is the single remaining arbitrary-exec vector inside the allow list and every hole above runs through it.

---

sha 45400e8 — U7 `hands send --prompt-file PATH` — the prompt travels as a file (DESIGN §4 `send` row, §12 rule 6, §19 bullet 1)
1. unit/sections: PASS — every brief item on disk: UTF-8 read + byte-for-byte send `src/hands/cli.py:701-726`; `Path(where).expanduser()`, no roots check, deliberate per docstring `cli.py:709-715`; 3-way exclusivity checked explicitly `cli.py:729-748`; rule 6 rewritten `driver/CLAUDE.md:40-47` + command list `:77-80` + kickoff `:99-107`; `docs/INTEGRATION.md:206-223`; 3 guard cases `driver/hooks/bash_guard.py:297-300`; README `:92-93`.
2. test-first: PASS — reverted the 5 non-test files to `45400e8^`, kept `tests/`, `uv run pytest tests/test_daemon.py tests/test_docs.py tests/test_bash_guard.py -q` → 12 FAILED, verbatim: `FAILED tests/test_daemon.py::test_send_reads_the_prompt_from_a_file_byte_for_byte` / `test_a_prompt_file_is_sent_with_its_trailing_newline` / `test_send_reads_a_prompt_file_outside_the_allowed_roots` / `test_send_refuses_a_prompt_file_together_with_stdin_or_a_prompt` / `test_send_with_no_prompt_at_all_names_every_route` / `test_send_refuses_a_missing_prompt_file` / `test_send_refuses_a_directory_as_a_prompt_file` / `test_send_refuses_a_prompt_file_that_is_not_utf8` / `test_send_refuses_an_empty_prompt_file` / `test_send_help_lists_the_prompt_file_route`, `FAILED tests/test_docs.py::test_the_driver_kit_sends_prompts_as_files - AssertionError: driver/CLAUDE.md must route prompts through --prompt-file`, `FAILED tests/test_bash_guard.py::test_the_table_covers_the_prompt_file_route - AssertionError: the guard's SELFTEST has no 'hands send --prompt-file' case`. Load-bearing: the first (the §4 gate), the roots one, the two doc guards. Restored with `git checkout 45400e8 -- .`, `git status --porcelain` = 0 lines.
3. scripts/check: green — `== ruff ==` / `All checks passed!` / `== pytest ==` / `618 passed in 31.76s` / `== cli smoke ==` / `check: green`, exit 0. `uv run hands send --help` shows `[--prompt-file PATH]` in usage and `--prompt-file PATH  read the prompt from this file (UTF-8), sent byte for byte; §4's normal route for prose…`.
4. conformance: PASS — unit gate met: `tests/test_daemon.py:266-269` `VERBATIM` holds `>`, `(`, `"`, `'` and an interior `\n`; `:292-293` asserts `job["prompt"] == VERBATIM` **and** `(await ok("show", job["id"]))["prompt"] == VERBATIM`. Trailing newline not stripped: decided in the commit body, docstring `cli.py:705-706`, INTEGRATION.md:209, pinned by `test_daemon.py:297-307`. No-root-confinement: docstring `cli.py:709-715` + INTEGRATION.md:216-221 + `test_daemon.py:311-324`. Not a security regression and the daemon gains nothing: the path is resolved and read entirely client-side (`cli.py:571-572` overwrites `args.prompt` before any socket call) and only the *content* is marshalled (`cli.py:261-268` `"prompt": a.prompt`); `grep -rn prompt_file src/` matches only `cli.py`, so no path ever reaches the daemon — contrast `files.py:68-70,76-77` where `put --from` is root-confined precisely because *the daemon* does that read. Forbidden files: none — `git show --stat` touches only README.md, docs/INTEGRATION.md, driver/CLAUDE.md, driver/hooks/bash_guard.py, src/hands/cli.py, tests/{test_bash_guard,test_daemon,test_docs}.py.
5. NOT proven / concerns:
- Report NOT-PROVEN 6 **verified true on disk**: driver cannot write (`driver/settings.json:4-6` denies Edit/Write/NotebookEdit, `:14-18` denies rm/mv/cp/touch/tee) and `put --from` is root-confined (`files.py:76-77`). Not a blocker — rule 6 states the constraint itself (`driver/CLAUDE.md:45-47,105-107`) — but rule 6 is unusable for any prompt the human/architect has not already placed on disk, and no run has exercised it.
- Rule 6 says "Nothing with shell metacharacters goes on a command line" while prescribing `hands put <path> --content "<text>"` in the same breath (`driver/CLAUDE.md:42-44`) — self-contradictory for content containing `>`. The old `>`-blocked caveat it deleted is genuinely obsolete (I ran `check('hands put notes.md --content "step 2 > notes"')` → `None`, allowed), so this is wording, not behaviour.
- No client-side size cap on `--prompt-file`: `MAX_PROMPT_BYTES` (10 MB) is only enforced at run time (`runner.py:283-285`), and the daemon socket reader caps at `MAX_PROMPT_BYTES + 1 MiB` (`daemon.py:63,166`). Unlike missing/dir/non-UTF-8/empty, an oversized file gets no refusal naming the path; the >11 MiB socket path is untested.
- `test_send_with_no_prompt_at_all_names_every_route` / `..._together_with_stdin_or_a_prompt` assert `"prompt" in err`, which `--prompt-file` satisfies trivially — the positional route's name is not actually pinned (the real message says "a prompt argument").
