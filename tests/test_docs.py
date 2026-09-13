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

import pytest

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
#: Commands of §4 the CLI answers itself, with no daemon method (`kit check`, §26).
CLIENT_COMMANDS = {"kit"}
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
            assert word in Api.COMMANDS or word in CLIENT_COMMANDS, (
                f"{where} names `hands {word}`, which does not exist"
            )


def test_the_client_only_commands_are_cli_commands_and_not_daemon_methods() -> None:
    """§4 `kit check` (§26) is answered by the client with no daemon, so it is not
    in `Api.COMMANDS`; the sweep above accepts it only because the CLI has it."""
    for word in CLIENT_COMMANDS:
        assert word not in Api.COMMANDS
        result = subprocess.run(
            ["uv", "run", "hands", word, "--help"], cwd=ROOT, capture_output=True, text=True
        )
        assert result.returncode == 0, result.stderr


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
    assert "kit_dir = " in block and "kit_max_mb = " in block  # §26's two keys
    assert config.files.kit_dir == tmp_home / "Downloads"
    assert config.files.kit_max_mb == 20


def test_the_playbook_doc_carries_the_section_10_example_verbatim() -> None:
    doc = (ROOT / "docs" / "PLAYBOOK.md").read_text(encoding="utf-8")
    for line in EXAMPLE.read_text(encoding="utf-8").splitlines():
        assert ("    " + line).rstrip() in doc, f"the §10 example line is missing: {line!r}"


def test_the_playbook_doc_says_a_review_reads_from_the_last_review_commit() -> None:
    """§23, review 6's scope note: the prose — not the verbatim example, which
    carries §10's prompt already — states the review base the reviewer computes,
    keeps `{job.head_at_start}` documented, and says when it is the wrong base
    (a job that resumed a mission mid-way) and when it is the right one."""
    doc = (ROOT / "docs" / "PLAYBOOK.md").read_text(encoding="utf-8")
    prose = flattened(doc.split("## The example (DESIGN §10, verbatim)")[0])
    for must in (
        "every commit after the last `review:` commit",
        "`git log --oneline --grep='^review: ' -1`",
        "the mission's kit commit if no review exists yet",
        "`{job.head_at_start}`, `{job.head_at_end}`",
        "`{job.head_at_start}` is the wrong review base",
        "a limit resume",
        "`builder.failed` → `resume`",
        "a human re-kick",
        "exactly the job that finished",
    ):
        assert must in prose, f"docs/PLAYBOOK.md's prose does not say {must!r} (§23)"


def test_the_playbook_doc_maps_the_mission_8_detectors_to_stop_and_says_the_group_is_weaker(
) -> None:
    """§24: both detectors are `stop` rules, and the process-group fallback is
    weaker than the scope."""
    doc = (ROOT / "docs" / "PLAYBOOK.md").read_text(encoding="utf-8")
    prose = flattened(doc.split("## The example (DESIGN §10, verbatim)")[0])
    for event in ("monitor.task_killed", "monitor.orphan_processes"):
        assert f'on = "{event}" then = "stop"' in prose, f"no stop rule shown for {event}"
    assert "which is weaker" in prose
    assert "`setsid` has left the group and is not listed or killed" in prose


def test_both_docs_say_the_task_killed_cause_is_always_unknown() -> None:
    """§25: the stream cannot tell a harness reap from a `TaskStop`; the docs say
    so, name `cause` as always `unknown`, and say what the example maps it to."""
    for name in ("PLAYBOOK.md", "INTEGRATION.md"):
        doc = flattened((ROOT / "docs" / name).read_text(encoding="utf-8"))
        assert "`TaskStop`" in doc, f"docs/{name} does not name `TaskStop`"
        assert "`cause` is always `unknown`" in doc, f"docs/{name} does not say cause is unknown"
    integration = flattened((ROOT / "docs" / "INTEGRATION.md").read_text(encoding="utf-8"))
    assert "handsd re-sends the notification of every job still held" in integration


#: The key statements of INTEGRATION.md's optional section (§11, §24), each
#: true of the code today; pinned so the section cannot drift silently.
OPTIONAL_SECTION = "## Optional: notifications, the command channel and the who view"
OPTIONAL_STATEMENTS = (
    "ntfy is never shipped with hands, only spoken to",
    "All three are off unless configured",
    "**The long-term secret never goes into a notification**",
    "is logged in handsd's journal (`journalctl --user -u handsd`) and ignored",
    "`systemd/handswho.service` is an optional user unit, off unless you enable it",
    "`hands doctor` reports each of the three as on or off, never as a failure",
)


def test_the_integration_doc_has_one_optional_section_for_notify_channel_and_who() -> None:
    text = (ROOT / "docs" / "INTEGRATION.md").read_text(encoding="utf-8")
    assert text.count(OPTIONAL_SECTION) == 1, f"docs/INTEGRATION.md has no {OPTIONAL_SECTION!r}"
    section = flattened(text.split(OPTIONAL_SECTION, 1)[1].split("\n## ", 1)[0])
    for said in OPTIONAL_STATEMENTS:
        assert flattened(said) in section, f"the optional section does not say {said!r}"
    # U4's and U6's separate headings were merged into it, not left beside it.
    for old in ("Optional: approve from the phone", "### Optional: the who view"):
        assert old not in text, f"docs/INTEGRATION.md still has {old!r}"


def section_6_vocabulary(field: str) -> list[str]:
    """The `|`-separated values DESIGN §6's job-record block lists for `field`.

    `failure_reason`'s list is a comment that wraps onto a second `#` line;
    `decided_by`'s sits inside the `gate` braces up to the next comma.
    """
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    section = design.split("## 6. Job lifecycle and limits")[1].split("\nRules:")[0]
    record = flattened(section.replace("#", " "))
    if field == "decided_by":
        listing = record.split("decided_by:", 1)[1].split(",", 1)[0]
    else:
        listing = record.split("failure_reason when failed:", 1)[1].split(" gate ", 1)[0]
    values = [value.strip() for value in listing.split("|")]
    assert values and all(re.fullmatch(r"[a-z_]+", value) for value in values), values
    return values


def test_the_code_vocabularies_are_section_6s_lists() -> None:
    """Review 8 should-fix 2, H-017: `failure_reason` and `gate.decided_by` hold
    exactly the values DESIGN §6's job record lists."""
    from hands.gates import DECIDED_BY
    from hands.runner import FAILURE_REASONS

    reasons = section_6_vocabulary("failure_reason")
    assert reasons == [
        "harness_terminated", "nonzero_exit", "no_final_result",
        "error_result", "no_num_turns", "spawn_error",
    ]
    assert set(FAILURE_REASONS) == set(reasons) and len(FAILURE_REASONS) == len(reasons)
    deciders = section_6_vocabulary("decided_by")
    assert deciders == ["cli", "driver", "phone"]
    assert set(DECIDED_BY) == set(deciders) and len(DECIDED_BY) == len(deciders)


def test_the_integration_doc_names_both_vocabularies_and_the_precedence() -> None:
    """docs/INTEGRATION.md carries every §6 value and the v3.8 precedence rule."""
    doc = flattened((ROOT / "docs" / "INTEGRATION.md").read_text(encoding="utf-8"))
    for value in (*section_6_vocabulary("failure_reason"), *section_6_vocabulary("decided_by")):
        assert f"`{value}`" in doc, f"docs/INTEGRATION.md does not name `{value}`"
    for said in (
        "a cancel stays `killed` and a detected limit stays `limited`",
        "the terminating line wins even over a `success` result",
    ):
        assert said in doc, f"docs/INTEGRATION.md does not say {said!r}"
    assert "whatever else stderr says" not in doc


def test_the_integration_doc_states_section_6s_error_subtype_rule() -> None:
    """Review 10 should-fix 7: the **How a job ends** bullet says §6's rule, that a
    `result` of subtype `error` (the `error_*` family) fails whatever `is_error`
    says, and that `done` needs a final `success` result carrying `num_turns`.
    The runner side is `test_runner.py`'s
    `test_an_error_subtype_fails_as_an_error_even_when_is_error_is_false`."""
    design = flattened((ROOT / "DESIGN.md").read_text(encoding="utf-8"))
    assert "with a `result` of subtype `error` (`error_result`)" in design
    doc = flattened((ROOT / "docs" / "INTEGRATION.md").read_text(encoding="utf-8"))
    for said in (
        "A job is `failed` when the process ends without a final `result` event, "
        "with a `result` of subtype `error`",
        "`error_max_turns` included, whatever its `is_error` says",
        "a final `result` of subtype `success` carrying `num_turns`",
    ):
        assert said in doc, f"docs/INTEGRATION.md does not say {said!r}"


#: The closed phone loop (§26, §27 "the apply from the kit", REVIEW-10 SF2): one
#: section, phone only — kit, buttons, `go`, buzz — and the statements that must
#: be in it, each a text the code prints or does.
LOOP_SECTION = "### The closed loop, from the phone"
LOOP_STATEMENTS = (
    "`hands kit check",
    "`kit <secret>`",
    "`kit received <name> <bytes> <sha256>`",
    "`Apply ~/Downloads/`",
    "The loop is phone only: kit, buttons, `go`, buzz.",
    "handsd files the apply itself",
    "`origin: kit`",
    "`apply <name>`",
    "`kit.refused`",
    "handsd never unzips the kit",
    "the first line of `KIT.md`",
    "`plan: kit <name>`",
    "`go <secret>`",
    "`[series] kickoff`",
    "`go: builder job <id> <state>`",
    "`hands: the pipeline stopped`",
    "the driver is the inspector",
    "never required for the loop",
    "No kit has been fetched from a real ntfy attachment",
    "No `go` has been sent from a real phone",
    "`hands who` matches an interactive session to its transcript through "
    "`~/.claude/sessions/<pid>.json`",
    "the line says `transcript: by directory`",
    "never shown under it",
)


def test_the_integration_doc_describes_the_closed_phone_loop_once() -> None:
    """§26: `docs/INTEGRATION.md` describes the loop end to end, phone only, in one
    place (inside the optional phone section), and says what is unproven."""
    text = (ROOT / "docs" / "INTEGRATION.md").read_text(encoding="utf-8")
    assert text.count(LOOP_SECTION) == 1, f"docs/INTEGRATION.md has no {LOOP_SECTION!r}"
    optional = text.split(OPTIONAL_SECTION, 1)[1].split("\n## ", 1)[0]
    assert LOOP_SECTION in optional, "the loop is not inside the optional phone section"
    section = flattened(text.split(LOOP_SECTION, 1)[1].split("\n### ", 1)[0].split("\n## ")[0])
    for said in LOOP_STATEMENTS:
        assert flattened(said) in section, f"the loop section does not say {said!r}"
    # REVIEW-10 SF2: the apply is no longer sent from the laptop or by the driver.
    for gone in ("nothing on the phone can start the apply", "sent from the laptop",
                 "hands send --role builder"):
        assert gone not in section, f"the loop section still says {gone!r}"


def test_the_origin_listings_name_kit() -> None:
    """§6 (v3.10): `origin (driver|playbook|cli|limit|phone|kit)`; INTEGRATION and
    PLAYBOOK say a `kit` job exists and un-pauses a stopped pipeline when it starts."""
    from hands.playbook import UNPAUSE_ORIGINS
    from hands.spool import ORIGINS

    design = flattened((ROOT / "DESIGN.md").read_text(encoding="utf-8"))
    assert "origin (driver|playbook|cli|limit|phone|kit)" in design
    assert ORIGINS == {"driver", "playbook", "cli", "limit", "phone", "kit"}
    assert UNPAUSE_ORIGINS == {"cli", "phone", "kit"}
    integration = flattened((ROOT / "docs" / "INTEGRATION.md").read_text(encoding="utf-8"))
    assert "`hands jobs --origin kit`" in integration
    playbook = flattened((ROOT / "docs" / "PLAYBOOK.md").read_text(encoding="utf-8"))
    assert "A `go` job or a kit's apply (`origin: kit`), like a `cli` send, un-pauses" in playbook


def test_the_handbook_says_handsd_files_the_apply_from_a_phone_kit() -> None:
    """§27: the apply prompt of §3 is filed held by handsd for a kit sent from the
    phone; the commit message is KIT.md's first line, else `plan: kit <name>`."""
    handbook = flattened((ROOT / "docs" / "ARCHITECT-HANDBOOK.md").read_text(encoding="utf-8"))
    section_3 = handbook.split("## 3. Kit anatomy", 1)[1].split("## 4.", 1)[0]
    for said in ("handsd files it as a held builder job", "the first line of `KIT.md`",
                 "`plan: kit <name>`"):
        assert said in section_3, f"handbook §3 does not say {said!r}"
    assert "sent by the human or the driver, gated" not in section_3
    section_11 = handbook.split("## 11. `hands kit check`", 1)[1].split("## 12.", 1)[0]
    assert "`plan: mission <N> kit`" not in section_11
    assert "the first line of `KIT.md`" in section_11


def test_the_readme_names_kit_check_go_and_the_kit_transport() -> None:
    readme = flattened((ROOT / "README.md").read_text(encoding="utf-8"))
    for said in ("`hands kit check", "`go <secret>`", "`kit <secret>`", "kit_dir",
                 "kit_max_mb", "docs/ARCHITECT-HANDBOOK.md"):
        assert said in readme, f"README.md does not mention {said}"


def test_the_readme_names_who_the_phone_channel_and_the_new_monitor_events() -> None:
    readme = flattened((ROOT / "README.md").read_text(encoding="utf-8"))
    for said in ("`hands who`", "`handswho`", "cmd_topic", "monitor.task_killed",
                 "monitor.orphan_processes"):
        assert said in readme, f"README.md does not mention {said}"


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


def test_the_handswho_unit_mirrors_handsd_and_is_off_unless_enabled() -> None:
    """§24: `handswho` ships as an optional user unit, off unless enabled."""
    unit = (ROOT / "systemd" / "handswho.service").read_text(encoding="utf-8")
    assert "EnvironmentFile=%h/.config/hands.env" in unit
    assert "--project ${HANDS_PROJECT}" in unit
    assert "Restart=on-failure" in unit
    assert "WantedBy=default.target" in unit
    assert "User=" not in unit and "Group=" not in unit
    exec_start = [line for line in unit.splitlines() if line.startswith("ExecStart=")]
    assert exec_start == ["ExecStart=%h/.local/bin/handswho --project ${HANDS_PROJECT}"]
    # Optional: the install recipe enables it only as a step the human takes.
    assert "systemctl --user enable --now handswho" in unit
    scripts = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert scripts["project"]["scripts"]["handswho"] == "hands.who:main"


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
    and not the v3.4 procedure. v3.6 put the exit-2 sentence back at the end
    of the rule, so the kit's rule ends with it too (see the test below)."""
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


#: The other half of the same retired claim, one phrase per sentence that was
#: on disk: not "arm a wait" but "the driver is the one waiting". These are
#: comments, docstrings and prose — `hands wait --for` itself is unchanged and
#: still right for a human at the laptop, so what is pinned is who is said to
#: run it, and the list is the sentences that were there, not a general rule.
DRIVER_WAITS = (
    "driver's wake path",
    "driver blocked on",
    "wakes a driver",
    "waking the driver",
    "the driver arms the wait",
    "driver re-arms",
    "the driver runs `hands wait",
    "the driver types `--for",
    "the driver kit types",
    "driver kit's `hands wait",
    "driver kit's own `--for",
    "a background wait can be told apart",
    "a background `wait --for`",
    # tests/test_playbook.py's pause test (review 6 should-fix 1).
    "not woken by a pause",
)

#: The retired claim that the wake path was still an open question, which
#: README.md kept after §11 answered it and doctor stopped printing the
#: procedure (review 6 blocker 1). Specific enough that §16's own open
#: questions, which are legitimate, do not match.
WAKE_STILL_OPEN = (
    "wakes an idle interactive claude code session",
    "prints the procedure that answers it",
)

#: Text-ness is decided by content, not by name (review 7 should-fix 4): a file
#: is binary when its first block holds a NUL byte, and every other tracked file
#: is read, whatever its suffix — a `.sh`, `.yml`, `.rst`, `uv.lock` or
#: `.gitignore` alike.
SNIFF_BYTES = 8192

#: Tracked text the sweep does not read, by path, each for a reason. `meta/`
#: history is excluded class by class rather than `meta/` whole, so a live
#: instruction file under `meta/` (`BUILDER-*-PROMPT.md`, `REVIEW-PROTOCOL.md`,
#: `BACKLOG.md`, `ROADMAP.md`, or one added later) is read by default.
SWEEP_EXCLUDED = (
    # The builder's historical state: reports, reviews, findings, the journal,
    # plan and checkpoint, prototypes and drafts quote the retired sentences
    # verbatim, and §20 forbids rewriting a report.
    "meta/reviews/",
    "meta/findings/",
    "meta/prototypes/",
    "meta/drafts/",
    "meta/journal.md",
    "meta/plan.md",
    "meta/CHECKPOINT.md",
    "meta/FINAL-REPORT-",
    # §11's History paragraph and the changelogs quote the retired model, and
    # builders do not edit DESIGN.md (CLAUDE.md).
    "DESIGN.md",
    # The mission 10 kit as committed at 61e1486, byte for byte: a fixture of
    # `hands kit check` (tests/test_kit.py), history like the kit commit itself.
    "tests/fixtures/kit-mission-10/",
    # This file: it holds the phrase lists, so every phrase is a hit in it.
    "tests/test_docs.py",
)

#: A live file that may carry one retired phrase, narrowly: (path, phrase) →
#: reason. Architect files are not edited by builders, so a hit in one that is
#: history-in-a-live-file is allowed here by name, never by path class.
SWEEP_ALLOWED = {
    ("meta/BUILDER-1-PROMPT.md", "background-wake check"): (
        "mission 1's brief specifies the doctor output of its own U10, which §11 "
        "and §22 later retired; the brief is the architect's, and mission 1 is done"
    ),
}


def is_swept(where: str, head: bytes) -> bool:
    """Is the tracked file at repo-relative `where`, whose first bytes are `head`,
    read by the sweep? Text by content; excluded only by `SWEEP_EXCLUDED`."""
    return not where.startswith(SWEEP_EXCLUDED) and b"\0" not in head[:SNIFF_BYTES]


def swept_files() -> list[str]:
    """Every tracked text file outside `SWEEP_EXCLUDED`, repo-relative.

    `git ls-files` is the source: without git, or outside a checkout, the
    subprocess raises and the test errors — it never passes on an empty list.
    """
    swept = []
    for path in tracked_files():
        where = path.relative_to(ROOT).as_posix()
        if not path.is_file():
            continue  # a tracked path deleted in the working tree
        with path.open("rb") as handle:
            head = handle.read(SNIFF_BYTES)
        if is_swept(where, head):
            swept.append(where)
    return swept


@pytest.mark.parametrize(
    ("where", "head", "swept"),
    [
        # Any suffix, or none, is read when its content is text.
        ("scripts/new.sh", b"#!/bin/sh\necho hi\n", True),
        (".github/workflows/ci.yml", b"on: push\n", True),
        ("docs/NOTES.rst", b"Notes\n=====\n", True),
        ("setup.cfg", b"[metadata]\n", True),
        ("tox.ini", b"[tox]\n", True),
        ("uv.lock", b"version = 1\n", True),
        (".gitignore", b".venv/\n", True),
        ("empty.txt", b"", True),
        # A NUL in the first block is binary, whatever the name says.
        ("docs/logo.png", b"\x89PNG\r\n\x1a\n\0\0\0\rIHDR", False),
        ("README.md", b"text then a NUL\0", False),
        ("late.bin", b"a" * (SNIFF_BYTES - 1) + b"\0", False),
        # Live instruction files under meta/ are read.
        ("meta/REVIEW-PROTOCOL.md", b"# protocol\n", True),
        ("meta/BUILDER-8-PROMPT.md", b"# mission 8\n", True),
        ("meta/BUILDER-12-PROMPT.md", b"# a later mission\n", True),
        ("meta/BACKLOG.md", b"# backlog\n", True),
        ("meta/ROADMAP.md", b"# roadmap\n", True),
        # meta/ history is not.
        ("meta/journal.md", b"# journal\n", False),
        ("meta/reviews/REVIEW-7.md", b"# review\n", False),
        ("meta/findings/FINDINGS.md", b"# findings\n", False),
        ("meta/prototypes/claudewho.py", b"import os\n", False),
        ("meta/drafts/FINAL-REPORT-8.md", b"# draft\n", False),
        ("meta/plan.md", b"# plan\n", False),
        ("meta/CHECKPOINT.md", b"# checkpoint\n", False),
        ("meta/FINAL-REPORT-7.md", b"# report\n", False),
        ("DESIGN.md", b"# design\n", False),
        ("tests/test_docs.py", b"import re\n", False),
    ],
    ids=lambda value: value if isinstance(value, str) else None,
)
def test_the_sweep_decides_text_by_content_and_excludes_meta_history_by_path(
    where: str, head: bytes, swept: bool
) -> None:
    """Review 7 should-fix 4: text by a NUL in the first block, not a suffix list;
    `meta/` history out by path, live `meta/` instructions in."""
    assert is_swept(where, head) is swept


def test_the_sweep_reads_every_tracked_text_file_and_only_excludes_path_classes() -> None:
    """Review 6 should-fix 1: a pinned phrase survived in a file the pin did not
    read. The sweep's reach is the tracked tree, so a new file is read the day it
    is added; this asserts the tree really was read, not an empty listing."""
    swept = swept_files()
    for must in (
        "README.md",
        "docs/INTEGRATION.md",
        "driver/CLAUDE.md",
        "src/hands/doctor.py",
        "tests/test_playbook.py",
        "tests/test_doctor.py",
        "systemd/handsd.service",
        "scripts/check",
        "uv.lock",
        ".gitignore",
        "meta/REVIEW-PROTOCOL.md",
        "meta/BUILDER-8-PROMPT.md",
        "meta/BACKLOG.md",
        "meta/ROADMAP.md",
    ):
        assert must in swept, f"the sweep does not read {must}"
    assert len(swept) >= 60, f"the sweep read only {len(swept)} files: {swept}"
    assert not [where for where in swept if where.startswith(SWEEP_EXCLUDED)]
    for never in ("meta/journal.md", "meta/plan.md", "meta/CHECKPOINT.md", "DESIGN.md"):
        assert never not in swept
    # Every tracked file is either read or excluded by a named path class: no
    # third group of silently skipped text.
    unread = [
        where
        for path in tracked_files()
        for where in [path.relative_to(ROOT).as_posix()]
        if where not in swept and not where.startswith(SWEEP_EXCLUDED)
    ]
    assert not unread, f"tracked files neither swept nor excluded by path: {unread}"


def test_nothing_shipped_says_the_driver_arms_or_blocks_on_a_wait() -> None:
    """§11, §22: the driver arms no background wait and blocks on nothing, so
    no shipped sentence may say it does — not as a rule, not as a first-run
    step, not as the wake check doctor prints (§12 rule 8), and not as the
    reason a comment gives for `--for`, for exit 2 or for a `pipeline` kind.
    Nor may one say the wake path is still an open question (§11 answered it).

    Every tracked text file is read (`swept_files`), so a phrase cannot survive
    in a file a list forgot. The phrases were taken from the sentences that were
    on disk, so this proves those do not come back, not that no new spelling of
    the claim exists; the rendered doctor output and rule 8 are pinned by what
    they must say (below, and in tests/test_doctor.py).

    `docs/INTEGRATION.md`'s "No background tasks in a role session (§21)"
    section and the `no_background.py` recipe are about the hook that *refuses*
    background tasks; they are untouched by this, and the phrases below do not
    appear in them.
    """
    hits = [
        (where, phrase)
        for where in swept_files()
        for flat in [
            flattened((ROOT / where).read_text(encoding="utf-8", errors="replace")).lower()
        ]
        for phrase in ARMED_WAIT + DRIVER_WAITS + WAKE_STILL_OPEN
        if phrase in flat
    ]
    offenders = [
        f"{where}: {phrase!r}" for where, phrase in hits if (where, phrase) not in SWEEP_ALLOWED
    ]
    assert not offenders, "a shipped sentence still arms the retired wait (§11, §22):\n" + (
        "\n".join(offenders)
    )
    # An allowance names a hit that is on disk; one that no longer hits is removed.
    stale = sorted(set(SWEEP_ALLOWED) - set(hits))
    assert not stale, f"sweep allowances that no longer match anything: {stale}"
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
    have to say what replaced it — ntfy for the human, `check` for the driver.

    Review 6 should-fix 2: "check" appearing anywhere in a document was already
    true before the change, so the driver's rule is asserted on rule 8's own
    words and the two human-facing documents on `check` standing within a few
    words before the wake it is said to be (driver/README.md shows `check` as a
    code block and calls it "the driver's wake" right after)."""
    rule = kit_rule(8)
    assert rule.startswith("Never arm a background task."), f"rule 8 does not forbid it: {rule}"
    assert "`check` is your wake" in rule, f"rule 8 does not name `check` as the wake: {rule}"
    assert "hands wait --for" not in rule, "rule 8 still offers the event wait"
    driver = (ROOT / "driver" / "CLAUDE.md").read_text(encoding="utf-8")
    readme = (ROOT / "driver" / "README.md").read_text(encoding="utf-8")
    integration = (ROOT / "docs" / "INTEGRATION.md").read_text(encoding="utf-8")
    for where, text in (("driver/README.md", readme), ("docs/INTEGRATION.md", integration)):
        # `check`, then at most four words, then the wake: "`check` is its
        # wake", "check That is the driver's wake".
        assert re.search(r"\bcheck\b`?\W{0,3}(?:[\w'’]+\W+){0,4}[\w'’]*wake", flattened(text)), (
            f"{where} never says `check` is the driver's wake (§11)"
        )
    assert "ntfy" in flattened(readme).lower(), "driver/README.md never names the doorbell (§11)"
    # The kickoff walk-through is where the retired "arm the background wait"
    # stood; it now sends the reader to rule 8 and names `check` as the wake.
    kickoff = driver.split("## Starting a mission")[1]
    assert "rule 8" in kickoff, "the kickoff walk-through does not cite rule 8"
    assert "`check`" in kickoff, "the kickoff walk-through does not say what the wake is"


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
    # H-014: continuing a finished sub-agent runs it in the background, and the
    # call carries no background input for the hook to refuse (mission 7a U2).
    "SendMessage",
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
#: So is the mission 10 kit fixture, whose DESIGN.md is v3.9 byte for byte.
HISTORY = ("DESIGN.md", "meta/", "tests/fixtures/kit-mission-10/")


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
