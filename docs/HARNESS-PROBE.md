# The harness probe (DESIGN §40), 2026-10-17

A dated record, not a design. Mission 24 U1 ran it on the laptop from
2026-10-17 02:01 to 02:20 (+03:00) to give §41 its evidence. Everything below
was observed on that machine at those versions. Every command and its output
are quoted verbatim. Keys, tokens and sign-in contents are `[redacted]`. The
probe neither read nor printed a credential file, so nothing had to be
redacted. The probe installed nothing.

## Setup

The probe used a scratch repository with one commit and one file. It never
ran in a project tree.

```text
$ S=/tmp/hands-probe-20261017020149; mkdir -p $S && cd $S && git init -q && echo "# probe scratch" > README.md && git add README.md && git -c user.name=probe -c user.email=probe@localhost commit -qm "probe: scratch" && git log --oneline
377e4f6 probe: scratch
```

Every harness command ran in the foreground under `timeout`, with cwd set to
that scratch repository and this PATH prefix:
`PATH=$HOME/.nvm/versions/node/v22.23.3/bin:$PATH`.

The task was the same for every harness:

> create a file `probe.txt` containing the word ok and commit nothing; your reply's first line must be exactly `VERDICT: probe ok`

### Versions

```text
$ codex --version
codex-cli 0.163.0
$ opencode --version
1.19.2
$ dsh --version
0.2.0-rc.2
$ node --version
v22.23.3
$ claude --version
2.1.300 (Claude Code)
$ which codex opencode dsh node claude
/home/msi/.nvm/versions/node/v22.23.3/bin/codex
/home/msi/.nvm/versions/node/v22.23.3/bin/opencode
/home/msi/.nvm/versions/node/v22.23.3/bin/dsh
/home/msi/.nvm/versions/node/v22.23.3/bin/node
/home/msi/.local/bin/claude
```

### Sign-in state (provider name only)

```text
$ timeout 60 codex login status
Logged in using ChatGPT
$ timeout 60 opencode auth list        # ANSI colour codes stripped
┌  Credentials ~/.local/share/opencode/auth.json
│
●  Nebius Token Factory api
│
└  1 credentials
$ if [ -n "${DEEPSEEK_API_KEY+x}" ]; then echo "DEEPSEEK_API_KEY set"; else echo "DEEPSEEK_API_KEY unset"; fi
DEEPSEEK_API_KEY unset
$ ls -la ~/.dsh ~/.config/dsh
ls: cannot access '/home/msi/.dsh': No such file or directory
ls: cannot access '/home/msi/.config/dsh': No such file or directory
```

The sign-in states were:

- **Codex** is signed in with ChatGPT.
- **OpenCode** has one credential, for the provider Nebius Token Factory (an
  API key, `[redacted]`, which the probe did not read). No default model is
  configured, so OpenCode is `unavailable: no model configured`; see its
  section.
- **dsh** is `unavailable: not signed in`. `DEEPSEEK_API_KEY` is unset,
  `DSH_HOME` is unset, and the default home `~/.dsh`, which would hold the
  credential store, does not exist. The probe did not run `dsh --profile
  headless`, because on first use that command creates `~/.dsh` from shipped
  templates (dsh README.md line 20).

## Codex (`@openai/codex` 0.163.0): available

Sources: `codex exec --help`, `codex exec resume --help`, `codex --help`,
`codex sandbox --help`, `codex features list`, and the strings of the installed
binary at
`~/.nvm/versions/node/v22.23.3/lib/node_modules/@openai/codex/node_modules/@openai/codex-linux-x64/vendor/x86_64-unknown-linux-musl/bin/codex`.
The package ships only a README with no docs directory. The docs it links to
are online, and the probe did not fetch them.

### The sandbox on this laptop (observed before the one-shot)

`codex exec --sandbox` offers `read-only`, `workspace-write` and
`danger-full-access`. On this laptop the first two do not start. The kernel
has `kernel.apparmor_restrict_unprivileged_userns = 1`, and Codex runs its own
bundled `codex-resources/bwrap`:

```text
$ timeout 60 codex sandbox -- touch sbx-a </dev/null; echo "exit=$?"
bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted
exit=1
$ timeout 60 codex sandbox -c sandbox_mode='"workspace-write"' -- touch sbx-b </dev/null; echo "exit=$?"
bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted
exit=1
$ timeout 60 codex sandbox -c sandbox_mode='"workspace-write"' -c sandbox_workspace_write.network_access=true -- touch sbx-c </dev/null; echo "exit=$?"
bwrap: setting up uid map: Permission denied
exit=1
$ timeout 60 codex sandbox --enable use_legacy_landlock -c sandbox_mode='"workspace-write"' -- touch sbx-d </dev/null; echo "exit=$?"

thread 'main' (1208807) panicked at linux-sandbox/src/linux_run_main.rs:416:9:
filesystem-restricted execution requires bubblewrap to isolate app-server sockets
note: run with `RUST_BACKTRACE=1` environment variable to display a backtrace
exit=101
```

`codex features list` reports `use_legacy_landlock  deprecated  false`. So the
most restrictive sandbox that still lets the task write in the working
directory is, on this laptop, `danger-full-access`, which means no sandbox.
The probe ran the task under both `workspace-write` and `danger-full-access`.

### One-shot headless command, exit status, event stream

Under `workspace-write`, the run below used a stdin that was still open. Later
runs passed `</dev/null`, and Codex printed `Reading additional input from
stdin...` on stderr either way.

```text
$ timeout 300 codex exec --json --sandbox workspace-write 'create a file `probe.txt` containing the word ok and commit nothing; your reply'"'"'s first line must be exactly `VERDICT: probe ok`'
exit=0
--- stderr
Reading additional input from stdin...
2026-10-16T23:03:01.251155Z ERROR codex_core::tools::router: error=Exit code: 1
Wall time: 0.1 seconds
Output:
Failed to write file /tmp/hands-probe-20261017020149/probe.txt

--- stdout (7 lines; the first five and the last five overlap, so all are shown)
{"type":"thread.started","thread_id":"01a146f4-3330-7871-8f49-32a7f65f41bf"}
{"type":"turn.started"}
{"type":"item.completed","item":{"id":"item_0","type":"agent_message","text":"I’ll create `probe.txt` containing `ok` and leave it uncommitted.\n"}}
{"type":"item.started","item":{"id":"item_1","type":"file_change","changes":[{"path":"/tmp/hands-probe-20261017020149/probe.txt","kind":"add"}],"status":"in_progress"}}
{"type":"item.completed","item":{"id":"item_1","type":"file_change","changes":[{"path":"/tmp/hands-probe-20261017020149/probe.txt","kind":"add"}],"status":"failed"}}
{"type":"item.completed","item":{"id":"item_2","type":"agent_message","text":"VERDICT: probe ok\nCouldn’t create `probe.txt`: the environment blocked both write attempts. Nothing was committed."}}
{"type":"turn.completed","usage":{"input_tokens":43632,"cached_input_tokens":40832,"cache_write_input_tokens":0,"output_tokens":133,"reasoning_output_tokens":0}}
$ ls; cat probe.txt
README.md
cat: probe.txt: No such file or directory
```

Under `danger-full-access`:

```text
$ timeout 300 codex exec --json --sandbox danger-full-access 'create a file `probe.txt` containing the word ok and commit nothing; your reply'"'"'s first line must be exactly `VERDICT: probe ok`' </dev/null
exit=0
--- stderr
Reading additional input from stdin...
--- stdout (7 lines; all shown)
{"type":"thread.started","thread_id":"01a146f5-65ba-7c33-8b33-9a0626db5ad9"}
{"type":"turn.started"}
{"type":"item.completed","item":{"id":"item_0","type":"agent_message","text":"I’ll create `probe.txt` containing `ok` without making a commit.\n"}}
{"type":"item.started","item":{"id":"item_1","type":"command_execution","command":"/bin/bash -lc \"printf 'ok' > probe.txt\"","aggregated_output":"","exit_code":null,"status":"in_progress"}}
{"type":"item.completed","item":{"id":"item_1","type":"command_execution","command":"/bin/bash -lc \"printf 'ok' > probe.txt\"","aggregated_output":"","exit_code":0,"status":"completed"}}
{"type":"item.completed","item":{"id":"item_2","type":"agent_message","text":"VERDICT: probe ok\nCreated `probe.txt` containing `ok`. No commit made."}}
{"type":"turn.completed","usage":{"input_tokens":28527,"cached_input_tokens":26368,"cache_write_input_tokens":0,"output_tokens":79,"reasoning_output_tokens":0}}
$ ls; cat probe.txt; git status --short; git log --oneline
probe.txt
README.md
ok?? probe.txt
377e4f6 probe: scratch
```

The streams show these shapes:

- **A tool call** is an `item.started` / `item.completed` pair with
  `item.type` `command_execution` (`command`, `aggregated_output`,
  `exit_code`, `status`) or `file_change` (`changes[].path`,
  `changes[].kind`, `status`).
- **The final message** is the last `item.completed` with `item.type`
  `agent_message`, and the stream closes with `turn.completed`, which carries
  `usage`.
- **The session id** is `thread.started.thread_id`.

### VERDICT

The final message's first line was quoted verbatim, the same in both runs:

```text
VERDICT: probe ok
```

It matches `VERDICT: probe ok` exactly in both runs. Under `workspace-write`
the model printed that line even though the write had failed. Its second line
says so.

### Resume

```text
$ timeout 300 codex exec resume --json -c sandbox_mode='"danger-full-access"' 01a146f5-65ba-7c33-8b33-9a0626db5ad9 'what did you create?' </dev/null
exit=0
--- stderr
(empty)
--- stdout (4 lines; all shown)
{"type":"thread.started","thread_id":"01a146f5-65ba-7c33-8b33-9a0626db5ad9"}
{"type":"turn.started"}
{"type":"item.completed","item":{"id":"item_0","type":"agent_message","text":"I created `probe.txt` containing exactly `ok`. No commit was made."}}
{"type":"turn.completed","usage":{"input_tokens":43815,"cached_input_tokens":40448,"cache_write_input_tokens":0,"output_tokens":99,"reasoning_output_tokens":0}}
```

The answer names the file. `codex exec resume` has no `--sandbox` flag, so the
sandbox is passed as `-c sandbox_mode=…`. `--last` picks the newest session,
filtered by cwd unless `--all` is given.

### Session store

```text
$ ls ~/.codex                           # (reflowed; auth.json was not opened)
auth.json (not read)  cache  config.toml  goals_1.sqlite  installation_id  log  logs_2.sqlite
memories_1.sqlite  models_cache.json  plugins  queue_1.sqlite  sessions  shell_snapshots  skills
state_5.sqlite  thread_history_1.sqlite  thread-writer-locks  tmp
$ grep -rl 01a146f5-65ba-7c33-8b33-9a0626db5ad9 ~/.codex/sessions
~/.codex/sessions/2026/10/17/rollout-2026-10-17T02-04-09-01a146f5-65ba-7c33-8b33-9a0626db5ad9.jsonl
```

The session file is JSONL, 36 records after the two turns above. The probe
recorded keys and types only:

- **The first record** is `type` `session_meta`, with keys `['ordinal',
  'payload', 'timestamp', 'type']`.
- **Its payload** has keys `['base_instructions', 'cli_version',
  'context_window', 'creator_account_id', 'creator_user_id', 'cwd', 'git',
  'history_mode', 'id', 'model_provider', 'originator',
  'runtime_workspace_roots', 'session_id', 'source', 'thread_source',
  'timestamp']`.
- **Record types and payload types**, with counts:

```text
('event_msg', 'item_completed') 6
('event_msg', 'task_complete') 2
('event_msg', 'task_started') 2
('event_msg', 'thread_settings_applied') 3
('event_msg', 'token_count') 3
('response_item', 'custom_tool_call') 1
('response_item', 'custom_tool_call_output') 1
('response_item', 'message') 10
('session_meta', None) 1
('token_usage_record', None) 3
('turn_context', None) 2
('world_state', None) 2
```

`CODEX_HOME` moves this store (§40 credential profiles), and `--ephemeral`
runs without writing session files (`codex exec --help`).

### Shell commands outside the working directory and `curl`

`/tmp/outside-probe` did not exist before each run. After each run the probe
checked it and then removed it.

```text
$ timeout 300 codex exec --json --sandbox workspace-write 'run the shell command `touch /tmp/outside-probe` and report exactly what happened' </dev/null
exit=0
{"type":"thread.started","thread_id":"01a146f5-df55-78b1-999c-36c30f30458f"}
{"type":"turn.started"}
{"type":"item.completed","item":{"id":"item_0","type":"agent_message","text":"I’ll run the command and report the result."}}
{"type":"item.completed","item":{"id":"item_1","type":"agent_message","text":"The command failed with exit code 1:\n\n```text\nbwrap: loopback: Failed RTM_NEWADDR: Operation not permitted\n```\n\nThe sandbox failed to start, so `touch` did not run."}}
{"type":"turn.completed","usage":{"input_tokens":28919,"cached_input_tokens":26496,"cache_write_input_tokens":0,"output_tokens":103,"reasoning_output_tokens":0}}
$ ls -la /tmp/outside-probe
ls: cannot access '/tmp/outside-probe': No such file or directory

$ timeout 300 codex exec --json --sandbox workspace-write 'run the shell command `curl --version` and report exactly what happened' </dev/null
exit=0
{"type":"thread.started","thread_id":"01a146f5-fb31-76f0-b3ee-0cb327fd5e54"}
{"type":"turn.started"}
{"type":"item.completed","item":{"id":"item_0","type":"agent_message","text":"I’ll run `curl --version` and report the output and exit status."}}
{"type":"item.completed","item":{"id":"item_1","type":"agent_message","text":"The command failed with exit code `1`. Output:\n\n```text\nbwrap: loopback: Failed RTM_NEWADDR: Operation not permitted\n```\n\nNo curl version information was returned."}}
{"type":"turn.completed","usage":{"input_tokens":29859,"cached_input_tokens":27008,"cache_write_input_tokens":0,"output_tokens":100,"reasoning_output_tokens":0}}

$ timeout 300 codex exec --json --sandbox danger-full-access 'run the shell command `touch /tmp/outside-probe` and report exactly what happened' </dev/null
exit=0
{"type":"thread.started","thread_id":"01a146f6-1782-76e1-ac0f-f709540ccb0e"}
{"type":"turn.started"}
{"type":"item.completed","item":{"id":"item_0","type":"agent_message","text":"I’ll run the command and report the result."}}
{"type":"item.started","item":{"id":"item_1","type":"command_execution","command":"/bin/bash -lc 'touch /tmp/outside-probe'","aggregated_output":"","exit_code":null,"status":"in_progress"}}
{"type":"item.completed","item":{"id":"item_1","type":"command_execution","command":"/bin/bash -lc 'touch /tmp/outside-probe'","aggregated_output":"","exit_code":0,"status":"completed"}}
{"type":"item.completed","item":{"id":"item_2","type":"agent_message","text":"Ran `touch /tmp/outside-probe`. It exited with code `0` and produced no output."}}
{"type":"turn.completed","usage":{"input_tokens":29444,"cached_input_tokens":26752,"cache_write_input_tokens":0,"output_tokens":76,"reasoning_output_tokens":0}}
$ ls -la /tmp/outside-probe
-rw-rw-r-- 1 msi msi 0 Oct 17 02:04 /tmp/outside-probe
$ rm -f /tmp/outside-probe

$ timeout 300 codex exec --json --sandbox danger-full-access 'run the shell command `curl --version` and report exactly what happened' </dev/null
exit=0
{"type":"thread.started","thread_id":"01a146f6-34ad-7730-a169-6e3abcfabead"}
{"type":"turn.started"}
{"type":"item.completed","item":{"id":"item_0","type":"agent_message","text":"I’ll run `curl --version` and report the output and exit status."}}
{"type":"item.started","item":{"id":"item_1","type":"command_execution","command":"/bin/bash -lc 'curl --version'","aggregated_output":"","exit_code":null,"status":"in_progress"}}
{"type":"item.completed","item":{"id":"item_1","type":"command_execution","command":"/bin/bash -lc 'curl --version'","aggregated_output":"curl 8.5.0 (x86_64-pc-linux-gnu) libcurl/8.5.0 OpenSSL/3.0.13 zlib/1.3 brotli/1.1.0 zstd/1.5.5 libidn2/2.3.7 libpsl/0.21.2 (+libidn2/2.3.7) libssh/0.10.6/openssl/zlib nghttp2/1.59.0 librtmp/2.3 OpenLDAP/2.6.10\nRelease-Date: 2023-12-06, security patched: 8.5.0-2ubuntu10.16\nProtocols: dict file ftp ftps gopher gophers http https imap imaps ldap ldaps mqtt pop3 pop3s rtmp rtsp scp sftp smb smbs smtp smtps telnet tftp\nFeatures: alt-svc AsynchDNS brotli GSS-API HSTS HTTP2 HTTPS-proxy IDN IPv6 Kerberos Largefile libz NTLM PSL SPNEGO SSL threadsafe TLS-SRP UnixSockets zstd\n","exit_code":0,"status":"completed"}}
{"type":"item.completed","item":{"id":"item_2","type":"agent_message","text":"`curl --version` completed successfully with exit code `0` and printed:\n\n```text\ncurl 8.5.0 (x86_64-pc-linux-gnu) libcurl/8.5.0 OpenSSL/3.0.13 zlib/1.3 brotli/1.1.0 zstd/1.5.5 libidn2/2.3.7 libpsl/0.21.2 (+libidn2/2.3.7) libssh/0.10.6/openssl/zlib nghttp2/1.59.0 librtmp/2.3 OpenLDAP/2.6.10\nRelease-Date: 2023-12-06, security patched: 8.5.0-2ubuntu10.16\nProtocols: dict file ftp ftps gopher gophers http https imap imaps ldap ldaps mqtt pop3 pop3s rtmp rtsp scp sftp smb smbs smtp smtps telnet tftp\nFeatures: alt-svc AsynchDNS brotli GSS-API HSTS HTTP2 HTTPS-proxy IDN IPv6 Kerberos Largefile libz NTLM PSL SPNEGO SSL threadsafe TLS-SRP UnixSockets zstd\n```"}}
{"type":"turn.completed","usage":{"input_tokens":28741,"cached_input_tokens":26240,"cache_write_input_tokens":0,"output_tokens":328,"reasoning_output_tokens":0}}
```

**`workspace-write`.** Both commands were stopped, but by the sandbox failing
to start, not by a policy refusal. The harness never asked; `codex exec` asks
no questions. Note also that the stream carried no `command_execution` item
for these two attempts: the failure appears only in the agent's own message.

**`danger-full-access`.** Both commands ran without being asked about. The
write outside the working directory happened.

The probe did not pass an approval policy. `codex exec` has no `-a` flag. The
top-level `codex -a` takes `on-request`, or `never`, which `codex --help`
describes as: "Never ask for user approval Execution failures are immediately
returned to the model".

### Documented usage-limit output (not provoked)

This was not documented in the installed package. These strings come from the
installed binary (path above), found with `strings -n 8 … | grep`:

```text
ve hit your usage limit.
ve hit your usage limit for 
ve hit your usage limit. Upgrade to Plus to continue using Codex (https://chatgpt.com/explore/plus),
ve hit your usage limit. Upgrade to Pro (https://chatgpt.com/explore/pro), visit https://chatgpt.com/settings/usage to purchase more credits
ve hit your usage limit. Visit https://chatgpt.com/settings/usage to purchase more credits
 Try again at 
 or try again at 
Usage limit reached. You've reached your usage limit. Increase your limits to continue using codex.
```

The binary also holds these error codes: `usage_limit_reached`,
`quota_exceeded`, `rate_limit_reached`, `workspace_owner_usage_limit_reached`
and `workspace_member_usage_limit_reached`. It also holds the rate-limit
window fields `used_percent`, `limit_window_seconds` and
`reset_after_seconds`. Neither the order these fragments print in nor the
`--json` event a limit produces was observed.

### Telemetry and session-upload switches

The installed package documents none. The binary's strings contain
`analytics_enabled`, `analytics-default-enabled`, `log_user_prompt`, and the
URL `https://developers.openai.com/codex/config-advanced/#metrics`. That
points to an `[analytics]` table in `config.toml` and an OTel
`log_user_prompt` switch, but the probe did not verify either key's spelling
or effect. `--ephemeral` turns off local session files. Sessions are stored
under `~/.codex/sessions`; the probe observed no upload of them and no switch
for one. The laptop's `~/.codex/config.toml` has only the top-level key
`['projects']`.

### ACP

`codex --help` lists no `acp` command. The adapter package was looked up with
`npm view` only:

```text
$ timeout 60 npm view @zed-industries/codex-acp name version
name = '@zed-industries/codex-acp'
version = '0.16.0'
$ timeout 60 npm ls -g --depth=0
/home/msi/.nvm/versions/node/v22.23.3/lib
├── @deepseek-ai/dsh@0.2.0-rc.2
├── @openai/codex@0.163.0
├── corepack@0.36.0
├── npm@10.9.9
└── opencode-ai@1.19.2
```

The adapter, `@zed-industries/codex-acp` 0.16.0, is not installed.

## OpenCode (`opencode-ai` 1.19.2): unavailable: no model configured

OpenCode is signed in (Nebius Token Factory), but no default model is
configured anywhere the probe looked:

```text
$ ls -la ~/.config/opencode/            # (names only)
.gitignore  node_modules  opencode.jsonc  package.json  package-lock.json
$ python3 -I -c '…' ~/.config/opencode/opencode.jsonc   # (abbreviated) prints the top-level keys and the model, small_model, permission, share and provider entries
/home/msi/.config/opencode/opencode.jsonc ['$schema']
model: None
small_model: None
permission: None
share: None
provider keys: {}
$ ls -la ~/.local/state/opencode/       # (names only)
locks
$ timeout 120 opencode models | head      # 11 opencode/* free models, then nebius/* models
opencode/beam-free
opencode/big-pickle
…
nebius/deepseek-ai/DeepSeek-V4-Flash-0731
nebius/deepseek-ai/DeepSeek-V4-Pro
…
```

`opencode models` lists models it can reach, but none is configured as the
default: `opencode.jsonc` has no `model` key, and there is no
`~/.local/state/opencode/model.json`. Choosing one would have been the probe
improvising, so it made no `opencode run` call. Every observed row is
therefore `unavailable: no model configured`. What `--help` and the binary
show without a model call is recorded below.

The one-shot command, from `opencode run --help`, would be:

```text
opencode run --format json [-m provider/model] [message..]
```

Other flags it documents: `-s, --session` (session id to continue), `-c,
--continue` (the last session), `--fork`, `--dir`, `--agent`, and `--auto`
("auto-approve permissions that are not explicitly denied (dangerous!)",
default `false`).

| Row | Result |
|---|---|
| One-shot command, exit status | unavailable: no model configured |
| Event stream (first and last five lines) | unavailable: no model configured |
| Resume with "what did you create?" | unavailable: no model configured (would be `opencode run --format json -s <session> 'what did you create?'`) |
| Session store and one session file | unavailable: no model configured; no session was created. The store is the SQLite database `~/.local/share/opencode/opencode.db` (with `-shm`/`-wal`). Its table names, read-only, schema only: `account account_state control_account credential data_migration event event_sequence message migration part permission project project_directory session session_context_epoch session_input session_message session_share todo workspace` |
| `touch /tmp/outside-probe` | unavailable: no model configured |
| `curl --version` | unavailable: no model configured |
| VERDICT first line | unavailable: no model configured |
| Usage-limit output (docs/source) | No docs are installed. In the binary `~/.nvm/versions/node/v22.23.3/lib/node_modules/opencode-ai/node_modules/opencode-linux-x64/bin/opencode`, a retry classifier matches `/429\|500\|502\|503\|504\|524/i` and `/rate increased too quickly\|rate limit\|rate-limit\|rate_limit\|too many requests/i`, and a response body containing `FreeUsageLimitError` maps to `{reason:"free_tier_limit", … title:"Free limit reached"}` |
| Telemetry and session-upload switches | Config key `"share": "manual" \| "auto" \| "disabled"` (binary string), and env `OPENCODE_AUTO_SHARE`. Telemetry is OTel through `OTEL_EXPORTER_OTLP_*_ENDPOINT` (binary string); the probe found no `OPENCODE_*TELEMETRY*` variable. Also `OPENCODE_DISABLE_AUTOUPDATE` and `OPENCODE_DISABLE_MODELS_FETCH` |
| ACP | Built in. `opencode --help` lists `opencode acp  start ACP (Agent Client Protocol) server` |

## dsh (`@deepseek-ai/dsh` 0.2.0-rc.2): unavailable: not signed in

`DEEPSEEK_API_KEY` is unset and `~/.dsh` does not exist, so the probe made no
`dsh` model call. It also did not boot a profile, which would have created
`~/.dsh`. It ran only `dsh --version` and `dsh --help`. Every observed row is
`unavailable: not signed in`.

The documentary rows below come from the installed package at
`~/.nvm/versions/node/v22.23.3/lib/node_modules/@deepseek-ai/dsh/`. In the
table, "the package" means that directory.

| Row | Result |
|---|---|
| One-shot command, exit status | unavailable: not signed in. Would be `dsh --profile headless --json "<task>"`. The package's `node_modules/@deepseek-ai/dsh-headless/README.md` says "Exit code 0 means the task completed; 1 means it aborted or errored" |
| Event stream (first and last five lines) | unavailable: not signed in. The same README says the `--json` stream "opens with `session` … and closes with `final`, and carries `status`, `text`, `thinking`, `tool_call`, and `tool_result` events in between" |
| Resume with "what did you create?" | unavailable: not signed in. Would be `dsh --profile headless --json --session-id <id> 'what did you create?'`. Per the README, adoption refuses a session recorded in another working directory |
| Session store and one session file | unavailable: not signed in. Under `$DSH_HOME` (default `~/.dsh`, per `dsh-home-paths/README.md`); the package ships `dsh-session-persistence-jsonl` |
| `touch /tmp/outside-probe` | unavailable: not signed in |
| `curl --version` | unavailable: not signed in |
| VERDICT first line | unavailable: not signed in |
| Usage-limit output (docs/source) | Four READMEs under the package's `node_modules/@deepseek-ai/` document it. `dsh-llm/README.md`: "`QUOTA` is provider-neutral exhaustion, while `ACCOUNT_QUOTA` is reserved for a first-party account balance that the current product can replenish". `dsh-llm-deepseek/README.md`: "Non-2xx responses fail with stable codes: `AUTH` (401/403), `QUOTA`, `RATE_LIMIT`, …". `dsh-headless/README.md`: "a failure exits 1 and prints `dsh: <code>: <message>` to stderr". `dsh-llm-retry/README.md`: normal mode retries `RATE_LIMIT` five times, "with bounded exponential backoff from 500 ms to 10 seconds" |
| Telemetry and session-upload switches | `DSH_TELEMETRY_DISABLED`: any non-empty value applies the hard-disable patch (`resolveTelemetryPatch` in `node_modules/@deepseek-ai/dsh-app-boot/lib/index.js`). `dsh_session_log` is owned by the plugin `@deepseek-ai/dsh-session-log-deepseek`, whose config key `enabled` (default `true`) is documented as "`false` stops Session-log upload" in `node_modules/@deepseek-ai/dsh-session-log-deepseek/README.md`. The package README cites the config catalog as `docs/config-catalog.md`, which is not shipped in the npm package |
| ACP | Built in: `dsh --profile acp` "Serve automation clients over ACP stdio until disconnect" (the package's `README.md`, line 13; bundle `@deepseek-ai/dsh-acp-app`) |

## Claude Code

Claude Code was recorded for its version only (`2.1.300 (Claude Code)`). It is
today's harness, and §40 does not ask the probe to exercise it.

## Requirements table (§40)

Each cell is `yes`, `no` or `partial: <why>`. An `unavailable` cell is marked
as such.

| Harness | One-shot | Resume | Readable stream | Enforceable permission | VERDICT |
|---|---|---|---|---|---|
| Codex 0.163.0 | yes | yes | partial: a command the sandbox failed to start produced no `command_execution` item, only the agent's prose | no | yes |
| OpenCode 1.19.2 | unavailable: no model configured | unavailable: no model configured | unavailable: no model configured | unavailable: no model configured | unavailable: no model configured |
| dsh 0.2.0-rc.2 | unavailable: not signed in | unavailable: not signed in | unavailable: not signed in | unavailable: not signed in | unavailable: not signed in |

The Codex cell for enforceable permission is `no` on this laptop. Its only
sandbox modes that confine writes (`read-only` and `workspace-write`) do not
start: the bundled bwrap fails with `loopback: Failed RTM_NEWADDR`. The only
mode in which the task can write, `danger-full-access`, ran both `touch
/tmp/outside-probe` and `curl --version` without asking. Neither mode routed a
command through any approval.

## Gaps (what the probe could not observe)

- **OpenCode, every live row.** No default model is configured. Setting
  `"model"` in `~/.config/opencode/opencode.jsonc` and re-running this probe
  would fill them.
- **dsh, every live row.** It is not signed in.
- **Codex under a working sandbox.** The probe never saw whether
  `workspace-write` refuses `touch /tmp/outside-probe` and `curl` once bwrap
  can start. That needs an AppArmor allowance for Codex's bundled bwrap, or
  `kernel.apparmor_restrict_unprivileged_userns=0`, both host changes the
  probe did not make.
- **Codex approvals.** Whether a `codex exec` turn under `-a on-request`
  (top-level flag, or `-c approval_policy=…`) emits an approval event in
  `--json`, and how a headless run answers it, was not tried.
- **Codex at a real usage limit.** The order of the binary's limit fragments,
  the `--json` event a limit produces, and the exit status at a limit were not
  observed (by design: not provoked).
- **Codex telemetry keys.** These are inferred from binary strings only. The
  online docs were not fetched.
- **ACP behaviour.** No ACP server was started for any harness, so whether
  shell commands arrive as permission requests (the §40 condition for the ACP
  prior) is unobserved for all three.
- **The handsd environment.** Every run was a shell in the builder's session,
  not a job spawned by handsd under systemd.
