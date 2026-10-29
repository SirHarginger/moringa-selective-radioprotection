"""Publication tables derived strictly from completed, saved analyses (no recomputation).

Core tables (from the evaluation folder and the saved task predictions):
- Table 1  dataset composition per tissue (records, independent components, strata);
- Table 2  model comparison (MAE, RMSE, out-of-sample R², calibration; change vs M1 and
           M0; paired ΔMAE and repeats favouring the richer model);
- Table 3  tissue-specific MAE (M0, M1, M2), support flag;
- Table S1 per-repeat paired ΔMAE;
- within_tissue_spearman_v2 (corrected reporting; see ``metrics.within_tissue_spearman_v2``).
Triage tables (from the triage folder):
- Table S2 exploratory gene-set ranking; Table S3 cell-line discrepancy review.
Every table states the descriptive-only status. Nothing here changes a tier, a rule or a
prediction.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from radiosensitivity_ml.evaluation import metrics as mt

STATUS = "descriptive only: superiority not formally assessed (coverage simulation deferred)"
PATHWAY_LIMIT = (
    "gene-set-level association inside a predictive model; not a gene-level finding, "
    "validated biomarker, causal mechanism or radiation-response pathway"
)


def dataset_composition(meta: pd.DataFrame) -> pd.DataFrame:
    """Table 1. ``meta``: one row per eligible record with depmap_id, lineage,
    component_id, component_records, stranded, pooled_stratum (QC metadata only)."""
    rows = []
    for lineage, part in meta.groupby("lineage"):
        rows.append(
            {
                "tissue": lineage,
                "records": len(part),
                "independent_components": part["component_id"].nunique(),
                "multi_record_components": part.loc[
                    part["component_records"] > 1, "component_id"
                ].nunique(),
                "stranded_rna_profiles": int(part["stranded"].sum()),
                "stratification": "pooled (small tissue)"
                if bool(part["pooled_stratum"].all())
                else "own stratum",
            }
        )
    table = pd.DataFrame(rows).sort_values(
        ["independent_components", "tissue"], ascending=[False, True]
    )
    total = {
        "tissue": "All",
        "records": len(meta),
        "independent_components": meta["component_id"].nunique(),
        "multi_record_components": meta.loc[
            meta["component_records"] > 1, "component_id"
        ].nunique(),
        "stranded_rna_profiles": int(meta["stranded"].sum()),
        "stratification": "",
    }
    return pd.concat([table, pd.DataFrame([total])], ignore_index=True)


def model_comparison(
    metrics: pd.DataFrame, comparisons: pd.DataFrame, per_repeat: pd.DataFrame
) -> pd.DataFrame:
    """Table 2: one row per model (raw scale) plus the paired comparisons' columns."""
    raw = metrics[metrics["scale"] == "raw"].set_index("model_id")
    out = raw[["mae", "rmse", "r2_oos", "calibration_slope", "calibration_intercept"]].copy()
    for reference in ("M1", "M0"):
        if reference in out.index:
            ref = out.loc[reference, "mae"]
            out[f"mae_change_vs_{reference}"] = ref - out["mae"]
            out[f"relative_mae_change_vs_{reference}"] = (ref - out["mae"]) / ref
    out["paired_delta_mae"] = np.nan
    out["paired_comparator"] = ""
    out["repeats_favouring_model"] = ""
    for _, row in comparisons[comparisons["scale"] == "raw"].iterrows():
        if row["model"] not in out.index:
            continue
        values = per_repeat.loc[per_repeat["comparison"] == row["comparison"], "delta_mae"]
        out.loc[row["model"], "paired_delta_mae"] = row["delta_mae"]
        out.loc[row["model"], "paired_comparator"] = row["comparator"]
        out.loc[row["model"], "repeats_favouring_model"] = (
            f"{int((values > 0).sum())}/{len(values)}"
        )
    out["inference_status"] = STATUS
    return out.reset_index()


def tissue_performance(
    errors: pd.DataFrame, min_components: int = 10, models: tuple[str, ...] = ("M0", "M1", "M2")
) -> pd.DataFrame:
    """Table 3: per-tissue component-weighted MAE; ΔMAE = MAE(M1) − MAE(M2)."""
    wide = errors[errors["model_id"].isin(models)].pivot(
        index="lineage", columns="model_id", values="mae"
    )
    wide.columns = [f"mae_{m}" for m in wide.columns]
    n = errors[errors["model_id"] == "M1"].set_index("lineage")["n_components"]
    wide.insert(0, "independent_components", n.reindex(wide.index).astype(int))
    wide["delta_mae_m1_minus_m2"] = wide["mae_M1"] - wide["mae_M2"]
    wide["direction"] = np.where(wide["delta_mae_m1_minus_m2"] > 0, "M2 lower", "M2 higher")
    wide["support"] = np.where(
        wide["independent_components"] >= min_components,
        f">= {min_components} components",
        f"< {min_components} components: descriptive only, unstable",
    )
    wide = wide.reset_index().rename(columns={"lineage": "tissue"})
    wide["_small"] = wide["independent_components"] < min_components
    wide = wide.sort_values(
        ["_small", "independent_components", "tissue"], ascending=[True, False, True]
    )
    return wide.drop(columns="_small").reset_index(drop=True)


def repeat_differences(per_repeat: pd.DataFrame) -> pd.DataFrame:
    """Table S1: ΔMAE per CV repeat (rows) and comparison (columns), with the mean."""
    wide = per_repeat.pivot(index="repeat", columns="comparison", values="delta_mae")
    wide.index = wide.index + 1
    wide.index.name = "cv_repeat"
    summary = pd.DataFrame(
        [wide.mean(), (wide > 0).sum()], index=["mean (pooled estimate)", "repeats > 0"]
    )
    return pd.concat([wide, summary]).rename_axis("cv_repeat").reset_index()


def gene_set_table(pathways: pd.DataFrame) -> pd.DataFrame:
    """Table S2 from the triage ``pathway_candidates.csv`` (tiers unchanged)."""
    null_draws = pathways[["n_draws_permuted_outcome", "n_draws_random_sets"]].min(axis=1)
    return pd.DataFrame(
        {
            "rank": pathways["rank"],
            "gene_set": pathways["gene_set"],
            "mean_importance": pathways["mean_importance_all_fits"],
            "sd_importance": pathways["sd_importance_all_fits"],
            "positive_importance_share": pathways["positive_importance_share"],
            "sign_consistency": pathways["sign_consistency"],
            "dominant_sign": pathways["dominant_sign"],
            "share_zero_coefficient": pathways["share_zero"],
            "null_control_evidence": np.where(
                null_draws > 0,
                "see p_permuted_outcome / p_random_sets",
                "not available (0 negative-control draws)",
            ),
            "tier": pathways["tier"],
            "tier_reason": pathways["tier_reason"],
            "shared_signal_caveat": pathways["caveat"],
            "interpretation_limit": PATHWAY_LIMIT,
        }
    )


def triage_category(row: pd.Series) -> str:
    """Presentation category of a discrepancy row (derived from its tier and flags only)."""
    if row["tier"] == "not_rankable":
        return "not rankable"
    if row["tier"] == "not_prioritised":
        return "not prioritised"
    flags = row["technical_flags"]  # empty flags read back from CSV as NaN
    if isinstance(flags, str) and flags.strip():
        return "technical review first"
    if row["tier"] in ("A", "B"):
        return "unexplained discrepancy requiring follow-up"
    return "exploratory candidate"


def discrepancy_table(
    discrepancies: pd.DataFrame, names: pd.Series, context: dict[str, str]
) -> pd.DataFrame:
    """Table S3 from the triage ``discrepancy_review.csv``; ``names``: DepMap
    CellLineName by ModelID; ``context``: lines highlighted as context (no tier change)."""
    table = discrepancies.copy()
    table["cell_line_name"] = table["depmap_id"].map(names).fillna("(name not in Model.csv)")
    table["triage_category"] = [triage_category(r) for _, r in table.iterrows()]
    table["context_line"] = table["depmap_id"].map(context).fillna("")
    columns = [
        "rank", "depmap_id", "cell_line_name", "lineage", "observed_msf2", "pred_m1",
        "pred_m2", "abs_error_m1", "abs_error_m2", "abs_error_m1_pct", "abs_error_m2_pct",
        "model_disagreement", "pred_m2_repeat_sd", "repeat_prediction_range_m2_min",
        "repeat_prediction_range_m2_max", "tier", "triage_category", "technical_flags",
        "tier_reason", "context_line",
    ]  # fmt: skip
    return table[columns]


def spearman_table(
    predictions: pd.DataFrame, oof: pd.DataFrame, min_components: int
) -> pd.DataFrame:
    return mt.within_tissue_spearman_v2(predictions, oof, min_components)


CAPTIONS = """# Publication tables: captions and notes (run {run_id})

Common notes. Unit of analysis: independent biological components (cell lines related by
identity records grouped; {n_components} components, {n_records} records). Validation:
10 repeats of 5-fold cross-validation grouped by component and stratified by tissue, with
all tuning and scaling inside training folds (nested 5-fold). Metrics are
component-weighted out-of-fold values averaged over repeats. Inference: {status}; no
interval or p-value is reported. Negative controls (permuted outcome, random gene sets)
were not run (0 draws), so gene-set attribution is not permitted.

Table 1. Dataset composition by tissue (OncotreeLineage): eligible records, independent
components, components with more than one record, stranded RNA profiles, stratification.

Table 2. Model comparison. MAE, RMSE, out-of-sample R² and calibration (slope,
intercept) of each model; change in MAE relative to M1 (tissue only) and M0 (global
mean), positive = lower MAE than the reference; paired component-weighted ΔMAE and the
number of CV repeats in which the richer model had lower MAE. Calibration slopes of M0
and M1 are distorted by the leave-fold-out mean artifact (see within_tissue_spearman_v2).

Table 3. Tissue-specific component-weighted MAE. ΔMAE = MAE(M1) − MAE(M2). Tissues with
fewer than {min_components} components are descriptive only and unstable.

Table S1. ΔMAE of each CV repeat. Repeats re-split the same lines: their spread is
split-to-split variability, not sampling uncertainty.

Table S2. Exploratory gene-set ranking (triage, protocol §21). Importance: increase in
component-weighted MAE when a Hallmark score is permuted across components on held-out
rows, averaged over all CV fits. Shares are proportions of CV fits (not probabilities).
Tiers A/B are closed (no formally shown gain; 0 null draws). {pathway_limit}.

Table S3. Cell-line discrepancy review (triage). Errors of the repeat-averaged out-of-fold
prediction; percentiles = (1 + lines with a strictly smaller value) / n (ties never raise
a percentile). Categories: technical review first (any technical flag), unexplained
discrepancy requiring follow-up (tier A/B without flags), exploratory candidate (tier C
without flags), not prioritised, not rankable. Measured lines are not independent
validation samples. Context lines (Moringa study) are labelled only; their tiers are not
changed.

within_tissue_spearman_v2. Replaces the version-1 table for reporting. M0 and M1 predict
one value per tissue in every fitted model, so their within-tissue rank correlation is
undefined; the strongly negative version-1 values arose from pooling out-of-fold
predictions whose training tissue mean excludes the held-out line. Defined values (models
with expression features) carry the same downward bias and are descriptive only.
"""
