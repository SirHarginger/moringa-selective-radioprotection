"""Provenance helpers: file hashing, manifest look-ups and write-once output folders.

Raw files are only ever opened for reading here. Output folders are written to a
``<name>.partial`` sibling and renamed into place only when complete, so a crashed
run never leaves a half-written folder under the final name, and an existing
folder is never overwritten.
"""

from __future__ import annotations

import hashlib
import json
import posixpath
import re
from collections.abc import Callable
from pathlib import Path

SHA256SUMS_LINE = re.compile(r"^([0-9a-f]{64}) [ *](?:\./)?(.+)$")


class ProvenanceError(RuntimeError):
    """Raised when an input does not match its recorded provenance."""


def file_sha256(path: Path) -> str:
    """Return the SHA-256 hex digest of a file, read in 1 MiB blocks."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def text_sha256(text: str) -> str:
    """Return the SHA-256 hex digest of UTF-8 text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def manifest_file_sha256(manifest: Path, file_path: str) -> str:
    """Return the ``sha256`` recorded for ``file_path`` in a YAML provenance manifest.

    Paths are compared after normalisation (``./data/raw/x`` equals ``data/raw/x``).
    """
    import yaml  # local import: only needed by callers that read manifests

    wanted = posixpath.normpath(file_path)
    data = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    for entry in data.get("files") or []:
        path = entry.get("path")
        if path and posixpath.normpath(str(path)) == wanted and entry.get("sha256"):
            return str(entry["sha256"])
    raise ProvenanceError(f"{manifest}: no sha256 recorded for {file_path}")


def verify_sha256(path: Path, expected: str) -> None:
    """Fail unless the file's SHA-256 equals ``expected``."""
    actual = file_sha256(path)
    if actual != expected:
        raise ProvenanceError(f"SHA-256 mismatch for {path}: {actual} != {expected}")


def listed_sha256(path: Path) -> str | None:
    """Return the digest recorded for a file in its folder's SHA256SUMS, if any."""
    sums = path.parent / "SHA256SUMS"
    if not sums.is_file():
        return None
    for line in sums.read_text(encoding="utf-8").splitlines():
        match = SHA256SUMS_LINE.match(line)  # text ("  name") and binary (" *name") modes
        if match and match.group(2) == path.name:
            return match.group(1)
    return None


def write_json(path: Path, data: object) -> None:
    """Write JSON with sorted keys and a trailing newline (deterministic bytes)."""
    path.write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )


def write_once_folder(final: Path, build: Callable[[Path], None]) -> None:
    """Create ``final`` by letting ``build`` fill a staging folder, then renaming it.

    Fails if ``final`` or the staging folder already exists. If ``build`` raises,
    the staging folder is left for inspection under its ``.partial`` name.
    """
    staging = final.with_name(final.name + ".partial")
    if final.exists():
        raise FileExistsError(f"{final} exists; choose a new output folder")
    if staging.exists():
        raise FileExistsError(f"{staging} exists from an earlier failed run; inspect and delete it")
    staging.mkdir(parents=True)
    build(staging)
    staging.rename(final)
