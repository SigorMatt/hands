<img src="https://img.shields.io/badge/Medium-634FD1?style=flat-square" height="20px" alt="Remediation recommended">

8\. Kits over about 9.4 mib can't be applied from the laptop <code>🐞 Bug</code> <code>≡ Correctness</code>

<pre>
<b><i>apply_run</i></b> accepts zips up to <b><i>[files] kit_max_mb</i></b> (20 MiB by default) and base64-encodes the
entire kit into one socket request, while <b><i>call</i></b> checks that request against the daemon’s 12.5 MiB
<b><i>LINE_LIMIT</i></b>. A zip above roughly 9.4 MiB can therefore pass the kit-size check but be refused
before reaching the daemon with an “over the daemon’s line room” message, even though the phone’s
<b><i>kit</i></b> path accepts the same file.
</pre>


<details>
<summary><strong>Agent Prompt</strong></summary>

```
## Issue description
`hands kit apply` accepts zips up to `kit_max_mb`, but base64 encoding can push a valid kit above the socket request limit before the daemon receives it.

## Fix Focus Areas
- src/hands/kit.py[1495-1501]
- src/hands/cli.py[914-921]
- src/hands/cli.py[1443-1459]
- src/hands/runner.py[142-151]

## Recommended Fix
Either provide a bounded transfer mechanism that supports the configured kit limit, such as passing the zip path to the daemon for reading under `allowed_roots`, or make the advertised and enforced kit cap consistent with the encoded request limit. For the latter, use `min(kit_max_mb * MiB, LINE_LIMIT * 3 // 4 - envelope)` as the effective cap and have refusals name both limits. Test a kit above the current socket threshold but below the default kit limit.
```

<code>ⓘ Copy this prompt and use it to remediate the issue with your preferred AI generation tools</code>
</details>

[Dismiss ↗](https://app.qodo.ai/findings/f516de7d-2a59-4222-a754-7f90c61871b1?action=dismiss&origin=git) | [View ↗](https://app.qodo.ai/findings/f516de7d-2a59-4222-a754-7f90c61871b1)