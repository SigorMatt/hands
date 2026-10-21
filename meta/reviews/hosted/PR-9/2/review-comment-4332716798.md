<img src="https://img.shields.io/badge/High-634FD1?style=flat-square" height="20px" alt="Action required">

1\. A review can merge unreviewed commits <code>🐞 Bug</code> <code>≡ Correctness</code>

<pre>
The review protocol waits for checks by pull request number and merges without verifying that the
head still matches the commit its sub-agents reviewed. If the mission branch advances during the
review, the review can record the earlier <b><i>headRefOid</i></b> while the later commit passes checks and is
merged.
</pre>


<details>
<summary><strong>Agent Prompt</strong></summary>

```
## Issue description
The pull-request review can merge a branch head that changed after the reviewed commit was selected.
## Fix Focus Areas
- templates/REVIEW-PROTOCOL.md[203-217]
- templates/REVIEW-PROTOCOL.md[275-283]
- meta/REVIEW-PROTOCOL.md[275-283]
## Recommended Fix
Require the fetched review tip to match the pull request head, recheck that head before accepting checks, and merge with a head-commit match condition. If it changed, stop for another review; update both protocol copies.
```

<code>ⓘ Copy this prompt and use it to remediate the issue with your preferred AI generation tools</code>
</details>

[Dismiss ↗](https://app.qodo.ai/findings/774fdc0f-39ba-41cc-8ce2-f710d331c7d6?action=dismiss&origin=git) | [View ↗](https://app.qodo.ai/findings/774fdc0f-39ba-41cc-8ce2-f710d331c7d6)