#!/usr/bin/env python3
"""Train conventional cancer-potency baselines from frozen NCI artifacts."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

from moringa_radioprotection.models import run_cancer_baseline
from moringa_radioprotection.nci import load_project_config


def configure_logger(log_dir: Path) -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"train_cancer_{timestamp}.log"

    logger = logging.getLogger("train_cancer")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)
    logger.info("Starting conventional frozen-split cancer-potency benchmark")
    logger.info("Log file: %s", log_path)
    return logger


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Train conventional MCF-7 and DU145 absolute-potency benchmarks."
    )
    parser.add_argument(
        "--config",
        required=True,
        help="Path to the YAML project configuration file.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from existing model checkpoints if present.",
    )
    args = parser.parse_args()

    config = load_project_config(args.config)
    logger = configure_logger(Path(config.get("paths", {}).get("logs", "results/logs")))
    run_cancer_baseline(config, logger, resume=bool(args.resume))
    logger.info("Cancer-potency benchmark completed successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
