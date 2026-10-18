<img src="https://img.shields.io/badge/High-634FD1?style=flat-square" height="20px" alt="Action required">

1\. Discotrade skips mid-mission rulings <code>🔗 Cross-repo conflict</code> <code>≡ Correctness</code>

<pre>
The new decisions-kit route tells operators to apply an owner file and use <b><i>go</i></b>, relying on the
added §R instruction to make the builder carry out its steps. Discotrade’s active mission 20 brief
has an older §R without that instruction, so a mid-mission decisions kit can be committed while the
resumed builder continues from its checkpoint without acting on the ruling.
</pre>


<details>
<summary><strong>Agent Prompt</strong></summary>

```
## Issue description
The decisions-kit-and-go route depends on recovery wording absent from discotrade’s active brief.

## Fix Focus Areas
- templates/BUILDER-N-PROMPT.md[98-101]
- docs/ARCHITECT-HANDBOOK.md[843-853]
- meta/BUILDER-20-PROMPT.md[128-136]

## Recommended Fix
Update discotrade’s active and future mission briefs with the owner-file recovery rule before recommending this route there, or provide a compatible route for briefs that lack it.
```

<code>ⓘ Copy this prompt and use it to remediate the issue with your preferred AI generation tools</code>
</details>

[Dismiss ↗](https://app.qodo.ai/findings/cb656a99-3a8c-4279-af18-84de7917ee2c?action=dismiss&origin=git) | [View ↗](https://app.qodo.ai/findings/cb656a99-3a8c-4279-af18-84de7917ee2c)