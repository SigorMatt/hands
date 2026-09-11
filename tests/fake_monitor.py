#!/usr/bin/env python3
"""A stand-in for the ops repo's monitor script (DESIGN §5, §14), so no test
needs the real `watch_monitor.sh`.

It imitates the contract §5 gives that script: it is long-lived, it takes
`--pids`, `--transcript` and `--base`, and it writes blank-line-separated event
blocks to stdout as they happen, flushing each one.

Environment (a test sets what it needs; everything is optional):

    HANDS_FAKE_MONITOR_ARGV   write the parsed flags, the cwd and this pid
                              there as JSON, before emitting anything
    HANDS_FAKE_MONITOR_GO     wait for this path to exist between the first
                              block and the rest, so a test can prove hands
                              files blocks as they arrive and not at exit
    HANDS_FAKE_MONITOR_EXIT   exit with this code after the last block instead
                              of idling until it is killed
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from typing import Any

FIRST = "STALL builder has not moved in 40m\n  last commit deadbee\n  no cpu"
SECOND = "TRIPWIRE deadbee landed on main"
THIRD = "noise the ops script felt like printing"
FAREWELL = "EVENT the monitor was asked to stop"


def emit(block: str) -> None:
    sys.stdout.write(block + "\n\n")
    sys.stdout.flush()


def _on_term(signum: int, frame: Any) -> None:
    emit(FAREWELL)
    sys.exit(0)


def main() -> int:
    parser = argparse.ArgumentParser(prog="fake_monitor")
    parser.add_argument("--pids", required=True)
    parser.add_argument("--transcript", required=True)
    parser.add_argument("--base", required=True)
    args = parser.parse_args()

    record = os.environ.get("HANDS_FAKE_MONITOR_ARGV")
    if record:
        with open(record, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "pids": args.pids,
                    "transcript": args.transcript,
                    "base": args.base,
                    "cwd": os.getcwd(),
                    "pid": os.getpid(),
                },
                handle,
            )

    signal.signal(signal.SIGTERM, _on_term)

    emit(FIRST)
    gate = os.environ.get("HANDS_FAKE_MONITOR_GO")
    if gate:
        while not os.path.exists(gate):
            time.sleep(0.02)
    emit(SECOND)
    emit(THIRD)

    code = os.environ.get("HANDS_FAKE_MONITOR_EXIT")
    if code:
        sys.stderr.write("fake monitor is giving up\n")
        sys.stderr.flush()
        return int(code)
    while True:  # long-lived, like the real one: it ends when hands kills it
        time.sleep(0.05)


if __name__ == "__main__":
    raise SystemExit(main())
