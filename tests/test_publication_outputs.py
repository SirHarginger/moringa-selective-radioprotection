"""Publication tables, version-2 figures, corrected within-tissue Spearman, triage gates.

SYNTHETIC SOFTWARE-TEST DATA ONLY: every table below is invented in memory to test code
paths; nothing is a scientific result. No model is fitted (no ``model_fit`` marker).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from radiosensitivity_ml.evaluation import metrics as mt
from radiosensitivity_ml.evaluation import publication as pub
from radiosensitivity_ml.evaluation.report import NOT_ASSESSED
from radiosensitivity_ml.triage import rules as tr
from radiosensitivity_ml.triage.report import gate_status
from radiosensitivity_ml.visualization import publication as fig
from radiosensitivity_ml.visualization.figures import FigureInputError

# ------------------------------------------------- within-tissue Spearman (v2)


def artifact_predictions() -> pd.DataFrame:
    """SYNTHETIC: lineage L (12 components, one with two records) in 4 outer folds, and a
    small lineage S. 'M1' predicts each fold's training tissue mean (constant within the
    tissue per fitted model); 'MV' predicts a monotone function of the observed value."""
    rows = []
    y = {i: float(i) for i in range(12)}
    fold = {i: i % 4 for i in range(12)}
    records = [(i, f"c{i}", "L", y[i], fold[i]) for i in range(12)]
    records.append((12, "c0", "L", 0.5, 0))  # second record of component c0
    records += [(20 + i, f"s{i}", "S", float(i), i % 2) for i in range(3)]
    frame = pd.DataFrame(records, columns=["row_number", "component_id", "lineage", "y", "fold"])
    for _, r in frame.iterrows():
        train = frame[(frame["lineage"] == r["lineage"]) & (frame["fold"] != r["fold"])]
        for model, pred in (("M1", train["y"].mean()), ("MV", 0.5 * r["y"] + 0.2)):
            rows.append(
                {
                    "model_id": model, "scale": "raw", "variant": "real", "repeat": 0,
                    "outer_fold": int(r["fold"]), "row_number": int(r["row_number"]),
                    "depmap_id": f"ACH-{int(r['row_number']):06d}",
                    "component_id": r["component_id"], "lineage": r["lineage"],
                    "y_true": r["y"], "y_pred": float(pred),
                }
            )  # fmt: skip
    return pd.DataFrame(rows)


def test_version1_spearman_shows_the_leave_fold_out_artifact() -> None:
    predictions = artifact_predictions()
    oof = mt.oof_mean_predictions(predictions, "raw")
    v1 = mt.within_tissue_spearman(oof, "M1", min_components=10)
    assert float(v1.loc[v1["lineage"] == "L", "spearman_rho"].iloc[0]) < 0  # artifact


def test_spearman_v2_reports_constant_models_as_undefined() -> None:
    predictions = artifact_predictions()
    oof = mt.oof_mean_predictions(predictions, "raw")
    table = mt.within_tissue_spearman_v2(predictions, oof, min_components=10).set_index(
        ["model_id", "lineage"]
    )
    m1 = table.loc[("M1", "L")]
    assert np.isnan(m1["spearman_rho"]) and m1["status"].startswith("undefined")
    mv = table.loc[("MV", "L")]
    assert mv["spearman_rho"] == pytest.approx(1.0) and mv["caveat"] == mt.SPEARMAN_ARTIFACT
    assert mv["n_components"] == 12 and mv["n_records"] == 13  # components, not records
    small = table.loc[("MV", "S")]
    assert np.isnan(small["spearman_rho"]) and small["status"].startswith("not reported")


def test_spearman_v2_ties_are_undefined_not_zero() -> None:
    predictions = artifact_predictions()
    predictions.loc[predictions["lineage"] == "L", "y_true"] = 0.5  # every observation tied
    oof = mt.oof_mean_predictions(predictions, "raw")
    row = mt.within_tissue_spearman_v2(predictions, oof, 10).set_index(["model_id", "lineage"])
    assert np.isnan(row.loc[("MV", "L"), "spearman_rho"])  # predictions vary, ranks do not
    assert row.loc[("MV", "L"), "status"] == "undefined: all values tied"


# ------------------------------------------------------------ publication tables


def synthetic_metrics() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "model_id": ["M0", "M1", "M1P", "M2", "M2P"],
            "scale": ["raw"] * 5,
            "mae": [0.20, 0.21, 0.205, 0.19, 0.195],
            "rmse": [0.25, 0.26, 0.255, 0.24, 0.245],
            "r2_oos": [-0.01, -0.02, -0.015, 0.02, 0.01],
            "calibration_slope": [0.1, 0.2, 0.3, 0.6, 0.5],
            "calibration_intercept": [0.4, 0.3, 0.3, 0.2, 0.2],
        }
    )


def synthetic_comparisons() -> tuple[pd.DataFrame, pd.DataFrame]:
    comparisons = pd.DataFrame(
        {
            "comparison": [fig.PRIMARY, "S1: beyond tissue+proliferation"],
            "model": ["M2", "M2P"],
            "comparator": ["M1", "M1P"],
            "scale": ["raw", "raw"],
            "delta_mae": [0.02, 0.01],
            "n_components": [30, 30],
            "verdict": [NOT_ASSESSED, "descriptive (not a confirmatory comparison)"],
        }
    )
    per_repeat = pd.DataFrame(
        {
            "repeat": list(range(4)) * 2,
            "delta_mae": [0.03, 0.02, -0.01, 0.04, 0.01, 0.0, 0.02, 0.01],
            "comparison": [fig.PRIMARY] * 4 + ["S1: beyond tissue+proliferation"] * 4,
            "scale": ["raw"] * 8,
        }
    )
    return comparisons, per_repeat


def synthetic_errors() -> pd.DataFrame:
    rows = []
    for lineage, n, m1, m2 in (("A", 20, 0.10, 0.09), ("B", 12, 0.10, 0.11), ("C", 3, 0.2, 0.1)):
        for model, mae in (("M0", m1 + 0.01), ("M1", m1), ("M2", m2)):
            rows.append({"model_id": model, "lineage": lineage, "mae": mae, "n_components": n})
    return pd.DataFrame(rows)


def test_model_comparison_table() -> None:
    comparisons, per_repeat = synthetic_comparisons()
    table = pub.model_comparison(synthetic_metrics(), comparisons, per_repeat).set_index("model_id")
    assert table.loc["M2", "mae_change_vs_M1"] == pytest.approx(0.02)
    assert table.loc["M2", "relative_mae_change_vs_M1"] == pytest.approx(0.02 / 0.21)
    assert table.loc["M2", "repeats_favouring_model"] == "3/4"
    assert table.loc["M2P", "repeats_favouring_model"] == "3/4"  # 0.0 does not favour
    assert (table["inference_status"] == pub.STATUS).all()


def test_tissue_table_flags_small_tissues_and_direction() -> None:
    table = pub.tissue_performance(synthetic_errors(), min_components=10)
    assert list(table["tissue"]) == ["A", "B", "C"]
    assert list(table["direction"]) == ["M2 lower", "M2 higher", "M2 lower"]
    assert table.loc[2, "support"].startswith("< 10")


def test_dataset_composition_counts_components_once() -> None:
    meta = pd.DataFrame(
        {
            "depmap_id": ["a", "b", "c", "d"],
            "lineage": ["L1", "L1", "L1", "L2"],
            "component_id": ["g1", "g1", "g2", "g3"],
            "component_records": [2, 2, 1, 1],
            "stranded": [False, True, False, False],
            "pooled_stratum": [False, False, False, True],
        }
    )
    table = pub.dataset_composition(meta).set_index("tissue")
    assert table.loc["L1", "records"] == 3 and table.loc["L1", "independent_components"] == 2
    assert table.loc["L1", "multi_record_components"] == 1
    assert table.loc["All", "independent_components"] == 3
    assert table.loc["L2", "stratification"].startswith("pooled")


def test_triage_categories_and_context_lines_never_change_tiers() -> None:
    discrepancies = pd.DataFrame(
        {
            "rank": [1, 2, 3, 4, 5], "depmap_id": ["x1", "x2", "x3", "x4", "ACH-000019"],
            "lineage": ["L"] * 5, "observed_msf2": [0.5] * 5, "pred_m1": [0.4] * 5,
            "pred_m2": [0.45] * 5, "abs_error_m1": [0.1] * 5, "abs_error_m2": [0.05] * 5,
            "abs_error_m1_pct": [1.0] * 5, "abs_error_m2_pct": [1.0] * 5,
            "model_disagreement": [0.05] * 5, "pred_m2_repeat_sd": [0.01] * 5,
            "repeat_prediction_range_m2_min": [0.4] * 5,
            "repeat_prediction_range_m2_max": [0.5] * 5,
            "tier": ["A", "A", "C", "not_prioritised", "not_rankable"],
            "technical_flags": ["stranded RNA profile", np.nan, "", "", ""],  # NaN as from CSV
            "tier_reason": ["r"] * 5,
        }
    )  # fmt: skip
    names = pd.Series({"x1": "LINE-1", "ACH-000019": "MCF7"})
    table = pub.discrepancy_table(discrepancies, names, {"ACH-000019": "MCF-7"})
    assert list(table["triage_category"]) == [
        "technical review first",
        "unexplained discrepancy requiring follow-up",
        "exploratory candidate",
        "not prioritised",
        "not rankable",
    ]
    assert list(table["tier"]) == list(discrepancies["tier"])  # unchanged
    assert table.loc[4, "context_line"] == "MCF-7" and table.loc[4, "cell_line_name"] == "MCF7"
    assert table.loc[1, "cell_line_name"].startswith("(name not")


# ------------------------------------------------------------------- triage gates


FITS = 4  # SYNTHETIC: four real CV fits


def evidence(n_draws: int) -> pd.DataFrame:
    """SYNTHETIC evidence built by the real ``pathway_evidence`` (its true output schema)."""
    sets = ["HALLMARK_X"]
    importance = pd.DataFrame(
        {f"real|r0|f{k}": [0.01 + 0.001 * k] for k in range(FITS)}, index=sets
    )
    signs = pd.DataFrame(
        {"share_positive": [1.0], "share_negative": [0.0], "share_zero": [0.0]}, index=sets
    )
    tests = pd.DataFrame(
        {
            "tested_importance_repeat0": [0.01], "n_draws_permuted_outcome": [n_draws],
            "n_draws_random_sets": [n_draws], "bh_permuted_outcome": [True],
            "bh_random_sets": [True], "attribution_permitted": [True],
        },
        index=sets,
    )  # fmt: skip
    return tr.pathway_evidence(importance, signs, tests, None)


RULES = tr.PathwayRules(0.9, 0.75, 0.5, 0.5, 0.8, 1000)


def test_descriptive_verdict_keeps_gene_set_tiers_at_c() -> None:
    comparisons = pd.DataFrame(
        {"model": ["M2"], "comparator": ["M1"], "scale": ["raw"], "verdict": [NOT_ASSESSED]}
    )
    gate, _ = gate_status(comparisons)
    assert gate is False
    assert tr.rank_pathways(evidence(5000), RULES, gate, FITS)["tier"].tolist() == ["C"]


def test_zero_null_draws_keep_tiers_at_c_even_with_a_gain() -> None:
    assert tr.rank_pathways(evidence(0), RULES, True, FITS)["tier"].tolist() == ["C"]


def test_gene_set_table_states_missing_null_evidence() -> None:
    ranked = tr.attach_external_evidence(tr.rank_pathways(evidence(0), RULES, False, FITS), None)
    table = pub.gene_set_table(ranked)
    assert table.loc[0, "sd_importance"] > 0  # the SD across fits from pathway_evidence
    assert table.loc[0, "null_control_evidence"].startswith("not available")
    assert table.loc[0, "interpretation_limit"] == pub.PATHWAY_LIMIT


# ---------------------------------------------------------- version-2 figures


def synthetic_oof() -> pd.DataFrame:
    rng = np.random.default_rng(0)
    rows = []
    for model in ("M0", "M1", "M2", "M2P"):
        for i in range(30):
            component = f"g{i // 2}"  # pairs of records share a component
            rows.append(
                {
                    "model_id": model, "row_number": i, "depmap_id": f"ACH-{i:06d}",
                    "component_id": component, "lineage": "L", "y_true": rng.uniform(0.2, 0.8),
                    "y_pred": rng.uniform(0.4, 0.6), "n_repeats": 10,
                }
            )  # fmt: skip
    return pd.DataFrame(rows)


def test_observed_vs_predicted_plots_one_point_per_component() -> None:
    figure = fig.observed_vs_predicted_v2(synthetic_oof(), synthetic_metrics())
    for ax in figure.axes[:4]:
        assert len(ax.collections[0].get_offsets()) == 15  # 30 records, 15 components
        assert ax.get_xlim() == figure.axes[0].get_xlim() == ax.get_ylim()  # shared limits
    with pytest.raises(FigureInputError):
        fig.observed_vs_predicted_v2(synthetic_oof(), synthetic_metrics(), models=("M0", "M3"))


def test_lollipop_is_symmetric_about_zero_and_counts_repeats() -> None:
    comparisons, per_repeat = synthetic_comparisons()
    figure = fig.repeat_lollipop(per_repeat, comparisons)
    ax = figure.axes[0]
    low, high = ax.get_ylim()
    assert low == pytest.approx(-high) and "3 of 4" in ax.get_title(loc="left")
    with pytest.raises(FigureInputError):
        fig.repeat_lollipop(per_repeat, comparisons, shown=("missing comparison",))


def test_tissue_dumbbell_separates_small_tissues() -> None:
    figure = fig.tissue_dumbbell(synthetic_errors(), min_components=10)
    top, bottom = figure.axes[:2]
    assert len(top.get_yticks()) == 2 and len(bottom.get_yticks()) == 1
    assert "1 of 2" in top.get_title(loc="left")


def test_model_summary_bars_start_at_zero() -> None:
    figure = fig.model_summary(synthetic_metrics())
    assert figure.axes[0].get_xlim()[0] == 0
    with pytest.raises(FigureInputError):
        fig.model_summary(synthetic_metrics().drop(columns="r2_oos"))


def test_context_lines_require_the_named_lines() -> None:
    oof = synthetic_oof()
    fig.context_lines_v2(oof, {"ACH-000001": "LINE-A"})
    with pytest.raises(FigureInputError):
        fig.context_lines_v2(oof, {"ACH-999999": "absent"})


def test_triage_figures_validate_inputs() -> None:
    s2 = pd.DataFrame(
        {
            "rank": [1, 2], "gene_set": ["HALLMARK_A", "HALLMARK_B"],
            "mean_importance": [0.01, 0.0], "sd_importance": [0.005, 0.002],
            "positive_importance_share": [0.8, 0.4], "tier": ["C", "not_prioritised"],
        }
    )  # fmt: skip
    figure = fig.gene_set_ranking(s2)
    labels = [t.get_text() for t in figure.axes[0].get_legend().get_texts()]
    assert labels == ["Tier C (exploratory)", "Not prioritised"]  # only tiers present
    s3 = pd.DataFrame(
        {
            "rank": [1], "depmap_id": ["x"], "cell_line_name": ["X"], "lineage": ["L"],
            "abs_error_m1": [0.3], "abs_error_m2": [0.2], "tier": ["not_prioritised"],
            "triage_category": ["not prioritised"],
        }
    )  # fmt: skip
    with pytest.raises(FigureInputError):
        fig.discrepancy_errors(s3)  # no tier A-C line: nothing to plot
