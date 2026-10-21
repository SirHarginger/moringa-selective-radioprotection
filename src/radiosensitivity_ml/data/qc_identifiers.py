"""Phase 01 identifier QC: deterministic identity matching of CLARIFi to DepMap and Cellosaurus.

Matching uses verified identifiers only:
- CLARIFi ``Depmap ID`` -> DepMap ``Model.csv`` ``ModelID`` (exact);
- DepMap ID -> Cellosaurus entries whose ``dr`` lists ``DepMap; <ID>`` (exact);
- DepMap ``RRID`` compared with the Cellosaurus primary or secondary accession.
Names are compared only to FLAG disagreement; they never create or resolve a match.

Identity status per CLARIFi record (each record keyed by its CLARIFi row number):
- ``verified``: in Model.csv with the same CCLE name, exactly one Cellosaurus entry
  cross-references the DepMap ID, its accession (primary or secondary) equals the
  DepMap RRID, and no other CLARIFi record shares that identity;
- ``ambiguous``: a candidate exists but a check fails (blocking issues listed), including
  an entry found only through the DepMap RRID without a DepMap cross-reference;
- ``unmatched``: not in Model.csv, or no Cellosaurus entry found by DepMap ID or RRID.
Non-blocking observations go to ``identity_notes``.

Outcome handling: the mSF2 cell is parsed only to decide whether it is usable on the
raw scale (finite and within [0, 1]); the value is never retained or written. Per
record only ``outcome_invalid`` (True/False) is kept; aggregate counts of the
invalid sub-types are reported. Boundary values (exactly 0 or 1) are deliberately
not flagged before the protocol freeze (statistical-reviewer, 2026-10-21).
"""

from __future__ import annotations

import csv
import math
import re
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from radiosensitivity_ml.data import cellosaurus as cs

ACH_PATTERN = re.compile(r"^ACH-\d{6}$")

CLARIFI_ID_COLUMN = "Depmap ID"
CLARIFI_NAME_COLUMN = "CCLE Name"
CLARIFI_OUTCOME_COLUMN = "mSF2"
CLARIFI_COLUMNS = (CLARIFI_ID_COLUMN, CLARIFI_NAME_COLUMN, CLARIFI_OUTCOME_COLUMN)
DEFAULT_PROFILE_COLUMNS = ("ModelID", "ProfileType")

MODEL_COLUMNS = (
    "ModelID",
    "CCLEName",
    "CellLineName",
    "StrippedCellLineName",
    "RRID",
    "PatientID",
    "OncotreeLineage",
    "OncotreePrimaryDisease",
    "DepmapModelType",
)
# Reported to exist in recent DepMap releases but UNVERIFIED for 24Q4: read if present.
MODEL_OPTIONAL_COLUMNS = ("EngineeredModel", "ModelType", "OncotreeCode", "GrowthPattern")
COLUMN_ABSENT = "column_absent"

VERIFIED = "verified"
AMBIGUOUS = "ambiguous"
UNMATCHED = "unmatched"

INVALID_OUTCOME_KINDS = ("blank", "non_numeric", "non_finite", "below_zero", "above_one")


class IdentifierQCError(ValueError):
    """Raised when an input file does not have the expected structure."""


# ----------------------------------------------------------------------------- inputs


def outcome_invalid_kind(cell: str) -> str:
    """Return '' if the cell is a finite number in [0, 1], else the kind of problem.

    The parsed value is discarded; only the classification leaves this function.
    """
    text = cell.strip()
    if not text:
        return "blank"
    try:
        value = float(text)
    except ValueError:
        return "non_numeric"
    if not math.isfinite(value):
        return "non_finite"
    if value < 0:
        return "below_zero"
    if value > 1:
        return "above_one"
    return ""


@dataclass(frozen=True)
class ClarifiRecord:
    """One CLARIFi row: identifiers and the outcome validity class only."""

    row_number: int
    depmap_id: str
    ccle_name: str
    outcome_invalid_kind: str  # '' when usable on the raw scale


def read_csv(
    path: Path, required: Iterable[str] = ()
) -> tuple[tuple[str, ...], list[dict[str, str]]]:
    """Read a CSV (UTF-8, BOM tolerated, any line ending); fail on missing columns."""
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        header = tuple(reader.fieldnames or ())
        require_columns(header, required, str(path))
        return header, list(reader)


def require_columns(header: Iterable[str] | None, required: Iterable[str], source: str) -> None:
    """Fail loudly if any required column is absent."""
    present = set(header or [])
    missing = [name for name in required if name not in present]
    if missing:
        raise IdentifierQCError(f"{source}: missing columns {missing}")


def parse_clarifi(rows: Iterable[Mapping[str, str]]) -> list[ClarifiRecord]:
    """Parse CLARIFi rows; validate the ID format; keep only the outcome validity class."""
    records = []
    for index, row in enumerate(rows, start=2):
        depmap_id = (row.get(CLARIFI_ID_COLUMN) or "").strip()
        if not ACH_PATTERN.match(depmap_id):
            raise IdentifierQCError(f"CLARIFi line {index}: malformed DepMap ID {depmap_id!r}")
        records.append(
            ClarifiRecord(
                row_number=index,
                depmap_id=depmap_id,
                ccle_name=(row.get(CLARIFI_NAME_COLUMN) or "").strip(),
                outcome_invalid_kind=outcome_invalid_kind(row.get(CLARIFI_OUTCOME_COLUMN) or ""),
            )
        )
    return records


def tissue_suffix(ccle_name: str) -> str:
    """Return the tissue part of a CCLE name (text after the first underscore)."""
    _, _, suffix = ccle_name.partition("_")
    return suffix


def index_model_table(
    rows: Iterable[Mapping[str, str]], header: Sequence[str] = ()
) -> dict[str, dict[str, str]]:
    """Index Model rows by ModelID; optional columns absent from ``header`` are marked."""
    present = tuple(c for c in MODEL_OPTIONAL_COLUMNS if c in header)
    index: dict[str, dict[str, str]] = {}
    for row in rows:
        model_id = (row.get("ModelID") or "").strip()
        if model_id in index:
            raise IdentifierQCError(f"Model table: duplicate ModelID {model_id}")
        entry = {name: (row.get(name) or "").strip() for name in MODEL_COLUMNS + present}
        for name in MODEL_OPTIONAL_COLUMNS:
            entry.setdefault(name, COLUMN_ABSENT)
        index[model_id] = entry
    return index


def default_rna_models(rows: Iterable[Mapping[str, str]]) -> tuple[set[str], list[str]]:
    """Return (ModelIDs with a default RNA profile, distinct ProfileType values).

    Fails if no RNA profile is found: the ProfileType vocabulary (UNVERIFIED for 24Q4)
    would otherwise silently exclude every record.
    """
    rows = list(rows)
    kinds = sorted({(row.get("ProfileType") or "").strip() for row in rows})
    models = {
        (row.get("ModelID") or "").strip()
        for row in rows
        if (row.get("ProfileType") or "").strip().lower() == "rna"
    }
    if not models:
        raise IdentifierQCError(f"no 'rna' ProfileType in default profiles; values seen: {kinds}")
    return models, kinds


def strandedness_report(
    profile_header: Sequence[str],
    profile_rows: Iterable[Mapping[str, str]],
    default_rows: Iterable[Mapping[str, str]],
    model_ids: Iterable[str],
) -> dict[str, object]:
    """Verify whether RNA strandedness is available for the given models' default RNA profiles.

    Nothing is assumed: any OmicsProfiles column whose name contains "strand" is
    reported. Value counts are given over the default RNA profiles of ``model_ids``,
    linked through ProfileID. Missing columns are reported, not guessed.
    """
    columns = [c for c in profile_header if "strand" in c.lower()]
    report: dict[str, object] = {"columns_found": columns, "available": bool(columns)}
    default_rows = list(default_rows)
    if not columns:
        return report
    if "ProfileID" not in profile_header or not all("ProfileID" in r for r in default_rows[:1]):
        report["available"] = False
        report["reason"] = "no ProfileID to link default profiles to OmicsProfiles"
        return report
    wanted = set(model_ids)
    profile_ids = {
        (r.get("ProfileID") or "").strip()
        for r in default_rows
        if (r.get("ModelID") or "").strip() in wanted
        and (r.get("ProfileType") or "").strip().lower() == "rna"
    }
    by_profile = {(r.get("ProfileID") or "").strip(): r for r in profile_rows}
    report["profiles_linked"] = sum(p in by_profile for p in profile_ids)
    report["profiles_requested"] = len(profile_ids)
    report["value_counts"] = {
        column: dict(
            sorted(
                Counter(
                    (by_profile[p].get(column) or "").strip() or "(blank)"
                    for p in profile_ids
                    if p in by_profile
                ).items()
            )
        )
        for column in columns
    }
    return report


def expression_row_ids(path: Path) -> list[str]:
    """Read only the first field of each data row of the expression matrix.

    UNVERIFIED layout assumption (first column holds ACH IDs) is checked here.
    """
    ids = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        next(reader, None)  # header (gene columns) is not used
        for row in reader:
            if row:
                ids.append(row[0].strip())
    if not ids:
        raise IdentifierQCError("Expression matrix: no data rows")
    bad = [value for value in ids if not ACH_PATTERN.match(value)]
    if bad:
        raise IdentifierQCError(
            f"Expression matrix: {len(bad)} first-column values are not ACH IDs "
            f"(e.g. {bad[:3]}); layout assumption failed"
        )
    return ids


# --------------------------------------------------------------------------- identity


@dataclass
class IdentityRow:
    """Identity and availability of one CLARIFi record. No outcome values.

    Filled in three explicit steps: ``assess_identity`` (identity fields), then
    ``eligibility.assign_components`` (component fields), then
    ``eligibility.apply_eligibility`` (eligibility fields).
    """

    row_number: int
    depmap_id: str
    clarifi_ccle_name: str
    clarifi_tissue_suffix: str
    outcome_invalid: bool = False
    in_model_table: bool = False
    model_ccle_name: str = ""
    ccle_name_matches: bool = False
    rrid: str = ""
    patient_id: str = ""
    oncotree_lineage: str = ""
    oncotree_primary_disease: str = ""
    depmap_model_type: str = ""
    engineered_model: str = COLUMN_ABSENT
    model_type: str = COLUMN_ABSENT
    oncotree_code: str = COLUMN_ABSENT
    has_default_rna_profile: bool = False
    in_expression_matrix: bool = False
    cellosaurus_candidates: tuple[str, ...] = ()
    cellosaurus_accession: str = ""
    cellosaurus_name: str = ""
    cellosaurus_category: str = ""
    cellosaurus_species: str = ""
    rrid_relation: str = "not_checked"
    parent_status: str = "not_checked"
    parent_accessions: tuple[str, ...] = ()
    same_individual_status: str = "not_checked"
    same_individual_accessions: tuple[str, ...] = ()
    problematic: str = "not_checked"
    identity_status: str = UNMATCHED
    identity_issues: tuple[str, ...] = ()
    identity_notes: tuple[str, ...] = ()
    component_id: str = ""
    component_records: int = 0
    candidate_component_id: str = ""
    component_flag_sources: tuple[str, ...] = ()
    eligible_primary: bool = False
    eligible_retaining_problematic: bool = False
    exclusion_reasons: tuple[str, ...] = ()


def rrid_relation(rrid: str, record: cs.CellosaurusRecord) -> str:
    """Compare a DepMap RRID with a Cellosaurus entry: primary / secondary / disagree / no_rrid."""
    value = rrid.removeprefix("RRID:").strip()
    if not value:
        return "no_rrid"
    if value == record.accession:
        return "primary"
    if value in record.secondary_accessions:
        return "secondary"
    return "disagree"


def index_by_any_accession(
    cellosaurus: Mapping[str, cs.CellosaurusRecord],
) -> dict[str, cs.CellosaurusRecord]:
    """Index entries by primary and secondary accessions."""
    index = dict(cellosaurus)
    for record in cellosaurus.values():
        for accession in record.secondary_accessions:
            index.setdefault(accession, record)
    return index


def assess_identity(
    clarifi: Sequence[ClarifiRecord],
    models: Mapping[str, Mapping[str, str]],
    rna_models: set[str] | None,
    expression_ids: set[str] | None,
    cellosaurus: Mapping[str, cs.CellosaurusRecord] | None,
) -> list[IdentityRow]:
    """Build one IdentityRow per CLARIFi record (sorted by DepMap ID, then row number).

    ``rna_models``/``expression_ids`` are None in the model-table audit mode;
    ``cellosaurus`` is None when no Cellosaurus responses are used.
    """
    by_depmap = cs.records_by_depmap(cellosaurus.values()) if cellosaurus is not None else {}
    by_accession = index_by_any_accession(cellosaurus) if cellosaurus is not None else {}
    id_counts = Counter(r.depmap_id for r in clarifi)
    rows = []
    for record in sorted(clarifi, key=lambda r: (r.depmap_id, r.row_number)):
        row = IdentityRow(
            row_number=record.row_number,
            depmap_id=record.depmap_id,
            clarifi_ccle_name=record.ccle_name,
            clarifi_tissue_suffix=tissue_suffix(record.ccle_name),
            outcome_invalid=bool(record.outcome_invalid_kind),
        )
        issues: list[str] = []
        notes: list[str] = []
        if id_counts[record.depmap_id] > 1:
            issues.append("duplicate_depmap_id_in_clarifi")
        model = models.get(record.depmap_id)
        if model is None:
            issues.append("not_in_model_table")
        else:
            fill_model_fields(row, model, issues)
        if rna_models is not None:
            row.has_default_rna_profile = record.depmap_id in rna_models
        if expression_ids is not None:
            row.in_expression_matrix = record.depmap_id in expression_ids
        if cellosaurus is not None:
            candidates = by_depmap.get(record.depmap_id, ())
            assess_cellosaurus(row, candidates, cellosaurus, by_accession, issues, notes)
        row.identity_issues = tuple(issues)
        row.identity_notes = tuple(notes)
        rows.append(row)
    flag_shared_identities(rows)
    for row in rows:
        row.identity_status = identity_status(row, cellosaurus is not None)
    return rows


def fill_model_fields(row: IdentityRow, model: Mapping[str, str], issues: list[str]) -> None:
    """Copy DepMap Model fields into the row and add model-level issues."""
    row.in_model_table = True
    row.model_ccle_name = model["CCLEName"]
    row.ccle_name_matches = model["CCLEName"] == row.clarifi_ccle_name
    row.rrid = model["RRID"]
    row.patient_id = model["PatientID"]
    row.oncotree_lineage = model["OncotreeLineage"]
    row.oncotree_primary_disease = model["OncotreePrimaryDisease"]
    row.depmap_model_type = model["DepmapModelType"]
    row.engineered_model = model.get("EngineeredModel", COLUMN_ABSENT)
    row.model_type = model.get("ModelType", COLUMN_ABSENT)
    row.oncotree_code = model.get("OncotreeCode", COLUMN_ABSENT)
    if not row.ccle_name_matches:
        issues.append("ccle_name_mismatch")
    if not row.rrid:
        issues.append("missing_rrid_in_model_table")


def fill_relationships(row: IdentityRow, record: cs.CellosaurusRecord) -> None:
    """Copy Cellosaurus relationship and descriptive fields into the row."""
    row.cellosaurus_name = record.name
    row.cellosaurus_category = record.category
    row.cellosaurus_species = record.species
    row.parent_status = record.parent_status
    row.parent_accessions = tuple(link.accession for link in record.parents)
    row.same_individual_status = record.same_individual_status
    row.same_individual_accessions = tuple(link.accession for link in record.same_individual)
    row.problematic = record.problematic


def assess_cellosaurus(
    row: IdentityRow,
    candidates: Sequence[str],
    cellosaurus: Mapping[str, cs.CellosaurusRecord],
    by_accession: Mapping[str, cs.CellosaurusRecord],
    issues: list[str],
    notes: list[str],
) -> None:
    """Fill the Cellosaurus fields of a row and append identity issues and notes."""
    row.cellosaurus_candidates = tuple(candidates)
    if not candidates:
        via_rrid = by_accession.get(row.rrid.removeprefix("RRID:").strip())
        if via_rrid is None:
            issues.append("no_cellosaurus_record")
            row.rrid_relation = row.parent_status = row.same_individual_status = "no_record"
            row.problematic = "unknown"
            return
        # Found only through the RRID: not cross-confirmed by a DepMap cross-reference.
        issues.append("cellosaurus_found_via_rrid_only")
        row.rrid_relation = rrid_relation(row.rrid, via_rrid)
        fill_relationships(row, via_rrid)
        return
    if len(candidates) > 1:
        issues.append("multiple_cellosaurus_records")
        row.rrid_relation = row.parent_status = row.same_individual_status = "ambiguous"
        row.problematic = "unknown"
        return
    record = cellosaurus[candidates[0]]
    row.cellosaurus_accession = record.accession
    row.rrid_relation = rrid_relation(row.rrid, record)
    if row.rrid_relation == "disagree":
        issues.append("rrid_disagrees_with_cellosaurus")
    elif row.rrid_relation == "secondary":
        notes.append("rrid_is_secondary_accession")
    if len(record.depmap_ids) > 1:
        notes.append("cellosaurus_entry_lists_multiple_depmap_ids")
    fill_relationships(row, record)


def flag_shared_identities(rows: Sequence[IdentityRow]) -> None:
    """Flag records that share a Cellosaurus accession, RRID or CCLE name with another record."""
    keys = {
        "shares_cellosaurus_accession": lambda r: r.cellosaurus_accession,
        "shares_rrid": lambda r: r.rrid.removeprefix("RRID:"),
        "shares_ccle_name": lambda r: r.clarifi_ccle_name,
    }
    for issue, key in keys.items():
        counts = Counter(key(r) for r in rows if key(r))
        for row in rows:
            if key(row) and counts[key(row)] > 1 and issue not in row.identity_issues:
                row.identity_issues = (*row.identity_issues, issue)


BLOCKING_UNMATCHED = {"not_in_model_table", "no_cellosaurus_record"}


def identity_status(row: IdentityRow, cellosaurus_used: bool) -> str:
    """Derive the identity status from the blocking issues (see module docstring)."""
    issues = set(row.identity_issues)
    if issues & BLOCKING_UNMATCHED:
        return UNMATCHED
    if issues:
        return AMBIGUOUS
    if not cellosaurus_used:
        return AMBIGUOUS  # identity cannot be cross-confirmed without Cellosaurus
    if row.rrid_relation not in {"primary", "secondary"}:
        return AMBIGUOUS
    return VERIFIED


def duplicate_identifier_rows(rows: Sequence[IdentityRow]) -> list[dict[str, str]]:
    """Return one row per identifier value shared by more than one CLARIFi record."""
    keys = {
        "clarifi_depmap_id": lambda r: r.depmap_id,
        "clarifi_ccle_name": lambda r: r.clarifi_ccle_name,
        "depmap_rrid": lambda r: r.rrid.removeprefix("RRID:"),
        "cellosaurus_accession": lambda r: r.cellosaurus_accession,
    }
    out = []
    for kind, key in keys.items():
        groups: dict[str, list[str]] = {}
        for row in rows:
            if key(row):
                groups.setdefault(key(row), []).append(f"{row.depmap_id}@row{row.row_number}")
        for value in sorted(groups):
            if len(groups[value]) > 1:
                out.append(
                    {
                        "identifier_type": kind,
                        "identifier": value,
                        "records": ";".join(sorted(groups[value])),
                    }
                )
    return out
