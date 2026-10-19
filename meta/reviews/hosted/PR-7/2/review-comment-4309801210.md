<img src="https://img.shields.io/badge/Medium-634FD1?style=flat-square" height="20px" alt="Remediation recommended">

2\. Reviewers cannot verify the reported run <code>📘 Rule violation</code> <code>✧ Quality</code>

<pre>
The new <b><i>meta/FINAL-REPORT-27.md</i></b> records only seven-character commit prefixes and summarizes the
gate without embedding its raw output. Because the report is the artifact reviewers use to validate
the tip and tool claims, they cannot independently match the cited commits, counts, or messages to
the run.
</pre>


<details>
<summary><strong>Agent Prompt</strong></summary>

```
## Issue description
`meta/FINAL-REPORT-27.md` uses shortened commit identifiers and narrative test results without including the exact tool output, so reviewers cannot independently verify the reported run.

## Fix Focus Areas
- meta/FINAL-REPORT-27.md[8-11]
- meta/FINAL-REPORT-27.md[15-24]

## Recommended Fix
Replace shortened commit identifiers with full commit SHAs, retain explicit integer metrics for every reported check, and add clearly marked raw-output sections containing the verbatim output from each discussed tool invocation.
```

<code>ⓘ Copy this prompt and use it to remediate the issue with your preferred AI generation tools</code>
</details>

[Dismiss ↗](https://app.qodo.ai/findings/018c7020-5097-44de-82c4-cf0a5493b712?action=dismiss&origin=git) | [View ↗](https://app.qodo.ai/findings/018c7020-5097-44de-82c4-cf0a5493b712)