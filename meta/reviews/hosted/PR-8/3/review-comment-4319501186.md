<img src="https://img.shields.io/badge/Medium-634FD1?style=flat-square" height="20px" alt="Remediation recommended">

3\. Restarts can miss the quiet moment <code>🐞 Bug</code> <code>≡ Correctness</code>

<pre>
<b><i>check_at_rest</i></b> runs when a pause is sent or a job ends, but startup does not run it for a restored
human pause after resolving pending retries. If a pending limited job is not rescheduled and all
persisted jobs are terminal, the unset at-rest mark has no subsequent job transition to trigger the
notification.
</pre>


<details>
<summary><strong>Agent Prompt</strong></summary>

```
## Issue description
Restoring an idle human pause does not announce rest when startup declines to reschedule its pending limit retry.
## Fix Focus Areas
- src/hands/daemon.py[283-300]
- src/hands/playbook.py[3566-3589]
## Recommended Fix
After startup restores and reconciles jobs and pending limit retries, call `check_at_rest` for the restored pause. Preserve the persisted mark so an already-announced pause is not announced twice.
```

<code>ⓘ Copy this prompt and use it to remediate the issue with your preferred AI generation tools</code>
</details>

[Dismiss ↗](https://app.qodo.ai/findings/248439d7-efd8-4334-bfde-4a2a57f6588a?action=dismiss&origin=git) | [View ↗](https://app.qodo.ai/findings/248439d7-efd8-4334-bfde-4a2a57f6588a)