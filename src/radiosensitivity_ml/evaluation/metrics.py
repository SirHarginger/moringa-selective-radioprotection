"""Out-of-fold performance metrics (protocol §11, §12). Pure functions on predictions.

Primary estimate, for a comparison of model B (comparator) against model A:
    d_ir   = |y_i - yhat_ir(B)| - |y_i - yhat_ir(A)|      (positive = A better)
    D_cr   = mean of d_ir over the records i of component c          (component value)
    dMAE_r = mean of D_cr over components                            (repeat value)
    dMAE   = mean of dMAE_r over repeats                              (estimate)
Per-fold values dMAE_rk = mean of D_cr over the components in outer test fold k.
Repeats are split replications, never extra observations.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

KEYS = ["repeat", "outer_fold", "row_number", "component_id", "lineage"]


def weighted_mae(y: np.ndarray, pred: np.ndarray, weights: np.ndarray) -> float:
    """Weighted mean absolute error (weights renormalised to sum to 1)."""
    return float(np.sum(weights * np.abs(y - pred)) / np.sum(weights))


def prepare(predictions: pd.DataFrame, clip_raw: bool) -> pd.DataFrame:
    """Apply the prespecified prediction clip rule (raw scale only; outcomes never clipped)."""
    out = predictions.copy()
    if clip_raw:
        raw = out["scale"] == "raw"
        out.loc[raw, "y_pred"] = out.loc[raw, "y_pred"].clip(0.0, 1.0)
    return out


def paired_differences(
    predictions: pd.DataFrame, model_a: str, model_b: str, scale: str, variant: str = "real"
) -> pd.DataFrame:
    """Record-level d_ir for one comparison (A vs comparator B), same splits required."""
    sub = predictions[(predictions["scale"] == scale) & (predictions["variant"] == variant)]
    a = sub[sub["model_id"] == model_a].set_index(["repeat", "row_number"])
    b = sub[sub["model_id"] == model_b].set_index(["repeat", "row_number"])
    if set(a.index) != set(b.index):
        raise ValueError(f"{model_a} and {model_b} predictions do not cover the same records")
    b = b.loc[a.index]
    if not (a["outer_fold"].to_numpy() == b["outer_fold"].to_numpy()).all():
        raise ValueError("paired models used different outer folds")
    frame = a[["outer_fold", "component_id", "lineage", "y_true"]].copy()
    frame["abs_error_a"] = (a["y_true"] - a["y_pred"]).abs()
    frame["abs_error_b"] = (b["y_true"] - b["y_pred"]).abs()
    frame["d"] = frame["abs_error_b"] - frame["abs_error_a"]
    return frame.reset_index()


def component_values(diffs: pd.DataFrame) -> pd.DataFrame:
    """D_cr: mean record difference within each component, per repeat."""
    return (
        diffs.groupby(["repeat", "outer_fold", "component_id", "lineage"], as_index=False)["d"]
        .mean()
        .rename(columns={"d": "D"})
    )


def delta_mae(diffs: pd.DataFrame) -> dict[str, object]:
    """Component-weighted estimate with its per-repeat and per-fold parts."""
    comp = component_values(diffs)
    per_repeat = comp.groupby("repeat")["D"].mean()
    per_fold = comp.groupby(["repeat", "outer_fold"]).agg(
        D=("D", "mean"), n_components=("D", "size")
    )
    record_weighted = diffs.groupby("repeat")["d"].mean().mean()
    return {
        "estimate": float(per_repeat.mean()),
        "per_repeat": per_repeat,
        "per_fold": per_fold.reset_index(),
        "component_mean_over_repeats": comp.groupby("component_id")["D"].mean(),
        "record_weighted_estimate": float(record_weighted),
        "n_components": int(comp["component_id"].nunique()),
        "n_records": int(diffs["row_number"].nunique()),
        "repeats": int(per_repeat.size),
    }


def component_weights(frame: pd.DataFrame) -> np.ndarray:
    """1/|component| within a repeat's predictions."""
    sizes = frame.groupby(["repeat", "component_id"])["row_number"].transform("size")
    return (1.0 / sizes).to_numpy()


def model_metrics(predictions: pd.DataFrame, model: str, scale: str) -> dict[str, float]:
    """Component-weighted MAE, RMSE, out-of-sample R2 and calibration, averaged over repeats."""
    sub = predictions[
        (predictions["model_id"] == model)
        & (predictions["scale"] == scale)
        & (predictions["variant"] == "real")
    ]
    rows = []
    for _, part in sub.groupby("repeat"):
        w = component_weights(part)
        y, p = part["y_true"].to_numpy(), part["y_pred"].to_numpy()
        mean_y = np.average(y, weights=w)
        slope, intercept = np.polyfit(p, y, 1, w=np.sqrt(w)) if np.ptp(p) > 0 else (np.nan, np.nan)
        rows.append(
            {
                "mae": np.average(np.abs(y - p), weights=w),
                "rmse": np.sqrt(np.average((y - p) ** 2, weights=w)),
                "r2_oos": 1
                - np.average((y - p) ** 2, weights=w) / np.average((y - mean_y) ** 2, weights=w),
                "calibration_slope": slope,
                "calibration_intercept": intercept,
            }
        )
    return {k: float(np.mean([r[k] for r in rows])) for k in rows[0]} if rows else {}


def oof_mean_predictions(predictions: pd.DataFrame, scale: str) -> pd.DataFrame:
    """Per record and model: observed value and prediction averaged over repeats.

    Also the spread of the out-of-fold prediction across repeats (SD, min, max): split
    variability of the prediction, not a prediction interval.
    """
    sub = predictions[(predictions["scale"] == scale) & (predictions["variant"] == "real")]
    return sub.groupby(
        ["model_id", "row_number", "depmap_id", "component_id", "lineage"], as_index=False
    ).agg(
        y_true=("y_true", "first"),
        y_pred=("y_pred", "mean"),
        y_pred_sd=("y_pred", "std"),
        y_pred_min=("y_pred", "min"),
        y_pred_max=("y_pred", "max"),
        n_repeats=("repeat", "nunique"),
    )


def tissue_errors(predictions: pd.DataFrame, scale: str, min_components: int = 1) -> pd.DataFrame:
    """Component-weighted MAE per lineage and model (descriptive), with component counts."""
    sub = predictions[(predictions["scale"] == scale) & (predictions["variant"] == "real")].copy()
    sub["abs_error"] = (sub["y_true"] - sub["y_pred"]).abs()
    comp = sub.groupby(["model_id", "repeat", "lineage", "component_id"], as_index=False)[
        "abs_error"
    ].mean()
    per = comp.groupby(["model_id", "repeat", "lineage"]).agg(
        mae=("abs_error", "mean"), n_components=("component_id", "nunique")
    )
    out = per.groupby(["model_id", "lineage"]).agg(
        mae=("mae", "mean"), n_components=("n_components", "max")
    )
    out = out.reset_index()
    return out[out["n_components"] >= min_components]


SPEARMAN_ARTIFACT = (
    "pooled out-of-fold predictions contain each fold's training tissue mean, which is "
    "lower when the held-out line's own value is high (leave-fold-out mean artifact); "
    "rho is biased downward and is not a pure within-tissue ranking accuracy"
)


def within_tissue_spearman_v2(
    predictions: pd.DataFrame,
    oof: pd.DataFrame,
    min_components: int = 10,
    tolerance: float = 1e-12,
) -> pd.DataFrame:
    """Within-tissue Spearman of observed vs repeat-averaged prediction, honestly labelled.

    Corrects the version-1 table (``within_tissue_spearman``), which reported a number
    for every model:
    - unit: one point per COMPONENT (records of a relationship component averaged), not
      per record;
    - a model whose prediction is CONSTANT within a tissue in every fitted model (M0 and
      the tissue-only M1: one value per tissue per fold) has no within-tissue ranking; the
      spread of its pooled out-of-fold predictions comes only from which lines were held
      out together, so rho is reported as undefined (NaN), not as a number;
    - fewer than ``min_components`` components, or tied observed/predicted values
      throughout: undefined;
    - every defined value carries the artifact caveat (``SPEARMAN_ARTIFACT``).
    ``predictions``: task-level out-of-fold predictions (raw, real); ``oof``: the
    evaluation's repeat-averaged table. Predictions are read, never recomputed.
    """
    sub = predictions[(predictions["scale"] == "raw") & (predictions["variant"] == "real")]
    per_fit = sub.groupby(["model_id", "repeat", "outer_fold", "lineage"])["y_pred"].agg(
        spread=lambda s: float(s.max() - s.min()), size="size"
    )
    summary = per_fit.groupby(["model_id", "lineage"]).agg(
        spread=("spread", "max"), size=("size", "max")
    )
    # constancy is only observable where some fitted model predicted >= 2 lines of the tissue
    constant = (summary["spread"] <= tolerance) & (summary["size"] >= 2)
    rows = []
    for (model, lineage), part in oof.groupby(["model_id", "lineage"]):
        comp = part.groupby("component_id").agg(
            y_true=("y_true", "mean"), y_pred=("y_pred", "mean")
        )
        row = {
            "model_id": model,
            "lineage": lineage,
            "n_components": len(comp),
            "n_records": len(part),
            "spearman_rho": float("nan"),
        }
        if len(comp) < min_components:
            row["status"] = f"not reported: fewer than {min_components} components"
        elif bool(constant.get((model, lineage), False)):
            row["status"] = (
                "undefined: prediction constant within this tissue in every fitted model "
                "(no within-tissue ranking)"
            )
        elif comp["y_pred"].nunique() < 2 or comp["y_true"].nunique() < 2:
            row["status"] = "undefined: all values tied"
        else:
            row["spearman_rho"] = float(stats.spearmanr(comp["y_true"], comp["y_pred"]).statistic)
            row["status"] = "defined (see caveat)"
        row["caveat"] = SPEARMAN_ARTIFACT if row["status"].startswith("defined") else ""
        rows.append(row)
    columns = [
        "model_id", "lineage", "n_components", "n_records", "spearman_rho", "status", "caveat",
    ]  # fmt: skip
    return pd.DataFrame(rows, columns=columns)


def within_tissue_spearman(oof: pd.DataFrame, model: str, min_components: int = 10) -> pd.DataFrame:
    """Spearman correlation of observed vs repeat-averaged prediction within lineages."""
    rows = []
    for lineage, part in oof[oof["model_id"] == model].groupby("lineage"):
        if part["component_id"].nunique() >= min_components:
            rho = stats.spearmanr(part["y_true"], part["y_pred"]).statistic
            rows.append({"lineage": lineage, "spearman_rho": float(rho), "n_records": len(part)})
    return pd.DataFrame(rows, columns=["lineage", "spearman_rho", "n_records"])
