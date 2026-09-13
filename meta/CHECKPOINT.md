# CHECKPOINT

Mission: 10 (meta/BUILDER-10-PROMPT.md, DESIGN v3.9 §26)
Unit in progress: U5 `hands kit check`; handbook and templates against the code
(§4, §26).
Intent: `hands kit check <zip|dir> [--repo path]`, no daemon, implementing the
checks §26 lists; reads the brief's final-reply vocabulary from the lines after
"Your final reply begins with" (or "Reply with one of") and the `verdict`
regexes of the playbook in force (the kit's, else the repo's); prints one line
per check and the apply prompt (handbook §3) listing every file; exit 0 only
when all pass. Then run it on the mission 10 kit (files at 61e1486) and on
templates/ filled with placeholders; fix the handbook or templates where the
code contradicts them (H-019: templates carry `series = "…"` beside `[series]`,
which TOML refuses; the loader takes `[series] name`); anything unreconcilable
is a finding.
Done means: one commit, body names U5, §4/§26, H-019, lists every file; tests
for each check with a passing kit and one failing kit per check; `hands --help`
lists `kit`; `hands kit check` exits 0 on this mission's kit files; pushed;
./scripts/check green 3/3.
Base: 61e1486.
Done: U0 cbb8fc8 (1435 passed); U1 17ba97e (1443); U2 067b8fd (1461);
U3 6852751 (1501).
Blocked: U4 on DESIGN (H-020, memo 9f7effd); U5–U7 do not depend on it.
Carried to U7 NOT PROVEN: the phone channel reads no other command during a kit
download (up to 300 s); real ntfy attachment delivery; real `go` from a phone;
who-by-pid not built.
Standing constraints: one foreground sub-agent per product unit, commit and
push every unit, ./scripts/check green three consecutive runs before each
commit, explicit paths only in `git add` (never `-A`), reports drafted under
meta/drafts/, DESIGN.md is not edited by builders (file a finding), sub-agents
do not edit meta/plan.md or this file.
