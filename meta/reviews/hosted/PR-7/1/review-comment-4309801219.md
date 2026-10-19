<img src="https://img.shields.io/badge/High-634FD1?style=flat-square" height="20px" alt="Action required">

1\. Role kits can rewrite the playbook by changing its case <code>🐞 Bug</code> <code>⛨ Security</code>

<pre>
<b><i>Spool.stored_kit_playbooks</i></b> (and <b><i>kit._owner_warning</i></b>) recognise only the exact names
<b><i>PLAYBOOK.toml</i></b> and <b><i>meta/PLAYBOOK.toml</i></b>, so an entry such as <b><i>playbook.toml</i></b>, <b><i>Playbook.toml</i></b> or
<b><i>Meta/PLAYBOOK.toml</i></b> passes <b><i>_carries_no_playbook</i></b> and the engine approves the apply. On a
case-insensitive filesystem the apply&#x27;s <b><i>unzip -o</i></b> writes that entry over the real playbook, which
the apply then commits. The role can therefore raise its own <b><i>max_architect_consults</i></b>, drop a stop
rule or change the kickoff without the human seeing it, which is exactly what H-075 was meant to
stop.
</pre>


<details>
<summary><strong>Agent Prompt</strong></summary>

```
## Issue description
The §43 hold detects a carried playbook by exact name, so a kit entry like `playbook.toml` or `Meta/PLAYBOOK.toml` is approved by the engine. On a case-folding filesystem it then overwrites the playbook in force.

## Fix Focus Areas
- src/hands/spool.py[574-583]
- src/hands/kit.py[873-900]

## Recommended Fix
Compare each zip name with `name.casefold()` against `{p.casefold() for p in PLAYBOOK_PATHS}`, and return the entry name actually found. Apply the same case-folded match in `_owner_warning`. Add tests for `playbook.toml` and `Meta/PLAYBOOK.toml` being held.
```

<code>ⓘ Copy this prompt and use it to remediate the issue with your preferred AI generation tools</code>
</details>

[Dismiss ↗](https://app.qodo.ai/findings/b1cbd300-c9c9-450a-a5a8-75fb851d03f8?action=dismiss&origin=git) | [View ↗](https://app.qodo.ai/findings/b1cbd300-c9c9-450a-a5a8-75fb851d03f8)