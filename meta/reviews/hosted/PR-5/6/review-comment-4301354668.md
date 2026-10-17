<img src="https://img.shields.io/badge/Medium-634FD1?style=flat-square" height="20px" alt="Remediation recommended">

9\. A restarted kickoff no longer resets the consult count <code>🐞 Bug</code> <code>≡ Correctness</code>

<pre>
<b><i>wants_journal_sentence</i></b> leaves out kickoffs only through the in-memory <b><i>Daemon.kickoffs</i></b> set. When
a <b><i>hands go</i></b> job (origin <b><i>cli</i></b>) is still held or queued across a daemon restart and the journal is
dirty, the runner rewrites the stored <b><i>prompt</i></b> to <b><i>&lt;sentence&gt;\n\n&lt;kickoff&gt;</i></b>. <b><i>consults_used</i></b>
recognises a kickoff by <b><i>record.prompt.strip() in kickoffs</i></b>, so that job no longer resets the
consultation count, and the pipeline can stop early on <b><i>max_consults</i></b>.
</pre>


<details>
<summary><strong>Agent Prompt</strong></summary>

```
## Issue description
A kickoff is recognised only through an in-memory set, so after a restart it gets the journal sentence. That rewrites its recorded prompt, and consults_used stops treating it as a kickoff.

## Fix Focus Areas
- src/hands/daemon.py[711-719]
- src/hands/api.py[375-379]

## Recommended Fix
Decide kickoff status from persisted data. Either compare `job.prompt.strip()` with the playbook's kickoff values (`PipelineState.kickoffs` plus the loaded book's), or store a marker on the job record at enqueue, and check that in `wants_journal_sentence` instead of `self.kickoffs`.
```

<code>ⓘ Copy this prompt and use it to remediate the issue with your preferred AI generation tools</code>
</details>

[Dismiss ↗](https://app.qodo.ai/findings/5fe0d239-437d-4a25-ad4e-26b337c2d95c?action=dismiss&origin=git) | [View ↗](https://app.qodo.ai/findings/5fe0d239-437d-4a25-ad4e-26b337c2d95c)