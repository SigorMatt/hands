"""Files — the only way hands puts bytes on the machine (DESIGN §1 invariant 2, §4).

Three commands (`put`, `get`, `ls`) and one flag (`send --file path=content`),
all of them confined to `files.allowed_roots` by `spool.resolve_under_roots`,
and every write reported with its sha256: §1 invariant 2 is "files are moved
with sha256", so no write here is reported without one.

Nothing in this module decides *whether* a file may be written — that is the
roots, which come from the config. It only refuses to be the thing that leaves
them.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from hands.spool import PathEscape, resolve_under_roots

__all__ = [
    # re-exported so a caller of this module imports one module, not two
    "FileError",
    "PathEscape",
    "list_dir",
    "parse_file_specs",
    "put_file",
    "read_file",
    "sha256_of",
    "write_files",
]

Roots = Iterable[str | Path]


class FileError(Exception):
    """A file operation inside the roots could not be carried out."""


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _written(path: Path, data: bytes) -> dict[str, Any]:
    """The record of one moved file: path, sha256, bytes (§1 invariant 2)."""
    return {"path": str(path), "sha256": sha256_of(data), "bytes": len(data)}


def _write(path: Path, data: bytes) -> dict[str, Any]:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    except OSError as exc:
        raise FileError(f"cannot write {path}: {exc}") from exc
    return _written(path, data)


# ---------------------------------------------------------------------- put


def put_file(
    path: str, *, content: str | None, from_path: str | None, roots: Roots
) -> dict[str, Any]:
    """`hands put <path> --content … | --from <file>` → sha256 and bytes (§4).

    `--from` is resolved under the roots too: the daemon reads it, so an
    unconfined `--from` would turn `put` into a read-anything oracle.
    """
    if content is not None and from_path is not None:
        raise FileError("give --content or --from, not both")
    if content is None and from_path is None:
        raise FileError("hands put needs --content or --from <file>")
    target = resolve_under_roots(path, roots)
    if from_path is not None:
        source = resolve_under_roots(from_path, roots)
        try:
            data = source.read_bytes()
        except OSError as exc:
            raise FileError(f"cannot read {source}: {exc}") from exc
    else:
        data = (content or "").encode("utf-8")
    return _write(target, data)


# ---------------------------------------------------------------------- get


def read_file(path: str, *, roots: Roots) -> dict[str, Any]:
    """`hands get <path>` → the content (§4), with its sha256 and size."""
    resolved = resolve_under_roots(path, roots)
    try:
        data = resolved.read_bytes()
    except OSError as exc:
        raise FileError(f"cannot read {resolved}: {exc}") from exc
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise FileError(
            f"{resolved} is not UTF-8 text ({exc}); hands moves text, and the "
            "record it returns is JSON"
        ) from exc
    return {"path": str(resolved), "content": text, **_written(resolved, data)}


# ----------------------------------------------------------------------- ls


def list_dir(path: str, *, roots: Roots) -> dict[str, Any]:
    """`hands ls <path>` → entries (§4), name-sorted, one level."""
    resolved = resolve_under_roots(path, roots)
    if not resolved.is_dir():
        raise FileError(f"{resolved} is not a directory")
    entries: list[dict[str, Any]] = []
    try:
        children = sorted(resolved.iterdir(), key=lambda child: child.name)
    except OSError as exc:
        raise FileError(f"cannot list {resolved}: {exc}") from exc
    for child in children:
        kind = "dir" if child.is_dir() else "file" if child.is_file() else "other"
        entry: dict[str, Any] = {"name": child.name, "path": str(child), "type": kind}
        try:
            stat = child.stat()
        except OSError:  # a dangling symlink, or a file that vanished mid-listing
            entry["type"] = "other"
        else:
            entry["bytes"] = stat.st_size if kind == "file" else None
            entry["modified"] = (
                datetime.fromtimestamp(stat.st_mtime, UTC).strftime("%Y-%m-%dT%H:%M:%S") + "Z"
            )
        entries.append(entry)
    return {"path": str(resolved), "entries": entries}


# ------------------------------------------------------- send --file (§4, §6)


def parse_file_specs(specs: Sequence[str], *, roots: Roots) -> list[tuple[Path, bytes]]:
    """`--file path=content` → resolved (path, bytes) pairs, or raise.

    Every spec is parsed and confined before any of them is written, so a path
    outside the roots refuses the whole `send` rather than half-writing it.
    """
    pairs: list[tuple[Path, bytes]] = []
    for spec in specs:
        path, sep, content = spec.partition("=")
        if not sep or not path.strip():
            raise FileError(f"--file wants path=content, got {spec!r}")
        pairs.append((resolve_under_roots(path.strip(), roots), content.encode("utf-8")))
    return pairs


def write_files(specs: Sequence[str], *, roots: Roots) -> list[dict[str, Any]]:
    """Write every `--file` of a send, all-or-nothing on confinement (§4)."""
    return [_write(path, data) for path, data in parse_file_specs(specs, roots=roots)]
