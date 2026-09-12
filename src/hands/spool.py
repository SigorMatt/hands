"""The spool — the whole of hands' runtime state (DESIGN §6, §7, §11).

Files under `~/.hands/`:

    jobs/<id>.json      one job record per file, written atomically, never pruned
    roles/<role>.json   last_session_id + last_job for `--context keep`
    inbox.jsonl         append-only event list
    inbox.acks.jsonl    append-only ack markers, so acking never rewrites history

The daemon (§3) is a single asyncio process and the CLI only reads, so plain
synchronous IO with `os.replace` is enough; no locking is needed.
"""

from __future__ import annotations

import json
import logging
import os
import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import MISSING, dataclass, field, fields
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

log = logging.getLogger("hands.spool")

__all__ = [
    "EVENT_KINDS",
    "INITIAL_STATES",
    "JOB_FIELDS",
    "STATES",
    "TERMINAL_STATES",
    "TRANSITIONS",
    "Event",
    "IllegalTransition",
    "Job",
    "PathEscape",
    "RoleState",
    "Spool",
    "SpoolError",
    "new_job_id",
    "resolve_kinds",
    "resolve_under_roots",
]


class SpoolError(Exception):
    """The spool was asked for something it cannot do."""


class IllegalTransition(SpoolError):
    """A job was asked to move along an edge the state machine does not have."""


class PathEscape(SpoolError):
    """A path left the allowed roots (DESIGN §4)."""


# --------------------------------------------------------- state machine §6
#
# DESIGN §6: held → queued → running → done | failed | limited | killed |
# orphaned; held → denied.
#
# Two edges the design leaves open, decided here and kept in this table so
# U4/U5/U7 read them rather than re-deciding:
#   * queued → killed exists: `hands cancel <job>` must reach a job that has
#     not been spawned yet, and there is no other state for the result.
#   * queued → held does NOT exist: gating is decided when the job is created
#     (§8), so a job is born `held` or never becomes one. A gated *cancel* is
#     a gate on the cancel, not a backwards move of the job.
# A `limited` job is never revived either: the resume is a new job carrying
# `resumed_from` (§6).

TRANSITIONS: dict[str, frozenset[str]] = {
    "held": frozenset({"queued", "denied"}),
    "queued": frozenset({"running", "killed"}),
    "running": frozenset({"done", "failed", "limited", "killed", "orphaned"}),
    "done": frozenset(),
    "failed": frozenset(),
    "limited": frozenset(),
    "killed": frozenset(),
    "orphaned": frozenset(),
    "denied": frozenset(),
}
STATES: tuple[str, ...] = tuple(TRANSITIONS)
TERMINAL_STATES = frozenset(state for state, out in TRANSITIONS.items() if not out)
INITIAL_STATES = frozenset({"held", "queued"})

CONTEXTS = frozenset({"clear", "keep"})  # §2
#: §6: the three clients that can ask for work, plus `limit` — the origin of a
#: job hands files for itself when a rate limit resets (H-004).
ORIGINS = frozenset({"driver", "playbook", "cli", "limit"})  # §6

# §11 event kinds. Closed on purpose: a unit that needs a new kind adds it here,
# where `hands wait --for <kind>` and the playbook can see it.
EVENT_KINDS = frozenset(
    {
        "job.held",  # a gated job is waiting for a human (§8)
        "job.done",
        "job.failed",
        "job.limited",
        "job.killed",
        "job.orphaned",
        "job.denied",
        "gate.requested",  # a human decision is waiting on a cancel (§8)
        "monitor.stall",
        "monitor.tripwire",
        "monitor.event",
        "playbook.rule",
        "stop",
        # §10: a stop over a pipeline already stopped. The first reason is kept,
        # so this one takes nothing and notifies nobody — it is recorded here and
        # nowhere else, which is why it is a kind of its own. In the `pipeline`
        # namespace and not in `stop`'s (H-011, §21): `--for stop` must not wake a
        # driver on a stop that was deliberately not notified.
        "pipeline.stop_suppressed",
        "pipeline.resumed",  # the other half of §10's stop → resume cycle (H-007)
        "gate.decided",
        "limit",
        "resume",
        "heartbeat",
        "notify",  # a notification hands could not deliver (§11, U8)
    }
)


def resolve_kinds(spec: str) -> frozenset[str]:
    """The kinds `hands wait --for <spec>` waits for (§11).

    The driver kit types `hands wait --for stop,held` (§11, §12) and the kind it
    means is `job.held`, so a name is matched three ways, in this order: the kind
    itself (`job.held`), the part after the dot (`held`), and a namespace
    (`job` → every `job.*`). A name that no kind can have is refused here rather
    than blocking forever on an event that cannot arrive.
    """
    wanted: set[str] = set()
    for raw in spec.split(","):
        name = raw.strip()
        if not name:
            continue
        matched = {
            kind
            for kind in EVENT_KINDS
            if kind == name or kind.endswith(f".{name}") or kind.startswith(f"{name}.")
        }
        if not matched:
            raise SpoolError(
                f"no inbox event kind is called {name!r}; the kinds are: "
                f"{', '.join(sorted(EVENT_KINDS))}"
            )
        wanted |= matched
    if not wanted:
        raise SpoolError("--for needs at least one event kind, e.g. `--for stop,held`")
    return frozenset(wanted)


# ------------------------------------------------------------- job record §6


@dataclass
class Job:
    """The record of §6, "returned verbatim, stored forever".

    Every field is modelled now, including the ones only later units fill, so
    that no later unit has to reshape the record.
    """

    id: str
    role: str
    context: str
    state: str
    created: str
    origin: str
    prompt: str
    started: str | None = None
    ended: str | None = None
    files_written: list[dict[str, Any]] = field(default_factory=list)
    session_id: str | None = None
    transcript_path: str | None = None
    pid: int | None = None
    exit_code: int | None = None
    head_at_start: str | None = None
    head_at_end: str | None = None
    result: str | None = None
    verdict: str | None = None
    stderr_tail: str | None = None
    permission_denials: list[Any] = field(default_factory=list)
    num_turns: int | None = None
    duration_ms: int | None = None
    total_cost_usd: float | None = None
    limit: dict[str, Any] | None = None
    gate: dict[str, Any] | None = None
    resumed_from: str | None = None
    playbook_sha256: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {name: getattr(self, name) for name in JOB_FIELDS}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Job:
        """Rebuild a record. Unknown keys are an error; optional keys may be absent.

        Records are kept forever (§7), so a record written before a later unit
        added an optional field must still load; it takes that field's default.
        """
        unknown = sorted(set(data) - set(JOB_FIELDS))
        if unknown:
            raise SpoolError(f"job record has unknown field(s): {', '.join(unknown)}")
        missing = sorted(name for name in _REQUIRED_FIELDS if name not in data)
        if missing:
            raise SpoolError(f"job record is missing field(s): {', '.join(missing)}")
        return cls(**data)


JOB_FIELDS: tuple[str, ...] = tuple(f.name for f in fields(Job))
_REQUIRED_FIELDS: tuple[str, ...] = tuple(
    f.name
    for f in fields(Job)
    if f.default is MISSING and f.default_factory is MISSING  # type: ignore[misc]
)
_SETTABLE_FIELDS = frozenset(JOB_FIELDS) - {"id", "created", "state"}


@dataclass
class RoleState:
    """`~/.hands/roles/<role>.json` — what `--context keep` resumes (§6).

    `consecutive_resumes` is §6's limit counter: auto-resumes since the role's
    last terminal `done`. It lives on the role and not on a job because it is
    the *role* that hands gives up on after `limits.max_resumes` (§6).
    """

    role: str
    last_session_id: str | None = None
    last_job: str | None = None
    consecutive_resumes: int = 0
    updated: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "last_session_id": self.last_session_id,
            "last_job": self.last_job,
            "consecutive_resumes": self.consecutive_resumes,
            "updated": self.updated,
        }


@dataclass
class Event:
    """One inbox event (§11)."""

    id: str
    kind: str
    created: str
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind, "created": self.created, "payload": self.payload}


# ------------------------------------------------------------------- ids/time


_B36 = "0123456789abcdefghijklmnopqrstuvwxyz"
_ID_WIDTH = 9  # base36 milliseconds stays 9 wide until the year 5138


def now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _b36(value: int, width: int) -> str:
    out = ""
    while value:
        value, rem = divmod(value, 36)
        out = _B36[rem] + out
    return (out or "0").rjust(width, "0")


def new_job_id(now_ms: int | None = None, suffix: str | None = None) -> str:
    """A short, sortable, filesystem-safe id: base36 milliseconds + 4 random chars.

    Sortable because the time part is fixed width; collisions inside one
    millisecond are resolved by `Spool.create_job`, which creates the file with
    O_EXCL and retries.
    """
    ms = int(time.time() * 1000) if now_ms is None else int(now_ms)
    if suffix is None:
        suffix = "".join(_B36[b % 36] for b in os.urandom(4))
    return f"{_b36(ms, _ID_WIDTH)}-{suffix}"


# ----------------------------------------------------------- atomic file IO


def _fsync_dir(path: Path) -> None:
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:  # pragma: no cover - not all platforms allow this
        return
    try:
        os.fsync(fd)
    except OSError:  # pragma: no cover
        pass
    finally:
        os.close(fd)


def atomic_write(path: Path, text: str) -> None:
    """Write `text` to `path` so a reader sees either the old file or the new one.

    tmp file in the same directory → fsync → `os.replace` → fsync the directory.
    If anything fails the tmp file is removed and the old file is untouched.
    """
    tmp = path.with_name(f".{path.name}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    try:
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    _fsync_dir(path.parent)


def _append_line(path: Path, text: str) -> None:
    """Append one line durably. Append-only files are never rewritten."""
    with path.open("a", encoding="utf-8") as handle:
        handle.write(text + "\n")
        handle.flush()
        os.fsync(handle.fileno())


# ------------------------------------------------------------ path confinement


def resolve_under_roots(candidate: str | os.PathLike[str], roots: Iterable[str | Path]) -> Path:
    """Resolve `candidate` and prove it stays inside one of `roots` (DESIGN §4).

    Rejects `..` anywhere in the path, relative paths, absolute paths outside the
    roots, and any symlink whose target leaves them. The path need not exist; its
    existing parents are still resolved, so a symlinked parent cannot be used to
    escape. Returns the fully resolved path.
    """
    real_roots: list[Path] = []
    for root in roots:
        try:
            real_roots.append(Path(root).expanduser().resolve())
        except OSError as exc:  # pragma: no cover - unreadable root
            raise PathEscape(f"allowed root {root} cannot be resolved: {exc}") from exc
    if not real_roots:
        raise PathEscape("no allowed roots are configured; every path is refused")

    raw = os.fspath(candidate)
    if not raw:
        raise PathEscape("empty path")
    path = Path(raw).expanduser()
    if ".." in path.parts:
        raise PathEscape(f"{raw!r} contains '..'")
    if not path.is_absolute():
        raise PathEscape(f"{raw!r} is relative; give an absolute path or one starting with ~")
    try:
        resolved = path.resolve()
    except OSError as exc:
        raise PathEscape(f"{raw!r} cannot be resolved: {exc}") from exc

    for root in real_roots:
        if resolved == root or root in resolved.parents:
            return resolved
    listed = ", ".join(str(root) for root in real_roots)
    raise PathEscape(f"{raw!r} resolves to {resolved}, outside the allowed roots: {listed}")


# --------------------------------------------------------------------- spool


class Spool:
    """Reader/writer for `~/.hands/`."""

    def __init__(self, root: str | Path | None = None) -> None:
        #: Called with every event this spool appends, in the appending call's own
        #: stack. The daemon puts one here so `hands wait --for` is a subscription
        #: and not a poll (§11); a listener that raises is logged and ignored,
        #: because writing the event is the part that must not fail.
        self.listeners: list[Callable[[Event], None]] = []
        self.root = Path(root).expanduser() if root is not None else Path("~/.hands").expanduser()
        self.jobs_dir = self.root / "jobs"
        self.roles_dir = self.root / "roles"
        self.inbox_path = self.root / "inbox.jsonl"
        self.acks_path = self.root / "inbox.acks.jsonl"
        for directory in (self.root, self.jobs_dir, self.roles_dir):
            directory.mkdir(parents=True, exist_ok=True)

    # ---------------------------------------------------------------- jobs

    def job_path(self, job_id: str) -> Path:
        if not job_id or "/" in job_id or job_id.startswith("."):
            raise SpoolError(f"bad job id {job_id!r}")
        return self.jobs_dir / f"{job_id}.json"

    def stream_path(self, job_id: str) -> Path:
        """`~/.hands/jobs/<job>.stream.jsonl` — the captured stream-json of §7.

        The runner appends to this file as each event arrives and never keeps the
        events (§21); `hands log <job>` and `hands log -f` read it back. It is
        the one spool file hands does not write through `_append_line`: an fsync
        per stream-json line would cost a disk write per token.
        """
        return self.job_path(job_id).with_name(f"{job_id}.stream.jsonl")

    def create_job(
        self,
        *,
        role: str,
        context: str,
        prompt: str,
        origin: str,
        state: str = "queued",
        **overrides: Any,
    ) -> Job:
        if not role or not isinstance(role, str):
            raise SpoolError(f"job needs a role, got {role!r}")
        if context not in CONTEXTS:
            raise SpoolError(f"context must be one of {sorted(CONTEXTS)}, got {context!r}")
        if origin not in ORIGINS:
            raise SpoolError(f"origin must be one of {sorted(ORIGINS)}, got {origin!r}")
        if state not in INITIAL_STATES:
            raise SpoolError(f"a job starts in {sorted(INITIAL_STATES)} (§6), not {state!r}")
        self._check_fields(overrides)

        job = Job(
            id="",
            role=role,
            context=context,
            state=state,
            created=now_iso(),
            origin=origin,
            prompt=prompt,
        )
        for name, value in overrides.items():
            setattr(job, name, value)

        for _ in range(100):
            job.id = new_job_id()
            path = self.job_path(job.id)
            try:
                fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                continue
            os.close(fd)
            self.save_job(job)
            return job
        raise SpoolError("could not allocate a free job id")  # pragma: no cover

    def save_job(self, job: Job) -> None:
        atomic_write(self.job_path(job.id), json.dumps(job.to_dict(), indent=2, sort_keys=True))

    def load_job(self, job_id: str) -> Job:
        path = self.job_path(job_id)
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise SpoolError(f"no such job {job_id!r}") from exc
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise SpoolError(f"job {job_id!r} is not readable JSON: {exc}") from exc
        return Job.from_dict(data)

    def list_jobs(self) -> list[Job]:
        """Every job, oldest id first. Stray files in the directory are ignored."""
        out = []
        for path in sorted(self.jobs_dir.glob("*.json")):
            if path.name.startswith("."):
                continue
            out.append(self.load_job(path.stem))
        return out

    def transition(self, job: Job | str, state: str, **updates: Any) -> Job:
        """Move a job along an edge of §6, refusing anything else.

        `started` is stamped on entering `running` and `ended` on entering a
        terminal state, unless the caller passes them explicitly.
        """
        record = self.load_job(job) if isinstance(job, str) else job
        if state not in TRANSITIONS:
            raise IllegalTransition(f"{record.state} -> {state}: {state!r} is not a job state")
        if state not in TRANSITIONS[record.state]:
            allowed = ", ".join(sorted(TRANSITIONS[record.state])) or "nothing (terminal)"
            raise IllegalTransition(
                f"{record.state} -> {state} is not a legal transition for job "
                f"{record.id}; from {record.state} a job may go to {allowed}"
            )
        self._check_fields(updates)

        record.state = state
        for name, value in updates.items():
            setattr(record, name, value)
        if state == "running" and record.started is None:
            record.started = now_iso()
        if state in TERMINAL_STATES and record.ended is None:
            record.ended = now_iso()
        self.save_job(record)
        return record

    @staticmethod
    def _check_fields(updates: dict[str, Any]) -> None:
        unknown = sorted(set(updates) - _SETTABLE_FIELDS)
        if unknown:
            raise SpoolError(f"not settable job field(s): {', '.join(unknown)}")

    # ---------------------------------------------------------- role state

    def role_path(self, role: str) -> Path:
        if not role or "/" in role or role.startswith("."):
            raise SpoolError(f"bad role name {role!r}")
        return self.roles_dir / f"{role}.json"

    def read_role(self, role: str) -> RoleState:
        path = self.role_path(role)
        if not path.exists():
            return RoleState(role=role)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SpoolError(f"role state {path} is not readable: {exc}") from exc
        return RoleState(
            role=role,
            last_session_id=data.get("last_session_id"),
            last_job=data.get("last_job"),
            consecutive_resumes=data.get("consecutive_resumes") or 0,
            updated=data.get("updated"),
        )

    def write_role(self, state: RoleState) -> RoleState:
        state.updated = now_iso()
        atomic_write(
            self.role_path(state.role), json.dumps(state.to_dict(), indent=2, sort_keys=True)
        )
        return state

    def update_role(self, role: str, **fields: Any) -> RoleState:
        """Read-modify-write one role's state, leaving every other field alone.

        Whole-record writes are what lose counters: the session id is rewritten
        on every job (§2) and the limit counter of §6 must survive that.
        """
        state = self.read_role(role)
        unknown = sorted(set(fields) - {"last_session_id", "last_job", "consecutive_resumes"})
        if unknown:
            raise SpoolError(f"not settable role field(s): {', '.join(unknown)}")
        for name, value in fields.items():
            setattr(state, name, value)
        return self.write_role(state)

    def set_last_session(
        self, role: str, *, session_id: str | None, job_id: str | None
    ) -> RoleState:
        return self.update_role(role, last_session_id=session_id, last_job=job_id)

    # --------------------------------------------------------------- inbox

    def append_event(self, kind: str, payload: dict[str, Any] | None = None) -> Event:
        if kind not in EVENT_KINDS:
            raise SpoolError(f"unknown event kind {kind!r}; known kinds: {sorted(EVENT_KINDS)}")
        event = Event(
            id=self._next_event_id(), kind=kind, created=now_iso(), payload=dict(payload or {})
        )
        _append_line(self.inbox_path, json.dumps(event.to_dict(), sort_keys=True))
        for listener in list(self.listeners):
            try:
                listener(event)
            except Exception:  # pragma: no cover - a listener bug must not lose the event
                log.exception("inbox listener failed on event %s (%s)", event.id, event.kind)
        return event

    def events(self, *, since: str | None = None, unacked_only: bool = False) -> list[Event]:
        out = []
        acked = self.acked_ids() if unacked_only else frozenset()
        for lineno, line in enumerate(self._lines(self.inbox_path), start=1):
            try:
                data = json.loads(line)
                event = Event(
                    id=data["id"],
                    kind=data["kind"],
                    created=data["created"],
                    payload=data["payload"],
                )
            except (json.JSONDecodeError, KeyError, TypeError) as exc:
                raise SpoolError(
                    f"{self.inbox_path}:{lineno} is not a readable event: {exc}"
                ) from exc
            if since is not None and event.id <= since:
                continue
            if unacked_only and event.id in acked:
                continue
            out.append(event)
        return out

    def unacked(self) -> list[Event]:
        return self.events(unacked_only=True)

    def ack(self, event_ids: str | Iterable[str]) -> list[str]:
        """Mark events read by appending markers; the inbox itself is never rewritten."""
        wanted = [event_ids] if isinstance(event_ids, str) else list(event_ids)
        known = {event.id for event in self.events()}
        unknown = [event_id for event_id in wanted if event_id not in known]
        if unknown:
            raise SpoolError(f"no such inbox event(s): {', '.join(unknown)}")
        already = self.acked_ids()
        newly = []
        for event_id in wanted:
            if event_id in already:
                continue
            _append_line(self.acks_path, json.dumps({"id": event_id, "acked": now_iso()}))
            newly.append(event_id)
        return newly

    def acked_ids(self) -> frozenset[str]:
        out = set()
        for lineno, line in enumerate(self._lines(self.acks_path), start=1):
            try:
                out.add(json.loads(line)["id"])
            except (json.JSONDecodeError, KeyError, TypeError) as exc:
                raise SpoolError(f"{self.acks_path}:{lineno} is not a readable ack: {exc}") from exc
        return frozenset(out)

    def _next_event_id(self) -> str:
        return f"e{len(self._lines(self.inbox_path)) + 1:06d}"

    @staticmethod
    def _lines(path: Path) -> Sequence[str]:
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return []
        except OSError as exc:
            raise SpoolError(f"{path} is not readable: {exc}") from exc
        return [line for line in text.splitlines() if line.strip()]
