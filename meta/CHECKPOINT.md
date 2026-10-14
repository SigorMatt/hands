# CHECKPOINT

Mission: 20 (meta/BUILDER-20-PROMPT.md, DESIGN v3.19 §36 with §31, §33,
§34, §35; meta/reviews/REVIEW-19.md, meta/reviews/REVIEW-18.md).
Pull request: every unit commits and pushes to `mission-20`.
Base: 238a57b (`plan: mission 20 kit (DESIGN v3.19)`).

Done: U0 1977864 (`plan:`) — H-041..H-045 filed; origin/mission-20 exists;
green 3/3 (4052, HANDS_* unset).

Done: U1 4752ace — conftest autouse fixture clears HANDS_*; gh row reads
`gh auth status --active --hostname github.com`, every WARN names the
remedy; INTEGRATION/PLAYBOOK corrected; H-040 resolved; green 3/3 (4059,
HANDS_PROJECT=x HANDS_JOB=y). From here the gate is plain ./scripts/check.

Done: U2 7326386 — protocol and template together (direct only on
"Direct", no PR = blocker, <branch> once, ^origin/main, tests-only by the
named wrong changes, sub-agents one at a time); diff = names only; green 3/3
(4076). Left for U9: docs/PLAYBOOK.md (~503) still says mission-N without
^origin/main; ARCHITECT-HANDBOOK (~236) likewise (handbook = mission 21).

Done: U3 0eb37bc — architect/settings.json allows Edit/Write/MultiEdit(kits/**);
doctor's row fails on a missing or wider write allow (any settings layer);
--live writes, checks, shows, doctor removes; H-041 resolved; green 3/3.

Done: U4 de2e34c — fetch + checkout --detach origin/<branch> before every
architect/driver job (failure = spawn_error before claude, git message in
stderr_tail); HANDS_PROJECT from the config on every job; doctor rows show
HEAD vs origin and the project; H-042, H-043 resolved; green 3/3 (4105).

Done: U5 337db9a — the engine reloads the committed playbook before its own
apply's builder.done (regression test red on 238a57b); unloadable playbook
stops with the loader's reason; autonomous role-kit hold decided before
publish (buttonless when approved, buttons on name/hash mismatch); H-044,
H-045 resolved; green 3/3 (4110).

Done: U6 187e38e — answer <secret> <text>: keep send origin phone,
un-pauses, not gated, refusals under hands: answer, .zip attachment into
kit_dir with sha256, answer.sent, builder reply titled builder, escalation
stop keeps the question, consult prompt lists human decisions; green 3/3
(4131).

Done: U7 61a2417 — builder/aux spawn_env defaults BASH_DEFAULT_TIMEOUT_MS and
BASH_MAX_TIMEOUT_MS 900000 (role env overrides), doctor prints them;
architect cp/cp -r clone->kits by realpath, symlink refusals; self-test
405/405; green 3/3 (4180).

Done: U8 6a3f2f2 — non-ASCII ntfy_url refused at load, folded-host broker
check; doctor self-test python3 -I, PYTHONPATH=""; kit record = sha256 of
checked bytes, mismatch refuses; hardlink under kits refuses cp/mv, doctor
reports; green 3/3 (4212). Residual for a finding: the live hook runs the
guard without -I.

Done: U9 2e9a6ca — every title the Notifier publishes (and notify --test)
begins with <project>: ; doctor `topics` row warns on a topic lacking the
project; INTEGRATION/README topic lines carry it; PLAYBOOK.toml kickoff is
the mission-less line (loads, 20 rules); kit check --repo exits 0;
docs/PLAYBOOK.md review range matches the protocol; green 3/3 (4225). The
sub-agent committed before its three runs (tests refuse a PLAYBOOK.toml
differing from HEAD), pushed only after 3/3.

Done: U10 (this commit) — meta/FINAL-REPORT-20.md; green 3/3 (4225,
HANDS_PROJECT=hands set); PR mission-20 -> main opened; tree back on main.
Mission 20 finished.

Standing constraints: one foreground sub-agent per unit; commit and push
every unit to `mission-20`; ./scripts/check green three consecutive runs
before each commit (each a foreground call, 20-minute timeout; as `env -u
HANDS_PROJECT -u HANDS_JOB ./scripts/check` until U1 lands); explicit paths
only in `git add` (never `-A`); reports drafted under meta/drafts/;
DESIGN.md is not edited by builders (file a finding); sub-agents do not
edit meta/plan.md or this file; retry a failed unit once then `[b]`. Not
this mission: onboarding, `hands project add`, the instruction templates,
the handbook's new sections (mission 21).
