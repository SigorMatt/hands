# plan — mission 17 (review 16; talking to the architect)

Source: meta/BUILDER-17-PROMPT.md, DESIGN v3.16 §33 (with §8, §11, §26, §31,
§32), meta/reviews/REVIEW-16.md. Units run in order; each ends with a commit
and a push. `[x]` = done and pushed, `[b]` = blocked (two failures).

Base of the mission: 0b8447e (`plan: mission 17 kit (DESIGN v3.16)`), green
(3743 passed).

- [ ] U0 Plan and bookkeeping (`plan:`) — this file, meta/CHECKPOINT.md;
      H-035 filed (the daemon must run the check it approves on, blocker 1)
      and H-036 (zip names, blocker 2); FINAL-REPORT-16's review-items row
      for REVIEW-15 blocker 3 and its §3.2 corrected by appended dated
      lines; should-fix 8: both templates' `task_killed` messages and
      docs/PLAYBOOK.md name no cause, the stale test docstring fixed, H-034's
      "byte for byte" overstatement corrected by an appended line
- [ ] U1 The daemon checks what it approves (§33; blocker 1; should-fix 1, 5)
- [ ] U2 Zip names (§33; blocker 2)
- [ ] U3 Architect mode and doctor (§33; should-fix 2, 3, 4)
- [ ] U4 Prompt and notifications (§33; should-fix 6, 7)
- [ ] U5 `reply` (§33)
- [ ] U6 Self-hosted ntfy (§33)
- [ ] U7 This repository's playbook (kickoff names BUILDER-18)
- [ ] U8 Final report (meta/FINAL-REPORT-17.md)

Review items by unit. REVIEW-16 blocker 1 → U1; blocker 2 → U2; should-fix
1, 5 → U1; should-fix 2, 3, 4 → U3; should-fix 6, 7 → U4; should-fix 8 → U0.

Scope choices (orchestrator's):
- Numbering. The brief says "file H-034 … and H-035", but H-034 already
  exists (mission 16 U5: §10's example still says `stop`). The two new
  findings are filed as H-035 (the daemon runs the check it approves on) and
  H-036 (zip names). Every reference in this mission uses those numbers.
- Should-fix 8 touches templates, docs/PLAYBOOK.md and a test docstring, not
  src/. It is text, and the brief places it in U0; a sub-agent makes those
  edits and they are folded into the `plan:` commit (as missions 15 and 16
  U0 did with base fixes).
- REVIEW-16's Notes (over-refusals, the budget's "restated", events that fire
  nothing, U2 nested kit dirs, pushInsteadOf docstring, U6's weak gate) are
  observations, not items, and are not taken unless a unit's own work
  touches them.

Dependencies. U2's shared zip judge is used by `kit_file`, which U1 changes:
U1 then U2, each keeping the other's tests green. U3 edits the guard and
doctor. U4 edits playbook prompt and notifier start. U5 needs the command
channel and the escalation notification; U6 touches the same ntfy client:
U5 before U6. U7 and U8 last.

Findings. H-035, H-036 filed by U0. H-034 (§10/§24 `stop`), H-027, H-001,
H-009 stay open.
