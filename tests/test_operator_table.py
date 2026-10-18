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

import io
import re
import subprocess
import textwrap
import tomllib
from pathlib import Path

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
