"""Shared visual identity of the publication figures (one place for every style choice).

- White background, light horizontal/vertical guides only where they aid reading.
- Okabe-Ito colours (colour-blind safe); each model also has its own marker, so models
  stay distinguishable in greyscale. The same model always has the same colour.
- Sans-serif type at 7-9 pt at final size (journal single column 89 mm, double 183 mm).
- Panel labels: bold upper-case A, B, C, ... at the top-left of each panel.
- Direction colours: improvement of the richer model (blue) vs worsening (vermillion);
  never red/green.
"""

from __future__ import annotations

from collections.abc import Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from radiosensitivity_ml.visualization.figures import MODEL_LABEL, MODEL_STYLE, OKABE_ITO

MM = 1 / 25.4  # inches per millimetre
SINGLE_COLUMN = 89 * MM
DOUBLE_COLUMN = 183 * MM

INK = "#222222"  # text and axes
MUTED = "#8C8C8C"  # secondary text, guides, small-sample data
GUIDE = "#E6E6E6"  # light reference grid
IMPROVES = OKABE_ITO["blue"]  # richer model better (positive ΔMAE)
WORSENS = OKABE_ITO["vermillion"]  # richer model worse (negative ΔMAE)

LIMITATION = "Descriptive only: superiority not formally assessed; no negative controls."


def apply() -> None:
    """Global rcParams for every publication figure."""
    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "savefig.facecolor": "white",
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Helvetica", "Liberation Sans", "DejaVu Sans"],
            "font.size": 7.5,
            "axes.titlesize": 8.5,
            "axes.titleweight": "bold",
            "axes.titlelocation": "left",
            "axes.labelsize": 7.5,
            "axes.labelcolor": INK,
            "axes.edgecolor": INK,
            "axes.linewidth": 0.6,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "xtick.color": INK,
            "ytick.color": INK,
            "xtick.labelsize": 7,
            "ytick.labelsize": 7,
            "xtick.major.width": 0.6,
            "ytick.major.width": 0.6,
            "xtick.major.size": 2.5,
            "ytick.major.size": 2.5,
            "legend.fontsize": 7,
            "legend.frameon": False,
            "lines.linewidth": 1.0,
            "savefig.bbox": "tight",
            "savefig.pad_inches": 0.03,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "svg.fonttype": "none",
            "svg.hashsalt": "radiosensitivity_ml",  # deterministic SVG element ids
        }
    )


def colour(model: str) -> str:
    return MODEL_STYLE[model][0]


def marker(model: str) -> str:
    return MODEL_STYLE[model][1]


def label(model: str) -> str:
    """Short legend label, e.g. 'M2 tissue + expression'."""
    return f"{model} {MODEL_LABEL[model].lower()}"


def panel_labels(axes: Iterable[plt.Axes], start: str = "A") -> None:
    """Bold A, B, C ... just outside the top-left corner of each axes."""
    for i, ax in enumerate(axes):
        ax.text(
            -0.02, 1.04, chr(ord(start) + i), transform=ax.transAxes, fontsize=10,
            fontweight="bold", va="bottom", ha="right", color=INK,
        )  # fmt: skip


def guides(ax: plt.Axes, axis: str = "x") -> None:
    """Light reference grid behind the data on one axis."""
    ax.grid(axis=axis, color=GUIDE, lw=0.5, zorder=0)
    ax.set_axisbelow(True)


def footnote(fig: plt.Figure, text: str = LIMITATION) -> None:
    """Small limitation note under the figure (always visible on the figure itself)."""
    fig.text(0.0, -0.01, text, fontsize=6.5, color=MUTED, ha="left", va="top")


# ---------------------------------------------------------------------------------------
# Report theme (version 3; Seaborn). Used by ``visualization.report_figures``.
#
# Rules: no titles, figure numbers, footnotes or explanatory notes inside a figure (all of
# that lives in the report caption); text >= 8 pt at final size; figures drawn at the A4
# text width (210 mm - 2 x 25 mm margins = 160 mm); lowercase bold panel letters only.
# The legacy ``apply``/``footnote`` helpers above are kept unchanged for version-2 figures.
# ---------------------------------------------------------------------------------------

REPORT_WIDTH = 160 * MM  # A4 text block
REPORT_FONT_PT = 8.5
REPORT_SMALL_PT = 8.0  # minimum for any text (project rule: >= 8 pt at final size)
PANEL_LETTER_PT = 9.5

SOFT_INK = "#3B3B3B"  # axes, ticks
FAINT = "#BDBDBD"  # reference lines, connectors
WASH = "#F3F3F3"  # light background bands
OBSERVED = "#4D4D4D"  # observed values (filled, solid)

TIER_ORDER = ("A", "B", "C", "not_prioritised", "not_rankable", "not_assessable")
TIER_COLOUR = {
    "A": "#0072B2",
    "B": "#56B4E9",
    "C": "#009E73",
    "not_prioritised": "#BDBDBD",
    "not_rankable": "#E3E3E3",
    "not_assessable": "#E3E3E3",
}
TIER_LABEL = {
    "A": "Tier A",
    "B": "Tier B",
    "C": "Tier C",
    "not_prioritised": "Not prioritised",
    "not_rankable": "Not rankable",
    "not_assessable": "Not assessable",
}
# Sequential (low = light) and diverging maps; both colour-blind safe and monotone in
# lightness, so they survive greyscale printing.
SEQUENTIAL = "crest"
DIVERGING_ENDS = (IMPROVES, WORSENS)  # blue = richer model better, vermillion = worse


def apply_report() -> None:
    """Seaborn theme plus rcParams shared by every report figure (call before drawing)."""
    import seaborn as sns

    sns.set_theme(
        context="paper",
        style="ticks",
        rc={
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "savefig.facecolor": "white",
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Helvetica", "Liberation Sans", "DejaVu Sans"],
            "font.size": REPORT_FONT_PT,
            "axes.labelsize": REPORT_FONT_PT,
            "axes.titlesize": REPORT_FONT_PT,
            "xtick.labelsize": REPORT_SMALL_PT,
            "ytick.labelsize": REPORT_SMALL_PT,
            "legend.fontsize": REPORT_SMALL_PT,
            "legend.title_fontsize": REPORT_SMALL_PT,
            "legend.frameon": False,
            "text.color": INK,
            "axes.labelcolor": INK,
            "axes.edgecolor": SOFT_INK,
            "axes.linewidth": 0.6,
            "axes.labelpad": 4.0,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": False,
            "grid.color": GUIDE,
            "grid.linewidth": 0.5,
            "xtick.color": SOFT_INK,
            "ytick.color": SOFT_INK,
            "xtick.major.width": 0.6,
            "ytick.major.width": 0.6,
            "xtick.major.size": 3.0,
            "ytick.major.size": 3.0,
            # Seaborn's "paper" context scales several font sizes below the project's
            # 8 pt floor. Every size that can carry text is set explicitly here, and
            # minor ticks are switched off so no unlabelled marks survive on
            # categorical axes and heatmaps.
            "figure.titlesize": REPORT_FONT_PT,
            "figure.labelsize": REPORT_FONT_PT,
            "xtick.minor.size": 0.0,
            "ytick.minor.size": 0.0,
            "xtick.minor.width": 0.0,
            "ytick.minor.width": 0.0,
            "lines.linewidth": 1.0,
            "patch.linewidth": 0.0,
            "savefig.bbox": "tight",
            "savefig.pad_inches": 0.04,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        },
    )


def model_palette(models: Iterable[str]) -> dict[str, str]:
    """The project-wide model colours (identical in every figure)."""
    return {m: colour(m) for m in models}


def short_label(model: str) -> str:
    """Two-line tick label, e.g. 'M2\\ntissue + expression'."""
    return f"{model}\n{MODEL_LABEL[model].lower()}"


def panel_letter(ax: plt.Axes, letter: str) -> None:
    """Lowercase bold panel letter just above the top-left corner of the axes."""
    ax.annotate(
        letter, xy=(0, 1), xycoords="axes fraction", xytext=(-18, 8),
        textcoords="offset points", fontsize=PANEL_LETTER_PT, fontweight="bold",
        ha="left", va="bottom", color=INK, annotation_clip=False,
    )  # fmt: skip


def reference_line(ax: plt.Axes, value: float = 0.0, axis: str = "x") -> None:
    """Thin solid reference line (e.g. zero) behind the data."""
    draw = ax.axvline if axis == "x" else ax.axhline
    draw(value, color=SOFT_INK, lw=0.6, zorder=0.5)


def no_ticks(ax: plt.Axes, axis: str = "both") -> None:
    """Remove tick marks while keeping the tick labels (for heatmaps and category axes).

    A heatmap cell is already bounded by its own edges, so the tick marks beside the
    labels carry no information and only add clutter.
    """
    ax.tick_params(axis=axis, which="both", length=0)


def light_grid(ax: plt.Axes, axis: str = "x") -> None:
    """Very light guide lines on one axis only, behind the data."""
    ax.grid(axis=axis, color=GUIDE, lw=0.5, zorder=0)
    ax.set_axisbelow(True)


def short_gene_set(name: str) -> str:
    """'HALLMARK_P53_PATHWAY' -> 'P53 pathway' (display only)."""
    words = name.removeprefix("HALLMARK_").split("_")
    keep_upper = {"P53", "MYC", "KRAS", "UV", "DNA", "TNFA", "NFKB", "IL2", "STAT5", "IL6",
                  "JAK", "STAT3", "TGF", "PI3K", "AKT", "MTOR", "MTORC1", "E2F", "G2M", "V1",
                  "V2", "WNT"}  # fmt: skip
    direction = {"UP": "up", "DN": "down"}
    out = [direction.get(w, w if w in keep_upper else w.lower()) for w in words]
    text = " ".join(out)
    return text[0].upper() + text[1:] if text else text
