# CHECKPOINT

Mission: 10 (meta/BUILDER-10-PROMPT.md, DESIGN v3.9 §26)
Unit in progress: U2 `[series] kickoff` and `go` (§10, §11, §26; H-018 gaps 1, 2).
Intent:
- Playbook loader accepts `[series] kickoff = "<line>"` (optional, non-empty
  string per §20); any other key in `[series]` refused at load.
- Phone channel (`cmd_topic`) accepts `go <secret>`. Refused, with a logged
  reason, when no playbook is loaded, when `[series] kickoff` is absent, or when
  the builder has a running or queued job. Otherwise: that line as a `clear`
  send to the builder with `origin: phone`, and an answer on `ntfy_topic` with
  the job id.
- H-018 gap 1: `phone` added to the origin vocabulary (spool ORIGINS). Gap 2:
  `phone` un-pauses the pipeline when its job starts (UNPAUSE_ORIGINS), so a `go`
  after a stop chains the review; a paused playbook is still "loaded".
- docs/PLAYBOOK.md and docs/INTEGRATION.md updated; root PLAYBOOK.toml gains
  `[series] kickoff = "Read meta/BUILDER-11-PROMPT.md and execute the mission
  below its divider."`.
Done means: one commit, body names U2, §10/§11/§26, H-018, lists every file;
tests for each refusal and the happy path; the playbook end-to-end still
passes; pushed; ./scripts/check green 3/3.
Base: 61e1486.
Done: U0 cbb8fc8 (1435 passed); U1 17ba97e (1443).
Standing constraints: one foreground sub-agent per product unit, commit and
push every unit, ./scripts/check green three consecutive runs before each
commit, explicit paths only in `git add` (never `-A`), reports drafted under
meta/drafts/, DESIGN.md is not edited by builders (file a finding), sub-agents
do not edit meta/plan.md or this file.
