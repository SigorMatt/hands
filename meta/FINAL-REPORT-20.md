# FINAL-REPORT-20 — the first role-mode series' findings

VERDICT: mission 20 finished

Brief: meta/BUILDER-20-PROMPT.md. Design: DESIGN v3.19 §36 (with §31, §33,
§34, §35). Reviews read: meta/reviews/REVIEW-19.md (should-fix 5) and
meta/reviews/REVIEW-18.md (should-fix 4); all nine are closed by this mission
(see "Review items"). Shape: pull request. Every unit was committed and pushed
to `mission-20`. The last unit opens the PR from `mission-20` to `main`, as
the brief's Branch section and §35 say. Base 238a57b (`plan: mission 20 kit
(DESIGN v3.19)`). Findings: U0 filed H-041..H-045. U3 resolved H-041, U4
resolved H-042 and H-043, and U5 resolved H-044 and H-045. U1 resolved H-040.
H-039, H-037, H-034, H-027, H-001 and H-009 stay open.

The gate environment (H-040). This mission ran as a hands builder job, so it
inherited `HANDS_PROJECT` and `HANDS_JOB`. U0's gate ran as `env -u
HANDS_PROJECT -u HANDS_JOB ./scripts/check`, and its commit body says so. U1
adds an autouse fixture that removes every `HANDS_*` variable from every
test's environment. U1 itself was proven with `HANDS_PROJECT=x HANDS_JOB=y
./scripts/check` (green 3/3, 4059 passed). From U1 on, every gate was plain
`./scripts/check`.

## 1. What changed (sha per unit)

- U0 1977864 (`plan:`): meta/plan.md, meta/CHECKPOINT.md, meta/journal.md,
  and H-041..H-045 in meta/findings/FINDINGS.md:
  - H-041: the architect role cannot write.
  - H-042: the role's clone never advances.
  - H-043: no role job carries `HANDS_PROJECT`.
  - H-044: the kickoff after an autonomous apply comes from the pre-apply
    playbook (discotrade HF-001).
  - H-045: a hold for a kit the role filed is published with buttons before
    the engine approves it.

  It also created the branch `mission-20` from 238a57b and pushed it. Green
  3/3, 4052 passed (HANDS_* unset).
- U1 4752ace (`tests:`):
  - tests/conftest.py: an autouse fixture, `_no_hands_environment`, deletes
    every `HANDS_*` variable. tests/test_hermetic.py checks that none is in a
    test's environment or in a child process's.
  - Doctor's `gh` row runs `gh auth status --active --hostname github.com`.
    The "`--version` did not answer" and "`gh auth status` did not run" warns
    now carry the remedy.
  - tests/fake_gh.py gains the `multihost`, `noversion` and `hang` modes.
  - docs/INTEGRATION.md and docs/PLAYBOOK.md are corrected.
  - H-040 is marked resolved.
  - Green 3/3, 4059 passed, with `HANDS_PROJECT=x HANDS_JOB=y` set.
- U2 7326386 (`protocol:`): templates/REVIEW-PROTOCOL.md and
  meta/REVIEW-PROTOCOL.md change together.
  - The direct shape applies only when the brief's Branch section says
    "Direct".
  - A brief that names a branch with no open PR gets the blocker "no pull
    request for <branch>". The review file then records `reviewed: none` and
    `blockers=1`, and the review stops there.
  - The branch is named once as `<branch>`.
  - The commits under review are `git log <base>..origin/<branch>
    ^origin/main`. Merge commits and `meta:` commits are skipped.
  - A tests-only commit is reviewed by making each wrong change its body
    names. A tests-only commit that names none is a blocker.
  - Sub-agents run one at a time with one check each. The reviewer runs the
    check once, at the tip.
  - The tree is put on `main` before the review file is committed.
  - Green 3/3, 4076 passed.
- U3 0eb37bc (`architect:`):
  - architect/settings.json allows exactly `Edit(kits/**)`,
    `Write(kits/**)` and `MultiEdit(kits/**)`.
  - Doctor's architect row fails if any of the three is missing, or if any
    Edit/Write/MultiEdit allow in any settings layer it reads names anything
    else.
  - `doctor --live` for the architect judges the turn by what it did:
    - a file written under `kits/`;
    - `hands kit check` and `hands show` in the turn's stream.
    Doctor removes the file afterwards, because the role's settings deny
    `rm`.
  - tests/fake_claude.py can script tool calls, and denied ones.
  - H-041 is marked resolved.
  - Green 3/3. The journal does not record the test count.
- U4 de2e34c (`runner:`):
  - Before every architect and driver job, the runner runs `git -C <clone>
    fetch -q origin` and then `checkout -q --detach origin/<branch>`. The
    branch comes from the new `[roles.<role>] branch` key (default `main`).
    Each command has a 300 s bound and no prompts.
  - If either command fails, the job fails before `claude` starts: state
    `failed`, reason `spawn_error`, with the git command and git's output in
    `stderr_tail`.
  - Every job's `HANDS_PROJECT` comes from the config's project name. It
    overrides handsd's environment and the role's env table.
  - Doctor's role rows print the clone's HEAD against `origin/<branch>`, and
    the project the job will see.
  - H-042 and H-043 are marked resolved.
  - Green 3/3, 4105 passed.
- U5 337db9a (`engine:`):
  - Before it decides the `builder.done` of an apply it approved itself, the
    engine reloads the playbook from the committed file.
  - If that playbook no longer loads, the pipeline stops with the loader's
    reason.
  - Under `autonomous`, the hold of a kit the role filed is decided before
    anything is published:
    - approved: one buttonless "kit <name> filed by the architect; apply
      approved by the playbook";
    - not approved: the §34 held notification with Approve/Deny.
  - The deferral is kept in memory only. A restart republishes held jobs with
    buttons, as §34 says.
  - H-044 and H-045 are marked resolved.
  - Green 3/3, 4110 passed.
- U6 187e38e (`phone:`): `answer <secret> <text>`, the ninth cmd_topic
  command.
  - It files a builder `keep` send of origin `phone` on the builder's last
    session. The job un-pauses the pipeline when it starts, and the §8 gate
    never holds it.
  - Refusals are published under `hands: answer`.
  - An attachment must be a `.zip`, and goes into `kit_dir` by the kit
    transport's rules. The delivered text ends with a sentence naming the
    file's path, and `files_written` keeps its sha256.
  - Each answer adds an `answer.sent` inbox event.
  - The builder's final reply is published titled `builder`.
  - The driver-escalation stop keeps the builder's question verbatim.
  - The architect's consult prompt gains "Decided by the human since your
    last consultation".
  - Green 3/3, 4131 passed.
- U7 61a2417 (`guard:`):
  - Builder and aux jobs carry `BASH_DEFAULT_TIMEOUT_MS` and
    `BASH_MAX_TIMEOUT_MS` = 900000 unless the role's env table sets them. The
    default lives in `RoleConfig.spawn_env`, so runner.py is unchanged.
    Doctor prints the effective values.
  - Architect mode allows `cp` and `cp -r` when every source is under
    `HANDS_CLONE` and the target is under `HANDS_KITS`, by realpath.
  - The copy is refused for:
    - a symlink source, or a symlink inside a `-r` source;
    - a symlink under the kits;
    - sources that mix the clone and the kits;
    - an unset `HANDS_CLONE`.
  - The guard's self-test passes 405/405.
  - Green 3/3, 4180 passed.
- U8 6a3f2f2 (`review-18:`): REVIEW-18's four should-fix items.
  - Any non-ASCII character in `ntfy_url` is refused at load. The
    public-broker check compares the host after NFKC and after folding U+3002
    to ".".
  - Doctor runs the guard's self-test as `python3 -I` with
    `PYTHONPATH=""`.
  - `_open_zip` reads the zip once, and the kit record stores the sha256 of
    the bytes `check_kit` read. If the client's hash differs, the filing is
    refused.
  - A hardlinked regular file under `kits/` refuses `cp` and `mv`, and
    doctor reports it. The self-test passes 409/409.
  - Green 3/3, 4212 passed.
- U9 2e9a6ca (`notify:`):
  - Every title the Notifier publishes, and `notify --test`, begins with
    `<project>: `.
  - Doctor has a `topics` row. It WARNs naming each configured topic whose
    value does not contain the project, and never prints a topic.
  - The topic lines in docs/INTEGRATION.md carry the project.
  - PLAYBOOK.toml's kickoff is the mission-less line, and nothing else in the
    file changes.
  - docs/PLAYBOOK.md's review range now reads as the protocol does.
  - Green 3/3, 4225 passed.

  Two departures, recorded as they happened:
  - **Commit order.** The sub-agent committed *before* its three green runs,
    because tests compare PLAYBOOK.toml to HEAD and refuse a working-tree
    copy that differs. It pushed only after 3/3.
  - **README.md.** It also touched README.md, which is not on the unit's file
    list: one `ntfy_topic` line, which the commit body names.
- U10 (this commit): this report and the mission's meta bookkeeping (plan,
  checkpoint, journal). After the commit, U10 opens the pull request and
  returns the tree to `main`.

## 2. What the tests prove

- **Hermetic tests.** tests/test_hermetic.py was red with
  `HANDS_PROJECT=x HANDS_JOB=y` before the fixture. With the fixture, neither
  a test's environment nor a child process's carries any `HANDS_*` variable.
- **Doctor's `gh` row**, against tests/fake_gh.py:
  - The fake can list a GHE host first, with another login and no `repo`
    scope, and make plain `auth status` exit 1. The row is still ok, and
    names github.com's login.
  - A `--version` that exits 1 warns naming `gh auth login`.
  - An `auth status` that times out (PROBE_S patched to 1 s) warns with the
    remedy.
  - All three tests were red before the change.
- **The review protocol.** 17 tests in tests/test_kit.py pin each new
  sentence of the template, and check that `mission-N` appears once and that
  no command says `origin/mission-N`. All 17 were red before the text change.
  The protocol still equals the template with `<owner>/<repo>` →
  `SigorMatt/hands`. The filled templates still pass `hands kit check` 6 of 6
  against a clone.
- **The architect's write permission.**
  - The shipped architect/settings.json carries exactly the three allows and
    passes the row.
  - Missing any one of the three fails the row (3 cases). So do
    `Write(repo/**)`, `Edit(.claude/**)`, `MultiEdit(./kits/**)`,
    `write(kits/**/../..)` and `Edit(~/**)` in settings.local.json.
  - Against a real daemon socket, a scripted live turn that writes, checks
    and shows passes and leaves no kit behind.
  - A turn whose write, kit check or show is denied, or whose show is not
    run, fails naming that step. So does one whose kit doctor cannot remove,
    and an empty spool fails the row too.
- **The runner.** These tests use a local bare repository as origin, with no
  network.
  - A driver clone and an architect clone one commit behind are advanced
    before `claude` runs, and left detached at the tip.
  - With `branch = "trunk"`, the runner checks out `origin/trunk`.
  - With the origin removed, the job fails with `spawn_error`, no pid and
    HEAD unchanged.
  - A builder job does not move a clone.
  - `HANDS_PROJECT` is the config's project for builder, driver and
    architect jobs, even when handsd's environment and the env table say
    otherwise.
- **The engine.**
  - A scripted apply rewrites and commits `[series] kickoff`, then replies
    `VERDICT: kit applied`. The kickoff job's prompt is then the committed
    line.
  - A playbook that no longer loads after the apply stops the pipeline with
    the loader's reason, and no kickoff is sent.
  - An approved role-filed kit gives one buttonless approval line, with no
    held note and no buttons.
  - These three fail at 238a57b and at de2e34c, and pass after U5. The two
    not-approved cases (a kit of another name, and a hash mismatch, each held
    with Approve/Deny) pass before and after; they pin "as before".
- **`answer`** (20 tests, red first):
  - Each sentence of §36's command has its own test. The command files one
    builder `keep` job of origin `phone` on the last session, and the job's
    start un-pauses the pipeline.
  - Its `VERDICT:` fires `builder.done`, and its reply is published titled
    `builder`.
  - Each refusal has its own test: no session; a builder job running,
    queued or held; empty or whitespace-only text.
  - An attachment with a non-.zip name, or over the size cap, is refused
    before any fetch.
  - The acceptance test: an `answer` whose text names a decisions file runs
    ungated. The same text sent by `hands send --context keep` is held (the
    control).
- **The job environment and the guard.**
  - Builder and aux jobs see 900000 for both names over handsd's value, and
    the role's env table overrides each.
  - Driver and architect jobs see handsd's value, or none.
  - Under real bash, a clone file and a clone directory are copied into the
    kits.
  - A symlink source, a symlink inside a `cp -r` source, and a symlink under
    the kits are refused, with the guard file unchanged.
- **REVIEW-18's four probes**, as tests (each red before the code):
  - `ntfy。sh`, `NTFY．SH` and `ntfy｡sh` are refused at load, with a token
    and without one.
  - A planted `shlex.py` beside the guard, or on PYTHONPATH, leaves no marker
    from doctor's self-test.
  - A passing zip swapped into the stored path for `check_kit` only is
    refused naming both hashes, end to end.
  - A hardlink `kits/h` to the guard: `cp`, `mv` and `cp -r` are refused
    under real bash with the guard unchanged, and the architect row fails
    naming it.
  - A shared-case test runs the guard's `kits_symlink` and doctor's
    `_kits_walk` over 10 trees, and requires the same answer from both.
- **Notifications and the kickoff.**
  - Every title in the test's TITLES list, driven through notify, answer and
    deliver, is published as `demo: <title>`. So are the start, the crash and
    `notify --test`. A held note keeps the raw title.
  - The `topics` row WARNs naming only `cmd_topic` and `who_cmd_topic` in
    its fixture. It is ok when every topic carries the project or none is
    set, and it never prints a topic.
  - The repository's playbook parses with 20 rules and the new kickoff.
  - A kit of that playbook with BUILDER-20's brief, carrying the new kickoff
    line, passes `hands kit check --repo <this repo>` (exit 0).

## 3. NOT PROVEN

1. **No `answer` has been sent from a real phone.** U6 is tested over the
   fake channel only. Not covered: a real ntfy round trip, a real phone's
   attachment, and a reply from a limit-resumed answer job.
2. **No real role job has had its clone advanced by the runner.** U4 used a
   local bare origin. Not tested:
   - a remote over a network transport;
   - the 300 s timeout firing;
   - a checkout refused by local changes in the clone.
3. **No real `claude` turn has run under the architect settings** (U3). The
   fake performs tool calls without Claude Code's permission layer or the
   guard. Not proven: that Claude Code resolves `kits/**` against the role's
   cwd.
4. **Real `gh` output for `--active --hostname github.com`** (U1) is not
   exercised by any test; only the fake answers it.
5. **No reviewer has followed the new protocol** (U2). The tests prove only
   that the texts say it.
6. **The deferred hold** (U5): no test of its own covers a paused pipeline at
   the decision, an approve call that fails, autonomy turned off before the
   consultation ends, or a kit filed during the wait. The deferral is in
   memory only.
7. **The job environment** (U7): the real harness honouring
   `BASH_DEFAULT_TIMEOUT_MS` and `BASH_MAX_TIMEOUT_MS` is not observed.
8. **The live hook runs the guard without `-I`** (U8). Only doctor's
   self-test runs isolated. When Claude Code runs the hook, a module planted
   beside the guard is still imported. §36 names doctor's self-test only.
9. **`apply_from_zip` re-reads the stored path after the check** (U8). A swap
   there is caught by the engine's re-hash at approval, not by the check.
10. **The `topics` row reads "lacks the project" as "the value does not
    contain the name as a substring"** (U9). That reading is the simplest,
    not the design's stated one.
11. **No test enumerates every title handsd can raise** (U9). TITLES lists
    the constants and literals that were found. A real ntfy/phone rendering
    of the prefixed titles is not observed.
12. **"3/3"** is each sub-agent's own report (and the orchestrator's for
    U0). No reviewer has reproduced it.
13. **The PR's hosted review and the merge** belong to the review, not to
    this mission. No hosted review has been read for this PR, and no merge
    has run.

## Review items

| Item | Unit | Commit | How closed |
|---|---|---|---|
| REVIEW-19 should-fix 1 — the protocol's "no PR" branch takes the direct shape for a PR mission whose PR was never opened | U2 | 7326386 | The direct shape only on a brief whose Branch section says "Direct"; a named branch with no open PR is blocker "no pull request for <branch>" and the review stops; pinned by text tests |
| REVIEW-19 should-fix 2 — a closer's base pulls in `main`'s commits; commands hard-code `mission-N` | U2 | 7326386 | The branch is named once as `<branch>`; commits are `git log <base>..origin/<branch> ^origin/main`; merge commits are skipped; a test checks `mission-N` appears once |
| REVIEW-19 should-fix 3 — doctor's `gh` row reads the first host's login/scopes and fails on any bad account | U1 | 4752ace | `gh auth status --active --hostname github.com`; a fake with a GHE host first and exit 1 for another host gives ok with github.com's login |
| REVIEW-19 should-fix 4 — INTEGRATION says every warn names `gh auth login`; two did not | U1 | 4752ace | Both warns carry `GH_REMEDY`; tests for `--version` failing and `auth status` timing out; doc test pins the wording |
| REVIEW-19 should-fix 5 — a garbled sentence in docs/PLAYBOOK.md about the review prompt | U1 | 4752ace | Reworded ("the review prompt that … ship says"); doc test red first |
| REVIEW-18 should-fix 1 — a Unicode full stop in `ntfy_url` gets the token past the public-broker check | U8 | 6a3f2f2 | Non-ASCII in `ntfy_url` refused at load; the broker check compares the NFKC/U+3002-folded host; the reviewer's three urls as tests |
| REVIEW-18 should-fix 2 — a module planted beside the guard shadows one it imports; doctor passes | U8 | 6a3f2f2 | Doctor's self-test runs `python3 -I` with `PYTHONPATH=""`; a planted `shlex.py` leaves no marker. The live hook is not changed (§3.8) |
| REVIEW-18 should-fix 3 — the kit record hashes the bytes the client sent, not the bytes checked | U8 | 6a3f2f2 | The zip is read once; the record stores the sha256 of the bytes `check_kit` read; a mismatch with the client's refuses the filing; the reviewer's swap probe as an end-to-end test |
| REVIEW-18 should-fix 4 — a hardlink under `kits/` lets `cp` overwrite the guard; doctor says ok | U8 | 6a3f2f2 | A regular file with `st_nlink > 1` under kits refuses `cp`/`mv` and fails the architect row; the guard's and doctor's walks are pinned by a shared-case test |

## 4. Acceptance

- The gate: U1 was proven with `HANDS_PROJECT=x HANDS_JOB=y` set, and every
  unit from U1 to U9 recorded green 3/3 with plain `./scripts/check` (4225
  passed at 2e9a6ca). The three runs on the pushed tip, with `HANDS_PROJECT`
  set, are recorded in this commit's body.
- Every unit commit's body lists every file it touches. Each file from `git
  show --name-only` for 1977864, 4752ace, 7326386, 0eb37bc, de2e34c, 337db9a,
  187e38e, 61a2417, 6a3f2f2 and 2e9a6ca was looked up in that commit's body,
  and none was missing. U0 is `plan:`.
- H-041..H-045 are filed (U0), and H-040 is resolved (U1).
- `architect/settings.json` carries the three allows, and doctor's architect
  row checks them (U3, §2).
- A test shows that the kickoff after an autonomous apply is the committed
  playbook's line (U5, §2).
- A test shows that an `answer` naming a decisions file is not held (U6, §2).
- `PLAYBOOK.toml`'s kickoff is the mission-less line, and the playbook loads
  with 20 rules (U9).
- This file exists with NOT PROVEN and the review-items table. The PR from
  `mission-20` to `main`, and the tree on `main`, are U10's steps after this
  commit.

## 5. For the architect

- Mission 20 is the first mission run through a pull request. Its review is
  the first to read a hosted review on a mission-sized PR and to run `gh pr
  merge --merge`.
- Residuals worth a finding later:
  - The live hook runs the guard as `python3 <guard>` without `-I`, so
    REVIEW-18 should-fix 2's premise still holds for the hook Claude Code
    runs (§3.8).
  - `apply_from_zip` re-reads the stored path after the check (§3.9).
  - docs/ARCHITECT-HANDBOOK.md's review wording still says `mission-N` and
    lacks `^origin/main`. U2 left it, because the handbook is mission 21's.
    docs/PLAYBOOK.md was brought into line by U9.
  - U5's deferral of a role kit's hold lives in memory only.
  - The `topics` row's substring reading of "lacks" (§3.10).
- Open findings that this mission did not touch: H-039, H-037, H-034,
  H-027, H-001, H-009.
- Mission 21 (onboarding, `hands project add`, the instruction templates, the
  handbook's new sections) is outside this mission, as the brief says.
