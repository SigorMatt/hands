# The architect role — directory and switch point

One directory per project, outside any repository:

    mkdir -p ~/hands-architect/<project>/kits && cd ~/hands-architect/<project>   # a kit is kits/<name>/<repository paths>, filed with hands kit file kits/<name>
    cp ~/git/hands/architect/CLAUDE.md ./CLAUDE.md        # fill the Parameters block
    mkdir -p .claude/hooks
    cp ~/git/hands/architect/settings.json .claude/settings.json
    cp ~/git/hands/driver/hooks/bash_guard.py .claude/hooks/bash_guard.py
    HANDS_ROLE=architect HANDS_KITS=$PWD/kits python3 .claude/hooks/bash_guard.py --selftest
    git clone <repo url> repo && git -C repo remote set-url --push origin no_push
    claude          # once, interactively: accept the trust dialog, then /exit

Config:

    [roles.architect]
    cwd = "~/hands-architect/<project>"     # permission_flags stays empty

    [series]
    architect = "role"
    autonomous = true
    gate_failures = 2
    escalate_on = ["blocker-unanswered", "milestone-missing", "budget-exhausted"]

## The switch point

The role takes over from the phone architect at the fully reviewed work
plan. Deliverables, all on the branch before the switch:

1. `DESIGN.md` — the shape.
2. `meta/ROADMAP.md` — every milestone with a checkable gate, in order.
3. The first brief or run plan, and the sequence of the rest at the
   roadmap's granularity.
4. `PLAYBOOK.toml` with `[series] architect = "role"`, `autonomous`, the
   escalation conditions, and `consult` on review outcomes with
   `role = "architect"`.
5. This directory, set up as above.

Applying that playbook (a gated job the human approves) is the switch. To
hand the series back to the phone: `hands pause`, then the phone architect
continues from the branch; set `architect = "phone"` in the next kit. One
architect at a time.

## When it escalates

The notification names the condition and the architect's last session id,
with a `claude --resume <id>` line. Open the directory on the laptop, run
that line, `/rc`, and talk to it from the Code tab; or, after mission 16,
answer over ntfy with `reply <secret> <text>`. Whatever is decided becomes
a decisions file the role applies in its next kit.
