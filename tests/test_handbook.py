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


# ------------------------------------------------- mission 22 U11 (DESIGN §38)

NEW_SECTIONS = (
    "## 13. The onboarding shape",
    "## 14. The ruling round",
    "## 15. The separation rule",
    "## 16. Re-firing a consultation after a stop",
    "## 17. Human-supplied content",
    "## 18. Reading hands: `send`, `jobs`, `pipeline`, `progress`",
)


def _section(heading: str) -> str:
    text = HANDBOOK.read_text(encoding="utf-8")
    body = text.split(f"\n{heading}\n", 1)[1].split("\n## ", 1)[0]
    return re.sub(r"\s+", " ", body)


def test_the_handbook_carries_section_38s_new_sections_in_order() -> None:
    text = HANDBOOK.read_text(encoding="utf-8")
    places = [text.find(f"\n{heading}\n") for heading in NEW_SECTIONS]
    assert all(place > 0 for place in places), dict(zip(NEW_SECTIONS, places, strict=True))
    assert places == sorted(places)


@pytest.mark.parametrize(
    ("heading", "said"),
    [
        (NEW_SECTIONS[0], "From the switch point the role writes every kit"),
        (NEW_SECTIONS[0], "hands-shaped content"),
        (NEW_SECTIONS[1], "`templates/DECISIONS-owner.md`"),
        (NEW_SECTIONS[1], "`approve <job> <secret>`"),
        (NEW_SECTIONS[1], "`plan: decisions <date> (owner)`"),
        (NEW_SECTIONS[2], "name, commit, date, review number, finding id"),
        (NEW_SECTIONS[3], "refused by design"),
        (NEW_SECTIONS[3], "consult <secret> <reason>"),
        (NEW_SECTIONS[3], "hands consult [--file <path>] [<reason>]"),
        (NEW_SECTIONS[3], "hands consult: consult on job none (role human)"),
        (NEW_SECTIONS[3], "Reciting a review-shaped reply through the aux role is retired"),
        (NEW_SECTIONS[4], "`~/Downloads/<name>/`"),
        (NEW_SECTIONS[4], "`git show --stat`"),
        (NEW_SECTIONS[5], "newest first"),
        (NEW_SECTIONS[5], "a plain argument"),
        (NEW_SECTIONS[5], "`progress <secret>`"),
        (NEW_SECTIONS[5], "counts only the runs a `send` rule with `run =` started"),
    ],
)
def test_each_new_handbook_section_says_its_rule(heading: str, said: str) -> None:
    assert said in strip_paths(_section(heading)), (heading, said)


def test_section_16_retires_the_recital() -> None:
    """§42: "The handbook's §16 describes `consult` and retires the recital" — no
    aux send reciting a review is offered any more."""
    assert "hands send --role aux --context clear" not in strip_paths(_section(NEW_SECTIONS[3]))
    assert "refire.txt" not in strip_paths(_section(NEW_SECTIONS[3]))


def test_the_handbooks_reading_claims_are_the_codes(tmp_home: Path) -> None:
    """§18's claims checked against the code: `hands send` takes the prompt as a
    positional argument, and `jobs` lists newest first (`Api.jobs` reverses the
    spool's oldest-first listing)."""
    from hands.api import Api
    from hands.cli import build_parser

    args = build_parser().parse_args(
        ["send", "--role", "builder", "--context", "keep", "the answer, verbatim"]
    )
    assert args.prompt == "the answer, verbatim"
    assert "newest first" in strip_paths(Api.jobs.__doc__ or "")


# ------------------------------------------ mission 23 U7 (DESIGN §39, H-051)


def test_hands_handbook_help_names_the_directory_as_it_is() -> None:
    """§39 (REVIEW-22 should-fix 10): the handbook is `$HANDS_DOCS/docs/…`, not
    a file directly under `$HANDS_DOCS`."""
    from hands.cli import build_parser

    sub = next(a for a in build_parser()._actions if a.dest == "command")
    parser = sub.choices["handbook"]  # type: ignore[attr-defined]
    # the help text as written (format_help wraps at hyphens, so it is not read here)
    text = " ".join([parser.description, *(a.help or "" for a in parser._actions)])
    assert "$HANDS_DOCS/docs/ARCHITECT-HANDBOOK.md" in strip_paths(text)
    assert "$HANDS_DOCS/templates" in strip_paths(text)
    assert "the directory is what every role job carries as $HANDS_DOCS" not in strip_paths(text)
