"""Compare the checkpoints of two simulation folders (read-only; no computation).

    python scripts/compare_simulation_runs.py \
        --reference results/simulation/coverage_v1_pilot \
        --candidate results/simulation/coverage_v1_pilot_opt

Used to check the optimised code (D04.05) against the pre-optimisation pilot. For every
truth_*.json and replicates/*.json present in BOTH folders it reports whether the bytes
are identical and, if not, the largest absolute difference over numeric fields. Exit
status 0 only if every common file is byte-identical, or (with --atol) every numeric
difference is <= atol and all non-numeric fields are equal. Files present in only one
folder are listed and do not count as failures.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path


def checkpoint_files(root: Path) -> dict[str, Path]:
    paths = [*root.glob("truth_*.json"), *(root / "replicates").glob("*.json")]
    return {str(p.relative_to(root)): p for p in sorted(paths)}


def max_difference(reference: dict[str, object], candidate: dict[str, object]) -> float:
    """Largest absolute numeric difference; inf if keys or non-numeric values differ."""
    if reference.keys() != candidate.keys():
        return math.inf
    worst = 0.0
    for key, ref in reference.items():
        new = candidate[key]
        numeric = isinstance(ref, int | float) and isinstance(new, int | float)
        if not numeric or isinstance(ref, bool) or isinstance(new, bool):
            if ref != new:
                return math.inf
            continue
        if math.isnan(ref) and math.isnan(new):
            continue
        if math.isinf(ref) or math.isinf(new):
            if ref != new:
                return math.inf
            continue
        worst = max(worst, abs(float(ref) - float(new)))
    return worst


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--atol", type=float, default=0.0, help="default 0: bytes must match")
    args = parser.parse_args(argv)
    reference, candidate = checkpoint_files(args.reference), checkpoint_files(args.candidate)
    common = sorted(reference.keys() & candidate.keys())
    failures = 0
    for name in common:
        ref_bytes, new_bytes = reference[name].read_bytes(), candidate[name].read_bytes()
        if ref_bytes == new_bytes:
            print(f"IDENTICAL  {name}")
            continue
        diff = max_difference(json.loads(ref_bytes), json.loads(new_bytes))
        ok = args.atol > 0 and diff <= args.atol
        failures += not ok
        print(f"{'WITHIN' if ok else 'DIFFERENT':<10} {name}  max|diff| = {diff:.3g}")
    for name in sorted(reference.keys() ^ candidate.keys()):
        side = "reference" if name in reference else "candidate"
        print(f"ONLY-IN-{side.upper():<9} {name}")
    print(f"{len(common)} common files, {failures} failing (atol = {args.atol})")
    if not common:
        print("ERROR: no common checkpoint files to compare", file=sys.stderr)
        return 2
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
