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

Status: open — no unit in mission 2 touched it, and nothing on this machine
can close it: the `.` rule still has no witness because no project directory
here comes from a dotted path. Closing it needs a real capture from such a
cwd, which is an observation, not a change. Blast radius unchanged (`hands
tail` for a dotted cwd).
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

Status: fixed — by DESIGN v3.1 itself, not by a mission-2 unit. §6 now reads
"a `system`/`api_retry` event whose `error` field is `rate_limit` (there is no
`category` field on the wire; H-002)" (DESIGN.md:236-238), which is what
`runner._on_event` already implements; the `category` fallback stays, because
it costs nothing and no real limit event has ever been seen by hands.
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
Status: fixed a67c4b0 — DESIGN v3.1 §6 spells the vocabulary `driver|playbook|cli|limit`.
Mission 2 U1: `ORIGINS` gains `limit`, §6's limit resume is filed with
`origin = "limit"` (a §10 `resume` rule on `failed`/`orphaned` stays
`playbook`), both `resume` inbox events carry `origin`, and `hands jobs
--origin <o>` filters on it and refuses a spelling outside the four.
`resumed_from` is unchanged.

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

Status: fixed 34b4ede — by DESIGN v3.1 §10 plus mission 2 U3. §10 now states
the ownership outright ("`limited` is owned by §6 and a `resume` rule on
`builder.limited` is accepted as an authorization that enqueues nothing") and
§6 says "§6 is the sole owner of the limit resume; the playbook never issues a
second one (H-005)" — which is the reading mission 1 U7 already implemented.
U3 removed the `builder.limited` rule from the §10 example fixture with the
design; `test_a_limited_job_leaves_the_resume_to_section_6` keeps its own
playbook (`LIMITED_BOOK`) so the authorization path is still proven.
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
Status: fixed 34b4ede — DESIGN v3.1 §10 took the explicit key. Mission 2 U3:
rules carry `run = "<expr>"` (one named group from the rule's own `verdict`,
`{n}`/`{n+1}`), refused at load when `[limits] auto_runs` is empty or the
expression names a group the `verdict` does not define; `only_if_run_in` is
refused at load with a message naming `run`. The inference is gone.

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
Status: fixed 267ee01 — DESIGN v3.1 §11 named the procedure. Mission 2 U4: `hands pause`
goes through the engine's own `stop()`, so it files the `stop` event with reason
`paused by human` and notifies like any other stop; a second pause files nothing
(`stop()` keeps "one stop, one notification") and no playbook needs to be loaded,
so the check is runnable at install time. `hands resume` closes the cycle with a
new `pipeline.resumed` event (as does the send that un-pauses, §10); resuming an
un-paused pipeline writes nothing. Doctor's wake procedure now offers `hands
pause` first and keeps the gated send, which is still the only way to witness a
real `job.held`.

---

## H-008 — `role.resume_line` has a default, so a limit resume cannot re-send the limited prompt

Severity: low · Component: config/limits (DESIGN §6 "Limits", §13)
Filed by: the architect, in DESIGN v3.1 §18 (not by a mission-1 builder);
entered here by mission 2 U0 so the ledger covers H-001..H-008.

Symptom. §13's example config sets `resume_line = "Resume WORKPLAN.md"`, and
mission 1 read that as a field every role has:

    $ grep -n 'resume_line' src/hands/config.py
    79:    resume_line: str
    335:        resume_line=_str(table, "resume_line", DEFAULT_RESUME_LINE, where, path),

so the field is non-optional with a default, and the builder's limit resume is
unconditionally that line:

    $ sed -n 456,460p src/hands/limits.py
        """§6: the builder gets `role.resume_line` as a new `clear` job; aux the same prompt."""
        …
            prompt, context = role.resume_line, "clear"

That is right for the spanweave form, whose kickoff line is `Resume
WORKPLAN.md`. It is wrong for the agile-skills form used by this repository,
whose kickoff line is checkpoint-driven (`Read meta/BUILDER-N-PROMPT.md and
execute the mission below its divider`): a limit resume there must re-send the
limited job's own prompt, and with a default in place a project cannot ask for
that — omitting the key silently selects the spanweave line.

Direction. §6 (v3.1) makes the key optional: absent, a builder limit resume
re-sends the limited job's prompt; set, it sends the line. Aux is unchanged
(always the same prompt again). §10's `resume` action reads the same way ("the
same prompt again, or the role's resume line when configured"). `hands doctor`
reports which of the two behaviours each role has, because the difference is
invisible until a limit is hit.

Status: open
Status: fixed 8448b6f — mission 2 U2: `role.resume_line` is `str | None` with no default
(`DEFAULT_RESUME_LINE` is gone). `RoleConfig.resume_prompt(prompt)` is the one
place the rule lives, so §6's limit resume (`hands.limits`) and §10's `resume`
action (`hands.playbook`) cannot drift: the builder gets a `clear` job carrying
the resume line when the config sets one, otherwise the resumed job's own
prompt; aux is unchanged. `hands doctor`'s role check prints the behaviour it
has (`RoleConfig.resume_behaviour`), since a limit is otherwise the first time
the difference shows.

---

## H-009 — §4's prose example for `hands jobs` omits `--origin`

Severity: low · Component: DESIGN §7 prose (DESIGN.md:258), against §4's
command table (DESIGN.md:159)
Filed by: mission 3 U0, carrying over `meta/reviews/REVIEW-2.md` Notes
("Design-side staleness, for a finding, not for a builder").

Symptom. Mission 2 U1 (a67c4b0) added `--origin` to `hands jobs` because §4's
table asks for it:

    $ sed -n 159p DESIGN.md
    | `jobs` | `[--role r] [--origin o] [--grep pat] [--since d] [-n]` | recent job summaries |

The §7 prose example one section later was not updated with it:

    $ sed -n 258p DESIGN.md
        hands jobs [--role builder] [--grep "run 3"] [--since 2d]

The code is right (`hands jobs --help` lists `--origin`, and
`tests/test_library.py::test_jobs_filters_by_origin` covers it); only the
design's own illustration is behind. Nothing is broken by it — but §7 is the
section a reader goes to for the job library, so the omission reads as "the
filter does not exist".

Direction. For the architect: add `[--origin limit]` (or similar) to the
DESIGN.md:258 example, or say in §7 that the table in §4 is the full arg
list and the examples are illustrative. Builders do not edit `DESIGN.md`, so
no mission unit can close this.

Status: open

---

## H-010 — §12 requires `MultiEdit` in the driver deny list; no such tool exists in Claude Code 2.1.x

Severity: low · Component: driver kit (DESIGN §12, `driver/settings.json`)
Filed by: mission 3 U0, ahead of U6, so that unit does not have to stop on a
design conflict it is not allowed to resolve.

Symptom. §12 enumerates the driver's enforcement:

    $ sed -n 502,503p DESIGN.md
    - `driver/settings.json` — enforcement: `permissions.deny` for Edit, Write,
      MultiEdit, NotebookEdit; `permissions.allow` for `Bash(hands *)`,

and the kit and its test both follow it:

    $ grep -n 'MultiEdit' driver/settings.json tests/test_docs.py
    driver/settings.json:6:      "MultiEdit",
    tests/test_docs.py:117:    for tool in ("Edit", "Write", "MultiEdit", "NotebookEdit"):

Claude Code 2.1.x has no `MultiEdit` tool (Edit takes the multi-edit case),
so the rule denies a name nothing can call and the CLI warns about an unknown
tool in `permissions.deny` when the driver session starts. The rule is inert,
and the warning is the only thing it produces.

Direction. `meta/BUILDER-3-PROMPT.md` U6 directs the kit to drop the rule,
which contradicts §12's list as written; the brief is taken as the
architect's instruction and U6 implements it (kit, test, and this memo
together). For the architect: strike `MultiEdit` from §12's deny list in the
next design revision, or say there that the list is by capability and the kit
carries whatever tool names the installed Claude Code actually has.

Status: open — U6 dropped `"MultiEdit"` from `driver/settings.json`
and `tests/test_docs.py` (which now asserts it is absent, citing this memo).
The kit denies Edit, Write, NotebookEdit; DESIGN §12 line 503 still lists
MultiEdit, so design and kit disagree until the architect resolves it.

Amendment, 2026-09-12 (mission 4 U0; REVIEW-3 should-fix 2). Appended, not a
rewrite: everything above is left as it was filed. Both observations are real
and they are about different things.

1. The CLI warning is real. `2.1.268` (and `2.1.269`) carries the string, and
   it is about the *rule*, not about the tool being callable:

       $ grep -ao '.\{60\}matches no known tool.\{25\}' \
             ~/.local/share/claude/versions/2.1.269
       …`Permission ${mn.ruleBehavior} rule "${gr(mn.ruleValue)}" matches no
       known tool — check for typos.`…

   This is what was observed at driver start on 2.1.268 and what the memo
   above generalised from.

2. `MultiEdit` *is* a known permission-rule tool name in 2.1.269, which the
   memo's headline denies. REVIEW-3 found it in the deny-rule normalizer, and
   that reproduces here:

       $ grep -ac 'MultiEdit' ~/.local/share/claude/versions/2.1.269
       9
       $ grep -aoc '"Write","Edit","MultiEdit","NotebookEdit"' … 2.1.269
       2
       $ grep -ao 'toolName==="MultiEdit"?"Edit"' … 2.1.269
       toolName==="MultiEdit"?"Edit"

   So the rule normalises to an `Edit` deny rather than being discarded. "Not
   offered to a model today" is a different claim from "no such tool name".

Decision (DESIGN §20, and §12 as revised in v3.3): **keep the rule.** A deny
rule that normalises to `Edit` costs a start-up warning and nothing else;
dropping it cost coverage on a name the binary still maps. Mission 4 U1 is the
unit that restores `"MultiEdit"` to `driver/settings.json` and turns
`tests/test_docs.py` back to asserting it is present.

Status: open — decision taken above, not yet on disk when this amendment was
written. The headline stays as filed and is corrected by point 2.

Status: closed on disk — mission 4 U1 put the rule back: `driver/settings.json`
denies `Edit`, `Write`, `MultiEdit`, `NotebookEdit` again and
`tests/test_docs.py::test_the_driver_denies_every_writing_tool` asserts
`MultiEdit` is present, citing this amendment. The sha is U1's single commit
(`driver: the git allowlist applies to every git token …`), which carries this
line too, so it cannot name itself; `git log -1 --format=%H -- driver/settings.json`
resolves it. The headline above stays as filed; the design side (§12 as revised
in v3.3 keeps MultiEdit) is settled, so nothing is left open for the architect.

---

## H-011 — `stop.suppressed` is inside `stop`'s wake namespace, so `--for stop` wakes on it

Severity: low · Component: DESIGN §10/§20 (the event name) against §11's wake
spelling (`src/hands/spool.py:126-146`, `resolve_kinds`)
Filed by: mission 4, after U3 (c108bfe) implemented §20's pipeline-state rules.

Symptom. §10 as revised says a later stop over an existing one "is recorded in
the inbox only" — no notification. U3 implements that with an event of the kind
the mission brief names, `stop.suppressed`. But `hands wait --for <spec>`
matches a name three ways, and the third is a namespace:

    $ sed -n 140,144p src/hands/spool.py
        matched = {
            kind
            for kind in EVENT_KINDS
            if kind == name or kind.endswith(f".{name}") or kind.startswith(f"{name}.")
        }

so `--for stop` — which is what `driver/CLAUDE.md` rule 8 and DESIGN §12 tell
the driver to arm — now resolves to `{stop, stop.suppressed}`. The driver wakes
on a stop that was deliberately not notified.

Why it is small. The pipeline is already stopped when a suppressed stop lands,
so the driver it wakes is being woken about a pipeline it has already been told
about; rule 2 sends it to `hands inbox` first, where the `stop.suppressed`
record explains itself. Nothing is lost and nothing is silently dropped; the
cost is one extra wake per suppressed stop.

Direction. For the architect, three ways out, in increasing order of change:
(1) accept it — a suppressed stop is still pipeline news, and the driver reads
the inbox before acting; (2) name the kind `stop_suppressed`, outside the
namespace, and keep `--for stop` meaning exactly one kind; (3) make the
namespace rule opt-in (`--for 'stop.*'`). Builders do not edit `DESIGN.md`, so
no mission unit can close this; U3 implemented the name the brief gave it.

Decision, 2026-09-12 (architect, DESIGN v3.4 §21; recorded by mission 5 U0).
Way (2): the kind is renamed **`pipeline.stop_suppressed`**. It sits in the
`pipeline` namespace beside `pipeline.resumed`, so `--for stop` resolves to
`{stop}` again and the driver is not woken by a stop that was deliberately not
notified; a session that does want them arms `--for pipeline`. Mission 5 U5
makes the rename in code, tests and docs; the acceptance is that
`grep -rn 'stop\.suppressed' src tests docs driver` returns nothing.

Status: closed by mission 5 U5 (the decision above; see meta/FINAL-REPORT-5.md)

Status: closed on disk, 2026-09-12 — mission 5 U5 made the rename: `EVENT_KINDS`
in `src/hands/spool.py`, `stop()` in `src/hands/playbook.py`, the `_limit_stop`
docstring in `src/hands/daemon.py`, `docs/PLAYBOOK.md` and every test that named
the kind. `grep -rn 'stop\.suppressed' src tests docs driver` returns nothing,
and `tests/test_wake.py::test_for_stop_is_the_stop_kind_and_nothing_else` pins
`resolve_kinds("stop") == {"stop"}` with `resolve_kinds("pipeline") ==
{"pipeline.resumed", "pipeline.stop_suppressed"}` beside it, so the namespace
cannot be re-entered without a red test. The unit commit carries this line, so
it cannot name itself; `git log -1 --format=%H -- src/hands/spool.py` resolves
it.

---

## H-012 — "cap plus one quarter" does not cover JSON escaping; the cap is measured on the wire

Severity: low · Component: DESIGN §4 (`send` row) against `src/hands/cli.py`
(`_wire_bytes`, `_checked_prompt`) and `src/hands/daemon.py:63` (`_LINE_LIMIT`)
Filed by: mission 5, U4 (prompt delivery), while implementing §4's revised
`send` row.

Symptom. §4 now says the client refuses "a missing, unreadable, non-regular,
empty or over-10 MB file on either route ... and the wire carries UTF-8
unescaped so the daemon's line room (cap plus one quarter) fits any accepted
prompt". `ensure_ascii=False` fixes the transcoding half — 9 MiB of CJK is
9 MiB on the wire instead of 18 — but JSON still escapes three things, and one
of them is not a rounding error:

    a quote     -> 2 bytes per byte     10 MiB of quotes -> 20 MiB
    a backslash -> 2 bytes per byte
    a NUL       -> 6 bytes per byte     10 MiB of NULs   -> 60 MiB

So a file *at* the cap by size can be 2x or 6x the cap on the wire, and a line
room of cap + cap/4 (12.5 MiB) does not hold it. Taken as bytes-of-file, §4's
enumeration would accept those two files and they would die exactly where
review 4 should-fix 3 says they must not: a broken pipe, with nothing in the
daemon log.

What U4 did. Read §4's "fits any accepted prompt" as the binding half: the cap
is measured on the prompt **as it appears on the wire**, so a prompt that
escapes past `MAX_PROMPT_BYTES` is refused client-side, with one line naming
the path and both sizes ("is 10485760 bytes, 20971520 once escaped for the
wire, over the 10485760 byte cap of §2"). Under that reading every accepted
prompt is at most the cap on the wire and the remaining quarter — 2.5 MiB — is
the envelope's, which no `--file`-bearing command line can exceed. The claim in
§4 becomes true rather than approximately true.

What the architect may want to say. Two things are the architect's, not a
builder's: (1) §4's list of refusals does not name this one, and a reader of
§4 alone would expect a 10 MiB file of quotes to be sent; (2) the cap is
therefore stricter than `Runner.run`'s (`runner.py:283`, raw UTF-8 bytes), so
the client refuses prompts the runner would have accepted — deliberate here,
because the daemon could never have received them, but it is a second meaning
for "10 MB" alongside the 10 MB / 10 MiB question already recorded. Either
spell the wire measurement into §4, or raise the line room to six times the
cap and let the daemon refuse the escaped monsters itself.

Status: open (design wording; the behaviour is implemented and tested at U4)

**Decision, 2026-09-12 (DESIGN v3.5 §4 `send` row, §22; recorded by mission 6
U0).** The architect took the first branch: the wire measurement is spelled
into §4, and it is widened from the prompt to the **whole request**. The client
builds the request, measures the exact bytes it will write (prompt, `--file`
payloads, gate, envelope), and refuses before connecting when the total exceeds
the daemon's line room — "so a request never fails inside the socket (H-012)".
The line room is not raised. The second meaning of "10 MB" the finding names
stays: the client's cap is on wire bytes, `Runner.run`'s is on raw UTF-8, and
the client is the stricter of the two by design. Mission 6 U1 implements this
on both prompt routes and rewrites the two sentences (`docs/INTEGRATION.md`,
`src/hands/daemon.py`) that said the envelope could not overflow.

Status: decided (DESIGN v3.5 §4); closed on disk by mission 6 U1

Status: closed on disk, 2026-09-12 (mission 6 U1). `hands.cli._wire_size`
counts the exact JSON line `call` writes — the shape serialized with every
string emptied, plus `_wire_bytes` per string — and `_checked_request` refuses
inside `call`, before the socket is opened, when that line is over
`runner.LINE_LIMIT` (the constant moved there from `daemon.py`, so the daemon's
reader and the client's measurement are one number). The message is one line
naming the total, the limit and the largest part. Tests (tests/test_daemon.py):
the count is byte-exact against `json.dumps(..., ensure_ascii=False)` over four
requests carrying quotes, backslashes, NULs, CJK and a `--file` list; the
reviewer's reproduction (at-cap prompt plus twelve `--file` values of
backslashes) exits 2 on all three prompt routes with one message, opens no
socket, and against a real daemon leaves the daemon's log empty and creates no
job; a request whose line is exactly `LINE_LIMIT` runs and writes its file,
and the same request one byte fatter is refused. The two false sentences are
rewritten and `tests/test_docs.py` fails if either comes back.

---

## H-013 — `hands log <job>` still answers a whole transcript in one message

Severity: low · Component: DESIGN §7 (`log` row) and §21 (daemon memory)
against `src/hands/api.py` (`Api.log`, `_read_from`) and `src/hands/cli.py`
(`_follow`)
Filed by: mission 5, U6 (daemon memory), while implementing §21's
"the daemon's resident size must not grow with a job's transcript".

Symptom. U6 makes the *running* half of §21 true: the runner writes each
stream-json line to `~/.hands/jobs/<job>.stream.jsonl` as it arrives and keeps
nothing per event, and `tail` reads a bounded window from the end of the
transcript instead of the whole file. One reader is still unbounded.
`Api.log(job=…)` with the default `offset = 0` reads the entire stream file,
splits it into a list of lines and returns all of them in one JSON-RPC
response: for a 60-turn mission that is the transcript in the daemon's heap,
again on the client's, and in one line on the socket. `hands log -f` does not
have the problem after its first request — it pages by `offset` — but its
first request is `offset = 0` too.

Why U6 did not close it. Bounding it means capping the bytes one `log` answer
carries, and that changes what `hands log <job>` *is*: today one call returns
the whole captured stream, and driver/CLAUDE.md tells the driver to read a job
that way. Capping it silently truncates that answer unless the caller pages,
and §7 describes no paging contract for `log` (the `offset` field is an
implementation detail of `-f`, not something §7 names). That is a spec
decision, not a builder's.

What the architect may want to say. Either (a) §7 gains a paging contract for
`log` — one answer is at most N bytes of complete lines plus the `offset` to
continue from, and the CLI loops for the non-`--json` route so a human still
sees the whole stream — or (b) §7 states that `log` is deliberately unbounded
and §21's claim is about a job *running*, not about a human asking for its
transcript. The measurable difference is one `hands log` of a 60-turn job.

Status: open (design decision; the running-job half of §21 is implemented and
tested at U6)

**Decision, 2026-09-12 (DESIGN v3.5 §4 `log` row, §22; recorded by mission 6
U2).** The architect took branch (a): `log` is "captured stream, delivered in
pages so a whole transcript is never one message (H-013)".

Status: decided (DESIGN v3.5 §4); closed on disk by mission 6 U2

Status: closed on disk, 2026-09-12 (mission 6 U2). `hands.api._read_from` reads
one page — at most `LOG_PAGE_BYTES` (256 KiB) of complete lines, plus the rest
of a single line wider than that — and `Api.log` answers with that page, the
`offset` it ends at and `more`. `hands log <job>` without `--json` walks the
pages itself (`cli._pages`) and prints them in order, so a human still sees the
whole stream in one command; a `--json` caller gets one page and continues with
`hands log <job> --json --offset <offset>` while `more` is true (driver/CLAUDE.md
says so). `hands log -f` is unchanged in shape and its first request is now a
page too. Tested in tests/test_library.py: `test_log_is_delivered_in_pages` (a
~800 KB stream: every page is within the bound, the pages concatenate to the
stream in order, the last has `more: false`, and the human route prints all of
it) and `test_log_of_a_huge_stream_is_read_in_bounded_memory` (64 MB of stream
read through `daemon.api.log` in >200 pages with a `tracemalloc` peak under
8 MiB, every line once, up to the end of the file). Not closed by this: the
daemon's other whole-file readers named in mission 5's U6 report
(`spool.events()`, `list_jobs()`).

The same unit made §4's `tail` row true (review 5 blocker 2): `-n` is `n >= 1`,
refused by the client before it connects (exit 2, one line), and the answer
carries `truncated` whenever the 1000-entry cap or `TAIL_WINDOW_BYTES` cut it
short — including the case where the window holds only a fragment of one entry
and the answer is empty. `tail_entries` returns the flag with the entries.

---

## H-014 — a harness termination of a role job is recorded as `done`

Severity: high · Component: DESIGN §2, §6 against `src/hands/runner.py`
(`_final_state`) and the role environment
Filed by: mission 7a, U0, from the record of job `0mtygi953-ym63`.

Symptom. Job `0mtygi953-ym63` (`~/.hands/jobs/0mtygi953-ym63.json`) is
mission 6's builder kickoff: role `builder`, origin `cli`, prompt `Read
meta/BUILDER-6-PROMPT.md and execute the mission below its divider.`, started
`2026-09-12T14:04:33.360Z`, ended `2026-09-12T15:48:02.748Z`. Its record says
`state done`, `exit_code 0`, `num_turns 59`, `verdict null`, and a `result`
that is a mid-mission progress note, not a report: "U0–U5 are committed and
pushed; the U5 follow-up (the argv prompt route's UTF-8 refusal) is running
now. I'll continue with U6 and U7 when it reports back." Its `stderr_tail` is
the one line that says what happened:

    Background tasks still running after 600s; terminating. Set
    CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0 to wait indefinitely.

The session transcript (`2fb3baa0-80cf-44cf-8ca1-6f25d8f1c941.jsonl`) shows the
cause. All five `Agent` calls pass `run_in_background: false`, and no tool call
anywhere in it asks for background execution. At `15:37:38Z` the builder
continued the finished U5 sub-agent with `SendMessage` ("Resuming agent
ac9f10b"), which runs that sub-agent in the background; at `15:38:01Z` it ended
its turn with the note above. `claude -p` stays open while a background task
runs, up to its idle ceiling (§2: 10 minutes,
`CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS`), and at `15:48:02Z` — 600 s later — the
harness terminated the process and exited 0. hands saw exit 0 and a final
result event, and `_final_state` answered `done`.

Consequences. A mission that stopped at U5 of 8 is recorded as a clean finish.
With a playbook loaded, `builder.done` with no verdict stops the pipeline (§10:
a missing `VERDICT:` line is always `stop`), so the human is called, but for
the wrong reason, and a `builder.failed → resume` rule never gets its event.
Nothing but the stderr line distinguishes this record from a finished turn: the
three checks the architect names below catch it only through that line, since
this job did produce a final result with `num_turns`. (The installed build is
mission 2's, which does not keep the stream file, so the result event's
`subtype` is not on disk for this job.)

Direction. Decided by the architect in DESIGN v3.6 §23 and
`meta/BUILDER-7-PROMPT.md`; recorded here as the decision.

**Decision, 2026-09-12 (DESIGN v3.6 §2, §6, §23; recorded by mission 7a U0).**
A harness termination of a role job is `failed`, not `done`. The runner
classifies a job as `failed` when the process ends without a final `result`
event of subtype `success` or `error`, or when stderr carries the harness's
`terminating` line, or when `num_turns` is absent; `stderr_tail` and a new
`failure_reason` field say which. The runner sets
`CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0` in the role environment unless the
config sets it (a new `[roles.<r>] env` table), and `hands doctor` reports the
effective value per role. The `.claude/hooks/no_background.py` hook covers
the sub-agent tool as well as Bash, and root `CLAUDE.md` says sub-agents run in
the foreground. Closed on disk by mission 7a U1 (the runner, the env, doctor)
and U2 (the hook).

Not covered by the decision as written, for the architect: the background task
in this job came from `SendMessage` continuing a finished sub-agent, not from a
tool input asking for background execution, so a hook that refuses only
background-asking inputs would not have refused it. With the ceiling at 0 the
process waits instead of being terminated; what the turn does when that
sub-agent reports back inside `-p` is not observed.

Status: decided (DESIGN v3.6 §23); fixing (mission 7a U1, U2)

**Status: closed on disk for the U1 half (mission 7a U1, the commit that
carries this paragraph).** `src/hands/runner.py` records `failed` with a new
job-record field `failure_reason` — `harness_terminated`, `no_final_result`,
`error_result`, `nonzero_exit`, `no_num_turns`, `spawn_error`, the first that
holds — and null for every other state. The terminating line is matched by
shape on every stderr line, not on the tail. `error` in the decision is read as
claude's `error_*` subtype family. Decided in U1: a cancel stays `killed` and a
detected limit stays `limited` even with the terminating line, because §6's
limit resume waits out the reset and a `builder.failed → resume` would not
(H-005). Every role job gets `CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0` unless
`[roles.<r>] env` sets it, and `hands doctor` prints the effective value per
role. Tests prove these with `tests/fake_claude.py`, including the recorded
shape of `0mtygi953-ym63` (success result, `num_turns` 59, exit 0, the
terminating line) and `builder.failed → resume` over the §10 example in a real
daemon. They do not prove that a real claude binary run with the ceiling at 0
waits instead of terminating, or what the turn does when the sub-agent reports
back; neither was observed. The hook half stays open for U2.

**Status: closed on disk (U2 half) (mission 7a U2, the commit that carries
this paragraph).** `.claude/settings.json` now matches `Bash|Agent|Task`, and
`.claude/hooks/no_background.py` also refuses a sub-agent call (exit 2, one
line on stderr, the Bash refusal's shape) unless its input carries the JSON
boolean `run_in_background: false`. Read from Claude Code 2.1.269 and recorded
in the hook's docstring:
- the tool is `Agent`, with `Task` as its alias;
- the harness counts a sub-agent as background when `run_in_background !==
  false`, so an omitted flag is refused;
- the transcripts have 85 `Agent` blocks and 0 `Task` blocks, and all 27
  `Agent` calls under 2.1.269 that omit the flag came back "Async agent
  launched";
- a matcher of `[a-zA-Z0-9_|]` only is split on `|` into exact names.

Tests prove the hook's exit code and stderr for `Agent` and `Task` with the
flag true, false, omitted, null, non-boolean and unreadable. They also prove
that the Bash refusals are byte-identical to 2955a20's, that `SendMessage` is
not refused, and that the settings matcher names the hook's tools. `SendMessage`
continuing a finished sub-agent (this finding's actual cause) is still not
refused, and is recorded in the hook's docstring and in docs/INTEGRATION.md's
"What the hook cannot see". Not proven: no live Claude Code session has run
the hook against a real `Agent` or `Task` call, so that the harness delivers
those payloads to it, and blocks on exit 2, is read from the binary, not
observed.

**Status: precedence changed (mission 8 U1, the commit that carries this
paragraph; DESIGN v3.7 §6, review 7 should-fix 2).** §6 now says "a job with a
`success` result, turns and exit 0 is `done` whatever else stderr says", so the
recorded shape of `0mtygi953-ym63` (success result, `num_turns` 59, exit 0, the
terminating line) is `done` again, and the test that pinned it `failed` now pins
it `done`. The terminating line still makes a job `failed`/`harness_terminated`
when any one of the three is missing, and it is matched only in the harness's
exact one-line shape, case-sensitive, from the line start through `Set
CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=`. For this finding's own case the defence
is now the ceiling at 0 and the hook (§2), not the runner's classification.

**Status: precedence reversed by DESIGN v3.8 (mission 9 U0, the commit that
carries this paragraph; DESIGN v3.8 §6, §25).** §25 records "The
termination-line precedence is reversed back to H-014's reading: it wins over a
`success` result (FINAL-REPORT-8 §5 item 1)". §6 now says: "Precedence: a
cancel stays `killed` and a limit stays `limited`; otherwise the termination
line wins even over a `success` result, because the harness ends the session
mid-turn and the \"result\" is whatever the model had said last (H-014's own
case)." So this finding's recorded shape of `0mtygi953-ym63` (success result,
`num_turns` 59, exit 0, the terminating line) is `failed`/`harness_terminated`
again under the design. The code does not say so yet: at this commit
`src/hands/runner.py` still returns `done` for that shape (the v3.7 rule), and
the change to the runner and its pinning test is mission 9 U1, still to come.

**Status: closed on disk (mission 9 U1, the commit that carries this
paragraph; DESIGN v3.8 §6, §25).** `src/hands/runner.py`'s `_failure_reason`
returns `harness_terminated` whenever stderr carried the terminating line, with
no exception for a `success` result; `_final_state` still decides a cancel
(`killed`) and a detected limit (`limited`) first. The matcher is unchanged:
anchored at the line start, case-sensitive, through `Set
CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=`. Tests prove, with `tests/fake_claude.py`:
the recorded shape of `0mtygi953-ym63` (success result, `num_turns` 59, exit 0,
the terminating line) is `failed`/`harness_terminated` in the runner, in `hands
show` against a real daemon, and in the §10 example's `builder.failed → resume`
over a real daemon; the line still wins with any one of success, turns or exit 0
taken away; a limit and a cancel still win over it; both REVIEW-7 over-match
lines leave a success job `done` and do not set the reason on a failed one. Not
proven: no real harness termination has been observed under this code, nor that
a real claude binary with the ceiling at 0 waits instead of terminating.

## H-015 — a held job can be decided from the phone only by a declaration

Severity: medium · Component: DESIGN §8 (human gates), §11 (notifications),
§13 (`[notify]`) against `src/hands/daemon.py`, `src/hands/notify.py` and
`hands doctor`
Filed by: mission 8, U0, from `meta/BACKLOG.md` (Mission 8 item 5 and
"Unscheduled: Authenticated approvals") and DESIGN v3.7 §24.

Symptom. The only phone path that releases a `held` job is a driver running
`hands approve <job> --human-confirmed`, recorded as `decided_by: driver`
with the quoted instruction. §8 says that record "is a declaration, not
authentication: the daemon cannot tell a driver quoting the human from a
driver inventing a quote", and that "Authenticated approval belongs to the
remote face (§9), if it is built". The backlog carried the same limit as
"Unscheduled: Authenticated approvals" (`decided_by: driver` is a
declaration; authentication belongs to the remote face if built), and
scheduled "ntfy command channel with authenticated approvals" as Mission 8
item 5: a second random topic, commands carrying a shared secret, recorded
as `decided_by: phone`, Approve/Deny action buttons on held-job
notifications, and "Nothing but commands and status lines ever travels
either topic."

Direction. Decided by the architect in DESIGN v3.7 §24 ("Mission 8, the
phone channel") and `meta/BUILDER-8-PROMPT.md` U4; recorded here as the
decision.

**Decision, 2026-09-13 (DESIGN v3.7 §8, §11, §24; recorded by mission 8 U0).**
A `[notify]` config section carries `ntfy_url`, `ntfy_topic` (events, as
today), `cmd_topic` (commands, optional), `cmd_secret` (required when
`cmd_topic` is set), `who_topic` and `who_cmd_topic` (optional); all topics
are random. `handsd` subscribes to `cmd_topic` by an outbound long-poll — no
ingress — and accepts `approve <job>`, `deny <job> [reason]`, `pause`,
`resume` and `status`, the last answered by publishing a status summary to
`ntfy_topic`. A typed command carries `cmd_secret` as its last word. A
held-job notification carries Approve/Deny action buttons that publish
`approve <job> <nonce>` / `deny <job> <nonce>`, where the nonce is 32 random
bytes minted per held job, single-use, and dying with the job; the long-term
secret is never placed in a notification. A decision taken this way is
`decided_by: phone`, the first authenticated approval path; §8's declaration
limitation applies to the driver only. Nothing but commands and status lines
ever travels either topic.

Operational additions from the mission brief (`meta/BUILDER-8-PROMPT.md`
U4): the long-poll reconnects on error; a bad secret or nonce is logged and
ignored, never answered; `hands doctor` reports the channel on/off and
refuses a `cmd_topic` without a `cmd_secret`.

Status: decided (DESIGN v3.7 §24); fixing (mission 8 U4)

## H-016 — §10's example playbook lacks the two stop rules §24 says it has

Severity: low · Component: DESIGN §10 (example), §24 ("Mission 8, the
detectors") against `tests/fixtures/playbook_example.toml` and
`docs/PLAYBOOK.md`
Filed by: mission 8, U7, from `meta/BUILDER-8-PROMPT.md` U7 and
`meta/BACKLOG.md` item 4.

Symptom. DESIGN v3.7 §24 says "The example playbook maps
`monitor.task_killed` and `monitor.orphan_processes` to `stop`", and U7's
brief says the §10 example gains both. §10's "Example (spanweave audit-fix
series)" carries neither: its last rule is `monitor.tripwire` → `stop`. The
example's two copies, `tests/fixtures/playbook_example.toml` and the verbatim
block at the end of `docs/PLAYBOOK.md`, are pinned byte for byte to §10 by
`tests/test_playbook.py::test_the_fixture_is_section_10s_example_verbatim` and
`tests/test_docs.py::test_the_playbook_doc_carries_the_section_10_example_verbatim`,
and builders do not edit DESIGN.md, so a builder cannot add the rules to the
example without breaking the pin or the rule.

What U7 did instead. The repository's own `PLAYBOOK.toml` has both rules
(`then = "stop"`, each with a message), and a test loads it through the real
loader and asserts both resolve to `stop`. `docs/PLAYBOOK.md` shows both rules
in its prose and says the verbatim copy of §10 does not carry them yet, citing
this finding. The two copies of §10's example are unchanged.

Direction, for the architect. Add to §10's example, after the
`monitor.tripwire` rule:

    [[rule]]
    on = "monitor.task_killed"
    then = "stop"

    [[rule]]
    on = "monitor.orphan_processes"
    then = "stop"

The next builder then copies the block into the fixture and the doc (the pins
will fail until it does), extends
`test_the_example_parses_into_the_rules_of_section_10`'s rule list, and drops
the "carries neither yet" sentence from `docs/PLAYBOOK.md`.

Status: closed (DESIGN v3.8 §10, §25; copies updated by mission 9 U0)

**Status: closed (mission 9 U0, the commit that carries this paragraph; DESIGN
v3.8 §10, §25).** §25 records "H-016 closed: §10's events list and example
carry the two detector rules." §10's events list names `monitor.task_killed`
and `monitor.orphan_processes`, and its example now ends, after the
`monitor.tripwire` rule, with `on = "monitor.task_killed"` → `then = "stop"`
and `on = "monitor.orphan_processes"` → `then = "stop"`, as this finding's
direction asked. This commit copies §10's example block verbatim into
`tests/fixtures/playbook_example.toml` and into the verbatim block at the end
of `docs/PLAYBOOK.md`, extends
`test_the_example_parses_into_the_rules_of_section_10`'s rule list with the two
rules, and drops `docs/PLAYBOOK.md`'s sentence saying the verbatim copy carries
neither yet.

## H-017 — DESIGN v3.7 §6's `failure_reason` and `decided_by` vocabularies disagree with the wire

Severity: medium · Component: DESIGN §6 (job record) against
`src/hands/runner.py` (`FAILURE_REASONS`, `_failure_reason`) and
`src/hands/api.py` (`decide_from_phone`)
Filed by: mission 9, U0, from `meta/reviews/REVIEW-8.md` should-fix 2.

Symptom. DESIGN v3.7 §6's job record listed `failure_reason` as
`harness_terminated | nonzero_exit | no_result` and `gate` as `{reason,
decided_by: cli|driver|button, decided_at, quote?}`. The code writes other
names. `src/hands/runner.py`'s `FAILURE_REASONS` and `_failure_reason` write
`harness_terminated`, `no_final_result`, `error_result`, `nonzero_exit`,
`no_num_turns` and `spawn_error` (the last from the spawn failure path); there
is no `no_result`. `src/hands/api.py`'s `decide_from_phone` records
`decided_by: phone`, which §24 asks for and v3.7 §6 did not list; `button`
exists in `src/hands/gates.py`'s `DECIDERS` but is marked not available. H-014's
mission 7a status paragraph named the code's reasons, but v3.7 §6 was written
after it, and missions 8 U0 and U1 both claimed §6 without reporting the gap.
The driver reads these fields verbatim, so a driver written from §6 would not
recognise four of the six reasons or a phone decision.

Direction. Decided by the architect in DESIGN v3.8 §6 and §25 ("§6 vocabularies
reconciled with the wire: `failure_reason` and `decided_by` list what the code
writes (review 8 should-fix 2)"); recorded here as the decision. §6 now lists
`failure_reason` as `harness_terminated | nonzero_exit | no_final_result |
error_result | no_num_turns | spawn_error` and `gate` as `{reason, decided_by:
cli|driver|phone, decided_at, quote?}`. Mission 9 U1 pins the code and
`docs/INTEGRATION.md` to the §6 lists.

Status: fixed by DESIGN v3.8 (§6 now lists exactly those; U1 pins the code and
docs/INTEGRATION.md to the §6 lists)

**Status: closed on disk (mission 9 U1, the commit that carries this paragraph):**
a test reads §6's two lists from DESIGN.md and asserts they equal
`hands.runner.FAILURE_REASONS` and the new `hands.gates.DECIDED_BY` (the available
§8 deciders; `button` stays an unavailable row that `check_decider` refuses), and
a test asserts docs/INTEGRATION.md names every value.

**Correction (2026-09-13, mission 10 U0, REVIEW-9 should-fix 4):** the Symptom
above misquotes DESIGN v3.7. v3.7 §6 (`git show 0ead876^:DESIGN.md`, line 235)
gave `gate` as `{reason, decided_by: cli|driver|button, decided_at}`, with no
`quote?`; `quote?` first appears in v3.8. The rest of the entry stands.

## H-018 — the closed phone loop (§26): decisions recorded, and two gaps §26 leaves

Severity: medium · Component: DESIGN §26 against §6 (job record `origin`), §10
(stop → resume cycle) and `src/hands/runner.py` (`_failure_reason`)
Filed by: mission 10, U0, from `meta/BUILDER-10-PROMPT.md` and DESIGN v3.9 §26.

Decisions (DESIGN v3.9 §26, recorded here as the ledger's copy):
- `[series] kickoff` names the series' fixed kickoff line; unknown keys in
  `[series]` are refused. `go <secret>` on `cmd_topic` sends exactly that line
  as a `clear` send to the builder with `origin: phone`; it is the only way to
  start work from the phone, and it is refused while a builder job is running
  or queued, while no playbook is loaded, or when `[series] kickoff` is absent.
- Kit transport: `kit <secret>` with an ntfy attachment is fetched into
  `[files] kit_dir` (default `~/Downloads`, an allowed root) under the
  attachment's own basename, `.zip` only, capped by `[files] kit_max_mb`
  (default 20) before download, written atomically, never overwritten (numeric
  suffix), never unzipped or executed; `kit.received` in the inbox and a
  notification `kit received <name> <bytes> <sha256>`. The apply stays a gated
  job.
- `hands who` matches an interactive session to its transcript by the pid the
  transcript records, never by directory.
- `hands kit check <zip|dir> [--repo path]` runs without a daemon and checks
  what §26 lists.
- REVIEW-9: the SF3 kill check must fail on the reused-group condition; the
  playbook HEAD comparison runs git with a scrubbed environment and compares
  normalized bytes; INTEGRATION's `done` statement follows §6; H-017's quote is
  corrected (appended above).

Gap 1 — `origin: phone` is outside §6's vocabulary. §6 lists `origin
(driver|playbook|cli|limit)`; `src/hands/spool.py:93` `ORIGINS` enforces exactly
that and `src/hands/api.py:273` refuses anything else. Direction (builder's,
simplest): §26 is the later text, so U2 adds `phone` to `ORIGINS`. §6's list
should gain `phone` in the next DESIGN revision.

Gap 2 — a `go` after a stop would not chain. §10: a `cli`-origin send un-pauses
the pipeline when it starts, and a stop is never cleared by a job the playbook
or the limit manager started (`src/hands/playbook.py:112` `UNPAUSE_ORIGINS =
{"cli"}`). After a stop the pipeline is paused, so a `phone` job would run the
builder while its `builder.done` fires no rule, and the review would never be
sent; §26's loop (send kit, approve, `go`, wait for the buzz) would not close.
§26 is silent. Direction (builder's, simplest): the human typed the secret, so
`phone` joins `UNPAUSE_ORIGINS` with the same "only when the job starts" rule;
`go` is accepted while the pipeline is paused (a paused playbook is still
loaded). U2 carries both, with tests.

Gap 3 — REVIEW-9 should-fix 2 has a code half. §6 says a `result` of subtype
`error` is `failed`/`error_result`; `_failure_reason` fails only on `is_error`,
so `error_max_turns` with `is_error: false`, `num_turns` and exit 0 is `done`.
U0 makes `docs/INTEGRATION.md` state §6's rule; U1 makes the runner follow it
(an `error`/`error_*` subtype is `error_result` whatever `is_error` says), with a
test that is red before.

Resolution (DESIGN v3.10 §27, 2026-09-13). §27: "`phone` and `kit` are job
origins (§6); a job of either origin un-pauses the pipeline when it starts, as
a `cli` one does." Gap 1 and gap 2 are resolved as U2 of mission 10 chose,
extended to `kit` (mission 11 U3 creates the first `origin: kit` job). §27 also
refuses `go` while the builder has a **held** job (REVIEW-10 SF1, mission 11
U1). Gap 3 was closed by mission 10 U1. (Moved into this section by mission 12 U0, REVIEW-11 should-fix 5.)

Status: resolved by DESIGN v3.10 (code: gap 3 m10 U1; `phone` m10 U2; `kit` m11 U3)

## H-019 — `series = "…"` and `[series] kickoff` cannot share one TOML file

Severity: medium · Component: DESIGN §10 (the example's `series = "audit-fixes"`)
against §26 (`[series] kickoff`); `templates/PLAYBOOK-missions.toml`,
`templates/PLAYBOOK-runs.toml`; `src/hands/playbook.py`
Filed by: mission 10, U2.

The contradiction. TOML forbids defining a key twice, and a `[series]` table
defines `series` a second time after a top-level `series = "<name>"`. Both
templates carry exactly that (`series = "<project>-…"`, then `[series]` with
`kickoff`), and `tomllib` refuses them as written: `Cannot overwrite a value (at
line 4, column 8)`. §10's example keeps the string; §26 adds the table; neither
says where the series' name goes once the table exists. DESIGN is silent, so the
templates and the design cannot both hold as written.

Chosen (U2, simplest, stated in its commit body):
- `[series]` holds two keys, `name` and `kickoff`, both optional strings; any
  other key is refused at load, naming it; `""` or blanks for either is refused
  (§20).
- The top-level `series = "<name>"` string still loads when there is no table,
  so §10's example and its verbatim fixture are unchanged; the loaded name is
  the same field either way (`hands pipeline`, doctor).
- A file with both forms is refused by the TOML parser ("is not valid TOML"),
  before any key is read; a test pins it.
- The root `PLAYBOOK.toml` now spells `[series] name = "hands-missions"` and the
  kickoff.

Needs: U5 reconciles `templates/` (the name moves into the table as `name`, or
is dropped) so they load; §10/§26 in the next DESIGN revision state the
table's keys (a different choice there supersedes this one).

Progress (mission 10, U5): `templates/PLAYBOOK-missions.toml` and
`templates/PLAYBOOK-runs.toml` now spell `[series] name` beside `kickoff`, with no
top-level `series`; both load, and filled in (N=11, `<project>`=hands) they pass
`hands kit check` (`tests/test_kit.py`). `docs/ARCHITECT-HANDBOOK.md` §6 names the
table's two keys. DESIGN §10/§26 still to state them.

Resolution (DESIGN v3.10 §27, 2026-09-13). §27: "the playbook's `[series]`
table is `name` and `kickoff`; a bare `series = "…"` string remains accepted as
the name." This is the form mission 10 U2 shipped and U5 put in the
templates. (Moved into this section by mission 12 U0, REVIEW-11 should-fix 5.)

Status: resolved by DESIGN v3.10 (no code change needed)

## H-020 — no transcript records a pid; §26's "the transcript's first line records" it does not hold

Severity: medium · Component: DESIGN §26 (`hands who` bullet), §4 `who` row,
§11/§24 who view; `src/hands/who.py`
Filed by: mission 10, U4 (BACKLOG "Mission 10" item 4). No code changed.

The claim. §26: "`hands who` matches an interactive session to its transcript
by pid, which the transcript's first line records, never by directory". U4's
brief: find that field in real transcripts; if none records a pid, stop and
file this memo instead of inventing one.

Evidence (Claude Code 2.1.270, this machine, 2026-09-13; read-only; ids, paths
and content replaced by placeholders):

1. First line of every transcript, `~/.claude/projects/*/*.jsonl` (470 files),
   tallied by `type` and key set:
   ```
   353 queue-operation  {content, operation, sessionId, timestamp, type}
    93 custom-title     {customTitle, sessionId, type}
    22 mode             {mode, sessionId, type}
     2 ai-title         {aiTitle, sessionId, type}
   ```
   No first line carries a pid. The first `user` entry carries `cwd`,
   `sessionId`, `entrypoint`, `version`, `gitBranch`, `permissionMode`,
   `userType`, `promptSource`, `promptId`, `uuid`, `parentUuid`,
   `isSidechain`, `timestamp`, `message` — no pid.
2. Every key on every line of all 470 transcripts (138,369 lines; `message`,
   `toolUseResult`, `content`, `snapshot`, `attachment` payloads excluded as
   user data), matched against `(?i).*(pid|process_?id|processid)`: no key.
   The only `pid`-substring keys in a 50-lines-per-file scan were
   `totalAPIDuration` and `totalAPIDurationWithoutRetries`.
3. For each live `claude` process from `pgrep -x claude` (3: two interactive,
   one `claude -p` hands job), `grep -E '"[A-Za-z_]*[Pp]id"\s*:\s*"?<pid>\b'`
   over all transcripts: no file.

Where the pid IS recorded: outside the transcript, in
`~/.claude/sessions/<pid>.json`, one file per live process:
```
{"pid": <pid>, "sessionId": "<uuid>", "cwd": "<path>", "kind": "interactive",
 "entrypoint": "cli" | "sdk-cli", "startedAt": <ms>, "procStart": "<s>",
 "status": "<s>", "updatedAt": <ms>, "version": "<s>", "name": "<s>", ...}
```
(plus a `<pid>.<hash>.key` file holding a peer token, not read further). For all
3 live processes `sessionId` names an existing transcript
`~/.claude/projects/<dir>/<sessionId>.jsonl`. The hands job (`claude -p`) also
writes one, with `kind: "interactive"` and `entrypoint: "sdk-cli"`; the two
human sessions have `entrypoint: "cli"`. So `kind` does not separate a job
from a human session here; `entrypoint` did in this sample of 3.

Why U4 stops. Matching through `~/.claude/sessions/<pid>.json` → `sessionId` →
transcript basename would meet §26's intent (a job in the same directory never
shown under the human's session), but it reads a file §26 does not name, whose
format is undocumented, and whose `.key` sibling holds a credential-like token.
That is a design choice, not a silence to fill.

Needs: the next DESIGN revision states the source of the pid → transcript
match (e.g. `~/.claude/sessions/<pid>.json` `sessionId`, reading only `pid` and
`sessionId`, never the `.key` file), what is shown when that file is absent
(the `transcript: by directory` fallback), and whether `entrypoint` may be
used. U4 is then re-run against it.

Resolution (DESIGN v3.10 §27, 2026-09-13). §27: `hands who` matches an
interactive `claude` process to its transcript through
`~/.claude/sessions/<pid>.json`, whose `sessionId` names the transcript; the
transcript stays the source of the session's state; with no sessions file for a
pid the line says `transcript: by directory` and is never attributed a job's
transcript. §27 does not name `entrypoint`; mission 11 U2 reads only `pid` and
`sessionId` and never the `.key` file. (Moved into this section by mission 12 U0, REVIEW-11 should-fix 5.) DESIGN v3.11 §28 adds
that the directory fallback also excludes the `sessionId` of every hands pid's
sessions file (REVIEW-11 blocker 4, mission 12 U4).

Status: resolved by DESIGN v3.10 (code: mission 11 U2; §28 fallback: mission 12 U4)

## H-021 — §26's verdict check reads the builder's brief; review verdicts have no literal to match

Severity: low · Component: DESIGN §26 (`kit check`: "every `verdict` regex of the
playbook in force … matches at least one literal in the brief's final-reply
vocabulary") against §10; `src/hands/kit.py`; `PLAYBOOK.toml`,
`templates/PLAYBOOK-*.toml`, `meta/REVIEW-PROTOCOL.md`
Filed by: mission 10, U5.

The contradiction. This repository's `PLAYBOOK.toml` and both templates carry
`aux.done` rules whose regexes discriminate on the review's count (`blockers=0`,
`blockers=[1-9]`, `blockers=`). A brief (`meta/BUILDER-N-PROMPT.md`, `WORKPLAN.md`)
fixes only the builder's replies. The review's vocabulary is fixed by the
review protocol (`VERDICT: review mission N blockers=<k> should-fix=<m>`) or by
the send prompt, and carries `N` and `<k>` as placeholders. Read as written, §26
fails every such playbook against every brief, including the mission 10 kit
U5 must pass. Matching the protocol's line instead, with placeholders left as
text, fails too: `\d+` does not match `N`, and `0` does not match `<k>`.

Chosen (U5, simplest; stated in its commit body and in handbook §11): the
regex ↔ literal check covers `builder.done` rules, in both directions. A
`builder.done` rule that matches none of the brief's literals passes only when
it matches `VERDICT: kit applied <sha>`, the reply `kit check`'s own apply
prompt asks for. Verdict rules on any other event are counted and named on the
`verdicts` line ("not matched against the brief"), never shown as matched; they
do not change the exit status.

Needs: the next DESIGN revision says whether and how review verdict rules are
checked (for example against the protocol's verdict line, with each named
placeholder read as its class of values), or confirms the builder-only scope.

Resolution (DESIGN v3.10 §27, 2026-09-13). §27: `hands kit check` verifies
every `verdict` rule, `aux.done` included, against the vocabulary the review
protocol specifies (the `VERDICT: review …` line), and refuses a kit whose brief
or protocol vocabulary a rule cannot match; a broken builder rule is never
excused by the apply-verdict exception (REVIEW-10 SF4). The builder-only scope
U5 shipped is superseded. (Moved into this section by mission 12 U0, REVIEW-11 should-fix 5.) DESIGN v3.11 §28 narrows the
apply-verdict exception to one `builder.done` rule (REVIEW-11 should-fix 7,
mission 12 U3).

Status: resolved by DESIGN v3.10 (code: mission 11 U1; §28 narrowing: mission 12 U3)

## H-022 — `hands kit check .` on this repository cannot exit 0

Severity: low · Component: mission 11 Acceptance ("`PLAYBOOK.toml` names
BUILDER-12 and has `consult` rules; `hands kit check .` exits 0") and U6's gate
against DESIGN §26/§27 `kit check`; `src/hands/kit.py` (`_read_dir`,
`_check_paths`, `_find_brief`, `_check_playbook`)
Filed by: mission 11, U6.

Symptom. `kit check` reads its argument as a kit, and a kit of the whole working
tree fails on this repository's layout, not on the playbook. With U6's
`PLAYBOOK.toml` in the working tree (2026-09-13, each line cut to 300 columns):

    $ uv run hands kit check .
    FAIL paths: 1896 of 3068 entries are not repository paths under /home/msi/git/hands: .git/COMMIT_EDITMSG (a path inside .git); …
    FAIL playbook: the kit's PLAYBOOK.toml loads; its [series] kickoff 'Read meta/BUILDER-12-PROMPT.md and execute the mission below its divider.' has no brief kickoff line to equal (see brief)
    FAIL brief: the kit carries meta/BUILDER-1-PROMPT.md, meta/BUILDER-10-PROMPT.md, meta/BUILDER-11-PROMPT.md, … and meta/BU…; carry one
    FAIL verdicts: no final-reply vocabulary to match (see brief)
    FAIL wording: no brief to read (see brief)
    PASS protocol: every file a send names is present: meta/REVIEW-PROTOCOL.md (kit)
    kit check: FAIL (5 of 6 checks failed); no apply prompt for a failing kit
    exit 1

Three independent causes, none fixable from `PLAYBOOK.toml`: (1) `.git/` is in
the directory, and every entry under it is refused (paths); (2) the repository
keeps every mission's brief, `meta/BUILDER-1…11-PROMPT.md`, and a kit must carry
exactly one (brief, then verdicts and wording); (3) §27's Conventions make the
kickoff name the *next* mission (BUILDER-12), and a kit's kickoff must equal its
brief's, while `meta/BUILDER-12-PROMPT.md` does not exist yet. Writing that
brief would not fix (1) or (2).

What does exit 0, and what does not (the same working tree, kits built under /tmp):

- a kit of `meta/BUILDER-11-PROMPT.md` alone, `--repo .`: 6 of 6 PASS, exit 0.
  The repository's `PLAYBOOK.toml` is in force (playbook: "loads, no
  quiet_hours; its kickoff is not compared"). verdicts: 5 `builder.done` verdict
  rules and the brief's 3 literals match each other (rule 1 through the apply
  literal); 2 `aux.done` rules match the review protocol; 2 `driver.done` rules
  match the driver's two lines. This checks the rules, not the kickoff.
- a kit of `PLAYBOOK.toml` + `meta/BUILDER-11-PROMPT.md`: 5 PASS, FAIL
  playbook ("its [series] kickoff 'Read meta/BUILDER-12-PROMPT.md …' is not the
  brief's kickoff line 'Read meta/BUILDER-11-PROMPT.md …'"), exit 1. By §27's
  convention this stays red until mission 12's brief exists and is the kit's.

Needs: the architect says what the acceptance line means. Either (a) it is the
brief-in-force kit above (exit 0 today, kickoff not compared), or (b) the check
belongs to mission 12's kit (`PLAYBOOK.toml` + `meta/BUILDER-12-PROMPT.md`),
whose brief must carry the literal `VERDICT: question`, or (c) `kit check`
gains a repository mode (skip `.git`, pick the brief the kickoff names), which
is a DESIGN change. U6 did not write BUILDER-12, did not edit BUILDER-11, and did
not change `kit.py`.

Resolution (DESIGN v3.11 §28, 2026-09-15). §28: "H-022 resolved: the
acceptance meant a kit of the mission's brief checked against the repository
passes; `kit check` stays a kit checker." That is option (a): a kit of
`meta/BUILDER-<N>-PROMPT.md` with `--repo .`. No repository mode is added.
Mission 12 U5 runs that form on `meta/BUILDER-12-PROMPT.md` (REVIEW-11 blocker
5).

Status: resolved by DESIGN v3.11 (acceptance form; checked by mission 12 U5)

## H-023 — the post-exit sweep kills a leaderless group on an environment mark, not on descent

Severity: medium · Component: DESIGN §27 (the sweep "signals only a group whose
leader is the job's own pid and whose members are all descendants") against
`src/hands/runner.py` (`_sweep`, `_kill_group`, `_last_resort`) as mission 11 U1
(`efe4d56`) shipped it
Filed by: mission 12, U0, from REVIEW-11 blocker 3 (a departure U1 made and
disclosed in FINAL-REPORT-11 §5 item 5 without a finding).

The departure. When no process holds the job's pid (the leader is gone), U1
still signals the group if every live member carries the job's `HANDS_JOB=<id>`
environment mark. §27 names the leader as the job's own pid; it does not name a
mark. The mark is a stand-in for descent, not descent: any process can set it,
and a member that clears its environment leaves the group unsignalled. The
leaderless, marked group is tested only through `_last_resort`
(`tests/test_runner.py:1144`), never through `_sweep`/`_kill_group`.

Resolution (DESIGN v3.11 §28, 2026-09-15). "The post-exit sweep signals a group
only when its leader is alive and is the job's pid, or when every live member
is a descendant by pid chain (or a member of the job's cgroup scope); the
`HANDS_JOB` mark alone never qualifies. H-023 records the departure U1 made."
Mission 12 U4 carries the code, with a test through `_sweep`/`_kill_group`
that leaves a leaderless marked group alone and kills a descendant group.

Progress (mission 13 U0, 2026-09-15). §28's rule could not hold after the
reap (H-025); DESIGN v3.12 §29 replaces it with H-025 option (b). This finding
closes with mission 13 U2, which removes the `HANDS_JOB`-mark-alone rule.

Status: resolved by DESIGN v3.12 (code: mission 13 U2)

## H-024 — §28's residual-character list, read literally, refuses commands the guard must keep allowing

Severity: low · Component: DESIGN §28 (the guard: "a token in argument position
that still contains `$`, a backtick, `{`, `}`, `\`, `~` (not leading), `*`, `?`,
`[` or `!` after `shlex` processing is refused") against §12 rule 6 ("the guard
treats quoted text as text") and the existing allowed tables;
`driver/hooks/bash_guard.py`
Filed by: mission 12, orchestrator, from U1's report (`3966f9b`).

The conflict. `shlex` removes quotes, so "after `shlex` processing" cannot tell
a quoted character from a bare one. Read literally, the list refuses commands
the brief requires to stay allowed: `git diff HEAD~1` (non-leading `~`),
`git rev-parse HEAD^{commit}` (`{`, `}`), and a quoted send prompt such as
"Apply ~/Downloads/k.zip …". §28's own reason is "because the shell would expand
it after the guard saw it".

Chosen (U1, stated in its commit body): a character counts only where bash
would still expand it — never inside single quotes or after a backslash;
inside double quotes only `$`, backtick, `\` and `!`; `{letters}` without a
comma or `..` is allowed; a non-leading `~` is refused only after `=` or `:`.
Every REVIEW-11 blocker 1 probe stays blocked under this reading.

Needs: the next DESIGN revision states the reading (expansion position, not
raw character after `shlex`), or names a different one.

Resolution (DESIGN v3.12 §29, 2026-09-15). "H-024's reading is the text: an
expansion character counts only where bash would still expand it; never inside
single quotes or after a backslash; inside double quotes only `$`, a backtick,
`\` and `!`; brace words only with a comma or `..`; a non-leading `~` only
after `=` or `:`. Every review 11 and review 12 probe stays blocked." §29 also
refuses any `#` outside quotes in both modes (REVIEW-12 blocker 1). Mission 13
U1 implements the reading exactly as stated.

Status: resolved by DESIGN v3.12 (code: mission 13 U1)

## H-025 — §28's sweep rule, read literally, never signals a process group after claude is reaped

Severity: high · Component: DESIGN §28 ("the post-exit sweep signals a group
only when its leader is alive and is the job's pid, or when every live member
is a descendant by pid chain (or a member of the job's cgroup scope)") against
§24 ("at job end anything still in the scope is filed as
`monitor.orphan_processes` … then the scope is killed", process-group fallback
included); `src/hands/runner.py` (`run`, `_sweep`, `_kill_group`,
`_last_resort`, `_group_is_the_jobs`)
Filed by: mission 12 U4 (the sweep half stopped here; the `who` half shipped).

The conflict. In process-group mode the sweep runs after asyncio has reaped
claude (`proc.returncode` is set, or `proc.wait()` returned; the child watcher
calls `waitpid` as soon as the pidfd fires). So at every sweep:
- no process holds the job's pid, so the "leader alive" branch never applies;
- a member that outlived claude was reparented to init or the nearest
  subreaper, so no member's pid chain reaches the job's pid;
- there is no cgroup scope in group mode.
Read literally, the group sweep never signals anything.

Measured (U4, a probe line in `_group_is_the_jobs` plus "leaderless → False";
reverted, not committed): every sweep printed `leader start_time None`, and
three existing §24 tests fail:
- `tests/test_runner.py::test_a_cancelled_jobs_orphan_is_reported_and_killed`
  (nothing reported);
- `tests/test_monitor.py::test_a_double_forked_orphan_is_filed_with_its_command_line_and_killed`,
  `[detached]` (nothing filed) and `[holding-its-pipes]`, which times out:
  `run()` awaits the pipes after the sweep, and the unkilled orphan holds
  them, so job end stalls until the orphan exits.

A proof of descent that works with the leader gone exists, but it is not "by
pid chain". Linux keeps a pid allocated while any process holds it as its
pgid or sid. A live member whose sid is the job's pid, and which started
before the last moment claude was seen holding that pid, is in claude's
session, so the pid was never free and every member descends from claude.
Its gap is timing: a fork in claude's last poll interval (≤ 50 ms) cannot be
proven, and those processes are left alive.

Needs: the architect's choice, for example one of these.
- (a) Group mode never signals after the reap. §24's group-mode kill and its
  tests are retired, and the design says what job end does when an unkilled
  orphan holds claude's pipes.
- (b) The session and start-time proof above is admitted as "descent".
- (c) The leader is kept observable until the sweep, for example with a
  subreaper or an unreaped leader. That changes spawning, §24.

Until then the U1 rule (the `HANDS_JOB` mark) stays in the code, and H-023
stays open.

Resolution (DESIGN v3.12 §29, 2026-09-15): option (b) chosen. "A live process
descends from the job when its session id is the job's pid and its start time
precedes the last moment the job's pid was observed alive, or when it is a
member of the job's cgroup scope; the `HANDS_JOB` mark is corroboration and
never sufficient alone. The residual is a fork inside the job's last poll
interval, documented in `docs/INTEGRATION.md`. Job end reads the pipes with a
bounded timeout (`runner.pipe_timeout_s`, default 10) so an unkilled orphan
cannot stall it; what remains after the sweep is reported as
`monitor.orphan_processes` with `killed: false`." Mission 13 U2 carries the
code; H-023 closes with it.

Status: resolved by DESIGN v3.12 (code: mission 13 U2)

## H-026 — the guard's parser is replaced by a language (§30)

Severity: high · Component: DESIGN §12 rule 6, §28, §29 (the guard) against
§30 (the driver's shell is one line); `driver/hooks/bash_guard.py`,
`.claude/hooks/bash_guard.py`, `tests/test_bash_guard.py`
Filed by: mission 14 U0, orchestrator, from REVIEW-13 blocker 1.

History, reviews 11–13:
- Review 11 blocker 1: the guard's bash reading missed shapes that hide a
  command; mission 12 patched the scanner.
- Review 12 blocker 1: an apostrophe inside a `#` comment opened a quote bash
  never sees; mission 13 refused `#` outside quotes.
- Review 13 blocker 1: a `'` inside a heredoc body desynchronised the quote
  state the same way, in both modes; each patch left the next bash corner.

Resolution (DESIGN v3.13 §30, 2026-09-16): the parser is not extended again.
The guard refuses, before any tokenizing, a newline, carriage return, `<`,
`>`, `#`, a backtick, `$(`, `\`, `$'` or any control character (naming the
first offender and its position), and `$` or `!` inside double quotes; what
remains is one line of words and quotes that `shlex` tokenizes without
ambiguity, split on `;`, `&&`, `||`, `|`, `&`. Heredoc, comment, redirection
and expansion-position handling is removed as unreachable. Mission 14 U1
carries the code.

Status: resolved by DESIGN v3.13 (code: mission 14 U1)

## H-027 — two DESIGN lines name things missions 13 and 14 retired

Severity: medium · Component: DESIGN §12 rule 6 ("the guard treats quoted text
as text", DESIGN.md:541) and DESIGN §14's repository layout
(`systemd/handsd.service`, DESIGN.md:644, with `handswho.service` at
DESIGN.md:921); `driver/CLAUDE.md` rule 6, `driver/hooks/bash_guard.py`,
`tests/test_docs.py`
Filed by: mission 14 U5, from REVIEW-13 should-fix 7 and §30.

Symptom, two lines, both of which a builder may not edit (CLAUDE.md: "DESIGN.md
is not edited by builders; file a finding").

1. **§12 rule 6 says quoting makes text.** §30 replaced the guard's parser with
   a language: mission 14 U1 refuses `<`, `>`, `#`, a backtick, `$(`, `\`, `$'`,
   a newline and any control character *in any position, quoted or not*, and `$`
   and `!` inside double quotes. So the rule the driver reads is false for
   exactly the characters it would reach for:

       $ cd driver/hooks
       $ printf '%s' '{"tool_name":"Bash","tool_input":{"command":"hands send
         --role builder --context clear \"see #3\""}}' | python3 bash_guard.py
       bash_guard blocked this command (refused before tokenizing: a `#` at
       position 47 (§30: the driver's shell is one line of words and quotes):
       'hands send --role builder --context clear "see #3"'). …
       exit 2

   (the JSON is one line here; wrapped for the ledger). The same command with
   `HANDS_ROLE=driver` and `HANDS_CLONE` set is refused identically, and so is
   a quoted backtick (`"run `date`"`, a backtick at position 47).

   `driver/CLAUDE.md` rule 6 carried the same sentence, and
   `tests/test_docs.py::test_driver_rule_6_is_the_design_section_12_rule_6` pins
   the kit's rule 6 to DESIGN's word for word.

2. **§14's layout ships `systemd/handsd.service`.** Mission 13 U6 (§29, "the
   un-templated units are retired") replaced it with `systemd/handsd@.service`
   and `systemd/handswho@.service`; neither un-templated unit exists in the
   repository. DESIGN.md:921 still calls `handswho.service` the optional unit.
   REVIEW-13 should-fix 7 named both lines and recorded that no finding was
   filed for them.

Direction — what the architect should change.

- §12 rule 6: replace "the guard treats quoted text as text" with §30's
  language, e.g. "quoting makes no character safe: one from the guard's refused
  set is refused inside quotes too". The shipped `driver/CLAUDE.md` rule 6 and
  the guard's own docstring now say that (mission 14 U5), so this closes a
  divergence rather than opening one.
- §14's layout line: `systemd/handsd@.service  systemd/handswho@.service  # user
  units, per project`. §24's sentence at DESIGN.md:921 wants `handswho@.service`
  for the same reason.

Until §12 rule 6 lands, `tests/test_docs.py` pins the kit's rule 6 to DESIGN's
rule with that one clause corrected (`STALE_QUOTED_CLAUSE` →
`GUARD_REFUSAL_CLAUSE`), so every other word of the rule stays pinned and the
test keeps passing unchanged once DESIGN says the same thing — the replacement
is then a no-op. Nothing else in the repository depends on either line.

Status: resolved by DESIGN v3.26 §43 ("The DESIGN wording, written here": §12
rule 6 and §14's and §24's unit names). The copies, mission 27 U1:
`tests/test_docs.py::test_driver_rule_6_is_the_design_section_12_rule_6` now
requires `driver/CLAUDE.md` rule 6 to equal DESIGN's rule exactly, and
`STALE_QUOTED_CLAUSE` is gone.

---

## H-028 — an allowed first word took unchecked options: the guard wrote and ran a program

Severity: high · Component: `driver/hooks/bash_guard.py` (`ALLOWED_FIRST_WORDS`,
`driver/hooks/bash_guard.py:110-116` at 041f647), normal mode; DESIGN §12, §30,
§31
Filed by: mission 15 U0, from REVIEW-14 blocker 1 (which reproduced it at the
tip 041f647) and the mission 14 U1 sub-agent's differential fuzz.

Symptom. §30 made the driver's *language* small enough to have no corners: no
redirection, no substitution, no escape, no comment. It did not touch the set of
allowed command words. `ALLOWED_FIRST_WORDS` admitted `sort`, `uniq`, `cut`,
`tr`, `find`, `stat`, `diff`, `printf`, … as bare words, and outside `git` and
`hands` no option table was applied in normal mode. Those commands write and
execute through their own options, so nothing in the command had to *look* like
a write. REVIEW-14 reproduced three, through the shipped file with hook JSON on
stdin:

    sort -o /tmp/rev14-probe/Z1 /etc/hostname                       -> exit 0 ; Z1 created
    uniq /etc/hostname /tmp/rev14-probe/W5                          -> exit 0 ; W5 created
    sort -S 1k --compress-program=/tmp/rev14-probe/prog <big file>  -> exit 0 ; prog EXECUTED

The file's own words contradicted this on disk: the docstring
(`driver/hooks/bash_guard.py:7`) said the command has "no way to write", and the
refusal text said the driver may run "read-only inspection commands; it never
writes". The comment above `GIT_SUBCOMMAND_OPTIONS` stated the right principle —
"no listed option takes a value that names a program to run" — and applied it to
git's rows only. Role mode refused all three (exit 2), so this was never a
role-mode hole; it was pre-existing at 4192af1 and undisclosed by
FINAL-REPORT-14 §3.1, which named only unquoted `$`.

Direction. DESIGN v3.14 §31 answers it: the one-line method applies to the words
as it applied to the syntax. `ALLOWED_FIRST_WORDS` is replaced by a table from
each command the driver's rules name to the options it may take, in both modes
(`cat`, `ls`, `head`, `tail`, `wc`, `grep`, `jq`, `pgrep`, `sleep`, `date`,
`echo`, `kill -0`, `hands`, `git`); every other word leaves the table and is
refused by name. No listed option takes a value that names a program or a file
to write. The three probes and a fuzz corpus over the removed words go into the
tests, and the docstring and refusal text are made to say what is true.

Status: resolved by DESIGN v3.14 (code: mission 15 U1)

---

## H-029 — the architect is a person in the loop; §31 makes it a role

Severity: medium · Component: DESIGN §31 (with §8, §10, §11, §26, §27);
`src/hands/config.py`, `src/hands/playbook.py`, `src/hands/kit.py`,
`src/hands/cli.py`, `src/hands/doctor.py`, `driver/hooks/bash_guard.py`,
`architect/`
Filed by: mission 15 U0, recording the shape of the change so the reasoning
survives the mission.

Symptom — what stood in the way before §31. Every planning round needed the
human: the architect thought in a chat Project, emitted a kit as files, the
human moved the zip to the laptop, `kit <secret>` filed a held apply, the human
pressed Approve, and `go <secret>` sent the kickoff. Three of those five steps
are judgment the human already exercised once, at the plan the series runs on.
The loop closed at mission 10 was closed *through the phone*, not closed.

Direction — what §31 decides, and the seams it opens.

- A fourth role, `architect`, started by handsd for one consultation, with no
  memory of earlier ones: the branch carries the state. Its cwd is
  `~/hands-architect/<project>/` with a fetch-only clone under `repo/` and a
  `kits/` directory; `permission_flags` is empty, so `settings.json` and the
  hook are the law, as for the driver role (§27).
- A third guard mode (`HANDS_ROLE=architect`): the driver's read-only table plus
  `hands kit check|file`, and `mkdir|cp|mv|zip|unzip` only with every path
  argument under `HANDS_KITS`. Writes are a *second* `PreToolUse` matcher
  (Write|Edit|MultiEdit → `--write`), which is new: until now the guard judged
  Bash alone and writes were denied outright by `settings.json`.
- `hands kit file <zip>` gives the role the phone's `kit` path from inside the
  laptop, running the kit check itself first and refusing a failing kit.
- `[series] architect = "phone" | "role"` and `[series] autonomous`: with both
  set, the engine approves held applies of `origin: architect` as `decided_by:
  playbook` and sends the kickoff after `VERDICT: kit applied`. §8's "nothing
  else releases a `held` job" gains an engine path, and its authority is the
  human's approval of the playbook — which is itself a gated kit apply. That
  standing approval is the whole of the autonomy, so it is worth naming: the
  human who approves an `autonomous` playbook is approving every apply the
  architect files under it.
- Escalation is written down rather than judged in the moment:
  `gate_failures = 2`, `escalate_on = ["blocker-unanswered", "milestone-missing",
  "budget-exhausted"]`, `[limits] max_architect_consults` (default 12), and the
  engine owns `budget-exhausted` itself.

Risks this mission should keep visible: a role that writes at all is a new
surface (mitigated by `HANDS_KITS` confinement on both matchers); `decided_by:
playbook` is a fourth gate authority §8 did not have; and an autonomous series
has no human between a bad kit and the branch except the kit check and the cold
review.

Status: resolved by DESIGN v3.14 (code: mission 15 U3, U4, U5)

---

## H-030 — the architect can write a kit under KITS but cannot name its entries as repository paths

Severity: medium · Component: DESIGN §31 (architect guard mode, `hands kit
file`); `driver/hooks/bash_guard.py`, `architect/CLAUDE.md` rule 3
Filed by: mission 15 U3, from building the mode §31 specifies.

Symptom. §31 gives the architect `zip` "only with every path argument under
`HANDS_KITS`", and `architect/CLAUDE.md` rule 3 says its output is "a zip under
KITS whose entries are repository paths". Those two cannot both hold with the
words the mode has. `zip` stores each entry under the path it is given on the
command line, and Info-ZIP has no option that changes directory first (no `-C`,
no `--strip-components`; `-j` junks *all* directories, which flattens
`meta/BUILDER-16-PROMPT.md` to `BUILDER-16-PROMPT.md`). The role's cwd is
`~/hands-architect/<project>/` and `HANDS_KITS` is `<cwd>/kits`, so:

    zip -r kits/m16.zip kits/m16     -> entries `kits/m16/DESIGN.md`, …
    zip -r kits/m16.zip DESIGN.md    -> refused: `DESIGN.md` is not under KITS
    cd kits/m16 && zip -r ../m16.zip .   -> `cd` is not a word the table has

The first is the only one the guard allows, and its entries are not repository
paths. `kit check`'s `paths` check does not catch it either: `kits/m16/DESIGN.md`
*is* a syntactically valid repository path, so the kit passes the check and the
apply prompt tells the builder to add files under `kits/`. Nothing in this unit
is wrong by §31; the mode as specified just cannot produce the artifact the
role's own instruction asks for. Evidence: `zip --help` on this machine lists no
directory option, and `driver/hooks/bash_guard.py: KITS_TABLE` has no `cd` row
(by §31: the table is closed, and `cd` would change what every later relative
path in the session means).

Direction — three candidates, none of them this unit's to choose:
1. `hands kit file <dir>`: `hands.kit._read_kit` already reads a directory kit
   at its own relative paths, and `check_kit` already accepts one; only
   `apply_from_zip` is zip-only. The architect would stage `kits/m16/<repo
   path>` and file the directory, and hands would build the zip (or the apply
   prompt would name the directory). This needs no new guard word.
2. A `zip` option table entry that makes the entries right — there is none, so
   this would mean a different archiver (`tar` is not in the table either).
3. A confined `cd`, allowed only into a path under `HANDS_KITS`. The cheapest to
   write and the most expensive to reason about: every relative path the guard
   judges afterwards, including `git -C` and the KITS containment itself, is
   resolved against the hook's cwd.
Until one is decided, an architect role that reaches rule 3 will either file a
kit whose entries are wrong or escalate.

Resolution appended 2026-09-16 (mission 16 U0, from DESIGN v3.15 §32). The
first candidate is chosen. `unzip` and `zip` leave the architect's table; the
architect stages a directory `kits/<name>/<repository paths>` and files it with
`hands kit file <dir>`, which builds the zip itself, checks it against the
role's clone, refuses a failing kit with the check's output, and files the held
apply (`origin: architect`). `mkdir`, `cp` and `mv` remain, every path argument
under `HANDS_KITS` and no option that names another path. The Write/Edit
matcher remains the only way to create file content. The removal of `unzip`
also closes REVIEW-15 blocker 2 (an `unzip` with no `-d` extracted into the
role's cwd, the parent of `HANDS_KITS`, over the guard and its settings).

Status: resolved by DESIGN v3.15 (code: mission 16 U2)

---

## H-031 — §6's `decided_by` vocabulary is three values; §31 adds a fourth

Severity: low · Component: DESIGN §6 (the job record's `gate` field) against
§31; `src/hands/gates.py` (`DECIDERS`, `DECIDED_BY`), `tests/test_docs.py`
Filed by: mission 15 U4, from building `decided_by: playbook`.

Symptom. DESIGN §6's job record line reads

    gate              # {reason, decided_by: cli|driver|phone, decided_at, quote?}

and §31 says a held apply of origin `architect` under a playbook with
`[series] architect = "role"` and `autonomous = true` is "approved by the
engine (`decided_by: playbook`)". Both cannot be read literally: `playbook` is
a value the record now carries and §6 does not list it. Review 8 should-fix 2
(H-017) turned §6's list into a test — `tests/test_docs.py::
test_the_code_vocabularies_are_section_6s_lists` parses the list out of §6 and
asserts `set(hands.gates.DECIDED_BY)` equals it exactly — so implementing §31
as written makes that test red without touching it.

Direction. U4 implemented §31's words (the code's vocabulary is `cli`,
`driver`, `phone`, `playbook`) and weakened that one assertion to "§6's list
plus `playbook`, and no more", naming this finding. The check still fails on a
fifth value appearing in code without a design change, which is what it was
for. The tidy resolution is a §6 line that reads `decided_by:
cli|driver|phone|playbook`, after which the assertion goes back to equality;
DESIGN.md is the architect's file, so this unit did not make that edit.

Resolution appended 2026-09-16 (mission 16 U0, from DESIGN v3.15 §32). §6 now
reads `decided_by: cli|driver|phone|playbook`; `playbook` is a `decided_by`
value. The work-around in `tests/test_docs.py` goes back to equality with §6's
list (mission 16 U0, because the base commit was red on it).

Status: resolved by DESIGN v3.15 (code: mission 16 U0)

---

## H-032 — the driver role refuses a direct `hands send`; the architect role does not

Severity: low · Component: `src/hands/api.py` (`Api.send`) against DESIGN §31
(with §27); `docs/INTEGRATION.md`
Filed by: mission 15 U6, from documenting how the role is started.

Symptom. §27 says the driver role is "started by `handsd` only through a
`consult` action", and `Api.send` enforces it by name: `role == "driver"` is
refused with that sentence. §31 gives the architect the same shape — a role
handsd starts "for one consultation" — and nothing in the code says so. A
playbook cannot reach it (a `send` rule's role is `builder` or `aux`, checked at
load) and the phone cannot (`go` sends the kickoff to the builder), so the one
route is a human typing `hands send --role architect "<anything>"` at the
laptop. That starts an architect session outside any consultation, with the
guard's architect mode, its `HANDS_KITS` write surface and `hands kit file` —
which, under an `autonomous` playbook, files an apply the engine then approves.

Why this unit did not close it. U6 is the documentation unit; the refusal is
product behaviour, one line in `Api.send` with a test beside the driver's, and
§31 does not write the sentence §27 wrote, so the shape of the refusal (refuse
outright, as the driver's is, or accept it as the human's own laptop authority)
is a choice this unit should not make alone. `docs/INTEGRATION.md` says what is
true today and names this memo rather than claiming a confinement that is not
there.

Direction. Simplest: extend the `role == "driver"` refusal in `Api.send` to
`CONSULT_ROLES` (`hands.config` already names both), with §31 in the message and
a test that both roles are refused. If instead a laptop send is meant to stay
possible, say so in §31 and the asymmetry is closed by a sentence rather than a
line of code.

Correction appended 2026-09-16 (mission 15 orchestrator). The memo's "simplest"
direction is not simple: `meta/BACKLOG.md` "Mission 16 — talking to the
architect" item 1 is `reply <secret> <text>` on `cmd_topic`, "delivered as
`hands send --role architect --context keep` to the architect's last session".
So a send to the architect is the *next* mission's design, and extending
`Api.send`'s driver refusal to both consult roles would have to be undone by it.
The two candidate resolutions are therefore: refuse a send to the architect
except from the phone's `reply` origin (which mission 16 builds), or leave the
laptop send as the human's own authority and say so in §31. Mission 15 chose
neither and left the asymmetry, which is why this stays open.

Resolution appended 2026-09-16 (mission 16 U0, from DESIGN v3.15 §32). The
refusal is chosen: `Api.send` refuses a direct send to any role whose start is
the engine's (`driver`, `architect`); they are started by `consult` only. A
laptop `hands send --role architect` is refused as `--role driver` is.

Status: resolved by DESIGN v3.15 (code: mission 16 U3)

---

## H-033 — the guard's language, finished: `$`, braces and reserved words leave it

Severity: high · Component: `driver/hooks/bash_guard.py` (all three modes);
DESIGN §12, §30, §31, §32; `docs/INTEGRATION.md`
Filed by: mission 16 U0, orchestrator, from REVIEW-15 blocker 1 (and should-fix
7).

History, reviews 11–15:
- Review 11 blocker 1: separators the scanner misread hid a command; mission 12 patched the scanner.
- Review 12 blocker 1: a `'` inside a `#` comment desynchronised quotes; mission 13 refused `#`.
- Review 13 blocker 1: a heredoc body did the same; mission 14 made the shell one line (§30, H-026).
- Review 14 blocker 1: allowed words wrote and ran programs through their options; mission 15 added the command table (§31, H-028).
- Review 15 blocker 1: a `for` segment went unjudged and `${c@P}` ran `$(…)`, in role mode too; `for o in -f; do tail $o F; done` passed the option tables.

Symptom. Reproduced by REVIEW-15 at 17b12fe, shipped file, hook JSON on stdin:

    for a in '$x'; do echo; done; for c in ${a%x}'(touch${IFS}/tmp/rev15-tip/PWN)'; do echo ${c@P}; done
      normal exit=0 · HANDS_ROLE=driver exit=0 · HANDS_ROLE=architect exit=0 ; PWN created under bash
    for o in -f; do tail $o /etc/hostname; done                    -> exit 0 (normal, driver)

§30 refused `$(` and `$'` but not `$` or `${`, and §28's `$`/`{` check applied
to the `git` and `hands` rows only; the `for` segment was skipped rather than
judged, so its body's words were never looked up. The option tables compared
the literal `$o`, which bash expands after the guard has approved it. Role mode
had refused the probe at 1a48e11 (`'echo'` not allowed) and mission 15 U1's
widening let it in. Should-fix 7: the widened role-mode reads reach any path the
user can read (`cat ~/.ssh/id_rsa`, `grep -r x /`), undisclosed.

Resolution (DESIGN v3.15 §32, 2026-09-16): besides §30's refusals the guard
refuses `$` anywhere, `{` and `}` anywhere, and every reserved word of the shell
appearing as a word (`for while until if then else elif fi do done case esac
select function in time coproc ! [[ ]]`), in every mode, before tokenizing.
What remains is words, `'…'` and `"…"` quotes and the separators `; && || | &`:
no expansion, no control flow, no redirection, no comment. The option tables
judge every word including values, and a value that is not a plain word is
refused. Role and architect modes are strict subsets; role-mode reads are
confined to the clone and the spool's own paths, and the refusal says so.
`docs/INTEGRATION.md` states the whole language in one paragraph and lists the
tables. §30's condition stands: the driver and architect roles are enabled
after a review finds no hole in this language.

Status: resolved by DESIGN v3.15 (code: mission 16 U1)

---

## H-034 — §10's example playbook still maps `monitor.task_killed` to `stop`; §32 says `notify`

Severity: low · Component: DESIGN §10 ("Example (spanweave audit-fix series)")
and §24 ("Mission 8, the detectors", last bullet) against §32's last paragraph;
`tests/fixtures/playbook_example.toml`; the verbatim block at the end of
`docs/PLAYBOOK.md`
Filed by: mission 16 U5, from the unit brief (playbook severity).

Symptom. DESIGN v3.15 §32 says: "`monitor.task_killed`: the detector cannot
tell a reap from a `TaskStop` or from the harness backgrounding a long
foreground command and reaping it; the example playbook and this repository's
map it to `notify`, and a job that ends `failed` is what stops." §10's example
still ends with `on = "monitor.task_killed"` → `then = "stop"`, and §24 still
says "The example playbook maps `monitor.task_killed` and
`monitor.orphan_processes` to `stop`". The example's two copies,
`tests/fixtures/playbook_example.toml` and the block under "## The example
(DESIGN §10, verbatim)" in `docs/PLAYBOOK.md`, are pinned byte for byte to §10
by `tests/test_playbook.py::test_the_fixture_is_section_10s_example_verbatim` and
`tests/test_docs.py::test_the_playbook_doc_carries_the_section_10_example_verbatim`,
and builders do not edit DESIGN.md — the same shape as H-016.

What U5 did instead. This repository's `PLAYBOOK.toml` and both templates map
the event to `notify` (the kit had already changed them); a test loads each
through the real loader and pins `notify`, `aux.failed` → `stop`,
`builder.failed` → `resume` with `max_resumes` set, and drives each file through
the engine. `docs/PLAYBOOK.md`'s prose shows the `notify` rule, says why, and
says the verbatim copy of §10 still says `stop` until this finding is resolved.
The two copies of §10's example are unchanged, and
`test_the_example_parses_into_the_rules_of_section_10` still lists
`("monitor.task_killed", "stop")`.

Direction, for the architect. In §10's example replace

    [[rule]]
    on = "monitor.task_killed"
    then = "stop"

with

    [[rule]]
    on = "monitor.task_killed"
    then = "notify"
    message = "A task inside a role job was killed"

(a `notify` rule needs a message, or the loader refuses it), and in §24 read "maps
`monitor.orphan_processes` to `stop`" (the §32 paragraph covers the other). The
next builder copies the block into the fixture and the doc, changes the rule list
in `test_the_example_parses_into_the_rules_of_section_10`, adjusts the sentence
after the verbatim block ("killed tasks and orphan processes stop and call you"),
and drops the H-034 sentence from `docs/PLAYBOOK.md`'s prose and its pin in
`tests/test_docs.py`.

Status: resolved by DESIGN v3.26 §43 ("The DESIGN wording, written here": §10's
example maps `monitor.task_killed` to `notify` with a message; §24 names
`monitor.orphan_processes` only). The copies, mission 27 U1:
`tests/fixtures/playbook_example.toml` and the verbatim block in
`docs/PLAYBOOK.md` take §10's example; `test_the_example_parses_into_the_rules_of_section_10`
lists `("monitor.task_killed", "notify")`; the sentence under the verbatim copy
says the example and this repository both notify on a killed task; the H-034
sentence in `docs/PLAYBOOK.md`'s prose and its pin in `tests/test_docs.py` are
gone; `test_a_task_killed_rule_loads_and_stops_the_pipeline` replaces the
example's `notify` rule by a `stop` rule instead of appending one the first
match would now shadow.

Correction appended 2026-09-17 (mission 17 U0, from REVIEW-16 should-fix 8): the
tests do not pin docs/PLAYBOOK.md's closing copy to §10 byte for byte, as the
Symptom above says; `tests/test_docs.py::test_the_playbook_doc_carries_the_section_10_example_verbatim`
only checks that each line of the fixture appears somewhere in the doc, and only
`tests/test_playbook.py::test_the_fixture_is_section_10s_example_verbatim`
compares a copy (the fixture) with §10's block exactly (after removing the
four-space indent).

---

## H-035 — the daemon must run the check it approves on

Severity: high · Component: `src/hands/api.py` (`Api.kit_file`), the engine's
approval of an architect apply, `hands kit check`; DESIGN §31, §32, §33
Filed by: mission 17 U0, orchestrator, from REVIEW-16 blocker 1 (with should-fix
1 and 5).

Symptom. §32 says `hands kit file <dir>` "builds the zip itself, checks it, and
files the held apply", and that the engine approves only an apply "from a kit
filed by the architect role (a `kit_id` the daemon minted …)". The check runs in
the client only. `Api.kit_file` (`src/hands/api.py:267-330` at review 16's tip)
checks the name, the base64, the size and the entry paths (through
`apply_from_zip`) and that an architect consultation is open; it never runs
`check_kit`, and the job it files carries `origin: architect` and a daemon-minted
`kit_id`, which is what the engine approves. REVIEW-16's repro: a real daemon,
fake_claude and the committed role + autonomous playbook; while the architect
job ran, a raw-socket `kit_file` filed two zips, `foo` and `bar`, each carrying
`.claude/hooks/bash_guard.py`, `.claude/settings.json`, `DESIGN.md` and a
`PLAYBOOK.toml` and no brief. Both were `decided_by=playbook`, and `check_kit`
on each gave `ok=False failed=[playbook, brief, verdicts, wording]`. Any socket
client can open the window (`send --role aux` whose reply is a review verdict).
No test bound "a kit that fails `hands kit check` is not approved".
- Should-fix 1: one consultation filed any number of kits, of any name, and the
  engine approved each, although the verdict was `VERDICT: next kit foo`.
- Should-fix 5: `hands kit check` passed a role-mode kit it had not judged (two
  project configs and no `--project`/`HANDS_PROJECT`, or a config that is not
  valid TOML): exit 0 with `PASS playbook: … is not judged against
  [roles.architect]: no hands config resolves here`.

Resolution (DESIGN v3.16 §33, "The autonomy path", 2026-09-17):

> - `kit_file` runs `check_kit` on the bytes it stores, against the builder's
>   clone, and refuses a failing kit with the check's output; the engine
>   approves only an apply whose stored `kit_id` records a passing check;
>   a consultation may file at most one kit, and its name must equal the
>   name the architect's `VERDICT: next kit <name>` states, else the apply
>   is denied by the engine and the consultation ends `escalate`.

> - `kit check` on a kit that carries a role-mode playbook judges the
>   playbook's role requirements against the repository's config the way
>   `handsd` will at load, and says so.

Code (mission 17 U1, f6f7f26, 2026-09-17): `Api.kit_file` runs `check_kit` on
the stored zip against the served repository and its config, refuses a failing
kit with the check's output and deletes the zip; `kit.json` records `"check":
"pass"` and the engine approves nothing without it; a kit filed while the
architect runs is decided when the consultation's verdict is known; two or
more kits, or a kit the verdict does not name, end the consultation `escalate`
and every such hold is denied (`deny_from_playbook`, not a socket method); `kit
check` fails a role-mode playbook when no config, two configs without
`--project`, or an invalid TOML config resolves. The reviewer's raw-socket
probe is an end-to-end acceptance test. Not proven: a daemon restart between
the hold and the verdict; concurrent `kit_file` calls.

Status: resolved by DESIGN v3.16 (code: mission 17 U1)

---

## H-036 — zip entry names: the judge reads the local header, extraction reads the Unicode Path

Severity: high · Component: `src/hands/kit.py` (`apply_from_zip`, `check_kit`'s
paths rule); the daemon's `kit_file`; DESIGN §26, §32, §33
Filed by: mission 17 U0, orchestrator, from REVIEW-16 blocker 2.

Symptom. `src/hands/kit.py` judges `info.orig_filename` (`kit.py:381`, `:432`,
`:1112`), the name in the zip's local header. `unzip` and Python's
`ZipInfo.filename` use the Info-ZIP Unicode Path extra field (0x7075) when one
is present. REVIEW-16 reproduced it at the tip with a zip built by Python
3.14.6, `ZipInfo("docs/notes.md")` with extra 0x7075 naming
`.git/hooks/pre-commit`, mode 0755:

    filename= .git/hooks/pre-commit orig= docs/notes.md
    apply_from_zip -> Apply(name='evil', adds=['docs/notes.md'], prompt="Apply ~/evil.zip to this
      repository: unzip -o into the repo root (it adds docs/notes.md), …")
    unzip -o ../evil.zip ->  extracting: .git/hooks/pre-commit

and the next `git commit` ran the hook. Over the socket `kit_file` the same kit
was held, origin architect, its prompt naming only `docs/notes.md`. Reach: on the
phone's kit path a human approves a prompt naming another file than the one
written; with H-035's hole it is engine-approved with no human. The architect's
own `hands kit file` builds its zip itself and cannot craft this. The rule
predates mission 16, but FINAL-REPORT-16 §2 says "the daemon refuses … an
escaping zip", and no test covered an entry whose two names differ.

Resolution (DESIGN v3.16 §33, "The autonomy path", 2026-09-17):

> - Zip entries are judged by the central directory's names, which are what
>   extraction uses; an entry whose local-header name differs from its
>   central-directory name is refused, as is any name that resolves into
>   `.git/`, `.claude/`, or outside the repository; both the daemon and
>   `kit check` share the one judge.

Code (mission 17 U2, 6f05e4e, 2026-09-17): `_zip_entries` in `kit.py` is the one
judge and the only reader of `orig_filename`: the central-directory name,
refused when the local-header name or any 0x7075 field disagrees; `.git` and
`.claude` refused at any depth in any letter case; a repository symlink leading
outside or into `.git`/`.claude` refused; used by `_read_zip` and
`apply_from_zip`, so `kit check`, `kit_file` and the phone's kit path share it.
The reviewer's zip and two variants are refused on all three paths. Not
proven: zips with several end-of-central-directory records; filesystem aliases
of `.git`/`.claude` (trailing dots, ignorable characters, 8.3 names).

Status: resolved by DESIGN v3.16 (code: mission 17 U2)

---

## H-037 — on a token-protected ntfy the Approve/Deny buttons carry no token

Severity: medium · Component: `src/hands/phone.py` (`PhoneChannel.actions`);
DESIGN §26 (the held job's buttons), §33 ("Self-hosted ntfy … `[notify]
ntfy_token` (sent as a bearer on publish and subscribe); the phone app
subscribes with the same token")
Filed by: mission 17 orchestrator, from the U6 sub-agent's report (4775880).

Symptom. U6 sends `Authorization: Bearer <ntfy_token>` on every publish and
subscription hands makes. A held job's notification carries two `http` action
buttons (`PhoneChannel.actions`) whose `url` is the command topic and whose
`body` is `approve|deny <job> <nonce>`; the action carries no `headers`. On a
server with `auth-default-access: deny-all`, the POST the phone app makes when
a button is pressed is anonymous unless the app adds its own sign-in to action
requests, which no one has verified. If it does not, the buttons fail on
exactly the setup §33 recommends, and the human must type `approve <job>
<secret>` instead (docs/INTEGRATION.md says so as a fallback).

Why a builder did not fix it. ntfy's `http` action accepts a `headers` map, so
the daemon could put the bearer in the action. That publishes the token inside
every held notification's payload, to every subscriber of `ntfy_topic` and into
the server's message cache. §33 says the token is sent as a bearer on publish
and subscribe; it does not say the token may appear in a message body. That is
a design choice.

Direction, for the architect. Either (a) the actions carry `headers:
{Authorization: Bearer …}` only when `ntfy_topic` and `cmd_topic` are on the
same token-protected server (a subscriber of `ntfy_topic` already holds a token
that reads it; state whether it may also write `cmd_topic`), or (b) a separate
write-only token for `cmd_topic`, `[notify] ntfy_action_token`, is what the
buttons carry, or (c) the buttons are dropped when `ntfy_token` is set and the
notification says to type the command. A real ntfy server and phone app should
settle whether the app signs action requests before choosing.

Status: resolved-by-code (mission 22 U1 — `notify.actions_header` puts
`headers.Authorization=Bearer <token>` on every `http` action when `[notify]
ntfy_token` is set and nothing without; `config._ntfy_token` refuses a token with
a comma or semicolon; doctor's `phone` row says "buttons: bearer on" | "buttons:
no token; a token-protected server refuses them"; tests in
`tests/test_ntfy_token.py`, §38 section. Whether the phone app sends the action's
headers is not proven by any test here.)

---

## H-038 — the start fold drops a held job's Approve/Deny buttons

Severity: high · Component: `src/hands/daemon.py` (`_publish_start`, `stop`),
`src/hands/notify.py` (the start fold); DESIGN §24 ("a held-job notification
carries Approve/Deny action buttons"), §26 ("The held notification carries the
buttons"), §33
Filed by: mission 18 U0, orchestrator, from REVIEW-17 blocker 1 (with
should-fix 6).

Symptom. Mission 17 U4 (c6380ab) made a start that re-admits queued jobs hold
back every notification for up to `START_FOLD_S` (5 s) and publish one
"handsd started" that lists the held notes by title and message only
(`daemon.py:293-309` at 011899e). A `job.held` raised in that window loses its
actions. REVIEW-17's probe: a real Daemon, a queued builder job (`FAKE:sleep
3`), an aux job gated at 0.3 s — `held job … held at 0.42`, then one publish at
3.2 s, `title='hands: handsd started' actions=False`. The human gets no button
and no nonce; only a typed `approve <job> <secret>` works. The "decide with
`hands approve`" text is added only for jobs held before the start.
FINAL-REPORT-17 §3.7 disclosed it; no finding covered it.
- Should-fix 6: `stop()` publishes the start notification and then
  `notifier.cancel_all()` (`daemon.py:439`) cancels the delivery still in
  flight. With 0.5 s publish latency and a stop at 1.0 s, nothing was
  delivered; the parent delivered "handsd started" and "the pipeline stopped".

Resolution (DESIGN v3.17 §34, 2026-09-17):

> The start fold (review 17 blocker 1, should-fix 6): the daemon's start fold
> holds back only what it may safely fold: heartbeats and `pipeline.resumed`
> of the jobs it re-admits. A `job.held` is never folded: it is published at
> once, with its buttons, whether the job was held before or during the
> start; the start notification lists it by title only. A `stop` inside the
> fold window flushes the fold first and cancels nothing that was already
> queued to publish; `cancel_all` is removed from that path. Tests bind both
> with the reviewer's timings.

Code (mission 18 U1, 45da318, 2026-09-17): `Notifier.notify(fold=False)` for
`job.held`: during the start's hold the held note is published at once with its
Approve/Deny buttons and named by title only in "handsd started"; a job held
before the start is re-published at start with fresh buttons (`_publish_held`
replaces `_remint_held`); `stop()` flushes the start notification first and
drains pending publishes (bounded, 30 s) instead of `notifier.cancel_all()`,
which is deleted. The reviewer's two probes (a job held at 0.3 s during a
start; a stop at 1.0 s with 0.5 s publish latency) are tests, red first. Not
proven: a real ntfy or claude; a kit apply or engine hold inside the window; a
publish hanging past the drain bound. The fold of other kinds is H-039.

Status: resolved by DESIGN v3.17 (code: mission 18 U1)

---

## H-039 — §34's start fold names what never reaches ntfy; the builder kept §33's fold of stops

Severity: low · Component: `src/hands/daemon.py`, `src/hands/notify.py` (the
start fold); DESIGN §33 (the start folds queued jobs' publishes into one),
§34 ("holds back only what it may safely fold: heartbeats and
`pipeline.resumed` of the jobs it re-admits")
Filed by: mission 18 orchestrator, from the U1 sub-agent's report (45da318).

Symptom. §34 says the fold holds back *only* heartbeats and
`pipeline.resumed`. In this code neither is an ntfy notification; both are
inbox events only, so there is nothing of theirs to fold. Read literally, the
fold would hold back nothing and every publish a re-admitted job raises
("the pipeline stopped" when a queued job fails at once) would go out on its
own, reopening REVIEW-16 should-fix 7, which §33 closed with one notification.
U1 read §34 as taking `job.held` out of §33's fold and kept the fold of
everything else; §33's one-notification tests still bind it.

Direction, for the architect. Either confirm the reading (the fold holds back
everything except `job.held`), or state which other kinds must publish at
once during the window.

Status: resolved by DESIGN v3.26 §43 ("The DESIGN wording, written here": §34's
start fold holds back everything a re-admitted job publishes except a
`job.held`, published at once with its buttons — U1's reading, which the code
has kept since mission 18). Mission 27 U1 copies nothing for it: no code or
test changes, since §33's one-notification tests already bind the reading.

---

## H-040 — twelve `kit file` tests fail when the gate runs inside a hands job

Severity: low · Component: `tests/test_kit.py` (the `hands kit file` CLI
tests); the gate `./scripts/check`
Filed by: mission 19 orchestrator, U0 (2026-10-14).

Symptom. This mission's orchestrator runs as a hands builder job, so its
environment carries `HANDS_PROJECT` and `HANDS_JOB`. At 21d62d9 with only
meta/ edits, `./scripts/check` gave `12 failed, 4018 passed`; every failure is
in tests/test_kit.py (`test_kit_file_refuses_*`,
`test_kit_file_does_not_file_a_failing_kit_*`,
`test_kit_file_files_a_held_apply_*`). For example:
`hands: cannot read config <path>/home/.hands/hands.toml: [Errno 2] No such
file or directory` where the test expected "HANDS_KITS". The CLI resolves the
project from `$HANDS_PROJECT` (src/hands/cli.py:880) when the test names none.
`env -u HANDS_PROJECT -u HANDS_JOB uv run pytest -q tests/test_kit.py` passes.
So the tests are not hermetic against the environment of the job that runs
them, and a builder dispatched by hands, which is how every mission runs, sees
a red gate the test log does not explain.

Direction. Have the tests (a conftest autouse fixture, or `scripts/check`)
clear `HANDS_*` from the environment before they run. This is test code
outside mission 19's scope. Mission 19 runs its gate as `env -u HANDS_PROJECT
-u HANDS_JOB ./scripts/check` and says so in every commit body.

Status: resolved (code: mission 20 U1 — the autouse fixture in tests/conftest.py
clears every `HANDS_*` variable for every test; tests/test_hermetic.py)

---

## H-041 — the architect role cannot write: no allow for the write tools; the `--write` hook only denies

Severity: high · Component: `architect/settings.json`, `src/hands/doctor.py`
(the architect row); DESIGN §31 (the architect role), §36 "The architect
role's write permission"
Filed by: mission 20 orchestrator, U0 (2026-10-14).
Evidence: the first role-mode series (discotrade, 2026-10-12 to 2026-10-14;
meta/BACKLOG.md "Mission 20" item 1, laptop workaround applied 2026-10-12).

Symptom. Headless `claude -p` without a bypass denies any tool that is not
allowed. `architect/settings.json` allows no `Edit`, `Write` or `MultiEdit`,
and the `--write` hook only ever denies, so the role could not write a byte
under `kits/`. Doctor's architect row said `ok`.

Direction. §36: allow exactly `Edit(kits/**)`, `Write(kits/**)`,
`MultiEdit(kits/**)`; doctor's row fails without them or with a wider write
allow; `doctor --live` writes, checks, shows and removes. Mission 20 U3.

Status: resolved (code: mission 20 U3 — architect/settings.json allows the
three writes under kits/; doctor's architect row and its `--live` turn judge them)

---

## H-042 — the role's clone never advances: `git fetch` only; `kit check --repo ./repo` judges the working tree

Severity: high · Component: `src/hands/runner.py` (role jobs),
`src/hands/config.py`, `src/hands/doctor.py`; DESIGN §31, §36 "The runner"
Filed by: mission 20 orchestrator, U0 (2026-10-14).
Evidence: the first role-mode series (meta/BACKLOG.md "Mission 20" item 2;
laptop workaround: a transient timer pulling every minute).

Symptom. Nothing advances the architect's or the driver's clone. A `git
fetch` moves the remote-tracking refs only; `hands kit check --repo ./repo`
judges the working tree, so the role checked its kits against the tree of
the day the clone was made and reviewed a project it could not see.

Direction. §36: before every architect and driver job the runner runs `git
-C <clone> fetch -q origin` and `git -C <clone> checkout -q --detach
origin/<branch>` (`[roles.<role>] branch`, default `main`); a failure fails
the job before `claude` starts. Mission 20 U4.

Status: resolved (code: mission 20 U4 — the runner fetches origin and checks out
origin/<branch> detached before every architect and driver job, `[roles.<role>]
branch` default main; a clone that cannot be advanced fails the job, spawn_error,
git's message in stderr_tail; doctor's role rows print HEAD against origin/<branch>)

---

## H-043 — no role job carries `HANDS_PROJECT`

Severity: medium · Component: `src/hands/runner.py`, `src/hands/doctor.py`;
DESIGN §36 "The runner"
Filed by: mission 20 orchestrator, U0 (2026-10-14).
Evidence: the first role-mode series (meta/BACKLOG.md "Mission 20" item 3;
laptop workaround: the unit's env file).

Symptom. A role job's environment had `HANDS_PROJECT` only when handsd's own
environment did; the role's `hands` calls and the guard's project
resolution had no project on a laptop with two.

Direction. §36: every role job's environment carries `HANDS_PROJECT` from
the config's project name, never from handsd's environment; doctor's role
rows print it. Mission 20 U4.

Status: resolved (code: mission 20 U4 — every job's environment carries
HANDS_PROJECT=<config project> over handsd's environment and the env table;
doctor's role rows print it)

---

## H-044 — the kickoff after an autonomous apply comes from the pre-apply playbook

Severity: high · Component: `src/hands/playbook.py`, `src/hands/daemon.py`
(the engine); DESIGN §33, §34, §36 "The engine"
Filed by: mission 20 orchestrator, U0 (2026-10-14).
Evidence: discotrade HF-001 (meta/BACKLOG.md "Mission 20" item 4).

Symptom. Under `autonomous`, an apply the engine approved itself rewrote and
committed the playbook's `[series] kickoff`; the engine decided the apply's
`builder.done` with the playbook it had loaded before the apply and sent the
old kickoff to the builder.

Direction. §36: reload the playbook from the committed file before deciding
that `builder.done`; a playbook that no longer loads stops the pipeline with
the loader's reason. Regression test: a scripted apply that rewrites and
commits the kickoff, then the kickoff job's prompt is the committed line.
Mission 20 U5.

Status: resolved-by-code (mission 20 U5 — the engine reloads the committed
playbook before deciding the builder.done of an apply it approved itself; a
playbook that no longer loads stops with the loader's reason; tests in
tests/test_playbook.py)

---

## H-045 — a hold for a kit the role filed is published with buttons before the engine approves it

Severity: medium · Component: `src/hands/daemon.py`, `src/hands/api.py`,
`src/hands/notify.py`; DESIGN §34, §36 "The engine"
Filed by: mission 20 orchestrator, U0 (2026-10-14).
Evidence: the first role-mode series (meta/BACKLOG.md "Mission 20" item 6).

Symptom. Under `autonomous`, the hold for a kit the architect filed was
published with Approve/Deny buttons, and the engine approved it a moment
later; the human saw buttons for a decision already taken.

Direction. §36: decide the hold before anything is published; one
buttonless "kit <name> filed by the architect; apply approved by the
playbook" when approved, the §34 buttons when not. Mission 20 U5.

Status: resolved-by-code (mission 20 U5 — Api.send defers the hold of a
role-filed kit under autonomous; the engine publishes one buttonless approval
line, or the hold with its buttons when it does not approve; tests in
tests/test_playbook.py)

## H-046 — `handswho` publishes every ~20 s and spends the public broker's daily cap

Severity: medium · Component: `src/hands/who.py`, `src/hands/doctor.py`,
docs/INTEGRATION.md; DESIGN §37 "What the laptop found"
Filed by: mission 21 orchestrator, U0 (2026-10-15).
Evidence: the laptop, 2026-10-14, while mission 20 ran (DESIGN §37).

Symptom. Both `handswho` units published every ~20 s because the who
text's relative-time line counts as a change; ~350 publishes an hour from
one address spent the public broker's free daily cap (HTTP 429), so the
daemons' own stops and holds were refused too.

Direction. §37: `handswho` publishes on a real state change only, compared
without the relative-time text, with a floor on the interval; doctor WARNS
on a public `ntfy_url` that the cap exists and names the self-hosted path.

Status: resolved-by-code (mission 22 U2 — `hands.who.WhoPusher.scan` publishes
only when the fingerprint and the picture with its times blanked
(`hands.who.blank_times`) both changed, at most once per `[notify]
who_min_interval_s` (default 60, `hands.config`) counting a refused attempt,
a request at once; doctor's `broker` row (`hands.doctor._broker_check`) WARNS on
a public `ntfy_url`; tests in tests/test_who.py (§38 block), tests/test_doctor.py
(§38 block) and tests/test_config.py)

## H-047 — a `handsd` restart kills the running builder job and nothing resumes it

Severity: medium · Component: `src/hands/daemon.py`, `src/hands/playbook.py`;
DESIGN §37 "What the laptop found"
Filed by: mission 21 orchestrator, U0 (2026-10-15).
Evidence: the laptop, 2026-10-14, while mission 20 ran (DESIGN §37).

Symptom. A `handsd` restart (every install) kills the running builder job;
the `task_killed` rule only notifies, so each install cost a `go` from the
phone.

Direction. §37: the daemon re-queues the kickoff for a builder job its own
stop killed, bounded as `resume` is.

Status: resolved-by-code (mission 22 U3 — a daemon stop records its running jobs
`orphaned` with `orphan_reason: daemon_stop` (runner `cancel(daemon_stop=True)`,
`_final_state`); every new orphan carries `orphan_fed: false` until a start feeds it
once as `<role>.orphaned` after the workers are up (`Daemon._feed_orphans`,
`Spool.orphans_owed`/`mark_orphan_fed`), and the start notification names the resumed
job; tests in tests/test_daemon_stop.py)

## H-048 — under `autonomous` a builder's `blocked` verdict stops for the human

Severity: medium · Component: `src/hands/playbook.py`; DESIGN §37 "What the
laptop found"
Filed by: mission 21 orchestrator, U0 (2026-10-15).
Evidence: the laptop, 2026-10-14, while mission 20 ran (DESIGN §37).

Symptom. Under `autonomous`, a builder's `VERDICT: mission N blocked <unit>`
stops the pipeline for the human, who can only re-fire the role through the
aux by hand.

Direction. §37: the playbook may consult the architect on `builder.done`
with a `blocked` verdict, the consult prompt carrying the builder's reply in
place of a review, counted against the same consultation budget.

Status: resolved-by-code (mission 22 U4 — `hands.playbook.CONSULT_EVENTS`
gives the architect `builder.done`, refused at load unless the rule's verdict
regex names `blocked`; `_architect_subject` writes the builder's verdict line
and full reply under "The builder's blocked verdict and its reply" in place of
the review markers; `templates/PLAYBOOK-missions.toml` carries the rule in its
role-mode block. Tests: tests/test_playbook.py `test_a_role_mode_blocked_*`,
`test_a_blocked_consultation_counts_*`, `test_a_phone_mode_template_stops_*`;
tests/test_kit.py `test_the_role_mode_missions_templates_pass_six_of_six_*`;
tests/test_docs.py `test_the_missions_templates_role_mode_*`)

## H-049 — the protocol's revert step fails for a file the commit adds

Severity: medium · Component: templates/REVIEW-PROTOCOL.md,
meta/REVIEW-PROTOCOL.md; DESIGN §37 "The protocol's revert step", §38
Filed by: mission 22 orchestrator, U0 (2026-10-15).
Evidence: REVIEW-21 should-fix 2 (the U4 sub-agent, in a scratch repo).

Symptom. `git checkout <sha>~1 -- <files>` exits 1 with `pathspec … did
not match` when a listed file does not exist at the parent, and then
reverts none of the listed files. A sub-agent that misses the error runs
the new tests against unreverted code; a red run caused by the missing
file can hide a weak test.

Direction. §38: for each non-test file the body lists, `git checkout
<sha>~1 -- <file>` when the file exists at `<sha>~1`, else `rm` it; run
the commit's new tests and expect red; then `git checkout <sha> --
<files>`. A commit body names added files as added. Mission 22 U7.

Status: resolved-by-doc (mission 22 U7 — templates/ and
meta/REVIEW-PROTOCOL.md step 2: for each listed non-test file, checkout at
<sha>~1 when it exists there, else rm; a commit body names added files as
added)

## H-050 — review 21 ran its sub-agents concurrently against the protocol's one-at-a-time rule

Severity: low · Component: templates/REVIEW-PROTOCOL.md,
meta/REVIEW-PROTOCOL.md; DESIGN §38 "The reviewer's schedule is written
down"
Filed by: mission 22 orchestrator, U0 (2026-10-15).
Evidence: REVIEW-21 Notes ("the five sub-agents ran concurrently");
discotrade HF-008.

Symptom. The protocol says one per-commit sub-agent at a time; REVIEW-21
ran five at once and nothing in the review records the schedule, so the
breach is visible only because the review mentions it.

Direction. §38: the protocol's Notes section requires one line per
sub-agent with its start and end time and states the rule's reason (one
`./scripts/check` at a time inside the 20-minute cap); a review whose
Notes lack the schedule is a should-fix for the next review. Mission 22 U7.

Status: resolved-by-doc (mission 22 U7 — templates/ and
meta/REVIEW-PROTOCOL.md: Notes carry one line per sub-agent with start and
end time; the reason, one ./scripts/check at a time inside the 20-minute
cap; a review lacking the schedule is a should-fix for the next)

## HF-002, HF-004, HF-005 — the onboarding findings, resolved

Severity: medium · Component: `pyproject.toml`, `src/hands/cli.py`,
`src/hands/config.py`, `src/hands/runner.py`, `architect/CLAUDE.md`,
`docs/ARCHITECT-INSTRUCTION.md`, `docs/ARCHITECT-HANDBOOK.md` §6 and §12;
DESIGN §38 "Onboarding"
Filed by: mission 22 U9 (2026-10-15), recording another project's findings.
Evidence: discotrade HF-002, HF-004, HF-005 (cited by DESIGN §36 and §38,
meta/BACKLOG.md "Mission 20" item 8).

Status: resolved (mission 22 U9 — HF-002: the wheel force-includes `docs/`
and `templates/` under `hands/shipped/`; `hands handbook` prints the
installed handbook's path and `--templates` the templates directory; every
role job carries `HANDS_DOCS`; both architect instructions read from it.
HF-004: handbook §6 lists every `playbook.SERIES_KEYS` key with the
loader's default. HF-005: handbook §12 names `hands kit check <kit> --repo
<clone>` at the laptop before a role-mode plan kit's apply, and the first
plan kit's silent apply. Tests: tests/test_handbook.py)
HF-002 resolved in full by mission 23 U7 with H-051's resolution: the
architect role can now reach the handbook (the consult prompt names its path,
and the guard reads under `HANDS_DOCS`); `hands handbook`'s help names
`$HANDS_DOCS/docs/…` (REVIEW-22 should-fix 10).

## H-051 — the architect role cannot learn the value of `HANDS_DOCS`

Severity: medium · Component: `architect/settings.json`,
`driver/hooks/bash_guard.py` (architect table), the architect's consult
prompt; DESIGN §38 "Onboarding", §31, §32
Filed by: mission 22 U9 (2026-10-15).
Evidence: the guard run on three commands with `HANDS_ROLE=architect`
during U9: `echo $HANDS_DOCS` is refused (a `$`, §30), `hands handbook` is
refused (not in the architect's `hands` subcommands, §31), and `cat
<handbook path>` is refused (reads confined to the clone, the spool and
`HANDS_KITS`, §32).

Symptom. §38 has every role job carry `HANDS_DOCS` and the architect read
the handbook and templates from it; U9 does both. But the Read tool, the
one route the guard does not judge (`architect/settings.json` allows
`Read`), takes a literal path, and nothing the role can run tells it the
variable's value. A real role session following `architect/CLAUDE.md`
rule 2 has no proven way to resolve `$HANDS_DOCS`.

Direction (for the architect to decide; U9 did not improvise one): the
consult prompt names the handbook's and templates' paths; or the
architect's table and settings allow `hands handbook [--templates]`; or
the guard's read roots gain `HANDS_DOCS` and the instruction says `cat`.

Status: resolved (mission 23 U7 — the architect's consult prompt names `docs_root()`'s handbook and templates paths; architect mode's read roots gain `$HANDS_DOCS/docs` and `$HANDS_DOCS/templates` (narrowed from §39's "HANDS_DOCS" by mission 23 U10 1276251; the narrower roots are the design, DESIGN §40, H-065) and its `hands` subcommands `handbook`; architect/CLAUDE.md rule 2 says to Read the named paths. Tests: tests/test_playbook.py, tests/test_bash_guard.py)

## H-052 — `project add` writes the architect role's `CLAUDE.md` from the role variant

Severity: low · Component: `src/hands/project.py`; DESIGN §38 "Onboarding",
§31
Filed by: mission 22 U10 (2026-10-15).
Evidence: §38 says `hands project add` "writes the architect's `CLAUDE.md`
from `docs/ARCHITECT-INSTRUCTION.md` with the Parameters filled". That file
is the phone Project's instruction: it tells the reader to install hands in
a sandbox and to deliver files for download, and it has no `KITS`, no `hands
kit file` and none of the role's verdicts (`VERDICT: next kit <name>`,
`series complete`, `escalate`) that the role-mode playbook's consult rules
match. §31 names `architect/CLAUDE.md` "the instruction's role variant", and
docs/INTEGRATION.md's by-hand recipe and `architect/README.md` copy that file
into `~/hands-architect/<project>/`.

Reading taken by U10 (not a design change): the role directory's `CLAUDE.md`
is `architect/CLAUDE.md` (the role variant of the instruction), its
Parameters filled; `docs/ARCHITECT-INSTRUCTION.md`, filled the same way, is
what the command prints last for pasting into the Project. Both now ship in
the wheel under `hands/shipped/`. If the design meant the phone instruction
literally, the role would answer consultations in a vocabulary no consult
rule matches.

Status: resolved (mission 23 U7 — U10's code already writes architect/CLAUDE.md filled and prints the filled phone instruction last; tests pin the written bytes and the `--dry-run` source line. Tests: tests/test_project_add.py)

## H-053 — §38 says `status` hides the architect row; the code shows it

Severity: low · Component: `src/hands/daemon.py` (`Daemon.status`),
`src/hands/cli.py` (`_status_block`), `src/hands/phone.py`
(`status_summary`); DESIGN §38 "The handbook's new sections"
Filed by: mission 22 U11 (2026-10-15).
Evidence: a config with `[roles.builder]` and `[roles.architect]`, loaded
with `load_config` and rendered by `_status_block(Daemon(config).status())`
during U11, prints an `architect idle; queued 0/1 <cwd>` line beside the
builder's. `Daemon.status` iterates `config.roles`, which holds every
configured role, and the phone's `status_summary` iterates the same dict.

Symptom. §38 asks the handbook to say "`status` hides the architect row".
Neither `hands status` nor the phone's `status` hides it. U11 documented
neither reading: the handbook's §18 says what the code does (one line per
configured role, running or idle, `queued N/M`) and makes no claim about the
architect row.

Direction (for the architect): either the design meant another view (for
instance an architect that is not configured, or `hands who`'s phone
picture), and the sentence is corrected in the next DESIGN revision; or
`status` should leave the architect out, which is a code change with its
own test.

Status: resolved-by-doc (mission 23 U9 515b736 — docs/ARCHITECT-HANDBOOK.md
says status prints one line per configured role, the architect's included,
checked against the CLI's status block by test)

## H-054 — §38 says a `[server] ntfy_topic` config refuses to load; the loader still reads it

Severity: low · Component: `src/hands/config.py` (`[server]`/`[notify]`
keys), docs/INTEGRATION.md; DESIGN §38 "The handbook's new sections"
Filed by: mission 22 orchestrator, U12 (2026-10-15), from the U11
sub-agent's report.
Evidence: src/hands/config.py reads `ntfy_topic` and `ntfy_url` from
`[notify]`, falls back to `[server]` ("still read for configs written
before it"), and raises `ConfigError` only when the same key is set in
both tables.

Symptom. §38 asks INTEGRATION to say that a config written before
`[notify]` existed "carries `ntfy_topic` under `[server]` and refuses to
load until it is moved". The loader loads such a config; it refuses only a
key set in both tables (for instance after a `[notify]` section was added
with the same key). U11 documented what the code does, not the design's
sentence.

Direction (for the architect): either correct §38's sentence in the next
DESIGN revision (the refusal is for a key set twice), or make the
`[server]` spelling a load error with a migration message, which is a code
change with its own test.

Status: resolved-by-doc (mission 23 U9 515b736 — docs/INTEGRATION.md says
[server] is the fallback, a key set in both tables refuses to load, and the
migration moves the key; checked against the loader by test)


## H-055 — the protocol's revert step fails for a file the commit deletes

Severity: medium · Component: templates/REVIEW-PROTOCOL.md,
meta/REVIEW-PROTOCOL.md; DESIGN §38, §39
Filed by: mission 23 orchestrator, U0 (2026-10-15).
Evidence: REVIEW-22 should-fix 8 (the U7 sub-agent, in a scratch repo).

Symptom. A file the commit deletes exists at `<sha>~1`, so the revert step
checks it out; the restore `git checkout <sha> -- <the same files>` then
stops with "pathspec did not match" and restores none of the listed files.
H-049's failure turned around; the step does not require a clean `git
status` afterwards, so a reviewer can continue on a half-restored tree.

Direction. §39: `git rm -q` a listed file absent at `<sha>` before the
restore, and `git status --short` must be empty after it. Mission 23 U6.

Status: resolved-by-doc (mission 23 U6 dc9698e — both protocols git rm -q -f
a listed file absent at <sha> before the restore (plain -q refuses the
deletion the revert staged) and require git status --short empty after it; a
scratch-repo test runs the steps)

## H-056 — `no_background.py` runs without `-I`

Severity: medium · Component: .claude/settings.json, docs/INTEGRATION.md;
DESIGN §38, §39
Filed by: mission 23 orchestrator, U0 (2026-10-15).
Evidence: REVIEW-22 should-fix 12: `.claude/settings.json:9` runs
`python3 "$CLAUDE_PROJECT_DIR"/.claude/hooks/no_background.py`; INTEGRATION's
copy line and self-test lack `-I` too.

Symptom. The hook imports json, re and sys, so a module planted in the
role's cwd is imported before the hook runs — the attack `-I` closed for
the guard.

Direction. §39: `python3 -I` in the settings file, the copy line and the
self-test, under the same rule as the guard. Mission 23 U9.

Status: resolved (mission 23 U9 515b736 — .claude/settings.json,
INTEGRATION's copy line and self-test run python3 -I; a planted json.py
beside the hook is ignored by the settings' command, imported without -I)

## H-057 — a daemon restart kills a running review and nothing resumes it

Severity: high · Component: src/hands/daemon.py, src/hands/playbook.py,
PLAYBOOK.toml, templates/PLAYBOOK-*.toml; DESIGN §38, §39
Filed by: mission 23 orchestrator, U0 (2026-10-15).
Evidence: a `handsd` restart at 2026-10-15 20:23 killed the review job of
mission 22 an hour in; no job followed.

Symptom. §38's stop records only builder jobs as orphaned with a reason the
engine feeds; `aux.orphaned` is not in `EVENTS` and no playbook rule
covers it, so a killed review waits for a human who is not told.

Direction. §39: `aux.orphaned` joins the events; the daemon's stop records
an aux job orphaned as it does a builder's; both templates and this
repository's playbook carry `aux.orphaned → resume` (the review's prompt to
a fresh context, bounded by `max_resumes`). Mission 23 U2.

Status: resolved-by-code (mission 23 U2 bcc3d53 — aux.orphaned in EVENTS,
the stop records an aux job orphaned, aux.orphaned -> resume in
PLAYBOOK.toml and both templates; a stop-orphaned review is resumed with its
prompt in a fresh context at the next start; INTEGRATION and the handbook
say a restart kills every running job, U9)

## H-058 — a refused phone command is logged, not published

Severity: medium · Component: src/hands/phone.py, src/hands/notify.py;
DESIGN §39
Filed by: mission 23 orchestrator, U0 (2026-10-15).
Evidence: two phone commands on 2026-10-15 carried the right secret, were
refused by handsd ("no such job"), and the phone saw nothing; the reason
was only in the daemon log. About an hour lost each.

Symptom. The human cannot tell a refused command from a lost one.

Direction. §39: a command with the right secret that handsd refuses is
published on `ntfy_topic` titled `<command>` with the reason; a wrong or
missing secret stays silent. Mission 23 U2.

Status: resolved-by-code (mission 23 U2 bcc3d53 — a refusal of a command
with the right secret is published titled <command> with the reason; wrong
or missing secret silent)

## H-059 — job ids typed on a phone arrive with `O` for `0` and are refused

Severity: medium · Component: src/hands/phone.py, src/hands/api.py,
src/hands/notify.py; DESIGN §39
Filed by: mission 23 orchestrator, U0 (2026-10-15).
Evidence: the same two commands of H-058 carried a job id copied by eye
from a notification, with `O` for `0`.

Symptom. An exact-match id lookup refuses a near-miss a human cannot see.

Direction. §39: ids in `approve`, `deny`, `answer`, `reply`, `cancel` are
matched case-insensitively with `O`→`0`, `l`/`I`→`1`, and a unique prefix
of four or more characters is accepted; an ambiguous prefix is refused with
the candidates; the hold notification prints the id on its own line.
Mission 23 U2.

Status: resolved-by-code (mission 23 U2 bcc3d53 — api.match_job_id: case-
insensitive, O->0, l/I->1, unique prefix of four or more, ambiguous refused
with candidates, in approve, deny, cancel (answer and reply carry no id);
hold notification prints the id on its own line)

## H-060 — the consult journal line after an escalation is left uncommitted

Severity: low · Component: src/hands/playbook.py, src/hands/api.py,
docs/ARCHITECT-HANDBOOK.md; DESIGN §27, §39
Filed by: mission 23 orchestrator, U0 (2026-10-15).
Evidence: after mission 22's escalation the consult line §27 appends to the
builder's `meta/journal.md` was never committed; the next ruling send met a
dirty tree.

Symptom. No builder commit follows an escalation, so the line stays dirty
and the builder's §R treats the tree as a unit in progress.

Direction. §39: the resume path (an `answer`, a cli `--context keep|clear`
send to the builder) prefixes the prompt with one sentence telling the
builder to commit a dirty `meta/journal.md` first when `git status
--porcelain -- meta/journal.md` in its cwd shows it; the handbook's ruling
round says the same for a human. Mission 23 U3.

Status: resolved-by-code (mission 23 U3 e36d558 — an answer and a cli
keep/clear send to the builder are prefixed with the commit-the-journal
sentence when git status --porcelain -- meta/journal.md shows it; the
handbook's ruling round says the same, U9 515b736)

## H-061 — discotrade's playbook has no `aux.orphaned` rule; a restarted review stops its pipeline

Severity: medium · Component: discotrade's `PLAYBOOK.toml` (another
repository); DESIGN §39 "A killed review is resumed (H-057)", §35
Filed by: mission 23 orchestrator, U10 (2026-10-16), from the hosted
review of PR #4, finding 2 "Discotrade reviews stop after restarts"
(meta/reviews/hosted/PR-4/5/issue-comment-6204626963.md).
Evidence: mission 23 U2 (bcc3d53) adds `aux.orphaned` to `EVENTS` and the
rule to this repository's PLAYBOOK.toml and both templates; a project whose
playbook was written from the older templates has no rule for the event.

Symptom. After this merges, a daemon stop that orphans a discotrade review
feeds `aux.orphaned` to an engine with no matching rule, which stops the
pipeline and tells the human instead of re-sending the review. Before it,
the orphaned review was stranded silently, so the stop is the less bad
outcome, but it is not the resume §39 describes.

Direction (for the architect): the next discotrade kit (or the series
switch point of M5b) adds `aux.orphaned → resume` to its playbook; hands
does not edit another project's playbook. Whether `kit check` should warn
on a playbook that has `aux.done` rules but no `aux.orphaned` rule is a
design question.

Status: resolved-by-code (mission 24 U6: `hands kit check` prints a `WARN playbook:` line, and the engine logs a warning at load, for a playbook with an `aux.done` rule and no `aux.orphaned` rule, and likewise `builder.done` without `builder.orphaned`; neither refuses; one function, `playbook.orphaned_rule_warnings`, computes both; docs/PLAYBOOK.md says so)

## H-062 — the monitor raises `task_killed` once per transcript line, not once per task

Severity: medium · Component: src/hands/monitor.py, src/hands/daemon.py;
DESIGN §40 "The monitor's `task_killed`, de-duplicated", §2, §38
Filed by: mission 24 orchestrator, U0 (2026-10-17).
Evidence: 2026-10-16 13:45, two `monitor.task_killed` raises within a
second for a builder the daemon's own stop had orphaned; 2026-10-16 16:05,
three raises within 120 ms for one review job whose single sub-agent ended
and which went on to finish. Each raise fired the playbook's rule and
published a line.

Symptom. The monitor raises once per transcript line that shows a killed
task, on every scan, and also for a job the daemon itself is stopping.

Direction. §40: raised once per killed task, keyed by the task's id in the
transcript, across scans; never for a job the daemon is stopping (its
record is `orphaned`, §38). Mission 24 U3.

Status: resolved-by-code (mission 24 U3 — `MonitorSupervisor` raises `task_killed` once per (session, task id) across every job that reads the transcript, and not for a job `runner.daemon_stopping` names)

Note (mission 25 U0, 2026-10-17): REVIEW-24 should-fix 6 found the session half of the key unpinned (`("", task_id)` left every test green) and the 1024-entry memory's eviction untested. Mission 25 U3 pins the session half (two sessions reporting the same task id each raise once) and the eviction.

## H-063 — `runner.transcript_path_for` ignores `CLAUDE_CONFIG_DIR`

Severity: high · Component: src/hands/runner.py, src/hands/monitor.py;
DESIGN §40 "The transcript path follows the configuration directory"
Filed by: mission 24 orchestrator, U0 (2026-10-17).
Evidence: `runner.transcript_path_for` names `~/.claude/projects/<dashed
cwd>/` by name; a role whose `[roles.<role>].env` sets `CLAUDE_CONFIG_DIR`
keeps its transcripts under that directory's `projects/`.

Symptom. The monitor reads nothing for such a role: no stall and no
task-killed detection. It blocks every credential profile and any manual
rotation by configuration directory.

Direction. §40: the path is computed from the job's environment and
recorded in the job record before the first scan. Mission 24 U3.

Status: resolved-by-code (mission 24 U3 — `runner.transcript_path_for` takes the job's environment and uses `$CLAUDE_CONFIG_DIR/projects/…` when it is set; the runner records it at the init event, before the monitor's first scan)

## H-064 — §39's lenient-id command list named `answer` and `reply`

Severity: low · Component: DESIGN §39, src/hands/phone.py, src/hands/api.py
Filed by: mission 24 orchestrator, U0 (2026-10-17), from REVIEW-23
should-fix 1.
Evidence: §39 says a job id in `approve`, `deny`, `answer`, `reply` and
`cancel` is matched leniently; `answer <secret> <text>` and `reply <secret>
<text>` carry no job id (phone.py), so mission 23 U2 (bcc3d53) applied
lenient matching to `approve`, `deny` and `cancel` only, and a refused
`reply`/`answer` keeps the titles `hands: reply` / `hands: answer`.

Status: decided (DESIGN §40 "Rulings on review 23's should-fix items 1 and
2" — the code's behaviour is the design)

## H-065 — the architect's read roots are narrower than §39 says

Severity: low · Component: driver/hooks/bash_guard.py (`DOCS_SUBDIRS`,
`Reads.__init__`); DESIGN §39, §40
Filed by: mission 24 orchestrator, U0 (2026-10-17), from REVIEW-23
should-fix 2.
Evidence: §39 (H-051's ruling) says "the guard's read roots gain
`HANDS_DOCS`"; mission 23 U10 (1276251) admits only `$HANDS_DOCS/docs` and
`$HANDS_DOCS/templates`, answering the hosted finding "Architects can read
unrelated hands files" (in a source-tree install `docs_root()` is the
repository root). H-051's Status line said the wider roots.

Status: decided (DESIGN §40 — the narrower roots are the design; H-051's
Status line corrected in this commit)

## H-066 — a sub-agent may refuse to author what a unit asks

Severity: medium · Component: templates/BUILDER-N-PROMPT.md,
architect/CLAUDE.md rule 8, docs/ARCHITECT-HANDBOOK.md §17; DESIGN §40, §38
Filed by: mission 24 orchestrator, U0 (2026-10-17), carried from another
project's ledger.
Evidence: discotrade, 2026-10-14, its HF-009.

Symptom. No escalation condition anticipated a unit no agent will author.

Direction. §40: the brief template's sub-agent rules gain `refused: <one
line>`; the orchestrator marks the unit `[b] refused` and continues; the
architect's escalation conditions gain "a unit no agent will author",
answered `VERDICT: escalate ruling: human-supplied content`. Mission 24 U7.

Status: resolved-by-doc (mission 24 U7 — templates/BUILDER-N-PROMPT.md's sub-agent rules carry the `refused: <one line>` sentence and its execution model the `[b] refused` rule; architect/CLAUDE.md rule 8 gains "a unit no agent will author", answered `VERDICT: escalate ruling: human-supplied content` with the human-supplied unit shape; docs/ARCHITECT-HANDBOOK.md §17 says the path. Tests: tests/test_kit.py)

## H-067 — worktrees of aborted review sessions are left registered

Severity: low · Component: templates/REVIEW-PROTOCOL.md,
meta/REVIEW-PROTOCOL.md, src/hands/doctor.py; DESIGN §40
Filed by: mission 24 orchestrator, U0 (2026-10-17), carried from another
project's ledger.
Evidence: discotrade, its HF-010, reviews 13–15.

Direction. §40: the reviewer starts with `git worktree prune`, removes
stale review worktrees of earlier reviews under `/tmp`, ends by removing its
own; `hands doctor` warns on a worktree registered under a role's clone
whose path is missing. Mission 24 U7, U8.

Status: resolved — protocol half resolved-by-doc (mission 24 U7, 649417d — both protocols' reviewer starts with `git worktree prune`, removes stale review worktrees of earlier reviews under `/tmp`, and ends by removing its own; handbook §7 says so. Tests: tests/test_kit.py); doctor half resolved-by-code (mission 24 U8 — `hands doctor`'s `worktrees` row reads each role clone's `.git/worktrees/*/gitdir` and warns on a registered worktree whose path is missing, naming `git worktree prune`. Tests: tests/test_doctor.py)

## H-068 — the review protocol's skip list does not name `plan:`, `journal:` or `report:`

Severity: low · Component: templates/REVIEW-PROTOCOL.md,
meta/REVIEW-PROTOCOL.md; DESIGN §40
Filed by: mission 24 orchestrator, U0 (2026-10-17), carried from another
project's ledger.
Evidence: discotrade, its HF-011.

Direction. §40: `plan:` (read for what it says), `meta:`, `journal:` and
`report:` (read for forbidden edits only, never reviewed as a unit),
`review:` and merge commits. Mission 24 U7.

Status: resolved-by-doc (mission 24 U7 — both protocols' skip list: `plan:` read for what it says, `meta:`/`journal:`/`report:` read for forbidden edits only, `review:` and merge commits skipped; handbook §7 says so. Tests: tests/test_kit.py)

## H-069 — a reviewer's sub-agent ran the gate twice, in the background, or returned early

Severity: low · Component: templates/REVIEW-PROTOCOL.md,
meta/REVIEW-PROTOCOL.md; DESIGN §40
Filed by: mission 24 orchestrator, U0 (2026-10-17), carried from another
project's ledger.
Evidence: discotrade, its HF-012, review 15.

Direction. §40: the protocol's sub-agent rules say "run `./scripts/check`
once, in the foreground, and report only when every command has finished".
Mission 24 U7.

Status: resolved-by-doc (mission 24 U7 — both protocols' per-commit step 3 says "run `./scripts/check` once, in the foreground, and report only when every command has finished"; handbook §7 says so. Tests: tests/test_kit.py)

## H-070 — per-commit reports run past the review protocol's twelve lines

Severity: low · Component: templates/REVIEW-PROTOCOL.md,
meta/REVIEW-PROTOCOL.md; DESIGN §42
Filed by: mission 26 orchestrator, U0 (2026-10-18), carried from another
project's ledger.
Evidence: discotrade, its HF-013, its review 18, 2026-10-17.

Direction. §42: a count nothing enforces is not a rule; both review
protocols drop the twelve lines and say what a report holds — the sha, a
verdict per point, what is not proven, and for the hosted-review sub-agent
every finding verbatim. The brief template keeps its twelve lines.

Status: resolved (mission 27 U4, this commit — DESIGN §43: both review protocols drop the twelve-line count and say what a report holds (the sha, a verdict per point and what is not proven; for the hosted-review sub-agent, every finding verbatim with its verdict on the builder's disposition), and run one gate at a time inside the gate's timeout, 15 minutes (900000 ms) in this repository's protocol, the timeout the project's briefs name in the template; the brief template keeps its twelve lines; the handbook's §7 says so. Tests: tests/test_kit.py, tests/test_docs.py)

## H-071 — the architect's guard refused read-only commands a consultation needed

Severity: low · Component: src/hands/guard (the Bash guard),
architect/CLAUDE.md, the architect's settings allow-list; DESIGN §42, §30
Filed by: mission 26 orchestrator, U0 (2026-10-18), carried from another
project's ledger.
Evidence: discotrade, its HF-014, its consultations 22 and 23.

Direction. §42: the guard refused every command holding `#`, `{` or a
backslash, and the options `ls -R`, `git ls-tree --name-only`, `git status
--short` and `git log --date=<format>`. The characters stay refused (§30);
a content search goes through the Grep and Read tools, and
`architect/CLAUDE.md` rule 10 will say so. The four options are read-only
and will be admitted in the guard's option sets for both guarded modes and
in the architect's settings allow-list, each pinned with its neighbours
still refused.

Status: resolved (mission 27 U4, this commit — DESIGN §43: the guard admits `ls -R`, `git ls-tree --name-only`, `git status --short` and `git log --date=<format>` in role and architect mode, each pinned with `ls -r`, `git ls-tree --name-status`, `git status --porcelain` and a `--date` with no value still refused, in the tests and in the guard's self-test (434 cases); `architect/settings.json` allows `git -C ./repo status`; `architect/CLAUDE.md` rule 10 sends a search of content through the Grep and Read tools; docs/INTEGRATION.md's table lists the options. Tests: tests/test_bash_guard.py, tests/test_docs.py)

## H-072 — a gate run on a shared machine ran past the timeouts

Severity: low · Component: docs/INTEGRATION.md, briefs; DESIGN §42, §36
Filed by: mission 26 orchestrator, U0 (2026-10-18), carried from another
project's ledger.
Evidence: discotrade, its HF-006, the 2026-10-17 update.

Direction. §42: a gate run on a shared machine took 1281 s, past a brief's
20-minute timeout and hands' 15-minute default (`BASH_MAX_TIMEOUT_MS`,
§36). A project whose gate runs longer raises `BASH_DEFAULT_TIMEOUT_MS` and
`BASH_MAX_TIMEOUT_MS` in its `[roles.builder.env]` and `[roles.aux.env]`,
and its briefs name a timeout no longer than that; docs/INTEGRATION.md
states the raise and the installed CLI's ceiling if it has one. hands'
default is unchanged; hands' own briefs name 15 minutes (900000 ms).

Status: resolved-by-doc (mission 26 U4 — docs/INTEGRATION.md states the raise of `BASH_DEFAULT_TIMEOUT_MS` and `BASH_MAX_TIMEOUT_MS` in `[roles.builder.env]` and `[roles.aux.env]`, briefs naming a timeout no longer than that, and that the installed CLI (2.1.302, read from its bundled files) has no ceiling of its own on `BASH_MAX_TIMEOUT_MS`; hands' default unchanged. Tests: tests/test_operator_table.py)

## H-073 — route 4 relies on a §R sentence a project's older brief does not carry

Severity: medium · Component: docs/ARCHITECT-HANDBOOK.md §19 (route 4),
templates/BUILDER-N-PROMPT.md §R; DESIGN §42
Filed by: mission 26 orchestrator, U5 (2026-10-18), from PR #6's hosted
review (finding "Discotrade skips mid-mission rulings").
Evidence: meta/reviews/hosted/PR-6/1/ — the reviewer reads that another
project's active brief (its mission 20) has a §R recovery brief without
§42's owner-file sentence.

Problem. Route 4 sends an owner file as a decisions kit and then `go`; the
builder carries out the owner file's "For the builder" steps only because
the brief's §R says so (§42, "The newest owner file, on a resume"). A
brief written before the template gained that sentence — any mission in
flight when this release is installed — resumes from its checkpoint and
does not act on the ruling, although the decisions kit is committed.

Decision needed. Whether the operator table's route 4 names the condition
(the brief's §R carries the sentence) and gives the fallback for a brief
without it (`answer <secret> <text>` naming the owner file after `VERDICT:
question`, or a `keep` send naming it), or whether the instruction paste
due after this release asks each project's chat to add the sentence to its
brief in flight. Not fixed in mission 26: the routes are §42's text.

Status: resolved (mission 27 U2, this commit — DESIGN §43: every builder job but an apply (a job with a `kit_id`, or a resume of one found through `resumed_from`) is dispatched with §43's owner sentence, after the journal sentence, naming the owner files with no `meta/CHECKPOINT.md` update since, oldest first, decided in a worker thread and counted by the prompt cap; one helper (`sent_prompt`) strips hands' sentences for `is_kickoff`, `consults_used`, the limit resume, the playbook `resume` action, §36's listing and the job summary line; the handbook's §4, §14 and §19 route 4 say hands names the owner file itself. Tests: tests/test_playbook.py, tests/test_operations.py, tests/test_limits.py)

## H-074 — a long gate backgrounded with no sanctioned wait, and the variable that stops it refused by hands' own hook

Severity: medium · Component: .claude/hooks/no_background.py,
src/hands/runner.py, src/hands/doctor.py, pyproject.toml,
templates/BUILDER-N-PROMPT.md, both review protocols,
docs/ARCHITECT-HANDBOOK.md §7, docs/INTEGRATION.md §21; DESIGN §43
Filed by: mission 27 orchestrator, U0 (2026-10-18), carried from another
project's ledger.
Evidence: discotrade, its HF-015 and HF-016, 2026-10-18; its commit
5ca133c; its jobs 0mvdoby7d-j90u, 0mvdxwh7s-y3e4 and 0mvdxy6xp-ysvh; its
hook copy's commit 3fbed1d (2026-10-11, the same bytes as hands' main).
Claude Code 2.1.300, read from its binary's strings on 2026-10-18 (nothing
run; the `Agent` schema confirmed by that project's probe under 2.1.302):
the `sleep` refusal (a first statement `sleep N`, N ≥ 25 s) is Claude
Code's own guard; for a command moved to the background the harness
advises one foreground command that blocks until the output file shows
what is needed; `BASH_MAX_TIMEOUT_MS` has no ceiling and a call's
effective timeout is the smaller of its own and that variable;
`CLAUDE_CODE_DISABLE_BACKGROUND_TASKS` counts as set only when its value,
trimmed, is `1`, `true`, `yes` or `on` in any case, and then no command is
moved to the background, the `sleep` guard is off, a sub-agent always
launches in the foreground, `SendMessage` runs inline, and the `Agent`
schema has no `run_in_background`; hands' hook refuses an omitted or null
flag (§23, H-014), so under the variable every sub-agent call is refused;
a hook's environment is the session's.

Problem. HF-015: a builder's long gate reached its timeout, the harness
moved it to the background, and nothing hands ships gave the builder a
sanctioned way to wait. HF-016: the project set the variable to stop the
backgrounding, and its builder could not start a sub-agent, because
hands' own hook refused every call (one stop; the variable was removed).

Direction. DESIGN §43 rules 1–6: the hook admits an omitted or null flag
under the variable's true spellings; the wheel ships the hook; doctor
warns on a role's copy that is not the installed hands' copy; the runner
sets the variable for a builder or aux job only when the role's copy is
the installed copy; the role's env table decides either way and an
inherited value reaches no job; the wait rule (prevent, an exit marker, a
blocking foreground wait) in the brief template, both protocols and the
handbook's §7.

Status: resolved (mission 27 U3 3383ffe, rules 1–5; mission 27 U4, this commit, rule 6 — the wait rule's three parts (a) prevent, (b) an exit marker, (c) one blocking foreground wait, word for word where §43 quotes them, in both review protocols' hosted-review and per-commit sub-agents, the brief template's sub-agent brief (its timeout the placeholder `<the gate's timeout, in ms>`) and the handbook's §7; this repository's protocol names 15 minutes (900000 ms). Tests: tests/test_kit.py)

## H-075 — a role-filed kit that carries the playbook is approved by the engine under autonomy

Severity: medium · Component: src/hands/playbook.py (`_release_kit`),
src/hands/kit.py (`kit check`), architect/CLAUDE.md rules 3 and 8,
docs/ARCHITECT-HANDBOOK.md §3, §6, §12, §19; DESIGN §43
Filed by: mission 27 orchestrator, U0 (2026-10-18).
Evidence: found 2026-10-18 by the architect while checking another
project's budget raise; scheduled by the human at 17:24.

Problem. Under `[series] architect = "role"` with `autonomous = true` the
engine approves every apply of a kit the architect role filed, judging its
provenance and never its content. A kit carrying `PLAYBOOK.toml` or
`meta/PLAYBOOK.toml` is approved too, so the role could raise its own
`max_architect_consults`, drop a stop rule or change the kickoff without
the human seeing it.

Direction. DESIGN §43 "A playbook change is the owner's": `_release_kit`,
after `kit_apply_problem` accepts and `_kit_bytes_unchanged` verifies,
holds such an apply for the human with its buttons and the reason §43
gives; no engine kickoff after the human approves it, the playbook's `kit
applied` rule fires; `hands kit check` prints a `WARN playbook:` line.

Status: fixed (mission 27 U5, this commit — DESIGN §43: `_release_kit`, after `kit_apply_problem` accepts the apply and `_kit_bytes_unchanged` verifies the stored zip, does not approve an architect-filed apply whose stored kit carries `PLAYBOOK.toml` or `meta/PLAYBOOK.toml` (`Spool.stored_kit_playbooks`, by the zip's central-directory names); `kit_apply_problem` is unchanged, so the kit stays a filed kit to the `next kit` wait, `defer_hold` and the `job.held` path; the hold is published with its buttons and the reason `apply <name>: the kit carries <path>, the playbook in force; a change of the playbook is the owner's (§43)`, passed to `Daemon.publish_hold` as `reason=` wherever the engine publishes a hold it does not approve, a paused pipeline's included; the gate's reason stays `apply <name>`; after a human approval no engine kickoff, the playbook's `kit applied` rule fires; `hands kit check` prints a `WARN playbook:` line when the repository's playbook or the kit's own is role mode with autonomy; architect rules 3 and 8, the handbook's §3, §6 and §12, and the role-mode kickoff notes of the missions playbook and brief templates. Tests: tests/test_playbook.py, tests/test_kit.py, tests/test_consult.py, tests/test_docs.py)

## H-076 — `test_kit_apply_refuses_a_staged_name_with_dot_dot` fails intermittently

Severity: medium · Component: tests/test_operations.py (and the code it
drives, if the race is there); DESIGN §43
Filed by: mission 27 orchestrator, U0 (2026-10-18), from REVIEW-26
should-fix 1.
Evidence: `tests/test_operations.py::test_kit_apply_refuses_a_staged_name_with_dot_dot`
failed twice at b956e2a (mission 26 U1): once in the builder's U1 gate
and once in the review's run, `1 failed, 4737 passed`; green alone, with
its file and at every other commit. The test dates from mission 24
(2f9e219). Leads (the architect's sandbox, 2026-10-18, at f16d6d1 and with
the mission-27 kit applied, run as uid 0 on a loaded machine):
`tests/test_library.py::test_open_refuses_a_running_job` failed in both
full-suite runs and passed alone;
`tests/test_gates.py::test_cancel_is_gated_by_default_and_approval_performs_it`
failed in one full-suite run and once alone, then passed alone. At U0 on
the laptop (mission-27 from 1b822a5, the kit applied), three full gate
runs failed only `test_the_fixture_is_section_10s_example_verbatim` (the
expected base red), `1 failed, 4833 passed` each; none of the three tests
above failed.

Problem. A gate that can go red on an unchanged tree is a gate nobody can
read.

Direction. DESIGN §43 "The intermittent test": find the race and fix it,
in the test or the code; if no cause is found, run the test in a loop
under the suite's conditions, record the count and result here, and pin
what can be pinned.

Found (mission 27 U1). A race between the test and the clock, in the test,
not in the code. `tests/harness.py::kit_zip` writes each entry with
`zipfile.ZipFile.writestr(name, text)`, which stamps it with
`time.localtime(time.time())` at the call, in the zip's DOS time of two
seconds' resolution. The test wrote the target with one `kit_zip(passing_kit())`
before the daemon started and compared it, after the start and one request,
with a second `kit_zip(passing_kit())`; when the clock crossed an even second
between the two calls the bytes differed (offset 10, the local header's time)
and the assertion `target.read_bytes() == kit_zip(passing_kit())` failed. The
longer the daemon's start, the likelier: a loaded machine, or a commit that
lengthens the start. `test_kit_apply_refuses_a_staged_symlink_and_removes_the_link_only`
had the same comparison. Reproduced ad hoc (not committed) by delaying
`Daemon.start` 2.1 s: both tests red at the old comparison, green at the fixed
one. No other test compares with a second `kit_zip` or `crafted_zip` call
(`grep` over tests/).

Fixed in the test: both compare the target with the bytes they wrote. Pinned by
`tests/test_operations.py::test_the_staged_refusals_hold_whatever_the_clock_does_between_two_zips`
(both cases), which gives every `kit_zip` call a timestamp of its own: red at
the old comparison, green at the fixed one.

The leads, looked at with the same eye: neither
`tests/test_library.py::test_open_refuses_a_running_job` nor
`tests/test_gates.py::test_cancel_is_gated_by_default_and_approval_performs_it`
compares generated bytes; both wait on a real fake-claude process (60 s body
bound, a cancel wait of `cancel_grace_s` + 10 s). No cause was found for them.
On the laptop at mission 27 U1 (machine otherwise idle): the two together 20
times in a loop, 20 passed; their files with tests/test_operations.py 3 times,
all passed; the U1 gate runs, recorded in the commit. Not proven: that the
zip timestamp was the cause of mission 26's two failures (their output was not
recorded), nor anything about the leads under the architect sandbox's load or
uid 0.

Status: resolved (test: mission 27 U1 — the race found and fixed in
tests/test_operations.py, pinned there); the two leads not reproduced, no
cause found, open as leads only (§43).

## H-077 — a role-filed kit entry naming the playbook in another case passes the engine's playbook check

Severity: low · Component: src/hands/spool.py (`stored_kit_playbooks`),
src/hands/kit.py (the `WARN playbook:` line); DESIGN §43, §26
Filed by: mission 27 orchestrator, U7 (2026-10-19), from PR #7's hosted
review (finding 1, "Role kits can rewrite the playbook by changing its
case").
Evidence: meta/reviews/hosted/PR-7/1/review-comment-4309801219.md — the
check recognises only the exact entries `PLAYBOOK.toml` and
`meta/PLAYBOOK.toml`; an entry `playbook.toml`, `Playbook.toml` or
`Meta/PLAYBOOK.toml` is approved by the engine, and on a case-insensitive
filesystem the apply's `unzip -o` would write it over the playbook in
force.

Problem. §43 names the two paths `hands kit check` reads and the engine
loads. On the case-sensitive filesystems hands runs on (Linux; the
systemd units of §14), such an entry is a different file from the
playbook in force and changes no rule; on a case-insensitive filesystem
(a casefolded directory, a macOS clone) it would replace it, past the
human.

Decision needed. Whether §43's check matches the two paths
case-insensitively (any entry whose casefolded path is `playbook.toml` or
`meta/playbook.toml`), or refuses such an entry outright at `kit check`,
or stands as written for a case-sensitive filesystem. Not changed in
mission 27: §43 names the paths exactly, and widening them is the
design's.

Status: resolved (mission 28 U4, this commit — DESIGN §44 "H-077, ruled": one test, `spool.carries_playbook`, counts an entry as carrying the playbook when its casefolded path equals the casefolded configured playbook path (`[playbook] path` read as a repository path with the builder cwd's own place before it, `playbook.playbook_repo_path`) or either fixed name; the engine's hold and published reason (`stored_kit_playbooks`, also asked by the daemon's `decide_held_reason`) and `hands kit check`'s `WARN playbook:` line use it; the WARN judges the repository's playbook at the configured path as well as the fixed names and ends naming the names it knows — without a project configuration, the two fixed names only; the `playbook` check is unchanged. Tests: tests/test_playbook.py, tests/test_kit.py)

## H-078 — a human pause drops the event that would start the next step

Severity: medium · Component: src/hands/playbook.py (`on_event`'s paused
branch, `pause`, `resume`, `_unpause`), src/hands/daemon.py
(`_feed_orphans`); DESIGN §10, §44
Filed by: mission 28 orchestrator, U0 (2026-10-19).
Evidence: another project's ledger (discotrade), its HF-017 (2026-10-19):
its builder job 0mve1pq5x-jej2 ran a whole mission while three owner
commits waited from 2026-10-18 21:14, and its aux guard replied `VERDICT:
blocked busy`. The code read at f16d6d1 and d587fa6: `playbook.py`
`on_event`'s paused branch logs "fires nothing" and returns, so a paused
pipeline drops every event it receives; `pause` is a stop and `resume`
un-pauses (`_unpause`) without replaying anything; nothing publishes the
moment the series has come to rest; `daemon.py` `_feed_orphans` feeds each
orphan once and marks it fed before the engine hears it, so a restart while
the pipeline is paused consumes the builder's orphan and nothing ever
resumes it.

Problem. In an autonomous series a builder job spans a whole mission, so
the first job boundary is the mission's end. A human who needs the working
tree quiet for an owner commit cannot stop the series at the next
boundary: `pause` lets the running job finish and then drops its end, so
the series is lost rather than held, `resume` does not take it up again,
and the human must poll `jobs` to learn when the tree is quiet.

Direction. DESIGN §44 "A pause that holds the next step", rules 1-6: under
a human pause (`paused_by` `cli` or `phone`) a role's end that would start
the next step is kept, one per role; everything else is as under any pause
and every suppressed stop is notified; `resume` rules fire until a stop is
suppressed under the pause; only `resume` ends a human pause, reloading the
playbook and replaying the kept ends up to the first that starts a job or
stops; `hands: at rest` is published once nothing runs; the state lives in
`pipeline.json`.

Status: resolved (mission 28 U1 d367373, rules 1, 2, 3, 5 and 6; mission 28 U2, this commit, rule 4 and the documentation — DESIGN §44: under a human pause a role's end that would start the next step is kept, one per role, in `pipeline.json`; a `notify` end fires; a `resume` rule fires until a stop is suppressed under the pause, and every suppressed stop is notified; `go` and `consult` are refused naming `resume`; `resume` reloads, refuses on a playbook that does not load, replays the kept ends up to the first that starts a job or stops and discards the rest; `hands: at rest` is published once per human pause (the mark in `pipeline.json`) at the first moment no job is running, queued or held and no §6 resume is scheduled, checked when the pause is sent, on every job end the engine hears, a denial, a cancel while queued and a job that could not spawn, naming each kept end or that none is kept, and again with the new list when a kept end is replaced after it; the handbook's §10, §14, §18 and §19, docs/PLAYBOOK.md and docs/OPERATIONS.md say so. Tests: tests/test_human_pause.py, tests/test_playbook.py, tests/test_phone.py, tests/test_operator_table.py)

## H-079 — `hands: at rest` is not published again when an end of another role is kept after it

Severity: low · Component: src/hands/playbook.py (`_keep`, the at-rest
mark); DESIGN §44 rule 4, §45
Filed by: mission 29 orchestrator, U0 (2026-10-21), from REVIEW-28
should-fix 1 (2026-10-20).
Evidence: meta/reviews/REVIEW-28.md should-fix 1; the code read at adb061b:
`_keep` clears the at-rest mark only when a kept end is replaced, so an end
of a role with nothing kept yet, kept after the mark (a laptop `hands send`
to the aux under the pause, whose `aux.done` is then kept), publishes
nothing.

Problem. The kept list the human or a project chat guards on is stale:
`hands: at rest` named the builder's end only, while the aux's end is kept
too and `resume` will replay it.

Direction. DESIGN §45 "Review 28's should-fix items" 1: rule 4 publishes
`hands: at rest` once per human pause at the first moment nothing runs, and
again, with the new list, at the first such moment after the kept list has
changed (an end kept or replaced after the last publication); the mark
records when it was last published; a restart publishes nothing unless an
end was kept after the mark.

Status: resolved (mission 29 U6, this commit — DESIGN §45 "Review 28's should-fix items" 1: under a human pause an end kept or replaced after `hands: at rest` was published sets `kept_since_rest` in `pipeline.json` (`PlaybookEngine._keep`), and `check_at_rest` publishes `at rest` again, with the new list, at the first moment after it that no job is running, queued or held and no §6 resume is scheduled, then clears it; `at_rest` records the last publication. A daemon start publishes nothing unless an end was kept after the mark and not yet published. The handbook's §19 `at rest` row, docs/PLAYBOOK.md and docs/OPERATIONS.md say it. Tests: tests/test_human_pause.py, tests/test_docs_45.py)

## H-080 — an apply that did not land meets the playbook's rules

Severity: medium · Component: src/hands/playbook.py (`_engine_rules`,
`_under_human_pause`); DESIGN §27, §31, §43, §44, §45
Filed by: mission 29 orchestrator, U0 (2026-10-21), from the architect's
reading of 1acc9e0 (2026-10-20).
Evidence: the code at 1acc9e0: an apply's `builder.done` goes to the
playbook's rules like any builder end — this repository's catch-all
`^VERDICT:` consults the driver about a "question" that is not one, the
templates' last rule stops with "Builder finished without a recognised
verdict", which says nothing of the kit; and under a human pause §44 rule 1
keeps it as the builder's end, replacing the kept end of the mission it was
sent beside.

Problem. Under the pull-request gate an apply that does not land (a red
check, a refused push or merge) becomes ordinary, and its end is decided by
rules written for a mission's builder.

Direction. DESIGN §45 "An apply that did not land (H-080)": the
`builder.done` of an apply as §43 counts one whose reply does not begin
`VERDICT: kit applied` is the engine's to decide, before any playbook rule:
over an unpaused pipeline a stop with §45's reason, over a paused one one
publication; never kept, never replacing a kept end.

Status: resolved (mission 29 U4, this commit — DESIGN §45 "An apply that did not land (H-080)": the `builder.done` of an apply as §43 counts one (`chain_first`: a job with a `kit_id`, or a resume of one) whose VERDICT: line does not begin `VERDICT: kit applied` is decided by the engine before any playbook rule (`PlaybookEngine._apply_not_landed`): over an unpaused pipeline a stop, `the kit's apply did not land: <its VERDICT: line cut to 200 characters, or "no VERDICT: line"> (§45)`, titled `hands: the pipeline stopped`; over a paused one the reason is published once — under a human pause as `hands: a stop under a human pause`, under any other pause titled as a stop — and the pause, its reason and the kept ends stay; never kept. A landed apply and a `hands send` are decided as before. With it, §45's CI hold (`spool.carries_ci`, `ci_hold_reason`, `hands kit check`'s `WARN ci:` line) and the `pull-request` journal sentence (`JOURNAL_REMINDER_PULL_REQUEST`); the handbook's §19 rows. Tests: tests/test_apply_not_landed.py, tests/test_operator_table.py)

## H-081 — the review's merge does not tie the merged head to the reviewed one

Severity: medium · Component: meta/REVIEW-PROTOCOL.md,
templates/REVIEW-PROTOCOL.md (the merge under `pull_request`); DESIGN §35,
§45 "The review"
Filed by: mission 29 orchestrator, U7 (2026-10-21), from PR #9's hosted
review (finding 1, "A review can merge unreviewed commits").
Evidence: meta/reviews/hosted/PR-9/1/ — the protocol waits for the checks
by pull request number (`hands ci-wait <number>`) and merges with `gh pr
merge <number> --merge --subject …`; nothing checks that the head merged is
the review's own commit on top of the reviewed tip. A commit pushed to the
branch during the review would pass the checks and be merged unreviewed.

Problem. §45 gives the merge command word for word, and the protocols and
their pins quote it; adding a guard changes that text.

Decision needed. Whether the merge carries `--match-head-commit <the
review commit's sha>` (gh refuses the merge when the head moved), and the
`not merged` blocker then covers a moved head. Not changed in mission 29:
the command is §45's.

Status: resolved (mission 30 U3, this commit — DESIGN §46 "H-081": both review protocols (templates/REVIEW-PROTOCOL.md and this repository's copy, the template with `SigorMatt/hands` and the 15-minute timeout), in every review of a pull request — its file going to `main` or to the branch; not in the direct shape, not for a `reviewed: none` review — check before the review's commit, after `git fetch origin`, that `git rev-parse origin/<branch>` is the whole `reviewed:` sha, else the blocker "the branch moved during the review: <reviewed sha> → <its tip>" and no merge; a refused push of the review's commit is the same blocker (rebase onto the new tip and `review: mission N (branch moved)`, or, when that fails too, `git rebase --abort`, the tree to `main`, `git branch -f <branch> origin/<branch>` and the blocker in the reply); the merge is `gh pr merge <number> --merge --match-head-commit <sha> --subject "merge: mission N (PR #<number>)"`, `<sha>` the reviewed tip on `main` or the review's own commit on the branch; a merge refused or not made, with or without the rule, is the `not merged` blocker committed where the review was. With it, §46's merge rule: a confirmed defect in what the pull request adds or changes, or one at the base it makes reachable or relies on, is a blocker; any other defect at the base a should-fix marked "to be filed"; in the direct shape a blocker; the `## Hosted review` section says which. The brief template's last unit and the handbook's §9 and §19 say so. Tests: tests/test_docs_46.py, tests/test_docs_45.py, tests/test_docs.py, tests/test_kit.py)

## H-082 — the `pull-request` apply prompt's case (b) matches `main` itself

Severity: high · Component: src/hands/kit.py (`PULL_REQUEST_APPLY`); DESIGN
§45 "The apply (§27), by the setting"
Filed by: mission 29 orchestrator, U7 (2026-10-21), from PR #9's hosted
review (finding 2, "Applies from main take the mission-branch path and
fail").
Evidence: meta/reviews/hosted/PR-9/1/ and §45's prompt, which the code
quotes word for word (cd0e13f): case (b) is "On another branch, not a
`kit/` one, that is on `origin` … and whose pull requests, if it has any,
are all open". `main` is on `origin`, is not a `kit/` branch, and no pull
request has `main` as its head, so a builder on `main` between missions —
the usual place of an apply — takes (b): it commits on `main` and pushes,
the gate refuses the push, it replies `VERDICT: kit not applied pr=none`,
and the engine stops (U4). Case (c) "On any other branch: `git checkout
main`. Then, on `main`: …" and the bullet "A mission in flight is the
branch case (b) … left for `main` (c)" show the intent: `main` is (c).

Problem. Under `[repository] main = "pull-request"` every apply started on
`main` would stop without a pull request. Nothing reaches it while the
setting is `direct` (the `direct` prompt is another text), so this
repository is safe until the switch of docs/PR-CI-GATE.md's "hands"
section step 2 — which must not be made before this is decided.

Decision needed. Proposed: case (b) reads "On another branch, not `main`
and not a `kit/` one, …" (the code, handbook §3's quotation and the
pinning tests moved to it by the next mission). Not changed in mission 29:
the prompt is §45's word for word.

Status: resolved (mission 30 U1, this commit — DESIGN §46 "H-082": `PULL_REQUEST_APPLY`'s case (b) begins "(b) On a branch that is neither `main` nor a `kit/` one, that is on `origin`", the rest of §45's prompt unchanged, so a builder on `main` is not case (b)'s; the handbook's §3 quotes it. With it, review 29's should-fix 3: `[repository] main` of any other value, whatever its type (`true`, `1`, `"squash"`), refuses to load as `[repository] main must be "direct" or "pull-request", got <the value>` (`config._choice`). Tests: tests/test_apply_shape.py, tests/test_docs_45.py, tests/test_config.py)

## H-083 — the CI hold names `.github/` and `scripts/check`, not the gate's other inputs

Severity: medium · Component: src/hands/spool.py (`carries_ci`); DESIGN
§43, §45 "A kit that carries the CI is the owner's"
Filed by: mission 29 orchestrator, U7 (2026-10-21), from PR #9's hosted
review (finding 6, "Kits can still weaken the gate their PR merges on").
Evidence: meta/reviews/hosted/PR-9/1/ — `scripts/check` runs `uv sync`,
`ruff check .` and `pytest`, which `pyproject.toml`, `uv.lock` and
`tests/conftest.py` (and any test file) configure; a role-filed kit that
changes `addopts`, a ruff exclude or a conftest is approved by the engine,
and its own pull request's check runs the gate it changed.

Problem. §45 names the two paths exactly; the gate's configuration is
wider, and a kit's tests are its own to change (kits add tests every
mission), so no path list closes it whole.

Decision needed. Whether the hold widens to the gate's configuration files
(`pyproject.toml`, `uv.lock`, `tests/conftest.py`, a project-configured
list), or stands, the review's forbidden-edit blocker and the human's
reading of the pull request being the rest. Not changed in mission 29: the
paths are §45's.

Status: resolved (mission 30 U2, this commit — DESIGN §46 "H-083": the engine approves a role-filed kit's apply under an autonomous role-mode playbook only when every file entry is a plan file (`spool.is_plan_file(entry, named)`: in exact case `KIT.md`, `DESIGN.md`, `WORKPLAN.md`, a root `decisions-<name>.md`, or Markdown under `meta/` not in `named`) and it carries no playbook; `named` is `kit.send_named_paths` (`named_paths` over the `send` rules' prompts of the repository's playbook in force, placeholder paths left out), reached from playbook.py by an import inside `PlaybookEngine._stored_kit_non_plan`; any other kit is held with `playbook.plan_hold_reason`'s sentence naming the first such entry in sorted order (§43's reason when it carries the playbook), `Spool.stored_kit_non_plan` reading the stored zip's file entries; `carries_ci`, `stored_kit_ci` and `ci_hold_reason` removed; `hands kit check`'s `WARN owner:` line (`--json` `owner_warnings`) in place of `WARN ci:`; architect rule 3 and rule 8; the handbook's §3, §12 and §19, docs/PLAYBOOK.md, docs/INTEGRATION.md and both templates' comments. Tests: tests/test_plan_files.py, tests/test_docs_45.py, tests/test_operator_table.py)

## H-084 — the review's file on its failure paths: committed nowhere, read from the branch

Severity: medium · Component: meta/REVIEW-PROTOCOL.md,
templates/REVIEW-PROTOCOL.md ("`main`'s rules", "The commits under
review"); DESIGN §45 "The review"
Filed by: mission 30 orchestrator, U0 (2026-10-22), from REVIEW-29
should-fix 2 (PR #9's hosted finding 5, 2026-10-21).
Evidence: meta/REVIEW-PROTOCOL.md at 4d32d35, "`main`'s rules" and "The
commits under review": under `pull_request` the `reviewed: none` review of
a missing pull request, and of a Direct brief, is committed nowhere, while
the review of a failed rules read goes to the mission's branch when it
exists; and the architect is told to read a review with blockers from the
branch.

Problem. A review the architect is told to read from the branch is, on two
of the three failure paths, committed nowhere, so the architect finds
nothing there to read.

Direction. DESIGN §46 "Review 29's should-fix items" 2.

Status: resolved (mission 30 U3, this commit — DESIGN §46 "Review 29's should-fix items" 2: both review protocols commit the review of a failed rules read, whatever the rules, and under `pull_request` that of a missing pull request, to the branch the brief's Branch section names when it exists on `origin` (`git ls-remote --exit-code --heads origin <branch>`), never to `main`, and otherwise nowhere; a Direct brief's under `pull_request` nowhere; the reply carries the blocker in every case; §45's "nowhere" for a missing pull request is gone. The handbook's §9 and §19 say so. Tests: tests/test_docs_46.py, tests/test_docs_45.py)

## H-085 — nothing returns the tree to `main` after the review commits to the branch on a failure path

Severity: medium · Component: meta/REVIEW-PROTOCOL.md,
templates/REVIEW-PROTOCOL.md; DESIGN §45 "The review"
Filed by: mission 30 orchestrator, U0 (2026-10-22), from REVIEW-29
should-fix 4 (2026-10-21).
Evidence: both protocols at 4d32d35: a review that commits its file to the
mission's branch on a failure path checks that branch out, and no step
returns the tree to `main` after it.

Problem. The next kit's apply runs in this tree and expects `main`; a tree
left on the mission's branch takes another case of the apply prompt.

Direction. DESIGN §46 "Review 29's should-fix items" 4.

Status: resolved (mission 30 U3, this commit — DESIGN §46 "Review 29's should-fix items" 4: both review protocols end, in every shape, in a section `## The end (every shape)`: a review that has checked out the mission's branch ends with `git checkout main && git pull --ff-only`, and the failure paths end as it says; the handbook's §9 says so. Tests: tests/test_docs_46.py)
