from __future__ import annotations

import json
import logging
import math
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import ExtraTreesRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import ElasticNet, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from moringa_radioprotection.plotting import style_publication_axes


TARGET_COLUMN_CANDIDATES = {
    "mcf7": ["mcf7_raw_neglog10_gi50"],
    "du145": ["du145_raw_neglog10_gi50"],
}
REPRESENTATIONS = ("descriptors", "morgan_fingerprint")
ALGORITHMS = (
    "dummy",
    "ridge",
    "elastic_net",
    "random_forest",
    "extra_trees",
    "xgboost",
)
RANKING_FRACTIONS = (0.05, 0.10)


@dataclass
class FrozenCancerData:
    """Aligned, read-only inputs for the conventional cancer-potency benchmark."""

    cohort: pd.DataFrame
    descriptor_features: pd.DataFrame
    fingerprints: np.ndarray
    target_columns: dict[str, str]


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Required frozen benchmark artifact not found: {path}")
    return pd.read_csv(path)


def _validated_ids(frame: pd.DataFrame, artifact_name: str) -> list[str]:
    if "chemical_group_id" not in frame.columns:
        raise ValueError(f"{artifact_name} is missing chemical_group_id.")
    if frame["chemical_group_id"].isna().any():
        raise ValueError(f"{artifact_name} contains missing chemical_group_id values.")
    identifiers = frame["chemical_group_id"].astype(str).tolist()
    if len(identifiers) != len(set(identifiers)):
        raise ValueError(f"{artifact_name} contains duplicate chemical_group_id values.")
    return identifiers


def _resolve_target_columns(cohort: pd.DataFrame) -> dict[str, str]:
    resolved: dict[str, str] = {}
    normalized = {str(column).strip().lower(): str(column) for column in cohort.columns}
    for target, candidates in TARGET_COLUMN_CANDIDATES.items():
        matches = [normalized[name.lower()] for name in candidates if name.lower() in normalized]
        if len(matches) != 1:
            raise ValueError(
                f"Expected exactly one absolute-response column for {target}; found {matches}."
            )
        resolved[target] = matches[0]
    return resolved


def load_frozen_cancer_data(config: dict[str, Any]) -> FrozenCancerData:
    """Load frozen artifacts and fail before fitting if any cohort or row alignment differs."""
    processed_dir = Path(config.get("paths", {}).get("processed_data", "data/processed"))
    cohort = _read_csv(processed_dir / "nci_cancer_unique_chemicals.csv")
    descriptors = _read_csv(processed_dir / "nci_basic_descriptors.csv")
    fingerprint_map = _read_csv(processed_dir / "nci_morgan_fingerprint_map.csv")
    split_table = _read_csv(processed_dir / "nci_scaffold_split.csv")
    fingerprint_path = processed_dir / "nci_morgan_fingerprints.npz"
    if not fingerprint_path.exists():
        raise FileNotFoundError(f"Required frozen benchmark artifact not found: {fingerprint_path}")
    with np.load(fingerprint_path) as archive:
        if "fingerprints" not in archive:
            raise ValueError(f"Fingerprint archive lacks 'fingerprints': {fingerprint_path}")
        fingerprints = archive["fingerprints"].copy()

    cohort_ids = _validated_ids(cohort, "Unique-chemical cohort")
    descriptor_ids = _validated_ids(descriptors, "Descriptor table")
    fingerprint_ids = _validated_ids(fingerprint_map, "Fingerprint map")
    split_ids = _validated_ids(split_table, "Scaffold split")
    for artifact_name, identifiers in (
        ("Descriptor table", descriptor_ids),
        ("Fingerprint map", fingerprint_ids),
        ("Scaffold split", split_ids),
    ):
        if identifiers != cohort_ids:
            raise ValueError(
                f"{artifact_name} chemical_group_id cohort or row order differs from the frozen cohort."
            )

    expected_rows = np.arange(len(cohort_ids), dtype=int)
    mapped_rows = pd.to_numeric(fingerprint_map.get("row_index"), errors="coerce")
    if mapped_rows.isna().any() or not np.array_equal(mapped_rows.to_numpy(dtype=int), expected_rows):
        raise ValueError("Fingerprint row_index mapping is not contiguous and aligned from zero.")
    if fingerprints.ndim != 2 or fingerprints.shape[0] != len(cohort_ids):
        raise ValueError(
            f"Fingerprint matrix shape {fingerprints.shape} does not match cohort size {len(cohort_ids)}."
        )

    feature_config = config.get("molecular_features", {})
    expected_bits = int(feature_config.get("n_bits", 2048))
    if (
        int(feature_config.get("radius", 2)) != 2
        or expected_bits != 2048
        or bool(feature_config.get("use_chirality", True)) is not True
    ):
        raise ValueError("Frozen Morgan configuration must remain radius=2, n_bits=2048, use_chirality=true.")
    if fingerprints.shape[1] != expected_bits:
        raise ValueError(
            f"Fingerprint matrix has {fingerprints.shape[1]} bits; expected {expected_bits}."
        )
    unique_bit_values = np.unique(fingerprints)
    if not set(unique_bit_values.tolist()).issubset({0, 1}):
        raise ValueError(f"Morgan fingerprint matrix is not binary: {unique_bit_values.tolist()}")

    if "split" not in split_table.columns:
        raise ValueError("Scaffold split is missing the split column.")
    if "scaffold" not in split_table.columns:
        raise ValueError("Scaffold split is missing the scaffold column.")
    split_values = split_table["split"].astype(str)
    allowed_splits = {"train", "validation", "test"}
    if set(split_values) != allowed_splits:
        raise ValueError(f"Frozen scaffold split labels differ from {sorted(allowed_splits)}.")
    observed_counts = split_values.value_counts().to_dict()
    baseline_config = config.get("cancer_baseline", {})
    expected_cohort_size = int(baseline_config.get("frozen_cohort_size", -1))
    expected_counts = {
        key: int(value)
        for key, value in baseline_config.get("frozen_split_counts", {}).items()
    }
    if len(cohort_ids) != expected_cohort_size:
        raise ValueError(
            f"Frozen cohort size changed: observed {len(cohort_ids)}, expected {expected_cohort_size}."
        )
    if observed_counts != expected_counts:
        raise ValueError(
            f"Frozen split counts changed: observed {observed_counts}, expected {expected_counts}."
        )
    if sum(expected_counts.values()) != expected_cohort_size:
        raise ValueError("Configured frozen split counts do not sum to the frozen cohort size.")
    scaffold_split_counts = split_table.groupby("scaffold")["split"].nunique()
    if scaffold_split_counts.gt(1).any():
        leaking_scaffolds = scaffold_split_counts[scaffold_split_counts.gt(1)].index[:5].tolist()
        raise ValueError(f"Frozen scaffold leakage detected for: {leaking_scaffolds}")

    target_columns = _resolve_target_columns(cohort)
    for target, column in target_columns.items():
        values = pd.to_numeric(cohort[column], errors="coerce")
        if values.isna().any():
            raise ValueError(f"Frozen primary target {target} contains missing or nonnumeric values.")
        cohort[column] = values

    required_sensitivity_columns = {
        "mcf7_at_lower_boundary",
        "mcf7_at_upper_boundary",
        "du145_at_lower_boundary",
        "du145_at_upper_boundary",
        "mcf7_zscore_reconstruction_abs_error",
        "du145_zscore_reconstruction_abs_error",
    }
    missing_sensitivity = required_sensitivity_columns.difference(cohort.columns)
    if missing_sensitivity:
        raise ValueError(
            f"Frozen cohort lacks sensitivity-analysis columns: {sorted(missing_sensitivity)}"
        )

    descriptor_features = descriptors.drop(columns=["chemical_group_id"]).apply(
        pd.to_numeric, errors="coerce"
    )
    if descriptor_features.shape[1] == 0:
        raise ValueError("Descriptor table contains no feature columns.")

    cohort = cohort.copy()
    cohort["split"] = split_values.to_numpy()
    return FrozenCancerData(
        cohort=cohort,
        descriptor_features=descriptor_features,
        fingerprints=fingerprints,
        target_columns=target_columns,
    )


def regression_metrics(observed: np.ndarray, predicted: np.ndarray) -> dict[str, float]:
    """Return primary and descriptive regression metrics; undefined correlations remain NaN."""
    observed = np.asarray(observed, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    if observed.shape != predicted.shape or observed.ndim != 1 or observed.size == 0:
        raise ValueError("Observed and predicted values must be nonempty aligned vectors.")

    pearson_r = float("nan")
    spearman_rho = float("nan")
    if observed.size >= 2 and np.ptp(observed) > 0 and np.ptp(predicted) > 0:
        pearson_r = float(stats.pearsonr(observed, predicted).statistic)
        spearman_rho = float(stats.spearmanr(observed, predicted).statistic)
    return {
        "mae": float(mean_absolute_error(observed, predicted)),
        "rmse": float(math.sqrt(mean_squared_error(observed, predicted))),
        "r2": float(r2_score(observed, predicted)) if observed.size >= 2 else float("nan"),
        "pearson_r": pearson_r,
        "spearman_rho": spearman_rho,
        "mean_prediction_error": float(np.mean(predicted - observed)),
    }


def ranking_metrics(
    observed: np.ndarray,
    predicted: np.ndarray,
    chemical_group_ids: np.ndarray,
) -> dict[str, float]:
    """Compute top-ranking overlap and enrichment with higher potency ranked first.

    For fraction f and n records, k=ceil(f*n). Top-f overlap is |O_k ∩ P_k|/k.
    Enrichment factor is (|O_k ∩ P_k|/k)/(k/n), i.e. observed-top hit rate
    among predicted-top records divided by the random hit prevalence. Ties use
    chemical_group_id ascending, making the calculation deterministic.
    """
    observed = np.asarray(observed, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    identifiers = np.asarray(chemical_group_ids, dtype=str)
    if not (observed.shape == predicted.shape == identifiers.shape) or observed.size == 0:
        raise ValueError("Ranking inputs must be nonempty aligned vectors.")

    observed_order = np.lexsort((identifiers, -observed))
    predicted_order = np.lexsort((identifiers, -predicted))
    metrics: dict[str, float] = {}
    for fraction in RANKING_FRACTIONS:
        k = max(1, int(math.ceil(fraction * observed.size)))
        observed_top = set(identifiers[observed_order[:k]])
        predicted_top = set(identifiers[predicted_order[:k]])
        hits = len(observed_top.intersection(predicted_top))
        suffix = str(int(fraction * 100))
        metrics[f"top_{suffix}_percent_overlap"] = float(hits / k)
        metrics[f"enrichment_factor_top_{suffix}_percent"] = float((hits / k) / (k / observed.size))
    return metrics


def evaluate_predictions(
    observed: np.ndarray,
    predicted: np.ndarray,
    chemical_group_ids: np.ndarray,
) -> dict[str, float]:
    return {
        **regression_metrics(observed, predicted),
        **ranking_metrics(observed, predicted, chemical_group_ids),
    }


def configured_candidates(config: dict[str, Any], algorithm: str) -> list[dict[str, Any]]:
    """Return the explicit candidate list without constructing an implicit large search."""
    grids = config.get("cancer_baseline", {}).get("candidate_grids", {})
    candidates = grids.get(algorithm)
    if not isinstance(candidates, list) or not candidates:
        raise ValueError(f"No explicit cancer-baseline candidates configured for {algorithm}.")
    if not all(isinstance(candidate, dict) for candidate in candidates):
        raise ValueError(f"Every {algorithm} candidate must be a parameter mapping.")
    return [dict(candidate) for candidate in candidates]


def build_regressor(
    algorithm: str,
    representation: str,
    parameters: dict[str, Any],
    config: dict[str, Any],
) -> Any:
    """Build one leakage-safe estimator; descriptor preprocessing is retained in its pipeline."""
    baseline_config = config.get("cancer_baseline", {})
    if algorithm == "dummy":
        regressor: Any = DummyRegressor(strategy="mean")
    elif algorithm == "ridge":
        regressor = Ridge(**parameters)
    elif algorithm == "elastic_net":
        max_iter_key = (
            "descriptor_elastic_net_max_iter"
            if representation == "descriptors"
            else "fingerprint_elastic_net_max_iter"
        )
        regressor = ElasticNet(
            **parameters,
            max_iter=int(baseline_config.get(max_iter_key, 20000)),
            tol=1e-4,
            random_state=42,
            selection="cyclic",
        )
    elif algorithm == "random_forest":
        regressor = RandomForestRegressor(
            **parameters,
            random_state=42,
            n_jobs=-1,
        )
    elif algorithm == "extra_trees":
        regressor = ExtraTreesRegressor(
            **parameters,
            random_state=42,
            n_jobs=-1,
        )
    elif algorithm == "xgboost":
        try:
            from xgboost import XGBRegressor
        except ImportError as exc:  # pragma: no cover - dependency failure is environment-specific
            raise ImportError("XGBoost is required for the configured cancer baseline.") from exc
        regressor = XGBRegressor(
            **parameters,
            objective="reg:squarederror",
            random_state=42,
            n_jobs=-1,
            tree_method="hist",
            verbosity=0,
        )
    else:
        raise ValueError(f"Unknown cancer-baseline algorithm: {algorithm}")

    if representation == "morgan_fingerprint":
        return regressor
    if representation != "descriptors":
        raise ValueError(f"Unknown feature representation: {representation}")

    steps: list[tuple[str, Any]] = [
        ("imputer", SimpleImputer(strategy="median", keep_empty_features=True)),
    ]
    if algorithm in {"ridge", "elastic_net"}:
        steps.append(("scaler", StandardScaler()))
    steps.append(("regressor", regressor))
    return Pipeline(steps)


def _warning_text(captured: list[warnings.WarningMessage]) -> str:
    return " | ".join(
        f"{warning.category.__name__}: {warning.message}" for warning in captured
    )


def _fit_with_warnings(
    estimator: Any,
    features: Any,
    target: np.ndarray,
) -> tuple[Any, str]:
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        estimator.fit(features, target)
    return estimator, _warning_text(captured)


def _feature_matrix(data: FrozenCancerData, representation: str) -> Any:
    if representation == "descriptors":
        return data.descriptor_features
    if representation == "morgan_fingerprint":
        return data.fingerprints
    raise ValueError(f"Unknown feature representation: {representation}")


def _json_parameters(parameters: dict[str, Any]) -> str:
    return json.dumps(parameters, sort_keys=True, separators=(",", ":"))


def _metric_row(prefix: dict[str, Any], metrics: dict[str, float]) -> dict[str, Any]:
    return {**prefix, **metrics}


def _sensitivity_masks(cohort: pd.DataFrame, target: str) -> dict[str, np.ndarray]:
    lower = cohort[f"{target}_at_lower_boundary"].fillna(False).astype(bool).to_numpy()
    upper = cohort[f"{target}_at_upper_boundary"].fillna(False).astype(bool).to_numpy()
    reconstruction_error = pd.to_numeric(
        cohort[f"{target}_zscore_reconstruction_abs_error"], errors="coerce"
    ).to_numpy()
    return {
        "exclude_target_assay_boundaries": ~(lower | upper),
        "target_reconstruction_abs_error_le_0_50": (
            np.isfinite(reconstruction_error) & (reconstruction_error <= 0.50)
        ),
    }


def _write_comparison_plot(
    test_results: pd.DataFrame,
    target: str,
    output_path: Path,
) -> None:
    target_results = test_results[test_results["target"] == target].copy()
    algorithm_labels = list(ALGORITHMS)
    positions = np.arange(len(algorithm_labels), dtype=float)
    width = 0.36
    fig, ax = plt.subplots(figsize=(10, 5.5))
    colors = {"descriptors": "#4C78A8", "morgan_fingerprint": "#F58518"}
    for offset, representation in zip((-width / 2, width / 2), REPRESENTATIONS):
        indexed = target_results[target_results["representation"] == representation].set_index(
            "algorithm"
        )
        values = [float(indexed.loc[name, "mae"]) for name in algorithm_labels]
        ax.bar(
            positions + offset,
            values,
            width=width,
            color=colors[representation],
            label=representation.replace("_", " "),
        )
    ax.set_xticks(positions)
    ax.set_xticklabels([name.replace("_", " ") for name in algorithm_labels], rotation=25, ha="right")
    style_publication_axes(ax, xlabel="Algorithm", ylabel="Scaffold test MAE")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(output_path, dpi=400, bbox_inches="tight")
    plt.close(fig)


def _write_observed_predicted_plot(
    selected_models: pd.DataFrame,
    predictions: pd.DataFrame,
    target: str,
    output_path: Path,
) -> None:
    selected = selected_models[selected_models["target"] == target].sort_values(
        ["validation_mae", "representation", "algorithm"],
        kind="stable",
    )
    if selected.empty:
        raise ValueError(f"No selected models available for {target} plotting.")
    best = selected.iloc[0]
    plotted = predictions[
        (predictions["target"] == target)
        & (predictions["representation"] == best["representation"])
        & (predictions["algorithm"] == best["algorithm"])
    ].copy()
    if plotted.empty:
        raise ValueError(f"No final test predictions available for {target} plotting.")

    observed = plotted["observed"].to_numpy(dtype=float)
    predicted = plotted["predicted"].to_numpy(dtype=float)
    axis_min = float(min(observed.min(), predicted.min()))
    axis_max = float(max(observed.max(), predicted.max()))
    padding = max(0.05, (axis_max - axis_min) * 0.04)
    fig, ax = plt.subplots(figsize=(6.4, 6.0))
    ax.scatter(
        observed,
        predicted,
        s=14,
        alpha=0.45,
        color="#4C78A8",
        edgecolors="none",
        label=f"{best['algorithm'].replace('_', ' ')}; {best['representation'].replace('_', ' ')}",
    )
    ax.plot(
        [axis_min - padding, axis_max + padding],
        [axis_min - padding, axis_max + padding],
        color="black",
        linewidth=1,
        linestyle="--",
        label="1:1",
    )
    ax.set_xlim(axis_min - padding, axis_max + padding)
    ax.set_ylim(axis_min - padding, axis_max + padding)
    style_publication_axes(
        ax,
        xlabel="Observed −log10(GI50)",
        ylabel="Predicted −log10(GI50)",
    )
    ax.legend(frameon=False, loc="best")
    fig.tight_layout()
    fig.savefig(output_path, dpi=400, bbox_inches="tight")
    plt.close(fig)


def _slice_features(features: Any, mask: np.ndarray) -> Any:
    if isinstance(features, pd.DataFrame):
        return features.loc[mask]
    return features[mask]


def _undefined_metrics() -> dict[str, float]:
    return {
        "mae": float("nan"),
        "rmse": float("nan"),
        "r2": float("nan"),
        "pearson_r": float("nan"),
        "spearman_rho": float("nan"),
        "mean_prediction_error": float("nan"),
        "top_5_percent_overlap": float("nan"),
        "top_10_percent_overlap": float("nan"),
        "enrichment_factor_top_5_percent": float("nan"),
        "enrichment_factor_top_10_percent": float("nan"),
    }


def select_validation_candidate(
    successful_candidates: list[tuple[float, int, dict[str, Any], dict[str, float]]],
) -> tuple[float, int, dict[str, Any], dict[str, float]]:
    """Select strictly by lowest validation MAE, breaking exact ties by candidate order."""
    if not successful_candidates:
        raise ValueError("Cannot select from an empty candidate set.")
    return min(successful_candidates, key=lambda item: (item[0], item[1]))


def run_cancer_baseline(
    config: dict[str, Any], logger: logging.Logger, resume: bool = False
) -> None:
    """Train conventional frozen-split benchmarks without modifying source artifacts."""
    data = load_frozen_cancer_data(config)
    cohort = data.cohort
    split = cohort["split"].to_numpy(dtype=str)
    train_mask = split == "train"
    validation_mask = split == "validation"
    test_mask = split == "test"
    train_validation_mask = train_mask | validation_mask
    split_counts = pd.Series(split).value_counts().to_dict()
    logger.info("Frozen cancer cohort size: %d", len(cohort))
    logger.info("Frozen scaffold split sizes: %s", split_counts)

    paths = config.get("paths", {})
    table_dir = Path(paths.get("tables", "results/tables"))
    model_dir = Path(paths.get("models", "results/models"))
    figure_dir = Path(paths.get("figures", "results/figures"))
    table_dir.mkdir(parents=True, exist_ok=True)
    model_dir.mkdir(parents=True, exist_ok=True)
    figure_dir.mkdir(parents=True, exist_ok=True)

    validation_rows: list[dict[str, Any]] = []
    selected_rows: list[dict[str, Any]] = []
    test_rows: list[dict[str, Any]] = []
    prediction_rows: list[dict[str, Any]] = []
    sensitivity_rows: list[dict[str, Any]] = []
    identifiers = cohort["chemical_group_id"].astype(str).to_numpy()

    for target, target_column in data.target_columns.items():
        target_values = cohort[target_column].to_numpy(dtype=float)
        logger.info("Target: %s; source column: %s", target, target_column)
        for representation in REPRESENTATIONS:
            features = _feature_matrix(data, representation)
            logger.info("Target=%s representation=%s", target, representation)
            train_features = _slice_features(features, train_mask)
            validation_features = _slice_features(features, validation_mask)
            train_validation_features = _slice_features(features, train_validation_mask)
            test_features = _slice_features(features, test_mask)
            train_target = target_values[train_mask]
            validation_target = target_values[validation_mask]
            train_validation_target = target_values[train_validation_mask]
            test_target = target_values[test_mask]
            validation_ids = identifiers[validation_mask]
            test_ids = identifiers[test_mask]

            for algorithm in ALGORITHMS:
                # Path for this algorithm's final model
                model_path = model_dir / f"cancer_{target}_{representation}_{algorithm}.joblib"
                target_test_cohort = cohort.loc[test_mask].reset_index(drop=True)
                if resume and model_path.exists():
                    logger.info(
                        "Resuming: found existing model for target=%s representation=%s algorithm=%s at %s",
                        target,
                        representation,
                        algorithm,
                        model_path,
                    )
                    try:
                        final_estimator = joblib.load(model_path)
                    except Exception as exc:  # pragma: no cover - loading issues environment-specific
                        logger.exception(
                            "Failed to load existing model %s; will retrain. Error: %s",
                            model_path,
                            exc,
                        )
                    else:
                        # Compute test predictions/metrics from the loaded estimator
                        try:
                            test_prediction = np.asarray(
                                final_estimator.predict(test_features), dtype=float
                            )
                            test_metrics = evaluate_predictions(test_target, test_prediction, test_ids)
                            logger.info(
                                "Loaded model test metrics target=%s representation=%s algorithm=%s metrics=%s",
                                target,
                                representation,
                                algorithm,
                                json.dumps(test_metrics, sort_keys=True),
                            )

                            # Record selection and test information with a resumed marker
                            selected_parameter_json = json.dumps({"resumed": True}, sort_keys=True, separators=(',', ':'))
                            selected_rows.append(
                                {
                                    "target": target,
                                    "target_column": target_column,
                                    "representation": representation,
                                    "algorithm": algorithm,
                                    "selected_candidate_index": -1,
                                    "selected_hyperparameters": selected_parameter_json,
                                    "selection_metric": "mae",
                                    "validation_mae": float('nan'),
                                    "validation_rmse": float('nan'),
                                    "validation_r2": float('nan'),
                                    "validation_pearson_r": float('nan'),
                                    "validation_spearman_rho": float('nan'),
                                    "model_path": str(model_path),
                                    "final_fit_warnings": "",
                                }
                            )
                            test_rows.append(
                                _metric_row(
                                    {
                                        "target": target,
                                        "target_column": target_column,
                                        "representation": representation,
                                        "algorithm": algorithm,
                                        "selected_candidate_index": -1,
                                        "selected_hyperparameters": selected_parameter_json,
                                        "selected_validation_mae": float('nan'),
                                        "n_evaluation": int(test_mask.sum()),
                                    },
                                    test_metrics,
                                )
                            )

                            for row_index, chemical_group_id in enumerate(test_ids):
                                prediction_rows.append(
                                    {
                                        "chemical_group_id": chemical_group_id,
                                        "split": "test",
                                        "target": target,
                                        "target_column": target_column,
                                        "representation": representation,
                                        "algorithm": algorithm,
                                        "observed": float(test_target[row_index]),
                                        "predicted": float(test_prediction[row_index]),
                                        "prediction_error": float(
                                            test_prediction[row_index] - test_target[row_index]
                                        ),
                                        "at_lower_assay_boundary": bool(
                                            target_test_cohort.loc[
                                                row_index, f"{target}_at_lower_boundary"
                                            ]
                                        ),
                                        "at_upper_assay_boundary": bool(
                                            target_test_cohort.loc[
                                                row_index, f"{target}_at_upper_boundary"
                                            ]
                                        ),
                                        "zscore_reconstruction_abs_error": float(
                                            target_test_cohort.loc[
                                                row_index,
                                                f"{target}_zscore_reconstruction_abs_error",
                                            ]
                                        ),
                                    }
                                )

                            for sensitivity_name, full_mask in _sensitivity_masks(cohort, target).items():
                                subset_mask = full_mask[test_mask]
                                if subset_mask.any():
                                    sensitivity_metrics = evaluate_predictions(
                                        test_target[subset_mask],
                                        test_prediction[subset_mask],
                                        test_ids[subset_mask],
                                    )
                                else:
                                    sensitivity_metrics = _undefined_metrics()
                                sensitivity_rows.append(
                                    _metric_row(
                                        {
                                            "target": target,
                                            "representation": representation,
                                            "algorithm": algorithm,
                                            "sensitivity_analysis": sensitivity_name,
                                            "threshold": (
                                                0.50
                                                if sensitivity_name
                                                == "target_reconstruction_abs_error_le_0_50"
                                                else float("nan")
                                            ),
                                            "n_evaluation": int(subset_mask.sum()),
                                            "primary_test_result": False,
                                        },
                                        sensitivity_metrics,
                                    )
                                )
                        except Exception:
                            logger.exception(
                                "Failed to evaluate loaded model %s; will retrain.", model_path
                            )
                            # fall through to normal training/fitting
                        else:
                            # Skip candidate search and retraining for this algorithm
                            continue
                successful_candidates: list[tuple[float, int, dict[str, Any], dict[str, float]]] = []
                candidates = configured_candidates(config, algorithm)
                for candidate_index, parameters in enumerate(candidates, start=1):
                    parameter_json = _json_parameters(parameters)
                    logger.info(
                        "Candidate target=%s representation=%s algorithm=%s index=%d parameters=%s",
                        target,
                        representation,
                        algorithm,
                        candidate_index,
                        parameter_json,
                    )
                    status = "success"
                    warning_text = ""
                    error_text = ""
                    try:
                        estimator = build_regressor(
                            algorithm,
                            representation,
                            parameters,
                            config,
                        )
                        estimator, warning_text = _fit_with_warnings(
                            estimator,
                            train_features,
                            train_target,
                        )
                        validation_prediction = np.asarray(
                            estimator.predict(validation_features), dtype=float
                        )
                        metrics = evaluate_predictions(
                            validation_target,
                            validation_prediction,
                            validation_ids,
                        )
                        successful_candidates.append(
                            (metrics["mae"], candidate_index, parameters, metrics)
                        )
                    except Exception as exc:  # candidate failures must remain visible in the audit table
                        status = "failed"
                        error_text = f"{type(exc).__name__}: {exc}"
                        metrics = _undefined_metrics()
                        logger.exception(
                            "Candidate failed target=%s representation=%s algorithm=%s index=%d",
                            target,
                            representation,
                            algorithm,
                            candidate_index,
                        )
                    if warning_text:
                        logger.warning(
                            "Candidate warnings target=%s representation=%s algorithm=%s index=%d: %s",
                            target,
                            representation,
                            algorithm,
                            candidate_index,
                            warning_text,
                        )
                    logger.info(
                        "Validation metrics target=%s representation=%s algorithm=%s index=%d metrics=%s",
                        target,
                        representation,
                        algorithm,
                        candidate_index,
                        json.dumps(metrics, sort_keys=True),
                    )
                    validation_rows.append(
                        _metric_row(
                            {
                                "target": target,
                                "target_column": target_column,
                                "representation": representation,
                                "algorithm": algorithm,
                                "candidate_index": candidate_index,
                                "hyperparameters": parameter_json,
                                "selection_metric": "mae",
                                "status": status,
                                "warnings": warning_text,
                                "error": error_text,
                                "n_evaluation": int(validation_mask.sum()),
                            },
                            metrics,
                        )
                    )

                if not successful_candidates:
                    raise RuntimeError(
                        f"All candidates failed for {target}/{representation}/{algorithm}."
                    )
                selected_mae, selected_index, selected_parameters, selected_metrics = (
                    select_validation_candidate(successful_candidates)
                )
                selected_parameter_json = _json_parameters(selected_parameters)
                logger.info(
                    "Selected target=%s representation=%s algorithm=%s candidate=%d validation_mae=%.8f parameters=%s",
                    target,
                    representation,
                    algorithm,
                    selected_index,
                    selected_mae,
                    selected_parameter_json,
                )

                final_estimator = build_regressor(
                    algorithm,
                    representation,
                    selected_parameters,
                    config,
                )
                final_estimator, final_warning_text = _fit_with_warnings(
                    final_estimator,
                    train_validation_features,
                    train_validation_target,
                )
                if final_warning_text:
                    logger.warning(
                        "Final fit warnings target=%s representation=%s algorithm=%s: %s",
                        target,
                        representation,
                        algorithm,
                        final_warning_text,
                    )
                test_prediction = np.asarray(
                    final_estimator.predict(test_features), dtype=float
                )
                test_metrics = evaluate_predictions(test_target, test_prediction, test_ids)
                logger.info(
                    "Final test metrics target=%s representation=%s algorithm=%s metrics=%s",
                    target,
                    representation,
                    algorithm,
                    json.dumps(test_metrics, sort_keys=True),
                )

                model_path = model_dir / f"cancer_{target}_{representation}_{algorithm}.joblib"
                joblib.dump(final_estimator, model_path)
                logger.info("Selected fitted estimator written to %s", model_path)
                selected_rows.append(
                    {
                        "target": target,
                        "target_column": target_column,
                        "representation": representation,
                        "algorithm": algorithm,
                        "selected_candidate_index": selected_index,
                        "selected_hyperparameters": selected_parameter_json,
                        "selection_metric": "mae",
                        "validation_mae": selected_metrics["mae"],
                        "validation_rmse": selected_metrics["rmse"],
                        "validation_r2": selected_metrics["r2"],
                        "validation_pearson_r": selected_metrics["pearson_r"],
                        "validation_spearman_rho": selected_metrics["spearman_rho"],
                        "model_path": str(model_path),
                        "final_fit_warnings": final_warning_text,
                    }
                )
                test_rows.append(
                    _metric_row(
                        {
                            "target": target,
                            "target_column": target_column,
                            "representation": representation,
                            "algorithm": algorithm,
                            "selected_candidate_index": selected_index,
                            "selected_hyperparameters": selected_parameter_json,
                            "selected_validation_mae": selected_mae,
                            "n_evaluation": int(test_mask.sum()),
                        },
                        test_metrics,
                    )
                )

                target_test_cohort = cohort.loc[test_mask].reset_index(drop=True)
                for row_index, chemical_group_id in enumerate(test_ids):
                    prediction_rows.append(
                        {
                            "chemical_group_id": chemical_group_id,
                            "split": "test",
                            "target": target,
                            "target_column": target_column,
                            "representation": representation,
                            "algorithm": algorithm,
                            "observed": float(test_target[row_index]),
                            "predicted": float(test_prediction[row_index]),
                            "prediction_error": float(
                                test_prediction[row_index] - test_target[row_index]
                            ),
                            "at_lower_assay_boundary": bool(
                                target_test_cohort.loc[
                                    row_index, f"{target}_at_lower_boundary"
                                ]
                            ),
                            "at_upper_assay_boundary": bool(
                                target_test_cohort.loc[
                                    row_index, f"{target}_at_upper_boundary"
                                ]
                            ),
                            "zscore_reconstruction_abs_error": float(
                                target_test_cohort.loc[
                                    row_index,
                                    f"{target}_zscore_reconstruction_abs_error",
                                ]
                            ),
                        }
                    )

                for sensitivity_name, full_mask in _sensitivity_masks(cohort, target).items():
                    subset_mask = full_mask[test_mask]
                    if subset_mask.any():
                        sensitivity_metrics = evaluate_predictions(
                            test_target[subset_mask],
                            test_prediction[subset_mask],
                            test_ids[subset_mask],
                        )
                    else:
                        sensitivity_metrics = _undefined_metrics()
                    sensitivity_rows.append(
                        _metric_row(
                            {
                                "target": target,
                                "representation": representation,
                                "algorithm": algorithm,
                                "sensitivity_analysis": sensitivity_name,
                                "threshold": (
                                    0.50
                                    if sensitivity_name
                                    == "target_reconstruction_abs_error_le_0_50"
                                    else float("nan")
                                ),
                                "n_evaluation": int(subset_mask.sum()),
                                "primary_test_result": False,
                            },
                            sensitivity_metrics,
                        )
                    )

    validation_results = pd.DataFrame(validation_rows)
    selected_models = pd.DataFrame(selected_rows)
    test_results = pd.DataFrame(test_rows)
    test_predictions = pd.DataFrame(prediction_rows)
    sensitivity_results = pd.DataFrame(sensitivity_rows)
    table_outputs = {
        "cancer_baseline_validation_results.csv": validation_results,
        "cancer_baseline_selected_models.csv": selected_models,
        "cancer_baseline_test_results.csv": test_results,
        "cancer_baseline_test_predictions.csv": test_predictions,
        "cancer_baseline_sensitivity_results.csv": sensitivity_results,
    }
    for filename, frame in table_outputs.items():
        output_path = table_dir / filename
        frame.to_csv(output_path, index=False)
        logger.info("Benchmark table written to %s", output_path)

    figure_outputs = {
        "mcf7": (
            figure_dir / "cancer_mcf7_baseline_comparison.png",
            figure_dir / "cancer_mcf7_test_observed_vs_predicted.png",
        ),
        "du145": (
            figure_dir / "cancer_du145_baseline_comparison.png",
            figure_dir / "cancer_du145_test_observed_vs_predicted.png",
        ),
    }
    for target, (comparison_path, observed_path) in figure_outputs.items():
        _write_comparison_plot(test_results, target, comparison_path)
        _write_observed_predicted_plot(
            selected_models,
            test_predictions,
            target,
            observed_path,
        )
        logger.info("Benchmark figures written to %s and %s", comparison_path, observed_path)
