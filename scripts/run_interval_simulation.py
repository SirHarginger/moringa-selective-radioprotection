"""Coverage simulation that selects the interval method (INVESTIGATOR-RUN; protocol §13).

    python scripts/run_interval_simulation.py --config configs/simulation.yaml --pilot
    python scripts/run_interval_simulation.py --config configs/simulation.yaml
    python scripts/run_interval_simulation.py --config configs/simulation.yaml --resume

Synthetic outcomes only: no CLARIFi outcome is read. Run it after the protocol freeze
and BEFORE unsealing the real outcome. --pilot runs a few replicates per scenario and
writes results/simulation/<pilot_run_id>/runtime.json only (no operating characteristics,
no decision; protocol §13 budget rule). The full run writes results/simulation/<run_id>/
operating_characteristics.csv, decision.json (adopted method and repeat count) and
runtime.json.

--workers N (default 1) computes independent replicates and truth draws in N processes.
Results do not depend on N, so N may change between resumed sessions. N > 1 requires
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 in the environment (use the
same setting for the pilot and the full run: it is recorded in, and compared by, the
manifest). Choose N from the available memory; it is never chosen automatically.
Ctrl+C stops the run; finished checkpoints are kept, and --resume continues.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import yaml

from radiosensitivity_ml.config import ExperimentConfigError, load_experiment
from radiosensitivity_ml.data.provenance import ProvenanceError
from radiosensitivity_ml.models.checkpoints import CheckpointError
from radiosensitivity_ml.models.run import prepare_inputs
from radiosensitivity_ml.simulation.study import check_workers, run_study, study_from_mapping


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--pilot", action="store_true", help="runtime pilot only")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--workers", type=int, default=1, help="worker processes (default 1; see above)"
    )
    args = parser.parse_args(argv)
    try:
        check_workers(args.workers)  # fail before loading inputs
        data = yaml.safe_load(args.config.read_text(encoding="utf-8"))
        study = study_from_mapping(data)
        experiment = load_experiment(Path(str(data["experiment_config"])))
        inputs = prepare_inputs(experiment, experiment.population_options)
        out = run_study(
            study, experiment, inputs, resume=args.resume, pilot=args.pilot,
            workers=args.workers,
        )  # fmt: skip
    except (ExperimentConfigError, ProvenanceError, CheckpointError, ValueError, KeyError) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print(
            "INTERRUPTED: finished checkpoints are intact; continue with --resume",
            file=sys.stderr,
        )
        return 130
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
