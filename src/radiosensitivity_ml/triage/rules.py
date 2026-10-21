"""Prespecified triage rules (protocol §21). Pure functions on saved result tables.

Triage is a SECONDARY, hypothesis-generating deliverable. It never changes the primary
comparison, feature selection or inference, and it reads only tables already written by
evaluation and explainability. Every rule below is fixed before any real ranking is
viewed; thresholds come from ``configs/triage.yaml`` (hashed into the triage manifest).
``criteria_text`` states the same rules in words; the triage diagram (fig_s04) is drawn
from it, so figure and code share one source.

Tiers (same meaning in every table):
- ``A``: strongest support under the rules below;
- ``B``: suggestive;
- ``C``: exploratory;
- ``not_prioritised``: the evidence was assessable but met no tier's criteria;
- ``not_rankable``: required evidence is missing or too sparse to assess.
Rows are ordered by tier, then by the table's tie-breaking keys (fixed below), and every
source metric is kept so a reader can see why a row got its position.

Interpretation limits (statistical review, D03.05):
- Shares are proportions of the 5 x R cross-validation fits. Fits share most training
  data and are not independent replicates; the shares are not probabilities, confidence
  levels or p-values. A zero coefficient gives zero importance, so the two shares are
  partly redundant, not two independent lines of evidence.
- BH decisions are "BH-adjusted" within the 50-set family, separately per null. The
  permuted-outcome null tests "importance exceeds the within-tissue permuted-outcome
  reference"; the random-set null tests "exceeds matched random gene sets". Neither is
  a set-specific causal or conditional association test.
- Repeat prediction ranges show split-to-split variability of the out-of-fold
  prediction only; they are not prediction or confidence intervals and widen with R.
  They are reported, never used for tiers.
- Only tier A gene sets may be described as "associated in-model, hypothesis-generating".
A tier is never evidence of causality, clinical utility, radioprotection or biological
significance. Coefficient size is never used, only sign consistency.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

TIERS = ("A", "B", "C", "not_prioritised", "not_rankable")
TIER_ORDER = {tier: i for i, tier in enumerate(TIERS)}
OOF_COLUMNS = [
    "model_id",
    "row_number",
    "y_true",
    "y_pred",
    "y_pred_sd",
    "y_pred_min",
    "y_pred_max",
    "n_repeats",
]
PATHWAY_CLAIM = {
    "A": "in-model association, hypothesis-generating (attribution permitted)",
    "B": "suggestive; attribution not permitted",
}
STATEMENT = (
    "Hypothesis-generating triage of model outputs; not evidence of causality, clinical "
    "utility, radioprotection or biological significance."
)


class TriageError(ValueError):
    """Raised when a triage input is missing, inconsistent or malformed."""


@dataclass(frozen=True)
class PathwayRules:
    """Thresholds for gene-set triage (shares are proportions of real M2 fits)."""

    strong: float  # A: sign consistency and positive-importance share
    moderate: float  # B: same two measures
    exploratory: float  # C: positive-importance share
    max_share_zero: float  # C: the set must be selected (non-zero) in most fits
    correlation_flag: float  # |Spearman| between set scores flagged as shared signal
    min_null_draws: int  # A/B need this many completed draws of each null (G-stab)


@dataclass(frozen=True)
class CellLineRules:
    """Thresholds for discrepancy and replication triage (cohort percentiles)."""

    min_repeats: int  # fewer CV repeats per record -> not_rankable
    high_percentile: float  # A, and technical flags (instability, disagreement)
    flag_percentile: float  # B and C


def pct(value: float) -> str:
    return f"{value * 100:.0f}th"


def criteria_text(pathway: PathwayRules, lines: CellLineRules) -> dict[str, str]:
    """The implemented rules in words (line breaks sized for the fig_s04 boxes)."""
    s, m, e, z = pathway.strong, pathway.moderate, pathway.exploratory, pathway.max_share_zero
    hi, fl = pct(lines.high_percentile), pct(lines.flag_percentile)
    return {
        "pathway_input": "Each Hallmark set\nall 5 × R real M2 fits",
        "pathway_rankable": "All fits complete and\nevery metric available?",
        "pathway_gate": (
            "Primary gain shown (one-sided\n95% lower bound > 0) and\n"
            f"≥ {pathway.min_null_draws} completed draws of\neach null?"
        ),
        "pathway_A": (
            f"BH-significant vs both nulls\nand sign consistency ≥ {s:.2f}\n"
            f"and share of fits with\nimportance > 0 ≥ {s:.2f}?"
        ),
        "pathway_B": f"BH-significant vs permuted-\noutcome null and both\nshares ≥ {m:.2f}?",
        "pathway_C": (
            f"Share of fits with importance\n> 0 ≥ {e:.2f} and share of\n"
            f"zero coefficients < {z:.2f}?"
        ),
        "pathway_note": (
            "Shares are proportions of CV fits, not\nprobabilities. Ties: mean importance,\n"
            f"then sign consistency, then name.\nScores with |ρ| ≥ {pathway.correlation_flag:.2f}"
            " flagged.\nLiterature shown beside the tier only."
        ),
        "lines_input": (
            "Each measured CLARIFi line: absolute\nerror of the repeat-averaged out-of-\n"
            "fold prediction, M1 and M2; cohort\npercentile = (1 + lines with smaller\n"
            "error) / n; ties never raise it"
        ),
        "lines_rankable": (
            f"not rankable if fewer than {lines.min_repeats} CV\nrepeats or a prediction is missing"
        ),
        "lines_A": f"Tier A if error ≥ {hi} percentile\nunder both M1 and M2",
        "lines_B": f"else Tier B if ≥ {fl} percentile\nunder both models",
        "lines_C": (
            f"else Tier C if ≥ {fl} percentile\nunder one model, or repeat spread\n"
            f"≥ {hi}, or |M2 − M1| ≥ {hi}"
        ),
        "lines_none": "else not prioritised",
        "lines_review": (
            "Review type: 'technical review first'\nif any flag (stranded RNA, related\n"
            "lines, flag on a relative, small\ntissue group, unstable or disagreeing\n"
            "prediction); else 'unexplained\ndiscrepancy'"
        ),
        "lines_replication": (
            "Replication priority = same tier;\nidentity flag on a relative →\n"
            "not rankable. Not independent\nvalidation samples."
        ),
    }


def require_columns(table: pd.DataFrame, columns: list[str], name: str) -> None:
    missing = [c for c in columns if c not in table.columns]
    if missing:
        raise TriageError(f"{name}: missing columns {missing}")


def order_by_tier(table: pd.DataFrame, keys: list[str], ascending: list[bool]) -> pd.DataFrame:
    """Sort by tier, then by the tie-breaking keys; add a 1-based ``rank``."""
    out = table.assign(_tier=table["tier"].map(TIER_ORDER))
    out = out.sort_values(["_tier", *keys], ascending=[True, *ascending], kind="mergesort")
    out = out.drop(columns="_tier").reset_index(drop=True)
    out.insert(0, "rank", np.arange(1, len(out) + 1))
    return out


def cohort_percentile(values: pd.Series) -> pd.Series:
    """(1 + number of evaluated lines with a strictly smaller value) / n.

    Ties take the lowest shared rank, so ties never raise a percentile: a value shared
    by the whole cohort (e.g. identical repeat spread) flags no line. The largest value
    still gets 1.0.
    """
    return values.rank(pct=True, method="min")


# ------------------------------------------------------------------ gene sets


def pathway_evidence(
    importance_per_task: pd.DataFrame,
    coefficient_signs: pd.DataFrame,
    gene_set_tests: pd.DataFrame,
    correlation: pd.DataFrame | None,
) -> pd.DataFrame:
    """One row per gene set with every source metric used by the tier rule.

    ``importance_per_task``: sets x tasks (columns ``variant|rR|fF``); only ``real``
    columns are used. Sign consistency counts zero coefficients against the set, so
    selection instability lowers it.
    """
    require_columns(coefficient_signs, ["share_positive", "share_negative", "share_zero"], "signs")
    require_columns(
        gene_set_tests,
        [
            "tested_importance_repeat0",
            "n_draws_permuted_outcome",
            "n_draws_random_sets",
            "bh_permuted_outcome",
            "bh_random_sets",
            "attribution_permitted",
        ],
        "gene_set_tests",
    )
    real = importance_per_task[[c for c in importance_per_task.columns if c.startswith("real|")]]
    sets = real.index
    out = pd.DataFrame(index=sets)
    out.index.name = "gene_set"
    out["n_real_tasks"] = real.notna().sum(axis=1)
    out["mean_importance_all_fits"] = real.mean(axis=1)
    out["sd_importance_all_fits"] = real.std(axis=1, ddof=1)
    out["positive_importance_share"] = (real > 0).sum(axis=1) / out["n_real_tasks"].where(
        out["n_real_tasks"] > 0
    )
    signs = coefficient_signs.reindex(sets)
    out["share_positive"] = signs["share_positive"]
    out["share_negative"] = signs["share_negative"]
    out["share_zero"] = signs["share_zero"]
    out["sign_consistency"] = signs[["share_positive", "share_negative"]].max(axis=1)
    out["dominant_sign"] = np.select(
        [
            signs["share_positive"] > signs["share_negative"],
            signs["share_negative"] > signs["share_positive"],
        ],
        ["positive", "negative"],
        "none",
    )
    tests = gene_set_tests.reindex(sets)
    out["tested_importance_repeat0"] = tests["tested_importance_repeat0"]
    for column in ("n_draws_permuted_outcome", "n_draws_random_sets"):
        out[column] = tests[column]
    for column in ("p_permuted_outcome", "p_random_sets"):
        out[column] = tests.get(column, np.nan)
    for column in ("bh_permuted_outcome", "bh_random_sets", "attribution_permitted"):
        out[column] = tests[column].fillna(False).astype(bool)
    out["nulls_passed"] = np.select(
        [
            out["bh_permuted_outcome"] & out["bh_random_sets"],
            out["bh_permuted_outcome"],
            out["bh_random_sets"],
        ],
        ["both", "permuted", "random"],
        "none",
    )
    out["max_abs_score_correlation"] = np.nan
    out["most_correlated_set"] = ""
    if correlation is not None:
        corr = correlation.reindex(index=sets, columns=sets).abs()
        corr = corr.where(~np.eye(len(sets), dtype=bool))
        out["max_abs_score_correlation"] = corr.max(axis=1)
        out["most_correlated_set"] = [
            str(values.idxmax()) if values.notna().any() else "" for _, values in corr.iterrows()
        ]
    return out


def pathway_tier(
    row: pd.Series, rules: PathwayRules, gate_passed: bool, required_fits: int
) -> tuple[str, str]:
    """(tier, reason) for one gene set; mirrors ``criteria_text`` step by step."""
    needed = ["positive_importance_share", "sign_consistency", "share_zero"]
    if row["n_real_tasks"] < required_fits or row[needed].isna().any():
        return "not_rankable", f"fewer than all {required_fits} real fits, or missing metrics"
    positive, sign = row["positive_importance_share"], row["sign_consistency"]
    feasible = (
        row["n_draws_permuted_outcome"] >= rules.min_null_draws
        and row["n_draws_random_sets"] >= rules.min_null_draws
    )
    if gate_passed and feasible:
        if row["attribution_permitted"] and sign >= rules.strong and positive >= rules.strong:
            return "A", (
                f"BH-significant vs both nulls; {row['dominant_sign']} coefficient sign in "
                f"{sign:.0%} of fits; importance > 0 in {positive:.0%} of fits"
            )
        if row["bh_permuted_outcome"] and sign >= rules.moderate and positive >= rules.moderate:
            return "B", (
                f"BH-significant vs permuted-outcome null; {row['dominant_sign']} sign in "
                f"{sign:.0%} of fits; importance > 0 in {positive:.0%} of fits"
            )
    if positive >= rules.exploratory and row["share_zero"] < rules.max_share_zero:
        reason = f"importance > 0 in {positive:.0%} of fits; selected in most fits"
        if not gate_passed:
            reason += " (capped at C: primary gain not shown)"
        elif not feasible:
            reason += f" (capped at C: fewer than {rules.min_null_draws} completed null draws)"
        return "C", reason
    return "not_prioritised", "importance or selection not consistent across fits"


def rank_pathways(
    evidence: pd.DataFrame, rules: PathwayRules, gate_passed: bool, required_fits: int
) -> pd.DataFrame:
    """Tiered, ordered gene-set table.

    Tie-break: mean importance over all fits, sign consistency, name.
    """
    table = evidence.copy()
    decided = [pathway_tier(row, rules, gate_passed, required_fits) for _, row in table.iterrows()]
    table["tier"] = [t for t, _ in decided]
    table["tier_reason"] = [r for _, r in decided]
    shared = table["max_abs_score_correlation"] >= rules.correlation_flag
    table["caveat"] = np.where(
        shared,
        "score correlated with "
        + table["most_correlated_set"].astype(str)
        + ": importance may be shared or split between the two",
        "",
    )
    table["claim_level"] = table["tier"].map(PATHWAY_CLAIM).fillna("exploratory")
    table = table.reset_index()
    return order_by_tier(
        table, ["mean_importance_all_fits", "sign_consistency", "gene_set"], [False, False, True]
    )


def attach_external_evidence(ranked: pd.DataFrame, external: pd.DataFrame | None) -> pd.DataFrame:
    """Add investigator-curated literature evidence as SEPARATE columns (never re-ranks).

    ``external`` needs columns gene_set, evidence_summary, citation (DOI or PMID).
    """
    out = ranked.copy()
    if external is None:
        out["external_evidence"] = "not assessed"
        out["external_citation"] = ""
        return out
    require_columns(external, ["gene_set", "evidence_summary", "citation"], "external_evidence")
    if external["citation"].fillna("").str.strip().eq("").any():
        raise TriageError("external_evidence: every row needs a citation (DOI or PMID)")
    merged = external.groupby("gene_set").agg(
        external_evidence=("evidence_summary", " | ".join),
        external_citation=("citation", "; ".join),
    )
    out = out.merge(merged, how="left", left_on="gene_set", right_index=True)
    out["external_evidence"] = out["external_evidence"].fillna("none curated")
    out["external_citation"] = out["external_citation"].fillna("")
    return out


# ------------------------------------------------------------------ cell lines


def cell_line_evidence(oof: pd.DataFrame, meta: pd.DataFrame) -> pd.DataFrame:
    """Per measured line: M1/M2 out-of-fold errors, repeat spread and metadata flags.

    ``oof``: evaluation ``oof_predictions.csv`` (raw scale; ``y_pred`` is the mean over
    repeats, so errors are those of the repeat-averaged prediction). ``meta`` (indexed by
    row_number): depmap_id, lineage, component_records, related_flag_sources, stranded,
    tissue_components, pooled_stratum.
    """
    require_columns(oof, OOF_COLUMNS, "oof_predictions")
    wide = {}
    for model in ("M1", "M2"):
        part = oof[oof["model_id"] == model].set_index("row_number")
        if part.empty:
            raise TriageError(f"oof_predictions has no {model} rows")
        wide[model] = part
    rows = meta.index
    m1, m2 = wide["M1"].reindex(rows), wide["M2"].reindex(rows)
    out = meta.copy()
    out["observed_msf2"] = m2["y_true"].combine_first(m1["y_true"])
    out["observed_msf2_pct"] = cohort_percentile(out["observed_msf2"])
    out["observed_in_outer_5pct"] = (out["observed_msf2_pct"] <= 0.025) | (
        out["observed_msf2_pct"] > 0.975
    )
    for name, part in (("m1", m1), ("m2", m2)):
        out[f"pred_{name}"] = part["y_pred"]
        out[f"residual_{name}"] = part["y_true"] - part["y_pred"]
        out[f"pred_{name}_repeat_sd"] = part["y_pred_sd"]
        out[f"repeat_prediction_range_{name}_min"] = part["y_pred_min"]
        out[f"repeat_prediction_range_{name}_max"] = part["y_pred_max"]
        out[f"abs_error_{name}"] = out[f"residual_{name}"].abs()
        out[f"abs_error_{name}_pct"] = cohort_percentile(out[f"abs_error_{name}"])
    out["n_repeats"] = pd.concat([m1["n_repeats"], m2["n_repeats"]], axis=1).min(axis=1)
    out["model_disagreement"] = (out["pred_m2"] - out["pred_m1"]).abs()
    out["model_disagreement_pct"] = cohort_percentile(out["model_disagreement"])
    out["repeat_instability_pct"] = cohort_percentile(out["pred_m2_repeat_sd"])
    out["assay_variability"] = "not assessable (CLARIFi reports one literature median per line)"
    return out


def technical_flags(row: pd.Series, rules: CellLineRules) -> list[str]:
    """Reasons to review data or identity before any biological reading."""
    flags = []
    if bool(row["stranded"]):
        flags.append("stranded RNA profile")
    if int(row["component_records"]) > 1:
        flags.append("related lines in the cohort")
    if str(row["related_flag_sources"]).strip():
        flags.append(f"Cellosaurus problem flag on a relative ({row['related_flag_sources']})")
    if bool(row["pooled_stratum"]):
        flags.append("small tissue group")
    if row["repeat_instability_pct"] >= rules.high_percentile:
        flags.append("prediction unstable across CV repeats")
    if row["model_disagreement_pct"] >= rules.high_percentile:
        flags.append("M1 and M2 disagree strongly")
    return flags


def discrepancy_tier(row: pd.Series, rules: CellLineRules) -> tuple[str, str]:
    """(tier, reason) for review of one measured line; mirrors ``criteria_text``."""
    needed = [
        "abs_error_m1_pct",
        "abs_error_m2_pct",
        "repeat_instability_pct",
        "model_disagreement_pct",
    ]
    if row["n_repeats"] < rules.min_repeats or row[needed].isna().any():
        return "not_rankable", f"fewer than {rules.min_repeats} CV repeats or missing predictions"
    p1, p2 = row["abs_error_m1_pct"], row["abs_error_m2_pct"]
    if min(p1, p2) >= rules.high_percentile:
        return "A", f"error ≥ {pct(rules.high_percentile)} percentile under both models"
    if min(p1, p2) >= rules.flag_percentile:
        return "B", f"error ≥ {pct(rules.flag_percentile)} percentile under both models"
    if (
        max(p1, p2) >= rules.flag_percentile
        or row["repeat_instability_pct"] >= rules.high_percentile
        or row["model_disagreement_pct"] >= rules.high_percentile
    ):
        return "C", "large error under one model, unstable prediction, or model disagreement"
    return "not_prioritised", "held-out errors within the bulk of the cohort"


def rank_discrepancies(
    evidence: pd.DataFrame, rules: CellLineRules, gate_passed: bool
) -> pd.DataFrame:
    """Discrepancy review table. Tie-break: smaller of the two error percentiles, mean
    error, DepMap ID. ``review_type`` separates technical review from candidates of
    (unexplained) biological interest."""
    table = evidence.copy()
    decided = [discrepancy_tier(row, rules) for _, row in table.iterrows()]
    table["tier"] = [t for t, _ in decided]
    table["tier_reason"] = [r for _, r in decided]
    flags = [technical_flags(row, rules) for _, row in table.iterrows()]
    table["technical_flags"] = ["; ".join(f) for f in flags]
    table["review_type"] = np.where(
        table["tier"].isin(["not_prioritised", "not_rankable"]),
        "none",
        np.where(
            [bool(f) for f in flags],
            "technical review first",
            "unexplained discrepancy (not evidence of unusual radiobiology)",
        ),
    )
    table["claim_level"] = "exploratory" if not gate_passed else "model-based review signal"
    table["_min_pct"] = table[["abs_error_m1_pct", "abs_error_m2_pct"]].min(axis=1)
    table["_mean_err"] = table[["abs_error_m1", "abs_error_m2"]].mean(axis=1)
    table = table.reset_index()
    ranked = order_by_tier(table, ["_min_pct", "_mean_err", "depmap_id"], [False, False, True])
    return ranked.drop(columns=["_min_pct", "_mean_err"])


def replication_priorities(discrepancies: pd.DataFrame) -> pd.DataFrame:
    """Measured CLARIFi lines that may warrant re-measurement or investigation.

    Same evidence and tiers as the discrepancy table, but a line with an identity-related
    flag (Cellosaurus problem on a relative) is not_rankable until identity is resolved.
    These lines are NOT independent validation samples: their values were used in model
    development even though each prediction was held out within cross-validation. Lines
    picked for extreme residuals are expected to show smaller discrepancies on
    re-measurement even without error (regression to the mean).
    """
    columns = [
        "depmap_id",
        "lineage",
        "tissue_components",
        "observed_msf2",
        "observed_in_outer_5pct",
        "pred_m1",
        "pred_m2",
        "abs_error_m1_pct",
        "abs_error_m2_pct",
        "technical_flags",
        "tier",
        "tier_reason",
        "claim_level",
    ]
    table = discrepancies[columns].copy()
    identity = discrepancies["related_flag_sources"].astype(str).str.strip() != ""
    table.loc[identity, "tier"] = "not_rankable"
    table.loc[identity, "tier_reason"] = "resolve identity flag before any re-measurement"
    table.insert(1, "panel", "measured CLARIFi line (replication / investigation)")
    table["validation_status"] = "not independent: used in model development"
    return order_by_tier(table, ["abs_error_m2_pct", "depmap_id"], [False, True])
