# ROADMAP

Standing reminder for the architect, at every milestone gate below: if
`docs/ARCHITECT-INSTRUCTION.md` changed since the last paste, hand the human
the complete new instruction text to paste into the claude.ai Project (the
human cannot see the installed copy; a stale one is invisible from inside a
chat). Missions 10 and 11 change it (kit check, the closed loop, the driver
role), and each Project onboarded in M5–M7 needs its own pasted copy, with
the Purpose block filled, pasted into the Project's instructions field and
verified by asking the new Project "What are your Parameters?" (discotrade
ran two days without one, noticed 2026-10-13). **INSTRUCTION PASTE after
the mission-26 release** — handed over at its install on 2026-10-18, and no
paste is due after mission 27, which does not change the instruction
(DESIGN §43) — (DESIGN §42: the new opening paragraph, rules 3, 9,
12 and 14 reworded, rule 15) for every Project, hands and discotrade; in
discotrade's it replaces the interim rule 15, and its interim operations
document is retired.

**Small missions (decided 2026-10-18 03:12).** One theme a mission, sized for
review: not split into micro-missions, but never large just because it can
be; a large theme is split into consecutive missions. Easier to review,
easier to address bugs.

**Reordered 2026-10-18 (01:33: project separation first, all planned work
that does not serve it waits; 03:08–03:12: the rest; 11:41: the
local-model harness numbered 28, M9 moved to 29; this numbering is
superseded at 18:52 by the next paragraph).** Mission 26 = the
project separation; mission 27 = M8b, the harness seam with Codex;
mission 28 = M8b's second mission, a harness for a local model (OpenCode
first; dsh when it is ready); mission 29 = M9; then M5b, a project
started from scratch (after
mission 26 is installed), and agile-skills as the migration of an
in-progress project (M7 redefined; after M9). Moved to the backlog: Claude
credential profiles (until a usage limit actually hits) and M6 spanweave.
The AppArmor host decision of 2026-10-17 21:21 is superseded: Codex runs
unconfined, as Claude Code does. This supersedes the order of 2026-10-17
20:27 (26 = the separation with credential profiles, 27 = the seam, 28 =
M9). Since 2026-10-18 01:45 discotrade has been operated from its own chat
by interim documents in its Project; the hands Project chat sees it only
as HF reports and when a release install restarts its daemon. The kit for
mission 26 issued 2026-10-17 23:25 (separation and credential profiles
together) was never sent; this kit replaces it.

**Renumbered 2026-10-18 18:52 (DESIGN §43; kept one mission at 19:22;
superseded on 2026-10-19 by the next paragraph).**
Mission 27 = the separation follow-up, operations and safety fixes (the
owner file named on every builder job, background tasks off where the
role's hook allows it, a playbook change kept for the owner, H-070,
H-071, the DESIGN wording of H-027, H-034 and H-039, review 25's
should-fix 1, review 26's should-fix 1 and 2), one mission of about
seven units; mission 28 = M8b, the harness seam with Codex (+ review
25's should-fix 3); mission 29 = M8b's second mission, a local-model
harness, OpenCode first; mission 30 = M9 (+ review 25's should-fix 2).
This supersedes the 11:41 numbering in the paragraph above (27 the seam,
28 the local harness, 29 M9); the order after M9 is unchanged.

**Renumbered 2026-10-19 01:42 and 19:3x (DESIGN §44; superseded on
2026-10-21 by the next paragraph).** At 01:42 the human
asked for GitHub to enforce a pull-request-only `main` with CI passing,
built into the next mission, then applied to the other project; at 19:3x
he split that mission, the pause first. Mission 28 = a pause that holds
the next step (H-078, from the other project's HF-017), review 27's three
should-fix items and the ruling on H-077; mission 29 = the pull-request
gate (CI, a per-project setting for how `main` moves, kit applies and the
review's commit through pull requests, docs/PR-CI-GATE.md, doctor); mission
30 = M8b, the harness seam with Codex (+ review 25's should-fix 3); mission
31 = M8b's second mission, a local-model harness, OpenCode first; mission
32 = M9 (+ review 25's should-fix 2). This supersedes the 18:52 numbering
above (28 the seam, 29 the local harness, 30 M9); the order after M9 is
unchanged.

**Renumbered 2026-10-21 (DESIGN §46).** Mission 29's review found that
switching this repository's `main` to pull requests would stop every kit
apply started on `main` (H-082), with two more gaps of the gate (H-081,
H-083); the human put a small follow-up first. Mission 30 = the gate's
follow-up (H-081, H-082, H-083 — the engine approves plan files only —
and review 29's should-fix 2–4); mission 31 = M8b, the harness seam with
Codex (+ review 25's should-fix 3), the first mission under the gate;
mission 32 = M8b's second mission, a local-model harness, OpenCode first;
mission 33 = M9 (+ review 25's should-fix 2). This supersedes the
2026-10-19 numbering above (30 the seam, 31 the local harness, 32 M9);
the order after M9 is unchanged.

Milestones are gated by a clean cold review of the mission that closes them,
then an install (`uv tool install --force`) and a driver-kit refresh.

- **M1 Core** — DONE 2026-09-11 (mission 1). Dispatch, gates, playbook,
  limits, monitor, inbox, ntfy, driver kit.
- **M2 Shakeout on hands itself** — DONE 2026-09-11 (mission 2). A run
  chained into a cold review with no human action between; ntfy proven.
- **M3 Hardening by review** — missions 3–7a, DONE 2026-09-12: the
  mission-7a build is installed; reviews now find claims, not code. Each review's
  blockers closed by the next mission; the Bash guard converges on a
  per-subcommand option allowlist; the driver's background wait retired;
  determinism as a property. Gate: a mission whose cold review has zero
  blockers, so a build can be installed and the driver kit refreshed.
- **M4 Detectors and the phone channel** — mission 8. Harness-killed
  background tasks detected from the stream; per-job systemd scope with
  orphan accounting; ntfy command channel with authenticated approvals
  (`decided_by: phone`); REVIEW-3's deferred items. Gate: clean review,
  install, and the doctor wake check redone over the phone channel.
- **M4b The closed loop** — mission 10 DONE 2026-09-13 (go, kit transport,
  kit check, handbook); mission 11 DONE (apply from kit, driver role, consult);
  mission 12 closes review 11 (the guard) before the driver role is enabled. Instruction re-pasted 2026-09-13 with rule 13.
  The closed loop — missions 10 and 11: `go` and kit transport from
  the phone; the driver as a headless role with bounded authority via
  `consult`. Gate: one mission of hands run end to end with no Code tab
  opened, and one builder question resolved by the driver role and graded
  by the cold review.
- **M4c The architect role** — missions 15 and 16 (decided 2026-09-15;
  renumbered twice: 13 closed review 12, 14 closes review 13 and ends the
  guard's parser).
  A fourth headless role, `architect`, consulted by the playbook on each
  review outcome: reads the branch, writes the next kit from this roadmap,
  files it with `hands kit file` (the local twin of the phone's `kit`), and
  replies `VERDICT: next kit <name>` | `VERDICT: series complete` |
  `VERDICT: escalate <reason>`. Its guard: read-only git, `hands kit
  check`, writes only under its own `kits/`, never a push, never a send.
  `[series] architect = "phone" | "role"` chosen per project at the switch
  point, which is the fully reviewed work plan: DESIGN, this roadmap with
  checkable gates, the first plan and the sequence of the rest, the
  playbook (consult on review outcomes, auto-approved kit applies, the
  escalation conditions), and the architect directory kit. Escalation is
  mechanical and approved with the plan: a roadmap gate failing twice, a
  review blocker the plan does not answer, a milestone the plan lacks, or
  the series' consult budget exhausted. Switching back to phone mode is
  "pause, continue from the branch"; one architect at a time.
  Mission 13 (closer): review 12, the sweep after the reap, the
  per-project spool and templated units so two projects can run on one
  laptop (M5 starts on that layout). Mission 14 (closer): the guard's
  one-line language, review 13 — DONE 2026-09-16; role mode held its
  review; the driver role is enabled. Mission 15: review 14, the role, its guard, `hands kit file`, the
  playbook mode and auto-approval, escalation conditions — DONE 2026-09-16,
  review 15 found the guard's `for`/`${…}` hole (role mode regressed).
  Mission 16 (closer): the guard's language finished, review 15, H-030..32
  — DONE 2026-09-16; review 16 found no guard hole; the driver role is
  enabled. Mission 17: review 16 (the autonomy path), `reply <secret> <text>` — DONE
  2026-09-17; review 17: one blocker (the start fold). Mission 18 (closer):
  review 17 — DONE 2026-09-17 (review 18: blockers=0, should-fix=4, carried
  to mission 20); the architect role enabled 2026-09-18. `reply <secret> <text>`
  on the command topic delivered as a `keep` to the architect's last
  session with its answer on the events topic, and self-hosted ntfy behind
  the Tailscale tunnel (free text about a project no longer crosses a
  public broker). Gate: one hands mission planned on the phone, handed to
  the role at the switch point, and run to a reviewed-clean stop with no
  human action; one escalation answered over `reply`.
  Requires: the driver role enabled (done 2026-09-17), the architect role
  enabled after review 17 finds the autonomy path closed (done 2026-09-18),
  and one real consultation graded by a review. GATE MET 2026-10-12: the
  discotrade series (M5) ran in role mode from its plan kit; the role's
  mission-2 kit was graded clean by discotrade review 2 (6e88bbb), and by
  the next morning the role had kitted missions 2–5 unattended. The first
  three consultations escalated on hands bugs (the role could not write,
  its clone never advanced, no `HANDS_PROJECT` in role jobs), worked
  around on the laptop and fixed in mission 20.
- **M4d The pull-request flow, then the shakedown's findings** — missions
  19 to 22 (decided 2026-10-12; split 2026-10-14; the closer added
  2026-10-15). Mission 19: DESIGN
  §35, the PR per mission with the hosted review (Qodo) read by the cold
  review as a second reviewer and the review merging on a clean verdict;
  templates, this repository's protocol and playbook, doctor's `gh` row,
  docs — DONE 2026-10-14 (review 19: blockers=0, should-fix=5; the probe
  PR #1 drew the hosted review in 29 seconds; installed 2026-10-14).
  Mission 20 (DESIGN §36, the first mission run through a pull request):
  hermetic tests (H-040); review 19's five should-fix items and the review
  protocol's tests-only and concurrency rules (HF-007, HF-008); the
  architect role's write permission (H-041); the runner advancing the
  roles' clones and setting `HANDS_PROJECT` (H-042, H-043); the engine's
  reload before an autonomous apply's kickoff (H-044, HF-001) and the hold
  decided before it is published (H-045); `answer <secret> <text>` with an
  attached file, not gated, with the builder's reply published and human
  decisions listed in the role's consult prompt; the job environment's
  timeouts (HF-006); `cp` from the clone into kits (HF-003); review 18's
  four should-fix items; project name in every notification title and in
  generated topic names; this repository's mission-less kickoff — built
  2026-10-14 on branch mission-20, PR #2; review 20 (2026-10-15, the first
  review through the flow): blockers=1, should-fix=6, nine hosted findings
  read, four confirmed; the PR stays open. Mission 21 (closer, DESIGN §37):
  review 20 — the cancel race during the clone advance, the `-I` hook and
  the module beside the guard, writes through a hardlink, the provenance
  of an `answer`, `doctor --live` for the architect, the protocol's revert
  step, the apply that leaves no playbook; files H-046..H-048. Gate:
  mission 21 merged by its own review through the flow (PR #2), with a
  `## Hosted review` section in REVIEW-21 — DONE 2026-10-15 (review 21:
  blockers=0, should-fix=3; the review merged PR #2 itself: 791f767;
  installed 2026-10-15). GATE MET. Mission 22 (DESIGN §38, the last of
  M4d): the buttons carrying the token (H-037, live since the move to the
  self-hosted server), the operational findings of 2026-10-14 (H-046 the
  who publish rate and doctor's warning on the public broker's cap; H-047
  the restart that kills the builder; H-048 the blocked verdict consulting
  the role; the self-hosted ntfy as the documented default with
  docs/INTEGRATION.md corrected; a phone `progress` command), review 21's
  three should-fix items (H-049 the revert step for added files, H-050 the
  reviewer's schedule), and the onboarding half — the role
  reads the handbook and templates from the installed hands (HF-002),
  `hands project add`, the Purpose block in both instruction templates, the
  owner-decisions file as a template with the review protocol's one-commit
  exception, the brief template's recovery rule for a `keep` answer, the
  handbook's onboarding shape, ruling round, separation rule and consultation
  re-firing, HF-004, HF-005 and the first plan kit's silent apply in the
  docs — DONE 2026-10-15 (review 22: blockers=0, should-fix=12; the review
  merged PR #3: f11cfb1; installed 2026-10-15 20:23; both Projects' instructions
  re-pasted). M4d CLOSED. Mission 23 (DESIGN §39): review 22's twelve
  should-fix items, H-051..H-054 ruled, a killed review resumed (H-057),
  phone refusals published and lenient job ids (H-058, H-059), the consult
  journal line on resume (H-060), `hands hosted-review <pr>` and the
  hosted review's findings fixed inside the pull request, the docs. Gate:
  mission 23 merged by its own review with a `## Hosted review` disposition
  table in FINAL-REPORT-23 and an archive under meta/reviews/hosted/ — DONE
  2026-10-16 (review 23: blockers=0, should-fix=9; PR #4 merged by the
  review: 2f81700; installed 2026-10-16 13:45, the restart proving H-047's
  resume on another project's builder). GATE MET.
- **M5 Pet projects from scratch (discotrade)** — decided 2026-09-17: before
  any integration, hands drives a new project from an empty repository in
  role mode, as the shakedown of the whole loop. discotrade
  (SigorMatt/discotrade): repo and SPEC.md 2026-10-11, laptop set up as a
  second project the same day, plan kit from its own Project chat applied
  2026-10-11 23:54, `go` 2026-10-12; the series runs autonomously; owner
  rulings as `meta/decisions/decisions-<date>-owner.md` (2026-10-13). Its
  hands findings (HF-001..006 in discotrade's FINDINGS) are mission 20's.
  Since 2026-10-14 both projects notify through the self-hosted ntfy of
  §33 behind Tailscale (the public broker's daily cap was hit that day).
  Gate: the series reaches its roadmap's last milestone or its consult
  budget, with every stop that needed a human answered from the phone.
  Status 2026-10-16: missions 13–15 finished and reviewed, mission 16
  running from the role's kit; 19 of 30 consultations used; three owner
  rulings (D-004; D-008/D-009; O-19..O-22 — a gate reshaped because no
  agent may author attack-shaped test content); four of its hands findings
  (HF-009..HF-012) carried into mission 24 as H-066..H-069.
- **M8 Other coding agents as backends** — MOVED AHEAD OF M6/M7 (decided
  2026-10-15, DESIGN §39): an integration should meet a backend shaken down
  on a series whose failures cost nothing, and a different model as the
  cold reviewer removes the shared-blind-spot problem. Mission 24 = M8a: a
  laptop probe as a gate (headless one-shot run, event stream, session
  resume, sandbox and approval behaviour, a transcript the monitor can read;
  Codex CLI first), then the design of the backend seam (`[roles.<role>]
  backend`, runner and monitor behind it, a guard story per backend — the
  driver and architect roles stay on Claude until a review finds no hole —
  doctor rows per backend, a per-role `model`, the optional polish round;
  ACP evaluated if the probe fails on resume or transcripts). Mission 24 (DESIGN v3.23 §40, kit issued
  2026-10-16): the probe on the three harnesses installed that day (Codex
  CLI 0.163.0, OpenCode 1.19.2, dsh 0.2.0-rc.2 under Node 22 by nvm),
  recorded in docs/HARNESS-PROBE.md; the seam as far as it is decided
  (harness-level, two candidate seams, ACP the prior); credential profiles
  designed (up to three Max subscriptions, workers B→C→A, the architect and
  driver pinned to A, a quota stop is a resume on the next profile; no
  metered usage); `hands go` and `hands kit apply`; `task_killed`
  de-duplicated (H-062); the transcript path under `CLAUDE_CONFIG_DIR`
  (H-063); review 23's should-fix; the kit-check warning for H-061; the
  templates' refusal path, worktree cleanup, skip list and gate rule
  (H-066..H-069); docs/OPERATIONS.md and docs/RELATED.md — BUILT 2026-10-17
  on branch mission-24, PR #5; review 24: blockers=1 (the capture script's
  false timeout line), should-fix=8; the probe found Codex's confining
  sandboxes do not start on this laptop (AppArmor's unprivileged-userns
  restriction blocks its bundled bubblewrap) and that its verdict line can
  be printed while the task failed — the host decision is the human's.
  Mission 25 (closer, DESIGN §41): review 24, the probe record corrected and
  its unavailable rows re-checked — DONE 2026-10-17 (review 25: blockers=0,
  should-fix=3, carried to missions 27 and 29 — since 2026-10-19 its
  should-fix 1 done in mission 27, 3 in mission 31, 2 in mission 33; the
  review merged PR #5:
  594b8ee; installed on both daemons 2026-10-17 20:40). M8a CLOSED.
  Renumbered 2026-10-18 (DESIGN §42): the separation is mission 26, M8b
  missions 27 (the seam with Codex) and 28 (a local-model harness), M9
  mission 29; and at 18:52 (DESIGN §43): the separation follow-up 27, the
  seam 28, the local-model harness 29, M9 30; and on 2026-10-19 (DESIGN
  §44): the pause 28, the pull-request gate 29, the seam 30, the
  local-model harness 31, M9 32; and on 2026-10-21 (DESIGN §46): the
  gate's follow-up 30, the seam 31, the local-model harness 32, M9 33.
- **The project separation** — mission 26 (designed 2026-10-17 18:45–20:27;
  made first and whole 2026-10-18 01:33, DESIGN §42). Each project's own
  Claude Project chat operates it from its pasted instruction (rule 15) and
  the installed handbook's operator table (§19), with phone commands; the
  laptop aux runs self-contained prompts for every project; the hands
  Project keeps hands' missions and machine-wide operations, takes each
  project's HF reports (`HF-<n>-report.md`, evidence only) into its kits,
  and checks every new playbook's hands-facing parts (a first plan kit and
  each series switch point, never a mission kit). `consult <secret>` (and
  `hands consult`), started by the engine, replaces the aux recital; a
  ruling travels as a decisions kit (`kit` + `go`, the brief's §R reading
  the newest owner file); `digest` (and `hands digest`) gives one line per
  project. The handbook gains the second onboarding shape (an existing,
  hand-relayed project reshaped into mission form). H-072 closed; H-070
  and H-071 decided for mission 27. Gate: `consult` used once from the
  phone on a role-mode project; both Projects' instructions re-pasted and
  discotrade's interim documents retired; one notification answered by a
  project's own chat from the operator table. DONE 2026-10-18 (review 26:
  blockers=0, should-fix=2, carried to mission 27; PR #6 merged by the
  review, f16d6d1; installed on both daemons 19:34, and the hand-over to
  each Project's chat given). The gate's three live
  parts are the human's, after the hand-over, and are declared met from
  the branch and the notifications, never from memory.
- **The separation follow-up** — mission 27 (split out 2026-10-18 18:52,
  kept one mission at 19:22; DESIGN §43). What the separation's first day
  showed a project's operation needs from hands: the owner file named
  before every builder job but an apply, so route 4 works whatever the
  brief (H-073); the role hook admitting an omitted sub-agent flag under
  `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS`, the wheel shipping the hook,
  doctor's warn on a copy that is not the installed hands' copy, the
  variable set by default only where the role's copy is that copy, and
  the wait rule (H-074, from another project's HF-015 and HF-016); a
  role-filed kit that carries the playbook held for the human (H-075);
  H-070 and H-071; the DESIGN wording of H-027, H-034 and H-039; review
  25's should-fix 1; review 26's should-fix 1 (H-076) and 2. Gate, after
  its install: a decisions kit applied and `go` on a project whose brief
  predates the mission-26 template, with the ruling carried out; a
  builder under the default starts a sub-agent through the hook, and a
  real command past its timeout ends with a timeout result, neither
  backgrounded nor waited on with a `sleep`; doctor reports the variable
  and why; a project with the old hook keeps working, with the warn and
  without the variable; a role-filed kit carrying the playbook held for
  the human. DONE 2026-10-19 (review 27: blockers=0, should-fix=3, carried
  to mission 28; PR #7 merged by the review, d587fa6; installed for hands
  on 2026-10-19 — the first install split per project — with the other
  project's part waiting for its own quiet moment). The gate's live parts
  are declared met from the branch and the notifications, never from
  memory.
- **A pause that holds the next step** — mission 28 (decided 2026-10-19
  02:2x, split out 19:3x; DESIGN §44). A human `pause` keeps the role's
  end that would start the next step instead of dropping it; everything
  else is as under any pause and notified; `resume` rules still continue
  the running step until a stop has been suppressed under the pause, so a
  restart under a human pause resumes the builder; only `resume` ends a
  human pause, and it replays
  what was kept; `hands: at rest` is published once nothing runs (H-078,
  from the other project's HF-017). Also review 27's three should-fix
  items and H-077 (a kit entry naming the playbook in another case, or the
  configured playbook path, held for the human). Gate, after its install:
  on the other project, `pause` while its builder runs, `at rest` naming
  the kept end, its three waiting owner commits made at rest, `resume`,
  the kept end's step starting — read back from its branch; a restart
  under a human pause resuming the builder. DONE 2026-10-20 (review 28:
  blockers=0, should-fix=2, carried to mission 29; PR #8 merged by the
  review, 1acc9e0; installed on both daemons 2026-10-20, both projects
  stopped with no job running). The gate's live part on the other project
  waits for its builder to run again, and is declared met from its branch
  and the notifications, never from memory.
- **Pull requests only, CI required** — mission 29 (decided 2026-10-19
  01:42; DESIGN §45, written 2026-10-20). A CI workflow running
  `./scripts/check` on pull requests and on pushes to `main`; a
  per-project setting, `[repository] main` (`direct`, the default, or
  `pull-request`), under which a kit's apply goes through a pull request
  of its own merged once its checks pass, a resumed apply finding it
  again; `hands ci-wait <pr>`, the checks read mechanically; the engine's
  stop for an apply that did not land, never kept under a human pause
  (H-080); a role-filed kit that carries `.github/` held for the human;
  no test sending a request off the machine; the review protocol
  committing its file to the mission's branch and merging on green checks
  wherever `main`'s rules take pull requests only; docs/PR-CI-GATE.md (a
  ruleset template proven on another repository, with the order a project
  switches in); doctor's `main` row, the setting against the branch's
  rules; review 28's should-fix 1 (H-079). DONE 2026-10-21 (review 29:
  blockers=0, should-fix=4, carried to mission 30; PR #9 merged by the
  review, 4d32d35; its `check` check green on GitHub's runner, the first
  CI run of this repository). Its gate moved to mission 30: the review
  found that the switch would stop every apply started on `main`
  (H-082), so the switch waits for mission 30's install. The other project
  switches at a later quiet moment of its own, after mission 28's pause
  has been tested there.
- **The gate's follow-up** — mission 30 (decided 2026-10-21; DESIGN
  §46). The `pull-request` apply prompt's case (b) excludes `main`
  (H-082); the engine approves a role-filed kit on its own only when it
  carries plan files alone (`KIT.md`, `DESIGN.md`, `WORKPLAN.md`, root
  decisions files, Markdown under `meta/` that no playbook rule names),
  anything else waiting for the human, which replaces §45's CI hold
  (H-083, decided by the human); the review blocks on a branch that
  moved during it and
  merges with `--match-head-commit` (H-081), commits its failure-path
  reviews to the mission's branch when it exists (H-084) and ends on
  `main` (H-085); the setting's refusal names its two values; and a
  confirmed bug in a pull request's own code blocks its merge (decided by
  the human on 2026-10-21; in force from mission 31's review). Gate: after
  its install the human sets this repository's `main` to `pull-request`
  and the aux creates the ruleset by docs/PR-CI-GATE.md
  (`current_user_can_bypass: never`); kit 31's apply merges through a
  pull request on green checks, and mission 31's review commits to its
  branch and merges on green checks with `--match-head-commit`.
- **M8b The harness seam** — mission 31 with Codex (DESIGN §47, written
  from docs/HARNESS-PROBE.md), the first mission under the pull-request
  gate; a harness for a local model (OpenCode or dsh,
  or both) is mission 32, M8b's second, kept separate under the
  small-missions rule, OpenCode first; its gate is written by its kit. Re-checked by the aux 2026-10-18
  03:28, correcting the probe's `unavailable` rows of 2026-10-17: OpenCode
  1.19.2 is signed in (Nebius Token Factory; its credential is a file
  under `$HOME`, so a job `handsd` starts sees it; a default model is set;
  `opencode run --format json` answered a one-shot with exit 0); dsh
  0.2.0-rc.2 has no key any hands job can reach — `DEEPSEEK_API_KEY` is
  exported only for interactive shells and dsh has no credentials file
  (`~/.dsh` absent) — so a credentials file under dsh's home is the
  human's step before dsh runs a role, its session-log extension and
  telemetry disabled first (DESIGN §40). A per-harness headless runner, or hands as an ACP client receiving
  the permission requests; `[roles.<role>] harness`; an opaque per-role
  harness profile (a directory, a PATH prefix, environment); the four
  requirements per harness; roles move reviewer → builder first, the
  guarded roles (driver, architect) stay on Claude Code until a harness
  guard has been reviewed; the harness-neutral guard and transcript
  reader; the templates' Task-tool and worktree wording made neutral;
  doctor rows per harness; a privacy note. Mission 31 also carries review
  25's should-fix 3 (since 2026-10-18 18:52; should-fix 1, H-070, H-071
  and the DESIGN wording of H-027, H-034 and H-039 went to mission 27,
  DESIGN §43). The optional polish round (on `aux.done` with
  `blockers=0 should-fix>0`, one bounded builder job on the same branch,
  a re-review of the delta, then the merge; off by default) is its own
  small mission when wanted. Gate: one hands mission built by a builder on
  Codex and reviewed clean.
  - **Codex runs unconfined (decided 2026-10-18 03:08, superseding the
    host decision of 2026-10-17 21:21).** Codex runs on this machine as
    Claude Code does — its `danger-full-access` mode, as Claude Code runs
    the unguarded roles with its permission bypass; the machine is the
    sandbox and git is the record. No AppArmor profile for its bundled
    bubblewrap is made (the narrow profile chosen 2026-10-17 21:21 is
    dropped), and no doctor row checks one. A role on Codex is graded by
    the review and the pull-request checks, not by its verdict line
    (DESIGN §41).
- **M9 A machine is replaceable** — decided 2026-10-16 (DESIGN §40), mission
  33 (renumbered 2026-10-18 by DESIGN §42, to 30 at 18:52 by §43, to 32
  on 2026-10-19 by §44, and to 33 on 2026-10-21 by §46; it
  also carries review 25's
  should-fix 2, and splits into two missions if it grows past one review's
  size), before M5b: `hands export` (everything but secrets, env tables
  redacted by name, a printed secrets checklist) and `hands import` (through
  the `project add` path, Purpose and Parameters intact, no daemon until
  `hands doctor` is green); `hands upgrade [--accept-builder]` (the release
  install routine as a command) and `hands project refresh <project>` (the
  role-kit refresh keeping Purpose and Parameters); the spool inventory
  settled in docs/OPERATIONS.md; the notification server addressed by its
  MagicDNS name. Gate: a rehearsal on a purpose-built Ubuntu VM — both
  projects from an export plus the secrets checklist, proven by one kickoff
  and one phone approve.
- **More projects on this machine** (decided 2026-10-16; changed
  2026-10-18 03:08): a project started from scratch may be onboarded once
  the separation (mission 26) is installed — its own chat operates it from
  day one under the new instruction, and the hands Project checks its first
  playbook; no gate on credential profiles (a usage limit is met when it
  hits). The migrated, in-progress project is agile-skills (M7, below),
  after M9 is installed and its VM rehearsal has passed. Each gate is
  declared met from the branch, never from memory.
- **M5b discotrade's second series on the Codex backend** — decided
  2026-10-15: no new pet project; discotrade-v2 starts at a series switch
  point (a new playbook with `[roles.<role>] harness` per role, approved by
  the human),
  builder on Codex and reviewer on Claude first, the architect role on
  Claude; after M9 (decided 2026-10-16); if v1 ends before then, the
  project waits. Its new playbook gains `aux.orphaned → resume` and the
  blocked→consult rule, and the hands Project checks its hands-facing
  parts. Gate: as M5, on the second backend.
- **M6 spanweave integration** — MOVED TO THE BACKLOG 2026-10-18: the human
  develops spanweave without hands for now; it may come later. The plan of
  2026-09-12, kept as history: INSTRUCTION PASTE DUE: the spanweave
  Project gets its own copy, parameters filled in.
  spanweave integration — hands drives spanweave's *development*
  (its builders and reviewers run as hands jobs); nothing of hands enters
  what spanweave ships. First external project, run as a shakeout.
  Shape agreed 2026-09-12: **PR per run, auto-merge on a clean review.**
  1. Laptop: `~/.hands/spanweave.toml` (builder/aux cwd, `resume_line =
     "Resume WORKPLAN.md"`, ops repo, allowed roots), a second `handsd`
     instance (templated user unit `handsd@<project>.service`), a driver
     directory `~/hands-driver/spanweave/` with a fetch-only clone.
  2. Ops repo: `watch_monitor.sh` accepts `--pids --transcript --base`;
     until then the built-in stall detector runs and tripwires are off.
  3. Series kit from the architect: `PLAYBOOK.toml` in the spanweave
     vocabulary (`VERDICT: run N finished`, `VERDICT: review run N
     blockers=k should-fix=m`), `auto_runs` for the runs already grouped in
     §2, and the merge rule; run and review prompts gain the `VERDICT:`
     first line; the architect instruction installed in the spanweave
     Project.
  4. Branching: each run starts a branch from `main`, opens a PR at run end
     (builder, `gh pr create`), the cold review runs on the branch, and on
     `blockers=0` with green checks the playbook has the builder merge
     (`gh pr merge --squash`) and start run N+1 if listed. Blockers, red
     checks, or an unrecognised verdict stop and notify. `WORKPLAN.md` lives
     on the branch of the run in flight and is folded into `TASKS.md` at
     series close. Branch protection on `main` requires the checks. The
     presence of the merge rule in an approved playbook is the human's
     standing approval of every merge it makes.
  5. First series is a shakeout in phone mode: expect doc-versus-reality
     findings, keep it short, and treat the first auto-merge as the
     milestone. The second series runs in role mode (M4c). The PR shape
     is mission 19's (DESIGN §35): the review merges, merge commits.
  Gate: one series of at least two runs merged with no human action
  between kickoff and the series-close stop.
- **M7 agile-skills: the migration of an in-progress project** — REDEFINED
  2026-10-18 03:08: agile-skills, stopped mid-work and relayed by hand
  today, is migrated to hands in the second onboarding shape (DESIGN §42)
  as the shakedown of migrating an in-progress project, after M9 and when
  the human says it is ready; its own chat operates it from the start. Its
  original integration line, kept as history: INSTRUCTION PASTE DUE: the
  agile-skills Project gets its own copy.
  agile-skills integration — hands drives agile-skills' development;
  agile-skills stays machinery-agnostic and owns the mission-form contract
  (kickoff line, checkpoint resume, `VERDICT:` first line) as its own spec,
  of which hands is one consumer and never a dependency. Same steps with
  `meta/` paths and the mission form (`meta/BUILDER-N-PROMPT.md`, checkpoint-driven kickoff, no
  `resume_line`), which is the form hands has been exercised on. PR per
  mission, auto-merge on a clean review.
- **(M8 moved above M6 on 2026-10-15; its original line, decided
  2026-09-17:** a role may run on a different agent CLI; Codex CLI first;
  evaluate ACP as the common protocol. Requirements: headless one-shot
  invocation with a resumable session, a transcript hands can read, a
  permission mode the guard can enforce, and the VERDICT contract
  unchanged.)
- **(removed 2026-09-15):** the optional remote MCP face (DESIGN §9) is
  dropped from the roadmap; the phone loop and the architect role cover
  what it was for. DESIGN §9 stays as history.