# Study protocol: incremental value of baseline gene expression over tissue of origin for clonogenic radiosensitivity

**Status: DRAFT v0.3 (2026-10-21). Option B (estimation-focused) selected by the investigator. Not frozen. Not registered.** Implementation: `src/radiosensitivity_ml/` and `configs/experiment*.yaml` (model IDs below match the code).

**Freeze requires:**
- the investigator's choice between the δ options (§3);
- the remaining **[OPEN]** items;
- specialist sign-off;
- the investigator's signature.

The interval-method simulation (§13) can be frozen as a specification and run afterwards, before any real outcome is analysed.

Amendments after freezing go in `docs/protocol_amendments.md`.

**Status tags:** **[OPEN]** = an investigator decision is still needed; **[SIM]** = filled mechanically from the investigator-run simulation under the frozen rules in §13.

**Sources:**
- Phase 01 decisions: `docs/phase_01_reconciliation.md`, `docs/decision_log.md`;
- QC outputs: `results/tables/phase_01/identifier_qc/` (provenance in §4);
- endpoint rules R1–R10: `docs/phase_01_endpoint_compatibility.md`.

**Roles:** the investigator runs all code. Claude Code prepares code and documents only; it runs no model, simulation or analysis.

---

## 1. Background and research gap

**What is already published:**
- Published radiosensitivity gene signatures perform no better than random gene sets (RadSigBench).
- Single-gene associations with SF2 are weak.
- Label agreement between sources is moderate: CLARIFi mSF2 vs Yard integral survival r = 0.28; mSF2 vs in-house SF2 r = 0.50, n = 23 (`docs/phase_01_literature_review.md`).

**What is missing:** as of the phase_01 search (`docs/phase_01_literature_review.md`, 2026-10-21), no published model has been trained on CLARIFi. The supplementary search (P01.05) must be completed and dated before submission. No study has estimated, out of sample, what expression adds beyond tissue of origin for a clonogenic endpoint.

**The contribution:** a prespecified, leakage-controlled estimate of that increment. A null or weak result is reported as such.

**Motivating study.** The Moringa manuscript (V79, DU145, MCF-7; 0/2 Gy; crystal-violet proliferation enhancement factor, PEF) motivates the programme but supplies no data. PEF is not SF2 (`docs/moringa_scientific_linkage.md`).

## 2. Principal research question

**Does baseline gene expression provide incremental out-of-sample predictive value for clonogenic radiosensitivity beyond tissue of origin?**

**Operationally:** among the 237 eligible solid-tumour relationship components (§4), does adding 50 prespecified Hallmark gene-set scores to a tissue-of-origin model reduce the component-weighted, out-of-sample mean absolute error for raw mSF2?

## 3. Estimand, inference and claims (Option B, investigator ruling 2026-10-21)

**Option B is adopted.** It reverses the O01.13 withdrawal (decision log D03.01).

**What the study estimates:** the paired, component-weighted ΔMAE (§11) and its uncertainty.

**Superiority statement.** A one-sided superiority statement at α = 0.05 ("gain shown") is made only if:
- the lower end of the two-sided 90% interval is > 0; **and**
- that interval comes from the method adopted by the §13 simulation rule.

**If no method qualifies,** ΔMAE is reported descriptively, with no confirmatory inference.

**Prohibited claims:** clinically meaningful, biologically meaningful, or practically meaningful improvement. No δ is used.

**Reported alongside every result:**
- ΔMAE/MAE(M1);
- the literature measurement-noise benchmark, as context only.

**Convention:** one-sided α = 0.05, reported as two-sided 90% intervals; LB = the lower end.

**Model names in this protocol and the code:**

| Current | Earlier name | Model |
|---|---|---|
| M0 | B0 | global mean |
| M1 | B1 | tissue ridge |
| M1P | B2 | tissue + proliferation |
| M2 | M1 | tissue + expression |
| M2P | M1′ | beyond proliferation |
| M2X | — | expression only, for held-out tissue |
| M3 | M2 | random forest, optional |

The rest of this section is kept for the record. **The δ text below is superseded by the paragraphs above.**

**δ, the minimum meaningful improvement.** Ruling O01.13 requires δ to be justified independently and fixed before the confirmatory freeze. **No verified numeric inputs exist yet:**
- the within-lab replicate CV of clonogenic SF2 (< 30%; Nuryadi 2018, Matsui 2019) is only an upper bound;
- converting a CV to an SD needs a cited reference SF2;
- the fractionation-relevance anchor needs a cited clinical input.

**The investigator chooses one option before the freeze:**

| Option | Confirmatory test | What may be claimed | Requirements |
|---|---|---|---|
| **A: δ-anchored** (complies with O01.13 as ruled) | H0: ΔMAE ≤ δ vs H1: ΔMAE > δ; gate G-pred = LB > δ | "Meaningful improvement" if LB > δ | Before the freeze, the investigator supplies the cited formula: δ from A4 (ΔSF2 through fractionation), checked to be at least A1 (replicate noise), with no CLARIFi outcome summary used. Dated and signed |
| **B: estimation-focused** (needs a **new dated ruling reversing** the O01.13 withdrawal) | H0: ΔMAE ≤ 0 vs H1: ΔMAE > 0; gate G-pred = LB > 0 | "Evidence of an out-of-sample gain" of the estimated size, with its interval and relative size ΔMAE/MAE(B1). **No claim that it is biologically meaningful.** The literature measurement-noise benchmark is reported descriptively only | An absolute precision criterion for G-n (CI half-width in SF2 units), taken from the literature only |

**Reporting categories under Option A** (mutually exclusive; two-sided 90% CI):

| Category | Condition |
|---|---|
| Meaningful | LB > δ |
| Inconclusive | LB ≤ δ ≤ UB |
| Detectable but small | 0 < LB and UB < δ |
| No meaningful gain | LB ≤ 0 and UB < δ |

**Under Option B:** for the single confirmatory comparison, report "gain shown" (LB > 0) or "no gain shown" (LB ≤ 0), always with the point estimate and interval. A negative estimate is described by its interval; no separate "worse" verdict is given (one-sided test). All other comparisons are descriptive.

**Competing explanations:**
- **Excluded by design:** leakage, through grouped splits and in-fold preprocessing.
- **Bounded, not excluded:**
  - tissue proxying (fair tissue comparator §7; within-tissue metrics);
  - proliferation proxying (S1).
- **Cannot be removed:** label noise from literature medians. It caps achievable accuracy and is stated as a limitation.

## 4. Analysis population (confirmed by the real QC)

**Provenance:**
- QC run 2026-10-21; `run_record.json` in `results/tables/phase_01/identifier_qc/`.
- Inputs: DepMap 24Q4 (figshare 27993248 v1), Cellosaurus 56.0 (`COMPLETE.json` SHA-256 `002524b7…7342`), CLARIFi v1.0.
- Output SHA-256:
  - `summary.json`: `b09e74ec…f402`;
  - `components.csv`: `3c310374…a6da`;
  - `eligibility.csv`: `2b820626…5c`.
- The run used `--allow-dirty` on commit `76f9e6f`, with every code file hashed in the run record. **Before the freeze, commit the code and re-run the QC into a new folder**, so that the frozen cohort is tied to a clean commit. Outputs are deterministic, so the counts are expected to be identical.

**Flow:**

| Step | Records |
|---|---|
| CLARIFi records | 285 |
| Identity verified (1 ambiguous: ACH-000921) | 284 |
| Verified, with default RNA profile and expression | 273 |
| Excluded: haematopoietic | 22 (18 of them have no other reason; these form the haematopoietic stratum) |
| Excluded: Cellosaurus problematic | 15 |
| Excluded: no expression profile | 11 |
| Excluded: ambiguous identity | 1 |
| Excluded: Cellosaurus category review | 1 |
| **Eligible primary records** | **241** |
| **Eligible relationship components (confirmed links)** | **237**: 233 singletons and 4 pairs (SW480/SW620; HEC-1-A/HEC-1-B; HOS/143B; HCT 15/DLD-1) |

Some records have more than one exclusion reason.

**Grouping checks:**
- **Candidate-link graph:** also 237 components, so no ambiguity-driven merges.
- **Lineage span:** no component spans two lineages.
- **Expansion:** no relationship links were left unexpanded.

**Excluded identities, reviewed (curator, 2026-10-21):**
- **ACH-000921** (CLARIFi "NCIH1339", DepMap NCI-H157-DM): the Cellosaurus entry CVCL_0463 cross-references this DepMap ID and is itself flagged contaminated (identical to NCI-H1264). NCI-H1339 (CVCL_A472) has no DepMap ID. The histology also conflicts. **It stays excluded.**
- **The 13 problematic solid records stay excluded from the primary analysis.** No source correction changes their eligibility.

**Tissues (OncotreeLineage; 20 levels among eligible records):**
- 9 lineages have ≥ 10 components: Lung 46, CNS/Brain 23, Esophagus/Stomach 23, Bowel 21, Head and Neck 18, Breast 17, Pancreas 16, Bladder/Urinary Tract 11, Ovary/Fallopian Tube 10. **T10 = 9.**
- 11 rare lineages have 52 components: Skin 9, Bone 8, Uterus 8, Pleura 6, Prostate 5, Kidney 3, Liver 3, Peripheral Nervous System 3, Soft Tissue 3, Thyroid 3, Biliary Tract 1.
- Every one of the 10 stratification strata (§10) has at least 5 components.

**Unit of analysis:** the relationship component. Components are never split across folds, and records within a component are related lines, not replicates.

**Sensitivity populations (prespecified; none replaces the primary):**

| ID | Population | Size |
|---|---|---|
| P-S1 | Retaining Cellosaurus-problematic records | 252 records / 247 components; T10 = 10 (adds Skin). Of the 13 problematic solid records, 11 are added. ACH-000921 (also ambiguous) and ACH-001198 (also lacks RNA) keep their other exclusion reason |
| P-S2 | Candidate-link grouping | 237 components (identical to primary) |
| P-S3 | Haematopoietic stratum, analysed separately and never pooled | 18 records |
| P-S4 | Stranded-RNA exclusion: drop the 7 eligible records with stranded default profiles from the frozen splits | 234 records. The 7 are ACH-000095, ACH-000337, ACH-000455, ACH-000468, ACH-000979 (DU145), ACH-001001, ACH-001061. Note: DU145 is in Prostate (5 components) |
| P-S5 | "Identity-sound", secondary: adds records whose only exclusion is a Cellosaurus problem text beginning "Misclassified." and whose DepMap lineage reflects the corrected classification. Rule fixed now, from metadata only: Hep-G2, Caki-2, SK-N-MC qualify; SK-HEP-1 is excluded (origin uncertain) | About 3 extra components; the exact count comes from code before any outcome is analysed |

The selection comparison between included and excluded lines uses metadata only, after the freeze.

## 5. Outcome

**Primary:** raw mSF2, the literature-median clonogenic SF2 at 2 Gy (photon), untreated cells; endpoint class `clonogenic_sf`. The number of source values per line is unknown (O01.12). The QC found 0 invalid values (blank, non-numeric, non-finite, below 0 or above 1).

**Mandatory sensitivity scales:** −ln(mSF2) and logit(mSF2). Domain rules are in `docs/phase_01_remediation_report.md` §5.
- **Boundary rule (decided 2026-10-21):** (E) exclude. −ln drops y = 0; logit drops y ∈ {0, 1}. This applies only in those analyses, as a per-record filter on the frozen splits. The resulting n is logged and reported. Valid 0 and 1 values stay in the raw primary analysis. **No outcome is ever clipped.**
- MAE on a transformed scale is a different estimand. It cannot rescue a failed primary.

**Out-of-range raw predictions:** clipped to [0, 1] for every arm (`predictions.clip_raw_to_unit_interval: true`). This is a rule about predictions only, justified because SF2 is bounded. Unclipped predictions are stored. This is not an outcome transformation.

**Blinding:** CLARIFi outcome values stay sealed, with an access log, until (1) the protocol is frozen and (2) the §13 simulation result is signed in the decision log.
- The QC read each value only to test validity, and produced no distribution summary.
- One deviation is recorded: two values were displayed by a header check (D01.19).
- CLARIFi is public, so blinding is procedural, not absolute. This is stated in the paper.

## 6. Molecular predictors

**Expression:**
- File: DepMap 24Q4 `OmicsExpressionProteinCodingGenesTPMLogp1.csv` (uncorrected; log2 TPM+1; one row per model).
- The batch-corrected matrix is a sensitivity input only.

**Gene sets:**
- MSigDB Hallmark, 50 sets.
- Release string, GMT SHA-256 and licence: **[OPEN]**, verified before the freeze.
- Gene mapping: Entrez preferred; unmapped genes reported.

**Scores:** per set, the mean of genes z-scored with means and SDs fitted on the training fold only.

**Secondary feature space:** the whole transcriptome with an in-fold variance filter. Used only in M4.

**Strandedness:** only 7 of 241 eligible default RNA profiles are stranded, across 6 tissues. It is **not** a covariate in any primary model, because a 7-line indicator would be unstable. It is handled by P-S4. This amends v0.1, which put it in every arm.

No feature is selected using outcome associations outside training folds.

## 7. Tissue-of-origin information (fair comparator)

**Two separate roles of tissue:**
- **Fold stratification:** 10 strata (the 9 qualifying lineages plus one pooled "other solid"). Used **only** to balance folds.
- **Prediction:** the full 20-level OncotreeLineage. **Rare tissues are not pooled for prediction.**

**B1, the tissue-only model:**
- full one-hot encoding of all 20 lineages, with no reference level;
- the category list is fixed from the eligible metadata;
- dummies are **not** standardised;
- the intercept is unpenalised;
- ridge (L2) penalty tuned in the inner loop. This is partial pooling: rare lineages shrink toward the training mean in proportion to their size.

**Unseen lineages:** a lineage absent from a training fold has an all-zero column, so its prediction is the intercept. These cases are logged. Biliary Tract (1 component) is always unseen when it is in a test fold. This replaces the v0.1 rule "min components ≥ K×K", which only Lung could meet.

**Fairness:**
- every tissue-plus-expression model uses B1's exact tissue encoding (as its offset) and the same technical covariates (none in the primary analysis);
- every arm gets the same tuning budget.

**Tissue sensitivities (prespecified; encodings fixed from metadata only):**
- **T-S1 granular:** nested one-hot of OncotreeLineage + OncotreePrimaryDisease, with one shared ridge penalty, so the tuning budget is unchanged. Comparison: B1g vs M1g.
- **T-S2 pooled:** the 10-level stratification encoding used for prediction. This shows how much the result depends on comparator strength.
- **T-S3:** CCLE-suffix taxonomy.

**B0:** the global training mean. It is the comparator for new tissues (§16).

**Fitting weights:** proposed: each record weighted 1/|component| in every fit, matching the estimand. With 4 pairs this hardly differs from unweighted fitting.

## 8. Proliferation-correlated comparator

**B2** = B1 + the in-fold mean of the z-scored Hallmark `E2F_TARGETS` and `G2M_CHECKPOINT` scores. It is nested in, and collinear with, the expression block (declared).

**Wording:** "beyond tissue and a proliferation-correlated signal".

**Doubling time:** the DepMap 24Q4 `Model.csv` header has no doubling-time column (checked 2026-10-21; the only growth-related column is `GrowthPattern`). Not used.

## 9. Prespecified models

| ID | Model | Role |
|---|---|---|
| B0 | Global mean | Floor; new-tissue comparator |
| B1 | Tissue-only ridge (§7) | **Primary comparator** |
| B2 | B1 + proliferation score | S1 comparator |
| M1 | B1 as offset + elastic net on the 50 Hallmark scores, fitted to B1 residuals | **Primary model** |
| M1′ | B2 as offset + elastic net on the other 48 Hallmark scores | S1 model |
| M2 | Random forest on lineage one-hot + 50 scores | Secondary |
| M3 | Gradient boosting (scikit-learn), same inputs | Exploratory |
| M4 | B1 offset + elastic net on the variance-filtered transcriptome | Secondary feature space |

**Offset models:** each is a single estimator whose `fit` refits its baseline, then the elastic net on the residuals. This happens inside every inner and outer fit.

**Fitting rules:**
- one squared-error training loss for every arm;
- grids are fixed in `configs/experiment.yaml` **[OPEN]**;
- seeds are recorded;
- every model is reported, and none is chosen on outer-fold performance.

## 10. Leakage-controlled validation

**Tier (a), within-distribution (primary):**
- **Outer loop:** repeated StratifiedGroupKFold with K = 5. Groups are components; strata are the 10 stratification strata, never the outcome.
- **Inner loop:** grouped 5-fold tuning within the outer-training data.
- **Repeats:** R from the §13 rule.
- **Fitted on training data only:** gene means and SDs, set scores, variance filters, tissue coefficients.

**Split keys:**
- source: the frozen QC `components.csv` and `eligibility.csv` (hashes in §4);
- outer and inner folds are stored in `splits.parquet` and hashed into the decision log before the outcome is unsealed;
- the split function has no outcome parameter;
- sensitivity populations that **remove** records (P-S4) drop them from the frozen splits;
- sensitivity populations that **add** components (P-S1, P-S5) keep the primary assignments unchanged. Each added component goes to an outer fold (and inner fold) by a seeded round-robin within its stratification stratum, in component-ID order, using metadata only. Primary folds therefore stay paired.

**Leakage tests:** phase_03, on synthetic fixtures, including "no component on both sides of any split".

## 11. Primary estimate (exact aggregation)

**Per-record difference:** d_ir = |y_i − ŷ_ir(B1)| − |y_i − ŷ_ir(M1)|, where ŷ_ir is the out-of-fold prediction in repeat r. A positive value means expression helps.

**Aggregation:**
1. Component value: D_cr = mean of d_ir over the records i in component c.
2. Repeat value: ΔMAE_r = mean of D_cr over all 237 components.
3. **Primary estimate: ΔMAE = mean of ΔMAE_r over the R repeats.**
4. Per-fold value (needed by the Nadeau–Bengio candidate): ΔMAE_rk = mean of D_cr over the components in test fold k. Folds are pooled weighted by their component count.

**Record-weighted sensitivity.** With 4 pairs it will differ only slightly from the primary. It is reported for completeness, not as a robustness check.

**Uncertainty estimand.** The expected component-weighted paired MAE difference of the two *procedures* when trained on about (K−1)/K of a cohort of this size and structure from the same population. This is a procedure-level generalisation difference (Err), not one conditional on this dataset's fitted models.

## 12. Secondary metrics (non-gating)

- ΔRMSE and ΔR²_oos;
- calibration slope and intercept;
- ΔMAE/MAE(B1);
- within-tissue Spearman ρ;
- S1 (M1′ vs B2), S3 (M2, M3, M4);
- tissue sensitivities T-S1 to T-S3;
- populations P-S1 to P-S5;
- the sensitivity scales.

## 13. Uncertainty: interval selection by simulation (specification only; run by the investigator)

**Candidates:**
- (I1) Nadeau–Bengio corrected resampled t on the ΔMAE_rk values;
- (I2) a Bates–Hastie–Tibshirani nested-CV interval adapted to the paired, component-grouped difference. **Not implemented** (D03.02): the paired, grouped adaptation is unverified, and the compute fallback below applies. The rule is applied to I1 and I3;
- (I3) a naive component-level t-interval on D_c averaged over repeats (a reference, expected to undercover).

The component bootstrap is **descriptive only** and cannot be adopted.

**ADEMP specification (frozen with the protocol):**

- **Aims:** one-sided lower-bound coverage, false-positive rate, interval width and bias of I1–I3 for the §11 estimand.

- **Data-generating mechanism:**
  - **Expression:** lineage-conditional. X\* = the real lineage centroid (mean expression of that lineage's eligible lines) + a residual drawn from a Gaussian copula fitted to the real within-lineage residuals (features only; no outcome). This keeps the confounding of expression with tissue.
  - **Structure:** the real 20-lineage labels and real component structure (237 components; 4 pairs).
  - **Outcome:**
    - on the logit scale, logit(y) = tissue effect + β·S(X\*) + component effect + ε, where S is the 50 Hallmark scores computed on X\*;
    - the map from X\* to the signal (scorer, score standardisation, signal scale) is fitted once on a reference synthetic sample and then fixed, so the truth and every replicate share one data-generating mechanism;
    - y is then back-transformed to (0, 1).
  - **No input is a summary of real CLARIFi outcomes.**
  - **Label noise, bracketed in two levels:**
    - low: within-lab replicate noise (A1; cited CV);
    - high: cross-lab noise consistent with the published mSF2-to-in-house agreement (r = 0.50). That agreement is used as a reliability, i.e. a share of variance, never as an SD in CLARIFi units.
    - **[OPEN]**: the inputs are verified before the freeze.
  - **Scenarios:**
    - tissue-variance share: low or high;
    - expression effect, Option A: {0, 0.5δ, δ, 2δ};
    - expression effect, Option B: k ∈ {0, 0.25, 0.5} × the noise SD (`effect_k`; expression variance weight = k² × noise weight; all four variance weights are then normalised to sum to 1);
    - implemented as nine scenarios: three backgrounds (low tissue / high noise, high tissue / high noise, high tissue / low noise) × three values of k (`configs/simulation.yaml`).

- **Estimand truth:** for each scenario, the Monte Carlo mean over ≥ 200 fresh training sets of size ≈ 0.8 × n drawn from the generator, each scored on 10,000 fresh test records. Test records are real (lineage, primary disease) pairs drawn with probability 1/|component|, each its own component. The Monte Carlo SE of the truth is recorded.

- **Methods:** the exact protocol pipeline (nested CV, grids, weights). It is fixed by code hash.

- **Performance measures:**
  - one-sided coverage of the lower bound;
  - false-positive rate against the gate's own threshold:
    - Option B: P(LB > 0 | true ΔMAE ≤ 0). Under the null scenario the true ΔMAE is slightly negative, because M1 adds variance;
    - Option A: P(LB > δ | true ΔMAE ≤ δ);
  - mean width;
  - bias.

- **Nsim:** 500 per scenario (Monte Carlo SE of coverage ≈ 0.0097).

- **Adoption rule (mechanical):**
  1. A candidate qualifies if, in **every** scenario, its one-sided coverage ≥ 0.95 − 2 × MCSE (≈ 0.93) and its false-positive rate ≤ 0.05 + 2 × MCSE.
  2. Among qualifiers, adopt the one with the smallest mean width.
  3. If none qualifies, G-pred is "not assessable" and the results are reported descriptively.

- **R rule:** the smallest R in {10, 20, 50} for which the simulated SD of ΔMAE between repeats (largest scenario mean), divided by √R, is ≤ 10% of the adopted interval's mean half-width.
  - If no R qualifies, the decision records `R_rule_not_met` and R is an investigator decision (an amendment); it is never defaulted silently.
  - Coverage is simulated at R = 10. If the adopted R differs, the decision records `recheck_required`, and coverage is re-checked at that R before the real run.
  - The real run's config must name the decision file and its SHA-256; evaluation refuses to give a verdict if the method or R differ from it.

- **Compute budget:** **[OPEN]**. Investigator estimate needed; I2 with full inner tuning is costly. Fallback, fixed now: if I2 cannot be completed within budget, it is dropped from the candidates and the rule is applied to I1 and I3.

## 14. Gates and stopping rules

| Gate | Condition | If it fails |
|---|---|---|
| G-ID | Frozen QC on a clean commit; reviews resolved | Stop before splits |
| G-n | Simulated CI half-width ≤ a stated fraction of δ (Option A), or ≤ an absolute SF2 precision from the literature (Option B) **[OPEN]** | Report as an estimation-only benchmark without a confirmatory claim |
| G-pred | LB > 0 (Option B) under the interval adopted by the §13 rule | "No gain shown", or descriptive only if no method is adopted; explanation limited to aggregate stability |
| G-stab | Per gene set, a permutation p-value with +1 correction against both nulls, BH at q = 0.05 (§15). P and B are large enough to reach the smallest BH threshold | No attribution statements |

## 15. Negative controls

**Primary:**
- within-tissue permuted outcome, P seeded permutations;
- size- and expression-level-matched random gene-set collections, B seeded draws, each run through the full pipeline.

**Secondary:**
- tissue-shuffled labels;
- an olfactory-receptor gene set;
- a housekeeping set (a sanity check, not a null).

**P and B, and the BH level:**
- **BH:** q = 0.05 (investigator ruling) within each explicitly defined pathway family: the 50 Hallmark sets, tested against each null separately.
- **Resolution:** the first BH threshold is 0.05/50 = 0.001, but with P = 1000 the smallest attainable p is 1/1001 ≈ 0.000999. That clears the threshold by a hair, so **P = B = 1000 is the minimum, not a comfortable budget**.
- **Recommendation:** P = B = 1999 (smallest attainable p = 1/2000 = 0.0005, half the first threshold), if the runtime pilot shows it is affordable. 1000 remains the floor.
- **Runtime:** the investigator runs the runtime pilot first. If 1000 control runs are infeasible, G-stab is declared infeasible in advance. Stability is then reported descriptively only, without attribution statements.
- **Scope:** controls use M1 and M2 on repeat 0 only.
- **Construction:** each permuted-outcome draw moves whole relationship components within each lineage (related lines keep travelling together). Each draw has one seed, shared by every fold and model of that draw, so the null of a draw is one coherent dataset.

## 16. Feature stability, explainability and new-tissue generalisation

**Explainability:**
- grouped permutation importance with MAE loss, on outer-test rows only: M2 (B1-offset model, "M1" in the old naming) with null tests; M2P and M3 descriptive only;
- stability measures: Kendall τ, rank-biased overlap, top-k Jaccard, and sign consistency of the M2 coefficients across tasks;
- null tests use the M2 control draws.
- **Scope of stability:** it describes the resampling splits of this one population and dataset. It is not evidence of stability across datasets, assays or laboratories.

**Attribution claims:**
- need G-pred and G-stab;
- worded "associated in-model, hypothesis-generating";
- if G-pred fails, only aggregate stability is reported.

**Tier (b), new-tissue generalisation (descriptive):**
- **Design:** leave one lineage out, for each of the 9 qualifying lineages; training sizes 191–227 components.
- **Comparison:** M1 without its tissue term vs B0.
- **Reporting:** Δ_b is split into the shift in the predicted lineage mean and within-lineage Spearman ρ.
- **Wording:** "beyond a tissue-agnostic mean".

## 17. Exploratory cross-assay rank concordance (tier (c))

- **Data:** Yard 2016 (CellTiter-Glo ATP, day 9, integral survival).
- **Design:** both directions; overlap excluded by component; no target-domain fitting.
- **Metric:** Spearman ρ and Δρ, with descriptive component-bootstrap intervals.
- **Status:** exploratory (O01.15). Blocked until the Yard mapping exists (P01.08). Never pooled with mSF2, and never called validation.

## 18. Multiplicity

- One confirmatory test: G-pred (M1 vs B1; raw scale; tier (a); component-weighted; primary population; primary tissue encoding).
- S1 is tested at the same α only if G-pred passes.
- Everything else is descriptive.
- Gene-set null comparisons are BH-adjusted (q = 0.05) within the 50-set family, separately for each null. Rejections mean "importance exceeds the within-tissue permuted-outcome reference" and/or "exceeds matched random gene sets", not set-specific causal or conditional association. Importance p-values of correlated, competing sets need not satisfy PRDS, so the decisions are called "BH-adjusted", not "FDR-controlled".

## 19. Biological interpretation and the Moringa link

Interpretation is limited to stable, gated associations, worded as hypotheses.

**E3, supplementary context only:**
- **Lines:** MCF-7 (ACH-000019, CVCL_0031; Breast) and DU145 (ACH-000979, CVCL_0105; Prostate). Both are verified and eligible.
- **Content:** observed vs out-of-fold predicted mSF2 on the solid-tumour distribution.
- **Note:** DU145 has a stranded RNA profile, which is stated in the caption.

**Forbidden in E3:**
- V79;
- PEF;
- extract effects;
- radioprotection or wound-healing claims;
- normal-versus-tumour contrasts.

Pathway relevance to future Moringa experiments is discussed only as a hypothesis (`docs/phase_01_moringa_linkage.md` §7).

## 20. Limitations and reproducibility

**Limitations:**
- no independent same-endpoint validation set;
- labels are literature medians of unknown precision;
- tissue strata are small (11 lineages have fewer than 10 components);
- possible source overlap with Yard and NCI-60;
- publication-driven selection;
- clonogenic SF2 is not proliferation-free;
- strandedness is too rare to model;
- the CLARIFi licence is unresolved.

**Reproducibility:**
- run manifests: config, code, input and split hashes, seeds, thread settings;
- `--resume` checkpoints (`docs/phase_03_implementation_spec.md`);
- TRIPOD+AI reporting.

## 21. Post-evaluation triage rankings (secondary, hypothesis-generating)

**Role.** Triage orders candidates for follow-up. It runs after evaluation and explainability, reads only their saved tables and QC metadata, and fits or predicts nothing. It never changes the primary comparison, feature selection or inference. No ranking is evidence of causality, clinical utility, radioprotection or biological significance. No patient-level or treatment triage is done.

**Tiers (all tables):** A (strongest support), B (suggestive), C (exploratory), `not_prioritised` (assessable, no tier met), `not_rankable` (required evidence missing or too sparse). Thresholds are in `configs/triage.yaml`, frozen with this protocol and hashed into the triage manifest. Every source metric is kept in the output.

**A. Gene sets** (shares are proportions of the 5 × R real M2 fits; fig_s04a):
- *A:* primary gain shown, ≥ 1000 completed draws of each null, BH-significant against both nulls (`attribution_permitted`, §15), coefficient-sign consistency ≥ 0.90 and positive-importance share ≥ 0.90;
- *B:* primary gain shown, ≥ 1000 completed draws of each null, BH-significant against the within-tissue permuted-outcome null, both shares ≥ 0.75;
- *C:* positive-importance share ≥ 0.50 and the set selected (non-zero coefficient) in more than half the fits;
- *not_rankable:* any of the 5 × R real fits missing, or missing metrics.
- Without a shown primary gain, or with fewer than 1000 completed draws of either null (G-stab infeasible), every set is capped at C.
- **Claim level:** only tier A sets may be described as "associated in-model, hypothesis-generating" (§16). Tier B is "suggestive; attribution not permitted"; everything else is exploratory. `tier_reason` names the dominant coefficient sign.
- **Interpretation of the shares:** the fits share most training data and are not independent replicates. The shares are descriptive proportions of split-to-split stability in this dataset, not probabilities, confidence levels or p-values. A zero coefficient gives zero importance, so the two shares are partly redundant.
- **Interpretation of the nulls:** the permuted-outcome null tests "importance exceeds the within-tissue permuted-outcome reference" (a global null of no expression signal beyond tissue); the random-set null tests "importance exceeds size- and expression-matched random gene sets". Neither is a set-specific causal or conditional association test: a set correlated with an informative set can pass. The tested statistic is the equal-weight mean over the 5 outer folds of repeat 0, computed identically for every null draw; draws with missing folds are refused, and the p-value denominator counts only valid draws.
- Coefficient size is never used: only sign consistency, with zero coefficients counted against the set (selection instability). Sets whose scores correlate at |Spearman| ≥ 0.80 are flagged as possibly sharing importance.
- Tie-break: mean importance over all fits (descending), sign consistency (descending), set name.
- Independent radiobiological evidence is optional, investigator-curated with a citation per row, shown beside the tier and never used to set it.
- Tissue reproducibility is **not assessed**: it needs per-lineage importance, which is not generated (most lineages are too small).

**B. Cell lines.**
- *Measured CLARIFi lines* (replication or investigation): same evidence and tiers as C below; a line whose component carries a Cellosaurus problem flag is `not_rankable` until identity is resolved. These lines are **not independent validation samples**: their values were used in model development, even though each prediction was held out within cross-validation. Lines selected for extreme residuals are expected to show smaller discrepancies on re-measurement even without error (regression to the mean).
- *New, unassayed DepMap lines:* **deferred.** Missing inputs: identity QC of non-CLARIFi lines (problem flags, contamination, relatedness to CLARIFi components); investigator-run M1/M2 predictions from a refit on all eligible lines; a panel-selection rule (e.g. per-tissue quota across the predicted range) added to this protocol before predictions are viewed. A prospectively selected panel is a designed validation experiment, not an unbiased external cohort.

**C. Discrepancy review** (fig_s04b; absolute error of the repeat-averaged raw-scale out-of-fold prediction; percentile = (1 + number of evaluated lines with a strictly smaller value) / n, so ties never raise a percentile and a value shared by the whole cohort flags no line; by construction about 5% / 10% of lines, ≈ 12 / 24 of ~241, reach the 95th / 90th percentile):
- *A:* error ≥ 95th percentile under both M1 and M2;
- *B:* error ≥ 90th percentile under both models;
- *C:* error ≥ 90th percentile under one model, or prediction spread across repeats ≥ 95th percentile, or |M2 − M1| ≥ 95th percentile;
- *not_rankable:* fewer than 10 CV repeats or missing predictions.
- Tie-break: the smaller of the two error percentiles (descending), mean error (descending), DepMap ID.
- *Review type:* "technical review first" if any of: stranded RNA profile, related lines in the cohort, a Cellosaurus problem flag in the component, a pooled (small) tissue group, unstable prediction, strong model disagreement; otherwise "unexplained discrepancy", which is never read as unusual radiation biology.
- Assay variability is not assessable per line (CLARIFi reports one literature median).
- **Repeat prediction ranges** (min–max of each line's out-of-fold prediction across CV repeats) are reported as descriptive columns only. They show split-to-split variability of the prediction; they are not prediction or confidence intervals, ignore residual and label noise, and widen with R. They are never used for tiers.
- Descriptive columns also give the observed-value percentile, signed residuals and a flag for observed values in the cohort's outer 5%, because errors are largest for extreme observed mSF2 (shrinkage).

**Limitations.** One dataset and one model family; cohort percentiles always flag about the stated fraction ("relatively large here", not "abnormal"); M2 contains M1 as an offset, so "large under both models" adds limited independent information; importance describes fitted models, not biology.

## Freeze checklist

| Item | Status |
|---|---|
| δ option | **Decided: B** (D03.01) |
| α | **Decided:** one-sided 0.05, reported as two-sided 90% intervals |
| G-n precision criterion | **[OPEN]**: an absolute CI half-width in SF2 units, from the literature only. Otherwise G-n is reported descriptively |
| Boundary rule; clip rule | **Decided:** (E) exclusion on transformed scales; predictions clipped on the raw scale |
| Hallmark release and licence | **Decided:** v2025.1.Hs symbols GMT, CC BY 4.0. GMT SHA-256 to record after download **[OPEN]** |
| Grids | **Decided:** `configs/experiment.yaml` |
| BH q | **Decided:** 0.05 |
| P and B | **[OPEN]** after the runtime pilot (minimum 1000; recommended 1999) |
| Compute budget | **[OPEN]** after the runtime pilot |
| Fitting weights | **Decided:** 1/\|component\| |
| Simulation scenario values (`logit_mean`, `logit_sd`, noise shares) | **[OPEN]**: confirm the literature sources |
| QC re-run on a clean commit; hashes recorded | **[OPEN]** |
| Triage thresholds (`configs/triage.yaml`, §21) | **[OPEN]**: confirm or amend before the freeze; fixed afterwards |
| Specialist sign-off; investigator signature | **[OPEN]** |
| R, adopted interval method | **[SIM]**, after the freeze, before the outcome is unsealed |
