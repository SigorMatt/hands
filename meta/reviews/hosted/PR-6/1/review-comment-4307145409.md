<img src="https://img.shields.io/badge/Medium-634FD1?style=flat-square" height="20px" alt="Remediation recommended">

3\. Exhausted jobs stay stopped after resume <code>🐞 Bug</code> <code>≡ Correctness</code>

<pre>
The operator table tells a human to run <b><i>resume</i></b> after a <b><i>limits.max_resumes reached</i></b> stop, but that
command only clears the pipeline pause. When the resume limit has been reached, the limit manager
schedules no new builder job, so following this row does not restart the work.
</pre>


<details>
<summary><strong>Agent Prompt</strong></summary>

```
## Issue description
The exhausted-resume row prescribes a command that unpauses the pipeline but does not restart its limited job.
## Fix Focus Areas
- docs/ARCHITECT-HANDBOOK.md[868-874]
- docs/ARCHITECT-HANDBOOK.md[907-908]
## Recommended Fix
Give `max_resumes reached` its own recovery route that identifies how the human resolves the exhausted limit and starts work again. Reserve the ordinary `resume` instruction for the case where the limit manager has scheduled a job resume.
```

<code>ⓘ Copy this prompt and use it to remediate the issue with your preferred AI generation tools</code>
</details>

[Dismiss ↗](https://app.qodo.ai/findings/dbc57327-85ee-4c58-a812-849676ac2910?action=dismiss&origin=git) | [View ↗](https://app.qodo.ai/findings/dbc57327-85ee-4c58-a812-849676ac2910)