<img src="https://img.shields.io/badge/Medium-634FD1?style=flat-square" height="20px" alt="Remediation recommended">

7\. Kits can still weaken the gate their pr merges on <code>🐞 Bug</code> <code>⛨ Security</code>

<pre>
<b><i>carries_ci</i></b> only treats an entry as CI when its casefolded path begins with <b><i>.github/</i></b> or equals
<b><i>scripts/check</i></b>. The gate that <b><i>scripts/check</i></b> runs (<b><i>uv sync</i></b>, <b><i>ruff check .</i></b>, <b><i>pytest</i></b>) is also
configured by <b><i>pyproject.toml</i></b>, <b><i>uv.lock</i></b> and <b><i>tests/conftest.py</i></b>. An architect-filed kit that
changes one of those files (for example pytest <b><i>addopts</i></b>, a conftest that deselects tests, or ruff
excludes) is still approved by the engine without a human hold, and its own pull request&#x27;s check
then runs the weakened gate it merges on, which is the exact risk §45&#x27;s hold is meant to close.
</pre>


<details>
<summary><strong>Agent Prompt</strong></summary>

```
## Issue description
`carries_ci` treats only `.github/` and `scripts/check` as the repository's CI. The gate that `scripts/check` runs is also driven by `pyproject.toml` (pytest/ruff config, dependencies), `uv.lock` and `tests/conftest.py`, so a role-filed kit that touches them is engine-approved and can weaken its own PR's check.

## Fix Focus Areas
- src/hands/spool.py[171-183]
- src/hands/kit.py[1003-1015]
- docs/ARCHITECT-HANDBOOK.md[147-162]

## Recommended Fix
Extend `carries_ci` to also match (casefolded) `pyproject.toml`, `uv.lock`, any `conftest.py`, and `scripts/` as a whole, or a configurable list. Update the hold reason text, the handbook and DESIGN wording, and the tests to match.
```

<code>ⓘ Copy this prompt and use it to remediate the issue with your preferred AI generation tools</code>
</details>

[Dismiss ↗](https://app.qodo.ai/findings/e5755419-309b-46a9-938e-af25dc3ef73c?action=dismiss&origin=git) | [View ↗](https://app.qodo.ai/findings/e5755419-309b-46a9-938e-af25dc3ef73c)