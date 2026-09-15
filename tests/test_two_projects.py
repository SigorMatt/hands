"""Mission 13 U6: two projects on one laptop (DESIGN §29, with §5, §13, §14).

The spool is per project (`~/.hands/<project>/`), `hands migrate-spool` moves the
flat layout to `~/.hands/hands/`, `handsd` refuses the flat layout, the systemd
units are templated, and `hands who` shows every project's daemon as a root.
Everything runs under `tmp_home`; the real `~/.hands` is never touched.
"""

from __future__ import annotations

import io
import json
import socket
from pathlib import Path

import pytest

from conftest import strip_paths
from hands import daemon as daemon_mod
from hands import who
from hands.cli import main as hands_main
from hands.config import load_config, spool_root
from hands.daemon import Daemon
from hands.spool import EVENT_KINDS, FLAT_ITEMS, Spool, flat_layout
from harness import config_body, write_project

ROOT = Path(__file__).parents[1]


def _two_projects(home: Path, workdir: Path) -> None:
    for name in ("alpha", "beta"):
        body = config_body(home, workdir).replace(
            f'socket = "{home}/.hands/handsd.sock"\n', ""
        )
        write_project(home, body, project=name)


def _flat_fixture(hands: Path) -> None:
    (hands / "jobs").mkdir()
    (hands / "jobs" / "j1.json").write_text('{"id": "j1"}')
    (hands / "roles").mkdir()
    (hands / "roles" / "builder.json").write_text("{}")
    (hands / "inbox.jsonl").write_text("")
    (hands / "inbox.acks.jsonl").write_text("")
    (hands / "pipeline.json").write_text("{}")


# ------------------------------------------------------------------ the layout


def test_the_spools_and_default_sockets_of_two_projects_are_disjoint(
    tmp_home: Path, tmp_path: Path
) -> None:
    _two_projects(tmp_home, tmp_path)
    alpha, beta = load_config("alpha"), load_config("beta")
    assert spool_root("alpha") == tmp_home / ".hands" / "alpha"
    assert alpha.spool_root == tmp_home / ".hands" / "alpha"
    assert beta.spool_root == tmp_home / ".hands" / "beta"
    assert alpha.server.socket == tmp_home / ".hands" / "alpha" / "handsd.sock"
    assert beta.server.socket == tmp_home / ".hands" / "beta" / "handsd.sock"

    a, b = Daemon(alpha), Daemon(beta)
    paths_a = {a.spool.root, a.spool.jobs_dir, a.spool.roles_dir, a.spool.inbox_path,
               a.spool.acks_path, a.playbook.state_path, a.socket_path}  # fmt: skip
    paths_b = {b.spool.root, b.spool.jobs_dir, b.spool.roles_dir, b.spool.inbox_path,
               b.spool.acks_path, b.playbook.state_path, b.socket_path}  # fmt: skip
    assert not paths_a & paths_b
    assert all(p.is_relative_to(tmp_home / ".hands" / "alpha") for p in paths_a)
    assert all(p.is_relative_to(tmp_home / ".hands" / "beta") for p in paths_b)
    job = a.spool.create_job(role="builder", context="clear", prompt="x", origin="cli")
    assert (tmp_home / ".hands" / "alpha" / "jobs" / f"{job.id}.json").exists()
    assert not b.spool.list_jobs()
    assert flat_layout(tmp_home / ".hands") == []  # a daemon never writes the flat layout


# --------------------------------------------------------------- the migration


def test_migrate_spool_moves_the_flat_layout_to_hands_and_files_an_inbox_event(
    tmp_home: Path,
) -> None:
    hands = tmp_home / ".hands"
    _flat_fixture(hands)
    assert sorted(p.name for p in flat_layout(hands)) == sorted(FLAT_ITEMS)
    out, err = io.StringIO(), io.StringIO()
    assert hands_main(["migrate-spool"], stdout=out, stderr=err) == 0, err.getvalue()
    target = hands / "hands"
    assert flat_layout(hands) == [], "nothing is left flat"
    for name in FLAT_ITEMS:
        assert not (hands / name).exists()
        assert (target / name).exists()
    assert (target / "jobs" / "j1.json").read_text() == '{"id": "j1"}'
    assert {"spool.migrated"} <= EVENT_KINDS
    [event] = [e for e in Spool(target).events() if e.kind == "spool.migrated"]
    assert sorted(event.payload["moved"]) == sorted(FLAT_ITEMS)
    assert event.payload["to"] == str(target)
    assert "hands" in strip_paths(out.getvalue())

    # Run again: nothing flat, nothing to do, exit 0, no second event.
    out = io.StringIO()
    assert hands_main(["migrate-spool"], stdout=out, stderr=err) == 0
    assert "nothing to migrate" in strip_paths(out.getvalue())
    assert len([e for e in Spool(target).events() if e.kind == "spool.migrated"]) == 1


def test_migrate_spool_refuses_when_the_target_exists_and_moves_nothing(tmp_home: Path) -> None:
    hands = tmp_home / ".hands"
    _flat_fixture(hands)
    (hands / "hands").mkdir()
    out, err = io.StringIO(), io.StringIO()
    assert hands_main(["migrate-spool"], stdout=out, stderr=err) == 1
    assert "already exists" in strip_paths(err.getvalue())
    assert sorted(p.name for p in flat_layout(hands)) == sorted(FLAT_ITEMS)
    assert list((hands / "hands").iterdir()) == []


def test_migrate_spool_refuses_while_a_daemon_answers_on_a_socket_in_the_flat_dir(
    tmp_home: Path,
) -> None:
    hands = tmp_home / ".hands"
    _flat_fixture(hands)
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(str(hands / "handsd.sock"))
    listener.listen(1)
    try:
        out, err = io.StringIO(), io.StringIO()
        assert hands_main(["migrate-spool"], stdout=out, stderr=err) == 1
        assert "a daemon is running" in strip_paths(err.getvalue())
    finally:
        listener.close()
    assert sorted(p.name for p in flat_layout(hands)) == sorted(FLAT_ITEMS)
    assert not (hands / "hands").exists()


# ----------------------------------------------------------------- the refusal


@pytest.mark.parametrize("item", FLAT_ITEMS)
def test_handsd_refuses_a_flat_layout_with_the_migration_instruction_and_starts_nothing(
    tmp_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str], item: str,
) -> None:  # fmt: skip
    write_project(tmp_home, config_body(tmp_home, tmp_path), project="demo")
    hands = tmp_home / ".hands"
    if item in ("jobs", "roles"):
        (hands / item).mkdir()
    else:
        (hands / item).write_text("")
    started: list[object] = []

    async def serve(*args: object) -> int:  # pragma: no cover - must not run
        started.append(args)
        return 0

    monkeypatch.setattr(daemon_mod, "_serve", serve)
    assert daemon_mod.main(["--project", "demo"]) != 0
    err = capsys.readouterr().err
    assert "hands migrate-spool" in strip_paths(err)
    assert started == []
    assert not (hands / "demo").exists(), "no per-project spool was created"
    assert not (hands / "handsd.sock").exists()


# ------------------------------------------------------------------- hands who


def test_hands_who_with_two_fixture_spools_shows_two_roots(
    tmp_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _two_projects(tmp_home, tmp_path)
    for name in ("alpha", "beta"):
        jobs = tmp_home / ".hands" / name / "jobs"
        jobs.mkdir(parents=True)
        (jobs / f"{name}1.json").write_text(json.dumps({"id": f"{name}1", "session_id": name}))
    monkeypatch.delenv("HANDS_PROJECT", raising=False)
    monkeypatch.setattr(who, "proc_table", lambda: {})

    out, err = io.StringIO(), io.StringIO()
    assert hands_main(["who"], stdout=out, stderr=err) == 0, err.getvalue()
    assert strip_paths(out.getvalue()).count("handsd (daemon, project ") == 2
    assert "handsd (daemon, project alpha)\n    not answering" in strip_paths(out.getvalue())
    assert "handsd (daemon, project beta)\n    not answering" in strip_paths(out.getvalue())

    # Named: the named project first, every other project still a root.
    out = io.StringIO()
    assert hands_main(["--project", "beta", "who", "--json"], stdout=out, stderr=err) == 0
    payload = json.loads(out.getvalue())
    assert payload["picture"].index("project beta") < payload["picture"].index("project alpha")
    assert sorted(payload["daemons"]) == ["alpha", "beta"]

    # Each root reads its own spool.
    srcs = who.all_sources(load_config("alpha"), None)
    assert [s.project for s in srcs] == ["alpha", "beta"]
    assert [s.job_sessions() for s in srcs] == [frozenset({"alpha"}), frozenset({"beta"})]


# --------------------------------------------------------------------- systemd


def test_systemd_holds_only_templated_units_reading_the_per_project_env_file() -> None:
    units = sorted(p.name for p in (ROOT / "systemd").iterdir())
    assert units == ["handsd@.service", "handswho@.service"]
    for name in units:
        text = (ROOT / "systemd" / name).read_text(encoding="utf-8")
        assert "EnvironmentFile=%h/.config/hands/%i.env" in strip_paths(text)
        exec_start = [line for line in text.splitlines() if line.startswith("ExecStart=")]
        binary = name.split("@")[0]
        assert exec_start == [f"ExecStart=%h/.local/bin/{binary} --project %i"]
