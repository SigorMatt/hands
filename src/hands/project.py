"""`hands project add <name> --repo <url> [--dry-run]` (DESIGN §38 "Onboarding").

What docs/INTEGRATION.md's setup does by hand, for one project: the config from
the installed template with four generated topics and a command secret, the
driver and architect directories with the shipped settings, guard and
instructions and a fetch-only clone each, `handsd@<name>` enabled, doctor run,
and the filled Project instruction printed last with its verification question.

A client command: no daemon, no existing config. Every refusal is made before
anything is written; `--dry-run` prints every path and command and writes nothing.
"""

from __future__ import annotations

import os
import re
import secrets
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from hands import doctor
from hands.config import ConfigError, check_project_name, docs_root, load_config

#: The question the human asks the Project after pasting the instruction (§38).
VERIFY_QUESTION = "What are your Parameters?"
#: The push URL that makes a role's clone fetch-only (§12, §28; doctor's push rule).
NO_PUSH = "no_push"
#: Parameters filled in every instruction this command writes or prints. The design
#: names none but PROJECT and REPO_URL; the rest are hands' own conventions (the
#: templates' meta/ layout and the config's default playbook path), for the human
#: to edit where the project differs.
DEFAULT_PARAMETERS = {
    "BRANCH": "main",
    "PLAN": "meta/CHECKPOINT.md meta/plan.md",
    "QUESTIONS": "meta/findings/FINDINGS.md",
    "PLAYBOOK": "PLAYBOOK.toml",
}
#: Longest run of the project name a topic carries, so every topic fits ntfy's
#: 64-character `[-_A-Za-z0-9]` topic names.
TOPIC_NAME_MAX = 24
TOPIC_PREFIXES = {
    "ntfy_topic": "hands",
    "cmd_topic": "hands-cmd",
    "who_topic": "who",
    "who_cmd_topic": "whocmd",
}
SUBPROCESS_S = 120.0


class ProjectError(Exception):
    """A refusal: nothing was written."""


def generated_topics(name: str) -> dict[str, str]:
    """The four topics, each `<prefix>-<name>-<random>` with the name's characters
    outside ntfy's topic alphabet made `-` and the name cut to TOPIC_NAME_MAX."""
    part = re.sub(r"[^-_A-Za-z0-9]", "-", name)[:TOPIC_NAME_MAX]
    return {
        key: f"{prefix}-{part}-{secrets.token_urlsafe(12)}"
        for key, prefix in TOPIC_PREFIXES.items()
    }


def fill_parameters(text: str, values: dict[str, str]) -> str:
    """Replace the value of each `KEY = value` Parameters line named in `values`,
    keeping its indentation, alignment and any trailing `# comment`."""
    for key, value in values.items():
        pattern = re.compile(rf"^([ \t]+{key}[ \t]*=[ \t]*)(.*?)([ \t]+#.*)?$", re.M)
        text = pattern.sub(lambda m, v=value: m.group(1) + v + (m.group(3) or ""), text, 1)
    return text


def project_instruction(text: str) -> str:
    """The block of docs/ARCHITECT-INSTRUCTION.md for pasting: below its `---`."""
    parts = re.split(r"^---\s*$", text, maxsplit=1, flags=re.M)
    return parts[-1].strip("\n") + "\n"


@dataclass(frozen=True)
class Plan:
    """Every path `add` writes and every command it runs, computed before any write."""

    name: str
    repo: str
    home: Path
    shipped: Path
    guard: Path

    @property
    def hands_dir(self) -> Path:
        return self.home / ".hands"

    @property
    def config(self) -> Path:
        return self.hands_dir / f"{self.name}.toml"

    @property
    def secret(self) -> Path:
        return self.hands_dir / f"{self.name}.cmd_secret"

    @property
    def spool(self) -> Path:
        return self.hands_dir / self.name

    @property
    def env(self) -> Path:
        return self.home / ".config" / "hands" / f"{self.name}.env"

    @property
    def unit(self) -> Path:
        return self.home / ".config" / "systemd" / "user" / "handsd@.service"

    def role_dir(self, role: str) -> Path:
        return self.home / f"hands-{role}" / self.name

    def role_files(self, role: str) -> dict[Path, Path]:
        """target → shipped source, for one role directory."""
        base = self.role_dir(role)
        return {
            base / ".claude" / "settings.json": self.shipped / role / "settings.json",
            base / ".claude" / "hooks" / "bash_guard.py": self.guard,
            base / "CLAUDE.md": self.shipped / role / "CLAUDE.md",
        }

    def systemctl(self) -> list[list[str]]:
        return [
            ["systemctl", "--user", "daemon-reload"],
            ["systemctl", "--user", "enable", f"handsd@{self.name}"],
        ]


def _shipped() -> tuple[Path, Path]:
    root = docs_root()
    guard = next((p for p in doctor.SHIPPED_GUARDS if p.is_file()), None)
    if root is None or guard is None:
        raise ProjectError("this install carries no shipped docs, templates and guard (§38); "
                           "reinstall hands")
    return root, guard


def _refusals(plan: Plan) -> None:
    for path in (plan.config, plan.spool, plan.secret):
        if path.exists() or path.is_symlink():
            raise ProjectError(f"project {plan.name!r} exists: {path} is there; nothing written")
    for role in ("driver", "architect"):
        base = plan.role_dir(role)
        if base.is_symlink() or (base.exists() and not base.is_dir()):
            raise ProjectError(f"{base} is not a directory; nothing written")
        if base.is_dir() and any(base.iterdir()):
            raise ProjectError(f"{base} is not empty; nothing written")


def _write_private(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(text)
    os.chmod(path, 0o600)


def _run(argv: list[str], out: TextIO) -> bool:
    print("$ " + " ".join(argv), file=out)
    try:
        done = subprocess.run(argv, capture_output=True, text=True, timeout=SUBPROCESS_S)
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"  failed: {type(exc).__name__}: {exc}", file=out)
        return False
    if done.returncode != 0:
        print(f"  failed: exit {done.returncode}: {done.stderr.strip()}", file=out)
        return False
    return True


def add(
    name: str,
    repo: str,
    *,
    dry_run: bool,
    out: TextIO,
    err: TextIO,
    home: Path | None = None,
) -> int:
    """Exit 0 when everything was written and every command succeeded; 1 on a
    refusal (nothing written) or a failed git/systemctl step. Doctor's own exit
    status is printed and does not decide this one: the project is written by then,
    and doctor's failures (no builder clone yet, say) are the human's next steps."""
    try:
        check_project_name(name)
        if not repo.strip():
            raise ProjectError("--repo is empty")
        shipped, guard = _shipped()
        plan = Plan(name, repo, Path(home or Path("~").expanduser()), shipped, guard)
        _refusals(plan)
    except (ConfigError, ProjectError) as exc:
        print(f"hands: {exc}", file=err)
        return 1
    params = {"PROJECT": name, "REPO_URL": repo, **DEFAULT_PARAMETERS}
    instruction = fill_parameters(
        project_instruction((shipped / "docs" / "ARCHITECT-INSTRUCTION.md").read_text()), params
    )
    if dry_run:
        _dry_run(plan, out)
        return 0
    ok = _write(plan, params, out)
    for argv in plan.systemctl():
        ok = _run(argv, out) and ok
    print(f"left for you: `systemctl --user enable --now handswho@{name}` (the who view, "
          f"optional), and `systemctl --user start handsd@{name}` once ~/git/{name} is "
          "cloned", file=out)
    print("\n== hands doctor ==", file=out)
    try:
        config = load_config(name)
    except ConfigError as exc:
        print(f"the written config does not load: {exc}", file=out)
        ok = False
    else:
        found = doctor.run_checks(config, socket_path=config.server.socket)
        print(doctor.render(name, found, live=False), file=out)
        failed = any(check.status == doctor.FAIL for check in found)
        print(f"doctor {'failed a check' if failed else 'passed'}; `project add` does not "
              "take its status from doctor's (the project is written; fix what it names "
              f"and run `hands --project {name} doctor` again)", file=out)
    print("\n== Project instruction (paste into the Claude Project; fill Purpose) ==\n",
          file=out)
    print(instruction, file=out)
    print("Then ask the Project:", file=out)
    print(VERIFY_QUESTION, file=out)
    return 0 if ok else 1


def _dry_run(plan: Plan, out: TextIO) -> None:
    print(f"dry run: hands project add {plan.name} --repo {plan.repo} would write:", file=out)
    print(f"  {plan.config}  (mode 600, from {plan.shipped / 'templates' / 'config.toml'})",
          file=out)
    print(f"  {plan.secret}  (mode 600)", file=out)
    print(f"  {plan.env}", file=out)
    if not plan.unit.exists():
        print(f"  {plan.unit}  (from {plan.shipped / 'systemd' / 'handsd@.service'})",
              file=out)
    for role in ("driver", "architect"):
        for target, source in plan.role_files(role).items():
            print(f"  {target}  (from {source})", file=out)
        print(f"  {plan.role_dir(role) / 'repo'}  (git clone {plan.repo}; push URL "
              f"{NO_PUSH})", file=out)
    print(f"  {plan.role_dir('architect') / 'kits'}", file=out)
    print("and run:", file=out)
    for argv in plan.systemctl():
        print("  " + " ".join(argv), file=out)
    print(f"  hands --project {plan.name} doctor", file=out)
    print("nothing written", file=out)


def _write(plan: Plan, params: dict[str, str], out: TextIO) -> bool:
    topics = generated_topics(plan.name)
    secret = secrets.token_urlsafe(32)
    text = (plan.shipped / "templates" / "config.toml").read_text()
    for key, value in {**topics, "cmd_secret": secret, "project": plan.name}.items():
        text = text.replace(f"<{key}>", value)
    _write_private(plan.secret, secret + "\n")
    _write_private(plan.config, text)
    print(f"wrote {plan.config} (mode 600) and {plan.secret} (mode 600)", file=out)
    plan.env.parent.mkdir(parents=True, exist_ok=True)
    plan.env.touch(exist_ok=True)
    if not plan.unit.exists():
        plan.unit.parent.mkdir(parents=True, exist_ok=True)
        plan.unit.write_bytes((plan.shipped / "systemd" / "handsd@.service").read_bytes())
        plan.unit.chmod(0o644)
        print(f"wrote {plan.unit}", file=out)
    ok = True
    for role in ("driver", "architect"):
        base = plan.role_dir(role)
        for target, source in plan.role_files(role).items():
            target.parent.mkdir(parents=True, exist_ok=True)
            data = source.read_text()
            if target.name == "CLAUDE.md":
                data = fill_parameters(data, params)
            target.write_text(data)
        if role == "architect":
            (base / "kits").mkdir(exist_ok=True)
        print(f"wrote {base} (settings, guard, CLAUDE.md)", file=out)
        clone = base / "repo"
        ok = (
            _run(["git", "clone", "-q", plan.repo, str(clone)], out)
            and _run(["git", "-C", str(clone), "remote", "set-url", "--push", "origin", NO_PUSH],
                     out)
            and ok
        )
    return ok
