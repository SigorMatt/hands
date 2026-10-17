<img src="https://img.shields.io/badge/High-634FD1?style=flat-square" height="20px" alt="Action required">

1\. Discotrade misses journal reminders <code>🔗 Cross-repo conflict</code> <code>≡ Correctness</code>

<pre>
<b><i>Runner.run()</i></b> records the new journal preface in the running job but still writes <b><i>job.prompt</i></b>,
without the preface, to Claude. When a discotrade builder answer or CLI send starts while
<b><i>meta/journal.md</i></b> is dirty, the builder misses the instruction to commit it before continuing the
mission, despite the job record saying that instruction was delivered.
</pre>


<details>
<summary><strong>Agent Prompt</strong></summary>

```
## Issue description
The running job records a journal preface that Claude never receives. This defeats the dirty-journal reminder for discotrade builder sessions.

## Fix Focus Areas
- src/hands/runner.py[617-618]
- src/hands/runner.py[653-656]
- src/hands/runner.py[693-701]

## Recommended Fix
Pass the same prefaced prompt to `_write_prompt` that the running job records, and test the subprocess input as well as the job record.
```

<code>ⓘ Copy this prompt and use it to remediate the issue with your preferred AI generation tools</code>
</details>

[Dismiss ↗](https://app.qodo.ai/findings/eca7f0c4-a719-4cb3-a2ac-7fd0992eea47?action=dismiss&origin=git) | [View ↗](https://app.qodo.ai/findings/eca7f0c4-a719-4cb3-a2ac-7fd0992eea47)