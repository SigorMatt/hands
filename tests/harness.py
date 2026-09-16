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
