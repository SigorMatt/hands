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
import subprocess
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


def test_the_integration_config_block_loads(tmp_home: Path) -> None:
    """§14 step 1's config is copied out of the doc: it has to be a real config.

    Under `tmp_home` because §21 makes `ops.monitor_cmd` name a script that is
    really there: the doc's `~/<project>-ops/watch_monitor.sh` is created here,
    the way §14 step 4 tells the human to create theirs.
    """
    script = tmp_home / "demo-ops" / "watch_monitor.sh"
    script.parent.mkdir()
    script.write_text("#!/bin/sh\nexit 0\n")
    script.chmod(0o755)
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
    # §12/§20: MultiEdit stays. It is a known permission-rule tool name in
    # 2.1.269 — the deny-rule normalizer maps it to Edit — so the rule costs a
    # start-up warning and nothing else, and dropping it dropped coverage
    # (H-010 as amended 2026-09-12; review 3 should-fix 2).
    for tool in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
        assert tool in deny, f"driver/settings.json must deny {tool} (§12)"
    assert "Bash(hands:*)" in settings["permissions"]["allow"]
    assert "Bash(claude:*)" in deny
    # `hands open` execs an interactive `claude --resume` (§7): not the driver's.
    assert "Bash(hands open:*)" in deny


def flattened(text: str) -> str:
    """One line, single-spaced: a rule is its words, not its line wrapping."""
    return re.sub(r"\s+", " ", text).strip()


def design_rule(number: int) -> str:
    """Rule `number` of DESIGN §12's `driver/CLAUDE.md` list, flattened."""
    section = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    listing = section.split("## 12. The driver kit")[1].split("\n- `driver/settings.json`")[0]
    body = listing.split(f"\n  {number}. ")[1].split(f"\n  {number + 1}. ")[0]
    return flattened(body)


def kit_rule(number: int) -> str:
    """Rule `number` of the shipped `driver/CLAUDE.md`, flattened."""
    kit = (ROOT / "driver" / "CLAUDE.md").read_text(encoding="utf-8")
    return flattened(kit.split(f"\n{number}. ")[1].split(f"\n{number + 1}. ")[0])


def test_the_driver_kit_sends_prompts_as_files() -> None:
    """§12 rule 6 (and §4's `send` row): the prompts the architect wrote travel
    as files, so no shell ever parses them."""
    kit = (ROOT / "driver" / "CLAUDE.md").read_text(encoding="utf-8")
    assert "--prompt-file" in kit, "driver/CLAUDE.md must route prompts through --prompt-file"
    assert "--prompt-file" in kit_rule(6)
    assert "--prompt-file" in (ROOT / "docs" / "INTEGRATION.md").read_text(encoding="utf-8")


def test_the_driver_kit_says_how_a_paged_log_and_a_cut_tail_read() -> None:
    """§4's `log` and `tail` rows (H-013): the driver reads `--json`, and one
    `log` answer is one page, so the kit has to say how to read the rest of a
    stream and when a `tail` answer was cut."""
    kit = (ROOT / "driver" / "CLAUDE.md").read_text(encoding="utf-8")
    assert "--offset" in kit, "the kit must say how a --json caller reads the next page"
    assert "`more`" in kit, "and what says there is one"
    assert "truncated" in kit, "and that `tail` marks an answer its bounds cut (§4)"


def test_driver_rule_6_is_the_design_section_12_rule_6() -> None:
    """§20 (review 3 should-fix 10): v3.3 rewrote rule 6 "to match what the
    driver can do", so the kit carries that text and not a paraphrase of it."""
    assert design_rule(6), "DESIGN §12 has no rule 6 to pin the kit to"
    assert kit_rule(6) == design_rule(6)


def test_driver_rule_8_is_the_design_section_12_rule_8() -> None:
    """§22 (the v3.5 change): rule 8 became "never arm a background task; the
    human's `check` is your wake", so the kit carries DESIGN §12's words for it
    and not the v3.4 procedure. The exit-2 sentence the kit used to end this
    rule with lives elsewhere in the document (see the test below)."""
    assert design_rule(8), "DESIGN §12 has no rule 8 to pin the kit to"
    assert kit_rule(8) == design_rule(8)


#: Sentences that told a reader to arm a background wait, or that described the
#: check built on one. §11's decision paragraph and §22's first bullet retire
#: all of them: "the driver arms no background wait at all. ntfy is the human's
#: doorbell; the human's `check` is the driver's". Each is matched against the
#: flattened, lowercased document, so line wrapping cannot hide one.
ARMED_WAIT = (
    "arm the background wait",
    "arm a background wait",
    "arm the wake path",
    "background-wake check",
    "background-wake procedure",
    "background wake check",
    "background wake procedure",
    "background* bash task",
    "background bash task",
)


def test_no_shipped_document_tells_anyone_to_arm_a_background_wait() -> None:
    """§11, §22: the driver arms no background wait, so the three documents a
    driver or an installer reads may not describe one — not as a rule, not as a
    first-run step, and not as the wake check doctor prints (§12 rule 8).

    `docs/INTEGRATION.md`'s "No background tasks in a role session (§21)"
    section and the `no_background.py` recipe are about the hook that *refuses*
    background tasks; they are untouched by this, and the phrases below do not
    appear in them.
    """
    offenders = [
        f"{path.relative_to(ROOT).as_posix()}: {phrase!r}"
        for path in (
            ROOT / "driver" / "CLAUDE.md",
            ROOT / "driver" / "README.md",
            ROOT / "docs" / "INTEGRATION.md",
        )
        for flat in [flattened(path.read_text(encoding="utf-8")).lower()]
        for phrase in ARMED_WAIT
        if phrase in flat
    ]
    assert not offenders, "a document still arms the retired wait (§11, §22):\n" + "\n".join(
        offenders
    )
    # The driver in particular waits for nothing it was not told to wait for:
    # §12 rule 8 leaves it `hands wait <job>` in the foreground after an
    # approval, and `--for stop,held` is the event wait it no longer arms. The
    # command itself stays in §4 for a human at the laptop, so this is the
    # kit's rule, not a repo-wide one.
    kit = flattened((ROOT / "driver" / "CLAUDE.md").read_text(encoding="utf-8"))
    assert "hands wait --for" not in kit, "the driver kit still offers the event wait (§12 rule 8)"
    assert "hands wait <job>" in kit, "the kit must keep §12 rule 8's foreground wait"


def test_the_docs_say_the_humans_check_is_the_drivers_wake() -> None:
    """The other half of §11's decision: having removed the wait, the documents
    have to say what replaced it — ntfy for the human, `check` for the driver."""
    driver = (ROOT / "driver" / "CLAUDE.md").read_text(encoding="utf-8")
    readme = (ROOT / "driver" / "README.md").read_text(encoding="utf-8")
    integration = (ROOT / "docs" / "INTEGRATION.md").read_text(encoding="utf-8")
    for where, text in (
        ("driver/CLAUDE.md", driver),
        ("driver/README.md", readme),
        ("docs/INTEGRATION.md", integration),
    ):
        assert "check" in flattened(text).lower(), f"{where} never names the `check` wake (§11)"
    assert "ntfy" in flattened(readme).lower(), "driver/README.md never names the doorbell (§11)"
    # The kickoff walk-through is where the retired "arm the background wait"
    # stood; it now sends the reader to rule 8.
    kickoff = driver.split("## Starting a mission")[1]
    assert "rule 8" in kickoff, "the kickoff walk-through does not cite rule 8"
    assert "check" in kickoff, "the kickoff walk-through does not say what the wake is"


def test_the_docs_say_what_exit_2_means() -> None:
    """§4/§21 (review 4 should-fix 5): exit 2 stopped being only a `wait`
    timeout when `send` began refusing prompts itself, so both documents that
    tell a reader what an exit code means have to say the whole of it — the
    driver's rule 8 in particular, because rule 6 is where it meets the other 2.
    """
    integration = (ROOT / "docs" / "INTEGRATION.md").read_text(encoding="utf-8")
    driver = (ROOT / "driver" / "CLAUDE.md").read_text(encoding="utf-8")
    said = "did not deliver a completed request"
    assert said in integration, "docs/INTEGRATION.md never says what exit 2 means"
    assert said in driver, "driver/CLAUDE.md never says what exit 2 means"
    stale = [
        f"{where}: {line}"
        for where, text in (("docs/INTEGRATION.md", integration), ("driver/CLAUDE.md", driver))
        for line in text.splitlines()
        if "every other command exits 1 with the message alone" in line
        or "Exit code 2 is a timeout, not an event" in line
        or ("--prompt-file" in line and "non-zero" in line)
    ]
    assert not stale, "a document still says exit 2 is one thing:\n" + "\n".join(stale)


def test_no_shipped_sentence_says_the_prompt_cap_covers_the_whole_request() -> None:
    """Review 5 blocker 1 / H-012: two shipped sentences said the prompt-sized
    cap made the envelope safe — `docs/INTEGRATION.md` ("so anything the client
    accepts fits") and `src/hands/daemon.py` ("more than a command line can
    hold"). Twelve `--file` values of backslashes are both, so both are gone,
    and the doc says what is measured instead (§4's `send` row).
    """
    integration = (ROOT / "docs" / "INTEGRATION.md").read_text(encoding="utf-8")
    daemon_src = (ROOT / "src" / "hands" / "daemon.py").read_text(encoding="utf-8")
    # Both sentences are wrapped across lines (one of them behind `# ` comment
    # markers), so the claim is looked for in the prose, not in the layout.
    flat = {
        "docs/INTEGRATION.md": " ".join(integration.split()),
        "src/hands/daemon.py": " ".join(daemon_src.replace("#", " ").split()),
    }
    stale = [
        f"{where}: {claim!r}"
        for where, text in flat.items()
        for claim in (
            "so anything the client accepts fits",
            "more than a command line can hold",
        )
        if claim in text
    ]
    assert not stale, "a shipped sentence still says the envelope cannot overflow:\n" + "\n".join(
        stale
    )
    for said in ("whole request", "--file", "before connecting"):
        assert said in flat["docs/INTEGRATION.md"], (
            f"docs/INTEGRATION.md never says {said!r} (§4, H-012)"
        )


def test_the_driver_kit_never_claims_a_command_line_cannot_hold_punctuation() -> None:
    """The driver cannot write files (settings.json denies every writing tool),
    so a rule forbidding punctuation on a command line leaves it with no way to
    send a prompt it composed. The guard passes quoted text as text; §12 rule 6
    says so, and no corner of the kit may say otherwise (review 3 should-fix 10).
    """
    banned = "meta" + "characters"  # spelled apart: this file is not a hit
    offenders = [
        f"{where}:{n}: {line.strip()}"
        for path in tracked_files()
        if (where := path.relative_to(ROOT).as_posix()).startswith("driver/")
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if banned in line.lower()
    ]
    assert not offenders, "driver/ still claims a metacharacter rule:\n" + "\n".join(offenders)


def test_the_integration_doc_installs_the_no_background_hook_in_every_driven_repo() -> None:
    """§21: the hook that refuses background tasks is not the driver's alone.

    The harness reaps a role session's background job, so every repository
    hands drives gets the same two files — the hook and the settings that run
    it — and the doc that sets a project up is where a human finds that out.
    """
    text = (ROOT / "docs" / "INTEGRATION.md").read_text(encoding="utf-8")
    for name in (".claude/settings.json", ".claude/hooks/no_background.py"):
        assert name in text, f"docs/INTEGRATION.md never tells the human to install {name} (§21)"
    for word in ("run_in_background", "foreground", "--selftest"):
        assert word in text, f"docs/INTEGRATION.md does not say {word!r} (§21)"
    # The two files it names are the two files this repository ships.
    for name in (".claude/settings.json", ".claude/hooks/no_background.py"):
        assert (ROOT / name).is_file(), f"{name} is missing from this repository"


#: What `.claude/hooks/no_background.py` does not and cannot catch. The hook
#: reads one command line as shell text: it never runs it, never resolves a
#: variable, and treats quoted text as text — so a session that spells its
#: background job in any of these ways is refused by nothing. Review 5
#: should-fix 2 asked for one list rather than two partial ones, so the doc
#: that installs the hook is where it lives, and this pins it.
BLIND_SPOTS = [
    "bash -c",
    "eval",
    "screen -dmS",
    "tmux new -d",
    "at ",
    "systemd-run",
    "fork",
    "variable",
]


def test_the_integration_doc_lists_what_the_no_background_hook_cannot_see() -> None:
    """§21: the hook is a guardrail against the spellings a role session writes,
    not a sandbox, and the human installing it is told where it stops."""
    text = (ROOT / "docs" / "INTEGRATION.md").read_text(encoding="utf-8")
    heading = "### What the hook cannot see"
    assert heading in text, f"docs/INTEGRATION.md has no {heading!r} section (§21)"
    section = text.split(heading, 1)[1].split("\n## ", 1)[0]
    for named in BLIND_SPOTS:
        assert named in section, f"the blind-spot list does not name {named!r} (§21)"


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


# ------------------------------------------------ bootstrap retired (§18, §15)

#: The v0 dispatcher's file name, built at runtime so that this file is not
#: itself a hit: the acceptance criterion for retiring bootstrap mode is a
#: repo-wide grep for that name, and a test that spelled it would fail it.
BOOTSTRAP_DISPATCHER = "dispatch" + ".sh"
#: DESIGN §15 keeps the bootstrap sequence as history, and `meta/` is the
#: builder's record of what happened; both are allowed to name the dispatcher.
HISTORY = ("DESIGN.md", "meta/")


def tracked_files() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout
    return [ROOT / name for name in out.split("\0") if name]


def test_the_bootstrap_dispatcher_is_gone_from_the_repo() -> None:
    """§18: the v0 dispatcher and the driver's bootstrap section are removed."""
    assert not (ROOT / "bootstrap").exists(), "bootstrap/ must be deleted (§18)"
    offenders = []
    for path in tracked_files():
        where = path.relative_to(ROOT).as_posix()
        if where.startswith(HISTORY):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for n, line in enumerate(text.splitlines(), 1):
            if BOOTSTRAP_DISPATCHER in line:
                offenders.append(f"{where}:{n}: {line.strip()}")
    assert not offenders, "bootstrap mode is retired (§18); still named in:\n" + "\n".join(
        offenders
    )


def test_the_driver_kit_does_not_mention_bootstrap_mode() -> None:
    """The driver starts a mission with `hands send`, not a bootstrap dispatcher."""
    for path in (ROOT / "driver" / "CLAUDE.md", ROOT / "driver" / "README.md"):
        text = path.read_text(encoding="utf-8").lower()
        assert "bootstrap" not in text, f"{path.relative_to(ROOT)} still describes bootstrap mode"
