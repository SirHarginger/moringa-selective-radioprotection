"""Evaluate a completed run: comparisons, model metrics, tissue errors, controls.

Refuses to run unless every task listed in the run manifest is complete and passes
its integrity checks. Writes write-once tables to ``results/tables/<run_id>/``.
Inference wording follows protocol §3 (Option B): only the primary comparison (M2 vs
M1, raw scale) receives a verdict, and only with an adopted interval method whose
decision file matches the config: "gain shown" (one-sided LB > 0) or "no gain shown".
Every other comparison, scale and population is descriptive. Biological or clinical
meaningfulness is never claimed.

Descriptive-only route (``inference.method: not_assessable``, D04.06): no simulation
decision exists, so no interval column is written (candidate intervals are unvalidated)
and the primary comparison reads "superiority not formally assessed". Estimates,
per-repeat values and metrics are reported as usual.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from radiosensitivity_ml.config import ExperimentConfig
from radiosensitivity_ml.data.provenance import file_sha256, write_json, write_once_folder
from radiosensitivity_ml.evaluation import intervals as iv
from radiosensitivity_ml.evaluation import metrics as mt
from radiosensitivity_ml.models import checkpoints as ck

# (label, model A, comparator B): A is the richer model; positive dMAE = A better.
COMPARISONS = (
    ("primary: tissue+expression vs tissue", "M2", "M1"),
    ("S1: beyond tissue+proliferation", "M2P", "M1P"),
    ("S3: random forest vs tissue", "M3", "M1"),
    ("exploratory: random forest vs global mean", "M3", "M0"),
    ("tier b: expression-only vs global mean", "M2X", "M0"),
)


PRIMARY = ("M2", "M1", "raw")
NOT_ASSESSED = "descriptive only: superiority not formally assessed"


class EvaluationError(ValueError):
    """Raised when the run, config or decision file do not match."""


def completed_predictions(store: ck.RunStore, config: ExperimentConfig) -> pd.DataFrame:
    """Predictions of all tasks, after checking the config and that every task is complete.

    Each task must hold exactly its outer-test rows that are available on its scale
    (``scale_rows.json``, written by the run; row numbers only).
    """
    manifest = store.load_manifest()
    if manifest.get("config_sha256") != config.sha256:
        raise EvaluationError("this config differs from the one recorded in run_manifest.json")
    scale_rows_path = store.root / "scale_rows.json"
    if not scale_rows_path.is_file():
        raise EvaluationError(f"{scale_rows_path} is missing; the run never loaded its outcome")
    scale_rows = {
        s: set(r) for s, r in json.loads(scale_rows_path.read_text(encoding="utf-8")).items()
    }
    details = manifest["task_details"]
    splits = store.load_splits(str(manifest["splits_sha256"]))
    incomplete = []
    for key in manifest["tasks"]:
        scale, model, repeat, fold, variant, seed = details[key]
        task = ck.Task(scale, model, repeat, fold, variant, seed, key)
        part = splits[(splits["repeat"] == repeat) & (splits["outer_fold"] == fold)]
        expected = set(part.loc[part["role"] == "test", "row_number"]) & scale_rows[scale]
        if not store.is_complete(task, expected):
            incomplete.append(key)
    if incomplete:
        raise ck.CheckpointError(
            f"{len(incomplete)} tasks are missing or invalid; run run_model.py --resume first"
        )
    return store.load_predictions(list(manifest["tasks"]))


def verify_decision(config: ExperimentConfig) -> dict[str, object] | None:
    """Check the simulation decision file named in the config; None if no method adopted.

    The file's hash, adopted method and repeat count must all match the config.
    """
    if config.interval_method == "not_assessable":
        return None
    if config.decision_file is None or config.decision_sha256 is None:
        raise EvaluationError(
            "an adopted interval method needs inference.decision_file and _sha256"
        )
    if file_sha256(config.decision_file) != config.decision_sha256:
        raise EvaluationError(f"{config.decision_file} differs from inference.decision_sha256")
    decision = json.loads(config.decision_file.read_text(encoding="utf-8"))
    if decision.get("adopted_method") != config.interval_method:
        raise EvaluationError("inference.method differs from the decision file's adopted_method")
    if decision.get("repeats") != config.repeats:
        raise EvaluationError("validation.repeats differs from the decision file's repeats")
    return decision


def verdict(interval: iv.Interval | None, primary: bool) -> str:
    """Option B wording. Only the primary comparison gets a verdict; the rest is descriptive."""
    if not primary:
        return "descriptive (not a confirmatory comparison)"
    if interval is None:
        return NOT_ASSESSED
    if interval.lower > 0:
        return "gain shown (one-sided LB > 0)"
    return "no gain shown"


def compare(
    predictions: pd.DataFrame, config: ExperimentConfig
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """One row per (comparison, scale): estimate, intervals, verdict; plus per-repeat values.

    With ``not_assessable`` no interval column is written (none is validated).
    """
    rows, repeats = [], []
    present = set(predictions["model_id"])
    write_intervals = config.interval_method != "not_assessable"
    for label, a, b in COMPARISONS:
        if not {a, b} <= present:
            continue
        for scale in config.scales:
            diffs = mt.paired_differences(predictions, a, b, scale)
            summary = mt.delta_mae(diffs)
            candidates = {
                i.method: i for i in iv.candidate_intervals(summary, config.alpha_one_sided)
            }
            adopted = candidates.get(config.interval_method)
            is_primary = (
                (a, b, scale) == PRIMARY
                and config.population == "primary"
                and config.tier == "within"
            )
            row = {
                "comparison": label,
                "model": a,
                "comparator": b,
                "scale": scale,
                "delta_mae": summary["estimate"],
                "record_weighted_delta_mae": summary["record_weighted_estimate"],
                "n_components": summary["n_components"],
                "n_records": summary["n_records"],
                "repeats": summary["repeats"],
                "adopted_method": config.interval_method,
                "verdict": verdict(adopted, is_primary),
            }
            for name, interval in candidates.items() if write_intervals else ():
                row[f"{name}_lower"] = interval.lower
                row[f"{name}_upper"] = interval.upper
            rows.append(row)
            per_repeat = summary["per_repeat"].rename("delta_mae").reset_index()
            per_repeat[["comparison", "scale"]] = label, scale
            repeats.append(per_repeat)
    return pd.DataFrame(rows), pd.concat(repeats, ignore_index=True) if repeats else pd.DataFrame()


def control_table(predictions: pd.DataFrame) -> pd.DataFrame:
    """Null dMAE (M2 vs M1, raw, repeat 0) for each negative-control variant."""
    real = predictions[predictions["variant"] == "real"]
    rows = []
    for variant in sorted(set(predictions["variant"]) - {"real"}):
        part = predictions[predictions["variant"] == variant]
        if variant.startswith("randsets_"):  # comparator: the real M1 predictions
            m1 = real[(real["model_id"] == "M1") & (real["repeat"] == 0) & (real["scale"] == "raw")]
            part = pd.concat([part, m1.assign(variant=variant)])
        diffs = mt.paired_differences(part, "M2", "M1", "raw", variant)
        rows.append({"variant": variant, "delta_mae": mt.delta_mae(diffs)["estimate"]})
    return pd.DataFrame(rows, columns=["variant", "delta_mae"])


def loto_table(predictions: pd.DataFrame) -> pd.DataFrame:
    """Tier (b): per held-out lineage, dMAE (M2X vs M0) and within-lineage Spearman."""
    diffs = mt.paired_differences(predictions, "M2X", "M0", "raw")
    oof = mt.oof_mean_predictions(predictions, "raw")
    rows = []
    for lineage, part in diffs.groupby("lineage"):
        held = oof[(oof["model_id"] == "M2X") & (oof["lineage"] == lineage)]
        rho = (
            held[["y_true", "y_pred"]].corr(method="spearman").iloc[0, 1]
            if len(held) > 2
            else float("nan")
        )
        rows.append(
            {
                "held_out_lineage": lineage,
                "delta_mae_vs_global_mean": mt.delta_mae(part)["estimate"],
                "mean_prediction_shift": float(held["y_pred"].mean() - held["y_true"].mean()),
                "within_lineage_spearman": float(rho),
                "n_components": int(part["component_id"].nunique()),
            }
        )
    return pd.DataFrame(rows)


def evaluate_run(config: ExperimentConfig, tables_root: Path = Path("results/tables")) -> Path:
    """Write the evaluation tables for a finished run; returns the output folder."""
    store = ck.RunStore(config.output_dir / config.run_id)
    decision = verify_decision(config)
    predictions = mt.prepare(completed_predictions(store, config), config.clip_raw_predictions)
    comparisons, per_repeat = compare(predictions, config)
    model_rows = [
        {"model_id": m, "scale": s, **mt.model_metrics(predictions, m, s)}
        for m in sorted(set(predictions["model_id"]))
        for s in config.scales
    ]
    oof = mt.oof_mean_predictions(predictions, "raw") if "raw" in config.scales else pd.DataFrame()
    controls = control_table(predictions)
    spearman = (
        pd.concat(
            [
                mt.within_tissue_spearman(oof, m).assign(model_id=m)
                for m in sorted(set(oof["model_id"]))
            ]
        )
        if not oof.empty
        else pd.DataFrame()
    )
    out = tables_root / config.run_id

    def build(staging: Path) -> None:
        comparisons.to_csv(staging / "comparisons.csv", index=False)
        per_repeat.to_csv(staging / "per_repeat_delta_mae.csv", index=False)
        pd.DataFrame(model_rows).to_csv(staging / "model_metrics.csv", index=False)
        if "raw" in config.scales:
            mt.tissue_errors(predictions, "raw").to_csv(staging / "tissue_errors.csv", index=False)
            oof.to_csv(staging / "oof_predictions.csv", index=False)
            spearman.to_csv(staging / "within_tissue_spearman.csv", index=False)
        controls.to_csv(staging / "negative_controls.csv", index=False)
        if config.tier == "loto":
            loto_table(predictions).to_csv(staging / "held_out_tissue.csv", index=False)
        write_json(
            staging / "evaluation_record.json",
            {
                "run_id": config.run_id,
                "config_sha256": config.sha256,
                "interval_method": config.interval_method,
                "inference_status": (
                    "superiority not formally assessed (descriptive only; no simulation-"
                    "adopted interval; D04.06)"
                    if decision is None
                    else "simulation-adopted interval"
                ),
                "decision_file": None if decision is None else str(config.decision_file),
                "decision_sha256": config.decision_sha256,
                "alpha_one_sided": config.alpha_one_sided,
                "clip_raw_predictions": config.clip_raw_predictions,
                "run_manifest_sha256": file_sha256(store.manifest_path),
                "splits_sha256": json.loads(store.manifest_path.read_text())["splits_sha256"],
                "note": "Estimation-focused (protocol Option B). No claim of biological or "
                "clinical meaningfulness.",
            },
        )

    write_once_folder(out, build)
    return out
