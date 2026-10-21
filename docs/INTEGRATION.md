# Integration — putting hands on the laptop

DESIGN §14, as a checklist. Do it once per machine (steps 1–2), then once per
project (steps 3–8). Every command here was run against the CLI in this repo;
where something has never been proven, it says so.

Nothing in hands is a background daemon you have to trust blindly: `hands
doctor` is the check, and `hands status`, `hands pipeline` and `hands inbox`
are the whole of its state.

docs/OPERATIONS.md is the human's runbook for a hands machine (DESIGN §40):
what the machine holds, its secrets by kind, and what to do at a usage-limit
stop, without the phone, for a planned migration, after a disaster and at a
release install. docs/RELATED.md records two readings of other orchestrators,
Gas Town and Conductor, that the harness work cites; docs/HARNESS-PROBE.md is
the dated record of the harness probe.

---

## 1. Install (once per machine)

    uv tool install ~/git/hands        # -> "Installed 3 executables: hands, handsd, handswho"

`~/.local/bin` must be on your PATH (`uv tool update-shell` adds it). Check:

    hands --version
    handsd --version

Python ≥ 3.11 and `uv`. The only runtime dependency is `httpx`, for ntfy.

### `gh`, for a pull request per mission (DESIGN §35)

A project whose missions run as pull requests (docs/ARCHITECT-HANDBOOK.md §9)
needs the GitHub CLI: the builder opens the PR with `gh pr create`, and the
review finds it with `gh pr list`, reads the hosted review with `gh api` and
merges a clean one with `gh pr merge --merge`. hands itself never runs `gh`
except for doctor's rows and `hands ci-wait` (DESIGN §45), both read-only. Three things, for **the user handsd runs as** (every role
job runs as that user, so it is that user's login that counts):

- `gh` installed and on that user's PATH;
- `gh auth login` run as that user;
- a token with the `repo` scope (`gh auth status` lists the token's scopes;
  `gh auth login --scopes repo` asks for it).

`hands doctor` checks all three (step 4). A project whose briefs say
"direct" commits to `main` and needs none of it.

A project whose `main` takes pull requests only (DESIGN §45,
docs/PR-CI-GATE.md) also runs `hands ci-wait <pr>`, which reads the checks
with `gh pr checks` and `main`'s rules with `gh api`, both read-only. Pushing
the CI workflow's file (`.github/workflows/check.yml`) needs GitHub's
`workflow` scope when the git user pushes over HTTPS with the `gh` token:
`gh auth status` lists the scopes, and `gh auth refresh -s workflow` adds it.

The working tree must be on `main` between missions: the next kit apply and
the next kickoff run in the builder's cwd, on whatever branch it is on. The
builder returns it at the end of a mission, and the review after a merge,
with `git checkout main && git pull --ff-only`. A tree left on `mission-N`
(a blocked mission, a review with blockers, a hand edit) is yours to put back
the same way before the next `go`.

## One command for steps 2, 3, 5 and 6: `hands project add` (§38)

    hands project add <project> --repo <url> --dry-run   # every path and command; writes nothing
    hands project add <project> --repo <url>

does for one project what the sections below do by hand, from the hands that is
installed (`hands handbook --templates` is where its templates are):

- `~/.hands/<project>.toml` from the installed `templates/config.toml`, with four
  generated topics that carry the project's name (`ntfy_topic`, `cmd_topic`,
  `who_topic`, `who_cmd_topic`) and a generated `cmd_secret`, which is also
  written alone to `~/.hands/<project>.cmd_secret`; both files mode 600. The
  config names `[roles.builder]` and `[roles.aux]` at `~/git/<project>`, the
  builder's own clone, which you make yourself; and `ntfy.sh` until you set
  `ntfy_url` (see "Self-hosted ntfy over Tailscale").
- `~/hands-driver/<project>/` and `~/hands-architect/<project>/` (and its
  `kits/`), each with the shipped `.claude/settings.json`, the shipped guard at
  `.claude/hooks/bash_guard.py`, the role's `CLAUDE.md` with the Parameters
  filled (`driver/CLAUDE.md`, and for the architect role `architect/CLAUDE.md`,
  the instruction's role variant), and `repo/`, a clone of `<url>` whose push
  URL is `no_push`.
- `~/.config/hands/<project>.env` (empty), `~/.config/systemd/user/handsd@.service`
  when it is not there yet, then `systemctl --user daemon-reload` and
  `systemctl --user enable handsd@<project>`. Starting it, and enabling
  `handswho@<project>`, are left to you.
- `hands --project <project> doctor`, printed. Its failures (no builder clone yet,
  no `claude` on PATH) are your next steps; they do not change the command's exit
  status, which is 1 only for a refusal or a failed `git` or `systemctl` step.
- Last, the Project instruction of `docs/ARCHITECT-INSTRUCTION.md` with the
  Parameters filled, for pasting into the Claude Project (fill its Purpose
  block), and the question to ask it: "What are your Parameters?".

The Parameters it fills: `PROJECT` and `REPO_URL` from the command line, and
`BRANCH = main`, `PLAN = meta/CHECKPOINT.md meta/plan.md`, `QUESTIONS =
meta/findings/FINDINGS.md`, `PLAYBOOK = PLAYBOOK.toml`, hands' own conventions;
edit them where the project differs. It refuses, before writing anything, a
project that exists (its config, its spool or its `.cmd_secret` is there), a role
directory that is not empty, and a name outside the pattern below. Proven by
tests against a temporary HOME, a stand-in `systemctl` and a local bare
repository; it has not been run on a real laptop.

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

**A restart kills running work (§38, §39).** A restart of handsd kills every
running job of the project, not only the builder's: the stop signals each
running `claude` and records it `orphaned` (`orphan_reason: daemon_stop`), and
the next start feeds each orphan to the playbook once as `<role>.orphaned`. What
resumes is the playbook's rules: the shipped playbooks (this repository's
`PLAYBOOK.toml` and both templates) carry `builder.orphaned → resume` and
`aux.orphaned → resume`, so a killed run or review is re-sent to a fresh
context — the builder's as `[roles.builder] resume_line` (else its own prompt),
the review as its own prompt, a phone `answer` as a `keep` — bounded by
`[limits] max_resumes`. An orphaned consultation (a driver or architect job) is not
resumed: it stops the pipeline, and the start notification says so. A job still
queued stays queued and the next start runs it. So restart between jobs when you
can: `hands status` shows what is running.

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
                                         # [server], where older configs have
                                         # them; never in both places
    ntfy_topic = "hands-<project>-<something-random>"
    ntfy_url = "https://ntfy.sh"         # default
    # ntfy_token = "tk_<…>"                     # optional: a self-hosted ntfy's access
    #                                           # token, sent as a bearer (§33); only
    #                                           # beside an ntfy_url naming that server,
    #                                           # never ntfy.sh (§34); see
    #                                           # "Self-hosted ntfy over Tailscale"
    # the command channel, optional (cmd_secret is required with cmd_topic),
    # and the who view and its commands, optional; see "Optional:
    # notifications, the command channel and the who view":
    # cmd_topic = "hands-<project>-cmd-<another-random>"
    # cmd_secret = "<one long random word>"
    # who_topic = "who-<project>-<random>"
    # who_cmd_topic = "whocmd-<project>-<random>"
    # who_min_interval_s = 60                   # default: handswho's floor between
    #                                           # two publishes (§38)

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
    BASH_DEFAULT_TIMEOUT_MS = "900000"   # builder and aux: hands sets both Bash
    BASH_MAX_TIMEOUT_MS = "900000"       # limits to "900000" unless set here (§36)

    [roles.aux]
    cwd = "~/git/<project>"
    queue_depth = 4                      # default for aux (builder 1); `hands
                                         # status` reports it as queue_capacity too

    [roles.driver]                       # optional (§27): the driver role
    cwd = "~/hands-driver/hands"         # the driver directory and its repo/ clone
                                         # (~/hands-driver/<project>; this is hands'
                                         # own); permission_flags must stay empty
    branch = "main"                      # default (§36): the clone is checked out
                                         # at origin/<branch> before every job

    [roles.architect]                    # optional (§31): the architect role
    cwd = "~/hands-architect/hands"      # the architect directory, its repo/ clone
                                         # and its kits/; permission_flags must stay
                                         # empty, as for the driver
    branch = "main"                      # default (§36), as for the driver

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

    [repository]                         # how `main` moves for hands (§45)
    main = "direct"                      # default, as before; or "pull-request":
                                         # only through pull requests merged once
                                         # their checks have passed (any other
                                         # value refuses to load). Read at start,
                                         # so a change takes a restart

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
  --role driver` is refused. Before every driver and architect job (§36,
  H-042) the runner advances the role's clone: `git -C <clone> fetch -q origin`,
  then `git -C <clone> checkout -q --detach origin/<branch>`, where `<branch>` is
  the role's `branch` key (default `main`; read by these two roles only). A
  clone that cannot be advanced (an unreachable origin, a branch origin does not
  have, local changes in the way) fails the job before `claude` starts:
  `failed`, `failure_reason` `spawn_error`, and `stderr_tail` holding the git
  command and git's own message. A role with no clone has nothing to advance;
  its job runs, and the guard refuses every `git -C`. `hands doctor` prints a
  `role driver` row with the
  cwd, the project its jobs see (`env HANDS_PROJECT=<project>`), the clone, the
  clone's HEAD against `origin/<branch>` as last fetched (doctor reads the
  clone's refs and does not fetch; the line does not change the row's status),
  the settings, the guard and its mode (§28, §36). The row fails on
  a permission bypass, when the driver directory's `.claude/settings.json` does
  not name the hook (a `PreToolUse` command hook for `Bash` that runs
  `.claude/hooks/bash_guard.py`), and when that hook's `--selftest` is not green
  run with the role's environment (`HANDS_ROLE=driver`). The hook self-tested
  is the file the settings' command names (§29), run as `python3 -I` with an
  empty `PYTHONPATH` (§36), so a module planted beside the guard is not imported
  by the self-test. The command must run it as
  the guard (§30, §37): exactly `python3 -I` and a path ending in
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
  cannot read fail. Since §34 (review 17 should-fix 4, 5) the settings are
  three layers: the two above and the user-level `~/.claude/settings.json` (may
  be absent; unreadable, it fails), every rule above applied to each; the row
  also fails when any layer's `env` sets a `HANDS_*` or `CLAUDE_*` variable, or
  (past §34's letter) `PATH` or a `PYTHON*` variable; when a guard hook carries
  any key besides `type` and `command` (`async`, `timeout`); when the hook
  command names a guard other than the role directory's own
  `.claude/hooks/bash_guard.py` (an absolute path elsewhere, compared by
  realpath); and when the named guard's sha256 is not that of the guard the
  repository ships (`driver/hooks/bash_guard.py`, carried in the wheel as
  `hands/shipped/bash_guard.py`) — both hashes printed — whatever its
  `--selftest` exits. The row ends with `verified:` lines: the settings files read
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
  Builder and aux jobs also get `BASH_DEFAULT_TIMEOUT_MS=900000` and
  `BASH_MAX_TIMEOUT_MS=900000` unless this table sets them (§36, HF-006): the
  harness moves a foreground command past its default limit to the background,
  where the no-background hook cannot see it, and a three-minute gate was moved
  so. Driver and architect jobs do not get them from hands. Doctor prints both
  effective values on the builder and aux rows.
  A project whose gate runs longer than 15 minutes raises `BASH_DEFAULT_TIMEOUT_MS`
  and `BASH_MAX_TIMEOUT_MS` in its `[roles.builder.env]` and `[roles.aux.env]`
  — an edit of its own config at the laptop, or an aux prompt its own chat
  gives — and its briefs name a timeout no longer than that (DESIGN §42,
  H-072: a gate on a shared machine took 1281 s). hands' default is
  unchanged, and hands' own briefs name 15 minutes (900000 ms). The installed
  Claude Code CLI has no ceiling of its own on `BASH_MAX_TIMEOUT_MS`: in
  2.1.302 it takes any positive number of milliseconds, raised to
  `BASH_DEFAULT_TIMEOUT_MS` when that is larger, and is 600000 when unset. Found by
  reading the CLI's bundled JavaScript inside its native binary
  (`~/.local/share/claude/versions/2.1.302`, the target of the `claude` on
  PATH) with `grep -a` for the variable's name, never by running it; the
  only bound beside it is a cap of 2147483647 ms, JavaScript's longest timer,
  on another limit the CLI derives from it. Read it again after a CLI
  upgrade.
  Every role job's environment also carries `HANDS_PROJECT`, the config's
  project name (§36, H-043), over handsd's own environment and this table
  alike; doctor prints it on each role's row as `env HANDS_PROJECT=<project>`.

  **A harness installed under nvm** (DESIGN §40, "The harness probe"). A job
  handsd spawns does not read a shell profile: under systemd nothing sources
  the `~/.bashrc` where nvm puts itself on PATH, so a harness under
  `~/.nvm/versions/node/<version>/bin` (the Codex and dsh binaries
  docs/HARNESS-PROBE.md records are in `~/.nvm/versions/node/v22.23.3/bin`)
  is not on a job's PATH unless the role's `env` table puts it there. A
  `PATH` in the table replaces handsd's own for that role's jobs; it is not
  prepended to it, so write the nvm directory first and then every directory
  the job still needs (`python3` for the hooks, `git`, `systemd-run`):

      [roles.builder.env]
      PATH = "/home/<you>/.nvm/versions/node/v22.23.3/bin:/home/<you>/.local/bin:/usr/local/bin:/usr/bin:/bin"

  The value is taken as written: no `~`, `$HOME` or `$PATH` in it is expanded.
  Those two harnesses start with `#!/usr/bin/env node`, so even one named by
  an absolute path needs the nvm directory on the job's PATH, for the `node`
  it runs on. Doctor's `claude` row looks `[runner] claude` up on doctor's own
  PATH, not on a role's `env` PATH.

  **The transcript path follows `CLAUDE_CONFIG_DIR`** (DESIGN §40, H-063). A
  role whose `env` sets `CLAUDE_CONFIG_DIR` keeps its transcripts under that
  directory's `projects/`, and the monitor reads them there: a job's
  transcript is `$CLAUDE_CONFIG_DIR/projects/<dashed cwd>/<session>.jsonl`
  when the job's environment — handsd's own or the role's `env` table — sets
  the variable (a relative value is taken from the role's cwd), and
  `~/.claude/projects/<dashed cwd>/<session>.jsonl` otherwise. The runner
  writes that path into the job record's `transcript_path` when claude
  reports its session, before the monitor's first scan.
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
are on, whether `ntfy_url` is a public broker, and whether handsd is answering.
The `broker` row (§38) is a **warning** when `ntfy_url` is unset (so
`https://ntfy.sh`) or names a host that is neither a private address (RFC 1918,
loopback, link-local, IPv6 unique-local, `localhost`) nor a tailnet name (an
address in `100.64.0.0/10`, or a name ending `.ts.net`): it names the public
broker's daily cap on what one address may publish and the "Self-hosted ntfy
over Tailscale" section below. A private or tailnet host is `ok`. Doctor
judges the url's text only; it does not resolve the name or reach the server. A daemon
that is not running is a **warning**, not a failure — this step comes before
you have to have started one. Exit code 1 means a check failed.

The `gh` row (DESIGN §35, §36) runs `gh --version` and `gh auth status
--active --hostname github.com` as the user doctor runs as — handsd's user
when the daemon answers `doctor` — and reports the version, the path, the
login of the active github.com account and whether its token's scopes
include `repo`. Another host listed by `gh auth status` (a GitHub Enterprise
host, say) or a bad account on one does not decide the row:

    ok    gh   gh version 2.92.0 (2026-04-28)  (/usr/bin/gh)
               logged in as <login> (user <user>); token scopes include `repo`

No `gh` on PATH, a `gh --version` that does not answer, a `gh auth status`
that does not return, not logged in, or a token without `repo` is a `warn`
naming the remedy — run `gh auth login` as this user (and grant the `repo`
scope) — and is a warning, not a failure, because a project may commit
direct.

The `main` row (DESIGN §45) prints `[repository] main` and `main`'s
effective rules, read with `gh api repos/<owner>/<repo>/rules/branches/main`
(a GET; `<owner>/<repo>` from the builder's clone's `origin`, a github.com
URL in https or ssh form), each rule type named. It is `ok` when they agree:
`direct` with neither `pull_request` nor `required_status_checks`, or
`pull-request` with both (the required checks named). It warns, never fails,
on `direct` with either rule (a direct push is refused, so applies stop and
reviews go to branches: set `pull-request`); on `pull-request` with no
`pull_request` rule (`main` is not protected yet: docs/PR-CI-GATE.md); on
`pull-request` with `pull_request` and no `required_status_checks` (pull
requests merge without CI, and `hands ci-wait` has no check to wait for, so
every apply stops); and on either setting with `required_linear_history`,
`update` or `merge_queue` (hands' merge commits and pull-request merges are
refused or queued by it). With no `gh`, no sign-in, an `origin` that is not
on github.com, or a failed read, the row is skipped, naming why; the `gh` row
already warns about `gh`.

The `worktrees` row (DESIGN §40, H-067) reads `.git/worktrees/` in each
role's clone (`<cwd>/repo` when there is one, else the cwd when it is a git
repository) from git's own files, running no `git`. It is a **warning** when
a worktree registered there has no directory any more — an aborted review's
under `/tmp` — or an entry has no readable `gitdir`, and it names each entry
and the remedy, `git -C <clone> worktree prune` (a locked entry is `git
worktree unlock`ed first). Otherwise it is `ok`, with the count of linked
worktrees per clone.

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

    ntfy 200  https://ntfy.sh/hands-<project>-<random>
    ntfy 403  https://ntfy.sh/hands-<project>-<random>     # printed too, and exits 1

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
machine. With `ntfy_token` set, every publish and every subscription carries it
as a bearer ("Self-hosted ntfy over Tailscale", below). All three are off unless
configured, and hands runs without any of them. Every topic name carries the
project (`hands-<project>-…`, `hands-<project>-cmd-…`, `who-<project>-…`,
`whocmd-<project>-…`, DESIGN §36), and every title handsd publishes begins with
`<project>: ` — `demo: hands: the pipeline stopped` — so two projects on one
phone are told apart by topic and by title; the titles this page names
(`hands: reply`, `builder`, …) are what follows that prefix:

| what | on when | who reads the topic |
|---|---|---|
| notifications | `ntfy_topic` is set | your phone: `stop`, a held job, an exhausted `max_resumes`, daemon start/crash (§11) |
| the command channel | `cmd_topic` is set (and `cmd_secret`, which it requires) | handsd |
| the who view | `who_topic` is set | your phone; `handswho` publishes it |

`hands doctor` reports each of the three as on or off, never as a failure: its
`notifications`, `phone` and `who` rows; the `notifications` row also says
`ntfy token on` or `ntfy token off`, never the token. Its `go` and `kit transport` rows
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
without a `cmd_secret`, below) is the failed `config` row, as always. The
`topics` row warns, never fails, when a configured topic's name does not carry
the project, naming the key and the shape to rename it to — never the topic.

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

A daemon start publishes exactly one start notification, `hands: handsd started`
(§32), and anything the start itself raises before it — the stop an orphaned
consultation's end makes, when a daemon died with a driver or architect job
running — is folded into its message, title and reason, rather than published a
few milliseconds ahead of it. When the start picks up jobs a dead daemon left
queued, the notification waits for them to end, for at most 5 seconds (DESIGN
§33): a queued job that fails at once stops the pipeline inside that window, and
the stop is folded in rather than published a quarter second after the start.
The same window is the bound on everything else it folds: none waits longer than
5 seconds. A queued job still running when the window closes does not hold the
start notification; what its end raises later is published on its own.

A held job is never folded (DESIGN §34). Its `job.held` notification is
published at once, with its Approve and Deny buttons, whether the job was held
before the start (every job still held is published again, with fresh buttons)
or during it; the start notification names it by title only. One hold is
decided before it is published (DESIGN §36): under a playbook with `architect =
"role"` and `autonomous = true`, the held apply of a kit the architect filed is
published only once the engine has decided it — as one notification without
buttons, `kit <name> filed by the architect; apply approved by the playbook`,
when it approves it, and as the held notification with its buttons when it does
not (the kit is not the one the verdict named, the stored zip's hash is not the
checked one). Stopping handsd
inside the window publishes the start notification first, and handsd waits for
what is already queued to publish instead of cancelling it.

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
long poll to ntfy, nothing listening on this machine — and takes twelve commands
from it. Set it up once:

    python3 -c 'import secrets; print("hands-<project>-cmd-" + secrets.token_urlsafe(16))'
    python3 -c 'import secrets; print(secrets.token_urlsafe(32))'

The first line is a topic name, the second the secret. Put both in the config
beside the events topic, which must be a different topic:

    [notify]
    ntfy_topic = "hands-<project>-<something-random>"
    cmd_topic = "<the first line>"
    cmd_secret = "<the second line>"

Restart handsd (`systemctl --user restart handsd@<project>`). A `cmd_topic` without a
`cmd_secret` does not load: doctor fails its `config` row, and handsd refuses
to start. So does a secret with a blank inside it, and a `cmd_topic` equal to
`ntfy_topic`.

Publish a command to `cmd_topic` from the ntfy app. The last word is the token
(but for `reply`, `answer` and `consult`, whose second word is the secret):

    approve <job> <secret>
    deny <job> [reason words] <secret>
    pause <secret>
    resume <secret>
    status <secret>
    progress <secret>
    go <secret>
    kit <secret>                  (with a .zip attached to the message)
    reply <secret> <text>
    answer <secret> <text>        (a .zip may be attached to the message)
    consult <secret> <text>       (a .md may be attached to the message)
    digest <secret>

- `approve` and `deny` decide a **held** job, exactly as `hands approve|deny`
  does, and the job record says `decided_by: phone`. `pause` and `resume` are
  `hands pause` and `hands resume` (`hands pipeline` shows `paused yes
  (phone)`). `status` answers on `ntfy_topic` with a few lines: each role,
  the held job ids, whether the pipeline is paused, the unread inbox count.
- `progress` (DESIGN §38) answers on `ntfy_topic`, titled `progress`, with
  what `status` does not say: the builder's running job and how long it has
  run, or its last ended job, that job's state and its `VERDICT:` line; the
  branch and last three commits of the builder's cwd (`git -C <cwd> rev-parse
  --abbrev-ref HEAD` and `git -C <cwd> log --oneline -3`), or one plain line
  when that directory is not a repository or has no commit yet; and the first
  line of `meta/CHECKPOINT.md` at the repository root (`git rev-parse
  --show-toplevel` of the builder's cwd, DESIGN §39) that names a unit in
  progress, or `no checkpoint`. It is read-only and starts no job.
- `go` is the only way to start work from the phone (DESIGN §26). It sends the
  playbook's `[series] kickoff` line (docs/PLAYBOOK.md) to the builder as a
  `clear` send, the job record says `origin: phone`, and `hands jobs --origin
  phone` lists those jobs. (The apply a kit files is `origin: kit`, and `hands
  jobs --origin kit` lists those; both origins, like `cli`, un-pause a stopped
  pipeline when their job starts.) The send takes the same path as `hands send`, so the
  gate patterns still apply. handsd answers on `ntfy_topic` with the job id and
  its state. It is refused, and the refusal answered titled `go`, while the
  builder has a job running or queued, when there is no playbook (or it cannot be loaded), and when the
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
- `answer` is the phone answering the builder (DESIGN §36). `answer <secret>
  <text>` is delivered as `hands send --role builder --context keep "<text>"`
  would be, to the builder's last session: one job, `origin: phone`, whose
  prompt is `<text>` as typed after the whitespace that follows the secret. The
  secret is the approval: an answer is never held by the gate patterns, whatever
  its text says (a text naming a decisions file included). Its job un-pauses a
  stopped pipeline when it starts, as a `cli` send's does, because answering the
  question is answering the stop. handsd answers on `ntfy_topic` titled `hands:
  answer` with the job id and state, files the text in the inbox as
  `answer.sent`, and when the job ends publishes the builder's final reply
  there titled `builder`; its `VERDICT:` line fires the playbook's rules as any
  builder end does. It is refused, and the refusal answered under `hands:
  answer`, when the text is empty, while the builder has a job running, queued
  or held, and when the builder has no resumable session. A file attached to
  the message is judged by the `kit` rules above (a plain `.zip` name,
  `kit_max_mb`, an http(s) URL, `kit_dir` inside `allowed_roots`) before
  anything is fetched, and fetched into `kit_dir` as a kit is; nothing is
  unzipped or applied. The delivered text then ends with one sentence naming the
  file's path, the job record's `files_written` keeps its sha256, and
  `answer.sent` carries the attachment's name and hash. A refused attachment
  refuses the answer. When the driver escalates, the stop's message carries the
  builder's question verbatim, so the question and your answer are on one
  screen; the architect's next consultation lists every `answer` (with every
  `hands send --role builder --context keep` and every committed
  `meta/decisions/*-owner.md`) since its last one, under "Decided by the human
  since your last consultation".
- `consult` asks the engine for one architect consultation (DESIGN §42), in
  role mode only. `consult <secret> <text>` starts an architect job of origin
  `playbook` whose prompt is the architect's consult prompt with your reason —
  the text, then an attached `.md` file's text — in place of the review's
  sections, under "The human's reason for this consultation"; its first line is
  `hands consult: consult on job none (role human)`. It counts against
  `[limits] max_architect_consults`, its verdict is read as any
  consultation's, its kit is filed and applied as any, and it un-pauses a
  stopped pipeline. The secret is the approval: nothing is held. handsd answers
  titled `hands: consult` with the job id; the inbox's `consult.sent` names the
  phone and carries the reason's sha256, never the reason. It is refused, and
  the refusal published titled `consult`, without `[series] architect = "role"`
  or `[roles.architect]`, while an architect, builder or aux job is running,
  queued or held or a `next kit` wait is open, when the reason is empty, when
  the budget is spent, and when the prompt passes the 10 MB cap. The attachment
  is judged as a kit's is, but by its own name rule (a plain `.md` name) and a
  256 KiB cap, fetched into `kit_dir` (the first free `<stem>-<n>.md` when the
  name is taken) and read as UTF-8. `hands consult [--file <path>] [<text>]` is
  the same at the laptop.
- `digest` (DESIGN §42) answers on `ntfy_topic`, titled `digest`, with the
  lines `hands digest` prints at the laptop: one per project configured on the
  machine (every `~/.hands/<project>.toml`, in name order) — the project; its
  daemon, `up` when its socket answers `status` within two seconds, else `down`;
  its pipeline, `running` or `paused`; the mission number from the first
  `Mission:` line of the builder's `meta/CHECKPOINT.md`, else `-`; the builder,
  `running <job> <age>` or `idle`, with the newest builder job's verdict line cut
  to 60 characters; `architect <used>/<budget>` in role mode, else `driver
  <used>/<budget>`; and the last stop's time and the first line of its reason cut
  to 100 characters, or `no stop`. Every project's `cmd_secret` and `ntfy_token`
  is redacted (`[redacted]`) before any field is cut. A config that does not load
  is one line naming its file only, never the loader's message. It is read-only:
  it starts no job, and `hands digest` needs no daemon.
- **The buttons.** With the channel on, a held job's notification has Approve
  and Deny buttons. Each publishes `approve <job> <nonce>` or `deny <job>
  <nonce>` to `cmd_topic`. The nonce is 32 random bytes minted for that one job
  and kept only in handsd's memory. It can decide only that job, and only once.
  It is gone as soon as the job is decided by any route (phone, `hands
  approve`, the driver) and when handsd restarts. After a restart the old
  buttons do nothing: handsd publishes every job still held again, with new
  buttons (§34), and names each by title in its `handsd started` notification.
  `hands approve <job>` / `hands deny <job>`, or `approve <job> <secret>` on
  `cmd_topic`, decide a held job all the same. `pause`, `resume`,
  `status`, `progress`, `go` and `digest` take the secret only, never a nonce. With
  `ntfy_token` set each button also carries the bearer, so a token-protected
  server accepts the press (§38; "Self-hosted ntfy over Tailscale").
- **A command with the right secret is always answered; nothing else is**
  (§39, H-058). `status`, `progress`, an accepted `go`, a written kit, a
  `reply` and an `answer` answer as above. A command carrying the right secret
  (or, for `approve` and `deny`, the job's nonce) that handsd refuses — no such
  job, a job that is not held, a builder with a job held, no resumable
  session — is published on `ntfy_topic` titled `<command>` with `<command>
  refused: <reason>`. A malformed `approve` or `deny` is answered only when
  its last word is the secret; one whose last word is a nonce is logged and
  not published. Only a wrong or missing secret or nonce, a malformed line
  not ending in the secret, and a message whose first word is no command,
  stay silent: each is logged in handsd's journal (`journalctl --user -u
  handsd@<project>`) and ignored. If a command seems to do nothing, look there.
  The log never contains the token.
- **Job ids are lenient** (§39, H-059). The id in `approve`, `deny` and `hands
  cancel` is matched case-insensitively, with `O` read as `0` and `l` or `I` as
  `1`, and a unique prefix of four or more characters is accepted; an
  ambiguous one is refused with the candidates. (`answer` and `reply` carry no
  id.) A held job's notification prints its id on a line of its own.
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
   same name in `~/Downloads` (the default `kit_dir`). A playbook in force
   with a rule on `aux.done` and none on `aux.orphaned`, or on `builder.done`
   and none on `builder.orphaned`, adds a `WARN playbook:` line after the
   check lines; a warning does not fail the kit, and the engine logs the same
   sentence each time it loads the file (docs/PLAYBOOK.md; DESIGN §40, H-061).
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
   is refused, and the refusal answered titled `go`, while a builder job is
   running, queued or held — the apply of step 3, if you have not approved it yet, is such a job,
   and the refusal names it.
5. **Wait for the buzz.** The playbook chains the builder's verdict to the
   review and on to a stop. Every stop reaches the phone as `hands: the
   pipeline stopped` with the reason, which is the rule's message. Paste it to
   the architect, and the loop starts again at step 1. A clean review is a
   stop, so it pauses the pipeline too (the missions template's `blockers=0`
   rule is a `stop`, §39): the next kit's apply and the `go` after it un-pause
   it when each job starts, as step 3 says, so no `resume <secret>` is needed.

**The same loop from a terminal** (DESIGN §40). Two commands stand in for
the phone's `go` and `kit` when the phone is away; both need handsd running,
and neither needs the command channel. `hands go` sends the playbook's
`[series] kickoff` line to the builder as a `clear` send with `origin: cli`,
by the code path the phone's `go` takes: refused while a builder job is
running, queued or held, when no playbook loads, and when it has no
`[series] kickoff`. `hands kit apply <zip>` checks the kit as `hands kit
check` does, against the builder's cwd and the project's config, and
refuses a failing kit with the check's lines, copying and filing nothing. A
passing kit is copied into `[files] kit_dir` under its own name: nothing is
copied when a file of that name holding the same bytes is already there,
another file of that name refuses and is left untouched (the phone's
`<stem>-1.zip` renaming is not done), and its apply prompt is then filed as
a held builder job, `origin: kit`, which `hands approve <job>` releases;
`hands go` follows the applied kit as step 4's `go` does. docs/OPERATIONS.md,
"No phone", maps every phone command to its laptop form.

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
    who_topic = "who-<project>-<something-random>"
    who_cmd_topic = "whocmd-<project>-<something-random>"   # optional

and run `handswho --project <project>` (the same as `hands who --daemon`).
`systemd/handswho@.service` is an optional user unit, off unless you enable it;
install it the way its header says, as `handswho@<project>`. `handswho` pushes the picture to
`who_topic` when what is running, held or waiting changes (a session's state
must hold for two scans first; your own
sessions never trigger a push), and whenever `status`, `who`, `check` or `?` is
published to `who_cmd_topic`. A change is compared with every relative-time
rendering blanked (each age such as `4s`, `5m`, `2h00`, and the header's
`HH:MM`), so a picture that differs only in its times is not published; the
picture that is published still shows them (§38). No two publishes fall
within `[notify] who_min_interval_s` (default 60 seconds) — counting a publish
the broker refused — except one a command asked for; a change inside it is
published by the first scan past it, every 20 seconds. Those words take no secret, because they execute
nothing: the only answer is the same picture. The picture does carry the first
line of each running job's prompt and of the commands under each session, so
keep `who_topic` as private as `ntfy_topic`. Without `who_topic`, `handswho`
exits 1 and names the key.

### Self-hosted ntfy over Tailscale (§33)

On ntfy.sh a topic is only as private as its name, and everything hands
publishes crosses a public broker: held-job reasons, `status` answers, the
architect's replies, the who picture, a kit. DESIGN §33's alternative is an ntfy
server of your own, in a container on the laptop, whose topics require a token,
reached by the phone through the Tailscale tunnel. Once hands and the phone use
only that server, free text about a project stops going to a public broker.

#### The default for role mode

Under `[series] architect = "role"` hands publishes for hours with no human in
the loop: the architect's replies, the builder's answers, held kits, the who
picture. The self-hosted server below is the documented default for role mode
(§38); ntfy.sh stays fine for a first phone-mode trial. `hands doctor`'s
`broker` row (§4 above) warns, and does not fail, on a public `ntfy_url`, and
names the public broker's daily cap and this section.

What hands does (tested against stand-in servers, see the end of this section):
`[notify] ntfy_token` is sent as `Authorization: Bearer <token>` on every publish
(handsd's notifications and answers, `handswho`'s pushes, `hands notify --test`)
and on every subscription (handsd's `cmd_topic` long poll, `handswho`'s
`who_cmd_topic`). A kit attachment is fetched with the bearer only when its URL
has the same scheme, host and port as `ntfy_url`; an attachment anywhere else is
fetched without it. With no `ntfy_token`, no request carries an
`Authorization` header. The token must be one word of visible ASCII; anything
else does not load, and the refusal names `[notify] ntfy_token` without
printing it. The token is accepted only beside an explicit `ntfy_url` that is
not a public broker (§34): with `ntfy_url` unset (so `https://ntfy.sh`), or set
to a url whose host is `ntfy.sh` or a subdomain of it (any letter case, scheme,
port or path), the config does not load, and the refusal names the url, not the
token. A non-ASCII character anywhere in `ntfy_url` does not load either, token
or not (§36: an HTTP client reads `https://ntfy。sh` as `ntfy.sh`); the refusal
names the character and its position, and a host is written in its `xn--` form. handsd, `handswho`, every `hands` command and `hands doctor` (as its
failed `config` row) read the config the same way. `hands doctor` says `ntfy
token on` or `ntfy token off`.

Every `http` action hands publishes, a held job's Approve and Deny, carries
`headers.Authorization=Bearer <token>` in ntfy's short action form, beside
`method=POST` and `body=…`, when `ntfy_token` is set (§38, H-037); without a
token the actions carry no header. The token is the one the phone already
subscribes with, so a subscriber of `ntfy_topic` learns nothing new from it. A
token holding `,` or `;`, which the short form cannot quote, does not load.
`hands doctor`'s `phone` row says `buttons: bearer on`, or `buttons: no token; a
token-protected server refuses them`.

The steps below follow ntfy's and Tailscale's own documentation. They were
corrected from the first real setup, on the laptop on 2026-10-14 (DESIGN §37,
§38); check each step against the version you install.

**1. The server, in a container.** A config with access control, the
`binwiederhier/ntfy` image, and a port on the laptop's loopback only. Set
`base-url` before the first start: it is the address the phone uses, and ntfy
builds attachment URLs from it, so it must be exactly the `ntfy_url` you give
hands (a kit's URL then has `ntfy_url`'s origin and is fetched with the
bearer). With no HTTPS certificate on the tailnet, use the second form of
step 3 and write its `http://` address here instead.

    mkdir -p ~/ntfy/etc ~/ntfy/cache
    cat > ~/ntfy/etc/server.yml <<'YML'
    base-url: "https://<laptop>.<tailnet>.ts.net"
    listen-http: ":80"
    behind-proxy: true
    cache-file: "/var/cache/ntfy/cache.db"
    auth-file: "/var/cache/ntfy/user.db"
    auth-default-access: "deny-all"
    attachment-cache-dir: "/var/cache/ntfy/attachments"
    YML
    docker run -d --name ntfy --restart unless-stopped \
      -v ~/ntfy/etc:/etc/ntfy -v ~/ntfy/cache:/var/cache/ntfy \
      -p 127.0.0.1:2586:80 binwiederhier/ntfy serve

`podman run` takes the same arguments. `auth-default-access: "deny-all"` is what
makes every topic require a user or a token. `attachment-cache-dir` is what lets
the server take a kit at all.

**2. A user, its access, and a token.** One user for hands and the phone, with
access to every topic hands uses, the who topics included:

    docker exec -it ntfy ntfy user add hands          # asks for a password
    docker exec ntfy ntfy access hands 'hands-*' read-write
    docker exec ntfy ntfy access hands 'who-*' read-write
    docker exec ntfy ntfy access hands 'whocmd-*' read-write
    docker exec ntfy ntfy token add hands             # prints tk_…

`hands-*` covers `ntfy_topic` and `cmd_topic` (`hands-<project>-…`,
`hands-<project>-cmd-…`), but not the who topics: step 5 and `hands project
add` name those `who-<project>-…` and `whocmd-<project>-…`, so without the two
further grants `handswho`'s publishes and its command topic are refused. Grant
each topic by name instead if you prefer. The printed `tk_…` is the token.

**3. Through the Tailscale tunnel.** The phone joins the same tailnet (the
Tailscale app, signed in to your account). Then either:

- `tailscale serve` on the laptop, which puts `https://<laptop>.<tailnet>.ts.net`
  in front of `http://127.0.0.1:2586` for tailnet devices only. This needs
  HTTPS certificates enabled for the tailnet. Its arguments, and how it keeps
  running after the terminal closes, differ between releases: see
  `tailscale serve --help`. Or
- with no certificate domain, the container on the tailnet address, below.

Do not use Tailscale Funnel: it publishes the server to the internet.

#### A tailnet without a certificate domain

A tailnet with HTTPS certificates off has no `<laptop>.<tailnet>.ts.net`
certificate for `tailscale serve` to present. Bind the container to the
laptop's tailnet address instead of loopback and use plain http over
Tailscale; traffic inside the tailnet is encrypted by the tunnel:

    tailscale ip -4                                   # 100.x.y.z
    docker run -d --name ntfy --restart unless-stopped \
      -v ~/ntfy/etc:/etc/ntfy -v ~/ntfy/cache:/var/cache/ntfy \
      -p 100.x.y.z:2586:80 binwiederhier/ntfy serve

with `base-url: "http://100.x.y.z:2586"` in `server.yml` and the same
`ntfy_url` in step 4. The container can bind that address only after
`tailscaled` is up. In the ntfy app, the WebSockets connection option is fine
with no proxy in front of the server (DESIGN §38, from the 2026-10-14 setup).

**4. Tell hands.** In `~/.hands/<project>.toml`:

    [notify]
    ntfy_url = "https://<laptop>.<tailnet>.ts.net"
    ntfy_token = "tk_<the token from step 2>"

`ntfy_url` must be the address the *phone* reaches, not `127.0.0.1`: a held
job's Approve and Deny buttons carry `ntfy_url` and `cmd_topic`, and the phone
presses them. Keep the config file private (`chmod 600`). It already holds
`cmd_secret`.

#### A config written before `[notify]`

A config written before §24 carries `ntfy_topic` (and perhaps `ntfy_url`)
under `[server]`. It loads as it is: `[server]` is read as the fallback for a
config written before `[notify]`, and a key set in both tables refuses to load
(§39, H-054). Once step 4 or step 5 adds the same key under `[notify]`, the
config does not load, and the refusal names the key:
`ntfy_topic is set in both [server] and [notify]; set it once, in [notify]`.
Move the line: delete it from `[server]` and keep the `[notify]` one. handsd,
`handswho`, every `hands` command and doctor's `config` row refuse the same
file the same way.

**5. Move the topics off the public broker.** Every topic hands uses:
`ntfy_topic`, `cmd_topic`, `who_topic` and `who_cmd_topic`, whichever you set.
Make each name fresh, because an old name may already be known to whoever read
it on ntfy.sh (`hands project add` generates the same four shapes for a new
project):

    python3 -c 'import secrets; print("hands-<project>-" + secrets.token_urlsafe(16))'      # ntfy_topic
    python3 -c 'import secrets; print("hands-<project>-cmd-" + secrets.token_urlsafe(16))'  # cmd_topic
    python3 -c 'import secrets; print("who-<project>-" + secrets.token_urlsafe(16))'        # who_topic
    python3 -c 'import secrets; print("whocmd-<project>-" + secrets.token_urlsafe(16))'     # who_cmd_topic

One line per topic you set, with your project's name for `<project>` (DESIGN
§36: two projects on one phone are then told apart by the topic too). Then:

1. Put the new names in `[notify]` beside `ntfy_url` and `ntfy_token`, and
   move any `ntfy_topic` left under `[server]` (above). Keep
   `cmd_secret` if only you have seen it; if it was ever typed on a topic
   someone else could read, make a new one too.
2. Restart: `systemctl --user restart handsd@<project>`, and
   `handswho@<project>` if you run it. `hands doctor` should show
   `ntfy token on` and `buttons: bearer on`.
3. `hands notify --test "self-hosted"` should print `ntfy 200` and your
   server's URL. A `401` or `403` means the token or its access in step 2 is
   wrong.
4. In the ntfy app, add the server and sign in with the same token (or with
   the `hands` user and password if your app release has no token field). Then
   subscribe to the new topics on it.
5. Unsubscribe the old topics on ntfy.sh in the app. What was already published
   there stays in ntfy.sh's cache until that server expires it, and hands
   cannot delete it.

From then on handsd, `handswho` and the phone talk only to your server. A
command typed in the app publishes as the user the app signed in with.

#### What has run on a real server, and what has not

Since the 2026-10-14 setup, hands has used a self-hosted server of this shape on
the laptop (DESIGN §37, §38): handsd's and `handswho`'s publishes, the phone's
subscriptions, commands typed in the app, and kit attachments. The Approve and
Deny buttons failed there with 403, because their actions carried no token
(H-037). Since mission 22 U1 the actions carry the bearer, which
`tests/test_ntfy_token.py` reads in the published `Actions` header; no real
phone has pressed an authenticated button yet, and whether the app sends an
action's headers is not proven by any test here. Until one has, a button that
does nothing (handsd's journal shows no command) is answered by a typed
`approve <job> <secret>` from the app, or `hands approve <job>` at the laptop.

The tests stand in a server that answers 401 to any request without the bearer
(`tests/test_ntfy_token.py`): publish, `hands notify --test`, handsd's command
channel, `handswho`'s push and subscription, the buttons' header, and a kit
fetched from a local HTTP server. No test runs ntfy, a container or Tailscale.

## 5. The driver session (§14 step 2)

`driver/README.md` is the full recipe. In short:

    mkdir -p ~/hands-driver/<project> && cd ~/hands-driver/<project>
    cp ~/git/hands/driver/CLAUDE.md ./CLAUDE.md
    mkdir -p .claude/hooks
    cp ~/git/hands/driver/settings.json .claude/settings.json
    cp ~/git/hands/driver/hooks/bash_guard.py .claude/hooks/
    python3 -I .claude/hooks/bash_guard.py --selftest
    git clone <repo-url> repo
    git -C repo remote set-url --push origin no_push
    claude          # then /rc to enable remote control

Fill in the parameter block at the top of `CLAUDE.md`. The driver never
writes: the deny-list, the Bash guard hook and the push-disabled clone are
three separate layers, and none of them is prose (§12).

The driver kit has one hook: `driver/settings.json`'s `Bash` matcher running
`python3 -I` on the guard. The architect kit has two: the same `Bash` hook and
the `Write|Edit|MultiEdit` matcher running the guard with `--write` ("The
architect role", below). A builder or aux cwd carries another hook, the
no-background one ("No background tasks in a role session", below), which is
neither kit's.

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
only `log --oneline -n --grep --format --stat --name-status --date=<format>`
(`--date` only with a value, §43), `show --stat --name-status`, `fetch -q`,
`ls-remote --heads --tags`, `rev-parse --verify --short`, `diff --stat
--name-status --name-only`, `grep -n -c -l -i -e`, `cat-file -t -p -e`,
`ls-files`, `ls-tree --name-only`, `branch --list`, `remote -v` and `status
--short`; `cat` (no options), `ls` (`-l -a -la -1 -R`), `head` and `tail` (`-n
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
show|jobs|inbox|pipeline|status|handbook|kit check|kit file` (`handbook` since
§39, H-051), plus `mkdir -p`, `cp -r`
and `mv` (no other option) with every path under `HANDS_KITS`, `cp` and `cp -r`
also with every source under `HANDS_CLONE` and the target under `HANDS_KITS`
(§36), `cp` and `mv`
refused while anything under `HANDS_KITS` is a symlink or (§36) a regular file
with more than one hard link, and every `mkdir`, `cp`,
`mv` and write refused when `HANDS_KITS` itself is one (§33); `zip` and `unzip`
are in no mode's table (§32). In both
role modes reads are confined to the clone and the spool: every path that
`cat`, `ls` (`.` when it names none), `head`, `tail`, `wc`, `grep` (`.` under
`-r` when it names none), `jq`, `git` (its words after the subcommand, from the
`-C` value) and `hands` (`--prompt-file`, `--socket`, `--repo`, a kit) read must
resolve by realpath under `HANDS_CLONE`, under the spool `~/.hands/<project>/`
(the project `$HANDS_PROJECT` names, else the only `~/.hands/*.toml`) or, for
the architect, under `HANDS_KITS` or under `docs/` and `templates/` in
`HANDS_DOCS` (the installed hands' handbook and templates, so `cat
$HANDS_DOCS/docs/ARCHITECT-HANDBOOK.md` runs; nothing else in `HANDS_DOCS`,
which in a source-tree install is the hands repository; §39, H-051); with none of them named every path read is
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
line. A project in role mode publishes to a self-hosted ntfy by default ("Self-hosted
ntfy over Tailscale", "The default for role mode"). `architect/README.md` is the
full recipe; in short:

    mkdir -p ~/hands-architect/<project>/kits && cd ~/hands-architect/<project>   # a kit is kits/<name>/<repository paths>, filed with hands kit file kits/<name>
    cp ~/git/hands/architect/CLAUDE.md ./CLAUDE.md        # fill the Parameters block
    mkdir -p .claude/hooks
    cp ~/git/hands/architect/settings.json .claude/settings.json
    cp ~/git/hands/driver/hooks/bash_guard.py .claude/hooks/bash_guard.py
    HANDS_ROLE=architect HANDS_KITS=$PWD/kits python3 -I .claude/hooks/bash_guard.py --selftest
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
the architect cannot make one, and `mkdir` still runs. Since §36 (HF-003) `cp`
and `cp -r` also copy from the role's clone: every source under `HANDS_CLONE`
and the target (the last path) under `HANDS_KITS`, judged by the same realpath
containment, refused with `HANDS_CLONE` unset, while anything under
`HANDS_KITS` is a symlink, and when a source is one or (for `cp -r`) holds one
anywhere inside it; a `cp` whose sources mix the clone and the kits is refused.
The role re-issues a file by copying it and editing the copy. Since §34 (review 17
should-fix 3: a link in a directory of mode 0111 was skipped by the walk) the
walk is `os.lstat` on every path from `HANDS_KITS` down, and a directory it
cannot list or a path it cannot stat refuses `cp` and `mv` as a link does. Since §36
(review 18 should-fix 4: `cp kits/pay/h kits/h`, with `kits/h` a planted hard link
to the guard, wrote into the guard) a regular file under `HANDS_KITS` whose link
count is above one refuses `cp` and `mv` as a symlink does. A `HANDS_KITS` that is
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
cwd, the project its jobs see, the clone and its HEAD against `origin/<branch>`
(as the driver row prints them; the clone is advanced before every architect
job as it is before every driver job, §36), the kits directory, the settings, the write matcher, the
guard's self-test run in architect mode, the mode itself, and the `verified:`
lines the driver row prints plus the kits realpath. It fails on a
permission bypass (`permission_flags`, or the driver row's settings rules, above,
over both settings files), on settings whose `Bash` hook or whose
`Write|Edit|MultiEdit` hook is not the guard (the write hook must be exactly
`python3 -I <path to .claude/hooks/bash_guard.py> --write` under exactly that
matcher, all three tools must be judged, every hook under `PreToolUse` must be a
command hook, and both matchers must run the same guard file), on a guard whose
`--selftest` is not
green run with `HANDS_ROLE=architect` and `HANDS_KITS` set, on a clone whose
push is not disabled (the driver row's rule, above), on a kits
directory that is missing or does not resolve under the architect's cwd
(§32), and (§33) on a kits directory that is a symlink or holds one (§34: or
holds a directory the same walk as the guard's cannot list; §36: or holds a
regular file with more than one hard link), or when
`.claude`, its hooks directory, either settings file, either guard file or the
clone resolves under the kits directory; a missing clone warns. Since §36
(finding H-041) it also fails when the settings lack any of the three allows
`architect/settings.json` ships — `Edit(kits/**)`, `Write(kits/**)` and
`MultiEdit(kits/**)`; headless `claude -p` denies a tool no allow names, and the
`--write` hook only ever denies, so without them the role cannot write a byte —
or when any allow for `Edit`, `Write` or `MultiEdit`, in any settings layer it
reads, names anything but `kits/**`. `hands doctor --live` gives the architect
a turn that does its work in miniature: it writes one file,
`kits/hands-doctor-live-<8 hex>/DOCTOR-LIVE.md` (a fresh name each run), with
the Write tool, runs `hands kit check kits/hands-doctor-live-<8 hex> --repo
<clone>` on that one-file kit — `<clone>` is `./repo`, or `.` when the role's
directory is itself the clone — and `hands show <job>` on the newest job of the
spool (so a daemon must be running, and a spool with no job fails the row before
a turn is spent); doctor then removes the directory, which the role cannot (its
settings deny `rm`). Since §37 (review 20 should-fix 4, 5) a role with no clone,
or a kit directory of the chosen name that already exists, fails the row before
the turn, and doctor removes only the directory it created; a `hands kit check`
of any other kit or against any other `--repo` does not count. The row is judged
from what happened — the file on disk, the two commands and their results in
the turn's stream, the path gone — and names whichever of the four did not
happen. The tests prove it with the fake `claude` performing scripted tool
calls; a real turn under the real settings and guard is not proven by them.

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
— never by origin alone; the record holds the sha256 of the bytes that check
read (§36: the stored zip is read once, and the same bytes are checked and
hashed), a hash that differs from the sha256 of the bytes the client sent
refuses the filing, and the engine re-hashes the stored zip when it approves, refusing a
mismatch with `kit.refused` carrying both hashes and a stop (§34). A socket client cannot set `origin:
architect` (`hands send` refuses it, naming §32), handsd takes `hands kit file`
only while an architect consultation runs or the engine waits for its `next
kit`, and any other hold stays held for you. A kit that fails `hands kit check`
is refused by handsd and never filed, so the engine never approves one (§33). A
consultation may file at most one kit, named as its `VERDICT: next kit <name>`
names it (§33): the kit is filed while the architect runs, before that verdict,
so the engine decides the hold at the consultation's end (or at once, for a kit
filed during the `next kit` wait). `hands kit file` calls are serialized per
consultation, and a second kit is refused by handsd as "one kit per
consultation" before it is checked (§34); a consultation that tried to file a
second kit, or filed a kit of another name, ends `escalate`, and its kit, if
still held, is denied by the engine (`decided_by: playbook`). `[series] kickoff` is sent when
that apply, approved by the engine, replies `VERDICT: kit applied` — a rule the
engine adds, which no playbook writes. The kickoff it sends is read from the
playbook as committed when that reply is decided — the engine reloads the file
first, so a kit that rewrote the kickoff is followed by its own line, and a
playbook that no longer loads stops the pipeline with the loader's reason
(DESIGN §36). What this cannot tell apart is another
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
    python3 -I .claude/hooks/no_background.py --selftest

The settings run the hook as `python3 -I` (§39, H-056), as the driver's and the
architect's settings run the guard (§37): `-I` keeps a module planted beside the
hook from being imported before it. The settings run the hook before every Bash
tool call. It exits 2 — which
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

Background tasks off where the role's hook allows it (§43, H-074).
`CLAUDE_CODE_DISABLE_BACKGROUND_TASKS` counts as set when its value, trimmed
and in any case, is `1`, `true`, `yes` or `on`; then the harness moves no
command to the background (one that reaches its timeout ends there), launches
every sub-agent in the foreground and strips the sub-agent's
`run_in_background`. (1) Under that variable the hook admits a sub-agent call
whose flag is omitted or null; `true` and every value that is not the boolean
`false` stay refused, and without the variable nothing changes. An older copy
of the hook refuses every sub-agent call under the variable. (2) The wheel
carries the hook as `hands/shipped/no_background.py`: that file, or for a hands
run from its source tree this repository's own copy, is the installed hands'
copy — unless it is the role's own file (the same realpath), when there is no
installed copy for that role. (3) `hands doctor`'s builder and aux rows compare
`<cwd>/.claude/hooks/no_background.py` with the installed hands' copy by sha256
and warn, never fail, on a copy that differs or is absent, or when no installed
copy is found, naming both files and both hashes. (4) hands sets
`CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1` in a builder or aux job's environment
only when the role's copy is the installed hands' copy, decided when the job is
dispatched; a driver or architect job never gets it by default. (5) A
`[roles.<r>.env]` that names the variable decides, either way (`0` turns it
off); a value handsd itself inherited reaches no role's job; doctor prints the
variable as the job will carry it, with its source, and warns when a table sets
it on over a copy that is not the installed hands' copy, since every sub-agent
call would be refused. (6) Where the harness can still background, a long
command ends with an exit marker (`./scripts/check; echo "check-exit=$?"`), and
a run moved to the background anyway is waited for with one foreground command
that blocks until the output file shows the marker (`until grep -q
'^check-exit=' <file>; do sleep 5; done`, with an explicit timeout), never a
first-statement `sleep` of 25 seconds or more, never Monitor or a background
task. A release that changes the hook is copied into each project's repository
by that project, at a stop with no job running, then checked with `python3 -I
.claude/hooks/no_background.py --selftest`; until it is, doctor warns and hands
leaves the variable unset.

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
- **No test reads a real ntfy stream.** The phone channel's tests feed a
  fake `/json` stream, record the buttons' `Actions` header, and serve a kit
  attachment from a local HTTP server. What has run against a real server is
  the human's own use since 2026-10-14 (DESIGN §37, §38: typed commands, a
  `go` after each daemon restart, kit attachments, buttons refused with 403
  before mission 22), recorded in the next bullet and not by a test. `hands
  who` matches sessions through `~/.claude/sessions/<pid>.json` (§27, H-020),
  a file read only as the tests write it.
- **The self-hosted ntfy is proven by use, not by a test.** A server of the
  documented shape has carried publishes, subscriptions, typed commands and
  kit attachments on the laptop since 2026-10-14 (DESIGN §37, §38); the tests
  run only stand-in servers that refuse a request without the bearer. No real
  phone has pressed an Approve or Deny button carrying the bearer ("Self-hosted
  ntfy over Tailscale", "What has run on a real server, and what has not").
