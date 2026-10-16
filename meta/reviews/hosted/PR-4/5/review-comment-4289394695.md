<img src="https://img.shields.io/badge/Low-634FD1?style=flat-square" height="20px" alt="Informational">

11\. A send to the builder can stall the daemon on git <code>🐞 Bug</code> <code>☼ Reliability</code>

<pre>
<b><i>Api._send</i></b> calls <b><i>PlaybookEngine.journal_reminder()</i></b> straight from the event loop. That runs a
blocking <b><i>git status --porcelain</i></b> (10 s timeout) and reads the whole inbox through <b><i>spool.events()</i></b>.
On every cli send and every phone <b><i>answer</i></b> to the builder, a slow or locked repository freezes the
queue, the socket and the phone channel for that time; <b><i>progress_report</i></b> avoids the same problem by
moving its git calls to a thread.
</pre>


<details>
<summary><strong>Agent Prompt</strong></summary>

```
## Issue description
The journal reminder's git call and inbox scan run synchronously on the daemon's event loop.

## Fix Focus Areas
- src/hands/api.py[340-346]

## Recommended Fix
Replace `reminder = self.daemon.playbook.journal_reminder()` with `reminder = await asyncio.to_thread(self.daemon.playbook.journal_reminder)`, as `progress_report` does for its git calls.
```

<code>ⓘ Copy this prompt and use it to remediate the issue with your preferred AI generation tools</code>
</details>

[Dismiss ↗](https://app.qodo.ai/findings/8b786ae5-572a-42d2-bc7b-52996ca49768?action=dismiss&origin=git) | [View ↗](https://app.qodo.ai/findings/8b786ae5-572a-42d2-bc7b-52996ca49768)