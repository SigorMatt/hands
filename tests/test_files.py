"""U4: files move only inside `files.allowed_roots` (DESIGN §1 invariant 2, §4, §13).

`hands put/get/ls` and `send --file path=content` are the only ways hands puts
bytes on the machine. Every one of them is confined, and every write is recorded
with its sha256 — §1 invariant 2 is "files are moved with sha256".
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from hands.daemon import Daemon
from harness import PROJECT, cli, config_body, drive, fails, ok


@pytest.fixture
def workdir(tmp_path: Path) -> Path:
    d = tmp_path / "work"
    d.mkdir(exist_ok=True)
    return d


@pytest.fixture
def outside(tmp_path: Path) -> Path:
    """A directory that is emphatically not an allowed root."""
    d = tmp_path / "outside"
    d.mkdir(exist_ok=True)
    (d / "secret.txt").write_text("do not read me")
    return d


@pytest.fixture
def drop(tmp_path: Path) -> Path:
    """A second allowed root, standing in for ~/Downloads (§13)."""
    d = tmp_path / "drop"
    d.mkdir(exist_ok=True)
    return d


@pytest.fixture
def project(tmp_home: Path, workdir: Path, drop: Path, outside: Path) -> str:
    body = config_body(
        tmp_home,
        workdir,
        extra=f"""
[files]
allowed_roots = ["{workdir}", "{drop}"]
""",
    )
    (tmp_home / ".hands" / f"{PROJECT}.toml").write_text(body)
    return PROJECT


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# --------------------------------------------------------------- put/get/ls


def test_put_reports_sha256_and_bytes(project: str, workdir: Path) -> None:
    content = "line one\nline two — é\n"
    target = workdir / "notes" / "a.md"

    async def body(daemon: Daemon) -> None:
        put = await ok("put", str(target), "--content", content)
        assert put["path"] == str(target)
        assert put["sha256"] == sha(content)
        assert put["bytes"] == len(content.encode("utf-8"))
        assert target.read_text() == content  # parent directory created

    drive(body)


def test_put_from_a_file_copies_it_byte_for_byte(project: str, workdir: Path, drop: Path) -> None:
    content = "decisions-2026-09-11\n"
    source = drop / "decisions.md"
    source.write_text(content)
    target = workdir / "decisions.md"

    async def body(daemon: Daemon) -> None:
        put = await ok("put", str(target), "--from", str(source))
        assert put["sha256"] == sha(content)
        assert target.read_text() == content

    drive(body)


def test_get_returns_the_content_verbatim(project: str, workdir: Path) -> None:
    content = "  ragged\ttabs\nand a trailing space \n"
    (workdir / "f.txt").write_text(content)

    async def body(daemon: Daemon) -> None:
        got = await ok("get", str(workdir / "f.txt"))
        assert got["content"] == content
        assert got["sha256"] == sha(content)
        assert got["bytes"] == len(content.encode("utf-8"))

    drive(body)


def test_ls_returns_entries(project: str, workdir: Path) -> None:
    (workdir / "a.txt").write_text("aa")
    (workdir / "sub").mkdir()

    async def body(daemon: Daemon) -> None:
        listing = await ok("ls", str(workdir))
        by_name = {entry["name"]: entry for entry in listing["entries"]}
        assert by_name["a.txt"]["type"] == "file"
        assert by_name["a.txt"]["bytes"] == 2
        assert by_name["sub"]["type"] == "dir"

    drive(body)


def test_put_refuses_content_and_from_together(project: str, workdir: Path, drop: Path) -> None:
    (drop / "src").write_text("x")

    async def body(daemon: Daemon) -> None:
        err = await fails("put", str(workdir / "t"), "--content", "x", "--from", str(drop / "src"))
        assert "--content" in err and "--from" in err
        assert not (workdir / "t").exists()
        err = await fails("put", str(workdir / "t"))
        assert "--content" in err or "--from" in err

    drive(body)


# ------------------------------------------------------------- confinement


def escapes(tmp_path: Path, workdir: Path, outside: Path) -> list[tuple[str, str]]:
    """(label, path) pairs that must never be reachable — §4 "confined"."""
    link = workdir / "escape-link"
    if not link.exists():
        link.symlink_to(outside)
    return [
        ("absolute outside", str(outside / "secret.txt")),
        ("parent traversal", f"{workdir}/../outside/secret.txt"),
        ("relative", "secret.txt"),
        ("sibling prefix", f"{workdir}-evil/secret.txt"),
        ("through a symlink", str(link / "secret.txt")),
        ("the root of the world", "/etc/passwd"),
    ]


@pytest.mark.parametrize("command", ["put", "get", "ls"])
def test_every_file_command_is_confined_to_the_allowed_roots(
    project: str, command: str, tmp_path: Path, workdir: Path, outside: Path
) -> None:
    cases = escapes(tmp_path, workdir, outside)

    async def body(daemon: Daemon) -> None:
        for label, path in cases:
            argv = [command, path] + (["--content", "written!"] if command == "put" else [])
            err = await fails(*argv)
            assert "allowed root" in err or "relative" in err or ".." in err, f"{label}: {err}"
        assert (outside / "secret.txt").read_text() == "do not read me"

    drive(body)


def test_put_from_outside_the_roots_is_refused(
    project: str, workdir: Path, outside: Path
) -> None:
    async def body(daemon: Daemon) -> None:
        err = await fails("put", str(workdir / "copy"), "--from", str(outside / "secret.txt"))
        assert "allowed root" in err
        assert not (workdir / "copy").exists()

    drive(body)


# ----------------------------------------------------- send --file (§4, §6)


def test_send_file_is_written_before_the_prompt_runs(project: str, workdir: Path) -> None:
    target = workdir / "payload" / "brief.md"
    content = "the brief\n"

    async def body(daemon: Daemon) -> None:
        sent = await ok(
            "send", "--role", "builder", "--context", "clear",
            "--file", f"{target}={content}",
            f"FAKE:cat {target}",
        )
        done = await ok("wait", sent["id"])
        # the fake binary read the file: it was on disk before the spawn
        assert done["result"] == content
        assert done["files_written"] == [
            {"path": str(target), "sha256": sha(content), "bytes": len(content.encode())}
        ]

    drive(body)


def test_send_file_outside_the_roots_refuses_the_whole_send(
    project: str, workdir: Path, outside: Path
) -> None:
    good = workdir / "good.txt"
    bad = outside / "bad.txt"

    async def body(daemon: Daemon) -> None:
        err = await fails(
            "send", "--role", "builder", "--context", "clear",
            "--file", f"{good}=good",
            "--file", f"{bad}=bad",
            "FAKE:result never",
        )
        assert "allowed root" in err
        assert not good.exists(), "a refused send must not half-write its files"
        assert not bad.exists()
        assert (await ok("jobs"))["jobs"] == [], "no job may be created by a refused send"

    drive(body)


def test_send_file_needs_a_path_equals_content_pair(project: str) -> None:
    async def body(daemon: Daemon) -> None:
        err = await fails(
            "send", "--role", "builder", "--context", "clear",
            "--file", "no-equals-sign",
            "FAKE:result never",
        )
        assert "path=content" in err

    drive(body)


def test_the_readable_form_of_put_get_and_ls(project: str, workdir: Path) -> None:
    async def body(daemon: Daemon) -> None:
        code, out, _ = await cli("put", str(workdir / "n.md"), "--content", "hello")
        assert code == 0
        assert sha("hello") in out and "5 bytes" in out

        code, out, _ = await cli("get", str(workdir / "n.md"))
        assert code == 0 and "hello" in out

        code, out, _ = await cli("ls", str(workdir))
        assert code == 0 and "n.md" in out and "file" in out

    drive(body)
