<img src="https://img.shields.io/badge/Medium-634FD1?style=flat-square" height="20px" alt="Remediation recommended">

3\. Paused playbook kits lose hold reasons <code>🐞 Bug</code> <code>◔ Observability</code>

<pre>
<b><i>_owner_hold_reason</i></b> reaches notifications only through <b><i>_announce_hold</i></b>, while <b><i>defer_hold</i></b> skips
holds filed during a pause and startup republishes held jobs without a reason override. When either
path handles a role-filed kit carrying a playbook, the human sees only <b><i>apply &lt;name&gt;</i></b>, not the
playbook path and ownership reason.
</pre>


<details>
<summary><strong>Agent Prompt</strong></summary>

```
## Issue description
Playbook-bearing kits filed while the pipeline is paused, or republished as held after restart, bypass the new reason override and show only the gate's generic apply reason.

## Fix Focus Areas
- src/hands/playbook.py[2087-2100]
- src/hands/playbook.py[2134-2136]
- src/hands/daemon.py[407-436]
- src/hands/daemon.py[861-879]

## Recommended Fix
Derive and publish the playbook-specific reason for qualifying architect-filed holds on immediate and startup publication paths as well as deferred publication. Preserve the gate's stored reason and add tests for a kit filed during a pause and one republished after restart.
```

<code>ⓘ Copy this prompt and use it to remediate the issue with your preferred AI generation tools</code>
</details>

[Dismiss ↗](https://app.qodo.ai/findings/3ab62326-22f1-48e8-ae21-67219a5a4381?action=dismiss&origin=git) | [View ↗](https://app.qodo.ai/findings/3ab62326-22f1-48e8-ae21-67219a5a4381)