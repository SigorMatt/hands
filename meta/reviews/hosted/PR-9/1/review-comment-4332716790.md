<img src="https://img.shields.io/badge/Medium-634FD1?style=flat-square" height="20px" alt="Remediation recommended">

3\. Test subprocesses can hang indefinitely <code>📘 Rule violation</code> <code>☼ Reliability</code>

<pre>
The new test fixtures invoke <b><i>git</i></b> and <b><i>gh</i></b> through <b><i>subprocess.run</i></b> without an explicit timeout. A
stalled local tool can block the test suite indefinitely, including repository setup in
<b><i>tests/test_ci_wait.py</i></b> and <b><i>tests/test_doctor.py</i></b>.
</pre>


<details>
<summary><strong>Agent Prompt</strong></summary>

```
## Issue description
Several new test subprocess calls omit explicit timeouts, so a stalled `git` or fake `gh` process can hang the quality gate indefinitely.

## Fix Focus Areas
- tests/test_ci_wait.py[47-51]
- tests/test_ci_wait.py[186-188]
- tests/test_ci_wait.py[369-381]
- tests/test_doctor.py[3580-3581]

## Recommended Fix
Add a bounded `timeout` argument to every new `subprocess.run` call, using a short test-appropriate limit and preserving the existing assertions and error handling.
```

<code>ⓘ Copy this prompt and use it to remediate the issue with your preferred AI generation tools</code>
</details>

[Dismiss ↗](https://app.qodo.ai/findings/8a7c6b70-87d8-45be-b1a2-8cdbceb331ee?action=dismiss&origin=git) | [View ↗](https://app.qodo.ai/findings/8a7c6b70-87d8-45be-b1a2-8cdbceb331ee)