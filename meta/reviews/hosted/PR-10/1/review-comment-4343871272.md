<img src="https://img.shields.io/badge/High-634FD1?style=flat-square" height="20px" alt="Action required">

1\. Reviewers can merge unreviewed changes <code>🐞 Bug</code> <code>≡ Correctness</code>

<pre>
The moved-branch check compares <b><i>origin/&lt;branch&gt;</i></b> with <b><i>reviewed:</i></b> before the protocol&#x27;s later `git
pull --ff-only`, which can advance the local branch after that comparison. If someone pushes in that
interval, the review commit is placed on the unreviewed tip, its push succeeds, and
<b><i>--match-head-commit</i></b> accepts that review commit for the merge.
</pre>


<details>
<summary><strong>Agent Prompt</strong></summary>

```
## Issue description
The branch can advance between the new reviewed-head comparison and the protocol's subsequent fast-forward pull, allowing an unreviewed commit into the merge.

## Fix Focus Areas
- meta/REVIEW-PROTOCOL.md[268-278]
- meta/REVIEW-PROTOCOL.md[295-301]
- templates/REVIEW-PROTOCOL.md[268-278]
- templates/REVIEW-PROTOCOL.md[295-301]

## Recommended Fix
For a branch review, perform the checkout and pull before the final comparison, and require the resulting local HEAD and fetched remote head to equal the full `reviewed:` SHA before making the review commit. Treat a mismatch as the moved-branch blocker; retain the refused-push handling for movement after that check.
```

<code>ⓘ Copy this prompt and use it to remediate the issue with your preferred AI generation tools</code>
</details>

[Dismiss ↗](https://app.qodo.ai/findings/090ab43e-d800-4188-ba90-5b3c872e7734?action=dismiss&origin=git) | [View ↗](https://app.qodo.ai/findings/090ab43e-d800-4188-ba90-5b3c872e7734)