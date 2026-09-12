#!/usr/bin/env python3
"""claudewho — who is running what, for a human.

Joins three sources into one short summary and pushes it over ntfy whenever
it changes (and on request):

  * /proc            every `claude` process: interactive or headless (-p),
                     cwd (→ project), age, the shell command it is running
                     right now (its child), whether hands started it
  * hands            per configured project: running/queued/held jobs with
                     the first line of their prompt, pipeline state
  * transcripts      for interactive sessions: is it waiting for you or
                     working, and what the last human message was

Usage:
  claudewho.py --topic hands-5c3ea73c3f41-who [--cmd-topic ...] [--interval 20]
  claudewho.py --once            # print the summary and exit
  claudewho.py --selftest

Commands on the command topic (publish from the ntfy app): `status`.

Only short lines leave the machine: role, job id, a prompt's first 70
characters, a command's first 60. Nothing else. Both topics should be random.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

HOME = Path.home()
CLAUDE_PROJECTS = HOME / ".claude" / "projects"
HANDS_DIR = HOME / ".hands"
NTFY = os.environ.get("NTFY_URL", "https://ntfy.sh")
PROMPT_CHARS = 70
CMD_CHARS = 60


# ----------------------------------------------------------------- /proc

def _read(path: Path, default: str = "") -> str:
    try:
        return path.read_text(errors="replace")
    except OSError:
        return default


def _clk_tck() -> int:
    return os.sysconf("SC_CLK_TCK")


def _uptime() -> float:
    return float(_read(Path("/proc/uptime"), "0 0").split()[0])


def proc_table() -> dict[int, dict]:
    """pid -> {ppid, argv, cwd, comm, age_s}."""
    out = {}
    up = _uptime()
    tck = _clk_tck()
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        argv = _read(entry / "cmdline").split("\0")
        argv = [a for a in argv if a]
        if not argv:
            continue
        stat = _read(entry / "stat")
        try:
            after = stat[stat.rindex(")") + 2:].split()
            ppid = int(after[1])
            start_ticks = int(after[19])
            age = max(0.0, up - start_ticks / tck)
        except (ValueError, IndexError):
            ppid, age = 0, 0.0
        try:
            cwd = os.readlink(entry / "cwd")
        except OSError:
            cwd = ""
        out[pid] = {"ppid": ppid, "argv": argv, "cwd": cwd, "age_s": age,
                    "comm": _read(entry / "comm").strip()}
    return out


def is_claude(p: dict) -> bool:
    a0 = os.path.basename(p["argv"][0])
    return a0 == "claude" or (a0 in ("node", "bun") and len(p["argv"]) > 1
                              and os.path.basename(p["argv"][1]) == "claude")


def claude_processes(table: dict[int, dict]) -> list[dict]:
    """Top-level claude processes (a claude whose parent is not a claude)."""
    res = []
    for pid, p in table.items():
        if not is_claude(p):
            continue
        parent = table.get(p["ppid"])
        if parent and is_claude(parent):
            continue  # a child claude (nested), attributed to its parent
        argv = p["argv"]
        res.append({
            "pid": pid,
            "cwd": p["cwd"],
            "age_s": p["age_s"],
            "headless": "-p" in argv or "--print" in argv,
            "skip_perms": "--dangerously-skip-permissions" in argv,
            "resume": "--resume" in argv,
            "parent_comm": (parent or {}).get("comm", ""),
            "parent_argv": (parent or {}).get("argv", []),
        })
    return res


def descendants(table: dict[int, dict], root: int) -> list[int]:
    kids = {}
    for pid, p in table.items():
        kids.setdefault(p["ppid"], []).append(pid)
    out, stack = [], [root]
    while stack:
        x = stack.pop()
        for k in kids.get(x, []):
            out.append(k)
            stack.append(k)
    return out


SHELLS = {"bash", "sh", "zsh", "dash"}


def clean_cmd(argv: list[str]) -> str:
    """`python -m pytest tests`, not `/x/.venv/bin/python -m pytest tests`."""
    argv = list(argv)
    argv = [os.path.basename(a) if i == 0 else a for i, a in enumerate(argv)]
    argv = [re.sub(r"^/home/[^/]+/[^ ]*/\.venv/bin/", "", a) for a in argv]
    argv[0] = re.sub(r"^python3(\.\d+)?$", "python", argv[0])
    if argv[0] == "python" and len(argv) > 1 and argv[1].endswith(".py"):
        argv[1] = os.path.basename(argv[1])
    return re.sub(r"\s+", " ", " ".join(argv)).strip()


def current_command(table: dict[int, dict], root: int) -> str | None:
    """The newest leaf command under a claude process, cleaned."""
    kids = child_commands(table, root, limit=1)
    return kids[0][0] if kids else None


# ----------------------------------------------------------------- hands

def hands_projects() -> list[str]:
    if not HANDS_DIR.is_dir():
        return []
    return sorted(p.stem for p in HANDS_DIR.glob("*.toml"))


def hands_json(project: str, *args: str) -> dict | None:
    try:
        r = subprocess.run(["hands", "--project", project, *args, "--json"],
                           capture_output=True, text=True, timeout=10)
        if r.returncode != 0 or not r.stdout.strip():
            return None
        return json.loads(r.stdout)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def hands_picture(project: str) -> dict | None:
    status = hands_json(project, "status")
    if status is None:
        return None
    pipeline = hands_json(project, "pipeline") or {}
    jobs = hands_json(project, "jobs", "-n", "8") or {}
    jl = jobs.get("jobs", jobs if isinstance(jobs, list) else [])
    live = [j for j in jl if j.get("state") in ("running", "queued", "held")]
    return {"status": status, "pipeline": pipeline, "jobs": live}


# ------------------------------------------------------------ transcripts

def dashed(cwd: str) -> str:
    return cwd.replace("/", "-")


def newest_transcript(cwd: str, not_older_than_s: float | None = None) -> Path | None:
    d = CLAUDE_PROJECTS / dashed(cwd)
    if not d.is_dir():
        return None
    files = [p for p in d.glob("*.jsonl") if p.is_file()]
    if not files:
        return None
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    f = files[0]
    if not_older_than_s is not None and time.time() - f.stat().st_mtime > not_older_than_s:
        return None
    return f


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


def transcript_state(path: Path) -> dict:
    """{'waiting': bool, 'last_prompt': str, 'idle_s': float}."""
    lines = _tail_lines(path)
    waiting = False
    last_prompt = ""
    last_type = None
    for raw in reversed(lines):
        try:
            e = json.loads(raw)
        except ValueError:
            continue
        t = e.get("type")
        if last_type is None and t in ("user", "assistant"):
            last_type = t
            msg = e.get("message") or {}
            content = msg.get("content")
            if t == "assistant":
                has_tool = isinstance(content, list) and any(
                    isinstance(c, dict) and c.get("type") == "tool_use" for c in content)
                waiting = not has_tool
        if t == "user" and not last_prompt:
            msg = e.get("message") or {}
            content = msg.get("content")
            text = None
            if isinstance(content, str):
                text = content
            elif isinstance(content, list):
                parts = [c.get("text", "") for c in content
                         if isinstance(c, dict) and c.get("type") == "text"]
                text = " ".join(parts) if parts else None
            if text and not text.startswith("<") and "tool_result" not in text[:20]:
                last_prompt = text
        if last_prompt and last_type:
            break
    idle = time.time() - path.stat().st_mtime
    return {"waiting": waiting, "last_prompt": last_prompt, "idle_s": idle}


# ------------------------------------------------------------- summary

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


def project_name(cwd: str, roles: dict[str, str]) -> str:
    for name, rcwd in roles.items():
        if cwd and (cwd == rcwd or cwd.startswith(rcwd.rstrip("/") + "/")):
            return name
    return os.path.basename(cwd.rstrip("/")) or cwd or "?"


NEEDS_YOU = {"stop", "job.held"}


def hands_inbox(project: str) -> list[dict]:
    r = hands_json(project, "inbox")
    if not r:
        return []
    return r.get("events", []) if isinstance(r, dict) else []


def child_commands(table: dict[int, dict], root: int, limit: int = 3) -> list[tuple[str, float]]:
    """Leaf commands under root: (command, age_s), newest first, shells and
    nested claude processes skipped."""
    out = []
    for pid in descendants(table, root):
        p = table[pid]
        if is_claude(p) or p["comm"] in SHELLS:
            continue
        if any(table[k]["ppid"] == pid and table[k]["comm"] not in SHELLS for k in descendants(table, pid)):
            continue  # not a leaf
        out.append((clean_cmd(p["argv"]), p["age_s"]))
    out.sort(key=lambda x: x[1])
    return out[:limit]


def session_state(p: dict, table: dict[int, dict]) -> tuple[str, str, dict | None]:
    """(state text, fingerprint value, transcript state or None)."""
    tp = newest_transcript(p["cwd"], not_older_than_s=p["age_s"] + 3600)
    ts = transcript_state(tp) if tp else None
    kids = child_commands(table, p["pid"])
    if ts is None:
        return ("state unknown", "?", None) if not kids else ("working", "work", None)
    if ts["waiting"]:
        return (f"waiting for you · {age(ts['idle_s'])} idle", "wait", ts)
    if kids:
        return ("working", "work", ts)
    return (f"thinking · {age(ts['idle_s'])} since last write", "think", ts)


def build_summary(table: dict[int, dict] | None = None) -> tuple[str, list[tuple[str, str]]]:
    """Returns (text, items). Text is a hierarchy: each root is a daemon or
    a session; under it the processes it owns; under those their children.
    Items are (key, value) pairs describing the set of things running, held
    or waiting; the caller fingerprints them. Ages, clocks and the command a
    running thing is executing right now are in the text, never in items."""
    table = table or proc_table()
    procs = claude_processes(table)
    items: list[tuple[str, str]] = []
    blocks: list[str] = []
    hands_pids: set[int] = set()
    role_cwds: dict[str, str] = {}
    inbox_by_project: dict[str, list[dict]] = {}

    for project in hands_projects():
        pic = hands_picture(project)
        if pic is None:
            blocks.append(f"handsd (daemon, project {project})\n    not answering")
            items.append((project, "down"))
            continue
        st = pic["status"]
        roles = st.get("roles", {})
        for r in roles.values():
            if r.get("cwd"):
                role_cwds[project] = r["cwd"]
        pl = pic["pipeline"] or {}
        if pl.get("paused"):
            pstate = "pipeline stopped"
            items.append((f"{project}:pipeline", "stopped"))
        else:
            pstate = "pipeline running" if any(r.get("running") for r in roles.values()) else "pipeline idle"
        rules = (pl.get("playbook") or {}).get("rules")
        head = f"handsd (daemon, project {project}) — {pstate}" + (f" · {rules} rules" if rules else "")
        lines = [head]
        if pl.get("paused"):
            lines.append(f"    reason: {short(pl.get('stop_reason') or 'paused', 60)}")
        for rname in sorted(roles, key=lambda n: (n != "builder", n)):
            r = roles[rname]
            run = r.get("running")
            queued = r.get("queued") or []
            if run:
                job = run if isinstance(run, dict) else {}
                run_id = job.get("id") or run
                job = {**next((j for j in pic["jobs"] if j.get("id") == run_id), {}), **job}
                pid = int(job["pid"]) if job.get("pid") else None
                if pid:
                    hands_pids.add(pid)
                a = age(table[pid]["age_s"]) if pid and pid in table else ""
                ptxt = job.get("prompt_line") or job.get("prompt") or ""
                lines.append(f"  role {rname} (job {run_id}, {a})" if a else f"  role {rname} (job {run_id})")
                if ptxt:
                    lines.append(f"      {short(ptxt.splitlines()[0], PROMPT_CHARS)}")
                if pid and pid in table:
                    for cmd, cage in child_commands(table, pid):
                        lines.append(f"    {short(cmd, CMD_CHARS)} (process, {age(cage)})")
                items.append((f"{project}:{rname}", f"run:{run_id}"))
            elif queued:
                lines.append(f"  role {rname} — {len(queued)} job{'s' if len(queued) != 1 else ''} queued")
                items.append((f"{project}:{rname}", f"q{len(queued)}"))
            else:
                lines.append(f"  role {rname} — no job")
                items.append((f"{project}:{rname}", "idle"))
        for j in [j for j in pic["jobs"] if j.get("state") == "held"]:
            reason = (j.get("gate") or {}).get("reason", "")
            lines.append(f"  held job {j.get('id')} ({j.get('role')}) — needs YOUR decision")
            if reason:
                lines.append(f"      {short(reason, 50)}")
            items.append((f"{project}:held:{j.get('id')}", "held"))
        unacked = (st.get("inbox") or {}).get("unacked", 0)
        if unacked:
            inbox_by_project[project] = hands_inbox(project)
            items.append((f"{project}:inbox", str(unacked)))
        blocks.append("\n".join(lines))

    other = [p for p in procs if p["pid"] not in hands_pids]
    for p in sorted(other, key=lambda x: ("hands-driver" not in x["cwd"], x["cwd"], x["pid"])):
        proj = project_name(p["cwd"], role_cwds)
        is_driver = "hands-driver" in p["cwd"]
        if is_driver:
            label = f"driver:{os.path.basename(p['cwd'])}"
        elif not p["headless"] and any(p["cwd"] == c for c in role_cwds.values()):
            label = f"{proj} (your session)"
        else:
            label = proj
        kind = "headless" if p["headless"] else "session"
        meta = [kind, age(p["age_s"])]
        if p["skip_perms"]:
            meta.append("skip-perms")
        state, val, ts = session_state(p, table)
        lines = [f"{label} ({', '.join(meta)}) — {state}"]
        if ts and ts["last_prompt"] and val != "work":
            lines.append(f"    last: {short(ts['last_prompt'], PROMPT_CHARS)}")
        kids = child_commands(table, p["pid"])
        for cmd, cage in kids:
            ptype = "background process" if val == "wait" else "process"
            lines.append(f"  {short(cmd, CMD_CHARS)} ({ptype}, {age(cage)})")
        if is_driver:
            proj_name = os.path.basename(p["cwd"])
            evs = inbox_by_project.get(proj_name)
            if evs:
                kinds = [e.get("kind", "?") for e in evs]
                need = [k for k in kinds if k in NEEDS_YOU]
                who = "needs YOU" if need else "informational, the driver acks it on its next check"
                lines.append(f"  inbox: {len(evs)} unread from handsd — {', '.join(sorted(set(kinds)))} — {who}")
        if is_driver or p["headless"]:
            items.append((f"s:{p['pid']}", val))  # your own sessions are shown, never fingerprinted
        blocks.append("\n".join(lines))

    for proj_name, evs in inbox_by_project.items():
        if not any(f"driver:{proj_name}" in b for b in blocks) and evs:
            kinds = sorted({e.get("kind", "?") for e in evs})
            blocks.append(f"inbox for a driver of {proj_name} (no driver session running)\n    {len(evs)} unread from handsd — {', '.join(kinds)}")

    if not blocks:
        blocks.append("nothing running")
    n = len(procs)
    head = time.strftime("%H:%M") + f" · {n} claude process{'es' if n != 1 else ''}"
    return head + "\n\n" + "\n\n".join(blocks), items


class Debounce:
    """Session states (keys starting with 's:') must hold for `hold` scans
    before they count; everything else counts at once."""

    def __init__(self, hold: int = 2):
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
        return hashlib.sha1("|".join(sorted(out)).encode()).hexdigest()


# ----------------------------------------------------------------- ntfy

def publish(topic: str, text: str, title: str = "claudewho") -> int:
    req = urllib.request.Request(f"{NTFY}/{topic}", data=text.encode("utf-8"),
                                 headers={"Title": title, "Content-Type": "text/plain; charset=utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status
    except Exception as e:  # noqa: BLE001
        print(f"publish failed: {e}", file=sys.stderr)
        return 0


def command_loop(cmd_topic: str, on_command) -> None:
    """Long-poll the command topic; call on_command(text) for each message."""
    since = "all"
    while True:
        try:
            url = f"{NTFY}/{cmd_topic}/json?since={since}&poll=0"
            with urllib.request.urlopen(url, timeout=None) as r:
                for raw in r:
                    try:
                        e = json.loads(raw.decode("utf-8"))
                    except ValueError:
                        continue
                    if e.get("event") != "message":
                        continue
                    since = e.get("id", since)
                    on_command((e.get("message") or "").strip().lower())
        except Exception as e:  # noqa: BLE001
            print(f"command stream: {e}; reconnecting", file=sys.stderr)
            time.sleep(5)


# ----------------------------------------------------------------- main

def selftest() -> int:
    import tempfile
    ok = True
    with tempfile.TemporaryDirectory() as d:
        t = Path(d) / "s.jsonl"
        t.write_text(
            json.dumps({"type": "user", "message": {"role": "user", "content": "Kick off mission 6: hands send …"}}) + "\n"
            + json.dumps({"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash"}]}}) + "\n"
            + json.dumps({"type": "user", "message": {"content": [{"type": "tool_result", "content": "x"}]}}) + "\n"
            + json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "VERDICT: mission 6 running"}]}}) + "\n")
        s = transcript_state(t)
        ok &= s["waiting"] is True and s["last_prompt"].startswith("Kick off mission 6")
        t.write_text(t.read_text() + json.dumps({"type": "user", "message": {"content": "check"}}) + "\n"
                     + json.dumps({"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash"}]}}) + "\n")
        s = transcript_state(t)
        ok &= s["waiting"] is False and s["last_prompt"] == "check"
    ok &= short("a" * 100, 10) == "a" * 9 + "…"
    ok &= age(45) == "45s" and age(3000) == "50m" and age(7200) == "2h00"
    table = {1: {"ppid": 0, "argv": ["init"], "cwd": "/", "age_s": 9e6, "comm": "init"},
             10: {"ppid": 1, "argv": ["claude", "-p"], "cwd": "/x", "age_s": 100, "comm": "claude"},
             11: {"ppid": 10, "argv": ["bash", "-c", "pytest"], "cwd": "/x", "age_s": 5, "comm": "bash"},
             12: {"ppid": 11, "argv": ["python", "-m", "pytest", "tests"], "cwd": "/x", "age_s": 4, "comm": "python"},
             13: {"ppid": 10, "argv": ["claude", "--resume", "abc"], "cwd": "/x", "age_s": 3, "comm": "claude"}}
    cp = claude_processes(table)
    ok &= [p["pid"] for p in cp] == [10] and cp[0]["headless"]
    ok &= current_command(table, 10) == "python -m pytest tests"
    d = Debounce(hold=2)
    f0 = d.fingerprint([("s:1", "wait"), ("hands:builder", "idle")])
    f1 = d.fingerprint([("s:1", "think"), ("hands:builder", "idle")])   # one scan: ignored
    f2 = d.fingerprint([("s:1", "think"), ("hands:builder", "idle")])   # held: counts
    f3 = d.fingerprint([("s:1", "think"), ("hands:builder", "run:x")])  # hands: at once
    ok &= f0 == f1 and f1 != f2 and f2 != f3
    print("selftest:", "ok" if ok else "FAIL")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic", help="ntfy topic to publish summaries to")
    ap.add_argument("--cmd-topic", help="ntfy topic to read commands from (status)")
    ap.add_argument("--interval", type=float, default=20.0, help="seconds between scans")
    ap.add_argument("--min-gap", type=float, default=60.0, help="min seconds between pushes")
    ap.add_argument("--heartbeat", type=float, default=6 * 3600, help="push unchanged summary every N seconds (0 = never)")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    deb = Debounce(hold=2)
    text, items = build_summary()
    fp = deb.fingerprint(items)
    if a.once or not a.topic:
        print(text)
        return 0

    state = {"fp": None, "last_push": 0.0, "force": False}
    lock = threading.Lock()

    def on_command(cmd: str) -> None:
        if cmd in ("status", "who", "check", "?"):
            with lock:
                state["force"] = True

    if a.cmd_topic:
        threading.Thread(target=command_loop, args=(a.cmd_topic, on_command), daemon=True).start()

    publish(a.topic, text, "claudewho started")
    state["fp"], state["last_push"] = fp, time.time()
    while True:
        time.sleep(a.interval)
        try:
            text, items = build_summary()
            fp = deb.fingerprint(items)
        except Exception as e:  # noqa: BLE001
            print(f"scan failed: {e}", file=sys.stderr)
            continue
        with lock:
            force, state["force"] = state["force"], False
        now = time.time()
        changed = fp != state["fp"] and now - state["last_push"] >= a.min_gap
        beat = a.heartbeat and now - state["last_push"] >= a.heartbeat
        if force or changed or beat:
            publish(a.topic, text, "claudewho" if not force else "claudewho (requested)")
            state["fp"], state["last_push"] = fp, now
    return 0


if __name__ == "__main__":
    sys.exit(main())
