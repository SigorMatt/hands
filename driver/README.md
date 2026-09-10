# Starting a driver session

One driver directory per project, outside any repository:

    mkdir -p ~/hands-driver/hands && cd ~/hands-driver/hands
    cp ~/git/hands/driver/CLAUDE.md ./CLAUDE.md
    mkdir -p .claude && cp ~/git/hands/driver/settings.json .claude/settings.json
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
- `.claude/settings.json` is what stops the driver from writing: Edit/Write
  are denied, git is read-only, `claude` itself is denied (it must go through
  `hands`/`dispatch.sh`). If a permission prompt appears, that is the driver
  trying something outside its role; answer no.
- The `repo/` clone has its push URL disabled. Even a bug in the driver
  cannot push from it.
- Once `hands` is installed, remove `dispatch.sh` from the directory and set
  `DISPATCH = hands` in `CLAUDE.md`.
