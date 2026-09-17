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
from hands.daemon import NOTIFY_KINDS, START_FOLD_S
from hands.playbook import ACTIONS, EVENTS

ROOT = Path(__file__).parents[1]
DOCS = [
    ROOT / "README.md",
    ROOT / "docs" / "INTEGRATION.md",
    ROOT / "docs" / "PLAYBOOK.md",
    ROOT / "driver" / "CLAUDE.md",
    ROOT / "driver" / "README.md",
]
UNIT = ROOT / "systemd" / "handsd@.service"
EXAMPLE = ROOT / "tests" / "fixtures" / "playbook_example.toml"

#: Words that follow `hands ` in a command without naming a command of §4.
NOT_COMMANDS = {"--help", "--version", "--project", "--json", "--socket", "<command>"}
#: Commands of §4 the CLI answers itself, with no daemon method (`kit check`, §26).
CLIENT_COMMANDS = {"kit", "migrate-spool"}  # §29: migrate-spool needs no daemon
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
    assert sorted(config.roles) == ["architect", "aux", "builder", "driver"]
    assert config.role("driver").permission_flags == ""  # §27
    assert config.role("driver").cwd == tmp_home / "hands-driver" / "hands"  # m11 U6
    # §31 (mission 15 U6): the architect role's table is in the doc's config too.
    assert config.role("architect").permission_flags == ""
    assert config.role("architect").cwd == tmp_home / "hands-architect" / "hands"
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


def test_the_playbook_doc_maps_the_mission_8_detectors_and_says_the_group_is_weaker() -> None:
    """§24, §32: the prose shows `monitor.orphan_processes` as a `stop` rule and
    `monitor.task_killed` as a `notify` rule, says why (the detector cannot tell a
    harness reap, a `TaskStop` or a reaped long foreground command apart; the job
    that ends `failed` is what stops), and the process-group fallback is weaker
    than the scope."""
    doc = (ROOT / "docs" / "PLAYBOOK.md").read_text(encoding="utf-8")
    prose = flattened(doc.split("## The example (DESIGN §10, verbatim)")[0])
    assert 'on = "monitor.orphan_processes" then = "stop"' in prose
    assert 'on = "monitor.task_killed" then = "notify"' in prose
    assert 'on = "monitor.task_killed" then = "stop"' not in prose
    for must in (
        "a long foreground command the harness moved to the background and then reaped",
        "a job that ends `failed` is what stops",
        "H-034",
    ):
        assert must in prose, f"docs/PLAYBOOK.md's prose does not say {must!r} (§32)"
    assert "which is weaker" in prose
    assert "`setsid` has left the group and is never killed" in prose
    assert "listed with `killed: false` while it carries the job's `HANDS_JOB` mark" in prose


#: §32's docs sweep: sentences that said a killed task stops the pipeline, each
#: in the file that carried it before mission 16 U5.
TASK_KILLED_STOP_SAYINGS = (
    ("README.md", "`PLAYBOOK.toml` stops on both"),
    ("docs/INTEGRATION.md", "the example playbook maps the event to `stop`"),
    ("docs/ARCHITECT-HANDBOOK.md", "`task_killed`/`orphan_processes` → `stop`"),
    ("docs/PLAYBOOK.md", "DESIGN §24 puts both in the example playbook"),
)


def test_no_doc_still_says_a_killed_task_stops_the_series() -> None:
    """§32: `monitor.task_killed` maps to `notify` in this repository's playbook and
    both templates; the docs that said it stops say `notify` now. Only the sentences
    listed are checked, not every phrasing a doc could use."""
    for name, said in TASK_KILLED_STOP_SAYINGS:
        text = flattened((ROOT / name).read_text(encoding="utf-8"))
        assert said not in text, f"{name} still says {said!r}"
    for name in ("README.md", "docs/INTEGRATION.md", "docs/ARCHITECT-HANDBOOK.md"):
        text = flattened((ROOT / name).read_text(encoding="utf-8"))
        assert "`notify`" in text and "task_killed" in text, name


def test_both_docs_say_the_task_killed_cause_is_always_unknown() -> None:
    """§25: docs/PLAYBOOK.md and docs/INTEGRATION.md each name `TaskStop` and say
    "`cause` is always `unknown`"; INTEGRATION.md also says (§31) that handsd does
    not re-send the held buttons after a restart and that the one notification
    lists every job still held."""
    for name in ("PLAYBOOK.md", "INTEGRATION.md"):
        doc = flattened((ROOT / "docs" / name).read_text(encoding="utf-8"))
        assert "`TaskStop`" in doc, f"docs/{name} does not name `TaskStop`"
        assert "`cause` is always `unknown`" in doc, f"docs/{name} does not say cause is unknown"
    # §31 (review 14 should-fix 1): after a restart the buttons are not re-sent;
    # the one `handsd started` notification lists the jobs instead.
    integration = flattened((ROOT / "docs" / "INTEGRATION.md").read_text(encoding="utf-8"))
    assert "handsd does not re-send them" in integration
    assert "notification lists every job still held" in integration


def test_the_sentence_under_the_verbatim_example_says_a_killed_task_notifies_here() -> None:
    """§33 (review 16 should-fix 8), §32, H-034: the reading of §10's example under
    its verbatim copy still says killed tasks stop (the copy is §10's), so it says
    that this repository and the templates only `notify` on a killed task."""
    doc = (ROOT / "docs" / "PLAYBOOK.md").read_text(encoding="utf-8")
    after = flattened(doc.split("## The example (DESIGN §10, verbatim)", 1)[1])
    reading = after.split("Read it as a sentence:", 1)[1]
    assert "H-034" in reading, "the reading under the verbatim example does not name H-034"
    assert "`notify`" in reading, "the reading under the verbatim example does not say `notify`"
    assert "`PLAYBOOK.toml`" in reading and "templates" in reading, reading


#: The key statements of INTEGRATION.md's optional section (§11, §24), each
#: true of the code today; pinned so the section cannot drift silently.
OPTIONAL_SECTION = "## Optional: notifications, the command channel and the who view"
OPTIONAL_STATEMENTS = (
    "ntfy is never shipped with hands, only spoken to",
    "All three are off unless configured",
    "**The long-term secret never goes into a notification**",
    "is logged in handsd's journal (`journalctl --user -u handsd@<project>`) and ignored",
    "`systemd/handswho@.service` is an optional user unit, off unless you enable it",
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
    assert deciders == ["cli", "driver", "phone", "playbook"]
    # H-031, resolved by DESIGN v3.15: §6 now lists §31's `playbook`, so the
    # vocabulary in code is §6's list exactly.
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


#: docs/INTEGRATION.md's `done` statement, one string (REVIEW-11 should-fix 4).
DONE_STATEMENT = (
    "A job that finished and is none of those is `done`: claude exited 0 with a "
    "final `result` of subtype `success` carrying `num_turns`, and the line never "
    "appeared."
)

#: Each §6 `failure_reason` value: the clause of the doc's `failed` sentence that
#: states it, and the clause of DONE_STATEMENT that rules it out.
FAILURE_REASON_CLAUSES = {
    "no_final_result": ("when the process ends without a final `result` event",
                        "with a final `result`"),
    "error_result": ("with a `result` of subtype `error`", "of subtype `success`"),
    "no_num_turns": ("without `num_turns`", "carrying `num_turns`"),
    "nonzero_exit": ("when it exits non-zero without a limit", "claude exited 0"),
    "spawn_error": ("when it could not be spawned", "A job that finished"),
    "harness_terminated": ("when stderr carries the harness's", "the line never appeared"),
}


def test_the_integration_doc_pins_done_against_each_failure_reason() -> None:
    """Review 11 should-fix 4, DESIGN §28: the **How a job ends** `done` statement
    is one exact string, each §6 `failure_reason` value is stated as a `failed`
    cause that the `done` statement rules out, and no other sentence of the doc
    calls a failing result (an `error` subtype, `is_error`, a non-zero exit, or
    any `failure_reason` value) `done`."""
    reasons = section_6_vocabulary("failure_reason")
    assert set(FAILURE_REASON_CLAUSES) == set(reasons)
    assert len(FAILURE_REASON_CLAUSES) == len(reasons)
    doc = flattened((ROOT / "docs" / "INTEGRATION.md").read_text(encoding="utf-8"))
    assert doc.count(DONE_STATEMENT) == 1, "docs/INTEGRATION.md does not say the `done` statement"
    bullet = doc.split("**How a job ends**", 1)[1].split(" - **", 1)[0]
    failed = bullet.split("A job is `failed` ", 1)[1].split(DONE_STATEMENT, 1)[0]
    listing = bullet.split("The record's `failure_reason` says why a job failed, one value each: ",
                           1)[1].split(" — ", 1)[0]
    assert sorted(v.strip().strip("`") for v in listing.split(",")) == sorted(reasons)
    for value in reasons:
        cause, ruled_out = FAILURE_REASON_CLAUSES[value]
        assert cause in failed, f"`{value}`: the `failed` sentence does not say {cause!r}"
        assert ruled_out in DONE_STATEMENT, f"`{value}`: `done` does not say {ruled_out!r}"
    failing = ("error", "non-zero", "nonzero", "exited 1", *reasons)
    assert not any(word in DONE_STATEMENT for word in failing)
    for sentence in re.split(r"(?<=[.;:])\s+", doc.replace(DONE_STATEMENT, "")):
        if "`done`" in sentence:
            said = [word for word in failing if word in sentence]
            assert not said, f"docs/INTEGRATION.md calls {said} `done`: {sentence!r}"


def how_a_job_ends() -> str:
    """docs/INTEGRATION.md's **How a job ends** bullet, flattened."""
    doc = flattened((ROOT / "docs" / "INTEGRATION.md").read_text(encoding="utf-8"))
    return doc.split("**How a job ends**", 1)[1].split(" - **", 1)[0]


def doc_failure_reason_order() -> list[str]:
    """The bullet's `failure_reason` list, in the order the doc states it."""
    listing = how_a_job_ends().split(
        "The record's `failure_reason` says why a job failed, one value each: ", 1
    )[1].split(" — ", 1)[0]
    return [value.strip().strip("`") for value in listing.split(",")]


#: REVIEW-12 should-fix 8, DESIGN §29: one row per `failure_reason`, in the doc's
#: order — the value, then a finished run (parsed-stream fields, exit code) where
#: that value holds and no earlier one does, with as many later ones holding as
#: can. `spawn_error` has no run: no process exists, so nothing else can hold.
FAILURE_REASON_ORDER: tuple[tuple[str, dict[str, object] | None, int | None], ...] = (
    ("harness_terminated", {"harness_terminated": True}, 1),
    ("no_final_result", {}, 1),
    ("error_result", {"saw_result": True, "subtype": "error_max_turns"}, 1),
    ("nonzero_exit", {"saw_result": True, "subtype": "success"}, 1),
    ("no_num_turns", {"saw_result": True, "subtype": "success"}, 0),
    ("spawn_error", None, None),
)

#: A run that is `done`: exit 0, a final `success` result carrying `num_turns`.
DONE_RUN: dict[str, object] = {"saw_result": True, "subtype": "success", "num_turns": 3}


def test_the_failure_reason_table_is_the_doc_order_unsorted() -> None:
    """REVIEW-12 should-fix 8: the doc's list, compared unsorted, is the table's
    order and the runner's `FAILURE_REASONS` order; the table covers §6's values;
    and the doc says the order is the precedence."""
    from hands.runner import FAILURE_REASONS

    order = [value for value, _, _ in FAILURE_REASON_ORDER]
    assert sorted(order) == sorted(section_6_vocabulary("failure_reason"))
    assert doc_failure_reason_order() == order, "the doc's `failure_reason` order changed"
    assert list(FAILURE_REASONS) == order, "the runner's `failure_reason` order changed"
    assert f"`{order[-1]}` — the first that holds, in that order;" in how_a_job_ends()


@pytest.mark.parametrize(
    ("position", "value", "fields", "exit_code"),
    [(i, *row) for i, row in enumerate(FAILURE_REASON_ORDER)],
    ids=[row[0] for row in FAILURE_REASON_ORDER],
)
def test_each_failure_reason_holds_at_its_doc_position(
    position: int, value: str, fields: dict[str, object] | None, exit_code: int | None
) -> None:
    """REVIEW-12 should-fix 8, §6, §29: `value` sits at `position` in the doc's
    list, and the runner records it for a run where it and later values hold but
    no earlier one does."""
    from hands.runner import _final_state, _Parsed

    assert doc_failure_reason_order().index(value) == position
    if fields is None:
        return
    parsed = _Parsed(**fields)  # type: ignore[arg-type]
    assert _final_state(parsed, exit_code, cancelled=False) == ("failed", value)


#: REVIEW-12 should-fix 8: the doc's precedence clauses, in the order it states
#: them, each with runs (parsed-stream fields, exit code, cancelled) and the
#: (state, failure_reason) the runner must record for every one of them.
PRECEDENCE = (
    ("a cancel stays `killed`",
     [({**DONE_RUN, "harness_terminated": line}, 0, True) for line in (True, False)]
     + [({"harness_terminated": True}, 1, True)],
     ("killed", None)),
    ("a detected limit stays `limited`",
     [({**DONE_RUN, "harness_terminated": line, "limit_category": "rate_limit"}, 0, False)
      for line in (True, False)]
     + [({"harness_terminated": True, "limit_category": "rate_limit"}, 1, False)],
     ("limited", None)),
    ("terminating line or not", [], None),
    # REVIEW-13 should-fix 8, DESIGN §30: both a cancel and a limit hold.
    ("a job both cancelled and over a limit is `killed`: `killed` wins over `limited`",
     [({**DONE_RUN, "harness_terminated": line, "limit_category": "rate_limit"}, 0, True)
      for line in (True, False)]
     + [({"harness_terminated": True, "limit_category": "rate_limit"}, 1, True),
        ({"limit_category": "rate_limit"}, None, True)],
     ("killed", None)),
    ("otherwise the terminating line wins even over a `success` result",
     [({**DONE_RUN, "harness_terminated": True}, 0, False)],
     ("failed", "harness_terminated")),
)


@pytest.mark.parametrize(("clause", "runs", "expected"), PRECEDENCE,
                         ids=["killed", "limited", "line-or-not", "killed-over-limited",
                              "line-wins"])
def test_the_doc_states_each_precedence_clause_and_the_runner_applies_it(
    clause: str,
    runs: list[tuple[dict[str, object], int, bool]],
    expected: tuple[str, str | None] | None,
) -> None:
    """REVIEW-12 should-fix 8, §6, §29: the **How a job ends** precedence
    sentence says `clause` at its place among the others, and the runner records
    `expected` for each of `runs`."""
    from hands.runner import _final_state, _Parsed

    sentence = how_a_job_ends().split("Precedence: ", 1)[1].split(" Only the line's", 1)[0]
    places = [sentence.find(said) for said, _, _ in PRECEDENCE]
    assert clause in sentence, f"the precedence sentence does not say {clause!r}"
    assert places == sorted(places), "the precedence clauses are out of order"
    for fields, exit_code, cancelled in runs:
        parsed = _Parsed(**fields)  # type: ignore[arg-type]
        assert _final_state(parsed, exit_code, cancelled=cancelled) == expected


def test_a_run_that_is_none_of_the_failures_is_done() -> None:
    """§6: the `done` statement's run records `done` with a null reason."""
    from hands.runner import _final_state, _Parsed

    parsed = _Parsed(**DONE_RUN)  # type: ignore[arg-type]
    assert _final_state(parsed, 0, cancelled=False) == ("done", None)
    assert DONE_STATEMENT in how_a_job_ends()


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
    """§6 (v3.14): `origin (driver|playbook|cli|limit|phone|kit|architect)`;
    INTEGRATION and PLAYBOOK say a `kit` job exists and un-pauses a stopped
    pipeline when it starts. `architect` is the value §31 gives the held apply
    `hands kit file` will file; here it is only legal (mission 15 U0, U3)."""
    from hands.playbook import UNPAUSE_ORIGINS
    from hands.spool import ORIGINS

    design = flattened((ROOT / "DESIGN.md").read_text(encoding="utf-8"))
    assert "origin (driver|playbook|cli|limit|phone|kit|architect)" in design
    assert ORIGINS == {"driver", "playbook", "cli", "limit", "phone", "kit", "architect"}
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
    """§29: templated; the instance name is the project, the env file is per project."""
    unit = UNIT.read_text(encoding="utf-8")
    assert "EnvironmentFile=%h/.config/hands/%i.env" in unit
    assert "--project %i" in unit
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
    unit = (ROOT / "systemd" / "handswho@.service").read_text(encoding="utf-8")
    assert "EnvironmentFile=%h/.config/hands/%i.env" in unit
    assert "--project %i" in unit
    assert "Restart=on-failure" in unit
    assert "WantedBy=default.target" in unit
    assert "User=" not in unit and "Group=" not in unit
    exec_start = [line for line in unit.splitlines() if line.startswith("ExecStart=")]
    assert exec_start == ["ExecStart=%h/.local/bin/handswho --project %i"]
    # Optional: the install recipe enables it only as a step the human takes.
    assert "systemctl --user enable --now handswho@" in unit
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


#: §30 (mission 14 U1): quoting stopped making a character safe — a character of
#: the guard's refused set is refused inside quotes too. DESIGN §12 rule 6 still
#: carries the old clause and builders may not edit DESIGN.md, so H-027 asks the
#: architect for that line. Until it lands the kit's rule 6 is DESIGN's rule with
#: this one clause corrected: every other word stays pinned, and this test keeps
#: passing unchanged once DESIGN says the same thing (the replace is then a no-op).
STALE_QUOTED_CLAUSE = "the guard treats quoted text as text"
GUARD_REFUSAL_CLAUSE = (
    "quoting makes no character safe: one from the guard's refused set is "
    "refused inside quotes too"
)


def test_driver_rule_6_is_the_design_section_12_rule_6() -> None:
    """§20 (review 3 should-fix 10): v3.3 rewrote rule 6 "to match what the
    driver can do", so the kit carries that text and not a paraphrase of it —
    corrected for §30's language, and for nothing else (H-027)."""
    assert design_rule(6), "DESIGN §12 has no rule 6 to pin the kit to"
    assert kit_rule(6) == design_rule(6).replace(STALE_QUOTED_CLAUSE, GUARD_REFUSAL_CLAUSE)


def test_no_driver_kit_file_still_promises_that_quoting_makes_text() -> None:
    r"""§30, §32: the guard refuses a newline, `<`, `>`, `#`, a backtick, `\`,
    `$`, `{`, `}` or a control character wherever it stands, and `!` inside
    double quotes. A kit file that still says quoted text is text would send the driver
    to write a command the guard blocks (REVIEW-13 blocker 1's language)."""
    promise = re.compile(r"quoted text (?:as|is) text")
    offenders = [
        f"{path.relative_to(ROOT).as_posix()}:{n}: {line.strip()}"
        for path in tracked_files()
        if path.is_file() and path.relative_to(ROOT).as_posix().startswith("driver/")
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if promise.search(line)
    ]
    assert not offenders, "a driver-kit file still says quoting makes text:\n" + "\n".join(
        offenders
    )
    assert GUARD_REFUSAL_CLAUSE in kit_rule(6), "rule 6 does not state §30's refusal"


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
        "systemd/handsd@.service",
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


def test_the_integration_doc_states_the_guards_language_in_one_paragraph() -> None:
    """§30, §32: `docs/INTEGRATION.md` states the guard's whole language in one
    paragraph and lists the tables, per mode, with the role modes' read
    confinement, so a reviewer can attack the definition rather than the parser."""
    text = (ROOT / "docs" / "INTEGRATION.md").read_text(encoding="utf-8")
    paragraphs = [" ".join(p.split()) for p in text.split("\n\n")]
    stated = [p for p in paragraphs if "The guard's language" in p]
    assert len(stated) == 1, f"expected one paragraph stating the language, found {len(stated)}"
    for said in ("newline", "carriage return", "control character", "`<`", "`>`", "`#`",
                 "backtick", "`\\`", "`$`", "`{`", "`}`", "first offender", "position",
                 "inside double quotes", "`!`", "reserved word",
                 "`for while until if then else elif fi do done case esac select function "
                 "in time coproc ! [[ ]]`", "`shlex`", "`;`", "`&&`", "`||`", "`|`", "`&`",
                 "no expansion, no control flow, no redirection, no comment", "plain word",
                 "realpath", "second `-C`", "--prompt-file", "`HANDS_ROLE=driver`",
                 "`HANDS_ROLE=architect`", "`HANDS_KITS`", "`HANDS_CLONE`",
                 "reads are confined to the clone and the spool", "`~/.hands/<project>/`",
                 "`wc --files0-from=`", "`grep -f`", "`date --set`", "`tail -f`"):
        assert said in stated[0], f"the language paragraph does not say {said!r} (§30, §32)"
    for row in ("cat", "ls", "head", "tail", "wc", "grep", "jq", "pgrep", "sleep <int>",
                "date [+FORMAT]", "echo", "kill -0 <pid>", "hands", "git"):
        assert f"`{row}" in stated[0], f"the language paragraph does not list {row!r} (§32)"
    guard = _load_guard_module()
    for word in guard.RESERVED_WORDS:
        assert f" {word} " in f" {stated[0]} " or f"`{word} " in stated[0] or (
            f" {word}`" in stated[0]), word
    for sub, options in guard.GIT_SUBCOMMAND_OPTIONS.items():
        assert f"`{sub}" in stated[0] or f" {sub} " in stated[0], sub
        for option in options:
            assert option in stated[0], (sub, option)


def _load_guard_module():
    spec = importlib.util.spec_from_file_location(
        "bash_guard", ROOT / "driver" / "hooks" / "bash_guard.py"
    )
    assert spec and spec.loader
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    return guard


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


# ------------------------------- §30 / REVIEW-13 should-fix 7: the retired units


#: §29 retired `handsd.service` and `handswho.service` for the templated
#: `handsd@<project>`. A command naming the un-templated unit does not work on a
#: machine set up by today's docs, so no shipped file may still tell a human to
#: run one. DESIGN.md's changelog and meta/'s history keep their own record, and
#: tests/fixtures/ holds captured kits that must stay as they were captured.
RETIRED_UNIT_COMMANDS = (
    re.compile(r"systemctl --user (?:start|stop|restart) handsd(?!@)"),
    re.compile(r"systemctl --user (?:start|stop|restart) handswho(?!@)"),
    re.compile(r"journalctl --user -u handsd(?!@)"),
    re.compile(r"journalctl --user -u handswho(?!@)"),
)
#: Where the retired names are history rather than instruction.
RETIRED_UNIT_EXEMPT = ("DESIGN.md", "meta/", "tests/fixtures/", "tests/test_docs.py")


def test_no_shipped_file_tells_a_human_to_run_an_un_templated_unit() -> None:
    """REVIEW-13 should-fix 7, §30: "References to the retired un-templated units
    are removed everywhere but the changelog"."""
    offenders = [
        f"{where}:{n}: {line.strip()}"
        for path in tracked_files()
        if path.is_file()
        and not (where := path.relative_to(ROOT).as_posix()).startswith(RETIRED_UNIT_EXEMPT)
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        for pattern in RETIRED_UNIT_COMMANDS
        if pattern.search(line)
    ]
    assert not offenders, "a retired unit is still named as a command:\n" + "\n".join(offenders)


def test_the_integration_doc_says_doctor_judges_every_bash_hook() -> None:
    """§31 (review 14 should-fix 3): the `role driver` row's rule, in the doc a
    human reads — every `PreToolUse` Bash hook; §33 (review 16 should-fix 4): a
    write-tool entry is judged too, as the write matcher, and both settings files
    are read."""
    text = flattened((ROOT / "docs" / "INTEGRATION.md").read_text(encoding="utf-8"))
    for said in (
        "judges every `PreToolUse` hook whose matcher selects `Bash`, not only the first",
        "is not a Bash hook; it is judged as the architect's write matcher is",
        "`.claude/settings.json` and `.claude/settings.local.json`",
    ):
        assert said in text, f"docs/INTEGRATION.md does not say {said!r} (§31)"


def test_the_integration_doc_states_the_limit_pair_as_it_is_implemented() -> None:
    """§31 (review 14 should-fix 2): "the limit pair is documented as it is
    implemented". `job.held` is the only inbox kind the daemon's listener publishes
    (and `stop`, which `PlaybookEngine.stop` publishes itself; the test below binds
    both), so a limit reaches the phone only through a playbook `notify` rule — no
    shipped playbook has one — and the resume reaches it by no route: `EVENTS`
    names no resume."""
    assert set(NOTIFY_KINDS) == {"job.held"}
    assert "builder.limited" in EVENTS and "driver.limited" in EVENTS
    assert not [event for event in EVENTS if "resume" in event]
    books = [
        ROOT / "PLAYBOOK.toml",
        ROOT / "templates" / "PLAYBOOK-missions.toml",
        ROOT / "templates" / "PLAYBOOK-runs.toml",
    ]
    for book in books:
        rules = tomllib.loads(book.read_text(encoding="utf-8")).get("rule") or []
        limits = [rule for rule in rules if str(rule.get("on", "")).endswith(".limited")]
        assert limits == [], f"{book.name} has a rule on a limit: {limits}"
    text = flattened((ROOT / "docs" / "INTEGRATION.md").read_text(encoding="utf-8"))
    for said in (
        "A limit and its resume are not such a pair.",
        "the inbox event kinds hands publishes by itself are `stop` and `job.held`",
        "no playbook hands ships has one",
        "there is no `resume` event a rule can name",
        "orders the scheduler",
    ):
        assert said in text, f"docs/INTEGRATION.md does not say {said!r} (§31)"


def test_the_inbox_kinds_hands_publishes_by_itself_are_stop_and_job_held(
    tmp_home: Path, tmp_path: Path
) -> None:
    """§32 (review 15 should-fix 5): INTEGRATION.md said "`job.held` is the only inbox
    event kind hands publishes by itself", and `stop` is always published. The doc's
    sentence, bound to behaviour: over one daemon (not started, so nothing else
    publishes), every inbox kind the spool writes is appended, and what reaches the
    publisher is exactly one `job.held` and one `stop`."""
    import asyncio

    from hands.config import load_config
    from hands.daemon import Daemon
    from hands.spool import EVENT_KINDS

    work = tmp_path / "work"
    work.mkdir()
    (tmp_home / ".hands" / "demo.toml").write_text(
        f'[server]\nntfy_topic = "hands-docs"\n\n[roles.builder]\ncwd = "{work}"\n',
        encoding="utf-8",
    )
    text = flattened((ROOT / "docs" / "INTEGRATION.md").read_text(encoding="utf-8"))
    assert "the inbox event kinds hands publishes by itself are `stop` and `job.held`" in text
    assert "`job.held` is the only inbox event kind" not in text

    sent: list[str] = []

    async def post(url: str, *, title: str, message: str, **_: object) -> int:
        sent.append(title)
        return 200

    async def scenario() -> None:
        daemon = Daemon(load_config("demo"))
        daemon.notifier.post = post
        for kind in sorted(EVENT_KINDS - {"stop"}):
            daemon.spool.append_event(kind, {"job": "0"})
        await daemon.playbook.stop("the docs test stops it", {})
        await daemon.notifier.drain()

    asyncio.run(scenario())
    assert sorted(sent) == ["hands: a job is held for a human", "hands: the pipeline stopped"]


def test_the_start_notification_doc_says_one_and_folds_what_the_start_raised() -> None:
    """§32: "daemon start publishes exactly one notification" — the count is bound by
    tests/test_phone.py::test_a_daemon_start_publishes_exactly_one_notification over
    a plain start, held jobs, and orphaned driver and architect consultations; §33's
    fold window over queued jobs, and its bound, by the two tests after it."""
    text = flattened((ROOT / "docs" / "INTEGRATION.md").read_text(encoding="utf-8"))
    for said in (
        "A daemon start publishes exactly one notification, `hands: handsd started`",
        "is folded into its message",
        "the notification waits for them to end, for at most "
        f"{START_FOLD_S:g} seconds (DESIGN §33)",
        f"none waits longer than {START_FOLD_S:g} seconds",
    ):
        assert said in text, f"docs/INTEGRATION.md does not say {said!r} (§32)"


#: §32 (review 15 blocker 4): a committed playbook in role mode, autonomous.
ROLE_BOOK = 'version = 1\n\n[series]\nname = "m17"\narchitect = "role"\nautonomous = true\n'


def test_the_docs_config_error_claims_are_what_handsd_doctor_the_engine_and_kit_check_do(
    tmp_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§32 (review 15 blocker 4): docs/INTEGRATION.md and docs/PLAYBOOK.md say a
    playbook with `architect = "role"` and no `[roles.architect]` is refused by
    handsd, fails doctor's playbook row, stops the engine, and fails `kit check` on
    a kit that carries it. The pin was a fragment of the sentence, and the doctor
    clause was false. Each clause is run here: the reviewer's repro, one project."""
    import asyncio
    import io

    from conftest import commit_file
    from hands.cli import main
    from hands.config import load_config
    from hands.daemon import Daemon, DaemonError
    from hands.doctor import run_checks
    from hands.playbook import PlaybookEngine

    monkeypatch.delenv("HANDS_PROJECT", raising=False)
    integration = flattened((ROOT / "docs" / "INTEGRATION.md").read_text(encoding="utf-8"))
    for said in (
        "`handsd` refuses to start on it, naming both files",
        "`hands doctor` fails its playbook row with it",
        "the engine stops on it",
        "`hands kit check` fails its playbook check on a kit that carries such a playbook",
    ):
        assert said in integration, f"docs/INTEGRATION.md does not say {said!r} (§32)"
    playbook = flattened((ROOT / "docs" / "PLAYBOOK.md").read_text(encoding="utf-8"))
    for said in (
        "`handsd` refuses to start on it",
        "`hands doctor` fails its playbook row",
        "the engine stops when it loads the file",
        "`hands kit check` fails a kit that carries it",
    ):
        assert said in playbook, f"docs/PLAYBOOK.md does not say {said!r} (§32)"

    work = tmp_path / "work"
    (tmp_home / ".hands" / "demo.toml").write_text(
        f'[server]\nsocket = "{tmp_home}/.hands/handsd.sock"\n\n'
        f'[roles.builder]\ncwd = "{work}"\n',
        encoding="utf-8",
    )
    commit_file(work, "PLAYBOOK.toml", ROLE_BOOK)
    config = load_config("demo")

    # handsd refuses, naming both files
    with pytest.raises(DaemonError) as refused:
        asyncio.run(Daemon(config).start())
    assert "PLAYBOOK.toml" in str(refused.value) and "demo.toml" in str(refused.value)

    # doctor's playbook row fails
    [row] = [check for check in run_checks(config) if check.name == "playbook"]
    assert row.status == "fail" and "[roles.architect]" in row.detail, row

    # the engine stops on it when it loads the file
    async def no_send(**_: object) -> dict[str, object]:
        raise AssertionError("nothing is sent")

    engine = PlaybookEngine(config, Daemon(config).spool, send=no_send, enqueue=no_send)
    asyncio.run(engine.on_job_start(engine.spool.create_job(
        role="builder", context="clear", prompt="p", origin="cli"
    )))
    assert engine.state.paused and "[roles.architect]" in (engine.state.stop_reason or "")

    # kit check fails a kit that carries it
    kit = tmp_path / "kit"
    brief = (
        "# BUILDER-17-PROMPT\n\nKickoff line:\n\n    Read meta/BUILDER-17-PROMPT.md.\n\n"
        "Your final reply begins with `VERDICT: mission 17 finished`.\n"
    )
    book = ROLE_BOOK + 'kickoff = "Read meta/BUILDER-17-PROMPT.md."\n'
    (kit / "meta").mkdir(parents=True)
    (kit / "meta" / "BUILDER-17-PROMPT.md").write_text(brief, encoding="utf-8")
    (kit / "PLAYBOOK.toml").write_text(book, encoding="utf-8")
    out = io.StringIO()
    code = main(["kit", "check", str(kit), "--repo", str(work)], stdout=out, stderr=io.StringIO())
    [line] = [
        text for text in out.getvalue().splitlines() if text.split(":")[0].endswith(" playbook")
    ]
    assert code == 1 and line.startswith("FAIL playbook"), out.getvalue()
    assert "[roles.architect]" in line and "demo.toml" in line, line


def test_the_integration_doc_says_paired_notifications_are_spaced() -> None:
    """§30 (decision 2026-09-15): the human reading the doc has to know why two
    messages of one cause arrive a second apart, and which pairs those are."""
    text = flattened((ROOT / "docs" / "INTEGRATION.md").read_text(encoding="utf-8"))
    assert "1.1 s" in text, "docs/INTEGRATION.md never states the spacing (§30)"
    for said in ("per-second", "kit receipt", "resume"):
        assert said in text, f"docs/INTEGRATION.md does not say {said!r} about the spacing (§30)"


# ------------------------------------- the templates' architect block (§31, U6)

#: The markers around the lines of `templates/PLAYBOOK-*.toml` that are commented
#: TOML rather than prose: the architect block a human uncomments (§31).
BLOCK_START = "# >>> architect"
BLOCK_END = "# <<< architect"
TEMPLATES = [
    ROOT / "templates" / "PLAYBOOK-missions.toml",
    ROOT / "templates" / "PLAYBOOK-runs.toml",
]


def uncommented(text: str) -> tuple[str, int]:
    """`text` with every architect block uncommented, and how many blocks there were.

    "Uncomment" is exactly what a human does: strip one `# ` from each line between
    the markers, and drop the markers. Nothing else in the file is touched, so what
    the loader reads below is the human's own edit and not a rewrite of the file.
    """
    out: list[str] = []
    inside, blocks = False, 0
    for line in text.splitlines():
        if line.strip() == BLOCK_START:
            assert not inside, "an architect block opens inside another"
            inside, blocks = True, blocks + 1
            continue
        if line.strip() == BLOCK_END:
            assert inside, "an architect block closes without opening"
            inside = False
            continue
        if inside:
            assert line.startswith("#"), f"an architect block line is not commented: {line!r}"
            out.append(line[2:] if line.startswith("# ") else line[1:])
        else:
            out.append(line)
    assert not inside, "an architect block never closes"
    return "\n".join(out) + "\n", blocks


@pytest.mark.parametrize("path", TEMPLATES, ids=lambda path: path.name)
def test_each_template_ships_a_commented_architect_block(path: Path) -> None:
    """§31: the block is commented as shipped, so the template loads as the phone
    architect's series (`architect = "phone"`, the default) until a human says so."""
    from hands.playbook import parse_playbook

    text = path.read_text(encoding="utf-8")
    lines = [line.strip() for line in text.splitlines()]
    assert lines.count(BLOCK_START) == lines.count(BLOCK_END) >= 3, path.name
    book = parse_playbook(text, path=path)
    assert book.architect == "phone" and book.autonomous is False
    assert not [rule for rule in book.rules if rule.then == "consult"]


@pytest.mark.parametrize("path", TEMPLATES, ids=lambda path: path.name)
def test_each_template_loads_with_its_architect_block_uncommented(path: Path) -> None:
    """The unit's gate: uncommenting the block programmatically and running the real
    loader over the result gives the series §31 describes — role mode, autonomous,
    the escalation conditions, the per-series budget, and one `consult` rule on
    `aux.done` naming the architect."""
    from hands.playbook import DEFAULT_MAX_ARCHITECT_CONSULTS, ESCALATE_ON, parse_playbook

    text, blocks = uncommented(path.read_text(encoding="utf-8"))
    assert blocks >= 3, f"{path.name} has {blocks} architect block(s)"
    book = parse_playbook(text, path=path)
    assert book.architect == "role" and book.autonomous is True
    assert book.gate_failures == 2 and book.escalate_on == ESCALATE_ON
    assert book.max_architect_consults == DEFAULT_MAX_ARCHITECT_CONSULTS
    consults = [rule for rule in book.rules if rule.then == "consult"]
    assert len(consults) == 1, consults
    assert consults[0].on == "aux.done" and consults[0].role == "architect"
    # §10: the first matching rule fires, so the consult must stand before the
    # template's own `aux.done` stops or it would never run.
    outcomes = [rule.index for rule in book.rules if rule.on == "aux.done"]
    assert outcomes and min(outcomes) == consults[0].index


# ------------------------------------- the architect role in the docs (§31, U6)

ARCHITECT_SECTION = "### The architect role (§31)"
ARCHITECT_README = ROOT / "architect" / "README.md"


def integration() -> str:
    return (ROOT / "docs" / "INTEGRATION.md").read_text(encoding="utf-8")


def test_the_integration_doc_has_one_architect_role_section(
) -> None:
    """§31, §14 step 3: the human's manual gains the role beside the phone
    architect it already describes, in one place."""
    text = integration()
    assert text.count(ARCHITECT_SECTION) == 1, f"docs/INTEGRATION.md has no {ARCHITECT_SECTION!r}"
    section = flattened(text.split(ARCHITECT_SECTION, 1)[1].split("\n## ", 1)[0])
    assert "[roles.architect]" in section
    assert "permission_flags" in section


def test_the_integration_doc_names_the_roles_environment_and_its_guard_mode() -> None:
    """The row `hands doctor` prints and the environment the runner sets, in the
    doc's words: the three variables an architect-role job carries (§31)."""
    from hands.config import ARCHITECT_ROLE, CLONE_ENV, KITS_ENV, ROLE_ENV

    section = flattened(integration().split(ARCHITECT_SECTION, 1)[1].split("\n## ", 1)[0])
    for name in (f"{ROLE_ENV}={ARCHITECT_ROLE}", CLONE_ENV, KITS_ENV):
        assert name in section, f"the architect section does not name {name}"
    for said in (
        "Write|Edit|MultiEdit",
        "--write",
        "`role architect` row",
        "hands kit file",
    ):
        assert said in section, f"the architect section does not say {said!r}"


def test_the_integration_doc_carries_the_switch_point_from_the_architect_readme() -> None:
    """The brief: carry `architect/README.md`'s procedure across rather than
    rewriting it, and pin the quotation so the two cannot drift.

    Every indented line of the section's setup block, and each quoted sentence, is
    in `architect/README.md` as written.
    """
    readme = ARCHITECT_README.read_text(encoding="utf-8")
    section = integration().split(ARCHITECT_SECTION, 1)[1].split("\n## ", 1)[0]
    block = [line.strip() for line in section.splitlines() if line.startswith("    ")]
    setup = [line for line in block if line.startswith(("mkdir", "cp ", "git ", "HANDS_ROLE"))]
    assert len(setup) >= 6, setup
    for line in setup:
        assert flattened(line) in flattened(readme), (
            f"the setup line is not architect/README.md's: {line!r}"
        )
    for said in (
        "The role takes over from the phone architect at the fully reviewed work",
        "Applying that playbook (a gated job the human approves) is the switch.",
        "One architect at a time.",
    ):
        assert flattened(said) in flattened(readme), f"architect/README.md no longer says {said!r}"
        assert flattened(said) in flattened(section), f"the architect section drops {said!r}"


def test_the_integration_doc_says_what_approving_an_autonomous_playbook_authorises() -> None:
    """H-029, in the human's language: the standing approval is the whole of the
    autonomy, and the gate record says the same thing (`AUTONOMOUS_APPROVAL`)."""
    from hands.playbook import AUTONOMOUS_APPROVAL

    section = flattened(integration().split(ARCHITECT_SECTION, 1)[1].split("\n## ", 1)[0])
    said = (
        "the human who approves an `autonomous` playbook is approving every apply the "
        "architect files under it"
    )
    assert flattened(said) in section, f"the architect section does not say {said!r}"
    assert "standing approval" in AUTONOMOUS_APPROVAL and "standing approval" in section


def test_the_integration_doc_names_the_series_keys_and_the_verdicts_from_code() -> None:
    """The doc's numbers and words are the code's: the escalation conditions, the
    two defaults, the three verdicts, and the one event the architect is consulted
    on (§31)."""
    from hands.playbook import (
        ARCHITECT_VERDICTS,
        CONSULT_EVENTS,
        DEFAULT_GATE_FAILURES,
        DEFAULT_MAX_ARCHITECT_CONSULTS,
        ESCALATE_ON,
    )

    section = flattened(integration().split(ARCHITECT_SECTION, 1)[1].split("\n## ", 1)[0])
    for condition in ESCALATE_ON:
        assert condition in section, f"the architect section does not name {condition}"
    assert f"gate_failures = {DEFAULT_GATE_FAILURES}" in section
    assert f"max_architect_consults` (default {DEFAULT_MAX_ARCHITECT_CONSULTS})" in section
    for verdict in ARCHITECT_VERDICTS:
        assert f"`{verdict}`" in section, f"the architect section does not name {verdict!r}"
    assert CONSULT_EVENTS["architect"] == ("aux.done",)
    assert "`aux.done`" in section
    assert "claude --resume" in section


def test_the_integration_doc_says_what_h_030s_code_built() -> None:
    """The unit's honesty clause, keyed to the ledger. H-030 is "resolved by DESIGN
    v3.15 (code: mission 16 U2)", and that code has landed: the doc names the
    finding and `hands kit file <dir>` as built — the zip built from the directory
    at repository paths, the check against the clone, the daemon-minted `kit_id` —
    says what is still not proven, and no longer says the command files a zip only
    or that the resolution is designed but not built."""
    findings = (ROOT / "meta" / "findings" / "FINDINGS.md").read_text(encoding="utf-8")
    memo = flattened(findings.split("## H-030", 1)[1].split("\n## H-", 1)[0])
    status = memo.rsplit("Status: ", 1)[1]
    assert status.startswith("resolved by DESIGN v3.15 (code: mission 16 U2)"), (
        f"H-030's status changed ({status[:60]!r}); docs/INTEGRATION.md must be revisited"
    )
    section = flattened(integration().split(ARCHITECT_SECTION, 1)[1].split("\n## ", 1)[0])
    for said in (
        "H-030, resolved by DESIGN v3.15 §32",
        "mission 16 U2",
        "hands kit file <dir>",
        "`hands kit file kits/<name>`",
        "builds the zip itself",
        "`kits/m16/meta/X.md` is `meta/X.md`",
        "HANDS_CLONE",
        "kit_id",
        "is not proven",
    ):
        assert said in section, f"the architect section does not say {said!r}"
    for stale in ("H-030, open", "designed, not built", "files a zip only", "`zip -r`",
                  "`unzip -o -d`", "`zip` and `unzip` only"):
        assert stale not in section and stale not in flattened(integration()), stale


def test_no_architect_doc_says_the_architect_zips_or_files_a_zip() -> None:
    """§32: the architect stages `kits/<name>` and files it with `hands kit file
    kits/<name>`; no doc the role or its human reads says it runs `zip`/`unzip` or
    files a `<zip>`, and each names the directory form."""
    docs = {
        "architect/CLAUDE.md": ROOT / "architect" / "CLAUDE.md",
        "architect/README.md": ARCHITECT_README,
        "docs/ARCHITECT-HANDBOOK.md": ROOT / "docs" / "ARCHITECT-HANDBOOK.md",
        "docs/INTEGRATION.md": ROOT / "docs" / "INTEGRATION.md",
    }
    stale = re.compile(r"kit file <zip>|kit file [^`\s]*\.zip|`zip -r|`unzip -o|zip:\*|unzip:\*")
    for name, path in docs.items():
        text = flattened(path.read_text(encoding="utf-8"))
        assert not stale.search(text), f"{name}: {stale.search(text)}"
        assert "hands kit file kits/<name>" in text, f"{name} does not name the directory form"
        assert "kits/<name>/<repository path" in text, f"{name} does not say directory kits"


def test_the_architect_setup_line_runs_its_cd() -> None:
    """The README's first setup line: a `#` comment ends the command, so the `&& cd`
    must come before it, in the README and in the INTEGRATION copy alike."""
    for text in (ARCHITECT_README.read_text(encoding="utf-8"), integration()):
        (first,) = [line.strip() for line in text.splitlines()
                    if line.strip().startswith("mkdir -p ~/hands-architect/")]
        command = first.split("#", 1)[0]
        assert "&& cd ~/hands-architect/<project>" in command, first
        assert "kits/<name>" in first.split("#", 1)[1], first


def test_the_integration_doc_carries_the_two_project_note_to_the_role_directories() -> None:
    """§29, carried forward: one architect directory per project, as there is one
    driver directory per project, and nothing shared but the subscription."""
    text = integration()
    section = flattened(text.split("## Two projects on one laptop (§29)", 1)[1]
                        .split("\n## ", 1)[0])  # fmt: skip
    for said in ("~/hands-architect/<project>/", "~/hands-driver/<project>/"):
        assert said in section, f"the two-project section does not name {said}"
    assert "one shared resource is the subscription" in section


def test_the_integration_doc_names_the_playbook_as_a_gate_authority() -> None:
    """§31, H-031: `decided_by` carries a fourth value now, and the doc that lists
    the other three lists it."""
    from hands.gates import DECIDED_BY

    doc = flattened(integration())
    assert "playbook" in DECIDED_BY
    for value in DECIDED_BY:
        assert f"`{value}`" in doc, f"docs/INTEGRATION.md does not name `{value}`"
    assert "decided_by" in doc


def playbook_doc(heading: str) -> str:
    """One `## ` section of `docs/PLAYBOOK.md`, flattened."""
    text = (ROOT / "docs" / "PLAYBOOK.md").read_text(encoding="utf-8")
    assert text.count(heading) == 1, f"docs/PLAYBOOK.md has no {heading!r}"
    return flattened(text.split(heading, 1)[1].split("\n## ", 1)[0])


def test_the_playbook_doc_lists_every_series_and_limit_key() -> None:
    """§31 adds four `[series]` keys and one `[limits]` key; the rule reference
    names each, so a key in the code that no document explains goes red."""
    from hands.playbook import LIMIT_KEYS, SERIES_KEYS

    doc = flattened((ROOT / "docs" / "PLAYBOOK.md").read_text(encoding="utf-8"))
    for key in SERIES_KEYS + LIMIT_KEYS:
        assert f"`{key}`" in doc, f"docs/PLAYBOOK.md does not name `{key}` (§31)"


def test_the_playbook_doc_describes_the_series_architect_mode() -> None:
    """The `[series]` section carries §31's mode, its default, and what autonomy
    means, with the numbers taken from the code."""
    from hands.playbook import (
        ARCHITECT_MODES,
        DEFAULT_ARCHITECT_MODE,
        DEFAULT_GATE_FAILURES,
        ESCALATE_ON,
    )

    section = playbook_doc("## The series and its kickoff (`[series]`)")
    assert ARCHITECT_MODES == ("phone", "role") and DEFAULT_ARCHITECT_MODE == "phone"
    for said in ('`architect = "phone" | "role"`', "default `phone`", "`autonomous`"):
        assert said in section, f"the [series] section does not say {said!r}"
    assert f"`gate_failures` (default {DEFAULT_GATE_FAILURES})" in section
    for condition in ESCALATE_ON:
        assert condition in section, f"the [series] section does not name {condition}"
    for said in (
        "approving every apply the architect files under it",
        "no `[roles.architect]`",
        "decided_by: playbook",
    ):
        assert said in section, f"the [series] section does not say {said!r}"


def test_the_playbook_doc_says_the_kickoff_rule_is_the_engines_and_not_written() -> None:
    """§31: "a `builder.done` rule the engine adds, not the playbook". A reader who
    thinks it is a rule they write will write it twice."""
    from hands.playbook import ENGINE_RULE_INDEX, KIT_APPLIED

    doc = flattened((ROOT / "docs" / "PLAYBOOK.md").read_text(encoding="utf-8"))
    assert KIT_APPLIED == "^VERDICT: kit applied" and ENGINE_RULE_INDEX == -1
    for said in (
        "the engine adds",
        "not a rule anyone writes",
        "`VERDICT: kit applied`",
        "ahead of every rule in the file",
    ):
        assert said in doc, f"docs/PLAYBOOK.md does not say {said!r} (§31)"


def test_the_playbook_doc_no_longer_calls_consult_driver_only() -> None:
    """§31 generalises `consult` to a second role. The section says which role each
    event may consult, from `CONSULT_EVENTS`, and carries the architect's three
    verdicts and its own budget."""
    from hands.playbook import ARCHITECT_VERDICTS, CONSULT_EVENTS, DEFAULT_MAX_ARCHITECT_CONSULTS

    section = playbook_doc('## Consult (`then = "consult"`, DESIGN §27, §31)')
    assert CONSULT_EVENTS["architect"] == ("aux.done",)
    for said in (
        '`role = "architect"`',
        "`aux.done`",
        "`[roles.architect]`",
        f"`max_architect_consults` (default {DEFAULT_MAX_ARCHITECT_CONSULTS})",
        "per series",
    ):
        assert said in section, f"the consult section does not say {said!r}"
    for verdict in ARCHITECT_VERDICTS:
        assert f"`{verdict}`" in section, f"the consult section does not name {verdict!r}"
    assert "A consult asks the driver role instead of stopping." not in section


def test_the_playbook_doc_says_architect_events_cannot_be_matched() -> None:
    """§31: the architect's own end is read by the engine, and `architect.*` is not
    in `EVENTS` — a rule naming it is refused when the file is parsed."""
    assert not [event for event in EVENTS if event.startswith("architect.")]
    section = playbook_doc("## Events (`on`)")
    for said in ("`architect.*` is not an event", "The engine reads the architect's verdict"):
        assert said in section, f"the events section does not say {said!r}"


def test_the_playbook_doc_counters_name_the_architect_budget() -> None:
    """`hands pipeline` prints the architect's counter in role mode; the doc that
    lists what that command reports lists it too."""
    section = playbook_doc("## Counters")
    for said in ("architect", "max_architect_consults"):
        assert said in section, f"the counters section does not say {said!r}"


def test_the_handbook_section_12_onboards_the_architect_role() -> None:
    """§31: the handbook's onboarding tells the architect what changes for *it* when
    a human turns the phone architect into a role one — where its kit goes, how it
    is filed, what it replies, and when it escalates — with the words taken from
    the code, and without copying `architect/CLAUDE.md`."""
    from hands.playbook import ARCHITECT_VERDICTS, DEFAULT_MAX_ARCHITECT_CONSULTS, ESCALATE_ON

    handbook = (ROOT / "docs" / "ARCHITECT-HANDBOOK.md").read_text(encoding="utf-8")
    section = flattened(handbook.split("## 12. Onboarding a project", 1)[1])
    for said in (
        "architect/README.md",
        "architect/CLAUDE.md",
        "`hands kit file",
        "`kits/`",
        '`[series] architect = "role"`',
        "H-030",
        f"max_architect_consults` (default {DEFAULT_MAX_ARCHITECT_CONSULTS})",
    ):
        assert said in section, f"handbook §12 does not say {said!r}"
    for verdict in ARCHITECT_VERDICTS:
        assert f"`{verdict}`" in section, f"handbook §12 does not name {verdict!r}"
    for condition in ESCALATE_ON:
        assert condition in section, f"handbook §12 does not name {condition}"
    # Referenced, not duplicated: no long line of the role's own instruction is
    # copied into the handbook.
    rules = [
        flattened(line)
        for line in (ROOT / "architect" / "CLAUDE.md").read_text(encoding="utf-8").splitlines()
        if len(line.strip()) >= 60
    ]
    assert rules
    copied = [line for line in rules if line in section]
    assert not copied, "handbook §12 copies architect/CLAUDE.md:\n" + "\n".join(copied)


# ------------------------------------- autonomy and origins (§32; mission 16 U3)


def test_the_integration_doc_says_the_send_refusals_of_section_32() -> None:
    """H-032 and blocker 3, in the doc's words: both consulted roles are refused a
    direct send, and no socket client sets `origin: architect`. The stale sentence
    that the architect send is "not refused today" is gone."""
    from hands.config import CONSULT_ROLES

    assert CONSULT_ROLES == ("driver", "architect")
    section = flattened(integration().split(ARCHITECT_SECTION, 1)[1].split("\n## ", 1)[0])
    for said in (
        "`hands send --role architect` is refused as `--role driver` is (finding H-032, §32)",
        "A socket client cannot set `origin: architect` (`hands send` refuses it, naming §32)",
    ):
        assert said in section, f"the architect section does not say {said!r}"
    assert "not refused today" not in flattened(integration())


def test_the_docs_say_what_the_engine_approves_and_when_the_kickoff_fires() -> None:
    """§32: the approval is for an apply hands filed from a kit the architect role
    filed during a consultation (a daemon-minted `kit_id` checked against the spool),
    never by origin alone; the kickoff follows only that apply, approved by the
    engine. Both docs say it; neither still says "a held apply of `origin: architect`
    is approved" as if the origin were the condition."""
    series = playbook_doc("## The series and its kickoff (`[series]`)")
    section = flattened(integration().split(ARCHITECT_SECTION, 1)[1].split("\n## ", 1)[0])
    for where, text in (("docs/PLAYBOOK.md [series]", series), ("INTEGRATION", section)):
        for said in ("never by origin alone", "`kit_id`", "checked against the spool"):
            assert said in text, f"{where} does not say {said!r}"
    kickoff = playbook_doc("## The series and its kickoff (`[series]`)")
    assert "fires only for that apply" in kickoff
    for stale in (
        "a **held** apply of `origin: architect` — the job `hands kit file` files — is approved",
        "a held apply of `origin: architect` is approved by the engine itself",
    ):
        assert flattened(stale) not in flattened(integration()), stale
        doc = flattened((ROOT / "docs" / "PLAYBOOK.md").read_text(encoding="utf-8"))
        assert flattened(stale) not in doc, stale


def test_the_docs_say_handsd_checks_the_kit_and_one_kit_per_consultation() -> None:
    """§33 (REVIEW-16 blocker 1, should-fix 1, 5; H-035): handsd runs the kit check on
    the zip it stores and refuses a failing kit; a consultation files at most one kit,
    named as its verdict names it, else the engine denies it and the consultation
    escalates; and a role-mode kit whose config cannot be judged no longer passes. The
    docs the human and the architect read say so, and none still says the check passes
    where no config resolves."""
    series = playbook_doc("## The series and its kickoff (`[series]`)")
    section = flattened(integration().split(ARCHITECT_SECTION, 1)[1].split("\n## ", 1)[0])
    handbook = flattened((ROOT / "docs" / "ARCHITECT-HANDBOOK.md").read_text(encoding="utf-8"))
    role = flattened((ROOT / "architect" / "CLAUDE.md").read_text(encoding="utf-8"))
    for where, text in (("docs/PLAYBOOK.md [series]", series), ("INTEGRATION", section),
                        ("ARCHITECT-HANDBOOK", handbook)):
        for said in ("§33", "at most one", "escalate"):
            assert said in text, f"{where} does not say {said!r}"
    assert "never filed" in series and "never filed" in section
    assert "at most one kit" in role and "denied" in role
    for path in (ROOT / "docs" / "PLAYBOOK.md", ROOT / "docs" / "INTEGRATION.md"):
        text = flattened(path.read_text(encoding="utf-8"))
        assert "the check passes and says it could not judge" not in text, path.name
        assert "check passes and says it could not" not in text, path.name
    assert "no daemon, no config and no network" not in handbook


def test_the_playbook_doc_says_kit_wait_s_and_the_rename_rule() -> None:
    """§32's two new rules, with the default from the code: `next kit` waits for its
    kit by `kit_id` up to `kit_wait_s`, and a series rename restates the budget."""
    from hands.playbook import DEFAULT_KIT_WAIT_S

    series = playbook_doc("## The series and its kickoff (`[series]`)")
    assert f"`kit_wait_s` (default {DEFAULT_KIT_WAIT_S})" in series
    consult = playbook_doc('## Consult (`then = "consult"`, DESIGN §27, §31)')
    for said in ("`kit_wait_s`", "under the name the verdict gives"):
        assert said in consult, f"the consult section does not say {said!r}"
    for said in ("a rename", "restated", "max_architect_consults"):
        assert said in consult, f"the consult section does not say {said!r}"


@pytest.mark.parametrize("path", TEMPLATES, ids=lambda path: path.name)
def test_each_templates_architect_block_carries_kit_wait_s(path: Path) -> None:
    from hands.playbook import DEFAULT_KIT_WAIT_S, parse_playbook

    text, _blocks = uncommented(path.read_text(encoding="utf-8"))
    assert "kit_wait_s" in text
    assert parse_playbook(text, path=path).kit_wait_s == DEFAULT_KIT_WAIT_S
