<img src="https://img.shields.io/badge/Medium-634FD1?style=flat-square" height="20px" alt="Remediation recommended">

4\. Ruling follow-ups refuse consultation <code>🐞 Bug</code> <code>≡ Correctness</code>

<pre>
Route 5 says to send an owner kit using route 4 and then run <b><i>consult</i></b>, but route 4 ends by running
<b><i>go</i></b>. If the human follows that sequence immediately, <b><i>go</i></b> starts a builder job and the new consult
path refuses the request while that job is queued or running.
</pre>


<details>
<summary><strong>Agent Prompt</strong></summary>

```
## Issue description
The consultation route inherits a `go` command that makes the ensuing consultation fail its builder-busy check.
## Fix Focus Areas
- docs/ARCHITECT-HANDBOOK.md[843-859]
- docs/ARCHITECT-HANDBOOK.md[924-925]
## Recommended Fix
Spell out when the owner kit has finished applying and when, if at all, `go` should run. If `go` is required first, instruct the human to wait for its builder job to end before issuing `consult`.
```

<code>ⓘ Copy this prompt and use it to remediate the issue with your preferred AI generation tools</code>
</details>

[Dismiss ↗](https://app.qodo.ai/findings/3187c741-5a3d-4f8c-9ea9-71bd6aac33e5?action=dismiss&origin=git) | [View ↗](https://app.qodo.ai/findings/3187c741-5a3d-4f8c-9ea9-71bd6aac33e5)