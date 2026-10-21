"""Generate triage rankings from a completed, evaluated and explained run (INVESTIGATOR-RUN).

    python scripts/generate_triage.py --config configs/triage.yaml

Reads saved outputs only (run manifest, evaluation tables, explainability tables, QC
metadata); fits and predicts nothing. Writes results/triage/<run_id>/ (write-once):
pathway_candidates.csv, cell_line_validation_priorities.csv, discrepancy_review.csv,
triage_manifest.json. Rankings are secondary and hypothesis-generating.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from radiosensitivity_ml.config import ExperimentConfigError
from radiosensitivity_ml.data.provenance import ProvenanceError
from radiosensitivity_ml.triage.report import generate_triage, load_triage
from radiosensitivity_ml.triage.rules import TriageError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        out = generate_triage(load_triage(args.config))
    except (TriageError, ExperimentConfigError, ProvenanceError, FileExistsError) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
