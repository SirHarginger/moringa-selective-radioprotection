"""Fetch Cellosaurus records for the CLARIFi DepMap IDs (INVESTIGATOR-RUN).

What it does (no parsing beyond completeness checks, no analysis):
1. Verifies data/raw/CLARIFi.csv against the SHA-256 in its manifest and reads ONLY
   the "Depmap ID" column. Verifies the DepMap Model.csv against its folder's
   SHA256SUMS and reads ONLY ModelID and RRID for those IDs.
2. Saves /release-info and stops unless the live release is the expected one
   (JSON path Cellosaurus.header.release.version, verified 2026-10-21).
3. Rounds (each saved file is named after its round):
   - ``dr``: ``dr:(ACH-... OR ...)`` in batches;
   - ``drsingle``: one ``dr:ACH-...`` query for EVERY ID (batched OR semantics are
     unverified; a batch could return only some of an ID's entries and hide an
     ambiguity). IDs whose batched and single results differ are listed in
     COMPLETE.json; the QC uses the union of all entries, so any extra entry makes the
     record ambiguous;
   - ``rrid``: ``ac:(CVCL_... OR ...)`` for DepMap RRIDs not yet fetched;
   - ``link1``, ``link2``, ...: ``ac:(...)`` for parent (hi) and same-individual (oi)
     accessions not yet fetched (primary or secondary), repeated until no new
     accession appears or --max-link-rounds is reached. Accessions still not fetched
     are listed in COMPLETE.json; the QC flags their components for review.
4. Every response is saved byte-for-byte with a sidecar JSON (URL, UTC time, HTTP
   status, content type, Content-Length, SHA-256) and checked: HTTP 200, body length
   equals Content-Length when given, record count equals ``## response.numFound``
   and stays below the row cap. A truncated or paginated response stops the run.
5. Writes COMPLETE.json last, makes every file read-only, renames ``<out>.partial``
   to ``<out>`` and prints the SHA-256 of COMPLETE.json for the manifest.

A failed run leaves ``<out>.partial``, which the QC never reads; inspect and delete it.

Called by ``python scripts/acquire_data.py`` (after the DepMap files are acquired).
"""

from __future__ import annotations

import csv
import os
import stat
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from radiosensitivity_ml.data import cellosaurus as cs
from radiosensitivity_ml.data.provenance import (
    ProvenanceError,
    file_sha256,
    listed_sha256,
    manifest_file_sha256,
    text_sha256,
    verify_sha256,
    write_json,
    write_once_folder,
)

API = "https://api.cellosaurus.org"
ROWS_CAP = 1000
USER_AGENT = "explainable-radiosensitivity-ml-phase01 (investigator-run)"


def batches(items: list[str], size: int) -> list[list[str]]:
    """Split a list into consecutive batches."""
    return [items[i : i + size] for i in range(0, len(items), size)]


def search_url(field: str, values: list[str]) -> str:
    """Build a TSV search URL for ``field:(v1 OR v2 ...)``."""
    params = {
        "q": f"{field}:(" + " OR ".join(values) + ")",
        "fields": ",".join(cs.REQUESTED_FIELDS),
        "format": "tsv",
        "rows": str(ROWS_CAP),
    }
    return f"{API}/search/cell-line?{urllib.parse.urlencode(params)}"


def fetch(url: str, path: Path) -> bytes:
    """Download one URL to a new file with a provenance sidecar; return the body."""
    if path.exists():
        raise FileExistsError(f"{path} exists; refusing to overwrite")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=120) as response:  # fixed https host
        body = response.read()
        status = response.status
        content_type = response.headers.get("Content-Type")
        content_length = response.headers.get("Content-Length")
    if status != 200:
        raise RuntimeError(f"HTTP {status} for {url}")
    if content_length is not None and int(content_length) != len(body):
        raise RuntimeError(f"truncated body for {url}: {len(body)} of {content_length} bytes")
    path.write_bytes(body)
    sidecar = {
        "url": url,
        "accessed_utc": datetime.now(UTC).isoformat(),
        "http_status": status,
        "content_type": content_type,
        "content_length_header": content_length,
        "sha256": file_sha256(path),
        "size_bytes": len(body),
    }
    write_json(path.with_name(path.name + ".json"), sidecar)
    return body


def read_depmap_ids(clarifi: Path) -> list[str]:
    """Read the sorted, unique DepMap IDs (only that column) and validate their format."""
    with clarifi.open(encoding="utf-8-sig", newline="") as handle:
        ids = sorted({(row.get("Depmap ID") or "").strip() for row in csv.DictReader(handle)})
    bad = [value for value in ids if not cs.DEPMAP_ID.match(value)]
    if bad:
        raise ValueError(f"malformed DepMap IDs in {clarifi}: {bad[:3]}")
    return ids


def read_rrids(model: Path, ids: list[str]) -> list[str]:
    """Return sorted RRIDs (prefix removed) of the given DepMap IDs from a verified Model.csv."""
    expected = listed_sha256(model)
    if expected is None or file_sha256(model) != expected:
        raise ProvenanceError(f"{model} is not verified against its SHA256SUMS")
    wanted = set(ids)
    rrids = set()
    with model.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if (row.get("ModelID") or "").strip() in wanted:
                value = (row.get("RRID") or "").strip().removeprefix("RRID:")
                if cs.CVCL.match(value):
                    rrids.add(value)
    return sorted(rrids)


def known_accessions(records: dict[str, cs.CellosaurusRecord]) -> set[str]:
    """Primary and secondary accessions of fetched entries."""
    return set(records) | {a for r in records.values() for a in r.secondary_accessions}


class Fetcher:
    """Runs query rounds into one staging folder and keeps the round log."""

    def __init__(self, folder: Path, batch_size: int) -> None:
        self.folder = folder
        self.batch_size = batch_size
        self.rounds: list[dict[str, object]] = []
        self.records: dict[str, cs.CellosaurusRecord] = {}

    def run(
        self, name: str, field: str, values: list[str], batch_size: int | None = None
    ) -> list[cs.CellosaurusRecord]:
        """Fetch, check and merge all batches of one round; return this round's records."""
        entries = []
        round_records: list[cs.CellosaurusRecord] = []
        for index, batch in enumerate(batches(values, batch_size or self.batch_size), start=1):
            file_name = f"{name}_batch{index:03d}.tsv"
            body = fetch(search_url(field, batch), self.folder / file_name)
            parsed = cs.parse_search_tsv(body.decode("utf-8"))  # fails if truncated
            if parsed.num_found >= ROWS_CAP:
                raise RuntimeError(f"{file_name}: numFound {parsed.num_found} reached the row cap")
            self.records = cs.merge_records([*self.records.values(), *parsed.records])
            round_records.extend(parsed.records)
            entries.append(
                {
                    "file": file_name,
                    "sha256": file_sha256(self.folder / file_name),
                    "n_requested": len(batch),
                    "num_found": parsed.num_found,
                }
            )
            time.sleep(1.0)
        self.rounds.append(
            {"round": name, "query_field": field, "n_values": len(values), "files": entries}
        )
        return round_records


def make_read_only(folder: Path) -> None:
    """Remove write permission from every file in a folder."""
    for path in folder.iterdir():
        mode = path.stat().st_mode
        os.chmod(path, mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))


@dataclass(frozen=True)
class FetchSettings:
    """Inputs and limits of one Cellosaurus fetch (defaults match the pinned release)."""

    clarifi: Path = Path("data/raw/CLARIFi.csv")
    clarifi_manifest: Path = Path("data/manifests/clarifi__v1_0.yaml")
    model: Path = Path("data/raw/depmap/24q4/Model.csv")
    out: Path = Path("data/raw/cellosaurus/r56_0")
    batch_size: int = 50
    max_link_rounds: int = 10
    expected_release: str = "56.0"


def fetch_cellosaurus(args: FetchSettings | None = None) -> str:
    """Fetch the release info and all query rounds; return the COMPLETE.json SHA-256.

    ``args`` defaults to ``FetchSettings()`` (built per call, never shared).
    """
    args = FetchSettings() if args is None else args
    verify_sha256(args.clarifi, manifest_file_sha256(args.clarifi_manifest, str(args.clarifi)))
    ids = read_depmap_ids(args.clarifi)
    rrids = read_rrids(args.model, ids)
    started = datetime.now(UTC).isoformat()

    def build(folder: Path) -> None:
        release_body = fetch(f"{API}/release-info?format=json", folder / "release_info.json")
        release = cs.parse_release_info(release_body.decode("utf-8"))
        if release["version"] != args.expected_release:
            raise RuntimeError(
                f"live Cellosaurus release {release['version']} != expected "
                f"{args.expected_release}; use a new --out and manifest for the live release"
            )
        fetcher = Fetcher(folder, args.batch_size)
        batched = cs.records_by_depmap(fetcher.run("dr", "dr", ids))
        # Every ID is also queried on its own: a batched OR query could return only some
        # of an ID's entries, which would hide an ambiguity. Differences are recorded.
        single = cs.records_by_depmap(fetcher.run("drsingle", "dr", ids, batch_size=1))
        batch_single_differences = sorted(i for i in ids if batched.get(i, ()) != single.get(i, ()))
        new_rrids = sorted(set(rrids) - known_accessions(fetcher.records))
        if new_rrids:
            fetcher.run("rrid", "ac", new_rrids)
        frontier: list[str] = []
        for number in range(1, args.max_link_rounds + 1):
            linked = {a for r in fetcher.records.values() for a in cs.linked_accessions(r)}
            frontier = sorted(linked - known_accessions(fetcher.records))
            if not frontier:
                break
            fetcher.run(f"link{number}", "ac", frontier)
        linked = {a for r in fetcher.records.values() for a in cs.linked_accessions(r)}
        unexpanded = sorted(linked - known_accessions(fetcher.records))
        by_depmap = cs.records_by_depmap(fetcher.records.values())
        write_json(
            folder / "COMPLETE.json",
            {
                "status": "complete",
                "script": "src/radiosensitivity_ml/data/cellosaurus_fetch.py",
                "script_sha256": file_sha256(Path(__file__)),
                "started_utc": started,
                "finished_utc": datetime.now(UTC).isoformat(),
                "release": release,
                "requested_fields": list(cs.REQUESTED_FIELDS),
                "batch_size": args.batch_size,
                "max_link_rounds": args.max_link_rounds,
                "clarifi_sha256": file_sha256(args.clarifi),
                "model_sha256": file_sha256(args.model),
                "depmap_ids_requested": len(ids),
                "depmap_ids_sha256": text_sha256("\n".join(ids)),
                "depmap_ids_without_record": [i for i in ids if i not in by_depmap],
                "batch_single_differences": batch_single_differences,
                "rrids_requested": len(rrids),
                "records_fetched": len(fetcher.records),
                "links_not_expanded": unexpanded,
                "rounds": fetcher.rounds,
            },
        )
        make_read_only(folder)

    write_once_folder(args.out, build)
    return file_sha256(args.out / "COMPLETE.json")
