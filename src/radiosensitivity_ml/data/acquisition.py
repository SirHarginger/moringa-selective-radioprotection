"""Download and verify fixed public source files (DepMap 24Q4 and optional extras).

Same integrity rules as the reviewed shell script it replaces:
- each file is streamed to ``<dest>.part``; MD5 (where published), size, file signature
  and an HTML check are verified BEFORE the file is renamed into place, so a failed or
  "bot check" response never becomes a raw file;
- an existing file is never overwritten; it is re-verified instead;
- a stale ``.part`` from an interrupted run is discarded and the download restarts
  (``.part`` files are never trusted), so re-running after an interruption is safe;
- accepted files are made read-only;
- one log line per download (source URL, final URL, HTTP status, size, path, expected
  MD5, observed MD5, observed SHA-256) goes to ``results/logs/phase_01/acquisition_log.tsv``,
  outside data/raw;
- each folder gets a write-once, read-only ``SHA256SUMS``; later runs verify it.

File IDs, sizes and MD5s: figshare API, article 27993248 (DepMap 24Q4, CC BY 4.0) and
24667905 v1 (23Q4), re-checked 2026-10-21.
"""

from __future__ import annotations

import hashlib
import os
import stat
import urllib.request
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from radiosensitivity_ml.data.provenance import SHA256SUMS_LINE

FIGSHARE = "https://ndownloader.figshare.com/files/"
LOG_PATH = Path("results/logs/phase_01/acquisition_log.tsv")
LOG_HEADER = (
    "utc_time\tsource_url\tfinal_url\thttp_status\tsize_bytes\tpath\t"
    "expected_md5\tobserved_md5\tobserved_sha256\n"
)
CHUNK = 1 << 20


class AcquisitionError(RuntimeError):
    """Raised when a download or an existing file fails verification."""


@dataclass(frozen=True)
class RemoteFile:
    """One file to acquire, with whatever the publisher states about it."""

    url: str
    dest: Path
    md5: str | None = None
    size: int | None = None
    magic: bytes | None = None  # expected leading bytes (e.g. b"PK\x03\x04" for xlsx)


def depmap(file_id: int, folder: str, name: str, md5: str, size: int) -> RemoteFile:
    """A DepMap figshare file."""
    return RemoteFile(f"{FIGSHARE}{file_id}", Path(folder) / name, md5, size)


D24 = "data/raw/depmap/24q4"
SOURCES: dict[str, tuple[RemoteFile, ...]] = {
    # Default: the five DepMap 24Q4 core files (uncorrected expression = primary input).
    "depmap_24q4": (
        depmap(51065795, D24, "README.txt", "54628c15a10b9ff6536db245cfed5231", 43103),
        depmap(51065297, D24, "Model.csv", "675210d17675f3517b0ce39a3c274f16", 645696),
        depmap(51065723, D24, "OmicsProfiles.csv", "7195088a5fc41eddb3f896c6e984a992", 254733),
        depmap(
            51065339,
            D24,
            "OmicsDefaultModelProfiles.csv",
            "4d342a03701c0a4c0742fedb56c1de40",
            90080,
        ),
        depmap(
            51065489,
            D24,
            "OmicsExpressionProteinCodingGenesTPMLogp1.csv",
            "71794802b750ce77c422dad0720a40af",
            506628654,
        ),
    ),
    # Default: MSigDB Hallmark gene sets (CC BY 4.0; no published checksum, so the
    # observed SHA-256 is recorded in the log and SHA256SUMS; HTML pages are rejected).
    "msigdb_hallmark": (
        RemoteFile(
            "https://data.broadinstitute.org/gsea-msigdb/msigdb/release/2025.1.Hs/"
            "h.all.v2025.1.Hs.symbols.gmt",
            Path("data/raw/msigdb/2025.1.Hs/h.all.v2025.1.Hs.symbols.gmt"),
        ),
    ),
    # Optional: sensitivity input only, kept in its own folder.
    "depmap_24q4_batch_corrected": (
        depmap(
            51065492,
            "data/raw/depmap/24q4_sensitivity",
            "OmicsExpressionProteinCodingGenesTPMLogp1BatchCorrected.csv",
            "afefd19098154a62972eb975a55a36c9",
            616166707,
        ),
    ),
    # Optional: identity-drift audit only.
    "depmap_23q4_audit": (
        depmap(
            43346895,
            "data/raw/depmap/23q4_v1",
            "Model.csv",
            "c14f90f02609b9507c8b31e6d5db309b",
            582229,
        ),
    ),
    # Optional, secondary: Yard 2016 supplements (no published checksums; signature only).
    "yard2016": (
        RemoteFile(
            "https://pmc.ncbi.nlm.nih.gov/articles/instance/4848553/bin/ncomms11428-s2.xlsx",
            Path("data/raw/yard2016/ncomms11428_v1/ncomms11428-s2.xlsx"),
            magic=b"PK\x03\x04",
        ),
        RemoteFile(
            "https://pmc.ncbi.nlm.nih.gov/articles/instance/4848553/bin/ncomms11428-s1.pdf",
            Path("data/raw/yard2016/ncomms11428_v1/ncomms11428-s1.pdf"),
            magic=b"%PDF",
        ),
    ),
}

Opener = Callable[[str], object]  # returns a context manager with .read(n), .status, .geturl()


def default_opener(url: str) -> object:
    """Open a URL with a project user agent."""
    request = urllib.request.Request(url, headers={"User-Agent": "explainable-radiosensitivity-ml"})
    return urllib.request.urlopen(request, timeout=300)  # fixed https publisher hosts


def file_digests(path: Path) -> tuple[str, str, int]:
    """(MD5, SHA-256, size) of a file."""
    md5, sha = hashlib.md5(), hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(CHUNK), b""):
            md5.update(block)
            sha.update(block)
            size += len(block)
    return md5.hexdigest(), sha.hexdigest(), size


def check(remote: RemoteFile, path: Path) -> tuple[str, str, int]:
    """Verify a file against everything published about it; return its digests."""
    md5, sha, size = file_digests(path)
    if remote.md5 and md5 != remote.md5:
        raise AcquisitionError(f"MD5 mismatch for {path}: {md5} != {remote.md5}")
    if remote.size is not None and size != remote.size:
        raise AcquisitionError(f"size mismatch for {path}: {size} != {remote.size} bytes")
    with path.open("rb") as handle:
        head = handle.read(4096)
    if remote.magic and not head.startswith(remote.magic):
        raise AcquisitionError(f"unexpected content in {path} (wrong file signature)")
    if b"<html" in head.lower() or b"<!doctype html" in head.lower():
        raise AcquisitionError(f"{path} looks like an HTML error or block page")
    return md5, sha, size


def make_read_only(path: Path) -> None:
    """Remove all write permission bits."""
    mode = path.stat().st_mode
    os.chmod(path, mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))


def acquire(remote: RemoteFile, opener: Opener = default_opener, log: Path = LOG_PATH) -> str:
    """Download one file safely, or verify it if it already exists.

    Returns "downloaded" or "verified_existing". Raises AcquisitionError on any failure;
    the final path is then left untouched (a failed download stays as ``.part``).
    """
    if remote.dest.exists():
        try:
            check(remote, remote.dest)
        except AcquisitionError as exc:
            raise AcquisitionError(
                f"{exc}. The existing file was NOT overwritten: move it aside and re-run."
            ) from exc
        make_read_only(remote.dest)  # repairs an interruption between rename and chmod
        return "verified_existing"
    remote.dest.parent.mkdir(parents=True, exist_ok=True)
    part = remote.dest.with_name(remote.dest.name + ".part")
    if part.exists():
        part.unlink()  # never resume from an untrusted partial file
    with opener(remote.url) as response, part.open("wb") as handle:  # type: ignore[attr-defined]
        status = getattr(response, "status", None)
        final_url = response.geturl() if hasattr(response, "geturl") else remote.url
        if status not in (None, 200):
            raise AcquisitionError(f"HTTP {status} for {remote.url}")
        for block in iter(lambda: response.read(CHUNK), b""):
            handle.write(block)
    md5, sha, size = check(remote, part)
    part.rename(remote.dest)
    make_read_only(remote.dest)
    log.parent.mkdir(parents=True, exist_ok=True)
    new_log = not log.exists()
    with log.open("a", encoding="utf-8", newline="\n") as handle:
        if new_log:
            handle.write(LOG_HEADER)
        fields = [
            datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            remote.url,
            str(final_url),
            str(status),
            str(size),
            str(remote.dest),
            remote.md5 or "none_published",
            md5,
            sha,
        ]
        handle.write("\t".join(fields) + "\n")
    return "downloaded"


def sha256sums(folder: Path, names: Iterable[str]) -> str:
    """Write ``SHA256SUMS`` for the named files once (read-only); afterwards verify it.

    Returns "written" or "verified". A later file not listed in an existing SHA256SUMS
    raises, so a folder's checksum list can never silently go stale.
    """
    path = folder / "SHA256SUMS"
    digests = {name: file_digests(folder / name)[1] for name in sorted(names)}
    if path.exists():
        listed = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            match = SHA256SUMS_LINE.match(line)
            if match:
                listed[match.group(2)] = match.group(1)
        for name, digest in digests.items():
            if name not in listed:
                raise AcquisitionError(f"{folder}/{name} is not listed in the existing SHA256SUMS")
            if listed[name] != digest:
                raise AcquisitionError(f"{folder}/{name} differs from its SHA256SUMS entry")
        return "verified"
    staging = path.with_name("SHA256SUMS.part")  # atomic: never a truncated SHA256SUMS
    staging.write_text("".join(f"{d}  {n}\n" for n, d in digests.items()), encoding="utf-8")
    make_read_only(staging)
    os.replace(staging, path)
    return "written"


def acquire_group(
    files: Sequence[RemoteFile], opener: Opener = default_opener, log: Path = LOG_PATH
) -> dict[str, str]:
    """Acquire every file of a source, then write or verify each folder's SHA256SUMS."""
    status = {str(f.dest): acquire(f, opener, log) for f in files}
    folders: dict[Path, list[str]] = {}
    for remote in files:
        folders.setdefault(remote.dest.parent, []).append(remote.dest.name)
    for folder, names in folders.items():
        status[str(folder / "SHA256SUMS")] = sha256sums(folder, names)
    return status


def verify_group(files: Sequence[RemoteFile]) -> dict[str, str]:
    """Offline check of already-acquired files: published facts and SHA256SUMS."""
    report = {}
    for remote in files:
        if not remote.dest.exists():
            report[str(remote.dest)] = "missing"
            continue
        check(remote, remote.dest)
        report[str(remote.dest)] = "ok"
    folders = {f.dest.parent for f in files if f.dest.exists()}
    for folder in sorted(folders):
        names = [f.dest.name for f in files if f.dest.parent == folder and f.dest.exists()]
        if (folder / "SHA256SUMS").exists():
            report[str(folder / "SHA256SUMS")] = sha256sums(folder, names)
        else:
            report[str(folder / "SHA256SUMS")] = "missing"
    return report
