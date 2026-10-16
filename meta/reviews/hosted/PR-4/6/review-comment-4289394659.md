<img src="https://img.shields.io/badge/Medium-634FD1?style=flat-square" height="20px" alt="Remediation recommended">

5\. Hosted reviews hide the verdict <code>📘 Rule violation</code> <code>✧ Quality</code>

<pre>
<b><i>run</i></b> prints the pull-request summary and archive location before it emits the eventual <b><i>verdict:</i></b>
line, and the verdict is lower-case rather than a leading <b><i>VERDICT:</i></b> line. Every human-visible
hosted review therefore begins with counts and archive metadata instead of the required verdict
prefix.
</pre>


<details>
<summary><strong>Agent Prompt</strong></summary>

```
## Issue description
The hosted review renderer emits summary and archive lines before its verdict and formats the verdict with a lower-case prefix.

## Fix Focus Areas
- src/hands/hosted.py[333-335]
- src/hands/hosted.py[376-388]

## Recommended Fix
Determine the Code Review verdict before rendering the report, print a first line beginning exactly with `VERDICT:`, and then emit counts, archive metadata, findings, and details on subsequent lines. Use the active verdict vocabulary and preserve the no-review state as an explicit non-clean verdict.
```

<code>ⓘ Copy this prompt and use it to remediate the issue with your preferred AI generation tools</code>
</details>

[Dismiss ↗](https://app.qodo.ai/findings/b01bbc4b-14eb-4650-88ca-26ccff7bd750?action=dismiss&origin=git) | [View ↗](https://app.qodo.ai/findings/b01bbc4b-14eb-4650-88ca-26ccff7bd750)