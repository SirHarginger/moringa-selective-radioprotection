"""Load and validate the curated compound evidence files (strict; nothing is inferred).

Two YAML files carry every assertion, each with its own source:

``data/compounds/moringa_constituents.yaml``
    One record per compound: identity (name, synonyms, PubChem CID, InChIKey, class), the
    plant part, and one or more *constituent reports* (a primary analytical study that
    identified the compound in Moringa seed or leaf, with the solvent/fraction actually
    used and the identification method).

``data/compounds/compound_biology_evidence.yaml``
    One record per evidence item: a primary experimental study of the PURIFIED compound,
    its model system, radiation (if any), concentration, endpoints, measured genes and the
    reported direction.

Validation refuses: unknown fields, unknown enumeration values, evidence for an unknown
compound, missing provenance, a review used as evidence, and a compound whose identifiers
are absent without a recorded reason. Missing information must be written as ``null`` with
an explicit note; it is never silently defaulted.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

import yaml

# ---------------------------------------------------------------- enumerations (frozen)

# How well the compound's presence in Moringa seed/leaf is documented, relative to the
# dichloromethane (DCM) seed and leaf extracts of the motivating manuscript.
EXTRACTION_CATEGORIES = (
    "dcm_documented",  # identified in a DCM extract or DCM fraction of seed or leaf
    "seed_or_leaf_other_solvent",  # primary analytical evidence, seed/leaf, other solvent
    "indirect_or_unconfirmed",  # review-only, tentative, or another plant part
)
# Strength of the analytical identification in the cited primary study.
IDENTIFICATION_STRENGTH = (
    "isolation_nmr",  # isolated, structure confirmed by NMR/MS
    "reference_standard",  # chromatography + authentic standard (retention + spectrum)
    "library_match_only",  # GC-MS/LC-MS spectral library match, no standard
    "not_stated",
)
PLANT_PARTS = ("seed", "leaf", "both", "other", "not_stated")
# Evidence level for the link to radiation-response biology. L3 requires ionising
# radiation; UV and non-ionising exposures are NOT L3.
EVIDENCE_LEVELS = (
    "L3_radiation",  # purified compound + ionising radiation + radiation-response endpoint
    "L2_process",  # purified compound modulating a relevant process, no radiation
    "L1_indirect",  # recorded for transparency; never scored
)
PROCESS_CATEGORIES = (
    "dna_damage",
    "dna_repair",
    "cell_cycle",
    "apoptosis",
    "oxidative_stress_response",
    "proliferation",
    "hypoxia_signalling",
    "oxidative_phosphorylation",
    "p53_pathway",
    "animal_survival",
    "other",
)
# What the study reported. Radioprotection and radiosensitisation are never merged, and
# the cell type protected is always part of the direction.
DIRECTIONS = (
    "radioprotection_normal",
    "radioprotection_tumour",  # liability: would oppose radiotherapy
    "radiosensitisation_tumour",
    "no_effect",
    "mixed",
    "process_modulation_no_radiation",
    "genotoxic",  # liability: compound itself damages DNA
)
# Directions that count against a candidate and cap its tier.
LIABILITY_DIRECTIONS = ("radioprotection_tumour", "genotoxic")
READING_DEPTH = ("abstract", "full_text")
VERIFIED_VIA = ("crossref", "europepmc", "pubchem", "publisher", "not_verified")

CONSTITUENT_FIELDS = {
    "compound_id", "preferred_name", "synonyms", "pubchem_cid", "inchikey",
    "molecular_formula", "chemical_class", "plant_part", "extraction_category",
    "identity_caveat", "identifier_verified_via", "reports", "notes",
}  # fmt: skip
REPORT_FIELDS = {
    "citation", "doi", "pmid", "doi_verified_via", "reading_depth", "is_review",
    "plant_part", "solvent_or_fraction", "identification_method",
    "identification_strength", "is_dcm", "research_group", "quoted_wording", "notes",
}  # fmt: skip
EVIDENCE_FIELDS = {
    "evidence_id", "compound_id", "evidence_level", "process_category", "citation", "doi",
    "pmid", "doi_verified_via", "reading_depth", "is_review", "purified_compound",
    "model_system", "tissue_class", "species", "radiation_type", "radiation_dose_gy",
    "concentration", "exposure_timing", "endpoints", "genes_measured", "direction",
    "research_group", "limitation", "counts_for_score", "notes",
}  # fmt: skip


class CurationError(ValueError):
    """Raised when a curated evidence file is incomplete, inconsistent or unsupported."""


@dataclass(frozen=True)
class ConstituentReport:
    """One primary analytical study reporting the compound in Moringa seed or leaf."""

    citation: str
    doi: str | None
    pmid: str | None
    doi_verified_via: str
    reading_depth: str
    is_review: bool
    plant_part: str
    solvent_or_fraction: str | None
    identification_method: str | None
    identification_strength: str
    is_dcm: bool
    research_group: str  # corresponding-author group: several papers from one group
    quoted_wording: str | None = None  # count as ONE independent source
    notes: str | None = None


@dataclass(frozen=True)
class Constituent:
    """Identity and Moringa-provenance of one curated constituent."""

    compound_id: str
    preferred_name: str
    chemical_class: str
    plant_part: str
    extraction_category: str
    reports: tuple[ConstituentReport, ...]
    synonyms: tuple[str, ...] = ()
    pubchem_cid: str | None = None
    inchikey: str | None = None
    molecular_formula: str | None = None
    identity_caveat: str | None = None
    identifier_verified_via: str = "not_verified"
    notes: str | None = None

    @property
    def primary_reports(self) -> tuple[ConstituentReport, ...]:
        """Reports that are primary studies (reviews are never counted as evidence)."""
        return tuple(r for r in self.reports if not r.is_review)

    @property
    def dcm_reports(self) -> tuple[ConstituentReport, ...]:
        return tuple(r for r in self.primary_reports if r.is_dcm)


@dataclass(frozen=True)
class BiologyEvidence:
    """One primary experimental study of the purified compound."""

    evidence_id: str
    compound_id: str
    evidence_level: str
    process_category: str
    citation: str
    doi: str | None
    pmid: str | None
    doi_verified_via: str
    reading_depth: str
    is_review: bool
    purified_compound: bool
    model_system: str
    tissue_class: str
    species: str | None
    radiation_type: str | None
    radiation_dose_gy: str | None
    concentration: str | None
    exposure_timing: str | None
    endpoints: str
    direction: str
    research_group: str
    limitation: str
    counts_for_score: bool
    genes_measured: tuple[str, ...] = ()
    notes: str | None = None

    @property
    def is_liability(self) -> bool:
        return self.direction in LIABILITY_DIRECTIONS


@dataclass(frozen=True)
class CuratedEvidence:
    """Everything the ranking needs, already validated."""

    constituents: tuple[Constituent, ...]
    evidence: tuple[BiologyEvidence, ...]
    sources: Mapping[str, str] = field(default_factory=dict)

    def for_compound(self, compound_id: str) -> tuple[BiologyEvidence, ...]:
        return tuple(e for e in self.evidence if e.compound_id == compound_id)


def _check_fields(record: Mapping[str, object], allowed: set[str], where: str) -> None:
    unknown = sorted(set(record) - allowed)
    if unknown:
        raise CurationError(f"{where}: unknown field(s) {unknown}")


def _check_enum(value: object, allowed: Sequence[str], where: str) -> str:
    if value not in allowed:
        raise CurationError(f"{where}: {value!r} is not one of {list(allowed)}")
    return str(value)


def _require(record: Mapping[str, object], keys: Sequence[str], where: str) -> None:
    missing = [k for k in keys if k not in record]
    if missing:
        raise CurationError(f"{where}: missing required field(s) {missing}")


def _tuple(value: object, where: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise CurationError(f"{where}: expected a list, got {type(value).__name__}")
    return tuple(str(v) for v in value)


def parse_report(record: Mapping[str, object], where: str) -> ConstituentReport:
    _check_fields(record, REPORT_FIELDS, where)
    _require(record, ["citation", "doi_verified_via", "reading_depth", "is_review",
                      "plant_part", "identification_strength", "is_dcm",
                      "research_group"], where)  # fmt: skip
    is_dcm = bool(record["is_dcm"])
    solvent = record.get("solvent_or_fraction")
    if is_dcm and not solvent:
        raise CurationError(f"{where}: is_dcm requires the solvent/fraction wording")
    if is_dcm and bool(record["is_review"]):
        raise CurationError(f"{where}: a review cannot establish a DCM extract report")
    return ConstituentReport(
        citation=str(record["citation"]),
        doi=record.get("doi") and str(record["doi"]),
        pmid=record.get("pmid") and str(record["pmid"]),
        doi_verified_via=_check_enum(record["doi_verified_via"], VERIFIED_VIA, where),
        reading_depth=_check_enum(record["reading_depth"], READING_DEPTH, where),
        is_review=bool(record["is_review"]),
        plant_part=_check_enum(record["plant_part"], PLANT_PARTS, where),
        solvent_or_fraction=solvent and str(solvent),
        identification_method=record.get("identification_method")
        and str(record["identification_method"]),
        identification_strength=_check_enum(
            record["identification_strength"], IDENTIFICATION_STRENGTH, where
        ),
        is_dcm=is_dcm,
        research_group=str(record["research_group"]),
        quoted_wording=record.get("quoted_wording") and str(record["quoted_wording"]),
        notes=record.get("notes") and str(record["notes"]),
    )


def parse_constituent(record: Mapping[str, object]) -> Constituent:
    where = f"constituent {record.get('compound_id', '<no id>')!r}"
    _check_fields(record, CONSTITUENT_FIELDS, where)
    _require(record, ["compound_id", "preferred_name", "chemical_class", "plant_part",
                      "extraction_category", "reports"], where)  # fmt: skip
    reports = record["reports"]
    if not isinstance(reports, Sequence) or not reports:
        raise CurationError(f"{where}: at least one report is required")
    parsed = tuple(
        parse_report(r, f"{where} report {i + 1}")
        for i, r in enumerate(reports)  # type: ignore[arg-type]
    )
    category = _check_enum(record["extraction_category"], EXTRACTION_CATEGORIES, where)
    if category == "dcm_documented" and not any(r.is_dcm for r in parsed if not r.is_review):
        raise CurationError(f"{where}: extraction_category 'dcm_documented' needs a DCM report")
    if category != "indirect_or_unconfirmed" and not any(not r.is_review for r in parsed):
        raise CurationError(f"{where}: {category} needs at least one primary (non-review) report")
    if not record.get("pubchem_cid") and not record.get("identity_caveat"):
        raise CurationError(f"{where}: a missing PubChem CID needs an identity_caveat")
    return Constituent(
        compound_id=str(record["compound_id"]),
        preferred_name=str(record["preferred_name"]),
        chemical_class=str(record["chemical_class"]),
        plant_part=_check_enum(record["plant_part"], PLANT_PARTS, where),
        extraction_category=category,
        reports=parsed,
        synonyms=_tuple(record.get("synonyms"), f"{where} synonyms"),
        pubchem_cid=record.get("pubchem_cid") and str(record["pubchem_cid"]),
        inchikey=record.get("inchikey") and str(record["inchikey"]),
        molecular_formula=record.get("molecular_formula") and str(record["molecular_formula"]),
        identity_caveat=record.get("identity_caveat") and str(record["identity_caveat"]),
        identifier_verified_via=_check_enum(
            record.get("identifier_verified_via", "not_verified"), VERIFIED_VIA, where
        ),
        notes=record.get("notes") and str(record["notes"]),
    )


def parse_evidence(record: Mapping[str, object], known: set[str]) -> BiologyEvidence:
    where = f"evidence {record.get('evidence_id', '<no id>')!r}"
    _check_fields(record, EVIDENCE_FIELDS, where)
    _require(record, ["evidence_id", "compound_id", "evidence_level", "process_category",
                      "citation", "doi_verified_via", "reading_depth", "is_review",
                      "purified_compound", "model_system", "tissue_class", "endpoints",
                      "direction", "research_group", "limitation", "counts_for_score"],
             where)  # fmt: skip
    compound_id = str(record["compound_id"])
    if compound_id not in known:
        raise CurationError(f"{where}: unknown compound_id {compound_id!r}")
    level = _check_enum(record["evidence_level"], EVIDENCE_LEVELS, where)
    counts = bool(record["counts_for_score"])
    is_review, purified = bool(record["is_review"]), bool(record["purified_compound"])
    if counts and is_review:
        raise CurationError(f"{where}: a review may never count towards the score")
    if counts and not purified:
        raise CurationError(f"{where}: only purified-compound studies may count")
    if counts and level == "L1_indirect":
        raise CurationError(f"{where}: indirect evidence may never count")
    radiation_type = record.get("radiation_type")
    if level == "L3_radiation" and not radiation_type:
        raise CurationError(f"{where}: L3 evidence must state the radiation type")
    if level != "L3_radiation" and radiation_type:
        raise CurationError(f"{where}: only L3 evidence records a radiation type")
    return BiologyEvidence(
        evidence_id=str(record["evidence_id"]),
        compound_id=compound_id,
        evidence_level=level,
        process_category=_check_enum(record["process_category"], PROCESS_CATEGORIES, where),
        citation=str(record["citation"]),
        doi=record.get("doi") and str(record["doi"]),
        pmid=record.get("pmid") and str(record["pmid"]),
        doi_verified_via=_check_enum(record["doi_verified_via"], VERIFIED_VIA, where),
        reading_depth=_check_enum(record["reading_depth"], READING_DEPTH, where),
        is_review=is_review,
        purified_compound=purified,
        model_system=str(record["model_system"]),
        tissue_class=str(record["tissue_class"]),
        species=record.get("species") and str(record["species"]),
        radiation_type=radiation_type and str(radiation_type),
        radiation_dose_gy=record.get("radiation_dose_gy") and str(record["radiation_dose_gy"]),
        concentration=record.get("concentration") and str(record["concentration"]),
        exposure_timing=record.get("exposure_timing") and str(record["exposure_timing"]),
        endpoints=str(record["endpoints"]),
        direction=_check_enum(record["direction"], DIRECTIONS, where),
        research_group=str(record["research_group"]),
        limitation=str(record["limitation"]),
        counts_for_score=counts,
        genes_measured=_tuple(record.get("genes_measured"), f"{where} genes_measured"),
        notes=record.get("notes") and str(record["notes"]),
    )


def load_curated(constituents_path: Path, evidence_path: Path) -> CuratedEvidence:
    """Read and validate both curated files (raises ``CurationError`` on any problem)."""
    raw_c = yaml.safe_load(constituents_path.read_text(encoding="utf-8")) or {}
    raw_e = yaml.safe_load(evidence_path.read_text(encoding="utf-8")) or {}
    records = raw_c.get("constituents")
    if not records:
        raise CurationError(f"{constituents_path}: no constituents")
    constituents = tuple(parse_constituent(r) for r in records)
    ids = [c.compound_id for c in constituents]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        raise CurationError(f"{constituents_path}: duplicate compound_id {duplicates}")
    known = set(ids)
    items = tuple(parse_evidence(r, known) for r in raw_e.get("evidence", []))
    evidence_ids = [e.evidence_id for e in items]
    duplicates = sorted({i for i in evidence_ids if evidence_ids.count(i) > 1})
    if duplicates:
        raise CurationError(f"{evidence_path}: duplicate evidence_id {duplicates}")
    sources = {
        str(constituents_path): str(raw_c.get("curation_record", "")),
        str(evidence_path): str(raw_e.get("curation_record", "")),
    }
    return CuratedEvidence(constituents=constituents, evidence=items, sources=sources)
