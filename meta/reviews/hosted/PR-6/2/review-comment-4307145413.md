<img src="https://img.shields.io/badge/Medium-634FD1?style=flat-square" height="20px" alt="Remediation recommended">

5\. Rejected consults fill the kit directory <code>🐞 Bug</code> <code>☼ Reliability</code>

<pre>
<b><i>_consult_command</i></b> leaves the permanently linked attachment in <b><i>kit_dir</i></b> when UTF-8 decoding or the
final consultation check refuses it. Repeated authenticated requests with invalid text, or requests
refused after a state change during download, accumulate files even though no consultation starts.
</pre>


<details>
<summary><strong>Agent Prompt</strong></summary>

```
## Issue description
A phone consult can retain a downloaded attachment after refusing the command, allowing unused files to accumulate.
## Fix Focus Areas
- src/hands/phone.py[617-632]
- src/hands/phone.py[1034-1043]
## Recommended Fix
Track the path returned by `_fetch` and remove that specific newly written file if decoding or `start_consult` fails. Preserve attachments for successfully started consultations.
```

<code>ⓘ Copy this prompt and use it to remediate the issue with your preferred AI generation tools</code>
</details>

[Dismiss ↗](https://app.qodo.ai/findings/613e7991-180e-47c2-8e85-3b0c4c7126ab?action=dismiss&origin=git) | [View ↗](https://app.qodo.ai/findings/613e7991-180e-47c2-8e85-3b0c4c7126ab)