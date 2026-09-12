# FINAL-REPORT-6 — hands mission 6: close review 5

Mission: `meta/BUILDER-6-PROMPT.md`. Design: `DESIGN.md` v3.5, §22.
Review closed: `meta/reviews/REVIEW-5.md`, `VERDICT: review mission 5
blockers=2 should-fix=7`.

Base `b950956` (`plan: mission 6 kit (DESIGN v3.5)`) — green here before U0:
ruff clean, **929 passed**, cli smoke, `check: green`.
Tip `TIP_SHA` — ruff clean, **TIP_COUNT passed** (TIP_TIMES), cli smoke,
`check: green`, three consecutive runs, verified by the builder at that sha.
U7 adds this file and nothing else, so the commit carrying it changes no gate
input.

Eight units planned, eight landed. No unit yielded, none blocked, no order
deviation. Two units took two commits each rather than one — U5 and U6 — and
§1 says why in each case; every other unit is one commit.

This report is a snapshot. Per DESIGN §20, a claim here that later expires is
corrected by an appended dated line, never by a rewrite; `FINAL-REPORT-3.md`
§3, `FINAL-REPORT-4.md` §3 and now `FINAL-REPORT-5.md` §3 each carry such
corrections.

---

## 1. What changed, by unit

**U0 — `bb9d8fb` `meta: mission 6 plan; review 5's three corrections and the
H-012 decision`.** Meta only; no product code, no tests, so the gate is the
base's (929, three runs). `meta/plan.md` and `meta/CHECKPOINT.md` for mission
6. Three dated corrections appended to `meta/FINAL-REPORT-5.md` §3, after
untouched originals: correction 1 (REVIEW-5 blocker 1) narrows §4's `closed
6d9664d` for review 4's should-fix 3 — that commit closed the fault class for
the *prompt*, not the request — and names the two shipped sentences that said
otherwise; correction 2 (blocker 2) states the two answers that silently
changed at `53bb986`, re-reproduced against the tip (`n = 0` on a 2000-entry
transcript now 1000 entries; a trailing entry wider than the window answers
`[]`); correction 3 (should-fix 2) lists the three hook bypasses the report did
not, each re-driven through `main()` and allowed. H-012 gains the architect's
decision: the client measures the **whole request** on the wire.
`7acaa8a`, `e912144`, `186113c`, `7954e06` and `a6ffe3c` are the per-unit
checkpoint and journal commits, meta only.

**U1 — `81e4cd2` `client: measure the whole request before connecting`.**
REVIEW-5 blocker 1; DESIGN §4's `send` row, §2; H-012. `cli._wire_size` counts
the exact JSON line `call` writes — the request's shape serialized with every
string emptied, plus `_wire_bytes` for each string it carries — and
`_checked_request` raises before the socket is opened when that line is over
`runner.LINE_LIMIT`, with one line naming the total, the limit and the largest
part, exit 2. The line-room constant moved from `daemon.py` to `runner.py`, so
the daemon's reader and the client's measurement are one number; the line room
itself is not raised. `docs/INTEGRATION.md`'s "so anything the client accepts
fits" and `daemon.py`'s "more than a command line can hold" are rewritten to
say what is measured, and `tests/test_docs.py` fails if either sentence
returns. H-012 gets an appended closing status line.

**U2 — `0042433` `api: tail says when it was cut, and log is delivered in
pages`.** REVIEW-5 blocker 2; DESIGN v3.5 §4's `tail` and `log` rows, §7, §21;
H-013. `hands tail -n 0` and negatives are refused by the client before it
connects (exit 2, one line naming the option, the value and the least it
takes), and `Api.tail` refuses the same `n`, so a JSON-RPC caller cannot ask
for it either — the `n <= 0` branch that used to mean "everything" is gone. The
answer carries `truncated: true` whenever the 1000-entry cap or the read window
cut it, false otherwise, and the human route prints one line saying so. For
`log`, `_read_from` reads one page — at most `LOG_PAGE_BYTES` (256 KiB) of
complete lines, plus the remainder of a single line wider than that — and
`Api.log` answers with the page, the `offset` it ends at, and `more`;
`hands log <job>` without `--json` walks the pages itself and prints them in
order, so a human still gets the whole stream from one command, while a
`--json` caller continues with `--offset <offset>` while `more` is true.
H-013 gets a dated decision and a closing status.

**U3 — `5ffbe33` `driver: git is an allowlist of options per subcommand, not a
denylist`.** REVIEW-5 should-fix 1; DESIGN §12's guard bullet, §22.
`driver/hooks/bash_guard.py` drops `FORBIDDEN_GIT_OPTIONS` and the option half
of `FORBIDDEN_GIT_FLAGS` for `GIT_SUBCOMMAND_OPTIONS`, the table §12
enumerates. A subcommand that is not a key is refused; for one that is, every
token beginning with `-` that its row does not list is refused. **The rows are
the remaining surface, and they are:**

    log        --oneline --grep= --format= --stat --name-status -n
               (and the `-n` shorthand `-10` / `-n10`)
    show       --stat --name-status
    fetch      -q
    ls-remote  --heads --tags
    rev-parse  --verify --short
    diff       --stat --name-status --name-only
    grep       -n -c -l -i -e
    cat-file   -t -p -e
    branch     --list
    remote     -v
    ls-files, ls-tree, status   no options

Revisions, `rev:path`, remotes, paths and `--` carry no leading dash and are
not judged. Before the subcommand only `-C <path>` and `--no-pager` are
accepted, and the word after `-C` is now judged: a single path that does not
begin with `-`. `describe`, `shortlog`, `blame` and `name-rev` are no longer
subcommands, because §12's table does not list them. Newly refused reads, from
the same rule: `git status --porcelain`, `git diff --no-ext-diff`,
`git log --no-textconv`, `git branch -a`, `git log -p`, `git show -s`,
`git ls-tree -r`, `git rev-parse --git-dir`, `git fetch --force`.
`driver/settings.json` is unchanged: the guard is the layer that decides.

**U4 — `fba759b` `hooks: a comment, a path-qualified daemonizer, and an
unreadable tool_input`.** REVIEW-5 should-fix 2; DESIGN §21's last bullet with
§2. Two of the three bypasses are closed in `.claude/hooks/no_background.py`:
an unquoted `#` that starts a word now opens a comment and the rest of the line
is blanked, so `sleep 30 &# note` is the background job bash reads it to be
(and `ls # a & b`, which the hook used to refuse, passes); a token whose
*basename* is `nohup`, `setsid` or `disown` is that daemonizer, so
`/usr/bin/nohup ./long.sh` is caught, at the deliberate cost of refusing
`ls -l /usr/bin/nohup`. The third — `bash -c 'sleep 30 &'`, `sh -c`, `eval` —
is **not** closed: quoted text is text is the property both hooks rely on, and
reading it as shell would block `git commit -m 'runner: the log & the spool'`.
It is documented instead, with the previously admitted blind spots, under a new
"What the hook cannot see" heading in `docs/INTEGRATION.md` that
`tests/test_docs.py` pins. Separately, `main()` no longer raises on a
`tool_input` that is not an object or a `command`/`run_in_background` of the
wrong type: those shapes exited 1 — non-blocking in Claude Code — and now exit
2 with one line and no traceback.

**U5 — `44e42ba` `review: five REVIEW-5 edges — an argv cap, ops containment,
two scans, one UTF-8 refusal`, then `3809fcf` `client: every string a request
carries is refused for not being UTF-8 where the prompt is`.** REVIEW-5
should-fix 3–7; DESIGN §21, §13, §5, §4. Two commits, because the first one's
own NOT PROVEN named a gap in its own item 7 and the second closes it; both
commits' tests are red at their parents.

- **3.** `Runner.last_argv` was never popped, so the daemon held one argv list
  per job it had ever run while `retained()`'s docstring said every count was
  bounded by the jobs in flight. It keeps the last `MAX_LAST_ARGV` (8) now, and
  the docstring names three bounded things the method does **not** count
  (`_Parsed.result`, the stderr tail, asyncio's reader buffer).
- **4.** `ops.monitor_cmd` containment was lexical. `<repo>/<cmd>` is resolved
  and checked against the resolved repo, so a symlink out of the repo and a
  traversal through a symlinked directory are refused by where they land, while
  a symlink resolving back inside still loads. `doctor`'s "does not exist" and
  "is not executable" rows — whose only coverage mission 5's U2 removed — are
  driven again through `run_checks`.
- **5.** The config helper-coverage scan reads the top-level section list too
  and reports any section that never calls `_check_keys`, so the reviewer's
  `[extra]`-section demonstration now fails two tests.
- **6.** `NOT_TEXT` exempts a name for what it holds, so the exemption is
  withdrawn from any name the file assigns text to, and a literal is recognised
  as an f-string or a sum of constants as well as a written one. The three
  shapes the reviewer drove past the audits are caught, and three that must
  stay exempt are asserted beside them.
- **7.** `_utf8_bytes(text, where)` is the one place a string a human handed
  the client is refused for not being UTF-8. `44e42ba` routed `--prompt-file`
  and `--stdin` through it; `3809fcf` routes a prompt given as a command-line
  **argument** through it too, and every string the request's `params` carry
  (`--gate`, `--file`, `--content`), under the name the human typed it as,
  before `_wire_size` encodes anything. Python decodes `argv` with
  `surrogateescape` exactly as it decodes stdin, so those fields used to die
  inside the wire measurement as `hands: 'utf-8' codec can't encode
  characters…` with exit 1 — review 5 blocker 1's shape, one field over.

**U6 — `56bef53` `docs: the driver arms no background wait; doctor checks the
doorbell instead`, then `U6B_SHA` `U6B_SUBJECT`.** Not a REVIEW-5 item: the
v3.5 design change (§22's first bullet, "Driver wait retired") the review did
not raise. §11's decision paragraph is the spec — the driver arms no background
wait at all; ntfy is the human's doorbell and the human's `check` is the
driver's.

- `driver/CLAUDE.md` rule 8 is DESIGN §12 rule 8 word for word; the exit-2
  sentence that used to end the rule moved into the surrounding text, where the
  document still says it. The kickoff walk-through no longer says "Arm the
  background wait (rule 8)" — it says to report the job id and stop, and what
  `check` then runs. `--for stop,held` is no longer offered to the driver; it
  remains a §4 command for a human at the laptop.
- `src/hands/doctor.py`'s `wake_procedure()` prints a **notification check**:
  the same `hands pause` (cleared by `resume`) or gated `--gate` send (cleared
  by `deny`), run once to prove the event reaches the phone over ntfy. The
  `wake_check` key in `--json` and the §11 citation are unchanged.
- `driver/README.md` and `docs/INTEGRATION.md` say the same;
  `docs/INTEGRATION.md`'s open question about whether a finished background
  Bash task wakes an idle session is replaced by the unknown that survives it,
  ntfy delivery.
- U6B_BULLET

**U7 — this file.** `meta/FINAL-REPORT-6.md` and nothing else.

---

## 2. What the tests prove

Test count at each unit's own commit, as its body states and the builder
re-ran: base 929 → U1 936 → U2 942 → U3 1047 → U4 1095 → U5 1109 → U6
TIP_COUNT. `driver/hooks/bash_guard.py --selftest` is **100/100**, up from 77;
`.claude/hooks/no_background.py --selftest` is **65/65**, up from 50.

**U1.** `_wire_size` is byte-exact against `json.dumps(..., ensure_ascii=False)`
for four requests carrying quotes, backslashes, NULs, CJK and a `--file` list.
The reviewer's own reproduction — an at-cap prompt plus twelve `--file` values
of backslashes — exits 2 with one message and no socket opened on all three
prompt routes, and against a real daemon adds no record to the daemon's log and
creates no job. A request whose line is exactly `LINE_LIMIT` is read, run and
its file written; the same request one byte fatter is refused. What is proven
is these requests, not all requests.

**U2.** A 2000-entry transcript asked for 2000 answers 1000 with
`truncated: true` and one "truncated" line for the human, while `-n 20` on the
same file says nothing of the kind; a transcript whose trailing entry is wider
than `TAIL_WINDOW_BYTES` answers `[]` with `truncated: true` rather than a
silent `[]`; `-n 0` and negatives are refused at both the client and `Api.tail`.
An ~800 KB stream comes back in more than three pages, each within the bound,
concatenating to the stream in order with `more: false` on the last, and the
human route prints every line. A 64 MB stream read through `daemon.api.log`
takes more than 200 pages with a `tracemalloc` peak under 8 MiB, every line
once, ending at the size of the file.

**U3.** Test-first: with U3's tests and the guard at the parent,
`tests/test_bash_guard.py` is 42 failed, 210 passed. Each of the reviewer's
probes is asserted blocked — `ls-remote --upload-pack=`, `-C ./src fetch
--upload-pack=`, `fetch --exec=`, `ls-remote --exec=`, `branch
--edit-description`, `-C ./repo -C --exec-path=/tmp/evil log` — and blocked by
**absence**: no denylist entry mentions them. The table itself is pinned
against a copy transcribed from DESIGN §12; no row lists an option that names a
program or a file; for each of the 13 subcommands, `--upload-pack=`, `--exec=`,
`--output=`, `--ext-diff`, `--config-env=` and an invented option are refused,
and git's global `-c` is refused before it. The driver's read-only commands are
asserted allowed: mission 5's four, every option in every row, and the git lines
`driver/CLAUDE.md` tells the driver to run.

**U4.** The two closed bypasses are red at the parent and exit 2 here; the
newly *allowed* comment forms (`ls # a & b`, `uv run pytest # then nohup ./x &
disown`) are asserted allowed so the fix is not a widening of refusal; the
deliberate cost (`ls -l /usr/bin/nohup`, now refused) is pinned as such. Every
line of the "what the hook cannot see" list was re-driven through `check()` and
is allowed today — the doc is tested to exist and to say so, not to be
complete.

**U5.** One test per item. Item 3 runs 11 jobs and asserts which argvs survive.
Item 4's symlink escape and traversal are refused by where they land, and
doctor's two rows go red when mutated. Item 5's unit test drives the scan on a
mutated copy of `config.py`. Item 6 catches the three shapes the reviewer drove
past the audits and asserts three that must stay exempt. Item 7: all three
prompt routes given the same bytes refuse with exit 2, name the route first and
give one identical reason, and `--gate` given those bytes refuses as
`hands: --gate`; both tests are red at `44e42ba` (exit 1, codec message).

**U6.** `kit_rule(8) == design_rule(8)`, the twin of the rule-6 test. A
"must not come back" phrase list over the shipped documents, verified red by
appending "Arm the background wait (rule 8)" to the kit. Doctor's output and
its `wake_check` JSON must not contain `hands wait --for stop,held` or the word
"background", and must carry ntfy, `check`, §11, the pause, `paused by human`,
the gated send, `deny <job>` and `resume`. These prove what the documents say,
and nothing about what a driver session does with them.

---

## 3. NOT PROVEN

1. **The guard's remaining surface is the enumerated option table of §1 U3.**
   That is the point of an allowlist: what it allows is the surface, and it is
   written out above rather than described. Inside it, the mutation vectors
   mission 5's report listed are **still live**, because they carry no option
   and so no option rule touches them — `git branch <name>` (creates a ref),
   `git remote prune origin`, `git remote set-head origin main`,
   `git fetch origin main:main` and a forced refspec. Against DESIGN §12's
   "never writes, never mutates a repo" these are open. They are not
   regressions and no unit of this mission was asked to close them; whether the
   allow list should contain second-level verbs at all is the architect's, and
   §6 puts it there. The arbitrary-**exec** surface is smaller than it was and
   is not known to be empty: the method that found `--upload-pack=` was a
   reviewer enumerating git's own wrappers, and nothing in the repository does
   that enumeration on a schedule.
2. **Neither hook has ever run as a real Claude Code `PreToolUse` hook.** Hooks
   are snapshotted at session start, so `.claude/settings.json` never took
   effect in the session that wrote it; both hooks' exit-2 semantics are proven
   as a subprocess contract only. `bash_guard.main()`'s stdin/exit-2 wiring
   still has no test at all — carried from mission 3, untouched by this
   mission, and the two hooks remain unequal in this respect.
3. **The inner-shell class stays allowed by design.** `bash -c 'cmd &'`,
   `sh -c`, `eval`, and the blind-spot list — `screen -dmS`, `tmux new -d`,
   `at`, `systemd-run`, a script that forks, a daemonizer arriving through a
   variable, `\nohup` — are documented in `docs/INTEGRATION.md` under "what the
   hook cannot see", not blocked. U4 closed what a hook can close; this is the
   rest, and it is a boundary, not a backlog item.
4. **No test proves another repository installed either hook.**
   `docs/INTEGRATION.md` is instructions; only this repo's copies are pinned.
5. **The UTF-8 refusals are driven in-process** with the surrogate strings
   `PYTHONUTF8=1` produces, not under a real `PYTHONUTF8=1` subprocess.
   `--file` and `--content` are covered by the request-wide check rather than
   by tests of their own, and nothing checks strings a request carries outside
   `params`.
6. **U1's cap is stricter than the runner's.** The client measures wire bytes;
   `Runner.run` still measures raw UTF-8, so the client refuses requests the
   runner would have accepted. Deliberate — the daemon could never have
   received them — but it is a second meaning for "10 MB" alongside the
   10 MB / 10 MiB question already open. H-012 records it as surviving the
   decision.
7. **U2's bounds are chosen, not derived.** 1000 entries, a 4 MiB tail window
   and a 256 KiB log page are judgements about what a peek at the end of a
   session should cost. The page bound is not a bound on one *line*: the
   runner's reader admits ~11 MiB, and such a line is answered whole.
   `spool.events()` and `list_jobs()` still read whole files, so U2 bounded two
   readers, not the daemon.
8. **U5's audits and scans enforce syntax, not semantics.** A stripped value
   hoisted into a variable, an assertion whose left side is a call or
   subscript, and `re.search`/`startswith` checks are outside the audits' rule;
   a config key read through a new helper the table does not list would still
   not be distinguished. `MAX_LAST_ARGV` bounds a *count*, and no test measures
   the daemon's resident size.
9. **U6 proves what the documents say, not what a driver does.** No driver
   session has run against the rewritten kit. The notification check
   `hands doctor` now prints has never been run, so **ntfy delivery is still
   unwitnessed**: no request has ever left this machine for a topic.
   `hands notify --test` has still never been run against a live topic.
10. **Nothing in this mission ran outside pytest.** The installed build is
    still mission 2's, so missions 3, 4, 5 and 6 are now four missions of code
    that have never run in a real session: no live daemon, no live driver, no
    real `claude`. The single exception is the builder's own re-drive of the
    reviewer's blocker-1 reproduction and of U2's two cut paths through the
    real CLI, recorded in `meta/CHECKPOINT.md` at `7acaa8a` and `e912144`.
11. **`mypy` is still not in `./scripts/check`.** The gate is ruff + pytest +
    a CLI smoke test. Carried from missions 3, 4 and 5 and still true.
12. **The `ADVERSARIAL` / `SELFTEST` overlap is still bounded only by
    `>= 20 / >= 10 / >= 10`** (REVIEW-4 should-fix 6). The tables grew again
    this mission and nothing asserts they stay independent.
13. **DESIGN §11 still carries the v3.4 text U6 retired**, around the decision
    paragraph that retires it — the opening "the driver runs `hands wait --for
    stop,held` as a Claude Code *background* Bash task" and the trailing
    background-completion fallback. Builders do not edit DESIGN.md; §6 puts it
    to the architect. The disk follows the decision paragraph and §22.

---

## 4. Review items

`meta/reviews/REVIEW-5.md`, `VERDICT: review mission 5 blockers=2
should-fix=7`.

| Item | Status |
|---|---|
| Blocker 1 — the fault class left open through the envelope, and two shipped sentences say otherwise | closed `bb9d8fb` (the dated correction) and `81e4cd2` (the measurement and both sentences) |
| Blocker 2 — `tail -n 0` changed meaning and a wide trailing entry answers `[]`, against a body that says no answer changes | closed `bb9d8fb` (the dated correction) and `0042433` (`n >= 1`, `truncated`, paged `log`) |
| 1 — the guard's arbitrary-exec surface still contains `--upload-pack=` / `--exec=` | closed `5ffbe33` (the per-subcommand option allowlist; the surface is §1 U3's table, and §3 item 1 says so) |
| 2 — three hook bypasses absent from NOT PROVEN, and one input shape fails open | closed `bb9d8fb` (the dated correction) and `fba759b` (two bypasses and the input shape; the third documented, §3 item 3) |
| 3 — `Runner.retained()` reports a bound its own docstring overstates | closed `44e42ba` |
| 4 — containment is lexical, and the commit removed the only coverage of two branches | closed `44e42ba` |
| 5 — three edges U5 left (the section-blind scan, `last_rule` without a sha, `gates.patterns` stripping) | closed `44e42ba` for the section-blind scan, which is the edge the brief's U5 item 5 names; (b) and (c) **not closed** — see below |
| 6 — the audits exempt by source text, not by type | closed `44e42ba` |
| 7 — the two prompt routes disagree on the encoding refusal | closed `44e42ba` (both file routes) and `3809fcf` (the argv route and every other string a request carries) |

Should-fix 5 carried three lettered edges and `BUILDER-6-PROMPT.md`'s U5 item 5
names only the first. The other two are open, unscheduled, and named here
rather than left implied — both re-checked on the tip today:

| Item | Status |
|---|---|
| 5(b) — a `last_rule` with no `playbook_sha256` at all is marked `stale: true` even when the loaded playbook is the one it fired under | **not closed**, unscheduled (`playbook.py:1081` compares against `self.state.last_rule_sha256`, which is `None` for a state file written before that field existed) |
| 5(c) — `_str_list` stripping widens `gates.patterns`, the one place trailing padding is meaningful | **not closed**, unscheduled (`config.py:455` still routes `gates.patterns` through `_str_list`) |

Neither is in `meta/BACKLOG.md`, so neither has a mission; §6 puts them to the
architect.

Carried from `meta/reviews/REVIEW-3.md`, deferred by missions 4 and 5 and
**still deferred** — `FINAL-REPORT-5.md` §4 scheduled them for mission 6, and
DESIGN §22 and `meta/BACKLOG.md` moved them to mission 7 so that mission 6
stayed review-closing. No unit of this mission was asked for them and none
touched them:

| Item | Status |
|---|---|
| REVIEW-3 3 — `doctor.py`'s probe argv hardcodes the three flags | deferred, mission 7 (`meta/BACKLOG.md` item 3) |
| REVIEW-3 6 — `accepted()` treats a non-integer status as delivered | deferred, mission 7 (`meta/BACKLOG.md` item 3) |
| REVIEW-3 7 — `Api.notify`'s failure shape has no client test | deferred, mission 7 (`meta/BACKLOG.md` item 3) |

Not a review item, landed this mission: **U6**, DESIGN v3.5 §22's first bullet
(driver wait retired), `56bef53` and `U6B_SHA`.

---

## 5. Acceptance, checked

- `./scripts/check` green on the pushed tip `TIP_SHA`, three consecutive runs:
  ruff `All checks passed!`, `TIP_COUNT passed` (TIP_TIMES), cli smoke,
  `check: green`, exit 0 each. Run by the builder, at the tip.
- The reviewer's blocker-1 reproduction refuses on the client: an at-cap prompt
  plus twelve `--file` values of backslashes exits 2 before a socket is opened,
  on all three prompt routes, and leaves the daemon's log untouched — tested at
  `81e4cd2` and re-driven through the real CLI by the builder (recorded in
  `meta/CHECKPOINT.md` at `7acaa8a`).
- The reviewer's should-fix-1 probes are in the adversarial table and blocked:
  `git ls-remote --upload-pack='touch …'`, `git -C ./src fetch
  --upload-pack='touch …'`, `git fetch --exec=`, `git ls-remote --exec=`,
  `git branch --edit-description`, `git -C ./repo -C --exec-path=/tmp/evil log`
  — each asserted `False` in `tests/test_bash_guard.py`, and blocked by absence
  from the allowlist rather than by a named rule.
- `driver/CLAUDE.md` rule 8 equals DESIGN §12 rule 8, asserted by
  `tests/test_docs.py::test_driver_rule_8_is_the_design_section_12_rule_8`.
- `grep -rn 'background' driver/ docs/ src/hands/doctor.py` returns no
  instruction to arm one. The surviving hits are rule 8 itself ("Never arm a
  background task"), two doctor docstrings saying §11 retired the wait,
  `docs/INTEGRATION.md`'s "Nothing in hands is a background daemon", and its
  "No background tasks in a role session (§21)" section with the
  `no_background.py` install recipe and the hook's blind-spot list.
- `meta/FINAL-REPORT-5.md` §3 carries the three dated corrections, each
  appended after an untouched original.
- `meta/FINAL-REPORT-6.md` exists, with NOT PROVEN and the review-items table.
- `python3 driver/hooks/bash_guard.py --selftest` → `selftest: 100/100 ok`;
  `python3 .claude/hooks/no_background.py --selftest` → `selftest: 65/65 ok`.
  Both exit 0.
- No unit commit touches `DESIGN.md`, `meta/plan.md` or `meta/CHECKPOINT.md`.

---

## 6. For the architect

1. **DESIGN §11 contradicts itself, and U6 had to pick a half.** The decision
   paragraph ("the driver arms no background wait at all") sits between the
   v3.4 text it supersedes: an opening that instructs the driver to run
   `hands wait --for stop,held` as a background Bash task, and a closing
   fallback for when background completion does not wake an idle session. §22
   says the wait is retired, so the disk follows the decision paragraph and the
   two leftovers are now the only place in the repository that describes the
   retired procedure. Builders do not edit DESIGN.md; this wants a v3.6 edit,
   not a finding.
2. **The guard's allow list still mutates repositories.** §3 item 1 lists what
   passes today. `git branch <name>`, `git remote prune`, `git remote
   set-head`, `git fetch <refspec>` and a forced refspec carry no option, so an
   option allowlist cannot reach them. Two questions are yours: whether those
   second-level verbs belong in the allow list at all, and whether the answer
   should be a subcommand allowlist that lists *arguments* as well as options.
   This is the fourth mission in which a git-shaped hole has been found by
   enumeration rather than by a rule.
3. **ntfy has never delivered a message.** It is the wake path §11 now leans
   on entirely — the driver arms nothing, so the human's phone is the only
   thing that learns a pipeline stopped without someone typing `check`. U6
   turned doctor's wake check into the procedure that would witness it, and
   nobody has run it. This is the single highest-value unproven claim in the
   repository right now, and it costs one command at the laptop.
4. **Two of review 5's lettered edges have no mission.** Should-fix 5(b) and
   5(c) (§4) were not in this mission's brief and are not in `meta/BACKLOG.md`,
   so nothing schedules them. 5(c) in particular is a judgement, not a bug: a
   deliberate trailing space in a `gates.patterns` entry — `"rm "` written to
   avoid matching `rmdir` — is silently widened, which is fail-safe in
   direction and wrong in intent. Either is a one-unit fix; both need a mission
   to be in.
5. **Four missions of code have never run.** The installed build is mission
   2's (§3 item 10). Every refusal message, the paged `log`, the `truncated`
   flag, the rewritten kit and both hooks are unwitnessed outside pytest. A
   mission that does nothing but install the tip and drive one real job would
   retire more unproven claims than any code unit in missions 3–6.
