"""The shipped artifacts of U10: docs, the systemd unit, the driver kit (§12, §14).

Documentation rots silently, so the parts of it that are machine-checkable are
checked here: every `hands <command>` a document names must exist, the config
block of `docs/INTEGRATION.md` must load through `hands.config`, the §10 example
in `docs/PLAYBOOK.md` must be the fixture byte for byte, and the driver kit must
still describe the CLI that exists.
"""

from __future__ import annotations

import importlib.util
import json
import re
import textwrap
import tomllib
from pathlib import Path

from hands.api import Api
from hands.config import parse_config
from hands.playbook import ACTIONS, EVENTS

ROOT = Path(__file__).parents[1]
DOCS = [
    ROOT / "README.md",
    ROOT / "docs" / "INTEGRATION.md",
    ROOT / "docs" / "PLAYBOOK.md",
    ROOT / "driver" / "CLAUDE.md",
    ROOT / "driver" / "README.md",
]
UNIT = ROOT / "systemd" / "handsd.service"
EXAMPLE = ROOT / "tests" / "fixtures" / "playbook_example.toml"

#: Words that follow `hands ` in a command without naming a command of §4.
NOT_COMMANDS = {"--help", "--version", "--project", "--json", "--socket", "<command>"}
#: `hands <command>`, where `hands` is the program and not the tail of a path
#: (`git clone …/hands repo`) — hence the lookbehind.
COMMAND_RE = re.compile(r"(?<![\w/.~-])hands (?:--\w+ [\w<>-]+ )?([a-z-]+|--[a-z-]+)")


def commands_named_in(text: str) -> list[str]:
    """Every `hands <word>` inside a code span or an indented code block.

    Prose is excluded on purpose — "drives hands from your phone" is English,
    not an invocation — so only text the reader would copy is checked.
    """
    spans = re.findall(r"`([^`]+)`", text)
    # Indented code blocks, minus their trailing comments ("# hands uses …").
    spans += [line.split("#")[0] for line in text.splitlines() if line.startswith("    ")]
    found: list[str] = []
    for span in spans:
        found += COMMAND_RE.findall(re.sub(r"\s+", " ", span))
    return found


def test_every_hands_command_named_in_the_docs_exists() -> None:
    for path in DOCS:
        where = path.relative_to(ROOT)
        named = commands_named_in(path.read_text(encoding="utf-8"))
        assert named, f"{where} names no hands command at all"
        for word in named:
            if word in NOT_COMMANDS:
                continue
            assert word in Api.COMMANDS, f"{where} names `hands {word}`, which does not exist"


def test_the_integration_config_block_loads() -> None:
    """§14 step 1's config is copied out of the doc: it has to be a real config."""
    text = (ROOT / "docs" / "INTEGRATION.md").read_text(encoding="utf-8")
    body = text.split("## 3. Write the config")[1].split("Notes that are easy")[0]
    block = textwrap.dedent(
        "\n".join(line for line in body.splitlines() if line.startswith("    "))
    ).replace("<project>", "demo")
    config = parse_config(
        tomllib.loads(block), project="demo", path=ROOT / ".hands" / "demo.toml"
    )
    assert sorted(config.roles) == ["aux", "builder"]
    assert config.ops.monitor_cmd == "watch_monitor.sh"


def test_the_playbook_doc_carries_the_section_10_example_verbatim() -> None:
    doc = (ROOT / "docs" / "PLAYBOOK.md").read_text(encoding="utf-8")
    for line in EXAMPLE.read_text(encoding="utf-8").splitlines():
        assert ("    " + line).rstrip() in doc, f"the §10 example line is missing: {line!r}"


def test_the_playbook_doc_lists_every_event_and_action() -> None:
    doc = (ROOT / "docs" / "PLAYBOOK.md").read_text(encoding="utf-8")
    for name in EVENTS + ACTIONS:
        assert name in doc, f"docs/PLAYBOOK.md does not mention `{name}` (§10)"


# ------------------------------------------------------------- systemd (§14)


def test_the_systemd_unit_is_a_user_unit_with_the_project_in_an_environment_file() -> None:
    unit = UNIT.read_text(encoding="utf-8")
    assert "EnvironmentFile=" in unit
    assert "--project ${HANDS_PROJECT}" in unit
    assert "Restart=on-failure" in unit
    assert "WantedBy=default.target" in unit  # a user unit, not multi-user.target
    assert "User=" not in unit and "Group=" not in unit  # it runs as you, by being yours
    # No login shell: ExecStart is an absolute path, not a bare name or `sh -c`.
    exec_start = [line for line in unit.splitlines() if line.startswith("ExecStart=")]
    assert len(exec_start) == 1
    assert exec_start[0].startswith("ExecStart=%h/") or exec_start[0].startswith("ExecStart=/")
    assert "sh -c" not in exec_start[0]


# ---------------------------------------------------------- driver kit (§12)


def test_the_driver_denies_every_writing_tool() -> None:
    settings = json.loads((ROOT / "driver" / "settings.json").read_text(encoding="utf-8"))
    deny = settings["permissions"]["deny"]
    for tool in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
        assert tool in deny, f"driver/settings.json must deny {tool} (§12)"
    assert "Bash(hands:*)" in settings["permissions"]["allow"]
    assert "Bash(claude:*)" in deny
    # `hands open` execs an interactive `claude --resume` (§7): not the driver's.
    assert "Bash(hands open:*)" in deny


def test_the_driver_bash_guard_selftest_passes() -> None:
    spec = importlib.util.spec_from_file_location(
        "bash_guard", ROOT / "driver" / "hooks" / "bash_guard.py"
    )
    assert spec and spec.loader
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    assert guard.selftest() == 0
    assert guard.check("hands wait --for stop,held --timeout 3600") is None
    assert guard.check("hands open job-1") is not None
