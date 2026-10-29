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
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import joblib
import pandas as pd

from radiosensitivity_ml.config import ExperimentConfig
from radiosensitivity_ml.data.provenance import write_json, write_once_folder
from radiosensitivity_ml.explainability import stability as st
from radiosensitivity_ml.features.gene_sets import GeneSetScorer
from radiosensitivity_ml.models import checkpoints as ck
from radiosensitivity_ml.models.run import ExperimentInputs, code_sha256, prepare_inputs
from radiosensitivity_ml.parallel import execute_tasks, thread_settings

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


@dataclass(frozen=True)
class ImportanceContext:
    """What an importance task needs (sent once to each worker; read-only)."""

    tasks_dir: Path
    features: pd.DataFrame
    n_repeats: int
    base_seed: int


def importance_task(
    context: ImportanceContext, task: tuple[str, int, int, str]
) -> dict[str, float]:
    """Grouped permutation importance of one saved task on its OUTER-TEST rows only.

    Pure: depends only on the saved model, its saved held-out predictions and the task's
    own seed; nothing is refitted.
    """
    key = task[0]
    folder = context.tasks_dir / key
    predictions = pd.read_parquet(folder / "predictions.parquet")
    fitted = joblib.load(folder / "model.joblib")
    rows = predictions["row_number"].to_numpy()
    series = st.permutation_importance(
        fitted,
        context.features.loc[rows],
        predictions["y_true"].to_numpy(),
        predictions["component_id"].to_numpy(),
        context.n_repeats,
        ck.stable_int(context.base_seed, "importance", key),
    )
    return {str(name): float(value) for name, value in series.items()}


def column_name(task: tuple[str, int, int, str]) -> str:
    _, repeat, fold, variant = task
    return f"{variant}|r{repeat}|f{fold}"


def task_importances(
    store: ck.RunStore,
    inputs: ExperimentInputs,
    tasks: list[tuple[str, int, int, str]],
    n_repeats: int,
    base_seed: int,
) -> pd.DataFrame:
    """Importance per feature (rows) for each listed completed task (columns); serial,
    no checkpoints (reference for ``checkpointed_importances``)."""
    context = ImportanceContext(store.tasks_dir, inputs.features, n_repeats, base_seed)
    return pd.DataFrame(
        {column_name(t): pd.Series(importance_task(context, t), name="importance") for t in tasks}
    )


def checkpoint_identity(
    store: ck.RunStore, key: str, n_repeats: int, base_seed: int
) -> dict[str, object]:
    """Everything that determines a task's importance (verified before reuse)."""
    record = json.loads((store.tasks_dir / key / "task_record.json").read_text(encoding="utf-8"))
    return {
        "task_key": key,
        "n_repeats": n_repeats,
        "seed": ck.stable_int(base_seed, "importance", key),
        "model_sha256": record["sha256"]["model.joblib"],
    }


def checkpointed_importances(
    store: ck.RunStore,
    inputs: ExperimentInputs,
    tasks: list[tuple[str, int, int, str]],
    n_repeats: int,
    base_seed: int,
    checkpoint_dir: Path,
    workers: int = 1,
    log: Callable[[str], None] = print,
) -> dict[str, pd.Series]:
    """Importance of every task (by key), computed in ``workers`` processes.

    Each finished task is written by THIS process as an atomic JSON checkpoint holding its
    identity (task key, permutations, seed, SHA-256 of the saved model). On a later call a
    matching checkpoint is reused; a mismatching or unreadable one is moved to
    ``_rejected/`` and recomputed. Results are always read back from the checkpoints in
    task order, so they do not depend on the worker count or completion order.
    """
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    identities = {t[0]: checkpoint_identity(store, t[0], n_repeats, base_seed) for t in tasks}

    def path(key: str) -> Path:
        return checkpoint_dir / f"{key}_p{n_repeats}.json"

    def valid(key: str) -> bool:
        try:
            stored = json.loads(path(key).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        same = all(stored.get(k) == v for k, v in identities[key].items())
        return same and isinstance(stored.get("importance"), dict)

    todo, reused, rejected = [], 0, 0
    for task in tasks:
        if path(task[0]).exists():
            if valid(task[0]):
                reused += 1
                continue
            rejected_dir = checkpoint_dir / "_rejected"
            rejected_dir.mkdir(exist_ok=True)
            stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
            os.replace(path(task[0]), rejected_dir / f"{path(task[0]).name}.{stamp}")
            rejected += 1
        todo.append(task)

    def handle(task: tuple[str, int, int, str], value: dict[str, float], seconds: float) -> None:
        record = {**identities[task[0]], "importance": value}
        ck.atomic_write_text(path(task[0]), json.dumps(record))
        log(f"importance {column_name(task)} ({task[0]}) {seconds:.1f}s")

    log(f"importance: {len(todo)} to compute, {reused} reused, {rejected} rejected")
    started = time.monotonic()
    context = ImportanceContext(store.tasks_dir, inputs.features, n_repeats, base_seed)
    execute_tasks(todo, importance_task, context, workers, handle)  # type: ignore[arg-type]
    with (checkpoint_dir / "sessions.jsonl").open("a", encoding="utf-8") as handle_file:
        session = {
            "ended_utc": datetime.now(UTC).isoformat(),
            "workers": workers,
            "threads": thread_settings(),
            "n_permutations": n_repeats,
            "computed": len(todo),
            "reused": reused,
            "rejected": rejected,
            "wall_clock_seconds": time.monotonic() - started,
            "code_sha256": code_sha256(),
        }
        handle_file.write(json.dumps(session, sort_keys=True) + "\n")
    out = {}
    for task in tasks:
        stored = json.loads(path(task[0]).read_text(encoding="utf-8"))
        out[task[0]] = pd.Series(stored["importance"], name="importance")
    return out


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
    config: ExperimentConfig,
    n_repeats: int = 20,
    tables_root: Path = Path("results/tables"),
    workers: int = 1,
    log: Callable[[str], None] = print,
) -> Path:
    """Compute importance, stability, sign consistency and null tests; returns the folder.

    All importance tasks (real M2, control draws, descriptive models) run in one pass in
    ``workers`` processes, checkpointed per task in
    ``results/tables/<run_id>/explainability_checkpoints/`` so an interrupted call resumes;
    the write-once output folder is built only after every task is done.
    """
    tables_dir = tables_root / config.run_id
    evaluation = require_evaluation(tables_dir, config)
    store = ck.RunStore(config.output_dir / config.run_id)
    manifest = store.load_manifest()
    inputs = prepare_inputs(config, config.population_options)
    families = {
        ("M2", "real"): matching_tasks(manifest, "M2", "real"),
        ("M2", "perm_"): matching_tasks(manifest, "M2", "perm_"),
        ("M2", "randsets_"): matching_tasks(manifest, "M2", "randsets_"),
        **{
            (m, "real"): matching_tasks(manifest, m, "real")
            for m in DESCRIPTIVE_MODELS
            if m in config.models
        },
    }
    unique = list({t[0]: t for tasks in families.values() for t in tasks}.values())
    computed = checkpointed_importances(
        store, inputs, unique, n_repeats, config.base_seed,
        tables_dir / "explainability_checkpoints", workers, log,
    )  # fmt: skip

    def importances(model_id: str, prefix: str) -> pd.DataFrame:
        return pd.DataFrame({column_name(t): computed[t[0]] for t in families[(model_id, prefix)]})

    real_tasks = families[("M2", "real")]
    real = importances("M2", "real")
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
