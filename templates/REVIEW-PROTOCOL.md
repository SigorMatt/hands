# REVIEW-PROTOCOL — cold review of a hands mission

You are the aux session. You start with no context of the mission you are
reviewing; that is the point. The prompt names the mission number N;
everything else you learn from disk and from the forge. Never take the base
from a job: a job that resumed a mission starts mid-mission.

## The commits under review (DESIGN §35)

The mission's branch is `mission-N`, or the branch `meta/BUILDER-N-PROMPT.md`
names for a closer mission. Find its pull request yourself:

    gh pr list --head mission-N --state open --json number,baseRefName,headRefOid

(with the closer's branch in place of `mission-N` when the brief names one).

- With a PR: `git fetch origin`, then the commits under review are the PR's
  own since the last reviewed tip, `git log <base>..origin/mission-N`. The
  base is the merge-base with `main` (`git merge-base origin/main
  origin/mission-N`) for a first review of the branch, or, for a closer, the
  `reviewed:` sha the previous REVIEW file of this branch recorded.
- Without one (a direct mission): the base is the last `review:` commit on
  `main` (`git log --oneline --grep='^review: ' -1`), or the mission's kit
  commit if no review exists yet, and the commits are `git log --oneline
  <base>..origin/main`.

Read, in this order: the DESIGN.md section the mission names as its own, `meta/BUILDER-N-PROMPT.md`, `meta/FINAL-REPORT-N.md`,
`meta/findings/FINDINGS.md`, then the `git log --oneline` of the commits
under review.

## The hosted review (with a PR)

Before writing, read the hosted reviewer's comments on the PR:
`gh api repos/<owner>/<repo>/issues/<pr>/comments`, `gh api
repos/<owner>/<repo>/pulls/<pr>/comments` and `gh api
repos/<owner>/<repo>/pulls/<pr>/reviews`. When none from the bot is there
yet, wait for it, up to ten minutes in one-minute foreground steps (read
again after each; never a background task); after ten minutes with none,
say so in the section below and go on.

## The per-commit sub-agents

Dispatch ONE sub-agent per unit commit (skip `meta:` bookkeeping commits).
Each sub-agent, in a `git worktree` at that commit:

1. Names the unit and the DESIGN sections it claims to implement.
2. Confirms test-first: the commit adds or changes tests that exercise the
   claimed behaviour, and the tests fail when the product change is
   reverted in the worktree (`git stash` the non-test files, run the
   relevant tests, expect red, restore).
3. Runs `./scripts/check` at that commit; records green/red verbatim.
4. Checks design conformance against the named sections, and that nothing
   forbidden was touched (`DESIGN.md`, `meta/plan.md`, `meta/CHECKPOINT.md`
   by a sub-agent commit).
5. Reports in ≤12 lines: sha, verdict per point, anything NOT proven.

## The review file

You then read `meta/FINAL-REPORT-N.md` §NOT PROVEN against what the
sub-agents found, and write `meta/reviews/REVIEW-N.md`. Its first line after
the title is `reviewed: <sha>`, the tip you reviewed (the PR's
`headRefOid`, or the tip of `origin/main` without a PR). Then exactly these
sections: `## Blockers` (numbered; a blocker is a failed gate, a missing
test, a design violation, or a claim the disk contradicts), `## Should-fix`
(numbered), `## Hosted review` (with a PR: every finding of the bot,
verbatim, each with one of: confirmed → carried as blocker k or should-fix
m; dismissed → the reason; without a PR, or with no bot review after ten
minutes, one line saying so), `## Notes`, `## Per-commit verdicts` (the
≤12-line reports, verbatim).

You may commit that one file only, to `main`, as `review: mission N`, and
push it, before any merge: the review is on `main` whatever happens to the
branch. Touch nothing else.

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
