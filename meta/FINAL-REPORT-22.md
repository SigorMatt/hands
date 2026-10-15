# FINAL-REPORT-22 — the operational findings and the onboarding half

VERDICT: mission 22 finished pr=3

Brief: meta/BUILDER-22-PROMPT.md. Design: DESIGN v3.21 §38 (with §26, §31,
§33, §36, §37). Review read: meta/reviews/REVIEW-21.md (`reviewed:
2b5a7fc`, blockers 0, should-fix 3). Shape: pull request. The branch
`mission-22` was created from `main` at 7ddc0e8 (`plan: mission 22 kit
(DESIGN v3.21)`); every unit committed and pushed to it; this commit opens
the pull request `mission-22` → `main`.
Findings resolved: H-037, H-046, H-047, H-048 (by code), H-049, H-050 (by
doc), HF-002, HF-004, HF-005 (noted in FINDINGS). Findings filed and left
open for the architect: H-051, H-052, H-053, H-054.

## 1. What changed (sha per unit)

- U0 759f605 (`plan:`): meta/plan.md, meta/CHECKPOINT.md, meta/journal.md,
  meta/findings/FINDINGS.md (H-049, H-050 filed; H-037, H-046..H-048 in
  progress). Green 3/3, 4261 passed.
- U1 3feb89b (`notify:`) — the buttons carry the token (H-037):
  `notify.actions_header` adds `headers.Authorization=Bearer <token>` to
  every `http` action in the short form when `[notify] ntfy_token` is set,
  at request build (the token is never spooled); config refuses a token
  containing `,` or `;`; doctor's `phone` row says "buttons: bearer on" or
  "buttons: no token; a token-protected server refuses them". Files
  notify.py, config.py (outside the brief's list, named in the body),
  doctor.py, tests/test_ntfy_token.py, FINDINGS. phone.py unchanged. Green
  3/3, 4269.
- U2 5f3b7ad (`who, doctor:`) — `handswho` on change only (H-046):
  `blank_times` blanks every relative-time rendering; a publish needs the
  state fingerprint and the blanked picture both to differ, and never
  happens twice within `[notify] who_min_interval_s` (default 60) unless a
  request on `who_cmd_topic` asks; a deferred change goes out at the first
  scan after the floor; a refused publish also starts the floor; the
  published picture keeps the times. Doctor's new `broker` row WARNS on an
  unset or public `ntfy_url`, `ok` on private and tailnet hosts. Files
  who.py, config.py, doctor.py, docs/INTEGRATION.md, tests (test_who,
  test_doctor, test_config), FINDINGS. Green 3/3, 4300.
- U3 96d3fbb (`daemon:`) — a daemon stop does not strand the builder
  (H-047): a job the daemon's stop ends is `orphaned` with `orphan_reason:
  daemon_stop` on the record (`reason` on the inbox event; the design
  names no record key, §6 has `failure_reason`); `killed` stays the record
  of a cancel; at the next start each orphan is fed to the engine as
  `<role>.orphaned` once (an `orphan_fed` flag), after queued jobs are
  re-admitted; the start notification names the resumed job. Files
  daemon.py, runner.py, spool.py, tests/test_daemon_stop.py (added),
  tests/test_spool.py, FINDINGS. playbook.py unchanged (its `resume` and
  the §28/§31 stops already did the work). Green 3/3, 4308.
- U4 69364de (`playbook:`) — a blocked mission consults the role (H-048):
  `CONSULT_EVENTS[ARCHITECT]` gains `builder.done`; the consult prompt for a
  builder's end carries the verdict line and the full reply between the
  REPLY markers under "The builder's blocked verdict and its reply", no
  REVIEW markers; an architect consult on `builder.done` without a
  `blocked` verdict regex is refused at load; the missions template carries
  the rule (role mode, commented) and the stop (phone mode). Files
  playbook.py, templates/PLAYBOOK-missions.toml, docs/PLAYBOOK.md, tests,
  FINDINGS. kit.py and this repository's PLAYBOOK.toml unchanged. Green
  3/3, 4317.
- U5 f16c331 (`phone:`) — `progress <secret>`, the tenth command:
  `Api.progress_report` (outside `Api.COMMANDS`) answers titled `progress`
  with the builder line (running id and age, or the last ended job with
  its state and verdict), `branch:` and `log --oneline -3` of the builder
  cwd (one plain line when that is not a repository), and the first
  checkpoint line naming a unit in progress or "no checkpoint". Files
  phone.py, api.py, docs/INTEGRATION.md, docs/PLAYBOOK.md, tests. Green 3/3,
  4322.
- U6 22a2ef5 (`playbook:`) — review 20's two notes on U6: the engine
  records HEAD of the builder cwd as `head` in `consult.sent`;
  `human_decisions` lists owner files from `git log <sha>..HEAD` (no
  `--since`), matched against `git ls-files --full-name` run in the cwd.
  An owner file no longer tracked at HEAD is now omitted. Files
  playbook.py, tests/test_playbook.py. Green 3/3, 4324.
- U7 cfb7e71 (`protocol:`) — the protocols (H-049, H-050): per file,
  `git checkout <sha>~1 -- <file>` when it exists at the parent (`git
  cat-file -e`), else `rm`; red; `git checkout <sha> -- <files>`; added
  files named as added; Notes carry one line per sub-agent with start and
  end times and the rule's reason, a review without them is a should-fix
  for the next; the `plan: decisions <date> (owner)` exception; a
  human-supplied `fixtures:` commit checked by `git show --stat` alone.
  Files templates/REVIEW-PROTOCOL.md, meta/REVIEW-PROTOCOL.md,
  tests/test_kit.py, FINDINGS. Green 3/3.
- U8 7df5bce (`templates:`) — templates/DECISIONS-owner.md (added); the
  brief template's §R `keep`-after-question rule and the human-supplied
  unit shape; the Purpose block (FOR / NOT / DECIDES) at the top of
  docs/ARCHITECT-INSTRUCTION.md and architect/CLAUDE.md, each with the
  paragraph on answering rulings with the owner file. Files those four plus
  templates/BUILDER-N-PROMPT.md and tests/test_kit.py; kit.py unchanged.
  Green 3/3, 4338.
- U9 b6e2511 (`docs:`) — the installed handbook and templates (HF-002,
  HF-004, HF-005): the wheel force-includes `docs/` and `templates/` under
  `hands/shipped/`; `hands handbook [--templates]`; the runner exports
  `HANDS_DOCS` to every role job; both instructions read from it; handbook
  §6 and §12. Files pyproject.toml, config.py, cli.py, runner.py,
  architect/CLAUDE.md, docs/ARCHITECT-INSTRUCTION.md,
  docs/ARCHITECT-HANDBOOK.md, tests/test_docs.py, tests/test_handbook.py
  (added), FINDINGS (HF-002/004/005 resolved; H-051 filed). Green 3/3,
  4349.
- U10 f1936b1 (`project:`) — `hands project add <name> --repo <url>
  [--dry-run]`: src/hands/project.py and templates/config.toml (both
  added; no installed config template existed); config and
  `<name>.cmd_secret` mode 600; both role directories with the shipped
  settings, guard and a `no_push` clone; the role's CLAUDE.md from
  architect/CLAUDE.md with the Parameters filled (H-052); `systemctl --user
  daemon-reload` and `enable handsd@<name>`; doctor run, its status
  printed and not propagated; the filled Project instruction and "What are
  your Parameters?" printed last. Files also cli.py, pyproject.toml,
  docs/INTEGRATION.md, tests/test_docs.py, tests/test_project_add.py,
  FINDINGS. Green 3/3, 4359.
- U11 9fae4ee (`docs:`) — INTEGRATION's self-hosted corrections (image
  `binwiederhier/ntfy`, `base-url` first, the who topic grants, the role-mode
  default, no certificate domain and WebSockets, pre-`[notify]` configs,
  what has run on a real server, the buttons' bearer), `python3 -I`
  everywhere (review 21 should-fix 3); handbook §13–§18; PLAYBOOK.md's
  `auto-runs`. Files docs/INTEGRATION.md, docs/ARCHITECT-HANDBOOK.md,
  docs/PLAYBOOK.md, README.md, architect/README.md, driver/README.md (the
  last two outside the brief's list: an existing test ties INTEGRATION's
  setup lines to them), tests/test_docs.py, tests/test_handbook.py,
  FINDINGS (H-053 filed). Green 3/3, 4387.
- U12 (this commit, `report:`): this file, meta/plan.md,
  meta/CHECKPOINT.md, meta/journal.md, meta/findings/FINDINGS.md (H-054
  filed).

## 2. What the tests prove

- Both actions of a held job's notification, published through the real
  `http_post` to a stub that refuses unauthenticated requests, carry the
  bearer when a token is set, and neither carries a `headers.` field
  without one; a token with `,` or `;` is refused at load (U1).
- Two who scans that differ only in relative-time text publish once; a
  real change publishes; two real changes 10 s apart publish once, the
  second at the first scan after the 60 s floor (injected clock); a request
  publishes inside the floor; doctor warns for `ntfy.sh` and unset, not for
  `http://100.64.0.1:2586` or `https://x.tailnet.ts.net` (U2).
- A daemon stopped with a running fake builder leaves it
  `orphaned/daemon_stop`; the next start, with a `builder.orphaned →
  resume` playbook, enqueues one builder job with the kickoff prompt and
  context clear, names it in the start notification, and a later start does
  not feed it again; an idle stop resumes nothing; `max_resumes` reached
  stops with the reason; a cancel still ends `killed` (U3).
- A role-mode playbook consults the architect on a blocked verdict and the
  prompt carries the reply; one review and one blocked consult use a
  budget of 2; the phone-mode template stops; a kit built from the
  templates passes `kit check` 6 of 6 (U4, U8).
- `progress` answers for a running job and for an idle builder with a local
  repository; a wrong secret is refused (U5).
- An owner file committed after a consultation with a 2001 committer date
  is listed, one before it dated 2099 is not; a cwd two levels below the
  root lists its owner files (U6).
- Both protocols carry the four §38 sentences and neither says "stash"
  (U7).
- `hands handbook` resolves into the installed package (an unpacked wheel);
  `HANDS_DOCS` is in builder, aux, driver and architect job environments;
  handbook §6's bullets equal `playbook.SERIES_KEYS` with the loader's
  defaults (U9).
- `hands project add --dry-run` against a temp HOME lists every path and
  writes nothing; a real run against a temp HOME and a local bare
  repository creates the files with mode 600 and the `no_push` push URL,
  calls the fake `systemctl` with `daemon-reload` and `enable
  handsd@demo`; each refusal leaves the tree unchanged (U10).
- The docs name `binwiederhier/ntfy`, spell the hook `python3 -I` and keep
  no `python3 <` hook line (U11).

Review 21 should-fix 1, corrected here: FINAL-REPORT-21 §2 said "The
daemon test is red without either half of the change." That was wrong.
The spool half of mission 21 U1 (44f7494) is proven only by `test_spool`'s
stale-object test; the daemon test is red without the runner half and
passes with only `src/hands/spool.py` reverted. No daemon-level test needs
the on-disk judgement in `Spool.transition`, and this report claims none.

## 3. NOT PROVEN

- No real phone has pressed an authenticated button: the ntfy app sending
  an action's `headers` to a token-protected server is untested (U1).
- No real daemon restart has resumed a builder; a driver or architect
  orphaned by a stop, and a stop that catches a job before it spawned, are
  untested (U3).
- `hands project add` has not run against a real laptop, real systemd, a
  remote URL or a started daemon; it does not create the builder's own
  clone (U10).
- A real architect session cannot yet learn `$HANDS_DOCS`' value under the
  guard (H-051, open): `echo $HANDS_DOCS`, `hands handbook` and `cat` on
  the handbook are each refused for the architect role. HF-002 is resolved
  as far as the files ship and the variable is set; the role reading them
  is not proven.
- Installing the wheel with pip or `uv tool install` (the tests unpack it).
- `handswho` against a real broker or a real 429; time formats other than
  `age()`'s and the header clock; short MagicDNS names are treated as
  public and warned on; a fingerprint change that leaves the blanked
  picture equal keeps the stored fingerprint stale (U2).
- A real architect's answer to a blocked-verdict prompt; the daemon end to
  end for U4 (the engine ran against a recorder).
- `progress` with git missing or timing out, the 200-character cut, the
  hour form of the age (U5).
- A recorded consult sha unknown to the repository or rewritten history;
  driver consultations record no sha (U6).
- A reviewer following the protocol's new steps (U7); an architect or
  builder following the template words (U8).
- None of INTEGRATION's ntfy, docker or Tailscale commands, nor the
  WebSockets remark, was run against a real install; the "what has run on
  a real server" list is taken from DESIGN §37/§38; the `jobs` newest-first
  test reads the docstring, not the ordering (U11).
- U7's gate count was not reported by its sub-agent; the three runs were
  green.

## Review items

| REVIEW-21 item | What | Closed by |
|---|---|---|
| Should-fix 1 | U1's body and FINAL-REPORT-21 §2 overstate the daemon test | this report, §2 (the spool half is proven by `test_spool`'s stale-object test only) |
| Should-fix 2 | the protocol's revert step fails for a file the commit adds | U7 cfb7e71 (H-049) |
| Should-fix 3 | docs/INTEGRATION.md spells the hook `python3 <path>` | U11 9fae4ee |

## Findings

Resolved: H-037 (U1), H-046 (U2), H-047 (U3), H-048 (U4) by code; H-049,
H-050 (U7) by doc; HF-002, HF-004, HF-005 (U9) noted in FINDINGS.

Filed, open, for the architect:
- H-051 — the architect role cannot learn the value of `HANDS_DOCS` (U9).
- H-052 — `project add` writes the role's CLAUDE.md from
  architect/CLAUDE.md, not docs/ARCHITECT-INSTRUCTION.md as §38 says
  literally; U10's reading, for a ruling (U10).
- H-053 — §38 says `status` hides the architect row; the code shows it
  (U11).
- H-054 — §38 says a `[server] ntfy_topic` config refuses to load; the
  loader still reads it and refuses only a key set in both tables (U12,
  from U11's report).
