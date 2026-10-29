"""Transparent compound prioritisation: four prespecified dimensions, 0-8 points.

The rules below were fixed **before** any score was computed (`docs/compound_protocol.md`,
decision log D05.01) and are implemented exactly once, here. Every point carries a written
justification derived from the curated records, so a reviewer can re-derive any total from
the evidence tables alone.

    D1  Strength of verified Moringa constituent evidence     0-2
    D2  Relevance to supported radiation-response biology     0-3
    D3  Independent evidence-source support                   0-2
    D4  Feasibility of future experimental follow-up          0-1
                                                        total 0-8

Rules that keep the score honest:
- only **primary** studies of the **purified** compound score; reviews never score, and
  several reviews repeating one experiment are one source, not many;
- **no analogy points.** Membership of a chemical class whose other members have radiation
  evidence earns nothing (investigator decision, 2026-10-22); such analogies are reported
  as untested hypotheses in the text instead;
- a compound with no primary Moringa identification (D1 = 0) is **not assessable** and
  never enters the ranked shortlist, however interesting its biology;
- evidence that the compound **protects tumour cells** from radiation, or is itself
  **genotoxic**, is a liability: it is displayed and it caps the tier at C;
- extraction-specific evidence (was the compound ever shown in a dichloromethane extract?)
  is reported **beside** the score and never folded into it;
- missing evidence is recorded as missing. It is never read as evidence of no effect.

Tiers describe the state of the published evidence. **Every tier, including A, is
hypothesis-generating**: no tier asserts radioprotection, radiosensitisation, potency or
any effect in the extracts of the motivating study.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import pandas as pd

from radiosensitivity_ml.compounds.curation import (
    BiologyEvidence,
    Constituent,
    CuratedEvidence,
)

MAX_POINTS = {"d1_moringa_identity": 2, "d2_radiation_biology": 3,
              "d3_independent_sources": 2, "d4_feasibility": 1}  # fmt: skip
TOTAL_POINTS = sum(MAX_POINTS.values())
STRONG_IDENTIFICATION = ("isolation_nmr", "reference_standard")
SEED_OR_LEAF = ("seed", "leaf", "both")
TIERS = ("A", "B", "C", "not_prioritised", "not_assessable")
TIER_LABEL = {
    "A": "higher-priority exploratory candidate",
    "B": "moderate-priority exploratory candidate",
    "C": "preliminary exploratory candidate",
    "not_prioritised": "not prioritised",
    "not_assessable": "not assessable",
}
# Thresholds (prespecified): (tier, minimum total, minimum D1, minimum D2)
TIER_RULES = (("A", 6, 1, 2), ("B", 4, 1, 1), ("C", 2, 1, 0))
LIABILITY_CAP = "C"  # best tier attainable when a liability direction is recorded
STATEMENT = (
    "Exploratory, hypothesis-generating prioritisation of published evidence. No tier "
    "asserts radioprotection, radiosensitisation, potency, selectivity, or any effect of "
    "the dichloromethane extracts of the motivating study."
)
SORT_COLUMNS = ["total_score", "d2_radiation_biology", "d1_moringa_identity",
                "d3_independent_sources", "d4_feasibility"]  # fmt: skip
TIE_BREAK = (
    "total score, then D2, then D1, then D3, then D4, all descending; remaining ties "
    "broken by preferred_name (A-Z). Deterministic and independent of input order."
)


@dataclass(frozen=True)
class Score:
    """One compound's points, justifications and tier."""

    compound_id: str
    points: Mapping[str, int]
    reasons: Mapping[str, str]
    tier: str
    tier_reason: str
    liabilities: tuple[str, ...]

    @property
    def total(self) -> int:
        return sum(self.points.values())


def scored_items(evidence: Sequence[BiologyEvidence]) -> tuple[BiologyEvidence, ...]:
    """Evidence items eligible for scoring (primary, purified, L2 or L3)."""
    return tuple(e for e in evidence if e.counts_for_score)


def independent_groups(items: Sequence[BiologyEvidence]) -> tuple[str, ...]:
    """Distinct research groups, so repeated work from one group counts once."""
    return tuple(sorted({e.research_group for e in items}))


def d1_moringa_identity(constituent: Constituent) -> tuple[int, str]:
    """0-2: how well the compound's presence in Moringa seed or leaf is documented."""
    primary = [r for r in constituent.primary_reports if r.plant_part in SEED_OR_LEAF]
    if not primary:
        return 0, ("no primary analytical study identifies this compound in Moringa seed or "
                   "leaf (review-only, tentative, or another plant part)")  # fmt: skip
    strong = [r for r in primary if r.identification_strength in STRONG_IDENTIFICATION]
    if strong:
        return 2, (f"{len(strong)} primary report(s) with structural confirmation "
                   f"({', '.join(sorted({r.identification_strength for r in strong}))})")  # fmt: skip
    return 1, (f"{len(primary)} primary report(s), but identification rests on a spectral "
               "library match or is not stated")  # fmt: skip


def d2_radiation_biology(items: Sequence[BiologyEvidence]) -> tuple[int, str]:
    """0-3: direct evidence linking the purified compound to radiation-response biology."""
    l3 = [e for e in items if e.evidence_level == "L3_radiation"]
    l2 = [e for e in items if e.evidence_level == "L2_process"]
    if l3:
        groups = independent_groups(l3)
        if len(groups) >= 2:
            return 3, (f"ionising-radiation evidence from {len(groups)} independent groups "
                       f"({', '.join(groups)})")  # fmt: skip
        return 2, f"ionising-radiation evidence from one group ({groups[0]})"
    if l2:
        groups = independent_groups(l2)
        return 1, (f"no ionising-radiation study; {len(l2)} study(ies) of a relevant process "
                   f"without radiation ({', '.join(groups)})")  # fmt: skip
    return 0, "no primary study of the purified compound in a relevant process"


def d3_independent_sources(
    constituent: Constituent, items: Sequence[BiologyEvidence]
) -> tuple[int, str]:
    """0-2: how many genuinely independent research groups support the record as a whole.

    Groups are counted once across the analytical and the biological evidence, so several
    papers from one laboratory (or several reviews of one experiment) are one source.
    """
    analytical = {r.research_group for r in constituent.primary_reports}
    biological = set(independent_groups(items))
    groups = sorted(analytical | biological)
    detail = (f"{len(analytical)} group(s) reporting it in Moringa, {len(biological)} group(s) "
              f"in the biology evidence, {len(groups)} distinct in total "
              f"({', '.join(groups) if groups else 'none'})")  # fmt: skip
    if len(groups) >= 3:
        return 2, detail
    if len(groups) == 2:
        return 1, detail
    return 0, f"at most one independent group: {detail}"


def d4_feasibility(constituent: Constituent, items: Sequence[BiologyEvidence]) -> tuple[int, str]:
    """0-1: is a follow-up experiment specifiable from the published record?

    One point requires both a resolved chemical identity (a verified public identifier, so
    the right material can be sourced) and at least one published concentration in a
    scored study, so a starting range exists. Neither is assumed.
    """
    identified = bool(constituent.pubchem_cid) and constituent.identifier_verified_via != (
        "not_verified"
    )
    dosed = [e for e in items if e.concentration]
    if identified and dosed:
        return 1, (f"public identifier verified via {constituent.identifier_verified_via} and "
                   f"{len(dosed)} scored study(ies) report a usable concentration")  # fmt: skip
    missing = []
    if not identified:
        missing.append("no verified public identifier")
    if not dosed:
        missing.append("no concentration reported in any scored study")
    return 0, "; ".join(missing)


def assign_tier(points: Mapping[str, int], liabilities: Sequence[str]) -> tuple[str, str]:
    """Apply the prespecified thresholds, then the liability cap."""
    total = sum(points.values())
    if points["d1_moringa_identity"] == 0:
        return "not_assessable", ("no primary Moringa identification: excluded from the ranked "
                                  "shortlist whatever its biology (prespecified rule)")  # fmt: skip
    tier, reason = "not_prioritised", f"total {total}/{TOTAL_POINTS} below the tier-C threshold"
    for name, min_total, min_d1, min_d2 in TIER_RULES:
        if (total >= min_total and points["d1_moringa_identity"] >= min_d1
                and points["d2_radiation_biology"] >= min_d2):  # fmt: skip
            tier = name
            reason = f"total {total}/{TOTAL_POINTS} with D1 ≥ {min_d1} and D2 ≥ {min_d2}"
            break
    if liabilities and tier in ("A", "B"):
        reason = (f"capped at {LIABILITY_CAP} from {tier} ({reason}): liability evidence "
                  f"recorded ({', '.join(liabilities)})")  # fmt: skip
        tier = LIABILITY_CAP
    return tier, reason


def score_compound(constituent: Constituent, evidence: Sequence[BiologyEvidence]) -> Score:
    """Score one compound from its curated records (pure; no input is modified)."""
    items = scored_items(evidence)
    points, reasons = {}, {}
    for name, (value, reason) in {
        "d1_moringa_identity": d1_moringa_identity(constituent),
        "d2_radiation_biology": d2_radiation_biology(items),
        "d3_independent_sources": d3_independent_sources(constituent, items),
        "d4_feasibility": d4_feasibility(constituent, items),
    }.items():
        if not 0 <= value <= MAX_POINTS[name]:
            raise ValueError(f"{name}: {value} outside 0-{MAX_POINTS[name]}")
        points[name], reasons[name] = value, reason
    liabilities = tuple(f"{e.evidence_id}: {e.direction}" for e in items if e.is_liability)
    tier, tier_reason = assign_tier(points, liabilities)
    return Score(
        compound_id=constituent.compound_id,
        points=points,
        reasons=reasons,
        tier=tier,
        tier_reason=tier_reason,
        liabilities=liabilities,
    )


def rank(curated: CuratedEvidence) -> list[Score]:
    """Score every constituent and apply the documented deterministic ordering."""
    return [score_compound(c, curated.for_compound(c.compound_id)) for c in curated.constituents]


def main_limitation(constituent: Constituent, items: Sequence[BiologyEvidence]) -> str:
    """The single most important caveat to print beside a candidate."""
    if constituent.extraction_category != "dcm_documented":
        return ("not verified in a dichloromethane extract of Moringa seed or leaf, so its "
                "presence in the extracts of the motivating study is unknown")  # fmt: skip
    if not any(e.evidence_level == "L3_radiation" for e in items):
        return "no primary study has combined the purified compound with ionising radiation"
    if all(e.reading_depth == "abstract" for e in items):
        return "evidence extracted from abstracts only; full texts not yet read"
    return next(
        (e.limitation for e in items if e.evidence_level == "L3_radiation"),
        "see the evidence table",
    )


def follow_up(constituent: Constituent, items: Sequence[BiologyEvidence]) -> str:
    """The next experiment the evidence gap implies (a proposal, never a result)."""
    if constituent.extraction_category != "dcm_documented":
        return ("analytical confirmation (LC-MS/MS or GC-MS against an authentic standard) "
                "in the original dichloromethane seed and leaf extracts")  # fmt: skip
    if not any(e.evidence_level == "L3_radiation" for e in items):
        return ("clonogenic survival of matched normal and tumour cells, with and without the "
                "purified compound, over a dose range")  # fmt: skip
    return ("dose-response clonogenic survival in matched normal and tumour lines to test "
            "whether the reported direction holds on a clonogenic endpoint")  # fmt: skip


def ranking_table(curated: CuratedEvidence) -> pd.DataFrame:
    """Candidate ranking table (one row per curated compound; ranks on prioritised tiers).

    ``rank`` is assigned only to tiers A-C (the shortlist); other rows carry a blank rank
    but stay in the table so that nothing is hidden.
    """
    by_id = {c.compound_id: c for c in curated.constituents}
    rows = []
    for score in rank(curated):
        constituent = by_id[score.compound_id]
        items = curated.for_compound(score.compound_id)
        scored = scored_items(items)
        rows.append(
            {
                "compound_id": score.compound_id,
                "preferred_name": constituent.preferred_name,
                "chemical_class": constituent.chemical_class,
                "pubchem_cid": constituent.pubchem_cid or "",
                "inchikey": constituent.inchikey or "",
                "plant_part": constituent.plant_part,
                "extraction_category": constituent.extraction_category,
                "dcm_reports": len(constituent.dcm_reports),
                **score.points,
                "total_score": score.total,
                "tier": score.tier,
                "tier_label": TIER_LABEL[score.tier],
                "tier_reason": score.tier_reason,
                "liability_flags": "; ".join(score.liabilities),
                "strongest_evidence_level": min((e.evidence_level for e in scored), default="none"),
                "processes": "; ".join(sorted({e.process_category for e in scored})),
                "directions": "; ".join(sorted({e.direction for e in scored})),
                "independent_groups": len(independent_groups(scored)),
                "n_scored_evidence": len(scored),
                "main_limitation": main_limitation(constituent, scored),
                "suggested_follow_up": follow_up(constituent, scored),
                **{f"reason_{k}": v for k, v in score.reasons.items()},
            }
        )
    table = pd.DataFrame(rows)
    table = table.sort_values(
        by=[*SORT_COLUMNS, "preferred_name"],
        ascending=[False] * len(SORT_COLUMNS) + [True],
        kind="stable",
    ).reset_index(drop=True)
    # Ranks are a nullable integer column: tiers A-C are numbered 1..n in the order above,
    # and every other row holds pd.NA rather than an empty string. A nullable integer dtype
    # is required because pandas >= 3.0 backs object columns with a strict Arrow string
    # dtype, which refuses integer assignment; it also keeps the column numerically
    # sortable. pd.NA is written as an empty field by `to_csv`, so the published table is
    # unchanged.
    shortlist = table["tier"].isin(["A", "B", "C"])
    ranks = pd.Series(pd.NA, index=table.index, dtype="Int64")
    ranks.loc[shortlist] = pd.array(range(1, int(shortlist.sum()) + 1), dtype="Int64")
    table.insert(0, "rank", ranks)
    return table
