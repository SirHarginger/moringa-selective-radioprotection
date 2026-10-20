#!/usr/bin/env python3
"""Prepare the NCI-60 CellMiner z-score dataset for downstream modeling stages.

This stage is intentionally limited to raw dataset reading, structure auditing, and
paired-response extraction. It does not model, split, or screen compounds.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

from moringa_radioprotection.nci import load_project_config, prepare_nci_stage


def configure_logger(log_dir: Path) -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"prepare_nci_{timestamp}.log"

    logger = logging.getLogger("prepare_nci")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    logger.info("Starting NCI preparation stage")
    logger.info("Log file: %s", log_path)
    return logger


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare the CellMiner NCI-60 z-score dataset for downstream analysis.")
    parser.add_argument("--config", required=True, help="Path to the YAML project configuration file.")
    args = parser.parse_args()

    config = load_project_config(args.config)
    logger = configure_logger(Path(config.get("paths", {}).get("logs", "results/logs")))

    logger.info("Configuration: %s", args.config)
    logger.info("Random seed: %s", config.get("project", {}).get("random_seed", "unknown"))

    prepared, paired, audit = prepare_nci_stage(config, logger)

    raw_dir = Path(config.get("paths", {}).get("raw_data", "data/raw")) / "nci60"
    interim_dir = Path(config.get("paths", {}).get("interim_data", "data/interim"))
    table_dir = Path(config.get("paths", {}).get("tables", "results/tables"))
    interim_dir.mkdir(parents=True, exist_ok=True)
    table_dir.mkdir(parents=True, exist_ok=True)

    prepared_path = interim_dir / "nci_cancer_response.csv"
    paired_path = interim_dir / "nci_paired_response.csv"
    audit_path = table_dir / "nci_dataset_audit.csv"

    prepared.to_csv(prepared_path, index=False)
    paired.to_csv(paired_path, index=False)
    audit.to_csv(audit_path, index=False)

    logger.info("Prepared dataset written to %s", prepared_path)
    logger.info("Paired dataset written to %s", paired_path)
    logger.info("Audit table written to %s", audit_path)
    logger.info("NCI preparation stage completed successfully")

    print(f"Prepared NCI table: {prepared_path}")
    print(f"Paired response table: {paired_path}")
    print(f"Audit table: {audit_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
