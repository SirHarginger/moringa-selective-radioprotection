"""Evaluate a completed run (INVESTIGATOR-RUN).

    python scripts/evaluate_models.py --config configs/experiment.yaml

Refuses to run unless every task of the run is complete and verified. Writes
results/tables/<run_id>/ (write-once): comparisons.csv (paired component-weighted dMAE,
candidate intervals, verdict), per_repeat_delta_mae.csv, model_metrics.csv,
tissue_errors.csv, oof_predictions.csv, within_tissue_spearman.csv,
negative_controls.csv, evaluation_record.json.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from radiosensitivity_ml.config import ExperimentConfigError, load_experiment
from radiosensitivity_ml.evaluation.report import evaluate_run
from radiosensitivity_ml.models.checkpoints import CheckpointError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        out = evaluate_run(load_experiment(args.config))
    except (ExperimentConfigError, CheckpointError, FileExistsError, ValueError) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
