"""Shared fixtures. Every test that touches the filesystem should take `tmp_home`."""

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
