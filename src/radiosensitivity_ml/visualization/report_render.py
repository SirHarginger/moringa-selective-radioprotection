"""Render the report figures (version 3) into the split output layout.

    figures/png/<stem>.png        600 dpi raster
    figures/pdf/<stem>.pdf        vector
    figures/metadata/<stem>.meta.json   provenance sidecar (inputs, code, caption)
    figures/metadata/figure_index.csv   one row per rendered figure

``stem`` = ``<id>_<slug>`` and is identical across the folders. Only PNG and PDF are
produced; SVG is refused. Outputs are write-once unless ``overwrite`` is given (report
figures are derived deterministically from immutable saved tables, so a re-render is a
reproduction, not a new result). Inputs under ``tests/`` are refused. Every input of
every requested figure is checked before anything is written.
"""

from __future__ import annotations

import csv
import io
import json
import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import pandas as pd

from radiosensitivity_ml.config import config_sha256
from radiosensitivity_ml.data.provenance import file_sha256
from radiosensitivity_ml.visualization import diagrams as dg
from radiosensitivity_ml.visualization import report_figures as rf
from radiosensitivity_ml.visualization.figures import FIXED_METADATA, FigureInputError

ALLOWED_FORMATS = ("png", "pdf")
PROVENANCE = ("empirical", "conceptual_diagram")
INDEX_COLUMNS = ("figure_id", "report_label", "stem", "png", "pdf", "metadata",
                 "data_provenance", "version")  # fmt: skip
# tables whose first column is the row index (gene sets)
INDEXED_INPUTS = ("importance_per_task.csv", "gene_set_score_correlation.csv")


@dataclass(frozen=True)
class FigurePlan:
    entry: Mapping[str, object]
    stem: str
    inputs: dict[str, Path]
    builder: Callable[..., plt.Figure]


def _rel(path: Path, root: Path) -> str:
    """Repository-relative path when possible (no machine-specific absolute paths)."""
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def output_paths(root: Path, stem: str) -> dict[str, Path]:
    """Where one figure's files go (identical basename in every folder)."""
    return {
        "png": root / "png" / f"{stem}.png",
        "pdf": root / "pdf" / f"{stem}.pdf",
        "metadata": root / "metadata" / f"{stem}.meta.json",
    }


def check_formats(formats: Sequence[str]) -> tuple[str, ...]:
    """Only PNG and PDF are produced for report figures."""
    bad = [f for f in formats if f not in ALLOWED_FORMATS]
    if bad:
        raise FigureInputError(f"report figures are PNG and PDF only; refused formats {bad}")
    return tuple(formats)


def load_input(path: Path) -> pd.DataFrame:
    """Read one input table; synthetic test locations are refused."""
    if "tests" in path.resolve().parts:
        raise FigureInputError(f"{path}: inputs under tests/ are synthetic and never plotted")
    if not path.is_file():
        raise FigureInputError(f"{path} does not exist (run the step that produces it first)")
    return pd.read_csv(path, index_col=0 if path.name in INDEXED_INPUTS else None)


def git_state(root: Path) -> dict[str, object]:
    """Git commit and dirty flag of ``root``, or an explicit record that they are absent.

    A real repository run records genuine provenance. When ``root`` is not inside a Git
    work tree, or the ``git`` executable is unavailable, the sidecar records
    ``available: false`` with the reason instead of failing: that case arises in tests,
    which render into a temporary directory, and in exported copies of the repository.
    Provenance is never silently faked -- a sidecar without a commit says so, and the
    completeness audit treats it as unprovenanced.
    """

    def git(*args: str) -> str:
        return subprocess.run(
            ["git", "-C", str(root), *args], capture_output=True, text=True, check=True
        ).stdout.strip()

    try:
        inside = git("rev-parse", "--is-inside-work-tree") == "true"
    except (subprocess.CalledProcessError, OSError) as exc:
        reason = (
            "git executable not available"
            if isinstance(exc, OSError)
            else f"{root} is not inside a Git work tree"
        )
        return {"available": False, "reason": reason, "commit": None, "dirty": None}
    if not inside:
        return {
            "available": False,
            "reason": f"{root} is not inside a Git work tree",
            "commit": None,
            "dirty": None,
        }
    return {
        "available": True,
        "commit": git("rev-parse", "HEAD"),
        "dirty": bool(git("status", "--porcelain")),
    }


def builder_for(kind: str) -> Callable[..., plt.Figure]:
    if kind in rf.FIGURES:
        return rf.FIGURES[kind]
    if kind in dg.DIAGRAMS and kind != "triage_decision":
        return dg.DIAGRAMS[kind]
    raise FigureInputError(f"unknown figure kind {kind!r}")


def plan(
    config: Mapping[str, object], repo_root: Path, only: Sequence[str] | None = None
) -> list[FigurePlan]:
    """Validate the configured entries (ids unique, provenance known, inputs present)."""
    entries = list(config["figures"])  # type: ignore[arg-type]
    ids = [str(e["id"]) for e in entries]
    if len(set(ids)) != len(ids):
        raise FigureInputError("figure ids must be unique")
    stems = [f"{e['id']}_{e['slug']}" for e in entries]
    if len(set(stems)) != len(stems):
        raise FigureInputError("figure stems must be unique")
    wanted = set(only) if only else set(ids)
    unknown = wanted - set(ids)
    if unknown:
        raise FigureInputError(f"--only names unknown figure ids {sorted(unknown)}")
    plans = []
    for entry, stem in zip(entries, stems, strict=True):
        if str(entry["id"]) not in wanted:
            continue
        if entry.get("data_provenance") not in PROVENANCE:
            raise FigureInputError(f"{entry['id']}: data_provenance must be one of {PROVENANCE}")
        inputs = {k: repo_root / str(v) for k, v in dict(entry.get("inputs", {})).items()}
        if entry["data_provenance"] == "conceptual_diagram" and inputs:
            raise FigureInputError(f"{entry['id']}: a conceptual diagram reads no data")
        if entry["data_provenance"] == "empirical" and not inputs:
            raise FigureInputError(f"{entry['id']}: an empirical figure needs input tables")
        plans.append(FigurePlan(entry, stem, inputs, builder_for(str(entry["kind"]))))
    return plans


def save(fig: plt.Figure, paths: Mapping[str, Path], dpi: int, formats: Sequence[str]) -> None:
    for fmt in formats:
        paths[fmt].parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(paths[fmt], dpi=dpi if fmt == "png" else None,
                    metadata=FIXED_METADATA.get(fmt))  # fmt: skip
    plt.close(fig)


def package_versions() -> dict[str, str]:
    versions = {"matplotlib": matplotlib.__version__, "pandas": pd.__version__}
    try:
        import seaborn

        versions["seaborn"] = seaborn.__version__
    except ImportError:  # diagrams need no Seaborn
        versions["seaborn"] = "not installed"
    return versions


def write_index(root: Path, rows: list[dict[str, object]]) -> Path:
    """figures/metadata/figure_index.csv, merged with rows of figures not re-rendered."""
    path = root / "metadata" / "figure_index.csv"
    merged: dict[str, dict[str, object]] = {}
    if path.is_file():
        for row in csv.DictReader(path.read_text(encoding="utf-8").splitlines()):
            merged[row["figure_id"]] = row
    for row in rows:
        merged[str(row["figure_id"])] = row
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(INDEX_COLUMNS), lineterminator="\n")
    writer.writeheader()
    for key in sorted(merged):
        writer.writerow({c: merged[key].get(c, "") for c in INDEX_COLUMNS})
    from radiosensitivity_ml.models.checkpoints import atomic_write_text

    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, buffer.getvalue())
    return path


def render_report(
    config: Mapping[str, object],
    config_path: Path,
    repo_root: Path,
    only: Sequence[str] | None = None,
    overwrite: bool = False,
) -> list[Path]:
    """Render the configured report figures; returns every written path."""
    from radiosensitivity_ml.models.checkpoints import atomic_write_text

    root = repo_root / str(config.get("output_root", "figures"))
    dpi = int(config["dpi"])  # type: ignore[arg-type]
    version = int(config["version"])  # type: ignore[arg-type]
    formats = check_formats(list(config.get("formats", ALLOWED_FORMATS)))  # type: ignore[arg-type]
    plans = plan(config, repo_root, only)
    built = []
    for item in plans:  # build every figure (all column checks) before writing anything
        paths = output_paths(root, item.stem)
        existing = [str(p) for p in paths.values() if p.exists()]
        if existing and not overwrite:
            raise FileExistsError(f"{existing} exist; pass --overwrite to reproduce them")
        tables = {name: load_input(path) for name, path in item.inputs.items()}
        figure = item.builder(**tables, **dict(item.entry.get("options", {})))
        built.append((item, paths, figure))
    git = git_state(repo_root)
    written: list[Path] = []
    rows = []
    for item, paths, figure in built:
        save(figure, paths, dpi, formats)
        record = {
            "figure_id": item.entry["id"],
            "report_label": item.entry.get("report_label", ""),
            "stem": item.stem,
            "version": version,
            "kind": item.entry["kind"],
            "script": "scripts/make_report_figures.py",
            "git": git,
            "config_path": str(config_path),
            "config_sha256": config_sha256(config),
            "inputs_sha256": {_rel(p, repo_root): file_sha256(p) for p in item.inputs.values()},
            "options": dict(item.entry.get("options", {})),
            "formats": list(formats),
            "png_dpi": dpi,
            "packages": package_versions(),
            "utc": datetime.now(UTC).isoformat(),
            "data_provenance": item.entry["data_provenance"],
            "caption": str(item.entry.get("caption", "")).strip(),
        }
        paths["metadata"].parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(paths["metadata"], json.dumps(record, indent=2, sort_keys=True))
        written += [paths[f] for f in formats] + [paths["metadata"]]
        rows.append(
            {
                "figure_id": item.entry["id"],
                "report_label": item.entry.get("report_label", ""),
                "stem": item.stem,
                "png": _rel(paths["png"], repo_root) if "png" in formats else "",
                "pdf": _rel(paths["pdf"], repo_root) if "pdf" in formats else "",
                "metadata": _rel(paths["metadata"], repo_root),
                "data_provenance": item.entry["data_provenance"],
                "version": version,
            }
        )
    written.append(write_index(root, rows))
    return written
