from __future__ import annotations

import csv
import hashlib
import io
import logging
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
import requests
import yaml

from moringa_radioprotection.chemistry import canonicalize_smiles, normalize_smiles_value, parse_numeric_response


def load_project_config(config_path: str | Path) -> dict[str, Any]:
    """Load the project configuration from YAML."""
    with Path(config_path).open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}
    if not isinstance(config, dict):
        raise ValueError(f"Configuration file {config_path} is not a YAML mapping.")
    return config


def acquisition_requirements(config: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the required and optional NCI/CellMiner source files for acquisition."""
    nci_config = config.get("nci", {})
    resources: list[dict[str, Any]] = []
    for section_name in ("required_files", "optional_files"):
        items = nci_config.get(section_name, [])
        if not isinstance(items, list):
            raise ValueError(f"The 'nci.{section_name}' configuration must be a list.")
        resources.extend(dict(item) for item in items)
    return resources


def raw_nci_directory(config: dict[str, Any]) -> Path:
    """Return the folder used to store raw NCI files."""
    base = config.get("paths", {}).get("raw_data", "data/raw")
    return Path(base) / "nci60"


def log_directory(config: dict[str, Any]) -> Path:
    """Return the folder used for timestamped acquisition logs."""
    return Path(config.get("paths", {}).get("logs", "results/logs"))


def timestamp_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def validate_file_readability(path: Path) -> tuple[bool, str]:
    """Check whether a candidate local file exists and can be opened for reading."""
    if not path.exists():
        return False, "missing"
    if not path.is_file():
        return False, "invalid_path"
    try:
        with path.open("rb") as handle:
            handle.read(1)
    except OSError as exc:  # pragma: no cover - defensive path, not executed in tests
        return False, f"unreadable: {exc}"
    return True, "readable"


def validate_zip_archive(path: Path) -> bool:
    """Validate that a local ZIP is readable and not corrupt."""
    if not path.exists() or not path.is_file():
        return False
    try:
        with zipfile.ZipFile(path, "r") as archive:
            bad = archive.testzip()
    except (zipfile.BadZipFile, OSError, RuntimeError):
        return False
    return bad is None


def sha256_file(path: Path) -> str:
    """Return the SHA-256 digest for a file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_file_status(path: Path) -> tuple[str, int, str]:
    """Map local file state to status label, byte size, and hash."""
    if not path.exists():
        return "missing", 0, ""
    if not path.is_file():
        return "invalid_path", 0, ""
    size = path.stat().st_size
    if size <= 0:
        return "empty", size, ""
    readable, flag = validate_file_readability(path)
    if not readable:
        return flag, size, ""
    if path.suffix.lower() == ".zip" and not validate_zip_archive(path):
        return "invalid_zip", size, ""
    return "present", size, sha256_file(path)


def download_resource(url: str, destination: Path, timeout: tuple[int, int] = (10, 60)) -> tuple[bool, str]:
    """Download a resource to the destination without overwriting existing files."""
    if destination.exists():
        return False, "existing"

    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_path = destination.with_suffix(destination.suffix + ".part")
    try:
        response = requests.get(url, timeout=timeout, stream=True)
        response.raise_for_status()
        with temp_path.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=65536):
                if chunk:
                    handle.write(chunk)
    except requests.RequestException as exc:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)
        return False, f"failed: {exc}"

    if not temp_path.exists():
        return False, "failed: empty_response"
    if destination.suffix.lower() == ".zip" and not validate_zip_archive(temp_path):
        temp_path.unlink(missing_ok=True)
        return False, "failed: invalid_zip"

    temp_path.replace(destination)
    return True, "downloaded"


def write_manifest(rows: Iterable[dict[str, Any]], manifest_path: Path) -> None:
    """Write the acquisition manifest as CSV."""
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "source",
        "source_url",
        "retrieval_date_utc",
        "local_filename",
        "local_path",
        "file_size_bytes",
        "sha256",
        "status",
        "required",
        "notes",
    ]

    with manifest_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def manual_download_instructions(config: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    """Format a clear instruction block for missing required raw files."""
    raw_dir = raw_nci_directory(config)
    lines = [
        "NCI acquisition failed because one or more required NIH/NCI CellMiner resources could not be retrieved.",
        "The script does not overwrite existing files and does not perform unsafe scraping around the official source.",
        "",
        f"Target directory: {raw_dir}",
        "",
        "Download the required files manually and save them exactly as listed below:",
    ]

    for row in rows:
        lines.append(f"- {row['local_filename']}")
        lines.append(f"  source: {row['source_url']}")
        lines.append(f"  purpose: {row['notes']}")

    lines.extend([
        "",
        "After the files are present, rerun:",
        "python scripts/fetch_nci.py --config config/analysis.yaml",
    ])
    return "\n".join(lines)


EXPECTED_PROCESSED_COLUMNS = {
    "NSC # b",
    "Drug name",
    "FDA status",
    "Mechanism of action c",
    "PubChem SID",
    "SMILES d",
    "BR:MCF7",
    "PR:DU-145",
    "Total experiments e",
    "Total after quality control f",
}

NSC_HEADER_ALIASES = ("NSC # b", "NSC #")


class MissingRequiredColumnsError(ValueError):
    """Raised when a required source column is missing from the workbook."""


def resolve_nsc_column(frame: pd.DataFrame) -> str:
    """Return the NSC identifier column, accepting the known CellMiner header variants."""
    for candidate in NSC_HEADER_ALIASES:
        if candidate in frame.columns:
            return candidate

    normalized = {str(column).strip().lower(): column for column in frame.columns}
    for candidate in (col.lower() for col in NSC_HEADER_ALIASES):
        if candidate in normalized:
            return normalized[candidate]

    raise MissingRequiredColumnsError(
        "Missing expected NSC identifier column. Expected one of: " + ", ".join(NSC_HEADER_ALIASES)
    )


def validate_expected_columns(frame: pd.DataFrame, required_columns: set[str]) -> None:
    """Fail clearly if expected source columns are absent, accepting known aliases for NSC IDs."""
    for column_name in list(required_columns):
        if column_name == "NSC # b" and "NSC #" in frame.columns:
            continue
        if column_name == "NSC #" and "NSC # b" in frame.columns:
            continue

    missing = []
    for column_name in sorted(required_columns):
        if column_name in frame.columns:
            continue
        if column_name == "NSC # b" and "NSC #" in frame.columns:
            continue
        if column_name == "NSC #" and "NSC # b" in frame.columns:
            continue
        missing.append(column_name)

    if missing:
        raise MissingRequiredColumnsError(
            "Missing expected columns in NCI workbook: " + ", ".join(missing)
        )


def read_excel_from_zip(zip_path: Path, workbook_name: str, sheet_name: str, header_row: int) -> pd.DataFrame:
    """Read a workbook directly from a ZIP archive without extracting raw files."""
    if not zip_path.exists():
        raise FileNotFoundError(f"Missing NCI archive: {zip_path}")

    with zipfile.ZipFile(zip_path, "r") as archive:
        names = {entry.lower(): entry for entry in archive.namelist()}
        target_key = workbook_name.lower()
        if target_key not in names:
            raise FileNotFoundError(f"Workbook '{workbook_name}' not found in {zip_path}.")
        with archive.open(names[target_key], "r") as handle:
            workbook_bytes = handle.read()

    with io.BytesIO(workbook_bytes) as buffer:
        frame = pd.read_excel(buffer, sheet_name=sheet_name, header=header_row - 1, engine="openpyxl")
    return frame


def clean_nsc_id(value: Any) -> str | None:
    """Normalize the original NSC identifier while preserving its source format."""
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    if text == "" or text.lower() in {"na", "n/a", "nan", "none"}:
        return None
    return text


def prepare_nci_response_table(frame: pd.DataFrame) -> pd.DataFrame:
    """Build the core prepared NCI cancer-response table."""
    prepared = frame.copy()
    nsc_column = resolve_nsc_column(prepared)

    prepared["nsc_id"] = prepared[nsc_column].map(clean_nsc_id)
    prepared["drug_name"] = prepared["Drug name"]
    prepared["fda_status"] = prepared["FDA status"]
    prepared["mechanism_of_action"] = prepared["Mechanism of action c"]
    prepared["pubchem_sid"] = prepared["PubChem SID"]
    prepared["original_smiles"] = prepared["SMILES d"].map(normalize_smiles_value)

    canonical_records = prepared["original_smiles"].map(lambda value: canonicalize_smiles(value))
    prepared["structure_valid"] = canonical_records.map(lambda item: item[0])
    prepared["canonical_smiles"] = canonical_records.map(lambda item: item[1])
    prepared["inchikey"] = canonical_records.map(lambda item: item[2])

    prepared["mcf7_zscore"] = parse_numeric_response(prepared["BR:MCF7"])
    prepared["du145_zscore"] = parse_numeric_response(prepared["PR:DU-145"])
    prepared["mcf7_available"] = prepared["mcf7_zscore"].notna()
    prepared["du145_available"] = prepared["du145_zscore"].notna()
    prepared["paired_response"] = prepared["mcf7_available"] & prepared["du145_available"]

    prepared["total_experiments"] = pd.to_numeric(prepared["Total experiments e"], errors="coerce")
    prepared["total_after_quality_control"] = pd.to_numeric(prepared["Total after quality control f"], errors="coerce")

    output_columns = [
        "nsc_id",
        "drug_name",
        "fda_status",
        "mechanism_of_action",
        "pubchem_sid",
        "original_smiles",
        "canonical_smiles",
        "inchikey",
        "structure_valid",
        "mcf7_zscore",
        "du145_zscore",
        "mcf7_available",
        "du145_available",
        "paired_response",
        "total_experiments",
        "total_after_quality_control",
    ]
    return prepared.loc[:, output_columns]


def compute_audit_table(prepared: pd.DataFrame, paired: pd.DataFrame) -> pd.DataFrame:
    """Construct the audit table metrics for the prepared NCI dataset."""
    rows = {
        "source_records": int(len(prepared)),
        "unique_nsc_ids": int(prepared["nsc_id"].dropna().nunique()),
        "records_with_mcf7": int(prepared["mcf7_available"].sum()),
        "records_with_du145": int(prepared["du145_available"].sum()),
        "records_with_both_responses": int(prepared["paired_response"].sum()),
        "records_with_smiles": int(prepared["original_smiles"].notna().sum()),
        "valid_structures": int(prepared["structure_valid"].sum()),
        "invalid_structures": int((~prepared["structure_valid"]).sum()),
        "unique_canonical_smiles": int(prepared["canonical_smiles"].dropna().nunique()),
        "unique_inchikeys": int(prepared["inchikey"].dropna().nunique()),
        "duplicate_nsc_records": int(prepared["nsc_id"].dropna().duplicated().sum()),
        "duplicate_canonical_structures": int(prepared["canonical_smiles"].dropna().duplicated().sum()),
        "paired_valid_structure_records": int(len(paired)),
        "missing_pubchem_sid": int(prepared["pubchem_sid"].isna().sum()),
        "missing_smiles": int(prepared["original_smiles"].isna().sum()),
        "missing_mcf7_response": int(prepared["mcf7_zscore"].isna().sum()),
        "missing_du145_response": int(prepared["du145_zscore"].isna().sum()),
    }

    return pd.DataFrame({"metric": list(rows.keys()), "value": list(rows.values())})


def load_optional_annotation_coverage(activity_frame: pd.DataFrame, logger: logging.Logger | None = None) -> dict[str, Any]:
    """Attempt a lightweight NSC coverage comparison with the older NSC annotation archive."""
    results: dict[str, Any] = {
        "activity_nsc_count": int(activity_frame["nsc_id"].dropna().nunique()),
        "annotation_nsc_count": None,
        "matched_nsc_count": None,
        "activity_nsc_missing_from_annotation": None,
    }

    annotation_zip = Path("data/raw/nci60/NSC_QUERY_LIST.zip")
    if not annotation_zip.exists():
        if logger is not None:
            logger.warning("Optional NSC annotation archive was not found; coverage check skipped: %s", annotation_zip)
        return results

    try:
        annotation_frame = read_excel_from_zip(annotation_zip, "output/NSC_QUERY_LIST.xlsx", "all", 1)
    except Exception as exc:  # pragma: no cover - optional coverage-only behaviour
        if logger is not None:
            logger.warning("Optional NSC annotation archive could not be read: %s", exc)
        return results

    candidate_columns = [col for col in annotation_frame.columns if "NSC" in str(col).upper()]
    if not candidate_columns:
        if logger is not None:
            logger.warning("No NSC column found in optional annotation archive; coverage check skipped.")
        return results

    annotation_values = set()
    for column_name in candidate_columns:
        annotation_values.update(
            clean_nsc_id(value)
            for value in annotation_frame[column_name].dropna().tolist()
            if clean_nsc_id(value) is not None
        )

    activity_values = set(activity_frame["nsc_id"].dropna().astype(str).tolist())
    matched = activity_values.intersection(annotation_values)
    results["annotation_nsc_count"] = len(annotation_values)
    results["matched_nsc_count"] = len(matched)
    results["activity_nsc_missing_from_annotation"] = len(activity_values.difference(annotation_values))
    return results


def append_annotation_coverage(audit_frame: pd.DataFrame, coverage: dict[str, Any]) -> pd.DataFrame:
    """Append the optional annotation coverage metrics to the audit data."""
    for key, value in coverage.items():
        audit_frame.loc[len(audit_frame)] = {"metric": key, "value": value}
    return audit_frame


def prepare_nci_stage(config: dict[str, Any], logger: logging.Logger) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Prepare the core NCI response table and paired subset from the CellMiner z-score workbook."""
    raw_dir = Path(config.get("paths", {}).get("raw_data", "data/raw")) / "nci60"
    archive = raw_dir / "DTP_NCI60_ZSCORE.zip"

    if not archive.exists():
        raise FileNotFoundError(f"Required CellMiner z-score archive missing: {archive}")

    logger.info("Reading processed NCI archive: %s", archive)
    processed_frame = read_excel_from_zip(archive, "output/DTP_NCI60_ZSCORE.xlsx", "all", 9)
    validate_expected_columns(processed_frame, EXPECTED_PROCESSED_COLUMNS)

    prepared = prepare_nci_response_table(processed_frame)
    paired = prepared[(prepared["mcf7_available"]) & (prepared["du145_available"]) & (prepared["structure_valid"])].copy()
    audit = compute_audit_table(prepared, paired)

    coverage = load_optional_annotation_coverage(prepared, logger)
    audit = append_annotation_coverage(audit, coverage)

    return prepared, paired, audit
