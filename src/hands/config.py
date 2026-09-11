"""Project configuration — `~/.hands/<project>.toml` (DESIGN §13).

One config per project; `handsd --project <name>` names the file. Everything
optional has a default here, so no later unit has to guess one. Unknown
sections and keys are refused: a typo in the config is a silent misconfiguration
otherwise, and this file is edited by hand.
"""

from __future__ import annotations

import os
import shlex
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

__all__ = [
    "DEFAULT_GATE_PATTERNS",
    "Config",
    "ConfigError",
    "FilesConfig",
    "GatesConfig",
    "LimitsConfig",
    "MonitorConfig",
    "OpsConfig",
    "PlaybookConfig",
    "RoleConfig",
    "RunnerConfig",
    "ServerConfig",
    "config_path",
    "list_projects",
    "load_config",
    "resolve_project",
]


class ConfigError(Exception):
    """The config is missing, unparseable, or says something impossible."""


# DESIGN §4: "defaults: `Apply ~/Downloads/`, `decisions-`, `playbook-`,
# `gh pr create`, `open the PR`". Gating on these cannot be disabled (§8).
DEFAULT_GATE_PATTERNS: tuple[str, ...] = (
    "Apply ~/Downloads/",
    "decisions-",
    "playbook-",
    "gh pr create",
    "open the PR",
)

KNOWN_ROLES: tuple[str, ...] = ("builder", "aux")
DEFAULT_QUEUE_DEPTH = {"builder": 1, "aux": 4}  # §6
DEFAULT_MODEL = "opus"
DEFAULT_NTFY_URL = "https://ntfy.sh"
DEFAULT_SOCKET = "~/.hands/handsd.sock"
DEFAULT_STALL_MINUTES = 40.0  # §5
DEFAULT_BACKOFF_MINUTES = 30.0  # §6
DEFAULT_MAX_RESUMES = 3  # §10 example; the playbook may override it
DEFAULT_PLAYBOOK_PATH = "PLAYBOOK.toml"  # §10, relative to roles.builder.cwd
DEFAULT_CLAUDE = "claude"
DEFAULT_CANCEL_GRACE_S = 20.0  # §2: SIGINT, wait, SIGTERM


@dataclass(frozen=True)
class ServerConfig:
    socket: Path
    ntfy_topic: str | None
    ntfy_url: str


@dataclass(frozen=True)
class RoleConfig:
    name: str
    cwd: Path
    model: str
    permission_flags: str
    resume_line: str | None  # §6, H-008: optional, no default
    queue_depth: int
    cancel_gated: bool

    @property
    def permission_argv(self) -> tuple[str, ...]:
        """`permission_flags` as argv, for the §2 invocation."""
        return tuple(shlex.split(self.permission_flags))

    def resume_prompt(self, prompt: str) -> str:
        """§6/§10 (H-008): `resume_line` when the config sets one, else `prompt` again.

        The one place the rule lives, so the limit resume (§6) and a playbook
        `resume` action (§10) cannot drift apart. `prompt` is the prompt of the
        job being resumed: re-sending it is right for a checkpoint-driven
        kickoff line, while `Resume WORKPLAN.md` is right for a workplan one.
        """
        return prompt if self.resume_line is None else self.resume_line

    @property
    def resume_behaviour(self) -> str:
        """One line for `hands doctor`: which of the two resumes this role has."""
        if self.name != "builder":
            unused = " (resume_line is set, but only the builder uses it)"
            extra = unused if self.resume_line else ""
            return f"limit resume: re-sends the limited job's own prompt{extra}"
        if self.resume_line is None:
            return "limit resume: re-sends the limited job's own prompt (no resume_line set)"
        return f'limit resume: sends resume_line "{self.resume_line}" as a clear job'


@dataclass(frozen=True)
class OpsConfig:
    repo: Path | None
    monitor_cmd: str | None

    @property
    def monitor_path(self) -> Path | None:
        """`<ops.repo>/<monitor_cmd>` when both are set (§5)."""
        if self.repo is None or self.monitor_cmd is None:
            return None
        return self.repo / self.monitor_cmd


@dataclass(frozen=True)
class MonitorConfig:
    stall_minutes: float


@dataclass(frozen=True)
class LimitsConfig:
    backoff_minutes: float
    max_resumes: int


@dataclass(frozen=True)
class PlaybookConfig:
    path: str


@dataclass(frozen=True)
class FilesConfig:
    allowed_roots: tuple[Path, ...]


@dataclass(frozen=True)
class GatesConfig:
    patterns: tuple[str, ...]


@dataclass(frozen=True)
class RunnerConfig:
    claude: str
    cancel_grace_s: float


@dataclass(frozen=True)
class Config:
    project: str
    path: Path
    server: ServerConfig
    roles: dict[str, RoleConfig]
    ops: OpsConfig
    monitor: MonitorConfig
    limits: LimitsConfig
    playbook: PlaybookConfig
    files: FilesConfig
    gates: GatesConfig
    runner: RunnerConfig

    def role(self, name: str) -> RoleConfig:
        try:
            return self.roles[name]
        except KeyError:
            raise KeyError(f"role {name!r} is not configured in {self.path}") from None


def config_path(project: str, *, home: Path | None = None) -> Path:
    base = Path("~/.hands").expanduser() if home is None else Path(home) / ".hands"
    return base / f"{project}.toml"


def list_projects(*, home: Path | None = None) -> list[str]:
    """Every project with a config in `~/.hands/`, by name."""
    base = Path("~/.hands").expanduser() if home is None else Path(home) / ".hands"
    try:
        return sorted(path.stem for path in base.glob("*.toml"))
    except OSError:  # pragma: no cover - unreadable ~/.hands
        return []


def resolve_project(explicit: str | None = None, *, home: Path | None = None) -> str:
    """Which project a command means: the flag, then $HANDS_PROJECT, then the only one.

    `handsd --project <name>` (§13) and `hands` share this, so the daemon and the
    CLI can never disagree about which socket they mean. Guessing stops as soon
    as there is more than one candidate.
    """
    if explicit:
        return explicit
    from_env = os.environ.get("HANDS_PROJECT")
    if from_env:
        return from_env
    names = list_projects(home=home)
    if len(names) == 1:
        return names[0]
    base = Path("~/.hands").expanduser() if home is None else Path(home) / ".hands"
    if not names:
        raise ConfigError(
            f"no project config in {base}/*.toml; write one (DESIGN §13) "
            "or name one with --project"
        )
    raise ConfigError(
        f"{base} configures several projects ({', '.join(names)}); "
        "name one with --project or $HANDS_PROJECT"
    )


def load_config(project: str, *, home: Path | None = None) -> Config:
    """Load and validate `~/.hands/<project>.toml`."""
    path = config_path(project, home=home)
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ConfigError(f"cannot read config {path}: {exc}") from exc
    try:
        data = tomllib.loads(raw.decode("utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
        raise ConfigError(f"{path} is not valid TOML: {exc}") from exc
    return parse_config(data, project=project, path=path)


def parse_config(data: dict[str, Any], *, project: str, path: Path) -> Config:
    _check_keys(
        data,
        ("server", "roles", "ops", "monitor", "limits", "playbook", "files", "gates", "runner"),
        "config",
        path,
    )

    server_t = _table(data, "server", path)
    _check_keys(server_t, ("socket", "ntfy_topic", "ntfy_url"), "[server]", path)
    server = ServerConfig(
        socket=_path(server_t, "socket", DEFAULT_SOCKET, "[server]", path),
        ntfy_topic=_opt_str(server_t, "ntfy_topic", "[server]", path),
        ntfy_url=_str(server_t, "ntfy_url", DEFAULT_NTFY_URL, "[server]", path),
    )

    roles_t = _table(data, "roles", path)
    for name in roles_t:
        if name not in KNOWN_ROLES:
            raise ConfigError(
                f"{path}: unknown role [roles.{name}]; known roles are {', '.join(KNOWN_ROLES)}"
            )
    if "builder" not in roles_t:
        raise ConfigError(f"{path}: [roles.builder] is required")
    roles = {name: _role(name, roles_t[name], path) for name in KNOWN_ROLES if name in roles_t}

    ops_t = _table(data, "ops", path)
    _check_keys(ops_t, ("repo", "monitor_cmd"), "[ops]", path)
    repo = ops_t.get("repo")
    ops = OpsConfig(
        repo=None if repo is None else _abs(_path(ops_t, "repo", "", "[ops]", path), "ops.repo"),
        monitor_cmd=_opt_str(ops_t, "monitor_cmd", "[ops]", path),
    )

    monitor_t = _table(data, "monitor", path)
    _check_keys(monitor_t, ("stall_minutes",), "[monitor]", path)
    monitor = MonitorConfig(
        stall_minutes=_number(monitor_t, "stall_minutes", DEFAULT_STALL_MINUTES, "[monitor]", path)
    )

    limits_t = _table(data, "limits", path)
    _check_keys(limits_t, ("backoff_minutes", "max_resumes"), "[limits]", path)
    limits = LimitsConfig(
        backoff_minutes=_number(
            limits_t, "backoff_minutes", DEFAULT_BACKOFF_MINUTES, "[limits]", path
        ),
        max_resumes=_int(limits_t, "max_resumes", DEFAULT_MAX_RESUMES, "[limits]", path, minimum=0),
    )

    playbook_t = _table(data, "playbook", path)
    _check_keys(playbook_t, ("path",), "[playbook]", path)
    playbook_path = _str(playbook_t, "path", DEFAULT_PLAYBOOK_PATH, "[playbook]", path)
    if Path(playbook_path).is_absolute() or playbook_path.startswith("~"):
        raise ConfigError(
            f"{path}: playbook.path must be relative to roles.builder.cwd, got {playbook_path!r}"
        )
    playbook = PlaybookConfig(path=playbook_path)

    files_t = _table(data, "files", path)
    _check_keys(files_t, ("allowed_roots",), "[files]", path)
    if "allowed_roots" in files_t:
        roots = tuple(
            _abs(Path(item).expanduser(), "files.allowed_roots")
            for item in _str_list(files_t, "allowed_roots", "[files]", path)
        )
        if not roots:
            raise ConfigError(f"{path}: files.allowed_roots must not be empty")
    else:
        # Default: exactly the role working directories. Nothing else is reachable
        # by `hands put/get/ls` until the human names it.
        roots = tuple(dict.fromkeys(role.cwd for role in roles.values()))
    files = FilesConfig(allowed_roots=roots)

    gates_t = _table(data, "gates", path)
    _check_keys(gates_t, ("patterns",), "[gates]", path)
    # §8: "gating on the default patterns cannot be disabled". A project's list
    # is therefore *added* to the defaults, never substituted for them: the union
    # is taken here, defaults first, so a config can only ever widen the gate.
    extra = tuple(_str_list(gates_t, "patterns", "[gates]", path))
    gates = GatesConfig(
        patterns=DEFAULT_GATE_PATTERNS
        + tuple(p for p in dict.fromkeys(extra) if p not in DEFAULT_GATE_PATTERNS)
    )

    runner_t = _table(data, "runner", path)
    _check_keys(runner_t, ("claude", "cancel_grace_s"), "[runner]", path)
    runner = RunnerConfig(
        claude=_str(runner_t, "claude", DEFAULT_CLAUDE, "[runner]", path),
        cancel_grace_s=_number(
            runner_t, "cancel_grace_s", DEFAULT_CANCEL_GRACE_S, "[runner]", path
        ),
    )

    return Config(
        project=project,
        path=path,
        server=server,
        roles=roles,
        ops=ops,
        monitor=monitor,
        limits=limits,
        playbook=playbook,
        files=files,
        gates=gates,
        runner=runner,
    )


def _role(name: str, table: Any, path: Path) -> RoleConfig:
    where = f"[roles.{name}]"
    if not isinstance(table, dict):
        raise ConfigError(f"{path}: {where} must be a table")
    _check_keys(
        table,
        ("cwd", "model", "permission_flags", "resume_line", "queue_depth", "cancel_gated"),
        where,
        path,
    )
    if "cwd" not in table:
        raise ConfigError(f"{path}: {where} needs a cwd")
    return RoleConfig(
        name=name,
        cwd=_abs(_path(table, "cwd", "", where, path), f"roles.{name}.cwd"),
        model=_str(table, "model", DEFAULT_MODEL, where, path),
        permission_flags=_str(table, "permission_flags", "", where, path),
        # H-008: no default — absent (or empty) means "re-send the limited prompt".
        resume_line=_opt_str(table, "resume_line", where, path) or None,
        queue_depth=_int(
            table, "queue_depth", DEFAULT_QUEUE_DEPTH.get(name, 1), where, path, minimum=1
        ),
        cancel_gated=_bool(table, "cancel_gated", True, where, path),
    )


# --------------------------------------------------------------- primitives


def _check_keys(table: dict[str, Any], allowed: tuple[str, ...], where: str, path: Path) -> None:
    unknown = sorted(set(table) - set(allowed))
    if unknown:
        raise ConfigError(
            f"{path}: unknown key(s) in {where}: {', '.join(unknown)}; "
            f"known keys are {', '.join(allowed)}"
        )


def _table(data: dict[str, Any], name: str, path: Path) -> dict[str, Any]:
    value = data.get(name, {})
    if not isinstance(value, dict):
        raise ConfigError(f"{path}: [{name}] must be a table, got {type(value).__name__}")
    return value


def _str(table: dict[str, Any], key: str, default: str, where: str, path: Path) -> str:
    value = table.get(key, default)
    if not isinstance(value, str):
        raise ConfigError(f"{path}: {where} {key} must be a string, got {value!r}")
    return value


def _opt_str(table: dict[str, Any], key: str, where: str, path: Path) -> str | None:
    if key not in table:
        return None
    return _str(table, key, "", where, path)


def _bool(table: dict[str, Any], key: str, default: bool, where: str, path: Path) -> bool:
    value = table.get(key, default)
    if not isinstance(value, bool):
        raise ConfigError(f"{path}: {where} {key} must be true or false, got {value!r}")
    return value


def _int(
    table: dict[str, Any], key: str, default: int, where: str, path: Path, *, minimum: int
) -> int:
    value = table.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"{path}: {where} {key} must be an integer, got {value!r}")
    if value < minimum:
        raise ConfigError(f"{path}: {where} {key} must be >= {minimum}, got {value}")
    return value


def _number(table: dict[str, Any], key: str, default: float, where: str, path: Path) -> float:
    value = table.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"{path}: {where} {key} must be a number, got {value!r}")
    if value < 0:
        raise ConfigError(f"{path}: {where} {key} must not be negative, got {value}")
    return float(value)


def _str_list(table: dict[str, Any], key: str, where: str, path: Path) -> list[str]:
    value = table.get(key, [])
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ConfigError(f"{path}: {where} {key} must be a list of strings, got {value!r}")
    return value


def _path(table: dict[str, Any], key: str, default: str, where: str, path: Path) -> Path:
    return Path(_str(table, key, default, where, path)).expanduser()


def _abs(value: Path, what: str) -> Path:
    if not value.is_absolute():
        raise ConfigError(f"{what} must be an absolute path (or start with ~), got {str(value)!r}")
    return value
