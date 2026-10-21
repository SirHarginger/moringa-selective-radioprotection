# Phase 01 recommendations and scientific feasibility decision

**Status:** phase_01 report for investigator review, 2026-10-21. Claude Code assembled it from the specialist reports listed in §8.

**Decision authority:** a phase gate passes only when the investigator signs it in `docs/decision_log.md`.

---

## 1. Feasibility decision: **CONDITIONAL GO** (protocol drafting only)

The evidence supports moving to phase_02: **drafting** `docs/protocol.md`. It does not support implementation or analysis.

**Do not freeze the protocol until the conditions in §2 are met.** The recommendation comes from the research-director. The ml-methodologist, statistical-reviewer, radiobiologist, radiogenomics-curator and reproducibility-auditor agree on substance; their disagreements are listed in §7.

**Why not GO:**
- The central feasibility count is not yet known: how many CLARIFi lines have DepMap expression. The download is blocked for Claude Code by the safety hook and has to be run by the investigator.
- Identity has not been resolved to Cellosaurus components, which every split depends on.
- The phase_00 gate is unsigned.

**Why not NO-GO:**
- A suitable primary label exists: 285 lines, clonogenic, defined provenance.
- Openly licensed features exist (DepMap 24Q4, CC BY 4.0).
- A specific question remains unanswered in the published literature: no published model on CLARIFi, and no out-of-sample tissue-only baseline for any radiation endpoint.

**Why the framing must change:** the evidence predicts a weak signal.
- Published signatures perform no better than random gene sets (RadSigBench, R² ≈ 0).
- Single-gene mRNA correlations with mSF2 are r ≈ 0.08.
- mSF2 agrees with Yard's endpoint at r = 0.28 and with single-institution SF2 at r = 0.50.

The defensible study is therefore a **prespecified, leakage-controlled benchmark of what expression adds beyond tissue of origin**, in which a null result is a valid answer. It is not a discovery claim that "explainable ML predicts radiosensitivity across cancers".

## 2. Conditions before the protocol freeze

1. **Gates.** The investigator signs the phase_00 → phase_01 gate, or records an exception, and later the phase_01 → phase_02 gate. The pytest cache is consistent with a passing run of the hook tests, but it is not a sign-off (reproducibility-auditor).
2. **Identifier QC run by the investigator** (§5), with the counts recorded in `docs/phase_01_dataset_feasibility.md` §4. No mSF2 summaries are produced.
3. **Cellosaurus components built**, and problematic, ICLAC-listed and same-donor lines flagged, with their handling pre-specified.
4. **Contact the CLARIFi authors** (Oike T) with four requests:
   - (a) confirm the licence and the Zenodo deposit;
   - (b) values and studies per line, and whether the median is over papers or over values;
   - (c) the DepMap release used;
   - (d) whether Amundson 2008 (NCI-60) values or Yard values are among the 926 source studies.
5. **Supplementary novelty search:**
   - Google Scholar, Scopus and Web of Science;
   - forward citations of Manem 2021, Kolnohuz 2024, Oike 2025 and RadSigBench;
   - bioRxiv and Research Square;
   - check every quantitative value against the PDFs.
6. **Fix the tissue taxonomy and the outcome scale before any outcome is seen.** The taxonomy choice (CCLE suffix with 24 tissues, the paper's 28 types, or OncotreeLineage) changes how strong the tissue baseline is. The scale is raw mSF2 or logit.
7. **Amend P00.10.** A study/lab-only baseline cannot be built from the released CLARIFi file.

## 3. What the pending identifier QC changes (thresholds for the investigator to accept before running it)

> **Amended 2026-10-21 (`docs/phase_01_reconciliation.md` §6).** The numbers below are kept only as **provisional data-sufficiency floors (descriptive)**. They were derived from the CI width of a single correlation and are **not evidence of power** for the paired ΔMAE comparison. G-n is replaced by a design-analysis precision criterion. The QC cannot produce *n* or T₁₀ until patch P01.07 is applied.

Definitions:
- **n**: the number of usable solid-tumour Cellosaurus components that have a DepMap default RNA profile.
- **T₁₀**: the number of tissues with at least 10 such components under the chosen taxonomy.

The thresholds come from Fisher-z design arithmetic: the 95% half-width near r = 0 is about ±0.12 at n = 260 and about ±0.20 at n = 100.

| QC result | Decision |
|---|---|
| n ≥ 230 and T₁₀ ≥ 10 | **GO.** Primary design as specified |
| 180 ≤ n < 230, or 6 ≤ T₁₀ < 10 | **CONDITIONAL GO.** Within-tissue and leave-one-tissue-out analyses limited to qualifying tissues and labelled descriptive; repeated outer CV becomes mandatory |
| 150 ≤ n < 180 | **Re-scope** to an estimation-focused benchmark with no superiority claim. Drop the within-tissue and leave-one-tissue-out aims. Consider making cross-assay transportability co-primary |
| n < 150 or T₁₀ < 6 | **NO-GO** for the predictive primary. Pivot to a study of label reliability and cross-assay concordance, or stop |

Other QC outcomes:
- More than about 5% of IDs still unresolved after the 23Q4 audit: the protocol freeze waits for human resolution.
- Any disagreement between the DepMap RRID and Cellosaurus: that line is held back until resolved.
- MCF-7 or DU145 without an RNA profile: drop exploratory aim E3 only.

## 4. Recommended research question

> **Amended 2026-10-21 (`docs/phase_01_reconciliation.md` §2, §4).** The primary metric is now the paired **ΔMAE** against tissue-only. ΔR² is a secondary, non-gating metric. The uncertainty method is a Bates-type nested-CV interval, with a Nadeau–Bengio fallback. The grouped bootstrap is descriptive only. S4 is "cross-assay transportability".

> **Primary.** Among solid-tumour CLARIFi cell lines with DepMap 24Q4 baseline expression (unit: one Cellosaurus component), does adding pre-specified gene-set expression scores to a tissue-of-origin model improve out-of-sample prediction of clonogenic mSF2?
> - Estimate: the paired difference in out-of-sample R² (expression + tissue vs tissue only).
> - Design: donor-grouped, tissue-stratified nested CV.
> - Uncertainty: paired grouped-bootstrap CI, judged against a pre-set margin.
> - A null result is a valid answer.

**Secondary aims:**
- S1: value beyond tissue plus proliferation.
- S2: within-tissue performance (tissues with at least 10 groups).
- S3: model-class comparison.
- S4: cross-assay transportability to Yard 2016, reported as endpoint heterogeneity and never as validation.
- S5: leave-one-tissue-out.
- S6: attribution stability, gated on the primary result.

**Exploratory aims:**
- E1: label reliability (needs per-line counts).
- E2: pathway grouping of stable attributions (hypothesis-generating; needs S6).
- E3: contextual placement of MCF-7 and DU145 (figure annotation only).

**Working title:** *Does baseline gene expression add to tissue of origin in predicting clonogenic radiosensitivity of cancer cell lines? A prespecified, leakage-controlled benchmark with cross-assay transportability.*

**Defensible alternative if the QC fails the thresholds:** a study of label reliability and cross-assay concordance (C5/C7), built on per-line provenance from the CLARIFi authors.

**Moringa linkage:** motivation only. Two of its three lines (MCF-7, DU145) are in CLARIFi. Its endpoint (PEF) is incompatible with every endpoint used here. A future wet-lab design is given in `docs/phase_01_moringa_linkage.md` §7.

## 5. Investigator commands (Claude Code cannot run these)

Run from the repository root, after reviewing the scripts:

> **Superseded 2026-10-21.** These commands are out of date: the QC options, the Cellosaurus invocation and the environment name have all changed. Use `docs/phase_01_investigator_qc_checklist.md`. The block below is kept unchanged as the historical record.

```bash
conda activate moringa-rad   # LEGACY name; the configured environment is explainable-radiosensitivity-ml (O01.16)
python3 -I -m compileall -q src tests scripts .claude/hooks
bash -n scripts/acquire_phase_01.sh          # syntax check (blocked for Claude Code)
PYTHONPATH=src python3 -m pytest tests/test_qc_identifiers.py tests/test_safety_hooks.py -q
bash scripts/acquire_phase_01.sh --yard
python3 -I scripts/fetch_cellosaurus_phase_01.py
PYTHONPATH=src python3 scripts/qc_phase_01_identifiers.py --allow-dirty
PYTHONPATH=src python3 scripts/qc_phase_01_identifiers.py --allow-dirty --no-cellosaurus \
  --model data/raw/depmap/23q4_v1/Model.csv --out results/tables/phase_01/identifier_qc_23q4_v1
git check-ignore -v data/raw/depmap/24q4/Model.csv data/raw/cellosaurus/r56_0/release_info.json
```

The second QC run (23Q4) uses the 24Q4 expression and profile files. Read only its Model-table match counts.

Then:
1. Fill in the manifests (SHA-256, size, access date, retrieved_by), using the checklist in §6.
2. Send `summary.json` from both runs to Claude Code.

## 6. Post-acquisition manifest checklist (reproducibility-auditor)

**For each file:**
- `access_date`, `retrieved_by` (a named person), `retrieval_method`;
- `sha256` and `size_bytes`, plus an MD5 match against `published_md5` where one exists;
- `encoding`, `delimiter`, `line_terminator`, `n_lines` (stating whether the header is counted), `header`, units.

**Per source:**
- **Expression file:** confirm the first-column layout.
- **Yard:** sheet names, columns, identifier type, replicate structure, and which version (533, 511 or 498 lines).
- **Cellosaurus:** fill `files:` from the sidecars, record whether the `hi`/`oi` fields were accepted, and the batch count.
- **GEO:** RAW.tar size compared with 3,020,800 bytes; date of the matrix file.
- **ICLAC:** confirm it is a genuine xlsx, not an HTML page.

**Before setting `provenance_status: verified`:** a named human must have checked the source, licence and endpoint.

## 7. Outstanding risks (ranked; research-director)

| # | Risk | Mitigation |
|---|---|---|
| 1 | No incremental signal | Null-tolerant framing; pre-set margin; title that does not assume a positive result |
| 2 | Label noise of unknown size (mSF2 vs in-house SF2 r = 0.50, n = 23) | State the noise ceiling (rule R9); request data from the authors |
| 3 | Effective n after QC and grouping; small tissues | §3 thresholds; descriptive within-tissue analyses |
| 4 | No independent external validation set; possible circularity with NCI-60 | Never write "external validation"; Yard is transportability only; NCI-60 deferred |
| 5 | Identifier drift between 23Q4 and 24Q4 | 23Q4 audit; human resolution of unmatched IDs |
| 6 | CLARIFi licence conflict | Contact the authors; release no CLARIFi values |
| 7 | Proliferation baseline circular or undefined | Investigator defines it before the freeze |
| 8 | Novelty erosion | Condition 5; optional formal registration (O00.07) |
| 9 | Popularity confounding in C5 | Adjust for tissue; label as exploratory |
| 10 | Moringa framing creep | Wording rules (`phase_01_moringa_linkage.md` §8) |
| 11 | Process and execution capacity | Gate housekeeping first |

### Specialist disagreements
- **D1 (explanation stability when the primary gate fails):** **unresolved; investigator decision O01.09.**
  - Research-director: report the stability metrics regardless, without biological interpretation.
  - ml-methodologist: stability is meaningful only if the gate passes.
- **D2 (haematopoietic lines):** solid-only primary analysis. Resolved by the research-director; awaits investigator approval.
- **D4 (direction of cross-assay transfer):** pre-specify both directions.
- **D3, D5, D6, D7:** resolved; see `docs/phase_01_novelty_assessment.md` §10.6.

## 8. Phase_02 priorities (in order)

1. **Gate housekeeping:** signatures, plus this report recorded in the decision log.
2. **Investigator-run acquisition and identifier QC**, Cellosaurus components, and the overlap table for CLARIFi, Yard and NCI-60. Strictly, this closes phase_01.
3. **Contact the authors.**
4. **Supplementary novelty search.**
5. **Draft `docs/protocol.md`:**
   - estimand and population;
   - taxonomy and scale;
   - baselines;
   - versioned gene-set collection;
   - expression product and the strandedness batch;
   - nested grouped CV with preprocessing inside the folds;
   - metric, margin and inference;
   - gates G-ID, G-n, G-pred and G-stab (G-C3 superseded by O01.15: cross-assay analysis is exploratory rank concordance);
   - multiplicity and sensitivity analyses;
   - TRIPOD+AI reporting.
6. **Statistical design note:** precision by n; justification of the margin.
7. **Explanation plan:** attribution methods, stability metrics and thresholds.
8. **Cross-assay plan:** Yard version and test directions.
9. **Figure and table shells** (no data): cell-line flow diagram, Δ forest plot, within-tissue panel.
10. **Review cycle and freeze;** optional formal OSF registration (O00.07). Until registration happens, the study is described as "prespecified", not "preregistered".

## 9. Investigator decisions requested

| ID | Decision | Recommendation |
|---|---|---|
| O01.01 | Reframing and working title (closes O00.10) | Accept; drop "explainable" from the paper title |
| O01.02 | Primary population | Solid tumours; haematopoietic lines as a sensitivity analysis |
| O01.03 | Tissue taxonomy | OncotreeLineage (24Q4) primary; CCLE suffix as sensitivity |
| O01.04 | Outcome scale | Choose raw or logit before the freeze |
| O01.05 | Proliferation baseline | Check for doubling-time data; otherwise a pre-specified expression score |
| O01.06 | Primary metric and margin | Δ R²_oos primary; margin set with rationale before the freeze |
| O01.07 | Gene-set collection and version | Pre-specified, versioned, licence-checked |
| O01.08 | Thresholds in §3 | Accept or amend before running the QC |
| O01.09 | Explanation gating (D1) | Investigator choice |
| O01.10 | Yard version and transfer directions | Original Supplementary Data 1; both directions |
| O01.11 | NCI-60 | Defer until source overlap (SR-02) is resolved |
| O01.12 | Retrieve Data S2 / ask the authors for per-line counts | Yes |

## 10. Agents and skills used in phase_01 (actual)

| Agent | Task | Output |
|---|---|---|
| literature-reviewer (×2) | Part A: ML, radiogenomics, tissue, explanations. Part B: datasets, normal cells, plant extracts | `phase_01_literature_review.md` |
| radiogenomics-curator | Source verification, dataset cards, acquisition specification | `phase_01_dataset_feasibility.md`; manifests |
| radiobiologist | Endpoint compatibility; Moringa linkage | `phase_01_endpoint_compatibility.md`; `phase_01_moringa_linkage.md` |
| ml-methodologist | Feasibility, novelty, leakage audit | `phase_01_novelty_assessment.md` §1–8 |
| statistical-reviewer | Independence, bias, pre-specification | `phase_01_novelty_assessment.md` §9 |
| research-director | Synthesis, framing, decision | `phase_01_novelty_assessment.md` §10; this document |
| reproducibility-auditor | Provenance audit; web spot-checks | Manifest fixes; script hardening |
| software-architect | Review of the QC and acquisition code | Code fixes (see the decision log) |

**Skills applied:** `literature-evidence-map`, `dataset-feasibility`, `leakage-audit`, `research-code-review`.

**Not used:** figure-editor (no figure required).
