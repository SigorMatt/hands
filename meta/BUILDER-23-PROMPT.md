# BUILDER-23-PROMPT — hands mission 23: review 22, the four findings, the hosted review read mechanically

Kickoff line (the only way this mission is started or resumed):

    Read the builder prompt with the highest mission number in the meta directory and execute the mission below its divider.

You are the builder for the `hands` repository. Read `DESIGN.md` (v3.22; §39
is this mission, with §24, §27, §31, §35, §38), `CLAUDE.md`,
`meta/CHECKPOINT.md` (a unit in progress means §R first),
`meta/reviews/REVIEW-22.md` and `docs/QODO-EXTRACTION.md` in full.

---

## Mission

Close review 22's twelve should-fix items and rule H-051..H-054 as DESIGN
§39 says; resume a review a daemon stop kills (H-057); publish phone
refusals and accept lenient job ids (H-058, H-059); commit the consult
journal line on resume (H-060); read the hosted review mechanically with
`hands hosted-review <pr>` and fix its findings inside the pull request
(§39); correct the docs. It does NOT touch the backend seam, the polish
round or any roadmap work of M8 (mission 24). Finish with a report whose
first line the playbook can match.

## Branch (DESIGN §35)

Pull request. This mission runs on the branch `mission-23`. U0 creates it
from `main` (`git checkout main && git pull --ff-only && git checkout -b
mission-23`). Every unit commit goes to that branch and is pushed at once
(`git push -u origin mission-23` the first time). The last unit opens the
pull request — `gh pr create --base main --head mission-23 --title "mission
23: review 22, the four findings, the hosted review read mechanically"
--body-file meta/FINAL-REPORT-23.md` — waits for the hosted review, fixes
what §39 allows, and the final reply's verdict carries the PR number. Then
return the working tree to `main` (`git checkout main && git pull
--ff-only`): the next kit apply and the next kickoff run in this tree, on
`main`.

## Execution model (binding)

- You are a thin orchestrator. You plan units, write the checkpoint,
  dispatch ONE sub-agent per unit (Task tool, foreground only), verify the
  unit cheaply, record one line, move on. You run nothing longer than `git
  status`, `git log --oneline -5`, and `./scripts/check` yourself.
- Before each unit: write `meta/CHECKPOINT.md` (unit id, intent, what
  "done" means, standing constraints). After each unit: update it and
  append one line to `meta/journal.md`.
- Every unit ends with a commit AND a push, to `mission-23`. A unit commit
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
- Your final reply begins with exactly one of: `VERDICT: mission 23
  finished pr=<number>` | `VERDICT: mission 23 blocked <unit>` | `VERDICT:
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
    change that would make them red; a commit that adds or deletes a
    non-test file names it as added or deleted; never `git add -A`; push to
    the branch `mission-23`; never edit meta/plan.md, meta/CHECKPOINT.md,
    or DESIGN.md; if the unit needs a design change, stop and write a memo
    to meta/findings/FINDINGS.md instead of improvising; dispatch nothing
    in the background; never require a real `claude`, `gh`, `systemctl`,
    ntfy server or `git` remote in tests (fakes on PATH, a local HTTP stub
    and local bare repositories, as tests/fake_claude.py is); report in ≤12
    lines: sha, files, tests added, what is NOT proven.

## §R Recovery brief

If `meta/CHECKPOINT.md` names a unit in progress and the working tree is
dirty: finish that unit under the sub-agent rules if it can pass
`./scripts/check`; otherwise `git stash push -m "wip <unit> <date>"`,
record in the checkpoint where it stopped and that a stash exists, and
leave the tree clean. Then continue from that unit. Push before taking any
new unit. If the tree is on `main` and `origin/mission-23` exists, `git
checkout mission-23 && git pull --ff-only` first. A `keep` send that
arrives after you replied `VERDICT: question` is the answer: carry it out,
continue the mission from the checkpoint, and end that reply with one of
the mission's `VERDICT:` lines, always, even when the answer came with a
file to commit first. If `meta/journal.md` alone is dirty when you start,
commit it first as `journal: consultation lines` and push.

## Units, in order

**U0 Plan, branch and findings (`plan:` commit).** `meta/plan.md`,
`meta/CHECKPOINT.md`; the branch `mission-23` created and pushed. File in
`meta/findings/FINDINGS.md`: H-055 the revert step fails for a file the
commit deletes (review 22 should-fix 8); H-056 `no_background.py` runs
without `-I` (should-fix 12); H-057 a daemon restart kills a running review
and nothing resumes it (`aux.orphaned` is not an event; 2026-10-15 20:23);
H-058 a refused phone command is logged, not published; H-059 job ids typed
on a phone arrive with `O` for `0` and are refused; H-060 the consult
journal line after an escalation is left uncommitted. Set H-051..H-054 to
"decided (DESIGN §39, mission 23 U<n>)" with the ruling's one line each.
Carry should-fix 1–12 by number into the units below. Gate: the entries
exist; `git branch -r` shows `origin/mission-23`.

**U1 The who watcher (§39; §24; should-fix 1, 2).** `src/hands/who.py`,
tests. A test whose fingerprint changes while the blanked picture does not,
and the reverse, pins the comparison; the fingerprint is stored whenever the
blanked picture equals the last published one; the scans `[True, True,
False, True]` reproduction from the review publishes nothing for the human's
own session. Gate: the tests; `./scripts/check` green.

**U2 Orphans, refusals and ids (§39; should-fix 3, 4; H-057, H-058, H-059).**
`src/hands/daemon.py`, `src/hands/playbook.py`, `src/hands/phone.py`,
`src/hands/notify.py`, `PLAYBOOK.toml`, `templates/PLAYBOOK-missions.toml`,
`templates/PLAYBOOK-runs.toml`, tests. A `reply` or `answer` a daemon stop
orphans is published as its end; a builder `answer` is re-sent as a `keep`;
the start notification names a daemon stop only when `orphan_reason` says
so. `aux.orphaned` joins `EVENTS`; the stop records an aux job orphaned as a
builder's; both templates and this repository's playbook gain `aux.orphaned
→ resume` and `kit check` accepts it. Every refusal of a command carrying
the right secret is published titled `<command>` with the reason; a wrong
or missing secret stays silent. Job ids are matched as §39 says (`O`→`0`,
`l`/`I`→`1`, case-insensitive, a unique prefix of four or more characters)
in `approve`, `deny`, `answer`, `reply`, `cancel`; the hold notification
prints the id on its own line. Tests: each orphan case; a review job
orphaned by a stop is resumed with the rule's prompt at the next start; a
refused `approve` publishes its reason; `Omv9a9z9a-arir` resolves the
right job and an ambiguous prefix is refused with the candidates. Gate: the
tests; `hands --project hands pipeline` loads this playbook with the new
rule; `./scripts/check` green.

**U3 The engine's small fixes (§39; should-fix 5, 7; H-060).**
`src/hands/playbook.py`, `src/hands/api.py`, tests. The architect-consult
rule check judges the compiled regex against sample lines (`VERDICT: mission
1 blocked U2` matches, `VERDICT: mission 1 finished` does not; `(?i)…` is
fine); the two owner-file fallbacks are inclusive with a note each; the
resume path — an `answer` and a cli `--context keep|clear` send to the
builder — prefixes the prompt with one sentence telling the builder to
commit a dirty `meta/journal.md` first when the working tree shows it
modified (the daemon checks `git status --porcelain -- meta/journal.md` in
the builder's cwd). Tests: the four regex cases; the two fallbacks; the
prefix present only when the file is dirty. Gate: the tests;
`./scripts/check` green.

**U4 `progress` and the README (§39; should-fix 6).** `src/hands/phone.py`,
`README.md`, tests. `progress` reads `meta/CHECKPOINT.md` at `git rev-parse
--show-toplevel` of the builder's cwd; README's phone-command list names
all ten commands. Tests: a cwd two levels below the root finds the
checkpoint; the docs test pins the ten names. Gate: the tests;
`./scripts/check` green.

**U5 `hands hosted-review <pr>` (§39; docs/QODO-EXTRACTION.md).**
`src/hands/cli.py`, a new `src/hands/hosted.py`, tests with a fake `gh` on
PATH serving recorded pages. The command fetches the three sources, every
page, filtered to the bot's login (default `qodo-code-review[bot]`,
`--bot` to change); archives each body byte for byte and the raw JSON under
`meta/reviews/hosted/PR-<n>/<k>/` with `k` the next unused number; prints
the Code Review comment's header categories and counts as found, every
numbered finding verbatim with its file:line anchor, and the summary
comment's id; with a previous `<k>` present, prints the diff by comment id
(changed bodies with `updated_at` and the changed lines; ids added or
vanished; findings struck through or marked resolved listed as such);
reports "no bot comment yet" with exit status 3 and writes nothing. Tests:
first fetch on recorded fixtures; second fetch after an in-place edit; no
comments; pagination across two pages; a category never seen before is
printed, not dropped. Gate: the tests; `./scripts/check` green.

**U6 The protocol and the brief template (§39; should-fix 8; H-055).**
`templates/REVIEW-PROTOCOL.md`, `meta/REVIEW-PROTOCOL.md`,
`templates/BUILDER-N-PROMPT.md`, `docs/ARCHITECT-HANDBOOK.md` §9, tests.
The revert step `git rm -q`s a listed file absent at `<sha>` before the
restore and requires `git status --short` empty after it; the hosted-review
step runs `hands hosted-review <pr>` as a fresh-context sub-agent, commits
the archive with the review file, takes the verdict from the Code Review
comment only, audits the builder's dispositions from the final report
against the archive, and treats "no bot comment yet" as the wait; the brief
template's last unit opens the PR, waits up to ten minutes for the bot,
runs the command, fixes findings within the design, pushes, and writes the
`## Hosted review` disposition table into the final report (fixed in
`<sha>` | dismissed: reason | finding H-nnn filed). The two protocol files
differ only in the project's names. Tests: the sentence-pinning tests cover
the new sentences; a kit from the templates passes `kit check` 6 of 6.
Gate: the tests; `./scripts/check` green.

**U7 H-051 and H-052 (§39; should-fix 10).** `src/hands/playbook.py`
(the consult prompt), `driver/hooks/bash_guard.py`, `architect/settings.json`
if needed, `architect/CLAUDE.md`, `src/hands/cli.py` (help text),
`src/hands/project.py`, `meta/findings/FINDINGS.md` (HF-002 resolved in
full), tests. The architect's consult prompt names the installed handbook's
and templates' absolute paths; the guard's read roots gain `HANDS_DOCS` and
the architect's `hands` subcommands gain `handbook`; `architect/CLAUDE.md`
rule 2 says to Read the paths the prompt names; the `hands handbook` help
text names `$HANDS_DOCS/docs/…`; `project add` writes `architect/CLAUDE.md`
with the Parameters filled into the role directory and prints the filled
`docs/ARCHITECT-INSTRUCTION.md` last (confirming U10's reading). Tests: the
prompt carries both paths; the guard allows `cat <HANDS_DOCS>/docs/x.md`
and `hands handbook` under `HANDS_ROLE=architect` and still refuses a read
outside the roots; `project add --dry-run` names the role variant. Gate:
the tests; `./scripts/check` green.

**U8 `project add` after a failed clone; the role's rulings (§39;
should-fix 9, 11).** `src/hands/project.py`, `architect/CLAUDE.md`, tests.
`git clone -- <url>`; a failed clone removes everything the command created
and prints the list; a re-run then succeeds. Rule 13 and rule 8 agree: a
ruling the role cannot make is `VERDICT: escalate ruling: <what>` with a
drafted owner file under `kits/<name>/meta/decisions/`; rule 8 lists it.
Tests: a clone that fails (a fake `git` on PATH) leaves nothing behind and
the re-run creates the project; the instruction test pins the rule text.
Gate: the tests; `./scripts/check` green.

**U9 Hooks and docs (§39; should-fix 12; H-053, H-054, H-056).**
`.claude/settings.json`, `docs/INTEGRATION.md`, `docs/ARCHITECT-HANDBOOK.md`,
`docs/PLAYBOOK.md`, tests. `no_background.py` runs as `python3 -I` in the
settings file, the copy line and the self-test; INTEGRATION says a restart
kills every running job of the project and what resumes what (builder and
aux by rule, consultations stop), that the driver kit has one hook and the
architect kit two, that a clean-review stop pauses the pipeline and the next
apply with `go` un-pauses it, and that `[server]` is read as the fallback
and a key set in both tables refuses to load; the handbook says `status`
prints every configured role, cites docs/QODO-EXTRACTION.md at the
hosted-review step, and describes the same-PR fix round and the lenient
ids. Tests: the docs tests pin the `-I` spelling for both hooks and the new
sentences. Gate: the tests; `./scripts/check` green.

**U10 Final report, the pull request and the hosted review's findings.**
`meta/FINAL-REPORT-23.md` (drafted under `meta/drafts/`, moved in by this
commit): what changed (sha per unit), what tests prove, NOT PROVEN
(mandatory; at least: no real phone has used the lenient ids or seen a
published refusal; no real daemon restart has resumed a review; the
command has run against recorded pages only), the `## Review items` table
for REVIEW-22 should-fix 1–12 and the findings resolved (H-051..H-060,
HF-002). Open the pull request as the Branch section says; wait for the
bot up to ten minutes in one-minute foreground steps; run `hands
hosted-review <pr>` (the command U5 built, from this tree); fix the
findings that are within §39 with one more commit per finding or one
commit for all, each naming the finding by its title; push; run the
command again so the archive holds both fetches; add the `## Hosted
review` disposition table to the report in a final `report:` commit; push;
return the tree to `main`; reply with the verdict line carrying the PR
number.

## Acceptance

- `./scripts/check` green on the pushed tip of `mission-23`, three
  consecutive runs.
- Every unit commit's body lists every file it touches; U0 is `plan:`.
- H-055..H-060 filed; H-051..H-060 and HF-002 resolved or decided as §39
  says; review 22 should-fix 1–12 each named by the unit that closed it.
- A test shows a review job orphaned by a daemon stop is resumed at the
  next start, and `PLAYBOOK.toml` carries `aux.orphaned → resume`.
- A test shows `Omv9a9z9a-arir` resolves and a refused `approve` is
  published.
- `hands hosted-review` archives two fetches and prints their diff on
  recorded fixtures.
- Both protocol files `git rm` a deleted file and require a clean status
  after the restore; neither says "stash".
- `meta/FINAL-REPORT-23.md` exists with NOT PROVEN, the review-items table
  and the `## Hosted review` disposition table; `meta/reviews/hosted/PR-<n>/`
  holds the archive; the PR from `mission-23` to `main` is open and the
  tree is on `main`.
