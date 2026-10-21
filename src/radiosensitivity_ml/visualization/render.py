"""Render every figure listed in configs/figures.yaml from saved tables, with sidecars.

Each entry names a figure ID (``fig_NN`` / ``fig_sNN``), a slug, a kind (plotting
function), its input tables (relative to the run's tables folder) and a draft caption.
Outputs go to ``figures/generated/<id>_<slug>_v<version>.{pdf,svg,png}`` with a
``.meta.json`` sidecar (script, git state, config hash, input hashes, package versions,
UTC time, ``data_provenance: empirical``). Inputs under ``tests/`` are refused.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path

import matplotlib
import pandas as pd

from radiosensitivity_ml.config import config_sha256
from radiosensitivity_ml.data.provenance import file_sha256
from radiosensitivity_ml.visualization import figures as fg

KINDS: dict[str, Callable[..., object]] = {
    "observed_vs_predicted": fg.observed_vs_predicted,
    "effect_forest": fg.effect_forest,
    "tissue_errors": fg.tissue_errors,
    "repeat_distribution": fg.repeat_distribution,
    "stability_vs_null": fg.stability_vs_null,
    "cross_assay": fg.cross_assay,
    "supplementary_case_lines": fg.supplementary_case_lines,
}
INDEX_COLUMN = {"gene_set_tests.csv": 0}


def git_state(root: Path) -> dict[str, object]:
    def git(*args: str) -> str:
        return subprocess.run(
            ["git", "-C", str(root), *args], capture_output=True, text=True, check=True
        ).stdout.strip()

    return {"commit": git("rev-parse", "HEAD"), "dirty": bool(git("status", "--porcelain"))}


def load_table(path: Path) -> pd.DataFrame:
    """Read an input table, refusing synthetic test locations."""
    if "tests" in path.resolve().parts:
        raise fg.FigureInputError(f"{path}: inputs under tests/ are synthetic and never plotted")
    if not path.is_file():
        raise fg.FigureInputError(f"{path} does not exist; run evaluate_models.py first")
    return pd.read_csv(path, index_col=INDEX_COLUMN.get(path.name))


def evaluation_record(tables_dir: Path) -> tuple[dict[str, object], str]:
    """The run's evaluation_record.json and its SHA-256 (figures need an evaluated run)."""
    path = tables_dir / "evaluation_record.json"
    if not path.is_file():
        raise fg.FigureInputError(f"{path} does not exist; run evaluate_models.py first")
    return json.loads(path.read_text(encoding="utf-8")), file_sha256(path)


def render_all(config: Mapping[str, object], config_path: Path, repo_root: Path) -> list[Path]:
    """Render all configured figures; returns the written paths (figures + sidecars).

    Every input table and every output path is checked before anything is written.
    """
    from radiosensitivity_ml.models.checkpoints import atomic_write_text

    fg.style()
    tables_dir = Path(str(config["tables_dir"]))
    out_dir = Path(str(config.get("output_dir", "figures/generated")))
    version = int(config["version"])  # type: ignore[arg-type]
    dpi = int(config["dpi"])  # type: ignore[arg-type]
    formats = tuple(config.get("formats", ("pdf", "svg", "png")))  # type: ignore[arg-type]
    record, record_sha = evaluation_record(tables_dir)
    plans = []
    for entry in config["figures"]:  # type: ignore[union-attr]
        if entry["kind"] not in KINDS:
            raise fg.FigureInputError(f"{entry['id']}: unknown kind {entry['kind']!r}")
        inputs = {name: tables_dir / rel for name, rel in entry["inputs"].items()}
        tables = {name: load_table(path) for name, path in inputs.items()}
        stem = f"{entry['id']}_{entry['slug']}_v{version}"
        targets = [out_dir / f"{stem}.{fmt}" for fmt in formats] + [out_dir / f"{stem}.meta.json"]
        existing = [str(p) for p in targets if p.exists()]
        if existing:
            raise FileExistsError(f"{existing} exist; figures are write-once (bump the version)")
        # building the figure runs each plot's column checks before any file is written
        figure = KINDS[entry["kind"]](**tables, **entry.get("options", {}))
        plans.append((entry, inputs, figure, stem))
    git = git_state(repo_root)
    written: list[Path] = []
    for entry, inputs, figure, stem in plans:
        paths = fg.save(figure, out_dir, stem, dpi, formats)
        sidecar = out_dir / f"{stem}.meta.json"
        atomic_write_text(
            sidecar,
            json.dumps(
                {
                    "figure_id": entry["id"],
                    "run_id": record.get("run_id"),
                    "evaluation_record_sha256": record_sha,
                    "experiment_config_sha256": record.get("config_sha256"),
                    "script": "scripts/generate_figures.py",
                    "git": git,
                    "config_path": str(config_path),
                    "config_sha256": config_sha256(config),
                    "inputs_sha256": {str(p): file_sha256(p) for p in inputs.values()},
                    "packages": {"matplotlib": matplotlib.__version__, "pandas": pd.__version__},
                    "utc": datetime.now(UTC).isoformat(),
                    "data_provenance": "empirical",
                    "caption_draft": entry.get("caption", ""),
                },
                indent=2,
                sort_keys=True,
            ),
        )
        written += [*paths, sidecar]
    return written


def render_diagrams(config: Mapping[str, object], config_path: Path, repo_root: Path) -> list[Path]:
    """Render the conceptual methods diagrams of configs/diagrams.yaml (no data read).

    The triage-rule diagram reads its thresholds from the triage config named in
    ``triage_config``; that file's SHA-256 goes into the sidecar. Sidecars say
    ``data_provenance: conceptual_diagram``.
    """
    from radiosensitivity_ml.models.checkpoints import atomic_write_text
    from radiosensitivity_ml.triage.report import load_triage
    from radiosensitivity_ml.visualization import diagrams as dg

    fg.style()
    out_dir = Path(str(config.get("output_dir", "figures/generated")))
    version = int(config["version"])  # type: ignore[arg-type]
    dpi = int(config["dpi"])  # type: ignore[arg-type]
    formats = tuple(config.get("formats", ("pdf", "svg", "png")))  # type: ignore[arg-type]
    triage_path = Path(str(config["triage_config"]))
    triage = load_triage(triage_path)
    plans = []
    for entry in config["diagrams"]:  # type: ignore[union-attr]
        if entry["kind"] not in dg.DIAGRAMS:
            raise fg.FigureInputError(f"{entry['id']}: unknown diagram kind {entry['kind']!r}")
        stem = f"{entry['id']}_{entry['slug']}_v{version}"
        targets = [out_dir / f"{stem}.{fmt}" for fmt in formats] + [out_dir / f"{stem}.meta.json"]
        existing = [str(p) for p in targets if p.exists()]
        if existing:
            raise FileExistsError(f"{existing} exist; figures are write-once (bump the version)")
        if entry["kind"] == "triage_decision":
            figure = dg.triage_decision(triage.pathway, triage.cell_lines)
        else:
            figure = dg.DIAGRAMS[entry["kind"]]()
        plans.append((entry, figure, stem))
    git = git_state(repo_root)
    written: list[Path] = []
    for entry, figure, stem in plans:
        paths = fg.save(figure, out_dir, stem, dpi, formats)
        sidecar = out_dir / f"{stem}.meta.json"
        inputs = (
            {str(triage_path): file_sha256(triage_path)}
            if entry["kind"] == "triage_decision"
            else {}
        )
        atomic_write_text(
            sidecar,
            json.dumps(
                {
                    "figure_id": entry["id"],
                    "script": "scripts/generate_figures.py",
                    "git": git,
                    "config_path": str(config_path),
                    "config_sha256": config_sha256(config),
                    "inputs_sha256": inputs,
                    "packages": {"matplotlib": matplotlib.__version__},
                    "utc": datetime.now(UTC).isoformat(),
                    "data_provenance": "conceptual_diagram",
                    "caption_draft": entry.get("caption", ""),
                },
                indent=2,
                sort_keys=True,
            ),
        )
        written += [*paths, sidecar]
    return written
