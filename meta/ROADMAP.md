# ROADMAP

Standing reminder for the architect, at every milestone gate below: if
`docs/ARCHITECT-INSTRUCTION.md` changed since the last paste, hand the human
the complete new instruction text to paste into the claude.ai Project (the
human cannot see the installed copy; a stale one is invisible from inside a
chat). Missions 10 and 11 change it (kit check, the closed loop, the driver
role), and each Project onboarded in M5/M6 needs its own pasted copy.

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
  enabled. Mission 17: review 16 (the autonomy path), `reply <secret> <text>`
  on the command topic delivered as a `keep` to the architect's last
  session with its answer on the events topic, and self-hosted ntfy behind
  the Tailscale tunnel (free text about a project no longer crosses a
  public broker). Gate: one hands mission planned on the phone, handed to
  the role at the switch point, and run to a reviewed-clean stop with no
  human action; one escalation answered over `reply`.
  Requires: the driver role enabled (done 2026-09-17), the architect role
  enabled after review 17 finds the autonomy path closed, and one real
  consultation graded by a review.
- **M5 spanweave integration** — INSTRUCTION PASTE DUE: the spanweave
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
     milestone. The second series runs in role mode (M4c).
  Gate: one series of at least two runs merged with no human action
  between kickoff and the series-close stop.
- **M6 agile-skills integration** — INSTRUCTION PASTE DUE: the agile-skills
  Project gets its own copy.
  agile-skills integration — hands drives agile-skills' development;
  agile-skills stays machinery-agnostic and owns the mission-form contract
  (kickoff line, checkpoint resume, `VERDICT:` first line) as its own spec,
  of which hands is one consumer and never a dependency. Same steps with
  `meta/` paths and the mission form (`meta/BUILDER-N-PROMPT.md`, checkpoint-driven kickoff, no
  `resume_line`), which is the form hands has been exercised on. PR per
  mission, auto-merge on a clean review.
- **M7 (removed 2026-09-15):** the optional remote MCP face (DESIGN §9) is
  dropped from the roadmap; the phone loop and the architect role cover
  what it was for. DESIGN §9 stays as history.