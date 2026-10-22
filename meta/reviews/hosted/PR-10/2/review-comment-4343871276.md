<img src="https://img.shields.io/badge/Medium-634FD1?style=flat-square" height="20px" alt="Remediation recommended">

3\. A moved head prevents saving the blocker <code>🐞 Bug</code> <code>☼ Reliability</code>

<pre>
The new <b><i>not merged</i></b> path requires a blocker commit on the branch but gives no recovery step if that
commit&#x27;s push is refused. When the head moves after the review commit was pushed,
<b><i>--match-head-commit</i></b> refuses the merge and the local branch is behind the remote, so pushing the
required blocker commit is non-fast-forward.
</pre>


<details>
<summary><strong>Agent Prompt</strong></summary>

```
## Issue description
A moved PR head makes the guarded merge fail, then prevents the protocol from pushing its required `not merged` blocker commit to the stale local branch.

## Fix Focus Areas
- meta/REVIEW-PROTOCOL.md[331-347]
- templates/REVIEW-PROTOCOL.md[331-347]

## Recommended Fix
Specify a recovery path for a refused push of the `not merged` commit: fetch the new branch tip, put the blocker review on that tip without merging, and push it. If that cannot be done, specify how to leave the local branch usable and report the blocker in the reply.
```

<code>ⓘ Copy this prompt and use it to remediate the issue with your preferred AI generation tools</code>
</details>

[Dismiss ↗](https://app.qodo.ai/findings/8942f708-6508-4af5-a310-e644960be71e?action=dismiss&origin=git) | [View ↗](https://app.qodo.ai/findings/8942f708-6508-4af5-a310-e644960be71e)