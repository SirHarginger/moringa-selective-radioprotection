#!/usr/bin/env python3
"""Audit raw NCI-60 CellMiner activity values without creating training data or model features."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

from moringa_radioprotection.nci import load_project_config
from moringa_radioprotection.raw_activity import (
    build_raw_activity_summary,
    build_raw_processed_overlap,
    build_raw_profile_identity_audit,
    build_raw_profile_identity_summary,
    build_raw_replicate_summary,
    build_raw_replicate_variability,
    build_raw_zscore_reconstruction,
    build_raw_zscore_reconstruction_summary,
    load_raw_activity_frame,
    summarize_raw_activity,
)


def configure_logger(log_dir: Path) -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"audit_nci_raw_{timestamp}.log"

    logger = logging.getLogger("audit_nci_raw")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)
    logger.info("Starting raw NCI activity audit")
    logger.info("Log file: %s", log_path)
    return logger


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit raw NCI-60 CellMiner activity values.")
    parser.add_argument("--config", required=True, help="Path to the YAML project configuration file.")
    args = parser.parse_args()

    config = load_project_config(args.config)
    logger = configure_logger(Path(config.get("paths", {}).get("logs", "results/logs")))

    raw_frame = load_raw_activity_frame(config)
    prepared_path = Path(config.get("paths", {}).get("interim_data", "data/interim")) / "nci_cancer_response.csv"
    prepared_frame = pd.read_csv(prepared_path)

    audit = summarize_raw_activity(raw_frame)
    replicate_summary = build_raw_replicate_summary(raw_frame)
    replicate_variability = build_raw_replicate_variability(raw_frame)
    overlap = build_raw_processed_overlap(raw_frame, prepared_frame)
    profile_identity_audit = build_raw_profile_identity_audit(raw_frame)
    profile_identity_summary = build_raw_profile_identity_summary(profile_identity_audit)
    zscore_reconstruction = build_raw_zscore_reconstruction(
        raw_frame,
        prepared_frame,
        identity_audit=profile_identity_audit,
    )
    zscore_reconstruction_summary = build_raw_zscore_reconstruction_summary(
        raw_frame,
        prepared_frame,
        reconstruction_frame=zscore_reconstruction,
    )

    candidate_summary = build_raw_activity_summary(raw_frame)
    candidate_summary_path = Path(config.get("paths", {}).get("interim_data", "data/interim")) / "nci_raw_activity_summary.csv"
    candidate_summary.to_csv(candidate_summary_path, index=False)
    logger.info("Candidate raw summary written to %s", candidate_summary_path)

    table_dir = Path(config.get("paths", {}).get("tables", "results/tables"))
    table_dir.mkdir(parents=True, exist_ok=True)

    outputs = {
        "nci_raw_activity_audit.csv": audit,
        "nci_raw_replicate_summary.csv": replicate_summary,
        "nci_raw_replicate_variability.csv": replicate_variability,
        "nci_raw_processed_overlap.csv": overlap,
        "nci_raw_profile_identity_audit.csv": profile_identity_audit,
        "nci_raw_profile_identity_summary.csv": profile_identity_summary,
        "nci_raw_zscore_reconstruction_summary.csv": zscore_reconstruction_summary,
        "nci_raw_zscore_reconstruction.csv": zscore_reconstruction,
    }

    for name, frame in outputs.items():
        path = table_dir / name
        frame.to_csv(path, index=False)
        logger.info("Wrote %s", path)

    logger.info("Raw NCI activity audit completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
