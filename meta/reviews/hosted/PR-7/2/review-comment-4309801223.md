<img src="https://img.shields.io/badge/Medium-634FD1?style=flat-square" height="20px" alt="Remediation recommended">

4\. Holds with other causes show the playbook-owner reason <code>🐞 Bug</code> <code>◔ Observability</code>

<pre>
<b><i>_announce_hold</i></b> now always passes <b><i>reason=self._owner_hold_reason(job)</i></b>, so every buttoned hold of
a kit that contains a playbook gets §43&#x27;s &quot;a change of the playbook is the owner&#x27;s&quot; reason. That
includes kits that <b><i>_escalate_kits</i></b> is about to deny for a §33 violation, and kits that
<b><i>_kit_bytes_unchanged</i></b> refused because the hash did not match. In those cases the human sees
Approve/Deny buttons with a wrong reason for the hold, and the real cause shows only in a separate
stop message.
</pre>


<details>
<summary><strong>Agent Prompt</strong></summary>

```
## Issue description
Every engine-published hold of a kit containing a playbook gets §43's reason, even when it is held or denied for a different cause (an escalation or a sha mismatch).

## Fix Focus Areas
- src/hands/playbook.py[2111-2140]
- src/hands/playbook.py[2254-2256]

## Recommended Fix
Add an optional `reason` parameter to `_announce_hold`, defaulting to None. Pass `owner_hold_reason(...)` only from `_release_kit`'s `_carries_no_playbook` branch, and from the paused-pipeline branch if §43 requires it there. Other callers then keep the gate's reason. Reuse the names `_carries_no_playbook` already read, rather than reopening the zip on the event loop.
```

<code>ⓘ Copy this prompt and use it to remediate the issue with your preferred AI generation tools</code>
</details>

[Dismiss ↗](https://app.qodo.ai/findings/168af956-edce-475e-a5d7-fb20059a584a?action=dismiss&origin=git) | [View ↗](https://app.qodo.ai/findings/168af956-edce-475e-a5d7-fb20059a584a)