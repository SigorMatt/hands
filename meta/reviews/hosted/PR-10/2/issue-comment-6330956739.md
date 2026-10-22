<h3>Code Review by Qodo</h3>

<code>🐞 Bugs (0)</code>  <code>📘 Rule violations (1)</code>  <code>🔗 Cross-repo conflicts (0)</code>  <code>📜 Skill insights (0)</code>

<img src="https://www.qodo.ai/wp-content/uploads/2025/11/light-grey-line.svg" height="10%" alt="Grey Divider">

<br/>

<img src="https://img.shields.io/badge/High-634FD1?style=flat-square" height="20px" alt="Action required">

<details>
<summary>  1.  <s>Reviewers can merge unreviewed changes</s> <code>✓ Resolved</code></summary>

<br/>

> <details open>
><summary>Description</summary>
><br/>
>
><pre>
>The moved-branch check compares <b><i>origin/&lt;branch&gt;</i></b> with <b><i>reviewed:</i></b> before the protocol&#x27;s later `git
>pull --ff-only`, which can advance the local branch after that comparison. If someone pushes in that
>interval, the review commit is placed on the unreviewed tip, its push succeeds, and
><b><i>--match-head-commit</i></b> accepts that review commit for the merge.
></pre>
></details>

> <details>
><summary>Code</summary>
><br/>
>
><code>[meta/REVIEW-PROTOCOL.md[R270-272]](https://github.com/SigorMatt/hands/pull/10/files#diff-d136b4ee2cca075a1117349d23c7a4be93a3bd39bc5aaad31471473f17afa8cfR270-R272)</code>
>
>```diff
>+for a `reviewed: none` review — before you commit the file: `git fetch
>+origin`, then `git rev-parse origin/<branch>` must equal the `reviewed:`
>+sha, the whole 40-character sha. When it does not, add a blocker, "the
>```
></details>

> <details>
><summary>Relevance</summary>
><br/>
>
> `●●● Strong`
>
><pre>
>The later pull creates a race that can place the review commit atop unreviewed changes; the merge
>guard cannot detect that parent.
></pre>
>
> <code>ⓘ Recommendations generated based on similar findings in past PRs</code>
></details>

> <details>
><summary>Evidence</summary>
><br/>
>
><pre>
>The new comparison precedes the protocol&#x27;s branch checkout and fast-forward pull. The subsequent
>merge guard matches the review commit, not its reviewed parent, so it cannot detect a tip absorbed
>by that pull.
></pre>
>
> <code>[meta/REVIEW-PROTOCOL.md\[268-278\]](https://github.com/SigorMatt/hands/blob/5a3a5a435d5ee6ff5d34c741548172424802a7f6/meta/REVIEW-PROTOCOL.md/#L268-L278)</code>
> <code>[meta/REVIEW-PROTOCOL.md\[295-301\]](https://github.com/SigorMatt/hands/blob/5a3a5a435d5ee6ff5d34c741548172424802a7f6/meta/REVIEW-PROTOCOL.md/#L295-L301)</code>
> <code>[meta/REVIEW-PROTOCOL.md\[318-329\]](https://github.com/SigorMatt/hands/blob/5a3a5a435d5ee6ff5d34c741548172424802a7f6/meta/REVIEW-PROTOCOL.md/#L318-L329)</code>
></details>

> <details>
><summary>Agent prompt</summary>
><br/>
>
>```
>The issue below was found during a code review. Follow the provided context and guidance below and implement a solution
>
>## Issue description
>The branch can advance between the new reviewed-head comparison and the protocol's subsequent fast-forward pull, allowing an unreviewed commit into the merge.
>
>## Fix Focus Areas
>- meta/REVIEW-PROTOCOL.md[268-278]
>- meta/REVIEW-PROTOCOL.md[295-301]
>- templates/REVIEW-PROTOCOL.md[268-278]
>- templates/REVIEW-PROTOCOL.md[295-301]
>
>## Recommended Fix
>For a branch review, perform the checkout and pull before the final comparison, and require the resulting local HEAD and fetched remote head to equal the full `reviewed:` SHA before making the review commit. Treat a mismatch as the moved-branch blocker; retain the refused-push handling for movement after that check.
>```
> <code>ⓘ Copy this prompt and use it to remediate the issue with your preferred AI generation tools</code>
></details>

<hr/>
</details>


<br/>

<img src="https://img.shields.io/badge/Medium-634FD1?style=flat-square" height="20px" alt="Remediation recommended">

<details>
<summary>  2.  <s>A moved head prevents saving the blocker</s> <code>✓ Resolved</code></summary>

<br/>

> <details open>
><summary>Description</summary>
><br/>
>
><pre>
>The new <b><i>not merged</i></b> path requires a blocker commit on the branch but gives no recovery step if that
>commit&#x27;s push is refused. When the head moves after the review commit was pushed,
><b><i>--match-head-commit</i></b> refuses the merge and the local branch is behind the remote, so pushing the
>required blocker commit is non-fast-forward.
></pre>
></details>

> <details>
><summary>Code</summary>
><br/>
>
><code>[meta/REVIEW-PROTOCOL.md[R331-335]](https://github.com/SigorMatt/hands/pull/10/files#diff-d136b4ee2cca075a1117349d23c7a4be93a3bd39bc5aaad31471473f17afa8cfR331-R335)</code>
>
>```diff
>+A merge that is refused or not made, with or without the `pull_request`
>+rule, is a blocker: add it to `REVIEW-N.md`, "the merge was not made: <the
>+command's last line>", commit it where the review was (to `main` without
>+the rule, to the branch with it) as `review: mission N (not merged)`, push,
>+and reply with that blocker counted. A clean verdict always means a merged
>```
></details>

> <details>
><summary>Relevance</summary>
><br/>
>
> `●● Moderate`
>
><pre>
>The required blocker push can fail after a moved-head refusal, but no close historical precedent
>confirms the team’s disposition.
></pre>
>
> <code>ⓘ Recommendations generated based on similar findings in past PRs</code>
></details>

> <details>
><summary>Evidence</summary>
><br/>
>
><pre>
>The guarded merge explicitly refuses a different head, while the newly generalized failure path
>requires a further commit and push to the branch. The refused-push recovery above it applies only to
>the earlier push of the review&#x27;s commit.
></pre>
>
> <code>[meta/REVIEW-PROTOCOL.md\[268-285\]](https://github.com/SigorMatt/hands/blob/5a3a5a435d5ee6ff5d34c741548172424802a7f6/meta/REVIEW-PROTOCOL.md/#L268-L285)</code>
> <code>[meta/REVIEW-PROTOCOL.md\[295-301\]](https://github.com/SigorMatt/hands/blob/5a3a5a435d5ee6ff5d34c741548172424802a7f6/meta/REVIEW-PROTOCOL.md/#L295-L301)</code>
> <code>[meta/REVIEW-PROTOCOL.md\[318-347\]](https://github.com/SigorMatt/hands/blob/5a3a5a435d5ee6ff5d34c741548172424802a7f6/meta/REVIEW-PROTOCOL.md/#L318-L347)</code>
></details>

> <details>
><summary>Agent prompt</summary>
><br/>
>
>```
>The issue below was found during a code review. Follow the provided context and guidance below and implement a solution
>
>## Issue description
>A moved PR head makes the guarded merge fail, then prevents the protocol from pushing its required `not merged` blocker commit to the stale local branch.
>
>## Fix Focus Areas
>- meta/REVIEW-PROTOCOL.md[331-347]
>- templates/REVIEW-PROTOCOL.md[331-347]
>
>## Recommended Fix
>Specify a recovery path for a refused push of the `not merged` commit: fetch the new branch tip, put the blocker review on that tip without merging, and push it. If that cannot be done, specify how to leave the local branch usable and report the blocker in the reply.
>```
> <code>ⓘ Copy this prompt and use it to remediate the issue with your preferred AI generation tools</code>
></details>

<hr/>
</details>


<details>
<summary>  3.  Sub-agents edit protected mission metadata <code>📘 Rule violation</code> <code>§ Compliance</code></summary>

<br/>

> <details open>
><summary>Description</summary>
><br/>
>
><pre>
>The U0 plan commit modifies <b><i>meta/plan.md</i></b> and <b><i>meta/CHECKPOINT.md</i></b>, despite the mission&#x27;s standing
>constraint that sub-agents must not edit those files. Protected planning state can therefore be
>rewritten by an automated unit, leaving later builders with metadata that does not reflect the
>designated owner&#x27;s checkpoint or plan.
></pre>
></details>

> <details>
><summary>Code</summary>
><br/>
>
><code>[meta/plan.md[R1-4]](https://github.com/SigorMatt/hands/pull/10/files#diff-7b1c6ea9ab4fd6179a8304348a94fbf1fa61cfb6aafed7ec549bcd7b7f8df461R1-R4)</code>
>
>```diff
>+# plan — mission 30 (the gate's follow-up before the switch)
> 
>-Source: meta/BUILDER-29-PROMPT.md, DESIGN v3.28 §45 (with §4, §6, §8, §10,
>-§13, §27, §31, §32, §35, §36, §39, §43, §44), meta/reviews/REVIEW-28.md,
>-meta/findings/FINDINGS.md (H-079, H-080), docs/PR-CI-GATE.md. Branch
>-`mission-29`, created from `main` (f7d61c8, `plan: mission 29 kit (DESIGN
>-v3.28, main by pull requests only)`). Units run in order; each ends with a
>-commit and a push to `mission-29`; the last unit opens the pull request,
>-waits for its `check` check and the hosted review, and returns the tree to
>-`main`. `[x]` = done and pushed, `[b]` = blocked (two failures) or refused.
>+Source: meta/BUILDER-30-PROMPT.md, DESIGN v3.29 §46 (with §43, §45, §35),
>+meta/reviews/REVIEW-29.md, meta/findings/FINDINGS.md (H-081, H-082, H-083;
>```
></details>

> <details>
><summary>Relevance</summary>
><br/>
>
> `●● Moderate`
>
><pre>
>The constraint violation is plausible, but history does not establish whether U0 orchestrator edits
>are exempt from the sub-agent restriction.
></pre>
>
> <code>ⓘ Recommendations generated based on similar findings in past PRs</code>
></details>

> <details>
><summary>Evidence</summary>
><br/>
>
><pre>
>The diff contains additions and removals in both protected metadata files, including the mission
>plan and checkpoint state. The PR&#x27;s U0 plan commit identifies these files as changed, while the
>checklist explicitly prohibits sub-agent modifications to them.
></pre>
>
> <code>Rule 3263089: [Sub-agents must not modify plan/checkpoint metadata files](https://app.qodo.ai/rules/3263089?state=active)</code>
> <code>[meta/plan.md\[1-4\]](https://github.com/SigorMatt/hands/blob/5a3a5a435d5ee6ff5d34c741548172424802a7f6/meta/plan.md/#L1-L4)</code>
> <code>[meta/CHECKPOINT.md\[3-6\]](https://github.com/SigorMatt/hands/blob/5a3a5a435d5ee6ff5d34c741548172424802a7f6/meta/CHECKPOINT.md/#L3-L6)</code>
></details>

> <details>
><summary>Agent prompt</summary>
><br/>
>
>```
>The issue below was found during a code review. Follow the provided context and guidance below and implement a solution
>
>## Issue description
>The PR modifies `meta/plan.md` and `meta/CHECKPOINT.md`, which the compliance rule reserves from sub-agent edits.
>
>## Fix Focus Areas
>- meta/plan.md[1-4]
>- meta/CHECKPOINT.md[3-6]
>
>## Recommended Fix
>Remove the sub-agent-authored changes to `meta/plan.md` and `meta/CHECKPOINT.md`, or move the plan and checkpoint updates into an owner-controlled step that is not performed by a sub-agent.
>```
> <code>ⓘ Copy this prompt and use it to remediate the issue with your preferred AI generation tools</code>
></details>

[Dismiss ↗](https://app.qodo.ai/findings/c0e7b7dc-4f2c-4815-9fa8-ea793a134dc3?action=dismiss&origin=git) | [View ↗](https://app.qodo.ai/findings/c0e7b7dc-4f2c-4815-9fa8-ea793a134dc3)

<hr/>
</details>


<br/>

<img src="https://img.shields.io/badge/Low-634FD1?style=flat-square" height="20px" alt="Informational">

<details>
<summary>  4.  <s>Role kits can overwrite the review protocol by changing its case</s> <code>✓ Resolved</code></summary>

<br/>

> <details open>
><summary>Description</summary>
><br/>
>
><pre>
><b><i>is_plan_file</i></b> excludes a <b><i>meta/*.md</i></b> entry only when it matches a <b><i>send</i></b>-named path in exact case
>(<b><i>entry not in set(named)</i></b>), so <b><i>meta/review-protocol.md</i></b> or <b><i>meta/Review-Protocol.md</i></b> counts as a
>plan file even when the review rule names <b><i>meta/REVIEW-PROTOCOL.md</i></b>. On a case-insensitive builder
>filesystem (macOS default) the apply&#x27;s <b><i>unzip -o</i></b> writes that entry over the real protocol and
>commits it. The engine approves the apply with no human hold, so the role can rewrite the reviewer&#x27;s
>procedure (merge rules, blocker rules). This is the same hole H-077 closed for the playbook by
>casefolding in <b><i>carries_playbook</i></b>.
></pre>
></details>

> <details>
><summary>Code</summary>
><br/>
>
><code>[src/hands/spool.py[R188-190]](https://github.com/SigorMatt/hands/pull/10/files#diff-afef6fe420dcdc67164710839c508470d94b5a42c23284c4d8cbca7fe9a71221R188-R190)</code>
>
>```diff
>+    if entry in PLAN_FILES or PLAN_DECISIONS_RE.fullmatch(entry):
>+        return True
>+    return entry.startswith(PLAN_META) and entry.endswith(".md") and entry not in set(named)
>```
></details>

> <details>
><summary>Relevance</summary>
><br/>
>
> `● Weak`
>
><pre>
>A closely matching case-insensitive protected-file precedent was rejected; exact-case behavior is
>intentional for Linux builders.
></pre>
>
> [PR-#7](https://github.com/SigorMatt/hands/pull/7)
> [PR-#9](https://github.com/SigorMatt/hands/pull/9)
>
> <code>ⓘ Recommendations generated based on similar findings in past PRs</code>
></details>

> <details>
><summary>Evidence</summary>
><br/>
>
><pre>
><b><i>carries_playbook</i></b> casefolds on purpose: FINAL-REPORT-27 records the finding (H-077) that an
>exact-case check let <b><i>playbook.toml</i></b> pass and overwrite the real playbook on a case-insensitive
>filesystem. The new <b><i>is_plan_file</i></b> treats the <b><i>meta/</i></b> + <b><i>.md</i></b> allowlist as the default and compares
>the <b><i>named</i></b> denylist in exact case. <b><i>send_named_paths</i></b> returns the names exactly as the prompt
>spells them (<b><i>named_paths</i></b>), so a differently-cased entry is not excluded. <b><i>_carries_no_owner_entry</i></b>
>then returns True and the engine approves the apply. Exact case is the safe choice for the allowlist
>(it refuses <b><i>Design.md</i></b>), but for the denylist it lets a renamed file through. DESIGN §46 explains
>exact case only in terms of a Linux builder.
></pre>
>
> <code>[src/hands/spool.py\[157-168\]](https://github.com/SigorMatt/hands/blob/5a3a5a435d5ee6ff5d34c741548172424802a7f6/src/hands/spool.py/#L157-L168)</code>
> <code>[src/hands/spool.py\[180-190\]](https://github.com/SigorMatt/hands/blob/5a3a5a435d5ee6ff5d34c741548172424802a7f6/src/hands/spool.py/#L180-L190)</code>
> <code>[src/hands/kit.py\[1377-1391\]](https://github.com/SigorMatt/hands/blob/5a3a5a435d5ee6ff5d34c741548172424802a7f6/src/hands/kit.py/#L1377-L1391)</code>
> <code>[meta/FINAL-REPORT-27.md\[155-155\]](https://github.com/SigorMatt/hands/blob/5a3a5a435d5ee6ff5d34c741548172424802a7f6/meta/FINAL-REPORT-27.md/#L155-L155)</code>
> <code>[DESIGN.md\[4155-4165\]](https://github.com/SigorMatt/hands/blob/5a3a5a435d5ee6ff5d34c741548172424802a7f6/DESIGN.md/#L4155-L4165)</code>
></details>

> <details>
><summary>Agent prompt</summary>
><br/>
>
>```
>The issue below was found during a code review. Follow the provided context and guidance below and implement a solution
>
>## Issue description
>`spool.is_plan_file` excludes a `meta/*.md` entry only when it matches a path a `send` rule's prompt names, in exact case. A kit entry such as `meta/review-protocol.md` therefore passes as a plan file. On a case-insensitive filesystem it overwrites `meta/REVIEW-PROTOCOL.md`, and the engine approves the apply with no human hold. H-077 closed the same hole for the playbook.
>
>## Fix Focus Areas
>- src/hands/spool.py[180-190]
>- src/hands/spool.py[628-639]
>
>## Recommended Fix
>Keep the exact-case allowlist (`KIT.md`, `DESIGN.md`, `WORKPLAN.md`, `decisions-*.md`, `meta/` + `.md`), but test the denylist casefolded: build `folded = {n.casefold() for n in named}` and return False when `entry.casefold() in folded`. Do the same in `Spool.stored_kit_non_plan`, where `judged` is built. Add tests to tests/test_plan_files.py: a kit with `meta/review-protocol.md` (and `meta/Review-Protocol.md`) is held with §46's reason when the review rule names `meta/REVIEW-PROTOCOL.md`, and `kit check`'s `WARN owner:` names it.
>```
> <code>ⓘ Copy this prompt and use it to remediate the issue with your preferred AI generation tools</code>
></details>

<hr/>
</details>



<img src="https://www.qodo.ai/wp-content/uploads/2025/11/light-grey-line.svg" height="10%" alt="Grey Divider">

<!-- qodo-self-review-slot -->


<!-- qodo-context:start -->
<details><summary><strong>Context sources</strong></summary>

<div>&#x274C; Tickets: failed to load — Ticket collection could not establish complete evidence</div>
<div>&#x2705; Compliance rules (platform): <a href="https://app.qodo.ai/rules?state=active&amp;scopes=/SigorMatt/hands/"><code>8 rules</code></a></div>
<details>
<summary>&#x2705; Cross-repo context — <a href="https://app.qodo.ai/management/repositories/77e6b9e3-9009-4fbe-bd8c-e1c4bd92a98f">repo relationships</a></summary>
<div>&nbsp;&nbsp;Explored: <code>repo: <a href="https://github.com/SigorMatt/discotrade/tree/2793514e730b9f06b98d0cede315d788d462609f">SigorMatt/discotrade</a> (sha: 2793514e)</code> — <a href="https://app.qodo.ai/management/relationships?repoId=77e6b9e3-9009-4fbe-bd8c-e1c4bd92a98f&amp;relatedRepoId=f8bc154f-fef0-4515-a253-775ba818fa12&amp;view=table">View relationship</a></div>
</details>
<div>Review mode: <code>Auto: 🧠 Deep</code>: Broad behavioral, workflow, and approval changes create multiple independent defect opportunities.</div>
<!-- qodo-context:end -->
</details>

<img src="https://www.qodo.ai/wp-content/uploads/2025/11/light-grey-line.svg" height="10%" alt="Grey Divider">



<!-- qodo-daily-tip:start -->

<details>
<summary><strong>Tip of the day</strong></summary>

<br/>

<pre>💡 Did you know, you can ask Qodo to dismiss a finding you disagree with, with your reason on record</pre>

<a href="https://docs.qodo.ai/tips-and-tricks">More tips ↗</a> | <a href="https://app.qodo.ai/configurations?tab=display-preferences">Customize Qodo ↗</a> | <a href="https://docs.qodo.ai">Qodo docs ↗</a>

</details>

<img src="https://www.qodo.ai/wp-content/uploads/2025/11/light-grey-line.svg" height="10%" alt="Grey Divider">
<!-- qodo-daily-tip:end -->


<!-- https://github.com/SigorMatt/hands/commit/5a3a5a435d5ee6ff5d34c741548172424802a7f6 -->

<a href="https://www.qodo.ai"><img src="https://www.qodo.ai/wp-content/uploads/2025/03/qodo-logo.svg" width="80" alt="Qodo Logo"></a>