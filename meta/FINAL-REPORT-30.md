# FINAL-REPORT-30 — mission 30: the gate's follow-up before the switch

VERDICT: mission 30 finished pr=<pr>

Source: meta/BUILDER-30-PROMPT.md, DESIGN v3.29 §46 (with §43, §45, §35),
meta/reviews/REVIEW-29.md, meta/findings/FINDINGS.md (H-081, H-082, H-083;
H-084, H-085 filed by U0). Branch `mission-30`, from main e213c2e. Gate:
`./scripts/check` green three consecutive runs before every unit commit:
5366 tests at U0, 5370 at U1, 5390 at U2, 5459 at U3 (the tip 2a2442e,
three more consecutive green runs before this report's commit).

## 1. What changed (sha per unit)

| Unit | sha | What |
|---|---|---|
| U0 Plan, branch and findings | 4c769fd | `plan:` — plan, checkpoint; H-081, H-082, H-083 decided by §46 and scheduled (U3, U1, U2); H-084 (the review's file on its failure paths, REVIEW-29 should-fix 2) and H-085 (the tree after a failure-path review, should-fix 4) filed, decided and scheduled for U3 |
| U1 Case (b), and the setting's refusal | 16723ad | `PULL_REQUEST_APPLY` case (b) begins "(b) On a branch that is neither `main` nor a `kit/` one, that is on `origin`", the rest unchanged; `[repository] main` read through `config._choice`, any other value of any type refused with `[repository] main must be "direct" or "pull-request", got <the value>` (the value in Python's repr); handbook §3's quotation; H-082 resolved |
| U2 The engine approves plan files only | 8b3aa60 | `spool.is_plan_file(entry, named)` (§46's one test, exact case), `Spool.stored_kit_non_plan`, `Spool.stored_kit_files` (added); `playbook.plan_hold_reason` (§46's reason word for word, §43's winning for a kit that carries the playbook), reached through `kit.send_named_paths` (added; `named_paths` over the `send` rules' prompts of the repository's playbook in force, placeholders ignored) by an import inside the engine's method; `carries_ci`, `stored_kit_ci`, `ci_hold_reason` removed; `hands kit check`'s `WARN owner:` and `--json` `owner_warnings` in place of `WARN ci:` / `ci_warnings`; architect/CLAUDE.md rules 3 and 8; handbook §3, §12, §19; docs/PLAYBOOK.md, docs/INTEGRATION.md, both playbook templates' comments; tests/test_plan_files.py added; H-083 resolved |
| U3 The review merges what it reviewed, its failure paths, a defect blocks | 2a2442e | both review protocols (one text): before the review's commit `git fetch origin` and `origin/<branch>` equal to the whole `reviewed:` sha, else the moved-branch blocker and no merge; a refused push the same blocker with §46's steps (rebase, `review: mission N (branch moved)`, or nothing more with `git rebase --abort`, `git branch -f <branch> origin/<branch>`); `gh pr merge <number> --merge --match-head-commit <sha> --subject …` (the reviewed tip when the review went to `main`, the review's own commit when it went to the branch); `not merged` with or without the `pull_request` rule; a failed rules read's review, and under `pull_request` a missing pull request's, to the brief's branch when `git ls-remote --exit-code --heads origin <branch>` finds it, never `main`, else nowhere; a Direct brief's under `pull_request` nowhere; `## A defect (DESIGN §46)` (the definition and the three cases) and the `## Hosted review` dispositions; `## The end (every shape)`, `git checkout main && git pull --ff-only`; templates/BUILDER-N-PROMPT.md's sentence after the pinned one; handbook §9, §19; tests/test_docs_46.py added; H-081, H-084, H-085 resolved |
| U4 Final report, the pull request, its checks and the hosted review | (this commit), … | this file; the pull request; the `## Hosted review` table, the `## CI` section and the hosted archive |

## 2. What the tests prove

- The `pull-request` apply prompt word for word, built from §45's block
  with §46's case (b) in its place; the phrase "neither `main` nor a
  `kit/` one" present and "another branch" gone. `main = true`, `main = 1`
  and `main = "squash"` each refused naming both values (U1).
- `is_plan_file` on 17 listed paths. On a role-mode autonomous playbook: a
  kit of `KIT.md`, `DESIGN.md`, `meta/BUILDER-31-PROMPT.md` and
  `meta/decisions/x-owner.md`, and kits with `WORKPLAN.md` and
  `decisions-2026-10-21.md` at the root, approved and followed by the
  engine's kickoff; kits each carrying one of `docs/x.md`,
  `.github/workflows/x.yml`, `scripts/check`, `pyproject.toml`, `uv.lock`,
  `tests/conftest.py`, `src/x.py`, `SPEC.md`, `meta/conftest.py`,
  `meta/REVIEW-PROTOCOL.md` (named by the review rule), `Meta/x.md` and
  `Design.md` held with §46's reason naming that path, no engine kickoff
  after the human's approval; the first such path in sorted order named;
  `PLAYBOOK.toml` with `docs/x.md`, and `meta/PLAYBOOK.toml`, held with
  §43's reason; `kit check`'s `WARN owner:` line for a role-mode
  autonomous repository and none for a phone-mode one; §19's new row is
  route 2 then `go`; a phone kit gets no §46 reason (U2).
- Both protocols carry the moved-branch check and blocker, the
  refused-push steps, the `--match-head-commit` merge, `not merged` with
  or without the rule, the failure paths to the branch via `ls-remote` and
  never `main`, the Direct brief's review nowhere, the end on `main`, the
  defect's definition and its three cases; the template and this
  repository's copy agree but for the repository and the timeout; the
  brief template's new sentence follows the intact pinned one; handbook §9
  and §19 carry them (U3).

## 3. NOT PROVEN

- No ruleset exists and this repository's setting is still `direct`, so
  no apply has gone through a pull request under the gate, no builder has
  followed the new case (b) or taken case (c) from `main`, and no review
  has merged with `--match-head-commit` on GitHub; that gh refuses a merge
  whose head moved is taken from §46, not observed.
- No real reviewer has followed the new protocol (moved-branch steps,
  failure paths, the defect rule); the tests pin its text only.
- The engine's plan-files hold is tested at the engine; the daemon path
  (socket, ntfy) with a held non-plan kit is not, nor a builder whose
  working directory is below the repository root when `named` is
  computed.
- The refusal of `[repository] main` is tested for three values (a bool,
  an int, a string), not for every type.

## 4. Deviations and readings

- U1: the refused value is shown in Python's repr (§46 says `<the value>`).
- U2: `kit check`'s playbook in force is the first that loads of the
  configured path, `PLAYBOOK.toml`, `meta/PLAYBOOK.toml`;
  `tests/harness.py`'s `playbookless_kit` no longer carries
  `meta/REVIEW-PROTOCOL.md` (the playbook's review rule names it, so §46
  holds it), and the two end-to-end projects commit it to the repository;
  `ops/rules.toml` at another project's configured path is now held.
- U3: a failed rules read on a Direct brief (branch `main`) commits its
  review nowhere; the end on `main` is one last section the failure paths
  point to. architect/CLAUDE.md rule 1 and handbook §7's list of blockers
  are outside §46's "Documentation" list and are unchanged: rule 1 still
  says a review with blockers is on the branch only under `pull_request`,
  and §7's list does not name a confirmed defect.

## Review items

- REVIEW-29 should-fix 1: closed by U1 16723ad (H-082), U2 8b3aa60
  (H-083) and U3 2a2442e (H-081).
- REVIEW-29 should-fix 2: closed by U3 2a2442e (H-084).
- REVIEW-29 should-fix 3: closed by U1 16723ad.
- REVIEW-29 should-fix 4: closed by U3 2a2442e (H-085).
- H-081, H-084, H-085: resolved by U3; H-082 by U1; H-083 by U2.
