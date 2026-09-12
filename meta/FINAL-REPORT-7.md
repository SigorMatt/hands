# FINAL-REPORT-7 — hands mission 7a: review 6 and the harness

Mission: `meta/BUILDER-7-PROMPT.md`. Design: `DESIGN.md` v3.6, §23.
Review closed: `meta/reviews/REVIEW-6.md`, `VERDICT: review mission 6
blockers=2 should-fix=6`. Finding decided and closed: H-014.

Base `db0bd2c` (`plan: mission 7a kit (DESIGN v3.6, review base)`) — **red**
here before U0: ruff clean, **2 failed, 1110 passed**. The kit changed two
texts the suite pins verbatim: DESIGN §12 rule 8 gained the exit-2 sentence,
and §10's example review prompt lost `{job.head_at_start}`.
Tip `f96938e` (U5, the last commit that changes a gate input; `dfd9e6c` and this
report's commit are meta only) — ruff clean, **1235 passed** (65.39s / 71.30s /
63.94s), cli smoke, `check: green`, three consecutive runs, verified by the
builder at `dfd9e6c`, whose gate inputs are `f96938e`'s; U6 runs it three more
times before its own commit.

Seven units planned, seven landed, plus one commit before U0 that made the
base green (order deviation, recorded in `meta/plan.md`). No unit yielded,
none blocked. Every unit is one commit; each is followed by a `meta:`
bookkeeping commit (plan, checkpoint, journal) that changes no gate input.

This report was drafted under `meta/drafts/` (gitignored since U0) and moved
into place by U6's own commit; no unit commit in this mission was made with
`git add -A`, and every commit body lists its files (§4 checks it).

This report is a snapshot. Per DESIGN §20, a claim here that later expires is
corrected by an appended dated line, never by a rewrite.

---

## 1. What changed, by unit

**Pre-U0 — `169ce88` `driver: rule 8 and the §10 example follow the v3.6
kit`.** `driver/CLAUDE.md` rule 8 ends with §12's exit-2 sentence (the separate
paragraph below the command list that said the same is gone);
`tests/fixtures/playbook_example.toml` and `docs/PLAYBOOK.md`'s copy carry
§10's v3.6 review prompt; the two playbook tests that fired the example expect
the new literal prompt (`REVIEW_PROMPT`), while `{job.head_at_start}`'s
rendering keeps its own parametrised tests.

**U0 — `b77bc4d` `meta: mission 7a plan; review 6's two blockers corrected and
H-014 filed`.**
- `README.md`'s Status paragraph no longer says the wake-path question is open
  or that doctor prints a procedure that answers it (blocker 1): nothing wakes
  an idle driver but the human's `check`, by decision, and doctor prints the
  notification check.
- `meta/FINAL-REPORT-6.md` §1 U5 item 7 carries a dated correction (blocker
  2): `_utf8_bytes` is the one refusal site for strings a **request** carries;
  `hands notify --test` is a second site that does not pass it.
- `.gitignore` gains `meta/drafts/` (should-fix 3).
- Root `CLAUDE.md`'s no-background bullet: "Sub-agents run in the foreground,
  never in the background." (in the existing bullet, because
  `tests/test_no_background.py` requires the rule stated once).
- H-014 filed with the record of job `0mtygi953-ym63` and the architect's
  decision, plus one gap the decision does not cover (below, §3 and §5).

**U1 — `c00f0c0` `runner: a harness termination is failed, not done`** (§2,
§6, §13, §23, H-014). The runner records `failed` when the process ends
without a final `result` of subtype `success` or `error_*`, when a stderr line
has the harness's terminating shape, or when `num_turns` is absent. A new
job-record field `failure_reason` holds the first cause that holds, in order:
`harness_terminated`, `no_final_result`, `error_result`, `nonzero_exit`,
`no_num_turns`, `spawn_error`; null for every other state and for older
records. A cancel stays `killed` and a detected limit stays `limited` even with
the terminating line, because §6's limit resume waits out the reset and a
`builder.failed → resume` would not (H-005). Role jobs run with
`CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0` unless the new optional
`[roles.<r>] env` table sets it; `hands doctor` prints the effective value on
each role row, and `--live` spawns with the same environment. `hands show`
gains a `failure` line. `docs/INTEGRATION.md` documents the table.

**U2 — `09eed7c` `hooks: the sub-agent tool cannot ask for the background
either`** (§2, §21, §23, H-014). `.claude/settings.json`'s matcher is
`Bash|Agent|Task`. The docstring records what 2.1.269 calls the tool: `Agent`,
with `Task` a still-accepted alias (read from the installed binary; the
transcripts hold 85 `Agent` blocks and 0 `Task`), and a sub-agent runs in the
background unless `run_in_background` is exactly `false` (27 transcript calls
that omitted the flag answered "Async agent launched"). So the hook lets
through only the JSON boolean `false`; `true`, omitted, null and non-boolean
values exit 2 with a message in the Bash refusal's shape. `SendMessage` is not
blocked, and the docstring and `docs/INTEGRATION.md` say plainly that it is
H-014's actual cause and the hook cannot see it. Bash behaviour is unchanged:
four refusal strings are pinned byte-identical, selftest 65/65, plus 12/12 for
Agent/Task.

**U3 — `da1ffb3` `docs: the sweep reads every tracked text file, not a list`**
(blocker 1, should-fix 1, 2). The phrase sweep reads `git ls-files` filtered to
`.md .py .toml .json .txt .service` plus extensionless `#!` files, excluding by
path class, each with a reason: `meta/` (history, §20), `DESIGN.md` (not the
builder's; §11's History quotes the retired model) and `tests/test_docs.py`
(holds the lists) — 50 of 79 tracked files at `da1ffb3`, with a test that
README.md, doctor.py, test_playbook.py, scripts/check and ≥ 40 files were read.
New phrases: README's retired sentence (two) and "not woken by a pause".
`tests/test_playbook.py`'s docstring no longer has a driver blocked on a wait
(should-fix 1). The U6 regression tests now assert on the rendered `hands
doctor` output (text and `--json`: the check names `pause` and a gated send,
says "phone", and every `hands` command it tells the human to type is one of
pause/send/resume/deny/inbox/notify) and on `driver/CLAUDE.md`'s rule 8 text;
the vacuous `"check" in text` half is gone (should-fix 2).

**U4 — `b29b1c7` `client: one tree walk for size and UTF-8; positionals keep
their names`** (should-fix 4, 5). One generator, `_carried`, yields every
string a request's params carry — dict keys included, at any depth — and both
the wire-size measurement and the UTF-8 check read it. A positional is refused
as `a job argument` / `a path argument` / `a prompt argument`, a flag under its
option string; names are read off the argparse parser. The docstring near
`cli.py:755` says "the notification check", not "the wake procedure".

**U5 — `f96938e` `docs: a review reads every commit after the last review: commit`** (§10, §23, review 6 scope note). `docs/PLAYBOOK.md` gains "The review base (DESIGN §23)" under Placeholders: a
cold review reads every commit after the last `review:` commit, which the
reviewer computes (`git log --oneline --grep='^review: ' -1`, or the kit commit
when no review exists); `{job.head_at_start}` stays documented, and the doc says
it is the wrong review base — the finished job may have resumed a mission
mid-way (limit resume, `builder.failed → resume`, a human re-kick), review 6
being the real case — and right for a diff of exactly the job that finished.
No other doc in `docs/`, `README.md` or `driver/` describes the review base.
`meta/REVIEW-PROTOCOL.md` is the kit's copy, unchanged: `git diff db0bd2c --
meta/REVIEW-PROTOCOL.md` and `git log --oneline db0bd2c.. --
meta/REVIEW-PROTOCOL.md` are both empty.

**U6 — this file**, plus `meta/plan.md`, `meta/CHECKPOINT.md`,
`meta/journal.md`. No product code, no tests.

---

## 2. What the tests prove

Counts: base 1110 (+2 red) → pre-U0 1112 → U0 1112 → U1 1156 → U2 1204 → U3
1205 → U4 1233 → U5 1235. Every unit's sub-agent ran `./scripts/check`
three times before its commit, and the builder ran it three more times at each
unit's sha before the `meta:` commit that followed.

**Pre-U0.** The two DESIGN-verbatim tests (`test_driver_rule_8_is_the_design_
section_12_rule_8`, `test_the_fixture_is_section_10s_example_verbatim`) and
the exit-2 doc test are green against v3.6.

**U1.** With `fake_claude` standing in for claude: the exact recorded shape of
job `0mtygi953-ym63` (success result, `num_turns` 59, exit 0, the terminating
line on stderr) is `failed`/`harness_terminated`; a mid-turn exit is
`no_final_result`; a result without `num_turns` is `no_num_turns`; subtypes
`progress`, `success_partial` and a missing subtype are `no_final_result`;
three `error_*` subtypes are `error_result`; a clean exit stays `done` with a
null reason; the terminating line wins over `no_final_result`, and a limit or
a cancel wins over it. The matcher accepts five spellings of the line and
refuses five other lines. The ceiling reaches the process as `0` by default,
even when handsd's own environment sets `600000`; a configured value wins. The
env table loads, a blank value and ten malformed shapes are refused. `hands
doctor` through the real CLI, text and `--json`, shows
`CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0` on both role rows for a config that
does not set it. With the §10 example playbook in a real daemon, a builder job
ending with the terminating line is `failed`/`harness_terminated` and
`builder.failed` fires `resume`: a new builder job, origin `playbook`,
`resumed_from` set, same prompt.

**U2.** The hook run as a subprocess on hook JSON: exit 2 and one stderr line
for `Agent` and `Task` with the flag true, omitted, null, or six non-boolean
values; exit 2 for unreadable input or a list/dict flag; exit 0 and silence
for `false`, `SendMessage`, `ListAgents`; the settings matcher names exactly
Bash plus the hook's sub-agent tools.

**U3.** The sweep, copied into a detached worktree at `dca0820`, is red there
naming README.md (two phrases), tests/test_playbook.py (two) and
tests/test_doctor.py (one), and green at `da1ffb3`; the rewritten
`check`-is-the-wake test is red at `56bef53^`.

**U4.** `_checked_request` on the review's three shapes, and on every string
slot (value or key) of five nested shapes, raises §4's refusal, not
`UnicodeEncodeError`; the set of strings measured equals the set checked
equals the set carried, and the size still equals `json.dumps(...,
ensure_ascii=False)` byte for byte. Through `main([...])` with sockets
forbidden, a bad positional exits 2 under its own name on result, show, open,
wait, log, cancel, approve, deny (job), put, get, ls (path) and send (prompt);
eleven flags keep their option strings; every param key of all 21 commands is
named as argparse names it.

**U5.** `tests/test_docs.py` pins the review-base prose (the rule, when
`{job.head_at_start}` is wrong, when it is right) — red before the doc change,
green after. `tests/test_playbook.py` loads the repository's root
`PLAYBOOK.toml` through `load_playbook` (equal to `parse_playbook` of the
same text) and asserts its review rule names no
`{job.head_at_start}` and says "the last review: commit"; that test was green
from the start (the kit already said so) and was shown red only by breaking
the prompt by hand, which the commit body says. The §10 fixture's load and
rule shape keep their existing test.

---

## 3. NOT PROVEN

1. **No real `claude` has run under any of this.** The terminating line's
   format, the `error_*` subtype names, the `Agent`/`Task` names and the
   background default were read from the installed 2.1.269 binary and from
   transcripts, not driven. That `CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0`
   makes `claude -p` wait instead of terminating is not observed.
2. **H-014's actual cause is not stopped.** Job `0mtygi953-ym63`'s background
   task came from `SendMessage` continuing a finished sub-agent. The hook does
   not refuse `SendMessage`, and no test says what a `-p` turn does when such a
   sub-agent reports back with the ceiling at 0. U1 makes the outcome honest
   (`failed`, not `done`) if the harness terminates anyway; nothing prevents
   the wait.
3. **The hook against a live session is unwitnessed.** That Claude Code sends
   `Agent`/`Task` payloads to a hook matched by `Bash|Agent|Task` and that exit
   2 blocks a sub-agent launch is read from the binary, not observed.
4. **`failure_reason` travels only in the job record.** The `job.failed` inbox
   payload does not carry it, and `hands show`'s new `failure` line has no
   test.
5. **The doc sweep still matches phrases.** A stale claim spelled with none of
   the pinned phrases passes; `meta/`, `DESIGN.md`, `tests/test_docs.py` and
   tracked files outside the extension/`#!` rule are unread; a negated sentence
   that also instructs arming would pass the doctor test.
6. **`hands notify --test` still skips the UTF-8 check** (REVIEW-6 blocker 2).
   U0 corrected the report's claim; the code is unchanged, so the exit-1 codec
   message that blames the ntfy URL is still what a human sees.
7. **`put --from` sends a path, not bytes** (REVIEW-6 note 5), so a file of
   invalid UTF-8 is never checked by the client; `--project` and `--socket`
   with bad bytes still exit 1.
8. **U4's positional names depend on argparse's private `_actions`** and the
   committed positional tests run in-process with surrogate strings; the
   subprocess route was driven by hand (the sub-agent's and the builder's
   probes), not pinned by a test.
9. **The label is "a job argument", not the bare `job`** the brief spelled; it
   follows the prompt label an earlier test pins. The name the human typed is
   in it, and no flag is invented.
10. **The review base is computed by the reviewer, not by hands.** No aux review has run with this
    prompt against a resumed mission; nothing tests that a reviewer follows the
    protocol, and the doc test pins phrases, not meaning.
11. **The installed build is still mission 2's** (FINAL-REPORT-6 §3 item 10):
    five missions of code have never run outside pytest, and ntfy has never
    delivered a message.
12. **H-001 and H-009 stay open**; REVIEW-5 should-fix 5(b) and 5(c) stay
    unscheduled (FINAL-REPORT-6 §4).

---

## Review items

| REVIEW-6 item | Status | Where |
|---|---|---|
| Blocker 1 — README says the wake-path question is open and doctor prints the procedure | closed | `b77bc4d` (the sentence), `da1ffb3` (the sweep that reads README and every tracked text file, red at `dca0820`) |
| Blocker 2 — FINAL-REPORT-6 §1 U5 item 7's totality claim; `notify --test` | closed for the report | `b77bc4d` (dated correction); the code path is unchanged — §3 item 6 |
| Should-fix 1 — the sweep missed `tests/test_playbook.py:689` | closed | `da1ffb3` (wording fixed; the file is now read) |
| Should-fix 2 — circular U6 tests; the vacuous `check` half | closed | `da1ffb3` (rendered doctor output, rule 8 text; the half removed) |
| Should-fix 3 — a unit commit carried the report draft via `git add -A` | closed | `b77bc4d` (`.gitignore` `meta/drafts/`); this mission's commits stage explicit paths and list every file (§4) |
| Should-fix 4 — the UTF-8 check and the size measurement walk different trees | closed | `b29b1c7` |
| Should-fix 5 — positionals refused under invented flag names | closed | `b29b1c7` (label "a job/path/prompt argument"; §3 item 9) |
| Should-fix 6 — DESIGN §11's self-contradiction not in FINDINGS.md | closed by the design | DESIGN v3.6 §11 rewritten by the architect (§23 bullet 1); no builder change, and no H-number is needed for a contradiction that no longer exists |

---

## 4. Acceptance, checked

- `./scripts/check` green on the pushed tip, three consecutive runs:
  at `dfd9e6c` (gate inputs = `f96938e`), 1235 passed in 65.39s, 71.30s,
  63.94s, ruff clean, cli smoke, `check: green` each; and again three times
  before U6's commit (the journal's U6 line carries those runs).
- No commit in this mission carries a file its body does not list:
  a script over `git rev-list db0bd2c..HEAD` compared each commit's
  `git show --name-only` with its body — 12 commits (`169ce88` through
  `dfd9e6c`), 0 with an unlisted file — and U6's commit lists its four files.
  Every `git add` in this mission named explicit paths.
- `README.md` and `docs/` contain no sentence saying the wake-path question is
  open or that doctor prints a wake procedure: the U3 sweep reads both and is
  green; `grep -rni 'open question|prints the procedure|wake procedure|wake-path
  question' README.md docs/` finds nothing.
- `hands doctor` shows `CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0` for both roles
  on a config that does not set it: pinned by U1's test through the CLI, and
  driven by the builder with `uv run hands --project hands doctor` (text and
  `--json`) against `~/.hands/hands.toml`, which has no `env` table.
- `meta/FINAL-REPORT-7.md` exists with NOT PROVEN (§3) and the table under
  `## Review items`.

---

## 5. For the architect

1. **`SendMessage` is the harness-termination path the decision does not
   close** (H-014, §3 item 2). Options: forbid continuing a sub-agent in role
   sessions (CLAUDE.md and the hook, refusing `SendMessage` whose target is a
   sub-agent — it would also block messaging teammates), or observe once what
   a `-p` turn does with the ceiling at 0 when such a sub-agent reports back.
2. **`failure_reason` in the inbox.** The `job.failed` event does not carry it,
   so a playbook rule cannot tell `harness_terminated` from `nonzero_exit`
   without reading the job. Whether §10 should distinguish them is a design
   call.
3. **The installed build** is still mission 2's; the first real run of U1's
   classification will be when it is reinstalled.
