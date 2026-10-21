"""Parse and validate saved Cellosaurus API responses (no network access here).

Response format, verified on 2026-10-21 against api.cellosaurus.org (release 56.0):

- ``/release-info?format=json`` returns
  ``{"Cellosaurus": {"header": {"release": {"version": "56.0", "updated": "2026-06-25", ...}}}}``.
- ``/search/cell-line?...&format=tsv`` returns metadata lines starting with ``##``
  (including ``##   response.numFound: N`` and ``##   query.fields: ...``), then a
  header line, then one line per record. Requesting ``prob`` yields a column named
  ``problematic``.
- ``dr`` entries are separated by ``|``; each entry is ``<resource>; <id>``, e.g.
  ``DepMap; ACH-000019``.
- ``hi`` (parent) and ``oi`` (same individual) entries are separated by ``|``; each
  entry is ``<accession> ! <name>``, e.g. ``CVCL_R729 ! HCT 116a``.
- ``sy`` and ``acas`` values are separated by ``; ``.
- An empty cell means Cellosaurus records nothing for that field in that entry.

Relationship states are kept distinct:
- ``recorded``: the column was returned and lists at least one accession;
- ``none_recorded``: the column was returned and is empty for this record
  (Cellosaurus lists no such relationship; this is not proof that none exists);
- ``field_unavailable``: the column was not part of the response.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from radiosensitivity_ml.data.provenance import file_sha256, text_sha256

RELEASE_KEYS = ("Cellosaurus", "header", "release")
NUM_FOUND = re.compile(r"^##\s+response\.numFound:\s*(\d+)\s*$")
CVCL = re.compile(r"^CVCL_[A-Z0-9]{4}$")
DEPMAP_ID = re.compile(r"^ACH-\d{6}$")

# Fields requested by radiosensitivity_ml.data.cellosaurus_fetch, as they appear in the
# TSV header. Every one is required: a missing column fails loudly.
REQUESTED_FIELDS = ("id", "ac", "acas", "sy", "dr", "hi", "oi", "ca", "prob", "ox", "dtv")
EXPECTED_COLUMNS = ("id", "ac", "acas", "sy", "dr", "hi", "oi", "ca", "problematic", "ox", "dtv")

RECORDED = "recorded"
NONE_RECORDED = "none_recorded"
FIELD_UNAVAILABLE = "field_unavailable"


class CellosaurusFormatError(ValueError):
    """Raised when a saved response does not have the verified structure."""


@dataclass(frozen=True)
class Link:
    """One relationship entry: target accession and the name Cellosaurus shows for it."""

    accession: str
    name: str


@dataclass(frozen=True)
class CellosaurusRecord:
    """Identity fields of one Cellosaurus entry, kept as returned (split, not edited)."""

    accession: str
    name: str
    secondary_accessions: tuple[str, ...]
    synonyms: tuple[str, ...]
    depmap_ids: tuple[str, ...]
    parents: tuple[Link, ...]
    parent_status: str
    same_individual: tuple[Link, ...]
    same_individual_status: str
    category: str
    species: str
    problematic: str
    entry_version: str


@dataclass(frozen=True)
class SearchResponse:
    """A parsed TSV search response."""

    num_found: int
    columns: tuple[str, ...]
    records: tuple[CellosaurusRecord, ...]


def parse_release_info(text: str) -> dict[str, str]:
    """Return the release block (version, updated, counts) from release-info JSON."""
    try:
        node: object = json.loads(text)
        for key in RELEASE_KEYS:
            if not isinstance(node, dict):
                raise KeyError(key)
            node = node[key]
    except (json.JSONDecodeError, KeyError) as exc:
        raise CellosaurusFormatError(f"release-info: unexpected structure ({exc})") from exc
    if not isinstance(node, dict) or "version" not in node:
        raise CellosaurusFormatError("release-info: no 'version' in the release block")
    return {str(k): str(v) for k, v in node.items()}


def split_values(cell: str, separator: str) -> tuple[str, ...]:
    """Split a multi-value cell, dropping empty parts and surrounding spaces."""
    return tuple(part.strip() for part in cell.split(separator) if part.strip())


def parse_links(cell: str) -> tuple[Link, ...]:
    """Parse ``CVCL_X ! name|CVCL_Y ! name`` into links; fail on a malformed accession."""
    links = []
    for entry in split_values(cell, "|"):
        accession, _, name = entry.partition(" ! ")
        accession = accession.strip()
        if not CVCL.match(accession):
            raise CellosaurusFormatError(f"relationship entry without a CVCL accession: {entry!r}")
        links.append(Link(accession=accession, name=name.strip()))
    return tuple(links)


def parse_depmap_xrefs(cell: str) -> tuple[str, ...]:
    """Return DepMap model IDs from a ``dr`` cell (entries ``DepMap; ACH-xxxxxx``)."""
    ids = set()
    for entry in split_values(cell, "|"):
        resource, _, identifier = entry.partition(";")
        if resource.strip() == "DepMap":
            identifier = identifier.strip()
            if not DEPMAP_ID.match(identifier):
                raise CellosaurusFormatError(f"malformed DepMap cross-reference: {entry!r}")
            ids.add(identifier)
    return tuple(sorted(ids))


def link_field(
    row: dict[str, str], column: str, columns: Sequence[str]
) -> tuple[tuple[Link, ...], str]:
    """Parse a relationship column and return (links, status)."""
    if column not in columns:
        return (), FIELD_UNAVAILABLE
    links = parse_links(row.get(column, ""))
    return links, (RECORDED if links else NONE_RECORDED)


def parse_search_tsv(
    text: str, required_columns: Sequence[str] = EXPECTED_COLUMNS
) -> SearchResponse:
    """Parse one saved TSV search response and check it is complete.

    Fails if ``response.numFound`` is missing, the header lacks a required column,
    a row has the wrong number of fields, or the number of records differs from
    ``numFound`` (truncated or paginated response).
    """
    lines = text.split("\n")
    num_found = None
    body: list[str] = []
    for line in lines:
        line = line.rstrip("\r")
        if line.startswith("##"):
            match = NUM_FOUND.match(line)
            if match:
                num_found = int(match.group(1))
        elif line.strip():
            body.append(line)
    if num_found is None:
        raise CellosaurusFormatError("no '## response.numFound' line; not a complete TSV response")
    if not body:
        if num_found:
            raise CellosaurusFormatError(f"numFound={num_found} but no header or records")
        return SearchResponse(num_found=0, columns=(), records=())
    columns = tuple(body[0].split("\t"))
    missing = [c for c in required_columns if c not in columns]
    if missing:
        raise CellosaurusFormatError(f"missing columns {missing} in header {list(columns)}")
    records = []
    for number, line in enumerate(body[1:], start=1):
        values = line.split("\t")
        if len(values) != len(columns):
            raise CellosaurusFormatError(
                f"record {number}: {len(values)} fields, header has {len(columns)}"
            )
        records.append(build_record(dict(zip(columns, values, strict=True)), columns))
    if len(records) != num_found:
        raise CellosaurusFormatError(
            f"{len(records)} records but numFound={num_found}; response truncated or paginated"
        )
    return SearchResponse(num_found=num_found, columns=columns, records=tuple(records))


def build_record(row: dict[str, str], columns: Sequence[str]) -> CellosaurusRecord:
    """Build one record from a header-keyed row."""
    accession = row.get("ac", "").strip()
    if not CVCL.match(accession):
        raise CellosaurusFormatError(f"malformed primary accession {accession!r}")
    parents, parent_status = link_field(row, "hi", columns)
    same, same_status = link_field(row, "oi", columns)
    secondary = tuple(a for a in split_values(row.get("acas", ""), ";") if a != accession)
    return CellosaurusRecord(
        accession=accession,
        name=row.get("id", "").strip(),
        secondary_accessions=secondary,
        synonyms=split_values(row.get("sy", ""), ";"),
        depmap_ids=parse_depmap_xrefs(row.get("dr", "")),
        parents=parents,
        parent_status=parent_status,
        same_individual=same,
        same_individual_status=same_status,
        category=row.get("ca", "").strip(),
        species=row.get("ox", "").strip(),
        problematic=row.get("problematic", "").strip(),
        entry_version=row.get("dtv", "").strip(),
    )


def merge_records(records: Iterable[CellosaurusRecord]) -> dict[str, CellosaurusRecord]:
    """Index records by primary accession; identical duplicates (from overlapping
    batches) collapse, conflicting duplicates fail loudly."""
    index: dict[str, CellosaurusRecord] = {}
    for record in records:
        existing = index.get(record.accession)
        if existing is not None and existing != record:
            raise CellosaurusFormatError(f"conflicting records for {record.accession}")
        index[record.accession] = record
    return index


def records_by_depmap(records: Iterable[CellosaurusRecord]) -> dict[str, tuple[str, ...]]:
    """Map each DepMap ID to the sorted accessions of all records cross-referencing it."""
    index: dict[str, set[str]] = {}
    for record in records:
        for depmap_id in record.depmap_ids:
            index.setdefault(depmap_id, set()).add(record.accession)
    return {key: tuple(sorted(value)) for key, value in sorted(index.items())}


def linked_accessions(record: CellosaurusRecord) -> tuple[str, ...]:
    """All accessions this record links to through hi or oi."""
    return tuple(sorted({link.accession for link in (*record.parents, *record.same_individual)}))


def load_saved_responses(
    folder: Path, expected_release: str, expected_ids: Sequence[str]
) -> tuple[dict[str, CellosaurusRecord], dict[str, object]]:
    """Load a folder written by radiosensitivity_ml.data.cellosaurus_fetch, verifying it first.

    Checks, in order: COMPLETE.json exists and says complete; the release-info
    response matches its sidecar hash and the expected release; the requested
    DepMap-ID list equals ``expected_ids``; every listed response file exists,
    matches the hash in COMPLETE.json and in its sidecar, has HTTP 200, and parses
    completely (record count equals numFound). Unlisted *.tsv files fail the check.

    Returns ``(records by accession, provenance summary)``.
    """
    complete_path = folder / "COMPLETE.json"
    if not complete_path.is_file():
        raise CellosaurusFormatError(f"{folder}: no COMPLETE.json; the fetch did not finish")
    complete = read_json_object(complete_path)
    if complete.get("status") != "complete":
        raise CellosaurusFormatError(f"{complete_path}: status is not 'complete'")

    release_path = folder / "release_info.json"
    check_sidecar(release_path)
    release = parse_release_info(release_path.read_text(encoding="utf-8"))
    if release["version"] != expected_release:
        raise CellosaurusFormatError(
            f"saved release {release['version']} != expected {expected_release}"
        )

    ids_text = "\n".join(sorted(set(expected_ids)))
    if complete.get("depmap_ids_sha256") != text_sha256(ids_text):
        raise CellosaurusFormatError("requested DepMap IDs differ from the current CLARIFi IDs")

    listed: set[str] = set()
    records: list[CellosaurusRecord] = []
    try:
        entries = [entry for r in complete["rounds"] for entry in r["files"]]
        for entry in entries:
            path = folder / str(entry["file"])
            listed.add(path.name)
            if not path.is_file() or file_sha256(path) != entry["sha256"]:
                raise CellosaurusFormatError(f"{path}: missing or hash differs from COMPLETE.json")
            check_sidecar(path)
            parsed = parse_search_tsv(path.read_text(encoding="utf-8"))
            if parsed.num_found != entry["num_found"]:
                raise CellosaurusFormatError(f"{path}: numFound differs from COMPLETE.json")
            records.extend(parsed.records)
    except (KeyError, TypeError) as exc:
        raise CellosaurusFormatError(f"{complete_path}: malformed ({exc})") from exc
    unlisted = sorted(p.name for p in folder.glob("*.tsv") if p.name not in listed)
    if unlisted:
        raise CellosaurusFormatError(f"{folder}: response files not in COMPLETE.json: {unlisted}")
    if not listed:
        raise CellosaurusFormatError(f"{folder}: COMPLETE.json lists no response files")

    provenance = {
        "folder": str(folder),
        "release": release,
        "n_response_files": len(listed),
        "link_rounds": complete.get("link_rounds"),
        "links_not_expanded": complete.get("links_not_expanded", []),
        "depmap_ids_without_record": complete.get("depmap_ids_without_record", []),
        "requested_fields": complete.get("requested_fields"),
    }
    return merge_records(records), provenance


def read_json_object(path: Path) -> dict[str, object]:
    """Read a JSON object; malformed content raises CellosaurusFormatError."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CellosaurusFormatError(f"{path}: not valid JSON ({exc})") from exc
    if not isinstance(data, dict):
        raise CellosaurusFormatError(f"{path}: not a JSON object")
    return data


def check_sidecar(path: Path) -> None:
    """Verify a response against its sidecar JSON: hash and HTTP status 200."""
    sidecar_path = path.with_name(path.name + ".json")
    if not path.is_file() or not sidecar_path.is_file():
        raise CellosaurusFormatError(f"{path}: response or sidecar missing")
    sidecar = read_json_object(sidecar_path)
    if sidecar.get("sha256") != file_sha256(path):
        raise CellosaurusFormatError(f"{path}: hash differs from its sidecar")
    if sidecar.get("http_status") != 200:
        raise CellosaurusFormatError(f"{path}: sidecar HTTP status {sidecar.get('http_status')}")
