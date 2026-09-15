"""`hands who` and `handswho` — who is running what, for a human (DESIGN §4, §11, §24).

One short picture joined from three sources:

  * this daemon     its roles, running/queued/held jobs, pipeline and inbox, read
                    over the socket with the read-only `who` method. §24 says the
                    view "reads this daemon's state in-process"; `hands who` and
                    `handswho` are client processes, so the daemon's own process
                    answers the question and the client never runs `hands`.
  * /proc           every other `claude` process: headless or a session, its cwd,
                    age, and the commands running under it right now
  * transcripts     for a session: waiting for you, working or thinking, and the
                    last thing the human typed. §27 (H-020): a process's transcript
                    is the one `~/.claude/sessions/<pid>.json` names by `sessionId`
                    (only `pid` and `sessionId` are taken; the `.key` file beside it
                    is never opened). With no usable sessions file the line says
                    `transcript: by directory` and the newest transcript of the
                    cwd's `~/.claude/projects/` folder is used, except one whose
                    session id a hands job record holds (`JobSessions`), the
                    sessions file of a hands job's pid names (§28), or that began
                    during a job that ended within `[who] grace_s` (§29)

§24's rules: roles are labelled `role <r>`; your own interactive session in a
role directory is `(your session)`; a session under `~/hands-driver/<project>/`
(§12, §14 step 2) is `driver:<project>`. The hierarchy is daemon → jobs →
processes and session → processes. A session's state counts only once it has
held for two scans (`Debounce`), and your own sessions — interactive ones outside
a driver directory — are shown but never fingerprinted, so they never cause a
push.

`hands who` prints the picture once. `handswho` (= `hands who --daemon`) pushes it
to `[notify] who_topic` when the fingerprint changes and whenever `status`, `who`,
`check` or `?` arrives on `who_cmd_topic`. Those four words are the whole command
set: nothing is executed, and the answer is the same status picture, so §24
names no secret for this topic and none is asked for.

Every input is injectable (`Sources`, `WhoPusher`): the process table, the
transcript reader, the daemon state, the clock and the ntfy transport.
Ported from the claudewho prototype (2026-09-12).
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import hashlib
import json
import logging
import os
import re
import sys
import time
from collections import deque
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, TextIO

from hands import notify as notify_mod
from hands.config import DEFAULT_WHO_GRACE_S, ConfigError, load_config, resolve_project
from hands.phone import BACKOFF_S, SEEN_IDS

if TYPE_CHECKING:  # pragma: no cover
    from hands.config import Config

__all__ = [
    "COMMANDS",
    "PUSH_TITLE",
    "REQUESTED_TITLE",
    "Debounce",
    "JobSessions",
    "Sources",
    "Transcripts",
    "WhoError",
    "WhoPusher",
    "build_summary",
    "main",
    "print_once",
    "proc_table",
    "session_id_for",
    "watch",
]

log = logging.getLogger("hands.who")

PROMPT_CHARS = 70
CMD_CHARS = 60
#: §24: the words on `who_cmd_topic` that ask for the picture.
COMMANDS = ("status", "who", "check", "?")
PUSH_TITLE = "hands who"
REQUESTED_TITLE = "hands who (requested)"
DEFAULT_INTERVAL_S = 20.0
#: A change seen sooner than this after the last push waits for the next scan past it.
DEFAULT_MIN_GAP_S = 60.0
#: A transcript older than the session's age plus this is not that session's.
TRANSCRIPT_SLACK_S = 3600.0
SHELLS = {"bash", "sh", "zsh", "dash"}
#: A `sessionId` becomes a file name, so it must be a plain basename.
SESSION_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")
#: §27: how a process's transcript was found.
BY_SESSION = "session"
BY_DIRECTORY = "directory"
NEEDS_YOU = {"stop", "job.held"}

Proc = dict[str, Any]


class WhoError(ValueError):
    """The who view cannot run as asked (no `who_topic` to push to)."""


# ----------------------------------------------------------------- /proc


def _read(path: Path, default: str = "") -> str:
    try:
        return path.read_text(errors="replace")
    except OSError:
        return default


def proc_table(root: Path = Path("/proc"), *, clk_tck: int | None = None) -> dict[int, Proc]:
    """pid -> {ppid, argv, cwd, comm, age_s}, read from a /proc-shaped directory."""
    tck = clk_tck or os.sysconf("SC_CLK_TCK")
    uptime = float((_read(root / "uptime", "0 0").split() or ["0"])[0])
    out: dict[int, Proc] = {}
    try:
        entries = list(root.iterdir())
    except OSError:
        return out
    for entry in entries:
        if not entry.name.isdigit():
            continue
        argv = [a for a in _read(entry / "cmdline").split("\0") if a]
        if not argv:
            continue
        stat = _read(entry / "stat")
        try:
            after = stat[stat.rindex(")") + 2 :].split()
            ppid = int(after[1])
            age = max(0.0, uptime - int(after[19]) / tck)
        except (ValueError, IndexError):
            ppid, age = 0, 0.0
        try:
            cwd = os.readlink(entry / "cwd")
        except OSError:
            cwd = ""
        out[int(entry.name)] = {
            "ppid": ppid, "argv": argv, "cwd": cwd, "age_s": age,
            "comm": _read(entry / "comm").strip(),
        }  # fmt: skip
    return out


def is_claude(p: Proc) -> bool:
    a0 = os.path.basename(p["argv"][0])
    return a0 == "claude" or (
        a0 in ("node", "bun") and len(p["argv"]) > 1 and os.path.basename(p["argv"][1]) == "claude"
    )


def claude_processes(table: dict[int, Proc]) -> list[dict[str, Any]]:
    """Top-level claude processes (a claude whose parent is not a claude)."""
    res = []
    for pid, p in table.items():
        if not is_claude(p):
            continue
        parent = table.get(p["ppid"])
        if parent and is_claude(parent):
            continue  # a nested claude, attributed to its parent
        argv = p["argv"]
        res.append({
            "pid": pid, "cwd": p["cwd"], "age_s": p["age_s"],
            "headless": "-p" in argv or "--print" in argv,
            "skip_perms": "--dangerously-skip-permissions" in argv,
        })  # fmt: skip
    return res


def descendants(table: dict[int, Proc], root: int) -> list[int]:
    kids: dict[int, list[int]] = {}
    for pid, p in table.items():
        kids.setdefault(p["ppid"], []).append(pid)
    out, stack = [], [root]
    while stack:
        for k in kids.get(stack.pop(), []):
            out.append(k)
            stack.append(k)
    return out


def clean_cmd(argv: list[str]) -> str:
    """`python -m pytest tests`, not `/x/.venv/bin/python3 -m pytest tests`."""
    argv = [os.path.basename(a) if i == 0 else a for i, a in enumerate(argv)]
    argv = [re.sub(r"^/home/[^/]+/[^ ]*/\.venv/bin/", "", a) for a in argv]
    argv[0] = re.sub(r"^python3(\.\d+)?$", "python", argv[0])
    if argv[0] == "python" and len(argv) > 1 and argv[1].endswith(".py"):
        argv[1] = os.path.basename(argv[1])
    return re.sub(r"\s+", " ", " ".join(argv)).strip()


def child_commands(table: dict[int, Proc], root: int, limit: int = 3) -> list[tuple[str, float]]:
    """Leaf commands under root, (command, age_s), newest first; shells and nested
    claude processes skipped."""
    out = []
    for pid in descendants(table, root):
        p = table[pid]
        if is_claude(p) or p["comm"] in SHELLS:
            continue
        if any(
            table[k]["ppid"] == pid and table[k]["comm"] not in SHELLS
            for k in descendants(table, pid)
        ):
            continue  # not a leaf
        out.append((clean_cmd(p["argv"]), p["age_s"]))
    out.sort(key=lambda x: x[1])
    return out[:limit]


def current_command(table: dict[int, Proc], root: int) -> str | None:
    """The newest leaf command under a claude process, cleaned."""
    kids = child_commands(table, root, limit=1)
    return kids[0][0] if kids else None


# ------------------------------------------------------------ transcripts


def dashed(cwd: str) -> str:
    """Claude Code's directory name for a cwd: every non-alphanumeric is `-`."""
    return re.sub(r"[^A-Za-z0-9]", "-", cwd)


def _tail_lines(path: Path, n: int = 40, block: int = 65536) -> list[str]:
    try:
        with path.open("rb") as fh:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            data = b""
            while size > 0 and data.count(b"\n") <= n:
                step = min(block, size)
                size -= step
                fh.seek(size)
                data = fh.read(step) + data
        return data.decode("utf-8", "replace").splitlines()[-n:]
    except OSError:
        return []


def transcript_state(path: Path, *, now: float) -> dict[str, Any]:
    """{'waiting': bool, 'last_prompt': str, 'idle_s': float}."""
    waiting = False
    last_prompt = ""
    last_type = None
    for raw in reversed(_tail_lines(path)):
        try:
            e = json.loads(raw)
        except ValueError:
            continue
        if not isinstance(e, dict):
            continue
        t = e.get("type")
        content = (e.get("message") or {}).get("content")
        if last_type is None and t in ("user", "assistant"):
            last_type = t
            if t == "assistant":
                waiting = not (
                    isinstance(content, list)
                    and any(isinstance(c, dict) and c.get("type") == "tool_use" for c in content)
                )
        if t == "user" and not last_prompt:
            text = None
            if isinstance(content, str):
                text = content
            elif isinstance(content, list):
                parts = [
                    c.get("text", "") for c in content
                    if isinstance(c, dict) and c.get("type") == "text"
                ]  # fmt: skip
                text = " ".join(parts) if parts else None
            if text and not text.startswith("<") and "tool_result" not in text[:20]:
                last_prompt = text
        if last_prompt and last_type:
            break
    try:
        idle = now - path.stat().st_mtime
    except OSError:
        idle = 0.0
    return {"waiting": waiting, "last_prompt": last_prompt, "idle_s": idle}


def session_id_for(sessions: Path, pid: int) -> str | None:
    """The `sessionId` of `<sessions>/<pid>.json` when that file's `pid` is `pid` (§27).

    Only that one file is opened, by its exact name: the directory is never
    listed, so the `<pid>.<hash>.key` beside it is never read. Of the JSON only
    `pid` and `sessionId` are used. Unreadable, not a JSON object, another pid, or
    a `sessionId` that is not a plain basename: None, as if there were no file.
    """
    try:
        data = json.loads((sessions / f"{pid}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    file_pid, sid = data.get("pid"), data.get("sessionId")
    if type(file_pid) is not int or file_pid != pid:
        return None
    if not isinstance(sid, str) or not SESSION_ID_RE.fullmatch(sid):
        return None
    return sid


#: How many leading lines of a transcript are read for its first `timestamp`.
FIRST_TIMESTAMP_LINES = 20


def _epoch(value: Any) -> float | None:
    """An ISO-8601 time (the spool's `…Z`, a transcript's `timestamp`) as epoch
    seconds; a time without a zone is UTC. Anything else: None."""
    if not isinstance(value, str):
        return None
    try:
        when = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    return when.timestamp()


def first_timestamp(path: Path, lines: int = FIRST_TIMESTAMP_LINES) -> float | None:
    """The first `timestamp` among a transcript's first `lines` lines, as epoch
    seconds; None when none of them has one, or the file cannot be read."""
    try:
        with path.open("rb") as fh:
            for _n, raw in zip(range(lines), fh, strict=False):
                try:
                    entry = json.loads(raw)
                except ValueError:
                    continue
                when = _epoch(entry.get("timestamp")) if isinstance(entry, dict) else None
                if when is not None:
                    return when
    except OSError:
        return None
    return None


class JobSessions:
    """The session ids `hands who`'s directory fallback never attributes (§27, §29).

    Every session id a hands job record holds: `jobs/<id>.json` `session_id`.
    And, for `grace_s` seconds after a job without one ended (§29, REVIEW-12
    should-fix 9), the basename of every transcript in its role's cwd folder
    whose first `timestamp` lies within the record's [`started`, `ended`]: the
    transcripts begun while that job ran. A record with no `started` or `ended`,
    a role missing from `role_cwds`, or a transcript with no timestamp in its
    first lines, excludes nothing by the grace.

    Read-only (the spool's CLI side only reads, §6); the directory is never
    created. A record that has a session id keeps it, so it is read once; one
    without is read again on the next call. Unreadable records are skipped.
    """

    def __init__(
        self,
        jobs_dir: Path,
        *,
        role_cwds: dict[str, str] | None = None,
        projects: Path | None = None,
        grace_s: float = DEFAULT_WHO_GRACE_S,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.jobs_dir = jobs_dir
        self.role_cwds = dict(role_cwds or {})
        self.projects = projects
        self.grace_s = grace_s
        self.clock = clock
        self._known: dict[str, str] = {}

    def __call__(self) -> frozenset[str]:
        try:
            names = [p for p in self.jobs_dir.glob("*.json") if not p.name.startswith(".")]
        except OSError:
            names = []
        now = self.clock()
        begun: set[str] = set()
        for path in names:
            if path.name in self._known:
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if not isinstance(data, dict):
                continue
            sid = data.get("session_id")
            if isinstance(sid, str) and sid:
                self._known[path.name] = sid
            else:
                begun |= self._begun_during(data, now)
        return frozenset(self._known.values()) | begun

    def _begun_during(self, record: dict[str, Any], now: float) -> set[str]:
        """§29: the transcripts begun during a job that ended within the grace."""
        role = record.get("role")
        cwd = self.role_cwds.get(role) if isinstance(role, str) else None
        started, ended = _epoch(record.get("started")), _epoch(record.get("ended"))
        if cwd is None or started is None or ended is None or now - ended > self.grace_s:
            return set()
        folder = (self.projects or Path.home() / ".claude" / "projects") / dashed(cwd)
        try:
            files = [p for p in folder.glob("*.jsonl") if p.is_file()]
        except OSError:
            return set()
        out = set()
        for path in files:
            first = first_timestamp(path)
            if first is not None and started <= first <= ended:
                out.add(path.stem)
        return out


class Transcripts:
    """The transcript reader (§27):
    `(pid, cwd, session age, job session ids) -> (BY_SESSION | BY_DIRECTORY, state or None)`.

    With a sessions file for the pid, the transcript is `<sessionId>.jsonl`, looked
    for in the cwd's project folder first and then in any project folder (a
    session may have changed directory since it started); if it does not exist
    (yet) the state is None — the directory is not consulted. Without one, the
    newest transcript of the cwd's folder whose basename is not a job's session
    id, if recent enough for the session's age.
    """

    def __init__(
        self,
        projects: Path | None = None,
        *,
        sessions: Path | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.projects = projects
        self.sessions = sessions
        self.clock = clock

    def session_id(self, pid: int) -> str | None:
        """The `sessionId` of this reader's `sessions/<pid>.json` (`session_id_for`)."""
        return session_id_for(self.sessions or Path.home() / ".claude" / "sessions", pid)

    def __call__(
        self, pid: int, cwd: str, age_s: float, exclude: frozenset[str] = frozenset()
    ) -> tuple[str, dict[str, Any] | None]:
        root = self.projects or Path.home() / ".claude" / "projects"
        sid = self.session_id(pid)
        now = self.clock()
        if sid is not None:
            named = root / dashed(cwd) / f"{sid}.jsonl"
            if not named.is_file():
                try:
                    named = next(p for p in root.glob(f"*/{sid}.jsonl") if p.is_file())
                except (OSError, StopIteration):
                    return BY_SESSION, None
            return BY_SESSION, transcript_state(named, now=now)
        folder = root / dashed(cwd)
        try:
            files = [
                (p.stat().st_mtime, p) for p in folder.glob("*.jsonl")
                if p.is_file() and p.stem not in exclude
            ]  # fmt: skip
        except OSError:
            return BY_DIRECTORY, None
        if not files:
            return BY_DIRECTORY, None
        mtime, newest = max(files)
        if now - mtime > age_s + TRANSCRIPT_SLACK_S:
            return BY_DIRECTORY, None
        return BY_DIRECTORY, transcript_state(newest, now=now)


# ------------------------------------------------------------- the picture


def short(s: str, n: int) -> str:
    s = re.sub(r"\s+", " ", s or "").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def age(s: float) -> str:
    s = int(s)
    if s < 90:
        return f"{s}s"
    if s < 5400:
        return f"{s // 60}m"
    if s < 172800:
        return f"{s // 3600}h{(s % 3600) // 60:02d}"
    return f"{s // 86400}d"


@dataclass(frozen=True)
class Sources:
    """Everything the picture reads, each one replaceable."""

    project: str
    #: role -> cwd, from the config (so labels work with the daemon down).
    role_cwds: dict[str, str]
    #: The daemon's `who` answer, or None when it is not answering.
    daemon: Callable[[], dict[str, Any] | None]
    procs: Callable[[], dict[int, Proc]]
    #: `(pid, cwd, age_s, job session ids) -> (match, state or None)` (§27).
    transcripts: Callable[[int, str, float, frozenset[str]], tuple[str, dict[str, Any] | None]]
    clock: Callable[[], float]
    #: `~/hands-driver/<project>/` is a driver directory (§12).
    home: Path
    #: The session ids hands' job records hold; never attributed by directory (§27).
    job_sessions: Callable[[], frozenset[str]]
    #: `pid -> sessionId` of `~/.claude/sessions/<pid>.json`, or None. A hands job
    #: pid's session is never attributed by directory either (§28).
    session_of: Callable[[int], str | None]


def _within(cwd: str, root: str) -> bool:
    root = root.rstrip("/")
    return bool(cwd) and (cwd == root or cwd.startswith(root + "/"))


def _driver_of(cwd: str, home: Path) -> str | None:
    base = str(home / "hands-driver")
    if not _within(cwd, base) or cwd == base:
        return None
    return cwd[len(base) + 1 :].split("/")[0]


def _session_state(
    p: dict[str, Any], table: dict[int, Proc], src: Sources, jobs: frozenset[str]
) -> tuple[str, str, dict[str, Any] | None]:
    """(state text, fingerprint value, transcript state or None)."""
    match, ts = src.transcripts(p["pid"], p["cwd"], p["age_s"], jobs)
    text, value = _state_text(ts, bool(child_commands(table, p["pid"])))
    if match == BY_DIRECTORY:
        text += " · transcript: by directory"
    return text, value, ts


def _state_text(ts: dict[str, Any] | None, kids: bool) -> tuple[str, str]:
    if ts is None:
        return ("working", "work") if kids else ("state unknown", "?")
    if ts["waiting"]:
        return f"waiting for you · {age(ts['idle_s'])} idle", "wait"
    if kids:
        return "working", "work"
    return f"thinking · {age(ts['idle_s'])} since last write", "think"


def _inbox_kinds(events: list[dict[str, Any]]) -> str:
    return ", ".join(sorted({str(e.get("kind", "?")) for e in events}))


def _daemon_block(
    state: dict[str, Any], table: dict[int, Proc], project: str
) -> tuple[list[str], list[tuple[str, str]], set[int]]:
    items: list[tuple[str, str]] = []
    pids: set[int] = set()
    roles = state.get("roles") or {}
    jobs = state.get("jobs") or []
    pipeline = state.get("pipeline") or {}
    if pipeline.get("paused"):
        pstate = "pipeline stopped"
        items.append((f"{project}:pipeline", "stopped"))
    elif any(r.get("running") for r in roles.values()):
        pstate = "pipeline running"
    else:
        pstate = "pipeline idle"
    rules = (pipeline.get("playbook") or {}).get("rules")
    head = f"handsd (daemon, project {project}) — {pstate}"
    lines = [head + (f" · {rules} rules" if rules else "")]
    if pipeline.get("paused"):
        lines.append(f"    reason: {short(pipeline.get('stop_reason') or 'paused', 60)}")
    for name in sorted(roles, key=lambda n: (n != "builder", n)):
        role = roles[name]
        job = role.get("running")
        queued = role.get("queued") or []
        if job:
            pid = job.get("pid") if isinstance(job.get("pid"), int) else None
            if pid is not None:
                pids.add(pid)
            live = pid is not None and pid in table
            when = f", {age(table[pid]['age_s'])}" if live else ""
            lines.append(f"  role {name} (job {job.get('id')}{when})")
            if job.get("prompt_line"):
                lines.append(f"      {short(job['prompt_line'], PROMPT_CHARS)}")
            if live:
                for cmd, cage in child_commands(table, pid):
                    lines.append(f"    {short(cmd, CMD_CHARS)} (process, {age(cage)})")
            items.append((f"{project}:{name}", f"run:{job.get('id')}"))
        elif queued:
            plural = "s" if len(queued) != 1 else ""
            lines.append(f"  role {name} — {len(queued)} job{plural} queued")
            items.append((f"{project}:{name}", f"q{len(queued)}"))
        else:
            lines.append(f"  role {name} — no job")
            items.append((f"{project}:{name}", "idle"))
    for job in jobs:
        if job.get("state") != "held":
            continue
        lines.append(f"  held job {job.get('id')} ({job.get('role')}) — needs YOUR decision")
        if job.get("gate_reason"):
            lines.append(f"      {short(job['gate_reason'], 50)}")
        items.append((f"{project}:held:{job.get('id')}", "held"))
    return lines, items, pids


def build_summary(src: Sources) -> tuple[str, list[tuple[str, str]]]:
    """(text, items). Text is the hierarchy; items are the (key, value) pairs the
    caller fingerprints — what is running, held or waiting, never ages or clocks."""
    table = src.procs()
    procs = claude_processes(table)
    state = src.daemon()
    items: list[tuple[str, str]] = []
    blocks: list[str] = []
    hands_pids: set[int] = set()
    inbox: list[dict[str, Any]] = []

    if state is None:
        blocks.append(f"handsd (daemon, project {src.project})\n    not answering")
        items.append((src.project, "down"))
    else:
        lines, daemon_items, hands_pids = _daemon_block(state, table, src.project)
        items += daemon_items
        inbox = list(state.get("inbox") or [])
        if inbox:
            items.append((f"{src.project}:inbox", str(len(inbox))))
        blocks.append("\n".join(lines))

    role_cwds = list(src.role_cwds.values())
    driver_shown = False
    others = [p for p in procs if p["pid"] not in hands_pids]
    jobs: frozenset[str] = frozenset()
    if others:
        # §28: a job's transcript can exist before its record holds the session id.
        by_pid = (src.session_of(pid) for pid in sorted(hands_pids))
        jobs = src.job_sessions() | {sid for sid in by_pid if sid is not None}
    others.sort(key=lambda x: (_driver_of(x["cwd"], src.home) is None, x["cwd"], x["pid"]))
    for p in others:
        driver = _driver_of(p["cwd"], src.home)
        in_role_dir = any(_within(p["cwd"], c) for c in role_cwds)
        if driver is not None:
            label = f"driver:{driver}"
        elif in_role_dir:
            label = src.project + ("" if p["headless"] else " (your session)")
        else:
            label = os.path.basename(p["cwd"].rstrip("/")) or p["cwd"] or "?"
        meta = ["headless" if p["headless"] else "session", age(p["age_s"])]
        if p["skip_perms"]:
            meta.append("skip-perms")
        text, value, ts = _session_state(p, table, src, jobs)
        lines = [f"{label} ({', '.join(meta)}) — {text}"]
        if ts and ts["last_prompt"] and value != "work":
            lines.append(f"    last: {short(ts['last_prompt'], PROMPT_CHARS)}")
        kind = "background process" if value == "wait" else "process"
        for cmd, cage in child_commands(table, p["pid"]):
            lines.append(f"  {short(cmd, CMD_CHARS)} ({kind}, {age(cage)})")
        if driver == src.project and inbox:
            driver_shown = True
            need = any(e.get("kind") in NEEDS_YOU for e in inbox)
            whose = "needs YOU" if need else "informational, the driver acks it on its next check"
            lines.append(
                f"  inbox: {len(inbox)} unread from handsd — {_inbox_kinds(inbox)} — {whose}"
            )
        # §24: your own sessions are shown, never fingerprinted.
        if driver is not None or p["headless"]:
            items.append((f"s:{p['pid']}", value))
        blocks.append("\n".join(lines))

    if inbox and not driver_shown:
        blocks.append(
            f"inbox for a driver of {src.project} (no driver session running)\n"
            f"    {len(inbox)} unread from handsd — {_inbox_kinds(inbox)}"
        )
    n = len(procs)
    head = time.strftime("%H:%M", time.localtime(src.clock()))
    head += f" · {n} claude process{'es' if n != 1 else ''}"
    return head + "\n\n" + "\n\n".join(blocks), items


class Debounce:
    """Session states (keys starting with `s:`) must hold for `hold` scans before
    they count; everything else counts at once."""

    def __init__(self, hold: int = 2) -> None:
        self.hold = hold
        self.seen: dict[str, tuple[str, int]] = {}
        self.stable: dict[str, str] = {}

    def fingerprint(self, items: list[tuple[str, str]]) -> str:
        keys = set()
        out = []
        for k, v in items:
            keys.add(k)
            if not k.startswith("s:"):
                out.append(f"{k}={v}")
                continue
            last, n = self.seen.get(k, (None, 0))
            n = n + 1 if v == last else 1
            self.seen[k] = (v, n)
            if n >= self.hold or k not in self.stable:
                self.stable[k] = v
            out.append(f"{k}={self.stable[k]}")
        for k in list(self.seen):
            if k not in keys:
                self.seen.pop(k, None)
                self.stable.pop(k, None)
        return hashlib.sha256("|".join(sorted(out)).encode()).hexdigest()


# ------------------------------------------------------------- the sources


def socket_state(socket_path: Path, project: str) -> Callable[[], dict[str, Any] | None]:
    """The daemon's `who` answer over its socket; None when it does not answer."""

    def read() -> dict[str, Any] | None:
        from hands.cli import ClientError, call  # the CLI imports this module

        try:
            result = call(socket_path, "who", {}, project=project)
        except (ClientError, OSError, ValueError) as exc:
            log.debug("who: the daemon did not answer: %s", exc)
            return None
        return result if isinstance(result, dict) else None

    return read


def sources_for(config: Config, socket_path: Path) -> Sources:
    transcripts = Transcripts()
    return Sources(
        project=config.project,
        role_cwds={name: str(role.cwd) for name, role in config.roles.items()},
        daemon=socket_state(socket_path, config.project),
        procs=lambda: proc_table(),  # looked up at call time, so a test can replace it
        transcripts=transcripts,
        clock=time.time,
        home=Path.home(),
        job_sessions=JobSessions(
            config.path.parent / "jobs",
            role_cwds={name: str(role.cwd) for name, role in config.roles.items()},
            grace_s=config.who.grace_s,
        ),
        session_of=transcripts.session_id,  # the same sessions directory
    )


def print_once(config: Config, socket_path: Path, *, out: TextIO, as_json: bool) -> int:
    """`hands who`: the picture, once. Exit 0 whether or not the daemon answered —
    a daemon that is down is part of the picture, and the rest is still true."""
    src = sources_for(config, socket_path)
    state = src.daemon()
    text, items = build_summary(replace(src, daemon=lambda: state))
    if as_json:
        payload = {"picture": text, "daemon": state, "items": [list(i) for i in items]}
        print(json.dumps(payload, sort_keys=True), file=out)
    else:
        print(text, file=out)
    return 0


# ---------------------------------------------------------------- handswho


class WhoPusher:
    """Scan on an interval, push on change, push on request (§24)."""

    def __init__(
        self,
        sources: Sources,
        *,
        topic: str,
        cmd_topic: str | None,
        ntfy_url: str,
        post: Callable[..., Awaitable[int]] | None = None,
        stream: Callable[[str], AsyncIterator[str]] | None = None,
        sleep: Callable[[float], Awaitable[None]] | None = None,
        clock: Callable[[], float] = time.time,
        interval: float = DEFAULT_INTERVAL_S,
        min_gap: float = DEFAULT_MIN_GAP_S,
    ) -> None:
        self.sources = sources
        self.topic = topic
        self.cmd_topic = cmd_topic
        self.ntfy_url = ntfy_url.rstrip("/")
        #: None means `hands.notify.http_post` / `http_stream`, looked up at call time.
        self.post = post
        self.stream = stream
        self.sleep: Callable[[float], Awaitable[None]] = sleep or asyncio.sleep
        self.clock = clock
        self.interval = interval
        self.min_gap = min_gap
        self.debounce = Debounce()
        self.fp: str | None = None
        self.last_push: float | None = None
        self.started_at: int | None = None
        self.last_id: str | None = None
        self._seen: deque[str] = deque(maxlen=SEEN_IDS)
        self._lock = asyncio.Lock()

    async def scan(self, *, requested: bool = False) -> bool:
        """One scan; publish when the fingerprint changed (past the gap) or on request."""
        async with self._lock:
            text, items = await asyncio.to_thread(build_summary, self.sources)
            fp = self.debounce.fingerprint(items)
            now = self.clock()
            gap_ok = self.last_push is None or now - self.last_push >= self.min_gap
            if not requested and (fp == self.fp or not gap_ok):
                return False
            if not await self._publish(REQUESTED_TITLE if requested else PUSH_TITLE, text):
                return False
            self.fp, self.last_push = fp, now
            return True

    async def _publish(self, title: str, text: str) -> bool:
        post = self.post if self.post is not None else notify_mod.http_post
        url = f"{self.ntfy_url}/{self.topic}"
        try:
            status = await post(url, title=title, message=text)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # best effort: the next change or request tries again
            log.warning("who: publish failed: %s: %s", type(exc).__name__, exc)
            return False
        if not notify_mod.accepted(status):
            log.warning("who: ntfy answered %s", status)
            return False
        return True

    async def command(self, text: str) -> bool:
        """A message from `who_cmd_topic`: one of `COMMANDS` is answered with a push."""
        if text.strip().lower() not in COMMANDS:
            log.info("who: a message that is not %s; ignored", "/".join(COMMANDS))
            return False
        return await self.scan(requested=True)

    # ------------------------------------------------------- the command stream

    def start_commands(self) -> None:
        self.started_at = int(self.clock())

    def cmd_url(self) -> str:
        since = self.last_id if self.last_id is not None else str(self.started_at)
        return f"{self.ntfy_url}/{self.cmd_topic}/json?since={since}"

    async def subscribe_once(self) -> None:
        """One long-poll connection, read to its end."""
        stream = self.stream if self.stream is not None else notify_mod.http_stream
        async for line in stream(self.cmd_url()):
            try:
                event = json.loads(line) if line.strip() else None
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict) or event.get("event") != "message":
                continue
            msg_id = event.get("id")
            if isinstance(msg_id, str):
                if msg_id in self._seen:
                    continue
                self._seen.append(msg_id)
                self.last_id = msg_id
            when = event.get("time")
            if isinstance(when, (int, float)) and self.started_at and when < self.started_at:
                continue  # sent before this subscription: not a request now
            if isinstance(event.get("message"), str):
                await self.command(event["message"])

    async def watch_commands(self) -> None:
        failures = 0
        while True:
            try:
                await self.subscribe_once()
                failures = 0
                why = "the stream ended"
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                why = f"{type(exc).__name__}: {exc}"
            delay = BACKOFF_S[min(failures, len(BACKOFF_S) - 1)]
            failures += 1
            log.warning("who: command stream: %s; reconnecting in %.0f s", why, delay)
            await self.sleep(delay)

    async def run(self) -> None:
        """Push the first picture, then scan every `interval` seconds, forever."""
        task: asyncio.Task[None] | None = None
        if self.cmd_topic:
            self.start_commands()
            task = asyncio.create_task(self.watch_commands(), name="hands-who-commands")
        else:
            log.info("who: no who_cmd_topic; pushing on change only")
        try:
            while True:
                try:
                    await self.scan()
                except Exception:  # a scan that fails must not end the view
                    log.exception("who: scan failed")
                await self.sleep(self.interval)
        finally:
            if task is not None:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task


def watch(config: Config, socket_path: Path) -> int:
    """`hands who --daemon` / `handswho`: run the pusher until interrupted."""
    notify = config.notify
    if not notify.who_topic:
        raise WhoError(
            f"{config.path}: [notify] who_topic is not set, so there is nowhere to push "
            "the who view (§24); set it to a long random topic, or run `hands who` to "
            "print the picture once"
        )
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    pusher = WhoPusher(
        sources_for(config, socket_path),
        topic=notify.who_topic,
        cmd_topic=notify.who_cmd_topic,
        ntfy_url=notify.ntfy_url,
    )
    try:
        asyncio.run(pusher.run())
    except KeyboardInterrupt:  # pragma: no cover - a human stopping it
        pass
    return 0


def main(
    argv: list[str] | None = None, *, stdout: TextIO | None = None, stderr: TextIO | None = None
) -> int:
    """The `handswho` console script: `hands who --daemon` under its own name."""
    err = sys.stderr if stderr is None else stderr
    parser = argparse.ArgumentParser(
        prog="handswho",
        description=(
            "Push the `hands who` picture to [notify] who_topic when it changes, and "
            f"when {', '.join(COMMANDS)} arrives on who_cmd_topic (DESIGN §24)."
        ),
    )
    parser.add_argument(
        "--project",
        help="project named by ~/.hands/<project>.toml (default: $HANDS_PROJECT, "
        "or the only config there is)",
    )
    parser.add_argument("--socket", help="override server.socket from the config")
    args = parser.parse_args(argv)
    try:
        config = load_config(resolve_project(args.project))
        socket_path = Path(args.socket).expanduser() if args.socket else config.server.socket
        return watch(config, socket_path)
    except (ConfigError, ValueError) as exc:
        print(f"handswho: {exc}", file=err)
        return 1
