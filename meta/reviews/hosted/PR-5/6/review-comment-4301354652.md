<img src="https://img.shields.io/badge/Medium-634FD1?style=flat-square" height="20px" alt="Remediation recommended">

6\. Restored held jobs block the kickoff step <code>🐞 Bug</code> <code>≡ Correctness</code>

<pre>
The migration procedure instructs the operator to run <b><i>hands go</i></b> after startup without first
resolving any restored builder jobs. When the restored spool contains a held builder apply—the
condition the preceding step says the start notification can announce—<b><i>Api.kickoff</i></b> refuses the
command because the builder is busy.
</pre>


<details>
<summary><strong>Agent Prompt</strong></summary>

```
### Issue description
The migration runbook calls for a kickoff even when a restored held builder job makes kickoff impossible.
### Fix Focus Areas
- docs/OPERATIONS.md[325-331]
### Recommended Fix
Tell operators to inspect and resolve restored held or queued builder jobs before using `hands go`, and describe when a fresh kickoff is appropriate.
```

<code>ⓘ Copy this prompt and use it to remediate the issue with your preferred AI generation tools</code>
</details>

[Dismiss ↗](https://app.qodo.ai/findings/f4b8827b-b25f-4f30-a632-d1624c9a0734?action=dismiss&origin=git) | [View ↗](https://app.qodo.ai/findings/f4b8827b-b25f-4f30-a632-d1624c9a0734)