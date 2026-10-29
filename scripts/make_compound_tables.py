"""Build the Moringa compound-evidence and candidate-ranking tables (INVESTIGATOR-RUN).

    python scripts/make_compound_tables.py --config configs/compounds.yaml

Reads the two curated YAML evidence files, validates every record, applies the
prespecified 0-8 priority score and writes write-once tables plus a provenance record to
``results/tables/<run_id>/compounds_v<N>/``. Bump ``version`` in the config to rewrite.

No model is fitted, tuned, evaluated or queried. The optional pathway-overlap table is a
set intersection between genes a published experiment measured and the members of a
Hallmark gene set; pass ``--no-overlap`` to skip it (and the raw GMT it needs).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd
import yaml

from radiosensitivity_ml.compounds.curation import CurationError
from radiosensitivity_ml.compounds.report import write_compound_tables
from radiosensitivity_ml.data.provenance import file_sha256
from radiosensitivity_ml.features.gene_sets import parse_gmt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument(
        "--no-overlap", action="store_true",
        help="skip table_c4 (does not read the Hallmark GMT or the triage table)",
    )  # fmt: skip
    args = parser.parse_args(argv)
    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    run_id = str(config["run_id"])
    version = int(config["version"])
    out_dir = ROOT / str(config["tables_root"]) / run_id / f"compounds_v{version}"
    gene_sets = candidates = None
    provenance: dict[str, object] = {"config_path": str(args.config), "run_id": run_id,
                                     "version": version}  # fmt: skip
    if not args.no_overlap:
        gmt = ROOT / str(config["gene_sets_gmt"])
        triage = ROOT / str(config["pathway_candidates"])
        for path in (gmt, triage):
            if not path.is_file():
                print(f"ERROR: {path} does not exist (use --no-overlap to skip table_c4)",
                      file=sys.stderr)  # fmt: skip
                return 1
        gene_sets = parse_gmt(gmt)
        candidates = pd.read_csv(triage)
        provenance["inputs_sha256_extra"] = {
            str(gmt): file_sha256(gmt),
            str(triage): file_sha256(triage),
        }
    try:
        written = write_compound_tables(
            constituents_path=ROOT / str(config["constituents"]),
            evidence_path=ROOT / str(config["evidence"]),
            out_dir=out_dir,
            gene_sets=gene_sets,
            pathway_candidates=candidates,
            overlap_tiers=tuple(config.get("overlap_tiers", ("A", "B", "C"))),
            extra_provenance=provenance,
        )
    except (CurationError, FileExistsError, KeyError) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    for path in sorted(written.iterdir()):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
