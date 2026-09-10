# Starting a driver session

One driver directory per project, outside any repository:

    mkdir -p ~/hands-driver/hands && cd ~/hands-driver/hands
    cp ~/git/hands/driver/CLAUDE.md ./CLAUDE.md
    mkdir -p .claude/hooks && cp ~/git/hands/driver/settings.json .claude/settings.json
    cp ~/git/hands/driver/hooks/bash_guard.py .claude/hooks/ && python3 .claude/hooks/bash_guard.py --selftest
    cp ~/git/hands/bootstrap/dispatch.sh ./dispatch.sh && chmod +x dispatch.sh
    git clone https://github.com/SigorMatt/hands repo
    git -C repo remote set-url --push origin no_push

Edit the Parameters block in `CLAUDE.md` for the project. Then:

    claude
    /rc            # enable remote control so the phone's Code tab can reach it

Leave the session open. From the phone (Claude app → Code tab → this
session) the first message for mission 1 is:

    kick off mission 1

The driver answers with a `VERDICT:` line, a job number, and a spool path.
Every later message is a question or a decision; the driver never needs
prompts from you.

Notes:
- Two layers stop the driver from writing. `.claude/settings.json` denies the
  Edit/Write tools, mutating git, and `claude` itself. `.claude/hooks/bash_guard.py`
  runs before every Bash call and blocks anything that is not `hands`,
  `./dispatch.sh`, read-only git, or a read-only inspection command, and any
  redirection, `tee`, `sed -i`, interpreter, or file mutation; permission
  rules alone cannot see a `>` inside an otherwise harmless command. Hooks
  are read at session start, so after changing either file restart the
  session. If a permission prompt appears, that is the driver trying
  something outside its role; answer no.
- The `repo/` clone has its push URL disabled. Even a bug in the driver
  cannot push from it.
- Once `hands` is installed, remove `dispatch.sh` from the directory and set
  `DISPATCH = hands` in `CLAUDE.md`.
