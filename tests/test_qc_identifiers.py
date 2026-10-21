"""Unit tests for the phase_01 identifier QC: identity, grouping, eligibility, outputs.

SYNTHETIC SOFTWARE-TEST DATA ONLY: every identifier, name, lineage assignment and
outcome cell below is invented to exercise the code (ACH-9xxxxx, CVCL_ZZxx, FAKE*
names). None is a scientific observation, and no real data are read. Outcome
cells are placeholders that only drive the validity check. No models are trained
or evaluated.
"""

from __future__ import annotations

import csv
import dataclasses
import io
from pathlib import Path

import pytest

from radiosensitivity_ml.data import cellosaurus as cs
from radiosensitivity_ml.data import components as cp
from radiosensitivity_ml.data import eligibility as el
from radiosensitivity_ml.data import qc_identifiers as qc
from radiosensitivity_ml.data import qc_report as report
from radiosensitivity_ml.data.provenance import (
    listed_sha256,
    manifest_file_sha256,
    write_once_folder,
)

SOLID = ["Lung", "Breast", "Skin", "Bowel"]


def synthetic_config(
    min_components: int = 2,
    outer_folds: int = 2,
    span_scope: str = "record_eligible",
    propagate: bool = False,
) -> el.QCConfig:
    """SYNTHETIC test configuration (small thresholds so tiny fixtures exercise T10)."""
    return el.config_from_mapping(
        {
            "schema_version": 1,
            "population": {
                "haematopoietic_lineages": ["Myeloid", "Lymphoid"],
                "excluded_lineages": ["Other"],
                "solid_lineages": SOLID,
                "non_cancer_markers": ["non-cancerous"],
                "lineage_span_scope": span_scope,
                "propagate_problem_flags": propagate,
            },
            "tissue": {
                "primary_taxonomy": "OncotreeLineage",
                "min_components_per_tissue": min_components,
            },
            "validation_structure": {"outer_folds": outer_folds},
            "moringa_lines": {"ACH-900001": "FAKEA"},
            "provisional_floors": [{"name": "floor", "min_n": 2, "min_t10": 1}],
        }
    )


def clarifi_row(depmap_id: str, name: str, outcome: str = "0.5") -> dict[str, str]:
    """SYNTHETIC CLARIFi-like row; the outcome cell is a placeholder."""
    return {"CCLE Name": name, "Depmap ID": depmap_id, "mSF2": outcome}


def model_row(depmap_id: str, name: str, rrid: str, patient: str, lineage: str) -> dict[str, str]:
    """SYNTHETIC DepMap Model-like row (optional columns absent)."""
    return {
        "ModelID": depmap_id,
        "CCLEName": name,
        "CellLineName": name,
        "StrippedCellLineName": name,
        "RRID": rrid,
        "PatientID": patient,
        "OncotreeLineage": lineage,
        "OncotreePrimaryDisease": "fake disease",
        "DepmapModelType": "FAKE",
    }


def cello(
    ac: str,
    name: str,
    depmap: tuple[str, ...] = (),
    parents: tuple[str, ...] = (),
    same: tuple[str, ...] = (),
    secondary: tuple[str, ...] = (),
    problematic: str = "",
    category: str = "Cancer cell line",
    species: str = "NCBI_TaxID=9606; ! Homo sapiens (Human)",
) -> cs.CellosaurusRecord:
    """SYNTHETIC Cellosaurus record."""
    return cs.CellosaurusRecord(
        accession=ac,
        name=name,
        secondary_accessions=secondary,
        synonyms=(),
        depmap_ids=depmap,
        parents=tuple(cs.Link(a, "") for a in parents),
        parent_status=cs.RECORDED if parents else cs.NONE_RECORDED,
        same_individual=tuple(cs.Link(a, "") for a in same),
        same_individual_status=cs.RECORDED if same else cs.NONE_RECORDED,
        category=category,
        species=species,
        problematic=problematic,
        entry_version="1",
    )


# SYNTHETIC scenario covering the main cases:
#  A, B   share a DepMap PatientID                -> same component
#  C, D   D's parent (hi) is C                    -> same component
#  E, F   both children of bridge CVCL_ZZ90 (fetched, outside CLARIFi) -> same component
#  G, H   same individual (oi)                    -> same component
#  I      RRID is a secondary accession            -> verified (note), singleton
#  J, K   two DepMap IDs, one Cellosaurus entry (alias) -> ambiguous, same component
#  L      two Cellosaurus entries cross-reference it -> ambiguous
#  M      not in Model table                      -> unmatched
#  N      no Cellosaurus entry at all              -> unmatched
#  O      no RNA profile / not in expression      -> excluded (missing expression)
#  P      haematopoietic lineage                  -> excluded, sensitivity stratum
#  Q      problematic entry                       -> excluded primary, retained in sensitivity
#  R      blank outcome cell                      -> outcome_invalid_review
#  S      CCLE name differs from Model table      -> ambiguous (ids concordant, name discordant)
#  T      unrecognised lineage string             -> review
LETTERS = "ABCDEFGHIJKLMNOPQRST"
IDS = {letter: f"ACH-9000{i:02d}" for i, letter in enumerate(LETTERS, start=1)}
LINEAGE = {
    "A": "Lung",
    "B": "Lung",
    "C": "Breast",
    "D": "Breast",
    "E": "Skin",
    "F": "Skin",
    "G": "Bowel",
    "H": "Bowel",
    "I": "Lung",
    "J": "Lung",
    "K": "Lung",
    "L": "Lung",
    "M": "Lung",
    "N": "Lung",
    "O": "Lung",
    "P": "Myeloid",
    "Q": "Skin",
    "R": "Lung",
    "S": "Lung",
    "T": "Unknown Tissue X",
}


def scenario_parts() -> tuple[
    list[dict[str, str]], dict[str, dict[str, str]], list[cs.CellosaurusRecord]
]:
    """Build the SYNTHETIC scenario's CLARIFi rows, Model index and Cellosaurus records."""
    clarifi_rows = [
        clarifi_row(IDS[k], f"FAKE{k}_X", outcome="" if k == "R" else "0.5") for k in LETTERS
    ]
    models = {}
    for k, depmap_id in IDS.items():
        if k == "M":
            continue
        rrid = {"I": "CVCL_ZZ79", "J": "CVCL_ZZJJ", "K": "CVCL_ZZJJ", "N": "CVCL_ZZNN"}.get(
            k, f"CVCL_ZZ{k}{k}"
        )
        patient = "PT-AB" if k in "AB" else f"PT-{k}"
        name = "FAKES_RENAMED" if k == "S" else f"FAKE{k}_X"
        models[depmap_id] = model_row(depmap_id, name, rrid, patient, LINEAGE[k])
    records = [cello(f"CVCL_ZZ{k}{k}", f"FAKE{k}", depmap=(IDS[k],)) for k in "ABCHMOPRST"]
    records += [
        cello("CVCL_ZZDD", "FAKED", depmap=(IDS["D"],), parents=("CVCL_ZZCC",)),
        cello("CVCL_ZZEE", "FAKEE", depmap=(IDS["E"],), parents=("CVCL_ZZ90",)),
        cello("CVCL_ZZFF", "FAKEF", depmap=(IDS["F"],), parents=("CVCL_ZZ90",)),
        cello("CVCL_ZZ90", "FAKEPARENT"),
        cello("CVCL_ZZGG", "FAKEG", depmap=(IDS["G"],), same=("CVCL_ZZHH",)),
        cello("CVCL_ZZII", "FAKEI", depmap=(IDS["I"],), secondary=("CVCL_ZZ79",)),
        cello("CVCL_ZZJJ", "FAKEJ", depmap=(IDS["J"], IDS["K"])),
        cello("CVCL_ZZL1", "FAKEL1", depmap=(IDS["L"],)),
        cello("CVCL_ZZL2", "FAKEL2", depmap=(IDS["L"],)),
        cello("CVCL_ZZQQ", "FAKEQ", depmap=(IDS["Q"],), problematic="Misidentified (synthetic)"),
    ]
    return clarifi_rows, models, records


def make_inputs(
    clarifi_rows: list[dict[str, str]],
    models: dict[str, dict[str, str]],
    records: list[cs.CellosaurusRecord],
    not_expressed: tuple[str, ...] = ("O",),
) -> report.QCInputs:
    """Assemble SYNTHETIC parsed inputs."""
    expressed = sorted(v for k, v in IDS.items() if k not in not_expressed)
    return report.QCInputs(
        clarifi=qc.parse_clarifi(clarifi_rows),
        models=models,
        model_header=tuple(qc.MODEL_COLUMNS),
        rna_models=set(expressed),
        profile_types=("rna",),
        expression_ids=expressed,
        cellosaurus=cs.merge_records(records),
        cellosaurus_provenance={},
    )


def run(inputs: report.QCInputs | None = None) -> report.QCResult:
    """Run the QC on the scenario (or given inputs)."""
    return report.run_identifier_qc(inputs or make_inputs(*scenario_parts()), synthetic_config())


@pytest.fixture()
def result() -> report.QCResult:
    return run()


def by_letter(result: report.QCResult) -> dict[str, qc.IdentityRow]:
    rows = {r.depmap_id: r for r in result.rows}
    return {k: rows[v] for k, v in IDS.items()}


def table(result: report.QCResult, name: str) -> tuple:
    return next(rows for table_name, rows, _ in result.tables if table_name == name)


# ----------------------------------------------------------------- identity status


def test_identity_statuses(result: report.QCResult) -> None:
    rows = by_letter(result)
    for k in "ABCDEFGHIOPQRT":
        assert rows[k].identity_status == qc.VERIFIED, k
    assert rows["I"].rrid_relation == "secondary"
    assert "rrid_is_secondary_accession" in rows["I"].identity_notes
    for k in "JKLS":
        assert rows[k].identity_status == qc.AMBIGUOUS, k
    for k in "MN":
        assert rows[k].identity_status == qc.UNMATCHED, k
    assert "not_in_model_table" in rows["M"].identity_issues
    assert "no_cellosaurus_record" in rows["N"].identity_issues
    assert rows["N"].parent_status == "no_record"


def test_alias_and_ambiguous_issues(result: report.QCResult) -> None:
    rows = by_letter(result)
    assert "shares_cellosaurus_accession" in rows["J"].identity_issues
    assert "shares_rrid" in rows["K"].identity_issues
    assert "multiple_cellosaurus_records" in rows["L"].identity_issues
    assert rows["L"].cellosaurus_accession == ""
    assert rows["L"].cellosaurus_candidates == ("CVCL_ZZL1", "CVCL_ZZL2")
    assert rows["S"].identity_issues == ("ccle_name_mismatch",)
    assert result.summary["ids_concordant_name_discordant"] == [
        f"{IDS['S']}@row{rows['S'].row_number}"
    ]


def test_entry_found_only_via_rrid_is_ambiguous_not_matched() -> None:
    clarifi_rows, models, records = scenario_parts()
    records.append(cello("CVCL_ZZNN", "FAKEN"))  # no DepMap cross-reference
    rows = by_letter(run(make_inputs(clarifi_rows, models, records)))
    assert rows["N"].identity_status == qc.AMBIGUOUS
    assert "cellosaurus_found_via_rrid_only" in rows["N"].identity_issues
    assert rows["N"].cellosaurus_accession == ""


def test_names_never_create_matches() -> None:
    clarifi = qc.parse_clarifi([clarifi_row("ACH-900099", "FAKEA_X")])
    models = {"ACH-900001": model_row("ACH-900001", "FAKEA_X", "CVCL_ZZAA", "PT-A", "Lung")}
    rows = qc.assess_identity(clarifi, models, set(), set(), {})
    assert rows[0].identity_status == qc.UNMATCHED


def test_duplicate_depmap_rows_share_a_component_and_are_excluded() -> None:
    clarifi_rows, models, records = scenario_parts()
    clarifi_rows.append(clarifi_row(IDS["A"], "FAKEA_X"))
    res = run(make_inputs(clarifi_rows, models, records))
    duplicates = [r for r in res.rows if r.depmap_id == IDS["A"]]
    assert len(duplicates) == 2
    assert len({r.row_number for r in duplicates}) == 2
    assert len({r.component_id for r in duplicates}) == 1
    assert not any(r.eligible_primary for r in duplicates)
    kinds = {row["identifier_type"] for row in table(res, "duplicate_identifiers.csv")}
    assert {"clarifi_depmap_id", "clarifi_ccle_name"} <= kinds


def test_model_table_rejects_duplicates_and_marks_absent_columns() -> None:
    row = model_row("ACH-900001", "FAKEA_X", "CVCL_ZZAA", "PT-A", "Lung")
    with pytest.raises(qc.IdentifierQCError):
        qc.index_model_table([row, row])
    index = qc.index_model_table([row], header=tuple(row))
    assert index["ACH-900001"]["EngineeredModel"] == qc.COLUMN_ABSENT


def test_default_profiles_without_rna_fail_loudly() -> None:
    with pytest.raises(qc.IdentifierQCError):
        qc.default_rna_models([{"ModelID": "ACH-900001", "ProfileType": "dna"}])
    models, kinds = qc.default_rna_models([{"ModelID": "ACH-900001", "ProfileType": "RNA"}])
    assert models == {"ACH-900001"} and kinds == ["RNA"]


# ------------------------------------------------------------------- relationships


def test_components_group_related_records(result: report.QCResult) -> None:
    rows = by_letter(result)
    for left, right in [("A", "B"), ("C", "D"), ("E", "F"), ("G", "H"), ("J", "K")]:
        assert rows[left].component_id == rows[right].component_id, (left, right)
    assert rows["A"].component_id != rows["C"].component_id
    assert rows["I"].component_records == 1


def test_relationship_tables(result: report.QCResult) -> None:
    parents = {
        (p["child_accession"], p["parent_accession"])
        for p in table(result, "relationships_parent.csv")
    }
    assert ("CVCL_ZZDD", "CVCL_ZZCC") in parents
    assert ("CVCL_ZZEE", "CVCL_ZZ90") in parents
    same = table(result, "relationships_same_individual.csv")
    sources = {(s["identifier_a"], s["identifier_b"], s["source"]) for s in same}
    assert ("CVCL_ZZGG", "CVCL_ZZHH", "cellosaurus_oi") in sources
    assert (IDS["A"], IDS["B"], "depmap_patient_id") in sources


def test_ambiguous_candidate_links_to_verified_record() -> None:
    clarifi_rows, models, records = scenario_parts()
    records = [r for r in records if r.accession != "CVCL_ZZL2"]
    records.append(cello("CVCL_ZZL2", "FAKEL2", depmap=(IDS["L"],), parents=("CVCL_ZZAA",)))
    rows = by_letter(run(make_inputs(clarifi_rows, models, records)))
    # Ambiguous candidates link only in the conservative candidate graph.
    assert rows["L"].candidate_component_id == rows["A"].candidate_component_id
    assert rows["L"].component_id != rows["A"].component_id


def test_hi_chain_through_bridges_and_cut_off_chain() -> None:
    clarifi_rows, models, records = scenario_parts()
    # C's grandparent chain: C -> B1 -> B2 <- T (T is a child of B2)
    records = [r for r in records if r.accession not in {"CVCL_ZZCC", "CVCL_ZZTT"}]
    chain = [
        cello("CVCL_ZZCC", "FAKEC", depmap=(IDS["C"],), parents=("CVCL_ZZB1",)),
        cello("CVCL_ZZB1", "BRIDGE1", parents=("CVCL_ZZB2",)),
        cello("CVCL_ZZB2", "BRIDGE2"),
        cello("CVCL_ZZTT", "FAKET", depmap=(IDS["T"],), parents=("CVCL_ZZB2",)),
    ]
    full = by_letter(run(make_inputs(clarifi_rows, models, records + chain)))
    assert full["C"].component_id == full["T"].component_id
    assert "component_links_not_expanded_review" not in full["C"].exclusion_reasons
    cut = by_letter(run(make_inputs(clarifi_rows, models, records + chain[:1] + chain[3:])))
    assert cut["C"].component_id != cut["T"].component_id
    assert "component_links_not_expanded_review" in cut["C"].exclusion_reasons
    assert "component_links_not_expanded_review" in cut["D"].exclusion_reasons


def test_one_sided_oi_and_secondary_hi_still_merge() -> None:
    clarifi_rows, models, records = scenario_parts()
    records = [r for r in records if r.accession not in {"CVCL_ZZRR", "CVCL_ZZII"}]
    records += [
        cello("CVCL_ZZRR", "FAKER", depmap=(IDS["R"],), parents=("CVCL_ZZ79",)),  # secondary of II
        cello("CVCL_ZZII", "FAKEI", depmap=(IDS["I"],), secondary=("CVCL_ZZ79",)),
    ]
    res = run(make_inputs(clarifi_rows, models, records))
    rows = by_letter(res)
    assert rows["R"].component_id == rows["I"].component_id
    assert "CVCL_ZZ79" not in res.summary["links_not_expanded"]
    assert rows["G"].component_id == rows["H"].component_id  # oi listed on G only


def test_problem_flag_on_bridge_entry_spreads() -> None:
    clarifi_rows, models, records = scenario_parts()
    records = [r for r in records if r.accession != "CVCL_ZZ90"]
    records.append(cello("CVCL_ZZ90", "FAKEPARENT", problematic="Contaminated (synthetic)"))
    inputs = make_inputs(clarifi_rows, models, records)
    # Default: the flag is reported but does not exclude otherwise eligible relatives.
    rows = by_letter(report.run_identifier_qc(inputs, synthetic_config()))
    for k in "EF":
        assert rows[k].component_flag_sources == ("CVCL_ZZ90",)
        assert rows[k].eligible_primary
    # propagate_problem_flags: true -> excluded from primary, kept in the sensitivity set.
    strict = by_letter(report.run_identifier_qc(inputs, synthetic_config(propagate=True)))
    for k in "EF":
        assert strict[k].exclusion_reasons == ("component_problematic",)
        assert strict[k].eligible_retaining_problematic


def test_candidate_graph_is_reported_separately(result: report.QCResult) -> None:
    candidate = result.summary["feasibility"]["candidate_graph_sensitivity"]
    primary = result.summary["feasibility"]["primary"]
    assert candidate["n_eligible_records"] == primary["n_eligible_records"]
    assert candidate["n_eligible_components"] <= primary["n_eligible_components"]
    names = [name for name, _, _ in result.tables]
    assert "candidate_components.csv" in names


def test_strandedness_is_verified_not_assumed() -> None:
    default_rows = [
        {"ModelID": "ACH-900001", "ProfileID": "PR-1", "ProfileType": "rna"},
        {"ModelID": "ACH-900002", "ProfileID": "PR-2", "ProfileType": "rna"},
    ]
    profiles = [{"ProfileID": "PR-1", "Stranded": "True"}, {"ProfileID": "PR-2", "Stranded": ""}]
    report_ = qc.strandedness_report(
        ("ProfileID", "Stranded"), profiles, default_rows, ["ACH-900001", "ACH-900002"]
    )
    assert report_["available"] is True
    assert report_["value_counts"] == {"Stranded": {"(blank)": 1, "True": 1}}
    absent = qc.strandedness_report(("ProfileID", "Other"), profiles, default_rows, ["ACH-900001"])
    assert absent == {"columns_found": [], "available": False}


def test_disagreeing_rrid_pulls_both_accessions_together() -> None:
    clarifi_rows, models, records = scenario_parts()
    models[IDS["A"]]["RRID"] = "CVCL_ZZCC"  # A's RRID points at C's entry
    rows = by_letter(run(make_inputs(clarifi_rows, models, records)))
    assert "rrid_disagrees_with_cellosaurus" in rows["A"].identity_issues
    # A disagreeing RRID links only in the candidate graph.
    assert rows["A"].candidate_component_id == rows["C"].candidate_component_id
    assert rows["A"].component_id != rows["C"].component_id


def test_haematopoietic_line_sharing_a_donor_with_solid_line() -> None:
    clarifi_rows, models, records = scenario_parts()
    models[IDS["P"]]["PatientID"] = "PT-AB"
    inputs = make_inputs(clarifi_rows, models, records)
    # Default scope (record_eligible): the excluded haematopoietic relative does not
    # exclude the solid lines, but they stay in one component (never split).
    rows = by_letter(report.run_identifier_qc(inputs, synthetic_config()))
    assert rows["P"].component_id == rows["A"].component_id
    assert rows["A"].eligible_primary
    # all_members scope: the whole component is excluded.
    strict = by_letter(report.run_identifier_qc(inputs, synthetic_config(span_scope="all_members")))
    assert "component_spans_lineages" in strict["A"].exclusion_reasons


def test_pending_review_records_are_reported_separately(result: report.QCResult) -> None:
    eligibility = result.summary["eligibility"]
    # Awaiting review only: J, K, L, S (identity_ambiguous), R (outcome_invalid_review),
    # T (lineage_unrecognised_review). M, N, O, P, Q have final reasons.
    assert eligibility["records_excluded_only_pending_review"] == 6
    assert (
        eligibility["components_if_pending_reviews_cleared"]
        >= result.summary["feasibility"]["primary"]["n_eligible_components"]
    )


def test_connected_components_are_order_independent() -> None:
    edges = [("b", "c"), ("x", "y"), ("a", "b")]
    first = cp.connected_components(["a", "z"], edges)
    second = cp.connected_components(["z", "a"], list(reversed(edges)))
    assert first == second
    assert first["c"] == "G:a" and first["z"] == "G:z" and first["y"] == "G:x"


# --------------------------------------------------------------------- eligibility


def test_exclusion_accounting(result: report.QCResult) -> None:
    rows = by_letter(result)
    assert rows["O"].exclusion_reasons == ("no_default_rna_profile", "not_in_expression_matrix")
    assert rows["P"].exclusion_reasons == ("lineage_haematopoietic",)
    assert rows["Q"].exclusion_reasons == ("problematic_cell_line",)
    assert rows["Q"].eligible_retaining_problematic and not rows["Q"].eligible_primary
    assert rows["R"].exclusion_reasons == ("outcome_invalid_review",)
    assert rows["T"].exclusion_reasons == ("lineage_unrecognised_review",)
    eligible = {k for k, r in rows.items() if r.eligible_primary}
    assert eligible == set("ABCDEFGHI")
    assert all(r.exclusion_reasons for k, r in rows.items() if k not in eligible)
    assert result.summary["eligibility"]["haematopoietic_stratum_records"] == 1


def test_review_rules_for_category_species_and_non_cancer() -> None:
    clarifi_rows, models, records = scenario_parts()
    records = [r for r in records if r.accession not in {"CVCL_ZZAA", "CVCL_ZZBB"}]
    records += [
        cello("CVCL_ZZAA", "FAKEA", depmap=(IDS["A"],), category="Transformed cell line"),
        cello("CVCL_ZZBB", "FAKEB", depmap=(IDS["B"],), species="NCBI_TaxID=10029; ! Hamster"),
    ]
    models[IDS["C"]]["OncotreePrimaryDisease"] = "Non-Cancerous"
    rows = by_letter(run(make_inputs(clarifi_rows, models, records)))
    assert "cellosaurus_category_review" in rows["A"].exclusion_reasons
    assert "non_human_review" in rows["B"].exclusion_reasons
    assert "non_cancer_model_review" in rows["C"].exclusion_reasons


def test_outcome_validity_classes() -> None:
    kinds = [qc.outcome_invalid_kind(v) for v in ("", "abc", "nan", "-0.1", "1.2", "0", "1", "0.4")]
    assert kinds == ["blank", "non_numeric", "non_finite", "below_zero", "above_one", "", "", ""]


def test_valid_outcome_values_do_not_change_grouping_or_eligibility(tmp_path: Path) -> None:
    clarifi_rows, models, records = scenario_parts()
    changed = [{**row, "mSF2": "0.123" if row["mSF2"] else ""} for row in clarifi_rows]
    first = run(make_inputs(clarifi_rows, models, records))
    second = run(make_inputs(changed, models, records))
    for folder, res in ((tmp_path / "a", first), (tmp_path / "b", second)):
        folder.mkdir()
        report.write_report(folder, res)
    for name in ("components.csv", "eligibility.csv", "tissue_counts.csv", "summary.json"):
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes(), name


def test_every_eligible_record_is_an_ach_node(result: report.QCResult) -> None:
    nodes = {
        (row["identifier"], row["component_id"])
        for row in table(result, "components.csv")
        if row["node_type"] == "ACH"
    }
    for row in result.rows:
        if row.eligible_primary:
            assert (row.depmap_id, row.component_id) in nodes


def test_component_spanning_lineages_is_excluded() -> None:
    clarifi_rows, models, records = scenario_parts()
    models[IDS["B"]]["OncotreeLineage"] = "Breast"  # A and B share a donor
    rows = by_letter(run(make_inputs(clarifi_rows, models, records)))
    assert "component_spans_lineages" in rows["A"].exclusion_reasons
    assert "component_spans_lineages" in rows["B"].exclusion_reasons


# ------------------------------------------------------------------- tissue and T10


def test_tissue_counts_and_t10(result: report.QCResult) -> None:
    primary = {
        c["tissue"]: c
        for c in table(result, "tissue_counts.csv")
        if c["taxonomy"] == "oncotree_lineage" and c["population"] == "primary"
    }
    # eligible: {A,B} and {I} (Lung); {C,D} Breast; {E,F} Skin; {G,H} Bowel
    assert primary["Lung"]["eligible_components"] == 2
    assert primary["Lung"]["eligible_records"] == 3
    assert primary["Breast"]["eligible_components"] == 1
    feasibility = result.summary["feasibility"]["primary"]
    assert feasibility["n_eligible_components"] == 5
    assert feasibility["T10"] == 1
    assert feasibility["qualifying_tissues"] == ["Lung"]
    assert feasibility["components_pooled_as_other_solid"] == 3
    assert feasibility["held_out_tissue_training_components"] == {"Lung": 3}
    assert feasibility["component_size_histogram"] == {"1": 1, "2": 4}
    floors = result.summary["feasibility"]["provisional_floors_descriptive_not_power"]
    assert floors[0]["met"] is True


def test_multiple_label_components_are_not_pooled() -> None:
    clarifi_rows, models, records = scenario_parts()
    clarifi_rows = [
        {**row, "CCLE Name": "FAKEB_OTHERSUFFIX"} if row["Depmap ID"] == IDS["B"] else row
        for row in clarifi_rows
    ]
    models[IDS["B"]]["CCLEName"] = "FAKEB_OTHERSUFFIX"
    res = run(make_inputs(clarifi_rows, models, records))
    suffix = res.summary["feasibility"]["sensitivity"]["primary/ccle_suffix"]
    assert suffix["components_with_multiple_labels_not_pooled"] == 1


def test_attrition_table_counts_first_and_any_reason(result: report.QCResult) -> None:
    attrition = {
        (a["oncotree_lineage"], a["reason"]): a for a in table(result, "attrition_by_tissue.csv")
    }
    assert attrition[("Lung", "no_default_rna_profile")]["records_first_reason"] == 1
    assert attrition[("Lung", "not_in_expression_matrix")]["records_first_reason"] == 0
    assert attrition[("Lung", "not_in_expression_matrix")]["records_any_position"] == 1


def test_config_validation() -> None:
    population = {
        "haematopoietic_lineages": ["Myeloid"],
        "excluded_lineages": [],
        "solid_lineages": ["Lung"],
        "non_cancer_markers": [],
        "lineage_span_scope": "record_eligible",
    }
    base = {
        "population": population,
        "tissue": {"min_components_per_tissue": 10},
        "validation_structure": {"outer_folds": 5},
        "moringa_lines": {},
    }
    assert el.config_from_mapping(base).min_components_per_tissue == 10
    bad_cases = [
        {**base, "population": {**population, "haematopoietic_lineages": ["Lung"]}},  # overlap
        {**base, "population": {**population, "solid_lineages": "Lung"}},  # not a list
        {**base, "schema_version": 2},
        {**base, "population": {**population, "non_cancer_marker": []}},  # typo key
        {**base, "tissue": {"min_components_per_tissue": 9.5}},  # not an integer
        {**base, "population": {k: v for k, v in population.items() if k != "non_cancer_markers"}},
        {**base, "population": {**population, "lineage_span_scope": "some"}},
        {**base, "unknown_section": {}},
    ]
    for case in bad_cases:
        with pytest.raises(el.ConfigError):
            el.config_from_mapping(case)


def test_moringa_lines_reported_without_outcomes(result: report.QCResult) -> None:
    (entry,) = table(result, "moringa_lines.csv")
    assert entry["depmap_id"] == "ACH-900001" and entry["clarifi_records"] == 1
    assert not any("msf2" in key.lower() for key in entry)


# ------------------------------------------------------------------------- outputs


def test_outputs_are_idempotent_order_independent_and_never_overwritten(tmp_path: Path) -> None:
    clarifi_rows, models, records = scenario_parts()
    reversed_models = dict(reversed(list(models.items())))

    def write(folder: Path, model_index: dict, recs: list) -> None:
        res = run(make_inputs(clarifi_rows, model_index, recs))
        write_once_folder(folder, lambda staging: report.write_report(staging, res))

    # CLARIFi row order defines row numbers, so only the other inputs are reordered.
    write(tmp_path / "first", models, records)
    write(tmp_path / "second", reversed_models, list(reversed(records)))
    names = sorted(p.name for p in (tmp_path / "first").iterdir())
    assert names == sorted(p.name for p in (tmp_path / "second").iterdir())
    for name in names:
        first = (tmp_path / "first" / name).read_bytes()
        assert first == (tmp_path / "second" / name).read_bytes(), name
    with pytest.raises(FileExistsError):
        write(tmp_path / "first", models, records)


def test_outputs_contain_no_outcome_values_or_flags(
    tmp_path: Path, result: report.QCResult
) -> None:
    report.write_report(tmp_path, result)
    for path in tmp_path.glob("*.csv"):
        header = next(csv.reader(io.StringIO(path.read_text())))
        assert "mSF2" not in header, path.name
        assert not any("equals" in column for column in header), path.name
    assert "0.5" not in (tmp_path / "identity_records.csv").read_text()


def test_failed_build_leaves_only_partial_folder(tmp_path: Path) -> None:
    def broken(staging: Path) -> None:
        (staging / "half.csv").write_text("x\n")
        raise RuntimeError("synthetic failure")

    with pytest.raises(RuntimeError):
        write_once_folder(tmp_path / "out", broken)
    assert not (tmp_path / "out").exists()
    assert (tmp_path / "out.partial").exists()


def test_model_table_audit_reads_no_expression() -> None:
    clarifi_rows, models, _ = scenario_parts()
    res = report.run_model_table_audit(qc.parse_clarifi(clarifi_rows), models)
    assert res.summary["mode"] == "model_table_audit"
    assert res.summary["records"]["in_model_table"] == len(IDS) - 1
    assert all(r.identity_status != qc.VERIFIED for r in res.rows)
    assert [name for name, _, _ in res.tables] == [
        "identity_records.csv",
        "duplicate_identifiers.csv",
    ]


# --------------------------------------------------------------------- file readers


def test_read_csv_handles_crlf_and_bom(tmp_path: Path) -> None:
    path = tmp_path / "SYNTHETIC.csv"
    path.write_bytes(b"\xef\xbb\xbfCCLE Name,Depmap ID,mSF2\r\nFAKEA_LUNG,ACH-900001,0.5")
    header, rows = qc.read_csv(path, qc.CLARIFI_COLUMNS)
    assert set(header) == set(qc.CLARIFI_COLUMNS) and rows[0]["Depmap ID"] == "ACH-900001"


def test_read_csv_rejects_missing_column(tmp_path: Path) -> None:
    path = tmp_path / "SYNTHETIC_profiles.csv"
    path.write_text("ModelID,Kind\nACH-900001,rna\n")
    with pytest.raises(qc.IdentifierQCError):
        qc.read_csv(path, qc.DEFAULT_PROFILE_COLUMNS)


def test_expression_row_ids_validate_layout(tmp_path: Path) -> None:
    good = tmp_path / "SYNTHETIC_expr.csv"
    good.write_text(",GENE1 (1)\nACH-900001,1.0\nACH-900002,3.0\n")
    assert qc.expression_row_ids(good) == ["ACH-900001", "ACH-900002"]
    bad = tmp_path / "SYNTHETIC_expr_bad.csv"
    bad.write_text("gene,ACH-900001\nGENE1,1.0\n")
    with pytest.raises(qc.IdentifierQCError):
        qc.expression_row_ids(bad)


def test_parse_clarifi_rejects_malformed_id() -> None:
    with pytest.raises(qc.IdentifierQCError):
        qc.parse_clarifi([clarifi_row("ACH-12", "X_LUNG")])


def test_sha256sums_text_and_binary_lines(tmp_path: Path) -> None:
    digest = "a" * 64
    (tmp_path / "SHA256SUMS").write_text(f"{digest}  text.csv\n{digest} *bin.csv\n")
    assert listed_sha256(tmp_path / "text.csv") == digest
    assert listed_sha256(tmp_path / "bin.csv") == digest
    assert listed_sha256(tmp_path / "other.csv") is None


def test_manifest_paths_are_normalised(tmp_path: Path) -> None:
    manifest = tmp_path / "SYNTHETIC_manifest.yaml"
    manifest.write_text("files:\n  - path: data/raw/x.csv\n    sha256: abc\n")
    assert manifest_file_sha256(manifest, "./data/raw/x.csv") == "abc"


def test_identity_row_has_no_outcome_value_field() -> None:
    names = {f.name for f in dataclasses.fields(qc.IdentityRow)}
    assert "outcome_invalid" in names
    assert not {"msf2", "mSF2", "outcome", "outcome_value"} & names
