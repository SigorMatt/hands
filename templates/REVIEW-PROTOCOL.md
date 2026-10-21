# REVIEW-PROTOCOL — cold review of a hands mission

You are the aux session. You start with no context of the mission you are
reviewing; that is the point. The prompt names the mission number N;
everything else you learn from disk and from the forge. Never take the base
from a job: a job that resumed a mission starts mid-mission.

Before anything else, run `git worktree prune` in your clone, then `git
worktree list`, and remove each stale review worktree an earlier review left
under `/tmp` with `git worktree remove --force <path>`: an aborted review
leaves its worktrees registered. A worktree is stale when it is registered
under the clone and its path no longer exists, or when it is a review
worktree under `/tmp` that is not this review's and is older than the
current aux job's start; a worktree of a review running concurrently, or one
a human made, is never stale, and you leave it. Every worktree this review
adds, yours and each sub-agent's, goes under `/tmp`, and the review ends by
removing them (below).

## `main`'s rules (DESIGN §45)

The review's first step, before you read the brief, reads once whether
`main` takes pull requests only, from GitHub, not from hands:

    gh api repos/<owner>/<repo>/rules/branches/main --jq '[.[].type] | join(" ")'

It names `pull_request` when it does. If the read fails, it is tried once
more a minute later, in the foreground. If that fails too, the review goes
no further: no sub-agents, no hosted review, no run of the gate. Write
`meta/reviews/REVIEW-N.md` with `reviewed: none` and one blocker, "`main`'s
rules could not be read: <the error>"; commit it to the mission's branch
when it exists (the branch the brief's Branch section names, found by `git
ls-remote --exit-code --heads origin <branch>`), as "The review file" says
for a `main` that takes pull requests only — a push to a branch is never
refused by the gate — and otherwise nowhere; and reply with `blockers=1
should-fix=0`.

- Without `pull_request`, the review is committed as before: to `main`,
  before any merge.
- With `pull_request`, a brief whose Branch section says "Direct" is a
  blocker, "a direct mission on a `main` that takes pull requests only", and
  the review goes no further: its file says `reviewed: none`, it is
  committed nowhere, and the reply carries the blocker (`blockers=1
  should-fix=0`). Every other brief is reviewed as below, by the steps that
  say "with `pull_request`".

## The commits under review (DESIGN §35, §36)

The Branch section of the brief decides the shape, and nothing else does.
The direct shape only when the Branch section of `meta/BUILDER-N-PROMPT.md`
says "Direct": the base is the last `review:` commit on `main` (`git log
--oneline --grep='^review: ' -1`), or the mission's kit commit if no review
exists yet, and the commits are `git log --oneline <base>..origin/main`.

Otherwise the review is of the branch the brief names, `<branch>`
(`mission-N`, or the open branch a closer mission continues); every command
below says `<branch>`. `git fetch origin`, then find its pull request
yourself:

    gh pr list --head <branch> --state open --json number,baseRefName,headRefOid

- With no open pull request, the review goes no further: no sub-agents, no
  hosted review, no run of the gate. Write `meta/reviews/REVIEW-N.md` with
  `reviewed: none` and one blocker, "no pull request for <branch>", commit
  it as below, and reply with `blockers=1 should-fix=0`. With `pull_request`
  it is committed nowhere: `main` refuses it, and the branch may not exist.
- With one, the commits under review are the PR's own since the last
  reviewed tip, without `main`'s own history: `git log
  <base>..origin/<branch> ^origin/main`. The base is the merge-base with
  `main` (`git merge-base origin/main origin/<branch>`) for a first review
  of the branch, or, for a closer, the `reviewed:` sha the previous REVIEW
  file of this branch recorded (a `reviewed: none` counts as no review).

Read, in this order: the DESIGN.md section the mission names as its own, `meta/BUILDER-N-PROMPT.md`, `meta/FINAL-REPORT-N.md`,
`meta/findings/FINDINGS.md`, then the `git log --oneline` of the commits
under review.

## The hosted review (with a PR)

Before writing, read the hosted reviewer mechanically (DESIGN §39; the
method is docs/QODO-EXTRACTION.md's, and `hands hosted-review <pr>` is that
method as a command). Dispatch ONE fresh-context sub-agent for it, before
the per-commit sub-agents and like them one at a time, so the reading is
anchored neither in the builder's work nor in yours. It runs `hands
hosted-review <pr>` in a `git worktree` at `origin/<branch>`, where the
builder's own fetch is committed. The command fetches, through `gh`, every
page, filtered to the bot's login, `gh api
repos/<owner>/<repo>/issues/<pr>/comments`, `gh api
repos/<owner>/<repo>/pulls/<pr>/comments` and `gh api
repos/<owner>/<repo>/pulls/<pr>/reviews`; archives each body byte for byte
with its JSON under `meta/reviews/hosted/PR-<pr>/<k>/` (`<k>` one more than
the highest there); diffs the fetch against the previous `<k>` by comment
id; prints the header categories as found and every numbered finding
verbatim with its anchor; and takes the verdict from the Code Review
comment only — never from the inline comments, which a re-review leaves as
they were, and never from "nothing new by id", which is what an in-place
edit looks like.

Exit 3, "no bot comment yet", is the wait, never a clean review (so is "no
Code Review comment yet"; neither writes anything): the sub-agent waits for
the bot up to ten minutes in one-minute foreground steps, running the
command again after each (never a background task); after ten minutes with
none, say so in the section below and go on. Exit 4 is no verdict either:
the header counts findings and none parsed as open, so the sub-agent reads
the archived Code Review comment itself.

The sub-agent then audits the builder's dispositions, the `## Hosted review`
table of `meta/FINAL-REPORT-N.md`, against the archive (the builder's fetch
and this one, and the diff between them) and the edited Code Review comment:
each finding has one row — fixed in `<sha>`, dismissed with a reason, or a
finding H-nnn filed. It reports a finding with no row, a fix whose commit
does not touch the finding's anchor or that the comment still shows open, a
dismissal with no reason, a filed finding absent from
`meta/findings/FINDINGS.md`, and a finding that needed a design decision and
was fixed in silence. It reports the sha, a verdict per point and what is
not proven, and every finding verbatim with its verdict on the builder's
disposition, and names the `<k>` it wrote. Each long command it runs
follows the wait rule (DESIGN §43), its explicit timeout the gate's timeout,
the timeout the project's briefs name (hands' default 15 minutes):
(a) prevent — a project whose
gate can run past its role's `BASH_MAX_TIMEOUT_MS` raises
`BASH_DEFAULT_TIMEOUT_MS` and `BASH_MAX_TIMEOUT_MS` above its worst case,
and its briefs name that timeout; (b) a long command ends with an exit
marker, `./scripts/check; echo "check-exit=$?"`, so its end shows in its
output; (c) if a run is moved to the background anyway, wait with one
foreground command that blocks until the output file shows the marker —
`until grep -q '^check-exit=' <file>; do sleep 5; done`, with an explicit
timeout — never a `sleep` of 25 seconds or more as a command's first
statement, never Monitor or a background task, and never end the turn
before the run has finished.

## The per-commit sub-agents

Dispatch ONE sub-agent per unit commit, one at a time, never concurrently:
the next starts when the last has reported, because each runs
`./scripts/check` and one run at a time fits inside the gate's timeout,
the timeout the project's briefs name (hands' default 15 minutes).
These commits are not units, and none gets a sub-agent, a revert or a run
of the gate:

- A `plan: decisions <date> (owner)` commit is read for what it says it does
  and is not reviewed as a unit: no sub-agent, no revert, no run of the gate.
  Every other `plan:` commit (the mission's U0 among them) is read the same
  way, for what it says it does.
- A `meta:`, `journal:` or `report:` commit is read for forbidden edits only
  and never reviewed as a unit: `git show --stat <sha>`, and a file it lists
  outside `meta/` is a forbidden edit, a blocker.
- A `review:` commit and a merge commit are skipped.
- A human-supplied commit (`fixtures:`, from a "human-supplied unit" of the
  brief) is checked by `git show --stat` alone: you compare the files and
  paths it lists with the ones the unit names, open none of them, and run
  no sub-agent for it.

Each sub-agent, in a `git worktree` at that commit:

1. Names the unit and the DESIGN sections it claims to implement.
2. Confirms test-first: the commit adds or changes tests that exercise the
   claimed behaviour, and the tests fail when the product change is
   reverted: in the worktree at the commit, for each non-test file the body
   lists, `git checkout <sha>~1 -- <file>` when the file exists at
   `<sha>~1`, else `rm` it; then run the commit's new tests and expect red;
   then restore: `git rm -q -f -- <file>` for each listed file absent at
   `<sha>` (a file the commit deletes), then `git checkout <sha> -- <the
   other files>`; `git status --short` must be empty after it. A commit
   body names each file it adds as added and each file it deletes as
   deleted; `git cat-file -e <rev>:<file>` says whether a file exists at a
   revision, and one checkout of several files reverts or restores none of
   them when one is missing at that revision. A sub-agent whose `git status
   --short` is not empty after the restore stops, reports what it lists,
   and goes no further at that commit. A commit that
   changes only tests must name in its body each wrong change that would
   make them red; the
   sub-agent makes each one in the worktree, without committing, runs the
   relevant tests, expects red, and restores. A tests-only commit whose body
   names none is a blocker.
3. At that commit: run `./scripts/check` once, in the foreground, and
   report only when every command has finished; record green/red verbatim.
   The run follows the wait rule (DESIGN §43), its explicit timeout the
   gate's timeout,
   the timeout the project's briefs name (hands' default 15 minutes):
   (a) prevent — a project whose gate can run past its role's `BASH_MAX_TIMEOUT_MS` raises
   `BASH_DEFAULT_TIMEOUT_MS` and `BASH_MAX_TIMEOUT_MS` above its worst case,
   and its briefs name that timeout; (b) a long command ends with an exit
   marker, `./scripts/check; echo "check-exit=$?"`, so its end shows in its
   output; (c) if a run is moved to the background anyway, wait with one
   foreground command that blocks until the output file shows the marker —
   `until grep -q '^check-exit=' <file>; do sleep 5; done`, with an explicit
   timeout — never a `sleep` of 25 seconds or more as a command's first
   statement, never Monitor or a background task, and never end the turn
   before the run has finished.
4. Checks design conformance against the named sections, and that nothing
   forbidden was touched (`DESIGN.md`, `meta/plan.md`, `meta/CHECKPOINT.md`
   by a sub-agent commit). And (DESIGN §45), in either shape, a file under
   `.github/` or `scripts/check` that no unit of the brief names, read with
   `git show --stat <sha>` like any forbidden edit, is a blocker.
5. Reports the sha, a verdict per point and what is not proven.

You run `./scripts/check` yourself once, at the tip under review (in a `git
worktree` at it), and record the result in `## Notes`; that is your only
run of the gate.

## The review file

With `pull_request`, before writing, wait for the pull request's checks at
the reviewed tip: `hands ci-wait <number>; echo "ci-wait-exit=$?"`, one
foreground call at a time, again while it exits 3, at most seven calls. An
end other than exit 0 is a blocker, "the pull request's checks did not pass
at the reviewed tip: <the command's last line>" (a failed gate, or a gate
not shown green), and, whatever the end, the command's last line goes in
`## Notes`.

You then read `meta/FINAL-REPORT-N.md` §NOT PROVEN against what the
sub-agents found, and write `meta/reviews/REVIEW-N.md`. Its first line after
the title is `reviewed: <sha>`, the tip you reviewed (the PR's
`headRefOid`, or the tip of `origin/main` in the direct shape; `reviewed:
none` when the brief's branch has no pull request, when `main`'s rules could
not be read, and for a direct brief on a `main` that takes pull requests
only). Then exactly these
sections: `## Blockers` (numbered; a blocker is a failed gate, a missing
test, a design violation, or a claim the disk contradicts), `## Should-fix`
(numbered), `## Hosted review` (with a PR: the archive's `<k>`, the
verdict the command took from the Code Review comment, every finding of the
bot, verbatim, each with one of: confirmed → carried as blocker k or
should-fix m; dismissed → the reason; and the sub-agent's audit of the
builder's disposition of it; without a PR, or with no bot review after ten
minutes, one line saying so), `## Notes`, `## Per-commit verdicts` (the
sub-agents' reports, verbatim, the hosted-review sub-agent's among them).

`## Notes` carries the schedule: one line per sub-agent with its start and
end time; the sub-agents run one at a time so that one `./scripts/check`
runs at a time inside the gate's timeout,
the timeout the project's briefs name (hands' default 15 minutes).
A review whose Notes lack the schedule is itself a should-fix for the next
review.

Without `pull_request`, the file goes to `main`. Before you commit it,
bring the tree to an up-to-date `main`: `git checkout main && git pull
--ff-only`, and copy the directory the hosted-review sub-agent wrote,
`meta/reviews/hosted/PR-<pr>/<k>/`, from its worktree to the same path. You
may commit that file and the hosted-review archive directory only, to
`main`, as `review: mission N`, and push them, before any merge: the review
and the bot's words as they were are on `main` whatever happens to the
branch. Touch nothing else.

With `pull_request`, the review file and the hosted review's archive are
committed to the mission's branch, never to `main`: carry the journal's
lines over (below), then `git checkout <branch> && git pull --ff-only`, copy
the archive directory in as above, and make one commit `review: mission N`,
pushed to the branch, before any merge. You may commit that file and the
hosted-review archive directory only, besides the journal's own commit. A
clean review lands on `main` with the merge; a review with blockers stays
on the open branch, which the closer mission continues, so the closer's
review finds it there.

Carrying the journal's lines over. A dirty `meta/journal.md` (`git status
--porcelain -- meta/journal.md` lists it) stops `git checkout` of a branch
whose journal differs from `main`'s, and every unit appended to it there.
So, before that `git checkout <branch>`: keep the lines `git diff -U0 --
meta/journal.md` adds (its `+` lines, without the `+++` header) in a file
under `/tmp`; `git checkout -- meta/journal.md` restores the file; check the
branch out; append the kept lines to its `meta/journal.md`; and commit them,
on their own, as `journal: consultation lines`, before the review's commit.
When the file is untracked on `main` (`??`), its whole content is the kept
lines, and it is removed before the checkout. With a clean `meta/journal.md`
there is nothing to carry.

## The merge (with a PR)

With `blockers=0`, merge the PR yourself — `gh pr merge <number> --merge
--subject "merge: mission N (PR #<number>)"` (a merge commit, never a
squash: the per-unit commits are what the next cold review works on) — then
bring the local tree level: `git checkout main && git pull --ff-only`. With
blockers, the review leaves the PR open; say so in the reply, after the
verdict line. Without a PR there is nothing to merge.

With `pull_request` and `blockers=0`, the review's own commit has started
the checks again, so first wait for them — `hands ci-wait <number>; echo
"ci-wait-exit=$?"`, one foreground call at a time, again while it exits 3,
at most seven calls — and merge only on exit 0, as above (`gh pr merge
<number> --merge --subject "merge: mission N (PR #<number>)"`, then `git
checkout main && git pull --ff-only`). On any other end, or when the merge
is refused, do not merge: add a blocker to `REVIEW-N.md`, "the merge was not
made: <the command's last line>", commit it to the branch as `review:
mission N (not merged)`, push, and reply with that blocker counted. A clean
verdict always means a merged mission. With blockers, the PR stays open:
return the tree to `main` (`git checkout main && git pull --ff-only`), so
the next kit's apply runs on `main`.

Last, remove every worktree this review added: `git worktree remove --force
<path>` for each (yours and each sub-agent's, under `/tmp`), then `git
worktree prune`, so that the clone registers none of them.

Your reply's first line is exactly:

    VERDICT: review mission N blockers=<k> should-fix=<m>

followed by the Blockers and Should-fix sections verbatim.
