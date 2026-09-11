# plan — mission 1 (the hands core)

Source: meta/BUILDER-1-PROMPT.md. Units run in order; each ends with a
commit and a push. `[x]` = done and pushed, `[b]` = blocked (two failures),
`[y]` = yielded under budget pressure.

- [x] U0 Scaffold — pyproject, package skeleton, scripts/check, tests/conftest tmp_home
- [x] U1 Config and spool — config.py (§13), spool.py (§6 state machine, inbox, confinement)
- [x] U2 Fake claude and runner — tests/fake_claude.py, runner.py (§2, §6)
- [x] U3 Daemon, local API, CLI — daemon.py, api.py, cli.py, handsd (§3, §4)
- [x] U4 Files and gates — put/get/ls, --file, gate triggers, authority table (§4, §8)
- [x] U5 Limits — detection, reset parsing, resume, max_resumes (§6)
- [x] U6 Monitor bridge — ops monitor_cmd bridge + built-in stall monitor (§5)
- [x] U7 Playbook engine — playbook.py, pause/resume, pipeline (§10)
- [x] U8 Wake path and notifications — wait --for, notify.py ntfy, quiet hours (§11)
- [x] U9 Job library — jobs/show/open/log (§7)
- [x] U10 Install surface — systemd unit, doctor, docs, driver/ check (§12, §14)
- [x] U11 Final report — meta/FINAL-REPORT-1.md

Yield order under quota pressure (BUILDER-1-PROMPT "Budget guidance"):
U9, U10 (except README.md and the systemd unit), U6 external-monitor
variant, U8 quiet hours. Never yield U0–U3, U4, U7, U11.
