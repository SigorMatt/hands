# FINAL-REPORT-5 — hands mission 5: review 4 and the daemon's memory

Mission: `meta/BUILDER-5-PROMPT.md`. Design: `DESIGN.md` v3.4, §21.
Review closed: `meta/reviews/REVIEW-4.md`, `VERDICT: review mission 4
blockers=2 should-fix=8`.

Base `6c9440d` (`plan: mission 5 kit (DESIGN v3.4, backlog)`) — green here
before U0: ruff clean, **726 passed**, cli smoke, `check: green`.
Tip `ffa4c65` — ruff clean, **929 passed** (38.53s / 40.59s / 40.63s), cli
smoke, `check: green`, three consecutive runs, verified by the builder at that
sha. U8 adds this file and nothing else, so the commit carrying it changes no
gate input.

Nine units planned, nine landed. No unit yielded, none blocked, no order
deviation, one commit per unit — the departure mission 4 recorded did not
recur.

This report is a snapshot. Per DESIGN §20, a claim here that later expires is
corrected by an appended dated line, never by a rewrite; `FINAL-REPORT-3.md`
§3 and now `FINAL-REPORT-4.md` §3 each carry such a correction.

---

## 1. What changed, by unit

**U0 — `068a091` `meta: mission 5 plan, checkpoint, and two corrections`.**
Meta only; no product code, no tests, so the gate is the base's (726). Three
things. `meta/plan.md` and `meta/CHECKPOINT.md` for mission 5. The dated
correction of `FINAL-REPORT-4.md` §3 item 15 (REVIEW-4 blocker 1): its middle
clause — "which was the one arbitrary-exec vector left inside the allow list" —
is false, and the five probes were re-run here against the guard at both
`935a275` and `edf0bc2`, all returning `None` from `check()`. The original text
is untouched. And H-011 gains the architect's decision: the suppressed-stop
event is renamed `pipeline.stop_suppressed`, out of `stop`'s wake namespace.
`34c4c22`, `bf97124`, `b4dc0c0`, `22658e0`, `3477423`, `2d08895` and `8119776`
are the per-unit checkpoint and journal commits, meta only.

**U1 — `50c466c` `driver: the guard's git option policy (§21) and find's
file-writing actions`.** REVIEW-4 blocker 1, the code half. Before a git
subcommand only `-C <path>` (and `-C=<path>`) and `--no-pager` are accepted;
every other token starting with `-` is refused with a message naming the
policy. After the subcommand `--output`, `--ext-diff`, `--textconv`, `-O`,
`--open-files-in-pager` and `--config-env` are refused, matched whole or with
`=`, so `-O<file>` and the separate spelling count while `--no-ext-diff` and
`--output-indicator-new=X` stay reads. `FIND_ACTION_FLAGS` gains `-fprint`,
`-fprint0`, `-fprintf`, `-fls`. `driver/settings.json` is unchanged — the guard
is the layer that decides, which is what the brief asked for. `ADVERSARIAL`
62 → 102 cases, `SELFTEST` 65 → 77. 28 of the 29 new must-block cases returned
`None` at the parent and are listed in the commit body; the 29th
(`find . -exec git -c core.pager=touch log \;`) was already blocked by `-exec`.
778 passed.

**U2 — `ce92ed6` `config: refuse an ops.monitor_cmd that is not a script in
the ops repo`.** REVIEW-4 blocker 2. `parse_config` refuses an
`ops.monitor_cmd` that is absolute, contains `..`, names the ops repo
directory itself, or does not name an existing executable regular file under
`ops.repo`; the shape half also runs in `OpsConfig.__post_init__`, because the
review demonstrated the bug through the dataclass, not the loader. The test
that claimed the state was unreachable now proves it. Fixtures and
`docs/INTEGRATION.md`'s config block were fixed by creating the script, not by
weakening the refusal, and the monitor's run-time "does not exist" / "is not
executable" events stay load-bearing by removing the script *after* load.
789 passed.

**U3 — `e35a2e7` `tests: every assertion compares against path-stripped
text`.** REVIEW-4 should-fix 1 and 2. One helper,
`conftest.strip_paths(text, *extra)`, replaces every path the environment
chose — `--basetemp`, `tmp_path`, `$HOME` with `~/.hands` and the socket under
it, the working directory, and any extra path a caller names — with `<path>`,
longest match first, prefixes only, never a root; an autouse fixture records
the two paths pytest picks. 203 assertions in 13 files go through it.
`tests/test_determinism.py` adds two AST audits over every `assert` in
`tests/`, which is what makes this a property rather than 203 fixes: a new
unstripped assertion fails the gate. Red first at the parent under crafted
values — the two the review named plus three more the audit found
(`test_daemon.py:640` `"for 40m"`, `:639,661` `"no progress and no
liveness"`). 5/5 green under the five `--basetemp` values listed in the commit
body, two of them containing `--pids` and `a send needs a prompt`; the gate
does not forward arguments, so they went through `PYTEST_ADDOPTS`. Test-only.
794 passed.

**U4 — `6d9664d` `cli: one prompt cap, on both routes and on the wire`.**
REVIEW-4 should-fix 3, 4 and 5. The request goes out with
`ensure_ascii=False`, so a 9 MiB CJK prompt file reaches the daemon where it
used to die at a broken pipe; the daemon's line room is
`MAX_PROMPT_BYTES + MAX_PROMPT_BYTES // 4`; `--stdin` gets the same size and
emptiness refusals as `--prompt-file`, at the same place and with the same exit
2; a directory, FIFO, socket or character device is refused from `stat` alone,
with `Path.read_bytes` never called. One judgement call, filed as H-012 for the
architect: "cap plus a quarter" does not cover JSON escaping (a quote is 2
bytes on the wire, a NUL 6), so the at-cap quote and NUL files the brief names
cannot be made to fit, and the unit measures the cap on the prompt **as it
appears on the wire** and refuses them client-side naming both sizes. That is
the reading under which §4's "fits any accepted prompt" is true. `hands
--help`, `docs/INTEGRATION.md` and `driver/CLAUDE.md` say exit 2 means the
client did not deliver a completed request; rule 6 is byte-pinned to DESIGN §12
rule 6, so the clause names rule 6 from rule 8 rather than editing it.
804 passed.

**U5 — `06de18c` `pipeline: stale last_rule, pipeline.stop_suppressed, two
config edges`.** REVIEW-4 should-fix 7 and 8, and H-011. The rename is
everywhere — `EVENT_KINDS`, `PlaybookEngine.stop()`, the daemon, tests,
`docs/PLAYBOOK.md` — and a test pins `resolve_kinds("stop")` to exactly
`{"stop"}`, which is the whole point of it: the driver kit's `--for stop,held`
is no longer woken by a stop that was deliberately not notified.
`hands pipeline` marks a `last_rule` whose `playbook_sha256` is not the loaded
file's with `stale: true`, in the JSON and the prose — marked, not cleared,
because clearing belongs to §10's load. The two config edges are closed as
mission 4's U4 closed the blank-value edge, by a mechanism in the helpers:
`[ops] monitor_cmd` with no `ops.repo` is refused at load and in `OpsConfig`
itself, and `_str`/`_str_list` strip. Three tests hold the mechanism there,
including an AST scan asserting every key `_check_keys` admits is read through
a helper. H-011 is closed on disk. 812 passed.

**U6 — `53bb986` `runner: the stream-json goes to the job's log file, never
to memory`.** DESIGN §21's daemon-memory bullet; not a review item. The audit's
finding is worth the architect's attention: **nothing accumulated events in a
list.** The daemon already flushed them to `<job>.stream.jsonl`. The unbounded
readers were `Api.tail`, which `read_text()`-ed the whole transcript on every
poll, and `Api.log` at offset 0. So the unit moved the writer into the runner
(one writer, at the point the events land; the daemon's `_streams`/`_capture`
pair and the `on_stream_line` hook are gone), added `Runner.retained()`, and
made `tail` read a bounded window backwards from the end. N is zero retained
stream events — both readers read the file — leaving only `tail`'s bound,
`MAX_TAIL_ENTRIES = 1000` or a 4 MiB window, whichever binds first. H-013 filed:
`Api.log` at offset 0 still answers a whole transcript in one message, and
bounding it needs a paging contract §7 does not have. 818 passed.

**U7 — `ffa4c65` `hooks: a role session cannot start a background task`.**
DESIGN §21 and §2; not a review item. `.claude/settings.json` runs
`.claude/hooks/no_background.py` as a `PreToolUse` hook on `Bash`; it exits 2
with the reason and the foreground-with-a-timeout advice on stderr when the
call sets `run_in_background` or the command daemonizes by hand. Two tables as
the guard has them — the hook's `SELFTEST` (50) and one owned by `tests/` (43)
— plus `main()` driven as a subprocess with hook JSON on stdin, which the
guard's `main()` still lacks. `CLAUDE.md` states the rule in one bullet;
`docs/INTEGRATION.md` says every repository hands drives installs the same two
files, pinned by `tests/test_docs.py`. `./scripts/check` still runs: every line
of it is foreground, and a test asserts each is allowed. 929 passed.

**U8 — this file.** No product code, no tests.

---

## 2. What the tests prove

929 tests at the tip, 203 more than the base's 726. By unit: 778, 789, 794,
804, 812, 818, 929 — each number is the gate's own count at that sha, and each
sub-agent ran `./scripts/check` three consecutive times before committing.

- **The guard refuses the reviewer's probes.** Each of the five probes REVIEW-4
  blocker 1 executed is in `ADVERSARIAL` asserted blocked, along with 24 more
  of the same shape the unit found (`--exec-path`, `--git-dir`, `--work-tree`,
  `--namespace`, `-p`/`--paginate`, `git -c protocol.ext.allow=always fetch
  "ext::sh -c …"`, both `--config-env` spellings, `--textconv`, `-O<file>`).
  The four read-only commands the driver relies on pass, and were green before
  the change too — they are anti-over-refusal guards, not evidence of the fix.
- **A monitor_cmd that cannot name a script does not load.** Eight refusals,
  two acceptances, and the dataclass raises where it used to return the ops
  directory.
- **The gate's determinism is a property.** Two AST audits over every `assert`
  in `tests/` fail the gate on a new unstripped assertion; the five crafted
  `--basetemp` values are 5/5 green, and two of them were re-run by the builder
  at the tip (`/tmp/pt-orch/z--pids`, `/tmp/pt-orch2/a send needs a prompt`,
  929 passed each). One of the review's two named instances was re-driven red
  at the parent by the builder as an independent check.
- **A prompt refuses at the path the human named, on both routes.** The 9 MiB
  CJK file is delivered; the at-cap quote and NUL files are refused
  client-side; the same oversized bytes get the same message tail and exit 2
  through `--prompt-file` and `--stdin`; a FIFO is refused from `stat` without
  a read.
- **`--for stop` is one kind again**, and `hands pipeline` says `stale: true`
  rather than printing an old rule beside a new sha.
- **The runner retains nothing per event.** With 200 000 events on disk and the
  job still running, every count `Runner.retained()` reports is 1 or 0, and the
  same after it ends; the file keeps all 200 000, verbatim, including a
  non-JSON line.
- **A role session cannot start a background task.** `nohup`, `setsid`,
  `disown`, a trailing `&` outside quotes and an `&` before `)` are refused,
  inside `$(…)` and backticks too; `&&`, `2>&1`, `&>`, `|&`, an `&` inside
  quotes or in a URL, and every line of `./scripts/check` are not; unbalanced
  quotes fail closed.

---

## 3. NOT PROVEN

1. **The guard's remaining surface, stated as the reviewer would.** U1 closed
   the arbitrary-exec and write vectors REVIEW-4 blocker 1 named. It did not
   empty the surface, and this sentence is written so that the mistake item 15
   of `FINAL-REPORT-4.md` made is not repeated. Run against the tip's
   `driver/hooks/bash_guard.py` (`check()` returning `None` = allowed), all
   confirmed here today:

       git branch newbranch              -> None   # creates a ref
       git branch -f main origin/main    -> None   # moves a branch
       git remote prune origin           -> None   # deletes remote-tracking refs
       git remote set-head origin -a     -> None   # writes a ref
       git fetch --force origin main:main-> None   # overwrites a local ref
       find . -name x                    -> None   # `find` is still on the allow list

   Only `-d`/`-D`/`-m`/`-M` are in `FORBIDDEN_GIT_FLAGS`, so `git branch <name>`
   and `git branch -f` mutate the repository through a subcommand the allow list
   contains; `git remote prune`/`set-head` and a `git fetch` with a refspec are
   the same shape. Against DESIGN §12's "never writes, never mutates a repo"
   these are live. They are not regressions — every one of them was allowed
   before this mission — and no unit of mission 5 was asked to close them; the
   general question of whether the allow list should contain second-level verbs
   and `find` at all is the architect's, and §6 puts it there. **The guard's
   arbitrary-exec surface is smaller than it was and is not known to be empty:**
   the method that found `git -c` was a reviewer enumerating git's own wrappers,
   and nothing in the repository does that enumeration on a schedule.
2. **The guard has still never run as a real Claude Code `PreToolUse` hook**,
   and `bash_guard.main()`'s stdin/exit-2 wiring still has no test. U7's hook
   does have that test, so the two hooks are now unequal in this respect; the
   guard's half is untouched by this mission. Carried from mission 3.
3. **The new hook has never run as a real hook either.** Hooks are snapshotted
   at session start, so `.claude/settings.json` did not take effect in the
   session that wrote it; the exit-2 semantics are proven as a subprocess
   contract only. Its detection is textual, not a shell parse: `screen -dmS`,
   `tmux new -d`, `at`, `systemd-run`, a script that forks, `echo a&b` and any
   daemonizer arriving through a variable are not caught.
4. **No test proves another repository installed the two files.**
   `docs/INTEGRATION.md` is instructions; only this repo's copies are pinned.
5. **The daemon's RSS before and after U6 is unmeasured.** The unit's claim is
   about what the runner retains — asserted on lengths, as the brief asked —
   not about resident size. The 959 MB observation in §21 is the architect's
   measurement of a *different* build, and nothing here reproduces or refutes
   it. The likeliest culprit U6 found (`Api.tail` reading the whole transcript
   on every poll) is a hypothesis fitted to the symptom, not a diagnosis.
6. **`hands log <job>` at offset 0 still materializes a whole transcript**
   (H-013). U6 bounded `tail`, not `log`.
7. **Nothing in this mission ran outside pytest.** The installed build is still
   mission 2's, so missions 3, 4 and 5 are now three missions of code that have
   never run in a real session: no live daemon, no live driver, no real
   `claude`. The stale-`last_rule` line, the `--for pipeline` wake, the new
   refusal messages and the streaming log are all unwitnessed outside the
   suite. `hands notify --test` has still never reached a live ntfy topic.
8. **U4's cap is now stricter than the runner's.** The client measures the cap
   on the wire; `Runner.run` still measures raw UTF-8 bytes, so the client
   refuses prompts the runner would have accepted. Deliberate — the daemon
   could never have received them — but it is a second meaning for "10 MB"
   alongside the 10 MB / 10 MiB question already open. H-012.
9. **U3's audits enforce syntax, not semantics.** A stripped value hoisted into
   a variable, an assertion whose left side is a call or subscript
   (`assert str(path) in err`), and `re.search`/`startswith` checks are outside
   their rule. `test_docs.py` and `test_bash_guard.py` are exempt on the
   argument that repository artifacts carry no run path — argued in the file,
   not tested. And the false-green half of the class is closed by construction:
   no run can demonstrate it, because a vacuous pass is green either way.
10. **U5's helper-coverage scan is a static read of `config.py`.** A key read
    through a new helper the table does not list would not be distinguished,
    and nothing asserts that no config key's padding is meaningful. `[ops] repo`
    with no `monitor_cmd` stays legal: only the half the review named is
    refused, so `config.py`'s "both keys, or neither" comment is narrowed
    rather than enforced both ways.
11. **`doctor._ops_check`'s "does not exist" / "not executable" branches are
    now reachable only if the script disappears between load and the check**,
    and no test covers them. Its `project = None` branch is still exercised by
    hand only — `FINAL-REPORT-4.md` §3 item 11, still true.
12. **A `monitor_cmd` that is a symlink out of `ops.repo` is accepted.**
    Containment is checked on the path's shape, not on the resolved path.
13. **`mypy` is still not in `./scripts/check`.** The gate is ruff + pytest + a
    CLI smoke test. Carried from missions 3 and 4 and still true.
14. **U6's `tail` bound of 1000 entries / 4 MiB is chosen, not derived.** No
    caller today asks for more than 20, so no answer changes; the number is a
    judgement about what a peek at the end of a session should cost.
15. **The `ADVERSARIAL` / `SELFTEST` overlap is still bounded only by
    `>= 20 / >= 10 / >= 10`** (REVIEW-4 should-fix 6). The tables grew to 102
    and 77 and nothing asserts they stay independent.

---

## 4. Review items

`meta/reviews/REVIEW-4.md`, `VERDICT: review mission 4 blockers=2
should-fix=8`.

| Item | Status |
|---|---|
| Blocker 1 — `FINAL-REPORT-4.md` §3 item 15 makes a safety claim the guard contradicts | closed `068a091` (the dated correction) and `50c466c` (the vectors) |
| Blocker 2 — U4's test claims an unreachable state that is reachable | closed `ce92ed6` |
| 1 — the fault class is live in two negative assertions | closed `e35a2e7` |
| 2 — the false-green half, in files the audit did not open | closed `e35a2e7` |
| 3 — the client's cap and the socket's line limit are different limits | closed `6d9664d` |
| 4 — a non-regular prompt file hangs the client forever | closed `6d9664d` |
| 5 — exit 2 is two things and the docs say it is one | closed `6d9664d` |
| 6 — `ADVERSARIAL`'s independence is real but not as clean as claimed | not applicable (a note on method; the brief assigns the answer to U3's independent table — `tests/test_determinism.py`'s AST audits, written by an agent that did not write the code they audit). The keeper the item asks for — an assertion that the two guard tables stay independent — is **not** in place; §3 item 15 says so |
| 7 — `hands pipeline` can print a `last_rule` from another playbook | closed `06de18c` |
| 8 — two smaller config edges of the same shape | closed `06de18c` |

Carried from `meta/reviews/REVIEW-3.md`, deferred by mission 4's brief and
**still deferred** — no unit of mission 5 was asked for them, and none touched
them:

| Item | Status |
|---|---|
| REVIEW-3 3 — `doctor.py`'s probe argv hardcodes the three flags | deferred, mission 6 |
| REVIEW-3 6 — `accepted()` treats a non-integer status as delivered | deferred, mission 6 |
| REVIEW-3 7 — `Api.notify`'s failure shape has no client test | deferred, mission 6 |

---

## 5. Acceptance, checked

- `./scripts/check` green on the pushed tip `ffa4c65`, three consecutive runs:
  ruff `All checks passed!`, `929 passed in 38.53s / 40.59s / 40.63s`,
  cli smoke, `check: green`, exit 0 each. Run by the builder, at the tip.
- The adversarial table contains every probe REVIEW-4 blocker 1 executed —
  `git -c diff.external='touch /tmp/gprobe-pwned' diff --ext-diff`,
  `git -c core.pager=touch log`, `git diff --output=/tmp/x`,
  `git show HEAD --output=/tmp/x`, `find . -fprint /tmp/out` and its
  `-fprint0`/`-fprintf`/`-fls` siblings — each asserted blocked. Re-run
  independently by the builder against the tip: all blocked, the four
  read-only driver commands all allowed.
- `grep -rn 'stop\.suppressed' src tests docs driver` returns nothing (exit 1).
- `meta/FINAL-REPORT-4.md` §3 carries the dated correction of item 15, appended
  after the original, which is untouched.
- `meta/FINAL-REPORT-5.md` exists, with NOT PROVEN and the review-items table.
- `python3 .claude/hooks/no_background.py --selftest` → `selftest: 50/50 ok`;
  `driver/hooks/bash_guard.py --selftest` → `selftest: 77/77 ok`. Both exit 0.
- No unit commit touches `DESIGN.md`, `meta/plan.md` or `meta/CHECKPOINT.md`.

---

## 6. For the architect

1. **The daemon-memory premise did not survive the audit.** §21 says
   "stream-json events are written to the job's log file as they arrive and
   never accumulated in memory" as a change to make; U6 found the daemon
   already did that. What was unbounded was the *reader* — `Api.tail`
   re-reading the whole transcript on every poll — which is a plausible source
   of the 959 MB but is not proven to be the one. If the peak matters, the
   thing to do is measure a real run, not to trust this report.
2. **The guard's allow list still mutates repositories.** §3 item 1 lists what
   passes today. Two questions are yours: whether `git branch`, `git remote`
   and `git fetch <refspec>` belong in a list whose contract is "never mutates
   a repo", and whether the list should be verbs at all rather than a small
   set of whole commands. A third: nothing enumerates git's wrappers on a
   schedule, so the next `git -c`-shaped hole will be found by a reviewer or
   not at all.
3. **H-012 — the prompt cap is now defined on the wire.** §4's refusal list
   does not name that refusal, and the client is stricter than `Runner.run`.
   One sentence in §4 settles it. The 10 MB / 10 MiB question is still open
   alongside it.
4. **H-013 — `hands log <job>` has no paging contract.** §7 describes the
   library but not how much of a transcript one answer may carry.
5. **The installed build is three missions behind.** Every NOT PROVEN item that
   begins "nothing ran outside pytest" has the same remedy —
   `uv tool install --force ~/git/hands` and one real job — and it has been
   carried across three reports now. It is the cheapest evidence left unbought.

---

VERDICT: mission 5 finished
