#!/usr/bin/env python3
"""Thin orchestration layer for the descriptive NCI-60 analysis stage."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from moringa_radioprotection.analysis import (
    compute_duplicate_structure_audit,
    compute_duplicate_structure_summary,
    compute_qc_experiment_summary,
    compute_response_correlation,
    compute_response_difference_summary,
    compute_response_summary,
    compute_scaffold_summary,
    load_prepared_tables,
)
from moringa_radioprotection.nci import load_project_config
from moringa_radioprotection.plotting import style_publication_axes


def configure_logger(log_dir: Path) -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"analyze_nci_{timestamp}.log"

    logger = logging.getLogger("analyze_nci")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    logger.info("Starting NCI exploratory analysis stage")
    logger.info("Log file: %s", log_path)
    return logger


def plot_response_distribution(values: pd.Series, output_path: Path, *, label: str) -> None:
    """Plot a single response distribution with minimal styling."""
    fig, ax = plt.subplots(figsize=(6.0, 4.5), dpi=400)
    values = pd.to_numeric(values, errors="coerce").dropna()
    if values.empty:
        ax.text(0.5, 0.5, "No data", ha="center", va="center")
        ax.set_axis_off()
    else:
        ax.hist(values, bins=30, color="#4c78a8", edgecolor="black", linewidth=0.4)
        ax.set_xlabel(f"{label} z-score")
        ax.set_ylabel("Count")
        style_publication_axes(ax, xlabel=f"{label} z-score", ylabel="Count")
    fig.tight_layout()
    fig.savefig(output_path, dpi=400, bbox_inches="tight")
    plt.close(fig)


def plot_response_scatter(paired: pd.DataFrame, output_path: Path) -> None:
    """Plot the paired MCF7/DU145 response relationship."""
    fig, ax = plt.subplots(figsize=(6.0, 4.5), dpi=400)
    if paired.empty:
        ax.text(0.5, 0.5, "No paired responses", ha="center", va="center")
        ax.set_axis_off()
    else:
        ax.scatter(paired["mcf7_zscore"], paired["du145_zscore"], s=18, alpha=0.7, color="#2f6fb3")
        ax.axhline(0, linestyle="--", linewidth=0.8, color="0.4")
        ax.axvline(0, linestyle="--", linewidth=0.8, color="0.4")
        ax.set_xlabel("MCF7 z-score")
        ax.set_ylabel("DU145 z-score")
        style_publication_axes(ax, xlabel="MCF7 z-score", ylabel="DU145 z-score")
    fig.tight_layout()
    fig.savefig(output_path, dpi=400, bbox_inches="tight")
    plt.close(fig)


def plot_response_difference_distribution(paired: pd.DataFrame, output_path: Path) -> None:
    """Plot a distribution of the exploratory response-difference statistic."""
    differences = (paired["mcf7_zscore"] - paired["du145_zscore"]).dropna()
    fig, ax = plt.subplots(figsize=(6.0, 4.5), dpi=400)
    if differences.empty:
        ax.text(0.5, 0.5, "No data", ha="center", va="center")
        ax.set_axis_off()
    else:
        ax.hist(differences, bins=30, color="#6b7ae8", edgecolor="black", linewidth=0.4)
        ax.set_xlabel("response_difference")
        ax.set_ylabel("Count")
        style_publication_axes(ax, xlabel="response_difference", ylabel="Count")
    fig.tight_layout()
    fig.savefig(output_path, dpi=400, bbox_inches="tight")
    plt.close(fig)


def plot_scaffold_frequency(scaffold_counts: pd.DataFrame, output_path: Path) -> None:
    """Optional scaffold-frequency plot for the paired valid-structure cohort."""
    fig, ax = plt.subplots(figsize=(7.0, 5.0), dpi=400)
    if scaffold_counts.empty:
        ax.text(0.5, 0.5, "No scaffolds", ha="center", va="center")
        ax.set_axis_off()
    else:
        top = scaffold_counts.head(10).copy()
        ax.bar(top["scaffold_smiles"].astype(str), top["count"], color="#4c78a8")
        ax.set_xlabel("Scaffold")
        ax.set_ylabel("Count")
        ax.tick_params(axis="x", labelrotation=90)
        style_publication_axes(ax, xlabel="Scaffold", ylabel="Count")
    fig.tight_layout()
    fig.savefig(output_path, dpi=400, bbox_inches="tight")
    plt.close(fig)


def write_outputs(config: dict[str, object], logger: logging.Logger, *, summary_table: pd.DataFrame, correlation_table: pd.DataFrame, difference_table: pd.DataFrame, duplicate_audit: pd.DataFrame, duplicate_summary: pd.DataFrame, qc_summary: pd.DataFrame, scaffold_summary: pd.DataFrame, scaffold_counts: pd.DataFrame, paired: pd.DataFrame) -> None:
    """Write all required NCI exploratory tables to the configured output directory."""
    table_dir = Path(config.get("paths", {}).get("tables", "results/tables"))
    figure_dir = Path(config.get("paths", {}).get("figures", "results/figures"))
    table_dir.mkdir(parents=True, exist_ok=True)
    figure_dir.mkdir(parents=True, exist_ok=True)

    table_paths = {
        "nci_response_summary.csv": summary_table,
        "nci_response_correlation.csv": correlation_table,
        "nci_response_difference_summary.csv": difference_table,
        "nci_duplicate_structure_audit.csv": duplicate_audit,
        "nci_duplicate_structure_summary.csv": duplicate_summary,
        "nci_qc_experiment_summary.csv": qc_summary,
        "nci_scaffold_summary.csv": scaffold_summary,
        "nci_scaffold_counts.csv": scaffold_counts,
    }

    for filename, frame in table_paths.items():
        output_path = table_dir / filename
        frame.to_csv(output_path, index=False)
        logger.info("Wrote table: %s", output_path)

    plot_response_distribution(paired["mcf7_zscore"], figure_dir / "nci_mcf7_response_distribution.png", label="MCF7")
    plot_response_distribution(paired["du145_zscore"], figure_dir / "nci_du145_response_distribution.png", label="DU145")
    plot_response_scatter(paired, figure_dir / "nci_mcf7_du145_response_scatter.png")
    plot_response_difference_distribution(paired, figure_dir / "nci_response_difference_distribution.png")

    if not scaffold_counts.empty:
        plot_scaffold_frequency(scaffold_counts, figure_dir / "nci_scaffold_frequency.png")

    logger.info("Wrote figures to %s", figure_dir)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run descriptive NCI-60 exploratory analysis.")
    parser.add_argument("--config", required=True, help="Path to the YAML project configuration file.")
    args = parser.parse_args()

    config = load_project_config(args.config)
    logger = configure_logger(Path(config.get("paths", {}).get("logs", "results/logs")))

    prepared, paired = load_prepared_tables(Path(config.get("paths", {}).get("interim_data", "data/interim")))

    summary_table = compute_response_summary(paired)
    correlation_table = compute_response_correlation(paired)
    difference_table = compute_response_difference_summary(paired)
    duplicate_audit = compute_duplicate_structure_audit(paired)
    duplicate_summary = compute_duplicate_structure_summary(duplicate_audit)
    qc_summary = compute_qc_experiment_summary(paired)
    scaffold_summary, scaffold_counts = compute_scaffold_summary(paired)

    write_outputs(
        config,
        logger,
        summary_table=summary_table,
        correlation_table=correlation_table,
        difference_table=difference_table,
        duplicate_audit=duplicate_audit,
        duplicate_summary=duplicate_summary,
        qc_summary=qc_summary,
        scaffold_summary=scaffold_summary,
        scaffold_counts=scaffold_counts,
        paired=paired,
    )

    logger.info("NCI exploratory analysis completed successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
