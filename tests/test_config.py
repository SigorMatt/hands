"""U1: the project config of DESIGN §13 — shape, expansion, validation, defaults."""

import ast
import dataclasses
from pathlib import Path
from typing import Any, NamedTuple

import pytest

import hands.config
from conftest import strip_paths
from hands.config import (
    DEFAULT_GATE_PATTERNS,
    ConfigError,
    OpsConfig,
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
    assert "nope.toml" in strip_paths(str(exc.value))


def test_unparseable_toml_is_an_error(write_config) -> None:
    write_config("[roles.builder\n")
    with pytest.raises(ConfigError):
        load_config("demo")


def test_full_config_loads_every_field(write_config, tmp_home: Path) -> None:
    # §21: `ops.monitor_cmd` must name an executable script under `ops.repo`.
    script = tmp_home / "spanweave-ops" / "watch_monitor.sh"
    script.parent.mkdir()
    script.write_text("#!/bin/sh\nexit 0\n")
    script.chmod(0o755)
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
    assert "roles.builder" in strip_paths(str(exc.value))


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
    assert "helper" in strip_paths(str(exc.value))


def test_role_without_cwd_is_refused(write_config) -> None:
    write_config("[roles.builder]\nmodel = 'opus'\n")
    with pytest.raises(ConfigError) as exc:
        load_config("demo")
    assert "cwd" in strip_paths(str(exc.value))


def test_relative_role_cwd_is_refused(write_config) -> None:
    write_config("[roles.builder]\ncwd = 'git/demo'\n")
    with pytest.raises(ConfigError) as exc:
        load_config("demo")
    assert "absolute" in strip_paths(str(exc.value))


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
    assert "absolute" in strip_paths(str(exc.value))


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
    assert "demo.toml" in strip_paths(message)  # the `path` context every config error carries
    assert "[roles.builder]" in strip_paths(message)
    assert "resume_line" in strip_paths(message)
    assert "omit" in strip_paths(message)  # choice 1: leave the key out
    assert "non-empty" in strip_paths(message)  # choice 2: give a real line


def test_a_whitespace_only_resume_line_is_refused(write_config) -> None:
    """A line of blanks is no more a prompt than "" is — same refusal."""
    write_config("[roles.aux]\ncwd = '~/g'\n[roles.builder]\ncwd = '~/g'\nresume_line = '   '\n")
    with pytest.raises(ConfigError) as exc:
        load_config("demo")
    assert "resume_line" in strip_paths(str(exc.value))
    assert "non-empty" in strip_paths(str(exc.value))


def test_an_empty_resume_line_on_aux_is_refused_too(write_config) -> None:
    """Aux ignores `resume_line` at resume time; the config is still wrong."""
    write_config("[roles.builder]\ncwd = '~/g'\n[roles.aux]\ncwd = '~/g'\nresume_line = ''\n")
    with pytest.raises(ConfigError) as exc:
        load_config("demo")
    assert "[roles.aux]" in strip_paths(str(exc.value))
    assert "resume_line" in strip_paths(str(exc.value))


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
    assert "demo.toml" in strip_paths(message)  # the `path` context every config error carries
    assert where in strip_paths(message) and key in strip_paths(message)
    assert "omit" in strip_paths(message)  # choice 1: leave the key out
    assert "non-empty" in strip_paths(message)  # choice 2: give a real value


def test_an_empty_monitor_cmd_cannot_make_the_ops_repo_the_monitor(write_config) -> None:
    """Review 3 should-fix 5, stated as the behaviour it prevents.

    `OpsConfig(repo=Path('/x'), monitor_cmd="").monitor_path` was `/x` — a
    directory as the monitor script. The blank is refused at load; the other
    ways to write the same state are refused below (review 4 blocker 2).
    """
    write_config("[roles.builder]\ncwd = '~/g'\n[ops]\nrepo = '~/ops'\nmonitor_cmd = ''\n")
    with pytest.raises(ConfigError) as exc:
        load_config("demo")
    assert "monitor_cmd" in strip_paths(str(exc.value))


@pytest.fixture
def ops_repo(tmp_home: Path) -> Path:
    """An ops repo (§13 `[ops] repo`) holding one of each thing a name can hit.

    Including the two that are inside it only by spelling: `link.sh` is a
    symlink to a script the ops repo does not hold, and `linkdir` is a symlink
    to the directory that holds it (review 5 should-fix 4).
    """
    repo = tmp_home / "ops"
    (repo / "sub").mkdir(parents=True)
    for name in ("watch_monitor.sh", "sub/nested.sh", "plain.sh"):
        script = repo / name
        script.write_text("#!/bin/sh\nexit 0\n")
        script.chmod(0o644 if name == "plain.sh" else 0o755)
    outside = tmp_home / "outside"
    outside.mkdir()
    evil = outside / "evil.sh"
    evil.write_text("#!/bin/sh\nexit 0\n")
    evil.chmod(0o755)
    (repo / "link.sh").symlink_to(evil)
    (repo / "linkdir").symlink_to(outside)
    return repo


def ops_config(monitor_cmd: str) -> str:
    return f"[roles.builder]\ncwd = '~/g'\n[ops]\nrepo = '~/ops'\nmonitor_cmd = '{monitor_cmd}'\n"


@pytest.mark.parametrize(
    "monitor_cmd,expected,advice",
    [
        (".", "the ops repo directory", "watch_monitor.sh"),
        ("./", "the ops repo directory", "watch_monitor.sh"),
        ("..", "'..'", "watch_monitor.sh"),
        ("../watch_monitor.sh", "'..'", "inside ops.repo"),
        ("/usr/bin/watch_monitor.sh", "relative", "inside ops.repo"),
        ("sub", "regular file", "watch_monitor.sh"),
        ("plain.sh", "not executable", "chmod +x"),
        ("not_there.sh", "does not exist", "watch_monitor.sh"),
    ],
    ids=[
        "dot",
        "dot_slash",
        "dotdot",
        "parent",
        "absolute",
        "directory",
        "not_executable",
        "missing",
    ],
)
def test_a_monitor_cmd_that_is_not_a_script_in_the_ops_repo_is_refused_at_load(
    write_config, ops_repo: Path, monitor_cmd: str, expected: str, advice: str
) -> None:
    """§21 (review 4 blocker 2): the shape of `ops.monitor_cmd`, checked at load.

    `monitor_cmd = "."` loaded clean and made `monitor_path` the ops *directory*:
    `hands status` then reports a directory as the deciding script while builder
    jobs go unwatched behind monitor.py's "is not a file" (§5). Every way of
    writing something that is not an executable regular file under `ops.repo` is
    refused here, where the human can act on it.
    """
    write_config(ops_config(monitor_cmd))
    with pytest.raises(ConfigError) as exc:
        load_config("demo")
    message = str(exc.value)
    assert "demo.toml" in strip_paths(message)  # the `path` context every config error carries
    assert "[ops]" in strip_paths(message) and "monitor_cmd" in strip_paths(message)
    assert expected in strip_paths(message)  # what is wrong with the value
    assert advice in strip_paths(message)  # what to do about it


@pytest.mark.parametrize("monitor_cmd", ["watch_monitor.sh", "sub/nested.sh"])
def test_a_monitor_cmd_naming_an_executable_script_under_the_ops_repo_loads(
    write_config, ops_repo: Path, monitor_cmd: str
) -> None:
    """The other half of §21: a real script, at the top of the repo or under it."""
    write_config(ops_config(monitor_cmd))
    cfg = load_config("demo")
    assert cfg.ops.monitor_cmd == monitor_cmd
    assert cfg.ops.monitor_path == ops_repo / monitor_cmd


@pytest.mark.parametrize(
    "monitor_cmd",
    ["link.sh", "linkdir/evil.sh"],
    ids=["a_symlink_out_of_the_repo", "a_traversal_through_a_symlinked_directory"],
)
def test_a_monitor_cmd_that_resolves_outside_the_ops_repo_is_refused_at_load(
    write_config, ops_repo: Path, monitor_cmd: str
) -> None:
    """§21 (review 5 should-fix 4): "under ops.repo" is a fact about the path
    the kernel reaches, not about the way it is spelled.

    The `..`-and-absolute check is lexical, so a symlink inside `ops.repo` that
    points out of it, and a traversal through a symlinked directory, both loaded
    clean and left `monitor_path` naming a script the ops repo does not hold —
    the thing review 4 blocker 2 refused, spelled differently. Containment is
    checked after resolution now, and the refusal names both the name and where
    it lands.
    """
    write_config(ops_config(monitor_cmd))
    with pytest.raises(ConfigError) as exc:
        load_config("demo")
    message = str(exc.value)
    assert "demo.toml" in strip_paths(message)  # the `path` context every error carries
    assert "[ops]" in strip_paths(message) and "monitor_cmd" in strip_paths(message)
    assert "outside ops.repo" in strip_paths(message)  # what is wrong with the value
    assert "evil.sh" in strip_paths(message)  # where it lands, which the name does not say
    assert "inside ops.repo" in strip_paths(message)  # what to do about it


def test_a_monitor_cmd_inside_the_ops_repo_may_still_be_a_symlink(
    write_config, ops_repo: Path
) -> None:
    """The refusal is about where the script *is*, not about symlinks: one that
    resolves back inside `ops.repo` is the repo's own script under another
    name, and stays legal."""
    (ops_repo / "alias.sh").symlink_to(ops_repo / "watch_monitor.sh")
    write_config(ops_config("alias.sh"))
    assert load_config("demo").ops.monitor_path == ops_repo / "alias.sh"


def test_the_ops_repo_directory_can_never_be_the_monitor_script() -> None:
    """Review 4 blocker 2, as the state it makes unreachable rather than as a load.

    `OpsConfig(repo=Path('/x/ops'), monitor_cmd='.').monitor_path` was `/x/ops`,
    the ops directory itself; `'..'` and an absolute path named something else
    again. The shape is refused in `OpsConfig`, so `monitor_path` returns a path
    under `ops.repo` or nothing — for the loader and for any other caller.
    """
    for cmd in (".", "./", "..", "../watch_monitor.sh", "/usr/bin/watch_monitor.sh"):
        with pytest.raises(ConfigError) as exc:
            OpsConfig(repo=Path("/x/ops"), monitor_cmd=cmd)
        assert "monitor_cmd" in strip_paths(str(exc.value))
    ops = OpsConfig(repo=Path("/x/ops"), monitor_cmd="watch_monitor.sh")
    assert ops.monitor_path == Path("/x/ops/watch_monitor.sh")


def test_empty_permission_flags_stay_legal(write_config) -> None:
    """The one optional string whose blank is its default: no flags at all (§13)."""
    write_config("[roles.builder]\ncwd = '~/g'\npermission_flags = ''\n")
    assert load_config("demo").role("builder").permission_flags == ""
    assert load_config("demo").role("builder").permission_argv == ()


def test_unknown_section_is_refused(write_config) -> None:
    write_config("[roles.builder]\ncwd = '~/git/demo'\n[nonsense]\nx = 1\n")
    with pytest.raises(ConfigError) as exc:
        load_config("demo")
    assert "nonsense" in strip_paths(str(exc.value))


def test_unknown_key_in_a_known_section_is_refused(write_config) -> None:
    write_config("[roles.builder]\ncwd = '~/git/demo'\n[monitor]\nstall_secconds = 4\n")
    with pytest.raises(ConfigError) as exc:
        load_config("demo")
    assert "stall_secconds" in strip_paths(str(exc.value))


def test_unknown_key_in_a_role_is_refused(write_config) -> None:
    write_config("[roles.builder]\ncwd = '~/git/demo'\nmodl = 'opus'\n")
    with pytest.raises(ConfigError) as exc:
        load_config("demo")
    assert "modl" in strip_paths(str(exc.value))


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


# ------------------- the loader's helpers are the mechanism (§21, review 4 should-fix 8)


def test_monitor_cmd_without_an_ops_repo_is_refused(write_config, ops_repo: Path) -> None:
    """§5/§13: `[ops]` is both keys or neither — the half-set pair is a mistake.

    `monitor_cmd` with no `repo` loaded clean and was then silently ignored:
    `monitor_path` is None, so `hands status` says the built-in detector is
    deciding while the config names a script it will never run. The refusal names
    the two ways out, like every other §13 refusal.
    """
    write_config("[roles.builder]\ncwd = '~/g'\n[ops]\nmonitor_cmd = 'watch_monitor.sh'\n")
    with pytest.raises(ConfigError) as exc:
        load_config("demo")
    message = str(exc.value)
    assert "demo.toml" in strip_paths(message)  # the `path` context every config error carries
    assert "[ops]" in strip_paths(message) and "monitor_cmd" in strip_paths(message)
    assert "repo" in strip_paths(message)  # what to add
    assert "omit" in strip_paths(message)  # or what to drop


def test_a_monitor_cmd_with_no_repo_is_unreachable_as_a_value_too() -> None:
    """The invariant lives on `OpsConfig`, as blocker 2's shape check does.

    `monitor_path`'s callers read it without re-checking, so the state where a
    script is configured and cannot be run is refused where it would be created.
    """
    with pytest.raises(ConfigError) as exc:
        OpsConfig(repo=None, monitor_cmd="watch_monitor.sh")
    assert "monitor_cmd" in strip_paths(str(exc.value))
    assert OpsConfig(repo=None, monitor_cmd=None).monitor_path is None


#: Every string key of §13 at once, each value padded with blanks. Loading this
#: is the test: `Path('  ~/g  ').expanduser()` does not expand, `'  P.toml  '`
#: names a file nobody wrote, and `[' x ']` gates on a pattern with a space in it.
PADDED = """
[server]
socket = "  ~/.hands/handsd.sock  "
ntfy_topic = "  hands-abc123  "
ntfy_url = "  https://ntfy.sh  "

[roles.builder]
cwd = "  ~/g  "
model = "  opus  "
permission_flags = "  --dangerously-skip-permissions  "
resume_line = "  Resume WORKPLAN.md  "

[roles.aux]
cwd = "  ~/g  "
model = "  sonnet  "

[ops]
repo = "  ~/ops  "
monitor_cmd = "  watch_monitor.sh  "

[playbook]
path = "  P.toml  "

[files]
allowed_roots = ["  ~/g  ", "  ~/ops  "]

[gates]
patterns = ["  gh pr create  ", "  decisions-  "]

[runner]
claude = "  /usr/local/bin/claude  "
"""


def padded_values(value: Any, where: str = "config") -> list[str]:
    """Every string in a loaded `Config` that kept a blank at either end."""
    if isinstance(value, str):
        return [] if value == value.strip() else [f"{where} = {value!r}"]
    if isinstance(value, Path):
        kept = [part for part in value.parts if part != part.strip()]
        return [f"{where} = {str(value)!r}"] if kept else []
    if isinstance(value, (list, tuple)):
        return [
            bad for i, item in enumerate(value) for bad in padded_values(item, f"{where}[{i}]")
        ]
    if isinstance(value, dict):
        return [bad for k, v in value.items() for bad in padded_values(v, f"{where}[{k!r}]")]
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return [
            bad
            for field in dataclasses.fields(value)
            for bad in padded_values(getattr(value, field.name), f"{where}.{field.name}")
        ]
    return []


def test_every_accepted_string_value_is_stored_stripped(write_config, ops_repo: Path) -> None:
    """§21 (review 4 should-fix 8): a padded value is the value, not a new key.

    The blank check of §20 used `strip()` and then stored the raw string, so
    `playbook.path = " P.toml "` and `gates.patterns = [" x "]` kept their
    padding: a path nothing on disk matches and a gate pattern that never fires.
    Stripping is in the loader's string helpers, so every key has it and the walk
    below covers the ones a future unit adds.
    """
    write_config(PADDED)
    cfg = load_config("demo")
    assert padded_values(cfg) == []
    # …and the stripped values are the ones the rest of hands then uses.
    assert cfg.role("builder").resume_line == "Resume WORKPLAN.md"
    assert cfg.playbook.path == "P.toml"
    assert cfg.ops.monitor_path == ops_repo / "watch_monitor.sh"
    assert cfg.role("builder").cwd.is_absolute()
    assert cfg.gates.patterns.count("gh pr create") == 1  # a default, not a second copy
    assert cfg.gates.patterns.count("decisions-") == 1


#: How each loader helper is called: the position of the `where` argument, so a
#: call can be tied to the section whose keys it reads.
HELPER_WHERE = {
    "_str": 3,
    "_opt_str": 2,
    "_path": 3,
    "_str_list": 2,
    "_int": 3,
    "_number": 3,
    "_bool": 3,
}
STRING_HELPERS = ("_str", "_opt_str", "_path", "_str_list")
#: `_role` and `_resume_line` take `where` as a parameter (`[roles.builder]` or
#: `[roles.aux]`, decided at run time), so every such call shares one scope here.
ROLE_SCOPE = "[roles.<name>]"


#: `config.py` as text, so a test can scan a *mutated* copy of it and show what
#: the scan below would say about a loader that does not exist yet.
SOURCE = Path(hands.config.__file__).read_text()


def section_scope(section: str) -> str:
    """The `where` a section's own `_check_keys` call passes (§13's headings)."""
    return ROLE_SCOPE if section == "roles" else f"[{section}]"


class Scan(NamedTuple):
    """What `config.py` says about itself: sections, keys, and how they are read."""

    admitted: set[tuple[str, str]]
    read: set[tuple[str, str]]
    strings: set[tuple[str, str]]
    sections: set[str]
    checked: set[str]

    @property
    def unchecked_sections(self) -> set[str]:
        """Sections the config admits whose own keys nothing checks (§21).

        A section that never calls `_check_keys` admits every key anyone writes
        under it, and none of its keys reach `admitted`, so the "read through a
        helper" walk has nothing to say about them either.
        """
        return {name for name in self.sections if section_scope(name) not in self.checked}


def config_keys(source: str | None = None) -> Scan:
    """Read `config.py`: the sections and keys it admits, and how it reads them."""
    tree = ast.parse(SOURCE if source is None else source)
    admitted: set[tuple[str, str]] = set()
    read: set[tuple[str, str]] = set()
    strings: set[tuple[str, str]] = set()
    sections: set[str] = set()
    checked: set[str] = set()
    for func in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]:
        for node in ast.walk(func):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                continue
            name = node.func.id
            if name == "_check_keys":
                where = node.args[2]
                scope = where.value if isinstance(where, ast.Constant) else ROLE_SCOPE
                if scope == "config":
                    # The section names, not keys — and the list of sections the
                    # rest of this scan has to account for (review 5 should-fix 5).
                    sections |= {item.value for item in node.args[1].elts}
                    continue
                checked.add(scope)
                admitted |= {(scope, item.value) for item in node.args[1].elts}
            elif name in HELPER_WHERE:
                key = node.args[1]
                if not isinstance(key, ast.Constant):
                    continue  # a helper delegating to another with its own argument
                where = node.args[HELPER_WHERE[name]]
                scope = where.value if isinstance(where, ast.Constant) else ROLE_SCOPE
                read.add((scope, key.value))
                if name in STRING_HELPERS:
                    strings.add((scope, key.value))
    return Scan(admitted, read, strings, sections, checked)


def test_every_key_the_config_admits_is_read_through_a_loader_helper() -> None:
    """§21 (review 4 should-fix 8): the mechanism, asserted instead of assumed.

    `blank=` is a required keyword of the string helpers and stripping is inside
    them, so no key that goes through them can skip either — but a key added with
    a raw `table.get(...)` skips the helpers themselves, which is how
    `monitor_cmd` skipped mission 3's check. `_check_keys` is the list of keys the
    config admits at all; every one of them must be read by a helper, and nothing
    else may be read, so the two lists cannot drift apart unnoticed.
    """
    scan = config_keys()
    assert scan.admitted, "the parse found no keys at all — the scan is broken, not the loader"
    assert scan.read - scan.admitted == set(), "a key is read that no section admits"
    assert scan.admitted - scan.read == set(), "a key is admitted that no helper reads"
    # …and every section the config admits checks its own keys, so the two lists
    # above cover the whole of §13 rather than the part of it that opted in.
    assert scan.sections, "the parse found no sections — the scan is broken, not the loader"
    assert scan.unchecked_sections == set(), "a section is admitted whose keys nothing checks"
    # …and the scan tells the string keys from the rest, which is what the two
    # tests around this one lean on.
    assert ("[ops]", "monitor_cmd") in scan.strings
    assert (ROLE_SCOPE, "queue_depth") in scan.read.difference(scan.strings)


def test_the_padded_config_names_every_string_key_the_loader_reads() -> None:
    """The walk above only proves what the config it loads actually sets.

    So the string keys are read out of `config.py` itself: a new one that this
    file does not exercise fails here rather than passing silently.
    """
    strings = config_keys().strings
    missing = sorted(key for _scope, key in strings if f"{key} = " not in PADDED)
    assert missing == []


def test_a_new_section_that_checks_no_keys_is_caught_by_the_scan() -> None:
    """§21 (review 5 should-fix 5): the scan binds every section, not only the
    sections that already call `_check_keys`.

    The reviewer added a whole `[extra]` section to the top-level list and read
    it with a raw `extra_t.get(...)`: this file stayed green, because the scan
    skipped the one call that says which sections exist, so `[extra]` admitted
    every key anyone wrote under it and its raw read was invisible to the walk
    above. The demonstration is a mutated copy of `config.py` — the real one is
    what the test above asserts on."""
    mutated = SOURCE.replace('"gates", "runner"),', '"gates", "runner", "extra"),', 1)
    assert mutated != SOURCE, "config.py no longer spells its section list as the scan expects"

    scan = config_keys(mutated)
    assert "extra" in scan.sections, "the scan did not see the new section at all"
    assert scan.unchecked_sections == {"extra"}
    # …and the section list the loader really has is fully accounted for.
    assert config_keys(SOURCE).unchecked_sections == set()
