# PR-CI-GATE — protect a repository's default branch: pull requests only, CI must pass

**For the human:** give this file to any coding session working in a GitHub repository, with
one line: *"Follow PR-CI-GATE.md for this repository."* To make it standing practice, commit
it as `docs/PR-CI-GATE.md` and add to the project's `CLAUDE.md`: *"Branch protection follows
docs/PR-CI-GATE.md."*

**For the session:** everything you need is in this file. Read it once in full before the
first command. You create one repository ruleset and report. You never push to the default
branch, never merge, and never test the rule by trying a direct push.

Provenance: the ruleset protecting `main` on `SigorMatt/harness-bench` (October 2026),
generalised. It was created through the API and verified there; its pull requests merge
with CI green and zero approvals. Carried into hands by DESIGN §45 (2026-10-20), with the
hosted reviewer's check excluded in step 3 and section 5, for a project hands runs.

---

## 1. What the gate enforces

One repository ruleset on the default branch, with four rules:

| Rule | Effect |
|---|---|
| `pull_request` | Every change lands through a pull request; no direct pushes, for anyone. |
| `required_status_checks` | The pull request's CI checks must pass before it can merge. |
| `non_fast_forward` | No force-pushes to the default branch. |
| `deletion` | The default branch cannot be deleted. |

Defaults, and why:

- **0 required approvals.** GitHub does not let anyone approve their own pull request, so in
  a one-maintainer repository any required approval blocks every merge. Raise it to 1 only
  when the owner says other people review.
- **`require_extra_approval_for_unattributed_changes: false`.** GitHub adds this parameter
  with the value `true` when it is not sent. It is undocumented, and with it on, pull
  requests have shown as BLOCKED with all checks green and 0 required approvals, notably
  for agent-authored commits. Always send it as `false`.
- **No bypass actors.** The rule applies to the owner too. The owner can add a bypass later
  in Settings → Rules; you never add one on your own.
- **Strict status checks off.** A pull request does not have to be rebased on the latest
  default branch before merging. That avoids a rebase per merge in small repositories.
- **`~DEFAULT_BRANCH`** targets whatever the default branch is called and follows renames.

## 2. Rules that do not bend

1. **Read only until step 5.** Discovery uses `gh api` GET calls only.
2. **Never push to the default branch, never force-push, never merge,** and never "test" the
   gate with a push. The first pull request after the gate exists is the test.
3. **Required check names come from check runs GitHub actually reported, never from reading
   workflow YAML.** A check is named after the job's `name:` if it has one, otherwise its
   job id. Matrix jobs report one check per combination (`test (3.12)`), and reusable
   workflows report `caller / callee`. A required name that never reports leaves every
   pull request waiting forever ("Expected — Waiting for status to be reported").
4. **Pin each required check to the app that reported it** (`integration_id`), using the
   app id observed on the check run. Then only that app, normally GitHub Actions, can
   satisfy the check; a commit status posted by anyone with write access cannot.
5. **One gate per repository.** If a ruleset or classic branch protection already covers the
   default branch, change nothing and report it to the owner.
6. **Write files with Python, never with heredocs.**
7. **Stop and ask the owner** whenever this file says so. Never decide by picking a value.

## 3. Procedure

**Step 1 — identify the repository.**

    gh auth status
    gh repo view --json nameWithOwner,defaultBranchRef,visibility,viewerPermission

You need `viewerPermission: ADMIN`; without it, stop and report. Write down
`OWNER/REPO`, the default branch and the visibility.

**Step 2 — look for an existing gate.**

    gh api repos/OWNER/REPO/rulesets
    gh api repos/OWNER/REPO/rules/branches/DEFAULT_BRANCH
    gh api repos/OWNER/REPO/branches/DEFAULT_BRANCH/protection

The last call returns 404 when there is no classic protection; that is the good case. If
any call shows rules already applying to the default branch, stop and report what exists.

**Step 3 — discover the CI checks.**

    gh api "repos/OWNER/REPO/commits/DEFAULT_BRANCH/check-runs?per_page=100" \
      --jq '.check_runs[] | [.name, .app.slug, .app.id, .conclusion] | @tsv'

- Prefer checks that also run on pull requests. Confirm by looking at a recent pull request,
  if one exists: `gh pr list --state all --limit 5`, then `gh pr checks <n>`. A check that
  only runs on `push` never reports on a pull request; do not require it.
- Leave out checks that do not run on every pull request, such as workflows with `paths:`
  filters or jobs gated by `if:` conditions. Required, they block every pull request that
  does not trigger them.
- Never require a hosted reviewer's check (a bot that reviews pull requests, such as
  `qodo-code-review`, if it reports one): its verdict is read by the project's review, not
  by the gate, and a reviewer that is slow or down would block every merge.
- If the default branch has no check runs at all, stop and ask the owner. Either CI is set
  up first, or the gate is created without the `required_status_checks` rule.
- Record each check as a pair: the exact name and the app id. GitHub Actions is usually
  `15368`, but use the value you observed.

**Step 4 — write the ruleset.** With Python, write `/tmp/pr-ci-gate.json`, putting the
discovered checks into `required_status_checks`:

```json
{
  "name": "DEFAULT_BRANCH: pull requests and CI",
  "target": "branch",
  "enforcement": "active",
  "bypass_actors": [],
  "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
  "rules": [
    {"type": "deletion"},
    {"type": "non_fast_forward"},
    {"type": "pull_request", "parameters": {
      "required_approving_review_count": 0,
      "dismiss_stale_reviews_on_push": false,
      "require_code_owner_review": false,
      "require_last_push_approval": false,
      "required_review_thread_resolution": false,
      "require_extra_approval_for_unattributed_changes": false,
      "allowed_merge_methods": ["merge", "squash", "rebase"]}},
    {"type": "required_status_checks", "parameters": {
      "strict_required_status_checks_policy": false,
      "do_not_enforce_on_create": false,
      "required_status_checks": [
        {"context": "CHECK_NAME_1", "integration_id": APP_ID},
        {"context": "CHECK_NAME_2", "integration_id": APP_ID}
      ]}}
  ]
}
```

Replace `DEFAULT_BRANCH` in `name` with the real branch name. If the owner chose to have no
required checks (step 3), leave out the whole `required_status_checks` rule.

**Step 5 — create it.**

    gh api --method POST repos/OWNER/REPO/rulesets --input /tmp/pr-ci-gate.json

If the call fails on a private repository with a message about upgrading the plan, stop
and report: rulesets on private repositories need GitHub Pro, Team or Enterprise.

**Step 6 — verify.**

    gh api repos/OWNER/REPO/rulesets/RULESET_ID
    gh api repos/OWNER/REPO/rules/branches/DEFAULT_BRANCH

Check each of the following, and fix it with step 7 if it is wrong:

- `enforcement` is `active`, and `bypass_actors` is empty;
- `current_user_can_bypass` is `never`;
- the effective rules for the default branch list `deletion`, `non_fast_forward`,
  `pull_request` and, if required, `required_status_checks`;
- `required_approving_review_count` is 0;
- `require_extra_approval_for_unattributed_changes` is `false`;
- the required checks are exactly the discovered names, each with its app id.

**Step 7 — change it later (only when needed).** An update replaces the whole definition,
so send the complete body. Start from the step 4 file, edit it with Python, then:

    gh api --method PUT repos/OWNER/REPO/rulesets/RULESET_ID --input /tmp/pr-ci-gate.json

Switching the gate off (`"enforcement": "disabled"`) or deleting it is the owner's
decision, never yours.

**Step 8 — report** in one short block:

- the ruleset id and its URL, `https://github.com/OWNER/REPO/rules/RULESET_ID`;
- the default branch it covers;
- the rule types in force;
- the required checks, each with its app id;
- anything left to the owner (step 2, 3 or 5 stops).

## 4. Pitfalls that have actually happened, or nearly did

- **The undocumented extra-approval parameter.** It was left at GitHub's default of `true`,
  which risked pull requests that nobody could merge in a one-maintainer repository.
- **Check names taken from YAML.** A job with a `name:`, a matrix or a reusable workflow
  reports under a different name than its job id.
- **Renaming a CI job later.** The required check then never reports, and every pull request
  blocks until the ruleset is updated with the new name (step 7).
- **Requiring a check that runs only on `push`,** or only for some paths.
- **Requiring an approval in a one-maintainer repository.** No one can approve, so nothing
  merges.
- **Testing the gate with a direct push.** That pushes to the default branch if the gate is
  missing or wrong. The first pull request is the test.
- **Adding a bypass "just in case".** It quietly turns the gate into a suggestion.

## 5. For a project hands runs (DESIGN §45)

hands moves a project's `main` itself: a kit's apply commits a plan, the review commits its
file, and the review merges a clean mission. Under this gate every one of those must go
through a pull request, so hands must be told before the gate exists. The order, all of it
with no job of the project running, queued or held (`hands --project <project> jobs`: a
restart kills running jobs, a push in flight to `main` would be refused, and an apply filed
before the switch keeps the prompt it was filed with):

1. **CI first.** A workflow on `main` that runs the project's gate on every pull request and
   on every push to `main`, its check green on at least one pull request. Step 3 reads the
   check's name from those runs.
2. **The setting.** In the project's hands config (`~/.hands/<project>.toml`):

       [repository]
       main = "pull-request"

   then restart the project's daemon (`systemctl --user restart handsd@<project>`). From
   then on a kit's apply goes through a pull request of its own and merges once the checks
   the rules require pass (until step 3 there are none, so an apply stops: make no apply
   between steps 2 and 3), and a mission is always the pull-request shape. hands' doctor row
   `main` warns that `main` is not protected yet.
3. **This procedure**, requiring the CI workflow's check only (never the hosted reviewer's,
   step 3). hands' doctor row `main` is then ok, and the review protocol, which reads the
   default branch's rules itself, commits each review to the mission's branch and merges on
   green checks.

To undo it — the owner's decision, never the session's — the owner disables the ruleset in
Settings → Rules, then sets `main = "direct"` and restarts the daemon, with no apply in
between (with the setting still `pull-request` and no rule to wait for, an apply stops).
