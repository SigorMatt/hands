"""U0 scaffold: the package imports, the CLI answers --help, tmp_home isolates HOME."""

import os
from pathlib import Path

import pytest

import hands
from hands.cli import main


def test_package_has_a_version() -> None:
    assert isinstance(hands.__version__, str)
    assert hands.__version__


def test_tmp_home_redirects_home_and_hands_dir(tmp_home: Path) -> None:
    # HOME is the fixture's directory, not the real user's.
    assert os.environ["HOME"] == str(tmp_home)
    assert Path.home() == tmp_home
    assert Path("~").expanduser() == tmp_home

    # ~/.hands exists inside it and is writable, so later units may use it freely.
    hands_dir = Path("~/.hands").expanduser()
    assert hands_dir == tmp_home / ".hands"
    assert hands_dir.is_dir()
    (hands_dir / "probe").write_text("ok")
    assert (tmp_home / ".hands" / "probe").read_text() == "ok"


def test_tmp_home_is_undone_after_the_test() -> None:
    # The monkeypatched HOME does not leak into the next test.
    assert Path.home() != Path("/nonexistent")
    assert not Path("~/.hands/probe").expanduser().exists()


def test_cli_help_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    assert "usage: hands" in capsys.readouterr().out


def test_cli_with_no_arguments_prints_help_and_returns_zero(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main([]) == 0
    assert "usage: hands" in capsys.readouterr().out
