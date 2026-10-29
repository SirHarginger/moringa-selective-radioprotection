"""Equivalence tests for the Phase 04 simulation performance changes (D04.05).

SYNTHETIC SOFTWARE-TEST DATA ONLY: every population, expression matrix, gene set and
outcome below is invented in memory; nothing here is a scientific result.

What is checked:
- cached inner-loop tuning (``inner_errors_cached``) against the original loop kept as
  ``inner_errors_reference``: same fold training rows, no validation row in any fit,
  identical inner errors, identical selected parameters, identical predictions;
- the task executor: serial and parallel give the same results, in-flight tasks are
  bounded, errors stop the run;
- the study: serial vs parallel, repeated runs, and resume give byte-identical
  checkpoints and summaries.

Tolerance: ZERO. The cached path performs the same floating-point operations in the
same order as the reference, so errors, predictions and checkpoint bytes must be
identical (``==`` / ``assert_array_equal`` / byte comparison), not merely close.

Tests marked ``model_fit`` fit small estimators and are run by the investigator only
(``python -m pytest -m model_fit tests/test_simulation_performance.py``).
"""

from __future__ import annotations

import operator
import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from radiosensitivity_ml.config import experiment_from_mapping
from radiosensitivity_ml.data import analysis_table as at
from radiosensitivity_ml.evaluation import splits as sp
from radiosensitivity_ml.features.gene_sets import PROLIFERATION_SETS, GeneSetScorer
from radiosensitivity_ml.models import checkpoints as ck
from radiosensitivity_ml.models.baselines import TissueRidge
from radiosensitivity_ml.models.offset import OffsetModel
from radiosensitivity_ml.models.registry import build_model, grid_points
from radiosensitivity_ml.models.run import (
    ExperimentInputs,
    cacheable,
    inner_errors_cached,
    inner_errors_reference,
    tune_and_fit,
)
from radiosensitivity_ml.parallel import check_workers, execute_tasks
from radiosensitivity_ml.simulation.study import run_study, study_from_mapping

# Grids of configs/experiment.yaml (M2: the full 36-point grid).
GRIDS = {
    "M1P": {"alpha": [0.1, 0.01], "baseline__alpha": [100.0, 1.0], "l1_ratio": [0.5]},
    "M2": {
        "alpha": [0.1, 0.01, 0.001],
        "baseline__alpha": [100.0, 10.0, 1.0, 0.1],
        "l1_ratio": [0.9, 0.5, 0.1],
    },
    "M2P": {
        "alpha": [0.1, 0.01],
        "baseline__alpha": [0.1, 0.001],
        "baseline__baseline__alpha": [100.0, 1.0],
        "l1_ratio": [0.9, 0.1],
    },
    "M2X": {"alpha": [0.1, 0.001], "l1_ratio": [0.9, 0.5]},
}


# ------------------------------------------------------------------ fixtures


def synthetic_inputs(n_components: int = 24, n_genes: int = 60, seed: int = 0) -> ExperimentInputs:
    """SYNTHETIC inputs with the real layout (3 lineages, some two-record components)."""
    rng = np.random.default_rng(seed)
    rows, row = [], 2
    for c in range(n_components):
        lineage = ["L_A", "L_B", "L_C"][c % 3]
        for _ in range(2 if c % 7 == 0 else 1):
            rows.append(
                {
                    "row_number": row, "depmap_id": f"ACH-9{row:05d}",
                    "component_id": f"G:{c:03d}", "lineage": lineage,
                    "primary_disease": f"{lineage}_d",
                }
            )  # fmt: skip
            row += 1
    table = pd.DataFrame(rows).set_index("row_number")
    table["stratum"] = at.stratum_labels(table, 3)
    genes = [f"GENE{i}" for i in range(n_genes)]
    expression = pd.DataFrame(
        rng.normal(5, 1, size=(len(table), n_genes)), index=table.index, columns=genes
    )
    names = [*PROLIFERATION_SETS, *(f"HALLMARK_S{i}" for i in range(48))]
    gene_sets = {
        n: tuple(genes[j] for j in sorted(rng.choice(n_genes, 6, replace=False))) for n in names
    }
    features = pd.concat([table[["lineage", "primary_disease"]], expression], axis=1)
    return ExperimentInputs(
        at.Population(table, "primary", {}), features, gene_sets, dict.fromkeys(names, 0),
        {"SYNTHETIC": "0" * 64},
    )  # fmt: skip


def tuning_problem(seed: int = 1) -> dict[str, object]:
    """SYNTHETIC outer-training rows: features, outcome, weights, grouped inner folds."""
    inputs = synthetic_inputs(seed=seed)
    table = inputs.population.table
    rng = np.random.default_rng(seed)
    splits = sp.make_splits(table, 3, 3, 1, seed)
    part = splits[(splits["repeat"] == 0) & (splits["outer_fold"] == 0)]
    train = part[part["role"] == "train"]
    rows = train["row_number"].to_numpy()
    test_rows = part.loc[part["role"] == "test", "row_number"].to_numpy()
    y = pd.Series(rng.uniform(0.05, 0.95, len(table)), index=table.index)
    return {
        "inputs": inputs,
        "X": inputs.features.loc[rows],
        "y": y.loc[rows].to_numpy(),
        "weights": inputs.population.component_weights().loc[rows].to_numpy(),
        "inner_fold": train["inner_fold"].to_numpy(),
        "X_test": inputs.features.loc[test_rows],
    }


# --------------------------------------------------- no fitting: dispatch, executor


def test_cache_applies_only_to_offset_models_with_residual_or_baseline_grids() -> None:
    inputs = synthetic_inputs()
    lineages, sets = inputs.population.lineages, inputs.gene_sets
    for model_id, grid in GRIDS.items():
        assert cacheable(build_model(model_id, lineages, sets, 0), grid)
    assert not cacheable(build_model("M1", lineages, sets, 0), {"alpha": [1.0]})
    assert not cacheable(build_model("M3", lineages, sets, 0), {"min_samples_leaf": [5]})
    # a grid over anything else (e.g. the scorer) must use the reference path
    assert not cacheable(build_model("M2", lineages, sets, 0), {"scorer__combine": ["x"]})
    assert not cacheable(build_model("M2", lineages, sets, 0), {"random_state": [0, 1]})


def test_executor_serial_and_parallel_give_the_same_results() -> None:
    if (os.cpu_count() or 1) < 2:
        pytest.skip("needs two logical cores")
    serial: dict[int, object] = {}
    parallel: dict[int, object] = {}
    execute_tasks(range(12), operator.mul, 3, 1, lambda t, v, s: serial.__setitem__(t, v))
    execute_tasks(range(12), operator.mul, 3, 2, lambda t, v, s: parallel.__setitem__(t, v))
    assert serial == parallel == {t: 3 * t for t in range(12)}


def test_executor_bounds_the_tasks_in_flight() -> None:
    if (os.cpu_count() or 1) < 2:
        pytest.skip("needs two logical cores")
    drawn: list[int] = []
    handled: list[object] = []
    in_flight: list[int] = []

    def tasks():
        for t in range(20):
            drawn.append(t)  # a task is drawn from the iterator only when submitted
            yield t

    def handle(task: object, value: object, seconds: float) -> None:
        in_flight.append(len(drawn) - len(handled))  # submitted and not yet handled
        handled.append(task)

    execute_tasks(tasks(), operator.mul, 1, 2, handle, max_pending=3)
    assert sorted(handled) == list(range(20))  # type: ignore[type-var]
    assert max(in_flight) <= 3


def test_executor_stops_on_error_without_handling_later_results() -> None:
    handled: list[int] = []
    with pytest.raises(ZeroDivisionError):
        execute_tasks([1, 2, 0, 4], operator.truediv, 1.0, 1, lambda t, v, s: handled.append(t))
    assert handled == [1, 2]  # serial: task order; nothing after the failure


def test_workers_need_single_thread_blas(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ck.THREAD_VARIABLES:
        monkeypatch.delenv(name, raising=False)
    check_workers(1)  # serial: any thread setting (recorded in the manifest)
    with pytest.raises(ValueError):
        check_workers(0)
    with pytest.raises(ValueError):
        check_workers((os.cpu_count() or 1) + 1)
    if (os.cpu_count() or 1) >= 2:
        with pytest.raises(ValueError, match="OMP_NUM_THREADS"):
            check_workers(2)
        for name in ck.THREAD_VARIABLES:
            monkeypatch.setenv(name, "1")
        check_workers(2)


def study_mapping(output_dir: Path, **overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "schema_version": 1,
        "run_id": "SYNTHETIC_cov",
        "experiment_config": "unused.yaml",
        "nsim": 2,
        "n_truth": 2,
        "truth_test_records": 40,
        "repeats": 2,
        "copula_components": 3,
        "base_seed": 7,
        "pilot_replicates": 1,
        "output_dir": str(output_dir),
        "scenarios": [
            {"name": "null_s", "tissue_share": 0.3, "effect_k": 0.0, "component_share": 0.05,
             "noise_share": 0.5, "logit_mean": -0.2, "logit_sd": 1.0},
            {"name": "moderate_s", "tissue_share": 0.3, "effect_k": 0.5,
             "component_share": 0.05, "noise_share": 0.5, "logit_mean": -0.2, "logit_sd": 1.0},
        ],
    }  # fmt: skip
    data.update(overrides)
    return data


def test_pilot_run_id_defaults_and_must_differ(tmp_path: Path) -> None:
    study = study_from_mapping(study_mapping(tmp_path))
    assert study.root(pilot=True) == tmp_path / "SYNTHETIC_cov_pilot"
    assert study.root(pilot=False) == tmp_path / "SYNTHETIC_cov"
    named = study_from_mapping(study_mapping(tmp_path, pilot_run_id="SYNTHETIC_cov_pilot_opt"))
    assert named.root(pilot=True) == tmp_path / "SYNTHETIC_cov_pilot_opt"
    with pytest.raises(ValueError):
        study_from_mapping(study_mapping(tmp_path, pilot_run_id="SYNTHETIC_cov"))


# ----------------------------------------------- model fitting: tuning equivalence

FIT_LOG: list[tuple[str, tuple[int, ...]]] = []


class SpyScorer(GeneSetScorer):
    """GeneSetScorer that records the rows it is fitted on (test only)."""

    def fit(self, X: pd.DataFrame, y: object = None) -> SpyScorer:
        FIT_LOG.append(("scorer", tuple(X.index)))
        return super().fit(X, y)  # type: ignore[return-value]


class SpyRidge(TissueRidge):
    """TissueRidge that records the rows it is fitted on (test only)."""

    def fit(self, X: pd.DataFrame, y: object, sample_weight: np.ndarray | None = None):
        FIT_LOG.append(("baseline", tuple(X.index)))
        return super().fit(X, y, sample_weight=sample_weight)  # type: ignore[arg-type]


@pytest.mark.model_fit
@pytest.mark.parametrize("model_id", sorted(GRIDS))
def test_cached_inner_errors_equal_the_reference(model_id: str) -> None:
    p = tuning_problem()
    inputs = p["inputs"]
    model = build_model(model_id, inputs.population.lineages, inputs.gene_sets, 11)  # type: ignore[union-attr]
    points = grid_points(GRIDS[model_id])
    args = (p["X"], p["y"], p["weights"], p["inner_fold"], True)
    reference = inner_errors_reference(model, points, *args)  # type: ignore[arg-type]
    cached = inner_errors_cached(model, points, *args)  # type: ignore[arg-type]
    assert len(cached) == len(points)
    assert cached == reference  # zero tolerance (bit-identical)


@pytest.mark.model_fit
@pytest.mark.parametrize("model_id", sorted(GRIDS))
@pytest.mark.parametrize("clip", [True, False])
def test_cached_tuning_selects_the_same_point_and_predicts_identically(
    model_id: str, clip: bool
) -> None:
    p = tuning_problem(seed=3)
    inputs = p["inputs"]
    model = build_model(model_id, inputs.population.lineages, inputs.gene_sets, 5)  # type: ignore[union-attr]
    args = (GRIDS[model_id], p["X"], p["y"], p["weights"], p["inner_fold"])
    fitted_c, best_c, scores_c = tune_and_fit(model, *args, clip=clip, cached=True)  # type: ignore[arg-type]
    fitted_r, best_r, scores_r = tune_and_fit(model, *args, clip=clip, cached=False)  # type: ignore[arg-type]
    assert best_c == best_r
    assert scores_c == scores_r  # same grid order, same errors -> same tie-breaking
    np.testing.assert_array_equal(fitted_c.predict(p["X_test"]), fitted_r.predict(p["X_test"]))


@pytest.mark.model_fit
def test_cached_tuning_fits_only_on_inner_training_rows() -> None:
    """Same fold training sets as the reference, never a validation row (no leakage)."""
    p = tuning_problem(seed=4)
    inputs: ExperimentInputs = p["inputs"]  # type: ignore[assignment]
    X: pd.DataFrame = p["X"]  # type: ignore[assignment]
    inner_fold: np.ndarray = p["inner_fold"]  # type: ignore[assignment]
    model = OffsetModel(
        baseline=SpyRidge(lineages=tuple(inputs.population.lineages)),
        scorer=SpyScorer(inputs.gene_sets),
    )
    points = grid_points(GRIDS["M2"])
    args = (X, p["y"], p["weights"], inner_fold, True)
    expected = {tuple(X.index[inner_fold != k]) for k in sorted(set(inner_fold))}
    logs = {}
    for name, inner in (("reference", inner_errors_reference), ("cached", inner_errors_cached)):
        FIT_LOG.clear()
        errors = inner(model, points, *args)  # type: ignore[arg-type]
        logs[name] = (list(FIT_LOG), errors)
    for kind in ("scorer", "baseline"):
        seen = {rows for k, rows in logs["cached"][0] if k == kind}
        assert seen == {rows for k, rows in logs["reference"][0] if k == kind} == expected
    # cached: one scorer fit per inner fold, one baseline fit per fold x baseline alpha
    n_folds = len(expected)
    kinds = [k for k, _ in logs["cached"][0]]
    assert kinds.count("scorer") == n_folds
    assert kinds.count("baseline") == n_folds * len(GRIDS["M2"]["baseline__alpha"])
    assert logs["cached"][1] == logs["reference"][1]


def test_inner_folds_are_deterministic() -> None:
    table = synthetic_inputs().population.table
    first = sp.make_splits(table, 5, 5, 2, 123)
    pd.testing.assert_frame_equal(first, sp.make_splits(table, 5, 5, 2, 123))


# ------------------------------------- model fitting: study serial/parallel/resume


def synthetic_experiment():
    return experiment_from_mapping(
        {
            "schema_version": 1,
            "run_id": "SYNTHETIC",
            "inputs": {
                "qc_dir": "q",
                "qc_sha256": {},
                "clarifi": "c",
                "clarifi_manifest": "m",
                "expression": "e",
                "gene_sets": "g",
                "gene_sets_sha256": None,
            },
            "population": "primary",
            "scales": ["raw"],
            "models": ["M1", "M2"],
            "grids": {
                "M1": {"alpha": [10.0, 1.0]},
                "M2": {"alpha": [0.1, 0.01], "baseline__alpha": [10.0, 1.0], "l1_ratio": [0.5]},
            },
            "validation": {"k_outer": 3, "k_inner": 2, "repeats": 2},
            "seeds": {"base_seed": 1},
            "fit": {"component_weighting": True},
            "predictions": {"clip_raw_to_unit_interval": True},
            "inference": {"method": "not_assessable", "alpha_one_sided": 0.05},
        }
    )


SCIENTIFIC_FILES = ("operating_characteristics.csv", "decision.json")


def scientific_files(root: Path) -> dict[str, bytes]:
    """Checkpoints and summaries (runtime.json and the manifest hold timings/env)."""
    paths = [*root.glob("truth_*.json"), *(root / "replicates").glob("*.json")]
    paths += [root / name for name in SCIENTIFIC_FILES if (root / name).exists()]
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(paths)}


def run_synthetic(output: Path, workers: int, resume: bool = False) -> Path:
    return run_study(
        study_from_mapping(study_mapping(output)), synthetic_experiment(), synthetic_inputs(),
        resume=resume, pilot=False, log=lambda _: None, workers=workers,
    )  # fmt: skip


@pytest.fixture
def single_thread_blas(monkeypatch: pytest.MonkeyPatch) -> None:
    if (os.cpu_count() or 1) < 2:
        pytest.skip("needs two logical cores")
    for name in ck.THREAD_VARIABLES:
        monkeypatch.setenv(name, "1")


@pytest.mark.model_fit
def test_study_is_identical_serial_parallel_and_repeated(
    tmp_path: Path, single_thread_blas: None
) -> None:
    serial = scientific_files(run_synthetic(tmp_path / "serial", workers=1))
    again = scientific_files(run_synthetic(tmp_path / "again", workers=1))
    parallel = scientific_files(run_synthetic(tmp_path / "parallel", workers=2))
    assert len(serial) == 2 + 2 * 2 + len(SCIENTIFIC_FILES)  # truths, replicates, summary
    assert serial == again == parallel


@pytest.mark.model_fit
def test_resume_recomputes_missing_work_identically_and_verifies_checkpoints(
    tmp_path: Path, single_thread_blas: None
) -> None:
    root = run_synthetic(tmp_path, workers=1)
    original = scientific_files(root)
    with pytest.raises(ck.CheckpointError):  # an existing run is never reused silently
        run_synthetic(tmp_path, workers=1)
    (root / "replicates" / "moderate_s_0001.json").unlink()
    (root / "truth_null_s.json").unlink()
    run_synthetic(tmp_path, workers=2, resume=True)  # worker count may change on resume
    assert scientific_files(root) == original
    # a checkpoint that does not belong to this study stops the resume
    tampered = root / "replicates" / "null_s_0000.json"
    text = original["replicates/null_s_0000.json"].decode()
    tampered.write_text(text.replace('"seed": ', '"seed": 1'))  # a different seed
    with pytest.raises(ck.CheckpointError):
        run_synthetic(tmp_path, workers=1, resume=True)
