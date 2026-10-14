"""U9 (mission 20): notifications name the project (DESIGN §36).

"Every title handsd publishes begins with `<project>: `; `handswho` keeps its root
line." The titles below are the ones handsd raises — the §11 notifications, the
phone channel's answers, the role replies and the engine's — driven through each of
the three Notifier seams (`notify`, `answer`, `deliver`) to a recording transport.
Doctor's half: a configured topic whose name lacks the project is a warning, never a
failure. Nothing here touches the network.
"""

from __future__ import annotations

import asyncio
import io
import re
from pathlib import Path
from typing import Any

import pytest

from conftest import strip_paths
from hands import daemon as daemon_mod
from hands import notify as notify_mod
from hands.cli import main
from hands.config import load_config
from hands.daemon import NOTIFY_KINDS, Daemon
from hands.doctor import FAIL, OK, WARN, run_checks
from hands.notify import Notifier
from hands.phone import (
    ANSWER_TITLE,
    ARCHITECT_TITLE,
    BUILDER_TITLE,
    GO_TITLE,
    KIT_TITLE,
    REPLY_TITLE,
    STATUS_TITLE,
)
from hands.playbook import SUPPRESSED_CONSULT_TITLE, parse_playbook
from hands.spool import Spool
from harness import PROJECT, TIMEOUT, config_body, poll

#: Every title constant handsd raises, plus the literal ones in daemon.py and
#: playbook.py (`hands: handsd started`, `hands: handsd crashed`, `hands: the
#: pipeline stopped`). The playbook's `notify` action raises `hands: <message>`.
TITLES = [
    BUILDER_TITLE,
    ARCHITECT_TITLE,
    ANSWER_TITLE,
    STATUS_TITLE,
    GO_TITLE,
    KIT_TITLE,
    REPLY_TITLE,
    NOTIFY_KINDS["job.held"],
    SUPPRESSED_CONSULT_TITLE,
    "hands: handsd started",
    "hands: handsd crashed",
    "hands: the pipeline stopped",
    "hands: a rule's own message",
]


class Recorder:
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    async def __call__(self, url: str, **kwargs: Any) -> int:
        self.sent.append({"url": url, **kwargs})
        return 200


def _write(tmp_home: Path, tmp_path: Path, notify: str, project: str = PROJECT) -> None:
    work = tmp_path / "work"
    work.mkdir(exist_ok=True)
    (tmp_home / ".hands" / f"{project}.toml").write_text(
        config_body(tmp_home, work, extra=notify)
    )


EVENTS = '\n[notify]\nntfy_url = "https://ntfy.example"\nntfy_topic = "hands-demo-ev"\n'


@pytest.mark.parametrize("seam", ["notify", "answer", "deliver"])
def test_every_title_handsd_publishes_begins_with_the_project(
    tmp_home: Path, tmp_path: Path, seam: str
) -> None:
    _write(tmp_home, tmp_path, EVENTS)
    config = load_config(PROJECT)
    posts = Recorder()
    notifier = Notifier(config, Spool(config.spool_root), post=posts)

    async def scenario() -> None:
        for title in TITLES:
            if seam == "notify":
                notifier.notify(title, {"message": "m"})
            elif seam == "answer":
                await notifier.answer(title, "m")
            else:
                await notifier.deliver(title, "m")
        await notifier.drain()

    asyncio.run(scenario())
    assert sorted(item["title"] for item in posts.sent) == sorted(
        f"{PROJECT}: {title}" for title in TITLES
    )


def test_a_held_notification_is_named_unprefixed_inside_the_start_message(
    tmp_home: Path, tmp_path: Path
) -> None:
    """The prefix is on the published title; what a hold keeps and the start's one
    names is the raised title, so the start's body does not repeat the project."""
    _write(tmp_home, tmp_path, EVENTS)
    config = load_config(PROJECT)
    posts = Recorder()
    notifier = Notifier(config, Spool(config.spool_root), post=posts)
    notifier.hold()
    notifier.notify(BUILDER_TITLE, {"message": "m"})
    assert [note.title for note in notifier.release()] == [BUILDER_TITLE]


def test_the_daemon_start_and_crash_titles_carry_the_project(
    tmp_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(tmp_home, tmp_path, EVENTS)
    config = load_config(PROJECT)
    posts = Recorder()

    async def scenario() -> None:
        daemon = Daemon(config)
        daemon.notifier.post = posts
        await daemon.start()
        try:

            async def started() -> Any:
                return [p for p in posts.sent if "started" in p["title"]]

            await asyncio.wait_for(poll(started, "the start notification"), TIMEOUT)
        finally:
            await daemon.stop()

    asyncio.run(scenario())
    assert [p["title"] for p in posts.sent] == [f"{PROJECT}: hands: handsd started"]

    crash = Recorder()
    monkeypatch.setattr(notify_mod, "http_post", crash)
    daemon_mod._notify_crash(config, RuntimeError("boom"))
    assert [p["title"] for p in crash.sent] == [f"{PROJECT}: hands: handsd crashed"]


# ------------------------------------------------------------------ doctor


def _topics_row(tmp_home: Path, tmp_path: Path, notify: str) -> Any:
    _write(tmp_home, tmp_path, notify)
    [row] = [c for c in run_checks(load_config(PROJECT)) if c.name == "topics"]
    return row


def test_doctor_warns_never_fails_on_a_topic_lacking_the_project(
    tmp_home: Path, tmp_path: Path
) -> None:
    notify = (
        '\n[notify]\nntfy_topic = "hands-demo-ev"\ncmd_topic = "hands-cmd-x"\n'
        'cmd_secret = "s3cret-s3cret-s3cret"\nwho_topic = "who-demo-w"\n'
        'who_cmd_topic = "whocmd-x"\n'
    )
    row = _topics_row(tmp_home, tmp_path, notify)
    assert row.status == WARN != FAIL, row
    first = strip_paths(row.detail).splitlines()[0]
    assert first.startswith("[notify] cmd_topic, who_cmd_topic: "), row
    for value in ("hands-cmd-x", "whocmd-x", "hands-demo-ev", "who-demo-w"):
        assert value not in strip_paths(row.detail), "doctor never prints a topic"


def test_doctor_is_ok_when_every_configured_topic_carries_the_project(
    tmp_home: Path, tmp_path: Path
) -> None:
    notify = (
        '\n[notify]\nntfy_topic = "hands-demo-ev"\ncmd_topic = "hands-demo-cmd-x"\n'
        'cmd_secret = "s3cret-s3cret-s3cret"\nwho_topic = "who-demo-w"\n'
        'who_cmd_topic = "whocmd-demo-x"\n'
    )
    assert _topics_row(tmp_home, tmp_path, notify).status == OK


def test_doctor_is_ok_with_no_topic_configured(tmp_home: Path, tmp_path: Path) -> None:
    assert _topics_row(tmp_home, tmp_path, "").status == OK


def test_notify_test_carries_the_project_in_the_client_and_through_the_daemon(
    tmp_home: Path, tmp_path: Path
) -> None:
    """handsd's API `notify --test` sends through `send_test`, as the client does."""
    _write(tmp_home, tmp_path, EVENTS)
    config = load_config(PROJECT)
    posts = Recorder()
    result = asyncio.run(notify_mod.send_test(config, "hello", post=posts))
    expected = f"{PROJECT}: {notify_mod.TEST_TITLE}"
    assert [p["title"] for p in posts.sent] == [expected]
    assert result["title"] == expected


# ------------------------------------------------- the documented topic lines

ROOT = Path(__file__).parents[1]
TOPIC_LINE = re.compile(r'^\s*#?\s*(ntfy_topic|cmd_topic|who_topic|who_cmd_topic) = "([^"]*)"')
SHAPES = {
    "ntfy_topic": "hands-<project>-",
    "cmd_topic": "hands-<project>-cmd-",
    "who_topic": "who-<project>-",
    "who_cmd_topic": "whocmd-<project>-",
}


def test_every_documented_topic_line_carries_the_project() -> None:
    """§36: "the documented setup lines generate topic names that carry the
    project". Every `<key> = "…"` topic line of INTEGRATION and the README begins
    with its shape, or is the generated line the command above it prints, and
    that command's line carries the project."""
    found = []
    for doc in (ROOT / "docs" / "INTEGRATION.md", ROOT / "README.md"):
        for line in doc.read_text(encoding="utf-8").splitlines():
            if match := TOPIC_LINE.match(line):
                key, value = match.groups()
                found.append(key)
                assert value.startswith(SHAPES[key]) or value == "<the first line>", line
    assert set(found) == set(SHAPES), found
    integration = (ROOT / "docs" / "INTEGRATION.md").read_text(encoding="utf-8")
    generators = [line for line in integration.splitlines() if "token_urlsafe(16)" in line]
    printed = [re.search(r'print\("([^"]*)" \+', line) for line in generators]
    prefixes = sorted(match.group(1) for match in printed if match)
    assert len(prefixes) == len(generators) == 5, generators
    assert prefixes == sorted([*SHAPES.values(), SHAPES["cmd_topic"]]), generators


# ----------------------------------------------- this repository's kickoff


KICKOFF = (
    "Read the builder prompt with the highest mission number in the meta directory "
    "and execute the mission below its divider."
)


def test_this_repositorys_playbook_loads_with_20_rules_and_the_mission_less_kickoff() -> None:
    book = parse_playbook((ROOT / "PLAYBOOK.toml").read_text(encoding="utf-8"), path=ROOT)
    assert book.kickoff == KICKOFF
    assert len(book.rules) == 20


def test_a_kit_of_a_brief_carrying_the_new_kickoff_checks_against_this_repository(
    tmp_path: Path,
) -> None:
    """The gate of §36's kickoff: a kit of the repository's playbook and a brief
    whose kickoff line is the new one passes `hands kit check --repo <this repo>`."""
    brief = (ROOT / "meta" / "BUILDER-20-PROMPT.md").read_text(encoding="utf-8")
    old = "    Read meta/BUILDER-20-PROMPT.md and execute the mission below its divider.\n"
    assert brief.count(old) == 1
    kit = tmp_path / "kit"
    (kit / "meta").mkdir(parents=True)
    (kit / "meta" / "BUILDER-21-PROMPT.md").write_text(brief.replace(old, f"    {KICKOFF}\n"))
    (kit / "PLAYBOOK.toml").write_bytes((ROOT / "PLAYBOOK.toml").read_bytes())
    out = io.StringIO()
    code = main(["kit", "check", str(kit), "--repo", str(ROOT)], stdout=out, stderr=io.StringIO())
    assert code == 0, out.getvalue()
