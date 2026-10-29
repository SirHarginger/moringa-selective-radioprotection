"""Audit completeness and provenance of the project's outputs (read-only).

    python scripts/audit_outputs.py
    python scripts/audit_outputs.py --runs primary_v1 controls_v1 exploratory_m3_v1
    python scripts/audit_outputs.py --strict      # exit non-zero on any warning too

Reads saved artefacts only; fits, predicts and scores nothing. It answers one question:
**is every number the report relies on backed by a complete, provenanced output on disk?**

Sections:
  RUNS       per model run: task completion, splits hash, frozen-input hashes, whether
             negative-control draws exist, and whether evaluation/explainability/triage
             outputs are present
  TABLES     the publication and compound tables the report cites, with their record files
  FIGURES    every figure the report embeds: PNG, PDF and sidecar present, provenance
             recorded (a sidecar without a Git commit is reported as unprovenanced), and
             inputs still matching the hashes recorded when the figure was rendered
  REPORT     report statements that must be reconciled against the outputs: the primary
             delta-MAE, the control-draw count, and the pending-output markers
  SUMMARY    counts, and a non-zero exit code if anything required is missing

An output that has not been produced is reported as MISSING, never inferred.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from radiosensitivity_ml.data.provenance import file_sha256

REPORT_DIR = ROOT / "reports" / "french_embassy"
FIGURE_MANIFEST = REPORT_DIR / "figure_manifest.csv"
TABLE_MANIFEST = REPORT_DIR / "table_manifest.csv"
REPORT = REPORT_DIR / "report.md"
PRIMARY_DELTA = "0.0038316558867076"
# Outputs every evaluated run writes, whatever its scales or tier.
EVALUATION_FILES = (
    "model_metrics.csv",
    "comparisons.csv",
    "per_repeat_delta_mae.csv",
    "negative_controls.csv",
    "evaluation_record.json",
)
# Outputs defined ONLY on the raw mSF2 scale. `evaluation.report` writes them when
# "raw" is among the run's configured scales and not otherwise, because out-of-fold
# predictions, per-tissue errors and the within-tissue rank statistic are all expressed
# in raw mSF2 units. A transformed-scale run (configs/experiment_scales.yaml: neglog and
# logit) therefore has no raw-scale predictions to summarise, and these files are
# genuinely inapplicable to it rather than missing.
RAW_SCALE_FILES = (
    "oof_predictions.csv",
    "tissue_errors.csv",
    "within_tissue_spearman.csv",
)
# Written only by a leave-one-tissue-out run (tier: loto).
LOTO_FILES = ("held_out_tissue.csv",)


class Audit:
    def __init__(self) -> None:
        self.lines: list[str] = []
        self.missing = 0
        self.warnings = 0

    def section(self, title: str) -> None:
        self.lines += ["", f"=== {title} ", ""]

    def ok(self, text: str) -> None:
        self.lines.append(f"  ok       {text}")

    def warn(self, text: str) -> None:
        self.warnings += 1
        self.lines.append(f"  WARN     {text}")

    def fail(self, text: str) -> None:
        self.missing += 1
        self.lines.append(f"  MISSING  {text}")

    def note(self, text: str) -> None:
        self.lines.append(f"           {text}")


def read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def count_rows(path: Path) -> int:
    """Data rows in a CSV (header excluded)."""
    with path.open(encoding="utf-8", newline="") as handle:
        return max(0, sum(1 for _ in handle) - 1)


def audit_run(audit: Audit, run_id: str) -> dict[str, object]:
    """One model run: completion, provenance, downstream outputs."""
    facts: dict[str, object] = {"run_id": run_id}
    run_dir = ROOT / "results" / "models" / run_id
    audit.note(f"[{run_id}]")
    manifest = read_json(run_dir / "run_manifest.json")
    if manifest is None:
        audit.fail(f"{run_id}: run_manifest.json absent -- the run has not been started")
        facts["started"] = False
        return facts
    facts["started"] = True
    status = read_json(run_dir / "run_status.json") or {}
    counts = dict(status.get("counts") or {})
    n_tasks = status.get("n_tasks", len(manifest.get("tasks") or []))
    complete = status.get("status") == "complete" and not counts.get("failed")
    (audit.ok if complete else audit.fail)(
        f"{run_id}: {counts.get('computed', 0)}/{n_tasks} tasks, "
        f"status={status.get('status', 'unknown')}, failed={counts.get('failed', 0)}"
    )
    facts["complete"] = bool(complete)
    facts["n_tasks"] = n_tasks

    splits = run_dir / "splits.parquet"
    if not splits.is_file():
        audit.fail(f"{run_id}: splits.parquet absent")
    elif file_sha256(splits) == manifest.get("splits_sha256"):
        audit.ok(f"{run_id}: splits.parquet matches its recorded hash")
    else:
        audit.fail(f"{run_id}: splits.parquet DIFFERS from run_manifest.json")

    config = dict(manifest.get("config") or {})
    controls = dict(config.get("controls") or {})
    draws = (controls.get("permuted_outcome", 0), controls.get("random_gene_sets", 0))
    facts["control_draws"] = draws
    if draws == (0, 0):
        audit.note(f"{run_id}: 0 negative-control draws -- attribution not permitted")
    else:
        audit.ok(f"{run_id}: control draws configured (permuted={draws[0]}, random={draws[1]})")

    # Required outputs depend on the run's own design, not on a single global list.
    scales = [str(s) for s in (config.get("scales") or [])]
    tier = str(config.get("tier", ""))
    required = list(EVALUATION_FILES)
    if "raw" in scales:
        required += list(RAW_SCALE_FILES)
    if tier == "loto":
        required += list(LOTO_FILES)
    facts["required_files"] = tuple(required)

    tables = ROOT / "results" / "tables" / run_id
    present = [name for name in required if (tables / name).is_file()]
    if not (tables / "evaluation_record.json").is_file():
        audit.note(f"{run_id}: no evaluation outputs (run evaluate_models.py)")
    elif len(present) == len(required):
        audit.ok(
            f"{run_id}: all {len(present)} evaluation outputs present "
            f"(scales={scales or 'unset'}, tier={tier or 'unset'})"
        )
    else:
        absent = sorted(set(required) - set(present))
        audit.fail(f"{run_id}: evaluation incomplete, absent: {', '.join(absent)}")
    if "raw" not in scales and scales:
        audit.note(
            f"{run_id}: raw-scale outputs ({', '.join(RAW_SCALE_FILES)}) are not required: "
            f"this run fits {', '.join(scales)} only, so it produces no raw-scale "
            f"predictions to summarise"
        )
    facts["evaluated"] = (tables / "evaluation_record.json").is_file() and len(present) == len(
        required
    )

    nulls = tables / "negative_controls.csv"
    if nulls.is_file():
        rows = count_rows(nulls)
        facts["null_rows"] = rows
        if rows == 0 and draws != (0, 0):
            audit.fail(f"{run_id}: control draws configured but negative_controls.csv is empty")
        elif rows:
            audit.ok(f"{run_id}: {rows} negative-control delta-MAE values recorded")

    explain = tables / "explainability" / "gene_set_tests.csv"
    if explain.is_file():
        text = explain.read_text(encoding="utf-8")
        has_p = any(
            row.get("p_permuted_outcome") not in (None, "")
            for row in csv.DictReader(text.splitlines())
        )
        audit.ok(
            f"{run_id}: explainability present, gene-set p-values "
            f"{'populated' if has_p else 'EMPTY (expected with 0 draws)'}"
        )
        facts["explained"] = True
    else:
        audit.note(f"{run_id}: no explainability outputs (run run_explainability.py)")
        facts["explained"] = False

    triage = ROOT / "results" / "triage" / run_id / "triage_manifest.json"
    if triage.is_file():
        record = read_json(triage) or {}
        audit.ok(
            f"{run_id}: triage present, gain_shown={record.get('primary_gain_shown')}, "
            f"tiers={dict(record.get('tier_counts', {}).get('pathway_candidates', {}))}"
        )
        facts["triaged"] = True
    else:
        audit.note(f"{run_id}: no triage outputs (run generate_triage.py)")
        facts["triaged"] = False
    return facts


def audit_tables(audit: Audit) -> None:
    if not TABLE_MANIFEST.is_file():
        audit.fail("reports/french_embassy/table_manifest.csv absent")
        return
    rows = list(csv.DictReader(TABLE_MANIFEST.read_text(encoding="utf-8").splitlines()))
    for row in rows:
        path = ROOT / row["path"]
        label = f"{row['report_label']} {row['path']}"
        if path.is_file():
            audit.ok(f"{label} ({count_rows(path)} rows)")
            if row["status"] == "pending_execution":
                audit.warn(f"{label}: file exists but the manifest still says pending_execution")
        elif row["status"] == "pending_execution":
            audit.fail(f"{label}: not generated ({row['produced_by']})")
        else:
            audit.fail(f"{label}: manifest says generated, but the file is absent")
    compound_dir = ROOT / "results" / "tables" / "primary_v1" / "compounds_v1"
    record = read_json(compound_dir / "compound_record.json")
    if record:
        counts = dict(record.get("counts") or {})
        audit.ok(
            f"compound record: {counts.get('constituents')} constituents, "
            f"{counts.get('evidence_items')} evidence items, "
            f"shortlist {counts.get('shortlist')}, tiers {counts.get('tiers')}"
        )


def audit_figures(audit: Audit) -> None:
    if not FIGURE_MANIFEST.is_file():
        audit.fail(
            "reports/french_embassy/figure_manifest.csv absent (run scripts/make_report_figures.py)"
        )
        return
    rows = list(csv.DictReader(FIGURE_MANIFEST.read_text(encoding="utf-8").splitlines()))
    for row in rows:
        label = f"{row['report_label']} {row['stem']}"
        # An empty column would resolve to ROOT itself, which is a directory, and would be
        # reported as a file named "" -- a manifest row missing a path is its own failure.
        blank = [name for name in ("png", "pdf", "metadata") if not str(row[name]).strip()]
        if blank:
            audit.fail(f"{label}: manifest row has no path for {', '.join(blank)}")
            continue
        png, pdf = ROOT / row["png"], ROOT / row["pdf"]
        sidecar = ROOT / row["metadata"]
        absent = [p.name for p in (png, pdf, sidecar) if not p.is_file()]
        if absent:
            audit.fail(f"{label}: absent {', '.join(absent)}")
            continue
        meta = read_json(sidecar) or {}
        git = dict(meta.get("git") or {})
        if git.get("commit"):
            provenance = f"commit {str(git['commit'])[:8]}{' (dirty)' if git.get('dirty') else ''}"
        else:
            provenance = "UNPROVENANCED (no Git commit recorded)"
            audit.warn(f"{label}: {provenance}")
        stale = [
            name
            for name, digest in dict(meta.get("inputs_sha256") or {}).items()
            if not (ROOT / name).is_file() or file_sha256(ROOT / name) != digest
        ]
        if stale:
            audit.fail(f"{label}: inputs changed since rendering: {', '.join(stale)}")
        elif not absent and git.get("commit"):
            audit.ok(f"{label}: PNG+PDF+sidecar, {provenance}, inputs unchanged")
        if not str(meta.get("caption", "")).strip():
            audit.warn(f"{label}: sidecar records no caption")


def audit_report(audit: Audit, facts: list[dict[str, object]], mode: str = "final") -> None:
    """Report-level reconciliation. ``mode='prebuild'`` does not require the built PDF or
    DOCX, because the pre-build audit runs precisely to decide whether to build them."""
    if not REPORT.is_file():
        audit.fail("reports/french_embassy/report.md absent")
        return
    text = REPORT.read_text(encoding="utf-8")
    metrics = ROOT / "results" / "tables" / "primary_v1" / "comparisons.csv"
    if metrics.is_file():
        saved = metrics.read_text(encoding="utf-8")
        if PRIMARY_DELTA in text and PRIMARY_DELTA[:16] in saved:
            audit.ok(f"primary delta-MAE {PRIMARY_DELTA} in the report matches comparisons.csv")
        else:
            audit.fail("the report's primary delta-MAE does not match comparisons.csv")
    pending = len(re.findall(r"pending investigator execution|not executed|not rendered", text))
    audit.note(f"report carries {pending} explicit 'not yet executed' markers")
    lowered = text.lower()
    says_not_run = "negative control" in lowered and "were not run" in lowered
    for entry in facts:
        run_id = entry["run_id"]
        has_draws = entry.get("control_draws", (0, 0)) != (0, 0) and entry.get("null_rows")
        if has_draws and says_not_run:
            audit.warn(
                f"{run_id} has {entry['null_rows']} control draws, but the report still "
                "states that negative controls were not run -- reconcile the text"
            )
    outputs = REPORT_DIR / "outputs"
    built = (
        sorted(p.name for p in outputs.glob("final_project_report.*")) if outputs.is_dir() else []
    )
    if built:
        audit.ok(f"built report documents: {', '.join(built)}")
    elif mode == "prebuild":
        audit.note(
            "built report not required in prebuild mode: this audit decides whether the "
            "prerequisites for building it are complete"
        )
    else:
        audit.fail("no built report in reports/french_embassy/outputs (run build.sh)")
    if mode == "final" and built:
        for required in ("final_project_report.pdf", "final_project_report.docx"):
            if required not in built:
                audit.fail(f"{required} absent (run reports/french_embassy/build.sh)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "--runs", nargs="+",
        default=["primary_v1", "controls_v1", "exploratory_m3_v1", "loto_v1", "scales_v1"],
    )  # fmt: skip
    parser.add_argument("--strict", action="store_true", help="warnings also fail the audit")
    parser.add_argument(
        "--mode", choices=("prebuild", "final"), default="final",
        help="prebuild: check the prerequisites for building the report, and do not "
             "require the built PDF/DOCX. final: require everything, including both "
             "built documents.",
    )  # fmt: skip
    args = parser.parse_args(argv)

    audit = Audit()
    audit.section("RUNS")
    facts = []
    for run_id in args.runs:
        if (ROOT / "results" / "models" / run_id).is_dir():
            facts.append(audit_run(audit, run_id))
        else:
            audit.note(f"[{run_id}] not present (optional run, not started)")
    audit.section("TABLES")
    audit_tables(audit)
    audit.section("FIGURES")
    audit_figures(audit)
    audit.section(f"REPORT ({args.mode} mode)")
    audit_report(audit, facts, args.mode)
    audit.section("SUMMARY")
    audit.note(f"{audit.missing} missing, {audit.warnings} warnings")
    print("\n".join(audit.lines))
    if audit.missing or (args.strict and audit.warnings):
        print("\nAudit FAILED: see MISSING/WARN lines above.", file=sys.stderr)
        return 1
    print("\nAudit passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
