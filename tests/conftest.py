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
    directory with fewer than two components (`/`, `/home`) is never stripped:
    that would delete the text rather than the path. Only prefixes go, so what
    the product printed *after* a path (`watch_monitor.sh`, `demo.toml`) is
    still there to assert on.

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
