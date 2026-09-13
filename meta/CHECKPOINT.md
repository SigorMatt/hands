# CHECKPOINT

Mission: 10 (meta/BUILDER-10-PROMPT.md, DESIGN v3.9 §26)
Unit in progress: U6 The closed loop in the docs; doctor rows (§26).
Intent: docs/INTEGRATION.md describes the loop end to end from the phone (send
the kit, approve the gated apply, `go`, wait for the buzz), with the driver as
inspector, stating what is unproven (real ntfy attachment, real `go`, who by
pid is not built: H-020); README.md updated (kit check, go, kit transport);
`hands doctor` reports `go` (on when cmd_topic + cmd_secret and a playbook
with `[series] kickoff`) and kit transport (on when cmd_topic + cmd_secret and
kit_dir inside allowed roots) as on/off rows, exit 0 without extras.
Done means: one commit, body names U6, §26, lists every file; doctor row tests
(on and off each); docs sweep (tests/test_docs.py) green; pushed;
./scripts/check green 3/3.
Base: 61e1486.
Done: U0 cbb8fc8 (1435 passed); U1 17ba97e (1443); U2 067b8fd (1461);
U3 6852751 (1501); U5 9e962a4 (1538).
Blocked: U4 on DESIGN (H-020, memo 9f7effd); U6–U7 do not depend on it.
Carried to U7 NOT PROVEN: the phone channel reads no other command during a kit
download (up to 300 s); real ntfy attachment delivery; real `go` from a phone;
who-by-pid not built; kit check covers builder.done verdict rules only (H-021);
kit check not run from a fresh `uv tool install`.
Standing constraints: one foreground sub-agent per product unit, commit and
push every unit, ./scripts/check green three consecutive runs before each
commit, explicit paths only in `git add` (never `-A`), reports drafted under
meta/drafts/, DESIGN.md is not edited by builders (file a finding), sub-agents
do not edit meta/plan.md or this file.
