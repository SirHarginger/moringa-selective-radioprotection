"""Acquire and verify the public source data (step 1 of the workflow).

    python scripts/acquire_data.py              # DepMap 24Q4 core files, then Cellosaurus
    python scripts/acquire_data.py --verify     # offline integrity check of what is present
    python scripts/acquire_data.py --dry-run    # list what would be downloaded, and where

Options that add files (nothing else is downloaded):
    --batch-corrected   24Q4 batch-corrected expression (sensitivity analysis only)
    --audit-23q4        23Q4 Model.csv (identifier-drift audit only)
    --yard              Yard 2016 supplements (secondary cross-assay data)
    --skip-cellosaurus  DepMap only

Re-running is safe: files already present are verified, never overwritten. An
interrupted download restarts from scratch. A failed Cellosaurus fetch leaves
data/raw/cellosaurus/r56_0.partial; delete that folder and re-run.

CLARIFi (data/raw/CLARIFi.csv) is not downloaded: it is already in place and is
verified against its manifest checksum.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))  # run without installing the package

from radiosensitivity_ml.data import acquisition as acq
from radiosensitivity_ml.data import cellosaurus as cs
from radiosensitivity_ml.data import cellosaurus_fetch as cf
from radiosensitivity_ml.data.provenance import (
    file_sha256,
    manifest_file_sha256,
)

CLARIFI = Path("data/raw/CLARIFi.csv")
CLARIFI_MANIFEST = Path("data/manifests/clarifi__v1_0.yaml")


def selected_sources(args: argparse.Namespace) -> list[str]:
    """Names of the file groups requested on the command line."""
    names = ["depmap_24q4", "msigdb_hallmark"]
    if args.batch_corrected:
        names.append("depmap_24q4_batch_corrected")
    if args.audit_23q4:
        names.append("depmap_23q4_audit")
    if args.yard:
        names.append("yard2016")
    return names


def check_clarifi() -> str:
    """Verify CLARIFi against its manifest; return a status line."""
    if not CLARIFI.is_file():
        raise acq.AcquisitionError(f"{CLARIFI} is missing; place the CLARIFi v1.0 file there")
    expected = manifest_file_sha256(CLARIFI_MANIFEST, str(CLARIFI))
    if file_sha256(CLARIFI) != expected:
        raise acq.AcquisitionError(f"{CLARIFI} does not match the SHA-256 in {CLARIFI_MANIFEST}")
    return "ok"


def verify_cellosaurus(settings: cf.FetchSettings) -> str:
    """Offline check of a finished Cellosaurus folder."""
    if not settings.out.exists():
        return "missing"
    ids = cf.read_depmap_ids(settings.clarifi)
    cs.load_saved_responses(settings.out, settings.expected_release, ids)
    return f"ok (COMPLETE.json sha256 {file_sha256(settings.out / 'COMPLETE.json')})"


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    """Command-line options."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--verify", action="store_true", help="offline integrity check only")
    parser.add_argument("--dry-run", action="store_true", help="list planned downloads only")
    parser.add_argument("--batch-corrected", action="store_true")
    parser.add_argument("--audit-23q4", action="store_true")
    parser.add_argument("--yard", action="store_true")
    parser.add_argument("--skip-cellosaurus", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None, opener: acq.Opener = acq.default_opener) -> int:
    """Run acquisition, verification or a dry run from the repository root."""
    args = parse_args(argv)
    if not (Path("pyproject.toml").is_file() and Path("data/manifests").is_dir()):
        print("Run this from the repository root.", file=sys.stderr)
        return 2
    sources = selected_sources(args)
    settings = cf.FetchSettings()
    report: dict[str, object] = {}
    try:
        report["CLARIFi"] = check_clarifi()
        if args.dry_run:
            report["planned"] = {
                name: [
                    {"url": f.url, "dest": str(f.dest), "size": f.size} for f in acq.SOURCES[name]
                ]
                for name in sources
            }
            if not args.skip_cellosaurus:
                report["planned"]["cellosaurus"] = str(settings.out)  # type: ignore[index]
        elif args.verify:
            for name in sources:
                report[name] = acq.verify_group(acq.SOURCES[name])
            if not args.skip_cellosaurus:
                report["cellosaurus"] = verify_cellosaurus(settings)
            missing = [
                k
                for k, v in report.items()
                if v == "missing" or (isinstance(v, dict) and "missing" in v.values())
            ]
            if missing:
                report["result"] = f"INCOMPLETE: missing items in {missing}"
                print(json.dumps(report, indent=2), file=sys.stderr)
                return 1
        else:
            for name in sources:
                print(f"acquiring {name} ...", flush=True)
                report[name] = acq.acquire_group(acq.SOURCES[name], opener)
            if not args.skip_cellosaurus:
                if settings.out.exists():
                    report["cellosaurus"] = verify_cellosaurus(settings)
                else:
                    print("fetching Cellosaurus (several minutes) ...", flush=True)
                    digest = cf.fetch_cellosaurus(settings)
                    report["cellosaurus"] = f"fetched (COMPLETE.json sha256 {digest})"
                    report["next_step"] = (
                        "copy this SHA-256 into configs/preprocessing.yaml "
                        "(cellosaurus.complete_json_sha256)"
                    )
    except (RuntimeError, cs.CellosaurusFormatError, OSError, ValueError) as exc:
        report["error"] = str(exc)
        print(json.dumps(report, indent=2), file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
