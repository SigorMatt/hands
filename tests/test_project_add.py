"""DESIGN §38 "Onboarding": `hands project add <name> --repo <url> [--dry-run]`
(mission 22 U10).

Every test runs against a temp HOME, a fake `systemctl` on PATH that records its
argv, and a local bare repository as the url: no real systemd, no remote, no
`claude`.
"""

from __future__ import annotations

import io
import os
import re
import shutil
import stat
import subprocess
import zipfile
from pathlib import Path

import pytest

from conftest import strip_paths
from hands.cli import main as hands_main
from hands.config import docs_root, load_config
from hands.doctor import SHIPPED_GUARDS
from hands.project import generated_topics

ROOT = Path(__file__).parents[1]
NTFY_TOPIC_RE = re.compile(r"[-_A-Za-z0-9]{1,64}")


def _run(argv: list[str]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    code = hands_main(argv, stdout=out, stderr=err)
    return code, out.getvalue(), err.getvalue()


def _git(*args: str, cwd: Path | None = None) -> str:
    done = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True, timeout=60
    )
    return done.stdout.strip()


@pytest.fixture
def fake_systemctl(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A `systemctl` on PATH that appends its argv to a log and exits 0. PATH is
    otherwise the system's own directories, so no real `claude` is found."""
    bin_dir = tmp_path / "fakebin"
    bin_dir.mkdir()
    log = tmp_path / "systemctl.log"
    script = bin_dir / "systemctl"
    script.write_text(f'#!/bin/sh\necho "$*" >> {log}\nexit 0\n')
    script.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}:/usr/local/bin:/usr/bin:/bin")
    return log


@pytest.fixture
def bare_repo(tmp_path: Path) -> Path:
    """A local bare repository with one commit on main: the project's url."""
    work = tmp_path / "seed"
    work.mkdir()
    _git("init", "-q", "-b", "main", cwd=work)
    (work / "README.md").write_text("seed\n")
    _git("add", "README.md", cwd=work)
    _git(
        "-c", "user.name=t", "-c", "user.email=t@example.invalid",
        "commit", "-q", "-m", "seed", cwd=work,
    )
    bare = tmp_path / "proj.git"
    _git("clone", "-q", "--bare", str(work), str(bare))
    return bare


def _tree(root: Path) -> list[str]:
    return sorted(str(p.relative_to(root)) for p in root.rglob("*"))


def _paths(home: Path, name: str) -> dict[str, Path]:
    driver = home / "hands-driver" / name
    architect = home / "hands-architect" / name
    return {
        "config": home / ".hands" / f"{name}.toml",
        "secret": home / ".hands" / f"{name}.cmd_secret",
        "env": home / ".config" / "hands" / f"{name}.env",
        "unit": home / ".config" / "systemd" / "user" / "handsd@.service",
        "driver_settings": driver / ".claude" / "settings.json",
        "driver_guard": driver / ".claude" / "hooks" / "bash_guard.py",
        "driver_claude": driver / "CLAUDE.md",
        "driver_repo": driver / "repo",
        "architect_settings": architect / ".claude" / "settings.json",
        "architect_guard": architect / ".claude" / "hooks" / "bash_guard.py",
        "architect_claude": architect / "CLAUDE.md",
        "architect_repo": architect / "repo",
        "architect_kits": architect / "kits",
    }


def test_dry_run_lists_every_path_and_writes_nothing(
    tmp_home: Path, fake_systemctl: Path, bare_repo: Path
) -> None:
    before = _tree(tmp_home)
    code, out, err = _run(["project", "add", "demo", "--repo", str(bare_repo), "--dry-run"])
    assert code == 0, err
    for key, path in _paths(tmp_home, "demo").items():
        assert str(path) in out, (key, out)
    assert "systemctl --user enable handsd@demo" in strip_paths(out)
    assert _tree(tmp_home) == before
    assert not fake_systemctl.exists(), "a dry run runs no systemctl"


def test_add_creates_the_project_with_modes_and_a_fetch_only_clone(
    tmp_home: Path, fake_systemctl: Path, bare_repo: Path
) -> None:
    code, out, err = _run(["project", "add", "demo", "--repo", str(bare_repo)])
    assert code == 0, err + out
    paths = _paths(tmp_home, "demo")
    root = docs_root()
    assert root is not None
    guard = next(p for p in SHIPPED_GUARDS if p.is_file())

    # The config and the secret: mode 600, and the config loads.
    assert stat.S_IMODE(paths["secret"].stat().st_mode) == 0o600
    assert stat.S_IMODE(paths["config"].stat().st_mode) == 0o600
    secret = paths["secret"].read_text().strip()
    assert len(secret) >= 32 and not any(ch.isspace() for ch in secret)
    config = load_config("demo")
    notify = config.notify
    topics = [notify.ntfy_topic, notify.cmd_topic, notify.who_topic, notify.who_cmd_topic]
    assert len(set(topics)) == 4
    for topic in topics:
        assert topic is not None and NTFY_TOPIC_RE.fullmatch(topic), topic
        assert "demo" in strip_paths(topic), topic
    assert notify.cmd_secret == secret
    assert config.roles["driver"].cwd == tmp_home / "hands-driver" / "demo"
    assert config.roles["architect"].cwd == tmp_home / "hands-architect" / "demo"
    assert paths["env"].is_file()
    assert paths["unit"].read_bytes() == (root / "systemd" / "handsd@.service").read_bytes()

    # Both role directories: the shipped settings and guard, a fetch-only clone.
    for role in ("driver", "architect"):
        assert paths[f"{role}_settings"].read_bytes() == (
            root / role / "settings.json"
        ).read_bytes()
        assert paths[f"{role}_guard"].read_bytes() == guard.read_bytes()
        repo = paths[f"{role}_repo"]
        assert _git("-C", str(repo), "remote", "get-url", "origin") == str(bare_repo)
        assert _git("-C", str(repo), "remote", "get-url", "--push", "origin") == "no_push"
        text = paths[f"{role}_claude"].read_text()
        assert re.search(r"^\s*PROJECT\s*= demo\s*$", text, re.M), text
        assert re.search(rf"^\s*REPO_URL\s*= {re.escape(str(bare_repo))}\s*$", text, re.M)
        assert "<public https url>" not in strip_paths(text)
    assert paths["architect_kits"].is_dir()
    # The architect role's CLAUDE.md is the role variant (it files kits).
    assert "hands kit file" in strip_paths(paths["architect_claude"].read_text())

    # systemd: handsd@demo enabled, handswho@demo left for the human.
    calls = fake_systemctl.read_text().splitlines()
    assert calls == ["--user daemon-reload", "--user enable handsd@demo"]

    # Doctor ran; the filled Project instruction and the question come last.
    assert "== hands doctor ==" in strip_paths(out)
    instruction = out.split("== Project instruction")[-1]
    assert re.search(r"^\s*PROJECT\s*= demo\s*$", instruction, re.M)
    assert re.search(rf"^\s*REPO_URL\s*= {re.escape(str(bare_repo))}\s*$", instruction, re.M)
    assert "You are the ARCHITECT" in strip_paths(instruction)
    assert out.rstrip().splitlines()[-1] == "What are your Parameters?"


def test_add_refuses_an_existing_project(
    tmp_home: Path, fake_systemctl: Path, bare_repo: Path
) -> None:
    (tmp_home / ".hands" / "demo.toml").write_text("[roles.builder]\ncwd = '~'\n")
    before = _tree(tmp_home)
    code, out, err = _run(["project", "add", "demo", "--repo", str(bare_repo)])
    assert code == 1
    assert "demo.toml" in strip_paths(err)
    assert _tree(tmp_home) == before
    assert not fake_systemctl.exists()


def test_add_refuses_an_existing_spool(
    tmp_home: Path, fake_systemctl: Path, bare_repo: Path
) -> None:
    (tmp_home / ".hands" / "demo").mkdir()
    before = _tree(tmp_home)
    code, _, err = _run(["project", "add", "demo", "--repo", str(bare_repo)])
    assert code == 1 and str(tmp_home / ".hands" / "demo") in err
    assert _tree(tmp_home) == before


@pytest.mark.parametrize("role_dir", ["hands-driver", "hands-architect"])
def test_add_refuses_a_non_empty_role_directory(
    tmp_home: Path, fake_systemctl: Path, bare_repo: Path, role_dir: str
) -> None:
    occupied = tmp_home / role_dir / "demo"
    occupied.mkdir(parents=True)
    (occupied / "notes.txt").write_text("mine\n")
    before = _tree(tmp_home)
    code, _, err = _run(["project", "add", "demo", "--repo", str(bare_repo)])
    assert code == 1 and str(occupied) in err
    assert _tree(tmp_home) == before
    assert not fake_systemctl.exists()


def test_add_accepts_an_empty_role_directory(
    tmp_home: Path, fake_systemctl: Path, bare_repo: Path
) -> None:
    (tmp_home / "hands-driver" / "demo").mkdir(parents=True)
    code, _, err = _run(["project", "add", "demo", "--repo", str(bare_repo)])
    assert code == 0, err
    assert (tmp_home / "hands-driver" / "demo" / "repo" / ".git").is_dir()


def test_add_refuses_a_bad_project_name(
    tmp_home: Path, fake_systemctl: Path, bare_repo: Path
) -> None:
    before = _tree(tmp_home)
    code, _, err = _run(["project", "add", "../x", "--repo", str(bare_repo)])
    assert code == 1 and "does not match" in strip_paths(err)
    assert _tree(tmp_home) == before


def test_generated_topics_carry_the_name_and_are_ntfy_topics() -> None:
    for name in ("demo", "my.proj", "a" * 64):
        topics = generated_topics(name)
        assert set(topics) == {"ntfy_topic", "cmd_topic", "who_topic", "who_cmd_topic"}
        assert len(set(topics.values())) == 4
        for topic in topics.values():
            assert NTFY_TOPIC_RE.fullmatch(topic), topic
            assert name.replace(".", "-")[:24] in topic


def test_the_wheel_carries_what_project_add_copies(tmp_path: Path) -> None:
    """The wheel, not the source tree: the files `project add` reads resolve
    inside the unpacked package's `hands/shipped/`."""
    uv = shutil.which("uv")
    assert uv is not None
    dist = tmp_path / "dist"
    built = subprocess.run(
        [uv, "build", "--wheel", "--offline", "--quiet", "-o", str(dist)],
        cwd=ROOT, capture_output=True, text=True, timeout=300,
        env={**os.environ},
    )
    assert built.returncode == 0, built.stderr
    (wheel,) = dist.glob("hands-*.whl")
    names = set(zipfile.ZipFile(wheel).namelist())
    for rel in (
        "templates/config.toml",
        "docs/ARCHITECT-INSTRUCTION.md",
        "driver/settings.json",
        "driver/CLAUDE.md",
        "architect/settings.json",
        "architect/CLAUDE.md",
        "systemd/handsd@.service",
        "bash_guard.py",
    ):
        assert f"hands/shipped/{rel}" in names, rel


def test_dry_run_names_the_role_variant_as_the_architects_claude_md_source(
    tmp_home: Path, fake_systemctl: Path, bare_repo: Path
) -> None:
    """§39 ruling on H-052: the role directory's CLAUDE.md is written from
    `architect/CLAUDE.md` (the role variant), never from the phone instruction."""
    code, out, err = _run(["project", "add", "demo", "--repo", str(bare_repo), "--dry-run"])
    assert code == 0, err
    root = docs_root()
    assert root is not None
    target = _paths(tmp_home, "demo")["architect_claude"]
    [line] = [ln for ln in out.splitlines() if ln.strip().startswith(f"{target} ")]
    assert line.strip() == f"{target}  (from {root / 'architect' / 'CLAUDE.md'})"
    assert "ARCHITECT-INSTRUCTION" not in strip_paths(line)


def test_the_architect_claude_md_is_the_filled_role_variant(
    tmp_home: Path, fake_systemctl: Path, bare_repo: Path
) -> None:
    """§39 ruling on H-052: byte for byte, `architect/CLAUDE.md` with the
    Parameters filled; the phone instruction is only printed, last."""
    from hands.project import DEFAULT_PARAMETERS, fill_parameters

    code, out, err = _run(["project", "add", "demo", "--repo", str(bare_repo)])
    assert code == 0, err + out
    root = docs_root()
    assert root is not None
    params = {"PROJECT": "demo", "REPO_URL": str(bare_repo), **DEFAULT_PARAMETERS}
    expected = fill_parameters((root / "architect" / "CLAUDE.md").read_text(), params)
    assert _paths(tmp_home, "demo")["architect_claude"].read_text() == expected
    assert out.index("== Project instruction") > out.index("== hands doctor ==")


# ------------------------------------------- mission 23 U8 (DESIGN §39, REVIEW-22 sf 11)


@pytest.fixture
def fake_git(tmp_path: Path, fake_systemctl: Path) -> Path:
    """A `git` ahead of the real one on PATH (fake_systemctl's fakebin) that logs its
    argv one call per line and then runs the real git, except that a `clone` whose
    argv names `hands-architect` exits 128 when `fail-architect` exists beside the
    log, and a `remote set-url` exits 2 when `fail-set-url` does. Returns the log."""
    real = shutil.which("git")
    assert real is not None
    log = tmp_path / "git.log"
    script = fake_systemctl.parent / "fakebin" / "git"
    script.write_text(
        "#!/bin/sh\n"
        f'echo "$*" >> {log}\n'
        f'if [ "$1" = clone ] && [ -e {tmp_path / "fail-architect"} ]; then\n'
        '  case "$*" in *hands-architect*) echo "fatal: refused" >&2; exit 128;; esac\n'
        "fi\n"
        f'if [ "$3" = remote ] && [ "$4" = set-url ] && [ -e {tmp_path / "fail-set-url"} ]; '
        "then\n"
        '  echo "error: could not set the url" >&2; exit 2\n'
        "fi\n"
        f'exec {real} "$@"\n'
    )
    script.chmod(0o755)
    return log


def _removed(out: str) -> list[str]:
    """The paths a failed add prints under its `removed:` line, one per line."""
    tail = out.split("removed:", 1)[1]
    return [ln.strip() for ln in tail.splitlines() if ln.startswith("  ")]


def test_a_failed_clone_leaves_nothing_and_a_rerun_creates_the_project(
    tmp_home: Path, fake_systemctl: Path, bare_repo: Path, tmp_path: Path
) -> None:
    """§39: a clone that fails removes everything the command created — config,
    secret, env file, unit, both role directories with kits/ — enables nothing,
    prints what it removed, and the same command then succeeds."""
    before = _tree(tmp_home)
    missing = tmp_path / "no-such.git"
    code, out, err = _run(["project", "add", "demo", "--repo", str(missing)])
    assert code == 1, out
    assert _tree(tmp_home) == before
    assert not fake_systemctl.exists(), "a failed clone enables no unit"
    removed = _removed(out)
    paths = _paths(tmp_home, "demo")
    for key in ("config", "secret", "env", "unit"):
        assert str(paths[key]) in removed, (key, removed)
    assert str(tmp_home / "hands-driver") in removed, removed
    assert "== hands doctor ==" not in strip_paths(out)
    assert "== Project instruction" not in strip_paths(out)

    code, out, err = _run(["project", "add", "demo", "--repo", str(bare_repo)])
    assert code == 0, err + out
    assert (paths["driver_repo"] / ".git").is_dir()
    assert (paths["architect_repo"] / ".git").is_dir()
    assert load_config("demo").roles["driver"].cwd == tmp_home / "hands-driver" / "demo"


def test_a_failed_second_clone_removes_the_first_and_both_role_directories(
    tmp_home: Path, fake_git: Path, bare_repo: Path, tmp_path: Path
) -> None:
    """The driver's clone succeeds and the architect's fails: the driver's clone,
    both role directories and the architect's kits/ go too."""
    (tmp_path / "fail-architect").touch()
    before = _tree(tmp_home)
    code, out, _ = _run(["project", "add", "demo", "--repo", str(bare_repo)])
    assert code == 1, out
    assert _tree(tmp_home) == before
    removed = _removed(out)
    assert str(tmp_home / "hands-driver") in removed, removed
    assert str(tmp_home / "hands-architect") in removed, removed
    assert not (tmp_path / "systemctl.log").exists()

    (tmp_path / "fail-architect").unlink()
    code, out, err = _run(["project", "add", "demo", "--repo", str(bare_repo)])
    assert code == 0, err + out


def test_a_failed_clone_keeps_what_was_there_before(
    tmp_home: Path, fake_systemctl: Path, tmp_path: Path
) -> None:
    """Only what the command created is removed: a unit file another project
    installed, an existing env file and an empty role directory the human made stay,
    byte for byte."""
    unit = tmp_home / ".config" / "systemd" / "user" / "handsd@.service"
    unit.parent.mkdir(parents=True)
    unit.write_text("# another project's unit\n")
    env = tmp_home / ".config" / "hands" / "demo.env"
    env.parent.mkdir(parents=True)
    env.write_text("KEY=1\n")
    (tmp_home / "hands-driver" / "demo").mkdir(parents=True)
    before = _tree(tmp_home)
    code, out, _ = _run(["project", "add", "demo", "--repo", str(tmp_path / "none.git")])
    assert code == 1, out
    assert _tree(tmp_home) == before
    assert unit.read_text() == "# another project's unit\n"
    assert env.read_text() == "KEY=1\n"
    removed = _removed(out)
    assert set(removed).isdisjoint({str(unit), str(env), str(tmp_home / "hands-driver" / "demo")})
    assert str(tmp_home / "hands-driver" / "demo" / "CLAUDE.md") in removed


def test_the_clone_puts_double_dash_before_the_url(
    tmp_home: Path, fake_git: Path, bare_repo: Path
) -> None:
    """§39 (REVIEW-22 should-fix 11): `git clone -- <url>`, so a url that begins with
    `-` is never read as an option."""
    code, out, err = _run(["project", "add", "demo", "--repo", str(bare_repo)])
    assert code == 0, err + out
    # The bare_repo fixture's own `clone --bare` may run through the fake too.
    clones = [
        ln.split() for ln in fake_git.read_text().splitlines()
        if ln.startswith("clone") and "--bare" not in ln.split()
    ]
    assert len(clones) == 2, clones
    for argv in clones:
        assert "--" in argv and argv.index("--") == argv.index(str(bare_repo)) - 1, argv


def test_the_dry_run_names_the_double_dash_before_the_url(
    tmp_home: Path, fake_systemctl: Path, bare_repo: Path
) -> None:
    """§39 (review 23 should-fix 9): the dry run says each role's clone is
    `git clone -- <url>`, as the run does."""
    code, out, err = _run(["project", "add", "demo", "--repo", str(bare_repo), "--dry-run"])
    assert code == 0, err
    said = f"(git clone -- {bare_repo}; push URL "
    assert out.count(said) == 2, out


def test_a_failed_push_url_step_is_a_failed_clone(
    tmp_home: Path, fake_git: Path, bare_repo: Path, tmp_path: Path
) -> None:
    """§39 (review 23 should-fix 9): a clone whose `remote set-url --push` fails
    counts as a failed clone — the command says the clone failed, removes what it
    created, enables no unit, and a re-run then succeeds."""
    (tmp_path / "fail-set-url").touch()
    before = _tree(tmp_home)
    code, out, _ = _run(["project", "add", "demo", "--repo", str(bare_repo)])
    assert code == 1, out
    assert f"the clone of {bare_repo} failed; removed:" in out, out
    assert _tree(tmp_home) == before
    removed = _removed(out)
    assert str(tmp_home / "hands-driver") in removed, removed
    assert not (tmp_path / "systemctl.log").exists(), "a failed clone enables no unit"
    set_urls = [ln for ln in fake_git.read_text().splitlines() if " remote set-url " in ln]
    assert len(set_urls) == 1, set_urls  # the driver's, which stopped the command

    (tmp_path / "fail-set-url").unlink()
    code, out, err = _run(["project", "add", "demo", "--repo", str(bare_repo)])
    assert code == 0, err + out
