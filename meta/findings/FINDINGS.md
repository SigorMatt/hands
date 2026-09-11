# FINDINGS — the ledger

Numbered H-### entries. Append-only; corrections append. Every entry has
severity, component, symptom with evidence (command and output, file and
line), direction, and Status: open | fixing | fixed <sha> | deferred <gate>
| rejected <reason> | tombstoned.

---

## H-001 — transcript path: the `.` case of the project-dir dashing is unwitnessed

Severity: low · Component: runner (DESIGN §2, "the transcript path follows from it")

Symptom. §2 says the transcript path follows from the session id but does not
say how `~/.claude/projects/<dir>` is spelled. Derived from evidence on this
machine (claude 2.1.268), by reading the `cwd` recorded inside each transcript
and comparing it with the directory the transcript sits in:

    $ cd ~/.claude/projects && for f in $(find . -name '*.jsonl'); do \
        d=$(dirname "$f"); c=$(grep -o '"cwd":"[^"]*"' "$f" | head -1 | cut -d'"' -f4); \
        [ -n "$c" ] && echo "$c  ->  ${d#./}"; done | sort -u
    /home/msi/Downloads/weaveviz                  ->  -home-msi-Downloads-weaveviz
    /home/msi/agile-skills-throwaway/envel        ->  -home-msi-agile-skills-throwaway-envel
    /home/msi/git/hands                           ->  -home-msi-git-hands
    /home/msi/git_2/flying_squirrel               ->  -home-msi-git-2-flying-squirrel
    /tmp/claude-1000/-home-msi-git-agile-skills/74627f4c-.../scratchpad/probe
                                                  ->  -tmp-claude-1000--home-msi-git-agile-skills-74627f4c-...-scratchpad-probe

    $ ls ~/.claude/projects | grep '\.' | wc -l
    0

That settles four rules: `/` → `-` (including the leading one), `_` → `-`,
an existing `-` stays `-`, and letter case is preserved (`Downloads`). It does
**not** settle `.`: no project directory on this machine comes from a path
containing a dot, so there is no witness either way.

Direction. `src/hands/runner.py:project_dir_name` implements
`re.sub(r"[^a-zA-Z0-9]", "-", str(cwd))`, the single rule that reproduces every
line of evidence above exactly (it predicts `.` → `-` as a consequence, not as
an assumption). The consequence of being wrong is bounded: `transcript_path` is
a *derived* record field — nothing in hands opens the file, and the runner never
requires it to exist — so a wrong dot rule mis-addresses `hands tail` for a role
whose cwd contains a dot, and nothing else. Revisit with a real capture from
such a cwd.

Status: open

---

## H-002 — §6 calls the limit field an "error category"; on the wire it is `error`

Severity: low · Component: runner (DESIGN §6, "Limits")

Symptom. §6 says hands "detects a limit from the `api_retry` error category
`rate_limit`". There is no `category` field in that event. The schema in the
installed binary is:

    $ strings -a ~/.local/share/claude/versions/2.1.268 | grep -o '.\{300\}"api_retry".\{500\}'
    …c({type:R("system"),subtype:R("api_retry"),attempt:E().int(),max_retries:E().int(),
      retry_delay_ms:E().int(),error_status:E().int().nullable(),error:a_(), …

    $ strings -a … | grep -o 'a_=m(()=>.\{0,300\}'
    a_=m(()=>Y(["authentication_failed","oauth_org_not_allowed","account_on_hold",
      "verification_required","billing_error","rate_limit","overloaded","invalid_request",
      "model_not_found","server_error","unknown","max_output_tokens","cloud_credential_error"]))

So the category §6 means is the `error` field, an enum that does contain
`rate_limit`; also note the event is `type: "system"` with
`subtype: "api_retry"`, not `type: "api_retry"`.

Direction. The design's intent is unambiguous and only the field name is off, so
this is recorded rather than escalated. `runner._on_event` reads `error` and
falls back to `category`, and stores the whole event as the job's raw limit
notice. If §6 is ever revised, say `error`.

Status: open

---

## H-003 — every flag DESIGN §2 names exists in claude 2.1.268

Severity: none (verification record) · Component: runner (DESIGN §2)

Checked before writing the §2 invocation, because `--permission-prompts` was
suspected of not being real:

    $ claude --help | grep -E -- '--permission-prompts|--output-format|-p, --print|-r, --resume|--model|--verbose'
      --output-format <format>   … (choices: "text", "json", "stream-json")
      --permission-prompts <target>  Who answers permission prompts with --print:
                                     "host" … or "none" (nobody: anything that would
                                     prompt is denied automatically …)
                                     (choices: "host", "none", default: "host")
      -p, --print                Print response and exit …
      -r, --resume [value]       Resume a conversation by session ID …
      --model <model>            Model for the current session …
      --verbose                  Override verbose mode setting from config

All six exist with the spelling §2 uses, and `--permission-prompts` does take
`none`. No flag was dropped. (`claude -p` was not run: that would spend quota.)

Status: fixed — nothing to change

---

## H-004 — §6's `origin` vocabulary has no value for a limit resume

Severity: low · Component: limits (DESIGN §6, "Limits — DECIDED: automatic, no nudge")

Symptom. §6's job record says `origin (driver|playbook|cli)` — the three clients
that can ask for work. The same section then has hands create a job that no
client asked for:

    DESIGN.md:236  … sends `role.resume_line` (`Resume WORKPLAN.md`) as a new
                   `clear` job for the builder, or re-sends the same prompt for aux.

A limit resume is hands resuming itself: not a human at a terminal (`cli`), not
the driver session (`driver`), and not a playbook rule firing (`playbook`). The
vocabulary is closed in code —

    $ grep -n 'ORIGINS' src/hands/spool.py
    87:ORIGINS = frozenset({"driver", "playbook", "cli"})  # §6

— so U5 had to pick one of the three or invent a fourth.

Direction. A fourth value (`limit`, say) is the honest spelling and is what §6
should say if it is ever revised; inventing it silently would have put a value on
the wire that `hands jobs --origin` and the §9 remote face do not know. So U5
picks the least wrong existing value, `playbook`: it is the "hands did this on
its own, from a pre-planned rule" origin rather than a human's client, and §10
already gives the playbook authority over `max_resumes`. Nothing is lost by the
choice, because `resumed_from` — non-null exactly on a limit resume — is what
actually identifies one, and both the job record and the `resume` inbox event
carry it. Revisit together with §10's playbook-issued sends, which will want to
be distinguishable from limit resumes by something better than `resumed_from`.

Status: open

---

## H-005 — §6's automatic limit resume and §10's `builder.limited → resume` are the same resume

Severity: low · Component: playbook/limits (DESIGN §6 "Limits", §10 "Actions")

Symptom. §6 makes the limit resume automatic and unconditional:

    DESIGN.md:236  … parses the reset time, sleeps until then, and sends
                   `role.resume_line` … as a new `clear` job for the builder

and §10's example playbook *also* has a rule for the same event:

    DESIGN.md:383  [[rule]]
    DESIGN.md:384  on = "builder.limited"
    DESIGN.md:385  then = "resume"

Both fire on one `limited` job. Taken literally that is two resume jobs for one
limit — and the playbook's one would fire immediately, before the reset §6 just
parsed, straight back into the limit.

Direction. U7 treats §6 as the owner of a limit resume: `LimitManager` schedules
it for the reset, and a `then = "resume"` rule on a `limited` job records that
the rule fired (one `playbook.rule` inbox event, with a note) and enqueues
nothing. The rule is therefore the architect's *authorisation* of the resume,
not a second mechanism, which is also the only reading under which §10's
`max_resumes` and §6's counter are one counter. `resume` on an event that §6
does not handle (`builder.orphaned`, the example's next rule) does enqueue, and
counts against the same `limits.max_resumes`. Tested by
`tests/test_playbook.py::test_a_limited_job_leaves_the_resume_to_section_6`.
If §10 is ever revised, say which unit owns the limit resume.

Status: open

---

## H-006 — §10 does not say which value `only_if_run_in = "auto_runs"` checks

Severity: low · Component: playbook (DESIGN §10, "Example", "Placeholders")

Symptom. §10 gives the check only by example:

    DESIGN.md:369  prompt = "Execute WORKPLAN.md run {n+1}"
    DESIGN.md:370  only_if_run_in = "auto_runs"   # {n+1} must be listed above, else stop

"`{n+1}` must be listed above" names the placeholder of *that* prompt. Nothing
says what is checked when the prompt has two placeholders, or none, or when the
rule carries no `verdict` regex to take a named group from.

Direction. U7 reads the run from the prompt: the value checked is the computed
value of the prompt's single verdict-group placeholder (`{n+1}` → 4), and a
playbook whose `only_if_run_in` rule has anything other than exactly one such
placeholder is refused when the playbook is *loaded*, not when it fires — so the
ambiguity can never reach a running pipeline. `only_if_run_in` also takes no
spelling but `"auto_runs"`, and requires `[limits] auto_runs` to be non-empty.
A cleaner spelling, if §10 is ever revised, is an explicit `run = "{n+1}"` key,
which would need no inference at all.

Status: open

---

## H-007 — §11's "fake event" for the wake check has no command behind it

Severity: low · Component: doctor (DESIGN §11, "hands doctor checks this path
end to end on first install (a fake event, and the driver session confirming it
woke)")

Symptom. §11 asks doctor to check the wake path with "a fake event". Nothing in
the command surface of §4 files an inbox event on demand, and the two commands
that sound as if they might do not:

    $ grep -n 'append_event' src/hands/playbook.py | sed -n 1,3p
    890:        if write_event:
    891:            self.spool.append_event("stop", {**(payload or {}), "reason": reason})

`stop` events are written by the engine's own `stop()`; `hands pause`
(`PlaybookEngine.pause`, playbook.py:895) sets `state.paused` and writes no
event at all, so a driver blocked on `hands wait --for stop,held` is not woken
by it. `hands doctor` also cannot file one itself: it runs without a daemon by
design (§14 step 1), and the spool belongs to the daemon.

Direction. U10 does not add an event-injection command — that would be new CLI
the design does not have, and the only honest "fake event" hands can produce is
a real one. `hands doctor` prints a procedure that uses a **gated send** as the
event: `hands send --role aux --context clear --gate "doctor wake check" …`
enters `held`, files a real `job.held` event (api.py:148), notifies ntfy, and
never starts a turn, so it costs nothing; `hands deny <job>` clears it, and
`hands resume` clears the pipeline stop an unplanned `job.held` causes when a
playbook is loaded. If §11 is ever revised, either name this procedure or say
which command files the fake event.

Status: open
