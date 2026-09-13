"""Shared fixtures. Every test that touches the filesystem should take `tmp_home`."""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture
def tmp_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Point HOME (and therefore `~/.hands`) at a temp dir for the duration of a test.

    `~/.hands` is created empty, so a test can write job records, sockets and
    config there without ever touching the real home directory.
    """
    home = tmp_path / "home"
    (home / ".hands").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.chdir(tmp_path)
    yield home


MINIMAL_CONFIG = """
[roles.builder]
cwd = "~/git/demo"
"""


@pytest.fixture
def write_config(tmp_home: Path):
    """Write `~/.hands/<project>.toml` and return its path.

    `body` is TOML text; when omitted a minimal valid config is written, so a
    test that only cares about defaults does not have to spell the file out.
    """

    def _write(body: str | None = None, project: str = "demo") -> Path:
        if body is None:
            body = MINIMAL_CONFIG
        path = tmp_home / ".hands" / f"{project}.toml"
        path.write_text(body)
        return path

    return _write


_INJECTED: tuple[Path, ...] = ()


@pytest.fixture(autouse=True)
def _injected_paths(tmp_path: Path, tmp_path_factory: pytest.TempPathFactory) -> Iterator[None]:
    """Record, for one test, the paths pytest itself chose: `tmp_path` and `--basetemp`.

    `strip_paths` is a plain function so that any test or helper can call it
    without taking a fixture; this is where it learns the two paths it cannot
    derive from the environment.
    """
    global _INJECTED
    _INJECTED = (tmp_path, tmp_path_factory.getbasetemp())
    yield
    _INJECTED = ()


def strip_paths(text: str, *extra: str | Path) -> str:
    """Return `text` with every path the *environment* put in it replaced by `<path>`.

    Stripped, longest match first: any `extra` path the caller names (the ops
    repo, a config file), the per-test `tmp_path` and pytest's `--basetemp`,
    `$HOME` with `~/.hands` and the daemon socket `~/.hands/handsd.sock` under
    it, and the current working directory — plus the resolved form of each. A
    directory of fewer than three components (`/`, `/home`, `/tmp`) is never
    stripped: that would delete the text rather than the path. Only prefixes
    go, so what the product printed *after* a path (`watch_monitor.sh`,
    `demo.toml`) is still there to assert on.

    Why (DESIGN §21, review 4 should-fix 1 and 2): none of these paths are the
    product's choice. `assert "--pids" not in out` went red under
    `--basetemp=/tmp/ptY/z--pids`, because `~/.hands/handsd.sock` in `hands
    status` output carried the basetemp; `assert "200" in out` would go green
    the same way, without the product printing anything, and no run can report
    that. Comparing against stripped text makes an assertion a property of the
    product instead of a property of where the run put its files.
    """
    candidates: list[Path] = [Path(path) for path in extra]
    candidates.extend(_INJECTED)
    home = os.environ.get("HOME")
    if home:
        candidates += [Path(home) / ".hands" / "handsd.sock", Path(home) / ".hands", Path(home)]
    try:
        candidates.append(Path.cwd())
    except OSError:  # a test deleted its own working directory
        pass

    forms: set[str] = set()
    for candidate in candidates:
        shapes = [candidate]
        try:
            shapes.append(candidate.resolve())
        except OSError:
            pass
        forms.update(str(shape) for shape in shapes if len(shape.parts) > 2)
    for form in sorted(forms, key=len, reverse=True):
        text = text.replace(form, "<path>")
    return text


@pytest.fixture(autouse=True)
def _process_group_isolation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every job in the suite runs in process-group mode (DESIGN §24).

    `hands.runner.detect_isolation` asks the machine whether a transient systemd
    user scope can be started. A developer box with a user manager says yes and
    CI may say no, so the suite would run jobs two different ways depending on
    where it runs. It is pinned to the process group here; a test that wants the
    scope path sets `Runner.isolation` or patches this function itself.
    """
    import hands.runner

    monkeypatch.setattr(hands.runner, "detect_isolation", lambda: hands.runner.GROUP)


def commit_file(repo: Path, name: str, body: str | bytes) -> str:
    """Write `repo/name` and commit it; return the sha256 of the bytes committed.

    DESIGN §10 (§25): hands refuses a playbook that differs from `git show
    HEAD:<path>`, so a test that loads one has to commit it first. `repo` is
    `git init`ed when it is not a repository yet, with its identity, signing and
    hooks set in the repository's *local* config only — the global config is
    never written.
    """
    import hashlib
    import subprocess

    def git(*args: str) -> None:
        subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)

    repo.mkdir(parents=True, exist_ok=True)
    if not (repo / ".git" / "HEAD").exists():  # an empty `.git` stand-in is not a repo
        git("init", "-q")
    git("config", "--local", "user.name", "hands tests")
    git("config", "--local", "user.email", "tests@hands.invalid")
    git("config", "--local", "commit.gpgsign", "false")
    git("config", "--local", "core.hooksPath", "/dev/null")
    data = body.encode("utf-8") if isinstance(body, str) else body
    target = repo / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    git("add", "--", name)
    git("commit", "-q", "--allow-empty", "-m", f"test: {name}")
    return hashlib.sha256(data).hexdigest()


def process_live(pid: int) -> bool:
    """Is `pid` a running process? A zombie is not: it has already exited."""
    try:
        text = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    fields = text[text.rindex(")") + 1 :].split()
    return bool(fields) and fields[0] not in ("Z", "X")


def kill_quietly(pid: int) -> None:
    """Teardown for a test that made a process meant to die: never leave one behind."""
    import signal

    if process_live(pid):
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass
