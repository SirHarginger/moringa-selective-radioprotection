#!/usr/bin/env python3
"""Acquire the official NCI-60 / CellMiner archive resources required by the project.

This stage is limited to raw acquisition. It downloads official NIH/NCI direct-download
ZIP files to data/raw/nci60/ and does not unzip, transform, or preprocess the data.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

from moringa_radioprotection.nci import (
    acquisition_requirements,
    download_resource,
    load_project_config,
    log_directory,
    manual_download_instructions,
    parse_file_status,
    raw_nci_directory,
    sha256_file,
    timestamp_utc,
    validate_zip_archive,
    write_manifest,
)


def configure_logger(log_dir: Path) -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"fetch_nci_{timestamp}.log"

    logger = logging.getLogger("fetch_nci")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    logger.info("Starting NCI raw acquisition stage")
    logger.info("Log file: %s", log_path)
    return logger


def evaluate_resource(config: dict, item: dict, raw_dir: Path, logger: logging.Logger) -> dict:
    """Check for presence, download if needed, and validate the resource."""
    filename = item.get("local_filename", "")
    if not filename:
        raise ValueError("Each NCI resource must specify a local_filename.")

    local_path = raw_dir / filename
    url = item.get("source_url", "")
    required = bool(item.get("required", True))

    if local_path.exists():
        status, size, digest = parse_file_status(local_path)
        if status == "present" and local_path.suffix.lower() == ".zip" and not validate_zip_archive(local_path):
            status = "invalid_zip"
            digest = ""
        row = {
            "source": config.get("nci", {}).get("source_name", "NIH/NCI CellMiner DTP direct download"),
            "source_url": url,
            "retrieval_date_utc": timestamp_utc(),
            "local_filename": filename,
            "local_path": str(local_path),
            "file_size_bytes": int(size),
            "sha256": digest,
            "status": status,
            "required": required,
            "notes": item.get("notes", item.get("purpose", "")),
        }
        logger.info("Existing file %s status=%s size=%s", local_path, status, size)
        return row

    logger.info("Downloading %s from %s", filename, url)
    success, message = download_resource(url, local_path)
    if success:
        size = local_path.stat().st_size
        digest = sha256_file(local_path)
        status = "downloaded"
        logger.info("Downloaded %s status=%s size=%s sha256=%s", local_path, status, size, digest)
    else:
        status = "failed" if required else "optional_failed"
        size = 0
        digest = ""
        logger.warning("Download failed for %s (%s): %s", filename, url, message)

    row = {
        "source": config.get("nci", {}).get("source_name", "NIH/NCI CellMiner DTP direct download"),
        "source_url": url,
        "retrieval_date_utc": timestamp_utc(),
        "local_filename": filename,
        "local_path": str(local_path),
        "file_size_bytes": int(size),
        "sha256": digest,
        "status": status,
        "required": required,
        "notes": item.get("notes", item.get("purpose", "")),
    }
    return row


def build_rows(config: dict, logger: logging.Logger) -> list[dict]:
    raw_dir = raw_nci_directory(config)
    raw_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Raw NCI directory: %s", raw_dir)

    rows: list[dict] = []
    for item in acquisition_requirements(config):
        rows.append(evaluate_resource(config, item, raw_dir, logger))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Acquire the official NCI-60 / CellMiner ZIP resources required by the project.")
    parser.add_argument("--config", required=True, help="Path to the YAML project configuration file.")
    args = parser.parse_args()

    config = load_project_config(args.config)
    logger = configure_logger(log_directory(config))

    logger.info("Configuration: %s", args.config)
    logger.info("Random seed: %s", config.get("project", {}).get("random_seed", "unknown"))

    rows = build_rows(config, logger)
    manifest_path = raw_nci_directory(config) / "acquisition_manifest.csv"
    write_manifest(rows, manifest_path)
    logger.info("Acquisition manifest written to %s", manifest_path)

    required_failures = [row for row in rows if row["required"] and row["status"] in {"failed", "missing", "invalid_zip", "unreadable", "invalid_path", "empty"}]
    optional_failures = [row for row in rows if not row["required"] and row["status"] == "optional_failed"]

    if required_failures:
        logger.error("Required acquisition failed for: %s", ", ".join(row["local_filename"] for row in required_failures))
        print(manual_download_instructions(config, required_failures))
        logger.info("Acquisition stage finished with failure due to required files.")
        return 1

    if optional_failures:
        logger.warning("Optional raw dataset could not be retrieved: %s", ", ".join(row["local_filename"] for row in optional_failures))
        print("Optional raw dataset acquisition failed, but the required NCI resources are available; acquisition continues.")

    logger.info("Required NCI acquisition completed successfully.")
    print("NCI acquisition completed successfully: required resources are present and validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
