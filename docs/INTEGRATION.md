# Integration — putting hands on the laptop

DESIGN §14, as a checklist. Do it once per machine (steps 1–2), then once per
project (steps 3–8). Every command here was run against the CLI in this repo;
where something has never been proven, it says so.

Nothing in hands is a background daemon you have to trust blindly: `hands
doctor` is the check, and `hands status`, `hands pipeline` and `hands inbox`
are the whole of its state.

---

## 1. Install (once per machine)

    uv tool install ~/git/hands        # -> "Installed 3 executables: hands, handsd, handswho"

`~/.local/bin` must be on your PATH (`uv tool update-shell` adds it). Check:

    hands --version
    handsd --version

Python ≥ 3.11 and `uv`. The only runtime dependency is `httpx`, for ntfy.

## 2. Run handsd (once per machine, per project)

    install -Dm644 ~/git/hands/systemd/handsd@.service ~/.config/systemd/user/handsd@.service
    mkdir -p ~/.config/hands && touch ~/.config/hands/<project>.env
    systemctl --user daemon-reload
    systemctl --user enable --now handsd@<project>
    journalctl --user -u handsd@<project> -f

The unit is a **user** unit — hands spawns `claude -p` as you, with your
subscription login and your `~/.claude` settings — and it is templated: the
instance name is the project (`handsd@<project>` runs `handsd --project
<project>`), and the instance reads `~/.config/hands/<project>.env`, that
project's environment file (`KEY=value` lines; it may be empty, but it must
exist). Nothing comes from a login shell. `Restart=on-failure`; `ExecStart` is
the absolute `%h/.local/bin/handsd` because a unit has no PATH from your shell.
A second project is a second instance of the same unit (see "Two projects on
one laptop" below).

Without systemd, `handsd --project <project>` in a terminal is the same thing.

## Two projects on one laptop (§29)

Each project has its own config, its own daemon and its own spool, and one
directory per role that lives outside the repository — `~/hands-driver/<project>/`
for the driver and `~/hands-architect/<project>/` for the architect role (§31):

    ~/.hands/<project>.toml     the config (§13)
    ~/.hands/<project>/         the spool: jobs/, roles/, inbox.jsonl,
                                inbox.acks.jsonl, pipeline.json, and the
                                daemon's default socket, handsd.sock

A project name matches `[A-Za-z0-9][A-Za-z0-9._-]{0,63}` (§30): `--project`,
`$HANDS_PROJECT` and the stem of every `~/.hands/*.toml`. Any other name is
refused with a message naming it and the pattern, exit 1, before anything is
read or created; in `hands who` a config file whose stem does not match is the
root line `<stem>: config error <reason>`. The pattern still admits `jobs` and
`roles`, which are also names of the flat layout below; do not use them.

Two daemons are two instances of the templated units, each with its own
environment file:

    touch ~/.config/hands/spanweave.env ~/.config/hands/agile-skills.env
    systemctl --user enable --now handsd@spanweave handsd@agile-skills
    systemctl --user enable --now handswho@spanweave    # optional, per project

A daemon reads and writes only its own project's spool. The default
`server.socket` is inside that spool, so two projects never share one; a config
that sets `server.socket` must name a path no other project's config names.
`hands who` reads every project that has a config in `~/.hands/` and shows each
daemon as a root of the picture; `handswho@<project>` pushes only its own
project's picture to its own `who_topic`. Each config is loaded on its own: one
that does not load is shown as the root line `<project>: config error <reason>`
and the others still render (exit 0); when none loads, `hands who` exits 1 with
one such line per project.

**The one shared resource is the subscription.** Both daemons run `claude -p`
as you, on the same Claude login, so every job of either project draws on the
same usage allowance; the usage limit belongs to the account, not to a project,
and each daemon meets it as its own `job.limited` and backs off by its own
`[limits]`. Nothing in hands divides the subscription between projects. What
meters it is each playbook's `auto_runs`: a daemon starts on its own only the
run numbers its project's `PLAYBOOK.toml` lists in `[limits] auto_runs`, and
stops for a human at any other, so what the laptop spends unattended is bounded
by the runs the two playbooks allow, taken together.

**Moving the flat spool.** Before §29 the spool sat directly under
`~/.hands/` (`jobs/`, `roles/`, `inbox.jsonl`, `inbox.acks.jsonl`,
`pipeline.json`). While any of those is there, `handsd` refuses to start: it
exits 1, names what it found and says to run the migration, and it creates and
binds nothing. Stop the old daemon, remove the retired `handsd.service` and
`handswho.service` units (and `~/.config/hands.env`), then run:

    hands migrate-spool

It moves those items to `~/.hands/hands/` and files a `spool.migrated` event in
that spool's inbox, naming what moved. It is refused, with nothing moved, while
a daemon answers on a `*.sock` directly under `~/.hands/` or on the
`server.socket` of any config there, and when `~/.hands/hands` already exists.
With nothing flat it says so and exits 0, so running it twice moves once. The
moved spool is the spool of the project called `hands`; if the flat spool was
another project's, rename that directory to the project's name before starting
its daemon.

## 3. Write the config (§14 step 1)

`~/.hands/<project>.toml`. Every key below is read by `src/hands/config.py`;
an unknown key or section is refused, and everything except `[roles.builder]
cwd` is optional.

    [server]
    socket = "~/.hands/<project>/handsd.sock"  # default (§29)

    [notify]                             # the two ntfy keys are also read from
    ntfy_topic = "hands-<something-random>"  # [server], where older configs have
    ntfy_url = "https://ntfy.sh"         # them (default); never in both places
    # cmd_topic = "hands-cmd-<another-random>"  # optional: the command channel,
    # cmd_secret = "<one long random word>"     # required with cmd_topic
    # who_topic = "hands-who-<random>"          # optional: the who view, and
    # who_cmd_topic = "hands-who-cmd-<random>"  # its commands; see "Optional:
    #                                           # notifications, the command
    #                                           # channel and the who view"

    [roles.builder]
    cwd = "~/git/<project>"              # required; the only required key
    model = "opus"                       # default
    permission_flags = "--dangerously-skip-permissions"
    resume_line = "Resume WORKPLAN.md"   # optional, no default: sent on a limit
                                         # resume (§6). Leave it out and a limit
                                         # resume re-sends the limited prompt
    queue_depth = 1                      # capacity: how many jobs may wait
    cancel_gated = true                  # default

    [roles.builder.env]                  # optional: added to handsd's environment
    CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS = "0"  # for this role's jobs. hands sets
                                         # this one to "0" unless you set it here

    [roles.aux]
    cwd = "~/git/<project>"
    queue_depth = 4                      # default for aux (builder 1); `hands
                                         # status` reports it as queue_capacity too

    [roles.driver]                       # optional (§27): the driver role
    cwd = "~/hands-driver/hands"         # the driver directory and its repo/ clone
                                         # (~/hands-driver/<project>; this is hands'
                                         # own); permission_flags must stay empty

    [roles.architect]                    # optional (§31): the architect role
    cwd = "~/hands-architect/hands"      # the architect directory, its repo/ clone
                                         # and its kits/; permission_flags must stay
                                         # empty, as for the driver

    [ops]
    repo = "~/<project>-ops"
    monitor_cmd = "watch_monitor.sh"     # both, or hands uses its built-in monitor

    [monitor]
    stall_minutes = 40                   # default

    [limits]
    backoff_minutes = 30                 # default
    max_resumes = 3                      # default; a playbook may override it

    [playbook]
    path = "PLAYBOOK.toml"               # default; relative to roles.builder.cwd

    [files]
    allowed_roots = ["~/git/<project>", "~/Downloads", "~/<project>-ops"]
    kit_dir = "~/Downloads"              # default: where a kit from the phone lands;
                                         # must be inside allowed_roots to be used
    kit_max_mb = 20                      # default: the largest kit fetched (MiB)

    [gates]
    patterns = ["...", "..."]            # added to the defaults, never replacing them

    [runner]
    claude = "claude"                    # default; an absolute path also works
    cancel_grace_s = 20                  # default: SIGINT, wait, SIGTERM (§2)
    pipe_timeout_s = 10                  # default: job end reads claude's pipes this
                                         # long after the sweep (§29)

    [who]                                # read by `hands who` and handswho only
    grace_s = 60                         # default: seconds after a job ends that its
                                         # transcript is still never shown by
                                         # directory (§29); a finite number >= 0
                                         # (`nan` and `inf` are refused, §30)

Notes that are easy to get wrong:

- `files.allowed_roots` defaults to exactly the role working directories.
  `hands put/get/ls` can reach nothing else, so `~/Downloads` must be listed
  if the plan kit lands there.
- `gates.patterns` is a **union** with the defaults (`Apply ~/Downloads/`,
  `decisions-`, `playbook-`, `gh pr create`, `open the PR`). A config can only
  widen the gate, never disable it (§8).
- `roles` are `builder`, `aux`, `driver` and `architect` (§31); `[roles.builder]` is required.
- **`[roles.driver]`** (§27) is optional and takes the same keys. Its cwd is the
  driver directory of section 5, with the fetch-only clone under `repo/`.
  `permission_flags` must be empty: a driver role with any value does not load,
  so `settings.json` and the Bash guard are the law. Every driver-role job's
  environment carries `HANDS_ROLE=driver`, on top of its `env` table and
  whatever that table says, which puts the guard in role mode. The driver role
  is started by handsd only through a playbook `consult` action: `hands send
  --role driver` is refused. `hands doctor` prints a `role driver` row with the
  cwd, the clone, the settings, the guard and its mode (§28). The row fails on
  a permission bypass, when the driver directory's `.claude/settings.json` does
  not name the hook (a `PreToolUse` command hook for `Bash` that runs
  `.claude/hooks/bash_guard.py`), and when that hook's `--selftest` is not green
  run with the role's environment (`HANDS_ROLE=driver`). The hook self-tested
  is the file the settings' command names (§29). The command must run it as
  the guard (§30): exactly `python3` and a path ending in
  `.claude/hooks/bash_guard.py`, with `$CLAUDE_PROJECT_DIR` and a relative path
  read against the driver directory, and nothing else: no further argument
  (`--selftest`), no other interpreter, no `;`, `&`, `|`, redirection, `$`
  other than `$CLAUDE_PROJECT_DIR`, glob, escape or newline. A named file that
  does not exist fails. Doctor
  judges every `PreToolUse` hook whose matcher selects `Bash`, not only the
  first, and fails if any one of them is not the guard — a second Bash hook
  beside the real one is a second answer to the same tool call. A `PreToolUse`
  entry for the write tools (the architect's `Write|Edit|MultiEdit` hook) is not a
  Bash hook; it is judged as the architect's write matcher is, below. A missing
  clone warns. Since §32 (review 15 should-fix 6) and §33 (review 16 should-fix
  4) the row reads both settings files Claude Code merges in the directory,
  `.claude/settings.json` and `.claude/settings.local.json` (the local one may be
  absent; unreadable, it fails), and fails when either sets `"disableAllHooks"`;
  when any hook anywhere under `PreToolUse` is not a command hook (`type:
  prompt`, say); when a matcher that could select `Bash` — or `Write`, `Edit`,
  `MultiEdit` — is not exactly `Bash` (or `Write|Edit|MultiEdit`), matchers read
  broadly: empty or `*`, an alternative equal to the tool's name in any case, or
  a regular expression that finds the name unanchored and case-insensitively
  (`bash`, `ulti.dit|as`, `.*`); when `permissions.defaultMode` is
  `"bypassPermissions"` or `"acceptEdits"`, or an `allow` entry names `Bash`,
  `Write`, `Edit` or `MultiEdit` bare or with a specifier holding no letter or
  digit (`Tool(*)`, `Write(**)`, `Edit(/**)`, `Bash(*:*)`); and when a push from
  the clone is not disabled. The push rule: `origin` exists; every remote `git
  -C <clone> remote` lists has push URLs (`git remote get-url --push --all
  <remote>`) that are each a plain word with no `/`, `\`, `:` or `@` naming
  nothing in the clone, as `no_push` is; and `remote.pushDefault`,
  `branch.<b>.pushRemote` and `branch.<b>.remote`, where set, name one of those
  remotes (or `.`). An unset push URL (git prints the fetch URL) and a clone git
  cannot read fail. The row ends with `verified:` lines: the settings files read
  (resolved), each guard hook's matcher, command and resolved file, every
  remote's push URLs with the push-remote settings, and the clone's realpath.
- **The consult flow** (§27, docs/PLAYBOOK.md "Consult"). A rule `then =
  "consult"` fires on an event, say a builder `VERDICT: question`. handsd starts
  a driver-role job in the driver's cwd, `context: clear`, `origin: playbook`,
  and files `consult.sent`. The job's environment carries `HANDS_CONSULT_ROLE`,
  the role the consultation is about, read from the prompt's first line (§28);
  the guard allows a send to that role only. It also carries `HANDS_CLONE`, the
  clone doctor's row names (absent when there is none), and the guard allows
  `git -C` on that path only (§29). The prompt carries the event, the job's id, role,
  state and verdict, and its `result` verbatim. The driver answers within its
  authority with `hands send --role builder --context keep` (the one send role
  mode allows) and replies `VERDICT: resolved <what was sent, and the section
  cited>`, or replies `VERDICT: escalate <reason>`. When the driver job ends,
  handsd files `consult.done` with its terminal state and verdict and appends
  one line to `meta/journal.md` under `roles.builder.cwd` (working tree only),
  whether the job ended done, failed, killed (a cancel, or a job that could not
  be spawned), orphaned or limited. The end is an event:
  `driver.done|failed|killed|orphaned|limited`. The engine stops and notifies
  for every one of them except a `driver.done` whose verdict is `VERDICT:
  resolved …`, whatever `driver.*` rules the playbook has (§28); a resolved
  verdict goes to the playbook's rules. Over a paused pipeline that stop is
  filed as `pipeline.stop_suppressed` with the consult reason and still
  notifies (§29). A limited driver job is not resumed.
  A consult with no `[roles.driver]`, or beyond `[limits] max_consults`
  (default 2), stops and starts no driver job. The count starts at the later
  of the last builder job whose prompt equals any `[series] kickoff` value the
  pipeline has loaded (kept in `pipeline.json`), the last kit apply that ran,
  and a daemon start (§29): the first daemon start that finds none recorded is
  kept in `pipeline.json` as `consults_since`, and a later restart does not
  move it, so a restart mid-mission keeps the count (§30).
  `hands pipeline` shows `consults <used> of max_consults <n>`.
- **`[roles.<role>] env`** (§23, H-014) is a table of environment variables for
  that role's `claude -p` jobs, on top of handsd's own environment. Names are
  environment variable names (letters, digits, `_`); values are non-empty
  strings. Every role job gets `CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0` unless
  this table sets that name — even when handsd's own environment carries another
  value. With Claude Code's default ceiling (600 s), a `claude -p` whose turn
  ended while a sub-agent it started was still running is terminated and exits 0.
  `hands doctor` prints the effective value on each role's row.
- **How a job ends** (§6, §23). A job is `failed` when the process ends without
  a final `result` event, with a `result` of subtype `error` (claude's `error_*`
  family, `error_max_turns` included, whatever its `is_error` says), without
  `num_turns`, when it exits non-zero without a limit, when it could not be
  spawned, or when stderr carries the harness's "Background tasks still running
  after …; terminating. Set CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=…" line. A job
  that finished and is none of those is `done`: claude exited 0 with a final
  `result` of subtype `success` carrying `num_turns`, and the line never
  appeared. The record's `failure_reason` says why a job failed, one value each:
  `harness_terminated`, `no_final_result`, `error_result`, `nonzero_exit`,
  `no_num_turns`, `spawn_error` — the first that holds, in that order;
  `stderr_tail` has the evidence. `failure_reason` is null for every other
  state. Precedence: a cancel stays `killed` and a detected limit stays
  `limited`, terminating line or not (§6's limit resume waits out the reset, and
  a `builder.failed → resume` would not); a job both cancelled and over a limit
  is `killed`: `killed` wins over `limited`; otherwise the terminating line wins
  even over a `success` result, because the harness ended the session mid-turn
  and the result is whatever the model had said last (H-014). Only the line's
  exact shape counts: from the line start, case-sensitive.
- **Who decided a gate** (§6, §8, §31). A decided job's `gate.decided_by` is one
  of `cli` (`hands approve|deny` at the laptop), `driver` (`--human-confirmed`
  with the human's quote), `phone` (the ntfy command channel, below) or
  `playbook` — the engine releasing a held apply hands filed from a kit the
  architect role filed (a `kit_id` handsd minted, §32) under a playbook that
  sets `[series] architect = "role"` and `autonomous = true`, whose gate reason
  names the standing approval it acted on (§31; §6's record line lists the
  first three, finding H-031).
- **An empty string is refused at load, for every optional key** (§20): `""` or
  blanks only is neither the key's absent meaning nor a usable value — an empty
  `ops.monitor_cmd` would have made the *ops directory* the monitor script. The
  error names both valid choices: omit the key, or give it a real value. The one
  exception is `permission_flags`, whose `""` is its default and means "no
  flags".
- **`ops.monitor_cmd` names a script inside `ops.repo`** (§21): a relative path
  with no `..`, and the file it names has to be an executable regular file that
  exists when the config loads *and resolves inside the repo* — a symlink out of
  it, or a traversal through a symlinked directory, is refused by where it lands
  rather than accepted by how it is spelled. `"."` used to load and make the ops
  *directory* the monitor script, which then failed silently and left builder
  jobs unwatched; it is a load error now, naming the path it looked for.

## 4. `hands doctor` (§14 step 1)

    hands --project <project> doctor

It checks, all for free: the config, the `claude` binary and its `--version`,
each role's `cwd` (and whether it is a git repository), the allowed roots, the
ops script's flags, which per-job isolation is in force, the playbook, whether
notifications, the command channel, `go`, the kit transport and the who view
are on, and whether handsd is answering. A daemon
that is not running is a **warning**, not a failure — this step comes before
you have to have started one. Exit code 1 means a check failed.

A config that will not load at all is reported the same way, not as a crash:
doctor prints its usual report with a failed `config` row carrying the error
(`--json` included) and exits 1. It is the one command that does this — every
other command prints the message alone and exits 1, or 2 when the client
refused before it delivered the request (see "Exit codes" below).

    hands doctor --live       # also runs ONE real `claude -p` turn per role

`--live` is the only thing in hands that spends your subscription, so it is
opt-in, and `HANDS_DOCTOR_FAKE=1` refuses it (that is how the test suite runs
doctor without a real binary). `hands doctor --json` prints the same report as
data.

Doctor checks that a topic is *configured*; it never sends anything. The proof
of delivery is one command, and it needs no daemon either:

    hands notify --test "ping from the laptop"
    hands notify --test                   # the same, with a default line

It publishes one message to `ntfy_topic` through the same transport
§11's `stop` and `job.held` notifications use, and prints the HTTP status ntfy
answered with — **whatever that status was**:

    ntfy 200  https://ntfy.sh/hands-<random>
    ntfy 403  https://ntfy.sh/hands-<random>     # printed too, and exits 1

A 2xx exits 0; any other code is printed with the same `ntfy <code> <url>` line
and exits 1, because the message did not reach the topic. With no `ntfy_topic`
set, or when nothing answered at all (no route, timeout, TLS), there is no code
to print and it says so on stderr and exits 1.

Doctor also prints the **notification check** of §11 — the one check hands
cannot run itself, because it ends on your phone. Run it by hand after step 5;
the procedure is in doctor's own output. It is the check that matters now that
the driver arms no wait of its own (§11, §22): ntfy is your doorbell, and your
message `check` is the driver's.

## Optional: notifications, the command channel and the who view

Three uses of ntfy, each on its own random topic in `[notify]` (DESIGN §11,
§24). ntfy is never shipped with hands, only spoken to: hands publishes to
`ntfy_url` (ntfy.sh by default, or your own server), and handsd and `handswho`
read their command topics by outbound long polls, so nothing listens on this
machine. All three are off unless configured, and hands runs without any of
them:

| what | on when | who reads the topic |
|---|---|---|
| notifications | `ntfy_topic` is set | your phone: `stop`, a held job, an exhausted `max_resumes`, daemon start/crash (§11) |
| the command channel | `cmd_topic` is set (and `cmd_secret`, which it requires) | handsd |
| the who view | `who_topic` is set | your phone; `handswho` publishes it |

`hands doctor` reports each of the three as on or off, never as a failure: its
`notifications`, `phone` and `who` rows. Its `go` and `kit transport` rows
(§26) are on/off the same way: `go` is on when the command channel is on and
the playbook in force loads with a `[series] kickoff`, which the row prints —
and it warns, still green, when that kickoff plainly names a file the builder's
cwd does not have, because a phone `go` would then send the builder to a brief
that is not there; `kit transport` is on when the command channel is on and
`[files] kit_dir` is inside `allowed_roots`, and it prints `kit_dir` and
`kit_max_mb`. Off, each
names what is missing. It prints no topic and no secret. The
`config` row also warns when `ntfy_topic` is missing, since you then learn you
are needed only by looking; and a config that does not load (a `cmd_topic`
without a `cmd_secret`, below) is the failed `config` row, as always.

### Notifications

Set `ntfy_topic` and subscribe your phone to it. `hands notify --test` proves
the transport, and the notification check doctor prints proves an event you did
not ask for arrives (step 4 above).

Notifications of one cause are published 1.1 s apart: a kit receipt, then the
held apply it files, then — for a kit with no `KIT.md` — the answer naming the
default commit message. ntfy stamps a
message with per-second timestamps, so two published inside the same second
would sort arbitrarily on the phone, and the second one reads as the answer to
the first. Nothing else waits: an unrelated notification is never delayed (§11),
and no notification queues behind another.

A daemon start publishes exactly one notification, `hands: handsd started`
(§32). The jobs still held are listed in it, and anything the start itself
raises before it — the stop an orphaned consultation's end makes, when a daemon
died with a driver or architect job running — is folded into its message, title
and reason, rather than published a few milliseconds ahead of it. When the start
picks up jobs a dead daemon left queued, the notification waits for them to end,
for at most 5 seconds (DESIGN §33): a queued job that fails at once stops the
pipeline inside that window, and the stop is folded in rather than published a
quarter second after the start. The same window is the bound on everything else:
any notification raised in it — a job held by a `hands send` in those seconds
included — is named inside the start notification, without buttons, and none
waits longer than 5 seconds. A queued job still running when the window closes
does not hold the start notification; what its end raises later is published on
its own.

A limit and its resume are not such a pair. Both are events you read with
`hands inbox` (`limit`, `resume`), and neither is published: the inbox event
kinds hands publishes by itself are `stop` and `job.held`. A limit reaches your phone only when the playbook in
force has a `notify` rule on `builder.limited` or `driver.limited`, and no
playbook hands ships has one; the resume reaches it by no route at all, because
there is no `resume` event a rule can name. What the 1.1 s does here is not a
published pair — it orders the scheduler: a resume is never scheduled sooner
than 1.1 s after the limit that caused it, so a limit notification you did add
is stamped before anything the resumed job goes on to publish. An exhausted
`max_resumes` is a `stop`, and every `stop` is published (§11).

### The command channel: approve from the phone

With `[notify] cmd_topic` set, handsd subscribes to that topic — an outbound
long poll to ntfy, nothing listening on this machine — and takes eight commands
from it. Set it up once:

    python3 -c 'import secrets; print("hands-cmd-" + secrets.token_urlsafe(16))'
    python3 -c 'import secrets; print(secrets.token_urlsafe(32))'

The first line is a topic name, the second the secret. Put both in the config
beside the events topic, which must be a different topic:

    [notify]
    ntfy_topic = "hands-<something-random>"
    cmd_topic = "hands-cmd-<the first line>"
    cmd_secret = "<the second line>"

Restart handsd (`systemctl --user restart handsd@<project>`). A `cmd_topic` without a
`cmd_secret` does not load: doctor fails its `config` row, and handsd refuses
to start. So does a secret with a blank inside it, and a `cmd_topic` equal to
`ntfy_topic`.

Publish a command to `cmd_topic` from the ntfy app. The last word is the token
(but for `reply`, whose second word is the secret):

    approve <job> <secret>
    deny <job> [reason words] <secret>
    pause <secret>
    resume <secret>
    status <secret>
    go <secret>
    kit <secret>                  (with a .zip attached to the message)
    reply <secret> <text>

- `approve` and `deny` decide a **held** job, exactly as `hands approve|deny`
  does, and the job record says `decided_by: phone`. `pause` and `resume` are
  `hands pause` and `hands resume` (`hands pipeline` shows `paused yes
  (phone)`). `status` answers on `ntfy_topic` with a few lines: each role,
  the held job ids, whether the pipeline is paused, the unread inbox count.
- `go` is the only way to start work from the phone (DESIGN §26). It sends the
  playbook's `[series] kickoff` line (docs/PLAYBOOK.md) to the builder as a
  `clear` send, the job record says `origin: phone`, and `hands jobs --origin
  phone` lists those jobs. (The apply a kit files is `origin: kit`, and `hands
  jobs --origin kit` lists those; both origins, like `cli`, un-pause a stopped
  pipeline when their job starts.) The send takes the same path as `hands send`, so the
  gate patterns still apply. handsd answers on `ntfy_topic` with the job id and
  its state. It is refused, and logged, while the builder has a job running or
  queued, when there is no playbook (or it cannot be loaded), and when the
  playbook has no `[series] kickoff`. A stopped pipeline still has its playbook:
  `go` is accepted, and its job un-pauses the pipeline when it starts, as a
  `cli` send's does, so the builder's `done` fires its rule.
- `kit` moves a kit from the phone to this machine (DESIGN §26). Publish the
  message `kit <secret>` to `cmd_topic` with the `.zip` attached, from the ntfy
  app or with curl (the body is the file, so the command goes in the `Message`
  header):

      curl -T mission-11.zip -H "Filename: mission-11.zip" \
           -H "Message: kit <secret>" https://ntfy.sh/<cmd_topic>

  handsd reads the attachment's `name`, `size` and `url` from the message, and
  refuses (and logs) the kit before fetching anything when there is no
  attachment, when the name is not a plain `.zip` file name (no `/` or `\`, no
  leading dot, ending in lowercase `.zip`), when the size ntfy reports is
  missing or over `[files] kit_max_mb` (MiB, default 20), when the URL is not
  http(s) or is malformed (httpx cannot parse it, or it has no host), or when
  `[files] kit_dir` (default `~/Downloads`) is not inside `[files]
  allowed_roots` — the default roots are only the role directories, so list
  `~/Downloads` there. Each refusal of a kit whose secret was right, before or
  during the download, is also filed in the inbox as `kit.refused` with the
  check that refused it, never the attachment's name or URL (DESIGN §27). The
  download stops as soon as it passes the cap, and is refused unless it ends at
  the reported size. The file is written under its own name in `kit_dir`; if
  that name exists it becomes `<stem>-1.zip`, `<stem>-2.zip`, … (`kit.zip` →
  `kit-1.zip`), and an existing
  file is never overwritten. It is never unzipped, never run, never made
  executable. handsd files `kit.received` in the inbox (the name written, bytes,
  sha256) and answers on `ntfy_topic` with `kit received <name> <bytes>
  <sha256>`. handsd then files the apply itself, held for your approval (DESIGN
  §27; the closed loop below says how). An ntfy server has its own attachment size limit, which
  may be lower than `kit_max_mb`.
- `reply` talks to the architect role (DESIGN §33; "The architect role" below).
  `reply <secret> <text>` is delivered as `hands send --role architect --context
  keep` would be — the one send to the architect, which `hands send` itself
  refuses (§32) — to the architect's last session: one job, `origin: phone`,
  whose prompt is `<text>` exactly as typed after the whitespace that follows the
  secret (inner and trailing whitespace and newlines kept). handsd answers on
  `ntfy_topic` titled `hands: reply` with the job id and state, and when the job
  ends it publishes the architect's final message there titled `architect`. It
  is refused, and the refusal answered under `hands: reply`, when the config has
  no `[roles.architect]`, while an architect job is running, queued or held (a
  consultation, or the last reply: one job per turn), while the engine waits for
  a consultation's `next kit`, and when the architect has no session yet. A reply
  is not a consultation: the engine reads no verdict from it, it does not
  un-pause a stopped pipeline, it does not count against
  `max_architect_consults`, and a `hands kit file` while it runs is refused. The
  text goes over ntfy: see "Old messages" and the privacy note below.
- **The buttons.** With the channel on, a held job's notification has Approve
  and Deny buttons. Each publishes `approve <job> <nonce>` or `deny <job>
  <nonce>` to `cmd_topic`. The nonce is 32 random bytes minted for that one job
  and kept only in handsd's memory. It can decide only that job, and only once.
  It is gone as soon as the job is decided by any route (phone, `hands
  approve`, the driver) and when handsd restarts. After a restart the old
  buttons do nothing, and handsd does not re-send them: its one `handsd started`
  notification lists every job still held, and a summary of several jobs can
  carry the buttons of none. Decide those with `hands approve <job>` / `hands
  deny <job>`, or with `approve <job> <secret>` on `cmd_topic`; a job held again
  later gets buttons again. `pause`, `resume`,
  `status` and `go` take the secret only, never a nonce.
- **Nothing is answered except `status`, an accepted `go`, a written kit and a
  `reply` whose secret was right.** A wrong secret or nonce, a command
  hands does not know, or a job that is not held is logged in handsd's journal
  (`journalctl --user -u handsd@<project>`) and ignored. If a command seems to do
  nothing, look there. The log never contains the token.
- **Old messages are not replayed.** handsd acts only on messages sent after
  it subscribed, judged by the time ntfy stamps on each message against this
  machine's clock. After a dropped connection it resumes after the last
  message it read, without acting on a message twice.
- **The long-term secret never goes into a notification**, but a typed
  command carries it on `cmd_topic`. An ntfy topic is only as private as its
  name (or the access control of a self-hosted server): anyone who can read
  `cmd_topic` can read your secret. Anyone who can read `ntfy_topic` sees a held job's buttons,
  and they can use them while that job is held. Keep both names random and to
  yourself.

### The closed loop, from the phone

DESIGN §26 and §27: one mission, from kit to stop, without the laptop's
keyboard. The loop is phone only: kit, buttons, `go`, buzz. It needs the
command channel, `ntfy_topic`, a playbook with `[series] kickoff`, and `[files]
kit_dir` inside `allowed_roots`. `hands doctor` shows the `go` and `kit transport` rows as on
when all of that holds, and says what is missing when it does not.

1. **The architect emits a kit** and checks it first, in its own sandbox or at
   the laptop:

       hands kit check mission-11.zip --repo ~/git/<project>

   It prints one PASS/FAIL line per check and, only when every check passes,
   `apply prompt:` followed by the prompt, which begins `Apply
   ~/Downloads/<kit>.zip to this repository:` and asks for the reply `VERDICT:
   kit applied <sha>`, then the commit message and a `KIT.md:` line. The commit
   message is the first line of `KIT.md` at the kit's root when it is
   not empty, at most 72 characters, and has no quote character or line break,
   else `plan: kit <name>` (`<name>` is the zip's file name without `.zip`);
   the prompt shell-quotes it, and the kit's file name (DESIGN §29; `a b.zip`
   is written `~/Downloads/'a b.zip'`). That prompt is the
   one handsd files in step 2, byte for byte, when the kit is written under the
   same name in `~/Downloads` (the default `kit_dir`).
2. **Send the kit to `cmd_topic`** from the ntfy app, the `.zip` attached and
   the message `kit <secret>`. handsd fetches it into `kit_dir`, and the phone
   buzzes with `kit received <name> <bytes> <sha256>` (title `hands: kit
   received`). `<name>` is the name written: if the file already existed it
   is `<stem>-1.zip`, and the apply names that file. handsd files the apply
   itself: it lists the zip's entries against the builder's cwd (handsd never
   unzips the kit; the builder does), builds the prompt of step 1 (it begins
   `Apply ~/Downloads/` with the default `kit_dir`), and files it as a `clear`
   builder job with `origin: kit` and gate reason `apply <name>`. When the
   message is the default, the phone also gets `apply <name>: <why>; the
   commit message is the default '<message>'`. An attachment URL that is not
   http(s), has no host, has a host that is neither an IP literal nor a name
   `idna.encode` accepts (DESIGN §29), has a port outside
   1-65535, or holds whitespace is refused before any fetch, as `kit.refused`
   naming the check.
   The job is held, not run. A zip that cannot be read, holds no files, or has
   an entry that is not a repository path (absolute, `..`, under `.git` or
   `.claude`, a duplicate, over the size caps, landing outside the repo or
   inside `.git` or `.claude` through a symlink, or whose local-header name or
   Unicode Path extra field names another file than the central directory's,
   the name `unzip` extracts — DESIGN §33) files no job: the inbox gets `kit.refused` ("the apply was not
   filed: …", the kinds of problem, never an entry's name), and the kit stays
   in `kit_dir`, so `hands kit check` on it names the entry. A builder that is
   busy does not refuse the apply; it waits, held, for your decision.
3. **Approve it from the phone.** The held job's notification (`hands: a job is
   held for a human`, reason `apply <name>`) carries Approve and Deny buttons.
   Approve publishes `approve <job> <nonce>`; the typed `approve <job> <secret>`
   does the same. If the playbook has no `job.held` rule, the hold also stopped
   the pipeline (`hands: the pipeline stopped`); the approved job un-pauses it
   when it starts (`origin: kit`, like `cli` and `phone`). The builder unzips
   the kit, commits it and replies `VERDICT: kit applied <sha>`; this
   repository's `PLAYBOOK.toml` and the missions template notify on it
   (`hands: Kit applied; the next kickoff is the driver's`), and the kickoff
   can come from the phone instead, in the next step.
4. **Send `go <secret>`** to `cmd_topic`. handsd reads the committed playbook,
   sends its `[series] kickoff` line to the builder (`clear`, `origin:
   phone`), and answers `go: builder job <id> <state>` (title `hands: go`). It
   is refused, and only logged, while a builder job is running, queued or
   held — the apply of step 3, if you have not approved it yet, is such a job,
   and the refusal names it.
5. **Wait for the buzz.** The playbook chains the builder's verdict to the
   review and on to a stop. Every stop reaches the phone as `hands: the
   pipeline stopped` with the reason, which is the rule's message. Paste it to
   the architect, and the loop starts again at step 1.

Throughout, the driver is the inspector: it reads `hands inbox`, `hands show`
and the fetched branch in its clone when you ask it to `check`, and reports.
It is never required for the loop.

Not proven, and not built:

- No kit has been fetched from a real ntfy attachment. The tests serve the
  attachment from a local HTTP server; the ntfy app's attach and ntfy's own
  attachment size limit are untested. While a kit downloads (up to 300 s) the
  channel reads no other command.
- No `go` has been sent from a real phone, and no Approve button has been
  pressed on one; the tests feed a fake ntfy stream.
- No apply has been filed from a kit sent by a real phone, and none has been
  applied by a real builder: the tests check the held job, its prompt against
  `hands kit check`'s, and its approval with `tests/fake_claude.py`, which does
  not unzip anything. handsd decompresses only `KIT.md`, so a corrupt other
  entry is found by the builder's unzip.
- `hands who` matches an interactive session to its transcript through
  `~/.claude/sessions/<pid>.json`, whose `sessionId` names the transcript (§27,
  FINDINGS H-020). That file is Claude Code's and undocumented; its shape was
  read on one machine and one Claude Code version. With no such file for a pid
  the line says `transcript: by directory`, and a transcript whose session id a
  hands job record holds, or a running hands job's own sessions file names
  (§28), is never shown under it. With handsd down, no running job's pid is
  known, so only the job records exclude. For `[who] grace_s` (default 60)
  after a job ends whose record never got a session id, a transcript of its
  role's directory whose first `timestamp` falls between the record's `started`
  and `ended` is excluded too (§29): that is how the ended job's transcript is
  recognised, because H-020 found sessions files only for live processes, so an
  ended job's pid may have none.
  So a transcript with no `timestamp` in its first 20 lines is not excluded by
  the grace, and a session of yours that has no sessions file and began in that
  directory while the job ran is hidden from its own line until the grace
  passes. After the grace such a transcript can be shown by directory again.
- `hands kit check` checks the builder's verdict rules only; review verdicts
  have no literal in the brief to match (FINDINGS H-021).

### The who view

    hands who                             # the picture, printed once

One screen: this daemon's roles, jobs, held gates, pipeline and unread inbox
(asked of handsd over its socket), every other `claude` process on the machine
(from /proc, with the commands running under it), and whether each interactive
session is waiting for you or working (from its transcript under
`~/.claude/projects/`, the one `~/.claude/sessions/<pid>.json` names by
`sessionId`; only `pid` and `sessionId` are read, and the `.key` file beside it
never is). A session with no sessions file says `transcript: by directory`: its
state is then read from the newest transcript of its directory that is not a
hands job's, nor one begun during a job that ended less than `[who] grace_s`
seconds ago (default 60, §29). Your own session in a role directory is labelled
`(your session)`; a session under `~/hands-driver/<project>/` is
`driver:<project>`. With handsd down it still prints the rest, says the daemon
is not answering, and exits 0.

To have it pushed to your phone, add two more random topics:

    [notify]
    who_topic = "hands-who-<something-random>"
    who_cmd_topic = "hands-who-cmd-<something-random>"   # optional

and run `handswho --project <project>` (the same as `hands who --daemon`).
`systemd/handswho@.service` is an optional user unit, off unless you enable it;
install it the way its header says, as `handswho@<project>`. `handswho` pushes the picture to
`who_topic` when what is running, held or waiting changes (a session's state
must hold for two scans first; your own
sessions never trigger a push), and whenever `status`, `who`, `check` or `?` is
published to `who_cmd_topic`. Those words take no secret, because they execute
nothing: the only answer is the same picture. The picture does carry the first
line of each running job's prompt and of the commands under each session, so
keep `who_topic` as private as `ntfy_topic`. Without `who_topic`, `handswho`
exits 1 and names the key.

## 5. The driver session (§14 step 2)

`driver/README.md` is the full recipe. In short:

    mkdir -p ~/hands-driver/<project> && cd ~/hands-driver/<project>
    cp ~/git/hands/driver/CLAUDE.md ./CLAUDE.md
    mkdir -p .claude/hooks
    cp ~/git/hands/driver/settings.json .claude/settings.json
    cp ~/git/hands/driver/hooks/bash_guard.py .claude/hooks/
    python3 .claude/hooks/bash_guard.py --selftest
    git clone <repo-url> repo
    git -C repo remote set-url --push origin no_push
    claude          # then /rc to enable remote control

Fill in the parameter block at the top of `CLAUDE.md`. The driver never
writes: the deny-list, the Bash guard hook and the push-disabled clone are
three separate layers, and none of them is prose (§12).

**The guard's language (§30, §32).** The driver's shell is one line of words,
quotes and separators, and the Bash guard judges nothing else. Before any
tokenizing it refuses, in every mode and in any position, quoted or not: a
newline, a carriage return or any other control character, `<`, `>`, `#`, a
backtick, `\`, `$`, `{` and `}`; a `!` inside double quotes; and every reserved
word of the shell appearing as a word — `for while until if then else elif fi
do done case esac select function in time coproc ! [[ ]]` — a word being what
bash splits outside quotes, on spaces and `; & | ( )`, so a quoted `'done'` is
text. The refusal names the first offender and its position (a reserved word by
name and position), and an unbalanced quote is refused at the position where it
opened. What remains is words, `'…'` and `"…"` quotes, which `shlex` reads one
way only, and the separators `;`, `&&`, `||`, `|` and `&` (parentheses only
split): no expansion, no control flow, no redirection, no comment, no heredoc
and no escape. Each segment is judged by the command table, and every word
after its command word must be a plain word — no unquoted `*`, `?`, `[`, `!`,
or `~` after `=` or `:` — because the shell would expand it after the guard
read it. The table (§12, §31): `hands`, every subcommand but `open`; read-only
`git`, with only `-C <path>` and `--no-pager` before the subcommand and after it
only `log --oneline -n --grep --format --stat --name-status`, `show --stat
--name-status`, `fetch -q`, `ls-remote --heads --tags`, `rev-parse --verify
--short`, `diff --stat --name-status --name-only`, `grep -n -c -l -i -e`,
`cat-file -t -p -e`, `ls-files`, `ls-tree`, `branch --list`, `remote -v` and
`status`; `cat` (no options), `ls` (`-l -a -la -1`), `head` and `tail` (`-n
<int>`), `wc` (`-l -c -w`), `grep` (`-n -c -i -l -E -F -r -e <pattern>`), `jq`
(`-r -c -e` and a `.` filter), `pgrep` (`-f -a -l`), `sleep <int>`, `date
[+FORMAT]`, `echo` (no options) and `kill -0 <pid>`. Any other option (`wc
--files0-from=`, `grep -f`, `date --set`, `tail -f`, which is `hands log -f`'s
alone) and any other word (`sort`, `uniq`, `cut`, `tr`, `find`, `stat`, `diff`,
`printf`, `basename`, `dirname`, `realpath`, `tty`, `id`, `whoami`, `uptime`,
`which`, `test`, `[`, `seq`, `true`, `false`, `pwd`) is refused by name. Driver
role mode (`HANDS_ROLE=driver`) is that table minus the `hands` subcommands §27
withholds — only `hands show|jobs|inbox|pipeline|status|tail|kit check|resume`
and `hands send --context keep` to `$HANDS_CONSULT_ROLE` — and its `git` takes
one `-C`, whose realpath must equal `HANDS_CLONE`'s (a second `-C` is refused,
because git applies each `-C` relative to the one before). Architect mode
(`HANDS_ROLE=architect`) is the same read-only table with `hands
show|jobs|inbox|pipeline|status|kit check|kit file`, plus `mkdir -p`, `cp -r`
and `mv` (no other option) with every path under `HANDS_KITS`, `cp` and `mv`
refused while anything under `HANDS_KITS` is a symlink, and every `mkdir`, `cp`,
`mv` and write refused when `HANDS_KITS` itself is one (§33); `zip` and `unzip`
are in no mode's table (§32). In both
role modes reads are confined to the clone and the spool: every path that
`cat`, `ls` (`.` when it names none), `head`, `tail`, `wc`, `grep` (`.` under
`-r` when it names none), `jq`, `git` (its words after the subcommand, from the
`-C` value) and `hands` (`--prompt-file`, `--socket`, `--repo`, a kit) read must
resolve by realpath under `HANDS_CLONE`, under the spool `~/.hands/<project>/`
(the project `$HANDS_PROJECT` names, else the only `~/.hands/*.toml`) or, for
the architect, under `HANDS_KITS`; with none of them named every path read is
refused, a read of stdin through a pipe is allowed, and a role's `jq` filter may
not name `env`. The human's session reads anywhere. Text that needs a refused
character travels as a file, with `hands send --prompt-file`.

## 6. The architect (§14 step 3)

Replace the Claude Project's instruction with `docs/ARCHITECT-INSTRUCTION.md`.
Its outputs are files for the repo; it never sends prompts to paste. That is
the **phone architect** — a person in a chat Project, and what a playbook means
when it says nothing (`[series] architect = "phone"`).

### The architect role (§31)

The same architect, headless: a fourth role handsd starts for **one
consultation** on a review outcome, with no memory of earlier ones — the branch
carries all of it. It reads the review and `meta/ROADMAP.md`, writes the next
kit, checks it, files it with `hands kit file`, and replies with one verdict
line. `architect/README.md` is the full recipe; in short:

    mkdir -p ~/hands-architect/<project>/kits && cd ~/hands-architect/<project>   # a kit is kits/<name>/<repository paths>, filed with hands kit file kits/<name>
    cp ~/git/hands/architect/CLAUDE.md ./CLAUDE.md        # fill the Parameters block
    mkdir -p .claude/hooks
    cp ~/git/hands/architect/settings.json .claude/settings.json
    cp ~/git/hands/driver/hooks/bash_guard.py .claude/hooks/bash_guard.py
    HANDS_ROLE=architect HANDS_KITS=$PWD/kits python3 .claude/hooks/bash_guard.py --selftest
    git clone <repo url> repo && git -C repo remote set-url --push origin no_push
    claude          # once, interactively: accept the trust dialog, then /exit

and the config gains one table:

    [roles.architect]
    cwd = "~/hands-architect/<project>"     # permission_flags stays empty

Every architect-role job's environment carries `HANDS_ROLE=architect` (the
guard's architect mode), `HANDS_CLONE` — the fetch-only clone under `repo/`,
the only path `git -C` may name — and `HANDS_KITS`, `<cwd>/kits`, the one
directory the role may write to. `permission_flags` must be empty, as for the
driver: a `[roles.architect]` carrying one does not load, so `settings.json`
and the hook are the law. handsd starts the role through a playbook `consult`
action and nothing else does: no playbook `send` can name it (a send's role is
`builder` or `aux`), and neither the phone's `go` nor its buttons reach it. A
`hands send --role architect` is refused as `--role driver` is (finding H-032,
§32): the refusal names §32 and the command exits non-zero.

Architect mode is the driver's read-only table plus `hands kit check` and
`hands kit file`, and `mkdir -p`, `cp -r` and `mv` only with every path
argument under `HANDS_KITS` and no other option (none that names another path,
such as `cp -t` or `--backup`, and none that makes a link). Realpath containment
judges where a path resolves when the command is judged, not where `cp` or `mv`
writes once it has moved a link (review 16 should-fix 2: `cp -r kits/a/h kits/`
moved a relative link planted inside `kits/` so it pointed out, and `cp
kits/pay/h kits/` wrote through it over the guard), so `cp` and `mv` are refused
while anything under `HANDS_KITS` — walked, links not followed — is a symlink;
the architect cannot make one, and `mkdir` still runs. A `HANDS_KITS` that is
itself a symlink (its realpath is not its parent's realpath joined to its name)
refuses every `mkdir`, `cp`, `mv` and every write (§33, review 16 should-fix 3:
`kits -> .claude` let the write matcher pass the role's own settings). `zip` and `unzip`
are refused by name in every mode (§32, review 15 blocker 2: an `unzip`
extracted into the role's cwd, the parent of `HANDS_KITS`, over the guard and
its settings). It never sends, approves, denies, `go`es, puts or pushes. Writes
are judged by a **second** `PreToolUse` matcher —
`Write|Edit|MultiEdit` running the same guard with `--write` — which allows a
write only under `HANDS_KITS`; the driver has no equivalent, because the driver
writes nothing at all.

`hands doctor` prints a `role architect` row beside the `role driver` one: the
cwd, the clone, the kits directory, the settings, the write matcher, the
guard's self-test run in architect mode, the mode itself, and the `verified:`
lines the driver row prints plus the kits realpath. It fails on a
permission bypass (`permission_flags`, or the driver row's settings rules, above,
over both settings files), on settings whose `Bash` hook or whose
`Write|Edit|MultiEdit` hook is not the guard (the write hook must be exactly
`python3 <path to .claude/hooks/bash_guard.py> --write` under exactly that
matcher, all three tools must be judged, every hook under `PreToolUse` must be a
command hook, and both matchers must run the same guard file), on a guard whose
`--selftest` is not
green run with `HANDS_ROLE=architect` and `HANDS_KITS` set, on a clone whose
push is not disabled (the driver row's rule, above), on a kits
directory that is missing or does not resolve under the architect's cwd
(§32), and (§33) on a kits directory that is a symlink or holds one, or when
`.claude`, its hooks directory, either settings file, either guard file or the
clone resolves under the kits directory; a missing clone warns.

**Directory kits (finding H-030, resolved by DESIGN v3.15 §32; code: mission 16
U2).** Under §31 the architect's `zip` could store entries only under
`kits/<kit>/…`, never at repository paths. Now the architect stages a directory
`kits/<name>/<repository paths>` (the Write tool creates the files; `mkdir -p`,
`cp -r` and `mv` arrange them) and files it with `hands kit file <dir>` —
`hands kit file kits/<name>`. The command builds the zip itself, each entry at
its path relative to the directory (`kits/m16/meta/X.md` is `meta/X.md`);
dotfiles are entries like any other, an empty directory carries nothing, and a
symlink anywhere inside refuses the kit. It refuses a zip, a file, the kits
directory itself, a path outside `HANDS_KITS` by realpath, and an unset
`HANDS_KITS`. It checks the built zip against the role's clone (`HANDS_CLONE`)
and refuses a failing kit with the check's output; a passing kit goes to
handsd, which stores the zip at `~/.hands/<project>/kits/<kit_id>/<name>.zip`
(outside `HANDS_KITS`, so nothing the architect may write can change it after
the check), runs `hands kit check` itself on those stored bytes against the
builder's repository and refuses a failing kit with the check's output (DESIGN
§33: the client's check is not trusted, because any socket client can call
`kit_file`), mints the `kit_id`, records it and the passing check, and files the held apply
the phone's `kit` files, `origin: architect`, whose prompt names that zip. The
phone's `kit` apply records a `kit_id` handsd mints too. What the tests prove is
that command against a real daemon socket with the fake `claude`; a real
architect session filing a kit that a builder then applies **is not proven**;
the engine's approval of such a kit is described below (§32, mission 16 U3), and
the config check below is mission 16 U4. Until a review finds them closed, run `[series]
architect = "role"` as an experiment, not as the way a series is driven.

**The switch point.** The role takes over from the phone architect at the fully
reviewed work plan. `architect/README.md` lists the deliverables that must be on
the branch before the switch: `DESIGN.md`, `meta/ROADMAP.md` with a checkable
gate per milestone, the first brief or run plan and the sequence of the rest,
`PLAYBOOK.toml` with `[series] architect = "role"`, `autonomous`, the escalation
conditions and the `consult` rule, and this directory. Applying that playbook (a
gated job the human approves) is the switch. To hand the series back to the
phone: `hands pause`, then the phone architect continues from the branch, and
the next kit sets `architect = "phone"`. One architect at a time.

**`[series] architect` and `autonomous`.** `architect = "role"` says which
architect this series has; `autonomous = true` says the engine may release what
that architect files. With both set, the engine approves a held job itself
(`decided_by: playbook`, the fourth value the gate record carries) only when it
is an apply hands filed from a kit the architect role filed (§32): the builder
apply `hands kit file` files, whose `kit_id` handsd minted and checked against
the spool — the stored zip and its record naming the kit and the consultation
it was filed during, and the passing check handsd itself ran on that zip (§33)
— never by origin alone. A socket client cannot set `origin:
architect` (`hands send` refuses it, naming §32), handsd takes `hands kit file`
only while an architect consultation runs or the engine waits for its `next
kit`, and any other hold stays held for you. A kit that fails `hands kit check`
is refused by handsd and never filed, so the engine never approves one (§33). A
consultation may file at most one kit, named as its `VERDICT: next kit <name>`
names it (§33): the kit is filed while the architect runs, before that verdict,
so the engine decides the hold at the consultation's end (or at once, for a kit
filed during the `next kit` wait); a second kit, or a kit of another name, is
denied by the engine (`decided_by: playbook`) and the consultation ends
`escalate`. `[series] kickoff` is sent when
that apply, approved by the engine, replies `VERDICT: kit applied` — a rule the
engine adds, which no playbook writes. What this cannot tell apart is another
process of your user calling the socket during a consultation from the
architect's own `hands kit file` — though such a kit must pass the check and be
the one kit its consultation's verdict names. Read that
plainly before you turn it on: **the human who approves an `autonomous`
playbook is approving every apply the architect files under it.** The playbook
is itself a gated kit apply, so that approval is a real one, made once; it is
the standing approval for every apply that follows, and nothing else stands
between a kit and the branch but `hands kit check` and the cold review. A
playbook with `architect = "role"` and no `[roles.architect]` in the config is
a config error (§32): `handsd` refuses to start on it, naming both files; `hands
doctor` fails its playbook row with it; the engine stops on it if the playbook
changes under a running daemon; and `hands kit check` fails its playbook check
on a kit that carries such a playbook, judged as `handsd` judges it at load,
against the config `hands` resolves (`--project`, `$HANDS_PROJECT`, the only
config). Where no config can be judged — none resolves (the phone architect's
sandbox), several do and none is named, or it is not valid TOML — the check
fails and says why (§33): check a role-mode kit where the project's config is.

**When it escalates.** The architect's reply begins with exactly one of
`VERDICT: next kit <name>`, `VERDICT: series complete` or `VERDICT: escalate
<reason>`. `next kit` waits for the apply it filed during that consultation,
by its `kit_id` and under the verdict's name, for up to `[series] kit_wait_s`
(default 600) — and stops if none is filed; under `autonomous` a second kit or
a kit of another name ends it `escalate` at once (§33); the other two stop the
pipeline and notify. `architect.*` is not an
event a playbook can match: the engine reads the verdict itself. An
escalation's stop reason carries the architect's own reason, its session id and
the line that re-opens it — `claude --resume <id>` — so the phone tells you the
condition, and at the laptop you open the architect's directory, run that line,
`/rc`, and talk to it from the Code tab. From the phone, `reply <secret> <text>`
on `cmd_topic` resumes that same session with your text and publishes the
architect's answer titled `architect` (DESIGN §33; the command channel above).
What you decide becomes a decisions file in its next kit. The conditions are written into the playbook rather than
judged in the moment: `gate_failures = 2` (the same roadmap gate failing twice
in a row, judged by the architect) and `escalate_on = ["blocker-unanswered",
"milestone-missing", "budget-exhausted"]`. hands can see only the last of them:
`[limits] max_architect_consults` (default 12) counts the architect
consultations of a series, and the engine stops with `budget-exhausted` itself
when they are spent. The series is `[series] name`: a role-mode playbook that
renames it is refused unless it restates `max_architect_consults` in its
`[limits]`, so a kit cannot reset the count by renaming the series alone. The consultation is fired by a `consult` rule on
`aux.done` with `role = "architect"` — the review outcome, and no other event
(docs/PLAYBOOK.md, "Consult").

**Two projects (§29).** One architect directory per project, as there is one
driver directory per project: `~/hands-architect/<project>/` with its own clone
and its own `kits/`, named by that project's `[roles.architect] cwd`. Two
projects are two directories, two configs and two daemons; they still share the
one resource two daemons share, the subscription.

## 7. The ops repo (§14 step 4)

`<ops.repo>/<monitor_cmd>` must accept `--pids`, `--transcript` and `--base`;
hands fills them from the job record and tails the script's stdout, filing each
blank-line-separated block to the inbox verbatim (§5). `status_check.sh` is no
longer used by hands.

`hands doctor` proves the flags without starting a real watch: it runs the
script with `--help` and looks for the three flag names; if `--help` says
nothing about them it runs one probe with `--pids <an impossible pid>` and
stops it after ten seconds. A missing script is a clear failure naming this
step, not a crash.

If `[ops]` is left out, hands uses its own built-in stall detector instead
(transcript mtime, subagent mtime, CPU ticks, commits, `.git/index` mtime,
stash) — the tripwire rules of §5 are the ops script's, though.

Whichever of the two decides, hands also reads every role job's stream-json
(builder and aux) for claude's task-killed notice and files
`monitor.task_killed` with the task's command line, once per task (§24). It
needs no script and no flag. The stream cannot tell a harness reap from the
agent's own `TaskStop` (or a killed parent agent), so the event's `cause` is
always `unknown` (§25). Nor can it tell those from a long foreground command
the harness backgrounded and reaped, so this repository's playbook and both
templates map the event to `notify`; a job that ends `failed` is what stops (§32).

Each `claude -p` also runs isolated per job (§24). When `systemd-run --user
--scope` can start a scope on this machine (systemd-run and systemctl on PATH,
cgroup v2, a user manager that answers), the job runs inside a transient user
scope named `hands-<project>-<job>`; otherwise it starts in a new process group.
The job's live pid set, which is what `--pids` carries, is the scope's
`cgroup.procs` or the group's members. When claude exits, anything still in
that set is filed as one `monitor.orphan_processes` event with each process's
command line and `killed`, and then the scope is stopped (`systemctl --user
stop`) or, in a process group, each process proven the job's is sent SIGTERM
and, two seconds later, SIGKILL. The process group is the weaker of the two.
By the time claude is reaped its group has no leader, so the proof is the
session (§29): a process descends from the job when its session id is the
job's pid and it started before the last moment claude was observed holding
that pid; the runner observes that every 50 ms while claude runs. The
`HANDS_JOB=<job>` mark each job carries is corroboration and never sufficient
alone, nor necessary: a proven process that cleared it is killed all the same
(§30). A process that is still the job's but not proven is listed with
`killed: false` and left alive: one forked inside claude's last poll interval,
with or without the mark, and one that carries the mark but called `setsid` (a
process that also clears its environment is not listed at all). That residual is not a bug to report: a fork in the job's
last 50 ms before exit cannot be proven the job's, so it is left alive and
reported `killed: false`; stop or kill it yourself. Job end then reads
claude's pipes for at most `runner.pipe_timeout_s` (default 10 s), so such a
process holding them cannot stall the job. `hands doctor` prints an
`isolation` row saying which is in force; it is information, never a
failure.

`hands status` names whichever monitor is deciding: with `[ops]` set it prints
the script's path and the three flags hands fills for it; otherwise it prints
the built-in rule (`stall = no progress and no liveness for <stall_minutes>m`),
and `monitor.stall_minutes = 0` prints that stall detection is off.
`monitor.stall_minutes` is the built-in rule only — it is never passed to the
ops script.

## 8. Plan kit and prompts (§14 steps 5–6)

- The plan kit gains `PLAYBOOK.toml` (see `docs/PLAYBOOK.md`). It is applied
  like a decisions file — a gated `hands send` the human approves — and the
  approval of that job is the approval of every launch the playbook may make.
  The file must be committed: hands refuses a playbook that differs from
  `git show HEAD:<path>` (dirty) or is not in HEAD (untracked) when a job
  starts, stops the pipeline with a reason naming both sha256s, and `hands
  doctor` fails its playbook row the same way.
- Every builder run prompt and aux review prompt must require the reply's
  first line to begin with `VERDICT:` in the playbook's vocabulary.
- Retire: the status+arm aux prompt, the `~/Downloads` relay of prompts (files
  still land there), and the "name the session and say clear context"
  preference — `hands send --context clear|keep` is the enforcement now.

### Prompts travel as files (§4, §12 rule 6)

    hands send --role builder --context clear --prompt-file ~/Downloads/run-3.txt

`--prompt-file` reads the file as UTF-8 and sends it byte for byte — a
trailing newline included — so a prompt with a `>`, a parenthesis or a quote in
it never reaches a command line and never has to survive a shell or the
driver's Bash guard. It is one of three exclusive routes: `--prompt-file PATH`,
`--stdin`, or the prompt as an argument. A missing file, an unreadable one, a
directory or any other non-regular file (a FIFO, a socket, a device — reading
one can never end), bytes that are not UTF-8, an empty (or all-whitespace)
file, and one over the 10 MB cap are each refused by the client, before the
daemon is contacted, with one line naming the file. `--stdin` gets the same
size, emptiness and encoding refusals, in the same place, with the same message
and the same exit code: one prompt cannot get two answers by changing route.
Bytes that are not UTF-8 are refused the same way on all three routes,
including a prompt typed as an argument — Python decodes `argv` and stdin with
`surrogateescape`, so those bytes arrive as text the client cannot encode
rather than as a read that fails, and every string a request carries (`--gate`,
`--file`, `--content`) is checked the same way before the request is
measured.

The cap is counted as the prompt appears **on the wire**: the request is JSON,
and JSON spends two bytes on a `"` or a `\` and six on a control byte, so a
file at the cap made of quotes is refused here — with its two sizes in the
message — instead of dying at a broken pipe against the daemon's line limit.
Non-ASCII text is not escaped (a 9 MB file of CJK is 9 MB on the wire).

The prompt is not the whole request, so the client then measures the whole
request — the prompt, every `--file` payload, `--gate`, and the JSON-RPC
envelope around them — as the line it is about to write, and refuses **before
connecting** when that line is over the daemon's line room (the cap plus a
quarter, 13 107 200 bytes). The message names the total, the limit and the
largest part, so you know which one to move to `hands put`. A prompt at the cap
beside twelve `--file` values of backslashes is such a request — each half is
accepted alone — and it used to be written into the socket and die there:
`hands: [Errno 32] Broken pipe`, exit 1, nothing in the daemon log.

That read is **not** confined to `files.allowed_roots`, and that is deliberate,
not an oversight: the roots confine what the *daemon* writes and reads on a
role's behalf (`hands put`/`get`/`ls`, `send --file`), while `--prompt-file` is
read by the CLI, in your terminal, as you. Any file you can read is a prompt
you can send.

### Exit codes

`0` is success. **`2` means the client did not deliver a completed request** —
it refused the prompt as above, or a `hands wait --timeout` expired — and in
both cases nothing was dispatched and nothing changed. Every other failure is
`1`. `hands --help` says the same three lines.

### No background tasks in a role session (§21)

Every repository a role works in — every `roles.*.cwd` — installs the same two
files as this repository has, so that a builder or aux session cannot start a
background job:

    cd <the role's cwd>
    mkdir -p .claude/hooks
    cp ~/git/hands/.claude/settings.json .claude/settings.json
    cp ~/git/hands/.claude/hooks/no_background.py .claude/hooks/
    python3 .claude/hooks/no_background.py --selftest

The settings run the hook before every Bash tool call. It exits 2 — which
blocks the call and hands the reason back to the agent — when the call sets
`run_in_background`, or when the command daemonizes by hand: `nohup`,
`setsid`, `disown`, a trailing `&` outside quotes, or an `&` before `)`.
Booleans and redirections are not backgrounding, so `&&`, `2>&1`, `&>` and an
`&` inside quotes or in a URL all still run, and so does the project's own
gate. The reason is that the harness reaps background tasks: a long background
job started by a role session can die silently mid-mission and nothing says
so. The way to run something long is the foreground with a timeout.

The settings also run the hook before every sub-agent call — the `Agent` tool,
and `Task`, its alias (matcher `Bash|Agent|Task`; §23, H-014). In Claude Code
2.1.x a sub-agent runs in the background unless its input says
`run_in_background: false`, so the hook exits 2 on every sub-agent call that
does not carry that boolean: `true`, an omitted flag, or any other value. A
role session runs its sub-agents in the foreground.

A repository that already has a `.claude/settings.json` gets the `PreToolUse`
entry added to it rather than the file overwritten. Copy the CLAUDE.md line
too, so the session knows the rule before the hook has to say no. Hooks run
even under `--dangerously-skip-permissions`, which is what §13's
`permission_flags` gives both roles.

A `#` comment is text, and hides nothing: `ls # a & b` runs, while `sleep 30 &#
note` is the background job bash reads it to be and is blocked. A daemonizer
written as a path is the same daemonizer, so `/usr/bin/nohup ./long.sh` is
blocked as `nohup ./long.sh` is — at the price of refusing `ls -l /usr/bin/nohup`
too, which starts nothing.

### What the hook cannot see

The hook reads one command line as shell text. It never runs the line, never
resolves a variable, and takes quoted text as text. That last one is a choice,
not an oversight: reading quoted text as shell would block `git commit -m
'runner: the log & the spool'` and `grep -rn "nohup" src`, which a role session
needs, so the hook cannot close the first item below without breaking the
commands the gate itself is made of. Everything here is **allowed** today:

    bash -c 'sleep 30 &'        # an inner shell: the quoted text is an argument
    sh -c "nohup ./long.sh"     # ...and so is this one
    eval 'sleep 30 &'           # eval, the same way
    screen -dmS job ./long.sh   # a terminal multiplexer detaches for you
    tmux new -d ./long.sh
    at now                      # a scheduler runs it later, out of this session
    systemd-run --user ./long.sh
    ./run.sh                    # a script that forks or daemonizes inside itself
    python3 -c 'import os; os.fork()'
    D=nohup; $D ./long.sh       # the daemonizer arrives through a variable
    \nohup ./long.sh            # ...or through a quoting spelling of the word

A sub-agent can also end up in the background with no call the hook can
refuse. `SendMessage` continuing a finished sub-agent runs that sub-agent in the
background: that is what happened in H-014, where every `Agent` call had said
`run_in_background: false`. The call names an agent and a message, not a mode,
so there is nothing background-shaped in it to refuse, and refusing
`SendMessage` itself would stop a role from ever continuing a sub-agent. The
hook does not match it. The hook is not what answers that case. hands sets
`CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0` in the role environment (§2, §23) so
that `claude -p` waits rather than terminating, and records a harness
termination as `failed`. That a real claude binary waits with the ceiling at
0 has not been observed.

So the hook is a guardrail against the spellings a role session actually
writes, not a sandbox. The rule it enforces is in CLAUDE.md as prose for the
same reason: a session that means to obey it is stopped by the hook when it
slips, and a session that works around it was never being stopped by a hook.

---

## First run, end to end

    hands status                                  # daemon, roles, monitor
    hands send --role aux --context clear "Reply with: VERDICT: hello"
    hands send --role aux --context clear --prompt-file ./prompt.txt   # prose route (§4)
    hands wait <job> --timeout 300
    hands show <job>                              # the record; `result` verbatim
    hands jobs -n 5
    hands inbox --ack

At the laptop you can also block on the next pipeline event, in the foreground
of this terminal. The driver does not: it arms nothing, and your message
`check` is its wake (§11, driver/CLAUDE.md rule 8).

    hands wait --for stop,held --timeout 3600     # exits 2 on timeout, 0 on an event

## What is not proven

- **No real `claude` has ever run under hands.** Every test runs against
  `tests/fake_claude.py`. `hands doctor --live` is the first real turn, and it
  has not been run in this repo.
- The ops-script bridge has only ever been exercised against
  `tests/fake_monitor.py`; no real `watch_monitor.sh` with the three flags
  exists yet (§14 step 4 is the work that creates it).
- **ntfy delivery has never been proven.** It has only been driven through a
  recording transport in the tests (`tests/test_wake.py`); no request has ever
  left the machine. It carries more than it used to: §11 answered the wake-path
  question by retiring the driver's wait, so ntfy is the only thing that tells
  the human an event happened when they are not looking. `hands notify --test`
  is the command that proves the transport, and the notification check `hands
  doctor` prints is the one that proves an event you did not ask for arrives.
  Run them once at an install and record the answer.
- **The phone channel has never read a real ntfy stream.** Its tests feed a
  fake `/json` stream and record the buttons' `Actions` header; no command has
  been sent from a real phone, and no button has been pressed on one. No kit has
  been fetched from a real ntfy attachment: the tests serve the attachment from a
  local HTTP server, so the curl line above and the ntfy app's attach are
  unproven. No `go` has been sent from a real phone, so the closed loop above
  has never run end to end. `hands who` matches sessions through
  `~/.claude/sessions/<pid>.json` (§27, H-020), a file read only as the tests
  write it. Nor has
  `handswho` pushed a picture to, or read a command from, a real topic.
