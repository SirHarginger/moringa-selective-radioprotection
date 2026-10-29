"""Report figures, version 3 (Seaborn; shared theme in ``visualization.style``).

Every function draws SAVED tables only (evaluation, explainability, triage and compound
outputs); nothing is refitted, re-predicted or re-scored. Inputs are validated before
drawing.

Presentation contract (checked by ``tests/test_report_figures.py``):
- no titles, figure numbers, footnotes or explanatory notes inside a figure; captions,
  methods notes and limitations live in the report;
- the only free text on a figure is short: lowercase panel letters, value labels, short
  series labels (at most ``MAX_TEXT_CHARS`` characters each);
- text is at least 8 pt at final size; figures are drawn at the A4 text width;
- model colours are identical in every figure (``style.model_palette``).

Statistical contract:
- out-of-fold predictions are shown once per independent component (records of a
  component averaged; each record's prediction already averaged over CV repeats), so
  repeated predictions of one line are never shown as independent points;
- bars that encode magnitude start at zero; small differences are shown on their own
  axis with a zero reference and, where useful, a relative scale, never on a truncated
  bar axis;
- no fitted trend lines, no intervals or significance marks (no inference was validated);
- no clustering or reordering by similarity (rows follow prespecified ranks or values).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import ListedColormap
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle

from radiosensitivity_ml.visualization import style as st
from radiosensitivity_ml.visualization.figures import FigureInputError, require

MAX_TEXT_CHARS = 40
PRIMARY = "primary: tissue+expression vs tissue"
SENSITIVITY = "S1: beyond tissue+proliferation"
COMPARISON_TICK = {PRIMARY: "M2 vs M1\nprimary", SENSITIVITY: "M2P vs M1P\nsensitivity"}
COMPARISON_MODELS = {PRIMARY: ("M2", "M1"), SENSITIVITY: ("M2P", "M1P")}
MODEL_TICK = {
    "M0": "M0 · global mean",
    "M1": "M1 · tissue",
    "M1P": "M1P · tissue + proliferation",
    "M2": "M2 · tissue + expression",
    "M2P": "M2P · tissue + proliferation\n+ expression",
}
ALL_MODELS = ("M0", "M1", "M1P", "M2", "M2P")
# Stacked labels for the narrow categorical axis of the variability figure (Figure S1).
MODEL_TICK_STACKED = {
    "M0": "M0\nglobal mean",
    "M1": "M1\ntissue",
    "M1P": "M1P\ntissue\n+ proliferation",
    "M2": "M2\ntissue\n+ expression",
    "M2P": "M2P\ntissue\n+ proliferation\n+ expression",
}
OTHER_TISSUES = "Other tissues (pooled)"

# Display names for compound rows (display only; the tables keep the full names). The two
# systematic names are far longer than the text limit and squeezed the panels of Figures 8
# and 9. "Acetylated moringin" is the synonym recorded in Table C1, with the acetyl
# position stated as that record requires.
_ACETYL_ITC = "4-[(4'-O-Acetyl-alpha-L-rhamnosyloxy)benzyl] isothiocyanate"
COMPOUND_DISPLAY = {
    _ACETYL_ITC: "Acetylated moringin (4'-O-acetyl)",
    "O-Ethyl-4-(alpha-L-rhamnosyloxy)benzyl carbamate": "O-Ethyl rhamnosyloxybenzyl carbamate",
}


def display_compound(name: str) -> str:
    """Short display name for a compound row; Greek prefixes as symbols (display only)."""
    text = COMPOUND_DISPLAY.get(name, name)
    for word, symbol in (("alpha-", "α-"), ("beta-", "β-")):
        if text.startswith(word):
            text = symbol + text.removeprefix(word)
    return text


def _signed_ticks(ax: plt.Axes, axis: str, decimals: int, bins: int = 5) -> None:
    """At most ``bins`` ticks with a fixed number of decimals and a true minus sign."""
    from matplotlib.ticker import FuncFormatter, MaxNLocator

    def fmt(value: float, _pos: int) -> str:
        text = f"{value:.{decimals}f}"
        if float(text) == 0.0:
            text = f"{0.0:.{decimals}f}"
        return text.replace("-", "−")

    target = ax.xaxis if axis == "x" else ax.yaxis
    target.set_major_locator(MaxNLocator(nbins=bins))
    target.set_major_formatter(FuncFormatter(fmt))


def _sns():  # imported lazily so the package imports without Seaborn installed
    import seaborn as sns

    return sns


def _figure(height_mm: float) -> plt.Figure:
    st.apply_report()
    return plt.figure(figsize=(st.REPORT_WIDTH, height_mm * st.MM), layout="constrained")


LEGEND_TEXT = {"tier": "Tier", "flagged": "Review flag", "level": "Evidence level",
               "groups": "Research groups (n)"}  # fmt: skip


def _relabel_legend(ax: plt.Axes, loc: str, figure: bool = False, **kwargs: object) -> None:
    """Move a Seaborn legend (keeping its handles), drop its title, readable entry labels.

    ``figure=True`` moves it to the figure, which is what an "outside ..." location needs:
    constrained layout then reserves space for the legend instead of clipping it.
    """
    existing = ax.get_legend()
    if existing is None:
        return
    handles = list(existing.legend_handles)
    labels = []
    for text in existing.get_texts():
        value = text.get_text()
        label = LEGEND_TEXT.get(value) or st.TIER_LABEL.get(value)
        labels.append(label or (value[:1].upper() + value[1:]))
    existing.remove()  # rebuilt below; a Seaborn legend cannot be moved axes -> figure
    if figure:
        ax.get_figure().legend(handles=handles, labels=labels, loc=loc, handletextpad=0.3, **kwargs)
    else:
        ax.legend(
            handles=handles, labels=labels, loc=loc, handletextpad=0.3,
            borderaxespad=0.2, **kwargs,
        )  # fmt: skip


def _raw_metrics(metrics: pd.DataFrame, models: Sequence[str]) -> pd.DataFrame:
    require(metrics, ["model_id", "scale", "mae", "rmse", "r2_oos"], "model_metrics")
    raw = metrics[metrics["scale"] == "raw"].set_index("model_id")
    missing = [m for m in models if m not in raw.index]
    if missing:
        raise FigureInputError(f"model_metrics: no raw row for {missing}")
    if raw.index.duplicated().any():
        raise FigureInputError("model_metrics: duplicated raw rows")
    return raw.loc[list(models)]


def component_points(oof: pd.DataFrame, models: Sequence[str]) -> pd.DataFrame:
    """One row per (model, lineage, component): mean observed and mean predicted mSF2.

    Each record's prediction is already the mean over CV repeats; records of one
    relationship component are averaged so that related lines count once. Components are
    keyed by lineage as in ``evaluation.metrics.tissue_errors``.
    """
    require(oof, ["model_id", "component_id", "lineage", "y_true", "y_pred"], "oof_predictions")
    part = oof[oof["model_id"].isin(models)]
    missing = sorted(set(models) - set(part["model_id"]))
    if missing:
        raise FigureInputError(f"oof_predictions: no predictions for {missing}")
    return part.groupby(["model_id", "lineage", "component_id"], as_index=False).agg(
        y_true=("y_true", "mean"), y_pred=("y_pred", "mean"), n_records=("y_true", "size")
    )


# ------------------------------------------------------------------ dataset overview


def dataset_overview(
    oof: pd.DataFrame,
    context_lines: Mapping[str, str] | None = None,
    min_components: int = 10,
    model: str = "M1",
) -> plt.Figure:
    """(a) Independent components per tissue; (b) observed mSF2 per tissue (one point per
    component; tissues below ``min_components`` pooled). Context lines are marked."""
    sns = _sns()
    require(oof, ["model_id", "depmap_id", "component_id", "lineage", "y_true"], "oof")
    obs = oof[oof["model_id"] == model]
    if obs.empty:
        raise FigureInputError(f"oof_predictions: no rows for {model}")
    comp = obs.groupby(["lineage", "component_id"], as_index=False).agg(
        y_true=("y_true", "mean"), depmap_ids=("depmap_id", lambda s: ";".join(sorted(s)))
    )
    counts = comp.groupby("lineage").size().sort_values(ascending=False, kind="stable")
    large = [t for t in counts.index if counts[t] >= min_components]
    comp["group"] = np.where(comp["lineage"].isin(large), comp["lineage"], OTHER_TISSUES)
    medians = comp[comp["group"] != OTHER_TISSUES].groupby("group")["y_true"].median()
    order = list(medians.sort_values(kind="stable").index)
    if (comp["group"] == OTHER_TISSUES).any():
        order.append(OTHER_TISSUES)
    group_n = comp.groupby("group").size()

    fig = _figure(96)
    grid = fig.add_gridspec(1, 2, width_ratios=[1.0, 1.55])
    ax_n, ax_d = fig.add_subplot(grid[0]), fig.add_subplot(grid[1])

    frame = counts.rename_axis("tissue").reset_index(name="n")
    shades = {t: ("#4C8DB8" if counts[t] >= min_components else "#C9C9C9") for t in frame["tissue"]}
    sns.barplot(
        data=frame, y="tissue", x="n", hue="tissue", palette=shades, legend=False,
        width=0.72, ax=ax_n,
    )  # fmt: skip
    for container in ax_n.containers:
        ax_n.bar_label(container, padding=2, fontsize=st.REPORT_SMALL_PT, color=st.SOFT_INK)
    ax_n.axvline(min_components, color=st.FAINT, lw=0.8, ls=(0, (2, 2)), zorder=0.5)
    ax_n.set(xlabel="Independent components (n)", ylabel="", xlim=(0, counts.max() * 1.18))
    ax_n.tick_params(axis="y", length=0)
    sns.despine(ax=ax_n, left=True)

    sns.boxplot(
        data=comp, y="group", x="y_true", order=order, width=0.58, showfliers=False,
        color="#E9EEF2", linewidth=0.7, ax=ax_d,
        medianprops={"color": st.INK, "linewidth": 1.2},
        whiskerprops={"color": st.SOFT_INK}, capprops={"color": st.SOFT_INK},
        boxprops={"edgecolor": st.SOFT_INK},
    )  # fmt: skip
    sns.stripplot(
        data=comp, y="group", x="y_true", order=order, size=2.8, jitter=0.2,
        color="#2F6F95", alpha=0.7, linewidth=0, ax=ax_d,
    )  # fmt: skip
    for depmap_id, name in (context_lines or {}).items():
        hit = comp[comp["depmap_ids"].str.split(";").apply(lambda ids, d=depmap_id: d in ids)]
        if hit.empty:
            raise FigureInputError(f"context line {depmap_id} ({name}) not in oof_predictions")
        row = hit.iloc[0]
        y = order.index(row["group"])
        ax_d.scatter(
            row["y_true"], y, marker="D", s=34, facecolor="white", edgecolor=st.INK,
            linewidth=1.1, zorder=5,
        )  # fmt: skip
        ax_d.annotate(
            name, xy=(row["y_true"], y), xytext=(5, 5), textcoords="offset points",
            fontsize=st.REPORT_SMALL_PT, color=st.INK, ha="left", va="bottom",
        )  # fmt: skip
    ax_d.set_yticks(range(len(order)), [f"{g} ({int(group_n[g])})" for g in order])
    ax_d.set(xlim=(0, 1), xlabel="Observed mSF2 (clonogenic SF2 at 2 Gy)", ylabel="")
    ax_d.tick_params(axis="y", length=0)
    st.light_grid(ax_d, "x")
    sns.despine(ax=ax_d, left=True)
    st.panel_letter(ax_n, "a")
    st.panel_letter(ax_d, "b")
    return fig


# ----------------------------------------------------------------- model performance


def model_performance(
    metrics: pd.DataFrame,
    per_repeat: pd.DataFrame,
    comparisons: pd.DataFrame,
    models: Sequence[str] = ALL_MODELS,
    shown: Sequence[str] = (PRIMARY, SENSITIVITY),
    reference: str = "M1",
) -> plt.Figure:
    """(a) MAE (bars from zero); (b) out-of-sample R²; (c) ΔMAE of every CV repeat for the
    primary and sensitivity comparisons, with the pooled estimate (mean of repeats)."""
    sns = _sns()
    rows = _raw_metrics(metrics, models)
    require(per_repeat, ["repeat", "delta_mae", "comparison"], "per_repeat_delta_mae")
    require(comparisons, ["comparison", "model", "comparator", "delta_mae"], "comparisons")
    palette = st.model_palette(models)

    fig = _figure(112)
    grid = fig.add_gridspec(2, 2, height_ratios=[1.0, 0.82], width_ratios=[1.25, 1.0])
    ax_a = fig.add_subplot(grid[0, 0])
    ax_b = fig.add_subplot(grid[0, 1], sharey=ax_a)
    ax_c = fig.add_subplot(grid[1, :])

    frame = rows.reset_index()[["model_id", "mae", "r2_oos"]]
    sns.barplot(
        data=frame, y="model_id", x="mae", hue="model_id", palette=palette, order=list(models),
        hue_order=list(models), legend=False, width=0.64, ax=ax_a,
    )  # fmt: skip
    for container in ax_a.containers:
        ax_a.bar_label(container, fmt="%.4f", padding=2, fontsize=st.REPORT_SMALL_PT)
    ax_a.set_yticks(range(len(models)), [MODEL_TICK.get(m, m) for m in models])
    ax_a.set(xlim=(0, float(frame["mae"].max()) * 1.32), ylabel="")
    ax_a.set_xlabel("MAE (mSF2; lower is better)")
    ax_a.tick_params(axis="y", length=0)
    sns.despine(ax=ax_a, left=True)

    y = np.arange(len(models))
    r2 = frame["r2_oos"].to_numpy()
    span = max(0.1, float(np.abs(r2).max()) * 1.6)
    st.reference_line(ax_b, 0.0, "x")
    ax_b.hlines(y, 0, r2, colors=[palette[m] for m in models], lw=1.6, zorder=2)
    for yi, value, model in zip(y, r2, models, strict=True):
        ax_b.scatter(
            value, yi, s=34, marker=st.marker(model), color=palette[model], zorder=3,
            linewidths=1.0 if st.marker(model) in ("x", "+") else 0.4,
            edgecolors=None if st.marker(model) in ("x", "+") else "white",
        )  # fmt: skip
        ax_b.annotate(
            f"{value:+.3f}", xy=(value, yi), xytext=(0, 6), textcoords="offset points",
            ha="center", va="bottom", fontsize=st.REPORT_SMALL_PT, color=st.SOFT_INK,
        )  # fmt: skip
    ax_b.set(xlim=(-span, span), xlabel="Out-of-sample R²")
    ax_b.tick_params(axis="y", left=False, labelleft=False)
    st.light_grid(ax_b, "x")
    sns.despine(ax=ax_b, left=True)

    part = per_repeat[per_repeat["comparison"].isin(shown)].copy()
    for name in shown:
        if part[part["comparison"] == name].empty:
            raise FigureInputError(f"per_repeat_delta_mae: no rows for {name!r}")
        if len(comparisons[comparisons["comparison"] == name]) != 1:
            raise FigureInputError(f"comparisons: expected one row for {name!r}")
    part["label"] = part["comparison"].map(lambda c: COMPARISON_TICK.get(c, c))
    part["sign"] = np.where(part["delta_mae"] > 0, "positive", "non-positive")
    labels = [COMPARISON_TICK.get(c, c) for c in shown]
    sns.stripplot(
        data=part, x="delta_mae", y="label", order=labels, hue="sign",
        palette={"positive": st.IMPROVES, "non-positive": st.WORSENS}, jitter=0.14, size=5.5,
        edgecolor="white", linewidth=0.5, legend=False, ax=ax_c,
    )  # fmt: skip
    for i, name in enumerate(shown):
        row = comparisons[comparisons["comparison"] == name].iloc[0]
        pooled, model = float(row["delta_mae"]), str(row["model"])
        ax_c.plot([pooled, pooled], [i - 0.34, i + 0.34], color=st.colour(model), lw=2.4,
                  solid_capstyle="butt", zorder=4)  # fmt: skip
    st.reference_line(ax_c, 0.0, "x")
    limit = float(np.abs(part["delta_mae"]).max()) * 1.4
    ax_c.set(xlim=(-limit, limit), ylabel="")
    ax_c.set_xlabel("ΔMAE per CV repeat (mSF2)\n> 0 favours the richer model")
    ref = float(rows.loc[reference, "mae"])
    top = ax_c.secondary_xaxis(
        "top", functions=(lambda x: 100 * x / ref, lambda p: p * ref / 100)
    )  # fmt: skip
    top.set_xlabel(f"Relative to MAE({reference}) (%)")
    top.tick_params(labelsize=st.REPORT_SMALL_PT)
    ax_c.tick_params(axis="y", length=0)
    st.light_grid(ax_c, "x")
    sns.despine(ax=ax_c, left=True)
    ax_a.set_ylim(len(models) - 0.5, -0.5)  # shared with (b): keep the categorical rows
    for ax, letter in ((ax_a, "a"), (ax_b, "b"), (ax_c, "c")):
        st.panel_letter(ax, letter)
    return fig


# -------------------------------------------------------------- prediction behaviour


def prediction_behaviour(oof: pd.DataFrame, models: Sequence[str] = ("M1", "M2")) -> plt.Figure:
    """(a, b) Observed vs out-of-fold predicted mSF2 per component with the identity line;
    (c) empirical cumulative distributions of observed and predicted values."""
    sns = _sns()
    points = component_points(oof, models)
    fig = _figure(62)
    grid = fig.add_gridspec(1, len(models) + 1, width_ratios=[1.0] * len(models) + [1.15])
    axes = [fig.add_subplot(grid[i]) for i in range(len(models) + 1)]
    for ax, model in zip(axes, models, strict=False):
        part = points[points["model_id"] == model]
        ax.plot([0, 1], [0, 1], color=st.FAINT, lw=0.8, ls=(0, (3, 2)), zorder=1)
        sns.scatterplot(
            data=part, x="y_pred", y="y_true", color=st.colour(model), marker=st.marker(model),
            s=15, alpha=0.75, edgecolor="white", linewidth=0.3, legend=False, ax=ax, zorder=2,
        )  # fmt: skip
        ax.text(
            0.05, 0.95, MODEL_TICK.get(model, model).split("\n")[0], transform=ax.transAxes,
            ha="left", va="top", fontsize=st.REPORT_SMALL_PT, color=st.colour(model),
        )  # fmt: skip
        ax.set(xlim=(0, 1), ylim=(0, 1), aspect="equal")
        ax.set(xlabel="Predicted mSF2 (out-of-fold)", ylabel="Observed mSF2")
        ax.set_xticks([0, 0.5, 1])
        ax.set_yticks([0, 0.5, 1])
    for ax in axes[1 : len(models)]:
        ax.set_ylabel("")
    ax_e = axes[-1]
    observed = points[points["model_id"] == models[0]]["y_true"]
    sns.ecdfplot(x=observed, color=st.OBSERVED, lw=1.6, label="Observed", ax=ax_e)
    for model in models:
        sns.ecdfplot(
            x=points.loc[points["model_id"] == model, "y_pred"], color=st.colour(model),
            lw=1.4, ls=(0, (4, 2)), label=f"{model} predicted", ax=ax_e,
        )  # fmt: skip
    ax_e.set(xlim=(0, 1), ylim=(0, 1.01), xlabel="mSF2", ylabel="Cumulative proportion")
    ax_e.set_xticks([0, 0.5, 1])
    ax_e.legend(loc="lower right", handlelength=2.2)
    st.light_grid(ax_e, "y")
    for ax, letter in zip(axes, "abc", strict=False):
        st.panel_letter(ax, letter)
    return fig


def prediction_variability(oof: pd.DataFrame, models: Sequence[str] = ALL_MODELS) -> plt.Figure:
    """Supplementary: SD of each line's out-of-fold prediction across CV repeats, by model
    (one value per record; split-to-split variability, not a prediction interval)."""
    sns = _sns()
    require(oof, ["model_id", "y_pred_sd"], "oof_predictions")
    part = oof[oof["model_id"].isin(models)].copy()
    if part.empty or part["y_pred_sd"].isna().all():
        raise FigureInputError("oof_predictions: no repeat SDs for the requested models")
    fig = _figure(64)
    ax = fig.add_subplot()
    sns.violinplot(
        data=part, x="model_id", y="y_pred_sd", order=list(models), hue="model_id",
        hue_order=list(models), palette=st.model_palette(models), legend=False, cut=0,
        inner="quart", linewidth=0.7, density_norm="width", saturation=0.85, ax=ax,
    )  # fmt: skip
    for collection in ax.collections:
        collection.set_alpha(0.55)
    # stacked labels: the one-line labels overlapped at the A4 text width
    ax.set_xticks(range(len(models)), [MODEL_TICK_STACKED.get(m, m) for m in models])
    ax.set(xlabel="", ylabel="SD of out-of-fold prediction\nacross CV repeats (mSF2)")
    ax.set_ylim(bottom=0)
    ax.tick_params(axis="x", length=0)
    st.light_grid(ax, "y")
    sns.despine(ax=ax, bottom=True)
    return fig


# ---------------------------------------------------------------- tissue performance


def tissue_performance(
    errors: pd.DataFrame, min_components: int = 10, models: Sequence[str] = ALL_MODELS
) -> plt.Figure:
    """(a) Component-weighted MAE by tissue and model (tissues with >= ``min_components``);
    (b) MAE(M1) − MAE(M2) per tissue, same row order."""
    sns = _sns()
    require(errors, ["model_id", "lineage", "mae", "n_components"], "tissue_errors")
    wide = errors.pivot(index="lineage", columns="model_id", values="mae")
    missing = [m for m in models if m not in wide.columns]
    if missing or "M1" not in wide.columns or "M2" not in wide.columns:
        raise FigureInputError(f"tissue_errors: missing models {missing or ['M1', 'M2']}")
    n = errors[errors["model_id"] == "M1"].set_index("lineage")["n_components"]
    keep = [t for t in wide.index if n.get(t, 0) >= min_components]
    if not keep:
        raise FigureInputError(f"tissue_errors: no tissue with >= {min_components} components")
    wide = wide.loc[keep, list(models)]
    if wide.isna().any().any():
        raise FigureInputError("tissue_errors: every model needs every retained tissue")
    delta = (wide["M1"] - wide["M2"]).sort_values(ascending=False, kind="stable")
    order = list(delta.index)

    fig = _figure(82)
    grid = fig.add_gridspec(2, 2, height_ratios=[0.05, 1.0], width_ratios=[1.7, 1.0])
    cax = fig.add_subplot(grid[0, 0])
    ax_h = fig.add_subplot(grid[1, 0])
    ax_b = fig.add_subplot(grid[1, 1])
    sns.heatmap(
        wide.loc[order], annot=True, fmt=".3f", cmap=st.SEQUENTIAL, linewidths=0.8,
        linecolor="white", ax=ax_h, cbar_ax=cax, cbar_kws={"orientation": "horizontal"},
        annot_kws={"fontsize": st.REPORT_SMALL_PT},
    )  # fmt: skip
    cax.set_xlabel("MAE (mSF2)", fontsize=st.REPORT_SMALL_PT)
    cax.xaxis.set_label_position("top")
    cax.tick_params(labelsize=st.REPORT_SMALL_PT, length=2)
    ax_h.set_yticks(
        np.arange(len(order)) + 0.5, [f"{t} ({int(n[t])})" for t in order], rotation=0
    )  # fmt: skip
    ax_h.set_xticks(np.arange(len(models)) + 0.5, list(models), rotation=0)
    ax_h.set(xlabel="", ylabel="")
    ax_h.tick_params(length=0)

    frame = pd.DataFrame({"tissue": order, "delta": delta.to_numpy()})
    colours = {t: (st.IMPROVES if d > 0 else st.WORSENS) for t, d in zip(order, delta, strict=True)}
    sns.barplot(
        data=frame, y="tissue", x="delta", hue="tissue", palette=colours, order=order,
        legend=False, width=0.6, ax=ax_b,
    )  # fmt: skip
    limit = float(np.abs(delta).max()) * 1.9
    for i, d in enumerate(delta.to_numpy()):
        ax_b.annotate(
            f"{d:+.4f}", xy=(d, i), xytext=(3 if d > 0 else -3, 0), textcoords="offset points",
            ha="left" if d > 0 else "right", va="center", fontsize=st.REPORT_SMALL_PT,
            color=st.SOFT_INK,
        )  # fmt: skip
    st.reference_line(ax_b, 0.0, "x")
    ax_b.set(xlim=(-limit, limit), ylabel="", xlabel="MAE(M1) − MAE(M2) (mSF2)")
    ax_b.tick_params(axis="y", left=False, labelleft=False)
    st.light_grid(ax_b, "x")
    sns.despine(ax=ax_b, left=True)
    st.panel_letter(ax_h, "a")
    st.panel_letter(ax_b, "b")
    return fig


# -------------------------------------------------------------------- explainability


def gene_set_importance(
    table_s2: pd.DataFrame,
    importance_per_task: pd.DataFrame,
    top: int = 15,
    exploratory_share: float = 0.5,
    max_share_zero: float = 0.5,
) -> plt.Figure:
    """(a) Held-out permutation importance of the top-ranked Hallmark scores in every M2
    fit (grey) and their mean (coloured by prespecified tier); (b) the two tier-C criteria
    for all 50 sets: share of fits with importance > 0 and share of fits selecting the set.

    ``importance_per_task``: rows = gene sets, columns = fits (``real|r<k>|f<j>``)."""
    sns = _sns()
    columns = ["rank", "gene_set", "mean_importance", "positive_importance_share",
               "share_zero_coefficient", "tier"]  # fmt: skip
    require(table_s2, columns, "table_s2_gene_set_ranking")
    if importance_per_task is None or importance_per_task.empty:
        raise FigureInputError("importance_per_task: table is empty")
    ranked = table_s2.sort_values("rank", kind="stable")
    head = ranked.head(top)
    absent = [g for g in head["gene_set"] if g not in importance_per_task.index]
    if absent:
        raise FigureInputError(f"importance_per_task: no rows for {absent}")
    fits = [c for c in importance_per_task.columns if str(c).startswith("real|")]
    if not fits:
        raise FigureInputError("importance_per_task: no real-data fit columns")
    long = (
        importance_per_task.loc[list(head["gene_set"]), fits]
        .rename_axis("gene_set")
        .reset_index()
        .melt(id_vars="gene_set", var_name="fit", value_name="importance")
    )
    long["label"] = long["gene_set"].map(st.short_gene_set)
    labels = [st.short_gene_set(g) for g in head["gene_set"]]

    fig = _figure(92)
    grid = fig.add_gridspec(1, 2, width_ratios=[1.45, 1.0])
    ax_a, ax_b = fig.add_subplot(grid[0]), fig.add_subplot(grid[1])
    st.reference_line(ax_a, 0.0, "x")
    sns.stripplot(
        data=long, x="importance", y="label", order=labels, color="#A3A3A3", size=2.3,
        alpha=0.6, jitter=0.24, linewidth=0, ax=ax_a,
    )  # fmt: skip
    for i, (_, row) in enumerate(head.iterrows()):
        ax_a.scatter(
            row["mean_importance"], i, marker="D", s=30, color=st.TIER_COLOUR.get(
                str(row["tier"]), st.MUTED), edgecolor="white", linewidth=0.6, zorder=5,
        )  # fmt: skip
    ax_a.set(xlabel="Permutation importance on held-out rows\n(increase in MAE, mSF2)",
             ylabel="")  # fmt: skip
    _signed_ticks(ax_a, "x", decimals=3, bins=4)  # default ticks collided at this width
    ax_a.tick_params(axis="y", length=0)
    st.light_grid(ax_a, "x")
    sns.despine(ax=ax_a, left=True)
    present = [t for t in st.TIER_ORDER if t in set(head["tier"].astype(str))]
    handles = [Line2D([], [], marker="o", ls="", color="#A3A3A3", markersize=3.5,
                      label="Single CV fit")]  # fmt: skip
    handles += [
        Line2D(
            [],
            [],
            marker="D",
            ls="",
            color=st.TIER_COLOUR[t],
            markersize=5,
            label=f"Mean · {st.TIER_LABEL[t][:1].lower()}{st.TIER_LABEL[t][1:]}",
        )
        for t in present
    ]
    ax_a.legend(handles=handles, loc="lower right", handletextpad=0.4)

    frame = ranked.assign(
        selected=1.0 - ranked["share_zero_coefficient"],
        tier=ranked["tier"].astype(str),
    )
    ax_b.add_patch(
        Rectangle((exploratory_share, 1.0 - max_share_zero), 1.0 - exploratory_share + 0.02,
                  max_share_zero + 0.02, facecolor=st.WASH, edgecolor="none", zorder=0)
    )  # fmt: skip
    ax_b.axvline(exploratory_share, color=st.FAINT, lw=0.8, ls=(0, (2, 2)), zorder=1)
    ax_b.axhline(1.0 - max_share_zero, color=st.FAINT, lw=0.8, ls=(0, (2, 2)), zorder=1)
    tiers = [t for t in st.TIER_ORDER if t in set(frame["tier"])]
    sns.scatterplot(
        data=frame, x="positive_importance_share", y="selected", hue="tier", hue_order=tiers,
        palette={t: st.TIER_COLOUR[t] for t in tiers}, s=26, alpha=0.9, edgecolor="white",
        linewidth=0.4, ax=ax_b, zorder=3,
    )  # fmt: skip
    _relabel_legend(ax_b, "lower right")  # the lower-right corner holds no points
    ax_b.set(xlim=(-0.03, 1.03), ylim=(-0.03, 1.03), aspect="equal")
    ax_b.set(xlabel="Share of fits with importance > 0", ylabel="Share of fits selecting the set")
    ax_b.set_xticks([0, 0.5, 1])
    ax_b.set_yticks([0, 0.5, 1])
    st.panel_letter(ax_a, "a")
    st.panel_letter(ax_b, "b")
    return fig


def gene_set_correlation(
    table_s2: pd.DataFrame, correlation: pd.DataFrame, tiers: Sequence[str] = ("C",)
) -> plt.Figure:
    """Supplementary: Spearman correlation between the scores of the tier-C sets and of
    every set flagged as sharing signal with them (rank order kept; no clustering)."""
    sns = _sns()
    require(table_s2, ["rank", "gene_set", "tier", "shared_signal_caveat"], "table_s2")
    if correlation is None or correlation.empty:
        raise FigureInputError("gene_set_score_correlation: table is empty")
    chosen = table_s2[table_s2["tier"].astype(str).isin(tiers)].sort_values("rank")
    if chosen.empty:
        raise FigureInputError(f"table_s2: no gene set in tiers {list(tiers)}")
    names = list(chosen["gene_set"])
    for caveat in chosen["shared_signal_caveat"].dropna().astype(str):
        for token in caveat.replace(":", " ").split():
            if token.startswith("HALLMARK_") and token not in names:
                names.append(token)
    absent = [g for g in names if g not in correlation.index or g not in correlation.columns]
    if absent:
        raise FigureInputError(f"gene_set_score_correlation: no rows for {absent}")
    matrix = correlation.loc[names, names].astype(float)
    labels = [st.short_gene_set(g) for g in names]
    mask = np.triu(np.ones_like(matrix, dtype=bool), k=1)
    cmap = _sns().blend_palette([st.IMPROVES, "#F7F7F7", st.WORSENS], n_colors=11, as_cmap=True)
    size = 18 + 7.2 * len(names)
    fig = _figure(min(size, 150))
    ax = fig.add_subplot()
    sns.heatmap(
        matrix, mask=mask, cmap=cmap, vmin=-1, vmax=1, center=0, annot=True, fmt=".2f",
        annot_kws={"fontsize": st.REPORT_SMALL_PT}, linewidths=0.8, linecolor="white",
        square=True, xticklabels=labels, yticklabels=labels, ax=ax,
        cbar_kws={"label": "Spearman ρ between set scores", "shrink": 0.6},
    )  # fmt: skip
    ax.tick_params(length=0)
    ax.set_xticklabels(labels, rotation=40, ha="right")
    ax.set(xlabel="", ylabel="")
    return fig


# ------------------------------------------------------------ cell-line discrepancies

FLAG_PREDICTION = "#E3B5CF"  # reddish-purple tint (Okabe-Ito #CC79A7)
FLAG_DATA = "#F2C18D"  # orange tint (Okabe-Ito #E69F00)
FLAG_COLUMNS = {
    "Repeat instability": ("prediction", "prediction unstable across CV repeats"),
    "Model disagreement": ("prediction", "M1 and M2 disagree strongly"),
    "Stranded RNA": ("data", "stranded RNA profile"),
    "Related lines": ("data", "related lines in the cohort"),
    "Identity flag (relative)": ("data", "Cellosaurus problem flag on a relative"),
    "Small tissue group": ("data", "small tissue group"),
}


def flag_matrix(table: pd.DataFrame) -> pd.DataFrame:
    """0 = no flag, 1 = prediction-behaviour flag, 2 = data or identity flag, per line."""
    flags = table["technical_flags"].fillna("").astype(str)
    out = pd.DataFrame(index=table.index)
    for column, (kind, text) in FLAG_COLUMNS.items():
        out[column] = np.where(flags.str.contains(text, regex=False), 1 if kind == "prediction"
                               else 2, 0)  # fmt: skip
    return out


def cell_line_discrepancies(
    table_s3: pd.DataFrame,
    context_lines: Mapping[str, str] | None = None,
    matrix_tiers: Sequence[str] = ("A", "B"),
) -> plt.Figure:
    """(a) Residual of the repeat-averaged M2 prediction against observed mSF2 for every
    measured line, coloured by discrepancy tier; (b) technical and prediction flags of the
    tier A and B lines (rank order)."""
    sns = _sns()
    columns = ["rank", "depmap_id", "cell_line_name", "lineage", "observed_msf2", "pred_m2",
               "tier", "technical_flags"]  # fmt: skip
    require(table_s3, columns, "table_s3_discrepancy_review")
    frame = table_s3.copy()
    frame["tier"] = frame["tier"].astype(str)
    frame["residual"] = frame["observed_msf2"] - frame["pred_m2"]
    frame["flagged"] = np.where(
        frame["technical_flags"].fillna("").astype(str).str.strip() != "",
        "technical flag", "no technical flag",
    )  # fmt: skip
    selected = frame[frame["tier"].isin(matrix_tiers)].sort_values("rank", kind="stable")
    if selected.empty:
        raise FigureInputError(f"table_s3: no line in tiers {list(matrix_tiers)}")

    fig = _figure(max(96, 30 + 3.7 * len(selected)))
    grid = fig.add_gridspec(1, 2, width_ratios=[1.15, 1.0])
    ax_a, ax_b = fig.add_subplot(grid[0]), fig.add_subplot(grid[1])
    tiers = [t for t in st.TIER_ORDER if t in set(frame["tier"])]
    layer = frame.assign(_z=frame["tier"].map({t: i for i, t in enumerate(reversed(tiers))}))
    layer = layer.sort_values("_z", kind="stable")
    st.reference_line(ax_a, 0.0, "y")
    sns.scatterplot(
        data=layer, x="observed_msf2", y="residual", hue="tier", hue_order=tiers,
        palette={t: st.TIER_COLOUR[t] for t in tiers}, style="flagged",
        markers={"no technical flag": "o", "technical flag": "^"},
        style_order=["no technical flag", "technical flag"], s=22, alpha=0.9,
        edgecolor="white", linewidth=0.35, ax=ax_a,
    )  # fmt: skip
    _relabel_legend(ax_a, "upper left")
    for depmap_id, name in (context_lines or {}).items():
        hit = frame[frame["depmap_id"] == depmap_id]
        if hit.empty:
            raise FigureInputError(f"context line {depmap_id} ({name}) not in table_s3")
        row = hit.iloc[0]
        ax_a.scatter(row["observed_msf2"], row["residual"], s=60, facecolor="none",
                     edgecolor=st.INK, linewidth=0.9, zorder=6)  # fmt: skip
        ax_a.annotate(
            name, xy=(row["observed_msf2"], row["residual"]), xytext=(6, -10),
            textcoords="offset points", fontsize=st.REPORT_SMALL_PT, color=st.INK,
        )  # fmt: skip
    limit = float(np.abs(frame["residual"]).max()) * 1.08
    ax_a.set(xlim=(0, 1), ylim=(-limit, limit), xlabel="Observed mSF2",
             ylabel="Observed − predicted mSF2 (M2)")  # fmt: skip
    st.light_grid(ax_a, "y")

    # cell codes: 0 none, 1 prediction-behaviour flag, 2 data/identity flag, 3 + k = tier k
    matrix = flag_matrix(selected)
    tier_codes = selected["tier"].map({t: 3 + i for i, t in enumerate(matrix_tiers)})
    full = pd.concat([tier_codes.rename("Tier"), matrix], axis=1).astype(float)
    full.index = [f"{n} · {lin}" for n, lin in zip(selected["cell_line_name"],
                                                   selected["lineage"], strict=True)]  # fmt: skip
    colours = ["#FFFFFF", FLAG_PREDICTION, FLAG_DATA] + [st.TIER_COLOUR[t] for t in matrix_tiers]
    sns.heatmap(
        full, cmap=ListedColormap(colours), vmin=-0.5, vmax=len(colours) - 0.5, cbar=False,
        linewidths=1.0, linecolor="#E4E4E4", ax=ax_b,
    )  # fmt: skip
    for i, tier in enumerate(selected["tier"]):
        ax_b.text(0.5, i + 0.5, tier, ha="center", va="center", fontsize=st.REPORT_SMALL_PT,
                  color="white" if tier == "A" else st.INK, fontweight="bold")  # fmt: skip
    ax_b.set_xticks(np.arange(full.shape[1]) + 0.5, list(full.columns), rotation=40, ha="right")
    ax_b.set_yticks(np.arange(full.shape[0]) + 0.5, list(full.index), rotation=0)
    ax_b.tick_params(length=0)
    ax_b.set(xlabel="", ylabel="")
    ax_b.yaxis.tick_right()
    # A figure-level legend in an "outside" location: constrained layout reserves room for
    # it, whereas an axes legend anchored beyond the axes (bbox_to_anchor) is not accounted
    # for and is clipped at the figure edge.
    fig.legend(
        handles=[
            Patch(facecolor=FLAG_PREDICTION, label="Prediction behaviour"),
            Patch(facecolor=FLAG_DATA, label="Data or identity"),
        ],
        loc="outside upper right", ncols=2, handlelength=1.0,
    )  # fmt: skip
    st.panel_letter(ax_a, "a")
    st.panel_letter(ax_b, "b")
    return fig


# --------------------------------------------------------------------------- compounds

SCORE_COLUMNS = {
    "d1_moringa_identity": ("Moringa identity", 2),
    "d2_radiation_biology": ("Radiation biology", 3),
    "d3_independent_sources": ("Independent sources", 2),
    "d4_feasibility": ("Feasibility", 1),
}
EXTRACTION_LEVEL = {
    "dcm_documented": ("DCM extract", "#1B6F6A"),
    "seed_or_leaf_other_solvent": ("Other solvent", "#9DCFC9"),
    "indirect_or_unconfirmed": ("Indirect", "#FFFFFF"),
}
EVIDENCE_LEVEL = {
    "L3_radiation": ("Ionising radiation", "#0072B2"),
    "L2_process": ("Process without radiation", "#56B4E9"),
    "L1_indirect": ("Indirect", "#C9C9C9"),
}


def compound_scorecard(ranking: pd.DataFrame, include_not_prioritised: bool = True) -> plt.Figure:
    """(a) Points per prespecified dimension (shade = share of the dimension's maximum) and
    extraction-specific evidence; (b) total priority score (0–8) coloured by tier."""
    sns = _sns()
    columns = ["rank", "preferred_name", "extraction_category", "total_score", "tier",
               *SCORE_COLUMNS]  # fmt: skip
    require(ranking, columns, "candidate_ranking")
    frame = ranking.copy()
    frame["tier"] = frame["tier"].astype(str)
    keep = ["A", "B", "C"] + (["not_prioritised"] if include_not_prioritised else [])
    frame = frame[frame["tier"].isin(keep)].sort_values("rank", kind="stable")
    if frame.empty:
        raise FigureInputError("candidate_ranking: no ranked compound to show")
    names = [display_compound(n) for n in frame["preferred_name"]]
    shares = pd.DataFrame(
        {label: frame[c].astype(float) / top for c, (label, top) in SCORE_COLUMNS.items()}
    )
    points = pd.DataFrame({label: frame[c].astype(int) for c, (label, _) in SCORE_COLUMNS.items()})
    shares.index = points.index = names
    unknown = sorted(set(frame["extraction_category"]) - set(EXTRACTION_LEVEL))
    if unknown:
        raise FigureInputError(f"candidate_ranking: unknown extraction categories {unknown}")
    codes = frame["extraction_category"].map(list(EXTRACTION_LEVEL).index).to_numpy()

    fig = _figure(max(80, 52 + 6.0 * len(names)))
    grid = fig.add_gridspec(1, 3, width_ratios=[0.3, 1.3, 1.0])
    ax_x = fig.add_subplot(grid[0])
    ax_a = fig.add_subplot(grid[1], sharey=ax_x)
    ax_b = fig.add_subplot(grid[2], sharey=ax_x)
    extraction = pd.DataFrame({"Extract": codes}, index=names).astype(float)
    sns.heatmap(
        extraction, cmap=ListedColormap([v[1] for v in EXTRACTION_LEVEL.values()]),
        vmin=-0.5, vmax=len(EXTRACTION_LEVEL) - 0.5, cbar=False, linewidths=1.0,
        linecolor="#D9D9D9", ax=ax_x,
    )  # fmt: skip
    # column headings are rotated: set side by side they collided at this width
    ax_x.set_xticks([0.5], ["Extract"], rotation=35, ha="right", rotation_mode="anchor")
    ax_x.set(xlabel="", ylabel="")
    ax_x.tick_params(length=0)
    sns.heatmap(
        shares, cmap=st.SEQUENTIAL, vmin=0, vmax=1, annot=points, fmt="d", cbar=False,
        annot_kws={"fontsize": st.REPORT_SMALL_PT}, linewidths=1.0, linecolor="white", ax=ax_a,
    )  # fmt: skip
    ax_a.set_xticks(np.arange(points.shape[1]) + 0.5, list(points.columns), rotation=35,
                    ha="right", rotation_mode="anchor")  # fmt: skip
    ax_a.tick_params(axis="y", left=False, labelleft=False)
    ax_a.tick_params(axis="x", length=0)
    ax_a.set(xlabel="", ylabel="")
    totals = pd.DataFrame({"compound": names, "total": frame["total_score"].astype(float),
                           "tier": frame["tier"].to_numpy()})  # fmt: skip
    y = np.arange(len(names)) + 0.5
    ax_b.barh(y, totals["total"], height=0.62, color=[st.TIER_COLOUR[t] for t in totals["tier"]],
              zorder=2)  # fmt: skip
    for yi, value in zip(y, totals["total"], strict=True):
        ax_b.annotate(f"{value:.0f}", xy=(value, yi), xytext=(3, 0), textcoords="offset points",
                      va="center", fontsize=st.REPORT_SMALL_PT)  # fmt: skip
    ax_b.set(xlim=(0, 8.6), xlabel="Total priority score (0–8)")
    ax_b.set_xticks(range(0, 9, 2))
    ax_b.tick_params(axis="y", left=False, labelleft=False)
    st.light_grid(ax_b, "x")
    sns.despine(ax=ax_b, left=True)
    present = [t for t in st.TIER_ORDER if t in set(totals["tier"])]
    handles = [Patch(facecolor=st.TIER_COLOUR[t], label=st.TIER_LABEL[t]) for t in present]
    handles += [Patch(facecolor=c, edgecolor="#BDBDBD", label=label)
                for label, c in EXTRACTION_LEVEL.values()]  # fmt: skip
    # Below the panels, in a layout-managed slot: inside panel (b) it covered the bars.
    fig.legend(handles=handles, loc="outside lower center", ncol=4, handlelength=1.0,
               handletextpad=0.4, columnspacing=1.4)  # fmt: skip
    # the three axes share y: set rows and labels last (each heatmap resets shared ticks)
    ax_x.set_ylim(len(names), 0)
    ax_x.set_yticks(np.arange(len(names)) + 0.5, names, rotation=0)
    for ax in (ax_a, ax_b):
        ax.tick_params(axis="y", left=False, labelleft=False)
    st.panel_letter(ax_x, "a")
    st.panel_letter(ax_b, "b")
    return fig


def compound_evidence_map(
    evidence: pd.DataFrame, ranking: pd.DataFrame, overlap: pd.DataFrame | None = None
) -> plt.Figure:
    """(a) Biological processes with primary evidence per compound: dot size = independent
    research groups, colour = strongest evidence level; (b) documented gene overlap between
    each compound's reported genes and the tier-C Hallmark sets (blank = none recorded)."""
    sns = _sns()
    require(evidence, ["compound_id", "process_category", "evidence_level", "research_group",
                       "counts_for_score"], "compound_biology_evidence")  # fmt: skip
    require(ranking, ["rank", "compound_id", "preferred_name", "tier"], "candidate_ranking")
    ranked = ranking[ranking["tier"].astype(str).isin(["A", "B", "C"])].sort_values("rank")
    if ranked.empty:
        raise FigureInputError("candidate_ranking: no compound in tiers A-C")
    names = dict(zip(ranked["compound_id"], map(display_compound, ranked["preferred_name"]),
                     strict=True))  # fmt: skip
    used = evidence[evidence["compound_id"].isin(names) & evidence["counts_for_score"].astype(bool)]
    levels = list(EVIDENCE_LEVEL)
    used = used[used["evidence_level"].isin(levels)].copy()
    if used.empty:
        raise FigureInputError("compound_biology_evidence: no scored evidence for tiers A-C")
    used["level_rank"] = used["evidence_level"].map(levels.index)
    cells = used.groupby(["compound_id", "process_category"], as_index=False).agg(
        groups=("research_group", "nunique"), best=("level_rank", "min")
    )
    cells["compound"] = cells["compound_id"].map(names)
    cells["level"] = cells["best"].map(lambda i: EVIDENCE_LEVEL[levels[i]][0])
    process_order = sorted(cells["process_category"].unique())
    compound_order = [names[c] for c in ranked["compound_id"]]
    # numeric positions: Seaborn would otherwise order string categories by appearance
    cells["x"] = cells["process_category"].map(process_order.index)
    cells["y"] = cells["compound"].map(compound_order.index)

    part = pd.DataFrame()
    if overlap is not None and not overlap.empty:
        require(overlap, ["compound_id", "gene_set", "n_overlapping_genes"], "overlap")
        part = overlap[overlap["compound_id"].isin(names) & (overlap["n_overlapping_genes"] > 0)]
    with_overlap = not part.empty
    n_sets = int(part["gene_set"].nunique()) if with_overlap else 0
    fig = _figure(max(90, 70 + 6.2 * len(compound_order)))
    # Panel widths follow their column counts so cells have the same width in both panels.
    grid = fig.add_gridspec(1, 2, width_ratios=[len(process_order), n_sets]) if (
        with_overlap) else fig.add_gridspec(1, 1)  # fmt: skip
    ax_a = fig.add_subplot(grid[0])
    sns.scatterplot(
        data=cells, x="x", y="y", size="groups", sizes=(30, 150),
        hue="level", hue_order=[v[0] for v in EVIDENCE_LEVEL.values()],
        palette={v[0]: v[1] for v in EVIDENCE_LEVEL.values()}, edgecolor="white",
        linewidth=0.6, ax=ax_a, legend="brief", zorder=3,
    )  # fmt: skip
    ax_a.set_xticks(range(len(process_order)))
    ax_a.set_xticklabels([p.replace("_", " ") for p in process_order], rotation=40, ha="right",
                         rotation_mode="anchor")  # fmt: skip
    ax_a.set_xlim(-0.6, len(process_order) - 0.4)
    ax_a.set_yticks(range(len(compound_order)), compound_order)
    ax_a.set_ylim(len(compound_order) - 0.5, -0.5)  # same row spacing as the heatmap in (b)
    ax_a.set(xlabel="", ylabel="")
    ax_a.tick_params(length=0)
    ax_a.grid(color=st.GUIDE, lw=0.5, zorder=0)
    ax_a.set_axisbelow(True)
    # Below the panels, in a layout-managed slot. Beside them (and with the long systematic
    # compound names) it left both panels only a few millimetres wide.
    _relabel_legend(ax_a, "outside lower center", figure=True, ncol=4, columnspacing=1.4)
    st.panel_letter(ax_a, "a")
    if with_overlap:
        ax_b = fig.add_subplot(grid[1])
        table = part.pivot_table(index="compound_id", columns="gene_set",
                                 values="n_overlapping_genes", aggfunc="sum")  # fmt: skip
        table = table.reindex(index=list(ranked["compound_id"]))
        table.index = compound_order
        table.columns = [st.short_gene_set(g) for g in table.columns]
        sns.heatmap(
            table, cmap=st.SEQUENTIAL, annot=True, fmt=".0f", cbar=False, linewidths=1.0,
            linecolor="white", annot_kws={"fontsize": st.REPORT_SMALL_PT}, ax=ax_b,
            mask=table.isna(),
        )  # fmt: skip
        ax_b.set_facecolor("#FAFAFA")
        ax_b.set_xticklabels(list(table.columns), rotation=40, ha="right",
                             rotation_mode="anchor")  # fmt: skip
        ax_b.tick_params(axis="y", left=False, labelleft=False)
        ax_b.tick_params(axis="x", length=0)
        ax_b.set(xlabel="", ylabel="")
        st.panel_letter(ax_b, "b")
    return fig


FIGURES = {
    "dataset_overview": dataset_overview,
    "model_performance": model_performance,
    "prediction_behaviour": prediction_behaviour,
    "prediction_variability": prediction_variability,
    "tissue_performance": tissue_performance,
    "gene_set_importance": gene_set_importance,
    "gene_set_correlation": gene_set_correlation,
    "cell_line_discrepancies": cell_line_discrepancies,
    "compound_scorecard": compound_scorecard,
    "compound_evidence_map": compound_evidence_map,
}
