<h3>Code Review by Qodo</h3>

<code>🐞 Bugs (4)</code>  <code>📘 Rule violations (1)</code>  <code>🔗 Cross-repo conflicts (0)</code>  <code>📜 Skill insights (0)</code>

<img src="https://www.qodo.ai/wp-content/uploads/2025/11/light-grey-line.svg" height="10%" alt="Grey Divider">

<br/>

<img src="https://img.shields.io/badge/High-634FD1?style=flat-square" height="20px" alt="Action required">

<details>
<summary>  1.  A review can merge unreviewed commits <code>🐞 Bug</code> <code>≡ Correctness</code></summary>

<br/>

> <details open>
><summary>Description</summary>
><br/>
>
><pre>
>The review protocol waits for checks by pull request number and merges without verifying that the
>head still matches the commit its sub-agents reviewed. If the mission branch advances during the
>review, the review can record the earlier <b><i>headRefOid</i></b> while the later commit passes checks and is
>merged.
></pre>
></details>

> <details>
><summary>Code</summary>
><br/>
>
><code>[templates/REVIEW-PROTOCOL.md[R275-279]](https://github.com/SigorMatt/hands/pull/9/files#diff-1a13ad1e2168d9dd38e2e3f07712fc77e6d7bbef5b55f45f54dbd1737103bfb6R275-R279)</code>
>
>```diff
>+With `pull_request` and `blockers=0`, the review's own commit has started
>+the checks again, so first wait for them — `hands ci-wait <number>; echo
>+"ci-wait-exit=$?"`, one foreground call at a time, again while it exits 3,
>+at most seven calls — and merge only on exit 0, as above (`gh pr merge
>+<number> --merge --subject "merge: mission N (PR #<number>)"`, then `git
>```
></details>

> <details>
><summary>Relevance</summary>
><br/>
>
> `●●● Strong`
>
><pre>
>Merging without pinning or rechecking the reviewed head permits commits added after review to merge
>unreviewed.
></pre>
>
> <code>ⓘ Recommendations generated based on similar findings in past PRs</code>
></details>

> <details>
><summary>Evidence</summary>
><br/>
>
><pre>
>The protocol identifies the reviewed commit as the PR&#x27;s <b><i>headRefOid</i></b>, but both waits use `hands
>ci-wait &lt;number&gt;<b><i> and the merge command supplies no expected head SHA. </i></b>ci_wait` queries checks for
>the PR&#x27;s current head and accepts no SHA argument.
></pre>
>
> <code>[templates/REVIEW-PROTOCOL.md\[46-70\]](https://github.com/SigorMatt/hands/blob/e3756303fbb6dc0a7d21ddd365f7c81357b7fd14/templates/REVIEW-PROTOCOL.md/#L46-L70)</code>
> <code>[templates/REVIEW-PROTOCOL.md\[203-217\]](https://github.com/SigorMatt/hands/blob/e3756303fbb6dc0a7d21ddd365f7c81357b7fd14/templates/REVIEW-PROTOCOL.md/#L203-L217)</code>
> <code>[templates/REVIEW-PROTOCOL.md\[275-283\]](https://github.com/SigorMatt/hands/blob/e3756303fbb6dc0a7d21ddd365f7c81357b7fd14/templates/REVIEW-PROTOCOL.md/#L275-L283)</code>
> <code>[src/hands/cli.py\[197-207\]](https://github.com/SigorMatt/hands/blob/e3756303fbb6dc0a7d21ddd365f7c81357b7fd14/src/hands/cli.py/#L197-L207)</code>
> <code>[src/hands/forge.py\[168-178\]](https://github.com/SigorMatt/hands/blob/e3756303fbb6dc0a7d21ddd365f7c81357b7fd14/src/hands/forge.py/#L168-L178)</code>
></details>

> <details>
><summary>Agent prompt</summary>
><br/>
>
>```
>The issue below was found during a code review. Follow the provided context and guidance below and implement a solution
>
>## Issue description
>The pull-request review can merge a branch head that changed after the reviewed commit was selected.
>## Fix Focus Areas
>- templates/REVIEW-PROTOCOL.md[203-217]
>- templates/REVIEW-PROTOCOL.md[275-283]
>- meta/REVIEW-PROTOCOL.md[275-283]
>## Recommended Fix
>Require the fetched review tip to match the pull request head, recheck that head before accepting checks, and merge with a head-commit match condition. If it changed, stop for another review; update both protocol copies.
>```
> <code>ⓘ Copy this prompt and use it to remediate the issue with your preferred AI generation tools</code>
></details>

[Dismiss ↗](https://app.qodo.ai/findings/774fdc0f-39ba-41cc-8ce2-f710d331c7d6?action=dismiss&origin=git) | [View ↗](https://app.qodo.ai/findings/774fdc0f-39ba-41cc-8ce2-f710d331c7d6)

<hr/>
</details>


<details>
<summary>  2.  Applies from main take the mission-branch path and fail <code>🐞 Bug</code> <code>≡ Correctness</code></summary>

<br/>

> <details open>
><summary>Description</summary>
><br/>
>
><pre>
><b><i>PULL_REQUEST_APPLY</i></b> case (b) treats <b><i>main</i></b> as an in-flight mission branch because it is on
><b><i>origin</i></b>, is not a <b><i>kit/</i></b> branch, and has no MERGED or CLOSED head pull requests. When an apply
>starts on <b><i>main</i></b> between missions, the builder commits and attempts to push there instead of opening
>the kit pull request; protected <b><i>main</i></b> refuses the push, and the resulting <b><i>kit not applied pr=none</i></b>
>reply stops the pipeline through <b><i>_apply_not_landed</i></b>.
></pre>
></details>

> <details>
><summary>Code</summary>
><br/>
>
><code>[src/hands/kit.py[R227-230]](https://github.com/SigorMatt/hands/pull/9/files#diff-c741f63d4fccb12bbfc566ee658f6a10d5d610c9e09e4a336f11292aaa5c1b37R227-R230)</code>
>
>```diff
>+    "(b) On another branch, not a `kit/` one, that is on `origin` (`git ls-remote",
>+    "--exit-code --heads origin <that branch>`) and whose pull requests, if it has",
>+    "any, are all open (`gh pr list --head <that branch> --state all --json state`",
>+    "names none `MERGED` or `CLOSED`), a mission is in flight on it: unzip -o into",
>```
></details>

> <details>
><summary>Relevance</summary>
><br/>
>
> `●●● Strong`
>
><pre>
>Normal apply from main matches case (b), causing a protected-branch push instead of kit pull-request
>creation.
></pre>
>
> <code>ⓘ Recommendations generated based on similar findings in past PRs</code>
></details>

> <details>
><summary>Evidence</summary>
><br/>
>
><pre>
>Case (b) does not exclude <b><i>main</i></b>, while case (c), which creates the kit branch and pull request, is
>reached only when case (b) does not match. The review protocol and builder brief return the tree to
><b><i>main</i></b> after a mission, making it the normal starting state for an apply. The protected-branch
>ruleset refuses a direct push to <b><i>main</i></b>, and the engine&#x27;s <b><i>_apply_not_landed</i></b> treats the resulting
><b><i>kit not applied</i></b> reply as a pipeline stop.
></pre>
>
> <code>[src/hands/kit.py\[222-257\]](https://github.com/SigorMatt/hands/blob/e3756303fbb6dc0a7d21ddd365f7c81357b7fd14/src/hands/kit.py/#L222-L257)</code>
> <code>[src/hands/playbook.py\[2085-2097\]](https://github.com/SigorMatt/hands/blob/e3756303fbb6dc0a7d21ddd365f7c81357b7fd14/src/hands/playbook.py/#L2085-L2097)</code>
> <code>[templates/REVIEW-PROTOCOL.md\[275-286\]](https://github.com/SigorMatt/hands/blob/e3756303fbb6dc0a7d21ddd365f7c81357b7fd14/templates/REVIEW-PROTOCOL.md/#L275-L286)</code>
> <code>[src/hands/kit.py\[222-256\]](https://github.com/SigorMatt/hands/blob/e3756303fbb6dc0a7d21ddd365f7c81357b7fd14/src/hands/kit.py/#L222-L256)</code>
> <code>[docs/ARCHITECT-HANDBOOK.md\[461-469\]](https://github.com/SigorMatt/hands/blob/e3756303fbb6dc0a7d21ddd365f7c81357b7fd14/docs/ARCHITECT-HANDBOOK.md/#L461-L469)</code>
> <code>[docs/ARCHITECT-HANDBOOK.md\[105-125\]](https://github.com/SigorMatt/hands/blob/e3756303fbb6dc0a7d21ddd365f7c81357b7fd14/docs/ARCHITECT-HANDBOOK.md/#L105-L125)</code>
></details>

> <details>
><summary>Agent prompt</summary>
><br/>
>
>```
>The issue below was found during a code review. Follow the provided context and guidance below and implement a solution
>
>## Issue description
>Case (b) of `PULL_REQUEST_APPLY` matches `main` as an in-flight mission branch. An apply started on `main`, the normal state between missions, therefore attempts a direct push to protected `main` instead of creating the kit branch and pull request.
>
>## Fix Focus Areas
>- src/hands/kit.py[222-257]
>- docs/ARCHITECT-HANDBOOK.md[91-128]
>- DESIGN.md[3750-3790]
>
>## Recommended Fix
>Explicitly exclude `main` from case (b), so an apply starting there proceeds through case (c). Update the matching prompt text in DESIGN.md and the handbook, update tests that pin the wording, and add a test asserting that case (b) excludes `main`.
>```
> <code>ⓘ Copy this prompt and use it to remediate the issue with your preferred AI generation tools</code>
></details>

[Dismiss ↗](https://app.qodo.ai/findings/9a353ce0-61e2-4400-a6c3-35ec8bf69897?action=dismiss&origin=git) | [View ↗](https://app.qodo.ai/findings/9a353ce0-61e2-4400-a6c3-35ec8bf69897)

<hr/>
</details>


<br/>

<img src="https://img.shields.io/badge/Medium-634FD1?style=flat-square" height="20px" alt="Remediation recommended">

<details>
<summary>  3.  <s>Stalled checks can exceed the tool timeout</s> <code>✓ Resolved</code></summary>

<br/>

> <details open>
><summary>Description</summary>
><br/>
>
><pre>
><b><i>ci_wait</i></b> starts its nine-minute deadline only after authentication, origin, pull-request and rules
>reads, each of which can consume a subprocess timeout, and it starts a further checks read without
>bounding it by the remaining time. When those commands stall, one foreground call can run well
>beyond the stated nine minutes and exceed the role&#x27;s tool-call timeout before returning a wait or
>error result.
></pre>
></details>

> <details>
><summary>Code</summary>
><br/>
>
><code>[src/hands/cli.py[R232-235]](https://github.com/SigorMatt/hands/pull/9/files#diff-b53aaafe941dad7529e17dc5ad20b86fb13177f2778fbe0547c019ca0c4c8ce4R232-R235)</code>
>
>```diff
>+    deadline = clock() + limit_s
>+    while True:
>+        try:
>+            reported = forge.pr_checks(gh, repo, pr)
>```
></details>

> <details>
><summary>Relevance</summary>
><br/>
>
> `●●● Strong`
>
><pre>
>The deadline excludes setup and fails to bound polling by remaining time, contradicting the
>command’s nine-minute guarantee.
></pre>
>
> [PR-#8](https://github.com/SigorMatt/hands/pull/8)
>
> <code>ⓘ Recommendations generated based on similar findings in past PRs</code>
></details>

> <details>
><summary>Evidence</summary>
><br/>
>
><pre>
>The deadline is set after four setup reads, while forge gives subprocesses a 120-second timeout by
>default; the polling read also uses that default after the deadline has been set. The new command
>promises a nine-minute foreground call.
></pre>
>
> <code>[src/hands/cli.py\[187-190\]](https://github.com/SigorMatt/hands/blob/e3756303fbb6dc0a7d21ddd365f7c81357b7fd14/src/hands/cli.py/#L187-L190)</code>
> <code>[src/hands/cli.py\[217-257\]](https://github.com/SigorMatt/hands/blob/e3756303fbb6dc0a7d21ddd365f7c81357b7fd14/src/hands/cli.py/#L217-L257)</code>
> <code>[src/hands/forge.py\[23-24\]](https://github.com/SigorMatt/hands/blob/e3756303fbb6dc0a7d21ddd365f7c81357b7fd14/src/hands/forge.py/#L23-L24)</code>
> <code>[src/hands/forge.py\[52-66\]](https://github.com/SigorMatt/hands/blob/e3756303fbb6dc0a7d21ddd365f7c81357b7fd14/src/hands/forge.py/#L52-L66)</code>
> <code>[src/hands/forge.py\[90-95\]](https://github.com/SigorMatt/hands/blob/e3756303fbb6dc0a7d21ddd365f7c81357b7fd14/src/hands/forge.py/#L90-L95)</code>
></details>

> <details>
><summary>Agent prompt</summary>
><br/>
>
>```
>The issue below was found during a code review. Follow the provided context and guidance below and implement a solution
>
>## Issue description
>The nine-minute limit excludes setup subprocesses and the final checks subprocess, so a stalled call can outlast its foreground tool timeout.
>## Fix Focus Areas
>- src/hands/cli.py[217-257]
>- src/hands/forge.py[52-59]
>- src/hands/forge.py[90-95]
>## Recommended Fix
>Start the deadline before setup and pass the remaining time as a timeout to every blocking subprocess, including the final poll. Return an appropriate waiting or error result when no time remains.
>```
> <code>ⓘ Copy this prompt and use it to remediate the issue with your preferred AI generation tools</code>
></details>

<hr/>
</details>


<details>
<summary>  4.  <s>Test subprocesses can hang indefinitely</s> <code>✓ Resolved</code></summary>

<br/>

> <details open>
><summary>Description</summary>
><br/>
>
><pre>
>The new test fixtures invoke <b><i>git</i></b> and <b><i>gh</i></b> through <b><i>subprocess.run</i></b> without an explicit timeout. A
>stalled local tool can block the test suite indefinitely, including repository setup in
><b><i>tests/test_ci_wait.py</i></b> and <b><i>tests/test_doctor.py</i></b>.
></pre>
></details>

> <details>
><summary>Code</summary>
><br/>
>
><code>[tests/test_ci_wait.py[R47-51]](https://github.com/SigorMatt/hands/pull/9/files#diff-36b7a4554465cfd4b0a4732939dec54773485e077f026a2d7d9c98ee7ed82e0dR47-R51)</code>
>
>```diff
>+    subprocess.run(["git", "init", "-q", str(root)], check=True)
>+    subprocess.run(
>+        ["git", "-C", str(root), "remote", "add", "origin", "https://github.com/o/r.git"],
>+        check=True,
>+    )
>```
></details>

> <details>
><summary>Relevance</summary>
><br/>
>
> `●●● Strong`
>
><pre>
>Added synchronous subprocess calls lack required explicit timeouts under the repository’s active
>compliance rule.
></pre>
>
> <code>ⓘ Recommendations generated based on similar findings in past PRs</code>
></details>

> <details>
><summary>Evidence</summary>
><br/>
>
><pre>
>Compliance rule 3263087 requires synchronous process calls to have explicit timeouts. The added test
>subprocess calls shown in these files use <b><i>subprocess.run</i></b> without any <b><i>timeout</i></b> argument, while the
>production calls and wheel-build helper do provide timeouts.
></pre>
>
> <code>Rule 3263087: [Do not start background processes; run with explicit timeouts in foreground](https://app.qodo.ai/rules/3263087?state=active)</code>
> <code>[tests/test_ci_wait.py\[47-51\]](https://github.com/SigorMatt/hands/blob/e3756303fbb6dc0a7d21ddd365f7c81357b7fd14/tests/test_ci_wait.py/#L47-L51)</code>
> <code>[tests/test_ci_wait.py\[186-188\]](https://github.com/SigorMatt/hands/blob/e3756303fbb6dc0a7d21ddd365f7c81357b7fd14/tests/test_ci_wait.py/#L186-L188)</code>
> <code>[tests/test_doctor.py\[3580-3581\]](https://github.com/SigorMatt/hands/blob/e3756303fbb6dc0a7d21ddd365f7c81357b7fd14/tests/test_doctor.py/#L3580-L3581)</code>
></details>

> <details>
><summary>Agent prompt</summary>
><br/>
>
>```
>The issue below was found during a code review. Follow the provided context and guidance below and implement a solution
>
>## Issue description
>Several new test subprocess calls omit explicit timeouts, so a stalled `git` or fake `gh` process can hang the quality gate indefinitely.
>
>## Fix Focus Areas
>- tests/test_ci_wait.py[47-51]
>- tests/test_ci_wait.py[186-188]
>- tests/test_ci_wait.py[369-381]
>- tests/test_doctor.py[3580-3581]
>
>## Recommended Fix
>Add a bounded `timeout` argument to every new `subprocess.run` call, using a short test-appropriate limit and preserving the existing assertions and error handling.
>```
> <code>ⓘ Copy this prompt and use it to remediate the issue with your preferred AI generation tools</code>
></details>

<hr/>
</details>


<details>
<summary>  5.  A missing pull request hides its review <code>🐞 Bug</code> <code>≡ Correctness</code></summary>

<br/>

> <details open>
><summary>Description</summary>
><br/>
>
><pre>
>The no-open-PR branch of the review protocol writes a blocker file but, under <b><i>pull_request</i></b>,
>explicitly commits it nowhere even if the mission branch exists. When that blocker stops the
>pipeline, the architect is instructed to read the review from the mission branch, where the file is
>absent.
></pre>
></details>

> <details>
><summary>Code</summary>
><br/>
>
><code>[templates/REVIEW-PROTOCOL.md[R64-65]](https://github.com/SigorMatt/hands/pull/9/files#diff-1a13ad1e2168d9dd38e2e3f07712fc77e6d7bbef5b55f45f54dbd1737103bfb6R64-R65)</code>
>
>```diff
>+  it as below, and reply with `blockers=1 should-fix=0`. With `pull_request`
>+  it is committed nowhere: `main` refuses it, and the branch may not exist.
>```
></details>

> <details>
><summary>Relevance</summary>
><br/>
>
> `●●● Strong`
>
><pre>
>The documented no-PR path leaves the blocker unavailable where the architect is instructed to read
>it.
></pre>
>
> <code>ⓘ Recommendations generated based on similar findings in past PRs</code>
></details>

> <details>
><summary>Evidence</summary>
><br/>
>
><pre>
>The new no-PR instruction says the file is committed nowhere, whereas the unreadable-rules path
>explicitly permits a commit to an existing mission branch. The handbook&#x27;s blocker route directs the
>architect to read that file from <b><i>origin/&lt;branch&gt;</i></b>.
></pre>
>
> <code>[templates/REVIEW-PROTOCOL.md\[26-35\]](https://github.com/SigorMatt/hands/blob/e3756303fbb6dc0a7d21ddd365f7c81357b7fd14/templates/REVIEW-PROTOCOL.md/#L26-L35)</code>
> <code>[templates/REVIEW-PROTOCOL.md\[61-65\]](https://github.com/SigorMatt/hands/blob/e3756303fbb6dc0a7d21ddd365f7c81357b7fd14/templates/REVIEW-PROTOCOL.md/#L61-L65)</code>
> <code>[docs/ARCHITECT-HANDBOOK.md\[1159-1161\]](https://github.com/SigorMatt/hands/blob/e3756303fbb6dc0a7d21ddd365f7c81357b7fd14/docs/ARCHITECT-HANDBOOK.md/#L1159-L1161)</code>
></details>

> <details>
><summary>Agent prompt</summary>
><br/>
>
>```
>The issue below was found during a code review. Follow the provided context and guidance below and implement a solution
>
>## Issue description
>A no-pull-request blocker review is not committed even when its mission branch exists, leaving the architect's documented read path empty.
>## Fix Focus Areas
>- templates/REVIEW-PROTOCOL.md[61-65]
>- meta/REVIEW-PROTOCOL.md[61-65]
>## Recommended Fix
>Check whether the named mission branch exists and commit the blocker review there when it does, as the unreadable-rules path already directs. Specify a usable handoff when no branch exists.
>```
> <code>ⓘ Copy this prompt and use it to remediate the issue with your preferred AI generation tools</code>
></details>

[Dismiss ↗](https://app.qodo.ai/findings/d54b3307-ca23-48e9-854a-abaab34fecee?action=dismiss&origin=git) | [View ↗](https://app.qodo.ai/findings/d54b3307-ca23-48e9-854a-abaab34fecee)

<hr/>
</details>


<details><summary><ins><strong>View medium (2)</strong></ins></summary><br/>
<details>
<summary>  6.  Kits can still weaken the gate their PR merges on <code>🐞 Bug</code> <code>⛨ Security</code></summary>

<br/>

> <details open>
><summary>Description</summary>
><br/>
>
><pre>
><b><i>carries_ci</i></b> only treats an entry as CI when its casefolded path begins with <b><i>.github/</i></b> or equals
><b><i>scripts/check</i></b>. The gate that <b><i>scripts/check</i></b> runs (<b><i>uv sync</i></b>, <b><i>ruff check .</i></b>, <b><i>pytest</i></b>) is also
>configured by <b><i>pyproject.toml</i></b>, <b><i>uv.lock</i></b> and <b><i>tests/conftest.py</i></b>. An architect-filed kit that
>changes one of those files (for example pytest <b><i>addopts</i></b>, a conftest that deselects tests, or ruff
>excludes) is still approved by the engine without a human hold, and its own pull request&#x27;s check
>then runs the weakened gate it merges on, which is the exact risk §45&#x27;s hold is meant to close.
></pre>
></details>

> <details>
><summary>Code</summary>
><br/>
>
><code>[src/hands/spool.py[R173-183]](https://github.com/SigorMatt/hands/pull/9/files#diff-afef6fe420dcdc67164710839c508470d94b5a42c23284c4d8cbca7fe9a71221R173-R183)</code>
>
>```diff
>+CI_PREFIX = ".github/"
>+#: …and so does the gate script every hands brief names.
>+CI_GATE = "scripts/check"
>+
>+
>+def carries_ci(entry: str) -> bool:
>+    """§45: the one test of whether a kit entry carries the repository's CI — its
>+    path, casefolded, begins `.github/` or equals `scripts/check`. The engine's hold
>+    (`Spool.stored_kit_ci`) and `hands kit check`'s `WARN ci:` line ask this."""
>+    folded = entry.casefold()
>+    return folded.startswith(CI_PREFIX) or folded == CI_GATE
>```
></details>

> <details>
><summary>Relevance</summary>
><br/>
>
> `●●● Strong`
>
><pre>
>Gate configuration files can alter the checks that approve their own merge, matching the stated
>security rationale.
></pre>
>
> [PR-#7](https://github.com/SigorMatt/hands/pull/7)
>
> <code>ⓘ Recommendations generated based on similar findings in past PRs</code>
></details>

> <details>
><summary>Evidence</summary>
><br/>
>
><pre>
><b><i>scripts/check</i></b> runs <b><i>uv sync --extra dev</i></b>, <b><i>uv run ruff check .</i></b> and <b><i>uv run pytest</i></b>, so its
>behaviour depends on the project and test configuration in the kit&#x27;s own branch.
><b><i>_carries_no_owner_entry</i></b> holds a kit only when <b><i>stored_kit_ci</i></b> (that is, <b><i>carries_ci</i></b>) names an
>entry, so changes to those other files are auto-approved. The handbook text added in this PR states
>the rationale: a PR&#x27;s check runs the gate script from its own branch, so a kit that rewrote it could
>weaken its own check.
></pre>
>
> <code>[scripts/check\[1-22\]](https://github.com/SigorMatt/hands/blob/e3756303fbb6dc0a7d21ddd365f7c81357b7fd14/scripts/check/#L1-L22)</code>
> <code>[src/hands/spool.py\[171-183\]](https://github.com/SigorMatt/hands/blob/e3756303fbb6dc0a7d21ddd365f7c81357b7fd14/src/hands/spool.py/#L171-L183)</code>
> <code>[src/hands/playbook.py\[2558-2597\]](https://github.com/SigorMatt/hands/blob/e3756303fbb6dc0a7d21ddd365f7c81357b7fd14/src/hands/playbook.py/#L2558-L2597)</code>
> <code>[docs/ARCHITECT-HANDBOOK.md\[147-162\]](https://github.com/SigorMatt/hands/blob/e3756303fbb6dc0a7d21ddd365f7c81357b7fd14/docs/ARCHITECT-HANDBOOK.md/#L147-L162)</code>
></details>

> <details>
><summary>Agent prompt</summary>
><br/>
>
>```
>The issue below was found during a code review. Follow the provided context and guidance below and implement a solution
>
>## Issue description
>`carries_ci` treats only `.github/` and `scripts/check` as the repository's CI. The gate that `scripts/check` runs is also driven by `pyproject.toml` (pytest/ruff config, dependencies), `uv.lock` and `tests/conftest.py`, so a role-filed kit that touches them is engine-approved and can weaken its own PR's check.
>
>## Fix Focus Areas
>- src/hands/spool.py[171-183]
>- src/hands/kit.py[1003-1015]
>- docs/ARCHITECT-HANDBOOK.md[147-162]
>
>## Recommended Fix
>Extend `carries_ci` to also match (casefolded) `pyproject.toml`, `uv.lock`, any `conftest.py`, and `scripts/` as a whole, or a configurable list. Update the hold reason text, the handbook and DESIGN wording, and the tests to match.
>```
> <code>ⓘ Copy this prompt and use it to remediate the issue with your preferred AI generation tools</code>
></details>

[Dismiss ↗](https://app.qodo.ai/findings/e5755419-309b-46a9-938e-af25dc3ef73c?action=dismiss&origin=git) | [View ↗](https://app.qodo.ai/findings/e5755419-309b-46a9-938e-af25dc3ef73c)

<hr/>
</details>


<details>
<summary>  7.  Mission metadata breaks its own edit rule <code>📘 Rule violation</code> <code>§ Compliance</code></summary>

<br/>

> <details open>
><summary>Description</summary>
><br/>
>
><pre>
>The PR modifies <b><i>meta/plan.md</i></b> and <b><i>meta/CHECKPOINT.md</i></b> while the updated checkpoint states that
>sub-agents must not edit either file. The U0 metadata changes therefore leave the mission plan and
>checkpoint outside the repository&#x27;s stated authoring constraint.
></pre>
></details>

> <details>
><summary>Code</summary>
><br/>
>
><code>[meta/plan.md[R1-3]](https://github.com/SigorMatt/hands/pull/9/files#diff-7b1c6ea9ab4fd6179a8304348a94fbf1fa61cfb6aafed7ec549bcd7b7f8df461R1-R3)</code>
>
>```diff
>+# plan — mission 29 (a `main` that takes pull requests only)
> 
>-Source: meta/BUILDER-28-PROMPT.md, DESIGN v3.27 §44 (with §6, §10, §19,
>-§31, §32, §33, §36, §38, §39, §43), meta/reviews/REVIEW-27.md,
>-meta/findings/FINDINGS.md (H-077, H-078). Branch `mission-28`, created from
>-`main` (b943019, `plan: mission 28 kit (DESIGN v3.27, a pause that holds
>-the next step)`). Units run in order; each ends with a commit and a push to
>-`mission-28`; the last unit opens the pull request, reads the hosted
>-review, and returns the tree to `main`. `[x]` = done and pushed, `[b]` =
>-blocked (two failures) or refused.
>+Source: meta/BUILDER-29-PROMPT.md, DESIGN v3.28 §45 (with §4, §6, §8, §10,
>```
></details>

> <details>
><summary>Relevance</summary>
><br/>
>
> `●●● Strong`
>
><pre>
>The finding identifies a direct violation of an explicit active metadata-authoring constraint.
></pre>
>
> <code>ⓘ Recommendations generated based on similar findings in past PRs</code>
></details>

> <details>
><summary>Evidence</summary>
><br/>
>
><pre>
>Compliance rule 3263089 prohibits sub-agent changes to <b><i>meta/plan.md</i></b> and <b><i>meta/CHECKPOINT.md</i></b>. Both
>files are modified in this PR, and the checkpoint&#x27;s standing constraints explicitly state that
>sub-agents do not edit them.
></pre>
>
> <code>Rule 3263089: [Sub-agents must not modify plan/checkpoint metadata files](https://app.qodo.ai/rules/3263089?state=active)</code>
> <code>[meta/plan.md\[1-10\]](https://github.com/SigorMatt/hands/blob/e3756303fbb6dc0a7d21ddd365f7c81357b7fd14/meta/plan.md/#L1-L10)</code>
> <code>[meta/CHECKPOINT.md\[65-70\]](https://github.com/SigorMatt/hands/blob/e3756303fbb6dc0a7d21ddd365f7c81357b7fd14/meta/CHECKPOINT.md/#L65-L70)</code>
></details>

> <details>
><summary>Agent prompt</summary>
><br/>
>
>```
>The issue below was found during a code review. Follow the provided context and guidance below and implement a solution
>
>## Issue description
>The PR changes `meta/plan.md` and `meta/CHECKPOINT.md` even though the mission's standing constraints prohibit sub-agents from editing those metadata files.
>
>## Fix Focus Areas
>- meta/plan.md[1-10]
>- meta/CHECKPOINT.md[3-12]
>
>## Recommended Fix
>Have the coordinating process own plan and checkpoint updates, and prevent sub-agent commits from including `meta/plan.md` or `meta/CHECKPOINT.md`; if these changes are required, record them as coordinator-authored changes rather than sub-agent edits.
>```
> <code>ⓘ Copy this prompt and use it to remediate the issue with your preferred AI generation tools</code>
></details>

[Dismiss ↗](https://app.qodo.ai/findings/e744dc6c-a3ae-4860-8a7b-1bd96185240b?action=dismiss&origin=git) | [View ↗](https://app.qodo.ai/findings/e744dc6c-a3ae-4860-8a7b-1bd96185240b)

<hr/>
</details>


</details>

<img src="https://www.qodo.ai/wp-content/uploads/2025/11/light-grey-line.svg" height="10%" alt="Grey Divider">


<!-- qodo-context:start -->
<details><summary><strong>Context sources</strong></summary>

<div>&#x274C; Tickets: failed to load — Ticket collection could not establish complete evidence</div>
<div>&#x2705; Compliance rules (platform): <a href="https://app.qodo.ai/rules?state=active&amp;scopes=/SigorMatt/hands/"><code>8 rules</code></a></div>
<details>
<summary>&#x2705; Cross-repo context — <a href="https://app.qodo.ai/management/repositories/77e6b9e3-9009-4fbe-bd8c-e1c4bd92a98f">repo relationships</a></summary>
<div>&nbsp;&nbsp;Explored: <code>repo: <a href="https://github.com/SigorMatt/discotrade/tree/2166a074711b6af28d6f1f2a9559f42e25bc0778">SigorMatt/discotrade</a> (sha: 2166a074)</code> — <a href="https://app.qodo.ai/management/relationships?repoId=77e6b9e3-9009-4fbe-bd8c-e1c4bd92a98f&amp;relatedRepoId=f8bc154f-fef0-4515-a253-775ba818fa12&amp;view=table">View relationship</a></div>
</details>
<div>Review mode: <code>Auto: 🧠 Deep</code>: Dense cross-cutting logic across CLI, GitHub integration, workflows, and persistence paths.</div>
<!-- qodo-context:end -->
</details>

<img src="https://www.qodo.ai/wp-content/uploads/2025/11/light-grey-line.svg" height="10%" alt="Grey Divider">



<!-- qodo-daily-tip:start -->

<details>
<summary><strong>Tip of the day</strong></summary>

<br/>

<pre>💡 Did you know, you can start a comment with &#x27;qodo&#x27; or &#x27;@qodo&#x27; to chat about any finding</pre>

<a href="https://docs.qodo.ai/tips-and-tricks">More tips ↗</a> | <a href="https://app.qodo.ai/configurations?tab=display-preferences">Customize Qodo ↗</a> | <a href="https://docs.qodo.ai">Qodo docs ↗</a>

</details>

<img src="https://www.qodo.ai/wp-content/uploads/2025/11/light-grey-line.svg" height="10%" alt="Grey Divider">
<!-- qodo-daily-tip:end -->


<!-- https://github.com/SigorMatt/hands/commit/e3756303fbb6dc0a7d21ddd365f7c81357b7fd14 -->

<a href="https://www.qodo.ai"><img src="https://www.qodo.ai/wp-content/uploads/2025/03/qodo-logo.svg" width="80" alt="Qodo Logo"></a>