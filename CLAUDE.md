# hands — project instructions (read by every session and sub-agent)

hands is a daemon plus CLI that dispatches prompts to headless Claude Code
roles, monitors them, and chains pre-planned steps by a playbook. The
specification is DESIGN.md; where the code and the design disagree, the
design wins unless a finding in meta/findings/FINDINGS.md says otherwise.

Stack: Python >= 3.11, uv, stdlib asyncio and tomllib, httpx for ntfy.
No other runtime dependencies without a finding explaining why.

Gate: ./scripts/check (ruff, pytest, CLI smoke). Green before every commit.

Conventions:
- One commit per unit: <area>: <one line> with a body naming the unit and
  the DESIGN.md sections it implements. Push immediately.
- Tests live in tests/; tests/fake_claude.py stands in for the claude CLI.
- Never require a real claude binary in tests.
- meta/ is the builder's state (checkpoint, plan, journal, findings,
  reports). Sub-agents do not edit meta/plan.md or meta/CHECKPOINT.md.
- DESIGN.md is not edited by builders; file a finding.
