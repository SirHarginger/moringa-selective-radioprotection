"""Multicore experiment runner and descriptive-only reporting (D04.06).

SYNTHETIC SOFTWARE-TEST DATA ONLY: inputs come from ``write_synthetic_inputs`` (fake QC
folder, expression, GMT and outcome files in pytest's tmp_path). Nothing here is a
scientific result.

Checked: serial vs parallel runs give identical splits, seeds and predictions (zero
tolerance); every task predicts exactly its outer-test rows (no train row, no leakage);
interrupted runs (partial folder, missing task, corrupted task) resume to identical
predictions with a different worker count; a changed thread setting refuses to resume;
descriptive-only evaluation writes no interval or p-value and the primary verdict reads
"superiority not formally assessed".

Tests marked ``model_fit`` are run by the investigator only:
``python -m pytest -m model_fit tests/test_model_parallel.py``.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pandas as pd
import pytest
import yaml

from radiosensitivity_ml.config import experiment_from_mapping
from radiosensitivity_ml.evaluation.report import NOT_ASSESSED, evaluate_run, verdict
from radiosensitivity_ml.models import checkpoints as ck
from radiosensitivity_ml.models.run import run_experiment
from radiosensitivity_ml.visualization import figures as fg
from test_pipeline_end_to_end import write_synthetic_inputs

REPO = Path(__file__).resolve().parents[1]


def descriptive_config(root: Path, inputs: dict[str, object], output: str = "models"):
    """SYNTHETIC experiment config on the descriptive-only route (no decision file)."""
    return experiment_from_mapping(
        {
            "schema_version": 1,
            "run_id": "SYNTHETIC_run",
            "inputs": inputs,
            "population": "primary",
            "population_options": {"min_components_per_tissue": 3},
            "scales": ["raw"],
            "models": ["M0", "M1", "M2"],
            "grids": {
                "M0": {},
                "M1": {"alpha": [10.0, 1.0]},
                "M2": {"alpha": [0.1, 0.01], "baseline__alpha": [10.0, 1.0], "l1_ratio": [0.5]},
            },
            "validation": {"k_outer": 3, "k_inner": 2, "repeats": 2},
            "seeds": {"base_seed": 1},
            "fit": {"component_weighting": True},
            "predictions": {"clip_raw_to_unit_interval": True},
            "inference": {"method": "not_assessable", "alpha_one_sided": 0.05},
            "output_dir": str(root / output),
        }
    )


def run(config, workers: int, resume: bool = False) -> dict[str, int]:
    return run_experiment(
        config, config.population_options, resume=resume, log=lambda _: None, workers=workers
    )


def store_of(config) -> ck.RunStore:
    return ck.RunStore(config.output_dir / config.run_id)


def predictions_of(config) -> pd.DataFrame:
    """All predictions, ordered by task coordinates (keys differ between run folders)."""
    manifest = store_of(config).load_manifest()
    frame = store_of(config).load_predictions(list(manifest["tasks"]))
    order = ["scale", "model_id", "variant", "repeat", "outer_fold", "row_number"]
    return frame.sort_values(order).reset_index(drop=True)


def coordinates(config) -> list[list[object]]:
    """(scale, model, repeat, fold, variant, seed) of every task, in task order."""
    manifest = store_of(config).load_manifest()
    return [manifest["task_details"][k] for k in manifest["tasks"]]


@pytest.fixture
def single_thread_blas(monkeypatch: pytest.MonkeyPatch) -> None:
    if (os.cpu_count() or 1) < 2:
        pytest.skip("needs two logical cores")
    for name in ck.THREAD_VARIABLES:
        monkeypatch.setenv(name, "1")


# ------------------------------------------------------------------ no fitting


def test_primary_verdict_without_adopted_method_is_not_formally_assessed() -> None:
    assert verdict(None, primary=True) == NOT_ASSESSED
    assert "superiority not formally assessed" in NOT_ASSESSED
    assert not NOT_ASSESSED.startswith("gain shown")  # explainability/triage gates stay shut


def test_forest_without_interval_draws_points_only() -> None:
    table = pd.DataFrame(
        {"comparison": ["SYNTHETIC"], "scale": ["raw"], "delta_mae": [0.01], "n_components": [9]}
    )
    figure = fg.effect_forest(table, fg.NO_INTERVAL)
    ax = figure.axes[0]
    assert not ax.containers  # no error bars
    assert "not formally assessed" in ax.get_xlabel()
    with pytest.raises(fg.FigureInputError):
        fg.effect_forest(table, "nadeau_bengio")  # an interval method needs its columns


def test_primary_figures_need_no_interval_and_no_explainability() -> None:
    config = yaml.safe_load((REPO / "configs" / "figures.yaml").read_text(encoding="utf-8"))
    by_id = {f["id"]: f for f in config["figures"]}
    assert by_id["fig_02"]["options"]["method"] == fg.NO_INTERVAL
    assert not any("explainability/" in str(f["inputs"]) for f in config["figures"])


# ----------------------------------------------------------------- model fitting


@pytest.mark.model_fit
def test_serial_and_parallel_runs_are_identical_and_leak_free(
    tmp_path: Path, single_thread_blas: None
) -> None:
    inputs = write_synthetic_inputs(tmp_path)
    serial = descriptive_config(tmp_path, inputs, "serial")
    again = descriptive_config(tmp_path, inputs, "again")
    parallel = descriptive_config(tmp_path, inputs, "parallel")
    for config, workers in ((serial, 1), (again, 1), (parallel, 2)):
        assert run(config, workers)["failed"] == 0
    manifests = [store_of(c).load_manifest() for c in (serial, again, parallel)]
    assert len({m["splits_sha256"] for m in manifests}) == 1  # identical fold membership
    assert coordinates(serial) == coordinates(again) == coordinates(parallel)  # same seeds
    reference = predictions_of(serial)
    pd.testing.assert_frame_equal(reference, predictions_of(again), check_exact=True)
    pd.testing.assert_frame_equal(reference, predictions_of(parallel), check_exact=True)
    # every task predicts exactly its outer-test rows, never a training row
    splits = store_of(parallel).load_splits(manifests[2]["splits_sha256"])
    for (repeat, fold), part in predictions_of(parallel).groupby(["repeat", "outer_fold"]):
        fold_rows = splits[(splits["repeat"] == repeat) & (splits["outer_fold"] == fold)]
        test = set(fold_rows.loc[fold_rows["role"] == "test", "row_number"])
        train = set(fold_rows.loc[fold_rows["role"] == "train", "row_number"])
        for _, rows in part.groupby("model_id")["row_number"]:
            assert set(rows) == test and not set(rows) & train


@pytest.mark.model_fit
def test_interrupted_run_resumes_identically_with_another_worker_count(
    tmp_path: Path, single_thread_blas: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = descriptive_config(tmp_path, write_synthetic_inputs(tmp_path))
    run(config, workers=2)
    original = predictions_of(config)
    store = store_of(config)
    keys = list(store.load_manifest()["tasks"])
    shutil.rmtree(store.tasks_dir / keys[0])  # a task that never finished
    (store.tasks_dir / f"{keys[1]}.partial").mkdir()  # a staging folder left by Ctrl+C
    with (store.tasks_dir / keys[2] / "predictions.parquet").open("ab") as handle:
        handle.write(b"corrupted")  # a damaged task
    counts = run(config, workers=1, resume=True)
    assert counts == {"reused": len(keys) - 2, "computed": 2, "rejected": 1, "failed": 0}
    assert not list(store.tasks_dir.glob("*.partial"))
    assert len(list(store.rejected_dir.iterdir())) == 1  # kept for inspection
    pd.testing.assert_frame_equal(original, predictions_of(config), check_exact=True)
    sessions = [
        json.loads(line)
        for line in (store.root / "sessions.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [s["workers"] for s in sessions] == [2, 1]
    assert all(s["threads"]["OMP_NUM_THREADS"] == "1" and s["code_sha256"] for s in sessions)
    monkeypatch.setenv("OMP_NUM_THREADS", "2")  # numerics may change: resume must refuse
    with pytest.raises(ck.CheckpointError):
        run(config, workers=1, resume=True)


@pytest.mark.model_fit
def test_descriptive_only_evaluation_reports_no_interval_or_p_value(
    tmp_path: Path, single_thread_blas: None
) -> None:
    config = descriptive_config(tmp_path, write_synthetic_inputs(tmp_path))
    run(config, workers=2)
    out = evaluate_run(config, tables_root=tmp_path / "tables")
    comparisons = pd.read_csv(out / "comparisons.csv")
    assert not [c for c in comparisons.columns if c.endswith(("_lower", "_upper"))]
    assert not [c for c in comparisons.columns if "p_value" in c or "pvalue" in c]
    primary = comparisons[(comparisons["model"] == "M2") & (comparisons["comparator"] == "M1")]
    assert primary["verdict"].tolist() == [NOT_ASSESSED]
    assert primary["delta_mae"].notna().all()  # the estimate itself is still reported
    record = json.loads((out / "evaluation_record.json").read_text(encoding="utf-8"))
    assert record["decision_file"] is None
    assert "superiority not formally assessed" in record["inference_status"]
