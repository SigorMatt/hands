<img src="https://img.shields.io/badge/Medium-634FD1?style=flat-square" height="20px" alt="Remediation recommended">

7\. Owner kits suggest a refused command <code>🔗 Cross-repo conflict</code> <code>≡ Correctness</code>

<pre>
<b><i>_under_human_pause</i></b> fires Discotrade’s <b><i>builder.done</i></b> kit-applied notification immediately, leaving
its instruction to send <b><i>go</i></b> unchanged. When an owner decisions kit finishes during a human pause,
<b><i>go</i></b> is refused until the operator sends <b><i>resume</i></b>.
</pre>


<details>
<summary><strong>Agent Prompt</strong></summary>

```
## Issue description
Discotrade’s kit-applied notification tells operators to send `go`, but a kit applied during a human pause leaves `go` refused until `resume`.

## Fix Focus Areas
- /cross_repos/discotrade/PLAYBOOK.toml[35-42]
- src/hands/playbook.py[2081-2085]

## Recommended Fix
Update Discotrade’s notification to say to send `resume` first if the pipeline is human-paused, and otherwise send `go`. Keep the immediate notification behavior in hands.
```

<code>ⓘ Copy this prompt and use it to remediate the issue with your preferred AI generation tools</code>
</details>

[Dismiss ↗](https://app.qodo.ai/findings/ad44f44d-04f2-4c2e-8307-d91bb88b9e45?action=dismiss&origin=git) | [View ↗](https://app.qodo.ai/findings/ad44f44d-04f2-4c2e-8307-d91bb88b9e45)