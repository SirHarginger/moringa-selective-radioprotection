"""Tests for the Moringa compound curation, scoring and table writing.

SYNTHETIC DATA ONLY: every record below is invented in memory to exercise code paths.
Nothing here is a scientific result, and no model is fitted or queried (no ``model_fit``
marker). A separate test checks the real curated files parse and that their rules hold.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
import yaml

from radiosensitivity_ml.compounds import curation as cu
from radiosensitivity_ml.compounds import ranking as rk
from radiosensitivity_ml.compounds import report as rp

ROOT = Path(__file__).resolve().parents[1]
REAL_CONSTITUENTS = ROOT / "data" / "compounds" / "moringa_constituents.yaml"
REAL_EVIDENCE = ROOT / "data" / "compounds" / "compound_biology_evidence.yaml"


# ------------------------------------------------------------------ synthetic builders


def report(**overrides: Any) -> dict[str, Any]:
    """SYNTHETIC analytical report (defaults: a strong, primary, non-DCM seed report)."""
    base = {
        "citation": "Synthetic A et al. Test journal 2020;1:1-2.",
        "doi": "10.0000/synthetic-a",
        "pmid": "1",
        "doi_verified_via": "europepmc",
        "reading_depth": "full_text",
        "is_review": False,
        "plant_part": "seed",
        "solvent_or_fraction": "Ethanol seed extract",
        "identification_method": "Isolation and NMR",
        "identification_strength": "isolation_nmr",
        "is_dcm": False,
        "research_group": "Group A",
    }
    return base | overrides


def constituent(**overrides: Any) -> dict[str, Any]:
    """SYNTHETIC constituent record."""
    base = {
        "compound_id": "synthcompound",
        "preferred_name": "Synthcompound",
        "chemical_class": "Test class",
        "plant_part": "seed",
        "extraction_category": "seed_or_leaf_other_solvent",
        "pubchem_cid": "1",
        "inchikey": "AAAAAAAAAAAAAA-AAAAAAAAAA-A",
        "identifier_verified_via": "pubchem",
        "reports": [report()],
    }
    return base | overrides


def evidence(**overrides: Any) -> dict[str, Any]:
    """SYNTHETIC biology evidence item (defaults: scored L3 radiation study)."""
    base = {
        "evidence_id": "SYN-01",
        "compound_id": "synthcompound",
        "evidence_level": "L3_radiation",
        "process_category": "dna_damage",
        "citation": "Synthetic B et al. Test journal 2021;2:3-4.",
        "doi": "10.0000/synthetic-b",
        "pmid": "2",
        "doi_verified_via": "europepmc",
        "reading_depth": "abstract",
        "is_review": False,
        "purified_compound": True,
        "model_system": "Test cells",
        "tissue_class": "normal",
        "species": "human",
        "radiation_type": "Gamma",
        "radiation_dose_gy": "2",
        "concentration": "10 micromolar",
        "exposure_timing": "1 h before",
        "endpoints": "Comet assay",
        "genes_measured": ["TP53", "BAX"],
        "direction": "radioprotection_normal",
        "research_group": "Group B",
        "limitation": "Synthetic",
        "counts_for_score": True,
    }
    return base | overrides


def curated(
    constituents: list[dict[str, Any]] | None = None,
    items: list[dict[str, Any]] | None = None,
) -> cu.CuratedEvidence:
    records = [cu.parse_constituent(c) for c in (constituents or [constituent()])]
    known = {c.compound_id for c in records}
    parsed = [cu.parse_evidence(e, known) for e in (items or [])]
    return cu.CuratedEvidence(constituents=tuple(records), evidence=tuple(parsed))


def write_pair(tmp_path: Path, constituents: list[dict], items: list[dict]) -> tuple[Path, Path]:
    a, b = tmp_path / "constituents.yaml", tmp_path / "evidence.yaml"
    a.write_text(yaml.safe_dump({"constituents": constituents}), encoding="utf-8")
    b.write_text(yaml.safe_dump({"evidence": items}), encoding="utf-8")
    return a, b


# ---------------------------------------------------------------- identity and schema


def test_unknown_field_is_refused() -> None:
    with pytest.raises(cu.CurationError, match="unknown field"):
        cu.parse_constituent(constituent(bioactivity="very high"))


def test_missing_identifier_requires_a_caveat() -> None:
    record = constituent(pubchem_cid=None)
    with pytest.raises(cu.CurationError, match="identity_caveat"):
        cu.parse_constituent(record)
    parsed = cu.parse_constituent(record | {"identity_caveat": "no public record found"})
    assert parsed.pubchem_cid is None and parsed.identity_caveat


def test_unknown_enumeration_values_are_refused() -> None:
    with pytest.raises(cu.CurationError, match="not one of"):
        cu.parse_constituent(constituent(extraction_category="probably_present"))
    with pytest.raises(cu.CurationError, match="not one of"):
        cu.parse_evidence(evidence(direction="works_well"), {"synthcompound"})


def test_evidence_for_an_unknown_compound_is_refused() -> None:
    with pytest.raises(cu.CurationError, match="unknown compound_id"):
        cu.parse_evidence(evidence(compound_id="ghost"), {"synthcompound"})


# ------------------------------------------------------- extraction-specific evidence


def test_dcm_category_requires_a_primary_dcm_report() -> None:
    with pytest.raises(cu.CurationError, match="needs a DCM report"):
        cu.parse_constituent(constituent(extraction_category="dcm_documented"))
    ok = constituent(
        extraction_category="dcm_documented",
        reports=[report(is_dcm=True, solvent_or_fraction="Methylene chloride fraction")],
    )
    parsed = cu.parse_constituent(ok)
    assert len(parsed.dcm_reports) == 1


def test_a_review_can_never_establish_a_dcm_report() -> None:
    with pytest.raises(cu.CurationError, match="review cannot establish"):
        cu.parse_report(report(is_dcm=True, is_review=True, solvent_or_fraction="DCM"), "test")


def test_dcm_report_requires_the_solvent_wording() -> None:
    with pytest.raises(cu.CurationError, match="solvent/fraction wording"):
        cu.parse_report(report(is_dcm=True, solvent_or_fraction=None), "test")


def test_extraction_category_never_changes_the_score() -> None:
    """The same evidence must score identically whatever the extraction category."""
    other = curated([constituent()], [evidence()])
    dcm = curated(
        [
            constituent(
                extraction_category="dcm_documented",
                reports=[report(is_dcm=True, solvent_or_fraction="Methylene chloride fraction")],
            )
        ],
        [evidence()],
    )
    assert rk.rank(other)[0].points == rk.rank(dcm)[0].points
    # ... but it is visible in the table, and it drives the stated limitation
    table = rk.ranking_table(dcm)
    assert table.loc[0, "extraction_category"] == "dcm_documented"
    assert table.loc[0, "dcm_reports"] == 1
    assert "dichloromethane" in rk.ranking_table(other).loc[0, "main_limitation"]


# --------------------------------------------------------- scoring: reviews, purity, D1


def test_a_review_may_never_score() -> None:
    with pytest.raises(cu.CurationError, match="review may never count"):
        cu.parse_evidence(evidence(is_review=True), {"synthcompound"})


def test_an_extract_study_may_never_score() -> None:
    with pytest.raises(cu.CurationError, match="only purified-compound studies"):
        cu.parse_evidence(evidence(purified_compound=False), {"synthcompound"})
    allowed = cu.parse_evidence(
        evidence(purified_compound=False, counts_for_score=False), {"synthcompound"}
    )
    assert not allowed.counts_for_score


def test_l3_requires_a_radiation_type_and_l2_forbids_one() -> None:
    with pytest.raises(cu.CurationError, match="must state the radiation type"):
        cu.parse_evidence(evidence(radiation_type=None), {"synthcompound"})
    with pytest.raises(cu.CurationError, match="only L3 evidence records a radiation type"):
        cu.parse_evidence(
            evidence(evidence_level="L2_process", radiation_type="Gamma"), {"synthcompound"}
        )


def test_d1_rewards_structural_confirmation_only() -> None:
    strong = cu.parse_constituent(constituent())
    weak = cu.parse_constituent(
        constituent(reports=[report(identification_strength="library_match_only")])
    )
    none = cu.parse_constituent(
        constituent(
            extraction_category="indirect_or_unconfirmed",
            reports=[report(is_review=True, identification_strength="not_stated")],
        )
    )
    assert rk.d1_moringa_identity(strong)[0] == 2
    assert rk.d1_moringa_identity(weak)[0] == 1
    assert rk.d1_moringa_identity(none)[0] == 0


def test_d1_ignores_reports_from_other_plant_parts() -> None:
    roots_only = cu.parse_constituent(
        constituent(
            plant_part="other",
            extraction_category="indirect_or_unconfirmed",
            reports=[report(plant_part="other")],
        )
    )
    assert rk.d1_moringa_identity(roots_only)[0] == 0


# ------------------------------------------------------ scoring: D2 and no analogy points


def test_d2_requires_ionising_radiation_for_the_top_bands() -> None:
    one_group = curated([constituent()], [evidence()])
    two_groups = curated(
        [constituent()],
        [evidence(), evidence(evidence_id="SYN-02", research_group="Group C")],
    )
    process_only = curated(
        [constituent()],
        [evidence(evidence_level="L2_process", radiation_type=None, radiation_dose_gy=None)],
    )
    nothing = curated([constituent()], [])
    assert rk.d2_radiation_biology(rk.scored_items(two_groups.evidence))[0] == 3
    assert rk.d2_radiation_biology(rk.scored_items(one_group.evidence))[0] == 2
    assert rk.d2_radiation_biology(rk.scored_items(process_only.evidence))[0] == 1
    assert rk.d2_radiation_biology(rk.scored_items(nothing.evidence))[0] == 0


def test_two_papers_from_one_group_are_one_source_for_d2() -> None:
    """Repeated work from a single laboratory must not reach the two-group band."""
    same_group = curated(
        [constituent()],
        [evidence(), evidence(evidence_id="SYN-02", doi="10.0000/synthetic-c")],
    )
    points, reason = rk.d2_radiation_biology(rk.scored_items(same_group.evidence))
    assert points == 2 and "one group" in reason


def test_chemical_class_analogy_earns_no_points() -> None:
    """Evidence recorded against a different compound never reaches this compound."""
    pair = curated(
        [
            constituent(),
            constituent(compound_id="analogue", preferred_name="Analogue", pubchem_cid="2"),
        ],
        [evidence(compound_id="analogue", evidence_id="AN-01")],
    )
    scores = {s.compound_id: s for s in rk.rank(pair)}
    assert scores["synthcompound"].points["d2_radiation_biology"] == 0
    assert scores["analogue"].points["d2_radiation_biology"] == 2


# ------------------------------------------------------------------ scoring: D3 and D4


def test_d3_counts_each_research_group_once_across_both_files() -> None:
    """Duplicate sources: one group appearing in both files counts once."""
    shared = curated(
        [
            constituent(
                reports=[
                    report(research_group="Group A"),
                    report(doi="10.0000/dup", research_group="Group A"),
                ]
            )
        ],
        [evidence(research_group="Group A")],
    )
    points, reason = rk.d3_independent_sources(
        shared.constituents[0], rk.scored_items(shared.evidence)
    )
    assert points == 0 and "at most one independent group" in reason
    three = curated(
        [
            constituent(
                reports=[
                    report(research_group="Group A"),
                    report(doi="10.0000/x", research_group="Group B"),
                ]
            )
        ],
        [evidence(research_group="Group C")],
    )
    assert rk.d3_independent_sources(three.constituents[0], rk.scored_items(three.evidence))[0] == 2


def test_d4_needs_both_a_verified_identifier_and_a_published_concentration() -> None:
    full = curated([constituent()], [evidence()])
    no_dose = curated([constituent()], [evidence(concentration=None)])
    unverified = curated([constituent(identifier_verified_via="not_verified")], [evidence()])
    assert rk.d4_feasibility(full.constituents[0], rk.scored_items(full.evidence))[0] == 1
    assert rk.d4_feasibility(no_dose.constituents[0], rk.scored_items(no_dose.evidence))[0] == 0
    assert (
        rk.d4_feasibility(unverified.constituents[0], rk.scored_items(unverified.evidence))[0] == 0
    )


# ------------------------------------------------------------------------------- tiers


def test_tier_thresholds_and_the_not_assessable_rule() -> None:
    assert rk.assign_tier(
        {"d1_moringa_identity": 0, "d2_radiation_biology": 3,
         "d3_independent_sources": 2, "d4_feasibility": 1}, []
    )[0] == "not_assessable"  # fmt: skip
    assert rk.assign_tier(
        {"d1_moringa_identity": 2, "d2_radiation_biology": 3,
         "d3_independent_sources": 2, "d4_feasibility": 1}, []
    )[0] == "A"  # fmt: skip
    assert rk.assign_tier(
        {"d1_moringa_identity": 1, "d2_radiation_biology": 1,
         "d3_independent_sources": 2, "d4_feasibility": 0}, []
    )[0] == "B"  # fmt: skip
    assert rk.assign_tier(
        {"d1_moringa_identity": 2, "d2_radiation_biology": 0,
         "d3_independent_sources": 0, "d4_feasibility": 0}, []
    )[0] == "C"  # fmt: skip
    assert rk.assign_tier(
        {"d1_moringa_identity": 1, "d2_radiation_biology": 0,
         "d3_independent_sources": 0, "d4_feasibility": 0}, []
    )[0] == "not_prioritised"  # fmt: skip


def test_interesting_biology_cannot_rescue_an_unidentified_compound() -> None:
    unconfirmed = curated(
        [
            constituent(
                extraction_category="indirect_or_unconfirmed",
                reports=[report(identification_strength="not_stated", is_review=True)],
            )
        ],
        [evidence(), evidence(evidence_id="SYN-02", research_group="Group C")],
    )
    table = rk.ranking_table(unconfirmed)
    assert table.loc[0, "tier"] == "not_assessable"
    assert pd.isna(table.loc[0, "rank"])  # never enters the shortlist
    assert table.loc[0, "d2_radiation_biology"] == 3  # the evidence is still shown


def test_tumour_radioprotection_and_genotoxicity_cap_the_tier() -> None:
    for liability in ("radioprotection_tumour", "genotoxic"):
        flagged = curated(
            [constituent()],
            [
                evidence(),
                evidence(evidence_id="SYN-02", research_group="Group C", direction=liability),
            ],
        )
        score = rk.rank(flagged)[0]
        assert score.total >= 6, "would otherwise reach tier A"
        assert score.tier == rk.LIABILITY_CAP
        assert "capped" in score.tier_reason and liability in score.tier_reason[:200]
        assert score.liabilities


def test_every_tier_label_is_exploratory() -> None:
    for tier in ("A", "B", "C"):
        assert "exploratory" in rk.TIER_LABEL[tier]
    for word in ("radioprotect", "radiosensitis", "efficacy", "potency"):
        assert not any(word in label for label in rk.TIER_LABEL.values())


# ----------------------------------------------------------- determinism and ordering


def test_ranking_is_deterministic_and_independent_of_input_order() -> None:
    records = [
        constituent(compound_id=f"c{i}", preferred_name=f"Compound {i}", pubchem_cid=str(i))
        for i in range(4)
    ]
    items = [
        evidence(evidence_id=f"E{i}", compound_id=f"c{i}", research_group=f"G{i}") for i in range(4)
    ]
    forward = rk.ranking_table(curated(records, items))
    backward = rk.ranking_table(curated(records[::-1], items[::-1]))
    pd.testing.assert_frame_equal(forward, backward)
    assert list(forward["rank"]) == [1, 2, 3, 4]
    assert forward["rank"].dtype == "Int64"  # nullable integer, blank for unranked rows


def test_ties_break_by_name_not_by_position() -> None:
    records = [
        constituent(compound_id="zeta", preferred_name="Zeta", pubchem_cid="1"),
        constituent(compound_id="alpha", preferred_name="Alpha", pubchem_cid="2"),
    ]
    items = [
        evidence(evidence_id="E1", compound_id="zeta", research_group="G1"),
        evidence(evidence_id="E2", compound_id="alpha", research_group="G1"),
    ]
    table = rk.ranking_table(curated(records, items))
    assert list(table["preferred_name"]) == ["Alpha", "Zeta"]
    assert table["total_score"].nunique() == 1


def test_points_never_exceed_their_maximum() -> None:
    many = curated(
        [constituent()],
        [
            evidence(evidence_id=f"E{i}", research_group=f"G{i}", process_category="apoptosis")
            for i in range(8)
        ],
    )
    score = rk.rank(many)[0]
    for name, value in score.points.items():
        assert 0 <= value <= rk.MAX_POINTS[name]
    assert score.total <= rk.TOTAL_POINTS


def test_every_point_carries_a_justification() -> None:
    score = rk.rank(curated([constituent()], [evidence()]))[0]
    assert set(score.reasons) == set(score.points)
    assert all(reason.strip() for reason in score.reasons.values())


# -------------------------------------------------------------- pathway-overlap rules


def test_overlap_only_reports_genes_a_study_actually_measured() -> None:
    gene_sets = {
        "HALLMARK_P53_PATHWAY": ("TP53", "CDKN1A", "MDM2"),
        "HALLMARK_DNA_REPAIR": ("XRCC1", "LIG1"),
    }
    base = curated([constituent()], [evidence()])  # measured TP53, BAX
    table = rp.pathway_overlap(base, gene_sets, ["HALLMARK_P53_PATHWAY", "HALLMARK_DNA_REPAIR"])
    assert list(table["gene_set"]) == ["HALLMARK_P53_PATHWAY"]  # no DNA-repair row invented
    assert table.loc[0, "overlapping_genes"] == "TP53"
    assert table.loc[0, "n_overlapping_genes"] == 1
    assert table.loc[0, "evidence_ids"] == "SYN-01"
    assert "not evidence" in table.loc[0, "interpretation_limit"]


def test_a_compound_with_no_measured_genes_gets_no_overlap_row() -> None:
    empty = curated([constituent()], [evidence(genes_measured=[])])
    table = rp.pathway_overlap(empty, {"HALLMARK_P53_PATHWAY": ("TP53",)},
                               ["HALLMARK_P53_PATHWAY"])  # fmt: skip
    assert table.empty and "compound_id" in table.columns


def test_unscored_evidence_contributes_no_overlap() -> None:
    extract_only = curated(
        [constituent()],
        [evidence(purified_compound=False, counts_for_score=False)],
    )
    table = rp.pathway_overlap(extract_only, {"HALLMARK_P53_PATHWAY": ("TP53",)},
                               ["HALLMARK_P53_PATHWAY"])  # fmt: skip
    assert table.empty


def test_overlap_refuses_a_gene_set_missing_from_the_gmt() -> None:
    with pytest.raises(cu.CurationError, match="absent from the GMT"):
        rp.pathway_overlap(curated([constituent()], [evidence()]), {}, ["HALLMARK_P53_PATHWAY"])


def test_prioritised_sets_follow_the_triage_tiers_and_rank() -> None:
    candidates = pd.DataFrame(
        {
            "rank": [2, 1, 3],
            "gene_set": ["HALLMARK_B", "HALLMARK_A", "HALLMARK_C"],
            "tier": ["C", "C", "not_prioritised"],
        }
    )
    assert rp.prioritised_gene_sets(candidates, ("A", "B", "C")) == ["HALLMARK_A", "HALLMARK_B"]


# ----------------------------------------------------------- provenance and the tables


def test_tables_preserve_provenance_for_every_assertion(tmp_path: Path) -> None:
    a, b = write_pair(tmp_path, [constituent()], [evidence()])
    out = rp.write_compound_tables(a, b, tmp_path / "compounds_v1")
    inventory = pd.read_csv(out / "table_c1_constituent_inventory.csv")
    items = pd.read_csv(out / "table_c2_biology_evidence.csv")
    for table, columns in (
        (
            inventory,
            [
                "citation",
                "doi",
                "doi_verified_via",
                "reading_depth",
                "research_group",
                "identification_strength",
                "solvent_or_fraction",
            ],
        ),
        (
            items,
            [
                "citation",
                "doi",
                "doi_verified_via",
                "reading_depth",
                "research_group",
                "limitation",
                "direction",
            ],
        ),
    ):
        for column in columns:
            assert column in table.columns
            assert (
                table[column].notna().all() and (table[column].astype(str).str.strip() != "").all()
            )
    record = json.loads((out / "compound_record.json").read_text())
    assert record["inputs_sha256"][str(a)] and record["inputs_sha256"][str(b)]
    assert record["scoring"]["analogy_points"].startswith("none")
    assert record["scoring"]["total_points"] == rk.TOTAL_POINTS
    assert "hypothesis-generating" in record["statement"]


def test_published_ranking_csv_leaves_unranked_rows_blank(tmp_path: Path) -> None:
    """The nullable-integer rank must still be written as an empty field, not 'NA'."""
    records = [
        constituent(),
        constituent(
            compound_id="unranked",
            preferred_name="Unranked",
            pubchem_cid="9",
            extraction_category="indirect_or_unconfirmed",
            reports=[report(is_review=True, identification_strength="not_stated")],
        ),
    ]
    a, b = write_pair(tmp_path, records, [evidence()])
    out = rp.write_compound_tables(a, b, tmp_path / "compounds_v1")
    text = (out / "table_c3_candidate_ranking.csv").read_text(encoding="utf-8")
    assert "NA," not in text and "<NA>" not in text
    reread = pd.read_csv(out / "table_c3_candidate_ranking.csv")
    ranked = reread[reread["tier"].isin(["A", "B", "C"])]
    assert ranked["rank"].notna().all()
    assert reread.loc[reread["tier"] == "not_assessable", "rank"].isna().all()


def test_tables_are_write_once(tmp_path: Path) -> None:
    a, b = write_pair(tmp_path, [constituent()], [evidence()])
    rp.write_compound_tables(a, b, tmp_path / "compounds_v1")
    with pytest.raises(FileExistsError):
        rp.write_compound_tables(a, b, tmp_path / "compounds_v1")


def test_writing_the_tables_twice_gives_identical_bytes(tmp_path: Path) -> None:
    a, b = write_pair(tmp_path, [constituent()], [evidence()])
    first = rp.write_compound_tables(a, b, tmp_path / "one")
    second = rp.write_compound_tables(a, b, tmp_path / "two")
    for name in ("table_c1_constituent_inventory.csv", "table_c2_biology_evidence.csv",
                 "table_c3_candidate_ranking.csv"):  # fmt: skip
        assert (first / name).read_bytes() == (second / name).read_bytes()


def test_duplicate_ids_are_refused(tmp_path: Path) -> None:
    a, b = write_pair(tmp_path, [constituent(), constituent()], [])
    with pytest.raises(cu.CurationError, match="duplicate compound_id"):
        cu.load_curated(a, b)
    other = tmp_path / "other"
    other.mkdir()
    a, b = write_pair(other, [constituent()], [evidence(), evidence()])
    with pytest.raises(cu.CurationError, match="duplicate evidence_id"):
        cu.load_curated(a, b)


# --------------------------------------------------- the real curated files must be valid


@pytest.mark.skipif(not REAL_CONSTITUENTS.is_file(), reason="curated files not present")
def test_the_curated_files_parse_and_obey_the_rules() -> None:
    real = cu.load_curated(REAL_CONSTITUENTS, REAL_EVIDENCE)
    assert real.constituents and real.evidence
    for item in real.evidence:
        if item.counts_for_score:
            assert item.purified_compound and not item.is_review
            assert item.evidence_level in ("L3_radiation", "L2_process")
    for compound in real.constituents:
        if compound.extraction_category == "dcm_documented":
            assert compound.dcm_reports
    table = rk.ranking_table(real)
    assert (table["total_score"] <= rk.TOTAL_POINTS).all()
    assert set(table["tier"]) <= set(rk.TIERS)
    # a compound without a primary Moringa identification is never shortlisted
    assert table.loc[table["d1_moringa_identity"] == 0, "rank"].isna().all()
    assert (table.loc[table["d1_moringa_identity"] == 0, "tier"] == "not_assessable").all()
    # liabilities never reach tier A or B
    flagged = table["liability_flags"].astype(str).str.strip() != ""
    assert not table.loc[flagged, "tier"].isin(["A", "B"]).any()


@pytest.mark.skipif(not REAL_CONSTITUENTS.is_file(), reason="curated files not present")
def test_a_weak_identification_is_down_weighted_not_excluded() -> None:
    """Regression guard for a corrected error (2026-10-22).

    Quercetin and kaempferol were described as "cannot be ranked". That was an unsupported
    exclusion: both have primary seed or leaf reports, so the prespecified D1 rule gives
    them 1 (library-match band), not 0. Only a compound with NO primary seed or leaf report
    is not assessable. The rubric must keep down-weighting these rather than excluding them.
    """
    real = cu.load_curated(REAL_CONSTITUENTS, REAL_EVIDENCE)
    table = rk.ranking_table(real).set_index("compound_id")
    for compound_id in ("quercetin", "kaempferol"):
        if compound_id not in table.index:
            pytest.skip(f"{compound_id} not in the inventory")
        row = table.loc[compound_id]
        assert row["d1_moringa_identity"] == 1, "library-match identification scores 1, not 0"
        assert row["tier"] != "not_assessable", "a weak identification is not no identification"
        assert pd.notna(row["rank"]), "an assessable compound carries a rank"
        assert row["extraction_category"] == "indirect_or_unconfirmed"
        assert "dichloromethane" in row["main_limitation"]


@pytest.mark.skipif(not REAL_CONSTITUENTS.is_file(), reason="curated files not present")
def test_benzyl_isothiocyanate_is_recorded_but_never_ranked() -> None:
    """The class analogy must stay out of the shortlist (investigator decision)."""
    real = cu.load_curated(REAL_CONSTITUENTS, REAL_EVIDENCE)
    table = rk.ranking_table(real).set_index("compound_id")
    if "benzyl_isothiocyanate" not in table.index:
        pytest.skip("compound not in the inventory")
    row = table.loc["benzyl_isothiocyanate"]
    assert row["tier"] == "not_assessable" and pd.isna(row["rank"])
    assert row["extraction_category"] == "indirect_or_unconfirmed"
