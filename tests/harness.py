"""Shared harness for the tests that drive a real daemon over its real socket.

The daemon runs in the test's event loop and the CLI runs in a worker thread,
exactly as `hands` runs at a terminal. Nothing is mocked but the `claude`
binary (`tests/fake_claude.py`).
"""

from __future__ import annotations

import asyncio
import io
import json
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from hands.cli import main
from hands.config import load_config
from hands.daemon import Daemon
from hands.spool import Job

FAKE = Path(__file__).with_name("fake_claude.py")
PROJECT = "demo"
TIMEOUT = 60.0
BLOCK = "FAKE:block"


def config_body(
    home: Path, workdir: Path, *, builder: str = "", aux: str = "", extra: str = ""
) -> str:
    """`~/.hands/demo.toml`: both roles on the fake binary, §13 queue depths."""
    return f"""
[server]
socket = "{home}/.hands/handsd.sock"

[roles.builder]
cwd = "{workdir}"
queue_depth = 1
{builder}

[roles.aux]
cwd = "{workdir}"
queue_depth = 4
{aux}

[runner]
claude = "{FAKE}"
cancel_grace_s = 0.5
{extra}
"""


def write_project(home: Path, body: str, project: str = PROJECT) -> str:
    (home / ".hands" / f"{project}.toml").write_text(body)
    return project


async def cli(*argv: str) -> tuple[int, str, str]:
    """Run the CLI in a thread — it is a blocking socket client, like the real one."""
    out, err = io.StringIO(), io.StringIO()
    code = await asyncio.to_thread(main, ["--project", PROJECT, *argv], stdout=out, stderr=err)
    return code, out.getvalue(), err.getvalue()


async def ok(*argv: str) -> Any:
    code, out, err = await cli(*argv, "--json")
    assert code == 0, f"hands {' '.join(argv)} failed: {err}"
    return json.loads(out)


async def fails(*argv: str) -> str:
    code, out, err = await cli(*argv, "--json")
    assert code != 0, f"hands {' '.join(argv)} unexpectedly succeeded: {out}"
    return err


async def poll(check: Callable[[], Awaitable[Any]], what: str) -> Any:
    for _ in range(int(TIMEOUT / 0.02)):
        value = await check()
        if value:
            return value
        await asyncio.sleep(0.02)
    raise AssertionError(f"timed out waiting for {what}")


async def running_job(role: str = "builder") -> Any:
    async def check() -> Any:
        return (await ok("status"))["roles"][role]["running"]

    return await poll(check, f"a running job on {role}")


def drive(body: Callable[[Daemon], Awaitable[None]]) -> None:
    """Start a daemon in-process, run `body` against it, always shut it down."""

    async def scenario() -> None:
        daemon = Daemon(load_config(PROJECT))
        await daemon.start()
        try:
            await asyncio.wait_for(body(daemon), TIMEOUT)
        finally:
            await daemon.stop()

    asyncio.run(scenario())


# ------------------------------------------------ the architect's consultation (§32)

#: The first line every consultation prompt carries (`playbook.consult_head`).
CONSULT_HEAD = "hands consult: aux.done on job 0 (role aux)\n"


def architect_table(home: Path) -> str:
    """`[roles.architect]`, for `config_body(extra=...)`: the role `kit_file` needs."""
    cwd = home.parent / "hands-architect"
    cwd.mkdir(exist_ok=True)
    return f'\n[roles.architect]\ncwd = "{cwd}"\n'


def open_consultation(daemon: Daemon) -> Job:
    """An architect consultation in progress, as the daemon holds one while its
    worker runs it: the job `running` in the spool and in the role's running slot.
    §32: `kit_file` is accepted only then (or while the engine waits for `next kit`).
    Close it with `close_consultation` before the daemon stops, or the daemon will
    try to signal a process that does not exist."""
    job = daemon.spool.create_job(
        role="architect", context="clear", prompt=CONSULT_HEAD, origin="playbook"
    )
    job = daemon.spool.transition(job, "running")
    daemon._running["architect"] = job.id
    return job


def close_consultation(daemon: Daemon, job: Job) -> Job:
    daemon._running["architect"] = None
    return daemon.spool.transition(job.id, "done")


# ------------------------------------------------ a kit that passes the check (§33)

#: §33: handsd runs `hands kit check` on every kit `kit_file` stores, against the
#: builder's repository, and refuses a failing one. These are the entries of a kit
#: that passes it against any repository — its own brief, its own playbook (phone
#: mode, so no config is judged), and the review protocol that playbook's send names
#: — so a test that files a kit over the socket files one handsd accepts.
PASSING_BRIEF = """\
# BUILDER-17-PROMPT — demo mission 17

Kickoff line (the only way this mission is started or resumed):

    Read meta/BUILDER-17-PROMPT.md and execute the mission below its divider.

---

- Your final reply begins with exactly one of: `VERDICT: mission 17
  finished` | `VERDICT: question <one line>`.
"""

PASSING_PLAYBOOK = """\
version = 1

[series]
name = "demo-17"
kickoff = "Read meta/BUILDER-17-PROMPT.md and execute the mission below its divider."

[[rule]]
on = "builder.done"
verdict = '^VERDICT: mission (?P<n>\\d+) finished'
then = "send"
role = "aux"
context = "clear"
prompt = "Read meta/REVIEW-PROTOCOL.md, review mission {n}, commit meta/reviews/REVIEW-{n}.md."

[[rule]]
on = "builder.done"
verdict = '^VERDICT: kit applied'
then = "notify"
message = "Kit applied"

[[rule]]
on = "builder.done"
verdict = '^VERDICT: question'
then = "stop"
message = "The builder has a question"

[[rule]]
on = "aux.done"
verdict = '^VERDICT: review mission (?P<n>\\d+) blockers=0'
then = "stop"
message = "Mission {n} reviewed clean"
"""

PASSING_PROTOCOL = (
    "# REVIEW-PROTOCOL\n\nYour reply's first line is exactly:\n\n"
    "    VERDICT: review mission N blockers=<k> should-fix=<m>\n"
)


def passing_kit() -> dict[str, str]:
    """The entries of a kit `hands kit check` passes against any repository."""
    return {
        "meta/BUILDER-17-PROMPT.md": PASSING_BRIEF,
        "PLAYBOOK.toml": PASSING_PLAYBOOK,
        "meta/REVIEW-PROTOCOL.md": PASSING_PROTOCOL,
        "KIT.md": "plan: mission 17 kit\n",
    }


#: REVIEW-16 blocker 1's kit: the guard, its settings, DESIGN.md and a playbook, and
#: no brief. `hands kit check` fails it (paths — §33 refuses `.claude/` — playbook,
#: brief, verdicts, wording).
UNCHECKED_KIT: dict[str, str] = {
    ".claude/hooks/bash_guard.py": "# neutered\n",
    ".claude/settings.json": "{}\n",
    "DESIGN.md": "# DESIGN\n",
    "PLAYBOOK.toml": PASSING_PLAYBOOK,
}


def kit_zip(files: dict[str, str]) -> bytes:
    """The zip of `files`, each entry at its repository path."""
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, text in files.items():
            archive.writestr(name, text)
    return buffer.getvalue()


#: REVIEW-16 blocker 2 (H-036): the entry's name in its local header and in the
#: central directory, and the name its Info-ZIP Unicode Path field (0x7075) gives —
#: the one `unzip` and `ZipInfo.filename` take.
CRAFTED_NAME = "docs/notes.md"
CRAFTED_TARGET = ".git/hooks/pre-commit"
#: The ways `crafted_zip` makes the entry's names disagree.
CRAFTED_HOWS = ("unicode", "local-unicode", "local")


def crafted_zip(files: dict[str, str | bytes], how: str) -> bytes:
    """The zip of `files` plus REVIEW-16 blocker 2's entry, mode 0755, whose names
    disagree `how`:

    - `unicode`: the reviewer's zip — local header and central directory say
      `docs/notes.md`, and a Unicode Path field in both names `.git/hooks/pre-commit`;
    - `local-unicode`: that field in the local header only;
    - `local`: no field, and the local header's raw name is `.git/hooks/xx` while
      the central directory's is `docs/notes.md`.
    """
    import struct
    import zipfile
    import zlib

    raw = CRAFTED_NAME.encode()
    target = CRAFTED_TARGET.encode()
    field = struct.pack("<HHBL", 0x7075, 5 + len(target), 1, zlib.crc32(raw)) + target
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, text in files.items():
            archive.writestr(name, text)
        info = zipfile.ZipInfo(CRAFTED_NAME)
        info.external_attr = 0o100755 << 16
        if how != "local":
            info.extra = field
        archive.writestr(info, "#!/bin/sh\necho hook ran\n")
    data = buffer.getvalue()
    if how == "local-unicode":
        assert data.count(field) == 2, "the field is in the local header and the directory"
        at = data.rindex(field)  # the central directory's copy: another, unknown, id
        data = data[:at] + struct.pack("<H", 0x6666) + data[at + 2 :]
    elif how == "local":
        swap = b".git/hooks/xx"
        assert data.count(raw) == 2 and len(swap) == len(raw)
        at = data.index(raw)  # the local header comes first
        data = data[:at] + swap + data[at + len(raw) :]
    else:
        assert how == "unicode", how
    return data
