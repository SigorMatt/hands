# FINAL-REPORT-17 — review 16, talking to the architect

VERDICT: mission 17 finished

Brief: meta/BUILDER-17-PROMPT.md. Design: DESIGN v3.16 §33 (with §8, §11,
§26, §31, §32). Review closed: meta/reviews/REVIEW-16.md (blockers 1–2,
should-fix 1–8). Findings: H-035 and H-036 filed (U0) and resolved (code U1,
U2); H-037 filed (U8, open). H-034, H-027, H-001, H-009 stay open. Base 0b8447e
(`plan: mission 17 kit (DESIGN v3.16)`), green (3743 passed).

Numbering. The brief says "file H-034 … and H-035"; H-034 already existed
(mission 16 U5), so blocker 1 is H-035 and blocker 2 is H-036 throughout.

## 1. What changed (sha per unit)

| Unit | Commit | What | Gate |
|---|---|---|---|
| U0 Plan and bookkeeping | c5b5416 | plan, checkpoint; H-035, H-036 filed; H-034's "byte for byte" corrected by a dated line; FINAL-REPORT-16's REVIEW-15 blocker 3 row and §3.2 corrected by a dated block; should-fix 8: both templates' `task_killed` message names no cause, docs/PLAYBOOK.md's closing sentence hedged, the stale docstring fixed | 3/3, 3747 |
| U1 The daemon checks what it approves | f6f7f26 | `kit_file` runs `check_kit` on the stored zip against the served repository, refuses and deletes a failing kit; `kit.json` records `check: pass`, required by the engine; a consultation's kit decided when the verdict is known; one kit named by `VERDICT: next kit <name>`, else every such hold denied and `escalate`; `kit check` judges a role-mode playbook against the config and fails when none, two, or an invalid one resolves | 3/3, 3761 |
| U2 Zip names | 6f05e4e | one judge (`_zip_entries`) over central-directory names; local-header or 0x7075 disagreement refused; `.git`/`.claude` at any depth and case refused; symlink escapes refused; shared by `kit check`, `kit_file` and the phone's kit path | 3/3, 3784 |
| U3 Architect mode and doctor | 2a08e42 | guard: `cp`/`mv` refused while anything under `HANDS_KITS` is a symlink, every KITS row refused when `HANDS_KITS` is one; doctor's role rows read `settings.json` and `settings.local.json`, fail `disableAllHooks`, `bypassPermissions`/`acceptEdits`, wildcard allows, non-command hooks, loose matchers, push URLs not `no_push`-shaped and `pushDefault`/`pushRemote`, a symlinked `kits`; rows print `verified:` | 3/3, 3879 |
| U4 Prompt and notifications | c6380ab | a milestone is done only when `DONE` is in or right after its bold heading (fixture roadmap); a start that inherits queued jobs folds their publishes into the one "handsd started", bounded by `START_FOLD_S` (5 s) | 3/3, 3897 |
| U5 `reply` | de17a7e | `reply <secret> <text>` on `cmd_topic` → `Api.reply_architect` (phone only): role architect, context keep, origin phone, text verbatim; refused with no `[roles.architect]`, an architect job running/queued/held, a `next kit` wait, or no session; the answer published titled `architect`; a reply job is not a consultation and `kit_file` refuses during one | 3/3, 3908 |
| U6 Self-hosted ntfy | 4775880 | `[notify] ntfy_token` validated, never printed; bearer on every publish, `notify --test`, the `cmd_topic` subscription and `handswho`; doctor `ntfy token on|off`; INTEGRATION: ntfy in a container with deny-all access, via Tailscale, moving the topics | 3/3, 3935 |
| U7 This repository's playbook | 63ac5c3 | `[series] kickoff` names meta/BUILDER-18-PROMPT.md; nothing else; loads (20 rules, phone, not autonomous); a kit of meta/BUILDER-17-PROMPT.md checked `--repo .` passes 6 of 6, exit 0 | 3/3, 3935 |
| U8 Final report | (this commit) | this file; H-035/H-036 code lines and status; H-037 filed; plan, checkpoint, journal | 3/3, 3935 |

## 2. What the tests prove

- **The daemon checks what it approves (U1).** End to end with a real daemon,
  fake_claude and a committed role + autonomous playbook: the reviewer's
  raw-socket `kit_file` of a kit that fails `hands kit check`, during an
  architect consultation, is refused and never `decided_by: playbook` — the
  acceptance test "a kit that fails `hands kit check` is never engine-approved";
  a passing kit named by the verdict is engine-approved; two kits in one
  consultation → both denied, `escalate`; a kit whose name differs from the
  verdict's → denied, `escalate`; a forged `kit.json` without a passing check is
  not approved; `kit check` fails the no-config, two-config and invalid-TOML
  cases that used to pass.
- **Zip names (U2).** The reviewer's zip (central and local name
  `docs/notes.md`, 0x7075 naming `.git/hooks/pre-commit`), a variant with the
  0x7075 field only in the local header, and one whose local and central raw
  names differ are refused by `kit check` (paths fails), `apply_from_zip`, a
  real daemon's socket `kit_file` (nothing filed or kept) and the phone path
  (`kit.refused`, no job); a clean kit is then filed; `.claude` entries and
  symlinks into `.claude`/`.git` are refused; a matching 0x7075 field is
  accepted. A witness test shows `unzip -o` does write `.git/hooks/pre-commit`
  from the crafted zip.
- **Architect mode and doctor (U3).** The reviewer's `cp -r kits/a/h kits/`
  then `cp kits/pay/h kits/` sequence under real bash leaves the guard file
  byte-equal (before the fix it wrote "# NEUTERED"); `ln -s .claude kits` makes
  the guard's `--write` for `.claude/settings.json` exit non-zero and doctor's
  architect row fail; each of should-fix 4's probes (a second push remote by
  `pushDefault`/`pushRemote`, `settings.local.json` with `disableAllHooks` and
  `bypassPermissions`, `Write(**)`, `Edit(/**)`, `Bash(*:*)`, `acceptEdits`, a
  `type: prompt` hook under `ulti.dit|as` or `bash`) fails the row; the shipped
  driver and architect settings still pass. 95 cases, 85 red first.
- **Prompt and notifications (U4).** On tests/fixtures/roadmap_headings.md the
  next milestone is the entry whose first line carries "mission 10 DONE" but
  whose heading is not DONE; all-done and none are stated. With a real Daemon
  and the phone on, each of the reviewer's three shapes (a queued consult
  driver job with no verdict, a failing builder, a failing aux) publishes
  exactly one notification during start, naming what happened.
- **`reply` (U5).** With a mocked stream and fake_claude as the architect: the
  round trip (command → architect job, origin phone, context keep on the last
  session, text verbatim in the record → the answer published titled
  `architect`); refusals with no session, while a consultation runs, with no
  `[roles.architect]`, with a queued or held architect job and during a
  `next kit` wait; a wrong secret and empty text; a kit filed during a reply
  job refused. The escalation notification's session id and `claude --resume
  <id>` line were already pinned in tests/test_playbook.py.
- **Self-hosted ntfy (U6).** Against a fake server that answers 401 without
  the bearer: every publish, `hands notify --test`, the daemon's `cmd_topic`
  subscription (it answers a `status` command) and `handswho`'s publish and
  subscription send `Authorization: Bearer` when the token is set, and nothing
  sends it when unset; a publish without the token is recorded as failed with
  "ntfy answered 401"; a bad token is refused naming the key and not the value;
  doctor prints `ntfy token on`/`off`; the value appears in no output, log or
  spool file the tests write.
- **Playbook (U7).** The kickoff pin was red on the value at 4775880; the
  committed file loads; the kit check passes 6 of 6.

## 3. NOT PROVEN

1. **A real `reply` round trip.** No phone, no ntfy server and no `claude
   --resume` of a real architect session ran. A reply held by a gate pattern
   is untested; a queued reply cancelled, or orphaned by a daemon restart,
   publishes nothing.
2. **A real self-hosted ntfy.** No container, no server.yml, no Tailscale
   tunnel and no phone app ran; docs/INTEGRATION.md's server steps are written
   from the ntfy and Tailscale docs and marked not run. Whether the ntfy app
   signs in with an access token, whether attachments need auth, and whether
   the Approve/Deny buttons work on a token-protected server are unknown: the
   buttons carry no token (H-037, open).
3. **A real architect session.** No Claude Code session ran the architect's
   hooks, filed a kit, or reached `escalate`. U1's decision at the verdict is
   in memory: a daemon restart between a kit's hold and its consultation's
   verdict is untested, as are concurrent `kit_file` calls and a double notify
   when a rule-breaking kit arrives.
4. **The phone architect's sandbox.** U1 dropped the pass `kit check` gave a
   role-mode playbook when no config resolves (§33: the check "judges"). A kit
   carrying a role-mode playbook now fails in the phone architect's sandbox and
   must be checked at the laptop; docs say so. No finding was filed; the
   architect may want one.
5. **Zip names.** Zips with several end-of-central-directory records (which
   one Python and every `unzip` pick), filesystem aliases of `.git`/`.claude`
   (trailing dots or spaces, ignorable characters, 8.3 names) and names that
   differ only in case are not tested.
6. **Doctor.** Claude Code matches hooks with a JavaScript regex, not Python
   `re`; user and managed settings are not read; hardlinks under `kits`,
   path-specific allow entries (`Write(/home/**)`), hooks on other events and
   the race between the guard's decision and the command are not covered.
7. **Notifications.** The heading rule is proven on the fixture and the listed
   first-line shapes only; the 5 s fold bound is tested at 0.5 s; a stop during
   the fold window may not deliver the notification; a hold inside the window
   is listed without its buttons.
8. **U7's kit-check gate is weak** (REVIEW-16's note on mission 16 U6 still
   applies): the kit carries no playbook, so the new kickoff value is never
   compared and the gate passes the same way at 4775880. meta/BUILDER-18-PROMPT.md
   does not exist; the architect ships it.

## Review items

| Item | Unit | Commit | State |
|---|---|---|---|
| REVIEW-16 blocker 1 — a socket client files an `origin: architect` apply the engine approves without the kit check | U1 | f6f7f26 | closed (`kit_file` runs `check_kit` on the stored bytes; the engine requires a recorded pass; the reviewer's probe is an acceptance test; H-035; restart and concurrency not proven, §3.3) |
| REVIEW-16 blocker 2 — entry names that disagree get past the path rules and write into `.git` | U2 | 6f05e4e | closed (one judge over central-directory names, mismatches refused, shared by daemon, `kit check` and phone; H-036; limits §3.5) |
| REVIEW-16 should-fix 1 — one consultation files any number of kits, any name | U1 | f6f7f26 | closed (one kit named by the verdict, else all denied and `escalate`) |
| REVIEW-16 should-fix 2 — architect `cp` writes through a symlink inside `kits/` | U3 | 2a08e42 | closed (`cp`/`mv` refused while anything under `HANDS_KITS` is a symlink; the reviewer's sequence under real bash) |
| REVIEW-16 should-fix 3 — doctor passes a `kits` symlinked to `.claude` | U3 | 2a08e42 | closed (`HANDS_KITS` a symlink refuses every KITS row; doctor fails the row) |
| REVIEW-16 should-fix 4 — doctor's role rows `ok` on settings that switch off what they check | U3 | 2a08e42 | closed (push remotes, `settings.local.json`, allow entries, matchers, non-command hooks; limits §3.6) |
| REVIEW-16 should-fix 5 — `kit check` passes a role-mode kit it has not judged | U1 | f6f7f26 | closed (no config, two configs, invalid TOML fail; the phone sandbox consequence, §3.4) |
| REVIEW-16 should-fix 6 — "next unmet milestone" not §32's rule | U4 | c6380ab | closed (DONE on the heading, pinned on a fixture roadmap; §33 states the rule, so no finding needed) |
| REVIEW-16 should-fix 7 — daemon start publishes twice when a queued job fails at once | U4 | c6380ab | closed (folded into one, bounded at 5 s; §3.7) |
| REVIEW-16 should-fix 8 — the sweep's text names a cause; H-034 overstates a pin | U0 | c5b5416 | closed (templates and docs/PLAYBOOK.md name no cause, pinned; docstring fixed; H-034 corrected by a dated line) |

## 4. Acceptance

- `./scripts/check` green on the pushed tip, three consecutive runs: 3935
  passed each (run on 63ac5c3's tree plus this commit's meta files).
- Every unit commit's body lists every file it touches (checked against `git
  show --name-only` for c5b5416 through 63ac5c3); U0 is `plan:`.
- A kit that fails `hands kit check` is never engine-approved: U1's
  end-to-end acceptance test.
- `hands doctor` shows the ntfy token as on/off (U6, pinned); `reply` is
  documented in docs/INTEGRATION.md, docs/ARCHITECT-HANDBOOK.md and README.md
  (U5, pinned).
- This file exists with NOT PROVEN and the review-items table.

## 5. For the architect

- H-037: choose how the Approve/Deny buttons authenticate on a token-protected
  ntfy (headers in the action, a separate write token, or no buttons).
- H-034 is still open: DESIGN §10's example and §24 say `stop` for
  `monitor.task_killed`.
- U1's choices where §33 is silent: a second kit is accepted and held, then
  denied with the first; the phone architect's sandbox can no longer pass a
  role-mode kit (§3.4).
- U5's choice: `reply` refusals are published on the phone (`hands: reply`),
  while other refused commands are only logged.
- The architect role stays off until this mission's review (§33).

Correction appended 2026-09-17 (mission 18 U0, from REVIEW-17 should-fix 2):
- §2, U1: "two kits in one consultation → both denied, `escalate`" is wider
  than the tests. `test_a_second_kit_in_one_consultation_is_denied_and_the_consultation_escalates`
  proves both denied only when both kits are filed while the architect job
  runs and are decided at its verdict; when a second kit arrives after the
  first was approved, only the second is denied. REVIEW-17 filed two
  `kit_file foo` calls concurrently during the `next kit` wait: both were
  held, the first was `approved by=playbook` and applied, the second denied,
  and the consultation escalated ("filed 2 kits"). Read the claim as: a
  consultation that files two kits escalates and the second is denied; the
  first is not always denied. §3.3's "concurrent `kit_file` calls" is thereby
  shown, not just untested. Mission 18 U2 serializes `kit_file` per
  consultation (DESIGN v3.17 §34).
- §3.7's "a hold inside the window is listed without its buttons" is a design
  violation, not a limit (REVIEW-17 blocker 1; H-038), and "a stop during the
  fold window may not deliver" was reproduced (should-fix 6). Mission 18 U1.
