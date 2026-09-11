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
    assert builder.resume_prompt("the limited prompt") == "Resume WORKPLAN.md"
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
    # H-008: no default. Absent, a limit resume re-sends the limited job's own prompt.
    assert builder.resume_line is None
    assert builder.resume_prompt("the limited prompt") == "the limited prompt"
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


def test_an_empty_resume_line_is_refused(write_config) -> None:
    """§19 (review should-fix 5): `resume_line = ""` is not the absent key.

    Absent means "re-send the limited job's own prompt" (H-008); an empty line
    is an operator mistake, so it is refused at load rather than folded into
    that branch. The message must name both valid choices.
    """
    write_config("[roles.builder]\ncwd = '~/git/demo'\nresume_line = ''\n")
    with pytest.raises(ConfigError) as exc:
        load_config("demo")
    message = str(exc.value)
    assert "demo.toml" in message  # the `path` context every config error carries
    assert "[roles.builder]" in message
    assert "resume_line" in message
    assert "omit" in message  # choice 1: leave the key out
    assert "non-empty" in message  # choice 2: give a real line


def test_a_whitespace_only_resume_line_is_refused(write_config) -> None:
    """A line of blanks is no more a prompt than "" is — same refusal."""
    write_config("[roles.aux]\ncwd = '~/g'\n[roles.builder]\ncwd = '~/g'\nresume_line = '   '\n")
    with pytest.raises(ConfigError) as exc:
        load_config("demo")
    assert "resume_line" in str(exc.value)
    assert "non-empty" in str(exc.value)


def test_an_empty_resume_line_on_aux_is_refused_too(write_config) -> None:
    """Aux ignores `resume_line` at resume time; the config is still wrong."""
    write_config("[roles.builder]\ncwd = '~/g'\n[roles.aux]\ncwd = '~/g'\nresume_line = ''\n")
    with pytest.raises(ConfigError) as exc:
        load_config("demo")
    assert "[roles.aux]" in str(exc.value)
    assert "resume_line" in str(exc.value)


#: Every optional string key of §13, with `{v}` where the blank value goes.
#: The table lives here rather than being derived from `config.py`, so that a key
#: added to the parser without a blank refusal shows up as a row nobody wrote —
#: review 3 should-fix 5 was exactly one dataclass that the last sweep missed.
OPTIONAL_STRING_KEYS = [
    (
        "server.socket",
        "[server]\nsocket = {v}\n[roles.builder]\ncwd = '~/g'\n",
        "[server]",
        "socket",
    ),
    (
        "server.ntfy_topic",
        "[server]\nntfy_topic = {v}\n[roles.builder]\ncwd = '~/g'\n",
        "[server]",
        "ntfy_topic",
    ),
    (
        "server.ntfy_url",
        "[server]\nntfy_url = {v}\n[roles.builder]\ncwd = '~/g'\n",
        "[server]",
        "ntfy_url",
    ),
    (
        "roles.builder.model",
        "[roles.builder]\ncwd = '~/g'\nmodel = {v}\n",
        "[roles.builder]",
        "model",
    ),
    (
        "roles.builder.resume_line",
        "[roles.builder]\ncwd = '~/g'\nresume_line = {v}\n",
        "[roles.builder]",
        "resume_line",
    ),
    ("ops.repo", "[roles.builder]\ncwd = '~/g'\n[ops]\nrepo = {v}\n", "[ops]", "repo"),
    (
        "ops.monitor_cmd",
        "[roles.builder]\ncwd = '~/g'\n[ops]\nrepo = '~/ops'\nmonitor_cmd = {v}\n",
        "[ops]",
        "monitor_cmd",
    ),
    (
        "playbook.path",
        "[roles.builder]\ncwd = '~/g'\n[playbook]\npath = {v}\n",
        "[playbook]",
        "path",
    ),
    (
        "files.allowed_roots",
        "[roles.builder]\ncwd = '~/g'\n[files]\nallowed_roots = ['~/g', {v}]\n",
        "[files]",
        "allowed_roots",
    ),
    (
        "gates.patterns",
        "[roles.builder]\ncwd = '~/g'\n[gates]\npatterns = [{v}]\n",
        "[gates]",
        "patterns",
    ),
    (
        "runner.claude",
        "[roles.builder]\ncwd = '~/g'\n[runner]\nclaude = {v}\n",
        "[runner]",
        "claude",
    ),
]


@pytest.mark.parametrize("blank", ["''", "'   '"], ids=["empty", "blanks"])
@pytest.mark.parametrize(
    "body,where,key",
    [row[1:] for row in OPTIONAL_STRING_KEYS],
    ids=[row[0] for row in OPTIONAL_STRING_KEYS],
)
def test_an_optional_string_key_refuses_a_blank_value(
    write_config, body: str, where: str, key: str, blank: str
) -> None:
    """§20 (review 3 should-fix 5): `""` is not a third state for an optional key.

    Every key here means something definite when it is left out. An empty value
    is neither that meaning nor a usable one — `Path('/ops') / ''` is the ops
    *directory*, which `hands status` would then report as the deciding monitor
    script while builder jobs go unwatched — so it is refused at load, with both
    valid choices named, the way mission 3 did it for `resume_line`.
    """
    write_config(body.format(v=blank))
    with pytest.raises(ConfigError) as exc:
        load_config("demo")
    message = str(exc.value)
    assert "demo.toml" in message  # the `path` context every config error carries
    assert where in message and key in message
    assert "omit" in message  # choice 1: leave the key out
    assert "non-empty" in message  # choice 2: give a real value


def test_an_empty_monitor_cmd_cannot_make_the_ops_repo_the_monitor(write_config) -> None:
    """Review 3 should-fix 5, stated as the behaviour it prevents.

    `OpsConfig(repo=Path('/x'), monitor_cmd="").monitor_path` was `/x` — a
    directory as the monitor script. No config can reach that state now.
    """
    write_config("[roles.builder]\ncwd = '~/g'\n[ops]\nrepo = '~/ops'\nmonitor_cmd = ''\n")
    with pytest.raises(ConfigError) as exc:
        load_config("demo")
    assert "monitor_cmd" in str(exc.value)


def test_empty_permission_flags_stay_legal(write_config) -> None:
    """The one optional string whose blank is its default: no flags at all (§13)."""
    write_config("[roles.builder]\ncwd = '~/g'\npermission_flags = ''\n")
    assert load_config("demo").role("builder").permission_flags == ""
    assert load_config("demo").role("builder").permission_argv == ()


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


def test_gates_patterns_may_be_extended_but_never_reduced(write_config) -> None:
    """§8: "gating on the default patterns cannot be disabled"."""
    write_config(
        """
[roles.builder]
cwd = "~/git/demo"
[gates]
patterns = ["Apply ~/Downloads/", "rm -rf", "rm -rf"]
"""
    )
    cfg = load_config("demo")
    # the config named one of the defaults and one addition, and tried to drop
    # the other four; the four stay, the addition is appended, once.
    assert cfg.gates.patterns == (*DEFAULT_GATE_PATTERNS, "rm -rf")


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
