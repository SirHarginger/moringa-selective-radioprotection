"""Write the compound-evidence tables from the curated files (investigator-run).

Outputs, into a write-once folder ``results/tables/<run_id>/compounds_v<N>/``:

    table_c1_constituent_inventory.csv   one row per compound x analytical report
    table_c2_biology_evidence.csv        one row per biology evidence item
    table_c3_candidate_ranking.csv       one row per compound: points, total, tier
    table_c4_pathway_overlap.csv         compound genes x prioritised Hallmark gene sets
    compound_record.json                 provenance: inputs, checksums, rules, counts

Nothing here fits, trains, tunes or evaluates a model. ``table_c4`` is a set
intersection between the genes a published study measured and the members of a Hallmark
gene set; it creates a research hypothesis and is **not** evidence that a compound
modifies clonogenic SF2.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from radiosensitivity_ml.compounds import ranking as rk
from radiosensitivity_ml.compounds.curation import (
    CuratedEvidence,
    CurationError,
    load_curated,
)
from radiosensitivity_ml.data.provenance import file_sha256, write_json, write_once_folder

OVERLAP_STATEMENT = (
    "Overlap between the genes a published experiment measured for a compound and the "
    "members of a Hallmark gene set whose score was ranked by the exploratory "
    "explainability analysis. It marks where a compound and a model-highlighted gene set "
    "touch the same genes, which is a hypothesis to test. It is not evidence that the "
    "compound modifies the gene set, the pathway, or clonogenic SF2, and the gene-set "
    "ranking itself was capped at tier C (no prediction gain was formally shown and no "
    "negative-control draws were run)."
)


def inventory_table(curated: CuratedEvidence) -> pd.DataFrame:
    """Table C1: every analytical report, with its solvent, method and verification."""
    rows = []
    for compound in curated.constituents:
        for i, report in enumerate(compound.reports, start=1):
            rows.append(
                {
                    "compound_id": compound.compound_id,
                    "preferred_name": compound.preferred_name,
                    "synonyms": "; ".join(compound.synonyms),
                    "pubchem_cid": compound.pubchem_cid or "",
                    "inchikey": compound.inchikey or "",
                    "molecular_formula": compound.molecular_formula or "",
                    "identifier_verified_via": compound.identifier_verified_via,
                    "chemical_class": compound.chemical_class,
                    "compound_plant_part": compound.plant_part,
                    "extraction_category": compound.extraction_category,
                    "identity_caveat": compound.identity_caveat or "",
                    "report_number": i,
                    "report_plant_part": report.plant_part,
                    "solvent_or_fraction": report.solvent_or_fraction or "NOT STATED",
                    "is_dichloromethane": report.is_dcm,
                    "identification_method": report.identification_method or "NOT STATED",
                    "identification_strength": report.identification_strength,
                    "citation": report.citation.strip(),
                    "doi": report.doi or "",
                    "pmid": report.pmid or "",
                    "doi_verified_via": report.doi_verified_via,
                    "reading_depth": report.reading_depth,
                    "is_review": report.is_review,
                    "research_group": report.research_group,
                    "quoted_wording": (report.quoted_wording or "").strip(),
                    "report_notes": (report.notes or "").strip(),
                }
            )
    return (
        pd.DataFrame(rows)
        .sort_values(["compound_id", "report_number"], kind="stable")
        .reset_index(drop=True)
    )


def evidence_table(curated: CuratedEvidence) -> pd.DataFrame:
    """Table C2: every biology evidence item, with model, dose, direction and genes."""
    names = {c.compound_id: c.preferred_name for c in curated.constituents}
    rows = []
    for item in curated.evidence:
        rows.append(
            {
                "evidence_id": item.evidence_id,
                "compound_id": item.compound_id,
                "preferred_name": names[item.compound_id],
                "evidence_level": item.evidence_level,
                "process_category": item.process_category,
                "model_system": item.model_system,
                "tissue_class": item.tissue_class,
                "species": item.species or "NOT STATED",
                "radiation_type": item.radiation_type or "none",
                "radiation_dose_gy": item.radiation_dose_gy or "NOT STATED",
                "concentration": item.concentration or "NOT STATED",
                "exposure_timing": item.exposure_timing or "NOT STATED",
                "endpoints": item.endpoints.strip(),
                "genes_measured": "; ".join(item.genes_measured),
                "n_genes_measured": len(item.genes_measured),
                "direction": item.direction,
                "is_liability": item.is_liability,
                "purified_compound": item.purified_compound,
                "counts_for_score": item.counts_for_score,
                "research_group": item.research_group,
                "citation": item.citation.strip(),
                "doi": item.doi or "",
                "pmid": item.pmid or "",
                "doi_verified_via": item.doi_verified_via,
                "reading_depth": item.reading_depth,
                "is_review": item.is_review,
                "limitation": item.limitation.strip(),
                "notes": (item.notes or "").strip(),
            }
        )
    return (
        pd.DataFrame(rows)
        .sort_values(["compound_id", "evidence_id"], kind="stable")
        .reset_index(drop=True)
    )


def pathway_overlap(
    curated: CuratedEvidence,
    gene_sets: Mapping[str, Sequence[str]],
    prioritised: Sequence[str],
) -> pd.DataFrame:
    """Table C4: measured genes of each compound against each prioritised gene set.

    One row per (compound, gene set) with at least one shared gene. Rows name the shared
    genes and the evidence items they came from, so every cell is traceable.
    """
    missing = [g for g in prioritised if g not in gene_sets]
    if missing:
        raise CurationError(f"prioritised gene sets absent from the GMT: {missing}")
    names = {c.compound_id: c.preferred_name for c in curated.constituents}
    rows = []
    for compound_id, preferred in names.items():
        items = [e for e in curated.for_compound(compound_id) if e.counts_for_score]
        measured = {g for e in items for g in e.genes_measured}
        if not measured:
            continue
        for gene_set in prioritised:
            shared = sorted(measured & set(gene_sets[gene_set]))
            if not shared:
                continue
            sources = sorted(e.evidence_id for e in items if set(e.genes_measured) & set(shared))
            rows.append(
                {
                    "compound_id": compound_id,
                    "preferred_name": preferred,
                    "gene_set": gene_set,
                    "n_overlapping_genes": len(shared),
                    "n_genes_measured": len(measured),
                    "n_genes_in_set": len(set(gene_sets[gene_set])),
                    "overlapping_genes": "; ".join(shared),
                    "evidence_ids": "; ".join(sources),
                    "interpretation_limit": OVERLAP_STATEMENT,
                }
            )
    columns = ["compound_id", "preferred_name", "gene_set", "n_overlapping_genes",
               "n_genes_measured", "n_genes_in_set", "overlapping_genes", "evidence_ids",
               "interpretation_limit"]  # fmt: skip
    table = pd.DataFrame(rows, columns=columns)
    return table.sort_values(
        ["compound_id", "n_overlapping_genes", "gene_set"],
        ascending=[True, False, True],
        kind="stable",
    ).reset_index(drop=True)


def prioritised_gene_sets(pathway_candidates: pd.DataFrame, tiers: Sequence[str]) -> list[str]:
    """Gene sets whose triage tier is in ``tiers``, in the triage's own rank order."""
    needed = {"gene_set", "tier"}
    if not needed <= set(pathway_candidates.columns):
        raise CurationError(f"pathway_candidates needs {sorted(needed)}")
    chosen = pathway_candidates[pathway_candidates["tier"].astype(str).isin(tiers)]
    if "rank" in chosen.columns:
        chosen = chosen.sort_values("rank", kind="stable")
    return [str(g) for g in chosen["gene_set"]]


def tier_counts(ranking: pd.DataFrame) -> dict[str, int]:
    return {tier: int((ranking["tier"] == tier).sum()) for tier in rk.TIERS}


def write_compound_tables(
    constituents_path: Path,
    evidence_path: Path,
    out_dir: Path,
    gene_sets: Mapping[str, Sequence[str]] | None = None,
    pathway_candidates: pd.DataFrame | None = None,
    overlap_tiers: Sequence[str] = ("A", "B", "C"),
    extra_provenance: Mapping[str, object] | None = None,
) -> Path:
    """Validate the curated files and write all compound tables into a new folder."""
    curated = load_curated(constituents_path, evidence_path)
    inventory = inventory_table(curated)
    evidence = evidence_table(curated)
    ranked = rk.ranking_table(curated)
    prioritised: list[str] = []
    overlap = pd.DataFrame()
    if gene_sets is not None and pathway_candidates is not None:
        prioritised = prioritised_gene_sets(pathway_candidates, overlap_tiers)
        overlap = pathway_overlap(curated, gene_sets, prioritised)

    def build(staging: Path) -> None:
        inventory.to_csv(staging / "table_c1_constituent_inventory.csv", index=False)
        evidence.to_csv(staging / "table_c2_biology_evidence.csv", index=False)
        ranked.to_csv(staging / "table_c3_candidate_ranking.csv", index=False)
        if not overlap.empty or prioritised:
            overlap.to_csv(staging / "table_c4_pathway_overlap.csv", index=False)
        write_json(
            staging / "compound_record.json",
            {
                "utc": datetime.now(UTC).isoformat(),
                "script": "scripts/make_compound_tables.py",
                "inputs_sha256": {
                    str(constituents_path): file_sha256(constituents_path),
                    str(evidence_path): file_sha256(evidence_path),
                },
                "curation_records": dict(curated.sources),
                "scoring": {
                    "dimensions": dict(rk.MAX_POINTS),
                    "total_points": rk.TOTAL_POINTS,
                    "tier_rules": [
                        {"tier": t, "min_total": a, "min_d1": b, "min_d2": c}
                        for t, a, b, c in rk.TIER_RULES
                    ],
                    "liability_cap": rk.LIABILITY_CAP,
                    "tie_break": rk.TIE_BREAK,
                    "analogy_points": "none; chemical-class analogy never scores",
                },
                "counts": {
                    "constituents": len(curated.constituents),
                    "analytical_reports": len(inventory),
                    "dcm_documented_compounds": int(
                        (ranked["extraction_category"] == "dcm_documented").sum()
                    ),
                    "evidence_items": len(curated.evidence),
                    "scored_evidence_items": int(evidence["counts_for_score"].sum()),
                    "liability_items": int(evidence["is_liability"].sum()),
                    "shortlist": int((ranked["rank"] != "").sum()),
                    "tiers": tier_counts(ranked),
                },
                "pathway_overlap": {
                    "prioritised_gene_sets": prioritised,
                    "overlap_tiers": list(overlap_tiers),
                    "rows": len(overlap),
                    "statement": OVERLAP_STATEMENT,
                },
                "statement": rk.STATEMENT,
                **dict(extra_provenance or {}),
            },
        )

    write_once_folder(out_dir, build)
    return out_dir


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))
