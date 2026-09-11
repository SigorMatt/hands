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
