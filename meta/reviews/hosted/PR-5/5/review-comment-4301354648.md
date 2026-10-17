<img src="https://img.shields.io/badge/Medium-634FD1?style=flat-square" height="20px" alt="Remediation recommended">

5\. Old spool state is skipped after migration <code>🐞 Bug</code> <code>≡ Correctness</code>

<pre>
The new-machine procedure extracts the archive and proceeds to daemon startup without running `hands
migrate-spool` for the flat spool layout that this runbook also describes. When the archived state
predates per-project spools, the daemon reads the new per-project directory instead of the restored
jobs, roles, inbox and pipeline files.
</pre>


<details>
<summary><strong>Agent Prompt</strong></summary>

```
### Issue description
The restore procedure does not move archived flat spool state into the project's spool before starting the daemon.
### Fix Focus Areas
- docs/OPERATIONS.md[315-329]
### Recommended Fix
Add a conditional step for a restored pre-per-project spool: run the documented spool migration and reconcile its destination with the configured project name before starting the daemon.
```

<code>ⓘ Copy this prompt and use it to remediate the issue with your preferred AI generation tools</code>
</details>

[Dismiss ↗](https://app.qodo.ai/findings/75a6deb5-d6ff-4f5d-a393-55b3734a5606?action=dismiss&origin=git) | [View ↗](https://app.qodo.ai/findings/75a6deb5-d6ff-4f5d-a393-55b3734a5606)