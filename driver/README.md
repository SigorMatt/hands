# Starting a driver session

One driver directory per project, outside any repository:

    mkdir -p ~/hands-driver/hands && cd ~/hands-driver/hands
    cp ~/git/hands/driver/CLAUDE.md ./CLAUDE.md
    mkdir -p .claude/hooks && cp ~/git/hands/driver/settings.json .claude/settings.json
    cp ~/git/hands/driver/hooks/bash_guard.py .claude/hooks/ && python3 .claude/hooks/bash_guard.py --selftest
    git clone https://github.com/SigorMatt/hands repo
    git -C repo remote set-url --push origin no_push

Edit the Parameters block in `CLAUDE.md` for the project. Then:

    claude
    /rc            # enable remote control so the phone's Code tab can reach it

Leave the session open. From the phone (Claude app → Code tab → this
session) the first message of a mission is:

    kick off mission 2

The driver turns that into one `hands send` carrying the mission's kickoff
line, and answers with a `VERDICT:` line and the job id. Every later message
is a question or a decision; the driver never needs prompts from you.

Notes:
- Two layers stop the driver from writing. `.claude/settings.json` denies the
  Edit/Write tools, mutating git, `claude` itself, and `hands open`.
  `.claude/hooks/bash_guard.py` runs before every Bash call and blocks
  anything that is not `hands`, read-only git, or a read-only
  inspection command, and any redirection, `tee`, `sed -i`, interpreter, or
  file mutation; permission rules alone cannot see a `>` inside an otherwise
  harmless command. Hooks are read at session start, so after changing either
  file restart the session. If a permission prompt appears, that is the driver
  trying something outside its role; answer no.
- `hands open <job>` is blocked in both layers: it execs an interactive
  `claude --resume` in the role's directory, which is not something a driver
  can drive. Jobs are read with `hands show`, `hands log` and `hands tail`.
- One honest cost of the guard: it cannot tell a `>` inside `hands put <path>
  --content "…"` from a redirection, and blocks the call. Content with a `>`
  in it has to reach the machine another way.
- The `repo/` clone has its push URL disabled. Even a bug in the driver
  cannot push from it.
- `hands` must be installed on the laptop first (`uv tool install
  ~/git/hands`, then `docs/INTEGRATION.md`). `hands doctor` at the laptop is
  the check that the driver has something to talk to; it also prints the §11
  notification check, which is run once at the laptop and ends on your phone.
- The driver waits for nothing and polls for nothing (CLAUDE.md rule 8). ntfy
  is your doorbell: a `stop`, a `job.held`, an exhausted `max_resumes` or a
  daemon crash arrives on the phone. Open this session's Code tab and send:

      check

  That is the driver's wake — it reads the inbox and reports (rule 2).
