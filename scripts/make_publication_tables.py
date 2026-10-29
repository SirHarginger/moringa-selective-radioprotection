"""Publication tables from saved outputs (INVESTIGATOR-RUN; nothing is refitted).

    python scripts/make_publication_tables.py --config configs/publication.yaml --part core
    python scripts/make_publication_tables.py --config configs/publication.yaml --part triage

core   (after evaluate_models.py): Tables 1-3, S1, within_tissue_spearman_v2, captions.md
       -> results/tables/<run_id>/publication_v<N>/
triage (after generate_triage.py): Tables S2, S3 (with DepMap cell-line names)
       -> results/tables/<run_id>/publication_triage_v<N>/
Write-once folders; every source file is hashed into publication_record.json.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd
import yaml

from radiosensitivity_ml.config import ExperimentConfigError, load_experiment
from radiosensitivity_ml.data.provenance import (
    ProvenanceError,
    file_sha256,
    write_json,
    write_once_folder,
)
from radiosensitivity_ml.evaluation import metrics as mt
from radiosensitivity_ml.evaluation import publication as pub
from radiosensitivity_ml.evaluation.report import completed_predictions
from radiosensitivity_ml.models import checkpoints as ck
from radiosensitivity_ml.models.run import code_sha256
from radiosensitivity_ml.triage.report import cell_line_metadata, load_triage


def verified_names(model_table: Path, checksums: Path) -> pd.Series:
    """DepMap CellLineName by ModelID, after checking Model.csv against SHA256SUMS."""
    expected = {
        line.split()[1]: line.split()[0]
        for line in checksums.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    if expected.get(model_table.name) != file_sha256(model_table):
        raise ProvenanceError(f"{model_table} does not match {checksums}")
    table = pd.read_csv(model_table, usecols=["ModelID", "CellLineName"], dtype=str)
    return table.set_index("ModelID")["CellLineName"]


def core(settings: dict, experiment, tables_dir: Path, if_exists: str = "fail") -> Path:
    sources = {
        name: tables_dir / f"{name}.csv"
        for name in (
            "model_metrics", "comparisons", "per_repeat_delta_mae", "tissue_errors",
            "oof_predictions",
        )
    }  # fmt: skip
    tables = {name: pd.read_csv(path) for name, path in sources.items()}
    store = ck.RunStore(experiment.output_dir / experiment.run_id)
    predictions = mt.prepare(
        completed_predictions(store, experiment), experiment.clip_raw_predictions
    )
    meta = cell_line_metadata(experiment)
    minimum = int(settings["min_components"])
    out = tables_dir / f"publication_v{int(settings['version'])}"
    record = {
        "part": "core",
        "run_id": experiment.run_id,
        "experiment_config_sha256": experiment.sha256,
        "publication_config": settings,
        "source_sha256": {k: file_sha256(p) for k, p in sources.items()},
        "run_manifest_sha256": file_sha256(store.manifest_path),
        "code_sha256": code_sha256(),
        "inference_status": pub.STATUS,
    }
    if out.exists() and if_exists == "verify-and-skip" and reuse_existing(out, record, "core"):
        return out

    def build(staging: Path) -> None:
        pub.dataset_composition(meta).to_csv(
            staging / "table_1_dataset_composition.csv", index=False
        )
        pub.model_comparison(
            tables["model_metrics"], tables["comparisons"], tables["per_repeat_delta_mae"]
        ).to_csv(staging / "table_2_model_comparison.csv", index=False)
        pub.tissue_performance(tables["tissue_errors"], minimum).to_csv(
            staging / "table_3_tissue_performance.csv", index=False
        )
        pub.repeat_differences(tables["per_repeat_delta_mae"]).to_csv(
            staging / "table_s1_repeat_delta_mae.csv", index=False
        )
        pub.spearman_table(predictions, tables["oof_predictions"], minimum).to_csv(
            staging / "within_tissue_spearman_v2.csv", index=False
        )
        (staging / "captions.md").write_text(
            pub.CAPTIONS.format(
                run_id=experiment.run_id, n_components=meta["component_id"].nunique(),
                n_records=len(meta), status=pub.STATUS, min_components=minimum,
                pathway_limit=pub.PATHWAY_LIMIT,
            ),
            encoding="utf-8",
        )  # fmt: skip
        write_json(staging / "publication_record.json", record)

    write_once_folder(out, build)
    return out


# Fields of publication_record.json that must match for an existing folder to count as a
# current reproduction of what would be written now. code_sha256 is deliberately NOT in
# this list: it changes whenever any module in the package changes, including modules that
# have nothing to do with these tables. A code change is reported instead, so the
# investigator can decide whether to bump `version`.
VERIFIED_FIELDS = (
    "part",
    "run_id",
    "experiment_config_sha256",
    "source_sha256",
    "publication_config",
)
EXPECTED_FILES = {
    "core": (
        "table_1_dataset_composition.csv",
        "table_2_model_comparison.csv",
        "table_3_tissue_performance.csv",
        "table_s1_repeat_delta_mae.csv",
        "within_tissue_spearman_v2.csv",
        "captions.md",
        "publication_record.json",
    ),
    "triage": (
        "table_s2_gene_set_ranking.csv",
        "table_s3_discrepancy_review.csv",
        "publication_record.json",
    ),
}


class StaleOutputError(RuntimeError):
    """An existing write-once folder does not match what would be written now."""


def reuse_existing(out: Path, record: dict, part: str) -> bool:
    """True when ``out`` already holds a complete set of tables built from these inputs.

    Raises ``StaleOutputError`` when the folder exists but is incomplete or was built
    from different inputs: a write-once output is never deleted or overwritten here, and a
    stale one must be resolved deliberately by bumping `version` in the configuration.
    """
    record_path = out / "publication_record.json"
    if not record_path.is_file():
        raise StaleOutputError(
            f"{out} exists but has no publication_record.json, so it cannot be verified. "
            f"Inspect it, then either remove it deliberately or bump `version`."
        )
    absent = [name for name in EXPECTED_FILES[part] if not (out / name).is_file()]
    if absent:
        raise StaleOutputError(
            f"{out} is incomplete, absent: {', '.join(absent)}. Bump `version` to rebuild."
        )
    stored = json.loads(record_path.read_text(encoding="utf-8"))
    differences = [
        f"{field}: recorded != current"
        for field in VERIFIED_FIELDS
        if stored.get(field) != record.get(field)
    ]
    if differences:
        raise StaleOutputError(
            f"{out} was built from different inputs or settings ({'; '.join(differences)}). "
            f"The existing tables are NOT overwritten. Bump `version` in the configuration "
            f"to build a new set beside them."
        )
    if stored.get("code_sha256") != record.get("code_sha256"):
        print(
            f"NOTE: {out} matches on every data input and setting, but the package code "
            f"has changed since it was written. Reusing it. Bump `version` if these tables "
            f"must be rebuilt with the current code.",
            file=sys.stderr,
        )
    return True


def triage(settings: dict, experiment, tables_dir: Path, if_exists: str = "fail") -> Path:
    triage_config = load_triage(Path(settings["triage_config"]))
    folder = triage_config.output_dir / experiment.run_id
    sources = {
        "pathway_candidates": folder / "pathway_candidates.csv",
        "discrepancy_review": folder / "discrepancy_review.csv",
        "triage_manifest": folder / "triage_manifest.json",
    }
    missing = [str(p) for p in sources.values() if not p.is_file()]
    if missing:
        raise FileNotFoundError(f"run generate_triage.py first; missing {missing}")
    names = verified_names(Path(settings["depmap_model_table"]), Path(settings["depmap_checksums"]))
    s2 = pub.gene_set_table(pd.read_csv(sources["pathway_candidates"]))
    s3 = pub.discrepancy_table(
        pd.read_csv(sources["discrepancy_review"]), names, dict(settings["context_lines"])
    )
    out = tables_dir / f"publication_triage_v{int(settings['version'])}"
    record = {
        "part": "triage",
        "run_id": experiment.run_id,
        "experiment_config_sha256": experiment.sha256,
        "publication_config": settings,
        "source_sha256": {k: file_sha256(p) for k, p in sources.items()},
        "depmap_model_table_sha256": file_sha256(Path(settings["depmap_model_table"])),
        "code_sha256": code_sha256(),
        "inference_status": pub.STATUS,
    }
    if out.exists() and if_exists == "verify-and-skip" and reuse_existing(out, record, "triage"):
        return out

    def build(staging: Path) -> None:
        s2.to_csv(staging / "table_s2_gene_set_ranking.csv", index=False)
        s3.to_csv(staging / "table_s3_discrepancy_review.csv", index=False)
        write_json(staging / "publication_record.json", record)

    write_once_folder(out, build)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--part", choices=("core", "triage"), required=True)
    parser.add_argument(
        "--if-exists", choices=("fail", "verify-and-skip"), default="fail",
        help="fail (default): refuse to touch an existing write-once folder. "
             "verify-and-skip: reuse it when it is complete and was built from exactly "
             "these inputs and settings, and fail if it is incomplete or stale. Nothing "
             "is ever deleted or overwritten.",
    )  # fmt: skip
    args = parser.parse_args(argv)
    try:
        settings = yaml.safe_load(args.config.read_text(encoding="utf-8"))
        experiment = load_experiment(Path(settings["experiment_config"]))
        tables_dir = Path(settings["tables_root"]) / experiment.run_id
        existed = (
            tables_dir
            / (
                f"publication_v{int(settings['version'])}"
                if args.part == "core"
                else f"publication_triage_v{int(settings['version'])}"
            )
        ).exists()
        out = (core if args.part == "core" else triage)(
            settings, experiment, tables_dir, args.if_exists
        )
    except (
        ExperimentConfigError, ProvenanceError, ck.CheckpointError, FileExistsError,
        FileNotFoundError, KeyError, ValueError, StaleOutputError,
    ) as exc:  # fmt: skip
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    if existed and args.if_exists == "verify-and-skip":
        print(f"verified and reused {out} (complete and built from these exact inputs)")
    else:
        print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
