"""End-to-end test of run -> resume -> evaluate -> figures on SYNTHETIC files.

SYNTHETIC SOFTWARE-TEST DATA ONLY: a fake QC folder, expression matrix, GMT file and
outcome table are written to pytest's tmp_path. The tiny models fitted here produce no
scientific result. Marked ``model_fit``: run by the investigator, never by Claude Code.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from radiosensitivity_ml.config import experiment_from_mapping
from radiosensitivity_ml.evaluation.report import EvaluationError, evaluate_run
from radiosensitivity_ml.explainability.report import ExplainabilityError, explain_run
from radiosensitivity_ml.models import checkpoints as ck
from radiosensitivity_ml.models.run import run_experiment
from radiosensitivity_ml.visualization import figures as fg
from radiosensitivity_ml.visualization.render import render_all

pytestmark = pytest.mark.model_fit


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_synthetic_inputs(root: Path) -> dict[str, object]:
    """Fake inputs with the real file layouts (all values invented)."""
    rng = np.random.default_rng(0)
    qc = root / "qc"
    qc.mkdir()
    rows, row = [], 2
    for c in range(24):
        lineage = ["L_A", "L_B", "L_C"][c % 3]
        for _ in range(2 if c == 0 else 1):
            rows.append(
                {
                    "row_number": row, "depmap_id": f"ACH-9{row:05d}", "component_id": f"G:{c:03d}",
                    "oncotree_lineage": lineage, "oncotree_primary_disease": f"{lineage}_d",
                    "eligible_primary": "True", "eligible_retaining_problematic": "True",
                }
            )  # fmt: skip
            row += 1
    eligibility = pd.DataFrame(rows)
    eligibility.to_csv(qc / "eligibility.csv", index=False)
    genes = [f"GENE{i} ({1000 + i})" for i in range(60)]
    expression = pd.DataFrame(
        rng.normal(5, 1, size=(len(rows), 60)), index=eligibility["depmap_id"], columns=genes
    )
    expression.to_csv(root / "SYNTHETIC_expression.csv")
    names = ["HALLMARK_E2F_TARGETS", "HALLMARK_G2M_CHECKPOINT"] + [
        f"HALLMARK_S{i}" for i in range(48)
    ]
    gmt = root / "SYNTHETIC.gmt"
    gmt.write_text(
        "\n".join(
            "\t".join([n, "synthetic", *[f"GENE{j}" for j in rng.choice(60, 6, replace=False)]])
            for n in names
        )
    )
    clarifi = root / "SYNTHETIC_CLARIFi.csv"
    pd.DataFrame(
        {
            "CCLE Name": [f"X{r}" for r in eligibility["row_number"]],
            "Depmap ID": eligibility["depmap_id"],
            "mSF2": rng.uniform(0.1, 0.9, len(rows)).round(2),
        }
    ).to_csv(clarifi, index=False)
    manifest = root / "SYNTHETIC_manifest.yaml"
    manifest.write_text(f"files:\n  - path: {clarifi}\n    sha256: {sha(clarifi)}\n")
    return {
        "qc_dir": str(qc),
        "qc_sha256": {"eligibility.csv": sha(qc / "eligibility.csv")},
        "clarifi": str(clarifi),
        "clarifi_manifest": str(manifest),
        "expression": str(root / "SYNTHETIC_expression.csv"),
        "gene_sets": str(gmt),
        "gene_sets_sha256": sha(gmt),
    }


def write_synthetic_decision(root: Path, repeats: int = 2) -> Path:
    """SYNTHETIC stand-in for a simulation decision.json (not a simulation result)."""
    path = root / f"SYNTHETIC_decision_r{repeats}.json"
    path.write_text(json.dumps({"adopted_method": "nadeau_bengio", "repeats": repeats}))
    return path


def config_for(
    root: Path, inputs: dict[str, object], grid_alpha: float = 10.0, decision_repeats: int = 2
):
    decision = write_synthetic_decision(root, decision_repeats)
    return experiment_from_mapping(
        {
            "schema_version": 1,
            "run_id": "SYNTHETIC_run",
            "inputs": inputs,
            "population": "primary",
            "population_options": {"min_components_per_tissue": 3},
            "scales": ["raw"],
            "models": ["M0", "M1", "M2"],
            "grids": {
                "M0": {},
                "M1": {"alpha": [grid_alpha, 1.0]},
                "M2": {"alpha": [0.1], "baseline__alpha": [1.0], "l1_ratio": [0.5]},
            },
            "validation": {"k_outer": 3, "k_inner": 2, "repeats": 2},
            "seeds": {"base_seed": 1},
            "fit": {"component_weighting": True},
            "predictions": {"clip_raw_to_unit_interval": True},
            "inference": {
                "method": "nadeau_bengio",
                "alpha_one_sided": 0.05,
                "bh_q": 0.05,
                "decision_file": str(decision),
                "decision_sha256": sha(decision),
            },
            "output_dir": str(root / "models"),
        }
    )


def test_run_resume_evaluate_and_figures(tmp_path: Path) -> None:
    inputs = write_synthetic_inputs(tmp_path)
    config = config_for(tmp_path, inputs)
    log: list[str] = []
    first = run_experiment(config, config.population_options, resume=False, log=log.append)
    n_tasks = 3 * 3 * 2  # models x folds x repeats
    assert first == {"reused": 0, "computed": n_tasks, "rejected": 0, "failed": 0}

    with pytest.raises(ck.CheckpointError):  # never reuse a folder without --resume
        run_experiment(config, config.population_options, resume=False, log=log.append)

    assert (
        run_experiment(config, config.population_options, resume=True, log=log.append)["reused"]
        == n_tasks
    )

    store = ck.RunStore(config.output_dir / config.run_id)
    victim = min(store.tasks_dir.iterdir())
    (victim / "predictions.parquet").write_bytes(b"corrupted")
    counts = run_experiment(config, config.population_options, resume=True, log=log.append)
    assert counts["rejected"] == 1 and counts["computed"] == 1 and counts["reused"] == n_tasks - 1

    changed = config_for(tmp_path, inputs, grid_alpha=100.0)
    with pytest.raises(ck.CheckpointError, match="incompatible"):
        run_experiment(changed, changed.population_options, resume=True, log=log.append)

    status = json.loads((store.root / "run_status.json").read_text())
    assert status["status"] == "complete"
    assert set(json.loads((store.root / "scale_rows.json").read_text())) == {"raw"}

    with pytest.raises(EvaluationError):  # decision file says R = 3, config says 2
        evaluate_run(config_for(tmp_path, inputs, decision_repeats=3), tables_root=tmp_path / "t2")
    with pytest.raises(ExplainabilityError):  # explainability needs an evaluated run
        explain_run(config, n_repeats=1, tables_root=tmp_path / "tables")

    out = evaluate_run(config, tables_root=tmp_path / "tables")
    comparisons = pd.read_csv(out / "comparisons.csv")
    primary = comparisons[(comparisons["model"] == "M2") & (comparisons["comparator"] == "M1")]
    assert len(primary) == 1 and primary["n_components"].iloc[0] == 24
    assert primary["verdict"].iloc[0] in {"gain shown (one-sided LB > 0)", "no gain shown"}
    others = comparisons[comparisons["model"] != "M2"]
    assert all(v.startswith("descriptive") for v in others["verdict"])
    assert {"nadeau_bengio_lower", "naive_component_t_lower", "component_bootstrap_lower"} <= set(
        comparisons.columns
    )

    figures_config = {
        "tables_dir": str(out),
        "output_dir": str(tmp_path / "figures"),
        "version": 1,
        "dpi": 72,
        "formats": ["png", "pdf", "svg"],
        "figures": [
            {
                "id": "fig_t1",
                "slug": "ovp",
                "kind": "observed_vs_predicted",
                "inputs": {"oof": "oof_predictions.csv"},
            },
            {
                "id": "fig_t2",
                "slug": "forest",
                "kind": "effect_forest",
                "inputs": {"comparisons": "comparisons.csv"},
                "options": {"method": "nadeau_bengio"},
            },
            {
                "id": "fig_t3",
                "slug": "tissue",
                "kind": "tissue_errors",
                "inputs": {"errors": "tissue_errors.csv"},
            },
        ],
    }
    written = render_all(
        figures_config, tmp_path / "figures.yaml", Path(__file__).resolve().parents[1]
    )
    assert len([p for p in written if p.suffix == ".json"]) == 3
    with pytest.raises(FileExistsError):  # write-once figures
        render_all(figures_config, tmp_path / "figures.yaml", Path(__file__).resolve().parents[1])


def test_figure_inputs_are_validated(tmp_path: Path) -> None:
    with pytest.raises(fg.FigureInputError):
        fg.effect_forest(pd.DataFrame({"comparison": ["x"]}), "nadeau_bengio")
    with pytest.raises(fg.FigureInputError):
        fg.observed_vs_predicted(pd.DataFrame())


def test_style_uses_at_least_8_point_fonts() -> None:
    import matplotlib.pyplot as plt

    fg.style()
    for key in (
        "font.size",
        "axes.labelsize",
        "legend.fontsize",
        "xtick.labelsize",
        "ytick.labelsize",
    ):
        assert float(plt.rcParams[key]) >= 8
    assert plt.rcParams["pdf.fonttype"] == 42
