"""Mission 26 U2: `hands digest` (DESIGN §42 "`digest`"; §41's redact-then-cut rule).

`hands digest` prints one line per `~/.hands/<project>.toml` in name order — the
project, its daemon, its pipeline, its mission, its builder, its consultations and
its last stop — and needs no daemon. A config that does not load is one line naming
its file only. Every line is redacted of every loadable project's `cmd_secret` and
`ntfy_token` before any field is cut. The phone's `digest <secret>` is tested in
`tests/test_phone.py`; the guard's refusal in `tests/test_bash_guard.py`.

The spools, repositories and configs live under the test's temporary home; the
one daemon that answers is a stand-in on a unix socket in a thread.
"""

from __future__ import annotations

import io
import json
import re
import shutil
import socket
import tempfile
import threading
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from conftest import commit_file, strip_paths
from hands import digest as digest_mod
from hands.cli import main
from hands.config import ConfigError, load_config
from hands.spool import Spool

ALPHA_SECRET = "Alpha-cmd-S3cret-0123456789abcdefXYZ"
ALPHA_TOKEN = "tk_alpha_TOKEN_9f8e7d6c5b4a39281706"
BETA_SECRET = "Beta-cmd-S3cret-fedcba9876543210QRS"
#: The bad value of the config that does not load: secret-shaped, and quoted by the
#: loader's message (the test checks that it is, so its absence means something).
LEAKY = "Leaky-SECRET-value-0123456789abcdef"
NTFY = "https://ntfy.example"

#: §42: the stop reason's first line is cut to 100 characters; ALPHA_SECRET starts
#: at character 90 of it, so a cut made before the redaction would keep its first
#: ten characters.
STOP_REASON = ("r" * 90) + ALPHA_SECRET + " and the rest\nsecond line " + BETA_SECRET
VERDICT = "VERDICT: unit done " + ("v" * 80)


def config_text(home: Path, name: str, workdir: Path, *, secret: str, token: str | None = None,
                sock: Path | None = None) -> str:
    token_line = f'ntfy_token = "{token}"' if token else ""
    sock = sock if sock is not None else home / ".hands" / name / "handsd.sock"
    return f"""
[server]
socket = "{sock}"

[roles.builder]
cwd = "{workdir}"

[notify]
ntfy_url = "{NTFY}"
ntfy_topic = "{name}-events"
cmd_topic = "{name}-cmd"
cmd_secret = "{secret}"
{token_line}
"""


def iso(delta: timedelta = timedelta(0)) -> str:
    return (datetime.now(UTC) - delta).isoformat(timespec="seconds").replace("+00:00", "Z")


class Machine:
    """Two projects with spools under the temporary home, and one broken config."""

    def __init__(self, home: Path, tmp_path: Path) -> None:
        self.home = home
        self.hands = home / ".hands"
        self.alpha_work = tmp_path / "alpha-work"
        self.beta_work = tmp_path / "beta-work"

    # alpha: paused by a stop; phone mode; an ended builder job with a verdict.
    def alpha(self) -> None:
        (self.hands / "alpha.toml").write_text(config_text(
            self.home, "alpha", self.alpha_work, secret=ALPHA_SECRET, token=ALPHA_TOKEN))
        commit_file(self.alpha_work, "PLAYBOOK.toml", "version = 1\n[limits]\nmax_consults = 4\n")
        (self.alpha_work / "meta").mkdir()
        (self.alpha_work / "meta" / "CHECKPOINT.md").write_text(
            "# CHECKPOINT\n\nBranch: x\nMission: 7 (meta/BUILDER-7-PROMPT.md).\nMission: 8\n",
            encoding="utf-8",
        )
        spool = Spool(self.hands / "alpha")
        job = spool.create_job(role="builder", context="clear", prompt="p", origin="cli")
        spool.transition(job, "running", started=iso(timedelta(minutes=30)))
        spool.transition(job.id, "done", ended=iso(), verdict=VERDICT)
        spool.create_job(role="driver", context="clear", prompt="d", origin="playbook")
        spool.append_event("stop", {"reason": "an older stop"})
        stop = spool.append_event("stop", {"reason": STOP_REASON})
        self.alpha_stop_at = stop.created
        (self.hands / "alpha" / "pipeline.json").write_text(json.dumps({
            "paused": True, "paused_by": "stop", "stop_reason": STOP_REASON,
            "stopped_at": stop.created,
        }))

    # beta: running; role mode; a builder job running for 17 minutes.
    def beta(self, sock: Path | None = None) -> None:
        (self.hands / "beta.toml").write_text(config_text(
            self.home, "beta", self.beta_work, secret=BETA_SECRET, sock=sock))
        commit_file(self.beta_work, "PLAYBOOK.toml", (
            'version = 1\n[series]\nname = "s1"\narchitect = "role"\n'
            "[limits]\nmax_architect_consults = 5\n"))
        spool = Spool(self.hands / "beta")
        spool.create_job(role="architect", context="clear", prompt="a", origin="playbook")
        job = spool.create_job(role="builder", context="clear", prompt="b", origin="cli")
        spool.transition(job, "running", started=iso(timedelta(minutes=17, seconds=5)))
        self.beta_job = job.id

    def broken(self) -> None:
        (self.hands / "broken.toml").write_text(f'[roles.builder]\ncwd = "{LEAKY}"\n')


@pytest.fixture
def machine(tmp_home: Path, tmp_path: Path) -> Machine:
    m = Machine(tmp_home, tmp_path)
    m.alpha()
    m.broken()
    return m


def run_digest(*argv: str) -> tuple[int, str]:
    out, err = io.StringIO(), io.StringIO()
    code = main(["digest", *argv], stdout=out, stderr=err)
    return code, out.getvalue() + err.getvalue()


#: The methods the stand-in daemon was asked, in order.
ASKED: list[str] = []


@pytest.fixture
def answering() -> Iterator[Path]:
    """A stand-in daemon: a unix socket that answers one JSON-RPC `status` per
    connection, in a thread. Its path is short, as a unix socket's must be."""
    where = Path(tempfile.mkdtemp(prefix="hd-"))
    path = where / "s.sock"
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(str(path))
    server.listen(4)
    methods = ASKED
    methods.clear()
    stop = threading.Event()

    def serve() -> None:
        server.settimeout(0.2)
        while not stop.is_set():
            try:
                conn, _ = server.accept()
            except TimeoutError:
                continue
            except OSError:
                return
            with conn, conn.makefile("rw", encoding="utf-8", newline="\n") as stream:
                request = json.loads(stream.readline())
                methods.append(request["method"])
                stream.write(json.dumps({"jsonrpc": "2.0", "id": request["id"],
                                         "result": {"roles": {}}}) + "\n")
                stream.flush()

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    try:
        yield path
    finally:
        stop.set()
        thread.join(5)
        server.close()
        shutil.rmtree(where, ignore_errors=True)


# ------------------------------------------------------------------ the lines


def test_digest_prints_one_line_per_config_in_name_order_with_section_42s_fields(
    machine: Machine, answering: Path
) -> None:
    machine.beta(sock=answering)
    code, out = run_digest()
    assert code == 0, out
    lines = out.splitlines()
    assert len(lines) == 3, lines
    alpha, beta, broken = lines
    # alpha: no daemon on its socket; paused by its stop; the checkpoint's first
    # `Mission:` line; idle, the newest builder job's verdict cut to 60; phone mode,
    # one driver consultation of a budget of four; the newest stop, redacted, cut.
    assert alpha == " | ".join([
        "alpha", "daemon down", "pipeline paused", "mission 7",
        f"builder idle, verdict {VERDICT[:60]}", "driver 1/4",
        f"stop {machine.alpha_stop_at} {('r' * 90 + '[redacted]')}",
    ])
    # beta: its daemon answers `status`; running; no checkpoint; its running job and
    # its age; role mode, one architect consultation of five; never stopped.
    assert re.fullmatch(
        rf"beta \| daemon up \| pipeline running \| mission - \| builder running "
        rf"{machine.beta_job} 17m, verdict none \| architect 1/5 \| no stop",
        beta,
    ), beta
    assert ASKED == ["status"]
    assert broken == "broken.toml: does not load"


def test_a_config_that_does_not_load_is_named_by_its_file_never_its_value(
    machine: Machine,
) -> None:
    with pytest.raises(ConfigError) as caught:
        load_config("broken")
    assert LEAKY in strip_paths(str(caught.value))  # the loader's message quotes the value
    code, out = run_digest()
    assert code == 0
    assert LEAKY not in strip_paths(out) and LEAKY[:12] not in strip_paths(out)
    assert out.splitlines()[-1] == "broken.toml: does not load"
    assert "cwd" not in strip_paths(out.split("broken.toml", 1)[1])  # nothing of the message


def test_every_secret_of_every_loadable_project_is_redacted_before_the_cut(
    machine: Machine,
) -> None:
    """The planted secret straddles the 100-character cut of the stop reason: it is
    absent in full, not cut into a prefix the redaction no longer matches. Every
    loadable project's secret and token is absent from every line."""
    machine.beta()
    spool = Spool(machine.hands / "beta")
    job = spool.create_job(role="builder", context="clear", prompt="c", origin="cli")
    spool.transition(job, "running", started=iso())
    spool.transition(job.id, "done", ended=iso(), verdict=f"VERDICT: {ALPHA_TOKEN} x {BETA_SECRET}")
    code, out = run_digest()
    assert code == 0
    for value in (ALPHA_SECRET, ALPHA_TOKEN, BETA_SECRET):
        assert value not in strip_paths(out)
        assert value[:10] not in strip_paths(out), value  # no piece left at a cut
        assert value.lower()[:10] not in strip_paths(out.lower())
    beta = out.splitlines()[1]
    assert "verdict VERDICT: [redacted] x [redacted]" in strip_paths(beta)


def test_digest_needs_no_daemon_and_a_down_daemon_reads_down(
    machine: Machine, tmp_path: Path
) -> None:
    """No socket at all, and a socket file nobody listens on, both read `down`;
    the command answers without one."""
    stale = Path(tempfile.mkdtemp(prefix="hd-")) / "s.sock"
    try:
        dead = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        dead.bind(str(stale))
        dead.close()  # the file stays; nothing listens
        machine.beta(sock=stale)
        code, out = run_digest()
    finally:
        shutil.rmtree(stale.parent, ignore_errors=True)
    assert code == 0
    alpha, beta = out.splitlines()[:2]
    assert " | daemon down | " in strip_paths(alpha)
    assert " | daemon down | " in strip_paths(beta)


def test_digest_is_read_only(machine: Machine) -> None:
    """It reads each spool and repository; it writes nothing, not even a spool
    directory for a project whose daemon never ran."""
    machine.beta()
    shutil.rmtree(machine.hands / "beta")
    before = sorted((p, p.stat().st_mtime_ns) for p in machine.home.rglob("*") if p.is_file())
    dirs = sorted(p for p in machine.home.rglob("*") if p.is_dir())
    code, out = run_digest()
    assert code == 0
    assert sorted((p, p.stat().st_mtime_ns) for p in machine.home.rglob("*")
                  if p.is_file()) == before
    assert sorted(p for p in machine.home.rglob("*") if p.is_dir()) == dirs
    assert out.splitlines()[1].startswith("beta | daemon down | pipeline running | ")


def test_digest_json_carries_the_same_lines(machine: Machine) -> None:
    code, out = run_digest("--json")
    assert code == 0
    assert json.loads(out) == {"lines": digest_mod.digest_lines(machine.hands)}


def test_the_daemon_probe_gives_up_within_two_seconds(tmp_path: Path) -> None:
    """§42: `up` only when the socket answers `status` within two seconds; one that
    accepts and never answers is `down`."""
    where = Path(tempfile.mkdtemp(prefix="hd-"))
    path = where / "s.sock"
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(str(path))
    server.listen(1)
    try:
        started = datetime.now(UTC)
        assert digest_mod.daemon_answers(path) is False
        assert datetime.now(UTC) - started < timedelta(seconds=4)
    finally:
        server.close()
        shutil.rmtree(where, ignore_errors=True)
    assert digest_mod.STATUS_TIMEOUT_S == 2.0
