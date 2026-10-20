<img src="https://img.shields.io/badge/Medium-634FD1?style=flat-square" height="20px" alt="Remediation recommended">

2\. Decided jobs receive late hold notices <code>🐞 Bug</code> <code>☼ Reliability</code>

<pre>
<b><i>Api.send</i></b> and <b><i>_publish_held</i></b> await held-reason computation, then announce a hold without
rechecking the job’s gate or current state. If another client approves or denies the job during that
wait, the later notification describes a hold that no longer exists and can create new approval
buttons.
</pre>


<details>
<summary><strong>Agent Prompt</strong></summary>

```
## Issue description
A client can approve or deny a held job while `Api.send` or startup hold publication awaits reason computation, leaving a stale hold event or notification to be published.

## Fix Focus Areas
- src/hands/api.py[440-451]
- src/hands/daemon.py[424-428]
- src/hands/daemon.py[430-451]
- src/hands/daemon.py[901-912]

## Recommended Fix
After reason computation, reload the job before filing `job.held` or publishing a startup hold. File the event only if the gate is still pending, and publish the startup hold only if the job is still held; keep the startup list consistent with that check and clear any cached reason when the gate has already been decided.
```

<code>ⓘ Copy this prompt and use it to remediate the issue with your preferred AI generation tools</code>
</details>

[Dismiss ↗](https://app.qodo.ai/findings/04de2b51-3613-401b-a417-6d2712b88ac7?action=dismiss&origin=git) | [View ↗](https://app.qodo.ai/findings/04de2b51-3613-401b-a417-6d2712b88ac7)