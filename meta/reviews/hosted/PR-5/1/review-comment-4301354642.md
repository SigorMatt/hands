<img src="https://img.shields.io/badge/Medium-634FD1?style=flat-square" height="20px" alt="Remediation recommended">

4\. Doctor fails on unreadable worktree data <code>🐞 Bug</code> <code>☼ Reliability</code>

<pre>
<b><i>_worktrees_check</i></b> calls <b><i>admin.iterdir()</i></b> without handling filesystem errors, although it handles
unreadable individual worktree records. If a role clone’s worktree directory is unreadable or
disappears during the check, <b><i>hands doctor</i></b> exits with a generic error instead of reporting its
other checks.
</pre>


<details>
<summary><strong>Agent Prompt</strong></summary>

```
### Issue description
A filesystem error while listing worktree records aborts the entire doctor report.
### Fix Focus Areas
- src/hands/doctor.py[1833-1848]
### Recommended Fix
Catch directory-listing errors and represent the unreadable clone as a worktrees check result, allowing the remaining doctor checks to run.
```

<code>ⓘ Copy this prompt and use it to remediate the issue with your preferred AI generation tools</code>
</details>

[Dismiss ↗](https://app.qodo.ai/findings/47889f6d-04a3-444d-95db-f423b415ac0e?action=dismiss&origin=git) | [View ↗](https://app.qodo.ai/findings/47889f6d-04a3-444d-95db-f423b415ac0e)