"""Mission 24 U2: `hands go` and `hands kit apply` (DESIGN §40; §29, §32).

The phone's `go` and its kit path, from the laptop: the same `Api` code the phone
channel runs, reached over the socket with `origin: cli` (go) and `origin: kit`
(the apply). The daemon, its socket and the CLI are the real ones (`harness`);
the builder is `tests/fake_claude.py`. Nothing here touches the network.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import os
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from conftest import commit_file, strip_paths
from hands import kit as kit_mod
from hands.api import HANDS_ERROR
from hands.config import load_config
from hands.daemon import INTERNAL_ERROR, Daemon
from hands.playbook import JOURNAL_REMINDER, OWNER_REMINDER
from hands.runner import LINE_LIMIT, MAX_PROMPT_BYTES
from hands.spool import new_kit_id
from harness import (
    PROJECT,
    UNCHECKED_KIT,
    cli,
    config_body,
    drive,
    fails,
    kit_zip,
    ok,
    passing_kit,
    poll,
)

KICKOFF = "FAKE:result VERDICT: go ran"


@pytest.fixture
def workdir(tmp_path: Path) -> Path:
    d = tmp_path / "work"
    d.mkdir()
    return d


@pytest.fixture
def downloads(tmp_home: Path) -> Path:
    d = tmp_home / "Downloads"
    d.mkdir()
    return d


@pytest.fixture
def project(tmp_home: Path, workdir: Path, downloads: Path) -> str:
    files = (
        f'\n[files]\nallowed_roots = ["{workdir}", "{downloads}"]\n'
        f'kit_dir = "{downloads}"\nkit_max_mb = 1\n'
    )
    (tmp_home / ".hands" / f"{PROJECT}.toml").write_text(
        config_body(tmp_home, workdir, extra=files)
    )
    return PROJECT


def with_playbook(workdir: Path) -> None:
    """A committed playbook with a kickoff in the builder's cwd (§10)."""
    commit_file(workdir, "PLAYBOOK.toml", f'version = 1\n[series]\nkickoff = "{KICKOFF}"\n')


def a_kit(where: Path, files: dict[str, str]) -> Path:
    where.parent.mkdir(parents=True, exist_ok=True)
    where.write_bytes(kit_zip(files))
    return where


# ------------------------------------------------------------------ hands go


def test_go_sends_the_kickoff_to_the_builder_with_origin_cli(
    project: str, workdir: Path
) -> None:
    """§40: `hands go` sends the playbook's `[series] kickoff` line to the builder
    as a `clear` send with `origin: cli`."""
    with_playbook(workdir)

    async def body(daemon: Daemon) -> None:
        job = await ok("go")
        record = await ok("show", job["id"])
        assert record["prompt"] == KICKOFF
        assert (record["role"], record["context"], record["origin"]) == (
            "builder", "clear", "cli",
        )
        assert (await ok("wait", job["id"]))["state"] == "done"
        assert [row["id"] for row in (await ok("jobs"))["jobs"]] == [job["id"]]

    drive(body)


def test_go_carries_no_journal_sentence_when_the_journal_is_dirty(
    project: str, workdir: Path
) -> None:
    """§39 (H-060) names an `answer` and a cli send as the resume path; `hands go`
    is the phone's `go` (§40), so the sentence decided at dispatch (review 23
    should-fix 6) is not put before its kickoff."""
    with_playbook(workdir)
    commit_file(workdir, "meta/journal.md", "a line\n")
    (workdir / "meta" / "journal.md").write_text("a line\nthe consult line\n")

    async def body(daemon: Daemon) -> None:
        job = await ok("go")
        record = await ok("wait", job["id"])
        assert record["state"] == "done" and record["prompt"] == KICKOFF, record

    drive(body)


def test_a_held_go_carried_over_a_restart_is_still_a_kickoff(
    tmp_home: Path, workdir: Path, downloads: Path
) -> None:
    """PR #5 hosted review, finding 9: a `hands go` job held (here by a §8 gate
    pattern) when the daemon stops, and released by a fresh daemon while
    `meta/journal.md` is dirty, still runs the kickoff alone (no journal sentence:
    nothing in the exemption lives only in the old daemon's memory), and still
    resets the consultation count (§28), so an earlier driver job is not counted."""
    files = (
        f'\n[files]\nallowed_roots = ["{workdir}", "{downloads}"]\n'
        f'kit_dir = "{downloads}"\n\n[gates]\npatterns = ["go ran"]\n'
    )
    (tmp_home / ".hands" / f"{PROJECT}.toml").write_text(
        config_body(tmp_home, workdir, extra=files)
    )
    with_playbook(workdir)
    commit_file(workdir, "meta/journal.md", "a line\n")

    async def scenario() -> None:
        first = Daemon(load_config(PROJECT))
        await first.start()
        try:
            earlier = first.spool.create_job(
                role="driver", context="clear", prompt="an earlier consultation",
                origin="playbook",
            )  # fmt: skip
            first.spool.transition(earlier, "running")
            first.spool.transition(earlier, "done", verdict="VERDICT: resolved a")
            time.sleep(0.01)  # job ids are ordered by their millisecond stamp
            job = await ok("go")
            assert (await ok("show", job["id"]))["state"] == "held"
        finally:
            await first.stop()
        (workdir / "meta" / "journal.md").write_text("a line\nthe consult line\n")
        second = Daemon(load_config(PROJECT))
        await second.start()
        try:
            code, _out, err = await cli("approve", job["id"], "--json")
            assert code == 0, err
            record = await ok("wait", job["id"])
            assert record["state"] == "done" and record["prompt"] == KICKOFF, record
            engine = second.playbook
            assert engine.consults_used(engine.playbook) == 0
        finally:
            await second.stop()

    asyncio.run(asyncio.wait_for(scenario(), 60))


def test_go_is_refused_while_a_builder_job_is_held(project: str, workdir: Path) -> None:
    """§40: refused while a builder job is held, with the phone's reason (§27)."""
    with_playbook(workdir)

    async def body(daemon: Daemon) -> None:
        held = await ok(
            "send", "--role", "builder", "--context", "clear", "--gate", "apply kit",
            "FAKE:result ok",
        )  # fmt: skip
        assert (await ok("show", held["id"]))["state"] == "held"
        err = await fails("go")
        assert f"the builder has a job held ({held['id']})" in strip_paths(err), err
        assert [row["id"] for row in (await ok("jobs"))["jobs"]] == [held["id"]]

    drive(body)


def test_go_is_refused_when_the_playbook_has_no_kickoff(project: str, workdir: Path) -> None:
    commit_file(workdir, "PLAYBOOK.toml", 'version = 1\n[series]\nname = "x"\n')

    async def body(daemon: Daemon) -> None:
        err = await fails("go")
        assert "the playbook has no [series] kickoff" in strip_paths(err), err
        assert (await ok("jobs"))["jobs"] == []

    drive(body)


# ------------------------------------------------------------ hands kit apply


def test_kit_apply_of_a_failing_kit_files_nothing_and_says_the_checks_output(
    project: str, workdir: Path, downloads: Path, tmp_path: Path
) -> None:
    """§40: the kit is checked as `hands kit check` checks it; a failing kit is
    refused with the check's output, nothing is filed and nothing is copied."""
    kit = a_kit(tmp_path / "elsewhere" / "bad.zip", UNCHECKED_KIT)
    assert not kit_mod.check_kit(kit, workdir).ok

    async def body(daemon: Daemon) -> None:
        err = await fails("kit", "apply", str(kit))
        said = strip_paths(err)
        for check in ("paths", "playbook", "brief"):
            assert f"FAIL {check}: " in said, (check, said)
        assert (await ok("jobs"))["jobs"] == []
        assert list(downloads.iterdir()) == []

    drive(body)


def test_kit_apply_of_a_passing_kit_files_a_held_apply_naming_the_copied_zip(
    project: str, workdir: Path, downloads: Path, tmp_path: Path
) -> None:
    """§40: a passing kit is copied into `[files] kit_dir` under its own name and its
    apply prompt — the check's — is filed as a held builder job of `origin: kit`,
    which `hands approve` releases."""
    kit = a_kit(tmp_path / "elsewhere" / "m24.zip", passing_kit())
    report = kit_mod.check_kit(kit, workdir)
    assert report.ok and report.apply_prompt

    async def body(daemon: Daemon) -> None:
        answer = await ok("kit", "apply", str(kit))
        job = answer["job"]
        record = await ok("show", job["id"])
        assert (record["role"], record["context"], record["origin"], record["state"]) == (
            "builder", "clear", "kit", "held",
        )
        assert record["prompt"] == report.apply_prompt
        assert "Apply ~/Downloads/m24.zip " in strip_paths(record["prompt"])
        assert record["kit_id"]
        copied = downloads / "m24.zip"
        assert copied.read_bytes() == kit.read_bytes()
        assert answer["zip"] == "~/Downloads/m24.zip" and answer["copied"] is True
        assert answer["sha256"] == hashlib.sha256(kit.read_bytes()).hexdigest()
        held = [e for e in daemon.spool.events() if e.kind == "job.held"]
        assert [e.payload["job"] for e in held] == [job["id"]]
        code, _out, err = await cli("approve", job["id"], "--json")
        assert code == 0, err

        async def released() -> bool:
            return (await ok("show", job["id"]))["state"] != "held"

        await poll(released, "the apply released")

    drive(body)


DECISIONS_MESSAGE = "plan: decisions 2026-10-18 (owner)"
DECISIONS_KIT = {
    "meta/decisions/2026-10-18-owner.md": "# Owner decisions\n\n## For the builder\n\nO-1.\n",
    "KIT.md": DECISIONS_MESSAGE + "\n",
}


def test_kit_apply_of_a_decisions_kit_files_the_held_apply(
    project: str, workdir: Path, downloads: Path, tmp_path: Path
) -> None:
    """§42 route 4 at the laptop: `hands kit apply` takes a decisions kit (one owner
    file and its `KIT.md`, no brief) as `hands kit check` passes it, and files its
    plan-only apply, committed under `plan: decisions <date> (owner)`, held."""
    with_playbook(workdir)
    kit = a_kit(tmp_path / "elsewhere" / "decisions.zip", DECISIONS_KIT)
    report = kit_mod.check_kit(kit, workdir)
    assert report.ok and report.decisions and report.apply_prompt

    async def body(daemon: Daemon) -> None:
        answer = await ok("kit", "apply", str(kit))
        record = await ok("show", answer["job"]["id"])
        assert (record["role"], record["origin"], record["state"]) == (
            "builder", "kit", "held",
        )
        assert record["prompt"] == report.apply_prompt
        assert "adds KIT.md and meta/decisions/2026-10-18-owner.md" in strip_paths(
            record["prompt"]
        )
        assert answer["commit_message"] == DECISIONS_MESSAGE
        assert record["gate"]["reason"] == "apply decisions"

    drive(body)


# ------------------------------------- §43 (H-073): the owner file on every builder job

OWNER_FILE = "meta/decisions/2026-10-18-owner.md"
#: §39's journal sentence as the dispatch writes it with no `consult.done` yet.
JOURNAL_SENTENCE = JOURNAL_REMINDER.format(journal="meta/journal.md", consultation="consultation")


def owner_said(*files: str) -> str:
    return OWNER_REMINDER.format(files=", ".join(files))


def dirty_journal(workdir: Path) -> None:
    commit_file(workdir, "meta/journal.md", "a line\n")
    (workdir / "meta" / "journal.md").write_text("a line\nthe consult line\n")


def test_a_kickoff_after_a_decisions_kit_apply_names_the_owner_file(
    project: str, workdir: Path, downloads: Path, tmp_path: Path
) -> None:
    """§43 (H-073): route 4 without the brief's §R. The decisions kit's apply is
    dispatched with no sentence although its owner file is committed (an apply
    changes nothing but the kit's files); the `go` after it carries §43's sentence
    naming the file, decided in a worker thread; the stored record keeps it, `hands
    jobs --grep` finds it there, the summary line does not show it, and the job is
    still a kickoff. Once the checkpoint is committed past it, a `go` carries none."""
    with_playbook(workdir)
    commit_file(workdir, "meta/CHECKPOINT.md", "# CHECKPOINT\n")
    kit = a_kit(tmp_path / "elsewhere" / "decisions.zip", DECISIONS_KIT)
    report = kit_mod.check_kit(kit, workdir)
    assert report.ok and report.apply_prompt

    async def body(daemon: Daemon) -> None:
        loop_thread = threading.get_ident()
        threads: list[int] = []
        real = daemon.playbook.owner_reminder

        def recorded() -> str | None:
            threads.append(threading.get_ident())
            return real()

        daemon.playbook.owner_reminder = recorded  # type: ignore[method-assign]
        answer = await ok("kit", "apply", str(kit))
        apply_id = answer["job"]["id"]
        # The apply's own commit, as the builder makes it (the fake applies nothing).
        commit_file(workdir, OWNER_FILE, DECISIONS_KIT[OWNER_FILE])
        code, _out, err = await cli("approve", apply_id, "--json")
        assert code == 0, err
        applied = await ok("wait", apply_id)
        assert applied["state"] == "done" and applied["prompt"] == report.apply_prompt, applied
        job = await ok("go")
        record = await ok("wait", job["id"])
        assert record["state"] == "done", record
        assert record["prompt"] == f"{owner_said(OWNER_FILE)}\n\n{KICKOFF}", record
        assert threads and all(thread != loop_thread for thread in threads), threads
        assert daemon.playbook.is_kickoff(daemon.spool.load_job(job["id"]))
        (row,) = [r for r in (await ok("jobs"))["jobs"] if r["id"] == job["id"]]
        assert row["prompt_line"] == KICKOFF, row
        found = await ok("jobs", "--grep", "an owner file was committed")
        assert [r["id"] for r in found["jobs"]] == [job["id"]]
        commit_file(workdir, "meta/CHECKPOINT.md", "# CHECKPOINT\n\nO-1 carried out.\n")
        again = await ok("go")
        assert (await ok("wait", again["id"]))["prompt"] == KICKOFF

    drive(body)


def test_the_journal_and_owner_sentences_come_together_in_that_order(
    project: str, workdir: Path
) -> None:
    """§43: a cli send to the builder with a dirty journal and two owner files with
    no checkpoint update since carries the journal sentence, then the owner sentence
    naming both oldest first, each with its blank line, then the sender's text —
    what claude reads (`FAKE:stdin`) and what the record keeps."""
    commit_file(workdir, "meta/CHECKPOINT.md", "# CHECKPOINT\n")
    commit_file(workdir, "meta/decisions/b-owner.md", "first\n")
    commit_file(workdir, "meta/decisions/a-owner.md", "second\n")
    dirty_journal(workdir)

    async def body(daemon: Daemon) -> None:
        sent = await ok("send", "--role", "builder", "--context", "clear", "FAKE:stdin")
        record = await ok("wait", sent["id"])
        owner = owner_said("meta/decisions/b-owner.md", "meta/decisions/a-owner.md")
        assert record["prompt"] == f"{JOURNAL_SENTENCE}\n\n{owner}\n\nFAKE:stdin", record
        assert record["result"] == record["prompt"]
        (row,) = [r for r in (await ok("jobs"))["jobs"] if r["id"] == sent["id"]]
        assert row["prompt_line"] == "FAKE:stdin", row

    drive(body)


@pytest.mark.parametrize("pending", [True, False], ids=["owner-pending", "carried-out"])
def test_the_prompt_cap_counts_both_sentences(
    project: str, workdir: Path, pending: bool
) -> None:
    """§43 (§41, §2): a builder send that fits the cap with the journal sentence
    alone is refused with the cap's reason when the owner sentence is due too, and
    sent with the journal sentence when it is not."""
    commit_file(workdir, "meta/CHECKPOINT.md", "# CHECKPOINT\n")
    commit_file(workdir, OWNER_FILE, "ruling\n")
    if not pending:
        commit_file(workdir, "meta/CHECKPOINT.md", "# CHECKPOINT\n\ndone\n")
    dirty_journal(workdir)
    text = "x" * (MAX_PROMPT_BYTES - len(JOURNAL_SENTENCE.encode("utf-8")) - 2)

    async def body(daemon: Daemon) -> None:
        sent = await ok("send", "--role", "builder", "--context", "clear", text)
        record = await ok("wait", sent["id"])
        reasons = [e.payload.get("reason") for e in daemon.spool.events()
                   if e.kind == "job.killed" and e.payload.get("job") == sent["id"]]
        if pending:
            assert record["state"] == "killed" and record["started"] is None, record["state"]
            (reason,) = reasons
            assert f"over the {MAX_PROMPT_BYTES} byte cap of §2" in strip_paths(reason)
        else:
            assert record["state"] == "done" and reasons == [], record["state"]
            assert record["prompt"] == f"{JOURNAL_SENTENCE}\n\n{text}"

    drive(body)


def test_an_apply_and_its_resumes_never_carry_the_owner_sentence(
    project: str, workdir: Path
) -> None:
    """§43: an apply — a job with a `kit_id`, or a resume of one, found by following
    `resumed_from` to the chain's first job (a limited apply's resume, and an
    orphaned resume of that) — gets no owner sentence at dispatch; a resume of a
    job with no `kit_id` gets it while it is true, and not once the checkpoint is
    committed past the owner file."""
    commit_file(workdir, "meta/CHECKPOINT.md", "# CHECKPOINT\n")
    commit_file(workdir, OWNER_FILE, "ruling\n")

    async def body(daemon: Daemon) -> None:
        spool = daemon.spool

        def held(**fields: Any) -> Any:
            return spool.create_job(role="builder", context="clear", state="held", **fields)

        apply = held(prompt="Apply the kit", origin="kit", kit_id=new_kit_id())
        limited = held(prompt="Apply the kit", origin="limit", resumed_from=apply.id)
        orphaned = held(prompt="Apply the kit", origin="playbook", resumed_from=limited.id)
        for job in (apply, limited, orphaned):
            assert await daemon.dispatch_preface(job) is None, job
        plain = held(prompt="work", origin="playbook")
        resume = held(prompt="work", origin="limit", resumed_from=plain.id)
        assert await daemon.dispatch_preface(resume) == owner_said(OWNER_FILE)
        commit_file(workdir, "meta/CHECKPOINT.md", "# CHECKPOINT\n\ndone\n")
        assert await daemon.dispatch_preface(resume) is None

    drive(body)


def test_kit_apply_of_a_kit_already_in_kit_dir_files_it_in_place(
    project: str, workdir: Path, downloads: Path
) -> None:
    kit = a_kit(downloads / "m24.zip", passing_kit())

    async def body(daemon: Daemon) -> None:
        code, out, err = await cli("kit", "apply", str(kit))  # the human's rendering
        assert code == 0, err
        assert "already at ~/Downloads/m24.zip" in strip_paths(out), out
        (row,) = (await ok("jobs"))["jobs"]
        assert f"filed {row['id']} as a held builder job" in strip_paths(out), out
        assert (row["state"], row["origin"]) == ("held", "kit")
        assert sorted(p.name for p in downloads.iterdir()) == ["m24.zip"]

    drive(body)


def test_kit_apply_refuses_to_overwrite_another_file_in_kit_dir(
    project: str, workdir: Path, downloads: Path, tmp_path: Path
) -> None:
    (downloads / "m24.zip").write_bytes(b"another file")
    kit = a_kit(tmp_path / "elsewhere" / "m24.zip", passing_kit())

    async def body(daemon: Daemon) -> None:
        err = await fails("kit", "apply", str(kit))
        assert "another file" in strip_paths(err) and "m24.zip" in strip_paths(err), err
        assert (downloads / "m24.zip").read_bytes() == b"another file"
        assert (await ok("jobs"))["jobs"] == []
        assert sorted(p.name for p in downloads.iterdir()) == ["m24.zip"]

    drive(body)


def test_kit_apply_files_a_kit_larger_than_the_daemons_line_room(
    tmp_home: Path, workdir: Path, downloads: Path, tmp_path: Path
) -> None:
    """PR #5 hosted review, finding 8: a kit the size check accepts ([files]
    kit_max_mb) is filed whatever the socket's line room (`runner.LINE_LIMIT`): its
    bytes never travel in the request. A stored 10 MiB member makes the zip larger
    than the base64 a line could carry (LINE_LIMIT * 3 / 4)."""
    files = (
        f'\n[files]\nallowed_roots = ["{workdir}", "{downloads}"]\n'
        f'kit_dir = "{downloads}"\nkit_max_mb = 12\n'
    )
    (tmp_home / ".hands" / f"{PROJECT}.toml").write_text(
        config_body(tmp_home, workdir, extra=files)
    )
    big = {**passing_kit(), "docs/large-notes.md": "a line of notes\n" * (10 * 1024 * 64)}
    kit = a_kit(tmp_path / "elsewhere" / "m24-large.zip", big)
    assert kit.stat().st_size * 4 // 3 > LINE_LIMIT
    assert kit.stat().st_size <= 12 * 1024 * 1024
    assert kit_mod.check_kit(kit, workdir).ok

    async def body(daemon: Daemon) -> None:
        answer = await ok("kit", "apply", str(kit))
        record = await ok("show", answer["job"]["id"])
        assert (record["state"], record["origin"]) == ("held", "kit")
        assert (downloads / "m24-large.zip").read_bytes() == kit.read_bytes()
        assert answer["copied"] is True
        assert sorted(p.name for p in downloads.iterdir()) == ["m24-large.zip"]

    drive(body)


# ------------------------------------- kit apply's staged name (§41, should-fix 2)
#
# REVIEW-24 should-fix 2: the daemon-side checks on `staged` are driven by a socket
# client that is not the CLI (`raw_kit_apply`), since the CLI only ever names a
# `.part` it wrote itself. Each refusal is a reasoned hands error (a `KitError`
# reported as an `ApiError`), never the daemon's internal error.

#: How long a refusal may take before the FIFO guard calls it a hang.
REFUSAL_S = 10.0


async def raw_kit_apply(daemon: Daemon, name: str, staged: str) -> dict[str, Any]:
    """One `kit_apply` request on the daemon's socket, its JSON-RPC answer."""
    reader, writer = await asyncio.open_unix_connection(str(daemon.socket_path))
    try:
        request = {
            "jsonrpc": "2.0", "id": 7, "method": "kit_apply",
            "params": {"name": name, "staged": staged},
        }  # fmt: skip
        writer.write(json.dumps(request).encode("utf-8") + b"\n")
        await writer.drain()
        return dict(json.loads(await reader.readline()))
    finally:
        writer.close()
        with contextlib.suppress(ConnectionError):
            await writer.wait_closed()


def refused(answer: dict[str, Any]) -> str:
    """The message of a hands refusal — never the internal error's code."""
    assert isinstance(answer.get("error"), dict), answer
    assert answer["error"]["code"] == HANDS_ERROR, answer
    assert answer["error"]["code"] != INTERNAL_ERROR, answer
    return str(answer["error"]["message"])


def test_kit_apply_refuses_a_staged_name_with_dot_dot(
    project: str, workdir: Path, downloads: Path, tmp_path: Path
) -> None:
    """A `..` name is refused by the staged-name check and the file it points at,
    a passing kit outside `kit_dir`, is neither read nor removed.

    H-076: the target's bytes are compared with the bytes written, never with a
    second `kit_zip` — `zipfile` stamps each entry with the time of the call (two
    seconds' resolution), so a daemon start that crossed a boundary made the two
    differ and the test red."""
    outside = tmp_path / "outside"
    outside.mkdir()
    target = outside / ".hands-kit-abc.part"
    written = kit_zip(passing_kit())
    target.write_bytes(written)

    async def body(daemon: Daemon) -> None:
        said = refused(await raw_kit_apply(daemon, "m24.zip", "../outside/.hands-kit-abc.part"))
        assert "staged must be the hidden .hands-kit-*.part basename" in strip_paths(said), said
        assert target.read_bytes() == written
        assert (await ok("jobs"))["jobs"] == []
        assert list(downloads.iterdir()) == []

    drive(body)


def test_kit_apply_refuses_a_staged_symlink_and_removes_the_link_only(
    project: str, workdir: Path, downloads: Path, tmp_path: Path
) -> None:
    """A staged name that is a symlink — here to a passing kit — is refused, never
    followed (`O_NOFOLLOW`); the link is removed, its target is not. The target is
    compared with its own bytes as written (H-076)."""
    target = tmp_path / "outside" / "m24.zip"
    written = a_kit(target, passing_kit()).read_bytes()
    link = downloads / ".hands-kit-link.part"
    link.symlink_to(target)

    async def body(daemon: Daemon) -> None:
        said = refused(await raw_kit_apply(daemon, "m24.zip", link.name))
        assert f"the staged kit {link.name!r} is a symlink" in strip_paths(said), said
        assert target.read_bytes() == written
        assert (await ok("jobs"))["jobs"] == []
        assert list(downloads.iterdir()) == []

    drive(body)


@pytest.mark.parametrize(
    "case",
    [
        test_kit_apply_refuses_a_staged_name_with_dot_dot,
        test_kit_apply_refuses_a_staged_symlink_and_removes_the_link_only,
    ],
    ids=["dot_dot", "symlink"],
)
def test_the_staged_refusals_hold_whatever_the_clock_does_between_two_zips(
    case: Any,
    project: str,
    workdir: Path,
    downloads: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """H-076 (§43 "The intermittent test"): `zipfile` stamps an entry with the time
    of the `writestr` call, so `kit_zip` called twice gives different bytes once the
    clock crosses a two-second boundary between the calls, as a slow daemon start
    can make it. Every call of `kit_zip` here gets a timestamp of its own, so a test
    that compared the target with a second `kit_zip` is red at once, not now and
    then; each test compares it with the bytes it wrote."""
    import zipfile

    calls = iter(range(1, 1000))

    def a_later_zip(files: dict[str, str]) -> bytes:
        import io

        second = 2 * next(calls)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            for name, text in files.items():
                stamp = (2026, 1, 1, 0, second // 60, second % 60)
                archive.writestr(zipfile.ZipInfo(name, date_time=stamp), text)
        return buffer.getvalue()

    assert a_later_zip(passing_kit()) != a_later_zip(passing_kit())
    monkeypatch.setitem(globals(), "kit_zip", a_later_zip)
    case(project, workdir, downloads, tmp_path)


def test_kit_apply_refuses_a_staged_fifo_without_blocking(
    project: str, workdir: Path, downloads: Path
) -> None:
    """A FIFO is refused as not a regular file, at once: the daemon opens it with
    `O_NONBLOCK`. Should it block, the guard opens the FIFO's write end (itself
    non-blocking) to free the daemon's thread, and the test fails, not hangs."""
    fifo = downloads / ".hands-kit-fifo.part"
    os.mkfifo(fifo)

    async def body(daemon: Daemon) -> None:
        try:
            answer = await asyncio.wait_for(
                raw_kit_apply(daemon, "m24.zip", fifo.name), REFUSAL_S
            )
        except TimeoutError:
            with contextlib.suppress(OSError):
                os.close(os.open(fifo, os.O_WRONLY | os.O_NONBLOCK))
            pytest.fail("kit_apply blocked on a staged FIFO")
        said = refused(answer)
        assert f"the staged kit {fifo.name!r} is not a regular file" in strip_paths(said), said
        assert (await ok("jobs"))["jobs"] == []
        assert list(downloads.iterdir()) == []

    drive(body)


def test_kit_apply_refuses_a_staged_directory(
    project: str, workdir: Path, downloads: Path
) -> None:
    """A directory is refused as not a regular file (review 24: it was an
    `IsADirectoryError` from `os.fdopen`, then another from the unlink)."""
    (downloads / ".hands-kit-dir.part").mkdir()

    async def body(daemon: Daemon) -> None:
        said = refused(await raw_kit_apply(daemon, "m24.zip", ".hands-kit-dir.part"))
        expected = "the staged kit '.hands-kit-dir.part' is not a regular file"
        assert expected in strip_paths(said), said
        assert (await ok("jobs"))["jobs"] == []

    drive(body)


def test_kit_apply_refuses_a_missing_staged_name(
    project: str, workdir: Path, downloads: Path
) -> None:
    async def body(daemon: Daemon) -> None:
        said = refused(await raw_kit_apply(daemon, "m24.zip", ".hands-kit-gone.part"))
        assert "no staged kit '.hands-kit-gone.part' in [files] kit_dir" in strip_paths(said), said
        assert (await ok("jobs"))["jobs"] == []
        assert list(downloads.iterdir()) == []

    drive(body)


@pytest.mark.parametrize("case", ["bad-name", "over-cap", "failing-kit"])
def test_a_part_the_daemon_refuses_is_removed_by_the_daemon(
    case: str, project: str, workdir: Path, downloads: Path
) -> None:
    """§41: a `.part` staged by a caller that is not the CLI (which removes its own
    on every path) and refused — for its kit name, its size over kit_max_mb, or a
    failing check — is removed by the daemon."""
    data = {
        "bad-name": kit_zip(passing_kit()),
        "over-cap": b"x" * (1024 * 1024 + 1),
        "failing-kit": kit_zip(UNCHECKED_KIT),
    }[case]
    name = ".hidden.zip" if case == "bad-name" else "m24.zip"
    staged = kit_mod.stage_kit(downloads, data)

    async def body(daemon: Daemon) -> None:
        said = refused(await raw_kit_apply(daemon, name, staged.name))
        assert said.startswith("kit_apply: "), said
        assert not staged.exists()
        assert (await ok("jobs"))["jobs"] == []
        assert list(downloads.iterdir()) == []

    drive(body)
