"""Assemble and write the phase_01 identifier-QC report (no outcome values).

``run_identifier_qc`` is pure: it takes parsed inputs and returns every table and
the summary. ``write_report`` writes them with deterministic ordering and bytes,
so identical inputs give byte-identical files (``run_record.json`` aside, which
the runner writes with timestamps).

Output files (all in one folder; every record is keyed by its CLARIFi row number):
- identity_records.csv               every record: identity, profiles, component, eligibility
- matched_verified.csv               identity_status = verified
- ambiguous_matches.csv              identity_status = ambiguous (blocking issues listed)
- unmatched_records.csv              identity_status = unmatched
- duplicate_identifiers.csv          identifier values shared by more than one record
- relationships_parent.csv           Cellosaurus parent (hi) links among fetched entries
- relationships_same_individual.csv  Cellosaurus oi pairs and shared DepMap PatientID pairs
- components.csv                     node -> relationship group (component)
- eligibility.csv                    per record: eligibility flags, tissue, exclusion reasons
- attrition_by_tissue.csv            exclusion reasons x OncotreeLineage (any / first reason)
- tissue_counts.csv                  records and components per tissue x taxonomy x population
- problematic_entries.csv            fetched Cellosaurus entries with a problem text (review)
- moringa_lines.csv                  MCF-7 / DU145 availability (identity only)
- summary.json                       all counts and feasibility quantities
"""

from __future__ import annotations

import csv
import dataclasses
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from radiosensitivity_ml.data import cellosaurus as cs
from radiosensitivity_ml.data import eligibility as el
from radiosensitivity_ml.data import qc_identifiers as qc
from radiosensitivity_ml.data.provenance import write_json


@dataclass(frozen=True)
class QCInputs:
    """Parsed, verified inputs of a full QC run."""

    clarifi: Sequence[qc.ClarifiRecord]
    models: Mapping[str, Mapping[str, str]]
    model_header: Sequence[str]
    rna_models: set[str]
    profile_types: Sequence[str]
    expression_ids: Sequence[str]
    cellosaurus: Mapping[str, cs.CellosaurusRecord]
    cellosaurus_provenance: Mapping[str, object]
    strandedness: Mapping[str, object] = dataclasses.field(default_factory=dict)


@dataclass(frozen=True)
class QCResult:
    """Every table and the summary produced by one QC run."""

    rows: tuple[qc.IdentityRow, ...]
    tables: tuple[tuple[str, tuple[Mapping[str, object], ...], tuple[str, ...]], ...]
    summary: Mapping[str, object]


def counter(values: object) -> dict[str, int]:
    """Sorted dict of counts."""
    return dict(sorted(Counter(values).items()))  # type: ignore[arg-type]


def run_identifier_qc(inputs: QCInputs, config: el.QCConfig) -> QCResult:
    """Run the full identity, grouping and eligibility QC on parsed inputs."""
    expression = set(inputs.expression_ids)
    rows = qc.assess_identity(
        inputs.clarifi, inputs.models, inputs.rna_models, expression, inputs.cellosaurus
    )
    assignment = el.assign_components(rows, inputs.cellosaurus)
    el.apply_eligibility(rows, config, assignment, inputs.cellosaurus, expression_checked=True)
    edges = el.relationship_edges(rows, inputs.cellosaurus, mode=el.CANDIDATE)
    counts = el.tissue_counts(rows, config)
    moringa = moringa_table(rows, config)
    unexpanded = sorted(el.unexpanded_accessions(inputs.cellosaurus))
    summary: dict[str, object] = {
        "mode": "full",
        "records": record_counts(inputs.clarifi, rows),
        "outcome_invalid_counts": {
            kind: sum(r.outcome_invalid_kind == kind for r in inputs.clarifi)
            for kind in qc.INVALID_OUTCOME_KINDS
        },
        "identity_issue_counts": counter(i for r in rows for i in r.identity_issues),
        "identity_note_counts": counter(i for r in rows for i in r.identity_notes),
        "ids_concordant_name_discordant": [
            f"{r.depmap_id}@row{r.row_number}"
            for r in rows
            if r.identity_issues == ("ccle_name_mismatch",)
            and r.rrid_relation in {"primary", "secondary"}
        ],
        "relationship_status_counts": {
            "parent": counter(r.parent_status for r in rows),
            "same_individual": counter(r.same_individual_status for r in rows),
        },
        "links_not_expanded": unexpanded,
        "components_with_clarifi_records": len({r.component_id for r in rows}),
        "eligibility": {
            "eligible_primary_records": sum(r.eligible_primary for r in rows),
            "eligible_retaining_problematic_records": sum(
                r.eligible_retaining_problematic for r in rows
            ),
            "haematopoietic_stratum_records": sum(
                r.exclusion_reasons == ("lineage_haematopoietic",) for r in rows
            ),
            "exclusion_reason_counts": counter(x for r in rows for x in r.exclusion_reasons),
            "records_excluded_only_pending_review": sum(pending_review_only(r) for r in rows),
            "components_if_pending_reviews_cleared": len(
                {r.component_id for r in rows if r.eligible_primary or pending_review_only(r)}
            ),
            "note": (
                "Pending-review exclusions (*_review, identity_ambiguous) are provisional: "
                "human resolution can only add records, so n is a lower bound until reviews end."
            ),
        },
        "feasibility": el.feasibility_summary(rows, counts, config, edges),
        "lineage_values_seen": sorted({r.oncotree_lineage for r in rows}),
        "model_optional_columns_present": sorted(
            c for c in qc.MODEL_OPTIONAL_COLUMNS if c in inputs.model_header
        ),
        "default_profile_type_values": list(inputs.profile_types),
        "strandedness": dict(inputs.strandedness) or {"available": "not_checked"},
        "expression_matrix_rows": len(inputs.expression_ids),
        "expression_matrix_duplicate_ids": len(inputs.expression_ids) - len(expression),
        "unmatched_records": [
            f"{r.depmap_id}@row{r.row_number}" for r in rows if r.identity_status == qc.UNMATCHED
        ],
        "ambiguous_records": [
            f"{r.depmap_id}@row{r.row_number}" for r in rows if r.identity_status == qc.AMBIGUOUS
        ],
        "moringa_lines": {str(m["depmap_id"]): m for m in moringa},
        "cellosaurus": dict(inputs.cellosaurus_provenance),
    }
    identity = tuple(asdict(r) for r in rows)
    by_status = {
        s: tuple(i for i in identity if i["identity_status"] == s)
        for s in (qc.VERIFIED, qc.AMBIGUOUS, qc.UNMATCHED)
    }
    tables = (
        ("identity_records.csv", identity, IDENTITY_COLUMNS),
        ("matched_verified.csv", by_status[qc.VERIFIED], IDENTITY_COLUMNS),
        ("ambiguous_matches.csv", by_status[qc.AMBIGUOUS], IDENTITY_COLUMNS),
        ("unmatched_records.csv", by_status[qc.UNMATCHED], IDENTITY_COLUMNS),
        ("duplicate_identifiers.csv", tuple(qc.duplicate_identifier_rows(rows)), DUPLICATE_COLUMNS),
        (
            "relationships_parent.csv",
            tuple(el.parent_relationships(inputs.cellosaurus, rows)),
            PARENT_COLUMNS,
        ),
        (
            "relationships_same_individual.csv",
            tuple(el.same_individual_relationships(inputs.cellosaurus, rows)),
            SAME_COLUMNS,
        ),
        ("components.csv", tuple(component_table(assignment, rows)), COMPONENT_COLUMNS),
        (
            "candidate_components.csv",
            tuple(
                {
                    "depmap_id": r.depmap_id,
                    "row_number": r.row_number,
                    "component_id": r.component_id,
                    "candidate_component_id": r.candidate_component_id,
                }
                for r in rows
            ),
            ("row_number", "depmap_id", "component_id", "candidate_component_id"),
        ),
        ("eligibility.csv", identity, ELIGIBILITY_COLUMNS),
        ("attrition_by_tissue.csv", tuple(el.attrition_by_tissue(rows)), ATTRITION_COLUMNS),
        ("tissue_counts.csv", tuple(counts), TISSUE_COLUMNS),
        (
            "problematic_entries.csv",
            tuple(el.problematic_entries(inputs.cellosaurus, assignment)),
            PROBLEM_COLUMNS,
        ),
        ("moringa_lines.csv", tuple(moringa), MORINGA_COLUMNS),
    )
    return QCResult(rows=tuple(rows), tables=tables, summary=summary)


def pending_review_only(row: qc.IdentityRow) -> bool:
    """True if every exclusion reason of an excluded record awaits human review."""
    reasons = row.exclusion_reasons
    return bool(reasons) and all(
        r.endswith("_review") or r == f"identity_{qc.AMBIGUOUS}" for r in reasons
    )


def run_model_table_audit(
    clarifi: Sequence[qc.ClarifiRecord], models: Mapping[str, Mapping[str, str]]
) -> QCResult:
    """Identity audit against one Model table only (e.g. 23Q4). No profiles, no eligibility."""
    rows = qc.assess_identity(clarifi, models, None, None, None)
    summary = {
        "mode": "model_table_audit",
        "note": "Model-table matching only; no expression, Cellosaurus, grouping or eligibility.",
        "records": {
            "clarifi_records": len(clarifi),
            "in_model_table": sum(r.in_model_table for r in rows),
            "ccle_name_mismatches": sum("ccle_name_mismatch" in r.identity_issues for r in rows),
            "missing_rrid": sum("missing_rrid_in_model_table" in r.identity_issues for r in rows),
        },
        "identity_issue_counts": counter(i for r in rows for i in r.identity_issues),
        "not_in_model_table": [
            f"{r.depmap_id}@row{r.row_number}" for r in rows if not r.in_model_table
        ],
    }
    identity = tuple(asdict(r) for r in rows)
    tables = (
        ("identity_records.csv", identity, IDENTITY_COLUMNS),
        ("duplicate_identifiers.csv", tuple(qc.duplicate_identifier_rows(rows)), DUPLICATE_COLUMNS),
    )
    return QCResult(rows=tuple(rows), tables=tables, summary=summary)


def record_counts(
    clarifi: Sequence[qc.ClarifiRecord], rows: Sequence[qc.IdentityRow]
) -> dict[str, int]:
    """Record-level counts from initial CLARIFi rows to matched molecular profiles."""
    verified = [r for r in rows if r.identity_status == qc.VERIFIED]
    return {
        "clarifi_records": len(clarifi),
        "unique_clarifi_depmap_ids": len({r.depmap_id for r in clarifi}),
        "in_model_table": sum(r.in_model_table for r in rows),
        "identity_verified": len(verified),
        "identity_ambiguous": sum(r.identity_status == qc.AMBIGUOUS for r in rows),
        "identity_unmatched": sum(r.identity_status == qc.UNMATCHED for r in rows),
        "unique_verified_identities": len({r.cellosaurus_accession for r in verified}),
        "with_default_rna_profile": sum(r.has_default_rna_profile for r in rows),
        "in_expression_matrix": sum(r.in_expression_matrix for r in rows),
        "verified_with_rna_profile_and_expression": sum(
            r.has_default_rna_profile and r.in_expression_matrix for r in verified
        ),
        "engineered_model_column_absent": sum(r.engineered_model == qc.COLUMN_ABSENT for r in rows),
    }


def component_table(
    assignment: Mapping[str, str], rows: Sequence[qc.IdentityRow]
) -> list[dict[str, str]]:
    """Node membership of every component that contains at least one CLARIFi record."""
    wanted = {row.component_id for row in rows}
    out = []
    for node, component in sorted(assignment.items(), key=lambda item: (item[1], item[0])):
        if component in wanted:
            kind, _, identifier = node.partition(":")
            out.append({"component_id": component, "node_type": kind, "identifier": identifier})
    return out


def moringa_table(rows: Sequence[qc.IdentityRow], config: el.QCConfig) -> list[dict[str, object]]:
    """Identity and eligibility of the Moringa-study human lines (no outcome values)."""
    out: list[dict[str, object]] = []
    for depmap_id, name in config.moringa_lines:
        matches = [r for r in rows if r.depmap_id == depmap_id]
        row = matches[0] if len(matches) == 1 else None
        out.append(
            {
                "depmap_id": depmap_id,
                "expected_name": name,
                "clarifi_records": len(matches),
                "identity_status": row.identity_status if row else "",
                "cellosaurus_accession": row.cellosaurus_accession if row else "",
                "oncotree_lineage": row.oncotree_lineage if row else "",
                "has_default_rna_profile": row.has_default_rna_profile if row else False,
                "in_expression_matrix": row.in_expression_matrix if row else False,
                "eligible_primary": row.eligible_primary if row else False,
                "exclusion_reasons": ";".join(row.exclusion_reasons)
                if row
                else ("not_in_clarifi" if not matches else "duplicate_records"),
            }
        )
    return out


# ---------------------------------------------------------------------------- writing


def cell(value: object) -> str:
    """Render one CSV cell: tuples joined with ';', everything else as str."""
    if isinstance(value, tuple):
        return ";".join(str(v) for v in value)
    return str(value)


def write_csv(path: Path, rows: Sequence[Mapping[str, object]], columns: Sequence[str]) -> None:
    """Write rows with a fixed header and '\\n' line endings."""
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(columns)
        for row in rows:
            writer.writerow([cell(row.get(c, "")) for c in columns])


def write_report(folder: Path, result: QCResult) -> list[Path]:
    """Write every table and summary.json into ``folder``; return the written paths."""
    written = []
    for name, rows, columns in result.tables:
        write_csv(folder / name, rows, columns)
        written.append(folder / name)
    write_json(folder / "summary.json", result.summary)
    written.append(folder / "summary.json")
    return written


IDENTITY_COLUMNS = tuple(f.name for f in fields(qc.IdentityRow))
ELIGIBILITY_COLUMNS = (
    "row_number",
    "depmap_id",
    "component_id",
    "component_records",
    "candidate_component_id",
    "identity_status",
    "oncotree_lineage",
    "oncotree_primary_disease",
    "clarifi_tissue_suffix",
    "eligible_primary",
    "eligible_retaining_problematic",
    "exclusion_reasons",
    "component_flag_sources",
)
DUPLICATE_COLUMNS = ("identifier_type", "identifier", "records")
COMPONENT_COLUMNS = ("component_id", "node_type", "identifier")
ATTRITION_COLUMNS = ("oncotree_lineage", "reason", "records_any_position", "records_first_reason")
TISSUE_COLUMNS = (
    "population",
    "taxonomy",
    "tissue",
    "eligible_records",
    "eligible_components",
    "meets_min_components",
)
PROBLEM_COLUMNS = ("accession", "name", "component_id", "problematic_text")
PARENT_COLUMNS = (
    "child_accession",
    "child_name",
    "child_clarifi_depmap_ids",
    "parent_accession",
    "parent_name",
    "parent_clarifi_depmap_ids",
    "parent_entry_fetched",
    "source",
)
SAME_COLUMNS = (
    "identifier_a",
    "identifier_b",
    "source",
    "a_clarifi_depmap_ids",
    "b_clarifi_depmap_ids",
)
MORINGA_COLUMNS = (
    "depmap_id",
    "expected_name",
    "clarifi_records",
    "identity_status",
    "cellosaurus_accession",
    "oncotree_lineage",
    "has_default_rna_profile",
    "in_expression_matrix",
    "eligible_primary",
    "exclusion_reasons",
)
