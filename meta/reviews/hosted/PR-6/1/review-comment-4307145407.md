<img src="https://img.shields.io/badge/Medium-634FD1?style=flat-square" height="20px" alt="Remediation recommended">

2\. Failed consults leave the pipeline running <code>🐞 Bug</code> <code>☼ Reliability</code>

<pre>
<b><i>_consult_for_human</i></b> persists an unpause before it calls <b><i>enqueue</i></b>, without restoring the stop if
enqueue fails. A queue or spool failure can therefore leave a stopped pipeline running even though
no architect consultation was created.
</pre>


<details>
<summary><strong>Agent Prompt</strong></summary>

```
## Issue description
A failed human-consult enqueue currently clears a persisted pipeline stop without starting a consultation.
## Fix Focus Areas
- src/hands/playbook.py[2533-2566]
- src/hands/api.py[593-609]
## Recommended Fix
Make job creation succeed before persisting the unpause, or restore the prior stopped state on enqueue failure. Keep the consultation event consistent with the created job.
```

<code>ⓘ Copy this prompt and use it to remediate the issue with your preferred AI generation tools</code>
</details>

[Dismiss ↗](https://app.qodo.ai/findings/2b567793-01a9-4e80-b276-92416b35a421?action=dismiss&origin=git) | [View ↗](https://app.qodo.ai/findings/2b567793-01a9-4e80-b276-92416b35a421)