<img src="https://img.shields.io/badge/Low-634FD1?style=flat-square" height="20px" alt="Informational">

9\. A finding titled with 'resolved' counts as fixed <code>🐞 Bug</code> <code>≡ Correctness</code>

<pre>
<b><i>_STRUCK</i></b> matches the bare substring <b><i>Resolved</i></b> anywhere in a finding&#x27;s title, and
<b><i>Finding.resolved</i></b> uses it to leave a finding out of the open count. An open finding whose title
contains that word (e.g. &quot;Resolved paths escape the root&quot;) is printed as <b><i>resolved</i></b>, drops out of
<b><i>verdict: N of M findings open</i></b>, and the diff reports it as <b><i>resolved since k</i></b>.
</pre>


<details>
<summary><strong>Agent Prompt</strong></summary>

```
## Issue description
`_STRUCK` treats any title containing `Resolved` as a resolved finding.

## Fix Focus Areas
- src/hands/hosted.py[57-57]

## Recommended Fix
Replace the bare `Resolved` alternative with the bot's actual marker, e.g. `✓ Resolved` (or `✓\s*Resolved`), and keep the strike-through tags. Add a test for an open finding whose title contains the word 'Resolved'.
```

<code>ⓘ Copy this prompt and use it to remediate the issue with your preferred AI generation tools</code>
</details>

[Dismiss ↗](https://app.qodo.ai/findings/db36f07b-e11d-4b66-bb1d-7851cebaf0ab?action=dismiss&origin=git) | [View ↗](https://app.qodo.ai/findings/db36f07b-e11d-4b66-bb1d-7851cebaf0ab)