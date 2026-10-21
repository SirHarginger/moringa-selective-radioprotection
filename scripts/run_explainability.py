"""Gene-set importance and stability for a completed run (INVESTIGATOR-RUN).

    python scripts/run_explainability.py --config configs/experiment.yaml

Uses the saved models of the run (no refitting) and the negative-control tasks as nulls.
Run evaluate_models.py first (its primary verdict gates attribution statements).
Writes results/tables/<run_id>/explainability/ (write-once).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from radiosensitivity_ml.config import ExperimentConfigError, load_experiment
from radiosensitivity_ml.data.provenance import ProvenanceError
from radiosensitivity_ml.explainability.report import explain_run
from radiosensitivity_ml.models.checkpoints import CheckpointError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--permutations", type=int, default=20, help="per feature and task")
    args = parser.parse_args(argv)
    try:
        out = explain_run(load_experiment(args.config), n_repeats=args.permutations)
    except (
        ExperimentConfigError, ProvenanceError, CheckpointError, FileExistsError, ValueError,
    ) as exc:  # fmt: skip
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
