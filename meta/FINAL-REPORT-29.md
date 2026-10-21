# FINAL-REPORT-29 — mission 29: a `main` that takes pull requests only

VERDICT: mission 29 finished pr=9

Source: meta/BUILDER-29-PROMPT.md, DESIGN v3.28 §45 (with §4, §6, §8, §10,
§13, §27, §31, §32, §35, §36, §39, §43, §44), meta/reviews/REVIEW-28.md,
meta/findings/FINDINGS.md (H-079, H-080), docs/PR-CI-GATE.md. Branch
`mission-29`, from main f7d61c8. Gate: `./scripts/check` green three
consecutive runs before every unit commit: 5137 tests at U0, 5143 at U1,
5216 at U2, 5237 at U3, 5274 at U4, 5353 at U5, 5357 at U6 (the tip
7e0914e), 5357 at b3f5b91 and 5366 at e375630 (the last code commit,
three consecutive green runs), and the bare-environment run (U1's `env -i`,
a fresh home) green once at 7e0914e (5354 passed, 3 skipped). The pull
request's `check` check passed on GitHub's runner at b3f5b91 and e375630.

## 1. What changed (sha per unit)

| Unit | sha | What |
|---|---|---|
| U0 Plan, branch and findings | 616f7e1 | `plan:` — plan, checkpoint; H-079 filed ("decided (DESIGN §45 ...), scheduled for U6"); H-080 filed ("decided (DESIGN §45 ...), scheduled for U4") |
| U1 CI on GitHub's runner | 624aff0 | `.github/workflows/check.yml` added: `./scripts/check` on `pull_request` and `push` to `main`, one job `check` (id and name), `ubuntu-latest`, `permissions: contents: read`, a per-ref `concurrency` group cancelling a superseded run, `timeout-minutes: 30`, `actions/checkout@3d3c42e…` (v7.0.1) and `astral-sh/setup-uv@1c37ad0…` (v10.3.0) pinned by full sha read with `git ls-remote`, Python 3.11; an autouse fixture in `tests/conftest.py` sets the proxies to `http://127.0.0.1:9` with `NO_PROXY=localhost,127.0.0.1`; the 12 doctor `--live` architect tests that published to the public ntfy now publish to a local stub; three wheel-build tests skip when uv's cache holds no hatchling (the suite is offline); tests/test_ci.py added |
| U2 The setting, `hands ci-wait`, doctor's `main` row | db5c000 | `[repository] main` (`direct` default, any other value refused naming the two); `src/hands/forge.py` added (owner/repo of a github.com `origin` in https/ssh form, a branch's effective rules, the required checks, a pull request's checks with gh's "no checks reported" read as none yet); `hands ci-wait <pr> [--check <name>]…` (exits 0/1/3/2, per-check lines, last line; nine-minute limit, 30 s interval, clock injectable); doctor's `main` row (ok, the four WARNs, skipped naming why); templates/config.toml; tests/fake_gh.py rules and checks; tests/test_ci_wait.py added |
| U3 The apply by the setting, and its resume | cd0e13f | `apply_prompt`/`plan_apply` take the shape and the zip's sha256; the `direct` prompt with the one added sentence; the `pull-request` prompt word for word (its wrapped lines joined by single spaces), `kit/<stem>-<12 hex>`, the body and subject; the phone's `kit`, `hands kit apply` and `hands kit file` use the daemon's setting; `kit check` prints the sha256 and the shape's prompt, saying which; a resume of an apply (orphaned, failed, limited) re-sends its own prompt found by §43's chain walk, never `resume_line`; §32's approved-apply test asked of the chain's first job; handbook §3's `direct` quotation; tests/test_apply_shape.py added |
| U4 An apply that did not land, the CI's hold, the journal sentence | 39e7976 | an apply's `builder.done` not beginning `VERDICT: kit applied` is the engine's stop before any rule (`the kit's apply did not land: … (§45)`), published once over a paused pipeline, never kept, never replacing a kept end; `spool.carries_ci` (casefolded `.github/` prefix or `scripts/check`) holds a role-filed kit with §45's reason (§43's when it carries the playbook too); `kit check`'s `WARN ci:`; the `pull-request` journal sentence; handbook §19 rows (the apply that did not land; the CI hold) with the operator table's pins; H-080 resolved; tests/test_apply_not_landed.py added |
| U5 The review protocol, the brief template, the architect, the documents | 897ec34 | both review protocols (the rules read first, retried once, the failure's blocker; under `pull_request` the Direct blocker, `reviewed: none` committed nowhere, the checks wait at the reviewed tip, review and archive on the branch, the merge's wait and `not merged` blocker, the return to `main`, the journal carried over; the `.github/`/`scripts/check` blocker); templates/BUILDER-N-PROMPT.md; architect/CLAUDE.md rules 1 and 3; handbook §3, §9, §10, §12, §18, §19; docs/INTEGRATION.md, docs/OPERATIONS.md, docs/PLAYBOOK.md, CLAUDE.md; tests/test_docs_45.py added |
| U6 At rest after the kept list changed | 7e0914e | a `kept_since_rest` flag in `pipeline.json`, set when an end is kept or replaced after the at-rest mark; `hands: at rest` published again with the new list at the next moment nothing runs; a restart publishes only a change never published; the §19 `at rest` row, docs/PLAYBOOK.md, docs/OPERATIONS.md; H-079 resolved |
| U7 Final report, the pull request, its checks and the hosted review | 9fa853c, b3f5b91, e375630, (this commit) | this file (9fa853c); PR #9; `tests:` b3f5b91 (the first CI run failed one test on the runner's Python 3.11, whose `zipfile` does not read the Unicode Path Extra Field that 3.12+ honours; hands' own kit check reads the field itself and was safe on 3.11, so the test now asserts `ZipInfo.filename` per Python version); `cli:` e375630 (hosted findings 3, 4: `ci-wait`'s nine minutes count from the call's start and every read is bounded by the time left; explicit timeouts on the new tests' `git`/`gh` calls); H-081, H-082, H-083 filed; the `## Hosted review` table, the `## CI` section and the archive meta/reviews/hosted/PR-9/1..2 (this commit) |

## 2. What the tests prove

- The workflow's text: both triggers, the job id and name `check`,
  `./scripts/check` as its run step, the permissions, the timeout, every
  `uses:` pinned to a 40-hexadecimal sha (red with a tag pin); a request to
  another host fails at once under the suite's proxy fixture (red without
  it) (U1).
- `[repository] main`: the default `direct`, both values, a third refused
  naming the two. `hands ci-wait` with the rules requiring `check`: `pass`
  and `skipping` → 0, `fail` and `cancel` → 1, pending or not reported at
  the limit → 3 (gh 2.89's "no checks reported" as none yet), another check
  deciding nothing; with no rules, `--check check` waited for by name and
  no `--check` → 2; no `gh`, not signed in, an unknown pull request → 2;
  the per-check lines and last line of each outcome. Doctor's `main` row ok
  for `direct`/no rules and `pull-request`/both rules, a WARN for each of
  §45's four disagreements, skipped naming why for no `gh`, no sign-in, a
  non-github.com `origin` and a failed read; `owner/repo` from the three
  URL forms (U2).
- The `direct` apply prompt with exactly the added sentence; the
  `pull-request` prompt word for word for `a b.c.zip`, a long stem cut to
  40, and other bytes under the same name giving another branch; the
  phone's `kit`, `hands kit apply` and `hands kit file` filing it under
  `pull-request`; `kit check`'s sha256 and prompt with and without a
  configuration and for a directory kit; an orphaned, a failed and a
  limited apply each resumed with its own prompt under a `resume_line`; a
  limited kickoff resumed with `resume_line`; an engine-approved apply
  orphaned, resumed and landing followed by the engine's kickoff (U3).
- An apply ending `VERDICT: kit not applied …` stops with §45's reason
  under this repository's playbook (no driver consulted) and under a
  role-mode autonomous playbook (no kickoff); no `VERDICT:` line named; a
  resumed apply's failed end stops the same way; a landed apply decided as
  before; a `hands send` replying `VERDICT: kit not applied` meets the
  rules only; under a human pause and over a rule's stop it is published
  once with the pause, kept end and stop reason unchanged; kits carrying
  `.github/workflows/x.yml`, `.GitHub/x`, `scripts/check` held with the
  CI's reason and warned, the playbook's reason winning when both, an
  ordinary kit unchanged; the journal sentence's two wordings, both
  stripped by §36's reader (U4).
- The protocols, template, architect rules, handbook and documents carry
  §45's sentences, the rules read before the brief and the journal carried
  over before `git checkout <branch>`; handbook §3 quotes the code's
  `pull-request` prompt; the architect's guard allows `git show
  origin/<branch>:meta/reviews/REVIEW-N.md` (U5).
- `at rest` republished, naming both ends, after a laptop aux send under
  the pause ends; after a replacement; not while a job runs, and at the
  next quiet moment; a restart publishing nothing with no end kept after
  the mark and publishing an unpublished change once (U6).

## 3. NOT PROVEN

- **H-082 (open, high): the `pull-request` apply prompt's case (b), §45
  word for word, matches `main` itself**, so an apply started on `main`
  under `pull-request` would commit there, have its push refused and stop.
  The switch of docs/PR-CI-GATE.md §5 step 2 (`[repository] main =
  "pull-request"`) must wait for the design's decision on H-082.

- No ruleset exists, so no apply has merged through a pull request under
  the gate, and `hands ci-wait` has never read required checks from real
  rules: it has waited only by name (`--check check`) on this pull request.
- Doctor's `main` row has read only this repository's rules, with none set.
- No real builder has followed either apply prompt, and no real aux has
  followed the new review protocol; the phone architect's `git fetch
  --depth 1` from a real shallow clone is untested.
- `gh`'s behaviour beyond what tests/fake_gh.py copies (gh 2.89's "no
  checks reported"; `gh pr checks --json` exiting 0 while checks are
  pending) is taken from §45, not observed here beyond this pull request.
- The engine's stop for an apply that did not land and U6's republication
  are tested at the engine; the daemon path (socket, ntfy) and the order of
  feeding orphans and checking at rest after a restart are not.
- The three wheel-build tests skip offline when uv's cache holds no
  hatchling; whether they run on GitHub's runner is read from the run, not
  proven by a test.

## 4. Deviations and readings

- U1: Python 3.11 on the runner (the minimum `pyproject.toml` allows; §45
  names none).
- U2: `ci-wait` prints nothing until it ends, passes `--repo
  <owner>/<repo>` from `origin` to gh, and never prints the `origin` URL.
- U3: a directory kit that `build_zip` refuses has no sha256 (it fails
  `paths` already); `kit check --json` gains `apply_shape` and `sha256`.
- U4: the stop fires with no playbook file too (the engine's own); under a
  human pause it is recorded as the pause's suppressed stop (§44 rule 2), so
  `resume` rules stop firing until a human `resume`; `kit check --json`
  gains `ci_warnings`.
- U5: a review stopped by unreadable rules or a Direct brief writes
  `reviewed: none` with `blockers=1`; a refused `gh pr merge` takes the
  `not merged` blocker; `ci-wait`'s last line goes in `## Notes` whatever
  its exit.
- U6: a `kept_since_rest` flag beside the mark, not a comparison of
  millisecond timestamps that can tie.

## Review items

- REVIEW-28 should-fix 1: closed by U6 (7e0914e).
- REVIEW-28 should-fix 2: answered by §45 (the reading is the design:
  §10's stop for a playbook that does not load is a stop like any other,
  kept under rule 1); nothing changed.
- H-079: closed by U6 (7e0914e).
- H-080: closed by U4 (39e7976).

## Hosted review

PR #9, qodo-code-review[bot]; Code Review comment 6307244055. Fetch 1 (meta/reviews/hosted/PR-9/1/, at 9fa853c/b3f5b91,
7 of 7 open) and fetch 2 (meta/reviews/hosted/PR-9/2/, at e375630, 5 of 7
open; 3 and 4 marked resolved by the bot).

| # | Finding (verbatim) | Disposition |
|---|---|---|
| 1 | A review can merge unreviewed commits | finding H-081 filed |
| 2 | Applies from main take the mission-branch path and fail | finding H-082 filed |
| 3 | Stalled checks can exceed the tool timeout | fixed in e375630 |
| 4 | Test subprocesses can hang indefinitely | fixed in e375630 |
| 5 | A missing pull request hides its review | dismissed: §45 "The review" says the `reviewed: none` review with no open pull request is committed nowhere, and the reply carries its blocker |
| 6 | Kits can still weaken the gate their PR merges on | finding H-083 filed |
| 7 | Mission metadata breaks its own edit rule | dismissed: the rule binds sub-agents; meta/plan.md and meta/CHECKPOINT.md are the orchestrator's (CLAUDE.md "meta/ is the builder's state") and no sub-agent edited them |

## CI

The check as GitHub reported it at the last code commit, e375630 (`gh api
repos/SigorMatt/hands/commits/<sha>/check-runs`):

| name | app | app id | conclusion | run |
|---|---|---|---|---|
| check | github-actions | 15368 | success | https://github.com/SigorMatt/hands/actions/runs/39545100168/job/119041379824 |

Awaited by name (`uv run hands ci-wait 9 --check check`, no rules on
`main` yet): failed at 9fa853c (run 39537905841, the Python 3.11 zipfile
test), passed at b3f5b91 (run 39540903955) and at e375630. The name
docs/PR-CI-GATE.md will require is `check`, reported by the
`github-actions` app (id 15368).
