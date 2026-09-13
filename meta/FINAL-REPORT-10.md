# FINAL-REPORT-10 — hands mission 10: the closed loop and the architect's tools

Mission: `meta/BUILDER-10-PROMPT.md`. Design: `DESIGN.md` v3.9, §26 (with §4,
§6, §8, §10, §11, §13). Review closed: `meta/reviews/REVIEW-9.md` (`VERDICT:
review mission 9 blockers=0 should-fix=4`) should-fix 1–4. Findings: H-018
filed (U0; its three gaps closed by U1 and U2), H-019 filed (U2; status line by
U5), H-020 filed (U4; open), H-021 filed (U5; open). H-017 gets a dated
correction line (U0). H-001 and H-009 stay open.

Base `61e1486` (`plan: mission 10 kit (DESIGN v3.9, handbook, templates)`) was
green: 1435 passed, three consecutive runs before U0's commit.

Tip `7c5e854` (U6, the last commit that changes a gate input; the U7 commit
that carries this report is meta only): **1549 passed**, `check: green`,
three consecutive runs by the builder before the U7 commit. Each unit's
sub-agent ran `./scripts/check` green three consecutive runs before its own
commit, and the builder ran three more before each `meta:` commit that
followed it.

**Mission 10 is blocked on U4.** Eight units planned (U0–U7). Seven landed.
U4 (who by pid) stopped on a design premise the disk contradicts: no Claude
Code transcript records a pid (H-020). The sub-agent filed the memo instead of
improvising, as the brief's sub-agent rules require. U4 was not retried: a
second run under the same rules stops at the same memo, and the fix is a
DESIGN revision, not a better attempt. U5–U7 do not depend on U4 and ran.

Every product unit is one commit; U4's commit carries only the H-020 memo.
Each of U0–U5 is followed by a `meta:` bookkeeping commit that touches only
`meta/plan.md`, `meta/CHECKPOINT.md` and `meta/journal.md`. U6's bookkeeping
rides in U7's commit together with this report. U0 is a `plan:` commit. The
report was drafted under `meta/drafts/` and moved in by U7's commit. Every
`git add` named explicit paths.

One deviation, recorded in `meta/plan.md`: REVIEW-9 should-fix 2 has a code
half. §26 asks only that `docs/INTEGRATION.md` match §6, but §6 fails a result
of subtype `error` and the runner did not. A doc that follows §6 over code
that does not would overclaim, so U1 also changed the runner (H-018 gap 3).
Between `cbb8fc8` and `17ba97e` the doc was ahead of the code by that one case.

This report is a snapshot. Per DESIGN §20, a claim here that later expires is
corrected by an appended dated line, never by a rewrite.

---

## 1. What changed, by unit

**U0 — `cbb8fc8` `plan: mission 10 U0 — plan, review 9 should-fix 2 and 4,
H-018`** (§6, §26; REVIEW-9 should-fix 2, 4). `meta/plan.md`,
`meta/CHECKPOINT.md`. `docs/INTEGRATION.md`'s "How a job ends" now states
§6's rule: a result of subtype `error` (claude's `error_*` family) is failed
whatever `is_error` says, and `done` is what remains. H-017 gets an appended,
dated correction: v3.7 §6's `gate` had no `quote?`. H-018 records §26's
decisions and three gaps §26 leaves: `origin: phone` is outside §6's list; a
`phone` job would not un-pause a stopped pipeline, so a `go` after a stop
would not chain the review; and should-fix 2's code half.

**U1 — `17ba97e` `runner, playbook: tie group kills to the job's group; clean
git env; error subtypes fail`** (§6, §10, §26; REVIEW-9 should-fix 1, 2, 3;
H-018 gap 3). `src/hands/runner.py`, `src/hands/monitor.py`,
`src/hands/playbook.py`, `tests/test_runner.py`, `tests/test_playbook.py`.
- Should-fix 1: at spawn the runner records claude's process start time. A
  group kill goes ahead only when no process holds claude's pid, or the
  holder started at the recorded time. This replaces the membership check, in
  `_last_resort` and also in the post-exit sweep, which had the same gap after
  claude was reaped. The misleading comment is corrected.
- Should-fix 3: `git show HEAD:<path>` runs with `GIT_DIR`, `GIT_WORK_TREE`
  and `GIT_INDEX_FILE` removed from the child environment and
  `-c core.autocrlf=false`. Both sides are compared with CRLF read as LF.
- Should-fix 2, code half: a final result whose subtype is `error` or
  `error_*` is `error_result` whatever `is_error` says.

**U2 — `067b8fd` `playbook, phone: [series] kickoff and `go <secret>` from the
phone`** (§6, §10, §11, §26; H-018 gaps 1, 2; H-019). `PLAYBOOK.toml`,
`docs/INTEGRATION.md`, `docs/PLAYBOOK.md`, `meta/findings/FINDINGS.md`,
`src/hands/api.py`, `src/hands/phone.py`, `src/hands/playbook.py`,
`src/hands/spool.py`, `tests/test_library.py`, `tests/test_phone.py`,
`tests/test_playbook.py`.
- TOML cannot hold `series = "…"` beside a `[series]` table, so the
  templates as the kit shipped them did not parse. The loader takes `[series]`
  with `name` and `kickoff`, and refuses any other key and blank values
  (§20). The top-level `series = "…"` string still loads when there is no
  table, so §10's example is unchanged. A file with both is refused as invalid
  TOML. Filed as H-019.
- `go <secret>` on `cmd_topic` sends `[series] kickoff` as a `clear` send to
  the builder with `origin: phone`, and answers on `ntfy_topic` with the job
  id. It is refused, with a logged reason, when no playbook is loaded, when
  the playbook has no kickoff, or when the builder has a running or queued
  job. A paused playbook still counts as loaded.
- `phone` joins `ORIGINS` and `UNPAUSE_ORIGINS`, under the same "only when the
  job starts" rule as `cli`.
- Root `PLAYBOOK.toml`: `[series] name = "hands-missions"`, `kickoff = "Read
  meta/BUILDER-11-PROMPT.md and execute the mission below its divider."`.
- The sub-agent ran its three gate runs in a throwaway worktree holding an
  unpushed commit of the same files. The root-playbook tests load only a
  `PLAYBOOK.toml` that matches HEAD, so they cannot pass on an uncommitted
  change. It then committed on main after checking the trees were identical;
  the worktree is gone.

**U3 — `6852751` `phone, config: `kit <secret>` fetches an ntfy attachment
into [files] kit_dir`** (§11, §13, §26). `src/hands/phone.py`,
`src/hands/config.py`, `src/hands/spool.py`, `docs/INTEGRATION.md`,
`tests/test_phone.py`, `tests/test_config.py`, `tests/test_docs.py`.
- `kit <secret>` with an ntfy attachment: `attachment.url`, `name` and `size`
  are read from the message.
- Refused before fetching: a name that is not a lowercase `.zip` basename
  (names are refused, never rewritten), a reported size over `[files]
  kit_max_mb` (default 20, MiB), a missing or non-integer size, and a
  `kit_dir` outside the allowed roots (checked on arrival, not at config
  load).
- The cap is also enforced while streaming. Redirects are not followed.
- The fetch goes to a temp file in `kit_dir`, then an exclusive `os.link` to
  the first free name (`<stem>-1.zip`, `-2`, …), then the temp is deleted.
  Nothing is unzipped, executed or made executable.
- `kit.received` is added to the spool's event kinds and filed with name,
  bytes and sha256. The notification reads `kit received <name> <bytes>
  <sha256>`.

**U4 — `9f7effd` `findings: H-020 no transcript records a pid; who-by-pid
blocked on DESIGN`** (§26). `meta/findings/FINDINGS.md` only. **Blocked.**
- On claude 2.1.270 the first lines of all 470 transcripts on this machine
  hold only `type`, `sessionId` and one of four entry kinds. None of 138,369
  transcript lines has a pid-like key, and the pids of the three running
  `claude` processes appear in no transcript.
- The pid lives in `~/.claude/sessions/<pid>.json`, whose `sessionId` names an
  existing transcript for all three. A handsd job writes one too; only
  `entrypoint` told them apart (`sdk-cli` for the job, `cli` for the humans).
- The builder spot-checked this: `~/.claude/sessions/` holds `<pid>.json`
  files, and the newest hands transcript's first line has keys `content,
  operation, sessionId, timestamp, type`, with no `"pid"` in its first 50
  lines.
- No code changed. `hands who` still matches by directory, and the docs say so.

**U5 — `9e962a4` `kit: `hands kit check <zip|dir> [--repo path]`; templates
and handbook against the code`** (§4, §10, §26; H-019; H-021).
`src/hands/kit.py` (new), `src/hands/cli.py`, `tests/test_kit.py` (new), a
byte-for-byte copy of the ten mission 10 kit files under
`tests/fixtures/kit-mission-10/`, `tests/test_docs.py`,
`templates/PLAYBOOK-missions.toml`, `templates/PLAYBOOK-runs.toml`,
`docs/ARCHITECT-HANDBOOK.md`, `meta/findings/FINDINGS.md`.
- Six checks, one line each, and exit 0 only when all pass:
  - paths: every entry is a repository path under the repo;
  - playbook: the kit's playbook loads under the engine (no HEAD check), sets
    no `quiet_hours`, and its kickoff equals the brief's; with no kit playbook
    the repo's is in force;
  - brief: the kickoff line and the final-reply literals, read across wrapped
    lines;
  - verdicts: checked both ways;
  - wording: no "as before" and no "Budget guidance";
  - protocol: every file a `send` names exists in the kit or the repo.
- It prints the apply prompt (handbook §3), naming what the kit replaces and
  adds, and a commit message. It needs no daemon and no network.
- H-021: as §26 is written, the verdict check fails on this repository's own
  playbook. The `aux.done` review rules match nothing in a builder brief, and
  not the review protocol's line either, because placeholders stay literal.
  The check therefore matches `builder.done` rules only, both ways, and counts
  the others on the `verdicts` line without failing on them. A `builder.done`
  rule that matches no brief literal passes only if it matches `VERDICT: kit
  applied <sha>`, the reply the printed apply prompt asks for. Handbook §11
  says exactly this.
- The templates move the series name into `[series] name` (H-019 status line),
  and handbook §6 and §11 match the code.

**U6 — `7c5e854` `docs: the closed phone loop in INTEGRATION; doctor `go` and
`kit transport` rows`** (§4, §11, §26). `src/hands/doctor.py`,
`tests/test_doctor.py`, `tests/test_docs.py`, `docs/INTEGRATION.md`,
`README.md`.
- `hands doctor` gains `go` and `kit transport` rows. Both have status `ok`,
  print on or off, name what is missing when off, and print neither a topic
  nor the secret.
- `docs/INTEGRATION.md` gains "The closed loop, from the phone", in six
  steps:
  1. `hands kit check`;
  2. send the kit with `kit <secret>`;
  3. the `kit received …` buzz;
  4. the apply send comes from the laptop or the driver, because nothing on
     the phone can start it;
  5. approve with the button;
  6. `go <secret>`, then wait for the stop buzz.

  The driver is the inspector, never required.
- `README.md` names `kit check`, `go`, the kit transport and the handbook.

## 2. What the tests prove

Test counts: 1435 → 1443 (U1) → 1461 (U2) → 1501 (U3) → 1501 (U4, memo) →
1538 (U5) → 1549 (U6). Each sub-agent reports its new tests red before its
product change.

- **U1.**
  - An `error_max_turns` result, and the other `error` subtypes tested (3
    cases), with `is_error: false`, `num_turns` and exit 0: all were `done`
    before and are `failed`/`error_result` now.
  - A reused group (the pid held by a process whose start time differs from
    the recorded one) is killed by the parent code; with U1 neither
    `_last_resort` nor the sweep kills it.
  - A group whose leader is still the spawned process is killed, and the
    leftover members of a reaped leader's group are killed.
  - A cancelled `run()` is cleaned up through its exception path.
  - A CRLF checkout of an LF-committed playbook is refused as dirty by the
    parent and loads with U1.
  - `GIT_DIR` pointing at another repository whose HEAD has an identical
    file, with the playbook untracked: the parent loads it, U1 refuses it.
- **U2.** 18 tests.
  - `go` refused for: no playbook; no kickoff; builder running; builder
    queued; bad, missing or nonce token. None creates a job or answers, and
    none logs the secret.
  - `go` happy path: one builder job, `clear`, `origin: phone`, prompt equal
    to the kickoff, the job id answered on `ntfy_topic`, the secret absent
    from publishes, spool and log.
  - `go` after a stop is accepted, its job un-pauses the pipeline when it
    starts, and its `builder.done` then fires a rule.
  - Loader: six `[series]` refusals, both series forms loading, the
    both-forms refusal, the root playbook's kickoff.
  - Origins: a `phone` job un-pauses only when it starts; `--origin phone` in
    the library tests.
- **U3.** 40 tests, against a mocked ntfy stream and a real HTTP server on
  127.0.0.1.
  - Happy path: bytes, name, no execute bit, no temp file left, the inbox
    event, the notification text with sha256, the secret nowhere.
  - Refused with the server never hit: oversize by reported size, 14 bad
    names, missing or wrong secret, no attachment, bad size, bad URL,
    `kit_dir` outside the roots.
  - Refused after fetch, leaving nothing behind: a body over the cap while
    streaming, and a body shorter than its reported size.
  - Duplicate names become `-1`, then `-2`, with the original unchanged.
  - The daemon answers `hands status` while a download is held open.
  - Config defaults, accepted values and refusals for `kit_dir` and
    `kit_max_mb`.
- **U5.** 37 tests.
  - A passing kit as a directory and as a zip; `--json`; the `--repo`
    default and its errors; failing kits for each of the six checks.
  - The mission 10 kit copy passes; the filled missions templates and the
    filled runs playbook pass.
  - `hands --help` lists `kit`, and handbook §11 names every check.
- **U6.** 8 doctor tests (`go`: no channel, no playbook, no kickoff,
  playbook that does not load, on; `kit transport`: no channel, `kit_dir`
  outside the roots, on) and 3 docs tests. The docs tests pin the loop
  section's statements, the README lines, and `hands kit --help` working
  without a daemon.

## 3. NOT PROVEN

1. **Real ntfy attachment delivery.** No kit was ever fetched from a real ntfy
   attachment. The stream is mocked and the attachment is served from
   127.0.0.1. The curl command in `docs/INTEGRATION.md` and the ntfy app's
   attach flow are unrun.
2. **A real `go` from a phone.** The `go` command is proven only against the
   mocked stream. No phone, no real `cmd_topic`, no real answer on
   `ntfy_topic`.
3. **The closed loop end to end** (kit, apply, approve, `go`, review, stop
   buzz) has never been run. Each step is tested alone.
4. **Who by pid is not built** (U4, H-020). `hands who` still attributes by
   directory, so a handsd job's transcript in the human's working directory
   can still be shown under the human's session. The sessions-file source is
   observed on claude 2.1.270 and three processes only; its format is
   undocumented, and whether `entrypoint` always separates a job from a human
   is unknown.
5. **U1, should-fix 1.**
   - The kernel never reuses a pid in the tests; reuse is simulated by
     recording a start time one tick early.
   - Check-then-kill is two steps, so a race between them remains.
   - If the start time cannot be read at spawn, the group counts as not the
     job's own whenever a process holds the pid, so a real group would then
     be left alive.
   - Per-job systemd scope mode is untested.
6. **U1, should-fix 3.**
   - Other `GIT_*` variables (for example `GIT_OBJECT_DIRECTORY`) are still
     inherited.
   - A playbook committed as a symlink is still refused as dirty. REVIEW-9
     named this, but the brief did not, so it is untested and unchanged.
   - The git timeout path is untested.
7. **U2.**
   - A kickoff line that matches a gate pattern (so `go` would produce a held
     job) is untested.
   - The queued refusal is exercised by calling the handler directly after an
     enqueue, not through the stream.
8. **U3.**
   - The phone channel reads no other command while a kit download runs (up
     to 300 s), so an approve button pressed during a download waits. This is
     untested.
   - A filesystem without hard links would refuse every kit; untested.
   - The timeout, HTTP-error and write-failure paths are untested.
   - A crash between link and unlink leaves a hidden `.hands-kit-*.part`.
   - The `kit_dir`/`kit_max_mb` bad-value config tests would also have passed
     before U3, because unknown keys were already refused.
9. **U5.**
   - `aux.done` (review) verdict regexes are checked against nothing (H-021).
   - The runs form is tested only with a stub `WORKPLAN.md`.
   - `hands kit check` has not been run from a fresh `uv tool install
     git+https://github.com/SigorMatt/hands`, which is what the handbook tells
     an architect to do.
   - A kit with no brief (a decisions-only kit) always fails the brief checks.
   - The protocol check sees only `.md`/`.toml` paths named in a prompt.
10. **U6.** Doctor does not check that `kit_dir` exists or is a directory, nor
    whether a builder job is running or queued (which would refuse `go`).
    The loop section is pinned as statements; that each step works as written
    is item 3.
11. **Base to U1 window.** Between `cbb8fc8` and `17ba97e` the INTEGRATION
    doc described §6's `error` rule while the runner still said `done` for
    an `error_*` subtype with `is_error: false`.

## Review items

| Item | Unit | Commit | Status | Evidence / limit |
|---|---|---|---|---|
| REVIEW-9 should-fix 1: the REVIEW-8 SF3 check cannot prevent the kill it guards | U1 | `17ba97e` | closed, with limits | The kill is tied to claude's recorded start time, in `_last_resort` and the sweep. A reused group is killed by the parent's code and spared by U1's. Reuse is simulated, check-then-kill is not atomic, and an unreadable start time spares a real group (§3 item 5). |
| REVIEW-9 should-fix 2: INTEGRATION's `done` statement disagrees with the runner | U0 + U1 | `cbb8fc8`, `17ba97e` | closed | U0: the doc states §6's rule. U1: an `error`/`error_*` subtype is `error_result` whatever `is_error` says; 3 cases were `done` before U1. |
| REVIEW-9 should-fix 3: the git check inherits `GIT_*` and compares raw bytes | U1 | `17ba97e` | closed for the named variables and CRLF; symlink open | `GIT_DIR`/`GIT_WORK_TREE`/`GIT_INDEX_FILE` scrubbed and `-c core.autocrlf=false`; a foreign `GIT_DIR` is refused and a CRLF checkout loads, both red on the parent. Other `GIT_*` are inherited; a committed symlink is still refused (§3 item 6). |
| REVIEW-9 should-fix 4: H-017 misquotes v3.7 | U0 | `cbb8fc8` | closed | A dated correction line is appended to H-017; nothing is rewritten. |

## 4. Acceptance, checked

- **`./scripts/check` green on the pushed tip, three consecutive runs:** tip
  `7c5e854`, 1549 passed ×3, `check: green`, run by the builder before the U7
  commit (which is meta only).
- **Every unit commit's body lists every file it touches; U0 is `plan:`:** a
  script compared `git show --name-only` with each body over
  `61e1486..7c5e854` (13 commits): unlisted files: none, for every commit.
  `cbb8fc8`'s subject begins `plan:`.
- **`hands --help` lists `kit`; `hands kit check` on this mission's kit files
  exits 0:**
  - `uv run hands --help` has the `kit` row.
  - The builder ran `git archive 61e1486` over the ten kit files into a temp
    dir and ran `uv run hands kit check <dir>`: six `PASS` lines, then `kit
    check: pass (6 of 6 checks)`, exit 0.
  - The verdicts line reports the two `aux.done` rules as not matched against
    the brief (H-021).
- **`PLAYBOOK.toml` carries `[series] kickoff` naming BUILDER-11:** `[series]
  name = "hands-missions"`, `kickoff = "Read meta/BUILDER-11-PROMPT.md and
  execute the mission below its divider."`.
- **`meta/FINAL-REPORT-10.md` exists with NOT PROVEN and the review-items
  table:** this file, §3 and `## Review items`.
- **Not met:** the U4 promise (who by pid, with its two-transcripts fixture).
  Hence the verdict `mission 10 blocked U4`.

## 5. For the architect

1. **H-020 (blocks U4).** Name the pid source for `hands who`. The observed
   source is `~/.claude/sessions/<pid>.json` → `sessionId` → transcript. The
   design also needs to say what happens when the file is missing, and
   whether `entrypoint` (`sdk-cli` vs `cli`) may separate a job from a human
   session. Alternatively, drop the pid premise: §26 says the transcript's
   first line records the pid, and it does not. The sessions directory also
   holds a `.key` file per process; the design should say hands never reads
   it.
2. **H-021.** Decide what `kit check` matches `aux.done` review regexes
   against: the review protocol's verdict line with its placeholders filled,
   or a vocabulary line the review prompt must carry. Today they are
   reported and not checked.
3. **H-019.** §10's example uses `series = "…"`, and §26 adds `[series]
   kickoff`; both cannot share a file. The code takes `[series] name`. The
   next DESIGN revision should show that form, and fix §13/§10 wording that
   implies a string key.
4. **H-018 gaps 1 and 2.** §6's `origin` list lacks `phone`, and §10's
   un-pause rule names only `cli`. The code adds `phone` to both, so that a
   `go` after a stop chains the review.
5. **The phone channel during a kit download.** Commands, approve buttons
   included, wait up to 300 s. Decide whether downloads move off the command
   loop.
6. **A decisions-only kit** (no brief) cannot pass `kit check`. Decide
   whether the brief checks apply only when a brief is present.
7. **REVIEW-9 should-fix 3's symlink case** is still refused as dirty; decide
   whether a committed symlink playbook is supported.
8. **The apply send cannot start from the phone.** The loop needs the laptop
   or the driver for step 4 (INTEGRATION). If the loop is to be phone-only as
   §26 says, the design needs a way to start the gated apply from the phone
   (for example, `kit` filing the apply send itself, held).
