<img src="https://img.shields.io/badge/Medium-634FD1?style=flat-square" height="20px" alt="Remediation recommended">

6\. Stalled checks can exceed the tool timeout <code>🐞 Bug</code> <code>☼ Reliability</code>

<pre>
<b><i>ci_wait</i></b> starts its nine-minute deadline only after authentication, origin, pull-request and rules
reads, each of which can consume a subprocess timeout, and it starts a further checks read without
bounding it by the remaining time. When those commands stall, one foreground call can run well
beyond the stated nine minutes and exceed the role&#x27;s tool-call timeout before returning a wait or
error result.
</pre>


<details>
<summary><strong>Agent Prompt</strong></summary>

```
## Issue description
The nine-minute limit excludes setup subprocesses and the final checks subprocess, so a stalled call can outlast its foreground tool timeout.
## Fix Focus Areas
- src/hands/cli.py[217-257]
- src/hands/forge.py[52-59]
- src/hands/forge.py[90-95]
## Recommended Fix
Start the deadline before setup and pass the remaining time as a timeout to every blocking subprocess, including the final poll. Return an appropriate waiting or error result when no time remains.
```

<code>ⓘ Copy this prompt and use it to remediate the issue with your preferred AI generation tools</code>
</details>

[Dismiss ↗](https://app.qodo.ai/findings/48385f72-7438-47c6-968c-858a90701911?action=dismiss&origin=git) | [View ↗](https://app.qodo.ai/findings/48385f72-7438-47c6-968c-858a90701911)