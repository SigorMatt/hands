# FINAL-REPORT-24 — M8a: the harness probe and the seam's shape; the day's findings; operations

VERDICT: mission 24 finished pr=<pending>

Brief: meta/BUILDER-24-PROMPT.md. Design: DESIGN v3.23 §40 (with §2, §23,
§33, §35, §38, §39). Review read: meta/reviews/REVIEW-23.md (`reviewed:
94ab38c`, blockers 0, should-fix 9); docs/RELATED.md;
docs/QODO-EXTRACTION.md. Shape: pull request. The branch `mission-24` was
created from `main` at de407f2 (`plan: mission 24 kit (DESIGN v3.23)`);
every unit committed and pushed to it; this unit opens the pull request
`mission-24` → `main`, reads the hosted review with `hands hosted-review`
and fixes its findings in the same pull request. Not built, as the brief
says: the backend seam, credential profiles, the polish round, any M9
command (missions 25, 26; §41 is written from docs/HARNESS-PROBE.md).

## 1. What changed (sha per unit)

- U0 f959c62 (`plan:`): meta/plan.md, meta/CHECKPOINT.md, meta/journal.md,
  meta/findings/FINDINGS.md — H-062..H-069 filed; H-064, H-065 decided
  (§40); H-061 decided (§40, U6); H-051's Status line corrected to the
  narrower read roots. Green 3/3, 4504 passed.
- U1 f558f0f (`docs:`) — docs/HARNESS-PROBE.md (added), from a scratch
  repository under /tmp, PATH prefixed with the nvm Node v22.23.3 bin.
  Versions: codex-cli 0.163.0, opencode 1.19.2, dsh 0.2.0-rc.2. Codex
  (signed in, ChatGPT) probed live: one-shot `codex exec --json`, resume,
  VERDICT first line verbatim. On this laptop Codex's bundled bwrap fails to
  start (`loopback: Failed RTM_NEWADDR`), so `workspace-write` and
  `read-only` block every command; under `danger-full-access` both `touch
  /tmp/outside-probe` and `curl --version` ran unasked; under
  `workspace-write` Codex still answered `VERDICT: probe ok` without writing
  `probe.txt`. OpenCode: signed in to a provider, no default model —
  `unavailable: no model configured` on every live row; ACP built in
  (`opencode acp`). dsh: `DEEPSEEK_API_KEY` unset, `~/.dsh` absent —
  `unavailable: not signed in` on every live row; usage-limit codes,
  `DSH_TELEMETRY_DISABLED`, the session-log plugin's `enabled` switch and
  `--profile acp` recorded from the installed package. `grep -c redacted
  docs/HARNESS-PROBE.md` = 3. Green 3/3, 4504.
- U2 b003bee (`cli:`) — `hands go` and `hands kit apply <zip>`: the phone's
  `go` and `hands go` share `Api.kickoff(origin)` (registered in
  `Api.OPERATIONS`, since `Api.COMMANDS` is pinned to §4's table;
  `Api.go_builder` removed); `Api.kit_apply` runs the kit check, copies the
  zip into `[files] kit_dir` (a same-bytes file there is filed where it is,
  another file of that name is refused), and files a held builder job
  `origin: kit`. Files api.py, cli.py, kit.py, phone.py, README.md,
  tests/test_operations.py (added), test_docs.py, test_gates.py,
  test_phone.py. Green 3/3, 4511.
- U3 6f373cd (`monitor:`) — H-062, H-063: `task_killed` raised once per
  (session, task id) across scans (bounded 1024-entry memory) and not for a
  job the daemon is stopping (logged; the record is `orphaned`);
  `transcript_path_for` takes the job's environment (handsd's environment
  with the role's `env` on top): `$CLAUDE_CONFIG_DIR/projects/…` when set
  and non-empty (relative taken from the role's cwd), else
  `~/.claude/projects/…`; the path is recorded in the job record when claude
  reports its session, before the first scan. Files monitor.py, runner.py,
  daemon.py, tests (conftest, fake_claude, fake_monitor, test_monitor,
  test_runner), FINDINGS.md. Green 3/3, 4518.
- U4 8c081d0 (`hosted:`) — should-fix 3, 4, 5: a review body and an inline
  comment headed "Code Review" are ignored; of two Code Review issue
  comments the newest wins; header 1 with its only finding struck exits 4;
  `match_job_id` quotes the typed id with `str` in backticks, not `repr`.
  Files api.py, tests/test_hosted.py, tests/test_phone.py. Green 3/3, 4523.
- U5 24ac73d (`daemon:`) — should-fix 6, 7, 8, 9: the commit-the-journal
  sentence is decided when the job starts (git in a worker thread); a held
  job is stored and announced with the human's prompt alone; `hands go`
  kickoffs exempt (in-memory set of job ids). docs/INTEGRATION.md says what
  `_decide` does with a malformed nonce line. Architect rule 2 pinned.
  `project add` dry run `git clone -- <url>` and a failing `remote set-url`
  pinned. Files api.py, daemon.py, runner.py, docs/INTEGRATION.md, tests
  (test_phone, test_operations, test_kit, test_docs, test_project_add).
  Green 3/3, 4530.
- U6 529b91f (`playbook:`) — H-061: `playbook.orphaned_rule_warnings`
  shared by `hands kit check` (a `WARN playbook: …` line after the six
  lines, and a `warnings` key in `--json`) and the engine's load (a log
  line at each load); the check still passes 6/6. Files playbook.py,
  kit.py, docs/PLAYBOOK.md, tests/test_kit.py, tests/test_playbook.py,
  FINDINGS.md. Green 3/3, 4542.
- U7 649417d (`templates:`) — H-066, H-068, H-069, H-067's protocol half:
  the brief template's `refused:` rule and `[b] refused` rule; rule 8's "a
  unit no agent will author" → `VERDICT: escalate ruling: human-supplied
  content`; both protocols start with `git worktree prune` and the removal
  of stale review worktrees under /tmp, end by removing their own; the new
  skip list; "run `./scripts/check` once, in the foreground, and report only
  when every command has finished"; handbook §7, §17. Files
  templates/BUILDER-N-PROMPT.md, architect/CLAUDE.md,
  templates/REVIEW-PROTOCOL.md, meta/REVIEW-PROTOCOL.md,
  docs/ARCHITECT-HANDBOOK.md, tests/test_kit.py, FINDINGS.md. Green 3/3,
  4576.
- U8 c6b70c1 (`ops:`) — docs/OPERATIONS.md (added): the inventory (spool
  entries classified against `hands.spool`), the secrets table (no values),
  the five runbooks; scripts/capture-quota-stop.sh (added; read-only but
  for its one mode-600 output file, works with the daemon down, redacts by
  fixed string and by pattern); `hands doctor` `worktrees` WARN row
  (H-067). Files doctor.py, tests/test_runbook.py (added), test_doctor.py,
  test_docs.py, FINDINGS.md. Green 3/3, 4614.
- U9 6fc7e6e (`docs:`) — INTEGRATION: pointers to OPERATIONS, RELATED,
  HARNESS-PROBE; the nvm PATH note (a role's PATH replaces handsd's and is
  not expanded, so the note gives a full value); the transcript path under
  `CLAUDE_CONFIG_DIR`; doctor's `worktrees` row; the kit-check WARN; `hands
  go` and `hands kit apply`. Handbook §11 (WARN) and §18 (`go`, `kit
  apply`, OPERATIONS, RELATED). README names the new docs. phone.py
  docstring corrected to `_decide`'s behaviour (docstring only). Files
  docs/INTEGRATION.md, docs/ARCHITECT-HANDBOOK.md, README.md,
  src/hands/phone.py, tests/test_docs.py. Green 3/3, 4625.
- U10 (`report:`) — this report; the pull request; the hosted review.

## 2. What the tests prove

- `hands go` sends the playbook's kickoff as a `clear` builder job with
  `origin: cli`, and is refused naming the held builder job while one is
  held, and when the playbook has no kickoff (U2).
- `hands kit apply` of a failing kit prints its FAIL lines, files no job
  and copies nothing; of a passing kit copies it into `kit_dir` and files a
  held job `origin: kit` whose prompt equals the check's apply prompt, and
  `hands approve` releases it; an existing other file of that name is not
  overwritten (U2).
- The same killed task across three scans raises `task_killed` once; two
  tasks raise twice; a daemon stop leaves the job `orphaned`/`daemon_stop`
  with no raise, while a cancel of the same fake raises once (U3).
- A role whose `env` sets `CLAUDE_CONFIG_DIR` has its transcript path
  recorded under it, the fake claude wrote there, and the ops monitor read
  its first line through the daemon (U3).
- The hosted-review verdict ignores a review body and an inline comment
  headed "Code Review", takes the newest Code Review issue comment, and
  exits 4 when the header counts one and the only finding is struck; each
  test is red under the review's named mutation (U4).
- A secret with backslashes typed as a job id: no substring of 4 or more
  characters appears in any published title or message or in the log (U4).
- The journal sentence: dirty at enqueue and committed before approval
  gives no sentence; the reverse gives it; the held prompt is the human's
  alone in both (U5).
- Architect rule 2's text is pinned (red with architect/CLAUDE.md at
  2b4df10~1); `project add`'s dry run prints `git clone -- <url>`; a failing
  `remote set-url` is a failed clone with cleanup and a working re-run (U5).
- Each orphaned pairing warns once in `kit check` (still 6/6) and once at
  the engine's load; both rules present warn nothing; the two templates and
  this repository's PLAYBOOK.toml warn nothing (U6).
- Every new protocol, brief-template, rule 8 and handbook sentence is
  pinned (36 pins, red before the edit); the protocol files differ only in
  the forge names; prune comes first and the removal last (U7).
- OPERATIONS.md: headings in order, the secrets table's columns and one row
  per kind, spool rows matching `hands.spool` each classified, a no-phone
  row per phone and who command, no match for 16 enumerated credential
  shapes (each checked against a planted sample) (U8).
- The capture script, against a fake `hands`/`journalctl` and a fake spool
  with planted secrets (one with regex metacharacters and a backslash),
  writes a mode-600 file with every section naming none of them, raw or
  JSON-escaped, and changes nothing else under HOME (U8).
- `hands doctor` warns on the deleted worktree only, is ok after `git
  worktree prune` (U8).
- Each U9 sentence is in its doc with a check of the code behind it (U9).

## 3. NOT PROVEN

- No real harness ran in the tests; the probe is the only real run, and it
  ran in a shell, not as a job handsd spawned under systemd.
- The probe's rows that are `unavailable` or `partial`: every live row of
  OpenCode (`unavailable: no model configured`) and of dsh (`unavailable:
  not signed in`); Codex's readable stream (`partial`: a command the
  sandbox failed to start left no `command_execution` item); Codex's
  enforceable permission is `no` on this laptop (bwrap cannot start; the
  only writable mode ran `touch` and `curl` unasked). Unobserved: Codex
  under a working sandbox, Codex approval events (`-a on-request`), any
  harness at a real usage limit, any harness speaking ACP, Codex's
  telemetry keys (inferred from binary strings). So §40's ACP condition
  ("each harness routes shell commands through permission requests") is
  unobserved for all three.
- `hands go` refused while a builder job is running or queued is proven
  only through the phone's tests of the shared code (U2).
- A real claude emitting kill notices on SIGINT; `~` in
  `CLAUDE_CONFIG_DIR` (used as written); the built-in stall monitor on the
  moved transcript (U3).
- The "is ambiguous" reason with the secret typed; other refusal reasons
  quoting typed text (U4).
- A `hands go` job held across a daemon restart: the kickoff exemption is
  an in-memory set, so after a restart it is treated as a send and gets the
  journal sentence if the journal is dirty (U5).
- The engine's WARN line in a running handsd's log; the phone's kit path
  showing it (U6).
- A reviewer following the new protocol rules; cleanup on a real aborted
  review (U7).
- A real usage-limit stop captured; any runbook carried out on a real
  migration or install; the notification password's location
  (`~/.hands/ntfy.password`) is observed on the laptop, not named by the
  code (U8). Linger is off on the laptop.
- A harness installed under nvm running under handsd with the PATH note's
  value (U9).

## Deviations

- U1: the sub-agent's first two gate runs were one call that passed the
  20-minute limit and was moved to the background by the tool; it stopped
  that and ran the third in the foreground (H-069's shape, in the builder).
  Every later unit ran three separate foreground calls.
- U2: `go` sits in `Api.OPERATIONS`, not `Api.COMMANDS` (pinned to §4).
- U3: the 2026-10-16 bursts were mostly distinct task ids (each followed by
  its `playbook.rule` line), so three distinct killed tasks in one job still
  raise three times; only repeats and the daemon-stop raise are removed.
- U4: no fixture files were added; the new cases are built in a temp
  directory from the recorded pages, as the existing hosted tests are.
- U5: one progress test now waits for the running job's start time (a 1-in-3
  flake made wider by the check before start).
- U9 changed src/hands/phone.py's docstring (carried from U5; no behaviour).

## Review items

| REVIEW-23 item | What | Closed by |
|---|---|---|
| Should-fix 1 | §39's lenient ids named `answer` and `reply` | H-064, decided in §40 (U0 f959c62) |
| Should-fix 2 | the architect's read roots narrower than §39 | H-065, decided in §40; H-051 Status corrected (U0 f959c62) |
| Should-fix 3 | "the verdict from the Code Review comment only" unpinned | U4 8c081d0 |
| Should-fix 4 | exit 4 half-proven | U4 8c081d0 |
| Should-fix 5 | the secret redaction bypassed by a backslash | U4 8c081d0 |
| Should-fix 6 | the journal reminder decided at enqueue | U5 24ac73d |
| Should-fix 7 | INTEGRATION says a malformed nonce line is answered | U5 24ac73d (doc), U9 6fc7e6e (docstring) |
| Should-fix 8 | architect rule 2 held by no test | U5 24ac73d |
| Should-fix 9 | `--` in the dry run and the set-url failure unpinned | U5 24ac73d |

## Findings

| Finding | Status | Unit |
|---|---|---|
| H-061 | resolved-by-code | U6 529b91f |
| H-062 | resolved-by-code | U3 6f373cd |
| H-063 | resolved-by-code | U3 6f373cd |
| H-064 | decided (§40) | U0 f959c62 |
| H-065 | decided (§40) | U0 f959c62 |
| H-066 | resolved-by-doc | U7 649417d |
| H-067 | resolved | U7 649417d, U8 c6b70c1 |
| H-068 | resolved-by-doc | U7 649417d |
| H-069 | resolved-by-doc | U7 649417d |

## Hosted review

(pending)
