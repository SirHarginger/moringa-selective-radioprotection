"""Render the report figures into figures/png, figures/pdf and figures/metadata
(INVESTIGATOR-RUN).

    python scripts/make_report_figures.py --config configs/figures_report.yaml
    python scripts/make_report_figures.py --config configs/figures_report.yaml \
        --only fig_08 fig_09            # just the compound figures
    python scripts/make_report_figures.py --config configs/figures_report.yaml \
        --overwrite                     # reproduce existing files in place

Results figures read saved tables only; the workflow diagram reads no data. Nothing is
fitted, re-predicted or re-scored. PNG (600 dpi) and PDF (vector) are written with
identical basenames, provenance sidecars go to figures/metadata/, and
figures/metadata/figure_index.csv lists everything rendered.

Also writes reports/french_embassy/figure_manifest.csv, which the report uses to resolve
each figure number to the file that was actually rendered (pass --no-manifest to skip).
"""

from __future__ import annotations

import argparse
import csv
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import yaml

from radiosensitivity_ml.models.checkpoints import atomic_write_text
from radiosensitivity_ml.visualization.figures import FigureInputError
from radiosensitivity_ml.visualization.report_render import render_report

MANIFEST_COLUMNS = ("report_label", "figure_id", "stem", "png", "pdf", "metadata",
                    "data_provenance", "caption")  # fmt: skip


def write_manifest(config: dict, manifest_path: Path) -> Path:
    """One row per configured figure: its report number, files and full caption."""
    version = int(config["version"])
    root = Path(str(config.get("output_root", "figures")))
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(MANIFEST_COLUMNS), lineterminator="\n")
    writer.writeheader()
    for entry in config["figures"]:
        stem = f"{entry['id']}_{entry['slug']}"
        writer.writerow(
            {
                "report_label": entry.get("report_label", ""),
                "figure_id": entry["id"],
                "stem": stem,
                "png": (root / "png" / f"{stem}.png").as_posix(),
                "pdf": (root / "pdf" / f"{stem}.pdf").as_posix(),
                "metadata": (root / "metadata" / f"{stem}.meta.json").as_posix(),
                "data_provenance": entry.get("data_provenance", ""),
                "caption": " ".join(str(entry.get("caption", "")).split()),
            }
        )
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(manifest_path, buffer.getvalue())
    print(f"(version {version}) {manifest_path}")
    return manifest_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--only", nargs="+", metavar="FIG_ID",
                        help="render only these figure ids")  # fmt: skip
    parser.add_argument("--overwrite", action="store_true",
                        help="replace existing files (a reproduction, not a new result)")  # fmt: skip
    parser.add_argument("--no-manifest", action="store_true",
                        help="do not write reports/french_embassy/figure_manifest.csv")  # fmt: skip
    args = parser.parse_args(argv)
    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    try:
        written = render_report(config, args.config, ROOT, only=args.only, overwrite=args.overwrite)
    except (FigureInputError, FileExistsError, KeyError) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    for path in written:
        print(path)
    if not args.no_manifest:
        write_manifest(config, ROOT / "reports" / "french_embassy" / "figure_manifest.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
