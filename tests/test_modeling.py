from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from moringa_radioprotection.modeling import (
    assess_split_leakage,
    assign_scaffold_split,
    attach_reconstruction_qc,
    build_cancer_modeling_table,
    build_discordant_duplicate_audit,
    build_duplicate_resolution_table,
    build_secondary_zscore_discordant_audit,
    summarize_scaffold_split,
    validate_dependent_artifact_alignment,
)


def _write_modeling_inputs(interim_dir: Path, raw_summary: pd.DataFrame) -> dict:
    interim_dir.mkdir(parents=True)
    paired = pd.DataFrame(
        {
            "nsc_id": ["NSC101"],
            "drug_name": ["compound-a"],
            "pubchem_sid": [1001],
            "canonical_smiles": ["CCO"],
            "inchikey": ["LFQSCWFLJHTTHZ-UHFFFAOYSA-N"],
            "mcf7_zscore": [0.5],
            "du145_zscore": [-0.5],
            "total_experiments": [2],
            "total_after_quality_control": [2],
        }
    )
    paired.to_csv(interim_dir / "nci_paired_response.csv", index=False)
    raw_summary.to_csv(interim_dir / "nci_raw_activity_summary.csv", index=False)
    return {"paths": {"interim_data": str(interim_dir)}}


def test_modeling_merge_ignores_missing_raw_summary_keys(tmp_path):
    raw_summary = pd.DataFrame(
        {
            "nsc_id": ["NSC101", None, None],
            "median_raw_neglog10_gi50_mcf7": [5.5, 1.0, 2.0],
            "median_raw_neglog10_gi50_du145": [6.5, 3.0, 4.0],
        }
    )
    config = _write_modeling_inputs(tmp_path / "interim", raw_summary)

    modeling, filter_report = build_cancer_modeling_table(config)

    assert modeling["nsc_id"].tolist() == ["NSC101"]
    assert modeling["mcf7_raw_neglog10_gi50"].tolist() == [5.5]
    assert modeling["du145_raw_neglog10_gi50"].tolist() == [6.5]
    assert filter_report.iloc[-1].to_dict() == {"step": "final_modeling_cohort", "n_records": 1}


def test_modeling_merge_rejects_duplicate_valid_raw_summary_keys(tmp_path):
    raw_summary = pd.DataFrame(
        {
            "nsc_id": ["NSC101", "NSC101"],
            "median_raw_neglog10_gi50_mcf7": [5.5, 5.6],
            "median_raw_neglog10_gi50_du145": [6.5, 6.6],
        }
    )
    config = _write_modeling_inputs(tmp_path / "interim", raw_summary)

    with pytest.raises(ValueError, match="duplicate NSC identifiers: NSC101"):
        build_cancer_modeling_table(config)


def test_attach_reconstruction_qc_joins_target_columns_without_suffixes(tmp_path):
    table_dir = tmp_path / "tables"
    table_dir.mkdir()
    pd.DataFrame(
        {
            "nsc_id": ["NSC101", "NSC101"],
            "target": ["MCF7", "DU145"],
            "abs_error_ddof0": [0.30, 0.10],
            "abs_error_ddof1": [0.29, 0.09],
        }
    ).to_csv(table_dir / "nci_raw_zscore_reconstruction.csv", index=False)
    frame = pd.DataFrame({"nsc_id": ["NSC101"]})
    config = {
        "paths": {"tables": str(table_dir)},
        "reconstruction_error_thresholds": {"gt_0_25": 0.25},
    }

    result = attach_reconstruction_qc(frame, config)

    assert result.loc[0, "mcf7_zscore_reconstruction_abs_error"] == 0.30
    assert result.loc[0, "du145_zscore_reconstruction_abs_error"] == 0.10
    assert bool(result.loc[0, "reconstruction_error_gt_0_25"]) is True


def test_primary_absolute_and_secondary_zscore_discordance_are_independent():
    modeling = pd.DataFrame(
        {
            "nsc_id": ["1", "2", "3", "4", "5", "6", "7"],
            "canonical_smiles": ["CCO", "CCO", "CCN", "CCN", "CCC", "CCC", "CCCC"],
            "inchikey": [
                "CONSISTENT",
                "CONSISTENT",
                "PRIMARY_DISCORDANT",
                "PRIMARY_DISCORDANT",
                "SECONDARY_ONLY",
                "SECONDARY_ONLY",
                "SINGLE",
            ],
            "mcf7_raw_neglog10_gi50": [5.0, 5.4, 2.0, 5.5, 5.0, 5.2, 4.0],
            "du145_raw_neglog10_gi50": [6.0, 6.2, 3.0, 3.1, 6.0, 6.2, 4.0],
            "mcf7_zscore": [0.1, 0.2, 0.0, 0.1, -1.0, 1.0, 0.0],
            "du145_zscore": [0.3, 0.4, 0.0, 0.1, 0.1, 0.2, 0.0],
        }
    )

    resolution, primary = build_duplicate_resolution_table(
        modeling,
        {
            "duplicate_absolute_discordance_threshold": 1.0,
            "duplicate_secondary_zscore_discordance_threshold": 1.0,
        },
    )
    primary_discordant = build_discordant_duplicate_audit(resolution)
    secondary_discordant = build_secondary_zscore_discordant_audit(resolution)

    assert len(resolution) == 4
    assert set(primary["source_nsc_ids"]) == {"1; 2", "5; 6", "7"}
    assert primary["primary_absolute_response_discordant"].eq(False).all()
    secondary_only = primary.loc[primary["source_nsc_ids"] == "5; 6"].iloc[0]
    assert bool(secondary_only["secondary_zscore_response_discordant"]) is True
    assert secondary_only["mcf7_raw_neglog10_gi50"] == 5.1
    consistent = primary.loc[primary["source_nsc_ids"] == "1; 2"].iloc[0]
    assert consistent["mcf7_raw_neglog10_gi50"] == 5.2
    assert consistent["du145_raw_neglog10_gi50"] == 6.1
    assert primary_discordant[["source_nsc_count", "source_nsc_ids"]].values.tolist() == [[2, "3; 4"]]
    assert primary_discordant.loc[0, "mcf7_raw_range"] == 3.5
    assert secondary_discordant[["source_nsc_count", "source_nsc_ids"]].values.tolist() == [[2, "5; 6"]]
    assert secondary_discordant.loc[0, "mcf7_raw_range"] == pytest.approx(0.2)
    assert secondary_discordant.loc[0, "mcf7_zscore_range"] == 2.0
    assert "duplicate_response_discordant" not in resolution.columns


def _synthetic_scaffold_cohort() -> pd.DataFrame:
    molecule_count = 30
    return pd.DataFrame(
        {
            "chemical_group_id": [f"chem_{index:02d}" for index in range(molecule_count)],
            "source_nsc_ids": [str(index) for index in range(molecule_count)],
            "canonical_smiles": ["C" * (index + 1) for index in range(molecule_count)],
            "mcf7_raw_neglog10_gi50": np.linspace(4.0, 8.0, molecule_count),
            "du145_raw_neglog10_gi50": np.linspace(8.0, 4.0, molecule_count),
            "mcf7_at_lower_boundary": [True] + [False] * (molecule_count - 1),
            "du145_at_lower_boundary": [False] * (molecule_count - 1) + [True],
            "mcf7_at_upper_boundary": [False] * (molecule_count - 1) + [True],
            "du145_at_upper_boundary": [True] + [False] * (molecule_count - 1),
            "reconstruction_error_gt_0_25": [False, True] * (molecule_count // 2),
        }
    )


def _split_config() -> dict:
    return {
        "project": {"random_seed": 42},
        "validation": {
            "train_fraction": 0.80,
            "validation_fraction": 0.10,
            "test_fraction": 0.10,
        },
        "reconstruction_error_thresholds": {"gt_0_25": 0.25},
    }


def test_scaffold_split_is_deterministic_diverse_and_target_independent():
    cohort = _synthetic_scaffold_cohort()

    first = assign_scaffold_split(cohort, _split_config())
    changed_targets = cohort.copy()
    changed_targets["mcf7_raw_neglog10_gi50"] = -999.0
    changed_targets["du145_raw_neglog10_gi50"] = 999.0
    second = assign_scaffold_split(changed_targets, _split_config())

    pd.testing.assert_frame_equal(first, second)
    assert first.groupby("split").size().to_dict() == {"test": 3, "train": 24, "validation": 3}
    assert first.groupby("split")["scaffold"].nunique().to_dict() == {
        "test": 3,
        "train": 24,
        "validation": 3,
    }
    assert first["scaffold_is_fallback"].all()
    assert set(first["scaffold_fallback_type"]) == {"canonical_smiles"}
    assert not assess_split_leakage(first)["forbidden_overlap_detected"].any()


def test_split_summary_reports_balance_fallbacks_boundaries_and_qc():
    cohort = _synthetic_scaffold_cohort()
    split = assign_scaffold_split(cohort, _split_config())

    summary = summarize_scaffold_split(split, cohort, _split_config())

    expected_columns = {
        "molecule_fraction",
        "scaffold_fraction",
        "bemis_murcko_scaffolds",
        "fallback_scaffold_molecules",
        "mcf7_boundary_lower_proportion",
        "du145_boundary_lower_proportion",
        "mcf7_boundary_upper_proportion",
        "du145_boundary_upper_proportion",
        "reconstruction_error_gt_0_25_proportion",
    }
    assert expected_columns.issubset(summary.columns)
    assert np.isclose(summary["molecule_fraction"].sum(), 1.0)
    assert np.isclose(summary["scaffold_fraction"].sum(), 1.0)
    assert summary["fallback_scaffold_molecules"].sum() == len(cohort)


def test_artifact_alignment_guard_rejects_reordered_ids():
    unique = pd.DataFrame({"chemical_group_id": ["chem_a", "chem_b"]})
    descriptors = pd.DataFrame({"chemical_group_id": ["chem_a", "chem_b"]})
    fingerprint_map = pd.DataFrame(
        {"row_index": [0, 1], "chemical_group_id": ["chem_a", "chem_b"]}
    )
    split = pd.DataFrame({"chemical_group_id": ["chem_b", "chem_a"]})

    with pytest.raises(ValueError, match="scaffold split chemical_group_id order"):
        validate_dependent_artifact_alignment(unique, descriptors, fingerprint_map, split)
