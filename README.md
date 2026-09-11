# hands

Hands for the brain: a user daemon and a CLI that dispatch prompts to headless
Claude Code roles (`builder`, `aux`), monitor them from outside, and chain
pre-planned steps by a playbook, so a planned series moves without a human
relay.

It replaces the relay, not the judgment: routing prompts to a named role with
an explicit clear/keep, moving files onto the machine, returning replies
verbatim, watching for stalls and commit tripwires, waiting out a rate limit
and resuming, and running the steps you approved in advance. Everything that
needs a decision — verdicts, scope, vetoes, decisions files, playbooks, PRs —
stops and waits for you.

`DESIGN.md` is the specification and the reasoning. `docs/INTEGRATION.md` is
the install checklist; `docs/PLAYBOOK.md` is the playbook reference;
`driver/` is the kit for the Claude Code session that drives hands from your
phone.

## Shape

    architect (a Claude Project)  ── files in the repo ──►  laptop
                                                              │
    driver (a Claude Code session, own dir, remote control on) │
        │  Bash: hands <command>
        ▼
    handsd (user daemon, unix socket ~/.hands/handsd.sock)
        ├─ runner    one `claude -p` per job, one job per role
        ├─ monitor   liveness, stalls, commit tripwires
        ├─ playbook  event → action, entirely pre-planned
        ├─ spool     job records, role state, inbox — the only state
        └─ notify    ntfy, for the four things that need you

The core never opens a port: the CLI talks to the daemon over a unix socket in
your home directory.

## Install

Needs Python ≥ 3.11 and [uv](https://docs.astral.sh/uv/). The only runtime
dependency is `httpx`.

    uv tool install ~/git/hands      # installs 2 executables: hands, handsd

Run the daemon under systemd (user unit; the project name comes from an
environment file):

    install -Dm644 ~/git/hands/systemd/handsd.service ~/.config/systemd/user/handsd.service
    printf 'HANDS_PROJECT=<project>\n' > ~/.config/hands.env
    systemctl --user daemon-reload
    systemctl --user enable --now handsd

or just `handsd --project <project>` in a terminal.

## First run

Write `~/.hands/<project>.toml` (every key is listed in
`docs/INTEGRATION.md` §3; only `[roles.builder] cwd` is required):

    [server]
    ntfy_topic = "hands-<something-random>"

    [roles.builder]
    cwd = "~/git/<project>"
    permission_flags = "--dangerously-skip-permissions"

    [roles.aux]
    cwd = "~/git/<project>"

Then check the install and send one prompt:

    hands doctor                                   # every check but the live turn is free
    hands notify --test "ping from the laptop"     # one real ntfy message + the status, 2xx or not
    hands status
    hands send --role aux --context clear "Reply with: VERDICT: hello"
    hands wait <job> --timeout 300
    hands show <job>

`hands doctor` also prints the one check it cannot run itself: the §11
background-wake procedure, for you to run from the driver session.

## The command surface

`send`, `wait`, `result`, `jobs`, `show`, `open`, `log`, `cancel`, `put`,
`get`, `ls`, `tail`, `inbox`, `pipeline`, `approve`, `deny`, `pause`,
`resume`, `status`, `notify`, `doctor`. Every one takes `--json` (that is what the driver
reads) and `--project`. `hands --help` is the reference; `handsd --help` is the
daemon's.

Three commands are worth knowing before the rest:

    hands send --role builder --context clear "Execute WORKPLAN.md run 2"
    hands wait --for stop,held --timeout 3600   # the driver's wake path (§11)
    hands approve <job> --human-confirmed --quote "<your own words>"

A gated send (decisions files, playbooks, PR opening, cancels, and anything
matching `gates.patterns`) is *held* until a human decides it. Nothing else
releases it.

## Development

    ./scripts/check        # ruff, pytest, a CLI smoke test — green before every commit

No test may run a real `claude`, spend quota, or touch the network:
`tests/fake_claude.py` stands in for the binary and `tests/fake_monitor.py` for
the ops script.

## Status

The core is built and tested against the stand-ins. **No real `claude` has ever
run under hands**, no real `watch_monitor.sh` has been driven, and no ntfy
request has left the machine (`hands notify --test` is the command that
changes that, and it has not been run here); `docs/INTEGRATION.md` ends with the full list of
what is unproven. Whether a finished background task wakes an idle interactive
Claude Code session (DESIGN §11, §16) is still an open question — `hands
doctor` prints the procedure that answers it.
