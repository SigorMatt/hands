"""DESIGN §45 "The review", "The brief template and the architect" and
"Documentation" (mission 29 U5): the review protocol (the template and this
repository's copy), the brief template, `architect/CLAUDE.md` rules 1 and 3, the
handbook, docs/INTEGRATION.md, docs/OPERATIONS.md, docs/PLAYBOOK.md and
`CLAUDE.md`, pinned sentence by sentence, flattened."""

from __future__ import annotations

import re
import textwrap
import tomllib
from pathlib import Path

import pytest

from conftest import strip_paths
from hands import kit as kit_mod
from hands.config import parse_config

ROOT = Path(__file__).resolve().parents[1]
HANDBOOK = ROOT / "docs" / "ARCHITECT-HANDBOOK.md"


def flat(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def read(*parts: str) -> str:
    return flat(ROOT.joinpath(*parts).read_text(encoding="utf-8"))


def section(text: str, heading: str) -> str:
    """The handbook's (or a doc's) `## <heading>` section, up to the next `## `."""
    start = text.index("\n" + heading)
    end = text.find("\n## ", start + 1)
    return flat(text[start:] if end < 0 else text[start:end])


def handbook_section(heading: str) -> str:
    return section(HANDBOOK.read_text(encoding="utf-8"), heading)


def rows_of(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.startswith("| ")]


# ------------------------------------------------------------ the review protocol

RULES_READ = "gh api repos/<owner>/<repo>/rules/branches/main --jq '[.[].type] | join(\" \")'"

#: §45 "The review": what both protocol files say, flattened.
PROTOCOL_45 = {
    "the-rules-read-before-the-brief": "The review's first step, before you read the brief",
    "from-github-not-from-hands": "from GitHub, not from hands",
    "pull-request-named": "It names `pull_request` when it does",
    "the-retry": "it is tried once more a minute later",
    "the-failures-blocker": "one blocker, \"`main`'s rules could not be read: <the error>\"",
    "a-branch-push-is-never-refused": "a push to a branch is never refused by the gate",
    "otherwise-nowhere": "and otherwise nowhere",
    "without-pull-request-to-main": (
        "Without `pull_request`, the review is committed as before: to `main`,"
        " before any merge"
    ),
    "the-direct-blocker": "\"a direct mission on a `main` that takes pull requests only\"",
    # §46 "Review 29's should-fix items" 2 moved this pin (H-084).
    "no-pr-committed-to-the-branch-on-origin": (
        "With `pull_request` it is committed to `<branch>` when it exists on"
        " `origin`"
    ),
    "the-wait-at-the-reviewed-tip": (
        "wait for the pull request's checks at the reviewed tip:"
        " `hands ci-wait <number>; echo \"ci-wait-exit=$?\"`, one foreground call at a"
        " time, again while it exits 3, at most seven calls"
    ),
    "the-waits-blocker": (
        "An end other than exit 0 is a blocker, \"the pull request's checks did not"
        " pass at the reviewed tip: <the command's last line>\" (a failed gate, or a"
        " gate not shown green)"
    ),
    "the-last-line-in-the-notes": "the command's last line goes in `## Notes`",
    "the-review-on-the-branch": (
        "the review file and the hosted review's archive are committed to the"
        " mission's branch, never to `main`"
    ),
    "one-commit-on-the-branch": (
        "one commit `review: mission N`, pushed to the branch, before any merge"
    ),
    "a-review-with-blockers-stays-on-the-branch": (
        "a review with blockers stays on the open branch, which the closer mission"
        " continues, so the closer's review finds it there"
    ),
    "the-merges-wait": (
        "the review's own commit has started the checks again, so first wait for them"
    ),
    "merge-only-on-exit-0": "merge only on exit 0",
    "the-not-merged-blocker": "\"the merge was not made: <the command's last line>\"",
    "the-not-merged-commit": "`review: mission N (not merged)`",
    "a-clean-verdict-is-a-merged-mission": "A clean verdict always means a merged mission",
    "the-return-to-main-with-blockers": (
        "return the tree to `main` (`git checkout main && git pull --ff-only`), so the"
        " next kit's apply runs on `main`"
    ),
    "the-journal-kept-lines": "keep the lines `git diff -U0 -- meta/journal.md` adds",
    "the-journal-restored": "`git checkout -- meta/journal.md` restores the file",
    "the-journal-committed": "commit them, on their own, as `journal: consultation lines`",
    "the-journal-untracked": (
        "When the file is untracked on `main` (`??`), its whole content is the kept"
        " lines, and it is removed before the checkout"
    ),
    "the-ci-blocker": (
        "in either shape, a file under `.github/` or `scripts/check` that no unit of"
        " the brief names, read with `git show --stat <sha>` like any forbidden edit,"
        " is a blocker"
    ),
}


@pytest.mark.parametrize("key", sorted(PROTOCOL_45))
@pytest.mark.parametrize("name", ["templates", "meta"])
def test_both_protocols_carry_section_45s_review(name: str, key: str) -> None:
    text = read(name, "REVIEW-PROTOCOL.md")
    said = PROTOCOL_45[key]
    assert said in strip_paths(text), f"{name}/REVIEW-PROTOCOL.md does not say {said!r}"


def test_the_rules_read_is_the_protocols_first_step_with_this_repositorys_names() -> None:
    """The read comes before the brief is read; this repository's copy names
    `SigorMatt/hands` (the rest of the copy is the template's, tests/test_docs.py)."""
    template = read("templates", "REVIEW-PROTOCOL.md")
    ours = read("meta", "REVIEW-PROTOCOL.md")
    assert RULES_READ in strip_paths(template)
    assert RULES_READ.replace("<owner>/<repo>", "SigorMatt/hands") in strip_paths(ours)
    for text in (template, ours):
        assert text.index("rules/branches/main") < text.index("Read, in this order:")
        assert text.index("rules/branches/main") < text.index("## The commits under review")


@pytest.mark.parametrize("name", ["templates", "meta"])
def test_the_journal_is_carried_over_before_the_branch_is_checked_out(name: str) -> None:
    text = read(name, "REVIEW-PROTOCOL.md")
    branch = text.index("the review file and the hosted review's archive are committed")
    rest = text[branch:]
    assert rest.index("carry the journal's lines over") < rest.index(
        "`git checkout <branch> && git pull --ff-only`"
    )


@pytest.mark.parametrize("name", ["templates", "meta"])
def test_the_merge_waits_before_it_merges_and_the_last_line_is_the_verdict(name: str) -> None:
    text = read(name, "REVIEW-PROTOCOL.md")
    merge = text.split("## The merge (with a PR)", 1)[1]
    assert merge.index("first wait for them") < merge.rindex("`gh pr merge <number> --merge")
    raw = ROOT.joinpath(name, "REVIEW-PROTOCOL.md").read_text(encoding="utf-8")
    assert kit_mod.review_literals([raw]) == [
        "VERDICT: review mission N blockers=<k> should-fix=<m>"
    ]


# ------------------------------------------------------------ the brief template


def brief() -> str:
    return read("templates", "BUILDER-N-PROMPT.md")


def test_the_brief_templates_direct_paragraph_says_a_pull_request_main_never_takes_it() -> None:
    direct = brief().split("Direct. This mission commits to `main`", 1)[1]
    direct = direct.split("## Execution", 1)[0]
    assert (
        "A repository whose `main` takes pull requests only (DESIGN §45) never takes"
        " this shape" in strip_paths(direct)
    )


def test_the_brief_templates_closer_carries_the_journal_over_before_its_checkout() -> None:
    branch = brief().split("## Branch (DESIGN §35)", 1)[1].split("Direct. This mission", 1)[0]
    for said in (
        "a dirty `meta/journal.md` stops that checkout",
        "keep the lines `git diff -U0 -- meta/journal.md` adds",
        "`git checkout -- meta/journal.md`",
        "commit them, on their own, as `journal: consultation lines`",
        "its whole content is the kept lines and it is removed before the checkout",
    ):
        assert said in strip_paths(branch), f"the Branch section does not say {said!r}"
    assert branch.index("keep the lines") < branch.index("then `git checkout <branch>`")
    assert branch.index("then `git checkout <branch>`") < branch.index("then `git merge main`")


def test_the_brief_templates_recovery_brief_says_the_journal_rule() -> None:
    recovery = brief().split("## §R Recovery brief", 1)[1].split("## Units, in order", 1)[0]
    assert (
        "A dirty `meta/journal.md` at the start is committed, on its own, as `journal:"
        " consultation lines` on the mission's branch — on `main`, only after U0 has"
        " created or checked out that branch — and never pushed to `main` unless the"
        " Branch section says Direct" in strip_paths(recovery)
    )


def test_the_brief_templates_last_unit_waits_for_the_checks_before_the_table() -> None:
    last = brief().split("**U-last Final report.**", 1)[1].split("## Acceptance", 1)[0]
    wait = (
        "On a repository whose `main` takes pull requests only (DESIGN §45) it then"
        " waits for the pull request's checks — `hands ci-wait <pr>; echo"
        " \"ci-wait-exit=$?\"`, one foreground call at a time, again while it exits 3,"
        " at most seven calls — and fixes a failed check within the design as it fixes"
        " a hosted finding, committed and pushed to the branch, before the `## Hosted"
        " review` table; the final report names each awaited check and its result"
    )
    assert wait in strip_paths(last)
    assert last.index("It pushes.") < last.index(wait) < last.index("`fixed in <sha>`")
    execution = brief().split("## Execution model", 1)[1].split("## Sub-agent brief", 1)[0]
    assert "`hands ci-wait <pr>`" in strip_paths(execution)


# ----------------------------------------------------------- architect/CLAUDE.md


def architect_rule(number: int) -> str:
    text = read("architect", "CLAUDE.md")
    found = re.search(rf" {number}\. (.*?)(?= {number + 1}\. |$)", text.split("## Rules", 1)[1])
    assert found, f"architect/CLAUDE.md has no rule {number}"
    return found.group(1)


def test_architect_rule_1_says_where_a_review_with_blockers_is() -> None:
    one = architect_rule(1)
    for said in (
        "On a repository whose `main` takes pull requests only (DESIGN §45), a review"
        " with blockers is on the mission's branch, not on `main`",
        "`git -C ./repo show origin/<branch>:meta/reviews/REVIEW-N.md`, the form the"
        " guard allows",
        "on any other repository it is on `origin/BRANCH`, as above",
    ):
        assert said in strip_paths(one), f"architect rule 1 does not say {said!r}"


def test_architect_rule_3_keeps_the_gate_green_and_carries_plan_files_only() -> None:
    three = architect_rule(3)
    for said in (
        "On a repository whose `main` takes pull requests only (DESIGN §45)",
        "a kit keeps the gate green",
        "its apply merges only on green checks and nothing bypasses the gate",
        "it never rewords design text a test pins",
        "the new wording goes in the kit's own section, and the mission's units move"
        " the code, its copies and the pinning tests to it",
        # §46 "H-083": the sentence that replaces the `.github/` clause, word for word.
        "Its files are plan files only: KIT.md, DESIGN.md, WORKPLAN.md, a"
        " decisions-<name>.md at the root, and Markdown files under meta/ that no send"
        " rule's prompt names; the engine approves no other kit, which waits for the"
        " human (DESIGN §46). When the next step needs any other file — code, tests,"
        " configuration, the CI, the playbook or the review protocol — do not put it"
        " in a kit: escalate (rule 8), naming the file.",
    ):
        assert said in strip_paths(three), f"architect rule 3 does not say {said!r}"
    for gone in ("unless the human asked for it", "(the next brief or run plan",
                 "and a kit that carries it waits for the human."):
        assert gone not in strip_paths(three), f"architect rule 3 still says {gone!r}"
    assert "a kit that would need a file other than a plan file (rule 3)" in strip_paths(
        architect_rule(8)
    )


# --------------------------------------------------------------------- handbook


def test_handbook_section_3_quotes_the_pull_request_apply_prompt_word_for_word() -> None:
    raw = HANDBOOK.read_text(encoding="utf-8")
    three = raw.split("\n## 3.", 1)[1].split("\n## 4.", 1)[0]
    after = three.split('Under `[repository] main = "pull-request"`', 1)[1]
    block = after.split("\n\n", 2)[1]
    assert all(line.startswith("    ") for line in block.splitlines()), block
    assert flat(block) == kit_mod.PULL_REQUEST_APPLY


def test_handbook_section_3_names_the_branch_the_body_the_subject_and_the_ci_kit() -> None:
    three = handbook_section("## 3. Kit anatomy")
    for said in (
        "`{branch}` is `kit/<stem>-<hash>`",
        "the first 12 hexadecimal digits of the zip's sha256",
        "`{body}` is `Kit <file name> (sha256 <the whole digest>), applied by hands"
        " (DESIGN §45): it {touched}.`",
        "`{subject}` is `merge: kit <stem> (PR #<pr>)`",
        "`hands kit check` prints the kit's sha256",
        "A resume of an apply",
        "re-sends the apply's own prompt",
        "A kit must leave the gate green",
        "never rewords design text a test pins",
        # §46 "H-083": the plan-files rule replaces §45's CI hold; the architect's
        # own rule on `.github/` and `scripts/check` stays.
        "apply <name>: the kit carries <path>, which is not a plan file; the engine"
        " approves plan files only (KIT.md, DESIGN.md, WORKPLAN.md, decisions files at"
        " the root, Markdown under meta/ that no send rule's prompt names), and any"
        " other file is the owner's (§46)",
        "`WARN owner:`",
        "no file under `.github/` and no `scripts/check` unless the human asked for it",
    ):
        assert said in strip_paths(three), f"handbook §3 does not say {said!r}"


def test_handbook_section_9_says_what_moves_main_the_review_on_the_branch_and_the_waits() -> None:
    nine = handbook_section("## 9. ")
    assert "### A `main` that takes pull requests only (DESIGN §45)" in strip_paths(nine)
    for said in (
        "every one of five commits",
        "the review's file is committed to the mission's branch",
        "`hands ci-wait <number>`",
        "`the merge was not made: <the command's last line>`",
        "A clean verdict always means a merged mission",
        "`journal: <consultation>`",
        "`journal: consultation lines`",
        "a direct mission on a `main` that takes pull requests only",
        "`main`'s rules could not be read",
    ):
        assert said in strip_paths(nine), f"handbook §9 does not say {said!r}"


def test_handbook_section_10_has_the_apply_that_did_not_land() -> None:
    ten = HANDBOOK.read_text(encoding="utf-8").split("\n## 10.", 1)[1].split("\n## 11.", 1)[0]
    row = next(r for r in rows_of(ten) if "apply did not land" in r)
    for said in ("the job's `result`", "`pr=<n>`", "§19"):
        assert said in strip_paths(row), f"§10's row does not say {said!r}"


def test_handbook_section_12_gives_the_order_a_project_switches_in() -> None:
    twelve = handbook_section("## 12. Onboarding a project")
    switching = twelve.split("**A project switching `main` to pull requests only", 1)[1]
    order = [
        "the CI workflow on `main`, its check green on a pull request",
        '`[repository] main = "pull-request"` and a restart of the project\'s `handsd`',
        "docs/PR-CI-GATE.md's procedure, requiring the CI workflow's check only",
    ]
    at = [switching.index(said) for said in order]
    assert at == sorted(at), at
    assert "no job of the project running, queued or held" in strip_paths(switching)


def test_handbook_section_18_names_ci_wait_and_its_exits() -> None:
    eighteen = handbook_section("## 18. Reading hands")
    for said in (
        "`hands ci-wait <pr> [--check <name>]…`",
        "`0` passed",
        "`1` failed",
        "`3` still waiting",
        "`2` no check to wait for",
        "nine minutes",
        "`ci-wait: passed | failed: <name> | waiting: <names> | error: <reason>`",
    ):
        assert said in strip_paths(eighteen), f"handbook §18 does not say {said!r}"


def test_handbook_section_19s_apply_row_reads_the_checks_with_ci_wait_and_gh() -> None:
    nineteen = HANDBOOK.read_text(encoding="utf-8").split("\n## 19.", 1)[1]
    row = next(r for r in rows_of(nineteen) if "the kit's apply did not land" in r)
    for said in (
        "`hands ci-wait <pr>`",
        "`gh pr checks <pr>`",
        "`gh run rerun <run> --failed`",
        "`gh pr merge <pr> --merge --delete-branch --subject",
        "`gh pr close <pr>`",
        "`go <secret>`",
        "`hands go`",
    ):
        assert said in strip_paths(row), f"§19's apply row does not say {said!r}"


def test_handbook_section_19s_review_with_blockers_row_gives_both_git_show_forms() -> None:
    nineteen = HANDBOOK.read_text(encoding="utf-8").split("\n## 19.", 1)[1]
    row = next(r for r in rows_of(nineteen) if "Mission <n> review has blockers" in r)
    for said in (
        "`git show origin/<branch>:meta/reviews/REVIEW-<n>.md`",
        "`git fetch --depth 1 origin <branch>`",
        "`git show FETCH_HEAD:meta/reviews/REVIEW-<n>.md`",
    ):
        assert said in strip_paths(row), f"§19's review-with-blockers row does not say {said!r}"


# ----------------------------------------------------- INTEGRATION, OPERATIONS


def test_integrations_config_block_carries_the_repository_key_and_loads(tmp_home: Path) -> None:
    script = tmp_home / "demo-ops" / "watch_monitor.sh"
    script.parent.mkdir()
    script.write_text("#!/bin/sh\nexit 0\n")
    script.chmod(0o755)
    text = (ROOT / "docs" / "INTEGRATION.md").read_text(encoding="utf-8")
    body = text.split("## 3. Write the config")[1].split("Notes that are easy")[0]
    block = textwrap.dedent(
        "\n".join(line for line in body.splitlines() if line.startswith("    "))
    ).replace("<project>", "demo")
    assert "[repository]" in strip_paths(block)
    config = parse_config(tomllib.loads(block), project="demo", path=ROOT / ".hands" / "demo.toml")
    assert config.repository.main == "direct"


def test_integration_says_the_workflow_scope_and_doctors_main_row() -> None:
    text = read("docs", "INTEGRATION.md")
    for said in (
        "GitHub's `workflow` scope",
        "`gh auth refresh -s workflow`",
        "The `main` row (DESIGN §45)",
        "`gh api repos/<owner>/<repo>/rules/branches/main`",
        "`required_status_checks`",
        "`required_linear_history`, `update` or `merge_queue`",
        "docs/PR-CI-GATE.md",
    ):
        assert said in strip_paths(text), f"docs/INTEGRATION.md does not say {said!r}"


def test_operations_has_the_switching_runbook_and_the_quiet_moments_step_3() -> None:
    raw = (ROOT / "docs" / "OPERATIONS.md").read_text(encoding="utf-8")
    assert "\n### Switching `main` to pull requests only\n" in strip_paths(raw)
    runbook = raw.split("\n### Switching `main` to pull requests only\n", 1)[1]
    runbook = flat(runbook.split("\n### ", 1)[0])
    for said in ("docs/PR-CI-GATE.md", "`hands jobs`", '`[repository] main = "pull-request"`',
                 "`systemctl --user restart handsd@<project>`", "`hands doctor`",
                 "Undoing it is the owner's"):
        assert said in strip_paths(runbook), f"the switching runbook does not say {said!r}"
    quiet = flat(raw.split("\n### A quiet moment\n", 1)[1].split("\n### ", 1)[0])
    assert (
        "Under `[repository] main = \"pull-request\"` a commit at rest is a decisions"
        " kit, whose apply goes through its own pull request" in strip_paths(quiet)
    )


def test_the_playbook_doc_says_the_engines_stop_for_an_apply_that_did_not_land() -> None:
    text = read("docs", "PLAYBOOK.md")
    for said in (
        "### An apply that did not land (DESIGN §45)",
        "the kit's apply did not land: <its VERDICT: line cut to 200 characters, or"
        " \"no VERDICT: line\"> (§45)",
        "before any playbook rule",
        "never kept",
    ):
        assert said in strip_paths(text), f"docs/PLAYBOOK.md does not say {said!r}"


def test_the_documents_say_at_rest_is_published_again_after_the_kept_list_changed() -> None:
    """§45 should-fix 1 (H-079): rule 4's "again" is an end kept or replaced after
    the last publication, not only a replaced one."""
    (row,) = [line for line in rows_of(HANDBOOK.read_text(encoding="utf-8"))
              if line.startswith("| `hands: at rest`")]
    again = ("again, with the new list, at the first such moment after the kept list has"
             " changed — an end kept or replaced after the last publication (§45)")
    assert again in strip_paths(row)
    assert "when a kept end is replaced after it" not in strip_paths(row)
    playbook = read("docs", "PLAYBOOK.md")
    for said in ("again, with the new list, at the first such moment after the kept list"
                 " has changed — an end kept or replaced after the last publication",
                 "a restart publishes nothing unless an end was kept after it"):
        assert said in strip_paths(playbook), f"docs/PLAYBOOK.md does not say {said!r}"
    assert "when a kept end is replaced after it" not in strip_paths(playbook)
    operations = read("docs", "OPERATIONS.md")
    for said in ("An end kept after it (a send of yours under the pause) publishes it"
                 " again, with the new list, once nothing runs",
                 "it publishes `at rest` only for an end kept after the mark and not yet"
                 " published"):
        assert said in strip_paths(operations), f"docs/OPERATIONS.md does not say {said!r}"


def test_this_repositorys_claude_md_says_how_main_moves_by_the_setting() -> None:
    text = read("CLAUDE.md")
    assert (
        "`main` moves by merges, and by plan and review commits only while `[repository]"
        " main` is `direct`; branch protection follows docs/PR-CI-GATE.md" in strip_paths(text)
    )
