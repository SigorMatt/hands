<img src="https://img.shields.io/badge/Medium-634FD1?style=flat-square" height="20px" alt="Remediation recommended">

4\. Reports omit auditable tool evidence <code>📘 Rule violation</code> <code>✧ Quality</code>

<pre>
<b><i>meta/FINAL-REPORT-23.md</i></b> records short commit identifiers and prose summaries of test runs without
full SHAs or verbatim tool output. When readers rely on the report to verify the claimed units and
checks, they cannot reproduce the exact commits, counts, messages, or line references from the
report itself.
</pre>


<details>
<summary><strong>Agent Prompt</strong></summary>

```
## Issue description
The final report uses abbreviated commit identifiers and summarizes test results without including exact integer metrics and raw command output.

## Fix Focus Areas
- meta/FINAL-REPORT-23.md[16-20]
- meta/FINAL-REPORT-23.md[128-134]

## Recommended Fix
Replace each abbreviated commit reference with the full commit SHA, add explicit test and failure counts for every reported check, and include clearly marked verbatim raw output sections for the test, lint, and other external tool invocations discussed in the report.
```

<code>ⓘ Copy this prompt and use it to remediate the issue with your preferred AI generation tools</code>
</details>

[Dismiss ↗](https://app.qodo.ai/findings/f8015f64-2e5e-4d21-8c79-2cb7cb0b83ba?action=dismiss&origin=git) | [View ↗](https://app.qodo.ai/findings/f8015f64-2e5e-4d21-8c79-2cb7cb0b83ba)