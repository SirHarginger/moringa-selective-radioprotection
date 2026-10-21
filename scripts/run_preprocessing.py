"""Preprocessing step 2: identifier QC and analysis-population definition.

    python scripts/run_preprocessing.py --config configs/preprocessing.yaml
    python scripts/run_preprocessing.py --config configs/preprocessing.yaml --check-inputs

Descriptive only: no modelling, no outcome statistics (the outcome is read only to
decide whether each value is valid on the raw scale).

``--check-inputs`` lists every required input with its status (present / missing /
checksum OK / mismatch) and exits without running the QC.

Full mode (default) verifies every input before reading it:
- CLARIFi against the SHA-256 in its manifest;
- DepMap files against their folder's SHA256SUMS;
- the Cellosaurus folder against COMPLETE.json, sidecars, release and requested-ID hash;
then writes the identity, relationship, component, eligibility, attrition and tissue
tables and summary.json (see radiosensitivity_ml.data.qc_report) plus run_record.json.

Audit mode (--model-table-audit MODEL_CSV --out NEW_FOLDER) matches CLARIFi against
one other Model table only (e.g. DepMap 23Q4) and reads no expression or Cellosaurus
files.

Outputs go to a new folder (written as <out>.partial, renamed when complete). An
existing folder is never overwritten. Raw inputs are only opened for reading.

Run from the repository root; commit first (--allow-dirty is recorded if used).
Audit example:
  python scripts/run_preprocessing.py --model-table-audit data/raw/depmap/23q4_v1/Model.csv \
      --out results/tables/phase_01/identifier_qc_23q4_v1_audit
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))  # run without installing the package

import yaml

from radiosensitivity_ml.data import cellosaurus as cs
from radiosensitivity_ml.data import eligibility as el
from radiosensitivity_ml.data import qc_identifiers as qc
from radiosensitivity_ml.data import qc_report as report
from radiosensitivity_ml.data.provenance import (
    ProvenanceError,
    file_sha256,
    listed_sha256,
    manifest_file_sha256,
    write_json,
    write_once_folder,
)

DEFAULT_CONFIG = Path("configs/preprocessing.yaml")
CODE_FILES = (
    "scripts/run_preprocessing.py",
    "src/radiosensitivity_ml/data/cellosaurus.py",
    "src/radiosensitivity_ml/data/components.py",
    "src/radiosensitivity_ml/data/eligibility.py",
    "src/radiosensitivity_ml/data/provenance.py",
    "src/radiosensitivity_ml/data/qc_identifiers.py",
    "src/radiosensitivity_ml/data/qc_report.py",
)


def code_hashes() -> dict[str, str]:
    """SHA-256 of every QC code file, resolved from the repository root; fail if one is missing."""
    hashes = {}
    for name in CODE_FILES:
        path = REPO_ROOT / name
        if not path.is_file():
            raise ProvenanceError(f"QC code file missing: {path}")
        hashes[name] = file_sha256(path)
    return hashes


def git_state() -> dict[str, object]:
    """Commit, dirty flag, hash of the tracked diff, and hashes of untracked files."""

    def git(*args: str) -> str:
        return subprocess.run(
            ["git", "-C", str(REPO_ROOT), *args], capture_output=True, text=True, check=True
        ).stdout

    status = git("status", "--porcelain").strip()
    diff = git("diff", "HEAD") if status else ""
    untracked = git("ls-files", "--others", "--exclude-standard").splitlines()
    return {
        "commit": git("rev-parse", "HEAD").strip(),
        "dirty": bool(status),
        "diff_sha256": hashlib.sha256(diff.encode("utf-8")).hexdigest() if status else None,
        "untracked_sha256": {
            name: file_sha256(REPO_ROOT / name)
            for name in sorted(untracked)
            if (REPO_ROOT / name).is_file()
        },
    }


def package_versions() -> dict[str, str]:
    """Versions of the third-party packages this run imports."""
    versions = {}
    for name in ("PyYAML",):
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            versions[name] = "not_found"
    return versions


def verify_depmap(path: Path) -> None:
    """Fail unless a DepMap file matches its folder's SHA256SUMS entry."""
    expected = listed_sha256(path)
    if expected is None:
        raise ProvenanceError(f"no SHA256SUMS entry for {path}; run python scripts/acquire_data.py")
    if file_sha256(path) != expected:
        raise ProvenanceError(f"SHA-256 mismatch vs SHA256SUMS: {path}")


def load_clarifi(inputs: dict[str, str]) -> tuple[Path, list[qc.ClarifiRecord]]:
    """Verify and parse CLARIFi (identifiers and outcome validity class only)."""
    path = Path(inputs["clarifi"])
    expected = manifest_file_sha256(Path(inputs["clarifi_manifest"]), inputs["clarifi"])
    if file_sha256(path) != expected:
        raise ProvenanceError(f"SHA-256 mismatch vs manifest: {path}")
    _, rows = qc.read_csv(path, qc.CLARIFI_COLUMNS)
    return path, qc.parse_clarifi(rows)


def load_models(path: Path) -> tuple[tuple[str, ...], dict[str, dict[str, str]]]:
    """Parse a verified Model table; return (header, index)."""
    header, rows = qc.read_csv(path, qc.MODEL_COLUMNS)
    return header, qc.index_model_table(rows, header)


INPUT_KEYS = (
    "clarifi",
    "clarifi_manifest",
    "model",
    "default_profiles",
    "omics_profiles",
    "expression",
    "cellosaurus_dir",
)
CHECKED_BY_SHA256SUMS = ("model", "default_profiles", "omics_profiles", "expression")


def check_inputs(config_data: dict) -> dict[str, str]:
    """Status of every configured input, without reading any data beyond checksums."""
    inputs: dict[str, str] = config_data["inputs"]
    status: dict[str, str] = {}
    recorded = config_data.get("cellosaurus", {}).get("complete_json_sha256")
    for key in INPUT_KEYS:
        path = Path(inputs[key])
        if not path.exists():
            status[key] = f"MISSING: {path}"
        elif key in CHECKED_BY_SHA256SUMS:
            expected = listed_sha256(path)
            if expected is None:
                status[key] = f"NOT LISTED in SHA256SUMS: {path}"
            else:
                status[key] = "ok" if file_sha256(path) == expected else f"MISMATCH: {path}"
        elif key == "clarifi":
            try:
                expected = manifest_file_sha256(Path(inputs["clarifi_manifest"]), inputs[key])
            except (ProvenanceError, FileNotFoundError):
                status[key] = f"NO CHECKSUM in {inputs['clarifi_manifest']}"
            else:
                status[key] = "ok" if file_sha256(path) == expected else f"MISMATCH: {path}"
        elif key == "cellosaurus_dir":
            complete = path / "COMPLETE.json"
            if not complete.is_file():
                status[key] = f"INCOMPLETE (no COMPLETE.json): {path}"
            elif recorded and file_sha256(complete) != recorded:
                status[key] = "MISMATCH: COMPLETE.json differs from the recorded SHA-256"
            else:
                status[key] = "ok" if recorded else "present (hash not yet recorded)"
        else:
            status[key] = "present"
    status["cellosaurus.complete_json_sha256"] = (
        "recorded" if recorded else "NOT RECORDED: copy it from acquire_data.py output"
    )
    return status


def main(argv: list[str] | None = None) -> int:
    """Run the identifier QC; turn expected failures into clear one-line errors."""
    try:
        return run(argv)
    except (
        ProvenanceError,
        cs.CellosaurusFormatError,
        qc.IdentifierQCError,
        el.ConfigError,
        FileNotFoundError,
        FileExistsError,
        KeyError,
        yaml.YAMLError,
    ) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        print(
            "No final output folder was created (a failed write leaves only <out>.partial; "
            "delete it). Fix the cause and re-run.",
            file=sys.stderr,
        )
        return 1


def run(argv: list[str] | None = None) -> int:
    """Run the identifier QC (full or model-table audit)."""
    parser = argparse.ArgumentParser(description="Identifier QC (preprocessing step).")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--out", type=Path, default=None, help="new output folder")
    parser.add_argument("--model-table-audit", type=Path, default=None, metavar="MODEL_CSV")
    parser.add_argument("--allow-dirty", action="store_true", help="run on an uncommitted tree")
    parser.add_argument("--check-inputs", action="store_true", help="report input status and exit")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if args.model_table_audit is not None and args.out is None:
        parser.error("--model-table-audit requires --out (a folder separate from the full QC)")
    if args.check_inputs:
        config_data = yaml.safe_load(args.config.read_text(encoding="utf-8"))
        el.config_from_mapping(config_data)
        status = check_inputs(config_data)
        print(json.dumps(status, indent=2))
        return 0 if all(v in {"ok", "present", "recorded"} for v in status.values()) else 1

    started = datetime.now(UTC).isoformat()
    git = git_state()
    if git["dirty"] and not args.allow_dirty:
        print("Working tree is dirty; commit first or pass --allow-dirty.", file=sys.stderr)
        return 2
    config_data = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    config = el.config_from_mapping(config_data)
    inputs: dict[str, str] = config_data["inputs"]
    out = args.out or Path(config_data["output_dir"])

    clarifi_path, clarifi = load_clarifi(inputs)
    used: list[Path] = [args.config, clarifi_path, Path(inputs["clarifi_manifest"])]
    if args.model_table_audit is not None:
        verify_depmap(args.model_table_audit)
        _, models = load_models(args.model_table_audit)
        result = report.run_model_table_audit(clarifi, models)
        used.append(args.model_table_audit)
    else:
        model, profiles, expression = (
            Path(inputs[k]) for k in ("model", "default_profiles", "expression")
        )
        omics_profiles = Path(inputs["omics_profiles"])
        for path in (model, profiles, expression, omics_profiles):
            verify_depmap(path)
        header, models = load_models(model)
        _, profile_rows = qc.read_csv(profiles, qc.DEFAULT_PROFILE_COLUMNS)
        rna_models, profile_types = qc.default_rna_models(profile_rows)
        omics_header, omics_rows = qc.read_csv(omics_profiles)
        strandedness = qc.strandedness_report(
            omics_header, omics_rows, profile_rows, [r.depmap_id for r in clarifi]
        )
        folder = Path(inputs["cellosaurus_dir"])
        recorded = config_data["cellosaurus"].get("complete_json_sha256")
        if not recorded:
            raise ProvenanceError(
                "record the COMPLETE.json SHA-256 in the config (cellosaurus.complete_json_sha256)"
            )
        if file_sha256(folder / "COMPLETE.json") != recorded:
            raise ProvenanceError(f"{folder}/COMPLETE.json differs from the recorded SHA-256")
        records, provenance = cs.load_saved_responses(
            folder,
            str(config_data["cellosaurus"]["expected_release"]),
            [r.depmap_id for r in clarifi],
        )
        provenance = {**provenance, "complete_json_sha256": file_sha256(folder / "COMPLETE.json")}
        qc_inputs = report.QCInputs(
            clarifi=clarifi,
            models=models,
            model_header=header,
            rna_models=rna_models,
            profile_types=profile_types,
            expression_ids=qc.expression_row_ids(expression),
            cellosaurus=records,
            cellosaurus_provenance=provenance,
            strandedness=strandedness,
        )
        result = report.run_identifier_qc(qc_inputs, config)
        used += [
            model,
            profiles,
            omics_profiles,
            expression,
            folder / "COMPLETE.json",
            folder / "release_info.json",
        ]
        used += sorted(folder.glob("*.tsv"))
    input_hashes = {str(p): file_sha256(p) for p in used}  # recorded right after reading

    def build(staging: Path) -> None:
        written = report.write_report(staging, result)
        write_json(
            staging / "run_record.json",
            {
                "script": "scripts/run_preprocessing.py",
                "argv": sys.argv if argv is None else argv,
                "started_utc": started,
                "finished_utc": datetime.now(UTC).isoformat(),
                "git": git,
                "code_sha256": code_hashes(),
                "config_sha256": file_sha256(args.config),
                "seeds": None,
                "lockfile_sha256": None,
                "python": sys.version,
                "packages": package_versions(),
                "platform": platform.platform(),
                "inputs": input_hashes,
                "outputs": {p.name: file_sha256(p) for p in written},
                "note": "Descriptive identifier QC only; no outcome values or statistics.",
            },
        )

    write_once_folder(out, build)
    headline = result.summary.get("feasibility") or result.summary.get("records")
    if isinstance(headline, dict) and "primary" in headline:
        headline = {k: headline["primary"][k] for k in ("n_eligible_components", "T10")}
    print(json.dumps({"out": str(out), "headline": headline}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
