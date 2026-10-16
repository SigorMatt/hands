<img src="https://img.shields.io/badge/Medium-634FD1?style=flat-square" height="20px" alt="Remediation recommended">

3\. The review command alters the repository <code>📘 Rule violation</code> <code>⛨ Security</code>

<pre>
<b><i>archive</i></b> creates directories and writes hosted comments and JSON files directly under the
repository. Running <b><i>hands hosted-review</i></b> therefore performs filesystem writes and invokes <b><i>gh api</i></b>,
rather than remaining limited to <b><i>hands</i></b> commands and read-only repository inspection.
</pre>


<details>
<summary><strong>Agent Prompt</strong></summary>

```
## Issue description
The hosted review command writes archived review data into the repository and invokes an external `gh` command, conflicting with the read-only driver restriction.

## Fix Focus Areas
- src/hands/hosted.py[91-108]
- src/hands/hosted.py[156-165]

## Recommended Fix
Keep the driver-side review operation read-only and route archival through an explicitly authorized non-driver component, or revise the command boundary so repository writes cannot occur in the driver implementation. Preserve explicit failure handling for the external API call and ensure any archival destination is separately authorized.
```

<code>ⓘ Copy this prompt and use it to remediate the issue with your preferred AI generation tools</code>
</details>

[Dismiss ↗](https://app.qodo.ai/findings/f6046d9a-cd11-440f-9c85-96198e0a9e2d?action=dismiss&origin=git) | [View ↗](https://app.qodo.ai/findings/f6046d9a-cd11-440f-9c85-96198e0a9e2d)