<img src="https://img.shields.io/badge/Medium-634FD1?style=flat-square" height="20px" alt="Remediation recommended">

6\. Ends arriving after a refused resume are lost <code>🐞 Bug</code> <code>≡ Correctness</code>

<pre>
<b><i>resume</i></b> calls <b><i>_load(stop_on_error=False)</i></b>, and a failed load sets <b><i>self.playbook = None</i></b> before it
returns, while the human pause stays. After that, <b><i>_under_human_pause</i></b> returns early on `book is
None<b><i>, so a builder/aux/driver end that arrives later is neither kept nor notified, and </i></b>resume`
rules on orphaned or failed jobs stop firing; the next successful <b><i>resume</i></b> then has nothing to
replay.
</pre>


<details>
<summary><strong>Agent Prompt</strong></summary>

```
## Issue description
When a human pause's `resume` is refused because the playbook does not load, `_load(stop_on_error=False)` has already set `self.playbook = None`. Under the still-active human pause, `_under_human_pause` returns early when `book is None`, so role ends that arrive afterwards are neither kept nor notified, and `resume` rules no longer fire. The series' next step can be lost without anyone being told.

## Fix Focus Areas
- src/hands/playbook.py[1811-1843]
- src/hands/playbook.py[3500-3518]
- src/hands/playbook.py[2064-2068]

## Recommended Fix
With `stop_on_error=False`, leave `self.playbook` (and preferably `self.load_error`) as they were when the load fails, so the engine keeps deciding with the playbook loaded before the refused resume. One way: in `_load`, assign `self.playbook = None` / `self.load_error` only when `stop_on_error` is True, or save and restore them in `resume()` around the refused load. Separately, consider keeping a ROLE_ENDS end in `_under_human_pause` when a playbook file exists but failed to load (`self.load_error is not None`), rather than dropping it. Add a test: pause, refused resume, then a `builder.done` arrives and must be kept.
```

<code>ⓘ Copy this prompt and use it to remediate the issue with your preferred AI generation tools</code>
</details>

[Dismiss ↗](https://app.qodo.ai/findings/3eb6b97c-36f6-42c0-bf51-ca8683747def?action=dismiss&origin=git) | [View ↗](https://app.qodo.ai/findings/3eb6b97c-36f6-42c0-bf51-ca8683747def)