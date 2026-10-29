"""Six-worker explainability: equivalence, held-out rows only, resume, corrupted checkpoints.

SYNTHETIC SOFTWARE-TEST DATA ONLY (``write_synthetic_inputs``). All tests fit small
models on synthetic data and are marked ``model_fit`` (investigator-run:
``python -m pytest -m model_fit tests/test_explainability_parallel.py``).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import joblib
import pandas as pd
import pytest

from radiosensitivity_ml.evaluation.report import evaluate_run
from radiosensitivity_ml.explainability import report as er
from radiosensitivity_ml.explainability import stability as st
from radiosensitivity_ml.models import checkpoints as ck
from radiosensitivity_ml.models.run import prepare_inputs
from test_model_parallel import descriptive_config, run
from test_pipeline_end_to_end import write_synthetic_inputs

pytestmark = pytest.mark.model_fit


@pytest.fixture
def evaluated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    if (os.cpu_count() or 1) < 2:
        pytest.skip("needs two logical cores")
    for name in ck.THREAD_VARIABLES:
        monkeypatch.setenv(name, "1")
    config = descriptive_config(tmp_path, write_synthetic_inputs(tmp_path))
    run(config, workers=2)
    for root in ("tables_serial", "tables_parallel"):
        evaluate_run(config, tables_root=tmp_path / root)
    return config, tmp_path


def explanation_files(folder: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in sorted(folder.iterdir())}


def test_serial_and_parallel_explanations_are_identical(evaluated) -> None:
    config, root = evaluated
    serial = er.explain_run(config, 3, root / "tables_serial", workers=1, log=lambda _: None)
    parallel = er.explain_run(config, 3, root / "tables_parallel", workers=2, log=lambda _: None)
    assert explanation_files(serial) == explanation_files(parallel)  # zero tolerance
    sessions = root / "tables_parallel" / config.run_id / "explainability_checkpoints"
    record = json.loads((sessions / "sessions.jsonl").read_text().splitlines()[-1])
    assert record["workers"] == 2 and record["threads"]["OMP_NUM_THREADS"] == "1"


def test_checkpoints_resume_and_corrupted_ones_are_recomputed(evaluated) -> None:
    config, root = evaluated
    store = ck.RunStore(config.output_dir / config.run_id)
    inputs = prepare_inputs(config, config.population_options)
    tasks = er.matching_tasks(store.load_manifest(), "M2", "real")
    folder = root / "checkpoints"
    first = er.checkpointed_importances(store, inputs, tasks, 3, config.base_seed, folder, 2)
    damaged = folder / f"{tasks[0][0]}_p3.json"
    damaged.write_text("{not json")
    stale = folder / f"{tasks[1][0]}_p3.json"
    stale.write_text(json.dumps({**json.loads(stale.read_text()), "seed": -1}))
    again = er.checkpointed_importances(store, inputs, tasks, 3, config.base_seed, folder, 1)
    assert len(list((folder / "_rejected").iterdir())) == 2
    for key in first:
        pd.testing.assert_series_equal(first[key], again[key], check_exact=True)
    # the reference (serial, no checkpoints) gives the same numbers
    reference = er.task_importances(store, inputs, tasks, 3, config.base_seed)
    for task in tasks:
        pd.testing.assert_series_equal(
            reference[er.column_name(task)], first[task[0]], check_exact=True, check_names=False
        )


class Opaque:
    """Exposes an OffsetModel's prediction interface without being one (generic path)."""

    def __init__(self, model: object):
        self.model = model
        self.feature_names_ = model.feature_names_  # type: ignore[attr-defined]

    def features(self, X: pd.DataFrame):
        return self.model.features(X)  # type: ignore[attr-defined]

    def predict_from_features(self, X: pd.DataFrame, values):
        return self.model.predict_from_features(X, values)  # type: ignore[attr-defined]


def test_cached_baseline_gives_bit_identical_importance_on_held_out_rows_only(
    evaluated,
) -> None:
    config, _ = evaluated
    store = ck.RunStore(config.output_dir / config.run_id)
    inputs = prepare_inputs(config, config.population_options)
    manifest = store.load_manifest()
    key, repeat, fold, _ = er.matching_tasks(manifest, "M2", "real")[0]
    predictions = pd.read_parquet(store.tasks_dir / key / "predictions.parquet")
    model = joblib.load(store.tasks_dir / key / "model.joblib")
    rows = predictions["row_number"].to_numpy()
    splits = store.load_splits(manifest["splits_sha256"])
    part = splits[(splits["repeat"] == repeat) & (splits["outer_fold"] == fold)]
    assert set(rows) == set(part.loc[part["role"] == "test", "row_number"])  # held out
    assert not set(rows) & set(part.loc[part["role"] == "train", "row_number"])
    args = (
        inputs.features.loc[rows], predictions["y_true"].to_numpy(),
        predictions["component_id"].to_numpy(), 3, 11,
    )  # fmt: skip
    fast = st.permutation_importance(model, *args)
    generic = st.permutation_importance(Opaque(model), *args)
    pd.testing.assert_series_equal(fast, generic, check_exact=True)
