# FINAL REPORT — mission 3 (close the review)

Mission: `meta/BUILDER-3-PROMPT.md`. Base `fa409e6` (`plan: mission 3 kit
(DESIGN v3.2)`), green before U0: ruff clean, 521 passed, cli smoke.
Tip `45400e8`, green: ruff clean, **618 passed**, cli smoke, and
`python3 driver/hooks/bash_guard.py --selftest` → `selftest: 65/65 ok`.

Nine units, all `[x]`, none yielded, none blocked, no order deviation. One
sub-agent per product unit, each in one commit with a `meta:` bookkeeping
commit after it. `DESIGN.md` was not edited by anyone.

---

## 1. What changed, by unit

| Unit | sha | One line |
|---|---|---|
| U0 | `efc501b` + `4338af5` | plan, checkpoint, journal sha fix, memos H-009 and H-010 |
| U1 | `87bb7f8` | `hands status` describes whichever monitor is deciding |
| U2 | `4fb1f35` | the four `run`/`only_if_run_in` assertions, and the alias assertion, made able to fail |
| U3 | `3cd2306` | a pause over an already-stopped pipeline keeps the first reason |
| U4 | `9cd6108` | an empty `resume_line` is refused at load |
| U5 | `861097f` | `hands notify --test` prints the HTTP status on the failure path too |
| U6 | `ecdb0f3` | the mutating-git check applies to the git subcommand position only; the guard is in `tests/` |
| U7 | `45400e8` | `hands send --prompt-file PATH` |
| U8 | this file | the report, then the verdict line |

**U0 `efc501b`, `4338af5` — meta only.** `meta/plan.md` and
`meta/CHECKPOINT.md` reset for mission 3. `meta/journal.md:17` cited
`857f6f2`, a commit that is unreachable from `main` because the mission-2 U0
commit named its own sha and was then amended; it now cites the reachable
`3c5d880` and says the original entry was amended (should-fix 6). Two
design-side memos were filed ahead of the units that would otherwise have had
to stop on them: **H-009** (DESIGN.md:258's `hands jobs` example omits
`--origin`, carried from REVIEW-2's Notes) and **H-010** (DESIGN §12 requires
`MultiEdit` in the driver deny list, but Claude Code 2.1.x has no such tool).
Both are for the architect; builders do not edit `DESIGN.md`. The journal line
is a second commit on purpose — a journal must never name a sha that does not
exist yet, which is the mistake should-fix 6 was filed about.

**U1 `87bb7f8` — status describes the deciding monitor (§4 `status`, §5, §19).**
`cli.py` printed `stall = no progress and no liveness for {stall_minutes}m`
unconditionally, so an `[ops]` install read as if `monitor.stall_minutes` were
deciding when the ops script holds the rule and never receives that number,
and `stall_minutes = 0` (detection off) printed "for 0m". `monitor.py` now has
`OPS_FLAGS = ("--pids", "--transcript", "--base")` as the one list of what §5
gives the ops script: `_external` builds its argv from it, `status()` reports
it as `flags` (`None` for the built-in), and `doctor.py`'s `MONITOR_FLAGS` is
that same list, so what doctor probes for is what the monitor sends. `cli.py`
branches on `source`: built-in prints the stall rule, `ops` prints the script
path plus the three flags, `stall_minutes = 0` says detection is off.
`docs/INTEGRATION.md` §7 records all three forms.

**U2 `4fb1f35` — tests that can fail (should-fix 3 and 8).** Test-only; no
product change. The four `BAD_PLAYBOOKS` cases now pin the sentence
(`run takes one named group of the rule's verdict regex…` /
`only_if_run_in is gone; §10 spells the check as run = "{n+1}"`) through two
named constants, not the substring `run` that `only_if_run_in` contains. The
`queue_capacity` alias assertion moved to aux, whose `queue_depth` is 4, so a
hardcoded `"queue_capacity": 1` no longer passes.

**U3 `3cd2306` — pause keeps the first reason (should-fix 4, §10, §11, §19).**
`pause()` now returns early with `already_stopped: true` when the pipeline is
already stopped, instead of going through `stop()`'s dedupe guard
(`paused and stop_reason == reason`) and overwriting the reason with `paused by
human`. No second `stop` event, no second notification, `hands pipeline` keeps
the original stop, and the CLI prints `already stopped: <reason>` above the
pipeline block so the human learns why. The no-op **exits 0**: §19 calls it a
no-op and the brief asks for the reason printed, and nothing in DESIGN asks for
a refusal. A pause of a *running* pipeline is unchanged — it still files its
`stop` event and still wakes `hands wait --for stop,held`.

**U4 `9cd6108` — empty `resume_line` refused (should-fix 5, §6, §13, §19).**
`config.py` read the key as `_opt_str(...) or None`, folding `""` into "key
absent", which since `8448b6f` means "a limit resume re-sends the limited job's
own prompt". A new `_resume_line()` raises `ConfigError` with the file and
`[roles.<r>]` context every other error in that file carries, naming both valid
choices. Whitespace-only is refused too (`not value.strip()`): a line of blanks
is no more a prompt than `""`. `_opt_str` itself is unchanged, so `ntfy_topic =
""` stays legal.

**U5 `861097f` — notify status on the failure path (should-fix 7, §4, §11, §19).**
`http_post` no longer calls `raise_for_status()`; it returns whatever code came
back and takes a `transport=` seam. A new `accepted()` judges 2xx. `hands notify
--test` prints `ntfy <code> <url>` either way and exits 1 on a non-2xx, with
`status`/`delivered` in the `--json` form; a transport error (no response, so no
code) keeps its old message shape. `raise_for_status` *was* load-bearing for
§11's ordinary daemon notifications, so the check moved into
`Notifier._publish`: a 500 there is still a failure, inboxed as `delivered:
false, error: "ntfy answered 500"`, and still never raised into a job.

**U6 `ecdb0f3` — guard fix and guard tests (§19, §12).** The mutating-git regex
matched the verbs anywhere in the command, so `git -C ./repo rev-parse
<sha>^{commit}` and `git log --grep=commit` — both read-only — were refused.
The list is now `MUTATING_GIT_SUBCOMMANDS`, read at the resolved subcommand via
a shared `git_subcommand()` that skips `-C`, `-c` and the other value-taking
global flags, which is why `git -c x=y commit` still blocks; `mutating_git()`
scans every `git` token in a segment, so `find . -exec git push \;` stays
blocked as the regex had it. `SELFTEST` gained 10 cases (5 newly-allowed
read-only, 5 adversarial mutating). New `tests/test_bash_guard.py` loads the
hook by path and runs every `SELFTEST` case as its own parametrized test, so
`./scripts/check` now covers the guard. `driver/settings.json` dropped
`"MultiEdit"` and `tests/test_docs.py` asserts its absence, citing H-010.

**U7 `45400e8` — `hands send --prompt-file PATH` (§4, §12, §19).** The CLI reads
the file as UTF-8 and sends it byte for byte; it is one of three exclusive
routes with `--stdin` and the positional prompt, and the refusal names all
three. A trailing newline is **not** stripped — §4's word is "byte for byte",
and `--stdin` already sends what it was piped. An empty or all-whitespace file
is refused client-side. The read deliberately skips `files.py`'s allowed roots:
the CLI runs as the human, not as the daemon, and that is stated in
`docs/INTEGRATION.md` so a later reader does not take it for an oversight.
`driver/CLAUDE.md` rule 6 is now the design's wording (prompts and long content
travel as files), the driver's command list and kickoff example use
`--prompt-file`, and the guard's `SELFTEST` carries a `--prompt-file` case.

---

## 2. What the tests prove

521 tests at the base, **618** at the tip; +97. Every product unit was
confirmed test-first: the new assertions were run against the unfixed code and
seen to fail before the fix landed. The load-bearing evidence, unit by unit:

- **U1.** Three status forms end to end over the real socket:
  `test_status_names_the_ops_script_and_its_flags_when_ops_decides`,
  `test_status_says_stall_detection_is_off_at_zero_minutes`, and the U6-era
  test extended for the built-in case. Reverting only `cli.py` reddens all
  three.
- **U2.** In a worktree at `34b4ede^` the old assertions gave `5 failed, 18
  passed` — reproducing the review's claim that three of the four still passed
  against the code that predates the behaviour — and the strengthened file
  gives `8 failed, 15 passed`: all four now fail there. None had to be left
  unpinned. For the alias, hardcoding `"queue_capacity": 1` in `daemon.py`
  fails the test with `assert 1 == 4`.
- **U3.** `test_a_pause_after_a_rule_stop_keeps_the_first_reason` and
  `test_a_pause_after_a_held_job_stop_keeps_the_first_reason` each assert all
  four of: reason unchanged, `stopped_at` unchanged, no new inbox event, no new
  notification — plus exit 0 and the printed reason.
  `test_a_resume_still_clears_a_stop_whatever_its_reason` pins the unpause
  path, and `tests/test_wake.py::test_wait_for_stop_wakes_on_a_hand_pause` is
  still green, so the wake path did not regress.
- **U4.** Four config tests: empty on builder, whitespace-only, empty on aux,
  and `ntfy_topic = ""` still legal (the refusal did not leak into the shared
  helper). `test_every_optional_key_has_a_default` and
  `test_full_config_loads_every_field` are untouched and green.
- **U5.** The one the review asked for: the real `http_post` over a real
  `httpx.MockTransport` at 200/202/403/404/500, so the `-> int` return is
  verified against httpx and not against a monkeypatch; plus the real
  `send_test` over the real `http_post` at 403, the CLI's 403 line and exit 1,
  the 404 `--json` shape, the daemon path's 500 inboxed as failed, and the
  transport-error case pinned to print no code.
- **U6.** `tests/test_bash_guard.py` runs all 65 `SELFTEST` cases as named
  tests, asserts the table is non-empty and carries both verdicts, and asserts
  `selftest() == 0`. Against the unfixed guard the five read-only cases failed
  with `mutating git` (`selftest: 57/62 ok`); the five new mutating cases
  already passed under the old regex, which is what proves the fix did not
  weaken it. Verified independently by the orchestrator at the tip: `git -C
  ./repo rev-parse abc123^{commit}` and `git log --grep=commit` → ALLOWED;
  `git commit -m x`, `git -C ./repo push` and `git -c x=y commit` → `mutating
  git`.
- **U7.** The gate test builds `Run step 2 (the "hard" one) > notes.md\nIt's
  prose, not a redirection: keep every byte.` — `>`, `(`, both quotes, an
  interior newline — writes it to a file, sends it over the real socket and
  asserts the prompt in the send reply *and* in `hands show` equals it exactly.
  Ten more cover the trailing newline, a path outside every allowed root, all
  three mutual-exclusion pairs and the none-given case, a missing file, a
  directory, non-UTF-8 bytes, an empty file, and `send --help`.

---

## 3. NOT PROVEN

1. **Nothing in missions 2 or 3 has ever run outside the test suite.** The
   installed daemon is still the mission-1 build, as REVIEW-2 verified against
   the installed `spool.py`. `uv tool install --force ~/git/hands` is what
   would put this mission's code under a real run. Carried forward from
   mission 2 unchanged, and still the largest gap in the whole project.
2. **No request has ever left the machine.** U5 proves the status plumbing
   against httpx's own `Response.status_code` through `MockTransport`, which is
   off-network by construction. `hands notify --test` against a live ntfy topic
   is still unrun, so delivery is unproven. Carried forward from mission 2.
3. **The ops monitor path is still only exercised against
   `tests/fake_monitor.py`.** U1's ops status line has never been printed
   against a real `watch_monitor.sh` install; no real ops script exists here.
   `hands doctor`'s flag probe was not re-run live after the `MONITOR_FLAGS`
   aliasing — only its own tests cover it.
4. **The guard has never run as an actual Claude Code `PreToolUse` hook in this
   mission.** `tests/test_bash_guard.py` proves `check()`'s verdicts; the
   `main()` stdin/exit-2 wiring has no test, and Claude Code's own hook
   invocation is not exercised by anything.
5. **H-010's premise was not re-verified.** That Claude Code 2.1.x has no
   `MultiEdit` tool is taken from the mission brief and the memo; the start-up
   warning it describes was not observed in this session. If the premise is
   wrong, U6 removed a live deny rule.
6. **The driver kit's rewritten instructions have never driven a session.**
   `driver/CLAUDE.md` rule 6 now tells the driver to send prompts as files, but
   the driver cannot write files, and `hands put --from FILE` still requires
   its source under the allowed roots — so in practice a prompt file must
   already exist in `CLONE` or have been placed by the human. That is
   documented, not enforced, and no driver run has tested whether it is
   workable.
7. **U3's fix is scoped to `pause()` only.** `stop()`'s dedupe guard is
   untouched, so a *rule* or *limit* stop over a different existing stop still
   overwrites the reason. That is unreachable for rules (none fire while
   paused) but is not proven for §6's limit-manager `on_stop` seam.
   `already_stopped` is a new key on the `pause` JSON result; no consumer other
   than the CLI renderer was checked against it.
8. **U5 changed `Api.notify`'s failure shape.** It now returns a refusal
   instead of raising `ApiError`; no socket client exercises that path, so only
   the direct-API shape is tested.
9. **U2's strengthened assertions couple the tests to prose.** They pin
   `playbook.py`'s current message wording, so a reword breaks them. That is
   the intended trade — an assertion that cannot fail is worse — but it is a
   cost, and it is recorded here rather than discovered later.
10. **U4 drove only `load_config`.** No test asserts how the new `ConfigError`
    surfaces through `handsd` startup or `hands doctor`; both merely propagate
    it. `RoleConfig.resume_behaviour` still has an `if self.resume_line`
    truthiness branch that `""` can no longer reach.
11. **`mypy` is not in `./scripts/check`.** The gate is ruff + pytest + a CLI
    smoke test, so no type checker has seen any of this mission's annotations.
12. **The guard's general `-exec` hole is unchanged.** `find . -exec git push
    \;` is blocked because `mutating_git()` scans every `git` token, but
    `-exec` with a non-git verb is as permitted as it was before U6.

---

## 4. Review items

`meta/reviews/REVIEW-2.md`, `VERDICT: review mission 2 blockers=0
should-fix=8`.

| # | Item | Status |
|---|---|---|
| 1 | Acceptance check 2 of the mission-2 brief is self-contradictory | **closed** — not applicable to a builder: the fix was the architect's, and `meta/BUILDER-3-PROMPT.md:114` now reads "`only_if_run_in` appears only at the refusal site … its tests … and `docs/PLAYBOOK.md`'s migration note". Verified below; it holds. |
| 2 | `hands status` states the built-in stall rule even on an ops install | **closed `87bb7f8`** (U1) |
| 3 | Four `BAD_PLAYBOOKS` assertions cannot fail | **closed `4fb1f35`** (U2) |
| 4 | `hands pause` over an already-stopped pipeline rewrites the reason | **closed `3cd2306`** (U3) |
| 5 | `resume_line = ""` is silently "re-send the prompt" | **closed `9cd6108`** (U4) |
| 6 | `meta/journal.md:17` cites an unreachable sha | **closed `efc501b`** (U0) |
| 7 | `hands notify --test` only ever prints a 2xx | **closed `861097f`** (U5) |
| 8 | The `queue_capacity` alias assertion cannot catch a hardcoded value | **closed `4fb1f35`** (U2) |

The review's **Notes** were not left on the floor either: the design-side
staleness it flagged for a memo is now **H-009**, and its observation that
`pipeline.resumed` is a conformant new event kind needed no action.

Two units close no review item: **U6** and **U7** are DESIGN §19 work.

---

## 5. Acceptance, checked

1. **`./scripts/check` green on the pushed tip.** At `45400e8`: `ruff … All
   checks passed!`, `618 passed`, `== cli smoke ==`, `check: green`.
2. **`only_if_run_in` appears only at the refusal site, its tests, and
   `docs/PLAYBOOK.md`'s migration note; `dispatch.sh` only in `DESIGN.md` and
   `meta/`.** `git grep -n only_if_run_in` outside `DESIGN.md` and `meta/`
   returns exactly `src/hands/playbook.py:391,396` (the refusal),
   `tests/test_playbook.py:235,241,286,288,289,290` (the constant, its comment
   and the two cases that pin it) and `docs/PLAYBOOK.md:122` (the migration
   note). `git grep -n 'dispatch\.sh'` returns only `DESIGN.md` (§14/§15/§17/§18
   history) and `meta/`. **Holds** — the criterion the last mission could not
   satisfy is satisfiable as amended, and is satisfied.
3. **`hands send --help` lists `--prompt-file`; `tests/test_bash_guard.py`
   exists and is collected by pytest.** `uv run hands send --help` shows
   `[--prompt-file PATH]` in the usage line and `the prompt; or
   --prompt-file/--stdin` on the positional. `uv run pytest
   tests/test_bash_guard.py -q` collects and passes 68 tests.
4. **`meta/FINAL-REPORT-3.md` exists with a non-empty NOT PROVEN section and
   the review-items table.** §3 above has twelve entries; §4 is the table.

---

## 6. For the architect

- **H-009** (open) — DESIGN.md:258's `hands jobs` example omits `--origin`,
  which §4's table at :159 requires and `a67c4b0` implemented.
- **H-010** (open) — DESIGN §12 line 503 requires `MultiEdit` in the driver
  deny list; Claude Code 2.1.x has no such tool, so the rule is inert and warns
  at session start. U6 dropped it from the kit on the mission brief's
  instruction, so the kit and §12 now disagree until §12 is amended. This is
  the one place mission 3 knowingly diverged from `DESIGN.md`, and it did so on
  the architect's written instruction with the memo filed first.
- **H-001** remains the only mission-1 finding still open: it needs a capture
  from a dotted `cwd`, which is an observation to make, not a change to write.
- The largest thing this mission did **not** do is item 1 of NOT PROVEN. Three
  missions of code have now been gated only by the test suite. A mission whose
  first unit is `uv tool install --force ~/git/hands` and whose gate is a real
  dispatch would be worth more than any further unit of code.
