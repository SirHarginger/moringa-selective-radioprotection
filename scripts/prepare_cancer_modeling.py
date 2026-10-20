#!/usr/bin/env python3
"""Construct the cancer-modeling cohort, duplicate-resolution tables, and scaffold-aware split without training models."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

from moringa_radioprotection.modeling import save_modeling_outputs
from moringa_radioprotection.nci import load_project_config


def configure_logger(log_dir: Path) -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"prepare_cancer_modeling_{timestamp}.log"

    logger = logging.getLogger("prepare_cancer_modeling")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)
    logger.info("Starting cancer-modeling preparation stage")
    logger.info("Log file: %s", log_path)
    return logger


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare the NCI cancer modeling dataset and scaffold-aware split.")
    parser.add_argument("--config", required=True, help="Path to the YAML project configuration file.")
    args = parser.parse_args()

    config = load_project_config(args.config)
    logger = configure_logger(Path(config.get("paths", {}).get("logs", "results/logs")))

    save_modeling_outputs(config, logger)
    logger.info("Cancer-modeling preparation stage completed successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
