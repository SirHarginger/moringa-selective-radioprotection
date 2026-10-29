# Compound-prioritisation protocol (prespecified)

**Status.** Written 2026-10-22, **before** any score was computed. Implemented once, in
`src/radiosensitivity_ml/compounds/ranking.py`. Decision log: D05.01.

**Question.** Which publicly documented *Moringa oleifera* seed or leaf constituents merit
further experimental investigation, because of independently supported links to biological
processes relevant to cellular radiation response?

This is evidence-based candidate prioritisation for future laboratory work. It is **not**
drug discovery, docking, virtual screening, or machine-learning prediction of compound
effects, and it produces **no** estimate of potency, efficacy or radioprotection.

## 1. What may enter

| Requirement | Rule |
|---|---|
| Species and part | *M. oleifera* **seed or leaf**. Root, bark and flower evidence does not qualify. |
| Source type | A **primary** analytical study. A review citing an earlier study is never independent confirmation. |
| Identity | A public identifier (PubChem CID, InChIKey) fetched and recorded. A missing identifier requires a written `identity_caveat`. |
| Biology evidence | A **primary** experimental study of the **purified compound**. A study that dosed an extract or fraction is recorded with `counts_for_score: false`. |
| Radiation | **Ionising** radiation only (X-ray, gamma, proton, carbon ion). UV and visible light never qualify as radiation evidence. |
| Formulation | Nanoparticle, metal-conjugate and liposomal studies are excluded: the carrier confounds the compound. |
| Chemical identity | Derivatives are distinct entities. CAPE is not caffeic acid; α-tocopherol succinate is not α-tocopherol; nitro-oleic acid is not oleic acid; BITC is not moringin. |

## 2. The four dimensions (0–8 points)

| Dimension | Points | Rule |
|---|---:|---|
| **D1** Verified Moringa constituent evidence | 0–2 | **2** if ≥ 1 primary seed/leaf report with structural confirmation (`isolation_nmr` or `reference_standard`); **1** if primary reports exist but identification rests on a spectral-library match or is not stated; **0** if no primary seed/leaf report. |
| **D2** Relevance to radiation-response biology | 0–3 | **3** if ionising-radiation evidence (L3) from ≥ 2 independent research groups; **2** if L3 from one group; **1** if only L2 (purified compound modulating a relevant process without radiation); **0** if none. |
| **D3** Independent source support | 0–2 | Research groups counted **once** across the analytical and biological evidence: **2** if ≥ 3 distinct groups, **1** if 2, **0** if ≤ 1. |
| **D4** Feasibility of follow-up | 0–1 | **1** only if the identifier is verified **and** ≥ 1 scored study reports a usable concentration or dose, so an experiment can be specified; **0** otherwise. |

### Rules that keep the score honest

1. **No analogy points.** Belonging to a chemical class whose *other* members have
   radiation evidence earns nothing (investigator decision, 2026-10-22). Such analogies
   are discussed in the report text as untested hypotheses. This is why moringin, the
   isothiocyanate most characteristic of Moringa, gains nothing from the benzyl
   isothiocyanate literature.
2. **One laboratory is one source.** Several papers from one group, or several reviews of
   one experiment, count once, in D2 and in D3 alike.
3. **Extraction evidence is never scored.** Whether a compound has been identified in a
   dichloromethane extract is reported *beside* the score, because the original study used
   DCM extracts whose composition was never measured. Folding it into the total would
   either reward or punish compounds for an accident of which solvents other laboratories
   happened to use.
4. **Missing evidence is missing, not negative.** An empty cell means no qualifying study
   was located. It is never read as evidence that the compound has no effect.
5. **Abstract-only reading is recorded.** `identification_strength` records what the cited
   source states; `reading_depth` records how deeply it was read here. A compound can hold
   D1 = 1 because full texts were not obtained, not because its identity is doubted.

## 3. Tiers

Applied in order; the first match wins.

| Tier | Condition | Meaning |
|---|---|---|
| **Not assessable** | D1 = 0 | No primary Moringa identification. Excluded from the ranked shortlist **whatever its biology**. |
| **A** | total ≥ 6 and D1 ≥ 1 and D2 ≥ 2 | Higher-priority exploratory candidate |
| **B** | total ≥ 4 and D1 ≥ 1 and D2 ≥ 1 | Moderate-priority exploratory candidate |
| **C** | total ≥ 2 and D1 ≥ 1 | Preliminary exploratory candidate |
| **Not prioritised** | otherwise | Identified in Moringa, but below the tier-C threshold |

**Liability cap.** If any scored evidence item reports that the compound **protects tumour
cells** from radiation (`radioprotection_tumour`) or is itself **genotoxic**
(`genotoxic`), the tier is capped at **C** and the flag is printed. Protecting a tumour
from radiotherapy is the opposite of what a radioprotector should do, and a compound that
damages DNA by itself is not a protection candidate.

**Every tier, including A, is hypothesis-generating.** No tier asserts radioprotection,
radiosensitisation, selectivity, potency, or any effect of the extracts used in the
original study. A tier is a statement about the state of the published evidence.

**Deterministic ordering.** Total, then D2, then D1, then D3, then D4, all descending;
remaining ties broken by `preferred_name` (A–Z). Ranks are assigned to tiers A–C only;
other rows stay in the table with a blank rank so that nothing is hidden.

## 4. Linking compounds to the model's pathways

Three things are kept apart, and the report never merges them:

- **A — model-associated pathways**: Hallmark gene sets highlighted by the exploratory
  permutation-importance analysis. These are capped at triage tier C, because no
  prediction gain was formally shown and no negative-control draws were run.
- **B — literature-supported processes**: processes a primary experiment associated with a
  compound.
- **C — overlap**: the genes a published experiment actually measured, intersected with
  the members of a gene set from A (`table_c4_pathway_overlap.csv`).

An overlap in C marks a point where a compound and a model-highlighted gene set touch the
same genes. **It creates a research hypothesis.** It is not evidence that the compound
modifies the gene set, the pathway, or clonogenic SF2, and a gene-set importance is not a
molecular effect size. Where the gene-set ranking is weak or not assessable, compound
prioritisation still proceeds on the external biological evidence alone, and the report
says so rather than borrowing strength from the model.

## 5. Outputs

`results/tables/<run_id>/compounds_v<N>/`, write-once:

| File | Contents |
|---|---|
| `table_c1_constituent_inventory.csv` | One row per compound × analytical report: identity, solvent, identification method and strength, DOI, verification route, reading depth, research group |
| `table_c2_biology_evidence.csv` | One row per evidence item: model system, tissue class, radiation type and dose, concentration, endpoints, measured genes, direction, limitation |
| `table_c3_candidate_ranking.csv` | One row per compound: points per dimension with written justifications, total, tier, liability flags, main limitation, suggested follow-up |
| `table_c4_pathway_overlap.csv` | Compound × prioritised gene set, with the shared genes and the evidence items they came from |
| `compound_record.json` | Input checksums, the scoring rules as applied, counts and tier counts |

Command: `python scripts/make_compound_tables.py --config configs/compounds.yaml`

## 6. What this module may never be used to claim

- that a compound is radioprotective, radiosensitising or selective;
- that a compound was present in the extracts of the original manuscript, or at what
  concentration;
- that an antioxidant is therefore a radioprotector;
- that a compound affecting tumour-cell viability therefore protects normal tissue;
- that a high priority score predicts experimental success.

*Rules fixed before computation by Claude Code on the investigator's instruction
(2026-10-22). Curation by the literature-reviewer agent; see
`docs/compound_evidence_curation.md` for searches, exclusions and unresolved gaps.*
