"""U1: the project config of DESIGN §13 — shape, expansion, validation, defaults."""

from pathlib import Path

import pytest

from hands.config import (
    DEFAULT_GATE_PATTERNS,
    ConfigError,
    config_path,
    load_config,
)

# The §13 example, verbatim apart from the project name.
FULL = """
[server]
socket = "~/.hands/handsd.sock"
ntfy_topic = "hands-abc123"
ntfy_url = "https://ntfy.sh"

[roles.builder]
cwd = "~/git/spanweave"
model = "opus"
permission_flags = "--dangerously-skip-permissions"
resume_line = "Resume WORKPLAN.md"
queue_depth = 1
cancel_gated = true

[roles.aux]
cwd = "~/git/spanweave"
model = "opus"
permission_flags = "--dangerously-skip-permissions"
queue_depth = 4

[ops]
repo = "~/spanweave-ops"
monitor_cmd = "watch_monitor.sh"

[monitor]
stall_minutes = 40

[limits]
backoff_minutes = 30

[playbook]
path = "PLAYBOOK.toml"

[files]
allowed_roots = ["~/git/spanweave", "~/Downloads", "~/spanweave-ops"]

[gates]
patterns = ["Apply ~/Downloads/", "decisions-", "playbook-", "gh pr create", "open the PR"]
"""


def test_config_path_is_under_the_hands_dir(tmp_home: Path) -> None:
    assert config_path("spanweave") == tmp_home / ".hands" / "spanweave.toml"


def test_missing_config_is_an_error(tmp_home: Path) -> None:
    with pytest.raises(ConfigError) as exc:
        load_config("nope")
    assert "nope.toml" in str(exc.value)


def test_unparseable_toml_is_an_error(write_config) -> None:
    write_config("[roles.builder\n")
    with pytest.raises(ConfigError):
        load_config("demo")


def test_full_config_loads_every_field(write_config, tmp_home: Path) -> None:
    write_config(FULL, project="spanweave")
    cfg = load_config("spanweave")

    assert cfg.project == "spanweave"
    assert cfg.path == tmp_home / ".hands" / "spanweave.toml"

    assert cfg.server.socket == tmp_home / ".hands" / "handsd.sock"
    assert cfg.server.ntfy_topic == "hands-abc123"
    assert cfg.server.ntfy_url == "https://ntfy.sh"

    builder = cfg.role("builder")
    assert builder.name == "builder"
    assert builder.cwd == tmp_home / "git" / "spanweave"
    assert builder.model == "opus"
    assert builder.permission_flags == "--dangerously-skip-permissions"
    assert builder.permission_argv == ("--dangerously-skip-permissions",)
    assert builder.resume_line == "Resume WORKPLAN.md"
    assert builder.queue_depth == 1
    assert builder.cancel_gated is True

    aux = cfg.role("aux")
    assert aux.queue_depth == 4
    assert aux.cwd == tmp_home / "git" / "spanweave"

    assert cfg.ops.repo == tmp_home / "spanweave-ops"
    assert cfg.ops.monitor_cmd == "watch_monitor.sh"
    assert cfg.monitor.stall_minutes == 40
    assert cfg.limits.backoff_minutes == 30
    assert cfg.playbook.path == "PLAYBOOK.toml"
    assert cfg.files.allowed_roots == (
        tmp_home / "git" / "spanweave",
        tmp_home / "Downloads",
        tmp_home / "spanweave-ops",
    )
    assert cfg.gates.patterns == DEFAULT_GATE_PATTERNS


def test_every_optional_key_has_a_default(write_config, tmp_home: Path) -> None:
    write_config()  # only [roles.builder] cwd
    cfg = load_config("demo")

    assert cfg.server.socket == tmp_home / ".hands" / "handsd.sock"
    assert cfg.server.ntfy_topic is None
    assert cfg.server.ntfy_url == "https://ntfy.sh"

    builder = cfg.role("builder")
    assert builder.model == "opus"
    assert builder.permission_flags == ""
    assert builder.permission_argv == ()
    assert builder.resume_line == "Resume WORKPLAN.md"
    assert builder.queue_depth == 1
    assert builder.cancel_gated is True

    assert cfg.ops.repo is None
    assert cfg.ops.monitor_cmd is None
    assert cfg.monitor.stall_minutes == 40
    assert cfg.limits.backoff_minutes == 30
    assert cfg.limits.max_resumes == 3
    assert cfg.playbook.path == "PLAYBOOK.toml"
    assert cfg.gates.patterns == DEFAULT_GATE_PATTERNS
    assert cfg.runner.claude == "claude"
    assert cfg.runner.cancel_grace_s == 20


def test_aux_queue_depth_defaults_to_four(write_config) -> None:
    write_config(
        """
[roles.builder]
cwd = "~/git/demo"
[roles.aux]
cwd = "~/git/demo"
"""
    )
    cfg = load_config("demo")
    assert cfg.role("builder").queue_depth == 1
    assert cfg.role("aux").queue_depth == 4


def test_allowed_roots_default_to_the_role_cwds(write_config, tmp_home: Path) -> None:
    write_config(
        """
[roles.builder]
cwd = "~/git/demo"
[roles.aux]
cwd = "~/git/other"
"""
    )
    cfg = load_config("demo")
    assert cfg.files.allowed_roots == (tmp_home / "git" / "demo", tmp_home / "git" / "other")


def test_tilde_is_expanded_everywhere(write_config, tmp_home: Path) -> None:
    write_config(
        """
[server]
socket = "~/sockets/handsd.sock"
[roles.builder]
cwd = "~/git/demo"
[ops]
repo = "~/ops"
[files]
allowed_roots = ["~/git/demo", "~/Downloads"]
"""
    )
    cfg = load_config("demo")
    assert cfg.server.socket == tmp_home / "sockets" / "handsd.sock"
    assert cfg.role("builder").cwd == tmp_home / "git" / "demo"
    assert cfg.ops.repo == tmp_home / "ops"
    assert cfg.files.allowed_roots == (tmp_home / "git" / "demo", tmp_home / "Downloads")


def test_roles_table_is_required(write_config) -> None:
    write_config("[server]\nntfy_topic = 'x'\n")
    with pytest.raises(ConfigError) as exc:
        load_config("demo")
    assert "roles.builder" in str(exc.value)


def test_unknown_role_is_refused(write_config) -> None:
    write_config(
        """
[roles.builder]
cwd = "~/git/demo"
[roles.helper]
cwd = "~/git/demo"
"""
    )
    with pytest.raises(ConfigError) as exc:
        load_config("demo")
    assert "helper" in str(exc.value)


def test_role_without_cwd_is_refused(write_config) -> None:
    write_config("[roles.builder]\nmodel = 'opus'\n")
    with pytest.raises(ConfigError) as exc:
        load_config("demo")
    assert "cwd" in str(exc.value)


def test_relative_role_cwd_is_refused(write_config) -> None:
    write_config("[roles.builder]\ncwd = 'git/demo'\n")
    with pytest.raises(ConfigError) as exc:
        load_config("demo")
    assert "absolute" in str(exc.value)


def test_relative_allowed_root_is_refused(write_config) -> None:
    write_config(
        """
[roles.builder]
cwd = "~/git/demo"
[files]
allowed_roots = ["git/demo"]
"""
    )
    with pytest.raises(ConfigError) as exc:
        load_config("demo")
    assert "absolute" in str(exc.value)


def test_empty_allowed_roots_is_refused(write_config) -> None:
    write_config(
        """
[roles.builder]
cwd = "~/git/demo"
[files]
allowed_roots = []
"""
    )
    with pytest.raises(ConfigError):
        load_config("demo")


def test_unknown_section_is_refused(write_config) -> None:
    write_config("[roles.builder]\ncwd = '~/git/demo'\n[nonsense]\nx = 1\n")
    with pytest.raises(ConfigError) as exc:
        load_config("demo")
    assert "nonsense" in str(exc.value)


def test_unknown_key_in_a_known_section_is_refused(write_config) -> None:
    write_config("[roles.builder]\ncwd = '~/git/demo'\n[monitor]\nstall_secconds = 4\n")
    with pytest.raises(ConfigError) as exc:
        load_config("demo")
    assert "stall_secconds" in str(exc.value)


def test_unknown_key_in_a_role_is_refused(write_config) -> None:
    write_config("[roles.builder]\ncwd = '~/git/demo'\nmodl = 'opus'\n")
    with pytest.raises(ConfigError) as exc:
        load_config("demo")
    assert "modl" in str(exc.value)


@pytest.mark.parametrize(
    "body",
    [
        "[roles.builder]\ncwd = '~/g'\nqueue_depth = 'one'\n",
        "[roles.builder]\ncwd = '~/g'\nqueue_depth = 0\n",
        "[roles.builder]\ncwd = '~/g'\ncancel_gated = 'yes'\n",
        "[roles.builder]\ncwd = 42\n",
        "[roles.builder]\ncwd = '~/g'\n[monitor]\nstall_minutes = 'soon'\n",
        "[roles.builder]\ncwd = '~/g'\n[monitor]\nstall_minutes = -1\n",
        "[roles.builder]\ncwd = '~/g'\n[limits]\nmax_resumes = -1\n",
        "[roles.builder]\ncwd = '~/g'\n[gates]\npatterns = 'decisions-'\n",
        "[roles.builder]\ncwd = '~/g'\n[gates]\npatterns = [1, 2]\n",
        "[roles.builder]\ncwd = '~/g'\n[files]\nallowed_roots = '~/g'\n",
        "[roles.builder]\ncwd = '~/g'\n[playbook]\npath = '/abs/PLAYBOOK.toml'\n",
        "[roles.builder]\ncwd = '~/g'\n[runner]\ncancel_grace_s = -3\n",
        "roles = 1\n",
    ],
)
def test_bad_values_are_refused(write_config, body: str) -> None:
    write_config(body)
    with pytest.raises(ConfigError):
        load_config("demo")


def test_gates_patterns_may_be_extended(write_config) -> None:
    write_config(
        """
[roles.builder]
cwd = "~/git/demo"
[gates]
patterns = ["Apply ~/Downloads/", "rm -rf"]
"""
    )
    cfg = load_config("demo")
    assert cfg.gates.patterns == ("Apply ~/Downloads/", "rm -rf")


def test_runner_keys_are_configurable(write_config) -> None:
    write_config(
        """
[roles.builder]
cwd = "~/git/demo"
[runner]
claude = "/usr/local/bin/claude"
cancel_grace_s = 5
"""
    )
    cfg = load_config("demo")
    assert cfg.runner.claude == "/usr/local/bin/claude"
    assert cfg.runner.cancel_grace_s == 5


def test_unknown_role_lookup_raises(write_config) -> None:
    write_config()
    cfg = load_config("demo")
    with pytest.raises(KeyError):
        cfg.role("aux")
