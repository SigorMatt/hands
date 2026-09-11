# Integration — putting hands on the laptop

DESIGN §14, as a checklist. Do it once per machine (steps 1–2), then once per
project (steps 3–8). Every command here was run against the CLI in this repo;
where something has never been proven, it says so.

Nothing in hands is a background daemon you have to trust blindly: `hands
doctor` is the check, and `hands status`, `hands pipeline` and `hands inbox`
are the whole of its state.

---

## 1. Install (once per machine)

    uv tool install ~/git/hands        # -> "Installed 2 executables: hands, handsd"

`~/.local/bin` must be on your PATH (`uv tool update-shell` adds it). Check:

    hands --version
    handsd --version

Python ≥ 3.11 and `uv`. The only runtime dependency is `httpx`, for ntfy.

## 2. Run handsd (once per machine, per project)

    install -Dm644 ~/git/hands/systemd/handsd.service ~/.config/systemd/user/handsd.service
    printf 'HANDS_PROJECT=<project>\n' > ~/.config/hands.env
    systemctl --user daemon-reload
    systemctl --user enable --now handsd
    journalctl --user -u handsd -f

The unit is a **user** unit — hands spawns `claude -p` as you, with your
subscription login and your `~/.claude` settings — and it takes the project
from the environment file, never from a login shell. `Restart=on-failure`;
`ExecStart` is the absolute `%h/.local/bin/handsd` because a unit has no PATH
from your shell. For a second project, copy the unit to
`handsd-<project>.service` with its own `EnvironmentFile`, and give each
project's config a different `server.socket`.

Without systemd, `handsd --project <project>` in a terminal is the same thing.

## 3. Write the config (§14 step 1)

`~/.hands/<project>.toml`. Every key below is read by `src/hands/config.py`;
an unknown key or section is refused, and everything except `[roles.builder]
cwd` is optional.

    [server]
    socket = "~/.hands/handsd.sock"      # default
    ntfy_topic = "hands-<something-random>"
    ntfy_url = "https://ntfy.sh"         # default

    [roles.builder]
    cwd = "~/git/<project>"              # required; the only required key
    model = "opus"                       # default
    permission_flags = "--dangerously-skip-permissions"
    resume_line = "Resume WORKPLAN.md"   # optional, no default: sent on a limit
                                         # resume (§6). Leave it out and a limit
                                         # resume re-sends the limited prompt.
                                         # `resume_line = ""` (or blanks only) is
                                         # refused at load: an empty line is no
                                         # prompt, and it would silently mean the
                                         # other behaviour. Omit the key, or give
                                         # a non-empty line
    queue_depth = 1                      # capacity: how many jobs may wait
    cancel_gated = true                  # default

    [roles.aux]
    cwd = "~/git/<project>"
    queue_depth = 4                      # default for aux (builder 1); `hands
                                         # status` reports it as queue_capacity too

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

    [gates]
    patterns = ["...", "..."]            # added to the defaults, never replacing them

    [runner]
    claude = "claude"                    # default; an absolute path also works
    cancel_grace_s = 20                  # default: SIGINT, wait, SIGTERM (§2)

Notes that are easy to get wrong:

- `files.allowed_roots` defaults to exactly the role working directories.
  `hands put/get/ls` can reach nothing else, so `~/Downloads` must be listed
  if the plan kit lands there.
- `gates.patterns` is a **union** with the defaults (`Apply ~/Downloads/`,
  `decisions-`, `playbook-`, `gh pr create`, `open the PR`). A config can only
  widen the gate, never disable it (§8).
- `roles` are exactly `builder` and `aux`; `[roles.builder]` is required.

## 4. `hands doctor` (§14 step 1)

    hands --project <project> doctor

It checks, all for free: the config, the `claude` binary and its `--version`,
each role's `cwd` (and whether it is a git repository), the allowed roots, the
ops script's flags, the playbook, and whether handsd is answering. A daemon
that is not running is a **warning**, not a failure — this step comes before
you have to have started one. Exit code 1 means a check failed.

    hands doctor --live       # also runs ONE real `claude -p` turn per role

`--live` is the only thing in hands that spends your subscription, so it is
opt-in, and `HANDS_DOCTOR_FAKE=1` refuses it (that is how the test suite runs
doctor without a real binary). `hands doctor --json` prints the same report as
data.

Doctor checks that a topic is *configured*; it never sends anything. The proof
of delivery is one command, and it needs no daemon either:

    hands notify --test "ping from the laptop"
    hands notify --test                   # the same, with a default line

It publishes one message to `server.ntfy_topic` through the same transport
§11's `stop` and `job.held` notifications use, and prints the HTTP status ntfy
answered with. With no `ntfy_topic` set, or if the publish failed, it says so
and exits 1. Quiet hours do not delay it: §11 delays notifications, never
actions, and a message you asked for at a terminal is an action.

Doctor also prints the **background-wake check** of §11 — the one check hands
cannot run itself, because it needs an idle interactive session. Run it by
hand after step 5; the procedure is in doctor's own output.

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

## 6. The architect (§14 step 3)

Replace the Claude Project's instruction with `docs/ARCHITECT-INSTRUCTION.md`.
Its outputs are files for the repo; it never sends prompts to paste.

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
- Every builder run prompt and aux review prompt must require the reply's
  first line to begin with `VERDICT:` in the playbook's vocabulary.
- Retire: the status+arm aux prompt, the `~/Downloads` relay of prompts (files
  still land there), and the "name the session and say clear context"
  preference — `hands send --context clear|keep` is the enforcement now.

---

## First run, end to end

    hands status                                  # daemon, roles, monitor
    hands send --role aux --context clear "Reply with: VERDICT: hello"
    hands wait <job> --timeout 300
    hands show <job>                              # the record; `result` verbatim
    hands jobs -n 5
    hands inbox --ack

Then arm the wake path the way the driver does:

    hands wait --for stop,held --timeout 3600     # exits 2 on timeout, 0 on an event

## What is not proven

- **No real `claude` has ever run under hands.** Every test runs against
  `tests/fake_claude.py`. `hands doctor --live` is the first real turn, and it
  has not been run in this repo.
- The ops-script bridge has only ever been exercised against
  `tests/fake_monitor.py`; no real `watch_monitor.sh` with the three flags
  exists yet (§14 step 4 is the work that creates it).
- Whether a finished background Bash task wakes an idle interactive Claude
  Code session (§11, §16) is **open**. Run the procedure `hands doctor` prints
  and record the answer; §11's fallback is a long-timeout `hands wait` re-armed
  by the driver, plus the ntfy notification.
- ntfy delivery has only been driven through a recording transport in the
  tests (`tests/test_wake.py`); no request has ever left the machine. `hands
  notify --test` is the command that proves it, and running it once at an
  install is the first proof there has ever been.
