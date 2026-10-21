"""Render publication figures (INVESTIGATOR-RUN).

    python scripts/generate_figures.py --config configs/figures.yaml    # results figures
    python scripts/generate_figures.py --config configs/diagrams.yaml   # methods diagrams

Results figures read saved evaluation tables only. Methods diagrams read no data (the
triage-rule diagram reads the frozen thresholds in configs/triage.yaml). Writes
figures/generated/<fig_id>_<slug>_v<N>.{pdf,svg,png} + .meta.json sidecars.
Figures are write-once: bump `version` in the config to regenerate.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import yaml

from radiosensitivity_ml.triage.rules import TriageError
from radiosensitivity_ml.visualization.figures import FigureInputError
from radiosensitivity_ml.visualization.render import render_all, render_diagrams


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
        render = render_diagrams if "diagrams" in config else render_all
        written = render(config, args.config, ROOT)
    except (FigureInputError, FileExistsError, KeyError, TriageError) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    for path in written:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
