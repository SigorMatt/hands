# CHECKPOINT

Mission: 13 (meta/BUILDER-13-PROMPT.md, DESIGN v3.12 §29 with §5, §12, §13,
§26, §28) — close review 12, the sweep (H-025 b), two projects on one laptop.
Base: 723dbeb (`plan: mission 13 kit (DESIGN v3.12)`).

Unit in progress: U6 Two projects on one laptop (§29).
Intent: per-project spool under `~/.hands/<project>/` (jobs/, roles/, inbox,
nonces); `hands migrate-spool` moves the flat layout to `~/.hands/hands/` and
files an inbox event; `handsd` refuses the flat layout with the migration
instruction; templated units `systemd/handsd@.service` and
`systemd/handswho@.service` reading `~/.config/hands/<project>.env`; the
un-templated units removed; `hands who` reads every project's spool and shows
each daemon as a root; docs/INTEGRATION.md describes two daemons and the one
shared resource, the subscription, metered by each playbook's `auto_runs`.
Done means: tests for the layout, the migration, and the refusal; `hands who`
with two fixture spools shows two roots; `systemd/` holds only templated
units; ./scripts/check 3/3; pushed.
Done: U0 b79d908 (1994); U1 eccc3a1 (2092); U2 ea7f1bc (2098); U3 126d4ff
(2196); U4 38022f2 (2235); U5 9ca89cf (2272).

Standing constraints: one foreground sub-agent per product unit, commit and
push every unit, ./scripts/check green three consecutive runs before each
commit, explicit paths only in `git add` (never `-A`), reports drafted under
meta/drafts/, DESIGN.md is not edited by builders (file a finding), sub-agents
do not edit meta/plan.md or this file, retry a failed unit once then `[b]`.
