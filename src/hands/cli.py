"""The `hands` command. U0 stub: `--help` only; the command surface (DESIGN §4) lands later."""

import argparse
from collections.abc import Sequence

from hands import __version__


def build_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        prog="hands",
        description=(
            "hands — dispatch prompts to headless Claude Code roles, monitor them, "
            "and chain pre-planned steps by a playbook."
        ),
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    parser.add_argument("--version", action="version", version=f"hands {__version__}")
    parser.parse_args(argv)
    # No commands yet (DESIGN §4 arrives with the daemon/API unit).
    parser.print_help()
    return 0
