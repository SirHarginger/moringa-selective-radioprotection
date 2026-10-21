"""Run the prespecified ML benchmark (INVESTIGATOR-RUN; requires the frozen protocol).

    python scripts/run_model.py --config configs/experiment.yaml
    python scripts/run_model.py --config configs/experiment.yaml --resume

Creates results/models/<run_id>/ (never overwrites). With --resume, continues an
interrupted run only if configuration, code, inputs, splits, packages and thread
settings are unchanged; completed tasks are verified and reused, corrupted ones moved to
_rejected/ and recomputed. See docs/phase_03_implementation_spec.md.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from radiosensitivity_ml.config import ExperimentConfigError, load_experiment
from radiosensitivity_ml.data.provenance import ProvenanceError
from radiosensitivity_ml.models.checkpoints import CheckpointError
from radiosensitivity_ml.models.run import run_experiment


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--resume", action="store_true", help="continue a compatible run")
    args = parser.parse_args(argv)
    if not (Path("pyproject.toml").is_file() and Path("configs").is_dir()):
        print("Run this from the repository root.", file=sys.stderr)
        return 2
    try:
        config = load_experiment(args.config)
        counts = run_experiment(config, config.population_options, resume=args.resume)
    except (
        ExperimentConfigError, ProvenanceError, CheckpointError, FileNotFoundError,
        NotImplementedError,
    ) as exc:  # fmt: skip
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    if counts["failed"]:
        print(
            f"{counts['failed']} task(s) failed (see failures.jsonl); fix and re-run with --resume",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
