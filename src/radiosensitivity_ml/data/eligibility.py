"""Eligibility, relationship groups and descriptive feasibility quantities (phase_01).

Definitions used in every output (docs/phase_01_remediation_report.md section 4):

- **record**: one CLARIFi row (one cell-line name and DepMap ID, one literature-median
  mSF2), keyed by its CLARIFi row number. It is not an experimental observation; the
  number of underlying SF2 measurements per record is unknown (O01.12).
- **relationship group (component)**: the connected set of records linked by a shared
  DepMap PatientID, a shared Cellosaurus candidate or RRID accession (primary or
  secondary), or a Cellosaurus parent (hi) or same-individual (oi) link, including
  links through Cellosaurus entries outside CLARIFi. Edge rule (conservative, decision
  D01.20): every Cellosaurus candidate links, even when the identity is ambiguous.
  This is the planned validation unit: a component is never split across folds.
  Component IDs (``G:<smallest node>``) are deterministic for fixed inputs but change
  when inputs change; never compare them across QC versions.
- **eligible record**: a record with no exclusion reason under the pre-fixed rules
  of configs/preprocessing.yaml.
- **n**: the number of components that contain at least one eligible record.
- **tissue**: the taxonomy label of a component (primary: DepMap OncotreeLineage).
- **T10** (named after the default threshold of 10): the number of tissues with at
  least ``min_components_per_tissue`` eligible components. Tissues below it are pooled
  as "other solid"; components whose records carry several labels ("MULTIPLE") are
  reported separately and never pooled. Pool membership is fixed globally from
  metadata (and outcome validity), not recomputed per fold.

Outcome information enters only as the record-level ``outcome_invalid`` flag, so pool
membership is weakly outcome-dependent through that flag (documented). These
quantities describe data sufficiency; they are not a power or precision analysis.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from radiosensitivity_ml.data import cellosaurus as cs
from radiosensitivity_ml.data import components as cp
from radiosensitivity_ml.data.qc_identifiers import COLUMN_ABSENT, VERIFIED, IdentityRow

SCHEMA_VERSION = 1
FALSEY = {"", "false", "no", "0"}
PROBLEMATIC_REASONS = {"problematic_cell_line", "component_problematic"}
# Values of IdentityRow.problematic that mean "no problem text available", not a problem.
PROBLEMATIC_SENTINELS = {"", "not_checked", "unknown"}
CANCER_CATEGORY = "Cancer cell line"  # observed in Cellosaurus responses, 2026-10-21
HUMAN_TAXON = "NCBI_TaxID=9606"  # observed in Cellosaurus responses, 2026-10-21
MULTIPLE = "MULTIPLE"
POOLED = "pooled (below min components)"  # "other solid" in the primary population


class ConfigError(ValueError):
    """Raised when the QC configuration is incomplete or inconsistent."""


@dataclass(frozen=True)
class QCConfig:
    """Pre-fixed eligibility and reporting rules (loaded from YAML)."""

    haematopoietic_lineages: tuple[str, ...]
    excluded_lineages: tuple[str, ...]
    solid_lineages: tuple[str, ...]
    non_cancer_markers: tuple[str, ...]
    lineage_span_scope: str
    propagate_problem_flags: bool
    min_components_per_tissue: int
    outer_folds: int
    moringa_lines: tuple[tuple[str, str], ...]
    provisional_floors: tuple[tuple[str, int, int], ...]


def string_list(value: object, name: str) -> tuple[str, ...]:
    """Require a list of strings (a bare string would otherwise split into characters)."""
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ConfigError(f"{name} must be a list of strings")
    return tuple(value)


ALLOWED_KEYS: dict[str, set[str]] = {
    "": {
        "schema_version",
        "inputs",
        "cellosaurus",
        "population",
        "tissue",
        "validation_structure",
        "provisional_floors",
        "moringa_lines",
        "output_dir",
    },
    "population": {
        "haematopoietic_lineages",
        "excluded_lineages",
        "solid_lineages",
        "non_cancer_markers",
        "lineage_span_scope",
        "propagate_problem_flags",
    },
    "tissue": {"primary_taxonomy", "min_components_per_tissue"},
    "validation_structure": {"outer_folds"},
}


def check_keys(data: Mapping[str, object]) -> None:
    """Reject unknown keys, so a typo cannot silently switch a rule off."""
    for section, allowed in ALLOWED_KEYS.items():
        block = data if not section else data.get(section)
        if isinstance(block, Mapping):
            unknown = sorted(set(block) - allowed)
            if unknown:
                raise ConfigError(f"unknown config keys in '{section or 'top level'}': {unknown}")


def positive_int(value: object, name: str) -> int:
    """Require an integer (a float such as 9.5 is rejected, not truncated)."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"{name} must be an integer")
    return value


def config_from_mapping(data: Mapping[str, object]) -> QCConfig:
    """Validate and build a QCConfig from a parsed YAML mapping."""
    check_keys(data)
    try:
        if data.get("schema_version", SCHEMA_VERSION) != SCHEMA_VERSION:
            raise ConfigError(f"schema_version must be {SCHEMA_VERSION}")
        population = dict(data["population"])  # type: ignore[call-overload]
        tissue = dict(data["tissue"])  # type: ignore[call-overload]
        if tissue.get("primary_taxonomy", "OncotreeLineage") != "OncotreeLineage":
            raise ConfigError("only primary_taxonomy: OncotreeLineage is implemented")
        structure = dict(data["validation_structure"])  # type: ignore[call-overload]
        moringa = dict(data["moringa_lines"])  # type: ignore[call-overload]
        floors = list(data.get("provisional_floors") or [])  # type: ignore[call-overload]
        config = QCConfig(
            haematopoietic_lineages=string_list(
                population["haematopoietic_lineages"], "haematopoietic_lineages"
            ),
            excluded_lineages=string_list(population["excluded_lineages"], "excluded_lineages"),
            solid_lineages=string_list(population["solid_lineages"], "solid_lineages"),
            non_cancer_markers=string_list(population["non_cancer_markers"], "non_cancer_markers"),
            lineage_span_scope=str(population["lineage_span_scope"]),
            propagate_problem_flags=population.get("propagate_problem_flags", False) is True,
            min_components_per_tissue=positive_int(
                tissue["min_components_per_tissue"], "min_components_per_tissue"
            ),
            outer_folds=positive_int(structure["outer_folds"], "outer_folds"),
            moringa_lines=tuple(sorted((str(k), str(v)) for k, v in moringa.items())),
            provisional_floors=tuple(
                (
                    str(f["name"]),
                    positive_int(f["min_n"], "min_n"),
                    positive_int(f["min_t10"], "min_t10"),
                )
                for f in floors
            ),
        )
    except (KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, ConfigError):
            raise
        raise ConfigError(f"incomplete QC configuration: {exc}") from exc
    overlap = set(config.solid_lineages) & (
        set(config.haematopoietic_lineages) | set(config.excluded_lineages)
    )
    if overlap:
        raise ConfigError(f"lineages both solid and excluded: {sorted(overlap)}")
    if config.lineage_span_scope not in {"record_eligible", "all_members"}:
        raise ConfigError("lineage_span_scope must be record_eligible or all_members")
    if not config.solid_lineages or config.min_components_per_tissue < 1 or config.outer_folds < 2:
        raise ConfigError("solid_lineages empty, min_components_per_tissue < 1 or outer_folds < 2")
    return config


# ------------------------------------------------------------------- relationships


CONFIRMED = "confirmed"
CANDIDATE = "candidate"


def relationship_edges(
    rows: Sequence[IdentityRow],
    cellosaurus: Mapping[str, cs.CellosaurusRecord] | None,
    mode: str = CONFIRMED,
) -> list[tuple[str, str]]:
    """Edges of the identity graph.

    Both modes: record <-> DepMap PatientID; Cellosaurus entry <-> each secondary
    accession, parent (hi) and same-individual (oi) (relationships Cellosaurus records).

    ``confirmed`` (primary grouping): record <-> its Cellosaurus entry only when exactly
    one entry cross-references the DepMap ID, and record <-> its DepMap RRID only when
    that RRID agrees with a Cellosaurus entry (primary or secondary accession).
    ``candidate`` (conservative sensitivity graph): record <-> every candidate entry and
    <-> its RRID, whether or not they agree.
    """
    if mode not in {CONFIRMED, CANDIDATE}:
        raise ValueError(f"unknown edge mode {mode!r}")
    edges: list[tuple[str, str]] = []
    for row in rows:
        node = cp.ach_node(row.depmap_id)
        if row.patient_id:
            edges.append((node, cp.patient_node(row.patient_id)))
        rrid = row.rrid.removeprefix("RRID:").strip()
        rrid_agrees = row.rrid_relation in {"primary", "secondary"}
        if rrid and (mode == CANDIDATE or rrid_agrees):
            edges.append((node, cp.cvcl_node(rrid)))
        if mode == CANDIDATE or len(row.cellosaurus_candidates) == 1:
            for accession in row.cellosaurus_candidates:
                edges.append((node, cp.cvcl_node(accession)))
    for record in (cellosaurus or {}).values():
        here = cp.cvcl_node(record.accession)
        for accession in record.secondary_accessions:
            edges.append((here, cp.cvcl_node(accession)))
        for accession in cs.linked_accessions(record):
            edges.append((here, cp.cvcl_node(accession)))
    return sorted(set(edges))


def unexpanded_accessions(cellosaurus: Mapping[str, cs.CellosaurusRecord]) -> set[str]:
    """Accessions cited by hi/oi whose own entry was not fetched (primary or secondary)."""
    known = set(cellosaurus) | {a for r in cellosaurus.values() for a in r.secondary_accessions}
    return {a for r in cellosaurus.values() for a in cs.linked_accessions(r)} - known


def parent_relationships(
    cellosaurus: Mapping[str, cs.CellosaurusRecord], rows: Sequence[IdentityRow]
) -> list[dict[str, str]]:
    """One row per Cellosaurus parent link among fetched entries."""
    clarifi_by_cvcl = clarifi_ids_by_accession(rows)
    out = []
    for record in sorted(cellosaurus.values(), key=lambda r: r.accession):
        for link in record.parents:
            out.append(
                {
                    "child_accession": record.accession,
                    "child_name": record.name,
                    "child_clarifi_depmap_ids": ";".join(clarifi_by_cvcl.get(record.accession, ())),
                    "parent_accession": link.accession,
                    "parent_name": link.name,
                    "parent_clarifi_depmap_ids": ";".join(clarifi_by_cvcl.get(link.accession, ())),
                    "parent_entry_fetched": str(link.accession in cellosaurus),
                    "source": "cellosaurus_hi",
                }
            )
    return out


def same_individual_relationships(
    cellosaurus: Mapping[str, cs.CellosaurusRecord] | None, rows: Sequence[IdentityRow]
) -> list[dict[str, str]]:
    """Unordered same-individual pairs from Cellosaurus oi and shared DepMap PatientID."""
    clarifi_by_cvcl = clarifi_ids_by_accession(rows)
    pairs: set[tuple[str, str, str]] = set()
    for record in (cellosaurus or {}).values():
        for link in record.same_individual:
            a, b = sorted((record.accession, link.accession))
            pairs.add((a, b, "cellosaurus_oi"))
    by_patient: dict[str, set[str]] = {}
    for row in rows:
        if row.patient_id:
            by_patient.setdefault(row.patient_id, set()).add(row.depmap_id)
    for members in by_patient.values():
        ordered = sorted(members)
        for i, a in enumerate(ordered):
            for b in ordered[i + 1 :]:
                pairs.add((a, b, "depmap_patient_id"))

    def clarifi_ids(identifier: str) -> str:
        if identifier.startswith("ACH-"):
            return identifier
        return ";".join(clarifi_by_cvcl.get(identifier, ()))

    return [
        {
            "identifier_a": a,
            "identifier_b": b,
            "source": source,
            "a_clarifi_depmap_ids": clarifi_ids(a),
            "b_clarifi_depmap_ids": clarifi_ids(b),
        }
        for a, b, source in sorted(pairs)
    ]


def clarifi_ids_by_accession(rows: Sequence[IdentityRow]) -> dict[str, tuple[str, ...]]:
    """Map each candidate Cellosaurus accession to the CLARIFi DepMap IDs that point to it."""
    index: dict[str, set[str]] = {}
    for row in rows:
        for accession in row.cellosaurus_candidates:
            index.setdefault(accession, set()).add(row.depmap_id)
    return {k: tuple(sorted(v)) for k, v in index.items()}


def assign_components(
    rows: Sequence[IdentityRow], cellosaurus: Mapping[str, cs.CellosaurusRecord] | None
) -> dict[str, str]:
    """Assign confirmed (primary) and candidate (sensitivity) component IDs in place.

    Returns the node assignment of the confirmed graph.
    """
    nodes = [cp.ach_node(row.depmap_id) for row in rows]
    assignment = cp.connected_components(nodes, relationship_edges(rows, cellosaurus))
    candidate = cp.connected_components(
        nodes, relationship_edges(rows, cellosaurus, mode=CANDIDATE)
    )
    sizes = Counter(assignment[cp.ach_node(row.depmap_id)] for row in rows)
    for row in rows:
        row.component_id = assignment[cp.ach_node(row.depmap_id)]
        row.component_records = sizes[row.component_id]
        row.candidate_component_id = candidate[cp.ach_node(row.depmap_id)]
    return assignment


# --------------------------------------------------------------------- eligibility


def record_reasons(row: IdentityRow, config: QCConfig, expression_checked: bool) -> list[str]:
    """Record-level exclusion reasons, in a fixed order."""
    reasons = []
    if row.identity_status != VERIFIED:
        reasons.append(f"identity_{row.identity_status}")
    if row.outcome_invalid:
        reasons.append("outcome_invalid_review")
    if expression_checked:
        if not row.has_default_rna_profile:
            reasons.append("no_default_rna_profile")
        if not row.in_expression_matrix:
            reasons.append("not_in_expression_matrix")
    lineage = row.oncotree_lineage
    if not lineage:
        reasons.append("lineage_missing_review")
    elif lineage in config.haematopoietic_lineages:
        reasons.append("lineage_haematopoietic")
    elif lineage in config.excluded_lineages:
        reasons.append("lineage_excluded")
    elif lineage not in config.solid_lineages:
        reasons.append("lineage_unrecognised_review")
    if row.engineered_model.strip().lower() not in FALSEY | {COLUMN_ABSENT}:
        reasons.append("engineered_model_review")
    disease_text = f"{row.oncotree_primary_disease} {row.depmap_model_type}".lower()
    if any(marker.lower() in disease_text for marker in config.non_cancer_markers):
        reasons.append("non_cancer_model_review")
    if row.cellosaurus_category and row.cellosaurus_category != CANCER_CATEGORY:
        reasons.append("cellosaurus_category_review")
    if row.cellosaurus_species and HUMAN_TAXON not in row.cellosaurus_species:
        reasons.append("non_human_review")
    if row.problematic not in PROBLEMATIC_SENTINELS:
        reasons.append("problematic_cell_line")
    return reasons


def apply_eligibility(
    rows: Sequence[IdentityRow],
    config: QCConfig,
    assignment: Mapping[str, str],
    cellosaurus: Mapping[str, cs.CellosaurusRecord] | None,
    expression_checked: bool,
) -> None:
    """Set exclusion reasons and eligibility flags on every row (in place).

    Requires ``assign_components`` to have run. Component-level rules:
    - records of a component carrying more than one lineage -> ``component_spans_lineages``.
      Which members count is set by ``lineage_span_scope`` (P01.13): ``record_eligible``
      (default: members with no record-level reason, so an excluded relative such as a
      haematopoietic line does not exclude a solid line) or ``all_members``;
    - a problem flag on any Cellosaurus entry in the component (including entries
      outside CLARIFi) is listed in ``component_flag_sources``; it adds
      ``component_problematic`` only when ``propagate_problem_flags`` is true;
    - a component touching an hi/oi accession that was never fetched may be
      incomplete -> ``component_links_not_expanded_review``.
    """
    if any(not row.component_id for row in rows):
        raise ValueError("assign_components must run before apply_eligibility")
    records = cellosaurus or {}
    problem_sources: dict[str, set[str]] = {}
    for record in records.values():
        node = cp.cvcl_node(record.accession)
        if record.problematic and node in assignment:
            problem_sources.setdefault(assignment[node], set()).add(record.accession)
    incomplete = {
        assignment[cp.cvcl_node(a)]
        for a in unexpanded_accessions(records)
        if cp.cvcl_node(a) in assignment
    }
    by_component: dict[str, list[IdentityRow]] = {}
    for row in rows:
        by_component.setdefault(row.component_id, []).append(row)
    for component, members in by_component.items():
        record_level = {id(m): record_reasons(m, config, expression_checked) for m in members}
        span_members = (
            members
            if config.lineage_span_scope == "all_members"
            else [m for m in members if not record_level[id(m)]]
        )
        lineages = {m.oncotree_lineage for m in span_members if m.oncotree_lineage}
        sources = tuple(sorted(problem_sources.get(component, ())))
        for row in members:
            reasons = list(record_level[id(row)])
            if len(lineages) > 1:
                reasons.append("component_spans_lineages")
            # A problem flag on a relative is reported (component_flag_sources) but only
            # excludes the record when propagation is switched on (investigator 2026-10-21).
            propagate = config.propagate_problem_flags
            if propagate and sources and "problematic_cell_line" not in reasons:
                reasons.append("component_problematic")
            if component in incomplete:
                reasons.append("component_links_not_expanded_review")
            row.component_flag_sources = sources
            row.exclusion_reasons = tuple(reasons)
            row.eligible_primary = not reasons
            row.eligible_retaining_problematic = set(reasons) <= PROBLEMATIC_REASONS


# ---------------------------------------------------------------- feasibility counts

TAXONOMIES: dict[str, Callable[[IdentityRow], str]] = {
    "oncotree_lineage": lambda r: r.oncotree_lineage,
    "oncotree_lineage_esophagus_stomach_split": lambda r: (
        f"Esophagus/Stomach: {r.oncotree_primary_disease}"
        if r.oncotree_lineage == "Esophagus/Stomach"
        else r.oncotree_lineage
    ),
    "ccle_suffix": lambda r: r.clarifi_tissue_suffix,
}

POPULATIONS: dict[str, Callable[[IdentityRow], bool]] = {
    "primary": lambda r: r.eligible_primary,
    "retaining_problematic": lambda r: r.eligible_retaining_problematic,
    "haematopoietic_stratum": lambda r: r.exclusion_reasons == ("lineage_haematopoietic",),
}


def component_labels(
    rows: Sequence[IdentityRow], label: Callable[[IdentityRow], str]
) -> dict[str, str]:
    """Label of each component among ``rows``; MULTIPLE when its records disagree."""
    labels: dict[str, set[str]] = {}
    for row in rows:
        labels.setdefault(row.component_id, set()).add(label(row))
    return {c: (next(iter(v)) if len(v) == 1 else MULTIPLE) for c, v in labels.items()}


def tissue_counts(rows: Sequence[IdentityRow], config: QCConfig) -> list[dict[str, object]]:
    """Eligible records and components per tissue, for every taxonomy and population."""
    out: list[dict[str, object]] = []
    for population, include in POPULATIONS.items():
        selected = [r for r in rows if include(r)]
        for taxonomy, label in TAXONOMIES.items():
            per_component = component_labels(selected, label)
            components = Counter(per_component.values())
            records = Counter(label(r) for r in selected)
            for tissue in sorted(set(components) | set(records)):
                n_components = components.get(tissue, 0)
                out.append(
                    {
                        "population": population,
                        "taxonomy": taxonomy,
                        "tissue": tissue,
                        "eligible_records": records.get(tissue, 0),
                        "eligible_components": n_components,
                        "meets_min_components": tissue != MULTIPLE
                        and n_components >= config.min_components_per_tissue,
                    }
                )
    return out


def structure_summary(
    rows: Sequence[IdentityRow],
    counts: Sequence[Mapping[str, object]],
    config: QCConfig,
    population: str,
    taxonomy: str,
) -> dict[str, object]:
    """n, T10, pooling, strata and component sizes for one population and taxonomy."""
    include = POPULATIONS[population]
    selected = [r for r in rows if include(r)]
    sizes = Counter(r.component_id for r in selected)
    labels = component_labels(selected, TAXONOMIES[taxonomy])
    table = [c for c in counts if c["population"] == population and c["taxonomy"] == taxonomy]
    qualifying = sorted(str(c["tissue"]) for c in table if c["meets_min_components"])
    pooled = sum(
        int(c["eligible_components"])  # type: ignore[call-overload]
        for c in table
        if not c["meets_min_components"] and c["tissue"] != MULTIPLE
    )
    multiple = sum(int(c["eligible_components"]) for c in table if c["tissue"] == MULTIPLE)  # type: ignore[call-overload]
    strata = {
        str(c["tissue"]): int(c["eligible_components"])  # type: ignore[call-overload]
        for c in table
        if c["meets_min_components"]
    }
    if pooled:
        strata[POOLED] = pooled
    n = len(sizes)
    size_by_tissue: dict[str, dict[int, int]] = {}
    records_by_stratum: Counter[str] = Counter()
    for component, size in sizes.items():
        tissue = labels[component] if labels[component] in strata else POOLED
        if labels[component] == MULTIPLE:
            tissue = MULTIPLE
        bucket = size_by_tissue.setdefault(tissue, {})
        bucket[size] = bucket.get(size, 0) + 1
        records_by_stratum[tissue] += size
    small = sorted(name for name, size in strata.items() if size < config.outer_folds)
    if 0 < multiple < config.outer_folds:
        small.append(MULTIPLE)
    return {
        "n_eligible_records": len(selected),
        "n_eligible_components": n,
        "T10": len(qualifying),
        "qualifying_tissues": qualifying,
        "components_pooled_as_other_solid": pooled,
        "components_with_multiple_labels_not_pooled": multiple,
        "strata_after_pooling": dict(sorted(strata.items())),
        "records_per_stratum": dict(sorted(records_by_stratum.items())),
        "strata_with_fewer_components_than_outer_folds": small,
        "held_out_tissue_training_components": {
            tissue: n - strata[tissue] for tissue in qualifying
        },
        "component_size_histogram": {str(k): v for k, v in sorted(Counter(sizes.values()).items())},
        "component_size_histogram_by_stratum": {
            t: {str(k): v for k, v in sorted(h.items())} for t, h in sorted(size_by_tissue.items())
        },
        "largest_component_records": max(sizes.values(), default=0),
    }


def feasibility_summary(
    rows: Sequence[IdentityRow],
    counts: Sequence[Mapping[str, object]],
    config: QCConfig,
    edges: Sequence[tuple[str, str]],
) -> dict[str, object]:
    """Descriptive data-sufficiency quantities for the planned validation structure."""
    primary = structure_summary(rows, counts, config, "primary", "oncotree_lineage")
    n, t10 = primary["n_eligible_components"], primary["T10"]
    ambiguous_nodes = {cp.ach_node(r.depmap_id) for r in rows if len(r.cellosaurus_candidates) > 1}
    return {
        "definitions": {
            "n": "components with >= 1 eligible record",
            "T10": (
                "tissues with >= min_components_per_tissue eligible components; "
                f"min_components_per_tissue = {config.min_components_per_tissue}"
            ),
        },
        "outer_folds_planned": config.outer_folds,
        "primary": primary,
        "sensitivity": {
            f"{population}/{taxonomy}": structure_summary(
                rows, counts, config, population, taxonomy
            )
            for population in POPULATIONS
            for taxonomy in TAXONOMIES
            if (population, taxonomy) != ("primary", "oncotree_lineage")
        },
        "candidate_graph_sensitivity": candidate_graph_summary(rows),
        "records_excluded_by_component_spans_lineages": sum(
            "component_spans_lineages" in r.exclusion_reasons for r in rows
        ),
        "edges_from_ambiguous_candidates": sum(
            1 for a, b in edges if a in ambiguous_nodes and b.startswith("CVCL:")
        ),
        "provisional_floors_descriptive_not_power": [
            {"name": name, "min_n": min_n, "min_T10": min_t10, "met": n >= min_n and t10 >= min_t10}  # type: ignore[operator]
            for name, min_n, min_t10 in config.provisional_floors
        ],
        "note": (
            "Descriptive data-sufficiency counts only. They do not establish power or "
            "precision for the paired dMAE comparison (docs/phase_01_reconciliation.md section 6)."
        ),
    }


def candidate_graph_summary(rows: Sequence[IdentityRow]) -> dict[str, object]:
    """Primary-eligible records regrouped with the conservative candidate graph."""
    eligible = [r for r in rows if r.eligible_primary]
    sizes = Counter(r.candidate_component_id for r in eligible)
    return {
        "note": "Same eligible records as the primary analysis; components from the "
        "candidate graph (every candidate link and RRID).",
        "n_eligible_records": len(eligible),
        "n_eligible_components": len(sizes),
        "multi_record_components": sum(1 for s in sizes.values() if s > 1),
        "largest_component_records": max(sizes.values(), default=0),
        "component_size_histogram": {str(k): v for k, v in sorted(Counter(sizes.values()).items())},
    }


def attrition_by_tissue(rows: Sequence[IdentityRow]) -> list[dict[str, object]]:
    """Records per (OncotreeLineage, exclusion reason): any position and first position."""
    any_counts: Counter[tuple[str, str]] = Counter()
    first_counts: Counter[tuple[str, str]] = Counter()
    for row in rows:
        tissue = row.oncotree_lineage or "(blank)"
        reasons = row.exclusion_reasons or ("eligible",)
        first_counts[(tissue, reasons[0])] += 1
        for reason in reasons:
            any_counts[(tissue, reason)] += 1
    return [
        {
            "oncotree_lineage": tissue,
            "reason": reason,
            "records_any_position": any_counts[(tissue, reason)],
            "records_first_reason": first_counts.get((tissue, reason), 0),
        }
        for tissue, reason in sorted(any_counts)
    ]


def problematic_entries(
    cellosaurus: Mapping[str, cs.CellosaurusRecord], assignment: Mapping[str, str]
) -> list[dict[str, str]]:
    """Every fetched entry with a problem text, for human review (e.g. named contaminants)."""
    return [
        {
            "accession": record.accession,
            "name": record.name,
            "component_id": assignment.get(cp.cvcl_node(record.accession), ""),
            "problematic_text": record.problematic,
        }
        for record in sorted(cellosaurus.values(), key=lambda r: r.accession)
        if record.problematic
    ]
