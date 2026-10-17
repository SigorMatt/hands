<img src="https://img.shields.io/badge/Medium-634FD1?style=flat-square" height="20px" alt="Remediation recommended">

3\. Sub-agents alter protected metadata <code>📘 Rule violation</code> <code>§ Compliance</code>

<pre>
<b><i>meta/plan.md</i></b> and <b><i>meta/CHECKPOINT.md</i></b> are changed in the U0 plan unit even though the mission&#x27;s
standing constraint forbids sub-agents from editing them. The protected metadata therefore has a
sub-agent-authored change in this PR, contrary to the repository workflow requirement.
</pre>


<details>
<summary><strong>Agent Prompt</strong></summary>

```
## Issue description
The PR changes `meta/plan.md` and `meta/CHECKPOINT.md` in the unit governed by the standing rule that sub-agents must not edit those files.

## Fix Focus Areas
- meta/plan.md[13-15]
- meta/CHECKPOINT.md[3-10]

## Recommended Fix
Remove sub-agent-authored edits to `meta/plan.md` and `meta/CHECKPOINT.md` from the sub-agent unit commit, and have the orchestrator or authorized maintainer apply any required plan and checkpoint updates separately.
```

<code>ⓘ Copy this prompt and use it to remediate the issue with your preferred AI generation tools</code>
</details>

[Dismiss ↗](https://app.qodo.ai/findings/7e135550-1599-451f-a8f6-1158430c1133?action=dismiss&origin=git) | [View ↗](https://app.qodo.ai/findings/7e135550-1599-451f-a8f6-1158430c1133)