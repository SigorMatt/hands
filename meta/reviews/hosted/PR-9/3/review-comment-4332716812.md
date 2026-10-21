<img src="https://img.shields.io/badge/High-634FD1?style=flat-square" height="20px" alt="Action required">

2\. Applies from main take the mission-branch path and fail <code>🐞 Bug</code> <code>≡ Correctness</code>

<pre>
<b><i>PULL_REQUEST_APPLY</i></b> case (b) treats <b><i>main</i></b> as an in-flight mission branch because it is on
<b><i>origin</i></b>, is not a <b><i>kit/</i></b> branch, and has no MERGED or CLOSED head pull requests. When an apply
starts on <b><i>main</i></b> between missions, the builder commits and attempts to push there instead of opening
the kit pull request; protected <b><i>main</i></b> refuses the push, and the resulting <b><i>kit not applied pr=none</i></b>
reply stops the pipeline through <b><i>_apply_not_landed</i></b>.
</pre>


<details>
<summary><strong>Agent Prompt</strong></summary>

```
## Issue description
Case (b) of `PULL_REQUEST_APPLY` matches `main` as an in-flight mission branch. An apply started on `main`, the normal state between missions, therefore attempts a direct push to protected `main` instead of creating the kit branch and pull request.

## Fix Focus Areas
- src/hands/kit.py[222-257]
- docs/ARCHITECT-HANDBOOK.md[91-128]
- DESIGN.md[3750-3790]

## Recommended Fix
Explicitly exclude `main` from case (b), so an apply starting there proceeds through case (c). Update the matching prompt text in DESIGN.md and the handbook, update tests that pin the wording, and add a test asserting that case (b) excludes `main`.
```

<code>ⓘ Copy this prompt and use it to remediate the issue with your preferred AI generation tools</code>
</details>

[Dismiss ↗](https://app.qodo.ai/findings/9a353ce0-61e2-4400-a6c3-35ec8bf69897?action=dismiss&origin=git) | [View ↗](https://app.qodo.ai/findings/9a353ce0-61e2-4400-a6c3-35ec8bf69897)