# REVIEW-PROTOCOL — cold review of a hands mission

You are the aux session. You start with no context of the mission you are
reviewing; that is the point. The prompt names the mission number N;
everything else you learn from disk and from the forge. Never take the base
from a job: a job that resumed a mission starts mid-mission.

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
  it as below, and reply with `blockers=1 should-fix=0`.
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

Before writing, read the hosted reviewer's comments on the PR:
`gh api repos/SigorMatt/hands/issues/<pr>/comments`, `gh api
repos/SigorMatt/hands/pulls/<pr>/comments` and `gh api
repos/SigorMatt/hands/pulls/<pr>/reviews`. When none from the bot is there
yet, wait for it, up to ten minutes in one-minute foreground steps (read
again after each; never a background task); after ten minutes with none,
say so in the section below and go on.

## The per-commit sub-agents

Dispatch ONE sub-agent per unit commit (skip `meta:` bookkeeping commits
and merge commits), one at a time, never concurrently: the next starts when
the last has reported. Each sub-agent, in a `git worktree` at that commit:

1. Names the unit and the DESIGN sections it claims to implement.
2. Confirms test-first: the commit adds or changes tests that exercise the
   claimed behaviour, and the tests fail when the product change is
   reverted in the worktree (`git stash` the non-test files, run the
   relevant tests, expect red, restore). A commit that changes only tests
   must name in its body each wrong change that would make them red; the
   sub-agent makes each one in the worktree, without committing, runs the
   relevant tests, expects red, and restores. A tests-only commit whose body
   names none is a blocker.
3. Runs `./scripts/check` once at that commit; records green/red verbatim.
4. Checks design conformance against the named sections, and that nothing
   forbidden was touched (`DESIGN.md`, `meta/plan.md`, `meta/CHECKPOINT.md`
   by a sub-agent commit).
5. Reports in ≤12 lines: sha, verdict per point, anything NOT proven.

You run `./scripts/check` yourself once, at the tip under review (in a `git
worktree` at it), and record the result in `## Notes`; that is your only
run of the gate.

## The review file

You then read `meta/FINAL-REPORT-N.md` §NOT PROVEN against what the
sub-agents found, and write `meta/reviews/REVIEW-N.md`. Its first line after
the title is `reviewed: <sha>`, the tip you reviewed (the PR's
`headRefOid`, or the tip of `origin/main` in the direct shape; `reviewed:
none` when the brief's branch has no pull request). Then exactly these
sections: `## Blockers` (numbered; a blocker is a failed gate, a missing
test, a design violation, or a claim the disk contradicts), `## Should-fix`
(numbered), `## Hosted review` (with a PR: every finding of the bot,
verbatim, each with one of: confirmed → carried as blocker k or should-fix
m; dismissed → the reason; without a PR, or with no bot review after ten
minutes, one line saying so), `## Notes`, `## Per-commit verdicts` (the
≤12-line reports, verbatim).

Before you commit it, bring the tree to an up-to-date `main`: `git
checkout main && git pull --ff-only`. You may commit that one file only, to
`main`, as `review: mission N`, and push it, before any merge: the review
is on `main` whatever happens to the branch. Touch nothing else.

## The merge (with a PR)

With `blockers=0`, merge the PR yourself — `gh pr merge <number> --merge
--subject "merge: mission N (PR #<number>)"` (a merge commit, never a
squash: the per-unit commits are what the next cold review works on) — then
bring the local tree level: `git checkout main && git pull --ff-only`. With
blockers, the review leaves the PR open; say so in the reply, after the
verdict line. Without a PR there is nothing to merge.

Your reply's first line is exactly:

    VERDICT: review mission N blockers=<k> should-fix=<m>

followed by the Blockers and Should-fix sections verbatim.
