"""Explainability for a completed, evaluated run (investigator-run; saved models only).

For every real-data raw-scale task of the primary expression model (M2) the saved model
is loaded and grouped permutation importance is computed on its outer-test rows. Null
importances come from the negative-control tasks (permuted outcome; random gene sets,
which keep the real set names so nulls align by set). Coefficient sign consistency of
M2 is reported across tasks. M2P and M3 importances are descriptive only (no null
tests). Writes write-once tables to ``results/tables/<run_id>/explainability/``.

Requires the evaluation folder of the same run and config (``evaluation_record.json``).
"""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import pandas as pd

from radiosensitivity_ml.config import ExperimentConfig
from radiosensitivity_ml.data.provenance import write_json, write_once_folder
from radiosensitivity_ml.explainability import stability as st
from radiosensitivity_ml.features.gene_sets import GeneSetScorer
from radiosensitivity_ml.models import checkpoints as ck
from radiosensitivity_ml.models.run import ExperimentInputs, prepare_inputs

DESCRIPTIVE_MODELS = ("M2P", "M3")


class ExplainabilityError(ValueError):
    """Raised when the evaluation record is missing or belongs to another config."""


def require_evaluation(tables_dir: Path, config: ExperimentConfig) -> dict[str, object]:
    """The evaluation record of this run, checked against the current config."""
    path = tables_dir / "evaluation_record.json"
    if not path.is_file():
        raise ExplainabilityError(f"{path} is missing; run evaluate_models.py first")
    record = json.loads(path.read_text(encoding="utf-8"))
    if record.get("config_sha256") != config.sha256 or record.get("run_id") != config.run_id:
        raise ExplainabilityError(f"{path} was produced with a different config or run_id")
    return record


def matching_tasks(
    manifest: dict[str, object], model_id: str, variant_prefix: str
) -> list[tuple[str, int, int, str]]:
    """(key, repeat, fold, variant) of raw-scale tasks of one model and variant family."""
    out = []
    for key in manifest["tasks"]:  # type: ignore[union-attr]
        scale, model, repeat, fold, variant, _seed = manifest["task_details"][key]  # type: ignore[index]
        if model == model_id and scale == "raw" and variant.startswith(variant_prefix):
            out.append((key, int(repeat), int(fold), variant))
    return out


def task_importances(
    store: ck.RunStore,
    inputs: ExperimentInputs,
    tasks: list[tuple[str, int, int, str]],
    n_repeats: int,
    base_seed: int,
) -> pd.DataFrame:
    """Importance per feature (rows) for each listed completed task (columns)."""
    columns = {}
    for key, repeat, fold, variant in tasks:
        folder = store.tasks_dir / key
        predictions = pd.read_parquet(folder / "predictions.parquet")
        fitted = joblib.load(folder / "model.joblib")
        rows = predictions["row_number"].to_numpy()
        columns[f"{variant}|r{repeat}|f{fold}"] = st.permutation_importance(
            fitted,
            inputs.features.loc[rows],
            predictions["y_true"].to_numpy(),
            predictions["component_id"].to_numpy(),
            n_repeats,
            ck.stable_int(base_seed, "importance", key),
        )
    return pd.DataFrame(columns)


def coefficient_signs(store: ck.RunStore, tasks: list[tuple[str, int, int, str]]) -> pd.DataFrame:
    """Per gene set: share of tasks with a positive, negative or zero M2 coefficient."""
    coefs = {}
    for key, repeat, fold, variant in tasks:
        fitted = joblib.load(store.tasks_dir / key / "model.joblib")
        coefs[f"{variant}|r{repeat}|f{fold}"] = pd.Series(
            fitted.enet_.coef_, index=fitted.feature_names_
        )
    table = pd.DataFrame(coefs)
    return pd.DataFrame(
        {
            "share_positive": (table > 0).mean(axis=1),
            "share_negative": (table < 0).mean(axis=1),
            "share_zero": (table == 0).mean(axis=1),
            "median_coefficient": table.median(axis=1),
            "n_tasks": table.shape[1],
        }
    )


def score_correlation(inputs: ExperimentInputs) -> pd.DataFrame:
    """Spearman correlation of gene-set scores over the eligible lines (features only).

    Shows which sets carry overlapping information, so importance may be shared or
    split between them. No outcome and no model is used.
    """
    genes = inputs.features.drop(columns=["lineage", "primary_disease"])
    scores = GeneSetScorer(inputs.gene_sets).fit(genes).transform(genes)
    return scores.corr(method="spearman")


def primary_gate_passed(tables_dir: Path) -> bool:
    """True only if evaluation recorded 'gain shown' for the primary raw comparison."""
    path = tables_dir / "comparisons.csv"
    if not path.is_file():
        return False
    table = pd.read_csv(path)
    row = table[
        (table["model"] == "M2") & (table["comparator"] == "M1") & (table["scale"] == "raw")
    ]
    return bool(len(row) == 1 and str(row["verdict"].iloc[0]).startswith("gain shown"))


def per_draw(importance: pd.DataFrame, index: pd.Index, n_folds: int) -> pd.DataFrame:
    """Mean importance over the outer folds of repeat 0 for each control draw.

    Every draw must have all ``n_folds`` folds and no missing value, so each null
    statistic is the same equal-weight fold mean as the tested real statistic.
    """
    if importance.empty:
        return pd.DataFrame(index=index)
    draws = importance.T.groupby(lambda c: c.split("|")[0])
    sizes = draws.size()
    incomplete = list(sizes.index[sizes != n_folds])
    if incomplete or importance.isna().to_numpy().any():
        raise ck.CheckpointError(
            f"control draws incomplete or with missing importance: {incomplete[:5]}; "
            "finish the run with --resume first"
        )
    return draws.mean().T


def explain_run(
    config: ExperimentConfig, n_repeats: int = 20, tables_root: Path = Path("results/tables")
) -> Path:
    """Compute importance, stability, sign consistency and null tests; returns the folder."""
    tables_dir = tables_root / config.run_id
    evaluation = require_evaluation(tables_dir, config)
    store = ck.RunStore(config.output_dir / config.run_id)
    manifest = store.load_manifest()
    inputs = prepare_inputs(config, config.population_options)

    def importances(model_id: str, prefix: str) -> pd.DataFrame:
        tasks = matching_tasks(manifest, model_id, prefix)
        return task_importances(store, inputs, tasks, n_repeats, config.base_seed)

    real_tasks = matching_tasks(manifest, "M2", "real")
    real = task_importances(store, inputs, real_tasks, n_repeats, config.base_seed)
    if real.empty:
        raise ck.CheckpointError("no completed real M2 tasks to explain")
    first_repeat = real[[c for c in real.columns if "|r0|" in c]]
    if first_repeat.shape[1] != config.k_outer:
        raise ck.CheckpointError("repeat 0 of the real M2 run is incomplete")
    gate = primary_gate_passed(tables_dir)
    null_permuted = per_draw(importances("M2", "perm_"), real.index, config.k_outer)
    null_random = per_draw(importances("M2", "randsets_"), real.index, config.k_outer)
    tests = st.gene_set_tests(
        first_repeat.mean(axis=1), null_permuted, null_random, gate, config.bh_q
    )
    signs = coefficient_signs(store, real_tasks)
    descriptive = {m: importances(m, "real") for m in DESCRIPTIVE_MODELS if m in config.models}
    correlation = score_correlation(inputs)

    def build(staging: Path) -> None:
        real.to_csv(staging / "importance_per_task.csv")
        correlation.to_csv(staging / "gene_set_score_correlation.csv")
        tests.to_csv(staging / "gene_set_tests.csv")
        signs.to_csv(staging / "coefficient_signs.csv")
        for model_id, table in descriptive.items():
            summary = pd.DataFrame(
                {"mean_importance": table.mean(axis=1), "sd_importance": table.std(axis=1, ddof=1)}
            )
            summary.to_csv(staging / f"importance_descriptive_{model_id}.csv")
        write_json(
            staging / "stability.json",
            {
                "run_id": config.run_id,
                "config_sha256": config.sha256,
                "evaluation_run_manifest_sha256": evaluation.get("run_manifest_sha256"),
                "stability_all_real_tasks": st.stability(real),
                "stability_descriptive": {
                    m: st.stability(t) for m, t in descriptive.items() if t.shape[1] > 1
                },
                "primary_gate_passed": gate,
                "bh_q": config.bh_q,
                "permutations_per_feature": n_repeats,
                "n_null_draws_completed": {
                    "permuted_outcome": int(null_permuted.shape[1]),
                    "random_gene_sets": int(null_random.shape[1]),
                },
                "minimum_attainable_p": (
                    1 / (1 + min(null_permuted.shape[1], null_random.shape[1]))
                    if min(null_permuted.shape[1], null_random.shape[1]) > 0
                    else None
                ),
                "g_stab_feasible": bool(tests["g_stab_feasible"].all()),
                "min_null_draws": st.MIN_NULL_DRAWS,
                "note": "Attribution statements require attribution_permitted == True; worded "
                "'associated in-model, hypothesis-generating'. Stability describes these splits "
                "of this population only. M2P/M3 importances are descriptive.",
            },
        )

    out = tables_dir / "explainability"
    write_once_folder(out, build)
    return out
