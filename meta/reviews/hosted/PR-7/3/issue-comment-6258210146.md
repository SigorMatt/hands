<h3>Code Review by Qodo</h3>

<code>🐞 Bugs (1)</code>  <code>📘 Rule violations (1)</code>  <code>🔗 Cross-repo conflicts (0)</code>  <code>📜 Skill insights (0)</code>

<img src="https://www.qodo.ai/wp-content/uploads/2025/11/light-grey-line.svg" height="10%" alt="Grey Divider">

<br/>

<img src="https://img.shields.io/badge/High-634FD1?style=flat-square" height="20px" alt="Action required">

<details>
<summary>  1.  Role kits can rewrite the playbook by changing its case <code>🐞 Bug</code> <code>⛨ Security</code></summary>

<br/>

> <details open>
><summary>Description</summary>
><br/>
>
><pre>
><b><i>Spool.stored_kit_playbooks</i></b> (and <b><i>kit._owner_warning</i></b>) recognise only the exact names
><b><i>PLAYBOOK.toml</i></b> and <b><i>meta/PLAYBOOK.toml</i></b>, so an entry such as <b><i>playbook.toml</i></b>, <b><i>Playbook.toml</i></b> or
><b><i>Meta/PLAYBOOK.toml</i></b> passes <b><i>_carries_no_playbook</i></b> and the engine approves the apply. On a
>case-insensitive filesystem the apply&#x27;s <b><i>unzip -o</i></b> writes that entry over the real playbook, which
>the apply then commits. The role can therefore raise its own <b><i>max_architect_consults</i></b>, drop a stop
>rule or change the kickoff without the human seeing it, which is exactly what H-075 was meant to
>stop.
></pre>
></details>

> <details>
><summary>Code</summary>
><br/>
>
><code>[src/hands/spool.py[R578-583]](https://github.com/SigorMatt/hands/pull/7/files#diff-afef6fe420dcdc67164710839c508470d94b5a42c23284c4d8cbca7fe9a71221R578-R583)</code>
>
>```diff
>+        try:
>+            with zipfile.ZipFile(self.kit_dir(kit_id) / f"{name}.zip") as archive:
>+                names = set(archive.namelist())
>+        except (SpoolError, OSError, zipfile.BadZipFile, ValueError):
>+            return None
>+        return tuple(path for path in PLAYBOOK_PATHS if path in names)
>```
></details>

> <details>
><summary>Evidence</summary>
><br/>
>
><pre>
>The check is an exact set lookup against <b><i>PLAYBOOK_PATHS</i></b>. The kit judge already accepts that
>extraction folds case on some filesystems: <b><i>_path_problem</i></b> compares <b><i>.git</i></b> with <b><i>part.lower()</i></b>, and
><b><i>TOOLING_DIRS</i></b> is &quot;compared case-folded (<b><i>.GIT</i></b> is <b><i>.git</i></b>, <b><i>.Claude</i></b> is <b><i>.claude</i></b>, where the
>filesystem folds case)&quot;. No such folding is applied to the playbook names, so the new hold is the
>only check that ignores case-folding filesystems.
></pre>
>
> <code>[src/hands/spool.py\[574-583\]](https://github.com/SigorMatt/hands/blob/3ad66dd7898abd463a2e9ba7ba09851da4a1e601/src/hands/spool.py/#L574-L583)</code>
> <code>[src/hands/kit.py\[388-424\]](https://github.com/SigorMatt/hands/blob/3ad66dd7898abd463a2e9ba7ba09851da4a1e601/src/hands/kit.py/#L388-L424)</code>
> <code>[src/hands/playbook.py\[2283-2313\]](https://github.com/SigorMatt/hands/blob/3ad66dd7898abd463a2e9ba7ba09851da4a1e601/src/hands/playbook.py/#L2283-L2313)</code>
></details>

> <details>
><summary>Agent prompt</summary>
><br/>
>
>```
>The issue below was found during a code review. Follow the provided context and guidance below and implement a solution
>
>## Issue description
>The §43 hold detects a carried playbook by exact name, so a kit entry like `playbook.toml` or `Meta/PLAYBOOK.toml` is approved by the engine. On a case-folding filesystem it then overwrites the playbook in force.
>
>## Fix Focus Areas
>- src/hands/spool.py[574-583]
>- src/hands/kit.py[873-900]
>
>## Recommended Fix
>Compare each zip name with `name.casefold()` against `{p.casefold() for p in PLAYBOOK_PATHS}`, and return the entry name actually found. Apply the same case-folded match in `_owner_warning`. Add tests for `playbook.toml` and `Meta/PLAYBOOK.toml` being held.
>```
> <code>ⓘ Copy this prompt and use it to remediate the issue with your preferred AI generation tools</code>
></details>

[Dismiss ↗](https://app.qodo.ai/findings/b1cbd300-c9c9-450a-a5a8-75fb851d03f8?action=dismiss&origin=git) | [View ↗](https://app.qodo.ai/findings/b1cbd300-c9c9-450a-a5a8-75fb851d03f8)

<hr/>
</details>


<br/>

<img src="https://img.shields.io/badge/Medium-634FD1?style=flat-square" height="20px" alt="Remediation recommended">

<details>
<summary>  2.  Reviewers cannot verify the reported run <code>📘 Rule violation</code> <code>✧ Quality</code></summary>

<br/>

> <details open>
><summary>Description</summary>
><br/>
>
><pre>
>The new <b><i>meta/FINAL-REPORT-27.md</i></b> records only seven-character commit prefixes and summarizes the
>gate without embedding its raw output. Because the report is the artifact reviewers use to validate
>the tip and tool claims, they cannot independently match the cited commits, counts, or messages to
>the run.
></pre>
></details>

> <details>
><summary>Code</summary>
><br/>
>
><code>[meta/FINAL-REPORT-27.md[R8-11]](https://github.com/SigorMatt/hands/pull/7/files#diff-51890f17d626388c6a5ad3a762059347669a69138a497b9877a871984fa958e3R8-R11)</code>
>
>```diff
>+1b822a5. Gate: `./scripts/check` green three consecutive runs before every
>+unit commit (U0 excepted, red as the kit made it); at the tip
>+(38e44ee) 5047 tests, three consecutive green runs and a fourth with
>+`CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1` in its environment.
>```
></details>

> <details>
><summary>Evidence</summary>
><br/>
>
><pre>
>Compliance rule 3255379 requires reports to include full commit SHAs, explicit counts, and verbatim
>raw outputs. The report provides a short tip SHA and test count but no full SHA or raw
><b><i>./scripts/check</i></b> output, while the unit table also uses short SHAs.
></pre>
>
> <code>Rule 3255379: [Include exact SHAs, counts, and raw outputs in reports](https://app.qodo.ai/rules/3255379?state=active)</code>
> <code>[meta/FINAL-REPORT-27.md\[8-11\]](https://github.com/SigorMatt/hands/blob/3ad66dd7898abd463a2e9ba7ba09851da4a1e601/meta/FINAL-REPORT-27.md/#L8-L11)</code>
> <code>[meta/FINAL-REPORT-27.md\[15-24\]](https://github.com/SigorMatt/hands/blob/3ad66dd7898abd463a2e9ba7ba09851da4a1e601/meta/FINAL-REPORT-27.md/#L15-L24)</code>
></details>

> <details>
><summary>Agent prompt</summary>
><br/>
>
>```
>The issue below was found during a code review. Follow the provided context and guidance below and implement a solution
>
>## Issue description
>`meta/FINAL-REPORT-27.md` uses shortened commit identifiers and narrative test results without including the exact tool output, so reviewers cannot independently verify the reported run.
>
>## Fix Focus Areas
>- meta/FINAL-REPORT-27.md[8-11]
>- meta/FINAL-REPORT-27.md[15-24]
>
>## Recommended Fix
>Replace shortened commit identifiers with full commit SHAs, retain explicit integer metrics for every reported check, and add clearly marked raw-output sections containing the verbatim output from each discussed tool invocation.
>```
> <code>ⓘ Copy this prompt and use it to remediate the issue with your preferred AI generation tools</code>
></details>

[Dismiss ↗](https://app.qodo.ai/findings/018c7020-5097-44de-82c4-cf0a5493b712?action=dismiss&origin=git) | [View ↗](https://app.qodo.ai/findings/018c7020-5097-44de-82c4-cf0a5493b712)

<hr/>
</details>


<details>
<summary>  3.  <s>Holds with other causes show the playbook-owner reason</s> <code>✓ Resolved</code></summary>

<br/>

> <details open>
><summary>Description</summary>
><br/>
>
><pre>
><b><i>_announce_hold</i></b> now always passes <b><i>reason=self._owner_hold_reason(job)</i></b>, so every buttoned hold of
>a kit that contains a playbook gets §43&#x27;s &quot;a change of the playbook is the owner&#x27;s&quot; reason. That
>includes kits that <b><i>_escalate_kits</i></b> is about to deny for a §33 violation, and kits that
><b><i>_kit_bytes_unchanged</i></b> refused because the hash did not match. In those cases the human sees
>Approve/Deny buttons with a wrong reason for the hold, and the real cause shows only in a separate
>stop message.
></pre>
></details>

> <details>
><summary>Code</summary>
><br/>
>
><code>[src/hands/playbook.py[R2134-2136]](https://github.com/SigorMatt/hands/pull/7/files#diff-d4c45908377a317f0fbbccad6f8af7a74c4af564c4272d3cecc7126bf1be9204R2134-R2136)</code>
>
>```diff
>+            # §43: the reason of a hold whose stored kit carries the playbook names the
>+            # path, wherever the engine publishes it — a paused pipeline's included.
>+            outcome = self.hold(job, reason=self._owner_hold_reason(job))
>```
></details>

> <details>
><summary>Evidence</summary>
><br/>
>
><pre>
><b><i>_announce_hold(approved=False)</i></b> is called from <b><i>_escalate_kits</i></b> (before the engine denies the kit),
>from <b><i>_kit_bytes_unchanged</i></b> on a sha mismatch, from the paused-pipeline path and from the
><b><i>kit_apply_problem</i></b> path. Every one of those calls now goes through <b><i>_owner_hold_reason</i></b>, which
>looks only at whether the stored zip contains a playbook, not at why the hold is being published.
></pre>
>
> <code>[src/hands/playbook.py\[2111-2140\]](https://github.com/SigorMatt/hands/blob/3ad66dd7898abd463a2e9ba7ba09851da4a1e601/src/hands/playbook.py/#L2111-L2140)</code>
> <code>[src/hands/playbook.py\[2315-2327\]](https://github.com/SigorMatt/hands/blob/3ad66dd7898abd463a2e9ba7ba09851da4a1e601/src/hands/playbook.py/#L2315-L2327)</code>
> <code>[src/hands/playbook.py\[2329-2349\]](https://github.com/SigorMatt/hands/blob/3ad66dd7898abd463a2e9ba7ba09851da4a1e601/src/hands/playbook.py/#L2329-L2349)</code>
> <code>[src/hands/playbook.py\[2382-2389\]](https://github.com/SigorMatt/hands/blob/3ad66dd7898abd463a2e9ba7ba09851da4a1e601/src/hands/playbook.py/#L2382-L2389)</code>
></details>

> <details>
><summary>Agent prompt</summary>
><br/>
>
>```
>The issue below was found during a code review. Follow the provided context and guidance below and implement a solution
>
>## Issue description
>Every engine-published hold of a kit containing a playbook gets §43's reason, even when it is held or denied for a different cause (an escalation or a sha mismatch).
>
>## Fix Focus Areas
>- src/hands/playbook.py[2111-2140]
>- src/hands/playbook.py[2254-2256]
>
>## Recommended Fix
>Add an optional `reason` parameter to `_announce_hold`, defaulting to None. Pass `owner_hold_reason(...)` only from `_release_kit`'s `_carries_no_playbook` branch, and from the paused-pipeline branch if §43 requires it there. Other callers then keep the gate's reason. Reuse the names `_carries_no_playbook` already read, rather than reopening the zip on the event loop.
>```
> <code>ⓘ Copy this prompt and use it to remediate the issue with your preferred AI generation tools</code>
></details>

<hr/>
</details>


<details>
<summary>  4.  <s>Paused playbook kits lose hold reasons</s> <code>✓ Resolved</code></summary>

<br/>

> <details open>
><summary>Description</summary>
><br/>
>
><pre>
><b><i>_owner_hold_reason</i></b> reaches notifications only through <b><i>_announce_hold</i></b>, while <b><i>defer_hold</i></b> skips
>holds filed during a pause and startup republishes held jobs without a reason override. When either
>path handles a role-filed kit carrying a playbook, the human sees only <b><i>apply &lt;name&gt;</i></b>, not the
>playbook path and ownership reason.
></pre>
></details>

> <details>
><summary>Code</summary>
><br/>
>
><code>[src/hands/playbook.py[R2134-2136]](https://github.com/SigorMatt/hands/pull/7/files#diff-d4c45908377a317f0fbbccad6f8af7a74c4af564c4272d3cecc7126bf1be9204R2134-R2136)</code>
>
>```diff
>+            # §43: the reason of a hold whose stored kit carries the playbook names the
>+            # path, wherever the engine publishes it — a paused pipeline's included.
>+            outcome = self.hold(job, reason=self._owner_hold_reason(job))
>```
></details>

> <details>
><summary>Evidence</summary>
><br/>
>
><pre>
><b><i>Api.send</i></b> files the hold after asking <b><i>defer_hold</i></b>; a paused pipeline makes that method return
>false, so the event listener publishes the event&#x27;s generic reason directly. Startup likewise calls
><b><i>publish_hold(job)</i></b> without an override, although the new override and owner-reason helper are
>available.
></pre>
>
> <code>[src/hands/playbook.py\[2087-2100\]](https://github.com/SigorMatt/hands/blob/3ad66dd7898abd463a2e9ba7ba09851da4a1e601/src/hands/playbook.py/#L2087-L2100)</code>
> <code>[src/hands/api.py\[438-449\]](https://github.com/SigorMatt/hands/blob/3ad66dd7898abd463a2e9ba7ba09851da4a1e601/src/hands/api.py/#L438-L449)</code>
> <code>[src/hands/daemon.py\[861-879\]](https://github.com/SigorMatt/hands/blob/3ad66dd7898abd463a2e9ba7ba09851da4a1e601/src/hands/daemon.py/#L861-L879)</code>
> <code>[src/hands/daemon.py\[407-436\]](https://github.com/SigorMatt/hands/blob/3ad66dd7898abd463a2e9ba7ba09851da4a1e601/src/hands/daemon.py/#L407-L436)</code>
> <code>[src/hands/playbook.py\[2315-2327\]](https://github.com/SigorMatt/hands/blob/3ad66dd7898abd463a2e9ba7ba09851da4a1e601/src/hands/playbook.py/#L2315-L2327)</code>
></details>

> <details>
><summary>Agent prompt</summary>
><br/>
>
>```
>The issue below was found during a code review. Follow the provided context and guidance below and implement a solution
>
>## Issue description
>Playbook-bearing kits filed while the pipeline is paused, or republished as held after restart, bypass the new reason override and show only the gate's generic apply reason.
>
>## Fix Focus Areas
>- src/hands/playbook.py[2087-2100]
>- src/hands/playbook.py[2134-2136]
>- src/hands/daemon.py[407-436]
>- src/hands/daemon.py[861-879]
>
>## Recommended Fix
>Derive and publish the playbook-specific reason for qualifying architect-filed holds on immediate and startup publication paths as well as deferred publication. Preserve the gate's stored reason and add tests for a kit filed during a pause and one republished after restart.
>```
> <code>ⓘ Copy this prompt and use it to remediate the issue with your preferred AI generation tools</code>
></details>

<hr/>
</details>



<img src="https://www.qodo.ai/wp-content/uploads/2025/11/light-grey-line.svg" height="10%" alt="Grey Divider">


<!-- qodo-context:start -->
<details><summary><strong>Context sources</strong></summary>

<div>&#x274C; Tickets: failed to load — Ticket collection could not establish complete evidence</div>
<div>&#x2705; Compliance rules (platform): <a href="https://app.qodo.ai/rules?state=active&amp;scopes=/SigorMatt/hands/"><code>43 rules</code></a></div>
<details>
<summary>&#x2705; Cross-repo context — <a href="https://app.qodo.ai/management/repositories/77e6b9e3-9009-4fbe-bd8c-e1c4bd92a98f">repo relationships</a></summary>
<div>&nbsp;&nbsp;Explored: <code>repo: <a href="https://github.com/SigorMatt/discotrade/tree/d67f708682a498f2f11881acccb15cc41c71188a">SigorMatt/discotrade</a> (sha: d67f7086)</code> — <a href="https://app.qodo.ai/management/relationships?repoId=77e6b9e3-9009-4fbe-bd8c-e1c4bd92a98f&amp;relatedRepoId=f8bc154f-fef0-4515-a253-775ba818fa12&amp;view=table">View relationship</a></div>
</details>
<div>Review mode: <code>Auto: 🧠 Deep</code>: Large cross-cutting change spans many independent logic paths and enforcement hooks.</div>
<!-- qodo-context:end -->
</details>

<img src="https://www.qodo.ai/wp-content/uploads/2025/11/light-grey-line.svg" height="10%" alt="Grey Divider">



<!-- qodo-daily-tip:start -->

<details>
<summary><strong>Tip of the day</strong></summary>

<br/>

<pre>💡 Did you know, you can import rules and skills only from the repositories your team follows</pre>

<a href="https://docs.qodo.ai/tips-and-tricks">More tips ↗</a> | <a href="https://app.qodo.ai/configurations?tab=display-preferences">Customize Qodo ↗</a> | <a href="https://docs.qodo.ai">Qodo docs ↗</a>

</details>

<img src="https://www.qodo.ai/wp-content/uploads/2025/11/light-grey-line.svg" height="10%" alt="Grey Divider">
<!-- qodo-daily-tip:end -->


<!-- https://github.com/SigorMatt/hands/commit/3ad66dd7898abd463a2e9ba7ba09851da4a1e601 -->

<a href="https://www.qodo.ai"><img src="https://www.qodo.ai/wp-content/uploads/2025/03/qodo-logo.svg" width="80" alt="Qodo Logo"></a>