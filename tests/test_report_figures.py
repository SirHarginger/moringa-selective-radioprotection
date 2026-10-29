"""Presentation and provenance tests for the version-3 report figures (Seaborn).

SYNTHETIC DATA ONLY: every table below is invented in memory to exercise plotting code
paths; nothing is a scientific result and no model is fitted or queried (no ``model_fit``
marker). Figures are drawn into pytest's temporary folder, never into figures/.

The central contract these tests defend: a report figure carries no title, figure number,
footnote or explanatory note. Captions live in configs/figures_report.yaml and in the
report, so that figure and caption can never drift apart.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd
import pytest
import yaml

matplotlib.use("Agg")
import matplotlib.pyplot as plt

pytest.importorskip("seaborn", reason="seaborn is required for the version-3 report figures")

from radiosensitivity_ml.visualization import diagrams as dg
from radiosensitivity_ml.visualization import report_figures as rf
from radiosensitivity_ml.visualization import report_render as rr
from radiosensitivity_ml.visualization import style as st
from radiosensitivity_ml.visualization.figures import FigureInputError

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "figures_report.yaml"
MODELS = ["M0", "M1", "M1P", "M2", "M2P"]
# Words that must never appear in figure text: they belong in the caption.
NOTE_WORDS = ("descriptive only", "superiority", "not formally assessed", "negative control",
              "hypothesis-generating", "figure", "fig.", "caption", "note:", "source:")  # fmt: skip


# ----------------------------------------------------------------- synthetic fixtures


def synthetic_oof(n: int = 40) -> pd.DataFrame:
    """SYNTHETIC out-of-fold predictions: 2 tissues above threshold, 1 small one."""
    rng = np.random.default_rng(0)
    rows = []
    tissues = ["Lung"] * 15 + ["Breast"] * 15 + ["Liver"] * (n - 30)
    for i, lineage in enumerate(tissues):
        y = float(np.clip(0.45 + 0.2 * rng.standard_normal(), 0.02, 0.98))
        for model in MODELS:
            rows.append(
                {
                    "model_id": model,
                    "row_number": i,
                    "depmap_id": f"ACH-{i:06d}",
                    "component_id": f"G:ACH:ACH-{i:06d}",
                    "lineage": lineage,
                    "y_true": y,
                    "y_pred": 0.5 + 0.05 * rng.standard_normal(),
                    "y_pred_sd": abs(0.01 * rng.standard_normal()),
                    "y_pred_min": 0.45,
                    "y_pred_max": 0.55,
                    "n_repeats": 10,
                }
            )
    return pd.DataFrame(rows)


def synthetic_metrics() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "model_id": MODELS,
            "scale": ["raw"] * 5,
            "mae": [0.1336, 0.1342, 0.1343, 0.1304, 0.1304],
            "rmse": [0.1708, 0.1715, 0.1713, 0.1691, 0.1688],
            "r2_oos": [-0.0095, -0.0183, -0.0160, 0.0093, 0.0128],
        }
    )


def synthetic_comparisons() -> tuple[pd.DataFrame, pd.DataFrame]:
    comparisons = pd.DataFrame(
        {
            "comparison": [rf.PRIMARY, rf.SENSITIVITY],
            "model": ["M2", "M2P"],
            "comparator": ["M1", "M1P"],
            "scale": ["raw", "raw"],
            "delta_mae": [0.00383, 0.00387],
        }
    )
    rng = np.random.default_rng(1)
    per_repeat = pd.DataFrame(
        {
            "repeat": list(range(10)) * 2,
            "delta_mae": list(rng.normal(0.004, 0.003, 10)) + list(rng.normal(0.004, 0.002, 10)),
            "comparison": [rf.PRIMARY] * 10 + [rf.SENSITIVITY] * 10,
            "scale": ["raw"] * 20,
        }
    )
    return comparisons, per_repeat


def synthetic_tissue_errors() -> pd.DataFrame:
    rows = []
    for lineage, n in (("Lung", 15), ("Breast", 15), ("Liver", 3)):
        for i, model in enumerate(MODELS):
            rows.append({"model_id": model, "lineage": lineage,
                         "mae": 0.13 + 0.002 * i, "n_components": n})  # fmt: skip
    return pd.DataFrame(rows)


def synthetic_table_s2() -> pd.DataFrame:
    sets = [f"HALLMARK_SET_{i}" for i in range(20)]
    return pd.DataFrame(
        {
            "rank": range(1, 21),
            "gene_set": sets,
            "mean_importance": np.linspace(0.003, -0.0001, 20),
            "sd_importance": np.linspace(0.003, 0.0001, 20),
            "positive_importance_share": np.linspace(0.9, 0.05, 20),
            "share_zero_coefficient": np.linspace(0.08, 0.98, 20),
            "sign_consistency": np.linspace(0.92, 0.02, 20),
            "tier": ["C"] * 7 + ["not_prioritised"] * 13,
            "shared_signal_caveat": ["score correlated with HALLMARK_SET_1: shared"] + [""] * 19,
        }
    )


def synthetic_importance_per_task() -> pd.DataFrame:
    rng = np.random.default_rng(2)
    columns = [f"real|r{r}|f{f}" for r in range(10) for f in range(5)]
    data = rng.normal(0.0005, 0.002, size=(20, len(columns)))
    return pd.DataFrame(data, index=[f"HALLMARK_SET_{i}" for i in range(20)], columns=columns)


def synthetic_correlation() -> pd.DataFrame:
    sets = [f"HALLMARK_SET_{i}" for i in range(20)]
    rng = np.random.default_rng(3)
    matrix = rng.uniform(-0.5, 0.5, size=(20, 20))
    matrix = (matrix + matrix.T) / 2
    np.fill_diagonal(matrix, 1.0)
    return pd.DataFrame(matrix, index=sets, columns=sets)


def synthetic_table_s3() -> pd.DataFrame:
    rng = np.random.default_rng(4)
    n = 30
    observed = np.clip(rng.uniform(0.05, 0.95, n), 0, 1)
    flags = [""] * n
    flags[0] = "small tissue group"
    flags[1] = "stranded RNA profile; M1 and M2 disagree strongly"
    flags[2] = "prediction unstable across CV repeats"
    return pd.DataFrame(
        {
            "rank": range(1, n + 1),
            "depmap_id": [f"ACH-{i:06d}" for i in range(n)],
            "cell_line_name": [f"LINE-{i}" for i in range(n)],
            "lineage": ["Lung"] * n,
            "observed_msf2": observed,
            "pred_m1": 0.55,
            "pred_m2": 0.56,
            "abs_error_m1": abs(observed - 0.55),
            "abs_error_m2": abs(observed - 0.56),
            "tier": ["A"] * 4 + ["B"] * 4 + ["C"] * 6 + ["not_prioritised"] * (n - 14),
            "triage_category": ["technical review first"] * n,
            "technical_flags": flags,
        }
    )


def synthetic_ranking() -> pd.DataFrame:
    return pd.DataFrame(
        {
            # nullable integer, as compounds/ranking.py produces: NA for unranked rows
            "rank": pd.array([1, 2, 3, pd.NA], dtype="Int64"),
            "compound_id": ["a", "b", "c", "d"],
            "preferred_name": ["Alpha", "Beta", "Gamma", "Delta"],
            "extraction_category": [
                "dcm_documented",
                "seed_or_leaf_other_solvent",
                "seed_or_leaf_other_solvent",
                "indirect_or_unconfirmed",
            ],
            "d1_moringa_identity": [2, 1, 2, 0],
            "d2_radiation_biology": [3, 3, 0, 3],
            "d3_independent_sources": [2, 2, 2, 2],
            "d4_feasibility": [1, 1, 0, 1],
            "total_score": [8, 7, 4, 6],
            "tier": ["A", "A", "C", "not_assessable"],
        }
    )


def synthetic_compound_evidence() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "evidence_id": ["E1", "E2", "E3", "E4"],
            "compound_id": ["a", "a", "b", "c"],
            "process_category": ["dna_damage", "apoptosis", "dna_damage", "cell_cycle"],
            "evidence_level": ["L3_radiation", "L2_process", "L3_radiation", "L2_process"],
            "research_group": ["G1", "G2", "G3", "G4"],
            "counts_for_score": [True, True, True, True],
        }
    )


def synthetic_overlap() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "compound_id": ["a", "b"],
            "gene_set": ["HALLMARK_P53_PATHWAY", "HALLMARK_P53_PATHWAY"],
            "n_overlapping_genes": [2, 1],
        }
    )


CONTEXT_LINES = {"ACH-000000": "MCF-7", "ACH-000001": "DU145"}
Builders = dict[str, Callable[[], plt.Figure]]


def figure_builders() -> dict[str, Callable[[], plt.Figure]]:
    """One callable per report figure, so a test can build them one at a time.

    Builders rather than built figures: holding all eleven open for the lifetime of a
    module-scoped fixture accumulates figures and trips Matplotlib's "more than 20
    figures" warning. ``iter_figures`` builds each one, hands it to the test and closes it
    before building the next, so at most one is open. The figures themselves are
    unchanged.
    """
    return {
        "project_workflow": dg.project_workflow,
        "dataset_overview": lambda: rf.dataset_overview(
            synthetic_oof(), context_lines=CONTEXT_LINES
        ),
        "model_performance": lambda: rf.model_performance(
            synthetic_metrics(), synthetic_comparisons()[1], synthetic_comparisons()[0]
        ),
        "prediction_behaviour": lambda: rf.prediction_behaviour(synthetic_oof()),
        "prediction_variability": lambda: rf.prediction_variability(synthetic_oof()),
        "tissue_performance": lambda: rf.tissue_performance(synthetic_tissue_errors()),
        "gene_set_importance": lambda: rf.gene_set_importance(
            synthetic_table_s2(), synthetic_importance_per_task()
        ),
        "gene_set_correlation": lambda: rf.gene_set_correlation(
            synthetic_table_s2(), synthetic_correlation()
        ),
        "cell_line_discrepancies": lambda: rf.cell_line_discrepancies(
            synthetic_table_s3(), context_lines=CONTEXT_LINES
        ),
        "compound_scorecard": lambda: rf.compound_scorecard(synthetic_ranking()),
        "compound_evidence_map": lambda: rf.compound_evidence_map(
            synthetic_compound_evidence(), synthetic_ranking(), synthetic_overlap()
        ),
    }


def iter_figures(
    builders: dict[str, Callable[[], plt.Figure]], only: Sequence[str] | None = None
) -> Iterator[tuple[str, plt.Figure]]:
    """Yield (name, figure) for each requested figure, closing it before the next."""
    for name, build in builders.items():
        if only is not None and name not in only:
            continue
        figure = build()
        try:
            yield name, figure
        finally:
            plt.close(figure)


@pytest.fixture(autouse=True)
def _close_leaked_figures() -> Iterator[None]:
    """Close any figure a test leaves open, so none accumulates between tests.

    A builder that validates its inputs late creates the figure and then raises, so the
    tests that assert those errors would otherwise leak one figure each. Only figure
    numbers that appear during the test are closed, so a figure created during fixture
    setup is never pulled out from under the test using it.
    """
    before = set(plt.get_fignums())
    yield
    for number in set(plt.get_fignums()) - before:
        plt.close(number)


@pytest.fixture(scope="module")
def builders() -> dict[str, Callable[[], plt.Figure]]:
    """Builders, not built figures: see ``figure_builders``. Nothing is open at rest."""
    return figure_builders()


def all_text(figure: plt.Figure) -> list[str]:
    """Every non-empty text string drawn anywhere on a figure, including tick labels."""
    figure.canvas.draw()
    texts = [t.get_text() for t in figure.texts]
    for ax in figure.axes:
        texts.append(ax.get_title())
        texts.append(ax.get_xlabel())
        texts.append(ax.get_ylabel())
        texts += [t.get_text() for t in ax.texts]
        texts += [t.get_text() for t in ax.get_xticklabels()]
        texts += [t.get_text() for t in ax.get_yticklabels()]
        legend = ax.get_legend()
        if legend is not None:
            texts.append(legend.get_title().get_text())
            texts += [t.get_text() for t in legend.get_texts()]
    return [t for t in texts if t and t.strip()]


# -------------------------------------------------- the no-title, no-footnote contract


def test_no_figure_carries_an_axes_title(builders: Builders) -> None:
    for name, figure in iter_figures(builders):
        for ax in figure.axes:
            assert not ax.get_title().strip(), f"{name}: axes title {ax.get_title()!r}"
        assert not figure._suptitle or not figure._suptitle.get_text().strip(), name


def test_no_figure_carries_a_footnote_or_explanatory_note(builders: Builders) -> None:
    for name, figure in iter_figures(builders):
        for text in all_text(figure):
            lowered = text.lower()
            for word in NOTE_WORDS:
                assert word not in lowered, f"{name}: note-like text {text!r}"


def test_free_text_on_a_figure_stays_short(builders: Builders) -> None:
    """Long sentences belong in the caption; labels may be short."""
    for name, figure in iter_figures(builders):
        for text in all_text(figure):
            for line in text.splitlines():
                assert len(line) <= rf.MAX_TEXT_CHARS, f"{name}: {line!r} is too long"


def test_panel_letters_are_lowercase_and_present_on_multi_panel_figures(
    builders: Builders,
) -> None:
    multi = ["dataset_overview", "model_performance", "prediction_behaviour",
             "tissue_performance", "gene_set_importance", "cell_line_discrepancies",
             "compound_scorecard", "compound_evidence_map"]  # fmt: skip
    seen = []
    for name, figure in iter_figures(builders, only=multi):
        seen.append(name)
        letters = [t for t in all_text(figure) if t in tuple("abcdef")]
        assert letters, f"{name}: no panel letters"
        assert letters == sorted(letters), f"{name}: panel letters out of order"
    assert sorted(seen) == sorted(multi), "a multi-panel figure was not checked"


def test_all_text_is_at_least_eight_point(builders: Builders) -> None:
    for name, figure in iter_figures(builders):
        figure.canvas.draw()
        for ax in figure.axes:
            for text in [*ax.texts, *ax.get_xticklabels(), *ax.get_yticklabels()]:
                if text.get_text().strip():
                    assert text.get_fontsize() >= 8, f"{name}: {text.get_text()!r}"


def test_figures_are_drawn_at_the_a4_text_width(builders: Builders) -> None:
    for name, figure in iter_figures(builders):
        width = figure.get_size_inches()[0]
        assert width == pytest.approx(st.REPORT_WIDTH, abs=0.01), name
        assert figure.get_size_inches()[1] <= 240 * st.MM + 0.01, f"{name}: taller than A4"


def test_no_figures_stay_open_after_the_contract_checks(builders: Builders) -> None:
    """Lifecycle guard: iter_figures must leave nothing open."""
    before = set(plt.get_fignums())
    for _name, figure in iter_figures(builders):
        assert figure.number in set(plt.get_fignums())
    assert set(plt.get_fignums()) == before, "figures accumulated across the iteration"


# ----------------------------------------------------- statistical presentation rules


def test_model_colours_are_identical_in_every_figure() -> None:
    assert st.model_palette(MODELS) == {m: st.colour(m) for m in MODELS}
    assert len(set(st.model_palette(MODELS).values())) == len(MODELS)


def test_predictions_are_shown_once_per_component() -> None:
    """Ten repeats of one line must never appear as ten independent points."""
    oof = synthetic_oof()
    points = rf.component_points(oof, ("M1", "M2"))
    assert len(points) == 2 * oof["component_id"].nunique()
    assert (
        points.groupby("model_id")["component_id"].nunique().eq(oof["component_id"].nunique()).all()
    )


def test_related_records_of_one_component_are_averaged() -> None:
    oof = synthetic_oof()
    oof.loc[oof["row_number"] == 1, "component_id"] = oof.loc[
        oof["row_number"] == 0, "component_id"
    ].iloc[0]
    points = rf.component_points(oof, ("M1",))
    assert len(points) == oof["component_id"].nunique()
    assert points["n_records"].max() == 2


def test_mae_bars_start_at_zero() -> None:
    comparisons, per_repeat = synthetic_comparisons()
    figure = rf.model_performance(synthetic_metrics(), per_repeat, comparisons)
    assert figure.axes[0].get_xlim()[0] == 0
    plt.close(figure)


def test_parity_panels_use_the_full_endpoint_range_and_equal_axes() -> None:
    figure = rf.prediction_behaviour(synthetic_oof())
    for ax in figure.axes[:2]:
        assert ax.get_xlim() == (0, 1) and ax.get_ylim() == (0, 1)
        assert ax.get_aspect() == 1
    plt.close(figure)


def test_delta_mae_axis_is_symmetric_about_zero() -> None:
    """A small improvement must not be exaggerated by a one-sided axis."""
    comparisons, per_repeat = synthetic_comparisons()
    figure = rf.model_performance(synthetic_metrics(), per_repeat, comparisons)
    low, high = figure.axes[2].get_xlim()
    assert low == pytest.approx(-high)
    plt.close(figure)


def test_no_figure_fits_a_trend_line() -> None:
    """Only the identity line is allowed on the parity panels."""
    figure = rf.prediction_behaviour(synthetic_oof())
    for ax in figure.axes[:2]:
        lines = [line for line in ax.lines if len(line.get_xdata()) > 1]
        assert len(lines) == 1
        assert list(lines[0].get_xdata()) == [0, 1]  # identity, not a fit
    plt.close(figure)


def test_gene_set_thresholds_come_from_the_arguments() -> None:
    figure = rf.gene_set_importance(
        synthetic_table_s2(), synthetic_importance_per_task(),
        exploratory_share=0.5, max_share_zero=0.5,
    )  # fmt: skip
    positions = [float(line.get_xdata()[0]) for line in figure.axes[1].lines
                 if len(set(line.get_xdata())) == 1]  # vertical lines only  # fmt: skip
    assert any(p == pytest.approx(0.5) for p in positions)
    plt.close(figure)


def test_correlation_heatmap_applies_no_clustering() -> None:
    """Row order must follow the triage rank, never a similarity dendrogram."""
    table = synthetic_table_s2()
    figure = rf.gene_set_correlation(table, synthetic_correlation())
    shown = [t.get_text() for t in figure.axes[0].get_yticklabels()]
    expected = [st.short_gene_set(g) for g in table.sort_values("rank")["gene_set"]]
    assert shown[: len(shown)] == expected[: len(shown)]
    plt.close(figure)


# ---------------------------------------------------------------- input validation


def test_figures_refuse_tables_missing_columns() -> None:
    with pytest.raises(FigureInputError):
        rf.dataset_overview(pd.DataFrame({"model_id": ["M1"]}))
    with pytest.raises(FigureInputError):
        rf.tissue_performance(pd.DataFrame({"model_id": ["M1"], "lineage": ["Lung"]}))
    with pytest.raises(FigureInputError):
        rf.compound_scorecard(pd.DataFrame({"rank": [1]}))


def test_a_missing_context_line_is_an_error_not_a_silent_omission() -> None:
    with pytest.raises(FigureInputError, match="context line"):
        rf.dataset_overview(synthetic_oof(), context_lines={"ACH-999999": "Nonexistent"})
    with pytest.raises(FigureInputError, match="context line"):
        rf.cell_line_discrepancies(
            synthetic_table_s3(), context_lines={"ACH-999999": "Nonexistent"}
        )


def test_tissue_figure_drops_tissues_below_the_threshold() -> None:
    figure = rf.tissue_performance(synthetic_tissue_errors(), min_components=10)
    shown = [t.get_text() for t in figure.axes[1].get_yticklabels()]
    assert any("Lung" in s for s in shown) and not any("Liver" in s for s in shown)
    plt.close(figure)


def test_unknown_extraction_category_is_refused() -> None:
    table = synthetic_ranking()
    table.loc[0, "extraction_category"] = "made_up"
    with pytest.raises(FigureInputError, match="unknown extraction categories"):
        rf.compound_scorecard(table)


def test_evidence_map_works_without_an_overlap_table() -> None:
    figure = rf.compound_evidence_map(
        synthetic_compound_evidence(), synthetic_ranking(), overlap=None
    )
    assert len(figure.axes) >= 1
    plt.close(figure)
    empty = rf.compound_evidence_map(
        synthetic_compound_evidence(), synthetic_ranking(), overlap=pd.DataFrame()
    )
    plt.close(empty)


# ------------------------------------------------------- output layout and provenance


def minimal_config(tmp_path: Path, tables: Path) -> dict:
    return {
        "output_root": "figures",
        "version": 3,
        "dpi": 72,
        "formats": ["png", "pdf"],
        "figures": [
            {
                "id": "fig_01", "report_label": "Figure 1", "slug": "project_workflow",
                "kind": "project_workflow", "data_provenance": "conceptual_diagram",
                "caption": "Synthetic test caption.",
            },
            {
                "id": "fig_05", "report_label": "Figure 5", "slug": "tissue_performance",
                "kind": "tissue_performance", "data_provenance": "empirical",
                "inputs": {"errors": str(tables / "tissue_errors.csv")},
                "options": {"min_components": 10},
                "caption": "Synthetic test caption.",
            },
        ],
    }  # fmt: skip


@pytest.fixture
def rendered(tmp_path: Path) -> tuple[Path, list[Path], dict]:
    tables = tmp_path / "tables"
    tables.mkdir()
    synthetic_tissue_errors().to_csv(tables / "tissue_errors.csv", index=False)
    config = minimal_config(tmp_path, tables)
    for entry in config["figures"]:  # paths are resolved against the repo root
        entry["inputs"] = {k: str(Path(v).resolve()) for k, v in entry.get("inputs", {}).items()}
    written = rr.render_report(config, tmp_path / "figures_report.yaml", tmp_path)
    return tmp_path, written, config


def test_png_and_pdf_go_to_their_own_folders_with_one_basename(
    rendered: tuple[Path, list[Path], dict],
) -> None:
    root, written, _ = rendered
    for stem in ("fig_01_project_workflow", "fig_05_tissue_performance"):
        png = root / "figures" / "png" / f"{stem}.png"
        pdf = root / "figures" / "pdf" / f"{stem}.pdf"
        meta = root / "figures" / "metadata" / f"{stem}.meta.json"
        assert png.is_file() and pdf.is_file() and meta.is_file()
        assert png.stat().st_size > 0 and pdf.stat().st_size > 0
    assert all(p.exists() for p in written)


def test_no_svg_is_ever_written(rendered: tuple[Path, list[Path], dict]) -> None:
    root, written, _ = rendered
    assert not list((root / "figures").rglob("*.svg"))
    assert not [p for p in written if p.suffix == ".svg"]


def test_svg_in_the_configured_formats_is_refused() -> None:
    with pytest.raises(FigureInputError, match="PNG and PDF only"):
        rr.check_formats(["png", "pdf", "svg"])
    assert rr.check_formats(["png", "pdf"]) == ("png", "pdf")


def test_metadata_records_inputs_captions_and_packages(
    rendered: tuple[Path, list[Path], dict],
) -> None:
    root, _, _config = rendered
    meta = json.loads(
        (root / "figures" / "metadata" / "fig_05_tissue_performance.meta.json").read_text()
    )
    assert meta["data_provenance"] == "empirical"
    assert meta["inputs_sha256"] and all(len(v) == 64 for v in meta["inputs_sha256"].values())
    assert meta["caption"] == "Synthetic test caption."
    assert meta["report_label"] == "Figure 5"
    assert meta["png_dpi"] == 72 and meta["formats"] == ["png", "pdf"]
    assert "seaborn" in meta["packages"]
    diagram = json.loads(
        (root / "figures" / "metadata" / "fig_01_project_workflow.meta.json").read_text()
    )
    assert diagram["data_provenance"] == "conceptual_diagram"
    assert diagram["inputs_sha256"] == {}


def test_git_provenance_is_recorded_or_explicitly_absent(tmp_path: Path) -> None:
    """Real runs record a commit; a non-repository records that it could not, never a fake."""
    outside = rr.git_state(tmp_path)
    assert outside["available"] is False
    assert outside["commit"] is None and outside["dirty"] is None
    assert "work tree" in str(outside["reason"]) or "git" in str(outside["reason"])
    inside = rr.git_state(ROOT)
    if inside["available"]:
        assert isinstance(inside["commit"], str) and len(inside["commit"]) == 40
        assert isinstance(inside["dirty"], bool)


def test_metadata_without_a_commit_says_so(rendered: tuple[Path, list[Path], dict]) -> None:
    """Figures rendered outside a repository must not claim provenance they lack."""
    root, _, _ = rendered
    meta = json.loads(
        (root / "figures" / "metadata" / "fig_05_tissue_performance.meta.json").read_text()
    )
    assert meta["git"]["available"] is False and meta["git"]["commit"] is None


def test_figure_index_lists_every_rendered_figure(
    rendered: tuple[Path, list[Path], dict],
) -> None:
    root, _, _ = rendered
    index = pd.read_csv(root / "figures" / "metadata" / "figure_index.csv")
    assert set(index["figure_id"]) == {"fig_01", "fig_05"}
    assert list(index.columns) == list(rr.INDEX_COLUMNS)
    for _, row in index.iterrows():
        assert (root / row["png"]).is_file() and (root / row["pdf"]).is_file()
        assert row["png"].startswith("figures/png/")
        assert row["pdf"].startswith("figures/pdf/")
        assert row["metadata"].startswith("figures/metadata/")


def test_rendering_is_write_once_unless_overwrite_is_given(tmp_path: Path) -> None:
    tables = tmp_path / "tables"
    tables.mkdir()
    synthetic_tissue_errors().to_csv(tables / "tissue_errors.csv", index=False)
    config = minimal_config(tmp_path, tables)
    for entry in config["figures"]:
        entry["inputs"] = {k: str(Path(v).resolve()) for k, v in entry.get("inputs", {}).items()}
    rr.render_report(config, tmp_path / "c.yaml", tmp_path)
    with pytest.raises(FileExistsError, match="--overwrite"):
        rr.render_report(config, tmp_path / "c.yaml", tmp_path)
    rr.render_report(config, tmp_path / "c.yaml", tmp_path, overwrite=True)  # reproduction


def test_inputs_under_tests_are_refused(tmp_path: Path) -> None:
    fake = ROOT / "tests" / "fixtures" / "synthetic.csv"
    with pytest.raises(FigureInputError, match="synthetic and never plotted"):
        rr.load_input(fake)


def test_plan_rejects_duplicate_ids_and_unknown_kinds(tmp_path: Path) -> None:
    config = minimal_config(tmp_path, tmp_path)
    config["figures"][1] = dict(config["figures"][0])
    with pytest.raises(FigureInputError, match="unique"):
        rr.plan(config, tmp_path)
    config = minimal_config(tmp_path, tmp_path)
    config["figures"][0]["kind"] = "not_a_figure"
    with pytest.raises(FigureInputError, match="unknown figure kind"):
        rr.plan(config, tmp_path)


def test_plan_requires_consistent_provenance(tmp_path: Path) -> None:
    config = minimal_config(tmp_path, tmp_path)
    config["figures"][0]["inputs"] = {"errors": "x.csv"}  # a diagram reads no data
    with pytest.raises(FigureInputError, match="reads no data"):
        rr.plan(config, tmp_path)
    config = minimal_config(tmp_path, tmp_path)
    config["figures"][1]["inputs"] = {}
    with pytest.raises(FigureInputError, match="needs input tables"):
        rr.plan(config, tmp_path)
    config = minimal_config(tmp_path, tmp_path)
    config["figures"][0]["data_provenance"] = "guesswork"
    with pytest.raises(FigureInputError, match="data_provenance"):
        rr.plan(config, tmp_path)


# ------------------------------------------------- the real config must stay consistent


@pytest.mark.skipif(not CONFIG.is_file(), reason="report figure config not present")
def test_the_report_config_is_internally_consistent() -> None:
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    assert config["formats"] == ["png", "pdf"], "SVG must not be configured"
    assert config["dpi"] >= 600
    assert config["output_root"] == "figures"
    ids = [e["id"] for e in config["figures"]]
    assert len(set(ids)) == len(ids)
    for entry in config["figures"]:
        assert entry["kind"] in rr.rf.FIGURES or entry["kind"] in rr.dg.DIAGRAMS
        assert entry["data_provenance"] in rr.PROVENANCE
        assert entry.get("report_label"), f"{entry['id']} has no report label"
        caption = " ".join(str(entry.get("caption", "")).split())
        assert len(caption) > 120, f"{entry['id']}: caption too thin to stand alone"
        for name, path in dict(entry.get("inputs", {})).items():
            assert not str(path).startswith("/"), f"{entry['id']}: {name} is an absolute path"
            assert "tests" not in Path(str(path)).parts


@pytest.mark.skipif(not CONFIG.is_file(), reason="report figure config not present")
def test_every_configured_input_is_produced_by_a_documented_step() -> None:
    """Report figures may read only saved evaluation, triage or compound outputs."""
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    allowed = ("results/tables/", "results/triage/")
    for entry in config["figures"]:
        for path in dict(entry.get("inputs", {})).values():
            assert str(path).startswith(allowed), f"{entry['id']}: unexpected input {path}"
