# Phase 01 final reconciliation and phase_02 preparation

**Status:** for investigator review, 2026-10-21. **Nothing here is a final approval.** Every decision is either:
- **investigator-directed (provisional):** set by the investigator's reconciliation brief of 2026-10-21, which uses the word "proposed"; or
- **proposed:** by specialists and Claude Code.

The investigator signs final approvals in `docs/decision_log.md`.

**What this document does:**
- **Supersedes:** where this document and `docs/phase_01_recommendations.md` or `docs/phase_01_novelty_assessment.md` differ, this document applies: primary metric, uncertainty method, gates, sample-size reasoning, explanation gating and wording.
- **Does not repeat:**
  - the code findings, which are in `docs/phase_01_static_code_review.md`;
  - the investigator's run steps, which are in `docs/phase_01_investigator_qc_checklist.md`;
  - the protocol outline, which is in `docs/phase_02_protocol_outline.md`.

**Scope of execution:** no model, analysis, download, QC or test was run. No outcome value was read. No numerical margin or sample size was invented.

---

## 1. Consultations actually performed (2026-10-21, this pass)

All agents were run as subagents with read and web tools only. None edited files or executed code.

| Agent | Task | Main recommendations |
|---|---|---|
| statistical-reviewer | Metric, uncertainty, threshold, sample size, gates | Accept ΔMAE. A Bates-type nested-CV interval is primary; Nadeau–Bengio is the fallback; the bootstrap is descriptive. δ is set from anchors, not invented. Fisher-z is replaced by an ADEMP design analysis. Log/logit sensitivity is mandatory |
| ml-methodologist | Validation tiers, comparators, controls, leakage, explanation | Three tiers with separate comparators. Proliferation comparator = Hallmark E2F + G2M scored in-fold. Primary null controls: permuted outcome and random gene sets. Accepts the explanation ruling with refinements. 10 leakage tests |
| radiobiologist | Scale, δ anchors, Yard wording, Moringa case study, proliferation confound | Raw mSF2 is defensible if −ln and logit sensitivity analyses and a boundary rule are frozen with it. Yard is judged by rank, with a list of forbidden words. The Moringa panel goes in the supplement. Clonogenic SF2 is not proliferation-free |
| radiogenomics-curator | Solid-tumour rule, components, QC dependencies, taxonomy | Myeloid and Lymphoid are the haematopoietic OncoTree level-1 tissues (verified on oncotree.info; 24Q4 strings unverified). The component graph rule. **The QC cannot yield *n* or T₁₀ without a patch** |
| reproducibility-auditor | Static audit of scripts, tests, hook | No accidental ML execution. Three high-severity gaps in grouping and the hook. Test status unknown |
| research-director | Synthesis of the above (received as **summaries relayed by Claude Code**) | Accepted R1, R3–R6 and R8. Amended R2, R7 and R9. Recommendation: CONDITIONAL GO |

**Skills applied:**
- `protocol-first`: structure of §2–§6 and of the protocol outline;
- `leakage-audit`: §4.4 and static review D1/D2;
- `research-code-review`: the static review.

Claude Code applied them by reading their instructions; the agents applied their own lenses.

**Not consulted:** literature-reviewer, software-architect and figure-editor.
- No new literature search was done in this pass.
- The code patches are proposed, not written, so software-architect review comes when they are written.
- No figure is specified beyond the outline.

## 2. Research question (retained)

> **Primary.** Among solid-tumour CLARIFi cell lines with DepMap 24Q4 baseline expression (unit: one Cellosaurus component), does adding pre-specified gene-set expression scores to a tissue-of-origin model reduce out-of-sample prediction error for clonogenic mSF2?
> - Estimate: the paired ΔMAE (tissue-only minus tissue + expression).
> - A null result is a valid answer.

**Working title (amended):**

> *Does baseline gene expression add to tissue of origin in predicting clonogenic radiosensitivity of cancer cell lines? A prespecified, leakage-controlled benchmark with cross-assay transportability*

The title said "preregistered" before. It may say that only after formal registration (O00.07).

**Target population.** The estimate applies only to "solid-tumour lines with published clonogenic SF2 and a DepMap RNA profile". Two selection effects, publication-driven inclusion and lines lacking expression, limit generalisation. A comparison of included and excluded lines is pre-specified and run only after the freeze (statistical-reviewer).

## 3. Population, taxonomy and outcome scale (investigator-directed, provisional)

### 3.1 Outcome scale
**Primary:** raw mSF2.

**Mandatory sensitivity analyses** (R3, accepted by the research-director). These must be frozen in the **same** protocol version as the raw-scale primary:
- −ln(mSF2). Under the linear-quadratic model this equals 2α + 4β at 2 Gy. It is a reparameterisation of a single-dose value, and α and β must not be reported separately.
- logit(mSF2).

**Rules fixed with them, without inspecting outcome values:**
- the boundary rule for exact 0 or 1 values (exclusion, or a declared offset);
- one rule for predictions outside [0, 1] (clip or not), applied to every model arm;
- one training loss for all compared arms.

**Caveat (research-director).** MAE on a transformed scale is a different estimand. A median is unchanged by monotone transforms, but an MAE is not. The sensitivity analyses test whether the conclusion depends on the scale. They cannot rescue a failed raw-scale primary. Disagreement between scales is itself reported.

### 3.2 Solid-tumour rule (fixed before QC; exact 24Q4 strings checked against the downloaded `Model.csv` header and value list)

**Include** a line when all three hold:
- `OncotreeLineage` is non-blank;
- it is an OncoTree level-1 tissue other than `Myeloid`, `Lymphoid` or `Other`;
- the model is a cancer model.

**Exclude, with the reason logged:**
- Myeloid and Lymphoid lines, which form the **haematopoietic sensitivity stratum**;
- non-cancerous or immortalised-normal lines;
- engineered derivatives (if `EngineeredModel` exists; UNVERIFIED);
- `Other`.

**Hold for human review:** a blank lineage, or a string that is not an OncoTree tissue. Lineage is never inferred silently from the CCLE suffix.

### 3.3 Unit of analysis: the Cellosaurus component

A component is a connected set in an undirected graph built from **metadata only**, over CLARIFi ∪ Yard. **The Yard part is pending P01.08.** Its edges are:
1. ACH–ACH pairs sharing a non-blank DepMap `PatientID`;
2. ACH–CVCL for **every** Cellosaurus candidate and for the DepMap RRID. **Amended 2026-10-21 (D01.20):** this was "accepted match only". Linking every candidate is more conservative and can only merge components; the summary reports how many edges come from ambiguous candidates;
3. CVCL–CVCL for every `hi` (parent) and `oi` (same individual) accession, and for secondary accessions, keeping bridge accessions outside CLARIFi.

A component that touches an `hi`/`oi` accession that was never fetched is flagged for review (`component_links_not_expanded_review`).

**Rules:**
- Problematic, misidentified and ICLAC flags propagate to the whole component. Exclusion is the primary handling; retention is a sensitivity analysis.
- A component spanning more than one lineage is flagged. It is assigned by a rule fixed before QC (proposed: exclude from the primary analysis and list it).
- The split generator takes no outcome argument.

### 3.4 Taxonomy
**Primary:** DepMap 24Q4 `OncotreeLineage`.

**Pre-specified sensitivity taxonomies:**
- (i) the CCLE name suffix as distributed;
- (ii) OncotreeLineage with `Esophagus/Stomach` split by `OncotreePrimaryDisease`.

**Why sensitivity is needed:** OncotreeLineage merges oesophagus with stomach, salivary gland with upper aerodigestive tract, and large with small intestine. Merges can change tissue counts and the held-out-tissue sets. These mappings are expected from OncoTree names; line-level moves are UNVERIFIED until QC.

**Small tissues:** tissues below the minimum component count are pooled as "other solid" for the tissue baseline. They are never held out alone.

## 4. Reconciled metrics and validation plan

### 4.1 Primary metric
For repeat *r* and component-member line *i*, using identical outer splits for both arms:

d_ir = |y_i − ŷ_ir(tissue-only)| − |y_i − ŷ_ir(tissue + expression)|

- **Sign:** a positive value means expression reduces error.
- **ΔMAE:** the mean over repeats of the mean over lines.
- **Resampling unit:** the Cellosaurus component.
- Repeats are split replications, not extra samples.

**Secondary metrics (reported, never gating):**
- ΔRMSE;
- ΔR²_oos;
- calibration slope and intercept;
- the relative estimand ΔMAE / MAE_tissue.

**Resolves an inconsistency.** Earlier documents named three different primaries:
- ΔR²_oos (`phase_01_recommendations.md` §4, O01.06);
- ΔMSE with a co-condition on within-tissue correlation (`phase_01_novelty_assessment.md` §6);
- an unspecified "paired Δ" (§10.4).

All are replaced by ΔMAE versus tissue-only. Within-tissue Spearman ρ becomes descriptive (S2) and leaves the gate (R8). The example margin "ΔR²_oos ≥ 0.03" (novelty §4) had no justification and has been withdrawn.

**Why ΔMAE (statistical-reviewer; accepted by the ml-methodologist):**
- it is robust to noisy medians built from few values;
- it is in SF2 units;
- it does not depend on outcome variance within each fold.

**Costs, which must be declared:**
- it is less sensitive to rare large errors;
- elastic net and shrunken means are fitted with a squared loss, while MAE rewards the median.

### 4.2 Uncertainty (R1, the statistician's position, adopted by the research-director)

> **Investigator ruling O01.15 (2026-10-21).** No interval method is adopted until the investigator has run a coverage assessment. The methods below are **candidates**, and their order is a proposal.

1. **Candidate 1:** the Bates, Hastie & Tibshirani nested-CV interval (JASA 2024; 119(546):1434–1445; doi:10.1080/01621459.2023.2197686, verified by the statistical-reviewer). It is adapted to the paired, component-grouped loss difference.
   - This adaptation is **unverified**.
   - It is used only if a pre-specified synthetic coverage check passes (§6).
2. **Candidate 2:** the Nadeau–Bengio corrected resampled *t*, in the Bouckaert & Frank repeated k-fold form, with component counts as the train and test sizes. The statistical-reviewer should verify both citations before the freeze.
3. **Descriptive only:** the component bootstrap of out-of-fold differences. It ignores training-set variability, so it undercovers.
4. **If neither 1 nor 2 reaches the target coverage:** G-pred is "not assessable". Results are descriptive and no gain is claimed.
5. Leave-one-tissue-out and cross-assay intervals each get their own stated method. They do not borrow this one.

**Multiplicity:**
- one primary contrast;
- S1 tested in fixed sequence after the primary;
- everything else descriptive;
- gene-set statements FDR-controlled.

### 4.3 The practically meaningful threshold δ (no number set)

| Anchor | Source | Status |
|---|---|---|
| A1 Measurement-noise floor | Within-lab replicate CV of clonogenic SF2: Nuryadi 2018 (*Oncotarget*, PMID 29568388) and Matsui 2019 (*IJMS*, PMID 31450688). Both are cited by the radiobiologist; the values must be re-checked against the PDFs | The CV-to-SD conversion needs a reference SF2 level **cited from the literature, never computed from CLARIFi** |
| A2 Label agreement | mSF2 vs in-house SF2 r = 0.50 (n = 23), from Oike 2025 | Describes the noise ceiling. A correlation must **not** be converted into SF2 units using the CLARIFi outcome SD |
| A3 Fraction of tissue-only MAE | — | Leaks if estimated on the analysis lines. Allowed only as the relative secondary estimand, with the fraction fixed from A1/A4 |
| A4 Radiobiological relevance | Propagation of ΔSF2 through fractionation (survival ≈ SF2ⁿ); radiobiologist | Primary anchor |
| A5 Per-line spread of source values | CLARIFi authors (O01.12) | Pending |

**Rule:**
- δ is taken from A4.
- It is checked so that it is not below the A1 floor.
- It is written as an explicit formula from cited inputs.
- It is dated and signed in the decision log **before any CLARIFi outcome summary exists**.

**Three-way reporting (lower and upper confidence bounds, LB and UB):**
- LB > δ: meaningful gain;
- 0 < LB ≤ δ: detectable, but not shown to be meaningful;
- UB < δ: no meaningful gain.

**Timing: investigator ruling O01.13 (2026-10-21).**
- δ must be justified independently and fixed before the confirmatory protocol is frozen.
- Drafting may continue without a numerical δ.
- The earlier fallback (G-pred testing LB > 0 only) is **withdrawn**.
- A5 is an external, author-supplied input. Whether it counts as "independent" justification is for the investigator to confirm (P01.15).

### 4.4 Three validation tiers (never pooled; each with its own comparator and wording)

| Tier | Question | Design | Comparator | Metric | Allowed wording |
|---|---|---|---|---|---|
| **(a) Within-distribution** (primary) | Does expression add to tissue for new lines from tissues seen in training? | Outer: repeated StratifiedGroupKFold (groups = components; stratified by lineage only, never by outcome). Inner: grouped CV tuning every arm with the same budget. All transforms fitted on the outer-training set | B1 tissue-only | ΔMAE (primary, §4.1) | "adds out-of-sample predictive value beyond tissue of origin" (only if the gate passes) |
| **(b) Held-out tissue** (S5, descriptive) | Does an expression model transfer to a lineage it never saw? | Leave one lineage out, for lineages meeting the minimum component count. "Other solid" is never held out | B0 global mean of the training lineages. A tissue model cannot predict an unseen level | Δ_b = MAE(B0) − MAE(expression); decomposed into the shift in predicted lineage mean and within-lineage Spearman ρ. R² only on pooled predictions | "transfers beyond a tissue-agnostic mean". **Never** "beyond tissue". A gain may reflect similarity to related tissues |
| **(c) Cross-assay transportability** (S4) | Does a model trained on one endpoint rank lines on the other? | Both directions: CLARIFi → Yard-only components, and Yard → CLARIFi-only components. Overlap excluded **by component**; overlapping components go to a separate descriptive concordance table. No target-domain tuning, scaling or recalibration. Solid lines only, 24Q4 features for both | Tissue-only, on lineages seen in training; proliferation comparator also reported | Spearman ρ with a pre-specified expected sign; Δρ vs tissue-only; within-lineage ρ. **No MAE or R² across scales** | "cross-assay transportability (transportability across assays measuring different endpoints)". **Forbidden:** validation, external validation, independent validation, replication, confirms, surrogate for SF2, "SF2 in Yard", pooling, or a shared value axis |

**Context for tier (c):** Yard 2016 measures CellTiter-Glo ATP at day 9 and reports integral survival over 1–10 Gy. Any transfer result is reported in the same sentence as these assay details and the published label agreement (r = 0.28).

### 4.5 Pre-specified comparators, features and negative controls (fixed without outcome look)

**Baselines and models:**
- **B0:** global mean.
- **B1:** tissue-only (penalised lineage means, with "other solid" pooling).
- **B2:** B1 plus a proliferation score.
- **M1 (primary model):** B1 as an offset, plus an elastic net on the RNA strandedness covariate and the gene-set scores, fitted to B1 residuals in-fold, so M1 contains B1 exactly.
- **Random forest:** secondary, on the same inputs.
- **Gradient boosting:** exploratory only.
- All pre-specified models are reported. No model is chosen on outer-fold performance.

**Proliferation comparator (R9, amended):**
- The mean of in-fold z-scored MSigDB Hallmark `E2F_TARGETS` and `G2M_CHECKPOINT` scores.
- In S1, these two sets sit in the comparator and are removed from the added block.
- The score is declared nested in, and collinear with, the expression block.
- The clonogenic assay is itself growth-time dependent (colonies scored at a 50-cell threshold within a fixed window). S1 is therefore worded "**beyond tissue and a proliferation-correlated signal**", never "beyond proliferation biology".
- A DepMap doubling-time field is UNVERIFIED. If it exists, it is a sensitivity comparator only.

**Gene-set resource:**
- MSigDB Hallmark, 50 sets.
- **Before the freeze, verify:** the exact release string, the GMT file's SHA-256, the licence terms, the gene identifier type, and the mapping to DepMap gene columns. Record unmapped genes.
- **Proposed scoring:** the mean of z-scored log2(TPM+1) per set, with gene means and SDs fitted on the training fold. singscore is the alternative. GSVA is not primary, because its estimation is cross-sample.

**Negative controls:**
- **Primary diagnostics:**
  - within-tissue permuted outcome, with P seeded permutations;
  - random gene-set collections with the same number of sets and sizes, expression-level matched (binned on mean and variance computed without the outcome), with B seeded draws, each run through the full nested pipeline. Report the percentile of the real Δ.
- **Secondary:**
  - tissue-shuffled labels;
  - an olfactory-receptor "nonsense" set;
  - a housekeeping set as a sanity check only (not a true null).
- P and B are fixed from a Monte Carlo error target, never from results.

## 5. Explanation gating (O01.09 resolved by investigator ruling; provisional)

**Ruling:** pre-specified stability diagnostics are reported even under weak predictive performance. Biological attribution claims are withheld wherever predictive or stability requirements fail.

**Refinements adopted** (ml-methodologist and statistical-reviewer; accepted by the research-director):

1. **Always reported (diagnostics):**
   - rank stability across outer folds × repeats (Kendall τ, rank-biased overlap, top-k Jaccard);
   - sign consistency;
   - agreement between model classes.
   - Importances are computed on outer test folds only. The random forest uses grouped permutation importance with MAE loss.
2. **Interpretable only against nulls.** Stability is compared with the permuted-outcome and random-gene-set models. Thresholds are percentiles of those null distributions, with the percentile and draw counts fixed before the freeze. Collinear blocks and tissue proxies can rank stably with no signal.
3. **Attribution statement** (always worded "associated in-model, hypothesis-generating", never causal or mechanistic). It requires **both**:
   - G-pred passed;
   - the feature passes G-stab.
4. **If G-pred fails:**
   - aggregate stability metrics only;
   - no named "top features" in the main text;
   - named lists only in the supplement, as a stability diagnostic with a disclaimer;
   - no pathway grouping (E2 cancelled).

**Recorded residual from D1:** the ml-methodologist's earlier position was that stability is meaningful only if the gate passes. That position is now satisfied by (2) and (4). No open disagreement remains, subject to investigator confirmation.

## 6. Amended feasibility criteria (replaces the justification in recommendations §3)

**Why the old justification is withdrawn.** The thresholds in §3 (*n* ≥ 230 / 180 / 150; T₁₀ ≥ 10 / 6) were derived from Fisher-z half-widths for a single correlation. That is **not a power analysis** for a paired ΔMAE. The precision of ΔMAE depends on:
- the variance of per-line loss differences;
- the correlation between the two arms' errors (tissue is shared);
- variability from training sets and splits;
- clustering within components;
- an unknown effect size.

**Amended criteria:**

1. **Provisional data-sufficiency floors (descriptive).** The §3 tier structure and numbers are kept **only** as provisional floors. They are labelled "derived from correlation CI width; not evidence of power for the paired comparison". The investigator accepts or amends them before the QC is opened (O01.08).
2. **G-n becomes a design-analysis precision criterion.** The investigator runs a simulation design analysis, set out in ADEMP terms (Morris, White & Crowther 2019):
   - **Inputs:**
     - labelled synthetic outcomes;
     - the real **metadata** structure (component and tissue counts from the QC);
     - effect and noise levels taken from the literature only (RadSigBench R² ≈ 0; single-gene r ≈ 0.08; reliability implied by mSF2-versus-in-house agreement).
   - **Outputs:**
     - expected CI half-width (minimum detectable ΔMAE);
     - power for LB > 0 and for LB > δ;
     - coverage of the primary CI method (which also decides §4.2);
     - type S and type M errors.
   - **Pass rule:** the CI half-width is at most a pre-stated fraction of δ, **and** coverage is acceptable (O01.13 requires δ before the freeze). The fraction and the coverage tolerance are investigator-set before the run.
   - Synthetic outputs never enter manuscript figures.
3. **Other gates, unchanged in intent:**
   - **G-ID:** components, flags and the overlap table complete; unresolved IDs within tolerance.
   - **G-C3:** superseded by O01.15. Cross-assay analysis is **exploratory rank concordance** (Spearman), reported descriptively with its interval. There is no inferential gate.
   - **G-pred:** see §4.3.
   - **G-stab:** see §5.

**Limitations to state explicitly:**
- No independent same-endpoint external validation set exists.
- Label noise is of unknown size until O01.12 is answered.
- δ depends on cited external inputs that are not yet assembled. O01.13 requires δ before the freeze, so the freeze waits for it.
- The Bates-type adaptation is unverified.
- 24Q4 lineage strings and the `hi`/`oi` API fields are unverified.
- The result generalises only to the target population in §2.

## 7. Decisions that depend on the pending identifier QC

**Depends on QC results.** None of these may be decided from assumed sample sizes:

| Item | QC quantity needed |
|---|---|
| Feasibility band and G-n input | *n* (solid components with an RNA profile) |
| Held-out-tissue eligibility; S2 and S5 scope; number of folds K (K ≤ smallest stratum); membership of "other solid" | T₁₀ and per-lineage component counts |
| Whether the freeze waits for human resolution | Fraction of unresolved IDs |
| Lines held back | RRID–Cellosaurus disagreements |
| Exclusion list | Problematic or ICLAC components |
| Assignment rule actually triggered | Components spanning lineages |
| Whether the solid rule needs review entries | 24Q4 lineage strings actually present |
| Human remapping list | 23Q4 → 24Q4 identifier drift |
| Strandedness covariate composition | RNA batch mix |
| E3 feasibility | MCF-7 / DU145 presence, RNA profile and solid lineage (metadata only) |
| S4 test-set sizes (exploratory rank concordance) | CLARIFi ∩ Yard overlap on components (**needs the unscripted Yard mapping**, P01.08) |
| Design-analysis inputs | All of the above |

**Fixable now, and to be fixed before the QC is opened:**
- primary metric, sign and CI rule;
- δ anchor rule;
- outcome scale, transforms and boundary rules;
- solid rule;
- taxonomy and sensitivity taxonomies;
- small-tissue pooling rule;
- component rule and flag propagation;
- cross-lineage rule;
- unresolved-ID tolerance;
- provisional floors;
- Yard version and transfer directions;
- NCI-60 deferral;
- comparators, gene-set resource and controls;
- explanation rules.

## 8. Moringa linkage (unchanged in substance)

- **Role:** the manuscript remains the motivating biological study (`docs/moringa_scientific_linkage.md`, `docs/phase_01_moringa_linkage.md`).
- **E3 exploratory case study (R5):**
  - **Lines:** MCF-7 (ACH-000019) and DU145 (ACH-000979) only, after confirming their presence and solid lineage from metadata.
  - **Placement:** a **supplementary** panel.
  - **Content:** observed CLARIFi mSF2 and **out-of-fold** predicted mSF2, as distinct glyphs, on the solid-tumour mSF2 distribution with *n* stated.
- **Forbidden:**
  - V79 (hamster; not in DepMap);
  - the proliferation enhancement factor (PEF) or ΔOD on any axis;
  - any extract, dose-modifying or radioprotection statement;
  - any normal-versus-tumour contrast;
  - any inference from two residuals;
  - calling the panel validation or a test set.
- **Required caption content:**
  - mSF2 is the literature-median clonogenic SF2 of **untreated** cells;
  - CLARIFi excludes studies with concomitant reagents, so it carries no information about any extract;
  - the lines were chosen because they appear in the motivating study;
  - the panel is "illustrative and hypothesis-generating".
- **PEF is never treated as SF2.** The study does not claim to predict extract-induced radioprotection.

## 9. Disagreements and how they were reconciled

| # | Topic | Positions | Reconciliation | Status |
|---|---|---|---|---|
| 1 | Primary CI method | ml-methodologist: component bootstrap. statistical-reviewer: Bates-type, with Nadeau–Bengio fallback | Statistical-reviewer adopted (more conservative; agent_workflow §4). Bootstrap descriptive | **Ruled (O01.15):** candidates only; adopted after an investigator-run coverage assessment |
| 2 | Yard terminology | Investigator: "cross-assay transportability". Radiobiologist: "cross-endpoint" | Investigator's term kept and defined as "across assays measuring different endpoints"; radiobiologist's forbidden-word list adopted | Investigator to confirm |
| 3 | Sensitivity scales "where justified" | Statistician and radiobiologist: mandatory | Mandatory (justified by fractionation and bounded-scale arguments) | Adopted |
| 4 | Explanation gating (old D1) | See §5 | Investigator ruling plus refinements | Closed, pending confirmation |
| 5 | Placement of the Moringa panel | Radiobiologist: supplement | Supplement | Adopted |
| 6 | Hook fixes as a QC precondition | Research-director: the hook gaps (static review E1–E5) block any decision-making QC output. Claude Code: the hook gaps do not affect the validity of QC outputs (the investigator runs the QC); they matter before Claude Code writes phase_03 code | Repair before QC execution | **Ruled (O01.14);** implemented (D01.17), awaiting review |
| 7 | δ fallback if O01.12 stalls | Research-director: LB > 0 only, no "meaningful" claims. Alternative: wait | δ is fixed before the confirmatory freeze; no fallback | **Ruled (O01.13)** |
| 8 | Yard wording | Research-director's relayed summary described Yard as "proliferation/viability" | Corrected to the verified endpoint class: ATP-based (CellTiter-Glo) day-9 integral survival (`profiling_derived_survival`, D01.03) | Claude Code correction |

## 10. Updated recommendation

**CONDITIONAL GO, for phase_02 protocol *drafting* only.** This covers the solid-tumour CLARIFi mSF2 benchmark with:
- paired ΔMAE versus tissue-only as the primary metric;
- three separate validation tiers;
- the rules above.

**NO-GO until the freeze and investigator sign-off** for:
- any identifier-QC output used for decisions (until the code patches are approved);
- the design-analysis simulation;
- any modelling;
- any manuscript claim.

**Not NO-GO** for the study as a whole. Feasibility cannot be judged until the QC quantities exist, and no sample size is assumed here.

**Ordered work before the protocol freeze:**
1. Investigator decisions in `docs/decision_log.md`: O01.01–O01.12 and P01.11–P01.15 (O01.13–O01.16 are ruled). Sign the phase_00 gate.
2. Review the remediation (`docs/phase_01_remediation_report.md`) and run the tests.
3. Investigator runs the metadata-only QC and the Yard mapping (`docs/phase_01_investigator_qc_checklist.md`).
4. Send the author request (P01.02 / O01.12). Justify and fix δ before the confirmatory freeze (O01.13).
5. Pin the gene-set release, SHA-256 and licence. Verify the `Model.csv` fields.
6. Specify the design analysis and coverage check in the protocol; the investigator runs them; record the interval method and the G-n result.
7. Draft `docs/protocol.md` from `docs/phase_02_protocol_outline.md`. Specialist review cycle (statistical-reviewer, ml-methodologist, radiobiologist, reproducibility-auditor).
8. Investigator signs the freeze (dated, hashed), then decides formal registration (O00.07).

## 11. Wording changes made in existing documents (this pass)

- **"Preregistered":** replaced by "prespecified" in `phase_01_recommendations.md` and `phase_01_novelty_assessment.md`. Lines that name OSF registration as an *option* were kept.
- **Unjustified example margin:** "ΔR²_oos ≥ 0.03" withdrawn in `phase_01_novelty_assessment.md` §4.
- **Pointer notes added:**
  - recommendations §3 and §4, and novelty §6 and §10.4, now point to this document for the metric, gates and thresholds;
  - the `dataset-feasibility` §5.3 note corrected: the hierarchy links are parsed but not yet output.
- Earlier text is otherwise left intact as the historical record.
