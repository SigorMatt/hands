# plan — mission 17 (review 16; talking to the architect)

Source: meta/BUILDER-17-PROMPT.md, DESIGN v3.16 §33 (with §8, §11, §26, §31,
§32), meta/reviews/REVIEW-16.md. Units run in order; each ends with a commit
and a push. `[x]` = done and pushed, `[b]` = blocked (two failures).

Base of the mission: 0b8447e (`plan: mission 17 kit (DESIGN v3.16)`), green
(3743 passed).

- [x] U0 Plan and bookkeeping (`plan:`) c5b5416 — this file, meta/CHECKPOINT.md;
      H-035 filed (the daemon must run the check it approves on, blocker 1)
      and H-036 (zip names, blocker 2); FINAL-REPORT-16's review-items row
      for REVIEW-15 blocker 3 and its §3.2 corrected by appended dated
      lines; should-fix 8: both templates' `task_killed` messages and
      docs/PLAYBOOK.md name no cause, the stale test docstring fixed, H-034's
      "byte for byte" overstatement corrected by an appended line
- [x] U1 The daemon checks what it approves (§33; blocker 1; should-fix 1, 5)
      f6f7f26 — kit_file runs check_kit on the stored zip (refused and deleted
      on failure; kit.json records check pass); engine decides a consultation's
      kit when the verdict is known; one kit named by the verdict, else all
      denied (deny_from_playbook) and escalate; kit check judges role
      requirements, no silent pass without a config
- [x] U2 Zip names (§33; blocker 2) 6f05e4e — one judge `_zip_entries`
      (central name; local header or 0x7075 disagreement refused; .git/.claude
      at any depth and case, symlink escapes, non-UTF-8-flagged non-ASCII)
      used by _read_zip and apply_from_zip; refused by kit check, kit_file,
      the phone path
- [x] U3 Architect mode and doctor (§33; should-fix 2, 3, 4) 2a08e42 —
      cp/mv refused while anything under HANDS_KITS is a symlink, every KITS
      row refused when HANDS_KITS is one; doctor's role rows read settings.json
      and settings.local.json, fail disableAllHooks, bypass/acceptEdits,
      wildcard allows, non-command hooks, loose matchers, non-no_push push
      URLs and pushDefault/pushRemote, a symlinked kits; `verified:` lines
- [x] U4 Prompt and notifications (§33; should-fix 6, 7) c6380ab — a
      milestone is done only when DONE is in or right after its bold heading
      (fixture tests/fixtures/roadmap_headings.md names M4b); start with
      inherited queued jobs folds publishes until they end or START_FOLD_S
      (5 s) into the one "handsd started"
- [x] U5 `reply` (§33) de17a7e — cmd_topic `reply <secret> <text>` →
      Api.reply_architect (phone only; Api.send still refuses architect):
      role architect, context keep, origin phone, text verbatim; refused with
      no [roles.architect], an architect job running/queued/held, a next-kit
      wait, or no session (refusals published as `hands: reply`); answer
      published titled `architect`; a reply job is not a consultation
- [x] U6 Self-hosted ntfy (§33) 4775880 — `[notify] ntfy_token` validated
      and never printed; bearer on every publish, notify --test, the cmd_topic
      subscription and handswho, same-origin kit attachments only; doctor
      `ntfy token on|off`; INTEGRATION's container + Tailscale + moving-topics
      section (not run); Approve/Deny buttons carry no token → H-037
- [x] U7 This repository's playbook (kickoff names BUILDER-18) 63ac5c3 —
      loads (20 rules); kit of BUILDER-17 brief `--repo .` 6 of 6, exit 0
- [x] U8 Final report (meta/FINAL-REPORT-17.md) (the commit that carries
      this line) — drafted under meta/drafts/, moved in with the mission's
      meta bookkeeping; H-035/H-036 code lines and status; H-037 filed

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

Findings. H-035, H-036 filed by U0, resolved (code U1, U2). H-037 filed by
U8 (Approve/Deny buttons carry no ntfy token; open, the architect's). H-034
(§10/§24 `stop`), H-027, H-001, H-009 stay open.
