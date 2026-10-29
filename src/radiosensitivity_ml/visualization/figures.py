"""Publication figures from SAVED evaluation tables only (never refits or recomputes).

Every function validates its input table's columns and refuses to plot an empty or
malformed table. Observed values and predictions are drawn distinctly; sample sizes
and the definition of every interval are written on the figure. Colours follow the
Okabe-Ito palette (colour-blind safe) and remain distinguishable in greyscale through
marker shape. Each figure is saved as PDF, SVG and PNG (dpi from configs/figures.yaml).
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

OKABE_ITO = {
    "black": "#000000",
    "orange": "#E69F00",
    "sky": "#56B4E9",
    "green": "#009E73",
    "yellow": "#F0E442",
    "blue": "#0072B2",
    "vermillion": "#D55E00",
    "purple": "#CC79A7",
}
MODEL_STYLE = {
    "M0": (OKABE_ITO["black"], "x"),
    "M1": (OKABE_ITO["blue"], "o"),
    "M1P": (OKABE_ITO["sky"], "s"),
    "M2": (OKABE_ITO["vermillion"], "^"),
    "M2P": (OKABE_ITO["orange"], "v"),
    "M2X": (OKABE_ITO["purple"], "D"),
    "M3": (OKABE_ITO["green"], "P"),
}
MODEL_LABEL = {
    "M0": "Global mean",
    "M1": "Tissue only",
    "M1P": "Tissue + proliferation",
    "M2": "Tissue + expression",
    "M2P": "Tissue + proliferation + expression",
    "M2X": "Expression only",
    "M3": "Random forest",
}


class FigureInputError(ValueError):
    """Raised when a results table is missing, empty or lacks required columns."""


def style() -> None:
    """Consistent typography for all figures."""
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.size": 8,
            "axes.titlesize": 9,
            "axes.labelsize": 8,
            "legend.fontsize": 8,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "ps.fonttype": 42,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "savefig.bbox": "tight",
            "pdf.fonttype": 42,
            "svg.fonttype": "none",
            "svg.hashsalt": "radiosensitivity_ml",  # deterministic SVG element ids
        }
    )


def require(table: pd.DataFrame, columns: Sequence[str], name: str) -> None:
    """Validate a results table before plotting."""
    if table is None or table.empty:
        raise FigureInputError(f"{name}: table is empty; run evaluate_models.py first")
    missing = [c for c in columns if c not in table.columns]
    if missing:
        raise FigureInputError(f"{name}: missing columns {missing}")


FIXED_METADATA = {
    "pdf": {"CreationDate": None, "ModDate": None},
    "svg": {"Date": None},
    "png": {},
}


def save(fig: plt.Figure, out_dir: Path, stem: str, dpi: int, formats: Sequence[str]) -> list[Path]:
    """Save one figure in every requested format (never overwrites; no timestamps)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for fmt in formats:
        path = out_dir / f"{stem}.{fmt}"
        if path.exists():
            raise FileExistsError(f"{path} exists; figures are write-once (bump the version)")
        fig.savefig(path, dpi=dpi if fmt == "png" else None, metadata=FIXED_METADATA.get(fmt))
        paths.append(path)
    plt.close(fig)
    return paths


def observed_vs_predicted(oof: pd.DataFrame, models: Sequence[str] = ("M1", "M2")) -> plt.Figure:
    """Observed raw mSF2 vs out-of-fold prediction (mean over repeats), one panel per model."""
    require(oof, ["model_id", "y_true", "y_pred", "n_repeats"], "oof_predictions")
    fig, axes = plt.subplots(
        1, len(models), figsize=(3.2 * len(models), 3.2), sharex=True, sharey=True
    )
    for ax, model in zip(list(axes) if len(models) > 1 else [axes], models, strict=True):
        part = oof[oof["model_id"] == model]
        if part.empty:
            raise FigureInputError(f"no predictions for {model}")
        colour, marker = MODEL_STYLE[model]
        ax.scatter(
            part["y_pred"], part["y_true"], s=10, c=colour, marker=marker, alpha=0.7, linewidths=0
        )
        ax.plot([0, 1], [0, 1], color="0.5", lw=0.8, ls="--")
        ax.set(
            xlim=(0, 1), ylim=(0, 1), xlabel="Predicted mSF2 (out-of-fold, mean over repeats)",
            title=f"{MODEL_LABEL[model]} (n = {len(part)} lines)",
        )  # fmt: skip
    (axes[0] if len(models) > 1 else axes).set_ylabel("Observed mSF2 (CLARIFi)")
    return fig


NO_INTERVAL = "none"


def effect_forest(comparisons: pd.DataFrame, method: str) -> plt.Figure:
    """dMAE point estimates with the interval of the given method, one row per analysis.

    ``method: none`` (descriptive-only route, D04.06) draws point estimates only: no
    interval is validated, so none is shown.
    """
    with_interval = method != NO_INTERVAL
    columns = ["comparison", "scale", "delta_mae", "n_components"]
    if with_interval:
        columns += [f"{method}_lower", f"{method}_upper"]
    require(comparisons, columns, "comparisons")
    table = comparisons.reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(5.0, 0.35 * len(table) + 1.0))
    for i, row in table.iterrows():
        if with_interval:
            ax.errorbar(
                row["delta_mae"], i,
                xerr=[[row["delta_mae"] - row[f"{method}_lower"]], [row[f"{method}_upper"] - row["delta_mae"]]],
                fmt="o", color=OKABE_ITO["vermillion"], ms=4, capsize=2, lw=1,
            )  # fmt: skip
        else:
            ax.plot(row["delta_mae"], i, "o", color=OKABE_ITO["vermillion"], ms=4)
    ax.axvline(0, color="0.4", lw=0.8)
    ax.set_yticks(range(len(table)))
    ax.set_yticklabels(
        [f"{r.comparison} [{r.scale}] (n = {r.n_components})" for r in table.itertuples()]
    )
    ax.invert_yaxis()
    note = (
        f"90% interval: {method}"
        if with_interval
        else "point estimates; no interval (superiority not formally assessed)"
    )
    ax.set_xlabel(f"Paired component-weighted ΔMAE (>0: richer model better)\n{note}")
    return fig


def tissue_errors(errors: pd.DataFrame, models: Sequence[str] = ("M1", "M2")) -> plt.Figure:
    """Component-weighted MAE per lineage for each model (descriptive), with n per lineage."""
    require(errors, ["model_id", "lineage", "mae", "n_components"], "tissue_errors")
    lineages = (
        errors[errors["model_id"] == models[0]]
        .sort_values("n_components", ascending=False)["lineage"]
        .tolist()
    )
    fig, ax = plt.subplots(figsize=(4.5, 0.25 * len(lineages) + 1.0))
    for offset, model in enumerate(models):
        part = errors[errors["model_id"] == model].set_index("lineage").reindex(lineages)
        colour, marker = MODEL_STYLE[model]
        y = [i + (offset - 0.5) * 0.25 for i in range(len(lineages))]
        ax.scatter(part["mae"], y, c=colour, marker=marker, s=14, label=MODEL_LABEL[model])
    counts = errors[errors["model_id"] == models[0]].set_index("lineage")["n_components"]
    ax.set_yticks(range(len(lineages)))
    ax.set_yticklabels([f"{name} (n = {counts[name]})" for name in lineages])
    ax.invert_yaxis()
    ax.set_xlabel("Component-weighted MAE (out-of-fold, mean over repeats)")
    ax.legend(frameon=False)
    return fig


def repeat_distribution(per_repeat: pd.DataFrame, comparison: str) -> plt.Figure:
    """dMAE of each cross-validation repeat (split variability, not sampling uncertainty)."""
    require(per_repeat, ["comparison", "scale", "repeat", "delta_mae"], "per_repeat_delta_mae")
    part = per_repeat[per_repeat["comparison"] == comparison]
    if part.empty:
        raise FigureInputError(f"no repeats for {comparison!r}")
    fig, ax = plt.subplots(figsize=(3.5, 2.5))
    for i, (_scale, values) in enumerate(part.groupby("scale")["delta_mae"]):
        ax.scatter([i] * len(values), values, s=10, c=OKABE_ITO["blue"], alpha=0.7)
    ax.set_xticks(range(part["scale"].nunique()))
    ax.set_xticklabels(sorted(part["scale"].unique()))
    ax.axhline(0, color="0.4", lw=0.8)
    ax.set_ylabel("ΔMAE per CV repeat")
    ax.set_title(f"{comparison}\n(spread across repeats = split variability)")
    return fig


def stability_vs_null(tests: pd.DataFrame, top: int = 15) -> plt.Figure:
    """Mean gene-set importance with BH decisions against both nulls (descriptive)."""
    require(
        tests,
        [
            "tested_importance_repeat0",
            "bh_permuted_outcome",
            "bh_random_sets",
            "attribution_permitted",
        ],
        "gene_set_tests",
    )
    table = tests.sort_values("tested_importance_repeat0", ascending=False).head(top).iloc[::-1]
    colours = [
        OKABE_ITO["vermillion"] if a else OKABE_ITO["sky"] for a in table["attribution_permitted"]
    ]
    fig, ax = plt.subplots(figsize=(4.5, 0.25 * len(table) + 1.0))
    ax.barh(range(len(table)), table["tested_importance_repeat0"], color=colours)
    ax.set_yticks(range(len(table)))
    ax.set_yticklabels([str(i).removeprefix("HALLMARK_") for i in table.index])
    ax.set_xlabel("Permutation importance, mean over repeat-0 folds (increase in weighted MAE)")
    ax.set_title("Dark: attribution permitted (gain shown + BH q=0.05 vs both nulls)")
    return fig


def cross_assay(concordance: pd.DataFrame) -> plt.Figure:
    """Exploratory cross-assay rank concordance (Spearman rho with interval), by direction."""
    require(
        concordance, ["direction", "model_id", "spearman_rho", "lower", "upper", "n"], "cross_assay"
    )
    fig, ax = plt.subplots(figsize=(4.0, 0.35 * len(concordance) + 1.0))
    for i, row in enumerate(concordance.itertuples()):
        colour, marker = MODEL_STYLE.get(row.model_id, (OKABE_ITO["black"], "o"))
        ax.errorbar(
            row.spearman_rho, i, xerr=[[row.spearman_rho - row.lower], [row.upper - row.spearman_rho]],
            fmt=marker, color=colour, capsize=2, ms=4,
        )  # fmt: skip
    ax.set_yticks(range(len(concordance)))
    ax.set_yticklabels(
        [f"{r.direction} {r.model_id} (n = {r.n})" for r in concordance.itertuples()]
    )
    ax.axvline(0, color="0.4", lw=0.8)
    ax.set_xlabel("Spearman ρ (exploratory; different endpoints, not validation)")
    return fig


def supplementary_case_lines(
    oof: pd.DataFrame, lines: dict[str, str], model: str = "M2"
) -> plt.Figure:
    """Supplementary context: MCF-7 and DU145 on the solid-tumour distribution.

    Observed (filled) and out-of-fold predicted (open) mSF2 for the named lines; no
    claim about extracts, PEF or radioprotection (protocol §19).
    """
    require(oof, ["model_id", "depmap_id", "y_true", "y_pred"], "oof_predictions")
    part = oof[oof["model_id"] == model]
    fig, ax = plt.subplots(figsize=(4.0, 2.6))
    ax.hist(part["y_true"], bins=20, range=(0, 1), color="0.85", edgecolor="0.6")
    for i, (depmap_id, name) in enumerate(lines.items()):
        row = part[part["depmap_id"] == depmap_id]
        if row.empty:
            continue
        colour = [OKABE_ITO["blue"], OKABE_ITO["vermillion"]][i % 2]
        ax.axvline(row["y_true"].iloc[0], color=colour, lw=1.2, label=f"{name}: observed")
        ax.axvline(row["y_pred"].iloc[0], color=colour, lw=1.2, ls=":", label=f"{name}: predicted")
    ax.set_xlabel("mSF2")
    ax.set_ylabel(f"Lines (n = {len(part)})")
    ax.legend(frameon=False)
    ax.set_title("Supplementary context only; hypothesis-generating")
    return fig
