"""Run the prespecified ML benchmark (INVESTIGATOR-RUN; requires the frozen protocol).

    export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
    python scripts/run_model.py --config configs/experiment.yaml --workers 6
    python scripts/run_model.py --config configs/experiment.yaml --resume --workers 6

Creates results/models/<run_id>/ (never overwrites). With --resume, continues an
interrupted run only if configuration, code, inputs, splits, packages and thread
settings are unchanged; completed tasks are verified and reused, corrupted ones moved to
_rejected/ and recomputed. See docs/phase_03_implementation_spec.md.

--workers N (default 1) fits independent tasks in N processes; N > 1 requires the three
thread variables above = 1 (use them for every session: they are compared on resume).
Results do not depend on N, so N may change on resume. Ctrl+C keeps finished tasks;
continue with --resume. Each session is logged in results/models/<run_id>/sessions.jsonl.
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
from radiosensitivity_ml.parallel import check_workers


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--resume", action="store_true", help="continue a compatible run")
    parser.add_argument("--workers", type=int, default=1, help="worker processes (default 1)")
    args = parser.parse_args(argv)
    if not (Path("pyproject.toml").is_file() and Path("configs").is_dir()):
        print("Run this from the repository root.", file=sys.stderr)
        return 2
    try:
        check_workers(args.workers)  # fail before loading any input
        config = load_experiment(args.config)
        counts = run_experiment(
            config, config.population_options, resume=args.resume, workers=args.workers
        )
    except (
        ExperimentConfigError, ProvenanceError, CheckpointError, FileNotFoundError,
        NotImplementedError, ValueError,
    ) as exc:  # fmt: skip
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("INTERRUPTED: finished tasks are intact; continue with --resume", file=sys.stderr)
        return 130
    if counts["failed"]:
        print(
            f"{counts['failed']} task(s) failed (see failures.jsonl); fix and re-run with --resume",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
