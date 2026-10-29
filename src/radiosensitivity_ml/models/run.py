"""Experiment engine: grouped nested cross-validation with checkpointed tasks.

Order of operations (protocol §10; leakage controls):
1. load the QC population (metadata only) and build or load the frozen split table;
2. write the split table and its SHA-256 into the run manifest;
3. only then load the outcome;
4. run every task (scale x model x repeat x outer fold x variant): tune on the grouped
   inner folds of the outer-training rows, refit on all outer-training rows, predict the
   outer-test rows, save predictions + fitted model atomically.

All learned operations (gene z-scoring, score scaling, tissue coefficients, residual
models, hyperparameter choice) happen inside ``fit`` on training rows only. Held-out
outcomes are used only to score predictions after the fit.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import traceback
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.preprocessing import StandardScaler

from radiosensitivity_ml.config import ExperimentConfig
from radiosensitivity_ml.data import analysis_table as at
from radiosensitivity_ml.data.provenance import ProvenanceError, file_sha256
from radiosensitivity_ml.evaluation import splits as sp
from radiosensitivity_ml.evaluation.metrics import weighted_mae
from radiosensitivity_ml.features.expression import load_expression
from radiosensitivity_ml.features.gene_sets import (
    EXPECTED_HALLMARK_SETS,
    mapped_sets,
    parse_gmt,
    random_gene_set_collection,
)
from radiosensitivity_ml.models import checkpoints as ck
from radiosensitivity_ml.models.offset import OffsetModel
from radiosensitivity_ml.models.registry import build_model, grid_points
from radiosensitivity_ml.parallel import check_workers, execute_tasks, thread_settings

REPO_ROOT = Path(__file__).resolve().parents[3]
CONTROL_MODELS = {"perm": ("M1", "M2"), "randsets": ("M2",)}


@dataclass
class ExperimentInputs:
    """Everything a task needs except the outcome."""

    population: at.Population
    features: pd.DataFrame  # index row_number: lineage, primary_disease, gene columns
    gene_sets: dict[str, tuple[str, ...]]
    unmapped_genes: dict[str, int]
    inputs_sha256: dict[str, str]


def code_sha256() -> dict[str, str]:
    """Hashes of the package source and the run script (the code version of a run)."""
    files = sorted((REPO_ROOT / "src" / "radiosensitivity_ml").rglob("*.py"))
    files.append(REPO_ROOT / "scripts" / "run_model.py")
    hashes = {str(p.relative_to(REPO_ROOT)): file_sha256(p) for p in files if p.is_file()}
    if len(hashes) < 2:
        raise ProvenanceError(
            f"source files not found under {REPO_ROOT}; run from a source checkout"
        )
    return hashes


def git_state() -> dict[str, object]:
    """Commit and dirty flag (recorded, not compared: code hashes are compared instead)."""
    import subprocess

    def git(*args: str) -> str:
        return subprocess.run(
            ["git", "-C", str(REPO_ROOT), *args], capture_output=True, text=True, check=False
        ).stdout.strip()

    return {"commit": git("rev-parse", "HEAD"), "dirty": bool(git("status", "--porcelain"))}


def prepare_inputs(config: ExperimentConfig, options: Mapping[str, object]) -> ExperimentInputs:
    """Population (no outcome), expression features and verified gene sets."""
    inputs = config.inputs
    population = at.load_population(
        Path(str(inputs["qc_dir"])),
        dict(inputs["qc_sha256"]),  # type: ignore[arg-type]
        config.population,
        min_components=int(options.get("min_components_per_tissue", 10)),  # type: ignore[arg-type]
        stranded_ids=frozenset(options.get("stranded_ids", ())),  # type: ignore[arg-type]
    )
    gmt = Path(str(inputs["gene_sets"]))
    expected_gmt = inputs["gene_sets_sha256"]
    if not expected_gmt:
        raise ProvenanceError("record inputs.gene_sets_sha256 (from acquire_data.py) first")
    if file_sha256(gmt) != expected_gmt:
        raise ProvenanceError(f"{gmt} differs from inputs.gene_sets_sha256")
    raw_sets = parse_gmt(gmt)
    if len(raw_sets) != EXPECTED_HALLMARK_SETS:
        raise ProvenanceError(f"{gmt} has {len(raw_sets)} sets, expected {EXPECTED_HALLMARK_SETS}")
    expression_path = Path(str(inputs["expression"]))
    expression = load_expression(expression_path, list(population.table["depmap_id"]))
    expression.index = population.table.index
    gene_sets, unmapped = mapped_sets(raw_sets, list(expression.columns))
    features = pd.concat([population.table[["lineage", "primary_disease"]], expression], axis=1)
    hashes = {
        **{f"qc/{k}": v for k, v in population.qc_sha256.items()},
        "expression": file_sha256(expression_path),
        "gene_sets": file_sha256(gmt),
        # file bytes only (no outcome value is read here); guards resume against a swapped file
        "clarifi": file_sha256(Path(str(inputs["clarifi"]))),
        "clarifi_manifest": file_sha256(Path(str(inputs["clarifi_manifest"]))),
    }
    return ExperimentInputs(population, features, gene_sets, unmapped, hashes)


def build_splits(
    config: ExperimentConfig, inputs: ExperimentInputs, options: Mapping[str, object]
) -> pd.DataFrame:
    """Split table for this run's tier and population (metadata only)."""
    table = inputs.population.table
    if config.tier == "loto":
        lineages = sorted(table.loc[table["stratum"] != at.STRATUM_POOLED, "lineage"].unique())
        return sp.loto_splits(table, lineages, config.k_inner, config.base_seed)
    if config.population == "retaining_problematic":
        primary = at.load_population(
            Path(str(config.inputs["qc_dir"])),
            dict(config.inputs["qc_sha256"]),  # type: ignore[arg-type]
            "primary",
            min_components=int(options.get("min_components_per_tissue", 10)),  # type: ignore[arg-type]
        )
        base = sp.make_splits(
            primary.table, config.k_outer, config.k_inner, config.repeats, config.base_seed
        )
        added = table.loc[~table.index.isin(primary.table.index)]
        lookup = {c: int(r) for r, c in primary.table["component_id"].items()}
        extended = sp.extend_splits(
            base, added, config.k_outer, config.k_inner, config.base_seed, lookup
        ).reset_index(drop=True)
        sp.check_splits(extended, table)
        return extended
    if config.population == "stranded_excluded":
        primary_options = dict(options)
        full = at.load_population(
            Path(str(config.inputs["qc_dir"])),
            dict(config.inputs["qc_sha256"]),  # type: ignore[arg-type]
            "primary",
            min_components=int(primary_options.get("min_components_per_tissue", 10)),  # type: ignore[arg-type]
        )
        base = sp.make_splits(
            full.table, config.k_outer, config.k_inner, config.repeats, config.base_seed
        )
        dropped = sp.drop_records(base, set(table.index))
        sp.check_splits(dropped, table)
        return dropped
    return sp.make_splits(table, config.k_outer, config.k_inner, config.repeats, config.base_seed)


def task_list(config: ExperimentConfig, context: str, splits: pd.DataFrame) -> list[ck.Task]:
    """Every task of the run, in a fixed order."""
    folds = sorted({(int(r), int(f)) for r, f in splits[["repeat", "outer_fold"]].values})
    tasks = [
        ck.make_task(context, config.base_seed, scale, model, r, f)
        for scale in config.scales
        for model in config.models
        for r, f in folds
    ]
    first_repeat = [(r, f) for r, f in folds if r == 0]
    for kind, count in (
        ("perm", config.controls.get("permuted_outcome", 0)),
        ("randsets", config.controls.get("random_gene_sets", 0)),
    ):
        for index in range(1, count + 1):
            for model in CONTROL_MODELS[kind]:
                for r, f in first_repeat:
                    variant = f"{kind}_{index:04d}"
                    tasks.append(
                        ck.make_task(context, config.base_seed, "raw", model, r, f, variant)
                    )
    return tasks


def manifest(
    config: ExperimentConfig, inputs: ExperimentInputs, splits_sha: str, tasks: list[ck.Task]
) -> dict[str, object]:
    return {
        "run_id": config.run_id,
        "created_utc": datetime.now(UTC).isoformat(),
        "config": dict(config.raw),
        "config_sha256": config.sha256,
        "code_sha256": code_sha256(),
        "inputs_sha256": inputs.inputs_sha256,
        "splits_sha256": splits_sha,
        "environment": ck.environment_record(),
        "git": git_state(),  # recorded only; resume compares code_sha256 instead
        "unmapped_genes_per_set": inputs.unmapped_genes,
        "tasks": [t.key for t in tasks],
        "task_details": {
            t.key: [t.scale, t.model_id, t.repeat, t.fold, t.variant, t.seed] for t in tasks
        },
    }


def context_sha256(config: ExperimentConfig, inputs: ExperimentInputs, splits_sha: str) -> str:
    text = json.dumps(
        [config.sha256, code_sha256(), inputs.inputs_sha256, splits_sha], sort_keys=True
    )
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def permuted_within_tissue(
    y: pd.Series, lineage: pd.Series, component: pd.Series, seed: int
) -> pd.Series:
    """Negative control: outcomes permuted between whole components within each lineage.

    Each component receives the outcome vector of another component of the same lineage
    (records matched by position, cycling for unequal sizes), so related lines move
    together. Seeded by the control draw only, so every fold and model of one draw sees
    the same permutation.
    """
    rng = np.random.default_rng(seed)
    out = y.copy()
    for index in y.groupby(lineage).groups.values():
        members = component.loc[index]
        units = list(dict.fromkeys(members))
        donors = [units[i] for i in rng.permutation(len(units))]
        for target, donor in zip(units, donors, strict=True):
            target_rows = members.index[members == target]
            donor_values = y.loc[members.index[members == donor]].to_numpy()
            for position, row in enumerate(target_rows):
                out.loc[row] = donor_values[position % len(donor_values)]
    return out


def control_seed(base_seed: int, variant: str) -> int:
    """Seed of a negative-control draw: the same for every fold and model of that draw."""
    return ck.stable_int(base_seed, "control", variant)


def inner_errors_reference(
    model: object,
    points: list[dict[str, object]],
    X: pd.DataFrame,
    y: np.ndarray,
    weights: np.ndarray,
    inner_fold: np.ndarray,
    clip: bool,
) -> list[float]:
    """Mean inner-fold weighted MAE per grid point, refitting the whole estimator for
    every point and fold (the original implementation, kept as the independent reference
    for ``inner_errors_cached`` and used for every non-offset model)."""
    means = []
    for params in points:
        errors = []
        for k in sorted(set(inner_fold)):
            train, valid = inner_fold != k, inner_fold == k
            estimator = clone(model).set_params(**params)
            estimator.fit(X.loc[train], y[train], sample_weight=weights[train])
            predicted = estimator.predict(X.loc[valid])
            if clip:
                predicted = np.clip(predicted, 0.0, 1.0)
            errors.append(weighted_mae(y[valid], predicted, weights[valid]))
        means.append(float(np.mean(errors)))
    return means


RESIDUAL_GRID_KEYS = frozenset({"alpha", "l1_ratio"})
BASELINE_PREFIX = "baseline__"


def cacheable(model: object, grid: Mapping[str, list]) -> bool:
    """True for an OffsetModel whose grid varies only the residual model and the baseline
    (then the gene-set scorer and score scaler do not depend on the grid point)."""
    return isinstance(model, OffsetModel) and all(
        key in RESIDUAL_GRID_KEYS or key.startswith(BASELINE_PREFIX) for key in grid
    )


def inner_errors_cached(
    model: OffsetModel,
    points: list[dict[str, object]],
    X: pd.DataFrame,
    y: np.ndarray,
    weights: np.ndarray,
    inner_fold: np.ndarray,
    clip: bool,
) -> list[float]:
    """The numbers of ``inner_errors_reference`` for an OffsetModel, without refitting
    what does not depend on the grid point.

    Per inner fold (training rows only, as in ``OffsetModel.fit``): the gene-set scorer,
    the score scaler and the scaled training and validation scores are computed once; the
    baseline is fitted once per distinct ``baseline__*`` setting; the residual ElasticNet
    is fitted for every grid point. Every step is the same call on the same values, with
    the same order of floating-point operations, as ``OffsetModel.fit`` and ``predict``,
    so the results are bit-identical. Arrays are copied before each fit so that every fit
    receives the values the reference path would give it, even if an estimator modified
    its inputs in place.
    """
    errors: list[list[float]] = [[] for _ in points]
    for k in sorted(set(inner_fold)):
        train, valid = inner_fold != k, inner_fold == k
        X_train, X_valid = X.loc[train], X.loc[valid]
        y_train, w_train = np.asarray(y[train], dtype=float), weights[train]
        scorer = clone(model.scorer).fit(X_train)
        scores = scorer.transform(X_train)
        scaler = StandardScaler().fit(scores)
        z_train = scaler.transform(scores)
        z_valid = scaler.transform(scorer.transform(X_valid))
        baselines: dict[tuple, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
        for i, params in enumerate(points):
            estimator = clone(model).set_params(**params)
            key = tuple(sorted((p, v) for p, v in params.items() if p.startswith(BASELINE_PREFIX)))
            if key not in baselines:
                y_fit, w_fit = y_train.copy(), w_train.copy()
                baseline = clone(estimator.baseline).fit(X_train, y_fit, sample_weight=w_fit)
                baselines[key] = (
                    y_fit - baseline.predict(X_train),
                    baseline.predict(X_valid),
                    w_fit,
                )
            residual, baseline_valid, w_fit = baselines[key]
            enet = estimator.residual_model().fit(
                z_train.copy(), residual.copy(), sample_weight=w_fit.copy()
            )
            predicted = baseline_valid + enet.predict(z_valid)
            if clip:
                predicted = np.clip(predicted, 0.0, 1.0)
            errors[i].append(weighted_mae(y[valid], predicted, weights[valid]))
    return [float(np.mean(e)) for e in errors]


def tune_and_fit(
    model: object,
    grid: Mapping[str, list],
    X: pd.DataFrame,
    y: np.ndarray,
    weights: np.ndarray,
    inner_fold: np.ndarray,
    clip: bool = False,
    cached: bool = True,
) -> tuple[object, dict[str, object], list[dict[str, object]]]:
    """Choose parameters by grouped inner CV (weighted MAE), then refit on all rows.

    ``clip`` applies the same raw-scale prediction clip as the outer evaluation.
    ``cached`` uses ``inner_errors_cached`` where it applies (same numbers, fewer fits);
    ``cached=False`` forces the reference implementation (equivalence tests).
    """
    points = grid_points(grid)
    inner = inner_errors_cached if cached and cacheable(model, grid) else inner_errors_reference
    means = inner(model, points, X, y, weights, inner_fold, clip)  # type: ignore[arg-type]
    scores = []
    best, best_error = None, np.inf
    for params, mean_error in zip(points, means, strict=True):
        scores.append({"params": params, "inner_weighted_mae": mean_error})
        if mean_error < best_error:  # strict: ties keep the earlier (more regularised) point
            best, best_error = params, mean_error
    fitted = clone(model).set_params(**best).fit(X, y, sample_weight=weights)
    return fitted, dict(best or {}), scores


def run_task(
    task: ck.Task,
    config: ExperimentConfig,
    inputs: ExperimentInputs,
    splits: pd.DataFrame,
    outcome: pd.Series,
) -> tuple[pd.DataFrame, object, dict[str, object]]:
    """Fit one task and return (predictions, fitted model, details)."""
    part = splits[(splits["repeat"] == task.repeat) & (splits["outer_fold"] == task.fold)]
    part = part[part["row_number"].isin(outcome.index)]
    train = part[part["role"] == "train"]
    test = part[part["role"] == "test"]
    y = outcome
    population = inputs.population
    available = population.table.loc[outcome.index]
    if task.variant.startswith("perm_"):
        y = permuted_within_tissue(
            outcome, available["lineage"], available["component_id"],
            control_seed(config.base_seed, task.variant),
        )  # fmt: skip
    gene_sets = inputs.gene_sets
    if task.variant.startswith("randsets_"):
        genes = inputs.features.drop(columns=["lineage", "primary_disease"])
        gene_sets = random_gene_set_collection(
            inputs.gene_sets, genes, control_seed(config.base_seed, task.variant)
        )
    # 1/|component| among the records available on this scale (boundary drops respected)
    sizes = available.groupby("component_id")["depmap_id"].transform("size")
    weights_all = (
        (1.0 / sizes) if config.component_weighting else pd.Series(1.0, index=available.index)
    )
    train_rows = train["row_number"].to_numpy()
    test_rows = test["row_number"].to_numpy()
    X_train = inputs.features.loc[train_rows]
    model = build_model(task.model_id, population.lineages, gene_sets, task.seed)
    fitted, best, scores = tune_and_fit(
        model,
        config.grids[task.model_id],
        X_train,
        y.loc[train_rows].to_numpy(dtype=float),
        weights_all.loc[train_rows].to_numpy(dtype=float),
        train["inner_fold"].to_numpy(),
        clip=config.clip_raw_predictions and task.scale == "raw",
    )
    predicted = fitted.predict(inputs.features.loc[test_rows])
    table = population.table.loc[test_rows]
    predictions = pd.DataFrame(
        {
            "row_number": test_rows,
            "depmap_id": table["depmap_id"].to_numpy(),
            "component_id": table["component_id"].to_numpy(),
            "lineage": table["lineage"].to_numpy(),
            "scale": task.scale,
            "model_id": task.model_id,
            "variant": task.variant,
            "repeat": task.repeat,
            "outer_fold": task.fold,
            "y_true": y.loc[test_rows].to_numpy(dtype=float),
            "y_pred": predicted,
        }
    )
    details = {
        "best_params": best,
        "inner_scores": scores,
        "n_train": len(train_rows),
        "n_test": len(test_rows),
        "unseen_tissue_columns": unseen_columns(fitted),
        "estimator_seed": task.seed,
        "control_seed": control_seed(config.base_seed, task.variant)
        if task.variant != "real"
        else None,
    }
    return predictions, fitted, details


def unseen_columns(fitted: object) -> list[str]:
    """Tissue categories absent from the training rows (searched through nested baselines)."""
    node = fitted
    while node is not None:
        if hasattr(node, "unseen_"):
            return list(node.unseen_)
        node = getattr(node, "baseline_", None)
    return []


class RemoteTaskError(RuntimeError):
    """A task failed inside a worker process (message holds the original error)."""


@dataclass(frozen=True)
class TaskContext:
    """Everything a task needs (sent once to each worker process; never written)."""

    config: ExperimentConfig
    inputs: ExperimentInputs
    splits: pd.DataFrame
    outcomes: Mapping[str, pd.Series]


def run_model_task(context: TaskContext, item: tuple[int, ck.Task]) -> tuple[bool, object]:
    """Fit one task (pure: depends only on the context and the task's own seed).

    Returns (True, (predictions, fitted, details)) or (False, (error, traceback)), so a
    failing task is recorded and the run continues, as in the serial runner.
    """
    _, task = item
    try:
        outcome = context.outcomes[task.scale]
        return True, run_task(task, context.config, context.inputs, context.splits, outcome)
    except Exception as exc:  # noqa: BLE001 - returned to the parent and recorded
        return False, (f"{type(exc).__name__}: {exc}", traceback.format_exc())


def run_experiment(
    config: ExperimentConfig,
    options: Mapping[str, object],
    resume: bool,
    log: Callable[[str], None] = print,
    workers: int = 1,
) -> dict[str, int]:
    """Create or resume a run; returns counts of reused, computed, rejected, failed tasks.

    ``workers`` > 1 fits independent tasks (scale x model x repeat x outer fold x variant)
    in a bounded process pool; each worker runs single-threaded BLAS, and the parent alone
    writes task checkpoints (atomic). Every task is determined by its own seed, so results
    do not depend on ``workers``, which is not part of the manifest and may change on
    resume. Each session is appended to ``sessions.jsonl`` (workers, threads, wall clock).
    """
    check_workers(workers)
    store = ck.RunStore(config.output_dir / config.run_id)
    inputs = prepare_inputs(config, options)
    if resume:
        stored = store.load_manifest()
        if stored.get("status") == "initialising":
            raise ck.CheckpointError("the run never finished initialising; start a new run_id")
        splits_sha = str(stored["splits_sha256"])
        splits = store.load_splits(splits_sha)
    else:
        store.create({"run_id": config.run_id, "status": "initialising"})
        splits = build_splits(config, inputs, options)
        splits_sha = store.save_splits(splits)
    context = context_sha256(config, inputs, splits_sha)
    tasks = task_list(config, context, splits)
    current = manifest(config, inputs, splits_sha, tasks)
    if resume:
        differences = store.incompatibilities(current)
        if differences:
            raise ck.CheckpointError(
                f"incompatible checkpoint: {differences} differ from the stored run. "
                "Nothing was changed; start a new run_id."
            )
        log(f"resuming {config.run_id}: discarded {store.discard_partials()} partial task folders")
    else:
        ck.atomic_write_text(store.manifest_path, json.dumps(current, indent=2, sort_keys=True))
        log(f"created {store.root} with {len(tasks)} tasks; splits sha256 {splits_sha}")

    # The outcome is loaded only now, after the split table and its hash are on disk.
    raw = at.load_outcome(
        Path(str(config.inputs["clarifi"])),
        Path(str(config.inputs["clarifi_manifest"])),
        inputs.population,
    )
    outcomes = {}
    for scale in config.scales:
        outcomes[scale], dropped = at.transform_outcome(raw, scale)
        log(
            f"scale {scale}: {len(outcomes[scale])} records ({dropped} dropped at undefined boundaries)"
        )
    check_scale_rows(store.root / "scale_rows.json", outcomes, resume)

    counts = {"reused": 0, "computed": 0, "rejected": 0, "failed": 0}
    write_status(store.root, "running", counts, len(tasks))
    to_compute: list[tuple[int, ck.Task]] = []
    for number, task in enumerate(tasks, start=1):
        outcome = outcomes[task.scale]
        part = splits[(splits["repeat"] == task.repeat) & (splits["outer_fold"] == task.fold)]
        expected = set(
            part.loc[
                (part["role"] == "test") & part["row_number"].isin(outcome.index), "row_number"
            ]
        )
        if store.task_dir(task).exists():
            if store.is_complete(task, expected):
                counts["reused"] += 1
                continue
            log(f"rejected corrupted task {task.key} -> {store.reject(task)}")
            counts["rejected"] += 1
        to_compute.append((number, task))

    def handle(item: tuple[int, ck.Task], result: tuple[bool, object], elapsed: float) -> None:
        number, task = item
        ok, payload = result
        try:
            if not ok:
                error, trace = payload  # type: ignore[misc]
                raise RemoteTaskError(error)
            store.write_task(task, *payload)  # type: ignore[misc]
            counts["computed"] += 1
            status = "done"
        except Exception as exc:  # noqa: BLE001 - recorded and reported; the run continues
            store.record_failure(task, exc, None if ok else trace)
            counts["failed"] += 1
            status = f"FAILED ({exc})"
        log(
            f"[{number}/{len(tasks)}] {task.scale} {task.model_id} r{task.repeat} f{task.fold} "
            f"{task.variant} {status} {elapsed:.1f}s"
        )

    log(f"{len(to_compute)} task(s) to fit with {workers} worker(s)")
    session = {"started_utc": datetime.now(UTC).isoformat(), "workers": workers}
    started = time.monotonic()
    context = TaskContext(config, inputs, splits, outcomes)
    execute_tasks(to_compute, run_model_task, context, workers, handle)  # type: ignore[arg-type]
    complete = counts["failed"] == 0
    write_status(store.root, "complete" if complete else "incomplete", counts, len(tasks))
    append_session(
        store.root,
        {
            **session,
            "ended_utc": datetime.now(UTC).isoformat(),
            "wall_clock_seconds": time.monotonic() - started,
            "logical_cores": os.cpu_count(),
            "threads": thread_settings(),
            "counts": dict(counts),
            "environment": ck.environment_record(),
            "code_sha256": code_sha256(),
            "git": git_state(),
        },
    )
    log(json.dumps(counts))
    return counts


def append_session(root: Path, record: Mapping[str, object]) -> None:
    """Append one line per finished session to sessions.jsonl (provenance; parent only)."""
    with (root / "sessions.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def check_scale_rows(path: Path, outcomes: Mapping[str, pd.Series], resume: bool) -> None:
    """Record (new run) or verify (resume) the row numbers available on each scale.

    Only row numbers are stored, never outcome values.
    """
    current = {scale: sorted(int(r) for r in values.index) for scale, values in outcomes.items()}
    if resume and path.is_file():
        stored = json.loads(path.read_text(encoding="utf-8"))
        if stored != current:
            raise ck.CheckpointError(
                f"{path}: rows available per scale changed since the run began"
            )
        return
    if resume:
        raise ck.CheckpointError(f"{path} is missing; cannot verify the resumed run")
    ck.atomic_write_text(path, json.dumps(current, indent=1, sort_keys=True))


def write_status(root: Path, status: str, counts: Mapping[str, int], n_tasks: int) -> None:
    """run_status.json: 'running', 'complete' (no failures) or 'incomplete'."""
    record = {
        "status": status,
        "updated_utc": datetime.now(UTC).isoformat(),
        "n_tasks": n_tasks,
        "counts": dict(counts),
    }
    ck.atomic_write_text(root / "run_status.json", json.dumps(record, indent=2, sort_keys=True))
