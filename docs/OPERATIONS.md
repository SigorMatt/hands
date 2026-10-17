# Operations — running hands without an agent

DESIGN §40. The human's runbook for every project on a hands machine: what
the machine holds, which secrets it uses, and what to do at a usage-limit
stop, without the phone, for a planned migration, after a disaster and at a
release install. Written from the code at mission 24; where the code does not
settle something, this document says so instead of guessing. Mission 26 (M9,
"a machine is replaceable") turns the migration runbook into commands and
rewrites this document; until then every step below is a command a human
types.

No value of any secret appears here, nor an example of one. Where a command
prints a secret, the command is named and its output is not shown.

Two words borrowed from Conductor (docs/RELATED.md): a stop is a **durable
pause** — the run halts with its state on disk and resumes on a human's
signal — and a mission is **pinned to its definition version**, the kit and
its `plan:` commit on the project's branch.

Every `hands` command below takes `--project <project>` when more than one
`~/.hands/*.toml` exists; it is left out for brevity.

---

## 1. What a hands machine holds

### The install

`uv tool install ~/git/hands` puts `hands`, `handsd` and `handswho` in
`~/.local/bin` and the package in uv's tool environment
(`~/.local/share/uv/tools/hands/`). The package carries `hands/shipped/`: the
handbook, the templates, the role directories' `settings.json` and
`CLAUDE.md`, the Bash guard and the `handsd@.service` unit (`pyproject.toml`'s
force-include list). `hands handbook` prints the installed handbook's path,
`hands handbook --templates` the templates directory. **Regenerable**: install
again from the same commit. `hands --version` prints the package version,
which is the same for every build, so the commit that was installed is known
only if you note it (`git -C ~/git/hands rev-parse --short HEAD` at install
time).

### Each project's configuration

- `~/.hands/<project>.toml` — the config (DESIGN §13), mode 600 when `hands
  project add` wrote it. It holds the project's command secret (`[notify]
  cmd_secret`) and, with a self-hosted server, the notification token
  (`[notify] ntfy_token`). **Must-carry**: it is edited by hand.
- `~/.hands/<project>.cmd_secret` — the command secret alone, mode 600,
  written by `hands project add` beside the config. **Must-carry** (or
  regenerable together with the config's copy, §2).
- `~/.config/hands/<project>.env` — the unit's environment file (`KEY=value`
  lines; it may be empty and must exist). **Must-carry**: hands writes it
  empty, and whatever is in it was put there by hand.

Every `~/.hands/*.toml` is read as a project: `hands who` shows each, and one
that does not load is shown as a config error line. Other files under
`~/.hands/` are not hands'.

### The spool

`~/.hands/<project>/` is one daemon's runtime state (`hands.spool`, §29). The
series' state of record is not here: it is the project's branch on its
remote — the plan, the checkpoint, the journal, the findings, the reviews and
every applied kit as committed. The spool is what the daemon needs to carry on
where it stopped.

| Item | Class | What it is, and what losing it costs |
|---|---|---|
| `jobs/<id>.json` | must-carry | One record per job, written atomically and never pruned. Both consultation budgets count from these records; §6's owed limit resumes, the orphans owed to the playbook and the held jobs are read from them; `hands jobs` and `hands show` read them. |
| `jobs/<id>.stream.jsonl` | safe to drop | The job's captured stream-json. Only `hands log` reads it (and the capture script below). Losing it loses the log, nothing else. |
| `roles/<role>.json` | must-carry | The role's last session and last job, which `--context keep`, the phone's `answer` and `reply` resume, and §6's count of consecutive resumes against `max_resumes`. Lost: the count restarts at zero and a `keep` send is refused until a `clear` job records a session. A session is resumable only beside the harness session store it names (§1, "The harness sign-ins"). |
| `inbox.jsonl` | must-carry | The append-only event list. `hands inbox` and `hands wait --for` read it, and so does the engine: the head a consultation was sent at, and the last consultation, which the journal sentence names. |
| `inbox.acks.jsonl` | safe to drop | Ack markers. Lost: every event reads as unread again. |
| `pipeline.json` | must-carry | The engine's state: paused and the stop reason, the last rule fired, the run numbers `auto_runs` already used, every kickoff line seen, and the two anchors the consultation budgets count from. Lost: both counts restart and a run number the playbook lists can start on its own again ("A disaster", below). |
| `kits/<kit_id>/` | must-carry | A kit the architect role filed: `<name>.zip` and `kit.json` (its name, the job it was filed during, its sha256 and the check result). The engine approves an apply only while this record says the check passed and the zip still has its sha256; once the apply has run, the kit is a `plan: kit` commit on the branch and its directory is history. |
| `handsd.sock` | regenerable | The daemon's socket (the default `server.socket`). handsd binds it at start. |

A spool from before §29 sat directly under `~/.hands/`; `hands migrate-spool`
moves it (docs/INTEGRATION.md, "Two projects on one laptop").

### The user units and linger

- `~/.config/systemd/user/handsd@.service` — the templated daemon unit, from
  the install (`hands project add` copies it when it is not there) or from
  `systemd/` in the repository. **Regenerable.**
- `~/.config/systemd/user/handswho@.service` — the optional who unit, from
  `systemd/` in the repository only (the wheel does not carry it).
  **Regenerable.**
- The enabled instances, `handsd@<project>` and `handswho@<project>`, are the
  links under `~/.config/systemd/user/default.target.wants/`. `systemctl
  --user enable` makes them again.
- Each job runs in a transient scope `hands-<project>-<job>` when
  `systemd-run --user --scope` works here (`hands doctor`'s `isolation` row);
  nothing of it persists.

Linger is not set on the laptop (`loginctl show-user "$USER" -p Linger`
answers `Linger=no`), so the user units run while the user has a session and
stop with the last one. hands' code neither requires linger nor checks it;
`loginctl enable-linger "$USER"` would keep the daemons running with nobody
logged in.

### The role directories

`~/hands-driver/<project>/` and `~/hands-architect/<project>/`, as `hands
project add` writes them:

- `CLAUDE.md` — the role's instructions from the install, with the
  Parameters filled. **Must-carry**: the filled Parameters are the human's.
- `.claude/settings.json` and `.claude/hooks/bash_guard.py` — the shipped
  settings and guard. **Regenerable** from the install; `hands doctor`'s
  `driver` and `architect` rows compare the guard with the shipped one by
  sha256.
- `repo/` — a fetch-only clone of the project (push URL `no_push`).
  **Regenerable**: `git clone -- <url> repo` and `git -C repo remote set-url
  --push origin no_push`.
- `kits/` (the architect only; `HANDS_KITS` in its jobs) — the kit
  directories the role builds. **Safe to drop** once each was filed: `hands
  kit file` stores the zip in the spool's `kits/<kit_id>/`.

### The builder's clones

`[roles.builder] cwd` and `[roles.aux] cwd` — `~/git/<project>` in the
template — is the builder's own clone, the one it commits and pushes in, and
the one a review reads. Everything pushed is on the remote, so what must be
carried is only what is not: `git -C ~/git/<project> status`, `git -C
~/git/<project> stash list` and `git -C ~/git/<project> log --oneline @{u}..`
show it. During a mission the orchestrator's `meta/CHECKPOINT.md`,
`meta/plan.md` and `meta/journal.md` are dirty by design until its next `plan:`
or `journal:` commit. A review adds git worktrees under `/tmp`, registered in
the clone's `.git/worktrees/`; `hands doctor`'s `worktrees` row warns on one
whose directory is gone (H-067), and `git -C ~/git/<project> worktree prune`
drops it.

### The notification server

Not hands' code: the container of docs/INTEGRATION.md, "Self-hosted ntfy over
Tailscale", whose files are these on the laptop:

- `~/ntfy/etc/server.yml` — the server's config; its `base-url` is the
  address every config's `ntfy_url` names and the phone reaches.
  **Must-carry**, or written again from that section.
- `~/ntfy/cache/user.db` — the users, their access and their tokens; a secret
  (§2). Written by the container, owned by root.
- `~/ntfy/cache/cache.db` — the cached messages, including the text of every
  notification hands published. **Safe to drop**: the phone loses its history.
- `~/ntfy/cache/attachments/` — kits sent from the phone. **Safe to drop**
  once handsd has fetched each into `kit_dir`.

### The kit directory

`[files] kit_dir` (default `~/Downloads`; it must be inside `[files]
allowed_roots`): a kit sent from the phone is written here, and `hands kit
apply` copies its zip here; the held apply's prompt names the file there.
**Must-carry** while an apply from it is held or queued; **safe to drop**
after, since the applied kit is a commit on the branch.

### The harness sign-ins

Each harness keeps its login and its sessions in one directory
(docs/HARNESS-PROBE.md for the three probed on 2026-10-17):

- Claude Code: `~/.claude/`, or the `CLAUDE_CONFIG_DIR` a role's `[roles.<role>]
  env` sets. Its `projects/<dashed cwd>/<session>.jsonl` files are the
  transcripts the monitor reads and `--resume` follows; the job record's
  `transcript_path` names the one a job wrote (§40, H-063).
- Codex: `~/.codex/` (`CODEX_HOME`), sessions under `sessions/`.
- OpenCode: `~/.local/share/opencode/`, sessions in `opencode.db`.
- dsh: `$DSH_HOME`, default `~/.dsh`; not signed in on the laptop.

A credential profile (§40, implemented in M8b) is one such directory per
subscription; hands holds its path, never its contents. **Not carried**: a
sign-in is made again on the new machine (§2), and a session store left
behind means the first job of each role after a move is a `clear` one.

---

## 2. Secrets

One row per kind of secret the machinery or its sign-ins use. Modes are
those on the laptop, read with `stat -c %a`.

| Secret | Where it lives | Mode | How it is obtained again | Regenerable |
|---|---|---|---|---|
| The notification user's password | The notification server's user database; in plain form only where the human keeps it (on the laptop `~/.hands/ntfy.password`) and in the ntfy app if it signed in with it. hands never reads it. | 600 | `docker exec -it ntfy ntfy user change-pass hands` sets a new one; sign the app in again. | yes |
| The notification user's token | Each config's `[notify] ntfy_token`; on the laptop also `~/.hands/ntfy.token`; the ntfy app; the server's user database. | 600 | `docker exec ntfy ntfy token list hands` lists the user's tokens; `docker exec ntfy ntfy token add hands` makes a new one, which then goes into every config and the app, followed by `systemctl --user restart handsd@<project>` for each project. | yes |
| Each project's command secret | `~/.hands/<project>.toml` (`[notify] cmd_secret`) and `~/.hands/<project>.cmd_secret`. Typed on the phone; never published, logged or stored by hands anywhere else. | 600 | Read it from `~/.hands/<project>.cmd_secret`; or make a new one, write it into both files and restart `handsd@<project>`. | yes |
| The notification server's user database | `~/ntfy/cache/user.db`. | 644, owned by root | Copy the file with the container stopped; or create the user, its access and a token again (docs/INTEGRATION.md, step 2), after which the token and the password are new. | yes, by creating the user again; the token and the password change |
| Each harness sign-in, per profile | Claude Code `~/.claude/.credentials.json` (or under the profile's `CLAUDE_CONFIG_DIR`); Codex `~/.codex/auth.json` (`CODEX_HOME`); OpenCode `~/.local/share/opencode/auth.json`; dsh under `$DSH_HOME`. | 600 (dsh: not signed in) | Sign in again as the user handsd runs as: `claude`, then `/login`; `codex login`; `opencode auth login`; for a profile, with its directory variable set. | yes, by signing in again; hands never copies one |
| `gh`'s login | `~/.config/gh/hosts.yml`, or the system keyring (`gh auth status` says which). | 600 | `gh auth login --scopes repo` as the user handsd runs as. | yes |
| The git push credential | On the laptop `~/.gitconfig` names `gh auth git-credential` as the credential helper for github.com, so a push uses `gh`'s login; an SSH key under `~/.ssh/` would serve a `git@` remote, which no project's remote on the laptop is. | 664 for `~/.gitconfig`, which holds no secret | `gh auth setup-git` after `gh auth login`. | yes |
| The tailnet node | `/var/lib/tailscale/`, tailscaled's state with the node's key. | 700, owned by root | `sudo tailscale up` and sign in to the tailnet; a new machine is a new node (remove the old one in the tailnet's admin console). | yes |

Not secrets, though they are kept private: the topics on a server whose topics
require a token (on ntfy.sh a topic is only as private as its name), and the
environment files, unless something secret was put in one by hand.

---

## 3. Runbooks

### A usage-limit stop

**What it looks like** (`hands.runner`, `hands.limits`, `hands.playbook`). A
role job whose stream carries a `system`/`api_retry` event with the error
`rate_limit`, or whose final `result` reads as a limit notice
(`hands.limits.is_limit_notice`), ends `limited`, and its record's `limit` holds the category, the
raw notice and the reset time when one was parsed. hands then writes a `limit`
event (`reset_at`, and `resume_at` unless `max_resumes` is reached) and, for a
builder or aux job, schedules §6's resume at the reset plus one minute: a new
job of origin `limit` (a `resume` event) — the builder's as a `clear` send of
`resume_line`, else its own prompt. The playbook also sees `<role>.limited`;
the shipped playbooks carry no rule for it, so the engine stops ("the
playbook has no rule for it") and the stop's notification is what reaches the
phone. While the pipeline is stopped no rule fires on the resumed job's end.
After `max_resumes` consecutive resumes without a `done`, the stop says
`limits.max_resumes reached`. A consultation (driver or architect) that ends
limited is not resumed: the engine stops. An end at a limit the runner does
not recognise is `failed`, and its rule (or the lack of one) decides.

**Capture it** — the first real stop is the fixture M8b classifies against
(§40). From the hands repository, with or without the daemon up:

    bash scripts/capture-quota-stop.sh <project>          # the newest job
    bash scripts/capture-quota-stop.sh <project> <job>    # a named job

It writes `~/quota-capture-<project>-<time>.txt`, mode 600, and nothing else:
`hands status`, `hands jobs -n 5`, `hands pipeline`, the job record, the job's
stream-json tail and its lines about a limit, the tail of the transcript the
record names, the daemon journal's lines that name the job
(`journalctl --user -u handsd@<project>`) and the inbox's tail. A command that
fails is recorded with its exit status. Every command that reads (`hands`,
`journalctl`, `find`, `cat`, `tail`, `grep` and python's read of the job
record) runs under `timeout`, `HANDS_CAPTURE_TIMEOUT` seconds (default 30),
its process group killed 5 s later; one that times out is recorded as
`(failed: timed out after <n>s: <command>)` and the capture goes on. When the
`find` for the newest job or the record read times out, that line stands in
the file where "no job record" or "no transcript" would otherwise be, and
neither of those is written. Before anything is written it redacts
every project's command secret and notification token and the notification
user's token and password where the laptop keeps them, each by value (as
written, as JSON escapes it and URL-encoded), then keys and the
credentials of authorization headers by pattern. Redaction runs on the whole
collected text before any line is cut; only then is each line cut to 4000
bytes, so a secret across the cut is removed whole. Read the file before you
share it: a secret the script does not know of is not redacted.

**Then, today.** Wait for the reset (the `limit` event's `reset_at`, or the
notice in the record's `limit`). `hands status`: if §6's resume job is running
or queued, let it end. When no builder job is running, queued or held,
`hands go` sends the kickoff (the phone's `go <secret>` is the same); its job
un-pauses the pipeline when it starts, and the builder resumes from
`meta/CHECKPOINT.md`. A stopped consultation is the human's, as any
consultation stop is (docs/ARCHITECT-HANDBOOK.md §10).

**After M8b.** Sign in each credential profile once; the daemon marks a
profile exhausted at its limit and re-sends the job from its checkpoint on the
next profile of the role's list (§40). This section is rewritten then.

### No phone

Every phone command has a laptop form. The phone's command words are those of
`hands.phone` and, on `who_cmd_topic`, of `hands.who`.

| Phone | Laptop | Notes |
|---|---|---|
| `approve <job> <secret>`, or the Approve button | `hands approve <job>` | |
| `deny <job> [reason] <secret>`, or the Deny button | `hands deny <job> --reason "<reason>"` | |
| `pause <secret>` | `hands pause` | |
| `resume <secret>` | `hands resume` | |
| `status <secret>` | `hands status` | |
| `progress <secret>` | `hands jobs --role builder -n 1`, then `git -C <builder cwd> rev-parse --abbrev-ref HEAD`, `git -C <builder cwd> log --oneline -3` and `grep -m 1 -i 'unit in progress' meta/CHECKPOINT.md` at the repository's root | No single command; these read what `progress` reads. |
| `go <secret>` | `hands go` | Origin `cli`; refused while a builder job is running, queued or held, as the phone's is. |
| `kit <secret>`, with the zip attached | `hands kit apply <zip>`, then `hands approve <job>` | Checked as `hands kit check` checks, copied into `kit_dir`, filed as a held apply of origin `kit`. |
| `reply <secret> <text>` | none: `hands send --role architect` is refused (§27, §32) | `hands open <architect job>` resumes that session in a terminal (`claude --resume`, in the role's cwd); handsd records no job for it and the engine reads nothing from it. |
| `answer <secret> <text>` | `hands send --role builder --context keep "<text>"`, or `--prompt-file <file>` | Unlike `answer`, it passes §8's gate patterns: a text that matches one is held for `hands approve`. A file for the builder goes under `allowed_roots` first (`hands put`), named in the text. |
| `status`, `who`, `check` or `?` on `who_cmd_topic` | `hands who` | |

**The notification server's web page.** ntfy serves a web app at its
`base-url` (ntfy's documentation; hands neither uses nor checks it): open
`ntfy_url` in a browser on the tailnet, sign in as the notification user,
subscribe to the project's topics, and a message published to `cmd_topic`
there is a command as the app's is. On the laptop itself the container also
answers on the port it publishes (`docker port ntfy`).

### A planned migration

Until M9 this is done by hand. On the old machine:

1. `hands status`, for each project: move between jobs when you can. A stop
   kills every running job of the project (`orphaned`, resumed by the
   playbook's `<role>.orphaned` rules on the next start).
2. Push what is not pushed in each builder clone ("The builder's clones").
   The branch is the state of record.
3. `systemctl --user stop handsd@<project> handswho@<project>`, for each
   project.
4. Export by hand: `~/.hands/` (every config, `.cmd_secret` and spool),
   `~/.config/hands/` (the environment files), the role directories (their
   `CLAUDE.md` files are what matter), any kit in `kit_dir` whose apply is held
   or queued, and `~/ntfy/etc/server.yml`; to keep the notification user's
   token and password, also `~/ntfy/cache/user.db` with the container stopped
   (`sudo`: root owns it). For example:

       tar -C ~ -czpf ~/hands-move.tgz .hands .config/hands hands-driver hands-architect

   That archive holds the command secrets and the notification token. Keep it
   mode 600, move it over the tailnet or by hand, and delete it after. Not
   exported: the harness sign-ins and session stores, `gh`'s login and the
   tailnet node, which are made again.

**The secrets checklist** is §2's table, one row at a time: each is obtained
again on the new machine, in the order below.

On the new machine, in this order:

1. The tailnet: install Tailscale and `sudo tailscale up` (a new node; keep
   the hostname, so its MagicDNS name stays the same — the M9 step that
   addresses the server by that name relies on it).
2. The notification server: the container of docs/INTEGRATION.md with the
   restored `server.yml` and `user.db`, or a new user, access and token. A new
   node has a new tailnet address: if `base-url` and the configs' `ntfy_url`
   name the old one, change all of them, and the app's server entry.
3. `gh auth login --scopes repo`, then `gh auth setup-git`.
4. The harness sign-ins: `claude`, then `/login`; `codex login` if a role
   runs on it.
5. `uv tool install ~/git/hands` (after `git clone` of hands into
   `~/git/hands`), then `hands --version`.
6. `tar -C ~ -xzpf ~/hands-move.tgz`; `stat -c '%a %n' ~/.hands/*.toml
   ~/.hands/*.cmd_secret` should say 600 for each. An archive from a hands
   older than per-project spools (§29) holds the flat spool: `jobs/`,
   `roles/`, `inbox.jsonl`, `inbox.acks.jsonl` or `pipeline.json` directly
   under `~/.hands/`. Then run `hands migrate-spool` before any handsd starts:
   handsd refuses to start on the flat layout, and names that command. It
   moves the flat spool to `~/.hands/hands/`; rename the project's config to
   `hands.toml`, or move the directory to the project's name, as it says.
7. Each builder clone: `git clone -- <url> ~/git/<project>`, on the branch
   the series is on.
8. The units: `install -Dm644 ~/git/hands/systemd/handsd@.service
   ~/.config/systemd/user/handsd@.service` (and `handswho@.service` if you run
   it), `systemctl --user daemon-reload`, `systemctl --user enable
   handsd@<project>`.
9. `hands doctor` for each project, until no row fails; `hands notify --test`
   prints `ntfy 200`.
10. `systemctl --user start handsd@<project>`; the start notification reaches
    the phone and names any held job, republished with fresh buttons.
11. The builder's restored jobs, before any kickoff: `hands jobs --role
    builder -n 5`. `hands go` is refused while a builder job is running,
    queued or held, as the phone's `go` is. A held one (a kit's apply, or a
    send §8's gate held) is decided with `hands approve <job>` or `hands deny
    <job> --reason "<reason>"`; `hands cancel` refuses a held job. A running
    or queued one is the series carrying on (an orphaned builder the playbook
    resumed): it needs no kickoff.
12. Then, with no builder job running, queued or held: one
    kickoff, `hands go`, or `go <secret>` from the phone, which proves the
    phone's path as well. The first job of each role is `clear`, since the
    sessions stayed behind.

### A disaster

The machine, its disk or a spool is lost.

**What the branch holds.** Everything committed and pushed on the project's
branch: the design, the brief, the plan and the checkpoint as last committed,
the journal, the findings, the reviews and final reports, the playbook, and
every applied kit as its `plan: kit` commit. A builder started with `hands go`
reads the checkpoint and recovers by the brief's §R. That is the whole of the
series; the spool is only the daemon's bookkeeping about it.

**What the unit in progress loses.** Whatever was not pushed: the builder's
uncommitted edits and unpushed commits, its harness session, and the
orchestrator's checkpoint, plan and journal lines since its last commit of
`meta/`. The unit is redone from the last pushed checkpoint.

**When the machine survived** (a crash, a power cut), the next handsd start
does the recovery itself: a job recorded running whose process is gone is
recorded `orphaned` and fed to the playbook once as `<role>.orphaned` (the
shipped playbooks resume a builder and a review, bounded by `max_resumes`; an
orphaned consultation stops); a queued job is run; an owed limit resume is
scheduled again; every held job is published again with fresh buttons.

**Re-filing a kit that was in flight.** An apply that was held when the spool
was lost is gone with it; the kit is not. Take its zip from `kit_dir`, from
the spool's `kits/<kit_id>/<name>.zip` if that survived, or build it from the
architect's `kits/<name>/` directory (`cd ~/hands-architect/<project>/kits/<name>
&& zip -r -D ../<name>.zip .`). Then `hands kit check <zip> --repo
~/git/<project>`, `hands kit apply <zip>`, and `hands approve <job>`. A kit
filed this way has origin `kit`, not `architect`, so under `autonomous` the
engine does not approve it on its own: the human does.

**Re-firing a review that was in flight.** With the spool, the review's
`aux.orphaned` rule resumes it on the next start. Without it, send the review
again: the prompt is the `builder.done` rule's `prompt` in the project's
`PLAYBOOK.toml`, with the mission's number in place of `{n}`, written to a
file under `allowed_roots`, and `hands send --role aux --context clear
--prompt-file <file>`. Its end fires the `aux.done` rules as any review's does.

**The consultation budgets' count of record** is the job records in `jobs/`
read against the two anchors in `pipeline.json` (`hands.playbook`):
`max_consults` counts the driver jobs, not resumes, after the later of the
last kickoff, the last kit apply that ran and the daemon start in
`consults_since`; `max_architect_consults` counts the architect jobs, not
resumes nor replies, after the job in `series_since`. With `pipeline.json`
lost, the next daemon start becomes the new `consults_since` and the next load
takes a new `series_since`, so both counts restart from zero; with `jobs/` lost
they restart too. hands has no command that restores a count: to keep the
budget, lower the playbook's limits by what was already spent, in a kit.
`auto_runs` is in the same file: the run numbers already used are forgotten
with it.

### A release install

The routine after a clean review (meta/ROADMAP.md: "an install
(`uv tool install --force`) and a driver-kit refresh"), each step a command.
M9 makes it one command; until then:

1. `hands status`, for each project: a restart kills running jobs. A builder
   job killed this way is re-sent by the playbook's `builder.orphaned` rule
   (H-047), a review by `aux.orphaned`.
2. `git -C ~/git/hands rev-parse --short HEAD` (note the installed commit),
   then `git -C ~/git/hands checkout main` and `git -C ~/git/hands pull
   --ff-only`.
3. `uv tool install --force ~/git/hands`, then `hands --version`.
4. `hands handbook`: the installed handbook's path; its directory's parent,
   `.../hands/shipped`, is `<shipped>` below.
5. The role-kit refresh, for each project:
   `cp <shipped>/driver/settings.json ~/hands-driver/<project>/.claude/settings.json`,
   `cp <shipped>/bash_guard.py ~/hands-driver/<project>/.claude/hooks/bash_guard.py`,
   `cp <shipped>/architect/settings.json ~/hands-architect/<project>/.claude/settings.json`,
   `cp <shipped>/bash_guard.py ~/hands-architect/<project>/.claude/hooks/bash_guard.py`;
   then `diff <shipped>/driver/CLAUDE.md ~/hands-driver/<project>/CLAUDE.md`
   and `diff <shipped>/architect/CLAUDE.md ~/hands-architect/<project>/CLAUDE.md`,
   carrying each change by hand and keeping the filled Parameters.
6. `diff <shipped>/systemd/handsd@.service ~/.config/systemd/user/handsd@.service`;
   when they differ, `install -Dm644 <shipped>/systemd/handsd@.service
   ~/.config/systemd/user/handsd@.service` and `systemctl --user
   daemon-reload`.
7. `systemctl --user restart handsd@<project>`, and `handswho@<project>` if it
   runs, for each project.
8. `hands doctor` for each project: the `driver` and `architect` rows compare
   each guard with the shipped one.
9. `git -C ~/git/hands diff --stat <installed commit>..HEAD --
   docs/ARCHITECT-INSTRUCTION.md`: when it lists the file, paste the new
   instruction into each project's Claude Project and ask it "What are your
   Parameters?" (docs/ARCHITECT-INSTRUCTION.md rule 13).
10. The next kickoff waits for `go`, unless step 1's restart re-sent a builder.
