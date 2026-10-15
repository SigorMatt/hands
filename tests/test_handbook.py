"""DESIGN §38 "Onboarding" (HF-002, HF-004, HF-005; mission 22 U9).

The installed hands ships `docs/` and `templates/` as package data; `hands
handbook` prints the installed handbook's path and `--templates` the templates
directory; the runner exports `HANDS_DOCS` to every role job; the handbook's §6
lists every `[series]` key with the default `playbook.py` gives it.
"""

from __future__ import annotations

import asyncio
import io
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from conftest import strip_paths
from hands.cli import main as hands_main
from hands.config import DOCS_ENV, docs_root, parse_config
from hands.playbook import SERIES_KEYS, parse_playbook
from hands.runner import Runner
from hands.spool import Spool

ROOT = Path(__file__).parents[1]
HANDBOOK = ROOT / "docs" / "ARCHITECT-HANDBOOK.md"
TEMPLATES = ROOT / "templates"
FAKE = ROOT / "tests" / "fake_claude.py"


def _run(argv: list[str]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    code = hands_main(argv, stdout=out, stderr=err)
    return code, out.getvalue(), err.getvalue()


def test_hands_handbook_prints_the_handbook_this_hands_carries(tmp_home: Path) -> None:
    """No config, no daemon (a client command, as `kit check` is): one line, the
    path of a file whose bytes are the handbook's."""
    code, out, err = _run(["handbook"])
    assert code == 0, err
    path = Path(out.strip())
    assert path.is_absolute() and path.is_file(), out
    assert path.name == "ARCHITECT-HANDBOOK.md"
    assert path.read_bytes() == HANDBOOK.read_bytes()
    assert path == docs_root() / "docs" / "ARCHITECT-HANDBOOK.md"


def test_hands_handbook_templates_prints_the_templates_directory(tmp_home: Path) -> None:
    code, out, err = _run(["handbook", "--templates"])
    assert code == 0, err
    path = Path(out.strip())
    assert path.is_dir(), out
    assert path == docs_root() / "templates"
    names = sorted(p.name for p in TEMPLATES.iterdir())
    assert sorted(p.name for p in path.iterdir()) == names
    for name in names:
        assert (path / name).read_bytes() == (TEMPLATES / name).read_bytes(), name


def test_the_installed_wheel_carries_the_handbook_and_templates(tmp_path: Path) -> None:
    """The wheel, not the source tree: build it (offline, from the build cache the
    gate's `uv sync` fills), unpack it, and run `hands handbook` from the unpacked
    package alone. Both paths resolve inside that package's `hands/shipped/`."""
    uv = shutil.which("uv")
    assert uv is not None, "the gate runs under uv; the wheel is built with it"
    dist = tmp_path / "dist"
    built = subprocess.run(
        [uv, "build", "--wheel", "--offline", "--quiet", "-o", str(dist)],
        cwd=ROOT, capture_output=True, text=True, timeout=300,
    )
    assert built.returncode == 0, built.stderr
    (wheel,) = dist.glob("hands-*.whl")
    site = tmp_path / "site"
    with zipfile.ZipFile(wheel) as zf:
        zf.extractall(site)
    probe = (
        "import sys, hands; from hands.cli import main; "
        "assert hands.__file__.startswith(sys.argv[1]), hands.__file__; "
        "main(['handbook']); main(['handbook', '--templates'])"
    )
    ran = subprocess.run(
        [sys.executable, "-c", probe, str(site)],
        cwd=tmp_path, capture_output=True, text=True, timeout=60,
        env={"PYTHONPATH": str(site), "PATH": "/usr/bin:/bin", "HOME": str(tmp_path)},
    )
    assert ran.returncode == 0, ran.stderr
    handbook, templates = (Path(line) for line in ran.stdout.splitlines())
    shipped = site / "hands" / "shipped"
    assert handbook == shipped / "docs" / "ARCHITECT-HANDBOOK.md"
    assert handbook.read_bytes() == HANDBOOK.read_bytes()
    assert templates == shipped / "templates"
    assert sorted(p.name for p in templates.iterdir()) == sorted(
        p.name for p in TEMPLATES.iterdir()
    )


@pytest.mark.parametrize("role", ["builder", "aux", "driver", "architect"])
def test_every_role_job_carries_hands_docs(
    tmp_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, role: str
) -> None:
    """§38 (HF-002): every role job's environment carries `HANDS_DOCS`, the
    directory of the handbook and templates of the hands that runs it — over
    handsd's environment and the role's env table alike."""
    monkeypatch.setenv(DOCS_ENV, "/elsewhere")
    cwd = tmp_path / "work"
    cwd.mkdir()
    cfg = parse_config(
        {
            "roles": {
                "builder": {"cwd": str(cwd)},
                role: {"cwd": str(cwd), "env": {DOCS_ENV: "/table"}},
            },
            "runner": {"claude": str(FAKE)},
        },
        project="demo",
        path=tmp_home / ".hands" / "demo.toml",
    )
    spool = Spool(tmp_home / ".hands" / "demo")
    job = spool.create_job(role=role, context="clear", prompt=f"FAKE:env {DOCS_ENV}",
                           origin="cli")
    done = asyncio.run(Runner(cfg, spool).run(job))
    assert done.result == str(docs_root()), done
    assert (Path(done.result) / "docs" / "ARCHITECT-HANDBOOK.md").is_file()
    assert (Path(done.result) / "templates").is_dir()


def _section_6_keys() -> dict[str, str]:
    text = HANDBOOK.read_text(encoding="utf-8")
    section = text.split("\n## 6. ")[1].split("\n## 7. ")[0]
    found = re.findall(r"^- `([a-z_]+)` \(([^)]*)\)", section, flags=re.M)
    return dict(found)


def _rendered(value: object) -> str:
    if value is None or value == ():
        return "none"
    if isinstance(value, bool):
        return "`true`" if value else "`false`"
    if isinstance(value, str):
        return f"`{value}`"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def test_handbook_section_6_lists_every_series_key_with_its_playbook_default(
    tmp_path: Path,
) -> None:
    """HF-004: §6's bullets are `playbook.SERIES_KEYS`, in order, each with the
    default the loader gives a playbook that omits it (`no default` for the two
    a `[series]` table has none for)."""
    listed = _section_6_keys()
    assert list(listed) == list(SERIES_KEYS)
    text = (
        'version = 1\n[series]\nname = "s"\n'
        '[[rule]]\non = "builder.done"\nthen = "stop"\nmessage = "m"\n'
    )
    playbook = parse_playbook(text, path=tmp_path / "PLAYBOOK.toml")
    for key in SERIES_KEYS:
        if key in ("name", "kickoff"):
            assert listed[key] == "no default", key
            continue
        assert listed[key] == f"default {_rendered(getattr(playbook, key))}", key


def test_handbook_section_12_names_the_laptop_check_and_the_silent_first_apply() -> None:
    """HF-005: §12 names `hands kit check <kit> --repo <clone>` at the laptop before
    a role-mode plan kit is applied, and the first plan kit's silent apply."""
    text = HANDBOOK.read_text(encoding="utf-8")
    section = text.split("\n## 12. ")[1]
    assert "hands kit check <kit> --repo <clone>" in strip_paths(section)
    assert "silent" in strip_paths(section)
    assert "kickoff" in strip_paths(section)


@pytest.mark.parametrize(
    "path", [ROOT / "architect" / "CLAUDE.md", ROOT / "docs" / "ARCHITECT-INSTRUCTION.md"]
)
def test_each_architect_instruction_reads_the_handbook_from_hands_docs(path: Path) -> None:
    """§38 (HF-002): both instructions send the architect to `$HANDS_DOCS`, the
    installed hands' handbook and templates, and neither to the clone's copy."""
    text = re.sub(r"\s+", " ", path.read_text(encoding="utf-8"))
    assert "`$HANDS_DOCS/docs/ARCHITECT-HANDBOOK.md`" in strip_paths(text)
    assert "`$HANDS_DOCS/templates/`" in strip_paths(text)
    assert "`docs/ARCHITECT-HANDBOOK.md` from the clone" not in strip_paths(text)
    assert "clone https://github.com/SigorMatt/hands" not in strip_paths(text)
