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
