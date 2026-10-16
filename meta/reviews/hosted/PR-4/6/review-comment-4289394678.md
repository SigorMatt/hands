<img src="https://img.shields.io/badge/Medium-634FD1?style=flat-square" height="20px" alt="Remediation recommended">

8\. A misparsed code review reads as a clean review <code>🐞 Bug</code> <code>≡ Correctness</code>

<pre>
<b><i>run</i></b> takes <b><i>findings(body)</i></b> as the whole truth: when <b><i>_FINDING</i></b> matches no `&lt;summary&gt;N.
…&lt;/summary&gt;<b><i> block, it prints </i></b>verdict: no finding open in the Code Review comment (it numbers
none)<b><i> and exits 0, even if the header counts it just parsed with </i></b>categories()` say there are
findings. A small change in the bot&#x27;s markup (a <b><i>&lt;b&gt;</i></b> around the number, a different list tag, say)
would turn a review with open findings into a pass, and both the builder&#x27;s last unit and the
reviewer&#x27;s sub-agent rely on this verdict.
</pre>


<details>
<summary><strong>Agent Prompt</strong></summary>

```
## Issue description
`hands hosted-review` exits 0 with "no finding open" whenever the findings regex matches nothing, even when the header counts say findings exist.

## Fix Focus Areas
- src/hands/hosted.py[196-220]
- src/hands/hosted.py[376-389]

## Recommended Fix
Parse the number in each header category label (`(\d+)`) and add them up. If the total is above zero and `findings(body)` returns fewer entries than that (or none), print a 'could not parse the findings' verdict and return a non-zero exit (1, or a new code) rather than 0. Add a test with a body whose header counts findings but whose `<summary>` markup the regex does not match.
```

<code>ⓘ Copy this prompt and use it to remediate the issue with your preferred AI generation tools</code>
</details>

[Dismiss ↗](https://app.qodo.ai/findings/90471514-81a7-496b-9598-4e68e6813ef8?action=dismiss&origin=git) | [View ↗](https://app.qodo.ai/findings/90471514-81a7-496b-9598-4e68e6813ef8)