<img src="https://img.shields.io/badge/Medium-634FD1?style=flat-square" height="20px" alt="Remediation recommended">

7\. Architects can read unrelated hands files <code>🐞 Bug</code> <code>⛨ Security</code>

<pre>
<b><i>Reads</i></b> adds the whole <b><i>HANDS_DOCS</i></b> directory as an architect read root rather than limiting access
to the handbook and templates. In a source-tree install, <b><i>docs_root()</i></b> can make that directory the
hands repository root, so guarded Bash reads also accept unrelated files under that repository.
</pre>


<details>
<summary><strong>Agent Prompt</strong></summary>

```
## Issue description
The new architect read root includes the entire hands source repository in source-tree installs, not just the documentation needed for consultations.
## Fix Focus Areas
- driver/hooks/bash_guard.py[643-665]
- src/hands/config.py[135-147]
## Recommended Fix
Allow architect reads beneath the handbook and templates paths within HANDS_DOCS instead of beneath HANDS_DOCS itself. Test the source-tree fallback against a file outside those paths.
```

<code>ⓘ Copy this prompt and use it to remediate the issue with your preferred AI generation tools</code>
</details>

[Dismiss ↗](https://app.qodo.ai/findings/0f88b604-1c17-42e0-b517-77ba0bf44298?action=dismiss&origin=git) | [View ↗](https://app.qodo.ai/findings/0f88b604-1c17-42e0-b517-77ba0bf44298)