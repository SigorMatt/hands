"""Mission 24 U2: `hands go` and `hands kit apply` (DESIGN §40; §29, §32).

The phone's `go` and its kit path, from the laptop: the same `Api` code the phone
channel runs, reached over the socket with `origin: cli` (go) and `origin: kit`
(the apply). The daemon, its socket and the CLI are the real ones (`harness`);
the builder is `tests/fake_claude.py`. Nothing here touches the network.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from conftest import commit_file, strip_paths
from hands import kit as kit_mod
from hands.daemon import Daemon
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
