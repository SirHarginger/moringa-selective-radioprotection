"""Publication figures, version 2 (shared style: ``visualization.style``).

Every function plots SAVED tables only (evaluation, triage, publication tables); nothing
is refitted or re-predicted. Inputs are validated before drawing. Design rules:
- out-of-fold predictions are shown per COMPONENT (records of a relationship component
  averaged; each record's prediction already averaged over CV repeats), so one cell line
  never appears as ten points and related lines never count twice;
- no fitted trend lines, no intervals that were not validated (descriptive-only route);
- axes that encode length (bars) start at zero; dot plots may use a data range;
- the descriptive-only limitation is printed on every results figure.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D

from radiosensitivity_ml.visualization import style as st
from radiosensitivity_ml.visualization.figures import FigureInputError, require

PRIMARY = "primary: tissue+expression vs tissue"
TIER_COLOUR = {
    "A": "#0072B2",
    "B": "#56B4E9",
    "C": "#009E73",
    "not_prioritised": "#B0B0B0",
    "not_rankable": "#DADADA",
}
TIER_LABEL = {
    "A": "Tier A",
    "B": "Tier B",
    "C": "Tier C (exploratory)",
    "not_prioritised": "Not prioritised",
    "not_rankable": "Not rankable",
}


def _open_handle(marker: str, colour: str, text: str) -> Line2D:
    """Legend entry for an open (unfilled) marker."""
    return Line2D(
        [], [], marker=marker, ls="", markerfacecolor="none", markeredgecolor=colour, label=text
    )


def _metrics_row(metrics: pd.DataFrame, model: str) -> pd.Series:
    rows = metrics[(metrics["model_id"] == model) & (metrics["scale"] == "raw")]
    if len(rows) != 1:
        raise FigureInputError(f"model_metrics: expected one raw row for {model}")
    return rows.iloc[0]


def component_points(oof: pd.DataFrame, models: Sequence[str]) -> pd.DataFrame:
    """One point per (model, component): mean observed and mean repeat-averaged prediction."""
    require(oof, ["model_id", "component_id", "y_true", "y_pred", "n_repeats"], "oof_predictions")
    part = oof[oof["model_id"].isin(models)]
    missing = sorted(set(models) - set(part["model_id"]))
    if missing:
        raise FigureInputError(f"oof_predictions: no predictions for {missing}")
    return part.groupby(["model_id", "component_id"], as_index=False).agg(
        y_true=("y_true", "mean"), y_pred=("y_pred", "mean"), n_records=("y_true", "size")
    )


def observed_vs_predicted_v2(
    oof: pd.DataFrame,
    metrics: pd.DataFrame,
    models: Sequence[str] = ("M0", "M1", "M2", "M2P"),
) -> plt.Figure:
    """Fig 1: observed vs out-of-fold predicted mSF2, one panel per model, shared limits."""
    st.apply()
    points = component_points(oof, models)
    values = pd.concat([points["y_true"], points["y_pred"]])
    lo = max(0.0, math.floor(values.min() * 20) / 20)
    hi = min(1.0, math.ceil(values.max() * 20) / 20)
    n_cols = min(len(models), 2)
    n_rows = math.ceil(len(models) / n_cols)
    size = st.DOUBLE_COLUMN * 0.36
    fig, axes = plt.subplots(
        n_rows, n_cols, figsize=(size * n_cols, size * n_rows), sharex=True, sharey=True,
        squeeze=False,
    )  # fmt: skip
    flat = list(axes.flat)
    repeats = int(oof["n_repeats"].max())
    for ax, model in zip(flat, models, strict=False):
        part = points[points["model_id"] == model]
        row = _metrics_row(metrics, model)
        ax.plot([lo, hi], [lo, hi], color=st.MUTED, lw=0.7, ls=(0, (3, 2)), zorder=1)
        unfilled = st.marker(model) in ("x", "+")
        ax.scatter(
            part["y_pred"], part["y_true"], s=10, alpha=0.6, color=st.colour(model),
            marker=st.marker(model), linewidths=0.7 if unfilled else 0.25,
            edgecolors=None if unfilled else "white", zorder=2,
        )  # fmt: skip
        ax.text(
            0.04, 0.96,
            f"MAE {row['mae']:.3f}\nR² (out-of-sample) {row['r2_oos']:+.3f}\n"
            f"n = {len(part)} components",
            transform=ax.transAxes, va="top", ha="left", fontsize=6.5, color=st.INK,
            bbox={"boxstyle": "round,pad=0.25", "fc": "white", "ec": st.GUIDE, "lw": 0.5},
        )  # fmt: skip
        ax.set_title(st.label(model), color=st.colour(model) if model != "M0" else st.INK)
        ax.set(xlim=(lo, hi), ylim=(lo, hi), aspect="equal")
    for ax in flat[len(models) :]:
        ax.set_visible(False)
    for ax in axes[-1, :]:
        ax.set_xlabel(f"Predicted mSF2 (out-of-fold, mean of {repeats} CV repeats)")
    for ax in axes[:, 0]:
        ax.set_ylabel("Observed mSF2 (CLARIFi)")
    st.panel_labels(flat[: len(models)])
    st.footnote(
        fig,
        "Points: independent components (related lines averaged). Dashed: identity. MAE and "
        "R² are component-weighted out-of-fold values averaged over repeats.\n" + st.LIMITATION,
    )
    fig.tight_layout()
    return fig


def repeat_lollipop(
    per_repeat: pd.DataFrame,
    comparisons: pd.DataFrame,
    shown: Sequence[str] = (PRIMARY,),
) -> plt.Figure:
    """Fig 2 / S01: ΔMAE of every CV repeat as lollipops, with the pooled estimate."""
    st.apply()
    require(per_repeat, ["repeat", "delta_mae", "comparison"], "per_repeat_delta_mae")
    require(comparisons, ["comparison", "model", "comparator", "delta_mae"], "comparisons")
    fig, axes = plt.subplots(
        1, len(shown), figsize=(st.SINGLE_COLUMN * 1.15 * len(shown), 2.4), squeeze=False
    )
    for ax, name in zip(axes[0], shown, strict=True):
        part = per_repeat[per_repeat["comparison"] == name].sort_values("repeat")
        row = comparisons[comparisons["comparison"] == name]
        if part.empty or len(row) != 1:
            raise FigureInputError(f"no per-repeat values or pooled estimate for {name!r}")
        model, comparator = row["model"].iloc[0], row["comparator"].iloc[0]
        pooled = float(row["delta_mae"].iloc[0])
        x = part["repeat"].to_numpy() + 1
        y = part["delta_mae"].to_numpy()
        colours = [st.IMPROVES if v > 0 else st.WORSENS for v in y]
        ax.vlines(x, 0, y, colors=colours, lw=1.6, zorder=2)
        ax.scatter(x, y, s=24, c=colours, zorder=3, edgecolors="white", linewidths=0.4)
        ax.axhline(0, color=st.INK, lw=0.6, zorder=1)
        ax.axhline(pooled, color=st.colour(model), lw=0.9, ls=(0, (4, 2)), zorder=1)
        ax.text(
            x.max() + 0.6, pooled, f"pooled\n{pooled:+.4f}", va="center", ha="left",
            fontsize=6.5, color=st.colour(model),
        )  # fmt: skip
        limit = max(np.abs(y).max(), abs(pooled)) * 1.3
        ax.set(ylim=(-limit, limit), xlim=(0.4, x.max() + 2.2), xticks=x)
        ax.set_xlabel("Cross-validation repeat")
        ax.set_ylabel(f"ΔMAE = MAE({comparator}) − MAE({model})\n(>0: {model} better)")
        better = int((y > 0).sum())
        ax.set_title(f"{model} vs {comparator}: lower MAE in {better} of {len(y)} repeats")
        st.guides(ax, "y")
    if len(shown) > 1:
        st.panel_labels(list(axes[0]))
    st.footnote(
        fig,
        "Each repeat re-splits the same lines: spread = split-to-split variability, not\n"
        "sampling uncertainty. No interval shown. " + st.LIMITATION,
    )
    fig.tight_layout()
    return fig


def tissue_dumbbell(
    errors: pd.DataFrame, min_components: int = 10, models: Sequence[str] = ("M1", "M2")
) -> plt.Figure:
    """Fig 3: per-tissue MAE of two models as a dumbbell; small tissues in a muted panel."""
    st.apply()
    require(errors, ["model_id", "lineage", "mae", "n_components"], "tissue_errors")
    a, b = models
    wide = errors[errors["model_id"].isin(models)].pivot(
        index="lineage", columns="model_id", values="mae"
    )
    if wide[[a, b]].isna().any().any():
        raise FigureInputError("tissue_errors: both models need every lineage")
    n = errors[errors["model_id"] == a].set_index("lineage")["n_components"]
    wide["n"] = n.reindex(wide.index)
    wide["delta"] = wide[a] - wide[b]  # >0: model b (richer) lower MAE
    big = wide[wide["n"] >= min_components].sort_values("delta")
    small = wide[wide["n"] < min_components].sort_values("delta")
    heights = [max(len(big), 1), max(len(small), 1) * 0.8]
    fig, (ax_big, ax_small) = plt.subplots(
        2, 1, figsize=(st.SINGLE_COLUMN * 1.6, 0.17 * sum(heights) + 1.3), sharex=True,
        gridspec_kw={"height_ratios": heights},
    )  # fmt: skip
    for ax, table, muted in ((ax_big, big, False), (ax_small, small, True)):
        alpha = 0.45 if muted else 1.0
        for i, (lineage, r) in enumerate(table.iterrows()):
            ax.plot([r[a], r[b]], [i, i], color="#C8C8C8", lw=2.2, solid_capstyle="round")
            for model in (a, b):
                ax.scatter(
                    r[model], i, s=22, color=st.colour(model), marker=st.marker(model),
                    alpha=alpha, zorder=3, edgecolors="white", linewidths=0.4,
                )  # fmt: skip
            ax.text(
                max(r[a], r[b]) + 0.004, i, f"{r['delta']:+.4f}", va="center", fontsize=6.5,
                color=(st.IMPROVES if r["delta"] > 0 else st.WORSENS) if not muted else st.MUTED,
            )  # fmt: skip
        ax.set_yticks(range(len(table)))
        ax.set_yticklabels(
            [f"{lineage}  (n = {int(r['n'])})" for lineage, r in table.iterrows()],
            color=st.MUTED if muted else st.INK,
        )
        ax.set_ylim(-0.7, len(table) - 0.3)
        st.guides(ax, "x")
    better = int((big["delta"] > 0).sum())
    ax_big.set_title(
        f"Tissues with ≥ {min_components} independent components: "
        f"{b} lower MAE in {better} of {len(big)}"
    )
    ax_small.set_title(
        f"Tissues with < {min_components} components (descriptive only; unstable)",
        color=st.MUTED, fontweight="normal",
    )  # fmt: skip
    ax_small.set_xlabel("Component-weighted out-of-fold MAE (mSF2 units; lower is better)")
    handles = [
        Line2D([], [], color=st.colour(m), marker=st.marker(m), ls="", label=st.label(m))
        for m in models
    ]
    ax_big.legend(handles=handles, loc="lower right", ncols=2, bbox_to_anchor=(1.0, 1.08))
    st.footnote(
        fig,
        f"Labels: MAE({a}) − MAE({b}); >0 means {b} lower. n = independent components.\n"
        + st.LIMITATION,
    )
    fig.tight_layout()
    return fig


def model_summary(
    metrics: pd.DataFrame,
    models: Sequence[str] = ("M0", "M1", "M1P", "M2", "M2P"),
    reference: str = "M1",
) -> plt.Figure:
    """Fig 5: MAE (bars from zero), out-of-sample R², and change in MAE vs the reference."""
    st.apply()
    require(metrics, ["model_id", "scale", "mae", "r2_oos"], "model_metrics")
    rows = pd.DataFrame([_metrics_row(metrics, m) for m in models]).set_index("model_id")
    y = np.arange(len(models))[::-1]
    fig, axes = plt.subplots(1, 3, figsize=(st.DOUBLE_COLUMN, 0.32 * len(models) + 1.2))
    colours = [st.colour(m) for m in models]
    ax = axes[0]
    ax.barh(y, rows["mae"], color=colours, alpha=0.85, height=0.62, zorder=2)
    for yi, value in zip(y, rows["mae"], strict=True):
        ax.text(value + 0.002, yi, f"{value:.4f}", va="center", fontsize=6.5)
    ax.set(xlim=(0, rows["mae"].max() * 1.28), title="Mean absolute error")
    ax.set_xlabel("Component-weighted MAE (mSF2 units)")
    ax = axes[1]
    r2 = rows["r2_oos"]
    span = max(0.03, float(np.abs(r2).max()) * 1.6)
    ax.axvline(0, color=st.INK, lw=0.6)
    ax.hlines(y, 0, r2, colors=colours, lw=1.4)
    for yi, value, model in zip(y, r2, models, strict=True):
        ax.scatter(value, yi, s=26, color=st.colour(model), marker=st.marker(model), zorder=3)
        ax.text(value, yi + 0.3, f"{value:+.3f}", ha="center", fontsize=6.5)
    ax.set(xlim=(-span, span), title="Out-of-sample R²")
    ax.set_xlabel("R² (0 = as accurate as the training mean)")
    ax = axes[2]
    ref = float(rows.loc[reference, "mae"])
    delta = ref - rows["mae"]
    span = max(0.006, float(np.abs(delta).max()) * 1.7)
    ax.axvline(0, color=st.INK, lw=0.6)
    for yi, value, model in zip(y, delta, models, strict=True):
        if model == reference:
            ax.text(0, yi, "reference", ha="center", va="center", fontsize=6.5, color=st.MUTED)
            continue
        ax.hlines(yi, 0, value, colors=st.colour(model), lw=1.4)
        ax.scatter(value, yi, s=26, color=st.colour(model), marker=st.marker(model), zorder=3)
        ax.text(value, yi + 0.3, f"{value:+.4f} ({value / ref:+.1%})", ha="center", fontsize=6.5)
    ax.set(xlim=(-span, span), title=f"Change in MAE vs {reference}")
    ax.set_xlabel(f"MAE({reference}) − MAE(model)  (>0: lower than {reference})")
    for ax in axes:
        ax.set_yticks(y)
        ax.set_ylim(-0.7, len(models) - 0.3)
        st.guides(ax, "x")
    axes[0].set_yticklabels([st.label(m) for m in models])
    for ax in axes[1:]:
        ax.set_yticklabels([])
    st.panel_labels(axes)
    st.footnote(
        fig,
        "Out-of-fold metrics averaged over 10 repeats of 5-fold grouped CV. For M2 vs M1 the "
        "change equals the paired component-weighted ΔMAE.\n" + st.LIMITATION,
    )
    fig.tight_layout()
    return fig


def context_lines_v2(
    oof: pd.DataFrame, lines: Mapping[str, str], models: Sequence[str] = ("M1", "M2")
) -> plt.Figure:
    """S03: observed CLARIFi mSF2 of all lines, with the Moringa-study lines marked."""
    st.apply()
    require(oof, ["model_id", "depmap_id", "y_true", "y_pred"], "oof_predictions")
    observed = oof[oof["model_id"] == models[0]]
    fig, (ax_hist, ax_rows) = plt.subplots(
        2, 1, figsize=(st.SINGLE_COLUMN * 1.4, 3.0), sharex=True,
        gridspec_kw={"height_ratios": [2.2, 1]},
    )  # fmt: skip
    ax_hist.hist(observed["y_true"], bins=24, range=(0, 1), color="#D9D9D9", edgecolor="white")
    ax_hist.set_ylabel(f"Cell lines (n = {len(observed)})")
    ax_hist.set_title("Observed CLARIFi mSF2 (clonogenic SF2 at 2 Gy, literature median)")
    shown = [(i, d, name) for i, (d, name) in enumerate(lines.items())]
    for i, depmap_id, name in shown:
        rows = oof[oof["depmap_id"] == depmap_id]
        if rows.empty:
            raise FigureInputError(f"{depmap_id} ({name}) is not in oof_predictions")
        y_obs = float(rows["y_true"].iloc[0])
        ax_hist.axvline(y_obs, color=st.INK, lw=0.8, ls=(0, (2, 2)))
        ax_hist.text(y_obs, ax_hist.get_ylim()[1] * (0.92 - 0.12 * i), f" {name}", fontsize=6.5)
        ax_rows.scatter(y_obs, i, s=30, marker="D", color=st.INK, zorder=3)
        for model in models:
            pred = rows.loc[rows["model_id"] == model, "y_pred"]
            if pred.empty:
                raise FigureInputError(f"{name}: no {model} prediction")
            ax_rows.scatter(
                float(pred.iloc[0]), i, s=26, marker=st.marker(model), facecolors="none",
                edgecolors=st.colour(model), linewidths=1.0, zorder=3,
            )  # fmt: skip
    ax_rows.set_yticks([i for i, _, _ in shown])
    ax_rows.set_yticklabels([name for _, _, name in shown])
    ax_rows.set_ylim(-0.6, len(shown) - 0.4)
    ax_rows.set_xlim(0, 1)
    ax_rows.set_xlabel("mSF2")
    st.guides(ax_rows, "x")
    handles = [Line2D([], [], marker="D", color=st.INK, ls="", label="observed")] + [
        _open_handle(st.marker(m), st.colour(m), f"{m} predicted (out-of-fold)") for m in models
    ]
    ax_rows.legend(handles=handles, loc="upper left", bbox_to_anchor=(1.0, 1.0))
    st.footnote(
        fig,
        "Context only. CLARIFi mSF2 is clonogenic survival, not the proliferation/viability\n"
        "endpoints of the Moringa study; nothing here concerns Moringa or radioprotection.",
    )
    fig.tight_layout()
    return fig


def _short(gene_set: str) -> str:
    return gene_set.removeprefix("HALLMARK_").replace("_", " ")


def gene_set_ranking(table_s2: pd.DataFrame, top: int | None = None) -> plt.Figure:
    """S07: exploratory gene-set ranking (publication Table S2), coloured by triage tier."""
    st.apply()
    columns = [
        "rank", "gene_set", "mean_importance", "sd_importance", "positive_importance_share",
        "tier",
    ]  # fmt: skip
    require(table_s2, columns, "table_s2_gene_set_ranking")
    table = table_s2.sort_values("rank")
    table = table.head(top) if top else table
    y = np.arange(len(table))[::-1]
    fig, ax = plt.subplots(figsize=(st.SINGLE_COLUMN * 1.5, 0.13 * len(table) + 1.1))
    ax.axvline(0, color=st.INK, lw=0.6)
    for yi, (_, r) in zip(y, table.iterrows(), strict=True):
        tier_colour = TIER_COLOUR.get(str(r["tier"]), st.MUTED)
        ax.hlines(
            yi, r["mean_importance"] - r["sd_importance"],
            r["mean_importance"] + r["sd_importance"], colors="#CFCFCF", lw=1.0,
        )  # fmt: skip
        ax.scatter(r["mean_importance"], yi, s=16, color=tier_colour, zorder=3)
        ax.text(
            1.01, yi, f"{r['positive_importance_share']:.0%}", transform=ax.get_yaxis_transform(),
            va="center", fontsize=6, color=st.MUTED,
        )  # fmt: skip
    ax.set_yticks(y)
    ax.set_yticklabels([_short(g) for g in table["gene_set"]], fontsize=6)
    ax.set_ylim(-0.8, len(table) - 0.2)
    ax.set_xlabel("Permutation importance on held-out rows\n(increase in component-weighted MAE)")
    ax.text(1.01, 1.0, "importance\n> 0 in", transform=ax.transAxes, fontsize=6, color=st.MUTED)
    present = [t for t in TIER_COLOUR if t in set(table["tier"])]
    ax.legend(
        handles=[
            Line2D([], [], marker="o", ls="", color=TIER_COLOUR[t], label=TIER_LABEL[t])
            for t in present
        ],
        loc="lower right",
    )
    st.guides(ax, "x")
    st.footnote(
        fig,
        "Exploratory: tiers capped at C (no formally shown gain; 0 negative-control draws).\n"
        "Bars: SD across CV fits (split variability, not a confidence interval). Not\n"
        "validated biomarkers or radiation-response mechanisms.",
    )
    fig.tight_layout()
    return fig


def discrepancy_errors(table_s3: pd.DataFrame, top: int = 25) -> plt.Figure:
    """S08: paired held-out errors (M1, M2) of the highest-ranked discrepancy lines."""
    st.apply()
    columns = [
        "rank", "depmap_id", "cell_line_name", "lineage", "abs_error_m1", "abs_error_m2",
        "tier", "triage_category",
    ]  # fmt: skip
    require(table_s3, columns, "table_s3_discrepancy_review")
    ranked = table_s3[table_s3["tier"].isin(["A", "B", "C"])].sort_values("rank").head(top)
    if ranked.empty:
        raise FigureInputError("table_s3: no line reaches tier A, B or C")
    y = np.arange(len(ranked))[::-1]
    fig, ax = plt.subplots(figsize=(st.SINGLE_COLUMN * 1.6, 0.16 * len(ranked) + 1.2))
    for yi, (_, r) in zip(y, ranked.iterrows(), strict=True):
        technical = r["triage_category"] == "technical review first"
        ax.plot([r["abs_error_m1"], r["abs_error_m2"]], [yi, yi], color="#C8C8C8", lw=2.0)
        for model, column in (("M1", "abs_error_m1"), ("M2", "abs_error_m2")):
            ax.scatter(
                r[column], yi, s=20, marker=st.marker(model), zorder=3,
                facecolors="none" if technical else st.colour(model),
                edgecolors=st.colour(model), linewidths=0.9,
            )  # fmt: skip
        ax.text(
            1.01, yi, f"{r['tier']}", transform=ax.get_yaxis_transform(), va="center",
            fontsize=6.5, color=TIER_COLOUR.get(str(r["tier"]), st.MUTED), fontweight="bold",
        )  # fmt: skip
    ax.set_yticks(y)
    ax.set_yticklabels(
        [f"{r['cell_line_name']} · {r['lineage']}" for _, r in ranked.iterrows()], fontsize=6
    )
    ax.set_ylim(-0.8, len(ranked) - 0.2)
    ax.set_xlim(left=0)
    ax.set_xlabel("Absolute error of the repeat-averaged out-of-fold prediction (mSF2)")
    handles = [
        Line2D([], [], marker=st.marker(m), ls="", color=st.colour(m), label=st.label(m))
        for m in ("M1", "M2")
    ] + [_open_handle("o", st.MUTED, "open: technical review first")]
    ax.legend(handles=handles, loc="lower right")
    st.guides(ax, "x")
    st.footnote(
        fig,
        "Measured CLARIFi lines, not independent validation samples. Review signals only;\n"
        "not evidence of unusual radiobiology. Extreme residuals regress on re-measurement.",
    )
    fig.tight_layout()
    return fig
