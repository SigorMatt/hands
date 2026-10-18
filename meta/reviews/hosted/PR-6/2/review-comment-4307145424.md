<img src="https://img.shields.io/badge/Medium-634FD1?style=flat-square" height="20px" alt="Remediation recommended">

7\. Discotrade consultations lack reviews <code>🔗 Cross-repo conflict</code> <code>≡ Correctness</code>

<pre>
<b><i>human_consult_prompt</i></b> replaces the review with a reason and starts the architect with no review
job. Discotrade’s standing architect instructions require a consultation on a review outcome and
require reading the review it names, leaving that required input undefined when its operator uses
the new <b><i>consult</i></b> command.
</pre>


<details>
<summary><strong>Agent Prompt</strong></summary>

```
## Issue description
Human-started consultations omit the review required by discotrade’s standing architect procedure.

## Fix Focus Areas
- src/hands/playbook.py[3406-3410]
- meta/ARCHITECT.md[1-5]
- meta/ARCHITECT.md[30-43]

## Recommended Fix
Update discotrade’s architect instructions to define the human-reason path, including what replaces the named review when deciding whether to file a kit or escalate, before enabling that command for the project.
```

<code>ⓘ Copy this prompt and use it to remediate the issue with your preferred AI generation tools</code>
</details>

[Dismiss ↗](https://app.qodo.ai/findings/54f50653-a20c-47bc-b540-550d7837bb58?action=dismiss&origin=git) | [View ↗](https://app.qodo.ai/findings/54f50653-a20c-47bc-b540-550d7837bb58)