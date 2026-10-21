"""Tests for the post-evaluation triage rules and report (no model fitting).

SYNTHETIC SOFTWARE-TEST DATA ONLY: every table, identifier, importance, coefficient
share, prediction and outcome below is invented to exercise the code. Nothing here is a
scientific observation and nothing may appear in a manuscript.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from radiosensitivity_ml.config import experiment_from_mapping
from radiosensitivity_ml.triage import rules as tr
from radiosensitivity_ml.triage.report import generate_triage, triage_from_mapping

PATHWAY = tr.PathwayRules(
    strong=0.9,
    moderate=0.75,
    exploratory=0.5,
    max_share_zero=0.5,
    correlation_flag=0.8,
    min_null_draws=1000,
)
LINES = tr.CellLineRules(min_repeats=2, high_percentile=0.95, flag_percentile=0.9)
FITS = 4  # SYNTHETIC: 2 repeats x 2 folds


def synthetic_pathway_tables() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """SYNTHETIC: S_STRONG stable and significant; S_ONE one null; S_WEAK; S_NONE."""
    sets = ["S_STRONG", "S_ONE", "S_WEAK", "S_NONE"]
    columns = [f"real|r{r}|f{f}" for r in range(2) for f in range(2)] + ["perm_0001|r0|f0"]
    importance = pd.DataFrame(
        [
            [0.02, 0.03, 0.02, 0.04, 9.0],  # the control column must be ignored
            [0.01, 0.02, 0.01, 0.01, 9.0],
            [0.01, 0.01, -0.01, 0.0, 9.0],
            [-0.01, -0.02, 0.0, -0.01, 9.0],
        ],
        index=sets,
        columns=columns,
    )
    signs = pd.DataFrame(
        {
            "share_positive": [1.0, 0.8, 0.5, 0.1],
            "share_negative": [0.0, 0.0, 0.1, 0.1],
            "share_zero": [0.0, 0.2, 0.4, 0.8],
        },
        index=sets,
    )
    tests = pd.DataFrame(
        {
            "tested_importance_repeat0": [0.025, 0.015, 0.0, -0.015],
            "n_draws_permuted_outcome": 1999,
            "n_draws_random_sets": 1999,
            "p_permuted_outcome": [0.001, 0.001, 0.5, 0.9],
            "p_random_sets": [0.001, 0.4, 0.5, 0.9],
            "bh_permuted_outcome": [True, True, False, False],
            "bh_random_sets": [True, False, False, False],
            "attribution_permitted": [True, False, False, False],
        },
        index=sets,
    )
    correlation = pd.DataFrame(np.eye(4), index=sets, columns=sets)
    correlation.loc["S_STRONG", "S_ONE"] = correlation.loc["S_ONE", "S_STRONG"] = 0.85
    return importance, signs, tests, correlation


def test_pathway_tiers_follow_the_prespecified_rules() -> None:
    evidence = tr.pathway_evidence(*synthetic_pathway_tables())
    assert evidence.loc["S_STRONG", "n_real_tasks"] == 4  # control column excluded
    ranked = tr.rank_pathways(evidence, PATHWAY, gate_passed=True, required_fits=FITS)
    ranked = ranked.set_index("gene_set")
    assert ranked.loc["S_STRONG", "tier"] == "A"
    assert ranked.loc["S_ONE", "tier"] == "B"
    assert ranked.loc["S_WEAK", "tier"] == "C"
    assert ranked.loc["S_NONE", "tier"] == "not_prioritised"
    assert "S_ONE" in ranked.loc["S_STRONG", "caveat"]  # correlated scores flagged
    assert "positive coefficient sign" in ranked.loc["S_STRONG", "tier_reason"]
    assert ranked.loc["S_ONE", "nulls_passed"] == "permuted"
    assert list(ranked["rank"]) == [1, 2, 3, 4]
    # only tier A may be called an in-model association
    assert ranked.loc["S_STRONG", "claim_level"].startswith("in-model association")
    assert ranked.loc["S_ONE", "claim_level"].startswith("suggestive")
    assert ranked.loc["S_WEAK", "claim_level"] == "exploratory"


def test_tier_b_needs_the_permuted_outcome_null() -> None:
    importance, signs, tests, correlation = synthetic_pathway_tables()
    tests.loc["S_ONE", ["bh_permuted_outcome", "bh_random_sets"]] = [False, True]
    evidence = tr.pathway_evidence(importance, signs, tests, correlation)
    ranked = tr.rank_pathways(evidence, PATHWAY, True, FITS).set_index("gene_set")
    assert ranked.loc["S_ONE", "tier"] == "C"
    assert ranked.loc["S_ONE", "nulls_passed"] == "random"


def test_pathways_are_capped_at_c_without_a_primary_gain() -> None:
    evidence = tr.pathway_evidence(*synthetic_pathway_tables())
    ranked = tr.rank_pathways(evidence, PATHWAY, gate_passed=False, required_fits=FITS)
    assert set(ranked["tier"]) <= {"C", "not_prioritised", "not_rankable"}
    assert set(ranked["claim_level"]) == {"exploratory"}


def test_pathways_are_capped_at_c_with_too_few_null_draws() -> None:
    importance, signs, tests, correlation = synthetic_pathway_tables()
    tests["n_draws_random_sets"] = 999
    ranked = tr.rank_pathways(
        tr.pathway_evidence(importance, signs, tests, correlation), PATHWAY, True, FITS
    ).set_index("gene_set")
    assert ranked.loc["S_STRONG", "tier"] == "C"
    assert "completed null draws" in ranked.loc["S_STRONG", "tier_reason"]


def test_too_few_fits_are_not_rankable() -> None:
    importance, signs, tests, correlation = synthetic_pathway_tables()
    sparse = importance[["real|r0|f0", "real|r0|f1"]]
    evidence = tr.pathway_evidence(sparse, signs, tests, correlation)
    ranked = tr.rank_pathways(evidence, PATHWAY, True, FITS)
    assert set(ranked["tier"]) == {"not_rankable"}


def test_criteria_text_states_the_configured_thresholds() -> None:
    text = tr.criteria_text(PATHWAY, LINES)
    assert "0.90" in text["pathway_A"] and "0.75" in text["pathway_B"]
    assert "1000" in text["pathway_gate"] and "permuted-" in text["pathway_B"]
    assert "95th" in text["lines_A"] and "90th" in text["lines_B"]
    assert "range" not in " ".join(text.values()).lower()  # no interval-like criterion


def test_external_evidence_is_shown_but_never_reranks() -> None:
    ranked = tr.rank_pathways(tr.pathway_evidence(*synthetic_pathway_tables()), PATHWAY, True, FITS)
    external = pd.DataFrame(
        {"gene_set": ["S_NONE"], "evidence_summary": ["SYNTHETIC note"], "citation": ["doi:0/0"]}
    )
    merged = tr.attach_external_evidence(ranked, external)
    pd.testing.assert_series_equal(merged["tier"], ranked["tier"])
    assert merged.set_index("gene_set").loc["S_NONE", "external_citation"] == "doi:0/0"
    with pytest.raises(tr.TriageError):
        tr.attach_external_evidence(ranked, external.assign(citation=[""]))
    assert set(tr.attach_external_evidence(ranked, None)["external_evidence"]) == {"not assessed"}


def synthetic_cell_lines(n: int = 40) -> tuple[pd.DataFrame, pd.DataFrame]:
    """SYNTHETIC oof table (M1, M2) and metadata. Row 2 has a large error under both."""
    rows = np.arange(2, n + 2)
    rng = np.random.default_rng(0)
    y = rng.uniform(0.3, 0.6, n)
    frames = []
    for model, shift in (("M1", 0.0), ("M2", 0.01)):
        pred = y + rng.normal(0, 0.02, n) + shift
        pred[0] = y[0] + 0.4  # far off under both models
        frames.append(
            pd.DataFrame(
                {
                    "model_id": model,
                    "row_number": rows,
                    "y_true": y,
                    "y_pred": pred,
                    "y_pred_sd": 0.01,
                    "y_pred_min": pred - 0.02,
                    "y_pred_max": pred + 0.02,
                    "n_repeats": 3,
                }
            )
        )
    meta = pd.DataFrame(
        {
            "depmap_id": [f"ACH-9{r:05d}" for r in rows],
            "lineage": "L_A",
            "component_id": [f"G:{r}" for r in rows],
            "component_records": 1,
            "related_flag_sources": "",
            "stranded": False,
            "tissue_components": n,
            "pooled_stratum": False,
        },
        index=pd.Index(rows, name="row_number"),
    )
    return pd.concat(frames, ignore_index=True), meta


def test_discrepancy_ranking_separates_technical_review() -> None:
    oof, meta = synthetic_cell_lines()
    ranked = tr.rank_discrepancies(tr.cell_line_evidence(oof, meta), LINES, gate_passed=True)
    top = ranked.iloc[0]
    assert top["row_number"] == 2 and top["tier"] == "A"
    assert top["review_type"].startswith("unexplained discrepancy")
    assert "outside_both_repeat_ranges" not in ranked.columns  # ranges are descriptive only
    assert "repeat_prediction_range_m2_max" in ranked.columns
    meta.loc[2, "stranded"] = True
    flagged = tr.rank_discrepancies(tr.cell_line_evidence(oof, meta), LINES, gate_passed=False)
    first = flagged.iloc[0]
    assert first["review_type"] == "technical review first"
    assert "stranded RNA profile" in first["technical_flags"]
    assert set(flagged["claim_level"]) == {"exploratory"}


def test_tied_values_never_raise_a_percentile_flag() -> None:
    oof, meta = synthetic_cell_lines()  # every line has the same repeat spread (0.01)
    evidence = tr.cell_line_evidence(oof, meta)
    assert (evidence["repeat_instability_pct"] < LINES.high_percentile).all()
    ranked = tr.rank_discrepancies(evidence, LINES, True)
    assert not ranked["technical_flags"].str.contains("unstable").any()
    assert tr.cohort_percentile(pd.Series([1.0, 2.0, 2.0, 3.0])).tolist() == [0.25, 0.5, 0.5, 1.0]


def test_identity_flags_block_replication_priority() -> None:
    oof, meta = synthetic_cell_lines()
    meta.loc[2, "related_flag_sources"] = "CVCL_XXXX"  # SYNTHETIC accession
    ranked = tr.rank_discrepancies(tr.cell_line_evidence(oof, meta), LINES, True)
    priorities = tr.replication_priorities(ranked).set_index("depmap_id")
    assert priorities.loc["ACH-900002", "tier"] == "not_rankable"
    assert set(priorities["validation_status"]) == {"not independent: used in model development"}


def test_too_few_repeats_are_not_rankable() -> None:
    oof, meta = synthetic_cell_lines()
    oof["n_repeats"] = 1
    ranked = tr.rank_discrepancies(tr.cell_line_evidence(oof, meta), LINES, True)
    assert set(ranked["tier"]) == {"not_rankable"}


def pathway_settings(**overrides: object) -> dict[str, object]:
    settings: dict[str, object] = {
        "strong": 0.9,
        "moderate": 0.75,
        "exploratory": 0.5,
        "max_share_zero": 0.5,
        "correlation_flag": 0.8,
        "min_null_draws": 1000,
    }
    settings.update(overrides)
    return settings


def triage_mapping(root: Path, **overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "schema_version": 1,
        "experiment_config": str(root / "unused.yaml"),
        "tables_root": str(root / "tables"),
        "output_dir": str(root / "triage"),
        "external_evidence": None,
        "pathway": pathway_settings(),
        "cell_lines": {"min_repeats": 2, "high_percentile": 0.95, "flag_percentile": 0.9},
    }
    data.update(overrides)
    return data


def test_triage_config_is_strict(tmp_path: Path) -> None:
    triage_from_mapping(triage_mapping(tmp_path))
    bad = [
        triage_mapping(tmp_path, typo=1),
        triage_mapping(tmp_path, pathway={"strong": 0.9}),
        triage_mapping(tmp_path, pathway=pathway_settings(strong=0.5)),  # strong < moderate
        triage_mapping(tmp_path, pathway=pathway_settings(min_null_draws=100)),  # below §15
        triage_mapping(
            tmp_path, cell_lines={"min_repeats": 2, "high_percentile": 0.8, "flag_percentile": 0.9}
        ),
    ]
    for case in bad:
        with pytest.raises(tr.TriageError):
            triage_from_mapping(case)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_generate_triage_end_to_end_on_synthetic_files(tmp_path: Path) -> None:
    oof, meta = synthetic_cell_lines()
    qc = tmp_path / "qc"
    qc.mkdir()
    pd.DataFrame(
        {
            "row_number": meta.index, "depmap_id": meta["depmap_id"],
            "component_id": meta["component_id"], "component_records": 1,
            "oncotree_lineage": "L_A", "oncotree_primary_disease": "L_A_d",
            "eligible_primary": "True", "eligible_retaining_problematic": "True",
            "component_flag_sources": "",
        }
    ).to_csv(qc / "eligibility.csv", index=False)  # fmt: skip
    experiment = experiment_from_mapping(
        {
            "schema_version": 1,
            "run_id": "SYNTHETIC_run",
            "inputs": {
                "qc_dir": str(qc),
                "qc_sha256": {"eligibility.csv": sha(qc / "eligibility.csv")},
                "clarifi": "c",
                "clarifi_manifest": "m",
                "expression": "e",
                "gene_sets": "g",
                "gene_sets_sha256": None,
            },
            "population": "primary",
            "population_options": {"min_components_per_tissue": 3},
            "scales": ["raw"],
            "models": ["M1", "M2"],
            "grids": {"M1": {"alpha": [1.0]}, "M2": {"alpha": [0.1]}},
            "validation": {"k_outer": 3, "k_inner": 2, "repeats": 3},
            "seeds": {"base_seed": 1},
            "fit": {"component_weighting": True},
            "predictions": {"clip_raw_to_unit_interval": True},
            "inference": {"method": "not_assessable", "alpha_one_sided": 0.05},
            "output_dir": str(tmp_path / "models"),
        }
    )
    run_dir = tmp_path / "models" / "SYNTHETIC_run"
    run_dir.mkdir(parents=True)
    (run_dir / "run_manifest.json").write_text(
        json.dumps({"splits_sha256": "0" * 64, "inputs_sha256": {"synthetic": "1" * 64}})
    )
    tables = tmp_path / "tables" / "SYNTHETIC_run"
    (tables / "explainability").mkdir(parents=True)
    (tables / "evaluation_record.json").write_text(
        json.dumps(
            {
                "run_id": "SYNTHETIC_run",
                "config_sha256": experiment.sha256,
                "run_manifest_sha256": sha(run_dir / "run_manifest.json"),
            }
        )
    )
    pd.DataFrame(
        {"model": ["M2"], "comparator": ["M1"], "scale": ["raw"], "verdict": ["descriptive only"]}
    ).to_csv(tables / "comparisons.csv", index=False)
    oof.to_csv(tables / "oof_predictions.csv", index=False)
    importance, signs, tests, correlation = synthetic_pathway_tables()
    importance.to_csv(tables / "explainability" / "importance_per_task.csv")
    signs.to_csv(tables / "explainability" / "coefficient_signs.csv")
    tests.to_csv(tables / "explainability" / "gene_set_tests.csv")
    correlation.to_csv(tables / "explainability" / "gene_set_score_correlation.csv")
    (tables / "explainability" / "stability.json").write_text(
        json.dumps({"config_sha256": experiment.sha256})
    )

    out = generate_triage(triage_from_mapping(triage_mapping(tmp_path)), experiment)
    manifest = json.loads((out / "triage_manifest.json").read_text())
    assert manifest["run_id"] == "SYNTHETIC_run"
    assert manifest["primary_gain_shown"] is False
    assert manifest["primary_status"] == "primary gain not shown"
    assert manifest["required_real_fits"] == 9  # 3 folds x 3 repeats in this fixture
    assert manifest["evaluation_record_sha256"] == sha(tables / "evaluation_record.json")
    assert "new_unassayed_depmap_lines" in manifest["deferred"]
    pathways = pd.read_csv(out / "pathway_candidates.csv")
    assert set(pathways["tier"]) <= {"C", "not_prioritised", "not_rankable"}
    for name in ("cell_line_validation_priorities.csv", "discrepancy_review.csv"):
        assert len(pd.read_csv(out / name)) == len(meta)
    with pytest.raises(FileExistsError):  # write-once
        generate_triage(triage_from_mapping(triage_mapping(tmp_path)), experiment)
