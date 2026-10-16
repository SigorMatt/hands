<img src="https://img.shields.io/badge/Medium-634FD1?style=flat-square" height="20px" alt="Remediation recommended">

6\. A failed archive leaves a false review fetch <code>🐞 Bug</code> <code>☼ Reliability</code>

<pre>
<b><i>archive</i></b> creates the numbered directory before writing its comment files, while <b><i>run</i></b> returns an
error without removing files already written. If a later write fails, the next invocation counts
that incomplete directory as a previous fetch and diffs against it.
</pre>


<details>
<summary><strong>Agent Prompt</strong></summary>

```
## Issue description
A write failure can leave an incomplete numbered hosted-review archive that a later run treats as a completed fetch.
## Fix Focus Areas
- src/hands/hosted.py[146-165]
- src/hands/hosted.py[315-331]
## Recommended Fix
Write the complete fetch into a temporary directory, remove it on failure, and move it to the numbered archive path only after every write succeeds. Test a failure after one comment has been written.
```

<code>ⓘ Copy this prompt and use it to remediate the issue with your preferred AI generation tools</code>
</details>

[Dismiss ↗](https://app.qodo.ai/findings/2a1335fa-b647-4220-ac18-e66064affb75?action=dismiss&origin=git) | [View ↗](https://app.qodo.ai/findings/2a1335fa-b647-4220-ac18-e66064affb75)