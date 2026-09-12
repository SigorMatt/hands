# ROADMAP

Milestones are gated by a clean cold review of the mission that closes them,
then an install (`uv tool install --force`) and a driver-kit refresh.

- **M1 Core** — DONE 2026-09-11 (mission 1). Dispatch, gates, playbook,
  limits, monitor, inbox, ntfy, driver kit.
- **M2 Shakeout on hands itself** — DONE 2026-09-11 (mission 2). A run
  chained into a cold review with no human action between; ntfy proven.
- **M3 Hardening by review** — missions 3–6, IN PROGRESS. Each review's
  blockers closed by the next mission; the Bash guard converges on a
  per-subcommand option allowlist; the driver's background wait retired;
  determinism as a property. Gate: a mission whose cold review has zero
  blockers, so a build can be installed and the driver kit refreshed.
- **M4 Detectors and the phone channel** — mission 7. Harness-killed
  background tasks detected from the stream; per-job systemd scope with
  orphan accounting; ntfy command channel with authenticated approvals
  (`decided_by: phone`); REVIEW-3's deferred items. Gate: clean review,
  install, and the doctor wake check redone over the phone channel.
- **M5 spanweave integration** — hands drives spanweave's *development*
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
  5. First series is a shakeout: expect doc-versus-reality findings, keep
     it short, and treat the first auto-merge as the milestone.
  Gate: one series of at least two runs merged with no human action
  between kickoff and the series-close stop.
- **M6 agile-skills integration** — hands drives agile-skills' development;
  agile-skills stays machinery-agnostic and owns the mission-form contract
  (kickoff line, checkpoint resume, `VERDICT:` first line) as its own spec,
  of which hands is one consumer and never a dependency. Same steps with
  `meta/` paths and the mission form (`meta/BUILDER-N-PROMPT.md`, checkpoint-driven kickoff, no
  `resume_line`), which is the form hands has been exercised on. PR per
  mission, auto-merge on a clean review.
- **M7 Optional remote face** (DESIGN §9) — only if a chat brain as a
  second driver is wanted after M5/M6.
