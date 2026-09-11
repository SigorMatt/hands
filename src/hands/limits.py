"""Limits — detect one, wait it out, resume by itself (DESIGN §6, §11).

§6 is "automatic, no nudge": every party shares one subscription, so the human
is limited exactly when the builder is and there is nobody useful to ask. hands
therefore reads the reset time out of the notice, sleeps until it, and re-sends.

Three separable pieces, so each is testable on its own:

* `is_limit_notice` — is this `result` text a limit notice? (the runner's other
  signal, the `system`/`api_retry` event, is unambiguous and lives there);
* `parse_reset_at` — the reset time, or None. Defensive by construction: an
  unparseable shape, a time in the past and a time further ahead than any
  subscription window all return None, and the caller falls back to
  `limits.backoff_minutes`. The raw notice is stored whatever this returns;
* `LimitManager` — the scheduler: one `limit` event, a resume at reset + 60 s,
  one `resume` event, and a `stop` once `limits.max_resumes` consecutive resumes
  have gone by without a `done`.

Evidence for the notice shapes (claude 2.1.268, read out of the installed
binary): the wait banner is built by

    function gS(l,f){return"Usage limit reached \\xB7 continuing automatically "
      +MS(l,f)+" \\xB7 esc or type to cancel"}
    function MS(l,f){…return y?`at ${y}`:"shortly"}

and its time `y` is `toLocaleTimeString("en-US",{hour:"numeric",minute:…,
hour12:!0})` lowercased — `at 3pm`, `at 3:45pm` — or, past 24 hours,
`toLocaleString` with `{month:"short",day:"numeric",…}` — `at Sep 12, 3pm` —
each optionally followed by ` (<zone>)`. Those, ISO timestamps and "in N
minutes" are the shapes parsed here; anything else is honestly unparseable.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import re
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from hands.config import Config
from hands.spool import Job, Spool

__all__ = [
    "MAX_AHEAD",
    "RESUME_GRACE_S",
    "RESUME_ORIGIN",
    "LimitManager",
    "from_iso",
    "is_limit_notice",
    "parse_reset_at",
    "resume_delay_s",
    "to_iso",
]

log = logging.getLogger("hands.limits")

#: §6: "parses the reset time, sleeps until then". The minute is the brief's:
#: a reset is a wall-clock boundary and hitting it to the second buys nothing.
RESUME_GRACE_S = 60.0

#: A reset further ahead than this is not believed. Seven days is the longest
#: window a subscription has (the weekly limit), so anything beyond it is a
#: misparse, and a misparse must cost `backoff_minutes`, not a week.
MAX_AHEAD = timedelta(days=7)

#: §6's origin vocabulary is `driver|playbook|cli|limit`, and a limit resume is
#: the fourth: not a client asking for work but hands resuming itself after a
#: reset (H-004). `resumed_from` is unchanged — it still says which job this one
#: resumes; `origin` now says who asked, and no playbook rule did.
RESUME_ORIGIN = "limit"


# ------------------------------------------------------------ the notice

# Kept deliberately tight: a false positive marks an ordinary `done` job
# `limited` and spends a resume on it, so prose *about* limits ("add rate
# limiting", "the limit of that function") must not match. Every alternative
# needs a word that says the limit was *hit*, or that it will *reset*.
_NOTICE_PATTERNS: tuple[str, ...] = (
    r"usage limit reached",
    r"\brate[ _-]?limit(?:ed)?\b[^\n]{0,30}?\b(?:reached|exceeded|hit|retry)\b",
    r"\b(?:hit|reached|exceeded)\b[^\n]{0,20}?"
    r"\b(?:usage|rate|session|weekly|daily|opus|sonnet|plan)\s+limits?\b",
    r"\blimits?\s+(?:will\s+)?resets?\s+(?:at|in|on)\b",
)
_NOTICE_RE = re.compile("|".join(_NOTICE_PATTERNS), re.IGNORECASE)


def is_limit_notice(text: str | None) -> bool:
    """Does this `result` text say the run ended on a usage limit (§6)?"""
    if not text:
        return False
    return _NOTICE_RE.search(text) is not None


# ------------------------------------------------------- the reset time

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}  # fmt: skip

_ISO_RE = re.compile(
    r"\b(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})(?::(\d{2}))?(?:\.\d+)?\s*"
    r"(Z|[+-]\d{2}:?\d{2})?",
    re.IGNORECASE,
)
# "Sep 12, 3pm" / "Sep 12, 2026, 3:45pm". The am/pm is required: without it the
# year of "Sep 12, 2026" reads as an hour, and a confident wrong answer is worse
# than a fallback to `backoff_minutes`.
_MONTH_RE = re.compile(
    r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(\d{1,2})"
    r"(?:,?\s*(\d{4}))?,?\s*(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*([ap])\.?m\.?\b",
    re.IGNORECASE,
)
_REL_RE = re.compile(
    r"\bin\s+(\d+(?:\.\d+)?)\s*(second|sec|minute|min|hour|hr)s?\b", re.IGNORECASE
)
# A bare clock needs a cue word, or every stray number is a reset time.
_CLOCK12_RE = re.compile(
    r"\b(?:at|by|until|after)\s+(\d{1,2})(?::(\d{2}))?\s*([ap])\.?m\.?\b", re.IGNORECASE
)
_CLOCK24_RE = re.compile(r"\b(?:at|by|until|after)\s+(\d{1,2}):(\d{2})\b")
_ZONE_RE = re.compile(r"\(([A-Za-z][A-Za-z0-9_+/-]*)\)")
_UTC_RE = re.compile(r"\b(?:UTC|GMT)\b", re.IGNORECASE)

_UNIT_SECONDS = {"second": 1, "sec": 1, "minute": 60, "min": 60, "hour": 3600, "hr": 3600}


def local_now() -> datetime:
    """Now, aware, in this machine's timezone — the clock every default uses."""
    return datetime.now().astimezone()


def parse_reset_at(text: str | None, *, now: datetime | None = None) -> datetime | None:
    """The moment a limit notice says the limit resets, or None (§6).

    `now` is injected rather than read, so the rule for a bare clock time is
    testable: a time with no date means *the next occurrence* of that time, and a
    time with no zone means the zone of `now` (this machine's, in production)
    unless the notice names one in parentheses or says UTC.

    None means "no usable reset time": unparseable, already past, or further than
    `MAX_AHEAD` ahead. The caller then waits `limits.backoff_minutes`. The text
    itself is never modified — this function only reads.
    """
    if not text:
        return None
    reference = local_now() if now is None else now
    zone = _zone_of(text, reference)
    for candidate in (
        _from_iso_text(text, zone),
        _from_month(text, zone, reference),
        _from_relative(text, reference),
        _from_clock(text, reference, zone),
    ):
        if candidate is None:
            continue
        if candidate <= reference or candidate > reference + MAX_AHEAD:
            return None  # absurd: the notice parsed, but not into a time to wait for
        return candidate
    return None


def _zone_of(text: str, reference: datetime) -> Any:
    """The zone a naive time in `text` is in: a named one, UTC, or `reference`'s."""
    match = _ZONE_RE.search(text)
    if match is not None:
        try:
            return ZoneInfo(match.group(1))
        except (KeyError, ValueError, OSError):
            pass  # "(PDT)" and friends are not zone keys; fall through
    if _UTC_RE.search(text):
        return UTC
    return reference.tzinfo


def _from_iso_text(text: str, zone: Any) -> datetime | None:
    match = _ISO_RE.search(text)
    if match is None:
        return None
    year, month, day, hour, minute, second, offset = match.groups()
    try:
        naive = datetime(
            int(year), int(month), int(day), int(hour), int(minute), int(second or 0)
        )
    except ValueError:
        return None
    if offset is None:
        return naive.replace(tzinfo=zone)
    if offset.upper() == "Z":
        return naive.replace(tzinfo=UTC)
    sign = 1 if offset[0] == "+" else -1
    digits = offset[1:].replace(":", "")
    delta = timedelta(hours=int(digits[:2]), minutes=int(digits[2:]))
    return naive.replace(tzinfo=UTC) - sign * delta


def _from_month(text: str, zone: Any, reference: datetime) -> datetime | None:
    match = _MONTH_RE.search(text)
    if match is None:
        return None
    name, day, year, hour, minute, half = match.groups()
    clock = _twelve_hour(hour, minute, half)
    if clock is None:
        return None
    # No year in the notice means this one: the binary only prints a year when it
    # differs from the current one.
    try:
        return datetime(
            int(year) if year else reference.year,
            _MONTHS[name[:3].lower()],
            int(day),
            clock[0],
            clock[1],
            tzinfo=zone,
        )
    except ValueError:
        return None


def _from_relative(text: str, reference: datetime) -> datetime | None:
    match = _REL_RE.search(text)
    if match is None:
        return None
    unit = _UNIT_SECONDS[match.group(2).lower()]
    return reference + timedelta(seconds=float(match.group(1)) * unit)


def _from_clock(text: str, reference: datetime, zone: Any) -> datetime | None:
    match = _CLOCK12_RE.search(text)
    if match is not None:
        clock = _twelve_hour(*match.groups())
    else:
        match = _CLOCK24_RE.search(text)
        if match is None:
            return None
        hour, minute = int(match.group(1)), int(match.group(2))
        clock = (hour, minute) if hour <= 23 and minute <= 59 else None
    if clock is None:
        return None
    local = reference.astimezone(zone)
    candidate = local.replace(hour=clock[0], minute=clock[1], second=0, microsecond=0)
    if candidate <= reference:
        candidate += timedelta(days=1)  # no date means the next occurrence
    return candidate


def _twelve_hour(hour: str, minute: str | None, half: str) -> tuple[int, int] | None:
    value, minutes = int(hour), int(minute or 0)
    if not 1 <= value <= 12 or minutes > 59:
        return None
    if half.lower() == "p" and value != 12:
        value += 12
    elif half.lower() == "a" and value == 12:
        value = 0
    return value, minutes


# ---------------------------------------------------------------- ISO text


def to_iso(moment: datetime | None) -> str | None:
    """A moment as the spool spells time (UTC, millisecond, `Z`), or None."""
    if moment is None:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def from_iso(text: str | None) -> datetime | None:
    """Read back a `to_iso` string (or any ISO one). Naive text is read as UTC."""
    if not text:
        return None
    try:
        moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)


# ------------------------------------------------------------- scheduling


def resume_delay_s(job: Job, *, backoff_minutes: float, now: datetime | None = None) -> float:
    """Seconds to wait before resuming a `limited` job (§6).

    The parsed reset time plus `RESUME_GRACE_S`, or `backoff_minutes` when the
    notice gave none. A reset already behind us (a daemon restart, say) is not a
    reason to wait out the backoff: the grace is enough.
    """
    reset = from_iso((job.limit or {}).get("reset_at"))
    if reset is None:
        return float(backoff_minutes) * 60.0
    reference = local_now() if now is None else now
    return max(0.0, (reset - reference).total_seconds()) + RESUME_GRACE_S


class LimitManager:
    """Waits out limits and resumes the role by itself (§6, §11).

    The daemon owns one of these and hands it every finished job. Nothing here
    sleeps in a way a test cannot see: `clock` and `sleep` are injected, and the
    scheduled delay is what `sleep` is called with.
    """

    def __init__(
        self,
        config: Config,
        spool: Spool,
        *,
        enqueue: Callable[..., Awaitable[Job]],
        clock: Callable[[], datetime] | None = None,
        sleep: Callable[[float], Awaitable[None]] | None = None,
        max_resumes: int | None = None,
        on_stop: Callable[[str, dict[str, Any]], Any] | None = None,
    ) -> None:
        self.config = config
        self.spool = spool
        #: Creates the resume job. The daemon passes its own `enqueue`, so a
        #: resume takes the role's queue like any other send.
        self.enqueue = enqueue
        self.clock = clock or local_now
        self.sleep: Callable[[float], Awaitable[None]] = sleep or asyncio.sleep
        #: §6's `limits.max_resumes`, held as a value and not a constant because
        #: §10 lets a playbook override it.
        self.max_resumes = config.limits.max_resumes if max_resumes is None else max_resumes
        #: The U7 seam: called with (reason, payload) when hands gives up on a
        #: role. The `stop` inbox event is written either way (§11); the playbook
        #: engine hangs its own rule evaluation here.
        self.on_stop = on_stop
        self._tasks: set[asyncio.Task[None]] = set()

    # --------------------------------------------------------------- hooks

    async def on_job_finished(self, job: Job) -> None:
        """Every terminal job passes through here (§6)."""
        if job.state == "done":
            # "consecutive resumes without a terminal `done`" — this is the reset.
            if self.spool.read_role(job.role).consecutive_resumes:
                self.spool.update_role(job.role, consecutive_resumes=0)
            return
        if job.state == "limited":
            await self.on_limited(job)

    async def on_limited(self, job: Job) -> None:
        """One inbox event for the limit, then a scheduled resume or a stop (§6)."""
        limit = job.limit or {}
        resumes = self.spool.read_role(job.role).consecutive_resumes
        delay = resume_delay_s(
            job, now=self.clock(), backoff_minutes=self.config.limits.backoff_minutes
        )
        will_resume = resumes < self.max_resumes
        self.spool.append_event(
            "limit",
            {
                "job": job.id,
                "role": job.role,
                "category": limit.get("category"),
                "message": limit.get("message"),  # the raw notice, never normalised
                "reset_at": limit.get("reset_at"),
                "resume_at": to_iso(self.clock() + timedelta(seconds=delay))
                if will_resume
                else None,
                "resumes": resumes,
                "max_resumes": self.max_resumes,
            },
        )
        if not will_resume:
            await self.stop(
                f"limits.max_resumes reached: {job.role} has been resumed {resumes} "
                f"time(s) with no `done` in between and is limited again",
                {"role": job.role, "job": job.id, "resumes": resumes},
            )
            return
        task = asyncio.create_task(
            self._resume_after(job, delay), name=f"hands-resume-{job.role}"
        )
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    def pending_resumes(self) -> list[Job]:
        """`limited` jobs whose resume never happened (§6, and the daemon of §3).

        A resume is a task in the daemon's process: if the daemon dies between the
        limit and the reset, the resume dies with it and the role is stuck. The
        spool still holds the evidence — a `limited` job that is the *newest* job
        of its role. Anything newer (the resume itself, or work a human sent in
        the meantime) means nothing is owed.
        """
        newest: dict[str, Job] = {}
        limited: dict[str, Job] = {}
        for job in self.spool.list_jobs():  # oldest id first
            newest[job.role] = job
            if job.state == "limited":
                limited[job.role] = job
        return [job for role, job in limited.items() if newest[role].id == job.id]

    async def reschedule_pending(self) -> list[Job]:
        """Re-arm the resumes a dead daemon owed. Called once, at startup (§3, §6).

        No second `limit` event is written: the limit was recorded when it
        happened and this is the same resume, late. A reset that passed while the
        daemon was down is due now — `resume_delay_s` floors at the grace.
        """
        owed: list[Job] = []
        for job in self.pending_resumes():
            resumes = self.spool.read_role(job.role).consecutive_resumes
            if resumes >= self.max_resumes:
                log.info("job %s: not rescheduling; %s is at max_resumes", job.id, job.role)
                continue
            delay = resume_delay_s(
                job, now=self.clock(), backoff_minutes=self.config.limits.backoff_minutes
            )
            log.info("job %s: re-scheduling the resume this daemon owes in %.0fs", job.id, delay)
            task = asyncio.create_task(
                self._resume_after(job, delay), name=f"hands-resume-{job.role}"
            )
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)
            owed.append(job)
        return owed

    async def stop(self, reason: str, payload: dict[str, Any]) -> None:
        """Give up on a role: a `stop` event (§11) and the U7 seam, nothing else."""
        self.spool.append_event("stop", {**payload, "reason": reason})
        log.warning("stop: %s", reason)
        if self.on_stop is None:
            return
        outcome = self.on_stop(reason, payload)
        if inspect.isawaitable(outcome):
            await outcome

    # ---------------------------------------------------------- the resume

    async def _resume_after(self, job: Job, delay: float) -> None:
        try:
            await self.sleep(delay)
            await self._resume(job)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # a full queue, a bad role, a broken spool file
            log.exception("job %s: the limit resume failed", job.id)
            await self.stop(
                f"could not resume {job.role} after its limit: {exc}",
                {"role": job.role, "job": job.id},
            )

    async def _resume(self, job: Job) -> Job:
        """§6: the builder gets a new `clear` job — `role.resume_line` when the config
        sets one, otherwise the limited job's own prompt (H-008); aux the same prompt."""
        role = self.config.role(job.role)
        if job.role == "builder":
            prompt, context = role.resume_prompt(job.prompt), "clear"
        else:
            prompt, context = job.prompt, job.context
        resumed = await self.enqueue(
            role=job.role,
            context=context,
            prompt=prompt,
            origin=RESUME_ORIGIN,
            resumed_from=job.id,
        )
        count = self.spool.read_role(job.role).consecutive_resumes + 1
        self.spool.update_role(job.role, consecutive_resumes=count)
        self.spool.append_event(
            "resume",
            {
                "job": resumed.id,
                "role": job.role,
                "resumed_from": job.id,
                "context": context,
                "origin": RESUME_ORIGIN,
                "resumes": count,
                "max_resumes": self.max_resumes,
            },
        )
        log.info("job %s: resumed %s as %s (%d/%d)", job.id, job.role, resumed.id,
                 count, self.max_resumes)
        return resumed

    # ------------------------------------------------------------- tasks

    async def drain(self) -> None:
        """Wait for every scheduled resume to have happened. For tests and shutdown."""
        while True:
            pending = [task for task in self._tasks if not task.done()]
            if not pending:
                await asyncio.sleep(0)  # let the done callbacks empty the set
                return
            await asyncio.gather(*pending, return_exceptions=True)

    def cancel_all(self) -> None:
        """Drop every scheduled resume — the daemon is going down (§3)."""
        for task in list(self._tasks):
            task.cancel()
        self._tasks.clear()
