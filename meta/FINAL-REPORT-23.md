# FINAL-REPORT-23 — review 22, the four findings, the hosted review read mechanically

VERDICT: mission 23 finished pr=4

Brief: meta/BUILDER-23-PROMPT.md. Design: DESIGN v3.22 §39 (with §24, §27,
§31, §35, §38). Review read: meta/reviews/REVIEW-22.md (`reviewed:
baa0b6e`, blockers 0, should-fix 12); docs/QODO-EXTRACTION.md. Shape: pull
request. The branch `mission-23` was created from `main` at 23eff6c (`plan:
mission 23 kit (DESIGN v3.22)`); every unit committed and pushed to it; this
unit opens the pull request `mission-23` → `main`, reads the hosted review
with `hands hosted-review` and fixes its findings in the same pull request.
Findings resolved: H-051, H-052 (U7), H-053, H-054, H-056 (U9), H-055 (U6),
H-057, H-058, H-059 (U2), H-060 (U3, U9); HF-002 in full (U7). Findings
filed and left open: none.

## 1. What changed (sha per unit)

- U0 b7b5c10 (`plan:`): meta/plan.md, meta/CHECKPOINT.md, meta/journal.md,
  meta/findings/FINDINGS.md (H-055..H-060 filed; H-051..H-054 set to
  "decided (DESIGN §39, mission 23 U<n>)"). Green 3/3, 4387 passed.
- U1 9c5d729 (`who:`) — the who watcher (should-fix 1, 2): every scan stores
  its fingerprint whenever the time-blanked picture equals the last
  published one; publish still needs both to differ. Files who.py,
  tests/test_who.py. Green 3/3, 4391.
- U2 bcc3d53 (`daemon:`) — orphans, refusals and ids (should-fix 3, 4;
  H-057, H-058, H-059): an orphaned phone `reply`/`answer` is published as
  its end; a builder `answer` orphaned by a stop is re-sent as `keep`
  (origin `playbook`); the start notification says "daemon stop" only when
  `orphan_reason` says so; `aux.orphaned` joins `EVENTS`, the stop records
  an aux job orphaned, and `aux.orphaned → resume` is in PLAYBOOK.toml and
  both templates (21 rules); a refusal of a command with the right secret is
  published titled `<command>` with the reason; `api.match_job_id` (O→0,
  l/I→1, case-insensitive, unique prefix ≥ 4, ambiguous refused with the
  candidates) in `approve`, `deny`, `cancel`; the hold notification prints
  the id on its own line. Files daemon.py, playbook.py, api.py, phone.py,
  notify.py, PLAYBOOK.toml, templates/PLAYBOOK-missions.toml,
  templates/PLAYBOOK-runs.toml, docs/PLAYBOOK.md (event row), tests. Green
  3/3, 4407.
- U3 e36d558 (`playbook:`) — the engine's small fixes (should-fix 5, 7;
  H-060): the architect consult rule on `builder.done` is refused at load
  unless its compiled regex matches `VERDICT: mission 1 blocked U2` and not
  `VERDICT: mission 1 finished`; the owner-file fallbacks list an untracked
  since-committed file and, for an unknown recorded sha, every owner file,
  each with a note; an `answer` and a cli `--context keep|clear` send to the
  builder are prefixed with the commit-the-journal sentence when `git status
  --porcelain -- meta/journal.md` shows it. Files playbook.py, api.py,
  tests. Green 3/3, 4424.
- U4 0c6d725 (`progress:`) — (should-fix 6): `progress` reads
  `meta/CHECKPOINT.md` at `git rev-parse --show-toplevel` of the builder's
  cwd (falls back to the cwd when git fails; design silent); README names
  the ten phone commands. Files api.py, phone.py (docstring), README.md,
  docs/INTEGRATION.md (the progress bullet), tests. Green 3/3, 4426.
- U5 59678ee (`hosted:`) — `hands hosted-review <pr> [--bot]`: new
  src/hands/hosted.py (added); fetches issue comments, reviews and review
  comments through `gh api`, every page, filtered to the bot; archives each
  body byte for byte and its JSON under `meta/reviews/hosted/PR-<n>/<k>/` at
  the repository root; prints the header categories as found, every
  numbered finding with its anchor, the summary comment's id and the
  verdict (from the Code Review comment only); diffs against `<k-1>` by
  comment id; "no bot comment yet" exits 3 and writes nothing. Files cli.py,
  hosted.py (added), tests/fake_gh.py, tests/fixtures/hosted/ (added),
  tests/test_hosted.py (added), tests/test_docs.py. Green 3/3, 4434.
- U6 dc9698e (`protocol:`) — (should-fix 8; H-055): both protocols' revert
  step `git rm -q -f`s a listed file absent at `<sha>` before the restore
  and requires `git status --short` empty after it; the hosted-review step
  runs the command as a fresh-context sub-agent, commits the archive,
  takes the verdict from the Code Review comment only, audits the builder's
  `## Hosted review` table, and treats "no bot comment yet" as the wait;
  the brief template's last unit opens the PR, waits up to ten minutes,
  runs the command, fixes, pushes and writes the disposition table;
  handbook §9. Files templates/REVIEW-PROTOCOL.md, meta/REVIEW-PROTOCOL.md,
  templates/BUILDER-N-PROMPT.md, docs/ARCHITECT-HANDBOOK.md, tests. Green
  3/3, 4465.
- U7 2b4df10 (`architect:`) — H-051, H-052 (should-fix 10; HF-002): the
  consult prompt names `docs_root()`'s handbook and templates paths; the
  guard lets the architect read under `HANDS_DOCS` and run `hands handbook`
  (the driver gets neither); architect/settings.json allows it;
  architect/CLAUDE.md rule 2 reads the named paths; `hands handbook` help
  names `$HANDS_DOCS/docs/…`; project.py unchanged (mission 22 U10 already
  wrote the role variant filled — now tested); FINDINGS H-051, H-052, HF-002
  resolved. Green 3/3, 4474.
- U8 a09b85f (`project:`) — (should-fix 9, 11): `git clone -q -- <url>`; a
  failed clone (or push-URL step) removes everything the command created,
  newest first, prints `removed:` and returns 1 before systemctl; anything
  that existed before is kept; architect/CLAUDE.md rules 8 and 13 agree on
  `VERDICT: escalate ruling: <what>` with a drafted owner file under
  `kits/<name>/meta/decisions/`. Files project.py, architect/CLAUDE.md,
  tests. Green 3/3, 4479.
- U9 515b736 (`docs:`) — (should-fix 12; H-053, H-054, H-056; H-060's human
  half): `.claude/settings.json`, INTEGRATION's copy line and self-test run
  `no_background.py` as `python3 -I`; INTEGRATION: a restart kills every
  running job and what resumes what, the kits' hook counts, the clean-review
  pause and `go`, the `[server]` fallback, the architect's `handbook` and
  `HANDS_DOCS`, lenient ids, refusals answered (two passages U2 made wrong
  rewritten); handbook: status prints every configured role, restart, ids,
  the ruling round's journal sentence; PLAYBOOK: `aux.orphaned → resume`.
  Files .claude/settings.json, docs/INTEGRATION.md,
  docs/ARCHITECT-HANDBOOK.md, docs/PLAYBOOK.md, tests. Green 3/3, 4493.
- U10 (`report:`, this commit): this report, plan, checkpoint, journal,
  FINDINGS statuses (H-053..H-060); then the pull request, the hosted
  review read with `hands hosted-review`, its fixes, and the `## Hosted
  review` table in a final `report:` commit.

## 2. What the tests prove

- who: a fingerprint-only change and a picture-only change each publish
  nothing (red under `fp != self.fp` and under `shown != self.shown`); the
  review's `[True, True, False, True]` reproduction with the real
  `Debounce` now gives `[True, True, False, False]`.
- A review job orphaned by a daemon stop is resumed at the next start with
  the rule's prompt in a fresh context; with `max_resumes` 0 it stops. A
  crash orphan is named as found. An orphaned `answer` is published and
  re-sent as `keep`; an orphaned `reply` is published.
- A refused `approve`, `deny`, `go` with the right secret is published under
  its command's name; a wrong or missing secret publishes nothing.
  `Omv9a9z9a-arir` resolves `0mv9a9z9a-arir`; a four-character prefix
  resolves; an ambiguous prefix is refused naming both candidates; `cancel`
  takes a lenient id; the hold notification has the id on its own line.
- Each shipped playbook carries exactly one `aux.orphaned → resume`; this
  tree's PLAYBOOK.toml loads with 21 rules (`load_playbook`).
- The consult-regex check: three patterns load, five are refused (including
  `blocked|finished` and `unblocked`). The two owner-file fallbacks list
  with notes. The journal sentence is present only when `meta/journal.md`
  is dirty, for `answer`, cli `keep` and `clear`; never on an aux send.
- `progress` from a cwd two levels below the root reads the root's
  checkpoint (a decoy under the cwd is ignored); README names the ten
  commands, pinned against the phone module's list.
- `hands hosted-review` on recorded pages (fake `gh`): byte-for-byte
  archive at the repository root from a subdirectory; categories (an unseen
  one printed), findings with anchors, summary id, verdict; the second fetch
  after an in-place edit prints `updated_at`, the changed lines, ids added
  and vanished, the resolved finding and "2 of 3 findings open"; every page
  read to the first empty page; no bot comment → exit 3, nothing written;
  `--bot`; a failing `gh` exits 1 and writes nothing.
- Protocols: the new sentences pinned in both files, no "stash"; a scratch
  repository whose commit adds, edits and deletes a file: the old restore
  fails, the new one leaves `git status --short` empty. A kit from the
  templates passes `kit check` 6/6.
- Guard: under `HANDS_ROLE=architect` `cat <HANDS_DOCS>/docs/x.md` and
  `hands handbook [--templates]` are allowed; reads outside the roots,
  `HANDS_DOCS/../x`, a look-alike prefix, and any read with `HANDS_DOCS`
  unset are refused; the driver gets neither. The consult prompt carries
  both paths.
- `project add`: a failed clone (missing URL; a fake `git` failing the
  architect's clone) leaves HOME as it was, enables nothing, and a re-run
  succeeds; pre-existing files survive byte for byte; `--` precedes the URL.
- Docs: every hook command in shipped docs, READMEs and settings carries
  `-I`; the settings' `no_background` command ignores a planted `json.py`
  and the same command without `-I` imports it; the INTEGRATION, handbook
  and PLAYBOOK sentences are pinned and checked against the code.

## 3. NOT PROVEN

- No real phone has used the lenient ids or seen a published refusal; no
  real ntfy server was involved.
- No real daemon restart has resumed a review: the installed handsd still
  runs the old code (`hands --project hands pipeline` shows 20 rules until
  it is reinstalled); the load of the 21-rule playbook is shown by
  `load_playbook` on this tree.
- `hands hosted-review` ran against recorded pages in the tests, and in
  this unit against the real PR (§Hosted review); its reading of how the bot
  marks a resolved finding comes from docs/QODO-EXTRACTION.md, not from a
  recorded edit (until this PR's second fetch).
- An `answer` or `reply` orphaned by a crash (not a stop) is not published.
- Storing the fingerprint on a requested or in-floor scan (§39 says
  "whenever"; taken literally).
- `progress` with a hanging git, a submodule or linked-worktree cwd.
- The journal check from a builder cwd below the repository root; on a held
  cli send.
- `project add` killed mid-way, a failed removal, a systemctl failure after
  both clones.
- A real architect session reading the handbook with Read; a real Claude
  Code hook run of `python3 -I`.
- That reviewers and builders follow the new protocol and brief text.

## Deviations

- U6: the protocols spell the step `git rm -q -f`, not §39's `git rm -q`:
  the revert has already staged the file at `<sha>~1`, and plain `git rm
  -q` refuses it. The scratch-repo test runs the `-f` form.
- U2: `answer` and `reply` carry no job id (`answer <secret> <text>`), so
  lenient matching applies to `approve`, `deny` and `cancel`.
- U2 touched docs/PLAYBOOK.md and tests/test_notify_project.py; U4 touched
  docs/INTEGRATION.md; U9 rewrote two INTEGRATION passages U2 made wrong —
  each named in its commit body.

## Review items

| REVIEW-22 item | What | Closed by |
|---|---|---|
| Should-fix 1 | the blanked-picture comparison is unpinned | U1 9c5d729 |
| Should-fix 2 | a stale fingerprint lets the human's session publish | U1 9c5d729 |
| Should-fix 3 | an orphaned `reply`/`answer` is never published; answer re-sent as clear | U2 bcc3d53 |
| Should-fix 4 | the start notification says "daemon stop" for every orphan | U2 bcc3d53 |
| Should-fix 5 | the blocked-regex load check is a substring test on the pattern (§39 records the refusal) | U3 e36d558 |
| Should-fix 6 | `progress` reads the cwd's checkpoint, not the root's; README omits `progress` and `answer` | U4 0c6d725 |
| Should-fix 7 | the two owner-file fallbacks are not inclusive | U3 e36d558 |
| Should-fix 8 | the revert step fails for a deleted file | U6 dc9698e (H-055) |
| Should-fix 9 | rule 13 makes a design decision; rule 8 disagrees | U8 a09b85f |
| Should-fix 10 | HF-002 recorded resolved while H-051 is open | U7 2b4df10 (H-051, HF-002) |
| Should-fix 11 | `project add` passes the URL without `--`; a failed clone leaves debris | U8 a09b85f |
| Should-fix 12 | `no_background.py` without `-I` | U9 515b736 (H-056) |

## Findings

| Finding | Status | Unit |
|---|---|---|
| H-051 | resolved | U7 2b4df10 |
| H-052 | resolved (the reading is the design; tested) | U7 2b4df10 |
| H-053 | resolved-by-doc | U9 515b736 |
| H-054 | resolved-by-doc | U9 515b736 |
| H-055 | resolved-by-doc | U6 dc9698e |
| H-056 | resolved | U9 515b736 |
| H-057 | resolved-by-code | U2 bcc3d53 (docs U9) |
| H-058 | resolved-by-code | U2 bcc3d53 |
| H-059 | resolved-by-code | U2 bcc3d53 |
| H-060 | resolved-by-code | U3 e36d558 (handbook U9) |
| HF-002 | resolved in full | U7 2b4df10 |
