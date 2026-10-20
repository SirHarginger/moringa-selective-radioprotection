from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline

from moringa_radioprotection.models import (
    ALGORITHMS,
    build_regressor,
    configured_candidates,
    load_frozen_cancer_data,
    ranking_metrics,
    regression_metrics,
    select_validation_candidate,
)
from moringa_radioprotection.nci import load_project_config


def test_ranking_metric_formulas_use_higher_potency_as_better():
    identifiers = np.array([f"chem_{index:02d}" for index in range(20)])
    observed = np.arange(20.0, 0.0, -1.0)
    predicted = observed.copy()
    predicted[1], predicted[2] = predicted[2], predicted[1]

    metrics = ranking_metrics(observed, predicted, identifiers)

    assert metrics["top_5_percent_overlap"] == 1.0
    assert metrics["top_10_percent_overlap"] == 0.5
    assert metrics["enrichment_factor_top_5_percent"] == 20.0
    assert metrics["enrichment_factor_top_10_percent"] == 5.0


def test_constant_dummy_predictions_leave_correlations_undefined():
    observed = np.array([1.0, 2.0, 3.0, 4.0])
    predicted = np.repeat(observed.mean(), len(observed))

    metrics = regression_metrics(observed, predicted)

    assert np.isnan(metrics["pearson_r"])
    assert np.isnan(metrics["spearman_rho"])
    assert metrics["mean_prediction_error"] == 0.0


def test_descriptor_linear_pipeline_is_scaled_but_fingerprint_bits_are_not():
    config = {"cancer_baseline": {"descriptor_elastic_net_max_iter": 20000}}

    descriptor_ridge = build_regressor("ridge", "descriptors", {"alpha": 1.0}, config)
    descriptor_forest = build_regressor(
        "random_forest",
        "descriptors",
        {"n_estimators": 10, "max_features": "sqrt", "min_samples_leaf": 1},
        config,
    )
    fingerprint_ridge = build_regressor(
        "ridge", "morgan_fingerprint", {"alpha": 1.0}, config
    )

    assert isinstance(descriptor_ridge, Pipeline)
    assert list(descriptor_ridge.named_steps) == ["imputer", "scaler", "regressor"]
    assert isinstance(descriptor_forest, Pipeline)
    assert list(descriptor_forest.named_steps) == ["imputer", "regressor"]
    assert isinstance(fingerprint_ridge, Ridge)


def _write_frozen_artifacts(processed_dir: Path) -> dict:
    processed_dir.mkdir()
    identifiers = [f"chem_{index}" for index in range(6)]
    cohort = pd.DataFrame(
        {
            "chemical_group_id": identifiers,
            "mcf7_raw_neglog10_gi50": [4.0, 5.0, 6.0, 7.0, 5.5, 6.5],
            "du145_raw_neglog10_gi50": [4.5, 5.5, 6.5, 7.5, 5.0, 6.0],
            "mcf7_at_lower_boundary": [True, False, False, False, False, False],
            "mcf7_at_upper_boundary": [False] * 6,
            "du145_at_lower_boundary": [False] * 6,
            "du145_at_upper_boundary": [False, False, False, True, False, False],
            "mcf7_zscore_reconstruction_abs_error": [0.1, 0.2, 0.3, 0.6, 0.4, 0.5],
            "du145_zscore_reconstruction_abs_error": [0.2, 0.3, 0.4, 0.7, 0.1, 0.5],
        }
    )
    descriptors = pd.DataFrame(
        {
            "chemical_group_id": identifiers,
            "feature_a": [1.0, 2.0, np.nan, 4.0, 5.0, 6.0],
            "feature_b": [6.0, 5.0, 4.0, 3.0, 2.0, 1.0],
        }
    )
    fingerprint_map = pd.DataFrame(
        {"row_index": np.arange(6), "chemical_group_id": identifiers}
    )
    split = pd.DataFrame(
        {
            "chemical_group_id": identifiers,
            "scaffold": ["s_train_1", "s_train_1", "s_train_2", "s_val", "s_test", "s_test"],
            "split": ["train", "train", "train", "validation", "test", "test"],
        }
    )
    cohort.to_csv(processed_dir / "nci_cancer_unique_chemicals.csv", index=False)
    descriptors.to_csv(processed_dir / "nci_basic_descriptors.csv", index=False)
    fingerprint_map.to_csv(
        processed_dir / "nci_morgan_fingerprint_map.csv", index=False
    )
    split.to_csv(processed_dir / "nci_scaffold_split.csv", index=False)
    np.savez_compressed(
        processed_dir / "nci_morgan_fingerprints.npz",
        fingerprints=np.zeros((6, 2048), dtype=np.uint8),
    )
    return {
        "paths": {"processed_data": str(processed_dir)},
        "molecular_features": {"radius": 2, "n_bits": 2048, "use_chirality": True},
        "cancer_baseline": {
            "frozen_cohort_size": 6,
            "frozen_split_counts": {"train": 3, "validation": 1, "test": 2},
        },
    }


def test_frozen_artifact_loader_accepts_aligned_inputs(tmp_path):
    config = _write_frozen_artifacts(tmp_path / "processed")

    data = load_frozen_cancer_data(config)

    assert len(data.cohort) == 6
    assert data.fingerprints.shape == (6, 2048)
    assert data.target_columns == {
        "mcf7": "mcf7_raw_neglog10_gi50",
        "du145": "du145_raw_neglog10_gi50",
    }


def test_frozen_artifact_loader_rejects_fingerprint_row_misalignment(tmp_path):
    processed_dir = tmp_path / "processed"
    config = _write_frozen_artifacts(processed_dir)
    mapping_path = processed_dir / "nci_morgan_fingerprint_map.csv"
    mapping = pd.read_csv(mapping_path)
    mapping.loc[[0, 1], "chemical_group_id"] = mapping.loc[[1, 0], "chemical_group_id"].to_numpy()
    mapping.to_csv(mapping_path, index=False)

    with pytest.raises(ValueError, match="Fingerprint map chemical_group_id cohort or row order"):
        load_frozen_cancer_data(config)


def test_candidate_grid_is_explicit_and_controlled():
    config = load_project_config("config/analysis.yaml")
    expected_counts = {
        "dummy": 1,
        "ridge": 4,
        "elastic_net": 9,
        "random_forest": 4,
        "extra_trees": 4,
        "xgboost": 4,
    }

    assert {algorithm: len(configured_candidates(config, algorithm)) for algorithm in ALGORITHMS} == expected_counts
    assert sum(expected_counts.values()) == 26


def test_selection_uses_lowest_validation_mae_and_candidate_order_for_ties():
    candidates = [
        (0.5, 1, {"alpha": 0.1}, {"mae": 0.5}),
        (0.3, 2, {"alpha": 1.0}, {"mae": 0.3}),
        (0.3, 3, {"alpha": 10.0}, {"mae": 0.3}),
    ]

    selected = select_validation_candidate(candidates)

    assert selected[1] == 2
    assert selected[2] == {"alpha": 1.0}
