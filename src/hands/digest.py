"""`hands digest` (DESIGN §42 "`digest`"): one line per project on the machine.

Every `~/.hands/<project>.toml`, in name order, is one line. A config that loads
gives seven fields, joined by ` | `:

    <project> | daemon up|down | pipeline running|paused | mission <n>|- |
    builder running <job> <age>|idle, verdict <line>|none |
    architect|driver <used>/<budget> | stop <time> <reason>|no stop

- the daemon is `up` when its socket answers `status` within two seconds
  (`STATUS_TIMEOUT_S`), else `down`;
- the pipeline is `paused` when `pipeline.json` says so (an unreadable one reads
  paused, as the engine reads it), else `running`;
- the mission is the number on the first line of the builder's
  `meta/CHECKPOINT.md` (at its repository root) that begins `Mission:`, else `-`;
- the builder is `running <job> <age>` for its newest job in state `running`, else
  `idle`; the verdict is the newest builder job's verdict line, cut to 60
  characters, or `none`;
- the consultations are `architect <used>/<budget>` when the committed playbook
  sets `[series] architect = "role"`, else `driver <used>/<budget>` (with no
  playbook that loads, the default `[limits] max_consults`), counted as the engine
  counts them;
- the stop is the newest `stop` event's time and the first line of its reason,
  cut to 100 characters (with none in the inbox, `pipeline.json`'s stop), or
  `no stop`.

A config that does not load is one line, `<file>: does not load`: never its
contents and never the loader's message, which can quote a value.

Every field is redacted of every loadable project's `cmd_secret` and
`ntfy_token`, by value and in any case, before it is cut (§41's rule for the
capture script: redact first, cut after), and the joined line is redacted again.

It reads each project's spool and repository and writes nothing: the spool is
read through `ReadOnlySpool`, which never creates a directory, and the playbook
engine is built only to count. It needs no daemon. The phone's `digest <secret>`
publishes the same lines titled `DIGEST_TITLE` (`hands.phone`).
"""

from __future__ import annotations

import json
import re
import socket
import time
import tomllib
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from hands.api import _age, _checkpoint_root
from hands.config import Config, check_project_name, hands_dir, parse_config
from hands.playbook import (
    ARCHITECT,
    DEFAULT_MAX_CONSULTS,
    Playbook,
    PlaybookEngine,
    PlaybookError,
    load_playbook,
    playbook_path,
)
from hands.spool import Job, Spool

__all__ = [
    "DIGEST_TITLE", "REASON_CHARS", "REDACTED", "STATUS_TIMEOUT_S", "VERDICT_CHARS",
    "ReadOnlySpool", "daemon_answers", "digest_lines", "redactor",
]  # fmt: skip

#: §42: the phone's `digest` is published "titled `digest`".
DIGEST_TITLE = "digest"
#: §42: "`up` when its socket answers `status` within two seconds".
STATUS_TIMEOUT_S = 2.0
#: §42: "the newest builder job's verdict line cut to 60 characters".
VERDICT_CHARS = 60
#: §42: "the first line of its reason cut to 100 characters".
REASON_CHARS = 100
#: What a secret is replaced by (§41's capture script writes the same).
REDACTED = "[redacted]"
SEPARATOR = " | "
CHECKPOINT = Path("meta") / "CHECKPOINT.md"
_MISSION_RE = re.compile(r"\AMission:\s*\D*?(\d+)")


class ReadOnlySpool(Spool):
    """A `Spool` that reads and never creates: `Spool()` makes the spool's
    directories, which a read-only command must not (§42: "read-only")."""

    def __init__(self, root: str | Path) -> None:
        self.listeners = []
        self.root = Path(root).expanduser()
        self.jobs_dir = self.root / "jobs"
        self.roles_dir = self.root / "roles"
        self.inbox_path = self.root / "inbox.jsonl"
        self.acks_path = self.root / "inbox.acks.jsonl"

    def list_jobs(self) -> list[Job]:
        return super().list_jobs() if self.jobs_dir.is_dir() else []


def redactor(values: Iterable[str]) -> Any:
    """A function that replaces each of `values`, in any case, longest first."""
    forms = sorted({value for value in values if value}, key=len, reverse=True)
    pattern = (
        re.compile("|".join(re.escape(form) for form in forms), re.IGNORECASE) if forms else None
    )

    def redact(text: str) -> str:
        return text if pattern is None else pattern.sub(REDACTED, text)

    return redact


def daemon_answers(path: Path, timeout: float = STATUS_TIMEOUT_S) -> bool:
    """Does the daemon on the unix socket `path` answer `status` within `timeout`
    seconds — one JSON-RPC response carrying a result?"""
    deadline = time.monotonic() + timeout
    request = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "status", "params": {}}) + "\n"
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        sock.settimeout(timeout)
        sock.connect(str(path))
        sock.sendall(request.encode("utf-8"))
        data = b""
        while b"\n" not in data:
            left = deadline - time.monotonic()
            if left <= 0:
                return False
            sock.settimeout(left)
            chunk = sock.recv(65536)
            if not chunk:
                return False
            data += chunk
        response = json.loads(data.split(b"\n", 1)[0])
    except (OSError, ValueError):
        return False
    finally:
        sock.close()
    return isinstance(response, dict) and "result" in response


def _load(path: Path) -> Config:
    """`load_config` for the file `path` itself, so a daemon's digest reads the
    directory its own config is in."""
    check_project_name(path.stem)
    data = tomllib.loads(path.read_bytes().decode("utf-8"))
    return parse_config(data, project=path.stem, path=path)


def digest_lines(base: Path | None = None) -> list[str]:
    """§42: the digest of every `<project>.toml` in `base` (`~/.hands`), in name order."""
    base = hands_dir() if base is None else Path(base)
    try:
        paths = sorted(base.glob("*.toml"), key=lambda path: path.stem)
    except OSError:  # pragma: no cover - an unreadable ~/.hands
        paths = []
    loaded: list[tuple[Path, Config | None]] = []
    for path in paths:
        try:
            loaded.append((path, _load(path)))
        except Exception:  # §42: "a config that does not load", whatever the reason
            loaded.append((path, None))
    secrets = [
        value
        for _path, config in loaded
        if config is not None
        for value in (config.notify.cmd_secret, config.notify.ntfy_token)
        if value
    ]
    redact = redactor(secrets)
    lines = []
    for path, config in loaded:
        if config is None:
            lines.append(redact(f"{path.name}: does not load"))
        else:
            lines.append(redact(_project_line(config, redact)))
    return lines


def _first_line(text: str, chars: int, redact: Any) -> str:
    """Redact the whole of `text`, then take its first line and cut that to `chars`:
    never the other way round (§41)."""
    whole = redact(text)
    lines = whole.splitlines()
    return (lines[0] if lines else "")[:chars]


def _project_line(config: Config, redact: Any) -> str:
    spool = ReadOnlySpool(config.spool_root)
    daemon = "up" if daemon_answers(config.server.socket) else "down"
    try:
        fields = _spool_fields(config, spool, redact)
    except Exception:  # one unreadable spool must not end the digest
        fields = ["spool unreadable"]
    return SEPARATOR.join([config.project, f"daemon {daemon}", *fields])


def _spool_fields(config: Config, spool: ReadOnlySpool, redact: Any) -> list[str]:
    engine = PlaybookEngine(config, spool, send=_never, enqueue=_never)
    cwd = Path(config.role("builder").cwd)
    pipeline = "paused" if engine.state.paused else "running"
    jobs = spool.list_jobs()
    builder_jobs = [job for job in jobs if job.role == "builder"]
    running = [job for job in builder_jobs if job.state == "running"]
    builder = f"running {running[-1].id} {_age(running[-1].started)}" if running else "idle"
    newest = builder_jobs[-1].verdict if builder_jobs else None
    verdict = _first_line(newest, VERDICT_CHARS, redact) if newest else "none"
    return [
        f"pipeline {pipeline}",
        f"mission {_mission(cwd)}",
        f"builder {builder}, verdict {verdict}",
        _consults(config, engine),
        _stop(spool, engine, redact),
    ]


def _consults(config: Config, engine: PlaybookEngine) -> str:
    book: Playbook | None
    try:
        book = load_playbook(playbook_path(config), cwd=config.role("builder").cwd)
    except PlaybookError:
        book = None
    if book is not None and book.architect == "role":
        return f"{ARCHITECT} {engine.architect_consults_used()}/{book.max_architect_consults}"
    budget = book.max_consults if book is not None else DEFAULT_MAX_CONSULTS
    return f"driver {engine.consults_used(book)}/{budget}"


def _stop(spool: ReadOnlySpool, engine: PlaybookEngine, redact: Any) -> str:
    when: str | None = None
    reason: str | None = None
    for event in reversed(spool.events()):
        if event.kind == "stop":
            when, said = event.created, event.payload.get("reason")
            reason = said if isinstance(said, str) else ""
            break
    if when is None and engine.state.stop_reason is not None:
        when, reason = engine.state.stopped_at or "-", engine.state.stop_reason
    if when is None:
        return "no stop"
    first = _first_line(reason or "", REASON_CHARS, redact)
    return f"stop {redact(when)} {first}".rstrip()


def _mission(cwd: Path) -> str:
    try:
        text = (_checkpoint_root(cwd) / CHECKPOINT).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "-"
    for line in text.splitlines():
        if line.startswith("Mission:"):
            match = _MISSION_RE.match(line)
            return match.group(1) if match else "-"
    return "-"


async def _never(*_args: Any, **_kwargs: Any) -> Any:  # pragma: no cover - never called
    raise RuntimeError("the digest's engine only counts; it sends nothing")
