"""Layout and consistency tests for the conceptual methods diagrams (no data, no models).

Each diagram is drawn in memory. The tests check that every label sits inside its box,
that no two texts overlap, that all text is inside the canvas and at least 8 pt, and
that the triage-rule diagram shows exactly the implemented rule text.
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path

import matplotlib.pyplot as plt
import pytest
import yaml

from radiosensitivity_ml.triage import rules as tr
from radiosensitivity_ml.triage.report import load_triage
from radiosensitivity_ml.visualization import diagrams as dg
from radiosensitivity_ml.visualization import figures as fg
from radiosensitivity_ml.visualization.render import render_diagrams

ROOT = Path(__file__).resolve().parents[1]
TRIAGE = load_triage(ROOT / "configs" / "triage.yaml")


def build(kind: str) -> plt.Figure:
    fg.style()
    if kind == "triage_decision":
        return dg.triage_decision(TRIAGE.pathway, TRIAGE.cell_lines)
    return dg.DIAGRAMS[kind]()


def contains(outer: object, inner: object) -> bool:
    """True if the ``inner`` display box lies entirely inside ``outer``."""
    return (
        outer.x0 <= inner.x0  # type: ignore[attr-defined]
        and inner.x1 <= outer.x1  # type: ignore[attr-defined]
        and outer.y0 <= inner.y0  # type: ignore[attr-defined]
        and inner.y1 <= outer.y1  # type: ignore[attr-defined]
    )


@pytest.mark.parametrize("kind", sorted(dg.DIAGRAMS))
def test_labels_fit_their_boxes_and_never_overlap(kind: str) -> None:
    fig = build(kind)
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    canvas_box = fig.bbox
    for patch, text in fig.diagram_boxes:
        inner = text.get_window_extent(renderer)
        assert contains(patch.get_window_extent(renderer), inner), f"{kind}: {text.get_text()!r}"
    texts = [t for t in fig.axes[0].texts if t.get_text().strip()]
    extents = [t.get_window_extent(renderer) for t in texts]
    for t, e in zip(texts, extents, strict=True):
        assert t.get_fontsize() >= 8
        assert contains(canvas_box, e), f"{kind}: {t.get_text()!r} off canvas"
    for (t1, e1), (t2, e2) in itertools.combinations(zip(texts, extents, strict=True), 2):
        assert not e1.overlaps(e2), f"{kind}: {t1.get_text()!r} overlaps {t2.get_text()!r}"
    plt.close(fig)


def test_triage_diagram_shows_exactly_the_implemented_rules() -> None:
    fig = build("triage_decision")
    shown = {t.get_text() for t in fig.axes[0].texts}
    for key, value in tr.criteria_text(TRIAGE.pathway, TRIAGE.cell_lines).items():
        assert value in shown, f"criteria_text[{key!r}] missing from the diagram"
    plt.close(fig)


def test_diagrams_render_with_conceptual_sidecars(tmp_path: Path) -> None:
    config = yaml.safe_load((ROOT / "configs" / "diagrams.yaml").read_text(encoding="utf-8"))
    config["output_dir"] = str(tmp_path / "generated")
    config["triage_config"] = str(ROOT / "configs" / "triage.yaml")
    config["dpi"] = 72
    written = render_diagrams(config, tmp_path / "diagrams.yaml", ROOT)
    sidecars = [p for p in written if p.suffix == ".json"]
    assert len(sidecars) == len(config["diagrams"])
    for path in sidecars:
        assert json.loads(path.read_text())["data_provenance"] == "conceptual_diagram"
    with pytest.raises(FileExistsError):  # write-once
        render_diagrams(config, tmp_path / "diagrams.yaml", ROOT)
