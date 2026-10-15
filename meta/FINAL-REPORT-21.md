# FINAL-REPORT-21 — closer for review 20

VERDICT: mission 21 finished pr=2

Brief: meta/BUILDER-21-PROMPT.md. Design: DESIGN v3.20 §37 (with §6, §32,
§35, §36). Review read: meta/reviews/REVIEW-20.md (`reviewed: 62f5618`,
blockers 1, should-fix 6). Shape: closer. The branch `mission-20` was
continued with `main` merged in first (5dfab55); every unit committed and
pushed to `mission-20`; no second pull request was opened — PR #2
(`gh pr list --head mission-20 --state open`) is still the branch's open
pull request. Base 1c68883 (`plan: mission 21 kit (DESIGN v3.20)`).
Findings filed: H-046, H-047, H-048 (open, mission 22).

## 1. What changed (sha per unit)

- U0 24aaba3 (`plan:`): meta/plan.md, meta/CHECKPOINT.md, meta/journal.md,
  meta/findings/FINDINGS.md (H-046..H-048). Green 3/3, 4225 passed.
- U1 44f7494 (`runner:`) — the cancel race:
  - `Spool.transition` reloads the record by id and judges the edge against
    the on-disk state; a stale caller gets `IllegalTransition` and nothing it
    carries is written. A `Job` passed in is refreshed in place with what
    was written (design silent; existing callers unchanged).
  - The runner reloads the job after `advance_clone` (and `_git_head`)
    return; when it is no longer `queued` it spawns nothing and raises
    `RunnerError`, which the worker already treats as "nothing to file".
  - Green 3/3, 4227 passed.
- U2 97d1666 (`guard:`) — the live hook and writes through a hardlink:
  - driver/settings.json and architect/settings.json: the hook commands are
    `python3 -I "$CLAUDE_PROJECT_DIR"/.claude/hooks/bash_guard.py` (and
    `--write`).
  - doctor accepts only that form, self-tests the settings' own command
    (via `/bin/sh -c`, the role directory as cwd, `CLAUDE_PROJECT_DIR` set),
    and FAILS the guard row naming any `.py`, `.pyc`, compiled extension or
    package directory beside the guard (`__pycache__` alone and plain files
    stay ok). The old `python3 <guard>` spelling now FAILS: an install must
    copy the new settings files.
  - The `--write` hook refuses a regular-file target with a link count above
    one, and every write while the kits walk reports anything, naming the
    link.
  - Green 3/3, 4251 passed.
- U3 056f044 (`doctor, api:`) — provenance and `doctor --live`:
  - `Api.send` refuses `origin: phone` from a socket client with a message
    naming `answer`. The phone's `go`, which also filed `origin: phone`
    through `Api.send`, now calls a new `Api.go_builder` that is not a
    socket command (design silent on `go`; src/hands/phone.py and
    tests/test_gates.py touched beyond the brief's file list).
  - The architect's live turn passes `--repo <the clone driver_clone
    resolves>` (`.` when the role directory is the clone), FAILS before the
    turn with none, and judges the `hands kit check` only when its argv
    names the live kit's path and that repo (`--repo X`, `--repo=X`,
    `--project X`).
  - The live kit is `kits/hands-doctor-live-<8 hex>`; doctor creates it,
    FAILS without running when the path exists (left untouched), and removes
    only the directory it created. docs/INTEGRATION.md's live paragraph
    follows.
  - Green 3/3, 4258 passed.
- U4 3dc5a32 (`protocol:`) — templates/REVIEW-PROTOCOL.md and
  meta/REVIEW-PROTOCOL.md step 2: in the worktree at the commit,
  `git checkout <sha>~1 -- <the non-test files the body lists>`, run the
  commit's new tests and expect red, then `git checkout <sha> -- <the same
  files>`. Neither file contains "stash" in any case; the files still differ
  only in the forge names. Green 3/3, 4260 passed.
- U5 37d2c51 (`playbook:`) — after the reload on the `builder.done` of an
  apply the engine approved itself, a missing playbook file (no book and no
  load error) stops the pipeline with "the apply removed <configured path>"
  and no rule fires; the stop with the loader's reason for an unloadable
  playbook is unchanged. Green 3/3, 4261 passed.
- U6 (this commit): this report, plan, checkpoint, journal.

## 2. What the tests prove

- U1: a transition from a stale `queued` copy against an on-disk `killed`
  record raises and leaves the file byte-identical. A driver job cancelled
  while a fake `advance_clone` waits on an event ends `killed` with no pid,
  session or start time; the inbox after the cancel is exactly what the
  cancel filed (`job.killed` first, then §28's `consult.done` and `stop`)
  and nothing after it; the worker logs no error. The daemon test is red
  without either half of the change.
- U2: both settings files parse and every hook command starts `python3 -I`.
  With a planted `shlex.py` beside the guard, the hook run as the settings
  command still refuses `rm -rf` and never imports it (the same command
  without `-I` imports it — the witness), and doctor's row FAILS naming it;
  likewise a planted `json/__init__.py` or `re.pyc`. A recording `python3`
  first on PATH shows the self-test runs the settings' exact words. Writes
  to a hardlinked file under `kits/`, writes while another hardlink or a
  symlink sits under `kits/`, and a target whose second link is outside
  `kits/` are refused; a clean `kits/` still passes.
- U3: socket sends with origin phone (builder keep, builder clear, aux
  clear) are refused naming `answer` and file no job. The live check passes
  with the role directory as the clone and fails before the turn with no
  clone; a turn that checks another kit, or the live kit against another
  repo, fails the kit-check step; a pre-existing kit directory of the chosen
  name is left as it was and the row fails; `live_kit_name` yields distinct
  `hands-doctor-live-<8 hex>` names.
- U4: each protocol file, whitespace collapsed, contains the revert sentence
  and no "stash" (red before the edit, red with the old text restored).
- U5: a scripted apply that `git rm`s PLAYBOOK.toml and commits ends with the
  pipeline stopped for exactly "the apply removed PLAYBOOK.toml" and no
  playbook-started builder job (red before: nothing stopped).

## 3. NOT PROVEN

- The cancel race through a live `handsd` and a real `hands cancel`; the
  race is tested only for the driver role, not the architect; other callers
  of `transition` (release, deny, reconcile, `_finish`) are covered by the
  on-disk judgement but not each tested for a window of their own.
- The `-I` hook under a real Claude Code turn: that Claude Code runs hook
  commands through `/bin/sh` with the role directory and environment doctor's
  self-test assumes.
- A real phone has not sent anything since U3 (`answer`, `go`, `reply`
  through `go_builder` and the refusal of socket phone origins are tested
  with fakes only).
- `doctor --live` with a real `claude` turn; the argv judgement covers the
  three spellings above, not every way to write the arguments.
- U5: "absent from the committed tree" read as "the reload finds no file";
  a file deleted but not committed would get the same stop (untested); only
  the default path tested; not tested while paused.
- A reviewer following U4's revert step.
- Left over: docs/INTEGRATION.md still spells the guard hook as `python3
  <path>` in places outside U3's live paragraph (U2's file list did not
  include it). Mission 22 rewrites that document.

## Review items

| REVIEW-20 item | What | Closed by |
|---|---|---|
| Blocker 1 | a cancelled architect/driver job can run anyway (cancel during the clone advance) | U1 44f7494 |
| Should-fix 1 | the live hook is shadowable and doctor said fine | U2 97d1666 |
| Should-fix 2 | Write/Edit/MultiEdit through a hardlink under `kits/` | U2 97d1666 |
| Should-fix 3 | a socket client can make a job look like a phone `answer` | U3 056f044 |
| Should-fix 4 | `doctor --live` for the architect judges the wrong repo/kit | U3 056f044 |
| Should-fix 5 | `doctor --live` deletes an existing kit | U3 056f044 |
| Should-fix 6 | the protocol's revert step does not work as written | U4 3dc5a32 |
| Note on U5 | an apply that leaves no playbook | U5 37d2c51 |

## Findings filed for mission 22

- H-046 — `handswho` publishes every ~20 s and spends the public broker's
  daily cap.
- H-047 — a `handsd` restart kills the running builder job and nothing
  resumes it.
- H-048 — under `autonomous` a builder's `blocked` verdict stops for the
  human instead of consulting the architect.
