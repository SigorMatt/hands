# BACKLOG — items the architect has committed to future missions

Maintained by the architect; the builder does not act on this file. Each
item names the mission it is scheduled for; unscheduled items say so.

## Mission 8 — DONE 2026-09-13 (review 8: blockers=0). Items 1–6 landed.

## Mission 9 — DONE 2026-09-13 (review 9: blockers=0).

## Mission 10 — DONE 2026-09-13 except who-by-pid (H-020; moved to 11).

## Mission 11 — DONE 2026-09-13 (review 11: blockers=5, the driver guard
   bypassable; driver role not enabled until mission 12).

## Mission 12 — DONE 2026-09-15 (review 12: blockers=3; the guard's comment hole).

## Mission 13 — DONE 2026-09-15 (review 13: blockers=4; the guard's heredoc hole).

## Mission 14 — DONE 2026-09-16 (review 14: blockers=2; role mode held; the command table).

## Mission 15 — DONE 2026-09-16 (review 15: blockers=4; the guard's `for`/`${…}` hole, role mode regressed; driver role disabled again).

## Mission 16 — DONE 2026-09-16 (review 16: blockers=2, neither the guard; driver role enabled 2026-09-17).

## Mission 17 — DONE 2026-09-17 (review 17: blockers=1, the start fold; autonomy path closed).

## Mission 18 — DONE 2026-09-17 (review 18: blockers=0, should-fix=4; the architect role enabled 2026-09-18).

## Mission 19 — DONE 2026-10-14 (review 19: blockers=0, should-fix=5; installed 2026-10-14).

## Mission 20 — BUILT 2026-10-14 on branch mission-20 (PR #2); review 20 (2026-10-15): blockers=1, should-fix=6; the PR stays open. Items 1–7, 9 (HF-003 only), the review-18 items and the title/topic item below landed; items 8 (HF-002, HF-004, HF-005, the silent first apply) and 10 are mission 22's.

## Mission 21 — DONE 2026-10-15 (review 21: blockers=0, should-fix=3; PR #2 merged by the review, 791f767; installed 2026-10-15). Spec: DESIGN v3.20 §37.

1. Review 20 blocker 1: the cancel race during the clone advance —
   `Spool.transition` judges the on-disk record; the runner re-reads after
   the advance and spawns nothing for a job no longer queued.
2. Review 20 should-fix 1, 2: `python3 -I` in both hook commands and
   doctor failing on a module beside the guard; the `--write` hook refuses
   hardlinked targets and any write while a link exists under `kits/`.
3. Review 20 should-fix 3, 4, 5: `origin: phone` refused from a socket
   client; `doctor --live` judges the resolved clone, a unique kit name,
   removes only what it made.
4. Review 20 should-fix 6: the protocol's revert step as the sub-agents did
   it (`git checkout <sha>~1 -- <files>`).
5. Review 20's note on U5: an apply that leaves no playbook stops.
6. Files H-046, H-047, H-048 for mission 22.

## Mission 23 — DONE 2026-10-16 (review 23: blockers=0, should-fix=9; PR #4 merged by the review, 2f81700; installed 13:45). Spec: DESIGN v3.22 §39.

1. Review 22 should-fix 1–12, each closed by a named unit (who tests and the
   stale fingerprint; orphaned reply/answer published; the start notice's
   reason; the blocked-regex check on samples; `progress` at the repo root
   and README's ten commands; inclusive owner-file fallbacks; the revert step
   for deleted files, H-055; the role's rulings as `escalate ruling:`;
   HF-002 in full with H-051; `project add` after a failed clone;
   `no_background.py` with `-I`, H-056).
2. H-051..H-054 ruled in §39: the consult prompt names the handbook and
   templates paths, the guard reads `HANDS_DOCS`, `hands handbook` allowed;
   U10's reading of `project add` confirmed; §38's two wrong sentences
   corrected (`status` shows every role; `[server]` is the fallback).
3. H-057 `aux.orphaned` event, the stop records it, `aux.orphaned → resume`
   in both templates and this playbook.
4. H-058 refusals of a secret-authenticated phone command are published;
   H-059 lenient job ids (`O`→`0`, `l`/`I`→`1`, case, unique prefix).
5. H-060 the resume path tells the builder to commit a dirty journal first.
6. `hands hosted-review <pr>` (docs/QODO-EXTRACTION.md): fetch, archive,
   diff by id, verdict from the Code Review comment, categories as found,
   "no bot comment yet" is a wait; the protocol runs it as a fresh-context
   sub-agent; the brief template's last unit fixes the bot's findings inside
   the PR with a disposition table in the final report.
7. Docs: restart kills every job; one hook vs two; stop pauses, apply+go
   un-pauses; the `[server]` fallback; QODO-EXTRACTION cited.

## Mission 25 — DONE 2026-10-17 (closer for review 24 on mission-24; review 25: blockers=0, should-fix=3, carried to missions 27 and 29; PR #5 merged by the review, 594b8ee; installed on both daemons 20:40). Spec: DESIGN v3.24 §41.

1. Blocker 1 and should-fix 1: the capture script records every timeout and
   redacts before it cuts; hanging-fake and straddling-secret tests.
2. Should-fix 2: the staged kit's name checks pinned (`..`, symlink, FIFO,
   directory, missing), `O_NONBLOCK` + `fstat`, the daemon removes a refused
   `.part`.
3. Should-fix 6, 7, 8: the `task_killed` key's session half and eviction;
   the ambiguous-prefix refusal with a backslash; the prompt cap counts the
   journal sentence.
4. Should-fix 4, 5: the WARN on a failing `playbook` line pinned; "stale"
   defined for the protocol's worktree cleanup and both commands pinned.
5. Should-fix 3: the probe record — Codex's VERDICT cell `partial`, the
   verbatim claim qualified, OpenCode/dsh rows filled where a sign-in now
   exists, one Codex approval-policy row attempted.
6. Adopted: a cli send equal to the kickoff line is a kickoff (hosted
   finding 3). The AppArmor host decision is the human's, outside hands.

## Mission 24 — DONE 2026-10-17 (PR #5; review 24: blockers=1, should-fix=8, closed by mission 25; merged with it, 594b8ee). Spec: DESIGN v3.23 §40.

1. U1 the probe on the laptop's three harnesses (Codex CLI 0.163.0, OpenCode
   1.19.2, dsh 0.2.0-rc.2; Node 22 by nvm, PATH prefix on every command),
   recorded in docs/HARNESS-PROBE.md: one-shot, event stream, resume,
   session store, sandbox and approval on an outside write and on `curl`,
   VERDICT honoured, documented limit output, telemetry switches, ACP;
   a harness not signed in is `unavailable`, Codex must be.
2. U2 `hands go` and `hands kit apply <zip>` (the phone's two commands at
   the laptop). U3 `task_killed` once per task and never on a daemon stop
   (H-062); the transcript path under `CLAUDE_CONFIG_DIR` (H-063).
3. U4, U5 review 23 should-fix 3–9; items 1 and 2 decided in §40 (H-064,
   H-065). U6 the kit-check and load WARN on a playbook with `aux.done` and
   no `aux.orphaned` (H-061). U7 the templates: `refused:` and `[b] refused`,
   the architect's "a unit no agent will author" escalation, worktree
   cleanup, the skip list, the gate once in the foreground (H-066..H-069).
4. U8 docs/OPERATIONS.md (inventory, the secrets table — kinds and sources,
   never values — and five runbooks), scripts/capture-quota-stop.sh, the
   doctor row for dangling worktrees. U9 docs. U10 the PR and its hosted
   review.
5. Source for the probe brief: docs/RELATED.md, Gas Town — its provider
   presets (`internal/config/agents.go` at `649b832`) and `opencode acp`
   proxy are the checklist; its four integration tiers name the level a
   harness must reach (their Tier 3). Cited, never imported.

## Order (2026-10-18: 01:33 project separation first; 03:08–03:12 the rest; small missions; renumbered 18:52, kept one mission at 19:22, DESIGN §43; renumbered 2026-10-19 01:42 and 19:3x, DESIGN §44) — 26 the separation (DONE); 27 the separation follow-up (DONE); 28 a pause that holds the next step (H-078) + review 27's should-fix 1–3 + H-077; 29 the pull-request gate (CI, the per-project `main` setting, applies and the review's commit through pull requests, docs/PR-CI-GATE.md, doctor); 30 M8b the harness seam with Codex (+ review 25's should-fix 3); 31 M8b's second mission, a local-model harness (OpenCode first); 32 M9 (+ review 25's should-fix 2); then M5b, a project from scratch (after 26), agile-skills migrated (after M9). Supersedes 2026-10-18 18:52's numbering (28 the seam, 29 the local harness, 30 M9), its 11:41 numbering and 2026-10-17 20:27's order. The 2026-10-17 23:25 kit for mission 26 (separation and profiles together) was never sent.

## Mission 26 — DONE 2026-10-18 (the project separation; review 26: blockers=0, should-fix=2, carried to mission 27; PR #6 merged by the review, f16d6d1; installed on both daemons 19:34). A project operated from its own chat and the phone. Spec: DESIGN v3.25 §42.

1. U0 the branch `mission-26`; H-070 (a report's twelve lines) and H-071
   (the architect guard on read-only commands), decided for mission 27;
   H-072 (a gate past the timeout on a shared machine), closed here; from
   another project's ledger (its HF-013, HF-014, HF-006's 2026-10-17
   update; evidence only).
2. U1 `consult <secret> <text>` (optional `.md` attachment) and `hands
   consult`, the consultation started by the engine (origin `playbook`,
   never a phone `reply`), counted against the budget, the command
   un-pausing first; architect/CLAUDE.md's new rule and rule 13; handbook
   §16 retires the recital.
3. U2 `hands digest` and `digest <secret>`: one redacted line per project,
   no daemon needed.
4. U3 the decisions kit (the phone's `kit` path files a brief-less kit of
   one owner file, pinned) and the owner file read on a resume (the brief
   template's §R).
5. U4 the handbook's §19 operator table (eight routes) with the HF report's
   form, §13's second onboarding shape, who operates a project and the
   playbook check, §18; the instruction's opening, rules 3, 9, 12 and 14
   reworded and rule 15, verbatim (INSTRUCTION PASTE DUE: hands,
   discotrade); OPERATIONS' no-phone rows; INTEGRATION's H-072. U5 the PR
   and its hosted review.

## Mission 27 — DONE 2026-10-19 (the separation follow-up, operations and safety fixes; review 27: blockers=0, should-fix=3, carried to mission 28; PR #7 merged by the review, d587fa6; installed for hands 2026-10-19, the other project's part waiting for its quiet moment). Spec: DESIGN v3.26 §43.

1. U0 the branch `mission-27`; H-074 (from another project's HF-015 and
   HF-016; evidence only), H-075 and H-076 filed; the correction line under
   FINAL-REPORT-25 §3 (review 25's should-fix 1).
2. U1 the base: the copies of the DESIGN wording §43 writes (H-027 §12
   rule 6 and §14's units; H-034 §10's example and its fixture, doc copy
   and tests; H-039 §34's start fold); the intermittent test (H-076,
   review 26's should-fix 1); review 26's untested `consult` refusals.
3. U2 the owner file named before every builder job but an apply (H-073),
   hands' sentences stripped wherever a stored prompt is read.
4. U3 H-074 rules 1–5: the hook admits an omitted sub-agent flag under
   `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS` (`1`/`true`/`yes`/`on`); the
   wheel ships the hook; doctor warns on a copy that is not the installed
   hands' copy (decided 2026-10-18 21:0x); the variable set for builder
   and aux only where the role's copy is that copy (decided 21:0x); the
   env table decides over it either way.
5. U4 the review protocols' report contents and the gate's timeout
   (H-070), the wait rule (H-074 rule 6), the guard's four read-only
   options and rule 10 (H-071).
6. U5 a role-filed kit that carries the playbook is held for the human
   (H-075); the role-mode kickoff that never changes.
7. U6 the operator table's missing rows (review 26's should-fix 2) and a
   test that reads the stop reasons and published lines from the code.
   U7 the PR and its hosted review.
8. Gate, after its install: a decisions kit and `go` on a project whose
   brief predates the mission-26 template, the ruling carried out; a
   builder under the default starts a sub-agent through the hook and a
   real command past its timeout ends with a timeout result; a project
   with the old hook keeps working, with the warn and without the
   variable; a role-filed kit carrying the playbook held for the human.

## Mission 28 (a pause that holds the next step; decided 2026-10-19 02:2x, split out 19:3x) — Spec: DESIGN v3.27 §44.

1. U0 the branch `mission-28`; H-078 filed (from another project's HF-017;
   evidence only); H-077's status set to the ruling.
2. U1 a human pause holds the next step: a role's end that would start it
   (a send, a consult, a stop, the engine's kickoff) is kept, one per role;
   `resume` rules fire until a stop has been suppressed under the pause,
   so a restart resumes the orphaned builder; every other stop under it
   is notified; only `resume` ends it — reloading the playbook (refused
   when one exists and does not load, or ends are kept and there is
   none), then replaying up to the first end that starts a step or stops;
   `go` and `consult` refused under it; kept ends persisted and
   shown by `hands pipeline` and `status`.
3. U2 `hands: at rest`, once per human pause; the handbook (§10, §14, §18,
   §19), docs/PLAYBOOK.md, docs/OPERATIONS.md; the operator table's reader
   matching titles at a row's start (review 27's should-fix 3).
4. U3 review 27's should-fix 1 (no zip read for a hold's reason on the
   event loop) and 2 (`doctor --live` builds its environment as a job does).
5. U4 H-077 ruled: an entry whose casefolded path equals the configured
   playbook path or either fixed name carries the playbook. U5 the PR and
   its hosted review.
6. Gate, after its install: on the other project, `pause` while its builder
   runs, `at rest` naming the kept end, its three waiting owner commits
   made at rest, `resume`, the kept end's step starting, read back from its
   branch; a restart under a human pause resuming the builder.

## Mission 29 (pull requests only, CI required; decided 2026-10-19 01:42) — DESIGN §44 records the facts; the kit writes the design (§45).

1. A CI workflow running `./scripts/check` on pull requests, green on
   GitHub's runner; its check's name read from a real run.
2. A per-project setting for how `main` moves: `direct` (the default) or
   `pull-request`. Under `pull-request`, a kit apply and a decisions kit land
   through a pull request merged once CI passes (the approval of the apply
   is the merge decision); the review commits `REVIEW-N.md` to the mission's
   branch before it merges; no `journal:` line lands on `main` directly;
   both protocols and the brief template carry the two shapes.
3. docs/PR-CI-GATE.md (the ruleset template; the hosted reviewer's check is
   never required; the order CI, setting, gate; at a stop with no job
   running); the handbook's onboarding and §19; doctor's report of the
   setting against the branch's rules.
4. Gate: after its install the aux creates the ruleset for this repository
   (`current_user_can_bypass: never`), and mission 30 runs entirely under
   it. The other project switches at a later quiet moment of its own.

## Mission 30 (M8b, the harness seam with Codex; renumbered several times — 25, then 26, then 27 in 2026-10-17 20:27's order and at 2026-10-18 03:08, 28 at 18:52 — and mission 30 since 2026-10-19 19:3x) — DESIGN §46 from docs/HARNESS-PROBE.md.

1. The seam: a per-harness runner or hands as an ACP client (the prior, if
   commands route through permission requests; the adapter
   `@zed-industries/codex-acp` is not installed); `[roles.<role>]
   harness`; the opaque harness profile; the four requirements per harness;
   Codex for the unguarded roles, unconfined (`danger-full-access`,
   decided 2026-10-18 03:08; no AppArmor profile); the guarded roles stay
   on Claude Code until a harness guard is reviewed.
2. The harness-neutral guard and transcript reader; the templates'
   Task-tool and worktree wording; doctor rows per harness; a privacy note.
3. Review 25's should-fix 3 (the probe record's approval flag in the form
   that ran, and its stray line break). Its should-fix 1, H-070, H-071 and
   the DESIGN wording of H-027, H-034 and H-039 went to mission 27
   (2026-10-18 18:52, DESIGN §43).
4. Gate: one hands mission built by a builder on Codex and reviewed clean.
   Split further if the kit grows past one review's size (small missions).

## Mission 31 (M8b's second mission; numbered 28 on 2026-10-18 11:41, 29 at 18:52, 31 since 2026-10-19 19:3x) — a harness for a local model (OpenCode or dsh, or both), OpenCode first. Re-checked 2026-10-18 03:28 by the aux: OpenCode 1.19.2 signed in (Nebius Token Factory, a credential file under `$HOME`, a default model set, a headless JSON one-shot answered); dsh unreachable by any hands job (its key is exported only for interactive shells; no `~/.dsh` credentials file) until the human writes one, with its session-log extension and telemetry disabled (DESIGN §40). Its own small mission, after mission 30.

## Mission 32 (M9, "a machine is replaceable"; 26, then 27, then 28 in 2026-10-17 20:27's order and at 2026-10-18 03:08; 29 at 11:41; 30 at 18:52; mission 32 since 2026-10-19 19:3x) — `hands export` / `hands import`, `hands upgrade [--accept-builder]`, `hands project refresh <p>` (replacing the laptop's merge script for architect/CLAUDE.md), the spool inventory, ntfy by MagicDNS name, docs/OPERATIONS.md updated; review 25's should-fix 2 (after a failed `find`, the capture script still writes the inbox tail; pinned by the hanging-`find` test); gate: the VM rehearsal. Split into two missions if it grows past one review's size. Then M5b (discotrade-v2 on Codex), a project from scratch (any time after mission 26 is installed), agile-skills migrated (M7, after M9).

## Backlog: Claude credential profiles (moved out of mission 26 on 2026-10-18; built when a usage limit actually hits) — DESIGN §42 "Decided and kept on disk for later missions".

1. The registry `~/.hands/profiles/profiles.toml` and the shared state
   `~/.hands/profiles/state.json` (locked, atomic; the name `profiles`
   reserved), `[roles.<r>] profiles`, `hands profiles` and `hands profiles
   clear <name>`; the profile's `env` refusals (`CLAUDE_CONFIG_DIR`, `PATH`,
   `HOME`, `HANDS_*`, hands' own variables, `ANTHROPIC_*`), an absolute
   `path_prefix`.
2. A job on a profile: chosen at dispatch, recorded, its environment
   (`CLAUDE_CONFIG_DIR`, the PATH prefix, the profile's env,
   `HANDS_PROFILE`), a `keep` refused on an exhausted profile, the
   unspawned `limited` end, `status`, the start notification, `who`.
3. A limit on a profile: mark, resume at once on the next eligible
   profile, or wait for the earliest reset with no stop; a limited keep
   job resumed with the kickoff; a restart reschedules by the rule; the
   classifier read from the installed CLI; `tests/fixtures/quota/`; the
   `builder.limited` notify rule in the three playbooks (`aux.limited` stays
   outside §10's events); docs/INTEGRATION.md's limit paragraph.
4. Doctor's profile rows and each profile home's settings layer for a
   guarded role; the trailer `Hands-Profile:` (a should-fix only when
   another commit of the mission carries it); the operator table's
   usage-limit row rewritten; OPERATIONS' usage-limit runbook.
5. Gate (the human's, after the install): a second Max account signed in
   as `claude-B`, the registry and the lists written, one real limit
   resumed on the next profile; the first real capture becomes the
   classifier's fixture.

## Backlog: M6 spanweave (moved 2026-10-18) — developed by the human without hands for now; may come later (ROADMAP M6 keeps the 2026-09-12 plan as history).

## Mission 22 — DONE 2026-10-15 (review 22: blockers=0, should-fix=12; PR #3 merged by the review, f11cfb1; installed 20:23; M4d closed). Spec: DESIGN v3.21 §38. Items 1–8 below plus: H-037 the buttons carry the token (FIRST; live on the self-hosted server since 2026-10-14, 403 on every button); review 21 should-fix 1–3 (H-049 the revert step for added files, H-050 the reviewer's schedule, the `-I` hook text in INTEGRATION); the human-supplied unit shape in the brief template and the protocol.

1. H-046: `handswho` publishes on a real state change only, compared
   without the relative-time text, with a floor on the interval; doctor
   WARNS on a public `ntfy_url` naming the daily cap and the self-hosted
   path. The laptop's who units stay stopped until this ships.
2. H-047: the daemon re-queues the kickoff for a builder job its own stop
   killed, bounded as `resume` is; the install routine stops costing a `go`.
3. H-048: under `autonomous`, a `blocked` builder verdict may consult the
   architect role (playbook rule), the consult prompt carrying the
   builder's reply in place of a review, against the same budget.
4. docs/INTEGRATION.md "Self-hosted ntfy over Tailscale" corrected from the
   2026-10-14 setup: the image `binwiederhier/ntfy`; no certificate domain
   → bind the tailnet address, plain http over Tailscale; `base-url` before
   the first start; `ntfy_topic` left under `[server]` refuses to load (the
   migration removes it); the access rule covers the who topics; the phone
   app's WebSockets option is fine without a proxy; the self-hosted server
   is the documented default for role mode.
5. Phone `progress <secret>`: job id and age, the working tree's branch,
   the last three commit subjects, the checkpoint's unit line. Handbook:
   `pipeline`'s `auto-runs` counts playbook-started runs only; `jobs`
   lists newest first.
6. Review 20's minor notes on U6: "since the last consultation" by the
   consultation's recorded sha rather than `git log --since`; the decisions
   path comparison for a builder cwd below the repository root.
7. Handbook: sub-agents refuse to author attack-shaped test content (a
   safety classifier; evidence: discotrade mission 13 U4, 2026-10-15), so a
   brief delivers such a suite as generated fixtures from a neutral spec;
   re-firing a consultation goes through the aux role's reply, never a
   direct send to the architect (refused by §31).
8. The onboarding half, as §36 lists it: HF-002 (handbook and templates
   from the installed hands), `hands project add`, the Purpose block,
   `templates/DECISIONS-owner.md` with the protocol's one-commit exception,
   the brief template's recovery rule for a `keep` answer, the handbook's
   onboarding shape, ruling round and separation rule, HF-004, HF-005, the
   first plan kit's silent apply. INSTRUCTION PASTE DUE after mission 22.


1. The architect role's write permission: `architect/settings.json` allows
   `Edit(kits/**)`, `Write(kits/**)`, `MultiEdit(kits/**)` and nothing wider;
   doctor checks exactly those; `doctor --live` for the architect writes and
   removes one file under `kits/` (laptop workaround applied 2026-10-12).
2. The runner advances the architect's (and driver's) clone to
   `origin/<branch>` before every job; doctor reports HEAD vs origin
   (laptop workaround: a transient timer pulling every minute).
3. The runner sets `HANDS_PROJECT` from the config on every role job, never
   from the environment; doctor's role rows print it (laptop workaround:
   the unit's env file).
4. HF-001: the engine reloads the playbook before deciding an apply's
   `builder.done` under autonomy; discotrade's probe test as the regression
   test; a mission-less kickoff line for this repository's playbook.
5. `answer <secret> <text>` on the command topic → `hands send --role
   builder --context keep`, origin phone, un-pauses, not held by the §8
   gate (the secret is the approval), with an optional attached file landed
   in `kit_dir`; the builder's final reply published titled `builder`;
   every answer and every owner decisions file since the architect's last
   consultation listed verbatim in its next consult prompt.
6. The hold notification under autonomy: decide before publishing; a
   buttonless "kit filed by the architect; apply approved by the playbook".
7. HF-006: `BASH_DEFAULT_TIMEOUT_MS` and `BASH_MAX_TIMEOUT_MS` set for
   builder and aux jobs unless the role's env table overrides them; the
   brief template's explicit gate timeout.
8. HF-002: the role reads the handbook and templates from the installed
   hands, not from the project's clone. HF-003: `cp` from `HANDS_CLONE` into
   `HANDS_KITS`. HF-004, HF-005: docs. The first plan kit's silent apply:
   docs. `doctor --live` exercises a real write, check and project lookup.
9. Review 18 should-fix 1–4: the Unicode full stop in `ntfy_url`; the guard
   module planted beside it; the kit record's bytes; the hardlink under
   `kits/`.
10. Project name in every notification title and in generated topic names
    (doctor warns); `hands project add <name> --repo <url>` ending with the
    filled instruction printed for pasting and the verification question;
    the Purpose block as a slot in both instruction templates;
    `templates/DECISIONS-owner.md`; the review-protocol template's
    one-commit exception for `plan: decisions <date> (owner)`; the brief
    template's recovery brief: a `keep` send after `VERDICT: question` is
    the answer, carried out, mission continued, a VERDICT line always; the
    onboarding shape and the ruling round in the handbook.

- Review 11 blockers 1–5 and should-fix 1–9; the guard rewritten on shlex
  tokens; consult stops in the engine; H-022 resolved. Spec: DESIGN v3.11
  §28. After it: enable `[roles.driver]`, refresh the driver kit, first
  real consultation, then M5.

## (specified in DESIGN §31, scheduled as mission 15) the architect role (decided 2026-09-15; ROADMAP M4c)

1. `[roles.architect]`: cwd `~/hands-architect/<project>/` with a fetch-only
   clone; CLAUDE.md = `docs/ARCHITECT-INSTRUCTION.md` (role variant: reads
   the handbook from the clone; outputs are kits under `kits/`); guard role
   mode `HANDS_ROLE=architect`: read-only git, `hands kit check`, `hands
   kit file`, `hands show|jobs|inbox|pipeline|status`; writes only under
   `kits/`; no send, no approve, no push; `permission_flags` empty.
2. `hands kit file <zip>`: files a held apply job exactly as the phone's
   `kit` does, from a local path under the architect's `kits/`.
3. `[series] architect = "phone" | "role"` and `[series] autonomous = true`:
   in role mode with autonomous set, kit applies from the architect role
   are approved by the engine (`decided_by: playbook`) and the kickoff is
   sent after `kit applied`; the human's approval of the playbook is the
   standing approval.
4. Consult on review outcomes: `aux.done` rules with `then = "consult"`,
   `role = "architect"`; the architect's verdict vocabulary and follow-up
   rules; `[limits] max_architect_consults` per series.
5. Escalation conditions in `[series]`: `gate_failures = 2`,
   `escalate_on = ["blocker-unanswered", "milestone-missing",
   "budget-exhausted"]`; each stops with a reason naming the condition and
   the architect's last session id.
6. `hands doctor` reports the architect role like the driver role.

## (specified in DESIGN §33, scheduled as mission 17) talking to the architect (decided 2026-09-15; ROADMAP M4c)

1. `reply <secret> <text>` on `cmd_topic`: delivered as `hands send --role
   architect --context keep` to the architect's last session; its reply's
   text is published on `ntfy_topic` (title `architect`); one job per turn.
2. `docs/INTEGRATION.md`: self-hosting ntfy in a container on the laptop,
   reachable through the Tailscale tunnel; both topics configured with
   `ntfy_url`; access control on the server so topics need credentials.
3. The escalation notification carries the architect's last session id and
   the one-line `claude --resume` for the Code tab route.

## Unscheduled

- **PR reviewer as a second verdict source.** A hosted PR review (bot or
  action) is one more cold reviewer whose verdict the playbook reads via
  `gh pr view`/checks; hands' own review could post as a PR review. A
  playbook rule and one tool, after M5's first auto-merge works.

- **tmux wake channel** — DROPPED 2026-10-18: the interactive driver session
  it served is retired. `handsd` (or a small watcher) sends a fixed
  `check` + Enter into the driver's tmux pane on `stop`/`held`, removing
  the human's message from the idle-time wake. Risk: `Enter` answers any
  open dialog in that pane. Decide from how many idle-time pokes the human
  actually makes across missions 5–7.
- **Remote MCP face** (DESIGN §9). Only if a chat brain as a second driver
  is wanted.
- **Authenticated approvals.** `decided_by: driver` is a declaration
  (DESIGN §8); authentication belongs to the remote face if built.
- **Driver guard: self-noise** — DROPPED 2026-10-18: the interactive driver
  session is retired. The driver's own gated send wakes its own
  wait; harmless, could be filtered by job origin.
