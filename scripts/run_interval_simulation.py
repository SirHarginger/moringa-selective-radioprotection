"""Coverage simulation that selects the interval method (INVESTIGATOR-RUN; protocol §13).

    python scripts/run_interval_simulation.py --config configs/simulation.yaml --pilot
    python scripts/run_interval_simulation.py --config configs/simulation.yaml
    python scripts/run_interval_simulation.py --config configs/simulation.yaml --resume

Synthetic outcomes only: no CLARIFi outcome is read. Run it after the protocol freeze
and BEFORE unsealing the real outcome. --pilot runs a few replicates per scenario to
measure runtime (no decision). The full run writes results/simulation/<run_id>/
operating_characteristics.csv and decision.json (adopted method and repeat count).
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
from radiosensitivity_ml.simulation.study import run_study, study_from_mapping


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--pilot", action="store_true", help="runtime pilot only")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args(argv)
    try:
        data = yaml.safe_load(args.config.read_text(encoding="utf-8"))
        study = study_from_mapping(data)
        experiment = load_experiment(Path(str(data["experiment_config"])))
        inputs = prepare_inputs(experiment, experiment.population_options)
        out = run_study(study, experiment, inputs, resume=args.resume, pilot=args.pilot)
    except (ExperimentConfigError, ProvenanceError, CheckpointError, ValueError, KeyError) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
