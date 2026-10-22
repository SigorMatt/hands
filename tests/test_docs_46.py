"""DESIGN §46 "H-081", "Review 29's should-fix items" 2 and 4, and "A confirmed bug
in the pull request's own code blocks its merge" (mission 30 U3): the review
protocol (the template and this repository's copy), the brief template's last
unit and the handbook's §9 and §19, pinned sentence by sentence, flattened."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from conftest import strip_paths

ROOT = Path(__file__).resolve().parents[1]
HANDBOOK = ROOT / "docs" / "ARCHITECT-HANDBOOK.md"

MERGE_46 = (
    '`gh pr merge <number> --merge --match-head-commit <sha> --subject'
    ' "merge: mission N (PR #<number>)"`'
)


def flat(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def read(*parts: str) -> str:
    return flat(ROOT.joinpath(*parts).read_text(encoding="utf-8"))


def handbook_section(number: int) -> str:
    text = HANDBOOK.read_text(encoding="utf-8")
    heads = re.findall(rf"^## {number}\. .*$", text, flags=re.M)
    assert len(heads) == 1, f"the handbook has no single `## {number}.` heading"
    return flat(text.split(heads[0], 1)[1].split("\n## ", 1)[0])


#: §46: what both protocol files say, flattened.
PROTOCOL_46 = {
    # H-081: the branch has not moved.
    "every-review-of-a-pull-request": (
        "In every review of a pull request — its file going to `main` or to the"
        " branch; not in the direct shape, and not for a `reviewed: none` review"
    ),
    "the-fetch-and-the-whole-sha": (
        "`git fetch origin`, then `git rev-parse origin/<branch>` must equal the"
        " `reviewed:` sha, the whole 40-character sha"
    ),
    "the-moved-branch-blocker": (
        "\"the branch moved during the review: <reviewed sha> → <its tip>\""
    ),
    "a-refused-push-is-the-same-blocker": (
        "A push of the review's commit to the branch that is refused (the branch"
        " moved after that check) is the same blocker"
    ),
    "the-rebase": "`git fetch origin && git rebase origin/<branch>`",
    "the-moved-commit": "`review: mission N (branch moved)`",
    "the-rebase-abort": "`git rebase --abort` if one is under way",
    "the-branch-reset": "`git branch -f <branch> origin/<branch>`",
    "the-reset-drops": (
        "which drops its unpushed `journal:` and `review:` commits, the carried"
        " journal lines among them"
    ),
    "the-moved-reply": "replies with the blocker counted",
    # PR #10's hosted finding 1: the check is the last step before the commit.
    "the-check-is-the-last-step": (
        "as the last step before you commit the file — after the tree is brought"
        " to `main` or the branch is checked out and pulled, as below"
    ),
    "the-check-after-the-pull": (
        "copy the archive directory in as above, check that the branch has not"
        " moved (above), and make one commit `review: mission N`"
    ),
    "the-head-is-the-reviewed-tip": (
        "When the file goes to the branch, the commit the review's commit goes on"
        " top of must be the reviewed tip, or the `journal: consultation lines`"
        " commit whose parent is the reviewed tip: `git rev-parse HEAD` must equal"
        " the whole `reviewed:` sha, or, when HEAD is that journal commit,"
        " `git rev-parse HEAD^` must"
    ),
    # PR #10's hosted finding 3: the not-merged push's recovery.
    "the-not-merged-push-refused": (
        "When that push is refused (the branch moved after the review's commit"
        " was pushed), take the steps of a refused push of the review's commit:"
        " `git fetch origin && git rebase origin/<branch>` (`git rebase"
        " origin/main` when the review went to `main`) puts the review's local"
        " commits on the new tip, and push"
    ),
    "the-not-merged-recovery-fails": (
        "if the rebase or that push fails too, commit nothing more (`git rebase"
        " --abort` if one is under way), return the tree to `main` (`git checkout"
        " main && git pull --ff-only`), set the local branch back to its remote"
        " (`git branch -f <branch> origin/<branch>`) when the review went to the"
        " branch, and reply with the blocker counted"
    ),
    # H-081: the merge names its head.
    "the-match-head-merge": MERGE_46,
    "the-sha-on-main": (
        "`<sha>` being the whole sha of the reviewed tip when the review was"
        " committed to `main`"
    ),
    "the-sha-on-the-branch": (
        "the review's own commit (`git rev-parse HEAD` after its push) when it was"
        " committed to the branch"
    ),
    "gh-refuses-another-head": "gh refuses the merge when the head is another commit",
    "not-merged-with-or-without-the-rule": (
        "A merge that is refused or not made, with or without the `pull_request`"
        " rule, is a blocker"
    ),
    "not-merged-where-the-review-was": (
        "commit it where the review was (to `main` without the rule, to the branch"
        " with it) as `review: mission N (not merged)`"
    ),
    # Should-fix 2 (H-084): the failure paths.
    "the-rules-failure-whatever-the-rules": (
        "whatever the rules are, since they are unknown, commit it to the branch the"
        " brief's Branch section names when it exists on `origin`"
        " (`git ls-remote --exit-code --heads origin <branch>`), never to `main`"
    ),
    "the-missing-pr-to-the-branch": (
        "With `pull_request` it is committed to `<branch>` when it exists on"
        " `origin` (`git ls-remote --exit-code --heads origin <branch>`), never to"
        " `main`, as \"The review file\" says, and otherwise nowhere"
    ),
    "the-direct-brief-nowhere": (
        "its file says `reviewed: none`, it is committed nowhere, and the reply"
        " carries the blocker"
    ),
    "the-reply-in-every-case": "the reply carries the blocker in every case",
    # Should-fix 4 (H-085): the end on main.
    "end-on-main": (
        "In every shape, a review that has checked out the mission's branch ends"
        " with `git checkout main && git pull --ff-only`"
    ),
    # A confirmed bug in the pull request's own code.
    "the-blocker-definition": (
        "a blocker is a failed gate, a missing test, a design violation, a claim the"
        " disk contradicts, or a confirmed defect as \"A defect\" says"
    ),
    "every-confirmed-finding": (
        "For every confirmed finding, the hosted reviewer's and your own"
    ),
    "the-defect-definition": (
        "A **defect** is text — code, a prompt, a protocol, a document — whose"
        " behaviour contradicts its own stated purpose: a wrong result, a failure,"
        " a security gap; not a missing feature, and not a design choice someone"
        " may disagree with"
    ),
    "a-defect-in-the-pull-request": (
        "A defect in what the pull request adds or changes is a blocker, even when"
        " the design prescribes it; so is a defect present at the base that the"
        " pull request makes reachable where it was not, or relies on for what it"
        " adds"
    ),
    "the-closer-continues": (
        "The pull request stays open, and the closer mission continues its branch,"
        " its kit correcting the design first"
    ),
    "another-defect-at-the-base": (
        "Any other defect present at the base — shown by the base's own text, or by"
        " one test or command in a worktree at the merge-base"
        " (`git merge-base origin/main origin/<branch>`), never by the gate — is a"
        " should-fix marked \"to be filed\""
    ),
    "the-review-commits-nothing-more": (
        "the review commits nothing but its own file and the archive"
    ),
    "the-direct-shape-defect": (
        "In the direct shape there is no pull request to hold: a defect in the"
        " commits under review is a blocker"
    ),
    "the-hosted-section-says-which": (
        "The `## Hosted review` section says, for each confirmed finding, which of"
        " these it is and why"
    ),
}


@pytest.mark.parametrize("key", sorted(PROTOCOL_46))
@pytest.mark.parametrize("name", ["templates", "meta"])
def test_both_protocols_carry_section_46s_review(name: str, key: str) -> None:
    text = read(name, "REVIEW-PROTOCOL.md")
    said = PROTOCOL_46[key]
    assert said in strip_paths(text), f"{name}/REVIEW-PROTOCOL.md does not say {said!r}"


@pytest.mark.parametrize("name", ["templates", "meta"])
def test_the_protocols_old_nowhere_and_unguarded_merge_are_gone(name: str) -> None:
    """§46 replaces §45's "nowhere" for a missing pull request, and every merge
    command names its head."""
    text = read(name, "REVIEW-PROTOCOL.md")
    assert "With `pull_request` it is committed nowhere: `main` refuses it" not in strip_paths(text)
    assert "--merge --subject" not in strip_paths(text)
    assert text.count("`gh pr merge <number> --merge") == text.count(MERGE_46) >= 2


@pytest.mark.parametrize("name", ["templates", "meta"])
def test_the_moved_branch_check_comes_before_the_reviews_commit(name: str) -> None:
    text = read(name, "REVIEW-PROTOCOL.md")
    review_file = text.split("## The review file", 1)[1].split("## The merge", 1)[0]
    check = review_file.index("`git rev-parse origin/<branch>` must equal")
    assert check < review_file.index("Without `pull_request`, the file goes to `main`")
    assert check < review_file.index("one commit `review: mission N`, pushed to the branch")


@pytest.mark.parametrize("name", ["templates", "meta"])
def test_the_moved_branch_check_comes_after_the_pull(name: str) -> None:
    """PR #10's hosted finding 1: a pull after the check could bring in a commit
    pushed after it, so the check is the last step before the review's commit,
    in both paragraphs that commit it."""
    text = read(name, "REVIEW-PROTOCOL.md")
    review_file = text.split("## The review file", 1)[1].split("## The merge", 1)[0]
    on_main = review_file.split("Without `pull_request`, the file goes to `main`", 1)[1]
    on_main = on_main.split("With `pull_request`, the review file", 1)[0]
    check = on_main.index("check that the branch has not moved (above)")
    assert on_main.index("`git checkout main && git pull --ff-only`") < check
    assert check < on_main.index("as `review: mission N`")
    on_branch = review_file.split("With `pull_request`, the review file", 1)[1]
    on_branch = on_branch.split("Carrying the journal's lines over", 1)[0]
    check = on_branch.index("check that the branch has not moved (above)")
    assert on_branch.index("`git checkout <branch> && git pull --ff-only`") < check
    assert check < on_branch.index("one commit `review: mission N`")


@pytest.mark.parametrize("name", ["templates", "meta"])
def test_the_failure_paths_end_on_main_before_the_verdict(name: str) -> None:
    """The end on `main` and the worktrees' removal hold in every shape, the
    failure paths' among them: they are the protocol's last section."""
    text = read(name, "REVIEW-PROTOCOL.md")
    end = text.split("## The end (every shape)", 1)[1]
    assert "a review that has checked out the mission's branch ends" in strip_paths(end)
    assert "`git worktree prune`" in strip_paths(end)
    assert "VERDICT: review mission N blockers=<k> should-fix=<m>" in strip_paths(end)
    rules = text.split("## `main`'s rules", 1)[1].split("## The commits under review", 1)[0]
    assert "\"The end\"" in strip_paths(rules)
    commits = text.split("## The commits under review", 1)[1].split("Read, in this order", 1)[0]
    assert "\"The end\"" in strip_paths(commits)


def test_the_brief_templates_last_unit_says_such_a_finding_blocks_the_merge() -> None:
    """§46: the pinned sentence stays intact and in its place, and the next one
    says such a finding in the pull request's own code blocks the merge."""
    text = read("templates", "BUILDER-N-PROMPT.md")
    last = text.split("**U-last Final report.**", 1)[1].split("## Acceptance", 1)[0]
    pinned = (
        "a finding that needs a design decision is filed in"
        " `meta/findings/FINDINGS.md`, never fixed in silence."
    )
    new = (
        " Such a finding in the pull request's own code — a defect in what it adds or"
        " changes, or one at the base that it makes reachable or relies on — blocks"
        " its merge until the closer mission fixes it (DESIGN §46). It pushes."
    )
    assert pinned + new in last


def test_the_handbook_section_9_says_section_46s_review() -> None:
    nine = handbook_section(9)
    for said in (
        MERGE_46,
        "the reviewed tip when the review was committed to `main`",
        "the review's own commit (`git rev-parse HEAD` after its push) when it was"
        " committed to the branch",
        "\"the branch moved during the review: <reviewed sha> → <its tip>\"",
        "`review: mission N (branch moved)`",
        "`git branch -f <branch> origin/<branch>`",
        "with or without the `pull_request` rule",
        "`review: mission N (not merged)`",
        "`git ls-remote --exit-code --heads origin <branch>`",
        "never to `main`",
        "a Direct brief's under `pull_request` is committed nowhere",
        "the reply carries the blocker in every case",
        "a review that has checked out the mission's branch ends with"
        " `git checkout main && git pull --ff-only`",
        "A **defect** is text — code, a prompt, a protocol, a document — whose"
        " behaviour contradicts its own stated purpose",
        "a blocker, even when the design prescribes it",
        "makes reachable where it was not, or relies on for what it adds",
        "its kit correcting the design first",
        "`git merge-base origin/main origin/<branch>`",
        "never by the gate",
        "a should-fix marked \"to be filed\"",
        "In the direct shape a defect in the commits under review is a blocker",
    ):
        assert said in strip_paths(nine), f"handbook §9 does not say {said!r}"
    assert "--merge --subject" not in strip_paths(nine)


def test_handbook_section_19s_review_with_blockers_row_says_the_failure_paths() -> None:
    nineteen = HANDBOOK.read_text(encoding="utf-8").split("\n## 19.", 1)[1]
    rows = [line for line in nineteen.splitlines() if line.startswith("| ")]
    row = next(r for r in rows if "Mission <n> review has blockers" in r)
    for said in (
        "the review of a failed rules read, whatever the rules, and under"
        " `pull_request` that of a missing pull request, is on the branch the brief"
        " names when it exists on `origin`, and otherwise nowhere",
        "a Direct brief's under `pull_request` is nowhere",
        "the reply carries the blocker",
        "a confirmed defect in what the pull request adds or changes",
        "its kit correcting the design first",
    ):
        assert said in strip_paths(row), f"§19's review-with-blockers row does not say {said!r}"
