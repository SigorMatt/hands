VERDICT: mission 15 finished

# FINAL-REPORT-15 — hands mission 15: the guard's command table, review 14, the architect role

Brief: meta/BUILDER-15-PROMPT.md. Design: DESIGN v3.14 §31 (with §8, §10, §11,
§12, §26, §27, §30). Review closed: meta/reviews/REVIEW-14.md (blockers 1–2,
should-fix 1–7). Findings: H-028 and H-029 filed and resolved by v3.14; H-030,
H-031 and H-032 filed by units and **open**. Base: 1f8141c (`plan: mission 15
kit (DESIGN v3.14, architect kit)`).

## 1. What changed (sha per unit)

| Unit | Commit | What | Gate |
|---|---|---|---|
| U0 Plan and bookkeeping | 1a48e11 | plan; H-028 (the command table) and H-029 (the architect role) filed; should-fix 7: doctor's `go` row warns when the kickoff plainly names a file the repository lacks; `spool.ORIGINS` gains `architect`, which the base commit left red | 3/3, 2605 |
| U1 The guard's command table | d32f409 | `COMMAND_TABLE` replaces `ALLOWED_FIRST_WORDS`: one row per command with only §31's options, judged by one lookup in both modes; 21 words refused by name; the reviewer's three probes blocked; a 10k fuzz corpus; role mode widened to the read-only rows | 3/3, 2721 |
| U2 Notifications and doctor | 6b27320 | blocker 2 and should-fix 1–6, one test each: the kit pair spaced on every branch; one daemon-start notification; the limit pair documented as implemented; doctor judges every Bash hook; an empty project name refused; the `ConsultAnchor`; the false-positive rows pinned | 3/3, 2751 |
| U3 Architect guard mode and `hands kit file` | adf3d7a | `HANDS_ROLE=architect` as a third mode; `HANDS_KITS` confinement for `mkdir cp mv zip unzip`; the `--write` matcher; `[roles.architect]`; `hands kit file <zip>` checks then files the held apply with `origin: architect`; H-030 filed | 3/3, 3013 |
| U4 Series mode and autonomy | c9ccc18 | `[series] architect`/`autonomous`/`gate_failures`/`escalate_on`, `[limits] max_architect_consults`; the engine approves an `origin: architect` hold as `decided_by: playbook`; the engine-added kickoff rule after `VERDICT: kit applied`; H-031 filed | 3/3, 3063 |
| U5 Consult for the architect | 9ed931b | `consult` with `role = "architect"` on `aux.done`; the four-part prompt; `next kit` \| `series complete` \| `escalate`; the escalation notification with the session id and `claude --resume`; the per-series budget the engine spends itself | 3/3, 3092 |
| U6 Docs and the templates | f798521 | doctor's `role architect` row (both hook matchers judged); `kit file`'s stale line corrected; INTEGRATION, PLAYBOOK, ARCHITECT-HANDBOOK §12 and both templates; ~20 doc claims pinned to code constants; H-032 filed | 3/3, 3126 |
| U7 This repository's playbook | fd1a2dd | `[series] kickoff` → BUILDER-16; `architect = "phone"` stated; the kit check of this brief exits 0 (6 of 6) | 3/3, 3126 |
| U8 Final report | this commit | this file, meta bookkeeping | — |

The mission's meta bookkeeping (meta/plan.md, meta/CHECKPOINT.md,
meta/journal.md) was held uncommitted between units and lands with this
commit, so mission 15 has no `meta:` commits between units. Units U3–U6 each
appended one finding to meta/findings/FINDINGS.md inside their own commit.

## 2. What the tests prove

- **U0.** Doctor's `go` row is `ok` when the kickoff names a brief that
  exists, `warn` naming the file when it does not, and `ok` for five
  kickoffs that name no path (bare `README`, `HEAD`, `TODO`, `API`, `e.g.`,
  `newdir/notes`). A warn keeps `doctor: green`, exit 0 and `"green": true`.
  `spool.ORIGINS` and DESIGN §6's listing agree.
- **U1.** The reviewer's three probes exit 2 in **both** modes through the
  shipped file with hook JSON on stdin (they exited 0 at 1a48e11, and no file
  is created now). 22 removed words are refused **by name** in three shapes ×
  two modes. A deterministic corpus (seed 20260916) of 10,000 commands over
  the removed words' real write and execute options is refused in both modes —
  20,000 `check()` calls in 1.8 s. Every command line `driver/CLAUDE.md`
  shows (14) passes the guard. The self-test is 235/235 at that commit.
- **U2.** Seven items, seven tests, each red first with the failure line in
  the commit body. The kit pair's ordinary branch (a kit with **no** KIT.md,
  the case the mission-14 test avoided) shows receipt → 1.1 s → hold → 1.1 s →
  explanation. Daemon start publishes one notification. Doctor exits 1 on the
  real guard *plus* a permissive second Bash hook. `hands --project ""` is
  refused instead of acting on another project. The anchor's job id and daemon
  start read back off disk. 22 false-positive rows are pinned in the fixture
  with no change to `kit.NAMED_PATH_RULE`.
- **U3.** Architect mode's allowed and refused tables; the `HANDS_KITS` pin
  against a path outside it, a `..` path, a real symlink, a relative path, a
  `~` path, and `HANDS_KITS` unset and empty; the five write words exist in
  no other mode; the write matcher through `main` and through the shipped file
  as a subprocess, fail-closed on every other tool, shape and mode;
  `architect/settings.json` agrees with the CLI and the guard;
  `[roles.architect]`'s three environment variables on a real job; `kit file`
  refusing a kit outside `HANDS_KITS` and a kit that fails the check (carrying
  the check's own output), and filing the held `origin: architect` job over a
  real daemon socket. Self-test 315/315.
- **U4.** Every new `[series]` and `[limits]` key, and every refusal, at load.
  The engine approves **only** an `origin: architect` hold, **only** under
  `architect = "role"` and `autonomous = true`, never while paused; §8's gate
  authority table gains the `playbook` row plus two narrowing tests. The
  engine-added kickoff rule is prepended and wins over a playbook's own
  `kit applied` rule (the inbox records `rule: -1`). The end-to-end gate —
  filed → `decided_by: playbook` → applied → kickoff sent — is asserted from
  the spool records, not the final state.
- **U5.** Four end-to-end runs with `fake_claude` as the architect, one per
  verdict (`next kit`, `series complete`, `escalate`, budget exhausted),
  asserted from the spool and the inbox; the escalation notification carries
  the reason, the session id and the `claude --resume <id>` line. The prompt's
  four parts are pinned verbatim, with a soft fallback (the whole reply) when
  a review heading is missing or spelled differently. `next kit` with no
  `origin: architect` job filed after the architect's own job stops and
  notifies rather than stalling the series silently.
- **U6.** Doctor's architect row, including a refusal for a non-empty
  `permission_flags` and for a write matcher that is not the guard, and a row
  for the shipped `architect/settings.json`. Both templates load through the
  real loader with their architect block programmatically uncommented. ~20
  doc sentences are pinned against code constants, the switch-point quotation
  against `architect/README.md`, and the H-030 sentence against the ledger
  while that finding is open.
- **U7.** The repository's playbook pins `kickoff` to BUILDER-16,
  `architect == "phone"` written out (not defaulted) and the `[series]` keys
  exactly `architect, kickoff, name`. Red was produced the right way — a
  detached worktree at the parent carrying only the new test; the wrong red
  (`PlaybookNotCommitted`) was observed in place and rejected.

## 3. NOT PROVEN

**3.0 The two the brief names.**
- **No real architect consultation has happened.** Every `consult` end-to-end
  in U5 uses `tests/fake_claude.py`. No `claude` process has ever run with
  `HANDS_ROLE=architect`, so the role's CLAUDE.md, its guard mode, its
  settings and `hands kit file` have never met outside tests.
- **No real `kit file` from a role.** U3's `kit file` tests file over a real
  daemon socket but from a test cwd, not from an architect directory a human
  built. Doctor's architect row has likewise only seen fixtures.

**3.1 The guard (U1, U3).** The three probes are proven blocked and the 10k
corpus is proven blocked, but neither enumerates the space: what is proven is
that the listed commands take only the listed options, not that no listed
option can reach a write in some spelling the corpus does not generate. No
real Claude Code session ran either hook, so the assumption that the string
Claude Code hands the hook is the string bash runs is still an assumption, and
the `Write|Edit|MultiEdit` payload is judged on `file_path` alone — a real
MultiEdit payload was never observed (anything unrecognised fails closed).
Role mode **widened** in this mission: `cat ls head tail wc grep jq pgrep
sleep date echo kill -0` now read in the driver role, where they were refused
before. That is §31's instruction ("Role mode is the same table"), it is the
one loosening in the mission, and it has no operational evidence behind it.

**3.2 The architect role cannot yet file a usable kit (H-030).** With the
words §31 gives it, the architect can write a zip under `HANDS_KITS` but
cannot make the zip's entries repository paths: `zip` has no chdir option,
`-j` flattens, `cd` is not in the table, and `kit check` does not catch it
because `kits/m16/DESIGN.md` *is* a syntactically valid repository path. So
the role as specified cannot produce the artifact its own CLAUDE.md rule 3
asks for. Everything in this mission is built to §31 as written; the memo
lists three candidate resolutions and none of them was this mission's to
choose. **Until one is chosen, an autonomous series cannot run.**

**3.3 Autonomy's blast radius is the playbook's approval.** The engine's
`decided_by: playbook` approval is new gate authority (§8 previously said
"Nothing else releases a `held` job"). It is narrow — one origin, one playbook
state, never while paused, with tests for each narrowing — but the standing
authority behind it is a human approving one playbook file. No test can prove
that is enough; H-029 states it so a reader meets it in the ledger.

**3.4 What the engine does not judge.** `gate_failures` and two of the three
`escalate_on` conditions (`blocker-unanswered`, `milestone-missing`) reach the
architect as **prompt data**; only `budget-exhausted` is enforced by the
engine. Nothing counts a roadmap gate failing twice, because nothing in hands
knows what a roadmap gate is. §31's words carry no more than this, and U5 did
not invent more.

**3.5 The asymmetry H-032 names.** `Api.send` refuses `--role driver` by name
and does not refuse `--role architect`, so a human typing `hands send --role
architect` at the laptop starts the role outside any consultation. The
orchestrator appended a correction to that memo: mission 16's `reply <secret>
<text>` is designed to be exactly that send, so closing the asymmetry is a
design choice, not a line of code, and mission 15 made neither choice.

**3.6 Notifications (U2).** The kit pair's ordering is proven at the hand-over
(the channel's injected sleep and the spawned publish), not on the wire; no
real ntfy delivery was observed, and clock skew is untested. The
one-notification daemon start **loses** the Approve/Deny buttons for re-minted
holds: after a restart a held job is decided by `hands approve|deny` or a
`cmd_topic` secret until it is held again. The nonces are still minted.
Doctor judges command-type hooks only; whether another hook shape Claude Code
honours could slip past is untested. `max_consults` is not restart-proof
against a deleted or rotated `pipeline.json` — U2 **disclosed** that in
`ConsultAnchor`'s docstring rather than closing it, as §31's words asked.

**3.7 Doc completeness.** The docs are pinned sentence by sentence against
code constants. That proves each pinned sentence is true; it does not prove
the prose is complete or that a human following it can set the role up.

## Review items

| Item | Unit | Commit | State |
|---|---|---|---|
| REVIEW-14 blocker 1 — an allowed first word takes unchecked options; the guard writes and runs a program | U1 | d32f409 | closed (the command table; the three probes exit 2 in both modes through the shipped file; §3.1) |
| REVIEW-14 blocker 2 — the kit pair is unspaced on the ordinary branch, and the test picks the other one | U2 | 6b27320 | closed (spacing on every branch; the test binds the no-KIT.md branch; §3.6) |
| REVIEW-14 should-fix 1 — daemon start publishes N+1 notifications in one second | U2 | 6b27320 | closed (one notification listing the re-minted holds; it loses the buttons, §3.6) |
| REVIEW-14 should-fix 2 — INTEGRATION states the limit pair as published, and nothing is published | U2 | 6b27320 | closed (documented as implemented, pinned by a test) |
| REVIEW-14 should-fix 3 — doctor judges only the first PreToolUse Bash hook | U2 | 6b27320 | closed (every Bash hook judged; the fail-closed spellings left as they are) |
| REVIEW-14 should-fix 4 — an empty project name is ignored, not refused | U2 | 6b27320 | closed (refused at every entry, exit 1) |
| REVIEW-14 should-fix 5 — the `max_consults` anchor is thinner than it reads | U2 | 6b27320 | closed as §31 words it (job id + daemon start read back); the two undisclosed cases are now disclosed, not closed (§3.6) |
| REVIEW-14 should-fix 6 — the bare-name rule's false positives are prose, not a pinned row | U2 | 6b27320 | closed (22 fixture rows, no rule change; the `hands who` case added) |
| REVIEW-14 should-fix 7 — `[series] kickoff` names a brief that does not exist and nothing flags it | U0 | 1a48e11 | closed (doctor warns; it warns on this repository's own playbook today, U7) |

## 4. Acceptance

- `./scripts/check` green on the pushed tip, three consecutive runs: green 3/3 on the U7
  tree at fd1a2dd (3126 passed; 176.42s, 181.19s, 180.09s).
  This commit adds meta files only.
- Every unit commit's body lists every file it touches — checked against `git
  show --stat` for all eight. **One exception, disclosed:** `adf3d7a` (U3)
  names its five product files and `meta/findings/FINDINGS.md` but not its
  four test files (`tests/test_bash_guard.py`, `tests/test_config.py`,
  `tests/test_kit.py`, `tests/test_runner.py`) by path; it describes what they
  test in prose. The other seven list every path. U0 is the `plan:` commit.
- `driver/hooks/bash_guard.py` contains no `ALLOWED_FIRST_WORDS`: `grep` on
  the file returns nothing, `tests/test_bash_guard.py` asserts both that the
  module has no such attribute and that the file's text does not carry it.
- The reviewer's three probes are in `tests/test_bash_guard.py`
  (`tests/test_bash_guard.py:1198-1200`), asserted blocked in both modes.
- `hands kit --help` lists `file` ("check a kit under $HANDS_KITS and file its
  held apply (§31)"); `hands doctor` on a config with `[roles.architect]`
  reports the role.
- This file exists with NOT PROVEN and the review-items table.

## 5. For the architect

1. **H-030 is the one that blocks the role, and it is yours to decide.** The
   architect cannot name a zip's entries as repository paths with the words
   §31 gives it. The memo lists three candidates; candidate 1 (`hands kit
   file <dir>`, since `kit._read_kit` and `check_kit` already accept a
   directory and only `apply_from_zip` is zip-only) needs no new guard word
   and is the cheapest. Until one is chosen, `autonomous = true` should not
   be set on any series.
2. **H-031** wants one DESIGN line: §6's `decided_by: cli|driver|phone` needs
   `|playbook`. Until then `tests/test_docs.py` asserts "§6's list plus
   `playbook`, and no more" instead of equality; the check still fails on a
   fifth value, which is what it was for.
3. **H-032** is a design choice, not a line of code: mission 16's `reply`
   *is* a `hands send --role architect`, so either the refusal is scoped to
   origins other than the phone's, or §31 says a laptop send is the human's
   own authority.
4. **H-027** stays open from mission 14 (DESIGN §12 rule 6 and §14's layout
   line, both of which only you may edit).
5. **Readings to confirm.** U1: role mode widened to the read-only rows, and
   `pwd` left the table by the closure rule (§31 lists it in neither set).
   U3: the architect's `hands` surface is `architect/settings.json`'s own
   allow list, so `tail` and `resume` are refused. U4: the engine-added
   kickoff rule is prepended, so a playbook's own `kit applied` rule does not
   fire; the kickoff job's origin is `playbook`. U5: `architect.*` is not an
   event a rule can match, the whole ROADMAP is carried in the prompt, and the
   budget is anchored per series by `[series] name`.
6. **BUILDER-16.** `PLAYBOOK.toml` names `meta/BUILDER-16-PROMPT.md`, which
   your next kit must ship. `hands doctor` now says so out loud — its `go` row
   warns today, which is the should-fix 7 machinery working on this
   repository's own playbook.
