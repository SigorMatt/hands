"""Mission 26 U4: the handbook's operator table, the Project instruction and the
runbooks (DESIGN §42 "Who operates a project", "An HF report", "The operator
table (handbook §19)", "The second onboarding shape (handbook §13)",
"Documentation"; H-072).

The table is pinned to the shipped playbook templates: every `stop` and `notify`
message of `templates/PLAYBOOK-missions.toml` and `templates/PLAYBOOK-runs.toml`
has a row, its `{n}` written `<n>`. The instruction's opening paragraph and rule
15 are read out of DESIGN.md §42's indented blocks and must stand in
docs/ARCHITECT-INSTRUCTION.md word for word; the four reworded rules carry §42's
sentences and not the ones they replace.
"""

from __future__ import annotations

import ast
import io
import re
import subprocess
import textwrap
import tomllib
from pathlib import Path
from typing import Any

import pytest

from conftest import strip_paths
from hands.cli import main as hands_main

ROOT = Path(__file__).parents[1]
HANDBOOK = ROOT / "docs" / "ARCHITECT-HANDBOOK.md"
INSTRUCTION = ROOT / "docs" / "ARCHITECT-INSTRUCTION.md"
DESIGN = ROOT / "DESIGN.md"
TEMPLATES = (
    ROOT / "templates" / "PLAYBOOK-missions.toml",
    ROOT / "templates" / "PLAYBOOK-runs.toml",
)

SECTION_19 = "## 19. The operator table"
#: §42: "in four columns: the notification as it reads on the phone (its title and
#: first words), who answers it (nobody, the human alone, the project's chat, the
#: hands Project), the phone route, and the laptop route".
COLUMNS = ["Notification", "Who answers", "Phone", "Laptop"]
ANSWERERS = ("nobody", "the human alone", "the project's chat", "the hands Project")
#: §42's eight routes, by their bold names.
ROUTES = {
    1: "Nothing to do.",
    2: "A hold.",
    3: "A kit.",
    4: "A ruling the builder needs in the middle of a mission",
    5: "A consultation the role must make after a ruling or a stop",
    6: "A stop the project's chat reads before deciding",
    7: "A usage-limit stop.",
    8: "A machine-wide event",
}


def flat(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def handbook_section(heading: str) -> str:
    text = HANDBOOK.read_text(encoding="utf-8")
    assert f"\n{heading}\n" in strip_paths(text), f"the handbook has no {heading!r}"
    return text.split(f"\n{heading}\n", 1)[1].split("\n## ", 1)[0]


def table_rows(text: str) -> list[list[str]]:
    """The first Markdown table in `text`: its header and rows, cells stripped. A
    `\\|` inside a cell is a literal bar, not a cell boundary."""
    lines = [line for line in text.splitlines() if line.startswith("|")]
    assert len(lines) >= 3, "no table"
    cells = [
        [cell.strip().replace("\\|", "|") for cell in re.split(r"(?<!\\)\|", line.strip())[1:-1]]
        for line in lines
    ]
    return [cells[0], *cells[2:]]


def template_messages() -> list[str]:
    found: list[str] = []
    for path in TEMPLATES:
        book = tomllib.loads(path.read_text(encoding="utf-8"))
        for rule in book["rule"]:
            if rule["then"] in ("stop", "notify") and rule.get("message"):
                found.append(rule["message"])
    return found


def as_the_table_writes_it(message: str) -> str:
    """`{n}` → `<n>`: the table writes a placeholder as the docs write one."""
    return re.sub(r"\{([^{}]+)\}", r"<\1>", message)


# ------------------------------------------------------------- §19, the table


def test_section_19_follows_section_18() -> None:
    text = HANDBOOK.read_text(encoding="utf-8")
    at_18 = text.find("\n## 18. ")
    at_19 = text.find(f"\n{SECTION_19}\n")
    assert 0 < at_18 < at_19, (at_18, at_19)


def test_the_table_has_the_four_columns_and_every_row_one_answerer_and_one_route() -> None:
    header, *rows = table_rows(handbook_section(SECTION_19))
    assert header == COLUMNS, header
    assert len(rows) > 20, len(rows)
    for row in rows:
        assert len(row) == len(COLUMNS), row
        assert all(row), f"an empty cell in {row}"
        who = row[1]
        assert who.startswith(ANSWERERS), row
        routes = re.findall(r"route ([1-8])\b", who)
        assert len(routes) == 1, f"the who cell names {routes}, not one route: {row}"


def test_every_template_stop_and_notify_message_has_a_row() -> None:
    messages = template_messages()
    assert len(messages) > 15, messages
    firsts = [row[0] for row in table_rows(handbook_section(SECTION_19))[1:]]
    for message in messages:
        written = as_the_table_writes_it(message)
        assert any(written in strip_paths(first) for first in firsts), (
            f"§19 has no row for the template message {written!r}"
        )


def test_a_template_stop_reads_under_the_stop_title_and_a_notify_under_its_own() -> None:
    """A `stop` rule publishes `hands: the pipeline stopped` with the message first;
    a `notify` rule publishes `hands: <message>` (playbook.py `_act_stop`,
    `_act_notify`): the table writes each as the phone shows it."""
    firsts = [row[0] for row in table_rows(handbook_section(SECTION_19))[1:]]
    for path in TEMPLATES:
        for rule in tomllib.loads(path.read_text(encoding="utf-8"))["rule"]:
            message = rule.get("message")
            if not message:
                continue
            written = as_the_table_writes_it(message)
            if rule["then"] == "notify":
                title = f"`hands: {written}`"
                assert any(title in strip_paths(first) for first in firsts), title
            else:
                assert any(
                    written in strip_paths(first)
                    and "`hands: the pipeline stopped`" in strip_paths(first)
                    for first in firsts
                ), written


@pytest.mark.parametrize(
    "said",
    [
        "`hands: handsd started`",
        "`hands: handsd crashed`",
        "`hands: a job is held for a human`",
        "filed by the architect; apply approved by the playbook",
        "`hands: a consultation stopped over a paused pipeline`",
        "the series' consult budget is exhausted (budget-exhausted)",
        "within [series] kit_wait_s = <s> (§32)",
        "the architect escalated: <reason>",
        "ends escalate (§33)",
        "builder.limited: the playbook has no rule for it",
        "limits.max_resumes reached:",
        "could not resume <role> after its limit:",
        "[limits] max_resumes is <m>",
        "paused by human",
        "<command> refused: <why>",
        "`hands: kit received`",
        "`digest`",
        "HF report",
    ],
)
def test_the_table_has_a_row_for_what_hands_writes_itself(said: str) -> None:
    firsts = " ".join(row[0] for row in table_rows(handbook_section(SECTION_19))[1:])
    assert said in strip_paths(firsts), f"§19 has no row for {said!r}"


def test_section_19_lists_the_eight_routes_in_order() -> None:
    body = flat(handbook_section(SECTION_19))
    places = [body.find(f"{n}. **{name}") for n, name in ROUTES.items()]
    assert all(place >= 0 for place in places), dict(zip(ROUTES, places, strict=True))
    assert places == sorted(places)


def test_route_4_is_the_decisions_kit_then_go_with_answer_the_shorter_route() -> None:
    body = flat(handbook_section(SECTION_19))
    route_4 = body.split("4. **", 1)[1].split("5. **", 1)[0]
    for said in (
        "`meta/decisions/<date>-owner.md`",
        "`plan: decisions <date> (owner)`",
        "`hands kit check`",
        "`go <secret>`",
        "`answer <secret> <text>`",
        "the shorter route",
        "`hands kit apply <zip>`",
        "`hands approve <job>`",
        "`hands go`",
    ):
        assert said in strip_paths(route_4), f"route 4 does not say {said!r}"


def test_route_5_sends_the_decisions_kit_without_go_then_consult() -> None:
    """PR #6 hosted review finding 4: route 4 ends with `go`, which starts a builder
    job, and `consult` is refused while one is queued, running or held — so route 5
    sends the owner file as route 4's decisions kit without the `go`, and consults
    once the apply has ended."""
    body = flat(handbook_section(SECTION_19))
    route_5 = body.split("5. **", 1)[1].split("6. **", 1)[0]
    for said in (
        "route 4's decisions kit",
        "`kit <secret>` with the zip attached, Approve",
        "without `go <secret>`",
        "a builder job is queued, running or held",
        "once the apply has ended",
        "`consult <secret> <reason>`",
        "`hands kit apply <zip>`, `hands approve <job>`, then `hands consult`",
        "without `hands go`",
    ):
        assert said in strip_paths(route_5), f"route 5 does not say {said!r}"
    assert "as route 4's kit; then" not in strip_paths(route_5)
    assert "`go <secret>`" not in strip_paths(route_5.replace("without `go <secret>`", ""))
    assert "`hands go`" not in strip_paths(route_5.replace("without `hands go`", ""))


def test_the_rows_on_route_5_send_no_go() -> None:
    """Finding 4: a row routed to route 5 gives no `go` before its `consult`."""
    rows = [row for row in table_rows(handbook_section(SECTION_19))[1:]
            if "route 5" in row[1]]
    assert len(rows) >= 2, rows
    for row in rows:
        phone, laptop = row[2], row[3]
        assert "`go <secret>`" not in strip_paths(phone.replace("without `go <secret>`", "")), row
        assert "`hands go`" not in strip_paths(laptop.replace("without `hands go`", "")), row
        assert "consult" in strip_paths(phone) and "`hands consult`" in strip_paths(laptop), row


def test_the_blocked_mission_row_consults_without_go() -> None:
    """Finding 4: the blocked mission row's route-5 branch, under a playbook without
    the blocked→consult rule, Approves the decisions kit without `go` and consults."""
    rows = table_rows(handbook_section(SECTION_19))[1:]
    row = next(row for row in rows if "Mission <n> blocked" in row[0])
    phone, laptop = row[2], row[3]
    for said in ("Approve without `go <secret>`", "once the apply has ended",
                 "`consult <secret> <reason>` (route 5)"):
        assert said in strip_paths(phone), f"the blocked row does not say {said!r}"
    assert "`hands kit apply <zip>`, `hands approve <job>`, then `hands consult` " \
        "without `hands go`" in strip_paths(laptop), row
    assert "Approve, `go <secret>`; in role mode" not in strip_paths(phone), row
    assert "`hands go` (or `hands consult`)" not in strip_paths(laptop), row


def test_section_16_commits_the_owner_file_without_go() -> None:
    body = flat(handbook_section("## 16. Re-firing a consultation after a stop"))
    assert "Approve it without `go`" in strip_paths(body), body
    assert "once its apply has ended" in strip_paths(body), body


def test_the_max_resumes_reached_row_is_route_6_and_restarts_with_go() -> None:
    """PR #6 hosted review finding 3: at `limits.max_resumes reached` the limit
    manager schedules no resume (src/hands/limits.py `on_limited`), so `resume`
    only clears the pause; the row is §42's route 6, and work restarts with a new
    job — `go` for the builder, the review prompt for the aux — after the reset."""
    rows = table_rows(handbook_section(SECTION_19))[1:]
    row = next(row for row in rows if "limits.max_resumes reached:" in row[0])
    who, phone, laptop = row[1], row[2], row[3]
    assert who == "the project's chat — route 6", row
    for said in ("`progress <secret>`", "`status <secret>`", "`go <secret>`",
                 "No resume is scheduled", "after the limit's reset", "aux prompt",
                 "capture-quota-stop.sh"):
        assert said in strip_paths(phone + " " + laptop), f"the row does not say {said!r}"
    assert "`hands go`" in strip_paths(laptop), row
    assert "`resume <secret>`" not in strip_paths(phone), row
    assert "`hands resume`" not in strip_paths(laptop), row


def test_the_digest_row_says_what_each_field_means() -> None:
    rows = table_rows(handbook_section(SECTION_19))[1:]
    row = next(row for row in rows if row[0].startswith("`digest`"))
    said = " ".join(row)
    for field in (
        "daemon up", "down", "pipeline running", "paused", "mission <n>", "`-`",
        "builder running <job> <age>", "idle", "60 characters",
        "architect <used>/<budget>", "driver <used>/<budget>",
        "stop <time> <reason>", "100 characters", "no stop", "does not load",
    ):
        assert field in strip_paths(said), f"the digest row does not say {field!r}"
    assert "`hands digest`" in strip_paths(row[3]), row


def test_the_hf_report_has_section_42s_form() -> None:
    body = flat(handbook_section(SECTION_19).split("\n### An HF report\n", 1)[1])
    for said in (
        "`HF-<n>-report.md`",
        "evidence only",
        "the HF id and its date",
        "the project's name",
        "`hands --version`",
        "the commit the last install named",
        "the notifications, job ids, command lines and their output as they appeared",
        "what the project expected of hands",
        "the commit, review number or consultation number where it was seen",
        "the project's interim workaround if any, named by what it does to hands",
        "No product design, code, domain term or fixture goes into it",
        "files it as H-nnn citing the HF id",
    ):
        assert said in strip_paths(body), f"the HF report's form does not say {said!r}"


# ------------------------------------------------- §10, §13, §14, §18 of the handbook


def test_section_10s_builder_question_row_gives_route_4_and_names_no_driver() -> None:
    rows = table_rows(handbook_section("## 10. What a stop means, and what to write next"))
    row = next(row for row in rows if row[0] == "builder question")
    said = " ".join(row)
    for needed in ("decisions kit", "`go <secret>`", "`answer <secret> <text>`",
                   "shorter route", "`VERDICT: question`", "route 4"):
        assert needed in strip_paths(said), f"§10's row does not say {needed!r}"
    assert "driver" not in strip_paths(said), row


def test_section_14_gives_route_4_and_names_no_driver() -> None:
    body = flat(handbook_section("## 14. The ruling round"))
    for needed in ("decisions kit", "`kit <secret>`", "`go <secret>`", "`hands kit apply <zip>`",
                   "`hands go`", "`answer <secret> <text>`", "the shorter route",
                   "`VERDICT: question`", "route 4"):
        assert needed in strip_paths(body), f"§14 does not say {needed!r}"
    assert "driver" not in strip_paths(body.lower()), "§14 still names a driver"


def test_section_13_has_the_second_shape_who_operates_and_the_playbook_check() -> None:
    body = flat(handbook_section("## 13. The onboarding shape"))
    for needed in (
        # who operates a project
        "The project's own chat operates that project",
        "The laptop's aux is hands for every project",
        "The hands Project chat keeps hands' own missions and the operations of the whole machine",
        "HF report",
        # the hands Project's playbook check
        "both orphaned rules and the blocked→consult rule",
        "never a mission kit",
        # the second onboarding shape
        "second onboarding shape",
        "`templates/BUILDER-N-PROMPT.md`",
        "`templates/REVIEW-PROTOCOL.md`",
        "`templates/PLAYBOOK-missions.toml`",
        "never rewritten",
        "after M9's rehearsal",
    ):
        assert needed in strip_paths(body), f"§13 does not say {needed!r}"


def test_section_18_names_consult_and_digest() -> None:
    body = flat(handbook_section("## 18. Reading hands: `send`, `jobs`, `pipeline`, `progress`"))
    for needed in ("`hands consult", "`consult <secret>", "`hands digest`", "`digest <secret>`"):
        assert needed in strip_paths(body), f"§18 does not say {needed!r}"


# ------------------------------------------------------ the Project instruction


def design_block(after: str) -> str:
    """The indented block that follows the paragraph ending `after` in §42."""
    section = DESIGN.read_text(encoding="utf-8").split("\n## 42. ", 1)[1]
    rest = section.split(after, 1)[1]
    lines: list[str] = []
    for line in rest.split("\n\n", 1)[1].splitlines():
        if line and not line.startswith("    "):
            break
        lines.append(line)
    return textwrap.dedent("\n".join(lines)).strip("\n")


def instruction() -> str:
    return INSTRUCTION.read_text(encoding="utf-8")


def rule(number: int) -> str:
    rules = instruction().split("\nRules:\n", 1)[1]
    found = re.search(rf"^{number}\. (.*?)(?=^\d+\. |\Z)", rules, re.M | re.S)
    assert found, f"the instruction has no rule {number}"
    return flat(found.group(1))


def test_the_opening_paragraph_is_section_42s_word_for_word() -> None:
    opening = design_block("which replaces \"You are the ARCHITECT\n… from files you write.\":")
    assert opening.startswith("You are the ARCHITECT for the project named below."), opening
    assert opening in strip_paths(instruction()), opening
    assert "a Claude Code DRIVER" not in strip_paths(instruction())


def test_rule_15_is_section_42s_word_for_word_after_rule_14() -> None:
    fifteen = design_block("Its new rule 15, after rule 14:")
    assert fifteen.startswith("15. When the human pastes a hands notification"), fifteen
    text = instruction()
    assert fifteen in strip_paths(text), fifteen
    assert text.index("\n14. ") < text.index("\n15. ")
    assert text.rstrip().endswith("give nothing to send for them unless this is that Project.")


@pytest.mark.parametrize(
    ("number", "new", "old"),
    [
        (3, "Short instructions for the aux session, phone commands, and this Project "
            "instruction itself, are chat text by nature",
         "Short instructions for the driver or aux sessions"),
        (9, "When the human reports what the aux session or a role said, treat the report "
            "as a claim like any other and verify it from the branch.",
         "what the driver said"),
        (12, "`status`, `progress` and `digest` are for runtime state that is not in the "
             "repository",
         "the driver's `check`"),
        (14, "Deliver it as a file and as a decisions kit — a zip holding the file at its "
             "repository path and a `KIT.md` whose first line is `plan: decisions <date> "
             "(owner)` — and give the route rule 15's table names for it.",
         "the human sends the builder a `keep` that names it"),
    ],
)
def test_the_four_rules_are_reworded_as_section_42_gives_them(
    number: int, new: str, old: str
) -> None:
    said = rule(number)
    assert new in strip_paths(said), (number, said)
    assert old not in strip_paths(said), (number, said)


def test_rule_9_is_exactly_section_42s_sentence() -> None:
    assert rule(9) == (
        "When the human reports what the aux session or a role said, treat the report as "
        "a claim like any other and verify it from the branch."
    )


def test_the_instruction_names_no_driver_session_or_keep_send() -> None:
    pasted = instruction().split("\n---\n", 1)[1]
    assert "driver" not in strip_paths(pasted.lower())
    assert "`keep`" not in strip_paths(pasted)


def _git(*args: str, cwd: Path | None = None) -> str:
    done = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True, timeout=60
    )
    return done.stdout.strip()


def test_project_add_prints_the_instruction_with_rule_15(
    tmp_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A real `hands project add` (a fake `systemctl` on PATH, a local bare
    repository as the url, as tests/test_project_add.py runs it) prints the filled
    instruction last, rule 15 in it."""
    bin_dir = tmp_path / "fakebin"
    bin_dir.mkdir()
    script = bin_dir / "systemctl"
    script.write_text("#!/bin/sh\nexit 0\n")
    script.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}:/usr/local/bin:/usr/bin:/bin")
    work = tmp_path / "seed"
    work.mkdir()
    _git("init", "-q", "-b", "main", cwd=work)
    (work / "README.md").write_text("seed\n")
    _git("add", "README.md", cwd=work)
    _git("-c", "user.name=t", "-c", "user.email=t@example.invalid",
         "commit", "-q", "-m", "seed", cwd=work)
    bare = tmp_path / "proj.git"
    _git("clone", "-q", "--bare", str(work), str(bare))

    out, err = io.StringIO(), io.StringIO()
    code = hands_main(["project", "add", "demo", "--repo", str(bare)], stdout=out, stderr=err)
    assert code == 0, err.getvalue() + out.getvalue()
    printed = out.getvalue().split("== Project instruction")[-1]
    assert design_block("Its new rule 15, after rule 14:") in strip_paths(printed)
    assert "You are the ARCHITECT for the project named below." in strip_paths(printed)
    assert re.search(r"^\s*PROJECT\s*= demo\s*$", printed, re.M), printed


# ------------------------------------------------------------- the runbooks


def test_the_no_phone_table_has_the_consult_and_digest_rows() -> None:
    text = (ROOT / "docs" / "OPERATIONS.md").read_text(encoding="utf-8")
    body = text.split("\n### No phone\n", 1)[1].split("\n### ", 1)[0]
    rows = table_rows(body)[1:]
    consult = next(row for row in rows if row[0].startswith("`consult <secret>"))
    assert "`hands consult [--file <path>] [<reason>]`" in strip_paths(consult[1]), consult
    digest = next(row for row in rows if row[0].startswith("`digest <secret>`"))
    assert strip_paths(digest[1]) == "`hands digest`", digest


def test_the_integration_doc_states_h_072s_raise_and_the_clis_ceiling() -> None:
    text = flat((ROOT / "docs" / "INTEGRATION.md").read_text(encoding="utf-8"))
    for said in (
        "A project whose gate runs longer than 15 minutes raises `BASH_DEFAULT_TIMEOUT_MS` "
        "and `BASH_MAX_TIMEOUT_MS` in its `[roles.builder.env]` and `[roles.aux.env]`",
        "its briefs name a timeout no longer than that",
        "has no ceiling of its own on `BASH_MAX_TIMEOUT_MS`",
        "H-072",
    ):
        assert said in strip_paths(text), f"docs/INTEGRATION.md does not say {said!r}"


# ------------------------------------- §43: the operator table follows the code

#: §43: "the engine, the limit manager, the daemon and the phone"; a helper they
#: call is read in whatever module of `hands` defines it.
SOURCE = ROOT / "src" / "hands"
SCANNED = ("playbook", "limits", "daemon", "phone")
#: A placeholder, as the extraction writes one before the table's `<…>`.
HOLE = "\x00"
#: The receivers §43 names, by the name a call is made through: the engine's and
#: the limit manager's `stop`, the daemon's `_limit_stop`, the notifier's `notify`
#: and `answer` and the engine's `_notify` — and two more publishes the same
#: modules make: the notifier's `deliver` (the crash notification) and the engine's
#: `hold` seam (`Daemon.publish_hold`, whose `reason` §43's hold is). A function by
#: one of these names is the receiver itself: a reason that is its own parameter
#: is read at its callers, which are the receivers' calls.
RECEIVER_DEFS = frozenset(
    {"stop", "_limit_stop", "notify", "answer", "deliver", "_notify", "publish_hold"}
)
#: What a receiver's arguments are, by position and by keyword.
TITLE, MESSAGE, PAYLOAD = "title", "message", "payload"
#: A payload's keys whose value is the notification's text (notify.py `_message`).
TEXT_KEYS = ("reason", "message")

#: (module, function, expression) → why its strings are not read here, and where
#: they are. An entry nothing matches any more is itself a failure.
EXEMPT: dict[tuple[str, str, str], str] = {
    ("playbook", "render", "_PLACEHOLDER_RE.sub(one, text)"):
        "a playbook rule's own `message`, rendered (`_act_stop`): the template "
        "rules' rows are pinned by test_every_template_stop_and_notify_message_has_a_row",
    ("playbook", "_act_notify", "self._fired(rule, event, job, message=message)"):
        "the payload of a `notify` rule carries the same rendered rule message, "
        "whose title `hands: <message>` is read; pinned by the template tests",
    ("daemon", "publish_hold", "gate['reason']"):
        "a gate's own reason, written by src/hands/gates.py (§8) and shown as "
        "<reason> in the `hands: a job is held for a human` row",
    ("daemon", "_on_event", "event.payload"):
        "an inbox event's payload; NOTIFY_KINDS publishes only `job.held`, whose "
        "reason is the gate's (gates.py), the `hands: a job is held for a human` row",
    ("daemon", "_held_reason", "self.playbook.published_hold_reason(job)"):
        "§43's hold reason at filing and at a start, decided by playbook.py "
        "`published_hold_reason` (`owner_hold_reason`): the `the kit carries <path>` "
        "row, pinned by test_section_43s_three_rows_are_in_the_table",
    ("playbook", "_release_kit", "asyncio.to_thread(self.published_hold_reason, job)"):
        "the same §43 reason, asked in a worker thread (it hashes the stored zip): "
        "the `the kit carries <path>` row, pinned by test_section_43s_three_rows_are_in_the_table",
    ("daemon", "start", "note.title"):
        "a note held during a start that failed, published as it was raised: its "
        "title was read at the notify that raised it",
    ("daemon", "start", "note.payload"):
        "the same held note's payload, read at the notify that raised it",
    ("phone", "reply_answer", "job.result"):
        "the architect's own reply, verbatim (§33): the `architect` row",
    ("phone", "answer_reply", "job.result"):
        "the builder's own final reply, verbatim (§36): the `builder` row",
    ("phone", "command", "words[0].lower()"):
        "the command word the human typed, echoed as a refusal's title (§39): "
        "the `<command>` row",
    ("phone", "command", "self.daemon.api.progress_report()"):
        "`progress`'s report, built by src/hands/api.py `progress_report` (§38): "
        "the `progress` row",
    ("phone", "_digest", "'\\n'.join(await asyncio.to_thread(digest_lines, base))"):
        "the digest's lines, built by src/hands/digest.py `digest_lines` (§42): "
        "the `digest` row, whose fields test_the_digest_row_says_what_each_field_means pins",
    ("phone", "status_summary", "'\\n'.join(lines)"):
        "`status`'s summary, its lines job states and counts: the `hands: status` row",
}

_FUNC = (ast.FunctionDef, ast.AsyncFunctionDef)


class _Module:
    """One module of `hands`, parsed: its functions, constants and imports."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.tree = ast.parse((SOURCE / f"{name}.py").read_text(encoding="utf-8"))
        self.parent: dict[ast.AST, ast.AST] = {}
        self.defs: dict[str, list[ast.FunctionDef | ast.AsyncFunctionDef]] = {}
        for node in ast.walk(self.tree):
            for child in ast.iter_child_nodes(node):
                self.parent[child] = node
            if isinstance(node, _FUNC):
                self.defs.setdefault(node.name, []).append(node)
        self.consts: dict[str, ast.expr] = {}
        self.imports: dict[str, tuple[str, str | None]] = {}
        for node in self.tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        self.consts[target.id] = node.value
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                if node.value is not None:
                    self.consts[node.target.id] = node.value
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                if node.module.startswith("hands."):
                    for alias in node.names:
                        self.imports[alias.asname or alias.name] = (node.module[6:], alias.name)
                elif node.module == "hands":
                    for alias in node.names:
                        self.imports[alias.asname or alias.name] = (alias.name, None)

    def function_of(self, node: ast.AST) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
        while node in self.parent:
            node = self.parent[node]
            if isinstance(node, _FUNC):
                return node
        return None


_MODULES: dict[str, _Module] = {}


def _module(name: str) -> _Module | None:
    if name not in _MODULES:
        if not (SOURCE / f"{name}.py").is_file():
            return None
        _MODULES[name] = _Module(name)
    return _MODULES[name]


Func = ast.FunctionDef | ast.AsyncFunctionDef | None
#: A found string: ("text", module, line, its text with HOLE for each placeholder),
#: or ("unread", module, function, the expression) for one this reading cannot follow.
Found = tuple[str, str, Any, str]


def _receiver(mod: _Module, call: ast.Call) -> dict[int | str, str] | None:
    """What each argument of `call` is, when `call` is one of the receivers."""
    func = call.func
    if not isinstance(func, ast.Attribute):
        return None
    on, name = ast.unparse(func.value), func.attr
    reason = {0: MESSAGE, "reason": MESSAGE}
    if name == "stop" and (
        (mod.name in ("playbook", "limits") and on == "self") or on.endswith(".playbook")
    ):
        return reason  # `self.monitors.stop(job_id)`, `self.phone.stop()` are no stop
    if name == "_limit_stop" and on == "self":
        return reason
    if on == "notifier" or on.endswith(".notifier"):
        if name == "notify":
            return {0: TITLE, 1: PAYLOAD, "title": TITLE, "payload": PAYLOAD}
        if name == "answer":
            return {0: TITLE, 1: MESSAGE}
        if name == "deliver":
            return {0: TITLE, 1: MESSAGE, 2: PAYLOAD}
    if mod.name == "playbook" and on == "self":
        if name == "_notify":
            return {0: TITLE, 1: PAYLOAD}
        if name == "hold":
            return {1: MESSAGE, "reason": MESSAGE}
    return None


def _parameters(func: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[list[str], list[str]]:
    args = func.args
    return [a.arg for a in args.posonlyargs + args.args], [a.arg for a in args.kwonlyargs]


def _argument(call: ast.Call, position: int | None, keyword: str) -> ast.expr | None:
    for given in call.keywords:
        if given.arg == keyword:
            return given.value
    if position is not None and position < len(call.args):
        return call.args[position]
    return None


def _callers(mod: _Module, func: ast.FunctionDef | ast.AsyncFunctionDef, name: str) -> list[
    tuple[_Module, Func, ast.expr]
]:
    """§43 "a reason that arrives as a parameter is read at the callers that pass
    it": every call of `func` by name in the scanned modules and its own."""
    positional, _ = _parameters(func)
    position = positional.index(name) if name in positional else None
    if position is not None and positional and positional[0] == "self":
        position -= 1
    passed = []
    for other in sorted(set(SCANNED) | {mod.name}):
        caller = _module(other)
        assert caller is not None
        for node in ast.walk(caller.tree):
            if not isinstance(node, ast.Call):
                continue
            called = node.func
            callee = (called.id if isinstance(called, ast.Name)
                      else called.attr if isinstance(called, ast.Attribute) else None)
            if callee == func.name:
                value = _argument(node, position, name)
                if value is not None:
                    passed.append((caller, caller.function_of(node), value))
    return passed


def _definition(mod: _Module, name: str) -> tuple[_Module, list[Any]]:
    if name in mod.defs:
        return mod, mod.defs[name]
    if name in mod.imports:
        where, real = mod.imports[name]
        other = _module(where)
        if other is not None and real is not None and real in other.defs:
            return other, other.defs[real]
    return mod, []


def _local_values(func: ast.AST, name: str) -> tuple[list[ast.expr], list[ast.expr]]:
    """The values assigned to `name` in `func` (`=`, `:=`, `+=`), and the values it
    is unpacked from (`a, b = value`), which are read by `_unpacked`."""
    values: list[ast.expr] = []
    unpacked: list[ast.expr] = []
    for node in ast.walk(func):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    values.append(node.value)
                elif isinstance(target, ast.Tuple) and any(
                    isinstance(item, ast.Name) and item.id == name for item in target.elts
                ):
                    index = next(i for i, item in enumerate(target.elts)
                                 if isinstance(item, ast.Name) and item.id == name)
                    unpacked.append(ast.Subscript(node.value, ast.Constant(index)))
        elif isinstance(node, (ast.AnnAssign, ast.NamedExpr, ast.AugAssign)):
            target = node.target
            if isinstance(target, ast.Name) and target.id == name and node.value is not None:
                values.append(node.value)
    return values, unpacked


def _literal_alternatives(mod: _Module, func: Func, value: ast.expr) -> list[str] | None:
    """A placeholder that is a name assigned only plain strings in its function
    (`_load`'s `what`) stands for each of them; any other placeholder is `<…>`."""
    if func is None or not isinstance(value, ast.Name):
        return None
    positional, keyword = _parameters(func)
    if value.id in positional + keyword:
        return None
    values, unpacked = _local_values(func, value.id)
    if unpacked or not values:
        return None
    if all(isinstance(v, ast.Constant) and isinstance(v.value, str) for v in values):
        return [v.value for v in values if isinstance(v, ast.Constant)]
    return None


def _read(mod: _Module, func: Func, expr: ast.expr, seen: frozenset[int] = frozenset()) -> list[
    Found
]:
    """Every string `expr` can be, as §43 reads it."""
    if id(expr) in seen:
        return []
    seen = seen | {id(expr)}
    where = func.name if func is not None else "<module>"
    if isinstance(expr, ast.Constant):
        return [("text", mod.name, expr.lineno, expr.value)] if isinstance(expr.value, str) else []
    if isinstance(expr, ast.JoinedStr):
        texts = [""]
        for part in expr.values:
            if isinstance(part, ast.Constant):
                texts = [text + str(part.value) for text in texts]
                continue
            assert isinstance(part, ast.FormattedValue)
            choices = _literal_alternatives(mod, func, part.value) or [HOLE]
            texts = [text + choice for text in texts for choice in choices]
        return [("text", mod.name, expr.lineno, text) for text in texts]
    if isinstance(expr, ast.BinOp) and isinstance(expr.op, ast.Add):
        left, right = _read(mod, func, expr.left, seen), _read(mod, func, expr.right, seen)
        joined = [("text", mod.name, a[2], a[3] + b[3])
                  for a in left if a[0] == "text" for b in right if b[0] == "text"]
        return joined + [item for item in left + right if item[0] != "text"]
    if isinstance(expr, ast.IfExp):
        return _read(mod, func, expr.body, seen) + _read(mod, func, expr.orelse, seen)
    if isinstance(expr, ast.BoolOp):
        return [item for value in expr.values for item in _read(mod, func, value, seen)]
    if isinstance(expr, ast.Await):
        return _read(mod, func, expr.value, seen)
    if isinstance(expr, ast.Name):
        if func is not None:
            positional, keyword = _parameters(func)
            if expr.id in positional + keyword:
                if func.name in RECEIVER_DEFS:
                    return []  # the receiver's own parameter: its callers are read
                passed = _callers(mod, func, expr.id)
                return [item for caller, at, value in passed
                        for item in _read(caller, at, value, seen)]
            values, unpacked = _local_values(func, expr.id)
            if values or unpacked:
                return [item for value in values for item in _read(mod, func, value, seen)] + [
                    item for value in unpacked for item in _unpacked(mod, func, value, seen)
                ]
        if expr.id in mod.consts:
            return _read(mod, None, mod.consts[expr.id], seen)
        if expr.id in mod.imports:
            where_from, real = mod.imports[expr.id]
            other = _module(where_from)
            if other is not None and real in other.consts:
                return _read(other, None, other.consts[real], seen)
    if isinstance(expr, ast.Attribute) and isinstance(expr.value, ast.Name):
        imported = mod.imports.get(expr.value.id)
        if imported is not None and imported[1] is None:
            other = _module(imported[0])
            if other is not None and expr.attr in other.consts:
                return _read(other, None, other.consts[expr.attr], seen)
    table = _constant_dict(mod, expr)
    if table is not None:
        return [item for value in table for item in _read(mod, None, value, seen)]
    if isinstance(expr, ast.Call):
        called = expr.func
        name = None
        if isinstance(called, ast.Name):
            name = called.id
        elif (isinstance(called, ast.Attribute) and isinstance(called.value, ast.Name)
              and called.value.id == "self"):
            name = called.attr
        if name is not None:
            # §43: "a helper whose returned string becomes a reason … is read by
            # its `return` statements".
            home, defs = _definition(mod, name)
            if defs:
                return [item for helper in defs for node in ast.walk(helper)
                        if isinstance(node, ast.Return) and node.value is not None
                        and home.function_of(node) is helper
                        for item in _read(home, helper, node.value, seen)]
    return [("unread", mod.name, where, ast.unparse(expr))]


def _constant_dict(mod: _Module, expr: ast.expr) -> list[ast.expr] | None:
    """`NOTIFY_KINDS["job.held"]` is its value; `NOTIFY_KINDS.get(kind)` any value."""
    def table(name: ast.expr) -> ast.Dict | None:
        if isinstance(name, ast.Name) and isinstance(mod.consts.get(name.id), ast.Dict):
            found = mod.consts[name.id]
            assert isinstance(found, ast.Dict)
            return found
        return None

    if isinstance(expr, ast.Subscript) and (found := table(expr.value)) is not None:
        if isinstance(expr.slice, ast.Constant):
            return [value for key, value in zip(found.keys, found.values, strict=True)
                    if isinstance(key, ast.Constant) and key.value == expr.slice.value]
    if (isinstance(expr, ast.Call) and isinstance(expr.func, ast.Attribute)
            and expr.func.attr == "get" and (found := table(expr.func.value)) is not None):
        return list(found.values)
    return None


def _unpacked(mod: _Module, func: Func, value: ast.expr, seen: frozenset[int]) -> list[Found]:
    """`message, held = self._start_pending`: the element at that index of every
    tuple assigned to `self._start_pending` in the module, read where it is built."""
    assert isinstance(value, ast.Subscript) and isinstance(value.slice, ast.Constant)
    source, index = value.value, value.slice.value
    if isinstance(source, ast.Attribute) and ast.unparse(source.value) == "self":
        found: list[Found] = []
        for node in ast.walk(mod.tree):
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Tuple) and any(
                ast.unparse(target) == ast.unparse(source) for target in node.targets
            ):
                found += _read(mod, mod.function_of(node), node.value.elts[index], seen)
        if found:
            return found
    return [("unread", mod.name, func.name if func else "<module>", ast.unparse(source))]


def _payload_texts(mod: _Module, func: Func, expr: ast.expr) -> list[Found]:
    """A payload's text: its `reason` or `message` (notify.py `_message`), from a
    dict written at the call or assigned to the name passed in the same function."""
    def from_dict(found: ast.Dict) -> list[Found]:
        return [item for key, value in zip(found.keys, found.values, strict=True)
                if isinstance(key, ast.Constant) and key.value in TEXT_KEYS
                for item in _read(mod, func, value)]

    if isinstance(expr, ast.Dict):
        return from_dict(expr)
    where = func.name if func is not None else "<module>"
    if isinstance(expr, ast.Name) and func is not None:
        positional, keyword = _parameters(func)
        if expr.id in positional + keyword and func.name in RECEIVER_DEFS:
            return []
        found: list[Found] = []
        assigned = False
        for node in ast.walk(func):
            if not isinstance(node, ast.Assign):
                continue
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == expr.id:
                    assigned = True
                    found += (from_dict(node.value) if isinstance(node.value, ast.Dict)
                              else [("unread", mod.name, where, ast.unparse(node.value))])
                elif (isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name)
                      and target.value.id == expr.id and isinstance(target.slice, ast.Constant)
                      and target.slice.value in TEXT_KEYS):
                    assigned = True
                    found += _read(mod, func, node.value)
        if assigned:
            return found
    return [("unread", mod.name, where, ast.unparse(expr))]


def code_strings() -> list[Found]:
    """§43: every string or f-string passed as a stop's reason or a publish's title
    or message to the receivers, in the engine, the limit manager, the daemon and
    the phone."""
    found: list[Found] = []
    for name in SCANNED:
        mod = _module(name)
        assert mod is not None
        for node in ast.walk(mod.tree):
            if not isinstance(node, ast.Call):
                continue
            kinds = _receiver(mod, node)
            if kinds is None:
                continue
            func = mod.function_of(node)
            given: list[tuple[str, ast.expr]] = [
                (kinds[i], arg) for i, arg in enumerate(node.args) if i in kinds
            ] + [(kinds[k.arg], k.value) for k in node.keywords if k.arg in kinds]
            for kind, arg in given:
                found += (_payload_texts(mod, func, arg) if kind == PAYLOAD
                          else _read(mod, func, arg))
    return found


def _pieces(text: str) -> list[str]:
    """§43: an f-string "matched on its literal pieces in order". The `: `, `; `
    or `, ` that joins a piece to a placeholder goes with the placeholder (a row
    that lists three reasons writes each without its `<event>: `), and a piece
    with no word left in it says nothing a row could be missing."""
    pieces = (flat(part).strip(" :;,") for part in text.split(HOLE))
    return [piece for piece in pieces if re.search(r"\w", piece)]


def _in_row(pieces: list[str], row: str) -> bool:
    at = 0
    for piece in pieces:
        found = row.find(piece, at)
        if found < 0:
            return False
        at = found + len(piece)
    return True


def test_every_stop_reason_and_published_line_of_the_code_has_a_row() -> None:
    """§43 "The operator table follows the code": a string the receivers are given
    with no row in §19 names itself, its placeholders written `<…>`."""
    firsts = [flat(row[0]) for row in table_rows(handbook_section(SECTION_19))[1:]]
    found = code_strings()
    texts = [item for item in found if item[0] == "text"]
    assert len(texts) > 60, len(texts)
    missing = sorted({
        f"{item[1]}.py:{item[2]}: {flat(item[3].replace(HOLE, '<…>'))!r}"
        for item in texts
        if _pieces(item[3]) and not any(_in_row(_pieces(item[3]), row) for row in firsts)
    })
    assert not missing, "§19 has no row for:\n" + "\n".join(missing)


def test_every_string_the_reading_cannot_follow_is_an_exemption_with_a_reason() -> None:
    unread = {(item[1], item[2], item[3]) for item in code_strings() if item[0] == "unread"}
    unexempt = sorted(unread - EXEMPT.keys())
    assert not unexempt, f"read neither as a string nor exempt: {unexempt}"
    stale = sorted(EXEMPT.keys() - unread)
    assert not stale, f"exemptions nothing in the code matches any more: {stale}"
    assert all(len(reason) > 40 for reason in EXEMPT.values())


@pytest.mark.parametrize(
    ("said", "where"),
    [
        ("the playbook is not the committed copy, so no rule can be trusted to fire:",
         "playbook.py `_load`"),
        ("apply <name>: <why>; the commit message is the default '<message>'",
         "phone.py `_file_apply`"),
        ("apply <name>: the kit carries <path>, the playbook in force; a change of the "
         "playbook is the owner's (§43)", "playbook.py `published_hold_reason`"),
    ],
)
def test_section_43s_three_rows_are_in_the_table(said: str, where: str) -> None:
    firsts = " ".join(flat(row[0]) for row in table_rows(handbook_section(SECTION_19))[1:])
    assert said in strip_paths(firsts), f"§19 has no row for {said!r} ({where})"


def test_the_owner_hold_row_is_route_2_then_go() -> None:
    """§43: the hold of a kit that carries the playbook is the human's, and once the
    apply is approved no engine kickoff follows — the human sends `go`."""
    rows = table_rows(handbook_section(SECTION_19))[1:]
    row = next(row for row in rows if "the kit carries <path>, the playbook in force" in row[0])
    assert row[0].startswith("`hands: a job is held for a human`"), row
    assert row[1] == "the human alone — route 2", row
    assert "`go <secret>`" in strip_paths(row[2]), row
    assert "`hands go`" in strip_paths(row[3]), row
    assert "Approve" in strip_paths(row[2]), row
    assert "`hands approve <job>`" in strip_paths(row[3]), row
