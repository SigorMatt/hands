"""Mission 24 U8: docs/OPERATIONS.md and scripts/capture-quota-stop.sh (DESIGN §40).

The runbook is pinned by its headings, its spool and secrets tables and the
absence of anything shaped like a credential. The capture script runs against a
fake `hands` and a fake `journalctl` on PATH and a fake spool under a temporary
HOME holding a planted command secret (with regular-expression metacharacters and
a backslash), a notification token and password, a planted key and a planted
bearer token: its output names none of them. No daemon, no network, no real
`hands`, `journalctl` or harness.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

from conftest import strip_paths
from hands import who
from hands.phone import _DECISIONS, _SECRET_ONLY
from hands.spool import FLAT_ITEMS, KITS_DIR

ROOT = Path(__file__).parents[1]
DOC = ROOT / "docs" / "OPERATIONS.md"
SCRIPT = ROOT / "scripts" / "capture-quota-stop.sh"

# ------------------------------------------------------------------- the doc

RUNBOOK_HEADINGS = (
    "## 1. What a hands machine holds",
    "## 2. Secrets",
    "## 3. Runbooks",
    "### A usage-limit stop",
    "### No phone",
    "### A planned migration",
    "### A disaster",
    "### A release install",
)
SECRETS_COLUMNS = (
    "Secret",
    "Where it lives",
    "Mode",
    "How it is obtained again",
    "Regenerable",
)
#: One row per kind of secret §40 names, matched against the row's first cell.
SECRET_KINDS = (
    "notification user's password",
    "notification user's token",
    "command secret",
    "notification server's user database",
    "harness sign-in",
    "`gh`",
    "git push credential",
    "tailnet node",
)
SPOOL_CLASSES = ("regenerable", "must-carry", "safe to drop")

#: The shapes of a credential the doc must not contain, each by name. A value, an
#: example of one, or a placeholder carrying a real prefix all match.
TOKEN_SHAPES: dict[str, str] = {
    "ntfy access token (tk_…)": r"\btk_",
    "Anthropic key (sk-ant-…)": r"\bsk-ant-",
    "OpenAI-style key (sk-…)": r"\bsk-[A-Za-z0-9_-]{4,}",
    "GitHub token (ghp_/gho_/ghu_/ghs_/ghr_)": r"\bgh[pousr]_[A-Za-z0-9]",
    "GitHub fine-grained token": r"\bgithub_pat_",
    "AWS access key id": r"\bAKIA[0-9A-Z]{8,}",
    "Slack token": r"\bxox[abposr]-",
    "Tailscale auth key": r"\btskey-",
    "JSON web token": r"\beyJ[A-Za-z0-9_-]{4,}",
    "PEM private key": r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    "a bearer credential": r"(?i)\bbearer\s+\S",
    "a basic-auth credential": r"(?i)\bbasic\s+[A-Za-z0-9+/]{8,}={0,2}",
    "a URL with a password": r"://[^/\s:@]+:[^/\s@]+@",
    "an assignment of a secret": (
        r"(?i)(?:password|passwd|secret|token|api[_-]?key)\s*[=:]\s*[\"']?[^\s\"'`<|]{4,}"
    ),
    "a long random word (24+ base64url characters with a digit and a letter)": (
        r"(?=[A-Za-z0-9_-]*[0-9])(?=[A-Za-z0-9_-]*[A-Za-z])\b[A-Za-z0-9_-]{24,}\b"
    ),
    "a long hex run (32+)": r"\b[0-9a-fA-F]{32,}\b",
}


def doc() -> str:
    return DOC.read_text(encoding="utf-8")


def flat(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def section(text: str, heading: str) -> str:
    """The body under `heading` up to the next heading of the same or a higher level."""
    level = len(heading) - len(heading.lstrip("#"))
    body = text.split(heading + "\n", 1)[1]
    stop = re.search(rf"^#{{1,{level}}} ", body, re.M)
    return body[: stop.start()] if stop else body


def table(text: str) -> list[list[str]]:
    """The first Markdown table in `text`: its header and rows, cells stripped."""
    rows = [line for line in text.splitlines() if line.startswith("|")]
    assert len(rows) >= 3, f"no table in:\n{text[:400]}"
    cells = [[cell.strip() for cell in row.strip().strip("|").split("|")] for row in rows]
    return [cells[0], *cells[2:]]


def test_the_runbook_has_its_headings_in_order() -> None:
    text = doc()
    at = [text.find("\n" + heading + "\n") for heading in RUNBOOK_HEADINGS]
    missing = [h for h, i in zip(RUNBOOK_HEADINGS, at, strict=True) if i < 0]
    assert not missing, f"docs/OPERATIONS.md lacks {missing}"
    assert at == sorted(at), "the runbook's headings are out of order"


def test_the_secrets_table_has_its_columns_and_a_row_per_kind() -> None:
    header, *rows = table(section(doc(), "## 2. Secrets"))
    assert tuple(header) == SECRETS_COLUMNS
    firsts = [row[0] for row in rows]
    for kind in SECRET_KINDS:
        assert any(kind in strip_paths(first) for first in firsts), f"no secrets row for {kind!r}"
    for row in rows:
        assert len(row) == len(SECRETS_COLUMNS), row
        assert row[4].split()[0].rstrip(".;:,") in ("yes", "no"), row
        assert all(cell for cell in row), f"an empty cell in {row}"


#: The spool's items as the table names them: one row each, nothing else.
SPOOL_ITEMS = (
    "jobs/<id>.json",
    "jobs/<id>.stream.jsonl",
    "roles/<role>.json",
    "inbox.jsonl",
    "inbox.acks.jsonl",
    "pipeline.json",
    "kits/<kit_id>/",
    "handsd.sock",
)


def test_the_spool_items_are_what_the_spool_module_defines(tmp_path: Path) -> None:
    """Tied to the code: every flat-layout item, `kits/`, the default socket and a
    job's stream file (`Spool.stream_path`) have a row, and nothing else does."""
    from hands.config import DEFAULT_SOCKET
    from hands.spool import Spool

    spool = Spool(tmp_path / "spool")
    defined = {
        spool.job_path("<id>").relative_to(spool.root).as_posix(),
        spool.stream_path("<id>").relative_to(spool.root).as_posix(),
        spool.role_path("<role>").relative_to(spool.root).as_posix(),
        spool.inbox_path.name,
        spool.acks_path.name,
        "pipeline.json",  # PlaybookEngine.state_path
        f"{KITS_DIR}/<kit_id>/",
        DEFAULT_SOCKET.rsplit("/", 1)[1],
    }
    assert defined == set(SPOOL_ITEMS)
    assert {item.split("/")[0] for item in SPOOL_ITEMS} == {*FLAT_ITEMS, KITS_DIR, "handsd.sock"}


def test_the_spool_table_classifies_every_item_the_spool_module_defines() -> None:
    body = section(doc(), "### The spool")
    header, *rows = table(body)
    assert header[:2] == ["Item", "Class"], header
    classes = {row[0].strip("`"): row[1] for row in rows}
    assert sorted(classes) == sorted(SPOOL_ITEMS), sorted(classes)
    for item, kind in classes.items():
        assert SPOOL_CLASSES.count(kind) == 1, (item, kind)
    assert "the project's branch" in strip_paths(flat(body))


def test_the_no_phone_table_gives_every_phone_command_a_row() -> None:
    commands = {*_SECRET_ONLY, *_DECISIONS, "reply", "answer"}
    header, *rows = table(section(doc(), "### No phone"))
    assert header[:2] == ["Phone", "Laptop"], header
    firsts = " ".join(row[0] for row in rows)
    for command in sorted(commands):
        assert f"`{command}" in firsts, f"the no-phone table has no row for {command!r}"
    for word in who.COMMANDS:
        assert f"`{word}`" in firsts, f"the no-phone table has no row for who's {word!r}"
    laptop = " ".join(row[1] for row in rows)
    for form in ("`hands go`", "`hands kit apply", "`hands approve", "`hands who`"):
        assert form in strip_paths(laptop), form


def test_the_runbook_names_the_capture_script_and_its_output() -> None:
    body = section(doc(), "### A usage-limit stop")
    assert "bash scripts/capture-quota-stop.sh <project>" in strip_paths(body)
    assert "~/quota-capture-<project>-<time>.txt" in strip_paths(body)
    assert "`hands go`" in strip_paths(body)


def _new_machine_steps() -> dict[int, str]:
    """The planned migration's numbered steps on the new machine, each flattened."""
    body = section(doc(), "### A planned migration").split("On the new machine", 1)[1]
    steps = re.split(r"(?m)^(\d+)\. ", body)[1:]
    return {int(n): flat(text) for n, text in zip(steps[::2], steps[1::2], strict=True)}


def test_the_migration_runs_migrate_spool_on_a_flat_archive_before_handsd_starts() -> None:
    """PR #5 hosted finding 5: an archive holding the flat spool of §29 is moved
    with `hands migrate-spool` after it is unpacked and before handsd starts
    (which refuses that layout: tests/test_two_projects.py). Each item of
    `FLAT_ITEMS` is named."""
    steps = _new_machine_steps()
    unpack = next(n for n, text in steps.items() if "hands-move.tgz" in text)
    start = next(n for n, text in steps.items() if "systemctl --user start handsd@" in text)
    assert unpack < start
    text = steps[unpack]
    assert "run `hands migrate-spool` before any handsd starts" in strip_paths(text), text
    assert "handsd refuses to start on the flat layout" in strip_paths(text), text
    for item in FLAT_ITEMS:
        assert f"`{item}" in text, f"step {unpack} does not name {item!r}"


def test_the_migration_decides_the_restored_builder_jobs_before_hands_go() -> None:
    """PR #5 hosted finding 6: `hands go` is refused while a builder job is held
    (`Api.builder_busy`); the runbook has the human list the builder's jobs and
    decide a held one with approve or deny before the kickoff, after handsd starts."""
    steps = _new_machine_steps()
    start = next(n for n, text in steps.items() if "systemctl --user start handsd@" in text)
    decide = next(n for n, text in steps.items() if "restored jobs" in text)
    kickoff = next(n for n, text in steps.items() if "kickoff, `hands go`" in text)
    assert start < decide < kickoff, (start, decide, kickoff)
    text = steps[decide]
    for said in (
        "`hands jobs --role builder -n 5`",
        "`hands go` is refused while a builder job is running, queued or held",
        "`hands approve <job>`",
        '`hands deny <job> --reason "<reason>"`',
        "`hands cancel` refuses a held job",
    ):
        assert said in strip_paths(text), f"step {decide} lacks {said!r}: {text}"
    assert "with no builder job running, queued or held" in strip_paths(steps[kickoff])


@pytest.mark.parametrize("shape", sorted(TOKEN_SHAPES))
def test_the_runbook_contains_nothing_shaped_like_a_credential(shape: str) -> None:
    found = re.findall(TOKEN_SHAPES[shape], doc())
    assert not found, f"docs/OPERATIONS.md has {shape}: {found[:3]}"


@pytest.mark.parametrize(
    ("shape", "sample"),
    [
        ("ntfy access token (tk_…)", "tk_" + "x" * 8),
        ("Anthropic key (sk-ant-…)", "sk-ant-" + "x" * 8),
        ("GitHub token (ghp_/gho_/ghu_/ghs_/ghr_)", "gho_" + "x" * 8),
        ("a bearer credential", "Bearer " + "x" * 8),
        ("an assignment of a secret", "cmd_secret = " + "x" * 8),
        ("a long random word (24+ base64url characters with a digit and a letter)",
         "a" * 20 + "1234"),
        ("a URL with a password", "https://user:pw@host"),
    ],
)
def test_each_shape_catches_its_sample(shape: str, sample: str) -> None:
    """The shapes are not vacuous: each catches a planted sample of itself."""
    assert re.search(TOKEN_SHAPES[shape], f"text {sample} text")


# -------------------------------------------------------------- the script

PROJECT = "demo"
#: Regular-expression metacharacters and a backslash: a redactor that built a
#: pattern from the value would miss it or fail on it.
SECRET = r"s3c.r*e+t?[x](y)|^$\back{2}"
TOKEN = r"ntf.y+tok(en)\z"
PASSWORD = r"pa$$w.rd\*[q]"
KEY = "sk-ant-api03-" + "Q7" * 20
BEARER = "Authorization: Bearer " + "beaRer9" * 4
OLD_JOB = "0mgu0000a-aaaa"
NEW_JOB = "0mgu0000b-bbbb"


def _exe(path: Path, body: str) -> None:
    path.write_text(body)
    path.chmod(0o755)


@pytest.fixture
def planted(tmp_path: Path) -> dict[str, Path]:
    """A HOME with the project's config, secret files and spool, every one carrying
    a planted credential, and a bin directory of fakes."""
    home = tmp_path / "home"
    hands = home / ".hands"
    spool = hands / PROJECT
    (spool / "jobs").mkdir(parents=True)
    (hands / f"{PROJECT}.toml").write_text(
        "[notify]\n"
        'ntfy_url = "http://127.0.0.1:2586"\n'
        f"ntfy_token = '{TOKEN}'\n"
        'ntfy_topic = "hands-demo-topic"\n'
        'cmd_topic = "hands-cmd-demo-topic"\n'
        f"cmd_secret = '{SECRET}'\n"
    )
    (hands / f"{PROJECT}.cmd_secret").write_text(SECRET + "\n")
    (hands / "ntfy.token").write_text(TOKEN + "\n")
    (hands / "ntfy.password").write_text(PASSWORD + "\n")
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text(
        json.dumps({"type": "assistant", "text": f"found {KEY} and {SECRET}"}) + "\n"
        + json.dumps({"type": "result", "text": "Usage limit reached"}) + "\n"
    )
    for job, result in ((OLD_JOB, "old job ran"), (NEW_JOB, f"Usage limit reached {SECRET}")):
        record = {
            "id": job,
            "role": "builder",
            "state": "limited" if job == NEW_JOB else "done",
            "result": result,
            "transcript_path": str(transcript) if job == NEW_JOB else None,
        }
        (spool / "jobs" / f"{job}.json").write_text(json.dumps(record, indent=2))
    (spool / "jobs" / f"{NEW_JOB}.stream.jsonl").write_text(
        json.dumps({"type": "system", "subtype": "init"}) + "\n"
        + json.dumps({"type": "result", "result": f"Usage limit reached; token {TOKEN}"})
        + "\n"
    )
    (spool / "inbox.jsonl").write_text(
        json.dumps({"id": "e1", "kind": "limit", "payload": {"job": NEW_JOB, "said": SECRET}})
        + "\n"
        + json.dumps({"id": "e2", "kind": "notify", "payload": {"password": PASSWORD}})
        + "\n"
    )
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _exe(
        bin_dir / "hands",
        "#!/bin/sh\n"
        'if [ -n "$FAKE_HANDS_DOWN" ]; then echo "hands: handsd is not answering" >&2; '
        "exit 1; fi\n"
        # A hung daemon: a child that outlives the shell unless its group is killed.
        'if [ -n "$FAKE_HANDS_HANG" ]; then sleep 300; echo late; fi\n'
        f"echo \"fake hands $*\"; echo '{SECRET} {BEARER}'\n",
    )
    _exe(
        bin_dir / "journalctl",
        "#!/bin/sh\n"
        'if [ -n "$FAKE_JOURNAL_HANG" ]; then sleep 300; fi\n'
        f"echo 'Oct 17 handsd[1]: job {NEW_JOB} limited {BEARER} {SECRET}'\n"
        "echo 'Oct 17 handsd[1]: an unrelated line'\n",
    )
    return {"home": home, "bin": bin_dir, "spool": spool}


def capture(
    planted: dict[str, Path], *args: str, down: bool = False, **extra: str
) -> tuple[subprocess.CompletedProcess[str], list[Path]]:
    env = {
        "HOME": str(planted["home"]),
        "PATH": f"{planted['bin']}{os.pathsep}{os.environ['PATH']}",
        "LANG": "C.UTF-8",
        **extra,
    }
    if down:
        env["FAKE_HANDS_DOWN"] = "1"
    done = subprocess.run(
        ["bash", str(SCRIPT), PROJECT, *args],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    return done, sorted(planted["home"].glob(f"quota-capture-{PROJECT}-*.txt"))


def tree(home: Path) -> dict[str, tuple[int, int]]:
    return {
        str(p.relative_to(home)): (p.stat().st_size, p.stat().st_mtime_ns)
        for p in home.rglob("*")
        if p.is_file()
    }


def assert_redacted(text: str) -> None:
    for name, value in {
        "the command secret": SECRET,
        "the command secret as JSON writes it": json.dumps(SECRET)[1:-1],
        "the notification token": TOKEN,
        "the notification token as JSON writes it": json.dumps(TOKEN)[1:-1],
        "the notification password": PASSWORD,
        "the notification password as JSON writes it": json.dumps(PASSWORD)[1:-1],
        "the planted key": KEY,
        "the planted bearer token": BEARER.split()[-1],
    }.items():
        assert value not in strip_paths(text), f"the capture names {name}"
    assert "[redacted]" in strip_paths(text)


def test_the_capture_writes_one_file_with_every_section_and_names_no_secret(
    planted: dict[str, Path],
) -> None:
    before = tree(planted["home"])
    done, outputs = capture(planted)
    assert done.returncode == 0, done.stderr
    assert len(outputs) == 1, outputs
    out = outputs[0]
    assert stat.S_IMODE(out.stat().st_mode) == 0o600
    text = out.read_text(encoding="utf-8")
    assert_redacted(text)
    assert f"job record {planted['spool'] / 'jobs' / (NEW_JOB + '.json')}" in text
    assert f"job {NEW_JOB} limited" in text
    for said in (
        f"fake hands --project {PROJECT} status",
        f"fake hands --project {PROJECT} jobs -n 5",
        f"fake hands --project {PROJECT} pipeline",
        "stream-json lines about a limit",
        "Usage limit reached",
        "transcript tail",
        "inbox tail",
    ):
        assert said in strip_paths(text), f"the capture lacks {said!r}:\n{text}"
    assert "an unrelated line" not in strip_paths(text), "the journal keeps the job's lines only"
    # Read-only: the one new file is the capture; nothing else changed.
    after = tree(planted["home"])
    assert {k: v for k, v in after.items() if k != out.name} == before


def test_the_capture_takes_the_job_named_as_its_second_argument(
    planted: dict[str, Path],
) -> None:
    done, outputs = capture(planted, OLD_JOB)
    assert done.returncode == 0, done.stderr
    text = outputs[0].read_text(encoding="utf-8")
    assert f"job record {planted['spool'] / 'jobs' / (OLD_JOB + '.json')}" in text
    assert "old job ran" in strip_paths(text)
    assert_redacted(text)


def test_the_capture_needs_no_daemon_and_records_the_failures(
    planted: dict[str, Path],
) -> None:
    done, outputs = capture(planted, down=True)
    assert done.returncode == 0, done.stderr
    text = outputs[0].read_text(encoding="utf-8")
    assert "handsd is not answering" in strip_paths(text)
    assert f"(failed: exit 1: hands --project {PROJECT} status)" in text
    assert "Usage limit reached" in strip_paths(text), "the spool is captured all the same"
    assert_redacted(text)


@pytest.mark.parametrize("bad", ["../x", ".hidden", "a/b"])
def test_the_capture_refuses_a_job_id_that_is_a_path_and_writes_nothing(
    planted: dict[str, Path], bad: str
) -> None:
    done, outputs = capture(planted, bad)
    assert done.returncode == 2
    assert outputs == []


def test_a_hung_hands_and_journalctl_are_bounded_and_recorded_as_failures(
    planted: dict[str, Path],
) -> None:
    """PR #5 hosted finding 2: every command that waits on another process runs
    under `timeout` (HANDS_CAPTURE_TIMEOUT seconds); a timeout is recorded in the
    file as a failure and the capture goes on to the spool, the redaction and the
    file. The fakes sleep 300 s; the run's own bound is 60 s."""
    done, outputs = capture(
        planted, HANDS_CAPTURE_TIMEOUT="1", FAKE_HANDS_HANG="1", FAKE_JOURNAL_HANG="1"
    )
    assert done.returncode == 0, done.stderr
    assert len(outputs) == 1, outputs
    text = outputs[0].read_text(encoding="utf-8")
    for command in ("status", "jobs -n 5", "pipeline"):
        said = f"(failed: timed out after 1s: hands --project {PROJECT} {command})"
        assert said in strip_paths(text), f"the capture lacks {said!r}:\n{text}"
    assert "(failed: timed out after 1s: journalctl" in strip_paths(text), text
    assert "late" not in strip_paths(text), "the hung command's group is killed"
    assert "Usage limit reached" in strip_paths(text), "the spool is captured all the same"
    assert_redacted(text)


def test_a_line_cut_inside_a_multibyte_character_is_still_captured_and_redacted(
    planted: dict[str, Path], tmp_path: Path
) -> None:
    """PR #5 hosted finding 7: `cut -c` cuts bytes, so a 4000th byte inside a UTF-8
    character leaves half of it; the redactor decodes with errors="replace" and
    the planted secrets on that line and the others are still redacted."""
    long_line = "a" * 3999 + "\u00e9" * 10 + "\n"
    assert len(long_line[:4000].encode("utf-8")) > 4000  # byte 4000 is inside the é
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text(
        f"key {KEY} secret {SECRET}\n" + long_line, encoding="utf-8"
    )
    done, outputs = capture(planted)
    assert done.returncode == 0, done.stderr
    assert len(outputs) == 1, outputs
    text = outputs[0].read_bytes().decode("utf-8")  # the file is valid UTF-8
    assert "a" * 3999 + "\ufffd" in text, "the cut line is kept, its half character replaced"
    assert_redacted(text)


def test_a_failed_redactor_leaves_no_empty_file(planted: dict[str, Path]) -> None:
    """PR #5 hosted finding 7: when the redactor fails, the capture says so and
    removes the file it created — no empty file is left behind silently. The fake
    `python3` fails only for the redactor (the program that holds PATTERNS)."""
    real = shutil.which("python3")
    assert real is not None
    _exe(
        planted["bin"] / "python3",
        "#!/bin/sh\n"
        'case "$3" in *PATTERNS*) echo "redactor broke" >&2; exit 3 ;; esac\n'
        f'exec "{real}" "$@"\n',
    )
    done, outputs = capture(planted)
    assert done.returncode == 1, done
    assert "redactor broke" in strip_paths(done.stderr)
    assert "failed" in strip_paths(done.stderr)
    assert outputs == [], "a failed capture leaves no file"


# ------------------------------------------- mission 25 U1 (REVIEW-24 blocker 1)


def _real(name: str) -> str:
    found = shutil.which(name)
    assert found is not None, name
    return found


def test_a_hung_find_is_recorded_as_a_timeout_and_never_as_no_record(
    planted: dict[str, Path],
) -> None:
    """REVIEW-24 blocker 1 (DESIGN §41): `find`, which looks for the newest job,
    runs under `timeout -k 5` and through the path that writes `(failed: timed
    out after <n>s: …)`. The fake ignores SIGTERM, so only the `-k 5` kill ends
    it: without `-k 5` the run outlives its own 60 s bound; without the bound on
    `find` it outlives it too; outside the recording path the capture says "no
    job record", which is false."""
    _exe(
        planted["bin"] / "find",
        "#!/bin/sh\n"
        "trap '' TERM\n"
        "sleep 300\n"
        f'exec "{_real("find")}" "$@"\n',
    )
    done, outputs = capture(planted, HANDS_CAPTURE_TIMEOUT="1")
    assert done.returncode == 0, done.stderr
    assert len(outputs) == 1, outputs
    text = outputs[0].read_text(encoding="utf-8")
    assert "(failed: timed out after 1s: find " in strip_paths(text), text
    assert "(no job record under" not in strip_paths(text), text
    assert "(no record, or it names no transcript)" not in strip_paths(text), text
    assert f"fake hands --project {PROJECT} pipeline" in strip_paths(text)
    assert_redacted(text)


def test_a_hung_record_read_is_recorded_as_a_timeout_and_never_as_no_record(
    planted: dict[str, Path],
) -> None:
    """REVIEW-24 blocker 1 (DESIGN §41): python3's read of the job record (the one
    whose program names `transcript_path`) is bounded and its timeout recorded;
    the capture does not say the record names no transcript. The redactor, also
    python3, runs as it is."""
    _exe(
        planted["bin"] / "python3",
        "#!/bin/sh\n"
        'case "$3" in *transcript_path*) sleep 300 ;; esac\n'
        f'exec "{_real("python3")}" "$@"\n',
    )
    done, outputs = capture(planted, HANDS_CAPTURE_TIMEOUT="1")
    assert done.returncode == 0, done.stderr
    assert len(outputs) == 1, outputs
    text = outputs[0].read_text(encoding="utf-8")
    assert "(failed: timed out after 1s: python3" in strip_paths(text), text
    assert "(no record, or it names no transcript)" not in strip_paths(text), text
    assert "(no job record under" not in strip_paths(text), text
    assert "Usage limit reached" in strip_paths(text), "the record and stream are captured"
    assert "inbox tail" in strip_paths(text), "the capture goes on"
    assert_redacted(text)


def test_a_secret_straddling_the_cut_is_redacted_whole(
    planted: dict[str, Path], tmp_path: Path
) -> None:
    """REVIEW-24 should-fix 1 (DESIGN §41): the redactor runs on the whole text and
    the 4000-byte cut comes after, so a secret across byte 4000 leaves no prefix.
    Cut first, the secret's first 12 bytes (and the key's first 12) would stay."""
    lead = 4000 - 12
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text(
        "x" * lead + SECRET + " tail\n" + "y" * (lead - 1) + " " + KEY + " tail\n", encoding="utf-8"
    )
    done, outputs = capture(planted)
    assert done.returncode == 0, done.stderr
    text = outputs[0].read_text(encoding="utf-8")
    # The fake hands' `echo` mangles the secret's `\b`, so its own output keeps a
    # prefix of it; the prefix asked about is the one on the cut line.
    secret_prefix = "x" * lead + SECRET[:12]
    key_prefix = "y" * (lead - 1) + " " + KEY[:12]
    assert secret_prefix not in strip_paths(text), "a prefix of the secret is in the capture"
    assert key_prefix not in strip_paths(text), "a prefix of the key is in the capture"
    assert "x" * lead + "[redacted]" in strip_paths(text)
    assert "y" * (lead - 1) + " [redacted]" in strip_paths(text)
    uncut = "x" * lead + "[redacted] tail"
    assert uncut not in strip_paths(text), "the line is still cut at 4000 bytes"
    assert_redacted(text)


def test_a_url_encoded_secret_is_redacted(planted: dict[str, Path], tmp_path: Path) -> None:
    """DESIGN §40/§41: each secret is matched URL-encoded as well; no pattern covers
    this line, so only the by-value URL-encoded form redacts it."""
    from urllib.parse import quote

    encoded = quote(SECRET, safe="")
    assert encoded != SECRET
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text(
        json.dumps({"type": "tool", "url": f"http://127.0.0.1:2586/x?q={encoded}&z=1"}) + "\n",
        encoding="utf-8",
    )
    done, outputs = capture(planted)
    assert done.returncode == 0, done.stderr
    text = outputs[0].read_text(encoding="utf-8")
    assert encoded not in strip_paths(text), "the URL-encoded secret is in the capture"
    assert "q=[redacted]&z=1" in strip_paths(text)
    assert_redacted(text)


def test_the_notification_password_is_redacted_by_value_from_its_file(
    planted: dict[str, Path], tmp_path: Path
) -> None:
    """DESIGN §40: ~/.hands/ntfy.password is read and its value redacted wherever
    it appears — here behind no key a pattern knows, so only the by-value read of
    that file redacts it (it is in no config)."""
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text(f"the word {PASSWORD} alone\n", encoding="utf-8")
    config = (planted["home"] / ".hands" / f"{PROJECT}.toml").read_text()
    assert PASSWORD not in strip_paths(config), "the password is in no config"
    done, outputs = capture(planted)
    assert done.returncode == 0, done.stderr
    text = outputs[0].read_text(encoding="utf-8")
    assert PASSWORD not in strip_paths(text), "the notification password is in the capture"
    assert "the word [redacted] alone" in strip_paths(text)
    assert_redacted(text)
