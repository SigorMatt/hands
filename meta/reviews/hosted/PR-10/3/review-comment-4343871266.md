<img src="https://img.shields.io/badge/Medium-634FD1?style=flat-square" height="20px" alt="Remediation recommended">

2\. Sub-agents edit protected mission metadata <code>📘 Rule violation</code> <code>§ Compliance</code>

<pre>
The U0 plan commit modifies <b><i>meta/plan.md</i></b> and <b><i>meta/CHECKPOINT.md</i></b>, despite the mission&#x27;s standing
constraint that sub-agents must not edit those files. Protected planning state can therefore be
rewritten by an automated unit, leaving later builders with metadata that does not reflect the
designated owner&#x27;s checkpoint or plan.
</pre>


<details>
<summary><strong>Agent Prompt</strong></summary>

```
## Issue description
The PR modifies `meta/plan.md` and `meta/CHECKPOINT.md`, which the compliance rule reserves from sub-agent edits.

## Fix Focus Areas
- meta/plan.md[1-4]
- meta/CHECKPOINT.md[3-6]

## Recommended Fix
Remove the sub-agent-authored changes to `meta/plan.md` and `meta/CHECKPOINT.md`, or move the plan and checkpoint updates into an owner-controlled step that is not performed by a sub-agent.
```

<code>ⓘ Copy this prompt and use it to remediate the issue with your preferred AI generation tools</code>
</details>

[Dismiss ↗](https://app.qodo.ai/findings/c0e7b7dc-4f2c-4815-9fa8-ea793a134dc3?action=dismiss&origin=git) | [View ↗](https://app.qodo.ai/findings/c0e7b7dc-4f2c-4815-9fa8-ea793a134dc3)