# ROADMAP

Standing reminder for the architect, at every milestone gate below: if
`docs/ARCHITECT-INSTRUCTION.md` changed since the last paste, hand the human
the complete new instruction text to paste into the claude.ai Project (the
human cannot see the installed copy; a stale one is invisible from inside a
chat). Missions 10 and 11 change it (kit check, the closed loop, the driver
role), and each Project onboarded in M5–M7 needs its own pasted copy, with
the Purpose block filled, pasted into the Project's instructions field and
verified by asking the new Project "What are your Parameters?" (discotrade
ran two days without one, noticed 2026-10-13).

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
  (H-066..H-069); docs/OPERATIONS.md and docs/RELATED.md. Mission 25
  (+ closer) = M8b (DESIGN §41, written from the probe record): the seam,
  the implementations the probe approved, the credential profiles with the
  `quota` classification and resume on the next profile, doctor rows per
  harness and per profile, the polish round. Gate: one hands mission built
  by a builder on the second backend and reviewed clean, and one quota
  stop resumed on the next profile.
- **M9 A machine is replaceable** — decided 2026-10-16 (DESIGN §40), mission
  26, before M5b: `hands export` (everything but secrets, env tables
  redacted by name, a printed secrets checklist) and `hands import` (through
  the `project add` path, Purpose and Parameters intact, no daemon until
  `hands doctor` is green); `hands upgrade [--accept-builder]` (the release
  install routine as a command) and `hands project refresh <project>` (the
  role-kit refresh keeping Purpose and Parameters); the spool inventory
  settled in docs/OPERATIONS.md; the notification server addressed by its
  MagicDNS name. Gate: a rehearsal on a purpose-built Ubuntu VM — both
  projects from an export plus the secrets checklist, proven by one kickoff
  and one phone approve.
- **M5b discotrade's second series on the Codex backend** — decided
  2026-10-15: no new pet project; discotrade-v2 starts at a series switch
  point (a new playbook with `backend` per role, approved by the human),
  builder on Codex and reviewer on Claude first, the architect role on
  Claude; after M9 (decided 2026-10-16); if v1 ends before then, the
  project waits. Its new playbook gains `aux.orphaned → resume` and the
  blocked→consult rule. Gate: as M5, on the second backend.
- **M6 spanweave integration** — INSTRUCTION PASTE DUE: the spanweave
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
- **M7 agile-skills integration** — INSTRUCTION PASTE DUE: the agile-skills
  Project gets its own copy.
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