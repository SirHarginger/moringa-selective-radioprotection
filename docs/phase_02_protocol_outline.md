# Draft outline for `docs/protocol.md` (phase_02)

**Status:** DRAFT OUTLINE, 2026-10-21. **Not a protocol, not frozen, not registered.**

`docs/protocol.md` is written from this outline only after the phase_01 → phase_02 gate is signed. Each section below names its source decision and its status:
- **[P]** proposed;
- **[ID]** investigator-directed (provisional);
- **[QC]** depends on the identifier QC;
- **[TBD]** to be decided before the freeze.

Structure follows the `protocol-first` skill and TRIPOD+AI (Collins 2024) where applicable. The protocol references code modules by their planned location in `src/radiosensitivity_ml/` (`docs/architecture.md` §4). No code is implemented before the freeze.

---

## 0. Administrative
- **Title:** the working title (`docs/phase_01_reconciliation.md` §2) [P].
- **Version, date, protocol SHA-256 and git commit at freeze.** Amendments go in `docs/protocol_amendments.md`.
- **Registration status:** none. OSF is optional (O00.07) [TBD].
- **Roles:**
  - investigator: runs everything;
  - Claude Code: prepares code only;
  - specialist reviewers: record their sign-offs.
- **Statement:** no outcome summary had been viewed at the freeze. Attach the list of what *was* viewed: QC counts, metadata only.

## 1. Background and rationale
- Evidence map summary, from `docs/phase_01_literature_review.md`:
  - RadSigBench;
  - single-gene correlations;
  - CLARIFi label agreement.
- The Moringa manuscript is the motivating study only; PEF is not SF2 (`docs/moringa_scientific_linkage.md`).
- Why a benchmark of incremental value, and why a null result is informative.

## 2. Objectives and hypotheses
- **Primary:** the expression-beyond-tissue question (reconciliation §2) [ID].
  - H0: ΔMAE ≤ 0.
  - Meaningful-gain hypothesis: LB > δ.
- **Secondary aims:**
  - S1: beyond tissue and a proliferation-correlated signal;
  - S2: within-tissue (descriptive);
  - S3: model classes;
  - S4: cross-assay transportability;
  - S5: held-out tissue;
  - S6: attribution stability diagnostics.
- **Exploratory aims:**
  - E1: label reliability (if O01.12 data arrive);
  - E2: pathway grouping (gated);
  - E3: MCF-7 and DU145 context (supplement).
- Competing explanations to rule out: tissue proxy; proliferation proxy; leakage; label noise.

## 3. Data sources (with manifest references)
- **CLARIFi v1.0:** endpoint, licence status, k-per-line status (`data/manifests/clarifi__v1_0.yaml`).
- **DepMap 24Q4:** files, MD5/SHA-256, CC BY 4.0. 23Q4 is used for the identity audit only.
- **Cellosaurus r56.0:** fields used, and `hi`/`oi` acceptance [QC].
- **Yard 2016:** Supplementary Data 1 version [P, O01.10], endpoint class `profiling_derived_survival`.
- **MSigDB Hallmark:** release, GMT SHA-256 and licence [TBD].
- **Excluded or deferred:** NCI-60 [P, O01.11]; GSE184119 (no modelling role); ICLAC (lookup only).

## 4. Endpoints
- **Primary outcome:** raw mSF2 [ID]. Its definition is "literature-median clonogenic SF2 at 2 Gy, untreated cells".
- **Mandatory sensitivity scales:** −ln(mSF2) and logit(mSF2). Fixed with them:
  - the boundary rule for exact 0/1;
  - the out-of-range prediction rule;
  - one training loss for all arms;
  - the statement that MAE on a transformed scale is a different estimand.
- **Cross-assay endpoint:** Yard integral survival. It is never pooled with mSF2, never imputed into it, and never placed on a shared axis (rules R1–R10).
- Assay, dose, radiation quality and timing differences, tabulated (`docs/phase_01_endpoint_compatibility.md`).

## 5. Population, unit of analysis and eligibility
- **Solid-tumour rule** and the haematopoietic sensitivity stratum (reconciliation §3.2) [ID; exact strings QC].
- **Unit:** the Cellosaurus component; graph rule; flag propagation; cross-lineage rule (reconciliation §3.3) [P].
- **Exclusions:** problematic or ICLAC components (sensitivity analysis: retained); unresolved IDs; RRID disagreements [QC].
- **Target population** statement, and the after-freeze comparison of included and excluded lines.
- **Flow diagram:** counts filled in from the QC [QC].

## 6. Features
- **Expression product:** OmicsExpressionProteinCodingGenesTPMLogp1 (24Q4), with the strandedness covariate.
- **Gene-set scores:** 50 Hallmark sets, mean of in-fold z-scored genes (proposed) [P]. Gene mapping and unmapped genes are reported.
- **Proliferation score:** E2F_TARGETS and G2M_CHECKPOINT, nested in and collinear with the expression block (declared) [P].
- **Tissue encoding:** OncotreeLineage, with "other solid" pooling [ID]. Sensitivity taxonomies (i) and (ii).
- **Secondary feature space:** full transcriptome with an in-fold unsupervised filter, penalised models only.
- Every feature is decided without outcome data.

## 7. Models
- **Baselines and models:** B0 global mean; B1 tissue-only; B2 tissue + proliferation; M1 = B1 offset + elastic net on residuals [P].
- **Other model classes:** random forest secondary; gradient boosting exploratory. xgboost only with written justification.
- **Hyperparameter grids** fixed in YAML (`configs/`) [TBD]. All arms get an equal tuning budget.
- **Seeds:** recorded in the config.

## 8. Validation design
- **Tier (a), within-distribution (primary):** repeated StratifiedGroupKFold; inner grouped CV. The number of repeats R and folds K are fixed (K ≤ smallest stratum) [QC for K].
- **Tier (b), held-out tissue:** B0 comparator; Δ_b decomposition; restricted wording [P].
- **Tier (c), cross-assay transportability (exploratory rank concordance, O01.15):**
  - both directions;
  - overlap excluded by component;
  - Spearman metric;
  - no target-domain fitting;
  - forbidden-word list [P].
- **Splits:** generated from metadata only, hashed and saved before the outcome is loaded.

## 9. Metrics and estimands
- **Primary:** paired ΔMAE versus tissue-only. Sign convention, aggregation and resampling unit as in reconciliation §4.1 [ID/P].
- **Secondary (non-gating):** ΔRMSE, ΔR²_oos, calibration, ΔMAE/MAE_tissue, within-tissue Spearman.
- **Tier (c):** Spearman ρ and Δρ.

## 10. Inference and uncertainty
- **CI method:** none adopted until the investigator-run coverage assessment (O01.15). Candidates: Bates-type nested-CV interval; Nadeau–Bengio corrected *t*. Descriptive only: component bootstrap.
- **Not-assessable rule:** applies if neither method covers adequately.
- **Multiplicity:** one primary; S1 in fixed sequence; FDR for gene sets.
- **δ:** anchor rule, formula, cited inputs, date and signature. Must be fixed before the confirmatory freeze; drafting proceeds without it [TBD; O01.13 ruled].
- **Reporting:** the three-way LB/UB result.

## 11. Design analysis (sample size and precision)
- ADEMP specification: aims, data-generating mechanisms (metadata structure plus literature-derived effects), estimands, methods and performance measures [P].
- **Outputs:** CI half-width; power for LB > 0 and LB > δ; coverage; type S and type M errors.
- **Pass rule for G-n** (fraction of δ; coverage tolerance) [TBD].
- Provisional data-sufficiency floors stated with their limitation [P, O01.08].
- Synthetic data are labelled and never appear in manuscript figures.

## 12. Gates and stopping rules
| Gate | Condition | If failed |
|---|---|---|
| G-ID | Components, flags and overlap complete; unresolved IDs within tolerance | Stop before splits |
| G-n | Design-analysis precision criterion | Re-scope (estimation-only) or pivot to the label-reliability / concordance study |
| G-pred | LB > δ, using the CI method adopted after the coverage assessment (O01.13, O01.15) | Report the null; S6 aggregate-only; E2 cancelled |
| G-stab | Stability above the null-percentile threshold | No attribution statements |
| (no gate) | Cross-assay analysis is exploratory rank concordance (O01.15) | Always descriptive |

## 13. Negative controls
- **Primary:** within-tissue permuted outcome (P draws); size- and expression-matched random gene-set collections (B draws).
- **Secondary:** tissue-shuffle; olfactory-receptor set; housekeeping sanity set.
- P and B are set from a Monte Carlo error target.

## 14. Explanation plan
- **Diagnostics always reported:** Kendall τ, RBO, top-k Jaccard, sign consistency, cross-model agreement. Computed on outer test folds only; grouped permutation importance.
- **Thresholds:** relative to the nulls.
- **Attribution claims:** need both G-pred and G-stab, and are worded "associated in-model, hypothesis-generating".
- **If G-pred fails:** rules in reconciliation §5.

## 15. Leakage controls and tests (implemented in phase_03 on labelled synthetic fixtures)
- **Failure modes:** L1–L12 (`docs/phase_01_novelty_assessment.md` §8).
- **Tests:** the ml-methodologist's 10 tests, among them:
  - no component split across folds (with bridge accessions);
  - alias duplicates fail loudly;
  - in-fold transforms;
  - outer indices never reach inner fits;
  - tissue means from training indices only;
  - CLARIFi/Yard overlap exclusion;
  - split function takes no outcome;
  - seed-deterministic within-tissue permutation;
  - importances on test rows only;
  - haematopoietic exclusion by metadata.
- Ask the investigator before running any test that fits a pipeline, even with a dummy estimator.

## 16. Missing data
- No imputation of the outcome.
- Missing expression → the line is excluded and counted in the flow diagram.
- Missing metadata → human review.
- Missingness is reported per source.

## 17. Sensitivity analyses (pre-specified list)
- Outcome scales: −ln and logit.
- Taxonomy: (i) CCLE suffix; (ii) Esophagus/Stomach split.
- Haematopoietic stratum.
- Problematic or ICLAC components retained.
- Doubling-time comparator (if the field exists).
- Full-transcriptome feature space.
- k-weighted or k-stratified analyses (E1; if O01.12 data arrive).

## 18. Exploratory analyses
- **E1:** label reliability.
- **E2:** pathway grouping (gated).
- **E3:** MCF-7 and DU145 supplementary panel, with forbidden content and the required caption (reconciliation §8).

## 19. Reporting
- TRIPOD+AI checklist.
- All repeats and seeds reported.
- Deviations recorded in the amendments log.
- **Figure and table shells (no data):**
  - cell-line flow diagram;
  - ΔMAE forest plot across tiers and scales;
  - within-tissue panel;
  - stability-versus-null panel;
  - E3 supplementary panel.
- Wording rules: forbidden terms for Yard; "beyond tissue and a proliferation-correlated signal".

## 20. Reproducibility
- Run records: commit, config hash, seeds, input and output SHA-256, lockfile hash.
- Environment lockfile (P00.02).
- Manifests at `provenance_status: verified`, set by a named human.

## 21. Limitations (pre-declared)
- No independent same-endpoint external validation set.
- Label noise of unknown size.
- Possible source overlap with NCI-60 and Yard (SR-02).
- Publication-driven selection.
- Clonogenic SF2 is not proliferation-free.
- The Bates-type adaptation is unverified.
- The CLARIFi licence is unresolved.

## 22. Freeze checklist
- [ ] Every [TBD] resolved.
- [ ] Every [QC] filled from investigator-run outputs.
- [ ] Specialist reviews recorded.
- [ ] Investigator signature, date and protocol SHA-256 recorded.
- [ ] Registration decision recorded.
