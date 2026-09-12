# REVIEW-PROTOCOL — cold review of a hands mission

You are the aux session. You start with no context of the mission you are
reviewing; that is the point. The prompt names the mission number N;
everything else you learn from disk. The base of the review is the last
`review:` commit on the branch (`git log --oneline --grep='^review: ' -1`),
or the mission's kit commit if no review exists yet. Never take the base
from a job: a job that resumed a mission starts mid-mission.

Read, in this order: the DESIGN.md section the mission names as its own, `meta/BUILDER-N-PROMPT.md`, `meta/FINAL-REPORT-N.md`,
`meta/findings/FINDINGS.md`, then `git log --oneline <base>..origin/main`.

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

You then read `meta/FINAL-REPORT-N.md` §NOT PROVEN against what the
sub-agents found, and write `meta/reviews/REVIEW-N.md` with exactly these
sections: `## Blockers` (numbered; a blocker is a failed gate, a missing
test, a design violation, or a claim the disk contradicts), `## Should-fix`
(numbered), `## Notes`, `## Per-commit verdicts` (the ≤12-line reports,
verbatim). You may commit that one file only, as `review: mission N`, and
push. Touch nothing else.

Your reply's first line is exactly:

    VERDICT: review mission N blockers=<k> should-fix=<m>

followed by the Blockers and Should-fix sections verbatim.
