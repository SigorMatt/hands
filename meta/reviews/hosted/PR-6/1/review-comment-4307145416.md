<img src="https://img.shields.io/badge/Medium-634FD1?style=flat-square" height="20px" alt="Remediation recommended">

6\. A refused consult can stop a running pipeline <code>🐞 Bug</code> <code>☼ Reliability</code>

<pre>
<b><i>Api.consult_refusal</i></b> calls <b><i>engine.reload()</i></b>, which runs the full <b><i>PlaybookEngine._load()</i></b>, before
it checks for a busy builder, aux or architect. <b><i>_load()</i></b> stops and pauses the pipeline when the
playbook does not load (dirty, uncommitted, wrong config). It also swaps the in-memory playbook and
clears <b><i>last_rule</i></b> in the middle of a running job. So a phone <b><i>consult</i></b> (asked twice, before and
after the fetch) or a <b><i>hands consult</i></b> sent while the builder is working can stop the pipeline. It
can also change which rules decide that builder&#x27;s end, even though the consult itself is then
refused as busy.
</pre>


<details>
<summary><strong>Agent Prompt</strong></summary>

```
## Issue description
`Api.consult_refusal` reloads the playbook through `PlaybookEngine._load()` before it checks for busy roles. `_load()` can call `stop()`, which pauses the pipeline and notifies. It also replaces the playbook in force and clears `last_rule` while a job is running. So a consult that is going to be refused anyway can stop a running pipeline or change the rules for the running job.

## Fix Focus Areas
- src/hands/api.py[557-591]
- src/hands/playbook.py[1623-1627]

## Recommended Fix
Run the `_role_busy` checks for architect/builder/aux, and the `kit_wait` check, before calling `engine.reload()`. Only reload once no role is busy. Also make `reload()` side-effect free on failure: load the playbook without `stop()` (for example, a `_load(stop_on_error=False)` variant that only sets `load_error`), so the refusal text reports the load error without stopping the pipeline. Add a test: a consult sent while a builder job is running with a dirty playbook leaves `pipeline.json` unpaused and `last_rule` unchanged.
```

<code>ⓘ Copy this prompt and use it to remediate the issue with your preferred AI generation tools</code>
</details>

[Dismiss ↗](https://app.qodo.ai/findings/6a5a3002-45ce-4425-843b-6e2595874939?action=dismiss&origin=git) | [View ↗](https://app.qodo.ai/findings/6a5a3002-45ce-4425-843b-6e2595874939)