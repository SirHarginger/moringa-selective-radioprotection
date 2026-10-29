"""Regression tests for the final-integration defects (2026-10-22).

SYNTHETIC DATA ONLY: manifests, records and tables are invented in tmp_path. Nothing is
fitted and no real run is read (no ``model_fit`` marker).

Defects pinned down here:
1. the audit demanded raw-scale outputs from a run that fits no raw scale, so `scales_v1`
   was reported incomplete although `evaluation.report` correctly never writes them;
2. the audit required a built report even when run to decide whether to build it;
3. publication tables could not be regenerated: an existing, matching write-once folder
   raised FileExistsError instead of being recognised.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]


def load_script(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def audit_script() -> ModuleType:
    return load_script("audit_outputs")


@pytest.fixture(scope="module")
def tables_script() -> ModuleType:
    return load_script("make_publication_tables")


# The real Audit interface (scripts/audit_outputs.py): it accumulates formatted strings in
# `.lines` and counts outcomes in `.missing` and `.warnings`. It has no render()/rows/
# failed -- those belong to the Report class in verify_run_consistency.py. These two
# helpers read the genuine attributes rather than adding methods to the audit.


def text_of(audit: object) -> str:
    return "\n".join(audit.lines)  # type: ignore[attr-defined]


def failure_lines(audit: object) -> list[str]:
    return [line for line in audit.lines if line.strip().startswith("MISSING")]  # type: ignore[attr-defined]


# --------------------------------------------- 1  scale-aware evaluation requirements


def write_run(
    root: Path, run_id: str, scales: list[str], tier: str = "within", files: tuple[str, ...] = ()
) -> None:
    """SYNTHETIC run folder: splits table, manifest, status and the named outputs.

    The splits table is written first and its real SHA-256 recorded in the manifest, so
    the audit's provenance check passes and a test fails only on the property it targets.
    """
    from radiosensitivity_ml.data.provenance import file_sha256

    run_dir = root / "results" / "models" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "repeat": [0, 0],
            "outer_fold": [0, 0],
            "row_number": [0, 1],
            "role": ["train", "test"],
            "inner_fold": [0, -1],
        }
    ).to_parquet(run_dir / "splits.parquet", index=False)
    (run_dir / "run_manifest.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "config": {"scales": scales, "tier": tier, "controls": {}},
                "splits_sha256": file_sha256(run_dir / "splits.parquet"),
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "run_status.json").write_text(
        json.dumps({"status": "complete", "n_tasks": 1, "counts": {"computed": 1, "failed": 0}}),
        encoding="utf-8",
    )
    tables = root / "results" / "tables" / run_id
    tables.mkdir(parents=True, exist_ok=True)
    for name in files:
        (tables / name).write_text("a,b\n1,2\n", encoding="utf-8")


ALWAYS = (
    "model_metrics.csv",
    "comparisons.csv",
    "per_repeat_delta_mae.csv",
    "negative_controls.csv",
    "evaluation_record.json",
)
RAW_ONLY = ("oof_predictions.csv", "tissue_errors.csv", "within_tissue_spearman.csv")


def test_required_files_exclude_raw_outputs_for_a_transformed_scale_run(
    audit_script: ModuleType,
) -> None:
    """`evaluation.report` writes the raw-scale outputs only when 'raw' is configured, so
    a neglog/logit run must not be required to have them."""
    assert set(audit_script.RAW_SCALE_FILES) == set(RAW_ONLY)
    assert not set(audit_script.EVALUATION_FILES) & set(RAW_ONLY), (
        "raw-scale outputs must not be in the always-required list"
    )


def test_a_transformed_scale_run_audits_as_complete(
    audit_script: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The scales_v1 case: complete with no raw-scale outputs at all."""
    monkeypatch.setattr(audit_script, "ROOT", tmp_path)
    write_run(tmp_path, "scales_v1", ["neglog", "logit"], files=ALWAYS)
    audit = audit_script.Audit()
    facts = audit_script.audit_run(audit, "scales_v1")
    rendered = text_of(audit)
    assert facts["evaluated"] is True, rendered
    assert audit.missing == 0, rendered
    assert "are not required" in rendered, "the exemption must be stated, not silent"
    assert not any("oof_predictions" in line for line in failure_lines(audit)), rendered


def test_a_raw_scale_run_still_requires_the_raw_outputs(
    audit_script: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fail-closed: the exemption applies only to runs with no raw scale."""
    monkeypatch.setattr(audit_script, "ROOT", tmp_path)
    write_run(tmp_path, "primary_v1", ["raw"], files=ALWAYS)
    audit = audit_script.Audit()
    facts = audit_script.audit_run(audit, "primary_v1")
    rendered = text_of(audit)
    assert facts["evaluated"] is False, rendered
    assert audit.missing >= 1, rendered
    assert any("evaluation incomplete" in line for line in failure_lines(audit)), rendered
    for name in RAW_ONLY:
        assert name in rendered, f"{name} must be named as absent"


def test_a_loto_run_requires_its_held_out_tissue_table(
    audit_script: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(audit_script, "ROOT", tmp_path)
    write_run(tmp_path, "loto_v1", ["raw"], tier="loto", files=(*ALWAYS, *RAW_ONLY))
    audit = audit_script.Audit()
    facts = audit_script.audit_run(audit, "loto_v1")
    rendered = text_of(audit)
    assert facts["evaluated"] is False, rendered
    assert audit.missing >= 1 and "held_out_tissue.csv" in rendered, rendered

    write_run(
        tmp_path, "loto_v1", ["raw"], tier="loto",
        files=(*ALWAYS, *RAW_ONLY, "held_out_tissue.csv"),
    )  # fmt: skip
    complete = audit_script.Audit()
    facts = audit_script.audit_run(complete, "loto_v1")
    assert facts["evaluated"] is True, text_of(complete)
    assert complete.missing == 0, text_of(complete)


# ------------------------------------------------------ 2  prebuild vs final audit mode


def synthetic_report_project(
    audit_script: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Redirect every path the report audit reads into tmp_path.

    ROOT must be redirected too, not only REPORT_DIR: `audit_report` reconciles the
    report's primary delta-MAE against ROOT/results/tables/primary_v1/comparisons.csv, so
    leaving ROOT pointing at the real repository would compare the real saved value with a
    synthetic report. A matching pair is written here, so that reconciliation is genuinely
    exercised and passes, and the test then isolates the prebuild/final mode behaviour.
    """
    monkeypatch.setattr(audit_script, "ROOT", tmp_path)
    monkeypatch.setattr(audit_script, "REPORT_DIR", tmp_path)
    monkeypatch.setattr(audit_script, "REPORT", tmp_path / "report.md")
    monkeypatch.setattr(audit_script, "TABLE_MANIFEST", tmp_path / "table_manifest.csv")
    monkeypatch.setattr(audit_script, "FIGURE_MANIFEST", tmp_path / "figure_manifest.csv")
    delta = audit_script.PRIMARY_DELTA
    (tmp_path / "report.md").write_text(
        f"# synthetic\n\nThe primary estimate is {delta} mSF2 units.\n", encoding="utf-8"
    )
    comparisons = tmp_path / "results" / "tables" / "primary_v1"
    comparisons.mkdir(parents=True, exist_ok=True)
    (comparisons / "comparisons.csv").write_text(
        f"comparison,delta_mae\nprimary,{delta}\n", encoding="utf-8"
    )


def test_prebuild_mode_does_not_require_a_built_report(
    audit_script: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The pre-build audit decides whether to build, so it cannot demand the output."""
    synthetic_report_project(audit_script, tmp_path, monkeypatch)
    audit = audit_script.Audit()
    audit_script.audit_report(audit, [], mode="prebuild")
    rendered = text_of(audit)
    assert audit.missing == 0, rendered
    assert "not required in prebuild mode" in rendered
    # the delta-MAE reconciliation still ran, and passed
    assert "matches comparisons.csv" in rendered


def test_final_mode_requires_a_built_report(
    audit_script: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    synthetic_report_project(audit_script, tmp_path, monkeypatch)
    audit = audit_script.Audit()
    audit_script.audit_report(audit, [], mode="final")
    rendered = text_of(audit)
    assert audit.missing >= 1, rendered
    assert any("no built report" in line for line in failure_lines(audit)), rendered


def test_final_mode_requires_both_documents(
    audit_script: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    synthetic_report_project(audit_script, tmp_path, monkeypatch)
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    (outputs / "final_project_report.pdf").write_text("pdf", encoding="utf-8")
    audit = audit_script.Audit()
    audit_script.audit_report(audit, [], mode="final")
    rendered = text_of(audit)
    assert audit.missing >= 1, rendered
    assert any("final_project_report.docx" in line for line in failure_lines(audit)), rendered
    assert "final_project_report.pdf" in rendered, "the built PDF must be acknowledged"


# ------------------------------------------ 3  reuse of a matching write-once folder


def publication_record(**overrides: object) -> dict:
    record = {
        "part": "core",
        "run_id": "primary_v1",
        "experiment_config_sha256": "c" * 64,
        "publication_config": {"version": 1, "min_components": 10},
        "source_sha256": {"model_metrics": "m" * 64},
        "code_sha256": {"a.py": "1" * 64},
    }
    record.update(overrides)
    return record


def test_a_matching_folder_is_reused_not_overwritten(
    tables_script: ModuleType, tmp_path: Path
) -> None:
    """The FileExistsError case: a complete folder built from these inputs is reused."""
    out = tmp_path / "publication_v1"
    out.mkdir()
    record = publication_record()
    for name in tables_script.EXPECTED_FILES["core"]:
        (out / name).write_text("x", encoding="utf-8")
    (out / "publication_record.json").write_text(json.dumps(record), encoding="utf-8")
    before = {p.name: p.read_bytes() for p in out.iterdir()}

    assert tables_script.reuse_existing(out, publication_record(), "core") is True
    after = {p.name: p.read_bytes() for p in out.iterdir()}
    assert before == after, "a reused folder must not be rewritten"


def test_a_code_change_alone_still_reuses_but_says_so(
    tables_script: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "publication_v1"
    out.mkdir()
    for name in tables_script.EXPECTED_FILES["core"]:
        (out / name).write_text("x", encoding="utf-8")
    (out / "publication_record.json").write_text(json.dumps(publication_record()), encoding="utf-8")
    assert tables_script.reuse_existing(
        out, publication_record(code_sha256={"a.py": "9" * 64}), "core"
    )
    assert "the package code has changed" in capsys.readouterr().err


@pytest.mark.parametrize(
    "overrides",
    [
        {"source_sha256": {"model_metrics": "z" * 64}},
        {"experiment_config_sha256": "z" * 64},
        {"publication_config": {"version": 1, "min_components": 5}},
        {"run_id": "another_run"},
    ],
)
def test_a_stale_folder_fails_closed(
    tables_script: ModuleType, tmp_path: Path, overrides: dict
) -> None:
    """Fail-closed: different inputs or settings must never be silently reused."""
    out = tmp_path / "publication_v1"
    out.mkdir()
    for name in tables_script.EXPECTED_FILES["core"]:
        (out / name).write_text("x", encoding="utf-8")
    (out / "publication_record.json").write_text(
        json.dumps(publication_record(**overrides)), encoding="utf-8"
    )
    with pytest.raises(tables_script.StaleOutputError, match="different inputs or settings"):
        tables_script.reuse_existing(out, publication_record(), "core")


def test_an_incomplete_folder_fails_closed(tables_script: ModuleType, tmp_path: Path) -> None:
    out = tmp_path / "publication_v1"
    out.mkdir()
    (out / "publication_record.json").write_text(json.dumps(publication_record()), encoding="utf-8")
    with pytest.raises(tables_script.StaleOutputError, match="incomplete"):
        tables_script.reuse_existing(out, publication_record(), "core")


def test_a_folder_without_a_record_fails_closed(tables_script: ModuleType, tmp_path: Path) -> None:
    out = tmp_path / "publication_v1"
    out.mkdir()
    (out / "table_1_dataset_composition.csv").write_text("x", encoding="utf-8")
    with pytest.raises(tables_script.StaleOutputError, match="cannot be verified"):
        tables_script.reuse_existing(out, publication_record(), "core")
