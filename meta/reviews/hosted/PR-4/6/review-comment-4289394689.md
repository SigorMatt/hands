<img src="https://img.shields.io/badge/Low-634FD1?style=flat-square" height="20px" alt="Informational">

10\. Each wait-loop retry writes another archive <code>🐞 Bug</code> <code>⚙ Maintainability</code>

<pre>
When the bot has posted its summary but not yet its Code Review comment, <b><i>run</i></b> archives a new <b><i>&lt;k&gt;</i></b>
directory and only then returns <b><i>EXIT_NOT_YET</i></b>. The protocol and the brief tell the agent to rerun
the command every minute for up to ten minutes on exit 3, so each retry adds another numbered
snapshot, which gets committed, and the next diff compares against a partial fetch rather than the
builder&#x27;s real one.
</pre>


<details>
<summary><strong>Agent Prompt</strong></summary>

```
## Issue description
Exit 3 on a missing Code Review comment still writes a new archive directory, so the one-minute wait loop piles up snapshots.

## Fix Focus Areas
- src/hands/hosted.py[315-379]

## Recommended Fix
Compute `_code_review(comments)` before `archive(...)`. When it is None, print the not-yet message and return `EXIT_NOT_YET` without writing anything, as the no-bot-comment case already does. Update the test that expects the archive to be kept.
```

<code>ⓘ Copy this prompt and use it to remediate the issue with your preferred AI generation tools</code>
</details>

[Dismiss ↗](https://app.qodo.ai/findings/b1093ffc-1489-4bcb-b717-f775edb12a9d?action=dismiss&origin=git) | [View ↗](https://app.qodo.ai/findings/b1093ffc-1489-4bcb-b717-f775edb12a9d)