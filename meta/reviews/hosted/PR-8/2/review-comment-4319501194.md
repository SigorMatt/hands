<img src="https://img.shields.io/badge/Medium-634FD1?style=flat-square" height="20px" alt="Remediation recommended">

4\. A failed retry hides the quiet moment <code>🐞 Bug</code> <code>≡ Correctness</code>

<pre>
<b><i>check_at_rest</i></b> excludes a pause while a limit-resume task is scheduled, but nothing checks again
when <b><i>_resume_after</i></b> fails without creating a job. If the retry fails while no other job is active,
its suppressed stop is announced but the human never receives the at-rest notification for that
pause.
</pre>


<details>
<summary><strong>Agent Prompt</strong></summary>

```
## Issue description
A limit retry that fails without starting a job removes the reason for withholding `hands: at rest`, but creates no job end to recheck it.
## Fix Focus Areas
- src/hands/limits.py[464-476]
- src/hands/playbook.py[3575-3589]
## Recommended Fix
Recheck at-rest eligibility after a scheduled retry terminates without starting a job, once that task no longer counts as scheduled. Retain the existing suppression and notification for its stop.
```

<code>ⓘ Copy this prompt and use it to remediate the issue with your preferred AI generation tools</code>
</details>

[Dismiss ↗](https://app.qodo.ai/findings/0508e1a9-3415-4416-83ec-f491e2955141?action=dismiss&origin=git) | [View ↗](https://app.qodo.ai/findings/0508e1a9-3415-4416-83ec-f491e2955141)