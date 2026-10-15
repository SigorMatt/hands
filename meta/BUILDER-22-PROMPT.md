# BUILDER-22-PROMPT — hands mission 22: the operational findings and the onboarding half

Kickoff line (the only way this mission is started or resumed):

    Read the builder prompt with the highest mission number in the meta directory and execute the mission below its divider.

You are the builder for the `hands` repository. Read `DESIGN.md` (v3.21; §38
is this mission, with §26, §31, §33, §36, §37), `CLAUDE.md`,
`meta/CHECKPOINT.md` (a unit in progress means §R first), and
`meta/reviews/REVIEW-21.md` in full.

---

## Mission

Build DESIGN §38: the phone's buttons carrying the token (H-037), the who
daemon publishing on change only with doctor's public-broker warning
(H-046), a daemon stop that no longer strands the builder (H-047), a
blocked mission consulting the architect role (H-048), the `progress`
command, the protocol's revert step for added files and the reviewer's
schedule (H-049, H-050), review 20's two notes on U6, the owner-decisions
template and the brief template's recovery and human-supplied shapes,
onboarding (`hands handbook`, `HANDS_DOCS`, `hands project add`, the Purpose
block), and the handbook and INTEGRATION corrections. Close review 21's
three should-fix items. It does NOT touch the guard's language, the review
merge step, or other agent backends. Finish with a report whose first line
the playbook can match.

## Branch (DESIGN §35)

Pull request. This mission runs on the branch `mission-22`. U0 creates it
from `main` (`git checkout main && git pull --ff-only && git checkout -b
mission-22`). Every unit commit goes to that branch and is pushed at once
(`git push -u origin mission-22` the first time). The last unit opens the
pull request — `gh pr create --base main --head mission-22 --title "mission
22: the operational findings and the onboarding half" --body-file
meta/FINAL-REPORT-22.md` — and the final reply's verdict carries its
number. Then return the working tree to `main` (`git checkout main && git
pull --ff-only`): the next kit apply and the next kickoff run in this tree,
on `main`.

## Execution model (binding)

- You are a thin orchestrator. You plan units, write the checkpoint,
  dispatch ONE sub-agent per unit (Task tool, foreground only), verify the
  unit cheaply, record one line, move on. You run nothing longer than `git
  status`, `git log --oneline -5`, and `./scripts/check` yourself.
- Before each unit: write `meta/CHECKPOINT.md` (unit id, intent, what
  "done" means, standing constraints). After each unit: update it and
  append one line to `meta/journal.md`.
- Every unit ends with a commit AND a push, to `mission-22`. A unit commit
  carries only its own files and its body lists every one; never `git add
  -A`. The U0 commit uses the `plan:` prefix. Drafts of the final report
  live under `meta/drafts/` (git-ignored) until the last unit.
- Retry a failed unit once with the sub-agent's report attached; after two
  failures mark it `blocked` in `meta/plan.md` and continue with units that
  do not depend on it.
- Never edit product code yourself. Never edit `DESIGN.md` (file a finding
  instead).
- `./scripts/check` three times before every commit, each run its own
  foreground call with an explicit timeout of 20 minutes.
- Your final reply begins with exactly one of: `VERDICT: mission 22
  finished pr=<number>` | `VERDICT: mission 22 blocked <unit>` | `VERDICT:
  question <one line>`.

## Sub-agent brief (give this to every unit sub-agent, verbatim, plus the unit)

    You are implementing one unit of hands. Read, in this order: CLAUDE.md,
    DESIGN.md sections named by the unit, meta/CHECKPOINT.md, the finding or
    review item(s) named by the unit, then only the files the unit touches.
    Rules: the design is the spec — where it is silent, choose the simplest
    thing and say so in the commit body; write the failing test before the
    code and confirm it fails; ./scripts/check green three times before you
    commit, each run a foreground call with a 20-minute timeout; one
    commit, `<area>: <one line>` + a body naming the unit, the DESIGN
    sections and the item, listing every file, and stating only what the
    tests prove — never a totality claim unless a test enumerates the whole
    space; a commit that changes only tests names in its body each wrong
    change that would make them red; a commit that adds a non-test file
    names it as added, so the reviewer removes it rather than checking it
    out; never `git add -A`; push to the branch `mission-22`; never edit
    meta/plan.md, meta/CHECKPOINT.md, or DESIGN.md; if the unit needs a
    design change, stop and write a memo to meta/findings/FINDINGS.md
    instead of improvising; dispatch nothing in the background; never
    require a real `claude`, `gh`, `systemctl`, `ntfy` server or `git`
    remote in tests (fakes on PATH, a local HTTP stub and local bare
    repositories, as tests/fake_claude.py is); report in ≤12 lines: sha,
    files, tests added, what is NOT proven.

## §R Recovery brief

If `meta/CHECKPOINT.md` names a unit in progress and the working tree is
dirty: finish that unit under the sub-agent rules if it can pass
`./scripts/check`; otherwise `git stash push -m "wip <unit> <date>"`,
record in the checkpoint where it stopped and that a stash exists, and
leave the tree clean. Then continue from that unit. Push before taking any
new unit. If the tree is on `main` and `origin/mission-22` exists, `git
checkout mission-22 && git pull --ff-only` first. A `keep` send that
arrives after you replied `VERDICT: question` is the answer: carry it out,
continue the mission from the checkpoint, and end that reply with one of
the mission's `VERDICT:` lines, always, even when the answer came with a
file to commit first.

## Units, in order

**U0 Plan, branch and findings (`plan:` commit).** `meta/plan.md`,
`meta/CHECKPOINT.md`; the branch `mission-22` created and pushed. File in
`meta/findings/FINDINGS.md`: H-049 the protocol's revert step fails for a
file the commit adds (review 21 should-fix 2); H-050 review 21 ran its
sub-agents concurrently against the protocol's one-at-a-time rule (HF-008).
Set H-037, H-046, H-047, H-048 to "in progress (mission 22, U<n>)" with the
unit that resolves each. Gate: the entries exist; `git branch -r` shows
`origin/mission-22`.

**U1 The buttons carry the token (§38; H-037).** `src/hands/notify.py`,
`src/hands/phone.py`, `src/hands/doctor.py`, tests. Every `http` action
hands publishes carries `headers.Authorization=Bearer <token>` in the short
action form when `[notify] ntfy_token` is set, and nothing when it is not;
doctor's `phone` row says "buttons: bearer on" or "buttons: no token; a
token-protected server refuses them". Tests: the `Actions` header of a held
job's notification carries the bearer on both actions with a token and on
neither without; a token containing no comma or semicolon is required at
config load (the short form cannot quote). Gate: the tests; `./scripts/check`
green. Set H-037 resolved-by-code.

**U2 `handswho` on change only; doctor's broker warning (§38; H-046).**
`src/hands/who.py`, `src/hands/config.py`, `src/hands/doctor.py`,
`docs/INTEGRATION.md` (the `[notify] who_min_interval_s` key), tests. The
watcher blanks every relative-time rendering before comparing pictures,
publishes only on a difference, never twice within `who_min_interval_s`
(default 60) unless requested on `who_cmd_topic`, and the published picture
keeps the times. Doctor WARNS on a public `ntfy_url` (unset, or a host that
is neither a private address nor a tailnet name) naming the daily cap and
the self-hosted section; a private or tailnet host gets no warning. Tests:
two scans differing only in the relative-time text publish once; a real
change publishes; two real changes 10 s apart publish once with the second
deferred; a request publishes at once; doctor's warning for `ntfy.sh`, none
for `http://100.64.0.1:2586` and `https://x.tailnet.ts.net`. Gate: the
tests; `./scripts/check` green. Set H-046 resolved-by-code.

**U3 A daemon stop does not strand the builder (§38; H-047; §2, §6, §28,
§31).** `src/hands/daemon.py`, `src/hands/runner.py`, `src/hands/spool.py`,
`src/hands/playbook.py`, tests. A job the daemon's own stop ends is
recorded `orphaned` with `reason: daemon_stop` after the process is
signalled as §2 requires; `killed` is the record of a cancel only; at the
next start every orphaned job (reconciled or recorded) is fed to the engine
as `<role>.orphaned` once the workers are up, so `builder.orphaned →
resume` re-sends the kickoff from a fresh context, bounded by
`max_resumes`; an orphaned consultation stops as §28 and §31 say; the start
notification names the resumed job. Tests: a daemon stopped with a running
fake builder leaves `orphaned/daemon_stop` and the next start, with a
playbook whose `builder.orphaned` rule is `resume`, enqueues one builder job
with the kickoff prompt and context clear; a stop with the builder idle
resumes nothing; `max_resumes` reached stops with the reason; a cancel
still ends `killed`. Gate: the tests; `./scripts/check` green. Set H-047
resolved-by-code.

**U4 A blocked mission consults the role (§38; H-048; §31).**
`src/hands/playbook.py`, `src/hands/kit.py`,
`templates/PLAYBOOK-missions.toml`, `docs/PLAYBOOK.md`, tests.
`CONSULT_EVENTS[ARCHITECT]` gains `builder.done`; the consult prompt for a
builder's end carries the verdict line and the full reply between markers
headed "The builder's blocked verdict and its reply" in place of the review
markers, the rest unchanged; `kit check` accepts an architect consult rule
on a `builder.done` rule whose verdict regex names `blocked`; the missions
template carries the rule in its role-mode variant with a comment and the
stop in phone mode; this repository's `PLAYBOOK.toml` is unchanged. Tests:
a role-mode playbook with the rule consults the architect on a blocked
verdict and the prompt carries the reply; the budget counts it; a phone-mode
playbook stops; `kit check` on a kit built from the template passes 6 of 6.
Gate: the tests; `./scripts/check` green. Set H-048 resolved-by-code.

**U5 `progress <secret>` (§38; §26).** `src/hands/phone.py`,
`src/hands/api.py`, `docs/INTEGRATION.md`, `docs/PLAYBOOK.md`, tests. The
tenth command, secret-only, publishes titled `progress`: the builder's
current job id and age or the last ended job and its verdict; the working
tree's branch and `git log --oneline -3` of the builder's cwd; the first
line of `meta/CHECKPOINT.md` naming a unit in progress, or "no checkpoint";
read-only, starts no job. Tests: the reply for a running job and for an
idle builder with a local repository; a wrong secret is refused as the
other commands are. Gate: the tests; `./scripts/check` green.

**U6 Review 20's two notes on U6 (§38).** `src/hands/playbook.py`, tests.
"Since the last consultation" uses the sha the last consultation recorded
(`git log <sha>..HEAD`), never `--since`; the decisions-path comparison
uses `git ls-files --full-name` paths, so a builder cwd below the
repository root lists its owner files. Tests: a decisions file committed
with an old committer date is listed; a cwd two levels below the root
lists the same files. Gate: the tests; `./scripts/check` green.

**U7 The protocols (§38; H-049, H-050; review 21 should-fix 2).**
`templates/REVIEW-PROTOCOL.md`, `meta/REVIEW-PROTOCOL.md`, tests. The
revert step: for each non-test file the body lists, `git checkout <sha>~1
-- <file>` when it exists at the parent, else `rm` it; new tests red; then
`git checkout <sha> -- <files>`; a commit body names added files as added.
The Notes section requires one line per sub-agent with start and end times
and states the one-at-a-time rule's reason; a review whose Notes lack the
schedule is a should-fix for the next review. The one-commit exception for
`plan: decisions <date> (owner)`: read for what it says, not reviewed as a
unit. A human-supplied commit (`fixtures:` from a "human-supplied unit") is
checked by `git show --stat` alone. The two files differ only in the
project's names. Tests: the sentence-pinning test covers the four new
sentences. Gate: the test; `./scripts/check` green; H-049 and H-050
resolved-by-doc.

**U8 The templates (§38).** `templates/DECISIONS-owner.md` (new),
`templates/BUILDER-N-PROMPT.md`, `docs/ARCHITECT-INSTRUCTION.md`,
`architect/CLAUDE.md`, `src/hands/kit.py`, tests. The owner file template
as §38 describes (O-n, precedence header, "Findings closed:", "For the
builder" last); the brief template's §R gains the `keep`-after-question
rule and its Units section gains the human-supplied unit shape (files,
paths, commit message, `~/Downloads/<name>/`, copied and committed by path
without opening); both instruction templates gain the Purpose block (three
lines, kept verbatim at the top) and the paragraph on answering rulings
with the owner file; `kit check` tolerates the new template text (a kit
built from the templates with placeholders filled passes 6 of 6). Tests:
the template files exist with the named sections; the kit-check test.
Gate: the tests; `./scripts/check` green.

**U9 The installed handbook and templates (§38; HF-002, HF-004, HF-005).**
`pyproject.toml` (package data), `src/hands/cli.py`, `src/hands/runner.py`,
`src/hands/config.py`, `architect/CLAUDE.md`, `docs/ARCHITECT-INSTRUCTION.md`,
`docs/ARCHITECT-HANDBOOK.md` §6 and §12, tests. `hands handbook` prints the
installed handbook's path and `--templates` the templates directory; the
runner exports `HANDS_DOCS` to every role job; the architect instruction
reads the handbook and templates from `$HANDS_DOCS`; the handbook's §6
lists every `[series]` key with its default from `playbook.py` (HF-004) and
§12 names the laptop check of a plan kit and the first plan kit's silent
apply (HF-005). Tests: `hands handbook` resolves to a file inside the
installed package; `HANDS_DOCS` is in a role job's environment; a test
compares §6's key list with `playbook.py`'s `[series]` keys. Gate: the
tests; `./scripts/check` green; HF-002, HF-004, HF-005 noted resolved in
FINDINGS.

**U10 `hands project add` (§38).** `src/hands/cli.py`, a new
`src/hands/project.py`, `docs/INTEGRATION.md`, tests. `hands project add
<name> --repo <url> [--dry-run]`: config from the installed template with
four generated topics carrying the name and a secret in
`~/.hands/<name>.cmd_secret` (mode 600); `~/hands-driver/<name>/` and
`~/hands-architect/<name>/` with the shipped settings and guard and a
fetch-only clone whose push URL is `no_push`; the architect's `CLAUDE.md`
from `docs/ARCHITECT-INSTRUCTION.md` with the Parameters filled; `handsd@
<name>` enabled through `systemctl --user` (a fake on PATH in tests);
doctor run; the filled Project instruction and the verification question
printed last. Refuses an existing project or a non-empty directory;
`--dry-run` prints every path and writes nothing. Tests: a dry run against
a temp HOME lists the paths; a real run against a temp HOME with a local
bare repository creates them with the right modes and push URL; the
refusals. Gate: the tests; `./scripts/check` green.

**U11 Docs (§38).** `docs/INTEGRATION.md`, `docs/ARCHITECT-HANDBOOK.md`,
`docs/PLAYBOOK.md`, `README.md`, tests. INTEGRATION: every correction §38
lists for the self-hosted section (image, no certificate domain, `base-url`
first, the `[server] ntfy_topic` migration, the access rule and the who
topics, WebSockets, `python3 -I` everywhere, the self-hosted server as the
default for role mode, the proven list, the buttons after U1). Handbook:
the onboarding shape, the ruling round, the separation rule, re-firing via
the aux role, human-supplied content, `hands send`'s plain argument,
`status`/`jobs`/`auto-runs` reading, the `progress` command. PLAYBOOK.md:
the blocked-consult rule and `progress`. Tests: the docs tests pin the
image name, the `-I` spelling (no `python3 <` hook text remains), and the
new section headings. Gate: the tests; `./scripts/check` green; review 21
should-fix 3 resolved.

**U12 Final report and the pull request.** `meta/FINAL-REPORT-22.md`
(drafted under `meta/drafts/`, moved in by this commit): what changed (sha
per unit), what tests prove, NOT PROVEN (mandatory; at least: no real phone
has pressed an authenticated button, no real daemon restart has resumed a
builder, `hands project add` has not run against a real laptop), the `##
Review items` table for REVIEW-21 should-fix 1–3 (should-fix 1: the
sentence corrected here — the spool half is proven by `test_spool`'s
stale-object test only), the findings resolved (H-037, H-046..H-050,
HF-002, HF-004, HF-005). Then open the pull request as the Branch section
says, return the tree to `main`, and reply with the verdict line carrying
the PR number.

## Acceptance

- `./scripts/check` green on the pushed tip of `mission-22`, three
  consecutive runs.
- Every unit commit's body lists every file it touches; U0 is `plan:`.
- H-049 and H-050 filed; H-037, H-046, H-047, H-048, H-049, H-050, HF-002,
  HF-004, HF-005 resolved.
- A test shows both actions of a held job carry the bearer when a token is
  set.
- A test shows a daemon stop followed by a start re-sends the kickoff.
- A test shows a role-mode playbook consults the architect on a blocked
  verdict.
- The `progress` reply and `hands project add --dry-run` are tested
  against a temp HOME.
- No protocol file says "stash"; both require the sub-agent schedule.
- `meta/FINAL-REPORT-22.md` exists with NOT PROVEN and the review-items
  table; the PR from `mission-22` to `main` is open and the tree is on
  `main`.
