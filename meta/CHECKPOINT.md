# CHECKPOINT

Mission: 10 (meta/BUILDER-10-PROMPT.md, DESIGN v3.9 §26)
Unit in progress: U3 Kit transport (§26, §13, §24/§25 phone channel).
Intent: a `cmd_topic` message with body `kit <secret>` and an ntfy attachment:
handsd reads `attachment.url`/`name`/`size` from the ntfy message; refuses a
name that is not a `.zip` basename; refuses a size over `[files] kit_max_mb`
(default 20) before downloading (ntfy reports the size; also cap while
streaming); writes into `[files] kit_dir` (default `~/Downloads`, must be an
allowed root) atomically (temp file in the same dir, rename); never unzips,
never executes; an existing name gets a numeric suffix, never overwritten;
files `kit.received` to the inbox and a notification
`kit received <name> <bytes> <sha256>`. Refusals are logged without the secret.
Done means: one commit, body names U3, §26/§13, lists every file; tests with a
mocked ntfy stream and a local HTTP server for the attachment: happy path,
oversize, bad name, duplicate name, missing secret; pushed; ./scripts/check
green 3/3.
Base: 61e1486.
Done: U0 cbb8fc8 (1435 passed); U1 17ba97e (1443); U2 067b8fd (1461).
Carried to U5: H-019 — templates/PLAYBOOK-*.toml carry `series = "…"` beside
`[series]`, which TOML refuses; the loader takes `[series] name`.
Standing constraints: one foreground sub-agent per product unit, commit and
push every unit, ./scripts/check green three consecutive runs before each
commit, explicit paths only in `git add` (never `-A`), reports drafted under
meta/drafts/, DESIGN.md is not edited by builders (file a finding), sub-agents
do not edit meta/plan.md or this file.
