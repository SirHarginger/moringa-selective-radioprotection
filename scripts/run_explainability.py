"""Gene-set importance and stability for a completed run (INVESTIGATOR-RUN).

    export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
    python scripts/run_explainability.py --config configs/experiment.yaml --workers 6

Uses the saved models of the run (no refitting) and the negative-control tasks as nulls.
Run evaluate_models.py first (its primary verdict gates attribution statements).
Writes results/tables/<run_id>/explainability/ (write-once). Per-task importances are
checkpointed in results/tables/<run_id>/explainability_checkpoints/ (parent-written,
atomic); re-running the same command after an interruption reuses verified checkpoints.
--workers N (default 1) computes tasks in N processes (N > 1 needs the thread variables
above = 1); results do not depend on N.
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
from radiosensitivity_ml.parallel import check_workers


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--permutations", type=int, default=20, help="per feature and task")
    parser.add_argument("--workers", type=int, default=1, help="worker processes (default 1)")
    args = parser.parse_args(argv)
    try:
        check_workers(args.workers)
        out = explain_run(
            load_experiment(args.config), n_repeats=args.permutations, workers=args.workers
        )
    except (
        ExperimentConfigError, ProvenanceError, CheckpointError, FileExistsError, ValueError,
    ) as exc:  # fmt: skip
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("INTERRUPTED: finished task checkpoints are kept; re-run to resume", file=sys.stderr)
        return 130
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
