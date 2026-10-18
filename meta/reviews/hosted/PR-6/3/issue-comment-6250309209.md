<h3>Code Review by Qodo</h3>

<code>🐞 Bugs (0)</code>  <code>📘 Rule violations (0)</code>  <code>🔗 Cross-repo conflicts (2)</code>  <code>📜 Skill insights (0)</code>

<img src="https://www.qodo.ai/wp-content/uploads/2025/11/light-grey-line.svg" height="10%" alt="Grey Divider">

<br/>

<img src="https://img.shields.io/badge/High-634FD1?style=flat-square" height="20px" alt="Action required">

<details>
<summary>  1.  Discotrade skips mid-mission rulings <code>🔗 Cross-repo conflict</code> <code>≡ Correctness</code></summary>

<br/>

> <details open>
><summary>Description</summary>
><br/>
>
><pre>
>The new decisions-kit route tells operators to apply an owner file and use <b><i>go</i></b>, relying on the
>added §R instruction to make the builder carry out its steps. Discotrade’s active mission 20 brief
>has an older §R without that instruction, so a mid-mission decisions kit can be committed while the
>resumed builder continues from its checkpoint without acting on the ruling.
></pre>
></details>

> <details>
><summary>Code</summary>
><br/>
>
><code>[templates/BUILDER-N-PROMPT.md[R98-101]](https://github.com/SigorMatt/hands/pull/6/files#diff-4abca313f3571f857a4d82f471a44d49fcb38a568dba8775b9e3aa7e82e30dcaR98-R101)</code>
>
>```diff
>+the answer came with a file to commit first. If a `plan: decisions <date>
>+(owner)` commit is on the branch after the checkpoint's last update and the
>+checkpoint does not record its "For the builder" steps as done, carry them
>+out first, record them in the checkpoint, and continue.
>```
></details>

> <details>
><summary>Evidence</summary>
><br/>
>
><pre>
>Hands makes the new route depend on §R, but discotrade’s current §R only describes dirty-tree
>recovery; its checkpoint shows that mission is still in progress.
></pre>
>
> <code>[hands -&gt; discotrade](https://app.qodo.ai/management/relationships?repoId=77e6b9e3-9009-4fbe-bd8c-e1c4bd92a98f&relatedRepoId=f8bc154f-fef0-4515-a253-775ba818fa12&view=table)</code>
> <code>[templates/BUILDER-N-PROMPT.md\[95-101\]](https://github.com/SigorMatt/hands/blob/d3c4f151575026c8aa29c3f057cbf45d248b9c63/templates/BUILDER-N-PROMPT.md/#L95-L101)</code>
> <code>[docs/ARCHITECT-HANDBOOK.md\[843-853\]](https://github.com/SigorMatt/hands/blob/d3c4f151575026c8aa29c3f057cbf45d248b9c63/docs/ARCHITECT-HANDBOOK.md/#L843-L853)</code>
> <code>[External repo: SigorMatt/discotrade, meta/BUILDER-20-PROMPT.md \[128-136\]](https://github.com/SigorMatt/discotrade/blob/4ed47b479a493492b5c6ba805bffd8271b76a8fd/meta/BUILDER-20-PROMPT.md/#L128-L136)</code>
> <code>[External repo: SigorMatt/discotrade, meta/CHECKPOINT.md \[3-9\]](https://github.com/SigorMatt/discotrade/blob/4ed47b479a493492b5c6ba805bffd8271b76a8fd/meta/CHECKPOINT.md/#L3-L9)</code>
></details>

> <details>
><summary>Agent prompt</summary>
><br/>
>
>```
>The issue below was found during a code review. Follow the provided context and guidance below and implement a solution
>
>## Issue description
>The decisions-kit-and-go route depends on recovery wording absent from discotrade’s active brief.
>
>## Fix Focus Areas
>- templates/BUILDER-N-PROMPT.md[98-101]
>- docs/ARCHITECT-HANDBOOK.md[843-853]
>- meta/BUILDER-20-PROMPT.md[128-136]
>
>## Recommended Fix
>Update discotrade’s active and future mission briefs with the owner-file recovery rule before recommending this route there, or provide a compatible route for briefs that lack it.
>```
> <code>ⓘ Copy this prompt and use it to remediate the issue with your preferred AI generation tools</code>
></details>

[Dismiss ↗](https://app.qodo.ai/findings/cb656a99-3a8c-4279-af18-84de7917ee2c?action=dismiss&origin=git) | [View ↗](https://app.qodo.ai/findings/cb656a99-3a8c-4279-af18-84de7917ee2c)

<hr/>
</details>


<br/>

<img src="https://img.shields.io/badge/Medium-634FD1?style=flat-square" height="20px" alt="Remediation recommended">

<details>
<summary>  2.  <s>Failed consults leave the pipeline running</s> <code>✓ Resolved</code></summary>

<br/>

> <details open>
><summary>Description</summary>
><br/>
>
><pre>
><b><i>_consult_for_human</i></b> persists an unpause before it calls <b><i>enqueue</i></b>, without restoring the stop if
>enqueue fails. A queue or spool failure can therefore leave a stopped pipeline running even though
>no architect consultation was created.
></pre>
></details>

> <details>
><summary>Code</summary>
><br/>
>
><code>[src/hands/playbook.py[R2542-2545]](https://github.com/SigorMatt/hands/pull/6/files#diff-d4c45908377a317f0fbbccad6f8af7a74c4af564c4272d3cecc7126bf1be9204R2542-R2545)</code>
>
>```diff
>+        self._unpause("resume")
>+        started = await self.enqueue(
>+            role=ARCHITECT,
>+            context="clear",
>```
></details>

> <details>
><summary>Evidence</summary>
><br/>
>
><pre>
>The new path saves the resumed state before awaiting enqueue; daemon enqueue can reject queue
>admission or fail while creating the job, and the API catches only consultation-specific refusals.
></pre>
>
> <code>[src/hands/playbook.py\[2533-2551\]](https://github.com/SigorMatt/hands/blob/d3c4f151575026c8aa29c3f057cbf45d248b9c63/src/hands/playbook.py/#L2533-L2551)</code>
> <code>[src/hands/daemon.py\[543-580\]](https://github.com/SigorMatt/hands/blob/d3c4f151575026c8aa29c3f057cbf45d248b9c63/src/hands/daemon.py/#L543-L580)</code>
> <code>[src/hands/api.py\[600-609\]](https://github.com/SigorMatt/hands/blob/d3c4f151575026c8aa29c3f057cbf45d248b9c63/src/hands/api.py/#L600-L609)</code>
></details>

> <details>
><summary>Agent prompt</summary>
><br/>
>
>```
>The issue below was found during a code review. Follow the provided context and guidance below and implement a solution
>
>## Issue description
>A failed human-consult enqueue currently clears a persisted pipeline stop without starting a consultation.
>## Fix Focus Areas
>- src/hands/playbook.py[2533-2566]
>- src/hands/api.py[593-609]
>## Recommended Fix
>Make job creation succeed before persisting the unpause, or restore the prior stopped state on enqueue failure. Keep the consultation event consistent with the created job.
>```
> <code>ⓘ Copy this prompt and use it to remediate the issue with your preferred AI generation tools</code>
></details>

<hr/>
</details>


<details>
<summary>  3.  <s>Ruling follow-ups refuse consultation</s> <code>✓ Resolved</code></summary>

<br/>

> <details open>
><summary>Description</summary>
><br/>
>
><pre>
>Route 5 says to send an owner kit using route 4 and then run <b><i>consult</i></b>, but route 4 ends by running
><b><i>go</i></b>. If the human follows that sequence immediately, <b><i>go</i></b> starts a builder job and the new consult
>path refuses the request while that job is queued or running.
></pre>
></details>

> <details>
><summary>Code</summary>
><br/>
>
><code>[docs/ARCHITECT-HANDBOOK.md[R857-859]](https://github.com/SigorMatt/hands/pull/6/files#diff-2ad26343d21a57c4b0e1450bc61bad64fd9ee975037b345cdcf9841cdab2905eR857-R859)</code>
>
>```diff
>+   blocked mission under a playbook without the blocked→consult rule): any
>+   owner file first, as route 4's kit; then `consult <secret> <reason>` (§16);
>+   at the laptop `hands consult`.
>```
></details>

> <details>
><summary>Evidence</summary>
><br/>
>
><pre>
>The two new routes prescribe <b><i>go</i></b> followed by <b><i>consult</i></b>; the phone go path starts builder work, and
><b><i>consult_refusal</i></b> rejects builder jobs in running, queued, or held states.
></pre>
>
> <code>[docs/ARCHITECT-HANDBOOK.md\[840-859\]](https://github.com/SigorMatt/hands/blob/d3c4f151575026c8aa29c3f057cbf45d248b9c63/docs/ARCHITECT-HANDBOOK.md/#L840-L859)</code>
> <code>[src/hands/phone.py\[493-516\]](https://github.com/SigorMatt/hands/blob/d3c4f151575026c8aa29c3f057cbf45d248b9c63/src/hands/phone.py/#L493-L516)</code>
> <code>[src/hands/api.py\[584-590\]](https://github.com/SigorMatt/hands/blob/d3c4f151575026c8aa29c3f057cbf45d248b9c63/src/hands/api.py/#L584-L590)</code>
></details>

> <details>
><summary>Agent prompt</summary>
><br/>
>
>```
>The issue below was found during a code review. Follow the provided context and guidance below and implement a solution
>
>## Issue description
>The consultation route inherits a `go` command that makes the ensuing consultation fail its builder-busy check.
>## Fix Focus Areas
>- docs/ARCHITECT-HANDBOOK.md[843-859]
>- docs/ARCHITECT-HANDBOOK.md[924-925]
>## Recommended Fix
>Spell out when the owner kit has finished applying and when, if at all, `go` should run. If `go` is required first, instruct the human to wait for its builder job to end before issuing `consult`.
>```
> <code>ⓘ Copy this prompt and use it to remediate the issue with your preferred AI generation tools</code>
></details>

<hr/>
</details>


<details>
<summary>  4.  Discotrade consultations lack reviews <code>🔗 Cross-repo conflict</code> <code>≡ Correctness</code></summary>

<br/>

> <details open>
><summary>Description</summary>
><br/>
>
><pre>
><b><i>human_consult_prompt</i></b> replaces the review with a reason and starts the architect with no review
>job. Discotrade’s standing architect instructions require a consultation on a review outcome and
>require reading the review it names, leaving that required input undefined when its operator uses
>the new <b><i>consult</i></b> command.
></pre>
></details>

> <details>
><summary>Code</summary>
><br/>
>
><code>[src/hands/playbook.py[R3406-3410]](https://github.com/SigorMatt/hands/pull/6/files#diff-d4c45908377a317f0fbbccad6f8af7a74c4af564c4272d3cecc7126bf1be9204R3406-R3410)</code>
>
>```diff
>+def human_consult_prompt(reason: str, brief: ArchitectBrief | None = None) -> str:
>+    """§42: the architect consult prompt of a consultation the human started — §31's
>+    prompt with the review's sections replaced by the human's reason, verbatim, under
>+    `HUMAN_REASON_HEADING`; its first line is `HUMAN_HEAD`."""
>+    return _architect_prompt(HUMAN_EVENT, None, brief, reason=reason)
>```
></details>

> <details>
><summary>Evidence</summary>
><br/>
>
><pre>
>The new prompt explicitly supplies a human reason instead of a review, while discotrade’s
>project-specific instructions mandate a review outcome and a named review.
></pre>
>
> <code>[hands -&gt; discotrade](https://app.qodo.ai/management/relationships?repoId=77e6b9e3-9009-4fbe-bd8c-e1c4bd92a98f&relatedRepoId=f8bc154f-fef0-4515-a253-775ba818fa12&view=table)</code>
> <code>[src/hands/playbook.py\[3406-3415\]](https://github.com/SigorMatt/hands/blob/d3c4f151575026c8aa29c3f057cbf45d248b9c63/src/hands/playbook.py/#L3406-L3415)</code>
> <code>[src/hands/playbook.py\[3352-3365\]](https://github.com/SigorMatt/hands/blob/d3c4f151575026c8aa29c3f057cbf45d248b9c63/src/hands/playbook.py/#L3352-L3365)</code>
> <code>[External repo: SigorMatt/discotrade, meta/ARCHITECT.md \[1-5\]](https://github.com/SigorMatt/discotrade/blob/4ed47b479a493492b5c6ba805bffd8271b76a8fd/meta/ARCHITECT.md/#L1-L5)</code>
> <code>[External repo: SigorMatt/discotrade, meta/ARCHITECT.md \[30-43\]](https://github.com/SigorMatt/discotrade/blob/4ed47b479a493492b5c6ba805bffd8271b76a8fd/meta/ARCHITECT.md/#L30-L43)</code>
></details>

> <details>
><summary>Agent prompt</summary>
><br/>
>
>```
>The issue below was found during a code review. Follow the provided context and guidance below and implement a solution
>
>## Issue description
>Human-started consultations omit the review required by discotrade’s standing architect procedure.
>
>## Fix Focus Areas
>- src/hands/playbook.py[3406-3410]
>- meta/ARCHITECT.md[1-5]
>- meta/ARCHITECT.md[30-43]
>
>## Recommended Fix
>Update discotrade’s architect instructions to define the human-reason path, including what replaces the named review when deciding whether to file a kit or escalate, before enabling that command for the project.
>```
> <code>ⓘ Copy this prompt and use it to remediate the issue with your preferred AI generation tools</code>
></details>

[Dismiss ↗](https://app.qodo.ai/findings/54f50653-a20c-47bc-b540-550d7837bb58?action=dismiss&origin=git) | [View ↗](https://app.qodo.ai/findings/54f50653-a20c-47bc-b540-550d7837bb58)

<hr/>
</details>


<details><summary><ins><strong>View medium (3)</strong></ins></summary><br/>
<details>
<summary>  5.  <s>Rejected consults fill the kit directory</s> <code>✓ Resolved</code></summary>

<br/>

> <details open>
><summary>Description</summary>
><br/>
>
><pre>
><b><i>_consult_command</i></b> leaves the permanently linked attachment in <b><i>kit_dir</i></b> when UTF-8 decoding or the
>final consultation check refuses it. Repeated authenticated requests with invalid text, or requests
>refused after a state change during download, accumulate files even though no consultation starts.
></pre>
></details>

> <details>
><summary>Code</summary>
><br/>
>
><code>[src/hands/phone.py[R624-628]](https://github.com/SigorMatt/hands/pull/6/files#diff-6d175ae5f33f6b544ecf5e01493181c805135928b88647bc51a3ff9971544b75R624-R628)</code>
>
>```diff
>+                data = await asyncio.to_thread((directory / written).read_bytes)
>+                attached = consult_file_text(data, "the attachment")
>+            except (OSError, ValueError) as exc:
>+                problem = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
>+                return await self._refuse("consult", problem)
>```
></details>

> <details>
><summary>Evidence</summary>
><br/>
>
><pre>
>The download links a permanent named file and cleans only its temporary file; both subsequent
>refusal branches return without deleting the permanent attachment.
></pre>
>
> <code>[src/hands/phone.py\[617-632\]](https://github.com/SigorMatt/hands/blob/d3c4f151575026c8aa29c3f057cbf45d248b9c63/src/hands/phone.py/#L617-L632)</code>
> <code>[src/hands/phone.py\[1034-1043\]](https://github.com/SigorMatt/hands/blob/d3c4f151575026c8aa29c3f057cbf45d248b9c63/src/hands/phone.py/#L1034-L1043)</code>
> <code>[src/hands/api.py\[593-608\]](https://github.com/SigorMatt/hands/blob/d3c4f151575026c8aa29c3f057cbf45d248b9c63/src/hands/api.py/#L593-L608)</code>
></details>

> <details>
><summary>Agent prompt</summary>
><br/>
>
>```
>The issue below was found during a code review. Follow the provided context and guidance below and implement a solution
>
>## Issue description
>A phone consult can retain a downloaded attachment after refusing the command, allowing unused files to accumulate.
>## Fix Focus Areas
>- src/hands/phone.py[617-632]
>- src/hands/phone.py[1034-1043]
>## Recommended Fix
>Track the path returned by `_fetch` and remove that specific newly written file if decoding or `start_consult` fails. Preserve attachments for successfully started consultations.
>```
> <code>ⓘ Copy this prompt and use it to remediate the issue with your preferred AI generation tools</code>
></details>

<hr/>
</details>


<details>
<summary>  6.  <s>A refused consult can stop a running pipeline</s> <code>✓ Resolved</code></summary>

<br/>

> <details open>
><summary>Description</summary>
><br/>
>
><pre>
><b><i>Api.consult_refusal</i></b> calls <b><i>engine.reload()</i></b>, which runs the full <b><i>PlaybookEngine._load()</i></b>, before
>it checks for a busy builder, aux or architect. <b><i>_load()</i></b> stops and pauses the pipeline when the
>playbook does not load (dirty, uncommitted, wrong config). It also swaps the in-memory playbook and
>clears <b><i>last_rule</i></b> in the middle of a running job. So a phone <b><i>consult</i></b> (asked twice, before and
>after the fetch) or a <b><i>hands consult</i></b> sent while the builder is working can stop the pipeline. It
>can also change which rules decide that builder&#x27;s end, even though the consult itself is then
>refused as busy.
></pre>
></details>

> <details>
><summary>Code</summary>
><br/>
>
><code>[src/hands/api.py[R569-576]](https://github.com/SigorMatt/hands/pull/6/files#diff-16f021e493ba18b1e5f11a7ee4f78300324921ac8ae5a15bbe45cab098c59139R569-R576)</code>
>
>```diff
>+        engine = self.daemon.playbook
>+        await engine.reload()
>+        why = engine.consult_mode_refusal()
>+        if why is not None:
>+            return why
>+        why = self._role_busy(ARCHITECT_ROLE)
>+        if why is not None:
>+            return why
>```
></details>

> <details>
><summary>Evidence</summary>
><br/>
>
><pre>
><b><i>consult_refusal</i></b> awaits <b><i>engine.reload()</i></b> first. <b><i>reload()</i></b> is <b><i>await self._load()</i></b>. On a
><b><i>PlaybookError</i></b>, <b><i>_load</i></b> calls <b><i>self.stop(...)</i></b>, which sets <b><i>paused=True</i></b>, appends a <b><i>stop</i></b> event
>and notifies &#x27;the pipeline stopped&#x27; whenever the pipeline is not already paused. On success it
>replaces <b><i>self.playbook</i></b>, re-anchors the series and clears <b><i>last_rule</i></b> when the sha changed.
>Elsewhere this only happens when a job starts (<b><i>on_job_start</i></b>). The busy-role refusals
>(<b><i>_role_busy</i></b>) only run after the reload.
></pre>
>
> <code>[src/hands/api.py\[557-591\]](https://github.com/SigorMatt/hands/blob/d3c4f151575026c8aa29c3f057cbf45d248b9c63/src/hands/api.py/#L557-L591)</code>
> <code>[src/hands/playbook.py\[1623-1677\]](https://github.com/SigorMatt/hands/blob/d3c4f151575026c8aa29c3f057cbf45d248b9c63/src/hands/playbook.py/#L1623-L1677)</code>
> <code>[src/hands/playbook.py\[2990-3032\]](https://github.com/SigorMatt/hands/blob/d3c4f151575026c8aa29c3f057cbf45d248b9c63/src/hands/playbook.py/#L2990-L3032)</code>
> <code>[src/hands/phone.py\[613-632\]](https://github.com/SigorMatt/hands/blob/d3c4f151575026c8aa29c3f057cbf45d248b9c63/src/hands/phone.py/#L613-L632)</code>
></details>

> <details>
><summary>Agent prompt</summary>
><br/>
>
>```
>The issue below was found during a code review. Follow the provided context and guidance below and implement a solution
>
>## Issue description
>`Api.consult_refusal` reloads the playbook through `PlaybookEngine._load()` before it checks for busy roles. `_load()` can call `stop()`, which pauses the pipeline and notifies. It also replaces the playbook in force and clears `last_rule` while a job is running. So a consult that is going to be refused anyway can stop a running pipeline or change the rules for the running job.
>
>## Fix Focus Areas
>- src/hands/api.py[557-591]
>- src/hands/playbook.py[1623-1627]
>
>## Recommended Fix
>Run the `_role_busy` checks for architect/builder/aux, and the `kit_wait` check, before calling `engine.reload()`. Only reload once no role is busy. Also make `reload()` side-effect free on failure: load the playbook without `stop()` (for example, a `_load(stop_on_error=False)` variant that only sets `load_error`), so the refusal text reports the load error without stopping the pipeline. Add a test: a consult sent while a builder job is running with a dirty playbook leaves `pipeline.json` unpaused and `last_rule` unchanged.
>```
> <code>ⓘ Copy this prompt and use it to remediate the issue with your preferred AI generation tools</code>
></details>

<hr/>
</details>


<details>
<summary>  7.  <s>Exhausted jobs stay stopped after resume</s> <code>✓ Resolved</code></summary>

<br/>

> <details open>
><summary>Description</summary>
><br/>
>
><pre>
>The operator table tells a human to run <b><i>resume</i></b> after a <b><i>limits.max_resumes reached</i></b> stop, but that
>command only clears the pipeline pause. When the resume limit has been reached, the limit manager
>schedules no new builder job, so following this row does not restart the work.
></pre>
></details>

> <details>
><summary>Code</summary>
><br/>
>
><code>[docs/ARCHITECT-HANDBOOK.md[908]](https://github.com/SigorMatt/hands/pull/6/files#diff-2ad26343d21a57c4b0e1450bc61bad64fd9ee975037b345cdcf9841cdab2905eR908-R908)</code>
>
>```diff
>+| `hands: the pipeline stopped` — limits.max_resumes reached: <role> has been resumed <k> time(s) with no `done` in between and is limited again | the human alone — route 7 | after the capture, `resume <secret>` | `bash scripts/capture-quota-stop.sh <project>`, then `hands resume` |
>```
></details>

> <details>
><summary>Evidence</summary>
><br/>
>
><pre>
>The limit manager returns without scheduling a resume at the maximum, while the public resume API
>delegates to a pipeline unpause rather than job creation.
></pre>
>
> <code>[src/hands/limits.py\[361-399\]](https://github.com/SigorMatt/hands/blob/d3c4f151575026c8aa29c3f057cbf45d248b9c63/src/hands/limits.py/#L361-L399)</code>
> <code>[src/hands/api.py\[1524-1533\]](https://github.com/SigorMatt/hands/blob/d3c4f151575026c8aa29c3f057cbf45d248b9c63/src/hands/api.py/#L1524-L1533)</code>
> <code>[src/hands/playbook.py\[3072-3092\]](https://github.com/SigorMatt/hands/blob/d3c4f151575026c8aa29c3f057cbf45d248b9c63/src/hands/playbook.py/#L3072-L3092)</code>
></details>

> <details>
><summary>Agent prompt</summary>
><br/>
>
>```
>The issue below was found during a code review. Follow the provided context and guidance below and implement a solution
>
>## Issue description
>The exhausted-resume row prescribes a command that unpauses the pipeline but does not restart its limited job.
>## Fix Focus Areas
>- docs/ARCHITECT-HANDBOOK.md[868-874]
>- docs/ARCHITECT-HANDBOOK.md[907-908]
>## Recommended Fix
>Give `max_resumes reached` its own recovery route that identifies how the human resolves the exhausted limit and starts work again. Reserve the ordinary `resume` instruction for the case where the limit manager has scheduled a job resume.
>```
> <code>ⓘ Copy this prompt and use it to remediate the issue with your preferred AI generation tools</code>
></details>

<hr/>
</details>


</details>

<img src="https://www.qodo.ai/wp-content/uploads/2025/11/light-grey-line.svg" height="10%" alt="Grey Divider">


<!-- qodo-context:start -->
<details><summary><strong>Context sources</strong></summary>

<div>&#x274C; Tickets: failed to load — Ticket collection could not establish complete evidence</div>
<div>&#x2705; Compliance rules (platform): <a href="https://app.qodo.ai/rules?state=active&amp;scopes=/SigorMatt/hands/"><code>8 rules</code></a></div>
<details>
<summary>&#x2705; Cross-repo context — <a href="https://app.qodo.ai/management/repositories/77e6b9e3-9009-4fbe-bd8c-e1c4bd92a98f">repo relationships</a></summary>
<div>&nbsp;&nbsp;Explored: <code>repo: <a href="https://github.com/SigorMatt/discotrade/tree/4ed47b479a493492b5c6ba805bffd8271b76a8fd">SigorMatt/discotrade</a> (sha: 4ed47b47)</code> — <a href="https://app.qodo.ai/management/relationships?repoId=77e6b9e3-9009-4fbe-bd8c-e1c4bd92a98f&amp;relatedRepoId=f8bc154f-fef0-4515-a253-775ba818fa12&amp;view=table">View relationship</a></div>
</details>
<div>Review mode: <code>Auto: 🧠 Deep</code>: Dense multi-path logic with secrets, jobs, files, and redaction risks.</div>
<!-- qodo-context:end -->
</details>

<img src="https://www.qodo.ai/wp-content/uploads/2025/11/light-grey-line.svg" height="10%" alt="Grey Divider">



<!-- qodo-daily-tip:start -->

<details>
<summary><strong>Tip of the day</strong></summary>

<br/>

<pre>💡 Did you know, you can move or hide resolved findings to focus on what still needs action</pre>

<a href="https://docs.qodo.ai/tips-and-tricks">More tips ↗</a> | <a href="https://app.qodo.ai/configurations?tab=display-preferences">Customize Qodo ↗</a> | <a href="https://docs.qodo.ai">Qodo docs ↗</a>

</details>

<img src="https://www.qodo.ai/wp-content/uploads/2025/11/light-grey-line.svg" height="10%" alt="Grey Divider">
<!-- qodo-daily-tip:end -->


<!-- https://github.com/SigorMatt/hands/commit/d3c4f151575026c8aa29c3f057cbf45d248b9c63 -->

<a href="https://www.qodo.ai"><img src="https://www.qodo.ai/wp-content/uploads/2025/03/qodo-logo.svg" width="80" alt="Qodo Logo"></a>