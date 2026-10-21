# Phase 01 novelty and feasibility assessment

**Status:** phase_01 draft for investigator review, 2026-10-21.

**Prepared by:**
- **ml-methodologist** subagent (§1–§8; `leakage-audit` skill applied);
- **statistical-reviewer** subagent (§9);
- **research-director** subagent (§10, synthesis).

Assembled by Claude Code. Nothing was executed, fitted or downloaded, and no outcome values were inspected. Every quantitative statement is either taken from a verified source (see `docs/phase_01_literature_review.md`) or labelled as a **planning calculation** (Fisher z, two-sided α = 0.05).

---

## 1. What the verified evidence implies (interpretation, not results)

| Evidence | Source | Implication for design |
|---|---|---|
| mSF2 vs Yard integral survival r = 0.28 (n = 187); r = 0.35 for lines with ≥ 3 papers | Oike 2025 (R17) | The endpoints differ substantially, are noisy, or both. Transfer between them is bounded |
| mSF2 vs single-institution SF2 r = 0.50 (n = 23; planning 95% CI ≈ 0.11–0.76) | Oike 2025 | Limited reliability. The ceiling on attainable performance is poorly constrained |
| Strongest published single-gene mRNA candidates r ≈ 0.08 with mSF2 (NFE2L2, SQSTM1; n = 260) | Oike 2025 | Univariate expression signal is weak |
| Published radiosensitivity signatures ≈ random gene sets (out-of-sample R² 0.01 / 0.00) | O'Connor 2022, RadSigBench | Strong prior that pan-cancer expression signal is small |
| No transcriptional pathway associated with response across all tissues | Manem 2019 (R13) | Biology is tissue-specific; leave-one-tissue-out transfer is expected to be poor |
| Blood lines have lower mSF2 than solid lines (p < 0.0001) | Oike 2025 | Blood vs solid status alone separates lines; pooled metrics are inflated by it |
| Removing between-tissue signal lowered ρ from 0.43–0.62 to 0.30–0.51 (MEK inhibitors) | Lloyd 2021 (P1) | Direct precedent for the main risk (drug response, not radiation) |
| Yard → NCI-60 external C-index about 0.59–0.61, with no overlap check | Manem 2021, Kolnohuz 2024 | Cross-dataset transfer has been done for the ATP → clonogenic direction, but leakage was not controlled |

## 2. Candidate contributions

### C1. Predictive value of expression beyond tissue (mSF2)
- **Already published:**
  - univariate associations (Yard, Manem, Oike);
  - small pooled multivariable SF2 models without tissue baselines (RSI, n = 48; ANN-SCGP, n = 82);
  - the drug-response analogue (Lloyd 2021).
- **Open:**
  - no cross-validated multivariable model on CLARIFi mSF2;
  - no out-of-sample test of value added beyond tissue for clonogenic SF2.
- **Feasibility:** borderline but testable. n ≈ 260–285 if expression coverage is confirmed (**pending**). p ≈ 19,000 genes ≫ n, so dimensionality reduction must be pre-specified.
- **Expectation (hypothesis):** the gain may be small or null. A well-powered null must be a pre-specified, publishable outcome.

### C2. Robustness across tissues (leave-one-tissue-out, LOTO)
- **Already published:** Manem 2019 makes poor transfer the expected result.
- **Feasibility:**
  - Only 12 tissues have ≥ 10 lines (236 lines in total).
  - At n = 10 and r = 0.3, the 95% CI is −0.40 to 0.79 (planning), so per-tissue estimates are uninterpretable.
  - Defensible only as LOTO over the 12 larger tissues, plus a random-effects meta-analysis of within-tissue Fisher-z correlations with τ².
  - Rare tissues never form a held-out set on their own.
- **Taxonomy:** 24 CCLE suffixes vs 28 types in the article vs OncotreeLineage. Fix the vocabulary in the protocol.

### C3. Assay-dependent generalisation (clonogenic mSF2 ↔ Yard ATP integral survival)
- **Already published:** the label correlation only (r = 0.28) and Yard's 15-line clonogenic check. Model transfer was not found.
- **Feasibility:**
  - Likely: about 187 shared lines, and by arithmetic about 98 CLARIFi-only and about 346 Yard-only lines.
  - **These counts are unverified**: they depend on ID mapping, the Yard version (533 / 511 / 498) and data access.
- **Key risk:** transfer is bounded by agreement between the endpoints, so low transfer is nearly guaranteed. It is informative only if framed as **quantifying assay dependence**.
- **Design:** train on Yard-only lines and test on CLARIFi-only lines, and the reverse, with shared lines excluded from the test side.

### C4. Reliability and stability of explanations
- **Already published:** generic results on importance-measure bias and instability (Strobl 2007; Haury 2011; Ein-Dor 2006; Janizek 2023). None for radiation response.
- **Feasibility:** meaningful **only if C1 passes its pre-specified performance gate**. Explaining a model no better than tissue explains noise or tissue identity.
- **Metrics:** rank stability across outer folds, repeats, bootstraps and model classes (Kendall τ, rank-biased overlap, top-k Jaccard); aggregation to gene sets.
- **Mandatory null comparisons:**
  1. permuted outcome;
  2. a tissue-identity probe;
  3. size- and expression-matched random gene sets.

### C5. Sensitivity to label heterogeneity (number of studies per line)
- **Already published:** Oike stratified by ≥ 3 papers.
- **Feasibility:** **not feasible with the released CSV**. It needs per-line study counts and individual SF2 values, which may be recoverable from Data S2 (926 papers) or from the authors.
- If obtained, this is arguably the most novel and useful aim: label-reliability weighting and a curve of performance against label reliability.
- **Confounding risk:** how often a line has been studied is correlated with tissue and with "classic" lines.

### C6. Relevance of identified pathways to radiation-modified proliferation (Moringa link)
- **Hypothesis-generating only.** PEF ≠ SF2. Attributions are associations, not mechanisms.
- Needs pre-specified gene sets and a competitive null. Report in a separate, labelled section (phase_05).

## 3. Summary table

| Candidate | Already published? | Feasible with available data? | Key risk |
|---|---|---|---|
| C1. Expression beyond tissue (mSF2) | Partly: univariate associations; small pooled models without tissue baselines. A test of value added beyond tissue on mSF2 was not found | **Yes, borderline** (n pending); needs pre-specified feature reduction | Gain ≈ 0; inflation from blood vs solid; ceiling set by label noise |
| C2. Leave-one-tissue-out | Partly (ATP endpoint; Manem) | **Partly**: 12 tissues with ≥ 10 lines | Very wide per-tissue CIs; assay practice confounded with tissue (haematopoietic suspension lines) |
| C3. Clonogenic ↔ ATP transfer | Correlation only | **Likely**, pending Yard access and mapping | Bounded by r = 0.28; leakage through overlapping lines |
| C4. Explanation stability | Not for radiation | Only if C1 passes its gate | Explanations recover tissue or collinear gene blocks |
| C5. Label heterogeneity | Oike ≥ 3-paper stratum | **No**, without Data S2 or the authors | Dependence on the authors; confounding by line popularity |
| C6. Pathway relevance to radiation-modified proliferation | Pathway associations exist for the ATP endpoint | Hypothesis only | Association reported as mechanism; over-reading the Moringa study |

## 4. Power and precision (planning calculations)

| Scenario | Observed r | Approximate 95% CI | Width |
|---|---|---|---|
| n = 285 | 0.30 | 0.19–0.40 | ≈ 0.21 |
| n = 285 | 0.50 | 0.41–0.58 | ≈ 0.17 |
| n = 187 (CLARIFi ∩ Yard) | 0.28 | 0.14–0.41 | ≈ 0.27 |
| n = 60 (NCI-60 scale) | 0.30 | 0.05–0.51 | ≈ 0.47 |
| n = 23 | 0.50 | 0.11–0.76 | ≈ 0.65 |
| n = 10 | 0.30 | −0.40–0.79 | ≈ 1.2 |

- **Minimum detectable correlation at 80% power:** about 0.165 at n = 285; about 0.355 at n = 60.
- **Value added beyond tissue:** the protocol should pre-specify a smallest effect of interest δ, fixed from the protocol anchors before any outcome is accessed, and report an interval. (An earlier example value, ΔR²_oos ≥ 0.03, had no justification and is withdrawn; see `docs/phase_01_reconciliation.md` §4.3.)
- **Note (2026-10-21):** the correlation CIs above are descriptive planning numbers. They are **not** a power analysis for the paired ΔMAE comparison (reconciliation §6).
- **Sample-to-feature ratio (n/p):**
  - about 50 pre-specified gene-set scores: n/p ≈ 5.7 (recommended **primary** feature space);
  - a 10-gene panel: n/p ≈ 28;
  - the whole transcriptome with an in-fold unsupervised filter: n/p ≈ 0.06–0.3 (**secondary** analysis, penalised models only).

## 5. Model classes (to be decided in the protocol; nothing implemented)

- **Elastic net (primary).** Tune α and λ in an inner grouped CV over a small, pre-specified grid.
- **Random forest (comparator).** Use permutation importance on outer-test data, not impurity importance.
- **Gradient boosting (exploratory).** Shallow trees; scikit-learn first. Adding xgboost needs a protocol justification (decision-log dependency table).
- Model class is unlikely to be the main source of variance. Report all pre-specified models; do not choose among them on outer-fold performance.

## 6. Mandatory baselines (same outer folds)

1. Global mean.
2. Blood vs solid.
3. **Tissue-only** (shrunken tissue means; rare tissues pooled by a pre-specified rule).
4. Tissue plus an expression-derived **proliferation score** (pre-specified gene set; no use of the outcome).
5. **RSI.** Coefficients to be verified from the primary source. Evaluate only on lines outside its 48-line training set, and document the shift from microarray to RNA-seq.
6. Study/lab-only baseline (P00.10): **blocked** until per-study provenance is obtained.
7. Permuted outcome.

**Gate (supports P00.10):** a molecular model "adds value" only if both of these hold:
- ΔMSE_oos against baselines 3 and 4 has a CI excluding 0;
- the within-tissue meta-analytic correlation has a CI excluding 0.

Explanations (C4, C6) are interpreted only if the gate passes.

> **Superseded 2026-10-21 (`docs/phase_01_reconciliation.md` §4–§5).** The gate is now:
> - LB of paired ΔMAE versus tissue-only (B1) > δ;
> - tissue + proliferation (B2) is the S1 comparator, tested in sequence;
> - within-tissue correlation is descriptive (S2) and not part of the gate.
>
> Stability diagnostics are always reported. Attribution claims require both G-pred and G-stab.

## 7. Validation design

- **Unit:** the cell line, harmonised to ACH + CVCL. **Grouping unit:** the donor (Cellosaurus same-individual links; DepMap `PatientID`).
- **Primary:** nested CV.
  - Outer: repeated 5-fold `StratifiedGroupKFold` (grouped by donor, stratified by tissue).
  - Inner: grouped 5-fold.
  - All preprocessing inside one Pipeline.
- **Secondary:** LOTO over the 12 tissues with ≥ 10 lines.
- **Uncertainty:** no naive fold-SD intervals (they undercover; Bates et al.). Use nested-CV variance estimation or a cell-line bootstrap of out-of-fold predictions, and paired comparisons for Δ.
- **Metrics:**
  - primary: R²_oos / MSE;
  - secondary: Spearman ρ, pooled and meta-analysed within tissue; MAE;
  - calibration: slope and intercept;
  - the logit-transform decision is pre-specified.
- **External:**
  - (a) Yard on lines not in CLARIFi: a cross-assay analysis, not validation;
  - (b) NCI-60 clonogenic SF2 on lines absent from CLARIFi and from its label sources, which may be very small.
  - **There is currently no adequately powered, independent, same-endpoint external validation set.**

## 8. Leakage audit: failure modes and planned tests (phase_03; nothing run)

| # | Failure mode | Planned control / test |
|---|---|---|
| L1 | Duplicate lines, aliases, same-donor derivatives split across folds | Harmonise to ACH + CVCL. Test: no donor group appears in both train and test |
| L2 | Misidentified lines | Cellosaurus and ICLAC flags; sensitivity analysis excluding them |
| L3 | **Cross-dataset label leakage** (CLARIFi medians containing NCI-60, RSI-training or Yard values) | Provenance cross-check (Data S2 or the authors). Test: external IDs ∩ training IDs = ∅ |
| L4 | Preprocessing on all data (filters, scaling, imputation, ComBat, PCA) | Everything inside the Pipeline. Synthetic planted-signal test; `fit` sees only training indices |
| L5 | Outcome-informed choice of gene sets | Gene sets fixed in the protocol; supervised selection only in inner folds |
| L6 | Tuning or selection on outer folds; forking paths | Nested CV; pre-specified grids and model list; amendments log |
| L7 | Tissue leakage through expression | Tissue baseline in the same folds; within-tissue metrics; tissue-identity probe |
| L8 | Batch or assay origin (haematopoietic suspension assays; stranded vs unstranded RNA-seq) | Record release and SHA-256; sensitivity analysis without haematopoietic lines; test association of principal components with batch |
| L9 | Explanations computed on training data or on an all-data refit | Stability computed on outer-test explanations; any all-data refit labelled descriptive |
| L10 | Target transform or threshold fitted on all data | Parameter-free or fitted in-fold; thresholds pre-specified |
| L11 | Yard/CLARIFi overlap in cross-assay tests | Test: held-out assay set excludes training-assay lines |
| L12 | Cherry-picking seeds or repeats | Seeds in YAML; all repeats reported |

## 9. Statistical design review (statistical-reviewer)

**Sample independence.** See `docs/phase_01_dataset_feasibility.md` §5.1. The splitting unit is the **Cellosaurus connected component**: sister, parent/child and misidentification links grouped together.

**Bias sources and mitigations:**

| # | Bias | Mitigation |
|---|---|---|
| B1 | Publication and selection bias in the CLARIFi compilation (Ioannidis 2005) | Target population is "lines with published clonogenic SF2". Compare the tissue mix with DepMap descriptively. Do not generalise to unrepresented tissues |
| B2 | Lab and protocol heterogeneity (Franken 2006) | Request per-value metadata. Otherwise list it as an unmodelled error source |
| B3 | Median of a heterogeneous, unknown number of values (k) | **Blocker for the phase_02 endpoint definition:** obtain k per line; otherwise state that no precision weighting is possible |
| B4 | Outcome measurement error caps performance (achievable correlation ≤ √reliability) | Estimate reliability only if per-value data are obtained. A high R² should raise suspicion of leakage |
| B5 | Tissue confounding | Tissue-only baseline; within-tissue metrics |
| B6 | Small strata (9 of 24 tissues have ≤ 6 lines; 3 have 1 line) | Pre-specify the collapsing rule **before** outcomes are viewed. Treat haematopoietic lines as a separate sensitivity stratum |
| B7 | Multiplicity in pathway interpretation | Versioned gene-set collections; FDR; selection frequency across grouped bootstraps |
| B8 | Garden of forking paths (Gelman & Loken 2014; Varma & Simon 2006) | Prespecify and time-stamp `docs/protocol.md`, with optional formal registration (Nosek 2018; O00.07); nested CV; deviation log |
| B9 | Identifier or release drift | Pin releases; report join losses as counts |
| B10 | Moringa design | No inferential use |
| B11 | GSE184119 | Hypothesis-level pathway concordance only |

**Permitted in phase_01 versus deferred to the phase_02 protocol:**
- Permitted now: counts, identifier resolution, overlaps and missingness.
- Deferred: any correlation, agreement statistic, tissue–SF2 association, distribution plot, outlier rule or reliability estimate.

**Pre-specification recommendations for phase_02:**
1. Primary endpoint: CLARIFi mSF2 (solid lines with resolvable expression), with haematopoietic lines handled by a pre-specified rule.
2. Primary metric with calibration (Van Calster 2019).
3. Bootstrap over CVCL components, repeating the whole pipeline where feasible.
4. Nested grouped CV.
5. Paired Δ-metric against tissue-only, with a pre-set margin, reported whichever way it falls.
6. Analyses at n ≈ 60 are descriptive or transportability only.
7. Feature reduction decided without outcome data (Riley 2020).
8. Attribution stability threshold pre-specified; no biological interpretation of attributions from models that fail the gate.
9. External-assay results reported separately and never pooled.
10. Report against TRIPOD+AI (Collins 2024) where applicable.

**Review issues:**

| ID | Severity | Issue |
|---|---|---|
| SR-01 | Blocker (phase_02 endpoint) | Values per line (k) and how the median was constructed: contact Oike T, together with the licence query |
| SR-02 | Blocker (external validation) | Possible data shared between CLARIFi and NCI-60/Amundson and/or Yard |
| SR-03 | Blocker (splits) | No CVCL identity or hierarchy resolution yet (QC script ready) |
| SR-04 | High | Yard assay class: **resolved** (`profiling_derived_survival`) |
| SR-05 | High | Handling of haematopoietic lines (investigator decision) |
| SR-06 | High | Thresholds for collapsing small strata |
| SR-07 | High | Adopt the four external-validation criteria |
| SR-08 | Medium | No outcome summaries before the protocol is frozen |
| SR-09 | Medium | Margin for the paired Δ-metric |
| SR-10 | Medium | Gene sets, FDR, stability threshold |
| SR-11 | Medium | Pin DepMap release; report join losses |
| SR-12 | Low | GSE184119 restricted to pathway concordance |
| SR-13 | Low | Moringa data used as motivation only |

## 10. Research-director synthesis

Prepared by the research-director subagent (review only). Specialist inputs reached it as summaries relayed by Claude Code. It independently checked RadSigBench (PMID 35066588: published signatures "equivalent to the resampled controls") and ran a Europe PMC query for CLARIFi users (4 hits; none trains a molecular model).

### 10.1 Published vs open

| # | Contribution | Already published | Still open | Novelty | Main threat |
|---|---|---|---|---|---|
| C1 | Value added by expression beyond tissue (and beyond proliferation) on CLARIFi mSF2 | Within-dataset SF2 models (R1, R6, R8, R9, R14–R16); RadSigBench R² ≈ 0; NFE2L2 mRNA r ≈ 0.08 | No model on CLARIFi mSF2; no out-of-sample tissue-only baseline for any radiation endpoint | **Moderate.** New in combination (the estimand), not in kind | Strong prior towards a null result |
| C2 | Leave-one-tissue-out | None for radiation (drug analogue P1) | Open | Low to moderate | About 12 tissues with ≥ 10 lines; a different question from C1 |
| C3 | Clonogenic ↔ ATP transfer | **Cross-assay transfer already done** (R14, R15; no overlap check); label correlation published (r = 0.28) | Overlap-controlled transfer reported as heterogeneity; larger clonogenic panel | Low to moderate (incremental) | Ceiling set by r = 0.28; small overlap-excluded test sets |
| C4 | Attribution stability | None for radiation | Open | Moderate, conditional on C1 | Stable explanations of a model no better than baseline are uninformative |
| C5 | Label reliability (studies per line) | Partly: Oike ≥ 3-paper stratum; Oike 2020 audit of reporting; Matsui 2019 CVs | Performance as a function of label support; noise ceiling | **Potentially the most original**, but depends on data not yet available | Confounding by line popularity; analyse with tissue adjusted |
| C6 | Pathway relevance "to radiation-modified proliferation" | None | — | **Not a contribution as worded**: it imports the PEF endpoint and breaks rule R5. Reworded: "pathway-level grouping of stable attributions associated with mSF2, hypothesis-generating" | Tertiary; conditional on C1 and C4 |
| C7 | Cross-dataset identity and overlap audit on Cellosaurus components before splitting | Not found (B8) | Open | Moderate methodological value | Needs the Cellosaurus hierarchy (SR-03) |

**Novelty in one sentence.** As far as the searches so far show (Scopus, Web of Science and Scholar still pending), the new contribution is a rigorous, prespecified, leakage-controlled benchmark of incremental value on a clonogenic endpoint. "Explainable ML predicts radiosensitivity" is not new.

### 10.2 Is the original framing defensible?

**"Explainable ML predicts cellular radiosensitivity across datasets and cancer types" is not defensible as an advance claim:**
- **"Predicts"** assumes the result, when the priors point to a null.
- **"Across datasets"** implies external validation, which no available dataset qualifies for.
- **"Explainable"** puts explanation first, although explanation is interpretable only if the predictive gate passes.
- **"Across cancer types"** overstates what about 12 adequately sized tissues can support.

**Recommended framing:** a prespecified benchmark of what baseline transcriptomes add beyond tissue of origin and proliferation for clonogenic radiosensitivity, within tissues and across assays, with explanations reported only if a predictive gate passes.

### 10.3 Primary question, secondary aims, title

**Primary question.** Among solid-tumour CLARIFi lines that have a DepMap default RNA profile (unit: one Cellosaurus component), does adding pre-specified baseline gene-set scores to a tissue-of-origin model improve out-of-sample prediction of mSF2?
- **Primary contrast:** the paired difference (expression + tissue minus tissue-only) in an out-of-sample metric.
- **Validation design:** donor-grouped, tissue-stratified nested CV.
- **Inference:** a paired grouped-bootstrap CI against a pre-set margin.
- **A null result is a valid answer.**

**Secondary aims:**
- S1: value beyond tissue plus proliferation.
- S2: within-tissue performance (tissues with ≥ 10 groups; descriptive).
- S3: model-class comparison (elastic net on gene-set scores is primary; RF and GBM as comparators; full-transcriptome elastic net as a sensitivity analysis).
- S4: cross-assay transportability (heterogeneity, never validation; overlap excluded; r = 0.28 quoted).
- S5: leave-one-tissue-out (≥ 10 groups; descriptive).
- S6: attribution stability (gated).

**Exploratory aims:**
- E1: label reliability (if per-line counts are obtained).
- E2: pathway grouping (if S6 is unlocked).
- E3: contextual placement of MCF-7 and DU145 (a figure annotation only, phase_05).

**Working title:**
> *Does baseline gene expression add to tissue of origin in predicting clonogenic radiosensitivity of cancer cell lines? A prespecified, leakage-controlled benchmark with cross-assay transportability*

Title rules:
- Add "and attribution stability" only if S6 is unlocked.
- Avoid "explainable", "predicts", "across cancers" and "validated" until results exist.
- The project name may stay as it is.

### 10.4 Gates inside the study (for `docs/protocol.md`)

> **Superseded 2026-10-21.** See `docs/phase_01_reconciliation.md` §6 and `docs/phase_02_protocol_outline.md` §12. Changes:
> - G-n is a design-analysis precision criterion.
> - G-pred uses paired ΔMAE versus tissue-only.
> - G-stab thresholds are relative to null distributions.
> - G-C3 uses a rank-based metric.

| Gate | Condition | If passed | If failed |
|---|---|---|---|
| G-ID | Identifier QC, Cellosaurus components and the overlap table complete | Splits may be generated | Stop |
| G-n | Usable n meets the thresholds in `docs/phase_01_recommendations.md` §3 | Primary design | Re-scope |
| G-pred | Lower CI bound of the paired Δ above the pre-set margin | Unlocks S6 interpretation and E2 | Report the null; S6 reported only as "instability under weak signal"; E2 cancelled |
| G-stab | Stability metrics above pre-set thresholds | E2 allowed (hypothesis-generating) | No pathway claims |
| G-C3 | Overlap-excluded test set has ≥ about 100 groups with expression | Inferential reporting of transfer | Descriptive only |

### 10.5 Journal fit (O00.06; not decided; scope and policies not checked)
Venues that have published comparable work: *Briefings in Bioinformatics* (RadSigBench; Xia 2022), *PLoS Computational Biology* (Lloyd 2021), *BMC Cancer* (Manem 2021; Kolnohuz 2024) and *Cancer Science* (CLARIFi). A null-tolerant methods benchmark fits *Brief Bioinform* or *PLoS Comput Biol* best (interpretation).

### 10.6 Disagreements and reconciliation

| # | Topic | Reconciliation (for investigator approval) |
|---|---|---|
| D1 | Explanation stability when G-pred fails | Report the pre-specified stability metrics regardless; no biological reading, pathway grouping or "top genes" figure unless G-pred passes. **Unresolved: investigator decision O01.09** |
| D2 | Haematopoietic lines | Solid-only primary analysis; blood lines in a sensitivity analysis or as their own stratum |
| D3 | What counts as "external validation" | No dataset qualifies. Use "cross-assay transportability" for Yard |
| D4 | Direction of the C3 transfer | Pre-specify both directions. CLARIFi → Yard-only gives the larger test set (counts unverified) |
| D5 | Release choice | 24Q4 for features; identity checked through the 23Q4 audit; a human resolves unmatched IDs |
| D6 | Novelty of C3 | Corrected in the literature review §A6 |
| D7 | P00.10 study-only baseline | Not buildable with current data. Amend P00.10 |

No disagreement on: endpoint separation (R1–R10); GSE184119 not usable as labels; no mSF2 summaries before the protocol freeze; analyses at n ≈ 60 being descriptive only.
