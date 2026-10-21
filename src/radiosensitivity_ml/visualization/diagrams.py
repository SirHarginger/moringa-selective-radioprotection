"""Conceptual methods diagrams (no data): workflow, triage rules, evidence, validation.

These figures show the study design. They contain no predictions, measurements,
statistics or results, and their sidecars say ``data_provenance: conceptual_diagram``.
The triage-rule diagram (fig_s04) takes every label from ``triage.rules.criteria_text``
with the frozen thresholds of ``configs/triage.yaml``, so it cannot drift from the
implemented rules.

Coordinates are millimetres at final print size (double column, 180 mm wide), so 8 pt
text stays 8 pt. Box kinds differ by fill, edge weight and line style, so they stay
distinguishable in greyscale; fills are light tints of the Okabe-Ito palette with black
text. ``Figure.diagram_boxes`` lists (patch, text) pairs so tests can check that every
label fits inside its box and that no labels overlap.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import pairwise

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

from radiosensitivity_ml.triage.rules import CellLineRules, PathwayRules, criteria_text

MM = 1 / 25.4
TEXT_PT = 8
PANEL_PT = 9
LINE = "#000000"


@dataclass(frozen=True)
class BoxStyle:
    face: str
    edge: str
    linestyle: str
    linewidth: float
    text: str = "#000000"


STYLES = {
    "source": BoxStyle("#D6ECF9", "#0072B2", "solid", 0.8),  # sky-blue tint
    "process": BoxStyle("#FFFFFF", "#000000", "solid", 0.8),
    "gate": BoxStyle("#FBE6BD", "#000000", "solid", 1.6),  # orange tint, heavy edge
    "secondary": BoxStyle("#F4DCEA", "#8E3D6C", "solid", 0.8),  # reddish-purple tint
    "outcome": BoxStyle("#CDEDE3", "#00694D", "solid", 0.8),  # bluish-green tint
    "deferred": BoxStyle("#FFFFFF", "#555555", "dashed", 0.8, text="#333333"),
    "note": BoxStyle("#F2F2F2", "#999999", "solid", 0.5),
}
LEGEND_LABELS = {
    "source": "Input or evidence",
    "process": "Investigator-run step",
    "gate": "Decision rule or gate",
    "secondary": "Secondary output",
    "outcome": "Tier or category",
    "deferred": "Deferred / not assessable",
    "note": "Design note",
}


@dataclass(frozen=True)
class Box:
    x: float
    y: float
    w: float
    h: float

    @property
    def top(self) -> tuple[float, float]:
        return (self.x + self.w / 2, self.y + self.h)

    @property
    def bottom(self) -> tuple[float, float]:
        return (self.x + self.w / 2, self.y)

    @property
    def left(self) -> tuple[float, float]:
        return (self.x, self.y + self.h / 2)

    @property
    def right(self) -> tuple[float, float]:
        return (self.x + self.w, self.y + self.h / 2)


def canvas(width_mm: float, height_mm: float) -> tuple[plt.Figure, plt.Axes]:
    """Blank figure whose data coordinates are millimetres."""
    fig = plt.figure(figsize=(width_mm * MM, height_mm * MM))
    ax = fig.add_axes((0, 0, 1, 1))
    ax.set_xlim(0, width_mm)
    ax.set_ylim(0, height_mm)
    ax.axis("off")
    fig.diagram_boxes = []  # type: ignore[attr-defined]
    return fig, ax


def box(
    ax: plt.Axes,
    x: float,
    y: float,
    w: float,
    h: float,
    text: str,
    kind: str,
    align: str = "center",
) -> Box:
    """Draw a labelled box (x, y = lower-left corner, mm) and register it for tests."""
    style = STYLES[kind]
    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0,rounding_size=1.2",
        facecolor=style.face,
        edgecolor=style.edge,
        linestyle=style.linestyle,
        linewidth=style.linewidth,
    )
    ax.add_patch(patch)
    label = ax.text(
        x + w / 2 if align == "center" else x + 2.0,
        y + h / 2,
        text,
        ha=align,
        va="center",
        fontsize=TEXT_PT,
        color=style.text,
        linespacing=1.25,
    )
    ax.figure.diagram_boxes.append((patch, label))  # type: ignore[attr-defined]
    return Box(x, y, w, h)


def arrow(
    ax: plt.Axes,
    points: list[tuple[float, float]],
    label: str | None = None,
    dashed: bool = False,
    label_at: tuple[float, float] | None = None,
) -> None:
    """Polyline with an arrow head on the last segment; optional 8 pt label at ``label_at``."""
    linestyle = (0, (3, 2)) if dashed else "solid"
    for start, end in pairwise(points[:-1]):
        ax.plot([start[0], end[0]], [start[1], end[1]], color=LINE, lw=0.8, linestyle=linestyle)
    ax.annotate(
        "",
        xy=points[-1],
        xytext=points[-2],
        arrowprops={
            "arrowstyle": "-|>",
            "mutation_scale": 8,
            "lw": 0.8,
            "color": LINE,
            "linestyle": linestyle,
            "shrinkA": 0,
            "shrinkB": 0,
        },
    )
    if label and label_at:
        ax.text(*label_at, label, fontsize=TEXT_PT, ha="left", va="center")


def down(ax: plt.Axes, upper: Box, lower: Box, x: float | None = None, **kwargs: object) -> None:
    """Vertical arrow from the bottom of ``upper`` to the top of ``lower``."""
    x = upper.bottom[0] if x is None else x
    arrow(ax, [(x, upper.y), (x, lower.y + lower.h)], **kwargs)  # type: ignore[arg-type]


def panel_letter(ax: plt.Axes, x: float, y: float, letter: str, title: str) -> None:
    ax.text(x, y, letter, fontsize=PANEL_PT, fontweight="bold", ha="left", va="top")
    ax.text(x + 5, y, title, fontsize=TEXT_PT, fontweight="bold", ha="left", va="top")


def legend(ax: plt.Axes, x: float, y: float, kinds: list[str]) -> None:
    """Legend of box kinds (swatch + label) from (x, y); wraps to a second row if needed."""
    start, right = x, ax.get_xlim()[1] - 2
    for kind in kinds:
        style = STYLES[kind]
        if x + 7.5 + 1.75 * len(LEGEND_LABELS[kind]) > right:
            x, y = start, y - 4.5
        ax.add_patch(
            FancyBboxPatch(
                (x, y),
                6,
                3.5,
                boxstyle="round,pad=0,rounding_size=0.8",
                facecolor=style.face,
                edgecolor=style.edge,
                linestyle=style.linestyle,
                linewidth=style.linewidth,
            )
        )
        label = LEGEND_LABELS[kind]
        ax.text(x + 7.5, y + 1.75, label, fontsize=TEXT_PT, ha="left", va="center")
        x += 7.5 + 1.75 * len(label) + 3


# ------------------------------------------------------------------ fig_04


def study_workflow() -> plt.Figure:
    """Overall research workflow, from sources to secondary triage (conceptual)."""
    fig, ax = canvas(180, 192)
    legend(ax, 6, 185, ["source", "process", "gate", "secondary"])
    sources = [
        "CLARIFi\nmSF2: literature-\nmedian clonogenic\nSF2 at 2 Gy",
        "DepMap 24Q4\nRNA-seq expression\nlog2(TPM + 1)",
        "Cellosaurus\nidentity, problem\nflags, relatives",
        "MSigDB Hallmark\nv2025.1.Hs\n50 gene sets",
    ]
    tops = [box(ax, 6 + i * 42.67, 163, 40, 18, t, "source") for i, t in enumerate(sources)]
    qc = box(
        ax,
        6,
        143,
        112,
        14,
        "Identifier QC (frozen, hash-pinned)\n"
        "solid-tumour lines with verified identity and RNA profile\n"
        "related lines grouped into relationship components",
        "process",
    )
    for source in tops[:3]:
        arrow(ax, [source.bottom, (source.bottom[0], qc.y + qc.h)])
    rows = [
        (
            126,
            11,
            "gate",
            [
                "Protocol freeze and investigator signature",
                "endpoint, models, grids, gates and triage thresholds fixed",
            ],
        ),
        (
            109,
            11,
            "process",
            [
                "Coverage simulation on synthetic outcomes (real structure)",
                "adopts the interval method and the number of CV repeats",
            ],
        ),
        (
            92,
            11,
            "process",
            [
                "Split table frozen and hashed before the outcome is loaded",
                "grouped by component, stratified by tissue",
            ],
        ),
        (
            68,
            18,
            "process",
            [
                "Nested grouped cross-validation (5 × 5 folds, R repeats)",
                "M0 global mean · M1 tissue ridge · M1P + proliferation",
                "M2 tissue + Hallmark scores · M2P + proliferation",
                "all tuning and scaling inside training folds",
            ],
        ),
        (
            48,
            14,
            "gate",
            [
                "Primary comparison (confirmatory)",
                "paired component-weighted ΔMAE, M2 vs M1, raw scale",
                "one-sided 95% lower bound > 0: 'gain shown'",
            ],
        ),
        (
            28,
            14,
            "process",
            [
                "Explainability on saved models (outer-test rows)",
                "permutation importance · coefficient-sign consistency",
                "nulls: permuted outcome, random gene sets; BH q = 0.05",
            ],
        ),
        (
            8,
            14,
            "secondary",
            [
                "Triage rankings (secondary, hypothesis-generating)",
                "gene sets · measured cell lines · discrepancy review",
                "never alters the primary comparison or inference",
            ],
        ),
    ]
    previous, main = qc, []
    for y, h, kind, lines in rows:
        current = box(ax, 6, y, 112, h, "\n".join(lines), kind)
        down(ax, previous, current, x=62)
        main.append(current)
        previous = current
    models, triage = main[3], main[6]
    box(
        ax,
        124,
        98,
        42,
        36,
        "Controls throughout\n• no relationship\n  component on both\n  sides of a split\n"
        "• preprocessing and\n  tuning in folds\n• hashes in run\n  manifests\n"
        "• write-once outputs",
        "note",
        align="left",
    )
    scores = box(
        ax, 124, 68, 50, 18, "Hallmark scores\nz-scored per fold\non training rows\nonly", "process"
    )
    arrow(ax, [(170, tops[3].y), (170, scores.y + scores.h)])
    arrow(ax, [scores.left, (models.x + models.w, scores.left[1])])
    secondary = box(
        ax,
        124,
        44,
        50,
        18,
        "Secondary analyses\n(descriptive): other\nscales, held-out tissue,\nsensitivity populations",
        "secondary",
    )
    arrow(ax, [(112, models.y), (112, 65), (149, 65), (149, secondary.y + secondary.h)])
    outputs = box(
        ax, 124, 8, 50, 14, "Figures and manuscript\nsaved tables only,\nprovenance sidecars",
        "process",
    )  # fmt: skip
    arrow(ax, [triage.right, outputs.left])
    return fig


# ------------------------------------------------------------------ fig_s04


def triage_decision(pathway: PathwayRules, cell_lines: CellLineRules) -> plt.Figure:
    """Triage decision rules, drawn from ``criteria_text`` and the frozen thresholds."""
    text = criteria_text(pathway, cell_lines)
    fig, ax = canvas(180, 192)
    legend(ax, 6, 185, ["process", "gate", "outcome", "note"])

    # a: gene sets (decision chain, x 10-72; tiers x 80-98) --------------
    panel_letter(ax, 4, 180, "a", "Gene sets (Hallmark)")
    start = box(ax, 10, 163, 62, 11, text["pathway_input"], "process")
    q0 = box(ax, 10, 146, 62, 11, text["pathway_rankable"], "gate")
    gate = box(ax, 10, 122, 62, 18, text["pathway_gate"], "gate")
    q_a = box(ax, 10, 98, 62, 18, text["pathway_A"], "gate")
    q_b = box(ax, 10, 78, 62, 14, text["pathway_B"], "gate")
    q_c = box(ax, 10, 58, 62, 14, text["pathway_C"], "gate")
    none = box(ax, 10, 44, 62, 8, "not prioritised", "outcome")
    tiers = {
        "nr": box(ax, 80, 146, 18, 11, "not\nrankable", "outcome"),
        "A": box(ax, 80, 103, 18, 8, "Tier A", "outcome"),
        "B": box(ax, 80, 81, 18, 8, "Tier B", "outcome"),
        "C": box(ax, 80, 61, 18, 8, "Tier C", "outcome"),
    }
    box(ax, 10, 10, 86, 21, text["pathway_note"], "note", align="left")
    down(ax, start, q0)
    for upper, lower, word in ((q0, gate, "yes"), (gate, q_a, "yes"), (q_a, q_b, "no"),
                               (q_b, q_c, "no"), (q_c, none, "no")):  # fmt: skip
        down(ax, upper, lower, label=word, label_at=(upper.bottom[0] + 1.5, upper.y - 3))
    for question, key, word in ((q0, "nr", "no"), (q_a, "A", "yes"), (q_b, "B", "yes"),
                                (q_c, "C", "yes")):  # fmt: skip
        target = tiers[key]
        y = target.y + target.h / 2
        arrow(ax, [(question.x + question.w, y), (target.x, y)], word, label_at=(73.2, y + 2.2))
    arrow(ax, [gate.left, (5, gate.left[1]), (5, q_c.left[1]), q_c.left])
    ax.text(3, 95, "no: capped at C", fontsize=TEXT_PT, rotation=90, ha="center", va="center")

    # b: measured cell lines (x 104-176) ---------------------------------
    panel_letter(ax, 102, 180, "b", "Measured cell lines")
    steps = [
        (153, 21, "process", text["lines_input"]),
        (136, 11, "gate", text["lines_rankable"]),
        (119, 11, "gate", text["lines_A"]),
        (102, 11, "gate", text["lines_B"]),
        (82, 14, "gate", text["lines_C"]),
        (68, 8, "outcome", text["lines_none"]),
        (37, 25, "outcome", text["lines_review"]),
        (14, 17, "outcome", text["lines_replication"]),
    ]
    previous = None
    for y, h, kind, label in steps:
        current = box(ax, 104, y, 72, h, label, kind)
        if previous is not None:
            down(ax, previous, current)
        previous = current
    return fig


# ------------------------------------------------------------------ fig_s05


def triage_evidence() -> plt.Figure:
    """Evidence behind each ranking: model-derived, independent and not assessable."""
    fig, ax = canvas(180, 150)
    legend(ax, 6, 143, ["source", "gate", "outcome", "secondary", "deferred"])
    panel_letter(ax, 4, 137, "a", "Gene sets")
    panel_letter(ax, 94, 137, "b", "Measured cell lines")
    evidence = {
        6: [
            "Permutation importance per fit\n→ share of fits with importance > 0",
            "M2 coefficient sign per fit\n→ sign consistency; share of zero fits",
            "Null comparisons (permuted outcome,\nrandom gene sets) → empirical p, BH",
            "Gene-set score correlation (features\nonly) → shared-importance caveat",
        ],
        96: [
            "Out-of-fold errors, M1 and M2\n→ cohort percentiles",
            "Spread of predictions across CV repeats\n(split variability, not an interval)",
            "Model disagreement |M2 − M1|\n→ cohort percentile",
            "QC flags: stranded RNA, related lines,\nflag on a relative, small tissue group",
        ],
    }
    stacks = {
        x: [box(ax, x, 117 - i * 14, 80, 11, t, "source") for i, t in enumerate(texts)]
        for x, texts in evidence.items()
    }
    verdict = box(
        ax, 6, 55, 80, 11, "Primary verdict (M2 vs M1)\nno gain shown → capped at C", "gate"
    )
    tier_a = box(
        ax, 6, 35, 80, 13, "Rule-based tier (fig_s04)\nA · B · C · not prioritised · not rankable",
        "outcome",
    )  # fmt: skip
    down(ax, stacks[6][-1], verdict)
    down(ax, verdict, tier_a)
    literature = box(
        ax, 6, 6, 38, 17, "Independent\nradiobiological\nliterature (cited)", "secondary"
    )
    box(ax, 48, 6, 38, 17, "Tissue\nreproducibility:\nnot assessed", "deferred")
    arrow(
        ax,
        [literature.top, (literature.top[0], tier_a.y)],
        "shown beside, never re-ranks",
        dashed=True,
        label_at=(27, 28.5),
    )
    tier_b = box(
        ax, 96, 47, 80, 16, "Discrepancy tier + review type\n'technical review first' or\n"
        "'unexplained discrepancy'", "outcome",
    )  # fmt: skip
    priority = box(
        ax, 96, 30, 80, 11, "Replication priority (measured lines)\nidentity flag → not rankable",
        "secondary",
    )  # fmt: skip
    box(
        ax, 96, 6, 80, 13, "Per-line assay variability:\nnot assessable (one median per line)",
        "deferred",
    )  # fmt: skip
    down(ax, stacks[96][-1], tier_b)
    down(ax, tier_b, priority)
    return fig


# ------------------------------------------------------------------ fig_s06


def validation_pathway() -> plt.Figure:
    """Proposed experimental validation pathway (conceptual; future work)."""
    fig, ax = canvas(180, 135)
    legend(ax, 6, 128, ["secondary", "process", "gate", "deferred"])
    panel_letter(ax, 4, 122, "a", "Measured CLARIFi lines")
    panel_letter(ax, 94, 122, "b", "New, unassayed DepMap lines")
    r1 = box(
        ax, 6, 99, 80, 16, "Replication priorities (tiers A–C)\nfrom triage; not independent\n"
        "validation samples", "secondary",
    )  # fmt: skip
    r2 = box(
        ax, 6, 75, 80, 18, "Re-measure selected lines: does a new\nclonogenic SF2 agree with the\n"
        "literature median? (expect some\nregression to the mean)", "process",
    )  # fmt: skip
    n1 = box(
        ax, 96, 104, 80, 11, "Identity QC of non-CLARIFi lines;\nexclude relatives of measured lines",
        "deferred",
    )  # fmt: skip
    n2 = box(
        ax, 96, 87, 80, 11, "Refit M1 and M2 on all eligible lines;\npredict candidates "
        "(investigator-run)", "deferred",
    )  # fmt: skip
    n3 = box(
        ax, 96, 70, 80, 11, "Panel-selection rule in a protocol\namendment before predictions "
        "are viewed", "gate",
    )  # fmt: skip
    down(ax, r1, r2)
    down(ax, n1, n2, dashed=True)
    down(ax, n2, n3, dashed=True)
    assay = box(
        ax, 6, 42, 170, 14, "Clonogenic survival assay, SF2 at 2 Gy\nauthenticated (STR), "
        "mycoplasma-tested lines; experimenters blinded to predictions\n"
        "independent experiments reported as such", "process",
    )  # fmt: skip
    arrow(ax, [r2.bottom, (r2.bottom[0], assay.y + assay.h)])
    arrow(ax, [n3.bottom, (n3.bottom[0], assay.y + assay.h)], dashed=True)
    report = box(
        ax, 6, 14, 170, 14, "Prespecified comparison with sealed predictions (M2 vs M1)\n"
        "reported as a designed validation panel, not an unbiased external cohort\n"
        "replication results kept separate from prospective results", "gate",
    )  # fmt: skip
    down(ax, assay, report)
    return fig


DIAGRAMS = {
    "study_workflow": study_workflow,
    "triage_decision": triage_decision,
    "triage_evidence": triage_evidence,
    "validation_pathway": validation_pathway,
}
